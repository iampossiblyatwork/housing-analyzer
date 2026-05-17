---
phase: quick-heatmap-polish
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - templates/heatmap.html
autonomous: true
requirements:
  - HEAT-05
  - HEAT-06
  - HEAT-07
must_haves:
  truths:
    - "An outlier price ($1.285M among $200k–$400k properties) no longer crushes the color scale to near-uniform green — the hex grid shows meaningful green→amber→red differentiation across non-outlier values."
    - "After panning/zooming the map, the heat field is anchored to the convex hull of the loaded data points, not to the viewport bbox at fetch time — no 'giant green bar' covering an unrelated rectangle."
    - "When the user pans the map so the viewport no longer overlaps the loaded data hull, a 'View changed — click Load heatmap for view to refresh' badge appears in the map top-center; it hides again when the viewport re-intersects the data hull."
    - "The legend still shows the actual min/max of the loaded data, with a small 'scale: p5 – p95' note so the clamping choice is visible to the user."
    - "Resolution / IDW power / Opacity sliders still trigger `rerenderHeat()` and update the visible field; Auto-load on pan checkbox and manual Load button behavior are unchanged."
  artifacts:
    - path: "templates/heatmap.html"
      provides: "Heatmap page with percentile-clamped color scale, hull-anchored IDW bbox, and viewport-mismatch badge"
      contains: "viewBadge"
    - path: "templates/heatmap.html"
      provides: "dataHull state and turf.convex/buffer/booleanIntersects usage"
      contains: "dataHull"
  key_links:
    - from: "renderHeat() / renderMarkers()"
      to: "percentile color clamping"
      via: "p5/p95 computed from heatData.value, used as minV/maxV for tToRGB normalization with clamp(t, 0, 1)"
      pattern: "percentile|p5|p95"
    - from: "fetchAndRender()"
      to: "dataHull state"
      via: "turf.convex on heatData featureCollection, buffered ~1.5km, stored in dataHull; hull bbox used as IDW bbox"
      pattern: "turf\\.(convex|buffer)"
    - from: "map.on('moveend')"
      to: "#viewBadge visibility"
      via: "turf.booleanIntersects(currentViewportPoly, dataHull) — hide on intersect, show otherwise; skipped when heatData.length === 0"
      pattern: "booleanIntersects"
---

<objective>
Polish the deployed `/heatmap` page with three frontend-only fixes to `templates/heatmap.html`:

1. **HEAT-05** — Replace data-min/max color normalization with **p5/p95 percentile clamping** so single outliers don't crush the gradient. Legend still displays the actual min/max plus a "scale: p5 – p95" note.
2. **HEAT-06** — Anchor the IDW grid to the **convex hull of loaded data points** (buffered ~1.5km via turf), not the viewport bbox at fetch time. Store the buffered hull as `dataHull` for the overlap check.
3. **HEAT-07** — Add a **`#viewBadge` "View changed — reload?" pill** that appears via `moveend` when the current viewport no longer intersects `dataHull`, and hides when it does. No-op when no data is loaded.

Purpose: Three correctness defects on the deployed heatmap — outlier-crushed colors give a near-uniform green field, stale viewport bbox produces a "giant green bar" after panning, and hull-anchored fields silently disappear off-screen. All three are addressed in one cohesive edit pass since they share state, helpers, and the existing turf import.

Output: Updated `templates/heatmap.html` with all three fixes, no new external dependencies (turf.convex/buffer/booleanIntersects/polygon are already in the imported `@turf/turf@7` bundle).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@templates/heatmap.html

<interfaces>
<!-- Key state and functions in templates/heatmap.html. Executor uses these directly — no further codebase exploration needed. -->

Existing module-level state (lines 124–132):
  let allData     = [];     // raw API response
  let heatData    = [];     // filtered {lat, lng, value, raw} for current metric
  let heatLayer   = null;   // L.geoJSON of interpolated cells
  let markerGroup = null;   // L.layerGroup of property CircleMarkers
  let lastBbox    = null;   // [west, south, east, north] of last successful load — REPLACE USAGE
  let autoLoad    = false;
  let moveTimer   = null;
  let currentAbort = null;

Existing helpers:
  tToRGB(t)                          // line 160 — clamps t internally; OK to pass raw t
  buildHeatData(metric)              // line 185
  formatMetric(v, metric)            // line 177
  currentMetric()                    // line 175
  METRIC_LABELS                      // line 169

Existing render functions to modify:
  fetchAndRender()                   // line 192 — currently sets lastBbox = map bounds (line 232–233); replace with hull-bbox logic
  renderHeat()                       // line 274 — currently uses minV/maxV from data; replace with p5/p95 clamping and use hull bbox
  renderMarkers()                    // line 335 — also uses minV/maxV; apply same p5/p95 clamping
  rerenderHeat()                     // line 330 — keep as-is

