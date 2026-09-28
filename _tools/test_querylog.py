"""Query log tests (kb/_self/querylog.md: Capture, Distill, Store, Learn and apply; `python3 _tools/tests.py -k querylog`).

  TestHookRows      the capture hook (`querylog.py capture`) with recorded hook events on stdin: one row per event
                    with a fresh UUID id; prompt, kb MCP, fetch and Stop rows; fetch rows keep host and path only,
                    Bash and PowerShell only for curl and wget, never command text or results; fetches and answers
                    only in a prompt that used the kb; the row size cap; stale spool files pruned
  TestSwitches      mode `off`, the DISABLED marker and an unreadable config file write nothing (planted: the same
                    events with the default mode write); where rows go in a clone and in a plugin host
  TestToolRows      kb_hook.py, kb_ask.py, fetch.py and census.py write their own rows; the kb: hook's answer is
                    unchanged
  TestNoHooks       every `claude -p` the pipeline starts carries --settings {"disableAllHooks": true} (planted: an
                    argument list without it, or with false), and nothing is written unless a hook or a tool runs
  TestHookConfig    the capture hooks are async on UserPromptSubmit, PostToolUse, PostToolUseFailure and Stop in
                    .claude/settings.json and the plugin, through kbpy, with matchers for the kb and fetch tools
                    (planted: a synchronous capture hook, a missing event); the shell form runs end to end; the
                    launcher runs on SessionEnd (synchronous) and SessionStart (async) in both files
  TestDistill       the fixture spool (_tools/fixtures/querylog/spool/) and the recorded Haiku reply file give the
                    golden run file (golden.jsonl): a header with run id, pipeline and retrieval versions and kb
                    commit, entries without them; only rule-redacted text reaches Haiku; nothing raw in the run
                    file; a flagged entry and a malformed reply's batch are dropped and only counted; over the batch,
                    run and daily caps entries wait in the spool; a failed call leaves its entries waiting; a second
                    run on the same spool writes nothing
  TestLock          a second distill exits on the lock (exit 3) and changes nothing; a stale lock is taken over;
                    of several processes taking the lock at once exactly one gets it
  TestLaunch        SessionEnd marks its session closed; the launcher returns within the 1.5-second budget with its
                    pipes free, and the distill it starts writes its run file after the launcher exited, also when
                    the launcher's process group is killed (POSIX) or its Windows job object closes with
                    kill-on-close (Windows only); SessionStart picks up closed sessions only, and starts nothing when
                    none is closed
  TestStore         the store gates, each with a planted failure: a duplicate id across run files (also through
                    `kbgit.py fix --check`), a missing header or provenance field, run metadata or raw fields in an
                    entry, an identifier in a text field, a fetch with a query string, a non-public host or command
                    text; `pack` and `search` never return a kb/_querylog/ line; _cache/ stays ignored
  TestLearn         the fixture store (_tools/fixtures/querylog/store/) gives findings of each kind with pack on
                    HEAD: eval, alias, expansion, gap candidate and source; every judged miss is re-run first
                    (`fixed-since` when it passes); learn writes findings only; two runs on the same store and HEAD
                    give byte-identical files, also in another copy; a HEAD change writes one new file
  TestSourceFindings  the staging triggers equal web-sources.md (planted: a changed number in the doc or the code); a
                    host's level comes from the provider registry (a root's _providers.csv too), else the routes
                    table, and every registry host has a routes row (planted: a row without one); no stage finding
                    for a host with the needed level; source findings read the registry and the routes table
  TestFindingsGates the findings gates of `check`, each with a planted failure
  TestApply         in a kb copy, `learn` then `apply` on the fixture store (a paraphrase and an unknown word): each
                    eval row lands with its expansion or alias, `rag.py eval` passes, the mean pack and off-kb `good`
                    do not rise; a miss with no accepted fix becomes a gap candidate and its fix `rejected`, as new
                    records; a second apply and learn change nothing; planted: an eval row without its fix fails
  TestApplyGates    apply with stub gates: planted failures for an eval row without its fix finding, a fix that fails
                    the gates (files put back), an alias term colliding with an existing term, source findings
                    (never applied), a red eval before any change; convergence
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub.
"""
import datetime, getpass, http.server, json, os, re, shutil, signal, socket, subprocess, sys, threading, time, uuid
from pathlib import Path

import pytest

import querylog
from conftest import GIT, KB, TOOLS, copy_kb, querylog_env

SID = "3f2a4c1e-0000-4000-8000-00000000abcd"
QL = os.path.join(TOOLS, "querylog.py")
SH = shutil.which("sh")


def spool(data):
    return Path(data) / "querylog" / "spool"


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


def prompt(text, pid="p1", sid=SID):
    return {"hook_event_name": "UserPromptSubmit", "session_id": sid, "prompt_id": pid, "prompt": text}


def tool(name, args, response=None, pid="p1", ok=True, error=None):
    ev = {"hook_event_name": "PostToolUse" if ok else "PostToolUseFailure", "session_id": SID, "prompt_id": pid,
          "tool_name": name, "tool_input": args, "tool_use_id": "toolu_01"}
    if ok:
        ev["tool_response"] = response
    else:
        ev["error"] = error or ""
    return ev


def stop(answer, pid="p1"):
    return {"hook_event_name": "Stop", "session_id": SID, "prompt_id": pid, "stop_hook_active": False,
            "last_assistant_message": answer}


