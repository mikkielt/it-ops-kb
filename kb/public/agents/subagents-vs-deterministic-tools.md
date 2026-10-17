---
topic: agents/subagents-vs-deterministic-tools
priority: P1
applies_to: "Claude Code / Agent Skills (2026-09 docs), MCP spec 2025-06-18, Microsoft Agent Framework 1.0 (GA 2026-04-03)"
retrieved_utc: 2026-10-17
sources: [S1920, S1921, S1922, S1923, S1924, S1925, S1926, S1927, S1928, S1930, S1931, S1932, S1934, S1935, S1936, S1937, S1938, S1939, S1940, S1941, S1942, S1943, S1944, S1945, S-teeldzof, S744, S745, S-qulnsg4e, S1824, S2157, S-qdxfqzln]
status: complete
---

# When to remove child agents and move logic into a deterministic MCP server

## Summary

Anthropic's own guidance is: prefer a workflow (predefined code paths) over an agent unless the outcome
space is genuinely open-ended, because agents are 4x the token cost of chat and multi-agent designs are
15x — with a documented 90.2% quality gain on its research eval, and token usage alone explaining 80% of
performance variance on BrowseComp. Its "code execution with MCP" pattern cut one task from 150,000 to
2,000 tokens (98.7%) by letting the agent load only the tool definitions it needs; the same pattern also
filters intermediate results in code before they reach the model, the isolation job a subagent used to do. MCP's `outputSchema`/`structuredContent`/annotations give a deterministic tool the
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
- A vendor guide (Augment Code, 2026-05-16) repeats those multipliers and argues that multi-agent cost grows faster than the agent count because context transfer, retries, verification and orchestration stack at every handoff, so per-agent budgets underestimate bills ("3 agents cost 10x" in its title). [COMMUNITY S1930]
- Published quality number: multi-agent (Opus lead + Sonnet subagents) beat single-agent Opus 4 by 90.2%
  on Anthropic's internal research eval. [DOC S1921]
- Published variance decomposition (BrowseComp eval): token usage alone explains ~80% of performance
  variance; tool-call count and model choice make up most of the remaining ~15% (~95% total from three
  factors). [DOC S1921]
- Anthropic's own named multi-agent failure modes: excessive subagent spawning on simple queries,
  duplicated work from vague task descriptions, agents preferring SEO content over authoritative sources,
  and needless slowness from non-parallel execution. [DOC S1921]
- What a delegation brief must hold, per Anthropic's Research system post: "Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries"; without detailed task descriptions agents duplicate work, leave gaps or fail to find what is needed. [DOC S1921]
- The post's example of a brief too short: an instruction such as "research the semiconductor shortage" led one subagent to the 2021 automotive chip crisis while two others duplicated work on 2025 supply chains, with no division of labour. [DOC S1921]
- The post embedded effort-scaling rules in the lead's prompt because agents misjudge effort: simple fact-finding one agent with 3-10 tool calls, direct comparisons 2-4 subagents with 10-15 calls each, complex research more than 10 subagents with divided responsibilities. [DOC S1921]
- The post advises subagents to write large outputs to external storage and pass lightweight references back to the coordinator, to avoid information loss and token overhead from copying output through the conversation (the "game of telephone"). [DOC S1921]
- Code execution with MCP: presenting MCP servers as code APIs on a filesystem, so the agent reads only the
  tool definitions it needs for the task, cut one Drive→Salesforce task from 150,000 to 2,000 tokens
  (98.7%). [DOC S1922]
- Independent (non-Anthropic) tests: AIMultiple measured 78.5% fewer input tokens (165K vs 771K, GPT-4.1);
  Bifrost's savings grew from 58% at 96 tools to 92.8% at 508 tools. [COMMUNITY S1931, S1932]
- The same secondary write-up reports Anthropic's Programmatic Tool Calling at 43,588→27,297 average
  tokens (37%) on complex research tasks. [COMMUNITY S1932]
- OpenAI's practical guide: maximize a single agent with tools first; split into multiple agents only on
  complex conditional logic or overlapping tool responsibilities; names the **manager** pattern (one
  central agent calls specialists as tools) and the **decentralized** pattern (peers hand off outright).
  [DOC S1924, S1941]
- Microsoft Azure Architecture Center: complexity spectrum "direct model call → single agent with tools →
  multi-agent orchestration," rule "use the lowest level of complexity that reliably meets your
  requirements"; lists sequential, concurrent, group-chat/maker-checker, handoff and magentic patterns. [DOC S1925]
- Microsoft Agent Framework (MIT, Python/.NET) combines agents, workflows with explicit multi-agent
  execution paths, middleware for intercepting agent actions, and OpenTelemetry observability.
  [DOC S1938, S1939]
- Agent Framework 1.0 reached GA on 2026-04-03 with stable Sequential, Group Chat and Magentic-One
  orchestration patterns and a middleware pipeline that injects logic (e.g. content safety) into the
  agent loop without touching prompts. [COMMUNITY S1940]
