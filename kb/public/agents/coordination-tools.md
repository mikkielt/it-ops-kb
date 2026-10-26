---
topic: agents/coordination-tools
priority: P3
applies_to: "Open-source tools that coordinate parallel coding agents, track their tasks or predict and resolve their merge conflicts: MCP Agent Mail (Rust rewrite), Beads, Clash, Weave, Mergiraf and Herdr (READMEs read at the commits named in the sources, 2026-10-26)"
retrieved_utc: 2026-10-26
sources: [S-d362rhhe, S-egysxiw3, S-46ixkva7, S-ipq4eeyz, S-quwo3n36, S-4afyfcvi, S-yfwvfjhn, S-2lg3fy3j, S-mczbffct, S-l2373ghm, S-ffm4okjz]
status: partial
---

# Tools that coordinate parallel agents, track their tasks and predict or resolve their merge conflicts

## Summary
Parallel coding agents collide in three places, and the open-source tools read here each cover one: who is editing which files now (MCP Agent Mail's advisory file reservations, Weave's advisory entity claims), which tasks exist and who has taken them (Beads), and whether two branches will conflict (Clash predicts it from `git merge-tree`, Weave previews an entity-level merge, Mergiraf resolves a conflict that already happened). Herdr, covered in `agents/herdr-agent-state.md`, tracks the state of each agent, not the files it touches. None of them speaks the same wire format: reservations, claims, conflict verdicts and agent states each have their own shape. Licences differ and one matters here: MCP Agent Mail's licence is MIT with a rider that grants no rights to OpenAI, Anthropic and parties acting for them. The READMEs are the tools' own descriptions; none was run for this topic.

## Facts
### MCP Agent Mail (coordination by mail and file reservations)
- The original Python MCP Agent Mail repository is marked deprecated in favour of `mcp_agent_mail_rust`, the maintained Rust rewrite; both describe an MCP coordination layer for coding agents with identities, inboxes, threads and advisory file leases over Git and SQLite. [DOC S-46ixkva7]
- The Rust rewrite gives every agent an identity, an inbox and outbox and "advisory file reservations (leases) to signal editing intent", and offers them as MCP tools and resources, a CLI and a terminal UI. [DOC S-d362rhhe]
- An agent reserves paths with the MCP tool `file_reservation_paths(project_key, agent_name, paths, ttl_seconds, exclusive)`, with an optional `reason`; `paths` are glob patterns and a reservation is exclusive or shared. [DOC S-d362rhhe]
- Reservations are advisory, not hard locks: the README says that acquiring one reports conflicts instead of waiting for another agent to release its lease, and that each expires on its TTL. [DOC S-d362rhhe]
- A Git pre-commit guard installed by the tool blocks commits that touch files reserved by other agents, with narrow exemptions: an agent's own reservation, and `.beads/**` metadata so shared task state is not stranded. [DOC S-d362rhhe]
- State lives in SQLite for live reads and in a per-project Git archive of message, profile and reservation files as the durable ledger. [DOC S-d362rhhe]
- The README's workflow pairs it with Beads: an agent reserves its edit surface with a `reason` that names the task id, works, then closes the task and releases the reservation. [DOC S-d362rhhe]
- The licence file is "MIT License (with OpenAI/Anthropic Rider)": the rider says no rights are granted to OpenAI, Anthropic and their affiliates or anyone acting on their behalf, voids any permission given to them, and makes the rider control over the rest of the licence. [DOC S-egysxiw3]
- The rider's list of "use" includes copying, hosting, executing, benchmarking, testing and indexing the software, and it bars making the software or a derivative work available to or for a restricted party. [DOC S-egysxiw3]

### Beads (task tracking)
- Beads describes itself as a distributed graph issue tracker for AI agents, built on the Dolt version-controlled SQL database, with dependency tracking and JSON output for agents. [DOC S-ipq4eeyz]
- `bd ready` lists tasks with no open blockers and `bd update <id> --claim` atomically claims one, setting the assignee and the in-progress status. [DOC S-ipq4eeyz]
- Task ids are hash-based, which the README says prevents merge collisions in multi-agent and multi-branch workflows; sync between machines and agents goes through Dolt remotes (`bd dolt push` and `pull`). [DOC S-ipq4eeyz]
- `bd init` writes agent instructions (an `AGENTS.md` section) and installs integrations for Claude Code, Codex and Cursor unless told not to. [DOC S-ipq4eeyz]
- The repository read is `gastownhall/beads` and its licence file is MIT. [DOC S-quwo3n36]

### Clash (conflict prediction across worktrees)
- Clash is a command-line tool that finds merge conflicts between git worktrees of parallel AI coding agents early, before the work is merged. [DOC S-4afyfcvi]
- It discovers all worktrees, finds the merge base of each pair, simulates the merge with `git merge-tree` through the `gix` library and reports the conflicting files; the README calls this read-only. [DOC S-4afyfcvi]
- `clash check <file>` prints JSON with the file, the current worktree and branch and, per other worktree, `has_merge_conflict` and `has_active_changes`; exit 0 means no conflict, 2 conflicts found and 1 an error. [DOC S-4afyfcvi]
- `clash status` prints a conflict matrix over all worktree pairs, `--json` gives machine-readable output, and a Claude Code hook can run the check before every file write. [DOC S-4afyfcvi]
- It is MIT licensed. [DOC S-yfwvfjhn]

