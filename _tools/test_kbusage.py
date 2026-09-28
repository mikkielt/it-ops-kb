"""Usage reader and query log usage sidecar tests (kb/_self/usage.md; `python3 _tools/tests.py -k kbusage`).
  TestReader        the fixture transcript (_tools/fixtures/kbusage/session.jsonl and its subagents/) gives each
                    prompt's exact record: one count per request id (the most output of its records), synthetic and
                    sidechain records of the main file left out, subagents by the prompt that started them and by
                    agent group, tool groups, steps with their growth (none after a shrink); no text of the transcript
                    reaches a record; a missing file or prompt gives None; the step cap; reading from the end in
                    small blocks gives the same record; the command line
  TestCapture       the Stop capture writes a `usage` row beside the `stop` row of a prompt that used the kb, with the
                    reader's version; no row for a prompt that did not, or when the transcript cannot be read
  TestSidecar       distill writes the usage sidecar beside the run file: one line per written entry with usage,
                    `missing` counting the rest, the store gates pass; a row of another reader version is left out;
                    a second distill writes nothing; delivery copies the sidecar with its run file
  TestUsageGates    the sidecar gates, each with a planted failure: header fields, a run id that names another file,
                    no run file beside it, a count that does not match, an entry the run file lacks, an id twice, an
                    unknown field (text), a model id, agent group or tool group outside its shape, a count that is
                    not a count, cw1h above cw, a step without tools
  TestDigest        the digest's usage lines from a store with a sidecar, the same in two copies; none without one
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


def hook(data, event):
    p = subprocess.run([sys.executable, QL, "capture"], input=json.dumps(event).encode("utf-8"), capture_output=True,
                       env=querylog_env(data), timeout=60)
    return p.returncode


def spool_rows(data):
    d = Path(data) / "querylog" / "spool"
    return [r for f in sorted(d.glob("*.jsonl")) for r in jsonl(f)] if d.is_dir() else []


class TestCapture:
    def events(self, pid, transcript, kb=True):
        out = [{"hook_event_name": "UserPromptSubmit", "session_id": SID, "prompt_id": pid, "prompt": "hello"}]
        if kb:
            out.append({"hook_event_name": "PostToolUse", "session_id": SID, "prompt_id": pid,
                        "tool_name": "mcp__kb__kb_pack", "tool_input": {"question": "laps"},
                        "tool_response": "coverage: good (x)\n## public/windows/laps.md\n- public/windows/laps.md:5 "
                                         "fact [DOC S1]"})
        out.append({"hook_event_name": "Stop", "session_id": SID, "prompt_id": pid, "transcript_path": transcript,
                    "last_assistant_message": "answer"})
        return out

    def test_usage_row_beside_stop(self, tmp_path):
        for e in self.events("p1", str(SESSION)):
            assert hook(tmp_path, e) == 0
        rows = spool_rows(tmp_path)
        assert [r["surface"] for r in rows] == ["prompt", "mcp", "stop", "usage"]
        u = rows[-1]
        assert u["usage"] == P1 and u["reader"] == kbusage.READER_VERSION and u["prompt_id"] == "p1"
        assert "PRIVATE-TEXT" not in json.dumps(u) and "transcript_path" not in u

    def test_no_row_without_kb_use(self, tmp_path):
        for e in self.events("p1", str(SESSION), kb=False):
            hook(tmp_path, e)
        assert [r["surface"] for r in spool_rows(tmp_path)] == ["prompt"]

    def test_unreadable_transcript(self, tmp_path):
        for e in self.events("p1", str(tmp_path / "missing.jsonl")):
            hook(tmp_path, e)
        assert [r["surface"] for r in spool_rows(tmp_path)] == ["prompt", "mcp", "stop"]


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
