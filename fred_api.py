"""
FRED (Federal Reserve Economic Data) API client.
Free key at https://fred.stlouisfed.org/docs/api/api_key.html
Set FRED_API_KEY in .env.

Behaves like the rest of the cache layer: soft-miss in production, the
refresh cron is responsible for populating data. In DEV_MODE the dev_cache
fixture short-circuits everything as before.
"""
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

import cache
import dev_cache

load_dotenv()

_BASE = "https://api.stlouisfed.org/fred/series/observations"
_KEY  = os.getenv("FRED_API_KEY", "")
_MONTHS_BACK = 36

# series_id → (friendly_name, unit)
SERIES = {
    "MORTGAGE30US": ("30-Yr Fixed Mortgage Rate",    "%"),
    "DGS10":        ("10-Year Treasury Yield",        "%"),
    "CPIAUCSL":     ("CPI (Seasonally Adj.)",         "Index"),
    "UNRATE":       ("Unemployment Rate",             "%"),
    "BPPRIV":       ("Building Permits (Private)",    "k units"),
    "PERMIT":       ("Building Permits (Thous.)",     "k units"),
    "HOUST":        ("Housing Starts (Thous.)",       "k units"),
}


@dev_cache.fixture("fred.series")
@cache.cached("fred.series")
def _fetch_series(series_id):
    """One FRED series. Strict soft-miss; cron calls .refresh() to populate."""
    if not _KEY:
        return None
    start = (datetime.now() - timedelta(days=30 * _MONTHS_BACK)).strftime("%Y-%m-%d")
    try:
        r = requests.get(_BASE, params={
            "series_id":         series_id,
            "api_key":           _KEY,
            "file_type":         "json",
            "observation_start": start,
            "sort_order":        "asc",
        }, timeout=10)
        r.raise_for_status()
        return [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in r.json().get("observations", [])
            if obs["value"] != "."
        ]
    except Exception:
        return None


def get_macro_context():
    """
    Returns a dict keyed by series_id with latest value + history.
    Any series that isn't cached yet is absent from the dict — the cron
    fills these in on its next run.
    """
    if not _KEY and not dev_cache.is_active():
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


def refresh_all():
    """Cron entrypoint: live-fetch every series and write to cache."""
    for sid in SERIES:
        _fetch_series.refresh(sid)


def is_configured():
    return bool(_KEY) or dev_cache.is_active()
