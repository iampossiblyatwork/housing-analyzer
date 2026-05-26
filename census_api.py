"""
Census ACS 5-year estimates for ZIP code tabulation areas.
Free key at https://api.census.gov/data/key_signup.html
Set CENSUS_API_KEY in .env.

Soft-miss in production. The refresh cron calls .refresh() per tracked ZIP.
"""
import os
import requests
from dotenv import load_dotenv

import cache
import dev_cache

load_dotenv()

_BASE = "https://api.census.gov/data/2023/acs/acs5"
_KEY  = os.getenv("CENSUS_API_KEY", "")

_VARS = {
    "B19013_001E": "median_income",
    "B01003_001E": "population",
    "B25001_001E": "housing_units",
    "B25002_003E": "vacant_units",
}


@dev_cache.fixture("census.demographics")
@cache.cached("census.demographics", zip_arg="zip_code")
def get_zip_demographics(zip_code):
    if not _KEY:
        return None
    try:
        r = requests.get(_BASE, params={
            "get": ",".join(_VARS.keys()),
            "for": f"zip code tabulation area:{zip_code}",
            "key": _KEY,
        }, timeout=10)
        r.raise_for_status()
        rows = r.json()
        if len(rows) < 2:
            return None
        headers, vals = rows[0], rows[1]
        data = {}
        for col, val in zip(headers, vals):
            if col in _VARS:
                try:
                    v = int(val)
                    data[_VARS[col]] = v if v >= 0 else None
                except (TypeError, ValueError):
                    data[_VARS[col]] = None
        hu = data.get("housing_units")
        vu = data.get("vacant_units")
        if hu and vu is not None and hu > 0:
            data["vacancy_rate"] = round(vu / hu * 100, 1)
        return data
    except Exception:
        return None


def is_configured():
    return bool(_KEY) or dev_cache.is_active()
