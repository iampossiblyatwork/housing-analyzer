# Housing Analyzer — Claude Memory Log

Running record of design decisions, architectural choices, and conversation context.
Updated by Claude at the end of sessions where meaningful decisions were made.

---

## Project Overview

A Flask web app for analyzing housing markets using the RentCast API, FRED, and Census ACS.
Surfaces 24-month sale and rental history with YoY comparisons, seasonal trend analysis,
leading/lagging signal chain, multi-ZIP time-series comparison, geofence search,
metric-driven heatmap, investor calculator, metrics reference, and SMS alerts via Twilio.

**Stack:** Python 3.12, Flask, gunicorn, RentCast API, FRED API, Census ACS API, Tailwind CSS (CDN), Chart.js, Leaflet, Twilio
**Entry point:** `app.py` (Flask); production WSGI server is gunicorn (see `Dockerfile`)
**Deployment:** `Dockerfile` + `render.yaml` for Render. 1 GB persistent disk mounted at `/app/.cache` so the 24-hr TTL cache and `alerts.json` survive deploys.
**API wrapper:** `housing_api.py` — thin wrapper around RentCast v1 REST API
**Macro data:** `fred_api.py` — FRED API client (optional, graceful fallback)
**Demographics:** `census_api.py` — Census ACS client (optional, graceful fallback)
**Cache:** `cache.py` — file-based TTL cache, `.cache/` dir (gitignored)
**Dev fixture store:** `dev_cache.py` — SQLite-backed; when `DEV_MODE=1`, decorated API wrappers consult it first and write back on miss. `dev_cache.sqlite` is committed so devs can work offline against captured responses.
**Alert engine:** `alerts.py` — JSON-file-backed alert store with Twilio SMS delivery
**Metrics layer:** `metrics.py` — full structured encoding of the PDF reference document

**Routes:**
| Route | Purpose |
|-------|---------|
| `/` | Landing — feature grid + analytics principles callout |
| `/market` | 24-month market analysis — 5 tabs, YoY panels, MA overlays, macro context |
| `/signals` | Leading vs. lagging signal chain dashboard (NAHB → Permits → … → Prices) |
| `/compare` | Multi-ZIP (2–3) time-series overlay with metric switcher and YoY grouped bars |
| `/property` | Address lookup — AVM estimates + investor quick-screen + Census demographics |
| `/heatmap` | Metric-driven IDW interpolated heatmap (price, price/sqft, DOM) |
| `/geofence` | Map-based radius property search with Leaflet heatmap |
| `/investor` | Income-property calculator (NOI, cap rate, GRM, DSCR) |
| `/reference` | Full metrics glossary rendered from PDF knowledge |
| `/alerts` | SMS alert creation and management |
| `/api/heatmap-data` | JSON endpoint — geofence search → metrics for heatmap |

---

## Architecture Decisions

### Flat file structure (no packages/submodules)
All Python files live at the project root. No `src/` layout, no packages.
Simple enough that the overhead of packaging isn't worth it.

### RentCast as primary data source, FRED + Census as optional supplements
All local market data comes from `api.rentcast.io/v1`. FRED and Census are opt-in —
each has its own env var (`FRED_API_KEY`, `CENSUS_API_KEY`). If unconfigured, affected
UI sections show a clear "configure this" message rather than erroring.

### File-based TTL cache (cache.py)
Simple JSON cache in `.cache/` at project root (gitignored). Cache key = MD5 of
(namespace, params). TTL: 24 hours for FRED and RentCast, 7 days for Census.
No Redis, no database — keeps the stack flat. If cache is stale or corrupt,
falls through to live API call transparently. Exposes both inline `get/put`
helpers and a `@cache.cached(namespace, ttl)` decorator (used by
`housing_api.py` to gate all RentCast calls to one live hit per 24h).

In production on Render, `.cache/` is mounted on a 1 GB persistent disk so the
cache survives deploys/restarts — without it, every redeploy re-burns the
first wave of RentCast calls.

