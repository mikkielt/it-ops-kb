# Benchmarks

What a kb lookup costs an agent, against the same agent without the kb, and what each of the kb's techniques and tools costs or saves. `kb/_self/design.md` draws the conclusions and `kb/_self/token-efficiency.md` lists the techniques; `kb/_self/reports/fact-diff.md` holds the fact diff's measurements.

- **Data:** every number is a row of `kb/_self/reports/benchmarks.csv`, one row per scenario, record, case, arm and metric. A record is one measurement: the date of a run of `_tools/benchmarks.py`, or, for the numbers of the reports this one replaced, the commit that wrote them (found with `git log -S` and `git blame`), with its date, the Claude Code version and the kb size its setup stated (empty where it stated none). The historical rows keep each cell as written (`$0.043 / $0.051` for two runs); a number those reports gave only in prose is a row with metric `text` and its sentence in `note`. The 2026-09-28 runs name the commit of the runner they ran; the runs of all scenarios but the query log's ran before `c038ae6` (the query log's entry change) was under them, which changes no file those scenarios read.
- **Tables:** every table below between `bench:` markers is generated from the results file by `python3 _tools/benchmarks.py report`; `report --check` (a test in `_tools/tests.py`) fails when a table, or a number in `README.md`, disagrees with it. A cell lists each record's value in date order (`->` between them) and the change of the newest from the one before it; a historical cell of several numbers counts as their mean.
- **Re-run:** `python3 _tools/benchmarks.py run` runs every scenario, `run <scenario>` one; each section names its command. Paid runs are fresh `claude -p` sessions; the rest run no model.
- **Counting:** input is uncached + cache-write + cache-read input tokens, read from each run's result event or transcript, never from an agent's own account. Effective input weights cache writes 2x and cache reads 0.1x. Dollar costs compare only within one batch, since the run that pays a cache write varies; compare tokens across batches.
- **Isolation:** every `claude -p` runs with hooks off (`--settings '{"disableAllHooks": true}'`) from a throwaway clone of `HEAD` whose query log is `off` and whose `origin` is a local bare repository; the kb and docs servers are registered at local scope for that clone and removed afterwards. The scenarios that measure the query log's hooks run them in a throwaway clone in mode `local` with a local bare `origin`, or as a copy of the plugin whose hook commands write under the scratch directory instead of `~/.claude/plugins/data/`. The historical runs had hooks on; a hook adds no context unless it prints, which the query log's never do.
- **Repetitions:** the re-run uses 1 run per cell where the history used 2, except where a section says otherwise; the history's run-to-run spread (in its cells) is the noise a single run carries. Re-runs on this machine, with other work on it: timings moved by up to 15% (`capture`'s median 47-55 ms over four runs of `querylog-hooks`), `always-on`'s token counts by under 0.1% (8 tokens). Model aliases resolved to Haiku 4.5, Sonnet 5 and Opus 5.5. From Claude Code 2.1.284 `sonnet` resolves to Sonnet 5.5, so a re-run's Sonnet arms change model; "A new model against the one it replaces" compares the two pinned by id.

