# Token usage of kb lookups: measurements and recommendations (2026-09-25)

Eval ids: on 2026-09-26 the `lookup_eval.csv` ids changed from `E01`-`E37` to `EV-<slug>` (`kbid.py eval`), so parallel writers no longer collide. The E numbers below are the old ids, in file order; `git log -p _tools/lookup_eval.csv` maps them.

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
- Further optimizations (a lean lookup agent, batch packs, plugin split, aliases, a workspace review skill) and their effect when the kb runs as a plugin in another project were planned in `plan-token-optimization.md`; they are done, and measured in the next section.

## Measurement in a host project (plan T1-T14, 2026-09-25)

`plan-token-optimization.md` T1-T13 are implemented (commit "feat(kb): token plan T1-T13"). This section is T14: the kb used as a plugin from another project, compared with the same questions in a clone.

### Setup
- **Host:** a throwaway git repo outside the kb, "a TypeScript MCP server for MECM and AD". It has a short `CLAUDE.md` and four `.ts` files: AdminService calls with Negotiate and an NTLM fallback, `ldapjs` with a simple bind over `ldap://`, MSAL `PublicClientApplication` with broad Graph scopes, and an MCP stdio server that logs to stdout.
- **Plugin loading:** `claude --plugin-dir <kb clone>` (the docs plugin left out unless stated).
- **Clone:** this repository, with `kb` and the docs servers registered at local scope (`kb_mcp.py --register-local`).
- **Runs:** Claude Code 2.1.282, `claude -p "<question>" --model sonnet --output-format stream-json --verbose`, one fresh session per question.
  - Allowed tools: the kb tools, Skill, Agent, Read, Grep and Glob, plus `rag.py` in the clone.
  - `--setting-sources project,local` and `ENABLE_CLAUDEAI_MCP_SERVERS=false`, so the operator's own plugins and connectors are not counted.
  - Each run's stdin was closed: `claude -p` reads stdin, and a first attempt fed it the rest of the question list.

### A bug the host run found
Claude Code negotiates MCP 2026-07-28 with the kb server. That revision requires `resultType` on every result. The server omitted it, so Claude Code rejected its `tools/list`. The debug log said: "missing required resultType — servers implementing protocol revision 2026-07-28 MUST include it".

The effect: no kb tool reached any plugin session, and the model fell back to ToolSearch loops and a subagent. The same happened with the previous commit, so the plugin had been unusable with this Claude Code version. Every result now carries `resultType: "complete"`, and a test holds it.

### Always-on cost in a host
From `/context` in the host (`claude plugin details` misses agents listed by path and inline MCP servers, and counts the manual-only skill):

| component | tokens |
|---|---|
| `kb_pack` schema (always loaded, T3) | 456 |
| the other 7 kb tools (deferred: names only until ToolSearch) | 1.9k counted as deferred |
| agents `it-ops-kb:kb-lookup` + `it-ops-kb:kb-reviewer` (descriptions) | 187 |
| skill `it-ops-kb:kb-lookup` (description; `/kb-review-workspace` is not listed) | ~150 |
| docs plugin, if installed | 3 servers' names and instructions, deferred tools |

The `kb_pack` schema is about 450 tokens, not the 150 the plan estimated, because of its description and the `questions` and `response_format` fields. It is still paid once per session, and saves a ToolSearch round trip on the first lookup.

Whole session, "Reply ok": 20.1k tokens in the host, 22.3k in the clone. The clone's extra is `AGENTS.md` (1.5k).

### Six questions, host vs clone (fresh sessions, Sonnet)

