# AGENTS.md

An offline knowledge base of facts from official sources on Windows endpoint management and the AI agents that operate it: Markdown articles and CSV data, searched and checked by the stdlib Python tools in `_tools/`. This file covers lookups. **Before any change** (edit, research, refresh, census, commit, push), read `_self/maintaining.md`. Overview for people: `README.md`.

## Look things up: deterministic tools first

- Answer lookups in the session that asked. Never start a general-purpose subagent for a lookup; several parts go in one `pack` call too; the `kb-lookup` agent only for long research whose output would fill the context (no cheaper, slower).
- From a shell or a script: `python3 _tools/kb_ask.py "<question>"` answers at the lowest cost that works (routing in `_self/tools.md`); `--route` shows the plan.
- One call first: `kb_pack` (MCP) or `python3 _tools/rag.py pack "<question>"`; several parts in one call: `questions` / `pack -q PART -q PART`. It prints `coverage: good|weak|none`, the best fact lines by article with `path:line` and tag, and one footer of source urls.
  - `good`: answer from the pack. A `check:` line under it flags a possible false `good`: answer only if a cited line answers the question itself, else treat it as `none`.
  - `weak`: one reworded pack, or one `show` of the article.
  - `none`: say the kb does not cover it. Add nothing from memory.
- Counts, lists and joins are tools, not reading: `rag.py audit [PREFIX] [--status partial] [--entries]` (per article: tag counts, linked gaps and conflicts), `rag.py facts PREFIX --tag UNK,COMMUNITY`, `rag.py src S123 --cited` (the row plus every line that cites it). MCP: `kb_audit`, `kb_facts`, `kb_source` with `cited`. Concise by default; `--format detailed` / `response_format` for full text and urls.
- Also: `rag.py show PATH:LINE -n 30`, `rag.py search "<keywords>" [-d DOMAIN] [--index]` (`--index` adds `_answers.md`, `_gaps.md`, `_conflicts.md` and the `_self/` docs), `rag.py topics [DOMAIN]`.
- `kb: <question>` from a person: a hook answers from the pack without the model when coverage is good, else passes the pack to you (`kb+:` always does).
- The `/kb-lookup` skill is the same procedure.

## Tags

Every fact ends in a tag with ids from `_sources.csv`: `DOC` (official), `CODE` (source code at a pinned commit: implementation, not a promise), `DER` (derived), `COMMUNITY` (non-official), `UNK` (not confirmed). `UNK`, `COMMUNITY`: leads, never the answer alone. `SNIPPET:` lines are tagged code examples. Cite `path:line`, the tag and the source url.

## Live documentation (only when the kb lacks it)

Three remote servers, no authentication (`.claude-plugin/it-ops-kb-docs/.mcp.json`; the `it-ops-kb-docs` plugin elsewhere, `python3 _tools/kb_mcp.py --register-local` in a clone). Label their answers "live docs, not in the kb", with url and date.

| name | url | use for |
|---|---|---|
| `microsoft-learn` | `https://learn.microsoft.com/api/mcp` | every Microsoft product in the kb |
| `claude-code-docs` | `https://code.claude.com/docs/mcp` | Claude Code |
| `mcp-docs` | `https://modelcontextprotocol.io/mcp` | the MCP specification |

## Skills

`/kb-lookup`, `/kb-review-workspace` and `/kb-gap` (read-only: review another project's code against the kb; draft a report of what the kb lacks). **A request to change the kb goes through its skill**, not freehand edits (a hook names it): `/kb-setup`, `/kb-research`, `/kb-refresh`, `/kb-add-topic`, `/kb-census`, `/kb-verify`, `/kb-git-sync`, `/kb-self`. They follow `_self/maintaining.md`.

## Agent conduct

- Never call a docs server's `submit_feedback` tool (denied in settings): it posts text outside the repo.
- Placeholders only in examples: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`. Never add real hostnames, tenant or object ids, addresses, people or tokens; `_cache/` and `_private/` are never committed.
- Run shell commands one at a time: permission rules match one command, so `a; b`, `a && b` and loops need approval.
