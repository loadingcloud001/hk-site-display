"""「極端情況」: the switch's rules, its state file, and how it ranks against HKO warnings on the screen."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import extreme
from app.snapshot import build_snapshot
from app.stations import Position

HKT = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 7, 17, 20, tzinfo=HKT)
ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SITE = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
MAIN = "留在原來的地點或安全的地點"
SUPERVISOR = "立即暫停僱員在戶外及空曠地方的工作，並安排僱員到安全地方暫避"
SUPERVISOR_EN = (  # the demo site shows English: the official English Code of Practice, same bullet
    "immediately suspend the work of employees working outdoors and in exposed areas and arrange temporary shelter "
    "in a safe place for them"
)


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def at(minutes):
    """NOW plus `minutes`, as the switch records it."""
    return extreme.iso(NOW + timedelta(minutes=minutes))


def ann(start=-20, end=100):
    return {"startsAt": at(start), "endsAt": at(end), "setAt": at(start)}


# --- what an operator may send ---------------------------------------------------------------------------------


def test_switch_on_now_until_the_announced_end():
    got = extreme.announcement({"endsAt": "2026-11-07T19:00"}, NOW)
    assert got == {"startsAt": "2026-11-07T17:20:00+08:00", "endsAt": "2026-11-07T19:00:00+08:00", "setAt": got["setAt"]}
    assert extreme.status(got, NOW) == "active"


def test_times_are_hong_kong_time_unless_they_say_otherwise():
    got = extreme.announcement({"startsAt": "2026-11-07 17:00", "endsAt": "2026-11-07T11:00:00Z"}, NOW)
    assert (got["startsAt"], got["endsAt"]) == ("2026-11-07T17:00:00+08:00", "2026-11-07T19:00:00+08:00")


def test_a_later_start_waits_and_shows_nothing_until_then():
    got = extreme.announcement({"startsAt": "2026-11-07T18:00", "endsAt": "2026-11-07T20:00"}, NOW)
    assert extreme.status(got, NOW) == "scheduled"
    assert extreme.active(got, NOW) is None
    assert extreme.status(got, NOW + timedelta(minutes=40)) == "active"


@pytest.mark.parametrize(
    ("body", "says"),
    [
        ({}, "endsAt is required"),
        ({"endsAt": None}, "endsAt is required"),
        ({"endsAt": "19:00"}, "not a date and time"),
        ({"endsAt": "tomorrow"}, "not a date and time"),
        ({"endsAt": "2026-11-08"}, "has no time"),  # would otherwise mean midnight
        ({"startsAt": "2026-11-07", "endsAt": "2026-11-07T19:00"}, "has no time"),
        ({"endsAt": 1900}, "must be a date and time"),
        ({"endsAt": "2026-11-07T17:00"}, "already passed"),
        ({"startsAt": "2026-11-07T19:00", "endsAt": "2026-11-07T18:00"}, "after startsAt"),
        ({"startsAt": "2026-11-07T19:00", "endsAt": "2026-11-07T19:00"}, "after startsAt"),
        ({"endsAt": "2026-11-08T17:21"}, "more than 24 hours ahead"),
        ({"startsAt": "2026-11-06T17:00", "endsAt": "2026-11-07T19:00"}, "more than 24 hours ago"),
        ({"until": "2026-11-07T19:00", "endsAt": "2026-11-07T19:00"}, "unknown field(s) until"),
        (["2026-11-07T19:00"], "JSON object"),
    ],
)
def test_mistakes_are_refused_with_a_reason(body, says):
    with pytest.raises(ValueError, match=None) as err:
        extreme.announcement(body, NOW)
    assert says in str(err.value)


def test_an_extension_keeps_the_recorded_start():
    on = extreme.announcement({"endsAt": "2026-11-07T19:00"}, NOW)  # 17:20 to 19:00
    extended = extreme.announcement({"endsAt": "2026-11-07T21:00"}, NOW + timedelta(minutes=90), on)
    assert (extended["startsAt"], extended["endsAt"]) == (on["startsAt"], "2026-11-07T21:00:00+08:00")


def test_a_scheduled_start_is_kept_too_and_an_ended_one_starts_afresh():
    scheduled = extreme.announcement({"startsAt": "2026-11-07T18:00", "endsAt": "2026-11-07T20:00"}, NOW)
    assert extreme.announcement({"endsAt": "2026-11-07T21:00"}, NOW, scheduled)["startsAt"] == "2026-11-07T18:00:00+08:00"
    ended = {"startsAt": "2026-11-07T15:00:00+08:00", "endsAt": "2026-11-07T17:00:00+08:00", "setAt": None}
    assert extreme.announcement({"endsAt": "2026-11-07T19:00"}, NOW, ended)["startsAt"] == "2026-11-07T17:20:00+08:00"


def test_a_long_one_can_still_be_extended_after_24_hours():
    on = {"startsAt": "2026-11-06T17:00:00+08:00", "endsAt": "2026-11-07T18:00:00+08:00", "setAt": None}
    assert extreme.announcement({"endsAt": "2026-11-07T20:00"}, NOW, on)["startsAt"] == on["startsAt"]
    resent = extreme.announcement({"startsAt": "2026-11-06T17:00", "endsAt": "2026-11-07T20:00"}, NOW, on)
    assert resent["startsAt"] == on["startsAt"]
    with pytest.raises(ValueError, match="more than 24 hours ago"):  # a different start that far back is a mistake
        extreme.announcement({"startsAt": "2026-11-06T16:00", "endsAt": "2026-11-07T20:00"}, NOW, on)


def test_the_announced_end_expires_it_by_itself():
    a = ann(start=-20, end=40)
    assert extreme.status(a, NOW + timedelta(minutes=39, seconds=59)) == "active"
    assert extreme.status(a, NOW + timedelta(minutes=40)) == "ended"
    assert extreme.active(a, NOW + timedelta(minutes=40)) is None
    assert extreme.status(None, NOW) == "off"


def test_times_on_screen_carry_the_date_only_when_not_today():
    assert extreme.when_zh(NOW + timedelta(minutes=100), NOW) == "19:00"
    assert extreme.when_zh(datetime(2026, 11, 8, 8, 0, tzinfo=HKT), NOW) == "11月8日 08:00"
    assert extreme.when_zh(datetime(2026, 11, 7, 0, 30, tzinfo=timezone.utc), NOW) == "08:30"


# --- the state file: restart, hand edits, failures -------------------------------------------------------------


def test_it_survives_a_restart(tmp_path):
    first = extreme.ExtremeStore(tmp_path)
    first.set(ann())
    restarted = extreme.ExtremeStore(tmp_path)
    assert restarted.get() == ann()
    assert restarted.problem is None
    assert json.loads((tmp_path / "extreme.json").read_text(encoding="utf-8")) == ann()
    assert not list(tmp_path.glob("*.tmp"))


def test_no_file_means_off(tmp_path):
    store = extreme.ExtremeStore(tmp_path / "not-yet")
    assert store.get() is None and store.problem is None


def test_switching_off_ends_it_now_and_keeps_the_record(tmp_path):
    store = extreme.ExtremeStore(tmp_path)
    store.set(ann())
    left = store.end(NOW)
    assert left["endsAt"] == at(0) and left["startsAt"] == at(-20)
    assert extreme.status(extreme.ExtremeStore(tmp_path).get(), NOW) == "ended"


def test_switching_off_before_the_start_withdraws_it(tmp_path):
    store = extreme.ExtremeStore(tmp_path)
    store.set(ann(start=30, end=150))
    assert store.end(NOW) is None
    assert not (tmp_path / "extreme.json").exists()
    assert extreme.ExtremeStore(tmp_path).get() is None


def test_switching_off_when_off_changes_nothing(tmp_path):
    store = extreme.ExtremeStore(tmp_path)
    assert store.end(NOW) is None
    store.set(ann(start=-200, end=-80))
    assert store.end(NOW)["endsAt"] == at(-80)


def test_a_hand_edit_on_the_server_is_picked_up(tmp_path):
    store = extreme.ExtremeStore(tmp_path)
    assert store.get() is None
    (tmp_path / "extreme.json").write_text(json.dumps({"startsAt": "2026-11-07T17:00", "endsAt": "2026-11-07T19:00"}))
    assert extreme.status(store.get(), NOW) == "active"
    assert store.get()["endsAt"] == "2026-11-07T19:00:00+08:00"


@pytest.mark.parametrize(
    "text",
    ["{not json", "[]", '{"startsAt": "2026-11-07T17:00"}', '{"startsAt": "2026-11-07T19:00", "endsAt": "2026-11-07T17:00"}'],
)
def test_a_bad_file_is_off_and_reported_never_fatal(tmp_path, text):
    (tmp_path / "extreme.json").write_text(text, encoding="utf-8")
    store = extreme.ExtremeStore(tmp_path)
    assert store.get() is None
    assert store.problem and "extreme.json" in store.problem


def test_a_bad_file_is_forgotten_once_the_switch_is_used_again(tmp_path):
    (tmp_path / "extreme.json").write_text("{not json", encoding="utf-8")
    store = extreme.ExtremeStore(tmp_path)
    store.get()
    store.set(ann())
    assert store.get() == ann() and store.problem is None


def test_a_failed_save_changes_nothing(tmp_path, monkeypatch):
    store = extreme.ExtremeStore(tmp_path)
    store.set(ann())

    def full(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(extreme.os, "replace", full)
    with pytest.raises(OSError):
        store.set(ann(end=200))
    monkeypatch.undo()
    assert store.get() == ann()
    assert extreme.ExtremeStore(tmp_path).get() == ann()
    assert not list(tmp_path.glob("*.tmp"))


def test_an_unwritable_state_folder_is_found_at_start_up(tmp_path):
    folder = tmp_path / "state"
    folder.mkdir()
    store = extreme.ExtremeStore(folder)
    assert store.check_writable() is True and store.problem is None
    blocked = extreme.ExtremeStore(tmp_path / "file" / "state")
    (tmp_path / "file").write_text("a file, not a folder")
    assert blocked.check_writable() is False
    assert "cannot write" in blocked.problem


# --- the admin key ---------------------------------------------------------------------------------------------


def test_key_comparison_is_constant_time_on_digests(monkeypatch):
    seen = []
    real = extreme.hmac.compare_digest

    def spy(a, b):
        seen.append((len(a), len(b)))
        return real(a, b)

    monkeypatch.setattr(extreme.hmac, "compare_digest", spy)
    key = "k" * 40
    assert extreme.key_ok(key, key) is True
    assert extreme.key_ok("short", key) is False
    assert seen == [(32, 32), (32, 32)]  # SHA-256 digests, so even the length is never compared
    assert extreme.key_ok("", key) is False and extreme.key_ok(key, "") is False


def test_short_or_missing_keys_turn_the_switch_off():
    assert extreme.usable_key(None) == ""
    assert extreme.usable_key("   ") == ""
    assert extreme.usable_key("x" * 31) == ""
    assert extreme.usable_key(" " + "x" * 32 + "\n") == "x" * 32


def test_bearer_header():
    assert extreme.bearer("Bearer abc") == "abc"
    assert extreme.bearer("bearer  abc ") == "abc"
    assert extreme.bearer("Basic abc") == ""
    assert extreme.bearer(None) == ""
    assert extreme.bearer("abc") == ""


# --- the screen: ranking against HKO warnings -------------------------------------------------------------------


def snap(warnsum=None, info=None, hsww="hsww_cancelled_stale.json", announcement=None, now=NOW, stale=False):
    return build_snapshot(
        load(hsww),
        warnsum or {},
        info or {},
        {},
        SITE,
        SCHEDULE,
        ICONS,
        now=now,
        stale=stale,
        extreme=announcement,
    )


def warn(code, type_, key="WTCSGNL", minutes=-120):
    return {key: {"name": type_, "code": code, "actionCode": "ISSUE", "type": type_, "issueTime": at(minutes), "updateTime": at(minutes)}}


def test_in_force_it_takes_the_centre_with_the_official_wording():
    s = snap(announcement=ann())
    assert s["display"]["mode"] == "extreme" and s["tone"] == "extreme"
    assert s["display"]["main"] == MAIN and s["display"]["sub"] == ["而非立即啟程往工作地點上班"]
    assert s["display"]["heroRel"] is None  # no official icon exists, and none is drawn
    assert s["extreme"] == {
        "nameZh": "「極端情況」",
        "startsAt": at(-20),
        "endsAt": at(100),
        "startZh": "17:00",
        "endZh": "19:00",
    }
    assert s["supervisor"] == [{"text": SUPERVISOR, "fromZh": "「極端情況」", "textEn": SUPERVISOR_EN, "fromEn": None}]
    assert s["priority"] == {"band": "P0", "headlineZh": "「極端情況」"}
    assert (s["display"]["action"], s["display"]["actionSub"]) == (MAIN, "而非立即啟程往工作地點上班")
    assert s["display"]["meta"] == "「極端情況」 · 17:00 生效 · 19:00 結束"


@pytest.mark.parametrize(
    ("warnsum", "code"),
    [
        (warn("TC10", "十號颶風信號"), "TC10"),
        (warn("TC9", "九號烈風或暴風風力增強信號"), "TC9"),
        (load("warnsum_tc8ne.json"), "TC8NE"),
        (load("warnsum_wrainb.json"), "WRAINB"),
        (warn("WL", "山泥傾瀉警告", key="WL"), "WL"),
        (warn("TC3", "三號強風信號"), "TC3"),
        (load("warnsum_tc1.json"), "TC1"),
        (warn("WTS", "雷暴警告", key="WTS"), "WTS"),
    ],
)
def test_it_outranks_every_hko_warning_which_stays_on_the_bar(warnsum, code):
    plain = snap(warnsum)
    s = snap(warnsum, announcement=ann())
    assert s["display"]["mode"] == "extreme"
    assert [x["code"] for x in s["signals"]] == [x["code"] for x in plain["signals"]]
    assert code in [x["code"] for x in s["signals"] if x["rel"]]


def test_it_outranks_heat_stress_which_stays_on_the_bar():
    s = snap(hsww="hsww_amber_inforce.json", announcement=ann())
    assert s["display"]["mode"] == "extreme"
    assert s["restTiles"] == [] and s["notes"] == []
    assert "HSWW-amber" in [x["code"] for x in s["signals"]]


def test_hko_supervisor_lines_give_way_to_its_own():
    s = snap(warn("TC3", "三號強風信號"), announcement=ann())
    assert [line["text"] for line in s["supervisor"]] == [SUPERVISOR]


def test_scheduled_or_ended_leaves_the_screen_to_hko():
    for later in (ann(start=10, end=130), ann(start=-150, end=-30)):
        s = snap(load("warnsum_tc8ne.json"), announcement=later)
        assert s["display"]["mode"] == "weather" and s["extreme"] is None
        assert s["priority"]["band"] == "P0" and s["priority"]["headlineZh"] != "「極端情況」"
    assert snap(announcement=ann(start=-150, end=-30))["display"]["mode"] == "normal"


def test_banner_when_it_takes_effect_and_when_it_ends():
    started = snap(warn("TC3", "三號強風信號", minutes=-4), announcement=ann(start=-4, end=116))["banner"]
    assert started == {"time": "17:16", "textZh": "「極端情況」 生效", "kind": "issue", "code": "EXTREME"}
    ended = snap(announcement=ann(start=-130, end=-3))["banner"]
    assert ended == {"time": "17:17", "textZh": "「極端情況」 結束", "kind": "cancel", "code": "EXTREME"}
    assert snap(announcement=ann(start=-130, end=-11))["banner"] is None
    assert snap(announcement=ann(start=-11, end=100))["banner"] is None


def test_no_banner_before_it_takes_effect_or_while_data_is_stale():
    assert snap(announcement=ann(start=5, end=120))["banner"] is None
    assert snap(announcement=ann(start=-4, end=116), stale=True)["banner"] is None


def test_position_never_changes_it():
    s = snap(announcement=ann())
    located = build_snapshot(
        load("hsww_cancelled_stale.json"), {}, {}, {}, SITE, SCHEDULE, ICONS, now=NOW, extreme=ann(),
        position=Position(22.3125, 114.2260, 60),
    )
    for key in ("display", "extreme", "supervisor", "tone", "banner", "priority"):
        assert located[key] == s[key], key


def test_the_state_file_holds_only_the_announced_times(tmp_path):
    store = extreme.ExtremeStore(tmp_path)
    store.set(extreme.announcement({"endsAt": "2026-11-07T19:00"}, NOW))
    assert set(json.loads((tmp_path / "extreme.json").read_text(encoding="utf-8"))) == {"startsAt", "endsAt", "setAt"}
