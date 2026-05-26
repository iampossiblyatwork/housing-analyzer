"""
Postgres-backed durable cache + tracked-ZIP store.

Replaces the file-based .cache/ directory. Two tables:

- api_cache        — generic (namespace, params) → JSON payload. Same role as
                     the old cache.py but queryable by ZIP for the refresh
                     cron, and not bound to a single container's disk.
- tracked_zips     — ZIPs we keep warm. Rows arrive two ways: a `static` tier
                     seeded from the RENTCAST_WARM_ZIPS env var on startup,
                     and an `auto` tier inserted whenever a user query hits
                     a route that takes a ZIP.

No TTL is enforced here — the refresh cron is responsible for keeping rows
fresh. The cache.py decorator layered on top reads but does not expire.
"""
import json
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool


_DATABASE_URL = os.getenv("DATABASE_URL", "")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key   TEXT PRIMARY KEY,
    namespace   TEXT NOT NULL,
    zip         TEXT,
    payload     JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_cache_namespace ON api_cache(namespace);
CREATE INDEX IF NOT EXISTS idx_api_cache_zip       ON api_cache(zip);

CREATE TABLE IF NOT EXISTS tracked_zips (
    zip             TEXT PRIMARY KEY,
    tier            TEXT NOT NULL DEFAULT 'auto',  -- 'static' | 'auto'
    last_user_seen  TIMESTAMPTZ DEFAULT NOW(),
    last_refreshed  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tracked_zips_seen ON tracked_zips(last_user_seen DESC);
"""

# Small pool. Gunicorn runs 2 workers × 4 threads → 8 concurrent connections
# possible; minconn=1/maxconn=10 leaves headroom without surprising Render's
# basic plan (97 connections cap).
_pool = None


def _ensure_pool():
    global _pool
    if _pool is None:
        if not _DATABASE_URL:
            return None
        _pool = ThreadedConnectionPool(1, 10, _DATABASE_URL)
    return _pool


def is_configured():
    return bool(_DATABASE_URL)


@contextmanager
def _conn():
    """
    Yields a Postgres connection, or None if DATABASE_URL isn't set. Callers
    must check for None — used so local dev (no Postgres) doesn't crash;
    every read returns None / every write is a no-op in that mode.
    """
    pool = _ensure_pool()
    if pool is None:
        yield None
        return
    c = pool.getconn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        pool.putconn(c)


def init_db():
    """Run CREATE TABLE IF NOT EXISTS. Safe to call repeatedly."""
    with _conn() as c:
        if c is None:
            return
        with c.cursor() as cur:
            cur.execute(_SCHEMA)


def seed_static_zips(zips):
    """
    Insert the hand-picked 'always warm' ZIP list. Idempotent — re-running
    with a different list adds new ZIPs but does not demote existing static
    entries to auto (we don't want a typo in the env var to lose history).
    """
    if not zips:
        return
    with _conn() as c:
        if c is None:
            return
        with c.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO tracked_zips(zip, tier)
                VALUES (%s, 'static')
                ON CONFLICT (zip) DO UPDATE
                    SET tier = 'static'
                    WHERE tracked_zips.tier = 'auto'
                """,
                [(z,) for z in zips],
            )


# ── ZIP tracking ─────────────────────────────────────────────────────────────

def track_zip(zip_code):
    """
    Record that a user just queried this ZIP. Insert as 'auto' tier; if it
    already exists, bump last_user_seen so the cron knows it's active.
    """
    if not zip_code:
        return
    with _conn() as c:
        if c is None:
            return
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tracked_zips(zip, tier, last_user_seen)
                VALUES (%s, 'auto', NOW())
                ON CONFLICT (zip) DO UPDATE SET last_user_seen = NOW()
                """,
                (zip_code,),
            )


def list_zips_to_refresh(auto_window_days=30):
    """
    What the cron iterates over: every static ZIP, plus every auto ZIP seen
    in the last `auto_window_days`. Auto entries older than the window are
    skipped to keep the cron's API budget bounded.
    """
    with _conn() as c:
        if c is None:
            return []
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT zip, tier
                FROM tracked_zips
                WHERE tier = 'static'
                   OR last_user_seen > NOW() - (%s || ' days')::interval
                ORDER BY tier DESC, zip ASC
                """,
                (auto_window_days,),
            )
            return cur.fetchall()


def mark_refreshed(zip_code):
    with _conn() as c:
        if c is None:
            return
        with c.cursor() as cur:
            cur.execute(
                "UPDATE tracked_zips SET last_refreshed = NOW() WHERE zip = %s",
                (zip_code,),
            )


# ── Generic API cache ────────────────────────────────────────────────────────

def get_cached(cache_key):
    with _conn() as c:
        if c is None:
            return None
        with c.cursor() as cur:
            cur.execute("SELECT payload FROM api_cache WHERE cache_key = %s", (cache_key,))
            row = cur.fetchone()
            return row[0] if row else None


def put_cached(cache_key, namespace, payload, zip_code=None):
    if payload is None:
        return
    with _conn() as c:
        if c is None:
            return
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_cache(cache_key, namespace, zip, payload, fetched_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (cache_key) DO UPDATE
                    SET payload    = EXCLUDED.payload,
                        fetched_at = NOW(),
                        zip        = EXCLUDED.zip
                """,
                (cache_key, namespace, zip_code, psycopg2.extras.Json(payload)),
            )


def stats():
    """Per-namespace row count + total tracked ZIPs. For diagnostics."""
    with _conn() as c:
        if c is None:
            return {"cache_rows_by_namespace": {}, "tracked_zips_by_tier": {}}
        with c.cursor() as cur:
            cur.execute(
                "SELECT namespace, COUNT(*) FROM api_cache GROUP BY namespace ORDER BY namespace"
            )
            by_ns = dict(cur.fetchall())
            cur.execute("SELECT tier, COUNT(*) FROM tracked_zips GROUP BY tier")
            by_tier = dict(cur.fetchall())
    return {"cache_rows_by_namespace": by_ns, "tracked_zips_by_tier": by_tier}
