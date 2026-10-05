"""Query log tests, learn (kb/_self/querylog.md, Learn; `python3 _tools/tests.py -k TestLearn`, and the other
classes below).

  TestLearn         the fixture store (_tools/fixtures/querylog/store/) gives findings of each kind with pack on
                    HEAD: eval, alias, expansion, gap candidate and source; every judged miss is re-run first
                    (`fixed-since` when it passes); learn writes findings only; two runs on the same store and HEAD
                    give byte-identical files, also in another copy; a HEAD change writes one new file
  TestLearnFalseNone a none entry whose fetched pages a source row holds (host and path, without scheme, www, query,
                    fragment, trailing slash, `.md` or Learn's locale segment) is an eval finding at stage miss whose
                    `expect` is the article with the most citing lines (ties by path) and `observed` the source ids,
                    in place of a gap; planted: a page no article cites, a weak verdict, a failed fetch, no fetch
                    (the findings they give now); fixed-since once the pack answers; a second learn writes nothing;
                    a kb_ask.py run routed web or split keeps on its row the ids of the kb sources its researcher's
                    answer names (never urls or text), distill carries them into the entry, learn reads them like
                    fetched pages (planted: an uncited source, an answer with no kb url, junk ids, an error result)
  TestSourceFindings  the staging triggers equal web-sources.md (planted: a changed number in the doc or the code); a
                    host's level comes from the provider registry (a root's _providers.csv too), else the routes
                    table, and every registry host has a routes row, in the planted pair and the clone's own
                    (planted: a row without one); no stage finding for a host with the needed level; source findings
                    read the registry and the routes table; the staging tests read a registry and a routes table they
                    plant, so rows the clone gains for their hosts change no result (planted: the same rows unplanted
                    turn them red)
  TestFindingsGates the findings gates of `check`, each with a planted failure
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The helpers the classes share are in
ql_testkit.py.
"""
import json, shutil, subprocess, sys
from pathlib import Path

import pytest

import ql_distill, ql_learn, ql_store
from conftest import KB, querylog_env, TOOLS
from ql_testkit import (by_id, failing, findings, FN, jsonl, LAPS, learn_store, none_entry, passing, plant_entries,
                        planted_staging, QL, run_learn, tree)
from ql_testkit import staging_planted  # noqa: F401  (autouse: the planted registry and routes table)


MISS = {f"55555555-0000-4000-8000-0000000000{n}" for n in ("a1", "a2", "a3", "a4")}
ANSWERED = "55555555-0000-4000-8000-0000000000a5"


UNSTAGED = "docs.unstaged.example.com"  # a level-0 host of the fixture store, as arxiv.org is


# ---------------------------------------------------------------- the real registry and routes table

REAL_REGISTRY = Path(TOOLS) / "providers.csv"  # the clone's registry and routes table: only the tests of the real
REAL_WEB_SOURCES = ql_learn.WEB_SOURCES  # data itself read them (test_triggers_match_web_sources, ..._agree)


@pytest.fixture(scope="module")
def head_pack():
    """pack on HEAD (the clone's kb), each question once for the module."""
    seen = {}

    def pack(q):
        if q not in seen:
            seen[q] = ql_learn.default_pack(q)
        return seen[q]
    return pack


