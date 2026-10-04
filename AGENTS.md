# AGENTS.md

An offline knowledge base of facts from official sources on Windows endpoint management and the AI agents that operate it: Markdown articles and CSV data in roots under `kb/` (`kb/public`, a team's own), searched and checked by stdlib Python tools in `_tools/`. **Before any change** (edit, research, refresh, census, commit, push), run `python3 _tools/selfdoc.py section maintaining "Conduct for changes"` (section "Skills that change the kb" only to pick a skill).

## Look things up: deterministic tools first

- Answer lookups in the session that asked. Never start a general-purpose subagent for one; the `kb-lookup` agent only for long research that would fill the context.
- From a shell or script: `python3 _tools/kb_ask.py "<question>"` answers at the lowest working cost (routing: `kb/_self/tools.md`).
- One call first: `kb_pack` (MCP) or `rag.py pack "<question>"`; several parts: `questions` / `pack -q PART -q PART`. It prints `coverage: good|weak|none`, the best fact lines by article (`root/path:line`, tag) and one footer of source urls; `root` keeps one root.
  - `good`: answer from the pack. A `check:` line flags a possible false `good`: answer only if a cited line itself answers it, else treat as `none`.
  - `weak`: one reworded pack or one `show` of the article.
  - `none` or a `route:` line: state what the kb has and lacks (`kb has:`, `kb lacks:`), answer what it has, research only the rest in the live docs (below, else the web), never from memory.
- Counts, lists and joins are tools, not reading: `rag.py audit [PREFIX] [--status partial] [--entries]` (per article: tag counts, linked gaps, conflicts), `rag.py facts PREFIX --tag UNK,COMMUNITY`, `rag.py src S123 --cited`. MCP: `kb_audit`, `kb_facts`, `kb_source` with `cited`. `--format detailed` / `response_format`: full text, urls.
- Also: `rag.py show PATH:LINE -n 30`, `rag.py search "<keywords>" [-d DOMAIN] [--index]` (`--index` adds the ledgers and `kb/_self/` docs), `rag.py topics [DOMAIN]`. A hook points article `cat`/`sed -n` here; raw reads only to edit.
- `kb: <question>`: a hook answers from the pack when coverage is good, else passes it on (`kb+:` always does).
- Open work, in order: `backlog.py horizon`, `next --all --any`, or `backlog:`.

## Tags

Every fact ends in a tag with ids from its root's `_sources.csv`: `DOC` (official), `CODE` (source code at a pinned commit: implementation, not a promise), `DER` (derived), `COMMUNITY` (non-official), `UNK` (not confirmed), `DECISION` (`[DECISION <decision id>]`: `decided` is the operator's call, cite its id; `proposed` is never an answer). `UNK`, `COMMUNITY`: leads, never the answer alone. `SNIPPET:` lines are tagged code examples. Cite `path:line`, the tag and the source url.

## Live documentation (only when the kb lacks it)

Three remote servers, no authentication, urls in `.claude-plugin/it-ops-kb-docs/.mcp.json`: `microsoft-learn` for Microsoft products in the kb, `claude-code-docs` for Claude Code, `mcp-docs` for the MCP specification. Label their answers "live docs, not in the kb", with url and date.

## Skills

`/kb-lookup`, `/kb-review-workspace` and `/kb-gap` (read-only). **A request to change the kb goes through its skill**, not freehand (a hook names it): `/kb-setup`, `/kb-research`, `/kb-refresh`, `/kb-add-topic`, `/kb-add-root`, `/kb-ingest`, `/kb-census`, `/kb-probe`, `/kb-verify`, `/kb-git-sync`, `/kb-self`; planned work: `/kb-backlog`, `/kb-sprint`, `/kb-item`.

## Agent conduct

- Never call a docs server's `submit_feedback` tool: it posts outside the repo.
- Placeholders only in examples outside `internal` roots: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`. Never add real hostnames, tenant or object ids, addresses, people or tokens; `_cache/` and `_private/` are never committed; content lands by `kbgit.py sync --push`; code only through the `code/<id>` merge request sync opens; GitHub gets only `kbgit.py publish`.
- Run shell commands one at a time: permission rules match one command.
