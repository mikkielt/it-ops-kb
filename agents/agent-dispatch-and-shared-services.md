---
topic: agents/agent-dispatch-and-shared-services
priority: P1
applies_to: "Copilot Studio connected agents (2026-06-23 docs), Microsoft Agent Framework (BUILD 2026), Claude Code subagents (2026-09 docs), MCP spec 2026-07-28"
retrieved_utc: 2026-09-26
sources: [S2080, S2081, S2082, S2083, S2084, S2109, S2110, S1920, S1928, S-vqothyeg]
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
- Microsoft Agent Framework's BUILD 2026 post adds an Agent Harness (built-in context compaction, file
  memory, background child agents for fan-out), Foundry Hosted Agents (the agent's own code as a container
  on Foundry-managed infrastructure, scale to zero, a VM-isolated sandbox per session) and CodeAct (the
  model writes one short Python program that calls the tools and runs once in a Hyperlight micro-VM); on
  the post's sample workload CodeAct cut time from 27.81 s to 13.23 s and tokens from 6,890 to 2,489
  against traditional tool calling. The post gives no hosted-vs-in-process comparison. [DOC S2082]
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
- MCP's 2026-07-28 specification revision makes a **remote** MCP server a plain HTTP request/response
  service (stateless core, no session/handshake, optional `server/discover` for capabilities, any request
  can land on any instance behind a round-robin load balancer; a partner quote in the post calls it "a
  first-class HTTP workload") —
  the concrete mechanism by which "dispatch to another service" and "dispatch to another agent" converge
  on the same protocol shape once the target is out-of-process. [DOC S2084]
- The A2A project's own documentation calls A2A and MCP complementary: MCP connects an agent to tools
  and resources, A2A connects agents to each other across team or organization boundaries. [DOC S-vqothyeg]
- The current MCP roadmap post (written after the 2026-07-28 spec) does not mention A2A; its five priority
  areas are agentic messaging primitives, HTTP transport unification and hardening, agent identity and
  enterprise security, improved primitives, and SDK developer experience. [DOC S2110] Full A2A treatment
  is topic 9's scope, not repeated here.
- Copilot Studio's agent-sharing feature (grant individual users, security groups or the whole
  organization permission to chat with an agent, or invite individual users to co-author it) is a related
  but distinct decision from connecting agents at runtime: sharing controls who can *use or edit* an
  agent; connecting controls whether one agent *calls* another during a conversation. [DOC S2109, S2080]
- Topic 4's own criteria (stable tool-call sequence, eval pass rate, token/latency cost, error
  compounding, auditability, need for confirmation) are the child-agent-vs-deterministic-tool axis; they
  are not repeated here — see `agents/subagents-vs-deterministic-tools.md`. [DER S1920, S1928: S1920
  gives the latency/cost tradeoff, compounding errors and workflow predictability, S1928 human
  confirmation and audit logging of tool use; eval pass rate is topic 4's own criterion]

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