PACK = ("coverage: good (best article matches 3 of 3 key words)\n\n## public/windows/laps.md  Windows LAPS\n- fact\n"
        "# Q2\ncoverage: weak (...)\n\n## public/intune/win32-apps.md  Win32 apps\n- fact\n")


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
        assert (b["tool"], b["args"], b["verdict"]) == ("kb_show", {"path": "public/windows/laps.md:12"}, "weak")
        assert (c["outcome"], "verdict" in c) == ("error", False)

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
        p = subprocess.run([sys.executable, "-c", "import querylog; querylog.record('kb_ask', question='q', route='plan')"],
                           cwd=TOOLS, env=env, capture_output=True, timeout=60)
        assert p.returncode == 0, p.stderr
        hook(tmp_path, stop("answer", pid="w"))
        assert [r["surface"] for r in lines(tmp_path)] == ["prompt", "stop", "kb_ask"]  # the session file sorts first

    def test_row_size_cap_and_utf8(self, tmp_path):
        hook(tmp_path, prompt("kb: " + "Łódź ☃ \"quoted\" " * 20000))
        data = raw(tmp_path)
        assert b"\r" not in data and data.endswith(b"\n")
        line = data.decode("utf-8").rstrip("\n")
        assert len(line) <= querylog.SPOOL_ROW_MAX_CHARS and "Łódź ☃" in line
        assert json.loads(line)["prompt"].endswith(querylog.CUT)

    def test_unsafe_session_id_goes_to_the_tools_file(self, tmp_path):
        hook(tmp_path, prompt("hi", sid="../../escape"))
        assert [f.name.startswith("tools-") for f in spool(tmp_path).iterdir()] == [True]
        assert not (tmp_path / "escape.jsonl").exists()

    def test_stale_spool_files_are_pruned(self, tmp_path):
        spool(tmp_path).mkdir(parents=True)
        old, new = spool(tmp_path) / "old.jsonl", spool(tmp_path) / "new.jsonl"
        for f in (old, new):
            f.write_text("{}\n", encoding="utf-8", newline="\n")
        t = time.time() - (querylog.SPOOL_MAX_AGE_DAYS + 1) * 86400
        os.utime(old, (t, t))
        hook(tmp_path, prompt("hi"))
        assert not old.exists() and new.exists()

    def test_bad_input_never_fails(self, tmp_path):
        for payload in (b"", b"not json", b"[1,2]", b'{"hook_event_name": "PostToolUse", "tool_input": "x"}'):
            p = subprocess.run([sys.executable, QL, "capture"], input=payload, capture_output=True,
                               env=querylog_env(tmp_path), timeout=60)
            assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"")
        assert lines(tmp_path) == []


class TestSwitches:
    EVENTS = [prompt("kb: laps"), tool("mcp__kb__kb_pack", {"question": "laps"}, PACK),
              tool("WebFetch", {"url": "https://example.com/x"}, "t"), stop("answer")]

    def write_config(self, data, text):
        d = Path(data) / "querylog"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(text, encoding="utf-8", newline="\n")

    def run_all(self, data):
        for ev in self.EVENTS:
            assert hook(data, ev) == (0, b"")
        return lines(data)

    def test_default_mode_is_local_and_writes(self, tmp_path):
        assert querylog.DEFAULT_MODE == "local"
        rows = self.run_all(tmp_path)  # planted: the same events with no config file do write
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
        assert querylog.HOME.samefile(KB)
        assert querylog.places() == (querylog.HOME / "_cache" / "querylog", querylog.HOME / "_private" / "querylog.json")
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))  # another plugin's hook: not this copy
        assert querylog.places()[0] == querylog.HOME / "_cache" / "querylog"
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", KB)
        assert querylog.places() == (tmp_path / "querylog", tmp_path / "querylog" / "config.json")

    def test_where(self, tmp_path):
        p = subprocess.run([sys.executable, QL, "where"], env=querylog_env(tmp_path), capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        assert p.returncode == 0 and p.stdout.startswith("mode=local ") and "writes=yes" in p.stdout
        assert lines(tmp_path) == []


@pytest.fixture
def www():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            code, body = {"/ok": (200, b"hello"), "/empty": (200, b""), "/missing": (404, b"no")}.get(
                self.path.split("?")[0], (500, b"x"))
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def inproc(tmp_path, monkeypatch):
    """Capture in this process, under tmp_path."""
    for k, v in querylog_env(tmp_path).items():
        if k.startswith("CLAUDE_PLUGIN_") or k in ("NO_PROXY", "no_proxy"):
            monkeypatch.setenv(k, v)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")
    querylog.spool_dir.cache_clear()
    yield tmp_path
    querylog.spool_dir.cache_clear()


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
        assert "reason" not in row and "text" not in row

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
        assert b"secret" not in raw(inproc) and b"frag" not in raw(inproc)

    def test_census_rows(self, inproc, www):
        import census
        assert census.fetch(www + "/ok?x=1")[0] == 200
        assert census.fetch(www + "/missing")[0] == 404
        assert census.fetch(www + "/ok", limit=3)[1] == "hel"
        assert census.fetch("http://127.0.0.1:1/refused")[0] != 200
        assert [r["outcome"] for r in lines(inproc)] == ["http-200", "http-404", "truncated", "error"]

    def test_request_outcome(self):
        o = querylog.request_outcome
        assert o(200, None, 5, "https://a.example.com/x", "https://b.example.com/y") == "redirect-cross-host"
        assert o(200, None, 5, "https://a.example.com/x", "https://a.example.com/y") == "http-200"
        assert (o(None, "boom"), o(200, None, 0), o(200, None, 10, limit=10), o()) == ("error", "empty", "truncated", "unknown")
        assert querylog.host_path("ftp://x.example.com/a") == (None, None) and querylog.host_path("not a url") == (None, None)


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
                     redact.names_argv("haiku")):
            assert "-p" in argv and hooks_off(argv), argv

    def test_distill_haiku_call(self, monkeypatch):
        """distill's Haiku call is redact.names_argv as an argument list: hooks off, --model haiku, no tools."""
        seen = {}

        def fake_run(argv, **kw):
            seen.update(argv=argv, **kw)
            return subprocess.CompletedProcess(argv, 0, "[]", "")
        monkeypatch.setattr(querylog.subprocess, "run", fake_run)
        assert querylog.claude_haiku("prompt") == "[]"
        argv = seen["argv"]
        assert isinstance(argv, list) and "-p" in argv and hooks_off(argv), argv
        assert argv[argv.index("--model") + 1] == querylog.HAIKU_MODEL == "haiku"
        assert argv[argv.index("--tools") + 1] == "" and not seen.get("shell")
        assert seen["input"] == "prompt" and seen["timeout"] == querylog.HAIKU_TIMEOUT_S

    def test_planted_argument_lists_fail(self):
        assert not hooks_off(["claude", "-p", "--model", "haiku"])
        assert not hooks_off(["claude", "-p", "--settings", json.dumps({"disableAllHooks": False})])
        assert not hooks_off(["claude", "-p", "--settings"])

    def test_every_claude_p_in_the_pipeline_is_checked(self):
        """The pipeline's modules build their `claude -p` lists only in the functions tested above."""
        for name, allowed in (("kb_ask.py", 1), ("redact.py", 1), ("querylog.py", 0)):
            text = Path(TOOLS, name).read_text(encoding="utf-8")
            assert len(re.findall(r'"-p"', text)) == allowed, name

    def test_nothing_is_written_when_no_hook_runs(self, tmp_path):
        """With hooks disabled Claude Code never starts the capture hook: importing the module, its help and `where`
        write nothing, and neither does a plain prompt through kb_hook.py."""
        env = querylog_env(tmp_path)
        for argv in ([QL, "-h"], [QL, "where"], [QL], ["-c", "import querylog, kb_hook"]):
            subprocess.run([sys.executable, *argv], cwd=TOOLS, env=env, capture_output=True, timeout=60)
        assert not (tmp_path / "querylog").exists()


