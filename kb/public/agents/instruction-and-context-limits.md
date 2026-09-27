---
topic: agents/instruction-and-context-limits
priority: P1
applies_to: "Copilot Studio, M365 Copilot declarative agent manifest 1.4/1.8, GitHub Copilot, OpenAI Assistants/custom GPTs, Gemini API, Claude Code/Projects/Skills, as published 2026-09-25"
retrieved_utc: 2026-09-27
sources: [S1840, S1841, S1842, S1843, S1844, S1845, S1846, S1847, S1848, S1849, S1850, S1851, S1852, S1853, S1854, S1855, S1856, S1857, S1859, S1860, S1863, S1864, S1865, S1866, S1867, S1869, S1870, S1960, S-jexpr3gv, S-gwco6fl2, S-etprakdx]
status: partial
---

# "Instruction limit exceeded" and instruction/context limits across products

## Summary
No product publishes the literal phrase "instruction limit exceeded" as a stable API error string. A Copilot Studio
error `OpenAIAdditionalInstructionsLengthExceededLimit` for combined instructions has been attributed to the
community, but neither the cited article nor Microsoft's error-code page (re-read 2026-09-27) states it; Copilot
Studio documents an 8,000-character instructions limit. Every other product enforces instruction/description length as a silent UI cap, a save-time refusal, or
a generic 400 on the underlying model call, worded around "exceeds the maximum" or similar, not "instruction limit".

## Facts
- Copilot Studio's quotas page lists 8,000 characters as the limit on instructions for a Copilot agent, and the
  generative-answers prompt-modification page limits prompt (custom) instructions to 8,000 characters.
  [DOC S1960, S-jexpr3gv]
- A community article says Copilot Studio accepts 8,000 characters of agent instructions at creation but some
  configurations enforce 2,000 characters after deployment (citing a Microsoft Q&A thread), and argues that agent
  reliability degrades well before the documented limit. [COMMUNITY S1843]
