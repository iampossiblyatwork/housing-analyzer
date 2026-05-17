import json, os, hashlib, time

_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(_CACHE_DIR, exist_ok=True)


def _path(namespace, params):
    h = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    return os.path.join(_CACHE_DIR, f"{namespace}_{h}.json")


def get(namespace, params, ttl):
    try:
        with open(_path(namespace, params)) as f:
            entry = json.load(f)
        if time.time() - entry["ts"] < ttl:
            return entry["data"]
    except Exception:
        pass
    return None


def put(namespace, params, data):
    with open(_path(namespace, params), "w") as f:
        json.dump({"ts": time.time(), "data": data}, f)
