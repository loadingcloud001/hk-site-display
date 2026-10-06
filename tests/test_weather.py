import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.stations import Position
from app.weather import parse_current, parse_forecast

HKT = timezone(timedelta(hours=8))
FIX = Path(__file__).resolve().parent / "fixtures"
NOW = datetime(2026, 10, 6, 17, 30, tzinfo=HKT)
NOW_FULL = datetime(2026, 10, 6, 21, 30, tzinfo=HKT)  # shortly after rhrread_full.json was issued
KWUN_TONG = Position(22.3125, 114.2260, 60)
TUEN_MUN = Position(22.3917, 113.9766, 60)


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_current_uses_site_station():
    assert parse_current(load("rhrread_sample.json"), "觀塘", NOW) == {
        "iconRel": "official/wxicon/pic51.png",
        "tempC": 28,
        "placeZh": "觀塘",
        "humidity": None,
        "uvValue": 0.7,
        "uvDescZh": "低",
        "updatedAt": "2026-10-06T17:02:00+08:00",
    }


def test_current_falls_back_to_observatory():
    weather = parse_current(load("rhrread_sample.json"), "沙田", NOW)
    assert weather["placeZh"] == "香港天文台" and weather["tempC"] == 27


def test_humidity_belongs_to_the_observatory_only():
    raw = load("rhrread_sample.json")
    assert parse_current(raw, "香港天文台", NOW)["humidity"] == 62
    assert parse_current(raw, "觀塘", NOW)["humidity"] is None
    assert parse_current(raw, "沙田", NOW)["humidity"] == 62  # shown station fell back to the Observatory


def test_position_picks_the_nearest_reporting_station():
    raw = load("rhrread_full.json")
    here = parse_current(raw, "香港天文台", NOW_FULL, KWUN_TONG)
    assert (here["placeZh"], here["tempC"], here["humidity"]) == ("觀塘", 25, None)
    far = parse_current(raw, "香港天文台", NOW_FULL, TUEN_MUN)
    assert (far["placeZh"], far["tempC"]) == ("屯門", 25)


def test_position_wins_over_the_site_station():
    assert parse_current(load("rhrread_full.json"), "沙田", NOW_FULL, KWUN_TONG)["placeZh"] == "觀塘"


def test_unusable_position_keeps_the_site_station():
    raw = load("rhrread_full.json")
    coarse = Position(22.3125, 114.2260, 20000)
    assert parse_current(raw, "沙田", NOW_FULL, coarse)["placeZh"] == "沙田"
    assert parse_current(raw, "沙田", NOW_FULL, Position(51.5, -0.12, 50))["placeZh"] == "沙田"
    assert parse_current(raw, "沙田", NOW_FULL, None)["placeZh"] == "沙田"
    assert parse_current(raw, "香港天文台", NOW_FULL, coarse)["placeZh"] == "香港天文台"


def test_station_without_a_reading_is_skipped():
    raw = load("rhrread_full.json")
    for t in raw["temperature"]["data"]:
        if t["place"] == "觀塘":
            t["value"] = ""
    assert parse_current(raw, "香港天文台", NOW_FULL, KWUN_TONG)["placeZh"] == "啟德跑道公園"
    assert parse_current(raw, "觀塘", NOW_FULL)["placeZh"] == "香港天文台"


def test_current_hidden_when_old_or_incomplete():
    assert parse_current(load("rhrread_sample.json"), "觀塘", NOW + timedelta(minutes=100)) is None
    assert parse_current({}, "觀塘", NOW) is None
    assert parse_current({"icon": [60]}, "觀塘", NOW) is None


def test_current_empty_uv_and_unknown_icon():
    raw = load("rhrread_sample.json")
    raw["uvindex"] = ""
    raw["icon"] = [99]
    weather = parse_current(raw, "觀塘", NOW)
    assert weather["uvValue"] is None and weather["uvDescZh"] is None and weather["iconRel"] is None


def test_forecast_picks_first_future_day():
    assert parse_forecast(load("fnd_sample.json"), NOW) == {
        "date": "20261007", "iconRel": "official/wxicon/pic81.png", "minC": 23, "maxC": 30
    }


def test_forecast_skips_today_and_expires():
    after_midnight = datetime(2026, 10, 7, 1, 0, tzinfo=HKT)
    assert parse_forecast(load("fnd_sample.json"), after_midnight)["date"] == "20261008"
    assert parse_forecast(load("fnd_sample.json"), NOW + timedelta(hours=13)) is None
