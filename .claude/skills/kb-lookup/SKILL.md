---
name: kb-lookup
description: Answer a question from the it-ops-kb knowledge base with cited sources (Windows endpoint management - DSC v3, ConfigMgr/MECM, Intune, Autopilot, Entra ID, Active Directory, Graph, GPO, Defender, SQL Server, Power BI, GitLab CI, Ansible, security baselines, identity/auth, Presidio/privacy, MCP, Claude Code, AI agents). Use whenever a question touches those domains, or the user asks what the kb says. Read-only.
allowed-tools: mcp__plugin_it-ops-kb_kb__kb_pack mcp__plugin_it-ops-kb_kb__kb_facts mcp__plugin_it-ops-kb_kb__kb_audit mcp__plugin_it-ops-kb_kb__kb_search mcp__plugin_it-ops-kb_kb__kb_show mcp__plugin_it-ops-kb_kb__kb_source mcp__plugin_it-ops-kb_kb__kb_status
disallowed-tools: mcp__claude-code-docs__submit_feedback mcp__mcp-docs__submit_feedback mcp__plugin_it-ops-kb_claude-code-docs__submit_feedback mcp__plugin_it-ops-kb_mcp-docs__submit_feedback
---

# Look up facts in it-ops-kb

Read-only. Do it here, not in a subagent. Use the `kb` MCP tools (`mcp__plugin_it-ops-kb_kb__<tool>` from the plugin); in a clone without them, use the `rag.py` command in brackets, one command per call.

1. **One pack.** Call `kb_pack` with the question as asked (`python3 _tools/rag.py pack "<question>"`). Read its first line:
   - `coverage: good`: answer from the pack. Stop searching.
   - `coverage: weak`: make one more call, either `kb_pack` with the product's own terms or `kb_show` on the best `path:line` with `n` = 30 (`rag.py show PATH:LINE -n 30`). Then answer with what you have.
   - `coverage: none`: the kb does not cover it. Say so. Do not fill the gap from memory.
2. **Counts, lists, joins**: use a tool, never read file after file.
   - Tag counts and linked gaps/conflicts per article: `kb_audit` (`rag.py audit PREFIX [--status partial] [--entries]`).
   - Fact lines by tag: `kb_facts` (`rag.py facts PREFIX --tag UNK,COMMUNITY`).
   - Who cites a source: `kb_source` with `cited` = true (`rag.py src S123 --cited`).
3. **Weigh the tags.** `DOC` is official. `DER` is derived, with the derivation shown. `COMMUNITY` and `UNK` are leads, never the answer by themselves: say so. An article with `status: partial` has known gaps.
4. **Answer.**
   - Lead with the answer.
   - Then the supporting facts, each with `path:line`, tag and source url (from the pack's `sources:` footer; `kb_source` only for ids not in it).
   - Do not restate the whole pack. The user may have seen it (the `kb:` hook).
5. **Live docs only on request or when the kb lacks it**, and only if the user wants the current state:
   - Microsoft products: `microsoft_docs_search`, then `microsoft_docs_fetch`. Claude Code: `search_claude_code_docs`. MCP spec: `search_model_context_protocol`.
   - Label that part "live docs, not in the kb", with the url and today's date. Suggest `/kb-add-topic` or `/kb-refresh` in a clone.
   - Never call `submit_feedback`.

Freshness when it matters: `kb_status` (commit, date, latest census). Examples use placeholders only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`).
