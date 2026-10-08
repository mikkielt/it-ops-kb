# Test suite speed on Windows

Where the time of `python3 _tools/tests.py` and `python3 _tools/stress_test.py` goes on the project's Windows 11 host, measured 2026-09-29/30 before any change. The plan that acts on it is the epic EP-hlnsqx4f “The test suites run in minutes on Windows, with no lost coverage” (`python3 _tools/backlog.py tree EP-hlnsqx4f`); the facts it rests on are in `kb/public/python/pytest.md`, `python/pytest-xdist.md`, `python/interpreter-startup.md`, `gitlab/git-test-repositories.md`, `windows/dev-drive.md`, `defender/asr-and-antivirus.md` and `windows/gitlab-runner-windows.md`, and the answer `QK-subprocess-heavy-pytest-suite-run-faster` in `kb/public/_answers.md`.

- **Host:** Windows 11 Pro build 26200, Intel i7-8665U (4 cores, 8 threads), 32 GB, C: NTFS (no Dev Drive), Microsoft Defender real-time protection on with no exclusions (platform 4.18.26080.4, engine 1.1.26080.3). Python 3.14.7 in a uv-managed `.venv` (uv 0.12.19), pytest 9.1.1, pytest-xdist 3.8.0, no `psutil`, Git for Windows 2.55.0.windows.3. The same PC hosts the project's CI runners (the WSL 2 Linux runner capped at 4 CPUs and 8 GB, and the docker-windows runner, `kb/_self/runners.md`).
- **Tree:** a worktree of `main` at `e152c86` plus this report's kb content changes (uncommitted during the runs, 1,841 files, 31 MB).
- **Host state:** every CI job on the host's runners was cancelled before the timed runs (operator's authorization, 2026-09-29 23:3x); the other local session held its gate runs, except one `tests.py -k TestCiAllManual` (under a minute) at 23:45 during run 1. CPU load before run 1 fell from 51% to 4% in 20 s.
- **Observers:** a pytest plugin loaded with `-p` wrote one line per test phase (worker, node id, phase, start, stop, duration), and in the counting runs a `sitecustomize.py` on `PYTHONPATH` logged each Python process's start, arguments, run time and every `subprocess.Popen` it made. Both only observe; the counting adds a file append per process.

## Full runs