- Cognition, "Don't Build Multi-Agents" (2025-06-12): subagents fail because they act on incomplete shared
  context — "actions carry implicit decisions, and conflicting decisions carry bad results" — recommends
  single-threaded linear agents by default, with LLM-based history compression only past one context
  window. [COMMUNITY S1926]
- Cognition's later, undated follow-up softens this: it now reports multi-agent setups that work in
  production provided writes stay single-threaded — the same vendor revising an earlier absolute claim
  (see `conflicts.md`). [COMMUNITY S1927]

### QG13b — failure modes of parallel or multi-agent work that Anthropic names, and its mitigations
- The Research post says its early agents spawned 50 subagents for simple queries, scoured the web endlessly for nonexistent sources and distracted each other with excessive updates, and that prompt engineering was its primary lever against these behaviours. [DOC S1921]
- Watching agents step by step in simulations with the exact prompts and tools revealed more failure modes: agents continuing when they already had sufficient results, using overly verbose search queries and selecting incorrect tools. [DOC S1921]
- The post's mitigations by failure: a delegation brief with an objective, output format, tool guidance and task boundaries against duplicated work and gaps; embedded effort-scaling rules against over-investment in simple queries; explicit tool-selection heuristics and distinct tool descriptions against wrong-tool paths; and subagent output stored externally with a lightweight reference returned against information loss. [DOC S1921]
- On stuck or failed runs the post says agents are stateful and errors compound, so a run cannot simply restart from the beginning; it built systems that resume from where the agent was when the error occurred, tells the agent when a tool is failing so it can adapt, and combines that with deterministic safeguards "like retry logic and regular checkpoints". [DOC S1921]
- For debugging the post says agents are non-deterministic between runs even with identical prompts, and that full production tracing plus monitoring of agent decision patterns and interaction structures (without reading conversation contents) let it diagnose why agents failed; for deployment it used rainbow deployments, shifting traffic gradually so running agents are not broken by a new version. [DOC S1921]
- The post names the cost of its design: lead agents run subagents synchronously, so the lead cannot steer subagents, subagents cannot coordinate and one slow subagent can block the system; asynchronous execution would add parallelism but also problems of result coordination, state consistency and error propagation. [DOC S1921]
- The post says domains where all agents must share the same context or have many dependencies between them are not a good fit for multi-agent systems today, and that most coding tasks have fewer truly parallelizable parts than research. [DOC S1921]
- "Building effective agents" names the generic risk and its mitigations: the autonomy of agents means higher costs and potentially compounding errors, so it recommends extensive testing in sandboxed environments with guardrails, and says an agent loop commonly includes stopping conditions such as a maximum number of iterations. [DOC S1920]
- Claude Code gives the operator hard stops for the same failure modes: a workflow run stops at 1,000 agents, which the workflows page says prevents runaway loops; `--max-budget-usd` stops a `claude -p` run at an estimated spend and makes a further subagent spawn fail; a subagent's `maxTurns` returns its output marked partial. [DOC S-qulnsg4e, S1824, S2157]
- Claude Code's agent teams page names its own failure modes (teammates that stop after errors, a lead that finishes early or does the work itself, lagging task status, same-file overwrites, runaway token cost) with fixes in `claude/skills-and-subagents.md`, and how to stop each kind of parallel work is in `claude/parallel-sessions.md`. [DOC S-qdxfqzln]
- No Anthropic page found names deadlock or livelock between agents as a failure mode; the nearest are the Research post's blocked-on-one-subagent synchronous bottleneck and the workflow stall restart (`agent stalled on all 6 attempts`). The claude-code-docs server was searched on 2026-10-17 for "deadlock" and found it only in a changelog line about a skill-file watcher. [DER S1921, S-qulnsg4e: the sync bottleneck and the stall paragraph; absence checked in the docs search, not a vendor statement]

### QG14 — decision signals for replacing a child agent with a deterministic tool
- **Stable, repeated tool-call sequence**: Anthropic's tool-writing guidance treats a fixed multi-step
  sequence (e.g. `list_users`→`list_events`→`create_event`) as the signal to consolidate into one tool
  (`schedule_event`) instead of letting the agent re-derive it every run. [DOC S1935]
- **Token/latency cost**: the published multipliers (4x agent, 15x multi-agent vs. chat) are the ceiling
  cost of doing one step by subagent instead of by a single deterministic tool call. [DER from S1921:
  derivation — whole-task multipliers bound the per-step cost of choosing agent-driven execution over a
  fixed call]
- **Error compounding / runaway cost**: Anthropic reports its early agents spawning 50 subagents for
  simple queries, an observed failure mode of its own architecture. [DOC S1921]
- A secondary write-up says a subagent that recursively spawns more subagents, or a tool that returns
  oversized results, can multiply a query's cost by "another 10x or more" on top of the 15x baseline, and
  that the published architecture has no circuit breakers or per-run caps. [COMMUNITY S1934]
