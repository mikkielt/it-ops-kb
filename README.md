# it-ops-kb

A knowledge base of facts from official sources on Windows endpoint management and the AI agents that operate it: DSC v3, ConfigMgr (MECM), Intune, Autopilot, Entra ID, Active Directory, Microsoft Graph, Group Policy, Defender, logs, SQL Server, Power BI, GitLab CI, Ansible, the Python toolchain (uv, pytest, ruff), security baselines, identity and authorization, privacy (Presidio), the Model Context Protocol, Claude Code and AI agents.

AI agents read it, write it and keep it current. People decide what it should cover and review what the agents did; nothing here is meant to be run by hand. This page says what the kb is, how it works and when it pays off. Everything the agents follow is in `kb/_self/`.

## Why

An agent that looks a fact up on the web reads whole pages to find one line. Measured with the same seven questions (Claude Code 2.1.283, the kb at 271 topics, 2026-09-28): a Sonnet web-search session spent about 188k input tokens, $0.19 and 74 s per question. The kb router answered them with about 14k tokens, $0.033 and 10 s, citing the article line, a tag and the source url. The work that does not need judgement (finding the facts, counting, joining) is done by deterministic tools, and the model only picks the tool and writes the reply.

## How it works

1. **Facts with provenance.** Knowledge lives in roots under `kb/`: `kb/public` holds the facts from official sources, and a team adds its own roots beside it for its systems and repositories, so one lookup answers across vendor products and the team's own services. One topic is one Markdown article, `<root>/<domain>/<topic>.md`, with large tables beside it as CSV. Every fact is one line that ends in a tag: `DOC` (an official document says it), `CODE` (source code says it, read at a pinned release), `DER` (derived, with the derivation shown), `COMMUNITY` (a non-official source) or `UNK` (not confirmed). Code examples are `SNIPPET:` lines that carry the same kind of tag. The tag carries source ids from the root's `_sources.csv`, which records each source's url, publisher, licence and date.
2. **Retrieval without a model.** `pack` ranks the fact lines for a question (BM25 over a persisted index, about 0.1 s) and returns a verdict (`good`, `weak` or `none`), the best lines with `path:line`, and one list of source urls, in 1-2k tokens. Counts, lists and "which lines cite this source" are exact tool answers, not reading.
3. **Three ways in.** The `kb` MCP server, which other projects get through a Claude Code plugin; a `kb: <question>` prompt, answered without any model when the kb covers it (`backlog:` too); and `kb_ask.py` for scripts, which sends a covered question to a small model with the facts in hand and anything else to a larger one with the live documentation servers.
4. **Upkeep by agents.** Skills research new topics, refresh changed sources (a fact diff dates the facts whose passage did not change without a model, so a model reads only the ones that did), run a census that re-confirms every source, verify quality and sync with `main`. Its own changes run as an approved backlog of sprints (`kb/_self/backlog.md`). A gate (consistency checks, tests, stress tests and a lookup eval set) must pass before every push, and commit trailers make the history searchable by source, topic and answer.

## When it pays off

| situation | what it costs (measured) |
|---|---|
| `kb:` prompt the kb covers | no model call; the pack is shown in about 0.05 s |
| lookup in a running session (`kb_pack`) | one tool call returning 1-2k tokens |
| a count, list or "who cites this source" | one exact tool call, about 1k tokens; an agent reading the files took 8 calls and 301k tokens |
| headless answer (`kb_ask.py`) | $0.033 per covered question on a first run, against $0.19-0.20 for Sonnet or Opus web search |
| a fresh general-purpose subagent per lookup | **not efficient**: it pays its whole startup context before reading a line |
| a question the kb does not cover | a web search plus a cheap check; the answer is labelled "live docs, not in the kb" |
| a `good` verdict on the wrong article | the verdict counts words, not meaning; the pack prints a `check:` line, and the model must judge |
| research, refresh and census | the expensive part, paid once per fact rather than once per question |

