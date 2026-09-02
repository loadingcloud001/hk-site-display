# hk-site-display

Hong Kong construction-site **canteen kiosk** for Labour Department Heat Stress at Work Warning and HKO extreme weather.

Not a Smart Site Safety System (4S). Official icons and notice text only. Rest times follow Labour Department *Guidance Notes on Prevention of Heat Stroke at Work* Appendix 4.

## Data sources

- HSWW: `https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml` (`iconIndex` 30/32/34)
- Weather warnings: HKO Open Data `warnsum` + `warningInfo`
- Icons: HKO / Labour Department originals in `apps/kiosk/public/official/`

## Local run

See `docker-compose.yml` (after Phase E) or ingest + Vite in development.
