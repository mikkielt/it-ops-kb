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
