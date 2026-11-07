"""Supervisor alerts: one short message to each of a site's supervisors when its gate screen changes state.

Detection works on the snapshot the screen gets (app.snapshot.build_snapshot), so a message repeats only what the
screen shows: official warning names, the instruction or rest tiles, the notes and the supervisor lines. The change
words are the screen banner's (生效, 發出, 取消) and HKO's 現正生效. No instruction wording is added here.

The poller in app.main calls AlertEngine.check after each feed refresh.
Design: docs/superpowers/specs/2026-11-07-supervisor-alerts-design.md
"""
import argparse
import copy
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from app.hko import PRE8_NAME, warning_name
from app.senders import Message, SendError, mask, sender_from_env
from app.site import alert_recipients, email_address
from app.snapshot import HSWW_LABEL, code_rank

HKT = timezone(timedelta(hours=8))
log = logging.getLogger("hk_site_display.alerts")

# A new reading must come from this many fetches of its feed in a row, because HKO feeds glitch.
CONFIRM = 2
# Each part of the state comes from one feed, and is read again only when that feed was fetched again.
PARTS = {"heat": "hsww", "warnings": "warnsum", "pre8": "warningInfo"}
# Per site, and for the operator: up to BURST messages at once, then one every REFILL_SEC. A change that issues a
# warning or raises a level is never held back (is_escalation); it spends a token too, down to -BURST.
BURST = 6
REFILL_SEC = 600
# After a failed send, the next try waits this long, then the next value, and so on.
BACKOFF_SEC = (60, 120, 300, 600, 1800)
# /api/v1/health fails once messages have not been going out for this long.
FAILING_AFTER_SEC = 900
# How long one poller cycle may spend sending, so a slow mail server never holds up the screens' data.
SEND_BUDGET_SEC = 20
HSWW_NAME = "工作暑熱警告"
LEVELS = ("none", "amber", "red", "black")
TC8_UP = {"TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10"}
OPERATOR = "operator"
STATE_VERSION = 1


# --- The state a screen shows, and what changed ---------------------------------------------------------------


def read_parts(snap):
    """The alert state from a snapshot: the HSWW level (iconIndex only), warnsum's warnings, the Pre-8 announcement.

    Each warning keeps its name as the screen shows it, for a later 取消 line, and its warnsum key ("group":
    WRAIN, WTCSGNL...), which holds one code at a time (HKO Open Data API documentation, warnsum).
    """
    hko = snap.get("hko") or {}
    names = {s["code"]: s.get("labelZh") or "" for s in snap.get("signals") or []}
    warnings = {}
    for item in hko.get("warnsum") or []:
        code = item["code"]
        label = names.get(code) or warning_name(item) or code
        warnings[code] = {"label": label, "group": item.get("key") or code}
    return {
        "heat": (snap.get("hsww") or {}).get("level") or "none",
        "warnings": warnings,
        "pre8": any(item.get("code") == "WTCPRE8" for item in hko.get("warningInfo") or []),
    }


def warnings_of(state):
    """warnsum's warnings plus the Pre-8 special announcement, which HKO publishes in warningInfo."""
    found = dict(state.get("warnings") or {})
    if state.get("pre8"):
        found["WTCPRE8"] = {"label": PRE8_NAME, "group": "WTCSGNL"}
    return found


def change_lines(old, new):
    """What changed from `old` to `new`, in the words of the screen's change banner: what is now in force first,
    most severe first, then what was cancelled. The first line is the message's subject."""
    found = []
    if old.get("heat") != new.get("heat"):
        level = new.get("heat")
        if level in HSWW_LABEL:
            found.append((code_rank(f"HSWW-{level}"), 0, f"{HSWW_LABEL[level]} 生效"))
        else:
            found.append((code_rank("HSWW"), 1, f"{HSWW_NAME} 取消"))
    before, after = warnings_of(old), warnings_of(new)
    added = [code for code in after if code not in before]
    replaced = {after[code]["group"] for code in added}
    for code in added:
        found.append((code_rank(code), 0, f"{after[code]['label']} 發出"))
    for code, item in before.items():
        if code in after or item["group"] in replaced:
            continue  # still in force, or replaced by a new code of the same kind: Signal 3 by No. 8, Amber by Red
        if code == "WTCPRE8" and TC8_UP & set(after):
            continue  # the Pre-8 announcement ends once Signal No. 8 or higher is in force
        found.append((code_rank(code), 1, f"{item['label']} 取消"))
    return [text for _, _, text in sorted(found, key=lambda f: (f[1], f[0]))]


