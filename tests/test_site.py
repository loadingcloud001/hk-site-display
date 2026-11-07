import json
from pathlib import Path

import pytest

from app.site import (
    GENERIC_SITE,
    configured_trades,
    load_sites,
    normal_workloads,
    tile_trades,
    validate_site,
    weather_station,
    wind_station,
)

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


def test_weather_station_defaults_to_the_observatory():
    assert weather_station({"weatherStation": "沙田"}) == "沙田"
    assert weather_station({"district": "觀塘"}) == "香港天文台"
    assert weather_station({}) == "香港天文台"
    assert weather_station(DEMO) == "香港天文台"


def test_weather_station_must_be_a_known_hko_station():
    validate_site({"weatherStation": "沙田"})
    with pytest.raises(ValueError, match="weatherStation"):
        validate_site({"weatherStation": "Sha Tin"})


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


def test_wind_station_must_be_an_hko_wind_station():
    assert wind_station({**DEMO, "windStation": "啟德"}) == "啟德"
    assert wind_station({"primaryTrades": []}) is None
    validate_site({**DEMO, "windStation": "香港航海學校"})  # listed by HKO without coordinates: fine as a fallback
    with pytest.raises(ValueError, match="windStation"):
        validate_site({**DEMO, "windStation": "觀塘"})  # a temperature station, not a wind station


def write(directory, name, site):
    (directory / name).write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")


def test_every_site_file_is_loaded_and_the_demo_is_the_default(tmp_path):
    write(tmp_path, "demo-site.json", DEMO)
    write(tmp_path, "a.json", {**DEMO, "siteId": "site-a"})
    write(tmp_path, "b.json", {**DEMO, "siteId": None})  # no siteId: the file name is the id
    sites, default, problems = load_sites(tmp_path)
    assert set(sites) == {"demo-kai-tak", "site-a", "b"}
    assert (default, problems) == ("demo-kai-tak", [])
    assert load_sites(tmp_path, "site-a")[1:] == ("site-a", [])


def test_a_wrong_default_site_shows_the_generic_site_and_is_reported(tmp_path):
    write(tmp_path, "demo-site.json", DEMO)
    sites, default, problems = load_sites(tmp_path, "nope")
    assert default is None and set(sites) == {"demo-kai-tak"}
    assert problems == ["DEFAULT_SITE 'nope' is not a usable siteId in config/sites"]


def test_one_site_without_the_demo_is_the_default(tmp_path):
    write(tmp_path, "only.json", {**DEMO, "siteId": "only"})
    assert load_sites(tmp_path)[1:] == ("only", [])


def test_several_sites_without_the_demo_need_default_site(tmp_path):
    write(tmp_path, "a.json", {**DEMO, "siteId": "a"})
    write(tmp_path, "b.json", {**DEMO, "siteId": "b"})
    sites, default, problems = load_sites(tmp_path)
    assert set(sites) == {"a", "b"} and default is None
    assert problems == ["several site files and no demo-site.json: set DEFAULT_SITE"]


@pytest.mark.parametrize(
    "content, message",
    [
        ("{ not json", "config/sites/bad.json: Expecting property name"),
        ("[1, 2]", "config/sites/bad.json: must be a JSON object"),
        (json.dumps({**DEMO, "siteId": "bad", "restAdjustMinutes": 10}), "config/sites/bad.json: restAdjustMinutes"),
        (json.dumps({**DEMO, "siteId": "bad", "weatherStation": ["觀塘"]}), "config/sites/bad.json: weatherStation"),
        (json.dumps({**DEMO, "siteId": "bad", "primaryTrades": {"x": 1}}), "primaryTrades must be a list"),
        (json.dumps({**DEMO, "siteId": "bad", "primaryTrades": ["紮鐵"]}), "primaryTrades[0] must be an object"),
    ],
)
def test_a_bad_site_file_is_left_out_and_named_and_the_others_still_load(tmp_path, content, message):
    write(tmp_path, "demo-site.json", DEMO)
    (tmp_path / "bad.json").write_text(content, encoding="utf-8")
    sites, default, problems = load_sites(tmp_path)
    assert set(sites) == {"demo-kai-tak"} and default == "demo-kai-tak"
    assert len(problems) == 1 and problems[0].startswith("config/sites/bad.json: ") and message in problems[0]


def test_two_files_with_one_site_id_are_both_left_out(tmp_path):
    write(tmp_path, "demo-site.json", DEMO)
    write(tmp_path, "a.json", {**DEMO, "siteId": "same"})
    write(tmp_path, "b.json", {**DEMO, "siteId": "same", "primaryTrades": []})
    sites, default, problems = load_sites(tmp_path)
    assert set(sites) == {"demo-kai-tak"} and default == "demo-kai-tak"
    assert problems == ["siteId 'same' is in config/sites/a.json, config/sites/b.json; none of them is used"]


def test_a_left_out_file_never_hands_the_default_to_another_site(tmp_path):
    # Two real sites and no demo: losing one file must not make the other site's trades the default.
    write(tmp_path, "a.json", {**DEMO, "siteId": "a", "restAdjustMinutes": 10})
    write(tmp_path, "b.json", {**DEMO, "siteId": "b"})
    sites, default, problems = load_sites(tmp_path)
    assert set(sites) == {"b"} and default is None and len(problems) == 2
    # A bad demo file: screens without ?site= show the generic site, not another site.
    write(tmp_path, "demo-site.json", {**DEMO, "environment": "street"})
    write(tmp_path, "a.json", {**DEMO, "siteId": "a"})
    sites, default, problems = load_sites(tmp_path)
    assert set(sites) == {"a", "b"} and default is None
    assert problems[0].startswith("config/sites/demo-site.json: environment")
    # The only file, and it is bad.
    for name in ("a.json", "b.json"):
        (tmp_path / name).unlink()
    assert load_sites(tmp_path)[:2] == ({}, None)


def test_no_site_file_is_reported(tmp_path):
    assert load_sites(tmp_path) == ({}, None, [f"no site file in {tmp_path}"])


def test_generic_site_shows_every_workload_level():
    validate_site(GENERIC_SITE)
    assert [t["workload"] for t in tile_trades(GENERIC_SITE)] == ["light", "moderate", "heavy", "very_heavy"]


def test_the_shipped_site_folder_loads():
    sites, default, problems = load_sites(ROOT / "config" / "sites")
    assert default == "demo-kai-tak" and sites[default]["windStation"] == "啟德" and problems == []
