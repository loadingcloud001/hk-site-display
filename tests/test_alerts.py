"""Supervisor alerts: change detection, one message per real change, restart, stale data, rate limit, channels."""
import json
import logging
import re
import smtplib
import threading
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.alerts import (
    BACKOFF_SEC,
    BURST,
    AlertEngine,
    change_lines,
    engine_from_env,
    is_escalation,
)
from app.feeds import Feed, FeedSet
from app.hko import PRE8_NAME, warning_name
from app.senders import DryRunSender, Message, SendError, SmtpSender, mask, sender_from_env
from app.site import GENERIC_SITE
from app.snapshot import build_snapshot

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
DEMO = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))
START = datetime(2026, 7, 15, 9, 0, tzinfo=HKT)
main.ENABLE_POLLER = False


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


NO_HSWW = fixture("hsww_cancelled_stale.json")
AMBER = fixture("hsww_amber_inforce.json")
RED = fixture("hsww_red_synth.json")
BLACK = fixture("hsww_black_synth.json")
PRE8 = fixture("warningInfo_pre8.json")

# warnsum entries shaped like HKO's live feed (key, name, type): `type` is the signal's name for tropical cyclone
# signals, only the colour for rainstorm and fire danger warnings, and absent for the others.
W = {
    "WTS": ("WTS", "雷暴警告", ""),
    "WRAINA": ("WRAIN", "暴雨警告信號", "黃色"),
    "WRAINR": ("WRAIN", "暴雨警告信號", "紅色"),
    "WRAINB": ("WRAIN", "暴雨警告信號", "黑色"),
    "TC1": ("WTCSGNL", "熱帶氣旋警告信號", "一號戒備信號"),
    "TC3": ("WTCSGNL", "熱帶氣旋警告信號", "三號強風信號"),
    "TC8NE": ("WTCSGNL", "熱帶氣旋警告信號", "八號東北烈風或暴風信號"),
    "TC8SE": ("WTCSGNL", "熱帶氣旋警告信號", "八號東南烈風或暴風信號"),
    "WL": ("WL", "山泥傾瀉警告", ""),
    "WMSGNL": ("WMSGNL", "強烈季候風信號", ""),
    "WHOT": ("WHOT", "酷熱天氣警告", ""),
    "WFIREY": ("WFIRE", "火災危險警告", "黃色"),
    "WFIRER": ("WFIRE", "火災危險警告", "紅色"),
}


def warnsum(*codes, action="ISSUE", updated="2026-07-15T08:30:00+08:00"):
    out = {}
    for code in codes:
        key, name, type_ = W[code]
        out[key] = {"name": name, "code": code, "actionCode": action, "issueTime": "2026-07-15T08:30:00+08:00"}
        out[key]["updateTime"] = updated
        if type_:
            out[key]["type"] = type_
    return out


def with_alerts(site, *emails):
    return {**site, "alerts": {"email": list(emails)}}


class FakeSender:
    channel, mode = "email", "email"

    def __init__(self, fail=False, refuse=()):
        self.sent, self.fail, self.refuse, self.attempts = [], fail, set(refuse), 0

    def describe(self):
        return "fake sender"

    def send(self, recipients, message):
        self.attempts += 1
        if self.fail:
            raise SendError("SMTPServerDisconnected: test")
        self.sent.append((list(recipients), message))
        return [r for r in recipients if r in self.refuse]


class World:
    """The official feeds as the poller sees them, and a clock. poll() is one fresh fetch of every feed, a minute
    after the last one; `fetched` names the feeds that fetched successfully this time."""

    def __init__(self, tmp_path, sites=None, operator=(), sender=None, state=None):
        self.hsww, self.warnsum, self.info = NO_HSWW, {}, {}
        self.now, self.marks = START, {}
        self.sender = sender or FakeSender()
        default = {"demo-kai-tak": with_alerts(DEMO, "chan@example.com", "lee@example.com")}
        self.sites = default if sites is None else sites
        self.operator = list(operator)
        self.state = state or tmp_path / "alerts.json"
        self.restart()

    def restart(self):
        self.engine = AlertEngine(self.sites, self.sender, self.state, self.operator, "https://screen.example")
        return self.engine

    def snapshot_for(self, site):
        site = site or GENERIC_SITE
        return build_snapshot(self.hsww, self.warnsum, self.info, {}, site, SCHEDULE, ICONS, now=self.now)

    def poll(self, times=1, fetched=("hsww", "warnsum", "warningInfo")):
        for _ in range(times):
            self.now += timedelta(minutes=1)
            for feed in fetched:
                self.marks[feed] = self.now
            self.engine.check(self.now, dict(self.marks), self.snapshot_for)

    def take(self):
        """Messages sent since the last take, as (recipients, subject, body)."""
        out = [(recipients, m.subject, m.body) for recipients, m in self.sender.sent]
        self.sender.sent.clear()
        return out

    def subjects(self):
        return [subject for _, subject, _ in self.take()]


