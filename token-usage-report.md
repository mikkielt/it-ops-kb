# Token usage of kb lookups: measurements and recommendations (2026-09-25)

Why: the kb exists to make lookups cheaper and faster than web search. This report measures what a lookup actually costs an agent today, where the tokens go, and what to change so the work is mostly deterministic, with the agent acting as a limited manager.

## Method

- 8 subagents on the mid-size model, 6 tasks from trivial to complex, repo content only (no web search, no web fetch, no docs MCP servers).
- Two tasks were run twice, A/B: "guided" (told to read and follow `/kb-lookup`) and "unguided" (told only that the directory is a kb).
- Usage comes from the subagent transcripts (per-request `usage`: uncached, cache-write and cache-read input tokens), not from the agents' own reports. The agents' self-reported tool-call counts were wrong (the audit agent reported 15 calls; it made 28).
- The fixed per-session overhead was measured separately with `claude -p "Reply with the single word ok."`, headless, in three directories: empty, only `CLAUDE.md` + `AGENTS.md`, and this repo.
- "Effective input" weights cache writes 2x (1-hour cache) and cache reads 0.1x, the relative input prices. Output tokens are not in the table: the transcripts record only the streaming-start count. The answers were 0.1k to 1.5k tokens each, small next to the input.
- Answers were checked against the articles, and the audit against a 20-line script.

## Results

| task | tool calls | turns | start ctx | final ctx | cumulative input | share that is the fixed start ctx | tool output | effective input | wall time |
|---|---|---|---|---|---|---|---|---|---|
| T1 one fact (NTLMv1 default-off date), guided | 3 | 5 | 50.0k | 57.0k | 274k | 91% | 7.7 KB | 136k | 16 s |
| T1 same, unguided | 1 | 3 | 49.9k | 55.8k | 161k | 93% | 5.3 KB | 122k | 12 s |
| T2 source id S1216: row, superseded, who cites it | 3 | 5 | 50.0k | 56.5k | 268k | 93% | 4.4 KB | 134k | 22 s |
| T3 medium, one topic (PIM for Groups to on-prem AD latency) | 5 | 5 | 50.1k | 67.2k | 296k | 84% | 25.2 KB | 157k | 41 s |
| T4 cross-topic synthesis (Kerberos CLI to AdminService + SQL), guided | 8 | 7 | 50.2k | 78.4k | 463k | 75% | 50.6 KB | 195k | 38 s |
| T4 same, unguided | 4 | 5 | 50.1k | 76.3k | 333k | 75% | 45.7 KB | 178k | 37 s |
| T5 question the kb does not cover (Wi-Fi roaming setting) | 4 | 5 | 50.0k | 60.8k | 282k | 88% | 14.2 KB | 144k | 23 s |
| T6 mechanical audit of `agents/` (partial articles, UNK/COMMUNITY counts, gap/conflict entries) | 28 | 30 | 50.1k | 84.6k | 2,021k | 74% | 33.6 KB | 363k | 195 s |
| T6 as a script (for comparison) | 1 | - | - | - | ~1k | - | 1 KB | ~1k | 0.02 s |

Fixed context of one session before any work (headless, measured):

| component | tokens |
|---|---|
| Claude Code system prompt and tool definitions (empty directory) | 41.0k |
| `AGENTS.md` (via `CLAUDE.md`) | +6.8k |
| skills list, `.claude/settings.json`, `.mcp.json` servers | +1.1k |
| total in this repo | 48.9k |

Quality: all answers were correct against the articles. T1 to T4 cited `path:line` and source ids. T5 correctly found no coverage in one search, but then added unsourced general knowledge (registry values) to its answer. T6 matched the script's counts within one or two per article (differences come from tag spelling variants; see finding 6). It also found links that a script cannot see (see finding 5).

## Findings

