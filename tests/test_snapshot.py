import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.hsww import parse_hkhi_icon
from app.snapshot import build_snapshot
from app.stations import Position

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_amber_plus_tc1_is_p3():
    site = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))
    schedule = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
    icons = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
    snap = build_snapshot(
        hsww_raw=load("hsww_amber_inforce.json"),
        warnsum=load("warnsum_tc1.json"),
        warning_info=load("warningInfo_tc1.json"),
        rhrread={"icon": [60]},
        site=site,
        schedule=schedule,
        icons_map=icons,
    )
    assert snap["hsww"]["level"] == "amber"
    assert snap["hsww"]["inForce"] is True
    assert snap["priority"]["band"] == "P3"
    assert snap["rest"]["rest"] == 45
    assert any(i["code"] == "TC1" for i in snap["hko"]["icons"])


def test_stale_cancel_not_in_force():
    site = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))
    schedule = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
    icons = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
    snap = build_snapshot(
        hsww_raw=load("hsww_cancelled_stale.json"),
        warnsum={},
        warning_info={},
        rhrread={},
        site=site,
        schedule=schedule,
        icons_map=icons,
    )
    assert snap["hsww"]["inForce"] is False
    assert snap["priority"]["band"] == "P4"


def test_workload_labels_are_official():
    from app.snapshot import WORKLOAD_ZH

    assert WORKLOAD_ZH == {
        "light": "輕勞動",
        "moderate": "中等勞動",
        "heavy": "重勞動",
        "very_heavy": "極重勞動",
    }


HKT = timezone(timedelta(hours=8))
SITE = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
T8_NE = {"WTCSGNL": {"name": "熱帶氣旋警告信號", "code": "TC8NE", "type": "八號東北烈風或暴風信號",
                     "actionCode": "ISSUE", "issueTime": "2026-09-14T15:30:00+08:00"}}
T3 = {"WTCSGNL": {"name": "熱帶氣旋警告信號", "code": "TC3", "type": "三號強風信號", "actionCode": "ISSUE"}}


def build(**overrides):
    args = {
        "hsww_raw": load("hsww_cancelled_stale.json"), "warnsum": {}, "warning_info": {}, "rhrread": {},
        "site": SITE, "schedule": SCHEDULE, "icons_map": ICONS,
    }
    args.update(overrides)
    return build_snapshot(**args)


def test_heat_state_has_tiles_note_and_meta():
    snap = build(hsww_raw=load("hsww_amber_inforce.json"))
    assert snap["display"]["mode"] == "heat"
    assert snap["display"]["meta"] == "黃色工作暑熱警告 · 14:40 生效"
    assert snap["display"]["heroRel"] == "official/hkhi_yellow.png"
    assert [t["rest"] for t in snap["restTiles"]] == [45, 30, 15, 10]
    assert snap["notes"] == ["僱員未適應或需重新適應在酷熱環境中工作：每小時的休息時間應增加15分鐘"]
    assert snap["tone"] == "amber"
    assert snap["display"]["action"] == "休息 45 分鐘"


def test_normal_state_lines_and_t3_supervisor_line():
    snap = build(warnsum=T3)
    assert snap["display"]["mode"] == "normal"
    assert snap["display"]["sub"] == ["重至極重勞動：每 2 小時休息 15 分鐘", "輕至中等勞動：每 2 小時休息 10 分鐘"]
    assert [(s["text"], s["fromZh"]) for s in snap["supervisor"]] == [("停止操作起重機、吊船", "三號強風信號")]
    assert snap["tone"] == "idle"


def test_weather_state_official_words_and_meta():
    snap = build(warnsum=T8_NE, hsww_raw=load("hsww_amber_inforce.json"))
    d = snap["display"]
    assert (d["mode"], d["main"], d["sub"]) == ("weather", "分批離開工作地點", ["如情況許可，市民應盡早回家"])
    assert d["meta"] == "八號東北烈風或暴風信號 · 15:30 發出"
    assert d["heroRel"] == "official/warning/tc8ne.png"
    assert snap["restTiles"] == [] and snap["supervisor"] == []
    assert snap["tone"] == "p0-tc"


def test_pre8_hero_is_the_signal_in_force():
    snap = build(warnsum=load("warnsum_tc1.json"), warning_info=load("warningInfo_pre8.json"))
    assert snap["display"]["main"] == "分批離開工作地點"
    assert snap["display"]["heroRel"] == "official/warning/tc1.png"
    assert snap["display"]["meta"] == "預警八號熱帶氣旋警告信號之特別報告"
    assert all(s["rel"] != "status/pre8.png" for s in snap["signals"])


def test_weather_and_forecast_fields():
    now = datetime(2026, 10, 6, 17, 30, tzinfo=HKT)
    snap = build(rhrread=load("rhrread_sample.json"), fnd=load("fnd_sample.json"), now=now)
    assert snap["weather"]["placeZh"] == "香港天文台" and snap["weather"]["tempC"] == 27
    assert snap["weather"]["humidity"] == 62
    assert snap["forecast"]["date"] == "20261007"
    assert snap["banner"] is None


def test_weather_station_follows_position_then_site_then_observatory():
    now = datetime(2026, 10, 6, 21, 30, tzinfo=HKT)
    full = load("rhrread_full.json")
    assert build(rhrread=full, now=now)["weather"]["placeZh"] == "香港天文台"
    assert build(rhrread=full, now=now, site={**SITE, "weatherStation": "沙田"})["weather"]["placeZh"] == "沙田"
    kwun_tong = Position(22.3125, 114.2260, 60)
    near = build(rhrread=full, now=now, site={**SITE, "weatherStation": "沙田"}, position=kwun_tong)
    assert (near["weather"]["placeZh"], near["weather"]["tempC"]) == ("觀塘", 25)