def load(rel):
    with open(os.path.join(KB, rel), encoding="utf-8") as f:
        return json.load(f)


CAPTURE_EVENTS = ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure", "Stop")


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
        hs = [h for g in cfg.get("hooks", {}).get(event, []) for h in g.get("hooks", []) if "querylog.py" in h.get("command", "")]
        if [(h.get("command"), h.get("async"), h.get("type")) for h in hs] != [(want, is_async, "command")]:
            bad.append(f"{event}: {hs}")
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


# ---------------------------------------------------------------- distill and the store (Query log item 4)

FIXTURES = Path(TOOLS) / "fixtures" / "querylog"
NOW = datetime.datetime(2026, 9, 28, 12, 0, tzinfo=datetime.timezone.utc)
RUN_ID = "20260928T120000Z-0000abcd"
S_ENDED, S_IDLE, S_OPEN = (f"aaaaaaaa-0000-4000-8000-00000000000{i}" for i in (1, 2, 3))
RAW = ["anna.nowak", "acme", "10." + "1.20.33", "PL-LAPTOP-7731", "it-helpdesk", "Kowalczyk", "Warsaw", "anowak",
       "session_id", "prompt_id", "transcript_path", S_ENDED, S_IDLE, '"pa1"', '"prompt":', '"answer":', "mailed"]


def c(s):
    """The fixtures break every identifier with `~`, so the leak scan of tracked files passes over them."""
    return s.replace("~", "")


