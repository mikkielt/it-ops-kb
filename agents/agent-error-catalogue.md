---
topic: agents/agent-error-catalogue
priority: P1
applies_to: "Claude API/Claude Code as documented 2026-09-25; extends claude/tool-output-limits.md"
retrieved_utc: 2026-09-25
sources: [S1847, S1857, S1858, S1855, S1861, S1862, S1864, S1842, S1843, S1865, S1868]
status: partial
---

# Agent and MCP-server error catalogue (extends `claude/tool-output-limits.md`)

## Summary
This file adds errors not already covered by `claude/tool-output-limits.md` (which owns MCP output-size and
timeout settings). It covers HTTP/API-level errors, `tool_use`/`tool_result` pairing failures, and a checklist for
keeping a project's `CLAUDE.md`, skills and MCP tool definitions inside documented limits.

## Facts
- Claude API HTTP error taxonomy (canonical): `400 invalid_request_error`, `401 authentication_error`,
  `402 billing_error`, `403 permission_error`, `404 not_found_error`, `409 conflict_error`,
  `413 request_too_large`, `429 rate_limit_error`, `500 api_error`, `504 timeout_error`, `529 overloaded_error`.
  [DOC S1847]
- `429 rate_limit_error`: fires on an organization rate limit, a usage tier's monthly spend cap, or a spend limit on
  the Claude Code workspace; a tier spend-cap 429 has **no** `retry-after` header and keeps failing until access
  resumes — a caller must not treat a bare 429 as always transient/retryable. [DOC S1847]
- `529 overloaded_error`: "The API is temporarily overloaded"; can also surface as 429s if an organization's own
  traffic spikes sharply enough to hit acceleration limits — the documented mitigation is to ramp traffic up
  gradually rather than retry harder. [DOC S1847]
- Official SDKs retry transient failures (connection errors, rate limits, 5xx) with exponential backoff, twice by
  default, honoring `retry-after` when present; retry count is configurable via `max_retries`. [DOC S1847]
- `413 request_too_large`: request exceeds a per-endpoint byte maximum (Messages API 32 MB, Token Counting API 32 MB,
  Batch API 256 MB, Files API 500 MB); on the direct API, Cloudflare returns this before the request reaches
  Anthropic's servers. [DOC S1847]
- `504 timeout_error`: "The request timed out while processing"; documented mitigation is the streaming Messages API
  for long-running requests, and the SDKs validate that non-streaming requests are not expected to exceed a 10-minute
  timeout. [DOC S1847]
- `tool_use` without a matching `tool_result` (and the inverse: an orphaned `tool_result` with an unrecognized
  `tool_use_id`) is a real, recurring 400 `invalid_request_error` in Claude Code sessions, most often produced when
  automatic context compaction drops one half of a tool_use/tool_result pair in long (50+ turn) sessions. [COMMUNITY
  S1858 — a bug-report digest, not an Anthropic-authored error-message quote]
- A tool name over 128 characters is rejected by the API; this was reproduced and reported as a Claude Code bug
  against a long MCP tool name (`mcp__<server>__<tool>` naming can approach this with a long server or tool name).
  [COMMUNITY S1857]
- Anthropic's own context-engineering guidance frames "oversized tool output" and "too many tools loaded up front" as
  the two biggest practical context-budget failures for agents, and recommends: keep tool descriptions minimal and
  distinctive, defer tool definition loading (tool search / `defer_loading`) once a toolset is large, and offload
  bulky observations to the filesystem or to sub-agents that return only a summary rather than raw output. [DOC
  S1855]
- `claude/tool-output-limits.md` already documents, and this file does not repeat: the 10,000-token MCP output
  warning threshold, `MAX_MCP_OUTPUT_TOKENS` (default 25,000), `anthropic/maxResultSizeChars` (ceiling 500,000
  chars), `MCP_TOOL_TIMEOUT`, `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`, `MCP_TIMEOUT`, `MCP_SERVER_CONNECTION_BATCH_SIZE`,
  and auto-backgrounding of long calls. [DER: cross-reference, no new source]

### Deepening pass additions (QG6 full catalogue)

- **Stdout pollution in stdio MCP servers.** The MCP spec (2026-07-28 revision) is explicit and normative: "The
  server **MAY** write UTF-8 strings to `stderr` for any logging purposes"; "The server **MUST NOT** write anything
  to its `stdout` that is not a valid MCP message"; and "The client **MUST NOT** assume `stderr` output indicates
  error conditions." A server that lets a dependency's default logger, a `print()`, or a startup banner reach stdout
  corrupts the newline-delimited JSON-RPC framing the client is parsing, which surfaces to the client as unparseable
  responses or a hung connection, not as a clean protocol error. [DOC S1861]