def started(tmp_path, **kwargs):
    world = World(tmp_path, **kwargs)
    world.poll(2)  # two readings confirm the state; a site seen for the first time is told nothing
    assert world.take() == []
    return world


def changes(body):
    """The change lines: after the site's name and time, up to the blank line."""
    return body.split("\n\n")[0].splitlines()[1:]


# --- What counts as a change ------------------------------------------------------------------------------------


def test_each_heat_stress_level_change_is_one_message(tmp_path):
    world = started(tmp_path)
    steps = [
        (AMBER, "黃色工作暑熱警告 生效", "紮鐵 · 棚架：休息 45 分鐘 · 工作 15 分鐘"),
        (RED, "紅色工作暑熱警告 生效", "紮鐵 · 棚架：暫停工作"),
        (BLACK, "黑色工作暑熱警告 生效", "紮鐵 · 棚架 · 釘板 · 混凝土：暫停工作"),
        (NO_HSWW, "工作暑熱警告 取消", "正常工作"),
    ]
    for raw, change, screen in steps:
        world.hsww = raw
        world.poll()
        assert world.take() == []  # one reading is not enough: HKO feeds glitch
        world.poll()
        ((recipients, subject, body),) = world.take()
        assert recipients == ["chan@example.com", "lee@example.com"]
        assert subject == f"【示範地盤】{change}" and changes(body) == [change]
        assert screen in body.splitlines()
        world.poll(3)
        assert world.take() == []


def test_a_warning_issued_then_cancelled(tmp_path):
    world = started(tmp_path)
    world.warnsum = warnsum("WTS")
    world.poll(2)
    ((_, subject, body),) = world.take()
    assert subject == "【示範地盤】雷暴警告 發出"
    assert "主管注意：有僱員可能遭受雷電擊中時：立即停止工作，並到安全地方暫避（雷暴警告）" in body
    assert body.endswith("現正生效：雷暴警告\n\nhttps://screen.example/?site=demo-kai-tak")
    world.warnsum = {}
    world.poll(2)
    ((_, subject, body),) = world.take()
    assert subject == "【示範地盤】雷暴警告 取消" and "現正生效" not in body


def test_a_changed_signal_names_only_the_new_one(tmp_path):
    world = started(tmp_path)
    for code, change in (("TC1", "一號戒備信號 發出"), ("TC3", "三號強風信號 發出"), ("TC8NE", "八號東北烈風或暴風信號 發出")):
        world.warnsum = warnsum(code)
        world.poll(2)
        ((_, subject, body),) = world.take()
        assert changes(body) == [change]  # never "三號強風信號 取消", which would read as an easing
    assert "分批離開工作地點" in body.splitlines()
    world.warnsum = warnsum("TC8NE", action="CANCEL")
    world.warnsum["WTCSGNL"]["code"] = "CANCEL"  # HKO cancels every signal with code CANCEL
    world.poll(2)
    assert world.subjects() == ["【示範地盤】八號東北烈風或暴風信號 取消"]


def test_rainstorm_signals_amber_red_black(tmp_path):
    world = started(tmp_path)
    for code, change, action in (
        ("WRAINA", "黃色暴雨警告信號 發出", "主管注意：停止操作吊船、進行斜坡工程（黃色暴雨警告信號）"),
        ("WRAINR", "紅色暴雨警告信號 發出", "暫停戶外作業"),
        ("WRAINB", "黑色暴雨警告信號 發出", "停止戶外作業"),
    ):
        world.warnsum = warnsum(code)
        world.poll(2)
        ((_, subject, body),) = world.take()
        assert changes(body) == [change] and action in body.splitlines()


def test_rainstorm_and_fire_danger_warnings_have_their_whole_names(tmp_path):
    # HKO's live feed sends only the colour as `type` for these warnings ("黑色", "紅色").
    world = started(tmp_path)
    world.warnsum = {**warnsum("WRAINB"), **warnsum("WFIRER")}
    world.poll(2)
    ((_, subject, body),) = world.take()
    assert subject == "【示範地盤】黑色暴雨警告信號 發出 +1"
    assert changes(body) == ["黑色暴雨警告信號 發出", "紅色火災危險警告 發出"]
    assert "現正生效：黑色暴雨警告信號 · 紅色火災危險警告" in body.splitlines()
    world.warnsum = warnsum("WRAINB")
    world.poll(2)
    assert world.subjects() == ["【示範地盤】紅色火災危險警告 取消"]


