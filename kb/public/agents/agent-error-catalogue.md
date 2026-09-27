---
topic: agents/agent-error-catalogue
priority: P1
applies_to: "Claude API/Claude Code as documented 2026-09-25; extends claude/tool-output-limits.md"
retrieved_utc: 2026-09-27
sources: [S1847, S1857, S1858, S1855, S1861, S1862, S1864, S1842, S1843, S1865, S1867, S1869, S1860, S1850, S-qso6o6wu, S1863, S1866, S-xxd6fl45, S-hzgoj7bh, S-hcl5uw5c, S-dorcmamy, S-rvnsf5ty, S-f3chtt24]
status: complete
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
- An orphaned `tool_result` (its `tool_use_id` has no matching `tool_use` block in the previous message) is rejected
  with a 400 `invalid_request_error` ("unexpected `tool_use_id` found in `tool_result` blocks"). The Claude Code
  report of it came from a session whose history was rebuilt after an interruption and resume; the issue was closed
  as a duplicate, not planned, with no maintainer diagnosis. [COMMUNITY S1858 — a bug report quoting the API error,
  not an Anthropic-authored explanation of the cause]
- A tool name over 128 characters is rejected by the API; this was reproduced and reported as a Claude Code bug
  against a long MCP tool name (`mcp__<server>__<tool>` naming can approach this with a long server or tool name).
  [COMMUNITY S1857]
- Anthropic's context-engineering guidance names bloated tool sets (too much functionality, ambiguous choice between
  tools) as one of the most common failure modes, and recommends a minimal viable tool set with minimal overlap,
  "just in time" loading of data through lightweight references such as file paths, clearing old tool results, and
  sub-agents that explore in their own context and return a condensed summary (often 1,000-2,000 tokens). [DOC
  S1855]
- Claude Code defers MCP tool definitions by default (tool search): only tool names and server instructions load at
  session start, so adding servers has little effect on the context window. [DOC S1862]
- `claude/tool-output-limits.md` already documents, and this file does not repeat: the 10,000-token MCP output
  warning threshold, `MAX_MCP_OUTPUT_TOKENS` (default 25,000), `anthropic/maxResultSizeChars` (ceiling 500,000
  chars), `MCP_TOOL_TIMEOUT`, `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`, `MCP_TIMEOUT`, `MCP_SERVER_CONNECTION_BATCH_SIZE`,
  and auto-backgrounding of long calls. [DER: cross-reference, no new source]

### Deepening pass additions (QG6 full catalogue)

- **Stdout pollution in stdio MCP servers.** The MCP spec (2026-07-28 revision) is explicit and normative: "The
  server **MAY** write UTF-8 strings to `stderr` for any logging purposes"; "The server **MUST NOT** write anything
  to its `stdout` that is not a valid MCP message"; and "The client **SHOULD NOT** assume `stderr` output indicates
  error conditions." A server that lets a dependency's default logger, a `print()`, or a startup banner reach stdout
  corrupts the newline-delimited JSON-RPC framing the client is parsing, which surfaces to the client as unparseable
  responses or a hung connection, not as a clean protocol error. [DOC S1861]
- **MCP timeouts, confirmed with current defaults (Claude Code, 2026-09-25):** `MCP_TIMEOUT` bounds MCP server
  *startup*; `MCP_TOOL_TIMEOUT` bounds a *tool call*, and is effectively unbounded (~28 hours) when unset; a
  per-server `timeout` in `.mcp.json` is a hard wall-clock floor of at least 1000 ms and also floors the idle
  timeout (requires Claude Code v2.1.203+, before which stdio servers were exempt from the idle timeout); `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`
  aborts a call with no response/progress notification within 5 minutes (HTTP/SSE/WebSocket/connector servers) or
  30 minutes (stdio servers) by default, `0` disables it; `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` (added 2.1.274) bounds
  how long a headless (`-p`) run's first turn waits for MCP servers to finish connecting. [DOC S1862, S1864]
