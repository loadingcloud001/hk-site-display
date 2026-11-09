"""Check that the official sources behind the screen's wording still say what we quote.

Run from the repo root. The PDFs need pypdf with AES support: pip install "pypdf[crypto]" fonttools
    python3 scripts/check_official_sources.py                 check every source; exit 1 on any problem
    python3 scripts/check_official_sources.py --update-lock   record the Labour Department PDFs as verified

Every source in config/display_actions.json is downloaded again, and every quote that cites it (weather,
supervisor and notes, their English, and the English rest wording) must still be in it word for word.
Only whitespace, list bullets at the start of a line, the punctuation variants ︰ : , ; ( ) against their
full-width forms, and PDF glyph artifacts (⾏ for 行, full-width digits) are ignored.

The Labour Department PDFs are also compared with config/official_sources_lock.json. A changed PDF fails the
check even when every quote still matches, because its rest tables (config/rest_schedule.json) are not
quotes and only a person can compare them (spec §9). After that re-check, run --update-lock.
"""
import argparse
import hashlib
import html
import http.client
import io
import json
import logging
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple, Optional
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ROOT / "config" / "display_actions.json"
LOCK = ROOT / "config" / "official_sources_lock.json"
SPEC = "spec §9, docs/superpowers/specs/2026-10-06-gate-screen-upgrade-design.md"
USER_AGENT = "hk-site-display official-source check (+https://github.com/loadingcloud001/hk-site-display)"
TIMEOUT_SEC = 60
RETRY_WAIT_SEC = (5, 15)  # two retries
HKT = timezone(timedelta(hours=8))
# Every section of config/display_actions.json that holds wording shown on screen (as in services/ingest/app/actions.py).
SECTIONS = ("weather", "supervisor", "notes", "rest")
UPDATE_LOCK = "python3 scripts/check_official_sources.py --update-lock"
LOCK_NOTE = (
    "Labour Department PDFs as last verified by a person (spec §9). "
    f"After re-verifying a changed PDF, run: {UPDATE_LOCK}"
)
# What a person compares when a Labour Department PDF changes (spec §9, item 1).
REVERIFY = {
    "ld-gn-heat": "its edition, App. 1, App. 4, App. 4(a), §4.7.1, §5.4.4, §5.5.4 and App. 6 against "
    "config/rest_schedule.json and config/display_actions.json",
    "ld-cop-weather": "its edition, App. 2 (what to do under each warning) and Ch. 3 復工安排的安全要點 (c) 保持警覺 "
    "against config/display_actions.json",
    "ld-gn-heat-en": "its edition, App. 1, App. 4, App. 4(a), §4.7.1, §5.4.4 and §5.5.4 against "
    "config/rest_schedule.json and the English in config/display_actions.json",
    "ld-cop-weather-en": "its edition, App. 2 (what to do under each warning) and Ch. 3 (c) Remain vigilant against "
    "the English in config/display_actions.json",
}
REVERIFY_OTHER = "the whole document against config/display_actions.json and config/rest_schedule.json"

# List markers that start a line in extracted PDF text ("…期間︰\n- 停止操作吊船…"); the quotes leave them out.
_BULLET = re.compile(r"(?m)^[ \t 　]*[-‐‑–•●▪■◆◦・][ \t 　]*")
# Kangxi radicals and CJK compatibility ideographs that some PDFs emit for ordinary characters (⾏ for 行).
_CJK_LOOKALIKE = re.compile("[⼀-⿟豈-﫿\U0002f800-\U0002fa1f]")
_PUNCT = str.maketrans({"︰": "：", ":": "：", ",": "，", ";": "；", "(": "（", ")": "）"})
_FULLWIDTH = {
    **{0xFF10 + i: 0x30 + i for i in range(10)},
    **{0xFF21 + i: 0x41 + i for i in range(26)},
    **{0xFF41 + i: 0x61 + i for i in range(26)},
}


class Doc(NamedTuple):
    body: bytes
    last_modified: Optional[str] = None
    charset: Optional[str] = None


