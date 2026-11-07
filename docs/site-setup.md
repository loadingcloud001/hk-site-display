# Putting a screen on site

For whoever installs a gate screen. The work takes about an hour per site:

1. add the site's file on the server;
2. set up the player so it opens the notice by itself;
3. place the screen;
4. check it.

Section 8 is for the service operator: switching every screen to 「極端情況」.

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

Restart the service, wait 10 seconds, and check:

```bash
docker compose restart ingest
curl -s https://YOUR-DOMAIN/api/v1/health
```

You want `"ok": true` and `"siteProblems": []`. If the file has a mistake, `siteProblems` names the file and the problem. Until it is fixed, that site's screens show every workload level (輕勞動, 中等勞動, 重勞動, 極重勞動) instead of the trade names. Other sites are not affected.

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
| 「極端情況」 with two times, and 留在原來的地點或安全的地點 | The Government has announced 「極端情況」, and the operator has switched it on. It ends by itself at the second time | Follow the instruction and the site's own arrangements. If it looks wrong, call the operator (§8) |

## 7. Keeping it running

- **Monitoring.** Point an uptime monitor (many are free) at `https://YOUR-DOMAIN/api/v1/health`. It answers 503, which a monitor reports as down, when the warning data is stale, the data fetching has stopped, a site file has a mistake, or the 「極端情況」 switch cannot be read or saved.
- **Updates.** A new version reaches every screen within 5 minutes. Nobody needs to visit.
- **Official wording.** A weekly automatic check compares every instruction with its Labour Department or HKO source (README, *Weekly official-source check*). Nothing to do on site.
- **Changing trades.** Edit the site's file and restart the service as in step 2. The screens pick up the change within 30 seconds.

## 8. 「極端情況」 (extreme conditions)

For the service operator, not for each site. After a super typhoon or another large-scale disaster, the Government may announce 「極端情況」 for the whole territory, for a stated period. No data feed carries it, so the operator switches it on, and every screen on the server shows the Labour Department's instruction for it until the announced end. Design: [the spec](superpowers/specs/2026-11-07-extreme-conditions-design.md).

**Who may switch it**

- Only the service operator, who holds the admin key. One switch changes every site's screens.
- Only to mirror a Government announcement of 「極端情況」, with the times it announces. Never for a site's own emergency or anything else: the screens would then quote the Code of Practice for an announcement that does not exist.
- Site staff never switch it. If the screens look wrong, they call the operator.

**Set up the key, once**

1. Generate a random key of at least 32 characters, with a password manager's generator or `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. Keep it in the team's password manager; we use Bitwarden Secrets Manager, key `HK_SITE_DISPLAY_ADMIN_KEY`. A shorter key leaves the switch off.
2. On the server, put it in the untracked `.env` without it showing on screen or in the shell history, and recreate the service. `docker compose restart ingest` is not enough, because it keeps the old environment.
   ```bash
   cd ~/hk-site-display
   touch .env && chmod 600 .env && sed -i '/^ADMIN_KEY=/d' .env
   read -rs -p 'Admin key: ' KEY && echo && printf 'ADMIN_KEY=%s\n' "$KEY" >> .env; unset KEY
   docker compose up -d ingest
   ```
3. Check: `https://YOUR-DOMAIN/api/v1/health` shows `"extreme": {"status": "off"}` and `"extremeProblem": null`, and `extreme` (below) answers `{"status":"off"}`.

**The commands**

In a bash terminal (macOS, Linux, or Git Bash or WSL on Windows), once per terminal:

```bash
read -rs -p 'Admin key: ' ADMIN_KEY; echo
extreme() { printf 'Authorization: Bearer %s\n' "$ADMIN_KEY" | curl -sS -H @- -H 'Content-Type: application/json' "$@" https://YOUR-DOMAIN/api/v1/admin/extreme; echo; }
```

With the Bitwarden CLI, `bws run -- bash` opens a shell with the key in `$HK_SITE_DISPLAY_ADMIN_KEY`; there, use `ADMIN_KEY=$HK_SITE_DISPLAY_ADMIN_KEY` instead of the `read` line. Then:

| To | Run |
|---|---|
| See the state, or test the key | `extreme` |
| Switch on now, until the announced end | `extreme -X PUT -d '{"endsAt": "2026-11-07T19:00"}'` |
| Switch on later, with both announced times | `extreme -X PUT -d '{"startsAt": "2026-11-07T17:00", "endsAt": "2026-11-07T19:00"}'` |
| Extend it, when the Government announces a new end | `extreme -X PUT -d '{"endsAt": "2026-11-07T21:00"}'` (the start stays as it was) |
| End it early, when the Government does | `extreme -X DELETE` |

- Times are Hong Kong time, with the date: `2026-11-07T19:00` or `2026-11-07 19:00`.
- When the announcement gives the start as an event rather than a clock time, for example a signal being replaced, switch on when it happens.
- Otherwise leave it to end by itself at the announced end. The screens show 「極端情況」 結束 for 10 minutes after the end, whether it ended by itself or by `DELETE`.
- `DELETE` before the start withdraws it, and the screens never change. That makes a safe rehearsal: switch on with a start a few minutes ahead, check that the answer says `scheduled`, then `DELETE`.

**What the answers mean**

| Answer | Meaning |
|---|---|
| `"status":"active"` | In force now, until `endsAt`. The screens change within 30 seconds |
| `"status":"scheduled"`, `"ended"` or `"off"` | Starts later; has ended; nothing recorded |
| A reason, such as `endsAt ... has already passed` (400) | The times were refused. Nothing changed |
| `admin-key-required` (401) | Missing or wrong key |
| `admin-disabled` (403) | The server has no `ADMIN_KEY`, or one shorter than 32 characters |
| `https-required` (403) | The address was `http://`. Use `https://`, then replace the key: it has crossed the network in clear |
| `not saved, nothing changed` (503) | The server could not save the switch. See `extremeProblem` in `/api/v1/health` |

**If the key may have leaked**, or was ever sent over `http://`: generate a new one, update the password manager, and repeat step 2. The old key stops working when the service is recreated.
