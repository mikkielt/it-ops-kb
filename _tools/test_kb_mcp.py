"""The `kb` MCP server and the Claude Code plugin that ships it (`python3 _tools/tests.py -k mcp`).

TestKbServer    _tools/kb_mcp.py as a subprocess over stdio: the legacy handshake (initialize, then
                notifications/initialized), tools/list (every description marked as documentation facts, only kb_pack
                always loaded, response_format on the list tools), kb_search (hits with path:line and source urls;
                the not-found note), kb_show, kb_source, kb_status, the 2026-07-28 server/discover and its version
                check, resultType on every result, JSON-RPC errors (parse error, unknown method or tool), stdout
                carrying only JSON-RPC, exit on EOF; kb_pack (coverage verdict, fact lines, url footer; a batch of
                questions with a verdict each and one footer), kb_audit, kb_facts (concise at least 30% smaller than
                detailed), kb_source with cited, kb_topics_for.
TestPluginManifest  .claude-plugin/marketplace.json and the two plugins: it-ops-kb (from the root: the kb server, the
                read-only kb-lookup, kb-review-workspace and kb-gap skills, the kb-lookup and kb-reviewer agents listed by path
                so the kb's agents/ articles never load, the kb: hook) and it-ops-kb-docs (the three documentation
                servers and a PreToolUse hook blocking submit_feedback); no root .mcp.json (it would load into
                it-ops-kb); no pinned version (users track commits); rag.py named only as the clone form; the GitLab
                SSH remote. With the `claude` CLI installed, `claude plugin validate` passes for both.
"""
import json, os, re, shutil, subprocess, sys

import pytest

from conftest import KB, P, Q, TOOLS, git_env

SERVER = os.path.join(TOOLS, "kb_mcp.py")
REMOTE = "git@gitlab.com:mikkielt/it-ops-kb.git"
DOCS_PLUGIN = ".claude-plugin/it-ops-kb-docs"


def load(rel):
    with open(os.path.join(KB, rel), encoding="utf-8") as f:
        return json.load(f)