def normalise(text):
    """The text as compared: no whitespace or line-leading bullets, one form of each punctuation mark."""
    text = _BULLET.sub("", text or "")
    text = _CJK_LOOKALIKE.sub(lambda m: unicodedata.normalize("NFKC", m.group()), text)
    text = re.sub(r"\s+", "", text)
    return text.translate(_PUNCT).translate(_FULLWIDTH)


def kind_of(url):
    """'pdf' or 'html', from the URL's file name; None when the URL does not say."""
    path = urlsplit(url or "").path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith((".htm", ".html", "/")):
        return "html"
    return None


def fetch(url):
    """Download `url`, retrying twice on network and server errors."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(len(RETRY_WAIT_SEC) + 1):
        last = attempt == len(RETRY_WAIT_SEC)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as resp:
                return Doc(resp.read(), resp.headers.get("Last-Modified"), resp.headers.get_content_charset())
        except urllib.error.HTTPError as err:
            if err.code < 500 or last:
                raise
        except (OSError, http.client.HTTPException):
            if last:
                raise
        time.sleep(RETRY_WAIT_SEC[attempt])


def html_text(body, charset=None):
    """The visible text of a web page: no scripts, styles, comments or tags; entities decoded."""
    raw = body.decode(charset or "utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|noscript|template)\b.*?</\1\s*>", " ", raw)
    raw = re.sub(r"(?s)<!--.*?-->", " ", raw)
    raw = re.sub(r"(?s)<[^>]*>", " ", raw)
    return html.unescape(raw)


def pdf_text(body):
    """The text of every page of a PDF."""
    from pypdf import PdfReader  # imported here so the tests and the service never need pypdf

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(io.BytesIO(body))
    if reader.is_encrypted:
        reader.decrypt("")  # the Labour Department sets an owner password only
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def cited_quotes(actions):
    """(where, quote) for every quote in the file: each entry's Chinese quotes, then its English ones."""
    out = []
    for section in SECTIONS:
        for name, spec in (actions.get(section) or {}).items():
            if not isinstance(spec, dict):
                continue  # notes such as rest._note
            out += [(f"{section}.{name}", quote) for quote in spec.get("quotes") or []]
            english = spec.get("en")
            if isinstance(english, dict):
                out += [(f"{section}.{name}.en", quote) for quote in english.get("quotes") or []]
    return out


def quotes_by_source(actions):
    """source key -> [(quote, [where, ...])], each distinct quote once, in file order."""
    out = {}
    for where, quote in cited_quotes(actions):
        texts = out.setdefault(quote.get("source"), {})
        texts.setdefault(quote.get("text") or "", []).append(where)
    return {key: list(texts.items()) for key, texts in out.items()}


def find_quote(doc, quote):
    """(found, hint) for a quote in normalised source text; the hint shows where the source stops matching."""
    want = normalise(quote)
    if want and want in doc:
        return True, None
    lo, hi = 0, len(want)
    while lo < hi:  # the longest beginning of the quote that the source still has
        mid = (lo + hi + 1) // 2
        if want[:mid] in doc:
            lo = mid
        else:
            hi = mid - 1
    if lo < 4:
        return False, "not in the source at all"
    at = doc.find(want[:lo])
    return False, (
        f"matches up to 「…{want[max(0, lo - 12):lo]}」, then the quote has 「{want[lo:lo + 16]}」 "
        f"and the source has 「{doc[at + lo:at + lo + 16]}」"
    )


