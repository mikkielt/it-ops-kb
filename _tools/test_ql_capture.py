"""Query log tests, capture (kb/_self/querylog.md, Capture; `python3 _tools/tests.py -k TestHookRows`, and the other classes below).

  TestHookRows      the capture hook (`querylog.py capture`) with recorded hook events on stdin: one row per event
                    with a fresh UUID id; prompt, kb MCP, fetch and Stop rows; fetch rows keep host and path only,
                    Bash and PowerShell only for curl and wget, never command text or results; fetches and answers
                    only in a prompt that used the kb; the row size cap; stale spool files pruned
  TestWorkRows      a successful `backlog.py claim|done|release ID` in Bash or PowerShell writes one `work` row
                    {item, action} (and the subagent's `agent_id`), keyed like every hook row, never the command's
                    text; a failed claim, a dry run, another command and a mention in quoted text write none
                    (planted: the same command succeeding writes one); a `done` that exits 1 (PostToolUseFailure,
                    `Exit code 1` first) writes `refused`, item only, and an interrupt, a start failure or timeout, another
                    exit code and a failed claim or release write none (`-k work_refused`)
                    `usage_targets` picks the prompts that need a usage row: the kb's and every prompt of a work window
  TestOpsRows       `ql_capture.record("ops", event=..., ...)` writes one `ops` row of a closed event with its closed
                    keys and values (names, exit codes, counts, milliseconds, item ids, short shas, test file names,
                    closed reason classes) to the tools file, with no session (`-k ops_sidecar`); it writes none for an
                    event or a key outside the set, a free-text or mistyped value, a missing required key or a row
                    too long to stay whole (planted: the same fields in their closed shape write one; `-k
                    ops_sidecar_refuses_free_text`)
  TestAgentRows     a SubagentStart or SubagentStop event writes one `work` row {action agent-start|agent-stop, agent,
                    group, item} (`-k ops_agent_rows`): `agent` a salted short hash of the agent id (the salt a file in
                    the querylog directory, made once), never the id; `group` kbusage's closed class; `item` only from a
                    `work/<id>` branch at the event's directory, read from HEAD with no process; no output on stdout;
                    the `agent.run` ops event refuses a raw agent id and a free-text group (planted: the closed shapes
                    are written)
  TestSwitches      mode `off`, the DISABLED marker and an unreadable config file write nothing (planted: the same
                    events with the default mode write); where rows go in a clone and in a plugin host
  TestToolRows      kb_hook.py, kb_ask.py, fetch.py and census.py write their own rows; the kb: hook's answer is
                    unchanged
  TestNoHooks       every `claude -p` the pipeline starts carries --settings {"disableAllHooks": true} (planted: an
                    argument list without it, or with false), research's call included, and nothing is written
                    unless a hook or a tool runs; research's only MCP tools are the kb server's cached docs_search
                    and docs_fetch (planted: the direct docs servers), and a repeated search calls the docs server once
  TestHookConfig    the capture hooks are async on UserPromptSubmit, PostToolUse, PostToolUseFailure and Stop in
                    .claude/settings.json and the plugin, through kbpy, with matchers for the kb and fetch tools
                    (planted: a synchronous capture hook, a missing event); the shell form runs end to end; the
                    launcher runs on SessionEnd (synchronous) and SessionStart (async) in both files, and the digest
                    hook on SessionStart, synchronous with its timeout (planted: async, no timeout, missing)
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The helpers the classes share are in
ql_testkit.py.
"""
import datetime, json, os, re, subprocess, sys, time, uuid
from pathlib import Path

import pytest

import ql_base, ql_capture, ql_distill, ql_report, ql_research, ql_store
from conftest import KB, TOOLS, querylog_env
from ql_testkit import load, prompt, QL, serve, SH, SID, spool, stop, tool


def lines(data):
    """Every spool row under `data`, in file order per file."""
    out = []
    for f in sorted(spool(data).glob("*.jsonl")) if spool(data).is_dir() else []:
        with open(f, encoding="utf-8") as fh:
            out += [json.loads(line) for line in fh if line.strip()]
    return out


def raw(data):
    return b"".join(f.read_bytes() for f in spool(data).glob("*.jsonl")) if spool(data).is_dir() else b""


def hook(data, event, env=None):
    """Run the capture hook with one event on stdin; returns (exit code, stdout)."""
    p = subprocess.run([sys.executable, QL, "capture"], input=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                       capture_output=True, env=env or querylog_env(data), timeout=60)
    return p.returncode, p.stdout


PACK = ("coverage: good (best article matches 3 of 3 key words)\n\n## public/windows/laps.md  Windows LAPS\n"
        "- public/windows/laps.md:24 The default length is 14. [DOC S-jmzxsdjr]\n"
        "# Q2\ncoverage: weak (...)\n\n## public/intune/win32-apps.md  Win32 apps\n"
        "- public/intune/win32-apps.md:49 A rule. (no tag)\n  (+3 more matching lines in public/intune/win32-apps.md)\n")


def is_uuid4(s):
    return uuid.UUID(s).version == 4 and str(uuid.UUID(s)) == s


