"""Usage reader and query log usage sidecar tests (kb/_self/usage.md; `python3 _tools/tests.py -k kbusage`).
  TestReader        the fixture transcript (_tools/fixtures/kbusage/session.jsonl and its subagents/) gives each
                    prompt's exact record: one count per request id (the most output of its records), synthetic and
                    sidechain records of the main file left out, subagents by the prompt that started them and by
                    agent group, tool groups, steps with their growth (none after a shrink); no text of the transcript
                    reaches a record; a missing file or prompt gives None; the step cap; reading from the end in
                    small blocks gives the same record; the command line
  TestSessionEnd    add_usage writes one `usage` row per kb prompt of the session (none for a prompt that did not use
                    the kb, the prompt still running, a transcript that cannot be read or an unsafe session id), once
                    per prompt and reader, with no text and no path; the next prompt's capture writes the earlier
                    prompts' rows; the SessionEnd launcher passes the session id and transcript path to
                    the distill it starts, also while a distill holds the lock; distill writes those rows first;
                    --session and --transcript go together
  TestWorkUsage     the same rows for every prompt inside a work window of the session (a claim row to the done or
                    release row of the same item, both prompts included, an open window running to the end of the
                    spool), kb prompts or not; a prompt outside any window keeps the kb rule; none twice, none for the
                    running prompt, none for a window that was closed, never opened or another item's; the next
                    prompt's capture and the distill write them
  TestWorkSubagent  a subagent transcript whose records name one `work/<id>` branch (in `gitBranch`) is counted under
                    `routed` by that item id and left out of `sub`; a worker's earlier branches are ignored; none,
                    two work branches or a name only like one (an id's shape, extra path parts) leave it in `sub`;
                    no branch string reaches the record or the command line's output (`-k work_subagent`)
  TestSidecar       distill writes the usage sidecar beside the run file: one line per written entry with usage,
                    `missing` counting the rest, the store gates pass; a row of another reader version is left out;
                    a second distill writes nothing; delivery copies the sidecar with its run file
  TestUsageGates    the sidecar gates, each with a planted failure: header fields, a run id that names another file,
                    no run file beside it, a count that does not match, an entry the run file lacks, an id twice, an
                    unknown field (text), a model id, agent group or tool group outside its shape, a count that is
                    not a count, cw1h above cw, a step without tools
  TestDigest        the digest's usage lines from a store with a sidecar, the same in two copies; none without one
  TestTree          `kbusage.py tree`: the rollup of tool results of a transcript with its subagents or of a project
                    directory, by tool, Bash command head, file path and agent group; a tool use answered twice counts
                    once, a result without its tool use and a tool use without a result are counted; the totals checked
                    against the usage, each check with a planted failure (a group whose rows do not add up, result
                    characters no fresh input could hold); the text and `--format json` forms, `--top`, exit codes;
                    no text of the transcript in the output
"""
import copy, datetime, json, shutil, subprocess, sys
from pathlib import Path

import pytest

import kbusage, ql_distill, ql_deliver, ql_report, ql_store
from conftest import TOOLS, querylog_env

FIX = Path(TOOLS) / "fixtures" / "kbusage"
SESSION = FIX / "session.jsonl"
QL = str(Path(TOOLS) / "querylog.py")
SID = "3f2a4c1e-0000-4000-8000-00000000abcd"
NOW = datetime.datetime(2026, 9, 28, 12, 0, tzinfo=datetime.timezone.utc)
RUN_ID = "20260928T120000Z-0000abcd"
E1, E2 = "11111111-0000-4000-8000-0000000000b1", "11111111-0000-4000-8000-0000000000b2"

P1 = {"main": {"claude-opus-5-5": {"requests": 2, "in": 5, "cw": 1200, "cw1h": 1200, "cr": 11000, "out": 170},
               "claude-opus-5-5[1m]": {"requests": 1, "in": 1, "cw": 300, "cw1h": 0, "cr": 6200, "out": 40}},
      "start": 6003,
      "sub": {"kb-lookup": {"claude-haiku-4-5-20251001": {"requests": 1, "in": 10, "cw": 3000, "cw1h": 0, "cr": 0,
                                                            "out": 80}}},
      "steps": [{"tools": [{"tool": "kb_pack", "ok": True, "chars": 100}], "grow": 199},
                {"tools": [{"tool": "Agent", "ok": True, "chars": 4}], "grow": 299}]}
P2 = {"main": {"claude-sonnet-5": {"requests": 2, "in": 9, "cw": 100, "cw1h": 0, "cr": 7900, "out": 50}},
      "start": 7005,
      "sub": {"other": {"other": {"requests": 1, "in": 1, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}}},
      "steps": [{"tools": [{"tool": "mcp:other", "ok": False, "chars": 3}]}]}


