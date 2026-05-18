"""
Populate dev_cache.sqlite from live APIs for a given list of ZIPs.

Usage:
    DEV_MODE=1 python record_fixtures.py 78244 90210 11215

Each ZIP triggers: rentcast market_stats, rentcast geofence (centered on ZIP
centroid via market_stats lat/lng), census demographics, and one full FRED
macro pull (which is ZIP-independent, so it only burns calls on the first ZIP).

Skips namespaces that are already recorded for the same params.
Reports a per-ZIP summary so you can see what was hit live vs. served from
the existing fixture.
"""
import os
import sys

if os.getenv("DEV_MODE", "").lower() not in ("1", "true", "yes", "on"):
    print("Refusing to run: set DEV_MODE=1 first so writes land in dev_cache.sqlite.")
    sys.exit(2)

import dev_cache
import housing_api
import fred_api
import census_api


def _record_zip(zip_code):
    print(f"\n=== {zip_code} ===")
    before = dev_cache.stats()

    try:
        stats = housing_api.get_market_stats(zip_code)
        print(f"  market_stats: ok")
    except Exception as e:
        print(f"  market_stats: FAILED ({e})")
        stats = None

    if stats:
        lat = stats.get("latitude") or stats.get("lat")
        lng = stats.get("longitude") or stats.get("lng") or stats.get("lon")
        if lat and lng:
            try:
                housing_api.search_by_geofence(lat, lng, 3)
                print(f"  geofence 3mi @ ({lat:.3f}, {lng:.3f}): ok")
            except Exception as e:
                print(f"  geofence: FAILED ({e})")
        else:
            print(f"  geofence: skipped (no lat/lng in market_stats)")

    try:
        census_api.get_zip_demographics(zip_code)
        print(f"  census: ok")
    except Exception as e:
        print(f"  census: FAILED ({e})")

    after = dev_cache.stats()
    delta = {ns: after.get(ns, 0) - before.get(ns, 0) for ns in set(after) | set(before)}
    delta = {ns: n for ns, n in delta.items() if n}
    if delta:
        print(f"  +rows: {delta}")


def _record_macro():
    print("\n=== FRED macro (ZIP-independent) ===")
    before = dev_cache.stats()
    fred_api.get_macro_context()
    after = dev_cache.stats()
    delta = after.get("fred", 0) - before.get("fred", 0)
    print(f"  +rows: fred={delta}")


def main():
    zips = sys.argv[1:]
    if not zips:
        print("Usage: DEV_MODE=1 python record_fixtures.py <zip> [<zip> ...]")
        sys.exit(1)
    _record_macro()
    for z in zips:
        _record_zip(z)
    print("\nFinal counts:")
    for ns, n in dev_cache.stats().items():
        print(f"  {ns:30s} {n:6d}")


if __name__ == "__main__":
    main()
