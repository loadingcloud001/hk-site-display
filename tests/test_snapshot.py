import json
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
