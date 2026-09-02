from datetime import datetime, timezone, timedelta

from app.hko import parse_warnsum, parse_warning_info, active_codes
from app.hsww import parse_hkhi_icon
from app.priority import classify
from app.rest import lookup

HKT = timezone(timedelta(hours=8))

P0 = {"TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC8", "TC9", "TC10", "WRAINB", "WL"}
P1 = {"TC3", "WRAINR", "WTS", "WTCPRE8"}


PRE8_CAPTION = "預警八號熱帶氣旋警告信號"


def weather_caption(warnings: list, info: list) -> str:
    """Canteen line: warnsum type/name, never bulletin contents[0]."""
    if warnings:

        def rank(w):
            c = w.get("code") or ""
            if c in P0:
                return 0
            if c in P1:
                return 1
            return 2

        w = sorted(warnings, key=rank)[0]
        return (w.get("type") or w.get("name") or "").strip()
    for item in info or []:
        if item.get("code") == "WTCPRE8" or item.get("subtype") == "WTCPRE8":
            return PRE8_CAPTION
    return ""


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
    caption = weather_caption(warnings, info)
    return {
        "generatedAt": now,
        "clock": clock,
        "staleAfterSec": 600,
        "stale": False,
        "tone": snapshot_tone(pri, hsww, codes, False),
        "site": {"id": site.get("siteId"), "nameZh": site.get("nameZh")},
        "hsww": hsww,
        "hko": {
            "warnsum": warnings,
            "warningInfo": info,
            "icons": icons,
            "wxIconRel": wx_icon,
            "rhrread": rhrread or {},
            "headlineZh": caption,
        },
        "priority": pri,
        "rest": rest,
    }
