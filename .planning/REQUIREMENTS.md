# Housing Analyzer — Requirements

Status: brownfield baseline (2026-05-17). Validated items are already shipped and in active use; Active items are the current build queue.

---

## Validated (already shipped)

### Market Analysis
- ✓ **MKT-01**: User can view 24-month market analysis for any US ZIP at `/market`
- ✓ **MKT-02**: User sees KPI strip with YoY delta chips on market page
- ✓ **MKT-03**: User can switch between Price Trends, Supply & Demand, Rental, Macro Context, and Insights tabs
- ✓ **MKT-04**: User sees 12-mo trailing MA overlays on time-series charts
- ✓ **MKT-05**: User sees YoY % change bar charts alongside raw time series

### Signal Chain
- ✓ **SIG-01**: User can view leading/lagging signal chain at `/signals`
- ✓ **SIG-02**: User sees 7-node chain (NAHB → Permits → Starts → Inventory → DOM → SNLR → Prices) with badges
- ✓ **SIG-03**: User sees FRED national macro indicators when configured

### Multi-ZIP Compare
- ✓ **CMP-01**: User can compare 2–3 ZIPs at `/compare`
- ✓ **CMP-02**: User can switch the comparison metric and see YoY grouped bars

### Property Lookup
- ✓ **PROP-01**: User can look up a property by address at `/property`
- ✓ **PROP-02**: User sees RentCast AVM estimate + investor quick-screen
- ✓ **PROP-03**: User sees Census ACS demographics when configured (route — template incomplete; see ACTIVE-03)

### Spatial Views
- ✓ **HEAT-01**: User can view IDW interpolated heatmap at `/heatmap`
- ✓ **HEAT-02**: User can switch heatmap metric (price, price/sqft, DOM)
- ✓ **HEAT-03**: User can adjust resolution, IDW power, and opacity sliders
- ✓ **HEAT-04**: User can toggle listing markers and auto-load-on-pan
- ✓ **GEO-01**: User can do radius geofence property search at `/geofence`

### Investor Tooling
- ✓ **INV-01**: User can compute NOI, cap rate, GRM, DSCR at `/investor`
- ✓ **REF-01**: User can read the full metrics glossary at `/reference`

### Alerts
- ✓ **ALT-01**: User can create and manage SMS alerts at `/alerts`
- ✓ **ALT-02**: Alerts are evaluated on `/market` page load and sent via Twilio when configured

### Data Layer
- ✓ **DATA-01**: RentCast v1 API wrapper with file-based TTL caching
- ✓ **DATA-02**: FRED API client with 7 series, 24hr cache, graceful fallback if unconfigured
- ✓ **DATA-03**: Census ACS client with 7-day cache, graceful fallback if unconfigured
- ✓ **DATA-04**: Domain knowledge encoded in `metrics.py` (supply, affordability, investor, signal chain, composite signals)

---

## Active (in scope)

### Heatmap Polish
- [ ] **HEAT-05**: Heatmap color scale must use p5/p95 percentile clamping instead of min/max so outliers don't crush the gradient
- [ ] **HEAT-06**: Heatmap hex grid bbox must come from the convex hull of loaded data (with buffer), not the stale fetch viewport, so the field is anchored to where data actually is
- [ ] **HEAT-07**: When the current map viewport no longer overlaps the data hull, user sees a small "view changed — reload?" badge so the empty area isn't mistaken for a broken renderer

### Property Page Completion
- [ ] **PROP-04**: Property page template renders the Census demographics block the route already provides

### OpenAddresses Property Lookup
- [ ] **OA-01**: User can look up a single property by address via OpenAddresses (https://github.com/openaddresses/openaddresses) data — independent of (or supplementing) RentCast lookup
- [ ] **OA-02**: OpenAddresses data is loaded efficiently (likely on-demand by region rather than bulk-loaded — exact approach TBD during plan phase)
- [ ] **OA-03**: Property lookup result distinguishes OpenAddresses-sourced fields from RentCast-sourced fields so the user knows the provenance

---

## Deferred / v2

- [ ] **HEAT-08**: Sparse-DOM heatmap metric — source from `/markets` aggregate endpoint instead of per-property records
- [ ] **ALT-03**: Background scheduler for alerts (no need until volume increases)

---

## Out of Scope

- **Multi-user auth / SaaS hosting** — single-user tool by design
- **SQL or Redis** — file-based persistence is sufficient at this scale
- **Build tooling / npm pipeline** — Tailwind/Chart.js/Leaflet via CDN, zero-build constraint
- **Non-US markets** — RentCast and FRED are US-only data sources
- **Full X-13ARIMA seasonal adjustment** — 12-mo trailing MA is honest enough for 24-mo series
- **Email or push notification channels** — SMS-only via Twilio

---

## Traceability

| REQ-ID | Phase |
|--------|-------|
| HEAT-05, HEAT-06, HEAT-07 | Phase 1 — Heatmap Polish |
| PROP-04 | Phase 2 — Property Page Completion |
| OA-01, OA-02, OA-03 | Phase 3 — OpenAddresses Property Lookup |
