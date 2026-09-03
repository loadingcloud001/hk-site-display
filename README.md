# hk-site-display

Hong Kong construction-site **live display** for Labour Department Heat Stress at Work Warning (HSWW) and HKO extreme weather.

Not a Smart Site Safety System (4S). Not a sensor product. Official HKO / Labour Department icons and notice wording only. Rest times follow *Guidance Notes on Prevention of Heat Stroke at Work* (3rd ed.) Appendix 4.

One URL, two orientations: **16:9 canteen TV** and **9:16 totem**. Two-second glance: one action, every in-force sign in the rail.

## Live demo

| | |
|---|---|
| Live (canteen / TV) | https://hksite-display.loadingtechnology.app/ |
| Preview (fixtures, does not overlay live) | https://hksite-display.loadingtechnology.app/?preview=1 |
| Gallery (every official icon + case) | https://hksite-display.loadingtechnology.app/?gallery=1 |

![Live 16:9 — 正常工作](docs/demo/live-16x9.png)

![Amber HSWW — 休息 45 分鐘](docs/demo/amber.png)

![Signal 8 NE — 留在室內](docs/demo/tc8.png)

Same URL on a portrait totem:

![Live 9:16](docs/demo/live-9x16.png)

## Rules the display will not break

- HSWW level comes only from `hkhi_icon.xml` `iconIndex` (30 amber / 32 red / 34 black). Never inferred from HKHI CSV or the title string.
- Rest minutes live in `config/rest_schedule.json` only.
- Warning marks are official HKO/LD files. We do not draw substitute typhoon / rain / heat symbols.
- `GET /api/v1/snapshot` is always live. `POST /sim` is preview-only.

## Data sources

- HSWW: `https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml`
- Weather warnings: HKO Open Data `warnsum` + `warningInfo`
- Icons: originals in `apps/kiosk/public/official/`

Ingest polls every 60s. The display refreshes `/api/v1/snapshot` every 30s.

## Local run

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir services/ingest --host 127.0.0.1 --port 8000
cd apps/kiosk && npm install && npm run dev
```

- http://localhost:5173/ — live fullscreen
- http://localhost:5173/?preview=1 — fixture preview
- http://localhost:5173/?gallery=1 — every official icon and signal case

`python -m pytest tests -q` (use `.venv/Scripts/python.exe`).

## Deploy

```bash
docker compose up --build -d
```

Open http://SERVER_IP/ (live). Do not commit `.env`, origin certificates, or real site names; copy `config/sites/demo-site.json`.
