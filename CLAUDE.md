# Housing Analyzer — Claude Memory Log

Running record of design decisions, architectural choices, and conversation context.
Updated by Claude at the end of sessions where meaningful decisions were made.

---

## Project Overview

A Flask web app for analyzing housing markets using the RentCast API.
Surfaces sale and rental data by ZIP code, property lookup, market comparison,
geofence search, metric-driven heatmap, investor calculator, metrics reference,
and threshold-based SMS alerts via Twilio.

**Stack:** Python 3.12, Flask, RentCast API, Tailwind CSS (CDN), Chart.js, Leaflet, Twilio (SMS alerts)
**Entry point:** `app.py` (Flask)
**API wrapper:** `housing_api.py` — thin wrapper around RentCast v1 REST API
**Alert engine:** `alerts.py` — JSON-file-backed alert store with Twilio SMS delivery
**Metrics layer:** `metrics.py` — full structured encoding of the PDF reference document

**Routes:**
| Route | Purpose |
|-------|---------|
| `/` | Home / search hub |
| `/market` | Market analysis by ZIP — sale, rental, insights, by-type tabs |
| `/property` | Address lookup — AVM estimates + investor quick-screen |
| `/compare` | Side-by-side ZIP comparison with bar chart |
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

### RentCast as sole data source
All market data comes from `api.rentcast.io/v1`. The API key lives in `.env`
(gitignored). No fallback data source; if the API is down, the app surfaces an
error page. Intentional — no caching or mock layer added.

### Alerts stored as flat JSON (`alerts.json`)
No database. Alerts are a list of dicts serialized to `alerts.json` at the
project root. Chosen for simplicity — the alert volume is low and there's no
need for querying, indexing, or concurrency safety at this scale.
If the alert set grows meaningfully, SQLite would be the natural next step.

### Alert evaluation happens on page load, not on a schedule
`alerts.check_and_notify()` is called every time `/market` is loaded for a
given ZIP code. Alerts only fire when someone visits the page.
A background scheduler was not added — keeping it simple until there's real need.

### SMS-only alerting (Twilio)
Only SMS delivery is implemented. Twilio credentials are optional — if not
configured, the app logs to stdout and continues normally (`send_sms` returns
`False` gracefully).

### Chart.js rendered client-side from inline JSON
History data is serialized via `{{ sale_chart | tojson }}`. Chart.js draws line
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

**Implementation:** render the IDW grid at ~10% of canvas resolution → `drawImage`
scale up to full canvas → CSS `blur()` filter for smooth continuous field. This
gives the smooth mesh appearance cheaply without WebGL. Step size adapts to data
density so it stays fast (< 100ms) for typical RentCast result sets (~500 props).

### metrics.py encodes PDF as Python, not a database or vector store
The PDF *"Measuring Real Estate Trend and Health"* was ingested as a Python module.
Reasons: thresholds are stable reference data (not user content), Python functions
are testable and directly callable, no LangChain/embeddings needed, keeps stack flat.

---

## Module: `metrics.py` — Domain Knowledge Layer

**Source:** `real-estate-market-metrics.pdf` (committed to repo)

### Supply indicators
| Function | Description |
|----------|-------------|
| `interpret_months_of_supply(mos)` | <3 seller's, 3-5 tightening, 5-7 balanced, 7-10 buyer's, >10 distressed |
| `interpret_absorption_rate(rate_pct)` | >20% seller's, <15% buyer's |
| `interpret_days_on_market(dom)` | <30 hot, ≤40 moderating, >40 cooling |
| `interpret_sale_to_list_ratio(ratio_pct)` | >100% over-ask, ≥99% seller, 95-97% balanced, <95% buyer |
| `interpret_price_cuts_share(pct)` | <10% seller, 10-20% normal, 20-35% elevated, >35% buyer |

### Pricing indicators
| Symbol | Description |
|--------|-------------|
| `PRICE_INDICES` | Case-Shiller, FHFA HPI, ZHVI — methodology, coverage, lag, strengths, limitations |
| `PRICING_NOTES` | Cross-methodology comparison warning |
| `MEDIAN_PRICE_NOTE` | Compositional shift caveat |

### Affordability indicators
| Function | Description |
|----------|-------------|
| `interpret_nar_affordability_index(value)` | ≥100 = qualifies, <100 = stressed |
| `interpret_price_to_income(ratio)` | ≤4 norm, ≤5 elevated, >5 stress |
| `interpret_price_to_rent(ratio)` | <15 buy, 15-20 borderline, >20 rent |
| `interpret_vacancy_rate(pct)` | ≤5 tight, ≤7 normal, ≤10 elevated, >10 high |