def is_escalation(old, new):
    """True when the change issues a warning, or raises a level: heat stress up, Signal 3 to 8, Amber to Black rain.

    These go out at once whatever the rate limit. Flapping stays bounded: a warning can only be issued again
    after its cancellation was sent, and cancellations wait for the rate limit.
    """
    if LEVELS.index(new.get("heat", "none")) > LEVELS.index(old.get("heat", "none")):
        return True
    before, after = warnings_of(old), warnings_of(new)
    for code, item in after.items():
        if code in before:
            continue
        replaced = [c for c, i in before.items() if c not in after and i["group"] == item["group"]]
        if not replaced or code_rank(code) < min(code_rank(c) for c in replaced):
            return True
    return False


def in_force(state):
    names = [HSWW_LABEL[state["heat"]]] if state.get("heat") in HSWW_LABEL else []
    return names + [item["label"] for item in warnings_of(state).values()]


# --- Messages -------------------------------------------------------------------------------------------------


def screen_lines(snap):
    """The centre of the screen as text, in the screen's order and its own words (Screen.tsx)."""
    display = snap.get("display") or {}
    lines = []
    if display.get("mode") == "heat":
        for tile in snap.get("restTiles") or []:
            if tile["kind"] == "suspend":
                what = "暫停工作"
            elif tile["kind"] == "baseline":
                what = f"休息 {tile['rest']} 分鐘 · 每 {tile['perHours']} 小時"
            else:
                what = f"休息 {tile['rest']} 分鐘 · 工作 {tile['work']} 分鐘"
            lines.append(f"{' · '.join(tile['trades'])}：{what}")
        lines.append(display.get("meta") or "")
        lines += snap.get("notes") or []
    else:
        lines.append(display.get("main") or display.get("action") or "")
        lines += display.get("sub") or []
        lines.append(display.get("meta") or "")
    lines += [f"主管注意：{line['text']}（{line['fromZh']}）" for line in snap.get("supervisor") or []]
    return [line for line in lines if line]


def _one_line(text):
    return " ".join(str(text).split())


def screen_url(public_url, site_id):
    return f"{public_url}/?site={quote(site_id, safe='')}"


def site_message(site_id, site, snap, lines, now, public_url=None, test=False):
    """What changed, then the screen as it is now, the warnings in force and the screen's address."""
    name = _one_line((site or {}).get("nameZh") or site_id)
    changes = ["測試訊息"] if test else list(lines)
    head = changes[0] + (f" +{len(changes) - 1}" if len(changes) > 1 else "")
    body = [f"{name} · {now.astimezone(HKT):%H:%M}", *changes, "", "告示屏：", *screen_lines(snap)]
    names = [s["labelZh"] for s in snap.get("signals") or [] if s.get("labelZh")]
    if names:
        body += ["", "現正生效：" + " · ".join(names)]
    if public_url:
        body += ["", screen_url(public_url, site_id)]
    return Message(f"【{name}】{head}", "\n".join(body))


def _when(at, now):
    at = at.astimezone(HKT)
    return f"{at:%H:%M}" if at.date() == now.astimezone(HKT).date() else f"{at:%d/%m %H:%M}"


def operator_message(stale, last_fresh, now, public_url=None):
    """For whoever runs the server: the warning data stopped, or came back. Never sent to supervisors."""
    check = f"Check: {public_url}/api/v1/health" if public_url else "Check /api/v1/health on the server."
    if stale:
        since = f"since {_when(last_fresh, now)}" if last_fresh else "since the service started"
        return Message(
            "[hk-site-display] Warning data stale: screens show 資料過期",
            f"No fresh Heat Stress at Work Warning or HKO warning data {since}.\n"
            "Every screen shows 資料過期 — 請以我的天文台為準 with the last data it had.\n\n" + check,
        )
    return Message(
        "[hk-site-display] Warning data back: screens are live",
        f"Fresh warning data again at {_when(now, now)}. The screens are live.\n\n" + check,
    )


# --- Detection, delivery and memory ---------------------------------------------------------------------------


@dataclass
class Reading:
    """One part of the state. A new value counts only after CONFIRM readings in a row from fresh fetches."""

    value: object = None
    known: bool = False
    pending: object = None
    count: int = 0
    seen: object = None

    def read(self, value, mark):
        """`mark` tells fetches apart (the feed's fetched_at). A repeat of the same fetch is not a new reading."""
        if mark is None or mark == self.seen:
            return
        self.seen = mark
        if self.known and value == self.value:
            self.pending, self.count = None, 0
            return
        if self.count and value == self.pending:
            self.count += 1
        else:
            self.pending, self.count = value, 1
        if self.count >= CONFIRM:
            self.value, self.known, self.pending, self.count = value, True, None, 0