| task | host: turns / input / output / time | clone: turns / input / output / time | clone on 2026-09-25 (previous section) |
|---|---|---|---|
| fixed context ("ok") | 1 / 20.1k / 4 / 1 s | 1 / 22.3k / 4 / 1 s | 1 / 41.2k |
| T1 one fact | 2 / 42.1k / 561 / 6 s | 2 / 46.5k / 478 / 5 s | 2 / 84.2k |
| T2 source id S1216 | 3 / 62.9k / 589 / 6 s | 3 / 68.0k / 558 / 6 s | 4 / 167.3k |
| T3 medium, one topic | 2 / 43.9k / 1309 / 13 s | 2 / 51.1k / 1655 / 16 s | 3 / 129.3k |
| T4 cross-topic synthesis | 2 / 48.9k / 1597 / 15 s | 2 / 52.9k / 1777 / 15 s | 6 / 139.5k |
| T5 not in kb | 2 / 40.5k / 271 / 4 s | 2 / 44.9k / 334 / 4 s | 2 / 83.0k |
| T6 domain audit | 3 / 67.2k / 3071 / 21 s | 2 / 49.0k / 2666 / 21 s | 2 / 88.1k |
| **T1-T6** | **14 / 306k / 7398 / 65 s** | **13 / 312k / 7468 / 67 s** | **19 / 691k / 7686 / 118 s** |

What the sessions did:
- **T1, T3, T4, T5:** one `kb_pack`, then the answer. T3 and T4 put their parts into one call with `questions`. No ToolSearch before the first kb call, in the host too (T3 accepted).
- **T4 took 2 turns**, against 6 on 2026-09-25 (T4 accepted: 3 or fewer).
- **T2:** ToolSearch for `kb_source` (deferred), then `kb_source` with `cited`.
- **T6:** in the host, ToolSearch then `kb_audit`. In the clone, `rag.py audit` through Bash, which needs no tool loading.
- **T5:** both said the kb does not cover the question, and added nothing from memory.
- **Answers:** all six were correct in both places, with `path:line`, tags and urls.

How to read the change against 2026-09-25: the clone's input fell from 691k to 312k (-55%) and its turns from 19 to 13. About half of the drop is Claude Code's own: the fixed context fell from 41.2k to 22.3k between versions, and every turn re-sends it. The rest is fewer turns (T2-T4) from batch packs, concise tool output and `kb_pack` being always loaded. The host costs the same as the clone, a little less, because it does not load `AGENTS.md`.

### Subagents (host)
Each was measured as the first request of the subagent's transcript:

| subagent | model | startup context | whole lookup |
|---|---|---|---|
| `it-ops-kb:kb-lookup` (T1: kb tools only, `omitClaudeMd`, `/kb-lookup` preloaded) | Haiku, effort low | **3.9k** | 2 requests, 13.2k input: one batch `kb_pack` with 3 parts, then the answer |
| general-purpose (same question) | Sonnet | 13.5k | - |

The T1 hypothesis (under 10k, against 50k for a general-purpose agent in the 2026-09-25 setup) holds: 3.9k. The general-purpose agent is itself down to 13.5k in this Claude Code version. The preloaded skill was confirmed in the subagent transcript. `experimental.cacheTtl` stays unset: nothing here spawns the agent repeatedly.

