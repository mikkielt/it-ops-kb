# _self: how this kb runs

Everything an agent needs to run, change and ship this kb, except the lookup rules that every session loads (`AGENTS.md`). People read the root `README.md`; nobody needs these files to use the kb, only to change it.

- **Not in the pack.** `pack`, `kb_pack` and the `kb:` hook never see `kb/_self/`, so the kb's own vocabulary (hook, skill, plugin, pack) never competes with the domain articles. Search it on purpose: `python3 _tools/rag.py search "<words>" --index` (MCP `kb_search` with `index`).
- **Read only what the job needs.** Each file serves one kind of work; the table says which. A skill names the files it relies on.

| file | read it when | kind |
|---|---|---|
| `kb/_self/maintaining.md` | before any change: setup, the skills that change the kb, conduct, the gate | rules |
| `kb/_self/content-rules.md` | writing articles, source rows, ledger entries or retrieval data | rules |
| `kb/_self/tools.md` | choosing or running a tool: commands, flags, exit codes, how pack decides | reference |
| `kb/_self/git.md` | committing, syncing, merging, reading the history | rules |
| `kb/_self/plugin.md` | changing the plugin, installing it in another project, a team's own roots (`/kb-add-root`, `KB_ROOTS`) | rules and runbook |
| `kb/_self/design.md` | how the kb works and why; when it is token-efficient and when it is not | explanation |
| `kb/_self/token-efficiency.md` | changing anything a lookup touches (pack, the hooks, the MCP server, the router, agents, plugin, `AGENTS.md`): every token-saving technique, its file and its measurement | catalogue |
| `kb/_self/doc2query.md` | document expansion for pack: protocol and results | protocol |
| `kb/_self/work-left.md` | at the start of a maintenance session: the open work | state |
| `kb/_self/reports/` | the measurements `design.md` and `token-efficiency.md` rest on, each section with its setup | measurements |
| `kb/_self/map.csv` | which files each doc above describes (`selfdoc.py`) | data |

## Keeping it current

- **Code is the source of truth.** A doc here describes files named in `kb/_self/map.csv` (`doc,pattern`). `python3 _tools/selfdoc.py stale` lists each doc whose described files changed after the doc's last commit; `/kb-self` is the runbook that brings them back in line, for one doc, a commit range or everything. A doc checked against a change that needed no edit goes in the commit's `Self-Reviewed: <doc>, <doc>` trailer, which clears it.
- **Tests hold the docs to the code.** Every `--flag` written next to a tool must exist in that tool, every backtick path must resolve, `AGENTS.md` stays under 4 KB and the root `README.md` under 8 KB, and every doc listed above is in `kb/_self/map.csv` (`python3 _tools/tests.py`).
- **One fact in one place.** A rule lives in one file; the others point to it. The tool table lives in `tools.md` only; the tools' own docstrings (`python3 _tools/<tool> --help`) are the full reference.
- **Generated parts are never hand-edited** (each root's `_coverage.md` table, `_coverage.csv`, `used_in`).
- **The present, not the history.** Every doc here describes the kb as it is now: no plans, plan item numbers, "decided on" dates or superseded numbers; git keeps those (`git log`, `python3 _tools/kbgit.py log`). A date stays only where it is data or an identifier (a census tag, a protocol revision, a trailer format). A measurement says what was measured (Claude Code version, models, kb size, which tools existed), not when; when a new one supersedes it, replace the section. Open work, and only open work, is in `work-left.md`: a finished item leaves the file, since its commit records it.