- **MCP timeouts, confirmed with current defaults (Claude Code, 2026-09-25):** `MCP_TIMEOUT` bounds MCP server
  *startup*; `MCP_TOOL_TIMEOUT` bounds a *tool call*, and is effectively unbounded (~28 hours) when unset; a
  per-server `timeout` in `.mcp.json` is a hard wall-clock floor of at least 1000 ms and also floors the idle
  timeout (stdio servers need Claude Code v2.1.203+ for this to apply to them); `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`
  aborts a call with no response/progress notification within 5 minutes (HTTP/SSE/WebSocket/connector servers) or
  30 minutes (stdio servers) by default, `0` disables it; `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` (added 2.1.274) bounds
  how long a headless (`-p`) run's first turn waits for MCP servers to finish connecting. [DOC S1862, S1864]
- **Headless permission denials.** A tool call needing interactive approval (for example a flagged `rm`) has no TTY
  to answer it in `-p`/headless mode. Claude Code 2.1.277 improved the dangerous-`rm` prompt to name the exact
  flagged command and suggest a `${VAR:?}` guard so a headless run can be diagnosed and re-run with a narrower
  `--allowedTools` scope, rather than silently hanging or failing opaquely. [DOC/DER S1864 — changelog entry, not an
  exhaustive permission-denial reference page]
- **Compaction effects, confirmed via changelog:** compaction can itself fail if the summarization request is
  refused (fixed 2.1.281 by retrying on a fallback model); a hook-driven session (for example an active `/goal`)
  previously ended with "Prompt is too long" instead of compacting when context overflowed a second time (fixed
  2.1.274); a restored memory file's relative "age" note re-rendering per request invalidated the prompt cache after
  every compaction/resume (fixed 2.1.275). [DOC S1864]
- **Claude Code's "Prompt is too long" error, confirmed as a real, named, recoverable condition** (not just an
  inference from context-window math): 2.1.281 "Improved 'Prompt is too long' recovery in sessions dominated by one
  very large first prompt: that prompt is now summarized on its own instead of being left out." [DOC S1864]
- **`stop_reason` values beyond the ones this file already covered** (`end_turn`, `stop_sequence`, `max_tokens`,
  `tool_use`): `pause_turn` (a long-running server-side operation paused rather than ended the turn; the caller
  resends the paused response unmodified to resume it), `refusal` (the model declined to continue generating, a
  terminal outcome that should not be retried unmodified), and `model_context_window_exceeded` (the context window
  was exceeded mid-generation, distinct from the request-time `413 request_too_large`, which fires before generation
  starts). [DER S1868 — derived from the Claude tool-use/messages documentation set; the exact wording of each value
  was not independently re-verified against a single canonical stop-reason reference page in this pass, see
  gaps.md] Separately, a proxy bug where a trailing usage-only frame dropped the true `stop_reason` was fixed in
  Claude Code 2.1.281. [DOC S1864]
- **Unsupported JSON Schema keywords / strict-mode restrictions, per vendor:**
  - *OpenAI* (function calling, strict mode): every object in the schema must set `additionalProperties: false` and
    list every property — including optional ones (typed `["string","null"]` etc.) — in `required`; a schema that
    doesn't is rejected. OpenAI also states plainly that "some features of JSON schema are not supported" under
    structured outputs generally, without enumerating the excluded keyword list on the fetched guide page. [DOC
    S1865, S1867]
  - *Anthropic* (Claude, strict tool use): `strict: true` compiles `input_schema` into a constrained-sampling grammar
    (the same pipeline as structured outputs), guaranteeing the returned `input` matches the schema and the tool
    `name` is always one of the provided tools; the two built-in toolset entries `computer_toolset_20260801` and
    `browser_toolset_20260801` explicitly reject a `strict: true` request. PHI must never appear in `input_schema`
    property names, `enum`/`const` values, or `pattern` regexes, because compiled schemas are cached up to 24 hours
    outside the normal ZDR/HIPAA prompt-and-response protections. [DOC S1869]
  - *Gemini*: the fetched function-calling guide documents no enumerated list of unsupported OpenAPI-subset keywords
    and no hard cap on the number of function declarations; function names are only style-guided ("underscores or
    camelCase"), not regex/length-constrained on the page. [UNK — not found on the fetched page, see gaps.md]
  - *Copilot Studio / M365 Copilot / Power Platform*: no separate JSON-Schema-keyword restriction was found;
    `AsyncResponsePayloadTooLarge` and the manifest string-length caps (`agents/instruction-and-context-limits.csv`)
    are the closest analogues, both shape restrictions rather than keyword restrictions.
- **Tool-count guidance (soft, not a hard vendor limit):** OpenAI's function-calling guide recommends "fewer than 20
  functions available at the start of a turn" as a soft suggestion, not an enforced ceiling, and directs larger
  toolsets to dynamic/deferred loading — the same shape of guidance Anthropic gives for Claude Code's `tool_search`.
  [DOC S1865, S1855]
- **Copilot Studio's full error-codes page, now parsed** (`learn.microsoft.com/.../authoring/error-codes`, S1842):
  the page enumerates roughly 50 named error codes plus a numbered channel-error table (2007, 2018, 2021, 2022,
  2100). The instructions-length code (`OpenAIAdditionalInstructionsLengthExceededLimit`) does **not** appear as a
  named row on this official page at all — it remains sourced only from the community digest (S1843); the official
  page's closest neighbors are `ConnectedAgentGptComponentNotFound` (a connected agent missing instructions/
  description) and `TooMuchDataToHandle`/error 2007 ("The bot contains too much content to be able to work.",
  reduce message lengths or topic count). Throttling and timeout codes are extensive: `HTTP429TooManyRequests`,
  `HTTP408RequestTimeout`, `HTTP504GatewayTimeout`, `ExecutionTimeout`, `OperationTimeout`,
  `GenAISearchandSummarizeRateLimitReached`, `GenAIToolPlannerRateLimitReached`, `OpenAIRateLimitReached`,
  `QuotaExceeded`, `EnforcementMessageC2`, `DataverseStructured429`, `DataverseFileAttachment429`, `SharePoint429`.
  See `agents/agent-error-catalogue.csv` for the full row-by-row breakdown with resolutions as documented. [DOC
  S1842]
