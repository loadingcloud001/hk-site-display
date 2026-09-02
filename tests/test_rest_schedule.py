import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    return json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))


def test_outdoor_very_heavy_amber_is_45():
    s = load()["outdoor"]["amber"]["very_heavy"]
    assert s == {"work": 15, "rest": 45, "suspend": False}


def test_outdoor_light_amber_no_extra():
    s = load()["outdoor"]["amber"]["light"]
    assert s == {"work": 60, "rest": 0, "suspend": False}


def test_outdoor_very_heavy_red_suspends():
    assert load()["outdoor"]["red"]["very_heavy"]["suspend"] is True


def test_outdoor_heavy_black_suspends():
    assert load()["outdoor"]["black"]["heavy"]["suspend"] is True