def test_pre8_is_announced_and_ends_quietly_under_signal_8(tmp_path):
    world = started(tmp_path)
    world.warnsum = warnsum("TC3")
    world.poll(2)
    world.info = PRE8
    world.poll(2)
    ((_, subject, body),) = world.take()[-1:]
    assert subject == f"【示範地盤】{PRE8_NAME} 發出" and "分批離開工作地點" in body.splitlines()
    world.warnsum = warnsum("TC8NE")  # warnsum changes first...
    world.poll(2)
    assert world.subjects() == ["【示範地盤】八號東北烈風或暴風信號 發出"]
    world.info = {}  # ...and the Pre-8 announcement ends a minute later: nothing a supervisor needs
    world.poll(4)
    assert world.take() == []


def test_an_extension_update_or_reissue_is_not_a_change(tmp_path):
    world = started(tmp_path)
    world.warnsum = {**warnsum("WTS"), **warnsum("WHOT")}
    world.poll(2)
    assert len(world.take()) == 1
    world.warnsum = {**warnsum("WTS", action="EXTEND", updated="2026-07-15T09:30:00+08:00"), **warnsum("WHOT")}
    world.poll(3)
    world.warnsum = {**warnsum("WTS", action="UPDATE"), **warnsum("WHOT", action="REISSUE")}
    world.poll(3)
    assert world.take() == []


def test_several_changes_in_one_poll_make_one_message_most_severe_first(tmp_path):
    world = started(tmp_path)
    world.hsww, world.warnsum = AMBER, {**warnsum("WTS"), **warnsum("WRAINB")}
    world.poll(2)
    ((_, subject, body),) = world.take()
    assert subject == "【示範地盤】黑色暴雨警告信號 發出 +2"
    assert changes(body) == ["黑色暴雨警告信號 發出", "雷暴警告 發出", "黃色工作暑熱警告 生效"]
    assert body.split("\n\n")[1].splitlines()[:3] == ["告示屏：", "停止戶外作業", "並到安全地方暫避"]


def test_the_position_never_matters(tmp_path):
    # The alerts build each site's snapshot without a position: the same one for every screen of the site.
    world = started(tmp_path)
    world.hsww = AMBER
    world.poll(2)
    ((_, _, body),) = world.take()
    assert "香港天文台" not in body and "lat" not in body


# --- Only what the screen shows ---------------------------------------------------------------------------------

# Words a message may add to the snapshot's own text: the screen's (apps/kiosk/src/Screen.tsx), the change
# banner's (app/banner.py), HKO's 現正生效 (warningInfo: "強烈季候風信號現正生效。"), and the name of the screen.
SCREEN_WORDS = ("暫停工作", "休息", "分鐘", "工作", "每", "小時", "主管注意")
BANNER_WORDS = ("發出", "取消", "生效", "工作暑熱警告")
OWN_WORDS = ("現正生效", "告示屏")


def test_the_screen_and_banner_words_are_really_theirs():
    screen = (ROOT / "apps/kiosk/src/Screen.tsx").read_text(encoding="utf-8")
    banner = (ROOT / "services/ingest/app/banner.py").read_text(encoding="utf-8")
    assert all(word in screen for word in SCREEN_WORDS)
    assert all(word in banner for word in BANNER_WORDS)


def test_a_message_says_nothing_the_screen_does_not(tmp_path):
    world = started(tmp_path)
    shown, sent = [json.dumps(world.snapshot_for(DEMO), ensure_ascii=False)], []
    steps = [
        (AMBER, warnsum("WTS"), {}),
        (RED, warnsum("WMSGNL"), {}),
        (NO_HSWW, warnsum("TC3"), PRE8),
        (NO_HSWW, {**warnsum("TC8NE"), **warnsum("WRAINB"), **warnsum("WL")}, {}),
        (BLACK, warnsum("WFIREY"), {}),
        (NO_HSWW, {}, {}),
    ]
    for hsww, warn, info in steps:
        world.hsww, world.warnsum, world.info = hsww, warn, info
        world.poll(2)
        world.poll(20)  # let any held message go out
        shown.append(json.dumps(world.snapshot_for(DEMO), ensure_ascii=False))
        sent += world.take()
    assert len(sent) == len(steps)
    for _, subject, body in sent:
        lines = [subject] + body.splitlines()[1:]  # the first line is the site's name and the time
        for line in lines:
            if line.startswith("https://"):
                continue
            for word in sorted(SCREEN_WORDS + BANNER_WORDS + OWN_WORDS, key=len, reverse=True):
                line = line.replace(word, " ")
            for piece in re.split(r"[\s·：（）【】+]+", line):
                assert not piece or any(piece in text for text in shown), (piece, body)


# --- Glitches and flapping --------------------------------------------------------------------------------------


