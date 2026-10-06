# Gate Screen Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the construction-site gate screen correct against the latest Labour Department and HKO guidance, and more useful at a glance. It gets per-trade heat-stress rest tiles, official instruction wording with a guard test, a supervisor line, district weather with tomorrow's forecast, and a 10-minute change banner, all in one centred layout that works in landscape and portrait.

**Architecture:**
- **Backend.** The FastAPI ingest service builds everything into `GET /api/v1/snapshot` from small pure-function modules: rest, heat, hsww, hko, weather, banner, state and actions. Each official feed is cached separately with its own refresh interval.
- **Frontend.** The React kiosk only renders. One `Screen` component is used full-size by the kiosk and scaled down in the Gallery, sized with CSS container-query units.
- **Config.** Rest numbers and instruction wording live only in `config/`. The instruction wording is stored with the verbatim official sentences it comes from.

**Tech Stack:** Python 3.11 / FastAPI / httpx / pytest; React 18 / TypeScript / Vite 5; Docker Compose + Caddy (unchanged).

**Spec:** `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md`. Read §3 (sources and corrections) and §4 (screen design) before starting.

---

## Conventions for every task

- Work from the repo root `hk-site-display/`.
- Python env: if `.venv/` is missing, create it once:
  ```bash
  python3 -m venv .venv && .venv/bin/pip install pytest fastapi httpx uvicorn
  ```
- Run all backend tests: `.venv/bin/python -m pytest tests -q`. Expected at the start: `46 passed`.
- Frontend: `cd apps/kiosk && npm ci` once; `npm run build` type-checks and builds.
- Commit after each task with the message given. End every commit message with:
  ```
  Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
  ```
- Chinese strings in code and config are **official wording**. Copy them exactly, including full-width punctuation (`，` `：` `︰` `（` `）`). Never retype them from memory.

## File map

| File | Status | Responsibility |
|---|---|---|
| `config/rest_schedule.json` | modify | Appendix 4 rest table, `environmentAdjust`, `baseline`, notes |
| `config/display_actions.json` | rewrite | Official instructions (weather, supervisor, notes) and their quotes |
| `config/wx_icons.json` | create | HKO weather icon codes → official Chinese names |
| `config/official_icons.json` | modify | Signal and rain codes point at HKO 100 px PNGs |
| `config/sites/demo-site.json` | modify | Demo trades from guidance Appendix 1; `weatherStation` |
| `scripts/fetch_official_icons.py` | create | Downloads official HKO icons |
| `services/ingest/app/rest.py` | modify | `compute_rest()` |
| `services/ingest/app/site.py` | create | Site validation, trade lists, workload labels, weather station |
| `services/ingest/app/actions.py` | create | Load, guard and look up `display_actions.json` |
| `services/ingest/app/heat.py` | create | Rest tiles per trade; normal-day rest lines |
| `services/ingest/app/hsww.py` | modify | Message kind (issue / update / cancel) and effective time |
| `services/ingest/app/hko.py` | modify | `PRE8_NAME`; `parse_warnsum_events()` (cancellations included) |
| `services/ingest/app/weather.py` | create | Current weather and tomorrow's forecast |
| `services/ingest/app/banner.py` | create | Stateless 10-minute change banner |
| `services/ingest/app/state.py` | create | Weather precedence, tones, supervisor lines |
| `services/ingest/app/snapshot.py` | modify | Wires everything into the snapshot (new and legacy fields) |
| `services/ingest/app/feeds.py` | create | Per-feed cache with intervals |
| `services/ingest/app/main.py` | modify | FastAPI lifespan, feed set, snapshot endpoint |
| `services/ingest/app/sim_cases.py` | modify | Fixed sim clock, times in fixtures, weather, new cases |
| `apps/kiosk/src/present.ts` | rewrite | Snapshot types and small format helpers |
| `apps/kiosk/src/Screen.tsx` | create | The one screen layout (kiosk and gallery) |
| `apps/kiosk/src/Kiosk.tsx` | modify | Data loading, preview bar, renders `Screen` |
| `apps/kiosk/src/Gallery.tsx` | modify | Renders `Screen` for each case |
| `apps/kiosk/src/kiosk.css` | rewrite | Layout in container-query units, tones, portrait rules |
| `apps/kiosk/src/gallery.css` | modify | Gallery tiles use `Screen` |
| `apps/kiosk/index.html` | modify | Noto Sans HK font |
| `apps/kiosk/package.json` | modify | `build` runs `tsc --noEmit` first |
| `.github/workflows/ci.yml` | modify | Adds the kiosk build job |
| `AGENTS.md`, `README.md`, `apps/kiosk/public/official/README.md`, `apps/kiosk/public/status/README.md` | modify | Rules, sources, config fields |
| `tests/…` | create / modify | One test file per new module; existing tests updated where wording changes |

---

## Task 0: Branch and commit the spec

**Files:**
- Commit: `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md`, `docs/superpowers/specs/2026-10-06-gate-screen-upgrade/*.png`, `docs/superpowers/plans/2026-10-06-gate-screen-upgrade.md`

- [ ] **Step 1: Create the branch**

```bash
git checkout -b feat/gate-screen-upgrade
```

- [ ] **Step 2: Confirm the baseline is green**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `46 passed`

- [ ] **Step 3: Commit the docs**

```bash
git add docs/superpowers
git commit -m "docs: gate screen upgrade spec and plan

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 1: Official names for workload and Pre-8

The guidance's Appendix 1 calls moderate work **中等勞動**. HKO's API calls Pre-8 **預警八號熱帶氣旋警告信號之特別報告**.

**Files:**
- Modify: `services/ingest/app/hko.py` (add constant at top)
- Modify: `services/ingest/app/snapshot.py:18` (`PRE8_CAPTION`) and `:24-29` (`WORKLOAD_ZH`)
- Test: `tests/test_caption.py`, `tests/test_snapshot.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_caption.py`, replace the last test with:

```python
def test_pre8_caption_from_warning_info():
    assert (
        weather_caption([], [{"code": "WTCPRE8", "contents": ["長文公報不應該出現"]}])
        == "預警八號熱帶氣旋警告信號之特別報告"
    )
```

Append to `tests/test_snapshot.py`:

```python
def test_workload_labels_are_official():
    from app.snapshot import WORKLOAD_ZH

    assert WORKLOAD_ZH == {
        "light": "輕勞動",
        "moderate": "中等勞動",
        "heavy": "重勞動",
        "very_heavy": "極重勞動",
    }
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_caption.py tests/test_snapshot.py -q`
Expected: 2 failed (`預警八號熱帶氣旋警告信號` != `…之特別報告`; `中勞動` != `中等勞動`)

- [ ] **Step 3: Implement**

At the top of `services/ingest/app/hko.py`, before `ACTIVE`, add:

```python
# Official name, HKO Open Data API documentation (TC), warningStatementCode WTCPRE8.
PRE8_NAME = "預警八號熱帶氣旋警告信號之特別報告"
```

In `services/ingest/app/snapshot.py`:
- Change the import line `from app.hko import parse_warnsum, parse_warning_info, active_codes` to:

  ```python
  from app.hko import PRE8_NAME, active_codes, parse_warning_info, parse_warnsum
  ```

- Replace `PRE8_CAPTION = "預警八號熱帶氣旋警告信號"` with:

  ```python
  PRE8_CAPTION = PRE8_NAME
  ```

- In `WORKLOAD_ZH`, change `"moderate": "中勞動",` to:

  ```python
      "moderate": "中等勞動",
  ```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `47 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/hko.py services/ingest/app/snapshot.py tests/test_caption.py tests/test_snapshot.py
git commit -m "fix: official names for moderate workload and Pre-8 announcement

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 2: Rest schedule matches both official appendices

Encode Appendix 4 so that indoor work (−15 minutes) reproduces Appendix 4(a) exactly. Add the 2-hour baseline (para 4.7.1). The Black/very-heavy cell becomes 75 (still `suspend`); spec §4.6 explains why.

**Files:**
- Modify: `config/rest_schedule.json` (whole file)
- Test: `tests/test_rest_schedule.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rest_schedule.py`:

```python
# Labour Department guidance notes, 3rd edition (revised) Aug 2026.
# (work, rest) per hour; "S" = 暫停工作; None = no hourly rest arrangement.
APPENDIX_4 = {
    "amber": {"light": None, "moderate": (45, 15), "heavy": (30, 30), "very_heavy": (15, 45)},
    "red": {"light": (45, 15), "moderate": (30, 30), "heavy": (15, 45), "very_heavy": "S"},
    "black": {"light": (30, 30), "moderate": (15, 45), "heavy": "S", "very_heavy": "S"},
}
APPENDIX_4A = {
    "amber": {"light": None, "moderate": None, "heavy": (45, 15), "very_heavy": (30, 30)},
    "red": {"light": None, "moderate": (45, 15), "heavy": (30, 30), "very_heavy": (15, 45)},
    "black": {"light": (45, 15), "moderate": (30, 30), "heavy": (15, 45), "very_heavy": "S"},
}


def cell_view(rest):
    if rest >= 60:
        return "S"
    if rest <= 0:
        return None
    return (60 - rest, rest)


def test_outdoor_matches_appendix_4():
    s = load()
    for level, row in APPENDIX_4.items():
        for workload, want in row.items():
            cell = s["outdoor"][level][workload]
            assert cell_view(cell["rest"]) == want, (level, workload)
            if isinstance(want, tuple):
                assert cell["work"] == want[0], (level, workload)


def test_indoor_adjustment_reproduces_appendix_4a():
    s = load()
    adjust = s["environmentAdjust"]["indoor"]
    assert s["environmentAdjust"]["outdoor"] == 0
    for level, row in APPENDIX_4A.items():
        for workload, want in row.items():
            assert cell_view(s["outdoor"][level][workload]["rest"] + adjust) == want, (level, workload)


def test_suspend_flag_matches_rest():
    s = load()
    for level in ("amber", "red", "black"):
        for workload, cell in s["outdoor"][level].items():
            assert cell["suspend"] is (cell["rest"] >= 60), (level, workload)


def test_baseline_matches_para_4_7_1():
    assert load()["baseline"] == {"light": 10, "moderate": 10, "heavy": 15, "very_heavy": 15, "perHours": 2}
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_rest_schedule.py -q`
Expected: 2 failed (`KeyError: 'environmentAdjust'`, `KeyError: 'baseline'`)

- [ ] **Step 3: Replace `config/rest_schedule.json`**

```json
{
  "_notes": [
    "Source: Labour Department, Guidance Notes on Prevention of Heat Stroke at Work, 3rd edition (revised) August 2026.",
    "outdoor = Appendix 4. Indoor work without air-conditioning = outdoor + environmentAdjust.indoor (paras 5.2.2 and 5.3.1); tests check this reproduces Appendix 4(a) exactly.",
    "baseline = para 4.7.1; it applies when the adjusted hourly rest is zero or negative (para 5.5.4).",
    "suspend=true cells keep the hourly rest the two appendices imply (the tables step 15 minutes per workload level and per warning level). outdoor black very_heavy is 75 because Appendix 4(a) still suspends it after the 15-minute indoor reduction.",
    "An adjusted hourly rest of 60 minutes or more means suspension of work (para 5.4.5)."
  ],
  "baseline": {"light": 10, "moderate": 10, "heavy": 15, "very_heavy": 15, "perHours": 2},
  "environmentAdjust": {"outdoor": 0, "indoor": -15},
  "outdoor": {
    "none": {
      "light": {"work": 120, "rest": 10, "suspend": false, "perHours": 2},
      "moderate": {"work": 120, "rest": 10, "suspend": false, "perHours": 2},
      "heavy": {"work": 120, "rest": 15, "suspend": false, "perHours": 2},
      "very_heavy": {"work": 120, "rest": 15, "suspend": false, "perHours": 2}
    },
    "amber": {
      "light": {"work": 60, "rest": 0, "suspend": false},
      "moderate": {"work": 45, "rest": 15, "suspend": false},
      "heavy": {"work": 30, "rest": 30, "suspend": false},
      "very_heavy": {"work": 15, "rest": 45, "suspend": false}
    },
    "red": {
      "light": {"work": 45, "rest": 15, "suspend": false},
      "moderate": {"work": 30, "rest": 30, "suspend": false},
      "heavy": {"work": 15, "rest": 45, "suspend": false},
      "very_heavy": {"work": 0, "rest": 60, "suspend": true}
    },
    "black": {
      "light": {"work": 30, "rest": 30, "suspend": false},
      "moderate": {"work": 15, "rest": 45, "suspend": false},
      "heavy": {"work": 0, "rest": 60, "suspend": true},
      "very_heavy": {"work": 0, "rest": 75, "suspend": true}
    }
  }
}
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `51 passed`. The legacy `lookup()` still returns rest 60 for every suspended cell.

- [ ] **Step 5: Commit**

```bash
git add config/rest_schedule.json tests/test_rest_schedule.py
git commit -m "feat: rest schedule matches LD Appendix 4 and 4(a), adds 2-hour baseline

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 3: `compute_rest()` follows the guidance's calculation

Para 5.5.2 method: start from the Appendix 4 value, then add the environment adjustment and the employer's adjustment.
- 60 or more → suspend (5.4.5).
- 0 or less → the 2-hour baseline (5.5.4).
- Air-conditioned indoor work → baseline (footnote 4).

**Files:**
- Modify: `services/ingest/app/rest.py` (append)
- Test: `tests/test_rest.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_rest.py`, change the import to `from app.rest import compute_rest, lookup` and append:

```python
def test_compute_amber_outdoor_very_heavy():
    assert compute_rest(SCHEDULE, "outdoor", "amber", "very_heavy") == {
        "kind": "rest", "rest": 45, "work": 15, "perHours": 1
    }


def test_compute_zero_rest_falls_back_to_two_hour_baseline():
    assert compute_rest(SCHEDULE, "outdoor", "amber", "light") == {
        "kind": "baseline", "rest": 10, "work": None, "perHours": 2
    }
    assert compute_rest(SCHEDULE, "outdoor", "amber", "heavy", -30) == {
        "kind": "baseline", "rest": 15, "work": None, "perHours": 2
    }


def test_compute_suspends_at_sixty():
    assert compute_rest(SCHEDULE, "outdoor", "red", "very_heavy")["kind"] == "suspend"
    assert compute_rest(SCHEDULE, "outdoor", "amber", "very_heavy", 15) == {
        "kind": "suspend", "rest": 60, "work": 0, "perHours": 1
    }


def test_compute_indoor_is_fifteen_less():
    assert compute_rest(SCHEDULE, "indoor", "red", "very_heavy") == {
        "kind": "rest", "rest": 45, "work": 15, "perHours": 1
    }
    assert compute_rest(SCHEDULE, "indoor", "black", "very_heavy")["kind"] == "suspend"


def test_compute_shaded_black_very_heavy_still_suspends():
    # Shelter (-15) on outdoor Black very heavy equals indoor work: Appendix 4(a) suspends it.
    assert compute_rest(SCHEDULE, "outdoor", "black", "very_heavy", -15)["kind"] == "suspend"
    assert compute_rest(SCHEDULE, "outdoor", "black", "very_heavy", -30) == {
        "kind": "rest", "rest": 45, "work": 15, "perHours": 1
    }


def test_compute_aircon_and_no_warning_use_baseline():
    assert compute_rest(SCHEDULE, "aircon", "black", "very_heavy")["kind"] == "baseline"
    assert compute_rest(SCHEDULE, "outdoor", "none", "moderate") == {
        "kind": "baseline", "rest": 10, "work": None, "perHours": 2
    }
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_rest.py -q`
Expected: collection error, `ImportError: cannot import name 'compute_rest'`

- [ ] **Step 3: Implement**

Append to `services/ingest/app/rest.py`:

```python


LEVELS = ("amber", "red", "black")


def compute_rest(schedule, environment, level, workload, adjust_minutes=0):
    """Hourly rest for one trade under a Heat Stress at Work Warning.

    Labour Department guidance notes (3rd ed., Aug 2026) para 5.5.2: start from
    Appendix 4, apply the environment and employer adjustments, suspend work at
    60 minutes or more (5.4.5) and fall back to the 2-hour baseline at zero or
    less (5.5.4). Air-conditioned indoor work needs no hourly rest (footnote 4).
    """
    base = schedule["baseline"]
    baseline = {"kind": "baseline", "rest": base[workload], "work": None, "perHours": base["perHours"]}
    if level not in LEVELS or environment == "aircon":
        return baseline
    rest = (
        int(schedule["outdoor"][level][workload]["rest"])
        + int(schedule["environmentAdjust"][environment])
        + int(adjust_minutes or 0)
    )
    if rest >= 60:
        return {"kind": "suspend", "rest": 60, "work": 0, "perHours": 1}
    if rest <= 0:
        return baseline
    return {"kind": "rest", "rest": rest, "work": 60 - rest, "perHours": 1}
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `57 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/rest.py tests/test_rest.py
git commit -m "feat: compute hourly rest per trade with LD adjustments and baseline

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 4: Site config with validated trades

Trades carry their own workload, plus an optional `environment` and `adjustMinutes`. The demo trades follow the guidance's Appendix 1 examples.

**Files:**
- Create: `services/ingest/app/site.py`
- Modify: `config/sites/demo-site.json` (whole file)
- Modify: `services/ingest/app/snapshot.py` (import `WORKLOAD_ZH` from `app.site`)
- Modify: `services/ingest/app/main.py:35` and `services/ingest/app/sim_cases.py:8` (validate on load)
- Test: `tests/test_site.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_site.py`:

```python
import json
from pathlib import Path

import pytest

from app.site import configured_trades, normal_workloads, tile_trades, validate_site, weather_station

ROOT = Path(__file__).resolve().parents[1]
DEMO = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))


def test_demo_site_is_valid_and_uses_official_examples():
    validate_site(DEMO)
    by = {t["labelZh"]: t["workload"] for t in configured_trades(DEMO)}
    assert by["紮鐵"] == "very_heavy" and by["棚架"] == "very_heavy"
    assert by["釘板"] == "heavy" and by["混凝土"] == "heavy"
    assert by["水喉"] == "moderate" and by["焊接"] == "moderate"
    assert by["保安"] == "light" and by["檢查"] == "light"


def test_trades_inherit_site_environment_and_adjust():
    site = {
        "environment": "indoor",
        "restAdjustMinutes": -15,
        "primaryTrades": [{"labelZh": "電工", "workload": "moderate"}],
    }
    (trade,) = configured_trades(site)
    assert trade == {
        "id": "電工", "labelZh": "電工", "workload": "moderate", "environment": "indoor", "adjustMinutes": -15
    }


def test_trade_overrides_win():
    site = {"primaryTrades": [{"labelZh": "焊接", "workload": "moderate", "environment": "aircon", "adjustMinutes": 15}]}
    (trade,) = configured_trades(site)
    assert trade["environment"] == "aircon" and trade["adjustMinutes"] == 15


def test_no_trades_gives_one_tile_row_per_workload():
    rows = tile_trades({"environment": "outdoor"})
    assert [r["labelZh"] for r in rows] == ["輕勞動", "中等勞動", "重勞動", "極重勞動"]


def test_normal_workloads_fall_back_to_default():
    assert normal_workloads({"defaultWorkload": "heavy"}) == {"heavy"}
    assert normal_workloads(DEMO) == {"light", "moderate", "heavy", "very_heavy"}


def test_weather_station_defaults():
    assert weather_station({"weatherStation": "沙田", "district": "觀塘"}) == "沙田"
    assert weather_station({"district": "觀塘"}) == "觀塘"
    assert weather_station({}) == "香港天文台"


@pytest.mark.parametrize(
    "bad",
    [
        {"environment": "rooftop"},
        {"restAdjustMinutes": 10},
        {"restAdjustMinutes": 75},
        {"primaryTrades": [{"labelZh": "紮鐵", "workload": "extreme"}]},
        {"primaryTrades": [{"workload": "heavy"}]},
        {"primaryTrades": [{"labelZh": "紮鐵", "workload": "heavy", "adjustMinutes": -45}]},
    ],
)
def test_invalid_site_config_raises(bad):
    with pytest.raises(ValueError):
        validate_site(bad)
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_site.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'app.site'`

- [ ] **Step 3: Create `services/ingest/app/site.py`**

