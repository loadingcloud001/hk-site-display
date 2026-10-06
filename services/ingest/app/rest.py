def lookup(schedule, environment, hsww_level, workload, adjust_minutes=0):
    level = hsww_level if hsww_level in ("amber", "red", "black") else "none"
    row = dict(schedule[environment][level][workload])
    if row.get("suspend"):
        return {**row, "work": 0, "rest": 60, "suspend": True}
    rest = max(0, int(row.get("rest", 0)) + int(adjust_minutes or 0))
    work = int(row.get("work", 60))
    if rest == 0 and level != "none":
        return {**row, "work": work, "rest": 0, "suspend": False}
    if rest <= 0 and level == "none":
        return {**row, "rest": row.get("rest", 10), "suspend": False}
    return {**row, "work": work, "rest": rest, "suspend": False}


LEVELS = ("amber", "red", "black")


def compute_rest(schedule, environment, level, workload, adjust_minutes=0):
    """Hourly rest for one trade under a Heat Stress at Work Warning.

    Labour Department guidance notes (3rd ed., Aug 2026) para 5.5.2: start from
    Appendix 4, apply the environment and employer adjustments, suspend work at
    60 minutes or more (5.4.5) and fall back to the 2-hour baseline at zero or
    less (5.5.4). Air-conditioned indoor work needs no hourly rest (footnote 4).
    """
    base = schedule["baseline"]
    baseline = {"kind": "baseline", "rest": base[workload], "work": None, "perHours": base["perHours"]}
    if level not in LEVELS or environment == "aircon":
        return baseline
    rest = (
        int(schedule["outdoor"][level][workload]["rest"])
        + int(schedule["environmentAdjust"][environment])
        + int(adjust_minutes or 0)
    )
    if rest >= 60:
        return {"kind": "suspend", "rest": 60, "work": 0, "perHours": 1}
    if rest <= 0:
        return baseline
    return {"kind": "rest", "rest": rest, "work": 60 - rest, "perHours": 1}
