# Site-ready upgrade: design

Date: 2026-11-07. Builds on `2026-10-06-gate-screen-upgrade-design.md` and `2026-10-06-weather-station-by-location-design.md`. Installer guide: `docs/site-setup.md`.

## 1. Goal

Make the gate screen practical to run on real sites, unattended, for months:

1. **Wind for lifting work.** Show HKO's 10-minute wind and gust at a nearby station, for crane, gondola and work-at-height decisions.
2. **Tomorrow's rain chance.** Show HKO's 顯著降雨概率 with tomorrow's forecast, for planning concrete pours, painting and lifting.
3. **A screen that looks after itself.** Right time on a TV box with a wrong clock, stale data detected without trusting the device clock, recovery from a crash, self-update after a deploy, no sleeping, and the page opens even when the site's internet is down at power-on.
4. **Health you can monitor.** One URL that says whether the screens are getting fresh official data.
5. **Several sites from one server.** Each site has its own trades and fallback stations, kept on the server outside git, and a mistake in one site's file never affects another site.
6. **Official wording that stays official.** A weekly automatic check that every quoted sentence is still in its LD/HKO source and that the Labour Department PDFs have not changed.
7. **No overlap, ever.** Busy warning days must never push content over the warning icons. A portrait Amber heat stress plus thunderstorm day did, on production, before this change.

## 2. Non-goals

- Turning wind readings into advice. There is no single official wind limit: tower cranes, mobile cranes and gondolas each have their manufacturer's limit, and the crane's own anemometer is the authority. The screen shows HKO's reading and its station, nothing more.
- English or other languages, 「極端情況」, the worker phone page and push alerts. These are follow-ups (§12).

## 3. Wind (bottom bar)

**Source.** HKO's regional weather report `latest_10min_wind_uc.csv` (data.weather.gov.hk), updated every 10 minutes: 10-minute mean direction (compass point), mean speed and maximum gust, in km/h, for 30 stations. Polled every 5 minutes. As with every feed, a failed fetch keeps the last good value. A reading older than 30 minutes is not shown.

**Which station.** The same rules as the temperature (location design §2):

| Situation | Station shown |
|---|---|
| Usable position | The nearest ground-level wind station that reports a speed |
| No usable position | The site's `windStation` |
| Neither | No wind block |

- **High ground is never "nearest".** Ngong Ping (593 m) and Tate's Cairn (572 m) measure hill-top winds, which HKO's forecasts give separately for 高地 (high ground). Wong Tai Sin and Diamond Hill are nearer Tate's Cairn than any street-level wind station, so without this rule they would show hill-top gusts. A site that really is on high ground sets `windStation` and uses `?loc=0`.
- **Hong Kong Sea School** (香港航海學校) is on HKO's wind page but not on its station page, so it has no coordinates. It can be a site's `windStation`, but is never "nearest".

**Station table.** `scripts/fetch_hko_stations.py` now also writes `windStations` in `config/hko_stations.json`. The wind report names stations in Chinese only. HKO's English report lists the same stations in the same order, and HKO's wind page gives the code of each English name. So the script derives every code from HKO and fails if the hand-written `WIND_PLACES` disagrees. Non-obvious codes, confirmed on HKO's wind page:

| Report name | Code | Station |
|---|---|---|
| 赤柱 | BHD | Bluff Head (HKO's wind page calls it Stanley) |
| 青衣 | SHL | Shell Oil Depot (called Tsing Yi) |
| 赤鱲角 | HKA | Hong Kong International Airport |
| 塔門 | TME | Tap Mun East (Tap Mun, TAP, measures temperature only) |
| 屯門 | TUN | Tuen Mun Government Offices |

**Display.** The gust is the big number (`陣風 40 公里/小時`), with the mean wind and the station under it (`東風 22 · 啟德`). An HKO compass point becomes the usual wind name (東 → 東風); anything else is shown as HKO wrote it. Without a gust, the mean wind is the big line.

## 4. Tomorrow's rain chance

`fnd` already carries `PSR` for each day: 高, 中高, 中, 中低 or 低 (HKO Open Data API documentation, field `PSR`, 「顯著降雨概率」). It is shown under tomorrow's range as `顯著降雨概率 低`. Any other value is not shown.

## 5. The bar on busy days

The bar now has up to five parts: the warning icons, the current weather, the wind, tomorrow and the clock.

- **Landscape:** when the warning icons need the room, the bar hides its extras in this order: humidity and UV, then tomorrow, then the wind. The warning icons and the clock are never hidden. The screen measures whether the icons fit, rather than counting them, so it copes with long station names. New content or a new screen size starts again from nothing hidden. The measurement runs before paint, so nothing visibly jumps.
- **Portrait:** the rail wraps instead, and the bar is a 2×2 grid: weather and wind, then tomorrow and the clock. A lone last block is centred.
- **The centre fits too.** When the centre content is taller than the room above the bar, it is scaled down as a whole, to no less than 60 %. Nothing is hidden, because every line in the centre is official wording. Measured at 1080×1920: Amber heat stress + thunderstorm scales to 81 %, Amber + Signal 3 and Rainstorm Amber + Signal 3 to 94 %, and nothing overlaps the warning icons in any preview case.

## 6. Unattended screen

| Problem on site | Behaviour |
|---|---|
| TV box boots with a wrong clock (no RTC, NTP blocked) | The clock shows the server's time. The kiosk keeps the offset from each snapshot's `generatedAt`, ignoring differences under 2 s so a right clock never jitters |
| Wrong clock makes data look fresh or stale | "Stale" is measured on the browser's monotonic clock: 10 minutes without a snapshot, or the server's own `stale` flag |
| A rendering bug or unexpected data | An error boundary shows 畫面出錯 — 請以我的天文台為準 instead of a blank page, and redraws with the next snapshot |
| A fix is deployed but screens run the old page | Every 5 minutes a live screen fetches `/` and compares the entry script name (Vite names it after its content). A new name reloads the page. It never reloads unless the server answered, and preview pages never reload |
| Tablet or TV box sleeps | Screen Wake Lock on live screens, taken again when the page becomes visible |
| Browser caches an old page | nginx serves the page with `no-cache`, the hashed bundles as `immutable`, and official icons for a day |
| Screen powers on, or the kiosk app reloads it, while the site's internet or the server is down | A service worker (`public/sw.js`) keeps a copy of the page and its script, never the data. The page opens, shows 無法取得資料 — 請以我的天文台為準, and shows live data by itself once the network is back. Without it, the browser shows its own error page, which may never retry |

**The service worker never holds back a deploy.** The page always comes from the network when the server answers within 8 s without a server error, so the copy is only used when the network has failed or the server answers 5xx (Caddy answers 502 while the web container restarts). A new copy replaces the old one only after all its files are stored. Old bundles are then dropped. `/api/` is never handled by the worker. It is registered only on built pages, over https or on localhost. To take it off every screen, deploy a `sw.js` that calls `self.registration.unregister()`.

## 7. Health

- `GET /api/v1/health` (public through Caddy): `ok`, `stale`, `poller`, each feed's age and last result, the number of site files in use, and `siteProblems`. It returns **503** when the warning feeds are stale, the poller has stopped, or a site file was left out (§8). Point an uptime monitor at it.
- `GET /healthz` (Docker): 503 when the poller has not finished a cycle in 2 minutes. A bad site file does not fail it, so Docker never restarts the service for one. docker-compose now has health checks for `ingest` and `web`.
- The poller catches and logs any exception in a cycle. Before, an exception escaping `refresh_due` ended the thread silently, and the screens' data froze until a restart.

## 8. Several sites

- Every `config/sites/*.json` is loaded and validated at start-up. A screen chooses its site with `?site=<siteId>` (the file name when `siteId` is absent). Preview takes `?site=` too, so a site can check its own heat-stress tiles before the hot season.
- **A bad file is left out, never fatal.** One server serves several sites, and site files are edited by hand on the server. If a typo stopped the service, every site's screen would lose its warnings. So a file that cannot be read or does not validate is left out, logged, and named in `/api/v1/health` `siteProblems` (503). Two files with the same `siteId` are both left out, because either could be the wrong one. Screens of a left-out site show the generic site until the file is fixed.
- **The generic site** shows every workload level without trade names: the Labour Department table itself, outdoor, with no adjustment. An unknown `?site=` shows it too, and logs a warning once. A typo never blanks a safety screen, and never shows another site's trades.
- **Default site.** Without `?site=`, the screen shows `DEFAULT_SITE`, else the demo site, else the only site file. The default never moves to another site because a file was left out. A bad demo file, a `DEFAULT_SITE` that is not usable, or several sites with no demo and no `DEFAULT_SITE` all give the generic site, and each is reported.
- docker-compose mounts `./config/sites` read-only, so changing a site's trades needs a restart, not a rebuild. Only `demo-site.json` is in git. `.gitignore` keeps real site files out.
- New optional field `windStation` (must be an HKO wind station). The demo site uses 啟德.
- The API returns `site.nameZh`, and anyone who knows a site's id can read it. A site whose name is confidential uses an opaque `siteId` and a generic `nameZh`.

## 9. Weekly official-source check

`scripts/check_official_sources.py` downloads every source in `config/display_actions.json` again and checks that every quote is still there word for word. It ignores only whitespace, list bullets at line starts, full/half-width punctuation and PDF glyph artifacts. The Labour Department PDFs are also compared with `config/official_sources_lock.json` (sha256, size, Last-Modified). A changed PDF fails even when every quote still matches, because the rest tables are not quotes and need a person to compare them (main spec §9). `--update-lock` records the PDFs after that re-check, and refuses while any PDF quote is missing.

`.github/workflows/official-sources.yml` runs it every Monday at 09:00 HKT and on demand, then `scripts/fetch_hko_stations.py --check`. When a scheduled run fails, GitHub notifies the person who last changed the schedule, if their Actions notifications are on. GitHub also disables schedules in public repositories after 60 days without activity.

Run on 2026-11-07: all 6 sources downloaded and all 13 quotes found. Both PDFs are unchanged since the 2026-10-06 verification (Last-Modified 27 Aug 2026 and 5 Jun 2026).

## 10. Testing

- pytest, 256 tests:
  - wind: report parsing (a fixture of HKO's real report for 2026-11-07 22:20, when the Strong Monsoon Signal was in force), missing values and malformed reports, the station table against the real report and HKO's codes, the nearest ground-level station for ten places, the high-ground rule, site fallback, freshness and clock slack;
  - PSR values;
  - site files: default rules, a bad file of each kind left out and named while the others load, duplicates, a left-out file never handing the default to another site, the generic site;
  - the API: `?site=`, wind, preview with a site's own trades, `/api/v1/health` with stale feeds and with a bad site file, `/healthz`, and a failing refresh never stopping the poller;
  - the official-source check, offline: normalisation, matching, lock comparison and the real config.
- Real Chrome (Playwright, run by hand, not in CI):
  - device clock a day ahead and an hour behind; offline for 9 and 11 minutes, then back; a snapshot that cannot be drawn, then a good one; `?site=` sent; wake lock on live screens only (16 checks);
  - auto-update on a built kiosk: same build, server down, new build, preview (6 checks);
  - service worker on a built kiosk: first visit keeps the page and never the data; server down at reload; network back with no reload; a new build through the worker drops the old script; server down after the update; the page answering 502 (11 checks);
  - late-widening text re-fits the bar; every gallery case without clipped icons and with no console errors.
- Docker: both images build and both containers report healthy; nginx headers as in §6, including `sw.js`; the health endpoint with live HKO data inside the network; an unknown site logged.
- Visual: every preview case at 1920×1080 and 1080×1920. README screenshots regenerated at the preview clock.
- A bad site file in a real run: the service starts, health is 503 and names the file, and that site's screen shows the generic tiles.

## 11. Rollout

1. Tag the running images (`pre-site-ready`), then deploy ingest and web as before. The snapshot is backward compatible (new fields only), so an older kiosk ignores `wind` and `psrZh`.
2. Check that `/api/v1/health` returns 200 with an empty `siteProblems`, and look at the live screen in both orientations.
3. The page now on screens has no auto-update, so reload each screen once after this deploy. Later deploys reach screens by themselves within 5 minutes.
4. Run the official-sources workflow once by hand from the Actions tab.

## 12. Follow-ups

- **English for non-Chinese-speaking workers**, using only the official English versions of the same sentences, verbatim, under the same test.
- **「極端情況」.** The Government announces it, but it is not an HKO warning and has no open-data feed. It needs a manual switch on the server, protected by an admin key, showing the Code of Practice's wording.
- **Worker phone page.** A QR code at the gate opening the same notice laid out for a phone.
- **Alerts for supervisors** when the heat-stress level or a signal changes (email or a chat app), sent by the same poller.
