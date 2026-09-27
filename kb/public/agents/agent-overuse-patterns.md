---
topic: agents/agent-overuse-patterns
priority: P1
applies_to: "Anthropic/OpenAI/Google/Microsoft agent guidance (2025-2026 docs), Thoughtworks Technology Radar Vol 34 (2026-04), jq 1.8, Renovate (docs 44.115.10), conventional-commits v1.0.0, semantic-release, LSP 3.18, DSC 3.3.0, Presidio (pattern_recognizer.py at commit e9895a51)"
retrieved_utc: 2026-09-27
sources: [S2160, S2162, S2163, S2164, S2165, S2166, S2167, S2168, S2169, S2170, S2171, S2172, S2173, S2174, S150, S154, S825, S-2z2zfj3l, S-sxtmngif, S-t5dhva6p, S900, S1920, S1924, S1925, S1935, S1936, S744, S745, S-3zepbhux]
status: complete
---

# Work routed to agents although plain tools would do

## Summary

Anthropic, OpenAI, Google and Microsoft all publish the same core rule, in their own words: find the
simplest solution first, and only reach for an agent when the task needs open-ended judgement, an
unstable ruleset, or unstructured input — never for tasks that are deterministic, stable and already
solved by a grammar, schema or algorithm. None of the four vendors publishes a single universal
cost/latency/error number; the concrete figures available (token multipliers, per-call latency figures,
a $/day example) come from Anthropic's own agent architecture post and from independent (COMMUNITY)
cost-modelling writeups, not from a cross-vendor benchmark. Topic 4's catalogue
(`agents/subagents-vs-deterministic-tools.md`) already covers *child-agent-vs-tool* signals; this
file's `agent-overuse-patterns.csv` is the wider list of task shapes a team hands to an LLM whole,
alongside the deterministic tool that already exists for them.

## Facts

### QG37 — vendor and practitioner guidance on when not to use an LLM or agent
- Anthropic: "we recommend finding the simplest solution possible, and only increasing complexity when
  needed... this might mean not building agentic systems at all,"
  and "agentic systems often trade latency and cost for better task performance... [and] higher costs,
  and the potential for compounding errors." [DOC S1920 — reused from topic 4]
- OpenAI's practical guide names three qualifying signals for building an agent — complex judgement-based
  decisions, rulesets that have grown unmaintainable, and heavy reliance on unstructured data — and states
  that if none apply, a deterministic solution may suffice; it explicitly excludes single-turn LLM calls,
  simple chatbots and sentiment classifiers from being "agents" at all. [DOC S1924 — reused from topic 4]
- Microsoft's Azure Architecture Center says to use the lowest level of complexity that reliably meets the
  requirements: a direct model call (no agent logic, no tools) covers single-step classification,
  summarization and translation, and "if prompt engineering can solve the problem, you don't need an
  agent"; it also lists deterministic, rule-based task routing as a case against an orchestrating agent.
  [DOC S1925]
- A Microsoft Foundry Blog post by a Microsoft practitioner gives the first tier decision as: does the
  problem need natural language understanding or dynamic generation? If not, it is a deterministic system
  and you stop there. [COMMUNITY S2162]
- A second Microsoft Foundry Blog post ("Deterministic Spine, Agentic Leaves") keeps workflow control in a
  deterministic, versioned workflow definition you can diff, review, test and roll back, with agents only
  as bounded workers inside controlled steps. [COMMUNITY S2163]
- Google's Cloud Architecture Center (read directly 2026-09-27, last updated 2026-04-21) says agents can be
  used for deterministic problems with predefined steps but other approaches can be more efficient and
  cost-effective, and that tasks like summarizing a document, translating text or classifying customer
  feedback do not need an agentic workflow. [DOC S2160] The further wording about stable logic and speed or
  reliability over flexibility is not on that page; it was attributed to the "Agents Companion" whitepaper
  (S2161), whose Kaggle page renders no text without JavaScript and was not read.
