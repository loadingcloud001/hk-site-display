# hk-site-display

Hong Kong construction-site **canteen kiosk** for Labour Department Heat Stress at Work Warning and HKO extreme weather.

Not a Smart Site Safety System (4S). Official icons and notice text only. Rest times follow Labour Department *Guidance Notes on Prevention of Heat Stroke at Work* Appendix 4.

## Data sources

- HSWW: `https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml` (`iconIndex` 30/32/34)
- Weather warnings: HKO Open Data `warnsum` + `warningInfo`
- Icons: HKO / Labour Department originals in `apps/kiosk/public/official/`

## Local run

```bash
# API
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir services/ingest --host 127.0.0.1 --port 8000

# Kiosk (another terminal)
cd apps/kiosk && npm install && npm run dev
```

Open http://localhost:5173/?gallery=1 — every official icon and every signal case.
Open http://localhost:5173/?sim=1 — fullscreen kiosk; top bar switches cases (none is dark, never white).

`python -m pytest tests -q` (use `.venv/Scripts/python.exe`).

Docker: `docker compose up --build` then http://127.0.0.1:8080/?sim=1
