---
topic: agents/agent-overuse-patterns
priority: P1
applies_to: "Anthropic/OpenAI/Google/Microsoft agent guidance (2025-2026 docs), Thoughtworks Technology Radar Vol 34 (2026-04), jq 1.8, Renovate (docs 44.115.4), conventional-commits v1.0.0, semantic-release, LSP 3.18, DSC 3.3.0, Presidio 2.2.364"
retrieved_utc: 2026-09-25
sources: [S2160, S2161, S2162, S2163, S2164, S2165, S2166, S2167, S2168, S2169, S2170, S2171, S2172, S2173, S2174, S2175, S150, S154, S825, S315, S316, S317, S900, S1920, S1924, S1925, S1935, S1936]
status: partial
---

# Work routed to agents although plain tools would do

## Summary

Anthropic, OpenAI, Google and Microsoft all publish the same core rule, in their own words: find the
simplest solution first, and only reach for an agent when the task needs open-ended judgement, an
unstable ruleset, or unstructured input — never for tasks that are deterministic, stable and already
solved by a grammar, schema or algorithm. None of the four vendors publishes a single universal
cost/latency/error number; the concrete figures available (token multipliers, per-model latency spread,
a $/day formula) come from Anthropic's own agent architecture post and from independent (COMMUNITY)
cost-modelling writeups, not from a cross-vendor benchmark. Topic 4's catalogue
(`agents/subagents-vs-deterministic-tools.md`) already covers *child-agent-vs-tool* signals; this
file's `agent-overuse-patterns.csv` is the wider list of task shapes a team hands to an LLM whole,
alongside the deterministic tool that already exists for them.

## Facts

### QG37 — vendor and practitioner guidance on when not to use an LLM or agent
- Anthropic: "When building applications with LLMs, we recommend finding the simplest solution possible,
  and only increasing complexity when needed... this might mean not building agentic systems at all,"
  and "agentic systems often trade latency and cost for better task performance... [and] higher costs,
  and the potential for compounding errors." [DOC S1920 — reused from topic 4]
- OpenAI's practical guide names three qualifying signals for building an agent — complex judgement-based
  decisions, rulesets that have grown unmaintainable, and heavy reliance on unstructured data — and states
  that if none apply, a deterministic solution may suffice; it explicitly excludes single-turn LLM calls,
  simple chatbots and sentiment classifiers from being "agents" at all. [DOC S1924 — reused from topic 4]
- Microsoft's Azure Architecture Center frames the first decision point as: "does the problem need natural
  language understanding or dynamic generation? If no, it's a deterministic system and you should stop,"
  and recommends starting with deterministic orchestration, escalating to agent-based reasoning only when
  predetermined logic is insufficient; it ranks a versioned, diffable, testable workflow-as-spine design
  (agents as bounded leaf workers) above letting an agent decide the workflow itself. [DOC S1925 — reused
  from topic 4, this fact newly extracted for QG37]
- Google's Cloud Architecture Center and "Agents Companion" whitepaper (content retrieved via search
  summary; direct fetch returned HTTP 403) state that summarization, translation and classification "often"
  do not need an agentic workflow, and name deterministic-and-stable logic, and a need for speed/reliability
  over flexibility, as reasons to avoid an agent. [DOC S2160, S2161 — note: content not independently
  re-verified by direct WebFetch; see `gaps.md`]