- Thoughtworks Technology Radar Volume 34 (April 2026) places "Agent Skills" in **Trial** ("worth
  pursuing") as a way to modularize context. Its "permission-hungry agents" theme says zero trust, least
  privilege, model improvements and defense in depth "are now table stakes" and expects safe agent systems to
  be "pipelines of more constrained agents" rather than monolithic agents; sandboxed execution for coding
  agents is a separate Trial blip, and "ignoring durability in agent workflows" is a Caution blip (systems
  that work in development but fail in production) — an implicit argument for keeping agent scope narrow
  rather than routing whole workflows through one. [DOC S2164, S2165]
- Radar Vol 34's rings are Adopt, Trial, Assess and Caution (no Hold). Its Caution blips on agents are
  "Agent instruction bloat" (as instructions grow, important rules are more likely to be ignored), "Coding
  agent swarms", "Ignoring durability in agent workflows" and "MCP by default" ("We caution against using MCP
  by default"). [DOC S2164]
- A Microsoft Open Source Blog post introducing Conductor (2026-05-14) argues that for workflows with a
  known structure, dynamic LLM-driven orchestration adds cost, latency and unpredictability, and keeps orchestration deterministic so that layer
  uses no tokens; it publishes no benchmark numbers. [COMMUNITY S-3zepbhux]
- Independent cost figures (none vendor-published as a general benchmark): a pipeline run 50,000 times a
  day at 3,000 tokens per run costs roughly $1.50/day at current frontier prices, and $15/day at 30,000
  tokens per run; a later passage of the same post calls the 30,000-token case "roughly 15x more" than the
  3,000-token one. [COMMUNITY S2174]
- Independent latency figures: deterministic steps can run in under 10 ms, while model-driven pipelines add
  at least 300-600 ms per LLM call and ReAct-style agents commonly issue 8-15 calls per task
  [COMMUNITY S2174]; a single LLM call might take 800 ms against 10-30 seconds for an orchestrator-worker
  flow with a reflection loop. [COMMUNITY S2173]
- Independent framing: agentic systems introduce "probabilistic uncertainty into previously deterministic
  software stacks," an "Unreliability Tax" (the extra compute, latency and engineering spent mitigating
  failure); a demo that works 80% of the time impresses, a production system failing 20% of the time is
  useless. [COMMUNITY S2173]
- The same decision-matrix post notes the failure modes mirror each other: deterministic pipelines break
  silently on out-of-distribution input, model-driven ones break noisily and expensively when the model
  misplans. [COMMUNITY S2174]
- "Stop Letting Agents Run the Workflow" (readable 2026-09-27) opens with an illustrative, unnamed
  five-agent access-request failure (a 30-day admin grant instead of 8 hours), not a documented incident;
  no fetched vendor page gives a named post-mortem of an agent deployed where a deterministic tool would
  have sufficed. [COMMUNITY S2163]

### QG38 — catalogue of over-routed tasks and their deterministic replacements
- See `agents/agent-overuse-patterns.csv` (26 rows, columns `task_shape,routed_to_agent,
  deterministic_tool,signal_agent_not_needed,sources`), covering: JSON/CSV/log parsing (`jq`), regex/
  pattern entity extraction (Presidio `PatternRecognizer`), schema-keyed masking, date/timezone
  arithmetic, JSON Schema validation, lint/format, code navigation (LSP), dependency updates (Renovate/
  Dependabot), release notes and version bumps (conventional-commits/semantic-release), CI triage by
  signature, ticket routing by keyword, fixed-string translation via catalogue, DSC/ConfigMgr drift
  detection (`dsc config test`, baseline compliance), structured-store querying (SQL/WQL/CMPivot),
  recurring reports (Power BI), scheduling/retry, simple chatbot/FAQ, classification, sort/filter/
  aggregate, fixed multi-step tool sequences, task-eligibility and landing-verification scripts, high-volume
  low-latency lookups, exact-reproduction audit trails, and tier/policy gating. [DER — table compiled from
  DOC facts per row, sources cited per row in the CSV]
