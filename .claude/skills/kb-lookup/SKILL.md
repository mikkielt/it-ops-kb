---
name: kb-lookup
description: Answer a question from the it-ops-kb knowledge base with cited sources (Windows endpoint management - DSC v3, ConfigMgr/MECM, Intune, Autopilot, Entra ID, Active Directory, Graph, GPO, Defender, SQL Server, Power BI, GitLab CI, Ansible, Python tooling (uv, pytest, ruff), security baselines, identity/auth, Presidio/privacy, MCP, Claude Code, AI agents). Use whenever a question touches those domains, or the user asks what the kb says. Read-only.
allowed-tools: mcp__plugin_it-ops-kb_kb__kb_pack mcp__plugin_it-ops-kb_kb__kb_facts mcp__plugin_it-ops-kb_kb__kb_audit mcp__plugin_it-ops-kb_kb__kb_search mcp__plugin_it-ops-kb_kb__kb_show mcp__plugin_it-ops-kb_kb__kb_source mcp__plugin_it-ops-kb_kb__kb_status mcp__kb__kb_pack mcp__kb__kb_facts mcp__kb__kb_audit mcp__kb__kb_search mcp__kb__kb_show mcp__kb__kb_source mcp__kb__kb_status
disallowed-tools: mcp__claude-code-docs__submit_feedback mcp__mcp-docs__submit_feedback mcp__plugin_it-ops-kb-docs_claude-code-docs__submit_feedback mcp__plugin_it-ops-kb-docs_mcp-docs__submit_feedback
---

# Look up facts in it-ops-kb

Read-only. The `kb` tools hold documentation facts, not live device or directory data. Do single facts and multi-part questions here, with no subagent (one `kb_pack` with `questions`); the kb-lookup agent is only for long research whose output would fill the context. In a clone without the `kb` MCP tools, use the `rag.py` command in brackets, one command per call.

1. **One pack.** Call `kb_pack` with the question as asked (in a clone: `python3 _tools/rag.py pack "<question>"`). A question with several parts: one call with `questions` = [part, part, ...] (up to 6; in a clone: `rag.py pack -q PART -q PART`). Read each `coverage:` line:
   - `good`: answer from the pack. Stop searching. A `check:` line under it flags a possible false `good` (a word of the question the lead article never mentions, or key words spread over separate facts): answer only if a cited line answers the question itself, else treat it as `none`.
   - `weak`: one more call, either `kb_pack` with the product's own terms or `kb_show` on the best `path:line` with `n` = 30 (`rag.py show PATH:LINE -n 30`). Then answer with what you have.
   - `none`: the kb does not cover it. Say so. Do not fill the gap from memory.
   - Open and closed gaps for the area: `kb_audit` with `entries` = true.
2. **Counts, lists, joins**: use a tool, never read file after file.
   - Tag counts and linked gaps/conflicts per article: `kb_audit` (`rag.py audit PREFIX [--status partial] [--entries]`).
   - Fact lines by tag: `kb_facts` (`rag.py facts PREFIX --tag UNK,COMMUNITY`).
   - Who cites a source: `kb_source` with `cited` = true (`rag.py src S123 --cited`).
   - These return `concise` output (no urls); pass `response_format` = `detailed` (`--format detailed`) when the answer needs the full text or urls.
3. **Weigh the tags.** `DOC` is official. `CODE` was read from source code at a pinned commit: implementation, not a documented promise, so say so. `DER` is derived, with the derivation shown. A `SNIPPET:` line introduces a code example; `kb_show` prints the block, and its `checked:` value says whether anyone ran it. `COMMUNITY` and `UNK` are leads, never the answer by themselves: say so. A line marked `(no tag)` is untagged reference data or summary from the article: usable, cited by `path:line`, but say it carries no tag. An article with `status: partial` has known gaps.
4. **Answer.**
   - Lead with the answer.
   - Then the supporting facts, each with `path:line`, tag and source url (from the pack's `sources:` footer; `kb_source` only for ids not in it).
   - Do not restate the whole pack. The user may have seen it (the `kb:` hook).
5. **Live docs only on request or when the kb lacks it**, and only if the user wants the current state:
   - Microsoft products: `microsoft_docs_search`, then `microsoft_docs_fetch`. Claude Code: `search_claude_code_docs`. MCP spec: `search_model_context_protocol`.
   - Label that part "live docs, not in the kb", with the url and today's date. In a clone, suggest `/kb-add-topic` or `/kb-refresh`.
   - Never call `submit_feedback`.

Freshness when it matters: `kb_status` (commit, date, latest census). Examples use placeholders only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`).