- An error `OpenAIAdditionalInstructionsLengthExceededLimit`, returned when combined agent + node + system
  instructions cross an internal threshold even though each field is under 8,000 characters.
  [UNK: not in S1843 as re-read 2026-09-27, and not listed on Microsoft's error-code page S1842]
- Microsoft's Copilot Studio prompt-node best practices include "Keep it brief": make custom instructions concise,
  because instructions that are too long can lead to latency, timeouts, or issues handling the prompt.
  [DOC S-gwco6fl2]
- A Microsoft Community Hub question (posted 2025-11-07, read 2026-09-27) reports an 8,000-character limit on agent
  instructions when building an agent with a Microsoft 365 Copilot licence and asks whether a Copilot Studio licence
  has a different limit; the thread has no reply, so whether Copilot Studio differs stays open.
  [COMMUNITY S1841: user report in an unanswered thread, no Microsoft answer]
- Microsoft's Copilot Studio authoring error-code reference (re-read in full 2026-09-27) lists no
  `OpenAIAdditionalInstructionsLengthExceededLimit` code and no instructions-length code; the nearest size errors are
  `TooMuchDataToHandle` (the request sent to OpenAI exceeds the maximum request size: user input, prior action
  output, tools called and conversation history) and `ConversationStateTooLarge`. [DOC S1842]
- M365 Copilot declarative agent manifest (schema 1.4; the page names 1.8 as the latest version): the `instructions`
  field "must contain at least one nonwhitespace character and be 8,000 characters or less." Unless stated otherwise,
  every other string property in the manifest is capped at 4,000 characters (`name` 100, `description` 1,000,
  `disclaimer.text` 500 are stated overrides). [DOC S1840]
  - The manifest schema does not document a runtime error message for exceeding `instructions` length; it states the
    constraint as a schema validation rule ("must ... be 8,000 characters or less"), which would fail app-package
    validation rather than emit a runtime "limit exceeded" error. [DER S1840: derived from the schema's constraint
    wording, which is a build-time/package-validation constraint, not a documented runtime error]
- GitHub Copilot: `copilot-instructions.md` and `*.instructions.md` under `.github/` previously stopped being read by
  Copilot code review past 4,000 characters; GitHub removed this character limit (announced June 2026). No error is
  raised — content past the old limit was silently truncated/ignored, not rejected. [DOC S1851, S1852]
  - Best practice from GitHub's own docs after the limit's removal: keep any single instruction file to roughly 1,000
    lines, since response quality can degrade past that size — a guidance line, not an enforced limit. [DOC S1851]
- A GitHub community question (2025-02-19) asking for the file-size limit of Copilot custom instructions in Visual Studio has no reply (read 2026-09-27), so no community answer fills that gap. [COMMUNITY S1853]
- Claude API strict tool use: `strict: true` on a tool definition constrains token sampling to the tool's `input_schema` (grammar-constrained sampling), so `input` always matches the schema and `name` is always valid; the schema may use only the JSON Schema subset listed under structured outputs, and a request that sets `strict: true` on the `computer_toolset_20260801` or `browser_toolset_20260801` entry is rejected. [DOC S1869]
- OpenAI: a community forum thread states that the ChatGPT custom-GPT builder UI caps instructions at 8,000
  characters (against a much larger Assistants API figure); the thread does not say what happens past the cap
  (error, blocked save or truncation). [COMMUNITY S1844]
- OpenAI Assistants API: a 2023 community forum thread reports a 32,768-character limit on a single message's content
  (validation error "ensure this value has at most 32768 characters"); it says nothing about the `instructions`
  field. [COMMUNITY S1845]
- The exact `instructions` field limit of the OpenAI Assistants API and its error text: no official OpenAI
  platform-docs page was fetched to confirm them. [UNK, see gaps.md]
- Gemini API: no published fixed `systemInstruction` character/token limit as a single documented number; behavior is
  reported as model- and backend-dependent. A community-reported case: `systemInstruction` around 300k characters
  (~84k tokens) succeeded, ~320k characters (~90k tokens) returned a 400 `INVALID_ARGUMENT` with the generic message
  "Request contains an invalid argument" (no length-specific wording). [COMMUNITY S1846]
- Gemini API generic input-length error "The input token count (N) exceeds the maximum number of tokens allowed
  (32768).", about total input tokens rather than an "instructions" field.
  [UNK: not in S1846 as re-read 2026-09-27; source of this wording not identified]
- Claude (Anthropic):
  - No API error type named for "instructions" specifically. The Claude API's documented error taxonomy is generic:
    `400 invalid_request_error`, `413 request_too_large` (request exceeds a per-endpoint byte maximum — 32 MB for the
    Messages API), `429 rate_limit_error`, `529 overloaded_error`. None of these use the phrase "instruction limit."
    [DOC S1847]
  - Claude Code skills: the combined `description` + `when_to_use` frontmatter text is truncated at 1,536 characters
    in the skill listing "to reduce context usage" — a silent truncation, not a raised error. The `compatibility`
    frontmatter field is capped at 500 characters. `SKILL.md` itself has no hard limit but a documented tip to keep it
    under 500 lines. [DOC S1860]
  - The 1,536-character cap is a recent raise from an earlier, differently documented 250-character cap; Claude Code's
    own issue tracker records that the docs lagged the change and that Claude Code added a startup warning when a
    skill description is truncated (exact current wording of that warning was not independently fetched). [COMMUNITY
    S1848, S1849]
  - A separate, portability-oriented Agent Skills specification (referenced from community sources, not confirmed as
    an Anthropic-authored page in this pass) is reported to cap `description` at 1,024 characters, narrower than
    Claude Code's own 1,536; an open GitHub issue on `anthropics/skills` reports frontmatter descriptions exceeding a
    1,024-character limit as a real failure mode when a skill is meant to be portable across tools. [COMMUNITY S1850]
  - CLAUDE.md: community measurement and tooling exist around a documented practical threshold; multiple sources
    describe Claude Code warning once a `CLAUDE.md` file reaches roughly 40KB, framed as a performance-degradation
    signal rather than a hard rejection. No official Anthropic docs page was fetched in this pass stating this 40KB
    number directly — a 2026-09-26 search of the Claude Code docs found a "large CLAUDE.md startup notice" in the changelog but no stated
    threshold. [UNK: search-result digest only, originating page not fetched; see gaps.md]
  - Claude Projects: content added to project knowledge is used as context in the project's chats, and on paid plans
    Claude automatically enables RAG mode when project knowledge approaches the context window limit. The support
    article publishes no character limit for the project instructions field. [DOC S1859]
  - Context window on paid Claude plans depends on the model: 200K tokens by default, 500K or 1M tokens for the newer
    models listed (for chat, for example 1M for Claude Opus 5.5 and 500K for Claude Opus 4.8). [DOC S-etprakdx]
  - A live character counter on the project instructions field with no published number. [UNK: not in S1859 as
    re-read 2026-09-27; see gaps.md]
  - Tool-count/tool-name limits: a tool name has a documented 128-character limit (reported via a Claude Code bug
    report reproducing the API's rejection), and the raw Messages API is reported to support very large tool catalogs
    (order 10,000) once `defer_loading`/tool search is used, versus client UIs (for example VS Code's tool picker)
    that cap selectable tools at 128 — a client-side limit, not an Anthropic API ceiling. [COMMUNITY S1857]
- Instruction volume and adherence (vendor-adjacent research): IFScale (arXiv, Distyl AI authors) measured
  instruction-following accuracy as the number of simultaneous keyword-inclusion instructions rises from 10 to 500 in
  steps of 10, finding three degradation patterns across model families — threshold decay (near-perfect until a
  critical density, then a sharp drop; reasoning models), linear decay (for example Claude Sonnet 4-era models, GPT-4.1),
  and exponential decay (weaker/non-reasoning models). This is a non-vendor academic benchmark. [COMMUNITY S1854]
- Anthropic's own engineering guidance ("Effective context engineering for AI agents") describes context as a finite
  resource with an "attention budget": every added token depletes it, and recommends finding the smallest set of
  high-signal tokens for the task. For long-horizon tasks it names compaction, structured note-taking, and multi-agent
  (sub-agent) architectures. [DOC S1855]
- A separate, real regression (not a documented limit) illustrates the practical stakes of instruction/system-prompt
  volume in Claude Code: the fixed system-prompt token overhead grew by roughly 70K tokens between two neighboring
  Claude Code versions (2.1.89 -> 2.1.96), reported by users as making sessions "effectively unusable" without manual
  compaction, given a fixed context budget. [COMMUNITY S1856 — a bug report, not vendor-confirmed root cause]

### Deepening pass additions (QG5, QG7)

- **The ~40KB CLAUDE.md warning is refuted, not merely unconfirmed.** `code.claude.com/docs/en/memory` (fetched
  directly, 2026-09-25) documents no KB-based threshold for `CLAUDE.md` at all: "target under 200 lines per
  CLAUDE.md file... Claude Code loads a CLAUDE.md file of up to 4 MiB in full and skips a larger file." The
  troubleshooting section repeats it: "Files over 200 lines consume more context and may reduce adherence. Claude
  Code skips a file over 4 MiB." The `/doctor` command (v2.1.206+) proposes trims for a checked-in `CLAUDE.md`,
  cutting content Claude can derive from the codebase. The separate 200-line/25KB limit in the same doc applies only
  to auto-generated `MEMORY.md`, not `CLAUDE.md` — a distinction the earlier community sources conflated. [DOC
  S1863, superseding the COMMUNITY/UNK row in the CSV]
- **OpenAI**: neither the current function-calling guide nor the structured-outputs guide (both fetched at
  `developers.openai.com`, the successor domain to `platform.openai.com/docs/guides/*`) states a numeric character
  limit for the Assistants/Responses `instructions` field; the guides describe the 128-tool-adjacent soft guidance
  ("aim for fewer than 20 functions... at the start of a turn") but not a hard 128-tool ceiling on either fetched
  page. [DOC S1865, S1867 — the specific "128 tools" figure this task asked to confirm was not found on either
  fetched OpenAI page; treat the commonly cited "128" as UNK, see gaps.md]
- **Gemini**: `ai.google.dev/gemini-api/docs/function-calling` (fetched) documents no numeric `systemInstruction`
  length limit and no fixed count limit on function declarations; it only shows examples using `type`, `properties`,
  `required`, `enum`, `description` without stating the full supported/unsupported OpenAPI-subset keyword list. [DOC
  S1866 — narrower confirmation than a full "supported subset" enumeration; still leaves the community-reported
  ~85-90K-token boundary (S1846) as the best available number]
- **Claude Code CHANGELOG (`github.com/anthropics/claude-code`, entries through v2.1.282, fetched 2026-09-25)**
  confirms CLAUDE.md-size tooling is active and evolving, not static: 2.1.281 "Improved the large CLAUDE.md startup
  notice to also count instruction files together, so many mid-sized files and @-imports are caught" — i.e. Claude
  Code already warns about *combined* instruction-file size (CLAUDE.md + imports + rules), a mechanism closer to
  Copilot Studio's combined-instructions threshold (`OpenAIAdditionalInstructionsLengthExceededLimit`) than to any
  single-file byte cap. [DOC S1864]
- **QG7 — Chroma "Context Rot" (research.trychroma.com / trychroma.com/research/context-rot, published 2025-07-14,
  vendor-authored by an AI infrastructure company benchmarking 18 models it does not sell — tagged COMMUNITY per
  rule 1 since Chroma is not the vendor of the models tested):** tested 18 models across Anthropic (Opus 4, Sonnet
  4/3.7/3.5, Haiku 3.5), OpenAI (o3, GPT-4.1, GPT-4.1 mini/nano, GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo), Google (Gemini
  2.5 Pro/Flash, 2.0 Flash) and Alibaba (Qwen3 8B/32B/235B) families. Findings: performance degrades with increasing input length
  even on "needle in a haystack" tasks with a single needle and no distractors — degradation is not explained by
  retrieval difficulty alone; a single distractor already reduces accuracy versus the no-distractor baseline, and
  additional distractors compound the effect non-uniformly; on LongMemEval (conversational QA), the gap between a
  focused ~300-token prompt and the full ~113K-token prompt was large, with Claude models showing the most
  pronounced gap; a "repeated words" structural task shows consistent degradation up to 10,000-word sequences purely
  from length, independent of semantic difficulty; on that task some models declined to attempt it (Claude Opus 4
  2.89% of attempts, GPT-4.1 2.55%, Qwen3-8B 4.21%); outputs were scored by a GPT-4.1 judge whose prompt was iterated
  until its alignment with human judgements exceeded 0.99. [COMMUNITY S1870]
- **QG7 tie-together**: IFScale (S1854, instruction *count* degradation) and Chroma's Context Rot (S1870, input
  *length* degradation, independent of instruction count) are two distinct, non-vendor-confirmed axes of the same
  underlying claim in Anthropic's own vendor guidance (S1855) that every added token depletes a finite "attention
  budget" — none of the three sources contradicts another; they measure different independent variables (instruction
  count vs. raw context length) with consistent directional findings (more of either degrades reliability). [DER S1854, S1870, S1855: the three measure different variables]

## Reference
See `agents/instruction-and-context-limits.csv` for the normalized product/limit/value/error-text table (40 rows
after this deepening pass). For the Claude Code data point in this survey (SKILL.md `description`+`when_to_use`
truncated at 1,536 characters), see `claude/skills-and-subagents.md`.

## Examples
None of the products above expose a fixture-estate-relevant example; this topic concerns a project's own instruction
authoring (`CLAUDE.md`, `.claude/skills/*/SKILL.md`, MCP tool descriptions), not device data, so no `PL-LT-00123` /
`corp.example.com` example applies. A worked example's own current sizes are stated as facts in
`agents/agent-error-catalogue.md` under QG8.