class TestKbServer:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def server(cls):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "kb_search", "arguments": {"query": "kerberos constrained delegation", "k": 3,
                                                           "response_format": "detailed"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "kb_search", "arguments": {"query": "zanzibarquux flibbertigibbet"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
             "params": {"name": "kb_show", "arguments": {"path": "README.md:1", "n": 3}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "kb_source", "arguments": {"ids": ["S100", "S99999"]}}},
            {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "kb_status", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "kb_show", "arguments": {"path": "../etc/passwd"}}},
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 10, "method": "no/such/method"},
            {"jsonrpc": "2.0", "id": 11, "method": "server/discover",
             "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}},
            {"jsonrpc": "2.0", "id": 12, "method": "tools/list",
             "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "1999-01-01"}}},
            {"jsonrpc": "2.0", "id": 13, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "Does deleting an Entra device delete its BitLocker keys?"}}},
            {"jsonrpc": "2.0", "id": 14, "method": "tools/call",
             "params": {"name": "kb_audit", "arguments": {"prefix": "ad", "status": "complete"}}},
            {"jsonrpc": "2.0", "id": 15, "method": "tools/call",
             "params": {"name": "kb_facts", "arguments": {"prefix": "ad/computer-attributes", "tags": ["UNK"]}}},
            {"jsonrpc": "2.0", "id": 16, "method": "tools/call",
             "params": {"name": "kb_source", "arguments": {"ids": ["S100"], "cited": True}}},
            {"jsonrpc": "2.0", "id": 17, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"questions": [
                 "Does deleting an Entra device delete its BitLocker keys?", "When is NTLMv1 disabled by default?"]}}},
            {"jsonrpc": "2.0", "id": 18, "method": "tools/call",
             "params": {"name": "kb_facts", "arguments": {"prefix": "agents"}}},
            {"jsonrpc": "2.0", "id": 19, "method": "tools/call",
             "params": {"name": "kb_facts", "arguments": {"prefix": "agents", "response_format": "detailed"}}},
            {"jsonrpc": "2.0", "id": 20, "method": "tools/call",
             "params": {"name": "kb_topics_for", "arguments": {"text": "new PublicClientApplication(c); fetch('/AdminService/wmi/SMS_R_System')"}}},
            {"jsonrpc": "2.0", "id": 21, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "x", "response_format": "verbose"}}},
            {"jsonrpc": "2.0", "id": 22, "method": "tools/call",
             "params": {"name": "kb_topics_for", "arguments": {"paths": [TOOLS + "/kb_mcp.py", "no/such/dir"]}}},
            {"jsonrpc": "2.0", "id": 23, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "Does deleting an Entra device delete its BitLocker keys?",
                                                         "root": "public"}}},
            {"jsonrpc": "2.0", "id": 24, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "bitlocker keys", "root": "no-such-root"}}},
            {"jsonrpc": "2.0", "id": 25, "method": "tools/call",
             "params": {"name": "kb_show", "arguments": {"path": Q("auth/kerberos.md") + ":1", "n": 1}}},
        ]
        stdin = "".join(json.dumps(m) + "\n" for m in msgs) + "this is not json\n"
        cls.proc = subprocess.run([sys.executable, SERVER], input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=os.sep)
        cls.lines = [ln for ln in cls.proc.stdout.splitlines() if ln.strip()]
        cls.replies = [json.loads(ln) for ln in cls.lines]
        cls.by_id = {r.get("id"): r for r in cls.replies}

    def text(self, msg_id):
        r = self.by_id[msg_id]["result"]
        return r["isError"], r["content"][0]["text"]

    def test_exits_on_eof_and_stdout_is_only_jsonrpc(self):
        assert self.proc.returncode == 0, self.proc.stderr
        assert len(self.lines) == 26, "one reply per request, none for the notification"  # 25 requests + parse error
        for r in self.replies:
            assert r["jsonrpc"] == "2.0"

    def test_initialize(self):
        r = self.by_id[1]["result"]
        assert r["protocolVersion"] == "2025-06-18"
        assert "tools" in r["capabilities"]
        assert r["serverInfo"]["name"] == "kb"
        assert "UNK" in r["instructions"]

    def test_tools_list(self):
        tools = {t["name"]: t for t in self.by_id[2]["result"]["tools"]}
        assert sorted(tools) == ["kb_audit", "kb_facts", "kb_pack", "kb_search", "kb_show", "kb_source", "kb_status",
                                         "kb_topics_for"]
        for t in tools.values():
            assert t["inputSchema"]["type"] == "object"
            assert t["annotations"]["readOnlyHint"]
            assert t["description"].startswith("Documentation facts from it-ops-kb (not live device or directory data)"), \
                            f"{t['name']}: a host's live MECM/AD tools must not be confused with the kb"
        assert tools["kb_search"]["inputSchema"]["required"] == ["query"]
        always = [n for n, t in tools.items() if t.get("_meta", {}).get("anthropic/alwaysLoad")]
        assert always == ["kb_pack"], "only kb_pack skips tool search; the rest stay deferred"
        for n in ("kb_pack", "kb_facts", "kb_audit", "kb_search"):
            assert tools[n]["inputSchema"]["properties"]["response_format"]["enum"] == ["concise", "detailed"]
            assert tools[n]["inputSchema"]["properties"]["root"]["type"] == "string", f"{n} takes a root filter"
        assert tools["kb_pack"]["inputSchema"]["properties"]["response_format"]["default"] == "detailed"
        assert tools["kb_facts"]["inputSchema"]["properties"]["response_format"]["default"] == "concise"

    def test_kb_search_cites_paths_and_urls(self):
        err, text = self.text(3)
        assert not err
        assert re.search(r"(?m)^\[\d+(\.\d+)?\] [\w./-]+\.(md|csv):\d+  § ", text)
        assert re.search(r"(?m)^  -> S[-\w]+  https://", text)

    def test_kb_pack_audit_facts_cited(self):
        err, text = self.text(13)
        assert not err
        assert text.startswith("coverage: good"), text[:200]
        assert re.search(rf"(?m)^- {re.escape(Q('entra/bitlocker-key-deletion.md'))}:\d+ ", text), "paths print qualified"
        assert re.search(r"(?m)^  -> S[-\w]+  https://", text)
        err, text = self.text(14)
        assert not err
        assert f"| {Q('ad/computer-attributes.md')} | complete |" in text
        err, text = self.text(15)
        assert not err
        assert re.search(r"facts=\d+", text)
        err, text = self.text(16)
        assert not err
        assert re.search(r"cited at [\w/.-]+:\d+", text)

    def test_kb_pack_batch(self):
        err, text = self.text(17)
        assert not err
        assert len(re.findall(r"(?m)^# Q\d: ", text)) == 2
        assert len(re.findall(r"(?m)^coverage: ", text)) == 2, "a verdict per question"
        assert text.count("\nsources:") == 1, "one shared footer"
        err, text = self.text(21)
        assert err
        assert "response_format" in text

    def test_concise_facts_are_smaller(self):
        (e1, concise), (e2, detailed) = self.text(18), self.text(19)
        assert not (e1 or e2)
        assert re.search(r"facts=\d+", concise).group(0) == re.search(r"facts=\d+", detailed).group(0)
        assert len(concise) <= 0.7 * len(detailed), "concise must be at least 30% smaller"

    def test_kb_topics_for(self):
        err, text = self.text(20)
        assert not err
        assert re.search(rf"(?m)^- {Q('mecm/adminservice')}  .*AdminService", text), "topics print qualified"
        assert re.search(rf"(?m)^- {Q('auth/msal-public-client')}  PublicClientApplication \(1, text:1\)", text)
        err, text = self.text(22)
        assert not err
        assert "skipped: no/such/dir: no such file or directory" in text

    def test_kb_search_says_when_the_kb_lacks_it(self):
        err, text = self.text(4)
        assert not err
        assert "note: not found anywhere" in text
        assert "no match" in text

    def test_kb_show_and_its_bounds(self):
        err, text = self.text(5)
        assert not err
        assert "# README.md lines 1-3 of" in text
        assert "it-ops-kb" in text
        err, text = self.text(8)
        assert err
        assert "not a path inside the kb" in text
        err, text = self.text(25)
        assert not err
        assert text.startswith(f"# {Q('auth/kerberos.md')} lines 1-1 of"), text[:80]

    def test_root_filter(self):
        err, text = self.text(23)
        assert not err
        assert text == self.text(13)[1], "the public root alone gives the same pack when it is the only root"
        err, text = self.text(24)
        assert err
        assert "no root 'no-such-root'" in text and "roots: public" in text

    def test_kb_source(self):
        err, text = self.text(6)
        assert not err
        assert re.search(r"S100  .+\n  url: https?://", text)
        assert "S99999  UNKNOWN id" in text

    def test_kb_status(self):
        err, text = self.text(7)
        assert not err
        for key in ("kb_dir:", "commit:", "census_log:", "sources:", "newest_retrieved_utc:", "topics:", "roots: public (prefix S"):
            assert key in text

    def test_errors(self):
        assert self.by_id[9]["error"]["code"] == -32602
        assert self.by_id[10]["error"]["code"] == -32601
        assert self.by_id[None]["error"]["code"] == -32700
        e = self.by_id[12]["error"]
        assert (e["code"], e["data"]["requested"]) == (-32022, "1999-01-01")
        assert "2026-07-28" in e["data"]["supported"]

    def test_server_discover(self):
        r = self.by_id[11]["result"]
        assert "2026-07-28" in r["supportedVersions"]
        assert "tools" in r["capabilities"]
        assert r["cacheScope"] == "public"
        assert r["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "kb"

    def test_every_result_has_result_type(self):
        """2026-07-28 requires resultType on every result: Claude Code drops a tools/list without it (no kb tools)."""
        for r in self.replies:
            if "result" in r:
                assert r["result"].get("resultType") == "complete", r.get("id")


class TestPluginManifest:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def manifests(cls):
        cls.mkt = load(".claude-plugin/marketplace.json")
        cls.plugin = load(".claude-plugin/plugin.json")
        cls.docs = load(DOCS_PLUGIN + "/.claude-plugin/plugin.json")
        cls.servers = load(DOCS_PLUGIN + "/.mcp.json")["mcpServers"]

    def test_two_plugins_kb_and_docs(self):
        entries = {e["name"]: e for e in self.mkt["plugins"]}
        assert sorted(entries) == ["it-ops-kb", "it-ops-kb-docs"]
        assert entries["it-ops-kb"]["source"] == "."
        assert entries["it-ops-kb-docs"]["source"] == "./" + DOCS_PLUGIN
        assert self.plugin["name"] == "it-ops-kb", "entry name must equal the manifest name"
        assert self.docs["name"] == "it-ops-kb-docs"
        for obj in (self.mkt, *entries.values(), self.plugin, self.docs):
            assert "version" not in obj, "a pinned version would keep users on one copy; the commit sha tracks updates"
        assert self.plugin["repository"] == REMOTE
        assert self.docs["repository"] == REMOTE

    def test_no_docs_servers_in_the_kb_plugin(self):
        """A plugin sourced from the root loads a root .mcp.json whatever plugin.json says, so the docs servers live
        only in the docs plugin; a host that already has microsoft-learn installs only it-ops-kb."""
        assert not os.path.exists(os.path.join(KB, ".mcp.json")), "a root .mcp.json would load into it-ops-kb"
        assert sorted(self.plugin["mcpServers"]) == ["kb"]
        assert sorted(self.servers) == ["claude-code-docs", "mcp-docs", "microsoft-learn"]
        assert "mcpServers" not in self.docs

    def test_only_read_only_skills(self):
        assert self.plugin["skills"] == ["./.claude/skills/kb-lookup", "./.claude/skills/kb-review-workspace",
                                         "./.claude/skills/kb-gap"]
        assert not os.path.isdir(os.path.join(KB, "skills")), "a root skills/ directory would be loaded too"
        for rel in self.plugin["skills"] + self.plugin["agents"]:
            path = os.path.join(KB, rel, "SKILL.md") if not rel.endswith(".md") else os.path.join(KB, rel)
            with open(path, encoding="utf-8") as f:
                fm = f.read().split("\n---", 1)[0]
            for w in ("Write", "Edit", "NotebookEdit", "Bash", "git"):
                assert not re.search(rf"(?m)^(allowed-tools|tools):.*\b{w}\b", fm), f"{rel} may not use {w}"
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            lookup = f.read()
        assert "disable-model-invocation" not in lookup.split("\n---", 1)[0]
        assert f"mcp__plugin_{self.plugin['name']}_kb__kb_pack" in lookup
        with open(os.path.join(KB, ".claude/skills/kb-review-workspace/SKILL.md"), encoding="utf-8") as f:
            fm = f.read().split("\n---", 1)[0]
        for line in ("disable-model-invocation: true", "context: fork", "agent: it-ops-kb:kb-reviewer"):
            assert line in fm
        # the gap report is drafted for the user to paste: kb tools only, nothing written, sent or posted
        with open(os.path.join(KB, ".claude/skills/kb-gap/SKILL.md"), encoding="utf-8") as f:
            fm, body = f.read().split("\n---", 1)
        assert "disable-model-invocation: true" in fm
        tools = re.search(r"(?m)^allowed-tools:(.*)$", fm).group(1).split()
        assert tools and all(re.fullmatch(r"mcp__(plugin_it-ops-kb_kb|kb)__kb_\w+", t) for t in tools), tools
        assert "submit_feedback" in re.search(r"(?m)^disallowed-tools:(.*)$", fm).group(1)
        assert "corp.example.com" in body, "the draft replaces organisation data with the kb's placeholders"

    def test_agents(self):
        """The lookup agent is lean (kb tools only, small model, no CLAUDE.md); the reviewer reads code."""
        assert self.plugin["agents"] == ["./.claude/agents/kb-lookup.md", "./.claude/agents/kb-reviewer.md"]
        assert os.path.isdir(os.path.join(KB, P("agents"))), "the kb's agents/ articles: never a default scan"

        def fm(rel):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                head = f.read().split("\n---", 1)[0]
            return dict(re.findall(r"(?m)^(\w+):[ \t]*(.*)$", head)), head
        lookup, raw = fm(".claude/agents/kb-lookup.md")
        assert (lookup["name"], lookup["model"], lookup["effort"], lookup["omitClaudeMd"]) == ("kb-lookup", "haiku", "low", "true")
        assert int(lookup["maxTurns"]) <= 6
        tools = [t.strip() for t in lookup["tools"].split(",")]
        assert all(re.fullmatch(r"mcp__(plugin_it-ops-kb_kb|kb)__kb_\w+", t) for t in tools), tools
        assert "- kb-lookup" in raw, "the lookup procedure is preloaded"
        reviewer, _ = fm(".claude/agents/kb-reviewer.md")
        assert (reviewer["name"], reviewer["model"]) == ("kb-reviewer", "sonnet")
        assert "omitClaudeMd" not in reviewer, "the host's CLAUDE.md describes the code under review"
        assert {"Read", "Grep", "Glob", "mcp__plugin_it-ops-kb_kb__kb_topics_for"} <= {t.strip() for t in reviewer["tools"].split(",")}
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            assert not re.search(r"(?m)^effort:", f.read().split("\n---", 1)[0]), "effort in a skill overrides the host session's"
        for d in ("commands", "output-styles", "workflows", "themes", "monitors", "hooks", "bin"):
            assert not os.path.exists(os.path.join(KB, d)), f"{d}/ at the root would load as a plugin component"

    def test_shipped_texts_mark_rag_py_as_clone_only(self):
        """A host has no _tools/rag.py on its path: the server's texts and the agents never name it, and the skills
        name it only as the clone form of a kb tool (in brackets, after saying so)."""
        sys.path.insert(0, TOOLS)
        import kb_mcp
        for text in [kb_mcp.INSTRUCTIONS] + [t["description"] for t in kb_mcp.TOOL_LIST]:
            assert "rag.py" not in text
        for rel in (".claude/agents/kb-lookup.md", ".claude/agents/kb-reviewer.md", ".claude/skills/kb-review-workspace/SKILL.md",
                    ".claude/skills/kb-gap/SKILL.md"):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                assert "rag.py" not in f.read(), rel
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            body = f.read().split("\n---", 1)[1]
        first = body.index("rag.py")
        assert "in a clone" in body[:first].lower(), "the skill says rag.py is the clone form before using it"
        for line in body.splitlines():
            for m in re.finditer(r"rag\.py", line):
                assert line.count("(", 0, m.start()) > line.count(")", 0, m.start()) or "in a clone" in line.lower(), \
                                f"rag.py outside brackets: {line}"

    def test_kb_server_from_the_plugin_root(self):
        kb = self.plugin["mcpServers"]["kb"]
        assert kb["command"] == "python3"
        assert kb["args"] == ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_mcp.py"]

    def test_submit_feedback_blocked_on_every_docs_server(self):
        hooks = self.docs["hooks"]["PreToolUse"]
        assert len(hooks) == 1
        rx = re.compile(hooks[0]["matcher"])
        for s in self.servers:
            assert rx.fullmatch(f"mcp__plugin_{self.docs['name']}_{s}__submit_feedback"), s
        assert not rx.fullmatch(f"mcp__plugin_{self.docs['name']}_microsoft-learn__microsoft_docs_search")
        h = hooks[0]["hooks"][0]
        # shell form with no interpreter to find (the docs plugin has no _tools/kbpy): sh -c, or Git Bash on Windows
        assert h["type"] == "command" and "args" not in h and "python" not in h["command"]
        if shutil.which("sh"):
            p = subprocess.run(["sh", "-c", h["command"]], input='{"tool_name": "x"}', capture_output=True, text=True,
                               encoding="utf-8", timeout=30)
            assert (p.returncode, p.stdout) == (2, "")
            assert "submit_feedback" in p.stderr
        assert "PreToolUse" not in self.plugin["hooks"], "the kb plugin has no docs servers to guard"

    def test_kb_prompt_hook_from_the_plugin_root(self):
        hooks = self.plugin["hooks"]["UserPromptSubmit"]
        assert len(hooks) == 1
        h = hooks[0]["hooks"][0]
        assert (h["type"], h["command"]) == ("command", 'sh "${CLAUDE_PLUGIN_ROOT}/_tools/kbpy" _tools/kb_hook.py')
        assert "args" not in h, "exec form needs a real .exe on Windows: the launcher runs in shell form"

    @pytest.mark.skipif(not shutil.which("claude"), reason="the claude CLI is not installed")
    def test_claude_plugin_validate(self):
        for target in (KB, os.path.join(KB, DOCS_PLUGIN)):
            p = subprocess.run(["claude", "plugin", "validate", target], capture_output=True, text=True, encoding="utf-8", timeout=120)
            assert p.returncode == 0, p.stdout + p.stderr
            assert "Validation passed" in p.stdout + p.stderr
            warnings = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip().startswith(">") or ln.strip().startswith("\u276f")]
            assert all("No version specified" in w for w in warnings), "\n".join(warnings)


