import json
from pathlib import Path

from app.actions import load_actions
from app.heat import build_rest_tiles, normal_rest_lines, trades_label
from app.site import configured_trades, tile_trades

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
DEMO = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))


def view(tiles):
    return [(t["kind"], t["rest"], t["tradesZh"]) for t in tiles]


def test_amber_demo_site_tiles():
    tiles = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "amber")
    assert view(tiles) == [
        ("rest", 45, "紮鐵 · 棚架"),
        ("rest", 30, "釘板 · 混凝土"),
        ("rest", 15, "水喉 · 焊接"),
        ("baseline", 10, "保安 · 檢查"),
    ]
    assert tiles[0]["work"] == 15 and tiles[0]["perHours"] == 1
    assert tiles[3]["work"] is None and tiles[3]["perHours"] == 2


def test_red_suspends_very_heavy_first():
    tiles = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "red")
    assert view(tiles)[0] == ("suspend", 60, "紮鐵 · 棚架")
    assert [t["rest"] for t in tiles] == [60, 45, 30, 15]


def test_black_merges_heavy_and_very_heavy_into_one_stop_tile():
    tiles = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "black")
    assert view(tiles) == [
        ("suspend", 60, "紮鐵 · 棚架 · 釘板 +1"),
        ("rest", 45, "水喉 · 焊接"),
        ("rest", 30, "保安 · 檢查"),
    ]
    assert tiles[0]["trades"] == ["紮鐵", "棚架", "釘板", "混凝土"]


def test_tiles_without_trades_use_workload_labels():
    tiles = build_rest_tiles(SCHEDULE, tile_trades({"environment": "outdoor"}), "amber")
    assert view(tiles) == [
        ("rest", 45, "極重勞動"),
        ("rest", 30, "重勞動"),
        ("rest", 15, "中等勞動"),
        ("baseline", 10, "輕勞動"),
    ]


def test_baseline_tiles_order_fifteen_before_ten():
    trades = [
        {"labelZh": "A", "workload": "light", "environment": "aircon", "adjustMinutes": 0},
        {"labelZh": "B", "workload": "heavy", "environment": "aircon", "adjustMinutes": 0},
    ]
    assert view(build_rest_tiles(SCHEDULE, trades, "black")) == [("baseline", 15, "B"), ("baseline", 10, "A")]


def test_at_most_six_tiles():
    trades = [
        {"labelZh": f"{wl}-{env}-{adj}", "workload": wl, "environment": env, "adjustMinutes": adj}
        for wl in ("light", "moderate", "heavy", "very_heavy")
        for env in ("outdoor", "indoor", "aircon")
        for adj in (-30, -15, 0, 15, 30, 45, 60)
    ]
    for level in ("amber", "red", "black"):
        assert len(build_rest_tiles(SCHEDULE, trades, level)) <= 6


def test_trades_label_truncates_after_three():
    assert trades_label(["a", "b"]) == "a · b"
    assert trades_label(["a", "b", "c", "d", "e"]) == "a · b · c +2"


def test_normal_day_lines():
    assert normal_rest_lines(SCHEDULE, {"very_heavy"}) == ["每 2 小時休息 15 分鐘"]
    assert normal_rest_lines(SCHEDULE, {"light", "moderate"}) == ["每 2 小時休息 10 分鐘"]
    assert normal_rest_lines(SCHEDULE, {"light", "heavy"}) == [
        "重至極重勞動：每 2 小時休息 15 分鐘",
        "輕至中等勞動：每 2 小時休息 10 分鐘",
    ]


REST_EN = load_actions()["rest"]


def english(tiles):
    return [(t["en"]["trades"], t["en"]["lines"]) for t in tiles]


def test_tiles_carry_their_official_english_on_sites_that_show_it():
    assert all("en" not in t for t in build_rest_tiles(SCHEDULE, configured_trades(DEMO), "amber"))
    tiles = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "amber", REST_EN)
    assert english(tiles) == [
        ("Bar-fixing worker · Scaffolder", ["45 mins rest", "15 mins work"]),
        ("Carpenter · Concrete worker", ["30 mins rest", "30 mins work"]),
        ("Plumber · Welder", ["15 mins rest", "45 mins work"]),
        ("Security guard · Inspector of works", ["at least 10 minutes of rest for every 2 hours of work"]),
    ]
    black = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "black", REST_EN)
    assert english(black)[0] == ("Bar-fixing worker · Scaffolder · Carpenter +1", ["Suspension of work"])


def test_generic_tiles_use_the_official_english_workload_levels():
    tiles = build_rest_tiles(SCHEDULE, tile_trades({"environment": "outdoor"}), "red", REST_EN)
    assert [t["en"]["trades"] for t in tiles] == ["Very Heavy", "Heavy", "Moderate", "Light"]


def test_a_tile_shows_english_names_only_when_every_trade_has_one():
    trades = [
        {"labelZh": "紮鐵", "labelEn": "Bar-fixing worker", "workload": "very_heavy", "environment": "outdoor", "adjustMinutes": 0},
        {"labelZh": "外牆", "workload": "very_heavy", "environment": "outdoor", "adjustMinutes": 0},
    ]
    (tile,) = build_rest_tiles(SCHEDULE, trades, "amber", REST_EN)
    assert tile["tradesZh"] == "紮鐵 · 外牆" and tile["en"] == {"trades": None, "lines": ["45 mins rest", "15 mins work"]}
