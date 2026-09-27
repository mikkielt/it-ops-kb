# Token usage of kb lookups: measurements

What a lookup costs an agent, where the tokens go, and what each of the kb's techniques saves. Every section starts with its **setup**: the Claude Code version, the models, the size of the kb and which tools existed, because the numbers move with all of them. `kb/_self/design.md` draws the conclusions; `kb/_self/token-efficiency.md` lists the techniques; `kb/_self/reports/benchmark-bare-vs-kb.md` holds the per-run tables of the bare-vs-kb comparison. Re-measure with `_tools/agent_bench.py`, and replace a section when its setup no longer describes the kb.

Counting rules used throughout:
- **Input** is uncached + cache-write + cache-read input tokens, read from the transcript's per-request `usage` or the result event, never from an agent's own report (agents miscount their tool calls).
- **Effective input** weights cache writes 2x (one-hour cache) and cache reads 0.1x, the relative input prices.
- **Tokens, not dollars, across batches:** the run that pays the cache write varies, so dollar costs compare only within one batch.

## Reading files without the lookup tools

**Setup:** 188 topics; only `rag.py search` and `show` existed (no pack, no verdict, no structural tools); `AGENTS.md` held every rule (15.8 KB). 8 subagents on the mid-size model, repo content only, 6 tasks; two tasks run "guided" (told to follow `/kb-lookup`) and "unguided". Fixed context measured with a headless `claude -p "Reply with the single word ok."`.

| task | tool calls | turns | start ctx | cumulative input | share that is start ctx | tool output | effective input | wall time |
|---|---|---|---|---|---|---|---|---|
| T1 one fact (NTLMv1 default-off date), guided | 3 | 5 | 50.0k | 274k | 91% | 7.7 KB | 136k | 16 s |
| T1 same, unguided | 1 | 3 | 49.9k | 161k | 93% | 5.3 KB | 122k | 12 s |
| T2 source id S1216: row, superseded, who cites it | 3 | 5 | 50.0k | 268k | 93% | 4.4 KB | 134k | 22 s |
| T3 one topic (PIM for Groups to on-prem AD latency) | 5 | 5 | 50.1k | 296k | 84% | 25.2 KB | 157k | 41 s |
| T4 cross-topic synthesis (Kerberos CLI to AdminService + SQL), guided | 8 | 7 | 50.2k | 463k | 75% | 50.6 KB | 195k | 38 s |
| T4 same, unguided | 4 | 5 | 50.1k | 333k | 75% | 45.7 KB | 178k | 37 s |
| T5 question the kb does not cover (Wi-Fi roaming) | 4 | 5 | 50.0k | 282k | 88% | 14.2 KB | 144k | 23 s |
| T6 audit of `agents/` (partial articles, UNK/COMMUNITY counts, gap and conflict entries) | 28 | 30 | 50.1k | 2,021k | 74% | 33.6 KB | 363k | 195 s |
| T6 as a script | 1 | - | - | ~1k | - | 1 KB | ~1k | 0.02 s |

Fixed context of one session: Claude Code's system prompt and tools 41.0k, `AGENTS.md` +6.8k, skills and servers +1.1k: 48.9k.

What it shows:
1. **The fixed context is the cost, not the kb content.** It was 74-93% of every task's input; a one-fact lookup in a fresh subagent cost 120-136k effective input for under 2k of facts. The median article is about 1.2k tokens.
2. **Turns multiply everything.** T6, a 21 ms script, took 30 turns and 363k effective input, and its counts were not reproducible (tag spelling variants).
3. **Urls were 25-46% of search output**, many repeated (25 url lines, 17 unique, in one query).
4. **More procedure made agents do more.** Guided agents read a 4.5 KB skill, always asked for urls and re-read text the search had returned: 8 calls and 463k against 4 calls and 333k, at the same quality.
5. **Ledger entries could not be joined to topics mechanically:** T6 spent 20 of 28 calls matching source ids by hand.
6. **The negative case did not stop:** T5 found no coverage in one search, ran two more, then added unsourced registry values.

## Lookup tools against reading files

**Setup:** the same 188 topics and the same six questions after the evidence pack, the verdict and its stop rule, `audit`/`facts`/`src --cited`, the `kb:` hook, a 3.2 KB `AGENTS.md` and a 23-question eval set existed. Fresh headless sessions on the mid-size model, allowed `rag.py`, Read, Grep, Glob and skills, no web and no subagents; the comparison ran the commit before these tools in a worktree.