def test_status_of_a_plugin_copy_from_a_directory_marketplace(tmp_path):
    """A plugin installed from a local directory marketplace has no clone under plugins/marketplaces/: kb_status
    reports its version (the commit) as the commit instead of calling the copy unknown."""
    from conftest import copy_kb
    sha = "929d59973c2b"
    home = copy_kb(str(tmp_path / "plugins" / "cache" / "it-ops-kb" / "it-ops-kb" / sha))
    env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "KB_INDEX", "CLAUDE_PLUGIN_DATA")}
    p = subprocess.run([sys.executable, os.path.join(home, "_tools", "kb_mcp.py"), "--status"], capture_output=True,
                       text=True, encoding="utf-8", timeout=120, env=env, cwd=str(tmp_path))
    assert p.returncode == 0, p.stdout + p.stderr
    assert f"installed_as: plugin it-ops-kb@it-ops-kb, version {sha}" in p.stdout, p.stdout
    assert f"commit: {sha}\n" in p.stdout, p.stdout


def _status(home, cwd):
    env = {k: v for k, v in git_env().items() if k not in ("KB_ROOTS", "KB_INDEX", "CLAUDE_PLUGIN_DATA")}
    p = subprocess.run([sys.executable, os.path.join(home, "_tools", "kb_mcp.py"), "--status"], capture_output=True,
                       text=True, encoding="utf-8", timeout=120, env=env, cwd=str(cwd))
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


