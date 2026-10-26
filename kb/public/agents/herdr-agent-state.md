---
topic: agents/herdr-agent-state
priority: P3
applies_to: "Herdr v0.9.5 (open-source terminal workspace manager for coding agents; docs read at the v0.9.5 tag, 2026-10-26)"
retrieved_utc: 2026-10-26
sources: [S-ffm4okjz, S-h5xo2alh, S-trea7px4, S-ww43mymu, S-yxd37uaa]
status: partial
---

# Herdr: the state of coding agents (idle, working, blocked, done) and its JSON socket API

## Summary
Herdr runs several coding agents in persistent terminal panes and reports, for each agent, one of five states: `idle`, `working`, `blocked`, `done` or `unknown`. A script or another tool reads those states through a newline-delimited JSON API on a local socket (`agent.list`, `agent.get`, `agent.wait`, `events.subscribe`), or through the `herdr agent ...` commands that wrap it. For an agent Herdr recognises, the state comes from reading the pane's screen against detection rules; an agent that supports Herdr (or an integration of your own) reports its state itself with `pane.report_agent`. The pages read are the Herdr documentation at its v0.9.5 tag; the project is Apache-2.0 licensed. This topic is the kb's record of an external agent-state source that a monitor can read through a JSON contract; how Claude Code reports its own state is in `claude/parallel-sessions.md` and `claude/ci-and-headless.md`.

## Facts
### What Herdr tracks
- Herdr keeps each agent in a real terminal pane, tracks which panes hold agents and rolls their state up to the tab and the workspace, so one blocked agent makes its pane, tab and workspace look blocked. [DOC S-ffm4okjz]
- An agent gets Herdr support in one of two ways: Herdr supports it (recognises the process and reads its state), or the agent supports Herdr itself and reports its own state; either way the state is idle, working or blocked, Herdr notifies when the agent finishes or needs you, and scripts can wait on it. [DOC S-ffm4okjz]
- The statuses the API and CLI report are `idle`, `working`, `blocked`, `done` and `unknown`: `idle` and `done` both mean ready for input, `done` is idle and not yet seen (focusing the pane or agent marks it seen, a read does not, and each TUI client tracks viewed completions on its own), `blocked` means Herdr recognised an approval or question UI, and `unknown` means an agent is present but Herdr cannot classify it, "not that its work succeeded". [DOC S-ww43mymu]

### How the state is found
- For an agent Herdr supports, Herdr finds the agent's process in each pane and reads the live bottom of the pane, not the scrolled part; rules in a detection manifest decide whether that screen means idle, working or blocked, and when an integration also reports state Herdr uses those reports instead of the screen. [DOC S-ffm4okjz]
- Blocked detection is strict for screen-manifest agents: Herdr marks `blocked` only when the bottom-buffer snapshot matches a known visible approval, question or permission UI, and falls back to `idle` (labelled `default_known_agent_idle_fallback` in explain output) when no rule matches, so an unusual new prompt may first show as idle; the page warns that idle is not authorisation to approve an action. [DOC S-ffm4okjz]
- Of the integrations, those for Pi, OMP, Kimi Code CLI, OpenCode, Kilo Code CLI and MastraCode also report state, and the others leave state to screen detection; the Claude Code hook, installed with `herdr integration install claude`, reports session identity at session start while Claude Code's state comes from screen detection. [DOC S-yxd37uaa]
- The Claude integration writes a hook script `hooks/herdr-agent-state.sh` and adds hook entries to `settings.json` under `~/.claude` (or `CLAUDE_CONFIG_DIR`); the directory must already exist, and uninstall removes the entries and the script. [DOC S-yxd37uaa]
- Antigravity and Grok count as idle once they return to their prompt even while background tasks, monitors or subagents still run, and `agent wait` and `agent prompt --wait` observe the agent's state, not the end of those jobs. [DOC S-ffm4okjz]
- A wrapper that hides the real agent process (a VM or sandbox runner) is declared with `HERDR_AGENT=<agent>` on the wrapper command, which only applies to that foreground process. [DOC S-ffm4okjz]
- `herdr agent explain <target> --json` shows the final state, the manifest source and version, the matched rule and any fallback reason, for a wrong state. [DOC S-ww43mymu]

