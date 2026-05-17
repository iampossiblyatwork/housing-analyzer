"""
Real estate market metric definitions, thresholds, and interpretations.
Source: "Measuring Real Estate Trend and Health: A Professional Reference"
"""

# ── Supply ────────────────────────────────────────────────────────────────────

def interpret_months_of_supply(mos):
    if mos is None:
        return None
    if mos < 3:
        return "Strong seller's market"
    if mos < 5:
        return "Tightening / mild seller's market"
    if mos <= 7:
        return "Balanced market"
    if mos <= 10:
        return "Buyer's market"
    return "Distressed / oversupplied"


def interpret_absorption_rate(rate_pct):
    """Absorption Rate — homes sold ÷ active inventory, as a percentage."""
    if rate_pct is None:
        return None
    if rate_pct > 20:
        return "Strong seller's market"
    if rate_pct < 15:
        return "Buyer's market"
    return "Neutral market"


def interpret_days_on_market(dom):
    """DOM — always compare YoY; highly seasonal."""
    if dom is None:
        return None
    if dom < 30:
        return "Hot market"
    if dom <= 40:
        return "Moderating"
    return "Cooling market"


def interpret_sale_to_list_ratio(ratio_pct):
    """
    Sale-to-List Price Ratio (SNLR).
    Best single read on negotiating power.
    A drop from ~100% to ~98% is a meaningful shift even though it looks small.
    """
    if ratio_pct is None:
        return None
    if ratio_pct > 100:
        return "Sellers receiving over asking — strong seller's market"
    if ratio_pct >= 99:
        return "Seller's market"
    if ratio_pct >= 97:
        return "Slight seller advantage"
    if ratio_pct >= 95:
        return "Balanced / slight buyer advantage"
    return "Buyer's market — meaningful discounts occurring"


def interpret_price_cuts_share(pct):
    """Price cuts/reduction share — percent of active listings with at least one price reduction."""
    if pct is None:
        return None
    if pct < 10:
        return "Very few price cuts — seller's market"
    if pct < 20:
        return "Normal — some seller flexibility"
    if pct < 35:
        return "Elevated — demand softening"
    return "High price cut rate — buyer's market signal"


# ── Pricing ───────────────────────────────────────────────────────────────────

PRICE_INDICES = {
    "case_shiller": {
        "name": "S&P CoreLogic Case-Shiller Home Price Index",
        "methodology": "Repeat-sales, value-weighted",
        "coverage": "20 major MSAs + national composite",
        "lag": "~2 months (7–8 weeks)",
        "strengths": "Institutional standard; tracks same-home appreciation",
        "limitations": "Excludes new construction and condos in some markets; high lag",
    },
    "fhfa_hpi": {
        "name": "FHFA House Price Index",
        "methodology": "Repeat-sales, GSE-linked loans only",
        "coverage": "All 50 states, 400+ cities; history to mid-1970s",
        "lag": "~2 months",
        "strengths": "Longest history; broad geography",
        "limitations": "Limited to conforming (non-jumbo) loans — weak at the high end",
    },
    "zhvi": {
        "name": "Zillow Home Value Index (ZHVI)",
        "methodology": "Hedonic/AVM-based (not repeat-sales)",
        "coverage": "Neighborhood, ZIP, city, county, metro, state, national",
        "lag": "~1 month",
        "strengths": "Granular, timely, includes new construction; full housing stock",
        "limitations": "More volatile; rises faster in hot markets, falls further in cool ones",
    },
}

PRICING_NOTES = (
    "The most common error in market analysis is comparing across price measures that use different "
    "methodologies. Always know which index produced the number you're quoting. "
    "Repeat-sales indices and AVM-based indices diverge at turning points — blending both "
    "is increasingly standard institutional practice."
)

MEDIAN_PRICE_NOTE = (
    "Median sale price movement can reflect either appreciation OR compositional shift "
    "(more high-end homes selling). Always pair median price with price-per-square-foot "
    "and a repeat-sales index to disentangle."
)


# ── Affordability & Financial Stress ──────────────────────────────────────────

def interpret_nar_affordability_index(value):
    """NAR Housing Affordability Index — whether a median-income family can qualify for a median-priced home."""
    if value is None:
        return None
    if value >= 100:
        return f"Affordable (index {value:.0f} — median-income family qualifies)"
    return f"Stressed (index {value:.0f} — median-income family falls short)"


def interpret_price_to_income(ratio):
    """Price-to-Income Ratio — median home price ÷ median household income. U.S. historical norm: 3–4×."""
    if ratio is None:
        return None
    if ratio <= 4:
        return "Within historical norm (3–4×)"
    if ratio <= 5:
        return "Elevated — watch closely"
    return "Affordability stress — elevated correction risk (>5×)"


