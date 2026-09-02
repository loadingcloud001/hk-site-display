from pathlib import Path

from app.sim_cases import CASE_IDS, build_case, list_cases

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps" / "kiosk" / "public"

REQUIRED = [
    "none",
    "amber",
    "red",
    "black",
    "tc1",
    "tc3",
    "tc8ne",
    "tc8se",
    "tc8nw",
    "tc8sw",
    "tc9",
    "tc10",
    "rain-amber",
    "rain-red",
    "rain-black",
    "thunderstorm",
    "landslip",
    "vhot",
    "monsoon",
    "pre8",
    "amber-tc1",
    "stale",
]


def test_catalog_covers_all_signals():
    ids = [c["id"] for c in list_cases()]
    assert ids == CASE_IDS
    for rid in REQUIRED:
        assert rid in ids


def test_none_is_idle_without_white_weather_tile():
    snap = build_case("none")
    assert snap["hsww"]["inForce"] is False
    assert snap["priority"]["band"] == "P4"
    assert snap["tone"] == "idle"
    assert snap["hko"]["wxIconRel"] is None
    assert snap["hko"]["icons"] == []
    assert snap["hko"]["headlineZh"] == ""


def test_black_rain_caption_not_typhoon():
    snap = build_case("rain-black")
    assert "黑色暴雨" in snap["hko"]["headlineZh"]
    assert "熱帶氣旋" not in snap["hko"]["headlineZh"]
    assert snap["tone"] == "p0-rain"


def test_pre8_has_short_caption():
    snap = build_case("pre8")
    assert snap["priority"]["band"] == "P1"
    assert "八號" in snap["hko"]["headlineZh"]
    assert snap["hko"]["headlineZh"] != "香港天文台發出最新熱帶氣旋警報"


def test_warning_cases_point_at_real_official_files():
    skip_icon = {"none", "stale", "pre8"}
    for case in list_cases():
        snap = case["snapshot"]
        if case["id"] in skip_icon:
            continue
        rels = []
        if snap["hsww"]["iconRel"]:
            rels.append(snap["hsww"]["iconRel"])
        rels.extend(i["rel"] for i in snap["hko"]["icons"])
        assert rels, case["id"]
        for rel in rels:
            path = PUBLIC / rel
            assert path.is_file(), f"{case['id']} missing {rel}"
