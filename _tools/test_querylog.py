"""Query log tests (kb/_self/querylog.md: Capture, Distill, Store, Learn, Apply; `python3 _tools/tests.py -k querylog`).

  TestHookRows      the capture hook (`querylog.py capture`) with recorded hook events on stdin: one row per event
                    with a fresh UUID id; prompt, kb MCP, fetch and Stop rows; fetch rows keep host and path only,
                    Bash and PowerShell only for curl and wget, never command text or results; fetches and answers
                    only in a prompt that used the kb; the row size cap; stale spool files pruned
  TestSwitches      mode `off`, the DISABLED marker and an unreadable config file write nothing (planted: the same
                    events with the default mode write); where rows go in a clone and in a plugin host
  TestToolRows      kb_hook.py, kb_ask.py, fetch.py and census.py write their own rows; the kb: hook's answer is
                    unchanged
  TestNoHooks       every `claude -p` the pipeline starts carries --settings {"disableAllHooks": true} (planted: an
                    argument list without it, or with false), research's call included, and nothing is written
                    unless a hook or a tool runs
  TestHookConfig    the capture hooks are async on UserPromptSubmit, PostToolUse, PostToolUseFailure and Stop in
                    .claude/settings.json and the plugin, through kbpy, with matchers for the kb and fetch tools
                    (planted: a synchronous capture hook, a missing event); the shell form runs end to end; the
                    launcher runs on SessionEnd (synchronous) and SessionStart (async) in both files, and the digest
                    hook on SessionStart, synchronous with its timeout (planted: async, no timeout, missing)
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
  TestLock         a second distill exits on the lock (exit 3) and changes nothing; a stale lock is taken over;
                    of several processes taking the lock at once exactly one gets it
  TestLaunch        SessionEnd marks its session closed; the launcher returns within the 1.5-second budget with its
                    pipes free, and the distill it starts writes its run file after the launcher exited, also when
                    the launcher's process group is killed (POSIX) or its Windows job object closes with
                    kill-on-close (Windows only); SessionStart picks up closed sessions only, and starts nothing when
                    none is closed
  TestStore         the store gates, each with a planted failure: a duplicate id across run files (also through
                    `kbgit.py fix --check`), a missing header or provenance field, run metadata or raw fields in an
                    entry, an identifier in the question, free text in an entry (a summary, an unknown field, text in
                    a closed field), citations that are not path:line or missing beside articles, a count other than
                    entries, dropped, waiting and a positive skipped, a fetch with a
                    query string, a non-public host or command
                    text; `pack` and `search` never return a kb/_querylog/ line; _cache/ stays ignored
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
  TestPushRules     apply --push without git: the host and forge from origin's url (GitLab.com when it names none);
                    only a finished failure is red (planted: each GitLab and GitHub state); the CI check is skipped
                    with a note when glab or gh is not signed in, and the glab and gh calls; the KB-Auto values of a
                    commit's paths, research's articles, sources, conflicts and coverage included (planted: a tool,
                    a kb/_self doc, the answers or anchors are refused); an edited fact line is refused at commit
  TestRetry         a finding recorded apply-failed is not applied again when a later record opens it (planted:
                    FAILED_RETRIES=1 applies it); findings named by --hold are left alone
  TestKbAutoTrailer (marker git) check-trailers reads a commit's KB-Auto trailer (planted: an unknown value, a second
                    line), in a clone of the shared seed; the pushes themselves are test_querylog_e2e.py's scenarios
  TestDeliverRules  distill with a stub push: mode `local` never pushes and deletes the spool rows at once; mode
                    `auto` keeps them while the push fails (planted), distills nothing twice, and spool_delivered
                    deletes only the delivered entries' rows; the leak scan over store files (planted: an address in
                    a field `check` never reads)
  TestHostRules     push_refusal on each refusal shape (GitLab project and protected branch, GitHub denied and GH006,
                    HTTP 403) and on what is no refusal (a generic declined hook, DNS, connection, remote failure);
                    the install url from known_marketplaces.json (git, github) or the marketplace clone's origin;
                    cloud_session from CLAUDE_CODE_REMOTE; `apply --push` in a plugin host runs host_push; the
                    host's apply names its data directory for research
  TestHost*InGit    (marker git) a plugin host in mode `auto` with a fake plugins directory and a local bare remote:
                    the push runs from the managed clone under the data directory and lands on main (TestHostInGit);
                    a remote whose pre-receive hook refuses with GitLab's or GitHub's message writes DISABLED and
                    deletes the spool, and distill then logs nothing (TestHostRefusalsInGit); planted: an unreachable
                    remote at clone and a red gate (TestHostInGit), a generic declined hook and an unreachable remote
                    at push (TestHostNoRefusalInGit) write no DISABLED and keep the spool
  TestCloudInGit    (marker git) a cloud session whose remote takes pushes to the checked-out branch only: the
                    automatic commits land on that branch and main stays; a second run pushes nothing; a detached
                    HEAD is refused
  TestGapStep      a reproduced gap candidate with an article in the pack's lead becomes a dated _gaps.md entry at
                    the end of its topic's section (or a new section), once, the finding promoted candidate-gap ->
                    gap, a none pack's too when its lead holds more than half the key words; off the kb's domains
                    (no lead, a lead no article holds, a stray none lead) it is rejected; a pass now, or a none lead
                    that holds the words the pack lacks, is left to learn, which makes the second an eval finding, so
                    no gap candidate is stranded and the digest's open gaps are what the queue reaches
  TestQueue         the research queue on the gap step's entries (two topics): one item per question, ranked by the
                    logged lookups that asked it, then by age, grouped by topic, the top N; two copies of one store print the
                    same queue; a gap the pack answers now is recorded `fixed-since` and leaves it (learn leaves that
                    record); a second queue after `close --claim` omits the closed gap and changes nothing; planted: a
                    later record reopening a closed gap (check and queue fail), a closed gap whose entry lost its
                    Resolved note, `--claim` without one; a tried note younger than QUEUE_TRIED_DAYS waits and an
                    older one is queued; the close records pass `check`; close refuses what is no open gap
  TestQuoteCheck    quotecheck on a recorded page: entities, no-break spaces, curly quotes, links and emphasis
                    normalized; planted: a quote not on its page, page chrome, over 25 or under 5 words, a page that
                    cannot be fetched; the default fetcher is fetch.py's; the command line
  TestResearchConfig  research is off without the config file and fails closed on a bad one; the daily cap counts
                    runs per day, and mode off or the DISABLED marker turns research off
  TestResearch      with stub gates on a one-article root: facts and source rows added, a disagreement to
                    _conflicts.md, the finding promoted gap -> candidate-fact -> claim; planted: a quote not on its
                    page, research editing an existing fact line, a red check.py (every file put back); at most the
                    runs left; a failed call writes nothing; a reply that is not the JSON; candidate and edit gates
  TestResearchInKbCopy  in a kb copy, learn then apply with research off (the gap entry only), then on at one run a day
                    (recorded reply and page): a fact, a source row and a conflict entry, check.py errors=0 and
                    build_index --check after it, and a second run changes nothing
  TestDigest        two copies of one fixture store give byte-identical `digest` output, equal to the expected text;
                    the default week is the newest entry's; findings states stop at the week's Sunday; an empty or
                    missing store and a bad week; distill sums a fetch's result characters
  TestDigestHook    the first SessionStart of an ISO week shows last week's digest once as a systemMessage; mode off,
                    the DISABLED marker and an empty week show nothing; planted: over DIGEST_BUDGET_S shows nothing
                    and is not tried again that week; the hook command prints at most one JSON line and exits 0
  TestStatus        open source findings ranked by result characters, open querylog/ merge requests (glab and gh
                    stubs: GitLab MR API, gh pr list) and KB-Auto reverts; not signed in, a failed call and no origin
                    are skipped with a note; the revert trailer read from a real git log (marker git)
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The git scenarios clone the run's shared seed
(conftest.kb_seed), and a worktree's `querylog.py check` runs in the test process (run_here).
"""
import contextlib, datetime, getpass, http.server, io, json, os, re, shutil, signal, socket, subprocess, sys, threading, time, uuid
from pathlib import Path

import pytest

import querylog, ql_apply, ql_base, ql_capture, ql_deliver, ql_distill, ql_learn, ql_report, ql_research, ql_store
from conftest import GIT, KB, TOOLS, D, P, Repo, copy_kb, git_env, querylog_env

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


def tool(name, args, response=None, pid="p1", ok=True, error=None, sid=SID):
    ev = {"hook_event_name": "PostToolUse" if ok else "PostToolUseFailure", "session_id": sid, "prompt_id": pid,
          "tool_name": name, "tool_input": args, "tool_use_id": "toolu_01"}
    if ok:
        ev["tool_response"] = response
    else:
        ev["error"] = error or ""
    return ev


def stop(answer, pid="p1", sid=SID):
    return {"hook_event_name": "Stop", "session_id": sid, "prompt_id": pid, "stop_hook_active": False,
            "last_assistant_message": answer}


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


class TestSwitches:
    EVENTS = [prompt("kb: laps"), tool("mcp__kb__kb_pack", {"question": "laps"}, PACK),
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


@contextlib.contextmanager
def serve():
    """A local HTTP server for fetch.py and census.py requests: /ok (200, `hello`), /empty (200, no body), /missing
    (404), anything else 500. Yields its base url."""
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
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


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
    rc = ql_distill.distill(qdir=qdir, cfg=Path(qdir) / "config.json", haiku=haiku, now_dt=now, run_id=run_id,
                            kb_commit="0" * 40, out=said.append)
    return rc, said


def store_files(qdir):
    return sorted((Path(qdir) / "store").rglob("*.jsonl"))


def jsonl(path):
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


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
LAPS = "public/windows/laps.md"


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


def session_start(sid="new-session"):
    return {"hook_event_name": "SessionStart", "session_id": sid, "source": "startup"}


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


# ---------------------------------------------------------------- learn (Query log item 5)

LEARN_STORE = FIXTURES / "store"
LAPS = "public/windows/laps.md"
MISS = {f"55555555-0000-4000-8000-0000000000{n}" for n in ("a1", "a2", "a3", "a4")}
ANSWERED = "55555555-0000-4000-8000-0000000000a5"


UNSTAGED = "docs.unstaged.example.com"  # the fixture store's level-0 host: no real registry or routes row serves it


def learn_store(tmp_path, name="store"):
    """A copy of the fixture store: one run file with judged misses, an answered lookup and fetch.py requests."""
    dst = Path(tmp_path) / name
    shutil.copytree(LEARN_STORE, dst)
    return dst


def run_learn(store, pack, **kw):
    said = []
    rc = ql_learn.learn(store, pack=pack, kb_commit="0" * 40, out=said.append, **kw)
    return rc, said


def findings(store):
    """[(file, [records])] of the store's findings files, oldest first."""
    return [(p, jsonl(p)[1:]) for p in ql_store.findings_files(store)]


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
            seen[q] = ql_learn.default_pack(q)
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


FN = "55555555-0000-4000-8000-0000000000{}"
LEARN_URL = "https://learn.microsoft.com/en-us/windows-server/identity/laps/laps-overview"
HOOKS = "public/claude/hooks.md"


def none_entry(n, question, *fetches, **extra):
    """A stored lookup with verdict none whose session fetched `fetches` (host, path, outcome)."""
    return {"id": FN.format(n), "surface": "prompt", "day": "2026-09-27", "tools": ["kb_pack"], "question": question,
            "verdict": "none", "articles": [], "judged": "missed",
            "fetches": [{"tool": "WebFetch", "host": h, "path": p, "outcome": o, "n": 1} for h, p, o in fetches],
            **extra}


def plant_entries(store, *entries):
    """Append `entries` to the store's run file and count them in its header."""
    run = ql_store.run_files(store)[0]
    lines = run.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["counts"]["entries"] += len(entries)
    lines = [json.dumps(header, separators=(",", ":"))] + lines[1:] + [json.dumps(e) for e in entries]
    run.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


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
        assert ql_learn.trigger_problems() == []
        doc = ql_learn.WEB_SOURCES.read_text(encoding="utf-8")
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
        assert ql_learn.registry_problems() == []
        import provider
        rows = provider._read(provider.SHARED)
        planted = rows + [{"provider": "vendor", "match": "docs.vendor.example.org/"}]
        assert ql_learn.registry_problems(planted) == [
            "provider vendor: docs.vendor.example.org has a registry row but no row in the routes table"]
        doc = ql_learn.WEB_SOURCES.read_text(encoding="utf-8")
        routes = ql_learn.routes_table(doc.replace("| `learn.microsoft.com` |", "| Learn |"))
        assert any("learn.microsoft.com" in p for p in ql_learn.registry_problems(rows, routes))
        team = [{"provider": "team-wiki", "match": "wiki.corp.example.com/", "_root": "team"}]
        assert ql_learn.registry_problems(rows + team) == []  # a root's own providers are its team's

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


# --- apply ------------------------------------------------------------------------------------------------------------

E = lambda n: f"55555555-0000-4000-8000-0000000000{n}"  # noqa: E731
ALIAS_Q = "Which zqxlapsor setting picks the backup directory?"  # a word the kb never holds, for LAPS
PARAPHRASE_Q = "How long is the default password?"  # every word known; the pack on HEAD misses the LAPS article


def apply_store(tmp_path, name="store"):
    """The fixture store with a1 a paraphrase an expansion fixes and a2 an unknown word an alias fixes; a3 (its best
    article cannot be reached without breaking the eval set), a4 (a gap) and the fetches as they are."""
    store = learn_store(tmp_path, name)
    (p,) = ql_store.run_files(store)
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
    return ql_apply.csv_rows(Path(home) / rel)


class TestApply:
    def test_eval_rows_come_with_their_fixes(self, applied):
        home, store, env, said, before = applied
        assert said[1].startswith("apply: run=") and "applied=4 rejected=2 no-fix=1" in said[1], said  # a4 off the kb
        m = re.search(r"eval=(\d+)/(\d+) mean-pack=(\d+)->(\d+) offkb-good=(\d+)->(\d+)", said[1])
        passed, n, mean0, mean1, good0, good1 = map(int, m.groups())
        assert passed == n and mean1 <= mean0 and good1 <= good0, said[1]  # the doc2query.md measurements
        added = {rel: kb_rows(home, rel)[len(ql_apply.csv_rows(Path(KB) / rel)):] for rel in KB_DATA}
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
        assert not [r for r in outcomes if r["kind"] == "source"]  # left alone
        gap = kinds[("gap", E("a4"))]  # VMware Horizon: a none pack whose lead holds half its key words or fewer
        assert (gap["state"], gap["stage"], gap["observed"]["gate"]) == ("rejected", "candidate-gap",
                                                                          ["off the kb's domains"])
        assert {r["id"] for r in learned} >= {r["id"] for r in outcomes}  # the learn file is not edited
        assert ql_store.store_problems(store) == []

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


class StubGate(ql_apply.Gate):
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
        rows = ql_apply.csv_rows(self.files["eval"])
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
    rc = ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=said.append)
    return rc, said


