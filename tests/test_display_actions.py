import copy

import pytest

from app.actions import fragment_errors, load_actions, note_text, validate_actions, weather_by_code

ACTIONS = load_actions()


def test_every_displayed_fragment_is_official_wording():
    assert fragment_errors(ACTIONS) == []


def test_paraphrase_is_rejected():
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["tc8"]["main"] = "留在室內"
    assert any("留在室內" in e for e in fragment_errors(bad))
    with pytest.raises(ValueError):
        validate_actions(bad)


def test_unknown_source_is_rejected():
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["rain-black"]["quotes"][0]["source"] = "blog"
    assert any("unknown source" in e for e in fragment_errors(bad))


def test_weather_codes_map_to_entries():
    by = weather_by_code(ACTIONS)
    assert by["TC8SW"]["main"] == "分批離開工作地點"
    assert by["WTCPRE8"]["sub"] == []
    assert by["WRAINR"]["sub"] == ["直至天氣情況許可為止"]


def test_note_text_joins_fragments():
    assert note_text(ACTIONS, "heatUnacclimatised") == (
        "僱員未適應或需重新適應在酷熱環境中工作：每小時的休息時間應增加15分鐘"
    )


def test_extreme_conditions_wording_is_verbatim_from_the_code_of_practice():
    from app.actions import extreme_wording

    spec = ACTIONS["extreme"]
    assert {q["source"] for part in spec.values() for q in part["quotes"]} == {"ld-cop-weather"}
    assert extreme_wording(ACTIONS) == {
        "main": "留在原來的地點或安全的地點",
        "sub": ["而非立即啟程往工作地點上班"],
        "supervisor": "立即暫停僱員在戶外及空曠地方的工作，並安排僱員到安全地方暫避",
    }
    assert spec["display"]["quotes"][0]["text"] == "在公布的指定期間留在原來的地點或安全的地點，而非立即啟程往工作地點上班。"
    assert spec["supervisor"]["quotes"][0]["text"] == "主管應立即暫停僱員在戶外及空曠地方的工作，並安排僱員到安全地方暫避。"


@pytest.mark.parametrize(
    ("part", "field", "value"),
    [
        ("display", "main", "留在安全的地點"),
        ("display", "sub", ["不要上班"]),
        ("supervisor", "fragments", ["暫停戶外工作"]),
    ],
)
def test_extreme_conditions_paraphrase_is_rejected(part, field, value):
    bad = copy.deepcopy(ACTIONS)
    bad["extreme"][part][field] = value
    assert any(e.startswith(f"extreme.{part}:") for e in fragment_errors(bad))
    with pytest.raises(ValueError):
        validate_actions(bad)


def test_a_section_the_check_does_not_know_is_rejected():
    bad = copy.deepcopy(ACTIONS)
    bad["announcements"] = {"x": {"main": "停工", "quotes": []}}
    assert any("announcements: unknown section" in e for e in fragment_errors(bad))


def test_every_section_with_wording_is_checked():
    from app.actions import SECTIONS

    assert set(ACTIONS) - {"sources"} == set(SECTIONS)
    for section in SECTIONS:
        for key in ACTIONS[section]:
            bad = copy.deepcopy(ACTIONS)
            bad[section][key]["quotes"] = [{"source": "ld-cop-weather", "text": "完全無關的句子。"}]
            assert any(e.startswith(f"{section}.{key}:") for e in fragment_errors(bad)), f"{section}.{key}"