def interpret_price_to_rent(ratio):
    """
    Price-to-Rent Ratio — median home price ÷ median annual rent.
    <15 = buying cheaper; >20 = renting more economical.
    """
    if ratio is None:
        return None
    if ratio < 15:
        return "Buying is cheaper than renting"
    if ratio <= 20:
        return "Borderline — context-dependent"
    return "Renting may be more economical than buying"


def interpret_vacancy_rate(pct):
    """Natural vacancy rate is typically 5–7%; significantly higher signals oversupply."""
    if pct is None:
        return None
    if pct <= 5:
        return "Tight rental market"
    if pct <= 7:
        return "Normal / natural vacancy range"
    if pct <= 10:
        return "Elevated — watch rent growth"
    return "High vacancy — oversupply or economic weakness"


MORTGAGE_RATE_SENSITIVITY = (
    "Each 1% increase in mortgage rates reduces purchasing power by approximately 10–11%. "
    "Track the 30-year fixed conforming rate alongside the 10-year Treasury — the spread "
    "between them widens in periods of credit stress."
)

RATE_LOCK_IN_NOTE = (
    "The rate-lock-in effect tracks the spread between the average outstanding mortgage rate (~3.8%) "
    "and the prevailing market rate. A wide spread suppresses existing-home turnover regardless of "
    "price trends — critical context for interpreting low inventory in 2024–2026."
)

FORECLOSURE_NOTE = (
    "Foreclosures spike after economic distress, not during it — they are lagging stress indicators. "
    "Useful for confirming a downturn, not predicting one. Standard sources: MBA National Delinquency "
    "Survey and ATTOM foreclosure data."
)


# ── Investor / Income-Property Metrics ───────────────────────────────────────

def compute_noi(monthly_rent, monthly_expenses):
    """NOI — annual rent minus annual operating expenses (excludes financing and capex)."""
    return (monthly_rent - monthly_expenses) * 12


def compute_grm(price, annual_rent):
    """Gross Rent Multiplier — price ÷ gross annual rent. Fast first-pass screening metric."""
    if not price or not annual_rent or annual_rent == 0:
        return None
    return round(price / annual_rent, 1)


def interpret_grm(grm):
    if grm is None:
        return None
    if grm < 10:
        return "Strong cash flow potential"
    if grm < 15:
        return "Reasonable income property"
    if grm < 20:
        return "Moderate — verify with cap rate"
    return "Low yield — price high relative to rent"


def compute_cap_rate(noi, price):
    """Cap Rate — NOI ÷ purchase price, expressed as a percentage."""
    if not noi or not price or price == 0:
        return None
    return round((noi / price) * 100, 2)


def interpret_cap_rate(rate_pct):
    """Compare to local market cap rates and risk-free rate. Cap rate compression = appreciation-dependent return."""
    if rate_pct is None:
        return None
    if rate_pct >= 8:
        return "Strong yield — verify NOI assumptions"
    if rate_pct >= 5:
        return "Market-range yield"
    if rate_pct >= 3:
        return "Compressed — appreciation-dependent return"
    return "Severe cap rate compression — high price risk"


def compute_dscr(noi, annual_debt_service):
    """DSCR — NOI ÷ annual debt service. Lenders typically require ≥1.25x."""
    if not noi or not annual_debt_service or annual_debt_service == 0:
        return None
    return round(noi / annual_debt_service, 2)


def interpret_dscr(ratio):
    if ratio is None:
        return None
    if ratio >= 1.25:
        return "Lender-qualifying — stable cash flow"
    if ratio >= 1.0:
        return "Break-even — thin margin, watch expenses"
    return "Cash flow negative — income below debt service"


# ── Demand signals ────────────────────────────────────────────────────────────

DEMAND_SIGNAL_LEAD_TIMES = {
    "nahb_hmi":                  "Earliest — leads permits and starts by 1–3 months",
    "mortgage_purchase_apps":    "Leads closed sales by 30–90 days",
    "pending_home_sales":        "Leads closed sales by 30–60 days (contracts signed, not yet closed)",
    "showing_traffic":           "Real-time proxy — before contracts are signed",
    "existing_new_home_sales":   "Lagging confirmation",
    "days_on_market":            "Faster than closed-sales data; directly reflects buyer urgency",
    "foreclosure_rates":         "Lagging — confirms downturn after the fact",
}

HOUSING_SUPPLY_CHAIN = (
    "NAHB builder confidence → Permits → Starts → Completions → Inventory / Rents. "
    "Housing turns before the broader economy at both peaks and troughs. "
    "Compare starts to permits — divergence signals a trend change ahead; trust permits for direction."
)

INVENTORY_INTERPRETATION = (
    "Active inventory count is seasonal — always compare YoY, not month-over-month. "
    "Rising inventory + flat/rising sales = healthy expansion. "
    "Rising inventory + falling sales = classic early signal of a market turn. "
    "New listings vs. pending sales reveal WHY inventory is moving."
)

