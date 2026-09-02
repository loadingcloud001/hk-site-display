ACTIVE = {"ISSUE", "REISSUE", "EXTEND", "UPDATE"}


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
