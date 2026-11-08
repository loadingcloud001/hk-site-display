import json
import logging
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import extreme
from app.alerts import engine_from_env
from app.feeds import Feed, FeedSet
from app.sim_cases import ALIASES, CASE_IDS, build_case, list_cases, list_official_icons
from app.site import GENERIC_SITE, load_sites
from app.snapshot import build_snapshot
from app.stations import parse_position
from app.wind import parse_wind_csv

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
HSWW_URL = "https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml"
WARN_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
WIND_URL = "https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_10min_wind_uc.csv"
POLL_SEC = 15
# The poller is wedged if it has not finished a cycle in this long (8 cycles).
POLLER_DEAD_AFTER = 120
STALE_AFTER = int(os.environ.get("STALE_AFTER_SEC", "600"))
ENABLE_SIM = os.environ.get("ENABLE_SIM", "true").lower() in ("1", "true", "yes")
ENABLE_POLLER = os.environ.get("ENABLE_LIVE_POLLER", "true").lower() in ("1", "true", "yes")

# Every site file is loaded and checked at start-up. Real site files live on the server, not in git.
# A bad file is left out and reported (log and /api/v1/health), never fatal: it must not blank other sites.
SITES_DIR = Path(os.environ.get("SITES_DIR") or ROOT / "config" / "sites")
SITES, DEFAULT_SITE, SITE_PROBLEMS = load_sites(SITES_DIR, os.environ.get("DEFAULT_SITE"))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))

log = logging.getLogger("hk_site_display")
if not log.handlers:  # uvicorn configures only its own loggers; without this, INFO lines such as alerts are lost
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
for _problem in SITE_PROBLEMS:
    log.error("site config problem: %s", _problem)

# Supervisor alerts (app.alerts): SMTP settings, ALERT_OPERATOR and the state file come from the environment.
ALERTS = engine_from_env(os.environ, SITES, ROOT, stale_after=STALE_AFTER)

# The 「極端情況」 switch (app/extreme.py). Its state lives in STATE_DIR, a Docker volume, so it survives restarts.
# ADMIN_KEY comes from the server's untracked .env (kept in Bitwarden); without it the admin endpoints are off.
STATE_DIR = Path(os.environ.get("STATE_DIR") or ROOT / "state")
ADMIN_KEY = extreme.usable_key(os.environ.get("ADMIN_KEY"))
EXTREME = extreme.ExtremeStore(STATE_DIR)
if ADMIN_KEY:
    EXTREME.check_writable()


def _get_json(client, url, params=None):
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _get_wind(client):
    response = client.get(WIND_URL)
    response.raise_for_status()
    return parse_wind_csv(response.content.decode("utf-8-sig"))


def _hko(data_type, lang="tc"):
    return lambda client: _get_json(client, WARN_URL, {"dataType": data_type, "lang": lang})


def make_feeds():
    return FeedSet(
        [
            Feed("hsww", lambda client: _get_json(client, HSWW_URL), 60),
            Feed("warnsum", _hko("warnsum"), 60),
            Feed("warningInfo", _hko("warningInfo"), 60),
            Feed("rhrread", _hko("rhrread"), 600),
            Feed("fnd", _hko("fnd"), 1800),
            # HKO updates the wind report every 10 minutes.
            Feed("wind", _get_wind, 300),
            # HKO's own English warning names, for sites that show English. Never decides what is in force, and
            # last in the cycle, so a slow English feed never holds up the Chinese ones.
            Feed("warnsumEn", _hko("warnsum", "en"), 60),
        ],
        lambda: httpx.Client(timeout=15.0),
    )


FEEDS = make_feeds()


class HidePosition(logging.Filter):
    """The screen's position is only used to pick a weather station, so keep it out of the access log."""

    PATTERN = re.compile(r"(?<=[?&])(lat|lon|acc)=[^&\s]*")

    def filter(self, record):
        args = record.args
        if isinstance(args, tuple) and len(args) > 2 and isinstance(args[2], str):
            record.args = (*args[:2], self.PATTERN.sub(r"\1=-", args[2]), *args[3:])
        return True


logging.getLogger("uvicorn.access").addFilter(HidePosition())


POLLER = {"last": None}