- **Headless permission denials.** A tool call needing interactive approval (for example a flagged `rm`) has no TTY
  to answer it in `-p`/headless mode. Claude Code 2.1.277 improved the dangerous-`rm` prompt to name the exact
  flagged command and suggest a `${VAR:?}` guard so a headless run can be diagnosed and re-run with a narrower
  `--allowedTools` scope, rather than silently hanging or failing opaquely. [DOC/DER S1864 — changelog entry, not an
  exhaustive permission-denial reference page]
- **Compaction effects, confirmed via changelog:** compaction can itself fail if the summarization request is
  refused (fixed 2.1.282 by retrying on a fallback model); a hook-driven session (for example an active `/goal`)
  previously ended with "Prompt is too long" instead of compacting when context overflowed a second time (fixed
  2.1.274); a restored memory file's relative "age" note re-rendering per request invalidated the prompt cache after
  every compaction/resume (fixed 2.1.275). [DOC S1864]
- **Claude Code's "Prompt is too long" error, confirmed as a real, named, recoverable condition** (not just an
  inference from context-window math): 2.1.281 improved "Prompt is too long" recovery in sessions dominated by one
  very large first prompt, which is now summarized on its own "instead of being left out of the summary."
  [DOC S1864]
- **`stop_reason` values beyond the ones this file already covered** (`end_turn`, `stop_sequence`, `max_tokens`,
  `tool_use`), per Anthropic's "Stop reasons and fallback" reference: `pause_turn` (the server-side sampling loop
  hit its iteration limit, 10 per request by default, while running server tools such as web search; the caller
  sends the response back as-is to let Claude finish; a response waiting on a client `tool_use` is `tool_use`,
  never `pause_turn`), `refusal` (Claude declined to respond; safety classifiers return it as a normal HTTP 200,
  not an error; `stop_details` names the policy category, and the documented handling is to retry on a fallback
  model rather than resend the same request to the same model), and `model_context_window_exceeded` (the response
  filled the model's context window and should be treated as truncated; distinct from the request-time
  `413 request_too_large`, which fires before generation starts; returned without a beta header on Sonnet 4.5 and
  newer). [DOC S-qso6o6wu] Separately, a proxy bug where a trailing usage-only frame dropped the true
  `stop_reason` was fixed in Claude Code 2.1.281. [DOC S1864]
