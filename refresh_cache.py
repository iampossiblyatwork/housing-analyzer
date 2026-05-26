"""
Daily refresh cron. Render runs this script on the schedule defined in
render.yaml. It is the ONLY thing that should ever call the live RentCast,
FRED, and Census APIs in production — the web service is strict-soft-miss.

Behavior:
  1. Initialize the schema (idempotent).
  2. Seed the 'static' ZIP tier from RENTCAST_WARM_ZIPS env var.
  3. Refresh all FRED series (ZIP-independent).
  4. For each tracked ZIP (static + auto-tracked within window):
       - RentCast market_stats
       - Census demographics
     Failures are isolated to one ZIP — a bad ZIP doesn't kill the run.
  5. Print a summary.

Set RENTCAST_WARM_ZIPS="78244,90210,11215" in the env for a static floor.
"""
import os
import sys
import traceback

import db
import housing_api
import fred_api
import census_api


def _parse_zip_env(raw):
    if not raw:
        return []
    out = []
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if tok.isdigit() and len(tok) == 5:
            out.append(tok)
    return out


def main():
    if not db.is_configured():
        print("ERROR: DATABASE_URL is not set; nothing to refresh.", file=sys.stderr)
        sys.exit(2)

    db.init_db()
    static_zips = _parse_zip_env(os.getenv("RENTCAST_WARM_ZIPS", ""))
    db.seed_static_zips(static_zips)

    # ── FRED — 7 series, no ZIP dimension ───────────────────────────────────
    print("FRED:")
    try:
        fred_api.refresh_all()
        print("  ok (all configured series refreshed)")
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()

    # ── Per-ZIP refresh ─────────────────────────────────────────────────────
    rows = db.list_zips_to_refresh()
    print(f"\nTracked ZIPs to refresh: {len(rows)}")

    n_ok = n_fail = 0
    for zip_code, tier in rows:
        print(f"\n[{tier:6s}] {zip_code}")
        try:
            housing_api.get_market_stats.refresh(zip_code)
            print(f"  rentcast.market_stats: ok")
        except Exception as e:
            print(f"  rentcast.market_stats: FAILED ({e})")
            n_fail += 1
            continue

        try:
            census_api.get_zip_demographics.refresh(zip_code)
            print(f"  census.demographics:   ok")
        except Exception as e:
            # Census failure is non-fatal — leave the row, retry tomorrow.
            print(f"  census.demographics:   FAILED ({e})")

        db.mark_refreshed(zip_code)
        n_ok += 1

    print(f"\nDone. {n_ok} ZIP(s) refreshed, {n_fail} failed.")
    print("\nFinal counts:")
    for k, v in db.stats().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
