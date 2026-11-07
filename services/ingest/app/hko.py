# Official names, HKO Open Data API documentation (TC and EN), warningStatementCode WTCPRE8.
PRE8_NAME = "預警八號熱帶氣旋警告信號之特別報告"
PRE8_NAME_EN = "Pre-no.8 Special Announcement"

ACTIVE = {"ISSUE", "REISSUE", "EXTEND", "UPDATE"}

# For these warnings warnsum's `type` is only the colour (黃色, Amber) and `name` is the warning (暴雨警告信號,
# Rainstorm Warning Signal); the official name is the two together (HKO Open Data API documentation, warnsum).
COLOUR_TYPED = ("WRAIN", "WFIRE")


def warning_name(item, lang="zh"):
    """Official name of a warnsum entry, in the feed's language.

    Tropical cyclone signals: `type` (八號東北烈風或暴風信號). Rainstorm and fire danger warnings: colour and
    name (黃色暴雨警告信號, Amber Rainstorm Warning Signal). Anything else: `name`.
    """
    name = (item.get("name") or "").strip()
    kind = (item.get("type") or "").strip()
    if not kind:
        return name
    if (item.get("code") or "").startswith(COLOUR_TYPED) and name and name not in kind:
        return f"{kind} {name}" if lang == "en" else f"{kind}{name}"
    return kind


def parse_warnsum(raw: dict) -> list[dict]:
    out = []
    if not isinstance(raw, dict):
        return out
    for key, item in raw.items():
        if not isinstance(item, dict):
            continue
        code = item.get("code") or key
        action = item.get("actionCode")
        if action not in ACTIVE:
            continue
        if code == "CANCEL":
            continue
        out.append(
            {
                "key": key,
                "code": code,
                "name": item.get("name") or "",
                "type": item.get("type") or "",
                "actionCode": action,
                "issueTime": item.get("issueTime"),
                "updateTime": item.get("updateTime"),
                "expireTime": item.get("expireTime"),
            }
        )
    return out


def active_codes(raw: dict) -> list[str]:
    return [w["code"] for w in parse_warnsum(raw)]


def parse_warning_info(raw: dict) -> list[dict]:
    details = raw.get("details") if isinstance(raw, dict) else None
    if not details:
        return []
    out = []
    for d in details:
        if not isinstance(d, dict):
            continue
        contents = d.get("contents") or []
        if not isinstance(contents, list):
            contents = [str(contents)]
        out.append(
            {
                "code": d.get("warningStatementCode") or d.get("subtype") or "",
                "subtype": d.get("subtype"),
                "contents": [str(c) for c in contents],
                "updateTime": d.get("updateTime"),
            }
        )
    return out


def parse_warnsum_events(raw: dict) -> list[dict]:
    """Every warnsum entry with its action and times, cancellations included (for the change banner)."""
    out = []
    if not isinstance(raw, dict):
        return out
    for key, item in raw.items():
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "key": key,
                "code": item.get("code") or key,
                "name": (item.get("name") or "").strip(),
                "type": (item.get("type") or "").strip(),
                "actionCode": item.get("actionCode") or "",
                "issueTime": item.get("issueTime"),
                "updateTime": item.get("updateTime"),
            }
        )
    return out