### Weave (entity-level merge, preview and advisory claims)
- Weave is a Git merge driver that parses base, ours and theirs into entities (functions, classes, keys) with tree-sitter and merges those instead of lines: changes to different entities resolve automatically, and one side modifying what the other deletes is flagged. [DOC S-2lg3fy3j]
- The merge is deterministic and stateless, "not a CRDT"; files over a size limit, binary files and types without a parser fall back to Git's line merge. [DOC S-2lg3fy3j]
- Its MCP server lists a `weave_preview` tool that dry-runs a merge of two branches and reports per-file verdicts, a findings document or the strategy used on each entity, beside tools to edit by entity, explain, check and land a merge. [DOC S-2lg3fy3j]
- A separate CRDT-backed layer (`weave-crdt`) holds live claims on entities; the README says the claims are advisory and not enforced, that a crashed agent's claims are not reaped, and that these tools are listed only with `WEAVE_EXPERIMENTAL=1`. [DOC S-2lg3fy3j]
- It is dual-licensed MIT or Apache-2.0 at the user's option. [DOC S-2lg3fy3j]

### Mergiraf (syntax-aware conflict resolution)
- Mergiraf is a syntax-aware Git merge driver for many languages and file formats; Git is configured to use it for merge, rebase, cherry-pick and revert, or it is run by hand after a conflict. [DOC S-mczbffct, S-l2373ghm]
- It errs on the side of caution and keeps conflict markers in suspicious cases, and when it resolves every conflict itself it points the user to `mergiraf review`. [DOC S-l2373ghm]
- It is licensed GPLv3. [DOC S-mczbffct]

### How they fit together
- Each tool answers a different question about the same agents: Herdr what state an agent is in, Beads which task it holds, Agent Mail and Weave's claims which files or entities it says it is editing, Clash and Weave's preview whether two branches will conflict, Mergiraf and Weave's merge how a conflict is resolved. [DER S-ffm4okjz, S-d362rhhe, S-ipq4eeyz, S-4afyfcvi, S-2lg3fy3j, S-l2373ghm: the one-line purpose each README or page gives, read side by side]
- Of the three claim stores only Agent Mail's reservation carries an expiry (`ttl_seconds`); Weave's entity claims stay until released, and Beads' claim is a task assignment with no expiry stated. [DER S-d362rhhe, S-2lg3fy3j, S-ipq4eeyz: the TTL in the reservation call against the crashed-agent note and the claim command]
- A reservation in Agent Mail carries a holder (`agent_name`), glob `paths`, a `ttl_seconds` and an optional `reason`, so an exchange of reservations between a coordination service and another store needs those four fields and a source label; it needs no Agent Mail-specific field. [DER S-d362rhhe: the fields of the `file_reservation_paths` call]
- Conflict output differs by tool: Clash gives JSON per file and worktree pair (textual, from a simulated three-way merge), Weave's preview gives per-file verdicts at entity level (semantic), and Mergiraf resolves rather than predicts; none of the READMEs describes a line format naming two branches, a path and a kind, so a consumer of one common line shape needs an adapter per tool. [DER S-4afyfcvi, S-2lg3fy3j, S-l2373ghm: the output each README describes]
- Of the licences read, MIT (Beads, Clash), MIT or Apache-2.0 (Weave) and GPLv3 (Mergiraf) name no party; Agent Mail's rider does, and a project that runs Claude-based agents should read it before installing or redistributing the tool. [DER S-egysxiw3, S-quwo3n36, S-yfwvfjhn, S-2lg3fy3j, S-mczbffct: the licence statements side by side]
- Whether using Agent Mail from a session of a user's own, with Claude as the model, counts as use "on behalf of" a restricted party is not stated in the licence text; it is a question for the licensor or a lawyer, not answered here. [UNK: the rider defines acting for or under the direction of a restricted party but gives no example of a customer's use of a model]
- Whether Agent Mail's guard, Weave's claims and Clash's hook reach a Claude Code session as a hook or as MCP tools only, and how they behave with `claude -p`, was not run for this topic. [UNK: the READMEs were read, not the tools run]

## Reference
| Tool | Covers | Coordination data | Licence |
|---|---|---|---|
| MCP Agent Mail (Rust rewrite) | mail between agents, file reservations, commit guard | `file_reservation_paths`: holder, globs, TTL, exclusive, reason | MIT with an OpenAI/Anthropic rider |
| Beads | task graph, atomic claim | `bd ready`, `bd update --claim`, Dolt remotes | MIT |
| Clash | conflict prediction between worktrees | `clash check` and `status --json` | MIT |
| Weave | entity-level merge, merge preview, advisory entity claims | `weave_preview`, CRDT claims | MIT or Apache-2.0 |
| Mergiraf | syntax-aware conflict resolution | merge driver, `mergiraf review` | GPLv3 |
| Herdr | agent state | JSON socket API (`agents/herdr-agent-state.md`) | see that topic |

Related: `agents/coordination-messages.md` (messages between agents and duplicate work), `agents/shared-state-concurrency.md`, `agents/herdr-agent-state.md`, `agents/peer-state-sync.md`.

## Examples
- SNIPPET: the reservation call of the Agent Mail README with a placeholder path and holder; context: MCP Agent Mail Rust rewrite README at the commit cited, a tool call as an MCP client sends its arguments; checked: no [DER S-d362rhhe: the argument names of the `file_reservation_paths` call]
```json
{"project_key": "/abs/path/to/repo", "agent_name": "GreenCastle", "paths": ["src/**"], "ttl_seconds": 3600, "exclusive": true}
```
