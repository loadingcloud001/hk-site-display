"""Site configuration: validation, loading every site file, and the trade lists the screen works from."""
import json
from pathlib import Path

from app.stations import OBSERVATORY, station_names, wind_station_names

WORKLOADS = ("light", "moderate", "heavy", "very_heavy")
ENVIRONMENTS = ("outdoor", "indoor", "aircon")
# Official labels, Labour Department guidance notes Appendix 1.
WORKLOAD_ZH = {"light": "輕勞動", "moderate": "中等勞動", "heavy": "重勞動", "very_heavy": "極重勞動"}


def _adjust_ok(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value % 15 == 0
        and -30 <= value <= 60
    )


def validate_site(site, where="site config"):
    if not isinstance(site, dict):
        raise ValueError(f"{where}: must be a JSON object")
    errors = []
    env = site.get("environment", "outdoor")
    if env not in ENVIRONMENTS:
        errors.append(f"environment {env!r} must be one of {ENVIRONMENTS}")
    if site.get("defaultWorkload", "very_heavy") not in WORKLOADS:
        errors.append(f"defaultWorkload must be one of {WORKLOADS}")
    if not _adjust_ok(site.get("restAdjustMinutes", 0)):
        errors.append("restAdjustMinutes must be a multiple of 15 between -30 and 60")
    station = site.get("weatherStation")
    if station is not None and (not isinstance(station, str) or station not in station_names()):
        errors.append(f"weatherStation {station!r} is not an HKO temperature station (see config/hko_stations.json)")
    wind = site.get("windStation")
    if wind is not None and (not isinstance(wind, str) or wind not in wind_station_names()):
        errors.append(f"windStation {wind!r} is not an HKO wind station (see config/hko_stations.json)")
    site_id = site.get("siteId")
    if site_id is not None and (not isinstance(site_id, str) or not site_id.strip()):
        errors.append("siteId must be a non-empty string")
    trades = site.get("primaryTrades") or []
    if not isinstance(trades, list):
        errors.append("primaryTrades must be a list")
        trades = []
    for i, trade in enumerate(trades):
        trade_at = f"primaryTrades[{i}]"
        if not isinstance(trade, dict):
            errors.append(f"{trade_at} must be an object")
            continue
        if not trade.get("labelZh") or not isinstance(trade["labelZh"], str):
            errors.append(f"{trade_at}.labelZh is required")
        if trade.get("workload") not in WORKLOADS:
            errors.append(f"{trade_at}.workload must be one of {WORKLOADS}")
        if trade.get("environment", env) not in ENVIRONMENTS:
            errors.append(f"{trade_at}.environment must be one of {ENVIRONMENTS}")
        if "adjustMinutes" in trade and not _adjust_ok(trade["adjustMinutes"]):
            errors.append(f"{trade_at}.adjustMinutes must be a multiple of 15 between -30 and 60")
    if errors:
        raise ValueError(f"{where}: " + "; ".join(errors))
    return site


# Used for a screen whose ?site= names no site file: every workload level, outdoor, no adjustment. That is the
# Labour Department table itself, so the screen stays correct, just without trade names.
GENERIC_SITE = {"siteId": None, "environment": "outdoor", "restAdjustMinutes": 0, "primaryTrades": []}
DEMO_FILE = "demo-site.json"


def load_sites(directory, wanted=None):
    """(siteId -> validated site, default siteId or None, problems) for every *.json in `directory`.

    A file that cannot be read or is not valid is left out and named in `problems`, so a mistake in one site's
    file never takes the other sites' screens down. Screens of a left-out site show GENERIC_SITE until the file
    is fixed. Two files with one siteId are both left out, because either could be the wrong one.

    The default is what a screen without ?site= shows: DEFAULT_SITE (`wanted`), else the demo site, else the
    only site file. None means GENERIC_SITE. It never falls to another site because a file was left out.
    """
    found, problems = {}, []
    files = sorted(Path(directory).glob("*.json"))
    for path in files:
        where = f"config/sites/{path.name}"
        try:
            site = validate_site(json.loads(path.read_text(encoding="utf-8")), where=where)
        except Exception as error:  # any mistake in a hand-edited file; reported, never fatal
            text = str(error)
            problems.append(text if text.startswith(where) else f"{where}: {text}")
            continue
        found.setdefault(site.get("siteId") or path.stem, []).append((path.name, site))
    sites, demo = {}, None
    for site_id, entries in found.items():
        if len(entries) > 1:
            names = ", ".join(f"config/sites/{name}" for name, _ in entries)
            problems.append(f"siteId {site_id!r} is in {names}; none of them is used")
            continue
        name, site = entries[0]
        sites[site_id] = site
        if name == DEMO_FILE:
            demo = site_id

    default = None
    if wanted:
        if wanted in sites:
            default = wanted
        else:
            problems.append(f"DEFAULT_SITE {wanted!r} is not a usable siteId in config/sites")
    elif any(path.name == DEMO_FILE for path in files):
        default = demo  # None when the demo file itself was left out
    elif len(files) == 1:
        default = next(iter(sites), None)
    elif not files:
        problems.append(f"no site file in {directory}")
    else:
        problems.append("several site files and no demo-site.json: set DEFAULT_SITE")
    return sites, default, problems


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
    """The station shown when the screen has no usable position."""
    return site.get("weatherStation") or OBSERVATORY


def wind_station(site):
    """The wind station shown when the screen has no usable position, or None to hide the wind."""
    return site.get("windStation")
