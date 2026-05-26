"""
Postgres-backed cache wrapper. Same decorator interface as before, but the
semantics changed:

  - Default behavior (production): SOFT MISS. A cache miss returns None
    instead of falling through to the live API. The refresh cron is the
    only thing that populates the cache.

  - DEV_MODE=1: legacy behavior. Misses fall through to the live API and
    the result is written back. Lets `record_fixtures.py` work without
    knowing about the new semantics.

  - `.refresh(*args, **kwargs)`: explicit escape hatch. Always calls the
    live function, writes the result to the cache, returns it. Used by
    `refresh_cache.py` (the cron entrypoint).

  - RENTCAST_ALLOW_LIVE=1: per-call opt-in for the non-warmable wrappers
    (property AVM, geofence). The cron can't pre-warm these because it
    doesn't know which addresses/coords a user will query, so soft-miss
    would break /property and /heatmap entirely. Functions can pass
    `allow_live=True` to opt into legacy behavior when this env var is on.
"""
import functools
import hashlib
import inspect
import json
import os

import db


DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes", "on")
_ALLOW_LIVE = os.getenv("RENTCAST_ALLOW_LIVE", "").lower() in ("1", "true", "yes", "on")


def _key(namespace, args, kwargs):
    blob = json.dumps({"args": list(args), "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(f"{namespace}|{blob}".encode()).hexdigest()


def cached(namespace, zip_arg=None, allow_live=False):
    """
    Decorator.

    namespace   — logical bucket; appears in api_cache.namespace
    zip_arg     — name (or 0-based index) of the ZIP argument, if any. Lets
                  the cache row carry a queryable `zip` so the cron knows
                  which entries belong to which tracked ZIP.
    allow_live  — if True, a miss may fall through to the live call when
                  RENTCAST_ALLOW_LIVE=1 is set in the env. Use for endpoints
                  the cron can't pre-warm (per-address AVMs, geofence).
                  Default False = strict soft-miss for unconfigured envs.
    """
    def decorator(fn):
        sig = inspect.signature(fn) if zip_arg else None

        def _zip_from(args, kwargs):
            """Extract the ZIP from a call regardless of positional vs keyword."""
            if zip_arg is None or sig is None:
                return None
            try:
                bound = sig.bind_partial(*args, **kwargs)
            except TypeError:
                return None
            val = bound.arguments.get(zip_arg) if isinstance(zip_arg, str) else None
            if val is None and isinstance(zip_arg, int) and zip_arg < len(args):
                val = args[zip_arg]
            return str(val) if val is not None else None

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = _key(namespace, args, kwargs)
            hit = db.get_cached(key)
            if hit is not None:
                return hit

            # In DEV_MODE we mimic the old fall-through so record_fixtures.py
            # and offline development keep working. In production this branch
            # is dead unless the wrapper opted into allow_live AND the env
            # flag is set.
            if DEV_MODE or (allow_live and _ALLOW_LIVE):
                result = fn(*args, **kwargs)
                if result is not None:
                    db.put_cached(key, namespace, result, _zip_from(args, kwargs))
                return result

            return None  # strict soft miss

        def refresh(*args, **kwargs):
            """Force a live call and write the result to the cache. Used by the cron."""
            result = fn(*args, **kwargs)
            if result is not None:
                db.put_cached(
                    _key(namespace, args, kwargs),
                    namespace,
                    result,
                    _zip_from(args, kwargs),
                )
            return result

        wrapper.refresh = refresh
        wrapper.__wrapped_namespace__ = namespace
        return wrapper

    return decorator