class TestLearn:
    def test_the_fixture_gives_findings_of_each_kind(self, tmp_path, head_pack):
        store = learn_store(tmp_path)
        rc, said = run_learn(store, head_pack)
        assert rc == 0 and said[0].startswith("learn: run=20260928T130000Z-") and "findings=9" in said[0], said
        ((f, recs),) = findings(store)
        assert f.parent.name == "2026-09" and f.parent.parent.name == "findings"
        kinds = {(r["kind"], r.get("entry", r.get("host"))): r for r in recs}
        assert {k for k, _ in kinds} == set(ql_store.FINDING_KINDS)

        def e(n):
            return f"55555555-0000-4000-8000-0000000000{n}"
        fixed = kinds[("eval", e("a1"))]  # judged missed, but the pack on HEAD now finds the LAPS article
        assert (fixed["state"], fixed["expect"], fixed["observed"]["verdict"]) == ("fixed-since", LAPS, "good")
        assert ("alias", e("a1")) not in kinds and ("expansion", e("a1")) not in kinds
        assert kinds[("eval", e("a2"))]["state"] == "open"
        assert kinds[("alias", e("a2"))]["terms"] == ["zqxlapsor", "plomkinator"]  # words the kb never holds
        assert kinds[("eval", e("a3"))]["state"] == "open"
        assert kinds[("expansion", e("a3"))]["article"] == "public/intune/win32-apps.md"  # every word known
        gap = kinds[("gap", e("a4"))]
        assert (gap["stage"], gap["promotions"]) == ("candidate-gap", [{"from": "miss", "to": "candidate-gap",
                                                                        "by": "learn"}])
        assert all(r["stage"] == "miss" for r in recs if r["kind"] in ("eval", "alias", "expansion"))
        assert not any(r.get("entry") == ANSWERED for r in recs)  # an answered lookup is no miss
        src = {(r["signal"], r["host"]): r for r in recs if r["kind"] == "source"}
        assert set(src) == {("stage", UNSTAGED), ("stage", "arxiv.org"), ("route", "learn.microsoft.com")}
        assert src[("stage", UNSTAGED)]["triggers"] == ["failures"]
        assert src[("stage", "arxiv.org")]["triggers"] == ["failures"]
        planted = ql_learn.source_findings(ql_store.store_entries(store), counts=({UNSTAGED: [(25, 400)]}, {}))
        assert next(r for r in planted if r.get("host") == UNSTAGED)["triggers"] == ["share", "failures"]
        assert ql_store.store_problems(store) == []

    def test_learn_rechecks_no_fix_eval_findings(self, tmp_path):
        """BG-bbfdisfu: a no-fix eval finding (apply found no fix and promoted it) whose question
        now passes on HEAD becomes fixed-since; one whose question still misses stays no-fix, and a second learn
        writes nothing more for either."""
        store = learn_store(tmp_path)
        run_learn(store, failing)
        entries = ql_store.store_entries(store)
        questions = {e["id"]: e.get("question") for _, e in entries}
        evals = sorted((r for r in by_id(store).values() if r["kind"] == "eval"), key=lambda r: r["id"])
        fixed, stuck = evals[0], evals[1]
        ql_store.write_findings(store, entries, [{**{k: v for k, v in r.items() if k != "observed"}, "state": "no-fix", "stage": "candidate-gap"}
                                                 for r in (fixed, stuck)], ("no-fix",))
        assert {by_id(store)[r["id"]]["state"] for r in (fixed, stuck)} == {"no-fix"}
        now = questions[fixed["entry"]]
        run_learn(store, lambda q: passing(q) if q == now else failing(q))
        last = by_id(store)
        assert last[fixed["id"]]["state"] == "fixed-since" and last[stuck["id"]]["state"] == "no-fix", last
        assert last[fixed["id"]]["stage"] == "candidate-gap"  # the finding's own record, moved on, not a new miss
        files = len(findings(store))
        run_learn(store, lambda q: passing(q) if q == now else failing(q))
        assert len(findings(store)) == files

    def test_learn_writes_findings_only(self, tmp_path, head_pack):
        store = learn_store(tmp_path)
        before = tree(store)
        kb_files = [Path(KB) / p for p in ("kb/public/_retrieval/lookup_eval.csv", "_tools/aliases.csv",
                                           "kb/public/_gaps.md", "kb/public/_retrieval/doc2query/expansions.csv")]
        kb_before = [p.read_bytes() for p in kb_files]
        run_learn(store, head_pack)
        after = tree(store)
        assert {k: v for k, v in after.items() if not k.startswith("findings/")} == before
        assert [p.read_bytes() for p in kb_files] == kb_before

    def test_every_judged_miss_is_rerun_on_head_first(self, tmp_path):
        asked = []

        def pack(q):
            asked.append(q)
            return passing(q)
        store = learn_store(tmp_path)
        run_learn(store, pack)
        entries = {e["id"]: e for _, e in ql_store.store_entries(store)}
        assert sorted(asked) == sorted(entries[i]["question"] for i in MISS)
        recs = [r for _, rs in findings(store) for r in rs if r["kind"] != "source"]
        # all pass now: each miss is fixed-since, and none gets a fix finding
        assert sorted(r["kind"] for r in recs) == ["eval", "eval", "eval", "gap"]
        assert {r["state"] for r in recs} == {"fixed-since"}

    def test_two_runs_on_the_same_store_and_head_give_identical_files(self, tmp_path, head_pack):
        store = learn_store(tmp_path)
        run_learn(store, head_pack)
        first = tree(store)
        rc, said = run_learn(store, head_pack)
        assert said == ["learn: nothing new (findings=9)"] and tree(store) == first
        other = learn_store(tmp_path, "other")  # another clone with the same store and HEAD
        run_learn(other, head_pack)
        assert tree(other) == first

    def test_a_head_change_is_one_new_file(self, tmp_path):
        store = learn_store(tmp_path)
        run_learn(store, failing)
        opened = by_id(store)
        assert {r["state"] for r in opened.values()} == {"open"}
        run_learn(store, passing)
        (f1, _), (f2, two) = findings(store)
        assert f1.stem < f2.stem  # the later file sorts later
        now = by_id(store)
        fixes = [i for i, r in opened.items() if r["kind"] in ("alias", "expansion")]
        assert fixes and all(now[i]["state"] == "fixed-since" for i in fixes)  # no longer derived: fixed since
        assert all(now[i]["state"] == "fixed-since" for i, r in opened.items() if r["kind"] in ("eval", "gap"))
        assert all(now[i]["state"] == "open" for i, r in opened.items() if r["kind"] == "source")
        assert {r["id"] for r in two} == {i for i, r in opened.items() if r["kind"] != "source"}
        run_learn(store, failing)  # regressed on a later HEAD: open again
        assert all(by_id(store)[i]["state"] == "open" for i in opened)
        assert ql_store.store_problems(store) == []

    def test_a_weak_pack_judged_answered_is_no_miss(self, tmp_path):
        base = {"surface": "prompt", "day": "2026-09-27", "tools": ["kb_pack"], "judged": "answered", "best": None}
        weak = {**base, "id": "55555555-0000-4000-8000-0000000000d1", "question": "Planted weak but answered?",
                "verdict": "weak"}
        none = {**base, "id": "55555555-0000-4000-8000-0000000000d2", "question": "Planted none but answered?",
                "verdict": "none"}
        assert not ql_learn.is_miss(weak) and ql_learn.is_miss(none)
        assert ql_learn.is_miss({**weak, "judged": "partly"}) and ql_learn.is_miss({**weak, "judged": "missed"})
        assert ql_learn.is_miss({k: v for k, v in weak.items() if k != "judged"})  # not judged: the verdict decides
        store = learn_store(tmp_path)
        run = ql_store.run_files(store)[0]
        with open(run, "a", encoding="utf-8", newline="\n") as f:
            for e in (weak, none):
                f.write("\n" + json.dumps(e))  # the fixture file ends without a newline
        run_learn(store, failing)
        found = {r.get("entry") for r in by_id(store).values()}
        assert none["id"] in found and weak["id"] not in found  # the planted weak entry yields no finding

    def test_cli(self, tmp_path):
        store = learn_store(tmp_path)
        p = subprocess.run([sys.executable, QL, "learn", "--store", str(store)], capture_output=True, text=True,
                           encoding="utf-8", env=querylog_env(tmp_path / "data"), timeout=300)
        assert p.returncode == 0 and p.stdout.startswith("learn: run="), p.stdout + p.stderr
        (tmp_path / "data" / "querylog").mkdir(parents=True, exist_ok=True)  # querylog_env made it
        (tmp_path / "data" / "querylog" / "config.json").write_text('{"mode": "off"}', encoding="utf-8")
        p = subprocess.run([sys.executable, QL, "learn"], capture_output=True, text=True, encoding="utf-8",
                           env=querylog_env(tmp_path / "data"), timeout=120)
        assert (p.returncode, p.stdout) == (0, "learn: logging is off\n")


