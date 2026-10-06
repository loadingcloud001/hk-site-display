import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps" / "kiosk" / "public"
HKO_WX_CODES = [50, 51, 52, 53, 54, 60, 61, 62, 63, 64, 65, 70, 71, 72, 73, 74, 75, 76, 77,
                80, 81, 82, 83, 84, 85, 90, 91, 92, 93]


def load(name):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def test_every_warning_icon_file_exists():
    for code, rel in load("official_icons.json").items():
        assert (PUBLIC / rel).is_file(), code


def test_signals_and_rain_use_hko_100px_png():
    icons = load("official_icons.json")
    for code in ("TC1", "TC3", "TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10", "WRAINA", "WRAINR", "WRAINB"):
        assert icons[code].startswith("official/warning/") and icons[code].endswith(".png"), code


def test_every_hko_weather_icon_is_listed_and_present():
    wx = load("wx_icons.json")["icons"]
    assert sorted(int(c) for c in wx) == HKO_WX_CODES
    for code in wx:
        assert (PUBLIC / f"official/wxicon/pic{code}.png").is_file(), code
