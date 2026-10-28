# Linux CI suite time on GitHub runners: median, p90 and the bytecode effect

Twenty `workflow_dispatch` runs of the `kb` workflow at the head of `main` of the public repository, read with `gh run view ID --log`: the time of the Linux `kb-tests` job's suite on GitHub-hosted runners, the effect of letting Python write `.pyc` files, and whether the runner's CPU model explains the fast and slow runs. Re-run it with `gh workflow run kb -f write_bytecode=true|false` once a run should supersede this one, and replace the run section.

**Setup.** All 20 runs ran at one commit, `ad09ab51f05c2749767536b519a5da1db993c598` (the public `main`, 32 test ids), from 2026-10-27T23:19Z to 2026-10-28T00:05Z, one after another: the workflow's concurrency group cancels an overlapping run of the same ref, so each dispatch waited for the last to finish. Each ran the `kb-tests` job (`ubuntu-latest`, container `python:3.14`, Python 3.14.10, pytest 9.1.1, xdist 3.8.0, `nproc` 4) with `python3 _tools/tests.py --durations 10`. The first 10 runs set no input (`write_bytecode` default false, `PYTHONDONTWRITEBYTECODE: 1`); the next 10 alternated `-f write_bytecode=true` (the variable empty, `.pyc` files written) and `-f write_bytecode=false`, five each, starting with true.

**Columns.** `pytest s` is pytest's own total from its last line. `tests.py s` is the figure of tests.py's over-the-ceiling line (`the full run took N s`, rounded), which it prints only above the 60 s Linux ceiling, so `-` is a run under it. `step s` is the wall time of the whole tests.py step from the log timestamps. A `red` run is a run whose job failed: every red run here failed on that ceiling line alone (all its tests passed).

## Runs

| # | run id | arm | CPU model | nproc | pytest s | tests.py s | step s | job |
|---|---|---|---|---|---|---|---|---|
| 1 | 40601316038 | default | AMD EPYC 9V74 80-Core Processor | 4 | 73.94 | 75 | 77.5 | red |
| 2 | 40601575588 | default | AMD EPYC 9V74 80-Core Processor | 4 | 70.54 | 72 | 74.2 | red |
| 3 | 40601831062 | default | AMD EPYC 9V74 80-Core Processor | 4 | 84.88 | 86 | 89.4 | red |
| 4 | 40602124395 | default | AMD EPYC 9V45 96-Core Processor | 4 | 58.31 | - | 61.1 | green |
| 5 | 40602333543 | default | AMD EPYC 7763 64-Core Processor | 4 | 92.13 | 93 | 96.6 | red |
| 6 | 40602617794 | default | AMD EPYC 7763 64-Core Processor | 4 | 95.41 | 97 | 100.3 | red |
| 7 | 40602915933 | default | AMD EPYC 9V74 80-Core Processor | 4 | 88.70 | 90 | 93.2 | red |
| 8 | 40603211416 | default | AMD EPYC 7763 64-Core Processor | 4 | 93.08 | 94 | 97.5 | red |
| 9 | 40603495329 | default | AMD EPYC 7763 64-Core Processor | 4 | 93.85 | 95 | 98.3 | red |
| 10 | 40603778252 | default | Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz | 4 | 90.80 | 92 | 95.5 | red |
| 11 | 40604062431 | true | AMD EPYC 9V74 80-Core Processor | 4 | 57.24 | - | 59.8 | green |
| 12 | 40604275747 | false | AMD EPYC 7763 64-Core Processor | 4 | 90.76 | 92 | 95.2 | red |
| 13 | 40604562812 | true | AMD EPYC 7763 64-Core Processor | 4 | 66.37 | 67 | 69.1 | red |
| 14 | 40604770236 | false | AMD EPYC 7763 64-Core Processor | 4 | 96.00 | 97 | 100.7 | red |
| 15 | 40605053568 | true | AMD EPYC 7763 64-Core Processor | 4 | 65.56 | 66 | 68.3 | red |
| 16 | 40605298179 | false | AMD EPYC 9V74 80-Core Processor | 4 | 89.19 | 90 | 93.7 | red |
| 17 | 40605570324 | true | AMD EPYC 9V45 96-Core Processor | 4 | 41.04 | - | 42.8 | green |
| 18 | 40605734098 | false | INTEL(R) XEON(R) PLATINUM 8573C | 4 | 82.43 | 84 | 86.7 | red |
| 19 | 40606019960 | true | AMD EPYC 7763 64-Core Processor | 4 | 66.63 | 67 | 69.3 | red |
| 20 | 40606228903 | false | AMD EPYC 7763 64-Core Processor | 4 | 98.58 | 100 | 103.5 | red |

