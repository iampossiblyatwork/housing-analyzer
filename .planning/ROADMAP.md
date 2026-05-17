# Housing Analyzer — Roadmap

**Mode:** brownfield. Existing app is in production use; phases here cover the Active requirements only.

---

## Active Phases

### Phase 1: Heatmap Polish
**Goal:** Fix the IDW heatmap so the color gradient reflects real value variation and the rendered field stays anchored to actual data — not a stale viewport.
**Mode:** mvp
**Requirements:** HEAT-05, HEAT-06, HEAT-07
**Success Criteria:**
1. Loading the same dataset that previously rendered "all green" now shows a clear emerald → amber → red gradient across the bulk of the distribution
2. After panning/zooming, the hex grid stays anchored to the data's convex hull (with small buffer) rather than the old fetch viewport
3. When the current map viewport stops overlapping the data hull, a small in-map badge appears indicating "view changed — reload?"
4. Existing manual reload button + auto-load checkbox behavior is unchanged
5. UI hint: yes

### Phase 2: Property Page Demographics
**Goal:** Surface the Census ACS demographics block on `/property` (route already passes data; template is incomplete).
**Mode:** mvp
**Requirements:** PROP-04
**Success Criteria:**
1. When Census API is configured, the property page renders median income, population, housing units, vacant units, vacancy rate
2. When Census API is not configured, the property page shows the standard "configure CENSUS_API_KEY" graceful fallback message — never a runtime error
3. UI hint: yes

### Phase 3: OpenAddresses Property Lookup
**Goal:** Add a property-identification capability backed by OpenAddresses data, supplementing the existing RentCast lookup.
**Mode:** mvp
**Requirements:** OA-01, OA-02, OA-03
**Success Criteria:**
1. User can enter an address and see a result row sourced from OpenAddresses (lat/lng, normalized address components, source region/file)
2. When the same address is also found in RentCast, the page shows both sources side-by-side with explicit provenance labels
3. Data ingestion strategy avoids pre-loading the full OpenAddresses corpus (region/state-scoped fetch or API proxy — exact approach selected during plan phase)
4. UI hint: yes

---

## Phase Order Notes

Phase 1 ships first — it's a focused fix to an existing user-visible problem.
Phase 2 is small and can ship anytime; it just completes work already routed.
Phase 3 is larger (new data integration + new UI surface) and benefits from `/gsd:plan-phase` research.

---

## Completed Phases

(None yet under GSD — pre-GSD work captured as Validated requirements in REQUIREMENTS.md.)
