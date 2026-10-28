"""
Which Thai province is a point in? Offline lookup against province boundaries.

The bounding box in core/geo.py is a cheap first check (and a DB constraint),
but it also covers parts of Laos, Cambodia and Myanmar. This module uses the
real province polygons plus the outlines of the neighbouring countries
(core/data/th_provinces.json, from geoBoundaries / OpenStreetMap):

  * inside a province                → that province (provinces within
                                       BORDER_KM also count, because the
                                       simplified borders are off by ~1 km)
  * inside a neighbouring country    → outside Thailand (unless within
                                       BORDER_KM of Thailand, same reason)
  * neither, i.e. at sea             → nearest province within SEA_KM, so small
                                       islands missing from the simplified
                                       data (e.g. the Similans) still work

Pure Python (ray casting), no GIS dependency. Data is loaded once per process.
"""
import json
from dataclasses import dataclass, field
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "th_provinces.json"
BORDER_KM = 3
SEA_KM = 100
_KM_PER_DEG = 111.32


@dataclass(frozen=True)
class _Area:
    name: str
    bbox: tuple  # (min_lng, min_lat, max_lng, max_lat)
    polygons: list  # [[outer ring, *holes], ...]; ring = [[lng, lat], ...]


@dataclass
class PinCheck:
    """Result of checking a map pin."""

    province: str | None  # best match; None = outside Thailand
    allowed: set = field(default_factory=set)  # provinces a user may pick for this pin
    country: str | None = None  # neighbouring country the pin is in, if any

    @property
    def in_thailand(self) -> bool:
        return self.province is not None


def _area(name, polygons) -> _Area:
    lngs = [c[0] for poly in polygons for c in poly[0]]
    lats = [c[1] for poly in polygons for c in poly[0]]
    return _Area(name, (min(lngs), min(lats), max(lngs), max(lats)), polygons)


@lru_cache(maxsize=1)
def _data():
    raw = json.loads(DATA_FILE.read_text())
    return ([_area(p["name"], p["polygons"]) for p in raw["provinces"]],
            [_area(n["name"], n["polygons"]) for n in raw["neighbours"]])


def province_names() -> list[str]:
    return sorted(a.name for a in _data()[0])


def canonical_province(name: str) -> str | None:
    """'chiang mai ' → 'Chiang Mai'; None if not a Thai province."""
    wanted = " ".join(name.split()).casefold()
    return next((n for n in province_names() if n.casefold() == wanted), None)


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
def _in_ring(lng, lat, ring) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _contains(area: _Area, lng, lat) -> bool:
    x0, y0, x1, y1 = area.bbox
    if not (x0 <= lng <= x1 and y0 <= lat <= y1):
        return False
    return any(_in_ring(lng, lat, poly[0]) and not any(_in_ring(lng, lat, h) for h in poly[1:])
               for poly in area.polygons)


def _edge_km(area: _Area, lng, lat, limit_km) -> float:
    """Distance from the point to the area's boundary (inf if farther than limit_km)."""
    pad_lat = limit_km / _KM_PER_DEG
    pad_lng = pad_lat / max(cos(radians(lat)), 0.1)
    x0, y0, x1, y1 = area.bbox
    if not (x0 - pad_lng <= lng <= x1 + pad_lng and y0 - pad_lat <= lat <= y1 + pad_lat):
        return float("inf")
    # Local flat projection in km around the point — accurate enough at these distances.
    kx, ky = _KM_PER_DEG * cos(radians(lat)), _KM_PER_DEG
    best = float("inf")
    for poly in area.polygons:
        for ring in poly:
            for (ax, ay), (bx, by) in zip(ring, ring[1:]):
                ax, ay, bx, by = (ax - lng) * kx, (ay - lat) * ky, (bx - lng) * kx, (by - lat) * ky
                dx, dy = bx - ax, by - ay
                seg = dx * dx + dy * dy
                t = 0.0 if seg == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg))
                px, py = ax + t * dx, ay + t * dy
                best = min(best, px * px + py * py)
    return sqrt(best)


def _provinces_within(lng, lat, km) -> list[tuple[float, str]]:
    found = [(_edge_km(a, lng, lat, km), a.name) for a in _data()[0]]
    return sorted((d, n) for d, n in found if d <= km)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def check_pin(latitude: float, longitude: float) -> PinCheck:
    provinces, neighbours = _data()
    lng, lat = longitude, latitude

    inside = next((a.name for a in provinces if _contains(a, lng, lat)), None)
    if inside:
        near = {n for _, n in _provinces_within(lng, lat, BORDER_KM)}
        return PinCheck(province=inside, allowed={inside} | near)

    country = next((a.name for a in neighbours if _contains(a, lng, lat)), None)
    near = _provinces_within(lng, lat, BORDER_KM if country else SEA_KM)
    if not near:
        return PinCheck(province=None, country=country)
    nearest = near[0][1]
    # At sea: only the nearest province. Just over a land border: the border provinces.
    allowed = {nearest} if not country else {n for _, n in near}
    return PinCheck(province=nearest, allowed=allowed)


def province_at(latitude: float, longitude: float) -> str | None:
    """Province name for a point, or None if it is not inside Thailand."""
    return check_pin(latitude, longitude).province


def distance_km(lat1, lng1, lat2, lng2) -> float:
    """Great-circle distance (haversine)."""
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))
