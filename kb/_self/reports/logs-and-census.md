# Logs, their role in the self-improvement pipeline, and a census of tool calls

What the kb records about its own use and work, what each record feeds, what no record holds, and what a census of one project's Claude Code transcripts shows. The design of the records is in `kb/_self/querylog.md` and `kb/_self/usage.md`; this file is the inventory and the measurement.

## Setup of the measurement

- **Command:** `python3 _tools/kbusage.py tree <project directory of transcripts> --top 0 --format json` (`kb/_self/usage.md`, "A census before and after a change"), the output kept in a scratch directory, never in the repository.
- **Sample:** every transcript of this project's directory under the local Claude Code projects folder on one macOS host, read on 2026-10-05: 103 session transcripts and 706 subagent transcripts. Claude Code deletes transcripts after `cleanupPeriodDays` (30 days by default, `claude/data-retention.md`), so the sample covers at most the last month and a repeat later reads a different set. Benchmark and scratch directories of the project are other folders and are not in it.
- **What it counts:** tool results and their characters, not billed tokens (`tree` divides by 4 for an estimate). The totals check passed (`check: ok`).

## The records, by stage

| record | written by | holds | read by |
|---|---|---|---|
| spool rows (`prompt`, `kb_hook`, `mcp`, `kb_ask`, `stop`, `usage`, `fetch`, `work`, `ops`, `tool_fetch`) | hooks and tools, local and short-lived | raw prompts and answers, so never committed | distill |
| run files in `kb/_querylog/<month>/` | distill | one redacted, Haiku-judged entry per kb lookup: question, verdict, cited lines, fetches | learn, the digest |
| findings in `kb/_querylog/findings/` | learn, apply, research | the state of each miss, gap and source finding | apply, the research queue, the digest |
| usage sidecar in `kb/_querylog/usage/` | distill, from the transcript | token counts per lookup: per model, agent group and step | the digest |
| work sidecar in `kb/_querylog/work/` | distill | token counts per backlog item, with rework after a refused `done`, and the distill's own Haiku overhead | `backlog.py cost`, the digest |
| ops sidecar in `kb/_querylog/ops/` | the tools that did the work | closed events: land steps, sync gates, test runs, refused dones, CI reads, intake runs, agent runs, sprint closes, stall remedies | the digest (not yet), `kblog.py propose` |
| `_logs.csv` rows | `kblog.py` | aggregates of the ops sidecar with their runs and days; `proposed` until the operator confirms | the lookup tools, as observed signals beside facts |
| `kb/_self/reports/benchmarks.csv` | `_tools/benchmarks.py` | paid benchmark runs | the reports, `design.md`, `token-efficiency.md` |
| transcripts (Claude Code's own) | Claude Code | every request with its `usage`, every tool call and result, compactions | `_tools/kbusage.py` on demand; nothing stores the result |

## State on the measurement day

- **Store:** run files of two months, with findings, usage, work and ops sidecars. The ops sidecar spans three days (2026-10-02 to 2026-10-04) and holds about 21 thousand rows: `land.step` 14067, `land.end` 4888, `test.run` 1792, `sync.gate` 382, `agent.run` 93, `intake.detect` 34, `sprint.close` 15, `ci.pipeline` 10, `stall.remedy` 2.
- **Digest of ISO week 2026-W40:** 301 lookups, of which good 31, weak 13, none 23, no verdict 234 (most are prompts of work sessions that touched the kb); 56 misses, 49 fixed (37 by the kb since, 7 by apply, 5 by research); 274 lookups with usage, input per lookup median 1.73 million tokens with 99% read from the cache and 25% spent in subagents; the work lines name 46 items and 183 million tokens, 82% of them in subagents.
- **`_logs.csv`:** no row in any root, so no observed signal reaches a pack yet.
- **Source findings:** three open, all `route` findings: WebFetch read a host whose routes-table row avoids it.

## Role in the self-improvement pipeline

- **Two loops, not one.** The lookup loop (prompt, spool, distill, learn, apply, push) changes the kb itself: eval rows, aliases, expansions, gap entries and, when the user allows it, researched facts. The measurement loop (usage, work and ops sidecars, `backlog.py cost`, `kblog.py`) changes nothing by itself: it gives a person or an agent numbers to decide on, and a change that cuts tokens is judged by a before and after census.
- **The ops sidecar is the least-used record.** Its rows outnumber the lines of every other store file together by more than twenty to one, yet the digest does not report them and `kblog.py propose` has produced no row. Test-run, land and gate times are read from it only by hand.
- **Records are about the kb's own surfaces.** A tool call that touches none of them (a `sed` of a source file, a `git` command, a hand-written script) leaves no row: only `curl`, `wget` and `backlog.py claim`, `done` and `release` are parsed from shell commands, and only kb, fetch and docs-server tools by name.

## Census of tool calls

Totals: 55,737 tool results, 137.2 million characters (about 34.3 million tokens at 4 characters), 1,823 errors. Billed counts: main chain 15,753 requests and subagents 29,997; the results are 23% of the fresh input (uncached input plus cache write), the rest is context re-sent each request. Subagents made 69% of the calls and 85% of the result characters.

| by tool | calls | characters | errors |
|---|---|---|---|
| Bash | 43,042 | 82.6 million | 1,688 |
| docs:microsoft-learn | 1,953 | 31.0 million | 0 |
| Read | 1,703 | 15.1 million | 10 |
| docs:claude-code-docs | 313 | 3.6 million | 0 |
| WebFetch | 443 | 0.96 million | 14 |
| kb_pack | 126 | 0.82 million | 11 |
| Edit | 3,524 | 0.53 million | 17 |

| by agent | calls | characters |
|---|---|---|
| general-purpose | 25,803 | 86.4 million |
| main | 17,166 | 20.3 million |
| kb-worker | 7,570 | 15.8 million |
| other | 5,178 | 14.6 million |
| Explore | 20 | 0.14 million |

| Bash command head | calls | characters | what it is |
|---|---|---|---|
| sed | 4,815 | 21.4 million | line-range reads of files |
| grep | 7,032 | 15.8 million | searches |
| cat | 1,862 | 9.8 million | whole-file reads |
| python3 (script read from stdin or a bare script) | 3,593 | 2.4 million | hand-written scripts, 197 errors |
| python3 -c | 1,130 | 1.8 million | inline scripts |
| python3 `_tools/selfdoc.py section` | 575 | 3.3 million | section reads of the kb's own docs |
| git show | 560 | 3.5 million | file reads at a revision |
| python3 `_tools/backlog.py show` | 535 | 1.2 million | one item per call |
| curl | 1,403 | 1.1 million | page fetches |
| python3 `_tools/tests.py` | 1,473 | 1.8 million | 99 errors, which are failing runs |
| git add, fetch, commit, status, worktree | 4,171 together | 2.2 million | routine git |

- **Reading dominates the characters.** `sed`, `grep` and `cat` are 47 million of the 82.6 million Bash characters; Read adds 15 million. The docs servers' search results add 35 million, of which Microsoft Learn is 31 million from 1,953 calls (about 16 thousand characters a call).
- **Files read most, by characters:** `_tools/querylog.py` (151 calls, 0.59 million), `kb/_self/querylog.md` (88 calls, 0.46 million), `kb/_self/maintaining.md` (51 calls, 0.44 million), `_tools/test_querylog.py` (134 calls, 0.42 million), `_tools/backlog.py` (168 calls), `kb/_self/backlog.md` (54 calls). The same few documents and modules are read again and again across sessions and subagents.
- **Hand-written scripts remain:** 4,723 calls (3,593 bare `python3` plus 1,130 `python3 -c`) against 575 section reads and 285 `rag.py pack` calls. What these scripts do is not visible in the rollup, since the usage record keeps no command text.
- **Errors worth reading:** `python3` bare 197 errors in 3,593 calls (5.5%); `selfdoc.py stale` 188 of 385 calls exit 1, which is its answer ("stale"), not a failure; `tests.py` 99 of 1,473.
- **Compaction:** 9 compactions over the 2,786 ticks read; context rot is small in this sample, and most work is spread over many short subagent contexts instead.
- **Unit cost is heavily skewed.** The five top items of the week take 72 million of 183 million tokens, most of it in subagents (three of the five at 92% or more). One tick of one session took 23.7 million tokens by itself.

## What no record holds

- **Command text and what a script did.** The usage record keeps no command, path or url by design; `tree` reads them from the transcript each time, and the result is never stored, so no trend across weeks exists, and a transcript older than the retention period is gone.
- **A durable per-call log.** Hooks give each executed call's tool name, `tool_use_id`, optional `duration_ms`, `agent_id` and `prompt_id` (`claude/hooks.md`, "Events that carry a per-call, permission, compaction or failure signal"). The query log's capture hook is installed on `PostToolUse` and `PostToolUseFailure` but writes a row only for kb tools, fetches and `backlog.py` actions; every other call (Bash, Read, Edit, Agent, SendMessage) is dropped at capture.
- **Permission waits and refused calls.** `duration_ms` excludes them, `PermissionRequest` has no call id, and `PermissionDenied` fires only in auto mode; no capture hook listens to either.
- **Compactions, API-error turn ends and instruction files loaded** (`PreCompact`, `PostCompact`, `StopFailure`, `InstructionsLoaded`): not captured; the compaction count exists only while transcripts do.
- **Tokens per call.** The API reports none; the nearest figure is the `grow` of a step, kept for kb steps only, and OpenTelemetry's `api_request` and `tool_result` events carry cost and sizes but need an exporter that is not set up here (`claude/otel-monitoring.md`).
- **Which answers were wrong or repeated work.** The `stop` row holds the final answer only for kb prompts, and nothing records a user correction, an interrupt or a redo.

## What a census can tell today, and what it cannot

- It finds repeated work as the same command head or file path in many calls across sessions (above), the largest results by tool, and the share spent in subagents.
- It cannot say that a repeated call was wasteful: a read of the same module by two agents may be the work. It also cannot split Bash `python3` by purpose without command text, and it cannot compare two weeks once the older transcripts are deleted.