### The socket API
- Herdr speaks newline-delimited JSON over a local socket (a Unix domain socket, a named pipe on Windows): one request per line, `{"id":"req_1","method":"ping","params":{}}`, answered by a line with the same `id` and a `result`; an error response echoes the `id` when the line reached JSON decoding. [DOC S-h5xo2alh]
- A process Herdr manages in a pane gets `HERDR_SOCKET_PATH`, `HERDR_ENV=1` and the workspace, tab and pane ids in its environment; the socket is chosen by the CLI `--session` option, then `HERDR_SOCKET_PATH`, then `HERDR_SESSION`, then the default session socket, and `HERDR_SOCKET_PATH` is for low-level overrides only. [DOC S-h5xo2alh]
- The agent methods are `agent.list`, `agent.get`, `agent.read`, `agent.explain`, `agent.send_keys`, `agent.prompt`, `agent.wait`, `agent.rename`, `agent.focus`, `agent.start` and the agents-view methods; `agent.list` and `agent.get` expose `agent_session` (when a native session reference is stored), `foreground_cwd` and the terminal title fields. [DOC S-h5xo2alh]
- `events.subscribe` takes subscriptions such as `{"type":"pane.agent_status_changed","pane_id":"w1:p1","agent_status":"blocked"}`, answers with an acknowledgement and then pushes event lines; history is not durable, and a subscriber that falls behind gets an error with `error.code` `events_lost` and its connection closed, after which the reader opens a new subscription and reconciles with `session.snapshot` on another connection. [DOC S-h5xo2alh]
- Snapshots and events share no sequence boundary and ordering is guaranteed only within one subscription entry, so a reader treats an event as a signal to read again, not as a payload to replay onto a snapshot. [DOC S-h5xo2alh]
- `agent.wait` is server-owned and event-driven and pins the resolved pane occupant so a replacement cannot satisfy the wait; `agent.prompt` with a `wait` object submits the prompt and starts the wait in one request and returns `agent_blocked`, sending nothing, when the agent is already blocked. [DOC S-h5xo2alh]
- `herdr agent wait <target> [--until STATUS]... [--timeout MS]` returns at once when the current status matches, and `wait` and `prompt --wait` default to `idle`, `done` or `blocked`; `unknown` must be asked for with `--until unknown`. [DOC S-ww43mymu]
- A prompt sent with `--wait` from a non-working state has up to five seconds to show `working` or `blocked`, else Herdr returns `agent_prompt_stalled`, so unrelated `idle` or `done` changes do not complete the wait; the wait does not track individual turns. [DOC S-ww43mymu]
- Agent targets are a unique live agent name or the pane id; `--machine <label-or-id>` before an `agent` command sends it through the JSON API over non-interactive SSH to one saved machine, with no fallback to the local server. [DOC S-ww43mymu]

### Reporting state from your own agent
- An agent not supported by Herdr makes three kinds of report through `"$HERDR_BIN_PATH"`: state (`idle`, `working` or `blocked`, on every change), the resume command, and a release when it exits; it reports only when `HERDR_ENV=1` and the other variables are set. [DOC S-trea7px4]
- `pane report-agent` takes `--source` (stable, unique, not starting with `herdr:`), `--agent` (the name users see), `--state`, an optional `--message` for a block and `--seq`; `--seq` must grow with every report of that source, also across restarts, and a report whose number is not higher than the last accepted is ignored, so a late report cannot overwrite newer state. [DOC S-trea7px4]
- The same report is the socket method `pane.report_agent` with `pane_id`, `source`, `agent`, `state` and `message`; its `state` is semantic and drives waits, notifications and rollups, while titles, display names, `state_labels` and tokens go through `pane.report_metadata` and never change the lifecycle state. [DOC S-h5xo2alh]
- Releasing the pane clears the agent's name, state and resume command at once, so a reporter releases only when the user quits, and sends only the latest state when several changes queue up. [DOC S-trea7px4]

### What this means for a monitor
- A monitor that reads Herdr gets, per agent, a status from a closed set of five and can subscribe to changes instead of polling; the pages read list `state_change_seq` as a filter and sort field but no time or last-activity field for an agent, so a silence measure is the reader's own clock over events or polls. [DER S-h5xo2alh, S-ww43mymu: the status set and the filter and sort fields read together; the missing field is absence in the pages read 2026-10-26]
- For a Claude Code pane Herdr's `blocked` is read from the screen while Claude Code's own `waitingFor` comes from the process (`claude/parallel-sessions.md`), so the two sources can disagree: a prompt shape the manifest does not match shows as `idle` in Herdr. [DER S-ffm4okjz, S-yxd37uaa: strict blocked detection and the screen-based Claude Code state]
- Whether a headless `claude -p` run in a pane is recognised as an agent, and what status it gets while it works without drawing a prompt, is not stated in the pages read. [UNK: not in the agents, integrations or socket pages; to be tried with a pane running `claude -p`]

## Reference
| Need | Herdr call |
|---|---|
| List agents and their status | `herdr agent list` or socket `agent.list` |
| Wait for a state | `herdr agent wait <target> --until blocked` or socket `agent.wait` |
| Be told of a change | socket `events.subscribe` with `pane.agent_status_changed` |
| Report state of your own agent | `"$HERDR_BIN_PATH" pane report-agent` or socket `pane.report_agent` |
| Find out why a state was chosen | `herdr agent explain <target> --json` |

Related: `claude/parallel-sessions.md` (Claude Code's own `claude agents --json` states), `claude/ci-and-headless.md` (session state events of a `claude -p` run), `agents/coordination-messages.md`.

## Examples
- SNIPPET: one request line of the socket protocol and its answer; context: Herdr v0.9.5, a newline-delimited JSON stream on the local socket; checked: syntax [DER S-h5xo2alh: the request and response shapes of the transport section]
```json
{"id": "req_1", "method": "ping", "params": {}}
```
- SNIPPET: subscription to a pane's blocked status; context: Herdr v0.9.5, the pane id `w1:p1` is a placeholder from the docs; checked: syntax [DER S-h5xo2alh: the subscription example of the event subscriptions section]
```json
{"id": "sub_1", "method": "events.subscribe", "params": {"subscriptions": [{"type": "pane.agent_status_changed", "pane_id": "w1:p1", "agent_status": "blocked"}]}}
```
