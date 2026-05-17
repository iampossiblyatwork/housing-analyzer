from flask import Flask, render_template, request, redirect, url_for, jsonify
import housing_api
import alerts as alert_mgr
import metrics

app = Flask(__name__)


# ── Home ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Market Analysis ───────────────────────────────────────────────────────────

@app.route("/market")
def market():
    zip_code = request.args.get("zip", "").strip()
    history_range = int(request.args.get("history", 12))
    if not zip_code:
        return redirect(url_for("index"))

    try:
        data = housing_api.get_market_stats(zip_code, history_range=history_range)
    except Exception as e:
        return render_template("error.html", message=str(e))

    def build_history(section_data, price_key, dom_key="averageDaysOnMarket"):
        history = section_data.get("history", {})
        months = sorted(history.keys())
        return {
            "labels":   months,
            "prices":   [history[m].get(price_key) for m in months],
            "dom":      [history[m].get(dom_key) for m in months],
            "listings": [history[m].get("totalListings") for m in months],
        }

    sale_chart = build_history(data.get("saleData", {}), "medianPrice")
    rent_chart = build_history(data.get("rentalData", {}), "medianRent")

    triggered        = alert_mgr.check_and_notify(data, zip_code)
    interpretations  = metrics.interpret_market(data)
    signals          = metrics.detect_composite_signals(sale_chart)

    return render_template(
        "market.html",
        zip_code=zip_code,
        data=data,
        sale_chart=sale_chart,
        rent_chart=rent_chart,
        history_range=history_range,
        triggered=triggered,
        interpretations=interpretations,
        signals=signals,
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

    # Investor quick-screen using AVM estimates
    investor_metrics = None
    if sale_est and rent_est:
        price        = sale_est.get("price")
        monthly_rent = rent_est.get("rent")
        if price and monthly_rent and monthly_rent > 0:
            annual_rent = monthly_rent * 12
            grm         = metrics.compute_grm(price, annual_rent)
            ptr         = round(price / annual_rent, 1)
            investor_metrics = {
                "grm":            grm,
                "grm_interp":     metrics.interpret_grm(grm),
                "grm_badge":      "success" if grm and grm < 10 else "warning" if grm and grm < 15 else "info" if grm and grm < 20 else "danger",
                "price_to_rent":  ptr,
                "ptr_interp":     metrics.interpret_price_to_rent(ptr),
                "ptr_badge":      "success" if ptr < 15 else "warning" if ptr <= 20 else "info",
                "note":           metrics.MEDIAN_PRICE_NOTE,
            }

    return render_template(
        "property.html",
        address=address,
        prop=prop,
        rent_est=rent_est,
        sale_est=sale_est,
        investor_metrics=investor_metrics,
    )


# ── Market Comparison ─────────────────────────────────────────────────────────

@app.route("/compare")
def compare():
    zip1 = request.args.get("zip1", "").strip()
    zip2 = request.args.get("zip2", "").strip()
    if not zip1 or not zip2:
        return render_template("compare.html", zip1=None, zip2=None, d1=None, d2=None)

    try:
        d1 = housing_api.get_market_stats(zip1)
        d2 = housing_api.get_market_stats(zip2)
    except Exception as e:
        return render_template("error.html", message=str(e))

    return render_template("compare.html", zip1=zip1, zip2=zip2, d1=d1, d2=d2)


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
            price         = float(request.form.get("price", 0) or 0)
            monthly_rent  = float(request.form.get("monthly_rent", 0) or 0)
            monthly_exp   = float(request.form.get("monthly_expenses", 0) or 0)
            annual_debt   = float(request.form.get("annual_debt_service", 0) or 0)
            form = request.form

            if price > 0 and monthly_rent > 0:
                annual_rent = monthly_rent * 12
                noi         = metrics.compute_noi(monthly_rent, monthly_exp)
                grm         = metrics.compute_grm(price, annual_rent)
                cap         = metrics.compute_cap_rate(noi, price)
                dscr        = metrics.compute_dscr(noi, annual_debt) if annual_debt else None
                ptr         = round(price / annual_rent, 1)

                result = {
                    "price":         price,
                    "monthly_rent":  monthly_rent,
                    "monthly_exp":   monthly_exp,
                    "annual_debt":   annual_debt,
                    "annual_rent":   annual_rent,
                    "noi":           noi,
                    "grm":           grm,
                    "grm_interp":    metrics.interpret_grm(grm),
                    "grm_badge":     "success" if grm and grm < 10 else "warning" if grm and grm < 15 else "info" if grm and grm < 20 else "danger",
                    "cap_rate":      cap,
                    "cap_interp":    metrics.interpret_cap_rate(cap),
                    "cap_badge":     "success" if cap and cap >= 8 else "warning" if cap and cap >= 5 else "info" if cap and cap >= 3 else "danger",
                    "dscr":          dscr,
                    "dscr_interp":   metrics.interpret_dscr(dscr),
                    "dscr_badge":    "success" if dscr and dscr >= 1.25 else "warning" if dscr and dscr >= 1.0 else "danger" if dscr else "secondary",
                    "ptr":           ptr,
                    "ptr_interp":    metrics.interpret_price_to_rent(ptr),
                    "ptr_badge":     "success" if ptr < 15 else "warning" if ptr <= 20 else "info",
                }
        except (ValueError, ZeroDivisionError):
            pass

    return render_template("investor.html", result=result, form=form)


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
        if not lat_p or not lng_p:
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
