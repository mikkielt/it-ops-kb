# AGENTS.md

An offline knowledge base of facts from official sources on Windows endpoint management and the AI agents that operate it: Markdown articles and CSV data, searched and checked by stdlib-only Python tools in `_tools/`. This file covers lookups. **Before any change** (edit, research, refresh, census, commit, push), read `MAINTAINING.md`. Overview for people: `README.md`.

## Look things up: deterministic tools first

- Answer lookups in the session that asked. Never start a general-purpose subagent for a lookup (about 50k tokens of startup context); several parts go in one `pack` call too (measured 2026-09-26: handing them to the Haiku `kb-lookup` agent cost the same and took twice as long). That agent only pays off for long research whose tool output would fill the main context.
- From a shell or a script: `python3 _tools/kb_ask.py "<question>"` routes by the pack's verdict (good: Haiku with the pack inline, one turn, no tool call; weak/none: Sonnet with the live docs). `--route` shows the choice, `--no-model` prints a good pack.
- One call first: `kb_pack` (MCP) or `python3 _tools/rag.py pack "<question>"`; several parts in one call: `questions` / `pack -q PART -q PART`. It prints `coverage: good|weak|none`, the best fact lines by article with `path:line` and tag, and one footer of source urls.
  - `good`: answer from the pack.
  - `weak`: one reworded pack, or one `show` of the article.
  - `none`: say the kb does not cover it. Add nothing from memory.
- Counts, lists and joins are tools, not reading: `rag.py audit [PREFIX] [--status partial] [--entries]` (per article: tag counts, linked gaps and conflicts), `rag.py facts PREFIX --tag UNK,COMMUNITY`, `rag.py src S123 --cited` (the row plus every line that cites it). MCP: `kb_audit`, `kb_facts`, `kb_source` with `cited`. These print concise output; `--format detailed` / `response_format` for full text and urls.
- Also: `rag.py show PATH:LINE -n 30`, `rag.py search "<keywords>" [-d DOMAIN] [--index]` (`--index` adds `_answers.md`, `_gaps.md`, `_conflicts.md`), `rag.py topics [DOMAIN]`.
- A person can type `kb: <question>`: a hook answers from the pack without the model when coverage is good, and otherwise passes the pack to you as context (`kb+:` always passes it).
- The `/kb-lookup` skill is the same procedure.

## Tags

Every fact ends in a tag with ids from `_sources.csv`: `DOC` (official), `DER` (derived, derivation shown), `COMMUNITY` (non-official), `UNK` (not confirmed). `UNK` and `COMMUNITY` are leads, never the answer by themselves. Cite `path:line`, the tag and the source url.

## Live documentation (only when the kb lacks it)

Three remote servers that need no authentication, in `.claude-plugin/it-ops-kb-docs/.mcp.json`: the `it-ops-kb-docs` plugin for other projects, `python3 _tools/kb_mcp.py --register-local` in a clone. Label what they give "live docs, not in the kb", with the url and date.

| name | url | use for |
|---|---|---|
| `microsoft-learn` | `https://learn.microsoft.com/api/mcp` | every Microsoft product in the kb |
| `claude-code-docs` | `https://code.claude.com/docs/mcp` | Claude Code |
| `mcp-docs` | `https://modelcontextprotocol.io/mcp` | the MCP specification |

## Skills

`/kb-lookup` and `/kb-review-workspace` (read-only; the review checks another project's code against the kb). The following change the kb and follow `MAINTAINING.md`: `/kb-setup`, `/kb-research`, `/kb-refresh`, `/kb-add-topic`, `/kb-census`, `/kb-verify`, `/kb-git-sync`.

## Agent conduct

- Never call a docs server's `submit_feedback` tool (denied in settings): it posts text outside the repo.
- Placeholders only in examples: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`. Never add real hostnames, tenant or object ids, addresses, people or tokens; `_cache/` and `_private/` are never committed.
- Run shell commands one at a time: the shared permission rules match single commands, so `a; b`, `a && b` and loops need approval.
