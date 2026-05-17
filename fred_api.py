"""
FRED (Federal Reserve Economic Data) API client.
Free key at https://fred.stlouisfed.org/docs/api/api_key.html
Set FRED_API_KEY in .env. Gracefully returns None if unconfigured.
"""
import os, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import cache

load_dotenv()

_BASE = "https://api.stlouisfed.org/fred/series/observations"
_KEY  = os.getenv("FRED_API_KEY", "")

# series_id → (friendly_name, unit)
SERIES = {
    "MORTGAGE30US": ("30-Yr Fixed Mortgage Rate",    "%"),
    "DGS10":        ("10-Year Treasury Yield",        "%"),
    "CPIAUCSL":     ("CPI (Seasonally Adj.)",         "Index"),
    "UNRATE":       ("Unemployment Rate",             "%"),
    "NAHBMMI":      ("NAHB Builder Confidence",       "Index"),
    "PERMIT":       ("Building Permits (Thous.)",     "k units"),
    "HOUST":        ("Housing Starts (Thous.)",       "k units"),
}


def _fetch_series(series_id, months_back=36):
    if not _KEY:
        return None
    start = (datetime.now() - timedelta(days=30 * months_back)).strftime("%Y-%m-%d")
    cache_params = {"sid": series_id, "start": start}
    cached = cache.get("fred", cache_params, ttl=86400)
    if cached is not None:
        return cached
    try:
        r = requests.get(_BASE, params={
            "series_id":         series_id,
            "api_key":           _KEY,
            "file_type":         "json",
            "observation_start": start,
            "sort_order":        "asc",
        }, timeout=10)
        r.raise_for_status()
        data = [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in r.json().get("observations", [])
            if obs["value"] != "."
        ]
        cache.put("fred", cache_params, data)
        return data
    except Exception:
        return None


def get_macro_context():
    """
    Returns a dict keyed by series_id with latest value + history.
    Any series that fails or is unconfigured is absent from the dict.
    """
    if not _KEY:
        return {}
    result = {}
    for sid in SERIES:
        obs = _fetch_series(sid)
        if obs:
            result[sid] = {
                "name":    SERIES[sid][0],
                "unit":    SERIES[sid][1],
                "latest":  obs[-1],
                "history": obs,
            }
    return result


def is_configured():
    return bool(_KEY)