class TestHookRows:
    def test_prompt_rows_one_per_event(self, tmp_path):
        for i, text in enumerate(["kb: LAPS password length", "/kb-research hooks input", "hello there"]):
            assert hook(tmp_path, prompt(text, pid=f"p{i}")) == (0, b"")
        rows = lines(tmp_path)
        assert [r["surface"] for r in rows] == ["prompt"] * 3
        assert [r.get("kb_intent") for r in rows] == ["lookup", "skill", None]
        assert [r["prompt"] for r in rows][2] == "hello there" and rows[0]["prompt_id"] == "p0"
        assert len({r["id"] for r in rows}) == 3 and all(is_uuid4(r["id"]) for r in rows)
        assert all(r["session_id"] == SID for r in rows)
        assert all(r["v"] == ql_capture.ROW_FORMAT for r in rows)  # the row format distill branches on
        assert [f.name for f in spool(tmp_path).iterdir()] == [f"{SID}.jsonl"]
        datetime.datetime.fromisoformat(rows[0]["ts"].replace("Z", "+00:00"))

    def test_change_request_counts_as_kb_use(self, tmp_path):
        hook(tmp_path, prompt("please refresh the intune win32 apps topic"))
        assert lines(tmp_path)[0]["kb_intent"] == "change"

    def test_kb_mcp_row(self, tmp_path):
        resp = [{"type": "text", "text": PACK}]
        hook(tmp_path, tool("mcp__kb__kb_pack", {"questions": ["a", "b"], "budget": 900}, resp))
        hook(tmp_path, tool("mcp__plugin_it-ops-kb_kb__kb_show", {"path": "public/windows/laps.md:12"}, {"content": resp}))
        hook(tmp_path, tool("mcp__kb__kb_pack", {"question": "q"}, ok=False, error="server gone"))
        a, b, c = lines(tmp_path)
        assert (a["surface"], a["tool"], a["args"], a["verdict"], a["verdicts"]) == \
               ("mcp", "kb_pack", {"questions": ["a", "b"]}, "weak", ["good", "weak"])
        assert a["articles"] == ["public/windows/laps.md", "public/intune/win32-apps.md"] and a["prompt_id"] == "p1"
        assert a["lines"] == [{"line": "public/windows/laps.md:24", "tag": "DOC", "verdict": "good"},
                              {"line": "public/intune/win32-apps.md:49", "verdict": "weak"}]  # path:line, never text
        assert (b["tool"], b["args"], b["verdict"]) == ("kb_show", {"path": "public/windows/laps.md:12"}, "weak")
        assert (c["outcome"], "verdict" in c) == ("error", False)

    def test_decision_tag_line_keeps_its_tag(self, tmp_path):
        """A pack line that cites a decision records `DECISION` as its tag, with the path:line and never the text or
        the decision's id; a tag of no kind the kb has is left out (planted)."""
        pack = ("coverage: good (best article matches 3 of 3 key words)\n\n## public/print/queues.md  Print queues\n"
                "- public/print/queues.md:12 Finished jobs are kept 14 days. [DECISION D-k3f7q2zd: pilot]\n"
                "- public/print/queues.md:13 A made-up kind. [GUESS S100]\n")
        assert "DECISION" in ql_capture.TAGS
        hook(tmp_path, tool("mcp__kb__kb_pack", {"question": "q"}, [{"type": "text", "text": pack}]))
        (row,) = lines(tmp_path)
        assert row["lines"] == [{"line": "public/print/queues.md:12", "tag": "DECISION", "verdict": "good"},
                                {"line": "public/print/queues.md:13", "verdict": "good"}]
        assert b"D-k3f7q2zd" not in raw(tmp_path)

    def test_fetch_rows_keep_host_and_path_only(self, tmp_path):
        hook(tmp_path, prompt("kb: windows laps"))
        url = "https://jan:pw@Learn.Microsoft.com:443/en-us/windows/laps?view=secret-token#frag"
        hook(tmp_path, tool("WebFetch", {"url": url, "prompt": "extract the private detail"}, {"result": "text"}))
        hook(tmp_path, tool("mcp__microsoft-learn__microsoft_docs_fetch", {"url": "https://learn.microsoft.com/a?b=c"}, "t"))
        hook(tmp_path, tool("mcp__claude-code-docs__query_docs_filesystem_claude_code_docs", {"command": "cat /en/x.mdx"}, "t"))
        hook(tmp_path, tool("WebFetch", {"url": "https://example.org/gone"}, ok=False,
                            error="Request failed with status code 404"))
        rows = [r for r in lines(tmp_path) if r["surface"] == "fetch"]
        assert [(r["tool"], r.get("host"), r.get("path"), r["outcome"]) for r in rows] == [
            ("WebFetch", "learn.microsoft.com", "/en-us/windows/laps", "unknown"),
            ("mcp__microsoft-learn__microsoft_docs_fetch", "learn.microsoft.com", "/a", "unknown"),
            ("mcp__claude-code-docs__query_docs_filesystem_claude_code_docs", None, None, "unknown"),
            ("WebFetch", "example.org", "/gone", "http-404")]
        assert [r.get("chars") for r in rows] == [4, 1, 1, None]  # the result's characters; none for a failure
        text = raw(tmp_path).decode("utf-8")
        for secret in ("secret-token", "frag", "jan:pw", "view=", "private detail", "cat /en/x.mdx", ":443"):
            assert secret not in text, secret

    def test_fetch_outcome_classes(self, tmp_path):
        hook(tmp_path, prompt("kb: x"))
        hook(tmp_path, tool("WebFetch", {"url": "https://a.example.com/p"}, {"result": ""}))
        hook(tmp_path, tool("WebFetch", {"url": "https://a.example.com/p"}, {"code": 200, "result": "page"}))
        hook(tmp_path, tool("WebFetch", {"url": "https://a.example.com/p"},
                            {"result": "REDIRECT DETECTED: https://a.example.com/p redirects to https://b.example.net/q"}))
        hook(tmp_path, tool("WebFetch", {"url": "https://a.example.com/p"}, ok=False, error="timed out"))
        assert [r["outcome"] for r in lines(tmp_path) if r["surface"] == "fetch"] == \
               ["empty", "http-200", "redirect-cross-host", "error"]

    def test_shell_rows_only_for_curl_and_wget(self, tmp_path):
        hook(tmp_path, prompt("kb: x"))
        cmds = [("Bash", "curl -sL -H 'Authorization: Bearer abc123' 'https://raw.example.com/o/r/main/f.md?token=zz'"),
                ("Bash", "git status && ls -la https://not.fetched.example.com/"),
                ("Bash", "echo done"),
                ("PowerShell", "curl.exe -s https://ps.example.com/path/x.json"),
                ("Bash", "cd /tmp && /usr/bin/wget -q -O - http://w.example.com/a/b"),
                ("Bash", "curl -s \"$URL\"")]
        for name, cmd in cmds:
            hook(tmp_path, tool(name, {"command": cmd, "description": "d"}, {"stdout": "BODY-SECRET", "stderr": ""}))
        rows = [r for r in lines(tmp_path) if r["surface"] == "fetch"]
        assert [(r["tool"], r["fetcher"], r["host"], r["path"], r["outcome"]) for r in rows] == [
            ("Bash", "curl", "raw.example.com", "/o/r/main/f.md", "unknown"),
            ("PowerShell", "curl", "ps.example.com", "/path/x.json", "unknown"),
            ("Bash", "wget", "w.example.com", "/a/b", "unknown")]
        assert not any("chars" in r for r in rows)  # a shell command's output is never read, not even its length
        text = raw(tmp_path).decode("utf-8")
        for secret in ("Bearer", "abc123", "token=", "BODY-SECRET", "-sL", "git status", "wget -q"):
            assert secret not in text, secret

    def test_fetches_and_answers_only_beside_the_kb(self, tmp_path):
        hook(tmp_path, prompt("what is the weather", pid="plain"))
        hook(tmp_path, tool("WebFetch", {"url": "https://example.com/x"}, "t", pid="plain"))
        hook(tmp_path, tool("Bash", {"command": "curl https://example.com/y"}, {}, pid="plain"))
        hook(tmp_path, stop("It is sunny.", pid="plain"))
        assert [r["surface"] for r in lines(tmp_path)] == ["prompt"]
        hook(tmp_path, prompt("tell me about laps", pid="kb"))
        hook(tmp_path, tool("mcp__kb__kb_pack", {"question": "laps"}, PACK, pid="kb"))
        hook(tmp_path, tool("WebFetch", {"url": "https://example.com/x"}, "t", pid="kb"))
        hook(tmp_path, stop("The LAPS password is 14 characters.", pid="kb"))
        rows = lines(tmp_path)
        assert [r["surface"] for r in rows] == ["prompt", "prompt", "mcp", "fetch", "stop"]
        assert rows[-1]["answer"] == "The LAPS password is 14 characters." and rows[-1]["prompt_id"] == "kb"

    def test_tool_rows_in_the_prompt_window_count_as_kb_use(self, tmp_path):
        env = querylog_env(tmp_path)
        hook(tmp_path, prompt("run the ask tool", pid="w"))
        p = subprocess.run([sys.executable, "-c", "import ql_capture; ql_capture.record('kb_ask', question='q', route='plan')"],
                           cwd=TOOLS, env=env, capture_output=True, timeout=60)
        assert p.returncode == 0, p.stderr
        hook(tmp_path, stop("answer", pid="w"))
        assert [r["surface"] for r in lines(tmp_path)] == ["prompt", "stop", "kb_ask"]  # the session file sorts first

    def test_row_size_cap_and_utf8(self, tmp_path):
        hook(tmp_path, prompt("kb: " + "Łódź ☃ \"quoted\" " * 20000))
        data = raw(tmp_path)
        assert b"\r" not in data and data.endswith(b"\n")
        line = data.decode("utf-8").rstrip("\n")
        assert len(line) <= ql_capture.SPOOL_ROW_MAX_CHARS and "Łódź ☃" in line
        assert json.loads(line)["prompt"].endswith(ql_capture.CUT)

    def test_unsafe_session_id_goes_to_the_tools_file(self, tmp_path):
        hook(tmp_path, prompt("hi", sid="../../escape"))
        assert [f.name.startswith("tools-") for f in spool(tmp_path).iterdir()] == [True]
        assert not (tmp_path / "escape.jsonl").exists()

    def test_stale_spool_files_are_pruned(self, tmp_path):
        spool(tmp_path).mkdir(parents=True)
        old, new = spool(tmp_path) / "old.jsonl", spool(tmp_path) / "new.jsonl"
        for f in (old, new):
            f.write_text("{}\n", encoding="utf-8", newline="\n")
        t = time.time() - (ql_capture.SPOOL_MAX_AGE_DAYS + 1) * 86400
        os.utime(old, (t, t))
        hook(tmp_path, prompt("hi"))
        assert not old.exists() and new.exists()

    def test_bad_input_never_fails(self, tmp_path):
        for payload in (b"", b"not json", b"[1,2]", b'{"hook_event_name": "PostToolUse", "tool_input": "x"}'):
            p = subprocess.run([sys.executable, QL, "capture"], input=payload, capture_output=True,
                               env=querylog_env(tmp_path), timeout=60)
            assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"")
        assert lines(tmp_path) == []


CLAIM = "python3 _tools/backlog.py claim TK-aaaaaaaa --by worker-aaaaaaaa --commit --trailer 'Co-Authored-By: Claude <noreply@example.com>'"


