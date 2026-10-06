from datetime import datetime, timedelta, timezone

from app.banner import build_banner
from app.snapshot import code_rank

HKT = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 15, 14, 45, tzinfo=HKT)


def iso(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


AMBER_ISSUE = {
    "level": "amber", "inForce": True, "titleZh": "黃色工作暑熱警告",
    "messageKind": "issue", "effectiveAt": iso(3),
}


def event(code, action, minutes_ago, type_="", name=""):
    at = iso(minutes_ago)
    return {"key": code, "code": code, "name": name, "type": type_, "actionCode": action, "issueTime": at, "updateTime": at}


def banner(hsww=None, events=(), info=(), stale=False):
    return build_banner(hsww or {}, list(events), list(info), NOW, code_rank, stale)


def test_hsww_issue_within_ten_minutes():
    assert banner(AMBER_ISSUE) == {"time": "14:42", "textZh": "黃色工作暑熱警告 生效", "kind": "issue", "code": "HSWW-amber"}


def test_hsww_hourly_update_never_shows():
    assert banner({**AMBER_ISSUE, "messageKind": "update"}) is None


def test_hsww_cancel():
    shown = banner({"level": "none", "inForce": False, "messageKind": "cancel", "effectiveAt": iso(5)})
    assert shown["textZh"] == "工作暑熱警告 取消" and shown["kind"] == "cancel"


def test_ten_minute_edges():
    assert banner({**AMBER_ISSUE, "effectiveAt": iso(9.98)}) is not None
    assert banner({**AMBER_ISSUE, "effectiveAt": iso(10.02)}) is None


def test_warnsum_issue_and_cancel():
    assert banner(events=[event("TC8NE", "ISSUE", 2, "八號東北烈風或暴風信號")])["textZh"] == "八號東北烈風或暴風信號 發出"
    assert banner(events=[event("WRAINB", "CANCEL", 4, "黑色暴雨警告信號")])["textZh"] == "黑色暴雨警告信號 取消"
    assert banner(events=[event("CANCEL", "ISSUE", 1, "", "熱帶氣旋警告信號")])["textZh"] == "熱帶氣旋警告信號 取消"


def test_extend_update_reissue_ignored():
    for action in ("EXTEND", "UPDATE", "REISSUE"):
        assert banner(events=[event("WTS", action, 1, "雷暴警告")]) is None


def test_pre8_banner():
    shown = banner(info=[{"code": "WTCPRE8", "updateTime": iso(2)}])
    assert shown["textZh"] == "預警八號熱帶氣旋警告信號之特別報告 發出"


def test_most_severe_wins():
    shown = banner(
        AMBER_ISSUE,
        events=[event("WRAINB", "ISSUE", 6, "黑色暴雨警告信號"), event("TC3", "ISSUE", 1, "三號強風信號")],
    )
    assert shown["code"] == "WRAINB"


def test_hidden_when_stale():
    assert banner(AMBER_ISSUE, stale=True) is None