Details, numbers and the reasoning: `kb/_self/design.md`.

## Benchmark: bare agent vs agent with the kb

Re-run on 2026-09-28 with Claude Code 2.1.283, the kb at 271 topics, Haiku 4.5, Sonnet 5 and Opus 5.5; the report puts each number beside its earlier records.

**On the seven questions the kb covers**, one headless session each:
- Sonnet with the kb: $0.107 and 16 s per question; searching the web: $0.192 and 74 s. Opus: $0.219 with the kb, $0.204 without, 22 s against 31 s.
- Haiku without the kb made no search on 6 of 7 questions and got 2 wrong; with the kb it was right on all 7, for $0.033.
- As subagents, the kb arm cost less on every model: Opus $0.412 against $0.962 for the four questions.

Where the kb lacks the answer it adds one pack call to the same web research. One regression found: "T-SQL" now reads as a product the kb lacks, so an `sp_getapplock` how-to packs `none`.

New since the first runs, a line each:
- **Query log hooks:** add no context; the `SessionEnd` launcher returns in 47-50 ms of its 500 ms budget.
- **Distill, learn and apply:** about 1.2k Haiku input tokens per entry; the adoption gates refused all 5 fixture candidates.
- **Redaction:** 3.8M characters a second, after a 4.1 s allowlist load.
- **Research:** $0.10 per accepted fact (one Sonnet run, 2 facts).
- **`/kb-ingest`:** a 12-file sample repository became 18 facts for $2.06, with no `check.py` error.
- **Host plugin with a team root:** both roots in one pack; Haiku missed the team's part in 1 of 4 runs per mode.
- **Hook launcher:** `sh _tools/kbpy` adds 3.5 ms on macOS; Linux and Windows are not measured.

Setups, every run and the history: `kb/_self/reports/benchmarks.md`.

## Where things are

- `kb/`: all the knowledge, one directory per root (`/kb-add-root` adds one). `kb/public/` holds the articles and their data (`kb/public/<domain>/`) and its ledgers: `_sources.csv`, `_answers.md`, `_gaps.md`, `_conflicts.md` (the source list, research answers, what could not be confirmed, and where sources disagree), plus its retrieval data in `_retrieval/`.
- `_tools/`: the Python tools (standard library only).
- `kb/_self/`: everything agents read to run, change and ship the kb: rules, tool reference, design notes, the coverage table, open work. Start at `kb/_self/README.md`.
- `AGENTS.md`: the short lookup rules every agent session loads.
- `.claude/` and `.claude-plugin/`: the skills, subagents and hooks, and the plugin that other projects install.

## Using it

- **From another project:** ask Claude Code to set up the `it-ops-kb` plugin by following `kb/_self/plugin.md`, then ask your questions. Pin a census tag for a confirmed copy.
- **Changing the kb:** open a clone in Claude Code and ask for the change in plain words. Claude routes it to the skill that does it (`/kb-research`, `/kb-add-topic`, `/kb-refresh`, `/kb-census`, `/kb-verify`, `/kb-git-sync`, and `/kb-self` for the kb's own documentation), and a hook names the likely skill. You can also type a skill yourself.

## What to trust

- A `DOC` fact is only as current as its source's date. A census tag (`census-YYYY-MM-DD`) marks a commit whose sources were all confirmed current on that date.
- `UNK` and `COMMUNITY` facts are leads to verify, never answers on their own. A `CODE` fact describes how a tool is implemented at one release, not what its vendor promises. A snippet's `checked:` value says whether anyone ran it.
- Examples use placeholders only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`). No real hosts, tenants or people are ever recorded.
- Licensing: facts are written in our own words, quotes are 25 words or fewer, and verbatim copies appear only where the source's licence allows it. The code is Apache-2.0 (`LICENSE`), the kb text CC BY 4.0 (`LICENSE-CONTENT`); snapshots and pinned files keep their sources' licences (`NOTICE`).