- **Power Platform / Power Automate throttling for agent flows.** The error-codes page's connector-throttling family
  (`HTTP429TooManyRequests`, `DataverseStructured429`, `DataverseFileAttachment429`, `SharePoint429`) is the same
  throttling surface an agent flow's connector actions hit; Microsoft's documented mitigation is retry-with-backoff,
  concurrency limits on batch operations, and monitoring throttling in Power Platform analytics — no
  agent-flow-specific throttling error code beyond the shared connector-level codes was found on the fetched page.
  [DOC S1842]

## Reference
See `agents/agent-error-catalogue.csv` for the normalized tool/error/cause/avoidance table (48 rows after this
deepening pass).

### Checklist: keeping a project inside documented limits

A `CLAUDE.md` at the repository root should be measured directly against the ~40 KB community-reported
Claude Code warning threshold (see `agents/instruction-and-context-limits.md`, which flags that figure as
COMMUNITY pending an official-docs confirmation); a file well under that line needs no action. Any `SKILL.md`
should be checked against Claude Code's own documented tip of staying under 500 lines, with detail moved into a
`scripts/` directory or separate files the skill reads on demand, matching Claude Code's progressive-disclosure
guidance [DOC S1860].

Checklist, each line cited:
1. Keep `CLAUDE.md` well under the community-reported ~40 KB caution line; if it grows, split into `.claude/rules/`
   and `@import` rather than inlining more into the root file (community pattern, not an Anthropic-documented
   mechanism) — [COMMUNITY, see instruction-and-context-limits.md gap on the exact 40 KB source].
2. Keep every `SKILL.md`'s `description` + `when_to_use` combined text under 1,536 characters, front-loading the
   trigger words, since Claude Code truncates silently past that point in the skill listing — [DOC S1860].
3. If a skill must stay portable to non-Claude-Code tools, keep its `description` under 1,024 characters, the
   narrower cap reported for the general Agent Skills spec — [COMMUNITY S1850].
4. Keep any `SKILL.md` body under roughly 500 lines; push detail into files the skill reads on demand — [DOC S1860].
5. Keep MCP tool names (the `mcp__<server>__<tool>` spelling) under 128 characters — a long server
   name plus a long tool name can combine to breach this — [COMMUNITY S1857].
6. Do not assume every tool's full JSON Schema/description needs to load up front once an MCP surface grows past
   a handful of tools; Anthropic's own guidance favors deferred loading over trimming correctness — [DOC S1855].
7. Treat a 429 from the Claude Code workspace spend cap as non-retryable (no `retry-after`), distinct from an
   ordinary rate-limit 429 — relevant if a project's own CI job ever calls the API directly — [DOC S1847].
8. In multi-turn sessions (long agentic runs), watch for `tool_use`/`tool_result` pairing errors after
   compaction; this is a known Claude Code failure mode, not specific to any one project, and is mitigated by not
   editing assistant/tool history manually — [COMMUNITY S1858].

## Examples
Not applicable to this topic (it concerns a project's own tooling files, not device data).
