# Agent notes

- Display official HKO/LD icons. Do not draw substitute warning symbols.
- HSWW level comes only from `iconIndex` (30 amber / 32 red / 34 black). Never infer level from HKHI CSV or from the title string.
- Do not commit `.env`, real site files or real site names. Only `config/sites/demo-site.json` is in git; real site files live on the server.
- Rest numbers live in `config/rest_schedule.json` only. UI must not hardcode minutes.
- Instruction text lives in `config/display_actions.json`. Every displayed fragment must be a verbatim, contiguous part of a quoted official sentence; `tests/test_display_actions.py` enforces this. Never paraphrase official wording.
- Re-verify the official sources every April and whenever LD or HKO announce revisions (checklist: `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md` §9). The weekly check (`scripts/check_official_sources.py`) only flags a change. Run `--update-lock` only after a person has re-verified the changed PDF.
- The screen's position only chooses the weather and wind stations. It must never influence warnings, rest times or wording, and must stay out of logs. Show humidity only with 香港天文台. Station coordinates live in `config/hko_stations.json` (`scripts/fetch_hko_stations.py`).
- Wind is HKO's reading at a named station. Never turn it into a limit, advice or an instruction.
- A bad site file must never stop the service or show another site's trades. It is left out and reported in `/api/v1/health`, and its screens show the generic site (every workload level). The exception is a mistake in `alerts`. It only affects who gets alerts, so it is reported, but the file stays in and its screens keep the site's trades.
- Supervisor alerts (`services/ingest/app/alerts.py`) repeat only what the screen shows and add no wording; `tests/test_alerts.py` checks every word. Never put recipient addresses or SMTP credentials in git, logs or `/api/v1/health`.
- Screens run unattended: never reload while offline, never handle `/api/` in the service worker (`apps/kiosk/public/sw.js`), and keep the page network-first, so a deploy is never held back.
