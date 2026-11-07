import json
import logging
import threading
import time
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.feeds import Feed, FeedSet
from app.wind import parse_wind_csv

HKT = timezone(timedelta(hours=8))
FIX = Path(__file__).resolve().parent / "fixtures"
NAMES = ("hsww", "warnsum", "warningInfo", "rhrread", "fnd", "wind")
main.ENABLE_POLLER = False


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def fake_feeds(fail=(), **values_override):
    values = {
        "hsww": load("hsww_cancelled_stale.json"),
        "warnsum": {},
        "warningInfo": {},
        "rhrread": {},
        "fnd": {},
        "wind": None,
    }
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


def fresh_wind():
    text = (FIX / "wind_10min_uc.csv").read_text(encoding="utf-8")
    stamp = datetime.now(HKT).strftime("%Y%m%d%H%M")
    return parse_wind_csv(text.replace("202611072220", stamp))


def test_wind_comes_from_the_nearest_ground_level_station_else_the_site_station():
    client = client_with(fake_feeds(wind=fresh_wind()))
    assert client.get("/api/v1/snapshot").json()["wind"]["placeZh"] == "啟德"  # the demo site's windStation
    located = client.get("/api/v1/snapshot?lat=22.37&lon=114.11&acc=100").json()["wind"]
    assert (located["placeZh"], located["dirZh"]) == ("青衣", "東南")
    assert client_with(fake_feeds()).get("/api/v1/snapshot").json()["wind"] is None


def test_site_parameter_chooses_the_site_file():
    client = client_with(fake_feeds(hsww=load("hsww_amber_inforce.json")))
    demo = client.get("/api/v1/snapshot").json()
    assert demo["site"]["id"] == "demo-kai-tak" and demo["site"]["known"] is True
    assert client.get("/api/v1/snapshot?site=demo-kai-tak").json()["restTiles"] == demo["restTiles"]
    assert any("紮鐵" in tile["trades"] for tile in demo["restTiles"])


def test_unknown_site_shows_every_workload_level_without_trade_names():
    client = client_with(fake_feeds(hsww=load("hsww_amber_inforce.json")))
    body = client.get("/api/v1/snapshot?site=no-such-site").json()
    assert body["site"] == {**body["site"], "id": None, "known": False}
    names = [name for tile in body["restTiles"] for name in tile["trades"]]
    assert sorted(names) == sorted(["輕勞動", "中等勞動", "重勞動", "極重勞動"])
    assert body["display"]["mode"] == "heat"


def test_preview_cases_can_show_a_sites_own_trades(monkeypatch):
    client = client_with(fake_feeds())
    trades = lambda body: sorted(n for t in body["restTiles"] for n in t["trades"])  # noqa: E731
    demo = client.post("/api/v1/sim", json={"fixture": "amber"}).json()
    assert "紮鐵" in trades(demo)
    site = {"siteId": "s7k2", "environment": "outdoor", "primaryTrades": [{"labelZh": "外牆", "workload": "heavy"}]}
    monkeypatch.setitem(main.SITES, "s7k2", site)
    own = client.post("/api/v1/sim", json={"fixture": "amber", "site": "s7k2"}).json()
    assert trades(own) == ["外牆"] and own["display"]["mode"] == "heat"
    unknown = client.post("/api/v1/sim", json={"fixture": "amber", "site": "no-such-site"}).json()
    assert trades(unknown) == sorted(["輕勞動", "中等勞動", "重勞動", "極重勞動"])
    assert trades(client.post("/api/v1/sim", json={"fixture": "amber", "site": 7}).json()) == trades(demo)


def test_health_reports_feeds_and_fails_when_warnings_are_stale():
    feeds = fake_feeds()
    client = client_with(feeds)
    client.get("/api/v1/snapshot")
    ok = client.get("/api/v1/health")
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True and body["stale"] is False and body["sites"] >= 1 and body["siteProblems"] == []
    assert set(body["feeds"]) == set(NAMES) and body["feeds"]["hsww"]["ok"] is True
    stale = fake_feeds(fail=("hsww", "warnsum"))
    preload(stale, timedelta(minutes=11))
    response = client_with(stale).get("/api/v1/health")
    assert response.status_code == 503 and response.json()["stale"] is True


def test_a_bad_site_file_fails_health_but_never_the_screens(monkeypatch):
    monkeypatch.setattr(main, "SITE_PROBLEMS", ["config/sites/a.json: restAdjustMinutes must be a multiple of 15"])
    client = client_with(fake_feeds())
    assert client.get("/api/v1/snapshot").status_code == 200
    response = client.get("/api/v1/health")
    assert response.status_code == 503 and response.json()["stale"] is False
    assert response.json()["siteProblems"] == main.SITE_PROBLEMS
    assert client.get("/healthz").status_code == 200  # Docker must not restart the service for it


def test_without_a_usable_default_site_screens_show_every_workload_level(monkeypatch):
    monkeypatch.setattr(main, "DEFAULT_SITE", None)
    body = client_with(fake_feeds(hsww=load("hsww_amber_inforce.json"))).get("/api/v1/snapshot").json()
    assert body["site"]["known"] is False
    assert sorted(n for t in body["restTiles"] for n in t["trades"]) == sorted(["輕勞動", "中等勞動", "重勞動", "極重勞動"])


def test_healthz_watches_the_poller(monkeypatch):
    client = client_with(fake_feeds())
    assert client.get("/healthz").status_code == 200  # poller disabled in tests
    monkeypatch.setattr(main, "ENABLE_POLLER", True)
    monkeypatch.setitem(main.POLLER, "last", None)
    assert client.get("/healthz").status_code == 503
    monkeypatch.setitem(main.POLLER, "last", time.monotonic())
    assert client.get("/healthz").status_code == 200
    monkeypatch.setitem(main.POLLER, "last", time.monotonic() - main.POLLER_DEAD_AFTER - 1)
    assert client.get("/healthz").status_code == 503


def test_a_failing_refresh_never_stops_the_poller(monkeypatch):
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        if calls["n"] >= 2:
            stop.set()
        raise RuntimeError("client could not start")

    stop = threading.Event()
    monkeypatch.setattr(main.FEEDS, "refresh_due", boom)
    monkeypatch.setattr(main, "POLL_SEC", 0)
    main._poll(stop)
    assert calls["n"] == 2 and main.POLLER["last"] is not None
