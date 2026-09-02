import json
from pathlib import Path

from app.rest import lookup

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))


def test_amber_very_heavy():
    r = lookup(SCHEDULE, "outdoor", "amber", "very_heavy")
    assert r["work"] == 15 and r["rest"] == 45 and r["suspend"] is False


def test_red_very_heavy_suspends():
    r = lookup(SCHEDULE, "outdoor", "red", "very_heavy")
    assert r["suspend"] is True and r["work"] == 0


def test_none_very_heavy_two_hours():
    r = lookup(SCHEDULE, "outdoor", "none", "very_heavy")
    assert r["perHours"] == 2 and r["rest"] == 15
