import json
from pathlib import Path

from app.rest import compute_rest, lookup

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


def test_compute_amber_outdoor_very_heavy():
    assert compute_rest(SCHEDULE, "outdoor", "amber", "very_heavy") == {
        "kind": "rest", "rest": 45, "work": 15, "perHours": 1
    }


def test_compute_zero_rest_falls_back_to_two_hour_baseline():
    assert compute_rest(SCHEDULE, "outdoor", "amber", "light") == {
        "kind": "baseline", "rest": 10, "work": None, "perHours": 2
    }
    assert compute_rest(SCHEDULE, "outdoor", "amber", "heavy", -30) == {
        "kind": "baseline", "rest": 15, "work": None, "perHours": 2
    }


def test_compute_suspends_at_sixty():
    assert compute_rest(SCHEDULE, "outdoor", "red", "very_heavy")["kind"] == "suspend"
    assert compute_rest(SCHEDULE, "outdoor", "amber", "very_heavy", 15) == {
        "kind": "suspend", "rest": 60, "work": 0, "perHours": 1
    }


def test_compute_indoor_is_fifteen_less():
    assert compute_rest(SCHEDULE, "indoor", "red", "very_heavy") == {
        "kind": "rest", "rest": 45, "work": 15, "perHours": 1
    }
    assert compute_rest(SCHEDULE, "indoor", "black", "very_heavy")["kind"] == "suspend"


def test_compute_shaded_black_very_heavy_still_suspends():
    # Shelter (-15) on outdoor Black very heavy equals indoor work: Appendix 4(a) suspends it.
    assert compute_rest(SCHEDULE, "outdoor", "black", "very_heavy", -15)["kind"] == "suspend"
    assert compute_rest(SCHEDULE, "outdoor", "black", "very_heavy", -30) == {
        "kind": "rest", "rest": 45, "work": 15, "perHours": 1
    }


def test_compute_aircon_and_no_warning_use_baseline():
    assert compute_rest(SCHEDULE, "aircon", "black", "very_heavy")["kind"] == "baseline"
    assert compute_rest(SCHEDULE, "outdoor", "none", "moderate") == {
        "kind": "baseline", "rest": 10, "work": None, "perHours": 2
    }
