# Benchmark: bare agent vs agent with the kb

Two measurements of the same comparison: subagents started from a running session (token counts from their transcripts, cost estimated), and fresh headless sessions (cost billed). **Setup:** Claude Code 2.1.282 (subagents) and 2.1.283 (headless); Haiku 4.5, Sonnet 5, Opus 5.5; the kb at 265 topics and 111 eval questions, with CODE facts, SNIPPET units, the persisted index and the verdict router. Re-run with `_tools/agent_bench.py` (`--summary` prints the rows), and replace this file when its setup no longer describes the kb. The README carries the summary; `kb/_self/reports/token-usage.md` puts it next to the other measurements.

**Summary.** On questions the kb covers:
- An agent that uses the kb pays 26-53% less than the same model searching the web, except Opus in a fresh headless session, which paid the same.
- It is 40-70% faster, makes 1-2 tool calls instead of 5-14, and was never less correct.
- The kb router (`kb_ask.py`) costs $0.018 and 9 s per question, 4-13x cheaper than any bare model.

On questions the kb lacks, the kb adds one pack call (1-2k tokens) to the same web research. The cheapest correct setup measured was Haiku reading the kb, not Opus reading the web.

## Subagents (24 runs)

24 subagents started from one Claude Code 2.1.282 session: 4 scenarios x 2 arms x 3 models. **Bare**: no kb tools, no repo files, only WebSearch, WebFetch and the Microsoft Learn docs server. **kb**: `kb_pack` first, live docs only when the kb lacks the answer. Usage comes from the subagent transcripts (per request, deduplicated); cost is list price per MTok (Haiku 4.5 $1 in / $5 out, Sonnet 5 $2 / $10, Opus 5.5 $4 / $20; cache writes 1.25x input, cache reads 0.1x, Opus 5.5 $0.20) plus $0.01 per web search. Input = uncached + cache write + cache read. Each subagent also paid one `ToolSearch > SendMessage` turn to report back, in both arms. One run per cell, so single cells carry run-to-run noise; the totals are the signal.

### Totals (4 scenarios)

| model | bare: input / cost | kb: input / cost | saving |
|---|---|---|---|
| Haiku 4.5 | 928k / $0.336 | 552k / $0.157 | -41% tokens, -53% cost |
| Sonnet 5 | 1,000k / $0.638 | 708k / $0.474 | -29% tokens, -26% cost |
| Opus 5.5 | 940k / $1.204 | 602k / $0.782 | -36% tokens, -35% cost |

