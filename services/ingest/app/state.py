"""Which state the screen is in, its tone, and the supervisor lines."""
from app.actions import ZH_JOIN, english_text

# Spec §4.2: instructions to stay sheltered outrank instructions to leave.
WEATHER_ORDER = ["TC10", "TC9", "WRAINB", "TC8NE", "TC8SE", "TC8NW", "TC8SW", "WL", "WTMW", "WTCPRE8", "WRAINR"]
TC_SIGNALS = ("TC1", "TC3", "TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10")
MAX_SUPERVISOR = 2


def winning_weather_code(codes):
    present = set(codes or [])
    return next((code for code in WEATHER_ORDER if code in present), None)


def state_tone(mode, code, level):
    if mode == "weather":
        if code in ("TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10"):
            return "p0-tc"
        if code == "WRAINB":
            return "p0-rain"
        if code == "WL":
            return "p0-landslip"
        if code == "WTMW":
            return "watch"
        return "p1"
    if mode == "heat":
        return level
    return "idle"


def supervisor_lines(actions, codes, labels, labels_en=None, after=None):
    """Official supervisor instructions, by rank, at most two: for warnings in force, and the line shown for a
    while after a signal ended (`after`: {code, fromZh, whenZh, fromEn}, from app.after, or None).

    With `labels_en` (HKO's English names by code, for a site that shows English) each line also gets its
    official English (`textEn`) and the warning's English name (`fromEn`); either is None when there is none.
    """
    present = set(codes or [])
    hits = []
    for spec in (actions.get("supervisor") or {}).values():
        if "after" in spec:
            if not after or after["code"] not in spec["after"]:
                continue
            line = {"text": ZH_JOIN.join(spec["fragments"]), "fromZh": after["fromZh"], "whenZh": after["whenZh"]}
            name_en = after.get("fromEn")
        else:
            code = next((c for c in spec["codes"] if c in present), None)
            if not code:
                continue
            line = {"text": ZH_JOIN.join(spec["fragments"]), "fromZh": labels.get(code) or code}
            name_en = labels_en.get(code) if labels_en is not None else None
        if labels_en is not None:
            line["textEn"] = english_text(spec)
            line["fromEn"] = name_en
        hits.append((spec["rank"], line))
    hits.sort(key=lambda hit: hit[0])
    return [line for _, line in hits[:MAX_SUPERVISOR]]


def tc_signal_code(codes):
    return next((code for code in codes or [] if code in TC_SIGNALS), None)