```python
"""Site configuration: validation and the trade lists the screen works from."""

WORKLOADS = ("light", "moderate", "heavy", "very_heavy")
ENVIRONMENTS = ("outdoor", "indoor", "aircon")
# Official labels, Labour Department guidance notes Appendix 1.
WORKLOAD_ZH = {"light": "輕勞動", "moderate": "中等勞動", "heavy": "重勞動", "very_heavy": "極重勞動"}
FALLBACK_STATION = "香港天文台"


def _adjust_ok(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value % 15 == 0
        and -30 <= value <= 60
    )


def validate_site(site):
    errors = []
    env = site.get("environment", "outdoor")
    if env not in ENVIRONMENTS:
        errors.append(f"environment {env!r} must be one of {ENVIRONMENTS}")
    if site.get("defaultWorkload", "very_heavy") not in WORKLOADS:
        errors.append(f"defaultWorkload must be one of {WORKLOADS}")
    if not _adjust_ok(site.get("restAdjustMinutes", 0)):
        errors.append("restAdjustMinutes must be a multiple of 15 between -30 and 60")
    for i, trade in enumerate(site.get("primaryTrades") or []):
        where = f"primaryTrades[{i}]"
        if not trade.get("labelZh"):
            errors.append(f"{where}.labelZh is required")
        if trade.get("workload") not in WORKLOADS:
            errors.append(f"{where}.workload must be one of {WORKLOADS}")
        if trade.get("environment", env) not in ENVIRONMENTS:
            errors.append(f"{where}.environment must be one of {ENVIRONMENTS}")
        if "adjustMinutes" in trade and not _adjust_ok(trade["adjustMinutes"]):
            errors.append(f"{where}.adjustMinutes must be a multiple of 15 between -30 and 60")
    if errors:
        raise ValueError("site config: " + "; ".join(errors))
    return site


def configured_trades(site):
    env = site.get("environment", "outdoor")
    adjust = site.get("restAdjustMinutes", 0)
    return [
        {
            "id": t.get("id") or t["labelZh"],
            "labelZh": t["labelZh"],
            "workload": t["workload"],
            "environment": t.get("environment", env),
            "adjustMinutes": t.get("adjustMinutes", adjust),
        }
        for t in site.get("primaryTrades") or []
    ]


def tile_trades(site):
    """Trades for the heat-stress tiles; one row per workload level when none are configured."""
    trades = configured_trades(site)
    if trades:
        return trades
    env = site.get("environment", "outdoor")
    adjust = site.get("restAdjustMinutes", 0)
    return [
        {"id": wl, "labelZh": WORKLOAD_ZH[wl], "workload": wl, "environment": env, "adjustMinutes": adjust}
        for wl in WORKLOADS
    ]


def normal_workloads(site):
    trades = configured_trades(site)
    return {t["workload"] for t in trades} or {site.get("defaultWorkload", "very_heavy")}


def weather_station(site):
    return site.get("weatherStation") or site.get("district") or FALLBACK_STATION
```

- [ ] **Step 4: Replace `config/sites/demo-site.json`**

```json
{
  "siteId": "demo-kai-tak",
  "nameZh": "示範地盤",
  "nameEn": "Demo Site",
  "district": "觀塘",
  "weatherStation": "觀塘",
  "defaultWorkload": "very_heavy",
  "environment": "outdoor",
  "restAdjustMinutes": 0,
  "primaryTrades": [
    { "id": "bar-fixer", "labelZh": "紮鐵", "workload": "very_heavy" },
    { "id": "scaffolder", "labelZh": "棚架", "workload": "very_heavy" },
    { "id": "formwork", "labelZh": "釘板", "workload": "heavy" },
    { "id": "concreter", "labelZh": "混凝土", "workload": "heavy" },
    { "id": "plumber", "labelZh": "水喉", "workload": "moderate" },
    { "id": "welder", "labelZh": "焊接", "workload": "moderate" },
    { "id": "security", "labelZh": "保安", "workload": "light" },
    { "id": "inspector", "labelZh": "檢查", "workload": "light" }
  ]
}
```

- [ ] **Step 5: Use the shared labels and validate on load**

In `services/ingest/app/snapshot.py`, delete the whole `WORKLOAD_ZH = {...}` block. Add this import with the other `app.` imports:

```python
from app.site import WORKLOAD_ZH
```

In `services/ingest/app/main.py`, add `from app.site import validate_site` to the imports, and change the `SITE = ...` line to:

```python
SITE = validate_site(json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8")))
```

In `services/ingest/app/sim_cases.py`, add `from app.site import validate_site` below `from app.snapshot import build_snapshot`, and change the `SITE = ...` line to:

```python
SITE = validate_site(json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8")))
```

- [ ] **Step 6: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `69 passed`

- [ ] **Step 7: Commit**

```bash
git add services/ingest/app/site.py services/ingest/app/snapshot.py services/ingest/app/main.py services/ingest/app/sim_cases.py config/sites/demo-site.json tests/test_site.py
git commit -m "feat: validated site config with per-trade workload and environment

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 5: Official instruction wording with a guard

Every instruction on screen must be a verbatim, contiguous fragment of a quoted official sentence. This task replaces the paraphrased actions (留在室內, 切勿離開有蓋處, 暫停戶外工作, 遠離斜坡, 盡早返回有蓋處) with the official words. It also adds a test that rejects paraphrases.

**Files:**
- Modify: `config/display_actions.json` (whole file)
- Create: `services/ingest/app/actions.py`
- Modify: `services/ingest/app/snapshot.py` (load actions through `app.actions`)
- Test: `tests/test_display_actions.py` (new), `tests/test_sim_cases.py` (expected wording)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_display_actions.py`:

```python
import copy

import pytest

from app.actions import fragment_errors, load_actions, note_text, validate_actions, weather_by_code

ACTIONS = load_actions()


def test_every_displayed_fragment_is_official_wording():
    assert fragment_errors(ACTIONS) == []


def test_paraphrase_is_rejected():
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["tc8"]["main"] = "留在室內"
    assert any("留在室內" in e for e in fragment_errors(bad))
    with pytest.raises(ValueError):
        validate_actions(bad)


def test_unknown_source_is_rejected():
    bad = copy.deepcopy(ACTIONS)
    bad["weather"]["rain-black"]["quotes"][0]["source"] = "blog"
    assert any("unknown source" in e for e in fragment_errors(bad))


def test_weather_codes_map_to_entries():
    by = weather_by_code(ACTIONS)
    assert by["TC8SW"]["main"] == "分批離開工作地點"
    assert by["WTCPRE8"]["sub"] == []
    assert by["WRAINR"]["sub"] == ["直至天氣情況許可為止"]


def test_note_text_joins_fragments():
    assert note_text(ACTIONS, "heatUnacclimatised") == (
        "僱員未適應或需重新適應在酷熱環境中工作：每小時的休息時間應增加15分鐘"
    )
```

In `tests/test_sim_cases.py`, update the expected wording:

```python
def test_pre8_has_short_caption():
    snap = build_case("pre8")
    assert snap["priority"]["band"] == "P1"
    assert snap["display"]["action"] == "分批離開工作地點"
    assert "八號" in snap["display"]["actionSub"]
    codes = [s["code"] for s in snap["signals"]]
    assert "WTCPRE8" in codes
    assert "TC3" in codes


def test_winning_weather_action_sets_tone_not_leftover_hsww():
    pre8a = build_case("pre8-amber")
    assert pre8a["display"]["action"] == "分批離開工作地點"
    assert pre8a["tone"] == "p1"
    stack = build_case("typhoon-stack")
    assert stack["display"]["action"] == "分批離開工作地點"
    assert stack["tone"] == "p0-tc"
```

In `test_official_display_actions`, replace the assertions above the `for name in` loop with:

```python
    assert build_case("tc8ne")["display"]["action"] == "分批離開工作地點"
    assert build_case("tc9")["display"]["action"] == "切勿外出"
    assert build_case("tc10")["display"]["action"] == "切勿離開有遮蔽的地方"
    assert build_case("rain-black")["display"]["action"] == "停止戶外作業"
    assert "暫避" in build_case("rain-black")["display"]["actionSub"]
    assert build_case("rain-red")["display"]["action"] == "暫停戶外作業"
    assert build_case("landslip")["display"]["action"] == "避免靠近陡峭的斜坡和護土牆"
    assert build_case("tsunami")["display"]["action"] == "遠離岸邊"
    assert build_case("amber")["display"]["action"] == "休息 45 分鐘"
    assert build_case("red")["display"]["action"] == "暫停工作"
    assert build_case("none")["display"]["action"] == "正常工作"
    assert build_case("pre8")["display"]["action"] == "分批離開工作地點"
```

(Task 13 changes `typhoon-stack` again, when Black rain starts to outrank Signal 8.)

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_display_actions.py tests/test_sim_cases.py -q`
Expected: collection error for `test_display_actions.py` (`No module named 'app.actions'`); wording failures in `test_sim_cases.py`

- [ ] **Step 3: Replace `config/display_actions.json`**

```json
{
  "sources": {
    "ld-gn-heat": {
      "titleZh": "勞工處《預防工作時中暑指引》",
      "edition": "第三版（修訂）2026年8月",
      "url": "https://www.labour.gov.hk/common/public/oh/Heat_Stress_GN_tc.pdf",
      "checked": "2026-10-06"
    },
    "ld-cop-weather": {
      "titleZh": "勞工處《惡劣天氣及「極端情況」下的工作守則》",
      "edition": "2026年5月（中文版2026年6月）",
      "url": "https://www.labour.gov.hk/tc/public/pdf/wcp/Rainstorm.pdf",
      "checked": "2026-10-06"
    },
    "hko-tc": {
      "titleZh": "天文台《熱帶氣旋警告信號生效時應注意的事項》",
      "edition": "網頁",
      "url": "https://www.hko.gov.hk/tc/informtc/precaution.htm",
      "checked": "2026-10-06"
    },
    "hko-rain": {
      "titleZh": "天文台《暴雨警告系統》",
      "edition": "網頁",
      "url": "https://www.hko.gov.hk/tc/wservice/warning/rainstor.htm",
      "checked": "2026-10-06"
    },
    "hko-landslip": {
      "titleZh": "天文台《山泥傾瀉警告》",
      "edition": "網頁",
      "url": "https://www.hko.gov.hk/tc/wservice/warning/landslip.htm",
      "checked": "2026-10-06"
    },
    "hko-tsunami": {
      "titleZh": "天文台《香港海嘯的監測及警告》",
      "edition": "網頁",
      "url": "https://www.hko.gov.hk/tc/gts/equake/tsunami_mon.htm",
      "checked": "2026-10-06"
    }
  },
  "weather": {
    "tc10": {
      "codes": ["TC10"],
      "main": "切勿離開有遮蔽的地方",
      "sub": ["同時留意風向轉變"],
      "quotes": [
        {"source": "hko-tc", "text": "倘若風眼直接掠過本港，風勢會停息數分鐘至數小時不等，但具有破壞性的風力隨時會突然恢復並從另一個方向吹來。切勿離開有遮蔽的地方，同時留意風向轉變。"}
      ]
    },
    "tc9": {
      "codes": ["TC9"],
      "main": "切勿外出",
      "sub": ["如果已經在有遮蔽的地方躲避，就應該繼續留在原處"],
      "quotes": [
        {"source": "hko-tc", "text": "切勿外出。如果已經在有遮蔽的地方躲避，就應該繼續留在原處。切勿接觸被風吹倒的電線。"}
      ]
    },
    "rain-black": {
      "codes": ["WRAINB"],
      "main": "停止戶外作業",
      "sub": ["並到安全地方暫避"],
      "quotes": [
        {"source": "hko-rain", "text": "在空曠地方工作的人士應停止戶外作業，並到安全地方暫避。"}
      ]
    },
    "tc8": {
      "codes": ["TC8NE", "TC8SE", "TC8NW", "TC8SW"],
      "main": "分批離開工作地點",
      "sub": ["如情況許可，市民應盡早回家"],
      "quotes": [
        {"source": "ld-cop-weather", "text": "當八號預警（在預計發出八號信號前兩小時內發出）或八號信號發出，按預先協定分批離開工作地點或下班。"},
        {"source": "hko-tc", "text": "如情況許可，市民應盡早回家，避免逗留在街上。"}
      ]
    },
    "landslip": {
      "codes": ["WL"],
      "main": "避免靠近陡峭的斜坡和護土牆",
      "sub": ["停止操作起重機、吊船、進行斜坡工程"],
      "quotes": [
        {"source": "hko-landslip", "text": "當山泥傾瀉警告生效時，市民應取消不必要的約會，留在家中或其他安全地方。行人應避免靠近陡峭的斜坡和護土牆。"},
        {"source": "ld-cop-weather", "text": "在發出強烈季候風信號及山泥傾瀉警告時，應停止操作起重機、吊船、進行斜坡工程等工作。"}
      ]
    },
    "tsunami": {
      "codes": ["WTMW"],
      "main": "遠離岸邊",
      "sub": ["前往內陸地方或地勢較高的地面"],
      "quotes": [
        {"source": "hko-tsunami", "text": "遠離岸邊、海灘及沿岸低窪地區。如身處這些地點，應前往內陸地方或地勢較高的地面。"}
      ]
    },
    "pre8": {
      "codes": ["WTCPRE8"],
      "main": "分批離開工作地點",
      "sub": [],
      "quotes": [
        {"source": "ld-cop-weather", "text": "當八號預警（在預計發出八號信號前兩小時內發出）或八號信號發出，按預先協定分批離開工作地點或下班。"}
      ]
    },
    "rain-red": {
      "codes": ["WRAINR"],
      "main": "暫停戶外作業",
      "sub": ["直至天氣情況許可為止"],
      "quotes": [
        {"source": "hko-rain", "text": "在空曠地方工作的人士應暫停戶外作業，直至天氣情況許可為止。"}
      ]
    }
  },
  "supervisor": {
    "thunderstorm": {
      "rank": 1,
      "codes": ["WTS"],
      "fragments": ["有僱員可能遭受雷電擊中時", "立即停止工作，並到安全地方暫避"],
      "quotes": [
        {"source": "ld-cop-weather", "text": "在雷暴警告生效期間及有僱員可能遭受雷電擊中時，主管應在切實可行範圍內盡量安排僱員立即停止工作，並到安全地方暫避。"}
      ]
    },
    "monsoon": {
      "rank": 2,
      "codes": ["WMSGNL"],
      "fragments": ["停止操作起重機、吊船、進行斜坡工程"],
      "quotes": [
        {"source": "ld-cop-weather", "text": "在發出強烈季候風信號及山泥傾瀉警告時，應停止操作起重機、吊船、進行斜坡工程等工作。"}
      ]
    },
    "tc1-tc3": {
      "rank": 3,
      "codes": ["TC1", "TC3"],
      "fragments": ["停止操作起重機、吊船"],
      "quotes": [
        {"source": "ld-cop-weather", "text": "在一號或三號信號期間︰停止操作起重機、吊船等。"}
      ]
    },
    "rain-amber": {
      "rank": 4,
      "codes": ["WRAINA"],
      "fragments": ["停止操作吊船、進行斜坡工程"],
      "quotes": [
        {"source": "ld-cop-weather", "text": "在黃色或紅色暴雨警告期間︰停止操作吊船、進行斜坡工程等工作。"}
      ]
    }
  },
  "notes": {
    "heatUnacclimatised": {
      "fragments": ["僱員未適應或需重新適應在酷熱環境中工作", "每小時的休息時間應增加15分鐘"],
      "quotes": [
        {"source": "ld-gn-heat", "text": "若僱員未適應或需重新適應在酷熱環境中工作，例如以往未曾或超過兩星期不曾在酷熱的環境中工作，僱主除了須跟從第4.6章有關熱適應期的安排外，當工作暑熱警告生效時，有關僱員每小時的休息時間應增加15分鐘。"}
      ]
    }
  }
}
```

- [ ] **Step 4: Create `services/ingest/app/actions.py`**

```python
"""Official instruction wording (config/display_actions.json) and the guard that keeps it verbatim."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACTIONS_PATH = ROOT / "config" / "display_actions.json"


def load_actions(path=ACTIONS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _norm(text):
    return re.sub(r"\s+", "", text or "")


def fragment_errors(actions):
    """Every displayed fragment must be a contiguous substring of one of its official quotes."""
    errors = []
    sources = actions.get("sources") or {}

    def check(where, fragments, quotes):
        if not quotes:
            errors.append(f"{where}: no official quote")
            return
        for quote in quotes:
            if quote.get("source") not in sources:
                errors.append(f"{where}: unknown source {quote.get('source')!r}")
        texts = [_norm(q.get("text")) for q in quotes]
        for fragment in fragments:
            if not _norm(fragment) or not any(_norm(fragment) in t for t in texts):
                errors.append(f"{where}: {fragment!r} is not in the official text")

    for key, spec in (actions.get("weather") or {}).items():
        check(f"weather.{key}", [spec["main"], *spec.get("sub", [])], spec.get("quotes"))
    for key, spec in (actions.get("supervisor") or {}).items():
        check(f"supervisor.{key}", spec.get("fragments") or [], spec.get("quotes"))
    for key, spec in (actions.get("notes") or {}).items():
        check(f"notes.{key}", spec.get("fragments") or [], spec.get("quotes"))
    return errors


def validate_actions(actions):
    errors = fragment_errors(actions)
    if errors:
        raise ValueError("display_actions.json: " + "; ".join(errors))
    return actions


def weather_by_code(actions):
    out = {}
    for spec in (actions.get("weather") or {}).values():
        for code in spec["codes"]:
            out[code] = spec
    return out


def note_text(actions, key):
    return "：".join(actions["notes"][key]["fragments"])
```

- [ ] **Step 5: Point `snapshot.py` at the new structure**

In `services/ingest/app/snapshot.py`:
- Delete the lines `from pathlib import Path`, `import json`, `ROOT = Path(__file__).resolve().parents[3]` and `ACTIONS = json.loads(...)`.
- Add, with the other `app.` imports:

  ```python
  from app.actions import load_actions, validate_actions, weather_by_code
  ```

- Below the imports, add:

  ```python
  ACTIONS = validate_actions(load_actions())
  WEATHER = weather_by_code(ACTIONS)
  ```

- Replace the whole `build_display` function with:

  ```python
  def build_display(hsww: dict, rest: dict, signals: list) -> dict:
      for s in signals or []:
          spec = WEATHER.get(s.get("code") or "")
          if not spec:
              continue
          return {
              "action": spec["main"],
              "actionSub": (spec.get("sub") or [s.get("labelZh") or ""])[0],
          }
      if rest.get("suspend"):
          return {
              "action": "暫停工作",
              "actionSub": hsww.get("titleZh") or "工作暑熱警告",
          }
      if hsww.get("inForce"):
          return {
              "action": f"休息 {rest.get('rest', 0)} 分鐘",
              "actionSub": f"工作 {rest.get('work', 0)} 分鐘",
          }
      per = rest.get("perHours") or 2
      return {
          "action": "正常工作",
          "actionSub": f"每 {per} 小時休息 {rest.get('rest', 10)} 分鐘",
          "heroRel": "status/work-ok.png",
      }
  ```

- In `build_snapshot`, replace these two lines:

  ```python
      weather_act = ACTIONS.get("weather") or {}
      win = next((s.get("code") for s in signals if weather_act.get(s.get("code") or "")), None)
  ```

  with:

  ```python
      win = next((s.get("code") for s in signals if WEATHER.get(s.get("code") or "")), None)
  ```

- [ ] **Step 6: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `74 passed`

- [ ] **Step 7: Commit**

```bash
git add config/display_actions.json services/ingest/app/actions.py services/ingest/app/snapshot.py tests/test_display_actions.py tests/test_sim_cases.py
git commit -m "fix: official LD/HKO wording for every screen instruction, with verbatim guard

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 6: Sharper official icons and the full HKO weather-icon set

- Signal and rainstorm icons switch from 58 px GIFs to the 100×100 PNGs HKO's own homepage uses.
- Every HKO weather-icon code (29 of them) is downloaded, with its official Chinese name. This also fixes three wrong Gallery labels: pic50 is 陽光充沛, pic62 is 微雨, pic90 is 熱.

**Files:**
- Create: `scripts/fetch_official_icons.py`, `config/wx_icons.json`
- Create (by running the script): `apps/kiosk/public/official/warning/*.png` (11), `apps/kiosk/public/official/wxicon/pic*.png` (29)
- Modify: `config/official_icons.json`, `services/ingest/app/sim_cases.py` (`WX_ICONS`), `apps/kiosk/public/official/README.md`
- Delete: the 11 replaced GIFs in `apps/kiosk/public/official/weather/`
- Test: `tests/test_official_icons.py` (new), `tests/test_sim_cases.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_official_icons.py`:

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps" / "kiosk" / "public"
HKO_WX_CODES = [50, 51, 52, 53, 54, 60, 61, 62, 63, 64, 65, 70, 71, 72, 73, 74, 75, 76, 77,
                80, 81, 82, 83, 84, 85, 90, 91, 92, 93]


def load(name):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def test_every_warning_icon_file_exists():
    for code, rel in load("official_icons.json").items():
        assert (PUBLIC / rel).is_file(), code


def test_signals_and_rain_use_hko_100px_png():
    icons = load("official_icons.json")
    for code in ("TC1", "TC3", "TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10", "WRAINA", "WRAINR", "WRAINB"):
        assert icons[code].startswith("official/warning/") and icons[code].endswith(".png"), code


def test_every_hko_weather_icon_is_listed_and_present():
    wx = load("wx_icons.json")["icons"]
    assert sorted(int(c) for c in wx) == HKO_WX_CODES
    for code in wx:
        assert (PUBLIC / f"official/wxicon/pic{code}.png").is_file(), code
```

Append to `tests/test_sim_cases.py`, and add `list_official_icons` to its `from app.sim_cases import` line:

```python
def test_gallery_weather_icons_use_official_names():
    by = {i["code"]: i["labelZh"] for i in list_official_icons() if i["kind"] == "wx"}
    assert len(by) == 29
    assert by["pic50"] == "陽光充沛"
    assert by["pic62"] == "微雨"
    assert by["pic90"] == "熱"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_official_icons.py tests/test_sim_cases.py -q`
Expected: failures (`wx_icons.json` missing; icons still GIF; gallery labels 天晴 / 間有驟雨 / 炎熱)

- [ ] **Step 3: Create `config/wx_icons.json`**

Names are copied from HKO's icon page (`alt` text):

```json
{
  "source": "https://www.hko.gov.hk/textonly/v2/explain/wxicon_c.htm",
  "checked": "2026-10-06",
  "icons": {
    "50": "陽光充沛",
    "51": "間有陽光",
    "52": "短暫陽光",
    "53": "間有陽光幾陣驟雨",
    "54": "短暫陽光有驟雨",
    "60": "多雲",
    "61": "密雲",
    "62": "微雨",
    "63": "雨",
    "64": "大雨",
    "65": "雷暴",
    "70": "天色良好(只在農曆第一日晚間使用)",
    "71": "天色良好(只在農曆第二日至第六日晚間使用)",
    "72": "天色良好(只在農曆第七日至第十三日晚間使用)",
    "73": "天色良好(只在農曆第十四日至第十七日晚間使用)",
    "74": "天色良好(只在農曆第十八日至第二十四日晚間使用)",
    "75": "天色良好(只在農曆第二十五日至第三十日晚間使用)",
    "76": "大致多雲(只在晚間使用)",
    "77": "天色大致良好(只在晚間使用)",
    "80": "大風",
    "81": "乾燥",
    "82": "潮濕",
    "83": "霧",
    "84": "薄霧",
    "85": "煙霞",
    "90": "熱",
    "91": "暖",
    "92": "涼",
    "93": "冷"
  }
}
```

- [ ] **Step 4: Create `scripts/fetch_official_icons.py`**

```python
"""Download the official HKO icons the gate screen uses.

