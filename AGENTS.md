# Agent notes

- Display official HKO/LD icons. Do not draw substitute warning symbols.
- HSWW level comes only from `iconIndex` (30 amber / 32 red / 34 black). Never infer level from HKHI CSV or from the title string.
- Do not commit `.env` or real site names.
- Rest numbers live in `config/rest_schedule.json` only. UI must not hardcode minutes.
- Instruction text lives in `config/display_actions.json`. Every displayed fragment must be a verbatim, contiguous part of a quoted official sentence; `tests/test_display_actions.py` enforces this. Never paraphrase official wording.
- Re-verify the official sources every April and whenever LD or HKO announce revisions (checklist: `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md` §9).