## Median and p90 per arm

The p90 is the nearest-rank value (the ceiling of 0.9 n, so the largest of five). Seconds.

**pytest s**

| arm | n | median | p90 | min | max |
|---|---|---|---|---|---|
| default (input unset, bytecode off) | 10 | 89.8 | 93.8 | 58.3 | 95.4 |
| `write_bytecode=false` | 5 | 90.8 | 98.6 | 82.4 | 98.6 |
| default and false together (bytecode off) | 15 | 90.8 | 96.0 | 58.3 | 98.6 |
| `write_bytecode=true` (bytecode on) | 5 | 65.6 | 66.6 | 41.0 | 66.6 |

**step s** (the tests.py step)

| arm | n | median | p90 | min | max |
|---|---|---|---|---|---|
| default (input unset, bytecode off) | 10 | 94.3 | 98.3 | 61.1 | 100.3 |
| `write_bytecode=false` | 5 | 95.2 | 103.5 | 86.7 | 103.5 |
| default and false together (bytecode off) | 15 | 95.2 | 100.7 | 61.1 | 103.5 |
| `write_bytecode=true` (bytecode on) | 5 | 68.3 | 69.3 | 42.8 | 69.3 |

Of the 15 runs with bytecode off, 1 ended green, and of the 5 with it on, 2. The ceiling is 60 s on Linux (`_tools/tests_ceiling.json`) and the three green runs had pytest times of 41.0, 57.2 and 58.3 s. In each red run the `check-trailers` step after the tests step still ran and passed.

## Does the CPU model explain the two timing modes

The runs landed on four CPU models, not two. Seconds, pytest's time:

| CPU model | arm | n | median | min | max |
|---|---|---|---|---|---|
| EPYC 9V45 | bytecode off | 1 | 58.3 | 58.3 | 58.3 |
| EPYC 9V45 | bytecode on | 1 | 41.0 | 41.0 | 41.0 |
| EPYC 9V74 | bytecode off | 5 | 84.9 | 70.5 | 89.2 |
| EPYC 9V74 | bytecode on | 1 | 57.2 | 57.2 | 57.2 |
| Xeon Platinum | bytecode off | 2 | 86.6 | 82.4 | 90.8 |
| EPYC 7763 | bytecode off | 7 | 93.8 | 90.8 | 98.6 |
| EPYC 7763 | bytecode on | 3 | 66.4 | 65.6 | 66.6 |

The Xeon rows are one 8370C and one 8573C run, both with bytecode off.

With bytecode off, the only run under the ceiling was on EPYC 9V45 (58.3 s); EPYC 9V74 took 70.5 to 89.2 s, the Xeons 82.4 and 90.8 s and EPYC 7763 90.8 to 98.6 s. So the CPU model orders the runs (9V45 fastest, 7763 slowest) and the fast mode is one model, but it does not make two modes: the slow side holds three models and EPYC 9V74 alone spans 18.7 s between its runs, which a CPU model cannot explain (the neighbours on the host are the likely cause, not measured here). The 7763 runs, the most frequent model, sit in a tight band (90.8 to 98.6 s off, 65.6 to 66.6 s on).

## The bytecode change