class TestWorkRows:
    """A successful `backlog.py claim|done|release ID` run through Bash or PowerShell writes one `work` row
    {item, action}, keyed like every hook row; the command's text and output never reach it."""

    def test_work_row_for_claim_done_and_release(self, tmp_path):
        cmds = [("Bash", CLAIM),
                ("Bash", "python3 _tools/backlog.py done TK-aaaaaaaa --commit --trailer 'Co-Authored-By: Claude <x>'"),
                ("Bash", "python3 _tools/backlog.py release ST-bbbbbbbb"),
                ("PowerShell", "python3 .\\_tools\\backlog.py claim BG-cccccccc --by worker-cccccccc"),
                ("PowerShell", "& \"C:\\Program Files\\Python311\\python.exe\" .\\_tools\\backlog.py done SB-dddddddd --commit")]
        for n, (name, cmd) in enumerate(cmds):
            assert hook(tmp_path, tool(name, {"command": cmd}, {"stdout": "OUTPUT-SECRET", "stderr": ""},
                                       pid=f"p{n}")) == (0, b"")
        rows = lines(tmp_path)
        assert [(r["surface"], r["item"], r["action"], r["prompt_id"]) for r in rows] == [
            ("work", "TK-aaaaaaaa", "claim", "p0"), ("work", "TK-aaaaaaaa", "done", "p1"),
            ("work", "ST-bbbbbbbb", "release", "p2"), ("work", "BG-cccccccc", "claim", "p3"),
            ("work", "SB-dddddddd", "done", "p4")]
        assert all(r["session_id"] == SID and r["v"] == ql_capture.ROW_FORMAT and is_uuid4(r["id"]) for r in rows)
        assert len({r["id"] for r in rows}) == 5 and not any("agent_id" in r for r in rows)
        assert [f.name for f in spool(tmp_path).iterdir()] == [f"{SID}.jsonl"]  # keyed like every hook row
        text = raw(tmp_path).decode("utf-8")
        for secret in ("OUTPUT-SECRET", "worker-", "--by", "--commit", "Co-Authored", "backlog.py", "python"):
            assert secret not in text, secret  # no command text, flag value or result

    def test_work_row_keeps_the_subagent_id_when_present(self, tmp_path):
        ev = tool("Bash", {"command": CLAIM}, {"stdout": ""})
        hook(tmp_path, ev)
        hook(tmp_path, dict(ev, agent_id="agent-0000000000000001", agent_type="kb-worker"))
        hook(tmp_path, dict(ev, agent_id=7))  # not a string: left out
        a, b, c = lines(tmp_path)
        assert "agent_id" not in a and b["agent_id"] == "agent-0000000000000001" and "agent_id" not in c
        assert "kb-worker" not in raw(tmp_path).decode("utf-8")

    def test_work_row_failed_run_writes_none(self, tmp_path):
        """PostToolUse fires only after a successful call, a non-zero exit fires PostToolUseFailure
        (claude/hooks.md): a refused claim writes none (a refused done writes `refused`, below). Planted: the same
        command succeeding writes one."""
        for name in ("Bash", "PowerShell"):
            hook(tmp_path, tool(name, {"command": CLAIM}, ok=False, error="Exit code 1\nrefused: already claimed"))
        assert lines(tmp_path) == []
        hook(tmp_path, tool("Bash", {"command": CLAIM}, {"stdout": "claimed"}))
        assert [r["surface"] for r in lines(tmp_path)] == ["work"]

    def test_work_row_non_backlog_command_writes_none(self, tmp_path):
        cmds = ["echo done", "git status", "python3 _tools/backlog.py show TK-aaaaaaaa",
                "python3 _tools/backlog.py next --any", "python3 _tools/backlog.py done TK-aaaaaaaa --dry-run",
                "python3 _tools/backlog.py claim --help", "python3 _tools/backlog.py claim",
                "python3 _tools/backlog.py claim not-an-id --by x", "python3 _tools/other.py claim TK-aaaaaaaa",
                "python3 _tools/backlog.py land TK-aaaaaaaa", "python3 _tools/backlog.py new task --title claim",
                "git commit -m 'run backlog.py claim TK-aaaaaaaa; then done'",
                "echo \"python3 _tools/backlog.py done TK-aaaaaaaa\"",
                "grep -n 'backlog.py done TK-aaaaaaaa' kb/_self/backlog.md",
                "cat _tools/backlog.py claim TK-aaaaaaaa", "python3 -c \"print('backlog.py done TK-aaaaaaaa')\""]
        for name in ("Bash", "PowerShell"):
            for n, cmd in enumerate(cmds):
                assert hook(tmp_path, tool(name, {"command": cmd}, {"stdout": ""}, pid=f"p{n}")) == (0, b"")
        for ev in (tool("Bash", {}, {}), tool("Bash", {"command": 7}, {}),
                   tool("Read", {"command": CLAIM}, {}), tool("mcp__kb__kb_pack", {"command": CLAIM}, "")):
            hook(tmp_path, ev)
        assert [r for r in lines(tmp_path) if r["surface"] == "work"] == []

    @pytest.mark.parametrize("command,expected", [
        ("python3 _tools/backlog.py claim TK-aaaaaaaa", ("TK-aaaaaaaa", "claim")),
        ("cd /repo && python3 _tools/backlog.py done TK-aaaaaaaa --commit", ("TK-aaaaaaaa", "done")),
        ("python3 _tools/backlog.py done TK-aaaaaaaa --commit 2>&1", ("TK-aaaaaaaa", "done")),
        ("python3 _tools/backlog.py done TK-aaaaaaaa &> /dev/null", ("TK-aaaaaaaa", "done")),
        ("python3 _tools/backlog.py done TK-aaaaaaaa --commit 2>&1 | tail -3", None),  # a pipe: the last exit code
        ("python3 _tools/backlog.py done TK-aaaaaaaa | tail -3", None),
        ("python3 _tools/backlog.py done TK-aaaaaaaa | tee out.txt", None),
        ("python3 _tools/backlog.py done TK-aaaaaaaa |& tee out.txt", None),
        ("python3 _tools/backlog.py done TK-aaaaaaaa || echo refused", None),
        ("python3 _tools/backlog.py claim TK-aaaaaaaa | tail -3", None),
        ("cd /repo && python3 _tools/backlog.py done TK-aaaaaaaa 2>&1 | tail -3", None),
        ("python3 _tools/backlog.py done TK-aaaaaaaa > out.txt", ("TK-aaaaaaaa", "done")),
        ("python3 _tools/backlog.py done TK-aaaaaaaa && echo ok | tail -1", ("TK-aaaaaaaa", "done")),
        ("echo 'x | y' | python3 _tools/backlog.py done TK-aaaaaaaa", ("TK-aaaaaaaa", "done")),
        ("python3 _tools/backlog.py done TK-aaaaaaaa --trailer 'Note: a | b'", ("TK-aaaaaaaa", "done")),
        ("python3 /home/jan.kowalski/it-ops-kb/_tools/backlog.py release EP-eeeeeeee", ("EP-eeeeeeee", "release")),
        ("python3 _tools/backlog.py --root /repo claim TK-aaaaaaaa", ("TK-aaaaaaaa", "claim")),
        ("python3 _tools/backlog.py claim --by worker-x TK-aaaaaaaa", ("TK-aaaaaaaa", "claim")),
        ("python3 _tools/backlog.py claim --by=worker-x TK-aaaaaaaa", ("TK-aaaaaaaa", "claim")),
        ("py -3 _tools\\backlog.py done SP-ffffffff", ("SP-ffffffff", "done")),
        ("sh _tools/kbpy _tools/backlog.py claim TK-aaaaaaaa", ("TK-aaaaaaaa", "claim")),
        ("KB_X=1 python _tools/backlog.py claim TK-aaaaaaaa", ("TK-aaaaaaaa", "claim")),
        ("/usr/bin/python3.12 -B _tools/backlog.py claim TK-aaaaaaaa", ("TK-aaaaaaaa", "claim")),
        ("& 'C:\\Python311\\python.exe' '.\\_tools\\backlog.py' done TK-aaaaaaaa", ("TK-aaaaaaaa", "done")),
        ("python3 _tools/backlog.py show TK-aaaaaaaa; python3 _tools/backlog.py done TK-bbbbbbbb", ("TK-bbbbbbbb", "done")),
        ("python3 _tools/backlog.py claim TK-aaaaaaaa; python3 _tools/backlog.py claim TK-bbbbbbbb", ("TK-aaaaaaaa", "claim")),
        ("python3 _tools/backlog.py claim TK-AAAAAAAA", None),  # an id has lower-case base32 characters
        ("python3 _tools/backlog.py done TK-aaaaaaaa --dry-run", None),
        ("python3 _tools/backlog.py land TK-aaaaaaaa", None),
        ("pip install backlog.py claim TK-aaaaaaaa", None),
        ("", None)])
    def test_work_row_command_forms(self, command, expected):
        assert ql_capture.work_action(command) == expected

    def test_work_row_documented_events(self, tmp_path):
        """The hook events of `fixtures/querylog/work_events.json` (the documented shapes: Bash, PowerShell, a
        subagent's call, a failure, a dry run) write the row each lists, or none."""
        events = load("_tools/fixtures/querylog/work_events.json")["events"]
        assert len(events) >= 6 and any(e["row"] is None for e in events) and any(e["row"] for e in events)
        for n, e in enumerate(events):
            assert hook(tmp_path / str(n), e["event"]) == (0, b""), e["name"]
            (row,) = lines(tmp_path / str(n)) or [None]
            got = None if row is None else {k: row[k] for k in ("item", "action", "agent_id") if k in row}
            assert got == e["row"], e["name"]
            if row:
                assert (row["surface"], row["session_id"], row["prompt_id"]) == \
                       ("work", e["event"]["session_id"], e["event"]["prompt_id"])

    def test_work_refused_done_writes_a_row(self, tmp_path):
        """A `backlog.py done ID` that exits 1 fires PostToolUseFailure with `Exit code 1` first: one `work` row
        `refused`, item only, keyed like every hook row, the error text and the command's flags never kept.
        Planted: the same command succeeding writes `done`, not `refused`."""
        err = "Exit code 1\nTK-aaaaaaaa is not done:\n  ERROR-SECRET uncommitted changes in scope"
        cmd = "python3 _tools/backlog.py done TK-aaaaaaaa --commit --trailer 'Co-Authored-By: Claude <x>'"
        for n, name in enumerate(("Bash", "PowerShell")):
            assert hook(tmp_path, tool(name, {"command": cmd}, ok=False, error=err, pid=f"p{n}")) == (0, b"")
        hook(tmp_path, dict(tool("Bash", {"command": cmd}, ok=False, error=err, pid="p2"),
                            agent_id="agent-0000000000000001"))
        a, b, c = lines(tmp_path)
        assert [(r["surface"], r["item"], r["action"], r["prompt_id"]) for r in (a, b, c)] == [
            ("work", "TK-aaaaaaaa", "refused", "p0"), ("work", "TK-aaaaaaaa", "refused", "p1"),
            ("work", "TK-aaaaaaaa", "refused", "p2")]
        assert all(r["session_id"] == SID and r["v"] == ql_capture.ROW_FORMAT and is_uuid4(r["id"]) for r in (a, b, c))
        assert "agent_id" not in a and c["agent_id"] == "agent-0000000000000001"
        assert [f.name for f in spool(tmp_path).iterdir()] == [f"{SID}.jsonl"]
        assert set(a) == {"id", "ts", "surface", "v", "session_id", "prompt_id", "item", "action"}
        text = raw(tmp_path).decode("utf-8")
        for secret in ("ERROR-SECRET", "Exit code", "is not done", "--commit", "Co-Authored", "backlog.py", "python"):
            assert secret not in text, secret  # no error text, command text or flag
        ok = tmp_path / "ok"
        hook(ok, tool("Bash", {"command": cmd}, {"stdout": "done"}))
        assert [r["action"] for r in lines(ok)] == ["done"]

    def test_work_refused_a_successful_done_still_writes_done(self, tmp_path):
        hook(tmp_path, tool("Bash", {"command": "python3 _tools/backlog.py done TK-aaaaaaaa"}, {"stdout": "done"}))
        (row,) = lines(tmp_path)
        assert (row["surface"], row["item"], row["action"]) == ("work", "TK-aaaaaaaa", "done")

    def test_work_row_piped_done_writes_none(self, tmp_path):
        """A pipeline's exit code is its last command's: `done ID | tail` exits 0 whether `done` was refused or not
        (a success event) and `done ID | false` exits 1 whatever `done` did (a failure event). Neither writes a
        row. Planted: the same `done` run alone writes `done` on success and `refused` on `Exit code 1`."""
        for n, tail in enumerate(("| tail -3", "2>&1 | tee out.txt", "|& tail", "|| echo no")):
            cmd = f"python3 _tools/backlog.py done TK-aaaaaaaa {tail}"
            hook(tmp_path, tool("Bash", {"command": cmd}, {"stdout": "x"}, pid=f"s{n}"))
            hook(tmp_path, tool("Bash", {"command": cmd}, ok=False, error="Exit code 1\nx", pid=f"f{n}"))
        assert lines(tmp_path) == []
        alone = "python3 _tools/backlog.py done TK-aaaaaaaa"
        hook(tmp_path, tool("Bash", {"command": alone}, {"stdout": "x"}, pid="a"))
        hook(tmp_path, tool("Bash", {"command": alone}, ok=False, error="Exit code 1\nx", pid="b"))
        assert [r["action"] for r in lines(tmp_path)] == ["done", "refused"]

    def test_work_refused_a_failed_claim_or_release_writes_none(self, tmp_path):
        """Only a done is a refusal worth a row. Planted: the same `Exit code 1` on a done writes one."""
        for n, cmd in enumerate(("python3 _tools/backlog.py claim TK-aaaaaaaa --by worker-x",
                                 "python3 _tools/backlog.py release TK-aaaaaaaa",
                                 "python3 _tools/backlog.py land TK-aaaaaaaa",
                                 "python3 _tools/backlog.py show TK-aaaaaaaa")):
            hook(tmp_path, tool("Bash", {"command": cmd}, ok=False, error="Exit code 1\nrefused", pid=f"p{n}"))
        assert lines(tmp_path) == []
        hook(tmp_path, tool("Bash", {"command": "python3 _tools/backlog.py done TK-aaaaaaaa"}, ok=False,
                            error="Exit code 1\nrefused"))
        assert [r["action"] for r in lines(tmp_path)] == ["refused"]

    def test_work_refused_interrupt_writes_none(self, tmp_path):
        """A done the user interrupted is no refusal, though its error may still begin `Exit code 1`. Planted: the
        same event with `is_interrupt` false writes one."""
        ev = tool("Bash", {"command": "python3 _tools/backlog.py done TK-aaaaaaaa"}, ok=False, error="Exit code 1\n")
        for flag in (True, 1, "yes"):
            hook(tmp_path, dict(ev, is_interrupt=flag))
        assert lines(tmp_path) == []
        hook(tmp_path, dict(ev, is_interrupt=False))
        assert [r["action"] for r in lines(tmp_path)] == ["refused"]

    @pytest.mark.parametrize("error", [
        "Command timed out after 2m 0s", "spawn /bin/sh ENOENT", "", "Exit code 0\nrefused", "Exit code 2\nusage: x",
        "Exit code 127\nsh: python3: command not found", "Exit code 9009", "Exit code\nrefused", "exit code 1",
        "Command timed out after 2m 0s\nExit code 1", "Exit code 10\nrefused", "Exit code -1"])
    def test_work_refused_needs_an_exit_code_one_first_line(self, tmp_path, error):
        """A start failure or timeout with no exit-code first line, another exit code and an exit line anywhere but
        first write none. Planted: `Exit code 1` first writes one."""
        cmd = {"command": "python3 _tools/backlog.py done TK-aaaaaaaa"}
        hook(tmp_path, tool("Bash", cmd, ok=False, error=error))
        assert lines(tmp_path) == []
        hook(tmp_path, tool("Bash", cmd, ok=False, error="Exit code 1\n" + error))
        assert [r["action"] for r in lines(tmp_path)] == ["refused"]

    def test_work_refused_a_mention_of_the_script_writes_none(self, tmp_path):
        """The parser of the success path decides which commands are a `backlog.py done`: a failed command that
        only mentions it, a dry run or a done with no id writes none. Planted: the plain command writes one."""
        cmds = ["grep -n 'backlog.py done TK-aaaaaaaa' missing.md", "echo \"backlog.py done TK-aaaaaaaa\" && false",
                "git commit -m 'run backlog.py done TK-aaaaaaaa'", "python3 _tools/backlog.py done TK-aaaaaaaa --dry-run",
                "python3 _tools/backlog.py done", "python3 _tools/backlog.py done not-an-id",
                "python3 _tools/other.py done TK-aaaaaaaa", "python3 -c \"print('backlog.py done TK-aaaaaaaa')\""]
        for n, cmd in enumerate(cmds):
            hook(tmp_path, tool("Bash", {"command": cmd}, ok=False, error="Exit code 1\nx", pid=f"p{n}"))
        for ev in (tool("Bash", {}, ok=False, error="Exit code 1"), tool("Bash", {"command": 7}, ok=False, error="Exit code 1"),
                   tool("Read", {"command": "python3 _tools/backlog.py done TK-aaaaaaaa"}, ok=False, error="Exit code 1"),
                   dict(tool("Bash", {"command": cmds[0]}, ok=False), error=None)):
            hook(tmp_path, ev)
        assert lines(tmp_path) == []
        hook(tmp_path, tool("Bash", {"command": "python3 _tools/backlog.py done TK-aaaaaaaa"}, ok=False,
                            error="Exit code 1\nx"))
        assert [r["action"] for r in lines(tmp_path)] == ["refused"]

    def test_work_refused_documented_events(self):
        """The fixture's `PostToolUseFailure` events (written by hand from the documented shape) cover a refused done
        and each case that writes none, and are run by test_work_row_documented_events."""
        fails = [e for e in load("_tools/fixtures/querylog/work_events.json")["events"]
                 if e["event"]["hook_event_name"] == "PostToolUseFailure"]
        assert sum(1 for e in fails if e["row"] and e["row"]["action"] == "refused") >= 3
        assert sum(1 for e in fails if e["row"] is None) >= 5 and any(e["event"]["is_interrupt"] for e in fails)

    def test_work_refused_off_writes_nothing(self, tmp_path):
        d = Path(tmp_path) / "querylog"
        d.mkdir()
        (d / "config.json").write_text('{"mode": "off"}', encoding="utf-8", newline="\n")
        assert hook(tmp_path, tool("Bash", {"command": "python3 _tools/backlog.py done TK-aaaaaaaa"}, ok=False,
                                   error="Exit code 1\nx")) == (0, b"")
        assert lines(tmp_path) == [] and not spool(tmp_path).exists()

    def test_work_refused_keeps_the_window_open(self):
        """A `refused` row neither opens a window nor closes one: the item is not done. Planted: a `done` row of the
        same prompt closes it, so the later prompt is no target."""
        def plan(action):
            return [{"surface": "prompt", "prompt_id": "p0"},
                    {"surface": "work", "prompt_id": "p0", "item": "TK-aaaaaaaa", "action": "claim"},
                    {"surface": "prompt", "prompt_id": "p1"},
                    {"surface": "work", "prompt_id": "p1", "item": "TK-aaaaaaaa", "action": action},
                    {"surface": "prompt", "prompt_id": "p2"}]
        assert ql_capture.usage_targets(plan("refused"))[0] == ["p0", "p1", "p2"]
        assert ql_capture.usage_targets(plan("done"))[0] == ["p0", "p1"]
        assert ql_capture.usage_targets([{"surface": "prompt", "prompt_id": "p0"},
                                         {"surface": "work", "prompt_id": "p0", "item": "TK-aaaaaaaa",
                                          "action": "refused"}])[0] == []

    def test_work_row_off_writes_nothing(self, tmp_path):
        d = Path(tmp_path) / "querylog"
        d.mkdir()
        (d / "config.json").write_text('{"mode": "off"}', encoding="utf-8", newline="\n")
        assert hook(tmp_path, tool("Bash", {"command": CLAIM}, {"stdout": ""})) == (0, b"")
        assert lines(tmp_path) == [] and not spool(tmp_path).exists()


    @pytest.mark.parametrize("plan,skip,want", [
        ([("p0", "prompt"), ("p1", "prompt")], None, []),
        ([("p0", "kb"), ("p1", "prompt")], None, ["p0"]),
        ([("p0", "claim"), ("p1", "prompt"), ("p2", "done"), ("p3", "prompt")], None, ["p0", "p1", "p2"]),
        ([("p0", "prompt"), ("p1", "claim"), ("p2", "prompt")], None, ["p1", "p2"]),  # open: runs to the end
        ([("p0", "claim"), ("p1", "prompt"), ("p2", "prompt")], "p2", ["p0", "p1"]),
        ([("p0", "done"), ("p1", "prompt")], None, []),  # no claim in these rows: no window
        ([("p0", "claim"), ("p1", "release"), ("p2", "kb"), ("p3", "prompt")], None, ["p0", "p1", "p2"])])
    def test_work_usage_targets(self, plan, skip, want):
        """Which prompts of a spool file need a usage row (planted: a done with no claim opens nothing, a prompt
        after the window closes is a target only when it used the kb)."""
        rs = []
        for pid, kind in plan:
            rs.append({"surface": "prompt", "prompt_id": pid})
            if kind == "kb":
                rs.append({"surface": "mcp", "prompt_id": pid})
            elif kind != "prompt":
                rs.append({"surface": "work", "prompt_id": pid, "item": "TK-aaaaaaaa", "action": kind})
        rs.append({"surface": "usage", "prompt_id": "p9", "reader": 1})
        assert ql_capture.usage_targets(rs, skip) == (want, {("p9", 1)})


