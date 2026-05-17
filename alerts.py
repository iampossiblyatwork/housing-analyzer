import json
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ALERTS_FILE = os.path.join(os.path.dirname(__file__), "alerts.json")


# ---------- storage ----------

def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return []
    with open(ALERTS_FILE) as f:
        return json.load(f)


def save_alerts(alerts):
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)


def add_alert(alert_data):
    alerts = load_alerts()
    alert_data["id"] = str(uuid.uuid4())[:8]
    alert_data["created"] = datetime.now().isoformat()
    alert_data["last_triggered"] = None
    alerts.append(alert_data)
    save_alerts(alerts)
    return alert_data


def delete_alert(alert_id):
    alerts = [a for a in load_alerts() if a["id"] != alert_id]
    save_alerts(alerts)


# ---------- evaluation ----------

OPERATORS = {
    "lt": lambda a, b: a < b,
    "gt": lambda a, b: a > b,
    "lte": lambda a, b: a <= b,
    "gte": lambda a, b: a >= b,
}

FIELD_MAP = {
    "median_rent":        ("rentalData", "medianRent"),
    "average_rent":       ("rentalData", "averageRent"),
    "median_price":       ("saleData",   "medianPrice"),
    "average_price":      ("saleData",   "averagePrice"),
    "days_on_market":     ("saleData",   "averageDaysOnMarket"),
    "rental_dom":         ("rentalData", "averageDaysOnMarket"),
    "total_listings":     ("saleData",   "totalListings"),
    "new_listings":       ("saleData",   "newListings"),
}


def evaluate_alert(alert, market_data):
    section, field = FIELD_MAP.get(alert["field"], (None, None))
    if not section:
        return False, None
    value = market_data.get(section, {}).get(field)
    if value is None:
        return False, None
    threshold = float(alert["threshold"])
    op = OPERATORS.get(alert["operator"], lambda a, b: False)
    triggered = op(value, threshold)
    return triggered, value


def check_and_notify(market_data, zip_code):
    import housing_api as rc
    alerts = load_alerts()
    triggered = []

    for alert in alerts:
        if alert.get("zip_code") != zip_code:
            continue
        fired, current_value = evaluate_alert(alert, market_data)
        if fired:
            msg = (
                f"Housing Analyzer Alert [{zip_code}]: {alert['label']}\n"
                f"{alert['field']} is {current_value:,.0f} "
                f"({alert['operator']} {float(alert['threshold']):,.0f})"
            )
            send_sms(msg)
            alert["last_triggered"] = datetime.now().isoformat()
            triggered.append(alert)

    if triggered:
        save_alerts(alerts)

    return triggered


# ---------- SMS ----------

def send_sms(body):
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_num = os.getenv("TWILIO_FROM_NUMBER", "")
    to_num = os.getenv("ALERT_TO_NUMBER", "")

    if not all([sid, token, from_num, to_num]) or sid.startswith("your_"):
        print(f"[SMS skipped — Twilio not configured] {body}")
        return False

    from twilio.rest import Client
    client = Client(sid, token)
    client.messages.create(body=body, from_=from_num, to=to_num)
    return True