Spend of the runs of each scenario, per record (paid `claude -p` runs, the Haiku and Sonnet calls made through the query log's own commands included):

<!-- bench:spend -->
| scenario | record | paid runs | input tokens | output tokens | spend |
|---|---|---|---|---|---|
| always-on | 2026-09-28 | 20 | 469,228 | 1,118 | $0.12 |
| doc2query | 2026-09-28 | 2 | 24,579 | 4,271 | $0.10 |
| files-headless | 2026-09-28 | 14 | 2,157,090 | 14,845 | $1.74 |
| files-subagents | 2026-09-28 | 11 | 362,274 | 8,113 | $1.35 |
| headless | 2026-09-28 | 67 | 5,782,044 | 85,290 | $8.10 |
| host-lookups | 2026-09-28 | 16 | 1,304,536 | 14,136 | $1.50 |
| host-roots | 2026-09-28 | 4 | 340,570 | 3,921 | $0.11 |
| howto | 2026-09-28 | 6 | 690,606 | 6,422 | $0.50 |
| ingest | 2026-09-28 | 1 | 6,947,437 | 26,909 | $2.06 |
| kb-lookup-agent | 2026-09-28 | 3 | 74,652 | 845 | $0.12 |
| models | 2026-09-28 | 28 | 2,788,545 | 26,211 | $4.01 |
| navigation | 2026-09-30 | 18 | 2,092,986 | 17,421 | $1.44 |
| new-model | 2026-09-28 | 60 | 6,125,840 | 59,832 | $6.62 |
| partial | 2026-09-28 | 13 | 2,522,765 | 21,392 | $1.79 |
| querylog-pipeline | 2026-09-28 | 1 | 7,250 | 2,608 | $0.03 |
| research | 2026-09-28 | 1 | 112,904 | 2,809 | $0.21 |
| retrieval | 2026-09-28 | 1 | 16,352 | 3,331 | $0.07 |
| route-by-verdict | 2026-09-29 | 36 | 2,723,008 | 57,099 | $3.73 |
| router | 2026-09-28 | 22 | 358,198 | 8,244 | $0.30 |
| subagents | 2026-09-28 | 24 | 724,378 | 23,213 | $3.30 |
| all | | 348 | 35,625,242 | 388,030 | $37.18 |
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

**Setup:** `python3 _tools/benchmarks.py run route-by-verdict`: `kb_ask.py`'s routing (`agent_bench.py` config `router-pinned`, which follows `kb_ask.plan`: a good pack to a tool-less Haiku 4.5 reader, a web pack to a Sonnet 5.5 researcher with the docs servers and no kb server, a split pack to the reader and the researcher with their costs summed) against the bare Sonnet 5.5 web arm (`web-sonnet-5-5`: WebSearch and WebFetch, no kb) and the kb Sonnet 5.5 arm (`sonnet-5-5`: the kb and docs servers, following the server instructions), all three pinned by full model name in one batch so that dollars compare. Six questions: `s5_none` and `o1_offkb` (off the kb), `s8_falsegood2` (the Purview false `good`), `h2_applock` (the pack's false `none`), `s1_fact` and `s3_multi` (facts the kb has). Each arm's question is the same; the web arm gets it without "Answer from the kb" and with "Cite the source urls" (`agent_bench.WEB_Q`).

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
<!-- /bench -->

<!-- bench:table partial metrics=cost,input,checks,searches,fetched,live checks,outcome -->
| case | arm | cost | input | checks | searches | fetched | live checks | outcome |
|---|---|---|---|---|---|---|---|---|
| p1_partial | haiku | $0.047, $0.037 -> $0.107 (+155%) | 82k, 111k -> 166,287 (+72%) | 4/4, 4/4 -> 4/4 | 1, 1 -> 2 (+100%) | 0, 0 -> 0 | - | - |
| p1_partial | sonnet | $0.215, $0.110 -> $0.370 (+128%) | 178k, 146k -> 441,925 (+173%) | 4/4, 4/4 -> 4/4 | 1, 1 -> 4 (+300%) | 0, 0 -> 3 | - | - |
| p2_partial | haiku | $0.024, $0.071 -> $0.052 (+9%) | 50k, 129k -> 115,598 (+29%) | 3/4 (no search), 3/4 (answer wrong) -> 3/4 | 0, 1 -> 0 (-100%) | 0, 1 (0) -> 2 (+300%) | - | - |
| p2_partial | sonnet | $0.158, $0.106 -> $0.191 (+45%) | 193k, 139k -> 330,934 (+99%) | 4/4, 4/4 -> 3/4 | 2, 1 -> 4 (+167%) | 0, 0 -> 0 | - | - |
| n1_newer | haiku, before the fixes | $0.020, $0.020 | 49k, 48k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n1_newer | sonnet, before the fixes | $0.065, $0.063 | 96k, 96k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n2_newer | haiku, before the fixes | $0.019, $0.026 | 47k, 95k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n2_newer | sonnet, before the fixes | $0.044, $0.026 | 63k, 95k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| k1_stale | haiku, before the fixes | $0.028, $0.026 | 74k, 96k | 1/3, 1/3 | 0, 0 | 0, 0 | - | - |
| k1_stale | sonnet, before the fixes | $0.061, $0.031 | 98k, 97k | 2/3, 1/3 | 0, 0 | 0, 0 | - | - |
| n1_newer | haiku | $0.010, $0.010 -> $0.023 (+134%) | 51,866 | 1/3, 1/3 -> 1/3 | 0 | 0 | 0, 0 | - |
| n1_newer | sonnet | $0.024, $0.032 -> $0.070 (+151%) | 105,743 | 1/3, 1/3 -> 1/3 | 0 | 0 | 0, 0 | - |
| n2_newer | haiku | $0.019, $0.020 -> $0.025 (+27%) | 75,848 | 1/3, 1/3 -> 0/3 | 0 | 0 | 0, 0 | - |
| n2_newer | sonnet | $0.018, $0.051 -> $0.063 (+83%) | 103,994 | 1/3, 1/3 -> 1/3 | 0 | 0 | 0, 0 | - |
| k1_stale | haiku | $0.015, $0.014 -> $0.054 (+272%) | 27,029 | 2/3, 2/3 -> 2/3 | 0 | 0 | - | - |
| k1_stale | sonnet | $0.059, $0.025 -> $0.091 (+116%) | 176,528 | 2/3, 2/3 -> 2/3 | 0 | 0 | - | - |
| n3_newer | haiku, before the fixes | $0.027 | - | - | - | - | - | no live check, 2.2.361 as the latest, $0.027 |
| n3_newer | haiku | $0.089 -> $0.083 (-6%) | 132,553 | 3/3 | 0 | 1 | - | PyPI fetched, 2.2.364 of 2026-07-22 with the kb's 2.2.361 beside it, $0.089 |
| n3_newer | sonnet, before the fixes | $0.158 | - | - | - | - | - | PyPI fetched, 2.2.364, $0.158 |
| n3_newer | sonnet | $0.141 | - | - | - | - | - | the same, $0.141 |
| n4_newer | haiku, before the fixes | $0.050 | - | - | - | - | - | searched, then "Yes" from a search summary (wrong), $0.050 |
| n4_newer | haiku | $0.122 -> $0.174 (+43%) | 222,145 | 2/3 | 2 | 4 | - | "No", from the tag's tree, $0.122 |
| n4_newer | sonnet, before the fixes | $0.117 | - | - | - | - | - | searched, then "Yes" from the kb's line on `main` read as a release (wrong), $0.117 |
| n4_newer | sonnet | $0.240 -> $0.489 (+104%) | 572,315 | 2/3 | 1 | 11 | - | "No", after 6 fetches, $0.240 |
<!-- /bench -->

