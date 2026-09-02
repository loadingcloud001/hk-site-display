import json
from pathlib import Path

from app.hsww import parse_hkhi_icon

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