LEARN_URL = "https://learn.microsoft.com/en-us/windows-server/identity/laps/laps-overview"
HOOKS = "public/claude/hooks.md"


@pytest.fixture
def planted_kb(monkeypatch):
    """A kb whose sources and citations are three planted rows: a Learn page cited by two articles (three lines and
    one) and by a data file and a ledger, a Claude Code page cited with `.md`, and a page no article cites."""
    import kbfacts
    rows = {"S9001": {"url": LEARN_URL + "?view=windows-server-2025#top"},
            "S9002": {"url": "https://code.claude.com/docs/en/hooks.md"},
            "S9003": {"url": "https://www.vendor.example.org/docs/only-in-a-ledger/"},
            "S9004": {"url": ""}}
    cites = {"S9001": [(LAPS, 8), (LAPS, 12), (LAPS, 20), ("public/intune/win32-apps.md", 5),
                       ("public/windows/laps.csv", 1), ("public/windows/laps.csv", 2), ("public/_answers.md", 9)],
             "S9002": [(HOOKS, 6), (HOOKS, 21), ("public/agents/headless-agent-runtimes.md", 43)],
             "S9003": [("public/_answers.md", 3)]}
    arts = {p: {} for p in (LAPS, "public/intune/win32-apps.md", HOOKS, "public/agents/headless-agent-runtimes.md")}
    monkeypatch.setattr(kbfacts, "source_rows", lambda: rows)
    monkeypatch.setattr(kbfacts, "articles", lambda: arts)
    monkeypatch.setattr(kbfacts, "cited_lines", lambda ids: {i: cites.get(i, []) for i in ids})


ASK_Q = "What is the Intel Wi-Fi Roaming Aggressiveness setting?"
ASK_LINES = """## public/intune/network-profiles.md  Intune network profiles  [complete, retrieved 2026-09-27]
- public/intune/network-profiles.md:25 Profile types (DOC S1)"""
ASK_WEB_PACK = f"coverage: none\nroute: web\nkb has: Wi-Fi\nkb lacks: Roaming\n\n{ASK_LINES}"
ASK_SPLIT_PACK = f"coverage: weak\nroute: split\nkb has: Wi-Fi\nkb lacks: Roaming\n\n{ASK_LINES}"


def ask_result(text):
    """The JSON a planted `claude -p --output-format json` prints."""
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text,
                       "total_cost_usd": 0.01})


