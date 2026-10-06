"""HKO temperature stations, and which one a screen at a given position should show."""
import json
import math
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parents[3]
STATIONS = json.loads((ROOT / "config" / "hko_stations.json").read_text(encoding="utf-8"))["stations"]
# The general HKO reading, shown whenever no better station is known.
OBSERVATORY = "香港天文台"

# A fix coarser than this cannot tell neighbouring stations apart, as with a position guessed from an IP address.
MAX_ACCURACY_M = 5000
# Farther than this from every station, the screen is not in Hong Kong. The remotest places people work at,
# such as Tap Mun, are 13 km from the nearest station.
MAX_DISTANCE_KM = 15
EARTH_RADIUS_KM = 6371.0088


class Position(NamedTuple):
    lat: float
    lon: float
    accuracy: Optional[float] = None  # metres, as the browser reports it


def station_names():
    return frozenset(s["name"] for s in STATIONS)


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _number(value):
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_position(lat, lon, accuracy=None):
    """A Position from raw query-string values, or None when they are absent or unusable."""
    la, lo = _number(lat), _number(lon)
    if la is None or lo is None or not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    if accuracy is None or str(accuracy).strip() == "":
        return Position(la, lo)
    acc = _number(accuracy)
    if acc is None or acc < 0:
        return None
    return Position(la, lo, acc)


def nearest_station(position, available):
    """Name of the station closest to `position` among the `available` names, or None.

    None also means the fix cannot be trusted (too coarse) or is nowhere near Hong Kong.
    """
    if position.accuracy is not None and position.accuracy > MAX_ACCURACY_M:
        return None
    best = None
    for station in STATIONS:
        if station["name"] not in available:
            continue
        d = distance_km(position.lat, position.lon, station["lat"], station["lon"])
        if best is None or d < best[0]:
            best = (d, station["name"])
    return best[1] if best and best[0] <= MAX_DISTANCE_KM else None