class TestApplyGates:
    def test_applied_with_stub_gates_then_converges(self, stub_store, tmp_path):
        gate = StubGate(tmp_path)
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=6 rejected=1 no-fix=0" in said[0], said  # the gap: off the kb's domains
        assert [r[0] for r in ql_apply.csv_rows(gate.files["aliases"])][-3:] == ["laps", "zqxlapsor", "plomkinator"]
        first = tree(stub_store), {k: p.read_bytes() for k, p in gate.files.items()}
        n = gate.measured
        assert run_apply(stub_store, gate) == (0, ["apply: nothing to apply"])
        assert (tree(stub_store), {k: p.read_bytes() for k, p in gate.files.items()}) == first
        assert gate.measured == n  # nothing open: no gate ran
        assert ql_store.store_problems(stub_store) == []

    def test_an_eval_row_is_never_written_without_its_fix(self, stub_store, tmp_path):
        (p,) = ql_store.findings_files(stub_store)  # planted: learn's fix records gone
        objs = jsonl(p)
        objs = [objs[0]] + [o for o in objs[1:] if o["kind"] not in ql_store.FIX_KINDS]
        objs[0]["counts"]["findings"] = len(objs) - 1
        p.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        gate = StubGate(tmp_path)
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=0 rejected=1 no-fix=3" in said[0], said  # the gap: off the kb's domains
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first
        recs = [r for r in by_id(stub_store).values() if r["kind"] == "eval"]
        assert all(r["observed"]["gate"] == ["no fix finding"] and r["stage"] == "candidate-gap" for r in recs)

    def test_a_fix_that_fails_the_gates_is_put_back(self, stub_store, tmp_path):
        gate = StubGate(tmp_path, works=False)  # planted: no fix makes the new eval row pass
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=0 rejected=4 no-fix=3" in said[0], said  # two fixes and one alias, the gap
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first  # every file as it was
        assert ql_store.store_problems(stub_store) == []

    @pytest.mark.parametrize("unknown,terms,problem", [
        (("sccm",), ["sccm"], "alias sccm: already a term of configmgr"),
        ((), ["password"], "alias password: a word the kb holds"),
    ])
    def test_an_alias_colliding_with_an_existing_term_is_refused(self, tmp_path, unknown, terms, problem):
        store = learn_store(tmp_path)
        run_learn(store, unknown_pack)
        (p,) = ql_store.findings_files(store)
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
        miss = by_id(store)[ql_store.finding_id("eval", E("a2"))]
        assert (miss["state"], miss["stage"]) == ("no-fix", "candidate-gap")

    def test_alias_problems(self):
        existing = {"sccm": "configmgr", "configmgr": "configmgr", "laps": "laps"}
        assert ql_apply.alias_problems(["zqx"], "laps", existing, ["zqx"]) == []
        assert ql_apply.alias_problems(["sccm"], "laps", existing, ["sccm"]) == ["alias sccm: already a term of configmgr"]
        assert ql_apply.alias_problems(["laps"], "laps", existing, []) == ["alias laps: already a term of laps"]
        assert ql_apply.alias_problems(["zqx"], "laps", existing, []) == ["alias zqx: a word the kb holds"]
        assert ql_apply.alias_problems(["zqx"], "sccm", existing, ["zqx"]) == ["alias sccm: a term of configmgr"]

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


# --- apply --push (Query log item 7) --------------------------------------------------------------------------------

class TestPushRules:
    @pytest.mark.parametrize("url,want", [
        ("git@gitlab.com:grp/proj.git", ("gitlab", "gitlab.com", "grp/proj")),
        ("https://gitlab.corp.example.com:8443/a/b/c.git", ("gitlab", "gitlab.corp.example.com", "a/b/c")),
        ("ssh://git@gitlab.corp.example.com:2222/a/b.git", ("gitlab", "gitlab.corp.example.com", "a/b")),
        ("https://github.com/o/r.git", ("github", "github.com", "o/r")),
        ("git@github.com:o/r.git", ("github", "github.com", "o/r")),
        ("/tmp/x/remote.git", ("gitlab", ql_deliver.FALLBACK_GITLAB_HOST, "x/remote")),
        ("C:\\work\\x\\remote.git", ("gitlab", ql_deliver.FALLBACK_GITLAB_HOST, "x/remote")),
        ("file:///srv/x/remote.git", ("gitlab", ql_deliver.FALLBACK_GITLAB_HOST, "x/remote")),
    ])
    def test_the_host_comes_from_origins_url(self, url, want):
        assert ql_deliver.origin_forge(url) == want

    @pytest.mark.parametrize("status,want", [
        ("failed", "red"), ("success", "ok"), ("manual", "ok"), ("skipped", "ok"), ("canceled", "ok"),
        ("created", "pending"), ("pending", "pending"), ("running", "pending"), ("waiting_for_resource", "pending"),
        ("preparing", "pending"), ("scheduled", "pending"), ("canceling", "pending"),
    ])
    def test_only_a_finished_failure_is_red_on_gitlab(self, status, want):
        assert ql_deliver.pipeline_verdict("gitlab", [status]) == want

    @pytest.mark.parametrize("runs,want", [
        ([("completed", "failure")], "red"), ([("completed", "timed_out")], "red"),
        ([("completed", "success"), ("completed", "startup_failure")], "red"),
        ([("completed", "cancelled")], "ok"), ([("completed", "skipped")], "ok"), ([("completed", "success")], "ok"),
        ([("in_progress", None)], "pending"), ([("queued", None), ("completed", "success")], "pending"),
    ])
    def test_only_a_finished_failure_is_red_on_github(self, runs, want):
        assert ql_deliver.pipeline_verdict("github", runs) == want

    def test_the_ci_check_is_skipped_when_no_cli_is_signed_in(self):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            return 1, "", "not logged in"
        verdict, detail = ql_deliver.ci_status("git@gitlab.corp.example.com:grp/proj.git", "a" * 40, run)
        assert verdict == "skip" and "glab is not signed in to gitlab.corp.example.com" in detail
        assert calls == [["glab", "auth", "status", "--hostname", "gitlab.corp.example.com"]]  # no API call

    def test_glab_and_gh_calls(self):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            if argv[1:3] == ["auth", "status"]:
                return 0, "", ""
            if argv[0] == "gh":
                return 0, json.dumps([{"status": "completed", "conclusion": "failure"}]), ""
            if "/jobs?" in argv[-1]:
                return 0, json.dumps([{"id": 9, "name": "kb-trailers", "status": "success"},
                                      {"id": 8, "name": "kb-tests", "status": "success"},
                                      {"id": 10, "name": "kb-tests-windows", "status": "manual"}]), ""
            return 0, json.dumps([{"id": 7, "status": "manual"}]), ""
        sha = "b" * 40
        assert ql_deliver.ci_status("git@gitlab.corp.example.com:grp/sub/proj.git", sha, run)[0] == "ok"
        assert calls[-2:] == [["glab", "api", "--hostname", "gitlab.corp.example.com",
                               f"projects/grp%2Fsub%2Fproj/pipelines?sha={sha}&per_page={ql_deliver.SHA_PIPELINES}"],
                              ["glab", "api", "--hostname", "gitlab.corp.example.com",
                               "projects/grp%2Fsub%2Fproj/pipelines/7/jobs?per_page=100"]]
        assert ql_deliver.ci_status("https://github.com/o/r.git", sha, run)[0] == "red"
        assert calls[-1][:6] == ["gh", "run", "list", "--commit", sha, "-R"] and calls[-1][6] == "github.com/o/r"

    def test_a_failed_or_empty_api_answer(self):
        def run(argv, cwd=None):
            return (0, "", "") if argv[1] == "auth" else (0, "[]", "")
        assert ql_deliver.ci_status("/x/y.git", "c" * 40, run)[0] == "none"

        def broken(argv, cwd=None):
            return (0, "", "") if argv[1] == "auth" else (1, "", "HTTP 404")
        assert ql_deliver.ci_status("/x/y.git", "c" * 40, broken) == ("skip", "glab api failed (HTTP 404)")


QUOTA = {"status": "failed", "failure_reason": "ci_quota_exceeded", "allow_failure": True}
PASSED = [{"name": "kb-trailers", "status": "success"}, {"name": "kb-tests", "status": "success"}]


DEFAULT_GATE = ql_deliver.GATE_JOBS