LAND_STEP = {"event": "land.step", "item": "ST-aaaaaaaa", "step": "rebase", "exit": 0, "ms": 1234}


class TestOpsRows:
    @pytest.fixture(autouse=True)
    def spool_here(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ql_capture, "spool_dir", lambda: tmp_path / "spool")
        self.spool = tmp_path / "spool"

    def rows(self):
        return [json.loads(ln) for f in sorted(self.spool.glob("*.jsonl")) for ln in f.read_text(encoding="utf-8").splitlines()]

    def test_ops_sidecar_a_closed_event_is_one_row_in_the_tools_file(self):
        row = ql_capture.record("ops", **LAND_STEP)
        (got,) = self.rows()
        assert got == row and got["surface"] == "ops" and got["v"] == ql_capture.ROW_FORMAT and is_uuid4(got["id"])
        assert {k: got[k] for k in LAND_STEP} == LAND_STEP and "session_id" not in got
        assert [f.name for f in self.spool.iterdir()] == [f"tools-{got['ts'][:10]}.jsonl"]

    def test_ops_sidecar_a_session_never_reaches_the_row(self):
        row = ql_capture.record("ops", SID, **LAND_STEP)
        assert row is not None and "session_id" not in row
        assert [f.name.startswith("tools-") for f in self.spool.iterdir()] == [True]

    @pytest.mark.parametrize("fields", [
        {"event": "land.step", "item": "ST-aaaaaaaa", "step": "rebase", "exit": 0, "ms": 5,
         "list": [1, 2]},  # a key land.step has not
        {"event": "land.step", "item": "ST-aaaaaaaa", "step": "rebase", "exit": 0},  # a required key missing
        {"event": "no.such.event", "ms": 5},
        {"item": "ST-aaaaaaaa", "ms": 5},  # no event at all
        {**LAND_STEP, "ms": True},  # a flag is no count
        {**LAND_STEP, "ms": -1},
        {**LAND_STEP, "ms": 1.5},
        {**LAND_STEP, "exit": "0"},
        {**LAND_STEP, "item": "ST-AAAAAAAA"},
        {"event": "ci.pipeline", "state": "failed", "calls": 3, "sha": "not-a-sha"},
        {"event": "done.refused", "item": "ST-aaaaaaaa", "ms": 5, "reasons": ["a reason of my own"]},
        {"event": "test.run", "mode": "fast", "ms": 1, "exit": 0, "slow": [{"file": "tests/test_x.py", "ms": 3}]},
        {"event": "test.run", "mode": "fast", "ms": 1, "exit": 0, "failed_files": ["test_x.py::test_node"]},
        {"event": "test.run", "mode": "fast", "ms": 1, "exit": 0, "slow": [{"file": "test_x.py", "ms": 3, "n": 1}]},
        {"event": "test.run", "mode": "turbo", "ms": 1, "exit": 0},
    ])
    def test_ops_sidecar_refuses_free_text_and_shapes_outside_the_closed_set(self, fields):
        assert ql_capture.record("ops", **fields) is None and not self.spool.exists()

    @pytest.mark.parametrize("step", ["fix the rebase and try again", "Rebase", "../../etc/passwd", "a" * 41, "1step",
                                      "step\nstep", ""])
    def test_ops_sidecar_refuses_free_text_in_a_name(self, step):
        assert ql_capture.record("ops", **{**LAND_STEP, "step": step}) is None and not self.spool.exists()

    def test_ops_sidecar_the_same_fields_in_their_closed_shape_are_written(self):
        """planted counterpart of the refusals above: each closed shape is one row."""
        rows = [{"event": "sync.gate", "ms": 90, "scope": "changed", "files": 4, "push": "pushed", "exit": 0,
                 "checks": [{"name": "check", "ran": True, "exit": 0, "ms": 5},
                            {"name": "fetch", "ran": False, "why": "no-pinned-change"}]},
                {"event": "done.refused", "item": "ST-aaaaaaaa", "ms": 7, "reasons": ["check-failed", "status"],
                 "checks": ["tests-ops-sidecar"]},
                {"event": "test.run", "mode": "full", "ms": 3 * 10 ** 6, "exit": 3221225786,
                 "slow": [{"file": "test_ql_store.py", "ms": 900}], "failed_files": ["test_ql_store.py"]},
                {"event": "ci.pipeline", "state": "failed", "calls": 3, "sha": "0123abc"},
                {"event": "agent.run", "group": "kb-worker", "ms": 5, "agent": "0123456789abcdef", "item": "ST-aaaaaaaa"},
                {"event": "intake.detect", "detector": "drift", "found": 2, "budget": False},
                {"event": "stall.remedy", "item": "ST-aaaaaaaa", "signal": "claim-no-commit", "remedy": "retry-narrower",
                 "count": 1}]
        for r in rows:
            assert ql_capture.record("ops", **r) is not None, r
        assert [{k: v for k, v in r.items() if k in rows[i]} for i, r in enumerate(self.rows())] == rows

    def test_ops_sidecar_a_row_too_long_to_stay_whole_is_not_written(self):
        names = [f"test_{'a' * 50}_{i}.py" for i in range(300)]
        files = [{"file": n, "ms": 10 ** 9} for n in names]
        assert len(json.dumps(files)) + len(json.dumps(names)) > ql_capture.OPS_ROW_MAX_CHARS
        assert ql_capture.record("ops", event="test.run", mode="full", ms=1, exit=0, files=files,
                                 failed_files=names) is None
        assert not self.spool.exists()

    def test_ops_sidecar_is_cut_by_nothing_the_spool_row_cap_applies_to(self):
        """a row over the spool's usual cap, within its own, is written whole"""
        files = [{"file": f"test_x{i}.py", "ms": 1234567} for i in range(300)]
        row = ql_capture.record("ops", event="test.run", mode="full", ms=1, exit=0, files=files)
        assert len(json.dumps(row)) > ql_capture.SPOOL_ROW_MAX_CHARS and self.rows()[0]["files"] == files
        assert "cut" not in self.rows()[0]

    def test_ops_sidecar_off_writes_nothing(self, monkeypatch):
        monkeypatch.setattr(ql_capture, "spool_dir", lambda: None)
        assert ql_capture.record("ops", **LAND_STEP) is None and not self.spool.exists()


