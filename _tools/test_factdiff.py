"""factdiff.py tests, no network (`python3 _tools/tests.py -k factdiff`).

TestUnits     document units (headings, sentences, list items, table rows, code lines) and sentence normalization.
TestAnchors   locating a fact's backing passage: a paraphrase is found, a window of sentences is used when the fact
              condenses two, an unrelated fact is left unlocated, a number decides between two sentences, statuses for
              failed fetches; quotes only from copy and quote sources.
TestCheckRule check.py rejects malformed _anchors.csv rows (on a throwaway copy of the kb).
"""
import os, shutil, subprocess, sys

import pytest

import factdiff as F
import kbcommon
from conftest import P, copy_kb

DOC = """# Win32 apps

## Size limits

Intune supports Win32 app packages up to 30 GB in size. The upload uses chunks of 6 MB.

- The content prep tool wraps the installer into an `.intunewin` file.
- Detection rules decide whether the app is installed.

| Setting | Default |
| --- | --- |
| Restart behavior | Determine behavior based on return codes |

## Delivery

Delivery Optimization downloads the content in the background. Clients cache it for 24 hours.

```powershell
IntuneWinAppUtil.exe -c <folder> -s setup.exe -o <out>
```
"""


class TestUnits:
    def test_units_and_headings(self):
        u = F.units(DOC)
        texts = [t for _, t in u]
        assert "Intune supports Win32 app packages up to 30 GB in size." in texts
        assert "The upload uses chunks of 6 MB." in texts
        assert "The content prep tool wraps the installer into an `.intunewin` file." in texts
        assert "Restart behavior | Determine behavior based on return codes" in texts
        assert not any(set(t) <= set("-| :") for t in texts), "table separator rows are not units"
        assert ("Win32 apps > Delivery", "IntuneWinAppUtil.exe -c <folder> -s setup.exe -o <out>") in u
        assert dict((t, h) for h, t in u)["Clients cache it for 24 hours."] == "Win32 apps > Delivery"

    def test_norm_ignores_markup_quotes_and_spacing(self):
        assert F.sha("The **tool** wraps  `x`.") == F.sha("the tool wraps x")
        assert F.sha("It’s on") == F.sha("It's on")
        assert F.sha("30 GB") != F.sha("8 GB")

    def test_fact_text_drops_tags_and_snippet_notes(self):
        assert F.fact_text("Win32 apps up to 30 GB. [DOC S123]") == "Win32 apps up to 30 GB."
        assert F.fact_text("SNIPPET: wrap an app; context: Windows 11; checked: no [DER S1: x]") == "wrap an app"