def plant_spool(qdir, now=NOW):
    """The fixture spool under qdir/spool: S_ENDED ended (SessionEnd marker), S_IDLE idle for two days, S_OPEN
    active a minute ago; the tools file of the day before."""
    sp = Path(qdir) / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    for f in (FIXTURES / "spool").iterdir():
        (sp / f.name).write_text(c(f.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    t = now.timestamp()
    for sid, age in ((S_ENDED, 3600), (S_IDLE, 2 * 86400), (S_OPEN, 60)):
        os.utime(sp / f"{sid}.jsonl", (t - age, t - age))
    (sp / f"{S_ENDED}.end").touch()
    return sp


def run_distill(qdir, haiku, now=NOW, run_id=RUN_ID):
    said = []
    rc = querylog.distill(qdir=qdir, cfg=Path(qdir) / "config.json", haiku=haiku, now_dt=now, run_id=run_id,
                          kb_commit="0" * 40, out=said.append)
    return rc, said


def store_files(qdir):
    return sorted((Path(qdir) / "store").rglob("*.jsonl"))


def jsonl(path):
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def echo(prompt):
    """A Haiku stub that answers every entry: its question is the rule-redacted prompt."""
    items = json.loads(prompt[prompt.index("\n\n[") + 2:])
    return json.dumps([{"i": it["i"], "question": it["prompt"], "summary": "Stub summary.", "judged": "answered",
                        "best": None, "identifying": False} for it in items])


class TestDistill:
    def test_golden_run_file(self, tmp_path):
        q = tmp_path / "querylog"
        sp = plant_spool(q)
        open_before = (sp / f"{S_OPEN}.jsonl").read_bytes()
        replay = querylog.Replay(FIXTURES / "haiku.json")
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
        assert set(header) == set(querylog.HEADER_KEYS) and header["run"] == RUN_ID
        assert all(not set(e) & set(querylog.HEADER_KEYS) for e in entries)
        assert querylog.store_problems(q / "store") == []
        # the spool: the closed sessions and the finished day's tools file are gone, the open session is untouched
        assert sorted(p.name for p in sp.iterdir()) == [f"{S_OPEN}.jsonl"]
        assert (sp / f"{S_OPEN}.jsonl").read_bytes() == open_before

    def test_only_rule_redacted_text_reaches_haiku(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        replay = querylog.Replay(FIXTURES / "haiku.json")
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
        run_distill(q, querylog.Replay(FIXTURES / "haiku.json"))
        text = store_files(q)[0].read_text(encoding="utf-8")
        for raw in RAW:
            assert raw not in text, raw
        for who in {getpass.getuser(), socket.gethostname().split(".")[0]} - {""}:
            assert not re.search(rf"(?<![\w-]){re.escape(who)}(?![\w-])", text), who

    def test_doubtful_entry_is_dropped_and_counted(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        run_distill(q, querylog.Replay(FIXTURES / "haiku.json"))
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
        run_distill(q, querylog.Replay(FIXTURES / "haiku.json"))
        e = next(e for e in jsonl(store_files(q)[0]) if e.get("id") == "11111111-0000-4000-8000-0000000000b1")
        assert "best" not in e and e["articles"] == ["public/intune/win32-apps.md"]

    def test_over_the_caps_entries_wait(self, tmp_path, monkeypatch):
        monkeypatch.setattr(querylog, "HAIKU_BATCH_ENTRIES", 2)
        monkeypatch.setattr(querylog, "HAIKU_BATCHES_PER_RUN", 1)
        monkeypatch.setattr(querylog, "HAIKU_DAILY_CALLS", 2)
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
        assert querylog.store_problems(q / "store") == []

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
        rc, said = run_distill(q, querylog.Replay(FIXTURES / "haiku.json"), run_id="20260928T120500Z-0000abce")
        assert said[-1].endswith("entries=4 dropped=1 waiting=0"), said
        ids = [e["id"] for f in store_files(q) for e in jsonl(f)[1:]]
        assert len(ids) == len(set(ids)) == 6

    def test_a_second_run_on_the_same_spool_writes_nothing(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        run_distill(q, querylog.Replay(FIXTURES / "haiku.json"))
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


def distill_cli(data, *args):
    return subprocess.run([sys.executable, QL, "distill", *args], capture_output=True, text=True, encoding="utf-8",
                          env=querylog_env(data), timeout=120)


LOCK_TAKER = """
import sys, time
import querylog
got = querylog.acquire(sys.argv[1])
print("got" if got else "busy", flush=True)
time.sleep(1.5)
"""


class TestLock:
    def test_a_second_distill_exits_on_the_lock(self, tmp_path):
        q = tmp_path / "querylog"
        sp = plant_spool(q)
        lock = querylog.acquire(q)
        info = json.loads(lock.read_text(encoding="utf-8"))
        assert info["pid"] == os.getpid() and info["started"].endswith("Z")
        before = {p.name: p.read_bytes() for p in sp.iterdir()}
        p = distill_cli(tmp_path, "--replay", str(FIXTURES / "haiku.json"))
        assert (p.returncode, p.stdout) == (3, "distill: another distill holds the lock\n"), p.stderr
        assert {p.name: p.read_bytes() for p in sp.iterdir()} == before and store_files(q) == []
        querylog.release(lock)
        p = distill_cli(tmp_path, "--replay", str(FIXTURES / "haiku.json"))  # planted: without the lock it runs
        assert p.returncode == 0 and "entries=" in p.stdout, p.stdout + p.stderr
        assert not (q / querylog.LOCK_NAME).exists()

    def test_a_stale_lock_is_taken_over(self, tmp_path):
        q = tmp_path / "querylog"
        q.mkdir()
        old = time.time() - querylog.LOCK_STALE_S - 5
        (q / querylog.LOCK_NAME).write_text(json.dumps({"pid": 1, "started_epoch": old}), encoding="utf-8")
        p = distill_cli(tmp_path)
        assert p.returncode == 0 and "nothing to write" in p.stdout, p.stdout + p.stderr
        (q / querylog.LOCK_NAME).write_text(json.dumps({"pid": 1, "started_epoch": time.time() - 5}), encoding="utf-8")
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


def session_start(sid="new-session"):
    return {"hook_event_name": "SessionStart", "session_id": sid, "source": "startup"}


def plant_fetch_day(data, n=1):
    """A tools file of yesterday (UTC) holding n fetch.py requests: ready to distill, with nothing for Haiku."""
    sp = spool(data)
    sp.mkdir(parents=True, exist_ok=True)
    day = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).date().isoformat()
    rows = [{"id": str(uuid.uuid4()), "ts": f"{day}T08:00:0{i}.000Z", "surface": "tool_fetch", "tool": "fetch.py",
             "host": "learn.microsoft.com", "path": f"/en-us/p{i}", "outcome": "http-200"} for i in range(n)]
    (sp / f"tools-{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    return rows


def wait_for_run(data, timeout=60):
    """The store's run files once one exists (the detached distill wrote it), else []."""
    end = time.time() + timeout
    while time.time() < end:
        files = sorted((Path(data) / "querylog" / "store").rglob("*.jsonl"))
        if files and not (Path(data) / "querylog" / querylog.LOCK_NAME).exists():
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
        assert files, (tmp_path / "querylog" / querylog.LOG_NAME).read_text(encoding="utf-8")
        assert files[0].stat().st_mtime > exited  # written after the launcher was gone (LAUNCH_SETTLE_S)
        assert [e["id"] for e in jsonl(files[0])[1:]] == [r["id"] for r in rows]
        log = (tmp_path / "querylog" / querylog.LOG_NAME).read_text(encoding="utf-8")
        assert "entries=1" in log and "Haiku" not in log

    def test_launch_itself_fits_its_share_of_the_budget(self, tmp_path, monkeypatch):
        for k, v in querylog_env(tmp_path).items():
            if k.startswith("CLAUDE_PLUGIN_"):
                monkeypatch.setenv(k, v)
        plant_fetch_day(tmp_path)
        t0 = time.monotonic()
        pid = querylog.launch(session_end())
        took = time.monotonic() - t0
        assert pid and took < querylog.LAUNCH_BUDGET_S, took
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
        """The SessionEnd command as Claude Code runs it (`sh -c`, Git Bash on Windows)."""
        (h,) = load(rel)["hooks"]["SessionEnd"][0]["hooks"]
        plant_fetch_day(tmp_path)
        env = querylog_env(tmp_path, base=dict(os.environ, **{var: KB}))
        t0 = time.monotonic()
        p = subprocess.run([SH, "-c", h["command"].replace("${" + var + "}", KB.replace("\\", "/"))],
                           input=json.dumps(session_end()).encode("utf-8"), capture_output=True, env=env, timeout=120)
        assert (p.returncode, p.stdout) == (0, b"") and time.monotonic() - t0 < 1.5, p.stderr
        assert wait_for_run(tmp_path)

    def test_session_start_picks_up_closed_sessions_only(self, tmp_path):
        sp = spool(tmp_path)
        sp.mkdir(parents=True)
        closed, active = "cccccccc-0000-4000-8000-000000000001", "cccccccc-0000-4000-8000-000000000002"
        for sid in (closed, active):
            row = {"id": str(uuid.uuid4()), "ts": "2026-09-20T10:00:00.000Z", "surface": "mcp", "session_id": sid,
                   "prompt_id": "p1", "tool": "kb_show", "args": {"path": "public/windows/laps.md:12"},
                   "articles": ["public/windows/laps.md"]}  # no question text: nothing for Haiku
            (sp / f"{sid}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8", newline="\n")
        old = time.time() - querylog.SESSION_IDLE_CLOSED_S - 60
        os.utime(sp / f"{closed}.jsonl", (old, old))
        before = (sp / f"{active}.jsonl").read_bytes()
        rc, out, took, _ = launch_proc(tmp_path, session_start())
        assert (rc, out) == (0, b"") and took < 1.5
        (run,) = wait_for_run(tmp_path)
        (entry,) = jsonl(run)[1:]
        assert (entry["surface"], entry["articles"]) == ("mcp", ["public/windows/laps.md"])
        assert sorted(p.name for p in sp.iterdir()) == [f"{active}.jsonl"]
        assert (sp / f"{active}.jsonl").read_bytes() == before

    def test_session_start_starts_nothing_when_no_session_is_closed(self, tmp_path):
        sp = spool(tmp_path)
        sp.mkdir(parents=True)
        (sp / f"{SID}.jsonl").write_text("{}\n", encoding="utf-8")
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        (sp / f"tools-{today}.jsonl").write_text("{}\n", encoding="utf-8")
        assert launch_proc(tmp_path, session_start())[:2] == (0, b"")
        assert not (tmp_path / "querylog" / querylog.LOG_NAME).exists()
        assert querylog.launch({"hook_event_name": "Stop"}) is None

    def test_launcher_starts_nothing_while_a_distill_runs(self, tmp_path):
        plant_fetch_day(tmp_path)
        lock = querylog.acquire(tmp_path / "querylog")
        assert launch_proc(tmp_path, session_start())[:2] == (0, b"")
        assert not (tmp_path / "querylog" / querylog.LOG_NAME).exists()
        querylog.release(lock)


# ---------------------------------------------------------------- the store gates

def golden_store(store, lines_=None, name=RUN_ID):
    """The store `store` with the golden run file (or `lines_`, JSON objects) as <yyyy-mm>/<run-id>.jsonl."""
    objs = lines_ if lines_ is not None else jsonl(FIXTURES / "golden.jsonl")
    p = Path(store) / f"{name[:4]}-{name[4:6]}" / f"{name}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in objs), encoding="utf-8", newline="\n")
    return Path(store)


def planted(tmp_path, change):
    """The golden run file with `change(objects)` applied: the store's problems."""
    objs = jsonl(FIXTURES / "golden.jsonl")
    change(objs)
    return querylog.store_problems(golden_store(tmp_path / "store", objs))


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
        assert querylog.store_problems() == []
        p = subprocess.run([sys.executable, QL, "check"], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert (p.returncode, p.stdout) == (0, "querylog check: problems=0\n"), p.stdout

    def test_golden_passes_and_check_reports(self, tmp_path):
        store = golden_store(tmp_path / "store")
        assert querylog.store_problems(store) == []
        bad =golden_store(tmp_path / "bad", [{"run": "x"}])
        p = subprocess.run([sys.executable, QL, "check", str(bad)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        assert p.returncode == 1 and "header lacks" in p.stdout, p.stdout

    def test_duplicate_id_across_run_files(self, tmp_path):
        store = golden_store(tmp_path / "store")
        assert querylog.duplicate_ids(store) == []
        golden_store(store, name="20260928T130000Z-0000ffff", lines_=[
            {**jsonl(FIXTURES / "golden.jsonl")[0], "run": "20260928T130000Z-0000ffff",
             "counts": {"entries": 1, "dropped": 0, "waiting": 0}}, jsonl(FIXTURES / "golden.jsonl")[1]])
        (dup,) = querylog.duplicate_ids(store)
        assert "2026-09/20260928T130000Z-0000ffff.jsonl:2: duplicate entry id 22222222-" in dup
        assert querylog.store_problems(store)[-1] == dup

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
        problems = planted(tmp_path / "s", lambda o: o[4].update(summary=c(text)))
        assert any("an identifier in `summary`" in p for p in problems), problems

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
    ])
    def test_fetch_gates(self, tmp_path, change, problem):
        problems = planted(tmp_path, lambda o: change(o[2]))  # the standalone fetch.py entry
        assert any(problem in p for p in problems), problems
        nested = planted(tmp_path / "n", lambda o: change(o[6]["fetches"][1]))  # a fetch inside a lookup
        if problem != "raw spool fields: command":
            assert any(problem in p for p in nested), nested
        else:
            assert any("fetch fields a fetch never keeps: command" in p for p in nested), nested

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


# ---------------------------------------------------------------- learn (Query log item 5)

LEARN_STORE = FIXTURES / "store"
LAPS = "public/windows/laps.md"
MISS = {f"55555555-0000-4000-8000-0000000000{n}" for n in ("a1", "a2", "a3", "a4")}
ANSWERED = "55555555-0000-4000-8000-0000000000a5"


def learn_store(tmp_path, name="store"):
    """A copy of the fixture store: one run file with judged misses, an answered lookup and fetch.py requests."""
    dst = Path(tmp_path) / name
    shutil.copytree(LEARN_STORE, dst)
    return dst


def run_learn(store, pack, **kw):
    said = []
    rc = querylog.learn(store, pack=pack, kb_commit="0" * 40, out=said.append, **kw)
    return rc, said


def findings(store):
    """[(file, [records])] of the store's findings files, oldest first."""
    return [(p, jsonl(p)[1:]) for p in querylog.findings_files(store)]


def by_id(store):
    return {r["id"]: r for _, recs in findings(store) for r in recs}


def tree(store):
    return {p.relative_to(store).as_posix(): p.read_bytes() for p in sorted(Path(store).rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def head_pack():
    """pack on HEAD (the clone's kb), each question once for the module."""
    seen = {}

    def pack(q):
        if q not in seen:
            seen[q] = querylog.default_pack(q)
        return seen[q]
    return pack


def failing(q):
    return {"verdict": "none", "paths": [], "missing": []}


def passing(q):
    return {"verdict": "good", "paths": [LAPS, "public/intune/win32-apps.md"], "missing": []}


class TestLearn:
    def test_the_fixture_gives_findings_of_each_kind(self, tmp_path, head_pack):
        store = learn_store(tmp_path)
        rc, said = run_learn(store, head_pack)
        assert rc == 0 and said[0].startswith("learn: run=20260928T130000Z-") and "findings=9" in said[0], said
        ((f, recs),) = findings(store)
        assert f.parent.name == "2026-09" and f.parent.parent.name == "findings"
        kinds = {(r["kind"], r.get("entry", r.get("host"))): r for r in recs}
        assert {k for k, _ in kinds} == set(querylog.FINDING_KINDS)

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
        assert set(src) == {("stage", "www.anthropic.com"), ("stage", "arxiv.org"), ("route", "learn.microsoft.com")}
        assert src[("stage", "www.anthropic.com")]["triggers"] == ["share"]
        assert src[("stage", "arxiv.org")]["triggers"] == ["failures"]
        assert querylog.store_problems(store) == []

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
        entries = {e["id"]: e for _, e in querylog.store_entries(store)}
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
        assert querylog.store_problems(store) == []

    def test_cli(self, tmp_path):
        store = learn_store(tmp_path)
        p = subprocess.run([sys.executable, QL, "learn", "--store", str(store)], capture_output=True, text=True,
                           encoding="utf-8", env=querylog_env(tmp_path / "data"), timeout=300)
        assert p.returncode == 0 and p.stdout.startswith("learn: run="), p.stdout + p.stderr
        (tmp_path / "data" / "querylog").mkdir(parents=True)
        (tmp_path / "data" / "querylog" / "config.json").write_text('{"mode": "off"}', encoding="utf-8")
        p = subprocess.run([sys.executable, QL, "learn"], capture_output=True, text=True, encoding="utf-8",
                           env=querylog_env(tmp_path / "data"), timeout=120)
        assert (p.returncode, p.stdout) == (0, "learn: logging is off\n")


class TestSourceFindings:
    def test_triggers_match_web_sources(self, monkeypatch):
        assert querylog.trigger_problems() == []
        doc = querylog.WEB_SOURCES.read_text(encoding="utf-8")
        assert "at least 25 rows" in doc and "Three or more failures" in doc
        planted = doc.replace("at least 25 rows", "at least 30 rows")
        assert querylog.trigger_problems(planted) == ["trigger share_rows: querylog.py has 25, web-sources.md has 30"]
        assert querylog.trigger_problems(doc.replace("Three or more failures", "Four or more failures"))
        assert querylog.trigger_problems(doc.replace("at least 5%", "at least 10%"))
        monkeypatch.setattr(querylog, "STAGE_FAILURES", 4)
        assert querylog.trigger_problems(doc) == ["trigger failures: querylog.py has 4, web-sources.md has 3"]

    def test_level_from_the_registry_else_the_routes_table(self, tmp_path, monkeypatch):
        assert querylog.staging_level("learn.microsoft.com") == (3, "registry")  # in both: the registry decides
        assert querylog.staging_level("raw.githubusercontent.com") == (3, "registry")
        assert querylog.staging_level("pypi.org") == (1, "routes")
        assert querylog.staging_level("platform.claude.com") == (1, "routes")
        assert querylog.staging_level("www.anthropic.com") == (0, None)
        import kbcommon, provider  # a root's own _providers.csv counts as the registry
        team = tmp_path / "team"
        team.mkdir()
        (team / provider.ROOT_FILE).write_text("provider,match\nteam-wiki,wiki.corp.example.com/\n", encoding="utf-8",
                                               newline="\n")
        roots = kbcommon.roots()
        monkeypatch.setattr(kbcommon, "roots", lambda: roots + [kbcommon.Root("team", str(team), "TM", "internal", "")])
        assert querylog.staging_level("wiki.corp.example.com") == (3, "registry")

    def test_the_registry_and_the_routes_table_agree(self):
        assert querylog.registry_problems() == []
        import provider
        rows = provider._read(provider.SHARED)
        planted = rows + [{"provider": "vendor", "match": "docs.vendor.example.org/"}]
        assert querylog.registry_problems(planted) == [
            "provider vendor: docs.vendor.example.org has a registry row but no row in the routes table"]
        doc = querylog.WEB_SOURCES.read_text(encoding="utf-8")
        routes = querylog.routes_table(doc.replace("| `learn.microsoft.com` |", "| Learn |"))
        assert any("learn.microsoft.com" in p for p in querylog.registry_problems(rows, routes))
        team = [{"provider": "team-wiki", "match": "wiki.corp.example.com/", "_root": "team"}]
        assert querylog.registry_problems(rows + team) == []  # a root's own providers are its team's

    def test_no_source_finding_for_a_host_with_the_needed_level(self, tmp_path):
        store = learn_store(tmp_path)
        run_learn(store, passing)
        hosts = {(r["signal"], r["host"]) for r in by_id(store).values() if r["kind"] == "source"}
        # learn.microsoft.com (registry) and pypi.org (routes) failed three times each, and learn.microsoft.com backs
        # far more than 25 sources: neither gets a stage finding
        assert ("stage", "learn.microsoft.com") not in hosts and ("stage", "pypi.org") not in hosts
        assert ("stage", "www.anthropic.com") in hosts and ("stage", "arxiv.org") in hosts  # planted: level 0

    def test_source_findings_read_the_registry_and_the_routes_table(self, tmp_path, monkeypatch):
        import provider
        shared = tmp_path / "providers.csv"
        row = ["anthropic", "www.anthropic.com/"] + [""] * (len(provider.COLS) - 2)
        shared.write_text(Path(provider.SHARED).read_text(encoding="utf-8") + ",".join(row) + "\n",
                          encoding="utf-8", newline="\n")
        assert querylog.registry_row("www.anthropic.com") is None
        monkeypatch.setattr(provider, "SHARED", str(shared))  # a registry row added: the host has level 3
        doc = querylog.WEB_SOURCES.read_text(encoding="utf-8").replace(
            "| PyPI |", "| `arxiv.org` | WebSearch | the abstract page | WebFetch |\n| PyPI |")
        monkeypatch.setattr(querylog, "WEB_SOURCES", tmp_path / "web-sources.md")
        querylog.WEB_SOURCES.write_text(doc, encoding="utf-8", newline="\n")  # a routes row added: level 1
        store = learn_store(tmp_path)
        run_learn(store, passing)
        assert not [r for r in by_id(store).values() if r.get("signal") == "stage"]


@pytest.fixture(scope="module")
def learned(tmp_path_factory):
    """The fixture store after one learn in which every miss still fails."""
    store = learn_store(tmp_path_factory.mktemp("learned"))
    run_learn(store, failing)
    return store


class TestFindingsGates:
    def planted(self, learned, tmp_path, change):
        store = tmp_path / "store"
        shutil.copytree(learned, store)
        (p,) = querylog.findings_files(store)
        objs = jsonl(p)
        change(objs)
        p.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        return querylog.store_problems(store)

    def test_the_learned_store_passes(self, learned):
        assert querylog.store_problems(learned) == []

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
    ])
    def test_findings_gates(self, learned, tmp_path, change, problem):
        problems = self.planted(learned, tmp_path, change)
        assert any(problem in p for p in problems), problems


# --- apply ------------------------------------------------------------------------------------------------------------

E = lambda n: f"55555555-0000-4000-8000-0000000000{n}"  # noqa: E731
ALIAS_Q = "Which zqxlapsor setting picks the backup directory?"  # a word the kb never holds, for LAPS
PARAPHRASE_Q = "How long is the default password?"  # every word known; the pack on HEAD misses the LAPS article


def apply_store(tmp_path, name="store"):
    """The fixture store with a1 a paraphrase an expansion fixes and a2 an unknown word an alias fixes; a3 (its best
    article cannot be reached without breaking the eval set), a4 (a gap) and the fetches as they are."""
    store = learn_store(tmp_path, name)
    (p,) = querylog.run_files(store)
    objs = jsonl(p)
    for o in objs:
        o["question"] = {E("a1"): PARAPHRASE_Q, E("a2"): ALIAS_Q}.get(o.get("id"), o.get("question"))
        if o.get("question") is None:
            o.pop("question")
    p.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in objs), encoding="utf-8", newline="\n")
    return store


KB_DATA = ("kb/public/_retrieval/lookup_eval.csv", "kb/public/_retrieval/doc2query/expansions.csv",
           "_tools/aliases.csv")


@pytest.fixture(scope="module")
def applied(tmp_path_factory):
    """A kb copy and the apply store after `learn` then `apply` in the copy: (home, store, env, apply's output,
    the copy's kb data files before)."""
    base = tmp_path_factory.mktemp("apply")
    home = Path(copy_kb(str(base / "kb")))
    store = apply_store(base)
    env = querylog_env(base / "data", home=str(home), base={**os.environ, "KB_INDEX": str(home / "_cache")})
    before = {f: (home / f).read_bytes() for f in KB_DATA}
    ql = [sys.executable, str(home / "_tools" / "querylog.py")]
    said = []
    for cmd in ("learn", "apply"):
        p = subprocess.run([*ql, cmd, "--store", str(store)], capture_output=True, text=True, encoding="utf-8",
                           env=env, cwd=home, timeout=600)
        assert p.returncode == 0, p.stdout + p.stderr
        said.append(p.stdout.strip())
    return home, store, env, said, before


def kb_rows(home, rel):
    return querylog.csv_rows(Path(home) / rel)


class TestApply:
    def test_eval_rows_come_with_their_fixes(self, applied):
        home, store, env, said, before = applied
        assert said[1].startswith("apply: run=") and "applied=4 rejected=1 no-fix=1" in said[1], said
        m = re.search(r"eval=(\d+)/(\d+) mean-pack=(\d+)->(\d+) offkb-good=(\d+)->(\d+)", said[1])
        passed, n, mean0, mean1, good0, good1 = map(int, m.groups())
        assert passed == n and mean1 <= mean0 and good1 <= good0, said[1]  # the doc2query.md measurements
        added = {rel: kb_rows(home, rel)[len(querylog.csv_rows(Path(KB) / rel)):] for rel in KB_DATA}
        import kbfacts, kbid
        assert added["kb/public/_retrieval/lookup_eval.csv"] == [
            [kbid.eval_id(PARAPHRASE_Q), PARAPHRASE_Q, "windows/laps.md", "good", ""],
            [kbid.eval_id(ALIAS_Q), ALIAS_Q, "windows/laps.md", "good", ""]]
        assert added["_tools/aliases.csv"] == [["zqxlapsor", "laps"]]  # into the existing laps group
        ((key, q),) = added["kb/public/_retrieval/doc2query/expansions.csv"]
        facts = {kbfacts.fact_key(u["text"]) for u in kbfacts.units(LAPS) if u["path"] == LAPS and u["tags"]}
        assert q == PARAPHRASE_Q and key in facts
        p = subprocess.run([sys.executable, str(home / "_tools" / "rag.py"), "eval"], capture_output=True, text=True,
                           encoding="utf-8", env=env, cwd=home, timeout=600)
        assert p.returncode == 0 and f"questions={n} passed={n}" in p.stdout, p.stdout[-400:]
        p = subprocess.run([sys.executable, str(home / "_tools" / "doc2query.py"), "stale"], capture_output=True,
                           text=True, encoding="utf-8", env=env, cwd=home, timeout=600)
        assert p.returncode == 0, p.stdout

    def test_outcomes_are_new_records(self, applied):
        home, store, env, said, before = applied
        (_, learned), (_, outcomes) = findings(store)
        now = by_id(store)
        kinds = {(r["kind"], r.get("entry")): r for r in now.values()}
        for n in ("a1", "a2"):
            assert kinds[("eval", E(n))]["state"] == "applied"
        assert kinds[("expansion", E("a1"))]["state"] == "applied" and kinds[("alias", E("a2"))]["state"] == "applied"
        miss = kinds[("eval", E("a3"))]  # no accepted fix: a gap candidate, the promotion on the finding
        assert (miss["state"], miss["stage"]) == ("no-fix", "candidate-gap")
        assert miss["promotions"] == [{"from": "miss", "to": "candidate-gap", "by": "apply"}]
        assert kinds[("expansion", E("a3"))]["state"] == "rejected" and kinds[("expansion", E("a3"))]["observed"]["gate"]
        assert not [r for r in outcomes if r["kind"] in ("source", "gap")]  # left alone
        assert {r["id"] for r in learned} >= {r["id"] for r in outcomes}  # the learn file is not edited
        assert querylog.store_problems(store) == []

    def test_a_second_apply_changes_nothing(self, applied):
        home, store, env, said, before = applied
        tree_before = tree(store), {f: (home / f).read_bytes() for f in KB_DATA}
        ql = [sys.executable, str(home / "_tools" / "querylog.py")]
        for cmd, want in (("apply", "apply: nothing to apply"), ("learn", "learn: nothing new (findings=10)")):
            p = subprocess.run([*ql, cmd, "--store", str(store)], capture_output=True, text=True, encoding="utf-8",
                               env=env, cwd=home, timeout=600)
            assert (p.returncode, p.stdout.strip()) == (0, want), p.stdout + p.stderr
        assert (tree(store), {f: (home / f).read_bytes() for f in KB_DATA}) == tree_before

    def test_an_eval_row_without_its_fix_fails_the_eval(self, tmp_path):
        import kbid, rag  # planted: the row alone, on this clone, which has no zqxlapsor alias
        f = tmp_path / "lookup_eval.csv"
        f.write_text(f"id,question,expect_paths,expect_verdict,allow_weak\n{kbid.eval_id(ALIAS_Q)},{ALIAS_Q},"
                     "windows/laps.md,good,\n", encoding="utf-8", newline="\n")
        assert rag.run_eval(str(f))["passed"] == 0

    def test_cli_off(self, tmp_path):
        (tmp_path / "data" / "querylog").mkdir(parents=True)
        (tmp_path / "data" / "querylog" / "config.json").write_text('{"mode": "off"}', encoding="utf-8")
        p = subprocess.run([sys.executable, QL, "apply"], capture_output=True, text=True, encoding="utf-8",
                           env=querylog_env(tmp_path / "data"), timeout=120)
        assert (p.returncode, p.stdout) == (0, "apply: logging is off\n")


class StubGate(querylog.Gate):
    """The kb gates on three files in a temporary directory: the eval set, the aliases and the expansions. A new eval
    row passes when `works` and some fix row was written with it; `measure` counts its calls."""

    def __init__(self, d, works=True, unknown=("zqxlapsor", "plomkinator")):
        import kbfacts
        self.files = {"eval": d / "lookup_eval.csv", "aliases": d / "aliases.csv", "expansions": d / "expansions.csv"}
        self.files["eval"].write_text("id,question,expect_paths,expect_verdict,allow_weak\nEV-old,Old?,a/b.md,good,\n",
                                      encoding="utf-8", newline="\n")
        self.files["aliases"].write_text("term,canonical\nsccm,configmgr\nconfigmgr,configmgr\nlaps,laps\n",
                                         encoding="utf-8", newline="\n")
        self.files["expansions"].write_text("key,question\n", encoding="utf-8", newline="\n")
        self.first = {k: p.read_bytes() for k, p in self.files.items()}
        self.works, self.missing, self.measured = works, [kbfacts.stem(w) for w in unknown], 0

    def fresh(self):
        pass

    def pack(self, question):
        return {"verdict": "none", "paths": [], "missing": self.missing}

    def measure(self):
        self.measured += 1
        rows = querylog.csv_rows(self.files["eval"])
        fixed = any(self.files[k].read_bytes() != self.first[k] for k in ("aliases", "expansions"))
        passed = len(rows) if self.works and fixed else 1
        return {"n": len(rows), "passed": passed, "failed": [r[0] for r in rows[passed:]],
                "chars": {r[0]: 100 for r in rows}, "offkb_good": 0}

    def targets(self, article):
        return {"root": "public", **self.files}

    def facts(self, article):
        return [(10, "PasswordLength default 14 characters."), (11, "Password age default 30 days.")]

    def title(self, article):
        return "Windows LAPS: policy"


def unknown_pack(q):
    import kbfacts
    return {"verdict": "none", "paths": [], "missing": [kbfacts.stem(w) for w in ("zqxlapsor", "plomkinator")]}


@pytest.fixture
def stub_store(tmp_path):
    """The fixture store after one learn where every miss fails and zqxlapsor and plomkinator are unknown words:
    eval findings for a1, a2 and a3, an alias for a2, expansions for a1 and a3, a gap and source findings."""
    store = learn_store(tmp_path)
    run_learn(store, unknown_pack)
    return store


def run_apply(store, gate):
    said = []
    rc = querylog.apply(store, gate=gate, kb_commit="0" * 40, out=said.append)
    return rc, said


class TestApplyGates:
    def test_applied_with_stub_gates_then_converges(self, stub_store, tmp_path):
        gate = StubGate(tmp_path)
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=6 rejected=0 no-fix=0" in said[0], said
        assert [r[0] for r in querylog.csv_rows(gate.files["aliases"])][-3:] == ["laps", "zqxlapsor", "plomkinator"]
        first = tree(stub_store), {k: p.read_bytes() for k, p in gate.files.items()}
        n = gate.measured
        assert run_apply(stub_store, gate) == (0, ["apply: nothing to apply"])
        assert (tree(stub_store), {k: p.read_bytes() for k, p in gate.files.items()}) == first
        assert gate.measured == n  # nothing open: no gate ran
        assert querylog.store_problems(stub_store) == []

    def test_an_eval_row_is_never_written_without_its_fix(self, stub_store, tmp_path):
        (p,) = querylog.findings_files(stub_store)  # planted: learn's fix records gone
        objs = jsonl(p)
        objs = [objs[0]] + [o for o in objs[1:] if o["kind"] not in querylog.FIX_KINDS]
        objs[0]["counts"]["findings"] = len(objs) - 1
        p.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        gate = StubGate(tmp_path)
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=0 rejected=0 no-fix=3" in said[0], said
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first
        recs = [r for r in by_id(stub_store).values() if r["kind"] == "eval"]
        assert all(r["observed"]["gate"] == ["no fix finding"] and r["stage"] == "candidate-gap" for r in recs)

    def test_a_fix_that_fails_the_gates_is_put_back(self, stub_store, tmp_path):
        gate = StubGate(tmp_path, works=False)  # planted: no fix makes the new eval row pass
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=0 rejected=3 no-fix=3" in said[0], said
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first  # every file as it was
        assert querylog.store_problems(stub_store) == []

    @pytest.mark.parametrize("unknown,terms,problem", [
        (("sccm",), ["sccm"], "alias sccm: already a term of configmgr"),
        ((), ["password"], "alias password: a word the kb holds"),
    ])
    def test_an_alias_colliding_with_an_existing_term_is_refused(self, tmp_path, unknown, terms, problem):
        store = learn_store(tmp_path)
        run_learn(store, unknown_pack)
        (p,) = querylog.findings_files(store)
        objs = jsonl(p)
        for o in objs[1:]:
            if o["kind"] == "alias":
                o["terms"] = terms  # planted: a term an alias file or the kb already holds
        p.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        gate = StubGate(tmp_path, unknown=unknown)
        run_apply(store, gate)
        assert gate.files["aliases"].read_bytes() == gate.first["aliases"]
        rec = next(r for r in by_id(store).values() if r["kind"] == "alias")
        assert rec["state"] == "rejected" and problem in rec["observed"]["gate"], rec
        miss = by_id(store)[querylog.finding_id("eval", E("a2"))]
        assert (miss["state"], miss["stage"]) == ("no-fix", "candidate-gap")

    def test_alias_problems(self):
        existing = {"sccm": "configmgr", "configmgr": "configmgr", "laps": "laps"}
        assert querylog.alias_problems(["zqx"], "laps", existing, ["zqx"]) == []
        assert querylog.alias_problems(["sccm"], "laps", existing, ["sccm"]) == ["alias sccm: already a term of configmgr"]
        assert querylog.alias_problems(["laps"], "laps", existing, []) == ["alias laps: already a term of laps"]
        assert querylog.alias_problems(["zqx"], "laps", existing, []) == ["alias zqx: a word the kb holds"]
        assert querylog.alias_problems(["zqx"], "sccm", existing, ["zqx"]) == ["alias sccm: a term of configmgr"]

    def test_source_findings_are_never_applied(self, tmp_path):
        store = learn_store(tmp_path)
        run_learn(store, passing)  # every miss passes: only source findings stay open
        assert {r["kind"] for r in by_id(store).values() if r["state"] == "open"} == {"source"}
        gate = StubGate(tmp_path)
        before = tree(store)
        assert run_apply(store, gate) == (0, ["apply: nothing to apply"])
        assert tree(store) == before and gate.measured == 0
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first

    def test_a_red_eval_before_any_change_applies_nothing(self, stub_store, tmp_path):
        gate = StubGate(tmp_path)
        gate.measure = lambda: {"n": 2, "passed": 1, "failed": ["EV-x"], "chars": {}, "offkb_good": 0}
        before = tree(stub_store)
        rc, said = run_apply(stub_store, gate)
        assert rc == 1 and "nothing applied" in said[0] and tree(stub_store) == before
