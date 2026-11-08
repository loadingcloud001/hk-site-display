import copy

import pytest

from app.actions import (
    EN_JOIN,
    english_lines,
    fragment_errors,
    load_actions,
    load_schedule,
    normal_lines_en,
    note_text,
    note_text_en,
    tile_lines_en,
    tile_results,
    validate_actions,
    weather_by_code,
)

ACTIONS = load_actions()
SCHEDULE = load_schedule()


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


# English: the official English version of each sentence, verbatim, from an English source.


def test_every_source_says_its_language():
    assert {source["lang"] for source in ACTIONS["sources"].values()} == {"zh", "en"}
    bad = copy.deepcopy(ACTIONS)
    del bad["sources"]["hko-tc"]["lang"]
    assert any("sources.hko-tc: lang" in e for e in fragment_errors(bad))


def test_english_paraphrase_is_rejected():
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["tc9"]["en"]["lines"] = ["Stay inside. If you are reasonably protected, stay where you are"]
    assert any("weather.tc9.en: 'Stay inside." in e for e in fragment_errors(bad))
    with pytest.raises(ValueError, match="weather.tc9.en"):
        validate_actions(bad)


def test_english_word_boundaries_count_but_line_breaks_do_not():
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["tc9"]["en"]["lines"] = ["Stayindoors"]
    assert any("'Stayindoors'" in e for e in fragment_errors(bad))
    wrapped = copy.deepcopy(ACTIONS)
    wrapped["weather"]["tc9"]["en"]["lines"] = ["Stay\n indoors"]
    assert fragment_errors(wrapped) == []


def test_english_must_cite_an_english_source_and_chinese_a_chinese_one():
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["tc9"]["en"]["quotes"][0]["source"] = "hko-tc"
    assert any("weather.tc9.en: source 'hko-tc' is not in 'en'" in e for e in fragment_errors(bad))
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["tc9"]["quotes"][0]["source"] = "hko-tc-en"
    assert any("weather.tc9: source 'hko-tc-en' is not in 'zh'" in e for e in fragment_errors(bad))


def test_every_entry_says_what_english_to_show():
    bad = copy.deepcopy(ACTIONS)
    del bad["supervisor"]["monsoon"]["en"]
    assert any("supervisor.monsoon: say what to show in English" in e for e in fragment_errors(bad))
    # null: no official English sentence exists, so the screen shows no English for it.
    none = copy.deepcopy(ACTIONS)
    none["weather"]["tc9"]["en"] = None
    assert fragment_errors(none) == []
    assert english_lines(none["weather"]["tc9"]) == []
    empty = copy.deepcopy(ACTIONS)
    empty["weather"]["tc9"]["en"]["lines"] = []
    assert any("weather.tc9.en: nothing to show" in e for e in fragment_errors(empty))


def test_english_lines_and_notes():
    assert english_lines(weather_by_code(ACTIONS)["TC8NE"]) == [
        "employees should be released from workplaces or from work by batches",
        "Return home as soon as possible if conditions so permit",
    ]
    assert note_text_en(ACTIONS, "heatUnacclimatised") == (
        "employees are unacclimatised or need to re-acclimate to hot work environment"
        + EN_JOIN
        + "increase the hourly rest time for such employees by 15 minutes"
    )


def test_rest_english_covers_every_value_the_schedule_can_give():
    results = tile_results(SCHEDULE)
    kinds = {(r["kind"], r["rest"], r["work"]) for r in results}
    assert kinds == {
        ("rest", 15, 45), ("rest", 30, 30), ("rest", 45, 15), ("suspend", 60, 0),
        ("baseline", 10, None), ("baseline", 15, None),
    }
    tile = ACTIONS["rest"]["tile"]["en"]
    shown = {line for result in results for line in tile_lines_en(result, tile)}
    assert shown == {
        "15 mins rest", "30 mins rest", "45 mins rest", "15 mins work", "30 mins work", "45 mins work",
        "Suspension of work",
        "at least 10 minutes of rest for every 2 hours of work",
        "at least 15 minutes of rest for every 2 hours of work",
    }


def test_rest_english_fails_when_the_schedule_no_longer_matches_the_quote():
    # A revised baseline (say 20 minutes) is not in the quoted paragraph: re-verify before showing it.
    schedule = copy.deepcopy(SCHEDULE)
    schedule["baseline"]["heavy"] = schedule["baseline"]["very_heavy"] = 20
    errors = fragment_errors(ACTIONS, schedule)
    assert any("at least 20 minutes of rest" in e for e in errors)
    assert any("at least a 20-minute rest break" in e for e in errors)
    bad = copy.deepcopy(ACTIONS)
    bad["rest"]["tile"]["en"]["rest"] = "rest {rest} minutes"
    assert any("rest.tile.rest: 'rest 45 minutes'" in e for e in fragment_errors(bad))


