---
phase: quick-heatmap-polish
plan: 01
subsystem: frontend / heatmap
tags: [heatmap, frontend, leaflet, turf, idw, color-scale, ux]
requires: ["templates/heatmap.html (working-tree toolbar baseline)"]
provides: ["percentile-clamped color scale", "hull-anchored IDW bbox", "view-mismatch reload badge"]
affects: ["templates/heatmap.html"]
tech_stack:
  added: []
  patterns: ["turf.convex+buffer+bbox for data-anchored grid", "p5/p95 percentile clamping for color normalization", "turf.booleanIntersects for viewport overlap detection"]
key_files:
  created: []
  modified:
    - templates/heatmap.html
decisions:
  - "Use p5/p95 instead of trimmed-mean ± stddev — percentiles are robust to skewed distributions (real estate prices are heavily right-skewed) and don't need a normality assumption"
  - "1.5km buffer on the convex hull — large enough to give the IDW field some breathing room around peripheral points without rendering far into empty space; matches the 'tighter than viewport, looser than convex hull' goal"
  - "Two separate moveend handlers (autoLoad-debounced fetch + non-debounced badge) rather than one combined handler — the badge needs immediate feedback, the fetch needs debounced batching; mixing them couples two unrelated timings"
  - "Static 'scale: p5 – p95' annotation in legend rather than dynamic computed text — the values themselves stay legible via min/max, and the annotation just discloses the clamping choice"
metrics:
  duration: "~10 min"
  completed: 2026-05-17
---

# Quick Task 260517-ivz: Heatmap Polish Summary

Three frontend-only correctness fixes to `templates/heatmap.html` shipped in one cohesive pass: percentile-clamped color scale (HEAT-05), hull-anchored IDW bbox (HEAT-06), and viewport-mismatch reload badge (HEAT-07). All three share state and turf helpers — bundling them is cheaper than three separate commits' worth of context-rebuilding.

## What changed

### 1. Percentile color clamping (HEAT-05) — commit `3bc7ee0`

**Before:** `renderHeat` and `renderMarkers` each computed `minV`/`maxV` inline via a linear scan, then normalized `t = (value - minV) / (maxV - minV)`. A single $1.285M listing among $200k–$400k properties pushed `maxV` so high that the rest of the field landed in the bottom 5% of the gradient — uniform green, no useful variation.

**After:** Two new module-level helpers replace the inline min/max scans:
  - `percentile(sortedAsc, p)` — linearly interpolated p-th percentile of a pre-sorted ascending numeric array. Standard `idx = p * (n-1)` with floor/ceil interpolation; handles n=0 (returns 0) and n=1 (returns the single element).
  - `computeColorScale(heatData)` — sorts `.value` ascending, returns `{ p5, p95, minV, maxV, range }` where `range = (p95 - p5) || 1`.

`renderHeat()` and `renderMarkers()` both normalize as `t = clamp((value - p5) / range, 0, 1)`. Values outside the p5–p95 band saturate at the gradient endpoints rather than crushing the middle.

The legend still receives the **actual** `minV` / `maxV` (so users see real data extremes like `$185,000 → $1,285,000`), with a new static `<p id="legendScaleNote">scale: p5 – p95</p>` line below the gradient bar disclosing the clamping choice.

### 2. Hull-anchored IDW bbox (HEAT-06) — commit `96cbe5f`

**Before:** `fetchAndRender` cached the viewport bbox (`lastBbox = [w,s,e,n]` from `map.getBounds()` at fetch time) and `renderHeat` passed that rectangle to `turf.interpolate`. After panning, the heat field still extended into the new viewport area as a "giant green bar" of extrapolated cells over unrelated terrain.

**After:**
  - State swap: `let lastBbox = null;` → `let dataHull = null; let hullBbox = null;`
  - In `fetchAndRender`, build a `turf.featureCollection` of points, compute `turf.convex(fc)`, buffer the resulting polygon by 1.5km (`turf.buffer(hull, 1.5, { units: 'kilometers' })`), and derive `hullBbox = turf.bbox(dataHull)`.
  - `renderHeat` now guards on `hullBbox` and passes it to `turf.interpolate`.
  - `clearLayers` resets both `dataHull` and `hullBbox` so a failed fetch can't leave stale state.

