import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.hko import parse_warnsum  # noqa: F401
from app.hsww import parse_hkhi_icon  # noqa: F401
from app.sim_cases import ALIASES, CASE_IDS, build_case, list_cases, list_official_icons
from app.snapshot import build_snapshot

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
HSWW_URL = "https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml"
WARN_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_lock = threading.Lock()
_cache = {"at": None, "snap": None}
TTL = int(os.environ.get("SNAPSHOT_TTL_SEC", "60"))
STALE_AFTER = int(os.environ.get("STALE_AFTER_SEC", "600"))
ENABLE_SIM = os.environ.get("ENABLE_SIM", "true").lower() in ("1", "true", "yes")
ENABLE_POLLER = os.environ.get("ENABLE_LIVE_POLLER", "true").lower() in ("1", "true", "yes")

SITE = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _fetch_live():
    with httpx.Client(timeout=15.0) as client:
        hsww = client.get(HSWW_URL).json()
        warnsum = client.get(WARN_URL, params={"dataType": "warnsum", "lang": "tc"}).json()
        winfo = client.get(WARN_URL, params={"dataType": "warningInfo", "lang": "tc"}).json()
        rhr = client.get(WARN_URL, params={"dataType": "rhrread", "lang": "tc"}).json()
    snap = build_snapshot(hsww, warnsum, winfo, rhr, SITE, SCHEDULE, ICONS)
    snap["source"] = "live"
    snap["stale"] = False
    return snap


def _age_sec(now):
    at = _cache["at"]
    if not at:
        return None
    return (now - at).total_seconds()


def _serve(now):
    snap = _cache["snap"]
    if not snap:
        return None
    out = dict(snap)
    age = _age_sec(now)
    out["stale"] = bool(age is None or age >= STALE_AFTER)
    return out


@app.get("/api/v1/snapshot")
def snapshot():
    now = datetime.now(HKT)
    with _lock:
        cached = _cache["snap"]
        age = _age_sec(now)
        if cached and age is not None and age < TTL:
            return _serve(now)
    try:
        snap = _fetch_live()
        with _lock:
            _cache["snap"] = snap
            _cache["at"] = now
        return snap
    except Exception:
        with _lock:
            out = _serve(now)
        if out:
            return out
        raise HTTPException(status_code=503, detail="no-data")


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


def _refresh_loop():
    while True:
        try:
            snap = _fetch_live()
            with _lock:
                _cache["snap"] = snap
                _cache["at"] = datetime.now(HKT)
        except Exception:
            pass
        time.sleep(max(TTL, 15))


@app.on_event("startup")
def _start_poller():
    if not ENABLE_POLLER:
        return
    threading.Thread(target=_refresh_loop, daemon=True, name="live-poll").start()
