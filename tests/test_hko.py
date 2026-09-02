from app.hko import active_codes, parse_warnsum, parse_warning_info


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