def _poll(stop):
    while not stop.is_set():
        try:
            FEEDS.refresh_due()
        except Exception:  # one bad cycle must never stop the screens' data for good
            log.exception("feed refresh failed")
        try:
            now = datetime.now(HKT)
            ALERTS.check(now, feed_marks(), snapshot_for(now))
        except Exception:  # alerts must never stop the screens' data either
            log.exception("alert check failed")
        POLLER["last"] = time.monotonic()
        stop.wait(POLL_SEC)


@asynccontextmanager
async def lifespan(_app):
    stop = threading.Event()
    if ENABLE_POLLER:
        threading.Thread(target=_poll, args=(stop,), daemon=True, name="live-poll").start()
    yield
    stop.set()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _stale(now):
    ages = (FEEDS.age("hsww", now), FEEDS.age("warnsum", now))
    return any(age is None or age >= STALE_AFTER for age in ages)


def _live_snapshot(site, now, position=None):
    """What a live screen shows. The alerts read the same snapshot, so they always match the screen, 「極端情況」
    included."""
    return build_snapshot(
        FEEDS.value("hsww") or {},
        FEEDS.value("warnsum") or {},
        FEEDS.value("warningInfo") or {},
        FEEDS.value("rhrread") or {},
        site,
        SCHEDULE,
        ICONS,
        fnd=FEEDS.value("fnd") or {},
        now=now,
        stale=_stale(now),
        position=position,
        wind=FEEDS.value("wind"),
        warnsum_en=FEEDS.value("warnsumEn"),
        extreme=EXTREME.get(),
    )


def snapshot_for(now):
    """For the alerts: a site's live snapshot as a screen without a position sees it (None: any site)."""
    return lambda site: _live_snapshot(site or GENERIC_SITE, now)


def feed_marks():
    """When each feed last fetched successfully. The alerts read a feed again only after a new fetch."""
    return {name: feed.fetched_at for name, feed in FEEDS.feeds.items()}


def _poller_ok():
    if not ENABLE_POLLER:
        return True
    last = POLLER["last"]
    return last is not None and time.monotonic() - last < POLLER_DEAD_AFTER


@app.get("/healthz")
def healthz():
    """Liveness for Docker: the process answers and the feed poller still finishes its cycles."""
    ok = _poller_ok()
    return JSONResponse({"ok": ok}, status_code=200 if ok else 503)


@app.get("/api/v1/health")
def health():
    """For an uptime monitor: 503 when the warning feeds are stale, the poller has stopped, a site file has a
    mistake, supervisor alerts are misconfigured or have not been going out for 15 minutes, or the 「極端情況」
    switch cannot read or save its state."""
    now = datetime.now(HKT)
    stale = _stale(now)
    poller = _poller_ok()
    feeds = {}
    for name, feed in FEEDS.feeds.items():
        age = FEEDS.age(name, now)
        feeds[name] = {"ageSec": None if age is None else round(age), "ok": feed.ok}
    switch = extreme.state(EXTREME.get(), now)
    problem = EXTREME.problem
    body = {
        "ok": poller and not stale and not SITE_PROBLEMS and ALERTS.healthy(now) and not problem,
        "stale": stale,
        "poller": poller,
        "feeds": feeds,
        "sites": len(SITES),
        "siteProblems": SITE_PROBLEMS,
        "extreme": switch,
        "extremeProblem": problem,
        "alerts": ALERTS.status(now),
    }
    return JSONResponse(body, status_code=200 if body["ok"] else 503)


_UNKNOWN_SITES = set()


def _site(site_id):
    """The site for ?site=; the default site without one; the generic site for an unknown or left-out one."""
    if not site_id:
        return SITES[DEFAULT_SITE] if DEFAULT_SITE else GENERIC_SITE
    if site_id in SITES:
        return SITES[site_id]
    if site_id not in _UNKNOWN_SITES and len(_UNKNOWN_SITES) < 100:
        _UNKNOWN_SITES.add(site_id)
        log.warning("no usable site file for ?site=%s; showing every workload level without trade names", site_id[:64])
    return GENERIC_SITE