- **Auditability**: when an LLM decides "this looks fine," it "doesn't generate a record that holds up in
  a SOC 2 audit"; the vendor recommends deterministic rules enforced at the tool-call layer, each decision
  logged with the tool call, arguments and rule that fired. [COMMUNITY S1945]
- Composing deterministic flows in code and wrapping multi-step orchestration into single composite tools,
  rather than having the model sequence calls, removes sequential-dependency errors and yields a
  verifiable record. [COMMUNITY S1944]
- **Need for confirmation**: MCP puts human-in-the-loop at protocol level regardless of agent-vs-tool
  framing — there "SHOULD" always be a human in the loop able to deny tool invocations, and applications
  "SHOULD" present confirmation prompts for operations. [DOC S1928]
- A deterministic tool's fixed schema is easier to gate this way than a subagent's not-yet-known call
  sequence. [DER S1928: confirmation prompts attach to known, declared tools]
- **Eval pass rate**: Anthropic's method tracks task success alongside runtime, tool-call count, token
  consumption and error rate. [DOC S1935]
- It publishes no numeric pass-rate threshold for converting an agentic step to a deterministic tool, so
  the trigger is the operator's own baseline. [DER S1935: the method names metrics, not thresholds]
- **Measuring from OTel/transcripts**: Claude Code's `claude_code.tool_result` / `claude_code.tool_decision`
  events (documented in `claude/otel-monitoring.md`, part `arch`) carry `duration_ms`, `success`,
  `tool_input_size_bytes`/`tool_result_size_bytes`, and — with `OTEL_LOG_TOOL_DETAILS=1` — the MCP
  server/tool name and arguments: the concrete fields for per-call latency, error rate and payload size
  behind every signal above. [DOC S744, S745 — reused, see `_sources.csv`]

### QG15 — migration patterns
- **To an MCP tool**: consolidate the subagent's fixed call sequence into one tool with a combined
  `inputSchema`; `outputSchema` lets the server's `structuredContent` be schema-validated instead of
  free text the model must re-parse each run. [DOC S1928, S1935]
- **Tool annotations replace some subagent judgment**: `readOnlyHint` (does not modify its environment),
  `destructiveHint`, `idempotentHint` and `openWorldHint` describe tool behaviour to clients — but they are
  hints only, clients MUST treat them as untrusted unless they come from trusted servers, and should never
  base tool-use decisions on annotations from untrusted servers. [DOC S1928, S-teeldzof]
- A host can use such hints from a trusted server to auto-approve reads and force confirmation on
  destructive calls deterministically. [DER S-teeldzof: readOnlyHint/destructiveHint semantics applied to an
  approval policy]
- **To a skill with scripts**: Anthropic draws the line explicitly — "sorting a list via token generation
  is far more expensive than simply running a sorting algorithm"; many applications "require the
  deterministic reliability that only code can provide." A skill script's *output*, not its source, enters
  context (example given: ~20 tokens instead of ~2,000). [DOC S1936, S1937]
- **Progressive disclosure vs a subagent for isolation**: three tiers — always-loaded frontmatter, SKILL.md
  body loaded once relevant, referenced resource files loaded only as needed — make the context bundled
  into a skill "effectively unbounded", since the agent reads files only as needed. [DOC S1936]
- **To code execution over MCP**: exposing tools as code the agent explores and calls from written code
  lets it load tool definitions on demand (the 150,000→2,000 token, 98.7% figure) and filter or transform
  intermediate results in the execution environment before they reach the model — the same isolation job
  a subagent used to do. [DOC S1922]
- **Keeping behaviour equal — record/replay/compare**: no fetched vendor page names this workflow for an
  agent→tool migration specifically; third-party eval tooling documents the general technique: Promptfoo's
  coding-agent guide runs a fixed task set against a build and asserts on outcomes in CI; a community
  write-up of AgentInspect checks an agent's trajectory (the tool-call sequence) and recorded error spans
  alongside the final answer, showing two runs with the same answer but different execution paths — the
  applicable pattern for proving a new deterministic tool reproduces a removed subagent's behaviour.
  [COMMUNITY S1942, S1943]
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
| Multi-agent + runaway/oversized result | ~15x × "another 10x or more" (secondary estimate) | S1934 (COMMUNITY) |
| Code execution over MCP (one measured task) | 150,000 → 2,000 tokens (98.7% reduction) | S1922 |

For what a brief or a returned summary should hold, how parallel agents avoid duplicate research and what the coordination costs in tokens, see `agents/coordination-messages.md`; for typed results between agents over A2A, see `agents/a2a-protocol.md`.

## Examples

- Example: a device-watch subagent that always runs the same three ConfigMgr AdminService calls
  for `PL-LT-00123` (recheck → drift-explain → format) is a QG14 "stable tool-call sequence"
  candidate for consolidation into one MCP tool with a combined `outputSchema`, per S1928 and
  S1935 — stated as an illustration of the signal, not a design decision for any particular system.