Answer checks: bare 11 of 12 fully right (Haiku's synthesis named `requests-kerberos` but not the TGT step), kb 12 of 12. Only kb answers cite `path:line` and a tag. On the three questions the kb covers, the kb arm used 1-2 kb calls; the bare arm used 1-14 docs or web calls.

### Per scenario (input tokens, cost, wall time, route)

**s1 one fact**: "What is the default Windows LAPS password length?" (answer: 14)

| model | bare | kb |
|---|---|---|
| Haiku | 94k, $0.056, 14 s: ToolSearch > docs_search | 87k, $0.028, 12 s: ToolSearch > kb_pack |
| Sonnet | 235k, $0.122, 14 s: ToolSearch > WebSearch > ToolSearch > SendMessage | 190k, $0.161, 9 s: kb_pack > ToolSearch > SendMessage |
| Opus | 185k, $0.316, 14 s: ToolSearch > docs_search > SendMessage | 79k, $0.142, 8 s: kb_pack |

**h1 how-to (code)**: "PowerShell to create a gMSA, let a server group retrieve its password, install and test it."

| model | bare | kb |
|---|---|---|
| Haiku | 197k, $0.064, 24 s: ToolSearch > docs_search x2 > docs_fetch x2 | 87k, $0.030, 15 s: ToolSearch > kb_pack |
| Sonnet | 301k, $0.187, 16 s: ToolSearch > docs_search x2 > ToolSearch > SendMessage | 241k, $0.122, 12 s: kb_pack > kb_show > ToolSearch > SendMessage |
| Opus | 237k, $0.291, 38 s: ToolSearch > docs_fetch x2 > SendMessage | 122k, $0.172, 16 s: kb_pack > kb_show |

**x1 cross-topic synthesis**: "A Python CLI calls the ConfigMgr AdminService as the engineer: which auth works on 2509+, what the Python side needs, which ConfigMgr permission?"

| model | bare | kb |
|---|---|---|
| Haiku | 383k, $0.146, 54 s: 14 calls (docs_search x6, docs_fetch x4, WebSearch x4) | 91k, $0.034, 16 s: ToolSearch > kb_pack |
| Sonnet | 225k, $0.190, 28 s: ToolSearch > docs_search x4 | 191k, $0.111, 11 s: kb_pack > ToolSearch > SendMessage |
| Opus | 381k, $0.378, 47 s: ToolSearch > docs_search > docs_fetch x2 > docs_search > SendMessage | 184k, $0.238, 25 s: kb_pack > ToolSearch > SendMessage |

**o1 not in the kb**: "Run the Kubernetes Cluster Autoscaler on AWS EKS with spot instances" (kb arm may fall back to the web)

| model | bare | kb |
|---|---|---|
| Haiku | 254k, $0.070, 42 s: ToolSearch > WebSearch > WebFetch x5 > WebSearch | 287k, $0.065, 37 s: ToolSearch > kb_pack (none) > ToolSearch > WebSearch > WebFetch x5 |
| Sonnet | 238k, $0.140, 35 s: ToolSearch > WebSearch > WebFetch > SendMessage | 87k, $0.079, 13 s: kb_pack (none), then answered from memory and said so |
| Opus | 137k, $0.218, 32 s: ToolSearch > WebFetch x2 | 218k, $0.229, 26 s: kb_pack (none) > ToolSearch > WebFetch x2 |

### What it shows

- Where the kb covers the question, it saved tokens and cost in 8 of 9 cells (up to -76% tokens and -77% cost), with one `kb_pack` call instead of a search-and-fetch loop, and it was faster in all 9 (8-25 s against 14-54 s). The exception: Sonnet's single fact cost $0.161 against $0.122, because the kb subagent paid a larger cache write for the same 4 turns.
- The gain grows with the question: a cross-topic synthesis cost bare Haiku 14 calls and 383k tokens, the kb arm one pack and 91k.
- Where the kb lacks the answer, it costs one extra pack (about 1-2k tokens) on top of the same web research: no saving, no real loss. Sonnet once skipped the web step and answered from memory, labelled as unverified.
- Haiku with the kb ($0.028-0.034 per covered question) beats Opus without it ($0.29-0.38) on cost by about 10x, at equal checks.
- Most of every subagent's input is its fixed start context (about 25-50k tokens re-read each turn), so fewer turns is where the kb saves; a lookup inline in a running session, or through `kb:` / `kb_ask.py`, avoids that start cost entirely (see "When it pays off").

## Headless sessions, billed cost (134 runs)

`_tools/agent_bench.py` ran each question as a fresh `claude -p` session (Claude Code 2.1.283), 2 runs per cell, and recorded the billed cost, tokens, time, the ordered tool calls and a regex check per expected answer element. **Bare** (`web-<model>`): an empty directory, no kb, plugins, skills or MCP servers, only WebSearch and WebFetch. **kb** (`<model>`): this clone with the user's plugins, the `kb` MCP server and live docs allowed. **kb router**: `kb_ask.py`, which routes on the pack's verdict: `good` to a tool-less Haiku reader with the pack in the prompt, `weak`/`none` to Sonnet at low effort with the kb and docs servers, counts to a tool with no model. Models reported by the runs: `claude-haiku-4-5-20251001`, `claude-sonnet-5`, `claude-opus-5-5`; bare Sonnet and Opus sessions also bill a little Haiku for WebFetch page summaries. Total spend $17.08. 69 runs of the first pass hit the session limit and returned "You've hit your session limit" at $0; they were discarded and re-run; `agent_bench.py` records such runs as errors, not as free answers.

Mean per question, 2 runs each:

| arm | 7 questions the kb covers: cost / time / input / tool calls / fully right | 2 questions it does not: cost / time / fully right |
|---|---|---|
| bare Haiku | $0.067 / 27 s / 132k / 6.4 / 11 of 14 | $0.071 / 35 s / 2 of 4 |
| bare Sonnet | $0.180 / 45 s / 155k / 5.8 / 13 of 14 | $0.183 / 44 s / 2 of 4 |
| bare Opus | $0.230 / 31 s / 99k / 4.9 / 14 of 14 | $0.249 / 37 s / 2 of 4 |
| kb Haiku | $0.042 / 16 s / 104k / 2.4 / 14 of 14 | $0.061 / 25 s / 3 of 4 |
| kb Sonnet | $0.110 / 14 s / 99k / 1.1 / 13 of 14 | $0.118 / 18 s / 2 of 4 |
| kb Opus | $0.229 / 18 s / 81k / 1.4 / 14 of 14 | $0.333 / 36 s / 4 of 4 |
| kb router | **$0.018 / 9 s / 14k / 0 / 12 of 14** | $0.072 / 17 s / 2 of 4 |

What the headless runs add to the subagent results:
- **Same model, kb vs bare, covered questions:** Haiku 38% cheaper, Sonnet 39% cheaper, Opus the same price; all three 41-69% faster, with 1-2 tool calls instead of 5-6, and never less correct.
- **Why Opus saves nothing here:** a session in this clone starts with 58-90k tokens of context (the user's plugins, skills, MCP tool definitions, `AGENTS.md`), against 17-56k for the bare empty directory. On a one-fact question that start costs as much as the web pages the bare session reads. The saving grows with the question: three facts from three domains cost bare Sonnet $0.41-0.47, 93 s and 13 page reads, kb Sonnet $0.11-0.12, 10-15 s and one pack.
- **The router is the efficient path:** $0.018 and 9 s per covered question, 13x cheaper than bare Opus and 4x cheaper than bare Haiku, at 10% of the input tokens, because the kb, not a model, chooses the evidence. Its misses: the Haiku reader named the Kerberos requirement but not the TGT step on `x1` (both runs), and the Purview false `good` needed an escalation.
- **Bare Haiku is not a search:** on both how-to questions it answered from memory with no tool call (right this time, unsourced), and on the three-part question it read 12-15 pages and got 1-2 of 3 facts.
- **Not in the kb:** the kb arms pay one pack and then do the same web research, at the same or a slightly higher price. Sonnet stopped at "the kb does not cover this" on the Purview question (the `AGENTS.md` rule for `none`), which the check counts as a miss; Opus researched the live docs and was the only arm right in all 4 runs.
- **Answers:** kb answers cite `path:line`, the tag and the source url; bare answers cite urls only.

Per scenario: the case, cost, mean time and tokens, checks passed over both runs, and the route.

**s1_fact, one fact.** kb arm asked: "What is the default Windows LAPS password length? Answer from the kb with citation." Bare arm asked: "What is the default Windows LAPS password length? Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.043 / $0.051 | 14 s | 87k | 742 | 2/2 | ToolSearch > WebFetch x2 |
| bare Sonnet | $0.117 / $0.135 | 19 s | 108k | 758 | 2/2 | ToolSearch > WebSearch > WebFetch |
| bare Opus | $0.116 / $0.254 | 15 s | 65k | 883 | 2/2 | ToolSearch > WebFetch; ToolSearch > WebFetch x2 |
| kb Haiku | $0.030 / $0.032 | 13 s | 58k | 449 | 2/2 | kb_pack |
| kb Sonnet | $0.105 / $0.106 | 16 s | 92k | 170 | 2/2 | kb_pack |
| kb Opus | $0.296 / $0.206 | 14 s | 67k | 504 | 2/2 | kb_pack |
| kb router (`kb_ask.py`) | $0.010 / $0.004 | 8 s | 10k | 522 | 2/2 | pack:good > reader:haiku |

**s2_fact_csv, one fact from a data table.** kb arm asked: "Which TCP port does Delivery Optimization use for peer-to-peer traffic? Answer from the kb with citation." Bare arm asked: "Which TCP port does Delivery Optimization use for peer-to-peer traffic? Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.037 / $0.055 | 29 s | 219k | 1888 | 2/2 | ToolSearch > WebFetch x5; ToolSearch > WebFetch x14 |
| bare Sonnet | $0.133 / $0.159 | 21 s | 151k | 1159 | 2/2 | ToolSearch > WebFetch x2; ToolSearch > WebFetch x4 |
| bare Opus | $0.215 / $0.191 | 18 s | 92k | 1122 | 2/2 | ToolSearch > WebFetch x3; ToolSearch > WebFetch x2 |
| kb Haiku | $0.032 / $0.034 | 16 s | 58k | 780 | 2/2 | kb_pack |
| kb Sonnet | $0.101 / $0.102 | 12 s | 90k | 160 | 2/2 | kb_pack |
| kb Opus | $0.193 / $0.200 | 15 s | 67k | 616 | 2/2 | kb_pack |
| kb router (`kb_ask.py`) | $0.008 / $0.003 | 6 s | 9k | 334 | 2/2 | pack:good > reader:haiku |

**s3_multi, three facts from three domains.** kb arm asked: "Answer from the kb, cite path:line for each: (1) default Windows LAPS password length; (2) the Delivery Optimization peer-to-peer port; (3) which Claude Code version added the Elicitation hook." Bare arm asked: "Cite the source url for each: (1) default Windows LAPS password length; (2) the Delivery Optimization peer-to-peer port; (3) which Claude Code version added the Elicitation hook."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.133 / $0.174 | 47 s | 235k | 2729 | 3/6 | ToolSearch > WebFetch x12; ToolSearch > WebFetch x15 |
| bare Sonnet | $0.411 / $0.473 | 93 s | 361k | 5498 | 6/6 | ToolSearch > WebSearch x3 > WebFetch x7 > ToolSearch x2 > WebFetch; ToolSearch > WebSearch x3 > WebFetch x6 > WebSearch x2 > WebFetch x3 |
| bare Opus | $0.365 / $0.409 | 33 s | 170k | 1898 | 6/6 | ToolSearch > WebFetch x4 > WebSearch > WebFetch x2 |
| kb Haiku | $0.035 / $0.036 | 13 s | 60k | 706 | 6/6 | kb_pack |
| kb Sonnet | $0.112 / $0.115 | 13 s | 93k | 275 | 6/6 | kb_pack |
| kb Opus | $0.218 / $0.218 | 11 s | 70k | 648 | 6/6 | kb_pack |
| kb router (`kb_ask.py`) | $0.016 / $0.006 | 10 s | 11k | 934 | 6/6 | pack:good > reader:haiku |

**h1_gmsa, how-to, PowerShell.** kb arm asked: "Using the kb, give the PowerShell to create a gMSA, allow a server group to retrieve its password, and install and test it on the server. Cite path:line." Bare arm asked: "Give the PowerShell to create a gMSA, allow a server group to retrieve its password, and install and test it on the server. Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.009 / $0.009 | 10 s | 17k | 973 | 6/6 | no tool call |
| bare Sonnet | $0.144 / $0.141 | 37 s | 121k | 2550 | 6/6 | ToolSearch > WebSearch > WebFetch x2; ToolSearch > WebSearch x3 |
| bare Opus | $0.254 / $0.334 | 38 s | 115k | 3218 | 6/6 | ToolSearch > WebFetch x4; ToolSearch > WebFetch x3 > WebSearch > WebFetch |
| kb Haiku | $0.050 / $0.049 | 18 s | 157k | 957 | 6/6 | kb_pack x3 > kb_show; kb_pack x3 > Bash |
| kb Sonnet | $0.119 / $0.119 | 17 s | 93k | 638 | 6/6 | kb_pack |
| kb Opus | $0.250 / $0.237 | 24 s | 88k | 1600 | 6/6 | kb_pack > kb_show; kb_pack |
| kb router (`kb_ask.py`) | $0.011 / $0.005 | 10 s | 10k | 676 | 6/6 | pack:good > reader:haiku |

**h2_applock, how-to, T-SQL.** kb arm asked: "Using the kb, show T-SQL that takes an exclusive session-owned application lock without waiting, fails if it is held, and releases it. Cite path:line." Bare arm asked: "Show T-SQL that takes an exclusive session-owned application lock without waiting, fails if it is held, and releases it. Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.010 / $0.008 | 10 s | 17k | 905 | 6/6 | no tool call |
| bare Sonnet | $0.017 / $0.016 | 11 s | 22k | 941 | 6/6 | no tool call |
| bare Opus | $0.139 / $0.123 | 24 s | 56k | 2090 | 6/6 | ToolSearch > WebFetch x2 |
| kb Haiku | $0.049 / $0.081 | 24 s | 246k | 1593 | 6/6 | kb_pack x4 > kb_show; kb_pack > Skill > Read x2 > Bash x2 > Read > Bash |
| kb Sonnet | $0.116 / $0.117 | 18 s | 137k | 474 | 6/6 | kb_pack > kb_show |
| kb Opus | $0.239 / $0.222 | 21 s | 120k | 1227 | 6/6 | kb_pack > ToolSearch > kb_show; kb_pack > kb_show |
| kb router (`kb_ask.py`) | $0.144 / $0.010 | 8 s | 35k | 358 | 6/6 | pack:weak > researcher:sonnet |

**x1_synth, cross-topic synthesis.** kb arm asked: "Using the kb: a Python CLI must call the ConfigMgr AdminService as the engineer's own identity. Which authentication works on ConfigMgr 2509 and later, what does the Python side need before the call, and what ConfigMgr permission must the account have? Cite path:line." Bare arm asked: "A Python CLI must call the ConfigMgr AdminService as the engineer's own identity. Which authentication works on ConfigMgr 2509 and later, what does the Python side need before the call, and what ConfigMgr permission must the account have? Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.103 / $0.264 | 62 s | 274k | 2798 | 5/6 | ToolSearch > WebFetch x11; ToolSearch > WebSearch > WebFetch > WebSearch x3 > WebFetch > WebSearch x2 > WebFetch > WebSearch > WebFetch > WebSearch |
| bare Sonnet | $0.247 / $0.202 | 70 s | 155k | 4340 | 5/6 | ToolSearch > WebSearch x2 > WebFetch > WebSearch > WebFetch > WebSearch x2; ToolSearch > WebSearch x2 > WebFetch x3 > WebSearch |
| bare Opus | $0.279 / $0.232 | 53 s | 125k | 3288 | 6/6 | ToolSearch > WebFetch > WebSearch > WebFetch x5; ToolSearch > WebFetch x2 > WebSearch > WebFetch x3 |
| kb Haiku | $0.036 / $0.037 | 12 s | 61k | 842 | 6/6 | kb_pack |
| kb Sonnet | $0.115 / $0.106 | 10 s | 93k | 352 | 5/6 | kb_pack |
| kb Opus | $0.239 / $0.269 | 25 s | 89k | 1716 | 6/6 | kb_pack; kb_pack > Bash |
| kb router (`kb_ask.py`) | $0.008 / $0.007 | 13 s | 10k | 1229 | 4/6 | pack:good > reader:haiku |

**s7_web, procedure (KRBTGT reset).** kb arm asked: "How should the KRBTGT account password be reset safely in an AD domain (how many times, how long between resets)? Check the kb first; if it lacks this, use live docs or web search and label the source." Bare arm asked: "How should the KRBTGT account password be reset safely in an AD domain (how many times, how long between resets)? Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.018 / $0.028 | 18 s | 76k | 1208 | 4/4 | ToolSearch > WebFetch; ToolSearch > WebFetch x5 |
| bare Sonnet | $0.155 / $0.174 | 62 s | 165k | 3623 | 4/4 | ToolSearch > WebSearch x2 > WebFetch x4; ToolSearch > WebSearch x2 > WebFetch x5 |
| bare Opus | $0.157 / $0.144 | 36 s | 72k | 2248 | 4/4 | ToolSearch > WebSearch > WebFetch > WebSearch; ToolSearch > WebSearch > WebFetch x2 |
| kb Haiku | $0.039 / $0.041 | 14 s | 90k | 856 | 4/4 | kb_pack > kb_show |
| kb Sonnet | $0.102 / $0.101 | 10 s | 91k | 268 | 4/4 | kb_pack |
| kb Opus | $0.213 / $0.204 | 16 s | 67k | 1117 | 4/4 | kb_pack |
| kb router (`kb_ask.py`) | $0.012 / $0.005 | 11 s | 10k | 770 | 4/4 | pack:good > reader:haiku |

**s8_falsegood2, not in the kb, the pack looks relevant.** kb arm asked: "Microsoft Purview Data Loss Prevention endpoint DLP onboarding requirements" Bare arm asked: "Microsoft Purview Data Loss Prevention endpoint DLP onboarding requirements. Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.041 / $0.056 | 26 s | 70k | 1662 | 2/4 | ToolSearch > WebFetch x2; ToolSearch > WebSearch > WebFetch |
| bare Sonnet | $0.194 / $0.236 | 45 s | 147k | 3230 | 2/4 | ToolSearch > WebSearch x2 > WebFetch x4 |
| bare Opus | $0.221 / $0.254 | 33 s | 96k | 3004 | 2/4 | ToolSearch > WebFetch x3; ToolSearch > WebFetch x4 |
| kb Haiku | $0.053 / $0.031 | 18 s | 77k | 1242 | 3/4 | kb_pack > learn_docs_search; kb_pack |
| kb Sonnet | $0.105 / $0.106 | 11 s | 91k | 186 | 0/4 | kb_pack |
| kb Opus | $0.407 / $0.405 | 33 s | 237k | 2175 | 4/4 | kb_pack x2 > ToolSearch > learn_docs_search > ToolSearch > learn_docs_fetch; kb_pack x2 > ToolSearch > learn_docs_search > learn_docs_fetch |
| kb router (`kb_ask.py`) | $0.064 / $0.064 | 16 s | 46k | 680 | 2/4 | pack:good > reader:haiku > escalate > researcher:sonnet |

**o1_offkb, not in the kb, off-domain.** kb arm asked: "How do I run the Kubernetes Cluster Autoscaler on AWS EKS with spot instances? Check the kb first; if it lacks this, use live docs or web search and label the source." Bare arm asked: "How do I run the Kubernetes Cluster Autoscaler on AWS EKS with spot instances? Cite the source urls."

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| bare Haiku | $0.062 / $0.127 | 45 s | 126k | 1939 | 4/4 | ToolSearch > WebFetch x4; ToolSearch > WebSearch > WebFetch x2 > WebSearch > WebFetch x3 |
| bare Sonnet | $0.150 / $0.151 | 43 s | 102k | 2744 | 4/4 | ToolSearch > WebSearch x2 > WebFetch x2 |
| bare Opus | $0.257 / $0.265 | 41 s | 95k | 3388 | 4/4 | ToolSearch > WebFetch x3 |
| kb Haiku | $0.066 / $0.093 | 31 s | 153k | 1404 | 4/4 | kb_pack > WebSearch > WebFetch x2; kb_pack > WebSearch > WebFetch x2 > ToolSearch > WebFetch x2 |
| kb Sonnet | $0.110 / $0.152 | 24 s | 138k | 1270 | 4/4 | kb_pack; kb_pack > ToolSearch > WebFetch |
| kb Opus | $0.423 / $0.097 | 39 s | 162k | 2476 | 4/4 | kb_pack > ToolSearch > WebFetch > WebSearch > WebFetch; kb_pack > ToolSearch > WebFetch |
| kb router (`kb_ask.py`) | $0.080 / $0.081 | 18 s | 109k | 1198 | 4/4 | pack:weak > researcher:sonnet > ToolSearch > WebSearch |

**s4_count, count over the kb itself.** kb arm asked: "How many intune articles in the kb have status partial? Give the number and list them." (no bare arm: the question is about the kb itself)

| arm | cost run 1 / run 2 | time | input tokens | output | checks | route (run 1; run 2 if different) |
|---|---|---|---|---|---|---|
| kb Haiku | $0.050 / $0.014 | 15 s | 133k | 948 | 4/4 | bash > Bash > kb_pack > ToolSearch > kb_audit; ToolSearch > kb_audit |
| kb Sonnet | $0.100 / $0.100 | 10 s | 91k | 184 | 4/4 | Bash |
| kb Opus | $0.188 / $0.028 | 11 s | 67k | 515 | 4/4 | Bash |
| kb router (`kb_ask.py`) | $0.000 / $0.000 | 1 s | 0k | 0 | 4/4 | kb_ask:tool |
