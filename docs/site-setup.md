# Putting a screen on site

For whoever installs a gate screen. The work takes about an hour per site:

1. add the site's file on the server;
2. set up the player so it opens the notice by itself;
3. place the screen;
4. check it;
5. optionally, list the supervisors who get an email when the screen changes (§8).

`YOUR-DOMAIN` below is your server's address, for example the one in the README's live demo.

## 1. What you need

| Item | What to get |
|---|---|
| Screen | A TV or monitor, landscape or portrait (the same address works for both). At a gate, 43 inches or larger, so the rest times can be read from a few metres away |
| Player | A mini PC with Google Chrome, or an Android TV box with a kiosk browser app. The browser must be Chrome 105 (2022) or later, or a WebView of that version. A TV's own browser is usually too old: the page then shows tiny or overlapping text |
| Internet | The site's broadband or Wi-Fi, or a 4G/5G router. A screen uses about 10 MB a day (about 300 MB a month) |
| Power | One socket for the screen, the player and the router, so after a power cut all three come back together |

## 2. Add the site on the server

Each site has one file in `config/sites/` on the server. Real site files are never committed to git.

```bash
cd ~/hk-site-display
cp config/sites/demo-site.json config/sites/s7k2.json
nano config/sites/s7k2.json
```

- **`siteId`**: a short code that does not reveal the site, such as `s7k2`. The code is in the screen's address, and anyone who has it can read the site's file through the API. Use a generic `nameZh` for the same reason.
- **`primaryTrades`**: the site's own trade names (`labelZh`), each with its workload: `light`, `moderate`, `heavy` or `very_heavy`, as in Labour Department guidance Appendix 1. The safety officer decides these. The rest times themselves come from the Labour Department table in `config/rest_schedule.json`. Never edit that table for one site.
- **`environment`**: `outdoor`, `indoor` (no air-conditioning) or `aircon`. Set it on a trade when that trade differs from the rest of the site.
- **`restAdjustMinutes`**: leave it at `0`, unless the employer's heat stress risk assessment sets an adjustment (Labour Department guidance §5.3–5.5).
- **`weatherStation`** and **`windStation`**: what the bar shows when the screen has no location. Pick the nearest HKO stations from `config/hko_stations.json`: `stations` for the temperature, `windStations` for the wind. Do not pick 昂坪 or 大老山 for the wind unless the site is on a hill: they measure hill-top winds.
- **`alerts`** (optional): the supervisors who get an email when the screen changes, as `{"email": ["name@example.com"]}`. See §8.

Restart the service, wait 10 seconds, and check:

```bash
docker compose restart ingest
curl -s https://YOUR-DOMAIN/api/v1/health
```

You want `"ok": true` and `"siteProblems": []`. If the file has a mistake, `siteProblems` names the file and the problem. Until it is fixed, that site's screens show every workload level (輕勞動, 中等勞動, 重勞動, 極重勞動) instead of the trade names. Other sites are not affected. A mistake in `alerts` is the exception: it is listed too, but only affects who gets emails. The screens keep the site's trades.

Then see what your site's screen will show on hot days, before the hot season:

- `https://YOUR-DOMAIN/?preview=1&site=s7k2&fixture=amber`
- the same with `fixture=red` and `fixture=black`

## 3. Set up the player

The screen's address is `https://YOUR-DOMAIN/?site=s7k2`. Every screen on the same site uses the same address.

**Location.** The page asks for the screen's location, so the bar can show the nearest HKO station. Allow it once, in a normal browser window, before you switch to kiosk mode; the browser remembers it. Most players have no GPS. A PC with Wi-Fi turned on usually gets a usable position from nearby Wi-Fi networks. Otherwise the browser only guesses from the internet address, and that guess is too rough to be used. Either way, the screen falls back to the site's stations. If nobody can answer the browser's question, add `&loc=0` to the address so it is not asked.

Whatever the player, it must:

1. open the address full screen when it powers on, with nobody pressing anything;
2. never sleep, show a screensaver or turn the display off;
3. come back by itself after a power cut;
4. use a normal browser profile, not a private one, so it keeps the location permission and its copy of the page.

The page looks after the rest. It shows the server's time even when the player's clock is wrong. It shows 資料過期 when the data stops arriving. It updates itself within 5 minutes of a new version. If the internet is down when it powers on, it still opens, shows 無法取得資料, and picks up the data by itself once the network is back.

**Windows mini PC (Chrome)**

