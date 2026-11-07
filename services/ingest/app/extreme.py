"""「極端情況」 (extreme conditions): the switch an operator sets when the Government announces it.

The Government announces 「極端情況」 for the whole territory after a super typhoon or another large-scale disaster
(Labour Department Code of Practice, footnote 2). It is not an HKO warning and has no open-data feed, so an operator
records the start and the end as announced (main.py, /api/v1/admin/extreme).

- The state ends by itself at the announced end. Every snapshot works it out from the clock, so nothing has to run
  at that moment, and a restart in between changes nothing.
- It is one small JSON file in STATE_DIR, a Docker volume, so it survives restarts and rebuilds.
- It applies to every site, because the announcement is territory-wide.
"""
import hashlib
import hmac
import json
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HKT = timezone(timedelta(hours=8))
# The Code of Practice's own term, always written with its brackets (its title, footnote 2 and Appendices 1 and 2).
NAME = "「極端情況」"
CODE = "EXTREME"
FILE_NAME = "extreme.json"
# An end further ahead than this is refused as a typing mistake. When the Government extends 「極端情況」, the
# operator enters the new end.
MAX_AHEAD = timedelta(hours=24)
# A start entered late may be this far back at most. It is only shown, as the time 「極端情況」 took effect.
MAX_BEHIND = timedelta(hours=24)
MIN_KEY_LENGTH = 32
EXAMPLE = '{"endsAt": "2026-11-07T19:00"}'

log = logging.getLogger("hk_site_display")


def iso(at):
    return at.astimezone(HKT).isoformat(timespec="seconds")


def parse_hkt(value, field):
    """An announced time as ISO 8601. A time without a UTC offset is Hong Kong time."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a date and time such as 2026-11-07T19:00 (Hong Kong time)")
    text = value.strip()
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} {value[:40]!r} is not a date and time such as 2026-11-07T19:00") from None
    if _date_alone(text):  # Python reads a date alone as midnight, which an announcement never means
        raise ValueError(f"{field} {text[:40]!r} has no time: give the time as announced, for example 2026-11-07T19:00")
    if at.tzinfo is None:
        at = at.replace(tzinfo=HKT)
    return at.astimezone(HKT).replace(microsecond=0)


def _date_alone(text):
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def announcement(body, now, current=None):
    """What to record for an admin request: {startsAt, endsAt, setAt}. Raises ValueError saying what is wrong.

    `endsAt` is required. Without `startsAt`, the start already recorded stays while that announcement is in force or
    still to come, so an extension keeps the time 「極端情況」 took effect; otherwise it starts now. A later start is
    kept, and the screens wait for it.
    """
    if not isinstance(body, dict):
        raise ValueError(f"send a JSON object, for example {EXAMPLE}")
    unknown = sorted(str(key) for key in body if key not in ("startsAt", "endsAt"))
    if unknown:
        raise ValueError(f"unknown field(s) {', '.join(unknown)}: send startsAt (optional) and endsAt")
    if body.get("endsAt") is None:
        raise ValueError(f"endsAt is required: the end of 「極端情況」 as announced, for example {EXAMPLE}")
    now = now.astimezone(HKT).replace(microsecond=0)
    kept = current["startsAt"] if status(current, now) in ("active", "scheduled") else None
    if body.get("startsAt") is not None:
        starts = parse_hkt(body["startsAt"], "startsAt")
    else:
        starts = datetime.fromisoformat(kept) if kept else now
    ends = parse_hkt(body["endsAt"], "endsAt")
    if ends <= now:
        raise ValueError(f"endsAt {iso(ends)} has already passed")
    if ends <= starts:
        raise ValueError(f"endsAt must be after startsAt ({iso(starts)})")
    if ends - now > MAX_AHEAD:
        raise ValueError(
            "endsAt is more than 24 hours ahead. Enter the end as announced; if the Government extends "
            "「極端情況」, enter the new end then"
        )
    # A typing mistake in a start entered late. The recorded start of a long 「極端情況」 that is being extended is not.
    if now - starts > MAX_BEHIND and iso(starts) != kept:
        raise ValueError("startsAt is more than 24 hours ago")
    return {"startsAt": iso(starts), "endsAt": iso(ends), "setAt": iso(now)}


def _times(ann):
    return datetime.fromisoformat(ann["startsAt"]), datetime.fromisoformat(ann["endsAt"])


def status(ann, now):
    """'off' (nothing recorded), 'scheduled', 'active' or 'ended'."""
    if not ann:
        return "off"
    starts, ends = _times(ann)
    if now < starts:
        return "scheduled"
    return "active" if now < ends else "ended"


def active(ann, now):
    """The announcement when 「極端情況」 is in force at `now`, else None."""
    return ann if status(ann, now) == "active" else None


def state(ann, now):
    """The switch as the admin endpoint and /api/v1/health report it."""
    current = status(ann, now)
    if current == "off":
        return {"status": "off"}
    return {"status": current, "startsAt": ann["startsAt"], "endsAt": ann["endsAt"], "setAt": ann.get("setAt")}


def when_zh(at, now):
    """HH:MM, with the date in front when it is not today in Hong Kong."""
    at, now = at.astimezone(HKT), now.astimezone(HKT)
    clock = at.strftime("%H:%M")
    return clock if at.date() == now.date() else f"{at.month}月{at.day}日 {clock}"


def _checked(data):
    """A state file's announcement, or ValueError: written by this service, or by hand on the server."""
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    starts, ends = parse_hkt(data.get("startsAt"), "startsAt"), parse_hkt(data.get("endsAt"), "endsAt")
    if ends <= starts:
        raise ValueError("endsAt is not after startsAt")
    return {"startsAt": iso(starts), "endsAt": iso(ends), "setAt": data.get("setAt")}


