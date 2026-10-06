"""Which state the screen is in, its tone, and the supervisor lines."""

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


def supervisor_lines(actions, codes, labels):
    """Official supervisor instructions for warnings in force, most severe first, at most two."""
    present = set(codes or [])
    hits = []
    for spec in (actions.get("supervisor") or {}).values():
        code = next((c for c in spec["codes"] if c in present), None)
        if code:
            hits.append((spec["rank"], "：".join(spec["fragments"]), labels.get(code) or code))
    hits.sort(key=lambda hit: hit[0])
    return [{"text": text, "fromZh": label} for _, text, label in hits[:MAX_SUPERVISOR]]


def tc_signal_code(codes):
    return next((code for code in codes or [] if code in TC_SIGNALS), None)