1. **The fixed context is the cost, not the kb content.** Each new agent starts at about 50k tokens, and every turn re-sends it. That is 74-93% of the cumulative input in every task. A one-fact lookup in a fresh subagent costs about 120-136k effective input tokens; the facts it needed were under 2k. The kb content itself is cheap: the median article is 3.8 KB (about 1.2k tokens), and a Summary section is about 560 bytes.
2. **Turns multiply everything.** T6 is a question a script answers in 21 ms. The agent took 30 turns, re-read its growing context each time (2.0M cumulative input, 363k effective, 195 s), and still gave counts that are not reproducible. Mechanical and structural questions (counts, joins, lists, "which files cite X") are the most expensive thing to give an agent and the easiest to make deterministic.
3. **Search output is 25-46% urls, many repeated.** `rag.py search -k 8 -u` returns 4-9 KB. With four typical T4 queries, `-u` grows the output from 18.4 KB to 28.2 KB. The same source url appears under several hits (25 url lines, 17 unique, in one query). Urls are needed only for the few ids the answer finally cites.
4. **The lookup skill made agents do more, not better.** The guided agents read `SKILL.md` (4.5 KB), always passed `-u`, and followed "read around a hit" with a `show` of text that the search had already returned. The result: T4 guided made 8 calls and 463k cumulative input, against 4 calls and 333k unguided, at the same answer quality. The unguided agents found `rag.py` anyway, through the tools table in `AGENTS.md`.
5. **The gap and conflict ledgers cannot be joined to topics mechanically.** `_gaps.md` and `_conflicts.md` sections are named after old research sessions (`agents-errors`, `agents-a2a-cache`), not after topic paths. T6 spent about 20 of its 28 calls matching source ids between articles and ledger sections to work out which entry belongs to which article.
6. **Tag spelling varies.** Facts are tagged `[UNK]`, `[UNK: ...]`, `[UNK, ...]`, `[DER: ...]`, `[COMMUNITY, ...]` as well as the canonical form, and `check.py` accepts all of them. Counting by regex then gives slightly different answers depending on the pattern, which is why the agent's and the script's counts differ.
7. **Source lookup lacks one field.** `rag.py src` prints the row but not `used_in`, although `_sources.csv` has it. T2 grepped the whole repo instead.
8. **The negative case works but does not stop.** The `not found anywhere` note appeared on the first search in T5. The agent still ran two more calls, then filled the gap with outside knowledge. Nothing tells it when to stop, or forbids unsourced additions.
9. **`AGENTS.md` is mostly for maintainers.** Of its 15.8 KB, the sections a lookup can use (what the repo is, tools, content rules, conduct) are about 7 KB, and half of the tools table is maintainer tools. Setup, plugin, git workflow, merging and commit rules (8.6 KB) load into every session and every subagent, including ones that only look things up.

## Recommendations

The target shape: deterministic tools answer, the agent picks the tool, checks the verdict and writes the reply. Ordered by savings per effort.

### A. Keep lookups out of fresh agents (largest saving, no code)
- Answer a lookup inline in the session that asked, with the `kb` MCP tools or `rag.py`. A fresh subagent costs about 50k tokens before it reads a line; the inline lookup costs the search output only (2-8k tokens).
- Use a subagent only for a multi-topic synthesis whose working context should not stay in the main session. Give one subagent several questions at once, so the 50k is paid once.
- Retrieval and short synthesis do not need the largest model. The smallest model tier is enough for T1, T2 and T5-type questions.

### B. Deterministic tools for structural questions (T6 goes from 363k to about 1k)
Add to `rag.py`, and to `kb_mcp.py` as tools:
- `audit [DOMAIN]`: per topic, the status, `retrieved_utc`, the count of each tag, and the gap and conflict entries for it (needs C).
- `facts TOPIC|DOMAIN --tag UNK,COMMUNITY`: the fact lines with a given tag, with `path:line`.
- `src ID --cited`: the row plus `used_in` and the `path:line` of every citation (T2 in one call).

### C. Make the ledgers joinable
- Give every `_gaps.md` and `_conflicts.md` entry a `topic: <domain>/<slug>` line, or move both to CSV (`id, topic, source_ids, status, text`). `check.py` then verifies the topic exists, and `audit` joins by key instead of by an agent matching ids.
- Enforce one tag grammar in `check.py`: `[TAG S1, S2]` with an optional `: note` after the ids. Rewrite the variants once, mechanically.

### D. One-call retrieval: an evidence pack
`rag.py pack "<question>" [--budget 1500]` (and `kb_pack` in `kb_mcp.py`):
- Rank fact bullets and table rows rather than 600-character chunks, since each fact is a single bullet that ends in its tag.
- Add the Summary section of the best one or two articles.
- Print one deduplicated footer of only the source ids in the pack, with their urls.
- Start with a verdict line: `coverage: good | weak | none` (from the existing notes and the score gap).
- Stop at a token budget.
Most questions then need a single call. T1 would take one call and about 1.5k tokens of output, instead of 3 calls and 7.7 KB; `show` is only for when the pack is not enough.

Until `pack` exists, cheaper defaults for `search`:
- Drop `-u` from the lookup instructions.
- Make search print a deduplicated url footer instead of urls after each hit, or resolve only the cited ids with one `src` call at the end.