def test_a_one_fetch_glitch_sends_nothing(tmp_path):
    world = started(tmp_path)
    world.warnsum = warnsum("WRAINR")
    world.poll(2)
    world.take()
    world.warnsum = {}  # HKO answers once with no warnings
    world.poll()
    world.warnsum = warnsum("WRAINR")
    world.poll(5)
    assert world.take() == []


def test_flapping_on_every_fetch_sends_nothing(tmp_path):
    world = started(tmp_path)
    for i in range(12):
        world.hsww = AMBER if i % 2 == 0 else NO_HSWW
        world.poll()
    assert world.take() == []


def test_a_failed_fetch_is_not_a_second_reading(tmp_path):
    world = started(tmp_path)
    world.warnsum = warnsum("WTS")
    world.poll(2)
    world.take()
    world.warnsum = {}
    world.poll()  # one glitched reading of warnsum
    world.poll(fetched=("hsww", "warningInfo"))  # warnsum's next fetch fails: its last value is not read twice
    world.warnsum = warnsum("WTS")
    world.poll(3)
    assert world.take() == []


# --- Restarts and first sight -----------------------------------------------------------------------------------


def test_a_restart_never_sends_again(tmp_path):
    world = started(tmp_path)
    world.hsww = AMBER
    world.poll(2)
    assert len(world.take()) == 1
    world.restart()
    world.poll(5)
    assert world.take() == []


def test_a_change_while_the_service_was_down_is_sent_after_the_restart(tmp_path):
    world = started(tmp_path)
    world.hsww = AMBER
    world.poll(2)
    world.take()
    world.hsww, world.warnsum = NO_HSWW, warnsum("WTS")  # while the service was down
    world.restart()
    world.poll()
    assert world.take() == []  # two readings after a restart too
    world.poll()
    ((_, subject, body),) = world.take()
    assert subject == "【示範地盤】雷暴警告 發出 +1" and changes(body) == ["雷暴警告 發出", "工作暑熱警告 取消"]


def test_a_new_site_starts_quietly_even_during_a_warning(tmp_path):
    world = World(tmp_path)
    world.hsww, world.warnsum = RED, warnsum("WRAINB")
    world.poll(4)
    assert world.take() == []
    world.warnsum = {}
    world.poll(2)
    assert world.subjects() == ["【示範地盤】黑色暴雨警告信號 取消"]


@pytest.mark.parametrize(
    "content",
    ["{ not json", '{"version": 1, "sites": {"demo-kai-tak": {"sent": {"heat": "purple"}}}}', '{"version": 9}'],
)
def test_a_damaged_state_file_starts_again_quietly(tmp_path, caplog, content):
    (tmp_path / "alerts.json").write_text(content, encoding="utf-8")
    world = World(tmp_path)
    world.hsww = AMBER
    world.poll(3)
    assert world.take() == []
    assert (tmp_path / "alerts.json.bad").read_text(encoding="utf-8") == content
    assert "damaged" in caplog.text
    world.hsww = NO_HSWW
    world.poll(2)
    assert world.subjects() == ["【示範地盤】工作暑熱警告 取消"]
    saved = json.loads(world.state.read_text(encoding="utf-8"))
    assert saved["sites"]["demo-kai-tak"]["sent"]["heat"] == "none"


def test_a_state_file_that_cannot_be_written_fails_health_but_alerts_still_go_out(tmp_path):
    (tmp_path / "file").write_text("x", encoding="utf-8")
    world = World(tmp_path, state=tmp_path / "file" / "alerts.json")  # its folder is a file
    world.poll(2)
    world.hsww = AMBER
    world.poll(2)
    assert len(world.take()) == 1
    assert not world.engine.healthy(world.now)
    assert world.engine.status(world.now)["problems"][0].startswith("ALERT_STATE_FILE cannot be written")


# --- Stale data: the operator only ------------------------------------------------------------------------------


def test_stale_and_recovered_go_to_the_operator_only(tmp_path):
    world = started(tmp_path, operator=["ops@example.com"])
    world.poll(9, fetched=())  # 9 minutes without a fresh fetch: not stale yet
    assert world.take() == []
    world.poll(2, fetched=())
    ((recipients, subject, body),) = world.take()
    assert recipients == ["ops@example.com"]
    assert subject == "[hk-site-display] Warning data stale: screens show 資料過期"
    assert "since 09:02" in body and "https://screen.example/api/v1/health" in body
    world.poll(2)
    assert [(r, s) for r, s, _ in world.take()] == [
        (["ops@example.com"], "[hk-site-display] Warning data back: screens are live")
    ]


def test_without_an_operator_stale_data_sends_nothing(tmp_path):
    world = started(tmp_path)
    world.poll(15, fetched=())
    world.poll(3)
    assert world.take() == []