RAW_AGENT = "agent-0123456789abcdef0"


def agent_event(kind, sid=SID, agent=RAW_AGENT, agent_type="kb-worker", cwd=None):
    ev = {"hook_event_name": kind, "session_id": sid, "agent_id": agent, "agent_type": agent_type}
    if cwd is not None:
        ev["cwd"] = str(cwd)
    return ev


def branch_dir(tmp_path, branch, worktree=False):
    """A directory whose repository's HEAD is on `branch` (a file read, no git): a plain checkout, or a worktree
    whose `.git` file names its own git directory."""
    repo = tmp_path / ("wt" if worktree else "repo")
    git_dir = tmp_path / "gitdirs" / "wt" if worktree else repo / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    if worktree:
        (repo / "sub").mkdir(parents=True)
        (repo / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    return repo


class TestAgentRows:
    def test_ops_agent_rows_start_and_stop_are_work_rows_with_a_hashed_agent(self, tmp_path):
        repo = branch_dir(tmp_path, "work/ST-lopowpsz")
        assert hook(tmp_path, agent_event("SubagentStart", cwd=repo)) == (0, b"")
        assert hook(tmp_path, agent_event("SubagentStop", agent_type="it-ops-kb:kb-worker", cwd=repo)) == (0, b"")
        a, b = lines(tmp_path)
        assert (a["surface"], a["action"], a["group"], a["item"], a["session_id"]) == (
            "work", "agent-start", "kb-worker", "ST-lopowpsz", SID)
        assert (b["action"], b["group"], b["item"]) == ("agent-stop", "kb-worker", "ST-lopowpsz")
        assert a["agent"] == b["agent"] and ql_capture.OPS_KINDS["agent"](a["agent"])
        assert "prompt_id" not in a and is_uuid4(a["id"]) and a["id"] != b["id"]
        text = raw(tmp_path).decode("utf-8")
        for secret in (RAW_AGENT, "agent-0123", str(repo), "refs/heads", "work/ST"):
            assert secret not in text, secret
        salt = (tmp_path / "querylog" / ql_capture.AGENT_SALT_NAME).read_text(encoding="utf-8").strip()
        assert len(salt) >= 32 and salt not in text

    def test_ops_agent_rows_the_hash_is_salted_and_stable(self, tmp_path):
        hook(tmp_path, agent_event("SubagentStart"))
        hook(tmp_path, agent_event("SubagentStart", agent="agent-other"))
        other = tmp_path / "other"
        hook(other, agent_event("SubagentStart"))
        a, b = lines(tmp_path)
        (c,) = lines(other)
        assert a["agent"] != b["agent"] and a["agent"] != c["agent"]  # another id, and another salt
        hook(tmp_path, agent_event("SubagentStop"))
        assert lines(tmp_path)[-1]["agent"] == a["agent"]  # the same id under the same salt

    @pytest.mark.parametrize("agent_type,group", [
        ("kb-worker", "kb-worker"), ("it-ops-kb:kb-worker", "kb-worker"), ("general-purpose", "general-purpose"),
        ("Explore", "explore"), ("my free text type", "other"), (None, "other"), ("", "other")])
    def test_ops_agent_rows_group_is_a_closed_class(self, tmp_path, agent_type, group):
        hook(tmp_path, agent_event("SubagentStart", agent_type=agent_type))
        (row,) = lines(tmp_path)
        assert row["group"] == group and ql_capture.OPS_KINDS["token"](row["group"])
        assert "my free text type" not in raw(tmp_path).decode("utf-8")

    def test_ops_agent_rows_item_only_from_a_work_branch(self, tmp_path):
        plain = tmp_path / "plain"
        for n, (branch, worktree) in enumerate([("main", False), ("work/not-an-item", False),
                                                ("work/ST-lopowpsz-extra", False), ("feature/ST-lopowpsz", False)]):
            hook(tmp_path, agent_event("SubagentStart", cwd=branch_dir(tmp_path / str(n), branch, worktree)))
        hook(tmp_path, agent_event("SubagentStart", cwd=plain))  # no repository
        hook(tmp_path, agent_event("SubagentStart", cwd="relative/dir"))
        hook(tmp_path, agent_event("SubagentStart"))
        assert all("item" not in r for r in lines(tmp_path)) and len(lines(tmp_path)) == 7
        # planted counterpart: a work branch, in a worktree and from a subdirectory of it, gives its item
        wt = branch_dir(tmp_path / "w", "work/BG-6eehkrei", worktree=True)
        hook(tmp_path, agent_event("SubagentStop", cwd=wt / "sub"))
        assert lines(tmp_path)[-1]["item"] == "BG-6eehkrei"

    @pytest.mark.parametrize("ev", [{"hook_event_name": "SubagentStart", "session_id": SID},
                                    {"hook_event_name": "SubagentStop", "session_id": SID, "agent_id": 7},
                                    {"hook_event_name": "SubagentStop", "session_id": SID, "agent_id": ""}])
    def test_ops_agent_rows_an_event_with_no_agent_id_writes_nothing(self, tmp_path, ev):
        assert hook(tmp_path, ev) == (0, b"") and lines(tmp_path) == []

    def test_ops_agent_rows_off_writes_nothing_and_no_salt(self, tmp_path):
        env = querylog_env(tmp_path, mode="off")
        assert hook(tmp_path, agent_event("SubagentStart"), env) == (0, b"")
        assert lines(tmp_path) == [] and not (tmp_path / "querylog" / ql_capture.AGENT_SALT_NAME).exists()

    @pytest.mark.parametrize("fields", [
        {"event": "agent.run", "group": "a free text group", "ms": 5},
        {"event": "agent.run", "group": "kb-worker", "ms": 5, "agent": RAW_AGENT},  # a raw id, not its hash
        {"event": "agent.run", "group": "kb-worker", "ms": 5, "agent": "0123456789abcdef0"},  # too long for a hash
        {"event": "agent.run", "group": "kb-worker", "ms": 5, "item": "work/ST-lopowpsz"},  # branch text
        {"event": "agent.run", "group": "kb-worker", "ms": 5, "branch": "work/ST-lopowpsz"},
        {"event": "agent.run", "group": "kb-worker"}])
    def test_ops_agent_rows_refuse_free_text_and_a_raw_agent_id(self, tmp_path, monkeypatch, fields):
        monkeypatch.setattr(ql_capture, "spool_dir", lambda: tmp_path / "spool")
        assert ql_capture.record("ops", **fields) is None and not (tmp_path / "spool").exists()
        ok = {"event": "agent.run", "group": "kb-worker", "ms": 5, "agent": "0123456789ab", "item": "ST-lopowpsz"}
        assert ql_capture.record("ops", **ok) is not None  # planted counterpart: the closed shapes are written


    @pytest.mark.parametrize("fields", [
        {"event": "stall.remedy", "item": "ST-aaaaaaaa", "signal": "claim no commit", "remedy": "retry-narrower", "count": 1},
        {"event": "stall.remedy", "item": "ST-aaaaaaaa", "signal": "red-main", "remedy": "Ask the operator", "count": 1},
        {"event": "stall.remedy", "item": "work/ST-aaaaaaaa", "signal": "red-main", "remedy": "ask-operator", "count": 1},
        {"event": "stall.remedy", "item": "ST-aaaaaaaa", "signal": "red-main", "remedy": "ask-operator", "count": -1},
        {"event": "stall.remedy", "item": "ST-aaaaaaaa", "signal": "red-main", "remedy": "ask-operator"},
        {"event": "stall.remedy", "item": "ST-aaaaaaaa", "signal": "red-main", "remedy": "ask-operator", "count": 1,
         "why": "free text"},
        {"event": "stall.remedies", "item": "ST-aaaaaaaa", "signal": "red-main", "remedy": "ask-operator", "count": 1}])
    def test_ops_stall_remedy_refuses_free_text_and_an_event_outside_the_set(self, tmp_path, monkeypatch, fields):
        monkeypatch.setattr(ql_capture, "spool_dir", lambda: tmp_path / "spool")
        assert ql_capture.record("ops", **fields) is None and not (tmp_path / "spool").exists()
        ok = {"event": "stall.remedy", "item": "ST-aaaaaaaa", "signal": "red-main", "remedy": "ask-operator", "count": 2}
        assert ql_capture.record("ops", **ok) is not None  # planted counterpart: the closed shapes are written


class TestSwitches:
    EVENTS =[prompt("kb: laps"), tool("mcp__kb__kb_pack", {"question": "laps"}, PACK),
              tool("WebFetch", {"url": "https://example.com/x"}, "t"), stop("answer")]

    def write_config(self, data, text):
        d = Path(data) / "querylog"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(text, encoding="utf-8", newline="\n")

    def run_all(self, data, mode="local"):
        for ev in self.EVENTS:
            assert hook(data, ev, querylog_env(data, mode=mode)) == (0, b"")
        return lines(data)

    def test_default_mode_is_auto_and_writes(self, tmp_path):
        assert ql_base.DEFAULT_MODE == "auto"
        rows = self.run_all(tmp_path, mode=None)  # planted: the same events with no config file do write
        assert not (tmp_path / "querylog" / "config.json").exists()
        assert [r["surface"] for r in rows] == ["prompt", "mcp", "fetch", "stop"]
        self.write_config(tmp_path / "x", '{"mode": "local"}')
        assert [r["surface"] for r in self.run_all(tmp_path / "x")] == ["prompt", "mcp", "fetch", "stop"]

    @pytest.mark.parametrize("text", ['{"mode": "off"}', "{not json", '{"mode": "of"}', "[]"])
    def test_off_or_unreadable_config_writes_nothing(self, tmp_path, text):
        self.write_config(tmp_path, text)
        assert self.run_all(tmp_path) == [] and not spool(tmp_path).exists()

    def test_disabled_marker_writes_nothing(self, tmp_path):
        (tmp_path / "querylog").mkdir()
        (tmp_path / "querylog" / "DISABLED").write_text("", encoding="utf-8")
        self.write_config(tmp_path, '{"mode": "auto"}')
        assert self.run_all(tmp_path) == [] and not spool(tmp_path).exists()

    def test_off_also_silences_tools(self, tmp_path):
        self.write_config(tmp_path, '{"mode": "off"}')
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_ask.py"), "--route", "windows laps password length"],
                           env=querylog_env(tmp_path), capture_output=True, timeout=60)
        assert p.returncode == 0 and lines(tmp_path) == []

    def test_places(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        assert ql_base.HOME.samefile(KB)
        assert ql_base.places() == (ql_base.HOME / "_cache" / "querylog", ql_base.HOME / "_private" / "querylog.json")
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))  # another plugin's hook: not this copy
        assert ql_base.places()[0] == ql_base.HOME / "_cache" / "querylog"
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", KB)
        assert ql_base.places() == (tmp_path / "querylog", tmp_path / "querylog" / "config.json")

    def test_where(self, tmp_path):
        p = subprocess.run([sys.executable, QL, "where"], env=querylog_env(tmp_path, mode=None), capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        assert p.returncode == 0 and p.stdout.startswith("mode=auto ") and "writes=yes" in p.stdout
        assert lines(tmp_path) == []


@pytest.fixture
def www():
    with serve() as url:
        yield url


@pytest.fixture
def inproc(tmp_path, monkeypatch):
    """Capture in this process, under tmp_path."""
    for k, v in querylog_env(tmp_path).items():
        if k.startswith("CLAUDE_PLUGIN_") or k in ("NO_PROXY", "no_proxy"):
            monkeypatch.setenv(k, v)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")
    ql_capture.spool_dir.cache_clear()
    yield tmp_path
    ql_capture.spool_dir.cache_clear()


class TestToolRows:
    def test_kb_hook_row_and_unchanged_answer(self, tmp_path):
        import kb_hook
        q = "kb: intune win32 app detection rule"
        ev = {"hook_event_name": "UserPromptSubmit", "session_id": SID, "prompt_id": "p9", "prompt": q}
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=json.dumps(ev).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=120)
        assert p.returncode == 0, p.stderr
        assert json.loads(p.stdout.decode("utf-8")) == kb_hook.answer(q)
        (row,) = lines(tmp_path)
        assert (row["surface"], row["prompt_id"], row["question"], row["verdict"], row["answered"], row["forward"]) == \
               ("kb_hook", "p9", "intune win32 app detection rule", "good", True, False)
        assert "public/intune/win32-apps.md" in row["articles"] and is_uuid4(row["id"])
        assert "reason" not in row and "text" not in row and "pack" not in row
        assert row["lines"] and all(ql_store.CITATION.fullmatch(x["line"]) and set(x) <= {"line", "tag", "verdict"}
                                    for x in row["lines"])  # the pack's kb lines as path:line, never their text

    def test_plain_prompt_writes_nothing(self, tmp_path):
        ev = {"hook_event_name": "UserPromptSubmit", "session_id": SID, "prompt_id": "p9", "prompt": "fix the build"}
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=json.dumps(ev).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=120)
        assert (p.returncode, p.stdout) == (0, b"") and not spool(tmp_path).exists()

    def test_kb_ask_row(self, tmp_path):
        for args in (["--route", "What is the default Windows LAPS password length?"],
                     ["How many intune articles are partial?", "--route"]):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_ask.py"), *args], env=querylog_env(tmp_path),
                               capture_output=True, timeout=120)
            assert p.returncode == 0, p.stderr
        a, b = lines(tmp_path)
        assert (a["surface"], a["route"], a["verdict"], a["parts"]) == ("kb_ask", "plan", "good", 1)
        assert a["lines"] and all(ql_store.CITATION.fullmatch(x["line"]) for x in a["lines"])
        assert (b["route"], "verdict" in b, "session_id" in a) == ("tool", False, False)
        assert [f.name for f in spool(tmp_path).iterdir()] == [f"tools-{a['ts'][:10]}.jsonl"]

    def test_fetch_py_rows(self, inproc, www, monkeypatch):
        import fetch
        monkeypatch.setattr(fetch, "DELAY", 0)
        assert fetch.fetch(www + "/ok?key=secret#frag")[0] == b"hello"
        assert fetch.fetch(www + "/empty")[0] == b""
        with pytest.raises(Exception):
            fetch.fetch(www + "/missing")
        rows = lines(inproc)
        assert [(r["surface"], r["host"], r["path"], r["outcome"]) for r in rows] == [
            ("tool_fetch", "127.0.0.1", "/ok", "http-200"), ("tool_fetch", "127.0.0.1", "/empty", "empty"),
            ("tool_fetch", "127.0.0.1", "/missing", "http-404")]
        assert [r.get("chars") for r in rows] == [5, 0, None]  # the body's characters, when one was read
        assert b"secret" not in raw(inproc) and b"frag" not in raw(inproc)

    def test_census_rows(self, inproc, www):
        import census
        assert census.fetch(www + "/ok?x=1")[0] == 200
        assert census.fetch(www + "/missing")[0] == 404
        assert census.fetch(www + "/ok", limit=3)[1] == "hel"
        assert census.fetch("http://127.0.0.1:1/refused")[0] != 200
        assert [r["outcome"] for r in lines(inproc)] == ["http-200", "http-404", "truncated", "error"]
        assert [r.get("chars") for r in lines(inproc)] == [5, None, 3, None]

    def test_request_outcome(self):
        o = ql_capture.request_outcome
        assert o(200, None, 5, "https://a.example.com/x", "https://b.example.com/y") == "redirect-cross-host"
        assert o(200, None, 5, "https://a.example.com/x", "https://a.example.com/y") == "http-200"
        assert (o(None, "boom"), o(200, None, 0), o(200, None, 10, limit=10), o()) == ("error", "empty", "truncated", "unknown")
        assert ql_capture.host_path("ftp://x.example.com/a") == (None, None) and ql_capture.host_path("not a url") == (None, None)


