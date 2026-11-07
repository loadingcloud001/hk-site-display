"""The 「極端情況」 switch through the API: the admin key, switching on and off, expiry, restarts and health."""
import json
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import extreme, main
from app.feeds import Feed, FeedSet

HKT = timezone(timedelta(hours=8))
FIX = Path(__file__).resolve().parent / "fixtures"
NAMES = ("hsww", "warnsum", "warningInfo", "rhrread", "fnd", "wind")
KEY = "test-admin-key-" + "x" * 32
URL = "/api/v1/admin/extreme"
main.ENABLE_POLLER = False


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def feeds(**values):
    base = {"hsww": load("hsww_cancelled_stale.json"), "warnsum": {}, "warningInfo": {}, "rhrread": {}, "fnd": {}, "wind": None}
    base.update(values)
    return FeedSet([Feed(name, (lambda n: lambda _client: base[n])(name), 60) for name in NAMES], nullcontext)


@pytest.fixture
def api(tmp_path, monkeypatch):
    """A client with the admin key set and the switch's state in tmp_path."""
    monkeypatch.setattr(main, "ADMIN_KEY", KEY)
    monkeypatch.setattr(main, "EXTREME", extreme.ExtremeStore(tmp_path))
    monkeypatch.setattr(main, "FEEDS", feeds())
    return TestClient(main.app)


def auth(key=KEY):
    return {"Authorization": f"Bearer {key}"}


def hkt(minutes):
    return (datetime.now(HKT) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M")


def screen(client, query=""):
    response = client.get("/api/v1/snapshot" + query)
    assert response.status_code == 200
    return response.json()


# --- the admin key ---------------------------------------------------------------------------------------------


def test_without_an_admin_key_on_the_server_the_switch_is_off(api, monkeypatch):
    monkeypatch.setattr(main, "ADMIN_KEY", "")
    for method in ("get", "put", "delete"):
        response = api.request(method, URL, headers=auth(), json={"endsAt": hkt(60)})
        assert response.status_code == 403 and response.json()["detail"].startswith("admin-disabled"), method
    assert screen(api)["display"]["mode"] == "normal"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer wrong-key-" + "y" * 32},
        {"Authorization": "Bearer " + KEY[:-1]},
        {"Authorization": "Bearer " + KEY + "x"},
        {"Authorization": "Basic " + KEY},
        {"Authorization": KEY},
        {"X-Admin-Key": KEY},
    ],
)
def test_a_missing_or_wrong_key_is_refused_and_changes_nothing(api, headers):
    for method in ("get", "put", "delete"):
        response = api.request(method, URL, headers=headers, json={"endsAt": hkt(60)})
        assert response.status_code == 401, method
        assert response.json() == {"detail": "admin-key-required"}
        assert response.headers["www-authenticate"].startswith("Bearer")
    assert screen(api)["display"]["mode"] == "normal"
    assert main.EXTREME.get() is None


def test_the_key_is_never_read_from_the_address(api):
    response = api.put(f"{URL}?key={KEY}&token={KEY}", json={"endsAt": hkt(60)})
    assert response.status_code == 401


def test_the_key_is_checked_before_the_body(api):
    assert api.put(URL, content=b"{not json", headers={"Content-Type": "application/json"}).status_code == 401
    assert api.put(URL, json=["x"]).status_code == 401


def test_plain_http_through_the_proxy_is_refused_even_with_the_right_key(api):
    response = api.put(URL, headers={**auth(), "X-Forwarded-Proto": "http"}, json={"endsAt": hkt(60)})
    assert response.status_code == 403 and response.json()["detail"].startswith("https-required")
    assert main.EXTREME.get() is None
    ok = api.put(URL, headers={**auth(), "X-Forwarded-Proto": "https"}, json={"endsAt": hkt(60)})
    assert ok.status_code == 200


def test_a_wrong_key_is_logged_without_the_key(api, caplog):
    api.get(URL, headers=auth("wrong-" + "z" * 40))
    assert "request refused" in caplog.text
    assert "z" * 40 not in caplog.text and KEY not in caplog.text


# --- switching on and off --------------------------------------------------------------------------------------


def test_switch_on_shows_it_on_every_sites_screens(api, monkeypatch):
    monkeypatch.setitem(main.SITES, "s7k2", {"siteId": "s7k2", "environment": "outdoor", "primaryTrades": []})
    response = api.put(URL, headers=auth(), json={"endsAt": hkt(90)})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active" and body["endsAt"].startswith(hkt(90))
    for query in ("", "?site=s7k2", "?site=no-such-site", "?lat=22.32&lon=114.22&acc=100"):
        s = screen(api, query)
        assert s["display"]["mode"] == "extreme", query
        assert s["display"]["main"] == "留在原來的地點或安全的地點"
        assert s["extreme"]["endsAt"] == body["endsAt"]


def test_the_switch_reports_its_state(api):
    assert api.get(URL, headers=auth()).json() == {"status": "off"}
    api.put(URL, headers=auth(), json={"startsAt": hkt(30), "endsAt": hkt(150)})
    got = api.get(URL, headers=auth()).json()
    assert got["status"] == "scheduled" and got["startsAt"].startswith(hkt(30))


def test_a_later_start_shows_nothing_yet(api):
    api.put(URL, headers=auth(), json={"startsAt": hkt(30), "endsAt": hkt(150)})
    assert screen(api)["display"]["mode"] == "normal"
    assert screen(api)["extreme"] is None


def test_an_extension_is_entered_again(api):
    api.put(URL, headers=auth(), json={"endsAt": hkt(60)})
    first = screen(api)["extreme"]
    response = api.put(URL, headers=auth(), json={"startsAt": first["startsAt"], "endsAt": hkt(180)})
    assert response.status_code == 200
    again = screen(api)["extreme"]
    assert again["startsAt"] == first["startsAt"] and again["endsAt"].startswith(hkt(180))