def test_no_data_since_a_restart_counts_from_the_start_and_is_never_a_recovery(tmp_path):
    world = started(tmp_path, operator=["ops@example.com"])
    world.marks = {}  # the service restarts while HKO cannot be reached
    world.restart()
    world.poll(10, fetched=())
    assert world.take() == []
    world.poll(2, fetched=())
    assert world.subjects() == ["[hk-site-display] Warning data stale: screens show 資料過期"]
    world.restart()  # and again, still without data: no "back" message
    world.poll(15, fetched=())
    assert world.take() == []


# --- Several sites ------------------------------------------------------------------------------------------------


def test_each_site_gets_its_own_message_and_recipients(tmp_path):
    other = {
        "siteId": "s7k2",
        "nameZh": "地盤乙",
        "primaryTrades": [{"labelZh": "外牆", "workload": "heavy"}],
        "alerts": {"email": ["wong@example.com"]},
    }
    sites = {"demo-kai-tak": with_alerts(DEMO, "chan@example.com"), "s7k2": other, "quiet": {**DEMO, "siteId": "quiet"}}
    world = started(tmp_path, sites=sites)
    world.hsww = AMBER
    world.poll(2)
    sent = {tuple(recipients): (subject, body) for recipients, subject, body in world.take()}
    assert set(sent) == {("chan@example.com",), ("wong@example.com",)}  # the site without alerts gets nothing
    subject, body = sent[("wong@example.com",)]
    assert subject == "【地盤乙】黃色工作暑熱警告 生效"
    assert "外牆：休息 30 分鐘 · 工作 30 分鐘" in body.splitlines() and "紮鐵" not in body
    assert body.endswith("https://screen.example/?site=s7k2")


# --- Rate limit ---------------------------------------------------------------------------------------------------


