import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.stations import HIGH_GROUND_M, NEAR_WIND_STATIONS, WIND_STATIONS, Position, wind_station_names
from app.wind import WIND_MAX_AGE, current_wind, parse_wind_csv

HKT = timezone(timedelta(hours=8))
FIX = Path(__file__).resolve().parent / "fixtures"
# tests/fixtures/wind_10min_uc.csv is HKO's report for 22:20 HKT on 2026-11-07 (Strong Monsoon Signal in force).
TEXT = (FIX / "wind_10min_uc.csv").read_text(encoding="utf-8")
REPORT = parse_wind_csv(TEXT)
NOW = datetime(2026, 11, 7, 22, 26, tzinfo=HKT)


def with_rows(*rows):
    head = "﻿日期時間,自動氣象站,十分鐘平均風向（方位點）,十分鐘平均風速（公里/小時）,十分鐘最高陣風風速（公里/小時）"
    return "\n".join([head, *(",".join(r) for r in rows)]) + "\n"


def test_parses_hkos_real_report():
    assert REPORT["at"] == "2026-11-07T22:20:00+08:00"
    assert len(REPORT["stations"]) == 30
    assert REPORT["stations"]["啟德"] == {"dir": "東", "speed": 22, "gust": 40, "at": "2026-11-07T22:20:00+08:00"}
    # 赤柱 reported no direction ("N/A") at that time.
    assert REPORT["stations"]["赤柱"]["dir"] is None and REPORT["stations"]["赤柱"]["gust"] == 45


def test_missing_values_are_none():
    report = parse_wind_csv(with_rows(["202611072220", "啟德", "N/A", "N/A", "N/A"], ["202611072220", "北角", "東", "12", "N/A"]))
    assert report["stations"]["啟德"] == {"dir": None, "speed": None, "gust": None, "at": "2026-11-07T22:20:00+08:00"}
    assert report["stations"]["北角"]["gust"] is None


@pytest.mark.parametrize("text", ["", "<html>error</html>", "a,b,c,d,e\n1,2,3,4,5\n", with_rows()])
def test_anything_else_raises_so_the_feed_keeps_its_last_value(text):
    with pytest.raises(ValueError):
        parse_wind_csv(text)


def test_every_station_in_the_real_report_is_in_the_table():
    rows = list(csv.reader(io.StringIO(TEXT.lstrip("﻿"))))[1:]
    assert {row[1] for row in rows} == wind_station_names()


def test_wind_table_is_well_formed():
    assert len(WIND_STATIONS) == len({s["code"] for s in WIND_STATIONS}) == len(wind_station_names())
    for s in WIND_STATIONS:
        assert s["name"] and s["nameEn"] and s["code"]
        if s["lat"] is None:
            assert s["code"] == "HSS"  # Hong Kong Sea School: on HKO's wind page, not on its station page
            continue
        assert 22.1 < s["lat"] < 22.6 and 113.8 < s["lon"] < 114.5, s["name"]


def test_codes_match_hkos_wind_page():
    by_name = {s["name"]: s["code"] for s in WIND_STATIONS}
    # https://www.hko.gov.hk/en/wxinfo/ts/display_element_ff.htm lists Stanley as #bhd and Tsing Yi as #shl.
    assert (by_name["赤柱"], by_name["青衣"], by_name["啟德"], by_name["塔門"]) == ("BHD", "SHL", "SE", "TME")


def test_high_ground_stations_are_never_nearest():
    high = {s["name"] for s in WIND_STATIONS if (s["elevation"] or 0) >= HIGH_GROUND_M}
    assert high == {"昂坪", "大老山"}
    assert not high & {s["name"] for s in NEAR_WIND_STATIONS}


@pytest.mark.parametrize(
    "lat, lon, expected",
    [
        (22.3125, 114.2260, "啟德"),  # Kwun Tong
        (22.2976, 114.1722, "天星碼頭"),  # Tsim Sha Tsui
        (22.2819, 114.1580, "中環碼頭"),  # Central
        (22.3714, 114.1139, "青衣"),  # Tsuen Wan
        (22.2890, 113.9410, "赤鱲角"),  # Tung Chung
        (22.3830, 114.1880, "沙田"),
        (22.2190, 114.2120, "赤柱"),
        (22.3917, 113.9766, "屯門"),
        # Wong Tai Sin and Diamond Hill are nearest to Tate's Cairn (572 m), which reads high-ground winds.
        (22.3420, 114.1930, "京士柏"),
        (22.3400, 114.2010, "啟德"),
    ],
)
def test_nearest_ground_level_station(lat, lon, expected):
    wind = current_wind(REPORT, None, NOW, Position(lat, lon, 50))
    assert wind["placeZh"] == expected


def test_block_content():
    assert current_wind(REPORT, None, NOW, Position(22.3125, 114.2260, 50)) == {
        "placeZh": "啟德",
        "dirZh": "東",
        "speedKmh": 22,
        "gustKmh": 40,
        "updatedAt": "2026-11-07T22:20:00+08:00",
    }


def test_site_station_without_a_position_and_hidden_without_either():
    assert current_wind(REPORT, "沙田", NOW)["placeZh"] == "沙田"
    assert current_wind(REPORT, None, NOW) is None
    # A position that cannot be used (too coarse, or not in Hong Kong) falls back the same way.
    assert current_wind(REPORT, "沙田", NOW, Position(22.31, 114.22, 20000))["placeZh"] == "沙田"
    assert current_wind(REPORT, "沙田", NOW, Position(51.5, -0.12, 20))["placeZh"] == "沙田"
    assert current_wind(REPORT, None, NOW, Position(51.5, -0.12, 20)) is None


def test_a_station_without_a_speed_is_skipped():
    report = parse_wind_csv(with_rows(["202611072220", "啟德", "東", "N/A", "40"], ["202611072220", "將軍澳", "東", "15", "30"]))
    assert current_wind(report, None, NOW, Position(22.3125, 114.2260, 50))["placeZh"] == "將軍澳"
    assert current_wind(report, "啟德", NOW) is None


def test_old_reports_are_hidden_and_a_slow_server_clock_is_tolerated():
    at = datetime(2026, 11, 7, 22, 20, tzinfo=HKT)
    assert current_wind(REPORT, "啟德", at + WIND_MAX_AGE) is not None
    assert current_wind(REPORT, "啟德", at + WIND_MAX_AGE + timedelta(minutes=1)) is None
    assert current_wind(REPORT, "啟德", at - timedelta(minutes=3)) is not None
    assert current_wind(None, "啟德", NOW) is None
