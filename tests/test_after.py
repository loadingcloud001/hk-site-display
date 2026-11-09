from datetime import datetime, timedelta, timezone

from app.after import LOST_TRACK, ended_signal, remember, when_zh
from app.snapshot import AFTER, AFTER_CODES

HKT = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 24, 16, 30, tzinfo=HKT)
TC_NAME = "熱帶氣旋警告信號"
TYPES = {
    "TC1": "一號戒備信號",
    "TC3": "三號強風信號",
    "TC8NE": "八號東北烈風或暴風信號",
    "TC8SE": "八號東南烈風或暴風信號",
    "TC9": "九號烈風或暴風風力增強信號",
    "TC10": "十號颶風信號",
    "WRAINA": "黃色",
    "WRAINR": "紅色",
    "WRAINB": "黑色",
}
ENGLISH = {"TC8NE": "No. 8 Northeast Gale or Storm Signal", "TC3": "Strong Wind Signal No. 3"}


def ago(minutes):
    return NOW - timedelta(minutes=minutes)


def iso(minutes):
    return ago(minutes).isoformat()


def warnsum(code, minutes, action="ISSUE", updated=None):
    """One entry shaped like HKO's live warnsum: TC signals under WTCSGNL, rainstorm signals under WRAIN."""
    key = "WRAIN" if code.startswith("WRAIN") else "WTCSGNL"
    name = "暴雨警告信號" if key == "WRAIN" else TC_NAME
    entry = {"name": name, "code": code, "actionCode": action, "issueTime": iso(minutes)}
    entry["updateTime"] = iso(minutes if updated is None else updated)
    if code in TYPES:
        entry["type"] = TYPES[code]
    return {key: entry}


def english(code, minutes):
    entry = {"name": "Tropical Cyclone Warning Signal", "code": code, "actionCode": "ISSUE", "issueTime": iso(minutes)}
    if code in ENGLISH:
        entry["type"] = ENGLISH[code]
    return {"WTCSGNL": entry}


def run(*readings):
    """The memory after (warnsum, fetched minutes ago[, English warnsum]) readings, oldest first."""
    memory = {}
    for reading in readings:
        value, minutes, *en = reading
        memory = remember(memory, value, en[0] if en else None, ago(minutes), AFTER_CODES)
    return memory


def ended(memory, now=NOW, in_force=()):
    return ended_signal(memory, now, AFTER["hours"], in_force)


def test_the_config_names_signal_8_or_above_and_black_rain_for_24_hours():
    assert AFTER_CODES == {"TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10", "WRAINB"}
    assert AFTER["hours"] == 24


def test_signal_8_lowered_to_3_ends_at_hkos_issue_time_of_signal_3():
    memory = run((warnsum("TC8NE", 300), 31, english("TC8NE", 300)), (warnsum("TC3", 30), 29, english("TC3", 30)))
    assert ended(memory) == {
        "code": "TC8NE",
        "nameZh": "八號東北烈風或暴風信號",
        "nameEn": "No. 8 Northeast Gale or Storm Signal",
        "at": ago(30),
        "how": "lower",
    }


def test_a_new_direction_or_a_lower_trigger_is_still_signal_8_or_above():
    memory = run((warnsum("TC10", 500), 400), (warnsum("TC9", 300), 299), (warnsum("TC8NE", 200), 199),
                 (warnsum("TC8SE", 100), 99))
    assert ended(memory) is None
    assert memory["WTCSGNL"]["code"] == "TC8SE"
    memory = remember(memory, warnsum("TC1", 10), None, ago(9), AFTER_CODES)
    assert ended(memory)["code"] == "TC8SE"
    assert ended(memory)["at"] == ago(10)


def test_every_signal_cancelled_ends_at_the_cancellations_update_time():
    # HKO's documentation gives the code CANCEL once every tropical cyclone signal is cancelled; either action.
    for action in ("ISSUE", "CANCEL"):
        memory = run((warnsum("TC8NE", 300), 21), (warnsum("CANCEL", 300, action=action, updated=20), 19))
        assert (ended(memory)["how"], ended(memory)["at"]) == ("cancel", ago(20)), action


def test_black_rain_lowered_to_red_or_amber():
    for lower in ("WRAINR", "WRAINA"):
        memory = run((warnsum("WRAINB", 120), 41), (warnsum(lower, 40), 39))
        found = ended(memory)
        assert (found["code"], found["nameZh"], found["how"], found["at"]) == ("WRAINB", "黑色暴雨警告信號", "lower", ago(40))


def test_a_cancellation_hkos_feed_still_lists_needs_no_memory():
    # HKO keeps a cancelled warning in warnsum for about an hour: issue time as issued, update time as cancelled.
    memory = run((warnsum("WRAINB", 300, action="CANCEL", updated=15), 1))
    assert (ended(memory)["how"], ended(memory)["at"]) == ("cancel", ago(15))
    # Read again at the next poll: still the same end.
    assert ended(remember(memory, warnsum("WRAINB", 300, action="CANCEL", updated=15), None, NOW, AFTER_CODES)) == (
        ended(memory)
    )


def test_a_lowered_signal_is_not_cancelled_again_by_its_later_cancellation():
    memory = run((warnsum("TC8NE", 600), 301), (warnsum("TC3", 300), 299), (warnsum("TC3", 300, "CANCEL", 60), 59))
    assert (ended(memory)["how"], ended(memory)["at"]) == ("lower", ago(300))


