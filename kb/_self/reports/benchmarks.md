# Benchmarks

What a kb lookup costs an agent, against the same agent without the kb, and what each of the kb's techniques and tools costs or saves. `kb/_self/design.md` draws the conclusions and `kb/_self/token-efficiency.md` lists the techniques; `kb/_self/reports/fact-diff.md` holds the fact diff's measurements.

- **Data:** every number is a row of `kb/_self/reports/benchmarks.csv`, one row per scenario, record, case, arm and metric. A record is one measurement: the date of a run of `_tools/benchmarks.py`, or, for the numbers of the reports this one replaced, the commit that wrote them (found with `git log -S` and `git blame`), with its date, the Claude Code version and the kb size its setup stated (empty where it stated none). The historical rows keep each cell as written (`$0.043 / $0.051` for two runs); a number those reports gave only in prose is a row with metric `text` and its sentence in `note`. The 2026-09-28 runs name the commit of the runner they ran; the runs of all scenarios but the query log's ran before `c038ae6` (the query log's entry change) was under them, which changes no file those scenarios read.
- **Tables:** every table below between `bench:` markers is generated from the results file by `python3 _tools/benchmarks.py report`; `report --check` (a test in `_tools/tests.py`) fails when a table, or a number in `README.md`, disagrees with it. A cell lists each record's value in date order (`->` between them) and the change of the newest from the one before it; a historical cell of several numbers counts as their mean.
- **Re-run:** `python3 _tools/benchmarks.py run` runs every scenario, `run <scenario>` one; each section names its command. Paid runs are fresh `claude -p` sessions; the rest run no model.
- **Counting:** input is uncached + cache-write + cache-read input tokens, read from each run's result event or transcript, never from an agent's own account. Output (`out`) is the sum of the result event's `modelUsage` `outputTokens` (the whole run: subagents and internal calls such as compaction included, thinking inside the count, `claude/ci-and-headless.md`; the event's `usage.output_tokens`, the main loop alone, when `modelUsage` has none), never the sum of the stream's per-message usage, whose output counts are partial and read a fraction of the run's output; `out` therefore covers the scope of the run's `total_cost_usd`, while the input counts are those of the main session's requests. A run's list cost (`list_cost`, the pool's check that a reported cost is the sum of its parts) prices that whole scope: the main session's requests, the output and uncached input `modelUsage` bills beyond them, a model the session never requested (the Haiku 5.5 call a WebFetch or WebSearch runs inside the tool, in whatever session, priced in its lowest tier) and the web searches billed, $0.01 each, on every arm. Effective input weights cache writes by their rate over the input price (1.25x for a 5-minute write, 2x for a 1-hour write: a request's usage splits its writes by TTL when the stream carries `cache_creation`, else the run's billing surface decides, one hour on a subscription) and cache reads by the read price of the model the run reports over its input price: 0.1x for Haiku 4.5, Haiku 5.5 (both of its price tiers), Sonnet 5 and Sonnet 5.5 (a Sonnet 5.5 run on Claude Code 2.1.296 or later is priced at the pricing page's $0.10 per MTok, one on an earlier version at the $0.20 that version's cost figure counted: `READ_BEFORE` in `_tools/bench_core.py`, and the resolved conflict in `kb/public/_conflicts.md`), 0.05x for Opus 5.5. A run is priced at its model's own list price per MTok (`PRICE` in `_tools/bench_core.py`, source S2131), the tier of a prompt-length price (Haiku 5.5) taken per request and the highest one a run reached recorded in the row's note; the stored rows of earlier batches keep the values they were written with. Dollar costs compare only within one batch, since the run that pays a cache write varies; compare tokens across batches.
- **Isolation:** every `claude -p` runs with hooks off (`--settings '{"disableAllHooks": true}'`) from a throwaway clone of `HEAD` whose query log is `off` and whose `origin` is a local bare repository; the kb and docs servers are registered at local scope for that clone and removed afterwards. The scenarios that measure the query log's hooks run them in a throwaway clone in mode `local` with a local bare `origin`, or as a copy of the plugin whose hook commands write under the scratch directory instead of `~/.claude/plugins/data/`. The historical runs had hooks on; a hook adds no context unless it prints, which the query log's never do.
- **Repetitions:** the re-run uses 1 run per cell where the history used 2, except where a section says otherwise; the history's run-to-run spread (in its cells) is the noise a single run carries. Re-runs on this machine, with other work on it: timings moved by up to 15% (`capture`'s median 47-55 ms over four runs of `querylog-hooks`), `always-on`'s token counts by under 0.1% (8 tokens). Model aliases resolved to Haiku 4.5, Sonnet 5 and Opus 5.5. From Claude Code 2.1.284 `sonnet` resolves to Sonnet 5.5, so a re-run's Sonnet arms change model; "A new model against the one it replaces" compares the two pinned by id.

Spend of the runs of each scenario, per record (paid `claude -p` runs, the Haiku and Sonnet calls made through the query log's own commands included):

<!-- bench:spend -->
| scenario | record | paid runs | input tokens | output tokens | spend |
|---|---|---|---|---|---|
| always-on | 2026-09-28 | 20 | 469,228 | 1,118 | $0.12 |
| always-on | 2026-10-08 | 20 | 423,992 | 156 | $0.02 |
| always-on | 2026-10-12 | 20 | 438,594 | 216 | $0.02 |
| doc2query | 2026-09-28 | 2 | 24,579 | 4,271 | $0.10 |
| files-headless | 2026-09-28 | 14 | 2,157,090 | 14,845 | $1.74 |
| files-subagents | 2026-09-28 | 11 | 362,274 | 8,113 | $1.35 |
| headless | 2026-09-28 | 67 | 5,782,044 | 85,290 | $8.10 |
| host-lookups | 2026-09-28 | 16 | 1,304,536 | 14,136 | $1.50 |
| host-lookups | 2026-10-09 | 16 | 847,989 | 16,522 | $0.86 |
| host-lookups | 2026-10-12 | 16 | 908,661 | 20,561 | $1.22 |
| host-roots | 2026-09-28 | 4 | 340,570 | 3,921 | $0.11 |
| howto | 2026-09-28 | 6 | 690,606 | 6,422 | $0.50 |
| ingest | 2026-09-28 | 1 | 6,947,437 | 26,909 | $2.06 |
| kb-lookup-agent | 2026-09-28 | 3 | 74,652 | 845 | $0.12 |
| kb-lookup-agent | 2026-10-12 | 3 | 71,524 | 1,769 | $0.01 |
| models | 2026-09-28 | 28 | 2,788,545 | 26,211 | $4.01 |
| navigation | 2026-09-30 | 18 | 2,092,986 | 17,421 | $1.44 |
| new-model | 2026-09-28 | 60 | 6,125,840 | 59,832 | $6.62 |
| partial | 2026-09-28 | 13 | 2,522,765 | 21,392 | $1.79 |
| partial | 2026-10-12 | 14 | 1,998,791 | 40,842 | $0.79 |
| pool | 2026-10-08 | 2643 | 256,726,989 | 692,631 | $113.96 |
| pool | 2026-10-09 | 1924 | 215,265,541 | 3,541,683 | $149.54 |
| pool | 2026-10-12 | 1072 | 102,163,906 | 2,523,195 | $61.29 |
| querylog-pipeline | 2026-09-28 | 1 | 7,250 | 2,608 | $0.03 |
| research | 2026-09-28 | 1 | 112,904 | 2,809 | $0.21 |
| retrieval | 2026-09-28 | 1 | 16,352 | 3,331 | $0.07 |
| retrieval | 2026-10-08 | 1 | 10,301 | 3,360 | $0.07 |
| retrieval | 2026-10-12 | 1 | 10,989 | 3,605 | $0.08 |
| route-by-verdict | 2026-09-29 | 36 | 2,723,008 | 57,099 | $3.73 |
| router | 2026-09-28 | 22 | 358,198 | 8,244 | $0.30 |
| subagents | 2026-09-28 | 24 | 724,378 | 23,213 | $3.30 |
| all | | 6078 | 614,492,519 | 7,232,570 | $365.03 |
<!-- /bench -->

## Lookups against the web

### Bare agent against agent with the kb: headless sessions

**Setup:** `python3 _tools/benchmarks.py run headless`. `_tools/agent_bench.py` runs each question as a fresh `claude -p`. **Bare** (`web-<model>`): an empty directory under the clone, no kb, plugins, skills or MCP servers, only WebSearch and WebFetch. **kb** (`<model>`): the clone with the user's plugins, the `kb` server and the Microsoft Learn server allowed. **Router** (`router`): `kb_ask.py`'s routing. A regex check per expected answer element; `s4_count`'s checks read the count from the kb at check time (it was 6 partial Intune articles in the history and is 0 now). The re-run runs each config in its own process at once.

<!-- bench:records headless -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 7c94354 | 2026-09-27 | 7c94354 | 2.1.283 | 265 | 2 | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 1 | $8.10 |
<!-- /bench -->

Mean per question, over the seven questions the kb covers and the two it does not:

<!-- bench:table headless metrics=cost,wall_s,input,tool_calls,fully_right cases=covered (7),not covered (2) -->
| case | arm | cost | wall_s | input | tool_calls | fully_right |
|---|---|---|---|---|---|---|
| covered (7) | web-haiku | $0.067 -> $0.012 (-83%) | 27 s -> 11 s (-58%) | 132k -> 21,782 (-83%) | 6.4 -> 0.3 (-96%) | 11 of 14 -> 5 of 7 |
| not covered (2) | web-haiku | $0.071 -> $0.025 (-65%) | 35 s -> 19 s (-45%) | 34,777 | 1 | 2 of 4 -> 1 of 2 |
| covered (7) | web-sonnet | $0.180 -> $0.192 (+7%) | 45 s -> 74 s (+64%) | 155k -> 187,958 (+21%) | 5.8 -> 6.4 (+11%) | 13 of 14 -> 6 of 7 |
| not covered (2) | web-sonnet | $0.183 -> $0.151 (-18%) | 44 s -> 135 s (+207%) | 104,298 | 4 | 2 of 4 -> 1 of 2 |
| covered (7) | web-opus | $0.230 -> $0.204 (-11%) | 31 s -> 31 s (+0%) | 99k -> 93,372 (-6%) | 4.9 -> 4.6 (-7%) | 14 of 14 -> 7 of 7 |
| not covered (2) | web-opus | $0.249 -> $0.235 (-6%) | 37 s -> 35 s (-4%) | 79,042 | 4 | 2 of 4 -> 1 of 2 |
| covered (7) | haiku | $0.042 -> $0.033 (-21%) | 16 s -> 16 s (-2%) | 104k -> 63,976 (-38%) | 2.4 -> 1.3 (-46%) | 14 of 14 -> 7 of 7 |
| not covered (2) | haiku | $0.061 -> $0.082 (+34%) | 25 s -> 31 s (+25%) | 138,010 | 3.5 | 3 of 4 -> 1 of 2 |
| covered (7) | sonnet | $0.110 -> $0.107 (-3%) | 14 s -> 16 s (+16%) | 99k -> 94,778 (-4%) | 1.1 -> 1.1 (+4%) | 13 of 14 -> 5 of 7 |
| not covered (2) | sonnet | $0.118 -> $0.127 (+7%) | 18 s -> 22 s (+21%) | 132,753 | 2 | 2 of 4 -> 1 of 2 |
| covered (7) | opus | $0.229 -> $0.219 (-4%) | 18 s -> 22 s (+20%) | 81k -> 80,695 (-0%) | 1.4 -> 1.4 (+2%) | 14 of 14 -> 7 of 7 |
| not covered (2) | opus | $0.333 -> $0.401 (+20%) | 36 s -> 46 s (+27%) | 191,143 | 4.5 | 4 of 4 -> 2 of 2 |
| covered (7) | router | $0.018 -> $0.033 (+81%) | 9 s -> 10 s (+12%) | 14k -> 13,690 (-2%) | 0 -> 0 | 12 of 14 -> 5 of 7 |
| not covered (2) | router | $0.072 -> $0.063 (-13%) | 17 s -> 17 s (-2%) | 71,034 | 1 | 2 of 4 -> 1 of 2 |
<!-- /bench -->

Per question:

<!-- bench:table headless metrics=cost,wall_s,input,out,checks cases=s1_fact,s2_fact_csv,s3_multi,s4_count,h1_gmsa,h2_applock,x1_synth,s7_web,s8_falsegood2,o1_offkb -->
| case | arm | cost | wall_s | input | out | checks |
|---|---|---|---|---|---|---|
| s1_fact | web-haiku | $0.043 / $0.051 -> $0.035 (-26%) | 14 s -> 12 s (-11%) | 87k -> 52,255 (-40%) | 742 -> 468 (-37%) | 2/2 -> 1/1 |
| s1_fact | web-sonnet | $0.117 / $0.135 -> $0.056 (-55%) | 19 s -> 13 s (-30%) | 108k -> 70,062 (-35%) | 758 -> 529 (-30%) | 2/2 -> 1/1 |
| s1_fact | web-opus | $0.116 / $0.254 -> $0.119 (-36%) | 15 s -> 19 s (+26%) | 65k -> 55,916 (-14%) | 883 -> 785 (-11%) | 2/2 -> 1/1 |
| s1_fact | haiku | $0.030 / $0.032 -> $0.037 (+19%) | 13 s -> 13 s (-1%) | 58k -> 55,438 (-4%) | 449 -> 578 (+29%) | 2/2 -> 1/1 |
| s1_fact | sonnet | $0.105 / $0.106 -> $0.122 (+16%) | 16 s -> 18 s (+12%) | 92k -> 88,133 (-4%) | 170 -> 284 (+67%) | 2/2 -> 1/1 |
| s1_fact | opus | $0.296 / $0.206 -> $0.209 (-17%) | 14 s -> 16 s (+11%) | 67k -> 65,362 (-2%) | 504 -> 656 (+30%) | 2/2 -> 1/1 |
| s1_fact | router | $0.010 / $0.004 -> $0.022 (+216%) | 8 s -> 6 s (-20%) | 10k -> 9,983 (-0%) | 522 -> 423 (-19%) | 2/2 -> 1/1 |
| s2_fact_csv | web-haiku | $0.037 / $0.055 -> $0.006 (-86%) | 29 s -> 7 s (-77%) | 219k -> 16,687 (-92%) | 1,888 -> 434 (-77%) | 2/2 -> 1/1 |
| s2_fact_csv | web-sonnet | $0.133 / $0.159 -> $0.060 (-59%) | 21 s -> 19 s (-9%) | 151k -> 70,395 (-53%) | 1,159 -> 676 (-42%) | 2/2 -> 1/1 |
| s2_fact_csv | web-opus | $0.215 / $0.191 -> $0.191 (-6%) | 18 s -> 16 s (-8%) | 92k -> 90,136 (-2%) | 1,122 -> 1,025 (-9%) | 2/2 -> 1/1 |
| s2_fact_csv | haiku | $0.032 / $0.034 -> $0.028 (-16%) | 16 s -> 11 s (-32%) | 58k -> 55,133 (-5%) | 780 -> 459 (-41%) | 2/2 -> 1/1 |
| s2_fact_csv | sonnet | $0.101 / $0.102 -> $0.095 (-6%) | 12 s -> 7 s (-42%) | 90k -> 87,887 (-2%) | 160 -> 222 (+39%) | 2/2 -> 1/1 |
| s2_fact_csv | opus | $0.193 / $0.200 -> $0.182 (-7%) | 15 s -> 16 s (+7%) | 67k -> 63,934 (-5%) | 616 -> 620 (+1%) | 2/2 -> 1/1 |
| s2_fact_csv | router | $0.008 / $0.003 -> $0.009 (+56%) | 6 s -> 6 s (+2%) | 9k -> 9,176 (+2%) | 334 -> 459 (+37%) | 2/2 -> 1/1 |
| s3_multi | web-haiku | $0.133 / $0.174 -> $0.007 (-96%) | 47 s -> 19 s (-60%) | 235k -> 16,713 (-93%) | 2,729 -> 477 (-83%) | 3/6 -> 0/3 |
| s3_multi | web-sonnet | $0.411 / $0.473 -> $0.395 (-11%) | 93 s -> 299 s (+222%) | 361k -> 374,079 (+4%) | 5,498 -> 3,789 (-31%) | 6/6 -> 3/3 |
| s3_multi | web-opus | $0.365 / $0.409 -> $0.429 (+11%) | 33 s -> 39 s (+19%) | 170k -> 189,875 (+12%) | 1,898 -> 2,010 (+6%) | 6/6 -> 3/3 |
| s3_multi | haiku | $0.035 / $0.036 -> $0.032 (-9%) | 13 s -> 14 s (+7%) | 60k -> 56,011 (-7%) | 706 -> 871 (+23%) | 6/6 -> 3/3 |
| s3_multi | sonnet | $0.112 / $0.115 -> $0.110 (-3%) | 13 s -> 11 s (-18%) | 93k -> 90,689 (-2%) | 275 -> 293 (+7%) | 6/6 -> 3/3 |
| s3_multi | opus | $0.218 / $0.218 -> $0.210 (-4%) | 11 s -> 17 s (+57%) | 70k -> 67,302 (-4%) | 648 -> 756 (+17%) | 6/6 -> 3/3 |
| s3_multi | router | $0.016 / $0.006 -> $0.015 (+33%) | 10 s -> 8 s (-17%) | 11k -> 11,476 (+4%) | 934 -> 731 (-22%) | 6/6 -> 3/3 |
| h1_gmsa | web-haiku | $0.009 / $0.009 -> $0.009 (+3%) | 10 s -> 11 s (+14%) | 17k -> 16,701 (-2%) | 973 -> 998 (+3%) | 6/6 -> 3/3 |
| h1_gmsa | web-sonnet | $0.144 / $0.141 -> $0.136 (-5%) | 37 s -> 31 s (-17%) | 121k -> 140,021 (+16%) | 2,550 -> 2,413 (-5%) | 6/6 -> 3/3 |
| h1_gmsa | web-opus | $0.254 / $0.334 -> $0.161 (-45%) | 38 s -> 26 s (-32%) | 115k -> 58,534 (-49%) | 3,218 -> 2,542 (-21%) | 6/6 -> 3/3 |
| h1_gmsa | haiku | $0.050 / $0.049 -> $0.032 (-35%) | 18 s -> 14 s (-19%) | 157k -> 56,489 (-64%) | 957 -> 1,067 (+11%) | 6/6 -> 3/3 |
| h1_gmsa | sonnet | $0.119 / $0.119 -> $0.119 (+0%) | 17 s -> 23 s (+37%) | 93k -> 135,727 (+46%) | 638 -> 771 (+21%) | 6/6 -> 3/3 |
| h1_gmsa | opus | $0.250 / $0.237 -> $0.217 (-11%) | 24 s -> 20 s (-19%) | 88k -> 66,599 (-24%) | 1,600 -> 1,374 (-14%) | 6/6 -> 3/3 |
| h1_gmsa | router | $0.011 / $0.005 -> $0.014 (+80%) | 10 s -> 15 s (+50%) | 10k -> 10,109 (+1%) | 676 -> 1,255 (+86%) | 6/6 -> 3/3 |
| h2_applock | web-haiku | $0.010 / $0.008 -> $0.008 (-12%) | 10 s -> 9 s (-10%) | 17k -> 16,696 (-2%) | 905 -> 712 (-21%) | 6/6 -> 3/3 |
| h2_applock | web-sonnet | $0.017 / $0.016 -> $0.075 (+353%) | 11 s -> 23 s (+113%) | 22k -> 70,995 (+223%) | 941 -> 1,308 (+39%) | 6/6 -> 3/3 |
| h2_applock | web-opus | $0.139 / $0.123 -> $0.118 (-10%) | 24 s -> 18 s (-24%) | 56k -> 55,413 (-1%) | 2,090 -> 1,530 (-27%) | 6/6 -> 3/3 |
| h2_applock | haiku | $0.049 / $0.081 -> $0.033 (-49%) | 24 s -> 18 s (-26%) | 246k -> 82,981 (-66%) | 1,593 -> 1,184 (-26%) | 6/6 -> 3/3 |
| h2_applock | sonnet | $0.116 / $0.117 -> $0.093 (-20%) | 18 s -> 12 s (-36%) | 137k -> 86,016 (-37%) | 474 -> 268 (-43%) | 6/6 -> 2/3 |
| h2_applock | opus | $0.239 / $0.222 -> $0.207 (-10%) | 21 s -> 21 s (+1%) | 120k -> 96,845 (-19%) | 1,227 -> 1,294 (+5%) | 6/6 -> 3/3 |
| h2_applock | router | $0.144 / $0.010 -> $0.145 (+88%) | 8 s -> 14 s (+79%) | 35k -> 34,910 (-0%) | 358 -> 494 (+38%) | 6/6 -> 2/3 |
| x1_synth | web-haiku | $0.103 / $0.264 -> $0.008 (-96%) | 62 s -> 9 s (-85%) | 274k -> 16,726 (-94%) | 2,798 -> 640 (-77%) | 5/6 -> 0/3 |
| x1_synth | web-sonnet | $0.247 / $0.202 -> $0.487 (+117%) | 70 s -> 94 s (+35%) | 155k -> 459,351 (+196%) | 4,340 -> 6,172 (+42%) | 5/6 -> 2/3 |
| x1_synth | web-opus | $0.279 / $0.232 -> $0.232 (-9%) | 53 s -> 48 s (-9%) | 125k -> 110,643 (-11%) | 3,288 -> 2,960 (-10%) | 6/6 -> 3/3 |
| x1_synth | haiku | $0.036 / $0.037 -> $0.032 (-12%) | 12 s -> 18 s (+49%) | 61k -> 56,414 (-8%) | 842 -> 941 (+12%) | 6/6 -> 3/3 |
| x1_synth | sonnet | $0.115 / $0.106 -> $0.106 (-4%) | 10 s -> 17 s (+71%) | 93k -> 88,198 (-5%) | 352 -> 658 (+87%) | 5/6 -> 2/3 |
| x1_synth | opus | $0.239 / $0.269 -> $0.278 (+9%) | 25 s -> 34 s (+37%) | 89k -> 105,639 (+19%) | 1,716 -> 2,140 (+25%) | 6/6 -> 3/3 |
| x1_synth | router | $0.008 / $0.007 -> $0.013 (+67%) | 13 s -> 11 s (-17%) | 10k -> 10,176 (+2%) | 1,229 -> 835 (-32%) | 4/6 -> 2/3 |
| s7_web | web-haiku | $0.018 / $0.028 -> $0.009 (-63%) | 18 s -> 12 s (-36%) | 76k -> 16,698 (-78%) | 1,208 -> 850 (-30%) | 4/4 -> 2/2 |
| s7_web | web-sonnet | $0.155 / $0.174 -> $0.136 (-17%) | 62 s -> 38 s (-39%) | 165k -> 130,806 (-21%) | 3,623 -> 2,089 (-42%) | 4/4 -> 2/2 |
| s7_web | web-opus | $0.157 / $0.144 -> $0.177 (+17%) | 36 s -> 50 s (+40%) | 72k -> 93,090 (+29%) | 2,248 -> 2,146 (-5%) | 4/4 -> 2/2 |
| s7_web | haiku | $0.039 / $0.041 -> $0.037 (-6%) | 14 s -> 22 s (+59%) | 90k -> 85,368 (-5%) | 856 -> 1,219 (+42%) | 4/4 -> 2/2 |
| s7_web | sonnet | $0.102 / $0.101 -> $0.102 (+0%) | 10 s -> 27 s (+166%) | 91k -> 86,796 (-5%) | 268 -> 720 (+169%) | 4/4 -> 2/2 |
| s7_web | opus | $0.213 / $0.204 -> $0.228 (+9%) | 16 s -> 28 s (+73%) | 67k -> 99,185 (+48%) | 1,117 -> 1,632 (+46%) | 4/4 -> 2/2 |
| s7_web | router | $0.012 / $0.005 -> $0.011 (+33%) | 11 s -> 10 s (-11%) | 10k -> 9,998 (-0%) | 770 -> 675 (-12%) | 4/4 -> 2/2 |
| s8_falsegood2 | web-haiku | $0.041 / $0.056 -> $0.009 (-82%) | 26 s -> 12 s (-53%) | 70k -> 16,685 (-76%) | 1,662 -> 914 (-45%) | 2/4 -> 0/2 |
| s8_falsegood2 | web-sonnet | $0.194 / $0.236 -> $0.134 (-38%) | 45 s -> 35 s (-22%) | 147k -> 108,313 (-26%) | 3,230 -> 2,344 (-27%) | 2/4 -> 1/2 |
| s8_falsegood2 | web-opus | $0.221 / $0.254 -> $0.270 (+14%) | 33 s -> 33 s (-0%) | 96k -> 97,689 (+2%) | 3,004 -> 3,561 (+19%) | 2/4 -> 1/2 |
| s8_falsegood2 | haiku | $0.053 / $0.031 -> $0.062 (+47%) | 18 s -> 23 s (+27%) | 77k -> 128,612 (+67%) | 1,242 -> 1,419 (+14%) | 3/4 -> 1/2 |
| s8_falsegood2 | sonnet | $0.105 / $0.106 -> $0.094 (-11%) | 11 s -> 12 s (+12%) | 91k -> 86,631 (-5%) | 186 -> 234 (+26%) | 0/4 -> 1/2 |
| s8_falsegood2 | opus | $0.407 / $0.405 -> $0.367 (-10%) | 33 s -> 38 s (+14%) | 237k -> 188,463 (-20%) | 2,175 -> 2,037 (-6%) | 4/4 -> 2/2 |
| s8_falsegood2 | router | $0.064 / $0.064 -> $0.053 (-17%) | 16 s -> 17 s (+4%) | 46k -> 34,914 (-24%) | 680 -> 805 (+18%) | 2/4 -> 1/2 |
| o1_offkb | web-haiku | $0.062 / $0.127 -> $0.041 (-57%) | 45 s -> 26 s (-42%) | 126k -> 52,869 (-58%) | 1,939 -> 1,251 (-35%) | 4/4 -> 2/2 |
| o1_offkb | web-sonnet | $0.150 / $0.151 -> $0.168 (+12%) | 43 s -> 235 s (+447%) | 102k -> 100,282 (-2%) | 2,744 -> 2,770 (+1%) | 4/4 -> 2/2 |
| o1_offkb | web-opus | $0.257 / $0.265 -> $0.200 (-23%) | 41 s -> 38 s (-8%) | 95k -> 60,396 (-36%) | 3,388 -> 2,976 (-12%) | 4/4 -> 2/2 |
| o1_offkb | haiku | $0.066 / $0.093 -> $0.102 (+28%) | 31 s -> 40 s (+28%) | 153k -> 147,407 (-4%) | 1,404 -> 1,615 (+15%) | 4/4 -> 2/2 |
| o1_offkb | sonnet | $0.110 / $0.152 -> $0.159 (+21%) | 24 s -> 31 s (+31%) | 138k -> 178,875 (+30%) | 1,270 -> 1,656 (+30%) | 4/4 -> 2/2 |
| o1_offkb | opus | $0.423 / $0.097 -> $0.434 (+67%) | 39 s -> 54 s (+38%) | 162k -> 193,823 (+20%) | 2,476 -> 3,408 (+38%) | 4/4 -> 2/2 |
| o1_offkb | router | $0.080 / $0.081 -> $0.072 (-10%) | 18 s -> 17 s (-8%) | 109k -> 107,154 (-2%) | 1,198 -> 819 (-32%) | 4/4 -> 2/2 |
| s4_count | haiku | $0.050 / $0.014 -> $0.039 (+22%) | 15 s -> 21 s (+39%) | 133k -> 113,003 (-15%) | 948 -> 1,187 (+25%) | 4/4 -> 2/2 |
| s4_count | sonnet | $0.100 / $0.100 -> $0.116 (+16%) | 10 s -> 26 s (+161%) | 91k -> 176,558 (+94%) | 184 -> 418 (+127%) | 4/4 -> 2/2 |
| s4_count | opus | $0.188 / $0.028 -> $0.190 (+76%) | 11 s -> 22 s (+98%) | 67k -> 96,604 (+44%) | 515 -> 444 (-14%) | 4/4 -> 2/2 |
| s4_count | router | $0.000 / $0.000 -> $0.000 | 1 s -> 1 s (+0%) | 0k -> 0 | 0 -> 0 | 4/4 -> 2/2 |
<!-- /bench -->

What it shows:
- **Same model, kb against bare, on the covered questions:** Sonnet with the kb cost $0.107 and 16 s against $0.192 and 74 s searching the web (44% cheaper, 78% faster); Opus cost about the same either way ($0.219 against $0.204) and was faster with the kb (22 s against 31 s); Haiku with the kb cost $0.033 against the bare arm's $0.012, because bare Haiku made no tool call on 6 of 7 questions and answered from memory (right on four, wrong on `s3_multi` and `x1_synth`). Every kb arm made 1-1.4 tool calls per question, the web arms 4.6-6.4 (Haiku aside).
- **The router** cost $0.033 and 10 s per covered question at 13.7k input, the lowest input of any arm; its first runs paid the reader's cache write ($0.022 on `s1_fact`, $0.003 on the repeat in "Routing by verdict").
- **A new false `none`:** `h2_applock` ("show T-SQL that takes an exclusive session-owned application lock ...") now packs `coverage: none; not in the kb: t-sql`: the correction that makes a question about another product `none` reads "T-SQL" as a product name the article lacks. Sonnet and the router stopped at "the kb does not cover this" (2/3 each), Haiku answered from the same pack (3/3). The history had all arms at 6/6 there.
- **Not covered:** the kb arms paid one pack plus the web research, $0.063-0.401 against $0.025-0.235 bare; only Opus was right on both runs.
- Against the history, one run per cell: covered-question costs moved by -21% to -3% for the kb models and the router's by +81% (a first run per question), within the history's own run-to-run spread (Opus `s1_fact`: $0.296 / $0.206).

### Bare agent against agent with the kb: subagents

**Setup:** `python3 _tools/benchmarks.py run subagents`. Four questions (s1 one fact, h1 a how-to, x1 a cross-topic synthesis, o1 off the kb), a bare and a kb arm, three models: 24 subagents. The history started them from one running session; the re-run starts each from a Haiku `claude -p` (hooks off) that hands the question to an agent defined with `--agents`: **bare** with WebSearch, WebFetch and the Microsoft Learn server only, **kb** with the kb tools first and those after. Usage comes from the subagent transcript (per request), cost is estimated at list price (Haiku 4.5 $1 in / $5 out, Sonnet 5 $2 / $10, Opus 5.5 $4 / $20 per MTok; cache writes 1.25x input, cache reads 0.1x, Opus $0.20; $0.01 per web search). The agents' tools are now set by their definition, so their start context is that agent's own (a few thousand tokens) instead of a general-purpose agent's 25-50k: compare the arms within a record, not the records.

<!-- bench:records subagents -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 7c94354 | 2026-09-27 | 7c94354 | 2.1.282 | 265 | - | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 1 | $3.30 |
<!-- /bench -->

<!-- bench:table subagents metrics=input,cost_est,wall_s,fully_right,checks -->
| case | arm | input | cost_est | wall_s | fully_right | checks |
|---|---|---|---|---|---|---|
| total (4 scenarios) | bare-haiku | 928k -> 280,963 (-70%) | $0.336 -> $0.211 (-37%) | - | 4/4 | - |
| total (4 scenarios) | kb-haiku | 552k -> 136,618 (-75%) | $0.157 -> $0.117 (-25%) | - | 4/4 | - |
| total (4 scenarios) | bare-sonnet | 1,000k -> 95,301 (-90%) | $0.638 -> $0.228 (-64%) | - | 2/4 | - |
| total (4 scenarios) | kb-sonnet | 708k -> 137,703 (-81%) | $0.474 -> $0.189 (-60%) | - | 2/4 | - |
| total (4 scenarios) | bare-opus | 940k -> 424,903 (-55%) | $1.204 -> $0.962 (-20%) | - | 4/4 | - |
| total (4 scenarios) | kb-opus | 602k -> 122,018 (-80%) | $0.782 -> $0.412 (-47%) | - | 4/4 | - |
| s1 | bare-haiku | 94k -> 20,669 (-78%) | $0.056 -> $0.025 (-56%) | 14 s -> 6 s (-59%) | - | 1/1 |
| s1 | kb-haiku | 87k -> 15,571 (-82%) | $0.028 -> $0.015 (-45%) | 12 s -> 4 s (-64%) | - | 1/1 |
| s1 | bare-sonnet | 235k -> 22,100 (-91%) | $0.122 -> $0.040 (-67%) | 14 s -> 3 s (-78%) | - | 1/1 |
| s1 | kb-sonnet | 190k -> 20,217 (-89%) | $0.161 -> $0.026 (-84%) | 9 s -> 2 s (-74%) | - | 1/1 |
| s1 | bare-opus | 185k -> 21,105 (-89%) | $0.316 -> $0.084 (-73%) | 14 s -> 6 s (-57%) | - | 1/1 |
| s1 | kb-opus | 79k -> 18,641 (-76%) | $0.142 -> $0.050 (-65%) | 8 s -> 6 s (-29%) | - | 1/1 |
| h1 | bare-haiku | 197k -> 68,491 (-65%) | $0.064 -> $0.042 (-34%) | 24 s -> 9 s (-62%) | - | 3/3 |
| h1 | kb-haiku | 87k -> 27,042 (-69%) | $0.030 -> $0.021 (-30%) | 15 s -> 6 s (-62%) | - | 3/3 |
| h1 | bare-sonnet | 301k -> 38,012 (-87%) | $0.187 -> $0.095 (-49%) | 16 s -> 18 s (+11%) | - | 3/3 |
| h1 | kb-sonnet | 241k -> 78,757 (-67%) | $0.122 -> $0.093 (-24%) | 12 s -> 19 s (+59%) | - | 3/3 |
| h1 | bare-opus | 237k -> 107,941 (-54%) | $0.291 -> $0.293 (+1%) | 38 s -> 19 s (-50%) | - | 3/3 |
| h1 | kb-opus | 122k -> 31,081 (-75%) | $0.172 -> $0.093 (-46%) | 16 s -> 12 s (-23%) | - | 3/3 |
| x1 | bare-haiku | 383k -> 169,091 (-56%) | $0.146 -> $0.103 (-29%) | 54 s -> 40 s (-26%) | - | 3/3 |
| x1 | kb-haiku | 91k -> 30,939 (-66%) | $0.034 -> $0.028 (-18%) | 16 s -> 11 s (-32%) | - | 3/3 |
| x1 | bare-sonnet | 225k -> 29,440 (-87%) | $0.190 -> $0.076 (-60%) | 28 s -> 18 s (-35%) | - | 2/3 |
| x1 | kb-sonnet | 191k -> 19,997 (-90%) | $0.111 -> $0.046 (-58%) | 11 s -> 10 s (-8%) | - | 2/3 |
| x1 | bare-opus | 381k -> 253,776 (-33%) | $0.378 -> $0.399 (+6%) | 47 s -> 57 s (+21%) | - | 3/3 |
| x1 | kb-opus | 184k -> 20,522 (-89%) | $0.238 -> $0.100 (-58%) | 25 s -> 8 s (-66%) | - | 3/3 |
| o1 | bare-haiku | 254k -> 22,712 (-91%) | $0.070 -> $0.041 (-42%) | 42 s -> 22 s (-48%) | - | 2/2 |
| o1 | kb-haiku | 287k -> 63,066 (-78%) | $0.065 -> $0.053 (-18%) | 37 s -> 32 s (-13%) | - | 2/2 |
| o1 | bare-sonnet | 238k -> 5,749 (-98%) | $0.140 -> $0.016 (-88%) | 35 s -> 0 s (-100%) | - | 1/2 |
| o1 | kb-sonnet | 87k -> 18,732 (-78%) | $0.079 -> $0.025 (-69%) | 13 s -> 5 s (-62%) | - | 1/2 |
| o1 | bare-opus | 137k -> 42,081 (-69%) | $0.218 -> $0.185 (-15%) | 32 s -> 43 s (+35%) | - | 2/2 |
| o1 | kb-opus | 218k -> 51,774 (-76%) | $0.229 -> $0.169 (-26%) | 26 s -> 27 s (+5%) | - | 2/2 |
| total (4 scenarios) | bare (all models) | - | - | - | 11/12 | - |
| total (4 scenarios) | kb (all models) | - | - | - | 12/12 | - |
<!-- /bench -->

What it shows:
- **Within the re-run, the kb arm cost less than the bare arm on every model:** $0.117 against $0.211 on Haiku (-45%), $0.189 against $0.228 on Sonnet (-17%), $0.412 against $0.962 on Opus (-57%), for the four questions (estimated at list price). The gap is widest on the synthesis (`x1`): bare Opus read 254k tokens for $0.399, kb Opus 21k for $0.100.
- Right answers: Haiku and Opus 4/4 in both arms, Sonnet 2/4 in both (one check missed on `x1` and one on `o1`, in each arm).
- The records do not compare with each other: the agents now carry only their own tools, so each starts at a few thousand tokens where the history's general-purpose agents started at 25-50k.

### Router against web search

**Setup:** the rows of `python3 _tools/benchmarks.py run headless`: the router and the web arms on the questions the kb covers (the history used 5 of them, the re-run all 7), and on the Purview false `good` (`s8_falsegood2`).

<!-- bench:records router-web -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 6f4b998 | 2026-09-26 | 6f4b998 | 2.1.283 | 259 | 2 | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 1 | $3.55 |
<!-- /bench -->

<!-- bench:table router-web metrics=cost,wall_s,input,correct -->
| case | arm | cost | wall_s | input | correct |
|---|---|---|---|---|---|
| covered | router | $0.011 -> $0.033 (+196%) | 8.9 s -> 10 s (+13%) | 10.4k -> 13,690 (+32%) | 10/10 -> 5/7 |
| covered | web-sonnet | $0.128 -> $0.192 (+50%) | 26.9 s -> 74 s (+175%) | 98k -> 187,958 (+92%) | 10/10 -> 6/7 |
| covered | web-opus | $0.228 -> $0.204 (-11%) | 26.7 s -> 31 s (+16%) | 103k -> 93,372 (-9%) | 10/10 -> 7/7 |
| covered | web-haiku | $0.025 -> $0.012 (-54%) | 11.9 s -> 11 s (-5%) | 43k -> 21,782 (-49%) | 8/10 -> 5/7 |
| not covered (false good) | router | $0.118 -> $0.053 (-55%) | 23.2 s -> 17 s (-28%) | 89k -> 34,914 (-61%) | 2/2 -> 0/1 |
| not covered (false good) | web-sonnet | $0.153 -> $0.134 (-13%) | 29.3 s -> 35 s (+20%) | 82k -> 108,313 (+32%) | 2/2 -> 0/1 |
| not covered (false good) | web-haiku | $0.009 | 12 s | 16,685 | 0/1 |
| not covered (false good) | web-opus | $0.270 | 33 s | 97,689 | 0/1 |
<!-- /bench -->

What it shows: on the covered questions the router cost $0.033 and 10 s against $0.192 and 74 s for Sonnet web search and $0.204 and 31 s for Opus, at 7-15% of their input; it was right on 5 of 7 (the `h2_applock` false `none`, and `x1_synth`'s TGT step missing as in the history), web Opus on 7 of 7. On the Purview false `good` the router escalated to Sonnet with the docs servers and stopped at "the kb does not cover this" ($0.053), where the history's escalation answered from live docs ($0.118).

## Models and routing

### Models and hand-off patterns

**Setup:** `python3 _tools/benchmarks.py run models`: `agent_bench.py` configs `haiku`, `sonnet`, `opus` on s1-s7, `opus+delegate` (Opus told to hand the lookup to the Haiku `kb-lookup` agent) on s1, s3, s4, s6, s7, and `haiku+escalate` (Haiku told to hand live-docs work to a Sonnet agent) on s6 and s7. s5 is off-domain (EKS autoscaler), s6 a false `good` (the GPO Central Store), s7 not in the kb then (KRBTGT reset). The history's cells are each prompt's first run.

<!-- bench:records models -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 3dcb873 | 2026-09-26 | 3dcb873 | 2.1.283 | 259 | 1 | - |
| 2026-09-28 | 2026-09-28 | 654c8ad | 2.1.283 | 271 | 1 | $4.01 |
<!-- /bench -->

<!-- bench:table models metrics=cost,wall_s,checks,tool_calls -->
| case | arm | cost | wall_s | checks | tool_calls |
|---|---|---|---|---|---|
| s1_fact | haiku | $0.031 -> $0.036 (+17%) | 9 s -> 10 s (+6%) | 1/1 | 1 |
| s1_fact | sonnet | $0.143 -> $0.193 (+35%) | 7 s -> 11 s (+61%) | 1/1 | 1 |
| s1_fact | opus | $0.286 -> $0.286 (+0%) | 12 s -> 9 s (-25%) | 1/1 | 1 |
| s1_fact | opus+delegate | $0.204 -> $0.233 (+14%) | 25 s -> 36 s (+46%) | 1/1 | 3 |
| s2_fact_csv | haiku | $0.030 -> $0.027 (-9%) | 14 s -> 9 s (-36%) | 1/1 | 1 |
| s2_fact_csv | sonnet | $0.094 -> $0.096 (+2%) | 12 s -> 7 s (-39%) | 1/1 | 1 |
| s2_fact_csv | opus | $0.184 -> $0.181 (-1%) | 10 s -> 15 s (+46%) | 1/1 | 1 |
| s3_multi | haiku | $0.036 -> $0.033 (-9%) | 10 s -> 11 s (+11%) | 3/3 | 1 |
| s3_multi | sonnet | $0.112 -> $0.108 (-4%) | 12 s -> 11 s (-12%) | 3/3 | 1 |
| s3_multi | opus | $0.231 -> $0.210 (-9%) | 16 s -> 12 s (-25%) | 3/3 | 1 |
| s3_multi | opus+delegate | $0.219 -> $0.262 (+20%) | 33 s -> 39 s (+17%) | 3/3 | 3 |
| s4_count | haiku | $0.030 -> $0.068 (+128%) | 14 s -> 32 s (+130%) | 2/2 | 9 |
| s4_count | sonnet | $0.087 -> $0.175 (+101%) | 7 s -> 33 s (+370%) | 2/2 | 3 |
| s4_count | opus | $0.183 -> $0.203 (+11%) | 12 s -> 27 s (+122%) | 2/2 | 3 |
| s4_count | opus+delegate | $0.213 -> $0.201 (-5%) | 31 s -> 44 s (+41%) | 2/2 | 1 |
| s5_none | haiku | $0.024-0.029 -> $0.027 (+3%) | 9-12 s -> 12 s (+11%) | 1/1 | 1 |
| s5_none | sonnet | $0.087 -> $0.093 (+7%) | 8 s -> 13 s (+65%) | 1/1 | 1 |
| s5_none | opus | $0.184 -> $0.177 (-4%) | 15 s -> 12 s (-22%) | 1/1 | 1 |
| s6_falsegood | haiku | $0.034-0.051 -> $0.030 (-28%) | 21-24 s -> 14 s (-39%) | 1/2 | 1 |
| s6_falsegood | sonnet | $0.199-0.247 -> $0.138 (-38%) | 19-21 s -> 22 s (+11%) | 2/2 | 2 |
| s6_falsegood | opus | $0.290 -> $0.256 (-12%) | 31 s -> 28 s (-10%) | 2/2 | 2 |
| s6_falsegood | opus+delegate | $0.365 -> $0.243 (-33%) | 80 s -> 62 s (-22%) | 2/2 | 1 |
| s7_web | haiku | $0.047-0.053 -> $0.029 (-42%) | 16-17 s -> 12 s (-24%) | 2/2 | 1 |
| s7_web | sonnet | $0.139-0.153 -> $0.099 (-32%) | 16-20 s -> 11 s (-41%) | 2/2 | 1 |
| s7_web | opus | $0.272 -> $0.234 (-14%) | 23 s -> 30 s (+32%) | 2/2 | 2 |
| s7_web | opus+delegate | $0.313 -> $0.249 (-20%) | 48 s -> 43 s (-10%) | 2/2 | 3 |
| s6_falsegood | haiku+escalate | $0.095 | 25 s | 2/2 | 6 |
| s7_web | haiku+escalate | $0.030 | 12 s | 0/2 | 1 |
<!-- /bench -->

What it shows:
- The single-model costs match the history within its spread: Haiku $0.027-0.068 per question, Sonnet $0.093-0.193, Opus $0.177-0.286. `s4_count` got slower and dearer on every model (Haiku 9 tool calls, $0.068): with no partial Intune article left, the models checked the empty answer several ways before reporting 0.
- **Handing the lookup to the Haiku `kb-lookup` agent still saves nothing:** Opus + agent cost $0.201-0.262 against Opus alone $0.203-0.286, and took 36-62 s against 9-30 s.
- **A model told to route still does not route reliably:** Haiku told to hand live-docs work to a Sonnet agent did so on `s6_falsegood` ($0.095, 6 tool calls, 2/2) and not on `s7_web` ($0.030, 0/2).

### Routing by verdict

**Setup:** `python3 _tools/benchmarks.py run router`: `kb_ask.py`'s routing on eight questions, a first run and a repeat (counts and "who cites" by the tools; parts split; `good` to a tool-less Haiku reader that answers `INSUFFICIENT` when the facts are only related; `weak`/`none` to Sonnet at low effort with only the kb and docs servers). Then the reader's start context in three forms: with the user's plugins and servers, without them (`--setting-sources project,local --strict-mcp-config`), and without tools too (`--tools ""`), 2 runs each (the highest shown).

<!-- bench:records router -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 3dcb873 | 2026-09-26 | 3dcb873 | 2.1.283 | 259 | - | - |
| 46aa6ae | 2026-09-26 | 46aa6ae | 2.1.283 | 259 | - | - |
| 2026-09-28 | 2026-09-28 | 654c8ad | 2.1.283 | 271 | 1 | $0.30 |
<!-- /bench -->

<!-- bench:table router metrics=cost,wall_s,checks,start_ctx,measured -->
| case | arm | cost | wall_s | checks | start_ctx | measured |
|---|---|---|---|---|---|---|
| claude -p without user plugins and MCP servers (--setting-sources project,local --strict-mcp-config) | router | - | - | - | - | start context 29.9k -> 24.8k; first run $0.027 -> $0.018 |
| no tools for the reader (--tools "") | router | - | - | - | - | start context 24.8k -> 9.8k; repeat $0.0054 -> $0.0027 |
| sufficiency check (INSUFFICIENT, escalate) | router | - | - | - | - | a Purview endpoint DLP false good escalated to Sonnet and was answered from live docs, labelled; $0.115-0.121 |
| counts and "who cites S123" by audit / cited_lines | router | - | - | - | - | $0, 0.5 s (was $0.098 on Sonnet) |
| parts split (numbered items or several ? questions) | router | - | - | - | - | three parts stay on Haiku: $0.013 (was $0.121 on Sonnet) |
| Sonnet at low effort with only the kb and docs servers | router | - | - | - | - | off-domain $0.044-0.046 (was $0.084); escalated research $0.115-0.121 (Sonnet alone: $0.199-0.247) |
| request words as stop words ("answer from the kb with citation") | router | - | - | - | - | a covered question stays good on Haiku instead of weak on Sonnet |
| s1_fact | router first run | $0.0095 -> $0.022 (+137%) | 6 s | 1/1 | - | - |
| s1_fact | router repeat | $0.0039 -> $0.003 (-15%) | 6 s | 1/1 | - | - |
| s2_fact_csv | router first run | $0.0085 -> $0.008 (-9%) | 5 s | 1/1 | - | - |
| s2_fact_csv | router repeat | $0.0056 -> $0.003 (-46%) | 6 s | 1/1 | - | - |
| s3_multi | router first run | $0.0135 -> $0.015 (+12%) | 10 s | 3/3 | - | - |
| s3_multi | router repeat | $0.0130 -> $0.005 (-62%) | 9 s | 3/3 | - | - |
| s4_count | router first run | $0 -> $0.000 | 1 s | 2/2 | - | - |
| s4_count | router repeat | $0 -> $0.000 | 1 s | 2/2 | - | - |
| s5_none | router first run | $0.044 -> $0.071 (+60%) | 7 s | 1/1 | - | - |
| s5_none | router repeat | $0.046 -> $0.011 (-77%) | 8 s | 1/1 | - | - |
| s6_falsegood | router first run | $0.014 -> $0.011 (-24%) | 10 s | 2/2 | - | - |
| s6_falsegood | router repeat | $0.015 -> $0.005 (-66%) | 10 s | 1/2 | - | - |
| s7_web | router first run | $0.013 -> $0.012 (-10%) | 11 s | 2/2 | - | - |
| s7_web | router repeat | $0.014 -> $0.004 (-69%) | 11 s | 2/2 | - | - |
| s8_falsegood2 | router first run | $0.121 -> $0.051 (-57%) | 10 s | 2/2 | - | - |
| s8_falsegood2 | router repeat | $0.115 -> $0.009 (-92%) | 9 s | 1/2 | - | - |
| start context | user plugins and servers | $0.011 | - | - | 29.9k -> 27,198 (-9%) | - |
| start context | lean | $0.012 | - | - | 24.8k -> 23,606 (-5%) | - |
| start context | lean, no tools | $0.009 | - | - | 9.8k -> 8,267 (-16%) | - |
<!-- /bench -->

What it shows:
- The router's repeats cost $0.003-0.011 per question and its first runs $0.008-0.071; counts cost nothing (`s4_count` by the tools, 1 s). The false `good` (`s8_falsegood2`) now takes the `weak` route to Sonnet ($0.051 first run) instead of the reader's escalation ($0.121).
- The reader's start context is 27.2k with the user's plugins and servers, 23.6k without them and 8.3k without tools, against 29.9k, 24.8k and 9.8k in the history: the lean `claude -p` still takes two thirds off.
- Checks: 1/2 on the repeats of `s6_falsegood` and `s8_falsegood2`, where the history passed every check.

### Routing by verdict against the bare agent

**Setup:** `python3 _tools/benchmarks.py run route-by-verdict`: `kb_ask.py`'s routing (`agent_bench.py` config `router-pinned`, which follows `kb_ask.plan`: a good pack to a tool-less reader (Haiku 4.5 in this record; `router-pinned` has pinned the reader to Haiku 5.5 since), a web pack to a Sonnet 5.5 researcher (in this record: the docs servers called directly, not through the kb server; the researcher now reads live docs through the kb server's cached `docs_search` and `docs_fetch`), a split pack to the reader and the researcher with their costs summed) against the bare Sonnet 5.5 web arm (`web-sonnet-5-5`: WebSearch and WebFetch, no kb) and the kb Sonnet 5.5 arm (`sonnet-5-5`: the kb and docs servers, following the server instructions), all three pinned by full model name in one batch so that dollars compare. Six questions: `s5_none` and `o1_offkb` (off the kb), `s8_falsegood2` (the Purview false `good`), `h2_applock` (the pack's false `none`), `s1_fact` and `s3_multi` (facts the kb has). Each arm's question is the same; the web arm gets it without "Answer from the kb" and with "Cite the source urls" (`agent_bench.WEB_Q`).

The case of a question is the route its pack takes on the run's commit (`pack_route`: `web`, `split` or `good`), not a fixed label. The operator's bar, judged per case on each arm's mean cost (`bar`, with `limit_ratio`, the router's cost over its limit):
- `web`: the router costs at most 110% of the bare web arm (`limit_ratio` at most 1);
- `split`: it costs less than both other arms (`limit_ratio` under 1, over the cheaper of the two);
- `good`: it stays on the reader route, with no escalation to the researcher.

