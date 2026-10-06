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