### E. Rewrite `/kb-lookup` around a stop rule
- Order: `pack` (or one `search` without urls). Then, only if the verdict is `weak`, one reworded query or one `show`. Answer.
- On `coverage: none` after two queries, stop and say the kb does not cover it. Add nothing that is not in the kb, and point to `/kb-research`.
- Do not `show` text that the search already returned; show the whole article (median 1.2k tokens) only when the answer needs its structure.
- Resolve urls once, for the ids in the answer.
- Shorten the file. The 4.5 KB is read on every guided lookup.

### F. Split `AGENTS.md` by audience (about 5k tokens off every session and every subagent)
- Keep in `AGENTS.md` about 1.5-2 KB: what the repo is, the lookup commands, the tag meanings, read-only conduct, placeholders, and one line saying where maintainer rules live.
- Move Setup, Plugin, Git workflow, Merging, and Commits and history to `docs/maintaining.md`. The skills that need them (`/kb-setup`, `/kb-git-sync`, `/kb-verify`, `/kb-refresh`, `/kb-add-topic`, `/kb-census`) read it when they run, so it loads only in maintenance sessions.
- Keep the SessionStart hook output short and move the census status line to `work-left.md`. It is already small; keep it that way.

### G. Measure retrieval deterministically
- Add `_tools/lookup_eval.csv` (question, expected `path` or `path:line`, expected verdict) and `rag.py eval`, which reports recall@k, the verdict accuracy, and the output bytes per question. Run it in `tests.py`, so ranking or output changes are caught without an agent.
- Seed it with this report's six questions. T5 is the `none` case.
- Re-run this measurement (same six tasks, transcript usage) after A-F to confirm the savings.

## Expected effect

| case | today (fresh subagent) | after A + D + F (inline, `pack`) |
|---|---|---|
| one-fact lookup (T1, T2) | 120-136k effective input, 3-5 turns | 2-4k in a warm session, 1-2 turns |
| no coverage (T5) | 144k, 4 calls, unsourced additions | 1 call, `coverage: none`, stop |
| cross-topic synthesis (T4) | 178-195k, 4-8 calls | 2-4 packs (6-10k); a subagent only if the main context must stay clean, then about 50k fixed + 10k |
| structural audit (T6) | 363k, 28 calls, 195 s, approximate counts | 1 tool call, about 1k, exact |

## Re-measurement after the changes

Recommendations A-G are implemented. The pieces:
- `_tools/kbfacts.py`, and in `rag.py` and `kb_mcp.py`: `pack`, `facts`, `audit`, `src --cited` and `eval`;
- the `kb:` prompt hook `_tools/kb_hook.py`;
- 55 ledger topic markers;
- `AGENTS.md` cut to 3.2 KB, with `MAINTAINING.md` for the rest;
- a rewritten `/kb-lookup`;
- `_tools/lookup_eval.csv`, 23 questions, all passing.

The same six questions were then asked again three ways.

### 1. The `kb:` hook (no model)

`claude -p "kb: Does deleting an Entra device also delete its BitLocker recovery keys?"` was blocked by the hook, which showed the pack.
- 0 input tokens, 0 output tokens, $0, 426 ms.
- The pack was 2.1 KB, with the answer in its first fact line.

### 2. Fresh headless sessions, one question each, old commit vs new commit

`claude -p` on the mid-size model, allowed to use `rag.py`, `Read`, `Grep`, `Glob` and skills, with no web and no subagents. The old commit ran in a worktree of `19010a8`.

| task | turns | cumulative input tokens | output tokens | time |
|---|---|---|---|---|
| fixed context only ("ok") | 1 -> 1 | 46.9k -> 41.2k | 4 -> 4 | 3 -> 4 s |
| T1 one fact | 5 -> 2 | 198.9k -> 84.2k | 853 -> 270 | 17 -> 8 s |
| T2 source id S1216 | 5 -> 4 | 190.6k -> 167.3k | 1013 -> 625 | 19 -> 15 s |
| T3 medium, one topic | 8 -> 3 | 259.6k -> 129.3k | 2361 -> 1354 | 38 -> 25 s |
| T4 cross-topic synthesis | 11 -> 6 | 586.3k -> 139.5k | 3630 -> 2302 | 59 -> 32 s |
| T5 not in kb | 5 -> 2 | 196.7k -> 83.0k | 761 -> 266 | 16 -> 8 s |
| T6 domain audit | 52 -> 2 | 1262.6k -> 88.1k | 18449 -> 2869 | 202 -> 30 s |
| **T1-T6** | **86 -> 19** | **2695k -> 691k (-74%)** | **27067 -> 7686 (-72%)** | **351 -> 118 s (-66%)** |

What the new sessions did:
- T1, T3, T5: one `pack` each, then the answer.
- T2: `src S1216 --cited`.
- T4: packs per part plus one `audit auth --entries`.
- T6: `audit agents --status partial --entries`, then the answer. The old session spent 52 turns on grep loops, 4 of them denied by the permission rules.

