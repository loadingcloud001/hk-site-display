"""10-minute mean wind and maximum gust (HKO regional weather report) for the bottom bar.

Lifting supervisors check the wind before crane, gondola and work-at-height jobs. The screen shows
HKO's reading at a nearby station with the station's name; it never turns the reading into an instruction.
"""
import csv
import io
from datetime import datetime, timedelta, timezone

from app.stations import NEAR_WIND_STATIONS, nearest_station
from app.weather import parse_time

HKT = timezone(timedelta(hours=8))
# HKO updates the report every 10 minutes; an older reading is no longer "current" in gusty weather.
WIND_MAX_AGE = timedelta(minutes=30)
# A server clock a little behind HKO's must not hide a fresh reading.
CLOCK_SLACK = timedelta(minutes=5)
MISSING = {"", "N/A"}


def _number(text):
    try:
        value = float(str(text).strip())
    except ValueError:
        return None
    return int(value) if value.is_integer() else value


def parse_wind_csv(text):
    """HKO's Chinese 10-minute wind CSV -> {"at": iso, "stations": {place: {dir, speed, gust, at}}}.

    Raises ValueError when the text is not that report, so the feed keeps its last good value.
    """
    rows = list(csv.reader(io.StringIO((text or "").lstrip("﻿"))))
    if not rows or len(rows[0]) < 5 or "陣風" not in "".join(rows[0]):
        raise ValueError("not HKO's 10-minute wind report")
    stations, latest = {}, None
    for row in rows[1:]:
        if len(row) < 5:
            continue
        stamp, place, direction, speed, gust = (cell.strip() for cell in row[:5])
        try:
            at = datetime.strptime(stamp, "%Y%m%d%H%M").replace(tzinfo=HKT)
        except ValueError:
            continue
        latest = at if latest is None or at > latest else latest
        stations[place] = {
            "dir": None if direction in MISSING else direction,
            "speed": None if speed in MISSING else _number(speed),
            "gust": None if gust in MISSING else _number(gust),
            "at": at.isoformat(),
        }
    if not stations:
        raise ValueError("the wind report has no stations")
    return {"at": latest.isoformat(), "stations": stations}


def current_wind(report, station, now, position=None):
    """The wind block: the nearest ground-level station to `position` that reports a wind speed, else the
    site's `station`. None when neither has a fresh reading (the block is then hidden)."""
    if not isinstance(report, dict):
        return None
    fresh = {}
    for place, row in (report.get("stations") or {}).items():
        at = parse_time(row.get("at"))
        if row.get("speed") is not None and at is not None and -CLOCK_SLACK <= now - at <= WIND_MAX_AGE:
            fresh[place] = row
    near = nearest_station(position, fresh, NEAR_WIND_STATIONS) if position else None
    place = next((p for p in (near, station) if p and p in fresh), None)
    if place is None:
        return None
    row = fresh[place]
    return {
        "placeZh": place,
        "dirZh": row["dir"],
        "speedKmh": row["speed"],
        "gustKmh": row["gust"],
        "updatedAt": row["at"],
    }