def hooks_off(argv):
    """Whether a `claude -p` argument list turns every hook off for its run."""
    for i, a in enumerate(argv[:-1]):
        if a == "--settings":
            try:
                if json.loads(argv[i + 1]).get("disableAllHooks") is True:
                    return True
            except (ValueError, AttributeError):
                pass
    return False


class TestNoHooks:
    def test_pipeline_claude_runs_carry_disable_all_hooks(self):
        import kb_ask, redact
        for argv in (kb_ask.claude_argv("haiku", tools=False), kb_ask.claude_argv("sonnet", tools=True),
                     redact.names_argv("haiku"), ql_research.research_argv()):
            assert "-p" in argv and hooks_off(argv), argv

    def test_distill_haiku_call(self, monkeypatch):
        """distill's Haiku call is redact.names_argv as an argument list: hooks off, --model haiku, no tools."""
        seen = {}

        def fake_run(argv, **kw):
            seen.update(argv=argv, **kw)
            return subprocess.CompletedProcess(argv, 0, "[]", "")
        monkeypatch.setattr(subprocess, "run", fake_run)
        assert ql_distill.claude_haiku("prompt") == "[]"
        argv = seen["argv"]
        assert isinstance(argv, list) and "-p" in argv and hooks_off(argv), argv
        assert argv[argv.index("--model") + 1] == ql_distill.HAIKU_MODEL == "haiku"
        assert argv[argv.index("--tools") + 1] == "" and not seen.get("shell")
        assert seen["input"] == "prompt" and seen["timeout"] == ql_distill.HAIKU_TIMEOUT_S

    def test_research_call(self, monkeypatch):
        """research's call is research_argv as an argument list, in an empty directory: hooks off, web search and
        fetch the only built-in tools, the prompt on stdin."""
        seen = {}

        def fake_run(argv, **kw):
            seen.update(argv=argv, **kw)
            return subprocess.CompletedProcess(argv, 0, '{"facts": []}', "")
        monkeypatch.setattr(subprocess, "run", fake_run)
        assert ql_research.claude_research("prompt") == '{"facts": []}'
        argv = seen["argv"]
        assert isinstance(argv, list) and "-p" in argv and hooks_off(argv) and not seen.get("shell"), argv
        assert argv[argv.index("--tools") + 1] == "WebSearch,WebFetch"
        assert argv[argv.index("--permission-mode") + 1] == "dontAsk" and "--strict-mcp-config" in argv
        assert seen["input"] == "prompt" and seen["timeout"] == ql_research.RESEARCH_TIMEOUT_S
        assert seen["cwd"] and not Path(seen["cwd"]).exists()  # a temporary directory, gone after the run

    def test_research_docs_go_through_the_kb_servers_cache(self):
        """research's only MCP server is this copy's kb stdio server (no --roots, so it serves the live docs), and its
        only MCP tools allowed are the kb server's cached docs_search and docs_fetch: not the documentation servers
        themselves, not any other kb tool (planted: the docs plugin's .mcp.json and a direct docs tool fail)."""
        import kb_mcp

        def mcp_of(argv):
            servers = json.loads(argv[argv.index("--mcp-config") + 1])["mcpServers"]
            allowed = argv[argv.index("--allowedTools") + 1:]
            return servers, [t for t in allowed if t.startswith("mcp__")]

        argv = ql_research.research_argv()
        servers, tools = mcp_of(argv)
        assert list(servers) == ["kb"] and "--strict-mcp-config" in argv, servers
        kb = servers["kb"]
        assert Path(kb["args"][0]) == Path(TOOLS, "kb_mcp.py") and "--roots" not in kb["args"], kb
        live = {t["name"] for t in kb_mcp.LIVE_TOOL_LIST}
        assert sorted(tools) == sorted(f"mcp__kb__{n}" for n in live) == ["mcp__kb__docs_fetch", "mcp__kb__docs_search"]
        assert not live & {t["name"] for t in kb_mcp.TOOL_LIST}
        assert not any(t.startswith(("mcp__microsoft-learn", "mcp__claude-code-docs", "mcp__mcp-docs")) for t in argv)
        docs = json.loads(Path(kb_mcp.DOCS_MCP).read_text(encoding="utf-8"))  # planted: the old, direct servers
        i = argv.index("--mcp-config") + 1
        planted = [*argv[:i], json.dumps(docs), *argv[i + 1:], "mcp__microsoft-learn__microsoft_docs_search"]
        servers, tools = mcp_of(planted)
        assert list(servers) != ["kb"] and "mcp__microsoft-learn__microsoft_docs_search" in tools

    def test_research_repeat_search_within_7_days_calls_no_docs_server(self, tmp_path, monkeypatch):
        """The tool research is allowed, called through the kb server's handler twice with the same arguments within
        7 days, reaches the documentation server once: the second answer comes from the disk cache."""
        import kb_mcp
        calls = []

        class Remote:
            def __init__(self, url):
                self.url = url

            def start(self):
                pass

            def call(self, tool, arguments):
                calls.append((self.url, tool, arguments))
                return "page text"
        monkeypatch.setattr(kb_mcp, "RemoteMcp", Remote)
        monkeypatch.setattr(kb_mcp, "LIVE_ON", [True])
        monkeypatch.setenv("KB_DOCS_CACHE", str(tmp_path / "cache"))
        monkeypatch.delenv("KB_LIVE_DOCS", raising=False)
        name = next(t for t in ql_research.RESEARCH_MCP_TOOLS if t.endswith("docs_search")).split("__", 2)[2]
        msg = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": name, "arguments": {"server": "microsoft-learn", "query": "windows laps"}}}
        first = kb_mcp.handle({**msg, "id": 1})["result"]
        second = kb_mcp.handle({**msg, "id": 2})["result"]
        assert not first["isError"] and not second["isError"], (first, second)
        assert len(calls) == 1 and calls[0][1] == "microsoft_docs_search", calls
        assert "from the cache" in second["content"][0]["text"]

    def test_planted_argument_lists_fail(self):
        assert not hooks_off(["claude", "-p", "--model", "haiku"])
        assert not hooks_off(["claude", "-p", "--settings", json.dumps({"disableAllHooks": False})])
        assert not hooks_off(["claude", "-p", "--settings"])

    def test_every_claude_p_in_the_pipeline_is_checked(self):
        """The pipeline's modules build their `claude -p` lists only in the functions tested above."""
        allowed = {"kb_ask.py": 1, "redact.py": 1, "ql_research.py": 1}
        for p in [Path(TOOLS, n) for n in ("kb_ask.py", "redact.py", "querylog.py")] + sorted(Path(TOOLS).glob("ql_*.py")):
            assert len(re.findall(r'"-p"', p.read_text(encoding="utf-8"))) == allowed.get(p.name, 0), p.name

    def test_nothing_is_written_when_no_hook_runs(self, tmp_path):
        """With hooks disabled Claude Code never starts the capture hook: importing the module, its help and `where`
        write nothing, and neither does a plain prompt through kb_hook.py."""
        env = querylog_env(tmp_path, mode=None)  # no config file, so the directory is the tools' to make; no distill
        for argv in ([QL, "-h"], [QL, "where"], [QL], ["-c", "import querylog, kb_hook"]):
            subprocess.run([sys.executable, *argv], cwd=TOOLS, env=env, capture_output=True, timeout=60)
        assert not (tmp_path / "querylog").exists()