`kb:` hook, covered question ("Does deleting an Entra device also delete its BitLocker recovery keys?"): blocked by the hook, pack shown; 0 tokens, $0, 426 ms; the 2.1 KB pack had the answer in its first line.

| task | turns | cumulative input | output tokens | time |
|---|---|---|---|---|
| fixed context only | 1 -> 1 | 46.9k -> 41.2k | 4 -> 4 | 3 -> 4 s |
| T1 one fact | 5 -> 2 | 198.9k -> 84.2k | 853 -> 270 | 17 -> 8 s |
| T2 source id S1216 | 5 -> 4 | 190.6k -> 167.3k | 1013 -> 625 | 19 -> 15 s |
| T3 one topic | 8 -> 3 | 259.6k -> 129.3k | 2361 -> 1354 | 38 -> 25 s |
| T4 cross-topic synthesis | 11 -> 6 | 586.3k -> 139.5k | 3630 -> 2302 | 59 -> 32 s |
| T5 not in kb | 5 -> 2 | 196.7k -> 83.0k | 761 -> 266 | 16 -> 8 s |
| T6 domain audit | 52 -> 2 | 1262.6k -> 88.1k | 18449 -> 2869 | 202 -> 30 s |
| **T1-T6** | **86 -> 19** | **2695k -> 691k (-74%)** | **27067 -> 7686 (-72%)** | **351 -> 118 s (-66%)** |

- T1, T3, T5: one pack, then the answer. T2: `src S1216 --cited`. T4: packs per part plus `audit auth --entries`. T6: `audit agents --status partial --entries`, then the answer.
- All six answers were correct and cited `path:line` and urls; T5 said the kb does not cover the question and added nothing; T6's counts come from one parser.
- **Subagents inherit the `AGENTS.md` their parent session loaded at start.** Subagents spawned from a session that began before the split still carried the 15.9 KB file and saved only 13% (1430k -> 1240k effective input). After changing `AGENTS.md`, start a new session.

## Plugin in a host project

**Setup:** Claude Code 2.1.282; 188 topics with batch packs, `response_format`, product aliases, `kb_pack` always loaded, the lean `kb-lookup` agent, the plugin split and `/kb-review-workspace`. Host: a throwaway git repo, "a TypeScript MCP server for MECM and AD", with a short `CLAUDE.md` and four `.ts` files (AdminService with Negotiate and an NTLM fallback, `ldapjs` simple bind over `ldap://`, MSAL with broad Graph scopes, an MCP stdio server logging to stdout). Plugin loaded with `--plugin-dir`; the clone registers its servers at local scope. One fresh `claude -p --model sonnet` per question, `--setting-sources project,local`, claude.ai connectors off.

| task | host: turns / input / output / time | clone: turns / input / output / time |
|---|---|---|
| fixed context ("ok") | 1 / 20.1k / 4 / 1 s | 1 / 22.3k / 4 / 1 s |
| T1 one fact | 2 / 42.1k / 561 / 6 s | 2 / 46.5k / 478 / 5 s |
| T2 source id S1216 | 3 / 62.9k / 589 / 6 s | 3 / 68.0k / 558 / 6 s |
| T3 one topic | 2 / 43.9k / 1309 / 13 s | 2 / 51.1k / 1655 / 16 s |
| T4 cross-topic synthesis | 2 / 48.9k / 1597 / 15 s | 2 / 52.9k / 1777 / 15 s |
| T5 not in kb | 2 / 40.5k / 271 / 4 s | 2 / 44.9k / 334 / 4 s |
| T6 domain audit | 3 / 67.2k / 3071 / 21 s | 2 / 49.0k / 2666 / 21 s |
| **T1-T6** | **14 / 306k / 7398 / 65 s** | **13 / 312k / 7468 / 67 s** |