class TestLearnFalseNone:
    """A none entry whose fetched pages the kb cites is a false none: an eval finding at stage miss whose `expect` is
    the article citing them most, in place of a gap finding."""

    def learned(self, tmp_path, pack, *entries):
        store = learn_store(tmp_path)
        plant_entries(store, *entries)
        run_learn(store, pack)
        return store

    def found(self, store, n):
        return {r["kind"]: r for r in by_id(store).values() if r.get("entry") == FN.format(n)}

    def test_the_kb_cites_a_learn_page_the_lookup_fetched(self, tmp_path, planted_kb):
        e = none_entry("f1", "How do I back up a LAPS password to Entra ID?",
                       ("learn.microsoft.com", "/pl-pl/windows-server/identity/laps/laps-overview/", "http-200"))
        store = self.learned(tmp_path, failing, e)
        got = self.found(store, "f1")
        assert set(got) == {"eval", "expansion"}  # every word known: the paraphrase fix, and no gap finding
        ev = got["eval"]
        assert (ev["stage"], ev["state"], ev["expect"]) == ("miss", "open", LAPS)  # 3 lines against 1
        assert ev["observed"] == {"verdict": "none", "paths": [], "sources": ["S9001"]}
        assert got["expansion"]["article"] == LAPS
        assert ql_store.store_problems(store) == []

    def test_the_kb_cites_a_claude_code_page_with_md(self, tmp_path, planted_kb):
        e = none_entry("f3", "Which hook events does Claude Code run?", ("code.claude.com", "/docs/en/hooks", "http-200"))
        got = self.found(self.learned(tmp_path, failing, e), "f3")
        assert (got["eval"]["stage"], got["eval"]["expect"], got["eval"]["observed"]["sources"]) == (
            "miss", HOOKS, ["S9002"])
        assert "gap" not in got

    def test_a_page_the_kb_does_not_cite_stays_a_gap(self, tmp_path, planted_kb):
        pages = [("learn.microsoft.com", "/en-us/windows-server/identity/laps/other-page", "http-200"),
                 ("www.vendor.example.org", "/docs/only-in-a-ledger", "http-200")]  # cited by a ledger only
        e = none_entry("f2", "Is there a LAPS page the kb lacks?", *pages)
        got = self.found(self.learned(tmp_path, failing, e), "f2")
        assert set(got) == {"gap"} and got["gap"]["stage"] == "candidate-gap"
        assert "sources" not in got["gap"]["observed"]

    def test_a_second_learn_writes_nothing(self, tmp_path, planted_kb):
        es = [none_entry("f1", "How do I back up a LAPS password to Entra ID?",
                         ("learn.microsoft.com", "/pl-pl/windows-server/identity/laps/laps-overview/", "http-200")),
              none_entry("f2", "Is there a LAPS page the kb lacks?",
                         ("learn.microsoft.com", "/en-us/windows-server/identity/laps/other-page", "http-200")),
              none_entry("f3", "Which hook events does Claude Code run?",
                         ("code.claude.com", "/docs/en/hooks", "http-200"))]
        store = self.learned(tmp_path, failing, *es)
        first = tree(store)
        rc, said = run_learn(store, failing)
        assert rc == 0 and said[0].startswith("learn: nothing new") and tree(store) == first

    def test_fixed_since_once_the_pack_answers(self, tmp_path, planted_kb):
        e = none_entry("f1", "How do I back up a LAPS password to Entra ID?",
                       ("learn.microsoft.com", "/en-us/windows-server/identity/laps/laps-overview", "http-200"))
        store = self.learned(tmp_path, failing, e)
        run_learn(store, passing)  # the pack on HEAD now finds the LAPS article
        got = {r["id"]: r for r in by_id(store).values()}
        assert got[ql_store.finding_id("eval", e["id"])]["state"] == "fixed-since"
        assert not any(r["state"] == "open" for r in got.values() if r.get("entry") == e["id"])

    def test_only_a_none_entry_whose_fetch_read_a_page(self, tmp_path, planted_kb):
        page = ("learn.microsoft.com", "/en-us/windows-server/identity/laps/laps-overview", "http-200")
        weak = none_entry("d1", "A weak lookup that fetched a cited page?", page, verdict="weak", judged="partly")
        dead = none_entry("d2", "A none lookup whose fetch failed?", (*page[:2], "http-404"))
        empty = none_entry("d3", "A none lookup with no fetch?")
        store = self.learned(tmp_path, failing, weak, dead, empty)
        for n in ("d1", "d2", "d3"):  # a weak verdict, a fetch that read nothing, no fetch: the findings they give now
            assert set(self.found(store, n)) == {"gap"}, n

    def test_the_article_citing_most_wins_and_ties_go_by_path(self, planted_kb):
        pages = ql_learn.KbPages()
        page = ("learn.microsoft.com", "/en-us/windows-server/identity/laps/laps-overview", "http-200")
        assert pages.match(none_entry("e1", "q", page)) == (LAPS, ["S9001"])
        both = none_entry("e2", "q", page, ("code.claude.com", "/docs/en/hooks/", "http-200"))
        assert pages.match(both) == (LAPS, ["S9001", "S9002"])  # the lines of both sources add up per article
        tie = none_entry("e3", "q", ("code.claude.com", "/docs/en/hooks", "http-200"),
                         ("learn.microsoft.com", "/docs/en/nothing", "http-200"))
        assert pages.match(tie)[0] == HOOKS
        pages._lines["S9002"] = {HOOKS: 1, "public/agents/headless-agent-runtimes.md": 1}
        assert pages.match(tie)[0] == "public/agents/headless-agent-runtimes.md"  # equal counts: the earlier path

    @pytest.mark.parametrize("host,path,key", [
        ("Learn.Microsoft.com", "/EN-US/windows/x/", "learn.microsoft.com/windows/x"),
        ("learn.microsoft.com", "/en-us", "learn.microsoft.com"),
        ("learn.microsoft.com", "/pl-pl/windows/x?view=y#z", "learn.microsoft.com/windows/x"),
        ("www.example.org", "/a/b.md", "example.org/a/b"),
        ("code.claude.com", "/docs/en/hooks.md/", "code.claude.com/docs/en/hooks"),
        ("example.org", "/en-us/a", "example.org/en-us/a"),  # only Learn has a locale segment
        ("example.org", None, "example.org"), (None, "/a", None), ("", "/a", None)])
    def test_page_key(self, host, path, key):
        assert ql_learn.page_key(host, path) == key

    def ask(self, monkeypatch, capsys, pack, *outs):
        """One kb_ask.py run over a planted pack and a planted `claude -p` (never the real CLI): (exit code, spool row)."""
        import kb_ask
        outs = list(outs)
        monkeypatch.setattr(kb_ask.kbfacts, "pack_many",
                            lambda parts, **kw: {"verdict": "none", "results": [], "text": pack})
        monkeypatch.setattr(kb_ask.shutil, "which", lambda name: "/planted/claude")
        monkeypatch.setattr(subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, outs.pop(0), ""))
        monkeypatch.setattr(sys, "argv", ["kb_ask.py", ASK_Q])
        row = {}
        code = kb_ask.run(row)
        capsys.readouterr()
        return code, {"id": FN.format("c9"), "ts": "2026-09-27T10:00:00.000Z", "surface": "kb_ask", "v": 1, **row}

    def test_a_kb_ask_row_carries_the_source_ids_its_researcher_cites(self, tmp_path, planted_kb, monkeypatch, capsys):
        import redact
        answer = (f"Back it up with the policy ([docs]({LEARN_URL}/?view=x#top)); events: "
                  "https://code.claude.com/docs/en/hooks.")
        code, row = self.ask(monkeypatch, capsys, ASK_WEB_PACK, ask_result(answer))
        assert code == 0 and row["route"] == "web" and row["sources"] == ["S9001", "S9002"]
        assert "learn.microsoft.com" not in json.dumps(row) and "policy" not in json.dumps(row)  # ids only
        entry, _, drop = ql_distill.entry_of([row], redact.known())
        assert drop is None and entry["sources"] == ["S9001", "S9002"] and entry["route"] == "web"
        assert "https" not in json.dumps(entry) and "policy" not in json.dumps(entry)
        store = self.learned(tmp_path, failing, entry)
        got = {r["kind"]: r for r in by_id(store).values() if r.get("entry") == row["id"]}
        assert set(got) == {"eval", "expansion"}, got  # a false none, as if the session had fetched the pages
        assert (got["eval"]["stage"], got["eval"]["expect"]) == ("miss", LAPS)  # 3 lines of S9001 against 2 of S9002
        assert got["eval"]["observed"]["sources"] == ["S9001", "S9002"]
        assert ql_store.store_problems(store) == []
        assert run_learn(store, failing)[1][0].startswith("learn: nothing new")  # converges

    def test_a_kb_ask_row_names_only_the_researchers_answer(self, monkeypatch, capsys, planted_kb):
        reader = f"The kb says so ({LEARN_URL}). "  # the reader's kb part is the kb's own answer, not a fetched page
        live = "See https://code.claude.com/docs/en/hooks.md and https://example.org/none-of-the-kbs."
        code, row = self.ask(monkeypatch, capsys, ASK_SPLIT_PACK, ask_result(reader), ask_result(live))
        assert code == 0 and row["route"] == "split" and row["sources"] == ["S9002"]
        code, row = self.ask(monkeypatch, capsys, ASK_SPLIT_PACK, ask_result("INSUFFICIENT: nothing"),
                             ask_result(f"Everything is at {LEARN_URL}"))
        assert code == 0 and row["escalated"] is True and row["sources"] == ["S9001"]

    def test_no_sources_without_a_kb_url_or_a_researcher_answer(self, monkeypatch, capsys, planted_kb):
        import redact
        for answer in ("The live docs do not answer it.", "See https://example.org/none-of-the-kbs and S9001.", ""):
            code, row = self.ask(monkeypatch, capsys, ASK_WEB_PACK, ask_result(answer))
            assert code == 0 and "sources" not in row, answer
        error = json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True,
                            "errors": [f"gave up at {LEARN_URL}"]})
        code, row = self.ask(monkeypatch, capsys, ASK_WEB_PACK, error)
        assert code == 1 and "sources" not in row  # an error result's errors are no answer
        entry, _, _ = ql_distill.entry_of([{**row, "sources": ["S9001"], "surface": "kb_hook"}], redact.known())
        assert "sources" not in entry  # only a kb_ask.py row carries them

    def test_a_source_no_article_cites_stays_a_gap(self, tmp_path, monkeypatch, capsys, planted_kb):
        import redact
        code, row = self.ask(monkeypatch, capsys, ASK_WEB_PACK,
                             ask_result("Only https://www.vendor.example.org/docs/only-in-a-ledger."))
        assert row["sources"] == ["S9003"]  # named, and in the kb: recorded as it is
        entry, _, _ = ql_distill.entry_of([row], redact.known())
        got = {r["kind"]: r for r in by_id(self.learned(tmp_path, failing, entry)).values()
               if r.get("entry") == row["id"]}
        assert set(got) == {"gap"} and "sources" not in got["gap"]["observed"]  # a ledger alone: no false none

    def test_distill_keeps_only_source_ids(self, planted_kb):
        import redact
        row = {"id": FN.format("c8"), "ts": "2026-09-27T10:00:00.000Z", "surface": "kb_ask", "v": 1, "route": "web",
               "question": ASK_Q, "verdict": "none",
               "sources": [LEARN_URL, "S9001", 7, "the LAPS page", "S9001", "S-abcdefg2", "S9002"]}
        entry, _, _ = ql_distill.entry_of([row], redact.known())
        assert entry["sources"] == ["S-abcdefg2", "S9001", "S9002"]
        assert "sources" not in ql_distill.entry_of([{**row, "sources": "S9001"}], redact.known())[0]
        many = [f"S{n}" for n in range(1000, 1000 + 2 * ql_store.SOURCES_MAX)]
        assert len(ql_distill.entry_of([{**row, "sources": many}], redact.known())[0]["sources"]) == ql_store.SOURCES_MAX

    def test_an_entry_with_sources_learns_a_false_none_without_a_fetch(self, planted_kb):
        e = none_entry("c7", "How do I back up a LAPS password to Entra ID?", sources=["S9001"])
        assert ql_learn.KbPages().match(e) == (LAPS, ["S9001"])
        assert ql_learn.KbPages().match({**e, "sources": ["S9003", "S9004", 4, "S0000"]}) is None  # none an article cites
        assert ql_learn.KbPages().match({**e, "verdict": "weak"}) is None  # a none lookup only
        failed = none_entry("c6", "q", ("code.claude.com", "/docs/en/hooks", "http-404"), sources=["S9002"])
        assert ql_learn.KbPages().match(failed) == (HOOKS, ["S9002"])  # the failed fetch adds none, the source counts

    def test_the_kb_at_head_cites_the_hooks_page(self, tmp_path):
        e = none_entry("k1", "Which hook events does Claude Code run?", ("code.claude.com", "/docs/en/hooks", "http-200"))
        hit = ql_learn.KbPages().match(e)
        assert hit and hit[0].startswith("public/claude/") and "S743" in hit[1]


