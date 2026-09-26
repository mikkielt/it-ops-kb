---
topic: agents/agent-dispatch-and-shared-services
priority: P1
applies_to: "Copilot Studio connected agents (2026-06-23 docs), Microsoft Agent Framework (BUILD 2026), Claude Code subagents (2026-09 docs), MCP spec 2026-07-28"
retrieved_utc: 2026-09-26
sources: [S2080, S2081, S2082, S2083, S2084, S2109, S2110, S1920, S1928]
status: partial
---

# What to dispatch to another agent or service vs keep in-process

## Summary
Vendors converge on the same criteria for splitting work across agents: a stable domain boundary
(specialization), reuse across more than one caller, independent ownership, and isolation of verbose
or sensitive intermediate output. None of the fetched vendor pages frame this as a data-boundary or
blast-radius decision the way `agents/subagents-vs-deterministic-tools.md` (topic 4) already covers
for the child-agent-vs-tool question; this file only adds the agent-to-agent / remote-service dispatch
angle topic 4 does not. The A2A protocol itself (governance, transport, auth) is out of scope here —
topic 9 (`agents-a2a-cache`) covers it; A2A is named below only as one transport option among several.

## Facts

### QG29 — dispatch criteria: agent-to-agent vs remote service vs in-process
- Microsoft Copilot Studio's **connected agents**: a "primary agent" can delegate to another agent when
  a user's request falls inside that agent's declared domain; the orchestration runtime does
  intent-matching per turn, and the connected agent "runs in its own orchestration context, with its own
  instructions, knowledge, and tools." [DOC S2080]
- Copilot Studio's stated reasons to connect rather than fold logic into one agent: **specialization**
  (own domain, easier to build/maintain), **reusability** (one specialist agent connected to several
  primary agents), **separation of concerns** (different teams own different agents), and
  **scalability** (add capability by connecting an agent rather than growing one agent's instructions).
  [DOC S2080]
- As of the 2026-06-23 Copilot Studio docs, the new agent experience can only connect other agents that
  are themselves built in Copilot Studio — not an arbitrary external service. [DOC S2080]
- Connected-agent invocation is usage-metered: "usage-based billing applies to using, building, testing,
  and evaluating agents," consuming Copilot Credits — a per-call cost that a purely in-process function
  call does not carry. [DOC S2080]
- Microsoft Agent Framework (announced at BUILD 2026) adds an "Agent Harness," hosted agents and a
  CodeAct pattern; the framework post frames these as ways to run agent logic in a separate managed
  runtime rather than inline in the caller's process, but the fetched summary gives no numeric
  latency/cost comparison against an in-process call. [DOC S2082]
- Anthropic's Claude Code subagent docs give four "use a subagent" signals: the task produces verbose
  output not needed in the main context; you want to enforce a narrower tool/permission set for that
  task; the work is self-contained and returns a summary; a side task "would flood your main
  conversation with search results, logs, or file contents you won't reference again." [DOC S2083]
- The same docs give the converse — keep it in-process/main-context — when: the task needs frequent
  back-and-forth or multiple feedback rounds; several phases share significant context (e.g.
  plan→implement→test); the change is small and targeted; or latency matters, because "a subagent that isn't a
  fork starts fresh and may need time to gather context." [DOC S2083]
- A **fork** (Claude Code) is the one dispatch form that keeps the full parent context/history instead of
  starting isolated — the opposite tradeoff from a normal subagent or a connected agent, which both start
  with a declared, narrower context. [DOC S2083]
- Tool-permission restriction is the concrete mechanism Claude Code gives for bounding a dispatched
  subagent's blast radius: per-subagent `tools:`/`disallowedTools:`/`permissionMode:` frontmatter, and a
  tool filter that removes a short list (including `AskUserQuestion`, `EnterPlanMode` and `Workflow`) from
  every non-fork subagent, and a smaller built-in tool set for background subagents (the default), which
  still keep every MCP tool; forks receive the main conversation's exact tool pool. [DOC S2083]
- MCP's 2026-07-28 specification revision makes a **remote** MCP server "no different from any other
  HTTP workload" (stateless core, no session/handshake, `server/discover` for capability discovery) —
  the concrete mechanism by which "dispatch to another service" and "dispatch to another agent" converge
  on the same protocol shape once the target is out-of-process. [DOC S2084]
- The MCP roadmap post situates A2A as a complementary, not competing, protocol for peer agent-to-agent
  handoff, while MCP stays the model-to-tool/resource protocol; the roadmap does not commit Anthropic
  products to speaking A2A. [DOC S2110] Full A2A treatment is topic 9's scope, not repeated here.
- Copilot Studio's agent-sharing feature (share an agent with other users/environments) is a related but
  distinct decision from connecting agents at runtime: sharing controls who can *use or edit* an agent;
  connecting controls whether one agent *calls* another during a conversation. [DOC S2109]
- Topic 4's own criteria (stable tool-call sequence, eval pass rate, token/latency cost, error
  compounding, auditability, need for confirmation) are the child-agent-vs-deterministic-tool axis; they
  are not repeated here — see `agents/subagents-vs-deterministic-tools.md`. [DOC S1920, S1928 — cited
  by reference, not re-derived]

## Reference
| Dispatch target | Declared boundary | Reuse across callers | Metered per call | Source |
|---|---|---|---|---|
| Copilot Studio connected agent | domain (intent-matched) | yes, one agent to many primaries | yes (Copilot Credits) | S2080 |
| Claude Code subagent (non-fork) | task/tool-permission scope | no (spawned per task) | model tokens only | S2083 |
| Claude Code fork | none (inherits full context) | no | model tokens only | S2083 |
| Remote MCP server (2026-07-28 spec) | protocol boundary (stateless HTTP) | yes, many clients | depends on hosting | S2084 |

## Examples
A Claude Code session on device `PL-LT-00123` at `corp.example.com` that needs to summarize a
long ConfigMgr baseline log before deciding a next step matches Claude Code's "verbose output isolation"
signal (a subagent reads the log, returns a short verdict) [DOC S2083]; it does not match Copilot
Studio's connected-agent case, which assumes a separate, independently owned agent with its own
domain. Not run against real data.