def _ahead(repo, n):
    """Commit n empty commits on top of HEAD without moving it; return the new tip."""
    tip, tree = repo.rev("HEAD"), repo.rev("HEAD^{tree}")
    for i in range(n):
        tip = repo.git("commit-tree", tree, "-p", tip, "-m", f"upstream {i}").strip()
    return tip


@pytest.mark.git
def test_status_says_how_far_a_clone_is_behind_its_remote(tmp_path):
    """A clone whose origin/main holds newer commits (as of its last fetch) says how many and how to update, from
    local refs only; one level with its remote says 0."""
    from conftest import Repo, copy_kb
    repo = Repo(copy_kb(str(tmp_path / "kb")))
    repo.git("init", "-q", "-b", "main")
    repo.git("add", "README.md")
    repo.git("commit", "-q", "-m", "kb")
    repo.git("update-ref", "refs/remotes/origin/main", repo.rev("HEAD"))
    out = _status(repo.path, tmp_path)
    assert "upstream: origin/main" in out and "behind_upstream: 0 commits\n" in out and "update:" not in out, out
    repo.git("update-ref", "refs/remotes/origin/main", _ahead(repo, 3))
    out = _status(repo.path, tmp_path)
    assert "behind_upstream: 3 commits\n" in out, out
    assert f"update: git -C {repo.path} pull --ff-only" in out, out
    code = "import kb_mcp; print(kb_mcp.kb_pack({'question': 'default Windows LAPS password length'}))"
    p = subprocess.run([sys.executable, "-c", code], cwd=os.path.join(repo.path, "_tools"), capture_output=True, text=True, encoding="utf-8",
                       timeout=300, env={**git_env(), "KB_INDEX": str(tmp_path / "index")})
    assert p.stdout.startswith("kb copy: 3 commits behind origin/main"), p.stdout[:300] + p.stderr[-500:]
    assert f"to update: git -C {repo.path} pull --ff-only.\n\ncoverage: good" in p.stdout, p.stdout[:300]