class TestSourceFindings:
    def test_triggers_match_web_sources(self, monkeypatch):
        doc = REAL_WEB_SOURCES.read_text(encoding="utf-8")
        assert ql_learn.trigger_problems(doc) == []
        assert "at least 25 rows" in doc and "Three or more failures" in doc
        planted = doc.replace("at least 25 rows", "at least 30 rows")
        assert ql_learn.trigger_problems(planted) == ["trigger share_rows: ql_learn.py has 25, web-sources.md has 30"]
        assert ql_learn.trigger_problems(doc.replace("Three or more failures", "Four or more failures"))
        assert ql_learn.trigger_problems(doc.replace("at least 5%", "at least 10%"))
        monkeypatch.setattr(ql_learn, "STAGE_FAILURES", 4)
        assert ql_learn.trigger_problems(doc) == ["trigger failures: ql_learn.py has 4, web-sources.md has 3"]

    def test_level_from_the_registry_else_the_routes_table(self, tmp_path, monkeypatch):
        assert ql_learn.staging_level("learn.microsoft.com") == (3, "registry")  # in both: the registry decides
        assert ql_learn.staging_level("raw.githubusercontent.com") == (3, "registry")
        assert ql_learn.staging_level("pypi.org") == (1, "routes")
        assert ql_learn.staging_level("platform.claude.com") == (1, "routes")
        assert ql_learn.staging_level(UNSTAGED) == (0, None)
        import kbcommon, provider  # a root's own _providers.csv counts as the registry
        team = tmp_path / "team"
        team.mkdir()
        (team / provider.ROOT_FILE).write_text("provider,match\nteam-wiki,wiki.corp.example.com/\n", encoding="utf-8",
                                               newline="\n")
        roots = kbcommon.roots()
        monkeypatch.setattr(kbcommon, "roots", lambda: roots + [kbcommon.Root("team", str(team), "TM", "internal", "")])
        assert ql_learn.staging_level("wiki.corp.example.com") == (3, "registry")

    def test_the_registry_and_the_routes_table_agree(self):
        assert ql_learn.registry_problems() == []  # the planted pair
        import provider
        rows = provider._read(str(REAL_REGISTRY))
        doc = REAL_WEB_SOURCES.read_text(encoding="utf-8")
        real = ql_learn.routes_table(doc)
        assert ql_learn.registry_problems(rows, real) == []  # the clone's own pair
        planted = rows + [{"provider": "vendor", "match": "docs.vendor.example.org/"}]
        assert ql_learn.registry_problems(planted, real) == [
            "provider vendor: docs.vendor.example.org has a registry row but no row in the routes table"]
        routes = ql_learn.routes_table(doc.replace("| `learn.microsoft.com` |", "| Learn |"))
        assert any("learn.microsoft.com" in p for p in ql_learn.registry_problems(rows, routes))
        team = [{"provider": "team-wiki", "match": "wiki.corp.example.com/", "_root": "team"}]
        assert ql_learn.registry_problems(rows + team, real) == []  # a root's own providers are its team's

    def test_no_source_finding_for_a_host_with_the_needed_level(self, tmp_path):
        store = learn_store(tmp_path)
        run_learn(store, passing)
        hosts = {(r["signal"], r["host"]) for r in by_id(store).values() if r["kind"] == "source"}
        # learn.microsoft.com (registry) and pypi.org (routes) failed three times each, and learn.microsoft.com backs
        # far more than 25 sources: neither gets a stage finding
        assert ("stage", "learn.microsoft.com") not in hosts and ("stage", "pypi.org") not in hosts
        assert ("stage", UNSTAGED) in hosts and ("stage", "arxiv.org") in hosts  # planted: level 0

    def test_source_findings_read_the_registry_and_the_routes_table(self, tmp_path, monkeypatch):
        import provider
        shared = tmp_path / "providers.csv"
        row = ["unstaged", UNSTAGED + "/"] + [""] * (len(provider.COLS) - 2)
        shared.write_text(Path(provider.SHARED).read_text(encoding="utf-8") + ",".join(row) + "\n",
                          encoding="utf-8", newline="\n")
        assert ql_learn.registry_row(UNSTAGED) is None
        monkeypatch.setattr(provider, "SHARED", str(shared))  # a registry row added: the host has level 3
        doc = ql_learn.WEB_SOURCES.read_text(encoding="utf-8").replace(
            "| PyPI |", "| `arxiv.org` | WebSearch | the abstract page | WebFetch |\n| PyPI |")
        monkeypatch.setattr(ql_learn, "WEB_SOURCES", tmp_path / "web-sources.md")
        ql_learn.WEB_SOURCES.write_text(doc, encoding="utf-8", newline="\n")  # a routes row added: level 1
        store = learn_store(tmp_path)
        run_learn(store, passing)
        assert not [r for r in by_id(store).values() if r.get("signal") == "stage"]