def test_banner_shows_then_hides_when_stale():
    now = datetime(2024, 7, 14, 14, 45, tzinfo=HKT)
    assert build(hsww_raw=load("hsww_amber_inforce.json"), now=now)["banner"]["textZh"] == "黃色工作暑熱警告 生效"
    assert build(hsww_raw=load("hsww_amber_inforce.json"), now=now, stale=True)["banner"] is None


def test_rainstorm_meta_and_supervisor_source_name_the_whole_warning():
    black = build(warnsum=load("warnsum_wrainb.json"))
    assert black["display"]["main"] == "停止戶外作業"
    assert black["display"]["meta"] == "黑色暴雨警告信號 · 00:05 發出"
    assert black["hko"]["headlineZh"] == "黑色暴雨警告信號"
    amber = build(warnsum={"WRAIN": {"name": "暴雨警告信號", "code": "WRAINA", "type": "黃色", "actionCode": "ISSUE"}})
    assert [(s["text"], s["fromZh"]) for s in amber["supervisor"]] == [("停止操作吊船、進行斜坡工程", "黃色暴雨警告信號")]


# English: only for a site whose file asks for it, and never instead of the Chinese.
ZH_SITE = {k: v for k, v in SITE.items() if k != "languages"}
T8_NE_EN = {"WTCSGNL": {"name": "Tropical Cyclone Warning Signal", "code": "TC8NE",
                        "type": "No. 8 Northeast Gale or Storm Signal", "actionCode": "ISSUE"}}
EN_KEYS = ("en", "metaEn", "notesEn", "textEn", "fromEn")


def has_english(value):
    if isinstance(value, dict):
        return any(k in EN_KEYS for k in value) or any(has_english(v) for v in value.values())
    if isinstance(value, list):
        return any(has_english(v) for v in value)
    return False


def test_a_chinese_only_site_gets_no_english_fields():
    for overrides in ({"warnsum": T8_NE}, {"hsww_raw": load("hsww_amber_inforce.json")}, {"warnsum": T3}):
        snap = build(site=ZH_SITE, warnsum_en=T8_NE_EN, **overrides)
        assert snap["site"]["languages"] == ["zh"] and not has_english(snap), overrides


def test_weather_state_english_lines_and_hko_english_name():
    snap = build(warnsum=T8_NE, warnsum_en=T8_NE_EN)
    d = snap["display"]
    assert snap["site"]["languages"] == ["zh", "en"]
    assert d["en"] == [
        "employees should be released from workplaces or from work by batches",
        "Return home as soon as possible if conditions so permit",
    ]
    assert d["metaEn"] == "No. 8 Northeast Gale or Storm Signal"
    assert (d["main"], d["meta"]) == ("分批離開工作地點", "八號東北烈風或暴風信號 · 15:30 發出")


def test_no_english_name_rather_than_a_guess():
    # The English feed has not caught up (or failed): the screen shows no English name, never a translation.
    snap = build(warnsum=T8_NE, warnsum_en={})
    assert snap["display"]["metaEn"] is None and snap["display"]["en"]
    other = build(warnsum=T8_NE, warnsum_en={"WTCSGNL": {**T8_NE_EN["WTCSGNL"], "code": "TC3", "type": "Strong Wind Signal No. 3"}})
    assert other["display"]["metaEn"] is None


def test_pre8_english_name_is_hkos_official_one():
    snap = build(warnsum=load("warnsum_tc1.json"), warning_info=load("warningInfo_pre8.json"))
    assert snap["display"]["metaEn"] == "Pre-no.8 Special Announcement"
    assert snap["display"]["en"] == ["employees should be released from workplaces or from work by batches"]


def test_heat_state_english_tiles_title_and_note():
    snap = build(hsww_raw=load("hsww_amber_inforce.json"))
    assert snap["display"]["en"] == [] and snap["display"]["metaEn"] == "Amber Heat Stress at Work Warning"
    assert snap["restTiles"][0]["en"] == {"trades": "Bar-fixing worker · Scaffolder", "lines": ["45 mins rest", "15 mins work"]}
    assert snap["notesEn"] == [
        "employees are unacclimatised or need to re-acclimate to hot work environment: "
        "increase the hourly rest time for such employees by 15 minutes"
    ]


def test_normal_state_english_has_the_rest_lines_but_no_made_up_heading():
    snap = build(warnsum=T3, warnsum_en={"WTCSGNL": {"name": "Tropical Cyclone Warning Signal", "code": "TC3",
                                                    "type": "Strong Wind Signal No. 3", "actionCode": "ISSUE"}})
    d = snap["display"]
    assert d["main"] == "正常工作" and d["metaEn"] is None  # 正常工作 has no official English
    assert d["en"] == [
        "heavy to very heavy levels of physical work: at least a 15-minute rest break after every 2 hours of work",
        "light to moderate levels of physical work: a minimum of a 10-minute rest break after every 2 hours of work",
    ]
    assert snap["supervisor"] == [{
        "text": "停止操作起重機、吊船", "fromZh": "三號強風信號",
        "textEn": "Stop the operation of cranes, suspended working platforms, etc.", "fromEn": "Strong Wind Signal No. 3",
    }]
    assert "notesEn" not in snap or snap["notesEn"] == []
