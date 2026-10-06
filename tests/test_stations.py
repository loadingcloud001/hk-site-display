import json
from pathlib import Path

import pytest

from app.stations import (
    MAX_ACCURACY_M,
    MAX_DISTANCE_KM,
    STATIONS,
    Position,
    distance_km,
    nearest_station,
    parse_position,
    station_names,
)

FIX = Path(__file__).resolve().parent / "fixtures"
ALL = station_names()


def test_every_station_in_a_real_report_has_coordinates():
    report = json.loads((FIX / "rhrread_full.json").read_text(encoding="utf-8"))
    reported = {t["place"] for t in report["temperature"]["data"]}
    assert len(reported) == 27
    assert reported <= ALL


def test_station_table_is_well_formed():
    assert len(ALL) == len(STATIONS) == len({s["code"] for s in STATIONS})
    for s in STATIONS:
        assert s["name"] and s["nameEn"] and s["code"]
        assert 22.1 < s["lat"] < 22.6 and 113.8 < s["lon"] < 114.5, s["name"]


def test_coordinates_match_hko_published_table():
    by_name = {s["name"]: s for s in STATIONS}
    # 22°18'07" N 114°10'27" E and 22°19'07" N 114°13'29" E on https://www.hko.gov.hk/en/cis/stn.htm
    assert (by_name["香港天文台"]["lat"], by_name["香港天文台"]["lon"]) == (22.30194, 114.17417)
    assert (by_name["觀塘"]["lat"], by_name["觀塘"]["lon"]) == (22.31861, 114.22472)


def test_distance_between_the_observatory_and_kwun_tong():
    assert distance_km(22.30194, 114.17417, 22.31861, 114.22472) == pytest.approx(5.5, abs=0.1)
    assert distance_km(22.3, 114.2, 22.3, 114.2) == 0


@pytest.mark.parametrize(
    "lat, lon, expected",
    [
        (22.2976, 114.1722, "香港天文台"),  # Tsim Sha Tsui
        (22.3125, 114.2260, "觀塘"),
        (22.3917, 113.9766, "屯門"),
        (22.2890, 113.9410, "赤鱲角"),  # Tung Chung
        (22.2190, 114.2120, "赤柱"),
        (22.2096, 114.0295, "長洲"),
        (22.3030, 114.2000, "啟德跑道公園"),  # Kai Tak
    ],
)
def test_nearest_station_for_known_places(lat, lon, expected):
    assert nearest_station(Position(lat, lon, 50), ALL) == expected


def test_nearest_station_skips_stations_without_a_reading():
    here = Position(22.3125, 114.2260, 50)
    assert nearest_station(here, ALL) == "觀塘"
    assert nearest_station(here, ALL - {"觀塘"}) == "啟德跑道公園"
    assert nearest_station(here, set()) is None
    assert nearest_station(here, {"unknown place"}) is None


def test_far_from_every_station_is_not_a_match():
    macau = Position(22.1987, 113.5439, 50)
    assert nearest_station(macau, ALL) is None
    assert nearest_station(Position(51.5074, -0.1278, 50), ALL) is None
    # Tap Mun is the remotest place people work at, 12.6 km from the nearest station.
    assert nearest_station(Position(22.4710, 114.3600, 50), ALL) == "大美督"
    assert MAX_DISTANCE_KM >= 13


def test_too_coarse_a_fix_is_not_a_match():
    tsim_sha_tsui = (22.2976, 114.1722)
    assert nearest_station(Position(*tsim_sha_tsui, MAX_ACCURACY_M), ALL) == "香港天文台"
    assert nearest_station(Position(*tsim_sha_tsui, MAX_ACCURACY_M + 1), ALL) is None
    assert nearest_station(Position(*tsim_sha_tsui, None), ALL) == "香港天文台"


def test_parse_position_reads_query_values():
    assert parse_position("22.31", "114.22", "65") == Position(22.31, 114.22, 65.0)
    assert parse_position("22.31", "114.22", None) == Position(22.31, 114.22, None)
    assert parse_position(" 22.31 ", "114.22", "") == Position(22.31, 114.22, None)


@pytest.mark.parametrize(
    "lat, lon, acc",
    [
        (None, None, None),
        ("22.3", None, "10"),
        (None, "114.2", "10"),
        ("", "", ""),
        ("abc", "114.2", "10"),
        ("22.3", "114.2", "abc"),
        ("nan", "114.2", "10"),
        ("22.3", "inf", "10"),
        ("22.3", "114.2", "nan"),
        ("22.3", "114.2", "-5"),
        ("91", "114.2", "10"),
        ("-91", "114.2", "10"),
        ("22.3", "181", "10"),
        ("22.3", "-181", "10"),
        ("1e999", "114.2", "10"),
    ],
)
def test_parse_position_rejects_unusable_values(lat, lon, acc):
    assert parse_position(lat, lon, acc) is None
