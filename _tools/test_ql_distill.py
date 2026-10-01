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
                    prompts of its claim-to-done-or-release window summed (kb prompts or not, overlapping windows
                    each counting the prompt) and one shared line per session that worked an item with its prompts
                    outside any window, a run file of no entry when nothing else was written, none for a session that
                    worked no item, a done with no claim or a session still open; `missing` counts window prompts
                    without usage of this reader; a usage record outside the closed shape is not counted; the
                    windows are `ql_capture.usage_targets`'; a prompt counted by an earlier run is not counted again
                    (planted: without the record of counted prompts it is); no session, prompt or text in the file
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


WA, WB = "TK-aaaaaaaa", "TK-bbbbbbbb"  # item ids as backlog.py writes them
W1, W2, W3, W4, W5 = (f"bbbbbbbb-0000-4000-8000-00000000000{i}" for i in range(1, 6))


def counts_of(n):
    return {"requests": 1, "in": n, "cw": 10 * n, "cw1h": n, "cr": 100 * n, "out": n}


def total_of(ns):
    """The counts of the prompts whose `counts_of` numbers are `ns`, added."""
    return {"requests": len(ns), "in": sum(ns), "cw": 10 * sum(ns), "cw1h": sum(ns), "cr": 100 * sum(ns),
            "out": sum(ns)}


def work_rows(sid, plan, reader=None):
    """A session's spool rows. `plan` lists per prompt p0, p1, ...: (its work rows as "claim:ID", "done:ID" or
    "release:ID", the number n of its usage record or None, whether that record has a subagent, whether the prompt
    used the kb)."""
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
            if sub:
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
    def test_work_sidecar_written_beside_the_run_file(self, tmp_path):
        """A holds prompts p1 p2 p3 of the first session and both of the second, B holds p2 p3 p4 (the prompts of its
        claim, of A's done and of its release), and the prompts outside every window with usage, p0 and p5 and the
        second session's third, are shared."""
        q = tmp_path / "querylog"
        plant_work(q, W1, PLAN_ONE)
        plant_work(q, W2, PLAN_TWO)
        plant_work(q, W3, [(("done:" + WB,), 1, False, False), ((), 2, False, False)])  # a done with no claim: none
        plant_work(q, W4, [((), 3, False, True), ((), 4, False, True)])  # kb prompts, no item worked: none
        plant_work(q, W5, [(("claim:" + WA,), 5, False, False)], closed=False)  # still open: not yet
        rc, said = run_distill(q, echo)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=2 dropped=0 waiting=0 usage=2 work=4"], said
        sub = {"Explore": {"claude-haiku-4-5-20251001": counts_of(3)}}
        assert jsonl(work_sidecar_of(q)) == [
            {"run": RUN_ID, "reader": kbusage.READER_VERSION, "counts": {"items": 2, "shared": 2, "missing": 0}},
            {"item": WA, "prompts": 5, "main": work_main(2, 3, 4, 7, 8), "sub": sub},
            {"item": WB, "prompts": 3, "main": work_main(3, 4, 5), "sub": sub},
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

    def test_work_sidecar_the_record_of_counted_prompts_drops_sessions_that_left_the_spool(self, tmp_path):
        q = tmp_path / "querylog"
        plant_work(q, W1, PLAN_ONE)
        (q / ql_distill.WORKED_NAME).write_text(json.dumps({"gone-session": ["p1"], W1: ["p9"]}), encoding="utf-8")
        run_distill(q, echo)
        assert json.loads((q / ql_distill.WORKED_NAME).read_text(encoding="utf-8")) == \
            {W1: ["p0", "p1", "p2", "p3", "p4", "p5", "p9"]}


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
