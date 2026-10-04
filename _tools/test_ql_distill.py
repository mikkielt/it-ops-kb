"""Query log tests, distill (kb/_self/querylog.md, Distill; `python3 _tools/tests.py -k TestDistill`, and the other classes below).

  TestDistill       the fixture spool (_tools/fixtures/querylog/spool/) and the recorded Haiku reply file give the
                    golden run file (golden.jsonl): a header with run id, pipeline and retrieval versions and kb
                    commit, entries without them; only rule-redacted text reaches Haiku; nothing raw in the run
                    file; a flagged entry and a malformed reply's batch are dropped and only counted; over the batch,
                    run and daily caps entries wait in the spool; a failed call leaves its entries waiting; a second
                    run on the same spool writes nothing; an entry's question is the kb's own (a work prompt with a
                    name and private context and a generic kb_pack question store the pack's question and no word of
                    the prompt or the reply), its citations are the path:line of the kb lines the reply named, else
                    the pack's first ones; Haiku's free text is ignored; a kb prompt with no kb call has no question
  TestSpoolFormats  the compat spool (_tools/fixtures/querylog/compat/: one row per row format capture has written,
                    per surface) and its recorded Haiku reply distill to a run file that passes `check`, with nothing
                    dropped; format 0 kb rows without `lines` get pack's lines of their recorded articles only
                    (`cited: pack`), and an entry with no citation keeps no articles; a planted row of each shape;
                    an unknown future `v` and malformed rows are skipped and counted; a second distill writes nothing
  TestWorkSidecar   distill writes the work sidecar beside the run file (`-k work_sidecar`): one line per item with the
                    prompts of its claim-to-done-or-release window summed (kb prompts or not; a prompt in several
                    windows counts once, on the line of their sprint) and one shared line per session that worked an
                    item with its prompts outside any window, a run file of no entry when nothing else was written,
                    none for a session that
                    worked no item, a done with no claim or a session still open; `missing` counts window prompts
                    without usage of this reader; a usage record outside the closed shape is not counted; the
                    windows are `ql_capture.usage_targets`'; a prompt counted by an earlier run is not counted again
                    (planted: without the record of counted prompts it is); no session, prompt or text in the file
  TestWorkSubagent  a subagent that worked on a work/<id> branch counts on that item's line (`-k work_subagent`), not on
                    the prompt it started under, with no prompt of its own; a prompt in two windows counts once, on
                    the line of their sprint (the sprint of the items' files: sprint_finder), on the session's shared
                    line when the items do not share one or no sprint is known; no duplicate on a second run; routing
                    outside the closed shape (a branch for an id, an unknown group or model) is not counted; the
                    routing is no part of an entry's usage line
  TestWorkRework    an item line's `rework` block (`-k work_rework`): the counts from the prompt of the item's first
                    `refused` row to the end of its window, a part of the line's own counts (work = the line less
                    it); none for an item with no refused row, for a refused row with no open claim or after the
                    window closed, or on a sprint's line; a routed subagent counts by the prompt it started under
  TestOverheadSidecar the counts of the distill's own Haiku calls (`--output-format json`, `modelUsage`) are the run's
                    `distill` overhead line in the work sidecar (`-k overhead_sidecar`): summed over calls and models,
                    no item, session or text, none for an injected Haiku, a result without counts or a failed call
  TestOpsSidecar    distill writes the ops sidecar beside the run file (`-k ops_sidecar`): the `ops` rows of the tools
                    files, in time order, as lines of id, time, event and the event's keys, with no surface or format; a
                    run file of no entry when nothing else was written; a row outside the closed shape or one the leak
                    scan flags is dropped and counted as skipped; a row is read once (the tools file keeps it until
                    its day is over, and `consumed.json` lists it) and, when a sidecar of an earlier run holds its id,
                    written no second time; an ops row joins no prompt, so an entry does not change for it
  TestAgentRows     distill turns each subagent start and stop (the `work` rows capture writes) into one ops `agent.run`
                    line (`-k ops_agent_rows`): the group, the salted hash, the item and the milliseconds between
                    them, the earliest start and latest stop of one agent when SubagentStart fired more than once;
                    an unpaired start or stop, or a stop before its start, is skipped and counted in the run header,
                    never written; a row with a raw agent id or free text is dropped; a session still open waits; a
                    pair is written once
  TestLock         a second distill exits on the lock (exit 3) and changes nothing; a stale lock is taken over;
                    of several processes taking the lock at once exactly one gets it
  TestLaunch        SessionEnd marks its session closed; the launcher returns within the 1.5-second budget with its
                    pipes free, and the distill it starts writes its run file after the launcher exited, also when
                    the launcher's process group is killed (POSIX) or its Windows job object closes with
                    kill-on-close (Windows only); SessionStart picks up closed sessions only, and starts nothing when
                    none is closed
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The helpers the classes share are in
ql_testkit.py.
"""
import datetime, getpass, json, os, re, shutil, signal, socket, subprocess, sys, time, uuid
from pathlib import Path

import pytest

import kbusage, ql_base, ql_capture, ql_deliver, ql_distill, ql_learn, ql_store
from conftest import GIT, KB, TOOLS, git_env, querylog_env
from ql_testkit import (auto_config, E, FIXTURES, jsonl, LAPS, load, NOW, plant_spool, plugins_dir, QL, RUN_ID,
                        S_ENDED, S_IDLE, S_OPEN, session_start, SH, SID, spool, store_files)


RAW = ["anna.nowak", "acme", "10." + "1.20.33", "PL-LAPTOP-7731", "it-helpdesk", "Kowalczyk", "Warsaw", "anowak",
       "session_id", "prompt_id", "transcript_path", S_ENDED, S_IDLE, '"pa1"', '"prompt":', '"answer":', "mailed"]


def run_distill(qdir, haiku, now=NOW, run_id=RUN_ID):
    said = []
    rc = ql_distill.distill(qdir=qdir, cfg=Path(qdir) / "config.json", haiku=haiku, now_dt=now, run_id=run_id,
                            kb_commit="0" * 40, out=said.append)
    return rc, said


def echo(prompt):
    """A Haiku stub that judges every entry answered."""
    items = json.loads(prompt[prompt.index("\n\n[") + 2:])
    return json.dumps([{"i": it["i"], "judged": "answered", "best": None, "identifying": False} for it in items])