### Dev fixture store (`dev_cache.py`, SQLite, committed)
Separate from the runtime TTL cache. When `DEV_MODE=1` is set, the
`@dev_cache.fixture(namespace)` decorator on each API wrapper checks
`dev_cache.sqlite` first; on miss it falls through to the live API and writes
the response back. The DB is checked into git so devs can iterate against a
captured snapshot of real responses without burning quota.

Populate it by running `DEV_MODE=1 python record_fixtures.py 78244 90210 ...`
with real keys in `.env`, then commit the updated `dev_cache.sqlite`.

In dev mode, `fred_api.is_configured()` and `census_api.is_configured()`
return True even without an API key, so template "configure this" branches
yield to the data branches (which read from the fixture).

This is NOT a TTL cache. Entries don't expire — it's a frozen snapshot. The
runtime TTL cache (`cache.py`) still applies on top in production.

### Alerts stored as flat JSON (`alerts.json`)
No database. Alerts are a list of dicts serialized to `alerts.json` at the project
root. Chosen for simplicity — the alert volume is low and there's no need for querying,
indexing, or concurrency safety at this scale. SQLite would be the natural next step.

### Alert evaluation happens on page load, not on a schedule
`alerts.check_and_notify()` is called every time `/market` is loaded for a given ZIP.
A background scheduler was not added — keeping it simple until there's real need.

### SMS-only alerting (Twilio)
Only SMS delivery is implemented. Twilio credentials are optional — if not configured,
`send_sms` returns `False` gracefully and logs to stdout.

### Chart.js rendered client-side from inline JSON
History data is serialized via `{{ sale_chart | tojson }}`. Chart.js draws line/bar
charts in the browser. No server-side chart generation; keeps the server stateless.

### Tailwind CSS via CDN (migrated from Bootstrap 5 in session 2)
No local asset bundling, no build step, no npm. Tailwind config is embedded in a
`<script id="tailwind-config">` block in `base.html` — extends the default theme
with the full "Precision Analytical" design token set.

**Why Tailwind over Bootstrap:** The Stitch design kit (provided as a zip) used
Tailwind with the "Precision Analytical" system. Matching it exactly required
Tailwind's utility model; Bootstrap's component model would have required overriding
too much. The CDN approach keeps the zero-build constraint.

### Sidebar layout (migrated from top navbar in session 2)
The Stitch reference kit used a sticky sidebar nav. Adopted for the same reason —
it's the intended layout for a data-dense analytical tool. Sidebar is hidden on
mobile, replaced by a hamburger slide-in overlay.

### IDW interpolation for heatmap (not kernel density estimation)
The heatmap uses Inverse Distance Weighting, not Leaflet.heat (which is density-based).
KDE shows where properties are clustered; IDW shows the VALUE of a metric across
the spatial field. That's what the user asked for: "each data point should be a
point in the mesh" — a continuous value field, not a density cloud.

**Implementation:** `turf.interpolate` generates a hex IDW grid (configurable
resolution + IDW power via toolbar sliders) sized to the **convex hull** of
loaded points (buffered 3 km, not the viewport bbox — otherwise panning
leaves a giant rectangle stretched across unrelated area). The grid is
rendered as Leaflet GeoJSON polygons with `preferCanvas: true` for speed,
and **clipped to the buffered hull** so hexagons in the bbox corners that
fall outside the hull don't render fake extrapolated values. A dashed
outline of the hull is drawn so users can see where the field's authority
ends.

The color gradient is clamped to the p5–p95 band so outliers don't wash
the field to a uniform color; the legend surfaces both the gradient
endpoints (p5/p95) and the raw data range (min/max) so the saturation
isn't hidden from the user.

Hull + bbox are recomputed on every metric switch — DOM in particular is
sparse and produces a much smaller hull than `price`.

### metrics.py encodes PDF as Python, not a database or vector store
The PDF "Measuring Real Estate Trend and Health" was ingested as a Python module.
Thresholds are stable reference data (not user content), Python functions are testable
and directly callable, no LangChain/embeddings needed, keeps stack flat.

