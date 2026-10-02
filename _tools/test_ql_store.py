"""Query log tests, store (kb/_self/querylog.md, Store; `python3 _tools/tests.py -k TestStore`).

  TestStore         the store gates, each with a planted failure: a duplicate id across run files (also through
                    `kbgit.py fix --check`), a missing header or provenance field, run metadata or raw fields in an
                    entry, an identifier in the question, free text in an entry (a summary, an unknown field, text in
                    a closed field), citations that are not path:line or missing beside articles, a count other than
                    entries, dropped, waiting and a positive skipped, a fetch with a
                    query string, a non-public host or command
                    text; `pack` and `search` never return a kb/_querylog/ line; _cache/ stays ignored
  TestWorkGates     the work sidecar gates (`-k work_sidecar`), each with a planted failure: a header other than run,
                    reader and counts, a run id that names another file or month, no run file beside it, counts that do
                    not match the lines, an unknown field (a session, a prompt, a command, a usage record's `start`),
                    an item that is not an item id, items unsorted, repeated or not a list, a prompt count that is not
                    a positive count (an item line may have none, with an empty `main` and a `sub`, for subagent counts
                    routed to it, never otherwise), a model id, agent group or count outside its shape, `cw1h`
                    above `cw`, an item twice in a file (the same item in two runs is fine), an empty file or one that is not JSON lines;
                    `querylog.py check` and the leak scan run over it
  TestOverheadGates the overhead line of the work sidecar (`-k overhead_sidecar`), each gate with a planted failure: an
                    item or items beside it, a session, prompt or text field, a kind outside `OVERHEAD_KINDS`, a
                    `calls` or a count that is not a (positive) count, counts outside the model shape, a header
                    count that does not match, a kind twice in a file; a valid line does not make `backlog.py cost`
                    skip the sidecar
  TestWorkReworkGates the `rework` block of an item line (`-k work_rework`), each gate with a planted failure: a sidecar
                    with and without it passes, a block that is not a block, one with a field outside `prompts`, `main`
                    and `sub`, counts outside the line shapes, counts above the line's own, one on a sprint's line or
                    on a shared line
  TestOpsGates      the ops sidecar gates (`-k ops_sidecar`), each with a planted failure: a header other than run and
                    counts, a run id that names another file or month, no run file beside it, a count that does not
                    match the lines, an id that is not a row id or twice across sidecars, a time that is not the
                    spool's, an event outside the closed set, a key the event does not have or lacks, and a value
                    outside its shape (free text in a name, a node id or a path in a test file, a flag for a count,
                    a reason of its own); an empty file or one that is not JSON lines; the leak scan finds an
                    identifier in a value that passes the shape (`-k ops_sidecar_refuses_free_text` covers the
                    values); `querylog.py check` runs them all
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The helpers the classes share are in
ql_testkit.py.
"""
import json, os, subprocess, sys
from pathlib import Path

import pytest

import ql_store
from conftest import GIT, KB, copy_kb
from ql_testkit import c, FIXTURES, golden_store, jsonl, QL, RUN_ID, S_ENDED


def planted(tmp_path, change):
    """The golden run file with `change(objects)` applied: the store's problems."""
    objs = jsonl(FIXTURES / "golden.jsonl")
    change(objs)
    return ql_store.store_problems(golden_store(tmp_path / "store", objs))


@pytest.fixture(scope="module")
def kb_copy(tmp_path_factory):
    """A copy of the kb with one run file under kb/_querylog/ whose question holds a word no article has."""
    home = copy_kb(str(tmp_path_factory.mktemp("ql") / "kb"))
    objs = jsonl(FIXTURES / "golden.jsonl")
    objs[1]["question"] = "Which zqxvortel recognizers cover the Polish PESEL number?"
    golden_store(Path(home) / "kb" / "_querylog", objs)
    return home