| run | command (from the worktree) | started | wall | result | worker-seconds | setup share | utilisation | idle tail |
|---|---|---|---|---|---|---|---|---|
| 1 | `tests.py --durations=40 -p perflog` | 23:41 | 1,106 s | 1,119 passed, 11 failed (10 from uncommitted ledger order and a missing report path, 1 timing flake) | 7,678 | 55% | 87% | 1,124 s |
| 2 | run 1 plus the process counter | 00:10 | 1,203 s | 1,128 passed, 2 failed (a missing report path; a retrieval ranking changed by this change's content, fixed) | 8,298 | 53% | 87% | 1,251 s |
| 3 | `tests.py -p perflog --no-loadscope-reorder` | 00:47 | 1,190 s | 1 failed (report path) | 8,160 | 57% | 86% | 1,288 s |
| 4 | `tests.py -p perflog --dist worksteal` | 01:09 | see below | | | | | |
| stress | `stress_test.py --durations=40 -p perflog` | 00:35 | 462 s | 88 passed, 1 skipped | 3,495 | 2% | 95% | 175 s |

- Every tests.py run collected 1,134 of 1,223 ids (89 stress ids deselected) on 8 workers: `-n auto` without `psutil` counts logical CPUs on Windows (`python/pytest-xdist.md`).
- Collection alone: 13.5 s inside the xdist run (each worker collects), 2.6 s in one process (`uv run --frozen python -m pytest _tools -m "not stress" --collect-only -q`, 6.0 s wall with uv). Importing pytest takes 0.9 s.
- The `-n 4` run was dropped at the operator's word (2026-09-30), so the worker count is left to ST-5q5b5qtz.

## Where tests.py's time goes (run 1)

Per file, worker-seconds (total, setup, call), sorted by total:

| file | total | setup | call | tests |
|---|---|---|---|---|
| test_querylog_e2e.py | 2,930 | 2,481 | 438 | 32 |
| test_querylog.py | 1,816 | 605 | 1,197 | 427 |
| test_sync.py | 593 | 581 | 7 | 24 |
| test_kb_mcp.py | 315 | 16 | 286 | 66 |
| test_kb.py | 313 | 0 | 309 | 70 |
| test_research_merge.py | 288 | 276 | 5 | 6 |
| test_kb_root.py | 226 | 0 | 226 | 5 |
| test_kbingest.py | 193 | 6 | 186 | 69 |
| all other 20 files | 1,004 | | | 415 |

- The costliest loadscope units: `TestAutonomousConverge` 518 s, `TestFixes` 446 s, `TestApply` 376 s, `TestSyncInGit` 364 s, e2e `TestResearch` 331 s, `test_kb_mcp.py` 294 s, `TestHostRefusalsInGit` 293 s, `TestResearchMergeInGit` 288 s, `TestModesAuto` 234 s, `test_kb_root.py` 226 s, `TestRedaction` 199 s, `TestTwoClones` 200 s.
- Scheduling: loadscope hands out the scopes with the most tests first, so these few-test, long-setup classes start 500-1,050 s into the run; the run ends with 1,124 idle worker-seconds (about 140 s of wall time). File order (`--no-loadscope-reorder`, run 3) did not help.
- Contention: `TestFixes` alone in one process (`tests.py -n 0 -k "TestFixes and e2e"`) spends 157 s in setup and 147-160 s in all, against 446 s inside the full run: the full run slows each scenario about 2.8 times.

## Process starts (run 2)

- Python code started 8,295 processes: 6,920 git, 1,044 python, 139 sh, 1 uv, the rest the ingest fixtures' fake toolchains. 1,559 Python interpreters started in all (children of git and sh included when they run Python).
- The most frequent git commands: `rev-parse` 1,568, `cat-file` 739, `-C ...` 714, `show` 455, `log` 427, `config` 340, `rev-list` 300, `commit` 262, `diff` 239, `add` 226; `clone` 90, `init` 96, `worktree` 62.
- Tool runs in the full suite, by total seconds (runs over 5 s among them): `kbgit.py sync` 1,639 s in 47 runs (40 over 5 s), `check.py` 1,322 s in 73 (42), `querylog.py apply` 1,272 s in 34 (6, the longest 426 s), `kbgit.py fix` 599 s in 52 (36), `kb_hook.py` 480 s in 55 (13), `querylog.py learn` 447 s in 33 (12). Nested runs count in both their own row and their parent's.
- In `TestFixes` alone: 387 process events; `querylog.py apply` 53 s, two `querylog.py learn` 12 s each, the first `check.py` 11 s and the second 0.9 s, one `kbgit.py sync --push` 16 s.

## One process, one command (idle host, 2026-09-30 00:00)

`gate_cost.py` in the session scratchpad, medians:

| what | time |
|---|---|
| `python -c pass` (the venv's 3.14.7) | 50.6 ms (n=20) |
| `python -S -c pass` / `python -I -c pass` | 36.1 ms / 47.3 ms |
| `python -c "import kbcommon"` in `_tools` | 67.0 ms |
| `git --version` / `git rev-parse HEAD` | 19.4 ms / 23.1 ms |
| `sh -c true` (Git Bash) | 32.7 ms |
| `sh _tools/kbpy -c pass` | 110.5 ms (n=10) |
| `uv run --frozen python -c pass` | 76.8 ms (n=10) |
| `check.py` / `build_index.py --check` / `fetch.py --offline` | 0.86 s / 0.50 s / 0.24 s (warm) |
| `doc2query.py stale` / `selfdoc.py stale --since HEAD~1` / `kbgit.py fix --check` | 0.42 s / 0.33 s / 1.47 s |
| `rag.py eval` | 5.33 s |
| bare clone plus repack of the kb | 1.28 s |
| `git clone` of the seed with checkout / `git clone --bare` / `git worktree add` | 2.25 s / 0.24 s / 2.15 s |
| `git commit --allow-empty` in a full clone / with `gc.auto=0` and `maintenance.auto=false` | 0.14 s / 0.10 s (n=5) |

Earlier the same day, under the CI jobs' load (23:34), the system Python took 78 ms, `git --version` 211 ms (max 723 ms).

## Cold trees: first open and the pack index

- **First open of new files** (`firstopen.py`, `hardlink.py`): in a fresh `git clone` of the kb, reading every one of its 1,841 files once took 18.9 s and the second read 0.3 s; `check.py` then took 1.5 s. In a second fresh clone not read first, `check.py` took 15.3 s, then 1.4 s. A `shutil.copytree` of a read clone gave 15.3 s for its first `check.py`. A hard-linked copy (`os.link` per file) of a read template took 0.42 s for its first full read, a plain copy 19.4 s. The cost follows the file, not the name: it fits Defender's synchronous scan of a new file on open, which the Defender performance recording below confirms.
- **Cold pack index** (`cold.py`): in a fresh clone the first `rag.py pack` took 12.8 s and the next 0.29 s; `rag.py eval` took 21.2 s cold and 7.5 s warm. The index is a file named by a content key (`kbfacts.index_path`), and a linked worktree of a clone reuses the clone's index for unchanged content: on 2026-10-07 a fresh worktree's first `rag.py pack` took 0.7 s against 14.3 s before. No git scenario of today's suite builds an index.

## stress_test.py

- 462 s wall, 3,495 worker-seconds on 8 workers, 95% utilisation, 175 idle worker-seconds at the end: the time is inside the tests, not in scheduling.
- The slowest: `test_corpus_scaling` 216 s; `test_mutation` cases 50-162 s each (3,000 extra topic files 162 s, 20 MB single-line article 121 s, 100k citations 93 s, most others 50-85 s).
- One mutation alone (`stress_test.py -n 0 -k "BOM and sources"`): 34.6 s, of which `rag.py search` 17.2 s (cold index after the mutation), `check.py` 10.9 s (first open of the fresh copy), `fetch.py --offline` 1.5 s, the copy itself the rest.
- `--dist load` spreads the module-scoped `base` copy's tests over all workers, so it is built 8 times.

## kb-tests-windows in CI

- Manually started jobs of 2026-09-29 (16816987768, 16818397132, 16820119881, 16821688871) ran 60.6-60.9 minutes and failed with `job_execution_timeout` (the 1-hour job timeout). Job 16821688871's log: the container reported `created: 2/2 workers`, pytest started at 22:09:30, and the job stopped at 23:08 at about 92% of tests.py; stress_test.py never ran.
- At the host's measured 7,700-8,300 worker-seconds for tests.py, two workers need more than an hour even at the host's speed, before the container's own overhead. The CPU count a hypervisor-isolated container sees is the runner's `[runners.docker] cpus` (`windows/gitlab-runner-windows.md`), an operator decision (ST-jpl4hh4q).
- The Linux `kb-tests` job on the WSL runner: 13.5 min (success, 20:06) and 32.9 min (failed, 20:32) that day.

## What this says

1. Setup, not test bodies, is the cost: 55% of tests.py's worker time is fixture setup, and each git scenario pays for fresh full-kb trees whose first open and cold pack index cost about 15-30 s each on this host, repeated by every sync, apply and learn inside it.
2. Process starts are cheap here on an idle host (19-110 ms each); about 8,300 of them are a few minutes of worker time, not the half hour the suite takes.
3. Scheduling wastes about 140 s of wall time at the end of tests.py, and file order does not fix it.
4. The stress suite is dominated by per-case copies and cold rebuilds after each mutation.
5. The CI Windows job cannot finish at 2 CPUs whatever the suite's scheduling.
6. The largest saving of all is not running the full suite for changes that cannot break it: most commits change only kb content, whose checks take seconds (ST-hwk2acoz, P1).

## After the suite was rewritten small (macOS host, 2026-10-06)

The figures above describe the suite as it was on 2026-09-29/30. It has since been replaced by a small one under a ceiling (`_tools/tests_ceiling.json`; `kb/_self/code.md`, Checks and their tests). One full `python3 _tools/tests.py` on the macOS host (14 cores, other sessions idle), read from its `test.run` ops row:

| run | workers | tests | test files | wall | worker time |
|---|---|---|---|---|---|
| full, default workers | 12 | 53 | 11 | 14.5 s | 62.9 s |
| full, `KB_TEST_WORKERS=6` | 6 | 53 | 11 | 16.1 s | not read |

The four end-to-end scenarios hold most of the worker time (sync 13.6 s, land 13.4 s, pre-push 10.9 s, publish 10.1 s); no other file takes 5 s. The wall time is the slowest file plus the workers' start, which is why files are handed to the workers slow ones first (`conftest.SLOW_FIRST`) and the default worker cap covers one worker per file. The ceiling's seconds are 20 on macOS and 60 on Windows and Linux; the Windows host and the two CI runners are not measured in this section.

## Defender's cost on the suite (Windows host, 2026-10-07)

One full `python3 _tools/tests.py` at `96c30c7` (54 tests, 11 files, 8 workers), run while an elevated session recorded Defender for 180 s: `New-MpPerformanceRecording -RecordTo <file.etl> -Seconds 180`, then `Get-MpPerformanceReport -Path <file.etl>` with `-TopProcesses`, `-TopExtensions`, `-TopFiles` and `-TopScans 20000` (`kb/public/defender/asr-and-antivirus.md`). Defender platform 4.18.26090.9, real-time protection on with no exclusions. The suite passed in 97.5 s (pytest's time) against 84-88 s for the same suite on the quiet host the same day (`kb/_self/reports/windows-run.md`), the recording's own load included.

The recording holds 9,106 scans and 84.2 s of scan time. Scan time is summed over the scans, which the 8 workers make at once, so it is not wall time. The report's durations are counts of 100 ns intervals in its `-Raw` output (`kb/public/defender/asr-and-antivirus.md`); the figures here are those durations in seconds.

| scanned files under | scans | scan seconds |
|---|---|---|
| pytest's scratch trees (`%LOCALAPPDATA%\Temp\pytest-of-<user>\`) | 3,644 | 44.2 |
| the clone the suite runs in (its worktree) | 4,046 | 38.0 |
| other Temp, Python and uv, the main checkout, the rest | 1,416 | 2.0 |

The third row's seconds are the total less the first two rows (the recording is not in the repository); the per-process split gives the same remainder (84.2 - 70.4 - 11.7 = 2.1 s, within rounding).

- By process: `python.exe` 7,668 scans, 70.4 s; `python3.exe` 703, 11.7 s; every other process under 0.6 s.
- By extension: `.md` 1,752 scans, 32.3 s; `.txt` 790, 19.3 s; `.json` 863, 9.0 s; `.csv` 608, 7.8 s; `.py` 353, 5.1 s; `.jsonl` 413, 4.5 s; `.pyc` 2,810, 1.7 s; the other extensions hold the remaining 4.5 s.
- The single costliest scans, about 0.4-0.5 s each, are first opens of `kb/public/_anchors.csv`, `_conflicts.md` and `kb/_self/tools.md`, in the clone and in each scenario's `clone1` under pytest's scratch root.
- `Get-MpPerformanceReport -TopPaths` grouped every scan under `c:` whatever `-TopPathsDepth` was given, so the table above groups `-TopScans` by path prefix instead.

Settled by the operator (gate `scratch-root` of ST-xjb4wykm): no change. The scratch trees stay in the default per-user Temp root with synchronous scanning, so nothing was applied, and the cost above is the suite's standing cost on this host: about half of the scan time is the scratch trees, the other half the clone's own kb files read by the tools.