### YoY comparisons as the primary analytical frame
The PDF is explicit: DOM and inventory are highly seasonal — always compare YoY, not
month-over-month. All time-series views now surface YoY % change as a bar chart
alongside the raw line, and KPI cards show a YoY delta chip. This is the correct
comparison frame per the source document.

### 12-month trailing MA as seasonal adjustment proxy
Full seasonal adjustment (X-13ARIMA, STL) requires more history than RentCast
provides and significant complexity. A 12-month trailing MA removes the seasonal
cycle while preserving the underlying trend — close enough for the ZIP-level series
(~24 months) we're working with. Labeled "12-mo MA" on charts, never "seasonally
adjusted" to be methodologically accurate.

### historyRange bumped to 24 months as default
RentCast `/markets` supports up to 24 months. Bumped from 12 to 24 everywhere so
YoY comparisons have full year-ago data from month 13 onward.

### FRED API optional with graceful degradation
FRED requires a free API key. Rather than blocking the app or requiring setup,
FRED-powered sections (macro tab on market page, national indicators on signals page)
show a clear "add FRED_API_KEY to .env" message when unconfigured. Same pattern for
Census ACS. This matches the Twilio pattern already in place.

---

## Module: `metrics.py` — Domain Knowledge Layer

**Source:** `real-estate-market-metrics.pdf` (committed to repo)

### Supply indicators
`interpret_months_of_supply`, `interpret_absorption_rate`, `interpret_days_on_market`,
`interpret_sale_to_list_ratio`, `interpret_price_cuts_share`

### Affordability indicators
`interpret_nar_affordability_index`, `interpret_price_to_income`, `interpret_price_to_rent`, `interpret_vacancy_rate`

### Investor / income-property metrics
`compute_noi`, `compute_grm`, `interpret_grm`, `compute_cap_rate`, `interpret_cap_rate`,
`compute_dscr`, `interpret_dscr`

### Time-series analytics (added session 3)
- `build_yoy_series(labels, values)` — parallel YoY % changes; None where year-ago absent
- `compute_moving_average(values, window=12)` — trailing N-period MA, tolerates None values

### Signal chain (added session 3)
- `SIGNAL_CHAIN` — ordered list of 7 nodes (NAHB, Permits, Starts, Inventory, DOM, SNLR, Prices)
  Each node has: id, name, description, source, fred_series, type (leading/coincident/lagging), thresholds
- `assess_signal_chain(market_data, macro_data)` — enriches chain with live values, YoY,
  and badge/status from RentCast + FRED data

### Composite signal detection
`detect_composite_signals(sale_chart)` — compares last 3 months vs prior 3 months.
Detects: cooling signal, softening, healthy expansion, supply expanding, hot market.
Requires ≥6 months of history; falls back to "Mixed signals."

### Convenience wrappers
`interpret_market(data)` — takes RentCast market stats dict, returns labeled interpretations
with badge colors for MOS, DOM, price-to-rent, GRM.
Badge values: "success" | "warning" | "danger" | "info" | "secondary"

### Reference constants
`PRICE_INDICES`, `DEMAND_SIGNAL_LEAD_TIMES`, `COMPOSITE_INDICES`, `ECONOMIC_DRIVERS`,
`COMMON_PITFALLS`, `SCOPE_NOTES`, `DATA_SOURCES`, `ANALYTICAL_PATTERNS`,
`HOUSING_SUPPLY_CHAIN`, `INVENTORY_INTERPRETATION`, `WITHDRAWN_RATE_NOTE`,
`MORTGAGE_RATE_SENSITIVITY`, `RATE_LOCK_IN_NOTE`, `FORECLOSURE_NOTE`, `MEDIAN_PRICE_NOTE`

---

## Module: `fred_api.py` — Macro Context Layer

**API:** `api.stlouisfed.org/fred/series/observations` (free key required)
**Env var:** `FRED_API_KEY` in `.env`

Series fetched (36-month history, cached 24hr):
- `MORTGAGE30US` — 30-yr fixed mortgage rate, weekly
- `DGS10` — 10-year Treasury yield, daily
- `CPIAUCSL` — CPI seasonally adjusted, monthly
- `UNRATE` — unemployment rate, monthly
- `NAHBMMI` — NAHB builder confidence (earliest signal in chain), monthly
- `PERMIT` — building permits (thousands), monthly
- `HOUST` — housing starts (thousands), monthly