def test_cancellations_wait_for_the_rate_limit_but_new_warnings_never_do(tmp_path, caplog):
    world = started(tmp_path)
    for _ in range(BURST // 2):  # three thunderstorm warnings issued and cancelled within minutes
        world.warnsum = warnsum("WTS")
        world.poll(2)
        world.warnsum = {}
        world.poll(2)
    assert len(world.take()) == BURST
    world.warnsum = warnsum("WTS")
    world.poll(2)
    assert world.subjects() == ["【示範地盤】雷暴警告 發出"]  # a new warning never waits
    world.warnsum = {}
    world.poll(2)
    assert world.take() == []  # a cancellation waits
    assert caplog.text.count("cancellations and lower levels wait") == 1
    world.warnsum = warnsum("WRAINA")  # a new warning goes out at once, with the held cancellation
    world.poll(2)
    ((_, subject, body),) = world.take()
    assert subject == "【示範地盤】黃色暴雨警告信號 發出 +1"
    assert changes(body) == ["黃色暴雨警告信號 發出", "雷暴警告 取消"]
    world.warnsum = {}
    world.poll(2)
    assert world.take() == []
    world.poll(20)  # the bucket refills one message every 10 minutes
    assert world.subjects() == ["【示範地盤】黃色暴雨警告信號 取消"]


def test_a_feed_flapping_for_hours_sends_a_bounded_number_of_messages(tmp_path):
    world = started(tmp_path)
    per_hour = [0, 0, 0]
    for minute in range(180):  # a thunderstorm warning that comes and goes every two fetches
        world.warnsum = warnsum("WTS") if (minute // 2) % 2 == 0 else {}
        world.poll()
        per_hour[minute // 60] += len(world.take())
    assert per_hour == [11, 6, 6]  # without the limit: 30 an hour


def test_a_held_cancellation_that_is_undone_sends_nothing(tmp_path):
    world = started(tmp_path)
    world.warnsum = warnsum("WTS")
    world.poll(2)
    world.take()
    world.engine.data["sites"]["demo-kai-tak"]["bucket"] = {"tokens": 0.0, "at": world.now.timestamp()}
    world.warnsum = {}
    world.poll(2)  # held: the rate limit is spent
    world.warnsum = warnsum("WTS")
    world.poll(30)  # undone before it could go out
    assert world.take() == []


@pytest.mark.parametrize(
    "old, new, raised",
    [
        (("none",), ("amber",), True),
        (("red",), ("amber",), False),
        (("amber",), ("none",), False),
        (("none",), ("none", "WTS"), True),
        (("none", "WTS"), ("none",), False),
        (("none", "TC3"), ("none", "TC8NE"), True),
        (("none", "TC8NE"), ("none", "TC3"), False),
        (("none", "TC8NE"), ("none", "TC8SE"), False),
        (("none", "WRAINA"), ("none", "WRAINR"), True),
        (("none", "WRAINB"), ("none", "WRAINR"), False),
        (("none", "WFIREY"), ("none", "WFIRER"), False),
        (("none", "TC3"), ("none", "TC3", "WTCPRE8"), True),
        (("none", "TC3", "WTCPRE8"), ("none", "TC8NE"), True),
    ],
)
def test_what_counts_as_raising_a_level(old, new, raised):
    assert is_escalation(state(*old), state(*new)) is raised


def state(heat, *codes):
    warnings = {c: {"label": warning_name(warnsum(c)[W[c][0]]), "group": W[c][0]} for c in codes if c != "WTCPRE8"}
    return {"heat": heat, "warnings": warnings, "pre8": "WTCPRE8" in codes}


@pytest.mark.parametrize(
    "old, new, lines",
    [
        (("none", "TC3"), ("none", "TC8NE"), ["八號東北烈風或暴風信號 發出"]),
        (("none", "TC3", "WTCPRE8"), ("none", "TC8NE"), ["八號東北烈風或暴風信號 發出"]),
        (("none", "TC8NE", "WTCPRE8"), ("none", "TC8NE"), []),
        (("none", "TC3", "WTCPRE8"), ("none", "TC3"), [f"{PRE8_NAME} 取消"]),
        (("none", "WTS", "WRAINA"), ("none", "WRAINR"), ["紅色暴雨警告信號 發出", "雷暴警告 取消"]),
        (("amber",), ("none", "WRAINB"), ["黑色暴雨警告信號 發出", "工作暑熱警告 取消"]),
    ],
)
def test_change_lines(old, new, lines):
    assert change_lines(state(*old), state(*new)) == lines


# --- Failures -----------------------------------------------------------------------------------------------------


def test_a_failed_send_is_retried_later_and_fails_health_after_15_minutes(tmp_path):
    sender = FakeSender(fail=True)
    world = started(tmp_path, sender=sender)
    world.hsww = AMBER
    world.poll(2)
    first = world.now
    assert sender.attempts == 1 and world.engine.status(world.now)["waiting"] == 1
    world.poll(10)  # retries after 1, 2 and 5 more minutes (BACKOFF_SEC)
    assert sender.attempts == 4 and BACKOFF_SEC[:3] == (60, 120, 300)
    assert world.engine.healthy(world.now)
    world.poll(5)
    assert (world.now - first).total_seconds() >= 900 and not world.engine.healthy(world.now)
    assert world.engine.status(world.now)["failingSinceSec"] == (world.now - first).total_seconds()
    sender.fail = False
    world.poll(10)
    assert world.subjects() == ["【示範地盤】黃色工作暑熱警告 生效"]
    assert world.engine.healthy(world.now) and world.engine.status(world.now)["waiting"] == 0
    world.poll(5)
    assert world.take() == []


def test_a_failure_with_nothing_left_to_send_does_not_fail_health(tmp_path):
    world = started(tmp_path, sender=FakeSender(fail=True))
    world.warnsum = warnsum("WTS")
    world.poll(2)  # cannot be sent
    world.warnsum = {}
    world.poll(20)  # and is undone before it could be
    assert world.engine.healthy(world.now) and world.engine.status(world.now)["failingSinceSec"] is None


def test_a_refused_address_is_logged_masked_and_not_retried(tmp_path, caplog):
    world = started(tmp_path, sender=FakeSender(refuse={"lee@example.com"}))
    world.hsww = AMBER
    world.poll(2)
    assert len(world.take()) == 1
    world.poll(5)
    assert world.take() == []
    assert "l***@example.com" in caplog.text and "lee@example.com" not in caplog.text


def test_an_error_in_the_alert_check_is_logged_once_and_fails_health_after_15_minutes(tmp_path, caplog):
    world = started(tmp_path)

    def broken(_site):
        raise RuntimeError("snapshot broke")

    for _ in range(16):
        world.now += timedelta(minutes=1)
        world.engine.check(world.now, dict(world.marks), broken)  # never raises into the poller
    assert caplog.text.count("alert check failed") == 1
    assert not world.engine.healthy(world.now)
    world.poll()
    assert world.engine.healthy(world.now)


# --- Dry run and email --------------------------------------------------------------------------------------------


def test_without_smtp_settings_messages_are_only_logged(tmp_path, caplog, monkeypatch):
    def no_network(*_args, **_kwargs):
        raise AssertionError("a dry run must not connect")

    monkeypatch.setattr(smtplib, "SMTP", no_network)
    monkeypatch.setattr(smtplib, "SMTP_SSL", no_network)
    sender, problems = sender_from_env({})
    assert isinstance(sender, DryRunSender) and problems == []
    caplog.set_level(logging.INFO, logger="hk_site_display")
    world = World(tmp_path, sender=sender)
    world.poll(2)
    world.hsww = AMBER
    world.poll(5)
    assert caplog.text.count("alert (dry run, not sent)") == 1
    assert "【示範地盤】黃色工作暑熱警告 生效" in caplog.text and "紮鐵 · 棚架：休息 45 分鐘 · 工作 15 分鐘" in caplog.text
    assert "c***@example.com, l***@example.com" in caplog.text and "chan@example.com" not in caplog.text
    # A dry run remembers what it logged, so switching SMTP on later does not send old changes.
    saved = json.loads(world.state.read_text(encoding="utf-8"))
    assert saved["sites"]["demo-kai-tak"]["sent"]["heat"] == "amber"


SMTP_ENV = {"SMTP_HOST": "smtp.example.com", "SMTP_USER": "alerts@example.com", "SMTP_PASSWORD": "pw-never-logged"}


def test_smtp_settings_choose_the_sender():
    sender, problems = sender_from_env(SMTP_ENV)
    assert isinstance(sender, SmtpSender) and problems == []
    assert (sender.port, sender.security, sender.from_addr) == (587, "starttls", "alerts@example.com")
    assert "pw-never-logged" not in repr(sender) + sender.describe() + repr(vars(sender).keys())
    assert sender_from_env({**SMTP_ENV, "SMTP_PORT": "465"})[0].security == "ssl"
    assert isinstance(sender_from_env({**SMTP_ENV, "ALERT_DRY_RUN": "true"})[0], DryRunSender)


@pytest.mark.parametrize(
    "env, problem",
    [
        ({"SMTP_PORT": "smtp"}, "SMTP_PORT must be a port number"),
        ({"SMTP_SECURITY": "tls"}, "SMTP_SECURITY must be one of"),
        ({"SMTP_SECURITY": "none"}, "unencrypted"),
        ({"SMTP_PASSWORD": ""}, "set both SMTP_USER and SMTP_PASSWORD"),
        ({"SMTP_USER": "", "SMTP_PASSWORD": "", "ALERT_FROM": ""}, "set ALERT_FROM"),
    ],
)
def test_smtp_settings_that_cannot_work_fall_back_to_dry_run_and_are_reported(env, problem):
    sender, problems = sender_from_env({**SMTP_ENV, **env})
    assert isinstance(sender, DryRunSender)
    assert len(problems) == 1 and problem in problems[0] and "pw-never-logged" not in problems[0]


class FakeSMTP:
    """Stands in for smtplib.SMTP / SMTP_SSL: records what the sender does."""

    last = None

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.calls, self.mails, self.refuse = host, port, [], [], set()
        self.fail_login = False
        FakeSMTP.last = self

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if self.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

    def send_message(self, mail):
        if mail["To"] in self.refuse:
            raise smtplib.SMTPRecipientsRefused({mail["To"]: (550, b"no such user")})
        self.mails.append(mail)

    def quit(self):
        self.calls.append("quit")

    def close(self):
        self.calls.append("close")


def test_email_is_one_plain_text_copy_per_recipient(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    sender = sender_from_env(SMTP_ENV)[0]
    message = Message("【示範地盤】黃色工作暑熱警告 生效", "示範地盤 · 14:42\n黃色工作暑熱警告 生效")
    assert sender.send(["chan@example.com", "lee@example.com"], message) == []
    smtp = FakeSMTP.last
    assert (smtp.host, smtp.port) == ("smtp.example.com", 587)
    assert smtp.calls == ["starttls", ("login", "alerts@example.com", "pw-never-logged"), "quit"]
    assert [mail["To"] for mail in smtp.mails] == ["chan@example.com", "lee@example.com"]
    mail = smtp.mails[0]
    assert mail["Subject"] == message.subject and mail["From"] == "alerts@example.com"
    assert mail["Auto-Submitted"] == "auto-generated"
    assert mail.get_content_type() == "text/plain" and mail.get_content_charset() == "utf-8"
    assert mail.get_content().rstrip("\n") == message.body


def test_email_on_port_465_uses_implicit_tls(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP", None)
    sender = sender_from_env({**SMTP_ENV, "SMTP_PORT": "465"})[0]
    sender.send(["chan@example.com"], Message("s", "b"))
    assert FakeSMTP.last.port == 465 and "starttls" not in FakeSMTP.last.calls


def test_a_refused_recipient_is_returned_and_the_others_still_get_it(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    sender = sender_from_env(SMTP_ENV)[0]
    original = FakeSMTP.__init__

    def refusing(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.refuse = {"chan@example.com"}

    monkeypatch.setattr(FakeSMTP, "__init__", refusing)
    assert sender.send(["chan@example.com", "lee@example.com"], Message("s", "b")) == ["chan@example.com"]
    assert [mail["To"] for mail in FakeSMTP.last.mails] == ["lee@example.com"]


def test_a_refused_login_is_a_send_error_without_the_password(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    original = FakeSMTP.__init__

    def failing(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.fail_login = True

    monkeypatch.setattr(FakeSMTP, "__init__", failing)
    with pytest.raises(SendError) as error:
        sender_from_env(SMTP_ENV)[0].send(["chan@example.com"], Message("s", "b"))
    assert str(error.value) == "SMTPAuthenticationError 535: 5.7.8 Username and Password not accepted"
    assert "pw-never-logged" not in str(error.value) and FakeSMTP.last.calls[-1] == "close"


def test_an_address_is_masked_in_logs():
    assert mask("chan@example.com") == "c***@example.com" and mask("nonsense") == "***"


# --- The service --------------------------------------------------------------------------------------------------


def test_engine_settings_come_from_the_environment(tmp_path):
    env = {
        "ALERT_OPERATOR": "ops@example.com, OPS@example.com ,not-an-address",
        "PUBLIC_URL": "https://screen.example/",
        "ALERT_STATE_FILE": str(tmp_path / "state.json"),
    }
    engine = engine_from_env(env, {"demo-kai-tak": with_alerts(DEMO, "chan@example.com")}, ROOT)
    assert engine.operator.recipients == {"email": ["ops@example.com"]}
    assert engine.problems == ["ALERT_OPERATOR address 3 is not an email address"]
    assert (engine.public_url, engine.path) == ("https://screen.example", tmp_path / "state.json")
    assert list(engine.targets) == ["demo-kai-tak"] and engine.status(START)["mode"] == "dry-run"
    assert not engine.healthy(START)
    default = engine_from_env({}, {"demo-kai-tak": DEMO}, ROOT)
    assert default.path == ROOT / "state" / "alerts.json" and default.targets == {} and default.healthy(START)


def fresh_feeds():
    values = {"hsww": NO_HSWW, "warnsum": {}, "warningInfo": {}, "rhrread": {}, "fnd": {}, "wind": None}
    return FeedSet([Feed(name, lambda _c, v=value: v, 60) for name, value in values.items()], nullcontext)


def test_health_shows_the_alerts_and_fails_on_their_problems(monkeypatch):
    monkeypatch.setattr(main, "FEEDS", fresh_feeds())
    monkeypatch.setattr(main, "SITE_PROBLEMS", [])
    client = TestClient(main.app)
    client.get("/api/v1/snapshot")
    body = client.get("/api/v1/health").json()
    assert body["ok"] is True
    assert body["alerts"] == {
        "mode": "dry-run",
        "sites": 0,
        "operator": False,
        "waiting": 0,
        "failingSinceSec": None,
        "problems": [],
    }
    bad = AlertEngine({}, DryRunSender(), None, problems=["ALERT_OPERATOR address 1 is not an email address"])
    monkeypatch.setattr(main, "ALERTS", bad)
    response = client.get("/api/v1/health")
    assert response.status_code == 503 and response.json()["alerts"]["problems"] == bad.problems


def test_the_poller_checks_alerts_after_each_refresh_and_survives_their_errors(monkeypatch):
    calls, stop = [], threading.Event()

    class Broken:
        def check(self, now, marks, snapshot_for):
            calls.append((now, marks, snapshot_for(None)["display"]["mode"]))
            if len(calls) >= 2:
                stop.set()
            raise RuntimeError("alerts broke")

    monkeypatch.setattr(main, "FEEDS", fresh_feeds())
    monkeypatch.setattr(main, "ALERTS", Broken())
    monkeypatch.setattr(main, "POLL_SEC", 0)
    main._poll(stop)
    assert len(calls) == 2 and main.POLLER["last"] is not None
    assert set(calls[0][1]) == set(main.FEEDS.feeds) and calls[0][1]["hsww"] is not None
    assert calls[0][2] == "normal"


def test_a_test_message_shows_the_screen_now_and_leaves_the_state_alone(tmp_path):
    world = started(tmp_path, operator=["ops@example.com"])
    before = world.state.read_text(encoding="utf-8")
    world.warnsum = warnsum("WMSGNL")
    assert world.engine.send_test("demo-kai-tak", world.now, world.snapshot_for) is True
    ((recipients, subject, body),) = world.take()
    assert subject == "【示範地盤】測試訊息" and recipients == ["chan@example.com", "lee@example.com"]
    assert "主管注意：停止操作起重機、吊船、進行斜坡工程（強烈季候風信號）" in body.splitlines()
    assert world.engine.send_test("operator", world.now, world.snapshot_for) is True
    assert world.take()[0][1] == "[hk-site-display] Test message"
    assert world.engine.send_test("no-such-site", world.now, world.snapshot_for) is False
    assert world.state.read_text(encoding="utf-8") == before