A miss is a finding for the sprint review, not a reason to change the bar.

<!-- bench:records route-by-verdict -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-29 | 2026-09-29 | 15fb0d9 | 2.1.284 | 288 | 2 | $3.73 |
<!-- /bench -->

<!-- bench:table route-by-verdict metrics=pack_route,cost,wall_s,checks,limit_ratio,bar -->
| case | arm | pack_route | cost | wall_s | checks | limit_ratio | bar |
|---|---|---|---|---|---|---|---|
| s5_none | router-pinned | web | $0.119 | 36 s | 2/2 | 0.87x | holds |
| o1_offkb | router-pinned | web | $0.110 | 34 s | 4/4 | 0.89x | holds |
| s8_falsegood2 | router-pinned | web | $0.100 | 25 s | 4/4 | 0.71x | holds |
| h2_applock | router-pinned | split | $0.055 | 20 s | 6/6 | 0.92x | holds |
| s1_fact | router-pinned | good | $0.013 | 6 s | 2/2 | - | holds |
| s3_multi | router-pinned | good | $0.011 | 10 s | 6/6 | - | holds |
| s5_none | web-sonnet-5-5 | - | $0.124 | 26 s | 0/2 | - | - |
| o1_offkb | web-sonnet-5-5 | - | $0.112 | 23 s | 4/4 | - | - |
| s8_falsegood2 | web-sonnet-5-5 | - | $0.128 | 22 s | 2/4 | - | - |
| h2_applock | web-sonnet-5-5 | - | $0.060 | 14 s | 6/6 | - | - |
| s1_fact | web-sonnet-5-5 | - | $0.053 | 9 s | 2/2 | - | - |
| s3_multi | web-sonnet-5-5 | - | $0.299 | 48 s | 6/6 | - | - |
| s5_none | sonnet-5-5 | - | $0.186 | 30 s | 2/2 | - | - |
| o1_offkb | sonnet-5-5 | - | $0.121 | 26 s | 4/4 | - | - |
| s8_falsegood2 | sonnet-5-5 | - | $0.111 | 21 s | 4/4 | - | - |
| h2_applock | sonnet-5-5 | - | $0.096 | 14 s | 6/6 | - | - |
| s1_fact | sonnet-5-5 | - | $0.097 | 10 s | 2/2 | - | - |
| s3_multi | sonnet-5-5 | - | $0.072 | 12 s | 6/6 | - | - |
<!-- /bench -->

Model runs of the arms, per case and arm; `route` of each arm is in `benchmarks.csv`.

**Conclusions (record 2026-09-29, 2 runs per cell).** The bar holds in all six cases. On the three uncovered questions (`web`) the router cost 0.78-0.98 of the bare web arm (`limit_ratio` 0.71-0.89 against the 110% limit) and passed every check, while the bare arm missed both checks of `s5_none` and half of `s8_falsegood2`: handing the researcher what the kb lacks, with the nearest articles as leads, made the web answer both cheaper and more often right. The Purview false `good` (`s8_falsegood2`) now packs `none` and routes `web`. On the near miss (`h2_applock`, `split`) the router cost $0.055 against $0.060 (web) and $0.096 (kb Sonnet), with every check passed. The two covered questions stayed on the reader, at $0.011-0.013 against $0.053-0.299 for the Sonnet arms. The kb Sonnet arm passed every check too, at a higher cost than the router on all six questions.

### How-to questions and SNIPPET units

**Setup:** `python3 _tools/benchmarks.py run howto`: h1 (gMSA, PowerShell), h2 (`sp_getapplock`, T-SQL) and h3 (Graph PowerShell app-only) on Haiku and Sonnet, one run each; `h1-h3` is the three questions' total. The history's `unchecked blocks` arm ran the kb before its code blocks became `SNIPPET:` units.

<!-- bench:records howto -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 5088c5a | 2026-09-27 | 5088c5a | 2.1.283 | 265 | 1 | - |
| 2026-09-28 | 2026-09-28 | 654c8ad | 2.1.283 | 271 | 1 | $0.50 |
<!-- /bench -->

<!-- bench:table howto metrics=cost,checks,wall_s -->
| case | arm | cost | checks | wall_s |
|---|---|---|---|---|
| h1-h3 | haiku, unchecked blocks | $0.168 | 8/9 (h2 missed `@LockTimeout = 0` and `sp_releaseapplock`) | - |
| h1-h3 | haiku | $0.126 -> $0.127 (+1%) | 9/9 -> 9/9 | - |
| h1-h3 | sonnet, unchecked blocks | $0.427 | 9/9 | - |
| h1-h3 | sonnet | $0.352 -> $0.371 (+5%) | 9/9 -> 9/9 | - |
| h1_gmsa | haiku | $0.044 | 3/3 | 17 s |
| h2_applock | haiku | $0.036 | 3/3 | 14 s |
| h3_mggraph | haiku | $0.047 | 3/3 | 22 s |
| h1_gmsa | sonnet | $0.140 | 3/3 | 16 s |
| h2_applock | sonnet | $0.113 | 3/3 | 15 s |
| h3_mggraph | sonnet | $0.117 | 3/3 | 15 s |
<!-- /bench -->

What it shows: with `SNIPPET:` units both models passed 9/9 again, Haiku at $0.127 and Sonnet at $0.371 for the three questions ($0.126 and $0.352 in the history). Here `h2_applock` passed on both models, unlike the headless run of the same question with Sonnet: the pack is `none` (see the headless section), and whether a model answers from it anyway varies by run.

### Partial knowledge, newer versions and stale copies

**Setup:** `python3 _tools/benchmarks.py run partial`: `agent_bench.py`'s host scenarios, one `claude -p` per run in an empty directory under the clone with the kb and docs plugins loaded by `--plugin-dir`, `--setting-sources project,local`, claude.ai connectors off; p1/p2 partial knowledge, n1/n2 a copy planted with an older presidio release ("using the kb"), n3/n4 the same with leave to use the web, k1 a copy 3 commits behind its remote. Scored from the stream: the urls a kb tool returned, the urls fetched, searches, tools called, regexes over the answer. The history's `before the fixes` arms ran the commit before the `freshness:` and `kb copy:` lines.

<!-- bench:records partial -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 464ae5f | 2026-09-28 | 464ae5f | 2.1.283 | 266 | 2 | - |
| 85bf6c8 | 2026-09-28 | 85bf6c8 | 2.1.283 | 266 | 2 | - |
| 2026-09-28 | 2026-09-28 | 654c8ad | 2.1.283 | 271 | 1 | $1.79 |
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 1 | $0.79 |
<!-- /bench -->

<!-- bench:table partial metrics=cost,input,checks,searches,fetched,live checks,outcome -->
| case | arm | cost | input | checks | searches | fetched | live checks | outcome |
|---|---|---|---|---|---|---|---|---|
| p1_partial | haiku | $0.047, $0.037 -> $0.107 -> $0.023 (-78%) | 82k, 111k -> 166,287 -> 287,861 (+73%) | 4/4, 4/4 -> 4/4 -> 4/4 | 1, 1 -> 2 -> 2 (+0%) | 0, 0 -> 0 -> 3 | - | - |
| p1_partial | sonnet | $0.215, $0.110 -> $0.370 -> $0.169 (-54%) | 178k, 146k -> 441,925 -> 197,523 (-55%) | 4/4, 4/4 -> 4/4 -> 4/4 | 1, 1 -> 4 -> 2 (-50%) | 0, 0 -> 3 -> 0 (-100%) | - | - |
| p2_partial | haiku | $0.024, $0.071 -> $0.052 -> $0.019 (-63%) | 50k, 129k -> 115,598 -> 203,577 (+76%) | 3/4 (no search), 3/4 (answer wrong) -> 3/4 -> 4/4 | 0, 1 -> 0 -> 3 | 0, 1 (0) -> 2 -> 1 (-50%) | - | - |
| p2_partial | sonnet | $0.158, $0.106 -> $0.191 -> $0.117 (-39%) | 193k, 139k -> 330,934 -> 166,161 (-50%) | 4/4, 4/4 -> 3/4 -> 4/4 | 2, 1 -> 4 -> 2 (-50%) | 0, 0 -> 0 -> 0 | - | - |
| n1_newer | haiku, before the fixes | $0.020, $0.020 | 49k, 48k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n1_newer | sonnet, before the fixes | $0.065, $0.063 | 96k, 96k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n2_newer | haiku, before the fixes | $0.019, $0.026 | 47k, 95k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n2_newer | sonnet, before the fixes | $0.044, $0.026 | 63k, 95k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| k1_stale | haiku, before the fixes | $0.028, $0.026 | 74k, 96k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| k1_stale | sonnet, before the fixes | $0.061, $0.031 | 98k, 97k | 2/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n1_newer | haiku | $0.010, $0.010 -> $0.023 -> $0.010 (-59%) | 51,866 -> 79,552 (+53%) | 1/3, 1/3 -> 1/3 -> 3/3 | 0 -> 0 | 0 -> 1 | 0, 0 | - |
| n1_newer | sonnet | $0.024, $0.032 -> $0.070 -> $0.059 (-16%) | 105,743 -> 50,665 (-52%) | 1/3, 1/3 -> 1/3 -> 1/3 | 0 -> 0 | 0 -> 0 | 0, 0 | - |
| n2_newer | haiku | $0.019, $0.020 -> $0.025 -> $0.009 (-63%) | 75,848 -> 132,168 (+74%) | 1/3, 1/3 -> 0/3 -> 2/3 | 0 -> 0 | 0 -> 3 | 0, 0 | - |
| n2_newer | sonnet | $0.018, $0.051 -> $0.063 -> $0.080 (+27%) | 103,994 -> 151,931 (+46%) | 1/3, 1/3 -> 1/3 -> 2/3 | 0 -> 0 | 0 -> 3 | 0, 0 | - |
| k1_stale | haiku | $0.015, $0.014 -> $0.054 -> $0.004 (-93%) | 27,029 -> 53,101 (+96%) | 2/3, 2/3 -> 2/3 -> 3/3 | 0 -> 0 | 0 -> 0 | - | - |
| k1_stale | sonnet | $0.059, $0.025 -> $0.091 -> $0.066 (-27%) | 176,528 -> 75,173 (-57%) | 2/3, 2/3 -> 2/3 -> 2/3 | 0 -> 0 | 0 -> 0 | - | - |
| n3_newer | haiku, before the fixes | $0.027 | - | - | - | - | - | no live check, 2.2.361 as the latest, $0.027 |
| n3_newer | haiku | $0.089 -> $0.083 -> $0.011 (-87%) | 132,553 -> 109,981 (-17%) | 3/3 -> 3/3 | 0 -> 0 | 1 -> 1 (+0%) | - | PyPI fetched, 2.2.364 of 2026-07-22 with the kb's 2.2.361 beside it, $0.089 |
| n3_newer | sonnet, before the fixes | $0.158 | - | - | - | - | - | PyPI fetched, 2.2.364, $0.158 |
| n3_newer | sonnet | $0.141 -> $0.085 (-40%) | 131,556 | 3/3 | 0 | 1 | - | the same, $0.141 |
| n4_newer | haiku, before the fixes | $0.050 | - | - | - | - | - | searched, then "Yes" from a search summary (wrong), $0.050 |
| n4_newer | haiku | $0.122 -> $0.174 -> $0.025 (-86%) | 222,145 -> 175,158 (-21%) | 2/3 -> 2/3 | 2 -> 1 (-50%) | 4 -> 4 (+0%) | - | "No", from the tag's tree, $0.122 |
| n4_newer | sonnet, before the fixes | $0.117 | - | - | - | - | - | searched, then "Yes" from the kb's line on `main` read as a release (wrong), $0.117 |
| n4_newer | sonnet | $0.240 -> $0.489 -> $0.112 (-77%) | 572,315 -> 184,384 (-68%) | 2/3 -> 2/3 | 1 -> 1 (+0%) | 11 -> 4 (-64%) | - | "No", after 6 fetches, $0.240 |
<!-- /bench -->

