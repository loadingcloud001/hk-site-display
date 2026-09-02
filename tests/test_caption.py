from app.snapshot import weather_caption


def test_caption_uses_type_not_bulletin_header():
    warnings = [
        {
            "code": "WRAINB",
            "type": "黑色暴雨警告信號",
            "name": "暴雨警告信號",
        }
    ]
    info = [{"code": "WTCSGNL", "contents": ["香港天文台發出最新熱帶氣旋警報"]}]
    assert weather_caption(warnings, info) == "黑色暴雨警告信號"


def test_caption_empty_when_no_warnings():
    assert weather_caption([], []) == ""


def test_pre8_caption_from_warning_info():
    assert (
        weather_caption([], [{"code": "WTCPRE8", "contents": ["長文公報不應該出現"]}])
        == "預警八號熱帶氣旋警告信號"
    )
