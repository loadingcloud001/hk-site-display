"""Heat Stress at Work Warning: rest tiles per trade, and the normal-day rest lines."""
from app.actions import tile_lines_en
from app.rest import compute_rest

TILE_ORDER = {"suspend": 0, "rest": 1, "baseline": 2}
MAX_NAMES = 3


def trades_label(names):
    shown = " · ".join(names[:MAX_NAMES])
    more = len(names) - MAX_NAMES
    return f"{shown} +{more}" if more > 0 else shown


def _trade_en(trade, workload_labels):
    """A trade's English name: the site's labelEn, or the official workload level on the generic site."""
    if trade.get("labelEn"):
        return trade["labelEn"]
    return workload_labels.get(trade["workload"]) if trade.get("generic") else None


def build_rest_tiles(schedule, trades, level, rest_en=None):
    """Group trades with the same result; 暫停工作 first, then most rest, then the 2-hour baselines.

    With `rest_en` (display_actions.json `rest`, for a site that shows English) each tile also gets `en`: its
    official English lines, and the trades' English names when every trade on the tile has one.
    """
    groups = {}
    for trade in trades:
        result = compute_rest(schedule, trade["environment"], level, trade["workload"], trade["adjustMinutes"])
        group = groups.setdefault((result["kind"], result["rest"]), {**result, "trades": [], "_en": []})
        group["trades"].append(trade["labelZh"])
        group["_en"].append(trade)
    tiles = sorted(groups.values(), key=lambda t: (TILE_ORDER[t["kind"]], -t["rest"]))
    for tile in tiles:
        members = tile.pop("_en")
        tile["tradesZh"] = trades_label(tile["trades"])
        if rest_en is not None:
            labels = rest_en["workloads"]["en"]["labels"]
            names = [_trade_en(trade, labels) for trade in members]
            tile["en"] = {
                "trades": trades_label(names) if all(names) else None,
                "lines": tile_lines_en(tile, rest_en["tile"]["en"]),
            }
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