WITHDRAWN_RATE_NOTE = (
    "An underused indicator. Listings that disappear without selling signal seller capitulation on price "
    "expectations without transactions occurring — a hidden supply overhang. "
    "~60% of listings were withdrawn by November 2025, capturing shadow supply that headline inventory misses."
)


# ── Composite signal detection ────────────────────────────────────────────────

def detect_composite_signals(sale_chart):
    """
    Detect analytical patterns from the PDF's practical framework using sale history.
    sale_chart = {"labels": [...], "prices": [...], "dom": [...], "listings": [...]}

    Compares last 3 months vs prior 3 months to identify trends.
    Returns list of {"pattern": str, "detail": str, "color": str}
    """
    prices   = [p for p in sale_chart.get("prices", []) if p is not None]
    doms     = [d for d in sale_chart.get("dom", []) if d is not None]
    listings = [l for l in sale_chart.get("listings", []) if l is not None]

    if len(prices) < 6 or len(doms) < 6 or len(listings) < 6:
        return []

    def avg(lst, start, end):
        slc = lst[start:end]
        return sum(slc) / len(slc)

    rp = avg(prices, -3, None);   pp = avg(prices, -6, -3)
    rd = avg(doms, -3, None);     pd = avg(doms, -6, -3)
    rl = avg(listings, -3, None); pl = avg(listings, -6, -3)

    dom_rising      = rd > pd * 1.05
    dom_falling     = rd < pd * 0.95
    listings_rising = rl > pl * 1.05
    listings_falling= rl < pl * 0.95
    price_rising    = rp > pp * 1.02
    price_falling   = rp < pp * 0.98

    signals = []

    if dom_rising and listings_rising and price_falling:
        signals.append({
            "pattern": "Cooling signal",
            "detail": "Rising DOM + rising inventory + falling prices — all major cooling indicators aligning.",
            "color": "danger",
        })
    elif dom_rising and listings_rising:
        signals.append({
            "pattern": "Softening",
            "detail": "DOM and inventory both rising — early signs of demand weakening. Watch SNLR.",
            "color": "warning",
        })

    if listings_rising and dom_falling and price_rising:
        signals.append({
            "pattern": "Healthy expansion",
            "detail": "Rising inventory + falling DOM + rising prices — supply expanding into strong demand.",
            "color": "success",
        })
    elif listings_rising and not dom_rising and price_rising:
        signals.append({
            "pattern": "Supply expanding",
            "detail": "Inventory rising without DOM deterioration — healthy market activity.",
            "color": "info",
        })

    if dom_falling and listings_falling and price_rising:
        signals.append({
            "pattern": "Hot market",
            "detail": "Falling DOM + tightening inventory + rising prices — strong seller conditions.",
            "color": "warning",
        })

    if not signals:
        signals.append({
            "pattern": "Mixed signals",
            "detail": "No clear composite pattern detected. Single metrics may still be informative.",
            "color": "secondary",
        })

    return signals


# ── Reference data ────────────────────────────────────────────────────────────

COMPOSITE_INDICES = [
    {
        "name": "U.S. News Housing Market Index",
        "description": "Measures and compares health of U.S. housing markets using housing demand, supply, and financial health.",
    },
    {
        "name": "HUD National Housing Market Indicators",
        "description": "Monthly composite from HUD's Office of Policy Development and Research.",
    },
    {
        "name": "NAHB/Wells Fargo Housing Market Index (HMI)",
        "description": "Builder sentiment composite — the earliest signal in the housing data chain.",
    },
    {
        "name": "Conference Board Leading Economic Index (housing components)",
        "description": "Relates housing signals to broader macro turning points.",
    },
]

ECONOMIC_DRIVERS = [
    ("Employment growth and wage growth", "The prerequisite for housing demand"),
    ("Net migration / population change", "Census ACS plus state-level IRS migration data"),
    ("Household formation rate", "Captures latent demand independent of population"),
    ("Median household income (and its growth)", "Denominator of affordability ratios"),
    ("Labor force participation and unemployment", "Broad measure of economic health"),
    ("Local industry diversification", "Single-industry metros face concentrated risk"),
]

COMMON_PITFALLS = [
    "Relying on national headlines for local decisions",
    "Quoting median price without checking compositional mix",
    "Treating any single month of data as a trend (always use rolling windows)",
    "Ignoring seasonality — normalize to YoY or seasonally adjusted series",
    "Conflating affordability (a level) with momentum (a rate of change)",
    "Missing the divergence between repeat-sales and AVM indices at turning points",
]

