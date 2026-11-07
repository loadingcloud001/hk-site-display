"""Official instruction wording (config/display_actions.json) and the guard that keeps it verbatim.

Chinese and English are checked the same way: every displayed fragment must be a contiguous part of an official
sentence quoted next to it, in the same language. Chinese ignores whitespace (PDF text breaks lines anywhere);
English only treats a run of whitespace as one space, so even a changed word boundary fails. Lines made of
several fragments are joined with ZH_JOIN or EN_JOIN, the only text on the screen that is not quoted.
"""
import json
import re
from pathlib import Path

from app.rest import compute_rest
from app.site import ADJUST_MINUTES, ENVIRONMENTS, WORKLOADS

ROOT = Path(__file__).resolve().parents[3]
ACTIONS_PATH = ROOT / "config" / "display_actions.json"
SCHEDULE_PATH = ROOT / "config" / "rest_schedule.json"
LANGS = ("zh", "en")
ZH_JOIN = "："
EN_JOIN = ": "
HSWW_LEVELS = ("amber", "red", "black")


def load_actions(path=ACTIONS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_schedule(path=SCHEDULE_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _norm(text):
    return re.sub(r"\s+", "", text or "")


def _norm_en(text):
    return re.sub(r"\s+", " ", text or "").strip()


def english_lines(spec):
    """The English lines shown under a weather instruction; [] when no official English sentence exists."""
    return list((spec.get("en") or {}).get("lines") or [])


def english_text(spec):
    """A supervisor line or note in English, or None when no official English sentence exists."""
    fragments = (spec.get("en") or {}).get("fragments") or []
    return EN_JOIN.join(fragments) or None


def tile_lines_en(result, en):
    """Official English for one heat-stress tile (`en` is rest.tile.en): Appendix 4 cells, or para 5.5.4."""
    if result["kind"] == "suspend":
        return [en["suspend"]]
    if result["kind"] == "baseline":
        return [en["baseline"].format(rest=result["rest"], hours=result["perHours"])]
    return [en["rest"].format(rest=result["rest"]), en["work"].format(work=result["work"])]


def normal_lines_en(schedule, workloads, en):
    """Official English for the normal-day rest lines (`en` is rest.normal.en), para 4.7.1.

    Same grouping as heat.normal_rest_lines: one line for one group, `group: rule` for each of two groups.
    """
    base = schedule["baseline"]
    hours = base["perHours"]
    heavy = bool(set(workloads) & {"heavy", "very_heavy"})
    light = bool(set(workloads) & {"light", "moderate"})

    def line(group, rest, labelled):
        label, rule = en[group]
        text = rule.format(rest=rest, hours=hours)
        return f"{label}{EN_JOIN}{text}" if labelled else text

    if heavy and light:
        return [line("heavy", base["very_heavy"], True), line("light", base["light"], True)]
    return [line("heavy", base["very_heavy"], False) if heavy else line("light", base["light"], False)]


def tile_results(schedule):
    """Every tile result the schedule can give: any warning level, workload, environment and site adjustment."""
    out = []
    for level in HSWW_LEVELS:
        for workload in WORKLOADS:
            for environment in ENVIRONMENTS:
                for adjust in ADJUST_MINUTES:
                    result = compute_rest(schedule, environment, level, workload, adjust)
                    if result not in out:
                        out.append(result)
    return out


def _rest_fragments(rest, schedule):
    """(where, fragment) for every English rest fragment the schedule can put on the screen."""
    out = []
    labels = rest["workloads"]["en"]["labels"]
    out += [(f"rest.workloads.{key}", labels[key]) for key in WORKLOADS]
    tile = rest["tile"]["en"]
    for result in tile_results(schedule):
        out += [(f"rest.tile.{result['kind']}", line) for line in tile_lines_en(result, tile)]
    normal = rest["normal"]["en"]
    base = schedule["baseline"]
    for group, workload in (("heavy", "very_heavy"), ("light", "light")):
        label, rule = normal[group]
        out.append((f"rest.normal.{group}", label))
        out.append((f"rest.normal.{group}", rule.format(rest=base[workload], hours=base["perHours"])))
    return out


def fragment_errors(actions, schedule=None):
    """Every displayed fragment must be a contiguous part of one of its official quotes, in its own language."""
    errors = []
    sources = actions.get("sources") or {}
    for key, source in sources.items():
        if source.get("lang") not in LANGS:
            errors.append(f"sources.{key}: lang must be one of {LANGS}")

    def check(where, fragments, quotes, lang):
        norm = _norm_en if lang == "en" else _norm
        if not quotes:
            errors.append(f"{where}: no official quote")
            return
        for quote in quotes:
            source = quote.get("source")
            if source not in sources:
                errors.append(f"{where}: unknown source {source!r}")
            elif sources[source].get("lang") != lang:
                errors.append(f"{where}: source {source!r} is not in {lang!r}")
        texts = [norm(q.get("text")) for q in quotes]
        if not fragments:
            errors.append(f"{where}: nothing to show")
        for fragment in fragments:
            if not isinstance(fragment, str) or not norm(fragment) or not any(norm(fragment) in t for t in texts):
                errors.append(f"{where}: {fragment!r} is not in the official text")

    def check_en(where, spec, key):
        if "en" not in spec:
            errors.append(f"{where}: say what to show in English (\"en\", or null when there is no official English)")
        elif spec["en"] is not None:
            check(f"{where}.en", spec["en"].get(key) or [], spec["en"].get("quotes"), "en")

    for key, spec in (actions.get("weather") or {}).items():
        check(f"weather.{key}", [spec["main"], *spec.get("sub", [])], spec.get("quotes"), "zh")
        check_en(f"weather.{key}", spec, "lines")
    for key, spec in (actions.get("supervisor") or {}).items():
        check(f"supervisor.{key}", spec.get("fragments") or [], spec.get("quotes"), "zh")
        check_en(f"supervisor.{key}", spec, "fragments")
    for key, spec in (actions.get("notes") or {}).items():
        check(f"notes.{key}", spec.get("fragments") or [], spec.get("quotes"), "zh")
        check_en(f"notes.{key}", spec, "fragments")

    rest = actions.get("rest")
    if rest is not None:
        try:
            fragments = _rest_fragments(rest, schedule or load_schedule())
        except (KeyError, IndexError, TypeError, ValueError) as error:
            errors.append(f"rest: incomplete or malformed ({error!r})")
        else:
            # Each part is checked against its own quotes: a tile cell must come from Appendix 4 or para 5.5.4.
            for where, fragment in fragments:
                section = where.split(".")[1]
                check(where, [fragment], rest[section]["en"].get("quotes"), "en")
    return errors


def validate_actions(actions, schedule=None):
    errors = fragment_errors(actions, schedule)
    if errors:
        raise ValueError("display_actions.json: " + "; ".join(dict.fromkeys(errors)))
    return actions


def weather_by_code(actions):
    out = {}
    for spec in (actions.get("weather") or {}).values():
        for code in spec["codes"]:
            out[code] = spec
    return out


def note_text(actions, key):
    return ZH_JOIN.join(actions["notes"][key]["fragments"])


def note_text_en(actions, key):
    return english_text(actions["notes"][key])