def test_an_extension_with_only_the_new_end_keeps_the_time_it_took_effect(api, monkeypatch):
    api.put(URL, headers=auth(), json={"endsAt": hkt(60)})
    first = screen(api)["extreme"]
    later = datetime.now(HKT) + timedelta(minutes=8)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return later.astimezone(tz) if tz else later

    monkeypatch.setattr(main, "datetime", Clock)
    response = api.put(URL, headers=auth(), json={"endsAt": hkt(180)})
    assert response.status_code == 200 and response.json()["startsAt"] == first["startsAt"]
    again = screen(api)
    assert again["stale"] is False
    assert again["extreme"]["startsAt"] == first["startsAt"] and again["extreme"]["endsAt"].startswith(hkt(180))
    assert again["banner"]["time"] == first["startZh"]  # still the first 生效, not a second one at the extension


def test_switch_off_ends_it_now(api):
    api.put(URL, headers=auth(), json={"endsAt": hkt(90)})
    response = api.delete(URL, headers=auth())
    assert response.status_code == 200 and response.json()["status"] == "ended"
    s = screen(api)
    assert s["display"]["mode"] == "normal" and s["extreme"] is None
    assert s["banner"]["textZh"] == "「極端情況」 結束"
    assert api.delete(URL, headers=auth()).json()["status"] == "ended"  # again: nothing to do


def test_switch_off_before_the_start_withdraws_it(api):
    api.put(URL, headers=auth(), json={"startsAt": hkt(30), "endsAt": hkt(150)})
    assert api.delete(URL, headers=auth()).json() == {"status": "off"}
    assert api.get(URL, headers=auth()).json() == {"status": "off"}


@pytest.mark.parametrize(
    ("body", "says"),
    [
        ({}, "endsAt is required"),
        ({"endsAt": "19:00"}, "not a date and time"),
        ({"endsAt": "2020-01-01T00:00"}, "already passed"),
        ({"endsAt": "2099-01-01T00:00"}, "more than 24 hours ahead"),
        ({"until": "2099-01-01T00:00"}, "unknown field"),
    ],
)
def test_mistakes_get_a_reason_and_change_nothing(api, body, says):
    response = api.put(URL, headers=auth(), json=body)
    assert response.status_code == 400 and says in response.json()["detail"]
    assert main.EXTREME.get() is None


def test_not_json_gets_a_reason(api):
    response = api.put(URL, headers={**auth(), "Content-Type": "application/json"}, content=b"endsAt=19:00")
    assert response.status_code == 400 and "send JSON" in response.json()["detail"]


def test_it_expires_by_itself_at_the_announced_end(api, monkeypatch):
    api.put(URL, headers=auth(), json={"endsAt": hkt(60)})
    assert screen(api)["display"]["mode"] == "extreme"
    later = datetime.now(HKT) + timedelta(minutes=61)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return later.astimezone(tz) if tz else later

    monkeypatch.setattr(main, "datetime", Clock)
    s = screen(api)
    assert s["display"]["mode"] == "normal" and s["extreme"] is None
    assert api.get(URL, headers=auth()).json()["status"] == "ended"
    assert api.get("/api/v1/health").json()["extreme"]["status"] == "ended"


def test_it_survives_a_restart(api, monkeypatch, tmp_path):
    api.put(URL, headers=auth(), json={"endsAt": hkt(90)})
    monkeypatch.setattr(main, "EXTREME", extreme.ExtremeStore(tmp_path))  # a new process reads the volume
    assert screen(api)["display"]["mode"] == "extreme"
    assert api.get(URL, headers=auth()).json()["status"] == "active"


def test_a_failed_save_says_so_and_changes_nothing(api, monkeypatch):
    def full(_ann):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(main.EXTREME, "_write", full)
    response = api.put(URL, headers=auth(), json={"endsAt": hkt(60)})
    assert response.status_code == 503 and "not saved" in response.json()["detail"]
    assert screen(api)["display"]["mode"] == "normal"


# --- ranking and health ----------------------------------------------------------------------------------------


def test_an_hko_signal_in_force_stays_on_the_bar(api, monkeypatch):
    monkeypatch.setattr(main, "FEEDS", feeds(warnsum=load("warnsum_tc8ne.json"), warningInfo=load("warningInfo_tc8.json")))
    assert screen(api)["display"]["mode"] == "weather"
    api.put(URL, headers=auth(), json={"endsAt": hkt(60)})
    s = screen(api)
    assert s["display"]["mode"] == "extreme"
    assert [(x["code"], x["rel"]) for x in s["signals"]] == [("TC8NE", "official/warning/tc8ne.png")]


def test_health_shows_the_switch_and_fails_on_a_bad_state_file(api, tmp_path):
    body = api.get("/api/v1/health").json()
    assert body["extreme"] == {"status": "off"} and body["extremeProblem"] is None
    api.put(URL, headers=auth(), json={"endsAt": hkt(60)})
    assert api.get("/api/v1/health").json()["extreme"]["status"] == "active"
    (tmp_path / "extreme.json").write_text("{broken", encoding="utf-8")
    response = api.get("/api/v1/health")
    assert response.status_code == 503 and "extreme.json" in response.json()["extremeProblem"]
    assert screen(api)["display"]["mode"] == "normal"  # never fatal for the screens
    assert api.get("/healthz").status_code == 200  # Docker must not restart the service for it


def test_the_health_endpoint_never_shows_the_key(api):
    assert KEY not in api.get("/api/v1/health").text
    assert KEY not in api.get(URL, headers=auth()).text