### `/kb-review-workspace` in the host (T13)
- **Run:** `claude -p "/it-ops-kb:kb-review-workspace"`, Sonnet. It forked into `it-ops-kb:kb-reviewer` (confirmed in the subagent's `.meta.json`).
- **Tool calls (9):** Glob, `kb_topics_for`, 4 Reads, 2 `kb_pack` with `questions`, 1 `kb_facts`.
- **Cost:** 11 subagent requests, first request 6.4k tokens; 73.1k input and 3.9k output in all; 32 s.
- **Findings, all five planted problems:**
  1. the NTLM fallback against the AdminService (NTLM rejected since 2509);
  2. a malformed SPN built from a url;
  3. simple bind over plain LDAP (signing and channel binding);
  4. `console.log` on a stdio MCP server;
  5. Graph scopes wider than least privilege.
- **Check notes:** LAPS password exposure, and device-code flow under Conditional Access.
- **Citations:** every finding gave the host `path:line`, the kb `path:line`, the tag and the source url. The report named the topics checked without a finding and the ones the kb has no facts for.

### Plugin split and the clone (T7, T1)
- **Docs servers out of the kb plugin:** a plugin sourced from the root loads the root `.mcp.json` whatever `plugin.json` declares (manifest reference: `.mcp.json` first, then `mcpServers`, later names replace earlier). So the docs servers moved to `.claude-plugin/it-ops-kb-docs/`, a second plugin with its own `submit_feedback` hook. The root has no `.mcp.json`.
- **A clone** registers `kb` and the three docs servers at local scope (`python3 _tools/kb_mcp.py --register-local`, also run by `/kb-setup` and the web SessionStart hook). The docs tools keep their old names, so the permission rules still apply. The agents list the kb tools under both the plugin and the local names.
- **No duplicates:** `/context` in the clone showed each tool, skill and agent once, and only `/kb-lookup` in the skill listing (T6).
- **Not recommended:** `--plugin-dir .` in a clone. It would load the project skills and agents a second time under plugin names.

### Watch
- `kb_pack`'s always-on schema (456 tokens) could be trimmed if more tools become always loaded.
- `claude plugin details` undercounts plugins like this one; use `/context`.

## Retrieval quality audit (2026-09-25)

Checked how well `pack` finds what the kb actually holds, beyond the eval set:
- keyword probes built from 844 sampled units (tagged facts, untagged csv rows, untagged Summary, Reference and Examples lines);
- 72 natural-language questions written blind by a subagent from item text alone;
- 20 near-domain questions the kb does not cover;
- truncation;
- the same probes on the pre-plan commit `20607d4`.

### Found (all but the concise cut predate the token plan)
- **Untagged content was invisible to `pack`.** `pack` indexed only units carrying a `[TAG]`, so 36% of article content lines were never searched: Summary, Reference tables, Examples, and 815 of 2649 csv rows (Graph CSDL properties, Presidio entities, dsregcmd fields). `pack` returned those lines 0% of the time; `search` found 82-100%.
- **False "not in the kb".** Words present only in untagged content (`isManagementRestricted`, `NPI`, `profileType`) were reported as "not in the kb". The verdict then told the model to add nothing from memory: 11% of blind questions on tagged facts and 30% on untagged content got `none`.
- **Verdict rules.**
  - One unknown abbreviation (`AV`, `PC`) vetoed an otherwise well-matched question.
  - The verdict looked only at the top-scored article.
- **Truncation.**
  - The 420-character cut dropped the tag of 180 facts.
  - Concise `kb_facts` cuts 64% of lines at 160 characters.
- **Vocabulary mismatch.** Compound identifiers were not split (`approximateLastSignInDateTime` vs "last sign-in"), and spelling variants did not match (license/licence, IE/Internet Explorer).

### Changed
- **Corpus:** untagged bullets, table rows, csv rows and fenced code blocks, ranked at 0.8 and shown as `(no tag)`.
- **Verdict:**
  - untagged content can lift a question from `none` to `weak`, never to `good`;
  - `good` needs tagged facts at 60% of the key words (80% when a word is unknown), and every informative name in a top-ranked fact;
  - a lone unknown name among 75% or more matched words is `weak`;
  - the verdict uses the top-ranked article that matches the most key words.
- **Tokens:** compound identifiers are also indexed as their parts, at query weight 0.2. New aliases: license/licence, IE/Internet Explorer.
- **Output:**
  - a cut fact keeps its tags;
  - fact listings say how many lines were cut and how to get the full text;
  - a pack names how many more matching lines a file has.
- **Eval set:** 37 questions, including E28-E37 from these findings.

### Results

| | before | after |
|---|---|---|
| untagged content, line in pack (keyword probes) | 0% | 84-100% |
| blind questions, line in pack | 36/72 (`20607d4`) | 68/72 (94%) |
| blind questions, false `none` | 11% tagged, 30% untagged | 0% |
| off-kb questions answered `good` | 3/20 | 2/20 |
| cut facts with no visible tag | 180 | 0 |
| code blocks retrievable | 0/44 | 44/44 |

### Tried and rejected
- **RM3-style query expansion from the top hits:** line recall 48-61/72 and 1-4 eval regressions. The expansion terms drift off-topic.
- **Case-sensitive name matching:** no gain, and 2 eval regressions. The kb really does say "Claude for **Teams**".
- **An instruction to stop after one weak pack when the missing words are the subject:** it saved a turn on Okta but made the model give up on the NPI question, whose answer came in the second pack.

### Left, and how it is handled
- **Adjacent unanswerable questions** (Teams shared-channel size, SharePoint upload limit) match related facts. Retrieval scores cannot separate these, a known limit of answerability signals. In fresh sessions the model read the pack and said the kb does not cover them, at the cost of one extra lookup.
- **Pure paraphrase** ("required keyword" vs "needs at least one"): only document expansion (doc2query) addresses it; see the pilot below.

## doc2query pilot (2026-09-25)

Protocol and tool: `_tools/doc2query/README.md`, `python3 _tools/doc2query.py`.

- **Arms:** 12 pilot articles (169 facts) and 12 control articles (185 facts), stratified by domain (`arms.json`, seed 7).
- **Generation:** Haiku wrote 3 questions per pilot fact, 507 in all. The Doc2Query-- filter (keep a question only if `pack` without expansion reaches its fact's article) kept 473 and dropped 34.
- **Blind test:** Sonnet wrote one paraphrased question for each of 80 facts, 40 per arm, from the fact text alone. It never saw the generated questions.

| expansion weight | pilot: line in pack | control: line in pack | eval | off-kb `good` | mean pack (chars) |
|---|---|---|---|---|---|
| off | 36/40 (90%) | 38/40 | 37/37 | 2/20 | 3345 |
| 0.3 | 37/40 | 38/40 | 37/37 | 2/20 | 3262 |
| **1.0 (chosen)** | **39/40 (97.5%)** | 38/40 | 37/37 | 2/20 | 3256 |
| 2.0 | 39/40 | 38/40 | 37/37 | 2/20 | 3215 |

- **What it fixed:** the three misses at 0.3 were pure paraphrase: "app-only vs delegated permission model", "RBAC permission needed to send a notification", "registry key to enable verbose kerberos logging".
- **No harm elsewhere:** the 72 audit questions stayed at 68/72, the keyword probes did not change, and packs got slightly smaller.
- **Verdicts unchanged by design:** expansion words rank facts but are never verdict words, so a generated question cannot turn an off-kb question into `good`.

**Caveats**
- 40 questions per arm is a small sample: the gain is 3 questions.
- The weight was chosen on the test questions themselves.
- Generated and test questions both come from models, and may share a phrasing style that real users do not.

**Decision after round 1:** keep the pilot expansions at weight 1.0, and confirm on fresh arms before expanding the whole kb.

**Maintenance:**
- After editing facts, `doc2query.py stale` lists the expansion keys whose fact text changed. Regenerate those with `batch` and `ingest`.
- A stale key does no harm: nothing matches it.

### Confirmation round (seed 29, fresh arms)
- **Arms:** `split --seed 29 --exclude arms-seed7.json` gave 12 new pilot articles (155 facts) and 12 new control articles (194 facts), none from round 1.
- **Generation:** the same prompts. Haiku wrote 465 questions for all 155 facts, and the filter kept 442.
- **Blind test:** 80 new Sonnet questions, 40 per arm.
- **Weight:** fixed at 1.0, not retuned.

| | pilot: line in pack | control: line in pack | eval | off-kb `good` | mean pack (chars) |
|---|---|---|---|---|---|
| expansion off | 38/40 (95%) | 39/40 | 37/37 | 2/20 | 3345 |
| expansion on | 38/40 (95%) | 39/40 | 37/37 | 2/20 | 3273 |

The two pilot misses are not expansion failures:
- the test question asks about Claude prompt caching, but its fact is about OpenAI's cache TTL (a bad test item);
- for the Power BI refresh timing question, the right article is in the pack, but another line of it ranks higher.

**Both rounds together** (80 pilot questions): with expansion, 3 more questions found their line and none were lost. All 3 gains are from round 1, where the weight was tuned on the test set. The audit's lexical fixes already put the baseline at 90-98%, which leaves little room.

**Decision:**
- **Do not expand the whole kb now.** The confirmed gain is too small for about 13k generated questions and their upkeep.
- **Keep the two pilot rounds' expansions.** They cost nothing at query time and made packs slightly smaller.
- **Revisit with real misses.** Add failed real-world lookups to `_tools/lookup_eval.csv`. If paraphrase misses show up there, expand only the affected articles (`doc2query.py batch`, then `ingest`).

## Agent benchmark and routing (2026-09-26)

Question: which model and which hand-off pattern answers kb lookups cheapest and fastest, from a single fact to a
multi-stage lookup that needs the live docs, and can a cheap model (Haiku) act as the router or manager?

### Method

- `_tools/agent_bench.py` runs one headless `claude -p` (Claude Code 2.1.283, this clone, the user's plugins loaded)
  per scenario and config and records the result event: cost, wall time, turns, cache-write and cache-read input
  tokens, tool calls of the main session and of subagents, and a regex check per expected answer element.
- 7 scenarios: s1 one fact (LAPS password length), s2 one fact from a data row (Delivery Optimization port), s3 three
  parts, s4 a count (partial intune articles), s5 off-domain (EKS autoscaler: must say not covered), s6 a false `good`
  (GPO Central Store: the pack matched `windows/winget.md` word by word), s7 not in the kb (KRBTGT reset: live docs).
- 76 runs in total. Costs are list prices from the result event. Cache state matters: the first run of a prompt
  writes the cache (about 11k-34k tokens), a repeat reads it.

### Deterministic layer (no model)

| path | measured |
|---|---|
| `pack`, in process, warm | 3 ms median, 4.5 ms p95 (eval set) |
| `rag.py pack` / `kb:` hook, cold process | 0.03-0.04 s |
| index rebuild after an edit | 1.4 s, once |
| MCP server: start / `tools/list` / `kb_pack` | 32 ms / <1 ms / 1-12 ms |
| 1,000 random packs / 16 concurrent cold CLI packs / a 2,000-word question | 3.3 s / 0.13 s / 52 ms |
| stress suite / full tests | 83 cases in 15 s / 121 tests in 17 s |

The tools are not the bottleneck: a lookup's time and cost are the model's.

### Models answering alone (first run of each prompt)

| scenario | Haiku | Sonnet | Opus | Opus + Haiku kb-lookup agent |
|---|---|---|---|---|
| s1 one fact | $0.031, 9 s | $0.143, 7 s | $0.286, 12 s | $0.204, 25 s |
| s2 data row | $0.030, 14 s | $0.094, 12 s | $0.184, 10 s | - |
| s3 three parts | $0.036, 10 s | $0.112, 12 s | $0.231, 16 s | $0.219, 33 s |
| s4 count | $0.030, 14 s | $0.087, 7 s | $0.183, 12 s | $0.213, 31 s |
| s5 off-domain | $0.024-0.029, 9-12 s | $0.087, 8 s | $0.184, 15 s | - |
| s6 false good + live docs | $0.034-0.051, 21-24 s | $0.199-0.247, 19-21 s | $0.290, 31 s | $0.365, 80 s |
| s7 live docs | $0.047-0.053, 16-17 s | $0.139-0.153, 16-20 s | $0.272, 23 s | $0.313, 48 s |

- Every run passed its checks. Quality differed where the model had to judge or synthesize: only Opus said that s6's
  `good` was a false match (it re-packed within `gpo`); Haiku once answered s5 without calling the kb at all, and its
  s7 synthesis added a wrong reason for the double reset.
- Handing the lookup to the Haiku `kb-lookup` agent never saved money (the Opus session still pays its own start)
  and took 2-3 times as long. The guidance now says: several parts go in one `kb_pack` with `questions`; the agent
  only for long research whose output would fill the caller's context.

### Haiku as the manager

- `haiku+escalate` (Haiku main session, told to hand live-docs work to a Sonnet agent): it handed off in 1 of 4 hard
  runs and researched itself in the others. The one hand-off cost $0.119 against Sonnet alone at $0.199-0.247.
- `+strict` (the docs tools denied so Haiku must hand off): the deny also reaches the subagent, so Haiku fell back to a
  general-purpose agent: $0.24-0.26 and 139-175 s for s7.
- Conclusion: a model told to route does not route reliably, and a tool deny cannot be scoped to the main session.

### Routing by verdict: `_tools/kb_ask.py`

The router is the pack's verdict (0 tokens, milliseconds). `good`: Haiku with the pack in the prompt, so it answers in
one turn without a tool call; `weak` or `none`: Sonnet with the pack and the live-docs tools. Both keep the docs tools,
so a false `good` can still be researched.

| scenario | first run | repeat (cache warm) |
|---|---|---|
| s1 one fact | $0.028, 7 s (Haiku) | $0.005, 7 s |
| s2 data row | $0.027, 9 s (Haiku) | $0.004, 6 s |
| s3 three parts in one sentence | $0.121, 12 s (Sonnet: `weak`) | $0.039, 12 s |
| s4 count | $0.098, 10 s (Sonnet: `weak`) | $0.020, 8 s |
| s5 off-domain | $0.084, 7 s (Sonnet) | $0.008, 7 s |
| s6 Central Store (article added in this run) | $0.027, 9 s (Haiku) | $0.008, 12 s |
| s7 KRBTGT (article added in this run) | $0.094, 9 s (Sonnet: `weak`) | $0.016, 10 s |

Against Opus alone on the same scenarios ($0.18-0.29 first run): 3-10 times cheaper on the first run and up to 50
times on a repeat, at equal or lower wall time, with every check passing.

### Changes made from these measurements

- `kb_ask.py` (new) and its test; `agent_bench.py` (new) to repeat the measurement.
- Request words (`answer`, `citation`, `please`, `explain`, `safely`, ...) are pack stop words: "What is the default
  LAPS password length? Answer from the kb with citation." was `weak` (2 of 6 key words "missing") and routed to
  Sonnet; it is `good` now (eval row `EV-please-answer-citations-default-windows-laps`). Index version 3.
- `pack_many` with 3-6 parts gives each part 2 x budget / n tokens, at least 800: 800 keep 98% of the expected
  article's fact lines that 1200 print, and a 6-part pack drops from 21.4k to 16.4k characters.
- New articles for the two gaps the benchmark hit: `ad/krbtgt-password-reset`, `gpo/admx-central-store` (Sonnet
  writers, Microsoft Learn sources, 2 `UNK` each in `_gaps.md`), with eval rows.
- A regression found by the stress suite on macOS: `rag.py search` no longer warned about an unreadable file after
  the one-engine change (CI runs as root, where the case is skipped). `kbfacts.units` warns again.

### Not solved

- A false `good` (the verdict counts key words anywhere in the best article, not meaning). A phrase rule (a question
  bigram the kb knows elsewhere but the best article lacks) missed the Central Store case and demoted 4 true `good`
  eval questions, so it was dropped. Opus catches these; Haiku mostly does not.
- Multi-part questions written as one sentence and count questions come out `weak` and go to Sonnet. Splitting parts
  and sending counts to `rag.py audit` before routing would keep them on Haiku.

## Router second pass (2026-09-26): web research applied

Recommendations from Claude Code's cost, caching and headless docs and from the routing and RAG-sufficiency
literature (FrugalGPT/RouteLLM cascades; "Sufficient Context", ICLR 2025), each implemented and measured. A direct
Messages API reader was built and then removed (decided 2026-09-26: the kb does not call the Anthropic API).

| change | measured |
|---|---|
| `claude -p` without user plugins and MCP servers (`--setting-sources project,local --strict-mcp-config`) | context 29.9k -> 24.8k; first run $0.027 -> $0.018 |
| the good-route reader gets no tools (`--tools ""`) | context 24.8k -> 9.8k; repeat $0.0054 -> $0.0027 |
| sufficiency check: the Haiku reader answers `INSUFFICIENT: ...` when the facts are only related, and the question escalates | the Purview endpoint DLP false `good` escalated to Sonnet and was answered from live docs, labelled; $0.115-0.121 in total |
| counts and "who cites S123" answered by `audit` / `cited_lines` | $0, 0.5 s (was $0.098 first run on Sonnet) |
| parts split (numbered items or several questions ending in `?`; instruction sentences are not parts) | the three-part question stays on Haiku: $0.013 (was $0.121) |
| weak/none route: Sonnet at `--effort low` with only the kb and docs servers | off-domain $0.044-0.046 (was $0.084); escalated research $0.115-0.121 (Sonnet alone, s6 before: $0.199-0.247) |

Router totals, 8 scenarios x 2 runs (first run / repeat): single fact $0.0095 / $0.0039, data row $0.0085 / $0.0056,
three parts $0.0135 / $0.0130, count $0 / $0, off-domain $0.044 / $0.046, Central Store $0.014 / $0.015, KRBTGT
$0.013 / $0.014, false good escalated $0.121 / $0.115. Opus alone on the same first runs: $0.18-0.29. Every check
passed.

Checked and left as they are:
- Prompt cache lifetime: a subscription already gets one hour on the main conversation; on an API key the default is
  five minutes and one-hour writes cost more, so set `promptCacheTtl: 1h` only when lookups repeat more than five
  minutes apart.
- The kb server's tools are `anthropic/alwaysLoad` (tested): no tool-search round trip for the first lookup.
- Plugin always-on cost (`claude plugin details it-ops-kb`): about 312 tokens (skills 190 + 130); not worth trimming,
  since the kb-lookup description is also what triggers it. The command lists `Agents (0)` for path-listed agents,
  but both agents load (`it-ops-kb:kb-lookup`, `it-ops-kb:kb-reviewer`).
- Rerankers and dense retrieval: not added; the misses are about meaning, which the reader's check handles more
  cheaply.

## kb router versus a typical web-search session (2026-09-26)

Same questions, 2 runs each. Web search: `agent_bench.py web-<model>`, a `claude -p` in an empty directory with no kb,
plugins, skills or MCP servers, only `WebSearch` and `WebFetch` (a first attempt was void: the installed it-ops-kb
plugin's `kb-lookup` skill leaked in, and Haiku then answered "32 characters" for the LAPS length). Router:
`kb_ask.py`. Input tokens are cache writes + cache reads + uncached input per question.

| per question (mean) | cost | wall time | input tokens | correct |
|---|---|---|---|---|
| kb router, 5 questions the kb covers | $0.011 | 8.9 s | 10.4k | 10/10 |
| web search, Sonnet, same 5 | $0.128 | 26.9 s | 98k | 10/10 |
| web search, Opus, same 5 | $0.228 | 26.7 s | 103k | 10/10 |
| web search, Haiku, same 5 | $0.025 | 11.9 s | 43k | 8/10 |
| kb router, not covered (false good, escalated) | $0.118 | 23.2 s | 89k | 2/2 |
| web search, Sonnet, same question | $0.153 | 29.3 s | 82k | 2/2 |

- For what the kb covers: about 12x cheaper and 3x faster than Sonnet web search, 20x cheaper and 3x faster than
  Opus, with a tenth of the input tokens. The three-part question shows it most: $0.013 and 9 s against $0.29-0.39,
  35-42 s and 195-241k tokens (7-8 page fetches).
- Haiku web search is as cheap but not a search: in 5 of 12 runs it made no tool call and answered from memory, and it
  failed 3 of 12 checks. The kb router's Haiku reads cited facts instead, 12/12 correct.
- For what the kb lacks, the router costs a web search plus the reader's check (about $0.01 and a few seconds), and
  labels the result as live docs.
- Answers from the kb carry `path:line`, a tag and the source url; web answers carry urls only.