class ExtremeStore:
    """The switch, kept in `<directory>/extreme.json`. No file means off.

    The file is read again whenever it changes, so a hand edit on the server also counts. A file that cannot be read
    or makes no sense is never fatal: 「極端情況」 is then off, `problem` says why, and /api/v1/health fails.
    """

    def __init__(self, directory):
        self.path = Path(directory) / FILE_NAME
        self.problem = None
        self._lock = threading.RLock()
        self._stamp = None
        self._value = None

    def get(self):
        with self._lock:
            try:
                info = self.path.stat()
            except FileNotFoundError:
                self._stamp, self._value, self.problem = None, None, None
                return None
            except OSError as err:  # keep the last good state rather than flip the screens over a disk error
                self.problem = f"cannot read {self.path}: {err}"
                return self._value
            stamp = (info.st_mtime_ns, info.st_size)
            if stamp != self._stamp:
                self._stamp = stamp
                try:
                    self._value, self.problem = _checked(json.loads(self.path.read_text(encoding="utf-8"))), None
                except (OSError, ValueError) as err:
                    self._value, self.problem = None, f"{self.path} is not used: {err}"
                    log.error("「極端情況」 switch: %s", self.problem)
            return self._value

    def set(self, ann):
        """Record an announcement. Raises OSError when it cannot be saved, and then changes nothing."""
        with self._lock:
            self._write(ann)
            self._value, self.problem = ann, None

    def end(self, now):
        """Switch off now. An announcement in force ends now, so screens show 「極端情況」 結束 for 10 minutes; one
        that has not started yet is withdrawn. Returns what is left."""
        with self._lock:
            ann = self.get()
            current = status(ann, now)
            if current == "active":
                ann = {**ann, "endsAt": iso(now), "setAt": iso(now)}
                self.set(ann)
            elif current == "scheduled":
                self.path.unlink(missing_ok=True)
                self._stamp, self._value, self.problem = None, None, None
                ann = None
            return ann

    def check_writable(self):
        """Fail at start-up, not during an emergency, when the state folder cannot be written."""
        probe = self.path.with_name(".write-check")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as err:
            self.problem = f"cannot write the state folder {self.path.parent}: {err}"
            log.error("「極端情況」 switch: %s", self.problem)
            return False
        return True

    def _write(self, ann):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(ann, ensure_ascii=False, indent=2) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise
        try:  # make the rename itself durable
            fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass
        info = self.path.stat()
        self._stamp = (info.st_mtime_ns, info.st_size)


def usable_key(value):
    """The admin key from the environment, or '' when it is unset or too short to be safe."""
    key = (value or "").strip()
    if key and len(key) < MIN_KEY_LENGTH:
        log.error("ADMIN_KEY is shorter than %d characters, so the 「極端情況」 switch is off", MIN_KEY_LENGTH)
        return ""
    return key


def key_ok(given, expected):
    """Constant time whatever the lengths: compares SHA-256 digests, never the keys themselves."""
    if not given or not expected:
        return False
    return hmac.compare_digest(
        hashlib.sha256(given.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )


def bearer(header):
    """The token of an `Authorization: Bearer <token>` header, or ''."""
    scheme, _, token = (header or "").strip().partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""