@app.get("/api/v1/snapshot")
def snapshot(
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    acc: Optional[str] = None,
    site: Optional[str] = None,
):
    # lat/lon/acc are the browser's position (rounded by the kiosk) and only choose the weather stations.
    # They are read as text so a bad value is ignored rather than failing a safety display with a 422.
    if not ENABLE_POLLER or FEEDS.never_fetched():
        FEEDS.refresh_due()
    if FEEDS.value("hsww") is None and FEEDS.value("warnsum") is None:
        raise HTTPException(status_code=503, detail="no-data")
    snap = _live_snapshot(_site(site), datetime.now(HKT), parse_position(lat, lon, acc))
    snap["source"] = "live"
    return snap


def require_admin(request: Request, authorization: Optional[str] = Header(default=None)):
    """The admin key as `Authorization: Bearer <key>`, over https only. Checked before anything is read."""
    if not ADMIN_KEY:
        raise HTTPException(status_code=403, detail="admin-disabled: ADMIN_KEY is not set on the server")
    # Caddy sets X-Forwarded-Proto from the real connection. A request sent over plain http has already shown the
    # key to the network, so refuse it, to make the mistake visible (docs/site-setup.md: replace the key).
    proto = request.headers.get("x-forwarded-proto")
    if proto is not None and proto.split(",")[0].strip().lower() != "https":
        raise HTTPException(status_code=403, detail="https-required: use https://, then replace the key")
    if not extreme.key_ok(extreme.bearer(authorization), ADMIN_KEY):
        log.warning("「極端情況」 switch: request refused (missing or wrong admin key)")
        raise HTTPException(
            status_code=401, detail="admin-key-required", headers={"WWW-Authenticate": 'Bearer realm="admin"'}
        )


@app.get("/api/v1/admin/extreme", dependencies=[Depends(require_admin)])
def extreme_status():
    """The switch as recorded. Also the way to check the admin key works, without changing anything."""
    return extreme.state(EXTREME.get(), datetime.now(HKT))


@app.put("/api/v1/admin/extreme", dependencies=[Depends(require_admin)])
async def extreme_on(request: Request):
    """Switch 「極端情況」 on, or change its times: {"startsAt": optional, "endsAt": required}, Hong Kong time.

    Without startsAt, one in force or still to come keeps its start (an extension); otherwise it starts now."""
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"send JSON, for example {extreme.EXAMPLE}") from None
    now = datetime.now(HKT)
    try:
        ann = extreme.announcement(body, now, EXTREME.get())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None
    try:
        EXTREME.set(ann)
    except OSError as err:
        log.error("「極端情況」 switch: could not save %s: %s", EXTREME.path, err)
        raise HTTPException(status_code=503, detail=f"not saved, nothing changed: {err}") from None
    log.warning("「極端情況」 set: %s to %s", ann["startsAt"], ann["endsAt"])
    return extreme.state(ann, now)


@app.delete("/api/v1/admin/extreme", dependencies=[Depends(require_admin)])
def extreme_off():
    """Switch 「極端情況」 off now: one in force ends now, one that has not started is withdrawn."""
    now = datetime.now(HKT)
    before = extreme.status(EXTREME.get(), now)
    try:
        ann = EXTREME.end(now)
    except OSError as err:
        log.error("「極端情況」 switch: could not save %s: %s", EXTREME.path, err)
        raise HTTPException(status_code=503, detail=f"not saved, nothing changed: {err}") from None
    if before in ("active", "scheduled"):
        log.warning("「極端情況」 switched off at %s (it was %s)", extreme.iso(now), before)
    return extreme.state(ann, now)


@app.get("/api/v1/sim/cases")
def sim_cases():
    if not ENABLE_SIM:
        raise HTTPException(status_code=403, detail="sim-disabled")
    return {"cases": list_cases(), "icons": list_official_icons()}


@app.post("/api/v1/sim")
def sim(body: dict):
    if not ENABLE_SIM:
        raise HTTPException(status_code=403, detail="sim-disabled")
    if body.get("clear"):
        return {"ok": True, "sim": None}
    name = body.get("fixture")
    key = ALIASES.get(name, name)
    if key not in CASE_IDS:
        raise HTTPException(status_code=400, detail="unknown-fixture")
    # A site's own trades in any case, so it can check its heat-stress tiles before the hot season.
    site_id = body.get("site")
    return build_case(key, _site(site_id) if isinstance(site_id, str) and site_id else None)
