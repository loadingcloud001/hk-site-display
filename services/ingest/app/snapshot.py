from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

from app.hko import parse_warnsum, parse_warning_info, active_codes
from app.hsww import parse_hkhi_icon
from app.priority import classify
from app.rest import lookup

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
ACTIONS = json.loads((ROOT / "config" / "display_actions.json").read_text(encoding="utf-8"))

P0 = {"TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC8", "TC9", "TC10", "WRAINB", "WL"}
P1 = {"TC3", "WRAINR", "WTS", "WTCPRE8"}


PRE8_CAPTION = "預警八號熱帶氣旋警告信號"
HSWW_LABEL = {
    "amber": "黃色工作暑熱警告",
    "red": "紅色工作暑熱警告",
    "black": "黑色工作暑熱警告",
}
WORKLOAD_ZH = {
    "light": "輕勞動",
    "moderate": "中勞動",
    "heavy": "重勞動",
    "very_heavy": "極重勞動",
}


def code_rank(code: str) -> int:
    c = code or ""
    if c == "TC10":
        return 0
    if c == "TC9":
        return 1
    if c.startswith("TC8"):
        return 2
    if c == "WRAINB":
        return 3
    if c == "WL":
        return 4
    if c in P1 or c == "WTCPRE8":
        return 10
    if c.startswith("HSWW"):
        return 20
    return 30


def is_high_impact(code: str, kind: str = "") -> bool:
    c = code or ""
    if kind == "hsww" or c.startswith("HSWW"):
        return True
    return c in P0 or c == "WRAINR"


def build_display(hsww: dict, rest: dict, signals: list) -> dict:
    weather = ACTIONS.get("weather") or {}
    for s in signals or []:
        spec = weather.get(s.get("code") or "")
        if not spec:
            continue
        return {
            "action": spec["action"],
            "actionSub": spec.get("sub") or s.get("labelZh") or "",
        }
    if rest.get("suspend"):
        return {
            "action": "暫停工作",
            "actionSub": hsww.get("titleZh") or "工作暑熱警告",
        }
    if hsww.get("inForce"):
        return {
            "action": f"休息 {rest.get('rest', 0)} 分鐘",
            "actionSub": f"工作 {rest.get('work', 0)} 分鐘",
        }
    per = rest.get("perHours") or 2
    return {
        "action": "正常工作",
        "actionSub": f"每 {per} 小時休息 {rest.get('rest', 10)} 分鐘",
    }


def weather_caption(warnings: list, info: list) -> str:
    """Canteen line: warnsum type/name, never bulletin contents[0]."""
    if warnings:
        w = sorted(warnings, key=lambda item: code_rank(item.get("code") or ""))[0]
        return (w.get("type") or w.get("name") or "").strip()
    for item in info or []:
        if item.get("code") == "WTCPRE8" or item.get("subtype") == "WTCPRE8":
            return PRE8_CAPTION
    return ""


def build_signals(hsww: dict, warnings: list, codes: list, icons_map: dict) -> list:
    out = []
    if hsww.get("inForce") and hsww.get("iconRel"):
        level = hsww.get("level") or "amber"
        out.append(
            {
                "code": f"HSWW-{level}",
                "rel": hsww["iconRel"],
                "labelZh": hsww.get("titleZh") or HSWW_LABEL.get(level, "工作暑熱警告"),
                "kind": "hsww",
                "impact": "high",
            }
        )
    seen = set()
    for w in warnings:
        code = w.get("code") or ""
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(
            {
                "code": code,
                "rel": icons_map.get(code),
                "labelZh": (w.get("type") or w.get("name") or "").strip(),
                "kind": "weather",
                "impact": "high" if is_high_impact(code, "weather") else "low",
            }
        )
    if "WTCPRE8" in (codes or []) and "WTCPRE8" not in seen:
        out.append(
            {
                "code": "WTCPRE8",
                "rel": None,
                "labelZh": PRE8_CAPTION,
                "kind": "weather",
                "impact": "low",
            }
        )
    out.sort(key=lambda s: code_rank(s["code"]))
    return out


def snapshot_tone(pri: dict, hsww: dict, codes: list, stale: bool = False) -> str:
    if stale:
        return "stale"
    codeset = set(codes or [])
    band = pri.get("band")
    if band == "P0":
        if "WRAINB" in codeset:
            return "p0-rain"
        if "WL" in codeset:
            return "p0-landslip"
        return "p0-tc"
    if hsww.get("inForce"):
        return hsww.get("level") or "idle"
    if band == "P1":
        return "p1"
    if band == "P3":
        return "watch"
    return "idle"


def build_snapshot(
    hsww_raw,
    warnsum,
    warning_info,
    rhrread,
    site,
    schedule,
    icons_map,
    generated_at=None,
):
    hsww = parse_hkhi_icon(hsww_raw or {})
    warnings = parse_warnsum(warnsum or {})
    info = parse_warning_info(warning_info or {})
    codes = active_codes(warnsum or {})
    for item in info:
        if item["code"] == "WTCPRE8" and "WTCPRE8" not in codes:
            codes.append("WTCPRE8")
    pri = classify(codes, hsww["level"])
    env = site.get("environment", "outdoor")
    wl = site.get("defaultWorkload", "very_heavy")
    rest = lookup(schedule, env, hsww["level"], wl, site.get("restAdjustMinutes", 0))
    icons = []
    for w in warnings:
        rel = icons_map.get(w["code"])
        if rel:
            icons.append({"code": w["code"], "rel": rel})
    wx_icon = None
    if isinstance(rhrread, dict):
        ic = rhrread.get("icon") or []
        if ic:
            wx_icon = f"official/wxicon/pic{ic[0]}.png"
    now_dt = datetime.now(HKT)
    now = generated_at or now_dt.isoformat(timespec="seconds")
    try:
        clock_src = datetime.fromisoformat(now.replace("Z", "+00:00"))
        clock = clock_src.astimezone(HKT).strftime("%H:%M")
    except Exception:
        clock = now_dt.strftime("%H:%M")
    trades = site.get("primaryTrades") or []
    trade = trades[0] if trades else {}
    caption = weather_caption(warnings, info)
    signals = build_signals(hsww, warnings, codes, icons_map)
    rest_display = build_display(hsww, rest, signals)
    tone = snapshot_tone(pri, hsww, codes, False)
    if rest_display.get("action") == "正常工作":
        tone = "idle"
    return {
        "generatedAt": now,
        "clock": clock,
        "staleAfterSec": 600,
        "stale": False,
        "tone": tone,
        "site": {
            "id": site.get("siteId"),
            "nameZh": site.get("nameZh"),
            "tradeZh": trade.get("labelZh") or "",
            "workloadZh": WORKLOAD_ZH.get(wl, wl),
        },
        "hsww": hsww,
        "hko": {
            "warnsum": warnings,
            "warningInfo": info,
            "icons": icons,
            "wxIconRel": wx_icon,
            "rhrread": rhrread or {},
            "headlineZh": caption,
        },
        "signals": signals,
        "display": rest_display,
        "priority": pri,
        "rest": rest,
    }