Over all runs, letting Python write `.pyc` files cut the median pytest time from 90.8 s to 65.6 s (28%) and the median step time from 95.2 s to 68.3 s (28%). The arms drew different CPUs (two of the five bytecode-on runs landed on the faster models), so the like-for-like figure is EPYC 7763 alone: 93.8 s off (n=7) against 66.4 s on (n=3), 29% saved, the ranges not overlapping (90.8 to 98.6 s against 65.6 to 66.6 s). Both exceed the 10% bar, so the change (dropping `PYTHONDONTWRITEBYTECODE` from the Linux CI jobs) is recommended on this measurement. It does not by itself bring the suite under the 60 s ceiling: the three bytecode-on runs on EPYC 7763 stayed at 65.6 to 66.6 s and red.

## Reading of the review's rows

- **CI-1** (the public job is red because the suite exceeds the 60 s ceiling): the falsifier was a median under 55 s over 10 runs at head; the 10 default runs have a median pytest time of 89.8 s and 9 of 10 were red, so it stands.
- **CI-2** (two timing modes, 36 to 50 s and 55 to 66 s): not reproduced as two modes here; the runs from 41 s to 99 s form a spread ordered by CPU model with overlap, as above, at the current 32-id suite.
- **CI-8** (bytecode cost, unknown share of 10 to 30%): measured at 28% of the median across arms and 29% on one model.

## The ten slowest tests per run

`--durations 10` lists the ten slowest test phases of each run; every entry here is a `call` phase. A run lists its tests by key with seconds. The keys, by median seconds over the runs that list the test:

| key | test | runs listing it | median s |
|---|---|---|---|
| A | `_tools/test_sync_e2e.py::TestRedGate::test_a_red_gate_leaves_main_where_the_last_push_put_it` | 20 | 62.5 |
| B | `_tools/test_leaks.py::test_tracked_files_hold_no_secret_and_authored_files_hold_placeholders_only` | 20 | 45.7 |
| C | `_tools/test_authority.py::test_an_agent_cannot_answer_or_provisionally_answer_an_operator_gate_the_operator_can` | 20 | 41.4 |
| D | `_tools/test_redact.py::test_an_ops_row_has_a_closed_shape_and_a_free_text_value_is_refused_and_kb_feedback_spools_one_closed_row_once_refuses_each_open_field_and_prints_its_call_on_a_weak_or_none_pack_only` | 20 | 27.3 |
| E | `_tools/test_check_programs.py::test_backlog_check_refuses_programs_outside_the_allowlist` | 17 | 15.2 |
| F | `_tools/test_sync_e2e.py::test_code_commit_goes_to_a_branch` | 20 | 12.3 |
| G | `_tools/test_authority.py::test_kbdecide_confirm_record_supersede_restore_are_refused_without_the_operator` | 20 | 11.4 |
| H | `_tools/test_authority.py::test_an_agent_cannot_confirm_an_operator_gate_check_reports_an_answer_or_a_lowered_class_and_a_delegate_grant_needs_the_operator` | 20 | 10.4 |
| I | `_tools/test_prepush_e2e.py::test_upstream_push_refused` | 15 | 9.2 |
| J | `_tools/test_sync_e2e.py::test_upstream_merge[me]` | 5 | 4.9 |
| K | `_tools/test_sync_e2e.py::test_upstream_merge[org]` | 10 | 4.8 |
| L | `_tools/test_sync_e2e.py::test_upstream_merge[team]` | 11 | 4.0 |
| M | `_tools/test_publish_e2e.py::test_publish_sends_the_projection_and_check_public_tells_it_apart` | 2 | 3.6 |

