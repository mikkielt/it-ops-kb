---
name: kb-review-workspace
description: Review this workspace's code against the it-ops-kb documentation facts (Kerberos/NTLM, MSAL, LDAP, ConfigMgr AdminService, Graph permissions, MCP servers) and report findings with the code's path:line and the kb citation. Read-only; the report goes to chat.
argument-hint: "[paths or focus]"
disable-model-invocation: true
context: fork
agent: it-ops-kb:kb-reviewer
background: false
allowed-tools: Read Grep Glob mcp__plugin_it-ops-kb_kb__kb_topics_for mcp__plugin_it-ops-kb_kb__kb_facts mcp__plugin_it-ops-kb_kb__kb_pack mcp__plugin_it-ops-kb_kb__kb_show mcp__plugin_it-ops-kb_kb__kb_source
---

# Review this workspace against it-ops-kb

Scope: $ARGUMENTS (when empty: the workspace's own source code, without dependencies, build output and generated files).

Read-only: read code and kb facts, write no file, run no command, change nothing. Follow your review procedure:

1. `kb_topics_for` on the source files or directories in scope.
2. Per relevant topic (at most 8): `kb_facts` or `kb_pack` with `response_format` = `detailed`.
3. Read the matched code and compare it with the DOC, CODE and DER facts; COMMUNITY and UNK facts give at most a "check" note.
4. Report in chat: one line per finding, most severe first, each with the workspace `path:line`, the kb `path:line`, tag and source url, and a one-sentence fix. Then the topics checked without a finding, and the ones the kb has no facts for.
5. Last, one line each, only when true (read `.claude/settings.json`): no code intelligence plugin in `enabledPlugins` for the workspace's languages; no `permissions.deny` `Read(./**/vendor/**/*)`-style rules for checked-in generated or vendored code. Cite `claude/large-codebases.md` (`kb_facts`); change nothing.