STAGING_TESTS = (TestLearn.test_the_fixture_gives_findings_of_each_kind,
                 TestLearn.test_two_runs_on_the_same_store_and_head_give_identical_files,
                 TestLearn.test_a_head_change_is_one_new_file,
                 TestSourceFindings.test_level_from_the_registry_else_the_routes_table,
                 TestSourceFindings.test_no_source_finding_for_a_host_with_the_needed_level,
                 TestSourceFindings.test_source_findings_read_the_registry_and_the_routes_table)


def staging_results(tmp_path, head_pack):
    """{test: "passed" or "failed"} of STAGING_TESTS run here, each in a directory of its own."""
    import inspect
    out = {}
    for fn in STAGING_TESTS:
        d = tmp_path / f"t{len(out)}"  # not the test name: a long profile path passes MAX_PATH on Windows
        d.mkdir(parents=True)
        mp = pytest.MonkeyPatch()
        args = {"tmp_path": d, "head_pack": head_pack, "monkeypatch": mp}
        try:
            fn(None, **{k: args[k] for k in list(inspect.signature(fn).parameters)[1:]})
            out[fn.__name__] = "passed"
        except AssertionError:
            out[fn.__name__] = "failed"
        finally:
            mp.undo()
    return out


def test_querylog_tests_plant_their_registry(tmp_path, head_pack, monkeypatch):
    """The clone gains provider and routes rows for the fixture store's level-0 hosts (as staging arxiv.org would
    add): the staging tests, on a registry they plant, give the same results; without the plant they would not."""
    import provider
    grown = tmp_path / "grown"
    grown.mkdir()
    rows = [",".join([name, host + "/"] + [""] * (len(provider.COLS) - 2))
            for name, host in (("arxiv", "arxiv.org"), ("unstaged", UNSTAGED))]
    registry = REAL_REGISTRY.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(rows) + "\n"
    (grown / "providers.csv").write_text(registry, encoding="utf-8", newline="\n")
    doc = REAL_WEB_SOURCES.read_text(encoding="utf-8")
    assert "| PyPI |" in doc
    doc = doc.replace("| PyPI |", "| `arxiv.org` | WebSearch | the abstract page | WebFetch |\n"
                                  f"| `{UNSTAGED}` | the site's search | the page | - |\n| PyPI |", 1)
    (grown / "web-sources.md").write_text(doc, encoding="utf-8", newline="\n")
    monkeypatch.setattr(provider, "SHARED", str(grown / "providers.csv"))  # what the clone's files now serve
    monkeypatch.setattr(ql_learn, "WEB_SOURCES", grown / "web-sources.md")
    assert ql_learn.staging_level("arxiv.org") == (3, "registry") and ql_learn.registry_problems() == []
    unplanted = staging_results(tmp_path / "unplanted", head_pack)
    assert "failed" in unplanted.values(), unplanted  # the grown rows reach a test that reads them
    with planted_staging(tmp_path / "planted"):
        assert ql_learn.staging_level("arxiv.org") == (0, None)
        assert staging_results(tmp_path / "planted-run", head_pack) == {fn.__name__: "passed" for fn in STAGING_TESTS}


