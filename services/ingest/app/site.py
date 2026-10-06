"""Site configuration: validation and the trade lists the screen works from."""

WORKLOADS = ("light", "moderate", "heavy", "very_heavy")
ENVIRONMENTS = ("outdoor", "indoor", "aircon")
# Official labels, Labour Department guidance notes Appendix 1.
WORKLOAD_ZH = {"light": "輕勞動", "moderate": "中等勞動", "heavy": "重勞動", "very_heavy": "極重勞動"}
FALLBACK_STATION = "香港天文台"


def _adjust_ok(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value % 15 == 0
        and -30 <= value <= 60
    )


def validate_site(site):
    errors = []
    env = site.get("environment", "outdoor")
    if env not in ENVIRONMENTS:
        errors.append(f"environment {env!r} must be one of {ENVIRONMENTS}")
    if site.get("defaultWorkload", "very_heavy") not in WORKLOADS:
        errors.append(f"defaultWorkload must be one of {WORKLOADS}")
    if not _adjust_ok(site.get("restAdjustMinutes", 0)):
        errors.append("restAdjustMinutes must be a multiple of 15 between -30 and 60")
    for i, trade in enumerate(site.get("primaryTrades") or []):
        where = f"primaryTrades[{i}]"
        if not trade.get("labelZh"):
            errors.append(f"{where}.labelZh is required")
        if trade.get("workload") not in WORKLOADS:
            errors.append(f"{where}.workload must be one of {WORKLOADS}")
        if trade.get("environment", env) not in ENVIRONMENTS:
            errors.append(f"{where}.environment must be one of {ENVIRONMENTS}")
        if "adjustMinutes" in trade and not _adjust_ok(trade["adjustMinutes"]):
            errors.append(f"{where}.adjustMinutes must be a multiple of 15 between -30 and 60")
    if errors:
        raise ValueError("site config: " + "; ".join(errors))
    return site


def configured_trades(site):
    env = site.get("environment", "outdoor")
    adjust = site.get("restAdjustMinutes", 0)
    return [
        {
            "id": t.get("id") or t["labelZh"],
            "labelZh": t["labelZh"],
            "workload": t["workload"],
            "environment": t.get("environment", env),
            "adjustMinutes": t.get("adjustMinutes", adjust),
        }
        for t in site.get("primaryTrades") or []
    ]


def tile_trades(site):
    """Trades for the heat-stress tiles; one row per workload level when none are configured."""
    trades = configured_trades(site)
    if trades:
        return trades
    env = site.get("environment", "outdoor")
    adjust = site.get("restAdjustMinutes", 0)
    return [
        {"id": wl, "labelZh": WORKLOAD_ZH[wl], "workload": wl, "environment": env, "adjustMinutes": adjust}
        for wl in WORKLOADS
    ]


def normal_workloads(site):
    trades = configured_trades(site)
    return {t["workload"] for t in trades} or {site.get("defaultWorkload", "very_heavy")}


def weather_station(site):
    return site.get("weatherStation") or site.get("district") or FALLBACK_STATION