Existing map listener:
  map.on('moveend', ...)             // line 252 — currently only handles auto-load debounce; ADD non-debounced badge-visibility check (always-on when heatData present)

Turf 7 functions already available via @turf/turf@7 bundle (line 122):
  turf.point(coords, props)
  turf.featureCollection(features)
  turf.interpolate(fc, cellSize, opts)
  turf.convex(featureCollection)            // returns Feature<Polygon> or null
  turf.buffer(feature, distance, {units})   // distance in km when units:'kilometers'
  turf.bbox(feature)                        // returns [w, s, e, n]
  turf.booleanIntersects(featureA, featureB)
  turf.polygon([[[lng,lat], ...]])          // build a polygon from ring coords

Existing DOM elements (relevant for badge styling parity):
  #legend     — absolute bottom-4 left-4 z-[500] bg-white/95 backdrop-blur-sm border border-outline-variant rounded-lg p-3 shadow-card
  #emptyState — absolute top-1/2 left-1/2 ... bg-white/90 backdrop-blur-sm border border-outline-variant rounded-lg shadow-card
  #errorToast — absolute top-4 right-4 z-[600] ...

Existing Precision Analytical typography:
  Inter (already loaded via base.html)
  text-label-sm class
  Material Symbols Outlined icons (already loaded via base.html); use <span class="material-symbols-outlined">refresh</span>
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add percentile color clamping (HEAT-05)</name>
  <files>templates/heatmap.html</files>
  <action>
Add a module-level helper `function percentile(sortedAsc, p)` that returns the linearly interpolated p-th percentile of a pre-sorted ascending numeric array (p in [0, 1]). Use the standard `index = p * (n - 1)` formula with floor/ceil interpolation; return `sortedAsc[0]` for n===1 and handle n===0 by returning 0.

Add a helper `function computeColorScale(heatData)` that:
  - Extracts `.value` from each heatData entry into an array.
  - Sorts ascending.
  - Returns `{ p5, p95, minV, maxV, range }` where p5/p95 come from the helper above, minV/maxV are the actual data min/max (for legend display), and `range = (p95 - p5) || 1`.

Update `renderHeat()` (currently lines 274–328):
  - Replace the inline minV/maxV loop (lines 277–282) with `const { p5, p95, minV, maxV, range } = computeColorScale(heatData);`.
  - Inside the `style: feature => { ... }` callback, change `const t = (feature.properties.v - minV) / range;` to `const t = Math.max(0, Math.min(1, (feature.properties.v - p5) / range));` so values outside the p5–p95 band saturate at the gradient endpoints.
  - Pass the ACTUAL `minV` and `maxV` (not p5/p95) to `showLegend(minV, maxV, heatData.length)` so the legend continues to show the real data range.

Update `renderMarkers()` (currently lines 335–375): apply the same `computeColorScale` + clamped `t` change so markers use the same p5/p95-clamped coloring and stay visually consistent with the field.

Update `showLegend(minV, maxV, count)` (currently lines 392–399) and the legend HTML block (lines 84–95) to add a small "scale: p5 – p95" annotation under the gradient bar. Add a new element (e.g. a `<p id="legendScaleNote" class="text-label-sm text-on-surface-variant mt-1">scale: p5 – p95</p>`) below the existing min/max row. The annotation is static text — no need to wire dynamic content.

Per HEAT-05 in REQUIREMENTS.md.
  </action>
  <verify>
    <automated>grep -n "percentile\|p5\|p95\|computeColorScale" templates/heatmap.html | grep -v '^\s*//' | wc -l | awk '$1 >= 8 {exit 0} {exit 1}'</automated>
    <human-check>
Load /heatmap in a market with at least one extreme outlier (e.g. a multi-million-dollar listing among median ~$300k properties). Confirm:
  1. The hex grid shows visible green→amber→red differentiation across the non-outlier majority (not a near-uniform green field).
  2. The legend min/max values still display the actual data extremes (e.g. "$185,000" → "$1,285,000").
  3. A small "scale: p5 – p95" note appears under the legend gradient.
  4. Markers (with Listings toggle on) use the same color scheme as the underlying hexes.
    </human-check>
  </verify>
  <done>
`percentile()` and `computeColorScale()` helpers exist; both `renderHeat()` and `renderMarkers()` use p5/p95 with `clamp(t, 0, 1)`; legend shows actual min/max plus a static "scale: p5 – p95" annotation; existing slider behavior unchanged.
  </done>
</task>

