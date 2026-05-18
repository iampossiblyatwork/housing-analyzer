"""
Dev-mode fixture store backed by SQLite.

When DEV_MODE=1, decorated API wrappers consult this DB before hitting the
live API. Hits return immediately; misses fall through to the live call and
are written back. The resulting `dev_cache.sqlite` is committed to the repo
so developers can work offline against a captured snapshot of real responses.

This is NOT a TTL cache. It is a fixture store. Entries do not expire.
The runtime TTL cache (cache.py) still applies on top in production.
"""
import functools
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes", "on")
_DB_PATH = os.path.join(os.path.dirname(__file__), "dev_cache.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fixtures (
    key         TEXT PRIMARY KEY,
    namespace   TEXT NOT NULL,
    params_json TEXT NOT NULL,
    data_json   TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fixtures_namespace ON fixtures(namespace);
"""


def _key(namespace, params):
    blob = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(f"{namespace}|{blob}".encode()).hexdigest()


@contextmanager
def _conn():
    c = sqlite3.connect(_DB_PATH)
    try:
        c.executescript(_SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


def get(namespace, params):
    if not DEV_MODE:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT data_json FROM fixtures WHERE key = ?",
            (_key(namespace, params),),
        ).fetchone()
    return json.loads(row[0]) if row else None


def put(namespace, params, data):
    if not DEV_MODE:
        return
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO fixtures(key, namespace, params_json, data_json, recorded_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                _key(namespace, params),
                namespace,
                json.dumps(params, sort_keys=True, default=str),
                json.dumps(data, default=str),
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )


def fixture(namespace):
    """Decorator: in DEV_MODE, check fixture DB first; on miss, call fn and persist."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not DEV_MODE:
                return fn(*args, **kwargs)
            key_params = {"args": list(args), "kwargs": kwargs}
            hit = get(namespace, key_params)
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            put(namespace, key_params, result)
            return result
        return wrapper
    return decorator


def is_active():
    return DEV_MODE


def stats():
    """Return per-namespace row counts for inspection."""
    if not os.path.exists(_DB_PATH):
        return {}
    with _conn() as c:
        rows = c.execute(
            "SELECT namespace, COUNT(*) FROM fixtures GROUP BY namespace ORDER BY namespace"
        ).fetchall()
    return dict(rows)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] == "stats":
        s = stats()
        if not s:
            print("Fixture DB empty or missing.")
        else:
            total = sum(s.values())
            for ns, n in s.items():
                print(f"  {ns:30s} {n:6d}")
            print(f"  {'TOTAL':30s} {total:6d}")
    else:
        print(f"Unknown command: {sys.argv[1]}")
        sys.exit(1)