- **Unsupported JSON Schema keywords / strict-mode restrictions, per vendor:**
  - *OpenAI* (function calling, strict mode): every object in the schema must set `additionalProperties: false` and
    list every property — including optional ones (typed `["string","null"]` etc.) — in `required`; a schema that
    doesn't is rejected. [DOC S1865, S1867] The structured-outputs guide's "Supported schemas" section lists
    what strict mode rejects: the composition keywords `allOf`, `not`, `dependentRequired`, `dependentSchemas`,
    `if`/`then`/`else`; for fine-tuned models also string `minLength`/`maxLength`/`pattern`/`format`, number
    `minimum`/`maximum`/`multipleOf`, object `patternProperties` and array `minItems`/`maxItems`; and size caps of
    5,000 object properties, 10 nesting levels, 120,000 characters of names/enum/const strings and 1,000 enum
    values. A strict request with an unsupported schema returns an error. [DOC S1867]
  - *Anthropic* (Claude, strict tool use): `strict: true` compiles `input_schema` into a constrained-sampling grammar
    (the same pipeline as structured outputs), guaranteeing the returned `input` matches the schema and the tool
    `name` is always one of the provided tools; the two built-in toolset entries `computer_toolset_20260801` and
    `browser_toolset_20260801` explicitly reject a `strict: true` request. PHI must never appear in `input_schema`
    property names, `enum`/`const` values, or `pattern` regexes, because compiled schemas are cached up to 24 hours
    outside the normal ZDR/HIPAA prompt-and-response protections. [DOC S1869]
  - *Gemini*: the API reference constrains a `FunctionDeclaration` name to a-z, A-Z, 0-9, underscores, colons, dots
    and dashes, at most 128 characters (function-call and function-response names: letters, digits, underscores and
    dashes, also 128) [DOC S-xxd6fl45]. Vertex AI's function-calling page is stricter as a best practice: names should
    start with a letter or underscore and be at most 64 characters [DOC S-hzgoj7bh]. The Gemini guide supports only a
    subset of the OpenAPI schema and advises keeping the active set to 10-20 tools; it publishes no hard cap on the
    number of declarations and no list of unsupported keywords [DOC S1866].
  - *Anthropic structured outputs / strict tools, schema subset*: recursive schemas, numeric constraints
    (`minimum`, `maximum`, `multipleOf`) and string length constraints are not supported, and an unsupported feature
    returns a 400 error; per request at most 20 strict tools, 24 optional parameters and 16 union-type parameters
    across all strict schemas, and an over-complex schema returns 400 "Schema is too complex for compilation."
    [DOC S-dorcmamy]
  - *OpenAI structured outputs, schema subset*: `allOf`, `not`, `dependentRequired`, `dependentSchemas` and
    `if`/`then`/`else` are unsupported; a schema may have up to 5000 object properties with up to 10 levels of
    nesting, 120,000 characters of names and enum/const values in total, and 1000 enum values [DOC S1867].
  - *OpenAI tool counts*: the "128 tools" figure is the Assistants API limit (at most 128 tools per assistant; the
    Assistants endpoints are marked deprecated) and the cap on the deprecated Chat Completions `functions` array;
    the current Chat Completions `tools` array carries no `maxItems` in the OpenAPI specification [DOC S-hcl5uw5c].
  - *Copilot Studio / M365 Copilot / Power Platform*: Copilot Studio's MCP troubleshooting page lists known schema
    issues: an integer `exclusiveMinimum` (instead of a Boolean) throws `System.FormatException`; a `type` given as
    an array of types truncates the input schema (use a single type); tools with reference-type inputs are filtered
    out (reference types are unsupported); enum inputs are read as plain strings; the SSE endpoint must be a full
    URI [DOC S-rvnsf5ty]. `AsyncResponsePayloadTooLarge` and the manifest string-length caps
    (`agents/instruction-and-context-limits.csv`) are the other shape restrictions.
- **Tool-count guidance (soft, not a hard vendor limit):** OpenAI's function-calling guide recommends "fewer than 20
  functions available at the start of a turn" as a soft suggestion, not an enforced ceiling, and directs larger
  toolsets to dynamic/deferred loading — the same shape as Claude Code's default MCP tool search (deferred tool definitions).
  [DOC S1865, S1862]
- **Copilot Studio's full error-codes page, now parsed** (`learn.microsoft.com/.../authoring/error-codes`, S1842):
  the page's web-app tab documents 66 named error codes, and its Classic/Teams tab a numbered table (2000-2030,
  2100-2102, 3000-3003). The instructions-length code (`OpenAIAdditionalInstructionsLengthExceededLimit`) does **not** appear as a
  named row on this official page at all; the official
  page's closest neighbors are `ConnectedAgentGptComponentNotFound` (a connected agent missing instructions/
  description), `TooMuchDataToHandle` (the request sent to OpenAI, i.e. user input, earlier action outputs, tools
  and conversation history, exceeds the maximum request size; scope tool outputs down) and Classic/Teams error
  2007 ("The bot contains too much content to be able to work.", reduce message lengths or topic count). Throttling and timeout codes are extensive: `HTTP429TooManyRequests`,
  `HTTP408RequestTimeout`, `HTTP504GatewayTimeout`, `ExecutionTimeout`, `OperationTimeout`,
  `GenAISearchandSummarizeRateLimitReached`, `GenAIToolPlannerRateLimitReached`, `OpenAIRateLimitReached`,
  `QuotaExceeded`, `EnforcementMessageC2`, `DataverseStructured429`, `DataverseFileAttachment429`, `SharePoint429`.
  See `agents/agent-error-catalogue.csv` for the full row-by-row breakdown with resolutions as documented. [DOC
  S1842]