class TestStore:
    def test_the_committed_store_passes(self):
        assert ql_store.store_problems() == []
        p = subprocess.run([sys.executable, QL, "check"], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert (p.returncode, p.stdout) == (0, "querylog check: problems=0\n"), p.stdout

    def test_golden_passes_and_check_reports(self, tmp_path):
        store = golden_store(tmp_path / "store")
        assert ql_store.store_problems(store) == []
        bad =golden_store(tmp_path / "bad", [{"run": "x"}])
        p = subprocess.run([sys.executable, QL, "check", str(bad)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert p.returncode == 1 and "header lacks" in p.stdout, p.stdout

    def test_duplicate_id_across_run_files(self, tmp_path):
        store = golden_store(tmp_path / "store")
        assert ql_store.duplicate_ids(store) == []
        golden_store(store, name="20260928T130000Z-0000ffff", lines_=[
            {**jsonl(FIXTURES / "golden.jsonl")[0], "run": "20260928T130000Z-0000ffff",
             "counts": {"entries": 1, "dropped": 0, "waiting": 0}}, jsonl(FIXTURES / "golden.jsonl")[1]])
        (dup,) = ql_store.duplicate_ids(store)
        assert "2026-09/20260928T130000Z-0000ffff.jsonl:2: duplicate entry id 22222222-" in dup
        assert ql_store.store_problems(store)[-1] == dup

    def test_kbgit_fix_check_fails_on_a_duplicate_id(self, kb_copy):
        env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "KB_INDEX")}
        run = lambda: subprocess.run([sys.executable, os.path.join(kb_copy, "_tools", "kbgit.py"), "fix", "--check"],  # noqa: E731
                                     cwd=kb_copy, capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
        p = run()
        assert p.returncode == 0, p.stdout + p.stderr
        dup = Path(kb_copy) / "kb" / "_querylog" / "2026-09" / "20260928T130000Z-0000ffff.jsonl"
        objs = jsonl(FIXTURES / "golden.jsonl")
        dup.write_text(json.dumps({**objs[0], "run": dup.stem, "counts": {"entries": 1, "dropped": 0, "waiting": 0}})
                       + "\n" + json.dumps(objs[2]) + "\n", encoding="utf-8", newline="\n")
        try:
            p = run()
        finally:
            dup.unlink()
        assert p.returncode == 2 and "PROBLEM kb/_querylog/2026-09/20260928T130000Z-0000ffff.jsonl:2: duplicate entry id" \
            in p.stdout, p.stdout + p.stderr

    @pytest.mark.parametrize("change,problem", [
        (lambda o: o[0].pop("kb_commit"), "header lacks kb_commit"),
        (lambda o: o[0].pop("retrieval"), "header lacks retrieval"),
        (lambda o: o[0].pop("pipeline"), "header lacks pipeline"),
        (lambda o: o.pop(0), "header lacks run, pipeline, retrieval, kb_commit, counts"),
        (lambda o: o[0].update(run="20260928T120000Z-00000000"), "run id does not name this file"),
        (lambda o: o[0].update(kb_commit="HEAD"), "kb commit is not a commit id"),
        (lambda o: o[0]["counts"].update(entries=2), "counts.entries is 2"),
        (lambda o: o[0].update(host="build-agent-7"), "header fields a header never has: host"),
        (lambda o: o[0]["counts"].update(skipped=0), "counts hold a field other than"),
        (lambda o: o[0]["counts"].update(skipped="3"), "counts hold a field other than"),
        (lambda o: o[0]["counts"].update(lost=1), "counts hold a field other than"),
        (lambda o: o[1].update(kb_commit="0" * 40), "run metadata in an entry: kb_commit"),
        (lambda o: o[1].update(run=RUN_ID, retrieval=4), "run metadata in an entry: retrieval, run"),
        (lambda o: o[1].update(prompt="kb: raw"), "raw spool fields: prompt"),
        (lambda o: o[1].update(session_id=S_ENDED), "raw spool fields: session_id"),
        (lambda o: o[1].update(prompt_id="pa1", transcript_path="/tmp/t.jsonl"), "raw spool fields: prompt_id, transcript_path"),
        (lambda o: o[1].update(user="jan"), "raw spool fields: user"),
        (lambda o: o[1].update(hostname="PL-LT-00123"), "raw spool fields: hostname"),
    ])
    def test_header_and_provenance_gates(self, tmp_path, change, problem):
        problems = planted(tmp_path, change)
        assert any(problem in p for p in problems), problems

    @pytest.mark.parametrize("text", ["sign-in fails for anna.nowak~@acme-corp.pl", "the DP at 10.~1.20.33 times out",
                                      "files on fs01.acme.local are locked", "the key Zk9xR2tWb3BqM3NlY3JldDEyMzQ1Ng fails",
                                      "whoami says ACME\\anowak", "object 3f2b8c1~e-5d4a-4b7c-9e1f-aa3b4c5d6e7f fails"])
    def test_identifier_gate(self, tmp_path, text):
        problems = planted(tmp_path, lambda o: o[1].update(question=c(text)))
        assert any("an identifier in `question`" in p for p in problems), problems

    @pytest.mark.parametrize("change,problem", [
        (lambda e: e.update(summary="The inquiry received a comprehensive answer."), "free text in an entry: summary"),
        (lambda e: e.update(outline="license files added"), "unknown fields: outline"),
        (lambda e: e.update(judged="answered in full, see the steps"), "`judged` is not a judged value"),
        (lambda e: e.update(best="the LAPS article"), "`best` is not a best value"),
        (lambda e: e.update(articles=["the LAPS article, lines 24 and 25"]), "`articles` is not a articles value"),
        (lambda e: e.update(intent="a license review for a colleague"), "`intent` is not a intent value"),
        (lambda e: e.update(tools=["kb_pack asked about licences"]), "`tools` is not a tools value"),
        (lambda e: e.update(verdict="mostly fine"), "`verdict` is not a verdict value"),
        (lambda e: e.update(day="last Tuesday"), "`day` is not a day value"),
    ])
    def test_free_text_gate(self, tmp_path, change, problem):
        """An entry holds the kb's question, closed values and citations: a summary or text in another field fails."""
        assert planted(tmp_path / "ok", lambda o: None) == []
        problems = planted(tmp_path, lambda o: change(o[5]))  # the kb: hook entry
        assert any(problem in p for p in problems), problems

    @pytest.mark.parametrize("change,problem", [
        (lambda e: e.pop("citations"), "articles without citations"),
        (lambda e: e.update(citations=[]), "citations are not a list"),
        (lambda e: e.update(citations="public/windows/laps.md:24"), "citations are not a list"),
        (lambda e: e.update(citations=[{"line": "the LAPS article says 14", "tag": "DOC"}]), "not a path:line"),
        (lambda e: e.update(citations=[{"line": "public/windows/laps.md"}]), "not a path:line"),
        (lambda e: e.update(citations=[{"line": "public/windows/laps.md:24", "text": "14 characters"}]),
         "not a path:line"),
        (lambda e: e.update(citations=[{"line": "public/windows/laps.md:24", "tag": "OFFICIAL"}]), "not a path:line"),
        (lambda e: e.update(citations=[{"line": "public/windows/laps.md:24", "verdict": "fine"}]), "not a path:line"),
        (lambda e: e.update(citations=[{"line": f"public/windows/laps.md:{n}"} for n in range(1, 8)]),
         "citations are not a list of 1 to 5"),
        (lambda e: e.pop("cited"), "`cited` is not reply or pack"),
        (lambda e: e.update(cited="the reply cited both lines"), "`cited` is not reply or pack"),
    ])
    def test_citation_gate(self, tmp_path, change, problem):
        """Citations are path:line with the tag and verdict the kb printed, never text; an entry that names articles
        carries them."""
        problems = planted(tmp_path, lambda o: change(o[5]))
        assert any(problem in p for p in problems), problems

    @pytest.mark.parametrize("change,problem", [
        (lambda e: e.update(path="/en-us/windows?token=abc"), "query string"),
        (lambda e: e.update(path="/en-us/windows#top"), "query string"),
        (lambda e: e.update(host="10." + "1.2.3"), "not a public host"),
        (lambda e: e.update(host="wiki.acme-corp.pl"), "not a public host"),
        (lambda e: e.update(host="fs01.corp"), "not a public host"),
        (lambda e: e.update(tool="curl -s https://learn.microsoft.com/x"), "not a tool name (command text?)"),
        (lambda e: e.update(command="curl -s https://learn.microsoft.com/x"), "raw spool fields: command"),
        (lambda e: e.update(outcome="a bot page"), "not an outcome class"),
        (lambda e: e.pop("host"), "fetch path without a public host"),
        (lambda e: e.update(chars=-1), "fetch chars is not a count"),
        (lambda e: e.update(chars="12 KB"), "fetch chars is not a count"),
        (lambda e: e.update(n=True), "fetch n is not a count"),
    ])
    def test_fetch_gates(self, tmp_path, change, problem):
        problems = planted(tmp_path, lambda o: change(o[2]))  # the standalone fetch.py entry
        assert any(problem in p for p in problems), problems
        nested = planted(tmp_path / "n", lambda o: change(o[6]["fetches"][1]))  # a fetch inside a lookup
        if problem != "raw spool fields: command":
            assert any(problem in p for p in nested), nested
        else:
            assert any("fetch fields a fetch never keeps: command" in p for p in nested), nested

    @pytest.mark.parametrize("value", [["https://learn.microsoft.com/en-us/windows/laps"], "S9001", ["the LAPS page"],
                                       ["S9001", "S9001"], [], [1234], ["S9001?x=1"],
                                       [f"S{n}" for n in range(1000, 1000 + ql_store.SOURCES_MAX + 1)]])
    def test_sources_gate(self, tmp_path, value):
        """`sources` holds kb source ids only: no url, no text, each once, at most SOURCES_MAX."""
        assert planted(tmp_path / "ok", lambda o: o[5].update(sources=["S1216", "S-3yod3u7q"])) == []
        problems = planted(tmp_path, lambda o: o[5].update(sources=value))
        assert any("`sources` is not a sources value" in p for p in problems), problems

    def test_pack_and_search_never_return_a_querylog_line(self, kb_copy, tmp_path):
        env = {**{k: v for k, v in os.environ.items() if k not in ("KB_ROOTS",)}, "KB_INDEX": str(tmp_path / "index")}
        rag = [sys.executable, os.path.join(kb_copy, "_tools", "rag.py")]

        def out(*args):
            p = subprocess.run(rag + list(args), capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
            return p.stdout + p.stderr
        for args in (["search", "zqxvortel recognizers"], ["search", "zqxvortel", "--index"],
                     ["pack", "Which zqxvortel recognizers cover the Polish PESEL number?"]):
            text = out(*args)
            assert "_querylog" not in text and "cover the Polish PESEL" not in text, text[:800]
        article = Path(kb_copy) / "kb" / "public" / "reuse" / "pseudonymization-tokenization.md"
        saved = article.read_bytes()
        try:  # planted: the same word in an article is found
            article.write_bytes(saved + b"\n- Planted zqxvortel line for the test. [DER S-h2cmbqvf]\n")
            assert "Planted zqxvortel line" in out("search", "zqxvortel")
        finally:
            article.write_bytes(saved)

    @pytest.mark.skipif(not GIT, reason="git is not installed")
    def test_the_spool_and_local_store_stay_ignored(self):
        def ignored(rel):
            return subprocess.run(["git", "check-ignore", "-q", rel], cwd=KB, capture_output=True).returncode == 0
        assert ignored("_cache/querylog/spool/x.jsonl") and ignored("_cache/querylog/store/2026-09/x.jsonl")
        assert ignored("_private/querylog.json")
        assert not ignored("kb/_querylog/2026-09/x.jsonl")  # planted: the store itself is committed


WORK_RUN = RUN_ID
WORK_A, WORK_B = "TK-aaaaaaaa", "TK-bbbbbbbb"
OPUS = {"requests": 2, "in": 5, "cw": 1200, "cw1h": 1200, "cr": 11000, "out": 170}
HAIKU = {"requests": 1, "in": 10, "cw": 3000, "cw1h": 0, "cr": 0, "out": 80}


def work_lines():
    """An item line with a subagent, an item line without, and a shared line."""
    return [{"item": WORK_A, "prompts": 3, "main": {"claude-opus-5-5": OPUS},
             "sub": {"kb-lookup": {"claude-haiku-4-5-20251001": HAIKU}}},
            {"item": WORK_B, "prompts": 1, "main": {"claude-opus-5-5": OPUS}},
            {"items": [WORK_A, WORK_B], "prompts": 2, "main": {"claude-opus-5-5": OPUS}}]


def work_store(tmp_path, change=None, lines=None, layout=None):
    """The golden run file with a work sidecar of `lines` (default: work_lines, written by write_work): `change(objects)`
    edits its header and lines, `layout(store)` the files. The store's work problems."""
    store = golden_store(tmp_path / "store")
    ql_store.write_work(store, WORK_RUN, lines or work_lines(), 0, 1)
    path = ql_store.work_files(store)[0]
    objs = jsonl(path)
    if change:
        change(objs)
    path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
    if layout:
        layout(store)
    return store, ql_store.work_problems(store)


def at(path, value):
    """A change setting the item of `path` (an index, then keys) to `value`."""
    def f(objs):
        target = objs
        for k in path[:-1]:
            target = target[k]
        target[path[-1]] = value
    return f


class TestWorkGates:
    """The work sidecar gates (`-k work_sidecar`), each with a planted failure."""

    def test_work_sidecar_gates_pass_on_a_written_sidecar(self, tmp_path):
        store, problems = work_store(tmp_path)
        assert problems == [] and ql_store.store_problems(store) == []
        assert [p.relative_to(store).as_posix() for p in ql_store.work_files(store)] == [f"work/2026-09/{WORK_RUN}.jsonl"]
        assert ql_store.run_ids(store) == [WORK_RUN]
        head = jsonl(ql_store.work_files(store)[0])[0]
        assert head == {"run": WORK_RUN, "reader": 1, "counts": {"items": 2, "shared": 1, "missing": 0}}

    def test_work_sidecar_an_item_line_of_routed_subagent_counts_only_passes(self, tmp_path):
        """An item no prompt of its own reached, only a subagent routed to it: prompts 0, an empty main, a sub."""
        sub = {"kb-lookup": {"claude-haiku-4-5-20251001": HAIKU}}
        lines = work_lines()[:1] + [{"item": WORK_B, "prompts": 0, "main": {}, "sub": sub}]
        store, problems = work_store(tmp_path, lines=lines)
        assert problems == [] and ql_store.store_problems(store) == []

    def test_work_sidecar_not_written_without_a_line(self, tmp_path):
        assert ql_store.write_work(tmp_path / "store", WORK_RUN, [], 0, 1) is None
        assert not (tmp_path / "store").exists()

    @pytest.mark.parametrize("change,needle", [
        (at([0, "session_id"], "3f2a4c1e-0000-4000-8000-00000000abcd"), "a work header is exactly"),
        (at([0, "run"], "20260928T120000Z-0000ffff"), "run id does not name this file"),
        (at([0, "reader"], 0), "reader is not a version number"),
        (at([0, "reader"], "1"), "reader is not a version number"),
        (at([0, "counts"], {"items": 2, "shared": 1}), "counts are not items, shared, missing"),
        (at([0, "counts", "missing"], -1), "counts are not items, shared, missing"),
        (at([0, "counts", "items"], 3), "counts.items is 3, the file has 2"),
        (at([0, "counts", "shared"], 0), "counts.shared is 0, the file has 1"),
        (at([1, "session_id"], "3f2a4c1e-0000-4000-8000-00000000abcd"), "fields a work line never has: session_id"),
        (at([1, "prompt_id"], "p1"), "fields a work line never has: prompt_id"),
        (at([1, "command"], "backlog.py claim TK-aaaaaaaa --by me"), "fields a work line never has: command"),
        (at([1, "start"], 5), "fields a work line never has: start"),
        (at([1, "steps"], []), "fields a work line never has: steps"),
        (at([1, "item"], "build the report for the payroll team"), "item is not an item id"),
        (at([1, "item"], "TK-AAAAAAAA"), "item is not an item id"),
        (at([3, "items"], [WORK_B, WORK_A]), "items are not sorted, each once"),
        (at([3, "items"], [WORK_A, WORK_A]), "items are not sorted, each once"),
        (at([3, "items"], []), "items are not a list of item ids"),
        (at([3, "items"], WORK_A), "items are not a list of item ids"),
        (at([3, "items"], ["TK-aaaaaaaa; rm -rf /"]), "items are not a list of item ids"),
        (at([1, "prompts"], 0), "an item line with no prompt holds an empty main and a sub"),
        (at([2, "prompts"], 0), "an item line with no prompt holds an empty main and a sub"),
        (at([2], {"item": WORK_B, "prompts": 0, "main": {}}), "an item line with no prompt holds an empty main and a sub"),
        (at([2], {"item": WORK_B, "prompts": 0, "main": {}, "sub": {"payroll-agent": {"claude-opus-5-5": OPUS}}}),
         "is not an agent group"),
        (at([2], {"item": WORK_B, "prompts": 0, "main": {}, "sub": {}}), "sub is not a map of agent groups"),
        (at([2], {"item": WORK_B, "prompts": 0.0, "main": {}, "sub": {"kb-lookup": {"claude-haiku-4-5-20251001": HAIKU}}}),
         "prompts is not a positive count"),
        (at([3, "prompts"], 0), "prompts is not a positive count"),
        (at([3, "main"], {}), "not a map of model ids to counts"),
        (at([1, "prompts"], -1), "prompts is not a positive count"),
        (at([1, "prompts"], True), "prompts is not a positive count"),
        (at([1, "prompts"], "3"), "prompts is not a positive count"),
        (at([1, "main"], {}), "not a map of model ids to counts"),
        (at([1, "main"], {"jan.kowalski@corp.example.com": OPUS}), "is not a model id"),
        (at([1, "main", "claude-opus-5-5", "in"], -1), "as counts"),
        (at([1, "main", "claude-opus-5-5", "note"], 1), "as counts"),
        (at([1, "main", "claude-opus-5-5", "cw1h"], 999999), "cw1h of 'claude-opus-5-5' exceeds cw"),
        (at([1, "sub"], {"payroll-agent": {"claude-opus-5-5": OPUS}}), "is not an agent group"),
        (at([1, "sub"], {}), "sub is not a map of agent groups"),
        (lambda o: o[1].pop("main"), "not a map of model ids to counts"),
        (lambda o: o[1].pop("prompts"), "prompts is not a positive count"),
        (lambda o: o[1].pop("item"), "a work line has an `item` or an `items`"),
        (lambda o: o[1].update(items=[WORK_A]), "a work line has an `item` or an `items`"),
    ])
    def test_work_sidecar_planted(self, tmp_path, change, needle):
        problems = work_store(tmp_path, change)[1]
        assert any(needle in p for p in problems), problems

    def test_work_sidecar_an_item_twice_in_a_file(self, tmp_path):
        def twice(objs):
            objs[2]["item"] = WORK_A
        problems = work_store(tmp_path, twice)[1]
        assert any(f"duplicate item {WORK_A} (also work/2026-09/{WORK_RUN}.jsonl:2)" in p for p in problems), problems

    def test_work_sidecar_the_same_item_in_two_runs_is_fine(self, tmp_path):
        store, _ = work_store(tmp_path)
        other = "20260929T120000Z-0000abcd"
        golden_store(store, [{**jsonl(FIXTURES / "golden.jsonl")[0], "run": other,
                              "counts": {"entries": 0, "dropped": 0, "waiting": 0}}], name=other)
        ql_store.write_work(store, other, work_lines()[:1], 0, 1)
        assert ql_store.store_problems(store) == []

    def test_work_sidecar_no_run_file_beside_it(self, tmp_path):
        problems = work_store(tmp_path, layout=lambda s: (s / "2026-09" / f"{WORK_RUN}.jsonl").unlink())[1]
        assert any(f"no run file {WORK_RUN} beside it" in p for p in problems), problems

    def test_work_sidecar_in_the_wrong_month_directory(self, tmp_path):
        def move(store):
            src = store / "work" / "2026-09" / f"{WORK_RUN}.jsonl"
            (store / "work" / "2026-10").mkdir()
            src.rename(store / "work" / "2026-10" / src.name)
        problems = work_store(tmp_path, layout=move)[1]
        assert any("run id does not name this file" in p for p in problems), problems

    def test_work_sidecar_empty_and_not_json(self, tmp_path):
        problems = work_store(tmp_path, layout=lambda s: (s / "work" / "2026-09" / f"{WORK_RUN}.jsonl").write_text(
            "", encoding="utf-8"))[1]
        assert any("empty work sidecar" in p for p in problems), problems
        problems = work_store(tmp_path / "b", layout=lambda s: (s / "work" / "2026-09" / f"{WORK_RUN}.jsonl").write_text(
            "not json\n", encoding="utf-8"))[1]
        assert any("not a work sidecar" in p for p in problems), problems

    def test_work_sidecar_check_runs_the_gates_and_the_leak_scan(self, tmp_path):
        store, _ = work_store(tmp_path)
        p = subprocess.run([sys.executable, QL, "check", str(store)], capture_output=True, text=True, encoding="utf-8",
                            timeout=120)
        assert (p.returncode, p.stdout) == (0, "querylog check: problems=0\n"), p.stdout
        assert ql_store.leak_problems(store, [f"work/2026-09/{WORK_RUN}.jsonl"]) == []
        bad, _ = work_store(tmp_path / "bad", at([1, "session_id"], "x"))
        p = subprocess.run([sys.executable, QL, "check", str(bad)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert p.returncode == 1 and "fields a work line never has: session_id" in p.stdout, p.stdout
        # planted: an address in a field the gates do not read is still found by the leak scan
        objs = jsonl(ql_store.work_files(bad)[0])
        objs[1]["note"] = "anna.nowak" + "@" + "acme-corp.pl"
        ql_store.work_files(bad)[0].write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8")
        (hit,) = ql_store.leak_problems(bad, [f"work/2026-09/{WORK_RUN}.jsonl"])
        assert hit == f"work/2026-09/{WORK_RUN}.jsonl:2: the leak scan flags an identifier (email)", hit


def overhead_lines():
    """The work lines with the distill's overhead line after them."""
    return work_lines() + [ql_store.overhead_line("distill", 2, {"claude-haiku-4-5-20251001": HAIKU})]


class TestOverheadGates:
    """The overhead line of the work sidecar (`-k overhead_sidecar`): one per kind of the kb's own background runs,
    with no item, session, prompt or text, each gate with a planted failure."""

    def test_overhead_sidecar_gates_pass_beside_item_lines(self, tmp_path):
        store, problems = work_store(tmp_path, lines=overhead_lines())
        assert problems == [] and ql_store.store_problems(store) == []
        objs = jsonl(ql_store.work_files(store)[0])
        assert objs[0] == {"run": WORK_RUN, "reader": 1,
                           "counts": {"items": 2, "shared": 1, "missing": 0, "overhead": 1}}
        assert objs[4] == {"overhead": "distill", "calls": 2, "main": {"claude-haiku-4-5-20251001": HAIKU}}

    def test_overhead_sidecar_alone_and_one_line_per_kind(self, tmp_path):
        two = [ql_store.overhead_line(k, 1, {"claude-haiku-4-5-20251001": HAIKU}) for k in ("distill", "eval")]
        store, problems = work_store(tmp_path, lines=two)
        assert problems == [] and jsonl(ql_store.work_files(store)[0])[0]["counts"] == {
            "items": 0, "shared": 0, "missing": 0, "overhead": 2}

    def test_overhead_sidecar_without_a_line_has_no_overhead_count(self, tmp_path):
        store, _ = work_store(tmp_path)
        assert "overhead" not in jsonl(ql_store.work_files(store)[0])[0]["counts"]

    def test_overhead_sidecar_line_builder_refuses_what_the_gates_refuse(self):
        counts = {"claude-haiku-4-5-20251001": HAIKU}
        assert ql_store.overhead_line("distill", 1, {}) is None
        assert ql_store.overhead_line("backup", 1, counts) is None
        assert ql_store.overhead_line("distill", 0, counts) is None
        assert ql_store.overhead_line("distill", 1, {"claude-haiku-4-5-20251001": {**HAIKU, "in": -1}}) is None
        assert ql_store.overhead_line("distill", 1, counts)["main"] == counts

    @pytest.mark.parametrize("change,needle", [
        # an item, session or prompt id, or any text on the line
        (at([4, "item"], WORK_A), "a work line has an `item` or an `items` or an `overhead`"),
        (at([4, "items"], [WORK_A]), "a work line has an `item` or an `items` or an `overhead`"),
        (at([4, "session_id"], "3f2a4c1e-0000-4000-8000-00000000abcd"), "fields an overhead line never has: session_id"),
        (at([4, "prompt_id"], "p1"), "fields an overhead line never has: prompt_id"),
        (at([4, "prompts"], 1), "fields an overhead line never has: prompts"),
        (at([4, "sub"], {"kb-lookup": {"claude-haiku-4-5-20251001": HAIKU}}), "fields an overhead line never has: sub"),
        (at([4, "text"], "judged the question of anna.nowak"), "fields an overhead line never has: text"),
        (at([4, "command"], "querylog.py distill --session abc"), "fields an overhead line never has: command"),
        # an unknown kind
        (at([4, "overhead"], "backup"), "overhead is not a background run kind"),
        (at([4, "overhead"], "TK-aaaaaaaa"), "overhead is not a background run kind"),
        (at([4, "overhead"], ""), "overhead is not a background run kind"),
        (at([4, "overhead"], ["distill"]), "overhead is not a background run kind"),
        # a count that is not one
        (at([4, "calls"], 0), "calls is not a positive count"),
        (at([4, "calls"], -1), "calls is not a positive count"),
        (at([4, "calls"], True), "calls is not a positive count"),
        (at([4, "calls"], "2"), "calls is not a positive count"),
        (lambda o: o[4].pop("calls"), "calls is not a positive count"),
        (at([4, "main", "claude-haiku-4-5-20251001", "in"], -1), "as counts"),
        (at([4, "main", "claude-haiku-4-5-20251001", "out"], True), "as counts"),
        (at([4, "main", "claude-haiku-4-5-20251001", "cr"], "5"), "as counts"),
        (at([4, "main", "claude-haiku-4-5-20251001", "requests"], 1.5), "as counts"),
        # counts in a malformed shape
        (lambda o: o[4].pop("main"), "not a map of model ids to counts"),
        (at([4, "main"], {}), "not a map of model ids to counts"),
        (at([4, "main"], [HAIKU]), "not a map of model ids to counts"),
        (at([4, "main"], {"jan.kowalski@corp.example.com": HAIKU}), "is not a model id"),
        (at([4, "main", "claude-haiku-4-5-20251001"], {"requests": 1, "in": 1}), "as counts"),
        (at([4, "main", "claude-haiku-4-5-20251001", "note"], 1), "as counts"),
        (at([4, "main", "claude-haiku-4-5-20251001", "cw1h"], 999999), "cw1h of 'claude-haiku-4-5-20251001' exceeds cw"),
        # the header's count
        (at([0, "counts"], {"items": 2, "shared": 1, "missing": 0}), "counts are not items, shared, missing, overhead"),
        (at([0, "counts", "overhead"], 2), "counts.overhead is 2, the file has 1"),
        (at([0, "counts", "overhead"], -1), "counts are not items, shared, missing, overhead"),
    ])
    def test_overhead_sidecar_planted(self, tmp_path, change, needle):
        problems = work_store(tmp_path, change, lines=overhead_lines())[1]
        assert any(needle in p for p in problems), problems

    def test_overhead_sidecar_a_kind_twice_in_a_file(self, tmp_path):
        lines = overhead_lines() + [ql_store.overhead_line("distill", 1, {"claude-haiku-4-5-20251001": HAIKU})]
        problems = work_store(tmp_path, lines=lines)[1]
        assert any(f"duplicate overhead distill (also work/2026-09/{WORK_RUN}.jsonl:5)" in p for p in problems), problems

    def test_overhead_sidecar_count_in_a_header_without_a_line(self, tmp_path):
        problems = work_store(tmp_path, at([0, "counts", "overhead"], 1))[1]
        assert any("counts are not items, shared, missing as counts" in p for p in problems), problems

    def test_overhead_sidecar_check_runs_the_gates(self, tmp_path):
        store, _ = work_store(tmp_path, lines=overhead_lines())
        p = subprocess.run([sys.executable, QL, "check", str(store)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert (p.returncode, p.stdout) == (0, "querylog check: problems=0\n"), p.stdout
        bad, _ = work_store(tmp_path / "bad", at([4, "item"], WORK_A), lines=overhead_lines())
        p = subprocess.run([sys.executable, QL, "check", str(bad)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert p.returncode == 1 and "a work line has an `item` or an `items` or an `overhead`" in p.stdout, p.stdout

    def test_overhead_sidecar_does_not_make_the_cost_report_skip_the_file(self, tmp_path):
        """backlog.py cost skips a sidecar that breaks a work gate whole: a valid overhead line must not."""
        import bl_cost
        store, problems = work_store(tmp_path, lines=overhead_lines())
        assert problems == []
        root = tmp_path / "root"
        (root / "kb").mkdir(parents=True)
        store.rename(root / "kb" / "_querylog")
        lines, skipped = bl_cost.cost_lines(root, None)
        assert skipped == [] and {ln["item"] for ln in lines if "item" in ln} == {WORK_A, WORK_B}


REWORK_PART = {"requests": 1, "in": 2, "cw": 600, "cw1h": 600, "cr": 5000, "out": 70}  # a part of OPUS


def rework_lines():
    """The first item line of work_lines with a `rework` block that is a part of its counts."""
    first = {**work_lines()[0], "rework": {"prompts": 1, "main": {"claude-opus-5-5": REWORK_PART},
                                           "sub": {"kb-lookup": {"claude-haiku-4-5-20251001": HAIKU}}}}
    return [first] + work_lines()[1:]


class TestWorkReworkGates:
    """The `rework` block of an item line (`-k work_rework`): optional, a part of the line's counts, each gate with a
    planted failure."""

    def test_work_rework_gates_pass_with_and_without_the_block(self, tmp_path):
        store, problems = work_store(tmp_path, lines=rework_lines())
        assert problems == [] and ql_store.store_problems(store) == []
        assert "rework" in jsonl(ql_store.work_files(store)[0])[1]
        store, problems = work_store(tmp_path / "old")  # a sidecar written before the block existed
        assert problems == [] and all("rework" not in w for w in jsonl(ql_store.work_files(store)[0]))

    def test_work_rework_a_block_of_routed_subagent_counts_only_passes(self, tmp_path):
        sub = {"kb-lookup": {"claude-haiku-4-5-20251001": HAIKU}}
        lines = [{"item": WORK_A, "prompts": 0, "main": {}, "sub": sub, "rework": {"prompts": 0, "main": {}, "sub": sub}}]
        assert work_store(tmp_path, lines=lines)[1] == []

    def test_work_rework_a_line_keeps_a_block_with_a_prompt_or_a_subagent_only(self):
        tally = ql_store.new_tally()
        assert "rework" not in ql_store.work_line("item", WORK_A, tally, ql_store.new_tally())
        ql_store.tally_add(tally, ({"claude-opus-5-5": OPUS}, {}))
        line = ql_store.work_line("item", WORK_A, tally, tally)
        assert line["rework"] == {"prompts": 1, "main": {"claude-opus-5-5": OPUS}}
        assert ql_store.work_line_problems(line, "x") == []

    @pytest.mark.parametrize("change,needle", [
        (at([1, "rework"], "yes"), "rework is not a block of counts"),
        (at([1, "rework"], [1]), "rework is not a block of counts"),
        (at([1, "rework", "session_id"], "3f2a4c1e-0000-4000-8000-00000000abcd"), "rework has fields it never has"),
        (at([1, "rework", "item"], WORK_A), "rework has fields it never has: item"),
        (at([1, "rework", "prompts"], 0), "rework: an item line with no prompt holds an empty main and a sub"),
        (at([1, "rework", "prompts"], -1), "rework: prompts is not a positive count"),
        (at([1, "rework", "prompts"], "1"), "rework: prompts is not a positive count"),
        (lambda o: o[1]["rework"].pop("prompts"), "rework: prompts is not a positive count"),
        (lambda o: o[1]["rework"].pop("main"), "rework: main: not a map of model ids to counts"),
        (at([1, "rework", "main"], {"jan.kowalski@corp.example.com": REWORK_PART}), "is not a model id"),
        (at([1, "rework", "main", "claude-opus-5-5", "in"], -1), "as counts"),
        (at([1, "rework", "sub"], {"payroll-agent": {"claude-haiku-4-5-20251001": HAIKU}}), "is not an agent group"),
        (at([1, "rework", "prompts"], 4), "rework prompts exceed the line's"),
        (at([1, "rework", "main", "claude-opus-5-5", "out"], 171), "main counts of 'claude-opus-5-5' exceed the line's"),
        (at([1, "rework", "main"], {"claude-haiku-4-5-20251001": REWORK_PART}),
         "main counts of 'claude-haiku-4-5-20251001' exceed"),
        (at([1, "rework", "sub", "kb-lookup", "claude-haiku-4-5-20251001", "cr"], 1), "sub 'kb-lookup' counts of"),
        (at([1, "rework", "sub"], {"Explore": {"claude-haiku-4-5-20251001": HAIKU}}), "sub 'Explore' counts of"),
        (at([1, "item"], "SP-aaaaaaaa"), "a sprint's line has no rework"),
        (at([3, "rework"], {"prompts": 1, "main": {"claude-opus-5-5": REWORK_PART}}), "fields a work line never has: rework"),
        (at([2, "rework"], {"prompts": 2, "main": {"claude-opus-5-5": REWORK_PART}}), "rework prompts exceed the line's"),
    ])
    def test_work_rework_planted(self, tmp_path, change, needle):
        problems = work_store(tmp_path, change, lines=rework_lines())[1]
        assert any(needle in p for p in problems), problems

    def test_work_rework_check_runs_the_gates(self, tmp_path):
        store, _ = work_store(tmp_path, lines=rework_lines())
        p = subprocess.run([sys.executable, QL, "check", str(store)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert (p.returncode, p.stdout) == (0, "querylog check: problems=0\n"), p.stdout
        bad, _ = work_store(tmp_path / "bad", at([1, "rework", "prompts"], 9), lines=rework_lines())
        p = subprocess.run([sys.executable, QL, "check", str(bad)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert p.returncode == 1 and "rework prompts exceed the line's" in p.stdout, p.stdout


OPS_RUN = RUN_ID
OPS_ROWS = [
    {"id": "11111111-1111-4111-8111-111111111111", "ts": "2026-09-28T11:00:00.000Z", "event": "land.step",
     "item": "ST-aaaaaaaa", "step": "rebase", "exit": 0, "ms": 1200},
    {"id": "22222222-2222-4222-8222-222222222222", "ts": "2026-09-28T11:00:05.000Z", "event": "test.run",
     "mode": "changed", "ms": 90000, "exit": 1, "selected": 3, "total": 120, "workers": 4, "failed": 1,
     "slow": [{"file": "test_ql_store.py", "ms": 41000}], "failed_files": ["test_ql_store.py"]},
    {"id": "33333333-3333-4333-8333-333333333333", "ts": "2026-09-28T11:00:09.000Z", "event": "done.refused",
     "item": "ST-aaaaaaaa", "reasons": ["check-failed", "uncommitted"], "ms": 30, "checks": ["tests-ops-sidecar"]},
]


def ops_store(tmp_path, change=None, rows=None, layout=None):
    """The golden run file with an ops sidecar of `rows` (default OPS_ROWS, written by write_ops): `change(objects)`
    edits its header and lines, `layout(store)` the files. (the store, the ops problems)."""
    store = golden_store(tmp_path / "store")
    ql_store.write_ops(store, OPS_RUN, [ql_store.ops_line(r) for r in (rows or OPS_ROWS)])
    path = ql_store.ops_files(store)[0]
    objs = jsonl(path)
    if change:
        change(objs)
    path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
    if layout:
        layout(store)
    return store, ql_store.ops_sidecar_problems(store)


def ops_path(store):
    return store / "ops" / "2026-09" / f"{OPS_RUN}.jsonl"


def secret_shaped():
    return "glpat" + "-" + "a" * 20  # a token the leak scan flags, built here so this file holds none


class TestOpsGates:
    """The ops sidecar gates (`-k ops_sidecar`), each with a planted failure."""

    def test_ops_sidecar_gates_pass_on_a_written_sidecar(self, tmp_path):
        store, problems = ops_store(tmp_path)
        assert problems == [] and ql_store.store_problems(store) == []
        assert [p.relative_to(store).as_posix() for p in ql_store.ops_files(store)] == [f"ops/2026-09/{OPS_RUN}.jsonl"]
        assert ql_store.run_ids(store) == [OPS_RUN]
        objs = jsonl(ops_path(store))
        assert objs[0] == {"run": OPS_RUN, "counts": {"rows": 3}} and objs[1:] == OPS_ROWS
        assert ql_store.ops_ids(store) == {r["id"] for r in OPS_ROWS}

    def test_ops_sidecar_not_written_without_a_line(self, tmp_path):
        assert ql_store.write_ops(tmp_path / "store", OPS_RUN, []) is None and not (tmp_path / "store").exists()

    def test_ops_sidecar_a_spool_row_is_its_line(self):
        row = {**OPS_ROWS[0], "surface": "ops", "v": 1}
        assert ql_store.ops_line(row) == OPS_ROWS[0]
        assert list(ql_store.ops_line({**row, "step": "rebase", "exit": 0})) == ["id", "ts", "event", "item", "step", "exit", "ms"]
        for bad in ({**row, "session_id": "x"}, {**row, "event": "land.nothing"}, {**row, "ms": "1"}, {**row, "step": "a b"},
                    {k: v for k, v in row.items() if k != "ts"}, "not a row"):
            assert ql_store.ops_line(bad) is None, bad

    @pytest.mark.parametrize("change,needle", [
        (at([0, "session_id"], "3f2a4c1e-0000-4000-8000-00000000abcd"), "an ops header is exactly"),
        (at([0, "counts"], {"rows": 2}), "counts.rows is 2, the file has 3"),
        (at([0, "counts"], {"rows": "3"}), "counts are not rows as counts"),
        (at([0, "run"], "20260928T120000Z-0000abce"), "run id does not name this file"),
        (at([1, "id"], "ops-1"), "ops id is not a row id"),
        (at([1, "ts"], "yesterday"), "ops ts is not a UTC time"),
        (lambda o: o[1].pop("ts"), "ops ts is not a UTC time"),
        (at([1, "event"], "land.nothing"), "event 'land.nothing' is not one of"),
        (lambda o: o[1].pop("event"), "is not one of"),
        (at([1, "session_id"], "3f2a4c1e-0000-4000-8000-00000000abcd"), "keys event land.step never has: session_id"),
        (at([1, "command"], "backlog.py done ST-aaaaaaaa"), "keys event land.step never has: command"),
        (lambda o: o[1].pop("exit"), "event land.step lacks exit"),
        (at([1, "step"], "fix the rebase and try again"), "step of land.step is not a closed token value"),
        (at([1, "step"], "Rebase"), "step of land.step is not a closed token value"),
        (at([1, "item"], "item 1"), "item of land.step is not a closed item value"),
        (at([1, "ms"], True), "ms of land.step is not a closed ms value"),
        (at([1, "ms"], -5), "ms of land.step is not a closed ms value"),
        (at([1, "exit"], "0"), "exit of land.step is not a closed exit value"),
        (at([2, "mode"], "everything"), "mode of test.run is not a closed mode value"),
        (at([2, "failed_files"], ["test_ql_store.py::test_ops_sidecar"]), "failed_files of test.run is not a closed list value"),
        (at([2, "slow"], [{"file": "_tools/test_ql_store.py", "ms": 5}]), "slow of test.run is not a closed rows value"),
        (at([2, "slow"], [{"file": "test_ql_store.py", "ms": 5, "note": "slow"}]), "slow of test.run is not a closed rows value"),
        (at([2, "selected"], 1.5), "selected of test.run is not a closed count value"),
        (at([3, "reasons"], ["the item was not ready"]), "reasons of done.refused is not a closed list value"),
        (at([3, "checks"], ["Check 1: fix it"]), "checks of done.refused is not a closed list value"),
    ])
    def test_ops_sidecar_planted(self, tmp_path, change, needle):
        problems = ops_store(tmp_path, change)[1]
        assert any(needle in p for p in problems), problems

    def test_ops_sidecar_refuses_free_text(self, tmp_path):
        """free text has no key of its own and no value that passes a closed shape"""
        for key, value, needle in (("step", "I could not rebase because main moved", "step of land.step is not a closed token"),
                                   ("note", "main moved", "keys event land.step never has: note"),
                                   ("summary", "rebase", "keys event land.step never has: summary"),
                                   ("item", "the rebase item", "item of land.step is not a closed item")):
            problems = ops_store(tmp_path / key, at([1, key], value))[1]
            assert any(needle in p for p in problems), problems
        problems = ops_store(tmp_path / "list", at([3, "checks"], ["tests", "it failed because of the network"]))[1]
        assert any("checks of done.refused is not a closed list value" in p for p in problems), problems
        assert all("because of the network" not in p for p in problems)  # a refusal repeats only the start of a value

    def test_ops_sidecar_the_same_row_twice_across_sidecars(self, tmp_path):
        store, _ = ops_store(tmp_path)
        other = "20260929T120000Z-0000abcd"
        golden_store(store, [{**jsonl(FIXTURES / "golden.jsonl")[0], "run": other,
                              "counts": {"entries": 0, "dropped": 0, "waiting": 0}}], name=other)
        ql_store.write_ops(store, other, [OPS_ROWS[0]])
        problems = ql_store.ops_sidecar_problems(store)
        assert any(f"duplicate ops id {OPS_ROWS[0]['id']} (also ops/2026-09/{OPS_RUN}.jsonl:2)" in p for p in problems), problems
        assert ql_store.write_ops(store, other, [{**OPS_ROWS[0], "id": "44444444-4444-4444-8444-444444444444"}])
        assert ql_store.ops_sidecar_problems(store) == []

    def test_ops_sidecar_no_run_file_beside_it(self, tmp_path):
        problems = ops_store(tmp_path, layout=lambda s: (s / "2026-09" / f"{OPS_RUN}.jsonl").unlink())[1]
        assert any(f"no run file {OPS_RUN} beside it" in p for p in problems), problems

    def test_ops_sidecar_in_the_wrong_month_directory(self, tmp_path):
        def move(store):
            (store / "ops" / "2026-10").mkdir()
            ops_path(store).rename(store / "ops" / "2026-10" / ops_path(store).name)
        problems = ops_store(tmp_path, layout=move)[1]
        assert any("run id does not name this file" in p for p in problems), problems

    def test_ops_sidecar_empty_and_not_json(self, tmp_path):
        problems = ops_store(tmp_path, layout=lambda s: ops_path(s).write_text("", encoding="utf-8"))[1]
        assert any("empty ops sidecar" in p for p in problems), problems
        problems = ops_store(tmp_path / "b", layout=lambda s: ops_path(s).write_text("not json\n", encoding="utf-8"))[1]
        assert any("not an ops sidecar" in p for p in problems), problems

    def test_ops_sidecar_the_leak_scan_finds_an_identifier_that_has_the_shape_of_a_name(self, tmp_path):
        """a secret-shaped value is a valid `token`: only the leak scan stops it, in check and in the push's scan"""
        assert ql_capture_token_ok(secret_shaped())
        store, problems = ops_store(tmp_path, at([1, "step"], secret_shaped()))
        assert problems and all("the leak scan flags an identifier (secret)" in p for p in problems), problems
        rel = f"ops/2026-09/{OPS_RUN}.jsonl"
        assert ql_store.leak_problems(store, [rel]) == [f"{rel}:2: the leak scan flags an identifier (secret)"]
        assert ql_store.ops_line_leaks(jsonl(ops_path(store))[1]) == ["secret"]
        assert ql_store.ops_line_leaks(OPS_ROWS[0]) == []

    def test_ops_sidecar_check_runs_the_gates(self, tmp_path):
        store, _ = ops_store(tmp_path)
        p = subprocess.run([sys.executable, QL, "check", str(store)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert (p.returncode, p.stdout) == (0, "querylog check: problems=0\n"), p.stdout
        for n, change in enumerate((at([1, "step"], "fix it now"), at([1, "step"], secret_shaped()))):
            bad, _ = ops_store(tmp_path / f"bad{n}", change)
            p = subprocess.run([sys.executable, QL, "check", str(bad)], capture_output=True, text=True,
                               encoding="utf-8", timeout=120)
            assert p.returncode == 1 and ("is not a closed token value" in p.stdout or "leak scan flags" in p.stdout), p.stdout


def ql_capture_token_ok(value):
    import ql_capture
    return ql_capture.OPS_KINDS["token"](value)
