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
