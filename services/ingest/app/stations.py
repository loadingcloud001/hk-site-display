"""HKO temperature stations, and which one a screen at a given position should show."""
import json
import math
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parents[3]
_TABLE = json.loads((ROOT / "config" / "hko_stations.json").read_text(encoding="utf-8"))
STATIONS = _TABLE["stations"]
WIND_STATIONS = _TABLE.get("windStations") or []
# The general HKO reading, shown whenever no better station is known.
OBSERVATORY = "香港天文台"
# HKO forecasts winds on high ground (高地) separately: stations this high (Ngong Ping, Tate's Cairn) read far
# stronger winds than a site at street level, so they are never chosen as the nearest wind station.
HIGH_GROUND_M = 300
# Wind stations a screen's position can choose: ground level, with published coordinates.
NEAR_WIND_STATIONS = [
    s for s in WIND_STATIONS if s.get("lat") is not None and (s.get("elevation") or 0) < HIGH_GROUND_M
]

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


def wind_station_names():
    return frozenset(s["name"] for s in WIND_STATIONS)


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


def nearest_station(position, available, stations=None):
    """Name of the station closest to `position` among the `available` names, or None.

    `stations` is the table to choose from (temperature stations by default).
    None also means the fix cannot be trusted (too coarse) or is nowhere near Hong Kong.
    """
    if position.accuracy is not None and position.accuracy > MAX_ACCURACY_M:
        return None
    best = None
    for station in STATIONS if stations is None else stations:
        if station["name"] not in available or station.get("lat") is None:
            continue
        d = distance_km(position.lat, position.lon, station["lat"], station["lon"])
        if best is None or d < best[0]:
            best = (d, station["name"])
    return best[1] if best and best[0] <= MAX_DISTANCE_KM else None