Run from the repo root:  python3 scripts/fetch_official_icons.py
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "apps" / "kiosk" / "public" / "official"
WARNING_BASE = "https://www.hko.gov.hk/images/HKOWarningSymbols/"
WX_BASE = "https://www.hko.gov.hk/images/HKOWxIconOutline/"

# local file name -> HKO file name (from HKO homepage script, images/HKOWarningSymbols/)
WARNING_FILES = {
    "tc1.png": "warn800_01_tc1.png",
    "tc3.png": "warn800_02_tc3.png",
    "tc8ne.png": "warn800_03_tc08ne.png",
    "tc8nw.png": "warn800_04_tc08nw.png",
    "tc8se.png": "warn800_05_tc08se.png",
    "tc8sw.png": "warn800_06_tc08sw.png",
    "tc9.png": "warn800_07_tc09.png",
    "tc10.png": "warn800_08_tc10.png",
    "raina.png": "warn800_09_rain amber.png",
    "rainr.png": "warn800_10_rain red.png",
    "rainb.png": "warn800_11_rain black.png",
}


def fetch(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": "hk-site-display icon fetch"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        data = resp.read()
    if not data.startswith(b"\x89PNG"):
        raise RuntimeError(f"{url} did not return a PNG")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"saved {dest.relative_to(ROOT)} ({len(data)} bytes)")


def main():
    for local, remote in WARNING_FILES.items():
        fetch(WARNING_BASE + urllib.parse.quote(remote), OFFICIAL / "warning" / local)
    codes = json.loads((ROOT / "config" / "wx_icons.json").read_text(encoding="utf-8"))["icons"]
    for code in codes:
        fetch(f"{WX_BASE}pic{code}.png", OFFICIAL / "wxicon" / f"pic{code}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Download the icons**

Run: `python3 scripts/fetch_official_icons.py`
Expected: 40 lines starting `saved apps/kiosk/public/official/…` (11 in `warning/`, 29 in `wxicon/`) and exit code 0. If any URL fails, stop and report it; do not substitute another image.

- [ ] **Step 6: Point the config at the new files and drop the replaced GIFs**

Replace `config/official_icons.json`:

```json
{
  "TC1": "official/warning/tc1.png",
  "TC3": "official/warning/tc3.png",
  "TC8NE": "official/warning/tc8ne.png",
  "TC8SE": "official/warning/tc8se.png",
  "TC8NW": "official/warning/tc8nw.png",
  "TC8SW": "official/warning/tc8sw.png",
  "TC9": "official/warning/tc9.png",
  "TC10": "official/warning/tc10.png",
  "WRAINA": "official/warning/raina.png",
  "WRAINR": "official/warning/rainr.png",
  "WRAINB": "official/warning/rainb.png",
  "WTS": "official/weather/ts.issuing.gif",
  "WL": "official/weather/landslip.issuing.gif",
  "WHOT": "official/weather/vhot.issuing.gif",
  "WMSGNL": "official/weather/msn.issuing.gif",
  "WCOLD": "official/weather/cold.issuing.gif",
  "WFIREY": "official/weather/firey.issuing.gif",
  "WFIRER": "official/weather/firer.issuing.gif",
  "WFROST": "official/weather/frost.issuing.gif",
  "WFNTSA": "official/weather/ntfl.issuing.gif",
  "WTMW": "official/weather/tsunami-warn.issuing.gif"
}
```

Then delete the replaced GIFs:

```bash
cd apps/kiosk/public/official/weather && git rm -q tc1.issuing.gif tc3.issuing.gif tc8ne.issuing.gif tc8nw.issuing.gif tc8se.issuing.gif tc8sw.issuing.gif tc9.issuing.gif tc10.issuing.gif raina.issuing.gif rainr.issuing.gif rainb.issuing.gif && cd -
```

- [ ] **Step 7: Gallery uses the official weather-icon names**

In `services/ingest/app/sim_cases.py`, replace the whole `WX_ICONS = [...]` list with:

```python
WX_NAMES = json.loads((ROOT / "config/wx_icons.json").read_text(encoding="utf-8"))["icons"]
WX_ICONS = [
    {"code": f"pic{code}", "labelZh": name, "rel": f"official/wxicon/pic{code}.png", "kind": "wx"}
    for code, name in WX_NAMES.items()
]
```

- [ ] **Step 8: Update `apps/kiosk/public/official/README.md`**

Replace the file with:

```markdown
Official warning icons and weather symbols.

Sources (Hong Kong Observatory / Labour Department originals, for this kiosk display only):

- HSWW colour tiles and LD logo: https://www.hko.gov.hk/images/index_icon/
- Tropical cyclone signals and rainstorm warnings, 100×100 PNG (`warning/`): https://www.hko.gov.hk/images/HKOWarningSymbols/ (the files HKO's own homepage uses)
- Other weather warnings, 58×58 GIF (`weather/`), the only size HKO publishes: https://www.hko.gov.hk/en/wxinfo/dailywx/images/
- Weather condition icons (`wxicon/`; codes and official names in `config/wx_icons.json`): https://www.hko.gov.hk/images/HKOWxIconOutline/

Refresh with `python3 scripts/fetch_official_icons.py`.
```

- [ ] **Step 9: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `78 passed`

- [ ] **Step 10: Commit**

```bash
git add scripts/fetch_official_icons.py config/wx_icons.json config/official_icons.json services/ingest/app/sim_cases.py apps/kiosk/public/official tests/test_official_icons.py tests/test_sim_cases.py
git commit -m "feat: HKO 100px signal and rain icons, full official weather icon set

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 7: Heat-stress tiles per trade and normal-day rest lines

**Files:**
- Create: `services/ingest/app/heat.py`
- Test: `tests/test_heat.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_heat.py`:

```python
import json
from pathlib import Path

from app.heat import build_rest_tiles, normal_rest_lines, trades_label
from app.site import configured_trades, tile_trades

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
DEMO = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))


def view(tiles):
    return [(t["kind"], t["rest"], t["tradesZh"]) for t in tiles]


def test_amber_demo_site_tiles():
    tiles = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "amber")
    assert view(tiles) == [
        ("rest", 45, "紮鐵 · 棚架"),
        ("rest", 30, "釘板 · 混凝土"),
        ("rest", 15, "水喉 · 焊接"),
        ("baseline", 10, "保安 · 檢查"),
    ]
    assert tiles[0]["work"] == 15 and tiles[0]["perHours"] == 1
    assert tiles[3]["work"] is None and tiles[3]["perHours"] == 2


def test_red_suspends_very_heavy_first():
    tiles = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "red")
    assert view(tiles)[0] == ("suspend", 60, "紮鐵 · 棚架")
    assert [t["rest"] for t in tiles] == [60, 45, 30, 15]


def test_black_merges_heavy_and_very_heavy_into_one_stop_tile():
    tiles = build_rest_tiles(SCHEDULE, configured_trades(DEMO), "black")
    assert view(tiles) == [
        ("suspend", 60, "紮鐵 · 棚架 · 釘板 +1"),
        ("rest", 45, "水喉 · 焊接"),
        ("rest", 30, "保安 · 檢查"),
    ]
    assert tiles[0]["trades"] == ["紮鐵", "棚架", "釘板", "混凝土"]


def test_tiles_without_trades_use_workload_labels():
    tiles = build_rest_tiles(SCHEDULE, tile_trades({"environment": "outdoor"}), "amber")
    assert view(tiles) == [
        ("rest", 45, "極重勞動"),
        ("rest", 30, "重勞動"),
        ("rest", 15, "中等勞動"),
        ("baseline", 10, "輕勞動"),
    ]


def test_baseline_tiles_order_fifteen_before_ten():
    trades = [
        {"labelZh": "A", "workload": "light", "environment": "aircon", "adjustMinutes": 0},
        {"labelZh": "B", "workload": "heavy", "environment": "aircon", "adjustMinutes": 0},
    ]
    assert view(build_rest_tiles(SCHEDULE, trades, "black")) == [("baseline", 15, "B"), ("baseline", 10, "A")]


def test_at_most_six_tiles():
    trades = [
        {"labelZh": f"{wl}-{env}-{adj}", "workload": wl, "environment": env, "adjustMinutes": adj}
        for wl in ("light", "moderate", "heavy", "very_heavy")
        for env in ("outdoor", "indoor", "aircon")
        for adj in (-30, -15, 0, 15, 30, 45, 60)
    ]
    for level in ("amber", "red", "black"):
        assert len(build_rest_tiles(SCHEDULE, trades, level)) <= 6


def test_trades_label_truncates_after_three():
    assert trades_label(["a", "b"]) == "a · b"
    assert trades_label(["a", "b", "c", "d", "e"]) == "a · b · c +2"


def test_normal_day_lines():
    assert normal_rest_lines(SCHEDULE, {"very_heavy"}) == ["每 2 小時休息 15 分鐘"]
    assert normal_rest_lines(SCHEDULE, {"light", "moderate"}) == ["每 2 小時休息 10 分鐘"]
    assert normal_rest_lines(SCHEDULE, {"light", "heavy"}) == [
        "重至極重勞動：每 2 小時休息 15 分鐘",
        "輕至中等勞動：每 2 小時休息 10 分鐘",
    ]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_heat.py -q`
Expected: collection error, `No module named 'app.heat'`

- [ ] **Step 3: Create `services/ingest/app/heat.py`**

```python
"""Heat Stress at Work Warning: rest tiles per trade, and the normal-day rest lines."""
from app.rest import compute_rest

TILE_ORDER = {"suspend": 0, "rest": 1, "baseline": 2}
MAX_NAMES = 3


def trades_label(names):
    shown = " · ".join(names[:MAX_NAMES])
    more = len(names) - MAX_NAMES
    return f"{shown} +{more}" if more > 0 else shown


def build_rest_tiles(schedule, trades, level):
    """Group trades with the same result; 暫停工作 first, then most rest, then the 2-hour baselines."""
    groups = {}
    for trade in trades:
        result = compute_rest(schedule, trade["environment"], level, trade["workload"], trade["adjustMinutes"])
        group = groups.setdefault((result["kind"], result["rest"]), {**result, "trades": []})
        group["trades"].append(trade["labelZh"])
    tiles = sorted(groups.values(), key=lambda t: (TILE_ORDER[t["kind"]], -t["rest"]))
    for tile in tiles:
        tile["tradesZh"] = trades_label(tile["trades"])
    return tiles


def normal_rest_lines(schedule, workloads):
    """Guidance para 4.7.1: light to moderate >=10 min, heavy to very heavy >=15 min, per 2 hours worked."""
    base = schedule["baseline"]
    hours = base["perHours"]
    heavy = bool(set(workloads) & {"heavy", "very_heavy"})
    light = bool(set(workloads) & {"light", "moderate"})
    if heavy and light:
        return [
            f"重至極重勞動：每 {hours} 小時休息 {base['very_heavy']} 分鐘",
            f"輕至中等勞動：每 {hours} 小時休息 {base['light']} 分鐘",
        ]
    rest = base["very_heavy"] if heavy else base["light"]
    return [f"每 {hours} 小時休息 {rest} 分鐘"]
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `86 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/heat.py tests/test_heat.py
git commit -m "feat: heat-stress rest tiles grouped by trade, normal-day rest lines

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 8: Heat-stress message kind and effective time

The Labour Department sends three message types (guidance Appendix 6): **生效** (issue), **仍然生效** (the hourly update) and **取消** (cancel). Each states the effective time, which can differ from when the message was sent: a message sent at 14:35 says the warning takes effect at 14:40.

**Files:**
- Modify: `services/ingest/app/hsww.py`
- Modify: `tests/fixtures/hsww_red_synth.json` (wording fix: the template says 甚高, not 很高)
- Test: `tests/test_hsww.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_hsww.py`, change the import to `from app.hsww import effective_time, message_kind, parse_hkhi_icon` and append:

```python
def test_message_kinds_follow_ld_templates():
    assert message_kind("黃色工作暑熱警告在今日下午2時40分生效，表示部分工作環境下的熱壓力頗高，請採取適當的防暑措施。") == "issue"
    assert message_kind("黃色工作暑熱警告在今日下午3時40分仍然生效，表示部分工作環境下的熱壓力頗高，請採取適當的防暑措施。") == "update"
    assert message_kind("工作暑熱警告在今日下午6時30分取消。") == "cancel"
    assert message_kind("請採取適當的防暑措施。") == "other"


def test_effective_time_from_message():
    assert effective_time("黃色工作暑熱警告在今日下午2時40分生效。", "202407141435").isoformat() == "2024-07-14T14:40:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日上午11時5分生效。", "202407141100").isoformat() == "2024-07-14T11:05:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日中午12時正生效。", "202407141155").isoformat() == "2024-07-14T12:00:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日下午12時15分生效。", "202407141210").isoformat() == "2024-07-14T12:15:00+08:00"


def test_effective_time_falls_back_to_message_time():
    assert effective_time("請採取適當的防暑措施。", "202608011400").isoformat() == "2026-08-01T14:00:00+08:00"
    assert effective_time("黃色工作暑熱警告在今日下午2時40分生效。", "") is None


def test_parse_adds_kind_and_effective_time():
    amber = parse_hkhi_icon(load("hsww_amber_inforce.json"))
    assert amber["messageKind"] == "issue"
    assert amber["effectiveAt"] == "2024-07-14T14:40:00+08:00"
    cancelled = parse_hkhi_icon(load("hsww_cancelled_stale.json"))
    assert cancelled["messageKind"] == "cancel"
    assert cancelled["effectiveAt"] == "2026-08-29T18:50:00+08:00"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_hsww.py -q`
Expected: collection error, `ImportError: cannot import name 'effective_time'`

- [ ] **Step 3: Implement**

Replace `services/ingest/app/hsww.py` with:

```python
import re
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
LEVEL = {30: "amber", 32: "red", 34: "black"}
ICON = {
    30: "official/hkhi_yellow.png",
    32: "official/hkhi_red.png",
    34: "official/hkhi_black.png",
}
# "下午2時40分", "中午12時正" (Labour Department message templates, guidance notes Appendix 6)
_EFFECTIVE = re.compile(r"([上中下])午\s*(\d{1,2})\s*時\s*(?:(\d{1,2})\s*分|正)?")


def message_kind(text):
    """生效 = issue, 仍然生效 = hourly update, 取消 = cancel (guidance notes Appendix 6)."""
    t = text or ""
    if "仍然生效" in t:
        return "update"
    if "取消" in t:
        return "cancel"
    if "生效" in t:
        return "issue"
    return "other"


def message_time(date_str):
    try:
        return datetime.strptime(str(date_str), "%Y%m%d%H%M").replace(tzinfo=HKT)
    except (TypeError, ValueError):
        return None


def effective_time(text, date_str):
    """Time stated in the message ("今日下午2時40分"), on the message's date; else the message time."""
    sent = message_time(date_str)
    match = _EFFECTIVE.search(text or "")
    if sent is None or match is None:
        return sent
    half, hour, minute = match.group(1), int(match.group(2)), int(match.group(3) or 0)
    if half == "上" and hour == 12:
        hour = 0
    elif half == "下" and hour < 12:
        hour += 12
    if hour > 23 or minute > 59:
        return sent
    return sent.replace(hour=hour, minute=minute)


def parse_hkhi_icon(raw: dict) -> dict:
    idx = int(raw.get("iconIndex", -1))
    level = LEVEL.get(idx, "none")
    in_force = idx in LEVEL
    effective = effective_time(raw.get("MessageTC2"), raw.get("date"))
    return {
        "level": level,
        "inForce": in_force,
        "cancelled": idx == -1,
        "iconIndex": idx,
        "titleZh": raw.get("TitleTC") or "",
        "noticeZh": raw.get("MessageTC2") or "",
        "noticeLeadZh": raw.get("MessageTC1") or "",
        "issuedAt": raw.get("date") or "",
        "messageKind": message_kind(raw.get("MessageTC2")),
        "effectiveAt": effective.isoformat() if effective else None,
        "iconRel": ICON.get(idx),
        "ldLogoRel": "official/ld_logo.png",
        "source": "hko-hkhi-icon",
    }
```

In `tests/fixtures/hsww_red_synth.json`, change `熱壓力很高` to `熱壓力甚高`. The official template words are 頗高 / 甚高 / 極高.

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `90 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/hsww.py tests/test_hsww.py tests/fixtures/hsww_red_synth.json
git commit -m "feat: classify LD heat-stress messages and read their effective time

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 9: HKO warning events, cancellations included

`parse_warnsum` keeps only warnings in force. The banner also needs cancellations, which the API reports as `actionCode = CANCEL` (HKO API documentation).

**Files:**
- Modify: `services/ingest/app/hko.py` (append)
- Test: `tests/test_hko.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_hko.py`, change the import to `from app.hko import active_codes, parse_warnsum, parse_warnsum_events, parse_warning_info` and append:

```python
def test_events_keep_cancellations_with_times():
    raw = {
        "WRAIN": {
            "name": "暴雨警告信號", "code": "WRAINB", "type": "黑色暴雨警告信號", "actionCode": "CANCEL",
            "issueTime": "2026-06-18T08:20:00+08:00", "updateTime": "2026-06-18T10:05:00+08:00",
        },
        "WTCSGNL": {
            "name": "熱帶氣旋警告信號", "code": "TC3", "type": "三號強風信號", "actionCode": "ISSUE",
            "issueTime": "2026-06-18T09:40:00+08:00", "updateTime": "2026-06-18T09:40:00+08:00",
        },
    }
    events = {e["code"]: e for e in parse_warnsum_events(raw)}
    assert events["WRAINB"]["actionCode"] == "CANCEL"
    assert events["WRAINB"]["updateTime"] == "2026-06-18T10:05:00+08:00"
    assert events["TC3"]["type"] == "三號強風信號"
    assert [w["code"] for w in parse_warnsum(raw)] == ["TC3"]


def test_events_ignore_bad_input():
    assert parse_warnsum_events({"x": "y"}) == []
    assert parse_warnsum_events(None) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_hko.py -q`
Expected: collection error, `ImportError: cannot import name 'parse_warnsum_events'`

- [ ] **Step 3: Implement**

Append to `services/ingest/app/hko.py`:

```python


def parse_warnsum_events(raw: dict) -> list[dict]:
    """Every warnsum entry with its action and times, cancellations included (for the change banner)."""
    out = []
    if not isinstance(raw, dict):
        return out
    for key, item in raw.items():
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "key": key,
                "code": item.get("code") or key,
                "name": (item.get("name") or "").strip(),
                "type": (item.get("type") or "").strip(),
                "actionCode": item.get("actionCode") or "",
                "issueTime": item.get("issueTime"),
                "updateTime": item.get("updateTime"),
            }
        )
    return out
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `92 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/hko.py tests/test_hko.py
git commit -m "feat: parse HKO warning events including cancellations

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 10: Current weather and tomorrow's forecast

**Files:**
- Create: `services/ingest/app/weather.py`
- Create: `tests/fixtures/rhrread_sample.json`, `tests/fixtures/fnd_sample.json` (shapes captured from the live API on 2026-10-06)
- Test: `tests/test_weather.py` (new)

- [ ] **Step 1: Create the fixtures**

`tests/fixtures/rhrread_sample.json`:

```json
{
  "icon": [51],
  "iconUpdateTime": "2026-10-06T06:00:00+08:00",
  "updateTime": "2026-10-06T17:02:00+08:00",
  "uvindex": {"data": [{"place": "京士柏", "value": 0.7, "desc": "低"}], "recordDesc": "過去一小時"},
  "humidity": {"recordTime": "2026-10-06T17:00:00+08:00", "data": [{"unit": "percent", "value": 62, "place": "香港天文台"}]},
  "temperature": {
    "recordTime": "2026-10-06T17:00:00+08:00",
    "data": [
      {"place": "京士柏", "value": 26, "unit": "C"},
      {"place": "香港天文台", "value": 27, "unit": "C"},
      {"place": "觀塘", "value": 28, "unit": "C"}
    ]
  },
  "tcmessage": "",
  "warningMessage": ""
}
```

`tests/fixtures/fnd_sample.json`:

```json
{
  "updateTime": "2026-10-06T16:30:00+08:00",
  "weatherForecast": [
    {"forecastDate": "20261007", "week": "星期三", "ForecastIcon": 81,
     "forecastMaxtemp": {"value": 30, "unit": "C"}, "forecastMintemp": {"value": 23, "unit": "C"}},
    {"forecastDate": "20261008", "week": "星期四", "ForecastIcon": 51,
     "forecastMaxtemp": {"value": 30, "unit": "C"}, "forecastMintemp": {"value": 25, "unit": "C"}}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_weather.py`:

```python
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.weather import parse_current, parse_forecast

HKT = timezone(timedelta(hours=8))
FIX = Path(__file__).resolve().parent / "fixtures"
NOW = datetime(2026, 10, 6, 17, 30, tzinfo=HKT)


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_current_uses_site_station():
    assert parse_current(load("rhrread_sample.json"), "觀塘", NOW) == {
        "iconRel": "official/wxicon/pic51.png",
        "tempC": 28,
        "placeZh": "觀塘",
        "humidity": 62,
        "uvValue": 0.7,
        "uvDescZh": "低",
        "updatedAt": "2026-10-06T17:02:00+08:00",
    }


def test_current_falls_back_to_observatory():
    weather = parse_current(load("rhrread_sample.json"), "沙田", NOW)
    assert weather["placeZh"] == "香港天文台" and weather["tempC"] == 27


def test_current_hidden_when_old_or_incomplete():
    assert parse_current(load("rhrread_sample.json"), "觀塘", NOW + timedelta(minutes=100)) is None
    assert parse_current({}, "觀塘", NOW) is None
    assert parse_current({"icon": [60]}, "觀塘", NOW) is None


def test_current_empty_uv_and_unknown_icon():
    raw = load("rhrread_sample.json")
    raw["uvindex"] = ""
    raw["icon"] = [99]
    weather = parse_current(raw, "觀塘", NOW)
    assert weather["uvValue"] is None and weather["uvDescZh"] is None and weather["iconRel"] is None


def test_forecast_picks_first_future_day():
    assert parse_forecast(load("fnd_sample.json"), NOW) == {
        "date": "20261007", "iconRel": "official/wxicon/pic81.png", "minC": 23, "maxC": 30
    }


def test_forecast_skips_today_and_expires():
    after_midnight = datetime(2026, 10, 7, 1, 0, tzinfo=HKT)
    assert parse_forecast(load("fnd_sample.json"), after_midnight)["date"] == "20261008"
    assert parse_forecast(load("fnd_sample.json"), NOW + timedelta(hours=13)) is None
```