@pytest.mark.git
def test_status_says_how_far_an_installed_plugin_is_behind_its_marketplace(tmp_path):
    """An installed plugin copy (no .git) is compared with the marketplace clone Claude Code keeps beside the cache:
    commits there after the copy's version mean the copy is older than the kb it follows."""
    from conftest import Repo, copy_kb
    plugins = tmp_path / "plugins"
    mkt = Repo(plugins / "marketplaces" / "it-ops-kb")
    os.makedirs(mkt.path)
    mkt.git("init", "-q", "-b", "main")
    mkt.git("commit", "-q", "--allow-empty", "-m", "version")
    sha = mkt.rev("HEAD")[:12]
    mkt.git("reset", "-q", "--hard", _ahead(mkt, 2))
    home = copy_kb(str(plugins / "cache" / "it-ops-kb" / "it-ops-kb" / sha))
    out = _status(home, tmp_path)
    assert f"commit: {sha}\n" in out and "behind_upstream: 2 commits\n" in out, out
    assert "update: /plugin marketplace update, then /reload-plugins" in out, out


def test_domain_is_matched_without_case_and_an_unknown_one_is_refused():
    """A model passed domain "Intune" and got `coverage: none` for a question the kb covers: a domain is matched
    against the kb's paths without regard to case, and one no path is under is an error listing the domains."""
    code = ("import json, kb_mcp\n"
            "out = {'pack': kb_mcp.kb_pack({'question': 'Can the Mark device noncompliant action be removed?', "
            "'domain': 'Intune'})}\n"
            "out['search'] = kb_mcp.kb_search({'query': 'noncompliance actions', 'domain': '/Public/Intune/'})\n"
            "for d in ('no-such-domain', 'Public/NoSuch'):\n"
            "    try:\n"
            "        kb_mcp.kb_pack({'question': 'x', 'domain': d}); out[d] = 'accepted'\n"
            "    except kb_mcp.ToolError as e:\n"
            "        out[d] = str(e)\n"
            "print(json.dumps(out))")
    env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "CLAUDE_PLUGIN_DATA")}
    p = subprocess.run([sys.executable, "-c", code], cwd=TOOLS, capture_output=True, text=True, encoding="utf-8", env=env, timeout=180)
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["pack"].startswith("coverage: good") and "public/intune/" in out["pack"], out["pack"][:300]
    assert "public/intune/" in out["search"], out["search"][:300]
    for d in ("no-such-domain", "Public/NoSuch"):
        assert out[d].startswith(f"no domain {d!r}") and "intune" in out[d], out[d]
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "rag.py"), "pack", "noncompliance actions", "-d", "nosuch"],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=180)
    assert p.returncode == 1 and "no domain 'nosuch'" in p.stderr and "coverage:" not in p.stdout, p.stdout + p.stderr
