"""
School district boundaries and attributes from Census TIGERweb (ArcGIS REST).

Free, no API key — same Census family as census_api.py. The polygons are the
NCES Local Education Agency boundaries as published by the Census Bureau, in
three levels: unified, elementary, secondary. (Most of the US is covered by
unified districts; elementary/secondary only exist where a community splits
K-8 and 9-12 governance.)

Backs the school district map overlay (`/api/school-districts`, drawn on the
heatmap and geofence maps) and the district card on /property.

Lookups are cached 7 days (boundaries change at most annually) and recorded
to the dev fixture store in DEV_MODE. Any network or service failure returns
None — callers render an "unavailable" state instead of erroring.
"""
import math
import requests
import cache
import dev_cache

_BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/School_Districts/MapServer"
_TTL  = 604800  # 7 days

_OUT_FIELDS = "GEOID,NAME,LOGRADE,HIGRADE"

LEVELS = ("unified", "elementary", "secondary")

# Max bbox span (degrees) for a boundary query. Wider views would pull
# hundreds of polygons in a multi-MB payload (and hit TIGERweb's record
# cap); the route returns a "zoom in" error instead.
MAX_BBOX_SPAN = 4.0

# Snap bbox queries outward to this grid so small pans reuse the same cache
# entry instead of issuing a fresh TIGERweb call per pixel of movement.
_BBOX_GRID = 0.02  # degrees, ~2 km


# ── Public API ────────────────────────────────────────────────────────────────

def get_districts_by_bbox(west, south, east, north, level="unified"):
    """GeoJSON FeatureCollection of districts intersecting the bbox, or None."""
    if level not in LEVELS:
        return None
    w = round(math.floor(west  / _BBOX_GRID) * _BBOX_GRID, 2)
    s = round(math.floor(south / _BBOX_GRID) * _BBOX_GRID, 2)
    e = round(math.ceil(east   / _BBOX_GRID) * _BBOX_GRID, 2)
    n = round(math.ceil(north  / _BBOX_GRID) * _BBOX_GRID, 2)
    try:
        return _districts_by_bbox(level, w, s, e, n)
    except (requests.exceptions.RequestException, RuntimeError):
        return None


def get_districts_for_point(lat, lng):
    """All districts (any level) covering a point, as a list of dicts, or None.

    Returns at most one district per level — unified-only in most of the US,
    elementary + secondary where K-8/9-12 governance is split.
    An empty list means the point is in a district-less area; None means the
    service was unreachable.
    """
    try:
        return _districts_for_point(round(float(lat), 4), round(float(lng), 4))
    except (requests.exceptions.RequestException, RuntimeError, ValueError):
        return None


# ── TIGERweb plumbing ─────────────────────────────────────────────────────────

@dev_cache.fixture("schools.layers")
@cache.cached("schools.layers", ttl=_TTL)
def _layer_ids():
    """Map level name → TIGERweb layer id, discovered from service metadata.

    Discovered at runtime rather than hardcoded because TIGERweb has
    renumbered layers across vintages.
    """
    r = requests.get(_BASE, params={"f": "json"}, timeout=15)
    r.raise_for_status()
    ids = {}
    for layer in r.json().get("layers", []):
        name = (layer.get("name") or "").lower()
        if "label" in name:
            continue
        for level in LEVELS:
            if level in name:
                ids.setdefault(level, layer["id"])
    if not ids:
        raise RuntimeError("TIGERweb returned no school district layers — service may be misconfigured")
    return ids


def _query(layer_id, params):
    base = {
        "inSR":       4326,
        "outSR":      4326,
        "outFields":  _OUT_FIELDS,
        "spatialRel": "esriSpatialRelIntersects",
        "where":      "1=1",
        "f":          "geojson",
    }
    base.update(params)
    r = requests.get(f"{_BASE}/{layer_id}/query", params=base, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" not in data and "features" in data:
        return data
    # Older ArcGIS builds reject f=geojson — fall back to Esri JSON.
    base["f"] = "json"
    r = requests.get(f"{_BASE}/{layer_id}/query", params=base, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"TIGERweb query failed: {data['error']}")
    return _esri_to_geojson(data)


def _esri_to_geojson(esri):
    feats = []
    for f in esri.get("features", []):
        rings = (f.get("geometry") or {}).get("rings")
        if not rings:
            geom = None
        elif len(rings) == 1:
            geom = {"type": "Polygon", "coordinates": rings}
        else:
            # Multi-ring Esri geometry: each ring may be a separate outer
            # polygon (island/enclave) rather than a hole in the first ring.
            # Winding-order analysis is complex; wrapping each ring as its own
            # polygon in a MultiPolygon is correct for districts with islands
            # and degrades gracefully (holes render as filled) for the rare
            # case of a district with an interior hole.
            geom = {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}
        feats.append({"type": "Feature", "geometry": geom,
                      "properties": f.get("attributes", {})})
    return {"type": "FeatureCollection", "features": feats}


@dev_cache.fixture("schools.bbox")
@cache.cached("schools.bbox", ttl=_TTL)
def _districts_by_bbox(level, west, south, east, north):
    layer_id = _layer_ids().get(level)
    if layer_id is None:
        raise RuntimeError(f"No TIGERweb layer found for level '{level}'")
    fc = _query(layer_id, {
        "geometry":           f"{west},{south},{east},{north}",
        "geometryType":       "esriGeometryEnvelope",
        "returnGeometry":     "true",
        "geometryPrecision":  5,
        # ~30 m simplification — invisible at city zoom, big payload win.
        "maxAllowableOffset": 0.0003,
    })
    for f in fc.get("features", []):
        f["properties"] = _shape_properties(f.get("properties", {}), level)
    return fc


@dev_cache.fixture("schools.point")
@cache.cached("schools.point", ttl=_TTL)
def _districts_for_point(lat, lng):
    out = []
    layers = _layer_ids()
    for level in LEVELS:
        layer_id = layers.get(level)
        if layer_id is None:
            continue
        fc = _query(layer_id, {
            "geometry":       f"{lng},{lat}",
            "geometryType":   "esriGeometryPoint",
            "returnGeometry": "false",
        })
        for f in fc.get("features", []):
            out.append(_shape_properties(f.get("properties", {}), level))
    return out


# ── Attribute shaping ─────────────────────────────────────────────────────────

def _shape_properties(attrs, level):
    # f=geojson and the Esri fallback both surface raw TIGER field names —
    # flatten to the lowercase keys the templates and overlay JS consume.
    def get(k):
        return attrs.get(k) or attrs.get(k.lower())
    return {
        "geoid":  get("GEOID"),
        "name":   get("NAME"),
        "grades": format_grade_range(get("LOGRADE"), get("HIGRADE")),
        "level":  level,
    }


_GRADE_LABELS = {"PK": "PK", "KG": "K", "UN": None, "00": None}


def _grade(g):
    if not g:
        return None
    g = str(g).strip().upper()
    if g in _GRADE_LABELS:
        return _GRADE_LABELS[g]
    return g.lstrip("0") or None


def format_grade_range(lo, hi):
    """TIGER LOGRADE/HIGRADE codes ('PK', 'KG', '01'…'12') → 'PK–12'."""
    lo, hi = _grade(lo), _grade(hi)
    if lo and hi:
        return f"{lo}–{hi}"
    return lo or hi