def compare_lock(key, current, entry):
    """(ok, message) for a downloaded PDF (`current`: url, sha256, size, lastModified) against its lock entry."""
    what = REVERIFY.get(key, REVERIFY_OTHER)
    if not entry:
        return False, f"has no entry in config/{LOCK.name}. Re-check {what} ({SPEC}), then run: {UPDATE_LOCK}"
    checked = entry.get("checked") or "an unknown date"
    if entry.get("url") != current["url"]:
        return False, (
            f"moved from {entry.get('url')} since it was verified on {checked}. "
            f"Re-check {what} ({SPEC}), then run: {UPDATE_LOCK}"
        )
    if entry.get("sha256") != current["sha256"]:
        return False, (
            f"changed since it was verified on {checked} "
            f"(Last-Modified {entry.get('lastModified')} -> {current.get('lastModified')}; "
            f"{entry.get('size')} -> {current.get('size')} bytes; "
            f"sha256 {str(entry.get('sha256'))[:12]}… -> {current['sha256'][:12]}…). "
            f"Re-check {what} ({SPEC}), update sources.{key}.checked in config/display_actions.json, "
            f"then run: {UPDATE_LOCK}"
        )
    return True, f"unchanged since it was verified on {checked}"


def check_source(key, source, quotes, entry, compare, get, read_pdf):
    """Download one source and check its quotes, and for a PDF its lock entry."""
    url = source.get("url") or ""
    result = {
        "key": key,
        "title": source.get("titleZh") or source.get("titleEn") or key,
        "edition": source.get("edition") or "",
        "url": url,
        "kind": kind_of(url),
        "error": None,
        "quotes": [],
        "file": None,
        "current": None,
    }
    try:
        doc = get(url)
    except Exception as err:  # report it and carry on with the other sources
        result["error"] = f"download failed: {err}"
        return result
    is_pdf = doc.body[:5] == b"%PDF-"
    if result["kind"] == "pdf" and not is_pdf:
        result["error"] = "expected a PDF but got something else (moved or removed?)"
        return result
    result["kind"] = "pdf" if is_pdf else "html"
    try:
        text = read_pdf(doc.body) if is_pdf else html_text(doc.body, doc.charset)
    except Exception as err:
        result["error"] = f"could not read the {result['kind'].upper()}: {err}"
        return result
    plain = normalise(text)
    for quote, where in quotes:
        found, hint = find_quote(plain, quote)
        result["quotes"].append({"text": quote, "where": where, "ok": found, "hint": hint})
    if is_pdf:
        result["current"] = {
            "url": url,
            "sha256": hashlib.sha256(doc.body).hexdigest(),
            "size": len(doc.body),
            "lastModified": doc.last_modified,
        }
        if compare:
            ok, message = compare_lock(key, result["current"], entry)
            result["file"] = {"ok": ok, "message": message}
    return result


def run(actions, lock, compare=True, get=None, read_pdf=None):
    """Check every source. Returns (results, quoted source keys that are missing from `sources`)."""
    get = get or fetch
    read_pdf = read_pdf or pdf_text
    cited = quotes_by_source(actions)
    sources = actions.get("sources") or {}
    results = [
        check_source(key, source, cited.get(key, []), lock.get(key), compare, get, read_pdf)
        for key, source in sources.items()
    ]
    return results, sorted(str(key) for key in cited if key not in sources)


def problems(results, unknown):
    """Every problem, one line each."""
    out = [f"a quote cites {key!r}, which is not in sources" for key in unknown]
    for r in results:
        if r["error"]:
            out.append(f"{r['key']}: {r['error']}")
        for q in r["quotes"]:
            if not q["ok"]:
                out.append(f"{r['key']}: {', '.join(q['where'])} no longer matches the source ({q['hint']})")
        if r["file"] and not r["file"]["ok"]:
            out.append(f"{r['key']}: the PDF {r['file']['message']}")
    return out


def _short(text, width=26):
    return text if len(text) <= width else text[:width] + "…"