CAPTURE_EVENTS = ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure", "Stop", "SubagentStart", "SubagentStop")


def capture_problems(cfg, var):
    """What is wrong with the capture hooks of a settings or plugin file."""
    want = f'sh "${{{var}}}/_tools/kbpy" _tools/querylog.py capture'
    bad = []
    for event in CAPTURE_EVENTS:
        hs = [(g, h) for g in cfg.get("hooks", {}).get(event, []) for h in g.get("hooks", []) if "querylog.py" in h.get("command", "")]
        if len(hs) != 1:
            bad.append(f"{event}: {len(hs)} capture hooks")
            continue
        g, h = hs[0]
        if h.get("command") != want or h.get("async") is not True or h.get("type") != "command":
            bad.append(f"{event}: {h}")
        if event.startswith("PostToolUse"):
            rx = re.compile(g.get("matcher", "^$"))
            names = ["mcp__kb__kb_pack", "mcp__plugin_it-ops-kb_kb__kb_search", "WebFetch", "Bash", "PowerShell",
                     "mcp__microsoft-learn__microsoft_docs_fetch", "mcp__plugin_it-ops-kb-docs_claude-code-docs__x"]
            bad += [f"{event}: matcher misses {n}" for n in names if not rx.fullmatch(n)]
            bad += [f"{event}: matcher takes {n}" for n in ("Read", "Edit", "mcp__other__x") if rx.fullmatch(n)]
    kb = [h for g in cfg["hooks"]["UserPromptSubmit"] for h in g["hooks"] if "kb_hook.py" in h["command"]]
    if [h.get("async") for h in kb] != [None]:
        bad.append("the kb: hook must stay synchronous: it answers")
    return bad


