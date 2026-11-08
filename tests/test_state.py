from app.actions import load_actions, weather_by_code
from app.state import WEATHER_ORDER, state_tone, supervisor_lines, tc_signal_code, winning_weather_code

ACTIONS = load_actions()


def test_black_rain_outranks_signal_8():
    assert winning_weather_code(["TC8NE", "WRAINB", "WL"]) == "WRAINB"


def test_weather_order():
    assert winning_weather_code(["TC8NE", "TC9"]) == "TC9"
    assert winning_weather_code(["TC10", "WRAINB"]) == "TC10"
    assert winning_weather_code(["WTCPRE8", "TC3", "WRAINR"]) == "WTCPRE8"
    assert winning_weather_code(["TC3", "WTS", "WRAINA"]) is None


def test_every_weather_code_has_an_official_instruction():
    assert set(weather_by_code(ACTIONS)) == set(WEATHER_ORDER)


def test_tones():
    assert state_tone("weather", "WRAINB", "amber") == "p0-rain"
    assert state_tone("weather", "TC8NE", "none") == "p0-tc"
    assert state_tone("weather", "WL", "none") == "p0-landslip"
    assert state_tone("weather", "WTCPRE8", "none") == "p1"
    assert state_tone("weather", "WTMW", "none") == "watch"
    assert state_tone("heat", None, "red") == "red"
    assert state_tone("normal", None, "none") == "idle"


def test_supervisor_lines_ranked_and_capped():
    labels = {"TC3": "三號強風信號", "WTS": "雷暴警告", "WMSGNL": "強烈季候風信號", "WRAINA": "黃色暴雨警告信號"}
    assert supervisor_lines(ACTIONS, ["TC3", "WRAINA", "WTS", "WMSGNL"], labels) == [
        {"text": "有僱員可能遭受雷電擊中時：立即停止工作，並到安全地方暫避", "fromZh": "雷暴警告"},
        {"text": "停止操作起重機、吊船、進行斜坡工程", "fromZh": "強烈季候風信號"},
    ]


def test_supervisor_line_for_signal_3():
    assert supervisor_lines(ACTIONS, ["TC3"], {"TC3": "三號強風信號"}) == [
        {"text": "停止操作起重機、吊船", "fromZh": "三號強風信號"}
    ]


def test_tc_signal_code():
    assert tc_signal_code(["WTCPRE8", "TC3"]) == "TC3"
    assert tc_signal_code(["WRAINR"]) is None


AFTER_TC8 = {"code": "TC8NE", "fromZh": "八號東北烈風或暴風信號", "whenZh": "16:20 改發較低警告信號",
             "fromEn": "No. 8 Northeast Gale or Storm Signal"}
REMAIN_VIGILANT = "留意天氣信息，保持高度警覺：可能仍持續影響工作安全"


def test_after_signal_8_the_reminder_follows_the_warnings_in_force():
    lines = supervisor_lines(ACTIONS, ["TC3"], {"TC3": "三號強風信號"}, None, AFTER_TC8)
    assert lines == [
        {"text": "停止操作起重機、吊船", "fromZh": "三號強風信號"},
        {"text": REMAIN_VIGILANT, "fromZh": "八號東北烈風或暴風信號", "whenZh": "16:20 改發較低警告信號"},
    ]


def test_the_reminder_is_never_more_than_the_second_line():
    labels = {"TC3": "三號強風信號", "WTS": "雷暴警告"}
    lines = supervisor_lines(ACTIONS, ["TC3", "WTS"], labels, None, AFTER_TC8)
    assert [line["text"] for line in lines] == [
        "有僱員可能遭受雷電擊中時：立即停止工作，並到安全地方暫避",
        "停止操作起重機、吊船",
    ]
    assert supervisor_lines(ACTIONS, [], {}, None, AFTER_TC8)[0]["text"] == REMAIN_VIGILANT


def test_the_reminder_only_for_its_own_signals():
    tc3 = {**AFTER_TC8, "code": "TC3"}
    assert supervisor_lines(ACTIONS, [], {}, None, tc3) == []
    assert supervisor_lines(ACTIONS, [], {}, None, None) == []


def test_the_reminder_in_english_is_the_official_sentence_and_hkos_name():
    [line] = supervisor_lines(ACTIONS, [], {}, {}, AFTER_TC8)
    assert line["textEn"] == (
        "Pay attention to weather information and remain highly vigilant; be aware that work safety may still be "
        "affected even after the cancellation or lowering of warning signals"
    )
    assert line["fromEn"] == "No. 8 Northeast Gale or Storm Signal"
    [line] = supervisor_lines(ACTIONS, [], {}, {}, {**AFTER_TC8, "fromEn": None})
    assert line["fromEn"] is None
