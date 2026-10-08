---
name: kb-setup
description: Use when the it-ops-kb clone is fresh, a check or MCP server fails at start, or the user asks to set up the kb: checks Python, runs the checks and tests, installs the commit hook, registers the MCP servers, asks about the query log, reports pass/fail.
---

# Set up it-ops-kb

Work from the repository root. Change no kb content (the only changes are the local git setting in step 3, the local-scope MCP servers in step 4 and the per-user query log file in step 5). Do every step even if an earlier one fails, then report.

Read this section of the `kb/_self/` docs first, not the whole doc (`selfdoc.py section` prints the section under a heading with its line numbers). Nothing is committed and no kb content is written, so no other section is needed; the commands are spelled out in the steps below:
- `python3 _tools/selfdoc.py section maintaining "Setup (first session in a fresh clone)"`

Any other rule: `python3 _tools/rag.py pack --root _self "<question>"` (`-q` for several parts, `--budget 400`). `coverage: good` names a tested question: follow its line. `weak` or `none`: `python3 _tools/kb_ask.py --root _self "<question>"` has a reader quote the answering lines from the sections, or read the section it names with `python3 _tools/selfdoc.py section DOC HEADING`. A rule you needed and no set or question gave you is a miss: say so in your report, with the question as you asked it.

`AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Python
- Run `python3 --version`. Needs 3.11 or newer (the floor in `pyproject.toml`; CI tests it). Development and the tests use the newest stable CPython pinned in `.python-version` (3.14), which uv installs on the first `tests.py`.
- The tools are stdlib-only: install nothing for them. If `python3` is missing, stop and tell the user how to install it for their OS. The tests need uv (`uv --version`); without it, tell the user to install uv (on a Windows host without Python, `_tools/install-python.ps1` below installs both; on one that has a Python and lacks only uv, the pinned uv release by hand as `python/uv-windows-install` shows, not pip; elsewhere https://docs.astral.sh/uv/) and mark the test step SKIPPED.
- Windows: `python3` exit 49 with "Python was not found" is the Store alias, not Python. Offer `_tools/install-python.ps1` (the pinned python.org installer, SHA-256 and signature checked, per user, adds `python3.exe`; then the pinned uv from its GitHub release, SHA-256 checked, into `%USERPROFILE%\.local\bin` on the user PATH; `-SkipUv` leaves uv out); install only when the user agrees. The script always installs the pinned Python too (there is no switch to skip it), so on a host that has another Python and lacks only uv, install the pinned uv release by hand as `python/uv-windows-install` shows. Run it with `-CheckOnly` first, then without.
  - Exit 3, or any `CONFLICT:` line: something already on the host conflicts with the install, and nothing was installed. Quote every `CONFLICT:` line to the user in the chat, word for word, and ask with AskUserQuestion how to proceed (resolve it themselves, or install anyway). Rerun with `-AcceptConflicts` only on their explicit answer, never on your own.
  - `NOTE:` and `WARNING:` lines: list them in the report. A `WARNING:` that `python` or `python3` in a new session does not start the new install goes to the user at once, as a conflict does.
  - After an install, tell the user to restart Claude Code (the session keeps its old PATH), then run `/kb-setup` again.

## 2. Repository checks
Run each and record exit code and last line:
- `python3 _tools/check.py` (expect `errors=0`)
- `python3 _tools/fetch.py --offline` (expect `mismatch=0 unknown=0`)
- `python3 _tools/tests.py` (expect no failures; this is what CI runs; it needs uv, which installs pytest from `uv.lock` on first use)
- `python3 _tools/rag.py eval` (expect `passed` equal to `questions` on the last line: the lookup eval set)
- `python3 _tools/rag.py pack "kerberos delegation"` (expect a `coverage:` line, fact lines with `path:line` and a `sources:` footer)

A failure here is a finding. Do not "fix" kb files to make a check pass.

## 3. Commit hook
- Run `python3 _tools/kbgit.py install-hooks` (expect `installed` or `already installed`). It only sets `git config core.hooksPath .githooks` in this clone's local config (nothing is committed or pushed); the versioned commit-msg hook then adds the KB-* trailers (`KB-Topics`, `KB-Sources-*`, `KB-Answers`) to every kb commit, and never blocks a commit.
- Exit 2 with `core.hooksPath is already ...`: the user has their own hooks path. Do not override it; report it and let the user decide (chain `.githooks/commit-msg` and `.githooks/prepare-commit-msg` from their hooks, or unset theirs).
- Not a git clone (e.g. an unpacked archive): SKIPPED.
- Ask whether this clone has a public remote (a public GitHub copy of the repository). If so, and `git config --get kb.publishRemote` is empty, set it with `git config kb.publishRemote <remote>`: that remote then gets `main` only through `python3 _tools/kbgit.py publish`, without `kb/_querylog/` and any `_logs.csv`, and refusing a `_private` or `_cache` path (`kb/_self/git.md`, Public home). A production clone has none: leave it unset.

## 4. MCP servers
A clone uses four servers at local scope (this machine and this clone only): `kb` (`_tools/kb_mcp.py`) and the three no-auth documentation servers of `.claude-plugin/it-ops-kb-docs/.mcp.json`: `microsoft-learn`, `claude-code-docs`, `mcp-docs`. There is no root `.mcp.json` (it would load into the `it-ops-kb` plugin).
- Run `python3 _tools/kb_mcp.py --register-local`. It registers the missing ones with `claude mcp add-json --scope local` and reports `already registered` for the rest, except a `kb` server that runs another clone's `kb_mcp.py`, which it replaces. This is the one change besides step 3; it is local to this user and clone and can be undone with `claude mcp remove <name>`.
- Run `claude mcp list` and note each server's state. Servers registered in this session load only after a restart: tell the user to restart and run `/kb-setup` again for the calls below.
- The deciding test is the read-only call below: a server that answers is a PASS, whatever `claude mcp list` says.
- `Failed`: note the error. Test reachability with `curl.exe -sI https://learn.microsoft.com/api/mcp` (`curl.exe` on Windows, where PowerShell 5.1 maps `curl` to `Invoke-WebRequest`; `curl` elsewhere) (any HTTP status means the host is reachable; proxies and firewalls are the usual cause).
- `kb`: call `kb_status` and confirm it names this clone's commit. Before a restart, `python3 _tools/kb_mcp.py --status` shows the same from a shell, and its `registered:` line names the `kb_mcp.py` the registered `kb` server runs: a `registered_clone:` line means another clone's, so run the `reregister:` command it prints and restart.
- For each connected server make one read-only call and confirm it returns content:
  - `microsoft_docs_search` with query `DSC v3 resource manifest`
  - `search_claude_code_docs` with query `hooks`
  - `search_model_context_protocol` with query `tools list_changed` (this server can return a very large result; a non-empty answer is enough)