def jsonl(path):
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def write_jsonl(path, objs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
    return path


@pytest.mark.parametrize("agent_type,group", [
    ("kb-worker", "kb-worker"), ("it-ops-kb:kb-worker", "kb-worker"), ("kb-lookup", "kb-lookup"),
    ("worker", "other"), (None, "other")])
def test_ops_agent_rows_the_agent_list_names_kb_worker(agent_type, group):
    assert kbusage.agent_group(agent_type) == group


class TestReader:
    def test_prompt_records(self):
        assert kbusage.prompt_usage(str(SESSION), "p1") == P1
        assert kbusage.prompt_usage(str(SESSION), "p2") == P2

    def test_no_text_of_the_transcript(self):
        for pid in ("p1", "p2"):
            assert "PRIVATE-TEXT" not in json.dumps(kbusage.prompt_usage(str(SESSION), pid))

    @pytest.mark.parametrize("path,pid", [(None, "p1"), ("", "p1"), (str(SESSION), None), (str(SESSION), "p9"),
                                          ("/nonexistent/x.jsonl", "p1")])
    def test_none(self, path, pid):
        assert kbusage.prompt_usage(path, pid) is None

    @pytest.mark.parametrize("name,group", [
        ("mcp__kb__kb_pack", "kb_pack"), ("mcp__plugin_it-ops-kb_kb__kb_show", "kb_show"),
        ("mcp__microsoft-learn__microsoft_docs_fetch", "docs:microsoft-learn"),
        ("mcp__plugin_it-ops-kb-docs_claude-code-docs__search_claude_code_docs", "docs:claude-code-docs"),
        ("Bash", "Bash"), ("WebFetch", "WebFetch"), ("mcp__acme_internal__lookup", "mcp:other"),
        ("SomethingNew", "other"), (None, "other")])
    def test_tool_group(self, name, group):
        assert kbusage.tool_group(name) == group
        assert kbusage.TOOL_GROUP.fullmatch(group)

    def test_small_blocks(self, monkeypatch):
        monkeypatch.setattr(kbusage, "BLOCK", 7)
        assert kbusage.prompt_usage(str(SESSION), "p1") == P1

    def test_step_cap(self, tmp_path):
        recs = [{"type": "user", "promptId": "q", "message": {"content": "x"}}]
        for i in range(kbusage.STEPS_MAX + 5):
            recs.append({"type": "assistant", "requestId": f"r{i}", "message": {
                "model": "claude-sonnet-5", "usage": {"input_tokens": 1, "cache_read_input_tokens": 100 * i},
                "content": [{"type": "tool_use", "id": f"t{i}", "name": "Read", "input": {}}]}})
            recs.append({"type": "user", "promptId": "q", "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"t{i}", "content": "abc"}]}})
        rec = kbusage.prompt_usage(str(write_jsonl(tmp_path / "t.jsonl", recs)), "q")
        assert len(rec["steps"]) == kbusage.STEPS_MAX and rec["cut"] == 5
        assert rec["steps"][0] == {"tools": [{"tool": "Read", "ok": True, "chars": 3}], "grow": 100}

    def test_command_line(self):
        p = subprocess.run([sys.executable, str(Path(TOOLS) / "kbusage.py"), str(SESSION)], capture_output=True,
                           text=True, encoding="utf-8", check=True)
        got = [json.loads(ln) for ln in p.stdout.splitlines()]
        assert got == [{"prompt": 1, **P1}, {"prompt": 2, **P2}]


class TestSessionEnd:
    def spool(self, tmp_path):
        sp = tmp_path / "querylog" / "spool"
        base = {"session_id": SID, "v": 1}
        write_jsonl(sp / f"{SID}.jsonl", [
            dict(base, id="r1", ts="2026-09-28T09:00:00.000Z", surface="prompt", prompt_id="p1", prompt="x"),
            dict(base, id="r2", ts="2026-09-28T09:00:01.000Z", surface="mcp", prompt_id="p1", tool="kb_pack"),
            dict(base, id="r3", ts="2026-09-28T09:01:00.000Z", surface="prompt", prompt_id="p2", prompt="y")])
        return sp

    def test_usage_rows_for_kb_prompts_only(self, tmp_path):
        sp = self.spool(tmp_path)
        assert ql_distill.add_usage(sp, SID, str(SESSION)) == 1
        rows = jsonl(sp / f"{SID}.jsonl")
        u = rows[-1]
        assert u["surface"] == "usage" and u["prompt_id"] == "p1" and u["usage"] == P1
        assert u["reader"] == kbusage.READER_VERSION and ql_distill.readable(u)
        text = (sp / f"{SID}.jsonl").read_text(encoding="utf-8")
        assert "PRIVATE-TEXT" not in text and str(SESSION) not in text and "transcript" not in text
        assert ql_distill.add_usage(sp, SID, str(SESSION)) == 0  # once per prompt and reader

    def test_unreadable_transcript_or_session(self, tmp_path):
        sp = self.spool(tmp_path)
        assert ql_distill.add_usage(sp, SID, str(tmp_path / "missing.jsonl")) == 0
        assert ql_distill.add_usage(sp, "../x", str(SESSION)) == 0
        assert len(jsonl(sp / f"{SID}.jsonl")) == 3

    def test_launch_passes_the_transcript(self, tmp_path, monkeypatch):
        q = tmp_path / "querylog"
        self.spool(tmp_path)
        (q / "distill.lock").write_text("{}", encoding="utf-8")  # a running distill: the new one waits for it
        started = []
        monkeypatch.setattr(ql_distill, "places", lambda: (q, q / "config.json"))
        monkeypatch.setattr(ql_distill, "detach", lambda argv, log: started.append(argv) or 1)
        event = {"hook_event_name": "SessionEnd", "session_id": SID, "transcript_path": str(SESSION)}
        assert ql_distill.launch(event) == 1
        assert started[0][-4:] == ["--session", SID, "--transcript", str(SESSION)]
        assert (q / "spool" / f"{SID}.end").exists()
        started.clear()
        assert ql_distill.launch({"hook_event_name": "SessionEnd", "session_id": SID}) is None  # the lock is fresh
        assert started == []

    def test_distill_writes_usage_first(self, tmp_path):
        q = tmp_path / "querylog"
        plant(q, usage_rows=False)
        said = []
        rc = ql_distill.distill(qdir=q, cfg=q / "config.json", haiku=echo, now_dt=NOW, run_id=RUN_ID,
                                kb_commit="0" * 40, out=said.append, usage_from=(SID, str(SESSION)))
        assert rc == 0 and said[0] == "distill: usage rows written: 2", said
        got = jsonl(sidecar(q))
        assert got[0]["counts"] == {"entries": 2, "missing": 0}
        assert got[1:] == [{"id": E1, **P1}, {"id": E2, **P2}]
        assert ql_store.store_problems(q / "store") == []

    def test_next_prompt_fills_in_the_last_ones(self, tmp_path):
        self.spool(tmp_path)
        event = {"hook_event_name": "UserPromptSubmit", "session_id": SID, "prompt_id": "p3", "prompt": "next",
                 "transcript_path": str(SESSION)}
        p = subprocess.run([sys.executable, QL, "capture"], input=json.dumps(event).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=60)
        assert p.returncode == 0 and p.stdout == b""
        rows = jsonl(tmp_path / "querylog" / "spool" / f"{SID}.jsonl")
        assert [(r["surface"], r["prompt_id"]) for r in rows[3:]] == [("prompt", "p3"), ("usage", "p1")]
        assert rows[-1]["usage"] == P1

    def test_the_running_prompt_is_skipped(self, tmp_path):
        sp = self.spool(tmp_path)
        assert ql_distill.add_usage(sp, SID, str(SESSION), skip="p1") == 0

    def test_command_line_pairs_session_and_transcript(self):
        p = subprocess.run([sys.executable, QL, "distill", "--session", SID], capture_output=True, text=True)
        assert p.returncode == 2 and "go together" in p.stderr


def work_spool(tmp_path, plan, sid=SID):
    """A session spool of prompts p0, p1, ...: `plan` lists per prompt its kinds, any of "kb" (an mcp row) and
    "claim:ID", "done:ID", "release:ID" (a work row); returns the spool directory."""
    sp = tmp_path / "querylog" / "spool"
    rows, n = [], 0
    for i, kinds in enumerate(plan):
        pid = f"p{i}"
        base = {"session_id": sid, "v": 1, "prompt_id": pid}
        for surface, extra in [("prompt", {"prompt": "x"})] + [
                ("mcp", {"tool": "kb_pack"}) if k == "kb" else ("work", dict(zip(("action", "item"), k.split(":"))))
                for k in kinds]:
            n += 1
            rows.append(dict(base, id=f"r{n}", ts=f"2026-09-28T09:{n // 60:02d}:{n % 60:02d}.000Z", surface=surface,
                             **extra))
    write_jsonl(sp / f"{sid}.jsonl", rows)
    return sp


def work_transcript(tmp_path, count):
    """A transcript of prompts p0 .. p<count-1>, each one request of 10 uncached input and i output tokens."""
    recs = []
    for i in range(count):
        recs.append({"type": "user", "promptId": f"p{i}", "message": {"content": "x"}})
        recs.append({"type": "assistant", "requestId": f"q{i}", "message": {
            "model": "claude-sonnet-5", "usage": {"input_tokens": 10, "output_tokens": i}, "content": []}})
    return str(write_jsonl(tmp_path / "t.jsonl", recs))


def usage_pids(sp, sid=SID):
    return [r["prompt_id"] for r in jsonl(sp / f"{sid}.jsonl") if r["surface"] == "usage"]


A, B = "TK-aaaaaaaa", "TK-bbbbbbbb"


class TestWorkUsage:
    def test_work_usage_window_kb_and_non_kb_prompts(self, tmp_path):
        sp = work_spool(tmp_path, [[], ["claim:" + A], [], ["kb"], ["done:" + A], []])
        t = work_transcript(tmp_path, 6)
        assert ql_distill.add_usage(sp, SID, t) == 4
        assert usage_pids(sp) == ["p1", "p2", "p3", "p4"]  # the claim's and the done's prompts, none outside
        rows = [r for r in jsonl(sp / f"{SID}.jsonl") if r["surface"] == "usage"]
        assert rows[1]["usage"]["main"] == {"claude-sonnet-5": {"requests": 1, "in": 10, "cw": 0, "cw1h": 0, "cr": 0,
                                                                "out": 2}}
        assert all(ql_distill.readable(r) and r["reader"] == kbusage.READER_VERSION for r in rows)
        text = (sp / f"{SID}.jsonl").read_text(encoding="utf-8")
        assert t not in text and "transcript" not in text

    def test_work_usage_outside_a_window_keeps_the_kb_rule(self, tmp_path):
        sp = work_spool(tmp_path, [["kb"], [], ["claim:" + A], ["done:" + A], ["kb"], []])
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 6)) == 4
        assert usage_pids(sp) == ["p0", "p2", "p3", "p4"]  # p1 and p5, outside, are not kb prompts: no row

    def test_work_usage_open_window_runs_to_the_end(self, tmp_path):
        sp = work_spool(tmp_path, [[], ["claim:" + A], [], []])
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 4)) == 3
        assert usage_pids(sp) == ["p1", "p2", "p3"]

    def test_work_usage_release_closes_the_window(self, tmp_path):
        sp = work_spool(tmp_path, [["claim:" + A], [], ["release:" + A], []])
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 4)) == 3
        assert usage_pids(sp) == ["p0", "p1", "p2"]

    def test_work_usage_planted_prompts_no_window_covers_get_none(self, tmp_path):
        """A done with no claim, another item's done, and a window another session holds open the wrong rows: each
        planted case writes no row for a prompt that is not in a window of its own session."""
        sp = work_spool(tmp_path, [["done:" + A], [], ["claim:" + A], ["done:" + B], [], ["done:" + A], []])
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 7)) == 4
        assert usage_pids(sp) == ["p2", "p3", "p4", "p5"]  # p0 (done without a claim), p1 and p6 get none
        other = "9a9a9a9a-0000-4000-8000-00000000dcba"
        sp2 = work_spool(tmp_path, [[], [], []], sid=other)  # no window in this session, though SID's is open
        assert ql_distill.add_usage(sp2, other, work_transcript(tmp_path, 3)) == 0

    def test_work_usage_two_items_overlap(self, tmp_path):
        sp = work_spool(tmp_path, [["claim:" + A], ["claim:" + B], ["done:" + A], [], ["done:" + B], []])
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 6)) == 5
        assert usage_pids(sp) == ["p0", "p1", "p2", "p3", "p4"]  # B holds the window open after A's done

    def test_work_usage_no_duplicate_row_on_a_second_run(self, tmp_path):
        sp = work_spool(tmp_path, [["claim:" + A], [], ["kb"]])
        t = work_transcript(tmp_path, 3)
        assert ql_distill.add_usage(sp, SID, t) == 3
        before = (sp / f"{SID}.jsonl").read_bytes()
        assert ql_distill.add_usage(sp, SID, t) == 0
        assert (sp / f"{SID}.jsonl").read_bytes() == before

    def test_work_usage_a_prompt_with_a_row_gets_none_and_another_reader_does(self, tmp_path):
        sp = work_spool(tmp_path, [["claim:" + A], [], []])
        have = {"id": "u1", "ts": "2026-09-28T10:00:00.000Z", "surface": "usage", "v": 1, "session_id": SID,
                "prompt_id": "p1", "reader": kbusage.READER_VERSION, "usage": P1}
        with open(sp / f"{SID}.jsonl", "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(have) + "\n" + json.dumps(dict(have, id="u2", prompt_id="p2",
                                                              reader=kbusage.READER_VERSION + 1)) + "\n")
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 3)) == 2
        assert usage_pids(sp) == ["p1", "p2", "p0", "p2"]

    def test_work_usage_the_running_prompt_is_skipped(self, tmp_path):
        sp = work_spool(tmp_path, [["claim:" + A], [], []])
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 3), skip="p2") == 2
        assert usage_pids(sp) == ["p0", "p1"]

    def test_work_usage_a_prompt_the_transcript_lacks_gets_none(self, tmp_path):
        sp = work_spool(tmp_path, [["claim:" + A], [], []])
        assert ql_distill.add_usage(sp, SID, work_transcript(tmp_path, 2)) == 2
        assert usage_pids(sp) == ["p0", "p1"]

    def test_work_usage_next_prompt_capture_writes_the_window_rows(self, tmp_path):
        work_spool(tmp_path, [[], ["claim:" + A], []])
        event = {"hook_event_name": "UserPromptSubmit", "session_id": SID, "prompt_id": "p3", "prompt": "next",
                 "transcript_path": work_transcript(tmp_path, 4)}
        p = subprocess.run([sys.executable, QL, "capture"], input=json.dumps(event).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=60)
        assert p.returncode == 0 and p.stdout == b""
        spool = tmp_path / "querylog" / "spool"
        assert usage_pids(spool) == ["p1", "p2"]  # never the prompt being recorded (p3), nor p0 before the claim

    def test_work_usage_distill_writes_the_window_rows_first(self, tmp_path):
        q = tmp_path / "querylog"
        work_spool(tmp_path, [[], ["claim:" + A], [], ["kb"]])
        said = []
        ql_distill.distill(qdir=q, cfg=q / "config.json", haiku=echo, now_dt=NOW, run_id=RUN_ID,
                                kb_commit="0" * 40, out=said.append, usage_from=(SID, work_transcript(tmp_path, 4)))
        assert said[0] == "distill: usage rows written: 3", said
        assert usage_pids(q / "spool") == ["p1", "p2", "p3"]


