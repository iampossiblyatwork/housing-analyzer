from flask import Flask, render_template, request, redirect, url_for, jsonify
import rentcast
import alerts as alert_mgr

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
        data = rentcast.get_market_stats(zip_code, history_range=history_range)
    except Exception as e:
        return render_template("error.html", message=str(e))

    # Build sorted history lists for charts
    def build_history(section_data, price_key, dom_key="averageDaysOnMarket"):
        history = section_data.get("history", {})
        months = sorted(history.keys())
        return {
            "labels": months,
            "prices": [history[m].get(price_key) for m in months],
            "dom":    [history[m].get(dom_key) for m in months],
            "listings": [history[m].get("totalListings") for m in months],
        }

    sale_chart = build_history(data.get("saleData", {}), "medianPrice")
    rent_chart = build_history(data.get("rentalData", {}), "medianRent")

    triggered = alert_mgr.check_and_notify(data, zip_code)

    return render_template(
        "market.html",
        zip_code=zip_code,
        data=data,
        sale_chart=sale_chart,
        rent_chart=rent_chart,
        history_range=history_range,
        triggered=triggered,
    )


# ── Property Lookup ───────────────────────────────────────────────────────────

@app.route("/property")
def property_lookup():
    address = request.args.get("address", "").strip()
    if not address:
        return render_template("property.html", address=None, data=None)

    try:
        props   = rentcast.get_properties(address=address, limit=1)
        rent_est = None
        sale_est = None
        try:
            rent_est = rentcast.get_rent_estimate(address=address)
        except Exception:
            pass
        try:
            sale_est = rentcast.get_sale_estimate(address=address)
        except Exception:
            pass
    except Exception as e:
        return render_template("error.html", message=str(e))

    prop = props[0] if props else None
    return render_template(
        "property.html",
        address=address,
        prop=prop,
        rent_est=rent_est,
        sale_est=sale_est,
    )


# ── Market Comparison ─────────────────────────────────────────────────────────

@app.route("/compare")
def compare():
    zip1 = request.args.get("zip1", "").strip()
    zip2 = request.args.get("zip2", "").strip()
    if not zip1 or not zip2:
        return render_template("compare.html", zip1=None, zip2=None, d1=None, d2=None)

    try:
        d1 = rentcast.get_market_stats(zip1)
        d2 = rentcast.get_market_stats(zip2)
    except Exception as e:
        return render_template("error.html", message=str(e))

    return render_template("compare.html", zip1=zip1, zip2=zip2, d1=d1, d2=d2)


# ── Geofence Search ───────────────────────────────────────────────────────────

@app.route("/geofence")
def geofence():
    lat    = request.args.get("lat", "").strip()
    lng    = request.args.get("lng", "").strip()
    radius = request.args.get("radius", "5").strip()
    prop_type = request.args.get("propertyType", "")

    if not lat or not lng:
        return render_template("geofence.html", results=None, params={})

    try:
        kwargs = {}
        if prop_type:
            kwargs["propertyType"] = prop_type
        results = rentcast.search_by_geofence(float(lat), float(lng), float(radius), **kwargs)
    except Exception as e:
        return render_template("error.html", message=str(e))

    params = {"lat": lat, "lng": lng, "radius": radius, "propertyType": prop_type}
    return render_template("geofence.html", results=results, params=params)


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