class TestAnchors:
    doc = F.Doc(DOC)

    def test_paraphrase_is_located(self):
        win, cover, shared = self.doc.locate("Win32 app packages can be as large as 30 GB in Intune.")
        assert win is not None and "30 GB" in self.doc.window(*win), (cover, shared)

    def test_number_picks_the_sentence(self):
        win, _, _ = self.doc.locate("Clients keep Delivery Optimization content cached for 24 hours.")
        assert win is not None and "24 hours" in self.doc.window(*win)

    def test_unrelated_fact_is_not_located(self):
        win, cover, _ = self.doc.locate("Kerberos armoring requires Windows Server 2012 domain controllers.")
        assert win is None and cover < F.MIN_COVER

    def test_anchor_rows_statuses_and_quotes(self):
        facts = [("a" * 12, "intune/win32.md", 3, "Win32 app packages may be up to 30 GB. [DOC S1]"),
                 ("b" * 12, "intune/win32.md", 4, "Kerberos armoring needs new domain controllers. [DOC S1]")]
        ok = {"status": 200, "text": DOC, "error": ""}
        rows = F.anchor_rows("S1", facts, ok, "copy", "2031-01-02")
        assert rows[0]["status"] == "located" and len(rows[0]["sha"]) == 16 and rows[0]["terms"]
        assert rows[0]["quote"] and len(rows[0]["quote"].split()) <= F.QUOTE_WORDS
        assert rows[1]["status"] == "unlocated:no-match" and not rows[1]["sha"]
        assert F.anchor_rows("S1", facts, ok, "paraphrase", "2031-01-02")[0]["quote"] == ""
        assert F.anchor_rows("S1", facts, {"status": 404, "text": None, "error": ""}, "copy", "d")[0]["status"] == "unlocated:gone"
        assert F.anchor_rows("S1", facts, {"status": 0, "text": None, "error": "URLError"}, "copy", "d")[0]["status"] == "unlocated:fetch-error"
        assert F.anchor_rows("S1", facts, {"status": 200, "text": None, "error": ""}, "copy", "d")[0]["status"] == "unlocated:not-text"

    def test_located_sha_is_found_again_in_the_same_text(self):
        rows = F.anchor_rows("S1", [("a" * 12, "x.md", 1, "Win32 app packages may be up to 30 GB. [DOC S1]")],
                             {"status": 200, "text": DOC, "error": ""}, "quote", "d")
        assert rows[0]["sha"] in F.Doc(DOC).shas
        assert rows[0]["sha"] in F.Doc(DOC.replace("Intune supports", "Intune   supports")).shas, "spacing is not a change"
        assert rows[0]["sha"] not in F.Doc(DOC.replace("30 GB", "8 GB")).shas


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = copy_kb(str(tmp_path_factory.mktemp("kb-anchors") / "kb"), skip=("_census",))
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestCheckRule:
    def check(self, kb, rows):
        kbcommon.write_csv(os.path.join(kb, P(kbcommon.ANCHORS)), kbcommon.ANCHOR_COLS, rows)
        p = subprocess.run([sys.executable, os.path.join(kb, "_tools", "check.py"), "--root", "public"], capture_output=True, text=True)
        return p.returncode, p.stdout

    def test_rule(self, kb):
        with open(os.path.join(kb, P("_sources.csv")), encoding="utf-8") as f:
            import csv
            srcs = {r["id"]: r["reuse"] for r in csv.DictReader(f)}
        copy_id = next(i for i, r in srcs.items() if r == "copy")
        para_id = next(i for i, r in srcs.items() if r == "paraphrase")
        path = "intune/win32-apps.md" if os.path.exists(os.path.join(kb, P("intune/win32-apps.md"))) else \
            next(p for p in ("auth/kerberos.md",) if os.path.exists(os.path.join(kb, P(p))))
        good = {"fact": "0123456789ab", "path": path, "source_id": copy_id, "status": "located", "heading": "A > B",
                "terms": "win32;size", "sha": "0123456789abcdef", "quote": "a short quote", "verified_utc": "2031-01-02"}
        code, out = self.check(kb, [good, {**good, "fact": "0123456789ac", "status": "unlocated:no-match", "terms": "",
                                                  "sha": "", "quote": ""}])
        assert code == 0, out
        bad = [
            ({**good, "fact": "xyz"}, "12-hex"),
            ({**good, "sha": "abc"}, "16-hex sha"),
            ({**good, "status": "found"}, "status"),
            ({**good, "status": "unlocated:no-match"}, "no sha, terms or quote"),
            ({**good, "source_id": para_id}, "only copy or quote"),
            ({**good, "quote": " ".join(["w"] * 26)}, "over 25 words"),
            ({**good, "path": "no/such.md"}, "no file"),
            ({**good, "verified_utc": "yesterday"}, "YYYY-MM-DD"),
        ]
        for row, want in bad:
            code, out = self.check(kb, [row])
            assert code == 1 and want in out, (want, out)
        code, out = self.check(kb, [good, good])
        assert code == 1 and "duplicate" in out
        os.remove(os.path.join(kb, P(kbcommon.ANCHORS)))


