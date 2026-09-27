# Maintaining the kb

Read this before any edit, research, refresh, census, commit or push. A lookup needs only `AGENTS.md`, which every session and subagent loads; this file is read on demand, so it never costs a lookup anything. The other rules are split by job (see `_self/README.md`): `_self/content-rules.md` for what you write, `_self/tools.md` for the commands, `_self/git.md` for commits and pushes, `_self/plugin.md` for the plugin.

## Setup (first session in a fresh clone)

Run `/kb-setup` (Claude Code), or do the same by hand. In Claude Code on the web, `.claude/hooks/session-start.sh` (a SessionStart hook in `.claude/settings.json`) already installs the commit hooks, registers the MCP servers, runs `check.py` and points the new session to `_self/work-left.md`, on every start, resume and `/clear`.

1. **Python 3.9+** as `python3`. Nothing to install for the tools: they use the standard library only. The tests use pytest through uv (`pyproject.toml`, `uv.lock`); `tests.py` installs them on first run.
2. **Checks pass on a clean tree:**
   - `python3 _tools/check.py` -> `errors=0`
   - `python3 _tools/fetch.py --offline` -> `mismatch=0 unknown=0`
   - `python3 _tools/stress_test.py` -> no failures
3. **MCP servers are in place.** `python3 _tools/kb_mcp.py --register-local` registers, at local scope (this machine and this clone only), the `kb` server and the three documentation servers of `.claude-plugin/it-ops-kb-docs/.mcp.json` (listed in `AGENTS.md`). The root has no `.mcp.json` on purpose (`_self/plugin.md`).
   - `claude mcp list` must show `kb` and the three docs servers `Connected`. Their tools keep the names `.claude/settings.json` allows (`mcp__kb`, `mcp__microsoft-learn__...`).
   - `Failed`: check network or proxy access to the url; the servers need no credentials.
   - Do not load the plugin in a clone (`--plugin-dir .`): the project skills and agents and the local servers would load a second time under plugin names.
   - Other agents (not Claude Code): register the same three urls as streamable-HTTP MCP servers in your client.
   - Optional, per user: GitHub's read-only repository server needs a personal token. Add it at user scope, never in a repo file:
     `claude mcp add --scope user --transport http github-repos-ro https://api.githubcopilot.com/mcp/x/repos/readonly --header "Authorization: Bearer $GITHUB_PAT"`
4. **Git hooks:** `python3 _tools/kbgit.py install-hooks`, once per clone: KB-* trailers on commits, and the gate on a plain `git push` (`_self/git.md`).
5. **Do not** run `python3 _tools/fetch.py --diff` over the whole kb as part of setup: it is a long network job that writes `_fetch_state.csv`. A whole-kb baseline is the maintainer's decision; a targeted `--diff` from `/kb-refresh` is committed with that refresh.

## Skills that change the kb (`.claude/skills/`)

**A request to change the kb goes through one of these skills, never freehand edits.** Claude invokes them on its own: they are model-invocable, with descriptions that start with their trigger ("Use when ..."), and they stay out of the plugin, so their descriptions cost nothing in host projects. A person can still type them. Each names the `_self/` files it relies on.

The routing is also deterministic: `.claude/hooks/kb_change_router.py`, a UserPromptSubmit hook in `.claude/settings.json` (never in the plugin), adds one line of context to a prompt that asks for a change (add, update, fix, refresh, research, commit, push, ...), naming the likely skill from its words plus the rule below the table. Questions, `kb:` prompts, slash commands and harness messages (a subagent's report, a task notification) pass unchanged. `python3 .claude/hooks/kb_change_router.py --test "<prompt>"` shows what it adds. A new change skill needs a route there (`_tools/test_change_router.py` fails otherwise).

| skill | does | reads |
|---|---|---|
| `/kb-setup` | the setup above, with a pass/fail report | this file |
| `/kb-research <question>` | research a question in the context of the topics the kb has, then extend them | content rules, tools, git |
| `/kb-add-topic <domain>/<slug>` | research and write a new topic | content rules, tools, git |
| `/kb-refresh <topic\|dir\|file\|S-id>` | diff sources and update the facts | content rules, tools, git |
| `/kb-census [date]` | confirm every source is current: mechanical checks, reading the undecided ones, dates only for what was confirmed, a sample check, the census tag | content rules, tools, git |
| `/kb-verify [prefixes]` | quality gate before a commit or a push | content rules, tools |
| `/kb-git-sync [--push]` | sync with `origin/main` when `kbgit.py sync` stops (exit 1 or 3): resolves conflicts by meaning, fixes a red gate, pushes only when asked | git, content rules |
| `/kb-self [doc\|--since REV\|all]` | bring `_self/` back in line with the code, skills and config it describes | `_self/README.md`, `_self/map.csv` |

Any change ends with `/kb-verify`, then `python3 _tools/kbgit.py sync --push` (`/kb-git-sync` when it stops); a change to tools, skills, hooks, the plugin or a rule also runs `/kb-self`. The read-only skills (`/kb-lookup`, `/kb-review-workspace`, `/kb-gap`) follow `AGENTS.md` and the plugin rules.

## Conduct for changes

- Do not edit files listed in `_artifacts.csv` by hand; they are pinned by sha256 (`fetch.py --refresh` rewrites them).
- A change to `_tools/`, `.claude/`, `.claude-plugin/`, `.githooks/` or a rule changes what `_self/` says: run `python3 _tools/selfdoc.py stale --since @{upstream}` and update the docs it lists in the same commit (`/kb-self`).
- **The gate before proposing a commit** (about 60 s in all):
  - `python3 _tools/check.py` and `python3 _tools/build_index.py --check`;
  - `python3 _tools/kbgit.py fix --check`;
  - `python3 _tools/tests.py` (CI runs it; includes `rag.py eval` and the doc cohesion checks; lint errors in `_tools/lint_baseline.txt` are known debt, new ones fail);
  - `python3 _tools/stress_test.py` when `_tools/` changed;
  - `python3 _tools/fetch.py --offline`;
  - after reworded or removed facts, `python3 _tools/doc2query.py stale`;
  - `/kb-verify` shows no new errors in the files you touched.
- `tests.py` scans tracked files only: stage new files (`git add`) before running it, or they pass unchecked.
- Commit messages: conventional prefix (`docs(kb):`, `fix(kb):`, `feat(kb):`, `chore:`), imperative, body explaining why; your own trailers (e.g. `Co-Authored-By`) in the last paragraph, and the hook appends the KB-* ones after them. Commit only when asked. Push with `python3 _tools/kbgit.py sync --push` (`_self/git.md`).
