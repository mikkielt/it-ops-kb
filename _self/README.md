# _self: how this kb runs

Everything an agent needs to run, change and ship this kb, except the lookup rules that every session loads (`AGENTS.md`). People read the root `README.md`; nobody needs these files to use the kb, only to change it.

- **Not in the pack.** `pack`, `kb_pack` and the `kb:` hook never see `_self/`, so the kb's own vocabulary (hook, skill, plugin, pack) never competes with the domain articles. Search it on purpose: `python3 _tools/rag.py search "<words>" --index` (MCP `kb_search` with `index`).
- **Read only what the job needs.** Each file serves one kind of work; the table says which. A skill names the files it relies on.

| file | read it when | kind |
|---|---|---|
| `_self/maintaining.md` | before any change: setup, the skills that change the kb, conduct, the gate | rules |
| `_self/content-rules.md` | writing articles, source rows, ledger entries or retrieval data | rules |
| `_self/tools.md` | choosing or running a tool: commands, flags, exit codes, how pack decides | reference |
| `_self/git.md` | committing, syncing, merging, reading the history | rules |
| `_self/plugin.md` | changing the plugin, installing it in another project, a team's own kb (`KB_ROOT`) | rules and runbook |
| `_self/design.md` | how the kb works and why; when it is token-efficient and when it is not | explanation |
| `_self/doc2query.md` | document expansion for pack: protocol and results | protocol |
| `_self/coverage.md` | every topic's status, files and source count | generated (`build_index.py`) |
| `_self/work-left.md` | at the start of a maintenance session: the open work | state |
| `_self/reports/` | the measurements and plans `design.md` rests on | dated records |
| `_self/map.csv` | which files each doc above describes (`selfdoc.py`) | data |

## Keeping it current

- **Code is the source of truth.** A doc here describes files named in `_self/map.csv` (`doc,pattern`). `python3 _tools/selfdoc.py stale` lists each doc whose described files changed after the doc's last commit; `/kb-self` is the runbook that brings them back in line, for one doc, a commit range or everything. A doc checked against a change that needed no edit goes in the commit's `Self-Reviewed: <doc>, <doc>` trailer, which clears it.
- **Tests hold the docs to the code.** Every `--flag` written next to a tool must exist in that tool, every backtick path must resolve, `AGENTS.md` stays under 4 KB and the root `README.md` under 8 KB, and every doc listed above is in `_self/map.csv` (`python3 _tools/tests.py`).
- **One fact in one place.** A rule lives in one file; the others point to it. The tool table lives in `tools.md` only; the tools' own docstrings (`python3 _tools/<tool> --help`) are the full reference.
- **Generated parts are never hand-edited** (`coverage.md`, `_coverage.csv`, `used_in`). **Reports are dated records:** add a new section or file, never rewrite an old measurement. `design.md` and `work-left.md` carry the current conclusions.