class TestDetect:
    """detect_source on canned provider answers; resolve per fact; similarity helpers."""

    @pytest.fixture(autouse=True)
    def cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(F, "CACHE", str(tmp_path / "cache"))
        monkeypatch.setattr(F, "ROOT", kbcommon.public())
        F._madeup.clear()
        F._pages.clear()
        F._added.clear()

    ROWS = [{"provider": "docs", "match": "docs.example.com/", "signals": "etag;version;hash", "version_meta": "git_commit_id",
             "raw_form": "-", "not_found": "hard-404", "search_api": "-", "sitemap": "-"},
            {"provider": "soft", "match": "soft.example.com/", "signals": "hash", "version_meta": "-", "raw_form": "-",
             "not_found": "soft-404", "search_api": "-", "sitemap": "-"}]

    def doc(self, monkeypatch, status=200, text=DOC, version="c2", final=None, hops=()):
        def fake(url, row, etag="", lastmod=""):
            if status == 304 or (etag and etag == '"same"'):
                return {"status": 304, "final": url, "hops": [], "etag": etag, "lastmod": "", "version": {}, "text": None,
                        "sha": "", "bytes": 0, "error": "", "ctype": ""}
            return {"status": status, "final": final or url, "hops": list(hops), "etag": '"e2"', "lastmod": "",
                    "version": {"git_commit_id": version} if version else {}, "text": text if status == 200 else None,
                    "sha": F.sha(text or "") if status == 200 else "", "bytes": len(text or ""), "error": "", "ctype": "text/markdown",
                    "raw": text, "raw_url": url}
        monkeypatch.setattr(F.provider, "document", fake)

    def test_verdicts(self, monkeypatch):
        src = {"id": "S1", "url": "https://docs.example.com/a"}
        self.doc(monkeypatch)
        assert F.detect_source("S1", src, {"etag": '"same"'}, self.ROWS)[0] == "unchanged"
        assert F.detect_source("S1", src, {}, self.ROWS)[0] == "new"
        assert F.detect_source("S1", src, {"version": "c2", "etag": '"e1"'}, self.ROWS)[:2] == ("unchanged", "version")
        v = F.detect_source("S1", src, {"version": "c1", "doc_sha256": "x", "simhash": F.simhash(DOC)}, self.ROWS)
        assert v[0] == "changed" and "c1 -> c2" in v[2]
        self.doc(monkeypatch, status=404)
        assert F.detect_source("S1", src, {}, self.ROWS)[0] == "gone"
        self.doc(monkeypatch, final="https://docs.example.com/b", hops=[(301, "https://docs.example.com/b")])
        assert F.detect_source("S1", src, {"version": "c1"}, self.ROWS)[0] == "moved"
        self.doc(monkeypatch, text="Totally different text about printers and toner cartridges. " * 20, version="c3")
        assert F.detect_source("S1", src, {"version": "c2", "doc_sha256": "x", "simhash": F.simhash(DOC)}, self.ROWS)[0] == "replaced"

    def test_soft_404(self, monkeypatch):
        landing = "Welcome to the site. Search our documentation. Popular pages and news. " * 10
        self.doc(monkeypatch, text=landing, version="")
        monkeypatch.setattr(F, "madeup_text", lambda url: landing)
        assert F.detect_source("S2", {"id": "S2", "url": "https://soft.example.com/p"}, {"doc_sha256": "x"}, self.ROWS)[0] == "soft-404"

    def test_resolve_outcomes(self, monkeypatch):
        facts = [("a" * 12, "x.md", 1, "Win32 app packages may be up to 30 GB. [DOC S1]"),
                 ("b" * 12, "x.md", 2, "Clients cache Delivery Optimization content for 24 hours. [DOC S1]"),
                 ("c" * 12, "x.md", 3, "The upload uses 6 MB chunks. [DOC S1]")]
        rows = F.anchor_rows("S1", facts, {"status": 200, "text": DOC, "error": ""}, "copy", "2031-01-01")
        anchors = {(r["fact"], r["path"], r["source_id"]): r for r in rows}
        anchors[("c" * 12, "x.md", "S1")].update(status="unlocated:no-match", sha="", terms="", quote="")
        new = DOC.replace("Clients cache it for 24 hours.", "Clients cache it for 72 hours.")
        monkeypatch.setattr(F, "search_urls", lambda *a: [])
        monkeypatch.setattr(F, "sitemap_added", lambda *a, **k: [])
        out, found = F.resolve("S1", {"id": "S1", "url": "https://docs.example.com/a"}, "changed",
                               {"text": new}, {"text": DOC}, facts, anchors, self.ROWS)
        got = {r["fact"][0]: r for r in out}
        assert got["a"]["outcome"] == "verbatim"
        assert got["b"]["outcome"] == "modified" and "24 -> 72" in got["b"]["note"], got["b"]
        assert got["c"]["outcome"] == "unanchored"
        # the passage left the page, and a linked page holds it word for word: moved
        gone = DOC.replace("Intune supports Win32 app packages up to 30 GB in size.", "")
        monkeypatch.setattr(F, "linked", lambda *a: ["https://docs.example.com/limits"])
        monkeypatch.setattr(F, "page_doc", lambda url, rows: (F.Doc(DOC), DOC))
        out, _ = F.resolve("S1", {"id": "S1", "url": "https://docs.example.com/a"}, "changed", {"text": gone}, {"text": DOC},
                           facts[:1], anchors, self.ROWS)
        assert out[0]["outcome"] == "moved" and out[0]["target"] == "https://docs.example.com/limits"
        # a dead source whose passage is nowhere: dead
        monkeypatch.setattr(F, "linked", lambda *a: [])
        out, _ = F.resolve("S1", {"id": "S1", "url": "https://docs.example.com/a"}, "gone", None, {"text": DOC}, facts[:1], anchors, self.ROWS)
        assert out[0]["outcome"] == "dead"

    def test_similarity_helpers(self):
        assert F.jaccard("a b c d", "a b c d") == 1.0 and F.jaccard("a b c d", "w x y z") == 0.0
        assert F.simhash_sim(F.simhash(DOC), F.simhash(DOC)) == 1.0
        assert F.unit_sim("Clients cache it for 24 hours.", "Clients cache it for 72 hours.") > F.MODIFIED_MIN
        assert F.best_cut([0.9, 0.95], [0.1, 0.2], [0.5])[1] == 1.0


