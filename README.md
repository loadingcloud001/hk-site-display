# hk-site-display

Hong Kong construction-site **live display** for Labour Department Heat Stress at Work Warning and HKO extreme weather.

Not a Smart Site Safety System (4S). Official icons and notice text only. Rest times follow Labour Department *Guidance Notes on Prevention of Heat Stroke at Work* Appendix 4.

## Data sources

- HSWW: `https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml` (`iconIndex` 30/32/34)
- Weather warnings: HKO Open Data `warnsum` + `warningInfo`
- Icons: HKO / Labour Department originals in `apps/kiosk/public/official/`

Ingest polls those feeds every 60s. The display refreshes `/api/v1/snapshot` every 30s.

## Local run

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir services/ingest --host 127.0.0.1 --port 8000
cd apps/kiosk && npm install && npm run dev
```

- http://localhost:5173/ or `/?live=1` — live fullscreen (auto-updates)
- http://localhost:5173/?preview=1 — fixture preview (does not replace live snapshot)
- http://localhost:5173/?gallery=1 — every official icon and signal case

`python -m pytest tests -q` (use `.venv/Scripts/python.exe`).

## Deploy

```bash
docker compose up --build -d
```

Open http://SERVER_IP/ (live). Do not commit `.env` or real site names; copy `config/sites/demo-site.json`.
