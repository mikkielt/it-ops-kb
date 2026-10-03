# _self: how this kb runs

Everything an agent needs to run, change and ship this kb, except the lookup rules that every session loads (`AGENTS.md`). People read the root `README.md`; nobody needs these files to use the kb, only to change it.

- **Not in the pack.** `pack`, `kb_pack` and the `kb:` hook never see `kb/_self/`, so the kb's own vocabulary (hook, skill, plugin, pack) never competes with the domain articles. Search it on purpose: `python3 _tools/rag.py search "<words>" --index` (MCP `kb_search` with `index`).
- **Read only what the job needs.** Each file serves one kind of work; the table says which. A skill names the files it relies on.

| file | read it when | kind |
|---|---|---|
| `kb/_self/maintaining.md` | before any change: setup, the skills that change the kb, conduct, the gate | rules |
| `kb/_self/content-rules.md` | writing articles, source rows, ledger entries or retrieval data | rules |
| `kb/_self/code.md` | writing or changing Python in `_tools/`: standard library only, portability, git in tests, deterministic output, exit codes, planted failures, flat prefixed modules behind a CLI facade, import direction | rules |
| `kb/_self/tools.md` | choosing or running a tool: commands, flags, exit codes, how pack decides | reference |
| `kb/_self/git.md` | committing, syncing, merging, reading the history | rules |
| `kb/_self/autopilot-test.md` | the pre-run checklist and staged test plan of the autopilot's first supervised run, its record and its stop | reference |
| `kb/_self/autopilot-container.md` | the plan to run the autopilot's runners in a Docker container: what it isolates and not, the pinned image, mounts, credentials, network allow-list, limits, the mapping to runner commands, macOS, the staged rollout and the operator's gates | plan |
| `kb/_self/plugin.md` | changing the plugin, installing it in another project, a team's own roots (`/kb-add-root`, `KB_ROOTS`) | rules and runbook |
| `kb/_self/embedding.md` | embedding the kb in another team's MCP server: the stdio child's command, roots, re-exposed tools, copied instructions, restarts and the contract test | contract |
| `kb/_self/runners.md` | setting up, moving or checking the project's two self-hosted GitLab runners (`docker-windows` on the host, `docker-linux` in WSL 2) | runbook |
| `kb/_self/hosting.md` | serving the kb to a remote MCP client by url (a Copilot Studio agent): which path to pick, and the runbook for `_tools/kb_http.py` behind an authenticating TLS front end | runbook |
| `kb/_self/design.md` | how the kb works and why; when it is token-efficient and when it is not | explanation |
| `kb/_self/alternatives.md` | comparing the kb with similar tools: what each overlaps with, how it differs, its licence, and when the kb or another tool fits | comparison |
| `kb/_self/token-efficiency.md` | changing anything a lookup touches (pack, the hooks, the MCP server, the router, agents, plugin, `AGENTS.md`): every token-saving technique, its file and its measurement | catalogue |
| `kb/_self/web-sources.md` | reading a web source during research, or a source family that keeps failing or grows large: the fetch route per family and the runbook for staging a new one | runbook |
| `kb/_self/doc2query.md` | document expansion for pack: protocol and results | protocol |
| `kb/_self/querylog.md` | building or changing the query log (capture, distill, redaction, the store, learn, apply, the direct push): its rules and every program default | design |
| `kb/_self/usage.md` | reading or changing how token usage is measured: the transcript reader (`kbusage.py`), what a usage record holds and never holds, the query log's usage sidecar | reference |
| `kb/_self/backlog.md` | planning, scheduling, working and closing changes to this project: epics, stories, tasks, subtasks, bugs and sprints in `kb/_self/backlog/`, the definition of done, gates and the horizon | runbook |
| `kb/_self/reports/` | the measurements `design.md` and `token-efficiency.md` rest on, each section with its setup; `benchmarks.md` generates its tables from `benchmarks.csv`, which `_tools/benchmarks.py` fills; `windows-fresh-host.md` records a clean Windows account going from no Python to every `/kb-setup` environment step | measurements |
| `kb/_self/map.csv` | which files each doc above describes (`selfdoc.py`) | data |

## Keeping it current

- **Code is the source of truth.** A doc here describes files named in `kb/_self/map.csv` (`doc,pattern`; a skill that restates a tool's behaviour, `.claude/skills/kb-ingest/SKILL.md` for `kbingest.py`, is a row's doc too). `python3 _tools/selfdoc.py stale` lists each doc whose described files changed after the doc's last commit; `/kb-self` is the runbook that brings them back in line, for one doc, a commit range or everything. A doc checked against a change that needed no edit goes in the commit's `Self-Reviewed: <doc>, <doc>` trailer, which clears it. A backlog item's check uses `stale --work ID`, which reads only the commits whose `KB-Work` trailer names the item, so a doc another change left stale does not fail it.
- **Tests hold the docs to the code.** Every `--flag` written next to a tool must exist in that tool, every backtick path must resolve, `AGENTS.md` stays under 4 KB and the root `README.md` under 8 KB, and every doc listed above is in `kb/_self/map.csv` (`python3 _tools/tests.py`).
- **One fact in one place.** A rule lives in one file; the others point to it. The tool table lives in `tools.md` only; the tools' own docstrings (`python3 _tools/<tool> --help`) are the full reference.
- **No sizes a command can measure.** Docs never record a file's current bytes, lines or characters (`wc` gives them before a commit); a cap is a rule and stays where its test is named; sizes inside a past measurement's setup stay with it.
- **Generated parts are never hand-edited** (each root's `_coverage.md` table, `_coverage.csv`, `used_in`).
- **The present, not the history.** Every doc here describes the kb as it is now: no plans, plan item numbers, "decided on" dates or superseded numbers; git keeps those (`git log`, `python3 _tools/kbgit.py log`). A date stays only where it is data or an identifier (a census tag, a protocol revision, a trailer format). A measurement says what was measured (Claude Code version, models, kb size, which tools existed), not when; when a new one supersedes it, replace the section. Open work, and only open work, is in the backlog (`kb/_self/backlog/`, run by `kb/_self/backlog.md`): its items describe their present state, and a sprint's items are deleted when it closes, since their commits (`KB-Work` trailers) record them.
