"""Query log capture tests (kb/_self/querylog.md, Capture; `python3 _tools/tests.py -k querylog`).

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
                    (planted: a synchronous capture hook, a missing event); the shell form runs end to end
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool.
"""
import datetime, http.server, json, os, re, shutil, subprocess, sys, threading, time, uuid
from pathlib import Path

import pytest

import querylog
from conftest import KB, TOOLS, querylog_env

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


class TestHookConfig:
    def test_settings_and_plugin(self):
        assert capture_problems(load(".claude/settings.json"), "CLAUDE_PROJECT_DIR") == []
        assert capture_problems(load(".claude-plugin/plugin.json"), "CLAUDE_PLUGIN_ROOT") == []

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
