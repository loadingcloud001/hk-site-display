import json
import os
import threading
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
_sim = None
TTL = int(os.environ.get("SNAPSHOT_TTL_SEC", "60"))
ENABLE_SIM = os.environ.get("ENABLE_SIM", "true").lower() in ("1", "true", "yes")

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
    return build_snapshot(hsww, warnsum, winfo, rhr, SITE, SCHEDULE, ICONS)


@app.get("/api/v1/snapshot")
def snapshot():
    global _cache
    if _sim is not None:
        return _sim
    now = datetime.now(HKT)
    with _lock:
        cached = _cache["snap"]
        at = _cache["at"]
        if cached and at and (now - at).total_seconds() < TTL:
            return cached
    try:
        snap = _fetch_live()
        with _lock:
            _cache["snap"] = snap
            _cache["at"] = now
        return snap
    except Exception:
        if cached:
            stale = dict(cached)
            stale["stale"] = True
            return stale
        raise HTTPException(status_code=503, detail="no-data")


@app.get("/api/v1/sim/cases")
def sim_cases():
    if not ENABLE_SIM:
        raise HTTPException(status_code=403, detail="sim-disabled")
    return {"cases": list_cases(), "icons": list_official_icons()}


@app.post("/api/v1/sim")
def sim(body: dict):
    global _sim
    if not ENABLE_SIM:
        raise HTTPException(status_code=403, detail="sim-disabled")
    if body.get("clear"):
        _sim = None
        return {"ok": True, "sim": None}
    name = body.get("fixture")
    key = ALIASES.get(name, name)
    if key not in CASE_IDS:
        raise HTTPException(status_code=400, detail="unknown-fixture")
    _sim = build_case(key)
    return _sim