def test_config_values_are_calibrated():
    import tomllib
    with open(F.CONFIG, "rb") as f:
        cfg = tomllib.load(f)
    assert cfg["anchor"]["min_cover"] == F.MIN_COVER and cfg["resolve"]["modified_min"] == F.MODIFIED_MIN
    assert 0 < F.ZOMBIE_MAX < 1 and 0 < F.SOFT404_MIN <= 1


def test_apply_confirms_unchanged_sources(kb):
    """apply on a log whose source did not change: the source row is confirmed and dated, nothing else moves."""
    import csv
    with open(os.path.join(kb, P("_sources.csv")), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    sid = next(r["id"] for r in rows if r["id"].startswith("S-") and "learn.microsoft.com" in r["url"] and not r["superseded_by"])
    log = os.path.join(kb, "log.csv")
    kbcommon.write_csv(log, F.LOG_COLS, [{"source_id": sid, "url": "u", "verdict": "unchanged", "signal": "etag",
                                          "evidence": "304 Not Modified"}])
    p = subprocess.run([sys.executable, os.path.join(kb, "_tools", "factdiff.py"), "apply", log, "--date", "2031-01-02"],
                       capture_output=True, text=True)
    assert p.returncode == 0 and "sources confirmed=1" in p.stdout, p.stdout + p.stderr
    with open(os.path.join(kb, P("_sources.csv")), encoding="utf-8") as f:
        row = next(r for r in csv.DictReader(f) if r["id"] == sid)
    assert row["retrieved_utc"] == "2031-01-02" and "confirmed 2031-01-02: fact diff: unchanged (etag)" in row["version_or_date"]