def subagent_transcript(tmp_path, branches, agent="a1", agent_type="Explore", out=7):
    """A main transcript of one prompt p0 (one request) with a subagent transcript whose records name the git branches
    `branches` in order (None: no `gitBranch`), each with one request of `out` output tokens; the main file's path."""
    main = write_jsonl(tmp_path / "t.jsonl", [
        {"type": "user", "promptId": "p0", "message": {"content": "x"}, "gitBranch": "main"},
        {"type": "assistant", "requestId": "q0", "gitBranch": "main", "message": {
            "model": "claude-sonnet-5", "usage": {"input_tokens": 10, "output_tokens": 1}, "content": []}}])
    recs = [{"type": "user", "promptId": "p0", "isSidechain": True, "message": {"content": "x"}}]
    for i, b in enumerate(branches):
        rec = {"type": "assistant", "requestId": f"s{agent}{i}", "isSidechain": True, "message": {
            "model": "claude-haiku-4-5", "usage": {"input_tokens": 2, "output_tokens": out}, "content": []}}
        if b is not None:
            rec["gitBranch"] = b
        recs.append(rec)
    d = tmp_path / "t" / "subagents"
    write_jsonl(d / f"agent-{agent}.jsonl", recs)
    (d / f"agent-{agent}.meta.json").write_text(json.dumps({"agentType": agent_type}), encoding="utf-8")
    return str(main)


