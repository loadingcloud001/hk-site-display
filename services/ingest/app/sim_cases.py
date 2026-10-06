import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.site import validate_site
from app.snapshot import build_snapshot

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
FIX = ROOT / "tests" / "fixtures"
SITE = validate_site(json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8")))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
WX_NAMES = json.loads((ROOT / "config/wx_icons.json").read_text(encoding="utf-8"))["icons"]

CANCELLED = "hsww_cancelled_stale.json"
# Preview cases are built at a fixed clock so banners and weather freshness are deterministic.
SIM_NOW = datetime(2026, 7, 15, 14, 45, tzinfo=HKT)
OLD = 120  # minutes ago: too old for the change banner


def _ago(minutes):
    return (SIM_NOW - timedelta(minutes=minutes)).isoformat(timespec="seconds")


def _zh_time(at):
    half = "上" if at.hour < 12 else ("中" if at.hour == 12 else "下")
    return f"{half}午{at.hour % 12 or 12}時{at.minute}分"


def _hsww(name: str, minutes_ago: int | None = None) -> dict:
    raw = json.loads((FIX / name).read_text(encoding="utf-8"))
    if minutes_ago is not None:
        at = SIM_NOW - timedelta(minutes=minutes_ago)
        raw["date"] = (at - timedelta(minutes=2)).strftime("%Y%m%d%H%M")
        raw["MessageTC2"] = re.sub(r"[上中下]午\d{1,2}時\d{1,2}分", _zh_time(at), raw.get("MessageTC2") or "")
    return raw


def _rhrread(minutes_ago: int) -> dict:
    raw = json.loads((FIX / "rhrread_sample.json").read_text(encoding="utf-8"))
    raw["updateTime"] = _ago(minutes_ago)
    return raw


def _fnd(minutes_ago: int) -> dict:
    raw = json.loads((FIX / "fnd_sample.json").read_text(encoding="utf-8"))
    raw["updateTime"] = _ago(minutes_ago)
    for i, day in enumerate(raw["weatherForecast"], start=1):
        day["forecastDate"] = (SIM_NOW + timedelta(days=i)).strftime("%Y%m%d")
    return raw


def _warn(code: str, name: str, type_: str, minutes_ago: int = OLD, action: str = "ISSUE") -> dict:
    if code.startswith("TC"):
        key = "WTCSGNL"
    elif code.startswith("WRAIN"):
        key = "WRAIN"
    elif code in {"WFIREY", "WFIRER"}:
        key = "WFIRE"
    else:
        key = code
    at = _ago(minutes_ago)
    return {key: {"name": name, "code": code, "actionCode": action, "type": type_, "issueTime": at, "updateTime": at}}


def _merge_warn(*parts: dict) -> dict:
    out = {}
    for part in parts:
        out.update(part)
    return out


def _merge_info(*parts: dict) -> dict:
    details = []
    for part in parts:
        details.extend((part or {}).get("details") or [])
    return {"details": details}


def _info(code: str, text: str, subtype: str | None = None, minutes_ago: int = OLD) -> dict:
    return {
        "details": [
            {
                "warningStatementCode": code,
                "subtype": subtype or code,
                "contents": [text],
                "updateTime": _ago(minutes_ago),
            }
        ]
    }


TC3_WARN = _warn("TC3", "熱帶氣旋警告信號", "三號強風信號")
TC3_INFO = _info("WTCSGNL", "三號強風信號現正生效。", "TC3")

SPECS = [
    {"id": "none", "labelZh": "無警告", "group": "hsww"},
    {"id": "amber", "labelZh": "黃色暑熱", "group": "hsww", "hsww": "hsww_amber_inforce.json"},
    {"id": "red", "labelZh": "紅色暑熱", "group": "hsww", "hsww": "hsww_red_synth.json"},
    {"id": "black", "labelZh": "黑色暑熱", "group": "hsww", "hsww": "hsww_black_synth.json"},
    {
        "id": "tc1",
        "labelZh": "一號戒備",
        "group": "tc",
        "warnsum": _warn("TC1", "熱帶氣旋警告信號", "一號戒備信號"),
        "info": _info("WTCSGNL", "一號戒備信號現正生效。", "TC1"),
    },
    {"id": "tc3", "labelZh": "三號強風", "group": "tc", "warnsum": TC3_WARN, "info": TC3_INFO},
    {
        "id": "tc8ne",
        "labelZh": "八號東北",
        "group": "tc",
        "warnsum": _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE"),
    },
    {
        "id": "tc8se",
        "labelZh": "八號東南",
        "group": "tc",
        "warnsum": _warn("TC8SE", "熱帶氣旋警告信號", "八號東南烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號東南烈風或暴風信號現正生效。", "TC8SE"),
    },
    {
        "id": "tc8nw",
        "labelZh": "八號西北",
        "group": "tc",
        "warnsum": _warn("TC8NW", "熱帶氣旋警告信號", "八號西北烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號西北烈風或暴風信號現正生效。", "TC8NW"),
    },
    {
        "id": "tc8sw",
        "labelZh": "八號西南",
        "group": "tc",
        "warnsum": _warn("TC8SW", "熱帶氣旋警告信號", "八號西南烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號西南烈風或暴風信號現正生效。", "TC8SW"),
    },
    {
        "id": "tc9",
        "labelZh": "九號烈風",
        "group": "tc",
        "warnsum": _warn("TC9", "熱帶氣旋警告信號", "九號烈風或暴風風力增強信號"),
        "info": _info("WTCSGNL", "九號烈風或暴風風力增強信號現正生效。", "TC9"),
    },
    {
        "id": "tc10",
        "labelZh": "十號颶風",
        "group": "tc",
        "warnsum": _warn("TC10", "熱帶氣旋警告信號", "十號颶風信號"),
        "info": _info("WTCSGNL", "十號颶風信號現正生效。", "TC10"),
    },
    {
        "id": "rain-amber",
        "labelZh": "黃色暴雨",
        "group": "rain",
        "warnsum": _warn("WRAINA", "暴雨警告信號", "黃色暴雨警告信號"),
        "info": _info("WRAIN", "黃色暴雨警告信號現正生效。", "WRAINA"),
    },
    {
        "id": "rain-red",
        "labelZh": "紅色暴雨",
        "group": "rain",
        "warnsum": _warn("WRAINR", "暴雨警告信號", "紅色暴雨警告信號"),
        "info": _info("WRAIN", "紅色暴雨警告信號現正生效。", "WRAINR"),
    },
    {
        "id": "rain-black",
        "labelZh": "黑色暴雨",
        "group": "rain",
        "warnsum": _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號"),
        "info": _info("WRAIN", "黑色暴雨警告信號現正生效。", "WRAINB"),
    },
    {
        "id": "thunderstorm",
        "labelZh": "雷暴",
        "group": "other",
        "warnsum": _warn("WTS", "雷暴警告", "雷暴警告"),
        "info": _info("WTS", "雷暴警告現正生效。"),
    },
    {
        "id": "landslip",
        "labelZh": "山泥傾瀉",
        "group": "other",
        "warnsum": _warn("WL", "山泥傾瀉警告", "山泥傾瀉警告"),
        "info": _info("WL", "山泥傾瀉警告現正生效。"),
    },
    {
        "id": "vhot",
        "labelZh": "酷熱天氣",
        "group": "other",
        "warnsum": _warn("WHOT", "酷熱天氣警告", "酷熱天氣警告"),
        "info": _info("WHOT", "酷熱天氣警告現正生效。"),
    },
    {
        "id": "monsoon",
        "labelZh": "強烈季候風",
        "group": "other",
        "warnsum": _warn("WMSGNL", "強烈季候風信號", "強烈季候風信號"),
        "info": _info("WMSGNL", "強烈季候風信號現正生效。"),
    },
    {
        "id": "pre8",
        "labelZh": "預警八號",
        "group": "tc",
        "warnsum": TC3_WARN,
        "info": _info("WTCPRE8", "天文台預告將改發八號烈風或暴風信號。"),
    },
    {
        "id": "amber-tc1",
        "labelZh": "黃暑熱＋一號",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("TC1", "熱帶氣旋警告信號", "一號戒備信號"),
        "info": _info("WTCSGNL", "一號戒備信號現正生效。", "TC1"),
    },
    {
        "id": "amber-vhot",
        "labelZh": "黃暑熱＋酷熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("WHOT", "酷熱天氣警告", "酷熱天氣警告"),
        "info": _info("WHOT", "酷熱天氣警告現正生效。"),
    },
    {
        "id": "amber-ts",
        "labelZh": "黃暑熱＋雷暴",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("WTS", "雷暴警告", "雷暴警告"),
        "info": _info("WTS", "雷暴警告現正生效。"),
    },
    {
        "id": "amber-tc3",
        "labelZh": "黃暑熱＋三號",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": TC3_WARN,
        "info": TC3_INFO,
    },
    {
        "id": "tc8-amber",
        "labelZh": "八號＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE"),
    },
    {
        "id": "rain-black-amber",
        "labelZh": "黑雨＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號"),
        "info": _info("WRAIN", "黑色暴雨警告信號現正生效。", "WRAINB"),
    },
    {
        "id": "pre8-amber",
        "labelZh": "預警八號＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": TC3_WARN,
        "info": _info("WTCPRE8", "天文台預告將改發八號烈風或暴風信號。"),
    },
    {
        "id": "typhoon-stack",
        "labelZh": "八號＋黑雨＋山泥＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _merge_warn(
            _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號"),
            _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號"),
            _warn("WL", "山泥傾瀉警告", "山泥傾瀉警告"),
        ),
        "info": _merge_info(
            _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE"),
            _info("WRAIN", "黑色暴雨警告信號現正生效。", "WRAINB"),
            _info("WL", "山泥傾瀉警告現正生效。"),
        ),
    },
    {"id": "stale", "labelZh": "資料過期", "group": "hsww", "stale": True},
    {
        "id": "cold",
        "labelZh": "寒冷天氣",
        "group": "other",
        "warnsum": _warn("WCOLD", "寒冷天氣警告", "寒冷天氣警告"),
        "info": _info("WCOLD", "寒冷天氣警告現正生效。"),
    },
    {
        "id": "fire-yellow",
        "labelZh": "黃色火災危險",
        "group": "other",
        "warnsum": _warn("WFIREY", "火災危險警告", "黃色火災危險警告"),
        "info": _info("WFIRE", "黃色火災危險警告現正生效。", "WFIREY"),
    },
    {
        "id": "fire-red",
        "labelZh": "紅色火災危險",
        "group": "other",
        "warnsum": _warn("WFIRER", "火災危險警告", "紅色火災危險警告"),
        "info": _info("WFIRE", "紅色火災危險警告現正生效。", "WFIRER"),
    },
    {
        "id": "frost",
        "labelZh": "霜凍",
        "group": "other",
        "warnsum": _warn("WFROST", "霜凍警告", "霜凍警告"),
        "info": _info("WFROST", "霜凍警告現正生效。"),
    },
    {
        "id": "ntfl",
        "labelZh": "新界北部水浸",
        "group": "other",
        "warnsum": _warn("WFNTSA", "新界北部水浸特別報告", "新界北部水浸特別報告"),
        "info": _info("WFNTSA", "新界北部水浸特別報告現正生效。"),
    },
    {
        "id": "tsunami",
        "labelZh": "海嘯",
        "group": "other",
        "warnsum": _warn("WTMW", "海嘯警告", "海嘯警告"),
        "info": _info("WTMW", "海嘯警告現正生效。"),
    },
    {"id": "amber-new", "labelZh": "黃暑熱（剛生效）", "group": "hsww", "hsww": "hsww_amber_inforce.json", "hswwAgo": 3},
    {"id": "hsww-cancel-new", "labelZh": "暑熱警告（剛取消）", "group": "hsww", "hsww": CANCELLED, "hswwAgo": 4},
    {
        "id": "tc8ne-new",
        "labelZh": "八號東北（剛發出）",
        "group": "tc",
        "warnsum": _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號", minutes_ago=4),
        "info": _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE", minutes_ago=4),
    },
    {
        "id": "rain-black-cancel",
        "labelZh": "黑雨（剛取消）",
        "group": "rain",
        "warnsum": _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號", minutes_ago=3, action="CANCEL"),
    },
    {
        "id": "rain-amber-tc3",
        "labelZh": "黃雨＋三號",
        "group": "combo",
        "warnsum": _merge_warn(_warn("WRAINA", "暴雨警告信號", "黃色暴雨警告信號"), TC3_WARN),
    },
    {
        "id": "trades-indoor",
        "labelZh": "黃暑熱＋室內工種",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "site": {
            "primaryTrades": [
                {"id": "bar-fixer", "labelZh": "紮鐵", "workload": "very_heavy"},
                {"id": "fitout", "labelZh": "室內裝修", "workload": "moderate", "environment": "indoor"},
                {"id": "electrician", "labelZh": "電工", "workload": "moderate", "environment": "aircon"},
                {"id": "welder", "labelZh": "焊接", "workload": "moderate", "adjustMinutes": 15},
            ]
        },
    },
    {"id": "weather-old", "labelZh": "天氣資料過舊", "group": "other", "rhrreadAgo": 120},
    {"id": "forecast-old", "labelZh": "預報資料過舊", "group": "other", "fndAgo": 13 * 60},
]