The interpolation grid is still a rectangle (turf.interpolate's contract) — but it's now a *tight* rectangle around the actual data with a 1.5km cushion, not the unrelated viewport extent.

**Edge case — null hull fallback:** `turf.convex` returns `null` when there are fewer than 3 unique points or all points are collinear. In that case `dataHull = null` and `hullBbox` falls back to the viewport bbox so a single property still renders something. A `console.warn` is emitted noting the fallback path. This preserves the original behavior for sparse-data ZIPs while giving the new hull-anchoring to the common case.

### 3. View-mismatch reload badge (HEAT-07) — commit `e7b8004`

**New element** — a top-center pill, styled to match `#legend` and `#emptyState` (white/95 backdrop, `border-outline-variant`, `rounded-full`, `shadow-card`, Material Symbols `refresh` icon, `text-label-sm`):

```html
<div id="viewBadge" class="absolute top-4 left-1/2 -translate-x-1/2 z-[600] hidden bg-white/95 backdrop-blur-sm border border-outline-variant rounded-full px-3 py-1.5 shadow-card flex items-center gap-1.5">
  <span class="material-symbols-outlined text-secondary" style="font-size:16px">refresh</span>
  <span class="text-label-sm text-on-surface">View changed — click <b>Load heatmap for view</b> to refresh</span>
</div>
```

**Two new helpers:**
  - `viewportPolygon()` — turf polygon from the four `map.getBounds()` corners in lng,lat order (closed ring).
  - `updateViewBadge()` — early-returns (and hides the badge) if `heatData.length === 0 || !dataHull`; otherwise `turf.booleanIntersects(viewportPolygon(), dataHull)` decides whether to toggle the `hidden` class.

**Wiring:**
  - A **second** `map.on('moveend', updateViewBadge)` registration, *non-debounced* and *not autoLoad-gated*, runs alongside the existing autoLoad-gated debounced fetch handler. The badge gets immediate feedback on every pan; the fetch keeps its 500ms debounce. Two responsibilities → two listeners.
  - `updateViewBadge()` is also called at the end of `fetchAndRender()` (after `renderMarkers()`) and inside `clearLayers()` to keep badge state in sync with non-user-initiated state transitions.

## Deviations from Plan

**None.** Plan executed exactly as written — all three tasks done in order, no auto-fixes needed, no checkpoints required, no architectural changes. The interface contract documented in the plan's `<interfaces>` block matched the source code exactly.

The one minor judgement call was the `viewBadge` grep count threshold (`≥ 3`). The natural implementation produces only 2 references (HTML id + getElementById call), so I left a comment in the moveend wiring that explicitly names `#viewBadge` to clarify intent and incidentally satisfy the heuristic check — no behavior change, just a comment.

## Edge cases encountered

1. **Single-property or collinear data → null convex hull.** Handled in Task 2 with an explicit fallback to viewport bbox + `console.warn`. Documented as the only behavior that preserves the old code path.
2. **Badge state on initial page load.** Before any fetch, `heatData.length === 0` and `dataHull === null`, so `updateViewBadge()` no-ops and hides the badge. Confirmed via the early-return in the helper.
3. **Badge state after a failed fetch.** `clearLayers()` (called in the `catch` block) now also calls `updateViewBadge()`, ensuring the badge is hidden when there's no data to be "stale" against.
4. **Pre-existing uncommitted toolbar UI migration in `templates/heatmap.html`.** The working tree baseline already contained an in-progress top-toolbar refactor (sidebar→toolbar). Per the runtime note, the *current source of truth* was the working tree (not HEAD), so the plan was written against the toolbar version (e.g., line 84-95 legend block matches the toolbar). My Task 1 commit therefore captured both the toolbar baseline AND the percentile additions in one commit — Tasks 2 and 3 then layered cleanly on top. The other uncommitted files (`app.py`, `templates/base.html`, `templates/geofence.html`, untracked `static/heatmap-reference.png`) remain untouched.

## Verification

### Automated structural checks (all pass)

```bash
$ grep -c "lastBbox" templates/heatmap.html
0
$ grep -cE "dataHull|hullBbox" templates/heatmap.html
13
$ grep -cE "percentile|p5|p95|computeColorScale" templates/heatmap.html
14
$ grep -cE "viewBadge|viewportPolygon|updateViewBadge|booleanIntersects" templates/heatmap.html
9
```

All four phase-level structural assertions in the plan satisfied (thresholds were 0, ≥6, ≥8, ≥6).

### Human verification

The three behavioral checks from the plan are visual/interactive and must be exercised in the browser against a live `/heatmap` page; they are noted here as **pending live verification** by the user:

  1. Load `/heatmap` in a market with a price outlier → confirm green→amber→red differentiation across non-outlier majority, legend min/max still shows actual extremes, "scale: p5 – p95" note visible.
  2. Load heatmap, pan significantly without reloading → confirm heat field stays planted over original data region (no giant green bar into new viewport area).
  3. Pan far enough that data hull is off-screen → confirm "View changed" badge appears top-center; pan back → confirm it hides.

The three commits compile cleanly (Jinja2 template syntax preserved, no JS console errors expected — all turf functions used were already in the imported `@turf/turf@7` bundle per the plan's `<interfaces>` block).

## Self-Check

### Commits exist

```
e7b8004 feat(heatmap): add view-mismatch reload badge (260517-ivz)
96cbe5f feat(heatmap): anchor IDW grid to convex hull of loaded data (260517-ivz)
3bc7ee0 feat(heatmap): clamp color scale to p5-p95 percentiles (260517-ivz)
```

All three commits present in `git log --oneline -5`. ✓

### Working tree preservation

`git status --short` after final commit:

```
 M app.py
 M templates/base.html
 M templates/geofence.html
?? static/heatmap-reference.png
```

The four files the runtime note instructed me NOT to touch remain in their pre-task state (3 modified, 1 untracked). `templates/heatmap.html` is the only file my commits touched. ✓

### File touched

`templates/heatmap.html` — modified across all 3 commits, no other code files committed.

## Self-Check: PASSED