def report(results, unknown, now, compared=True):
    """The plain-text report printed to the console."""
    lines = [f"Official sources in config/display_actions.json, checked {now:%Y-%m-%d %H:%M} Hong Kong time", ""]
    for r in results:
        lines.append(f"{r['key']}  {r['title']}  {r['edition']}".rstrip())
        lines.append(f"  {r['url']}")
        if r["error"]:
            lines += [f"  FAIL  {r['error']}", ""]
            continue
        if r["current"]:
            modified = r["current"]["lastModified"] or "not given"
            lines.append(f"  PDF, {r['current']['size']} bytes, Last-Modified {modified}")
        if r["file"]:
            lines.append(f"  {'ok  ' if r['file']['ok'] else 'FAIL'}  file {r['file']['message']}")
        for q in r["quotes"]:
            lines.append(f"  {'ok  ' if q['ok'] else 'FAIL'}  {', '.join(q['where'])}  {_short(q['text'])}")
            if not q["ok"]:
                lines.append(f"        {q['hint']}")
        if not r["quotes"]:
            lines.append("  (no quote cites this source)")
        lines.append("")
    lines += [f"FAIL  a quote cites {key!r}, which is not in sources" for key in unknown]
    found = problems(results, unknown)
    count = sum(len(r["quotes"]) for r in results)
    if not found:
        files = "Labour Department PDFs unchanged." if compared else "PDF files not compared (updating the lock)."
        lines.append(f"All {len(results)} sources downloaded and all {count} quotes found. {files}")
        return "\n".join(lines)
    lines += [f"{len(found)} problem(s). What to do:"]
    if any(not q["ok"] for r in results for q in r["quotes"]):
        lines.append(
            "- A quote no longer matches: re-read the source, then update the quote and the wording shown on the "
            "screen in config/display_actions.json (tests/test_display_actions.py keeps them consistent) "
            "and sources.<key>.checked."
        )
    if any(r["file"] and not r["file"]["ok"] for r in results):
        lines.append(f"- A PDF changed: re-check it as listed above, then run: {UPDATE_LOCK}")
    if unknown or any(r["error"] for r in results):
        lines.append("- A download failed: open the URL; if the document moved, update sources.<key>.url.")
    return "\n".join(lines)


def summary_markdown(results, unknown):
    """The same result as a Markdown table, for the GitHub Actions job summary."""
    rows = ["## Official sources", "", "| Source | Document | Quotes | PDF file | Result |", "|---|---|---|---|---|"]
    for r in results:
        found = sum(q["ok"] for q in r["quotes"])
        quotes = "download failed" if r["error"] else (f"{found}/{len(r['quotes'])} found" if r["quotes"] else "—")
        file = "—" if not r["file"] else ("unchanged" if r["file"]["ok"] else "**changed**")
        ok = not r["error"] and found == len(r["quotes"]) and (not r["file"] or r["file"]["ok"])
        rows.append(f"| [{r['key']}]({r['url']}) | {r['title']} | {quotes} | {file} | {'✅' if ok else '❌'} |")
    found = problems(results, unknown)
    if found:
        rows += ["", "### Problems", ""] + [f"- {p}" for p in found]
    return "\n".join(rows) + "\n"


def _display(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the official sources behind the screen's wording.")
    parser.add_argument(
        "--update-lock",
        action="store_true",
        help="record the Labour Department PDFs as verified, after a person has re-checked them (spec §9)",
    )
    parser.add_argument(
        "--checked",
        metavar="YYYY-MM-DD",
        type=date.fromisoformat,
        help="verification date to record with --update-lock (default: today in Hong Kong)",
    )
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    actions = json.loads(ACTIONS.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    now = datetime.now(HKT)
    results, unknown = run(actions, lock, compare=not args.update_lock)
    print(report(results, unknown, now, compared=not args.update_lock))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(results, unknown))
    if args.update_lock:
        pdfs = [r for r in results if r["kind"] == "pdf"]
        blocked = problems(pdfs, [])
        if blocked or any(r["current"] is None for r in pdfs):
            print(f"\n{_display(LOCK)} not written: fix the PDF problems above first.")
            return 1
        checked = (args.checked or now.date()).isoformat()
        new_lock = {"_note": LOCK_NOTE}
        for r in pdfs:
            new_lock[r["key"]] = {**r["current"], "checked": checked}
        LOCK.write_text(json.dumps(new_lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {_display(LOCK)}: {len(pdfs)} PDF(s), verified {checked}")
    return 1 if problems(results, unknown) else 0


if __name__ == "__main__":
    sys.exit(main())