def haiku_counts(n, out):
    return {"claude-haiku-4-5": {"requests": n, "in": 2 * n, "cw": 0, "cw1h": 0, "cr": 0, "out": out}}


class TestWorkSubagent:
    """A subagent transcript's `work/<id>` branch routes its counts to that item (`-k work_subagent`)."""

    def test_work_subagent_branch_routing(self, tmp_path):
        """The worker starts on the branch its worktree was made on and moves to its work branch: the item is the one
        work branch, the counts are `routed` and no longer `sub`, and no branch string is in the record."""
        t = subagent_transcript(tmp_path, ["main", "worktree-agent-a1", "work/" + A, "work/" + A])
        rec = kbusage.prompt_usage(t, "p0")
        assert rec["routed"] == {A: {"Explore": haiku_counts(4, 28)}} and "sub" not in rec
        assert rec["main"] == {"claude-sonnet-5": {"requests": 1, "in": 10, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}}
        text = json.dumps(rec)
        assert "work/" not in text and "worktree" not in text and "gitBranch" not in text

    def test_work_subagent_work_item(self):
        rs = lambda *bs: [{"gitBranch": b} if b is not None else {} for b in bs]  # noqa: E731
        assert kbusage.work_item(rs("main", "work/" + A)) == A
        assert kbusage.work_item(rs("work/SP-aaaaaaaa", "work/SP-aaaaaaaa")) == "SP-aaaaaaaa"
        for none in (rs(), rs("main"), rs("work/" + A, "work/" + B), rs("work/" + A + "x"), rs("work/ST-AAAAAAAA"),
                     rs("feature/work/" + A), rs("work/" + A + "/sub"), rs("work/XX-aaaaaaaa"), rs("work/TK-aaaaaaa1"),
                     [{"gitBranch": 5}, {"gitBranch": None}, {"gitBranch": ["work/" + A]}]):
            assert kbusage.work_item(none) is None, none

    @pytest.mark.parametrize("branches", [["main"], ["worktree-agent-a1", "main"], [None, None], ["work/TK-short"],
                                          ["work/" + A, "work/" + B], ["feature/x/work/" + A]])
    def test_work_subagent_non_work_branch_ignored(self, tmp_path, branches):
        """A subagent on no work branch, on two of them or on a name that is only like one stays in `sub`."""
        rec = kbusage.prompt_usage(subagent_transcript(tmp_path, branches), "p0")
        assert rec["sub"] == {"Explore": haiku_counts(len(branches), 7 * len(branches))} and "routed" not in rec

    def test_work_subagent_routed_and_unrouted_apart(self, tmp_path):
        """Two subagents of the prompt, one on a work branch: `sub` holds the other, `routed` the first, by its
        agent group."""
        t = subagent_transcript(tmp_path, ["work/" + A], agent="a1", agent_type="it-ops-kb:kb-lookup")
        subagent_transcript(tmp_path, ["main"], agent="a2", out=9)
        rec = kbusage.prompt_usage(t, "p0")
        assert rec["routed"] == {A: {"kb-lookup": haiku_counts(1, 7)}}
        assert rec["sub"] == {"Explore": haiku_counts(1, 9)}

    def test_work_subagent_no_row_changes_without_a_work_branch(self):
        """The fixture's subagents record no branch: the records are the ones the sidecar always kept."""
        assert "routed" not in kbusage.prompt_usage(str(SESSION), "p1")
        assert kbusage.prompt_usage(str(SESSION), "p1") == P1

    def test_work_subagent_command_line_prints_the_item_only(self, tmp_path):
        t = subagent_transcript(tmp_path, ["work/" + A])
        p = subprocess.run([sys.executable, str(Path(TOOLS) / "kbusage.py"), t], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        assert p.returncode == 0 and A in p.stdout and "work/" not in p.stdout, p.stdout


def plant(qdir, usage_rows=True, reader=None):
    """A closed session of two kb prompts (E1 with a usage row, E2 without) in qdir/spool."""
    sp = Path(qdir) / "spool"
    rows = []
    for eid, pid, t in ((E1, "p1", "09:00"), (E2, "p2", "09:10")):
        base = {"session_id": SID, "prompt_id": pid, "v": 1}
        rows += [dict(base, id=eid, ts=f"2026-09-28T{t}:00.000Z", surface="prompt", prompt="kb question"),
                 dict(base, id=eid[:-2] + "c" + eid[-1], ts=f"2026-09-28T{t}:01.000Z", surface="mcp", tool="kb_pack",
                      args={"question": "windows laps password length"}, verdict="good",
                      articles=["public/windows/laps.md"],
                      lines=[{"line": "public/windows/laps.md:5", "tag": "DOC", "verdict": "good"}]),
                 dict(base, id=eid[:-2] + "d" + eid[-1], ts=f"2026-09-28T{t}:02.000Z", surface="stop",
                      answer="done")]
    if usage_rows:
        rows.append({"id": "11111111-0000-4000-8000-0000000000e1", "ts": "2026-09-28T09:00:03.000Z",
                     "surface": "usage", "v": 1, "session_id": SID, "prompt_id": "p1",
                     "reader": reader or kbusage.READER_VERSION, "usage": P1})
    write_jsonl(sp / f"{SID}.jsonl", rows)
    (sp / f"{SID}.end").touch()


def echo(prompt):
    items = json.loads(prompt[prompt.index("\n\n[") + 2:])
    return json.dumps([{"i": it["i"], "judged": "answered", "best": None, "identifying": False} for it in items])


def distill(qdir):
    said = []
    rc = ql_distill.distill(qdir=qdir, cfg=Path(qdir) / "config.json", haiku=echo, now_dt=NOW, run_id=RUN_ID,
                            kb_commit="0" * 40, out=said.append)
    return rc, said


def sidecar(qdir):
    return Path(qdir) / "store" / "usage" / "2026-09" / f"{RUN_ID}.jsonl"


class TestSidecar:
    def test_written_beside_the_run_file(self, tmp_path):
        q = tmp_path / "querylog"
        plant(q)
        rc, said = distill(q)
        assert rc == 0 and said == [f"distill: run={RUN_ID} entries=2 dropped=0 waiting=0 usage=1"], said
        got = jsonl(sidecar(q))
        assert got == [{"run": RUN_ID, "reader": kbusage.READER_VERSION, "counts": {"entries": 1, "missing": 1}},
                       {"id": E1, **P1}]
        assert ql_store.store_problems(q / "store") == []
        assert "PRIVATE-TEXT" not in sidecar(q).read_text(encoding="utf-8")

    def test_other_reader_left_out(self, tmp_path):
        q = tmp_path / "querylog"
        plant(q, reader=kbusage.READER_VERSION + 1)
        distill(q)
        assert not sidecar(q).exists()

    def test_second_distill_writes_nothing(self, tmp_path):
        q = tmp_path / "querylog"
        plant(q)
        distill(q)
        before = {p: p.read_bytes() for p in (q / "store").rglob("*.jsonl")}
        rc, said = distill(q)
        assert rc == 0 and {p: p.read_bytes() for p in (q / "store").rglob("*.jsonl")} == before

    def test_delivery_copies_the_sidecar(self, tmp_path):
        q = tmp_path / "querylog"
        plant(q)
        distill(q)
        pusher = ql_deliver.Pusher(tmp_path, q, None, lambda *a: 0, print, cloud=False)
        _, new, _ = pusher.local_files()
        assert sorted(rel for _, rel, _ in new) == [f"2026-09/{RUN_ID}.jsonl", f"usage/2026-09/{RUN_ID}.jsonl"]


def planted_store(tmp_path, change=None, run_change=None):
    """A store with one run file (entries E1, E2) and its sidecar; `change(objects)` edits the sidecar's objects,
    `run_change(path)` the layout. Its usage problems."""
    q = tmp_path / "querylog"
    plant(q)
    distill(q)
    store = q / "store"
    objs = jsonl(sidecar(q))
    if change:
        change(objs)
    write_jsonl(sidecar(q), objs)
    if run_change:
        run_change(store)
    return ql_store.usage_problems(store)


def set_(path, value):
    def f(objs):
        target = objs
        for k in path[:-1]:
            target = target[k]
        target[path[-1]] = value
    return f


class TestUsageGates:
    def test_clean(self, tmp_path):
        assert planted_store(tmp_path) == []

    @pytest.mark.parametrize("change,needle", [
        (set_([0, "kb_commit"], "0" * 40), "a usage header is exactly"),
        (set_([0, "run"], "20260928T120000Z-0000ffff"), "run id does not name this file"),
        (set_([0, "reader"], 0), "reader is not a version number"),
        (set_([0, "counts", "entries"], 3), "counts.entries is 3"),
        (set_([0, "counts"], {"entries": 1}), "counts are not"),
        (set_([1, "id"], E2[:-1] + "9"), "is not in run file"),
        (set_([1, "prompt"], "how long is the laps password"), "fields a usage line never has: prompt"),
        (set_([1, "main"], {"jan.kowalski@corp.example.com": P1["main"]["claude-opus-5-5"]}), "is not a model id"),
        (set_([1, "main", "claude-opus-5-5", "in"], -1), "as counts"),
        (set_([1, "main", "claude-opus-5-5", "note"], 1), "as counts"),
        (set_([1, "main", "claude-opus-5-5", "cw1h"], 999999), "cw1h of 'claude-opus-5-5' exceeds cw"),
        (set_([1, "sub"], {"payroll-agent": P1["sub"]["kb-lookup"]}), "is not an agent group"),
        (set_([1, "steps", 0, "tools", 0, "tool"], "Bash: curl https://corp.example.com"), "a step that is not"),
        (set_([1, "steps", 0, "tools"], []), "a step that is not"),
        (set_([1, "steps", 0, "grow"], "199"), "a step that is not"),
        (set_([1, "start"], None), "start is not a count"),
        (set_([1, "cut"], 0), "cut is not a positive count"),
    ])
    def test_planted(self, tmp_path, change, needle):
        problems = planted_store(tmp_path, change)
        assert any(needle in p for p in problems), problems

    def test_duplicate_id(self, tmp_path):
        problems = planted_store(tmp_path, lambda objs: (objs.append(copy.deepcopy(objs[1])),
                                                         objs[0]["counts"].update(entries=2)))
        assert any("duplicate usage id" in p for p in problems), problems

    def test_no_run_file_beside_it(self, tmp_path):
        problems = planted_store(tmp_path, run_change=lambda s: (s / "2026-09" / f"{RUN_ID}.jsonl").unlink())
        assert any("no run file" in p for p in problems), problems

    def test_check_runs_the_usage_gates(self, tmp_path):
        planted_store(tmp_path, set_([1, "prompt"], "x"))
        assert any("usage" in p for p in ql_store.store_problems(tmp_path / "querylog" / "store"))


class TestDigest:
    def test_usage_lines(self, tmp_path):
        q = tmp_path / "querylog"
        plant(q)
        distill(q)
        copy_ = tmp_path / "copy"
        shutil.copytree(q / "store", copy_)
        _, lines, _ = ql_report.digest(q / "store", "2026-W40")
        assert lines == ql_report.digest(copy_, "2026-W40")[1]
        total = 5 + 1200 + 11000 + 1 + 300 + 6200 + 10 + 3000
        assert (f"usage: 1 of 2 lookups; input tokens per lookup median {total}, p90 {total}; output median 290; "
                f"cache reads {round(100 * 17200 / total)}% of input, subagents {round(100 * 3010 / total)}%") in lines
        assert "kb results: 1 steps, context growth median 199 tokens, result characters median 100" in lines

    def test_no_sidecar(self, tmp_path):
        q = tmp_path / "querylog"
        plant(q, usage_rows=False)
        distill(q)
        assert "usage: 0 of 2 lookups" in ql_report.digest(q / "store", "2026-W40")[1]


def tool_use(rid, uid, name, inp, inp_tokens=100, cwd=None, side=False):
    r = {"type": "assistant", "requestId": rid, "message": {
        "model": "claude-sonnet-5", "usage": {"input_tokens": 1, "cache_creation_input_tokens": inp_tokens,
                                              "cache_read_input_tokens": 50, "output_tokens": 5},
        "content": [{"type": "tool_use", "id": uid, "name": name, "input": inp}]}}
    if cwd:
        r["cwd"] = cwd
    if side:
        r["isSidechain"] = True
    return r


def tool_result(uid, content, error=False, side=False):
    b = {"type": "tool_result", "tool_use_id": uid, "content": content}
    if error:
        b["is_error"] = True
    r = {"type": "user", "message": {"role": "user", "content": [b]}}
    if side:
        r["isSidechain"] = True
    return r


def rows_of(rep, group):
    return {r["key"]: (r["calls"], r["chars"], r["errors"]) for r in rep["rows"] if r["group"] == group}


def run_tree(path, *args):
    return subprocess.run([sys.executable, str(Path(TOOLS) / "kbusage.py"), "tree", str(path), *args],
                          capture_output=True, text=True, encoding="utf-8")


def tree_session(tmp_path, name="s1"):
    """A main transcript of placeholder tools with one subagent transcript beside it."""
    wt = "/home/jan.kowalski/proj/.claude/worktrees/agent-1"
    main = write_jsonl(tmp_path / f"{name}.jsonl", [
        {"type": "user", "promptId": "q", "message": {"content": "PRIVATE-TEXT"}},
        tool_use("r1", "u1", "Bash", {"command": "cd /x && python3 _tools/rag.py pack PRIVATE-TEXT"}, cwd=wt),
        tool_result("u1", "a" * 40),
        tool_use("r2", "u2", "Read", {"file_path": wt + "/kb/_self/a.md"}, cwd=wt),
        tool_result("u2", [{"type": "text", "text": "b" * 30}]),
        tool_use("r3", "u3", "Read", {"file_path": "/home/jan.kowalski/proj/kb/_self/a.md"}, cwd=wt),
        tool_result("u3", "c" * 20, error=True),
        tool_use("r4", "u4", "mcp__acme__lookup", {"q": "PRIVATE-TEXT"}),
        tool_result("u4", "d" * 5),
        tool_use("r5", "u5", "Grep", {"pattern": "PRIVATE-TEXT"}),
        tool_result("u5", "e" * 7)])
    sub = tmp_path / name / "subagents"
    write_jsonl(sub / "agent-a1.jsonl", [
        tool_use("s1", "v1", "Bash", {"command": "git -C /x status --short"}, side=True),
        tool_result("v1", "f" * 12, side=True),
        tool_use("s2", "v2", "Write", {"file_path": "/x/out.txt", "content": "PRIVATE-TEXT"}, side=True),
        tool_result("v2", "ok", side=True)])
    (sub / "agent-a1.meta.json").write_text(json.dumps({"agentType": "Explore"}), encoding="utf-8", newline="\n")
    return main


def tree_report(path):
    t = kbusage.Tree()
    for scope, f in kbusage.tree_files(path):
        t.scan(scope, f)
    return t.report()


class TestTree:
    def test_kbusage_tree_fixture(self):
        assert [s for s, _ in kbusage.tree_files(SESSION)] == ["main", "kb-lookup", "other"]
        rep = tree_report(SESSION)
        assert rep["totals"] == {"transcripts": 1, "subagent_transcripts": 2, "calls": 3, "chars": 107, "errors": 1,
                                 "unmatched": 0, "no_result": 0, "result_tokens_est": 26, "fresh_input": 1615 + 3011}
        assert rows_of(rep, "tool") == {"kb_pack": (1, 100, 0), "Agent": (1, 4, 0),
                                        "mcp__claude_ai_Gmail__search_threads": (1, 3, 1)}
        assert rows_of(rep, "agent") == {"main": (3, 107, 1)}
        assert rep["usage"]["main"] == {"requests": 5, "in": 15, "cw": 1600, "cw1h": 1200, "cr": 25100, "out": 260}
        assert rep["usage"]["sub"]["requests"] == 2 and rep["usage"]["all"]["requests"] == 7
        assert rep["check"] == {"ok": True, "problems": []}

    def test_kbusage_tree_groups(self, tmp_path):
        rep = tree_report(tree_session(tmp_path))
        assert rows_of(rep, "tool") == {"Bash": (2, 52, 0), "Read": (2, 50, 1), "mcp__acme__lookup": (1, 5, 0),
                                        "Grep": (1, 7, 0), "Write": (1, 2, 0)}
        assert rows_of(rep, "bash") == {"python3 _tools/rag.py pack": (1, 40, 0), "git status": (1, 12, 0)}
        # the worktree's file and the project's own are one file
        assert rows_of(rep, "file") == {"kb/_self/a.md": (2, 50, 1), "/x/out.txt": (1, 2, 0)}
        assert rows_of(rep, "agent") == {"main": (5, 102, 1), "Explore": (2, 14, 0)}
        assert [r["chars"] for r in rep["rows"] if r["group"] == "tool"] == [52, 50, 7, 5, 2]
        assert rep["usage"]["main"]["requests"] == 5 and rep["usage"]["sub"]["requests"] == 2
        assert rep["check"]["ok"], rep["check"]

    def test_kbusage_tree_directory(self, tmp_path):
        tree_session(tmp_path, "s1")
        tree_session(tmp_path, "s2")
        (tmp_path / "notes.txt").write_text("not a transcript", encoding="utf-8")
        files = kbusage.tree_files(tmp_path)
        assert [(s, f.name) for s, f in files] == [("main", "s1.jsonl"), ("Explore", "agent-a1.jsonl"),
                                                   ("main", "s2.jsonl"), ("Explore", "agent-a1.jsonl")]
        a = json.loads(run_tree(tmp_path, "--format", "json").stdout)
        b = json.loads(run_tree(tmp_path / "s1.jsonl", "--format", "json").stdout)
        # the second session repeats every id of the first: each tool use and request counts once
        assert a["totals"]["calls"] == b["totals"]["calls"] == 7 and a["totals"]["transcripts"] == 2
        assert a["rows"] == b["rows"] and a["usage"] == b["usage"]

    def test_kbusage_tree_counts_a_result_once(self, tmp_path):
        recs = [tool_use("r1", "u1", "Bash", {"command": "ls"}, inp_tokens=1000), tool_result("u1", "x" * 10),
                tool_result("u1", "x" * 10), tool_result("zz", "y" * 3, error=True),
                tool_use("r2", "u2", "Bash", {"command": "ls"}, inp_tokens=1000)]
        rep = tree_report(write_jsonl(tmp_path / "t.jsonl", recs))
        assert rows_of(rep, "tool") == {"Bash": (1, 10, 0), "other": (1, 3, 1)}
        assert (rep["totals"]["calls"], rep["totals"]["unmatched"], rep["totals"]["no_result"]) == (2, 1, 1)
        assert rep["check"]["ok"]

    @pytest.mark.parametrize("command,head", [
        ("ls -la /x", "ls"), ("cd /x && git status --short", "git status"), ("git -C /x diff HEAD", "git diff"),
        ("git -c a=b log -3", "git log"), ("FOO=1 BAR=2 python3 _tools/rag.py pack 'q'", "python3 _tools/rag.py pack"),
        ("python3 /home/jan.kowalski/p/_tools/tests.py -k x", "python3 _tools/tests.py"),
        ("python3 _tools/selfdoc.py section a b", "python3 _tools/selfdoc.py section"),
        ("python3 _tools/backlog.py show TK-1", "python3 _tools/backlog.py show"),
        ("python3 -m pytest -q", "python3 -m pytest"), ("python3 -c 'print(1)'", "python3 -c"),
        ("python3 - <<'EOF'\nprint(1)\nEOF", "python3"), ("python3", "python3"),
        ("sudo /usr/bin/env gh pr list", "gh pr"), ("export A=1\n# note\ncat a | head", "cat"),
        ("cd x; pushd y\n\nsed -n 1p f", "sed"), ("echo 'unclosed", "echo"), ("", "(none)"), ("cd x", "(none)"),
        (None, "(none)"), ("glab api projects", "glab api")])
    def test_kbusage_tree_command_head(self, command, head):
        assert kbusage.command_head(command) == head

    @pytest.mark.parametrize("path,cwd,key", [
        ("/p/.claude/worktrees/w1/kb/a.md", "/p/.claude/worktrees/w1", "kb/a.md"),
        ("/p/kb/a.md", "/p/.claude/worktrees/w1", "kb/a.md"), ("/p/kb/a.md", "/p", "kb/a.md"),
        ("/q/kb/a.md", "/p", "/q/kb/a.md"), ("C:\\p\\kb\\a.md", "C:\\p", "kb/a.md"), ("kb/a.md", None, "kb/a.md")])
    def test_kbusage_tree_file_key(self, path, cwd, key):
        assert kbusage.file_key(path, cwd) == key

    @pytest.mark.parametrize("group", ["tool", "agent", "bash", "file"])
    def test_kbusage_tree_planted_rows_that_do_not_add_up(self, tmp_path, group):
        rep = tree_report(tree_session(tmp_path))
        assert kbusage.tree_problems(rep) == []
        next(r for r in rep["rows"] if r["group"] == group)["chars"] += 1
        problems = kbusage.tree_problems(rep)
        assert any(p.startswith(f"{group} rows hold") for p in problems), problems

    def test_kbusage_tree_planted_a_dropped_row(self, tmp_path):
        rep = tree_report(tree_session(tmp_path))
        rep["rows"] = [r for r in rep["rows"] if r["key"] != "Grep"]
        assert any(p.startswith("tool rows hold") for p in kbusage.tree_problems(rep))

    def test_kbusage_tree_planted_results_no_usage_could_hold(self, tmp_path):
        span = kbusage.TOKEN_SPAN_MAX
        main = write_jsonl(tmp_path / "t.jsonl", [
            tool_use("r1", "u1", "Read", {"file_path": "/x/a"}, inp_tokens=1), tool_result("u1", "z" * (span * 2 + 1))])
        p = run_tree(main)
        assert p.returncode == 1 and "check: FAILED" in p.stdout and "cannot come from 2 fresh input tokens" in p.stdout
        ok = write_jsonl(tmp_path / "u.jsonl", [
            tool_use("r1", "u1", "Read", {"file_path": "/x/a"}, inp_tokens=1), tool_result("u1", "z" * span * 2)])
        assert run_tree(ok).returncode == 0

    def test_kbusage_tree_command_line(self, tmp_path):
        main = tree_session(tmp_path)
        p = run_tree(main, "--top", "1")
        assert p.returncode == 0, p.stderr
        lines = p.stdout.splitlines()
        assert lines[0].startswith("tree: 1 transcripts, 1 subagent transcripts; 7 tool results, 116 characters (~29 ")
        assert "by bash:" in p.stdout and "  ... 1 more rows (--top 0 shows all)" in p.stdout
        assert lines[-1] == "check: ok"
        full = run_tree(main, "--top", "0").stdout
        assert "git status" in full and "python3 _tools/rag.py pack" in full and "more rows" not in full
        out = run_tree(main, "--format", "json").stdout
        j = json.loads(out)
        assert sorted(j) == ["check", "rot", "rows", "totals", "usage"]
        assert all(sorted(r) == ["calls", "chars", "errors", "group", "key"] for r in j["rows"])
        assert out == run_tree(main, "--format", "json").stdout
        for text in (p.stdout, full, out):
            assert "PRIVATE-TEXT" not in text

    def test_kbusage_tree_no_input(self, tmp_path):
        p = run_tree(tmp_path / "missing.jsonl")
        assert p.returncode == 2 and "no such file or directory" in p.stderr
        p = run_tree(tmp_path)
        assert p.returncode == 2 and "no transcripts" in p.stderr

    def test_kbusage_tree_leaves_the_prompt_form_alone(self):
        p = subprocess.run([sys.executable, str(Path(TOOLS) / "kbusage.py"), str(SESSION), "--prompt", "p2"],
                           capture_output=True, text=True, encoding="utf-8", check=True)
        assert json.loads(p.stdout) == {"prompt": 1, **P2}


def reading(rid, path, out=5):
    """An assistant record of one request (in 1, cache write 100, cache read 50, `out` output) that reads PATH."""
    r = tool_use(rid, "u" + rid, "Read", {"file_path": path}, cwd="/home/jan.kowalski/proj")
    r["message"]["usage"]["output_tokens"] = out
    return r


def boundary(pre):
    return {"type": "system", "subtype": "compact_boundary", "compactMetadata": {"trigger": "auto", "preTokens": pre}}


def prompt(pid):
    return {"type": "user", "promptId": pid, "message": {"content": "PRIVATE-TEXT"}}


def rot_session(tmp_path):
    """Three manager ticks of known numbers: t1 one compaction (150000) and a.md read three times, b.md once; t2 none
    and one read, its one request written twice (the larger output counts); t3 two compactions (100, 200) and a
    subagent of 9 tokens. Every request is 156 tokens with output 5."""
    main = write_jsonl(tmp_path / "m.jsonl", [
        prompt("t1"), reading("r1", "/home/jan.kowalski/proj/a.md"), reading("r2", "/home/jan.kowalski/proj/a.md"),
        reading("r2b", "/home/jan.kowalski/proj/b.md"), boundary(150000),
        reading("r3", "/home/jan.kowalski/proj/.claude/worktrees/w1/a.md"),  # a worktree's path is the project's
        prompt("t2"), reading("r4", "/home/jan.kowalski/proj/c.md"), reading("r4", "/home/jan.kowalski/proj/c.md", out=9),
        prompt("t3"), boundary(100), reading("r5", "/home/jan.kowalski/proj/a.md"), boundary(200),
        {"type": "assistant", "isSidechain": True, "requestId": "side", "message": {"usage": {"output_tokens": 999}}}])
    d = tmp_path / "m" / "subagents"
    write_jsonl(d / "agent-s.jsonl", [
        {"type": "user", "promptId": "t3", "isSidechain": True, "message": {"content": "x"}},
        {"type": "assistant", "requestId": "s1", "isSidechain": True, "message": {
            "model": "claude-haiku-4-5", "usage": {"input_tokens": 2, "output_tokens": 7}, "content": []}}])
    return main


def event(**kw):
    return kw


def stream_run(*extra):
    """A runner's stream of known numbers, 156 tokens a message: m1 (its event written twice, the larger output counts)
    and m2 both read a.md; a subagent's (parent tool use T) m3 reads a.md too (another agent: not repeated), m4 and m5
    read b.md (repeated); then EXTRA, a boundary in the stream's spelling."""
    def msg(mid, path, out=5, parent=None):
        return event(type="assistant", parent_tool_use_id=parent, message={
            "id": mid, "model": "claude-opus-5-5", "usage": {"input_tokens": 1, "cache_creation_input_tokens": 100,
                                                            "cache_read_input_tokens": 50, "output_tokens": out},
            "content": [{"type": "tool_use", "id": "u" + mid, "name": "Read", "input": {"file_path": path}}]})
    return [event(type="system", subtype="init"), msg("m1", "/w/a.md", 1), msg("m1", "/w/a.md"), msg("m2", "/w/a.md"),
            msg("m3", "/w/a.md", parent="T"), msg("m4", "/w/b.md", parent="T"), msg("m5", "/w/b.md", parent="T"), *extra]


def test_autopilot_rot_metrics_per_tick_compactions_tokens_and_repeated_reads(tmp_path):
    rows = kbusage.tick_rows(rot_session(tmp_path))
    assert [(r["compactions"], r["pre_tokens"], r["tokens"], r["requests"], r["reads"], r["repeated_reads"],
             r["repeated_files"]) for r in rows] == [
        (1, [150000], 4 * 156, 4, 4, 2, 1),   # r1, r2, r2b, r3: a.md three times (one worktree path), b.md once
        (0, [], 160, 1, 1, 0, 0),             # no compaction: 0, not blank; the request counted once with output 9
        (2, [100, 200], 156 + 9, 2, 1, 0, 0)]  # the main sidechain record is left out; the subagent's request counts


def test_autopilot_rot_metrics_per_runner_numbers_and_agents(tmp_path):
    base = tmp_path / "autopilot"
    boundary_ev = event(type="system", subtype="compact_boundary", compact_metadata={"trigger": "auto", "pre_tokens": 168000})
    write_jsonl(base / "SP-aaaaaaaa" / "20261001T000000Z.jsonl", stream_run(boundary_ev))
    write_jsonl(base / "SP-bbbbbbbb" / "20261002T000000Z.jsonl", stream_run()[:1])
    (base / "SP-aaaaaaaa" / "status.json").write_text("{}", encoding="utf-8", newline="\n")
    got = kbusage.rot_rows([], base)["runners"]
    assert [(r["sprint"], r["run"]) for r in got] == [("SP-aaaaaaaa", "20261001T000000Z"), ("SP-bbbbbbbb", "20261002T000000Z")]
    a, b = got
    assert (a["compactions"], a["pre_tokens"], a["tokens"], a["requests"], a["reads"], a["repeated_reads"], a["repeated_files"]) == (
        1, [168000], 5 * 156, 5, 5, 2, 2)  # main: a.md twice (m1's repeated event is one call); T: a.md once, b.md twice
    assert (b["compactions"], b["pre_tokens"], b["tokens"], b["reads"]) == (0, [], 0, 0)


def test_autopilot_rot_metrics_tree_command_prints_both_tables(tmp_path):
    main = rot_session(tmp_path)
    base = tmp_path / "autopilot"
    write_jsonl(base / "SP-aaaaaaaa" / "20261001T000000Z.jsonl", stream_run(
        event(type="system", subtype="compact_boundary", compact_metadata={"pre_tokens": 168000})))
    write_jsonl(base / "SP-bbbbbbbb" / "20261002T000000Z.jsonl", stream_run()[:1])
    p = run_tree(main, "--runners", str(base))
    assert p.returncode in (0, 1), p.stderr
    lines = p.stdout.splitlines()
    assert any(ln.startswith("by tick:") for ln in lines) and any(ln.startswith("by runner:") for ln in lines)
    tick_rows = [ln for ln in lines if ln.endswith(("  t1.1", "  t1.2", "  t1.3"))]
    assert [ln.split()[:2] for ln in tick_rows] == [["1", "150000"], ["0", "0"], ["2", "100,200"]]
    runner_rows = [ln for ln in lines if "SP-" in ln]
    assert [ln.split()[:2] for ln in runner_rows] == [["1", "168000"], ["0", "0"]]
    rep = json.loads(run_tree(main, "--runners", str(base), "--format", "json").stdout)
    assert [r["compactions"] for r in rep["rot"]["ticks"]] == [1, 0, 2] and len(rep["rot"]["runners"]) == 2
    assert run_tree(main, "--runners", str(tmp_path / "nowhere")).returncode == 2
    assert "by runner" not in run_tree(main).stdout  # without --runners the transcript's ticks only
