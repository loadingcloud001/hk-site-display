"""Per-feed cache: each official feed refreshes on its own interval and keeps its last good value."""
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

HKT = timezone(timedelta(hours=8))
RETRY_SEC = 60


@dataclass
class Feed:
    name: str
    fetch: Callable[[Any], Any]
    interval: float
    value: Any = None
    fetched_at: datetime | None = None
    last_attempt: float | None = None
    ok: bool = False

    def is_due(self, mono):
        if self.last_attempt is None:
            return True
        wait = self.interval if self.ok else min(self.interval, RETRY_SEC)
        return mono - self.last_attempt >= wait

    def refresh(self, client, now):
        self.last_attempt = time.monotonic()
        try:
            value = self.fetch(client)
        except Exception:
            self.ok = False
            return False
        self.value, self.fetched_at, self.ok = value, now, True
        return True


class FeedSet:
    def __init__(self, feeds, client_factory):
        self.feeds = {feed.name: feed for feed in feeds}
        self.client_factory = client_factory
        self._lock = threading.Lock()

    def refresh_due(self, force=False):
        with self._lock:
            mono = time.monotonic()
            due = [feed for feed in self.feeds.values() if force or feed.is_due(mono)]
            if not due:
                return
            with self.client_factory() as client:
                for feed in due:
                    feed.refresh(client, datetime.now(HKT))

    def value(self, name):
        return self.feeds[name].value

    def age(self, name, now):
        at = self.feeds[name].fetched_at
        return None if at is None else (now - at).total_seconds()

    def never_fetched(self):
        return all(feed.last_attempt is None for feed in self.feeds.values())
