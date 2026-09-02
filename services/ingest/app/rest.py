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
