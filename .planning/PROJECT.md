# Housing Analyzer

## What This Is

A Flask web app for analyzing housing markets. Surfaces 24-month sale and rental history with YoY comparisons, leading/lagging signal chain, multi-ZIP comparison, geofence search, metric-driven heatmap, investor calculator, metrics reference, and SMS alerts. Built for a single power user (the owner) doing analytical work on US residential markets.

## Core Value

Give an analyst-minded user a fast, methodologically honest read on a housing market — YoY framing, lead/lag signal chain, and value-vs-density spatial views — without forcing them through enterprise tooling.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ 24-month market analysis page (`/market`) — KPI strip, 5 tabs (Price Trends, Supply & Demand, Rental, Macro Context, Insights), YoY chips, 12-mo MA overlays
- ✓ Leading/lagging signal chain dashboard (`/signals`) — NAHB → Permits → Starts → Inventory → DOM → SNLR → Prices
- ✓ Multi-ZIP comparison (`/compare`) — 2–3 ZIPs, time-series overlay with metric switcher and YoY grouped bars
- ✓ Property lookup (`/property`) — RentCast AVM estimates + investor quick-screen + Census demographics
- ✓ Metric-driven IDW heatmap (`/heatmap`) — price, price/sqft, DOM
- ✓ Geofence radius property search (`/geofence`) — Leaflet heatmap
- ✓ Investor calculator (`/investor`) — NOI, cap rate, GRM, DSCR
- ✓ Metrics reference (`/reference`) — PDF knowledge rendered
- ✓ SMS alerts via Twilio (`/alerts`) — JSON-backed, page-load evaluation
- ✓ RentCast API wrapper (`housing_api.py`) — primary data source
- ✓ FRED API client (`fred_api.py`) — optional, graceful fallback
- ✓ Census ACS client (`census_api.py`) — optional, graceful fallback
- ✓ File-based TTL cache (`cache.py`) — `.cache/` dir
- ✓ Domain-knowledge module (`metrics.py`) — PDF encoded as Python
- ✓ Precision Analytical design system — Tailwind CDN, sidebar layout, Inter typography

### Active

<!-- Current scope. Building toward these. -->

- [ ] Fix heatmap rendering — outlier-crushed color scale + stale bbox + view-changed-but-not-reloaded UX
- [ ] OpenAddresses single-property lookup feature — use openaddresses.io data for property identification/enrichment alongside RentCast
- [ ] Property page Census demographics block — route already passes data, template needs update
- [ ] DOM heatmap metric — currently sparse from per-property records; consider sourcing from `/markets` aggregates

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Multi-user auth — single-user tool, not a SaaS product
- Background scheduler for alerts — page-load evaluation is sufficient at current volume
- SQL database / Redis — JSON files + file-based cache are enough at this scale
- Build tooling / npm — Tailwind/Chart.js/Leaflet all via CDN; zero-build constraint
- Server-rendered charts — Chart.js runs client-side from inline JSON
- Full seasonal adjustment (X-13ARIMA/STL) — 12-month trailing MA is sufficient for 24-month series
- Email/push notifications — SMS-only via Twilio
- Non-US markets — RentCast and FRED are US-only data sources

## Context

- **Stack:** Python 3.12, Flask, RentCast v1 REST API, FRED API, Census ACS API, Tailwind CSS (CDN), Chart.js, Leaflet, Twilio
- **Data philosophy:** RentCast is the primary data source for local market data; FRED + Census are optional supplements (each gated by its own env var with graceful UI fallback if unconfigured)
- **Methodological frame:** YoY comparisons are primary (DOM and inventory are highly seasonal); MoM is nearly meaningless without adjustment. 12-mo trailing MA labeled "12-mo MA" — never "seasonally adjusted" — to be methodologically honest.
- **Heatmap approach:** IDW interpolation, not KDE — shows VALUE of a metric across space, not density.
- **Architecture style:** Flat (no packages), file-based persistence, stateless server, client-side charts. Simplicity over abstractions.
- **Owner:** James (single user). Detailed architectural decisions and session history live in `CLAUDE.md`.

## Constraints

- **Tech stack:** Python 3.12 + Flask only — no packaging, no submodules, no npm/build tooling
- **Persistence:** File-based — `.cache/`, `alerts.json`. No SQL/Redis until volume demands it.
- **Frontend:** Tailwind via CDN, no compile step. Material Symbols + Inter via Google Fonts.
- **Third-party APIs:** RentCast (paid, low-rate-limit), FRED (free, optional), Census (free, optional), Twilio (paid, SMS only)
- **Local-only deployment:** Runs as `python app.py` on the owner's machine. No production hosting concerns.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tailwind CSS over Bootstrap | Stitch design kit used Tailwind's utility model; matching Precision Analytical required it | ✓ Good |
| Sidebar layout over top navbar | Intended layout for data-dense analytical tool per Stitch kit | ✓ Good |
| IDW heatmap over Leaflet.heat (KDE) | User wants value-across-space, not density | ✓ Good |
| `metrics.py` as Python over vector store | PDF is stable reference data, not user content; testable functions | ✓ Good |
| YoY as primary analytical frame | PDF explicit: DOM/inventory highly seasonal, MoM misleading | ✓ Good |
| 12-mo trailing MA as smoother | Full seasonal adjustment requires more history + complexity than warranted | ✓ Good |
| 24-month default history | RentCast max; needed for full YoY from month 13 | ✓ Good |
| FRED + Census optional with graceful fallback | Same pattern as existing Twilio integration; lowers setup friction | ✓ Good |
| File-based TTL cache | Avoids API hammer; no Redis/DB needed at this scale | ✓ Good |
| Alerts evaluated on page load | No scheduler — keep simple until real need | — Pending |
| Flat file structure (no packages) | App is small enough; abstraction not worth it | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-17 after brownfield initialization*
