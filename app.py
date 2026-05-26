import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import housing_api
import alerts as alert_mgr
import metrics
import fred_api
import census_api
import db

app = Flask(__name__)


# ── Postgres bootstrap ────────────────────────────────────────────────────────
# Initialize schema and seed the static ZIP floor at process start. Failures
# here intentionally crash the worker — without the DB the app is non-functional
# (everything reads through cache.py now). Render's healthcheck will catch it.
if db.is_configured():
    db.init_db()
    static_zips = [z.strip() for z in os.getenv("RENTCAST_WARM_ZIPS", "").replace(";", ",").split(",")
                   if z.strip().isdigit() and len(z.strip()) == 5]
    db.seed_static_zips(static_zips)


def _soft_miss(zip_code, what):
    """Standardized response when a cache lookup returns None for a tracked entity."""
    db.track_zip(zip_code)
    return render_template(
        "error.html",
        kind="pending",
        message=f"{what} for ZIP {zip_code} isn't in the cache yet. We've added it to the refresh queue.",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_history(section_data, price_key, dom_key="averageDaysOnMarket"):
    history = section_data.get("history", {})
    months  = sorted(history.keys())
    return {
        "labels":   months,
        "prices":   [history[m].get(price_key) for m in months],
        "dom":      [history[m].get(dom_key) for m in months],
        "listings": [history[m].get("totalListings") for m in months],
    }


def _enrich_chart(chart):
    """Attach YoY series and 12-month moving average to a history chart dict."""
    chart["prices_yoy"] = metrics.build_yoy_series(chart["labels"], chart["prices"])
    chart["dom_yoy"]    = metrics.build_yoy_series(chart["labels"], chart["dom"])
    chart["listings_yoy"] = metrics.build_yoy_series(chart["labels"], chart["listings"])
    chart["prices_ma"]  = metrics.compute_moving_average(chart["prices"])
    chart["dom_ma"]     = metrics.compute_moving_average(chart["dom"])
    chart["listings_ma"] = metrics.compute_moving_average(chart["listings"])
    return chart


# ── Home ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Market Analysis ───────────────────────────────────────────────────────────

@app.route("/market")
def market():
    zip_code = request.args.get("zip", "").strip()
    if not zip_code:
        return redirect(url_for("index"))

    db.track_zip(zip_code)
    try:
        data = housing_api.get_market_stats(zip_code, history_range=24)
    except Exception as e:
        return render_template("error.html", message=str(e))
    if data is None:
        return _soft_miss(zip_code, "Market data")

    sale_chart = _enrich_chart(_build_history(data.get("saleData", {}), "medianPrice"))
    rent_chart = _enrich_chart(_build_history(data.get("rentalData", {}), "medianRent"))

    triggered       = alert_mgr.check_and_notify(data, zip_code)
    interpretations = metrics.interpret_market(data)
    signals         = metrics.detect_composite_signals(sale_chart)
    demographics    = census_api.get_zip_demographics(zip_code)
    macro           = fred_api.get_macro_context()

    return render_template(
        "market.html",
        zip_code=zip_code,
        data=data,
        sale_chart=sale_chart,
        rent_chart=rent_chart,
        triggered=triggered,
        interpretations=interpretations,
        signals=signals,
        demographics=demographics,
        macro=macro,
        fred_configured=fred_api.is_configured(),
        census_configured=census_api.is_configured(),
    )


# ── Property Lookup ───────────────────────────────────────────────────────────

@app.route("/property")
def property_lookup():
    address = request.args.get("address", "").strip()
    if not address:
        return render_template("property.html", address=None, data=None)

    try:
        props    = housing_api.get_properties(address=address, limit=1)
        rent_est = None
        sale_est = None
        try:
            rent_est = housing_api.get_rent_estimate(address=address)
        except Exception:
            pass
        try:
            sale_est = housing_api.get_sale_estimate(address=address)
        except Exception:
            pass
    except Exception as e:
        return render_template("error.html", message=str(e))

    prop = props[0] if props else None

    investor_metrics = None
    if sale_est and rent_est:
        price        = sale_est.get("price")
        monthly_rent = rent_est.get("rent")
        if price and monthly_rent and monthly_rent > 0:
            annual_rent = monthly_rent * 12
            grm         = metrics.compute_grm(price, annual_rent)
            ptr         = round(price / annual_rent, 1)
            investor_metrics = {
                "grm":           grm,
                "grm_interp":    metrics.interpret_grm(grm),
                "grm_badge":     "success" if grm and grm < 10 else "warning" if grm and grm < 15 else "info" if grm and grm < 20 else "danger",
                "price_to_rent": ptr,
                "ptr_interp":    metrics.interpret_price_to_rent(ptr),
                "ptr_badge":     "success" if ptr < 15 else "warning" if ptr <= 20 else "info",
                "note":          metrics.MEDIAN_PRICE_NOTE,
            }

    zip_code     = prop.get("zipCode") if prop else None
    if zip_code:
        db.track_zip(zip_code)
    demographics = census_api.get_zip_demographics(zip_code) if zip_code else None

    return render_template(
        "property.html",
        address=address,
        prop=prop,
        rent_est=rent_est,
        sale_est=sale_est,
        investor_metrics=investor_metrics,
        demographics=demographics,
        census_configured=census_api.is_configured(),
    )


# ── Market Comparison — multi-ZIP time-series overlay ─────────────────────────

@app.route("/compare")
def compare():
    zips = [z.strip() for z in [
        request.args.get("zip1", ""),
        request.args.get("zip2", ""),
        request.args.get("zip3", ""),
    ] if z.strip()]

    if len(zips) < 2:
        return render_template("compare.html", zips=[], datasets=[], market_data=[])

    for z in zips:
        db.track_zip(z)
    try:
        raw = [housing_api.get_market_stats(z, history_range=24) for z in zips]
    except Exception as e:
        return render_template("error.html", message=str(e))
    missing = [z for z, d in zip(zips, raw) if d is None]
    if missing:
        return _soft_miss(missing[0], f"Market data (one of {len(missing)} ZIPs)")

    datasets = []
    for z, d in zip(zips, raw):
        chart = _enrich_chart(_build_history(d.get("saleData", {}), "medianPrice"))
        datasets.append({
            "zip":    z,
            "chart":  chart,
            "interp": metrics.interpret_market(d),
            "sale":   d.get("saleData", {}),
        })

    return render_template("compare.html", zips=zips, datasets=datasets, market_data=raw)


# ── Signal Chain Dashboard ────────────────────────────────────────────────────

@app.route("/signals")
def signals():
    zip_code = request.args.get("zip", "").strip()
    market_data = {}

    if zip_code:
        db.track_zip(zip_code)
        try:
            market_data = housing_api.get_market_stats(zip_code, history_range=24) or {}
        except Exception:
            market_data = {}

    macro       = fred_api.get_macro_context()
    chain       = metrics.assess_signal_chain(market_data, macro)

    return render_template(
        "signals.html",
        zip_code=zip_code,
        chain=chain,
        macro=macro,
        fred_configured=fred_api.is_configured(),
        signal_chain_desc=metrics.HOUSING_SUPPLY_CHAIN,
        demand_lead_times=metrics.DEMAND_SIGNAL_LEAD_TIMES,
    )


# ── Geofence Search ───────────────────────────────────────────────────────────

@app.route("/geofence")
def geofence():
    lat       = request.args.get("lat", "").strip()
    lng       = request.args.get("lng", "").strip()
    radius    = request.args.get("radius", "5").strip()
    prop_type = request.args.get("propertyType", "")

    if not lat or not lng:
        return render_template("geofence.html", results=None, params={})

    try:
        kwargs = {}
        if prop_type:
            kwargs["propertyType"] = prop_type
        results = housing_api.search_by_geofence(float(lat), float(lng), float(radius), **kwargs)
    except Exception as e:
        return render_template("error.html", message=str(e))

    params = {"lat": lat, "lng": lng, "radius": radius, "propertyType": prop_type}
    return render_template("geofence.html", results=results, params=params)


# ── Investor Calculator ───────────────────────────────────────────────────────

@app.route("/investor", methods=["GET", "POST"])
def investor():
    result = None
    form   = {}

    if request.method == "POST":
        try:
            price        = float(request.form.get("price", 0) or 0)
            monthly_rent = float(request.form.get("monthly_rent", 0) or 0)
            monthly_exp  = float(request.form.get("monthly_expenses", 0) or 0)
            annual_debt  = float(request.form.get("annual_debt_service", 0) or 0)
            form = request.form

            if price > 0 and monthly_rent > 0:
                annual_rent = monthly_rent * 12
                noi         = metrics.compute_noi(monthly_rent, monthly_exp)
                grm         = metrics.compute_grm(price, annual_rent)
                cap         = metrics.compute_cap_rate(noi, price)
                dscr        = metrics.compute_dscr(noi, annual_debt) if annual_debt else None
                ptr         = round(price / annual_rent, 1)

                result = {
                    "price":        price,
                    "monthly_rent": monthly_rent,
                    "monthly_exp":  monthly_exp,
                    "annual_debt":  annual_debt,
                    "annual_rent":  annual_rent,
                    "noi":          noi,
                    "grm":          grm,
                    "grm_interp":   metrics.interpret_grm(grm),
                    "grm_badge":    "success" if grm and grm < 10 else "warning" if grm and grm < 15 else "info" if grm and grm < 20 else "danger",
                    "cap_rate":     cap,
                    "cap_interp":   metrics.interpret_cap_rate(cap),
                    "cap_badge":    "success" if cap and cap >= 8 else "warning" if cap and cap >= 5 else "info" if cap and cap >= 3 else "danger",
                    "dscr":         dscr,
                    "dscr_interp":  metrics.interpret_dscr(dscr),
                    "dscr_badge":   "success" if dscr and dscr >= 1.25 else "warning" if dscr and dscr >= 1.0 else "danger" if dscr else "secondary",
                    "ptr":          ptr,
                    "ptr_interp":   metrics.interpret_price_to_rent(ptr),
                    "ptr_badge":    "success" if ptr < 15 else "warning" if ptr <= 20 else "info",
                }
        except (ValueError, ZeroDivisionError):
            pass

    macro = fred_api.get_macro_context()
    return render_template("investor.html", result=result, form=form, macro=macro)


# ── Metrics Reference ─────────────────────────────────────────────────────────

@app.route("/reference")
def reference():
    return render_template(
        "reference.html",
        price_indices=metrics.PRICE_INDICES,
        demand_lead_times=metrics.DEMAND_SIGNAL_LEAD_TIMES,
        composite_indices=metrics.COMPOSITE_INDICES,
        economic_drivers=metrics.ECONOMIC_DRIVERS,
        common_pitfalls=metrics.COMMON_PITFALLS,
        scope_notes=metrics.SCOPE_NOTES,
        data_sources=metrics.DATA_SOURCES,
        analytical_patterns=metrics.ANALYTICAL_PATTERNS,
        signal_chain=metrics.SIGNAL_CHAIN,
    )


# ── Market Heatmap ───────────────────────────────────────────────────────────

@app.route("/heatmap")
def heatmap():
    return render_template("heatmap.html")


@app.route("/api/heatmap-data")
def heatmap_data():
    lat       = request.args.get("lat", type=float)
    lng       = request.args.get("lng", type=float)
    radius    = request.args.get("radius", 5, type=float)
    prop_type = request.args.get("propertyType", "")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    try:
        kwargs = {}
        if prop_type:
            kwargs["propertyType"] = prop_type
        results = housing_api.search_by_geofence(lat, lng, radius, **kwargs)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    features = []
    for p in results:
        lat_p = p.get("latitude")
        lng_p = p.get("longitude")
        # Drop null and out-of-range coordinates — a single bogus point would
        # otherwise stretch the heatmap's convex hull across the continent and
        # visibly wreck the IDW grid's position and scale. NaN comparisons are
        # always False, so the range checks catch NaN too.
        if (lat_p is None or lng_p is None
                or not (-90 <= lat_p <= 90)
                or not (-180 <= lng_p <= 180)):
            continue
        price = p.get("lastSalePrice")
        sqft  = p.get("squareFootage")
        dom   = p.get("daysOnMarket")
        features.append({
            "lat":            lat_p,
            "lng":            lng_p,
            "price":          price,
            "price_per_sqft": round(price / sqft, 2) if price and sqft and sqft > 0 else None,
            "dom":            dom,
            "address":        p.get("formattedAddress", ""),
            "propertyType":   p.get("propertyType", ""),
            "bedrooms":       p.get("bedrooms"),
            "sqft":           sqft,
        })

    return jsonify(features)


# ── Alerts ────────────────────────────────────────────────────────────────────

@app.route("/alerts", methods=["GET", "POST"])
def alerts():
    if request.method == "POST":
        alert_mgr.add_alert({
            "label":     request.form["label"],
            "zip_code":  request.form["zip_code"],
            "field":     request.form["field"],
            "operator":  request.form["operator"],
            "threshold": request.form["threshold"],
        })
        return redirect(url_for("alerts"))

    return render_template("alerts.html", alerts=alert_mgr.load_alerts())


@app.route("/alerts/<alert_id>/delete", methods=["POST"])
def delete_alert(alert_id):
    alert_mgr.delete_alert(alert_id)
    return redirect(url_for("alerts"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