- T1, T3, T4, T5: one `kb_pack`, then the answer; T3 and T4 put their parts in one call with `questions`. No ToolSearch before the first kb call. T2: ToolSearch for the deferred `kb_source`, then `kb_source` with `cited`. T6: `kb_audit` in the host, `rag.py audit` through Bash in the clone.
- Against the previous section the clone went from 19 turns and 691k to 13 and 312k. About half is Claude Code's own fixed context falling from 41.2k to 22.3k between versions; the rest is fewer turns from batch packs, concise output and the always-loaded `kb_pack`. The host costs the same as the clone, a little less without `AGENTS.md` (1.5k).
- **Subagents** (first request of the transcript): `it-ops-kb:kb-lookup` (Haiku, low effort, kb tools only, no `CLAUDE.md`, the lookup skill preloaded) starts at **3.9k**, the whole lookup 13.2k in 2 requests; a general-purpose Sonnet agent starts at 13.5k.
- **`/kb-review-workspace`:** forked into `it-ops-kb:kb-reviewer`; 9 tool calls (Glob, `kb_topics_for`, 4 Reads, 2 batch `kb_pack`, 1 `kb_facts`), 73.1k input and 3.9k output in 32 s. It found all five planted problems (NTLM fallback rejected since ConfigMgr 2509, a malformed SPN, simple bind over plain LDAP, `console.log` on a stdio MCP server, over-broad Graph scopes), each with the host `path:line`, the kb `path:line`, the tag and the url.
- **No duplicates in the clone:** `/context` showed each tool, skill and agent once. `--plugin-dir .` in a clone would load the project skills and agents a second time.

### Always-on cost

**Setup:** Claude Code 2.1.283; 265 topics in one root (`kb/public`); the trimmed server instructions, `kb_pack` schema (with the `root` parameter), `kb-lookup` skill and agent descriptions. Fresh `claude -p "Reply with the single word ok." --model haiku --output-format json --no-session-persistence --setting-sources project,local` in an empty directory, 4 runs without the plugin and 5 with `--plugin-dir` at this repository.

| arm | input tokens per run |
|---|---|
| no plugin | 22,038 (all 4) |
| `--plugin-dir` | 23,282 (all 5) |

- The plugin adds about **1.24k tokens** per session once its `kb` server has connected; the untrimmed texts added 1,447. A run whose first request comes before the server connects lacks the instructions and the `kb_pack` schema; none of these runs did.
- What is left: the `kb_pack` schema, the server instructions, the skill and agent descriptions, the 7 deferred tool names, and Claude Code's own framing of each.
- A host lookup with the trimmed texts (Haiku, `--allowedTools mcp__plugin_it-ops-kb_kb`, "How many apps can an Intune Win32 app supersede?"): `kb_pack`, a `kb_show` called with its schema unloaded (`root` passed for `path`; refused), a second `kb_pack`, and a correct cited answer (the 10-node supersedence graph, `S-wc6e3fba`), 4 turns, $0.020.
- `claude plugin details it-ops-kb` shows far less (it counts skills and instructions, misses path-listed agents and the inline server, and needs an installed plugin); measure this way instead.

## Retrieval quality

**Setup:** 188 topics; a 37-question eval set. Probes: keyword queries built from 844 sampled units (tagged facts and untagged csv rows, Summary, Reference and Examples lines), 72 natural-language questions written blind by a subagent from item text alone, 20 near-domain questions the kb does not cover, and truncation checks. "Lexical baseline" is `pack` when it indexed tagged units only, cut facts at 420 characters and split no identifiers.

| | lexical baseline | current retrieval |
|---|---|---|
| untagged content, line in pack (keyword probes) | 0% | 84-100% |
| blind questions, line in pack | 36/72 | 68/72 (94%) |
| blind questions, false `none` | 11% on tagged facts, 30% on untagged content | 0% |
| off-kb questions answered `good` | 3/20 | 2/20 |
| cut facts with no visible tag | 180 | 0 |
| code blocks retrievable | 0/44 | 44/44 |

What makes the difference, all in `_tools/kbfacts.py`:
- untagged bullets, table rows, csv rows and code blocks are indexed at weight 0.8 and shown as `(no tag)`; they can lift `none` to `weak`, never to `good`;
- `good` needs tagged facts at 60% of the key words (80% with an unknown word) and every informative name in a top-ranked fact; a lone unknown name among 75% or more matched words is `weak`; the verdict uses the top article that matches the most key words;
- compound identifiers (`approximateLastSignInDateTime`) are also indexed as their parts at query weight 0.2; aliases cover spelling variants (license/licence, IE/Internet Explorer);
- a cut fact keeps its tags, and listings say how many lines were cut and how to get them;
- a batch pack of 3-6 parts gives each part 2 x budget / n tokens, at least 800: on the 88-question eval set 800 keep 98% of the expected article's fact lines that 1200 print, and a 6-part pack shrinks from 21.4k to 16.4k characters.

