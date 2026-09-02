LEVEL = {30: "amber", 32: "red", 34: "black"}
ICON = {
    30: "official/hkhi_yellow.png",
    32: "official/hkhi_red.png",
    34: "official/hkhi_black.png",
}


def parse_hkhi_icon(raw: dict) -> dict:
    idx = int(raw.get("iconIndex", -1))
    level = LEVEL.get(idx, "none")
    in_force = idx in LEVEL
    return {
        "level": level,
        "inForce": in_force,
        "cancelled": idx == -1,
        "iconIndex": idx,
        "titleZh": raw.get("TitleTC") or "",
        "noticeZh": raw.get("MessageTC2") or "",
        "noticeLeadZh": raw.get("MessageTC1") or "",
        "issuedAt": raw.get("date") or "",
        "iconRel": ICON.get(idx),
        "ldLogoRel": "official/ld_logo.png",
        "source": "hko-hkhi-icon",
    }