- Thoughtworks Technology Radar Volume 34 (April 2026) places "Agent Skills" in **Trial** ("worth
  pursuing") as a way to modularize context, while separately warning that "permission-hungry agents"
  seeking maximum access to private data/systems make zero-trust, sandboxed execution and defense-in-depth
  "non-negotiable table stakes," and that teams are finding agent workflows fail in production when agent
  durability is ignored — an implicit argument for keeping agent scope narrow rather than routing whole
  workflows through one. [DOC S2164, S2165]
- Independent cost/latency figures (none vendor-published as a general benchmark): a high-volume pipeline
  run 50,000×/day at 3,000 tokens/run costs roughly $1.50/day at current frontier prices, rising to $15/day
  at 30,000 tokens/run — a 10x token increase producing a 10x cost increase, i.e. cost scales linearly with
  token volume, not with task difficulty. [COMMUNITY S2173]
- Independent measurement: per-model latency for the same agentic task varies about 21x across model
  choices in one comparison (12,874 ms vs 613 ms per trial). [COMMUNITY S2174]
- Independent framing: agentic systems introduce "probabilistic uncertainty into previously deterministic
  software stacks," an "Unreliability Tax" — the same request can succeed 95% of the time and silently
  produce a wrong answer the other 5%, which a deterministic script cannot do by construction (its wrong
  answers are only encoded bugs, not run-to-run variance). [COMMUNITY S2174, S2172]
- No fetched vendor page gives a single named "post-mortem" of an agent deployed where a deterministic
  tool would have sufficed; the closest official material is Microsoft's own blog title "Stop Letting
  Agents Run the Workflow," whose body could not be retrieved this session (see `gaps.md`). [UNK]

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
- Renovate (docs banner version 44.115.4) automates "pull requests to update your dependencies and lock
  files" from declared configuration/presets, with no LLM/AI step named anywhere in its own docs. [DOC
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
- `dsc config test` and ConfigMgr baseline compliance evaluation are deterministic drift-detection
  tools for Windows endpoint management: DSC's `test` operation has a published output schema
  (`schemas/v3/bundled/outputs/{config,resource}/test.json`) [DOC S150, S154 — reused from `dsc/`,
  part `dsc`], and ConfigMgr's CMPivot query surface (entities, `CcmLog()`, `WinEvent()`) is the
  documented structured-query path for live device state. [DOC S315, S316, S317 — reused from
  `mecm/cmpivot.md`, part `mecm`]
- Presidio's `PatternRecognizer` (2.2.364) matches entities by regex plus context words and deny/allow
  lists — the documented deterministic alternative to a free-text NER call for any entity with a fixed
  lexical shape (the same class of fact used for structured-field tokenization design). [DOC S825 —
  reused from `privacy/`, part `privacy`]
- Power BI scheduled refresh (documented elsewhere in the kb, part `arch`/`powerbi`) is the deterministic
  path for recurring report generation over a fixed view/measure set, rather than an agent re-summarizing
  the same numbers on each request. [DOC S900 — reused, cited by reference not re-derived]

### QG39 — signals and measures that a task is over-routed
- **Output fully determined by input**: OpenAI's own exclusion list (single-turn LLM call, sentiment
  classifier) matches this signal directly — no workflow control is being exercised, so there is nothing
  "agentic" to justify. [DOC S1924]
- **Same answer recurs across runs**: Anthropic's own consolidation signal for tools (see topic 4, QG14) —
  a fixed multi-step call sequence that never varies across runs is the same signal applied one level up,
  to whether the whole task needed an agent at all. [DOC S1935 — reused from topic 4]
- **A spec or grammar already exists**: JSON, CSV, DSC configuration documents, conventional-commit
  messages and Presidio's regex patterns are all named, published grammars; wherever one exists the tool
  reading it does not need to "understand" language, only parse a format. [DER from S2166, S2169, S150]
- **Errors are unacceptable / audit needs exact reproduction**: the same input to a deterministic tool
  always produces the same output; a model can succeed 95% of the time and silently err the other 5%
  ("Unreliability Tax") — unacceptable where the record itself is the audit trail. [COMMUNITY S2174; DER
  general implication for any system that inserts audit rows for its own actions]
- **Volume is high / latency matters**: cost scales linearly with token volume in the one published
  formula found (10x tokens → 10x cost), and per-model latency spread (21x in one comparison) makes an
  LLM call a poor fit once a sub-second or high-throughput budget is required. [COMMUNITY S2173, S2174]
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
| Microsoft (Azure Architecture Center) | "does it need NL understanding or dynamic generation? If no, stop — deterministic system" | S1925 |
| Google (Cloud Architecture Center / Agents Companion) | summarization/translation/classification often don't need an agent; deterministic-and-stable logic doesn't either | S2160, S2161 |
| Thoughtworks (Radar Vol 34) | narrow agent scope (Agent Skills, Trial); zero-trust/sandboxing as table stakes against "permission-hungry agents" | S2164, S2165 |

| Published number | Value | Source | Tag |
|---|---|---|---|
| Cost scaling with token volume | 10x tokens/run → 10x $/day (linear) | S2173 | COMMUNITY |
| Per-model latency spread on one agentic task | ~21x (613 ms – 12,874 ms) | S2174 | COMMUNITY |
| Non-deterministic success rate framing | "95% success, 5% silent wrong answer" as an illustrative split | S2174 | COMMUNITY |
| Agent vs. multi-agent token multiplier vs. chat | ~4x / ~15x | reused from topic 4 (S1921) | DOC |

## Examples

- Example: a drift-explanation call for device `PL-LT-00123` compares the declared DSC document in git
  against the observed `DCMAgent`/`CIAgent` log lines for that device — a three-way deterministic diff,
  not a case where an agent is asked to "figure out" whether the device drifted. Not run against real
  data.
- Example: routing "list every failing resource id for `PL-LT-00123`'s last baseline evaluation" through
  `dsc config test`'s documented output schema (S150/S154) rather than through free-text log
  summarization is the catalogue's "declared-configuration drift detection" row.
