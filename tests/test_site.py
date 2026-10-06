import json
from pathlib import Path

import pytest

from app.site import configured_trades, normal_workloads, tile_trades, validate_site, weather_station

ROOT = Path(__file__).resolve().parents[1]
DEMO = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))


def test_demo_site_is_valid_and_uses_official_examples():
    validate_site(DEMO)
    by = {t["labelZh"]: t["workload"] for t in configured_trades(DEMO)}
    assert by["紮鐵"] == "very_heavy" and by["棚架"] == "very_heavy"
    assert by["釘板"] == "heavy" and by["混凝土"] == "heavy"
    assert by["水喉"] == "moderate" and by["焊接"] == "moderate"
    assert by["保安"] == "light" and by["檢查"] == "light"


def test_trades_inherit_site_environment_and_adjust():
    site = {
        "environment": "indoor",
        "restAdjustMinutes": -15,
        "primaryTrades": [{"labelZh": "電工", "workload": "moderate"}],
    }
    (trade,) = configured_trades(site)
    assert trade == {
        "id": "電工", "labelZh": "電工", "workload": "moderate", "environment": "indoor", "adjustMinutes": -15
    }


def test_trade_overrides_win():
    site = {"primaryTrades": [{"labelZh": "焊接", "workload": "moderate", "environment": "aircon", "adjustMinutes": 15}]}
    (trade,) = configured_trades(site)
    assert trade["environment"] == "aircon" and trade["adjustMinutes"] == 15


def test_no_trades_gives_one_tile_row_per_workload():
    rows = tile_trades({"environment": "outdoor"})
    assert [r["labelZh"] for r in rows] == ["輕勞動", "中等勞動", "重勞動", "極重勞動"]


def test_normal_workloads_fall_back_to_default():
    assert normal_workloads({"defaultWorkload": "heavy"}) == {"heavy"}
    assert normal_workloads(DEMO) == {"light", "moderate", "heavy", "very_heavy"}


def test_weather_station_defaults():
    assert weather_station({"weatherStation": "沙田", "district": "觀塘"}) == "沙田"
    assert weather_station({"district": "觀塘"}) == "觀塘"
    assert weather_station({}) == "香港天文台"


@pytest.mark.parametrize(
    "bad",
    [
        {"environment": "rooftop"},
        {"restAdjustMinutes": 10},
        {"restAdjustMinutes": 75},
        {"primaryTrades": [{"labelZh": "紮鐵", "workload": "extreme"}]},
        {"primaryTrades": [{"workload": "heavy"}]},
        {"primaryTrades": [{"labelZh": "紮鐵", "workload": "heavy", "adjustMinutes": -45}]},
    ],
)
def test_invalid_site_config_raises(bad):
    with pytest.raises(ValueError):
        validate_site(bad)