<task type="auto">
  <name>Task 2: Anchor IDW bbox to convex hull of data (HEAT-06)</name>
  <files>templates/heatmap.html</files>
  <action>
Replace the `let lastBbox = null;` state declaration (line 129) with two related pieces of state:
  let dataHull = null;     // turf Feature<Polygon> — buffered convex hull of loaded points
  let hullBbox = null;     // [w, s, e, n] derived from dataHull

In `fetchAndRender()` (currently around lines 232–235), replace the block that sets `lastBbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]` with hull-derivation logic:
  1. Build a turf FeatureCollection of points from `heatData` (lng,lat order — same as in `renderHeat`).
  2. Compute `const hull = turf.convex(fc);` Guard against `hull === null` (occurs when fewer than 3 unique points or all collinear) — in that case fall back to the previous viewport-bbox behavior so a single property still renders something. Log a `console.warn` noting the fallback.
  3. When hull is non-null, `dataHull = turf.buffer(hull, 1.5, { units: 'kilometers' });` and `hullBbox = turf.bbox(dataHull);`.
  4. When falling back, `dataHull = null;` and `hullBbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];`.

Update `renderHeat()` (currently lines 274–306):
  - Replace the guard `if (heatData.length === 0 || !lastBbox) return;` with `if (heatData.length === 0 || !hullBbox) return;`.
  - Replace destructuring `const [w, s, e, n] = lastBbox;` with `const [w, s, e, n] = hullBbox;`.
  - Replace the `bbox: lastBbox` option passed to `turf.interpolate` with `bbox: hullBbox`.

Update `clearLayers()` (currently lines 384–389) to also reset `dataHull = null; hullBbox = null;` so a failed fetch doesn't leave a stale hull pointing at empty data.

Remove the now-unused `lastBbox` variable entirely (sweep the file with `grep -n "lastBbox" templates/heatmap.html` and remove every remaining reference).

Per HEAT-06 in REQUIREMENTS.md. Note: turf.interpolate still requires a rectangular bbox — the hex grid will still be rectangular, but anchored to the hull's bbox (a much tighter rectangle around the actual data), not the unrelated viewport rect.
  </action>
  <verify>
    <automated>! grep -n "lastBbox" templates/heatmap.html</automated>
    <automated>grep -cE "dataHull|hullBbox|turf\.(convex|buffer|bbox)" templates/heatmap.html | awk '$1 >= 6 {exit 0} {exit 1}'</automated>
    <human-check>
Load /heatmap, click "Load heatmap for view" on an area with data. Then pan the map significantly to one side without reloading. Confirm:
  1. The heat field stays planted over the original data region — it does NOT extend into the new viewport area as a "giant green bar."
  2. The heat field's rectangular bbox visually surrounds (with ~1.5km buffer) the loaded marker cluster, not the entire viewport.
  3. Reloading with the new viewport correctly recomputes the hull around the new data set.
    </human-check>
  </verify>
  <done>
`lastBbox` removed from the file; `dataHull` and `hullBbox` set in `fetchAndRender()` via `turf.convex` + `turf.buffer(..., 1.5, {units:'kilometers'})` + `turf.bbox`; null-hull fallback to viewport bbox with console warning preserves single-property edge case; `renderHeat()` uses `hullBbox`; `clearLayers()` resets both.
  </done>
</task>

<task type="auto">
  <name>Task 3: Add "View changed — reload?" badge with moveend overlap check (HEAT-07)</name>
  <files>templates/heatmap.html</files>
  <action>
Add a new badge element to the map container, positioned top-center, styled to match existing panels (white/95 backdrop, `border-outline-variant`, `rounded-full`, `shadow-card`, Inter via inherited base, `text-label-sm`). Place it after `#errorToast` (around line 116) so its z-index sits in the same layer:

```
<div id="viewBadge" class="absolute top-4 left-1/2 -translate-x-1/2 z-[600] hidden bg-white/95 backdrop-blur-sm border border-outline-variant rounded-full px-3 py-1.5 shadow-card flex items-center gap-1.5">
  <span class="material-symbols-outlined text-secondary" style="font-size:16px">refresh</span>
  <span class="text-label-sm text-on-surface">View changed — click <b>Load heatmap for view</b> to refresh</span>
</div>
```

Note the action uses Tailwind classes (no fenced action code, but the literal HTML markup above belongs in the template file).

