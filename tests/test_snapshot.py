import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.hsww import parse_hkhi_icon
from app.snapshot import build_snapshot

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
    assert snap["supervisor"] == [{"text": "停止操作起重機、吊船", "fromZh": "三號強風信號"}]
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
    assert snap["weather"]["placeZh"] == "觀塘" and snap["weather"]["tempC"] == 28
    assert snap["forecast"]["date"] == "20261007"
    assert snap["banner"] is None


def test_banner_shows_then_hides_when_stale():
    now = datetime(2024, 7, 14, 14, 45, tzinfo=HKT)
    assert build(hsww_raw=load("hsww_amber_inforce.json"), now=now)["banner"]["textZh"] == "黃色工作暑熱警告 生效"
    assert build(hsww_raw=load("hsww_amber_inforce.json"), now=now, stale=True)["banner"] is None