def test_raised_signals_are_never_an_end():
    memory = run((warnsum("TC1", 300), 200), (warnsum("TC3", 100), 99), (warnsum("WRAINA", 50), 49),
                 (warnsum("WRAINR", 20), 19))
    assert memory == {}
    assert ended(memory) is None


def test_without_memory_signal_3_says_nothing_about_signal_8():
    # A restart forgets: Signal 3 alone reads the same after Signal 1 as after Signal 8.
    assert ended(run((warnsum("TC3", 30), 29))) is None


def test_back_in_force_clears_the_end():
    memory = run((warnsum("WRAINB", 120), 61), (warnsum("WRAINR", 60), 59), (warnsum("WRAINB", 30), 29))
    assert ended(memory) is None
    assert memory["WRAIN"]["ended"] is None


def test_back_in_force_is_skipped_even_before_the_next_reading():
    memory = run((warnsum("WRAINB", 120), 61), (warnsum("WRAINR", 60), 59))
    assert ended(memory, in_force=["WRAINB"]) is None
    assert ended(memory, in_force=["WRAINR", "TC8NE"]) is not None


def test_a_reading_without_the_entry_is_no_evidence():
    memory = run((warnsum("TC8NE", 300), 31), ({}, 29), ({"WTS": {"code": "WTS", "actionCode": "ISSUE"}}, 20))
    assert memory["WTCSGNL"]["ended"] is None
    assert ended(memory) is None


def test_a_change_long_after_the_last_sighting_is_not_put_down_to_it():
    # The service lost track (HKO or the service down for hours): Signal 3 might follow anything.
    gap = int(LOST_TRACK.total_seconds() // 60)
    memory = run((warnsum("TC8NE", gap + 400), gap + 100), (warnsum("TC3", 90), 89))
    assert memory == {}
    assert ended(memory) is None


def test_a_change_from_before_the_signal_was_issued_is_not_its_end():
    memory = run((warnsum("TC8NE", 60), 31), (warnsum("TC3", 90), 29))
    assert memory == {}


def test_hkos_time_is_used_and_a_missing_or_future_one_falls_back_to_the_reading():
    bad = warnsum("TC3", 30)
    bad["WTCSGNL"]["issueTime"] = None
    bad["WTCSGNL"]["updateTime"] = None
    assert ended(run((warnsum("TC8NE", 300), 31), (bad, 29)))["at"] == ago(29)
    future = warnsum("TC3", -60)
    assert ended(run((warnsum("TC8NE", 300), 31), (future, 29)))["at"] == ago(29)


def test_the_same_reading_twice_gives_the_same_memory():
    first = run((warnsum("TC8NE", 300), 31), (warnsum("TC3", 30), 29))
    again = remember(first, warnsum("TC3", 30), None, ago(29), AFTER_CODES)
    assert again == first


def test_the_english_name_arrives_with_hkos_english_feed():
    memory = run((warnsum("TC8NE", 300), 40))
    assert memory["WTCSGNL"]["nameEn"] is None
    memory = remember(memory, warnsum("TC8NE", 300), english("TC8NE", 300), ago(39), AFTER_CODES)
    memory = remember(memory, warnsum("TC8NE", 300), {}, ago(38), AFTER_CODES)
    memory = remember(memory, warnsum("TC3", 30), None, ago(29), AFTER_CODES)
    assert ended(memory)["nameEn"] == "No. 8 Northeast Gale or Storm Signal"


def test_shown_for_24_hours_then_not():
    memory = run((warnsum("TC8NE", 300), 31), (warnsum("TC3", 30), 29))
    assert ended(memory, now=ago(30) + timedelta(hours=24) - timedelta(seconds=1)) is not None
    assert ended(memory, now=ago(30) + timedelta(hours=24)) is None


def test_the_most_recent_end_is_shown_when_both_kinds_ended():
    memory = run(
        (warnsum("WRAINB", 400), 301),
        (warnsum("WRAINR", 300), 299),
        (warnsum("TC8NE", 500), 201),
        (warnsum("TC3", 200), 199),
    )
    assert ended(memory)["code"] == "TC8NE"


def test_when_names_the_day_unless_it_is_today():
    labels = AFTER["when"]
    assert when_zh({"at": ago(30), "how": "lower"}, NOW, labels) == "16:00 改發較低警告信號"
    assert when_zh({"at": ago(30), "how": "cancel"}, NOW, labels) == "16:00 取消"
    yesterday = {"at": datetime(2026, 9, 23, 18, 45, tzinfo=HKT), "how": "lower"}
    assert when_zh(yesterday, NOW, labels) == "9月23日 18:45 改發較低警告信號"
    utc = {"at": datetime(2026, 9, 24, 2, 5, tzinfo=timezone.utc), "how": "cancel"}
    assert when_zh(utc, NOW, labels) == "10:05 取消"


def test_a_time_without_a_time_zone_is_never_compared():
    naive = warnsum("TC8NE", 300)
    naive["WTCSGNL"]["issueTime"] = "2026-09-24T11:30:00"
    lowered = warnsum("TC3", 30)
    lowered["WTCSGNL"]["issueTime"] = "2026-09-24T16:00:00"
    assert ended(run((naive, 31), (lowered, 29)))["at"] == ago(29)
