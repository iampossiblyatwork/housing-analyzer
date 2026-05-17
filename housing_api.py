import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.rentcast.io/v1"


def _headers():
    return {"X-Api-Key": os.getenv("RENTCAST_API_KEY")}


def get_properties(**params):
    r = requests.get(f"{BASE_URL}/properties", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


def get_rent_estimate(**params):
    r = requests.get(f"{BASE_URL}/avm/rent/long-term", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


def get_sale_estimate(**params):
    r = requests.get(f"{BASE_URL}/avm/value", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


def get_market_stats(zip_code, data_type="All", history_range=24):
    params = {"zipCode": zip_code, "dataType": data_type, "historyRange": history_range}
    r = requests.get(f"{BASE_URL}/markets", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


def search_by_geofence(lat, lng, radius_miles, **params):
    params.update({"latitude": lat, "longitude": lng, "radius": radius_miles, "limit": 500})
    r = requests.get(f"{BASE_URL}/properties", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()
