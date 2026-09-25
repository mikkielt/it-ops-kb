---
name: kb-setup
description: First-time setup and health check of the it-ops-kb repository. Checks Python, runs the kb checks and stress tests, installs the local commit hook (KB-* trailers), makes sure the shared documentation MCP servers are approved and answering, and ends with a pass/fail report. Use when someone has just cloned the repo or asks to set it up.
disable-model-invocation: true
---

# Set up it-ops-kb

Work from the repository root. Change no kb content (the one change is the local git setting in step 3). Do every step even if an earlier one fails, then report.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Python
- Run `python3 --version`. Needs 3.9 or newer (the tools use `str.removesuffix` and `random.randbytes`).
- The tools are stdlib-only: install nothing. If `python3` is missing, stop and tell the user how to install it for their OS.

## 2. Repository checks
Run each and record exit code and last line:
- `python3 _tools/check.py` (expect `errors=0`)
- `python3 _tools/fetch.py --offline` (expect `mismatch=0 unknown=0`)
- `python3 _tools/stress_test.py` (expect `0 failed`; takes about 10 s)
- `python3 _tools/tests.py` (expect `OK`; this is what CI runs)
- `python3 _tools/rag.py search "kerberos delegation" -k 3 -u` (expect hits; `->` url lines appear only under chunks that cite a source)

A failure here is a finding. Do not "fix" kb files to make a check pass.

## 3. Commit hook
- Run `python3 _tools/kbgit.py install-hooks` (expect `installed` or `already installed`). It only sets `git config core.hooksPath .githooks` in this clone's local config (nothing is committed or pushed); the versioned commit-msg hook then adds the KB-* trailers (`KB-Topics`, `KB-Sources-*`, `KB-Answers`) to every kb commit, and never blocks a commit.
- Exit 2 with `core.hooksPath is already ...`: the user has their own hooks path. Do not override it; report it and let the user decide (chain `.githooks/commit-msg` and `.githooks/prepare-commit-msg` from their hooks, or unset theirs).
- Not a git clone (e.g. an unpacked archive): SKIPPED.

## 4. MCP servers
The repo shares three no-auth documentation servers in `.mcp.json`: `microsoft-learn`, `claude-code-docs`, `mcp-docs`.
- Run `claude mcp list` and note each server's state.
- The deciding test is the read-only call below: a server that answers is a PASS, whatever `claude mcp list` says.
- `Pending approval` next to a working server is normal before the folder is trusted, and in headless runs (`claude -p`), which load project servers without asking. For interactive use, tell the user to accept the trust prompt and restart, or approve the three servers in `/mcp`; `.claude/settings.json` pre-approves them once the folder is trusted. Do not write `.claude/settings.local.json` unless the user asks.
- `Pending approval` and the tools are unavailable in this session: FAIL, with the same advice.
- `Failed`: note the error. Test reachability with `curl -sI https://learn.microsoft.com/api/mcp` (any HTTP status means the host is reachable; proxies and firewalls are the usual cause).
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
End with a short table: step, result (PASS/FAIL/SKIPPED), evidence (last output line or error). Then list what the user must do (e.g. approve servers, install Python). Then point to the other skills: `/kb-lookup`, `/kb-research`, `/kb-refresh`, `/kb-add-topic`, `/kb-verify`.