class TestDistill:
    def test_golden_run_file(self, tmp_path):
        q = tmp_path / "querylog"
        sp = plant_spool(q)
        open_before = (sp / f"{S_OPEN}.jsonl").read_bytes()
        replay = ql_base.Replay(FIXTURES / "haiku.json")
        rc, said = run_distill(q, replay)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=6 dropped=1 waiting=0"], said
        (run,) = store_files(q)
        assert run.relative_to(q / "store").as_posix() == f"2026-09/{RUN_ID}.jsonl"
        got, want = jsonl(run), jsonl(FIXTURES / "golden.jsonl")
        import kbfacts
        want[0]["retrieval"] = kbfacts.INDEX_VERSION
        assert got == want
        assert run.read_bytes().endswith(b"\n") and b"\r" not in run.read_bytes()
        header, entries = got[0], got[1:]
        assert set(header) == set(ql_store.HEADER_KEYS) and header["run"] == RUN_ID
        assert all(not set(e) & set(ql_store.HEADER_KEYS) for e in entries)
        assert ql_store.store_problems(q / "store") == []
        # the spool: the closed sessions and the finished day's tools file are gone, the open session is untouched
        assert sorted(p.name for p in sp.iterdir()) == [f"{S_OPEN}.jsonl"]
        assert (sp / f"{S_OPEN}.jsonl").read_bytes() == open_before

    def test_only_rule_redacted_text_reaches_haiku(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        replay = ql_base.Replay(FIXTURES / "haiku.json")
        run_distill(q, replay)
        (sent,) = replay.prompts
        for raw in ("anna.nowak", "acme-corp", "10." + "1.20.33", "PL-LAPTOP-7731", "it-helpdesk", "ACME\\anowak"):
            assert raw not in sent, raw
        assert "jan.kowalski@corp.example.com" in sent and "PL-LT-00123" in sent
        assert "Kowalczyk" in sent  # names rest on Haiku, which gets them only after the rules
        assert "Warsaw" not in sent  # a prompt that never used the kb is never sent

    def test_nothing_raw_in_the_run_file(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        run_distill(q, ql_base.Replay(FIXTURES / "haiku.json"))
        text = store_files(q)[0].read_text(encoding="utf-8")
        for raw in RAW:
            assert raw not in text, raw
        for who in {getpass.getuser(), socket.gethostname().split(".")[0]} - {""}:
            assert not re.search(rf"(?<![\w-]){re.escape(who)}(?![\w-])", text), who

    def test_doubtful_entry_is_dropped_and_counted(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        run_distill(q, ql_base.Replay(FIXTURES / "haiku.json"))
        header, *entries = jsonl(store_files(q)[0])
        assert header["counts"]["dropped"] == 1
        assert "11111111-0000-4000-8000-0000000000c1" not in {e["id"] for e in entries}  # Haiku flagged it
        planted = tmp_path / "planted"
        plant_spool(planted)
        rc, said = run_distill(planted, lambda prompt: "I cannot help with that.")  # a reply that is not the JSON
        header, *entries = jsonl(store_files(planted)[0])
        assert header["counts"] == {"entries": 2, "dropped": 5, "waiting": 0}, said
        assert {e["surface"] for e in entries} == {"tool_fetch"}

    def test_a_best_article_code_did_not_offer_is_not_kept(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        run_distill(q, ql_base.Replay(FIXTURES / "haiku.json"))
        e = next(e for e in jsonl(store_files(q)[0]) if e.get("id") == "11111111-0000-4000-8000-0000000000b1")
        assert "best" not in e and e["articles"] == ["public/intune/win32-apps.md"]

    def test_the_entry_holds_the_kb_question_not_the_prompt(self, tmp_path):
        """A work prompt with a person's name and private project context, and a kb_pack call with a generic
        question: the entry's question is the pack's (after the rules), its citations the kb lines the reply named,
        and no word of the prompt, of the reply or of Haiku's free text reaches the run file."""
        q = tmp_path / "querylog"
        sp = q / "spool"
        sp.mkdir(parents=True)
        work = ("Anna Nowak owns the Kestrel licence rollout for Globex: check the licence files, the validation "
                "results and the open issues, then tell me where the rollout stands")
        pack = ("coverage: weak (best article matches 2 of 3 key words)\n\n## public/intune/win32-apps.md  Win32 apps\n"
                "- public/intune/win32-apps.md:49 All configured detection rules must be met. [DOC S-wc6e3fba]\n"
                "- public/intune/win32-apps.md:52 A custom detection script must exit 0 and write to STDOUT. "
                "[DOC S-wc6e3fba]\n")
        answer = ("Kestrel's licence check for Globex passes; the detection script rule applies "
                  "(kb/public/intune/win32-apps.md:52). Anna Nowak still has two open issues.")
        rows = [{"id": E("f1"), "ts": "2026-09-27T10:00:00.000Z", "surface": "prompt", "session_id": SID,
                 "prompt_id": "w1", "prompt": work},
                {"id": E("f2"), "ts": "2026-09-27T10:00:05.000Z", "surface": "mcp", "session_id": SID,
                 "prompt_id": "w1", "tool": "kb_pack",
                 "args": {"question": "intune win32 detection script licence file at 10." + "1.20.33"},
                 "verdict": "weak", "articles": ["public/intune/win32-apps.md"], **ql_capture.pack_summary(pack)},
                {"id": E("f3"), "ts": "2026-09-27T10:02:00.000Z", "surface": "stop", "session_id": SID,
                 "prompt_id": "w1", "answer": answer}]
        (sp / f"{SID}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
        (sp / f"{SID}.end").touch()
        free = ("What is the status of the Kestrel licence implementation owned by Anna Nowak at Globex?",
                "The inquiry received a comprehensive answer detailing licence files added and outstanding issues.")

        def stub(prompt):
            items = json.loads(prompt[prompt.index("\n\n[") + 2:])
            return json.dumps([{"i": it["i"], "question": free[0], "summary": free[1], "judged": "answered",
                                "best": "public/intune/win32-apps.md", "identifying": False, "note": free[1]}
                               for it in items])
        rc, said = run_distill(q, stub)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=1 dropped=0 waiting=0"], said
        _, e = jsonl(store_files(q)[0])
        assert e == {"id": E("f1"), "surface": "prompt", "day": "2026-09-27", "tools": ["kb_pack"],
                     "question": "intune win32 detection script licence file at 192.0.2.10", "verdict": "weak",
                     "articles": ["public/intune/win32-apps.md"],
                     "citations": [{"line": "public/intune/win32-apps.md:52", "tag": "DOC", "verdict": "weak"}],
                     "cited": "reply", "judged": "answered", "best": "public/intune/win32-apps.md"}
        text = store_files(q)[0].read_text(encoding="utf-8")
        for word in ("Anna", "Nowak", "Kestrel", "Globex", "rollout", "status", "validation", "issues", "inquiry",
                     "comprehensive", "summary", "10." + "1.20.33"):
            assert word not in text, word
        assert ql_store.store_problems(q / "store") == []

    def test_citations_are_the_packs_first_lines_when_the_reply_names_none(self):
        import redact
        kb = [{"id": E("g2"), "ts": "2026-09-27T10:00:05.000Z", "surface": "mcp", "tool": "kb_pack",
               "args": {"questions": ["windows laps password length", "bitlocker escrow"]},
               "lines": [{"line": f"public/windows/laps.md:{n}", "tag": "DOC", "verdict": "good"} for n in range(20, 28)]
               + [{"line": "the LAPS article", "tag": "DOC"}, "public/windows/laps.md:40"]}]
        rows = [{"id": E("g1"), "ts": "2026-09-27T10:00:00.000Z", "surface": "prompt", "prompt": "how long?"}, *kb,
                {"id": E("g3"), "ts": "2026-09-27T10:01:00.000Z", "surface": "stop", "answer": "It is 14 (laps.md:99)."}]
        entry, judge, drop = ql_distill.entry_of(rows, redact.known())
        assert drop is None and entry["cited"] == "pack" and entry["question"] == "windows laps password length"
        assert [x["line"] for x in entry["citations"]] == [f"public/windows/laps.md:{n}" for n in range(20, 25)]
        assert judge == {"question": "windows laps password length", "prompt": "how long?",
                         "answer": "It is 14 (laps.md:99).", "candidates": []}  # Haiku judges from these; none is stored

    def test_haiku_free_text_is_ignored(self):
        items = [{"i": 0, "candidates": ["public/windows/laps.md"]}, {"i": 1, "candidates": []}]
        reply = json.dumps([{"i": 0, "question": "What does Anna Nowak need?", "summary": "Anna got the steps.",
                             "judged": "answered", "best": "public/windows/laps.md", "identifying": False},
                            {"i": 1, "text": "free", "judged": "missed", "best": "public/other.md",
                             "identifying": False}])
        got = ql_distill.parse_distill(reply, items)
        assert got == [{"judged": "answered", "best": "public/windows/laps.md", "identifying": False},
                       {"judged": "missed", "best": None, "identifying": False}]
        assert [ql_distill.judged(r) for r in got] == [{"judged": "answered", "best": "public/windows/laps.md"},
                                                       {"judged": "missed", "best": None}]
        with pytest.raises(ValueError):  # planted: free text in place of a judgement is no reply
            ql_distill.parse_distill(json.dumps([{"i": 0, "judged": "Anna got the steps", "best": None,
                                                  "identifying": False}, {"i": 1, "judged": "missed", "best": None,
                                                                        "identifying": False}]), items)

    def test_a_kb_intent_without_a_kb_call_has_no_question(self, tmp_path):
        """A /kb-... prompt that made no kb call keeps its fetches (source findings read them) but gets no question
        and no Haiku call, so learn finds no lookup in it."""
        q = tmp_path / "querylog"
        sp = q / "spool"
        sp.mkdir(parents=True)
        rows = [{"id": E("h1"), "ts": "2026-09-27T10:00:00.000Z", "surface": "prompt", "session_id": SID,
                 "prompt_id": "k1", "prompt": "/kb-refresh windows/laps for Anna Nowak's Globex audit",
                 "kb_intent": "skill"},
                {"id": E("h2"), "ts": "2026-09-27T10:00:05.000Z", "surface": "fetch", "session_id": SID,
                 "prompt_id": "k1", "tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/laps",
                 "outcome": "http-200", "chars": 900},
                {"id": E("h3"), "ts": "2026-09-27T10:02:00.000Z", "surface": "stop", "session_id": SID,
                 "prompt_id": "k1", "answer": "Refreshed for Anna Nowak."}]
        (sp / f"{SID}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
        (sp / f"{SID}.end").touch()
        calls = []
        rc, said = run_distill(q, lambda prompt: calls.append(prompt) or "[]")
        assert rc == 0 and calls == [] and said == [f"distill: run={RUN_ID} entries=1 dropped=0 waiting=0"], said
        _, e = jsonl(store_files(q)[0])
        assert e == {"id": E("h1"), "surface": "prompt", "day": "2026-09-27", "intent": "skill",
                     "fetches": [{"tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/laps",
                                  "outcome": "http-200", "n": 1, "chars": 900}]}
        assert not ql_learn.is_miss(e) and ql_learn.host_fetches([(RUN_ID, e)])  # no lookup to learn from; the fetch counts

    def test_an_entry_whose_articles_have_no_kb_lines_keeps_no_articles(self, tmp_path):
        """A row of format 1 whose result held no kb line: the entry is kept without `articles` (an article is stored
        only with the lines that back it), and Haiku still judges among the recorded articles."""
        import redact
        rows = [{"id": E("j1"), "ts": "2026-09-27T10:00:00.000Z", "surface": "kb_hook", "v": 1, "question": "laps",
                 "verdict": "good", "articles": ["public/windows/laps.md"]}]
        entry, judge, drop = ql_distill.entry_of(rows, redact.known())
        assert drop is None and not {"citations", "cited", "articles"} & set(entry) and entry["question"] == "laps"
        assert judge["candidates"] == ["public/windows/laps.md"]
        rows[0]["lines"] = [{"line": "public/windows/laps.md:24", "tag": "DOC", "verdict": "good"}]
        entry, judge, drop = ql_distill.entry_of(rows, redact.known())
        assert drop is None and entry["citations"] == rows[0]["lines"] and judge["question"] == "laps"
        assert entry["articles"] == ["public/windows/laps.md"]

    def test_over_the_caps_entries_wait(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ql_distill, "HAIKU_BATCH_ENTRIES", 2)
        monkeypatch.setattr(ql_distill, "HAIKU_BATCHES_PER_RUN", 1)
        monkeypatch.setattr(ql_distill, "HAIKU_DAILY_CALLS", 2)
        q = tmp_path / "querylog"
        sp = plant_spool(q)
        calls = []

        def stub(prompt):
            calls.append(prompt)
            return echo(prompt)
        rc, said = run_distill(q, stub, run_id="20260928T120000Z-00000001")
        assert said == ["distill: run=20260928T120000Z-00000001 entries=4 dropped=0 waiting=3"] and len(calls) == 1
        assert (sp / f"{S_ENDED}.jsonl").exists() and (sp / f"{S_ENDED}.end").exists()  # its lookups wait
        rc, said = run_distill(q, stub, run_id="20260928T120001Z-00000002")
        assert said[-1].endswith("entries=2 dropped=0 waiting=1") and len(calls) == 2
        rc, said = run_distill(q, stub, run_id="20260928T120002Z-00000003")
        assert said == ["distill: nothing to write (waiting=1)"] and len(calls) == 2  # the daily cap
        rc, said = run_distill(q, stub, now=NOW + datetime.timedelta(days=1), run_id="20260929T120000Z-00000004")
        # the last waiting lookup, and S_OPEN's: a day idle, it now counts as closed
        assert said[-1].endswith("entries=2 dropped=0 waiting=0") and len(calls) == 3
        ids = [e["id"] for f in store_files(q) for e in jsonl(f)[1:]]
        assert len(ids) == len(set(ids)) == 8
        assert list(sp.iterdir()) == []
        assert ql_store.store_problems(q / "store") == []

    def test_a_failed_call_leaves_its_entries_waiting(self, tmp_path):
        q = tmp_path / "querylog"
        sp = plant_spool(q)
        before = {p.name: p.read_bytes() for p in sp.iterdir()}

        def down(prompt):
            raise OSError("no network")
        rc, said = run_distill(q, down)
        assert rc == 0 and said[-1].endswith("entries=2 dropped=0 waiting=5"), said
        assert (sp / f"{S_IDLE}.jsonl").read_bytes() == before[f"{S_IDLE}.jsonl"]
        kept = [r["prompt_id"] for r in jsonl(sp / f"{S_ENDED}.jsonl")]
        assert sorted(set(kept)) == ["pa1", "pa2", "pa3"]  # the prompt that never used the kb is gone already
        assert len(kept) == len(jsonl(FIXTURES / "spool" / f"{S_ENDED}.jsonl")) - 1
        rc, said = run_distill(q, ql_base.Replay(FIXTURES / "haiku.json"), run_id="20260928T120500Z-0000abce")
        assert said[-1].endswith("entries=4 dropped=1 waiting=0"), said
        ids = [e["id"] for f in store_files(q) for e in jsonl(f)[1:]]
        assert len(ids) == len(set(ids)) == 6

    def test_a_second_run_on_the_same_spool_writes_nothing(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        run_distill(q, ql_base.Replay(FIXTURES / "haiku.json"))
        files = {p: p.read_bytes() for p in store_files(q)}
        rc, said = run_distill(q, echo, run_id="20260928T130000Z-0000abcf")
        assert rc == 0 and said == ["distill: nothing to write (waiting=0)"]
        assert {p: p.read_bytes() for p in store_files(q)} == files

    @pytest.mark.parametrize("config,marker", [('{"mode": "off"}', False), ("{broken", False), (None, True)])
    def test_off_or_disabled_distills_nothing(self, tmp_path, config, marker):
        q = tmp_path / "querylog"
        sp = plant_spool(q)
        if config:
            (q / "config.json").write_text(config, encoding="utf-8")
        if marker:
            (q / "DISABLED").write_text("", encoding="utf-8")
        rc, said = run_distill(q, echo)
        assert (rc, said, store_files(q)) == (0, ["distill: logging is off"], [])
        assert (sp / f"{S_ENDED}.jsonl").exists()


COMPAT = FIXTURES / "compat"  # one spool row per row format capture has written, per surface
S_COMPAT = "bbbbbbbb-0000-4000-8000-000000000001"
SHAPES = json.loads((COMPAT / "shapes.json").read_text(encoding="utf-8"))  # {row id: the shape it stands for}
SHAPE_ROWS = {shape: rid for rid, shape in reversed(list(SHAPES.items()))}  # {shape: its first row id}


def plant_compat(qdir, extra_session=(), extra_tools=()):
    """The compat spool under qdir/spool, its session ended an hour before NOW, plus raw lines appended to the
    session file and to the tools file."""
    sp = Path(qdir) / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    for f in (COMPAT / "spool").iterdir():
        more = extra_tools if f.name.startswith("tools-") else extra_session
        (sp / f.name).write_text(f.read_text(encoding="utf-8") + "".join(ln + "\n" for ln in more),
                                 encoding="utf-8", newline="\n")
        os.utime(sp / f.name, (NOW.timestamp() - 3600,) * 2)
    (sp / f"{S_COMPAT}.end").touch()
    return sp


def compat_rows():
    out = []
    for f in sorted((COMPAT / "spool").iterdir()):
        out += jsonl(f)
    return out


class TestSpoolFormats:
    """Every spool row format capture has written distills: rows without `v` (format 0) with or without `lines`,
    `verdicts`, `kb_intent`, `chars`, host and path; rows cut to their ids; rows of format 1. A row distill cannot
    read is skipped and counted."""

    def test_the_compat_spool_distills_and_passes_check(self, tmp_path):
        q = tmp_path / "querylog"
        sp = plant_compat(q)
        rc, said = run_distill(q, ql_base.Replay(COMPAT / "haiku.json"))
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=17 dropped=0 waiting=0"], said
        (run,) = store_files(q)
        header, *entries = jsonl(run)
        assert header["pipeline"] == ql_base.PIPELINE_VERSION and "skipped" not in header["counts"]
        assert ql_store.store_problems(q / "store") == []
        p = subprocess.run([sys.executable, QL, "check", str(q / "store")], capture_output=True, text=True,
                           encoding="utf-8", timeout=300)
        assert p.returncode == 0, p.stdout + p.stderr
        assert list(sp.iterdir()) == []  # the closed session and the finished day are distilled
        by = {e["id"]: e for e in entries}
        kept = {r["id"] for r in compat_rows() if r.get("surface") == "prompt" and r.get("prompt_id") != "pj"}
        kept |= {r["id"] for r in compat_rows() if "session_id" not in r}
        assert set(by) == kept  # every lookup is an entry; the prompt that never used the kb is none
        rows = {r["id"]: r for r in compat_rows()}
        for e in entries:
            assert not {"verdicts", "chars", "v", "cut", "answer", "prompt"} & set(e) or e["surface"] == "tool_fetch"
            for f in e.get("fetches", []):
                assert set(f) <= set(ql_store.FETCH_KEYS)
        # format 0 kb rows without `lines`: pack re-ran their own questions, lines of their recorded articles only
        for pid, article in (("pa", LAPS), ("pb", "public/intune/win32-apps.md")):
            e = next(e for i, e in by.items() if rows[i].get("prompt_id") == pid)
            assert e["cited"] == "pack" and e["articles"] == [article], e
            assert e["citations"] and all(x["line"].rsplit(":", 1)[0] == article for x in e["citations"])
        # no line of the recorded article (format 0), and no line in the result (format 1): kept without articles
        for pid in ("pc", "pk"):
            e = next(e for i, e in by.items() if rows[i].get("prompt_id") == pid)
            assert e["question"] and not {"articles", "citations", "cited"} & set(e), e
        pk = next(e for i, e in by.items() if rows[i].get("prompt_id") == "pk")
        assert pk["best"] == LAPS  # Haiku judged among the recorded articles
        # format 0 rows with `lines` keep their own: the reply named one
        pf = next(e for i, e in by.items() if rows[i].get("prompt_id") == "pf")
        assert (pf["cited"], pf["citations"]) == ("reply", [{"line": f"{LAPS}:25", "tag": "DOC", "verdict": "good"}])
        # a fetch row without chars, host or path keeps what it has
        pb = next(e for i, e in by.items() if rows[i].get("prompt_id") == "pb")
        assert all("chars" not in f for f in pb["fetches"])
        assert {"tool": "mcp__microsoft-learn__microsoft_docs_search", "outcome": "unknown", "n": 1} in pb["fetches"]
        # rows cut to their ids give an entry of the day alone
        pi = next(e for i, e in by.items() if rows[i].get("prompt_id") == "pi")
        assert set(pi) == {"id", "surface", "day"}

    def test_a_second_distill_writes_nothing_new(self, tmp_path):
        """Convergence, in mode local (the spool rows go) and with the rows kept for delivery (mode auto): the
        entries a run file holds are not distilled again, pack's re-run included."""
        q = tmp_path / "querylog"
        plant_compat(q)
        run_distill(q, ql_base.Replay(COMPAT / "haiku.json"))
        files = {p: p.read_bytes() for p in store_files(q)}
        rc, said = run_distill(q, echo, run_id="20260928T130000Z-0000abcf")
        assert rc == 0 and said == ["distill: nothing to write (waiting=0)"] and \
            {p: p.read_bytes() for p in store_files(q)} == files
        k = tmp_path / "keep"
        sp = plant_compat(k)
        said = []
        ql_distill._distill(k, ql_base.Replay(COMPAT / "haiku.json"), NOW, RUN_ID, "0" * 40, said.append, keep=True)
        assert said[0] == f"distill: run={RUN_ID} entries=17 dropped=0 waiting=0", said
        files = {p: p.read_bytes() for p in store_files(k)}
        spool_before = {p.name: p.read_bytes() for p in sp.iterdir()}
        said = []
        ql_distill._distill(k, echo, NOW, "20260928T130000Z-0000abcf", "0" * 40, said.append, keep=True)
        assert said[0] == "distill: nothing to write (waiting=0)", said
        assert {p: p.read_bytes() for p in store_files(k)} == files
        assert {p.name: p.read_bytes() for p in sp.iterdir()} == spool_before

    @pytest.mark.parametrize("shape", sorted(SHAPE_ROWS))
    def test_a_planted_row_of_each_shape(self, tmp_path, shape):
        """One row of each shape in a spool of its own: in a kb prompt of a closed session (a prompt row: with a
        kb_hook row of format 1), or alone in a finished day's tools file. It is read, never skipped or dropped, and
        the run file passes the gates."""
        row = next(r for r in compat_rows() if r["id"] == SHAPE_ROWS[shape])
        q = tmp_path / "querylog"
        sp = q / "spool"
        sp.mkdir(parents=True)
        if "session_id" not in row:
            (sp / "tools-2026-09-25.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8", newline="\n")
        else:
            row = dict(row, prompt_id="d1")
            ts = row["ts"][:-5]
            base = [{"id": E("d1"), "ts": ts + "0.000Z", "surface": "prompt", "session_id": S_COMPAT,
                     "prompt_id": "d1", "prompt": "kb: laps password length", "kb_intent": "lookup"},
                    {"id": E("d2"), "ts": ts + "0.500Z", "surface": "kb_hook", "v": 1, "session_id": S_COMPAT,
                     "prompt_id": "d1", "question": "laps password length", "verdict": "good", "articles": [LAPS],
                     "lines": [{"line": f"{LAPS}:24", "tag": "DOC", "verdict": "good"}]}]
            rs = [row, base[1]] if row["surface"] == "prompt" else base + [row]
            (sp / f"{S_COMPAT}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8",
                                                  newline="\n")
            os.utime(sp / f"{S_COMPAT}.jsonl", (NOW.timestamp() - 3600,) * 2)
            (sp / f"{S_COMPAT}.end").touch()
        rc, said = run_distill(q, echo)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=1 dropped=0 waiting=0"], said
        assert ql_store.store_problems(q / "store") == []
        assert list(sp.iterdir()) == []

    def test_unknown_and_malformed_rows_are_skipped_and_counted(self, tmp_path):
        """A row of an unknown future format, or one distill cannot read, is skipped and counted in the header; the
        rest distills as before, and the skipped rows go with the pass that counted them."""
        future = {"id": E("e1"), "ts": "2026-09-26T09:00:02.000Z", "surface": "kb_hook", "v": 2,
                  "session_id": S_COMPAT, "prompt_id": "pa", "question": "laps", "cites": ["laps@24"]}
        bad = [json.dumps(future), json.dumps(dict(future, id=E("e2"), v="1")), json.dumps(dict(future, id=E("e3"), v=True)),
               json.dumps(dict(future, id=E("e4"), v=0)), '{"id": "' + E("e5") + '", "ts": "2026-09-26T09', "[1, 2]",
               json.dumps({"ts": "2026-09-26T09:00:03.000Z", "surface": "prompt"}),
               json.dumps({"id": E("e6"), "ts": "2026-09-26T09:00:04.000Z", "surface": "telemetry"}),
               json.dumps({"id": E("e7"), "surface": "stop", "answer": "no time"}), ""]
        tools_bad = [json.dumps({"id": E("e8"), "ts": "2026-09-25T08:00:01.000Z", "surface": "kb_ask", "v": 9,
                                 "question": "laps"})]
        q = tmp_path / "querylog"
        sp = plant_compat(q, bad, tools_bad)
        rc, said = run_distill(q, ql_base.Replay(COMPAT / "haiku.json"))
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=17 dropped=0 waiting=0 skipped=10"], said
        header = jsonl(store_files(q)[0])[0]
        assert header["counts"] == {"entries": 17, "dropped": 0, "waiting": 0, "skipped": 10}
        assert ql_store.store_problems(q / "store") == [] and list(sp.iterdir()) == []
        rc, said = run_distill(q, echo, run_id="20260928T130000Z-0000abcf")
        assert said == ["distill: nothing to write (waiting=0)"]
        # an open session's rows are neither read nor counted, and stay as they are
        o = tmp_path / "open"
        sp = o / "spool"
        sp.mkdir(parents=True)
        (sp / f"{S_COMPAT}.jsonl").write_text(json.dumps(future) + "\n", encoding="utf-8", newline="\n")
        before = (sp / f"{S_COMPAT}.jsonl").read_bytes()
        rc, said = run_distill(o, echo)
        assert said == ["distill: nothing to write (waiting=0)"] and store_files(o) == []
        assert (sp / f"{S_COMPAT}.jsonl").read_bytes() == before
        # only skipped rows in a closed session: a run file that counts them, with no entry
        (sp / f"{S_COMPAT}.end").touch()
        rc, said = run_distill(o, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 skipped=1"], said
        assert ql_store.store_problems(o / "store") == [] and list(sp.iterdir()) == []

    def test_a_finished_days_tools_file_that_stays_loses_its_skipped_rows(self, tmp_path):
        """A tools file kept for a waiting entry is rewritten without the rows counted as skipped, so no later pass
        counts them again."""
        q = tmp_path / "querylog"
        sp = plant_compat(q, (), ["not json"])

        def down(prompt):
            raise OSError("no network")
        rc, said = run_distill(q, down)
        assert said[-1].endswith("skipped=1"), said
        assert all(json.loads(ln) for ln in (sp / "tools-2026-09-25.jsonl").read_text(encoding="utf-8").splitlines())
        rc, said = run_distill(q, ql_base.Replay(COMPAT / "haiku.json"), run_id="20260928T120500Z-0000abce")
        assert said[-1].endswith("waiting=0"), said
        assert "skipped" not in jsonl(store_files(q)[-1])[0]["counts"]

    def test_row_lines_keep_only_the_recorded_articles(self, monkeypatch):
        """pack re-runs only a format 0 row without `lines`, on the questions the row recorded, and keeps only the
        lines of the articles it recorded; it never adds a line of another article."""
        text = ("coverage: good (...)\n\n## public/windows/laps.md  LAPS\n- public/windows/laps.md:24 A. [DOC S-1]\n"
                "\n## public/intune/win32-apps.md  Win32\n- public/intune/win32-apps.md:49 B. [DOC S-2]\n")
        asked = []
        monkeypatch.setattr(ql_distill, "head_pack_text", lambda q: asked.append(q) or text)
        old = {"id": E("r1"), "ts": "2026-09-26T09:00:00.000Z", "surface": "mcp", "tool": "kb_pack",
               "args": {"questions": ["laps length", "laps age"]}, "articles": [LAPS]}
        got, again = ql_distill.row_lines(old)
        assert again and got == [{"line": f"{LAPS}:24", "tag": "DOC", "verdict": "good"}] * 2
        assert asked == ["laps length", "laps age"]
        assert ql_distill.citations([old], "")[0] == [{"line": f"{LAPS}:24", "tag": "DOC", "verdict": "good"}]
        asked.clear()
        for row in (dict(old, v=1), dict(old, lines=[{"line": f"{LAPS}:9"}]), dict(old, articles=None),
                    dict(old, args={"path": f"{LAPS}:24"}), dict(old, articles=["public/other/none.md"])):
            got, again = ql_distill.row_lines(row)
            assert not again and got == row.get("lines", []), row
        assert asked == ["laps length", "laps age"]  # only the row whose articles pack could not back
        # planted: an entry whose re-run lines name the reply's line is still `pack`, never `reply`
        assert ql_distill.citations([old], f"see {LAPS}:24")[1] == "pack"


WA, WB, WC = "TK-aaaaaaaa", "TK-bbbbbbbb", "TK-cccccccc"  # item ids as backlog.py writes them
SA, SB = "SP-aaaaaaaa", "SP-bbbbbbbb"  # sprint ids: WA and WB belong to SA, WC to SB
SPRINTS = {WA: SA, WB: SA, WC: SB}
REAL_SPRINT_FINDER = ql_distill.sprint_finder
W1, W2, W3, W4, W5 = (f"bbbbbbbb-0000-4000-8000-00000000000{i}" for i in range(1, 6))


def counts_of(n):
    return {"requests": 1, "in": n, "cw": 10 * n, "cw1h": n, "cr": 100 * n, "out": n}


def total_of(ns):
    """The counts of the prompts whose `counts_of` numbers are `ns`, added."""
    return {"requests": len(ns), "in": sum(ns), "cw": 10 * sum(ns), "cw1h": sum(ns), "cr": 100 * sum(ns),
            "out": sum(ns)}


def work_rows(sid, plan, reader=None):
    """A session's spool rows. `plan` lists per prompt p0, p1, ...: (its work rows as "claim:ID", "done:ID" or
    "release:ID", the number n of its usage record or None, whether that record has a subagent (True: one counted
    under `sub`; an item id: one routed to that item), whether the prompt used the kb)."""
    rows, n = [], 0
    for i, (work, usage, sub, kb) in enumerate(plan):
        base = {"session_id": sid, "v": 1, "prompt_id": f"p{i}"}
        kinds = [("prompt", {"prompt": "PRIVATE-WORK-TEXT"})]
        kinds += [("work", dict(zip(("action", "item"), w.split(":")))) for w in work]
        if kb:
            kinds.append(("mcp", {"tool": "kb_pack", "args": {"question": "windows laps password length"},
                                  "verdict": "good", "articles": [LAPS],
                                  "lines": [{"line": f"{LAPS}:5", "tag": "DOC", "verdict": "good"}]}))
        if usage is not None:
            rec = {"main": {"claude-opus-5-5": counts_of(usage)}, "start": 1000 + usage}
            if isinstance(sub, str):
                rec["routed"] = {sub: {"Explore": {"claude-haiku-4-5-20251001": counts_of(usage)}}}
            elif sub:
                rec["sub"] = {"Explore": {"claude-haiku-4-5-20251001": counts_of(usage)}}
            kinds.append(("usage", {"reader": reader or kbusage.READER_VERSION, "usage": rec}))
        for surface, extra in kinds:
            n += 1
            rows.append(dict(base, id=f"{sid[:23]}-{n:012x}", ts=f"2026-09-28T09:{n // 60:02d}:{n % 60:02d}.000Z",
                             surface=surface, **extra))
    return rows


def plant_work(qdir, sid, plan, closed=True, reader=None):
    sp = Path(qdir) / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / f"{sid}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in work_rows(sid, plan, reader)),
                                     encoding="utf-8", newline="\n")
    if closed:
        (sp / f"{sid}.end").touch()
    return sp


NO = ((), None, False, False)
# A is claimed in p1, B in p2, A is done in p3 and B released in p4: p0 and p5 lie outside both windows, p6 has no usage
PLAN_ONE = [((), 1, False, False), (("claim:" + WA,), 2, False, False), (("claim:" + WB,), 3, True, False),
            (("done:" + WA,), 4, False, False), (("release:" + WB,), 5, False, False), ((), 6, False, False), NO]
# the same item A again in a second session, with a prompt outside its window
PLAN_TWO = [(("claim:" + WA,), 7, False, False), (("done:" + WA,), 8, False, False), ((), 9, False, False)]


def work_sidecar_of(q, run_id=RUN_ID):
    return Path(q) / "store" / "work" / f"{run_id[:4]}-{run_id[4:6]}" / f"{run_id}.jsonl"


def work_main(*ns):
    return {"claude-opus-5-5": total_of(list(ns))}


class TestWorkSidecar:
    @pytest.fixture(autouse=True)
    def sprints(self, monkeypatch):
        """The backlog's sprint of each item, WA and WB in SA and WC in SB, instead of the clone's item files."""
        monkeypatch.setattr(ql_distill, "sprint_finder", lambda directory=None: SPRINTS.get)

    def test_work_sidecar_written_beside_the_run_file(self, tmp_path):
        """A holds p1 of the first session and both prompts of the second, B holds p4 (the prompt of its release),
        p2 and p3 (B's claim, A's done) lie in both windows, so SA, their sprint, holds them once, and the prompts
        outside every window with usage, p0 and p5 and the second session's third, are shared."""
        q = tmp_path / "querylog"
        plant_work(q, W1, PLAN_ONE)
        plant_work(q, W2, PLAN_TWO)
        plant_work(q, W3, [(("done:" + WB,), 1, False, False), ((), 2, False, False)])  # a done with no claim: none
        plant_work(q, W4, [((), 3, False, True), ((), 4, False, True)])  # kb prompts, no item worked: none
        plant_work(q, W5, [(("claim:" + WA,), 5, False, False)], closed=False)  # still open: not yet
        rc, said = run_distill(q, echo)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=2 dropped=0 waiting=0 usage=2 work=5"], said
        sub = {"Explore": {"claude-haiku-4-5-20251001": counts_of(3)}}
        assert jsonl(work_sidecar_of(q)) == [
            {"run": RUN_ID, "reader": kbusage.READER_VERSION, "counts": {"items": 3, "shared": 2, "missing": 0}},
            {"item": SA, "prompts": 2, "main": work_main(3, 4), "sub": sub},
            {"item": WA, "prompts": 3, "main": work_main(2, 7, 8)},
            {"item": WB, "prompts": 1, "main": work_main(5)},
            {"items": [WA, WB], "prompts": 2, "main": work_main(1, 6)},
            {"items": [WA], "prompts": 1, "main": work_main(9)}]
        assert ql_store.store_problems(q / "store") == []
        text = work_sidecar_of(q).read_text(encoding="utf-8")
        assert text.endswith("\n") and "\r" not in text
        for raw in (W1, W2, W3, "p1", "session_id", "prompt_id", "PRIVATE-WORK-TEXT", "transcript"):
            assert raw not in text, raw
        assert sorted(p.name for p in (q / "spool").iterdir()) == [f"{W5}.jsonl"]  # the open session's rows stay

    def test_work_sidecar_a_run_file_of_no_entry_holds_it(self, tmp_path):
        q = tmp_path / "querylog"
        plant_work(q, W1, PLAN_TWO)
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 work=2"], said
        (run,) = [p for p in store_files(q) if p.parent.parent.name != "work"]
        assert jsonl(run)[0]["counts"] == {"entries": 0, "dropped": 0, "waiting": 0} and len(jsonl(run)) == 1
        assert ql_store.store_problems(q / "store") == []

    def test_work_sidecar_none_when_no_session_worked_an_item(self, tmp_path):
        q = tmp_path / "querylog"
        plant_work(q, W3, [(("done:" + WB,), 1, False, False), ((), 2, False, False)])
        plant_work(q, W4, [((), 3, False, True)])
        rc, said = run_distill(q, echo)
        assert rc == 0 and said[0].startswith("distill: run=") and "work=" not in said[0], said
        assert not (q / "store" / "work").exists()

    def test_work_sidecar_missing_counts_window_prompts_without_usage(self, tmp_path):
        q = tmp_path / "querylog"
        plant_work(q, W1, [(("claim:" + WA,), 2, False, False), ((), 3, False, False),
                           (("done:" + WA,), 4, False, False)], reader=kbusage.READER_VERSION + 1)
        rc, said = run_distill(q, echo)  # usage rows of another reader count as none
        assert rc == 0 and said == ["distill: nothing to write (waiting=0)"], said
        plant_work(q, W2, [(("claim:" + WA,), 2, False, False), ((), None, False, False),
                           (("done:" + WA,), 4, False, False)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 work=1"], said
        got = jsonl(work_sidecar_of(q))
        assert got[0]["counts"] == {"items": 1, "shared": 0, "missing": 1}
        assert got[1] == {"item": WA, "prompts": 2, "main": work_main(2, 4)}

    def test_work_sidecar_a_usage_record_outside_the_closed_shape_is_not_counted(self, tmp_path):
        q = tmp_path / "querylog"
        sp = plant_work(q, W1, [(("claim:" + WA,), 2, False, False), (("done:" + WA,), 4, False, False)])
        rows = jsonl(sp / f"{W1}.jsonl")
        for r in rows:
            if r["surface"] == "usage" and r["prompt_id"] == "p1":
                r["usage"]["main"] = {"jan.kowalski@corp.example.com": counts_of(4)}  # planted: not a model id
        (sp / f"{W1}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 work=1"], said
        got = jsonl(work_sidecar_of(q))
        assert got[0]["counts"]["missing"] == 1 and got[1]["prompts"] == 1
        assert ql_store.store_problems(q / "store") == []

    def test_work_sidecar_windows_are_the_usage_windows(self):
        """work_windows holds the prompts ql_capture.usage_targets asks usage rows for."""
        plans = [PLAN_ONE, PLAN_TWO, [(("done:" + WA,), 1, False, False), (("claim:" + WA,), 2, False, False), NO],
                 [(("claim:" + WA,), 1, False, False), NO, (("release:" + WA,), 1, False, False), NO]]
        for plan in plans:
            rows = work_rows(W1, plan)
            inside, _ = ql_distill.work_windows(rows)
            targets, _ = ql_capture.usage_targets(rows)
            assert [p for p, items in inside.items() if items] == targets, plan
        inside, worked = ql_distill.work_windows(work_rows(W1, PLAN_ONE))
        assert worked == {WA, WB} and inside["p3"] == {WA, WB} and inside["p4"] == {WB} and inside["p5"] == set()

    def test_work_sidecar_a_prompt_is_never_counted_twice(self, tmp_path):
        """Mode `auto` keeps the rows of a written entry until its run file is on origin/main: the prompts of the
        first run's sidecar are not counted again by the next."""
        q = tmp_path / "querylog"
        plant_work(q, W1, [(("claim:" + WA,), 2, False, True), ((), 3, False, False), (("done:" + WA,), 4, False, False)])
        cfg = auto_config(q, "auto")

        def run(run_id):
            said = []
            rc = ql_distill.distill(qdir=q, cfg=cfg, haiku=echo, now_dt=NOW, run_id=run_id, kb_commit="0" * 40,
                                    out=said.append, deliver=lambda qdir, out: 0)
            return rc, said
        rc, said = run(RUN_ID)
        assert rc == 0 and said[0] == f"distill: run={RUN_ID} entries=1 dropped=0 waiting=0 usage=1 work=1", said
        assert jsonl(work_sidecar_of(q))[1] == {"item": WA, "prompts": 3, "main": work_main(2, 3, 4)}
        assert (q / "spool" / f"{W1}.jsonl").exists()  # the entry's rows stay until it is delivered
        before = {p: p.read_bytes() for p in store_files(q)}
        rc, said = run("20260928T130000Z-0000abcd")
        assert rc == 0 and said[0] == "distill: nothing to write (waiting=0)", said
        assert {p: p.read_bytes() for p in store_files(q)} == before
        # planted: without the record of the counted prompts the kept claim prompt is counted a second time
        (q / ql_distill.WORKED_NAME).unlink()
        rc, said = run("20260928T130000Z-0000abce")
        assert said[0].endswith("work=1"), said
        assert jsonl(work_sidecar_of(q, "20260928T130000Z-0000abce"))[1]["prompts"] == 1

    def test_work_sidecar_a_delivered_entry_leaves_a_closed_work_session_not_yet_counted(self, tmp_path):
        """W1 (claim, done, usage) closed after the pass that read the spool; W4 is a closed kb-only session whose
        entry is delivered. spool_delivered drops W4's file, keeps W1's, and the next distill counts W1."""
        q = tmp_path / "querylog"
        plant_work(q, W4, [((), 3, False, True)])
        cfg = auto_config(q, "auto")
        rc = ql_distill.distill(qdir=q, cfg=cfg, haiku=echo, now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40,
                                out=lambda m: None, deliver=lambda qdir, out: 0)
        assert rc == 0 and (q / "spool" / f"{W4}.jsonl").exists()  # the entry's rows stay until delivered
        ids = {e["id"] for e in jsonl(next((q / "store").rglob(f"{RUN_ID}.jsonl")))[1:]}
        assert ids, "no entry planted"
        plant_work(q, W1, [(("claim:" + WA,), 1, False, False), (("done:" + WA,), 2, False, False)])  # closed since
        assert ql_distill.spool_delivered(q, ids, NOW) == len(ids)
        assert not (q / "spool" / f"{W4}.jsonl").exists()  # the kb-only session is settled
        assert (q / "spool" / f"{W1}.jsonl").exists()  # planted: the settle step deleted it before it was counted
        rc, said = run_distill(q, echo)
        assert rc == 0 and said[0].endswith("work=1"), said
        assert jsonl(work_sidecar_of(q))[0] == {"item": WA, "prompts": 2, "main": work_main(1, 2)} or \
            any(ln.get("item") == WA and ln["prompts"] == 2 for ln in jsonl(work_sidecar_of(q)))
        assert not (q / "spool" / f"{W1}.jsonl").exists()  # counted: now it goes

    def test_work_sidecar_the_record_of_counted_prompts_drops_sessions_that_left_the_spool(self, tmp_path):
        q = tmp_path / "querylog"
        plant_work(q, W1, PLAN_ONE)
        (q / ql_distill.WORKED_NAME).write_text(json.dumps({"gone-session": ["p1"], W1: ["p9"]}), encoding="utf-8")
        run_distill(q, echo)
        assert json.loads((q / ql_distill.WORKED_NAME).read_text(encoding="utf-8")) == \
            {W1: ["p0", "p1", "p2", "p3", "p4", "p5", "p9"]}


def work_sessions(plan, sid=W1):
    """plan_work's `sessions` for one closed session of `plan` (work_rows)."""
    return {sid: {"closed": True, "rows": work_rows(sid, plan)}}


def prompts_in(lines):
    return sum(ln["prompts"] for ln in lines)


class TestWorkSubagent:
    """A subagent that worked on a work/<id> branch counts on that item's line (`-k work_subagent`); a prompt in two
    windows counts once, on the line of their sprint."""

    @pytest.fixture(autouse=True)
    def sprints(self, monkeypatch):
        monkeypatch.setattr(ql_distill, "sprint_finder", lambda directory=None: SPRINTS.get)

    def test_work_subagent_counts_on_the_items_line_and_not_on_the_prompts(self, tmp_path):
        q = tmp_path / "querylog"
        plant_work(q, W1, [(("claim:" + WA,), 2, False, False), ((), 3, WA, False), (("done:" + WA,), 4, False, False)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 work=1"], said
        sub = {"Explore": {"claude-haiku-4-5-20251001": counts_of(3)}}
        assert jsonl(work_sidecar_of(q))[1:] == [{"item": WA, "prompts": 3, "main": work_main(2, 3, 4), "sub": sub}]
        assert ql_store.store_problems(q / "store") == []
        text = work_sidecar_of(q).read_text(encoding="utf-8")
        assert "routed" not in text and "work/" not in text  # the item id alone

    def test_work_subagent_of_another_item_is_that_items_counts(self, tmp_path):
        """The subagent of p1 worked WB, which this session never claimed: WB's line gets its counts, with no prompt
        of its own, and the store's gate takes that line."""
        plan = [(("claim:" + WA,), 2, False, False), ((), 3, WB, False), (("done:" + WA,), 4, False, False)]
        lines, missing, counted = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        sub = {"Explore": {"claude-haiku-4-5-20251001": counts_of(3)}}
        assert lines == [{"item": WA, "prompts": 3, "main": work_main(2, 3, 4)},
                         {"item": WB, "prompts": 0, "main": {}, "sub": sub}], lines
        assert missing == 0 and counted == {W1: {"p0", "p1", "p2"}}
        q = tmp_path / "querylog"
        plant_work(q, W1, plan)
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 work=2"], said
        assert jsonl(work_sidecar_of(q))[2] == lines[1] and ql_store.store_problems(q / "store") == []

    def test_work_subagent_a_prompt_in_two_windows_counts_once_on_the_sprint(self):
        """WA and WB are in SA: p1, p2 and p3 lie in both windows (B's claim, A's done and the prompt between) and
        are SA's, never WA's and WB's."""
        plan = [(("claim:" + WA,), 2, False, False), (("claim:" + WB,), 3, False, False), ((), 5, False, False),
                (("done:" + WA,), 4, False, False), (("done:" + WB,), 6, False, False)]
        lines, missing, counted = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        assert lines == [{"item": SA, "prompts": 3, "main": work_main(3, 5, 4)},
                         {"item": WA, "prompts": 1, "main": work_main(2)},
                         {"item": WB, "prompts": 1, "main": work_main(6)}], lines
        assert prompts_in(lines) == len(counted[W1]) == 5  # planted: counted for each item, they would add to 8
        assert ql_store.work_line_problems(lines[0], "x") == []

    @pytest.mark.parametrize("sprint_of", [None, {WA: SA}.get, {WA: SA, WB: SB}.get, {WA: None, WB: SA}.get])
    def test_work_subagent_overlap_with_no_one_sprint_is_shared(self, sprint_of):
        """Items of different sprints, one of unknown sprint or no resolver: the prompts in both windows count once
        on the session's shared line, which names the items the session claimed."""
        plan = [(("claim:" + WA,), 2, False, False), (("claim:" + WB,), 3, False, False),
                (("done:" + WA,), 4, False, False), (("done:" + WB,), 5, False, False)]
        lines, _, counted = ql_distill.plan_work(work_sessions(plan), {}, sprint_of)
        assert lines == [{"item": WA, "prompts": 1, "main": work_main(2)},
                         {"item": WB, "prompts": 1, "main": work_main(5)},
                         {"items": [WA, WB], "prompts": 2, "main": work_main(3, 4)}], lines
        assert prompts_in(lines) == len(counted[W1]) == 4

    def test_work_subagent_overlap_in_one_sprint_is_the_sprints(self):
        plan = [(("claim:" + WA,), 2, False, False), (("claim:" + WB,), 3, False, False),
                (("done:" + WA,), 4, False, False), (("done:" + WB,), 5, False, False)]
        lines, _, counted = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        assert lines == [{"item": SA, "prompts": 2, "main": work_main(3, 4)},
                         {"item": WA, "prompts": 1, "main": work_main(2)},
                         {"item": WB, "prompts": 1, "main": work_main(5)}], lines
        assert prompts_in(lines) == len(counted[W1]) == 4

    def test_work_subagent_one_window_is_the_item_even_when_the_sprint_is_known(self):
        plan = [(("claim:" + WA,), 2, False, False), ((), 3, False, False), (("done:" + WA,), 4, False, False)]
        lines, _, _ = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        assert lines == [{"item": WA, "prompts": 3, "main": work_main(2, 3, 4)}]

    def test_work_subagent_no_duplicates_on_a_second_run(self, tmp_path):
        """Mode `auto` keeps the rows of a written entry: the subagent counts of its prompts are not added again."""
        q = tmp_path / "querylog"
        plant_work(q, W1, [(("claim:" + WA,), 2, WA, True), ((), 3, False, False), (("done:" + WA,), 4, False, False)])
        cfg = auto_config(q, "auto")

        def run(run_id):
            said = []
            rc = ql_distill.distill(qdir=q, cfg=cfg, haiku=echo, now_dt=NOW, run_id=run_id, kb_commit="0" * 40,
                                    out=said.append, deliver=lambda qdir, out: 0)
            return rc, said
        rc, said = run(RUN_ID)
        assert said[0] == f"distill: run={RUN_ID} entries=1 dropped=0 waiting=0 usage=1 work=1", said
        sub = {"Explore": {"claude-haiku-4-5-20251001": counts_of(2)}}
        assert jsonl(work_sidecar_of(q))[1] == {"item": WA, "prompts": 3, "main": work_main(2, 3, 4), "sub": sub}
        before = {p: p.read_bytes() for p in store_files(q)}
        rc, said = run("20260928T130000Z-0000abcd")
        assert said[0] == "distill: nothing to write (waiting=0)", said
        assert {p: p.read_bytes() for p in store_files(q)} == before
        # planted: without the record of counted prompts the subagent is counted a second time
        (q / ql_distill.WORKED_NAME).unlink()
        run("20260928T130000Z-0000abce")
        again = jsonl(work_sidecar_of(q, "20260928T130000Z-0000abce"))[1]
        assert again == {"item": WA, "prompts": 1, "main": work_main(2), "sub": sub}  # the kept claim prompt again

    @pytest.mark.parametrize("routed", [
        {"work/" + WA: {"Explore": {"claude-haiku-4-5-20251001": counts_of(3)}}},  # a branch, not an item id
        {WA: {"jan.kowalski": {"claude-haiku-4-5-20251001": counts_of(3)}}},  # not an agent group
        {WA: {"Explore": {"jan.kowalski@corp.example.com": counts_of(3)}}},  # not a model id
        {WA: {"Explore": {"claude-haiku-4-5-20251001": {"in": 3}}}},  # counts of another shape
        {WA: {}}, ["routed"]])
    def test_work_subagent_planted_routing_outside_the_closed_shape_is_not_counted(self, routed):
        plan = [(("claim:" + WA,), 2, False, False), ((), 3, False, False), (("done:" + WA,), 4, False, False)]
        rows = work_rows(W1, plan)
        for r in rows:
            if r["surface"] == "usage" and r["prompt_id"] == "p1":
                r["usage"]["routed"] = routed
        sessions = {W1: {"closed": True, "rows": rows}}
        lines, missing, counted = ql_distill.plan_work(sessions, {}, SPRINTS.get)
        assert missing == 1 and counted == {W1: {"p0", "p2"}}
        assert lines == [{"item": WA, "prompts": 2, "main": work_main(2, 4)}]
        assert "work/" not in json.dumps(lines)

    def test_work_subagent_the_routing_is_no_part_of_an_entrys_usage(self, tmp_path):
        """A kb prompt whose subagent was routed keeps the closed usage shape in the usage sidecar."""
        q = tmp_path / "querylog"
        plant_work(q, W1, [(("claim:" + WA,), 2, WA, True), (("done:" + WA,), 3, False, False)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=1 dropped=0 waiting=0 usage=1 work=1"], said
        (usage,) = [p for p in store_files(q) if p.parent.parent.name == "usage"]
        assert "routed" not in usage.read_text(encoding="utf-8")
        assert ql_store.store_problems(q / "store") == []

    def test_work_subagent_sprint_of_an_item_from_its_files(self, tmp_path):
        d = tmp_path / "backlog"
        d.mkdir()
        files = {WA: {"parent": "ST-aaaaaaaa"}, "ST-aaaaaaaa": {"parent": "EP-aaaaaaaa", "sprint": SA},
                 "EP-aaaaaaaa": {}, WB: {"sprint": SB, "parent": "ST-aaaaaaaa"}, WC: {"parent": "EP-aaaaaaaa"},
                 "TK-dddddddd": {"parent": "TK-eeeeeeee"}, "TK-eeeeeeee": {"parent": "TK-dddddddd"}}
        for name, obj in files.items():
            (d / f"{name}.json").write_text(json.dumps(obj), encoding="utf-8")
        (d / "TK-ffffffff.json").write_text("not json", encoding="utf-8")
        sprint_of = REAL_SPRINT_FINDER(d)
        assert sprint_of(WA) == SA and sprint_of(WB) == SB  # the story's sprint, an item's own first
        assert sprint_of(SB) == SB  # a sprint is its own
        for none in (WC, "TK-dddddddd", "TK-ffffffff", "TK-gggggggg", "not an id", None):
            assert sprint_of(none) is None, none
        assert REAL_SPRINT_FINDER(tmp_path / "missing")(WA) is None  # a clone without the backlog


# A claimed and worked, refused twice (p2, p4) and done in p5; the subagent of p1 and that of p3 are routed to A, the
# one of p2 is its prompt's own; p6 lies outside the window
PLAN_REWORK = [(("claim:" + WA,), 2, False, False), ((), 3, WA, False), (("refused:" + WA,), 4, True, False),
               ((), 5, WA, False), (("refused:" + WA,), 6, False, False), (("done:" + WA,), 7, False, False),
               ((), 8, False, False)]


def models_minus(whole, part):
    """{model: counts} of `whole` less `part`'s, as the cost report takes rework from a line's counts."""
    return {m: {k: v - part.get(m, {}).get(k, 0) for k, v in c.items()} for m, c in whole.items()
            if any(v - part.get(m, {}).get(k, 0) for k, v in c.items())}


def check_rework_split(lines):
    """A's line of PLAN_REWORK: the prompts from the first refused done (p2) on are the rework block, the two before
    it the work, and the two sum to the window's total."""
    (line,) = [ln for ln in lines if ln.get("item") == WA]
    haiku = "claude-haiku-4-5-20251001"
    assert line["prompts"] == 6 and line["main"] == work_main(2, 3, 4, 5, 6, 7), line
    assert line["sub"] == {"Explore": {haiku: total_of([3, 4, 5])}}, line
    assert line.get("rework") == {"prompts": 4, "main": work_main(4, 5, 6, 7),
                              "sub": {"Explore": {haiku: total_of([4, 5])}}}, line
    rework = line["rework"]
    assert line["prompts"] - rework["prompts"] == 2 and models_minus(line["main"], rework["main"]) == work_main(2, 3)
    assert models_minus(line["sub"]["Explore"], rework["sub"]["Explore"]) == {haiku: total_of([3])}
    assert ql_store.work_line_problems(line, "x") == []


class TestWorkRework:
    """The work sidecar splits an item's counts at its first refused done (`-k work_rework`): the item line keeps the
    window's total and a `rework` block holds the part from the first `refused` row's prompt to the end of the window."""

    @pytest.fixture(autouse=True)
    def sprints(self, monkeypatch):
        monkeypatch.setattr(ql_distill, "sprint_finder", lambda directory=None: SPRINTS.get)

    def test_work_rework_split_sums_to_the_window_total(self):
        lines, missing, counted = ql_distill.plan_work(work_sessions(PLAN_REWORK), {}, SPRINTS.get)
        check_rework_split(lines)
        # p6, outside the window, is the session's shared line: the lines add to the prompts counted, no more
        assert missing == 0 and counted == {W1: {f"p{i}" for i in range(7)}} and prompts_in(lines) == 7

    def test_work_rework_the_total_is_what_a_run_without_refusals_writes(self):
        """The line's own counts do not depend on the split: PLAN_REWORK without its refused rows has them all."""
        plain = [(tuple(w for w in work if not w.startswith("refused:")), *rest) for work, *rest in PLAN_REWORK]
        lines, _, _ = ql_distill.plan_work(work_sessions(plain), {}, SPRINTS.get)
        refused, _, _ = ql_distill.plan_work(work_sessions(PLAN_REWORK), {}, SPRINTS.get)
        assert [{k: v for k, v in ln.items() if k != "rework"} for ln in refused] == lines

    def test_work_rework_an_item_without_a_refused_row_has_no_rework(self):
        plan = [(("claim:" + WA,), 2, False, False), ((), 3, False, False), (("done:" + WA,), 4, False, False)]
        lines, _, _ = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        assert lines == [{"item": WA, "prompts": 3, "main": work_main(2, 3, 4)}], lines
        # a refusal of another item does not give this one a figure
        plan = [(("claim:" + WA,), 2, False, False), (("refused:" + WB,), 3, False, False),
                (("done:" + WA,), 4, False, False)]
        lines, _, _ = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        assert lines == [{"item": WA, "prompts": 3, "main": work_main(2, 3, 4)}], lines

    def test_work_rework_a_refused_row_with_no_open_claim_is_none(self):
        rows = work_rows(W1, [(("refused:" + WA,), 1, False, False), (("claim:" + WA,), 2, False, False),
                              (("done:" + WA,), 3, False, False), (("refused:" + WA,), 4, False, False)])
        assert ql_distill.rework_windows(rows) == {"p0": set(), "p1": set(), "p2": set(), "p3": set()}

    def test_work_rework_ends_with_the_window_and_a_new_claim_starts_none(self):
        plan = [(("claim:" + WA,), 1, False, False), (("refused:" + WA,), 2, False, False),
                (("release:" + WA,), 3, False, False), (("claim:" + WA,), 4, False, False), ((), 5, False, False),
                (("done:" + WA,), 6, False, False)]
        got = ql_distill.rework_windows(work_rows(W1, plan))
        assert got == {"p0": set(), "p1": {WA}, "p2": {WA}, "p3": set(), "p4": set(), "p5": set()}, got
        lines, _, _ = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        assert lines[0]["rework"] == {"prompts": 2, "main": work_main(2, 3)}, lines

    def test_work_rework_a_prompt_in_two_windows_is_never_split(self):
        """The prompts of A and B's overlap are their sprint's, with no rework block, whatever was refused in them."""
        plan = [(("claim:" + WA,), 2, False, False), (("claim:" + WB,), 3, False, False),
                (("refused:" + WA,), 5, False, False), (("done:" + WA,), 4, False, False),
                (("done:" + WB,), 6, False, False)]
        lines, _, _ = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        assert [ln["item"] for ln in lines] == [SA, WA, WB] and all("rework" not in ln for ln in lines), lines

    def test_work_rework_a_routed_subagent_counts_by_the_prompt_it_started_under(self):
        plan = [(("claim:" + WA,), 2, WB, False), (("refused:" + WA,), 3, WB, False), (("done:" + WA,), 4, False, False)]
        lines, _, _ = ql_distill.plan_work(work_sessions(plan), {}, SPRINTS.get)
        by = {ln["item"]: ln for ln in lines}
        sub = {"Explore": {"claude-haiku-4-5-20251001": total_of([2, 3])}}
        assert by[WB] == {"item": WB, "prompts": 0, "main": {}, "sub": sub}, by  # B has no window of this session
        assert "rework" not in by[WB] and by[WA]["rework"] == {"prompts": 2, "main": work_main(3, 4)}, by

    def test_work_rework_written_to_the_sidecar_passes_the_gates(self, tmp_path):
        q = tmp_path / "querylog"
        plant_work(q, W1, PLAN_REWORK)
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 work=2"], said  # A's line, a shared line
        got = jsonl(work_sidecar_of(q))
        assert got[0]["counts"] == {"items": 1, "shared": 1, "missing": 0}
        check_rework_split(got[1:])
        assert "rework" not in got[2]
        assert ql_store.store_problems(q / "store") == []
        text = work_sidecar_of(q).read_text(encoding="utf-8")
        assert W1 not in text and "refused" not in text and "PRIVATE-WORK-TEXT" not in text and "p2" not in text

    def test_work_rework_planted_a_split_that_never_starts_is_caught(self, monkeypatch):
        monkeypatch.setattr(ql_distill, "rework_windows", lambda rows: {r["prompt_id"]: set() for r in rows
                                                                       if "prompt_id" in r})
        lines, _, _ = ql_distill.plan_work(work_sessions(PLAN_REWORK), {}, SPRINTS.get)
        with pytest.raises(AssertionError):
            check_rework_split(lines)

    def test_work_rework_planted_a_split_that_starts_at_the_claim_is_caught(self, monkeypatch):
        monkeypatch.setattr(ql_distill, "rework_windows", lambda rows: {r["prompt_id"]: {WA} for r in rows
                                                                       if "prompt_id" in r})
        lines, _, _ = ql_distill.plan_work(work_sessions(PLAN_REWORK), {}, SPRINTS.get)
        with pytest.raises(AssertionError):
            check_rework_split(lines)


def distill_cli(data, *args):
    """`querylog.py distill ARGS` in mode `local` under the plugin data directory `data`."""
    auto_config(Path(data) / "querylog", "local")
    return subprocess.run([sys.executable, QL, "distill", *args], capture_output=True, text=True, encoding="utf-8",
                          env=querylog_env(data), timeout=120)


LOCK_TAKER = """
import sys, time
import ql_base
got = ql_base.acquire(sys.argv[1])
print("got" if got else "busy", flush=True)
time.sleep(1.5)
"""


HAIKU_ID = "claude-haiku-4-5-20251001"
HAIKU_USAGE = {"inputTokens": 120, "outputTokens": 40, "cacheReadInputTokens": 5, "cacheCreationInputTokens": 7,
               "costUSD": 0.001}
OVERHEAD_COUNTS = {"requests": 1, "in": 120, "cw": 7, "cw1h": 0, "cr": 5, "out": 40}


def cli_result(text, model_usage=None, **over):
    """What `claude -p --output-format json` prints for a successful run: the reply in `result`, the whole run's counts
    per model in `modelUsage`, and fields the distill never reads (a session id, a cost)."""
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1, "result": text,
                       "session_id": "3f2a4c1e-0000-4000-8000-00000000abcd", "total_cost_usd": 0.01,
                       "modelUsage": {HAIKU_ID: HAIKU_USAGE} if model_usage is None else model_usage, **over})


def fake_claude(monkeypatch, reply, calls=None):
    """Replace the subprocess under claude_p (never the real CLI): its stdout is `reply(prompt)`."""
    def run(argv, prompt, timeout):
        if calls is not None:
            calls.append(argv)
        return reply(prompt)
    monkeypatch.setattr(ql_distill, "claude_p", run)


class TestOverheadSidecar:
    """The distill's own Haiku calls are the run's overhead line in the work sidecar (`-k overhead_sidecar`): no item,
    no session, no text; only the kinds whose counts exist are written."""

    def distill_with_cli(self, q, monkeypatch, wrap=cli_result, **kw):
        replay = ql_base.Replay(FIXTURES / "haiku.json")
        calls = []
        fake_claude(monkeypatch, lambda prompt: wrap(replay(prompt), **kw), calls)
        said = []
        rc = ql_distill.distill(qdir=q, cfg=Path(q) / "config.json", now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40,
                                out=said.append)
        return rc, said, calls

    def overhead_sidecar_of(self, q):
        return jsonl(q / "store" / "work" / "2026-09" / f"{RUN_ID}.jsonl")

    def test_overhead_sidecar_counts_of_the_haiku_call_are_the_distill_line(self, tmp_path, monkeypatch):
        q = tmp_path / "querylog"
        plant_spool(q)
        rc, said, calls = self.distill_with_cli(q, monkeypatch)
        assert rc == 0 and len(calls) == 1 and said == [f"distill: run={RUN_ID} entries=6 dropped=1 waiting=0 overhead=1"]
        assert "--output-format" in calls[0] and calls[0][calls[0].index("--output-format") + 1] == "json"
        assert self.overhead_sidecar_of(q) == [
            {"run": RUN_ID, "reader": kbusage.READER_VERSION, "counts": {"items": 0, "shared": 0, "missing": 0,
                                                                          "overhead": 1}},
            {"overhead": "distill", "calls": 1, "main": {HAIKU_ID: OVERHEAD_COUNTS}}]
        assert ql_store.store_problems(q / "store") == []
        text = (q / "store" / "work" / "2026-09" / f"{RUN_ID}.jsonl").read_text(encoding="utf-8")
        for raw in ("session_id", "3f2a4c1e", "total_cost_usd", "costUSD", "anna.nowak", "judged", '"item"', '"items":['):
            assert raw not in text, raw

    def test_overhead_sidecar_the_entries_are_what_a_replayed_reply_gives(self, tmp_path, monkeypatch):
        """The JSON wrapper changes nothing the run file holds."""
        q = tmp_path / "querylog"
        plant_spool(q)
        self.distill_with_cli(q, monkeypatch)
        run = [p for p in store_files(q) if p.parent.parent.name != "work"]
        import kbfacts
        want = jsonl(FIXTURES / "golden.jsonl")
        want[0]["retrieval"] = kbfacts.INDEX_VERSION
        assert [jsonl(p) for p in run] == [want]

    def test_overhead_sidecar_calls_and_models_sum(self, tmp_path, monkeypatch):
        """Several calls (a batch each) and models add into the one line of the kind."""
        q = tmp_path / "querylog"
        plant_spool(q)
        monkeypatch.setattr(ql_distill, "HAIKU_BATCH_ENTRIES", 2)
        seen = []

        def reply(prompt):
            seen.append(prompt)
            items = json.loads(prompt[prompt.index("\n\n[") + 2:])
            usage = {HAIKU_ID: HAIKU_USAGE, "claude-sonnet-5-5": {"inputTokens": 3, "outputTokens": 1}} \
                if len(seen) == 1 else {HAIKU_ID: HAIKU_USAGE}
            return cli_result(echo(prompt), usage, num_turns=len(items))
        fake_claude(monkeypatch, reply)
        assert ql_distill.distill(qdir=q, cfg=q / "config.json", now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40,
                                  out=lambda s: None) == 0
        assert len(seen) == 3
        (line,) = self.overhead_sidecar_of(q)[1:]
        assert line["overhead"] == "distill" and line["calls"] == 3, line
        main = line["main"]
        assert list(main) == [HAIKU_ID, "claude-sonnet-5-5"]  # sorted
        assert main["claude-sonnet-5-5"] == {"requests": 1, "in": 3, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}
        assert (main[HAIKU_ID]["in"], main[HAIKU_ID]["out"], main[HAIKU_ID]["cr"], main[HAIKU_ID]["cw"]) \
            == (360, 120, 15, 21)
        assert ql_store.store_problems(q / "store") == []

    def test_overhead_sidecar_a_batch_that_is_dropped_still_spent_its_tokens(self, tmp_path, monkeypatch):
        """A reply that is not the expected JSON drops its batch; the call's counts are still the run's overhead."""
        q = tmp_path / "querylog"
        plant_spool(q)
        fake_claude(monkeypatch, lambda prompt: cli_result("not a JSON array of judgements"))
        said = []
        ql_distill.distill(qdir=q, cfg=q / "config.json", now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40,
                           out=said.append)
        assert "overhead=1" in said[0], said
        assert self.overhead_sidecar_of(q)[0]["counts"] == {"items": 0, "shared": 0, "missing": 0, "overhead": 1}
        assert ql_store.store_problems(q / "store") == []

    def test_overhead_sidecar_none_without_counts(self, tmp_path, monkeypatch):
        """A stdout that is not a result (an older CLI), a result with no `modelUsage` and one with only zeros give no
        line, no sidecar and the same entries."""
        for n, wrap in enumerate((lambda text: text, lambda text: cli_result(text, {}),
                                  lambda text: cli_result(text, {HAIKU_ID: {"inputTokens": 0}}))):
            q = tmp_path / f"q{n}"
            plant_spool(q)
            rc, said, _ = self.distill_with_cli(q, monkeypatch, wrap=wrap)
            assert said == [f"distill: run={RUN_ID} entries=6 dropped=1 waiting=0"], said
            assert not (q / "store" / "work").exists()

    def test_overhead_sidecar_a_failed_call_leaves_no_line(self, tmp_path, monkeypatch):
        """An error result is a failed call: its entries wait, nothing is counted, nothing written."""
        q = tmp_path / "querylog"
        plant_spool(q)
        fake_claude(monkeypatch, lambda prompt: cli_result("", is_error=True, subtype="error_during_execution"))
        said = []
        assert ql_distill.distill(qdir=q, cfg=q / "config.json", now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40,
                                  out=said.append) == 0
        assert any("Haiku call failed" in s for s in said), said
        assert not (q / "store" / "work").exists()

    def test_overhead_sidecar_no_line_when_haiku_is_injected(self, tmp_path):
        """A replayed or stubbed Haiku has no counts: only a real call is measured."""
        q = tmp_path / "querylog"
        plant_spool(q)
        run_distill(q, ql_base.Replay(FIXTURES / "haiku.json"))
        assert not (q / "store" / "work").exists()

    def test_overhead_sidecar_only_the_distill_kind_has_counts(self):
        """The digest, eval and census run no model and write none: the kinds the gates name are a superset."""
        assert ql_distill.Spend().lines() == []
        spend = ql_distill.Spend()
        spend.add({HAIKU_ID: OVERHEAD_COUNTS})
        (line,) = spend.lines()
        assert line["overhead"] == "distill" and line["overhead"] in ql_store.OVERHEAD_KINDS

    @pytest.mark.parametrize("result,want", [
        (cli_result("ok"), ("ok", {HAIKU_ID: OVERHEAD_COUNTS})),
        (cli_result("ok", {HAIKU_ID: HAIKU_USAGE}, num_turns=3), ("ok", {HAIKU_ID: {**OVERHEAD_COUNTS, "requests": 3}})),
        (cli_result("ok", {"claude-opus-5-5": {"inputTokens": 2}, HAIKU_ID: HAIKU_USAGE}, num_turns=4),
         ("ok", {"claude-opus-5-5": {"requests": 1, "in": 2, "cw": 0, "cw1h": 0, "cr": 0, "out": 0},
                 HAIKU_ID: OVERHEAD_COUNTS})),
        (cli_result("ok", {"payroll-model": {"inputTokens": 9}}),
         ("ok", {"other": {"requests": 1, "in": 9, "cw": 0, "cw1h": 0, "cr": 0, "out": 0}})),
        (cli_result("ok", {HAIKU_ID: {"inputTokens": -5, "outputTokens": True, "cacheReadInputTokens": "9",
                                      "cacheCreationInputTokens": 2.5}}), ("ok", {})),
        (cli_result("ok", {HAIKU_ID: "not a map"}), ("ok", {})),
        ("[]", ("[]", {})),
        ("not json", ("not json", {})),
        ('{"type": "assistant"}', ('{"type": "assistant"}', {})),
    ])
    def test_overhead_sidecar_haiku_result(self, result, want):
        assert ql_distill.haiku_result(result) == want

    @pytest.mark.parametrize("result", [
        cli_result("", is_error=True), cli_result("", subtype="error_max_turns"),
        json.dumps({"type": "result", "subtype": "success", "is_error": False}),
    ])
    def test_overhead_sidecar_haiku_result_error_is_oserror(self, result):
        with pytest.raises(OSError):
            ql_distill.haiku_result(result)


def ops_row(n, event="land.step", day="2026-09-28", **fields):
    """The nth ops row of a tools file as capture writes it (the closed fields of a land.step unless given)."""
    fields = fields or {"item": WA, "step": "rebase", "exit": 0, "ms": 100 + n}
    return {"id": f"{n:08x}-1111-4111-8111-111111111111", "ts": f"{day}T10:00:{n:02d}.000Z", "surface": "ops", "v": 1,
            "event": event, **fields}


def plant_ops(qdir, rows, day="2026-09-28"):
    sp = Path(qdir) / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    f = sp / f"tools-{day}.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    return f


def ops_sidecar_of(q, run_id=RUN_ID):
    return Path(q) / "store" / "ops" / f"{run_id[:4]}-{run_id[4:6]}" / f"{run_id}.jsonl"


class TestOpsSidecar:
    def test_ops_sidecar_written_beside_the_run_file(self, tmp_path):
        q = tmp_path / "querylog"
        rows = [ops_row(3), ops_row(1), ops_row(2, "test.run", mode="fast", ms=5, exit=0,
                                                 slow=[{"file": "test_x.py", "ms": 3}])]
        f = plant_ops(q, rows)
        rc, said = run_distill(q, echo)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 ops=3"], said
        got = jsonl(ops_sidecar_of(q))
        assert got[0] == {"run": RUN_ID, "counts": {"rows": 3}}
        assert [g["id"] for g in got[1:]] == [r["id"] for r in sorted(rows, key=lambda r: r["ts"])]
        assert got[2] == {k: v for k, v in rows[2].items() if k not in ("surface", "v")}
        assert list(got[1]) == ["id", "ts", "event", "item", "step", "exit", "ms"]
        (run,) = [x for x in store_files(q) if x.parent.parent.name not in ("ops", "work", "usage")]
        assert jsonl(run) == [{**jsonl(run)[0], "counts": {"entries": 0, "dropped": 0, "waiting": 0}}]
        assert ql_store.store_problems(q / "store") == []
        text = ops_sidecar_of(q).read_text(encoding="utf-8")
        assert text.endswith("\n") and "\r" not in text and '"surface"' not in text and '"v"' not in text
        assert f.exists()  # today's tools file stays until its day is over
        assert sorted(json.loads((q / ql_distill.CONSUMED_NAME).read_text(encoding="utf-8"))[f.name]) == sorted(r["id"] for r in rows)

    def test_ops_sidecar_a_row_is_read_once(self, tmp_path):
        q = tmp_path / "querylog"
        plant_ops(q, [ops_row(1)])
        run_distill(q, echo)
        before = {p: p.read_bytes() for p in store_files(q)}
        rc, said = run_distill(q, echo, run_id="20260928T130000Z-0000abce")
        assert rc == 0 and said == ["distill: nothing to write (waiting=0)"], said
        assert {p: p.read_bytes() for p in store_files(q)} == before
        plant_ops(q, [ops_row(1), ops_row(2)])  # a second row arrives in the same file
        rc, said = run_distill(q, echo, run_id="20260928T140000Z-0000abcf")
        assert said == ["distill: run=20260928T140000Z-0000abcf entries=0 dropped=0 waiting=0 ops=1"], said
        assert [g["id"] for g in jsonl(ops_sidecar_of(q, "20260928T140000Z-0000abcf"))[1:]] == [ops_row(2)["id"]]
        assert ql_store.store_problems(q / "store") == []

    def test_ops_sidecar_a_row_a_sidecar_holds_is_not_written_twice(self, tmp_path):
        """the run that wrote it died before recording its consumption: the next one finds the id in the store"""
        q = tmp_path / "querylog"
        plant_ops(q, [ops_row(1)])
        run_distill(q, echo)
        (q / ql_distill.CONSUMED_NAME).unlink()
        rc, said = run_distill(q, echo, run_id="20260928T130000Z-0000abce")
        assert said == ["distill: nothing to write (waiting=0)"], said
        assert len(list((q / "store" / "ops").rglob("*.jsonl"))) == 1 and ql_store.store_problems(q / "store") == []
        assert (q / ql_distill.CONSUMED_NAME).exists()  # and it is recorded now

    def test_ops_sidecar_a_finished_days_file_goes_once_read(self, tmp_path):
        q = tmp_path / "querylog"
        f = plant_ops(q, [ops_row(1, day="2026-09-27")], day="2026-09-27")
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 ops=1"], said
        assert not f.exists()

    def test_ops_sidecar_a_row_outside_the_closed_shape_is_dropped_and_counted(self, tmp_path):
        q = tmp_path / "querylog"
        free = "I could not rebase because main moved"
        key = "glpat" + "-" + "a" * 20  # a valid name the leak scan flags
        rows = [ops_row(1), ops_row(2, step=free, item=WA, exit=0, ms=1), ops_row(3, event="no.such", ms=1),
                ops_row(4, item=WA, step=key, exit=0, ms=1), {**ops_row(5), "prompt": free}, {**ops_row(6), "session_id": SID}]
        plant_ops(q, rows)
        rc, said = run_distill(q, echo)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 skipped=5 ops=1"], said
        assert [g["id"] for g in jsonl(ops_sidecar_of(q))[1:]] == [ops_row(1)["id"]]
        run = [x for x in store_files(q) if x.parent.parent.name not in ("ops", "work", "usage")][0]
        assert jsonl(run)[0]["counts"] == {"entries": 0, "dropped": 0, "waiting": 0, "skipped": 5}
        text = "".join(x.read_text(encoding="utf-8") for x in store_files(q))
        assert free not in text and key not in text
        assert ql_store.store_problems(q / "store") == []
        before = {p: p.read_bytes() for p in store_files(q)}
        assert run_distill(q, echo, run_id="20260928T130000Z-0000abce")[1] == ["distill: nothing to write (waiting=0)"]
        assert {p: p.read_bytes() for p in store_files(q)} == before  # dropped rows are not read again

    def test_ops_sidecar_only_dropped_rows_still_write_a_run_file_with_the_count(self, tmp_path):
        q = tmp_path / "querylog"
        plant_ops(q, [ops_row(1, event="no.such", ms=1)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 skipped=1"], said
        assert not (q / "store" / "ops").exists() and ql_store.store_problems(q / "store") == []

    def test_ops_sidecar_an_ops_row_joins_no_prompt(self, tmp_path):
        """the fixture spool distills to the same entries with an ops row inside a session's window"""
        base, with_ops = tmp_path / "base", tmp_path / "with"
        for q in (base, with_ops):
            plant_spool(q)
        tools = with_ops / "spool" / "tools-2026-09-27.jsonl"  # the day of the first session, which began at 09:00:00
        row = {**ops_row(1, day="2026-09-27"), "ts": "2026-09-27T09:00:00.500Z"}
        tools.write_text(tools.read_text(encoding="utf-8") + json.dumps(row) + "\n", encoding="utf-8", newline="\n")
        for q in (base, with_ops):
            assert run_distill(q, lambda p: echo(p))[0] == 0
        assert jsonl(ql_store.run_files(with_ops / "store")[0]) == jsonl(ql_store.run_files(base / "store")[0])
        assert len(jsonl(ops_sidecar_of(with_ops))) == 2 and not (base / "store" / "ops").exists()


AG1, AG2, AG3 = "0123456789ab", "ba9876543210", "00ff00ff00ff"  # the salted hashes capture writes


def agent_row(n, action, agent, ms, group="kb-worker", item=None, sid=W1, **extra):
    """The nth `work` row of a subagent's start or stop, `ms` milliseconds into the session's day."""
    t = datetime.datetime(2026, 9, 28, 10, 0, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(milliseconds=ms)
    row = {"id": f"{n:08x}-2222-4222-8222-222222222222", "ts": ql_base.iso(t.timestamp()), "surface": "work", "v": 1,
           "session_id": sid, "action": action, "agent": agent, "group": group, **extra}
    if item:
        row["item"] = item
    return row


def plant_agents(qdir, rows, sid=W1, closed=True):
    sp = Path(qdir) / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / f"{sid}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    if closed:
        (sp / f"{sid}.end").touch()
    return sp / f"{sid}.jsonl"


class TestAgentRows:
    def test_pipeline_version_covers_agent_run_lines(self, tmp_path):
        """distill has written agent.run lines since version 7: the version and the golden run file's header say so"""
        assert ql_base.PIPELINE_VERSION >= 7
        assert jsonl(FIXTURES / "golden.jsonl")[0]["pipeline"] == ql_base.PIPELINE_VERSION
        q = tmp_path / "querylog"
        plant_agents(q, [agent_row(1, "agent-start", AG1, 0, item=WA), agent_row(2, "agent-stop", AG1, 5, item=WA)])
        assert run_distill(q, echo)[0] == 0
        assert [g["event"] for g in jsonl(ops_sidecar_of(q))[1:]] == ["agent.run"]

    def test_ops_agent_rows_a_pair_is_one_agent_run_line(self, tmp_path):
        q = tmp_path / "querylog"
        f = plant_agents(q, [agent_row(1, "agent-start", AG1, 0, item=WA), agent_row(2, "agent-stop", AG1, 61234, item=WA),
                             agent_row(3, "agent-start", AG2, 100, group="general-purpose"),
                             agent_row(4, "agent-stop", AG2, 900, group="general-purpose")])
        rc, said = run_distill(q, echo)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 ops=2"], said
        got = jsonl(ops_sidecar_of(q))
        assert got[0] == {"run": RUN_ID, "counts": {"rows": 2}}
        assert [{k: v for k, v in g.items() if k not in ("id", "ts")} for g in got[1:]] == [
            {"event": "agent.run", "group": "general-purpose", "agent": AG2, "ms": 800},
            {"event": "agent.run", "group": "kb-worker", "agent": AG1, "item": WA, "ms": 61234}]
        assert all(ql_capture.OPS_KINDS["agent"](g["agent"]) for g in got[1:])
        assert ql_store.store_problems(q / "store") == []
        assert not f.exists()  # the session's rows are consumed
        before = {p: p.read_bytes() for p in store_files(q)}
        assert run_distill(q, echo, run_id="20260928T130000Z-0000abce")[1] == ["distill: nothing to write (waiting=0)"]
        assert {p: p.read_bytes() for p in store_files(q)} == before  # a pair is written once

    def test_ops_agent_rows_the_same_rows_again_write_no_second_line(self, tmp_path):
        """the spool kept the rows (keep) or the run died before the session left: the line's id is the pair's"""
        q = tmp_path / "querylog"
        rows = [agent_row(1, "agent-start", AG1, 0), agent_row(2, "agent-stop", AG1, 50)]
        plant_agents(q, rows)
        run_distill(q, echo)
        plant_agents(q, rows)
        rc, said = run_distill(q, echo, run_id="20260928T130000Z-0000abce")
        assert said == ["distill: nothing to write (waiting=0)"], said
        assert len(list((q / "store" / "ops").rglob("*.jsonl"))) == 1 and ql_store.store_problems(q / "store") == []

    def test_ops_agent_rows_a_start_that_fired_twice_is_one_run_from_the_first(self, tmp_path):
        q = tmp_path / "querylog"
        plant_agents(q, [agent_row(1, "agent-start", AG1, 0), agent_row(2, "agent-start", AG1, 40),
                         agent_row(3, "agent-stop", AG1, 100)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 ops=1"], said
        assert [g["ms"] for g in jsonl(ops_sidecar_of(q))[1:]] == [100]

    def test_ops_agent_rows_an_unpaired_start_or_stop_is_skipped_and_counted(self, tmp_path):
        q = tmp_path / "querylog"
        plant_agents(q, [agent_row(1, "agent-start", AG1, 0), agent_row(2, "agent-stop", AG2, 10),
                         agent_row(3, "agent-start", AG3, 500), agent_row(4, "agent-stop", AG3, 20),  # stop first
                         agent_row(5, "agent-start", "aaaaaaaaaaaa", 0), agent_row(6, "agent-stop", "aaaaaaaaaaaa", 7)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 skipped=3 ops=1"], said
        assert [(g["agent"], g["ms"]) for g in jsonl(ops_sidecar_of(q))[1:]] == [("aaaaaaaaaaaa", 7)]
        run = [x for x in store_files(q) if x.parent.parent.name not in ("ops", "work", "usage")][0]
        assert jsonl(run)[0]["counts"] == {"entries": 0, "dropped": 0, "waiting": 0, "skipped": 3}
        assert ql_store.store_problems(q / "store") == []

    def test_ops_agent_rows_only_unpaired_rows_write_a_run_file_with_the_count_and_no_sidecar(self, tmp_path):
        q = tmp_path / "querylog"
        plant_agents(q, [agent_row(1, "agent-start", AG1, 0)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 skipped=1"], said
        assert not (q / "store" / "ops").exists()

    @pytest.mark.parametrize("bad", [
        {"agent": "agent-0123456789abcdef0"},  # a raw agent id
        {"group": "a free text group"},
        {"item": "work/ST-lopowpsz"},  # branch text
        {"group": "kb-worker", "agent": "glpat" + "-" + "a" * 20}])  # a valid name the leak scan flags
    def test_ops_agent_rows_a_raw_id_or_free_text_is_dropped_never_written(self, tmp_path, bad):
        q = tmp_path / "querylog"
        row = {"agent": AG1, "group": "kb-worker", **bad}
        plant_agents(q, [agent_row(1, "agent-start", row.pop("agent"), 0, **row),
                         agent_row(2, "agent-stop", bad.get("agent", AG1), 5, **row)])
        rc, said = run_distill(q, echo)
        assert said == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 skipped=1"] or "skipped" in said[0], said
        assert not (q / "store" / "ops").exists()
        text = "".join(x.read_text(encoding="utf-8") for x in store_files(q))
        for v in bad.values():
            assert v not in text
        assert ql_store.store_problems(q / "store") == []

    def test_ops_agent_rows_a_session_still_open_waits(self, tmp_path):
        q = tmp_path / "querylog"
        f = plant_agents(q, [agent_row(1, "agent-start", AG1, 0), agent_row(2, "agent-stop", AG1, 5)], closed=False)
        t = NOW.timestamp() - 60
        os.utime(f, (t, t))
        assert run_distill(q, echo)[1] == ["distill: nothing to write (waiting=0)"]
        assert f.exists() and not (q / "store").exists()
        (q / "spool" / f"{W1}.end").touch()  # planted counterpart: closed, the pair is written
        assert run_distill(q, echo)[1] == [f"distill: run={RUN_ID} entries=0 dropped=0 waiting=0 ops=1"]

    def test_ops_agent_rows_open_no_prompt_window(self, tmp_path):
        """the fixture spool distills to the same entries with agent rows inside a session"""
        base, with_rows = tmp_path / "base", tmp_path / "with"
        for q in (base, with_rows):
            plant_spool(q)
        f = with_rows / "spool" / f"{S_ENDED}.jsonl"
        first = json.loads(f.read_text(encoding="utf-8").splitlines()[0])
        t = datetime.datetime.fromisoformat(first["ts"]) + datetime.timedelta(seconds=1)
        extra = [agent_row(1, "agent-start", AG1, 0, sid=S_ENDED), agent_row(2, "agent-stop", AG1, 9, sid=S_ENDED)]
        for r in extra:
            r["ts"] = ql_base.iso(t.timestamp())
        f.write_text(f.read_text(encoding="utf-8") + "".join(json.dumps(r) + "\n" for r in extra), encoding="utf-8",
                     newline="\n")
        for q in (base, with_rows):
            assert run_distill(q, echo)[0] == 0
        assert jsonl(ql_store.run_files(with_rows / "store")[0])[1:] == jsonl(ql_store.run_files(base / "store")[0])[1:]
        assert len(jsonl(ops_sidecar_of(with_rows))) == 2


class TestLock:
    def test_a_second_distill_exits_on_the_lock(self, tmp_path):
        q = tmp_path / "querylog"
        plant_fetch_day(tmp_path)
        sp = spool(tmp_path)
        lock = ql_base.acquire(q)
        info = json.loads(lock.read_text(encoding="utf-8"))
        assert info["pid"] == os.getpid() and info["started"].endswith("Z")
        before = {p.name: p.read_bytes() for p in sp.iterdir()}
        p = distill_cli(tmp_path, "--replay", str(FIXTURES / "haiku.json"))
        assert (p.returncode, p.stdout) == (3, "distill: another distill holds the lock\n"), p.stderr
        assert {p.name: p.read_bytes() for p in sp.iterdir()} == before and store_files(q) == []
        ql_base.release(lock)
        p = distill_cli(tmp_path, "--replay", str(FIXTURES / "haiku.json"))  # planted: without the lock it runs
        assert p.returncode == 0 and "entries=" in p.stdout, p.stdout + p.stderr
        assert not (q / ql_base.LOCK_NAME).exists()

    def test_a_stale_lock_is_taken_over(self, tmp_path):
        q = tmp_path / "querylog"
        q.mkdir()
        old = time.time() - ql_base.LOCK_STALE_S - 5
        (q / ql_base.LOCK_NAME).write_text(json.dumps({"pid": 1, "started_epoch": old}), encoding="utf-8")
        p = distill_cli(tmp_path)
        assert p.returncode == 0 and "nothing to write" in p.stdout, p.stdout + p.stderr
        (q / ql_base.LOCK_NAME).write_text(json.dumps({"pid": 1, "started_epoch": time.time() - 5}), encoding="utf-8")
        assert distill_cli(tmp_path).returncode == 3  # planted: a fresh one holds

    def test_one_taker_wins(self, tmp_path):
        env = dict(os.environ, PYTHONPATH=TOOLS)
        procs = [subprocess.Popen([sys.executable, "-c", LOCK_TAKER, str(tmp_path)], stdout=subprocess.PIPE, text=True,
                                  encoding="utf-8", env=env) for _ in range(6)]
        said = sorted(p.communicate(timeout=60)[0].strip() for p in procs)
        assert said == ["busy"] * 5 + ["got"], said


# ---------------------------------------------------------------- the launcher


def session_end(sid=SID):
    return {"hook_event_name": "SessionEnd", "session_id": sid, "reason": "prompt_input_exit"}


def plant_fetch_day(data, n=1):
    """A tools file of yesterday (UTC) holding n fetch.py requests to a local address: ready to distill, with nothing
    for Haiku or the redactor."""
    sp = spool(data)
    sp.mkdir(parents=True, exist_ok=True)
    day = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).date().isoformat()
    rows = [{"id": str(uuid.uuid4()), "ts": f"{day}T08:00:0{i}.000Z", "surface": "tool_fetch", "tool": "fetch.py",
             "host": "127.0.0.1", "path": f"/p{i}", "outcome": "http-200"} for i in range(n)]
    (sp / f"tools-{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    return rows


def wait_for_run(data, timeout=60):
    """The store's run files once one exists (the detached distill wrote it), else []."""
    end = time.time() + timeout
    while time.time() < end:
        files = sorted((Path(data) / "querylog" / "store").rglob("*.jsonl"))
        if files and not (Path(data) / "querylog" / ql_base.LOCK_NAME).exists():
            return files
        time.sleep(0.2)
    return []


def launch_proc(data, event, **kw):
    """Run the launcher as Claude Code runs a hook: (exit code, stdout, seconds until it returned, time it exited)."""
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, QL, "launch"], input=json.dumps(event).encode("utf-8"), capture_output=True,
                       env=querylog_env(data), timeout=60, **kw)
    return p.returncode, p.stdout, time.monotonic() - t0, time.time()


JOB_PARENT = r"""
import ctypes, subprocess, sys
from ctypes import wintypes
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateJobObjectW.restype = wintypes.HANDLE
k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
k32.GetCurrentProcess.restype = wintypes.HANDLE
k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]


class Basic(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class Io(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("Read", "Write", "Other", "ReadBytes", "WriteBytes", "OtherBytes")]


class Extended(ctypes.Structure):
    _fields_ = [("Basic", Basic), ("Io", Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


job = k32.CreateJobObjectW(None, None)
info = Extended()
info.Basic.LimitFlags = 0x2000 | 0x800  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
    sys.exit(f"SetInformationJobObject: {ctypes.get_last_error()}")
if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
    sys.exit(f"AssignProcessToJobObject: {ctypes.get_last_error()}")
p = subprocess.run([sys.executable, sys.argv[1], "launch"], input=sys.stdin.buffer.read(), timeout=60)
sys.exit(p.returncode)
"""  # the job's only handle closes when this process exits: every process still in the job ends with it


class TestLaunch:
    def test_session_end_marks_its_session_closed(self, tmp_path):
        spool(tmp_path).mkdir(parents=True)
        (spool(tmp_path) / f"{SID}.jsonl").write_text("{}\n", encoding="utf-8")
        assert launch_proc(tmp_path, session_end())[:2] == (0, b"")
        assert (spool(tmp_path) / f"{SID}.end").exists()
        assert not (tmp_path / "querylog" / "store").exists()  # its only row used no kb: nothing to write
        assert launch_proc(tmp_path, session_end("../../x"))[:2] == (0, b"")
        assert not (tmp_path / "x.end").exists()

    def test_the_launcher_returns_in_budget_and_its_child_outlives_it(self, tmp_path):
        rows = plant_fetch_day(tmp_path)
        rc, out, took, exited = launch_proc(tmp_path, session_end())
        assert (rc, out) == (0, b"") and took < 1.5, took  # SessionEnd hooks share 1.5 s; the pipes are free
        files = wait_for_run(tmp_path)
        assert files, (tmp_path / "querylog" / ql_distill.LOG_NAME).read_text(encoding="utf-8")
        assert files[0].stat().st_mtime > exited  # written after the launcher was gone (LAUNCH_SETTLE_S)
        assert [e["id"] for e in jsonl(files[0])[1:]] == [r["id"] for r in rows]
        log = (tmp_path / "querylog" / ql_distill.LOG_NAME).read_text(encoding="utf-8")
        assert "entries=1" in log and "Haiku" not in log

    def test_launch_itself_fits_its_share_of_the_budget(self, tmp_path, monkeypatch):
        for k, v in querylog_env(tmp_path).items():
            if k.startswith("CLAUDE_PLUGIN_"):
                monkeypatch.setenv(k, v)
        plant_fetch_day(tmp_path)
        t0 = time.monotonic()
        pid = ql_distill.launch(session_end())
        took = time.monotonic() - t0
        assert pid and took < ql_distill.LAUNCH_BUDGET_S, took
        assert wait_for_run(tmp_path)

    @pytest.mark.skipif(os.name == "nt", reason="POSIX sessions and process groups")
    def test_child_survives_its_launchers_process_group(self, tmp_path):
        plant_fetch_day(tmp_path)
        p = subprocess.Popen([sys.executable, QL, "launch"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                             env=querylog_env(tmp_path), start_new_session=True)
        p.communicate(json.dumps(session_end()).encode("utf-8"), timeout=60)
        exited = time.time()
        try:
            os.killpg(p.pid, signal.SIGKILL)  # what ending the hook's session does to what is left in it
        except ProcessLookupError:
            pass  # nothing left in the group: the child runs in a session of its own
        files = wait_for_run(tmp_path)
        assert files and files[0].stat().st_mtime > exited

    @pytest.mark.skipif(os.name != "nt", reason="Windows job objects")
    def test_child_survives_a_kill_on_close_job(self, tmp_path):
        """The launcher runs inside a job object that kills its processes when the job closes; the distill it starts
        breaks away (CREATE_BREAKAWAY_FROM_JOB) and writes its run file after the job is gone."""
        plant_fetch_day(tmp_path)
        p = subprocess.run([sys.executable, "-c", JOB_PARENT, QL], input=json.dumps(session_end()).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=120)
        exited = time.time()
        assert p.returncode == 0, p.stderr
        files = wait_for_run(tmp_path)
        assert files and files[0].stat().st_mtime > exited

    @pytest.mark.skipif(not SH, reason="no sh on PATH (Windows without Git Bash)")
    @pytest.mark.parametrize("rel,var", [(".claude/settings.json", "CLAUDE_PROJECT_DIR"),
                                         (".claude-plugin/plugin.json", "CLAUDE_PLUGIN_ROOT")])
    def test_shell_form_launches(self, tmp_path, rel, var):
        """The SessionEnd command as Claude Code runs it (`sh -c`, Git Bash on Windows) starts the distill and returns
        without waiting for it: the run file is written after the command returned (the distill settles for
        LAUNCH_SETTLE_S first). No wall-clock bound here: sh and the interpreter probe cost what the host's load
        makes them cost, and the launcher's own budget is held by the two tests above."""
        (h,) = load(rel)["hooks"]["SessionEnd"][0]["hooks"]
        cmd = h["command"].replace("${" + var + "}", KB.replace("\\", "/"))
        plant_fetch_day(tmp_path)
        rc, out, err, returned = self.shell_run(tmp_path, cmd, var)
        assert (rc, out) == (0, b""), err
        files = wait_for_run(tmp_path)
        assert files and files[0].stat().st_mtime > returned, err

    @pytest.mark.skipif(not SH, reason="no sh on PATH (Windows without Git Bash)")
    def test_shell_form_check_catches_a_waiting_launcher(self, tmp_path):
        """Planted: a SessionEnd command that runs the distill itself, so it returns only after the run file exists,
        fails the check test_shell_form_launches makes."""
        (h,) = load(".claude/settings.json")["hooks"]["SessionEnd"][0]["hooks"]
        assert h["command"].endswith(" launch"), h["command"]
        cmd = h["command"][:-len("launch")] + "distill --settle 0"
        cmd = cmd.replace("${CLAUDE_PROJECT_DIR}", KB.replace("\\", "/"))
        plant_fetch_day(tmp_path)
        _rc, _out, err, returned = self.shell_run(tmp_path, cmd, "CLAUDE_PROJECT_DIR")  # rc: the push step's, not ours
        files = wait_for_run(tmp_path)
        assert files, err
        assert not files[0].stat().st_mtime > returned  # the check above would fail on this command

    @pytest.mark.skipif(not GIT, reason="git is not installed")
    def test_the_real_distill_under_querylog_env_delivers_nothing(self, tmp_path):
        """A plugin host whose install source is recorded: the plugin copy (the tools, at cache/mkt/it-ops-kb/<version>)
        whose known_marketplaces.json names a local bare repository. The real distill under querylog_env, as the tests
        above start it, writes its run file and clones and pushes nothing. Planted: without the mode querylog_env pins
        (mode=None), mode `auto` takes host_push, which clones the install source to push the test's entries."""
        env = git_env()
        bare = tmp_path / "remote.git"
        subprocess.run([GIT, "init", "-q", "--bare", str(bare)], env=env, check=True, capture_output=True, timeout=60)
        root = plugins_dir(tmp_path, {"source": "git", "url": str(bare)})
        shutil.copytree(TOOLS, root / "_tools", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        assert ql_deliver.install_url(root) == str(bare)

        def distill(data, **kw):
            plant_fetch_day(data)
            p = subprocess.run([sys.executable, str(root / "_tools" / "querylog.py"), "distill", "--settle", "0"],
                               capture_output=True, text=True, encoding="utf-8", timeout=120,
                               env=querylog_env(data, home=str(root), base={**env, "KB_INDEX": str(root / "_cache")},
                                                **kw))
            q = Path(data) / "querylog"
            return p, q, sorted((q / "store").rglob("*.jsonl")), (q / ql_deliver.CLONE_NAME).exists()

        p, q, files, cloned = distill(tmp_path / "data")
        assert p.returncode == 0 and files and not cloned, p.stdout + p.stderr
        assert "apply --push" not in p.stdout + p.stderr and not (q / ql_deliver.WORKTREE_NAME).exists()
        refs = subprocess.run([GIT, "for-each-ref"], cwd=bare, env=env, capture_output=True, text=True, timeout=60)
        assert (refs.returncode, refs.stdout) == (0, "")  # nothing pushed
        p, q, files, cloned = distill(tmp_path / "planted", mode=None)
        assert files and cloned, p.stdout + p.stderr  # planted: mode auto reaches the install source

    @staticmethod
    def shell_run(data, cmd, var):
        """(exit code, stdout, stderr, time it returned) of CMD under sh with the hook's input and environment."""
        env = querylog_env(data, base=dict(os.environ, **{var: KB}))
        p = subprocess.run([SH, "-c", cmd], input=json.dumps(session_end()).encode("utf-8"), capture_output=True,
                           env=env, timeout=120)
        return p.returncode, p.stdout, p.stderr, time.time()

    @staticmethod
    def two_sessions(tmp_path):
        """A spool with a closed session (idle past SESSION_IDLE_CLOSED_S) and an active one, each one kb_show row;
        (spool, closed id, active id, the active file's bytes)."""
        sp = spool(tmp_path)
        sp.mkdir(parents=True)
        auto_config(tmp_path / "querylog", "local")  # the rows of what it wrote go at once
        closed, active = "cccccccc-0000-4000-8000-000000000001", "cccccccc-0000-4000-8000-000000000002"
        for sid in (closed, active):
            row = {"id": str(uuid.uuid4()), "ts": "2026-09-20T10:00:00.000Z", "surface": "mcp", "session_id": sid,
                   "prompt_id": "p1", "tool": "kb_show", "args": {"path": "public/windows/laps.md:12"},
                   "articles": ["public/windows/laps.md"], "lines": [{"line": "public/windows/laps.md:12"}]}
            # no question: nothing for Haiku
            (sp / f"{sid}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8", newline="\n")
        old = time.time() - ql_distill.SESSION_IDLE_CLOSED_S - 60
        os.utime(sp / f"{closed}.jsonl", (old, old))
        return sp, closed, active, (sp / f"{active}.jsonl").read_bytes()

    def test_session_start_picks_up_closed_sessions_only(self, tmp_path):
        """SessionStart starts a distill of the closed session alone and returns without waiting for it: the run file
        is written after the launcher exited (the distill settles LAUNCH_SETTLE_S first). No wall-clock bound: the
        interpreter's start costs what the host's load makes it cost, and the budget of launch() itself is held by
        test_launch_itself_fits_its_share_of_the_budget."""
        sp, closed, active, before = self.two_sessions(tmp_path)
        rc, out, _took, exited = launch_proc(tmp_path, session_start())
        assert (rc, out) == (0, b"")
        (run,) = wait_for_run(tmp_path)
        assert run.stat().st_mtime > exited  # written after the launcher was gone
        (entry,) = jsonl(run)[1:]
        assert (entry["surface"], entry["articles"]) == ("mcp", ["public/windows/laps.md"])
        assert sorted(p.name for p in sp.iterdir()) == [f"{active}.jsonl"]
        assert (sp / f"{active}.jsonl").read_bytes() == before

    def test_session_start_check_catches_a_waiting_launcher(self, tmp_path):
        """Planted: a hook that runs the distill itself returns only after the run file exists, so the check
        test_session_start_picks_up_closed_sessions_only makes fails on it."""
        self.two_sessions(tmp_path)
        p = subprocess.run([sys.executable, QL, "distill", "--settle", "0"], capture_output=True,
                           env=querylog_env(tmp_path), timeout=120)
        exited = time.time()
        files = wait_for_run(tmp_path)
        assert files, p.stdout + p.stderr
        assert not files[0].stat().st_mtime > exited

    def test_session_start_starts_nothing_when_no_session_is_closed(self, tmp_path):
        sp = spool(tmp_path)
        sp.mkdir(parents=True)
        (sp / f"{SID}.jsonl").write_text("{}\n", encoding="utf-8")
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        (sp / f"tools-{today}.jsonl").write_text("{}\n", encoding="utf-8")
        assert launch_proc(tmp_path, session_start())[:2] == (0, b"")
        assert not (tmp_path / "querylog" / ql_distill.LOG_NAME).exists()
        assert ql_distill.launch({"hook_event_name": "Stop"}) is None

    def test_launcher_starts_nothing_while_a_distill_runs(self, tmp_path):
        plant_fetch_day(tmp_path)
        lock = ql_base.acquire(tmp_path / "querylog")
        assert launch_proc(tmp_path, session_start())[:2] == (0, b"")
        assert not (tmp_path / "querylog" / ql_distill.LOG_NAME).exists()
        ql_base.release(lock)
