# Agent notes

- Display official HKO/LD icons. Do not draw substitute warning symbols.
- HSWW level comes only from `iconIndex` (30 amber / 32 red / 34 black). Never infer level from HKHI CSV or from the title string.
- Do not commit `.env`, real site files or real site names. Only `config/sites/demo-site.json` is in git; real site files live on the server.
- Rest numbers live in `config/rest_schedule.json` only. UI must not hardcode minutes.
- Instruction text lives in `config/display_actions.json`. Every displayed fragment must be a verbatim, contiguous part of a quoted official sentence; `tests/test_display_actions.py` enforces this. Never paraphrase official wording.
- Re-verify the official sources every April and whenever LD or HKO announce revisions (checklist: `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md` §9). The weekly check (`scripts/check_official_sources.py`) only flags a change. Run `--update-lock` only after a person has re-verified the changed PDF.
- The screen's position only chooses the weather and wind stations. It must never influence warnings, rest times or wording, and must stay out of logs. Show humidity only with 香港天文台. Station coordinates live in `config/hko_stations.json` (`scripts/fetch_hko_stations.py`).
- Wind is HKO's reading at a named station. Never turn it into a limit, advice or an instruction.
- 「極端情況」 comes only from the operator's switch (`/api/v1/admin/extreme`), which mirrors a Government announcement. Never infer it from HKO data, and never draw an icon for it. Its wording comes only from the `extreme` section of `config/display_actions.json`.
- The admin key lives in Bitwarden and the server's untracked `.env`. Never log, return or commit it. Keep the admin endpoints https-only, with the key in the `Authorization` header and compared in constant time.
- A bad site file must never stop the service or show another site's trades. It is left out and reported in `/api/v1/health`, and its screens show the generic site (every workload level).
- Screens run unattended: never reload while offline, never handle `/api/` in the service worker (`apps/kiosk/public/sw.js`), and keep the page network-first, so a deploy is never held back.