What it shows:
- **Partial knowledge still works:** p1 passed 4/4 on both models; p2 3/4 on both (Haiku fetched again a url the pack had cited, Sonnet's answer did not say the log names are undocumented).
- **The freshness and stale-copy lines still reach the answer:** k1 kept 2/3 on both models (the copy reported behind, without calling `kb_status`); n1/n2 "using the kb" stayed inside the kb (1/3, no live check), as after the fixes.
- **With leave to use the web** Haiku checked PyPI on n3 (3/3, $0.083) and both models answered "no" on n4 (2/3), Sonnet after 11 fetches ($0.489). Sonnet's n3 run failed with `529 Overloaded` and has no row.

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

<!-- bench:records host-lookups -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 0659f83 | 2026-09-25 | 0659f83 | 2.1.282 | 188 | - | - |
| 945fb09 | 2026-09-27 | 945fb09 | 2.1.282 | 188 | - | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 1 | $1.50 |
<!-- /bench -->

<!-- bench:table host-lookups metrics=turns,input,out,wall_s,tool_calls,checks,start_ctx -->
| case | arm | turns | input | out | wall_s | tool_calls | checks | start_ctx |
|---|---|---|---|---|---|---|---|---|
| fixed context | host | 1 -> 1 (+0%) | 20.1k -> 30,278 (+51%) | 4 -> 4 (+0%) | 1 s -> 3 s (+210%) | 0 | 0/0 | - |
| fixed context | clone | 1 -> 1 (+0%) | 22.3k -> 34,369 (+54%) | 4 -> 4 (+0%) | 1 s -> 4 s (+310%) | 0 | 0/0 | - |
| T1 | host | 2 -> 2 (+0%) | 42.1k -> 61,792 (+47%) | 561 -> 681 (+21%) | 6 s -> 10 s (+67%) | 1 | 0/0 | - |
| T1 | clone | 2 -> 2 (+0%) | 46.5k -> 70,928 (+53%) | 478 -> 504 (+5%) | 5 s -> 8 s (+50%) | 1 | 0/0 | - |
| T2 | host | 3 -> 3 (+0%) | 62.9k -> 92,230 (+47%) | 589 -> 512 (-13%) | 6 s -> 8 s (+28%) | 2 | 0/0 | - |
| T2 | clone | 3 -> 3 (+0%) | 68.0k -> 104,451 (+54%) | 558 -> 504 (-10%) | 6 s -> 9 s (+47%) | 2 | 0/0 | - |
| T3 | host | 2 -> 2 (+0%) | 43.9k -> 63,263 (+44%) | 1,309 -> 874 (-33%) | 13 s -> 13 s (+0%) | 1 | 0/0 | - |
| T3 | clone | 2 -> 3 (+50%) | 51.1k -> 109,848 (+115%) | 1,655 -> 1,112 (-33%) | 16 s -> 16 s (+1%) | 2 | 0/0 | - |
| T4 | host | 2 -> 5 (+150%) | 48.9k -> 145,003 (+197%) | 1,597 -> 2,154 (+35%) | 15 s -> 22 s (+44%) | 4 | 0/0 | - |
| T4 | clone | 2 -> 3 (+50%) | 52.9k -> 115,951 (+119%) | 1,777 -> 2,394 (+35%) | 15 s -> 22 s (+49%) | 2 | 0/0 | - |
| T5 | host | 2 -> 2 (+0%) | 40.5k -> 61,226 (+51%) | 271 -> 277 (+2%) | 4 s -> 8 s (+112%) | 1 | 0/0 | - |
| T5 | clone | 2 -> 2 (+0%) | 44.9k -> 69,366 (+54%) | 334 -> 236 (-29%) | 4 s -> 7 s (+77%) | 1 | 0/0 | - |
| T6 | host | 3 -> 4 (+33%) | 67.2k -> 141,435 (+110%) | 3,071 -> 1,879 (-39%) | 21 s -> 22 s (+3%) | 3 | 0/0 | - |
| T6 | clone | 2 -> 4 (+100%) | 49.0k -> 179,963 (+267%) | 2,666 -> 2,336 (-12%) | 21 s -> 30 s (+44%) | 3 | 0/0 | - |
| T1-T6 | host | 14 -> 18 (+29%) | 306k -> 564,949 (+85%) | 7,398 -> 6,377 (-14%) | 65 s -> 82 s (+27%) | - | - | - |
| T1-T6 | clone | 13 -> 17 (+31%) | 312k -> 650,507 (+108%) | 7,468 -> 7,086 (-5%) | 67 s -> 92 s (+38%) | - | - | - |
| general-purpose agent | host | - | - | - | - | - | - | 13.5k -> 15,281 (+13%) |
| kb-review-workspace | host | 0 | 73.1k -> 0 (-100%) | 3.9k -> 0 (-100%) | 32 s -> 45 s (+42%) | 9 -> 0 (-100%) | 5/5 -> 5/5 | - |
<!-- /bench -->

What it shows:
- **The host still costs less than the clone:** 18 turns and 565k input for the six tasks against 17 turns and 651k, at 30.3k and 34.4k of fixed context (the clone also loads `AGENTS.md` and the user's local-scope servers). Both are above the history (306k and 312k): the fixed context grew by 10-12k, and T4 and T6 took 1-3 more turns.
- **`/kb-review-workspace`** named all five planted problems (5/5) in 45 s; it runs in the forked `kb-reviewer` agent, whose usage the result event does not carry (0 input and tool calls in the main session).
- A general-purpose Sonnet agent in the host starts at 15.3k (13.5k in the history).

### Always-on cost

**Setup:** `python3 _tools/benchmarks.py run always-on`: `claude -p "Reply with the single word ok." --model haiku --no-session-persistence --setting-sources project,local` in an empty directory without the plugin, with `--plugin-dir` (hooks off), and with a copy of the plugin whose hooks run and write under the scratch directory; and in a clone with its hooks off and with them on (the query log in mode `local`, a local bare `origin`). 4 runs each; the value is the steady (highest) input, since a run whose first request comes before the `kb` server connects lacks its texts. The history's `--plugin-dir` runs had the plugin's hooks on.

<!-- bench:records always-on -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 3725d8f | 2026-09-27 | 3725d8f | 2.1.283 | 265 | - | - |
| 99e464a | 2026-09-28 | 99e464a | 2.1.283 | 271 | - | - |
| 01587ae | 2026-09-28 | 01587ae | 2.1.283 | 271 | - | - |
| 2026-09-28 | 2026-09-28 | 3e83754 | 2.1.283 | 271 | 4 | $0.12 |
<!-- /bench -->

<!-- bench:table always-on metrics=input,files_the_hooks_wrote -->
| case | arm | input | files_the_hooks_wrote |
|---|---|---|---|
| ok | no plugin | 22,038 (all 4) -> 22,036 (all 4) -> 22,036 (all 4) -> 22,042 (+0%) | - |
| ok | --plugin-dir, hooks on | 23,282 (all 5) -> 23,280 (all 5) -> 23,280 (all 5) -> 23,286 (+0%) | - |
| ok | --plugin-dir, hooks off | 23,286 | - |
| ok | clone, hooks off | 24,584 | - |
| ok | clone, query log hooks on | 24,584 | - |
| isolation | --plugin-dir, hooks on | - | 3 |
<!-- /bench -->

What it shows:
- **The plugin adds 1,244 tokens** (23,286 against 22,042), the same as in the two history records; its hooks on or off make no difference (23,286 both), since no hook prints.
- **The query log's hooks add nothing to a clone's context:** 24,584 with them on and off. With them on, the plugin copy's hooks wrote 3 files under the scratch directory (its `digest-week` marker, `distill.log` and the spool directory) and nothing under `~/.claude/plugins/data/`.

### kb-lookup agent start context

**Setup:** `python3 _tools/benchmarks.py run kb-lookup-agent`: in an empty directory, `claude -p "Use the it-ops-kb:kb-lookup agent to answer this, then relay its answer: How many apps can an Intune Win32 app supersede?" --model haiku --setting-sources project,local --plugin-dir <clone> --allowedTools "Agent,mcp__plugin_it-ops-kb_kb"`, hooks off, session kept; the start context is the first request of the subagent transcript.

<!-- bench:records kb-lookup-agent -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| 945fb09 | 2026-09-27 | 945fb09 | 2.1.283 | 266 | - | - |
| 2026-09-28 | 2026-09-28 | 654c8ad | 2.1.283 | 271 | 1 | $0.12 |
<!-- /bench -->

<!-- bench:table kb-lookup-agent metrics=start_ctx,input,requests,route,checks -->
| case | arm | start_ctx | input | requests | route | checks |
|---|---|---|---|---|---|---|
| run 1 | kb-lookup | 3,937 -> 3,999 (+2%) | 11,149 -> 10,079 (-10%) | 2 -> 2 (+0%) | kb_pack -> kb_pack | 1/1 |
| run 2 | kb-lookup | 3,938 -> 4,005 (+2%) | 18,026 -> 20,915 (+16%) | 3 -> 3 (+0%) | kb_pack, kb_show -> kb_pack > kb_show | 1/1 |
| run 3 | kb-lookup | 3,932 -> 4,009 (+2%) | 9,937 -> 17,784 (+79%) | 2 -> 3 (+50%) | kb_pack -> kb_pack > kb_show | 1/1 |
| run 4 | kb-lookup | 3,931 | 9,935 | 2 | kb_pack | - |
<!-- /bench -->

What it shows: the agent starts at 4.0k (3,999-4,009), 70 tokens above the history's 3,931-3,938: the lookup skill it preloads grew. Every run called `kb_pack` first and answered 10 nodes.

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
<!-- /bench -->

<!-- bench:table retrieval metrics=value -->
| case | arm | value |
|---|---|---|
| untagged content, line in pack (keyword probes) | lexical baseline | 0% |
| untagged content, line in pack (keyword probes) | current | 84-100% -> 95% (+3%) |
| blind questions, line in pack | lexical baseline | 36/72 |
| blind questions, line in pack | current | 68/72 (94%) -> 71/72 |
| blind questions, false none | lexical baseline | 11% on tagged facts, 30% on untagged content |
| blind questions, false none | current | 0% -> 0/72 |
| off-kb questions answered good | lexical baseline | 3/20 |
| off-kb questions answered good | current | 2/20 -> 15/106 |
| cut facts with no visible tag | lexical baseline | 180 |
| cut facts with no visible tag | current | 0 -> 33 |
| code blocks retrievable | lexical baseline | 0/44 |
| code blocks retrievable | current | 44/44 -> 187/189 |
| tagged facts, line in pack (keyword probes) | current | 98% |
<!-- /bench -->

What it shows: on the grown kb, keyword probes find 98% of sampled tagged facts' lines and 95% of untagged content's; 71 of 72 blind questions put the fact's line in the pack and none got a false `none`; 187 of 189 `SNIPPET:` units are found by their own words. The off-kb list (106 questions now) has 15 `good`, as in "Verdict corrections". 33 cut lines of tagged units show no tag, all of them CSV data rows cut before their tag column (16 in `security/settings-crosswalk.csv`); the history counted fact bullets only.

### Verdict corrections

**Setup:** `python3 _tools/benchmarks.py run verdict`: the eval set, the off-kb list's verdicts, the indexed lines, and `pack`'s time over the eval questions (in process, warm, 3 passes). The history's rule tables (the design set of common-word false goods and off-domain questions, and the held-out set) chose the rules that shipped; those sets were not committed, so the re-run measures the shipped rules on the committed sets.

<!-- bench:records verdict -->
| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |
|---|---|---|---|---|---|---|
| beacebd | 2026-09-28 | beacebd | - | 266 | - | - |
| 2026-09-28 | 2026-09-28 | bfa2a7d | 2.1.283 | 271 | 1 | - |
<!-- /bench -->

<!-- bench:table verdict metrics=passed,verdict_good,verdict_weak,verdict_none,indexed_lines,median_ms,p95_ms -->
| case | arm | passed | verdict_good | verdict_weak | verdict_none | indexed_lines | median_ms | p95_ms |
|---|---|---|---|---|---|---|---|---|
| index | current | - | - | - | - | 12,469 -> 12,713 (+2%) | - | - |
| eval set | previous code | 190/250 | - | - | - | - | - | - |
| eval set | current | 250/250 -> 250/250 | - | - | - | - | - | - |
| off-kb list | previous code | - | 55 | 38 | 13 | - | - | - |
| off-kb list | current | - | 15 -> 15 (+0%) | 48 -> 48 (+0%) | 43 -> 43 (+0%) | - | - | - |
| pack, warm | current | - | - | - | - | - | 2.3 ms -> 2.3 ms (-1%) | 4.6 ms -> 4.6 ms (-1%) |
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

What it shows: the shipped rules hold on the grown kb: the eval set passes 250 of 250, the off-kb list gives 15 `good`, 48 `weak` and 43 `none` as when the rules shipped, and `pack` takes 2.3 ms median and 4.6 ms at p95 over 12,713 indexed lines (12,469 then). The rule tables are the history's design-set results; the re-run does not repeat them.

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
<!-- /bench -->

<!-- bench:table tool-speed metrics=time,median_ms,p95_ms,s,size_mb -->
| case | arm | time | median_ms | p95_ms | s | size_mb |
|---|---|---|---|---|---|---|
| rag.py pack (CLI, cold) | before | 3.93 s | - | - | - | - |
| rag.py pack (CLI, cold) | current | 0.06 s -> 0.04 s (-27%) | 43.6 ms | 50.4 ms | - | - |
| kb: hook | before | 2.05-2.15 s | - | - | - | - |
| kb: hook | current | 0.05-0.09 s -> 0.05 s (-29%) | 49.5 ms | 70.3 ms | - | - |
| rag.py eval | before | 8.63 s | - | - | - | - |
| rag.py eval | current | 0.71 s -> 0.79 s (+11%) | 786.7 ms | 788.7 ms | - | - |
| rag.py search | before | 0.29 s | - | - | - | - |
| rag.py search | current | 0.05 s -> 0.04 s (-21%) | 39.3 ms | 40.2 ms | - | - |
| MCP session (12 calls) | before | 4.04 s | - | - | - | - |
| MCP session (12 calls) | current | 1.63 s -> 2.06 s (+26%) | 2055.5 ms | 2080.3 ms | - | - |
| kbgit.py check-trailers (30 commits) | before | 0.77-0.95 s | - | - | - | - |
| kbgit.py check-trailers (30 commits) | current | 0.41 s -> 0.21 s (-48%) | 211.6 ms | 235.0 ms | - | - |
| index build | before | - | - | - | - | - |
| index build | current | about 3 s, 24 MB -> 2.17 s (-84%) | - | - | - | 32.5 MB |
| pack in-process, warm | current | - | 3.0 ms -> 2.9 ms (-3%) | 4.5 ms -> 6.6 ms (+46%) | - | - |
| MCP server start (initialize reply) | current | - | 32.0 ms -> 29.7 ms (-7%) | 30.2 ms | - | - |
| 1,000 random packs | current | - | - | - | 3.30 s -> 2.47 s (-25%) | - |
<!-- /bench -->

What it shows: with 271 topics on macOS, a cold `rag.py pack` takes 44 ms, the `kb:` hook 50 ms, `search` 39 ms and `eval` (250 questions) 0.79 s; an MCP session of 12 calls 2.06 s (1.63 s for the history's calls) and the server answers `initialize` in 30 ms; an index build takes 2.2 s and 32.5 MB. In process a warm `pack` takes 2.9 ms at the median and 6.6 ms at p95, and 1,000 random packs 2.5 s. The history's `before` column is the corpus rebuilt by every process; nothing measured here needs it again.

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
| 2026-09-30 | 2026-09-30 | f2509b1 | 2.1.286 | 292 | 3 | $0.70 |
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