@dataclass(frozen=True)
class Target:
    key: str
    recipients: dict
    site: dict | None = None


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valid_entry(entry):
    if not isinstance(entry, dict):
        return False
    sent, bucket = entry.get("sent", {}), entry.get("bucket", {})
    if not isinstance(sent, dict) or not isinstance(bucket, dict):
        return False
    if not all(_number(bucket[k]) for k in ("tokens", "at") if k in bucket):
        return False
    if "heat" in sent and sent["heat"] not in LEVELS:
        return False
    if any(k in sent and not isinstance(sent[k], bool) for k in ("pre8", "stale")):
        return False
    warnings = sent.get("warnings", {})
    return isinstance(warnings, dict) and all(
        isinstance(w, dict) and isinstance(w.get("label"), str) and isinstance(w.get("group"), str)
        for w in warnings.values()
    )


def valid_state(data):
    if not isinstance(data, dict) or data.get("version") != STATE_VERSION or not isinstance(data.get("sites"), dict):
        return False
    entries = list(data["sites"].values()) + ([data["operator"]] if "operator" in data else [])
    return all(_valid_entry(entry) for entry in entries)


class AlertEngine:
    """Watches the confirmed state, and brings each site's supervisors (and the operator) up to date with it.

    Per site the state file keeps what was last sent. A site, or a part of the state, seen for the first time is
    remembered without a message, so a restart or a new recipient never sends again what was already true. A
    change while the service was down is sent after the restart, because the file still has the older state.
    """

    def __init__(self, sites, sender, state_path, operator=(), public_url=None, problems=(), stale_after=600):
        self.sender = sender
        self.senders = {sender.channel: sender}
        self.targets = {}
        for site_id, site in sites.items():
            recipients = alert_recipients(site)[0]
            if recipients:
                self.targets[site_id] = Target(site_id, recipients, site)
        self.operator = Target(OPERATOR, {"email": list(operator)}) if operator else None
        self.public_url = public_url or None
        self.problems = list(problems)
        self.path = Path(state_path) if state_path else None
        self.stale_after = stale_after
        self.started = None
        self.parts = {name: Reading() for name in PARTS}
        self.stale = Reading()
        self.data = None
        self.watching = None
        self.failures, self.failing_since, self.retry_at = 0, None, None
        self.error_since = None
        self.save_problem = None
        self.held = set()
        self.waiting = 0

    # The poller's entry point. Never raises: alerts must never stop the screens' data.
    def check(self, now, marks, snapshot_for):
        """One poller cycle. `marks`: each feed's fetched_at. `snapshot_for(site)`: the live snapshot for a site
        (None for any site), as a screen without a position gets it."""
        try:
            self._check(now, marks, snapshot_for)
        except Exception:
            if self.error_since is None:
                log.exception("alert check failed; the screens are not affected")
            self.error_since = self.error_since or now
            return
        if self.error_since is not None:
            log.info("alert checks work again")
        self.error_since = None

    def _check(self, now, marks, snapshot_for):
        self._load()
        self.started = self.started or now
        parts = read_parts(snapshot_for(None))
        for name, feed in PARTS.items():
            self.parts[name].read(parts[name], marks.get(feed))
        current = {name: reading.value for name, reading in self.parts.items() if reading.known}
        self._log_confirmed(current)
        stale = self._stale_reading(now, marks)
        if stale is not None:
            self.stale.read(stale, now)  # time-based: every cycle is a reading
        deadline = time.monotonic() + SEND_BUDGET_SEC
        waiting = 0
        for target in self.targets.values():
            waiting += not self._bring_site_up_to_date(target, current, now, snapshot_for, deadline)
        if self.operator and self.stale.known:
            waiting += not self._bring_operator_up_to_date(now, marks, deadline)
        self.waiting = waiting
        if not waiting and self.failures:  # nothing left to send, so an earlier failure no longer matters
            self.failures, self.failing_since, self.retry_at = 0, None, None

    def _stale_reading(self, now, marks):
        """True when hsww or warnsum has had no fresh fetch for stale_after, as the screens see it. A feed never
        fetched counts from the service's start, so a restart during an outage never reads as a recovery."""
        ages = []
        for feed in ("hsww", "warnsum"):
            at = marks.get(feed) or self.started
            ages.append((now - at).total_seconds())
        if any(marks.get(feed) is None for feed in ("hsww", "warnsum")) and max(ages) < self.stale_after:
            return None
        return max(ages) >= self.stale_after

    def _log_confirmed(self, current):
        if len(current) < len(PARTS):
            return
        if self.watching is None:
            log.info(
                "alerts: watching %d site(s)%s; in force now: %s",
                len(self.targets),
                " and the operator" if self.operator else "",
                " · ".join(in_force(current)) or "nothing",
            )
        elif current != self.watching:
            log.info("alerts: confirmed %s", " · ".join(change_lines(self.watching, current)) or "a change")
        self.watching = copy.deepcopy(current)

    def _bring_site_up_to_date(self, target, current, now, snapshot_for, deadline):
        """True when the site's supervisors have been told the current state."""
        entry = self.data["sites"].setdefault(target.key, {})
        sent = entry.setdefault("sent", {})
        first = {name: value for name, value in current.items() if name not in sent}
        if first:  # first sight of this site, or of this part: remember it without a message
            sent.update(copy.deepcopy(first))
            self._save()
        goal = {**sent, **current}  # a part not yet confirmed since the start keeps what was last sent
        if goal == sent:
            self.held.discard(target.key)
            return True
        lines = change_lines(sent, goal)
        if not lines:  # nothing the supervisors would see differently, like Pre-8 ending under Signal 8
            entry["sent"] = copy.deepcopy(goal)
            self._save()
            return True
        if not self._may_send(target.key, entry, now, deadline, is_escalation(sent, goal)):
            return False
        message = site_message(target.key, target.site, snapshot_for(target.site), lines, now, self.public_url)
        if not self._send(target, message, now):
            return False
        entry["sent"] = copy.deepcopy(goal)
        entry["sentAt"] = now.isoformat(timespec="seconds")
        self._spend(target.key, entry, now)
        self._save()
        return True

    def _bring_operator_up_to_date(self, now, marks, deadline):
        entry = self.data.setdefault("operator", {})
        sent = entry.setdefault("sent", {})
        stale = self.stale.value
        if "stale" not in sent:
            sent["stale"] = stale
            self._save()
        if sent["stale"] == stale:
            self.held.discard(OPERATOR)
            return True
        if not self._may_send(OPERATOR, entry, now, deadline, urgent=stale):
            return False
        fresh = [marks.get(feed) for feed in ("hsww", "warnsum")]
        last_fresh = None if None in fresh else min(fresh)
        if not self._send(self.operator, operator_message(stale, last_fresh, now, self.public_url), now):
            return False
        entry["sent"] = {"stale": stale}
        entry["sentAt"] = now.isoformat(timespec="seconds")
        self._spend(OPERATOR, entry, now)
        self._save()
        return True

    def _tokens(self, entry, now):
        bucket = entry.get("bucket") or {}
        tokens = bucket.get("tokens", BURST)
        if "at" in bucket:
            tokens += max(0.0, now.timestamp() - bucket["at"]) / REFILL_SEC
        return min(float(BURST), tokens)

    def _spend(self, key, entry, now):
        entry["bucket"] = {"tokens": max(-BURST, self._tokens(entry, now) - 1), "at": now.timestamp()}
        self.held.discard(key)

    def _may_send(self, key, entry, now, deadline, urgent=False):
        if self.retry_at is not None and now < self.retry_at:
            return False
        if time.monotonic() > deadline:
            return False
        if not urgent and self._tokens(entry, now) < 1:
            if key not in self.held:
                self.held.add(key)
                log.warning(
                    "alerts for %s: many messages in a short time, so cancellations and lower levels wait; "
                    "the next message, within about %d minutes, covers every change since the last one sent. "
                    "New warnings still go out at once",
                    key,
                    REFILL_SEC // 60,
                )
            return False
        return True

    def _send(self, target, message, now):
        try:
            for channel, addresses in target.recipients.items():
                sender = self.senders.get(channel)
                if sender is None:
                    continue
                for address in sender.send(addresses, message):
                    log.warning("alert for %s: the mail server refused %s", target.key, mask(address))
        except SendError as error:
            self.failures += 1
            self.failing_since = self.failing_since or now
            wait = BACKOFF_SEC[min(self.failures, len(BACKOFF_SEC)) - 1]
            self.retry_at = now + timedelta(seconds=wait)
            log.error("alert for %s not sent (%s); next try in %d s", target.key, error, wait)
            return False
        if self.failures:
            log.info("alerts are going out again")
        self.failures, self.failing_since, self.retry_at = 0, None, None
        if self.sender.mode != "dry-run":
            log.info("alert for %s sent: %s", target.key, message.subject)
        return True

    def _load(self):
        if self.data is not None:
            return
        self.data = {"version": STATE_VERSION, "sites": {}}
        if self.path is None:
            return
        lost = "starting again, so a change made while the service was down is not sent"
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except (OSError, ValueError) as error:
            log.error("cannot read the alert state %s (%s); %s", self.path, error, lost)
            return
        try:
            data = json.loads(text)
            if not valid_state(data):
                raise ValueError("not an alert state file of this version")
        except ValueError as error:
            log.error("alert state %s is damaged (%s); kept as .bad, %s", self.path, error, lost)
            try:
                self.path.replace(self.path.with_name(self.path.name + ".bad"))
            except OSError:
                pass
            return
        self.data = data

    def _save(self):
        if self.path is None:
            return
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=1)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        except OSError as error:
            reason = error.strerror or type(error).__name__
            if self.save_problem is None:
                log.error("cannot write the alert state %s (%s); a restart may miss changes", self.path, reason)
            self.save_problem = f"ALERT_STATE_FILE cannot be written ({reason}); a restart may miss changes"
            return
        self.save_problem = None

    # --- For /api/v1/health -----------------------------------------------------------------------------------

    def current_problems(self):
        return self.problems + ([self.save_problem] if self.save_problem else [])

    def _longest_failure(self, now):
        since = [at for at in (self.failing_since, self.error_since) if at is not None]
        return None if not since else (now - min(since)).total_seconds()

    def healthy(self, now):
        failing = self._longest_failure(now)
        return not self.current_problems() and (failing is None or failing < FAILING_AFTER_SEC)

    def status(self, now):
        failing = self._longest_failure(now)
        return {
            "mode": self.sender.mode,
            "sites": len(self.targets),
            "operator": self.operator is not None,
            "waiting": self.waiting,
            "failingSinceSec": None if failing is None else round(failing),
            "problems": self.current_problems(),
        }

    # --- `python -m app.alerts --test SITE` ---------------------------------------------------------------------

    def send_test(self, key, now, snapshot_for):
        """A test message with the screen as it is now. Does not touch the state file."""
        if key == OPERATOR:
            target = self.operator
            if target is None:
                log.error("ALERT_OPERATOR is not set")
                return False
            body = f"Alerts from hk-site-display reach this address.\nSent at {now.astimezone(HKT):%H:%M} HKT."
            message = Message("[hk-site-display] Test message", body)
        else:
            target = self.targets.get(key)
            if target is None:
                log.error("no site %r with alerts.email; sites with alerts: %s", key, ", ".join(self.targets) or "none")
                return False
            message = site_message(key, target.site, snapshot_for(target.site), [], now, self.public_url, test=True)
        try:
            for channel, addresses in target.recipients.items():
                for address in self.senders[channel].send(addresses, message):
                    log.warning("the mail server refused %s", mask(address))
        except SendError as error:
            log.error("test alert not sent: %s", error)
            return False
        log.info("test alert for %s: %s", key, self.sender.describe())
        return True


