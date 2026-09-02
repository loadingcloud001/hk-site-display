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
    "amber-vhot",
    "amber-ts",
    "amber-tc3",
    "tc8-amber",
    "typhoon-stack",
    "rain-black-amber",
    "pre8-amber",
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
    assert snap["site"]["tradeZh"] == "紮鐵"
    assert snap["site"]["workloadZh"] == "極重勞動"


def test_normal_work_uses_idle_tone_even_with_tc1():
    snap = build_case("tc1")
    assert snap["display"]["action"] == "正常工作"
    assert snap["tone"] == "idle"
    assert snap["display"]["heroRel"] == "status/work-ok.svg"
    assert (ROOT / "apps/kiosk/public/status/work-ok.svg").is_file()


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


def test_amber_plus_tc1_keeps_rest_and_both_signals():
    snap = build_case("amber-tc1")
    codes = [s["code"] for s in snap["signals"]]
    assert snap["rest"]["rest"] == 45
    assert snap["hsww"]["inForce"] is True
    assert "HSWW-amber" in codes
    assert "TC1" in codes


def test_tc8_plus_amber_is_stop_with_hsww_still_listed():
    snap = build_case("tc8-amber")
    codes = [s["code"] for s in snap["signals"]]
    assert snap["priority"]["band"] == "P0"
    assert codes[0] == "TC8NE"
    assert "HSWW-amber" in codes


def test_official_display_actions():
    assert build_case("tc8ne")["display"]["action"] == "留在室內"
    assert build_case("tc9")["display"]["action"] == "切勿外出"
    assert build_case("rain-black")["display"]["action"] == "暫停戶外工作"
    assert "暫避" in build_case("rain-black")["display"]["actionSub"]
    assert build_case("landslip")["display"]["action"] == "遠離斜坡"
    assert build_case("amber")["display"]["action"] == "休息 45 分鐘"
    assert build_case("red")["display"]["action"] == "暫停工作"
    assert build_case("none")["display"]["action"] == "正常工作"
    for name in ("tc1", "tc3", "rain-amber", "thunderstorm", "vhot", "pre8"):
        snap = build_case(name)
        assert snap["signals"], name
        assert all(s["impact"] == "low" for s in snap["signals"]), name


def test_site_changing_signals_are_high_impact():
    for name, code in (
        ("amber", "HSWW-amber"),
        ("tc8ne", "TC8NE"),
        ("rain-black", "WRAINB"),
        ("rain-red", "WRAINR"),
        ("landslip", "WL"),
    ):
        snap = build_case(name)
        hit = next(s for s in snap["signals"] if s["code"] == code)
        assert hit["impact"] == "high", name


def test_amber_tc1_splits_impact():
    snap = build_case("amber-tc1")
    by = {s["code"]: s["impact"] for s in snap["signals"]}
    assert by["HSWW-amber"] == "high"
    assert by["TC1"] == "low"


def test_typhoon_stack_lists_every_sign():
    snap = build_case("typhoon-stack")
    assert [s["code"] for s in snap["signals"]] == [
        "TC8NE",
        "WRAINB",
        "WL",
        "HSWW-amber",
    ]
    assert all(s["impact"] == "high" for s in snap["signals"])


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
