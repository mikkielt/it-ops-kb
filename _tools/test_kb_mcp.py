#!/usr/bin/env python3
"""The `kb` MCP server and the Claude Code plugin that ships it (stdlib only). tests.py runs it.

  test_kb_mcp.py       run it on its own

KbServer        _tools/kb_mcp.py as a subprocess over stdio: the legacy handshake (initialize, then
                notifications/initialized), tools/list (every description marked as documentation facts, only kb_pack
                always loaded, response_format on the list tools), kb_search (hits with path:line and source urls;
                the not-found note), kb_show, kb_source, kb_status, the 2026-07-28 server/discover and its version
                check, resultType on every result, JSON-RPC errors (parse error, unknown method or tool), stdout
                carrying only JSON-RPC, exit on EOF; kb_pack (coverage verdict, fact lines, url footer; a batch of
                questions with a verdict each and one footer), kb_audit, kb_facts (concise at least 30% smaller than
                detailed), kb_source with cited, kb_topics_for.
PluginManifest  .claude-plugin/marketplace.json and the two plugins: it-ops-kb (from the root: the kb server, the
                read-only kb-lookup and kb-review-workspace skills, the kb-lookup and kb-reviewer agents listed by path
                so the kb's agents/ articles never load, the kb: hook) and it-ops-kb-docs (the three documentation
                servers and a PreToolUse hook blocking submit_feedback); no root .mcp.json (it would load into
                it-ops-kb); no pinned version (users track commits); rag.py named only as the clone form; the GitLab
                SSH remote. With the `claude` CLI installed, `claude plugin validate` passes for both.
"""
import json, os, re, shutil, subprocess, sys, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
SERVER = os.path.join(TOOLS, "kb_mcp.py")
REMOTE = "git@gitlab.com:mikkielt/it-ops-kb.git"
DOCS_PLUGIN = ".claude-plugin/it-ops-kb-docs"


def load(rel):
    with open(os.path.join(KB, rel), encoding="utf-8") as f:
        return json.load(f)


class KbServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        ]
        stdin = "".join(json.dumps(m) + "\n" for m in msgs) + "this is not json\n"
        cls.proc = subprocess.run([sys.executable, SERVER], input=stdin, capture_output=True, text=True, timeout=60, cwd=os.sep)
        cls.lines = [ln for ln in cls.proc.stdout.splitlines() if ln.strip()]
        cls.replies = [json.loads(ln) for ln in cls.lines]
        cls.by_id = {r.get("id"): r for r in cls.replies}

    def text(self, msg_id):
        r = self.by_id[msg_id]["result"]
        return r["isError"], r["content"][0]["text"]

    def test_exits_on_eof_and_stdout_is_only_jsonrpc(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertEqual(len(self.lines), 23, "one reply per request, none for the notification")  # 22 requests + parse error
        for r in self.replies:
            self.assertEqual(r["jsonrpc"], "2.0")

    def test_initialize(self):
        r = self.by_id[1]["result"]
        self.assertEqual(r["protocolVersion"], "2025-06-18")
        self.assertIn("tools", r["capabilities"])
        self.assertEqual(r["serverInfo"]["name"], "kb")
        self.assertIn("UNK", r["instructions"])

    def test_tools_list(self):
        tools = {t["name"]: t for t in self.by_id[2]["result"]["tools"]}
        self.assertEqual(sorted(tools), ["kb_audit", "kb_facts", "kb_pack", "kb_search", "kb_show", "kb_source", "kb_status",
                                         "kb_topics_for"])
        for t in tools.values():
            self.assertEqual(t["inputSchema"]["type"], "object")
            self.assertTrue(t["annotations"]["readOnlyHint"])
            self.assertTrue(t["description"].startswith("Documentation facts from it-ops-kb (not live device or directory data)"),
                            f"{t['name']}: a host's live MECM/AD tools must not be confused with the kb")
        self.assertEqual(tools["kb_search"]["inputSchema"]["required"], ["query"])
        always = [n for n, t in tools.items() if t.get("_meta", {}).get("anthropic/alwaysLoad")]
        self.assertEqual(always, ["kb_pack"], "only kb_pack skips tool search; the rest stay deferred")
        for n in ("kb_pack", "kb_facts", "kb_audit", "kb_search"):
            self.assertEqual(tools[n]["inputSchema"]["properties"]["response_format"]["enum"], ["concise", "detailed"])
        self.assertEqual(tools["kb_pack"]["inputSchema"]["properties"]["response_format"]["default"], "detailed")
        self.assertEqual(tools["kb_facts"]["inputSchema"]["properties"]["response_format"]["default"], "concise")

    def test_kb_search_cites_paths_and_urls(self):
        err, text = self.text(3)
        self.assertFalse(err)
        self.assertRegex(text, r"(?m)^\[\d+(\.\d+)?\] [\w./-]+\.(md|csv):\d+  § ")
        self.assertRegex(text, r"(?m)^  -> S[-\w]+  https://")

    def test_kb_pack_audit_facts_cited(self):
        err, text = self.text(13)
        self.assertFalse(err)
        self.assertTrue(text.startswith("coverage: good"), text[:200])
        self.assertRegex(text, r"(?m)^- entra/bitlocker-key-deletion\.md:\d+ ")
        self.assertRegex(text, r"(?m)^  -> S[-\w]+  https://")
        err, text = self.text(14)
        self.assertFalse(err)
        self.assertIn("| ad/computer-attributes.md | complete |", text)
        err, text = self.text(15)
        self.assertFalse(err)
        self.assertRegex(text, r"facts=\d+")
        err, text = self.text(16)
        self.assertFalse(err)
        self.assertRegex(text, r"cited at [\w/.-]+:\d+")

    def test_kb_pack_batch(self):
        err, text = self.text(17)
        self.assertFalse(err)
        self.assertEqual(len(re.findall(r"(?m)^# Q\d: ", text)), 2)
        self.assertEqual(len(re.findall(r"(?m)^coverage: ", text)), 2, "a verdict per question")
        self.assertEqual(text.count("\nsources:"), 1, "one shared footer")
        err, text = self.text(21)
        self.assertTrue(err)
        self.assertIn("response_format", text)

    def test_concise_facts_are_smaller(self):
        (e1, concise), (e2, detailed) = self.text(18), self.text(19)
        self.assertFalse(e1 or e2)
        self.assertEqual(re.search(r"facts=\d+", concise).group(0), re.search(r"facts=\d+", detailed).group(0))
        self.assertLessEqual(len(concise), 0.7 * len(detailed), "concise must be at least 30% smaller")

    def test_kb_topics_for(self):
        err, text = self.text(20)
        self.assertFalse(err)
        self.assertRegex(text, r"(?m)^- mecm/adminservice  .*AdminService")
        self.assertRegex(text, r"(?m)^- auth/msal-public-client  PublicClientApplication \(1, text:1\)")
        err, text = self.text(22)
        self.assertFalse(err)
        self.assertIn("skipped: no/such/dir: no such file or directory", text)

    def test_kb_search_says_when_the_kb_lacks_it(self):
        err, text = self.text(4)
        self.assertFalse(err)
        self.assertIn("note: not found anywhere", text)
        self.assertIn("no match", text)

    def test_kb_show_and_its_bounds(self):
        err, text = self.text(5)
        self.assertFalse(err)
        self.assertIn("# README.md lines 1-3 of", text)
        self.assertIn("it-ops-kb", text)
        err, text = self.text(8)
        self.assertTrue(err)
        self.assertIn("not a path inside the kb", text)

    def test_kb_source(self):
        err, text = self.text(6)
        self.assertFalse(err)
        self.assertRegex(text, r"S100  .+\n  url: https?://")
        self.assertIn("S99999  UNKNOWN id", text)

    def test_kb_status(self):
        err, text = self.text(7)
        self.assertFalse(err)
        for key in ("kb_root:", "commit:", "census_log:", "sources:", "newest_retrieved_utc:", "topics:"):
            self.assertIn(key, text)

    def test_errors(self):
        self.assertEqual(self.by_id[9]["error"]["code"], -32602)
        self.assertEqual(self.by_id[10]["error"]["code"], -32601)
        self.assertEqual(self.by_id[None]["error"]["code"], -32700)
        e = self.by_id[12]["error"]
        self.assertEqual((e["code"], e["data"]["requested"]), (-32022, "1999-01-01"))
        self.assertIn("2026-07-28", e["data"]["supported"])

    def test_server_discover(self):
        r = self.by_id[11]["result"]
        self.assertIn("2026-07-28", r["supportedVersions"])
        self.assertIn("tools", r["capabilities"])
        self.assertEqual(r["cacheScope"], "public")
        self.assertEqual(r["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "kb")

    def test_every_result_has_result_type(self):
        """2026-07-28 requires resultType on every result: Claude Code drops a tools/list without it (no kb tools)."""
        for r in self.replies:
            if "result" in r:
                self.assertEqual(r["result"].get("resultType"), "complete", r.get("id"))


class PluginManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mkt = load(".claude-plugin/marketplace.json")
        cls.plugin = load(".claude-plugin/plugin.json")
        cls.docs = load(DOCS_PLUGIN + "/.claude-plugin/plugin.json")
        cls.servers = load(DOCS_PLUGIN + "/.mcp.json")["mcpServers"]

    def test_two_plugins_kb_and_docs(self):
        entries = {e["name"]: e for e in self.mkt["plugins"]}
        self.assertEqual(sorted(entries), ["it-ops-kb", "it-ops-kb-docs"])
        self.assertEqual(entries["it-ops-kb"]["source"], ".")
        self.assertEqual(entries["it-ops-kb-docs"]["source"], "./" + DOCS_PLUGIN)
        self.assertEqual(self.plugin["name"], "it-ops-kb", "entry name must equal the manifest name")
        self.assertEqual(self.docs["name"], "it-ops-kb-docs")
        for obj in (self.mkt, *entries.values(), self.plugin, self.docs):
            self.assertNotIn("version", obj, "a pinned version would keep users on one copy; the commit sha tracks updates")
        self.assertEqual(self.plugin["repository"], REMOTE)
        self.assertEqual(self.docs["repository"], REMOTE)

    def test_no_docs_servers_in_the_kb_plugin(self):
        """A plugin sourced from the root loads a root .mcp.json whatever plugin.json says, so the docs servers live
        only in the docs plugin; a host that already has microsoft-learn installs only it-ops-kb."""
        self.assertFalse(os.path.exists(os.path.join(KB, ".mcp.json")), "a root .mcp.json would load into it-ops-kb")
        self.assertEqual(sorted(self.plugin["mcpServers"]), ["kb"])
        self.assertEqual(sorted(self.servers), ["claude-code-docs", "mcp-docs", "microsoft-learn"])
        self.assertNotIn("mcpServers", self.docs)

    def test_only_read_only_skills(self):
        self.assertEqual(self.plugin["skills"], ["./.claude/skills/kb-lookup", "./.claude/skills/kb-review-workspace"])
        self.assertFalse(os.path.isdir(os.path.join(KB, "skills")), "a root skills/ directory would be loaded too")
        for rel in self.plugin["skills"] + self.plugin["agents"]:
            path = os.path.join(KB, rel, "SKILL.md") if not rel.endswith(".md") else os.path.join(KB, rel)
            with open(path, encoding="utf-8") as f:
                fm = f.read().split("\n---", 1)[0]
            for w in ("Write", "Edit", "NotebookEdit", "Bash", "git"):
                self.assertNotRegex(fm, rf"(?m)^(allowed-tools|tools):.*\b{w}\b", f"{rel} may not use {w}")
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            lookup = f.read()
        self.assertNotIn("disable-model-invocation", lookup.split("\n---", 1)[0])
        self.assertIn(f"mcp__plugin_{self.plugin['name']}_kb__kb_pack", lookup)
        with open(os.path.join(KB, ".claude/skills/kb-review-workspace/SKILL.md"), encoding="utf-8") as f:
            fm = f.read().split("\n---", 1)[0]
        for line in ("disable-model-invocation: true", "context: fork", "agent: it-ops-kb:kb-reviewer"):
            self.assertIn(line, fm)

    def test_agents(self):
        """The lookup agent is lean (kb tools only, small model, no CLAUDE.md); the reviewer reads code."""
        self.assertEqual(self.plugin["agents"], ["./.claude/agents/kb-lookup.md", "./.claude/agents/kb-reviewer.md"])
        self.assertTrue(os.path.isdir(os.path.join(KB, "agents")), "the kb's agents/ articles: never a default scan")

        def fm(rel):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                head = f.read().split("\n---", 1)[0]
            return dict(re.findall(r"(?m)^(\w+):[ \t]*(.*)$", head)), head
        lookup, raw = fm(".claude/agents/kb-lookup.md")
        self.assertEqual((lookup["name"], lookup["model"], lookup["effort"], lookup["omitClaudeMd"]), ("kb-lookup", "haiku", "low", "true"))
        self.assertLessEqual(int(lookup["maxTurns"]), 6)
        tools = [t.strip() for t in lookup["tools"].split(",")]
        self.assertTrue(all(re.fullmatch(r"mcp__(plugin_it-ops-kb_kb|kb)__kb_\w+", t) for t in tools), tools)
        self.assertIn("- kb-lookup", raw, "the lookup procedure is preloaded")
        reviewer, _ = fm(".claude/agents/kb-reviewer.md")
        self.assertEqual((reviewer["name"], reviewer["model"]), ("kb-reviewer", "sonnet"))
        self.assertNotIn("omitClaudeMd", reviewer, "the host's CLAUDE.md describes the code under review")
        self.assertTrue({"Read", "Grep", "Glob", "mcp__plugin_it-ops-kb_kb__kb_topics_for"} <= {t.strip() for t in reviewer["tools"].split(",")})
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            self.assertNotRegex(f.read().split("\n---", 1)[0], r"(?m)^effort:", "effort in a skill overrides the host session's")
        for d in ("commands", "output-styles", "workflows", "themes", "monitors", "hooks", "bin"):
            self.assertFalse(os.path.exists(os.path.join(KB, d)), f"{d}/ at the root would load as a plugin component")

    def test_shipped_texts_mark_rag_py_as_clone_only(self):
        """A host has no _tools/rag.py on its path: the server's texts and the agents never name it, and the skills
        name it only as the clone form of a kb tool (in brackets, after saying so)."""
        sys.path.insert(0, TOOLS)
        import kb_mcp
        for text in [kb_mcp.INSTRUCTIONS] + [t["description"] for t in kb_mcp.TOOL_LIST]:
            self.assertNotIn("rag.py", text)
        for rel in (".claude/agents/kb-lookup.md", ".claude/agents/kb-reviewer.md", ".claude/skills/kb-review-workspace/SKILL.md"):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                self.assertNotIn("rag.py", f.read(), rel)
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            body = f.read().split("\n---", 1)[1]
        first = body.index("rag.py")
        self.assertIn("in a clone", body[:first].lower(), "the skill says rag.py is the clone form before using it")
        for line in body.splitlines():
            for m in re.finditer(r"rag\.py", line):
                self.assertTrue(line.count("(", 0, m.start()) > line.count(")", 0, m.start()) or "in a clone" in line.lower(),
                                f"rag.py outside brackets: {line}")

    def test_kb_server_from_the_plugin_root(self):
        kb = self.plugin["mcpServers"]["kb"]
        self.assertEqual(kb["command"], "python3")
        self.assertEqual(kb["args"], ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_mcp.py"])

    def test_submit_feedback_blocked_on_every_docs_server(self):
        hooks = self.docs["hooks"]["PreToolUse"]
        self.assertEqual(len(hooks), 1)
        rx = re.compile(hooks[0]["matcher"])
        for s in self.servers:
            self.assertTrue(rx.fullmatch(f"mcp__plugin_{self.docs['name']}_{s}__submit_feedback"), s)
        self.assertFalse(rx.fullmatch(f"mcp__plugin_{self.docs['name']}_microsoft-learn__microsoft_docs_search"))
        h = hooks[0]["hooks"][0]
        self.assertEqual((h["type"], h["command"], h["args"]),
                         ("command", "python3", ["${CLAUDE_PLUGIN_ROOT}/deny_submit_feedback.py"]))
        p = subprocess.run([sys.executable, os.path.join(KB, DOCS_PLUGIN, "deny_submit_feedback.py")],
                           input='{"tool_name": "x"}', capture_output=True, text=True, timeout=30)
        self.assertEqual((p.returncode, p.stdout), (2, ""))
        self.assertIn("submit_feedback", p.stderr)
        self.assertNotIn("PreToolUse", self.plugin["hooks"], "the kb plugin has no docs servers to guard")

    def test_kb_prompt_hook_from_the_plugin_root(self):
        hooks = self.plugin["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(hooks), 1)
        h = hooks[0]["hooks"][0]
        self.assertEqual((h["type"], h["command"], h["args"]), ("command", "python3", ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_hook.py"]))

    @unittest.skipUnless(shutil.which("claude"), "the claude CLI is not installed")
    def test_claude_plugin_validate(self):
        for target in (KB, os.path.join(KB, DOCS_PLUGIN)):
            p = subprocess.run(["claude", "plugin", "validate", target], capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("Validation passed", p.stdout + p.stderr)
            warnings = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip().startswith(">") or ln.strip().startswith("\u276f")]
            self.assertTrue(all("No version specified" in w for w in warnings), "\n".join(warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