- [ ] **Step 3: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_weather.py -q`
Expected: collection error, `No module named 'app.weather'`

- [ ] **Step 4: Create `services/ingest/app/weather.py`**

```python
"""Current weather (HKO rhrread) and tomorrow's forecast (HKO fnd) for the bottom bar."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
WX_ICONS = json.loads((ROOT / "config" / "wx_icons.json").read_text(encoding="utf-8"))["icons"]
WEATHER_MAX_AGE = timedelta(minutes=90)
FORECAST_MAX_AGE = timedelta(hours=12)
OBSERVATORY = "香港天文台"


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def wx_icon_rel(code):
    key = "" if code is None else str(code)
    return f"official/wxicon/pic{key}.png" if key in WX_ICONS else None


def parse_current(rhrread, station, now):
    if not isinstance(rhrread, dict):
        return None
    updated = parse_time(rhrread.get("updateTime"))
    if updated is None or now - updated > WEATHER_MAX_AGE:
        return None
    temps = {
        t.get("place"): t.get("value")
        for t in (rhrread.get("temperature") or {}).get("data") or []
        if isinstance(t, dict)
    }
    place = station if temps.get(station) is not None else OBSERVATORY
    temp = temps.get(place)
    if temp is None:
        return None
    humidity = next(
        (
            h.get("value")
            for h in (rhrread.get("humidity") or {}).get("data") or []
            if isinstance(h, dict) and h.get("place") == OBSERVATORY
        ),
        None,
    )
    uv_value = uv_desc = None
    uv = rhrread.get("uvindex")
    if isinstance(uv, dict) and uv.get("data"):
        first = uv["data"][0] or {}
        uv_value, uv_desc = first.get("value"), first.get("desc")
    icons = rhrread.get("icon") or []
    return {
        "iconRel": wx_icon_rel(icons[0]) if icons else None,
        "tempC": temp,
        "placeZh": place,
        "humidity": humidity,
        "uvValue": uv_value,
        "uvDescZh": uv_desc,
        "updatedAt": rhrread.get("updateTime"),
    }


def parse_forecast(fnd, now):
    if not isinstance(fnd, dict):
        return None
    updated = parse_time(fnd.get("updateTime"))
    if updated is None or now - updated > FORECAST_MAX_AGE:
        return None
    today = now.astimezone(HKT).strftime("%Y%m%d")
    for day in fnd.get("weatherForecast") or []:
        date = str(day.get("forecastDate") or "")
        if date > today:
            return {
                "date": date,
                "iconRel": wx_icon_rel(day.get("ForecastIcon")),
                "minC": (day.get("forecastMintemp") or {}).get("value"),
                "maxC": (day.get("forecastMaxtemp") or {}).get("value"),
            }
    return None
```

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `98 passed`

- [ ] **Step 6: Commit**

```bash
git add services/ingest/app/weather.py tests/test_weather.py tests/fixtures/rhrread_sample.json tests/fixtures/fnd_sample.json
git commit -m "feat: district weather and tomorrow's forecast with freshness limits

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 11: Change banner (stateless, 10 minutes)

The banner is a pure function of the feeds and `now`, so it survives restarts and every screen agrees.
- **Shows** for heat-stress Issue and Cancel, HKO ISSUE and CANCEL, and Pre-8.
- **Never shows** for heat-stress hourly updates, or for REISSUE / EXTEND / UPDATE.
- **Several events:** the most severe wins, then the newest.
- **Stale data:** hidden.

**Files:**
- Create: `services/ingest/app/banner.py`
- Test: `tests/test_banner.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_banner.py`:

```python
from datetime import datetime, timedelta, timezone

from app.banner import build_banner
from app.snapshot import code_rank

HKT = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 15, 14, 45, tzinfo=HKT)


def iso(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


AMBER_ISSUE = {
    "level": "amber", "inForce": True, "titleZh": "黃色工作暑熱警告",
    "messageKind": "issue", "effectiveAt": iso(3),
}


def event(code, action, minutes_ago, type_="", name=""):
    at = iso(minutes_ago)
    return {"key": code, "code": code, "name": name, "type": type_, "actionCode": action, "issueTime": at, "updateTime": at}


def banner(hsww=None, events=(), info=(), stale=False):
    return build_banner(hsww or {}, list(events), list(info), NOW, code_rank, stale)


def test_hsww_issue_within_ten_minutes():
    assert banner(AMBER_ISSUE) == {"time": "14:42", "textZh": "黃色工作暑熱警告 生效", "kind": "issue", "code": "HSWW-amber"}


def test_hsww_hourly_update_never_shows():
    assert banner({**AMBER_ISSUE, "messageKind": "update"}) is None


def test_hsww_cancel():
    shown = banner({"level": "none", "inForce": False, "messageKind": "cancel", "effectiveAt": iso(5)})
    assert shown["textZh"] == "工作暑熱警告 取消" and shown["kind"] == "cancel"


def test_ten_minute_edges():
    assert banner({**AMBER_ISSUE, "effectiveAt": iso(9.98)}) is not None
    assert banner({**AMBER_ISSUE, "effectiveAt": iso(10.02)}) is None


def test_warnsum_issue_and_cancel():
    assert banner(events=[event("TC8NE", "ISSUE", 2, "八號東北烈風或暴風信號")])["textZh"] == "八號東北烈風或暴風信號 發出"
    assert banner(events=[event("WRAINB", "CANCEL", 4, "黑色暴雨警告信號")])["textZh"] == "黑色暴雨警告信號 取消"
    assert banner(events=[event("CANCEL", "ISSUE", 1, "", "熱帶氣旋警告信號")])["textZh"] == "熱帶氣旋警告信號 取消"


def test_extend_update_reissue_ignored():
    for action in ("EXTEND", "UPDATE", "REISSUE"):
        assert banner(events=[event("WTS", action, 1, "雷暴警告")]) is None


def test_pre8_banner():
    shown = banner(info=[{"code": "WTCPRE8", "updateTime": iso(2)}])
    assert shown["textZh"] == "預警八號熱帶氣旋警告信號之特別報告 發出"


def test_most_severe_wins():
    shown = banner(
        AMBER_ISSUE,
        events=[event("WRAINB", "ISSUE", 6, "黑色暴雨警告信號"), event("TC3", "ISSUE", 1, "三號強風信號")],
    )
    assert shown["code"] == "WRAINB"


def test_hidden_when_stale():
    assert banner(AMBER_ISSUE, stale=True) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_banner.py -q`
Expected: collection error, `No module named 'app.banner'`

- [ ] **Step 3: Create `services/ingest/app/banner.py`**

```python
"""Change banner: 10 minutes after a warning is issued or cancelled. Stateless by design."""
from datetime import timedelta

from app.hko import PRE8_NAME
from app.weather import HKT, parse_time

BANNER_AFTER = timedelta(minutes=10)
# LD messages can announce an effective time a few minutes after they are sent.
BANNER_AHEAD = timedelta(minutes=15)
HSWW_NAME = "工作暑熱警告"
TC_SIGNAL_NAME = "熱帶氣旋警告信號"


def _recent(at, now):
    return at is not None and -BANNER_AHEAD <= now - at <= BANNER_AFTER


def build_banner(hsww, events, info, now, rank, stale=False):
    """Most severe recent issue/cancel event. `rank(code)` gives severity, lower is more severe."""
    if stale:
        return None
    candidates = []
    at = parse_time(hsww.get("effectiveAt"))
    if _recent(at, now):
        kind = hsww.get("messageKind")
        if kind == "issue" and hsww.get("inForce"):
            code = f"HSWW-{hsww.get('level')}"
            candidates.append((rank(code), at, "issue", code, f"{hsww.get('titleZh') or HSWW_NAME} 生效"))
        elif kind == "cancel":
            candidates.append((rank("HSWW"), at, "cancel", "HSWW", f"{HSWW_NAME} 取消"))
    for event in events:
        code, action = event["code"], event["actionCode"]
        label = event["type"] or event["name"]
        if code == "CANCEL" or action == "CANCEL":
            at = parse_time(event.get("updateTime") or event.get("issueTime"))
            name = (event["name"] or TC_SIGNAL_NAME) if code == "CANCEL" else label
            if _recent(at, now) and name:
                candidates.append((rank(code), at, "cancel", code, f"{name} 取消"))
        elif action == "ISSUE":
            at = parse_time(event.get("issueTime"))
            if _recent(at, now) and label:
                candidates.append((rank(code), at, "issue", code, f"{label} 發出"))
    for item in info:
        if item.get("code") == "WTCPRE8":
            at = parse_time(item.get("updateTime"))
            if _recent(at, now):
                candidates.append((rank("WTCPRE8"), at, "issue", "WTCPRE8", f"{PRE8_NAME} 發出"))
    if not candidates:
        return None
    best = min(candidates, key=lambda c: (c[0], -c[1].timestamp()))
    return {"time": best[1].astimezone(HKT).strftime("%H:%M"), "textZh": best[4], "kind": best[2], "code": best[3]}
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `107 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/banner.py tests/test_banner.py
git commit -m "feat: stateless 10-minute change banner for issues and cancellations

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 12: Screen state rules: weather precedence, tones, supervisor lines

- **Weather order** (spec §4.2): stay-sheltered instructions outrank leave instructions, so **Black rain outranks Signal 8**. HKO's Signal 8 advice applies only 如情況許可 ("if conditions permit").
- **Supervisor lines** use the ranks in `display_actions.json`, at most two.

**Files:**
- Create: `services/ingest/app/state.py`
- Test: `tests/test_state.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_state.py`:

```python
from app.actions import load_actions, weather_by_code
from app.state import WEATHER_ORDER, state_tone, supervisor_lines, tc_signal_code, winning_weather_code

ACTIONS = load_actions()


def test_black_rain_outranks_signal_8():
    assert winning_weather_code(["TC8NE", "WRAINB", "WL"]) == "WRAINB"


def test_weather_order():
    assert winning_weather_code(["TC8NE", "TC9"]) == "TC9"
    assert winning_weather_code(["TC10", "WRAINB"]) == "TC10"
    assert winning_weather_code(["WTCPRE8", "TC3", "WRAINR"]) == "WTCPRE8"
    assert winning_weather_code(["TC3", "WTS", "WRAINA"]) is None


def test_every_weather_code_has_an_official_instruction():
    assert set(weather_by_code(ACTIONS)) == set(WEATHER_ORDER)


def test_tones():
    assert state_tone("weather", "WRAINB", "amber") == "p0-rain"
    assert state_tone("weather", "TC8NE", "none") == "p0-tc"
    assert state_tone("weather", "WL", "none") == "p0-landslip"
    assert state_tone("weather", "WTCPRE8", "none") == "p1"
    assert state_tone("weather", "WTMW", "none") == "watch"
    assert state_tone("heat", None, "red") == "red"
    assert state_tone("normal", None, "none") == "idle"


def test_supervisor_lines_ranked_and_capped():
    labels = {"TC3": "三號強風信號", "WTS": "雷暴警告", "WMSGNL": "強烈季候風信號", "WRAINA": "黃色暴雨警告信號"}
    assert supervisor_lines(ACTIONS, ["TC3", "WRAINA", "WTS", "WMSGNL"], labels) == [
        {"text": "有僱員可能遭受雷電擊中時：立即停止工作，並到安全地方暫避", "fromZh": "雷暴警告"},
        {"text": "停止操作起重機、吊船、進行斜坡工程", "fromZh": "強烈季候風信號"},
    ]


def test_supervisor_line_for_signal_3():
    assert supervisor_lines(ACTIONS, ["TC3"], {"TC3": "三號強風信號"}) == [
        {"text": "停止操作起重機、吊船", "fromZh": "三號強風信號"}
    ]


def test_tc_signal_code():
    assert tc_signal_code(["WTCPRE8", "TC3"]) == "TC3"
    assert tc_signal_code(["WRAINR"]) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_state.py -q`
Expected: collection error, `No module named 'app.state'`

- [ ] **Step 3: Create `services/ingest/app/state.py`**

```python
"""Which state the screen is in, its tone, and the supervisor lines."""

# Spec §4.2: instructions to stay sheltered outrank instructions to leave.
WEATHER_ORDER = ["TC10", "TC9", "WRAINB", "TC8NE", "TC8SE", "TC8NW", "TC8SW", "WL", "WTMW", "WTCPRE8", "WRAINR"]
TC_SIGNALS = ("TC1", "TC3", "TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10")
MAX_SUPERVISOR = 2


def winning_weather_code(codes):
    present = set(codes or [])
    return next((code for code in WEATHER_ORDER if code in present), None)


def state_tone(mode, code, level):
    if mode == "weather":
        if code in ("TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10"):
            return "p0-tc"
        if code == "WRAINB":
            return "p0-rain"
        if code == "WL":
            return "p0-landslip"
        if code == "WTMW":
            return "watch"
        return "p1"
    if mode == "heat":
        return level
    return "idle"


def supervisor_lines(actions, codes, labels):
    """Official supervisor instructions for warnings in force, most severe first, at most two."""
    present = set(codes or [])
    hits = []
    for spec in (actions.get("supervisor") or {}).values():
        code = next((c for c in spec["codes"] if c in present), None)
        if code:
            hits.append((spec["rank"], "：".join(spec["fragments"]), labels.get(code) or code))
    hits.sort(key=lambda hit: hit[0])
    return [{"text": text, "fromZh": label} for _, text, label in hits[:MAX_SUPERVISOR]]


def tc_signal_code(codes):
    return next((code for code in codes or [] if code in TC_SIGNALS), None)
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `114 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/state.py tests/test_state.py
git commit -m "feat: weather precedence (black rain over signal 8), tones, supervisor lines

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 13: Snapshot carries the new design (legacy fields kept)

- **New fields:** `display.mode/main/sub/meta/heroRel`, `restTiles`, `notes`, `supervisor`, `banner`, `weather`, `forecast`.
- **Legacy fields:** `display.action/actionSub`, `rest`, `hko.*` and `priority` stay, so the kiosk that is already deployed keeps working until the new frontend ships.
- **Pre-8:** loses its Icons8 picture; its hero becomes the official icon of the signal in force.

**Files:**
- Modify: `services/ingest/app/snapshot.py` (whole file)
- Delete: `apps/kiosk/public/status/pre8.png`
- Modify: `apps/kiosk/public/status/README.md`
- Test: `tests/test_snapshot.py`, `tests/test_sim_cases.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_snapshot.py`:

```python
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
SITE = json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8"))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
T8_NE = {"WTCSGNL": {"name": "熱帶氣旋警告信號", "code": "TC8NE", "type": "八號東北烈風或暴風信號",
                     "actionCode": "ISSUE", "issueTime": "2026-09-14T15:30:00+08:00"}}
T3 = {"WTCSGNL": {"name": "熱帶氣旋警告信號", "code": "TC3", "type": "三號強風信號", "actionCode": "ISSUE"}}


def build(**overrides):
    args = {
        "hsww_raw": load("hsww_cancelled_stale.json"), "warnsum": {}, "warning_info": {}, "rhrread": {},
        "site": SITE, "schedule": SCHEDULE, "icons_map": ICONS,
    }
    args.update(overrides)
    return build_snapshot(**args)


def test_heat_state_has_tiles_note_and_meta():
    snap = build(hsww_raw=load("hsww_amber_inforce.json"))
    assert snap["display"]["mode"] == "heat"
    assert snap["display"]["meta"] == "黃色工作暑熱警告 · 14:40 生效"
    assert snap["display"]["heroRel"] == "official/hkhi_yellow.png"
    assert [t["rest"] for t in snap["restTiles"]] == [45, 30, 15, 10]
    assert snap["notes"] == ["僱員未適應或需重新適應在酷熱環境中工作：每小時的休息時間應增加15分鐘"]
    assert snap["tone"] == "amber"
    assert snap["display"]["action"] == "休息 45 分鐘"


def test_normal_state_lines_and_t3_supervisor_line():
    snap = build(warnsum=T3)
    assert snap["display"]["mode"] == "normal"
    assert snap["display"]["sub"] == ["重至極重勞動：每 2 小時休息 15 分鐘", "輕至中等勞動：每 2 小時休息 10 分鐘"]
    assert snap["supervisor"] == [{"text": "停止操作起重機、吊船", "fromZh": "三號強風信號"}]
    assert snap["tone"] == "idle"


def test_weather_state_official_words_and_meta():
    snap = build(warnsum=T8_NE, hsww_raw=load("hsww_amber_inforce.json"))
    d = snap["display"]
    assert (d["mode"], d["main"], d["sub"]) == ("weather", "分批離開工作地點", ["如情況許可，市民應盡早回家"])
    assert d["meta"] == "八號東北烈風或暴風信號 · 15:30 發出"
    assert d["heroRel"] == "official/warning/tc8ne.png"
    assert snap["restTiles"] == [] and snap["supervisor"] == []
    assert snap["tone"] == "p0-tc"


def test_pre8_hero_is_the_signal_in_force():
    snap = build(warnsum=load("warnsum_tc1.json"), warning_info=load("warningInfo_pre8.json"))
    assert snap["display"]["main"] == "分批離開工作地點"
    assert snap["display"]["heroRel"] == "official/warning/tc1.png"
    assert snap["display"]["meta"] == "預警八號熱帶氣旋警告信號之特別報告"
    assert all(s["rel"] != "status/pre8.png" for s in snap["signals"])


def test_weather_and_forecast_fields():
    now = datetime(2026, 10, 6, 17, 30, tzinfo=HKT)
    snap = build(rhrread=load("rhrread_sample.json"), fnd=load("fnd_sample.json"), now=now)
    assert snap["weather"]["placeZh"] == "觀塘" and snap["weather"]["tempC"] == 28
    assert snap["forecast"]["date"] == "20261007"
    assert snap["banner"] is None


def test_banner_shows_then_hides_when_stale():
    now = datetime(2024, 7, 14, 14, 45, tzinfo=HKT)
    assert build(hsww_raw=load("hsww_amber_inforce.json"), now=now)["banner"]["textZh"] == "黃色工作暑熱警告 生效"
    assert build(hsww_raw=load("hsww_amber_inforce.json"), now=now, stale=True)["banner"] is None
```

In `tests/test_sim_cases.py`, change the `typhoon-stack` part of `test_winning_weather_action_sets_tone_not_leftover_hsww` to:

```python
    stack = build_case("typhoon-stack")
    assert stack["display"]["action"] == "停止戶外作業"
    assert stack["tone"] == "p0-rain"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py tests/test_sim_cases.py -q`
Expected: failures (`build_snapshot() got an unexpected keyword argument 'fnd'`, `KeyError: 'mode'`, typhoon-stack still says 分批離開工作地點)

- [ ] **Step 3: Replace `services/ingest/app/snapshot.py`**

```python
from datetime import datetime, timedelta, timezone

from app.actions import load_actions, note_text, validate_actions, weather_by_code
from app.banner import build_banner
from app.heat import build_rest_tiles, normal_rest_lines
from app.hko import PRE8_NAME, active_codes, parse_warning_info, parse_warnsum, parse_warnsum_events
from app.hsww import parse_hkhi_icon
from app.priority import classify
from app.rest import compute_rest
from app.site import WORKLOAD_ZH, normal_workloads, tile_trades, weather_station
from app.state import state_tone, supervisor_lines, tc_signal_code, winning_weather_code
from app.weather import parse_current, parse_forecast, parse_time, wx_icon_rel

HKT = timezone(timedelta(hours=8))
ACTIONS = validate_actions(load_actions())
WEATHER = weather_by_code(ACTIONS)

P0 = {"TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC8", "TC9", "TC10", "WRAINB", "WL"}
P1 = {"TC3", "WRAINR", "WTS", "WTCPRE8"}

PRE8_CAPTION = PRE8_NAME
IDLE_HERO = "status/work-ok.png"
HSWW_LABEL = {
    "amber": "黃色工作暑熱警告",
    "red": "紅色工作暑熱警告",
    "black": "黑色工作暑熱警告",
}


def code_rank(code: str) -> int:
    c = code or ""
    if c == "TC10":
        return 0
    if c == "TC9":
        return 1
    if c.startswith("TC8"):
        return 2
    if c == "WRAINB":
        return 3
    if c == "WL":
        return 4
    if c in P1 or c == "WTCPRE8":
        return 10
    if c.startswith("HSWW"):
        return 20
    return 30


def is_high_impact(code: str, kind: str = "") -> bool:
    c = code or ""
    if kind == "hsww" or c.startswith("HSWW"):
        return True
    return c in P0 or c in {"WRAINR", "WTCPRE8", "WTMW"}


def weather_caption(warnings: list, info: list) -> str:
    """Canteen line: warnsum type/name, never bulletin contents[0]."""
    if warnings:
        w = sorted(warnings, key=lambda item: code_rank(item.get("code") or ""))[0]
        return (w.get("type") or w.get("name") or "").strip()
    for item in info or []:
        if item.get("code") == "WTCPRE8" or item.get("subtype") == "WTCPRE8":
            return PRE8_CAPTION
    return ""


def build_signals(hsww: dict, warnings: list, codes: list, icons_map: dict) -> list:
    out = []
    if hsww.get("inForce") and hsww.get("iconRel"):
        level = hsww.get("level") or "amber"
        out.append(
            {
                "code": f"HSWW-{level}",
                "rel": hsww["iconRel"],
                "labelZh": hsww.get("titleZh") or HSWW_LABEL.get(level, "工作暑熱警告"),
                "kind": "hsww",
                "impact": "high",
            }
        )
    seen = set()
    for w in warnings:
        code = w.get("code") or ""
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(
            {
                "code": code,
                "rel": icons_map.get(code),
                "labelZh": (w.get("type") or w.get("name") or "").strip(),
                "kind": "weather",
                "impact": "high" if is_high_impact(code, "weather") else "low",
            }
        )
    if "WTCPRE8" in (codes or []) and "WTCPRE8" not in seen:
        # HKO publishes no Pre-8 icon; the screen shows the signal in force instead.
        out.append({"code": "WTCPRE8", "rel": None, "labelZh": PRE8_CAPTION, "kind": "weather", "impact": "high"})
    out.sort(key=lambda s: code_rank(s["code"]))
    return out


def _clock(value):
    at = parse_time(value)
    return at.astimezone(HKT).strftime("%H:%M") if at else None


def _weather_display(code, warnings, info, icons_map, codes):
    spec = WEATHER[code]
    if code == "WTCPRE8":
        name = PRE8_NAME
        at = next((i.get("updateTime") for i in info if i.get("code") == "WTCPRE8"), None)
        signal = tc_signal_code(codes)
        hero = icons_map.get(signal) if signal else None
    else:
        warning = next((w for w in warnings if w["code"] == code), {})
        name = (warning.get("type") or warning.get("name") or "").strip()
        at = warning.get("issueTime")
        hero = icons_map.get(code)
    clock = _clock(at)
    meta = f"{name} · {clock} 發出" if name and clock else (name or None)
    return {"mode": "weather", "main": spec["main"], "sub": list(spec.get("sub") or []), "meta": meta, "heroRel": hero}


def _heat_display(hsww):
    title = hsww.get("titleZh") or HSWW_LABEL.get(hsww.get("level"), "工作暑熱警告")
    clock = _clock(hsww.get("effectiveAt"))
    meta = f"{title} · {clock} 生效" if clock else title
    return {"mode": "heat", "main": None, "sub": [], "meta": meta, "heroRel": hsww.get("iconRel")}


def _legacy_fields(display, rest, hsww):
    """`action` / `actionSub` for the kiosk deployed before this change."""
    mode = display["mode"]
    if mode == "weather":
        return {"action": display["main"], "actionSub": (display["sub"] or [display["meta"] or ""])[0]}
    if mode == "heat":
        if rest["kind"] == "suspend":
            return {"action": "暫停工作", "actionSub": hsww.get("titleZh") or "工作暑熱警告"}
        if rest["kind"] == "baseline":
            return {"action": f"休息 {rest['rest']} 分鐘", "actionSub": f"每 {rest['perHours']} 小時"}
        return {"action": f"休息 {rest['rest']} 分鐘", "actionSub": f"工作 {rest['work']} 分鐘"}
    return {"action": "正常工作", "actionSub": display["sub"][0] if display["sub"] else ""}


def _legacy_rest(rest):
    if rest["kind"] == "suspend":
        return {"work": 0, "rest": 60, "suspend": True}
    if rest["kind"] == "baseline":
        return {"work": 120, "rest": rest["rest"], "suspend": False, "perHours": rest["perHours"]}
    return {"work": rest["work"], "rest": rest["rest"], "suspend": False}


def build_snapshot(
    hsww_raw,
    warnsum,
    warning_info,
    rhrread,
    site,
    schedule,
    icons_map,
    generated_at=None,
    fnd=None,
    now=None,
    stale=False,
):
    now = now or datetime.now(HKT)
    hsww = parse_hkhi_icon(hsww_raw or {})
    warnings = parse_warnsum(warnsum or {})
    events = parse_warnsum_events(warnsum or {})
    info = parse_warning_info(warning_info or {})
    codes = active_codes(warnsum or {})
    for item in info:
        if item["code"] == "WTCPRE8" and "WTCPRE8" not in codes:
            codes.append("WTCPRE8")
    pri = classify(codes, hsww["level"])
    workload = site.get("defaultWorkload", "very_heavy")
    rest = compute_rest(
        schedule, site.get("environment", "outdoor"), hsww["level"], workload, site.get("restAdjustMinutes", 0)
    )
    icons = [{"code": w["code"], "rel": icons_map[w["code"]]} for w in warnings if icons_map.get(w["code"])]
    wx_icon = wx_icon_rel(rhrread["icon"][0]) if isinstance(rhrread, dict) and rhrread.get("icon") else None
    generated = generated_at or datetime.now(HKT).isoformat(timespec="seconds")
    clock = _clock(generated) or datetime.now(HKT).strftime("%H:%M")
    trades = site.get("primaryTrades") or []
    trade = trades[0] if trades else {}
    signals = build_signals(hsww, warnings, codes, icons_map)
    labels = {s["code"]: s["labelZh"] for s in signals}

    weather_code = winning_weather_code(codes)
    rest_tiles, notes, supervisor = [], [], []
    if weather_code:
        display = _weather_display(weather_code, warnings, info, icons_map, codes)
    elif hsww.get("inForce"):
        display = _heat_display(hsww)
        rest_tiles = build_rest_tiles(schedule, tile_trades(site), hsww["level"])
        notes = [note_text(ACTIONS, "heatUnacclimatised")]
    else:
        display = {
            "mode": "normal",
            "main": "正常工作",
            "sub": normal_rest_lines(schedule, normal_workloads(site)),
            "meta": None,
            "heroRel": IDLE_HERO,
        }
    if display["mode"] != "weather":
        supervisor = supervisor_lines(ACTIONS, codes, labels)
    display.update(_legacy_fields(display, rest, hsww))

    return {
        "generatedAt": generated,
        "clock": clock,
        "staleAfterSec": 600,
        "stale": bool(stale),
        "tone": state_tone(display["mode"], weather_code, hsww["level"]),
        "site": {
            "id": site.get("siteId"),
            "nameZh": site.get("nameZh"),
            "tradeZh": trade.get("labelZh") or "",
            "workloadZh": WORKLOAD_ZH.get(workload, workload),
        },
        "hsww": hsww,
        "hko": {
            "warnsum": warnings,
            "warningInfo": info,
            "icons": icons,
            "wxIconRel": wx_icon,
            "headlineZh": weather_caption(warnings, info),
        },
        "signals": signals,
        "display": display,
        "priority": pri,
        "rest": _legacy_rest(rest),
        "restTiles": rest_tiles,
        "notes": notes,
        "supervisor": supervisor,
        "banner": build_banner(hsww, events, info, now, code_rank, stale),
        "weather": parse_current(rhrread, weather_station(site), now),
        "forecast": parse_forecast(fnd, now),
    }
```

- [ ] **Step 4: Remove the non-official Pre-8 picture**

```bash
git rm -q apps/kiosk/public/status/pre8.png
```

Replace `apps/kiosk/public/status/README.md` with:

```markdown
Status marks (not official HKO / Labour Department warnings).

- `work-ok.png` — idle / 正常工作. Icons8 ios-filled worker-male. https://icons8.com

Pre-8 has no official HKO icon, so the screen shows the official icon of the tropical cyclone signal in force (T1 or T3) instead of a substitute picture.

Icons by Icons8.
```

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `120 passed`

- [ ] **Step 6: Commit**

```bash
git add services/ingest/app/snapshot.py apps/kiosk/public/status tests/test_snapshot.py tests/test_sim_cases.py
git commit -m "feat: snapshot with screen modes, rest tiles, supervisor lines, banner and weather

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 14: Per-feed cache, FastAPI lifespan, snapshot endpoint

**Files:**
- Create: `services/ingest/app/feeds.py`
- Modify: `services/ingest/app/main.py` (whole file)
- Test: `tests/test_feeds.py` (new), `tests/test_live_api.py` (rewrite)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_feeds.py`:

```python
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from app.feeds import Feed, FeedSet

HKT = timezone(timedelta(hours=8))


def test_failed_fetch_keeps_last_value():
    calls = {"n": 0}

    def flaky(_client):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("down")
        return {"v": 1}

    feeds = FeedSet([Feed("a", flaky, 0)], nullcontext)
    feeds.refresh_due()
    feeds.refresh_due(force=True)
    assert feeds.value("a") == {"v": 1}
    assert feeds.feeds["a"].ok is False


def test_one_feed_failing_does_not_block_others():
    def boom(_client):
        raise RuntimeError("x")

    feeds = FeedSet([Feed("bad", boom, 60), Feed("good", lambda _client: 2, 60)], nullcontext)
    feeds.refresh_due()
    assert feeds.value("good") == 2
    assert feeds.value("bad") is None


def test_interval_and_quicker_retry_after_failure():
    feed = Feed("a", lambda _client: 1, 600)
    assert feed.is_due(0.0)
    feed.last_attempt, feed.ok = 1000.0, True
    assert not feed.is_due(1300.0)
    assert feed.is_due(1600.0)
    feed.ok = False
    assert feed.is_due(1061.0)


def test_age_in_seconds():
    feeds = FeedSet([Feed("a", lambda _client: 1, 60)], nullcontext)
    now = datetime(2026, 10, 6, 12, 0, tzinfo=HKT)
    assert feeds.age("a", now) is None
    feeds.feeds["a"].fetched_at = now - timedelta(minutes=11)
    assert feeds.age("a", now) == 660
```

Replace `tests/test_live_api.py` with:

```python
import json
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.feeds import Feed, FeedSet

HKT = timezone(timedelta(hours=8))
FIX = Path(__file__).resolve().parent / "fixtures"
NAMES = ("hsww", "warnsum", "warningInfo", "rhrread", "fnd")
main.ENABLE_POLLER = False


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def fake_feeds(fail=()):
    values = {"hsww": load("hsww_cancelled_stale.json"), "warnsum": {}, "warningInfo": {}, "rhrread": {}, "fnd": {}}

    def fetcher(name):
        def fetch(_client):
            if name in fail:
                raise RuntimeError(f"{name} down")
            return values[name]

        return fetch

    return FeedSet([Feed(name, fetcher(name), 60) for name in NAMES], nullcontext)


def preload(feeds, age):
    at = datetime.now(HKT) - age
    feeds.feeds["hsww"].value, feeds.feeds["hsww"].fetched_at = load("hsww_cancelled_stale.json"), at
    feeds.feeds["warnsum"].value, feeds.feeds["warnsum"].fetched_at = {}, at


def client_with(feeds):
    main.FEEDS = feeds
    return TestClient(main.app)


def test_snapshot_stays_live_after_sim_post():
    client = client_with(fake_feeds())
    sim = client.post("/api/v1/sim", json={"fixture": "amber"})
    assert sim.status_code == 200
    assert sim.json()["display"]["mode"] == "heat"
    body = client.get("/api/v1/snapshot").json()
    assert body["display"]["mode"] == "normal"
    assert body["source"] == "live"
    assert body["stale"] is False


def test_snapshot_marks_stale_when_warning_feeds_old():
    feeds = fake_feeds(fail=("hsww", "warnsum"))
    preload(feeds, timedelta(minutes=11))
    body = client_with(feeds).get("/api/v1/snapshot").json()
    assert body["stale"] is True
    assert body["banner"] is None


def test_transient_failure_keeps_fresh_cache_not_stale():
    feeds = fake_feeds(fail=("hsww", "warnsum"))
    preload(feeds, timedelta(seconds=90))
    assert client_with(feeds).get("/api/v1/snapshot").json()["stale"] is False


def test_weather_feed_failure_does_not_block_snapshot():
    body = client_with(fake_feeds(fail=("rhrread", "fnd"))).get("/api/v1/snapshot").json()
    assert body["weather"] is None and body["forecast"] is None
    assert body["display"]["mode"] == "normal"


def test_no_data_at_all_is_503():
    response = client_with(fake_feeds(fail=NAMES)).get("/api/v1/snapshot")
    assert response.status_code == 503
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_feeds.py tests/test_live_api.py -q`
Expected: collection errors (`No module named 'app.feeds'`)

- [ ] **Step 3: Create `services/ingest/app/feeds.py`**

```python
"""Per-feed cache: each official feed refreshes on its own interval and keeps its last good value."""
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

HKT = timezone(timedelta(hours=8))
RETRY_SEC = 60


@dataclass
class Feed:
    name: str
    fetch: Callable[[Any], Any]
    interval: float
    value: Any = None
    fetched_at: datetime | None = None
    last_attempt: float | None = None
    ok: bool = False

    def is_due(self, mono):
        if self.last_attempt is None:
            return True
        wait = self.interval if self.ok else min(self.interval, RETRY_SEC)
        return mono - self.last_attempt >= wait

    def refresh(self, client, now):
        self.last_attempt = time.monotonic()
        try:
            value = self.fetch(client)
        except Exception:
            self.ok = False
            return False
        self.value, self.fetched_at, self.ok = value, now, True
        return True


class FeedSet:
    def __init__(self, feeds, client_factory):
        self.feeds = {feed.name: feed for feed in feeds}
        self.client_factory = client_factory
        self._lock = threading.Lock()

    def refresh_due(self, force=False):
        with self._lock:
            mono = time.monotonic()
            due = [feed for feed in self.feeds.values() if force or feed.is_due(mono)]
            if not due:
                return
            with self.client_factory() as client:
                for feed in due:
                    feed.refresh(client, datetime.now(HKT))

    def value(self, name):
        return self.feeds[name].value

    def age(self, name, now):
        at = self.feeds[name].fetched_at
        return None if at is None else (now - at).total_seconds()

    def never_fetched(self):
        return all(feed.last_attempt is None for feed in self.feeds.values())
```

- [ ] **Step 4: Replace `services/ingest/app/main.py`**

```python
import json
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.feeds import Feed, FeedSet
from app.sim_cases import ALIASES, CASE_IDS, build_case, list_cases, list_official_icons
from app.site import validate_site
from app.snapshot import build_snapshot

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
HSWW_URL = "https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml"
WARN_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
POLL_SEC = 15
STALE_AFTER = int(os.environ.get("STALE_AFTER_SEC", "600"))
ENABLE_SIM = os.environ.get("ENABLE_SIM", "true").lower() in ("1", "true", "yes")
ENABLE_POLLER = os.environ.get("ENABLE_LIVE_POLLER", "true").lower() in ("1", "true", "yes")

SITE = validate_site(json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8")))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))


def _get_json(client, url, params=None):
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _hko(data_type):
    return lambda client: _get_json(client, WARN_URL, {"dataType": data_type, "lang": "tc"})


def make_feeds():
    return FeedSet(
        [
            Feed("hsww", lambda client: _get_json(client, HSWW_URL), 60),
            Feed("warnsum", _hko("warnsum"), 60),
            Feed("warningInfo", _hko("warningInfo"), 60),
            Feed("rhrread", _hko("rhrread"), 600),
            Feed("fnd", _hko("fnd"), 1800),
        ],
        lambda: httpx.Client(timeout=15.0),
    )


FEEDS = make_feeds()


def _poll(stop):
    while not stop.is_set():
        FEEDS.refresh_due()
        stop.wait(POLL_SEC)


@asynccontextmanager
async def lifespan(_app):
    stop = threading.Event()
    if ENABLE_POLLER:
        threading.Thread(target=_poll, args=(stop,), daemon=True, name="live-poll").start()
    yield
    stop.set()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _stale(now):
    ages = (FEEDS.age("hsww", now), FEEDS.age("warnsum", now))
    return any(age is None or age >= STALE_AFTER for age in ages)


@app.get("/api/v1/snapshot")
def snapshot():
    if not ENABLE_POLLER or FEEDS.never_fetched():
        FEEDS.refresh_due()
    if FEEDS.value("hsww") is None and FEEDS.value("warnsum") is None:
        raise HTTPException(status_code=503, detail="no-data")
    now = datetime.now(HKT)
    stale = _stale(now)
    snap = build_snapshot(
        FEEDS.value("hsww") or {},
        FEEDS.value("warnsum") or {},
        FEEDS.value("warningInfo") or {},
        FEEDS.value("rhrread") or {},
        SITE,
        SCHEDULE,
        ICONS,
        fnd=FEEDS.value("fnd") or {},
        now=now,
        stale=stale,
    )
    snap["source"] = "live"
    return snap


@app.get("/api/v1/sim/cases")
def sim_cases():
    if not ENABLE_SIM:
        raise HTTPException(status_code=403, detail="sim-disabled")
    return {"cases": list_cases(), "icons": list_official_icons()}


@app.post("/api/v1/sim")
def sim(body: dict):
    if not ENABLE_SIM:
        raise HTTPException(status_code=403, detail="sim-disabled")
    if body.get("clear"):
        return {"ok": True, "sim": None}
    name = body.get("fixture")
    key = ALIASES.get(name, name)
    if key not in CASE_IDS:
        raise HTTPException(status_code=400, detail="unknown-fixture")
    return build_case(key)
```

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `126 passed`, with no `on_event is deprecated` warnings.

- [ ] **Step 6: Commit**

```bash
git add services/ingest/app/feeds.py services/ingest/app/main.py tests/test_feeds.py tests/test_live_api.py
git commit -m "feat: per-feed cache with own intervals, FastAPI lifespan poller

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 15: Preview cases with a fixed clock, weather and banners

Preview and Gallery need deterministic banners and weather, so every case is built at a fixed clock `SIM_NOW`. Event times are set relative to it.

New cases:
- the four banner sources;
- indoor and air-conditioned trades;
- two supervisor lines;
- stale weather and stale forecast.

`pre8-amber` gains the T3 signal that is always in force with Pre-8.

**Files:**
- Modify: `services/ingest/app/sim_cases.py` (whole file)
- Test: `tests/test_sim_cases.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_sim_cases.py`, append these ids to the end of the `REQUIRED` list:

```python
    "amber-new",
    "hsww-cancel-new",
    "tc8ne-new",
    "rain-black-cancel",
    "rain-amber-tc3",
    "trades-indoor",
    "weather-old",
    "forecast-old",
```

Replace `test_none_is_idle_without_white_weather_tile` with:

```python
def test_none_is_a_normal_day_with_weather():
    snap = build_case("none")
    assert snap["hsww"]["inForce"] is False
    assert snap["priority"]["band"] == "P4"
    assert snap["tone"] == "idle"
    assert snap["display"]["mode"] == "normal"
    assert snap["hko"]["wxIconRel"] == "official/wxicon/pic51.png"
    assert snap["hko"]["icons"] == []
    assert snap["hko"]["headlineZh"] == ""
    assert snap["site"]["tradeZh"] == "紮鐵"
    assert snap["site"]["workloadZh"] == "極重勞動"
```

Append:

```python
def test_banner_cases():
    amber_new = build_case("amber-new")["banner"]
    assert (amber_new["time"], amber_new["textZh"]) == ("14:42", "黃色工作暑熱警告 生效")
    assert build_case("hsww-cancel-new")["banner"]["textZh"] == "工作暑熱警告 取消"
    assert build_case("tc8ne-new")["banner"]["textZh"] == "八號東北烈風或暴風信號 發出"
    assert build_case("rain-black-cancel")["banner"]["textZh"] == "黑色暴雨警告信號 取消"
    assert build_case("amber")["banner"] is None
    assert build_case("stale")["banner"] is None


def test_weather_freshness_cases():
    none = build_case("none")
    assert none["weather"]["placeZh"] == "觀塘"
    assert none["forecast"]["date"] == "20260716"
    assert build_case("weather-old")["weather"] is None
    assert build_case("forecast-old")["forecast"] is None


def test_indoor_and_aircon_trades():
    tiles = build_case("trades-indoor")["restTiles"]
    assert [(t["kind"], t["rest"], t["tradesZh"]) for t in tiles] == [
        ("rest", 45, "紮鐵"),
        ("rest", 30, "焊接"),
        ("baseline", 10, "室內裝修 · 電工"),
    ]


def test_two_supervisor_lines():
    lines = build_case("rain-amber-tc3")["supervisor"]
    assert [line["text"] for line in lines] == ["停止操作起重機、吊船", "停止操作吊船、進行斜坡工程"]


def test_pre8_shows_the_signal_in_force():
    assert build_case("pre8-amber")["display"]["heroRel"] == "official/warning/tc3.png"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_sim_cases.py -q`
Expected: failures (unknown case ids, no weather on `none`, `pre8-amber` has no hero)

- [ ] **Step 3: Replace `services/ingest/app/sim_cases.py`**

```python
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.site import validate_site
from app.snapshot import build_snapshot

HKT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
FIX = ROOT / "tests" / "fixtures"
SITE = validate_site(json.loads((ROOT / "config/sites/demo-site.json").read_text(encoding="utf-8")))
SCHEDULE = json.loads((ROOT / "config/rest_schedule.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "config/official_icons.json").read_text(encoding="utf-8"))
WX_NAMES = json.loads((ROOT / "config/wx_icons.json").read_text(encoding="utf-8"))["icons"]

CANCELLED = "hsww_cancelled_stale.json"
# Preview cases are built at a fixed clock so banners and weather freshness are deterministic.
SIM_NOW = datetime(2026, 7, 15, 14, 45, tzinfo=HKT)
OLD = 120  # minutes ago: too old for the change banner


def _ago(minutes):
    return (SIM_NOW - timedelta(minutes=minutes)).isoformat(timespec="seconds")


def _zh_time(at):
    half = "上" if at.hour < 12 else ("中" if at.hour == 12 else "下")
    return f"{half}午{at.hour % 12 or 12}時{at.minute}分"


def _hsww(name: str, minutes_ago: int | None = None) -> dict:
    raw = json.loads((FIX / name).read_text(encoding="utf-8"))
    if minutes_ago is not None:
        at = SIM_NOW - timedelta(minutes=minutes_ago)
        raw["date"] = (at - timedelta(minutes=2)).strftime("%Y%m%d%H%M")
        raw["MessageTC2"] = re.sub(r"[上中下]午\d{1,2}時\d{1,2}分", _zh_time(at), raw.get("MessageTC2") or "")
    return raw


def _rhrread(minutes_ago: int) -> dict:
    raw = json.loads((FIX / "rhrread_sample.json").read_text(encoding="utf-8"))
    raw["updateTime"] = _ago(minutes_ago)
    return raw


def _fnd(minutes_ago: int) -> dict:
    raw = json.loads((FIX / "fnd_sample.json").read_text(encoding="utf-8"))
    raw["updateTime"] = _ago(minutes_ago)
    for i, day in enumerate(raw["weatherForecast"], start=1):
        day["forecastDate"] = (SIM_NOW + timedelta(days=i)).strftime("%Y%m%d")
    return raw


def _warn(code: str, name: str, type_: str, minutes_ago: int = OLD, action: str = "ISSUE") -> dict:
    if code.startswith("TC"):
        key = "WTCSGNL"
    elif code.startswith("WRAIN"):
        key = "WRAIN"
    elif code in {"WFIREY", "WFIRER"}:
        key = "WFIRE"
    else:
        key = code
    at = _ago(minutes_ago)
    return {key: {"name": name, "code": code, "actionCode": action, "type": type_, "issueTime": at, "updateTime": at}}


def _merge_warn(*parts: dict) -> dict:
    out = {}
    for part in parts:
        out.update(part)
    return out


def _merge_info(*parts: dict) -> dict:
    details = []
    for part in parts:
        details.extend((part or {}).get("details") or [])
    return {"details": details}


def _info(code: str, text: str, subtype: str | None = None, minutes_ago: int = OLD) -> dict:
    return {
        "details": [
            {
                "warningStatementCode": code,
                "subtype": subtype or code,
                "contents": [text],
                "updateTime": _ago(minutes_ago),
            }
        ]
    }


TC3_WARN = _warn("TC3", "熱帶氣旋警告信號", "三號強風信號")
TC3_INFO = _info("WTCSGNL", "三號強風信號現正生效。", "TC3")

SPECS = [
    {"id": "none", "labelZh": "無警告", "group": "hsww"},
    {"id": "amber", "labelZh": "黃色暑熱", "group": "hsww", "hsww": "hsww_amber_inforce.json"},
    {"id": "red", "labelZh": "紅色暑熱", "group": "hsww", "hsww": "hsww_red_synth.json"},
    {"id": "black", "labelZh": "黑色暑熱", "group": "hsww", "hsww": "hsww_black_synth.json"},
    {
        "id": "tc1",
        "labelZh": "一號戒備",
        "group": "tc",
        "warnsum": _warn("TC1", "熱帶氣旋警告信號", "一號戒備信號"),
        "info": _info("WTCSGNL", "一號戒備信號現正生效。", "TC1"),
    },
    {"id": "tc3", "labelZh": "三號強風", "group": "tc", "warnsum": TC3_WARN, "info": TC3_INFO},
    {
        "id": "tc8ne",
        "labelZh": "八號東北",
        "group": "tc",
        "warnsum": _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE"),
    },
    {
        "id": "tc8se",
        "labelZh": "八號東南",
        "group": "tc",
        "warnsum": _warn("TC8SE", "熱帶氣旋警告信號", "八號東南烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號東南烈風或暴風信號現正生效。", "TC8SE"),
    },
    {
        "id": "tc8nw",
        "labelZh": "八號西北",
        "group": "tc",
        "warnsum": _warn("TC8NW", "熱帶氣旋警告信號", "八號西北烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號西北烈風或暴風信號現正生效。", "TC8NW"),
    },
    {
        "id": "tc8sw",
        "labelZh": "八號西南",
        "group": "tc",
        "warnsum": _warn("TC8SW", "熱帶氣旋警告信號", "八號西南烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號西南烈風或暴風信號現正生效。", "TC8SW"),
    },
    {
        "id": "tc9",
        "labelZh": "九號烈風",
        "group": "tc",
        "warnsum": _warn("TC9", "熱帶氣旋警告信號", "九號烈風或暴風風力增強信號"),
        "info": _info("WTCSGNL", "九號烈風或暴風風力增強信號現正生效。", "TC9"),
    },
    {
        "id": "tc10",
        "labelZh": "十號颶風",
        "group": "tc",
        "warnsum": _warn("TC10", "熱帶氣旋警告信號", "十號颶風信號"),
        "info": _info("WTCSGNL", "十號颶風信號現正生效。", "TC10"),
    },
    {
        "id": "rain-amber",
        "labelZh": "黃色暴雨",
        "group": "rain",
        "warnsum": _warn("WRAINA", "暴雨警告信號", "黃色暴雨警告信號"),
        "info": _info("WRAIN", "黃色暴雨警告信號現正生效。", "WRAINA"),
    },
    {
        "id": "rain-red",
        "labelZh": "紅色暴雨",
        "group": "rain",
        "warnsum": _warn("WRAINR", "暴雨警告信號", "紅色暴雨警告信號"),
        "info": _info("WRAIN", "紅色暴雨警告信號現正生效。", "WRAINR"),
    },
    {
        "id": "rain-black",
        "labelZh": "黑色暴雨",
        "group": "rain",
        "warnsum": _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號"),
        "info": _info("WRAIN", "黑色暴雨警告信號現正生效。", "WRAINB"),
    },
    {
        "id": "thunderstorm",
        "labelZh": "雷暴",
        "group": "other",
        "warnsum": _warn("WTS", "雷暴警告", "雷暴警告"),
        "info": _info("WTS", "雷暴警告現正生效。"),
    },
    {
        "id": "landslip",
        "labelZh": "山泥傾瀉",
        "group": "other",
        "warnsum": _warn("WL", "山泥傾瀉警告", "山泥傾瀉警告"),
        "info": _info("WL", "山泥傾瀉警告現正生效。"),
    },
    {
        "id": "vhot",
        "labelZh": "酷熱天氣",
        "group": "other",
        "warnsum": _warn("WHOT", "酷熱天氣警告", "酷熱天氣警告"),
        "info": _info("WHOT", "酷熱天氣警告現正生效。"),
    },
    {
        "id": "monsoon",
        "labelZh": "強烈季候風",
        "group": "other",
        "warnsum": _warn("WMSGNL", "強烈季候風信號", "強烈季候風信號"),
        "info": _info("WMSGNL", "強烈季候風信號現正生效。"),
    },
    {
        "id": "pre8",
        "labelZh": "預警八號",
        "group": "tc",
        "warnsum": TC3_WARN,
        "info": _info("WTCPRE8", "天文台預告將改發八號烈風或暴風信號。"),
    },
    {
        "id": "amber-tc1",
        "labelZh": "黃暑熱＋一號",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("TC1", "熱帶氣旋警告信號", "一號戒備信號"),
        "info": _info("WTCSGNL", "一號戒備信號現正生效。", "TC1"),
    },
    {
        "id": "amber-vhot",
        "labelZh": "黃暑熱＋酷熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("WHOT", "酷熱天氣警告", "酷熱天氣警告"),
        "info": _info("WHOT", "酷熱天氣警告現正生效。"),
    },
    {
        "id": "amber-ts",
        "labelZh": "黃暑熱＋雷暴",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("WTS", "雷暴警告", "雷暴警告"),
        "info": _info("WTS", "雷暴警告現正生效。"),
    },
    {
        "id": "amber-tc3",
        "labelZh": "黃暑熱＋三號",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": TC3_WARN,
        "info": TC3_INFO,
    },
    {
        "id": "tc8-amber",
        "labelZh": "八號＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號"),
        "info": _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE"),
    },
    {
        "id": "rain-black-amber",
        "labelZh": "黑雨＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號"),
        "info": _info("WRAIN", "黑色暴雨警告信號現正生效。", "WRAINB"),
    },
    {
        "id": "pre8-amber",
        "labelZh": "預警八號＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": TC3_WARN,
        "info": _info("WTCPRE8", "天文台預告將改發八號烈風或暴風信號。"),
    },
    {
        "id": "typhoon-stack",
        "labelZh": "八號＋黑雨＋山泥＋黃暑熱",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "warnsum": _merge_warn(
            _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號"),
            _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號"),
            _warn("WL", "山泥傾瀉警告", "山泥傾瀉警告"),
        ),
        "info": _merge_info(
            _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE"),
            _info("WRAIN", "黑色暴雨警告信號現正生效。", "WRAINB"),
            _info("WL", "山泥傾瀉警告現正生效。"),
        ),
    },
    {"id": "stale", "labelZh": "資料過期", "group": "hsww", "stale": True},
    {
        "id": "cold",
        "labelZh": "寒冷天氣",
        "group": "other",
        "warnsum": _warn("WCOLD", "寒冷天氣警告", "寒冷天氣警告"),
        "info": _info("WCOLD", "寒冷天氣警告現正生效。"),
    },
    {
        "id": "fire-yellow",
        "labelZh": "黃色火災危險",
        "group": "other",
        "warnsum": _warn("WFIREY", "火災危險警告", "黃色火災危險警告"),
        "info": _info("WFIRE", "黃色火災危險警告現正生效。", "WFIREY"),
    },
    {
        "id": "fire-red",
        "labelZh": "紅色火災危險",
        "group": "other",
        "warnsum": _warn("WFIRER", "火災危險警告", "紅色火災危險警告"),
        "info": _info("WFIRE", "紅色火災危險警告現正生效。", "WFIRER"),
    },
    {
        "id": "frost",
        "labelZh": "霜凍",
        "group": "other",
        "warnsum": _warn("WFROST", "霜凍警告", "霜凍警告"),
        "info": _info("WFROST", "霜凍警告現正生效。"),
    },
    {
        "id": "ntfl",
        "labelZh": "新界北部水浸",
        "group": "other",
        "warnsum": _warn("WFNTSA", "新界北部水浸特別報告", "新界北部水浸特別報告"),
        "info": _info("WFNTSA", "新界北部水浸特別報告現正生效。"),
    },
    {
        "id": "tsunami",
        "labelZh": "海嘯",
        "group": "other",
        "warnsum": _warn("WTMW", "海嘯警告", "海嘯警告"),
        "info": _info("WTMW", "海嘯警告現正生效。"),
    },
    {"id": "amber-new", "labelZh": "黃暑熱（剛生效）", "group": "hsww", "hsww": "hsww_amber_inforce.json", "hswwAgo": 3},
    {"id": "hsww-cancel-new", "labelZh": "暑熱警告（剛取消）", "group": "hsww", "hsww": CANCELLED, "hswwAgo": 4},
    {
        "id": "tc8ne-new",
        "labelZh": "八號東北（剛發出）",
        "group": "tc",
        "warnsum": _warn("TC8NE", "熱帶氣旋警告信號", "八號東北烈風或暴風信號", minutes_ago=4),
        "info": _info("WTCSGNL", "八號東北烈風或暴風信號現正生效。", "TC8NE", minutes_ago=4),
    },
    {
        "id": "rain-black-cancel",
        "labelZh": "黑雨（剛取消）",
        "group": "rain",
        "warnsum": _warn("WRAINB", "暴雨警告信號", "黑色暴雨警告信號", minutes_ago=3, action="CANCEL"),
    },
    {
        "id": "rain-amber-tc3",
        "labelZh": "黃雨＋三號",
        "group": "combo",
        "warnsum": _merge_warn(_warn("WRAINA", "暴雨警告信號", "黃色暴雨警告信號"), TC3_WARN),
    },
    {
        "id": "trades-indoor",
        "labelZh": "黃暑熱＋室內工種",
        "group": "combo",
        "hsww": "hsww_amber_inforce.json",
        "site": {
            "primaryTrades": [
                {"id": "bar-fixer", "labelZh": "紮鐵", "workload": "very_heavy"},
                {"id": "fitout", "labelZh": "室內裝修", "workload": "moderate", "environment": "indoor"},
                {"id": "electrician", "labelZh": "電工", "workload": "moderate", "environment": "aircon"},
                {"id": "welder", "labelZh": "焊接", "workload": "moderate", "adjustMinutes": 15},
            ]
        },
    },
    {"id": "weather-old", "labelZh": "天氣資料過舊", "group": "other", "rhrreadAgo": 120},
    {"id": "forecast-old", "labelZh": "預報資料過舊", "group": "other", "fndAgo": 13 * 60},
]

CASE_IDS = [s["id"] for s in SPECS]
_BY_ID = {s["id"]: s for s in SPECS}

# Aliases used by the old 6-button sim bar.
ALIASES = {"black-rain": "rain-black", "tc8": "tc8ne"}

HSWW_ICONS = [
    {"code": "HSWW-amber", "labelZh": "黃色工作暑熱警告", "rel": "official/hkhi_yellow.png", "kind": "hsww"},
    {"code": "HSWW-red", "labelZh": "紅色工作暑熱警告", "rel": "official/hkhi_red.png", "kind": "hsww"},
    {"code": "HSWW-black", "labelZh": "黑色工作暑熱警告", "rel": "official/hkhi_black.png", "kind": "hsww"},
    {"code": "LD", "labelZh": "勞工處", "rel": "official/ld_logo.png", "kind": "hsww"},
]

WX_ICONS = [
    {"code": f"pic{code}", "labelZh": name, "rel": f"official/wxicon/pic{code}.png", "kind": "wx"}
    for code, name in WX_NAMES.items()
]

WARN_LABELS = {
    "TC1": "一號戒備信號",
    "TC3": "三號強風信號",
    "TC8NE": "八號東北",
    "TC8SE": "八號東南",
    "TC8NW": "八號西北",
    "TC8SW": "八號西南",
    "TC9": "九號烈風",
    "TC10": "十號颶風",
    "WRAINA": "黃色暴雨",
    "WRAINR": "紅色暴雨",
    "WRAINB": "黑色暴雨",
    "WTS": "雷暴警告",
    "WL": "山泥傾瀉",
    "WHOT": "酷熱天氣",
    "WMSGNL": "強烈季候風",
    "WCOLD": "寒冷天氣",
    "WFIREY": "黃色火災危險",
    "WFIRER": "紅色火災危險",
    "WFROST": "霜凍",
    "WFNTSA": "新界北部水浸",
    "WTMW": "海嘯",
}


def build_case(name: str) -> dict:
    spec = _BY_ID.get(ALIASES.get(name, name))
    if spec is None:
        raise KeyError(name)
    site = validate_site({**SITE, **spec["site"]}) if spec.get("site") else SITE
    snap = build_snapshot(
        _hsww(spec.get("hsww", CANCELLED), spec.get("hswwAgo")),
        spec.get("warnsum") or {},
        spec.get("info") or {"details": []},
        _rhrread(spec.get("rhrreadAgo", 20)),
        site,
        SCHEDULE,
        ICONS,
        fnd=_fnd(spec.get("fndAgo", OLD)),
        now=SIM_NOW,
        stale=bool(spec.get("stale")),
    )
    if spec.get("stale"):
        snap["tone"] = "stale"
    return snap


def list_cases() -> list[dict]:
    return [
        {"id": spec["id"], "labelZh": spec["labelZh"], "group": spec["group"], "snapshot": build_case(spec["id"])}
        for spec in SPECS
    ]


def list_official_icons() -> list[dict]:
    warn = [
        {"code": code, "labelZh": WARN_LABELS.get(code, code), "rel": rel, "kind": "warning"}
        for code, rel in ICONS.items()
    ]
    return HSWW_ICONS + warn + WX_ICONS
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `131 passed`

- [ ] **Step 5: Commit**

```bash
git add services/ingest/app/sim_cases.py tests/test_sim_cases.py
git commit -m "feat: preview cases at a fixed clock with weather, banners and trade variants

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 16: One `Screen` component and the new layout

The kiosk only renders the snapshot.
- **Sizing:** everything inside `.stage` uses container-query units (`cqh`/`cqw`), so the same component also works as a Gallery thumbnail.
- **Portrait:** `@container (max-aspect-ratio: 3/4)` switches the layout.

The sizes and colours come from the spec §4.1 and the rendered mockups.

**Files:**
- Modify: `apps/kiosk/src/present.ts` (whole file)
- Create: `apps/kiosk/src/Screen.tsx`
- Modify: `apps/kiosk/src/Kiosk.tsx` (whole file)
- Modify: `apps/kiosk/src/kiosk.css` (whole file)
- Modify: `apps/kiosk/src/Gallery.tsx` (whole file), `apps/kiosk/src/gallery.css`
- Modify: `apps/kiosk/index.html`

- [ ] **Step 1: Replace `apps/kiosk/src/present.ts`**

```ts
export type Signal = {
  code: string;
  rel: string | null;
  labelZh: string;
  kind: string;
  impact?: "high" | "low";
};

export type RestTile = {
  kind: "suspend" | "rest" | "baseline";
  rest: number;
  work: number | null;
  perHours: number;
  trades: string[];
  tradesZh: string;
};

export type Banner = { time: string; textZh: string; kind: "issue" | "cancel"; code: string };

export type SupervisorLine = { text: string; fromZh: string };

export type WeatherNow = {
  iconRel: string | null;
  tempC: number;
  placeZh: string;
  humidity: number | null;
  uvValue: number | null;
  uvDescZh: string | null;
  updatedAt: string;
};

export type Forecast = { date: string; iconRel: string | null; minC: number | null; maxC: number | null };

export type Display = {
  mode: "normal" | "heat" | "weather";
  main: string | null;
  sub: string[];
  meta: string | null;
  heroRel: string | null;
  action: string;
  actionSub: string;
};

export type Snapshot = {
  generatedAt: string;
  clock?: string;
  staleAfterSec: number;
  stale?: boolean;
  tone?: string;
  signals?: Signal[];
  display: Display;
  restTiles?: RestTile[];
  notes?: string[];
  supervisor?: SupervisorLine[];
  banner?: Banner | null;
  weather?: WeatherNow | null;
  forecast?: Forecast | null;
};

const HK = "Asia/Hong_Kong";
const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

export function isStale(s: Snapshot, now = Date.now()): boolean {
  if (s.stale) return true;
  const t = Date.parse(s.generatedAt);
  if (Number.isNaN(t)) return true;
  return now - t > (s.staleAfterSec || 600) * 1000;
}

export function railSignals(s: Snapshot): (Signal & { rel: string })[] {
  return (s.signals || []).filter((x): x is Signal & { rel: string } => Boolean(x.rel));
}

export function formatUv(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function clockNow(d = new Date()): string {
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: HK });
}

export function dateZh(d = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: HK,
    month: "numeric",
    day: "numeric",
    weekday: "short",
  }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const day = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(get("weekday"));
  return `${get("month")}月${get("day")}日 星期${WEEKDAYS[day] ?? ""}`;
}
```

- [ ] **Step 2: Create `apps/kiosk/src/Screen.tsx`**

```tsx
import type { CSSProperties, ReactNode } from "react";
import { formatUv, isStale, railSignals, type RestTile, type Snapshot } from "./present";

const STALE_TEXT = "資料過期 — 請以我的天文台為準";

function Plate({ rel, className }: { rel: string; className?: string }) {
  return (
    <span className={className ? `plate ${className}` : "plate"}>
      <img src={"/" + rel} alt="" />
    </span>
  );
}

function Tile({ tile }: { tile: RestTile }) {
  if (tile.kind === "suspend") {
    return (
      <div className="tile stop">
        <div className="trades">{tile.tradesZh}</div>
        <div className="big big-word">暫停工作</div>
        <div className="small" />
      </div>
    );
  }
  return (
    <div className="tile">
      <div className="trades">{tile.tradesZh}</div>
      <div className="big">
        休息<b>{tile.rest}</b>分鐘
      </div>
      <div className="small">{tile.kind === "baseline" ? `每 ${tile.perHours} 小時` : `工作 ${tile.work} 分鐘`}</div>
    </div>
  );
}

type ScreenProps = {
  snap: Snapshot;
  clock: string;
  date: string;
  layout?: string;
  simbar?: ReactNode;
};

export function Screen({ snap, clock, date, layout, simbar }: ScreenProps) {
  const stale = isStale(snap);
  const display = snap.display;
  const mode = display.mode || "normal";
  const main = display.main || display.action || "";
  const banner = stale ? null : snap.banner;
  const weather = snap.weather;
  const forecast = snap.forecast;
  const supervisor = snap.supervisor || [];

  return (
    <div
      className="stage"
      data-tone={snap.tone || "idle"}
      data-mode={mode}
      data-sup={supervisor.length || undefined}
      data-layout={layout}
    >
      {simbar}
      {stale ? (
        <div className="banner banner-stale">
          <span className="msg">{STALE_TEXT}</span>
        </div>
      ) : banner ? (
        <div className="banner">
          <span className="tag">最新</span>
          <span className="msg">
            {banner.time}　{banner.textZh}
          </span>
        </div>
      ) : null}

      <div className="center">
        {display.heroRel && <Plate rel={display.heroRel} className="hero" />}
        {mode === "heat" ? (
          <>
            <div className="tiles">
              {(snap.restTiles || []).map((tile) => (
                <Tile key={`${tile.kind}-${tile.rest}`} tile={tile} />
              ))}
            </div>
            {display.meta && <div className="meta">{display.meta}</div>}
            {(snap.notes || []).map((note) => (
              <div key={note} className="note">
                {note}
              </div>
            ))}
          </>
        ) : (
          <>
            <div className="action" style={{ "--chars": [...main].length } as CSSProperties}>
              {main}
            </div>
            {(display.sub || []).map((line) => (
              <div key={line} className="sub">
                {line}
              </div>
            ))}
            {display.meta && <div className="meta">{display.meta}</div>}
          </>
        )}
        {supervisor.map((line) => (
          <div key={line.text} className="sup">
            <span className="lab">主管注意</span>
            <span className="txt">{line.text}</span>
            <span className="src">{line.fromZh}</span>
          </div>
        ))}
      </div>

      <div className="bar">
        <div className="rail">
          {railSignals(snap).map((s) => (
            <Plate key={s.code} rel={s.rel} />
          ))}
        </div>
        <div className="info">
          {weather && (
            <div className="wx">
              {weather.iconRel && <Plate rel={weather.iconRel} />}
              <div className="temp">
                {weather.tempC}°<small>{weather.placeZh}</small>
              </div>
              <div className="metaw">
                {weather.humidity !== null && <div>濕度 {weather.humidity}%</div>}
                {weather.uvValue !== null && (
                  <div>
                    紫外線 {formatUv(weather.uvValue)} {weather.uvDescZh || ""}
                  </div>
                )}
              </div>
            </div>
          )}
          {forecast && (
            <>
              <div className="sep" />
              <div className="wx tmr">
                {forecast.iconRel && <Plate rel={forecast.iconRel} />}
                <div className="range">
                  <small>明日</small>
                  {forecast.minC}–{forecast.maxC}°
                </div>
              </div>
            </>
          )}
          <div className="sep sep-clock" />
          <div className="clock">
            <div className="t">{clock}</div>
            <div className="d">{date}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Replace `apps/kiosk/src/Kiosk.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { clockNow, dateZh, type Snapshot } from "./present";
import { Screen } from "./Screen";

const params = new URLSearchParams(window.location.search);
const flag = (...keys: string[]) => keys.some((k) => params.get(k) === "1");
const PREVIEW = flag("preview", "sim");
const LIVE = !PREVIEW || flag("live", "kiosk");
const FIXTURE = params.get("fixture");
// ?bar=0 hides the preview buttons, for screenshots and showing a case on a real screen.
const SHOW_BAR = params.get("bar") !== "0";
const POLL_MS = 30_000;

type CaseBtn = { id: string; labelZh: string };

const FALLBACK_CASES: CaseBtn[] = [
  { id: "none", labelZh: "無警告" },
  { id: "amber", labelZh: "黃色暑熱" },
  { id: "red", labelZh: "紅色暑熱" },
  { id: "black", labelZh: "黑色暑熱" },
  { id: "tc8ne", labelZh: "八號東北" },
  { id: "rain-black", labelZh: "黑色暴雨" },
];

async function loadSnap(): Promise<Snapshot> {
  const r = await fetch("/api/v1/snapshot");
  if (!r.ok) throw new Error("snapshot");
  return r.json();
}

function readLayout(): "portrait" | "landscape" {
  return window.innerWidth / Math.max(window.innerHeight, 1) < 0.75 ? "portrait" : "landscape";
}

export function Kiosk() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseBtn[]>([]);
  const [clock, setClock] = useState(clockNow);
  const [date, setDate] = useState(dateZh);
  const [holdSim, setHoldSim] = useState(false);
  const [layout, setLayout] = useState(readLayout);
  // Once a preview case is requested, a late live response must never overwrite it.
  const holdSimRef = useRef(Boolean(PREVIEW && !LIVE && FIXTURE));

  useEffect(() => {
    document.documentElement.classList.toggle("live", LIVE);
    document.documentElement.classList.toggle("kiosk", LIVE);
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setClock(clockNow());
      setDate(dateZh());
    }, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const onResize = () => setLayout(readLayout());
    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
  }, []);

  useEffect(() => {
    if (holdSim || holdSimRef.current) return;
    let alive = true;
    const tick = async () => {
      try {
        const s = await loadSnap();
        if (alive && !holdSimRef.current) {
          setSnap(s);
          setErr(null);
        }
      } catch {
        if (alive && !holdSimRef.current) setErr("無法取得資料 — 請以我的天文台為準");
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [holdSim]);

  useEffect(() => {
    if (!PREVIEW || LIVE) return;
    fetch("/api/v1/sim/cases")
      .then((r) => r.json())
      .then((d) => setCases((d.cases || []).map((c: CaseBtn) => ({ id: c.id, labelZh: c.labelZh }))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!PREVIEW || LIVE || !FIXTURE) return;
    void sim(FIXTURE);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sim(name: string) {
    holdSimRef.current = true;
    const r = await fetch("/api/v1/sim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fixture: name }),
    });
    if (!r.ok) return;
    setHoldSim(true);
    setSnap(await r.json());
    setErr(null);
  }

  if (!snap) {
    return (
      <div className="stage" data-tone="idle" data-layout={layout}>
        <div className="boot">{err || "載入中…"}</div>
      </div>
    );
  }

  const simbar =
    PREVIEW && !LIVE && SHOW_BAR ? (
      <div className="simbar">
        <a className="sim-link" href="/">
          Live
        </a>
        <a className="sim-link" href="/?gallery=1">
          Gallery
        </a>
        {(cases.length ? cases : FALLBACK_CASES).map((n) => (
          <button key={n.id} type="button" onClick={() => sim(n.id)}>
            {n.labelZh}
          </button>
        ))}
      </div>
    ) : null;

  return <Screen snap={snap} clock={clock} date={date} layout={layout} simbar={simbar} />;
}
```

- [ ] **Step 4: Replace `apps/kiosk/src/kiosk.css`**

```css
html,
body,
#root {
  margin: 0;
  height: 100%;
  overflow: hidden;
  background: #c9c2b0;
  color: #1b1914;
  color-scheme: light;
  font-family: "Noto Sans HK", "Microsoft JhengHei", "Noto Sans CJK HK", sans-serif;
  user-select: none;
  -webkit-user-select: none;
}

html.live,
html.live *,
html.kiosk,
html.kiosk * {
  cursor: none !important;
}

html.gallery-page,
html.gallery-page body,
html.gallery-page #root {
  height: auto;
  min-height: 100%;
  overflow: auto;
  background: #1a1714;
  color: #f4efe6;
  color-scheme: dark;
}

.stage {
  --bg: #c9c2b0;
  --fg: #1b1914;
  position: relative;
  container-type: size;
  box-sizing: border-box;
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg);
  color: var(--fg);
}

.stage[data-tone="amber"] {
  --bg: #f5c518;
  --fg: #111111;
}

.stage[data-tone="red"] {
  --bg: #c1121f;
  --fg: #ffffff;
}

.stage[data-tone="black"] {
  --bg: #111111;
  --fg: #ffffff;
}

.stage[data-tone="p0-tc"] {
  --bg: #4a0000;
  --fg: #ffffff;
}

.stage[data-tone="p0-rain"] {
  --bg: #0a0a0a;
  --fg: #ffffff;
}

.stage[data-tone="p0-landslip"] {
  --bg: #1a1208;
  --fg: #ffffff;
}

.stage[data-tone="p1"] {
  --bg: #3a2208;
  --fg: #ffffff;
}

.stage[data-tone="watch"] {
  --bg: #243044;
  --fg: #f4efe6;
}

.boot {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 6vh;
  font-weight: 900;
}

.banner {
  position: absolute;
  inset: 0 0 auto 0;
  z-index: 5;
  box-sizing: border-box;
  min-height: 8cqh;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.4cqw;
  padding: 0.8cqh 3cqw;
  background: var(--fg);
  color: var(--bg);
}

.banner-stale {
  background: #c1121f;
  color: #ffffff;
}

.banner .tag {
  white-space: nowrap;
  font-size: 2.6cqh;
  font-weight: 900;
  border: 0.35cqh solid currentColor;
  border-radius: 0.8cqh;
  padding: 0.2cqh 0.9cqw;
}

.banner .msg {
  font-size: 3.8cqh;
  font-weight: 900;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.center {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.3cqh;
  padding: 9cqh 3cqw 0.6cqh;
  text-align: center;
}

.plate {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
  background: #f4efe6;
  border-radius: 1.2cqh;
}

.plate img {
  display: block;
  object-fit: contain;
}

.hero {
  padding: 1.4cqh;
}

.hero img {
  height: 34cqh;
  width: 34cqh;
}

.stage[data-mode="heat"] .hero img {
  height: 24cqh;
  width: 24cqh;
}

.stage[data-sup="1"] .hero img {
  height: 30cqh;
  width: 30cqh;
}

.stage[data-sup="2"] .hero img {
  height: 25cqh;
  width: 25cqh;
}

.stage[data-mode="heat"][data-sup="1"] .hero img {
  height: 20cqh;
  width: 20cqh;
}

.stage[data-mode="heat"][data-sup="2"] .hero img {
  height: 16cqh;
  width: 16cqh;
}

.action {
  font-size: min(11.5cqh, calc(88cqw / var(--chars, 4)));
  font-weight: 900;
  line-height: 1.04;
  letter-spacing: 0.02em;
  white-space: nowrap;
  margin-top: 0.4cqh;
}

.sub {
  font-size: 4.2cqh;
  font-weight: 700;
  line-height: 1.25;
}

.meta {
  font-size: 3cqh;
  font-weight: 500;
  line-height: 1.25;
}

.note {
  font-size: 2.7cqh;
  font-weight: 700;
}

.tiles {
  width: 94cqw;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: stretch;
  gap: 1.4cqw;
}

.tile {
  flex: 0 1 22cqw;
  min-width: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4cqh;
  padding: 1.3cqh 1cqw 1.4cqh;
  border-radius: 1.6cqh;
  background: color-mix(in srgb, var(--fg) 11%, transparent);
}

.tile .trades {
  align-self: stretch;
  font-size: 3.6cqh;
  font-weight: 900;
  padding-bottom: 0.8cqh;
  margin-bottom: 0.3cqh;
  border-bottom: 0.3cqh solid color-mix(in srgb, var(--fg) 35%, transparent);
}

.tile .big {
  font-size: 4.6cqh;
  font-weight: 900;
  line-height: 1.05;
  white-space: nowrap;
}

.tile .big b {
  font-size: 8cqh;
  font-weight: 900;
  padding: 0 0.16em;
}

.tile .big-word {
  font-size: 6.8cqh;
  line-height: 1.22;
}

.tile .small {
  font-size: 2.6cqh;
  font-weight: 700;
  min-height: 3.2cqh;
}

.tile.stop {
  background: var(--fg);
}

.tile.stop > * {
  color: var(--bg);
  border-color: color-mix(in srgb, var(--bg) 40%, transparent);
}

.sup {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.6cqh 1cqw;
  margin-top: 0.6cqh;
  padding: 0.8cqh 1.2cqw;
  border: 0.3cqh solid color-mix(in srgb, var(--fg) 55%, transparent);
  border-radius: 1.2cqh;
}

.sup .lab {
  white-space: nowrap;
  font-size: 2.4cqh;
  font-weight: 900;
  background: var(--fg);
  color: var(--bg);
  border-radius: 0.7cqh;
  padding: 0.3cqh 0.7cqw;
}

.sup .txt {
  font-size: 3.3cqh;
  font-weight: 900;
}

.sup .src {
  white-space: nowrap;
  font-size: 2.5cqh;
  font-weight: 500;
}

.bar {
  height: 17cqh;
  display: flex;
  align-items: center;
  gap: 1.4cqw;
  padding: 0 2.6cqw 1.4cqh;
}

.rail {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 1cqw;
}

.rail .plate {
  padding: 0.8cqh;
}

.rail .plate img {
  height: 12cqh;
  width: 12cqh;
}

.info {
  display: flex;
  align-items: center;
  gap: 2cqw;
  white-space: nowrap;
}

.wx {
  display: flex;
  align-items: center;
  gap: 0.8cqw;
}

.wx .plate {
  padding: 0.5cqh;
}

.wx .plate img {
  height: 7cqh;
  width: 7cqh;
}

.tmr .plate img {
  height: 5.6cqh;
  width: 5.6cqh;
}

.temp {
  font-size: 6.6cqh;
  font-weight: 900;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.temp small {
  display: block;
  font-size: 2.3cqh;
  font-weight: 700;
  margin-top: 0.5cqh;
}

.metaw {
  font-size: 2.6cqh;
  font-weight: 700;
  line-height: 1.45;
}

.range {
  font-size: 4.2cqh;
  font-weight: 900;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.range small {
  display: block;
  font-size: 2.3cqh;
  font-weight: 700;
  margin-bottom: 0.6cqh;
}

.sep {
  width: 0.25cqh;
  height: 9cqh;
  background: color-mix(in srgb, var(--fg) 30%, transparent);
}

.clock {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.clock .t {
  font-size: 7.6cqh;
  font-weight: 900;
  line-height: 1;
}

.clock .d {
  font-size: 2.3cqh;
  font-weight: 700;
  margin-top: 0.5cqh;
}

.simbar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.72);
  cursor: auto;
  max-height: 22vh;
  overflow: auto;
}

.simbar button,
.sim-link {
  font-size: 13px;
  padding: 6px 10px;
  cursor: pointer;
  background: #f4efe6;
  color: #1a1714;
  border: 0;
  border-radius: 4px;
  font-weight: 700;
}

@container (max-aspect-ratio: 3/4) {
  .banner {
    min-height: 5.5cqh;
  }

  .banner .tag {
    font-size: 3.2cqw;
  }

  .banner .msg {
    font-size: 3.7cqw;
  }

  .center {
    padding: 7cqh 4cqw 0.6cqh;
    gap: 1.2cqh;
  }

  .hero img {
    height: min(28cqh, 54cqw);
    width: min(28cqh, 54cqw);
  }

  .stage[data-mode="heat"] .center {
    padding-top: 6.5cqh;
  }

  .stage[data-mode="heat"] .hero img {
    height: 11cqh;
    width: 11cqh;
  }

  .stage[data-sup="1"] .hero img,
  .stage[data-sup="2"] .hero img {
    height: min(22cqh, 44cqw);
    width: min(22cqh, 44cqw);
  }

  .stage[data-mode="heat"][data-sup="1"] .hero img,
  .stage[data-mode="heat"][data-sup="2"] .hero img {
    height: 9cqh;
    width: 9cqh;
  }

  .action {
    font-size: min(10cqh, calc(92cqw / var(--chars, 4)));
  }

  .sub {
    font-size: 4.2cqw;
  }

  .meta {
    font-size: 3.4cqw;
  }

  .note {
    font-size: 3.2cqw;
  }

  .tiles {
    width: 92cqw;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 2.6cqw;
  }

  .tile {
    padding: 1.2cqh 2cqw;
  }

  .tile .trades {
    font-size: 4.6cqw;
  }

  .tile .big {
    font-size: 5cqw;
  }

  .tile .big b {
    font-size: 8.4cqw;
  }

  .tile .big-word {
    font-size: 7.4cqw;
    line-height: 1.3;
  }

  .tile .small {
    font-size: 3.1cqw;
    min-height: 4cqw;
  }

  .sup {
    padding: 0.8cqh 3cqw;
    gap: 0.6cqh 2cqw;
  }

  .sup .lab {
    font-size: 3cqw;
  }

  .sup .txt {
    font-size: 4cqw;
  }

  .sup .src {
    font-size: 3cqw;
  }

  .bar {
    height: auto;
    flex-direction: column;
    gap: 2cqh;
    padding: 1cqh 5cqw 3cqh;
  }

  .rail {
    flex: none;
    justify-content: center;
    gap: 3cqw;
  }

  .rail .plate img {
    height: 13cqw;
    width: 13cqw;
  }

  .info {
    flex-wrap: wrap;
    justify-content: center;
    gap: 2cqh 5cqw;
  }

  .wx .plate img {
    height: 9cqw;
    width: 9cqw;
  }

  .tmr .plate img {
    height: 7cqw;
    width: 7cqw;
  }

  .temp {
    font-size: 8cqw;
  }

  .temp small,
  .range small {
    font-size: 3cqw;
  }

  .metaw {
    font-size: 3.4cqw;
  }

  .range {
    font-size: 5.6cqw;
  }

  .sep-clock {
    display: none;
  }

  .clock {
    flex-basis: 100%;
    display: flex;
    align-items: baseline;
    justify-content: center;
    gap: 3cqw;
    text-align: center;
  }

  .clock .t {
    font-size: 10cqw;
  }

  .clock .d {
    font-size: 3.6cqw;
  }
}
```

- [ ] **Step 5: Load Noto Sans HK in `apps/kiosk/index.html`**

Add inside `<head>`, after the viewport meta:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+HK:wght@500;700;900&display=swap" rel="stylesheet" />
```

- [ ] **Step 6: Gallery renders the same `Screen`**

`Gallery.tsx` imported the old `present()` helper, which no longer exists, so it switches to `Screen` in this same task. Replace `apps/kiosk/src/Gallery.tsx` with:

```tsx
import { useEffect, useState } from "react";
import type { Snapshot } from "./present";
import { Screen } from "./Screen";
import "./gallery.css";

type Icon = { code: string; labelZh: string; rel: string; kind: string };
type Case = { id: string; labelZh: string; group: string; snapshot: Snapshot };

const GROUPS: { id: string; label: string }[] = [
  { id: "hsww", label: "工作暑熱" },
  { id: "tc", label: "熱帶氣旋" },
  { id: "rain", label: "暴雨" },
  { id: "other", label: "其他天氣" },
  { id: "combo", label: "同時生效" },
];

export function Gallery() {
  const [icons, setIcons] = useState<Icon[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.classList.add("gallery-page");
    document.documentElement.classList.remove("kiosk", "live");
    fetch("/api/v1/sim/cases")
      .then((r) => {
        if (!r.ok) throw new Error("cases");
        return r.json();
      })
      .then((d) => {
        setIcons(d.icons || []);
        setCases(d.cases || []);
      })
      .catch(() => setErr("無法載入預覽 — 請確認 ingest API 已開"));
  }, []);

  function openCase(id: string) {
    window.location.href = "/?preview=1&fixture=" + encodeURIComponent(id);
  }

  if (err || !cases.length) {
    return (
      <div className="gallery">
        <p className="gallery-err">{err || "載入中…"}</p>
      </div>
    );
  }

  return (
    <div className="gallery">
      <header className="gallery-head">
        <h1>全部訊號</h1>
        <a href="/">Live</a>
        <a href="/?preview=1">Preview</a>
      </header>

      <h2>官方圖示</h2>
      {["hsww", "warning", "wx"].map((kind) => (
        <div key={kind} className="icon-wall">
          {icons
            .filter((i) => i.kind === kind)
            .map((i) => (
              <figure key={i.code} className="icon-card">
                <img src={"/" + i.rel} alt={i.labelZh} />
                <figcaption>
                  {i.labelZh}
                  <small>{i.code}</small>
                </figcaption>
              </figure>
            ))}
        </div>
      ))}

      <h2>全部訊號</h2>
      {GROUPS.map((g) => {
        const rows = cases.filter((c) => c.group === g.id);
        if (!rows.length) return null;
        return (
          <section key={g.id}>
            <h3>{g.label}</h3>
            <div className="case-grid">
              {rows.map((c) => (
                <button key={c.id} type="button" className="case-tile" onClick={() => openCase(c.id)}>
                  <Screen snap={c.snapshot} clock={c.snapshot.clock || ""} date="" />
                  <span className="case-label">{c.labelZh}</span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
```

In `apps/kiosk/src/gallery.css`:
- Delete every rule whose selector starts with `.case-tile .stage.mini`, plus the `.mini-rail` and `.mini-rail img` rules.
- Change `.case-grid`'s `minmax(280px, 1fr)` to `minmax(360px, 1fr)`.
- Add:

```css
.case-tile .stage {
  height: auto;
  aspect-ratio: 16 / 9;
  pointer-events: none;
}
```

- [ ] **Step 7: Type-check and build**

Run: `cd apps/kiosk && npx tsc --noEmit -p . && npm run build && cd -`
Expected: no TypeScript errors; `✓ built in …`

- [ ] **Step 8: Commit**

```bash
git add apps/kiosk/src apps/kiosk/index.html
git commit -m "feat(kiosk): one centred Screen for kiosk and gallery, container-unit layout

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 17: CI builds and type-checks the kiosk

**Files:**
- Modify: `apps/kiosk/package.json` (`scripts`)
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Make `build` type-check first**

In `apps/kiosk/package.json`, replace the `scripts` block with:

```json
  "scripts": {
    "dev": "vite",
    "typecheck": "tsc --noEmit",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
```

- [ ] **Step 2: Add the kiosk job**

Replace `.github/workflows/ci.yml` with:

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: pip install pytest fastapi httpx uvicorn
      - name: Test
        run: python -m pytest tests -q

  kiosk:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/kiosk
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: apps/kiosk/package-lock.json
      - name: Install
        run: npm ci
      - name: Type-check and build
        run: npm run build
```

- [ ] **Step 3: Verify locally**

Run: `cd apps/kiosk && npm run build && cd -`
Expected: `tsc` prints nothing, then `✓ built in …`

- [ ] **Step 4: Commit**

```bash
git add apps/kiosk/package.json .github/workflows/ci.yml
git commit -m "ci: type-check and build the kiosk

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 18: Docs: rules, sources, site config

**Files:**
- Modify: `AGENTS.md` (whole file), `README.md` (whole file)

- [ ] **Step 1: Replace `AGENTS.md`**

```markdown
# Agent notes

- Display official HKO/LD icons. Do not draw substitute warning symbols.
- HSWW level comes only from `iconIndex` (30 amber / 32 red / 34 black). Never infer level from HKHI CSV or from the title string.
- Do not commit `.env` or real site names.
- Rest numbers live in `config/rest_schedule.json` only. UI must not hardcode minutes.
- Instruction text lives in `config/display_actions.json`. Every displayed fragment must be a verbatim, contiguous part of a quoted official sentence; `tests/test_display_actions.py` enforces this. Never paraphrase official wording.
- Re-verify the official sources every April and whenever LD or HKO announce revisions (checklist: `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md` §9).
```

- [ ] **Step 2: Replace `README.md`**

````markdown
# hk-site-display

Hong Kong construction **site notice**: live Labour Department Heat Stress at Work Warning (HSWW) and HKO weather warnings on one screen at the gate.

Official HKO / Labour Department icons and wording only. Every state uses one centred layout, in landscape or portrait: a large official icon, the instruction, and a bottom bar with every warning in force, district weather, tomorrow's forecast and the clock. On heat-stress days the instruction becomes one tile per rest time, labelled with the site's trades.

## Live demo

| | |
|---|---|
| Live | https://hksite-display.loadingtechnology.app/ |
| Preview (switch cases; does not overlay live) | https://hksite-display.loadingtechnology.app/?preview=1 |
| Gallery (every official icon + case) | https://hksite-display.loadingtechnology.app/?gallery=1 |

![Normal day, 16:9](docs/demo/live-16x9.png)

![Amber heat stress](docs/demo/amber.png)

![Signal 8 NE](docs/demo/tc8.png)

Same URL, portrait:

![Normal day, 9:16](docs/demo/live-9x16.png)

Design and decisions: `docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md`.

## Rules the notice will not break

- HSWW level comes only from `hkhi_icon.xml` `iconIndex` (30 amber / 32 red / 34 black). Never inferred from HKHI CSV or the title string.
- Rest minutes live in `config/rest_schedule.json` only (LD guidance Appendix 4; the indoor −15 minute adjustment reproduces Appendix 4(a)).
- Instruction text lives in `config/display_actions.json`, stored with the official sentence it comes from. `tests/test_display_actions.py` fails if a displayed fragment is not a verbatim part of its quote.
- Warning marks are official HKO/LD files. We do not draw substitute typhoon / rain / heat symbols.
- `GET /api/v1/snapshot` is always live. `POST /sim` is preview-only.

## Official sources (checked 2026-10-06)

- Labour Department 《預防工作時中暑指引》, 3rd edition (revised) Aug 2026: https://www.labour.gov.hk/common/public/oh/Heat_Stress_GN_tc.pdf
- Labour Department 《惡劣天氣及「極端情況」下的工作守則》, May 2026: https://www.labour.gov.hk/tc/public/pdf/wcp/Rainstorm.pdf
- HKO advice pages for tropical cyclone signals, rainstorms, landslips and tsunamis (URLs in `config/display_actions.json`)
- HKO Open Data API documentation: https://data.weather.gov.hk/weatherAPI/doc/HKO_Open_Data_API_Documentation.pdf

Re-check every April and whenever LD or HKO announce a revision (spec §9).

## Data sources

| Feed | Source | Refresh |
|---|---|---|
| HSWW | `https://www.hko.gov.hk/wxinfo/hkhi/hkhi_icon.xml` | 60 s |
| Warnings | HKO Open Data `warnsum` + `warningInfo` | 60 s |
| Current weather | HKO Open Data `rhrread` | 10 min |
| 9-day forecast | HKO Open Data `fnd` | 30 min |

Each feed is cached separately, and a failing feed keeps its last value.
- The screen shows 資料過期 when the warning feeds are more than 10 minutes old.
- It hides the weather after 90 minutes and the forecast after 12 hours.
- The notice refreshes `/api/v1/snapshot` every 30 s.

Icons: `apps/kiosk/public/official/` (see its README). Refresh them with `python3 scripts/fetch_official_icons.py`.

## Site config

`config/sites/demo-site.json`. Copy it, and do not commit real site names.

| Field | Meaning |
|---|---|
| `district`, `weatherStation` | HKO temperature station shown on screen (defaults to `district`, then 香港天文台) |
| `environment` | `outdoor`, `indoor` (no air-conditioning) or `aircon`; the default for every trade |
| `restAdjustMinutes` | Employer's adjustment under LD guidance §5.3–5.5: a multiple of 15, from −30 to +60 |
| `defaultWorkload` | `light`, `moderate`, `heavy` or `very_heavy` |
| `primaryTrades[]` | `labelZh`, `workload`, and optional per-trade `environment` and `adjustMinutes` |

## Local run

Linux / macOS:

```bash
python3 -m venv .venv && .venv/bin/pip install pytest fastapi httpx uvicorn
.venv/bin/python -m uvicorn app.main:app --app-dir services/ingest --host 127.0.0.1 --port 8000
cd apps/kiosk && npm install && npm run dev
```

On Windows, use `.venv/Scripts/python.exe` in place of `.venv/bin/python`.

- http://localhost:5173/ — live fullscreen
- http://localhost:5173/?preview=1 — fixture preview (add `&bar=0` to hide the buttons)
- http://localhost:5173/?gallery=1 — every official icon and signal case

Tests: `.venv/bin/python -m pytest tests -q`. Kiosk type-check and build: `cd apps/kiosk && npm run build`.

## Deploy

```bash
docker compose up --build -d
```

Open http://SERVER_IP/ (live). Do not commit `.env`, origin certificates, or real site names; copy `config/sites/demo-site.json`.
````

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md README.md
git commit -m "docs: official-wording rule, sources, site config and Linux run commands

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Task 19: End-to-end verification and new demo screenshots

**Files:**
- Modify: `docs/demo/*.png` (regenerated)

- [ ] **Step 1: Full backend suite**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `131 passed`, and no `on_event is deprecated` warning.

- [ ] **Step 2: Kiosk build**

Run: `cd apps/kiosk && npm run build && cd -`
Expected: `✓ built in …`

- [ ] **Step 3: Start both servers (keep them running)**

Run the backend in one terminal and the frontend in another:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir services/ingest --host 127.0.0.1 --port 8000
```

```bash
cd apps/kiosk && npm run dev
```

- [ ] **Step 4: Check the live snapshot**

Run: `curl -s http://127.0.0.1:8000/api/v1/snapshot | python3 -m json.tool | head -40`
Expected: `"stale": false`, a `display.mode`, and non-null `weather` and `forecast` (the HKO feeds are live).

- [ ] **Step 5: Render every key case in both orientations**

```bash
mkdir -p /tmp/gate-shots
for c in none amber-new amber-tc3 red black tc8ne-new rain-black pre8 landslip thunderstorm rain-amber-tc3 trades-indoor weather-old; do
  google-chrome --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=8000 --window-size=1920,1080 --screenshot=/tmp/gate-shots/$c-l.png "http://localhost:5173/?preview=1&bar=0&fixture=$c"
  google-chrome --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=8000 --window-size=1080,1920 --screenshot=/tmp/gate-shots/$c-p.png "http://localhost:5173/?preview=1&bar=0&fixture=$c"
done
ls /tmp/gate-shots | wc -l
```

Expected: `26`. Open every image and check it against the spec mockups (`docs/superpowers/specs/2026-10-06-gate-screen-upgrade/landscape.png`, `portrait.png`):
- Nothing is clipped or overlapping, and the main icon and instruction are centred.
- Warning icons in the bar are larger than the weather and forecast icons.
- `amber-new` and `tc8ne-new` show the 最新 banner; `none` and `red` don't.
- `red` shows a solid 暫停工作 tile first; `trades-indoor` shows 休息 45 / 休息 30 / 休息 10 (每 2 小時).
- `pre8` shows the official T3 icon with 分批離開工作地點.
- `thunderstorm`, `amber-tc3` and `rain-amber-tc3` show 主管注意 lines, and nothing overlaps the bottom bar (the main icon shrinks when supervisor lines are present).
- `weather-old` has no weather block but still shows the forecast and clock.
- Every Chinese instruction matches `config/display_actions.json` exactly.

Fix any layout problem in `apps/kiosk/src/kiosk.css`, then re-render before continuing.

- [ ] **Step 6: Regenerate the README demo screenshots**

```bash
shot() { google-chrome --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=8000 --window-size=$2 --screenshot=docs/demo/$1.png "http://localhost:5173/$3"; }
shot live-16x9 1920,1080 "?preview=1&bar=0&fixture=none"
shot live-9x16 1080,1920 "?preview=1&bar=0&fixture=none"
shot amber 1920,1080 "?preview=1&bar=0&fixture=amber"
shot amber-9x16 1080,1920 "?preview=1&bar=0&fixture=amber"
shot red 1920,1080 "?preview=1&bar=0&fixture=red"
shot black 1920,1080 "?preview=1&bar=0&fixture=black"
shot tc8 1920,1080 "?preview=1&bar=0&fixture=tc8ne"
shot pre8 1920,1080 "?preview=1&bar=0&fixture=pre8"
shot rain-black 1920,1080 "?preview=1&bar=0&fixture=rain-black"
shot preview 1920,1080 "?preview=1&fixture=none"
shot gallery 1920,1080 "?gallery=1"
```

Open `docs/demo/live-16x9.png`, `amber.png`, `tc8.png` and `live-9x16.png` and confirm they show the new design.

- [ ] **Step 7: Stop the servers and commit**

```bash
git add docs/demo
git commit -m "docs: demo screenshots of the upgraded gate screen

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Finish the branch**

Use superpowers:finishing-a-development-branch. Do not push or deploy without the owner's go-ahead. Deploy order once approved: ingest first, then web (the snapshot is backward-compatible).

---

## Spec coverage map

| Spec section | Task |
|---|---|
| §3.1 #1 zero rest → baseline | 3, 7 |
| §3.1 #2 中等勞動 | 1 |
| §3.1 #3 Pre-8 official name | 1 |
| §3.1 #4 banner ignores hourly updates | 8, 11 |
| §3.1 #5 indoor work | 2, 3 |
| §3.1 #6 per-trade adjustments | 3, 4 |
| §3.1 #7 unacclimatised note | 5, 13 |
| §3.1 #8–13 official instruction wording | 5 |
| §3.1 #14–15 supervisor line | 5, 12, 13 |
| §3.1 #16 Black rain over Signal 8 | 12, 13 |
| §4.1 layout, sizes, font, tones | 16 |
| §4.2 states and precedence | 12, 13 |
| §4.3 normal state | 7, 13 |
| §4.4 weather state, Pre-8 hero | 5, 13 |
| §4.5 supervisor line | 12, 13, 16 |
| §4.6 heat tiles | 3, 7, 13, 16 |
| §4.7 change banner | 8, 9, 11, 13, 16 |
| §4.8 weather and forecast | 10, 13, 16 |
| §4.9 official icons | 6 |
| §5.1 feeds and caching, lifespan | 14 |
| §5.2 config changes and validation | 2, 4, 5, 6 |
| §5.3 snapshot additions | 13 |
| §5.4 frontend and preview cases | 15, 16 |
| §5.5 docs | 6, 13, 18 |
| §6 failure handling | 4, 10, 11, 14 |
| §7 testing (pytest, CI, guard, visual) | every task, 17, 19 |
| §8 rollout | 19 |
