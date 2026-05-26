import os
import requests
from dotenv import load_dotenv
import cache
import dev_cache

load_dotenv()

BASE_URL = "https://api.rentcast.io/v1"


def _headers():
    return {"X-Api-Key": os.getenv("RENTCAST_API_KEY")}


# Per-address AVMs and geofence searches can't be pre-warmed by the cron
# (the cron doesn't know which addresses or coordinates users will query).
# `allow_live=True` means: if RENTCAST_ALLOW_LIVE=1 is set, a cache miss
# falls through to the live API. Otherwise these soft-miss like everything
# else — strict no-API-at-request-time mode.

@dev_cache.fixture("rentcast.properties")
@cache.cached("rentcast.properties", allow_live=True)
def get_properties(**params):
    r = requests.get(f"{BASE_URL}/properties", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


@dev_cache.fixture("rentcast.rent_estimate")
@cache.cached("rentcast.rent_estimate", allow_live=True)
def get_rent_estimate(**params):
    r = requests.get(f"{BASE_URL}/avm/rent/long-term", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


@dev_cache.fixture("rentcast.sale_estimate")
@cache.cached("rentcast.sale_estimate", allow_live=True)
def get_sale_estimate(**params):
    r = requests.get(f"{BASE_URL}/avm/value", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


# Market stats are the highest-volume RentCast call and the canonical thing
# the cron pre-warms. Strict soft-miss — no live fallback even with the env
# flag set. The cron's job is to keep this populated.
@dev_cache.fixture("rentcast.market_stats")
@cache.cached("rentcast.market_stats", zip_arg="zip_code")
def get_market_stats(zip_code, data_type="All", history_range=24):
    params = {"zipCode": zip_code, "dataType": data_type, "historyRange": history_range}
    r = requests.get(f"{BASE_URL}/markets", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


@dev_cache.fixture("rentcast.geofence")
@cache.cached("rentcast.geofence", allow_live=True)
def search_by_geofence(lat, lng, radius_miles, **params):
    params.update({"latitude": lat, "longitude": lng, "radius": radius_miles, "limit": 500})
    r = requests.get(f"{BASE_URL}/properties", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()
