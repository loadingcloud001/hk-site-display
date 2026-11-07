"""Official instruction wording (config/display_actions.json) and the guard that keeps it verbatim."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACTIONS_PATH = ROOT / "config" / "display_actions.json"
# Every section that holds wording shown on screen. scripts/check_official_sources.py checks the same sections.
SECTIONS = ("weather", "supervisor", "notes", "extreme")


def load_actions(path=ACTIONS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _norm(text):
    return re.sub(r"\s+", "", text or "")


def displayed(spec):
    """Everything an entry puts on screen: its main line, its sub lines and its fragments."""
    main = [spec["main"]] if "main" in spec else []
    return [*main, *(spec.get("sub") or []), *(spec.get("fragments") or [])]


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
            if not isinstance(fragment, str) or not _norm(fragment) or not any(_norm(fragment) in t for t in texts):
                errors.append(f"{where}: {fragment!r} is not in the official text")

    for key in actions:
        if key != "sources" and key not in SECTIONS:
            errors.append(f"{key}: unknown section, so its wording would never be checked (add it to SECTIONS)")
    for section in SECTIONS:
        for key, spec in (actions.get(section) or {}).items():
            if section == "weather" and not spec.get("main"):
                errors.append(f"{section}.{key}: no main instruction")
            check(f"{section}.{key}", displayed(spec), spec.get("quotes"))
    extreme = actions.get("extreme")
    if extreme is not None and not ((extreme.get("display") or {}).get("main") and "supervisor" in extreme):
        errors.append("extreme: needs display.main and supervisor")
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


def extreme_wording(actions):
    """The 「極端情況」 lines: the instruction and its sub lines, and the supervisor line."""
    spec = actions["extreme"]
    return {
        "main": spec["display"]["main"],
        "sub": list(spec["display"].get("sub") or []),
        "supervisor": "：".join(spec["supervisor"]["fragments"]),
    }