- Never call `submit_feedback` on any server. It posts text to the vendor and is denied in project settings.

## 5. Query log (ask)
Tell the person what the query log does by default, in these words or close to them, then ask whether to keep it:

- **Logging is on.** Every kb lookup in this clone's sessions (a `kb:` prompt, a kb MCP call, a `kb_ask.py` run, and the web and docs fetches of a prompt that used the kb) is logged to `_cache/querylog/spool/`. The spool holds prompts and answers as typed; it is never committed, and its rows are deleted once their entry is delivered (pushed, or in `local` stored), or after 30 days.
- **Text is sent to the API.** When a session ends, a background distill replaces addresses, ids, paths, user and host names, keys and tokens with placeholders by rule, then sends that rule-redacted text (the question the kb was asked, and the prompt and the reply) to the Claude API for Haiku, which only judges: whether the reply answered, which of the kb articles the lookup returned answers it, and whether the question names a person or an organisation (such an entry is dropped). Nothing Haiku writes is stored. The API keeps it under the organisation's retention: 30 days standard for commercial use (Team, Enterprise, API), unless zero data retention applies (`claude/data-retention.md`).
- **The kb's questions are recorded in the repository.** The redacted entries (the question the kb was asked, as the `kb:` hook, the kb tool call or `kb_ask.py` got it, never the prompt as typed; the verdict; the articles and the `path:line` and tag of the kb lines the lookup returned, never the reply; Haiku's judgement; fetched hosts and paths) are committed to `kb/_querylog/` and pushed to `main` on `origin`, readable by everyone who can read the repository.
- **Fixes, gap entries and pushes are automatic.** From those entries the pipeline commits eval rows, aliases, doc2query expansions and `_gaps.md` entries, and pushes them to `main` once the local gate passes; a conflict it cannot resolve becomes a merge request.
- **Research is off.** When turned on, a `claude -p` run with web search adds quote-checked facts and source rows, and `_conflicts.md` entries, to the articles of gap entries, capped by runs a day.

The choices: keep the default (`auto`); `local` (logged and distilled into `_cache/querylog/store/` only, Haiku still called, nothing committed or pushed); `off` (nothing logged, nothing sent). Research only when the person asks for it: `"research": true` with `"research_daily"` runs a day (3 when not given).

- Write the answer to `_private/querylog.json` (never committed), for example `{"mode": "auto", "research": false}`. When the person also uses the kb as a plugin in other projects, those sessions read `${CLAUDE_PLUGIN_DATA}/querylog/config.json` instead (the plugin's `data/<plugin-id>/` directory under `~/.claude/plugins/`, `claude/plugins.md`); write the same answer there if they want it for those sessions too.
- A file already there: show its `mode` and research setting and ask whether to keep them; change it only on their answer.
- No answer (a headless run): write nothing, and report that the default `auto` applies.
- Check with `python3 _tools/querylog.py where` (expect `mode=<the choice>`; `writes=no` for `off`). A file that cannot be read counts as `off`.

## 6. Optional GitHub server (ask first)
GitHub's remote MCP server (read-only repository tools, GA) needs the user's own token, so it is never committed. If the user wants it, show this command and let them run it themselves, with `GITHUB_PAT` set in their shell:
```
claude mcp add --scope user --transport http github-repos-ro https://api.githubcopilot.com/mcp/x/repos/readonly --header "Authorization: Bearer $GITHUB_PAT"
```
Never ask for the token or put it in a repo file.

## 7. Do not
- Run `fetch.py --diff` without a selection, or `--verify`/`--refresh`. They are long network jobs that write state. A first baseline is the user's decision.
- Commit anything.

## 8. Report
End with a short table: step, result (PASS/FAIL/SKIPPED), evidence (last output line or error). Include the query log's mode and research setting as the person chose them. Then list what the user must do (e.g. approve servers, install Python). Then point to the other skills: `/kb-lookup`, `/kb-review-workspace`, `/kb-gap`, `/kb-research`, `/kb-refresh`, `/kb-add-topic`, `/kb-census`, `/kb-verify`, `/kb-git-sync`.
