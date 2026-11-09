from pathlib import Path

from app.sim_cases import CASE_IDS, SITE, build_case, list_cases, list_official_icons

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
    "amber-new",
    "hsww-cancel-new",
    "tc8ne-new",
    "rain-black-cancel",
    "rain-amber-tc3",
    "trades-indoor",
    "weather-old",
    "forecast-old",
    "tc8-lowered",
    "tc8-all-cancelled",
    "rain-black-lowered",
    "amber-after-tc8",
]


def test_catalog_covers_all_signals():
    ids = [c["id"] for c in list_cases()]
    assert ids == CASE_IDS
    for rid in REQUIRED:
        assert rid in ids


def test_none_is_a_normal_day_with_weather():
    snap = build_case("none")
    assert snap["hsww"]["inForce"] is False
    assert snap["priority"]["band"] == "P4"
    assert snap["tone"] == "idle"
    assert snap["display"]["mode"] == "normal"
    assert snap["hko"]["wxIconRel"] == "official/wxicon/pic51.png"
    assert snap["hko"]["icons"] == []
    assert snap["hko"]["headlineZh"] == ""
    assert snap["site"]["tradeZh"] == "紮鐵"
    assert snap["site"]["workloadZh"] == "極重勞動"


def test_normal_work_uses_idle_tone_even_with_tc1():
    snap = build_case("tc1")
    assert snap["display"]["action"] == "正常工作"
    assert snap["tone"] == "idle"
    assert snap["display"]["heroRel"] == "status/work-ok.png"
    assert (ROOT / "apps/kiosk/public/status/work-ok.png").is_file()


def test_black_rain_caption_not_typhoon():
    snap = build_case("rain-black")
    assert "黑色暴雨" in snap["hko"]["headlineZh"]
    assert "熱帶氣旋" not in snap["hko"]["headlineZh"]
    assert snap["tone"] == "p0-rain"


def test_pre8_has_short_caption():
    snap = build_case("pre8")
    assert snap["priority"]["band"] == "P1"
    assert snap["display"]["action"] == "分批離開工作地點"
    assert "八號" in snap["display"]["actionSub"]
    codes = [s["code"] for s in snap["signals"]]
    assert "WTCPRE8" in codes
    assert "TC3" in codes


def test_winning_weather_action_sets_tone_not_leftover_hsww():
    pre8a = build_case("pre8-amber")
    assert pre8a["display"]["action"] == "分批離開工作地點"
    assert pre8a["tone"] == "p1"
    stack = build_case("typhoon-stack")
    assert stack["display"]["action"] == "停止戶外作業"
    assert stack["tone"] == "p0-rain"


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
    assert build_case("tc8ne")["display"]["action"] == "分批離開工作地點"
    assert build_case("tc9")["display"]["action"] == "切勿外出"
    assert build_case("tc10")["display"]["action"] == "切勿離開有遮蔽的地方"
    assert build_case("rain-black")["display"]["action"] == "停止戶外作業"
    assert "暫避" in build_case("rain-black")["display"]["actionSub"]
    assert build_case("rain-red")["display"]["action"] == "暫停戶外作業"
    assert build_case("landslip")["display"]["action"] == "避免靠近陡峭的斜坡和護土牆"
    assert build_case("tsunami")["display"]["action"] == "遠離岸邊"
    assert build_case("amber")["display"]["action"] == "休息 45 分鐘"
    assert build_case("red")["display"]["action"] == "暫停工作"
    assert build_case("none")["display"]["action"] == "正常工作"
    assert build_case("pre8")["display"]["action"] == "分批離開工作地點"
    for name in ("tc1", "tc3", "rain-amber", "thunderstorm", "vhot"):
        snap = build_case(name)
        assert snap["signals"], name
        assert all(s["impact"] == "low" for s in snap["signals"]), name