`get_macro_context()` → dict keyed by series_id with `{name, unit, latest, history}`.
`is_configured()` → bool (drives UI conditional rendering).

---

## Module: `census_api.py` — Demographics Layer

**API:** `api.census.gov/data/2023/acs/acs5` (free key required)
**Env var:** `CENSUS_API_KEY` in `.env`

Returns per-ZIP: `median_income`, `population`, `housing_units`, `vacant_units`,
`vacancy_rate` (computed). Cached 7 days.

Used in `/market` Macro Context tab and `/property` page to compute price-to-income ratio.

---

## Module: `cache.py` — File-Based TTL Cache

Stores JSON files in `.cache/` (gitignored). Key = MD5(namespace + params).
- `get(namespace, params, ttl)` → cached data or None
- `put(namespace, params, data)` → writes entry

---

## Design System: Precision Analytical (Tailwind)

Adopted in session 2 from the Stitch design kit.

**Key color tokens:**
| Token | Hex | Use |
|-------|-----|-----|
| `primary` | `#0b1c30` | Headings, key text |
| `secondary` | `#3755c3` | Royal blue — CTAs, active nav, links |
| `on-tertiary-container` | `#005236` | Positive / green data |
| `error` | `#ba1a1a` | Negative / red data |
| `surface` | `#f8f9ff` | Page background |
| `outline-variant` | `#c6c6cd` | Card borders |
| `surface-container-low` | `#eff4ff` | Table headers, sidebar active |

**Typography:** Inter (Google Fonts). Custom font-size tokens: `text-headline-lg/md`,
`text-label-md/sm`, `text-body-md/lg`, `text-data-tabular`.

**Icons:** Material Symbols Outlined (Google Fonts CDN). Use `filled` class to toggle fill.

**Card pattern:** `bg-white border border-outline-variant rounded-lg` with
`hover:shadow-card transition-shadow`.

**Badge macro** (inline in each template that needs it):
Maps: success→emerald, warning→amber, danger→red, info→blue, secondary→gray.
Repeated in each template rather than base.html because Jinja2 macros don't
inherit across `{% extends %}` without explicit import.

**Chart colors (Precision Analytical palette):**
- Primary line: `#3755c3` (secondary blue)
- MA overlay: `#d97706` (amber), dashed
- Positive/growth: `#10b981` (emerald)
- Negative/concern: `#ef4444` (red)
- YoY bars: emerald (positive) / red (negative) with 0.75 alpha

---

## Market Page — Chart Architecture

Each tab uses Chart.js with no additional plugins. All charts rendered from
inline JSON passed via Jinja2 `| tojson` filter.

**Price Trends tab:**
- `priceChart` — 24-month price line + 12-mo MA overlay (dashed amber)
- `priceYoyChart` — YoY % change bar chart (green/red coloring)

**Supply & Demand tab:**
- `domChart` — 24-month DOM line + MA
- `listingsChart` — 24-month active listings + MA
- `domYoyChart` — DOM YoY bar
- `listingsYoyChart` — listings YoY bar

**Rental tab:**
- `rentChart` — 24-month rent + MA
- `rentYoyChart` — rent YoY bar

**Macro Context tab:**
- `mortgageChart`, `unemployChart`, `cpiChart`, `treasuryChart` — FRED series lines
- Only rendered when `fred_configured` is True

---

## Heatmap Implementation Notes

**Route:** `/heatmap` (page) + `/api/heatmap-data` (JSON)

**Data flow:**
1. User clicks map → sets lat/lng inputs
2. "Load Heatmap" → `fetchAndRender()` hits `/api/heatmap-data`
3. Backend calls `search_by_geofence()`, extracts `price`, `price_per_sqft` (computed),
   `dom` per property → returns JSON array
4. Client filters to selected metric, runs IDW on canvas, renders

