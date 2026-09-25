#!/usr/bin/env python3
"""The `kb` MCP server and the Claude Code plugin that ships it (stdlib only). tests.py runs it.

  test_kb_mcp.py       run it on its own

KbServer        _tools/kb_mcp.py as a subprocess over stdio: the legacy handshake (initialize, then
                notifications/initialized), tools/list, kb_search (hits with path:line and source urls; the
                not-found note), kb_show, kb_source, kb_status, the 2026-07-28 server/discover and its version check,
                JSON-RPC errors (parse error, unknown method or tool), stdout carrying only JSON-RPC, exit on EOF, and the
                submit_feedback hook exiting 2; kb_pack (coverage verdict, fact lines, url footer), kb_audit,
                kb_facts and kb_source with cited.
PluginManifest  .claude-plugin/marketplace.json and plugin.json: one plugin whose entry name equals its manifest name,
                sourced from the marketplace root; no pinned version (users track commits); only the read-only kb-lookup
                skill; no default agents/ scan (the kb's agents/ domain holds articles, not subagents); the kb server
                started from ${CLAUDE_PLUGIN_ROOT}; a PreToolUse hook blocking submit_feedback on every docs server in
                .mcp.json; the kb: UserPromptSubmit hook from ${CLAUDE_PLUGIN_ROOT}; the GitLab SSH remote. With the `claude` CLI installed, `claude plugin validate` passes.
"""
import json, os, re, shutil, subprocess, sys, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
SERVER = os.path.join(TOOLS, "kb_mcp.py")
REMOTE = "git@gitlab.com:mikkielt/it-ops-kb.git"


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
             "params": {"name": "kb_search", "arguments": {"query": "kerberos constrained delegation", "k": 3}}},
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
        self.assertEqual(len(self.lines), 17, "one reply per request, none for the notification")  # 16 requests + parse error
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
        self.assertEqual(sorted(tools), ["kb_audit", "kb_facts", "kb_pack", "kb_search", "kb_show", "kb_source", "kb_status"])
        for t in tools.values():
            self.assertEqual(t["inputSchema"]["type"], "object")
            self.assertTrue(t["annotations"]["readOnlyHint"])
        self.assertEqual(tools["kb_search"]["inputSchema"]["required"], ["query"])

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

    def test_submit_feedback_hook_blocks(self):
        p = subprocess.run([sys.executable, SERVER, "--deny-submit-feedback"], input='{"tool_name": "x"}', capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 2)
        self.assertIn("submit_feedback", p.stderr)
        self.assertEqual(p.stdout, "")


class PluginManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mkt = load(".claude-plugin/marketplace.json")
        cls.plugin = load(".claude-plugin/plugin.json")
        cls.servers = load(".mcp.json")["mcpServers"]

    def test_one_plugin_from_the_marketplace_root(self):
        self.assertEqual(len(self.mkt["plugins"]), 1)
        entry = self.mkt["plugins"][0]
        self.assertEqual(entry["name"], self.plugin["name"], "entry name must equal the manifest name")
        self.assertEqual(entry["source"], ".")
        for obj in (self.mkt, entry, self.plugin):
            self.assertNotIn("version", obj, "a pinned version would keep users on one copy; the commit sha tracks updates")
        self.assertEqual(self.plugin["repository"], REMOTE)

    def test_only_the_read_only_skill(self):
        self.assertEqual(self.plugin["skills"], ["./.claude/skills/kb-lookup"])
        self.assertFalse(os.path.isdir(os.path.join(KB, "skills")), "a root skills/ directory would be loaded too")
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        self.assertNotIn("disable-model-invocation", skill.split("\n---", 1)[0])
        self.assertIn(f"mcp__plugin_{self.plugin['name']}_kb__kb_search", skill)
        for w in ("Write", "Edit", "git commit", "git push"):
            self.assertNotRegex(skill, rf"(?m)^allowed-tools:.*\b{re.escape(w)}\b")

    def test_no_default_agents_scan(self):
        self.assertTrue(os.path.isdir(os.path.join(KB, "agents")))
        self.assertEqual(self.plugin.get("agents"), [], "the kb's agents/ articles must not load as subagents")
        for d in ("commands", "output-styles", "workflows", "themes", "monitors", "hooks", "bin"):
            self.assertFalse(os.path.exists(os.path.join(KB, d)), f"{d}/ at the root would load as a plugin component")

    def test_kb_server_from_the_plugin_root(self):
        kb = self.plugin["mcpServers"]["kb"]
        self.assertEqual(kb["command"], "python3")
        self.assertEqual(kb["args"], ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_mcp.py"])
        self.assertNotIn("kb", self.servers, "the root .mcp.json loads in the plugin too; kb is declared in plugin.json")

    def test_submit_feedback_blocked_on_every_docs_server(self):
        hooks = self.plugin["hooks"]["PreToolUse"]
        self.assertEqual(len(hooks), 1)
        rx = re.compile(hooks[0]["matcher"])
        for s in self.servers:
            self.assertTrue(rx.fullmatch(f"mcp__plugin_{self.plugin['name']}_{s}__submit_feedback"), s)
        self.assertFalse(rx.fullmatch(f"mcp__plugin_{self.plugin['name']}_kb__kb_search"))
        h = hooks[0]["hooks"][0]
        self.assertEqual((h["type"], h["command"], h["args"]),
                         ("command", "python3", ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_mcp.py", "--deny-submit-feedback"]))

    def test_kb_prompt_hook_from_the_plugin_root(self):
        hooks = self.plugin["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(hooks), 1)
        h = hooks[0]["hooks"][0]
        self.assertEqual((h["type"], h["command"], h["args"]), ("command", "python3", ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_hook.py"]))

    @unittest.skipUnless(shutil.which("claude"), "the claude CLI is not installed")
    def test_claude_plugin_validate(self):
        p = subprocess.run(["claude", "plugin", "validate", KB], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Validation passed", p.stdout + p.stderr)
        warnings = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip().startswith(">")]
        self.assertTrue(all("No version specified" in w for w in warnings), "\n".join(warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