Answer quality:
- All six answers were correct and cited `path:line` and source urls.
- T5 said the kb does not cover the question and added nothing from memory; the first run had added registry values.
- T6's counts come from one parser and are reproducible.

Dollar cost is left out of the table. It depends on which run in a batch pays the cache write, so it is not comparable across batches; the token counts are.

### 3. Subagents from this session (the setup of the first measurement)

| task | calls | turns | cumulative input | tool output | effective input |
|---|---|---|---|---|---|
| T1 one fact, guided | 3 -> 2 | 5 -> 4 | 274k -> 217k | 7.7 -> 7.3 KB | 136k -> 130k |
| T1 one fact, unguided | 1 -> 2 | 3 -> 4 | 161k -> 218k | 5.3 -> 7.9 KB | 122k -> 129k |
| T2 source id S1216 | 3 -> 2 | 5 -> 3 | 268k -> 159k | 4.4 -> 3.3 KB | 134k -> 121k |
| T3 medium, one topic | 5 -> 3 | 5 -> 5 | 296k -> 275k | 25.2 -> 8.5 KB | 157k -> 139k |
| T4 synthesis, guided | 8 -> 7 | 7 -> 9 | 463k -> 549k | 50.6 -> 40.6 KB | 195k -> 194k |
| T4 synthesis, unguided | 4 -> 7 | 5 -> 7 | 333k -> 468k | 45.7 -> 42.9 KB | 178k -> 188k |
| T5 not in kb | 4 -> 4 | 5 -> 6 | 282k -> 332k | 14.2 -> 11.9 KB | 144k -> 148k |
| T6 domain audit | 28 -> 9 | 30 -> 11 | 2021k -> 642k | 33.6 -> 14.8 KB | 363k -> 191k |
| **total** | | | | | **1430k -> 1240k (-13%)** |

The gain here is small. Every subagent still starts at the same 50.0k tokens, because subagents inherit the `AGENTS.md` their parent session loaded at start. These were spawned from a session that began before the split, so they carried the old 15.9 KB `AGENTS.md`, without the lookup rules or the new commands. Only agents told to read `SKILL.md` saw the new procedure.

That confirms recommendation A: the fixed context is the cost. After changing `AGENTS.md`, start a new session; and do lookups inline or with the hook, not in subagents.

### Found and fixed during the re-measurement

A subagent's reworded query, `Intel Wi-Fi roaming aggressiveness`, got `coverage: good`. Two causes:
- the hyphen parts of "Wi-Fi" counted as extra matched words;
- the first word of the query was never treated as a product name.

Fix: the verdict now counts whole words only and treats every capitalised word as a name. The query and its lowercase variant are now eval cases E21 and E22.

The only pattern still reading whole articles was a multi-part question (T4 in subagents). `/kb-lookup` now says to use one pack per part.

### Status of the recommendations

| | status |
|---|---|
| A. lookups inline, not in fresh agents | in `AGENTS.md`, `/kb-lookup`, the MCP server instructions and the README note for other projects |
| B. structural tools | `rag.py audit`, `facts`, `src --cited`; `kb_audit`, `kb_facts`, `kb_source` with `cited` |
| C. joinable ledgers | explicit links via a `(topic: <domain>/<slug>)` marker, a path in the text, or a section heading. 55 markers were added where an entry's sources point at exactly one topic of its section's domain. Links via sources are reported separately. Skills require the marker on new entries; `check.py` validates markers. One shared tag parser replaces a rewrite of the 128 tag variants in articles, most of which carry meaning in their notes; lint reports DOC/COMMUNITY tags without an id (13 recorded as known debt). |
| D. evidence pack | `rag.py pack`, `kb_pack` |
| E. `/kb-lookup` stop rule | done, 3.0 KB |
| F. `AGENTS.md` split | 15.9 KB -> 3.2 KB, capped at 4 KB by `tests.py`; `MAINTAINING.md` is read by the skills that change the kb |
| G. deterministic retrieval eval | `_tools/lookup_eval.csv` (23 questions), `rag.py eval`, gated in `tests.py` |

### What is left

- 233 ledger entries have no explicit topic link. 125 of them (118 in `_gaps.md`, 7 in `_conflicts.md`) are not even linked through their sources, because they name no source id and no path. `rag.py audit` cannot attribute them until someone adds a marker; `rag.py audit --unlinked [DOMAIN]` lists them. This is a one-time triage.
- The 13 DOC/COMMUNITY tags without a source id need their sources found or their tag changed.
- Grow `lookup_eval.csv` from real questions that miss: every failed `kb:` lookup is a candidate row.