1. Make a local Windows account that signs in automatically (search for `netplwiz`), so the screen comes back after Windows restarts for an update.
2. Settings → System → Power: screen and sleep both **Never**. Turn location services on (Settings → Privacy & security → Location) if you want the nearest station.
3. Put a shortcut in the Startup folder (Win+R, `shell:startup`), with this target:
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk "https://YOUR-DOMAIN/?site=s7k2"
   ```
   Alt+F4 leaves kiosk mode.
4. In the BIOS/UEFI setup, set *Restore on AC power loss* (or *After power failure*) to **Power On**.
5. Set Windows Update's active hours to cover the working day.

Edge's own kiosk mode is not recommended: it always runs InPrivate, so after every restart it forgets the location permission and the page's copy. If you use it anyway, add `&loc=0`.

**Android TV box**

Chrome is not available for Android TV, so use a kiosk browser app, for example Fully Kiosk Browser. Turn on its settings to start on boot, keep the screen on, and reload when the network reconnects. These apps use the box's *Android System WebView*: check under Settings → Apps that its version is 105 or later. Many cheap boxes have an old WebView that cannot be updated. Choose another box if the page looks wrong.

**The TV itself**

- Turn off every automatic power-off. Many TVs switch themselves off after 2 to 4 hours without a remote-control press (called *Auto Power Off*, *4 Hours Off*, *Idle TV standby* and similar), or when they see no signal.
- Make it power on when the mains comes back. Commercial displays have a setting for this. Many home TVs go to standby after a power cut instead: test it, and if the TV stays off, use a commercial display.
- HDMI-CEC (*Anynet+*, *SimpLink*, *BRAVIA Sync*) can switch the TV on when the player starts, which helps. Some players also switch it off when they idle: test it, and turn CEC off if that happens.
- Use the highest brightness.

## 4. Where to put it

- Where workers pass or queue: the gate, the turnstiles, the site office door. Mount it high enough that people in the queue do not block it.
- Out of direct sun and rain, for example under the gate canopy or inside the guard house window facing out. In direct sun a normal TV cannot be read and can overheat. A high-brightness outdoor display (700 nits or more) is the option for an exposed spot.
- Avoid facing it towards the low morning or evening sun.
- Fix it well enough to stay put in a typhoon, as you would any other item on site.

## 5. Check it on the day

1. The clock on the bar shows the right time. The screen shows the server's time, so a wrong time means the server's clock is wrong, not the player's.
2. The bar shows a station name under the temperature and the wind: the nearest one if the location was allowed, otherwise the site's own.
3. With the preview addresses from step 2, the tiles show the site's trade names, not 輕勞動 / 中等勞動 / 重勞動 / 極重勞動.
4. Switch everything off at the socket, then on. Within a few minutes the notice is back with nobody touching it.
5. Unplug the internet. After 10 minutes the screen shows 資料過期 — 請以我的天文台為準. Plug it back: the message clears by itself within a minute.

## 6. What the screen's messages mean

| On the screen | Meaning | What to do |
|---|---|---|
| 載入中… | Starting | Wait a few seconds |
| 無法取得資料 — 請以我的天文台為準 | The screen cannot reach the server: no internet, or the server is down | Check the site's internet. Meanwhile workers use the MyObservatory app |
| 資料過期 — 請以我的天文台為準 | No fresh warning data for over 10 minutes. The screen still shows the last data | As above. It clears by itself |
| 畫面出錯 — 請以我的天文台為準 | The page hit an error. It redraws itself with the next data | If it stays for more than a minute, restart the player and report it |
| Tiles show 輕勞動 / 中等勞動 / 重勞動 / 極重勞動 instead of trade names | The address's `?site=` does not match a site file that works | Check the address, and `siteProblems` in `/api/v1/health` |

## 7. Keeping it running

- **Monitoring.** Point an uptime monitor (many are free) at `https://YOUR-DOMAIN/api/v1/health`. It answers 503, which a monitor reports as down, when the warning data is stale, the data fetching has stopped, or a site file has a mistake.
- **Updates.** A new version reaches every screen within 5 minutes. Nobody needs to visit.
- **Official wording.** A weekly automatic check compares every instruction with its Labour Department or HKO source (README, *Weekly official-source check*). Nothing to do on site.
- **Changing trades.** Edit the site's file and restart the service as in step 2. The screens pick up the change within 30 seconds.
- **Supervisors.** Add or remove addresses in the site's `alerts` and restart the same way. A new supervisor gets emails from the next change on (§8).

## 8. Alerts for supervisors

When the screen changes, each supervisor listed in the site's file gets one short email. It says what changed, what the screen now shows, which warnings are in force, and the screen's address. A real one, from a test run on live HKO data:

```
【地盤乙】強烈季候風信號 發出

地盤乙 · 00:19
強烈季候風信號 發出

告示屏：
正常工作
重至極重勞動：每 2 小時休息 15 分鐘
輕至中等勞動：每 2 小時休息 10 分鐘
主管注意：停止操作起重機、吊船、進行斜坡工程（強烈季候風信號）

現正生效：強烈季候風信號

https://YOUR-DOMAIN/?site=s7k2
```

