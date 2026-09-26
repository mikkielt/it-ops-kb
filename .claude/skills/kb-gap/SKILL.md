---
name: kb-gap
description: Draft a gap report for it-ops-kb when the kb did not answer a question (coverage none or weak, or a good pack whose facts missed the point). Runs the kb tools and prints an issue text for you to paste into the kb's issue tracker. Read-only; nothing is written or sent.
argument-hint: "<the question the kb did not answer>"
disable-model-invocation: true
allowed-tools: mcp__plugin_it-ops-kb_kb__kb_pack mcp__plugin_it-ops-kb_kb__kb_audit mcp__plugin_it-ops-kb_kb__kb_show mcp__plugin_it-ops-kb_kb__kb_status mcp__kb__kb_pack mcp__kb__kb_audit mcp__kb__kb_show mcp__kb__kb_status
disallowed-tools: mcp__claude-code-docs__submit_feedback mcp__mcp-docs__submit_feedback mcp__plugin_it-ops-kb-docs_claude-code-docs__submit_feedback mcp__plugin_it-ops-kb-docs_mcp-docs__submit_feedback
---

# Draft an it-ops-kb gap report

Question: $ARGUMENTS (when empty: the last question in this conversation that the kb did not answer; if there is none, ask for the question and stop).

Read-only. Use only the kb tools listed above: write no file, run no command, post or send nothing, and never call a `submit_feedback` tool. The user pastes the text; maintainers turn it into a kb entry.

1. `kb_status`: note the kb commit and date the answer came from.
2. `kb_pack` with the question as asked (several parts: `questions` = [part, ...]). Note each part's `coverage:` line, its `check:` line if any, and the words listed as "not in the kb".
3. The nearest articles: the first two `## path` groups of the pack. For each, `kb_audit` with `prefix` = its path and `entries` = true, to see whether a gap for this is already logged (then say so in the report and name the entry).
4. Only if the pack was `good` or `weak`: one `kb_show` on the best `path:line` with `n` = 20, to state exactly what the kb has and what it lacks.

Then print one fenced `markdown` block, nothing else around it but one line saying where to paste it (the kb's issue tracker: the plugin's homepage, `claude plugin details it-ops-kb`):

```markdown
### kb gap: <the question in at most 12 words>

**Question:** <the question as asked>
**kb version:** <commit and date from kb_status>
**Verdict:** <good|weak|none per part; the check: line if there was one>
**Nearest articles:**
- `<path>:<line>` <what this fact says, one line> [<tag>]
- ...
**Missing:** <what an answer needs that the kb lacks: a fact, a setting, a version, a whole topic>
**Already logged:** <gap entry id or text from kb_audit, or "no">
**Where an answer may be (optional):** <official doc urls the user knows; mark anything from memory as unverified>
```

Before printing, remove anything specific to the user's organisation from the question and the text: real hostnames, domains, tenant or object ids, addresses, people's names, tokens. Use the kb's placeholders instead (`PL-LT-00123`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`), and tell the user you did so.
