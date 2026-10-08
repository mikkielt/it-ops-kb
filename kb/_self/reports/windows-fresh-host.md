# Windows fresh host: from no Python to the /kb-setup environment steps

A clean Windows account going from no Python to every `/kb-setup` step that needs no Claude Code sign-in, run by the steps' own commands (`.claude/skills/kb-setup/SKILL.md`, steps 1 to 3). Re-run it with `_tools/cleanhost-run.ps1` (elevated; `-Short` for the step 4 and 5 commands that need no sign-in, without the test suite; `kb/_self/tools.md`), which makes the setup below and prints each step's exit code and last line, and replace the run sections when a new run supersedes them.

**Setup.** The Windows 11 Pro 25H2 host `PL-LT-00123` (build 26200.9448, AMD64), with Git for Windows 2.55.0.windows.3 installed machine-wide and only `C:\Program Files\Git\cmd` of it on PATH (beside the GitHub CLI's and the GitLab Runner's directories; Git's defaults: no `sh`, `test` or other `usr\bin` tools). A temporary local **standard** account (not an Administrators member, no Developer Mode, so no symbolic-link privilege), created for the run with a random in-memory password and deleted with its profile afterwards; its steps ran in Windows PowerShell 5.1 through `Start-Process -Credential`, not in Git Bash. The kb came from a git bundle of `origin/main`, cloned by that account (no git credentials). The operator's account (`jan.kowalski`) only drove the run. Not run, by the operator's decision for this unattended run: the Claude Code sign-in for that account and what needs it, `/kb-setup` step 4's `kb_mcp.py --register-local` and MCP calls and step 5's question to the person; step 4's `kb_mcp.py --status` and step 5's `querylog.py where`, which need no sign-in, run with `-Short` and did not run here (they ran at d10da8d, 2026-09-30, both exit 0). The steps below are the same commands the skill runs.

Before the install the account had no `python`, `python3`, `py` or `uv` on PATH (`python3` was not a command).

## Run

At `origin/main` `97e650478ca6a62eeacf3e2c8bae476b15ac1d33`, 2026-10-08 08:54 to 08:58 local time, `cleanhost-run.ps1` without `-Short` (exit 0), started by a Claude session of the operator's account (ST-2ukv6ysc):

| step | exit | result |
|---|---|---|
| `git clone` of the bundle | 0 | `97e65047 Merge branch 'code/ST-2ukv6ysc' into 'main'` (3 s) |
| `install-python.ps1 -CheckOnly` | 0 | Preflight: nothing on this host conflicts with the install. (1 s) |
| `install-python.ps1` | 0 | Done. Open a new terminal (and restart Claude Code) so the new PATH applies, then run /kb-setup. (44 s): CPython 3.14.7 and uv 0.12.19 per user; `python`, `python3`, `py` and `uv` on the account's PATH |
| `python3 --version` | 0 | Python 3.14.7 |
| `uv --version` | 0 | uv 0.12.19 (bea138450 2026-09-24 x86_64-pc-windows-msvc) |
| `check.py` | 0 | sources=3106 citations=16934 errors=0 (20 s) |
| `fetch.py --offline` | 0 | ok=164 mismatch=0 unknown=0 sources_with_sha=68 artifacts=164 (2 s) |
| `rag.py eval` | 0 | questions=560 passed=560 verdict_ok=560 found_ok=560 mean_chars=2493 (24 s) |
| `rag.py pack "kerberos delegation"` | 0 | a coverage line, fact lines and a sources footer (last line its S1297 source url) |
| `kbgit.py install-hooks` | 0 | installed: core.hooksPath=.githooks (prepare-commit-msg, commit-msg, pre-push); kb commits now get KB-* trailers (1 s) |
| `tests.py` | 0 | 57 passed, 1 skipped in 124.06 s, 8 workers (131 s with the start), under the win32 ceiling of 150 s |

The suite is the one after the rewrite `4d70166f` (58 ids, `_tools/tests_ceiling.json`); `stress_test.py` is no longer a `/kb-setup` step. pytest's short summary does not name the skipped test.

A first run the same morning at `42148c0e`, with the account then named after the script, failed `tests.py` (1 failed, 56 passed, 1 skipped): in the land scenario, `backlog.py check` read the account's user name from the environment, and its piece matched the script's own name in this story's goal and touches, so the gate refused the push. The account is now `kbch`, a name in which `bl_base.name_pieces` finds no piece; every other step of that run gave the same results as above.