Tried and rejected: RM3-style query expansion from the top hits (line recall 48-61/72, 1-4 eval regressions); case-sensitive name matching (no gain, 2 regressions: the kb really says "Claude for **Teams**"); an instruction to stop after one weak pack when the missing words are the subject (saved a turn on one question, lost the answer on another); verdict rules against a false `good` (a question bigram the best article lacks; named words required in the best article; tie-breaks by named words): each missed the GPO Central Store case or demoted true `good` eval rows (NTLMv1, `sp_getapplock`, Kerberos), so the verdict stays lexical and the `check:` line flags the doubtful cases instead. On the 88-question eval set the missing-name `check:` line fired once; the spread-key-words line fired on no `good` row and caught 2 of about 10 hand-made common-word false goods.

Limits: adjacent unanswerable questions (Teams shared-channel size, SharePoint upload limit) match related facts, which retrieval scores cannot separate; the model reading the pack said the kb does not cover them, at one extra lookup. Pure paraphrase is what doc2query addresses (next section).

## doc2query

**Setup:** 188 topics, the retrieval above, a 37-question eval set. Protocol and tool: `kb/_self/doc2query.md`. Haiku wrote 3 questions per fact; the Doc2Query-- filter kept those `pack` already routes to the fact's article. A blind Sonnet wrote one paraphrased question per fact, never seeing the generated ones. Two rounds on disjoint arms of 12 pilot and 12 control articles each.

Round 1 (pilot 169 facts, 507 questions generated, 473 kept; 40 blind questions per arm), by expansion weight:

| weight | pilot: line in pack | control | eval | off-kb `good` | mean pack (chars) |
|---|---|---|---|---|---|
| off | 36/40 (90%) | 38/40 | 37/37 | 2/20 | 3345 |
| 0.3 | 37/40 | 38/40 | 37/37 | 2/20 | 3262 |
| **1.0 (in use)** | **39/40 (97.5%)** | 38/40 | 37/37 | 2/20 | 3256 |
| 2.0 | 39/40 | 38/40 | 37/37 | 2/20 | 3215 |

Round 2 (fresh arms: pilot 155 facts, 465 generated, 442 kept; weight fixed at 1.0): pilot 38/40 (95%) with and without expansion, control 39/40, eval 37/37, off-kb `good` 2/20, mean pack 3345 -> 3273 characters. Its two pilot misses were a bad test item and a right article ranked below another line of it.

What it shows: the three round-1 gains were pure paraphrase ("app-only vs delegated permission model"), and the weight was tuned on those test questions; on fresh arms the lexical baseline was already 95%, so expansion added nothing measurable. Expansion never changes a verdict (its words are not key words) and made packs slightly smaller. The two rounds' expansions stay in the index; the rest of the kb is not expanded (`kb/_self/doc2query.md`).

## Models and hand-off patterns

**Setup:** Claude Code 2.1.283, this clone with the user's plugins loaded; 259 topics, 88 eval questions, the persisted index. `_tools/agent_bench.py`, one headless `claude -p` per scenario and config, 76 runs. Scenarios: s1 one fact (LAPS password length), s2 a data row (Delivery Optimization port), s3 three parts, s4 a count (partial intune articles), s5 off-domain (EKS autoscaler), s6 a false `good` (GPO Central Store matched `windows/winget.md` word by word), s7 not in the kb then (KRBTGT reset). First run of each prompt (it pays the cache write, about 11-34k tokens):

| scenario | Haiku | Sonnet | Opus | Opus + Haiku `kb-lookup` agent |
|---|---|---|---|---|
| s1 one fact | $0.031, 9 s | $0.143, 7 s | $0.286, 12 s | $0.204, 25 s |
| s2 data row | $0.030, 14 s | $0.094, 12 s | $0.184, 10 s | - |
| s3 three parts | $0.036, 10 s | $0.112, 12 s | $0.231, 16 s | $0.219, 33 s |
| s4 count | $0.030, 14 s | $0.087, 7 s | $0.183, 12 s | $0.213, 31 s |
| s5 off-domain | $0.024-0.029, 9-12 s | $0.087, 8 s | $0.184, 15 s | - |
| s6 false good + live docs | $0.034-0.051, 21-24 s | $0.199-0.247, 19-21 s | $0.290, 31 s | $0.365, 80 s |
| s7 live docs | $0.047-0.053, 16-17 s | $0.139-0.153, 16-20 s | $0.272, 23 s | $0.313, 48 s |