### Investor / income-property metrics
| Function | Description |
|----------|-------------|
| `compute_noi(monthly_rent, monthly_expenses)` | Annual rent minus operating expenses |
| `compute_grm(price, annual_rent)` | Price ÷ annual gross rent |
| `interpret_grm(grm)` | <10 strong, <15 reasonable, <20 moderate, ≥20 low yield |
| `compute_cap_rate(noi, price)` | NOI ÷ price as % |
| `interpret_cap_rate(rate_pct)` | ≥8 strong, ≥5 market, ≥3 compressed, <3 severe |
| `compute_dscr(noi, annual_debt_service)` | NOI ÷ annual debt |
| `interpret_dscr(ratio)` | ≥1.25 lender-qualifying, ≥1.0 break-even, <1.0 negative |

### Demand signals and reference data
`DEMAND_SIGNAL_LEAD_TIMES`, `HOUSING_SUPPLY_CHAIN`, `INVENTORY_INTERPRETATION`,
`WITHDRAWN_RATE_NOTE`, `MORTGAGE_RATE_SENSITIVITY`, `RATE_LOCK_IN_NOTE`,
`FORECLOSURE_NOTE`, `COMPOSITE_INDICES`, `ECONOMIC_DRIVERS`, `COMMON_PITFALLS`,
`SCOPE_NOTES`, `DATA_SOURCES`, `ANALYTICAL_PATTERNS`

### Composite signal detection
`detect_composite_signals(sale_chart)` — compares last 3 months vs prior 3 months
of sale history (price, DOM, listings). Detects: cooling signal, softening, healthy
expansion, supply expanding, hot market. Requires ≥6 months of history in the chart
data; returns `[{pattern, detail, color}]`. Falls back to "Mixed signals" if no clear
pattern is detected.

### Convenience wrappers
`interpret_market(data)` — takes a RentCast market stats dict, returns a dict with
labeled interpretations and badge colors for MOS, DOM, price-to-rent, and GRM.
Badge colors: "success" (green), "warning" (amber), "danger" (red), "info" (blue),
"secondary" (gray) — used by Jinja2 badge macros in templates.

---

## Design System: Precision Analytical (Tailwind)

Adopted in session 2 from the Stitch design kit (`stitch_housing_market_insights.zip`).

**Color tokens (key subset):**
| Token | Hex | Use |
|-------|-----|-----|
| `primary` | `#0b1c30` | Headings, key text |
| `secondary` | `#3755c3` | Royal blue — CTAs, active nav, links |
| `on-tertiary-container` | `#005236` | Positive / green data |
| `error` | `#ba1a1a` | Negative / red data |
| `surface` | `#f8f9ff` | Page background |
| `outline-variant` | `#c6c6cd` | Card borders |
| `surface-container-low` | `#eff4ff` | Table headers, sidebar active |

**Typography:** Inter (Google Fonts). Custom Tailwind font-size tokens: `text-headline-lg`,
`text-headline-md`, `text-label-md`, `text-label-sm`, `text-data-tabular`.

**Icons:** Material Symbols Outlined (Google Fonts CDN). Use `filled` class to toggle fill.

**Card pattern:** `bg-white border border-outline-variant rounded-lg` with
`hover:shadow-card transition-shadow`.

**Badge macro** (defined inline in each template that needs it):
```jinja2
{% macro badge(color, text) %}...{% endmacro %}
```
Maps: success→emerald, warning→amber, danger→red, info→blue, secondary→gray.
Repeated in each template rather than base.html because Jinja2 macros don't
inherit across `{% extends %}` without explicit import.

---

## Heatmap Implementation Notes

**Route:** `/heatmap` (page) + `/api/heatmap-data` (JSON)

**Data flow:**
1. User clicks map → sets lat/lng inputs
2. User clicks "Load Heatmap" → `fetchAndRender()` hits `/api/heatmap-data`
3. Backend calls `housing_api.search_by_geofence()`, extracts `price`,
   `price_per_sqft` (computed), `dom` per property → returns JSON array
4. Client filters to selected metric, runs IDW on canvas, renders

