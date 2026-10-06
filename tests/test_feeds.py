from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from app.feeds import Feed, FeedSet

HKT = timezone(timedelta(hours=8))


def test_failed_fetch_keeps_last_value():
    calls = {"n": 0}

    def flaky(_client):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("down")
        return {"v": 1}

    feeds = FeedSet([Feed("a", flaky, 0)], nullcontext)
    feeds.refresh_due()
    feeds.refresh_due(force=True)
    assert feeds.value("a") == {"v": 1}
    assert feeds.feeds["a"].ok is False


def test_one_feed_failing_does_not_block_others():
    def boom(_client):
        raise RuntimeError("x")

    feeds = FeedSet([Feed("bad", boom, 60), Feed("good", lambda _client: 2, 60)], nullcontext)
    feeds.refresh_due()
    assert feeds.value("good") == 2
    assert feeds.value("bad") is None


def test_interval_and_quicker_retry_after_failure():
    feed = Feed("a", lambda _client: 1, 600)
    assert feed.is_due(0.0)
    feed.last_attempt, feed.ok = 1000.0, True
    assert not feed.is_due(1300.0)
    assert feed.is_due(1600.0)
    feed.ok = False
    assert feed.is_due(1061.0)


def test_age_in_seconds():
    feeds = FeedSet([Feed("a", lambda _client: 1, 60)], nullcontext)
    now = datetime(2026, 10, 6, 12, 0, tzinfo=HKT)
    assert feeds.age("a", now) is None
    feeds.feeds["a"].fetched_at = now - timedelta(minutes=11)
    assert feeds.age("a", now) == 660