**Scale factor:** `scale = max(0.08, min(0.18, 800 / (W * N^0.3)))` — adapts to density,
keeps render < 100ms for typical datasets.

**Color scale:** emerald `#10b981` (low) → amber `#f59e0b` (mid) → red `#ef4444` (high).
Same direction for all metrics; users read legend min/max for orientation.

**Known limitation:** `daysOnMarket` is often null on individual RentCast property
records — more reliably available in market-level aggregates. Zero valid points → toast error.

---

## Session Log

### 2026-05-17 — Session 1
- Ingested PDF as `metrics.py` (supply + pricing + affordability + demand signals)
- Wired `interpret_market()` into `/market` route
- Created initial `CLAUDE.md`

### 2026-05-17 — Session 2
- Full UI rebuild: Bootstrap 5 → Tailwind CSS + Precision Analytical design system
- Layout: top navbar → sidebar with mobile hamburger overlay
- `metrics.py` significantly expanded: investor metrics, composite signal detection,
  all reference constants
- New routes: `/investor`, `/reference`, `/heatmap`, `/api/heatmap-data`
- All templates rebuilt (11 total)
- Committed to `feature/precision-analytical-redesign`, merged to main
- Heatmap committed directly to main

### 2026-05-17 — Session 3
**Trigger:** "rebuild the entire app w/ modern UI, employ data analytics best practices,
need more data than last year to account for seasonality"

**User choices:**
- Full visual overhaul (not just incremental updates)
- Data sources: max RentCast history (24 mo) + FRED + Census ACS
- Analytics: YoY everywhere, seasonality-adjusted trendlines, leading/lagging dashboard,
  multi-ZIP trend comparison

**What changed:**
- `housing_api.py` — historyRange default 12 → 24
- `cache.py` — new file-based TTL cache
- `fred_api.py` — new FRED API client (7 series, optional)
- `census_api.py` — new Census ACS client (optional)
- `metrics.py` — added `build_yoy_series`, `compute_moving_average`, `SIGNAL_CHAIN`,
  `assess_signal_chain`
- `app.py` — new `_enrich_chart` helper adds YoY + MA to all history dicts;
  new `/signals` route; `/compare` rebuilt for multi-ZIP; all routes pass new data
- `base.html` — added Signals to nav (both desktop + mobile)
- `index.html` — new feature grid landing with analytics principles callout
- `market.html` — complete overhaul: KPI strip with YoY delta chips, 5 tabs
  (Price Trends, Supply & Demand, Rental, Macro Context, Insights), 8 charts
- `compare.html` — multi-ZIP (2–3) overlay with metric switcher + YoY grouped bars
- `signals.html` — new: supply chain visual, 3-column indicator cards, FRED macro table
- `.gitignore` — added `.cache/` and `alerts.json`

**Key decisions made in session 3:**
1. **YoY as primary frame, not MoM** — the PDF is explicit that DOM and inventory
   are highly seasonal; MoM is nearly meaningless without adjustment
2. **12-month trailing MA as seasonal smoother** — labeled "12-mo MA" not
   "seasonally adjusted" to be methodologically honest; appropriate for 24-month series
3. **FRED + Census as optional** — free keys, both optional with graceful UI fallback;
   same pattern as existing Twilio integration
4. **File-based cache** — avoids hitting API limits on every page load; no Redis
   or database needed at this scale
5. **Multi-ZIP time-series overlay** — replaced point-in-time bar chart comparison
   with 24-month line overlay; relative momentum is more analytically useful than
   absolute snapshots
6. **Signal chain page as separate route** — organizing metrics by their position in
   the supply chain (leading/coincident/lagging) is a core PDF concept; deserves its
   own dedicated view

**Open / next steps:**
- No test suite
- Alert evaluation still fires only on page load (no background scheduler)
- DOM metric on heatmap is sparse — consider sourcing from `/markets` endpoint
- Census ACS uses 2023 vintage — income/population data lags by ~18 months
- YoY bars on signals/macro charts not yet implemented (deferred for context reasons)
- `property.html` — Census demographics block added to route but template not yet updated
  (needs `demographics` + `census_configured` blocks added)
