# Agent notes

- This is a public service with no operator on call. Everything on screen comes from official machine-readable feeds (HKO, LD). Do not add manual switches, admin endpoints or secrets an operator must hold. When no feed exists, as for 「極端情況」, leave the state out and say so in the docs (`docs/superpowers/specs/2026-11-08-no-operator-switch-design.md`).
- Display official HKO/LD icons. Do not draw substitute warning symbols.
- HSWW level comes only from `iconIndex` (30 amber / 32 red / 34 black). Never infer level from HKHI CSV or from the title string.
- Do not commit `.env`, real site files or real site names. Only `config/sites/demo-site.json` is in git; real site files live on the server.
- Rest numbers live in `config/rest_schedule.json` only. UI must not hardcode minutes.
- Instruction text lives in `config/display_actions.json`. Every displayed fragment must be a verbatim, contiguous part of a quoted official sentence; `tests/test_display_actions.py` enforces this. Never paraphrase official wording.
- English (sites with `"languages": ["zh", "en"]`) follows the same rule: a verbatim part of the official English sentence, quoted from an English LD/HKO source next to the Chinese. Never translate. Every entry needs `"en"`: its English, or `null` when no official English exists, and then no English is shown. HKO's English warning names come from HKO's feeds, never from a table we write.
- Re-verify the official sources every April and whenever LD or HKO announce revisions (checklist: `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md` §9). The weekly check (`scripts/check_official_sources.py`) only flags a change. Run `--update-lock` only after a person has re-verified the changed PDF.
- The screen's position only chooses the weather and wind stations. It must never influence warnings, rest times or wording, and must stay out of logs. Show humidity only with 香港天文台. Station coordinates live in `config/hko_stations.json` (`scripts/fetch_hko_stations.py`).
- Wind is HKO's reading at a named station. Never turn it into a limit, advice or an instruction.
- The 主管注意 reminder after Signal 8 or above, or Black rain, ends (`services/ingest/app/after.py`) comes only from warnsum's codes, actions and times. Never read warningInfo's bulletin text, and never infer an end from the clock. It is kept in memory only, so a restart forgets it (the owner's choice, `docs/superpowers/specs/2026-11-08-after-signal-reminder-design.md`). Its signals and its 24 hours live in that `supervisor` entry of `config/display_actions.json`.
- A bad site file must never stop the service or show another site's trades. It is left out and reported in `/api/v1/health`, and its screens show the generic site (every workload level).
- Screens run unattended: never reload while offline, never handle `/api/` in the service worker (`apps/kiosk/public/sw.js`), and keep the page network-first, so a deploy is never held back.