class TestNoGateJobs:
    """Every job is manual, so no job is a gate by default: a pipeline is never `unverified` for a job nobody
    started, and a job whose script ran and failed still makes it red."""

    def test_no_job_is_a_gate_by_default(self):
        assert DEFAULT_GATE == ()

    @pytest.mark.parametrize("jobs", [
        [{"name": "kb-tests", "status": "manual"}, {"name": "kb-trailers", "status": "manual"}],
        [{"name": "kb-tests", **QUOTA}, {"name": "kb-trailers", "status": "skipped"}],
        [{"name": "kb-tests", "status": "canceled"}], [],
    ])
    def test_a_pipeline_whose_jobs_never_ran_is_ok(self, jobs):
        assert ql_deliver.job_verdict(jobs) == ("ok", [], [])

    def test_a_failed_script_is_red_and_an_unreadable_list_is_unverified(self):
        failed = {"name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}
        assert ql_deliver.job_verdict([failed, {"name": "kb-tests", "status": "manual"}]) == (
            "red", ["kb-tests-windows"], [])
        assert ql_deliver.job_verdict(None)[0] == "unverified"

    @pytest.mark.parametrize("reason", ["job_execution_timeout", "stuck_or_timeout_failure"])
    def test_a_timed_out_or_stuck_job_is_red(self, reason):
        job = {"name": "kb-tests-windows", "status": "failed", "failure_reason": reason}
        assert ql_deliver.job_ran(job)
        assert ql_deliver.job_verdict([job]) == ("red", ["kb-tests-windows"], [])

    @pytest.mark.parametrize("job,ran", [
        ({"status": "manual"}, False), ({"status": "skipped"}, False), ({"status": "created"}, False),
        ({"status": "canceled"}, False), ({**QUOTA}, False), ({"status": "canceled", "started_at": "t"}, True),
        ({"status": "success"}, True), ({"status": "running"}, True),
        ({"status": "failed", "failure_reason": "script_failure"}, True),
    ])
    def test_job_ran(self, job, ran):
        assert ql_deliver.job_ran(job) is ran

    def test_the_revert_check_reads_the_newest_pipeline_of_the_commit_where_a_job_ran(self):
        """Planted: a red started pipeline of the commit, then newer ones where no job ran."""
        jobs = {9: [{"name": "kb-tests", "status": "manual"}], 8: [],
                7: [{"name": "kb-tests", "status": "failed", "failure_reason": "script_failure"}]}

        def run(argv, cwd=None):
            if argv[1:3] == ["auth", "status"]:
                return 0, "", ""
            if "/jobs?" in argv[-1]:
                return 0, json.dumps(jobs[int(argv[-1].split("/pipelines/")[1].split("/")[0])]), ""
            return 0, json.dumps([{"id": i, "status": "manual"} for i in (9, 8, 7)]), ""
        verdict, detail, pipe = ql_deliver.ci_pipeline("https://gitlab.example.com/team/kb.git", "d" * 40, run)
        assert (verdict, pipe["id"]) == ("red", 7) and "the newest where a job ran" in detail, detail
        jobs[7] = [{"name": "kb-tests", "status": "manual"}]  # no job ran in any: the newest is read, and is ok
        verdict, _, pipe = ql_deliver.ci_pipeline("https://gitlab.example.com/team/kb.git", "d" * 40, run)
        assert (verdict, pipe["id"]) == ("ok", 9)


@pytest.fixture
def gate_jobs(monkeypatch):
    """The two jobs that were once gates, named again, for the tests of the gate mechanism."""
    monkeypatch.setattr(ql_deliver, "GATE_JOBS", ("kb-tests", "kb-trailers"))


@pytest.mark.usefixtures("gate_jobs")
class TestJobVerdict:
    """A GitLab pipeline read by its jobs (recorded job lists, no network), with GATE_JOBS named: every job is manual
    with allow_failure, so the pipeline's status says success whatever the jobs did."""

    @pytest.mark.parametrize("jobs,want", [
        (PASSED, ("ok", [], [])),
        (PASSED + [{"name": "kb-tests-windows", "status": "manual"}, {"name": "tool-stress", **QUOTA},
                   {"name": "kb-tests-floor", "status": "skipped"}], ("ok", [], [])),
        ([{"name": "kb-trailers", **QUOTA}, {"name": "kb-tests", **QUOTA}, {"name": "kb-tests-floor", **QUOTA}],
         ("unverified", [], ["kb-tests failed (ci_quota_exceeded)", "kb-trailers failed (ci_quota_exceeded)"])),
        ([{"name": "kb-trailers", "status": "manual"}, {"name": "kb-tests", "status": "manual"}],
         ("unverified", [], ["kb-tests manual", "kb-trailers manual"])),
        ([{"name": "kb-trailers", "status": "success"}, {"name": "kb-tests", "status": "skipped"}],
         ("unverified", [], ["kb-tests skipped"])),
        ([{"name": "kb-trailers", "status": "canceled"}, {"name": "kb-tests", "status": "success"}],
         ("unverified", [], ["kb-trailers canceled"])),
        ([{"name": "kb-tests", "status": "failed"}, {"name": "kb-trailers", "status": "success"}],
         ("unverified", [], ["kb-tests failed"])),  # no failure_reason: not shown to have run
        ([{"name": "kb-tests", "status": "success"}], ("unverified", [], ["kb-trailers not in the pipeline"])),
        ([], ("unverified", [], ["kb-tests not in the pipeline", "kb-trailers not in the pipeline"])),
        (None, ("unverified", [], ["the pipeline's jobs could not be read"])),
        ([{"name": "kb-tests", "status": "running"}, {"name": "kb-trailers", "status": "manual"}],
         ("pending", [], ["kb-tests running", "kb-trailers manual"])),
        ([{"name": "kb-tests", "status": "failed", "failure_reason": "script_failure", "allow_failure": True},
          {"name": "kb-trailers", "status": "success"}], ("red", ["kb-tests"], ["kb-tests failed (script_failure)"])),
        (PASSED + [{"name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}],
         ("red", ["kb-tests-windows"], [])),
        ([{"name": "kb-tests", "status": "success"}, {"name": "kb-tests", **QUOTA}, {"name": "kb-trailers", "status": "success"}],
         ("ok", [], [])),  # the newest entry of a name counts (the API lists newest first)
    ])
    def test_gate_jobs_decide(self, jobs, want):
        assert ql_deliver.job_verdict(jobs) == want

    def run(self, pipeline_status, jobs):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            if argv[1:3] == ["auth", "status"]:
                return 0, "", ""
            if "/jobs?" in argv[-1]:
                return (0, json.dumps(jobs), "") if jobs is not None else (1, "", "HTTP 500")
            return 0, json.dumps([{"id": 7, "status": pipeline_status}]), ""
        return ql_deliver.ci_pipeline("git@gitlab.corp.example.com:grp/proj.git", "d" * 40, run), calls

    def test_a_success_pipeline_whose_gate_never_ran_is_unverified(self):
        jobs = [{"name": "kb-tests-windows", "status": "manual"}, {"name": "kb-trailers", **QUOTA},
                {"name": "tool-stress", **QUOTA}, {"name": "kb-tests-floor", **QUOTA}, {"name": "kb-tests", **QUOTA}]
        (verdict, detail, pipe), _ = self.run("success", jobs)
        assert verdict == "unverified" and pipe["id"] == 7, detail
        assert detail.endswith("success; kb-tests failed (ci_quota_exceeded), kb-trailers failed (ci_quota_exceeded)")
        assert self.run("manual", [{"name": "kb-tests", "status": "manual"}])[0][0] == "unverified"
        assert self.run("success", None)[0][0] == "unverified"
        assert self.run("success", PASSED)[0][0] == "ok"

    def test_a_failed_script_under_allow_failure_is_red(self):
        (verdict, detail, _), _ = self.run("success", PASSED + [{"name": "tool-stress", "status": "failed",
                                                                  "failure_reason": "script_failure"}])
        assert verdict == "red" and detail.endswith("script failed in tool-stress"), detail

    @pytest.mark.parametrize("status,want", [("failed", "red"), ("running", "pending"), ("pending", "pending")])
    def test_the_pipeline_status_still_decides_a_failure_or_an_unfinished_run(self, status, want):
        (verdict, _, _), calls = self.run(status, None)
        assert verdict == want and not any("/jobs?" in c[-1] for c in calls)  # no job list needed

    def test_the_revert_fingerprint_names_a_script_that_ran(self):
        import backlog
        jobs = [{"id": 1, "name": "kb-lint", **QUOTA},
                {"id": 2, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure"}]
        run = fingerprint_forge(jobs, {2: "FAILED _tools/test_x.py::test_a - assert 1 == 2\n"})
        failure, fp = ql_deliver.pipeline_failure("https://gitlab.example.com/team/kb.git", {"id": 3}, run)
        assert fp == backlog.failure_fingerprint("kb-tests", "_tools/test_x.py::test_a"), failure

    def test_auto_kinds(self):
        import kbgit
        paths = ["kb/_querylog/findings/2026-09/x.jsonl", "_tools/aliases.csv", "kb/public/_retrieval/lookup_eval.csv",
                 "kb/public/_retrieval/doc2query/expansions.csv", "kb/team/_retrieval/aliases.csv", "kb/public/_gaps.md"]
        assert ql_deliver.auto_kinds(paths) == ["alias", "eval", "expansion", "gap", "querylog"]
        assert set(ql_deliver.auto_kinds(paths)) <= set(kbgit.AUTO_VALUES)
        research = ["kb/public/windows/laps.md", "kb/public/_sources.csv", "kb/public/_conflicts.md",
                    "kb/public/_coverage.csv", "kb/public/_coverage.md", "kb/team/infra/dns/zones.md"]
        assert ql_deliver.auto_kinds(paths + research) == ["alias", "eval", "expansion", "gap", "querylog", "research"]
        assert ql_deliver.auto_kinds(["kb/_self/backlog/BG-abcdefgh.json"]) == ["revert"]  # a revert's bug item
        for p in ("_tools/kbfacts.py", "kb/_self/tools.md", "kb/_self/backlog.md", "kb/_self/backlog/x/y.json", "kb/public/_answers.md", "kb/public/_anchors.csv",
                  "README.md", "kb/public/_retrieval/signals.csv", "kb/public/_snapshots/S100.txt"):
            with pytest.raises(ValueError, match=re.escape(p)):  # planted: a path apply never writes
                ql_deliver.auto_kinds(paths + [p])

    def test_an_edited_line_is_refused_at_commit(self, tmp_path):
        """apply --push checks the worktree's change against HEAD: added lines pass, an edited fact line, ledger
        entry or source row is refused (planted)."""
        old = "---\ntopic: a/b\n---\n## Facts\n- One fact. [DOC S100]\n"
        f = tmp_path / ql_deliver.WORKTREE_NAME / "kb" / "public" / "a" / "b.md"
        f.parent.mkdir(parents=True)

        def run(argv, cwd=None):
            if argv[:3] == ["git", "cat-file", "-e"]:
                return 0, "", ""  # the file is at HEAD
            return (0, old, "") if argv[:3] == ["git", "cat-file", "blob"] else (1, "", "")
        p = ql_deliver.Pusher(tmp_path, tmp_path, run, None, print)
        f.write_text(old + "- Two facts. [DOC S101]\n", encoding="utf-8", newline="\n")
        assert p.edited(["kb/public/a/b.md"]) == []
        f.write_text(old.replace("One fact.", "One fact, edited."), encoding="utf-8", newline="\n")
        (why,) = p.edited(["kb/public/a/b.md"])
        assert "removes or edits an existing fact line" in why


def reopen(store, ids):
    """Planted: a later findings file that records `ids` open again, as a parallel learn in another clone could."""
    last = ql_store.finding_states(store)
    recs = [{**{k: v for k, v in last[i].items() if k != "observed"}, "state": "open"} for i in ids]
    ql_store.write_findings(store, ql_store.store_entries(store), recs, ql_store.LEARN_STATES, "0" * 40)


class TestRetry:
    def test_a_failed_finding_is_never_applied_again(self, stub_store, tmp_path, monkeypatch):
        (tmp_path / "a").mkdir()
        assert run_apply(stub_store, StubGate(tmp_path / "a"))[0] == 0
        applied = {i: r for i, r in by_id(stub_store).items() if r["state"] == "applied"}
        assert len(applied) == 6
        failed = [{**{k: v for k, v in r.items() if k != "observed"}, "state": ql_store.APPLY_FAILED,
                   "observed": {"ci": "failed", "commit": "0" * 12}} for r in applied.values()]
        ql_store.write_findings(stub_store, ql_store.store_entries(stub_store), failed, (ql_store.APPLY_FAILED,),
                                "0" * 40)
        assert ql_store.store_problems(stub_store) == []
        reopen(stub_store, list(applied))
        (tmp_path / "b").mkdir()
        gate = StubGate(tmp_path / "b")
        assert run_apply(stub_store, gate) == (0, ["apply: nothing to apply"])
        assert gate.measured == 0 and {k: p.read_bytes() for k, p in gate.files.items()} == gate.first
        monkeypatch.setattr(ql_apply, "FAILED_RETRIES", 1)  # planted: one retry allowed, and it is taken
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=6" in said[0], said

    def test_held_findings_are_left_alone(self, stub_store, tmp_path):
        gate = StubGate(tmp_path)
        hold = {i for i, r in by_id(stub_store).items() if r["kind"] in ("eval", "gap") + ql_store.FIX_KINDS}
        said = []
        assert ql_apply.apply(stub_store, gate=gate, kb_commit="0" * 40, out=said.append, hold=hold) == 0
        assert said == ["apply: nothing to apply"] and gate.measured == 0

    def test_the_command_line(self, stub_store, capsys):
        # the gap held too: this apply runs on the clone's own kb, which it must not write
        hold = sorted(i for i, r in by_id(stub_store).items() if r["kind"] in ("eval", "gap") + ql_store.FIX_KINDS)
        argv = ["apply", "--store", str(stub_store)]
        for i in hold:
            argv += ["--hold", i]
        assert querylog.main(argv) == 0 and capsys.readouterr().out.strip() == "apply: nothing to apply"
        assert querylog.main(["apply", "--push", "--store", str(stub_store)]) == 2  # the push has its own store


class RepoGate(ql_apply.Gate):
    """apply's gate on a worktree: the clone's real alias terms, facts and titles, a pack that misses, and a measure
    under which every candidate passes (the gates themselves are tested above); the files written are the
    worktree's."""

    def __init__(self, wt):
        self.wt = Path(wt)

    def fresh(self):
        pass

    def pack(self, question):
        return unknown_pack(question)

    def targets(self, article):
        return {"root": "public", "eval": self.wt / D("lookup_eval.csv"), "aliases": self.wt / "_tools" / "aliases.csv",
                "expansions": self.wt / D("doc2query/expansions.csv")}

    def measure(self):
        rows = ql_apply.csv_rows(self.targets(None)["eval"])
        return {"n": len(rows), "passed": len(rows), "failed": [], "chars": {r[0]: 100 for r in rows}, "offkb_good": 0}


def repo_step(wt, store, hold, out):
    return ql_apply.apply(store, gate=RepoGate(wt), kb_commit="0" * 40, out=out, hold=hold)


def signed_out(argv):
    return 1, "", "not logged in"


def run_here(argv, cwd=None, env=None):
    """ql_base.run_cmd, but a worktree's `querylog.py check DIR` runs in this process: the same store gates
    (ql_store.check on that directory), with the public root's known ids read once per process instead of once per
    push. The command line of `check` is tested on its own (TestStore, TestSpoolFormats)."""
    if len(argv) == 4 and Path(argv[1]).name == "querylog.py" and argv[2] == "check":
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ql_store.check(argv[3])
        return code, out.getvalue(), ""
    return ql_base.run_cmd(argv, cwd=cwd, env=env)


def pipeline(status, jobs=()):
    """A signed-in glab that answers one pipeline of `status` for any commit, and `jobs` as its job list."""
    def ci(argv):
        if argv[1:3] == ["auth", "status"]:
            return 0, "", "Logged in"
        if "/jobs?" in argv[-1]:
            return 0, json.dumps(list(jobs)), ""
        return 0, json.dumps([{"id": 1, "status": status}]), ""
    return ci


PUSH_OPTIONS_HOOK = """#!/bin/sh
i=0
while [ "$i" -lt "${GIT_PUSH_OPTION_COUNT:-0}" ]; do
  eval "printf '%s\\n' \\"\\$GIT_PUSH_OPTION_$i\\"" >> push-options.txt
  i=$((i+1))
done
"""


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestKbAutoTrailer:
    """kbgit.py check-trailers on a commit's KB-Auto trailer, in a clone of the shared seed (conftest.kb_seed)."""

    @pytest.fixture(scope="class")
    @classmethod
    def clone(cls, kb_seed, tmp_path_factory):
        c = Repo(tmp_path_factory.mktemp("ql-trailer") / "a")
        Repo(Path(c.path).parent).git("clone", "-q", str(kb_seed[0]), c.path)
        return c, kb_seed[1]

    @pytest.mark.parametrize("value,ok", [("eval", True), ("alias, eval", True), ("bogus", False),
                                          ("eval\nKB-Auto: alias", False)])
    def test_check_trailers_reads_kb_auto(self, clone, value, ok):
        c, base = clone
        c.git("checkout", "-q", "-B", "t-trailer", base)
        c.append("README.md", "x\n")
        c.git("commit", "-q", "-a", "--no-verify", "-m", "chore: x", "-m", f"KB-Auto: {value}")
        p = c.kbgit("check-trailers", "HEAD")
        c.git("checkout", "-q", "main")
        assert (p.returncode == 0) is ok, p.stdout
        if not ok:
            assert "KB-Auto: has " in p.stdout and "expected once, of querylog|eval|" in p.stdout, p.stdout


# --- the local store's run files and findings delivered to origin/main -------------------------------------------

def auto_config(qdir, mode="auto"):
    cfg = Path(qdir) / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"mode": mode}), encoding="utf-8", newline="\n")
    return cfg


def spool_names(qdir):
    sp = Path(qdir) / "spool"
    return sorted(p.name for p in sp.iterdir()) if sp.is_dir() else []


CLOSED = sorted([f"{S_ENDED}.jsonl", f"{S_ENDED}.end", f"{S_IDLE}.jsonl", "tools-2026-09-27.jsonl"])


class TestDeliverRules:
    """distill's spool rules for the push of mode `auto`, with a stub push (no git)."""

    def distill(self, q, mode, calls, rc=0):
        def deliver(qdir, out):
            calls.append(spool_names(qdir))
            return rc
        said = []
        got = ql_distill.distill(qdir=q, cfg=auto_config(q, mode), haiku=ql_base.Replay(FIXTURES / "haiku.json"),
                                 now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40, out=said.append, deliver=deliver)
        return got, said

    def test_local_never_pushes_and_deletes_the_rows_at_once(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        calls = []
        rc, said = self.distill(q, "local", calls)
        assert rc == 0 and calls == [] and said == [f"distill: run={RUN_ID} entries=6 dropped=1 waiting=0"], said
        assert spool_names(q) == [f"{S_OPEN}.jsonl"]

    def test_auto_keeps_the_rows_until_their_run_file_is_on_main(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        calls = []
        rc, said = self.distill(q, "auto", calls, rc=1)  # planted: the push fails
        assert rc == 1 and len(calls) == 1, said
        assert "distill: the spool keeps the rows of 6 entries until their run file is on origin/main" in said
        assert set(CLOSED) <= set(calls[0]) and set(CLOSED) <= set(spool_names(q))  # nothing deleted
        (run,) = store_files(q)
        before = run.read_bytes()
        rc, said = self.distill(q, "auto", calls, rc=1)  # the next run distills nothing twice
        assert rc == 1 and said[0] == "distill: nothing to write (waiting=0)", said
        assert store_files(q) == [run] and run.read_bytes() == before
        ids = [e["id"] for e in jsonl(run)[1:]]
        assert ql_distill.spool_delivered(q, ids[:0], NOW) == 0 and set(CLOSED) <= set(spool_names(q))
        assert ql_distill.spool_delivered(q, ids, NOW) == 6
        assert spool_names(q) == [f"{S_OPEN}.jsonl"]  # the open session is never touched

    def test_one_delivered_entry_leaves_the_others(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        self.distill(q, "auto", [], rc=1)
        (run,) = store_files(q)
        entries = jsonl(run)[1:]
        sessions = {S_ENDED: (q / "spool" / f"{S_ENDED}.jsonl").read_text(encoding="utf-8"),
                    S_IDLE: (q / "spool" / f"{S_IDLE}.jsonl").read_text(encoding="utf-8")}
        one = next(e["id"] for e in entries if e["id"] in sessions[S_ENDED])
        assert ql_distill.spool_delivered(q, [one], NOW) == 1
        left = (q / "spool" / f"{S_ENDED}.jsonl").read_text(encoding="utf-8")
        assert one not in left and (q / "spool" / f"{S_IDLE}.jsonl").read_text(encoding="utf-8") == sessions[S_IDLE]
        rc, said = self.distill(q, "auto", [], rc=1)
        assert said[0] == "distill: nothing to write (waiting=0)" and store_files(q) == [run], said

    def test_the_leak_scan_over_store_files(self, tmp_path):
        store = tmp_path / "store"
        golden_store(store)
        rel = f"2026-09/{RUN_ID}.jsonl"
        assert ql_store.leak_problems(store, [rel]) == []
        objs = jsonl(FIXTURES / "golden.jsonl")
        objs[1]["tools"] = objs[1]["tools"] + ["anna.nowak" + "@" + "acme-corp.pl"]  # planted: a field check never reads
        golden_store(store, objs)
        (hit,) = ql_store.leak_problems(store, [rel])
        assert hit == f"{rel}:2: the leak scan flags an identifier (email)", hit


def learn_then_apply(wt, store, hold, out):
    """learn (pack: every question misses) and apply with the repo gate, in the worktree on its store."""
    rc = ql_learn.learn(store, pack=unknown_pack, kb_commit="0" * 40, out=out)
    return rc or repo_step(wt, store, hold, out)


REJECT_HOOK = "#!/bin/sh\necho 'planted: push refused' >&2\nexit 1\n"


# --- plugin hosts and cloud sessions -------------------------------------------------------------------------------

GITLAB_PROJECT = "GitLab: You are not allowed to push code to this project."
GITLAB_PROTECTED = "GitLab: You are not allowed to push code to protected branches on this project."
GITHUB_DENIED = "Permission to grp/proj.git denied to jan-kowalski."
GITHUB_GH006 = "error: GH006: Protected branch update failed for refs/heads/main.\nerror: Changes have been requested."
PUSH_RULE = "GitLab: Commit message does not follow the pattern '^(feat|fix):'"
UNREACHABLE = "http://127.0.0.1:9/grp/proj.git"  # a closed local port: a connection error, never the network


def plugins_dir(tmp, source):
    """A fake ~/.claude/plugins with one marketplace `mkt` whose known_marketplaces.json entry has `source`; the
    plugin copy's root (cache/mkt/it-ops-kb/<version>)."""
    plugins = Path(tmp) / "plugins"
    root = plugins / "cache" / "mkt" / "it-ops-kb" / "0123abcd4567"
    root.mkdir(parents=True, exist_ok=True)
    entry = {"source": source, "installLocation": str(plugins / "marketplaces" / "mkt"), "lastUpdated": "x"}
    (plugins / "known_marketplaces.json").write_text(json.dumps({"mkt": entry}), encoding="utf-8", newline="\n")
    return root


def reject_hook(message):
    """A pre-receive hook that prints `message` (each line, as a forge does) and refuses the push."""
    lines = "".join(f"echo {json.dumps(ln)} >&2\n" for ln in message.splitlines())
    return f"#!/bin/sh\n{lines}exit 1\n"


class TestHostRules:
    @pytest.mark.parametrize("text,kind", [
        (f"remote: {GITLAB_PROJECT}\nfatal: Could not read from remote repository.", "gitlab"),
        (f"remote: {GITLAB_PROTECTED}\n ! [remote rejected] main -> main (pre-receive hook declined)", "gitlab"),
        ("remote: GitLab: You are not allowed to force push code to a protected branch on this project.", "gitlab"),
        (f"ERROR: {GITHUB_DENIED}\nfatal: Could not read from remote repository.", "github"),
        ("remote: " + GITHUB_GH006.replace("\n", "\nremote: "), "github"),
        ("remote: Permission to grp/proj.git denied to jan-kowalski.\nfatal: unable to access "
         "'https://github.com/grp/proj.git/': The requested URL returned error: 403", "github"),
        ("fatal: unable to access 'https://gitlab.corp.example.com/grp/proj.git/': The requested URL returned "
         "error: 403", "http-403"),
    ])
    def test_a_refusal_for_want_of_rights(self, text, kind):
        assert ql_deliver.push_refusal(text).startswith(kind + ": "), ql_deliver.push_refusal(text)

    @pytest.mark.parametrize("text", [
        f"remote: {PUSH_RULE}\n ! [remote rejected] main -> main (pre-receive hook declined)",
        " ! [remote rejected] main -> main (pre-receive hook declined)",
        "fatal: unable to access 'https://gitlab.com/grp/proj.git/': Could not resolve host: gitlab.com",
        "ssh: Could not resolve hostname gitlab.com: nodename nor servname provided, or not known",
        "fatal: unable to access 'http://127.0.0.1:9/x.git/': Failed to connect to 127.0.0.1 port 9: Connection refused",
        " ! [remote failure] main -> main (remote failed to report status)",
        "fatal: unable to access 'https://gitlab.com/grp/proj.git/': The requested URL returned error: 503",
        "git@gitlab.corp.example.com: Permission denied (publickey).\nfatal: Could not read from remote repository.",
        "",
    ])
    def test_no_refusal(self, text):
        assert ql_deliver.push_refusal(text) is None

    def test_the_install_url(self, tmp_path, monkeypatch):
        root = plugins_dir(tmp_path / "a", {"source": "git", "url": "git@gitlab.corp.example.com:grp/proj.git"})
        assert ql_deliver.install_url(root) == "git@gitlab.corp.example.com:grp/proj.git"
        root = plugins_dir(tmp_path / "b", {"source": "github", "repo": "grp/proj"})
        assert ql_deliver.install_url(root) == "https://github.com/grp/proj.git"
        assert ql_deliver.install_url(tmp_path / "not-a-cache" / "x") is None
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        assert ql_deliver.install_url(None) is None

    @pytest.mark.skipif(not GIT, reason="git is not installed")
    def test_the_install_url_from_the_marketplace_clone(self, tmp_path):
        root = plugins_dir(tmp_path, {"source": "url", "url": "https://corp.example.com/marketplace.json"})
        mkt = Repo(tmp_path / "plugins" / "marketplaces" / "mkt", git_env())
        os.makedirs(mkt.path)
        mkt.git("init", "-q")
        assert ql_deliver.install_url(root) is None  # a clone without origin names nothing
        mkt.git("remote", "add", "origin", "https://gitlab.corp.example.com/grp/proj.git")
        assert ql_deliver.install_url(root) == "https://gitlab.corp.example.com/grp/proj.git"

    def test_a_cloud_session(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
        assert ql_deliver.cloud_session()
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", "false")
        assert not ql_deliver.cloud_session()
        monkeypatch.delenv("CLAUDE_CODE_REMOTE")
        assert not ql_deliver.cloud_session()

    def test_apply_push_in_a_plugin_host(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(ql_base.HOME))
        seen = []

        def host_push(qdir, run, apply_step, out, now_dt, root):
            seen.append(Path(qdir))
            return 0
        monkeypatch.setattr(ql_deliver, "host_push", host_push)
        assert querylog.main(["apply", "--push"]) == 0 and seen == [tmp_path / "querylog"]
        assert querylog.main(["apply", "--push", "--plugin-data", str(tmp_path)]) == 2  # the push names its own

    def test_a_host_without_an_install_source_is_refused(self, tmp_path):
        said = []
        assert ql_deliver.host_push(tmp_path, lambda argv, cwd=None: (1, "", ""), None, said.append,
                                    root=tmp_path / "x") == 2
        assert "install source is not recorded" in said[0] and not (tmp_path / ql_base.DISABLED_NAME).exists()

    def test_the_hosts_apply_reads_research_from_its_data_directory(self, tmp_path):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            return 0, "", ""
        p = ql_deliver.Pusher(tmp_path / "clone", tmp_path, run, None, print, research=["--plugin-data", str(tmp_path)])
        assert p.learn_and_apply(tmp_path / "wt", tmp_path / "wt" / "store", {"F-1"}, print) == 0
        assert calls[1][-4:] == ["--plugin-data", str(tmp_path), "--hold", "F-1"]
        assert ql_research.research_places(None, tmp_path) == (tmp_path, tmp_path / "config.json")
        p = ql_deliver.Pusher(tmp_path / "clone", tmp_path, run, None, print)
        calls.clear()
        p.learn_and_apply(tmp_path / "wt", tmp_path / "wt" / "store", set(), print)
        assert calls[1][-2:] == ["--clone", str(tmp_path / "clone")]


HOST_REFUSALS = {"gitlab-project": GITLAB_PROJECT, "gitlab-protected": GITLAB_PROTECTED,
                 "github-denied": GITHUB_DENIED, "github-gh006": GITHUB_GH006}


class HostCase:
    """A plugin host in mode `auto`: a fake plugins directory whose known_marketplaces.json names a local bare remote
    (a clone of the shared seed, conftest.kb_seed), a data directory with the fixture spool, distill with host_push;
    glab signed out, learn and apply in-process, kbgit.py sync's gate without tests.py (KB_SYNC_NO_TESTS=1). One case
    per test."""

    def run_case(self, case, kb_seed, env, tmp):
        top = Repo(tmp, env)
        bare = Repo(tmp / "remote.git", env)
        top.git("clone", "-q", "--bare", str(kb_seed[0]), bare.path)
        hook = Path(bare.path) / "hooks" / "pre-receive"
        if case in HOST_REFUSALS or case == "push-rule":
            hook.write_text(reject_hook(HOST_REFUSALS.get(case, PUSH_RULE)), encoding="utf-8", newline="\n")
            hook.chmod(0o755)
        if case == "red-gate":  # planted: main on the remote fails check.py (a fact citing no source row)
            planter = Repo(tmp / "planter", env)
            top.git("clone", "-q", bare.path, planter.path)
            planter.append(P("claude/plugins.md"), "- A planted fact. [DOC S-zzzzzzzz]\n")
            planter.git("commit", "-q", "-a", "--no-verify", "-m", "chore: planted")
            planter.git("push", "-q", "origin", "HEAD:main")
        url = UNREACHABLE if case == "unreachable-at-clone" else bare.path
        root = plugins_dir(tmp, {"source": "git", "url": url})
        q = tmp / "data" / "querylog"
        plant_spool(q)

        def run(argv, cwd=None):
            if argv[0] in ("glab", "gh"):
                return signed_out(argv)
            return run_here(argv, cwd=cwd, env=env)
        if case == "unreachable-at-push":  # the fetch works, the push meets a closed port
            clone = ql_deliver.managed_clone(q, bare.path, run, print)
            Repo(clone, env).git("config", "remote.origin.pushurl", UNREACHABLE)
        said = []
        rc = ql_distill.distill(qdir=q, cfg=auto_config(q), haiku=ql_base.Replay(FIXTURES / "haiku.json"),
                                now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40, out=said.append,
                                deliver=lambda qd, out: ql_deliver.host_push(qd, run, learn_then_apply, out, NOW, root))
        return rc, said, q, bare

    def case(self, case, kb_seed, tmp_path):
        rc, said, q, bare = self.run_case(case, kb_seed, git_env(KB_SYNC_NO_TESTS="1"), tmp_path)
        text = "\n".join(said)
        disabled = q / ql_base.DISABLED_NAME
        base = kb_seed[1]
        if case == "delivers":
            assert rc == 0, text
            assert (q / ql_deliver.CLONE_NAME / ".git").is_dir() and (q / ql_deliver.WORKTREE_NAME / ".git").exists()
            files = bare.git("ls-tree", "-r", "--name-only", "main", "--", ql_base.STORE_REL).split()
            assert f"{ql_base.STORE_REL}/2026-09/{RUN_ID}.jsonl" in files, files
            assert spool_names(q) == [f"{S_OPEN}.jsonl"] and not disabled.exists()
            return
        assert rc == 1, text
        if case == "red-gate":
            assert "gate check.py: FAILED" in text and "kbgit.py sync exit 1: nothing pushed to main" in text, text
        if case in HOST_REFUSALS:
            kind = case.split("-")[0]
            assert disabled.exists(), text
            why = disabled.read_text(encoding="utf-8")
            assert why.startswith("push refused for want of rights on ") and f": {kind}: " in why, why
            assert not (q / "spool").exists(), spool_names(q)
            assert "wrote DISABLED and deleted the spool" in text, text
            again = []
            assert ql_distill.distill(qdir=q, cfg=auto_config(q), out=again.append) == 0
            assert again == ["distill: logging is off"]
        else:
            assert not disabled.exists(), text
            assert set(CLOSED) <= set(spool_names(q)), spool_names(q)
        if case != "red-gate":
            assert bare.rev("main") == base  # nothing pushed
        assert bare.git("for-each-ref", "--format=%(refname)", "refs/heads").split() == ["refs/heads/main"]


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestHostInGit(HostCase):
    @pytest.mark.parametrize("case", ["delivers", "unreachable-at-clone", "red-gate"])
    def test_case(self, case, kb_seed, tmp_path):
        self.case(case, kb_seed, tmp_path)


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestHostRefusalsInGit(HostCase):
    @pytest.mark.parametrize("case", ["gitlab-project", "gitlab-protected", "github-denied", "github-gh006"])
    def test_case(self, case, kb_seed, tmp_path):
        self.case(case, kb_seed, tmp_path)


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestHostNoRefusalInGit(HostCase):
    @pytest.mark.parametrize("case", ["push-rule", "unreachable-at-push"])
    def test_case(self, case, kb_seed, tmp_path):
        self.case(case, kb_seed, tmp_path)


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestCloudInGit:
    """A cloud session: a clone on the branch `claude/work` of a bare remote whose pre-receive hook takes pushes to
    that branch only (as the session's git proxy does); distill in mode `auto` with a Pusher told it is a cloud
    session."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, kb_seed):
        cls.tmp = Path(tmp_path_factory.mktemp("ql-cloud"))
        cls.env = git_env(KB_SYNC_NO_TESTS="1")
        cls.base = kb_seed[1]
        top = Repo(cls.tmp, cls.env)
        cls.bare = Repo(cls.tmp / "remote.git", cls.env)
        top.git("clone", "-q", "--bare", str(kb_seed[0]), cls.bare.path)
        hook = Path(cls.bare.path) / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nwhile read old new ref; do\n  [ \"$ref\" = refs/heads/claude/work ] || "
                        "{ echo \"push to $ref refused: the session pushes to claude/work only\" >&2; exit 1; }\n"
                        "done\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        cls.a = Repo(cls.tmp / "a", cls.env)
        top.git("clone", "-q", cls.bare.path, cls.a.path)
        cls.a.git("checkout", "-q", "-b", "claude/work")
        cls.q = Path(cls.a.path) / "_cache" / "querylog"
        plant_spool(cls.q)
        cls.first = cls.distill()
        cls.branch1 = cls.bare.rev("claude/work")
        cls.again = cls.distill()
        cls.branch2 = cls.bare.rev("claude/work")
        cls.a.git("checkout", "-q", "--detach")
        cls.detached = []
        cls.detached_rc = ql_deliver.Pusher(cls.a.path, cls.q, cls.runner(), learn_then_apply, cls.detached.append, NOW,
                                            cloud=True)()

    @classmethod
    def runner(cls):
        def run(argv, cwd=None):
            if argv[0] in ("glab", "gh"):
                return signed_out(argv)
            return run_here(argv, cwd=cwd, env=cls.env)
        return run

    @classmethod
    def distill(cls):
        said = []

        def deliver(qdir, out):
            return ql_deliver.Pusher(cls.a.path, qdir, cls.runner(), learn_then_apply, out, NOW, cloud=True)()
        rc = ql_distill.distill(qdir=cls.q, cfg=auto_config(cls.q), haiku=ql_base.Replay(FIXTURES / "haiku.json"),
                                now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40, out=said.append, deliver=deliver)
        return rc, said

    def test_the_commits_land_on_the_working_branch(self):
        rc, said = self.first
        assert rc == 0, "\n".join(said)
        assert "apply --push: cloud session: automatic commits go to its working branch claude/work" in said
        files = self.bare.git("ls-tree", "-r", "--name-only", "claude/work", "--", ql_base.STORE_REL).split()
        assert f"{ql_base.STORE_REL}/2026-09/{RUN_ID}.jsonl" in files, files
        assert self.bare.rev("main") == self.base
        assert "apply --push: deleted the spool rows of 6 entries whose run file is on origin/claude/work" in said
        assert spool_names(self.q) == [f"{S_OPEN}.jsonl"]

    def test_a_second_run_starts_from_the_branch_and_pushes_nothing(self):
        rc, said = self.again
        assert rc == 0 and "apply --push: nothing to push" in said, said
        assert self.branch2 == self.branch1

    def test_a_detached_head_is_refused(self):
        assert self.detached_rc == 2 and "HEAD is detached" in self.detached[0], self.detached


# --- the gap step, the quote check and research (Query log item 8) --------------------------------------------------

PAGE = FIXTURES / "pages" / "laps-platforms.html"
PAGE_URL = "https://docs.example.com/laps/platforms"
GOOD_QUOTE = "it doesn't support Windows Server 2012 R2"  # the page writes doesn&#8217;t and 2012&nbsp;R2
BAD_QUOTE = "Windows LAPS supports Windows Server 2012 R2 with the April 2023 update"
LEGACY_QUOTE = "The legacy Microsoft LAPS product remains available for older operating systems"  # a link and <em>
DAY = "2026-09-28"
GAP_ID = ql_store.finding_id("gap", E("a4"))
ARTICLE_MD = """---
topic: windows/laps
priority: P1
applies_to: [windows]
retrieved_utc: 2026-09-01
sources: [S100, S101]
status: complete
---

# Windows LAPS

## Summary

A test article.

## Facts

- Windows LAPS keeps the managed account's password in the directory. [DOC S100]
- The default password length is 14 characters. [DOC S101]

## Reference

- None.
"""
SOURCES_CSV = ("id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
               "S100,https://docs.example.com/laps/overview,LAPS overview,Example Docs,CC BY 4.0,copy,2026-09-01,,,"
               "windows/laps.md,\n"
               "S101,https://docs.example.com/laps/policy,LAPS policy,Example Docs,CC BY 4.0,copy,2026-09-01,,,"
               "windows/laps.md,\n")
GAPS_MD = ("# Gaps\n\n## windows/laps\n\n- **An older entry.** Looked somewhere. (topic: windows/laps)\n\n"
           "## other/topic\n\n- **Another entry.** Elsewhere. (topic: other/topic)\n")


def pages(url):
    if url != PAGE_URL:
        raise OSError(f"no recorded page for {url}")
    return PAGE.read_bytes(), "text/html; charset=utf-8"


def cand(**kw):
    c = {"text": "Windows LAPS does not back up passwords from Windows Server 2012 R2 devices.", "tag": "DOC",
         "url": PAGE_URL, "title": "Windows LAPS platform support", "publisher": "Example Docs",
         "licence": "CC BY 4.0, stated on the page (test page)", "reuse": "copy", "quote": GOOD_QUOTE,
         "conflicts_with": None}
    c.update(kw)
    return c


def reply(*cands):
    return "Here is what I found.\n" + json.dumps({"facts": list(cands)})


class KbGate(ql_apply.Gate):
    """The gap step's and research's gate on a one-article root in a temporary directory: pack leads with that
    article (`res`), build_index and check.py stubbed (`checks` are their problems), the eval set unchanged."""

    def __init__(self, root, res=None, checks=()):
        self.dir, self.checks, self.indexed = Path(root), list(checks), 0
        self.res = res or {"verdict": "weak", "paths": [LAPS, "public/windows/gmsa.md"], "missing": []}

    def fresh(self):
        pass

    def pack(self, question):
        return self.res

    def article_of(self, path):
        return path if path == LAPS else None

    def topic(self, article):
        return "windows/laps"

    def ledger(self, article, name):
        return self.dir / name

    def file(self, article):
        return self.dir / "windows" / "laps.md"

    def id_prefix(self, article):
        return "S"

    def index_and_check(self):
        self.indexed += 1
        return list(self.checks)

    def measure(self):
        return {"n": 1, "passed": 1, "failed": [], "chars": {"EV-a": 100}, "offkb_good": 0}


def kb_root(d, gaps=GAPS_MD):
    d = Path(d)
    (d / "windows").mkdir(parents=True, exist_ok=True)
    for name, text in (("windows/laps.md", ARTICLE_MD), ("_sources.csv", SOURCES_CSV), ("_gaps.md", gaps),
                       ("_conflicts.md", "# Conflicts\n")):
        (d / name).write_text(text, encoding="utf-8", newline="\n")
    return d


def root_files(d):
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(Path(d).rglob("*")) if p.is_file()}


def gap_store(tmp_path, extra=()):
    """The fixture store after one learn in which only a4 (and the `extra` entries, copies of a4 with other ids, each
    `n` or `(n, question, day)`) still fail: open gap candidates, the evals fixed since."""
    store = learn_store(tmp_path)
    (p,) = ql_store.run_files(store)
    objs = jsonl(p)
    a4 = next(o for o in objs if o.get("id") == E("a4"))
    for x in extra:
        n, q, day = (x, None, None) if isinstance(x, str) else x
        objs.append({**a4, "id": E(n), "question": q or f"{a4['question']} ({n})", "day": day or a4["day"]})
    objs[0]["counts"]["entries"] = len(objs) - 1
    p.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in objs), encoding="utf-8", newline="\n")
    run_learn(store, lambda q: failing(q) if "VMware" in q else passing(q))
    return store


def run_gap_apply(store, gate, research=None):
    said = []
    rc = ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=said.append, research=research, day=DAY)
    return rc, said


class TestGapStep:
    def test_a_reproduced_gap_becomes_an_entry_under_its_topic(self, tmp_path):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        rc, said = run_gap_apply(store, KbGate(root))
        assert rc == 0 and "gaps=1" in said[0] and "applied=1" in said[0], said
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        lines = text.split("\n")
        at = lines.index("- **An older entry.** Looked somewhere. (topic: windows/laps)")
        new = lines[at + 1]  # at the end of its topic's section, before the next section
        assert new.startswith("- **How do I configure VMware Horizon instant clone pools?** ") and lines[at + 3] == \
            "## other/topic"
        assert new.endswith("(topic: windows/laps)") and f"Looked in the kb {DAY}" in new and GAP_ID in new
        assert ql_research.edit_problems("_gaps.md", GAPS_MD, text) == []  # added, nothing edited
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["article"]) == ("applied", "gap", LAPS)
        assert rec["promotions"] == [{"from": "miss", "to": "candidate-gap", "by": "learn"},
                                     {"from": "candidate-gap", "to": "gap", "by": "apply"}]
        assert ql_store.store_problems(store) == []
        first = tree(store), root_files(root)
        assert run_gap_apply(store, KbGate(root)) == (0, ["apply: nothing to apply"])  # converges
        assert (tree(store), root_files(root)) == first

    def test_a_topic_without_a_section_gets_one(self, tmp_path):
        old = "# Gaps\n\n## other/topic\n\n- **Another entry.** x. (topic: other/topic)\n"
        root = kb_root(tmp_path / "root", gaps=old)
        run_gap_apply(gap_store(tmp_path), KbGate(root))
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        assert text.startswith(old + "\n## windows/laps\n\n- **How do I configure VMware Horizon instant clone pools?**")
        assert text.endswith("(topic: windows/laps)\n") and text.count("\n") == old.count("\n") + 4

    def test_an_entry_is_written_once(self, tmp_path):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        run_gap_apply(store, KbGate(root))
        text = (root / "_gaps.md").read_bytes()
        ql_store.findings_files(store)[-1].unlink()  # the record is gone (a lost run), the entry is there
        run_gap_apply(store, KbGate(root))
        assert (root / "_gaps.md").read_bytes() == text

    @pytest.mark.parametrize("res", [
        {"verdict": "none", "paths": [], "missing": ["horizon"]},  # no lead
        {"verdict": "weak", "paths": ["public/nowhere/x.csv"], "missing": []},  # a lead no article holds
        {"verdict": "none", "paths": [LAPS], "matched": ["configur", "instant", "pool"],  # a stray none lead: 3 of 6
         "known": ["clon", "configur", "horizon", "instant", "pool", "vmwar"], "lacks": ["VMware", "Horizon", "clone"]},
    ])
    def test_a_gap_off_the_kb_is_rejected(self, tmp_path, res):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        before = root_files(root)
        rc, said = run_gap_apply(store, KbGate(root, res=res))
        assert rc == 0 and "applied=0 rejected=1 no-fix=0" in said[0] and "gaps=" not in said[0], said
        assert root_files(root) == before  # no topic takes its entry
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == ("rejected", "candidate-gap",
                                                                          ["off the kb's domains"])
        assert ql_store.store_problems(store) == []
        assert run_gap_apply(store, KbGate(root, res=res)) == (0, ["apply: nothing to apply"])  # converges

    @pytest.mark.parametrize("res", [
        {"verdict": "good", "paths": [LAPS], "missing": []},  # passes now: learn records it
        {"verdict": "none", "paths": [LAPS], "matched": ["budget", "hook", "sessionend"],  # the lead holds `1.5`:
         "known": ["1.5", "budget", "hook", "sessionend"], "lacks": ["1.5"]},  # learn makes it an eval finding
    ])
    def test_a_gap_fixed_or_held_is_left_to_learn(self, tmp_path, res):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        gate = KbGate(root, res=res)
        gate.facts = lambda article: [(9, "`SessionEnd` hooks share a 1.5-second budget on exit. [DOC S100]")]
        before = root_files(root), tree(store)
        assert run_gap_apply(store, gate) == (0, ["apply: nothing to apply"])
        assert (root_files(root), tree(store)) == before
        assert (by_id(store)[GAP_ID]["state"], by_id(store)[GAP_ID]["stage"]) == ("open", "candidate-gap")

    def test_gap_step_rejects_weak_off_domain(self, tmp_path):
        """F-bd7367a45f3a: 'What is the maximum email attachment size?' packs `weak` with 3 of 4 key words, led by
        mecm/collect-client-logs; the words it matched are qualifiers that name nothing of the lead's topic, and the
        word it lacks, the subject, is in none of the lead's facts: off the kb's domains, no _gaps.md entry."""
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        res = {"verdict": "weak", "paths": [LAPS, GMSA], "matched": ["attachment", "maximum", "size"],
               "known": ["attachment", "email", "maximum", "size"], "lacks": ["email"], "missing": []}
        gate = KbGate(root, res=res)
        gate.title = lambda article: "Windows LAPS"
        gate.facts = lambda article: [(9, "Windows LAPS backs up the password to Active Directory. [DOC S100]")]
        before = root_files(root)
        rc, said = run_gap_apply(store, gate)
        assert rc == 0 and "applied=0 rejected=1 no-fix=0" in said[0] and "gaps=" not in said[0], said
        assert root_files(root) == before
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == ("rejected", "candidate-gap",
                                                                          ["off the kb's domains"])
        assert ql_store.store_problems(store) == []

    @pytest.mark.parametrize("res,fact", [
        ({"verdict": "weak", "paths": [LAPS], "matched": ["laps", "maximum", "password"],  # names the lead's topic
          "known": ["azur", "laps", "maximum", "password"], "lacks": ["Azure"], "missing": []},
         "Windows LAPS backs up the password to Active Directory. [DOC S100]"),
        ({"verdict": "weak", "paths": [LAPS], "matched": ["backup", "maximum", "size"],  # the lead's facts hold `Azure`
          "known": ["azur", "backup", "maximum", "size"], "lacks": ["Azure"], "missing": []},
         "Windows LAPS backs up the password to Azure or AD. [DOC S100]"),
    ])
    def test_gap_step_takes_weak_on_domain(self, tmp_path, res, fact):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        gate = KbGate(root, res=res)
        gate.title = lambda article: "Windows LAPS"
        gate.facts = lambda article: [(9, fact)]
        rc, said = run_gap_apply(store, gate)
        assert rc == 0 and "gaps=1" in said[0], said
        assert "gives `weak`, with this topic in the lead" in (root / "_gaps.md").read_text(encoding="utf-8")
        assert (by_id(store)[GAP_ID]["state"], by_id(store)[GAP_ID]["stage"]) == ("applied", "gap")

    def test_a_none_gap_under_its_article_becomes_an_entry(self, tmp_path):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        res = {"verdict": "none", "paths": [LAPS], "matched": ["backup", "laps", "password"],
               "known": ["azur", "backup", "laps", "password"], "lacks": ["Azure"]}  # 3 of 4: the LAPS topic
        gate = KbGate(root, res=res)
        gate.facts = lambda article: [(9, "Windows LAPS backs up the password to Active Directory. [DOC S100]")]
        rc, said = run_gap_apply(store, gate)
        assert rc == 0 and "gaps=1" in said[0], said
        assert "gives `none`, with this topic in the lead" in (root / "_gaps.md").read_text(encoding="utf-8")
        assert (by_id(store)[GAP_ID]["state"], by_id(store)[GAP_ID]["stage"]) == ("applied", "gap")

    def test_none_candidate_gap_is_not_stranded(self, tmp_path, monkeypatch):
        """Every open gap candidate reaches a next state (F-6298df20a337: a none pack whose lead article holds the
        answer): learn turns the one the lead article holds into an eval finding, apply the one the kb lacks under
        its article into a _gaps.md entry the queue lists, and the stray none into a rejection, so the digest's open
        gaps are none but what the queue reaches."""
        held_q, lacks_q, stray_q = ("SessionEnd hook input fields reason budget 1.5 seconds",
                                    "Does SessionEnd hook input carry a zorblax field?", VMWARE_Q)
        store = learn_store(tmp_path)
        plant_entries(store, none_entry("ca", held_q), none_entry("cb", lacks_q))
        packs = {held_q: {"verdict": "none", "paths": [LAPS], "matched": ["budget", "hook", "reason", "sessionend"],
                          "known": ["1.5", "budget", "hook", "reason", "sessionend"], "lacks": ["1.5"], "missing": []},
                 lacks_q: {"verdict": "none", "paths": [LAPS], "matched": ["hook", "input", "sessionend"],
                           "known": ["field", "hook", "input", "sessionend"], "lacks": ["zorblax"],
                           "missing": ["zorblax"]},
                 stray_q: {"verdict": "none", "paths": [LAPS], "matched": ["configur", "instant", "pool"],
                           "known": ["clon", "configur", "horizon", "instant", "pool", "vmwar"],
                           "lacks": ["VMware", "Horizon", "clone"], "missing": []}}
        pack = lambda q: packs.get(q) or passing(q)  # noqa: E731
        facts = [(64, "`SessionEnd` hooks share a 1.5-second budget on exit, `/clear` and `/resume`. [DOC S100]")]
        monkeypatch.setattr(ql_learn, "article_of", lambda path: path if path == LAPS else None)
        monkeypatch.setattr(ql_learn, "article_facts", lambda article: facts if article == LAPS else [])
        gap = {n: ql_store.finding_id("gap", E(n)) for n in ("ca", "cb", "a4")}
        ev = ql_store.finding_id("eval", E("ca"))

        def open_gaps():
            week, lines_, _ = ql_report.digest(store, "2026-W40")
            line = next((ln for ln in lines_ if ln.startswith("  gap: ")), "")
            m = re.search(r"\bopen (\d+)", line)
            return int(m.group(1)) if m else 0

        # the store as it stood: three none misses, each an open gap candidate (the planted stranded state)
        run_learn(store, lambda q: {**packs[q], "lacks": ["zorblax"]} if q in packs else passing(q))
        assert {by_id(store)[gap[n]]["stage"] for n in gap} == {"candidate-gap"} and open_gaps() == 3
        root = kb_root(tmp_path / "root")
        gate = KbGate(root)
        gate.pack, gate.facts = pack, ql_learn.article_facts
        assert run_queue(store, gate)[1][0].startswith("queue: gaps=0 ")  # the digest counts 3 the queue cannot reach

        rc, said = run_learn(store, pack)  # the lead article holds `1.5`: an eval finding, the gap candidate gone
        assert rc == 0, said
        now = by_id(store)
        assert (now[ev]["kind"], now[ev]["state"], now[ev]["stage"], now[ev]["expect"]) == ("eval", "open", "miss", LAPS)
        assert now[gap["ca"]]["state"] == "fixed-since"  # no longer an open candidate: it left candidate-gap
        assert now[ql_store.finding_id("expansion", E("ca"))]["article"] == LAPS  # its fix, as for any eval miss

        hold = {i for i, r in now.items() if r["kind"] in ("eval",) + ql_store.FIX_KINDS}  # the gap step alone
        said = []
        rc = ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=said.append, hold=hold, day=DAY)
        assert rc == 0 and "applied=1 rejected=1" in said[0] and "gaps=1" in said[0], said
        now = by_id(store)
        assert (now[gap["cb"]]["state"], now[gap["cb"]]["stage"]) == ("applied", "gap")  # the kb lacks it
        assert (now[gap["a4"]]["state"], now[gap["a4"]]["stage"]) == ("rejected", "candidate-gap")  # the stray lead
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        assert gap["cb"] in text and gap["ca"] not in text and gap["a4"] not in text
        rc, said = run_queue(store, gate)
        assert rc == 0 and said[0].startswith("queue: gaps=1 queued=1 ") and listed(said) == [gap["cb"]], said
        assert open_gaps() == 0  # no open gap the queue cannot reach
        assert ql_store.store_problems(store) == []
        before = tree(store), root_files(root)
        assert run_learn(store, pack)[1][0].startswith("learn: nothing new")  # converges
        assert ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=lambda _: None, hold=hold, day=DAY) == 0
        assert (tree(store), root_files(root)) == before

    def test_holds_word(self):
        assert ql_learn.holds_word("1.5", "hooks share a 1.5-second budget") and ql_learn.holds_word("1.5", "is 1.5.")
        assert not ql_learn.holds_word("1.5", "since v2.1.5 it") and not ql_learn.holds_word("1.5", "a 1.50 s wait")
        assert ql_learn.holds_word("Azure", "backs up to azure.") and not ql_learn.holds_word("log", "a catalog")

    def test_add_under(self):
        assert ql_research.add_under("", "a/b", "- x") == "## a/b\n\n- x\n"
        assert ql_research.add_under("# T\n\n## a/b\n", "a/b", "- x") == "# T\n\n## a/b\n\n- x\n"
        assert ql_research.add_under("# T\n\n## a/b\n\n- y\n\n\n## c/d\n\n- z\n", "a/b", "- x") == \
            "# T\n\n## a/b\n\n- y\n- x\n\n\n## c/d\n\n- z\n"


GMSA = "public/windows/gmsa.md"
VMWARE_Q = "How do I configure VMware Horizon instant clone pools?"  # a4's question
LATER = "2026-10-28"  # QUEUE_TRIED_DAYS after DAY


class TwoTopicGate(KbGate):
    """KbGate with a second article: a question naming gMSA leads with windows/gmsa, any other with windows/laps."""

    def pack(self, question):
        if self.res.get("verdict") == "good":
            return self.res
        return {"verdict": "weak", "paths": [GMSA if "gMSA" in question else LAPS], "missing": []}

    def article_of(self, path):
        return path if path in (LAPS, GMSA) else None

    def topic(self, article):
        return {LAPS: "windows/laps", GMSA: "windows/gmsa"}[article]


def queued(tmp_path, extra=()):
    """(root, store, gate): the gap store after the gap step wrote its _gaps.md entries in a one-article root."""
    root = kb_root(tmp_path / "root")
    store = gap_store(tmp_path, extra)
    gate = TwoTopicGate(root)
    run_gap_apply(store, gate)
    return root, store, gate


def run_queue(store, gate, limit=None, day=DAY):
    said = []
    rc = ql_research.queue(store, limit, gate=gate, day=day, kb_commit="0" * 40, out=said.append)
    return rc, said


def run_close(store, gate, fid, **kw):
    said = []
    rc = ql_research.close(fid, store=store, gate=gate, day=DAY, kb_commit="0" * 40, out=said.append, **kw)
    return rc, said


def resolve(root, fid, note="the vendor's page states it (S100)"):
    """The _gaps.md entry of `fid` closed by the content rules: a `Resolved <day>:` note under it."""
    p = root / "_gaps.md"
    lines = p.read_text(encoding="utf-8").split("\n")
    _, end = ql_research.entry_block(lines, fid)
    lines[end:end] = [f"  - Resolved {DAY}: {note}. (topic: windows/laps)"]
    p.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def listed(said):
    """The finding ids a queue printed, in order."""
    return re.findall(r"^     (F-[0-9a-f]{12}) ", "\n".join(said), re.M)


class TestQueue:
    def test_ranked_by_lookups_then_age_and_grouped_by_topic(self, tmp_path):
        _, store, gate = queued(tmp_path, extra=(("d1", VMWARE_Q, None),  # asked twice with a4
                                                 ("d2", "Can VMware Horizon run as a gMSA?", "2026-09-20"),  # older
                                                 ("d3", "VMware Horizon pool sizes?", None)))
        gap = {n: ql_store.finding_id("gap", E(n)) for n in ("a4", "d1", "d2", "d3")}
        rc, said = run_queue(store, gate)
        assert rc == 0 and said[0].startswith("queue: gaps=4 queued=3 listed=3 waiting=0 fixed-since=0"), said
        # one item per question: a4 and d1 asked the same one; grouped by topic, laps (d3 too), then gmsa (d2)
        assert listed(said) == sorted([gap["a4"], gap["d1"]]) + [gap["d3"], gap["d2"]]
        assert [s for s in said if s.startswith("topic ")] == ["topic windows/laps", "topic windows/gmsa"]
        first = said.index("  1. asked=2 since=2026-09-27")
        assert said[first + 1] == f"     question: {VMWARE_Q}"
        assert re.fullmatch(rf"     {sorted([gap['a4'], gap['d1']])[0]} .*_gaps\.md:\d+", said[first + 2])
        rc, top = run_queue(store, gate, limit=2)  # the top two by rank: the question asked twice, then the oldest
        assert listed(top) == sorted([gap["a4"], gap["d1"]]) + [gap["d2"]]
        assert "listed=2" in top[0] and top.count("topic windows/gmsa") == 1

    def test_the_same_store_and_head_give_the_same_queue(self, tmp_path):
        _, store, gate = queued(tmp_path, extra=("d1",))
        other = tmp_path / "copy"
        shutil.copytree(store, other)
        assert run_queue(store, gate) == run_queue(other, gate) and tree(store) == tree(other)

    def test_a_gap_that_passes_now_is_recorded_fixed_since(self, tmp_path):
        root, store, gate = queued(tmp_path, extra=("d1",))
        gate.res = {"verdict": "good", "paths": [LAPS], "missing": []}
        rc, said = run_queue(store, gate)
        assert rc == 0 and "queued=0" in said[0] and "fixed-since=2" in said[0], said
        recs = findings(store)[-1][1]
        assert {r["state"] for r in recs} == {"fixed-since"} and {r["stage"] for r in recs} == {"gap"}
        assert ql_store.store_problems(store) == []
        gate.res = {}  # the kb fails it again: it stays fixed-since, learn leaves it
        before = tree(store)
        assert run_queue(store, gate)[1][0].startswith("queue: gaps=0 ")
        rc, said = run_learn(store, lambda q: failing(q) if "VMware" in q else passing(q))
        assert said[0].startswith("learn: nothing new") and tree(store) == before, said

    def test_a_second_queue_after_a_closing_run_omits_the_closed_gap(self, tmp_path):
        root, store, gate = queued(tmp_path, extra=("d1",))
        fid = listed(run_queue(store, gate)[1])[0]
        assert run_close(store, gate, fid, claim=True) == (1, [
            f"close: {root.as_posix()}/_gaps.md:{ql_research.ledger_entry(gate, by_id(store)[fid])[1]} has no "
            "`Resolved <date>:` note under it; close the entry by the content rules first"])
        resolve(root, fid)
        rc, said = run_close(store, gate, fid, claim=True)
        assert rc == 0 and said[0].startswith(f"close: {fid} claim run="), said
        rec = by_id(store)[fid]
        assert (rec["state"], rec["stage"], rec["promotions"][-1]) == (
            "applied", "claim", {"from": "gap", "to": "claim", "by": "kb-research"})
        assert querylog.main(["check", str(store)]) == 0
        rc, again = run_queue(store, gate)
        assert rc == 0 and fid not in "\n".join(again) and len(listed(again)) == 1
        before = tree(store), root_files(root)
        assert run_queue(store, gate) == (rc, again) and (tree(store), root_files(root)) == before  # converges
        assert run_close(store, gate, fid, claim=True)[0] == 1  # closed: no second record

    def test_a_planted_closed_gap_that_reappears_fails(self, tmp_path):
        root, store, gate = queued(tmp_path)
        fid = listed(run_queue(store, gate)[1])[0]
        resolve(root, fid)
        run_close(store, gate, fid, claim=True)
        entries = ql_store.store_entries(store)
        back = {**by_id(store)[fid], "stage": "gap", "promotions": by_id(store)[fid]["promotions"][:2]}
        ql_store.write_findings(store, entries, [back], ("applied",), "0" * 40)  # a later record reopens it
        assert any("reappears at stage gap" in p for p in ql_store.store_problems(store))
        rc, said = run_queue(store, gate)
        assert rc == 1 and listed(said) == [] and any("reappears at stage gap" in s for s in said), said

    def test_a_closed_gap_whose_entry_reopens_fails(self, tmp_path):
        root, store, gate = queued(tmp_path)
        fid = listed(run_queue(store, gate)[1])[0]
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        _, line, _ = ql_research.ledger_entry(gate, by_id(store)[fid])
        resolve(root, fid)
        run_close(store, gate, fid, claim=True)
        assert run_queue(store, gate)[0] == 0
        (root / "_gaps.md").write_text(text, encoding="utf-8", newline="\n")  # the Resolved note is gone
        rc, said = run_queue(store, gate)
        assert rc == 1 and said[-1] == (f"problem: {fid}: closed at claim, but its entry {root.as_posix()}/_gaps.md:"
                                        f"{line} has no Resolved note"), said

    def test_a_recent_tried_note_waits_and_an_old_one_is_queued(self, tmp_path):
        root, store, gate = queued(tmp_path)
        fid = listed(run_queue(store, gate)[1])[0]
        assert run_close(store, gate, fid, tried="   ")[0] == 1
        rc, said = run_close(store, gate, fid, tried="Searched the vendor docs; no page states it. (topic: x/y)")
        assert rc == 0 and said[0].startswith(f"close: {fid} tried {DAY} run="), said
        lines = (root / "_gaps.md").read_text(encoding="utf-8").split("\n")
        i, end = ql_research.entry_block(lines, fid)
        assert lines[end - 1] == f"  - Tried {DAY}: Searched the vendor docs; no page states it. (topic: windows/laps)"
        assert by_id(store)[fid]["tried"] == DAY and querylog.main(["check", str(store)]) == 0
        day_before = (datetime.date.fromisoformat(LATER) - datetime.timedelta(days=1)).isoformat()
        rc, said = run_queue(store, gate, day=day_before)
        assert listed(said) == [] and f"waiting {fid}: tried {DAY}, back in the queue {LATER}" in said, said
        assert listed(run_queue(store, gate, day=LATER)[1]) == [fid]

    def test_close_refuses_what_is_no_open_gap(self, tmp_path):
        root, store, gate = queued(tmp_path)
        assert run_close(store, gate, "F-000000000000", claim=True)[0] == 1
        other = next(r["id"] for r in by_id(store).values() if r["kind"] == "eval")
        assert run_close(store, gate, other, tried="x")[0] == 1
        (root / "_gaps.md").write_text(GAPS_MD, encoding="utf-8", newline="\n")  # the entry is gone
        fid = next(r["id"] for r in by_id(store).values() if r["kind"] == "gap")
        assert run_close(store, gate, fid, tried="x") == (1, [f"close: no _gaps.md entry names {fid}"])

    def test_cli(self, tmp_path):
        store = learn_store(tmp_path)
        out = subprocess.run([sys.executable, QL, "queue", "2", "--store", str(store)], capture_output=True, text=True,
                             encoding="utf-8", cwd=KB, env=querylog_env(tmp_path / "data"))
        assert out.returncode == 0 and out.stdout.startswith("queue: gaps=0 "), out.stdout + out.stderr
        out = subprocess.run([sys.executable, QL, "close", "F-000000000000", "--claim", "--store", str(store)],
                             capture_output=True, text=True, encoding="utf-8", cwd=KB,
                             env=querylog_env(tmp_path / "data"))
        assert out.returncode == 1 and "no open gap finding" in out.stdout, out.stdout + out.stderr


class TestQuoteCheck:
    @pytest.mark.parametrize("quote", [
        GOOD_QUOTE,  # an entity and a no-break space on the page
        f"\u201c{LEGACY_QUOTE}.\u201d",  # a link and emphasis on the page, the quote in curly quotes
        "Windows LAPS backs up passwords to Microsoft Entra ID only from devices",  # spread over lines
        "WINDOWS SERVER 2012 R2 & EARLIER RELEASES",  # &amp; on the page
    ])
    def test_a_quote_on_its_page(self, quote):
        assert ql_research.quotecheck(PAGE_URL, quote, pages) == (True, "quote is on the page")

    @pytest.mark.parametrize("quote,why", [
        (BAD_QUOTE, "quote is not on the page"),  # planted: a quote not on its page
        ("Docs > Identity > LAPS is the path", "quote is not on the page"),  # page chrome is not the page's text
        (" ".join(["word"] * 26), "quote has 26 words, over 25"),
        ("Windows LAPS", "quote has 2 words, under 5"),
    ])
    def test_a_quote_not_accepted(self, quote, why):
        assert ql_research.quotecheck(PAGE_URL, quote, pages) == (False, why)

    def test_a_page_that_cannot_be_fetched(self):
        ok, why = ql_research.quotecheck("https://docs.example.com/other", GOOD_QUOTE, pages)
        assert not ok and why.startswith("page not fetched: OSError")

    def test_a_markdown_page(self):
        md = b"See the [LAPS overview](https://docs.example.com/o) for **supported** platforms and more.\n"
        assert ql_research.quotecheck(PAGE_URL, "See the LAPS overview for supported platforms",
                                      lambda u: (md, "text/markdown"))[0]

    def test_pages_are_fetched_as_fetch_py_fetches_them(self, monkeypatch):
        import fetch
        asked = []
        monkeypatch.setattr(fetch, "fetch", lambda url: asked.append(url) or pages(url))
        assert ql_research.quotecheck(PAGE_URL, GOOD_QUOTE)[0] and asked == [PAGE_URL]

    def test_quote_max_words_is_the_kb_rule(self):
        import kbcommon
        assert ql_research.QUOTE_MAX_WORDS == kbcommon.QUOTE_WORDS == 25

    @pytest.mark.parametrize("quote,rc,said", [(GOOD_QUOTE, 0, "quotecheck: quote is on the page\n"),
                                               (BAD_QUOTE, 1, "quotecheck: quote is not on the page\n")])
    def test_cli(self, tmp_path, quote, rc, said):
        p = subprocess.run([sys.executable, QL, "quotecheck", PAGE_URL, quote, "--page", str(PAGE)],
                           capture_output=True, text=True, encoding="utf-8", env=querylog_env(tmp_path), timeout=120)
        assert (p.returncode, p.stdout) == (rc, said), p.stderr


class TestResearchConfig:
    @pytest.mark.parametrize("text,want", [
        (None, (False, 0)),  # no file: research is off by default
        ('{"mode": "local"}', (False, 0)),
        ('{"research": true}', (True, ql_base.DEFAULT_RESEARCH_DAILY)),
        ('{"research": true, "research_daily": 1}', (True, 1)),
        ('{"research": true, "research_daily": 0}', (True, 0)),
        ('{"research": "yes"}', (False, 0)),  # fail closed
        ('{"research": true, "research_daily": -1}', (False, 0)),
        ('{"research": true, "research_daily": "many"}', (False, 0)),
        ('{"research": true, "research_daily": true}', (False, 0)),
        ("{not json", (False, 0)),
    ])
    def test_read_research(self, tmp_path, text, want):
        cfg = tmp_path / "config.json"
        if text is not None:
            cfg.write_text(text, encoding="utf-8")
        assert ql_base.read_research(cfg) == want
        assert ql_base.DEFAULT_RESEARCH is False

    def test_the_daily_cap_counts_runs(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"mode": "local", "research": true, "research_daily": 2}', encoding="utf-8")
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 2
        ql_research.count_research(tmp_path, DAY)
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 1
        ql_research.count_research(tmp_path, DAY)
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 0
        ql_research.count_research(tmp_path, DAY)  # never below 0
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 0
        assert ql_research.research_budget(tmp_path, cfg, "2026-09-29") == 2  # a new day
        (tmp_path / "DISABLED").write_text("", encoding="utf-8")
        assert ql_research.research_budget(tmp_path, cfg, "2026-09-29") == 0
        (tmp_path / "DISABLED").unlink()
        cfg.write_text('{"mode": "off", "research": true}', encoding="utf-8")
        assert ql_research.research_budget(tmp_path, cfg, "2026-09-29") == 0

    def test_a_clone_names_its_own_config(self, tmp_path):
        assert ql_research.research_places(tmp_path) == (tmp_path / "_cache" / "querylog",
                                                         tmp_path / "_private" / "querylog.json")


class TestResearch:
    def setup(self, tmp_path, *cands, runs=1, checks=(), extra=()):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path, extra)
        calls, counted = [], []

        def call(prompt):
            calls.append(prompt)
            return reply(*cands)
        research = ql_research.Researcher(runs, call=call, fetcher=pages, counted=lambda: counted.append(1))
        return root, store, KbGate(root, checks=checks), research, calls, counted

    def test_facts_sources_and_a_conflict_are_added(self, tmp_path):
        other = cand(text="Windows LAPS supports Windows Server 2012 R2 after a later update.", quote=BAD_QUOTE)
        legacy = cand(text="Legacy Microsoft LAPS stays available for older operating systems.", quote=LEGACY_QUOTE,
                      conflicts_with=19)
        root, store, gate, research, calls, counted = self.setup(tmp_path, cand(), other, legacy)
        rc, said = run_gap_apply(store, gate, research)  # the gap step and research in one run
        assert rc == 0 and "gaps=1 research=1 facts=1 conflicts=1" in said[0], said
        assert len(calls) == len(counted) == 1 and not research.left()
        assert "How do I configure VMware Horizon instant clone pools?" in calls[0]
        assert "19: - The default password length is 14 characters. [DOC S101]" in calls[0]
        import kbid
        sid = kbid.source_id(PAGE_URL, "S")
        art = (root / "windows" / "laps.md").read_text(encoding="utf-8")
        assert ql_research.edit_problems("laps.md", ARTICLE_MD, art) == []
        lines = art.split("\n")
        assert lines[19] == f"- {cand()['text']} [DOC {sid}]" and lines[20:22] == ["", "## Reference"]
        assert f"sources: [S100, S101, {sid}]" in lines
        src = (root / "_sources.csv").read_text(encoding="utf-8")
        assert src.startswith(SOURCES_CSV) and src[len(SOURCES_CSV):].count("\n") == 1  # one row for one url
        assert src.endswith(f"{sid},{PAGE_URL},Windows LAPS platform support,Example Docs,"
                            f'"CC BY 4.0, stated on the page (test page)",copy,{DAY},,,,\n')
        conflicts = (root / "_conflicts.md").read_text(encoding="utf-8")
        assert conflicts.startswith("# Conflicts\n\n## windows/laps\n\n- **The default password length is 14 characters.**")
        assert f"[DOC {sid} vs S101] (topic: windows/laps)" in conflicts and GAP_ID in conflicts
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"]) == ("applied", "claim")
        assert [(p["to"], p["by"]) for p in rec["promotions"]] == [
            ("candidate-gap", "learn"), ("gap", "apply"), ("candidate-fact", "research"), ("claim", "research")]
        assert rec["observed"] == {"facts": 1, "conflicts": 1, "sources": [sid],
                                   "gate": ["fact 1: quote is not on the page"]}
        gaps = (root / "_gaps.md").read_text(encoding="utf-8")  # the claim closes its entry by the content rules
        (note,) = [ln for ln in gaps.split("\n") if ln.startswith("  - Resolved ")]
        assert f"added 1 fact from {sid} (finding {GAP_ID}) (topic: windows/laps)" in note, note
        assert ql_research.settled(ql_research.ledger_entry(gate, rec)[2])
        assert gate.indexed == 1 and ql_store.store_problems(store) == []
        first = tree(store), root_files(root)
        assert run_gap_apply(store, gate, ql_research.Researcher(1, call=calls.append, fetcher=pages)) == \
            (0, ["apply: nothing to apply"])  # a claim is not researched again
        assert (tree(store), root_files(root)) == first

    def test_a_quote_not_on_its_page_is_rejected(self, tmp_path):
        root, store, gate, research, calls, _ = self.setup(tmp_path, cand(quote=BAD_QUOTE))  # planted
        before = root_files(root)
        run_gap_apply(store, gate)
        gapped = root_files(root)
        assert gapped != before  # the gap entry
        rc, said = run_gap_apply(store, gate, research)
        assert rc == 0 and "research=1 facts=0 conflicts=0" in said[0] and "rejected=1" in said[0], said
        assert root_files(root) == gapped and gate.indexed == 0
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == (
            "rejected", "candidate-fact", ["fact 0: quote is not on the page"])
        assert ql_store.store_problems(store) == []

    def test_research_editing_an_existing_fact_line_is_put_back(self, tmp_path, monkeypatch):
        root, store, gate, research, _, _ = self.setup(tmp_path, cand())
        run_gap_apply(store, gate)
        before = root_files(root)
        add = ql_research.add_fact
        monkeypatch.setattr(ql_research, "add_fact", lambda text, line: add(text, line).replace(
            "is 14 characters", "is 16 characters"))  # planted: the writer also edits an existing fact line
        rc, said = run_gap_apply(store, gate, research)
        assert rc == 0 and "rejected=1" in said[0], said
        assert root_files(root) == before and gate.indexed == 0  # every file put back
        rec = by_id(store)[GAP_ID]
        assert rec["state"] == "rejected" and rec["stage"] == "candidate-fact"
        assert rec["observed"]["gate"] == ["laps.md: removes or edits an existing fact line: - The default password "
                                           "length is 14 characters. [DOC S101]"]

    def test_a_red_check_puts_everything_back(self, tmp_path):
        root, store, gate, research, _, _ = self.setup(tmp_path, cand(), checks=["ERROR windows/laps.md cites S9"])
        run_gap_apply(store, gate)
        before = root_files(root)
        run_gap_apply(store, gate, research)
        assert root_files(root) == before
        assert by_id(store)[GAP_ID]["observed"]["gate"] == ["ERROR windows/laps.md cites S9"]

    def test_at_most_the_daily_runs(self, tmp_path):
        root, store, gate, research, calls, counted = self.setup(tmp_path, cand(), runs=1, extra=("a6",))
        rc, said = run_gap_apply(store, gate, research)
        assert "gaps=2 research=1" in said[0], said
        assert len(calls) == len(counted) == 1
        stages = sorted(r["stage"] for r in by_id(store).values() if r["kind"] == "gap")
        assert stages == ["claim", "gap"]  # the second waits for another day
        rc, said = run_gap_apply(store, gate, ql_research.Researcher(0, call=calls.append, fetcher=pages))
        assert said == ["apply: nothing to apply"] and len(calls) == 1

    def test_no_research_leaves_gap_findings(self, tmp_path):
        root, store, gate, research, calls, _ = self.setup(tmp_path, cand())
        run_gap_apply(store, gate, None)
        assert by_id(store)[GAP_ID]["stage"] == "gap" and calls == []
        assert run_gap_apply(store, gate, None) == (0, ["apply: nothing to apply"])

    def test_a_failed_call_writes_nothing_and_counts(self, tmp_path):
        root, store, gate, _, _, _ = self.setup(tmp_path)
        run_gap_apply(store, gate)
        before = tree(store), root_files(root)
        counted = []

        def down(prompt):
            raise OSError("claude -p exited 1")
        rc, said = run_gap_apply(store, gate, ql_research.Researcher(2, call=down, counted=lambda: counted.append(1)))
        assert said == ["apply: nothing to apply (research runs=1, no reply)"] and counted == [1]
        assert (tree(store), root_files(root)) == before  # tried again on a later run

    @pytest.mark.parametrize("text,why", [
        ("no JSON here", "reply: no JSON object in the reply"),
        ('{"facts": "none"}', "reply: no facts list"),
        ('{"facts": [{"text": "x"}]}', "reply: fact 0 is malformed"),
    ])
    def test_a_reply_that_is_not_the_json_is_rejected(self, tmp_path, text, why):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        run_gap_apply(store, KbGate(root))
        before = root_files(root)
        run_gap_apply(store, KbGate(root), ql_research.Researcher(1, call=lambda p: text, fetcher=pages))
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == ("rejected", "gap", [why])
        assert root_files(root) == before

    @pytest.mark.parametrize("change,why", [
        ({"tag": "DER"}, "tag 'DER' is not one of DOC, COMMUNITY"),
        ({"url": "https://wiki.corp/laps"}, "url is not a public http(s) page"),
        ({"url": "ftp://docs.example.com/x"}, "url is not a public http(s) page"),
        ({"reuse": "free"}, "reuse 'free' is not a reuse class"),
        ({"licence": " "}, "title, publisher or licence is empty"),
        ({"text": "Short."}, "text is not one short sentence"),
        ({"text": "Windows LAPS does not support 2012 R2 at all. [DOC S100]"}, "text carries a tag"),
        ({"text": "The default password length is 14 characters."}, "text is already a fact"),
        ({"text": "Windows LAPS reads its settings from C:\\Users\\" + "anna.nowak\\laps.json on each device."},
         "leak scan flags"),  # a home path, joined at run time so the tracked-file leak scan does not flag it
        ({"conflicts_with": 3}, "conflicts_with 3 names no fact line"),
    ])
    def test_candidate_problems(self, change, why):
        facts = ql_research.fact_lines(ARTICLE_MD)
        assert [n for n, _ in facts] == [18, 19]
        assert ql_research.candidate_problems(cand(), facts) == []
        assert any(why in p for p in ql_research.candidate_problems(cand(**change), facts)), change

    def test_edit_problems(self):
        e = ql_research.edit_problems
        assert e("x/a.md", ARTICLE_MD, ARTICLE_MD.replace("## Reference", "- New. [DOC S1]\n\n## Reference")) == []
        assert e("x/a.md", ARTICLE_MD, ARTICLE_MD.replace("14", "16"))  # planted: an edited fact line
        assert e("x/a.md", ARTICLE_MD, ARTICLE_MD.replace("A test article.", "Other words.")) == []  # no fact line
        assert e("_gaps.md", GAPS_MD, GAPS_MD.replace("Looked somewhere", "Looked"))  # planted: an edited entry
        assert e("_sources.csv", SOURCES_CSV, SOURCES_CSV.replace("windows/laps.md,\n", "a.md;b.md,\n")) == []
        assert e("_sources.csv", SOURCES_CSV, SOURCES_CSV.replace("LAPS policy", "LAPS"))  # planted: a changed row
        assert e("_sources.csv", SOURCES_CSV, SOURCES_CSV.split("S101")[0])  # planted: a removed row
        assert e("x/a.md", None, "anything") == []  # a new file

    def test_source_rows_go_in_id_order(self):
        """A new source row goes where kbgit.py fix, which sorts the rows by id, would put it (planted: appended at
        the end, which fix would move)."""
        import kbgit
        text = SOURCES_CSV + "S-aaaaaaaa,https://a.example.com/,A,P,L,quote,2026-09-01,,,windows/laps.md,\n"
        new = ["S-mmmmmmmm,https://m.example.com/,M,P,L,quote,2026-09-28,,,windows/laps.md,",
               "S150,https://s.example.com/,S,P,L,quote,2026-09-28,,,windows/laps.md,"]
        got = ql_research.insert_rows(text, new)
        assert [ln.split(",")[0] for ln in got.splitlines()] == ["id", "S100", "S101", "S150", "S-aaaaaaaa", "S-mmmmmmmm"]
        assert kbgit.canon_csv(got, True) == got and ql_research.edit_problems("_sources.csv", text, got) == []
        appended = text + "".join(ln + "\n" for ln in new)
        assert kbgit.canon_csv(appended, True) != appended


LAPS_GAP_Q ="Can Windows LAPS back up the password of a Windows Server 2016 member server to Azure?"


@pytest.fixture(scope="module")
def researched(tmp_path_factory):
    """A kb copy and a store whose one lookup is a gap under the LAPS article: learn, then apply with research off
    (the gap entry), then with research on at one run a day (the recorded reply and page), then apply again.
    (home, store, outputs, the copy's files before, the copy's files after research)."""
    base = tmp_path_factory.mktemp("research")
    home = Path(copy_kb(str(base / "kb")))
    store = base / "store"
    run = store / "2026-09" / "20260928T130000Z-0000beef.jsonl"
    run.parent.mkdir(parents=True)
    header = {"run": run.stem, "pipeline": 1, "retrieval": 4, "kb_commit": "0" * 40,
              "counts": {"entries": 1, "dropped": 0, "waiting": 0}}
    entry = {"id": E("a4"), "surface": "prompt", "day": "2026-09-27", "tools": ["kb_pack"], "question": LAPS_GAP_Q,
             "verdict": "weak", "articles": [LAPS], "citations": [{"line": f"{LAPS}:18", "verdict": "weak"}],
             "cited": "pack", "judged": "missed"}
    run.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in (header, entry)), encoding="utf-8",
                   newline="\n")
    art = home / "kb" / "public" / "windows" / "laps.md"
    n, line = ql_research.fact_lines(art.read_text(encoding="utf-8"))[0]
    legacy = cand(text="Legacy Microsoft LAPS stays available for older operating systems.", quote=LEGACY_QUOTE,
                  conflicts_with=n)
    shutil.copy(PAGE, base / "page.html")
    replay = base / "research.json"
    replay.write_text(json.dumps({"replies": [reply(cand(), cand(text="Windows LAPS supports Windows Server 2012 R2 "
                                                                  "after a later update.", quote=BAD_QUOTE), legacy)],
                                  "pages": {PAGE_URL: "page.html"}}), encoding="utf-8")
    data = base / "data"
    cfg = data / "querylog" / "config.json"
    cfg.parent.mkdir(parents=True)
    env = querylog_env(data, home=str(home), base={**os.environ, "KB_INDEX": str(home / "_cache")})
    files = ("kb/public/windows/laps.md", "kb/public/_sources.csv", "kb/public/_conflicts.md", "kb/public/_gaps.md",
             "kb/public/_coverage.csv", "kb/public/_coverage.md")
    snap = lambda: {f: (home / f).read_bytes() for f in files}  # noqa: E731
    before, said = snap(), []
    ql = [sys.executable, str(home / "_tools" / "querylog.py")]
    for config, cmd in (('{"mode": "local"}', ["learn", "--store", str(store)]),
                        ('{"mode": "local"}', ["apply", "--store", str(store), "--replay-research", str(replay)]),
                        ('{"mode": "local", "research": true, "research_daily": 1}',
                         ["apply", "--store", str(store), "--replay-research", str(replay)]),
                        ('{"mode": "local", "research": true, "research_daily": 1}',
                         ["apply", "--store", str(store), "--replay-research", str(replay)])):
        cfg.write_text(config, encoding="utf-8")
        p = subprocess.run([*ql, *cmd], capture_output=True, text=True, encoding="utf-8", env=env, cwd=home,
                           timeout=900)
        assert p.returncode == 0, p.stdout + p.stderr
        said.append(p.stdout.strip())
        if len(said) == 3:
            after = snap()
    return home, store, env, said, before, after, (n, line), data


class TestResearchInKbCopy:
    def test_research_off_writes_the_gap_entry_only(self, researched):
        home, store, env, said, before, after, _, _ = researched
        assert "gaps=1" in said[1] and "research=" not in said[1], said
        text = (home / "kb" / "public" / "_gaps.md").read_text(encoding="utf-8")
        assert f"- **{LAPS_GAP_Q}** " in text and "(topic: windows/laps)" in text

    def test_research_adds_a_fact_a_source_and_a_conflict(self, researched):
        home, store, env, said, before, after, (n, line), _ = researched
        assert "research=1 facts=1 conflicts=1" in said[2], said
        import kbid
        sid = kbid.source_id(PAGE_URL, "S")
        rel = "kb/public/windows/laps.md"
        art = after[rel].decode("utf-8")
        assert f"- {cand()['text']} [DOC {sid}]" in art.split("\n")
        assert ql_research.edit_problems(rel, before[rel].decode("utf-8"), art) == []
        assert ql_research.edit_problems("kb/public/_sources.csv", before["kb/public/_sources.csv"].decode("utf-8"),
                                         after["kb/public/_sources.csv"].decode("utf-8")) == []
        import kbgit  # the new row sits in id order: kbgit.py fix, which sorts the rows by id, changes nothing
        sources = after["kb/public/_sources.csv"].decode("utf-8")
        assert kbgit.canon_csv(sources, True) == sources
        assert ql_research.insert_rows(before["kb/public/_sources.csv"].decode("utf-8"), [
            ln for ln in sources.splitlines() if ln.startswith(sid + ",")]) == sources
        conflicts = after["kb/public/_conflicts.md"].decode("utf-8")
        assert ql_research.edit_problems("kb/public/_conflicts.md", before["kb/public/_conflicts.md"].decode("utf-8"),
                                         conflicts) == []
        (entry,) = [ln for ln in conflicts.split("\n") if GAP_ID in ln]
        assert f"(line {n} of the article)" in entry and entry.endswith("(topic: windows/laps)")
        assert json.loads((Path(researched[7]) / "querylog" / ql_research.RESEARCH_RUNS_NAME).read_text(
            encoding="utf-8"))["runs"] == 1

    def test_check_passes_after_the_research_run(self, researched):
        home, store, env, *_ = researched
        for tool, want in (("check.py", "errors=0"), ("build_index.py", "")):
            argv = [sys.executable, str(home / "_tools" / tool)] + (["--check"] if tool == "build_index.py" else [])
            p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=env, cwd=home, timeout=600)
            assert p.returncode == 0 and want in p.stdout, p.stdout[-600:] + p.stderr[-600:]
        assert ql_store.store_problems(store) == []
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"]) == ("applied", "claim")

    def test_a_second_run_changes_nothing(self, researched):
        home, store, env, said, before, after, *_ = researched
        assert said[3] == "apply: nothing to apply", said
        files = {f: (home / f).read_bytes() for f in after}
        assert files == after


# ---------------------------------------------------------------- digest and status (Query log item 9)

W39_RUN = "20260927T100000Z-0000cafe"  # a second run file, in ISO week 2026-W39
W39_FINDINGS = "20260927T230000Z-0000d1ce"  # findings written in 2026-W39
W40_FINDINGS = "20260929T080000Z-0000d2ce"  # findings written in 2026-W40: after the week's end


def f_rec(kind, entry=None, state="open", **kw):
    rec = {"id": ql_store.finding_id(kind, entry if entry else kw.get("signal", ""), kw.get("host", "")),
           "kind": kind, "state": state}
    if entry:
        rec["id"] = ql_store.finding_id(kind, entry)
        rec.update(stage=kw.pop("stage", "miss"), entry=entry)
    rec.update(kw)
    return rec


def write_store_file(path, header, objs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in [header, *objs]), encoding="utf-8",
                    newline="\n")


def digest_store(dst):
    """The fixture store plus a run file and findings files around ISO week 2026-W39: two misses fixed (one since,
    one by apply), a gap still open, two open source findings, and a later record that the week's end must not see."""
    store = learn_store(dst.parent, dst.name)
    a = "55555555-0000-4000-8000-0000000000"
    extra = {"id": "66666666-0000-4000-8000-0000000000a1", "surface": "kb_ask", "day": "2026-09-27", "tools": ["kb_ask"],
             "route": "good", "question": "Which port does WinRM over HTTPS use?", "verdict": "good"}
    write_store_file(store / "2026-09" / f"{W39_RUN}.jsonl",
                     {"run": W39_RUN, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                      "counts": {"entries": 1, "dropped": 2, "waiting": 0}}, [extra])
    lap = "public/windows/laps.md"
    w39 = [f_rec("eval", a + "a1", "fixed-since", expect=lap),
           f_rec("eval", a + "a3", "applied", expect="public/intune/win32-apps.md"),
           f_rec("expansion", a + "a3", "applied", article="public/intune/win32-apps.md"),
           f_rec("gap", a + "a4", stage="candidate-gap",
                 promotions=[{"from": "miss", "to": "candidate-gap", "by": "learn"}]),
           f_rec("eval", a + "a2", expect=lap),
           f_rec("alias", a + "a2", article=lap, terms=["zqxlapsor"]),
           f_rec("source", signal="stage", host="learn.microsoft.com", level=0, needs=1, triggers=["failures"]),
           f_rec("source", signal="stage", host="arxiv.org", level=0, needs=1, triggers=["failures"])]
    w40 = [f_rec("alias", a + "a2", "applied", article=lap, terms=["zqxlapsor"]),
           f_rec("eval", a + "a2", "applied", expect=lap)]
    for run, recs in ((W39_FINDINGS, w39), (W40_FINDINGS, w40)):
        write_store_file(store / "findings" / "2026-09" / f"{run}.jsonl",
                         {"run": run, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                          "counts": {"findings": len(recs)}}, recs)
    return store


DIGEST_W39 = """query log digest 2026-W39 (2026-09-21 to 2026-09-27)
lookups: 16 (prompt 5, kb_ask 1, tool_fetch 10)
verdicts: good 3, weak 1, none 2, no verdict 10
judged: answered 1, partly 1, missed 3, not judged 11
misses: 4, fixed: 2 (by the kb since 1, by apply 1, by research 0)
fetches: 13, failed 12, result characters 1079632
usage: 0 of 16 lookups
runs: 1, entries dropped by redaction 2
finding records written: 8
findings by kind and state at the week's end:
  eval: open 1, fixed-since 1, applied 1
  alias: open 1
  expansion: applied 1
  gap: open 1
  source: open 2"""


class TestDigest:
    def test_two_copies_of_one_store_give_identical_output(self, tmp_path):
        outs = []
        for name in ("one", "two"):
            store = digest_store(tmp_path / name / "store")
            assert ql_store.store_problems(store) == []
            p = subprocess.run([sys.executable, QL, "digest", "--store", str(store), "--week", "2026-W39"],
                               capture_output=True, timeout=120, cwd=str(tmp_path / name))
            assert p.returncode == 0, p.stderr
            outs.append(p.stdout)
        assert outs[0] == outs[1]
        assert outs[0].decode("utf-8").replace("\r\n", "\n") == DIGEST_W39 + "\n"

    def test_the_default_week_is_the_newest_entrys(self, tmp_path):
        store = digest_store(tmp_path / "store")
        week, lines_, found = ql_report.digest(store)
        assert (week, "\n".join(lines_), found) == ("2026-W39", DIGEST_W39, True)
        assert ql_report.digest(store) == ql_report.digest(store)  # nothing but the store goes in

    def test_the_weeks_end_bounds_the_findings(self, tmp_path):
        store = digest_store(tmp_path / "store")
        week, lines_, found = ql_report.digest(store, "2026-W40")
        text = "\n".join(lines_)
        assert found and "lookups: 0\n" in text and "finding records written: 2" in text
        assert "  eval: fixed-since 1, applied 2" in text and "  alias: applied 1" in text
        assert "runs: 1," in text  # the fixture's run file, written 2026-09-28

    def test_an_empty_or_missing_store_and_a_bad_week(self, tmp_path):
        assert ql_report.digest(tmp_path / "none") == (None, ["query log digest: the store holds no run file"], False)
        store = digest_store(tmp_path / "store")
        assert ql_report.digest(store, "2026-W30")[2] is False
        with pytest.raises(ValueError):
            ql_report.digest(store, "2026-09-27")
        p = subprocess.run([sys.executable, QL, "digest", "--store", str(store), "--week", "last"], capture_output=True,
                           timeout=120)
        assert p.returncode == 2 and b"not an ISO week" in p.stderr

    def test_distill_sums_result_characters_per_fetch(self):
        import redact
        rows = [{"id": "77777777-0000-4000-8000-000000000001", "ts": "2026-09-27T08:00:00.000Z", "surface": "prompt",
                 "prompt": "kb: laps", "kb_intent": "lookup"}]
        for i, c in enumerate((10, 5, None)):
            rows.append({"id": str(uuid.uuid4()), "ts": f"2026-09-27T08:00:0{i + 1}.000Z", "surface": "fetch",
                         "tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/a", "outcome": "unknown",
                         **({"chars": c} if c is not None else {})})
        entry, _, _ = ql_distill.entry_of(rows, redact.known())
        assert entry["fetches"] == [{"tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/a",
                                     "outcome": "unknown", "n": 3, "chars": 15}]


class TestDigestHook:
    MONDAY = datetime.datetime(2026, 9, 28, 7, 0, tzinfo=datetime.timezone.utc)  # 2026-W40: shows 2026-W39

    @pytest.fixture
    def qdir(self, tmp_path, monkeypatch):
        q = tmp_path / "querylog"
        monkeypatch.setattr(ql_report, "places", lambda: (q, q / "config.json"))
        return q

    def test_the_first_session_of_a_week_shows_last_weeks_digest_once(self, tmp_path, qdir):
        store = digest_store(tmp_path / "store")
        line = ql_report.digest_hook(self.MONDAY, store)
        assert json.loads(line) == {"systemMessage": DIGEST_W39}
        assert (qdir / ql_report.DIGEST_MARKER).read_text(encoding="utf-8") == "2026-W40\n"
        assert ql_report.digest_hook(self.MONDAY + datetime.timedelta(days=6, hours=16), store) is None  # Sunday
        nxt = ql_report.digest_hook(self.MONDAY + datetime.timedelta(days=7), store)  # 2026-W41 shows 2026-W40
        assert json.loads(nxt)["systemMessage"].startswith("query log digest 2026-W40 ")

    def test_off_disabled_empty_and_over_budget_show_nothing(self, tmp_path, qdir, monkeypatch):
        store = digest_store(tmp_path / "store")
        qdir.mkdir(parents=True)
        (qdir / "config.json").write_text('{"mode": "off"}', encoding="utf-8")
        assert ql_report.digest_hook(self.MONDAY, store) is None and not (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / "config.json").unlink()
        (qdir / "DISABLED").touch()
        assert ql_report.digest_hook(self.MONDAY, store) is None and not (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / "DISABLED").unlink()
        late = datetime.datetime(2026, 12, 1, tzinfo=datetime.timezone.utc)
        assert ql_report.digest_hook(late, store) is None  # an empty week
        assert (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / ql_report.DIGEST_MARKER).unlink()
        monkeypatch.setattr(ql_report, "DIGEST_BUDGET_S", -1)  # planted: reading the store took too long
        assert ql_report.digest_hook(self.MONDAY, store) is None
        assert (qdir / ql_report.DIGEST_MARKER).read_text(encoding="utf-8") == "2026-W40\n"  # not tried again

    def test_the_hook_command_prints_at_most_one_json_line_and_exits_0(self, tmp_path):
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, QL, "digest", "--hook"], input=json.dumps(session_start()).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=60)
        assert p.returncode == 0 and time.monotonic() - t0 < ql_report.DIGEST_HOOK_TIMEOUT_S, p.stderr
        out = p.stdout.decode("utf-8").strip()
        assert out == "" or list(json.loads(out)) == ["systemMessage"]
        assert (tmp_path / "querylog" / ql_report.DIGEST_MARKER).exists()
        p = subprocess.run([sys.executable, QL, "digest", "--hook"], input=b"not json", capture_output=True,
                           env=querylog_env(tmp_path), timeout=60)
        assert (p.returncode, p.stdout) == (0, b"")  # shown once this week already


class StubRun:
    """git, glab and gh answers for status: origin's url, signed in or not, the open merge requests, the log."""

    def __init__(self, url="git@gitlab.corp.example.com:grp/kb.git", signed=True, mrs=None, log="", api_ok=True):
        self.url, self.signed, self.mrs, self.log, self.api_ok, self.calls = url, signed, mrs or [], log, api_ok, []

    def __call__(self, argv, cwd=None):
        self.calls.append(argv)
        if argv[1:3] == ["remote", "get-url"]:
            return (0, self.url + "\n", "") if self.url else (2, "", "error: No such remote 'origin'")
        if argv[1:2] == ["log"]:
            return 0, self.log, ""
        if argv[1:3] == ["auth", "status"]:
            return (0, "", "") if self.signed else (1, "", "You are not logged into any hosts")
        return (0, json.dumps(self.mrs), "") if self.api_ok else (1, "", "HTTP 401")


def status_lines(store, run):
    said = []
    assert ql_report.status(store, home=str(store.parent), run=run, out=said.append) == 0
    return said


class TestStatus:
    LOG = ("1111111\x1fchore(kb): query log apply 20260927T230000Z-0000d1ce\x1feval, expansion, querylog\x1e\n"
           "2222222\x1frevert: query log commit 3333333aa\x1frevert\x1e\n"
           "4444444\x1fdocs(kb): a person's commit\x1f\x1e\n")

    def test_the_three_lists_on_gitlab(self, tmp_path):
        store = digest_store(tmp_path / "store")
        mrs = [{"iid": 12, "source_branch": "querylog/20260927T230000Z-0000d1ce", "title": "chore(kb): query log apply",
                "web_url": "https://gitlab.corp.example.com/grp/kb/-/merge_requests/12"},
               {"iid": 13, "source_branch": "feature/x", "title": "a person's MR", "web_url": "u"}]
        run = StubRun(mrs=mrs, log=self.LOG)
        said = status_lines(store, run)
        assert said == [
            "open source findings, most result characters first: 2",
            f"  1018432 chars  learn.microsoft.com  stage: level 0, needs 1 (failures)  "
            f"{ql_store.finding_id('source', 'stage', 'learn.microsoft.com')}",
            f"  0 chars  arxiv.org  stage: level 0, needs 1 (failures)  "
            f"{ql_store.finding_id('source', 'stage', 'arxiv.org')}",
            "open conflict merge requests (glab on gitlab.corp.example.com): 1",
            "  !12 querylog/20260927T230000Z-0000d1ce  chore(kb): query log apply  "
            "https://gitlab.corp.example.com/grp/kb/-/merge_requests/12",
            "reverted automatic commits: 1",
            "  2222222 revert: query log commit 3333333aa"]
        assert ["glab", "api", "--hostname", "gitlab.corp.example.com",
                "projects/grp%2Fkb/merge_requests?state=opened&target_branch=main&per_page=100"] in run.calls

    def test_github_lists_pull_requests(self, tmp_path):
        store = digest_store(tmp_path / "store")
        prs = [{"number": 4, "headRefName": "querylog/20260927T230000Z-0000d1ce", "title": "t", "url": "https://x/4"}]
        run = StubRun(url="https://github.com/o/r.git", mrs=prs)
        said = status_lines(store, run)
        assert "open conflict merge requests (gh on github.com): 1" in said
        assert "  #4 querylog/20260927T230000Z-0000d1ce  t  https://x/4" in said
        assert ["gh", "pr", "list", "-R", "github.com/o/r", "--base", "main", "--state", "open",
                "--json", "number,title,headRefName,url", "-L", "100"] in run.calls

    @pytest.mark.parametrize("run,note", [
        (StubRun(signed=False), "not checked: glab is not signed in to gitlab.corp.example.com (You are not logged"),
        (StubRun(api_ok=False), "not checked: glab api failed (HTTP 401)"),
        (StubRun(url=None), "not checked: no remote origin"),
    ])
    def test_merge_requests_are_skipped_with_a_note(self, tmp_path, run, note):
        said = status_lines(digest_store(tmp_path / "store"), run)
        assert any(line.startswith("open conflict merge requests: " + note) for line in said), said
        if not run.signed or not run.url:
            assert not [c for c in run.calls if c[:2] in (["glab", "api"], ["gh", "pr"])]  # no API call

    @pytest.mark.git
    def test_reverted_commits_come_from_the_trailer(self, tmp_path):
        """In a real repository: the KB-Auto trailers of git log, one revert among them."""
        repo = Repo(tmp_path / "clone")
        os.makedirs(repo.path)
        repo.git("init", "-q")
        for text, msg in (("a\n", "chore(kb): query log apply x\n\nKB-Auto: eval"),
                          ("b\n", "revert: query log commit abc\n\nKB-Auto: revert"),
                          ("c\n", "docs: a body that names KB-Auto: revert\n\nno trailer here.\n\nOther: x")):
            repo.write("a.txt", text)
            repo.git("add", "a.txt")
            repo.git("commit", "-q", "-m", msg)

        def run(argv, cwd=None):
            p = subprocess.run(argv, cwd=cwd, env=repo.env, capture_output=True, text=True, encoding="utf-8")
            return p.returncode, p.stdout, p.stderr
        got = ql_report.reverted_commits(repo.path, run)
        assert [s for _, s in got] == ["revert: query log commit abc"]


# ---- the revert's bug carries the failure fingerprint (backlog.py's) and joins an open bug with the same one

def fingerprint_forge(jobs, logs):
    """A signed-in glab stub for the revert's pipeline: its failed jobs and their traces (no network)."""
    def run(argv, cwd=None):
        if argv[1:3] == ["auth", "status"]:
            return 0, "", "Logged in"
        if "/jobs?scope=failed" in argv[-1]:
            return 0, json.dumps(jobs), ""
        m = re.search(r"/jobs/(\d+)/trace$", argv[-1])
        return (0, logs.get(int(m.group(1)), ""), "") if m else (1, "", "unexpected call")
    return run


def fingerprint_pusher(tmp_path, run):
    (tmp_path / "worktree" / "kb" / "_self" / "backlog").mkdir(parents=True)
    return ql_deliver.Pusher(tmp_path, tmp_path / "q", run, None, lambda *_: None, cloud=False)


def test_revert_fingerprint_is_backlogs_and_a_second_pipeline_joins_the_open_bug(tmp_path):
    import backlog
    url = "https://gitlab.example.com/team/kb.git"
    jobs = [{"id": 11, "name": "lint", "status": "failed"}, {"id": 10, "name": "check", "status": "failed"}]
    log = "2026-09-01T10:00:00Z FAILED _tools/test_x.py::test_a - assert 3 == 4\n"
    run = fingerprint_forge(jobs, {10: log, 11: "lint error\n"})
    failure, fp = ql_deliver.pipeline_failure(url, {"id": 901}, run)
    assert failure == "_tools/test_x.py::test_a"
    assert fp == backlog.failure_fingerprint("check", "_tools/test_x.py::test_a")  # the first failed job by name
    pusher = fingerprint_pusher(tmp_path, run)
    pipe = {"id": 901, "url": "https://x/901", "status": "failed", "failure": failure, "fingerprint": fp}
    first = pusher.file_bug("a" * 40, {"F1": {}}, pipe)
    bl = backlog.Backlog(pusher.wt)
    assert list(bl.items) == [first] and bl.items[first]["severity"] == "S2"  # no open bug: exactly one S2 bug
    assert bl.items[first]["links"] == ["pipeline 901", f"fingerprint {fp}"]
    # planted: a later revert's pipeline that fails the same way (other job id, time and numbers) joins that bug
    log2 = "2026-09-03T08:15:42Z FAILED _tools/test_x.py::test_a - assert 7 == 9\n"
    run2 = fingerprint_forge([{"id": 20, "name": "check", "status": "failed"}], {20: log2})
    failure2, fp2 = ql_deliver.pipeline_failure(url, {"id": 902}, run2)
    assert fp2 == fp
    again = pusher.file_bug("b" * 40, {}, {"id": 902, "failure": failure2, "fingerprint": fp2})
    bl = backlog.Backlog(pusher.wt)
    assert again == first and list(bl.items) == [first]  # no second bug
    assert bl.items[first]["links"] == ["pipeline 901", f"fingerprint {fp}", "pipeline 902"]
    assert pusher.file_bug("c" * 40, {}, {"id": 902, "fingerprint": fp}) is None  # the pipeline is already named
    # a different failure files a second bug
    other = pusher.file_bug("d" * 40, {}, {"id": 903, "fingerprint": backlog.failure_fingerprint("check", "other")})
    assert other not in (None, first) and len(backlog.Backlog(pusher.wt).items) == 2


def test_revert_fingerprint_unreadable_pipeline_files_a_bug_without_one(tmp_path):
    import backlog
    url = "https://gitlab.example.com/team/kb.git"
    run = fingerprint_forge([], {})
    assert ql_deliver.pipeline_failure(url, {"id": 5}, run) == ("", None)
    assert ql_deliver.pipeline_failure(url, {}, run) == ("", None)
    pusher = fingerprint_pusher(tmp_path, run)
    bug = pusher.file_bug("e" * 40, {}, {"id": 5, "failure": "", "fingerprint": None})
    assert backlog.Backlog(pusher.wt).items[bug]["links"] == ["pipeline 5"]