def launch_problems(cfg, var):
    """What is wrong with the distill launcher hooks: one on SessionEnd (synchronous: it returns within the budget
    anyway) and one async on SessionStart, both `sh "<root>/_tools/kbpy" _tools/querylog.py launch`."""
    want = f'sh "${{{var}}}/_tools/kbpy" _tools/querylog.py launch'
    bad = []
    for event, is_async in (("SessionEnd", None), ("SessionStart", True)):
        hs = [h for g in cfg.get("hooks", {}).get(event, []) for h in g.get("hooks", [])
              if "querylog.py launch" in h.get("command", "")]
        if [(h.get("command"), h.get("async"), h.get("type")) for h in hs] != [(want, is_async, "command")]:
            bad.append(f"{event}: {hs}")
    return bad


def digest_problems(cfg, var):
    """What is wrong with the digest hook: one synchronous SessionStart command hook (an async hook's systemMessage
    reaches Claude, not the person) with the timeout DIGEST_HOOK_TIMEOUT_S, and no digest hook on another event."""
    want = f'sh "${{{var}}}/_tools/kbpy" _tools/querylog.py digest --hook'
    bad = []
    for event, groups in cfg.get("hooks", {}).items():
        hs = [h for g in groups for h in g.get("hooks", []) if "querylog.py digest" in h.get("command", "")]
        got = [(h.get("command"), h.get("async"), h.get("type"), h.get("timeout")) for h in hs]
        if event == "SessionStart" and got != [(want, None, "command", ql_report.DIGEST_HOOK_TIMEOUT_S)]:
            bad.append(f"{event}: {hs}")
        elif event != "SessionStart" and hs:
            bad.append(f"{event}: a digest hook")
    if "SessionStart" not in cfg.get("hooks", {}):
        bad.append("SessionStart: no digest hook")
    return bad


class TestHookConfig:
    def test_settings_and_plugin(self):
        assert capture_problems(load(".claude/settings.json"), "CLAUDE_PROJECT_DIR") == []
        assert capture_problems(load(".claude-plugin/plugin.json"), "CLAUDE_PLUGIN_ROOT") == []

    def test_launcher_hooks(self):
        assert launch_problems(load(".claude/settings.json"), "CLAUDE_PROJECT_DIR") == []
        assert launch_problems(load(".claude-plugin/plugin.json"), "CLAUDE_PLUGIN_ROOT") == []
        cfg = load(".claude/settings.json")
        missing = json.loads(json.dumps(cfg))
        del missing["hooks"]["SessionEnd"]
        asleep = json.loads(json.dumps(cfg))
        asleep["hooks"]["SessionEnd"][0]["hooks"][0]["async"] = True
        assert launch_problems(missing, "CLAUDE_PROJECT_DIR") and launch_problems(asleep, "CLAUDE_PROJECT_DIR")

    def test_digest_hook(self):
        assert digest_problems(load(".claude/settings.json"), "CLAUDE_PROJECT_DIR") == []
        assert digest_problems(load(".claude-plugin/plugin.json"), "CLAUDE_PLUGIN_ROOT") == []
        cfg = load(".claude/settings.json")
        asleep, slow, gone = (json.loads(json.dumps(cfg)) for _ in range(3))
        for c in (asleep, slow, gone):
            (h,) = [h for g in c["hooks"]["SessionStart"] for h in g["hooks"] if "digest" in h["command"]]
            if c is asleep:
                h["async"] = True
            elif c is slow:
                del h["timeout"]
            else:
                h["command"] = h["command"].replace("digest --hook", "launch")
        for c in (asleep, slow, gone):
            assert digest_problems(c, "CLAUDE_PROJECT_DIR")

    def test_planted_configs_fail(self):
        cfg = load(".claude/settings.json")
        sync = json.loads(json.dumps(cfg))
        del sync["hooks"]["Stop"][0]["hooks"][0]["async"]
        missing = json.loads(json.dumps(cfg))
        del missing["hooks"]["PostToolUseFailure"]
        narrow = json.loads(json.dumps(cfg))
        narrow["hooks"]["PostToolUse"][0]["matcher"] = "mcp__kb__.*"
        assert capture_problems(sync, "CLAUDE_PROJECT_DIR") and capture_problems(missing, "CLAUDE_PROJECT_DIR")
        assert any("misses WebFetch" in p for p in capture_problems(narrow, "CLAUDE_PROJECT_DIR"))
        assert capture_problems(cfg, "CLAUDE_PLUGIN_ROOT")  # the wrong root variable

    @pytest.mark.skipif(not SH, reason="no sh on PATH (Windows without Git Bash)")
    @pytest.mark.parametrize("rel,var", [(".claude/settings.json", "CLAUDE_PROJECT_DIR"),
                                         (".claude-plugin/plugin.json", "CLAUDE_PLUGIN_ROOT")])
    def test_shell_form_runs_end_to_end(self, tmp_path, rel, var):
        """The Stop capture command as Claude Code runs it (`sh -c`, Git Bash on Windows) after a kb: prompt."""
        (h,) = load(rel)["hooks"]["Stop"][0]["hooks"]
        env = querylog_env(tmp_path, base=dict(os.environ, **{var: KB}))
        hook(tmp_path, prompt("kb: laps"), env)
        p = subprocess.run([SH, "-c", h["command"].replace("${" + var + "}", KB.replace("\\", "/"))],
                           input=json.dumps(stop("done")).encode("utf-8"), capture_output=True, env=env, timeout=120)
        assert (p.returncode, p.stdout) == (0, b""), p.stderr
        assert [r["surface"] for r in lines(tmp_path)] == ["prompt", "stop"]
