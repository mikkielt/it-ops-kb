# Research reproducibility: three isolated instances, the same 21 areas

Measured on 2026-10-15 from the run `repro run` made over three isolated instances of the start commit `2170d88f4b11` (record `2170d88` of `kb/_self/reports/benchmarks.csv`). Each instance ran one headless Sonnet `/kb-research` session per area of `kb/public/_retrieval/repro_briefs.csv`, 21 areas, from the same brief, with no view of the others' work. 53 of the 63 area runs finished; 10 stopped on the instance's cost cap (`failure` `budget`: instance 1 `uv`, `pip`; instance 2 `pip`; instance 3 `age`, `sops`, `rust`, `python`, `cpython`, `uv`, `pip`). The run cost $178.02 (instance 1 $59.09, instance 2 $60.79, instance 3 $58.14).

Every number below is a row of the `repro` or the `repro-compare` scenario of `kb/_self/reports/benchmarks.csv` (the generated tables are in the section "Three isolated instances research the same areas" of `kb/_self/reports/benchmarks.md`), or a line `python3 _tools/benchmarks.py repro compare` prints (it reads the three bare repositories and runs no model, so it is re-run at no cost; `--record` merges its rows). A figure counted from the printed lines says so.

## What is measured

- **Added:** per instance and area, what the instance's bare `main` holds beyond the start commit for that area's commits: new articles, facts (`rag.py audit`'s lines), their tags (`DOC`, `CODE`, `DER`, `COMMUNITY`, `UNK`) and the source rows.
- **Jaccard overlap** (`url_jaccard`): of the urls of the sources two instances added in an area; 1.00 when both added none.
- **Facts' overlap** (`fact_overlap`): matched claims over the union of the two instances' added facts; two facts are one claim only on one article path with a difflib ratio of at least 0.8.
- **Conflicts:** a matched pair whose numbers differ; `repro compare` prints both lines.
- **Errors:** `check.py` and the kb-verify lint (facts since the start commit) on each instance's final `main`.
- **Frozen set:** `kb/public/_retrieval/repro_bench.csv`, 103 questions, 3 to 5 per area, asked of each instance's final `main` with its own `rag.py eval`. The pass rate is `eval_passed` of `eval_total`; the coverage verdicts are each row's `good`, `weak` or `none`. The agreement of an area is the share of its rows on which all three instances have the same verdict and the same `expect_re` outcome; it is computed only for the areas every instance finished (14 of 21).

## 1. Per instance and area

`python3 _tools/benchmarks.py repro compare`, with the `repro` rows' cost, turns and wall time. `run` is `ok` for a finished run and `cap` for one the cost cap stopped (no cost, no commits). `frozen passed` and `good / weak / none` count the area's frozen rows on the instance's whole final `main`, so an area an instance did not research still has them.

| area | instance | run | cost | turns | wall s | articles | facts | DOC | CODE | DER | COMMUNITY | UNK | sources | frozen passed | good / weak / none |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| podman | 1 | ok | $3.14 | 168 | 625 | 1 | 74 | 66 | 1 | 5 | 0 | 2 | 16 | 1 of 5 | 2 / 3 / 0 |
| podman | 2 | ok | $4.03 | 204 | 814 | 2 | 120 | 106 | 3 | 8 | 0 | 3 | 20 | 0 of 5 | 4 / 1 / 0 |
| podman | 3 | ok | $4.01 | 204 | 771 | 5 | 119 | 103 | 0 | 13 | 0 | 3 | 15 | 0 of 5 | 4 / 1 / 0 |
| puppet | 1 | ok | $3.75 | 178 | 839 | 1 | 87 | 80 | 2 | 3 | 0 | 2 | 26 | 0 of 5 | 4 / 1 / 0 |
| puppet | 2 | ok | $4.13 | 233 | 781 | 2 | 113 | 82 | 28 | 3 | 0 | 0 | 35 | 0 of 5 | 4 / 0 / 1 |
| puppet | 3 | ok | $4.28 | 249 | 802 | 4 | 128 | 114 | 5 | 7 | 0 | 1 | 30 | 0 of 5 | 5 / 0 / 0 |
| chef | 1 | ok | $3.97 | 216 | 630 | 1 | 91 | 84 | 0 | 4 | 0 | 3 | 29 | 0 of 5 | 5 / 0 / 0 |
| chef | 2 | ok | $3.57 | 181 | 703 | 2 | 88 | 77 | 7 | 4 | 0 | 0 | 17 | 0 of 5 | 5 / 0 / 0 |
| chef | 3 | ok | $4.68 | 254 | 866 | 4 | 136 | 118 | 8 | 8 | 0 | 2 | 31 | 0 of 5 | 5 / 0 / 0 |
| almalinux | 1 | ok | $3.06 | 186 | 660 | 1 | 59 | 46 | 4 | 8 | 0 | 1 | 21 | 0 of 5 | 5 / 0 / 0 |
| almalinux | 2 | ok | $3.61 | 205 | 722 | 1 | 58 | 44 | 3 | 8 | 0 | 3 | 18 | 0 of 5 | 5 / 0 / 0 |
| almalinux | 3 | ok | $3.01 | 186 | 648 | 3 | 66 | 49 | 3 | 11 | 0 | 3 | 20 | 0 of 5 | 5 / 0 / 0 |
| kali | 1 | ok | $2.97 | 177 | 686 | 1 | 100 | 81 | 11 | 7 | 0 | 1 | 23 | 0 of 4 | 3 / 1 / 0 |
| kali | 2 | ok | $1.89 | 136 | 454 | 1 | 68 | 54 | 5 | 7 | 0 | 2 | 18 | 0 of 4 | 4 / 0 / 0 |
| kali | 3 | ok | $4.04 | 237 | 816 | 4 | 92 | 70 | 9 | 9 | 0 | 4 | 23 | 0 of 4 | 4 / 0 / 0 |
| gentoo | 1 | ok | $4.40 | 203 | 850 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 of 5 | 0 / 1 / 4 |
| gentoo | 2 | ok | $3.84 | 186 | 774 | 2 | 140 | 125 | 0 | 11 | 0 | 4 | 18 | 0 of 5 | 4 / 1 / 0 |
| gentoo | 3 | ok | $7.19 | 268 | 1241 | 6 | 218 | 196 | 4 | 16 | 0 | 2 | 26 | 0 of 5 | 5 / 0 / 0 |
| zsh | 1 | ok | $3.72 | 188 | 857 | 1 | 73 | 59 | 1 | 9 | 0 | 4 | 10 | 0 of 5 | 5 / 0 / 0 |
| zsh | 2 | ok | $4.07 | 181 | 943 | 2 | 94 | 72 | 4 | 16 | 0 | 2 | 10 | 0 of 5 | 2 / 3 / 0 |
| zsh | 3 | ok | $5.45 | 239 | 1130 | 4 | 88 | 72 | 0 | 15 | 0 | 1 | 10 | 0 of 5 | 2 / 3 / 0 |
| bash | 1 | ok | $3.88 | 165 | 689 | 1 | 119 | 97 | 0 | 17 | 0 | 5 | 1 | 0 of 5 | 2 / 3 / 0 |
| bash | 2 | ok | $4.15 | 181 | 742 | 3 | 131 | 112 | 0 | 16 | 0 | 3 | 1 | 0 of 5 | 3 / 2 / 0 |
| bash | 3 | ok | $4.63 | 184 | 889 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 of 5 | 1 / 4 / 0 |
| fish | 1 | ok | $3.34 | 132 | 575 | 1 | 148 | 131 | 0 | 12 | 0 | 5 | 10 | 0 of 5 | 5 / 0 / 0 |
| fish | 2 | ok | $5.02 | 167 | 947 | 3 | 203 | 181 | 0 | 19 | 0 | 3 | 14 | 0 of 5 | 4 / 1 / 0 |
| fish | 3 | ok | $6.14 | 239 | 1122 | 6 | 122 | 104 | 0 | 18 | 0 | 0 | 12 | 0 of 5 | 4 / 1 / 0 |
| cmd | 1 | ok | $1.35 | 78 | 368 | 1 | 57 | 45 | 0 | 8 | 0 | 4 | 11 | 0 of 5 | 2 / 3 / 0 |
| cmd | 2 | ok | $1.31 | 84 | 324 | 1 | 58 | 53 | 0 | 4 | 0 | 1 | 11 | 1 of 5 | 1 / 4 / 0 |
| cmd | 3 | ok | $3.69 | 202 | 827 | 2 | 84 | 70 | 0 | 7 | 0 | 7 | 11 | 0 of 5 | 2 / 3 / 0 |
| robocopy | 1 | ok | $1.02 | 57 | 215 | 1 | 59 | 50 | 0 | 9 | 0 | 0 | 4 | 0 of 5 | 5 / 0 / 0 |
| robocopy | 2 | ok | $1.06 | 66 | 280 | 1 | 74 | 62 | 0 | 8 | 0 | 4 | 5 | 0 of 5 | 5 / 0 / 0 |
| robocopy | 3 | ok | $1.08 | 63 | 322 | 1 | 62 | 52 | 0 | 6 | 0 | 4 | 2 | 0 of 5 | 5 / 0 / 0 |
| ssh-windows-estate | 1 | ok | $2.58 | 128 | 579 | 2 | 59 | 51 | 0 | 7 | 0 | 1 | 8 | 4 of 5 | 5 / 0 / 0 |
| ssh-windows-estate | 2 | ok | $2.42 | 116 | 440 | 1 | 53 | 47 | 0 | 4 | 0 | 2 | 8 | 3 of 5 | 4 / 1 / 0 |
| ssh-windows-estate | 3 | ok | $3.00 | 158 | 545 | 2 | 63 | 55 | 0 | 5 | 0 | 3 | 12 | 4 of 5 | 5 / 0 / 0 |
| jea | 1 | ok | $1.54 | 78 | 348 | 0 | 58 | 54 | 0 | 3 | 0 | 0 | 4 | 5 of 5 | 5 / 0 / 0 |
| jea | 2 | ok | $1.17 | 64 | 245 | 0 | 48 | 47 | 0 | 1 | 0 | 0 | 1 | 5 of 5 | 5 / 0 / 0 |
| jea | 3 | ok | $2.14 | 107 | 497 | 0 | 46 | 44 | 0 | 2 | 0 | 0 | 2 | 5 of 5 | 5 / 0 / 0 |
| typescript | 1 | ok | $4.31 | 198 | 940 | 1 | 67 | 52 | 9 | 4 | 0 | 0 | 26 | 1 of 5 | 4 / 1 / 0 |
| typescript | 2 | ok | $3.82 | 153 | 794 | 1 | 77 | 46 | 23 | 4 | 0 | 1 | 20 | 1 of 5 | 4 / 1 / 0 |
| typescript | 3 | ok | $4.82 | 188 | 942 | 4 | 147 | 124 | 7 | 14 | 0 | 1 | 42 | 1 of 5 | 4 / 1 / 0 |
| age | 1 | ok | $1.81 | 94 | 343 | 1 | 58 | 48 | 2 | 7 | 0 | 1 | 6 | 2 of 5 | 3 / 2 / 0 |
| age | 2 | ok | $2.14 | 101 | 473 | 1 | 70 | 53 | 11 | 5 | 0 | 1 | 6 | 2 of 5 | 3 / 2 / 0 |
| age | 3 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 of 5 | 3 / 2 / 0 |
| sops | 1 | ok | $2.92 | 139 | 624 | 1 | 55 | 33 | 16 | 5 | 0 | 1 | 8 | 2 of 5 | 4 / 1 / 0 |
| sops | 2 | ok | $1.68 | 94 | 410 | 1 | 44 | 34 | 7 | 2 | 0 | 1 | 6 | 2 of 5 | 4 / 1 / 0 |
| sops | 3 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 of 5 | 4 / 1 / 0 |
| rust | 1 | ok | $3.08 | 159 | 623 | 1 | 82 | 76 | 0 | 6 | 0 | 0 | 24 | 2 of 5 | 3 / 2 / 0 |
| rust | 2 | ok | $3.09 | 167 | 704 | 1 | 90 | 77 | 0 | 11 | 0 | 2 | 33 | 2 of 5 | 3 / 2 / 0 |
| rust | 3 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 of 5 | 3 / 2 / 0 |
| python | 1 | ok | $3.44 | 155 | 726 | 3 | 138 | 121 | 4 | 12 | 0 | 1 | 9 | 1 of 4 | 4 / 0 / 0 |
| python | 2 | ok | $3.65 | 144 | 727 | 5 | 163 | 140 | 0 | 19 | 0 | 4 | 8 | 1 of 4 | 4 / 0 / 0 |
| python | 3 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 of 4 | 2 / 2 / 0 |
| cpython | 1 | ok | $4.80 | 211 | 941 | 2 | 87 | 83 | 0 | 3 | 0 | 0 | 13 | 1 of 5 | 5 / 0 / 0 |
| cpython | 2 | ok | $3.09 | 164 | 647 | 2 | 70 | 65 | 0 | 3 | 0 | 0 | 9 | 1 of 5 | 5 / 0 / 0 |
| cpython | 3 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 of 5 | 5 / 0 / 0 |
| uv | 1 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 of 5 | 5 / 0 / 0 |
| uv | 2 | ok | $3.04 | 147 | 621 | 4 | 133 | 112 | 8 | 13 | 0 | 0 | 8 | 3 of 5 | 4 / 1 / 0 |
| uv | 3 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 of 5 | 4 / 1 / 0 |
| pip | 1 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 of 5 | 4 / 1 / 0 |
| pip | 2 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 of 5 | 2 / 3 / 0 |
| pip | 3 | cap | $0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 of 5 | 2 / 3 / 0 |

## 2. Per pair of instances, the 14 areas all three finished

`python3 _tools/benchmarks.py repro compare`: the pairs 1+2, 1+3 and 2+3, and the area's agreement. The seven areas an instance stopped on (`age`, `sops`, `rust`, `python`, `cpython`, `uv`, `pip`) have no agreement and no pair figure worth reading: the tool prints a pair for them too, with an empty set on one side (0.00) or on both (1.00).

| area | url_jaccard 1+2 | 1+3 | 2+3 | fact_overlap 1+2 | 1+3 | 2+3 | conflicts 1+2 | 1+3 | 2+3 | agreement |
|---|---|---|---|---|---|---|---|---|---|---|
| podman | 0.38 | 0.48 | 0.40 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.60 |
| puppet | 0.20 | 0.14 | 0.25 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.40 |
| chef | 0.24 | 0.43 | 0.33 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 1.00 |
| almalinux | 0.15 | 0.32 | 0.46 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 1.00 |
| kali | 0.41 | 0.48 | 0.58 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.75 |
| gentoo | 0.00 | 0.00 | 0.33 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.00 |
| zsh | 0.82 | 0.82 | 0.82 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.40 |
| bash | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.00 |
| fish | 0.60 | 0.69 | 0.53 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.40 |
| cmd | 0.69 | 0.69 | 0.69 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0.80 |
| robocopy | 0.50 | 0.50 | 0.40 | 0.13 | 0.10 | 0.14 | 0 | 0 | 0 | 1.00 |
| ssh-windows-estate | 0.23 | 0.05 | 0.18 | 0.01 | 0.07 | 0.04 | 0 | 0 | 0 | 0.80 |
| jea | 0.25 | 0.50 | 0.50 | 0.06 | 0.07 | 0.11 | 0 | 1 | 1 | 1.00 |
| typescript | 0.59 | 0.48 | 0.32 | 0.01 | 0.00 | 0.00 | 2 | 1 | 0 | 1.00 |

## 3. Per instance, whole run

Sums of the `repro` and `repro-compare` rows over the areas the instance finished; `frozen passed` is `repro pick`'s `eval_passed` summed over the 21 areas (`python3 _tools/benchmarks.py repro pick`), the verdicts are counted from the lines `repro compare` prints for all 103 frozen rows.

| instance | areas finished | cost | turns | wall s | articles | facts | DOC | CODE | DER | COMMUNITY | UNK | sources | check + lint errors | frozen passed | good / weak / none |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 19 | $59.09 | 2910 | 12119 | 21 | 1471 | 1257 | 50 | 129 | 0 | 31 | 249 | 0 | 24 of 103 | 80 / 19 / 4 |
| 2 | 20 | $60.79 | 2974 | 12545 | 36 | 1895 | 1589 | 99 | 166 | 0 | 36 | 266 | 0 | 22 of 103 | 79 / 23 / 1 |
| 3 | 14 | $58.14 | 2778 | 11419 | 45 | 1371 | 1171 | 36 | 131 | 0 | 31 | 236 | 0 | 24 of 103 | 79 / 24 / 0 |

The instances did not finish the same areas, so the sums do not compare. On the 14 areas all three finished:

| instance | cost | turns | wall s | articles | facts | DOC share | CODE share | DER share | UNK share | sources | cost per fact |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | $43.03 | 2152 | 8861 | 13 | 1051 | 85.3% | 2.7% | 9.1% | 2.7% | 189 | $0.041 |
| 2 | $44.10 | 2157 | 8962 | 22 | 1325 | 83.6% | 5.5% | 8.5% | 2.1% | 196 | $0.033 |
| 3 | $58.14 | 2778 | 11419 | 45 | 1371 | 85.4% | 2.6% | 9.6% | 2.3% | 236 | $0.042 |

## 4. How reproducible the research is

**Reproducible, in kind:**
- **Quality gates:** all three instances end with 0 `check.py` errors and 0 lint errors.
- **Tag mix:** `DOC` is 84% to 85% of the added facts in every instance, `DER` 8.5% to 9.6%, `UNK` 2% to 3%, `COMMUNITY` none. `CODE` differs most, 2.6% to 5.5%: instance 2 wrote 73 `CODE` facts on the 14 common areas, 28 of them in `puppet` and 23 in `typescript`, where the others wrote 2 and 5 (`puppet`) and 9 and 7 (`typescript`).
- **Volume:** where all three added facts (12 areas), the largest instance wrote 1.1 to 2.2 times the smallest's fact count (`almalinux` 1.1, `typescript` 2.2). Sources added over the 14 common areas: 189, 196 and 236.
- **Sources:** over those 12 areas the 36 pair values of `url_jaccard` have a mean of 0.45 and a median of 0.47, from 0.05 (`ssh-windows-estate`, 1+3) to 0.82 (`zsh`, all three pairs). It is high in `zsh` (0.82), `cmd` (0.69) and `fish` (0.53 to 0.69) and low in `puppet` (0.14 to 0.25), `almalinux` (0.15 to 0.46) and `ssh-windows-estate` (0.05 to 0.23).
- **Conflicts:** five conflict entries over all pairs, none a contradiction. The `jea` pair 1+3 and 2+3 differ in the sample value of one config example (the share name of an `EnvironmentVariables` entry); the `typescript` and `cpython` pairs state the same claim with a different set of numbers (`5.9` against `5.x`, a mention of the next release `3.15`). The detector flags a matched pair whose numbers differ, so it over-reports.
- **Frozen verdicts:** 81 of the 103 rows have the same verdict in all three instances (counted from the lines printed; 22 differ). The agreement of the 14 finished areas is 0.65 by area mean and 45 of 69 rows; 5 areas agree on every row (`chef`, `almalinux`, `robocopy`, `jea`, `typescript`).

**Not reproducible, in content:**
- **Facts' overlap:** the pair value is 0.00 in 30 of the 42 area-pair values of the 14 areas and at most 0.14 (`robocopy`, 2+3), mean 0.02 over all 42. Two instances state the same claim in separate facts nearly never, by the tool's rule of one claim: one article path. That rule is strict: instance 3 wrote 45 articles on the 14 areas where instance 1 wrote 13, so most of the claims cannot match across instances by path alone. The value is a floor on shared claims, not their share.
- **Article layout:** instance 1 wrote one article per area in 11 of its 14 common areas, instance 2 one or two in 11, instance 3 two to six in 11. The split of the same subject into articles is the most stable difference between the instances, not a random one.
- **Which areas finish:** the cost cap stopped instance 3 after 14 areas and instance 1 after 19; the instances' mean cost per finished area was $4.15, $3.11 and $3.04 (instance 3, 1, 2). Instance 3's `gentoo` cost $7.19 (the others $4.40 and $3.84), `fish` $6.14 ($3.34, $5.02) and `zsh` $5.45 ($3.72, $4.07).

## 5. Where the instances diverge

- **A finished session that landed nothing:** `gentoo` in instance 1 ($4.40, 203 turns, 850 s) and `bash` in instance 3 ($4.63, 184 turns, 889 s) have `failure` `none` and a bare `main` unchanged by the run (`main_before` equals `main_after`): no article, no fact, no source. They are the two areas of the 14 with agreement 0.00, and instance 1's 4 `none` verdicts are all `gentoo` rows. Why they landed nothing is not read here.
- **Frozen rows that differ:** 22 rows. `gentoo` 5 (instance 1 has `none` or `weak` where 2 and 3 have `good`), `zsh` 3 (instance 1 `good`, 2 and 3 `weak`), `bash` 2, `python` 2, `pip` 2 and `podman` 2, the others 1. The `pip` rows differ although no instance researched `pip`, so a verdict also moves with the other areas' articles, not only with the area's own research.
- **Article granularity:** the clearest systematic difference, above.
- **`CODE` against `DOC`:** instance 2 reads source code where the others read docs (`puppet`, `typescript`).
- **Sources:** the overlap is high on pages the brief names and low on open areas, and instance 3 cites the most sources (236 on the 14 areas, against 189 and 196).

## 6. Limits of these numbers

- **The pass rate is not a quality measure here.** `eval_passed` is `rag.py eval`'s `ok`, which requires the verdict to equal the file's `expect_verdict`; for the 63 `absent` rows that is `none`, the start state, so a row passes only while the kb still does not answer it, and `repro pick` ranks on it. Only the 40 `present` and `partial` rows can pass while their answer holds; an `absent` row passes only if the pack still says `none` and yet matches the answer's regex. The 24, 22 and 24 of 103 therefore say little about the research. Read the verdict counts instead. This is the defect of BG-qztas5u4.
- **No start verdicts are recorded**, so the verdict counts are of the final `main`, not a gain.
- **One run per instance.** Three instances give three samples of one process; a spread over a repeat of the whole run is not measured.
- **Unequal sets:** the instances finished 19, 20 and 14 areas, so totals compare only on the 14 common ones, and every figure of the 7 stopped areas is an artefact of an empty side.
- **The pair rule** (one article path) makes the facts' overlap a floor, and the conflict detector (numbers differ) over-reports.

## Conclusion

The research is reproducible in what it produces and not in how it is laid out. All three instances ended clean (0 `check.py` and 0 lint errors), with the same tag mix (84% to 85% `DOC`, about 9% `DER`, no `COMMUNITY`), a fact volume within a factor of about 2 per area, no contradiction between them, a source overlap of 0.45 where all three wrote, `good` on 80, 79 and 79 of the 103 frozen rows, with the verdict identical in all three on 81. They diverge in how they split a subject into articles (13, 22 and 45 on the same 14 areas), in how many sources and `CODE` facts they add, in the cost per area (instance 3's areas cost about 1.3 times the others'), and above all in whether a session lands anything: two finished sessions wrote nothing, and the cost cap took 7 areas from one instance and 2 and 1 from the others. The two reading limits are the facts' overlap, a floor, and the pass rate, which does not measure research (BG-qztas5u4).