1. 40601316038 (default, EPYC 9V74): A 54.9, C 34.2, B 33.5, D 20.5, H 13.8, E 11.8, F 9.7, G 8.5, I 7.5, K 5.2
2. 40601575588 (default, EPYC 9V74): A 50.8, C 34.0, B 33.5, D 22.7, E 11.5, F 9.9, G 9.4, H 8.4, I 7.0, L 4.8
3. 40601831062 (default, EPYC 9V74): A 64.9, B 43.4, C 39.2, D 29.4, E 14.8, F 12.3, G 11.4, H 10.6, I 9.0, K 4.8
4. 40602124395 (default, EPYC 9V45): A 41.2, C 29.4, B 26.7, D 16.4, H 11.0, E 9.5, F 7.8, I 5.6, G 4.4, L 4.0
5. 40602333543 (default, EPYC 7763): A 70.1, B 48.6, C 43.5, D 30.3, E 16.5, F 13.5, G 11.6, H 10.6, I 9.3, K 4.8
6. 40602617794 (default, EPYC 7763): A 74.0, B 49.3, C 43.5, D 32.7, E 16.5, F 13.7, G 13.1, H 11.3, I 10.1, L 4.8
7. 40602915933 (default, EPYC 9V74): A 60.9, C 43.8, B 43.4, D 27.3, E 14.7, F 12.3, G 10.8, H 10.4, I 9.0, J 5.1
8. 40603211416 (default, EPYC 7763): A 65.8, B 48.5, C 46.9, D 27.9, E 15.6, F 13.3, G 11.6, H 10.3, I 9.2, L 4.9
9. 40603495329 (default, EPYC 7763): A 71.7, B 50.0, C 47.1, D 28.1, E 17.0, G 13.5, F 13.3, H 10.7, I 9.4, K 5.0
10. 40603778252 (default, Xeon Platinum): A 65.3, C 44.8, B 42.8, D 26.2, E 15.2, F 12.7, G 11.9, I 9.8, H 9.7, J 5.0
11. 40604062431 (true, EPYC 9V74): A 44.1, B 43.1, D 27.2, C 9.8, F 5.4, G 5.1, L 3.9, K 3.9, J 3.6, H 3.5
12. 40604275747 (false, EPYC 7763): A 66.9, B 50.3, C 43.8, D 27.7, E 16.1, F 13.3, G 12.1, H 10.3, I 9.5, J 4.9
13. 40604562812 (true, EPYC 7763): A 55.0, B 47.3, D 24.8, C 10.8, F 7.5, G 5.3, L 3.9, K 3.9, H 3.9, E 3.5
14. 40604770236 (false, EPYC 7763): A 73.9, B 48.0, C 46.1, D 31.3, E 17.6, F 14.0, G 13.4, H 11.4, I 9.8, L 5.0
15. 40605053568 (true, EPYC 7763): A 54.0, B 47.6, D 25.0, C 11.2, F 7.5, G 5.6, H 4.0, M 3.7, L 3.6, E 3.4
16. 40605298179 (false, EPYC 9V74): A 64.0, B 44.2, C 44.0, D 26.3, E 15.6, F 12.4, G 12.1, H 10.7, I 8.9, L 4.9
17. 40605570324 (true, EPYC 9V45): A 32.0, B 23.9, D 16.2, C 7.7, G 3.4, L 2.9, K 2.9, J 2.8, H 2.8, F 2.8
18. 40605734098 (false, Xeon Platinum): A 61.1, C 38.6, B 35.0, D 27.7, E 14.9, F 11.7, G 11.4, H 9.9, I 9.0, K 5.0
19. 40606019960 (true, EPYC 7763): A 54.4, B 48.4, D 24.8, C 10.8, F 7.4, G 5.3, L 3.9, H 3.7, M 3.6, K 3.4
20. 40606228903 (false, EPYC 7763): A 73.2, B 49.4, C 49.2, D 30.8, E 16.9, F 14.0, G 13.8, H 11.3, I 10.3, K 5.8

## Limits

The arms are small (5 each, the p90 of five is its maximum) and the runner's CPU is drawn at random, so the arms do not hold the same CPUs; the EPYC 7763 comparison is the one that does (3 against 7 runs). The runs were made within one hour, so a time-of-day effect is not separated. The `kb-public` job ran beside `kb-tests` in each run and passed; its time is not measured here.
