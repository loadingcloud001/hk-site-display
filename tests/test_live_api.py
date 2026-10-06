import json
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.feeds import Feed, FeedSet

HKT = timezone(timedelta(hours=8))
FIX = Path(__file__).resolve().parent / "fixtures"
NAMES = ("hsww", "warnsum", "warningInfo", "rhrread", "fnd")
main.ENABLE_POLLER = False


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def fake_feeds(fail=()):
    values = {"hsww": load("hsww_cancelled_stale.json"), "warnsum": {}, "warningInfo": {}, "rhrread": {}, "fnd": {}}

    def fetcher(name):
        def fetch(_client):
            if name in fail:
                raise RuntimeError(f"{name} down")
            return values[name]

        return fetch

    return FeedSet([Feed(name, fetcher(name), 60) for name in NAMES], nullcontext)


def preload(feeds, age):
    at = datetime.now(HKT) - age
    feeds.feeds["hsww"].value, feeds.feeds["hsww"].fetched_at = load("hsww_cancelled_stale.json"), at
    feeds.feeds["warnsum"].value, feeds.feeds["warnsum"].fetched_at = {}, at


def client_with(feeds):
    main.FEEDS = feeds
    return TestClient(main.app)


def test_snapshot_stays_live_after_sim_post():
    client = client_with(fake_feeds())
    sim = client.post("/api/v1/sim", json={"fixture": "amber"})
    assert sim.status_code == 200
    assert sim.json()["display"]["mode"] == "heat"
    body = client.get("/api/v1/snapshot").json()
    assert body["display"]["mode"] == "normal"
    assert body["source"] == "live"
    assert body["stale"] is False


def test_snapshot_marks_stale_when_warning_feeds_old():
    feeds = fake_feeds(fail=("hsww", "warnsum"))
    preload(feeds, timedelta(minutes=11))
    body = client_with(feeds).get("/api/v1/snapshot").json()
    assert body["stale"] is True
    assert body["banner"] is None


def test_transient_failure_keeps_fresh_cache_not_stale():
    feeds = fake_feeds(fail=("hsww", "warnsum"))
    preload(feeds, timedelta(seconds=90))
    assert client_with(feeds).get("/api/v1/snapshot").json()["stale"] is False


def test_weather_feed_failure_does_not_block_snapshot():
    body = client_with(fake_feeds(fail=("rhrread", "fnd"))).get("/api/v1/snapshot").json()
    assert body["weather"] is None and body["forecast"] is None
    assert body["display"]["mode"] == "normal"


def test_no_data_at_all_is_503():
    response = client_with(fake_feeds(fail=NAMES)).get("/api/v1/snapshot")
    assert response.status_code == 503
