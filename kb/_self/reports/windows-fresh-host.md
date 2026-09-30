# Windows fresh host: from no Python to the /kb-setup environment steps

A clean Windows account going from no Python to every `/kb-setup` step that needs no Claude Code sign-in, run by the steps' own commands (`.claude/skills/kb-setup/SKILL.md`, steps 1 to 3). Re-run it with the same setup and replace the run sections when a new run supersedes them.

**Setup.** The Windows 11 Pro 25H2 host `PL-LT-00123` (build 26200.8655, AMD64), with Git for Windows 2.55.0 installed machine-wide and only `C:\Program Files\Git\cmd` of it on PATH (Git's defaults: no `sh`, `test` or other `usr\bin` tools). A temporary local **standard** account (not an Administrators member, no Developer Mode, so no symbolic-link privilege), created for the run with a random in-memory password and deleted with its profile afterwards; its steps ran in Windows PowerShell 5.1 through `Start-Process -Credential`, not in Git Bash. The kb came from a git bundle of `origin/main`, cloned by that account (no git credentials). The operator's account (`jan.kowalski`) only drove the run. Not run, by the operator's decision for this unattended run: the Claude Code sign-in for that account and so `/kb-setup` step 4 (`kb_mcp.py --register-local` and the MCP calls) and step 5 (the query log question); the steps below are the same commands the skill runs.

Before the install the account had no `python`, `python3`, `py` or `uv` on PATH (`python3` was not a command).

## Run 1: tests fail without Git Bash's tools

At `origin/main` c671478, 2026-09-30. `install-python.ps1 -CheckOnly` reported no conflict; `install-python.ps1` installed CPython 3.14.7 and uv 0.12.19 per user and added `python3.exe` (38 s). Every step up to the test suites passed (the same as run 2, below). `stress_test.py` failed 2 (86 passed) and `tests.py` failed 7 (1262 passed, 18 skipped, 1 xfailed):

- the item checks of `test_backlog.py` ran `test -f` and `true`, and `test_benchmarks.py` ran its shims through `sh`: Git Bash tools the account did not have on PATH (`[WinError 2]`);
- the two symbolic-link mutations of `test_stress.py` needed the privilege a standard account lacks (`[WinError 1314]`).

The operator's own sessions had hidden both: they run in Git Bash (its `usr\bin` on PATH) and elevated. Filed and fixed as BG-2j5ba56h (item checks as Python commands, shim steps skip without `sh`, the mutations skip on WinError 1314, with a planted test); its worker found and filed BG-ndgci3gc (benchmark shims Windows never resolves) and BG-37t2orjz (WSL's bash launcher taken for a hook shell).

## Run 2: every step passes

At `origin/main` ea85ddb, 2026-09-30, the same setup:

| step | exit | result |
|---|---|---|
| `install-python.ps1 -CheckOnly` | 0 | Preflight: nothing on this host conflicts with the install (2 s) |
| `install-python.ps1` | 0 | CPython 3.14.7 and uv 0.12.19 per user; `python`, `python3`, `py` and `uv` on the account's PATH (44 s) |
| `python3 --version` | 0 | Python 3.14.7 |
| `uv --version` | 0 | uv 0.12.19 |
| `check.py` | 0 | sources=2988 citations=16093 errors=0 (23 s) |
| `fetch.py --offline` | 0 | ok=164 mismatch=0 unknown=0 (3 s) |
| `rag.py eval` | 0 | questions=267 passed=267 (19 s) |
| `rag.py pack "kerberos delegation"` | 0 | a coverage line, fact lines and a sources footer |
| `kbgit.py install-hooks` | 0 | installed: core.hooksPath=.githooks |
| `stress_test.py` | 0 | 87 passed, 3 skipped (10:17) |
| `tests.py` | 0 | 1288 passed, 19 skipped, 1 xfailed (28:39) |

The skips are the tests that need `sh`, which the account did not have, and the OS-specific ones. Another session ran short test selections on the host during the run.

result: pass
