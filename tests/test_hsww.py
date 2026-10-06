import json
from pathlib import Path

from app.hsww import effective_time, message_kind, parse_hkhi_icon

FIX = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_amber_in_force():
    g = parse_hkhi_icon(load("hsww_amber_inforce.json"))
    assert g["level"] == "amber" and g["inForce"] is True
    assert g["iconRel"] == "official/hkhi_yellow.png"


def test_stale_cancel_hidden():
    g = parse_hkhi_icon(load("hsww_cancelled_stale.json"))
    assert g["inForce"] is False and g["level"] == "none"


def test_title_must_not_override_iconindex():
    g = parse_hkhi_icon({"iconIndex": -1, "TitleTC": "黃色工作暑熱警告"})
    assert g["level"] == "none"


def test_red_and_black_from_iconindex():
    assert parse_hkhi_icon(load("hsww_red_synth.json"))["level"] == "red"
    assert parse_hkhi_icon(load("hsww_black_synth.json"))["level"] == "black"


def test_minus2_not_in_force():
    g = parse_hkhi_icon(load("hsww_iconindex_minus2.json"))
    assert g["inForce"] is False
    assert g["iconRel"] is None


def test_message_kinds_follow_ld_templates():
    assert message_kind("黃色工作暑熱警告在今日下午2時40分生效，表示部分工作環境下的熱壓力頗高，請採取適當的防暑措施。") == "issue"
    assert message_kind("黃色工作暑熱警告在今日下午3時40分仍然生效，表示部分工作環境下的熱壓力頗高，請採取適當的防暑措施。") == "update"
    assert message_kind("工作暑熱警告在今日下午6時30分取消。") == "cancel"
    assert message_kind("請採取適當的防暑措施。") == "other"


def test_effective_time_from_message():
    assert effective_time("黃色工作暑熱警告在今日下午2時40分生效。", "202407141435").isoformat() == "2024-07-14T14:40:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日上午11時5分生效。", "202407141100").isoformat() == "2024-07-14T11:05:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日中午12時正生效。", "202407141155").isoformat() == "2024-07-14T12:00:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日下午12時15分生效。", "202407141210").isoformat() == "2024-07-14T12:15:00+08:00"


def test_effective_time_falls_back_to_message_time():
    assert effective_time("請採取適當的防暑措施。", "202608011400").isoformat() == "2026-08-01T14:00:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日下午2時40分生效。", "") is None


def test_parse_adds_kind_and_effective_time():
    amber = parse_hkhi_icon(load("hsww_amber_inforce.json"))
    assert amber["messageKind"] == "issue"
    assert amber["effectiveAt"] == "2024-07-14T14:40:00+08:00"
    cancelled = parse_hkhi_icon(load("hsww_cancelled_stale.json"))
    assert cancelled["messageKind"] == "cancel"
    assert cancelled["effectiveAt"] == "2026-08-29T18:50:00+08:00"