CASE_IDS = [s["id"] for s in SPECS]
_BY_ID = {s["id"]: s for s in SPECS}

# Aliases used by the old 6-button sim bar.
ALIASES = {"black-rain": "rain-black", "tc8": "tc8ne"}

HSWW_ICONS = [
    {"code": "HSWW-amber", "labelZh": "黃色工作暑熱警告", "rel": "official/hkhi_yellow.png", "kind": "hsww"},
    {"code": "HSWW-red", "labelZh": "紅色工作暑熱警告", "rel": "official/hkhi_red.png", "kind": "hsww"},
    {"code": "HSWW-black", "labelZh": "黑色工作暑熱警告", "rel": "official/hkhi_black.png", "kind": "hsww"},
    {"code": "LD", "labelZh": "勞工處", "rel": "official/ld_logo.png", "kind": "hsww"},
]

WX_ICONS = [
    {"code": f"pic{code}", "labelZh": name, "rel": f"official/wxicon/pic{code}.png", "kind": "wx"}
    for code, name in WX_NAMES.items()
]

WARN_LABELS = {
    "TC1": "一號戒備信號",
    "TC3": "三號強風信號",
    "TC8NE": "八號東北",
    "TC8SE": "八號東南",
    "TC8NW": "八號西北",
    "TC8SW": "八號西南",
    "TC9": "九號烈風",
    "TC10": "十號颶風",
    "WRAINA": "黃色暴雨",
    "WRAINR": "紅色暴雨",
    "WRAINB": "黑色暴雨",
    "WTS": "雷暴警告",
    "WL": "山泥傾瀉",
    "WHOT": "酷熱天氣",
    "WMSGNL": "強烈季候風",
    "WCOLD": "寒冷天氣",
    "WFIREY": "黃色火災危險",
    "WFIRER": "紅色火災危險",
    "WFROST": "霜凍",
    "WFNTSA": "新界北部水浸",
    "WTMW": "海嘯",
}


def build_case(name: str) -> dict:
    spec = _BY_ID.get(ALIASES.get(name, name))
    if spec is None:
        raise KeyError(name)
    site = validate_site({**SITE, **spec["site"]}) if spec.get("site") else SITE
    snap = build_snapshot(
        _hsww(spec.get("hsww", CANCELLED), spec.get("hswwAgo")),
        spec.get("warnsum") or {},
        spec.get("info") or {"details": []},
        _rhrread(spec.get("rhrreadAgo", 20)),
        site,
        SCHEDULE,
        ICONS,
        fnd=_fnd(spec.get("fndAgo", OLD)),
        now=SIM_NOW,
        stale=bool(spec.get("stale")),
    )
    if spec.get("stale"):
        snap["tone"] = "stale"
    return snap


def list_cases() -> list[dict]:
    return [
        {"id": spec["id"], "labelZh": spec["labelZh"], "group": spec["group"], "snapshot": build_case(spec["id"])}
        for spec in SPECS
    ]


def list_official_icons() -> list[dict]:
    warn = [
        {"code": code, "labelZh": WARN_LABELS.get(code, code), "rel": rel, "kind": "warning"}
        for code, rel in ICONS.items()
    ]
    return HSWW_ICONS + warn + WX_ICONS
