---
name: kb-lookup
description: Answer a question from the it-ops-kb knowledge base with cited sources (Windows endpoint management - DSC v3, ConfigMgr/MECM, Intune, Autopilot, Entra ID, Active Directory, Graph, GPO, Defender, SQL Server, Power BI, GitLab CI, Ansible, security baselines, identity/auth, Presidio/privacy, MCP, Claude Code, AI agents). Use whenever a question touches those domains, or the user asks what the kb says. Read-only.
allowed-tools: mcp__plugin_it-ops-kb_kb__kb_search mcp__plugin_it-ops-kb_kb__kb_show mcp__plugin_it-ops-kb_kb__kb_source mcp__plugin_it-ops-kb_kb__kb_status
disallowed-tools: mcp__claude-code-docs__submit_feedback mcp__mcp-docs__submit_feedback mcp__plugin_it-ops-kb_claude-code-docs__submit_feedback mcp__plugin_it-ops-kb_mcp-docs__submit_feedback
---

# Look up facts in it-ops-kb

Read-only: change no file, and never call a docs server's `submit_feedback`.

## 0. Which interface
- **The `kb` MCP tools** (`kb_search`, `kb_show`, `kb_source`, `kb_status`; from the it-ops-kb plugin they are named `mcp__plugin_it-ops-kb_kb__<tool>`): use them whenever they are available. They are the same searches as below, with the output already cited.
- **In a clone of the repo without them**: the same through `python3 _tools/rag.py`, one command at a time (no `;`, `&&`, pipes or loops: the shared permission rules match single commands). The equivalent command is given after each tool below.

## 1. Search the kb first
- `kb_search` with `query` = 3-8 keywords (`rag.py search "<keywords>" -k 8 -u`): chunks with `path:line`, the heading, the text and the url of each cited source id.
- Watch the `note:` lines: "not found anywhere" means those words are in no kb file; "weak match" means the top hit misses most of the query. Either one means the kb likely does not cover the question: say so, do not stretch a loosely related hit into an answer.
- Narrow with `domain` (`-d auth`), and try a synonym or the product's own term if the first query misses. `rag.py topics [DOMAIN]` lists articles.
- The search leaves out root files. `index: true` (`--index`) includes `_answers.md` (research answers with evidence), `_gaps.md` and `_conflicts.md`: use it when the question is about open items or disagreements.
- Read around a hit before quoting it: `kb_show` with `path` = `<path>:<line>` and `n` = 30 (`rag.py show <path>:<line> -n 30`).
- Resolve ids: `kb_source` with `ids` (`rag.py src S1234 S-k3f7q2zd`); it shows `superseded by` when a newer row replaced the source.

## 2. Weigh what you found
Each fact ends in one tag:
- `DOC` official document; `DER` derived from DOC facts (the derivation is shown); `COMMUNITY` non-official; `UNK` not confirmed.
- `UNK` and `COMMUNITY` are leads, never the answer by themselves. Say so.
- Check `_conflicts.md` when sources disagree (`kb_search` with `index: true`), and the article's `status` (`partial` means known gaps) and `retrieved_utc` (`kb_show` on `<path>:1` shows the front matter).
- Freshness: `kb_status` gives this copy's commit, its date and the latest census (the date the whole kb was confirmed current). In a clone, `python3 _tools/fetch.py --status --file <path>` shows when one article's sources were last fetched (`never` is normal).

## 3. Go live only when needed
If the kb has no answer, only `UNK`/`COMMUNITY`, or the user needs the current state, check the official docs through the documentation MCP servers (shipped with the plugin, and in the repo's `.mcp.json`):
- Microsoft products: `microsoft_docs_search`, then `microsoft_docs_fetch` on the best url.
- Claude Code: `search_claude_code_docs`. MCP spec: `search_model_context_protocol`.
- Never call `submit_feedback` (the plugin blocks it with a hook; the repo denies it in `.claude/settings.json`).
Label that part of the answer "live docs, not in the kb" with the url and today's date. Do not add it to the kb here: suggest `/kb-add-topic` or `/kb-refresh` in a clone of the repo.

## 4. Answer
- Lead with the answer. Then the supporting facts, each with `path:line`, tag and source id + url.
- State what is unknown or unverified, and how current the kb copy is when it matters (`kb_status`).
- If neither the kb nor the live docs answer it, say that plainly: no guessing.
- Examples use placeholder names only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`, tenant `00000000-0000-0000-0000-000000000000`).
