from datetime import datetime, timezone, timedelta

from app.hko import parse_warnsum, parse_warning_info, active_codes
from app.hsww import parse_hkhi_icon
from app.priority import classify
from app.rest import lookup

HKT = timezone(timedelta(hours=8))


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
    now = generated_at or datetime.now(HKT).isoformat(timespec="seconds")
    return {
        "generatedAt": now,
        "staleAfterSec": 600,
        "stale": False,
        "site": {"id": site.get("siteId"), "nameZh": site.get("nameZh")},
        "hsww": hsww,
        "hko": {
            "warnsum": warnings,
            "warningInfo": info,
            "icons": icons,
            "wxIconRel": wx_icon,
            "rhrread": rhrread or {},
        },
        "priority": pri,
        "rest": rest,
    }
