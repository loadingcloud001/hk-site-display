# Agent notes

- Display official HKO/LD icons. Do not draw substitute warning symbols.
- HSWW level comes only from `iconIndex` (30 amber / 32 red / 34 black). Never infer level from HKHI CSV or from the title string.
- Do not commit `.env` or real site names.
- Rest numbers live in `config/rest_schedule.json` only. UI must not hardcode minutes.
