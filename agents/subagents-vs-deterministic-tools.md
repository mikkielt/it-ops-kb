---
topic: agents-mcp/subagents-vs-deterministic-tools
priority: P1
applies_to: "Claude Code / Agent Skills (2026-09 docs), MCP spec 2025-06-18, Microsoft Agent Framework 1.0 (GA 2026-04-03)"
retrieved_utc: 2026-09-25
sources: [S1920, S1921, S1922, S1923, S1924, S1925, S1926, S1927, S1928, S1929, S1930, S1931, S1932, S1933, S1934, S1935, S1936, S1937, S1938, S1939, S1940, S1941, S1942, S1943, S1944, S1945]
status: complete
---

# When to remove child agents and move logic into a deterministic MCP server

## Summary

Anthropic's own guidance is: prefer a workflow (predefined code paths) over an agent unless the outcome
space is genuinely open-ended, because agents are 4x the token cost of chat and multi-agent designs are
15x — with a documented 90.2% quality gain and a measured 80% of that gain explained by token volume
alone. Its "code execution with MCP" pattern cut one task from 150,000 to 2,000 tokens (98.7%) by keeping
tool outputs out of the model's context entirely, which is the same intermediate-result-isolation job a
subagent used to do. MCP's `outputSchema`/`structuredContent`/annotations give a deterministic tool the
typed, auditable interface a subagent's free-text output cannot. A task-management skill built on a
stdlib script that resolves eligibility from fixed headers, never guessing on an unparseable one, is a
worked example of this kind of deterministic tool; the parts of such a skill that stay model-driven do so
because no observed failure yet justifies scripting them.

## Facts

### QG13 — workflows vs agents, single vs multi-agent, official + community positions
- Anthropic: workflows = "systems where LLMs and tools are orchestrated through predefined code paths";
  agents = "systems where LLMs dynamically direct their own processes and tool usage." [DOC S1920]
- Anthropic's default: find the simplest solution first; add agentic complexity only when it demonstrably
  helps; "agentic systems often trade latency and cost for better task performance." [DOC S1920]
- Anthropic's production multi-agent Research system: lead agent (Opus) spawns 3-5 parallel subagents
  (Sonnet), each with its own context window and 3+ parallel tool calls, plus a separate synthesis/citation
  pass. [DOC S1921]
- Published token multipliers vs a single chat turn: agents ≈4x, multi-agent systems ≈15x. [DOC S1921]
- Published quality number: multi-agent (Opus lead + Sonnet subagents) beat single-agent Opus 4 by 90.2%
  on Anthropic's internal research eval. [DOC S1921]
- Published variance decomposition (BrowseComp eval): token usage alone explains ~80% of performance
  variance; tool-call count and model choice make up most of the remaining ~15% (~95% total from three
  factors). [DOC S1921]
- Anthropic's own named multi-agent failure modes: excessive subagent spawning on simple queries,
  duplicated work from vague task descriptions, agents preferring SEO content over authoritative sources,
  and needless slowness from non-parallel execution. [DOC S1921]
- Code execution with MCP: presenting MCP tools as on-disk/importable code and letting the agent write code
  to call and filter results cut one Drive→Salesforce task from 150,000 to 2,000 tokens (98.7%). [DOC S1922]
- Independent (non-Anthropic) replications: 78.5% input-token cut (165K→771K reduction ratio, GPT-4.1);
  43,588→27,297 tokens (37%) on a complex research task; 58% savings at 96 tools scaling to 92.8% at 508
  tools in a separate report. [COMMUNITY S1931, S1932, S1934]
- OpenAI's practical guide: maximize a single agent with tools first; split into multiple agents only on
  complex conditional logic or overlapping tool responsibilities; names the **manager** pattern (one
  central agent calls specialists as tools) and the **decentralized** pattern (peers hand off outright).
  [DOC S1924, S1941]