- jq (current: 1.8) is "a lightweight and flexible command-line JSON processor" whose programs are
  composable filters over JSON — the deterministic tool for exactly the extraction/reshaping tasks teams
  otherwise hand an LLM prompt. [DOC S2166]
- Renovate (docs banner version 44.115.10 on 2026-09-26) automates "pull requests to update your
  dependencies and lock files" from declared configuration/presets, with no LLM/AI step named anywhere in its own docs. [DOC
  S2167]
- GitHub Dependabot version updates are "automated pull requests that keep your dependencies updated,"
  driven by a `dependabot.yml` schedule and semantic-versioning rules, with a default 3-day cooldown for
  non-security version updates. [DOC S2168]
- Conventional Commits v1.0.0 fixes `fix→PATCH`, `feat→MINOR`, `BREAKING CHANGE→MAJOR` as a closed rule
  table, letting a version bump be computed instead of judged. [DOC S2169]
- semantic-release (canonical docs now at semantic-release.org; the gitbook mirror fetched here states its
  own discontinuation) runs a fixed eight-step pipeline (Verify Conditions → Get Last Release → Analyze
  Commits → Verify Release → Generate Notes → Create Git Tag → Prepare → Publish → Notify) purely from
  commit-message classification, with no model in the loop. [DOC S2170]
- LSP (spec version 3.18) "standardizes the protocol for how [language] servers and development tools
  communicate," giving deterministic go-to-definition/find-references/completion without re-implementing
  per editor-language pair and without a model reasoning over source text. [DOC S2171]
- Anthropic's Agent Skills post says some operations suit traditional code execution better than a model: sorting a list via token generation is far more expensive than running a sorting algorithm, and many applications need the deterministic reliability only code provides, so a skill can bundle a script for Claude to run. [DOC S1936]
- The AgentAssay preprint (arXiv 2603.02601, 2026-03-03) says no principled method existed for checking that an agent has not regressed after changes to its prompts, tools, models or orchestration, and proposes statistical regression testing of non-deterministic agent workflows with three-valued verdicts (PASS, FAIL, INCONCLUSIVE) and CI/CD gates as statistical decision procedures. [COMMUNITY S2172]
- `dsc config test` and ConfigMgr baseline compliance evaluation are deterministic drift-detection
  tools for Windows endpoint management: DSC's `test` operation has a published output schema
  (`schemas/v3/bundled/outputs/{config,resource}/test.json`) [DOC S150, S154 — reused from `dsc/`,
  part `dsc`], and ConfigMgr's CMPivot query surface (entities, `CcmLog()`, `WinEvent()`) is the
  documented structured-query path for live device state. [DOC S-2z2zfj3l, S-sxtmngif, S-t5dhva6p — reused from
  `mecm/cmpivot.md`, part `mecm`]
- Presidio's `PatternRecognizer` (source at pinned commit `e9895a51`) matches entities by regex patterns and an
  optional deny list (turned into one more regex), with optional context words — a deterministic alternative to a free-text NER call for any entity with a fixed
  lexical shape (the same class of fact used for structured-field tokenization design). [CODE S825:
  presidio-analyzer/presidio_analyzer/pattern_recognizer.py#PatternRecognizer]
- Power BI scheduled refresh imports data into a semantic model on a configured schedule (up to 8 daily
  slots on shared capacity, 48 on Premium, PPU or Fabric capacity), so a recurring report over a fixed
  model is a scheduled job rather than an agent re-summarizing the same numbers on each request.
  [DER S900: the schedule and slot limits are documented; the agent comparison is our inference]

### QG39 — signals and measures that a task is over-routed
- **Output fully determined by input**: OpenAI's own exclusion list (single-turn LLM call, sentiment
  classifier) matches this signal directly — no workflow control is being exercised, so there is nothing
  "agentic" to justify. [DOC S1924]
