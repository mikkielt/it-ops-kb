# Design: how the kb works, and when it is token-efficient

The reasoning behind the kb's shape, with the measurements it rests on. Numbers are dated: they come from `_self/reports/token-usage.md` (section names in quotes) and change with Claude Code versions and models. Re-measure with `_tools/agent_bench.py` before relying on an old number, and add the result to the report as a new dated section.

## The idea

A lookup costs an agent its fixed context times its turns, plus what the tools return. The facts a question needs are small (a median article is about 1.2k tokens, a fact line under 100); the cost is everything around them. So the kb moves every step that needs no judgement into deterministic tools, and leaves the model three jobs: pick the tool, check the verdict, write the reply.

- **Fact lines, not pages.** One fact per line, each ending in a tag with source ids, so a tool can return exactly the lines that answer, with provenance, and nothing else.
- **One call, one verdict.** `pack` returns a verdict, the best lines grouped by article and one url footer within a token budget. The verdict is also the stop rule: `none` means say so and add nothing from memory.
- **Exact tools for structural questions.** Counts, lists and joins ("partial intune articles", "who cites S1216") are `audit`, `facts` and `src --cited`, never reading.
- **The model is optional where the verdict is clear.** The `kb:` hook answers a `good` pack with no model call; `kb_ask.py` routes by verdict to the cheapest model that can answer.
- **Rules load only where needed.** `AGENTS.md` (under 4 KB, tested) loads in every session and subagent, so it holds only lookup rules. Everything a maintainer or a skill needs sits in `_self/` and is read on demand, one file per job.
- **Freshness is evidence, not a promise.** Each source row carries its retrieval date, `fetch.py --diff` finds changed sources, the census re-confirms every source, and a census tag marks a commit whose sources were all confirmed on that date.

## When it is efficient

| situation | measured | where |
|---|---|---|
| `kb:` prompt the kb covers | 0 model tokens, $0, about 0.4 s | "Re-measurement after the changes", 1 |
| lookup inline in a running session | one `kb_pack`, then the answer: 2 turns, 42-49k input in a fresh Sonnet session, most of it Claude Code's own fixed context | "Six questions, host vs clone" |
| several parts | one `kb_pack` with `questions` (up to 6), a verdict each, one url footer | same |
| count, list, join | 1 tool call, about 1k tokens, exact; an agent reading files: 28 calls, 363k effective input, 195 s, approximate | "Results", T6 |
| headless (`kb_ask.py`), question covered | $0.004-0.014 per question; Opus alone $0.18-0.29 | "Router second pass" |
| against web search, 5 covered questions | kb router $0.011, 8.9 s, 10.4k input, 10/10 correct; Sonnet web search $0.128, 26.9 s, 98k, 10/10; Haiku web search $0.025 but 8/10, often without searching | "kb router versus a typical web-search session" |
| the kb as a plugin in another project | about 312 always-on tokens per session; the same six questions cost the same as in a clone (306k vs 312k in total) | "Always-on cost in a host" |

## When it is not

- **A fresh general-purpose subagent per lookup.** It pays its startup context (13.5k tokens in the host measurement, 50k in the first) before reading a line, and every turn re-sends it; a fact lookup in one cost 120-136k effective input. Answer inline. Even the lean `kb-lookup` agent (3.9k startup, Haiku) never saved money when a larger model handed off to it and took 2-3 times as long ("Agent benchmark and routing"); it pays only for long research whose output would fill the caller's context.
- **A question the kb does not cover.** The router adds a cheap check (about $0.01 and a few seconds) to what a web search costs anyway; the answer is labelled live docs, not in the kb.
- **A false `good`.** The verdict counts key words, not meaning, so a `good` pack can be about a related subject. The `check:` line catches a missing product name and key words spread across unrelated facts, not everything; Opus noticed such cases, Haiku mostly did not. `kb_ask.py`'s Haiku reader answers `INSUFFICIENT` and escalates.
- **Very small kbs.** A word counts as a key word only when under a fifth of the lines hold it, so a team kb of one or two articles cannot reach `good`.
- **Writing and upkeep.** Research, refresh, the census and the citation-support audit are network- and model-heavy; they are paid once per fact, and every later lookup reuses them. A census of about 1,900 sources took one mechanical pass plus about ten readers.
- **Rerankers, embeddings, a hosted API.** Not used: the misses are about meaning, which the reader's sufficiency check handles more cheaply, and the kb does not call the Anthropic API ("Router second pass", decided 2026-09-26).

## How the kb documents itself

- **Code is the source of truth for mechanics.** Each tool's docstring is its reference; `_self/tools.md` is the only table of them. `_self/` docs describe files listed in `_self/map.csv`, and `_tools/selfdoc.py stale` lists docs whose described files changed after the doc did; `/kb-self` updates them.
- **Tests hold prose to code.** Flags named next to a tool must exist in it, backtick paths must resolve, the generated tables must be current, and `AGENTS.md` and `README.md` have size caps.
- **Measurements are dated records.** Reports keep what was measured and decided on a date; this file keeps the current conclusions, and says where each number comes from.
- **Kept out of retrieval.** `_self/` is searched only with `--index`, never by `pack`: its words (hook, skill, plugin, subagent) are also domain words in `claude/`, `mcp/` and `agents/`, and would crowd out real answers for plugin users.
