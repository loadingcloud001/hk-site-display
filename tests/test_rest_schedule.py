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


# Labour Department guidance notes, 3rd edition (revised) Aug 2026.
# (work, rest) per hour; "S" = 暫停工作; None = no hourly rest arrangement.
APPENDIX_4 = {
    "amber": {"light": None, "moderate": (45, 15), "heavy": (30, 30), "very_heavy": (15, 45)},
    "red": {"light": (45, 15), "moderate": (30, 30), "heavy": (15, 45), "very_heavy": "S"},
    "black": {"light": (30, 30), "moderate": (15, 45), "heavy": "S", "very_heavy": "S"},
}
APPENDIX_4A = {
    "amber": {"light": None, "moderate": None, "heavy": (45, 15), "very_heavy": (30, 30)},
    "red": {"light": None, "moderate": (45, 15), "heavy": (30, 30), "very_heavy": (15, 45)},
    "black": {"light": (45, 15), "moderate": (30, 30), "heavy": (15, 45), "very_heavy": "S"},
}


def cell_view(rest):
    if rest >= 60:
        return "S"
    if rest <= 0:
        return None
    return (60 - rest, rest)


def test_outdoor_matches_appendix_4():
    s = load()
    for level, row in APPENDIX_4.items():
        for workload, want in row.items():
            cell = s["outdoor"][level][workload]
            assert cell_view(cell["rest"]) == want, (level, workload)
            if isinstance(want, tuple):
                assert cell["work"] == want[0], (level, workload)


def test_indoor_adjustment_reproduces_appendix_4a():
    s = load()
    adjust = s["environmentAdjust"]["indoor"]
    assert s["environmentAdjust"]["outdoor"] == 0
    for level, row in APPENDIX_4A.items():
        for workload, want in row.items():
            assert cell_view(s["outdoor"][level][workload]["rest"] + adjust) == want, (level, workload)


def test_suspend_flag_matches_rest():
    s = load()
    for level in ("amber", "red", "black"):
        for workload, cell in s["outdoor"][level].items():
            assert cell["suspend"] is (cell["rest"] >= 60), (level, workload)


def test_baseline_matches_para_4_7_1():
    assert load()["baseline"] == {"light": 10, "moderate": 10, "heavy": 15, "very_heavy": 15, "perHours": 2}