What it shows (the record of 2026-10-12, Claude Code 2.1.296, 359 kb topics, one run per cell):
- **Partial knowledge still works:** p1 and p2 passed 4/4 on both models (p2 3/4 on both in the record of 2026-09-28). The runs cost $0.019-$0.169, below the earlier record's $0.052-$0.370; Haiku fetched 3 urls on p1 and 1 on p2, Sonnet none.
- **The freshness and stale-copy lines still reach the answer:** k1 3/3 on Haiku, which called `kb_status`, and 2/3 on Sonnet, which did not. The n1/n2 "using the kb" arms no longer stay inside the kb: Haiku fetched 1 url on n1 (3/3) and 3 on n2 (2/3), Sonnet none on n1 (1/3) and 3 on n2 (2/3), where the record of 2026-09-28 made no fetch (1/3 on both).
- **With leave to use the web** both models checked PyPI on n3 (3/3, Haiku $0.011, Sonnet $0.085) and answered "no" on n4 (2/3), after 4 fetches and 1 search ($0.025 and $0.112), where Sonnet's n4 took 11 fetches in the record of 2026-09-28. Sonnet's n3 has a row now (its run of 2026-09-28 failed with `529 Overloaded`).

### A new model against the one it replaces
**Setup:** `python3 _tools/benchmarks.py run new-model`: the new model and the one it replaces, pinned by id (`agent_bench.py` configs `sonnet-5-5` and `sonnet-5`, since the `sonnet` alias follows the newest), in one batch so that dollars compare. A curated set from the sections above: the kb arm on ten questions (`s1_fact`, `s3_multi` facts; `s5_none`, `o1_offkb` off the kb; `s6_falsegood`, `s8_falsegood2` false `good`s that need live docs; `h1`-`h3` how-to snippets, `h2_applock` the pack's false `none`; `x1_synth` a cross-topic synthesis), 2 runs each; the bare web arm on `s1_fact`, `x1_synth` and `o1_offkb`; the host scenarios `p1_partial`, `n1_newer` and `k1_stale`; and "Reply with the single word ok." in an empty directory and in the clone (2 runs each, the highest shown). `kb (10)` and `host (3)` are means per question over those cases.
<!-- bench:records new-model -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | bb6e13e | 2.1.284 | 277 | 2 | $6.62 |
<!-- /bench -->
<!-- bench:table new-model metrics=cost,wall_s,input,out,tool_calls,checks,fully_right cases=kb (10),host (3) -->
| case | arm | cost | wall_s | input | out | tool_calls | checks | fully_right |
|---|---|---|---|---|---|---|---|---|
| kb (10) | sonnet-5-5 | $0.108 | 16 s | 90,140 | 1,161 | 1.9 | 46/46 | 20 of 20 |
| host (3) | sonnet-5-5 | $0.127 | 14 s | 127,096 | 1,018 | 5 | 8/10 | 2 of 3 |
| kb (10) | sonnet-5 | $0.106 | 15 s | 111,844 | 703 | 1.5 | 44/46 | 18 of 20 |
| host (3) | sonnet-5 | $0.172 | 26 s | 244,344 | 1,386 | 7.3 | 6/10 | 1 of 3 |
<!-- /bench -->
Per question:
<!-- bench:table new-model metrics=cost,wall_s,input,out,tool_calls,checks cases=s1_fact,s3_multi,s5_none,s6_falsegood,s8_falsegood2,h1_gmsa,h2_applock,h3_mggraph,x1_synth,o1_offkb,p1_partial,n1_newer,k1_stale -->
| case | arm | cost | wall_s | input | out | tool_calls | checks |
|---|---|---|---|---|---|---|---|
| s1_fact | sonnet-5-5 | $0.100 | 11 s | 62,678 | 424 | 1 | 2/2 |
| s3_multi | sonnet-5-5 | $0.107 | 11 s | 65,906 | 692 | 1 | 6/6 |
| s5_none | sonnet-5-5 | $0.052 | 8 s | 62,667 | 320 | 1 | 2/2 |
| s6_falsegood | sonnet-5-5 | $0.098 | 18 s | 101,354 | 1,709 | 2 | 4/4 |
| s8_falsegood2 | sonnet-5-5 | $0.165 | 23 s | 142,712 | 1,596 | 3 | 4/4 |
| h1_gmsa | sonnet-5-5 | $0.098 | 14 s | 63,294 | 1,014 | 1 | 6/6 |
| h2_applock | sonnet-5-5 | $0.075 | 14 s | 96,367 | 1,036 | 2.5 | 6/6 |
| h3_mggraph | sonnet-5-5 | $0.080 | 14 s | 98,376 | 1,383 | 2 | 6/6 |
| x1_synth | sonnet-5-5 | $0.119 | 17 s | 67,428 | 1,253 | 1 | 6/6 |
| o1_offkb | sonnet-5-5 | $0.186 | 33 s | 140,618 | 2,182 | 4 | 4/4 |
| s1_fact | sonnet-5 | $0.148 | 9 s | 88,208 | 174 | 1 | 2/2 |
| s3_multi | sonnet-5 | $0.110 | 9 s | 91,264 | 276 | 1 | 6/6 |
| s5_none | sonnet-5 | $0.059 | 10 s | 87,546 | 294 | 1 | 2/2 |
| s6_falsegood | sonnet-5 | $0.087 | 21 s | 113,452 | 1,448 | 1.5 | 4/4 |
| s8_falsegood2 | sonnet-5 | $0.096 | 12 s | 87,484 | 283 | 1 | 2/4 |
| h1_gmsa | sonnet-5 | $0.114 | 15 s | 113,038 | 802 | 1.5 | 6/6 |
| h2_applock | sonnet-5 | $0.114 | 16 s | 133,308 | 698 | 2 | 6/6 |
| h3_mggraph | sonnet-5 | $0.079 | 16 s | 134,192 | 730 | 2 | 6/6 |
| x1_synth | sonnet-5 | $0.125 | 15 s | 136,925 | 876 | 2 | 6/6 |
| o1_offkb | sonnet-5 | $0.130 | 25 s | 133,024 | 1,444 | 2 | 4/4 |
| s1_fact | web-sonnet-5-5 | $0.061 | 9 s | 55,799 | 523 | 2 | 1/1 |
| x1_synth | web-sonnet-5-5 | $0.201 | 32 s | 109,571 | 2,764 | 9 | 3/3 |
| o1_offkb | web-sonnet-5-5 | $0.132 | 24 s | 66,467 | 2,682 | 4 | 2/2 |
| s1_fact | web-sonnet-5 | $0.075 | 10 s | 69,717 | 426 | 2 | 1/1 |
| x1_synth | web-sonnet-5 | $0.371 | 89 s | 297,405 | 6,242 | 13 | 3/3 |
| o1_offkb | web-sonnet-5 | $0.169 | 43 s | 101,452 | 2,686 | 6 | 2/2 |
| p1_partial | sonnet-5-5 | $0.251 | 22 s | 241,493 | 1,809 | 9 | 4/4 |
| n1_newer | sonnet-5-5 | $0.064 | 7 s | 69,762 | 475 | 2 | 1/3 |
| k1_stale | sonnet-5-5 | $0.067 | 12 s | 70,033 | 769 | 4 | 3/3 |
| p1_partial | sonnet-5 | $0.373 | 59 s | 486,797 | 3,203 | 17 | 4/4 |
| n1_newer | sonnet-5 | $0.063 | 11 s | 104,666 | 343 | 2 | 0/3 |
| k1_stale | sonnet-5 | $0.079 | 9 s | 141,569 | 611 | 3 | 2/3 |
<!-- /bench -->
Fixed context:
<!-- bench:table new-model metrics=start_ctx,out,cost cases=ok in an empty directory,ok in the clone -->
| case | arm | start_ctx | out | cost |
|---|---|---|---|---|
| ok in an empty directory | sonnet-5-5 | 24,574 | 4 | $0.053 |
| ok in the clone | sonnet-5-5 | 31,012 | 4 | $0.076 |
| ok in an empty directory | sonnet-5 | 37,187 | 4 | $0.042 |
| ok in the clone | sonnet-5 | 43,625 | 4 | $0.045 |
<!-- /bench -->

What it shows (Sonnet 5.5 against Sonnet 5, Claude Code 2.1.284):
- **Same cost, more right, on the kb questions:** $0.108 and 16 s per question against $0.106 and 15 s, all 20 runs fully right against 18 of 20. The two misses were Sonnet 5 on the Purview false `good` (`s8_falsegood2`): it stopped at the pack on both runs (1 tool call, 2/4), where Sonnet 5.5 went on to the live docs (3 tool calls, 4/4, $0.165 against $0.096). `h2_applock`'s false `none` passed on both models.
- **Less input, more output:** 90k input per kb question against 112k (-19%), and 1,161 output tokens against 703 (+65%); 1.9 tool calls against 1.5. The same per-token price ($2 / $10) turns that into the same dollars.
- **A smaller fixed context:** "ok" starts at 24.6k tokens in an empty directory and 31.0k in the clone, against 37.2k and 43.6k (12.6k less in each). What makes up the difference is not measured here. The two "ok" runs still cost more on Sonnet 5.5 ($0.053 against $0.042).
- **Host scenarios cheaper and better:** $0.127 and 14 s per question against $0.172 and 26 s, at 127k input against 244k and 5 tool calls against 7.3; checks 8/10 against 6/10. `p1_partial` took 9 tool calls against 17 ($0.251 against $0.373). `k1_stale` passed 3/3 (2/3). The planted older copy (`n1_newer`, "using the kb") still stays inside the kb on both models (1/3 and 0/3).
- **Bare web search got cheaper:** Sonnet 5.5 without the kb answered `x1_synth` for $0.201 in 32 s with 9 tool calls, against Sonnet 5's $0.371, 89 s and 13 calls. The kb arm still wins that synthesis ($0.119, 17 s). On the single fact `s1_fact`, web search ($0.061) now costs less than the kb arm ($0.100), which also loads the user's plugins. On the off-kb `o1_offkb`, the kb arm pays for a pack plus research ($0.186 against $0.132).
- One batch of 2 runs per kb cell and 1 per host and web cell: the history's run-to-run spread (Opus `s1_fact`: $0.296 against $0.206) applies to any one cell. The means over the ten kb questions are steadier.

### A question pool over the kb, router, hook and web arms
**In short** (the record of 2026-10-09, Claude Code 2.1.293, 150 pool rows, every arm label complete at one rep, $149.54 of paid runs after the router arm was run again on Haiku 5.5 (see "The record of 2026-10-09"); the figures and their intervals are in "What it shows" below):
- **Opus 5.5:** right in 90.0% of runs at the default level, within the spread of Sonnet 5.5 (89.3%) and Haiku 5.5 (84.7%), with the fewest tokens per right answer of the kb arms (56,816, 15k-17k fewer than Sonnet 5.5 and Haiku 5.5 at the default level), at $0.232 a run: 1.5 times Sonnet 5.5 and 26 times Haiku 5.5.
- **Router (Haiku 5.5 reads, Sonnet 5.5 researches):** 17,544 effective input tokens per right answer against 73,323 for Haiku 5.5 with the kb, the interval of its cell (15,236-20,250) far below that of Haiku 5.5's (67,217-80,635); right in 92.0% of runs (138 of 150) against 84.7% for Haiku 5.5 and 90.0% for Opus 5.5, the cells' intervals overlapping; $0.024 a run. The record's first router rows read on Haiku 4.5 (14,632 tokens per right answer, 82.7% right, $0.026 a run) and were replaced; their cost does not compare with these, see "The router arm's two readers".
- **Hook:** no model tokens, and its pack holds the checked text in 128 of 150 runs; it cannot count or join.
- **Fixed context:** a kb run starts at about 32k-33k tokens, 22.8%-38.0% of its input.
- **Effort `low`:** 17% fewer tokens per right answer and 26% cheaper for Sonnet 5.5; for Haiku 5.5 and Opus 5.5 the tokens are within the spread and the run 13% and 6% cheaper; the rate of right answers within the spread for all three.
- **Haiku 5.5 against Haiku 4.5:** right in 84.7% of runs against 48.0%, at $0.009 a run against $0.034; Haiku 4.5 takes in less input per run, so it spends fewer tokens per right answer.
- **A session of six questions:** the first question adds 34.6k-38.2k tokens, each later one 3.7k-10.1k, and a session takes 23k-34k fewer tokens per right answer than fresh sessions on the same 150 rows, at 30%-48% less per question.
- **Bare web sessions:** right in 53.2% and 56.5% of runs against 88.7% for the kb arm on the same 62 rows, with fewer tokens per right answer.
- **Against the record of 2026-10-08:** on the 130 rows whose checks did not change, every arm's rate of right answers and input per run are within the spread. The tables' higher tokens per right answer (+13% to +20% for the kb arms, +99% for the router, over all rows and its reader now Haiku 5.5) mix more cache writes per run (Haiku 5.5 +2.4k, the router +4.2k), the new weights of effective input (a one-hour cache write at twice an input token, a Sonnet 5.5 cache read at its billed price), the changed checks, and cells over other rows (Haiku 4.5 and Sonnet 5.5 at the default level lacked the 20 `querylog` rows then). The router run costs more, billed: $0.024 against $0.020 over all rows, and its two records read on different models.
- **Not supported:** rankings within kinds of 1-5 rows (one run per row and arm label), and the four rows on the Autopilot motherboard question, whose check names a line that does not answer it (BG-zcw5yqch).
- **The record of 2026-10-12 (fresh shape, 180 rows, the 30 scenario rows included; Claude Code 2.1.296; six arms, 1,072 paid runs, $61.29, none failed; a first attempt of $61.09 failed `pool verify` (b) and was discarded, see "The record of 2026-10-12"):** router 18,197 effective input tokens per right answer (15,573-20,982 by the interval of its cell), right in 165 of 180 runs (91.7%; 87.8%-95.6%), $0.026 a run; Haiku 5.5 at the default level 66,482 (61,436-72,715), 152 of 180 (84.4%; 78.9%-89.4%), $0.009; Sonnet 5.5 at the default level 66,451 (61,603-72,345), 158 of 180 (87.8%; 82.8%-92.2%), $0.143, and at `low` 54,724 (51,444-58,678), $0.107; hook 168 of 180 (93.3%; 89.4%-96.7%) with no model tokens; the web arms 45 of 86 (Haiku 5.5) and 43 of 86 (Sonnet 5.5) runs right. The Sonnet 5.5 costs are priced at $0.10 per MTok for cache reads, the figure Claude Code 2.1.296 reports, where the earlier records' were counted at $0.20, so a Sonnet 5.5 dollar figure does not compare across the two.
- **The scenario kinds in that record (six rows each, one run per row and arm label, so no ranking within a kind):** runs right of six, in the order Haiku 5.5 `low`, Haiku 5.5 `default`, Sonnet 5.5 `low`, Sonnet 5.5 `default`, router, hook. `sc_present` 6, 6, 6, 6, 6, 6; `sc_partial` 4, 3, 4, 3, 4, 6; `sc_absent` 5, 5, 4, 5, 6, 2; `sc_offkb` 5, 4, 6, 5, 6, 6; `sc_stale` 1, 1, 1, 2, 1, 6. The web arms, which never ask `sc_stale`: `sc_present` 4 and 4, `sc_partial` 0 and 0, `sc_absent` 0 and 0, `sc_offkb` 1 and 1.

**Setup:** `python3 _tools/benchmarks.py run pool [--arms A,B] [--kinds K,K] [--effort low,default] [--reps N] [--shape fresh|session] [--seed N]` runs every row of the question pool (`kb/public/_retrieval/bench_pool.csv`, built by `pool build`, and the query-log file `kb/_querylog/bench/pool.csv` when this host has it) as a fresh `claude -p` per question (shape `fresh`, the default), hooks off, from the throwaway clone. The held-out rows' question text is read from `lookup_heldout.csv` at run time and is in no results file. The arms:
- **`haiku-5-5`, `haiku-4-5`, `sonnet-5-5`, `opus-5-5`:** the model pinned by id with the kb's tools and the docs servers, as the kb arm of "A new model against the one it replaces". `opus-5-5` runs only when `--arms` names it (a run with no `--arms` leaves it out, so the spend of a full record stays the arms above's), and then on its sanity subset, the kinds `csv_fact`, `multi`, `synthesis` and `near_miss` (10 rows at one rep, `bench_pool.SUBSET_KINDS`), unless `--kinds` or `--arm-kinds` name others; `--arm-kinds opus-5-5=all` runs every row, the full Opus arm that a model change needs (see the procedure). Its `planned_kinds` row names the kinds it ran, so `pool verify` (a) checks the subset's kinds and no others. Each runs at effort `low` (`--effort low`) and at `default` (no flag: the level the model starts with, `medium` on Haiku 5.5, Sonnet 5.5 and Opus 5.5 according to the Claude Code model configuration page, "Adjust effort level"). Haiku 4.5 has no effort level, so its arm runs once and the effort table marks it.
- **`router`:** `kb_ask.py`'s routing with the routed models pinned (`router-pinned`: Haiku 5.5 reads, the model the `haiku` alias names from Claude Code 2.1.293, and Sonnet 5.5 researches; the record's first router rows read on Haiku 4.5, see "The router arm's two readers"); its researcher always runs at effort `low`, so the router has one level.
- **`hook`:** the `kb:` hook, started through `_tools/kbpy` as the query log's hook scenarios start it; no model runs, so it records 0 tokens and its wall time, and its answer is the pack the hook shows (or, for a pack routed on, the context it adds), scored by the same checks.
- **`web-haiku-5-5`, `web-sonnet-5-5`:** the bare web session (no kb, no servers, no project files), the question followed by "Cite the source urls.". They run only the kinds a web search can answer (`fact`, `csv_fact`, `multi`, `synthesis`, `offkb`, `snippet`, `false_good`, `sc_present`, `sc_partial`, `sc_absent`, `sc_offkb`) and at the default effort only.

**The scenario kinds:** `kb/public/_retrieval/bench_scenarios.csv` holds the rows of five scenarios, six each, that `pool build` writes into the public pool, each with its expected outcome stated by its checks and its route:
- **`sc_present`, knowledge present:** the kb states the answer; the pack's route is `good` with no `check:` line, and a right answer matches the regex of the kb line that answers it.
- **`sc_partial`, present in part:** the kb states part of it and lacks the rest; the route is `split`, and a right answer matches that regex and says what the kb lacks (`LACKS_CHECK`).
- **`sc_absent`, not present:** the kb lacks it; the route is `web` or `none`, or, where the row's note marks a false good, a `good` or `split` pack that answers something else; a right answer says it is not confirmed in the kb or points to the live docs (`GAP_CHECK`).
- **`sc_offkb`, off the kb:** a question of no domain the kb covers, never a line of the off-kb list or the question of a good eval row; the route is `none` (printed `web`), and a right answer says the kb does not cover it (`NONE_CHECK`).
- **`sc_stale`, stale source:** the kb states the fact, but a source it cites is past its freshness lifetime; the route is `good`, and a right answer gives the fact with its source's confirmation date or a freshness mark (`FRESH_CHECK`: `confirmed DATE`, `unconfirmed`, `not confirmed`, `unanchored`, `source changed` or `stale`; the retrieved date of an article header, which every pack holds, does not meet it).
The web arms ask the first four kinds and never `sc_stale`: no web page states how old a kb source is. `pool check` asks `rag.py pack` for each scenario row's route and exits 1, naming the row, on one that disagrees with its `expected_route`: a pack with a `check:` line and no `route:` line is not `good` (the scatter note sets no route), so a `sc_present` or `sc_stale` row whose pack prints one is named.

`--arms` and `--kinds` name the subset, `--reps` the runs of each row on each arm, `--effort` the levels; `--arm-reps ARM=N` and `--arm-kinds ARM=K+K` (comma separated pairs, or the flag repeated; the kinds value `all` is every kind) give one arm its own reps and kinds, the arms they do not name taking `--reps` and `--kinds`, and an arm they name that the run does not run is an error (exit 2); `--sample N` keeps N rows of each kind, drawn per kind with `--seed`; `--shape fresh,session` runs both shapes in one run (the `ARM/session` key of `--arm-reps` and `--arm-kinds` gives an arm its own value in the session shape only), so a record shaped like that of 2026-10-08 below is one command with one `--max-usd` over all of it, one set of spend rows and one log; `--dry-run` prints the number of runs per arm label and starts no model. `--jobs N` (default 1) runs up to N of the runs at once; the rows and their order are those of one job, and every row carries the date the run started on, so a run that crosses midnight is one record. `--max-usd X` starts no new run of a shape once the finished runs have cost that shape's part of X (what is left of X shared out by the shapes' estimated spend, the last shape taking all that is left), the runs of a shape starting one of each arm label in turn (the order of the rows too), so that a run the cap stops leaves every arm label some runs (the runs in flight finish, so the spend can pass X by up to `--jobs` runs, or sessions in the session shape), writes a `spend_stopped` row per arm label (case `not started`, the value the runs not started, the note naming them) and exits 1; the arm labels it left unfinished then hold fewer runs than `--reps` asks. `--dry-run` also prints an estimate of the spend, per arm label: a run priced at the mean `cost` of the label's `all` cell in its newest earlier pool record (what its runs were billed, web searches included), else, for a kb arm whose label has no record, at the list prices of `bench_core.py` on the mean tokens of the same effort and shape label of another kb arm (the newest record, Sonnet 5.5 first), priced as the arm's own model, else on a stated default per run (about a Sonnet 5.5 lookup with the kb tools, in `bench_pool.DEFAULT_RUN`), web searches left out of the last two. It is an estimate of the spend, not a measurement. A run replaces the rows of the same day for the arm labels it ran (`model:level`, or the arm's name), so a second run of other arms on the same day adds to the record.

**The session shape (`--shape session`):** an operator asks several lookups in one session, so the fixed context is paid once and cache reads carry the rest, which a fresh session per question cannot show. The shape orders the pool's rows with its own generator (seed `--seed`, default the pool's), builds groups of six rows, each of mixed kinds (a group takes rows of different kinds first) and never two rows of one `source` (a base question and its variants name one fact), and leaves out the rows that cannot fill a last group. Each group runs in one `claude -p` session on the kb arms `haiku-5-5` and `sonnet-5-5` (`--arms` narrows them, `--effort` sets the levels, both at `low` and `default` by default), from the throwaway clone: the first question starts the session with `--session-id` and keeps it, each later one resumes it with `--resume` in the same directory, and each question's run is parsed from its own stream. A question that fails ends its group's session; the questions after it count as errors. `--reps` repeats every group in a new session. The arm labels of the shape end in `/session` (`model:level/session`), so its rows sit beside the fresh labels' and a same-day run of either replaces only its own. Besides the rows per kind and for all kinds of "Counting (the pool)", each label has, per position of the question in its session (the case `position N`), `marginal_input` (the whole prompt of the question's last request less the last prompt of the question before it, so the first question's is all of its prompt), `cache_read_share` (cache reads over input, pooled over the position's runs) and `checks`. `--dry-run` prints the sessions and runs, and the estimate of the spend, without starting a model; `--jobs` runs sessions at once, each session's questions in order. The table of these rows, `marginal_input` and `cache_read_share` by position and arm label, is the report's `session` view (`bench_report.py`); the section gets its marker with the first record of the shape.

**Recording a pool run (the procedure):** a record is one command under one `--max-usd`, run first as a smoke and then in full, and each is checked by `pool verify` before its rows are kept.
1. *Dry run.* The command below with `--dry-run` prints the runs per arm label and the estimate of the spend (list prices, cache writes at the rate of the billing surface the runs are billed on, one hour on a subscription). Set `--max-usd` above that estimate: a run stopped at its cap writes `spend_stopped` rows, exits 1 and does not pass `pool verify`, and every arm label stopped is short of the runs it planned.
2. *Smoke.* All the arms with the Opus arm (on its subset kinds, so two rows of each of the four), both shapes, two rows of each kind, one rep, eight runs at once, the rows written to a scratch file and never to `benchmarks.csv`: `python3 _tools/benchmarks.py run pool --arms haiku-5-5,haiku-4-5,sonnet-5-5,opus-5-5,router,hook,web-haiku-5-5,web-sonnet-5-5 --shape fresh,session --sample 2 --reps 1 --jobs 8 --max-usd CAP --out SCRATCH/pool-smoke.csv`, with CAP above the dry run's estimate and SCRATCH a scratch directory outside the tracked files (`_cache/scratch/` holds them). Then `python3 _tools/benchmarks.py pool verify --file SCRATCH/pool-smoke.csv`: exit 0 passes it, and any other exit names the property it breaks, to be fixed at its cause before the record is run.
3. *Record.* The smoke's command without `--sample` and `--out`, at `--reps 1`, the cap above its own dry run's estimate, then `python3 _tools/benchmarks.py pool verify --record DATE` on the results file, and `python3 _tools/benchmarks.py report`. The Opus arm of this command runs its sanity subset only: its cells then rest on 10 rows and 20 runs, a fraction of the other arms' cells.
4. *A model change.* When the model behind an arm changes (a new id for `opus-5-5`), the record names the full Opus arm: the same command with `--arm-kinds opus-5-5=all` (the dry run plans every row of the pool for each effort level, and its estimate shows the cost), so that the new model is read on the rows the other arms ran. A record without it carries Opus cells that are the subset's.
5. *A change to how a run is counted or priced.* A change to a `bench_*` module or `agent_bench.py` that alters a count or a price lands with one real probe for each shape it changes: the smoke's command narrowed to the arms of that shape (`--shape fresh`, `--shape session` or a web arm), `--sample 1`, `--reps 1`, `--max-usd` 1.5 times its own dry run's estimate, and `BENCH_SCRATCH` naming a directory under `_cache/scratch/` so the runs file keeps the streams. `pool verify --file` on its rows must pass check (b): every run's list cost within 20% of its billed cost. The fake-runner tests plant the shapes their author knew, and the three smoke records of SP-2vhfsn4o, 96 USD in all, found the five they missed (`kb/_self/backlog.md`, Sprints, Plan).

`pool verify [--file F] [--record R]` reads only the rows of record R (default the newest pool record) in file F (default the results file), and exits 1, one line for each break, when the record breaks one of these (the letter starts the line): (a) an arm label has no row for a kind it was to run, or has runs not started (every label has a `planned_kinds` row, written before the first run: its kinds joined by `+`, its planned runs as `runs`); (b) a model arm has a run whose cost is more than 20% from the list price of its counted input and output (`off_list`, the count of such runs in the label's `all` cell, must be 0; `list_cost` is the mean list price, which prices a cache write at its TTL's rate (the usage's split, else the billing surface's) and a web arm's searches at 0.01 each), which a cumulative session cost or an undercounted `out` breaks; (c) the spend rows of a set of labels differ from the sum over those labels of the mean `cost` times the runs, or a label that cost something is in no spend row; (d) a session label's mean `cost` is higher at every position than at the one before, over three or more positions, or its positions hold no `cost`; (e) `out` is 0 or missing on a model arm; (f) failed runs are 2% or more of the record's runs together. The record of 2026-10-08 predates (a), (b) and (d): its rows hold no plan, its `out` is a partial count and its session rows hold no cost per position, so `pool verify` names those three as not checked and checks the others, which it passes; a record of another date, or one that holds `planned_kinds` rows, is checked in full. The runs file is not read: it sits in the scratch directory, outside the repository, and a same-day run appends to it whatever `--out` says.

**Counting (the pool):** one row per kind and arm label, and one for all kinds (`all`); the means over the cell's runs of `input` (uncached + cache-write + cache-read, from the requests of the run's stream), `cache_read`, `cache_write`, `effective_input` (weighted as in Counting above, each request by its own model's prices), `out` (from the result event, as in Counting above), `start_ctx` (the first request's whole prompt), `pack_tokens`, `tool_calls`, `turns`, `wall_s` and `cost` (the run's result event). `pack_tokens` is the size of the kb tool results of the main session: each result's growth of the prompt from the request before it, less that request's output (the result event's main-loop output count shared by the requests in proportion to their messages' partial counts, which the stream gives instead of the real ones), at most the result's characters, and four characters per token when the prompt did not grow; the router's pack, which it hands to the reader in the prompt and not as a tool result, is counted at four characters per token, and the hook arm and the web arms have none. A run is right when all of its checks pass; `checks` is the passed over the total, `fully_right` the runs that were right, `fixed_share` is `start_ctx` over `input` (the share of a run's input that is there before the question) and `tokens_per_right` is the effective input of all the cell's runs over the runs that were right, left out where none was. Each cell also keeps the 95% interval of `tokens_per_right` and of the right share (`fully_right` over the cell's runs) as the metrics `tokens_per_right_lo`, `tokens_per_right_hi`, `right_share_lo` and `right_share_hi`, so a later report judges a difference from the results file alone: a bootstrap over the cell's pool rows, 1000 resamples, each drawing as many rows as the cell has with replacement and keeping a row's reps together (rows are the unit, not runs, since the reps of one question are not independent), by a generator seeded from the pool's seed so the same runs give the same bounds on any host; each resample gives its right share and its `tokens_per_right`, and the bounds are the values at 2.5% and 97.5% of the sorted resamples. A resample with no right run has no `tokens_per_right` and is left out of that interval (the bounds come from the resamples that have one, so they sit lower than an interval that counted such a resample as unbounded); a cell with no right run has no `tokens_per_right` pair at all, as it has no mean. A cell of one row has an interval of a single point. The rows of earlier records are not rewritten and have no interval. A failed run (no result event, a usage limit) has no tokens and is counted in `errors`. Besides, the `all` cell of each label holds `list_cost` and `off_list` and each session position its mean `cost`, and each label has a `planned_kinds` row (the procedure above).

The generated tables of this section: the records, `tokens_per_right` and `fully_right` by kind (rows) and arm (columns), the all-kinds cells by arm (`start_ctx`, `fixed_share`, `tokens_per_right`, `fully_right`, `cost`), the effort levels of each model side by side (`low` against `default`), the pair Haiku 5.5 against Haiku 4.5 at the default level as "A new model against the one it replaces" prints its pair, and the session shape by position. `report --check` fails on a `bench:` marker whose scenario has no rows in the results file.

<!-- bench:records pool -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-10-08 | 2026-10-08 | 19e0568 | 2.1.293 | 299 | 6 | $113.96 |
| 2026-10-09 | 2026-10-09 | 0969f3c | 2.1.293 | 299 | 2 | $149.54 |
| 2026-10-12 | 2026-10-12 | 541378c | 2.1.296 | 359 | 6 | $61.29 |
<!-- /bench -->

