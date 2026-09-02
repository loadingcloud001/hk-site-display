from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main

HKT = timezone(timedelta(hours=8))
main.ENABLE_POLLER = False


def _live_snap():
    return {
        "display": {"action": "正常工作", "actionSub": "live"},
        "tone": "idle",
        "stale": False,
        "source": "live",
        "signals": [],
    }


def setup_function():
    main._sim = None
    main._cache = {"at": None, "snap": None}


def test_snapshot_stays_live_after_sim_post():
    with patch.object(main, "_fetch_live", return_value=_live_snap()):
        client = TestClient(main.app)
        sim = client.post("/api/v1/sim", json={"fixture": "amber"})
        assert sim.status_code == 200
        assert sim.json()["display"]["action"] == "休息 45 分鐘"
        live = client.get("/api/v1/snapshot")
        assert live.status_code == 200
        body = live.json()
        assert body["display"]["action"] == "正常工作"
        assert body.get("source") == "live"


def test_snapshot_marks_stale_when_live_fetch_fails_and_cache_old():
    old = datetime.now(HKT) - timedelta(minutes=11)
    main._cache = {"at": old, "snap": _live_snap()}
    with patch.object(main, "_fetch_live", side_effect=RuntimeError("down")):
        client = TestClient(main.app)
        body = client.get("/api/v1/snapshot").json()
        assert body["stale"] is True
        assert body["display"]["action"] == "正常工作"


def test_transient_fetch_fail_keeps_fresh_cache_not_stale():
    recent = datetime.now(HKT) - timedelta(seconds=90)
    main._cache = {"at": recent, "snap": _live_snap()}
    with patch.object(main, "_fetch_live", side_effect=RuntimeError("blip")):
        client = TestClient(main.app)
        body = client.get("/api/v1/snapshot").json()
        assert body["stale"] is False