- **Same answer recurs across runs**: Anthropic recommends tools that consolidate frequently chained,
  multi-step tasks into one call (see topic 4, QG14); a fixed call sequence that never varies across runs
  is that signal applied one level up, to whether the whole task needed an agent at all. [DER S1935: the
  consolidation advice is the post's; applying it to the whole task is our inference]
- **A spec or grammar already exists**: JSON, CSV, DSC's published `test` output schema, conventional-commit
  messages and Presidio's regex patterns are all defined formats; wherever one exists the tool
  reading it does not need to "understand" language, only parse a format. [DER from S2166, S2169, S150, S825]
- **Errors are unacceptable / audit needs exact reproduction**: the same input to a deterministic tool
  always produces the same output, while an agentic system carries an "Unreliability Tax" (a demo that
  works 80% of the time, a production system failing 20%) — unacceptable where the record itself is the
  audit trail. [DER S2173: the failure framing is the post's; the audit implication is ours]
- **Volume is high / latency matters**: one post's example goes from $1.50/day to $15/day when tokens per
  run rise from 3,000 to 30,000 at 50,000 runs a day, and puts each LLM call at 300-600 ms against under
  10 ms for a deterministic step, which makes an LLM call a poor fit once a sub-second or high-throughput
  budget is required. [COMMUNITY S2174]
- **How to find candidates in transcripts/OTel data**: no vendor page fetched in this topic names a
  specific query; topic 4 already documents the concrete Claude Code OTel fields
  (`claude_code.tool_result.duration_ms`, `tool_input_size_bytes`/`tool_result_size_bytes`,
  `claude_code.tool_decision`) that would surface a stable, repeated, low-variance tool-call sequence — the
  same fields, read as "this sequence never changes across N runs," are the concrete signal for "this
  whole task could have skipped the agent." [DER from `agents/subagents-vs-deterministic-tools.md`
  (reused S744/S745 there), not re-fetched here]

## Reference

| Vendor | Core "don't build an agent" rule | Source |
|---|---|---|
| Anthropic | simplest solution first; agents trade latency/cost for task performance | S1920 |
| OpenAI | agent only for complex judgement, unmaintainable rulesets, unstructured input | S1924 |
| Microsoft (Azure Architecture Center) | lowest complexity that works; if prompt engineering solves it, no agent | S1925 |
| Microsoft Foundry Blog (practitioner posts) | "NL understanding or dynamic generation? If no, stop"; deterministic spine, agentic leaves | S2162, S2163 |
| Google (Cloud Architecture Center / Agents Companion) | summarization/translation/classification often don't need an agent; deterministic-and-stable logic doesn't either | S2160 |
| Thoughtworks (Radar Vol 34) | narrow agent scope (Agent Skills, Trial); zero trust, least privilege and defense in depth as table stakes for "permission-hungry agents"; sandboxed execution a separate Trial blip | S2164, S2165 |

| Published number | Value | Source | Tag |
|---|---|---|---|
| Cost vs token volume | 3,000 → 30,000 tokens/run at 50,000 runs/day: ~$1.50 → ~$15/day | S2174 | COMMUNITY |
| Per-call latency | deterministic step < 10 ms; LLM call 300-600 ms; ReAct agents 8-15 calls/task | S2174 | COMMUNITY |
| Non-deterministic success rate framing | "Unreliability Tax": 80% demo success vs 20% production failure | S2173 | COMMUNITY |
| Agent vs. multi-agent token multiplier vs. chat | ~4x / ~15x | reused from topic 4 (S1921) | DOC |

## Examples

- Example: a drift-explanation call for device `PL-LT-00123` compares the declared DSC document in git
  against the observed `DCMAgent`/`CIAgent` log lines for that device — a three-way deterministic diff,
  not a case where an agent is asked to "figure out" whether the device drifted. Not run against real
  data.
- Example: routing "list every failing resource id for `PL-LT-00123`'s last baseline evaluation" through
  `dsc config test`'s documented output schema (S150/S154) rather than through free-text log
  summarization is the catalogue's "declared-configuration drift detection" row.