- **What sends one:**
  - the Heat Stress at Work Warning starting, changing level or ending;
  - any HKO warning issued, changed or cancelled: tropical cyclone signals, the Pre-8 announcement, rainstorm, thunderstorm, landslip and the rest.
- **What does not:**
  - the Labour Department's hourly reminder;
  - a thunderstorm warning being extended;
  - the weather, wind and forecast.
- **Timing.** The email arrives 1–2 minutes after the official change, because the service waits for two readings in a row. The screen and MyObservatory stay the authority.
- **How many.** A burst of quick changes is merged: after 6 messages close together, cancellations wait (about 10 minutes at most) and go out together with the next message. A new warning is never held back.
- **The words.** An email repeats only what the screen shows. It adds no instructions of its own.

**Add the supervisors to the site's file**, then restart and send a test:

```json
"alerts": {
  "email": ["supervisor@example.com", "safety.officer@example.com"]
}
```

```bash
docker compose restart ingest
docker compose exec ingest python -m app.alerts --test s7k2
```

- **The test.** Each supervisor gets 【site name】測試訊息, with the screen as it is now. Ask them to check that it arrived and is not in their spam folder.
- **A new supervisor** gets emails from the next change on. Nothing is sent about warnings already in force.
- **A mistake in the list.** A typo in one address is listed in `siteProblems` (`alerts.email[1] is not an email address`), and the other supervisors still get emails.

**Set up email on the server.** This is done once, by whoever runs the server. Until then, the service runs in dry run: each email is written to the log instead (`docker compose logs ingest`), so you can read what supervisors would get.

1. Get an SMTP account to send from. Either:
   - a mail service with your own domain, which has the best delivery;
   - or a Gmail account with an app password (`smtp.gmail.com`, port 587, two-step verification on).
2. Store the login in Bitwarden Secrets Manager as `HK_SITE_DISPLAY_SMTP_USER` and `HK_SITE_DISPLAY_SMTP_PASSWORD`.
3. Write them to the server's `.env` without printing them. The password is written in single quotes, so `$`, `#` and spaces in it are safe; it must not contain a single quote itself.
   ```bash
   bws run -- sh -c 'printf "SMTP_USER=%s\nSMTP_PASSWORD=\047%s\047\n" "$HK_SITE_DISPLAY_SMTP_USER" "$HK_SITE_DISPLAY_SMTP_PASSWORD"' | ssh YOUR-SERVER 'cat >> ~/hk-site-display/.env && chmod 600 ~/hk-site-display/.env'
   ```
4. Add the other settings to `.env` by hand. None of them is secret:
   ```
   SMTP_HOST=smtp.example.com
   SMTP_PORT=587
   ALERT_FROM=alerts@example.com
   ALERT_OPERATOR=you@example.com
   PUBLIC_URL=https://YOUR-DOMAIN
   ```
   - `SMTP_PORT` 465 uses implicit TLS; any other port uses STARTTLS.
   - `ALERT_FROM` is the sender address. Leave it out to use `SMTP_USER`.
   - `ALERT_OPERATOR` (you) gets one email when the screens' warning data goes stale (資料過期) and one when it comes back. Supervisors do not get these.
   - `PUBLIC_URL` adds the screen's address to each email.
5. Recreate the service, then check:
   ```bash
   docker compose up -d ingest
   curl -s https://YOUR-DOMAIN/api/v1/health
   docker compose exec ingest python -m app.alerts --test operator
   ```
   - The service has to be recreated: `restart` does not read `.env` again.
   - You want `"alerts": {"mode": "email", ...}` with empty `problems`.
   - Add `ALERT_DRY_RUN=true` to `.env` to go back to logging only, without removing the settings.

**When something is wrong**, `/api/v1/health` answers 503 and says why:

| Health shows | Meaning | What to do |
|---|---|---|
| `siteProblems`: `alerts.email[1] is not an email address` | A typo in the site's file. The other supervisors still get emails | Fix it, then `docker compose restart ingest` |
| `alerts.problems`: `set ALERT_FROM ...`, `SMTP_PORT ...` | Email settings that cannot work. The service stays in dry run | Fix `.env`, then `docker compose up -d ingest` |
| `alerts.failingSinceSec` over 900 | Emails have not been going out for 15 minutes | `docker compose logs ingest` shows why (`not sent (SMTPAuthenticationError 535 ...)`, no connection). Fix the account or the network; waiting emails then go out by themselves |
| `alerts.problems`: `ALERT_STATE_FILE cannot be written` | The `alert-state` volume is missing or read-only | Check `docker-compose.yml`. Until it is fixed, a restart may miss a change |

The service keeps what each site was last told on the `alert-state` Docker volume, so a restart or an update never sends an email again. Deleting the volume (`docker compose down -v`) is safe: the next start remembers the current state without sending anything.
