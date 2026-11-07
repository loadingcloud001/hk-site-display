from app.hko import active_codes, parse_warnsum, parse_warnsum_events, parse_warning_info, warning_name


def test_empty():
    assert parse_warnsum({}) == []


def test_tc1_active():
    codes = active_codes(
        {"WTCSGNL": {"code": "TC1", "actionCode": "ISSUE"}}
    )
    assert codes == ["TC1"]


def test_cancel_not_active():
    assert active_codes({"WTCSGNL": {"code": "TC1", "actionCode": "CANCEL"}}) == []


def test_tc_code_cancel():
    assert active_codes({"WTCSGNL": {"code": "CANCEL", "actionCode": "ISSUE"}}) == []


def test_pre8_from_warning_info():
    info = parse_warning_info(
        {"details": [{"warningStatementCode": "WTCPRE8", "contents": ["x"]}]}
    )
    assert any(x["code"] == "WTCPRE8" for x in info)


def test_missing_details_ok():
    assert parse_warning_info({}) == []


def test_events_keep_cancellations_with_times():
    raw = {
        "WRAIN": {
            "name": "暴雨警告信號", "code": "WRAINB", "type": "黑色暴雨警告信號", "actionCode": "CANCEL",
            "issueTime": "2026-06-18T08:20:00+08:00", "updateTime": "2026-06-18T10:05:00+08:00",
        },
        "WTCSGNL": {
            "name": "熱帶氣旋警告信號", "code": "TC3", "type": "三號強風信號", "actionCode": "ISSUE",
            "issueTime": "2026-06-18T09:40:00+08:00", "updateTime": "2026-06-18T09:40:00+08:00",
        },
    }
    events = {e["code"]: e for e in parse_warnsum_events(raw)}
    assert events["WRAINB"]["actionCode"] == "CANCEL"
    assert events["WRAINB"]["updateTime"] == "2026-06-18T10:05:00+08:00"
    assert events["TC3"]["type"] == "三號強風信號"
    assert [w["code"] for w in parse_warnsum(raw)] == ["TC3"]


def test_events_ignore_bad_input():
    assert parse_warnsum_events({"x": "y"}) == []
    assert parse_warnsum_events(None) == []


def test_warning_name_is_the_official_name_in_each_language():
    # HKO's live feed sends only the colour as `type` for rainstorm and fire danger warnings.
    black = {"name": "暴雨警告信號", "code": "WRAINB", "type": "黑色"}
    assert warning_name(black) == "黑色暴雨警告信號"
    amber_en = {"name": "Rainstorm Warning Signal", "code": "WRAINA", "type": "Amber"}
    assert warning_name(amber_en, "en") == "Amber Rainstorm Warning Signal"
    assert warning_name({"name": "Fire Danger Warning", "code": "WFIRER", "type": "Red"}, "en") == "Red Fire Danger Warning"
    assert warning_name({"name": "火災危險警告", "code": "WFIREY", "type": "黃色"}) == "黃色火災危險警告"
    # Tropical cyclone signals: `type` is the signal's own name.
    t8 = {"name": "Tropical Cyclone Warning Signal", "code": "TC8NE", "type": "No. 8 Northeast Gale or Storm Signal"}
    assert warning_name(t8, "en") == "No. 8 Northeast Gale or Storm Signal"
    assert warning_name({"name": "熱帶氣旋警告信號", "code": "TC3", "type": "三號強風信號"}) == "三號強風信號"
    # No `type`: the name. A `type` that already holds the whole name is kept as it is.
    assert warning_name({"name": "Thunderstorm Warning", "code": "WTS"}, "en") == "Thunderstorm Warning"
    assert warning_name({"name": "暴雨警告信號", "code": "WRAINB", "type": "黑色暴雨警告信號"}) == "黑色暴雨警告信號"
    assert warning_name({}) == ""
