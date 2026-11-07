# Supervisor alerts: design

Date: 2026-11-07. Builds on the site-ready upgrade (`2026-11-07-site-ready-upgrade-design.md`, follow-up in its §12). Set-up: `docs/site-setup.md` §8. Code: `services/ingest/app/alerts.py`, `services/ingest/app/senders.py`.

## 1. Goal

When a site's gate screen changes state, each of the site's supervisors gets one short message, so they can act without watching the screen. Whoever runs the server gets one message when the warning data goes stale, and one when it comes back.

## 2. Non-goals

- **New wording.** A message is built from the snapshot the screen gets and repeats only what the screen shows (§4). It adds no instruction text (AGENTS.md).
- **Replacing the official channels or the screen.** A message goes out 1–2 minutes after HKO or the Labour Department change (§5.1), after the screen has changed. HKO, the Labour Department and the screen stay the authority.
- **Chat apps, SMS, quiet hours, choosing which warnings to get, acknowledgements.** Email comes first, behind a small interface (§7). The rest are follow-ups (§12).

## 3. What counts as a change

| Change | Read from | Sent to |
|---|---|---|
| Heat Stress at Work Warning level: none, amber, red or black | `hkhi_icon.xml` `iconIndex` only (snapshot `hsww.level`) | the site's supervisors |
| Any HKO warning issued or cancelled, or changed to another code of the same kind | `warnsum` (snapshot `hko.warnsum`; names from `signals`) | the site's supervisors |
| The Pre-8 special announcement (預警八號熱帶氣旋警告信號之特別報告) | `warningInfo` `WTCPRE8` | the site's supervisors |
| Warning data stale (no fresh `hkhi_icon.xml` or `warnsum` for 10 minutes, as the screens' 資料過期), and back again | the feeds' fetch times | the operator only |

None of these is a change, so none sends a message:

- an extension or update of a warning already in force: `EXTEND` and `UPDATE` (thunderstorm), `REISSUE` (hot weather, cold weather, northern New Territories flooding);
- the Labour Department's hourly 「仍然生效」 message, at the same level;
- new text in HKO's bulletins, and the weather, wind and forecast;
- a site-file edit, or a screen's position.

**Changed, not cancelled.** HKO's `warnsum` keys each kind of warning by its warning statement code (`WRAIN`, `WTCSGNL`, `WFIRE` and so on) and holds one code under each key (HKO Open Data API documentation, *Weather Warning Summary*). When the code under a key changes, the message names only the new code. Signal No. 3 to No. 8 reads `八號東北烈風或暴風信號 發出`. It does not add `三號強風信號 取消`, which would read as an easing. The Pre-8 announcement counts as a tropical cyclone signal:
- it ends without a line when Signal No. 8 or higher is in force;
- it ends with `… 取消` when HKO withdraws it and no Signal No. 8 follows.

## 4. The message

Plain text in UTF-8. The subject is what a phone shows first. The real message from the dry run on live HKO data (§10), for a second site, at 00:19 HKT on 8 November 2026, with the Strong Monsoon Signal in force:

```
Subject: 【地盤乙】強烈季候風信號 發出

地盤乙 · 00:19
強烈季候風信號 發出

告示屏：
正常工作
重至極重勞動：每 2 小時休息 15 分鐘
輕至中等勞動：每 2 小時休息 10 分鐘
主管注意：停止操作起重機、吊船、進行斜坡工程（強烈季候風信號）

現正生效：強烈季候風信號

https://hksite-display.loadingtechnology.app/?site=s7k2
```

Every line comes from the screen:

| Line | Source |
|---|---|
| `地盤乙 · 00:19` | the site file's `nameZh` (else its `siteId`), and the time the message was made |
| `強烈季候風信號 發出` | the change, worded like the screen's change banner: the warning's name from `signals`, then `發出` or `取消` (HKO), or `生效` or `取消` (heat stress, the Labour Department's own verbs) |
| `告示屏：` and the lines under it | the centre of the screen, in its order (a table below lists them) |
| `現正生效：…` | the name of every warning in force (`signals`): the bar's icons, in words. 現正生效 is HKO's own phrase |
| the address | `PUBLIC_URL/?site=<siteId>`: the screen itself |

The centre of the screen, by mode:

| Screen | Lines | Source |
|---|---|---|
| Weather warning | the instruction and its second line, then the warning's name and issue time | `display.main`, `display.sub` (from `config/display_actions.json`), `display.meta` |
| Heat stress | one line per rest tile, then the warning's name and time, then the note | `restTiles` (from `config/rest_schedule.json`, in the tiles' own words: 暫停工作, 休息 N 分鐘 · 工作 N 分鐘, 休息 N 分鐘 · 每 N 小時), `display.meta`, `notes` |
| Normal | 正常工作 and the normal rest lines | `display.main`, `display.sub` |
| Any but weather | one 主管注意 line per supervisor instruction | `supervisor` (from `config/display_actions.json`) |

- **Several changes in one message.** The subject shows the first change, and ` +N` for the others, as the tiles do for trade names. What is now in force comes first, most severe first (the screen's own `code_rank`), then what was cancelled. So the subject is the most urgent news. An earlier draft ordered by severity alone, and put `雷暴警告 取消` ahead of a new `黃色暴雨警告信號 發出`.
- **One text per site.** A message is built from the site's snapshot without a position. The position only chooses a weather station, so every screen of a site, and every supervisor, gets the same text.
- **A test enforces the rule.** It runs a busy day and checks that every word of every message appears in the snapshots the screen got, except for a few words. Those are the screen's labels (from `Screen.tsx`), the banner's verbs (from `banner.py`), 現正生效 and 告示屏. The test also checks that those words really are in `Screen.tsx` and `banner.py`.

Two more messages, made by the code from the tests' fixtures (Amber heat stress at 14:40; Signal No. 8 at 09:40 and Black Rain at 09:41, after Signal No. 3 and the Pre-8 announcement):

```
Subject: 【示範地盤】黃色工作暑熱警告 生效

示範地盤 · 14:42
黃色工作暑熱警告 生效

告示屏：
紮鐵 · 棚架：休息 45 分鐘 · 工作 15 分鐘
釘板 · 混凝土：休息 30 分鐘 · 工作 30 分鐘
水喉 · 焊接：休息 15 分鐘 · 工作 45 分鐘
保安 · 檢查：休息 10 分鐘 · 每 2 小時
黃色工作暑熱警告 · 14:40 生效
僱員未適應或需重新適應在酷熱環境中工作：每小時的休息時間應增加15分鐘

現正生效：黃色工作暑熱警告

https://hksite-display.loadingtechnology.app/?site=demo-kai-tak
```

```
Subject: 【示範地盤】八號東北烈風或暴風信號 發出 +1

示範地盤 · 09:43
八號東北烈風或暴風信號 發出
黑色暴雨警告信號 發出

告示屏：
停止戶外作業
並到安全地方暫避
黑色暴雨警告信號 · 09:41 發出

現正生效：八號東北烈風或暴風信號 · 黑色暴雨警告信號

https://hksite-display.loadingtechnology.app/?site=demo-kai-tak
```

The Pre-8 announcement was in force before the second message, and ended with it. It gets no line (§3).

**The operator's messages** are in English, for whoever runs the server, and name the stale banner the screens show:

```
Subject: [hk-site-display] Warning data stale: screens show 資料過期

No fresh Heat Stress at Work Warning or HKO warning data since 09:02.
Every screen shows 資料過期 — 請以我的天文台為準 with the last data it had.

Check: https://hksite-display.loadingtechnology.app/api/v1/health
```

When the data comes back: `[hk-site-display] Warning data back: screens are live`.

## 5. One message per real change

### 5.1 Two readings in a row

The state has three parts, and each comes from one feed: the heat-stress level from `hkhi_icon.xml`, the warnings from `warnsum`, the Pre-8 announcement from `warningInfo`. A part takes a new value only when two fetches of its own feed in a row agree, because HKO feeds glitch.

- A failed fetch leaves the old value in the cache, and it is not counted as a reading. Otherwise one glitched answer, then a network error, would count twice and send a false message.
- The warning feeds are fetched every 60 s, so a message goes out 1–2 minutes after the official change.
- Stale data is measured on time, every poller cycle (15 s), from the warning feeds' last good fetch. A feed never fetched since the service started counts from the start. So a restart during an HKO outage reads as stale after 10 minutes, and never as a recovery.

### 5.2 What each site was last told

`ALERT_STATE_FILE`, on the `alert-state` Docker volume, keeps two things per site, and for the operator: the state last sent, and the rate-limit bucket. A message describes the difference between the state last sent and the confirmed state.

- **Restart.** The file still says what was sent, so nothing is sent again. A change made while the service was down is sent once the new state is confirmed.
- **First sight.** A site, or a part of the state, missing from the file is remembered without a message, even during a warning. A new site, a new recipient or a lost file never sends what was already true. The test command (§8) shows supervisors the screen as it is now.
- **Nothing visible.** A change the supervisors would not see updates the file without a message: the Pre-8 announcement ending under Signal No. 8, or HKO renaming a warning that stays in force.
- **Dry run** updates the file too, so switching email on later does not send old changes.
- **Writing.** The file is written to a temporary file, synced and renamed. A damaged file is kept as `alerts.json.bad`, and the service starts again from first sight. A file that cannot be written is reported in `/api/v1/health`.

### 5.3 Rate limit

Each site, and the operator, can get up to 6 messages at once, then one every 10 minutes (a token bucket).

- **A change that issues a warning or raises a level is never held back.** That covers a new warning, a higher heat-stress level, Signal No. 3 to No. 8, Amber to Red or Black rain, and the data going stale. It still spends a token, down to −6.
- **Everything else waits for a token:** cancellations, lower levels, and a change to a code of the same rank (Signal No. 8 changing direction, Yellow to Red fire danger). A waiting change is merged: the next message says everything that changed since the last one sent, and nothing if it changed back.
- **Flapping stays bounded.** A warning can only be issued again after its cancellation was sent, and cancellations wait. A test runs a thunderstorm warning that comes and goes every two fetches for three hours: 11 messages in the first hour, then 6 an hour. Without the limit that would be 30 an hour.

Why the exception: an extreme day can bring several changes within an hour (thunderstorm, Amber, Red and Black rain, landslip, flooding in the northern New Territories). On those days a supervisor needs every new warning at once. In a simulation of a busy day, a plain bucket held back Signal No. 8 with Black Rain, because earlier and milder messages had used it up.

### 5.4 Failures

- A send that fails (no connection, login refused) is retried after 1, 2, 5 and 10 minutes, then every 30 minutes. While it fails, no other site is tried in that cycle, since they share the mail server.
- A recipient the mail server refuses is logged, masked, and not retried. The others still get the message.
- One poller cycle spends at most 20 s sending, and each SMTP step times out after 10 s, so a slow mail server never holds up the screens' data.
- Any error in the alert check is caught and logged once, and never stops the poller.
- A failure stops counting once nothing is left to send. So a change that was undone before the retry does not keep health failing.

## 6. Recipients

Each site's supervisors are listed in its file on the server (`config/sites/<id>.json`, untracked):

```json
"alerts": {
  "email": ["supervisor@example.com", "safety.officer@example.com"]
}
```

The field is checked at start-up, like the rest of the file. A mistake changes only who gets alerts, never what the site's screens show:

| Mistake | Result |
|---|---|
| `alerts` is not an object, or `alerts.email` is not a list | no alerts for the site |
| an entry is not an email address | that entry gets nothing; the others still get alerts |
| an unknown key (`alerts.telegram`, `alerts.Email`) | ignored |
| more than 20 addresses | the first 20 get alerts |
| the same address twice, in any case | sent once |

- Each mistake is listed in `/api/v1/health` `siteProblems`, which then returns 503 like any other site-file mistake. The site's screens keep its own trades: unlike other mistakes, the file is not left out.
- `/api/v1/health` is public, so a problem names the field and index (`alerts.email[2]`), never the address.
- Several sites can list the same person, who then gets one message for each site.
- Whoever runs the server is `ALERT_OPERATOR` (comma-separated). It gets the stale and recovery messages only.

## 7. Channel: email, and dry run

**Interface** (`senders.py`): a sender has a `channel` key and `send(recipients, message)`. That returns the recipients the server refused, or raises `SendError` when nothing could be sent. `Message` is a subject and a plain-text body.

- `SmtpSender` sends one copy per recipient, so nobody sees the others' addresses. It uses STARTTLS on 587, or implicit TLS on 465. It sets `Auto-Submitted: auto-generated`, so out-of-office replies are not sent back.
- `DryRunSender` logs each message instead, with masked addresses. It is the default.
- A chat bot is another sender, with its own channel key, matching a key next to `email` in the site file's `alerts`. Detection, messages, the state file and the rate limit stay as they are.

**Settings** (environment variables in the server's untracked `.env`, passed through by `docker-compose.yml`):

| Variable | Meaning |
|---|---|
| `SMTP_HOST` | Mail server. Unset: dry run, messages are logged and not sent |
| `SMTP_PORT` | Default 587 |
| `SMTP_SECURITY` | `starttls` (default), `ssl` (default on port 465), or `none` for a relay without login |
| `SMTP_USER`, `SMTP_PASSWORD` | Login. Both, or neither |
| `ALERT_FROM` | Sender address. Default: `SMTP_USER` |
| `ALERT_DRY_RUN` | `true` logs even with SMTP set, to try out a new configuration |
| `ALERT_OPERATOR` | The operator's addresses, comma-separated |
| `PUBLIC_URL` | The screens' address, for the link in each message (`https://hksite-display.loadingtechnology.app`) |
| `ALERT_STATE_FILE` | Default `state/alerts.json` (`/app/state/alerts.json` on the Docker volume) |

A setting that cannot work keeps the service in dry run and is reported in health. That covers a port that is not a number, an unknown security value, a user without a password, a password over `none`, and a missing sender address.

**Secrets.** Once a mail provider is chosen, the SMTP user name and password go in Bitwarden Secrets Manager as `HK_SITE_DISPLAY_SMTP_USER` and `HK_SITE_DISPLAY_SMTP_PASSWORD`. They are written to the server's `.env` without being printed (`docs/site-setup.md` §8). No SMTP account exists yet, which is why dry run is the default. They are read only from the environment. They never appear in git, logs, `/api/v1/health`, a sender's `repr`, or tests (the tests use made-up values and check that they do not leak).

## 8. Operating it

- **`/api/v1/health`** gains an `alerts` block: `mode` (`email` or `dry-run`), the number of sites with recipients, whether an operator is set, how many sites wait for a message (`waiting`), `failingSinceSec`, and `problems`. It returns 503 in these cases:
  - a recipients entry is wrong (`siteProblems`);
  - an alert setting is wrong, or the state file cannot be written;
  - messages have not been going out, or the alert check has been failing, for 15 minutes.

  If email itself is down, the operator cannot be emailed, so the uptime monitor on this URL is how they hear about it.
- **Logs.** The service logs:
  - at start-up, the mode, the number of sites with recipients, the masked operator and the state file;
  - the first confirmed state, and every confirmed change;
  - in dry run, every message in full;
  - otherwise, every message's subject.

  Each failed send and each refused address is logged. A site whose messages are held back is logged once, and an error in the alert check once until it works again. Addresses are always masked (`c***@example.com`).
- **Test message.** `docker compose exec ingest python -m app.alerts --test <siteId>` sends that site's supervisors a message marked 測試訊息, with the screen as it is now. `--test operator` sends one to `ALERT_OPERATOR`. In dry run the message is only logged. A test message does not touch the state file.

## 9. Privacy and safety

- Addresses never leave the server except in the messages themselves. The snapshot returns only a site's id, name and trade fields. Health shows counts and field indexes. Logs mask addresses. The public repository has no addresses: the demo site has no `alerts`.
- Header injection: addresses must match a strict pattern with no spaces or line breaks, the site name is put on one line, and Python's email library rejects line breaks in headers.
- A message carries only what a worker can already read at the gate. A site whose name is confidential already uses a generic `nameZh` (site-ready spec §8).
- With email down, alerts stop but the screens do not. The two never share a failure: any alert error is caught inside the poller cycle.

## 10. Testing

- pytest, 334 tests in all, 78 of them new:
  - change detection for each kind (every heat-stress level; issue and cancel; signals changing code; rain Amber, Red and Black; Pre-8 announced, and ended under No. 8; extensions, updates and reissues ignored);
  - several changes in one message, in order; one text per site;
  - only what the screen shows (above);
  - glitches: one bad fetch, flapping on every fetch, a failed fetch never counted twice;
  - restarts: never sending again, sending a change made while down, new sites starting quietly, damaged and unwritable state files;
  - stale and recovered to the operator only, nothing without an operator, and no false recovery after a restart during an outage;
  - recipients per site, and every kind of bad entry, never naming the address;
  - rate limit: cancellations held and merged, new warnings never held, a held change undone, three hours of flapping;
  - failures: backoff, health after 15 minutes, refused addresses, an exception in the check, a failure with nothing left to send;
  - dry run (no network touched), settings that cannot work, SMTP with a fake server (STARTTLS and login, one copy per recipient, port 465, refused recipient, refused login without the password);
  - health, the poller hook surviving an alert error, and the test command.
- **Dry run on live HKO data** (8 November 2026, 00:17 HKT, Strong Monsoon Signal in force), with the service's own poller:
  - two scratch site files, one of them with a bad third address;
  - a state file where the second site was last told "nothing in force" and the operator "stale".

  Results:
  - the operator's recovery message after 21 s;
  - the second site's message above after 76 s, once two `warnsum` fetches agreed, to its two valid addresses only;
  - the demo site, new to the file, remembered without a message;
  - health 503 naming `config/sites/s7k2.json: alerts.email[2]` and nothing else;
  - `--test s7k2` and `--test operator` logged their messages and left the state file unchanged; `--test` with an unknown site exits 1 at once.

## 11. Rollout

1. Merge, then deploy ingest as usual (tag the running image `pre-alerts` first). With no SMTP settings, the service runs in dry run and only logs. `/api/v1/health` should show `"alerts": {"mode": "dry-run", ...}` and stay 200.
2. Add `alerts.email` to each site's file, set `ALERT_OPERATOR` and `PUBLIC_URL` in `.env`, and restart. Check `siteProblems`, and the start-up log line. Run `--test` for one site and read the logged message.
3. Choose a mail provider. Store the login in Bitwarden, write it to `.env`, restart, and run `--test` for each site. The supervisors should receive the 測試訊息.
4. Leave it in dry run for a day or two first if you like (`ALERT_DRY_RUN=true`). The state file is kept up to date either way.

## 12. Follow-ups

- **A chat bot** (WhatsApp or Telegram) as a second sender (§7).
- **Choosing what to get**, per site: for example no fire danger or cold weather warnings, or quiet hours for non-urgent changes.
- **English messages** for non-Chinese-speaking supervisors, using HKO's and the Labour Department's English names and the official English instructions, as for the screen (site-ready spec §12).
- **An HTML email** with the official icons.
