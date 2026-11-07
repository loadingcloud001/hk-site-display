"""Offline tests for scripts/check_official_sources.py: no network and no pypdf needed."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("check_official_sources", ROOT / "scripts" / "check_official_sources.py")
cos = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cos)

ACTIONS = json.loads((ROOT / "config" / "display_actions.json").read_text(encoding="utf-8"))
LOCK = json.loads((ROOT / "config" / "official_sources_lock.json").read_text(encoding="utf-8"))

# As pypdf extracts the Code of Practice: spaces inside words, a ︰ and a "-" bullet the quote leaves out.
COP_TEXT = (
    "例 如：\n在黃色或紅色暴雨警告期間︰\n- 停止操作吊船 、 進行斜坡工程 \n 等工作。\n"
    "-  停止操作船舶吊重機械及起卸    \n 貨物。\n在一號或三號信號期間︰\n-  停止操作起重機 、 吊船等 。\n"
)
RAIN_AMBER = "在黃色或紅色暴雨警告期間︰停止操作吊船、進行斜坡工程等工作。"
PDF_BYTES = b"%PDF-1.6 fake Labour Department PDF"
PDF_URL = "https://example.test/guidance.pdf"
PAGE_URL = "https://example.test/advice.htm"


def test_whitespace_is_ignored():
    text = "在空曠地方 工作的人士\n應停止　戶外作業， 並到安全地方暫避。"
    assert cos.normalise(text) == "在空曠地方工作的人士應停止戶外作業，並到安全地方暫避。"


@pytest.mark.parametrize("bullet", ["-", "•", "●", "▪", "■", ""])
def test_line_leading_bullets_are_ignored(bullet):
    text = f"在黃色或紅色暴雨警告期間︰\n{bullet} 停止操作吊船、進行斜坡工程等工作。"
    assert cos.normalise(RAIN_AMBER) in cos.normalise(text)


def test_a_hyphen_inside_a_line_is_kept():
    assert cos.normalise("甲 - 乙") == "甲-乙"


def test_punctuation_variants_compare_equal():
    assert cos.normalise("期間︰停止") == cos.normalise("期間：停止") == cos.normalise("期間:停止")
    assert cos.normalise("甲,乙;丙(丁)") == cos.normalise("甲，乙；丙（丁）")


def test_pdf_glyph_artifacts_compare_equal():
    assert cos.normalise("進⾏斜坡⼯程") == cos.normalise("進行斜坡工程")
    assert cos.normalise("增加１５分鐘") == cos.normalise("增加15分鐘")


def test_quote_is_found_in_extracted_pdf_text():
    assert cos.find_quote(cos.normalise(COP_TEXT), RAIN_AMBER) == (True, None)
    assert cos.find_quote(cos.normalise(COP_TEXT), "在一號或三號信號期間︰停止操作起重機、吊船等。")[0]


def test_changed_wording_is_reported_where_it_stops_matching():
    doc = cos.normalise("切勿外出。如果已經在有遮蔽的地方躲避，就應該繼續留在原處。切勿接觸被風吹倒的電線。")
    found, hint = cos.find_quote(doc, "切勿外出。如果已經在有遮蔽的地方躲避，就應該留在家中。")
    assert found is False
    assert "就應該" in hint and "留在家中" in hint and "繼續留在原處" in hint


def test_a_quote_absent_from_the_source_is_reported():
    assert cos.find_quote(cos.normalise("完全不同的文件"), RAIN_AMBER) == (False, "not in the source at all")
    assert cos.find_quote(cos.normalise(COP_TEXT), "")[0] is False


def test_page_text_drops_scripts_styles_comments_and_tags():
    page = "<p>切勿<b>外出</b>&nbsp;&amp;<!-- 舊文字 --></p><script>var a = '舊';</script><style>p{}</style>"
    assert cos.normalise(cos.html_text(page.encode("utf-8"), "utf-8")) == "切勿外出&"


def _entry(**changes):
    entry = {
        "url": PDF_URL,
        "sha256": "a" * 64,
        "size": 10,
        "lastModified": "Thu, 27 Aug 2026 05:55:00 GMT",
        "checked": "2026-10-06",
    }
    return {**entry, **changes}


def _current(**changes):
    return {key: value for key, value in _entry(**changes).items() if key != "checked"}


def test_unchanged_pdf_passes_the_lock():
    ok, message = cos.compare_lock("ld-gn-heat", _current(), _entry())
    assert ok and "2026-10-06" in message


def test_changed_pdf_fails_with_what_to_recheck():
    ok, message = cos.compare_lock("ld-gn-heat", _current(sha256="b" * 64, size=11), _entry())
    assert not ok
    assert "2026-10-06" in message and "App. 4(a)" in message and "rest_schedule.json" in message
    assert "--update-lock" in message


def test_changed_code_of_practice_names_its_appendix():
    ok, message = cos.compare_lock("ld-cop-weather", _current(sha256="b" * 64), _entry())
    assert not ok and "App. 2" in message


def test_pdf_missing_from_the_lock_fails():
    ok, message = cos.compare_lock("ld-gn-heat", _current(), None)
    assert not ok and "--update-lock" in message


def test_moved_pdf_fails_the_lock():
    ok, message = cos.compare_lock("ld-gn-heat", _current(url="https://example.test/new.pdf"), _entry())
    assert not ok and "moved" in message


def test_document_kind_comes_from_the_url():
    assert cos.kind_of("https://www.labour.gov.hk/tc/public/pdf/wcp/Rainstorm.pdf") == "pdf"
    assert cos.kind_of("https://www.hko.gov.hk/tc/informtc/precaution.htm") == "html"
    assert cos.kind_of("https://example.test/data") is None


def test_every_quote_cites_a_source_the_check_can_fetch():
    cited = cos.quotes_by_source(ACTIONS)
    assert cited and set(cited) <= set(ACTIONS["sources"])
    for key, source in ACTIONS["sources"].items():
        assert cos.kind_of(source["url"]) in ("pdf", "html"), key
    entries = [q for section in cos.SECTIONS for spec in ACTIONS[section].values() for q in spec["quotes"]]
    assert sum(len(where) for quotes in cited.values() for _, where in quotes) == len(entries)


def test_every_pdf_source_is_in_the_lock():
    pdfs = {key: s["url"] for key, s in ACTIONS["sources"].items() if cos.kind_of(s["url"]) == "pdf"}
    assert pdfs
    assert {key for key in LOCK if not key.startswith("_")} == set(pdfs)
    for key, url in pdfs.items():
        entry = LOCK[key]
        assert entry["url"] == url
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
        assert isinstance(entry["size"], int) and entry["size"] > 0
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", entry["checked"])


def _actions(page_quote="切勿外出。"):
    return {
        "sources": {
            "page": {"titleZh": "網頁", "url": PAGE_URL},
            "guide": {"titleZh": "指引", "url": PDF_URL},
        },
        "weather": {"x": {"codes": ["X"], "main": "切勿外出", "quotes": [{"source": "page", "text": page_quote}]}},
        "supervisor": {"y": {"rank": 1, "codes": ["Y"], "fragments": [], "quotes": [{"source": "guide", "text": RAIN_AMBER}]}},
        "notes": {},
    }


def _site(page="<p>切勿外出。</p>", pdf=PDF_BYTES):
    docs = {
        PAGE_URL: cos.Doc(page.encode("utf-8"), None, "utf-8"),
        PDF_URL: cos.Doc(pdf, "Thu, 27 Aug 2026 05:55:00 GMT", None),
    }

    def get(url):
        if url not in docs:
            raise OSError("no route")
        return docs[url]

    return get


def _lock(body=PDF_BYTES):
    return {"guide": _entry(sha256=hashlib.sha256(body).hexdigest(), size=len(body))}


def _check(actions=None, lock=None, get=None):
    results, unknown = cos.run(
        actions or _actions(), _lock() if lock is None else lock, get=get or _site(), read_pdf=lambda body: COP_TEXT
    )
    return cos.problems(results, unknown)


def test_all_good_has_no_problems():
    assert _check() == []


def test_a_changed_pdf_is_a_problem_even_when_its_quotes_match():
    found = _check(lock=_lock(b"%PDF-1.6 the version that was verified"))
    assert len(found) == 1 and "changed since it was verified" in found[0]


def test_a_changed_page_is_a_problem():
    found = _check(get=_site(page="<p>切勿出外。</p>"))
    assert len(found) == 1 and "weather.x" in found[0]


def test_a_failed_download_is_a_problem():
    actions = _actions()
    actions["sources"]["page"]["url"] = "https://example.test/gone.htm"
    found = _check(actions=actions)
    assert len(found) == 1 and "download failed" in found[0]


def test_a_pdf_url_that_returns_a_web_page_is_a_problem():
    found = _check(get=_site(pdf=b"<html>Sorry, the page you requested cannot be found.</html>"))
    assert any("expected a PDF" in p for p in found)


def test_a_quote_citing_an_unknown_source_is_a_problem():
    actions = _actions()
    actions["notes"] = {"n": {"fragments": [], "quotes": [{"source": "blog", "text": "甲"}]}}
    assert any("'blog'" in p for p in _check(actions=actions))


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """main() against the fake documents, with the config files in tmp_path."""
    actions_path, lock_path = tmp_path / "display_actions.json", tmp_path / "official_sources_lock.json"
    actions_path.write_text(json.dumps(_actions(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cos, "ACTIONS", actions_path)
    monkeypatch.setattr(cos, "LOCK", lock_path)
    monkeypatch.setattr(cos, "fetch", _site())
    monkeypatch.setattr(cos, "pdf_text", lambda body: COP_TEXT)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return lock_path


def test_update_lock_records_the_pdfs(offline, capsys):
    assert cos.main(["--update-lock", "--checked", "2026-10-06"]) == 0
    lock = json.loads(offline.read_text(encoding="utf-8"))
    assert lock["guide"] == {**_lock()["guide"], "checked": "2026-10-06"}
    assert set(lock) == {"_note", "guide"}
    assert cos.main([]) == 0
    assert "Labour Department PDFs unchanged" in capsys.readouterr().out


def test_update_lock_refuses_while_a_pdf_quote_is_missing(offline, monkeypatch):
    monkeypatch.setattr(cos, "pdf_text", lambda body: "另一份文件")
    assert cos.main(["--update-lock"]) == 1
    assert not offline.exists()


def test_check_fails_without_a_lock(offline, capsys):
    assert cos.main([]) == 1
    assert "--update-lock" in capsys.readouterr().out


def test_job_summary_is_written_for_github_actions(offline, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert cos.main([]) == 1
    text = summary.read_text(encoding="utf-8")
    assert "| [page](https://example.test/advice.htm) | 網頁 | 1/1 found | — | ✅ |" in text
    assert "### Problems" in text and "guide" in text
