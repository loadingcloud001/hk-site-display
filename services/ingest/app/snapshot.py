from datetime import datetime, timedelta, timezone

from app.actions import load_actions, note_text, validate_actions, weather_by_code
from app.banner import build_banner
from app.heat import build_rest_tiles, normal_rest_lines
from app.hko import PRE8_NAME, active_codes, parse_warning_info, parse_warnsum, parse_warnsum_events
from app.hsww import parse_hkhi_icon
from app.priority import classify
from app.rest import compute_rest
from app.site import WORKLOAD_ZH, normal_workloads, tile_trades, weather_station
from app.state import state_tone, supervisor_lines, tc_signal_code, winning_weather_code
from app.weather import parse_current, parse_forecast, parse_time, wx_icon_rel

HKT = timezone(timedelta(hours=8))
ACTIONS = validate_actions(load_actions())
WEATHER = weather_by_code(ACTIONS)

P0 = {"TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC8", "TC9", "TC10", "WRAINB", "WL"}
P1 = {"TC3", "WRAINR", "WTS", "WTCPRE8"}

PRE8_CAPTION = PRE8_NAME
IDLE_HERO = "status/work-ok.png"
HSWW_LABEL = {
    "amber": "黃色工作暑熱警告",
    "red": "紅色工作暑熱警告",
    "black": "黑色工作暑熱警告",
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
    return c in P0 or c in {"WRAINR", "WTCPRE8", "WTMW"}


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
        # HKO publishes no Pre-8 icon; the screen shows the signal in force instead.
        out.append({"code": "WTCPRE8", "rel": None, "labelZh": PRE8_CAPTION, "kind": "weather", "impact": "high"})
    out.sort(key=lambda s: code_rank(s["code"]))
    return out


def _clock(value):
    at = parse_time(value)
    return at.astimezone(HKT).strftime("%H:%M") if at else None


def _weather_display(code, warnings, info, icons_map, codes):
    spec = WEATHER[code]
    if code == "WTCPRE8":
        name = PRE8_NAME
        at = next((i.get("updateTime") for i in info if i.get("code") == "WTCPRE8"), None)
        signal = tc_signal_code(codes)
        hero = icons_map.get(signal) if signal else None
    else:
        warning = next((w for w in warnings if w["code"] == code), {})
        name = (warning.get("type") or warning.get("name") or "").strip()
        at = warning.get("issueTime")
        hero = icons_map.get(code)
    clock = _clock(at)
    meta = f"{name} · {clock} 發出" if name and clock else (name or None)
    return {"mode": "weather", "main": spec["main"], "sub": list(spec.get("sub") or []), "meta": meta, "heroRel": hero}


def _heat_display(hsww):
    title = hsww.get("titleZh") or HSWW_LABEL.get(hsww.get("level"), "工作暑熱警告")
    clock = _clock(hsww.get("effectiveAt"))
    meta = f"{title} · {clock} 生效" if clock else title
    return {"mode": "heat", "main": None, "sub": [], "meta": meta, "heroRel": hsww.get("iconRel")}


def _legacy_fields(display, rest, hsww):
    """`action` / `actionSub` for the kiosk deployed before this change."""
    mode = display["mode"]
    if mode == "weather":
        return {"action": display["main"], "actionSub": (display["sub"] or [display["meta"] or ""])[0]}
    if mode == "heat":
        if rest["kind"] == "suspend":
            return {"action": "暫停工作", "actionSub": hsww.get("titleZh") or "工作暑熱警告"}
        if rest["kind"] == "baseline":
            return {"action": f"休息 {rest['rest']} 分鐘", "actionSub": f"每 {rest['perHours']} 小時"}
        return {"action": f"休息 {rest['rest']} 分鐘", "actionSub": f"工作 {rest['work']} 分鐘"}
    return {"action": "正常工作", "actionSub": display["sub"][0] if display["sub"] else ""}


def _legacy_rest(rest):
    if rest["kind"] == "suspend":
        return {"work": 0, "rest": 60, "suspend": True}
    if rest["kind"] == "baseline":
        return {"work": 120, "rest": rest["rest"], "suspend": False, "perHours": rest["perHours"]}
    return {"work": rest["work"], "rest": rest["rest"], "suspend": False}


def build_snapshot(
    hsww_raw,
    warnsum,
    warning_info,
    rhrread,
    site,
    schedule,
    icons_map,
    generated_at=None,
    fnd=None,
    now=None,
    stale=False,
    position=None,
):
    now = now or datetime.now(HKT)
    hsww = parse_hkhi_icon(hsww_raw or {})
    warnings = parse_warnsum(warnsum or {})
    events = parse_warnsum_events(warnsum or {})
    info = parse_warning_info(warning_info or {})
    codes = active_codes(warnsum or {})
    for item in info:
        if item["code"] == "WTCPRE8" and "WTCPRE8" not in codes:
            codes.append("WTCPRE8")
    pri = classify(codes, hsww["level"])
    workload = site.get("defaultWorkload", "very_heavy")
    rest = compute_rest(
        schedule, site.get("environment", "outdoor"), hsww["level"], workload, site.get("restAdjustMinutes", 0)
    )
    icons = [{"code": w["code"], "rel": icons_map[w["code"]]} for w in warnings if icons_map.get(w["code"])]
    wx_icon = wx_icon_rel(rhrread["icon"][0]) if isinstance(rhrread, dict) and rhrread.get("icon") else None
    generated = generated_at or datetime.now(HKT).isoformat(timespec="seconds")
    clock = _clock(generated) or datetime.now(HKT).strftime("%H:%M")
    trades = site.get("primaryTrades") or []
    trade = trades[0] if trades else {}
    signals = build_signals(hsww, warnings, codes, icons_map)
    labels = {s["code"]: s["labelZh"] for s in signals}

    weather_code = winning_weather_code(codes)
    rest_tiles, notes, supervisor = [], [], []
    if weather_code:
        display = _weather_display(weather_code, warnings, info, icons_map, codes)
    elif hsww.get("inForce"):
        display = _heat_display(hsww)
        rest_tiles = build_rest_tiles(schedule, tile_trades(site), hsww["level"])
        notes = [note_text(ACTIONS, "heatUnacclimatised")]
    else:
        display = {
            "mode": "normal",
            "main": "正常工作",
            "sub": normal_rest_lines(schedule, normal_workloads(site)),
            "meta": None,
            "heroRel": IDLE_HERO,
        }
    if display["mode"] != "weather":
        supervisor = supervisor_lines(ACTIONS, codes, labels)
    display.update(_legacy_fields(display, rest, hsww))

    return {
        "generatedAt": generated,
        "clock": clock,
        "staleAfterSec": 600,
        "stale": bool(stale),
        "tone": state_tone(display["mode"], weather_code, hsww["level"]),
        "site": {
            "id": site.get("siteId"),
            "nameZh": site.get("nameZh"),
            "tradeZh": trade.get("labelZh") or "",
            "workloadZh": WORKLOAD_ZH.get(workload, workload),
        },
        "hsww": hsww,
        "hko": {
            "warnsum": warnings,
            "warningInfo": info,
            "icons": icons,
            "wxIconRel": wx_icon,
            "headlineZh": weather_caption(warnings, info),
        },
        "signals": signals,
        "display": display,
        "priority": pri,
        "rest": _legacy_rest(rest),
        "restTiles": rest_tiles,
        "notes": notes,
        "supervisor": supervisor,
        "banner": build_banner(hsww, events, info, now, code_rank, stale),
        "weather": parse_current(rhrread, weather_station(site), now, position),
        "forecast": parse_forecast(fnd, now),
    }