- Microsoft Azure Architecture Center: complexity spectrum "direct model call → single agent with tools →
  multi-agent orchestration," rule "use the lowest level of complexity that reliably meets your
  requirements"; lists sequential, concurrent, group-chat/maker-checker, handoff and magentic patterns, and
  ranks orchestrator-worker (matching Anthropic's own architecture) first for production. [DOC S1925]
- Microsoft Agent Framework (GA 2026-04-03, MIT, Python/.NET) ships stable Sequential, Group Chat and
  Magentic-One orchestration with OpenTelemetry observability and middleware for content-safety/logging
  injection without touching prompts. [DOC S1938, S1939; COMMUNITY S1940]
- Cognition, "Don't Build Multi-Agents" (2025-06-12): subagents fail because they act on incomplete shared
  context — "actions carry implicit decisions, and conflicting decisions carry bad results" — recommends
  single-threaded linear agents by default, with LLM-based history compression only past one context
  window. [COMMUNITY S1926]
- Cognition's later, undated follow-up softens this: it now reports multi-agent setups that work in
  production provided writes stay single-threaded — the same vendor revising an earlier absolute claim
  (see `conflicts.md`). [COMMUNITY S1927]

### QG14 — decision signals for replacing a child agent with a deterministic tool
- **Stable, repeated tool-call sequence**: Anthropic's tool-writing guidance treats a fixed multi-step
  sequence (e.g. `list_users`→`list_events`→`create_event`) as the signal to consolidate into one tool
  (`schedule_event`) instead of letting the agent re-derive it every run. [DOC S1935]
- **Token/latency cost**: the published multipliers (4x agent, 15x multi-agent vs. chat) are the ceiling
  cost of doing one step by subagent instead of by a single deterministic tool call. [DER from S1921:
  derivation — whole-task multipliers bound the per-step cost of choosing agent-driven execution over a
  fixed call]
- **Error compounding / runaway cost**: Anthropic names a subagent recursively spawning more subagents as
  an observed failure mode of its own architecture and states the published design has no circuit breaker
  or per-run cap; a secondary source estimates such a runaway or an oversized tool result can multiply cost
  by "another 10x or more" on top of the 15x baseline. [DOC S1921 for the failure mode; COMMUNITY S1930 for
  the 10x figure]
- **Auditability**: "an LLM-based filter deciding something looks fine... doesn't generate a record that
  holds up in a SOC 2 audit"; recommendation is to compose deterministic flows in code and wrap multi-step
  orchestration into single composite tools rather than have the model sequence calls, removing
  sequential-dependency errors and producing a verifiable record. [COMMUNITY S1945, S1944]
- **Need for confirmation**: MCP puts human-in-the-loop at protocol level regardless of agent-vs-tool
  framing — servers "SHOULD" always keep a human able to deny invocations; clients "SHOULD" prompt for
  confirmation on sensitive operations. A deterministic tool's fixed schema is easier to gate this way than
  a subagent's not-yet-known call sequence. [DOC S1928]
- **Eval pass rate**: Anthropic's method tracks task success alongside runtime, tool-call count, token
  consumption and error rate, but publishes no numeric pass-rate threshold that should trigger converting
  an agentic step to a deterministic tool — left to the operator's own baseline. [DOC S1935 for method;
  UNK for a numeric trigger — see gaps.md]
- **Measuring from OTel/transcripts**: Claude Code's `claude_code.tool_result` / `claude_code.tool_decision`
  events (documented in `kb/claude/otel-monitoring.md`, part `arch`) carry `duration_ms`, `success`,
  `tool_input_size_bytes`/`tool_result_size_bytes`, and — with `OTEL_LOG_TOOL_DETAILS=1` — the MCP
  server/tool name and arguments: the concrete fields for per-call latency, error rate and payload size
  behind every signal above. [DOC S744, S745 — reused, see `kb/_parts/arch/sources.csv`]

### QG15 — migration patterns
- **To an MCP tool**: consolidate the subagent's fixed call sequence into one tool with a combined
  `inputSchema`; `outputSchema` lets the server's `structuredContent` be schema-validated instead of
  free text the model must re-parse each run. [DOC S1928]
- **Tool annotations replace some subagent judgment**: `readOnlyHint`/`destructiveHint`/`idempotentHint`/
  `openWorldHint` let a host auto-approve safe reads and force confirmation on destructive calls
  deterministically — though the spec requires annotations be treated as untrusted unless the server
  itself is trusted. [DOC S1928]
- **To a skill with scripts**: Anthropic draws the line explicitly — "sorting a list via token generation
  is far more expensive than simply running a sorting algorithm"; many applications "require the
  deterministic reliability that only code can provide." A skill script's *output*, not its source, enters
  context (example given: ~20 tokens instead of ~2,000). [DOC S1936, S1937]
- **Progressive disclosure vs a subagent for isolation**: three tiers — always-loaded frontmatter, SKILL.md
  body loaded once relevant, referenced resource files loaded only as needed — give "effectively unbounded"
  skill complexity without a subagent's fresh-context startup cost or lost conversation history. [DOC S1936]
