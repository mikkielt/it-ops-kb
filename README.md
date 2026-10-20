# it-ops-kb

## What it is

An offline knowledge base of facts from official sources on Windows endpoint management and the AI agents that operate it: ConfigMgr (MECM), Intune, Autopilot, Entra ID, Active Directory, Microsoft Graph, Group Policy, Defender, DSC v3, SQL Server, Power BI, GitLab CI, Ansible, the Python toolchain, security baselines, privacy (Presidio), the Model Context Protocol, Claude Code and AI agents.

- **Facts with provenance.** One topic is one Markdown article under `kb/<root>/<domain>/`. Every fact is one line that ends in a tag (`DOC` official, `CODE` source code at a pinned release, `DER` derived, `COMMUNITY` non-official, `UNK` not confirmed, `DECISION` an operator's call) and the ids of its sources, which record url, publisher, licence and date. `UNK` and `COMMUNITY` are leads, never answers on their own.
- **Retrieval without a model.** Stdlib Python tools in `_tools/` rank the fact lines for a question and return a verdict (`good`, `weak`, `none`), the best lines with `path:line` and one list of source urls, in 1-2k tokens. Counts, lists and joins are exact tool answers, not reading.
- **Upkeep by agents.** Skills research topics, refresh changed sources, run a census that re-confirms every source and verify quality. A gate of checks, tests and a lookup eval set must pass before every push.

Measured against a web-searching agent, the kb answers covered questions with a fraction of the input tokens, cost and time, and cites the article line and the source. The numbers, their setups and the cases where it does not pay off are in `kb/_self/design.md` and `kb/_self/reports/benchmarks.md`.

## Who it is for

- **AI agents** that look up Windows endpoint management facts and need a cited answer cheaply, in a session, a script or a project that installs the plugin.
- **Teams** that add their own roots beside the public one, so a lookup answers across vendor products and their own systems.
- **People** who decide what the kb should cover and review what the agents did. Nothing here is meant to be run by hand.

## Use it in five minutes

- **From another project:** ask Claude Code to set up the `it-ops-kb` plugin by following `kb/_self/plugin.md`, then ask your questions. Pin a census tag for a confirmed copy. The plugin also gives a project with a `backlog.json` the sprint, item and backlog skills.
- **In a clone:** `python3 _tools/rag.py pack "<question>"` prints the verdict, the fact lines and the source urls. A `kb: <question>` prompt in Claude Code answers without a model call, and `python3 _tools/kb_ask.py "<question>"` answers from a script.
- **Changing the kb:** open a clone in Claude Code and ask for the change in plain words. A hook names the skill that does it (`/kb-research`, `/kb-add-topic`, `/kb-refresh`, `/kb-census`, `/kb-verify`, `/kb-git-sync`).

## Where the rest lives

- `kb/_self/README.md`: start here; every doc agents read to run, change and ship the kb, with when to read each.
- `kb/_self/design.md`: how it works and why, and when it is token-efficient. `kb/_self/reports/benchmarks.md` holds the measurements.
- `kb/_self/plugin.md`: installing the plugin, a team's own roots. `kb/_self/backlog.md`: the approved backlog of sprints the kb changes by. `kb/_self/coordination.md`: how agents claim work, ask each other and are steered.
- `kb/`: the knowledge, one directory per root; `_tools/`: the tools; `AGENTS.md`: the short lookup rules every session loads; `.claude/` and `.claude-plugin/`: skills, agents, hooks and the plugin.

Code is Apache-2.0 (`LICENSE`), kb text CC BY 4.0 (`LICENSE-CONTENT`); snapshots and pinned files keep their sources' licences (`NOTICE`). Examples use placeholders only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`).
