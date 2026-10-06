import re
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
LEVEL = {30: "amber", 32: "red", 34: "black"}
ICON = {
    30: "official/hkhi_yellow.png",
    32: "official/hkhi_red.png",
    34: "official/hkhi_black.png",
}
# "下午2時40分", "中午12時正" (Labour Department message templates, guidance notes Appendix 6)
_EFFECTIVE = re.compile(r"([上中下])午\s*(\d{1,2})\s*時\s*(?:(\d{1,2})\s*分|正)?")


def message_kind(text):
    """生效 = issue, 仍然生效 = hourly update, 取消 = cancel (guidance notes Appendix 6)."""
    t = text or ""
    if "仍然生效" in t:
        return "update"
    if "取消" in t:
        return "cancel"
    if "生效" in t:
        return "issue"
    return "other"


def message_time(date_str):
    try:
        return datetime.strptime(str(date_str), "%Y%m%d%H%M").replace(tzinfo=HKT)
    except (TypeError, ValueError):
        return None


def effective_time(text, date_str):
    """Time stated in the message ("今日下午2時40分"), on the message's date; else the message time."""
    sent = message_time(date_str)
    match = _EFFECTIVE.search(text or "")
    if sent is None or match is None:
        return sent
    half, hour, minute = match.group(1), int(match.group(2)), int(match.group(3) or 0)
    if half == "上" and hour == 12:
        hour = 0
    elif half == "下" and hour < 12:
        hour += 12
    if hour > 23 or minute > 59:
        return sent
    return sent.replace(hour=hour, minute=minute)


def parse_hkhi_icon(raw: dict) -> dict:
    idx = int(raw.get("iconIndex", -1))
    level = LEVEL.get(idx, "none")
    in_force = idx in LEVEL
    effective = effective_time(raw.get("MessageTC2"), raw.get("date"))
    return {
        "level": level,
        "inForce": in_force,
        "cancelled": idx == -1,
        "iconIndex": idx,
        "titleZh": raw.get("TitleTC") or "",
        "noticeZh": raw.get("MessageTC2") or "",
        "noticeLeadZh": raw.get("MessageTC1") or "",
        "issuedAt": raw.get("date") or "",
        "messageKind": message_kind(raw.get("MessageTC2")),
        "effectiveAt": effective.isoformat() if effective else None,
        "iconRel": ICON.get(idx),
        "ldLogoRel": "official/ld_logo.png",
        "source": "hko-hkhi-icon",
    }