- **To code execution over MCP**: exposing tools as files/modules the agent explores and calls from written
  code removes the round-trip of every intermediate result through the model — the same isolation job a
  subagent used to do — behind the 150,000→2,000 token (98.7%) reduction figure. [DOC S1922]
- **Keeping behaviour equal — record/replay/compare**: no fetched vendor page names this workflow for an
  agent→tool migration specifically; third-party eval tooling documents the general technique: Promptfoo's
  coding-agent guide runs a fixed task set against a build and asserts on outcomes in CI; a community tool
  (AgentInspect) diffs "the full agent trajectory — tool calls, parameters, sequence, output, cost — against
  a golden baseline," the applicable pattern for proving a new deterministic tool reproduces a removed
  subagent's behaviour. [COMMUNITY S1942, S1943]
- **Claude Code's own decision rule**: use a subagent "when a side task would flood your main conversation
  with search results, logs, or file contents you won't reference again"; "consider Skills instead when you
  want reusable prompts or workflows that run in the main conversation context" — the vendor's rule is
  context-volume isolation, not task complexity. A subagent producing no large disposable output has no
  isolation benefit to trade against its token/latency cost. [DOC S1923]

### QG16 — a worked example: a task-eligibility picker and a landing-verification script
- A task-eligibility picker can be a fully deterministic tool: a stdlib-only script run once, before any
  skill prose loads, reading only a tasks index, task-file headers and a gates/open-issues file, returning
  a fixed verdict set (`eligible`, `blocked`, `gated`, `not-before`, `unparseable`, `done`). [DER — general
  pattern for a task-picking skill]
- A skill built this way can enforce "never overrule the picker from prose" — the general rule that unknown
  is never eligible, applied to task selection: an unparseable header is `unparseable`, never guessed at.
  [DER — general implication]
- A companion landing-verification script can likewise be deterministic and explicitly replace model
  judgment by design, on the principle that "a transcript claiming success is not evidence." It can shell
  to `git` to check a README tick, a landed row with a resolvable merge-commit sha, that sha's ancestry on
  the main branch, a required commit trailer, a clean tree and open planning debt; every check returns
  True/False/None, and unknown counts as failing (`0 if all(ok ...) else 1`) — a code-level instance of
  "unknown is never treated as success." [DER — general pattern]
- Machine-read task headers to an exact grammar (a `Depends on:` / `Gates:` / optional `Note:` shape) exist
  so a regex script, not a model, resolves eligibility; "a header the picker cannot parse is unknown, never
  eligible" is the general rule this enables. [DER — general implication]
- What can stay model-driven in the same kind of skill: folding open debt and batching gate questions for a
  human, naming the failure a new mechanism would pay for, and branch/commit/checks execution plus secret/
  hostname scanning in diffs — all prose-guided, no script backing, until an observed failure justifies
  scripting them. [DER — general pattern]

## Reference

| Signal (QG14) | How to measure from OTel/transcripts | Source |
|---|---|---|
| Stable tool-call sequence | Diff tool-call sequences across N runs of the same task (AgentInspect-style trajectory diff) | S1943 |
| Token/latency cost | `claude_code.tool_result.duration_ms`, `tool_input_size_bytes`/`tool_result_size_bytes` | S744 |
| Error compounding | `claude_code.tool_decision` error/reject counts per subagent chain depth | S744, S1921 |
| Auditability | Whether the call has a fixed, schema-validated `structuredContent`/`outputSchema` vs. free text | S1928 |
| Confirmation need | MCP client behavior: prompts before sensitive/destructive-annotated calls | S1928 |
| Eval pass rate | Task success rate, tool-call count, token count, error rate on a fixed eval set | S1935 |

| Product | Token multiplier vs. chat | Source |
|---|---|---|
| Single agent w/ tools | ~4x | S1921 |
| Multi-agent (orchestrator + subagents) | ~15x | S1921 |
| Multi-agent + runaway/oversized result | ~15x × "another 10x or more" (uncapped in published design) | S1921 (failure mode), S1930 (multiplier, COMMUNITY) |
| Code execution over MCP (one measured task) | 150,000 → 2,000 tokens (98.7% reduction) | S1922 |

## Examples

- Example: a device-watch subagent that always runs the same three ConfigMgr AdminService calls
  for `PL-LT-00123` (recheck → drift-explain → format) is a QG14 "stable tool-call sequence"
  candidate for consolidation into one MCP tool with a combined `outputSchema`, per S1928 and
  S1935 — stated as an illustration of the signal, not a design decision for any particular system.
