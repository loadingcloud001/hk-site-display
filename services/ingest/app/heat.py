"""Heat Stress at Work Warning: rest tiles per trade, and the normal-day rest lines."""
from app.rest import compute_rest

TILE_ORDER = {"suspend": 0, "rest": 1, "baseline": 2}
MAX_NAMES = 3


def trades_label(names):
    shown = " · ".join(names[:MAX_NAMES])
    more = len(names) - MAX_NAMES
    return f"{shown} +{more}" if more > 0 else shown


def build_rest_tiles(schedule, trades, level):
    """Group trades with the same result; 暫停工作 first, then most rest, then the 2-hour baselines."""
    groups = {}
    for trade in trades:
        result = compute_rest(schedule, trade["environment"], level, trade["workload"], trade["adjustMinutes"])
        group = groups.setdefault((result["kind"], result["rest"]), {**result, "trades": []})
        group["trades"].append(trade["labelZh"])
    tiles = sorted(groups.values(), key=lambda t: (TILE_ORDER[t["kind"]], -t["rest"]))
    for tile in tiles:
        tile["tradesZh"] = trades_label(tile["trades"])
    return tiles


def normal_rest_lines(schedule, workloads):
    """Guidance para 4.7.1: light to moderate >=10 min, heavy to very heavy >=15 min, per 2 hours worked."""
    base = schedule["baseline"]
    hours = base["perHours"]
    heavy = bool(set(workloads) & {"heavy", "very_heavy"})
    light = bool(set(workloads) & {"light", "moderate"})
    if heavy and light:
        return [
            f"重至極重勞動：每 {hours} 小時休息 {base['very_heavy']} 分鐘",
            f"輕至中等勞動：每 {hours} 小時休息 {base['light']} 分鐘",
        ]
    rest = base["very_heavy"] if heavy else base["light"]
    return [f"每 {hours} 小時休息 {rest} 分鐘"]
