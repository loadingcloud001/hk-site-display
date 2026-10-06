"""Current weather (HKO rhrread) and tomorrow's forecast (HKO fnd) for the bottom bar."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.stations import OBSERVATORY, nearest_station

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
WX_ICONS = json.loads((ROOT / "config" / "wx_icons.json").read_text(encoding="utf-8"))["icons"]
WEATHER_MAX_AGE = timedelta(minutes=90)
FORECAST_MAX_AGE = timedelta(hours=12)


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def wx_icon_rel(code):
    key = "" if code is None else str(code)
    return f"official/wxicon/pic{key}.png" if key in WX_ICONS else None


def readings(rhrread):
    """place -> temperature for the stations that have a numeric reading right now."""
    data = (rhrread.get("temperature") or {}).get("data") or []
    return {
        t.get("place"): t["value"]
        for t in data
        if isinstance(t, dict)
        and isinstance(t.get("value"), (int, float))
        and not isinstance(t.get("value"), bool)
    }


def parse_current(rhrread, station, now, position=None):
    """The weather block. The station shown is the one nearest `position` when there is a usable one,
    else `station`, else the Observatory. Only a station with a reading can be shown."""
    if not isinstance(rhrread, dict):
        return None
    updated = parse_time(rhrread.get("updateTime"))
    if updated is None or now - updated > WEATHER_MAX_AGE:
        return None
    temps = readings(rhrread)
    near = nearest_station(position, temps) if position else None
    place = next((p for p in (near, station, OBSERVATORY) if p in temps), None)
    if place is None:
        return None
    # HKO reports humidity for the Observatory only, so it is shown next to that station only.
    humidity = None
    if place == OBSERVATORY:
        humidity = next(
            (
                h.get("value")
                for h in (rhrread.get("humidity") or {}).get("data") or []
                if isinstance(h, dict) and h.get("place") == OBSERVATORY
            ),
            None,
        )
    uv_value = uv_desc = None
    uv = rhrread.get("uvindex")
    if isinstance(uv, dict) and uv.get("data"):
        first = uv["data"][0] or {}
        uv_value, uv_desc = first.get("value"), first.get("desc")
    icons = rhrread.get("icon") or []
    return {
        "iconRel": wx_icon_rel(icons[0]) if icons else None,
        "tempC": temps[place],
        "placeZh": place,
        "humidity": humidity,
        "uvValue": uv_value,
        "uvDescZh": uv_desc,
        "updatedAt": rhrread.get("updateTime"),
    }


def parse_forecast(fnd, now):
    if not isinstance(fnd, dict):
        return None
    updated = parse_time(fnd.get("updateTime"))
    if updated is None or now - updated > FORECAST_MAX_AGE:
        return None
    today = now.astimezone(HKT).strftime("%Y%m%d")
    for day in fnd.get("weatherForecast") or []:
        date = str(day.get("forecastDate") or "")
        if date > today:
            return {
                "date": date,
                "iconRel": wx_icon_rel(day.get("ForecastIcon")),
                "minC": (day.get("forecastMintemp") or {}).get("value"),
                "maxC": (day.get("forecastMaxtemp") or {}).get("value"),
            }
    return None
