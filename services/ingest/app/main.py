import json
import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.feeds import Feed, FeedSet
from app.sim_cases import ALIASES, CASE_IDS, build_case, list_cases, list_official_icons
from app.site import validate_site
from app.snapshot import build_snapshot
from app.stations import parse_position

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
HSWW_URL = "https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml"
WARN_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
POLL_SEC = 15
STALE_AFTER = int(os.environ.get("STALE_AFTER_SEC", "600"))
ENABLE_SIM = os.environ.get("ENABLE_SIM", "true").lower() in ("1", "true", "yes")
ENABLE_POLLER = os.environ.get("ENABLE_LIVE_POLLER", "true").lower() in ("1", "true", "yes")

SITE = validate_site(json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8")))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))


def _get_json(client, url, params=None):
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _hko(data_type):
    return lambda client: _get_json(client, WARN_URL, {"dataType": data_type, "lang": "tc"})


def make_feeds():
    return FeedSet(
        [
            Feed("hsww", lambda client: _get_json(client, HSWW_URL), 60),
            Feed("warnsum", _hko("warnsum"), 60),
            Feed("warningInfo", _hko("warningInfo"), 60),
            Feed("rhrread", _hko("rhrread"), 600),
            Feed("fnd", _hko("fnd"), 1800),
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


def _poll(stop):
    while not stop.is_set():
        FEEDS.refresh_due()
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


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _stale(now):
    ages = (FEEDS.age("hsww", now), FEEDS.age("warnsum", now))
    return any(age is None or age >= STALE_AFTER for age in ages)


@app.get("/api/v1/snapshot")
def snapshot(lat: Optional[str] = None, lon: Optional[str] = None, acc: Optional[str] = None):
    # lat/lon/acc are the browser's position (rounded by the kiosk) and only choose the weather station.
    # They are read as text so a bad value is ignored rather than failing a safety display with a 422.
    if not ENABLE_POLLER or FEEDS.never_fetched():
        FEEDS.refresh_due()
    if FEEDS.value("hsww") is None and FEEDS.value("warnsum") is None:
        raise HTTPException(status_code=503, detail="no-data")
    now = datetime.now(HKT)
    stale = _stale(now)
    snap = build_snapshot(
        FEEDS.value("hsww") or {},
        FEEDS.value("warnsum") or {},
        FEEDS.value("warningInfo") or {},
        FEEDS.value("rhrread") or {},
        SITE,
        SCHEDULE,
        ICONS,
        fnd=FEEDS.value("fnd") or {},
        now=now,
        stale=stale,
        position=parse_position(lat, lon, acc),
    )
    snap["source"] = "live"
    return snap


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
    return build_case(key)
