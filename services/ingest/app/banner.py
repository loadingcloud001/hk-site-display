"""Change banner: 10 minutes after a warning is issued or cancelled. Stateless by design."""
from datetime import timedelta

from app.hko import PRE8_NAME
from app.weather import HKT, parse_time

BANNER_AFTER = timedelta(minutes=10)
# LD messages can announce an effective time a few minutes after they are sent.
BANNER_AHEAD = timedelta(minutes=15)
HSWW_NAME = "工作暑熱警告"
TC_SIGNAL_NAME = "熱帶氣旋警告信號"


def _recent(at, now):
    return at is not None and -BANNER_AHEAD <= now - at <= BANNER_AFTER


def build_banner(hsww, events, info, now, rank, stale=False):
    """Most severe recent issue/cancel event. `rank(code)` gives severity, lower is more severe."""
    if stale:
        return None
    candidates = []
    at = parse_time(hsww.get("effectiveAt"))
    if _recent(at, now):
        kind = hsww.get("messageKind")
        if kind == "issue" and hsww.get("inForce"):
            code = f"HSWW-{hsww.get('level')}"
            candidates.append((rank(code), at, "issue", code, f"{hsww.get('titleZh') or HSWW_NAME} 生效"))
        elif kind == "cancel":
            candidates.append((rank("HSWW"), at, "cancel", "HSWW", f"{HSWW_NAME} 取消"))
    for event in events:
        code, action = event["code"], event["actionCode"]
        label = event["type"] or event["name"]
        if code == "CANCEL" or action == "CANCEL":
            at = parse_time(event.get("updateTime") or event.get("issueTime"))
            name = (event["name"] or TC_SIGNAL_NAME) if code == "CANCEL" else label
            if _recent(at, now) and name:
                candidates.append((rank(code), at, "cancel", code, f"{name} 取消"))
        elif action == "ISSUE":
            at = parse_time(event.get("issueTime"))
            if _recent(at, now) and label:
                candidates.append((rank(code), at, "issue", code, f"{label} 發出"))
    for item in info:
        if item.get("code") == "WTCPRE8":
            at = parse_time(item.get("updateTime"))
            if _recent(at, now):
                candidates.append((rank("WTCPRE8"), at, "issue", "WTCPRE8", f"{PRE8_NAME} 發出"))
    if not candidates:
        return None
    best = min(candidates, key=lambda c: (c[0], -c[1].timestamp()))
    return {"time": best[1].astimezone(HKT).strftime("%H:%M"), "textZh": best[4], "kind": best[2], "code": best[3]}