SCOPE_NOTES = {
    "Neighborhood / ZIP level": (
        "Case-Shiller and FHFA aren't granular enough. Rely on MLS-derived data "
        "(DOM, SNLR, price cuts, absorption), Zillow ZHVI at ZIP, and price per square foot. "
        "Sample sizes get noisy quickly — use 6- or 12-month rolling windows."
    ),
    "Metro / MSA level": (
        "Case-Shiller (20-city), ZHVI, FHFA MSA-level HPI, NAR pending sales by region, "
        "MBA application data by metro where available."
    ),
    "Cross-market comparison": (
        "Normalize. Price-to-income, price-to-rent, MOS, YoY price growth, and net migration "
        "are the cleanest cross-market metrics. Absolute price levels are nearly useless for comparison."
    ),
}

DATA_SOURCES = [
    ("S&P CoreLogic Case-Shiller", "Repeat-sales HPI, national + 20 MSAs", "~2 months"),
    ("FHFA HPI", "Repeat-sales HPI, national + 400+ cities", "~2 months"),
    ("Zillow Research", "ZHVI, ZORI rents, inventory, DOM down to ZIP", "~1 month"),
    ("Redfin Data Center", "Weekly metro-level sales, pending, price cuts, SNLR", "~1 week"),
    ("Realtor.com", "Active listings, new listings, DOM, price reductions", "Weekly"),
    ("NAR", "Existing home sales, pending sales, affordability index", "~1 month"),
    ("Census/HUD", "New home sales, starts, permits, completions", "~1 month"),
    ("MBA", "Purchase and refi applications", "Weekly"),
    ("NAHB", "Builder confidence (HMI)", "Monthly"),
    ("FRED (St. Louis Fed)", "Aggregator for most public housing series", "Varies"),
    ("ATTOM", "Foreclosure data", "Monthly"),
    ("HUD USER", "National Housing Market Indicators composite", "Monthly"),
]

ANALYTICAL_PATTERNS = [
    {
        "pattern": "Rising inventory + falling sales + rising DOM + falling SNLR",
        "signal": "Clean cooling signal — all four together is hard to argue with.",
        "color": "danger",
    },
    {
        "pattern": "Rising sales + rising inventory",
        "signal": "Healthy expansion, not a turn. Supply expanding into strong demand.",
        "color": "success",
    },
    {
        "pattern": "Permits falling while starts hold up",
        "signal": "Builders working through pipeline; weakness comes later.",
        "color": "warning",
    },
    {
        "pattern": "Repeat-sales index diverging from median price",
        "signal": "Compositional shift — usually the high end pulling away from the rest.",
        "color": "info",
    },
    {
        "pattern": "Withdrawn-listing share rising while inventory looks flat",
        "signal": "Hidden supply overhang — shadow inventory that headline numbers miss.",
        "color": "warning",
    },
    {
        "pattern": "Price-to-rent rising faster than price-to-income",
        "signal": "Investor-led market, more correction-prone.",
        "color": "danger",
    },
]


# ── Convenience: interpret a market stats dict from the RentCast API ──────────

def interpret_market(data):
    """
    Given a market stats dict from housing_api.get_market_stats(), return a dict
    of human-readable interpretations with badge colors for each available metric.
    """
    sale   = data.get("saleData", {})
    rental = data.get("rentalData", {})
    results = {}

    mos = sale.get("monthsOfSupply")
    if mos is not None:
        results["months_of_supply"] = {
            "label": "Months of Supply",
            "value": f"{mos:.1f} mo",
            "interpretation": interpret_months_of_supply(mos),
            "badge": "warning" if mos < 3 else "warning" if mos < 5 else "success" if mos <= 7 else "info" if mos <= 10 else "danger",
        }

    dom = sale.get("averageDaysOnMarket")
    if dom is not None:
        results["days_on_market"] = {
            "label": "Avg Days on Market",
            "value": f"{dom:.0f} days",
            "interpretation": interpret_days_on_market(dom),
            "badge": "warning" if dom < 30 else "success" if dom <= 40 else "info",
        }

    median_price = sale.get("medianPrice")
    median_rent  = rental.get("medianRent")

    if median_price and median_rent and median_rent > 0:
        annual_rent = median_rent * 12
        ptr = round(median_price / annual_rent, 1)
        grm = compute_grm(median_price, annual_rent)

        results["price_to_rent"] = {
            "label": "Price-to-Rent Ratio",
            "value": f"{ptr}×",
            "interpretation": interpret_price_to_rent(ptr),
            "badge": "success" if ptr < 15 else "warning" if ptr <= 20 else "info",
        }

        if grm is not None:
            results["gross_rent_multiplier"] = {
                "label": "Gross Rent Multiplier",
                "value": f"{grm}×",
                "interpretation": interpret_grm(grm),
                "badge": "success" if grm < 10 else "warning" if grm < 15 else "info" if grm < 20 else "danger",
            }

    return results