Add two helper functions near the existing UI helpers (around lines 401–417):
  - `function viewportPolygon()` — reads `map.getBounds()` and returns a turf polygon built from the four corners in lng,lat order (closing ring). Use `turf.polygon([[[w,s],[e,s],[e,n],[w,n],[w,s]]])` where w/s/e/n come from `map.getBounds()` getters.
  - `function updateViewBadge()` — early-return if `heatData.length === 0 || !dataHull` (also hide the badge in that case to be safe); otherwise compute `const intersects = turf.booleanIntersects(viewportPolygon(), dataHull);` and toggle the `hidden` class on `#viewBadge` accordingly (`hidden` when intersects, visible when NOT).

Wire the check into `moveend`. The existing handler (line 252) is autoLoad-gated; add a SECOND, always-on `moveend` handler that calls `updateViewBadge()` (do not couple it with the autoLoad debounce — the badge should respond immediately to every pan):
  - Either add a separate `map.on('moveend', updateViewBadge);` registration, OR extend the existing handler to call `updateViewBadge()` unconditionally before the autoLoad gate. Either approach is fine — prefer the separate registration for clarity.

Also call `updateViewBadge()` at the end of `fetchAndRender()` (after `renderMarkers()`) and in `clearLayers()` (to hide the badge when data is cleared) so the badge state stays in sync with state transitions, not just user-initiated map moves.

Per HEAT-07 in REQUIREMENTS.md.
  </action>
  <verify>
    <automated>grep -n "viewBadge" templates/heatmap.html | wc -l | awk '$1 >= 3 {exit 0} {exit 1}'</automated>
    <automated>grep -cE "booleanIntersects|viewportPolygon|updateViewBadge" templates/heatmap.html | awk '$1 >= 4 {exit 0} {exit 1}'</automated>
    <human-check>
Load /heatmap, load heatmap data for the current view. Then:
  1. Pan slightly — confirm badge stays HIDDEN while the viewport still overlaps the data hull.
  2. Pan far enough that the data hull is completely off-screen — confirm the "View changed — click Load heatmap for view to refresh" badge appears top-center.
  3. Pan back into the data region — confirm the badge hides again.
  4. Confirm the badge does NOT appear on initial page load before any data has been fetched.
  5. Confirm the badge styling matches the Precision Analytical look (white pill, subtle border, refresh icon, Inter font).
    </human-check>
  </verify>
  <done>
`#viewBadge` element exists in template with refresh icon and Precision Analytical pill styling; `viewportPolygon()` and `updateViewBadge()` helpers defined; `moveend` triggers badge update non-debounced; `fetchAndRender()` end and `clearLayers()` also sync badge state; badge is correctly hidden when `heatData.length === 0 || !dataHull`.
  </done>
</task>

</tasks>

<verification>
Phase verification (manual, in browser):
  1. Open /heatmap in a market with mixed-price inventory (San Antonio default works; the area used to surface the $1.285M outlier is ideal).
  2. Load heatmap for view → confirm meaningful green→amber→red color differentiation; confirm "scale: p5 – p95" annotation in legend.
  3. Pan the map far from the data hull → confirm "View changed — reload?" badge appears.
  4. Pan back → confirm badge hides.
  5. Click Load heatmap for view at the new location → confirm hex grid re-anchors to new data hull (no giant rectangular green bar over irrelevant area).
  6. Toggle each slider (Resolution / IDW power / Opacity) → confirm `rerenderHeat()` still fires and updates visible field.
  7. Toggle "Auto-load on pan" → confirm existing debounce behavior preserved.

Automated structural checks (run from project root):
  - `grep -n "lastBbox" templates/heatmap.html` → no matches
  - `grep -cE "dataHull|hullBbox" templates/heatmap.html` → ≥ 6
  - `grep -cE "percentile|p5|p95|computeColorScale" templates/heatmap.html` → ≥ 8
  - `grep -cE "viewBadge|viewportPolygon|updateViewBadge|booleanIntersects" templates/heatmap.html` → ≥ 6
</verification>

<success_criteria>
- All three HEAT-0{5,6,7} requirements behaviorally satisfied (see human-check items in each task).
- Single file modified: `templates/heatmap.html`.
- No new external script tags, no new npm/pip dependencies — uses already-imported `@turf/turf@7` bundle.
- Existing controls (Type, Metric, Resolution, IDW power, Opacity, Listings toggle, Auto-load checkbox, Load button) all continue to work.
- Map panes (`heatPane`, `listingPane`) preserved.
- Page loads without JS errors in browser console.
</success_criteria>

<output>
On completion, create `.planning/quick/260517-ivz-phase-1-heatmap-polish-percentile-color-/260517-ivz-SUMMARY.md` documenting:
  - The three behaviors changed (percentile clamping, hull-anchored bbox, viewport badge)
  - Any edge cases encountered (e.g. < 3 unique points → null hull fallback path)
  - Confirmation that all three human-check items passed
</output>