- Every run passed its checks; quality differed where the model had to judge. Only Opus said s6's `good` was a false match; Haiku once answered s5 without calling the kb, and its s7 synthesis added a wrong reason.
- **Handing a lookup to the Haiku `kb-lookup` agent never saved money** (the caller still pays its own start) and took 2-3 times as long.
- **A model told to route does not route reliably.** A Haiku main session told to hand live-docs work to a Sonnet agent did so in 1 of 4 hard runs ($0.119 that time, against $0.199-0.247 for Sonnet alone). Denying Haiku the docs tools to force the hand-off also denied them to the subagent, so it fell back to a general-purpose agent: $0.24-0.26 and 139-175 s.

## Routing by verdict (`kb_ask.py`)

**Setup:** as the previous section. The router in its current form: counts and "who cites" by the tools; parts split before routing; `good` to a tool-less Haiku reader with the packs in the prompt, which answers `INSUFFICIENT` and escalates when the facts are only related; `weak`/`none` to Sonnet at `--effort low` with only the kb and docs servers; every `claude -p` without the user's plugins and MCP servers. 8 scenarios x 2 runs.

What each part of that setup saves, measured by adding it to a router that sent `good` to Haiku and the rest to Sonnet, both with every tool and the user's plugins:

| part | measured |
|---|---|
| `claude -p` without user plugins and MCP servers (`--setting-sources project,local --strict-mcp-config`) | start context 29.9k -> 24.8k; first run $0.027 -> $0.018 |
| no tools for the reader (`--tools ""`) | start context 24.8k -> 9.8k; repeat $0.0054 -> $0.0027 |
| sufficiency check (`INSUFFICIENT`, escalate) | a Purview endpoint DLP false `good` escalated to Sonnet and was answered from live docs, labelled; $0.115-0.121 |
| counts and "who cites S123" by `audit` / `cited_lines` | $0, 0.5 s (was $0.098 on Sonnet) |
| parts split (numbered items or several `?` questions) | three parts stay on Haiku: $0.013 (was $0.121 on Sonnet) |
| Sonnet at low effort with only the kb and docs servers | off-domain $0.044-0.046 (was $0.084); escalated research $0.115-0.121 (Sonnet alone: $0.199-0.247) |
| request words as stop words ("answer from the kb with citation") | a covered question stays `good` on Haiku instead of `weak` on Sonnet |

Router per question, first run / repeat: single fact $0.0095 / $0.0039, data row $0.0085 / $0.0056, three parts $0.0135 / $0.0130, count $0 / $0, off-domain $0.044 / $0.046, Central Store $0.014 / $0.015, KRBTGT $0.013 / $0.014, false good escalated $0.121 / $0.115. Opus alone on the same first runs: $0.18-0.29. Every check passed.