- The error code `OpenAIAdditionalInstructionsLengthExceededLimit` ("The length of the prompt instructions exceeds the
  threshold") is reported by a Copilot Studio user on a generative-answers node once main agent plus node
  instructions passed about 5,300 characters, although the node field shows an 8,000 limit; no Microsoft staff
  answer or error-code page confirms the threshold. [COMMUNITY S-f3chtt24]
- A community post reports that Copilot Studio allows 8,000 characters of agent instructions at creation but
  enforces a 2,000-character limit after deployment in some configurations (citing a Microsoft Q&A thread), and
  recommends keeping instructions to 1,000-2,000 characters. [COMMUNITY S1843]
- **Power Platform / Power Automate throttling for agent flows.** The error-codes page has no agent-flow-specific
  throttling code; its throttling family (`HTTP429TooManyRequests` for tool calls, `DataverseStructured429`,
  `DataverseFileAttachment429`, `SharePoint429` for knowledge search) documents waiting and retrying with
  (exponential) backoff, limiting concurrency for batch operations, and monitoring usage and throttling in
  analytics. The flow-specific code it does document is `FlowActionTimedOut`: a cloud flow that takes more than
  100 seconds to return to the agent. [DOC S1842]

## Reference
See `agents/agent-error-catalogue.csv` for the normalized tool/error/cause/avoidance table (49 rows after this
deepening pass). See `claude/messages-api.md` for the Messages API request/response shape (tool_use/tool_result
pairing, stop_reason values including pause_turn/refusal/model_context_window_exceeded), and Batches/Files API and
rate-limit numbers (`claude/api-limits.csv`), which this article's HTTP-error/limits facts extend rather than
duplicate.

### Checklist: keeping a project inside documented limits

A `CLAUDE.md` at the repository root should be measured directly against the ~40 KB community-reported
Claude Code warning threshold (see `agents/instruction-and-context-limits.md`, which flags that figure as
COMMUNITY pending an official-docs confirmation); a file well under that line needs no action. Any `SKILL.md`
should be checked against Claude Code's own documented tip of staying under 500 lines, with detail moved into a
`scripts/` directory or separate files the skill reads on demand, matching Claude Code's progressive-disclosure
guidance [DOC S1860].

Checklist, each line cited:
1. Keep each `CLAUDE.md` under about 200 lines: Claude Code warns at startup and in `/status` when an instruction
   file is over the recommended length or several files add up past a combined limit, and skips a file over 4 MiB;
   move path-specific instructions into `.claude/rules/` (imports still load at launch). The "~40 KB" figure is not
   Anthropic's — [DOC S1863].
2. Keep every `SKILL.md`'s `description` + `when_to_use` combined text under 1,536 characters, front-loading the
   trigger words, since Claude Code truncates silently past that point in the skill listing — [DOC S1860].
3. If a skill must stay portable to non-Claude-Code tools, keep its `description` under 1,024 characters, the
   narrower cap reported for the general Agent Skills spec — [COMMUNITY S1850].
4. Keep any `SKILL.md` body under roughly 500 lines; push detail into files the skill reads on demand — [DOC S1860].
5. Keep MCP tool names (the `mcp__<server>__<tool>` spelling) under 128 characters — a long server
   name plus a long tool name can combine to breach this — [COMMUNITY S1857].
6. Do not assume every tool's full JSON Schema/description needs to load up front once an MCP surface grows past
   a handful of tools; Claude Code defers MCP tool definitions by default (tool search) — [DOC S1862].
7. Treat a 429 from the Claude Code workspace spend cap as non-retryable (no `retry-after`), distinct from an
   ordinary rate-limit 429 — relevant if a project's own CI job ever calls the API directly — [DOC S1847].
8. In multi-turn sessions (long agentic runs), watch for `tool_use`/`tool_result` pairing errors when history is
   rebuilt, for example after an interrupted session is resumed; do not edit assistant/tool history manually, and
   start a fresh session if a resumed one keeps failing — [COMMUNITY S1858].

## Examples
Not applicable to this topic (it concerns a project's own tooling files, not device data).
