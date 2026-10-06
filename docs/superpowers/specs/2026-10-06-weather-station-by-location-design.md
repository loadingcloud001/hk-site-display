# Weather station by location: design

Date: 2026-10-06. Builds on `2026-10-06-gate-screen-upgrade-design.md` §4.8.

## 1. Goal

The temperature on the bottom bar should come from the HKO station nearest the screen. The page may ask the browser for the screen's location. With no location, it shows the general HKO reading, 香港天文台, instead of the demo site's 觀塘.

## 2. Behaviour

| Situation | Station shown |
|---|---|
| Location allowed and usable | The nearest station that has a temperature in the latest `rhrread` report |
| No location: refused, unavailable, still waiting, `?loc=0`, or a plain `http://` page | The site's `weatherStation` if set, else 香港天文台 |
| Location too coarse (accuracy over 5 km, typical of an IP-based guess) | As "no location" |
| Location more than 15 km from every station (not in Hong Kong) | As "no location" |
| The chosen station has no reading | The next candidate in the order above, ending at 香港天文台 |
| 香港天文台 has no reading either | No weather block, as today |

The screen never waits for the browser: it renders at once and switches station when a position arrives. The position never touches warnings, rest times or wording.

Humidity is shown only with 香港天文台. HKO's current-weather report gives humidity for that one station, so showing it next to another station's temperature would misattribute it. (Before this change it was shown next to 觀塘.) UV is HKO's single King's Park reading and stays as it was.

## 3. Decisions

**The backend chooses the station; the browser only reports where it is.** The kiosk adds `?lat=&lon=&acc=` to the snapshot request. `app/stations.py` holds the geometry, the accuracy and distance limits, and the choice among stations that currently report. This keeps the logic in the tested Python and the kiosk thin, in line with "backend builds all".

*Alternative considered:* the browser picks the station from a coordinates list and sends only a name, so no position leaves the device. Rejected for now: it needs a second endpoint and TypeScript logic that has no test runner in CI (the kiosk has none), and the position sent is only the screen's own location, rounded to about 1 km. It would be a reasonable change if a deployment must never send a position at all.

**Privacy.** The kiosk rounds the position to 2 decimals (about 1 km) and the accuracy up to 100 m before sending, which is all that is needed when stations are several km apart. The service reads it for one request and keeps nothing. uvicorn's access log is filtered so it shows `lat=-&lon=-&acc=-`. The browser keeps the last position in `localStorage` (`hksd.fix`) so a reload shows the right station at once. It is cleared when the permission is refused.

**Lenient parsing.** `lat`, `lon` and `acc` are read as text. A bad value means "no position", never a 422, because a malformed query must not blank a safety display.

**Fallback configuration.** `weatherStation` in the site config now means the fallback station, not a fixed one, and must be a known HKO station (validated at startup). `district` no longer selects a station; it was only ever used for that, so it was removed from the demo config.

## 4. Data

`config/hko_stations.json` lists the 27 stations in HKO's current-weather report (`rhrread.temperature.data[].place`) with coordinates from HKO's *Information of Weather Station* page (https://www.hko.gov.hk/en/cis/stn.htm), checked 2026-10-06. The report names stations differently from that page, so `scripts/fetch_hko_stations.py` maps each report name to an HKO station code and fails if the code is missing or does not measure air temperature. Non-obvious mappings:

| Report name | Station | Why |
|---|---|---|
| 赤鱲角 | HKA, Hong Kong International Airport | The airport's own station |
| 青衣 | TY1, New Tsing Yi Station | Ching Pak House (CPH) measures no air temperature |
| 荃灣可觀 | TWN, "Tsuen Wan" | Opened 2006-04-25 with the Ho Koon centre; the other Tsuen Wan station is 城門谷 |
| 屯門 | TU1, Tuen Mun Children and Juvenile Home | Tuen Mun Government Offices (TUN) is a wind station |
| 大埔 | YCT, Tai Po (Yuen Chau Tsai Park) | The station moved there on 2022-04-01 |

Stations farther than 15 km from a screen are not used. The limit is set from sample places: every populated part of Hong Kong is within 10 km of a station (Lantau south and Discovery Bay are the farthest), Tap Mun is 12.6 km, Macau is 41 km.

## 5. Kiosk

`src/locate.ts` (`useFix`) runs when the page is live, and only if `window.isSecureContext` and `navigator.geolocation` exist.

1. Start from the remembered position, so the first request can already carry it.
2. If the Permissions API reports `denied`, forget the position and stop. Otherwise call `getCurrentPosition` (low accuracy, 30 s timeout, browser cache up to 5 min), which makes the browser show its own prompt when needed.
3. On a fix, remember and use it, and read it again in 30 minutes. On `PERMISSION_DENIED`, forget it and stop. On any other error, retry after 1, 5, 15, then every 30 minutes.
4. If the permission later becomes `granted` (the Permissions API `change` event), try again at once.

`Kiosk.tsx` appends the position to `/api/v1/snapshot` and restarts its poll when the position changes. `?loc=0` turns the whole thing off.

## 6. Testing

- pytest: station table well formed; every station in a real 27-station report (`tests/fixtures/rhrread_full.json`) has coordinates; nearest-station cases for known places, unreported stations, out-of-Hong-Kong and coarse fixes; query parsing of bad values; the snapshot with and without a position; the API end to end; the access-log filter; a position never changes warnings, tiles or banner.
- Browser (Playwright on Chrome, run by hand, not in CI): allowed (shows 觀塘, sends the rounded query, remembers it), not allowed, far away, coarse, `?loc=0` (no call), once on load, cached position on first request, retry after a failed read, permission granted after load, refusal clears the cache, and the longest names (啟德跑道公園, 荃灣城門谷) in landscape and portrait.

## 7. Rollout and re-verification

Deploy ingest and web in either order: an older ingest ignores the query, and an older kiosk sends none. Allow the location once on each screen. `python3 scripts/fetch_hko_stations.py --check` is item 4 of the April checklist (§9 of the main spec).