def test_normal_day_english_follows_the_chinese_grouping():
    normal = ACTIONS["rest"]["normal"]["en"]
    assert normal_lines_en(SCHEDULE, {"very_heavy"}, normal) == [
        "at least a 15-minute rest break after every 2 hours of work"
    ]
    assert normal_lines_en(SCHEDULE, {"light", "moderate"}, normal) == [
        "a minimum of a 10-minute rest break after every 2 hours of work"
    ]
    assert normal_lines_en(SCHEDULE, {"light", "heavy"}, normal) == [
        "heavy to very heavy levels of physical work: at least a 15-minute rest break after every 2 hours of work",
        "light to moderate levels of physical work: a minimum of a 10-minute rest break after every 2 hours of work",
    ]


def test_a_section_the_check_does_not_know_is_rejected():
    bad = copy.deepcopy(ACTIONS)
    bad["announcements"] = {"x": {"main": "停工", "quotes": []}}
    assert any("announcements: unknown section" in e for e in fragment_errors(bad))


def test_every_section_with_wording_is_checked():
    from app.actions import ENTRY_SECTIONS, SECTIONS

    assert set(ACTIONS) - {"sources"} == set(SECTIONS)
    unrelated_en = [{"source": "ld-cop-weather-en", "text": "An unrelated sentence."}]
    for section in ENTRY_SECTIONS:
        for key in ACTIONS[section]:
            bad = copy.deepcopy(ACTIONS)
            bad[section][key]["quotes"] = [{"source": "ld-cop-weather", "text": "完全無關的句子。"}]
            assert any(e.startswith(f"{section}.{key}:") for e in fragment_errors(bad)), f"{section}.{key}"
            if ACTIONS[section][key]["en"] is not None:
                bad = copy.deepcopy(ACTIONS)
                bad[section][key]["en"]["quotes"] = unrelated_en
                assert any(e.startswith(f"{section}.{key}.en:") for e in fragment_errors(bad)), f"{section}.{key}.en"
    for part in ("workloads", "tile", "normal"):
        bad = copy.deepcopy(ACTIONS)
        bad["rest"][part]["en"]["quotes"] = [{"source": "ld-gn-heat-en", "text": "An unrelated sentence."}]
        assert any(e.startswith(f"rest.{part}.") for e in fragment_errors(bad)), f"rest.{part}"


def test_english_must_be_kept_where_the_screen_reads_it():
    # Lines under an instruction (an entry with a main line), fragments for a supervisor line or a note.
    bad = copy.deepcopy(ACTIONS)
    en = bad["weather"]["tc9"]["en"]
    en["fragments"] = en.pop("lines")
    assert any("weather.tc9.en: nothing to show" in e for e in fragment_errors(bad))
    bad = copy.deepcopy(ACTIONS)
    en = bad["supervisor"]["monsoon"]["en"]
    en["lines"] = en.pop("fragments")
    assert any("supervisor.monsoon.en: nothing to show" in e for e in fragment_errors(bad))


# The supervisor line shown after Signal 8 or above, or Black rain, ends.


def test_the_after_signal_line_and_its_labels_are_official_wording():
    from app.actions import after_spec, displayed

    spec = after_spec(ACTIONS)
    assert spec["fragments"] == ["留意天氣信息，保持高度警覺", "可能仍持續影響工作安全"]
    assert spec["when"] == {"cancel": "取消", "lower": "改發較低警告信號"}
    assert set(spec["when"].values()) <= set(displayed(spec))
    bad = copy.deepcopy(ACTIONS)
    bad["supervisor"]["after-tc8-black-rain"]["when"]["lower"] = "改發低一級信號"
    assert any("改發低一級信號" in e for e in fragment_errors(bad))


def test_the_after_signal_line_needs_its_signals_hours_and_labels():
    def errors(change):
        bad = copy.deepcopy(ACTIONS)
        change(bad["supervisor"])
        return fragment_errors(bad)

    assert any("either \"codes\"" in e for e in errors(lambda s: s["after-tc8-black-rain"].update(codes=["TC3"])))
    assert any("either \"codes\"" in e for e in errors(lambda s: s["monsoon"].pop("codes")))
    assert any("\"hours\"" in e for e in errors(lambda s: s["after-tc8-black-rain"].update(hours=0)))
    assert any("\"hours\"" in e for e in errors(lambda s: s["after-tc8-black-rain"].update(hours="24")))
    assert any("\"when\"" in e for e in errors(lambda s: s["after-tc8-black-rain"]["when"].pop("cancel")))
    two = errors(lambda s: s.update({"copy": copy.deepcopy(s["after-tc8-black-rain"])}))
    assert any("only one entry" in e for e in two)
