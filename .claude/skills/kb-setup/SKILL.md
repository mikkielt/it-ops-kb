---
name: kb-setup
description: First-time setup and health check of the it-ops-kb repository. Checks Python, runs the kb checks and stress tests, installs the local commit hook (KB-* trailers), registers the kb and documentation MCP servers at local scope and checks they answer, and ends with a pass/fail report. Use when someone has just cloned the repo or asks to set it up.
disable-model-invocation: true
---

# Set up it-ops-kb

Work from the repository root. Change no kb content (the only changes are the local git setting in step 3 and the local-scope MCP servers in step 4). Do every step even if an earlier one fails, then report.

Read `MAINTAINING.md` first: the content rules, tools, git workflow and commit rules this skill relies on (`AGENTS.md` covers lookups only).

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Python
- Run `python3 --version`. Needs 3.9 or newer (the tools use `str.removesuffix` and `random.randbytes`).
- The tools are stdlib-only: install nothing. If `python3` is missing, stop and tell the user how to install it for their OS.

## 2. Repository checks
Run each and record exit code and last line:
- `python3 _tools/check.py` (expect `errors=0`)
- `python3 _tools/fetch.py --offline` (expect `mismatch=0 unknown=0`)
- `python3 _tools/stress_test.py` (expect `0 failed`; takes about 35 s)
- `python3 _tools/tests.py` (expect `OK`; this is what CI runs)
- `python3 _tools/rag.py search "kerberos delegation" -k 3 -u` (expect hits; `->` url lines appear only under chunks that cite a source)

A failure here is a finding. Do not "fix" kb files to make a check pass.

## 3. Commit hook
- Run `python3 _tools/kbgit.py install-hooks` (expect `installed` or `already installed`). It only sets `git config core.hooksPath .githooks` in this clone's local config (nothing is committed or pushed); the versioned commit-msg hook then adds the KB-* trailers (`KB-Topics`, `KB-Sources-*`, `KB-Answers`) to every kb commit, and never blocks a commit.
- Exit 2 with `core.hooksPath is already ...`: the user has their own hooks path. Do not override it; report it and let the user decide (chain `.githooks/commit-msg` and `.githooks/prepare-commit-msg` from their hooks, or unset theirs).
- Not a git clone (e.g. an unpacked archive): SKIPPED.

## 4. MCP servers
A clone uses four servers at local scope (this machine and this clone only): `kb` (`_tools/kb_mcp.py`) and the three no-auth documentation servers of `.claude-plugin/it-ops-kb-docs/.mcp.json`: `microsoft-learn`, `claude-code-docs`, `mcp-docs`. There is no root `.mcp.json` (it would load into the `it-ops-kb` plugin).
- Run `python3 _tools/kb_mcp.py --register-local`. It registers the missing ones with `claude mcp add-json --scope local` and reports `already registered` for the rest. This is the one change besides step 3; it is local to this user and clone and can be undone with `claude mcp remove <name>`.
- Run `claude mcp list` and note each server's state. Servers registered in this session load only after a restart: tell the user to restart and run `/kb-setup` again for the calls below.
- The deciding test is the read-only call below: a server that answers is a PASS, whatever `claude mcp list` says.
- `Failed`: note the error. Test reachability with `curl -sI https://learn.microsoft.com/api/mcp` (any HTTP status means the host is reachable; proxies and firewalls are the usual cause).
- `kb`: call `kb_status` and confirm it names this clone's commit.
- For each connected server make one read-only call and confirm it returns content:
  - `microsoft_docs_search` with query `DSC v3 resource manifest`
  - `search_claude_code_docs` with query `hooks`
  - `search_model_context_protocol` with query `tools list_changed` (this server can return a very large result; a non-empty answer is enough)
- Never call `submit_feedback` on any server. It posts text to the vendor and is denied in project settings.

## 5. Optional GitHub server (ask first)
GitHub's remote MCP server (read-only repository tools, GA) needs the user's own token, so it is never committed. If the user wants it, show this command and let them run it themselves, with `GITHUB_PAT` set in their shell:
```
claude mcp add --scope user --transport http github-repos-ro https://api.githubcopilot.com/mcp/x/repos/readonly --header "Authorization: Bearer $GITHUB_PAT"
```
Never ask for the token or put it in a repo file.

## 6. Do not
- Run `fetch.py --diff` without a selection, or `--verify`/`--refresh`. They are long network jobs that write state. A first baseline is the user's decision.
- Commit anything.

## 7. Report
End with a short table: step, result (PASS/FAIL/SKIPPED), evidence (last output line or error). Then list what the user must do (e.g. approve servers, install Python). Then point to the other skills: `/kb-lookup`, `/kb-research`, `/kb-refresh`, `/kb-add-topic`, `/kb-census`, `/kb-verify`, `/kb-git-sync`.