def engine_from_env(env, sites, root, stale_after=600):
    """The engine for the service: SMTP settings, operator and state file from environment variables."""
    sender, problems = sender_from_env(env)
    operator = []
    for i, value in enumerate(v for v in (env.get("ALERT_OPERATOR") or "").split(",") if v.strip()):
        address = email_address(value)
        if address is None:
            problems.append(f"ALERT_OPERATOR address {i + 1} is not an email address")
        elif address.lower() not in {a.lower() for a in operator}:
            operator.append(address)
    public_url = (env.get("PUBLIC_URL") or "").strip().rstrip("/")
    if public_url and not public_url.startswith(("https://", "http://")):
        log.warning("PUBLIC_URL must start with https://; messages go out without the screen's address")
        public_url = ""
    state = env.get("ALERT_STATE_FILE") or Path(root) / "state" / "alerts.json"
    engine = AlertEngine(sites, sender, state, operator, public_url, problems, stale_after)
    log.info(
        "alerts: %s; %d site(s) with alerts.email; operator: %s; state: %s",
        sender.describe(),
        len(engine.targets),
        ", ".join(mask(a) for a in operator) or "none",
        state,
    )
    for problem in problems:
        log.error("alerts: %s", problem)
    return engine


def cli(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m app.alerts",
        description="Send a test alert showing the screen as it is now. In dry run it is only logged.",
    )
    parser.add_argument("--test", required=True, metavar="SITE", help="a siteId with alerts.email, or 'operator'")
    args = parser.parse_args(argv)
    from app import main as service  # the service's own site files and alert settings

    if args.test in service.ALERTS.targets:
        service.FEEDS.refresh_due(force=True)  # the screen as it is now
    now = datetime.now(HKT)
    return 0 if service.ALERTS.send_test(args.test, now, service.snapshot_for(now)) else 1


if __name__ == "__main__":
    sys.exit(cli())