**IDW rendering pipeline:**
```
allData (full) → heatData (metric-filtered) → pixel coords
→ low-res IDW grid (TW×TH canvas, ~10% of map size)
→ drawImage() scale up to full map size + CSS blur(N px)
→ optional dot overlay (property positions, same color scale)
```

**Scale factor** adapts dynamically: `scale = max(0.08, min(0.18, 800 / (W * N^0.3)))`
where N = number of data points. Keeps render time bounded regardless of density.

**Color scale:** emerald green (`#10b981`) → amber (`#f59e0b`) → red (`#ef4444`).
Represents low→high for price and price/sqft. For DOM, higher = slower market = red.
The scale is the same direction for all three — red always means "more" of the metric,
green always means "less". Users should read the legend min/max labels for orientation.

**Canvas overlay:** absolutely positioned over the Leaflet map div, `pointer-events:none`,
`z-index:400` (above tile layers, below Leaflet controls). Re-renders on `moveend` and
`zoomend` events (canvas coordinate space changes with map). Canvas is hidden during
panning is not explicitly implemented — re-render fires after the pan settles.

**Metrics available:**
- `price` — `lastSalePrice` from RentCast property records
- `price_per_sqft` — `lastSalePrice / squareFootage` (computed client-side)
- `dom` — `daysOnMarket` from property records (may be null for many properties)

**Known limitation:** `daysOnMarket` is often absent on individual property records
from RentCast's `/properties` endpoint — the metric is more reliably available in
market-level aggregates. If zero points have DOM data, the UI shows a toast error.

---

## Session Log

### 2026-05-17 — Session 1

- Confirmed repo is on `main` branch, 3 prior commits
- User added `real-estate-market-metrics.pdf`
- Ingested PDF as `metrics.py` (initial version: supply + pricing + affordability + demand signals)
- Wired `metrics.interpret_market()` into the `/market` route in `app.py`
- Created this `CLAUDE.md` file

### 2026-05-17 — Session 2 (branched from session 1 at the btw/design handoff)

**Trigger:** User provided Stitch design kit zip and said "rebuild the housing analyzer app".

**What changed:**
- Full visual rebuild: Bootstrap 5 → Tailwind CSS with Precision Analytical design system
- Layout: top navbar → sidebar navigation with mobile hamburger overlay
- `metrics.py` significantly expanded: added investor metrics (cap rate, GRM, NOI, DSCR,
  vacancy rate, price cuts interpretation), composite signal detection, and all reference
  data constants needed by the `/reference` page
- Two new routes: `/investor` (income-property calculator) and `/reference` (PDF glossary)
- New `/heatmap` route + `/api/heatmap-data` endpoint with IDW canvas interpolation
- All 9 templates rebuilt (base, index, market, property, compare, investor, reference,
  alerts, error, geofence) + 2 new templates (investor, heatmap)
- `market.html` Insights tab now live: renders `interpretations` dict, composite signals
  panel, and analytical context accordions
- `property.html` investor quick-screen: auto-computes GRM + price-to-rent from AVM estimates
- Committed to `feature/precision-analytical-redesign`, then merged to `main`
- Heatmap committed directly to `main` (commit `339be42`)

**Decisions made in session 2:**
1. **Tailwind over Bootstrap** — required by the Stitch kit's component model; CDN approach
   preserves zero-build constraint
2. **Sidebar layout** — matches the Stitch reference kit's intended UX for data-dense tools
3. **Badge macro repeated per template** — Jinja2 `extends` doesn't expose macros defined
   in child templates to parent; repeating the 10-line macro is cleaner than an `import`
4. **IDW over KDE for heatmap** — user asked for value field, not density. KDE (leaflet.heat)
   shows clustering; IDW shows metric values spatially interpolated
5. **Low-res render + blur** — avoids WebGL, keeps the implementation in ~50 lines of vanilla
   JS, renders in < 100ms for typical datasets
6. **`detect_composite_signals` uses 3-month trailing comparison** — requires ≥6 months of
   history. Shorter windows are too noisy; the PDF's framework is implicitly YoY but
   RentCast history goes back 24 months max, so 3-month windows are a pragmatic proxy

**Open / next steps:**
- `daysOnMarket` on individual property records is sparse; heatmap DOM metric may rarely
  have enough data to be useful — consider sourcing DOM from market-level data by ZIP
- No test suite exists
- Alert evaluation still fires only on page load (no background scheduler)
- The `/reference` page is static; could add links from each metric to the corresponding
  calculator or market page field
