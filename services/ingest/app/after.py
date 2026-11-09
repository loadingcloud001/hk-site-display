"""After Signal 8 or above, or Black rain, ends: remembered so the screen can remind supervisors for a while.

HKO's warnsum holds one entry per kind of warning (`WTCSGNL`, `WRAIN`), so it cannot say that a signal was lowered:
Signal 3 after Signal 8 reads exactly like Signal 3 after Signal 1, and once every tropical cyclone signal is
cancelled the entry's code is only `CANCEL`. So the service remembers the last of these signals it saw in force,
and when HKO replaces it with a lower signal or cancels it, records that with HKO's own time: the new entry's issue
time, or the cancellation's update time.

The memory is a plain dict, rebuilt one warnsum reading at a time by `remember`, which never reads the clock: the
same readings always give the same memory. It lives in the ingest process only. A restart forgets it, and the
screen then shows what it showed before this reminder existed. A cancelled signal that HKO still lists (`WRAINB`
with actionCode `CANCEL`; HKO lists a cancellation for about an hour) is read from the reading itself.

Only HKO's structured fields are read: never the bulletin text in warningInfo, and never a guess from the time.
"""
from datetime import timedelta

from app.hko import ACTIVE, parse_warnsum_events, warning_name
from app.weather import HKT, parse_time

# Each signal's place on its own scale. The signals of one kind share one warnsum entry.
LEVELS = {
    "TC1": 1,
    "TC3": 3,
    "TC8NE": 8,
    "TC8SE": 8,
    "TC8NW": 8,
    "TC8SW": 8,
    "TC9": 9,
    "TC10": 10,
    "WRAINA": 1,
    "WRAINR": 2,
    "WRAINB": 3,
}
KINDS = ("WTCSGNL", "WRAIN")
# A change is put down to the remembered signal only if HKO made it within this long of the last reading that
# showed the signal in force. Beyond that the service lost track (HKO's feed or the service was down), so it
# forgets the signal rather than guess.
LOST_TRACK = timedelta(hours=2)
# HKO's times are never meaningfully ahead of the reading that carries them; a later one is not trusted.
AHEAD = timedelta(minutes=15)


def _kind_of(code):
    if code.startswith("TC"):
        return "WTCSGNL"
    if code.startswith("WRAIN"):
        return "WRAIN"
    return None


def _entries(warnsum):
    """Kind -> its warnsum entry, as app.hko.parse_warnsum_events gives it, cancellations included."""
    out = {}
    for event in parse_warnsum_events(warnsum or {}):
        kind = event["key"] if event["key"] in KINDS else _kind_of(event["code"])
        if kind:
            out[kind] = event
    return out


def _names_en(warnsum_en):
    """HKO's English name of every entry in the English warnsum, by code."""
    return {e["code"]: warning_name(e, "en") for e in parse_warnsum_events(warnsum_en or {}) if warning_name(e, "en")}


def _time(value):
    """One of HKO's times (always sent with +08:00), or None when it is missing or has no time zone."""
    at = parse_time(value)
    return at if at is not None and at.tzinfo is not None else None


def _hko_time(value, read_at):
    """HKO's time for a change; the reading's time when HKO gives none, or one later than the reading allows."""
    at = _time(value)
    if at is None or at > read_at + AHEAD:
        return read_at
    return at


def _how_ended(entry, last):
    """'cancel' or 'lower' when this entry ends the remembered signal; None when it says nothing about it."""
    code, action = entry["code"], entry["actionCode"]
    if code == "CANCEL" or action == "CANCEL":
        return "cancel"
    if action in ACTIVE and code in LEVELS and LEVELS[code] < LEVELS.get(last["code"], 0):
        return "lower"
    return None


def remember(memory, warnsum, warnsum_en, read_at, triggers):
    """The memory after one warnsum reading, fetched from HKO at `read_at` (the feed's time, not the clock).

    `memory` maps a kind of warning (WTCSGNL, WRAIN) to the last of the `triggers` seen in force there:
    {code, nameZh, nameEn, issued, seen, ended}. `ended` is None while it is in force, then {at, how} once HKO
    replaced it with a lower signal (how "lower") or cancelled it ("cancel"). `warnsum_en` is HKO's English warnsum,
    read only for the signal's English name.
    """
    out = dict(memory or {})
    entries = _entries(warnsum)
    names_en = _names_en(warnsum_en)
    for kind in KINDS:
        entry = entries.get(kind)
        last = out.get(kind)
        if not entry:
            continue  # no word from HKO about this kind of warning: nothing to go on
        code, action = entry["code"], entry["actionCode"]
        same = last if last and last["code"] == code else None
        if code in triggers and action in ACTIVE:
            out[kind] = {
                "code": code,
                "nameZh": warning_name(entry),
                # HKO's English feed is read after the Chinese one, so a new signal can lack its English for a cycle.
                "nameEn": names_en.get(code) or (same or {}).get("nameEn"),
                "issued": _time(entry["issueTime"]),
                "seen": read_at,
                "ended": None,
            }
        elif code in triggers and action == "CANCEL":
            if same and same["ended"]:
                continue  # already recorded
            at = _hko_time(entry["updateTime"] or entry["issueTime"], read_at)
            out[kind] = {
                "code": code,
                "nameZh": warning_name(entry),
                "nameEn": names_en.get(code) or (same or {}).get("nameEn"),
                "issued": _time(entry["issueTime"]),
                "seen": (same or {}).get("seen") or read_at,
                "ended": {"at": at, "how": "cancel"},
            }
        elif last and not last["ended"]:
            how = _how_ended(entry, last)
            if not how:
                continue
            when = entry["updateTime"] if how == "cancel" else entry["issueTime"]
            at = _hko_time(when or entry["issueTime"] or entry["updateTime"], read_at)
            issued = last["issued"]
            if (issued and at < issued) or at > last["seen"] + LOST_TRACK:
                del out[kind]  # cannot be put down to the remembered signal
            else:
                out[kind] = {**last, "ended": {"at": at, "how": how}}
    return out


def _back_in_force(kind, last, in_force):
    """A signal of the same kind, as high as the remembered one or higher, is in force again."""
    level = LEVELS.get(last["code"], 0)
    return any(_kind_of(code) == kind and LEVELS.get(code, 0) >= level for code in in_force)


def ended_signal(memory, now, hours, in_force=()):
    """The most recent remembered end within `hours` before `now`: {code, nameZh, nameEn, at, how}, else None.

    `in_force` holds the codes in force now. An end is skipped once its signal is back in force, which `remember`
    also sees at its next reading.
    """
    best = None
    for kind, last in (memory or {}).items():
        ended = (last or {}).get("ended")
        if not ended or _back_in_force(kind, last, in_force or ()):
            continue
        if not -AHEAD <= now - ended["at"] < timedelta(hours=hours):
            continue
        if best is None or ended["at"] > best["at"]:
            best = {"code": last["code"], "nameZh": last["nameZh"], "nameEn": last["nameEn"], **ended}
    return best


def when_zh(ended, now, labels):
    """When and how the signal ended: `16:20 取消`, with the date (`11月7日 16:20 取消`) when it was not today."""
    at = ended["at"].astimezone(HKT)
    day = "" if at.date() == now.astimezone(HKT).date() else f"{at.month}月{at.day}日 "
    return f"{day}{at.strftime('%H:%M')} {labels[ended['how']]}"
