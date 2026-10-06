"""Current weather (HKO rhrread) and tomorrow's forecast (HKO fnd) for the bottom bar."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
WX_ICONS = json.loads((ROOT / "config" / "wx_icons.json").read_text(encoding="utf-8"))["icons"]
WEATHER_MAX_AGE = timedelta(minutes=90)
FORECAST_MAX_AGE = timedelta(hours=12)
OBSERVATORY = "香港天文台"


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def wx_icon_rel(code):
    key = "" if code is None else str(code)
    return f"official/wxicon/pic{key}.png" if key in WX_ICONS else None


def parse_current(rhrread, station, now):
    if not isinstance(rhrread, dict):
        return None
    updated = parse_time(rhrread.get("updateTime"))
    if updated is None or now - updated > WEATHER_MAX_AGE:
        return None
    temps = {
        t.get("place"): t.get("value")
        for t in (rhrread.get("temperature") or {}).get("data") or []
        if isinstance(t, dict)
    }
    place = station if temps.get(station) is not None else OBSERVATORY
    temp = temps.get(place)
    if temp is None:
        return None
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
        "tempC": temp,
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