Checked and left as they are: the prompt cache lifetime (a subscription already gets one hour on the main conversation; on an API key set `promptCacheTtl: 1h` only when lookups repeat more than five minutes apart); rerankers and dense retrieval (the misses are about meaning, which the reader's check handles more cheaply).

## Router against web search

**Setup:** as the previous section. Web search: `agent_bench.py web-<model>`, a `claude -p` in an empty directory with no kb, plugins, skills or MCP servers, only WebSearch and WebFetch (an installed it-ops-kb plugin must be kept out: its skill leaks in otherwise). 2 runs per question.

| per question (mean) | cost | wall time | input tokens | correct |
|---|---|---|---|---|
| kb router, 5 questions the kb covers | $0.011 | 8.9 s | 10.4k | 10/10 |
| web search, Sonnet, same 5 | $0.128 | 26.9 s | 98k | 10/10 |
| web search, Opus, same 5 | $0.228 | 26.7 s | 103k | 10/10 |
| web search, Haiku, same 5 | $0.025 | 11.9 s | 43k | 8/10 |
| kb router, not covered (false good, escalated) | $0.118 | 23.2 s | 89k | 2/2 |
| web search, Sonnet, same question | $0.153 | 29.3 s | 82k | 2/2 |

- Covered: about 12x cheaper and 3x faster than Sonnet web search, 20x cheaper than Opus, at a tenth of the input. The three-part question: $0.013 and 9 s against $0.29-0.39, 35-42 s and 195-241k tokens (7-8 page fetches).
- Haiku web search is cheap but not a search: in 5 of 12 runs it made no tool call and answered from memory, failing 3 of 12 checks; the router's Haiku reads cited facts, 12/12.
- Not covered: the router costs a web search plus the reader's check (about $0.01 and a few seconds) and labels the answer as live docs.

## How-to questions and SNIPPET units

**Setup:** Claude Code 2.1.283; 265 topics, 111 eval questions. Code examples are `SNIPPET:` units with evidence (179 of 191 blocks; 12 are illustrations), and facts read from source code are tagged `CODE`. Three how-to scenarios (`h1_gmsa`, `h2_applock`, `h3_mggraph` in `_tools/agent_bench.py`), one run each, against the same kb with the blocks unchecked and untagged:

| config | unchecked blocks: cost, checks | SNIPPET units: cost, checks |
|---|---|---|
| Haiku | $0.168, 8/9 (h2 missed `@LockTimeout = 0` and `sp_releaseapplock`) | $0.126, 9/9 |
| Sonnet | $0.427, 9/9 | $0.352, 9/9 |

One run per cell, so the cost difference is within noise; Haiku's h2 check is the real difference (it reproduced the whole lock-and-release snippet). Every run used `kb_pack` first and 1-4 kb calls. Checking the blocks against their sources found real defects: an undocumented assign endpoint, a cmdlet that does not exist (`New-MgDeviceManagementReportExportJob`), compliance JSON without its `Rules` wrapper, wrong runtime and auth types in a Copilot plugin manifest, a VS Code input missing a required field.

## Bare agent against agent with the kb

**Setup:** Claude Code 2.1.282 (subagents) and 2.1.283 (headless); Haiku 4.5, Sonnet 5, Opus 5.5; 265 topics with CODE and SNIPPET. 24 subagents (4 scenarios x bare/kb x 3 models) and 134 headless runs (10 scenarios x 7 configs x 2 runs, billed, $17.08). Per-run tables: `kb/_self/reports/benchmark-bare-vs-kb.md`.

- Covered questions, same model: kb 38-39% cheaper on Haiku and Sonnet, the same on Opus (a session in this clone starts at 58-90k tokens, the bare empty directory at 17-56k), 41-69% faster, 1-2 tool calls instead of 5-6, never less correct.
- The router: $0.018, 9 s and 14k input per covered question; 12 of 14 fully right (the Haiku reader dropped the TGT step of `x1_synth` twice).
- Not covered: the kb arms cost the same or slightly more; Sonnet stopped at `none` on the Purview question; Opus was right in all 4 runs.
- A run refused by a usage limit returns "You've hit your session limit" at $0; `agent_bench.py` records it as an error, not an answer.

## Tool speed

**Setup:** Python 3.11 in a Linux container, 259 topics, 85 eval questions; "before" is the corpus rebuilt in memory by every process (and by the MCP server after 30 s idle), with a second chunker for `search`; "now" is the persisted `sqlite3` index keyed by a file fingerprint, one engine, and memoized stemming. Output was byte-identical on every tool surface (255 packs in three formats, search, facts, audit, `src --cited`, `topics-for`, show, the `kb:` hook, an MCP session, the checks and the git history commands).

| path | before | now |
|---|---|---|
| `rag.py pack` (CLI, cold) | 3.93 s | 0.06 s |
| `kb:` hook | 2.05-2.15 s | 0.05-0.09 s |
| `rag.py eval` (85 questions) | 8.63 s | 0.71 s |
| `rag.py search` | 0.29 s | 0.05 s |
| MCP session (12 calls incl. search, audit) | 4.04 s | 1.63 s |
| `kbgit.py check-trailers` (30 commits) | 0.77-0.95 s | 0.41 s |
| index build (once per kb change) | - | about 3 s, 24 MB |

In-process, warm: `pack` 3 ms median, 4.5 ms p95; MCP server start 32 ms, `kb_pack` 1-12 ms; 1,000 random packs 3.3 s. A lookup's time and cost are the model's, not the tools'.
