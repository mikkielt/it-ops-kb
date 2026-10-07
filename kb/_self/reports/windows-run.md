# Windows host: a full test suite run by a Claude session

The last full `python3 _tools/tests.py` run a Claude session made on the project's Windows host, against the win32 ceiling of `_tools/tests_ceiling.json`. Re-run it from a Claude session in a clone on that host, with nothing else running there, and replace the run section when a new run supersedes it.

**Setup.** The project's Windows 11 Pro host (build 26200, AMD64, 8 logical processors), CPython 3.14.7 with pytest 9.1.1 and pytest-xdist 3.8.0 through uv, Git for Windows 2.55.0. The session ran the suite through the Bash tool (Git Bash) in its own worktree of the clone, `time python3 _tools/tests.py`, with the default workers (8).

## Run

At commit `22bf0ab1621d4528ccd08e47b31dd61e07f96533`, 2026-10-07T09:54Z, the host quiet:

| measure | value |
|---|---|
| result | exit 0, 54 passed (54 ids in 11 files) |
| pytest's time | 86.94 s |
| wall time | 87.6 s |
| ceiling | win32 `max_seconds` 150 (decision D-776rvpx2) |

The same suite at earlier commits of the same day took 136 s while a sprint worker shared the host, and 88 s and 84 s quiet: a run with other work on the host takes about half again as long.