def test_site_changing_signals_are_high_impact():
    for name, code in (
        ("amber", "HSWW-amber"),
        ("tc8ne", "TC8NE"),
        ("rain-black", "WRAINB"),
        ("rain-red", "WRAINR"),
        ("pre8", "WTCPRE8"),
        ("tsunami", "WTMW"),
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
    skip_icon = {"none", "stale"}
    for case in list_cases():
        snap = case["snapshot"]
        if case["id"] in skip_icon:
            continue
        rels = []
        if snap["hsww"]["iconRel"]:
            rels.append(snap["hsww"]["iconRel"])
        rels.extend(i["rel"] for i in snap["hko"]["icons"])
        rels.extend(s["rel"] for s in snap.get("signals") or [] if s.get("rel"))
        if snap.get("display", {}).get("heroRel"):
            rels.append(snap["display"]["heroRel"])
        assert rels, case["id"]
        for rel in rels:
            path = PUBLIC / rel
            assert path.is_file(), f"{case['id']} missing {rel}"


def test_display_covers_every_sim_case():
    missing = []
    for case in list_cases():
        snap = case["snapshot"]
        action = (snap.get("display") or {}).get("action")
        if not action:
            missing.append(f"{case['id']}:no-action")
            continue
        if action == "正常工作":
            if snap.get("stale"):
                continue
            if snap["tone"] != "idle":
                missing.append(f"{case['id']}:normal-work-not-idle")
            continue
        highs = [s for s in snap["signals"] if s.get("impact") == "high" and s.get("rel")]
        if not highs and not (snap.get("display") or {}).get("heroRel"):
            missing.append(f"{case['id']}:no-hero")
    assert missing == []


def test_gallery_weather_icons_use_official_names():
    by = {i["code"]: i["labelZh"] for i in list_official_icons() if i["kind"] == "wx"}
    assert len(by) == 29
    assert by["pic50"] == "陽光充沛"
    assert by["pic62"] == "微雨"
    assert by["pic90"] == "熱"


def test_banner_cases():
    amber_new = build_case("amber-new")["banner"]
    assert (amber_new["time"], amber_new["textZh"]) == ("14:42", "黃色工作暑熱警告 生效")
    assert build_case("hsww-cancel-new")["banner"]["textZh"] == "工作暑熱警告 取消"
    assert build_case("tc8ne-new")["banner"]["textZh"] == "八號東北烈風或暴風信號 發出"
    assert build_case("rain-black-cancel")["banner"]["textZh"] == "黑色暴雨警告信號 取消"
    assert build_case("amber")["banner"] is None
    assert build_case("stale")["banner"] is None


def test_weather_freshness_cases():
    none = build_case("none")
    assert none["weather"]["placeZh"] == "香港天文台"
    assert none["forecast"]["date"] == "20260716"
    assert build_case("weather-old")["weather"] is None
    assert build_case("forecast-old")["forecast"] is None


def test_indoor_and_aircon_trades():
    tiles = build_case("trades-indoor")["restTiles"]
    assert [(t["kind"], t["rest"], t["tradesZh"]) for t in tiles] == [
        ("rest", 45, "紮鐵"),
        ("rest", 30, "焊接"),
        ("baseline", 10, "室內裝修 · 電工"),
    ]


def test_two_supervisor_lines():
    lines = build_case("rain-amber-tc3")["supervisor"]
    assert [line["text"] for line in lines] == ["停止操作起重機、吊船", "停止操作吊船、進行斜坡工程"]


def test_pre8_shows_the_signal_in_force():
    assert build_case("pre8-amber")["display"]["heroRel"] == "official/warning/tc3.png"


EN_KEYS = ("en", "metaEn", "notesEn", "textEn", "fromEn")


def without_english(value):
    if isinstance(value, dict):
        return {k: without_english(v) for k, v in value.items() if k not in EN_KEYS}
    if isinstance(value, list):
        return [without_english(v) for v in value]
    return value


def test_english_never_changes_the_chinese_in_any_case():
    chinese_only = {k: v for k, v in SITE.items() if k != "languages"}
    for case_id in CASE_IDS:
        english = without_english(build_case(case_id))
        chinese = build_case(case_id, chinese_only)
        assert english["site"].pop("languages") == ["zh", "en"], case_id
        assert chinese["site"].pop("languages") == ["zh"], case_id
        assert english == chinese, case_id


def test_every_case_has_english_names_and_lines_where_official_ones_exist():
    for case_id in CASE_IDS:
        snap = build_case(case_id)
        display = snap["display"]
        if display["mode"] == "weather":
            assert display["en"] and display["metaEn"], case_id
        elif display["mode"] == "heat":
            assert display["metaEn"] and snap["notesEn"], case_id
            assert all(tile["en"]["lines"] for tile in snap["restTiles"]), case_id
        else:
            assert display["en"] and display["metaEn"] is None, case_id
        for line in snap["supervisor"]:
            assert line["textEn"] and line["fromEn"], case_id


def test_preview_english_names_follow_the_live_feed_shape():
    assert build_case("rain-black")["display"]["metaEn"] == "Black Rainstorm Warning Signal"
    assert build_case("tc9")["display"]["metaEn"] == "Increasing Gale or Storm Signal No. 9"
    lines = build_case("rain-amber-tc3")["supervisor"]
    assert [line["fromEn"] for line in lines] == ["Strong Wind Signal No. 3", "Amber Rainstorm Warning Signal"]
    assert build_case("trades-indoor")["restTiles"][0]["en"]["trades"] == "Bar-fixing worker"



REMAIN_VIGILANT = "留意天氣信息，保持高度警覺：可能仍持續影響工作安全"


def after_line(case_id):
    return next((line for line in build_case(case_id)["supervisor"] if line.get("whenZh")), None)


def test_after_signal_8_or_black_rain_ends_supervisors_are_reminded():
    tc3 = build_case("tc8-lowered")
    assert tc3["display"]["main"] == "正常工作"
    assert [line["text"] for line in tc3["supervisor"]] == ["停止操作起重機、吊船", REMAIN_VIGILANT]
    assert after_line("tc8-lowered") == {
        "text": REMAIN_VIGILANT,
        "fromZh": "八號東北烈風或暴風信號",
        "whenZh": "14:00 改發較低警告信號",
        "textEn": tc3["supervisor"][1]["textEn"],
        "fromEn": "No. 8 Northeast Gale or Storm Signal",
    }
    cancelled = build_case("tc8-all-cancelled")
    assert cancelled["signals"] == []
    assert [(line["fromZh"], line["whenZh"]) for line in cancelled["supervisor"]] == [
        ("八號東南烈風或暴風信號", "09:45 改發較低警告信號")
    ]
    rain = build_case("rain-black-lowered")
    assert [line["text"] for line in rain["supervisor"]] == ["停止操作吊船、進行斜坡工程", REMAIN_VIGILANT]
    assert (after_line("rain-black-lowered")["fromZh"], after_line("rain-black-lowered")["whenZh"]) == (
        "黑色暴雨警告信號",
        "13:15 改發較低警告信號",
    )


def test_a_black_rain_cancellation_hko_still_lists_is_read_without_memory():
    line = after_line("rain-black-cancel")
    assert (line["fromZh"], line["whenZh"]) == ("黑色暴雨警告信號", "14:42 取消")


def test_the_reminder_shows_with_the_heat_tiles_and_the_day_it_ended():
    snap = build_case("amber-after-tc8")
    assert snap["display"]["mode"] == "heat" and snap["restTiles"]
    assert after_line("amber-after-tc8")["whenZh"] == "7月14日 18:45 改發較低警告信號"


def test_the_reminder_never_replaces_an_instruction_in_force():
    for case_id in ("rain-black", "rain-red", "tc8ne", "typhoon-stack", "landslip"):
        assert build_case(case_id)["supervisor"] == [], case_id
    for case_id in CASE_IDS:
        snap = build_case(case_id)
        if after_line(case_id):
            assert snap["display"]["mode"] in ("normal", "heat"), case_id
            assert snap["supervisor"][-1]["whenZh"], case_id
