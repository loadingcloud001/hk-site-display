import json
import logging
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


def fake_feeds(fail=(), **values_override):
    values = {"hsww": load("hsww_cancelled_stale.json"), "warnsum": {}, "warningInfo": {}, "rhrread": {}, "fnd": {}}
    values.update(values_override)

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


def fresh_rhrread():
    raw = load("rhrread_full.json")
    raw["updateTime"] = datetime.now(HKT).isoformat(timespec="seconds")
    return raw


def weather_at(client, query=""):
    response = client.get("/api/v1/snapshot" + query)
    assert response.status_code == 200
    return response.json()["weather"]


def test_snapshot_shows_the_observatory_without_a_position():
    client = client_with(fake_feeds(rhrread=fresh_rhrread()))
    weather = weather_at(client)
    assert (weather["placeZh"], weather["tempC"], weather["humidity"]) == ("香港天文台", 26, 58)


def test_snapshot_shows_the_station_nearest_the_position():
    client = client_with(fake_feeds(rhrread=fresh_rhrread()))
    weather = weather_at(client, "?lat=22.32&lon=114.22&acc=65")
    assert (weather["placeZh"], weather["tempC"], weather["humidity"]) == ("觀塘", 25, None)
    assert weather_at(client, "?lat=22.39&lon=113.98&acc=65")["placeZh"] == "屯門"


def test_unusable_positions_fall_back_to_the_observatory():
    client = client_with(fake_feeds(rhrread=fresh_rhrread()))
    for query in (
        "?lat=22.31&lon=114.22&acc=20000",  # too coarse to tell stations apart
        "?lat=51.5&lon=-0.12&acc=20",  # not in Hong Kong
        "?lat=abc&lon=114.22&acc=65",
        "?lat=22.31",
        "?lat=nan&lon=inf",
        "?lat=22.31&lon=114.22&acc=-1",
    ):
        assert weather_at(client, query)["placeZh"] == "香港天文台", query


def test_position_never_changes_the_warning_state():
    client = client_with(fake_feeds(rhrread=fresh_rhrread()))
    plain = client.get("/api/v1/snapshot").json()
    located = client.get("/api/v1/snapshot?lat=22.31&lon=114.22&acc=65").json()
    for key in ("display", "tone", "signals", "rest", "restTiles", "banner", "stale", "priority"):
        assert located[key] == plain[key], key


def access_record(path):
    args = ("127.0.0.1:50000", "GET", path, "1.1", 200)
    return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', args, None)


def test_access_log_does_not_keep_the_position():
    record = access_record("/api/v1/snapshot?lat=22.32&lon=114.22&acc=100")
    assert main.HidePosition().filter(record) is True
    assert record.getMessage() == '127.0.0.1:50000 - "GET /api/v1/snapshot?lat=-&lon=-&acc=- HTTP/1.1" 200'
    other = access_record("/api/v1/snapshot?latitude=3&x=lat")
    main.HidePosition().filter(other)
    assert "/api/v1/snapshot?latitude=3&x=lat" in other.getMessage()
    assert any(isinstance(f, main.HidePosition) for f in logging.getLogger("uvicorn.access").filters)