@pytest.fixture(scope="module")
def learned(tmp_path_factory):
    """The fixture store after one learn in which every miss still fails."""
    store = learn_store(tmp_path_factory.mktemp("learned"))
    run_learn(store, failing)
    return store


def gap_of(objs):
    return next(o for o in objs[1:] if o["kind"] == "gap")


class TestFindingsGates:
    def planted(self, learned, tmp_path, change):
        store = tmp_path / "store"
        shutil.copytree(learned, store)
        (p,) = ql_store.findings_files(store)
        objs = jsonl(p)
        change(objs)
        p.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        return ql_store.store_problems(store)

    def test_the_learned_store_passes(self, learned):
        assert ql_store.store_problems(learned) == []

    @pytest.mark.parametrize("change,problem", [
        (lambda o: o[0].pop("kb_commit"), "header lacks kb_commit"),
        (lambda o: o[0].update(run="20260928T120000Z-00000000"), "run id does not name this file"),
        (lambda o: o[0]["counts"].update(findings=1), "counts.findings is 1"),
        (lambda o: o[1].update(id="F-1"), "finding id is not F-<12 hex>"),
        (lambda o: o[1].update(kind="hunch"), "unknown kind 'hunch'"),
        (lambda o: o[1].update(state="done"), "unknown state 'done'"),
        (lambda o: o[1].update(stage="rumour"), "unknown stage 'rumour'"),
        (lambda o: o[1].update(entry="55555555-0000-4000-8000-0000000000ff"), "is in no run file of the store"),
        (lambda o: o[1].update(question="raw text"), "unknown fields: question"),
        (lambda o: o[1].update(promotions=[{"from": "miss"}]), "a promotion without its from and to stages"),
        (lambda o: o[-1].update(host="wiki.acme-corp.pl"), "source host is not a public host"),
        (lambda o: o[-1].update(signal="vibes"), "unknown signal 'vibes'"),
        (lambda o: o[-1].update(state="applied"), "a source finding is never applied"),
        (lambda o: o[1].update(state="applied"), "is applied without its fix"),
        (lambda o: gap_of(o).update(promotions=[{"from": "miss", "to": "candidate-gap", "by": "haiku"}]),
         "a promotion by 'haiku'"),
        (lambda o: gap_of(o).update(stage="gap", article=LAPS, promotions=[
            {"from": "miss", "to": "candidate-gap", "by": "learn"}, {"from": "miss", "to": "gap", "by": "apply"}]),
         "promotions do not follow each other"),
        (lambda o: gap_of(o).update(stage="gap", article=LAPS), "stage gap is not its last promotion's candidate-gap"),
        (lambda o: gap_of(o).update(stage="gap", promotions=[{"from": "miss", "to": "candidate-gap", "by": "learn"},
                                                             {"from": "candidate-gap", "to": "gap", "by": "apply"}]),
         "a gap finding at stage gap names no article"),
    ])
    def test_findings_gates(self, learned, tmp_path, change, problem):
        problems = self.planted(learned, tmp_path, change)
        assert any(problem in p for p in problems), problems