**The record of 2026-10-12** (Claude Code 2.1.296, 359 kb topics, 180 rows: the 150 of the record before and the 30 scenario rows; the fresh shape, six arms, 1,072 paid runs, none failed, $61.29) is the procedure above's third step, run on commit `541378c`. **A first attempt of the same command the same day was discarded:** it cost $61.09 and failed `pool verify` (b) on 8 of its 1,072 runs, whose cost was more than 20% from the list price of their counted input. `bench_core.PRICE` held $0.20 per million tokens for a Sonnet 5.5 cache read, and Claude Code 2.1.296 reports $0.10, the pricing page's figure; a run is now priced at the rate its own version's cost figure counted (`READ_BEFORE`: $0.20 before 2.1.296), and the command was run again. The second run's rows replaced the first attempt's, so no table here holds the first attempt's figures. The smoke before the first attempt (312 runs) had passed `pool verify`: a smoke of that size is too small to catch a rare off-list run.

**The record of 2026-10-09** (Claude Code 2.1.293, 299 kb topics, the same 150 rows as the record before, 19 of them with a new check and one `querylog` row replaced) is the procedure above in one command: `run pool --arms haiku-5-5,haiku-4-5,sonnet-5-5,opus-5-5,router,hook,web-haiku-5-5,web-sonnet-5-5 --shape fresh,session --reps 1 --jobs 8 --max-usd 170`, after a smoke of the same arms that passed `pool verify`. It ran before the Opus subset became the default, so its Opus arm ran every row (the full arm, as `--arm-kinds opus-5-5=all` plans it now): the same command today plans the subset. The dry run estimated $142.24 for its 2,074 runs; all ran, none failed, and the paid ones (all but the hook's 150) cost $149.74: Opus 5.5 $67.43, Sonnet 5.5 fresh $39.16 and in sessions $24.41, the web arms $5.90, Haiku 4.5 $5.05, Haiku 5.5 fresh and in sessions $3.97, the router $3.83 (its rows were replaced, see "The router arm's two readers"). Every arm label ran all its rows once (the web arms their 62 rows of the kinds a web search can answer), and each session label 25 sessions of six over the whole pool. No free scenario ran with it. Its counts differ from the record before in four ways: `out` is the output of every model of the run (it was a partial count), a split route of the router is scored on both answers (it was the researcher's alone), a cache write is weighted at its TTL's rate and a Sonnet 5.5 cache read at its billed price, and a session question holds its own share of the session's output and models.

**The router arm's two readers.** The record's first router rows ran `router-pinned` with `agent_bench.PIN` naming `claude-haiku-4-5` for the reader, while `kb_ask.py`'s reader runs on the `haiku` alias, which names Haiku 5.5 from Claude Code 2.1.293 (`kb/public/claude/ci-and-headless.md:85`). The pin now names `claude-haiku-5-5` and the arm was run again, the same day, on commit `bc8f8d7`: `run pool --arms router --reps 1 --max-usd 5.75`, 150 runs, none failed, $3.62 (the dry run estimated $3.83 from the first rows), which replaced the first router rows and left every other arm label's. The reader's model sets the price of a run's cache writes: a 1-hour write costs $2 per million tokens on Haiku 4.5 and $0.20 on Haiku 5.5 (`kb/public/claude/ci-and-headless.md:88`, `:91`), and the first rows wrote 5,424 tokens a run to the cache. Their cost per run, $0.026, therefore does not compare with the new rows' $0.024. Effective input weights a 1-hour write at twice an input token on both readers, so the two figures of tokens per right answer, 14,632 and 17,544, are counted alike and belong to two readers. Read the new rows only: right in 138 of 150 runs (92.0%, 87.3%-96.0% by the interval of its cell) against 124 of 150, a start of 7,587 tokens (9,455), 19,761 tokens of input a run (17,814), 7,453 tokens written to the cache a run (5,424), 1,864 output tokens a run (1,170) and 0.8 tool calls a run (0.6). The pool's spend rows for the record hold the full run's 1,774 paid runs that stand ($145.91, the first router rows taken out) and the re-run's 150 ($3.62): $149.54 in 1,924 runs, where the $149.74 above counts the first router rows too.

**The record of 2026-10-08** (Claude Code 2.1.293, 299 kb topics; the pool is 150 rows: 130 of the public pool and the 20 `querylog` rows of the host's query-log file) was run as six same-day chunks, each a `run` of its own (the pool ones with `--jobs 8` and a `--max-usd` cap); the arm labels each chunk did not run keep their rows:
- **Free scenarios** (`always-on`, `retrieval`, `verdict`, `tool-speed`): $0.09.
- **`haiku-5-5` and `haiku-4-5`** (`--arms haiku-5-5,haiku-4-5 --reps 3 --max-usd 20`): $20.25. `haiku-5-5` at both effort levels ran all 450 runs. `haiku-4-5` stopped at the cap: **382 of its 450 runs ran, 68 were not started**: the 20 `querylog` rows, a `variant_typo` row and a `variant_sentence` row have no run, and a `variant_keyword` row has fewer than 3. Its cells are short, and the `querylog` kind has no `haiku-4-5` cell.
- **`sonnet-5-5`** (`--arms sonnet-5-5 --reps 2 --max-usd 68`): $68.87. `sonnet-5-5:low` ran all 300 runs; **`sonnet-5-5:default` ran 255 of 300, 45 not started**, the same rows as `haiku-4-5` lacks, so it too has no `querylog` cell.
- **`router` and `hook`** (`--reps 3 --max-usd 16`): $9.09, complete (450 runs each; the hook starts no model).
- **`web-haiku-5-5` and `web-sonnet-5-5`** (`--kinds csv_fact,multi,synthesis,false_good,snippet,offkb --reps 2 --max-usd 7`): $6.00, complete: 29 rows, 58 runs each.
- **The session shape** (`--shape session` on the kinds `csv_fact`, `multi`, `synthesis`, `false_good`, `near_miss`, `snippet`, `count`, `cites`, `decision`, `conflict` and `gap`, 5 groups of six rows, `--reps 2 --max-usd 11`): $9.75, complete: each of the four labels ran its 10 sessions (60 runs). A first run of this chunk the same day counted each follow-up's cost as the session's running total, which a resumed run's result event reports, so its cap stopped `sonnet-5-5:default/session` early; its rows were replaced by this run, once each question's cost was its own share of that total (BG-2tan24sm). That first run cost about $4.27.

The pool chunks of the record cost $113.96 and the free scenarios $0.09: $114.05 in all, and $118.32 with the replaced first session run. Each chunk's spend rows carry an arm naming the labels it ran (`paid: ...`), so a same-day chunk keeps the others' and the records and spend tables sum them; the first chunks' rows were rebuilt from the runs file, since the runner then wrote them under one arm and each chunk replaced the one before. "Runs per cell" is the most common cell size, not the reps. No Opus subset ran: the pool scenario has no Opus arm. The results file holds means only; the spreads below were computed from the record's run records (3,033 from the first runs, the session shape's 240 from its re-run) that the scenario appends to its runs file (kept outside the repository, not committed).

**Opus cells.** An `opus-5-5` cell of a record whose Opus arm ran its sanity subset (its `planned_kinds` row names `csv_fact`, `multi`, `synthesis` and `near_miss`) is over those four kinds' 10 rows: its other kinds' cells are empty, and its all-kinds cell, its effort pair and its differences against the other arms are over 10 rows, not the pool's 150, and are not compared with theirs. The Opus cells of the record of 2026-10-09 below are the full arm's: all 150 rows.

Tokens per right answer, by kind and arm (the effective input of all of a cell's runs over the runs that were right):
<!-- bench:matrix pool metric=tokens_per_right arms=haiku-5-5:low,haiku-5-5:default,haiku-4-5,sonnet-5-5:low,sonnet-5-5:default,opus-5-5:low,opus-5-5:default,router,hook,web-haiku-5-5,web-sonnet-5-5 -->
| case | haiku-5-5:low | haiku-5-5:default | haiku-4-5 | sonnet-5-5:low | sonnet-5-5:default | router | hook | web-haiku-5-5 | web-sonnet-5-5 | opus-5-5:low | opus-5-5:default |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fact | 49,542 -> 62,434 -> 58,523 (-6%) | 56,427 -> 63,929 -> 54,022 (-15%) | 37,953 -> 39,150 (+3%) | 47,289 -> 59,035 -> 54,541 (-8%) | 55,290 -> 67,847 -> 61,608 (-9%) | 5,624 -> 13,677 -> 13,337 (-2%) | 0 -> 0 -> 0 | 37,873 -> 32,015 (-15%) | 26,249 -> 23,414 (-11%) | 55,654 | 62,481 |
| multi | 49,177 -> 48,294 -> 55,259 (+14%) | 49,402 -> 56,291 -> 42,471 (-25%) | 58,400 -> 85,180 (+46%) | 48,522 -> 49,002 -> 45,482 (-7%) | 65,089 -> 50,828 -> 50,482 (-1%) | 5,593 -> 9,863 -> 10,011 (+2%) | 0 -> 0 -> 0 | 40,874 | 35,888 | 46,541 | 49,581 |
| synthesis | 67,810 -> 79,308 -> 67,536 (-15%) | 76,630 -> 90,908 -> 82,334 (-9%) | 28,050 | 58,715 -> 48,171 -> 46,804 (-3%) | 75,981 -> 87,563 -> 77,454 (-12%) | 5,522 -> 9,869 -> 10,565 (+7%) | 0 -> 0 -> 0 | 69,384 -> 18,273 -> 32,792 (+79%) | 60,884 -> 46,033 -> 67,369 (+46%) | 59,416 | 64,830 |
| csv_fact | 61,215 -> 62,716 -> 61,695 (-2%) | 63,999 -> 69,675 -> 60,526 (-13%) | 33,031 -> 57,472 (+74%) | 47,032 -> 53,670 -> 46,145 (-14%) | 49,445 -> 60,083 -> 49,977 (-17%) | 10,789 -> 18,667 -> 16,822 (-10%) | 0 -> 0 -> 0 | 79,523 -> 52,266 -> 43,506 (-17%) | 39,199 -> 34,697 -> 19,345 (-44%) | 54,679 | 49,492 |
| heldout | 69,065 -> 67,547 -> 61,706 (-9%) | 61,894 -> 66,245 -> 71,627 (+8%) | 253,610 -> 165,213 (-35%) | 46,293 -> 56,510 -> 55,020 (-3%) | 66,093 -> 69,607 -> 65,531 (-6%) | 3,545 -> 12,331 -> 17,130 (+39%) | 0 -> 0 -> 0 | - | - | 49,422 | 52,396 |
| offkb | 71,901 -> 68,744 -> 84,694 (+23%) | 95,807 -> 81,580 -> 73,931 (-9%) | 78,676 -> 61,841 (-21%) | 61,531 -> 61,521 -> 55,227 (-10%) | 75,559 -> 82,705 -> 84,874 (+3%) | 21,097 -> 30,620 -> 30,435 (-1%) | 0 -> 0 -> 0 | 200,365 -> 334,407 (+67%) | 362,921 -> 215,306 (-41%) | 60,050 | 65,522 |
| false_good | 108,155 -> 83,690 -> 75,822 (-9%) | 111,005 -> 81,438 -> 81,889 (+1%) | 55,266 -> 45,623 (-17%) | 81,218 -> 126,143 -> 67,958 (-46%) | 126,998 -> 81,773 -> 73,566 (-10%) | 14,031 -> 26,772 -> 26,780 (+0%) | 0 -> 0 -> 0 | 84,731 -> 121,526 -> 68,250 (-44%) | 83,438 -> 50,529 -> 110,095 (+118%) | 128,345 | 63,935 |
| near_miss | 52,342 -> 47,894 -> 37,068 (-23%) | 44,354 -> 53,780 -> 47,935 (-11%) | 28,382 -> 26,163 (-8%) | 45,014 -> 47,634 -> 44,225 (-7%) | 32,477 -> 49,270 -> 34,309 (-30%) | 7,783 -> 15,456 -> 12,384 (-20%) | 0 -> 0 -> 0 | - | - | 43,611 | 45,305 |
| gap | 73,010 -> 54,090 -> 60,322 (+12%) | 54,150 -> 58,553 -> 49,710 (-15%) | 139,321 -> 69,315 (-50%) | 53,359 -> 60,939 -> 59,457 (-2%) | 79,102 -> 89,328 -> 59,467 (-33%) | 23,695 -> 27,833 -> 0 (-100%) | 0 -> 0 -> 0 | - | - | 58,282 | 54,528 |
| count | 48,372 -> 48,141 -> 48,552 (+1%) | 47,979 -> 52,954 -> 41,903 (-21%) | 32,534 -> 48,976 (+51%) | 43,727 -> 47,870 -> 43,010 (-10%) | 38,638 -> 47,964 -> 40,046 (-17%) | 0 -> 0 -> 0 | 0 | - | - | 42,793 | 44,262 |
| cites | 33,543 -> 48,731 -> 46,235 (-5%) | 46,771 -> 45,554 -> 46,285 (+2%) | 29,582 -> 28,203 (-5%) | 31,235 -> 48,345 -> 40,986 (-15%) | 44,629 -> 47,728 -> 41,669 (-13%) | 0 -> 0 -> 0 | 0 -> 0 -> 0 | - | - | 42,765 | 44,180 |
| decision | 45,663 -> 111,655 -> 45,093 (-60%) | 56,125 -> 59,980 -> 50,033 (-17%) | 91,532 | 93,218 -> 45,310 (-51%) | 46,909 -> 67,416 -> 42,264 (-37%) | 0 | 0 | - | - | 48,449 | 49,476 |
| conflict | 127,767 -> 159,850 (+25%) | 208,010 -> 154,701 (-26%) | 178,456 -> 107,000 (-40%) | 84,968 -> 43,962 (-48%) | 150,610 -> 220,196 -> 79,711 (-64%) | 0 | 0 | - | - | 109,455 | 68,213 |
| snippet | 72,344 -> 105,863 -> 70,897 (-33%) | 81,679 -> 103,669 -> 74,806 (-28%) | 52,876 -> 80,955 (+53%) | 52,745 -> 60,389 -> 79,385 (+31%) | 98,377 -> 86,630 -> 97,230 (+12%) | 14,363 -> 22,152 -> 21,954 (-1%) | 0 -> 0 -> 0 | 60,866 -> 59,264 -> 58,969 (-0%) | 31,659 -> 32,282 -> 34,460 (+7%) | 57,634 | 64,762 |
| variant_keyword | 48,904 -> 64,280 -> 49,818 (-22%) | 54,960 -> 79,573 -> 63,632 (-20%) | 32,612 -> 35,369 (+8%) | 38,147 -> 51,541 -> 45,783 (-11%) | 46,531 -> 75,502 -> 54,568 (-28%) | 3,656 -> 8,908 -> 11,952 (+34%) | 0 -> 0 -> 0 | - | - | 58,364 | 59,125 |
| variant_sentence | 50,978 -> 59,686 -> 55,458 (-7%) | 52,008 -> 63,903 -> 58,903 (-8%) | 48,576 -> 51,018 (+5%) | 46,607 -> 55,497 -> 47,984 (-14%) | 48,667 -> 74,676 -> 60,849 (-19%) | 9,822 -> 23,495 -> 16,911 (-28%) | 0 -> 0 -> 0 | - | - | 59,010 | 62,342 |
| variant_typo | 52,555 -> 73,083 -> 61,163 (-16%) | 63,318 -> 79,134 -> 61,159 (-23%) | 35,538 -> 45,906 (+29%) | 44,246 -> 61,845 -> 48,132 (-22%) | 52,237 -> 69,514 -> 51,318 (-26%) | 15,897 -> 22,944 -> 27,387 (+19%) | 0 -> 0 -> 0 | - | - | 60,288 | 60,469 |
| querylog | 66,828 -> 90,908 -> 68,880 (-24%) | 81,135 -> 91,445 -> 62,121 (-32%) | 447,615 | 67,843 -> 57,836 -> 46,353 (-20%) | 71,430 -> 58,018 (-19%) | 7,407 -> 15,902 -> 15,119 (-5%) | 0 -> 0 -> 0 | - | - | 56,142 | 47,592 |
| sc_present | 53,615 | 48,038 | - | 46,253 | 52,951 | 9,440 | 0 | 43,022 | 20,476 | - | - |
| sc_partial | 117,480 | 158,411 | - | 82,093 | 172,410 | 70,991 | 0 | - | - | - | - |
| sc_absent | 95,644 | 88,001 | - | 96,366 | 105,017 | 33,304 | 0 | - | - | - | - |
| sc_offkb | 73,980 | 84,461 | - | 52,722 | 72,424 | 15,049 | 0 | 114,274 | 57,752 | - | - |
| sc_stale | 315,995 | 348,550 | - | 288,871 | 159,961 | 90,621 | 0 | - | - | - | - |
| all | 58,872 -> 69,260 -> 66,390 (-4%) | 64,928 -> 73,323 -> 66,482 (-9%) | 50,787 -> 58,742 (+16%) | 50,665 -> 59,573 -> 54,724 (-8%) | 60,167 -> 72,010 -> 66,451 (-8%) | 8,828 -> 17,544 -> 18,197 (+4%) | 0 -> 0 -> 0 | 97,389 -> 54,988 -> 56,365 (+3%) | 72,802 -> 36,122 -> 38,164 (+6%) | 55,882 | 56,816 |
<!-- /bench -->

Runs that were right, by kind and arm:
<!-- bench:matrix pool metric=fully_right arms=haiku-5-5:low,haiku-5-5:default,haiku-4-5,sonnet-5-5:low,sonnet-5-5:default,opus-5-5:low,opus-5-5:default,router,hook,web-haiku-5-5,web-sonnet-5-5 -->
| case | haiku-5-5:low | haiku-5-5:default | haiku-4-5 | sonnet-5-5:low | sonnet-5-5:default | router | hook | web-haiku-5-5 | web-sonnet-5-5 | opus-5-5:low | opus-5-5:default |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fact | 94 of 99 -> 30 of 33 -> 30 of 33 | 96 of 99 -> 29 of 33 -> 31 of 33 | 73 of 99 -> 24 of 33 | 64 of 66 -> 28 of 33 -> 29 of 33 | 63 of 66 -> 28 of 33 -> 29 of 33 | 93 of 99 -> 29 of 33 -> 30 of 33 | 99 of 99 -> 29 of 33 -> 30 of 33 | 25 of 33 -> 28 of 33 | 26 of 33 -> 27 of 33 | 28 of 33 | 27 of 33 |
| multi | 6 of 6 -> 2 of 2 -> 2 of 2 | 6 of 6 -> 2 of 2 -> 2 of 2 | 3 of 6 -> 1 of 2 | 4 of 4 -> 2 of 2 -> 2 of 2 | 3 of 4 -> 2 of 2 -> 2 of 2 | 6 of 6 -> 2 of 2 -> 2 of 2 | 6 of 6 -> 2 of 2 -> 2 of 2 | 0 of 4 -> 0 of 2 -> 2 of 2 | 0 of 4 -> 0 of 2 -> 2 of 2 | 2 of 2 | 2 of 2 |
| synthesis | 3 of 3 -> 1 of 1 -> 1 of 1 | 3 of 3 -> 1 of 1 -> 1 of 1 | 2 of 3 -> 0 of 1 | 2 of 2 -> 1 of 1 -> 1 of 1 | 2 of 2 -> 1 of 1 -> 1 of 1 | 3 of 3 -> 1 of 1 -> 1 of 1 | 3 of 3 -> 1 of 1 -> 1 of 1 | 2 of 2 -> 1 of 1 -> 1 of 1 | 2 of 2 -> 1 of 1 -> 1 of 1 | 1 of 1 | 1 of 1 |
| csv_fact | 12 of 12 -> 4 of 4 -> 4 of 4 | 12 of 12 -> 4 of 4 -> 4 of 4 | 10 of 12 -> 2 of 4 | 8 of 8 -> 4 of 4 -> 4 of 4 | 8 of 8 -> 4 of 4 -> 4 of 4 | 12 of 12 -> 4 of 4 -> 4 of 4 | 12 of 12 -> 4 of 4 -> 4 of 4 | 4 of 8 -> 2 of 4 -> 3 of 4 | 3 of 8 -> 2 of 4 -> 3 of 4 | 4 of 4 | 4 of 4 |
| heldout | 49 of 60 -> 17 of 20 -> 17 of 20 | 54 of 60 -> 18 of 20 -> 15 of 20 | 6 of 60 -> 3 of 20 | 36 of 40 -> 19 of 20 -> 17 of 20 | 37 of 40 -> 20 of 20 -> 18 of 20 | 60 of 60 -> 20 of 20 -> 19 of 20 | 60 of 60 -> 20 of 20 -> 20 of 20 | - | - | 20 of 20 | 20 of 20 |
| offkb | 41 of 45 -> 14 of 15 -> 12 of 15 | 32 of 45 -> 13 of 15 -> 14 of 15 | 16 of 45 -> 7 of 15 | 26 of 30 -> 14 of 15 -> 15 of 15 | 27 of 30 -> 14 of 15 -> 14 of 15 | 43 of 45 -> 15 of 15 -> 15 of 15 | 39 of 45 -> 13 of 15 -> 13 of 15 | 3 of 30 -> 0 of 15 -> 1 of 15 | 1 of 30 -> 1 of 15 -> 0 of 15 | 14 of 15 | 14 of 15 |
| false_good | 4 of 6 -> 2 of 2 -> 2 of 2 | 4 of 6 -> 2 of 2 -> 2 of 2 | 4 of 6 -> 2 of 2 | 3 of 4 -> 1 of 2 -> 2 of 2 | 3 of 4 -> 2 of 2 -> 2 of 2 | 5 of 6 -> 2 of 2 -> 2 of 2 | 3 of 6 -> 1 of 2 -> 1 of 2 | 2 of 4 -> 1 of 2 -> 1 of 2 | 2 of 4 -> 1 of 2 -> 1 of 2 | 1 of 2 | 2 of 2 |
| near_miss | 8 of 9 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 -> 3 of 3 | 8 of 9 -> 3 of 3 | 6 of 6 -> 3 of 3 -> 3 of 3 | 6 of 6 -> 3 of 3 -> 3 of 3 | 8 of 9 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 -> 3 of 3 | - | - | 3 of 3 | 3 of 3 |
| gap | 10 of 15 -> 5 of 5 -> 4 of 5 | 12 of 15 -> 5 of 5 -> 5 of 5 | 3 of 15 -> 2 of 5 | 8 of 10 -> 4 of 5 -> 4 of 5 | 8 of 10 -> 4 of 5 -> 5 of 5 | 4 of 15 -> 5 of 5 -> 5 of 5 | 6 of 15 -> 2 of 5 -> 5 of 5 | - | - | 4 of 5 | 5 of 5 |
| count | 9 of 9 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 2 of 3 | 6 of 6 -> 3 of 3 -> 3 of 3 | 6 of 6 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 -> 3 of 3 | 0 of 9 -> 0 of 3 -> 3 of 3 | - | - | 3 of 3 | 3 of 3 |
| cites | 9 of 9 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 | 6 of 6 -> 3 of 3 -> 3 of 3 | 6 of 6 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 -> 3 of 3 | 9 of 9 -> 3 of 3 -> 3 of 3 | - | - | 3 of 3 | 3 of 3 |
| decision | 6 of 6 -> 1 of 2 -> 2 of 2 | 6 of 6 -> 2 of 2 -> 2 of 2 | 2 of 6 -> 0 of 2 | 2 of 4 -> 0 of 2 -> 2 of 2 | 4 of 4 -> 2 of 2 -> 2 of 2 | 0 of 6 -> 0 of 2 -> 2 of 2 | 0 of 6 -> 0 of 2 -> 2 of 2 | - | - | 2 of 2 | 2 of 2 |
| conflict | 3 of 6 -> 0 of 2 -> 1 of 2 | 3 of 6 -> 0 of 2 -> 1 of 2 | 3 of 6 -> 1 of 2 | 3 of 4 -> 0 of 2 -> 2 of 2 | 2 of 4 -> 1 of 2 -> 2 of 2 | 0 of 6 -> 0 of 2 -> 2 of 2 | 0 of 6 -> 0 of 2 -> 2 of 2 | - | - | 1 of 2 | 2 of 2 |
| snippet | 11 of 15 -> 3 of 5 -> 4 of 5 | 12 of 15 -> 4 of 5 -> 4 of 5 | 10 of 15 -> 3 of 5 | 8 of 10 -> 4 of 5 -> 3 of 5 | 6 of 10 -> 4 of 5 -> 3 of 5 | 11 of 15 -> 4 of 5 -> 4 of 5 | 15 of 15 -> 5 of 5 -> 5 of 5 | 8 of 10 -> 4 of 5 -> 4 of 5 | 8 of 10 -> 4 of 5 -> 4 of 5 | 4 of 5 | 4 of 5 |
| variant_keyword | 30 of 30 -> 8 of 10 -> 10 of 10 | 30 of 30 -> 8 of 10 -> 9 of 10 | 23 of 28 -> 6 of 10 | 20 of 20 -> 8 of 10 -> 10 of 10 | 19 of 19 -> 8 of 10 -> 9 of 10 | 30 of 30 -> 10 of 10 -> 9 of 10 | 30 of 30 -> 9 of 10 -> 10 of 10 | - | - | 8 of 10 | 8 of 10 |
| variant_sentence | 30 of 30 -> 9 of 10 -> 10 of 10 | 30 of 30 -> 9 of 10 -> 9 of 10 | 17 of 27 -> 6 of 10 | 20 of 20 -> 9 of 10 -> 10 of 10 | 18 of 18 -> 8 of 10 -> 9 of 10 | 27 of 30 -> 9 of 10 -> 10 of 10 | 30 of 30 -> 9 of 10 -> 10 of 10 | - | - | 8 of 10 | 8 of 10 |
| variant_typo | 29 of 30 -> 8 of 10 -> 9 of 10 | 30 of 30 -> 8 of 10 -> 9 of 10 | 20 of 27 -> 6 of 10 | 20 of 20 -> 8 of 10 -> 10 of 10 | 18 of 18 -> 9 of 10 -> 10 of 10 | 28 of 30 -> 10 of 10 -> 10 of 10 | 27 of 30 -> 8 of 10 -> 9 of 10 | - | - | 8 of 10 | 8 of 10 |
| querylog | 41 of 60 -> 13 of 20 -> 14 of 20 | 41 of 60 -> 13 of 20 -> 16 of 20 | 1 of 20 | 26 of 40 -> 17 of 20 -> 17 of 20 | 18 of 20 -> 18 of 20 | 43 of 60 -> 18 of 20 -> 18 of 20 | 48 of 60 -> 19 of 20 -> 19 of 20 | - | - | 18 of 20 | 19 of 20 |
| sc_present | 6 of 6 | 6 of 6 | - | 6 of 6 | 6 of 6 | 6 of 6 | 6 of 6 | 4 of 6 | 4 of 6 | - | - |
| sc_partial | 4 of 6 | 3 of 6 | - | 4 of 6 | 3 of 6 | 4 of 6 | 6 of 6 | 0 of 6 | 0 of 6 | - | - |
| sc_absent | 5 of 6 | 5 of 6 | - | 4 of 6 | 5 of 6 | 6 of 6 | 2 of 6 | 0 of 6 | 0 of 6 | - | - |
| sc_offkb | 5 of 6 | 4 of 6 | - | 6 of 6 | 5 of 6 | 6 of 6 | 6 of 6 | 1 of 6 | 1 of 6 | - | - |
| sc_stale | 1 of 6 | 1 of 6 | - | 1 of 6 | 2 of 6 | 1 of 6 | 6 of 6 | - | - | - | - |
| all | 395 of 450 -> 126 of 150 -> 152 of 180 | 398 of 450 -> 127 of 150 -> 152 of 180 | 218 of 382 -> 72 of 150 | 268 of 300 -> 128 of 150 -> 158 of 180 | 236 of 255 -> 134 of 150 -> 158 of 180 | 391 of 450 -> 138 of 150 -> 165 of 180 | 396 of 450 -> 128 of 150 -> 168 of 180 | 19 of 58 -> 33 of 62 -> 45 of 86 | 16 of 58 -> 35 of 62 -> 43 of 86 | 132 of 150 | 135 of 150 |
<!-- /bench -->

All kinds, by arm (the fixed share is the part of a run's input that is there before the question):
<!-- bench:table pool metrics=start_ctx,input,fixed_share,tokens_per_right,fully_right,checks,cost,wall_s cases=all -->
| case | arm | start_ctx | input | fixed_share | tokens_per_right | fully_right | checks | cost | wall_s |
|---|---|---|---|---|---|---|---|---|---|
| all | haiku-5-5:low | 33,027 -> 32,800 -> 33,284 (+1%) | 106,653 -> 109,415 -> 102,879 (-6%) | 31.0% -> 30.0% -> 32.4% (+8%) | 58,872 -> 69,260 -> 66,390 (-4%) | 395 of 450 -> 126 of 150 -> 152 of 180 | 432/492 -> 137/164 -> 176/206 | $0.007 -> $0.008 -> $0.008 (+9%) | 14 s -> 13 s -> 17 s (+30%) |
| all | haiku-5-5:default | 33,065 -> 32,872 -> 33,115 (+1%) | 125,329 -> 125,445 -> 119,269 (-5%) | 26.4% -> 26.2% -> 27.8% (+6%) | 64,928 -> 73,323 -> 66,482 (-9%) | 398 of 450 -> 127 of 150 -> 152 of 180 | 436/492 -> 139/164 -> 176/206 | $0.008 -> $0.009 -> $0.009 (-1%) | 16 s -> 16 s -> 20 s (+23%) |
| all | haiku-4-5 | 27,518 -> 27,518 (-0%) | 81,491 -> 72,397 (-11%) | 33.8% -> 38.0% (+13%) | 50,787 -> 58,742 (+16%) | 218 of 382 -> 72 of 150 | 247/424 -> 81/164 | $0.035 -> $0.034 (-4%) | 17 s -> 17 s (-3%) |
| all | sonnet-5-5:low | 32,324 -> 31,964 -> 32,385 (+1%) | 86,237 -> 84,198 -> 92,634 (+10%) | 37.5% -> 38.0% -> 35.0% (-8%) | 50,665 -> 59,573 -> 54,724 (-8%) | 268 of 300 -> 128 of 150 -> 158 of 180 | 292/328 -> 138/164 -> 182/206 | $0.106 -> $0.111 -> $0.107 (-4%) | 17 s -> 14 s -> 17 s (+22%) |
| all | sonnet-5-5:default | 32,693 -> 31,981 -> 32,489 (+2%) | 150,940 -> 140,442 -> 157,122 (+12%) | 21.7% -> 22.8% -> 20.7% (-9%) | 60,167 -> 72,010 -> 66,451 (-8%) | 236 of 255 -> 134 of 150 -> 158 of 180 | 262/283 -> 147/164 -> 184/206 | $0.145 -> $0.150 -> $0.143 (-5%) | 30 s -> 25 s -> 30 s (+20%) |
| all | router | 9,393 -> 7,587 -> 7,473 (-1%) | 17,290 -> 19,761 -> 21,941 (+11%) | 54.3% -> 38.4% -> 34.1% (-11%) | 8,828 -> 17,544 -> 18,197 (+4%) | 391 of 450 -> 138 of 150 -> 165 of 180 | 419/492 -> 149/164 -> 189/206 | $0.020 -> $0.024 -> $0.026 (+9%) | 14 s -> 13 s -> 13 s (+3%) |
| all | hook | 0 -> 0 -> 0 | 0 -> 0 -> 0 | - | 0 -> 0 -> 0 | 396 of 450 -> 128 of 150 -> 168 of 180 | 429/492 -> 139/164 -> 194/206 | $0.000 -> $0.000 -> $0.000 | 0 s -> 0 s -> 0 s (+81%) |
| all | web-haiku-5-5 | 15,926 -> 15,924 -> 15,925 (+0%) | 87,137 -> 78,915 -> 86,397 (+9%) | 18.3% -> 20.2% -> 18.4% (-9%) | 97,389 -> 54,988 -> 56,365 (+3%) | 19 of 58 -> 33 of 62 -> 45 of 86 | 29/68 -> 37/67 -> 51/97 | $0.031 -> $0.029 -> $0.030 (+5%) | 27 s -> 25 s -> 26 s (+6%) |
| all | web-sonnet-5-5 | 15,148 -> 15,146 -> 15,147 (+0%) | 64,017 -> 62,737 -> 67,927 (+8%) | 23.7% -> 24.1% -> 22.3% (-8%) | 72,802 -> 36,122 -> 38,164 (+6%) | 16 of 58 -> 35 of 62 -> 43 of 86 | 25/68 -> 39/67 -> 49/97 | $0.073 -> $0.066 -> $0.070 (+5%) | 22 s -> 21 s -> 22 s (+1%) |
| all | haiku-5-5:low/session | 49,172 -> 47,823 (-3%) | 149,647 -> 137,855 (-8%) | 32.9% -> 34.7% (+6%) | 37,451 -> 35,330 (-6%) | 49 of 60 -> 128 of 150 | 65/80 -> 138/164 | $0.004 -> $0.004 (+13%) | 13 s -> 12 s (-5%) |
| all | haiku-5-5:default/session | 54,722 -> 49,740 (-9%) | 205,356 -> 164,599 (-20%) | 26.6% -> 30.2% (+13%) | 45,435 -> 41,231 (-9%) | 54 of 60 -> 127 of 150 | 71/80 -> 139/164 | $0.006 -> $0.006 (-0%) | 15 s -> 14 s (-10%) |
| all | sonnet-5-5:low/session | 43,224 -> 42,317 (-2%) | 113,193 -> 107,972 (-5%) | 38.2% -> 39.2% (+3%) | 21,568 -> 27,582 (+28%) | 55 of 60 -> 132 of 150 | 73/80 -> 144/164 | $0.058 -> $0.058 (-0%) | 15 s -> 13 s (-12%) |
| all | sonnet-5-5:default/session | 51,811 -> 52,446 (+1%) | 203,432 -> 211,545 (+4%) | 25.5% -> 24.8% (-3%) | 33,482 -> 49,012 (+46%) | 53 of 60 -> 128 of 150 | 71/80 -> 141/164 | $0.095 -> $0.105 (+10%) | 22 s -> 25 s (+13%) |
| all | opus-5-5:low | 32,154 | 91,950 | 35.0% | 55,882 | 132 of 150 | 144/164 | $0.217 | 18 s |
| all | opus-5-5:default | 32,256 | 110,976 | 29.1% | 56,816 | 135 of 150 | 149/164 | $0.232 | 22 s |
<!-- /bench -->

The effort levels, `low` against `default` (the change of `low` from `default` in brackets):
<!-- bench:effort pool metrics=tokens_per_right,fixed_share,fully_right,cost cases=all -->
| case | model | tokens_per_right low | tokens_per_right default | fixed_share low | fixed_share default | fully_right low | fully_right default | cost low | cost default |
|---|---|---|---|---|---|---|---|---|---|
| all | haiku-5-5 | 66,390 (-0%) | 66,482 | 32.4% (+17%) | 27.8% | 152 of 180 | 152 of 180 | $0.008 (-4%) | $0.009 |
| all | sonnet-5-5 | 54,724 (-18%) | 66,451 | 35.0% (+69%) | 20.7% | 158 of 180 | 158 of 180 | $0.107 (-25%) | $0.143 |
| all | haiku-4-5 (no effort setting) | - | 58,742 | - | 38.0% | - | 72 of 150 | - | $0.034 |
| all | opus-5-5 | 55,882 (-2%) | 56,816 | 35.0% (+20%) | 29.1% | 132 of 150 | 135 of 150 | $0.217 (-6%) | $0.232 |
<!-- /bench -->

Haiku 5.5 against Haiku 4.5 at the default level:
<!-- bench:table pool metrics=cost,wall_s,input,out,tool_calls,checks,fully_right,tokens_per_right cases=all arms=haiku-5-5:default,haiku-4-5 -->
| case | arm | cost | wall_s | input | out | tool_calls | checks | fully_right | tokens_per_right |
|---|---|---|---|---|---|---|---|---|---|
| all | haiku-5-5:default | $0.008 -> $0.009 -> $0.009 (-1%) | 16 s -> 16 s -> 20 s (+23%) | 125,329 -> 125,445 -> 119,269 (-5%) | 24 -> 2,027 -> 2,073 (+2%) | 2.7 -> 2.7 -> 2.5 (-5%) | 436/492 -> 139/164 -> 176/206 | 398 of 450 -> 127 of 150 -> 152 of 180 | 64,928 -> 73,323 -> 66,482 (-9%) |
| all | haiku-4-5 | $0.035 -> $0.034 (-4%) | 17 s -> 17 s (-3%) | 81,491 -> 72,397 (-11%) | 7 -> 1,050 (+15257%) | 1.7 -> 1.5 (-14%) | 247/424 -> 81/164 | 218 of 382 -> 72 of 150 | 50,787 -> 58,742 (+16%) |
<!-- /bench -->

The session shape, by position of the question in its session:
<!-- bench:session pool -->
| position | haiku-5-5:low/session marginal_input | haiku-5-5:low/session cache_read_share | haiku-5-5:default/session marginal_input | haiku-5-5:default/session cache_read_share | sonnet-5-5:low/session marginal_input | sonnet-5-5:low/session cache_read_share | sonnet-5-5:default/session marginal_input | sonnet-5-5:default/session cache_read_share |
|---|---|---|---|---|---|---|---|---|
| 1 | 36,514 -> 36,049 (-1%) | 75.2% -> 74.5% (-1%) | 38,605 -> 36,745 (-5%) | 80.6% -> 76.9% (-5%) | 34,912 -> 34,552 (-1%) | 67.1% -> 71.6% (+7%) | 37,459 -> 38,182 (+2%) | 80.9% -> 78.5% (-3%) |
| 2 | 11,668 -> 7,258 (-38%) | 92.3% -> 94.6% (+2%) | 12,919 -> 8,179 (-37%) | 93.1% -> 94.6% (+2%) | 5,492 -> 4,774 (-13%) | 94.8% -> 94.8% (-0%) | 11,292 -> 9,467 (-16%) | 94.4% -> 94.5% (+0%) |
| 3 | 4,525 -> 7,018 (+55%) | 97.2% -> 95.3% (-2%) | 6,992 -> 7,594 (+9%) | 96.1% -> 95.3% (-1%) | 3,980 -> 3,657 (-8%) | 97.1% -> 96.3% (-1%) | 6,165 -> 7,444 (+21%) | 97.1% -> 96.3% (-1%) |
| 4 | 4,022 -> 5,157 (+28%) | 96.9% -> 96.6% (-0%) | 8,122 -> 5,439 (-33%) | 96.3% -> 96.8% (+1%) | 4,556 -> 3,868 (-15%) | 95.2% -> 96.8% (+2%) | 7,100 -> 6,713 (-5%) | 96.2% -> 97.2% (+1%) |
| 5 | 5,070 -> 6,448 (+27%) | 97.4% -> 96.1% (-1%) | 7,235 -> 8,473 (+17%) | 97.0% -> 95.5% (-2%) | 4,293 -> 5,487 (+28%) | 96.5% -> 95.9% (-1%) | 6,513 -> 10,129 (+56%) | 97.1% -> 96.2% (-1%) |
| 6 | 3,227 -> 4,259 (+32%) | 98.2% -> 97.1% (-1%) | 4,128 -> 7,123 (+73%) | 98.5% -> 96.8% (-2%) | 3,128 -> 3,938 (+26%) | 98.0% -> 97.0% (-1%) | 5,876 -> 7,860 (+34%) | 97.9% -> 97.2% (-1%) |
<!-- /bench -->

What it shows (the record of 2026-10-09, Claude Code 2.1.293; a run is right when all its checks pass):

*How the differences are judged.* Between two arms, over the rows both ran, a difference is a conclusion only when its 95% interval, from 2,000 resamples of the pool's rows (a row's runs of both arms stay together), excludes 0: its spread is below it. Otherwise it is written "within the spread". Intervals are in brackets. Reps of a row are not independent runs of a kind, so a kind of 1-5 rows (`multi`, `synthesis`, `csv_fact`, `near_miss`, `count`, `cites`, `decision`, `conflict`, `false_good`, `snippet`, `gap`) has no conclusion of its own beyond what is written below. The checks also count: those of `multi` and some of `csv_fact` and `fact` name a kb article, and those of `offkb` look for "the kb does not cover it" wording, which a bare web session cannot give. Every pair below is over the rows both arm labels ran, all 150 unless stated.

- **Opus 5.5 is right as often as Sonnet 5.5 and Haiku 5.5, with fewer tokens per right answer, at the highest cost.** These are the full Opus arm's cells (all 150 rows); a record whose Opus arm ran the sanity subset gives 10 rows and no such comparison ("Opus cells" above). At the default level it is right in 90.0% of runs against 89.3% for Sonnet 5.5 (+0.7 points [-4.0, +5.3]) and 84.7% for Haiku 5.5 (+5.3 [-0.7, +10.7]): both within the spread. It spends 56,816 tokens of effective input per right answer against 72,010 (-15,195 [-20,096, -10,625]) and 73,323 (-16,508 [-23,255, -10,557]), reading less per run (110,976 against 140,442 and 125,445). A run costs $0.232 against $0.150 and $0.009. At `low` against Sonnet 5.5 at `low`: right 88.0% against 85.3% (+2.7 [-1.3, +6.7], within the spread), 55,882 against 59,573 tokens per right answer (-3,692 [-7,386, -250]), $0.218 against $0.111.
- **The router takes the fewest tokens to a right answer; in dollars it is not the cheapest.** Its reader is Haiku 5.5 and its researcher Sonnet 5.5. 17,544 tokens of effective input per right answer (15,236-20,250 by the interval of its cell) against 73,323 for Haiku 5.5 at the default level (67,217-80,635) and 56,816 for Opus 5.5 (53,456-60,702): the intervals do not overlap. Right in 92.0% of runs (138 of 150; 87.3%-96.0%) against 84.7% for Haiku 5.5 (78.7%-90.0%), 89.3% for Sonnet 5.5 (84.0%-94.0%) and 90.0% for Opus 5.5 (84.7%-94.7%): the intervals overlap, and the pairs' differences were not computed. A router run costs $0.024 against $0.009 for Haiku 5.5 with the kb. These are the re-recorded rows. The first rows of the record read on Haiku 4.5 and were 14,632 tokens per right answer, right in 82.7% of runs, $0.026 a run; a 1-hour cache write costs $2 per million tokens on Haiku 4.5 against $0.20 on Haiku 5.5 (`kb/public/claude/ci-and-headless.md:88`, `:91`), so their cost does not compare with these (see "The router arm's two readers"). It passed none of the `decision` and `conflict` runs (0 of 2 each), which a tool answers.
- **The hook costs no tokens and its pack carries the checked text in 85.3% of runs** (128 of 150), against 84.7% for Haiku 5.5 at the default level (+0.7 points [-6.7, +8.0]: within the spread). It passed none of the `count`, `decision` and `conflict` runs.
- **The kb arms spend 55,882-73,323 tokens per right answer, and 22.8%-38.0% of a run's input is there before the question.** A run starts at 31,964-32,872 tokens on Haiku 5.5, Sonnet 5.5 and Opus 5.5, 27,518 on Haiku 4.5, 7,587 for the router (9,455 on its first rows, which read on Haiku 4.5) and 15,146-15,924 for the web sessions. Sonnet 5.5 and Haiku 5.5 at the default level differ by 1,313 tokens per right answer (Sonnet fewer, [-8,214, +5,180]) and 4.7 points of right runs (Sonnet more, [-0.7, +10.7]): both within the spread, at $0.150 a run against $0.009. `out`, now the output of every model of the run, is 960-2,966 tokens a run on the kb arms, 1,864 for the router (1,170 on its first rows) and 2,901-5,654 for the web sessions.
- **Effort `low` is cheaper at a rate of right answers within the spread.** Sonnet 5.5: 59,573 against 72,010 tokens per right answer (-12,437 [-17,167, -7,808], -17%), $0.111 against $0.150 a run (-26%), right 85.3% against 89.3% (-4.0 points [-9.3, +0.7]). Haiku 5.5: 69,260 against 73,323 (-4,063 [-8,928, +804], within the spread), $0.008 against $0.009 (-13%), right 84.0% against 84.7% (-0.7 [-5.3, +3.3]). Opus 5.5: 55,882 against 56,816 (-934 [-4,237, +2,280], within the spread), $0.218 against $0.232 (-6% [-$0.022, -$0.007]), right 88.0% against 90.0% (-2.0 [-6.0, +2.0]). The start of the run does not change with the level, so the fixed share rises as the rest of the run shrinks.
- **Haiku 5.5 against Haiku 4.5 at the default level:** Haiku 5.5 is right in 84.7% of runs against 48.0% (+36.7 points [+28.7, +45.3]); on the 20 `heldout` rows 18 against 3, on the 20 `querylog` rows 13 against 1. Haiku 4.5 takes in less input per run (72,397 against 125,445), so it spends fewer tokens per right answer, 58,742 against 73,323 (Haiku 5.5 +14,581 [+4,040, +23,134]); at `low` the difference is within the spread (+10,518 [-221, +19,285]). In dollars Haiku 5.5 is the cheaper, $0.009 a run against $0.034.
- **A bare web session is right far less often on this pool's checks, with fewer tokens per right answer.** On its 62 rows, web-haiku-5-5 is right in 53.2% of runs against 88.7% for Haiku 5.5 with the kb (-35.5 points [-48.4, -22.6]) and web-sonnet-5-5 in 56.5% against 88.7% for Sonnet 5.5 (-32.3 [-45.2, -19.4]), at 54,988 and 36,122 tokens per right answer against 72,259 and 72,676 (-17,271 [-29,843, -1,342], -36,555 [-47,089, -24,824]). On the `fact` rows they are right in 25 and 26 of 33 runs, against 29 and 28 for the kb arms; on `offkb`, which asks for "the kb does not cover it" wording, in 0 and 1 of 15, and on `multi`, whose checks name a kb article, in none. A web-sonnet-5-5 run costs $0.066 against $0.153 for the kb arm on these rows; a web-haiku-5-5 run $0.029 against $0.010.
- **In a session the fixed context is paid once.** The first question adds 34,552-38,182 tokens to the prompt (`marginal_input`), the later ones 3,657-10,129 on average per position; the cache read share is 71.6%-78.5% at the first position and 94.5%-97.2% after it. Over the whole pool (25 sessions per label), a session takes fewer tokens per right answer than fresh sessions on the same rows: 35,330 against 69,260 for `haiku-5-5:low` (-33,930 [-40,130, -28,251]), 41,231 against 73,323 for `haiku-5-5:default` (-32,092 [-38,992, -25,928]), 27,582 against 59,573 for `sonnet-5-5:low` (-31,991 [-36,235, -27,989]) and 49,012 against 72,010 for `sonnet-5-5:default` (-22,998 [-27,713, -18,266]), at rates of right answers within the spread (85.3% against 84.0%, 84.7% against 84.7%, 88.0% against 85.3%, 85.3% against 89.3%, the last at its edge: -4.0 [-8.7, +0.0]). A question costs $0.004 against $0.008, $0.006 against $0.009, $0.058 against $0.111 and $0.105 against $0.150. Mean `cost` does not rise with the position (`pool verify` (d)).
- **Against the record of 2026-10-08, on the 130 rows whose checks did not change** (111 for Haiku 4.5 and Sonnet 5.5 at the default level, whose cells then lacked rows; the fresh labels only, since the session labels then covered 30 rows): the rate of right answers is within the spread for every arm (Haiku 5.5 87.7% against 88.7% at `low` and 89.2% against 89.0% at the default level, Haiku 4.5 56.8% against 56.8%, Sonnet 5.5 90.0% against 90.0% and 94.6% against 91.9%; the hook, which starts no model, 88.5% both times), and so is the input per run. The router is left out of this comparison: its rows were re-recorded on a different reader (Haiku 5.5 now, Haiku 4.5 then), and the 130-row subset was not computed for them. Over all rows its table line reads $0.020 -> $0.024 a run, 86.9% -> 92.0% right (391 of 450 -> 138 of 150) and 8,828 -> 17,544 tokens per right answer; the first rows of 2026-10-09, still on Haiku 4.5, were $0.026 and 14,632, and wrote more cache than the record before (5,424 against 3,295 tokens a run over all rows). The billed cost per run of the other arms moves by less than half a cent. The three `querylog` rows no arm passed then (`BP-9b5aab96`, `BP-ab7a8cc2`, and `BP-36864ffb`, replaced by `BP-b58a1dea`) now check the article that answers them, and 11 or 12 of the 15 arm labels passed each in the first run of the record (the router's re-run rows are not counted in that). The web arms' all-kinds rate rose (19 and 16 of 58 runs right then, 33 and 35 of 62 now) because their kinds now include `fact` and fewer of their checks name a kb path; on the rows both records ran it is within the spread.

*Rows no arm passed (2026-10-09).* Four rows, all of one source: `BP-ff6bf9a2` (`fact`, "What happens to the Autopilot device record when the motherboard is replaced?") and its three variants. Their check, new in this record, names `autopilot/lifecycle.md:13`, a line on the two Entra device objects of a hybrid join, which does not answer the question; BG-zcw5yqch is to correct it. Three more rows were passed by no kb arm: `BP-0e42ddeb` (`fact`) and `BP-1e5f5182` (`querylog`) by the hook alone, `BP-97f8027d` (`variant_keyword`) by the hook, the router and the Haiku 5.5 sessions. These row lists are those of the record's first run; the router's re-recorded rows (138 of 150 right) were not read per row, so a row listed here as passed by no arm may be passed by the router now.

*What the numbers of 2026-10-09 do not support.* A ranking of the arms on any kind of 1-5 rows, each of which has one run per row and arm label; a ranking of Opus 5.5, Sonnet 5.5 and Haiku 5.5 by their rate of right answers, all within the spread at both levels; the four rows of the Autopilot motherboard source (BG-zcw5yqch); the pairs' differences between the re-recorded router and the other arms (only the cells' intervals are read here); and a split of the router's cost by route, which the cells do not give. The router's dearer runs than the record before (2026-10-08) are not the reader's model: the rows of 2026-10-08 and the first rows of this record read on Haiku 4.5, and the rows on Haiku 5.5 still cost $0.024 a run against $0.020 then. What the record shows is more cache written a run (3,295 tokens then, 5,424 on the first rows, 7,453 on the re-recorded ones); why a router run writes more is not read here.

What the record of 2026-10-08 showed (by its own counts, which the record of 2026-10-09 changed: its `out` is a partial count, a split route of the router is scored on the researcher's answer alone, every cache write is weighted at the five-minute rate, and its Haiku 4.5 and Sonnet 5.5 default cells lack 22 rows):

- **The router takes the fewest tokens to a right answer, seven times fewer; in dollars it is not the cheapest.** Its reader runs on Haiku 4.5, so a router run costs $0.020 against $0.008 for Haiku 5.5 with the kb, and the hook costs nothing. 8,828 tokens of effective input per right answer against 64,928 for Haiku 5.5 at the default level (-56,100 [-60,988, -51,867]) and 60,167 for Sonnet 5.5 at the default level (-51,056 [-56,137, -46,533], on the 128 rows both ran), at 86.9% of runs right against 88.4% (-1.6 points [-6.4, +3.3]) and, on those 128 rows, 89.1% against 92.5% (-3.5 points [-8.8, +1.7]): both within the spread. It is cheaper on every kind of 10 or more rows (`fact`, `heldout`, `offkb`, `querylog`, the three variants). On `gap` (5 rows) it passed 4 of 15 runs against 12 of 15 for Haiku 5.5, within the spread. It passed none of the 6 `decision` and 6 `conflict` runs, which ask for a record or a join that a tool answers.
- **The hook costs no tokens and its pack carries the checked text in 88.0% of runs** (396 of 450), against 88.4% for Haiku 5.5 at the default level (-0.4 points [-5.8, +5.3]: within the spread). The pack is not an answer: the hook passed none of the 9 `count`, 6 `decision` and 6 `conflict` runs, which need a count or a join, and 6 of 15 of `gap`.
- **The kb arms (Haiku 5.5, Sonnet 5.5) spend 50,665-64,928 tokens per right answer, and 21.7%-37.5% of a run's input is there before the question.** The start of a run is 33,027-33,065 tokens on Haiku 5.5, 32,324-32,693 on Sonnet 5.5, 27,518 on Haiku 4.5, 9,393 for the router and 15,148-15,926 for the web sessions; the fixed share of the input is 21.7%-37.5% for the kb arms, 33.8% for Haiku 4.5 and 54.3% for the router, whose input is 17,290 in all. Haiku 5.5 and Sonnet 5.5 at the default level differ by 3,258 tokens per right answer (Sonnet fewer, [-7,850, +1,214]: within the spread) and 1.1 points of right runs (within the spread), at $0.145 a run against $0.008.
- **Effort `low` is cheaper per right answer at the same rate of right answers.** Haiku 5.5: 58,872 against 64,928 tokens (-6,056 [-9,390, -2,771], -9%), $0.0072 against $0.0082 a run (-13%), right 87.8% against 88.4% (-0.7 points [-3.3, +2.2]). Sonnet 5.5, on the 128 rows both levels ran: 48,891 against 60,167 (-11,275 [-15,821, -7,253], -19%), right 93.0% against 92.5% (+0.4 points [-2.3, +3.2]); the effort table's -16% and -27% for Sonnet compare `low` over 150 rows with `default` over 128, so read the paired figure. The start of the run does not change (33,027 against 33,065; 32,324 against 32,693), so the fixed share rises because the rest of the run shrinks: +4.6 points for Haiku 5.5 [+3.1, +6.1], +15.9 points for Sonnet 5.5 [+12.8, +19.0]. By kind the saving is not uniform: for Haiku 5.5 `low` is dearer per right answer on `heldout` (+7,171 [+323, +15,411]) and cheaper on `fact`, `offkb`, `querylog` and `variant_typo`; on `offkb` Haiku 5.5 at `low` is right more often (41 of 45 against 32 of 45, +20.0 points [+8.9, +31.1]).
- **Haiku 5.5 against Haiku 4.5 at the default level (the 128 rows both ran):** Haiku 5.5 is right in 91.4% of runs against 57.1% (+34.3 points [+27.1, +41.4]); on the 20 `heldout` rows it is right 54 of 60 against 6 of 60. It reads more per run, 57,974 effective input tokens against 28,983 (+28,991 [+25,315, +32,688]), with 2.7 tool calls against 1.7, so per right answer Haiku 4.5 is cheaper in tokens, 50,787 against 63,425 (Haiku 5.5 +12,638 [+4,569, +19,648]): it reads half as much per run, which outweighs being right less often. In dollars Haiku 5.5 is the cheaper, $0.008 a run against $0.035 (the list prices in `bench_core.py` are $0.10 / $0.50 per million tokens up to a 100k prompt against $1 / $5; the two cells cover 150 and 128 rows). At `low`, Haiku 5.5's tokens per right answer against Haiku 4.5's are within the spread (+7,425 [-435, +13,784]). The `haiku-4-5` cell is short (382 of 450 runs, no `querylog` rows), so the table's all-kinds figures for it are over fewer rows than the others.
- **A bare web session answers with less input and far fewer right answers on this pool's checks.** On the 29 rows both ran, per run web-haiku-5-5 reads 31,903 tokens against 66,486 for the kb arm (-34,583 [-41,922, -27,088]) and web-sonnet-5-5 20,083 against 64,727 (-44,643 [-51,500, -37,370]); right in 32.8% and 27.6% of runs against 79.3% and 84.5% (-46.6 points [-60.3, -32.2], -56.9 points [-74.1, -37.9]), partly because the web sessions cannot name a kb article or say "the kb does not cover it" (`multi` 0 of 8, `offkb` 4 of 60). Their tokens per right answer, 97,389 and 72,802, are within the spread of the kb arms' on the same rows (+13,559 [-13,599, +83,804], -3,814 [-30,280, +70,637]); the kinds whose checks name content (`synthesis` 1 row, `snippet` 5, `false_good` 2) are too few to compare. The router on the same rows: 16,436 tokens per right answer, right 92.0%.
- **In a session the fixed context is paid once, and the questions after the first cost a fraction of it.** The first question of a session adds 34,912-38,605 tokens to the prompt (`marginal_input`), the later ones 3,128-12,919 on average per position; pooled over positions 2-6 that is 5,702 (`haiku-5-5:low`), 7,879 (`haiku-5-5:default`), 4,290 (`sonnet-5-5:low`) and 7,389 (`sonnet-5-5:default`), 6.4, 4.9, 8.1 and 5.1 times less. The lowest first-question value of the four labels (33,053) is above the highest value at any later position (31,473), so the difference is larger than the spread; the position means of 2-6 vary less than the sessions do, so no order among them is concluded. The cache read share is 67.1%-80.9% at the first position and 92.3%-98.5% after it. Per right answer a session takes less than fresh sessions on the same 30 rows: 37,451 against 60,874 tokens for `haiku-5-5:low` ([-31,757, -13,972]), 45,435 against 63,838 for `haiku-5-5:default` ([-27,323, -9,374]), 21,568 against 53,038 for `sonnet-5-5:low` ([-39,291, -24,310]) and 33,482 against 63,796 for `sonnet-5-5:default` ([-39,636, -22,261]), at rates of right answers within the spread (81.7% against 86.7%, 90.0% against 91.1%, 91.7% against 88.3%, 88.3% against 86.7%). A question in a session costs less too: $0.004 against $0.006 (Haiku 5.5 at `low`), $0.006 against $0.007, $0.058 against $0.108 (Sonnet 5.5 at `low`) and $0.095 against $0.142. The table's `start_ctx` and fixed share for the session labels are not the fresh arms': each question's `start_ctx` there is the whole prompt of its first request, history included.

*Rows no arm passed (2026-10-08).* Of the 150 rows, three were not passed by any run of any arm at any rep: `BP-36864ffb`, `BP-9b5aab96` and `BP-ab7a8cc2`, all `querylog` rows (14 runs each: `haiku-5-5` at both levels, the router and the hook at 3 reps, `sonnet-5-5:low` at 2). The runs answered from another article than the one the row's check names: `BP-36864ffb` from `_self/backlog.md` (8 runs) and `agents/agent-planning-and-done.md` (4), `BP-9b5aab96` from `agents/test-suite-size-and-agent-overengineering.md` (12 runs), `BP-ab7a8cc2` from `claude/powershell-tool.md` (11) and `en/permissions.md` (7). Whether a check names the wrong article or the runs missed the right one was for a review of the rows: before the next record, two of them got a check of the article that answers them and the third was replaced, and 11 or 12 of the 15 arm labels passed each then. Two more rows, a `fact` and a `querylog` row, were passed only by the router, the hook or a web arm, by none of the kb arms.

*What the numbers of 2026-10-08 do not support.* A ranking of the arms on any kind of 1-5 rows; the effort and arm figures of the kinds with a single row; Sonnet 5.5 at the default level and Haiku 4.5 on the 22 rows they lack (the 20 `querylog` rows among them); the web arms' right answers against the kb's, whose checks name kb articles; anything about Opus 5.5 (no arm), and about the output tokens: the pool's `out` column counts 7 to 24 tokens a run, far below what the cost implies, and is not used here. The record of 2026-10-09 has an Opus arm and counts `out` in full.

## Since the records of 2026-10-08 and 2026-10-09

What moved between the pool records of 2026-10-08 (150 rows, three reps, Claude Code 2.1.293) and 2026-10-09 (the same 150 rows, one rep, the first with intervals) and the record of 2026-10-12 (180 rows: those 150 and the 30 scenario rows; Claude Code 2.1.296; commit `541378c`, which holds every change below), and in the other scenarios' records of 2026-10-12 (commit `9dabbdb`, nothing since changes what they read). **Beyond** means the new figure lies outside the 95% interval that the 2026-10-09 record's cell holds; **within** means inside it. A kind of 2-5 rows has no ranking of its own and its interval is wide, so a moved kind cell shows a direction, not a size; a scenario with one run per cell or with no earlier record has no interval and is marked so. Figures marked *derived* are computed here from the results file's cells, not read from a cell: a cell's `tokens_per_right` times its right runs is the effective input of all its runs, so the 150 rows the earlier record asked are the all-kinds cell less the five scenario kinds' cells; they carry no interval. Sonnet 5.5's effective input of 2026-10-12 weights a cache read at $0.10 where the earlier records' weighted $0.20, so its tokens per right answer do not compare across the records (its raw `input` does).

Where a figure moves in a scenario that measures many changes together, the change behind it was found by running the free part of the scenario on the tree of each change's merge commit in a throwaway clone (the cold `pack` of the tool-speed scenario at each commit, five runs each, and the pool's hook arm, which starts no model, with one change undone). A change no such run moves is marked *no figure moved*.

**What landed, which scenario measures it, and what moved**

| change | measured by | figure moved | against the previous record's interval |
|---|---|---|---|
| The kind router and RRF fusion: `pack`, `kb_pack`, `kb_ask.py` and the `kb:` hook answer a count, a decision, a conflict and a gap question from the tool that holds the answer (ST-b27c527d) | pool, kinds `count`, `decision`, `conflict`, `gap`, arms `hook` and `router`; the hook arm run again free on the change's commit (12 of 12 right) | hook `count` 0 of 3 -> 3 of 3, `decision` 0 of 2 -> 2 of 2, `conflict` 0 of 2 -> 2 of 2, `gap` 2 of 5 -> 5 of 5; router `decision` 0 of 2 -> 2 of 2, `conflict` 0 of 2 -> 2 of 2, `gap` 27,833 -> 0 tokens per right answer (the ledger answers, no model reads); Sonnet 5.5 at `low` `decision` and `conflict` 0 of 2 -> 2 of 2, Haiku 5.5 `conflict` 0 of 2 -> 1 of 2 at both levels, and Haiku 5.5 at `low` `gap` 5 of 5 -> 4 of 5, the one cell of these four kinds that fell; the hook over all kinds 85.3% (128 of 150) -> 93.3% (168 of 180), over the earlier 150 rows 142 of 150 (94.7%, derived): 14 more rows right than the 128 of 2026-10-09, 10 of them in the router's four kinds (`count` 3, `decision` 2, `conflict` 2, `gap` 3) and the other 4 in kinds the router does not route, `fact` 29 of 33 -> 30 of 33 and one row each of `variant_keyword` 9 of 10 -> 10 of 10, `variant_sentence` 9 of 10 -> 10 of 10 and `variant_typo` 8 of 10 -> 9 of 10 | beyond for the hook's four kinds (intervals 0%-0%, and 0%-80% for `gap`), the router's `decision` and `conflict` (0%-0%) and `gap` tokens (18,340-36,069), the Sonnet 5.5 `low` and Haiku 5.5 `conflict` cells named, Haiku 5.5 at `low` `gap` against the change (4 of 5 lies below its record cell's interval of 100%-100%, one run in five), and the hook over all kinds (79.3%-90.7%); within for the router's `count` and `gap` right shares, for the hook's 4 rows outside the router's kinds (`fact` 75.8%-97.0%, each `variant_*` cell 70%-100% or 50%-100%) and for the other kb cells of the router's kinds. The change alone moves the cold `pack` 55.8 -> 56.0 ms (within the spread of about 1 ms) |
| The `check:` line on a `good` pack whose top articles are scattered and weakly scored, threshold 15 (ST-iyrixezt) | verdict (the off-kb list and the eval set); pool, kinds `offkb`, `false_good` and `sc_absent`, arms `hook` and the kb arms | the note flags 8 of the off-kb list's 11 `good` and 3 of 233 eval `good`; it is on 9 of the hook arm's 180 packs (7 on rows whose checks the pack met, 2 on `offkb` rows it did not meet) and on none of the four `sc_absent` rows built as false goods; hook `offkb` 13 of 15 -> 13 of 15, `false_good` 1 of 2 -> 1 of 2, the kb arms' `offkb` 12-15 of 15 against 13-15 and `false_good` 2 of 2 against 1-2; cold `pack` 56.0 -> 57.4 ms | within for every `offkb` and `false_good` cell (the narrowest 67%-100% and 0%-100%); the counts of the verdict scenario are deterministic and have no interval; the cold `pack` step is at the edge of its spread. The note changes no verdict, and the pool's false goods are not flagged by it |
| The gap expert leaves a broad question to the pack unless the question holds a third of the gap title's weight (BG-zpcqo7qt) | pool, the hook arm run again free with the change undone in a throwaway clone | 168 of 180 with and without it, and no row's answer or checks differ: *no figure moved*; the pool's `gap` rows ask a gap's own missing fact, never a broad question the kb answers, which is what the change corrects | within (nothing moved); no scenario row asks the case the change is for |
| The off-kb list keeps no question the kb answers; the eval refuses a row that is both answered and off-kb (ST-efyc4jiw) | verdict, the off-kb list's verdicts | 15 `good` of 106 questions -> 11 of 103, `weak` 48 -> 48, `none` 43 -> 44; the three removed questions were three of the 15 `good`, so the 103 left read 12 `good` before and 11 now, and one `good` of the list became `none` since (not attributed here) | deterministic counts of one record each, no interval. The pool's `offkb` kind, whose rows are drawn from the list, is within the spread for every arm (see the scatter row) |
| Every pack prints an offline freshness stamp per cited source and marks a fact line that is unanchored or older than its source's change (ST-ebn65qen) | tool-speed (cold `pack` and the `kb:` hook), verdict (mean pack size), pool kind `sc_stale` | cold `pack` 56.8 -> 110.2 ms at the commit that merged it and 56.0 -> 110.1 ms between the records, the `kb:` hook 59.4 -> 111.4 ms (a warm in-process `pack` 3.1 -> 3.6 ms, 2026-10-09 against 2026-10-12); the eval set's mean pack 2,525 -> 2,699 characters (+6.9% against 2026-10-08; the item's bound, 2,730, is met); 125 of the hook arm's 180 packs carry an `[unanchored]` mark; `sc_stale`: hook 6 of 6, kb arms 1-2 of 6, but the hook's check is also met by the article header's retrieved date, so a pack from the tree before the stamp passes it too (BG-chs2di4p) | beyond for the cold `pack` and the hook (the cell's 5 runs lie within 3 ms of each other, 56.0 ms before); the `sc_stale` figures are of one record and do not isolate the stamp |
| Each source has a freshness lifetime from its own change history, and a lookup revalidates a cited source only past it (ST-jqwqdj2g) | the pool's `sc_stale` rows are chosen by it; `fetch.py --status`, offline, reads it for every source; always-on counts the tool list | of the 3,981 sources, 1,340 are pinned (no lifetime), 89 take it from a recorded change history, 1,464 from a fraction of the time since their page date, 1,088 from their provider's default, and 1,445 are past it today; `pool check` finds that 5 of the 6 `sc_stale` rows cite a source past its lifetime and warns that `BP-4edc88f0`'s pack cites none now; the `kb_pack` tool list grows by 114 characters. The pool arms ran with hooks off and their wall time per run did not move on the router's rows (13 s -> 13 s over all rows), so *no figure moved* by revalidation | no earlier record; within for the router's wall time (the cells hold no interval for it) |
| `pack --revalidate` and `kb_pack`'s `revalidate` check only the pack's cited sources live and resolve only the printed lines' anchors (ST-mq7we5r2) | freshness (first record, 2026-10-12, run twice that day); always-on counts the tool list | 387 printed `DOC` lines over 54 questions: 227 (58.7%) current, 15 (3.9%) moved, 9 not found, 134 (34.6%) dated at their source only, 2 not checked; a lookup 3.13 s at the median and 7.88 s at p95, 278 requests, none failed; the `kb_pack` tool list grows by 268 characters | no earlier record of the scenario, so no interval; the earlier run of the day, over 310 lines, read 62.3% current and 30.6% dated at their source only |
| The census and refresh read the lookups' cached revalidations as hints (ST-f2n2h22c) | none: no scenario runs the census, and the hints count appears in a census's summary | no figure; no cached revalidation existed before ST-mq7we5r2, so there is no earlier state to compare | not measured |
| The plugin ships the sprint, item and backlog skills and the worker agent (TK-p7ajxp72) | always-on (the plugin's added input); host-lookups | the plugin adds 2,339 input tokens against 1,818 on 2026-10-08 (+521); about 257 of them are the four new descriptions (1,028 characters at four per token, an estimate) and about 95 the `kb_pack` tool list's growth (the two rows above), the rest not attributed; host-lookups: six tasks 352k -> 388k input in the host (+10%) at 18.7k -> 19.3k fixed context, turns 17 -> 18, one run each | beyond the spread of the 2026-10-08 and 2026-10-12 cells of always-on: the two records' cells without the plugin differ by 230 tokens (19,754, 19,524) and with it by 291 (21,572, 21,863; Claude Code 2.1.293 and 2.1.296), so +521 is the fall of the baseline (230) and the rise of the plugin's cell (291) together, 1.8 times the larger of the two; a cell's value is the highest of its 4 runs, and the runs whose first request comes before a server connects read about 2.1k lower (with the plugin and hooks off, 3 of 4 on 2026-10-08 and none on 2026-10-12). The attributed 352 tokens (257 and 95) exceed the plugin cell's own rise (291), so they fit the cells only through the baseline's fall; host-lookups has one run per cell and no interval |
| The census's Haiku 5.5 judging and dispatch (ST-jkehwsu4, ST-jlezjp6k, ST-zdfghdlb) | measured by SP-yojt6y7v on 2026-10-11 in `kb/_self/reports/fact-diff.md`; **not re-run here** | judging steps: false confirms 3 against 3 on both, agreement +7.2 points (judge) and +4.4 points (checker) over Sonnet 5.5 and Opus 5.5 at about a tenth and a nineteenth of the spend, so Haiku 5.5 is their default; dispatch of phase-2 groups: usable runs 18 against 21 and agreement 21.9% against 46.5%, so `census.DISPATCH_MODEL` stays Sonnet 5.5; the orchestrator: agreement 57.1% against 71.4%, one run each | no pool figure moves: the census is no pool arm |
| The research of FSMO role transfer and seizure, DHCP failover and AG automatic seeding (ST-wik6j6im) | pool, kind `sc_present` (the three rows FSMO, DHCP and seeding); `rag.py pack` on the tree before and after | each kb arm 6 of 6 on `sc_present`; the pack text holds the row's answer in 3 of 6 rows before the research and 6 of 6 after (below) | no earlier record of the rows, so no interval; the kb arms' cells are 100%-100% |

The cold `pack` step is the one figure of the table that more than one change could own, so it was timed at each merge commit (median of five, in order): 53.4 ms at the tree of the 2026-10-09 record, 55.6 ms at the start of the day's changes, 55.8 ms after ST-efyc4jiw, 56.0 ms after ST-b27c527d, 57.4 ms after ST-iyrixezt, 56.8 ms after BG-zpcqo7qt, **110.2 ms after ST-ebn65qen**, 110.3 ms after ST-mq7we5r2, 111.0 ms after ST-jqwqdj2g, 110.6 ms after ST-f2n2h22c, 111.3 ms after the research and 111.8 ms at the record's tree. The doubling is the freshness stamp's; its cost is per process (a warm in-process `pack` moved by under a millisecond). Wall time per run did not follow it: over the 150 earlier rows the kb arms' wall time rose 8% to 22% (derived), several seconds a run, which two or three cold packs of 54 ms more each cannot make, so the rise is not attributed to a change here.

**Three scenarios whose figures moved over the same window with no row above to own them** (`kb-lookup-agent` and `partial` against their records of 2026-09-28, `retrieval` against that of 2026-10-08; the intervals named are computed here, not read from a cell):

- **`kb-lookup-agent`: the start context rose 37%**, about 4.0k to 5.5k (3,999-4,009 on 2026-09-28, 5,466-5,537 on 2026-10-12), and the input of the whole run from 10.1k-20.9k to 23.4k-23.8k at three requests each. The changes behind it that the kb holds are the agent's file (+163 bytes, 1,560 -> 1,723: the `none` and `route:` rule of 2026-09-29), the preloaded `kb-lookup` skill (+958 bytes, 4,236 -> 5,194: the same rule and the paragraph on decisions) and the six kb tools it lists as `tools/list` serializes them (+633 characters, 5,282 -> 5,915, of which `kb_pack` +504 for its `include_invalidated` and `revalidate` parameters), about 440 tokens at four characters per token, an estimate. The other 1.0k is not attributed: the model behind the `haiku` alias moved from Haiku 4.5 (`claude-haiku-4-5-20251001`) to Haiku 5.5 and Claude Code from 2.1.283 to 2.1.296 between the records, and three runs of one record each, none of which isolates either.
- **`partial`: the comparison with 2026-09-28 spans a model move.** Its `haiku` arm ran on Haiku 4.5 then and Haiku 5.5 now, its `sonnet` arm on Sonnet 5 then and Sonnet 5.5 now (Claude Code 2.1.283 and 2.1.296), one run per cell. The table's cost and input differences (p1 on Haiku $0.107 -> $0.023, on Sonnet $0.370 -> $0.169) are those of two models with their own prices (a 1-hour cache write costs $2 per million tokens on Haiku 4.5 and $0.20 on Haiku 5.5; Sonnet 5.5's cache read counts at $0.10 on Claude Code 2.1.296), and no change of the kb is attributed to them; the checks, 4/4 on p1 and p2 on both arms now against 4/4 on p1 and 3/4 on p2 then, differ by one check on p2.
- **`retrieval`: the untagged content's `line-in-pack` share fell 97% -> 93%** (189 of 194 sampled units on 2026-10-08, 221 of 237 on 2026-10-12), the tagged facts' staying at 99% (642 of 650, 602 of 607). No cause is isolated and the fall is not separated from the draw: each record draws its probes anew (seed 7 over the corpus as it is, 299 -> 359 topics, so 194 -> 237 untagged units and other units), the 95% Wilson intervals are 94.1%-98.9% and 89.3%-95.8% and overlap, and a Fisher exact test of the two counts gives p = 0.07.

**Per scenario kind: runs whose answer met the kind's expected outcome (record of 2026-10-12, six rows each, one run per row and arm label)**

| kind (expected outcome) | haiku-5-5:low | haiku-5-5:default | sonnet-5-5:low | sonnet-5-5:default | router | hook | web-haiku-5-5 | web-sonnet-5-5 |
|---|---|---|---|---|---|---|---|---|
| `sc_present` (route `good`, the row's answer in the reply) | 100% (6 of 6) | 100% (6 of 6) | 100% (6 of 6) | 100% (6 of 6) | 100% (6 of 6) | 100% (6 of 6) | 66.7% (4 of 6) | 66.7% (4 of 6) |
| `sc_partial` (route `split`, the answer and what the kb lacks) | 66.7% (4 of 6) | 50.0% (3 of 6) | 66.7% (4 of 6) | 50.0% (3 of 6) | 66.7% (4 of 6) | 100% (6 of 6) | 0% (0 of 6) | 0% (0 of 6) |
| `sc_absent` (route `web` or `none`, "not confirmed" or the live docs) | 83.3% (5 of 6) | 83.3% (5 of 6) | 66.7% (4 of 6) | 83.3% (5 of 6) | 100% (6 of 6) | 33.3% (2 of 6) | 0% (0 of 6) | 0% (0 of 6) |
| `sc_offkb` (route `none`, "the kb does not cover it") | 83.3% (5 of 6) | 66.7% (4 of 6) | 100% (6 of 6) | 83.3% (5 of 6) | 100% (6 of 6) | 100% (6 of 6) | 16.7% (1 of 6) | 16.7% (1 of 6) |
| `sc_stale` (route `good`, the fact with its source's date or a freshness mark) | 16.7% (1 of 6) | 16.7% (1 of 6) | 16.7% (1 of 6) | 33.3% (2 of 6) | 16.7% (1 of 6) | 100% (6 of 6) | - | - |

Read the kinds as follows. **Met:** `sc_present` by every kb arm (the web arms' two misses are runs whose reply lacks the row's wording), and `sc_offkb` by the router, the hook and Sonnet 5.5 at `low`. **Not met on two to three of six runs:** `sc_partial` by every model arm, each run that failed passed one of its two checks (the model answered what the kb has and did not say what it lacks, or the reverse); only the hook, whose pack prints `kb lacks:`, met it six times, outside the 17%-83% interval of Haiku 5.5 and Sonnet 5.5 at the default level and overlapping the router's and the `low` arms'. **`sc_absent`:** the router met it six times; the hook only twice, the two rows whose pack is `none` with route `web` (Okta, Azure Site Recovery); the four rows built as false goods (tempdb files, Exchange retention, Microsoft 365 E5, Pod Security Admission) print a `good` pack with no `check:` line, which the scatter check does not flag, so a hook answer on them is the pack and does not say the kb lacks it (interval 0%-67%, outside the router's 100%-100%). **`sc_stale`:** the kb arms gave the fact and rarely its source's date or a mark (1-2 of 6, intervals up to 50%-67%), the hook's pack always prints one, but its 6 of 6 is met by the article header on its own (BG-chs2di4p), so it measures the check's wording and not the stamp. The web arms' 0 of 6 on `sc_partial` and `sc_absent` is a floor: their checks name the kb's wording, which a web session cannot give.

**The three research questions, before and after ST-wik6j6im** (`python3 _tools/rag.py pack "<question>"`, the tree before the research commit and the tree after it; the three new articles are `kb/public/ad/fsmo-roles.md`, `kb/public/windows/dhcp-failover.md` and `kb/public/sqlserver/availability-group-seeding.md`):

- **FSMO** ("How do I transfer or seize the FSMO roles to another domain controller with PowerShell?"). Before: `coverage: none (best article matches 4 of 6 key words: another, domain, powershell, role); not in the kb: fsmo, seiz`, `route: web`, `kb lacks: transfer, seize, FSMO, controller`, lead `public/windows/azure-arc-servers.md:46`. After: `coverage: good (best article matches 8 of 8 key words: another, controller, domain, fsmo, powershell, role, seiz, transfer)`, no `check:` line, lead `public/ad/fsmo-roles.md:25`, and `:26` names `Move-ADDirectoryServerOperationMasterRole`.
- **DHCP** ("How do I configure DHCP failover between two Windows Server DHCP servers?"). Before: `coverage: good (best article matches 5 of 6 key words: between, configur, dhcp, server, two)`, no `check:` line, lead `public/windows/delivery-optimization.md:17`, a false good about the DHCP options that point clients at a cache. After: `coverage: good (best article matches 6 of 6 key words: between, configur, dhcp, failover, server, two)`, no `check:` line, lead `public/windows/dhcp-failover.md:21` (`Add-DhcpServerv4Failover`, load balance as the default mode, `-ServerRole` or `-ReservePercent` for hot standby).
- **seeding** ("How do I configure automatic seeding for a SQL Server Always On availability group?"). Before: `coverage: good (best article matches 6 of 8 key words: automatic, availability, configur, group, server, sql)`, no `check:` line, lead `public/windows/azure-update-manager.md:42`, a false good about patch modes. After: `coverage: good (best article matches 8 of 8 key words: alway, automatic, availability, configur, group, seed, server, sql)`, no `check:` line, lead `public/sqlserver/availability-group-seeding.md:20` (`SEEDING_MODE = AUTOMATIC`, then `GRANT CREATE ANY DATABASE` on each secondary).

The scatter check did not flag either false good before the research (its note needs the top three articles in two domains and a best score under 15), so the research, not the check, closed them. The pool had no run on these three rows before the research: the three rows' `sc_present` cells are new in the record of 2026-10-12.

**What this section does not support.** A ranking of the arms on any scenario kind (six rows, one run each); the size of any moved kind cell; an effect of ST-jqwqdj2g's automatic revalidation or ST-f2n2h22c's hints on a lookup, which no scenario runs (the pool arms ran with hooks off); a reading of `sc_stale` as the stamp's effect (BG-chs2di4p); a cause for the kb arms' longer wall time per run; the census items' figures, which this sprint did not re-run; and a Sonnet 5.5 comparison in tokens per right answer between the records, whose cache-read weight differs.

### The false-good fix (BG-xbbimxpq): the pool's `sc_absent` and `sc_partial` before and after

Four questions the kb lacks packed to a clean `good` led by an article on another subject, which the record of 2026-10-12 above shows as the hook's 2 of 6 on `sc_absent`. The fix (`718d1dcb5`) makes `pack` print a `check:` line and route `split`, with `kb has:` and `kb lacks:`, for a plain question word the kb holds in only a few lines and in no article about it, and for a price asked where no printed fact states an amount; it never changes the verdict. This section measures the 12 pool rows of the two kinds the figures above name, `sc_absent` and `sc_partial` (six rows each), before and after it. **Before** is the tree of `0ae6d30bc` (origin/main when the fix was planned), **after** is this branch's tree, which holds the fix (`1e837c5` is the commit the rows name); both ran on 2026-10-12, Claude Code 2.1.296, one rep, with `--out` to a scratch file, so the results file, its generated tables and its spend table do not hold them. The commands:
- `python3 _tools/benchmarks.py run pool --arms hook --kinds sc_absent,sc_partial --reps 1 --out SCRATCH/before.csv`, run from a clone checked out at `0ae6d30bc`, then the same command from the tree after the fix with `--out SCRATCH/after-hook.csv` (free: no model, 16 s each).
- `python3 _tools/benchmarks.py run pool --arms haiku-5-5,sonnet-5-5,router --kinds sc_absent,sc_partial --reps 1 --jobs 8 --max-usd 5 --out SCRATCH/after-paid.csv`, the tree after the fix only; their cells before are those of the record of 2026-10-12 (commit `541378c`, the same rows, one run each), which ran before the fix.

**The hook arm, free, runs right of six, before and after the fix:**

| kind | before (`0ae6d30bc`) | after |
|---|---|---|
| `sc_absent` | 2 of 6 | 5 of 6 |
| `sc_partial` | 6 of 6 | 6 of 6 |
| both kinds | 8 of 12 | 11 of 12 |

The two before figures are those the record of 2026-10-12 holds (2 of 6, 6 of 6), measured again here on `0ae6d30bc`. The two `sc_absent` rows the hook met before are the two whose pack is `none` with route `web` (Okta, Azure Site Recovery). After the fix the packs of the tempdb data files, the Microsoft 365 E5 price and the Pod Security Admission questions carry a `check:` line and route `split` (`kb lacks: tempdb`, `kb lacks: enforce`; the price question's `kb lacks:` is empty, its `check:` names the missing amount), which is what the three more right runs are. The Exchange Online retention question (`BP-023d9e73`) still packs to a clean `good` led by `public/auth/audit-log-apis.md:52`, so the hook meets 5 of 6, not 6 (BG-j7pe3u46). `sc_partial` has nothing to gain: its pack was already `split`, and it is 6 of 6 on both sides.

**The paid arms, one run for each row after the fix, against their cells of the record of 2026-10-12** (runs right of the rows asked; `now` is the run of this section):

| arm label | `sc_absent`, record | `sc_absent`, now | `sc_partial`, record | `sc_partial`, now |
|---|---|---|---|---|
| haiku-5-5:low | 5 of 6 | 6 of 6 | 4 of 6 | 4 of 6 |
| haiku-5-5:default | 5 of 6 | 3 of 6 | 3 of 6 | 2 of 6 |
| sonnet-5-5:low | 4 of 6 | 3 of 5 | 4 of 6 | 4 of 6 |
| sonnet-5-5:default | 5 of 6 | 5 of 5 | 3 of 6 | 3 of 6 |
| router | 6 of 6 | 5 of 5 | 4 of 6 | 4 of 6 |

Effective input tokens per right answer, then the cost of a run (record -> now):

| arm label | `sc_absent` tokens | `sc_absent` cost | `sc_partial` tokens | `sc_partial` cost |
|---|---|---|---|---|
| haiku-5-5:low | 95,645 -> 79,995 | $0.0124 -> $0.0117 | 117,480 -> 137,669 | $0.0169 -> $0.0249 |
| haiku-5-5:default | 88,001 -> 149,675 | $0.0112 -> $0.0121 | 158,411 -> 252,425 | $0.0194 -> $0.0209 |
| sonnet-5-5:low | 96,366 -> 103,934 | $0.1470 -> $0.1390 | 82,093 -> 108,066 | $0.1291 -> $0.1647 |
| sonnet-5-5:default | 105,017 -> 92,857 | $0.2080 -> $0.2156 | 172,410 -> 180,649 | $0.2245 -> $0.2324 |
| router | 33,304 -> 38,679 | $0.0708 -> $0.0805 | 70,991 -> 89,198 | $0.1021 -> $0.1245 |

Read them as follows. **Within:** every figure above lies inside the 95% interval of its cell in the record of 2026-10-12 (a right share of 3 of 6 by Haiku 5.5 at the default level sits on the lower bound of 50%, the router's 38,679 tokens on the upper bound of 38,963), so no model arm's `sc_absent` or `sc_partial` figure moved beyond the spread of one run per row. The fix changes what the pack says on three rows, which the model arms read through their own tools; Sonnet 5.5 at `low`, the model arm shortest of `sc_absent` in the record (4 of 6), shows 3 of 5, and the other cells differ from the record's by one or two runs, which one run per row does not separate from the noise of a run. **The hook is the one arm the fix moves:** 2 of 6 to 5 of 6 on `sc_absent`, beyond its record cell's interval (0%-67%), at no model tokens and no change on `sc_partial`.

**The run's own limit.** The dry run estimated $3.51 for 60 runs, each priced at the mean cost of its label's all-kinds cell; these two kinds cost more a run than that mean (the router's $0.10 against $0.026), so the 57 runs that ran billed $5.72 (Haiku 5.5 $0.42 in both levels, Sonnet 5.5 $4.16, the router $1.15), and `--max-usd 5` with `--jobs 8` stopped the run three runs short, each the Pod Security Admission row (`BP-1fa2c349`) on `sonnet-5-5:low`, `sonnet-5-5:default` and the router. Those three cells therefore rest on five rows, not six, and the one row left out is one of the four the fix flags; a re-run of the three would add to a spend already past the limit and was not made.

**What this section does not support.** A ranking of the arms on either kind (six rows, one run each, three cells of five); a size for any moved cell; an effect of the fix on a model arm's answer, which no cell separates from the run-to-run spread; and the Exchange Online row, which the fix does not close.

## Reading files, hosts and start contexts

### Reading files without the lookup tools

**Setup:** `python3 _tools/benchmarks.py run files-subagents`: the six tasks (T1 one fact, T2 a source id, T3 one topic, T4 a cross-topic synthesis, T5 not in the kb, T6 a domain audit; T1 and T4 also "guided", told to follow `/kb-lookup`) as Sonnet subagents in a clone of `19010a8`, the commit before the evidence pack, the audit tools and the `kb:` hook (188 topics, `rag.py search` and `show` only, the 15.8 KB `AGENTS.md`). The task wording follows the eval rows those tasks seeded (the history did not record it). The re-run's subagent is defined with `--agents` (Bash, Read, Grep, Glob, Skill), started by a Haiku `claude -p` with no MCP servers; the fixed context is a Sonnet "Reply with the single word ok." in an empty directory and in that clone.

<!-- bench:records files-subagents -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 19010a8 | 2026-09-25 | 19010a8 | - | 188 | - | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 1 | $1.35 |
<!-- /bench -->

<!-- bench:table files-subagents metrics=tool_calls,requests,start_ctx,input,effective_input,wall_s -->
| case | arm | tool_calls | requests | start_ctx | input | effective_input | wall_s |
|---|---|---|---|---|---|---|---|
| T1 guided | subagent | 3 -> 2 (-33%) | 5 -> 3 (-40%) | 50.0k -> 24,343 (-51%) | 274k -> 78,992 (-71%) | 136k -> 62,250 (-54%) | 16 s -> 7 s (-56%) |
| T1 | subagent | 1 -> 2 (+100%) | 3 -> 3 (+0%) | 49.9k -> 24,329 (-51%) | 161k -> 78,950 (-51%) | 122k -> 46,871 (-62%) | 12 s -> 6 s (-46%) |
| T2 | subagent | 3 -> 2 (-33%) | 5 -> 3 (-40%) | 50.0k -> 24,326 (-51%) | 268k -> 77,084 (-71%) | 134k -> 43,962 (-67%) | 22 s -> 11 s (-48%) |
| T3 | subagent | 5 -> 2 (-60%) | 5 -> 3 (-40%) | 50.1k -> 24,366 (-51%) | 296k -> 79,663 (-73%) | 157k -> 48,016 (-69%) | 41 s -> 15 s (-63%) |
| T4 guided | subagent | 8 -> 3 (-62%) | 7 -> 4 (-43%) | 50.2k -> 24,376 (-51%) | 463k -> 115,637 (-75%) | 195k -> 62,609 (-68%) | 38 s -> 23 s (-39%) |
| T4 | subagent | 4 -> 3 (-25%) | 5 -> 4 (-20%) | 50.1k -> 24,362 (-51%) | 333k -> 115,580 (-65%) | 178k -> 62,574 (-65%) | 37 s -> 20 s (-47%) |
| T5 | subagent | 4 -> 2 (-50%) | 5 -> 3 (-40%) | 50.0k -> 24,340 (-51%) | 282k -> 78,598 (-72%) | 144k -> 46,061 (-68%) | 23 s -> 8 s (-65%) |
| T6 | subagent | 28 -> 8 (-71%) | 30 -> 9 (-70%) | 50.1k -> 24,344 (-51%) | 2,021k -> 300,522 (-85%) | 363k -> 101,674 (-72%) | 195 s -> 49 s (-75%) |
| T6 as a script | subagent | 1 | - | - | ~1k | ~1k | 0.02 s |
| fixed context | empty directory | - | - | - | 41.0k -> 28,132 (-31%) | - | - |
| fixed context | old clone | - | - | - | 48.9k -> 45,564 (-7%) | - | - |
| fixed context | old clone, no servers | - | - | - | 42,122 | - | - |
<!-- /bench -->

What it shows: at the old commit and with today's Claude Code, a Sonnet subagent starts at 24.3k (50.0k in the history) and the file-reading tasks took 2-3 tool calls where they took 1-8, T6 8 calls and 301k input where it took 28 and 2.0M. The fixed context is still most of each task's input: 24.3k of 77-80k on T1-T3 and T5, re-read on each of 3 requests. The fixed context of a session in that clone is 45.6k (48.9k), 28.1k of it Claude Code's own in an empty directory (41.0k); the guided runs cost no more than the unguided ones now.

### Lookup tools against reading files

**Setup:** `python3 _tools/benchmarks.py run files-headless`: the same six tasks in fresh Sonnet sessions, `before` in the clone of `19010a8` and `after` in the clone of `HEAD`, allowed `rag.py`, Read, Grep, Glob and skills, no web, no subagents, no MCP servers.

<!-- bench:records files-headless -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 0f85d24 | 2026-09-25 | 0f85d24 | - | 188 | - | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 1 | $1.74 |
<!-- /bench -->

<!-- bench:table files-headless metrics=turns,input,out,wall_s -->
| case | arm | turns | input | out | wall_s |
|---|---|---|---|---|---|
| fixed context | before | 1 -> 1 (+0%) | 46.9k -> 39,483 (-16%) | 4 -> 4 (+0%) | 3 s -> 6 s (+103%) |
| fixed context | after | 1 -> 1 (+0%) | 41.2k -> 35,642 (-13%) | 4 -> 4 (+0%) | 4 s -> 3 s (-18%) |
| T1 | before | 5 -> 5 (+0%) | 198.9k -> 166,029 (-17%) | 853 -> 674 (-21%) | 17 s -> 15 s (-14%) |
| T1 | after | 2 -> 2 (+0%) | 84.2k -> 72,717 (-14%) | 270 -> 598 (+121%) | 8 s -> 12 s (+50%) |
| T2 | before | 5 -> 3 (-40%) | 190.6k -> 81,392 (-57%) | 1,013 -> 560 (-45%) | 19 s -> 8 s (-58%) |
| T2 | after | 4 -> 2 (-50%) | 167.3k -> 71,699 (-57%) | 625 -> 334 (-47%) | 15 s -> 14 s (-8%) |
| T3 | before | 8 -> 5 (-38%) | 259.6k -> 166,930 (-36%) | 2,361 -> 1,103 (-53%) | 38 s -> 20 s (-47%) |
| T3 | after | 3 -> 5 (+67%) | 129.3k -> 150,065 (+16%) | 1,354 -> 1,274 (-6%) | 25 s -> 24 s (-2%) |
| T4 | before | 11 -> 8 (-27%) | 586.3k -> 319,810 (-45%) | 3,630 -> 2,427 (-33%) | 59 s -> 42 s (-28%) |
| T4 | after | 6 -> 5 (-17%) | 139.5k -> 157,749 (+13%) | 2,302 -> 1,631 (-29%) | 32 s -> 37 s (+16%) |
| T5 | before | 5 -> 5 (+0%) | 196.7k -> 164,286 (-16%) | 761 -> 650 (-15%) | 16 s -> 26 s (+64%) |
| T5 | after | 2 -> 5 (+150%) | 83.0k -> 148,520 (+79%) | 266 -> 663 (+149%) | 8 s -> 20 s (+146%) |
| T6 | before | 52 -> 8 (-85%) | 1262.6k -> 340,403 (-73%) | 18,449 -> 3,408 (-82%) | 202 s -> 66 s (-67%) |
| T6 | after | 2 -> 6 (+200%) | 88.1k -> 242,365 (+175%) | 2,869 -> 1,515 (-47%) | 30 s -> 23 s (-23%) |
| T1-T6 | before | 86 -> 34 (-60%) | 2695k -> 1,238,850 (-54%) | 27,067 -> 8,822 (-67%) | 351 s -> 177 s (-49%) |
| T1-T6 | after | 19 -> 25 (+32%) | 691k -> 843,115 (+22%) | 7,686 -> 6,015 (-22%) | 118 s -> 130 s (+10%) |
| kb: hook, covered question | after | - | 0 | - | 426 ms |
<!-- /bench -->

What it shows:
- **The old commit, run again with today's Claude Code, took 34 turns and 1.24M input for the six tasks** against 86 turns and 2.70M in the history; T6 (the domain audit) fell from 52 turns and 1.26M to 8 turns and 340k. Claude Code's fixed context in that clone fell from 46.9k to 39.5k.
- **With the lookup tools (`after`) the six tasks took 25 turns and 843k input,** against 19 and 691k in the history: T1 and T2 took 2 turns, T3, T5 and T6 2-4 more than in the history and T4 one fewer (this arm reaches `rag.py` through Bash only, no MCP server). The tools still cut input by a third against the old commit (843k against 1.24M) and T6 from 8 turns to 6.
- The `kb:` hook row is the history's; the hook's time now is in "Tool speed".

### Plugin in a host project

**Setup:** `python3 _tools/benchmarks.py run host-lookups`: the six tasks in fresh Sonnet sessions (`--setting-sources project,local`, claude.ai connectors off) in a throwaway TypeScript MCP-server project with five planted problems (an NTLM fallback, a malformed SPN, a simple bind over `ldap://`, `console.log` on a stdio MCP server, broad Graph scopes) and the plugin loaded with `--plugin-dir`, against the same tasks in the clone; `/it-ops-kb:kb-review-workspace` in the host (its checks: the five problems named); the first request of a general-purpose Sonnet agent in the host.

**The reviewer at both levels (2026-10-09):** the scenario has no effort setting: the host is a clone of `HEAD`, so the `kb-reviewer` agent runs at the `effort` its file holds there. The record of 2026-10-09 is therefore two runs of the whole scenario on the same day (Claude Code 2.1.293, 299 kb topics, one run per cell each, 16 paid runs each):
- **`effort: medium`**, started from commit 1484912 (the file's level then) with `--out` to a scratch file, so its rows are not in the results file: $0.83 for the scenario, 234 s. The medium figures below are cited from that scratch file, which is not in the repository.
- **`effort: low`**, started from commit 36a4550 (the file set to `low`) into the results file, which holds this record: $0.86, 222 s.

A same-day run replaces the rows of its scenario and day, which is why the medium run went to the scratch file. One run each: a difference between the two levels is one pair of runs, not a measured spread.

<!-- bench:records host-lookups -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 0659f83 | 2026-09-25 | 0659f83 | 2.1.282 | 188 | - | - |
| 945fb09 | 2026-09-27 | 945fb09 | 2.1.282 | 188 | - | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 1 | $1.50 |
| 2026-10-09 | 2026-10-09 | 36a4550 | 2.1.293 | 299 | 1 | $0.86 |
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 1 | $1.22 |
<!-- /bench -->

<!-- bench:table host-lookups metrics=turns,input,out,wall_s,tool_calls,checks,start_ctx -->
| case | arm | turns | input | out | wall_s | tool_calls | checks | start_ctx |
|---|---|---|---|---|---|---|---|---|
| fixed context | host | 1 -> 1 -> 1 -> 1 (+0%) | 20.1k -> 30,278 -> 18,675 -> 19,308 (+3%) | 4 -> 4 -> 4 -> 4 (+0%) | 1 s -> 3 s -> 3 s -> 3 s (-3%) | 0 -> 0 -> 0 | 0/0 -> 0/0 -> 0/0 | - |
| fixed context | clone | 1 -> 1 -> 1 -> 1 (+0%) | 22.3k -> 34,369 -> 22,876 -> 23,573 (+3%) | 4 -> 4 -> 4 -> 4 (+0%) | 1 s -> 4 s -> 5 s -> 3 s (-37%) | 0 -> 0 -> 0 | 0/0 -> 0/0 -> 0/0 | - |
| T1 | host | 2 -> 2 -> 2 -> 2 (+0%) | 42.1k -> 61,792 -> 39,505 -> 41,057 (+4%) | 561 -> 681 -> 932 -> 810 (-13%) | 6 s -> 10 s -> 11 s -> 8 s (-22%) | 1 -> 1 -> 1 (+0%) | 0/0 -> 0/0 -> 0/0 | - |
| T1 | clone | 2 -> 2 -> 2 -> 2 (+0%) | 46.5k -> 70,928 -> 48,611 -> 49,575 (+2%) | 478 -> 504 -> 976 -> 911 (-7%) | 5 s -> 8 s -> 14 s -> 9 s (-37%) | 1 -> 1 -> 1 (+0%) | 0/0 -> 0/0 -> 0/0 | - |
| T2 | host | 3 -> 3 -> 3 -> 3 (+0%) | 62.9k -> 92,230 -> 57,339 -> 59,238 (+3%) | 589 -> 512 -> 549 -> 630 (+15%) | 6 s -> 8 s -> 7 s -> 7 s (-7%) | 2 -> 2 -> 2 (+0%) | 0/0 -> 0/0 -> 0/0 | - |
| T2 | clone | 3 -> 3 -> 3 -> 3 (+0%) | 68.0k -> 104,451 -> 69,801 -> 71,973 (+3%) | 558 -> 504 -> 518 -> 563 (+9%) | 6 s -> 9 s -> 12 s -> 7 s (-38%) | 2 -> 2 -> 2 (+0%) | 0/0 -> 0/0 -> 0/0 | - |
| T3 | host | 2 -> 2 -> 2 -> 2 (+0%) | 43.9k -> 63,263 -> 43,563 -> 42,875 (-2%) | 1,309 -> 874 -> 1,145 -> 1,099 (-4%) | 13 s -> 13 s -> 15 s -> 11 s (-26%) | 1 -> 1 -> 1 (+0%) | 0/0 -> 0/0 -> 0/0 | - |
| T3 | clone | 2 -> 3 -> 2 -> 3 (+50%) | 51.1k -> 109,848 -> 48,092 -> 76,521 (+59%) | 1,655 -> 1,112 -> 895 -> 1,011 (+13%) | 16 s -> 16 s -> 12 s -> 12 s (+0%) | 2 -> 1 -> 2 (+100%) | 0/0 -> 0/0 -> 0/0 | - |
| T4 | host | 2 -> 5 -> 3 -> 3 (+0%) | 48.9k -> 145,003 -> 74,035 -> 80,267 (+8%) | 1,597 -> 2,154 -> 2,016 -> 2,225 (+10%) | 15 s -> 22 s -> 17 s -> 19 s (+13%) | 4 -> 2 -> 2 (+0%) | 0/0 -> 0/0 -> 0/0 | - |
| T4 | clone | 2 -> 3 -> 4 -> 3 (-25%) | 52.9k -> 115,951 -> 124,126 -> 87,213 (-30%) | 1,777 -> 2,394 -> 2,709 -> 2,202 (-19%) | 15 s -> 22 s -> 34 s -> 19 s (-45%) | 2 -> 3 -> 2 (-33%) | 0/0 -> 0/0 -> 0/0 | - |
| T5 | host | 2 -> 2 -> 4 -> 4 (+0%) | 40.5k -> 61,226 -> 78,103 -> 80,278 (+3%) | 271 -> 277 -> 591 -> 694 (+17%) | 4 s -> 8 s -> 9 s -> 9 s (-3%) | 1 -> 3 -> 3 (+0%) | 0/0 -> 0/0 -> 0/0 | - |
| T5 | clone | 2 -> 2 -> 4 -> 2 (-50%) | 44.9k -> 69,366 -> 94,780 -> 46,776 (-51%) | 334 -> 236 -> 664 -> 550 (-17%) | 4 s -> 7 s -> 11 s -> 9 s (-20%) | 1 -> 3 -> 1 (-67%) | 0/0 -> 0/0 -> 0/0 | - |
| T6 | host | 3 -> 4 -> 3 -> 4 (+33%) | 67.2k -> 141,435 -> 58,963 -> 84,638 (+44%) | 3,071 -> 1,879 -> 1,193 -> 2,055 (+72%) | 21 s -> 22 s -> 11 s -> 19 s (+68%) | 3 -> 2 -> 3 (+50%) | 0/0 -> 0/0 -> 0/0 | - |
| T6 | clone | 2 -> 4 -> 2 -> 4 (+100%) | 49.0k -> 179,963 -> 47,935 -> 123,380 (+157%) | 2,666 -> 2,336 -> 1,079 -> 4,256 (+294%) | 21 s -> 30 s -> 12 s -> 30 s (+149%) | 3 -> 1 -> 3 (+200%) | 0/0 -> 0/0 -> 0/0 | - |
| T1-T6 | host | 14 -> 18 -> 17 -> 18 (+6%) | 306k -> 564,949 -> 351,508 -> 388,353 (+10%) | 7,398 -> 6,377 -> 6,426 -> 7,513 (+17%) | 65 s -> 82 s -> 71 s -> 73 s (+4%) | - | - | - |
| T1-T6 | clone | 13 -> 17 -> 17 -> 17 (+0%) | 312k -> 650,507 -> 433,345 -> 455,438 (+5%) | 7,468 -> 7,086 -> 6,841 -> 9,493 (+39%) | 67 s -> 92 s -> 94 s -> 85 s (-10%) | - | - | - |
| general-purpose agent | host | - | - | - | - | - | - | 13.5k -> 15,281 -> 10,228 -> 10,760 (+5%) |
| kb-review-workspace | host | 0 -> 0 -> 0 | 73.1k -> 0 -> 0 -> 0 | 3.9k -> 0 -> 2,305 -> 2,855 (+24%) | 32 s -> 45 s -> 22 s -> 22 s (+5%) | 9 -> 0 -> 0 -> 0 | 5/5 -> 5/5 -> 5/5 -> 5/5 | - |
<!-- /bench -->

What it shows:
- **The host still costs less than the clone:** in the record of 2026-10-12, 18 turns and 388k input for the six tasks against 17 turns and 455k, at 19.3k and 23.6k of fixed context (the clone also loads `AGENTS.md` and the user's local-scope servers). The record of 2026-10-09 read 17 turns and 352k against 17 turns and 433k, at 18.7k and 22.9k. Both records are above the history (306k and 312k) and below the record of 2026-09-28 (565k and 651k, 30.3k and 34.4k of fixed context); T5 took 4 turns in the host where the history took 2, and T6 4 turns in both. One run each.
- **`/kb-review-workspace` named all five planted problems (5/5)** at `effort: low` (the level the file holds at that commit): $0.0858, 22.5 s, 2,855 output tokens and 9 tool calls in the `kb-reviewer` agent. The record of 2026-10-09 read, at medium (scratch file) $0.0927, 27.8 s, 3,403 output tokens and 10 tool calls, and at low $0.0538, 21.5 s, 2,305 output tokens and 8 tool calls; the record of 2026-09-28 $0.1318 and 45.4 s at medium. The rows read 0 input, turns and tool calls (the main session's: the agent runs forked) and carry output tokens and the agent's tool calls (`sub_tool_calls`). One run each, so the difference between the two records at low is not a measured spread; low missed none of the five in either.
- A general-purpose Sonnet agent in the host starts at 10.8k (10.2k on 2026-10-09, 15.3k on 2026-09-28, 13.5k in the history).

### Always-on cost

**Setup:** `python3 _tools/benchmarks.py run always-on`: `claude -p "Reply with the single word ok." --model haiku --no-session-persistence --setting-sources project,local` in an empty directory without the plugin, with `--plugin-dir` (hooks off), and with a copy of the plugin whose hooks run and write under the scratch directory; and in a clone with its hooks off and with them on (the query log in mode `local`, a local bare `origin`). 4 runs each; the value is the steady (highest) input, since a run whose first request comes before the `kb` server connects lacks its texts. The history's `--plugin-dir` runs had the plugin's hooks on.

<!-- bench:records always-on -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 3725d8f | 2026-09-27 | 3725d8f | 2.1.283 | 265 | - | - |
| 99e464a | 2026-09-28 | 99e464a | 2.1.283 | 271 | - | - |
| 01587ae | 2026-09-28 | 01587ae | 2.1.283 | 271 | - | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 4 | $0.12 |
| 2026-10-08 | 2026-10-08 | 58ebb9c | 2.1.293 | 299 | 4 | $0.02 |
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 4 | $0.02 |
<!-- /bench -->

<!-- bench:table always-on metrics=input,files_the_hooks_wrote -->
| case | arm | input | files_the_hooks_wrote |
|---|---|---|---|
| ok | no plugin | 22,038 (all 4) -> 22,036 (all 4) -> 22,036 (all 4) -> 22,042 -> 19,754 -> 19,524 (-1%) | - |
| ok | --plugin-dir, hooks on | 23,282 (all 5) -> 23,280 (all 5) -> 23,280 (all 5) -> 23,286 -> 21,572 -> 21,863 (+1%) | - |
| ok | --plugin-dir, hooks off | 23,286 -> 21,572 -> 21,863 (+1%) | - |
| ok | clone, hooks off | 24,584 -> 24,303 -> 24,173 (-1%) | - |
| ok | clone, query log hooks on | 24,584 -> 24,420 -> 24,286 (-1%) | - |
| isolation | --plugin-dir, hooks on | - | 3 -> 3 -> 3 (+0%) |
<!-- /bench -->

What it shows:
- **The plugin adds 2,339 tokens** (21,863 against 19,524 in the record of 2026-10-12; 1,818 in the record of 2026-10-08, 21,572 against 19,754; 1,244 in the history, 23,286 against 22,042); its hooks on or off make no difference (21,863 both), since no hook prints.
- **The query log's hooks add about 110 tokens to a clone's context in the last two records:** 24,286 with them on against 24,173 off on 2026-10-12, 24,420 against 24,303 on 2026-10-08; the history read 24,584 on and off. The runs say not where the difference comes from. With them on, the plugin copy's hooks wrote 3 files under the scratch directory (its `digest-week` marker, `distill.log` and the spool directory) and nothing under `~/.claude/plugins/data/`.

### kb-lookup agent start context

**Setup:** `python3 _tools/benchmarks.py run kb-lookup-agent`: in an empty directory, `claude -p "Use the it-ops-kb:kb-lookup agent to answer this, then relay its answer: How many apps can an Intune Win32 app supersede?" --model haiku --setting-sources project,local --plugin-dir <clone> --allowedTools "Agent,mcp__plugin_it-ops-kb_kb"`, hooks off, session kept; the start context is the first request of the subagent transcript.

<!-- bench:records kb-lookup-agent -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 945fb09 | 2026-09-27 | 945fb09 | 2.1.283 | 266 | - | - |
| 2026-09-28 | 2026-09-28 | 654c8ad | 2.1.283 | 271 | 1 | $0.12 |
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 1 | $0.01 |
<!-- /bench -->

<!-- bench:table kb-lookup-agent metrics=start_ctx,input,requests,route,checks -->
| case | arm | start_ctx | input | requests | route | checks |
|---|---|---|---|---|---|---|
| run 1 | kb-lookup | 3,937 -> 3,999 -> 5,466 (+37%) | 11,149 -> 10,079 -> 23,548 (+134%) | 2 -> 2 -> 3 (+50%) | kb_pack -> kb_pack -> kb_pack > kb_pack | 1/1 -> 1/1 |
| run 2 | kb-lookup | 3,938 -> 4,005 -> 5,481 (+37%) | 18,026 -> 20,915 -> 23,353 (+12%) | 3 -> 3 -> 3 (+0%) | kb_pack, kb_show -> kb_pack > kb_show -> kb_pack > kb_pack | 1/1 -> 1/1 |
| run 3 | kb-lookup | 3,932 -> 4,009 -> 5,537 (+38%) | 9,937 -> 17,784 -> 23,790 (+34%) | 2 -> 3 -> 3 (+0%) | kb_pack -> kb_pack > kb_show -> kb_pack > kb_pack | 1/1 -> 1/1 |
| run 4 | kb-lookup | 3,931 | 9,935 | 2 | kb_pack | - |
<!-- /bench -->

What it shows: in the record of 2026-10-12 the agent starts at 5.5k (5,466-5,537), 1.5k above the record of 2026-09-28 (3,999-4,009) and the history's 3,931-3,938. The run does not split the difference: the agent's file changed once since then (the `none` rule, 2026-09-29), it lists 12 kb tools and preloads the `kb-lookup` skill. Every run called `kb_pack` twice in 3 requests and passed its check, at 23.4k-23.8k input in total, where the record of 2026-09-28 read 10.1k-20.9k in 2 to 3 requests.

## Retrieval

### Retrieval quality

**Setup:** `python3 _tools/benchmarks.py run retrieval`, no model but one: keyword probes (the six longest words of each of 844 units sampled with seed 7) and whether the unit's line is in the pack; 72 blind questions written by Sonnet from the fact text alone; the off-kb list's `good` count; cut fact lines without a visible tag over the eval packs; and the `SNIPPET:` units a keyword probe finds. The history's probes and blind set were not committed, so the re-run's are new: the rows compare in kind, not question for question. The history's `lexical baseline` is `pack` before untagged content was indexed.

<!-- bench:records retrieval -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 0659f83 | 2026-09-25 | 0659f83 | - | 188 | - | - |
| beeb4de | 2026-09-25 | beeb4de | - | 188 | - | - |
| beacebd | 2026-09-28 | beacebd | - | 188 | - | - |
| 2026-09-28 | 2026-09-28 | f830156 | 2.1.283 | 271 | 1 | $0.07 |
| 2026-10-08 | 2026-10-08 | 58ebb9c | 2.1.293 | 299 | 1 | $0.07 |
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 1 | $0.08 |
<!-- /bench -->

<!-- bench:table retrieval metrics=value -->
| case | arm | value |
|---|---|---|
| untagged content, line in pack (keyword probes) | lexical baseline | 0% |
| untagged content, line in pack (keyword probes) | current | 84-100% -> 95% -> 97% -> 93% (-4%) |
| blind questions, line in pack | lexical baseline | 36/72 |
| blind questions, line in pack | current | 68/72 (94%) -> 71/72 -> 67/72 -> 69/72 |
| blind questions, false none | lexical baseline | 11% on tagged facts, 30% on untagged content |
| blind questions, false none | current | 0% -> 0/72 -> 0/72 -> 0/72 |
| off-kb questions answered good | lexical baseline | 3/20 |
| off-kb questions answered good | current | 2/20 -> 15/106 -> 15/106 -> 11/103 |
| cut facts with no visible tag | lexical baseline | 180 |
| cut facts with no visible tag | current | 0 -> 33 -> 43 -> 43 (+0%) |
| code blocks retrievable | lexical baseline | 0/44 |
| code blocks retrievable | current | 44/44 -> 187/189 -> 221/225 -> 312/317 |
| tagged facts, line in pack (keyword probes) | current | 98% -> 99% -> 99% (+0%) |
<!-- /bench -->

What it shows: on the kb at 359 topics (2026-10-12), keyword probes find 99% of sampled tagged facts' lines and 93% of untagged content's (97% on 2026-10-08, 95% on 2026-09-28); 69 of 72 blind questions put the fact's line in the pack (71 and 67 in the two records before) and none got a false `none`; 312 of 317 `SNIPPET:` units are found by their own words (221 of 225 on 2026-10-08). The off-kb list (103 questions now) has 11 `good` (15 of 106 before), as in "Verdict corrections". 43 cut lines of tagged units show no tag, as on 2026-10-08, where the first record counted 33; the history counted fact bullets only. Each re-run draws its probes and blind questions anew, so the cells compare in kind, not question for question.

### Verdict corrections

**Setup:** `python3 _tools/benchmarks.py run verdict`: the eval set, the off-kb list's verdicts, the scatter check's calibration (case `scatter check`, arms `calibrated` and `current`: the threshold fitted on the eval set's `good` rows against the off-kb list's `good` ones, the one `kbfacts.SCATTER_SCORE` holds, and for each the off-kb goods and the eval goods flagged; the held-out file is never read), the indexed lines, and `pack`'s time over the eval questions (in process, warm, 3 passes). The history's rule tables (the design set of common-word false goods and off-domain questions, and the held-out set) chose the rules that shipped; those sets were not committed, so the re-run measures the shipped rules on the committed sets.

<!-- bench:records verdict -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| beacebd | 2026-09-28 | beacebd | - | 266 | - | - |
| 2026-09-28 | 2026-09-28 | bfa2a7d | 2.1.283 | 271 | 1 | - |
| 2026-10-08 | 2026-10-08 | 58ebb9c | 2.1.293 | 299 | 1 | - |
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 1 | - |
<!-- /bench -->

<!-- bench:table verdict metrics=passed,verdict_good,verdict_weak,verdict_none,indexed_lines,median_ms,p95_ms -->
| case | arm | passed | verdict_good | verdict_weak | verdict_none | indexed_lines | median_ms | p95_ms |
|---|---|---|---|---|---|---|---|---|
| index | current | - | - | - | - | 12,469 -> 12,713 -> 14,375 -> 16,972 (+18%) | - | - |
| eval set | previous code | 190/250 | - | - | - | - | - | - |
| eval set | current | 250/250 -> 250/250 -> 574/574 -> 621/621 | - | - | - | - | - | - |
| off-kb list | previous code | - | 55 | 38 | 13 | - | - | - |
| off-kb list | current | - | 15 -> 15 -> 15 -> 11 (-27%) | 48 -> 48 -> 48 -> 48 (+0%) | 43 -> 43 -> 43 -> 44 (+2%) | - | - | - |
| pack, warm | current | - | - | - | - | - | 2.3 ms -> 2.3 ms -> 2.8 ms -> 3.6 ms (+29%) | 4.6 ms -> 4.6 ms -> 5.6 ms -> 6.9 ms (+22%) |
<!-- /bench -->

<!-- bench:table verdict metrics=eval (129 rows),false goods fixed,TG weak,design off-domain none,original 20 off-kb none -->
| case | arm | eval (129 rows) | false goods fixed | TG weak | design off-domain none | original 20 off-kb none |
|---|---|---|---|---|---|---|
| one tagged fact holds every key word, unless the question has a name, an identifier or a one-word alias | design set | 126 (`resources subscribe/templates`, `uv sync --frozen`: slash and flag parts were split off; `ruff`/`noqa`) | 29/35 | 8/30 | - | - |
| same, fact must also hold two question words side by side | design set | 126 | 32/35 | 13/30 | - | - |
| two question words side by side only | design set | 128 (ruff) | 17/35 | 1/30 | - | - |
| one fact, identifiers read from the raw question, a title word under 1% of lines as anchor | design set | 129 | 27/35 | 4/30 (`cmpivot`, `bitlocker` typed lowercase) | - | - |
| + the kb's brand spelling as anchor (CMPivot, BitLocker, LAPS) | design set | 129 | 27/35 (rare title words `resolution`, `replacement` anchor false goods) | 2/30 | - | - |
| brand spelling without a title anchor | design set | 128 (ruff) | 29/35 | 3/30 | - | - |
| shipped:** one fact, or a name, identifier, alias, brand spelling, or word an article is about (60% of its lines in the article named after it) | design set | 129 | 29/35 | 2/30 | - | - |
| shipped, but the fact's own text must hold the words (not its title) | design set | 129 | 30/35 | 4/30 | - | - |
| shipped + two words side by side | design set | 129 | 32/35 | 4/30 | - | - |
| before | design set | 129 | - | - | - | - |
| a name no line the pack could print holds, any frequency | design set | 128 (Presidio REST API: "API" is missing from the answer lines) | - | - | - | - |
| a name absent from the lead article (the check: condition) and rare | design set | would demote the NTLMv1 row (LmCompatibilityLevel, 2 lines, sits in the second article) | - | - | - | - |
| shipped:** printable lines lack a name held by under 1% of lines | design set | 129 | - | - | - | - |
| shipped:** + the AV/PC exemption only for names of up to 3 letters | design set | 129 | - | - | - | - |
<!-- /bench -->

What it shows: the shipped rules hold on the grown kb (2026-10-12): the eval set passes 621 of 621 (574 of 574 on 2026-10-08, 250 of 250 before), the off-kb list of 103 questions gives 11 `good`, 48 `weak` and 44 `none` (15, 48 and 43 of 106 on 2026-10-08, and as when the rules shipped), and `pack` takes 3.6 ms median and 6.9 ms at p95 over 16,972 indexed lines (2.8 ms and 5.6 ms over 14,375 on 2026-10-08; 2.3 ms and 4.6 ms over 12,713 on 2026-09-28). The scatter check flags 8 of the 11 off-kb `good` and 3 of 233 eval `good` at its threshold of 15, calibrated and current alike. The rule tables are the history's design-set results; the re-run does not repeat them.

### doc2query

**Setup:** `python3 _tools/benchmarks.py run doc2query`: the pilot and control arms of `kb/public/_retrieval/doc2query/arms.json` (round 2's), 40 facts sampled from each, one blind paraphrase per fact written by Sonnet, then `doc2query.py evaluate` with expansion off and on (the protocol in `kb/_self/doc2query.md`).

<!-- bench:records doc2query -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 88e2a10 | 2026-09-25 | 88e2a10 | - | 188 | - | - |
| 17387ce | 2026-09-25 | 17387ce | - | 188 | - | - |
| 2026-09-28 | 2026-09-28 | f830156 | 2.1.283 | 271 | 1 | $0.10 |
<!-- /bench -->

<!-- bench:table doc2query metrics=line_in_pack_pct,passed,mean_chars,verdicts,pilot line in pack,control line in pack,eval,off-kb good,mean pack chars -->
| case | arm | line_in_pack_pct | passed | mean_chars | verdicts | pilot line in pack | control line in pack | eval | off-kb good | mean pack chars |
|---|---|---|---|---|---|---|---|---|---|---|
| round 1 | weight off | - | - | - | - | 36/40 (90%) | 38/40 | 37/37 | 2/20 | 3,345 |
| round 1 | weight 0.3 | - | - | - | - | 37/40 | 38/40 | 37/37 | 2/20 | 3,262 |
| round 1 | weight 1.0 (in use) | - | - | - | - | 39/40 (97.5%) | 38/40 | 37/37 | 2/20 | 3,256 |
| round 1 | weight 2.0 | - | - | - | - | 39/40 | 38/40 | 37/37 | 2/20 | 3,215 |
| pilot arm | expansion off | 95.0% -> 95.0% (+0%) | - | - | - | - | - | - | - | - |
| pilot arm | expansion on | 95.0% -> 95.0% (+0%) | - | - | - | - | - | - | - | - |
| control arm | expansion on | 97.5% -> 90.0% (-8%) | - | - | - | - | - | - | - | - |
| eval set | expansion on | - | 37/37 -> 250/250 | 3,273 -> 3,362 (+3%) | - | - | - | - | - | - |
| eval set | expansion off | - | 250/250 | 3,345 -> 3,384 (+1%) | - | - | - | - | - | - |
| off-kb | expansion on | - | - | - | good 2/20 -> good 15, weak 48, none 43 | - | - | - | - | - |
| control arm | expansion off | 92.0% | - | - | - | - | - | - | - | - |
| off-kb | expansion off | - | - | - | good 15, weak 48, none 43 | - | - | - | - | - |
<!-- /bench -->

What it shows: as in round 2, expansion adds nothing measurable on fresh blind questions: the pilot arm finds 95% of fact lines with and without it, the control arm 90% and 92% (one question apart). The eval set passes 250 of 250 either way, the off-kb verdicts are the same, and the mean pack is 22 characters smaller with expansion on (3,362 against 3,384).

### Tool speed

**Setup:** `python3 _tools/benchmarks.py run tool-speed` on macOS (the history: Python 3.11 in a Linux container): cold CLI calls with the persisted index (5 runs, 3 for `eval` and `check-trailers`), an MCP session of 12 calls, the server's start to its `initialize` reply, an index build into an empty directory, and in process `pack` over the eval questions and 1,000 random packs. The history's `before` is the corpus rebuilt in memory by every process.

<!-- bench:records tool-speed -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| e397a24 | 2026-09-27 | e397a24 | - | 259 | - | - |
| 2026-09-28 | 2026-09-28 | 287f380 | 2.1.283 | 271 | 5 | - |
| 2026-10-08 | 2026-10-08 | 58ebb9c | 2.1.293 | 299 | 5 | - |
| 2026-10-09 | 2026-10-09 | 73af85f | 2.1.293 | 300 | 5 | - |
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 5 | - |
<!-- /bench -->

<!-- bench:table tool-speed metrics=time,median_ms,p95_ms,s,size_mb -->
| case | arm | time | median_ms | p95_ms | s | size_mb |
|---|---|---|---|---|---|---|
| rag.py pack (CLI, cold) | before | 3.93 s | - | - | - | - |
| rag.py pack (CLI, cold) | current | 0.06 s -> 0.04 s -> 0.05 s -> 0.06 s -> 0.11 s (+97%) | 43.6 ms -> 54.8 ms -> 56.0 ms -> 110.1 ms (+97%) | 50.4 ms -> 57.6 ms -> 73.6 ms -> 124.6 ms (+69%) | - | - |
| kb: hook | before | 2.05-2.15 s | - | - | - | - |
| kb: hook | current | 0.05-0.09 s -> 0.05 s -> 0.06 s -> 0.06 s -> 0.11 s (+87%) | 49.5 ms -> 57.4 ms -> 59.4 ms -> 111.4 ms (+87%) | 70.3 ms -> 62.1 ms -> 64.1 ms -> 115.9 ms (+81%) | - | - |
| rag.py eval | before | 8.63 s | - | - | - | - |
| rag.py eval | current | 0.71 s -> 0.79 s -> 3.97 s -> 2.24 s -> 2.81 s (+25%) | 786.7 ms -> 3970.3 ms -> 2236.0 ms -> 2805.4 ms (+25%) | 788.7 ms -> 3987.3 ms -> 2255.6 ms -> 2808.6 ms (+25%) | - | - |
| rag.py search | before | 0.29 s | - | - | - | - |
| rag.py search | current | 0.05 s -> 0.04 s -> 0.05 s -> 0.05 s -> 0.05 s (-3%) | 39.3 ms -> 50.7 ms -> 52.4 ms -> 50.9 ms (-3%) | 40.2 ms -> 51.8 ms -> 52.9 ms -> 51.7 ms (-2%) | - | - |
| MCP session (12 calls) | before | 4.04 s | - | - | - | - |
| MCP session (12 calls) | current | 1.63 s -> 2.06 s -> 2.76 s -> 2.84 s -> 4.19 s (+48%) | 2055.5 ms -> 2761.8 ms -> 2842.6 ms -> 4193.7 ms (+48%) | 2080.3 ms -> 2995.9 ms -> 3112.1 ms -> 4917.4 ms (+58%) | - | - |
| kbgit.py check-trailers (30 commits) | before | 0.77-0.95 s | - | - | - | - |
| kbgit.py check-trailers (30 commits) | current | 0.41 s -> 0.21 s -> 1.93 s -> 0.16 s -> 0.21 s (+29%) | 211.6 ms -> 1926.6 ms -> 158.8 ms -> 205.3 ms (+29%) | 235.0 ms -> 1963.5 ms -> 198.8 ms -> 239.6 ms (+21%) | - | - |
| index build | before | - | - | - | - | - |
| index build | current | about 3 s, 24 MB -> 2.17 s -> 3.76 s -> 3.87 s -> 4.66 s (+21%) | - | - | - | 32.5 MB -> 108.0 MB -> 109.0 MB -> 130.6 MB (+20%) |
| pack in-process, warm | current | - | 3.0 ms -> 2.9 ms -> 2.9 ms -> 3.1 ms -> 3.6 ms (+18%) | 4.5 ms -> 6.6 ms -> 5.8 ms -> 6.1 ms -> 7.1 ms (+17%) | - | - |
| MCP server start (initialize reply) | current | - | 32.0 ms -> 29.7 ms -> 52.0 ms -> 51.8 ms -> 49.9 ms (-4%) | 30.2 ms -> 52.9 ms -> 51.9 ms -> 50.6 ms (-3%) | - | - |
| 1,000 random packs | current | - | - | - | 3.30 s -> 2.47 s -> 2.69 s -> 2.83 s -> 3.18 s (+12%) | - |
<!-- /bench -->

What it shows: with 359 topics on macOS (2026-10-12), a cold `rag.py pack` takes 110 ms, the `kb:` hook 111 ms, `search` 51 ms and `eval` (621 questions) 2.8 s. The cold `pack` and the hook took 56 ms and 59 ms with 300 topics (2026-10-09) and about twice that now, the same in two runs of the day (110 ms and 139 ms); the persisted index grew by 18% in lines and 20% in size (130.6 MB), which does not account for a doubling. The doubling is the freshness stamp's: timed at each merge commit, the cold `pack` read 56.8 ms before it and 110.2 ms at the commit that merged it, and moved by 2.2 ms or less at every other change, the router and the `check:` lines among them (the table in "Since the records of 2026-10-08 and 2026-10-09"). `search` did not move. `eval` took 2.2 s over 574 questions on 2026-10-09 and 3.97 s on 2026-10-08 (0.79 s over 250 on 2026-09-28): the `_self` view holds each anchored tested question's informative words once instead of reading the index for them on every pack, and now 2.8 s over 621. `check-trailers` over 30 commits takes 0.21 s, as on 2026-10-09 (0.16 s) and 2026-09-28 (0.21 s) and where the run of 2026-10-08 took 1.93 s: it had grown to about three git processes per commit (the KB-Work checks asked git for origin/main, its ancestry and the item files once per commit), and now reads a range in a fixed number of git calls, so the number of git processes no longer grows with the count of commits. An MCP session of 12 calls takes 4.2 s (2.8 s on 2026-10-09) and the server answers `initialize` in 50 ms; an index build takes 4.7 s and 130.6 MB. In process a warm `pack` takes 3.6 ms at the median and 7.1 ms at p95, and 1,000 random packs 3.2 s. The history's `before` column is the corpus rebuilt by every process; nothing measured here needs it again.

### Freshness of the cited sources

**Setup:** `python3 _tools/benchmarks.py run freshness --sample 5` (no model, no paid run): each answerable row of the question pool (route `good`; 5 rows of each kind, drawn with seed 11, from the public file and, on a host that has it, the query-log file) is looked up with `kbfacts.pack_many(..., revalidate=True)`, so the cited sources of the printed fact lines are asked live within each provider's pacing and the revalidation's 90 s budget, and the printed lines that carry a `DOC` tag are counted by the outcome the lookup prints: `current`, `moved`, `not found`, `source-dated only` (the fact has no located anchor, so only its source's state is known) or `not checked` (none of the sources it cites could be asked). A line counts under the host of the source whose outcome it prints (of several sources, the worst). `requests` counts every request made during the lookups at `provider.request`, those to hosts no line cites included (the GitHub API a pinned repository is asked through, a search); `median_s` and `p95_s` are the wall time of a whole lookup (the pack and its revalidation), over the questions that cite the host, and the `all` row's over every question. `python3 _tools/benchmarks.py run freshness --dry-run` prints the sources and the requests a run would make (one per source per question as the least) and asks nothing. A source asked again within its provider's pacing is answered from the stored check of the lookup before (`cached`, 18 of the 308 source checks of the run).

<!-- bench:records freshness -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-10-12 | 2026-10-12 | 9dabbdb | 2.1.296 | 359 | 1 | - |
<!-- /bench -->

<!-- bench:table freshness metrics=doc_lines,current,moved,not_found,source_dated_only,not_checked -->
| case | arm | doc_lines | current | moved | not_found | source_dated_only | not_checked |
|---|---|---|---|---|---|---|---|
| all | current | 387 | 227 | 15 | 9 | 134 | 2 |
| api.github.com | current | 6 | 0 | 0 | 0 | 6 | 0 |
| code.claude.com | current | 94 | 61 | 13 | 0 | 20 | 0 |
| curia.europa.eu | current | 1 | 0 | 0 | 1 | 0 | 0 |
| docs.ansible.com | current | 2 | 1 | 0 | 0 | 1 | 0 |
| docs.github.com | current | 5 | 3 | 0 | 0 | 2 | 0 |
| docs.gitlab.com | current | 1 | 0 | 0 | 0 | 1 | 0 |
| docs.langchain.com | current | 5 | 0 | 0 | 0 | 5 | 0 |
| download.microsoft.com | current | 2 | 0 | 0 | 2 | 0 | 0 |
| eur-lex.europa.eu | current | 2 | 0 | 0 | 0 | 0 | 2 |
| github.com | current | 2 | 0 | 0 | 0 | 2 | 0 |
| gitlab.com | current | 32 | 20 | 0 | 0 | 12 | 0 |
| learn.microsoft.com | current | 159 | 88 | 0 | 3 | 68 | 0 |
| platform.claude.com | current | 2 | 0 | 2 | 0 | 0 | 0 |
| pypi.org | current | 2 | 0 | 0 | 1 | 1 | 0 |
| raw.githubusercontent.com | current | 65 | 52 | 0 | 0 | 13 | 0 |
| support.microsoft.com | current | 1 | 1 | 0 | 0 | 0 | 0 |
| techcommunity.microsoft.com | current | 4 | 0 | 0 | 2 | 2 | 0 |
| www.anthropic.com | current | 1 | 1 | 0 | 0 | 0 | 0 |
| www.edpb.europa.eu | current | 1 | 0 | 0 | 0 | 1 | 0 |
<!-- /bench -->

<!-- bench:table freshness metrics=current_share,moved_share,source_dated_only_share,requests,failed_requests,median_s,p95_s -->
| case | arm | current_share | moved_share | source_dated_only_share | requests | failed_requests | median_s | p95_s |
|---|---|---|---|---|---|---|---|---|
| all | current | 58.7% | 3.9% | 34.6% | 278 | 0 | 3.13 s | 7.88 s |
| api.github.com | current | 0.0% | 0.0% | 100.0% | 7 | 0 | 6.97 s | 6.97 s |
| code.claude.com | current | 64.9% | 13.8% | 21.3% | 60 | 0 | 4.54 s | 7.38 s |
| curia.europa.eu | current | 0.0% | 0.0% | 0.0% | 1 | 0 | 1.73 s | 1.73 s |
| docs.ansible.com | current | 50.0% | 0.0% | 50.0% | 3 | 0 | 2.99 s | 2.99 s |
| docs.github.com | current | 60.0% | 0.0% | 40.0% | 4 | 0 | 6.96 s | 7.64 s |
| docs.gitlab.com | current | 0.0% | 0.0% | 100.0% | 2 | 0 | 2.41 s | 2.41 s |
| docs.langchain.com | current | 0.0% | 0.0% | 100.0% | 3 | 0 | 4.25 s | 4.25 s |
| download.microsoft.com | current | 0.0% | 0.0% | 0.0% | 3 | 0 | 6.79 s | 6.79 s |
| eur-lex.europa.eu | current | 0.0% | 0.0% | 0.0% | 2 | 0 | 1.73 s | 1.73 s |
| github.com | current | 0.0% | 0.0% | 100.0% | 5 | 0 | 1.30 s | 1.30 s |
| gitlab.com | current | 62.5% | 0.0% | 37.5% | 6 | 0 | 1.59 s | 2.41 s |
| learn.microsoft.com | current | 55.3% | 0.0% | 42.8% | 116 | 0 | 3.12 s | 10.40 s |
| platform.claude.com | current | 0.0% | 100.0% | 0.0% | 4 | 0 | 3.39 s | 3.64 s |
| pypi.org | current | 0.0% | 0.0% | 50.0% | 7 | 0 | 5.61 s | 6.97 s |
| raw.githubusercontent.com | current | 80.0% | 0.0% | 20.0% | 28 | 0 | 2.10 s | 10.40 s |
| support.microsoft.com | current | 100.0% | 0.0% | 0.0% | 2 | 0 | 1.96 s | 1.96 s |
| techcommunity.microsoft.com | current | 0.0% | 0.0% | 50.0% | 8 | 0 | 7.30 s | 22.07 s |
| www.anthropic.com | current | 100.0% | 0.0% | 0.0% | 1 | 0 | 1.79 s | 1.79 s |
| www.edpb.europa.eu | current | 0.0% | 0.0% | 100.0% | 2 | 0 | 1.73 s | 1.73 s |
| docs.rs | current | - | - | - | 6 | 0 | - | - |
| scrumguides.org | current | - | - | - | 1 | 0 | - | - |
| support.atlassian.com | current | - | - | - | 3 | 0 | - | - |
| zenchong.substack.com | current | - | - | - | 4 | 0 | - | - |
<!-- /bench -->

<!-- bench:table freshness metrics=questions,max_s,budget_spent,sources_live,sources_cached,sources_offline cases=all -->
| case | arm | questions | max_s | budget_spent | sources_live | sources_cached | sources_offline |
|---|---|---|---|---|---|---|---|
| all | current | 54 | 22.07 s | 0 | 288 | 18 | 2 |
<!-- /bench -->

What it shows: of the 387 printed DOC lines over 54 questions, 227 (58.7%) were current at their source, 15 (3.9%) had moved, 9 were not found, 134 (34.6%) were dated at their source only and 2 could not be checked. The earlier run of the same day read 310 lines over 44 questions: 193 (62.3%) current, 12 moved, 8 not found, 95 (30.6%) dated at their source only and 2 not checked. All 15 `moved` lines are Claude Code's pages (13 of `code.claude.com`'s 94 lines, 2 of `platform.claude.com`'s 2); `learn.microsoft.com`, with 159 lines, has 88 current, 68 source-dated only and 3 not found, and the pinned `raw.githubusercontent.com` pages 52 current of 65. The run made 278 requests, all of which got an HTTP answer. A lookup took 3.13 s at the median and 7.88 s at p95, and the slowest, 22.07 s, cited `techcommunity.microsoft.com`; no lookup used up its 90 s budget (`budget_spent` 0), so the budget stands with more than four times the slowest lookup's time. `techcommunity.microsoft.com`'s pages are client-rendered: the fetch extracts no text from the page or from its made-up sibling, so each source asked answers `soft-404` and its lines print `not found`.

## The query log and the newer tools

These scenarios have no history: they measure what was built after the last runs.

### Query log hooks

**Setup:** `python3 _tools/benchmarks.py run querylog-hooks`: each hook command through `sh _tools/kbpy` of a throwaway clone, its query log in mode `local` under a scratch plugin data directory: `capture` on a `kb:` prompt, a `kb_pack` call and a `Stop` (30 runs each; async hooks, so no prompt waits on them), the two synchronous `UserPromptSubmit` hooks on a prompt without `kb:`, the `SessionEnd` launcher with nothing waiting and with a closed session to distill (20 each; the second starts a detached distill, whose `claude` here fails at once, so no model runs), and the weekly digest hook; the query log at `PIPELINE_VERSION` 3. The always-on context of the hooks is in "Always-on cost".

<!-- bench:records querylog-hooks -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | 8d9ada4 | 2.1.283 | 271 | 30 | - |
<!-- /bench -->

<!-- bench:table querylog-hooks metrics=median_ms,p95_ms,max_ms -->
| case | arm | median_ms | p95_ms | max_ms |
|---|---|---|---|---|
| capture, UserPromptSubmit | async hook | 48.9 ms | 50.0 ms | - |
| capture, PostToolUse (kb_pack) | async hook | 48.8 ms | 49.7 ms | - |
| capture, Stop | async hook | 49.0 ms | 49.5 ms | - |
| kb_hook.py, a prompt without kb: | sync hook | 17.8 ms | 18.2 ms | - |
| kb_change_router.py, a question | sync hook (clone only) | 17.7 ms | 18.3 ms | - |
| SessionEnd launcher, nothing waiting | sync hook | 47.3 ms | 48.1 ms | - |
| SessionEnd launcher, a session to distill | sync hook | 50.0 ms | 50.7 ms | - |
| SessionEnd launcher | sync hook | - | - | 51.1 ms |
| digest --hook | sync hook | 52.0 ms | 54.2 ms | - |
<!-- /bench -->

What it shows:
- **The `SessionEnd` launcher returns in 47-50 ms at the median and 51 ms at worst,** about a tenth of `LAUNCH_BUDGET_S` (500 ms), also when it starts a detached distill.
- `capture` takes 49 ms per event, all of it Python's start and the module's import; it runs async, so no prompt waits on it.
- The synchronous `UserPromptSubmit` hooks add 17 ms each to a prompt without `kb:` (`kb_hook.py`, and in a clone the change router); the weekly digest hook 52 ms.

### Distill, learn and apply

**Setup:** `python3 _tools/benchmarks.py run querylog-pipeline`: `distill --replay` over the fixture spool (`_tools/fixtures/querylog/`) with the recorded Haiku replies, 5 runs; `learn` and `apply` on the fixture store in a throwaway clone (mode `local`), with the adoption gates' numbers (`rag.py eval`, mean pack, off-kb `good`) before and after, and what the gates refused; then one `distill` of the same spool with the real Haiku, through a `claude` shim that logs each call's usage. The rows name `PIPELINE_VERSION` (3: an entry holds the kb's own question and its citations, and Haiku only judges).

<!-- bench:records querylog-pipeline -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | 8d9ada4 | 2.1.283 | 271 | 1 | $0.03 |
<!-- /bench -->

<!-- bench:table querylog-pipeline metrics=median_ms,s,entries,finding_records,eval_passed,eval_rows,mean_pack_chars,offkb_good,rejected,failed: eval fails,failed: off-kb good rises,failed: mean pack grows,haiku_calls,entries_sent,input_per_entry,out_per_entry,cost -->
| case | arm | median_ms | s | entries | finding_records | eval_passed | eval_rows | mean_pack_chars | offkb_good | rejected | failed: eval fails | failed: off-kb good rises | failed: mean pack grows | haiku_calls | entries_sent | input_per_entry | out_per_entry | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| distill (recorded Haiku) | fixtures | 4074.5 ms | - | 4 | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| learn | fixtures | - | 0.13 s | - | 9 | - | - | - | - | - | - | - | - | - | - | - | - | - |
| apply | fixtures | - | 24.88 s | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| adoption gates | before apply | - | - | - | - | 250 | 250 | 3,362 | 15 | - | - | - | - | - | - | - | - | - |
| adoption gates | after apply | - | - | - | - | 250 | 250 | 3,362 | 15 | - | - | - | - | - | - | - | - | - |
| adoption gates | candidates | - | - | - | - | - | - | - | - | 5 | 4 | 1 | 0 | - | - | - | - | - |
| apply outcomes | alias | - | - | - | - | - | - | - | - | 1 | - | - | - | - | - | - | - | - |
| apply outcomes | expansion | - | - | - | - | - | - | - | - | 1 | - | - | - | - | - | - | - | - |
| distill (real Haiku) | fixtures | - | 29.97 s | - | - | - | - | - | - | - | - | - | - | 1 | 6 | 1,208 | 435 | $0.028 |
<!-- /bench -->

<!-- bench:table querylog-pipeline metrics=open,rejected,no-fix,fixed-since,applied cases=apply outcomes -->
| case | arm | open | rejected | no-fix | fixed-since | applied |
|---|---|---|---|---|---|---|
| apply outcomes | alias | - | 1 | - | - | - |
| apply outcomes | eval | - | - | 2 | 1 | - |
| apply outcomes | expansion | - | 1 | - | - | - |
| apply outcomes | gap | 1 | - | - | - | - |
| apply outcomes | source | 3 | - | - | - | - |
<!-- /bench -->

What it shows:
- **Run time:** `distill` of the fixture spool takes 4.1 s with the recorded replies (4 entries; most of it the redaction allowlist's load, see "Redaction speed"), `learn` 0.13 s and `apply` 24.9 s, which is the adoption gates: each candidate costs a full `rag.py eval` and off-kb run.
- **The adoption gates refused all 5 candidates** of the fixture store: 4 because an eval question failed with them, 1 because it raised off-kb `good` from 15 to 16. So the eval set stayed at 250 of 250, the mean pack at 3,362 characters and off-kb `good` at 15, and no file changed.
- **Haiku tokens per entry:** one real batch of the 6 entries with text took 1,208 input and 435 output tokens per entry, $0.028 in all, in 30 s; 3 entries were written, the rest dropped by the rules or waiting.

### Redaction speed

**Setup:** `python3 _tools/benchmarks.py run redaction`: `redact.known()` (the public root read once as the allowlist), then `redact()` and the leak scan over every prompt, answer and question of the query log fixtures, 20 times over, in process, at `PIPELINE_VERSION` 3.

<!-- bench:records redaction -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | 8d9ada4 | 2.1.283 | 271 | 740 | - |
<!-- /bench -->

<!-- bench:table redaction metrics=s,median_us,chars_per_s -->
| case | arm | s | median_us | chars_per_s |
|---|---|---|---|---|
| allowlist load (known()) | rules | 4.09 s | - | - |
| redact() | rules | - | 14.6 us | 3,759,641 |
| leak scan | rules | - | - | 7,177,615 |
<!-- /bench -->

What it shows: the rules redact 3.8M characters a second (a median entry in 15 us) and the leak scan reads 7.2M a second; the one fixed cost is `known()`, which reads the public root once per process: 4.1 s. A distill pays it once per run, which is most of its 4.1 s on the fixtures.

### Research cost per accepted fact

**Setup:** `python3 _tools/benchmarks.py run research`: a throwaway clone (mode `local`, research on with 1 run a day, a local bare `origin`), a one-entry store whose question the LAPS article leads for without answering (Windows Server 2012 R2 and Azure backup), then `learn` and `apply --clone`: the gap step writes a `_gaps.md` entry and research runs once on Sonnet, its usage logged by a `claude` shim; the quote check fetches the cited page.

<!-- bench:records research -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | b166082 | 2.1.283 | 271 | 1 | $0.21 |
<!-- /bench -->

<!-- bench:table research metrics=s,research_runs,cost,input,facts_accepted,conflict_lines,gap_lines,cost_per_fact -->
| case | arm | s | research_runs | cost | input | facts_accepted | conflict_lines | gap_lines | cost_per_fact |
|---|---|---|---|---|---|---|---|---|---|
| apply with research | sonnet | 37.24 s | 1 | $0.205 | 112,904 | 2 | 0 | 1 | $0.103 |
<!-- /bench -->

What it shows: one research run on Sonnet read the LAPS pages for $0.205 (112.9k input, 37 s for the whole apply), and 2 candidate facts passed the gates and their quote checks: **$0.10 per accepted fact**. The gap step wrote its `_gaps.md` entry first; no conflict was found. Distill and apply cost nothing beside it.

### /kb-ingest on a sample repository

**Setup:** `python3 _tools/benchmarks.py run ingest`: `pypa/sampleproject` at `621e4974ca25ce531773def586ba3ed8e736b3fc`, surveyed with `kbingest.py survey --files` (3 runs), then `/kb-ingest` in a headless Sonnet session (hooks off, `--permission-mode bypassPermissions`, `--max-budget-usd 4`) in a throwaway clone, the skill's questions answered in the prompt: a new public root `sample`, one topic.

<!-- bench:records ingest -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | 654c8ad | 2.1.283 | 271 | 1 | $2.06 |
<!-- /bench -->

<!-- bench:table ingest metrics=median_ms,files_kept,files_left_out,cost,wall_s,turns,tool_calls,facts_written,check_errors -->
| case | arm | median_ms | files_kept | files_left_out | cost | wall_s | turns | tool_calls | facts_written | check_errors |
|---|---|---|---|---|---|---|---|---|---|---|
| kbingest.py survey | sampleproject | 126.1 ms | 12 | 0 | - | - | - | - | - | - |
| /kb-ingest | sonnet | - | - | - | $2.056 | 562 s | 87 | 86 | 18 | 0 |
<!-- /bench -->

What it shows: the survey of the 12-file repository takes 0.13 s and left nothing out; the skill then wrote the new root and one topic with 18 facts in 87 turns, 562 s and $2.06, and `check.py` reported no error. The paid part is the reading and writing, not the survey.

### A host plugin with team roots

**Setup:** `python3 _tools/benchmarks.py run host-roots`: a fork (a throwaway clone) with a `team` root (`kbroot.py add team --prefix TM --visibility internal`) and one article, the question of `kb/_self/reports/host-plugin-roots.md` spanning both roots, asked on Haiku in an empty host with the fork loaded by `--plugin-dir`, and with the team root served by `KB_ROOTS` (`--mcp-config`, `--strict-mcp-config`), 2 runs each; and the fork's server over stdio. Checks: the naming rule, "cannot be removed", and a citation from each root. The installed-plugin mode of that report is not run here: installing writes the installed plugin's data directory under `~/.claude`.

<!-- bench:records host-roots -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | 287f380 | 2.1.283 | 271 | 2 | $0.11 |
<!-- /bench -->

<!-- bench:table host-roots metrics=cost,wall_s,turns,checks,errors,coverage,roots_in_pack -->
| case | arm | cost | wall_s | turns | checks | errors | coverage | roots_in_pack |
|---|---|---|---|---|---|---|---|---|
| fork | check.py | - | - | - | - | 0 | - | - |
| both roots | --plugin-dir | $0.031 | 18 s | 4.5 | 3/8 | - | - | - |
| both roots | KB_ROOTS | $0.022 | 11 s | 2.5 | 8/8 | - | - | - |
| server over stdio | no model | - | - | - | - | - | good | 2 |
<!-- /bench -->

What it shows: the fork's server over stdio packs both roots with `coverage: good`, so the pack side works. Haiku is less steady than in `kb/_self/reports/host-plugin-roots.md`: over this run and the one before it (checks then asked for paths), one of four `--plugin-dir` runs and one of four `KB_ROOTS` runs said the kb did not cover the team's rule after a `good` pack; the other runs answered both parts and cited both roots. This run: `KB_ROOTS` 8/8, `--plugin-dir` 3/8.

### Hook launcher start-up

**Setup:** `python3 _tools/benchmarks.py run kbpy`: a script that does nothing, run 50 times by `python3` directly and by `sh _tools/kbpy`, on this machine (macOS). Linux and Windows (Git Bash, where `kbpy` probes each interpreter before running it) are not measured.

<!-- bench:records kbpy -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-28 | 2026-09-28 | 287f380 | 2.1.283 | 271 | 50 | - |
<!-- /bench -->

<!-- bench:table kbpy metrics=median_ms,p95_ms -->
| case | arm | median_ms | p95_ms |
|---|---|---|---|
| python3 noop.py | Darwin | 9.6 ms | 10.5 ms |
| sh _tools/kbpy noop.py | Darwin | 13.1 ms | 15.6 ms |
| launcher overhead | Darwin | 3.5 ms | - |
<!-- /bench -->

What it shows: `sh _tools/kbpy` adds 3.5 ms at the median to a Python start of 9.6 ms on macOS (13.1 ms against 9.6 ms). On Windows it probes each interpreter before running it, which this machine cannot measure.

## The code

### Finding the code

**Setup:** `python3 _tools/benchmarks.py run navigation`, or `python3 _tools/benchmarks.py run navigation --arm ARM --reps 3`: what it costs an agent to find the code and the tests of a rule in this repository's tools. Three questions, each put to a fresh Sonnet session in a throwaway clone of `HEAD` (query log off, origin a local bare repository), hooks off, no MCP servers, no subagents, no web; Read, Grep, Glob, a few read-only shell commands (`git grep`, `grep`, `ls`, `cat`, `head`, `tail`, `sed -n`, `wc`) and the kb's own `rag.py` and `selfdoc.py` are allowed, and Edit and Write are not:
- `N1`: the query log's automatic push reads a GitLab pipeline by its jobs, not its status, to decide whether the pushed commit is red; which function decides that and which tests pin it.
- `N2`: `kbgit.py sync --push` sends a range that changes code to a merge-request branch named after a work id; which function plans that and which test pins the id.
- `N3`: a benchmark scenario holds the router to a cost bar that depends on the verdict of the pack; which function decides whether the bar holds and which tests pin it.

Each question asks for function and test names only, and an answer is checked by those names, never by a file path: it is right when it names the case's function and at least one of the tests that pin the rule (`benchmarks.NAV`), so the same three questions score the code after a file moves or a module splits, and a test (`test_navigation_answers_name_code_that_exists_and_the_prompts_do_not_name_it`) fails when a name stops being defined anywhere under `_tools/` or a prompt gives it away. The scenario writes one row set per case and arm: `turns`, `tool_calls`, `files_read` and `input` (means over `--reps` runs), `checks` (the functions and the tests named right, two checks per run), and the sums of the three cases under `N1-N3`. `files_read` is counted from the run's own tool calls: the distinct files of its Read calls, of a Grep or Glob whose path is a file, and of the file names in its shell commands; a search over a directory or a wildcard reads no one file, so the count is a floor.

`--arm` names the arm of the rows (default `current`); a run replaces only the rows of its own arm for the day, so two arms run on one date (a layout before and after a change) both stay in `kb/_self/reports/benchmarks.csv`, and their spend adds up in the spend table. To measure a layout, check out its commit and run the scenario there: the clone is of that checkout's `HEAD`. The scenario's tests run no model (`python3 _tools/tests.py -k navigation`); the stream they read is synthetic, like `agent_bench.py`'s.

<!-- bench:records navigation -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 2026-09-30 (before) | 2026-09-30 | f2509b1 | 2.1.286 | 292 | 3 | $0.70 |
| 2026-09-30 (after) | 2026-09-30 | 0c375fc | 2.1.286 | 292 | 3 | $0.74 |
<!-- /bench -->

<!-- bench:table navigation metrics=turns,tool_calls,files_read,input,cost,wall_s,checks -->
| case | arm | turns | tool_calls | files_read | input | cost | wall_s | checks |
|---|---|---|---|---|---|---|---|---|
| N1 | before | 4.3 | 3.3 | 1.7 | 100,548 | $0.094 | 12 s | 6/6 |
| N2 | before | 6.3 | 5.3 | 2.3 | 140,379 | $0.076 | 15 s | 6/6 |
| N3 | before | 4.3 | 3.3 | 1.7 | 100,096 | $0.063 | 14 s | 6/6 |
| N1-N3 | before | 15 | 12 | 5.7 | 341,022 | - | - | - |
| N1 | after | 4.7 | 3.7 | 2 | 112,620 | $0.100 | 12 s | 6/6 |
| N2 | after | 6 | 5 | 2.7 | 131,700 | $0.073 | 14 s | 6/6 |
| N3 | after | 6 | 5 | 2 | 112,320 | $0.074 | 13 s | 6/6 |
| N1-N3 | after | 16.7 | 13.7 | 6.7 | 356,640 | - | - | - |
<!-- /bench -->

What it shows:
- **The baseline:** arm `before`, 3 runs per question on Sonnet 5.5 (`claude-sonnet-5-5`) with Claude Code 2.1.286, at commit `f2509b1`, the last commit of `main` before any file of the sprint "Codebase maintainability proven" moved, so the tools are still the flat modules the later arms are compared with. Nine runs cost $0.70.
- **Every answer was right:** all nine named the case's function and a test that pins the rule (6/6 checks in each case), so the arm has no room left on correctness and a later layout can differ only in what it costs to get there.
- **What finding the code costs here:** N1 and N3 took 4.3 turns and 3.3 tool calls on average, N2 took 6.3 turns and 5.3 tool calls; the three questions together took 15 turns, 12 tool calls and 341k input tokens, at 12-15 s and $0.063-0.094 per run on average. Seven of the nine runs began with a `Grep` for a word of the question and two with a shell search, then read one to three files; the files read are a floor, since a search over a directory counts no file.
- **Noise:** the cells are means of 3 runs, and the runs of one case differ by up to 3 turns (N1 3-6, N2 5-7, N3 3-5) and by a factor of 2-3 in cost, so a later arm that moves a mean by about that much has shown nothing.
- **The split:** arm `after`, the same three questions, 3 runs each, Sonnet 5.5 with Claude Code 2.1.286, at commit `0c375fc`, the tip of `main` once the flat modules were split: `kbgit.py`'s merge into `kg_merge.py` and `kg_base.py`, `benchmarks.py` into the `bench_*.py` modules, `test_querylog.py` into `test_ql_*.py` and `ql_testkit.py`, and `test_kb.py` into `test_kb_cohesion.py`, `test_kb_lookup.py`, `test_kb_ids.py` and `test_kb_leaks.py`. The function and test names are unchanged, so the same answer checks apply. Nine runs cost $0.74.
- **Every answer was right again:** 6/6 checks in each case, so the arms differ only in what the route cost.
- **The change, after against before (means of 3 runs per case, the total is the sum of the three cases):**

| case | turns | tool calls | files read | input tokens |
|---|---|---|---|---|
| N1 | 4.3 to 4.7 (+0.3) | 3.3 to 3.7 (+0.3) | 1.7 to 2 (+0.3) | 100,548 to 112,620 (+12%) |
| N2 | 6.3 to 6 (-0.3) | 5.3 to 5 (-0.3) | 2.3 to 2.7 (+0.3) | 140,379 to 131,700 (-6%) |
| N3 | 4.3 to 6 (+1.7) | 3.3 to 5 (+1.7) | 1.7 to 2 (+0.3) | 100,096 to 112,320 (+12%) |
| N1-N3 | 15 to 16.7 (+1.7, +11%) | 12 to 13.7 (+1.7, +14%) | 5.7 to 6.7 (+1, +18%) | 341,022 to 356,640 (+15,618, +5%) |

- **Noise:** the runs of one case differ by up to 3 turns in both arms (after: N1 4-5, N2 5-8, N3 5-7), and the input of one run by up to a factor of 2 (N2 after 105k-177k, before 81k-178k). Taking one run of each case together as a total, the three totals were 16, 16 and 13 turns before and 15, 15 and 20 after, so the spread between runs of one arm (a standard deviation of 1.7 turns before and 2.9 after) is as large as the difference between the arms, 1.7 turns; the standard error of that difference is about 1.9 turns, 0.75 files and 46k input tokens. No metric's difference exceeds its spread. All four means are higher after than before and N2 is lower on turns, tool calls and input, but with 3 runs per arm that direction is no evidence of a cost: the data show neither a gain nor a loss. Three runs of three questions cannot show a change below about 2 turns in the total.
- **Files read:** the files read per run were 2 in every N1 and N3 run after (before: 1-3 and 1-2) and 2-3 in N2 (before 2-3), about a third of a file more per case on average but with less spread between runs. The count is a floor, since a search over a directory counts no file, and one file more per question is within what a single run's route changes.

Verdict: stop splitting. The split did not make the code cheaper to find in these nine runs (16.7 turns, 13.7 tool calls, 6.7 files and 357k input tokens after, against 15, 12, 5.7 and 341k before, all within the run-to-run spread), and with every answer right in both arms there is no navigation cost left for a further split to remove, so splitting `kbfacts.py`, `factdiff.py` and `backlog.py` has no measured payoff to claim; split them only for a reason other than navigation.
