---
topic: claude/otel-monitoring
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23; metrics and correlation read 2026-09-29)"
retrieved_utc: 2026-09-29
sources: [S744, S745, S741, S743]
status: complete
---
# OpenTelemetry monitoring events (MCP-relevant)

## Summary
Enable with `CLAUDE_CODE_ENABLE_TELEMETRY=1` plus OTLP exporter variables. MCP activity appears in
`claude_code.mcp_server_connection`, `claude_code.tool_result` and `claude_code.tool_decision` events. Without
`OTEL_LOG_TOOL_DETAILS=1`, user-configured MCP tools appear as `tool_name = "mcp_tool"` with no server/tool names or arguments.

## Facts
- Enable: `CLAUDE_CODE_ENABLE_TELEMETRY=1`; `OTEL_METRICS_EXPORTER` (otlp, prometheus, console, none); `OTEL_LOGS_EXPORTER` (otlp, console, none); `OTEL_EXPORTER_OTLP_PROTOCOL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`. [DOC S744]
- `claude_code.tool_result`: `tool_name`, `tool_use_id` (matches hook `tool_use_id`), `success`, `duration_ms`, `error_type`, `decision_type`, `decision_source` (config/hook/user_permanent/user_temporary), `tool_input_size_bytes`, `tool_result_size_bytes`, `mcp_server_scope`; with details flag: `error`, `tool_parameters` (`mcp_server_name`, `mcp_tool_name`), `tool_input` (values >512 chars truncated, ~4K total). [DOC S744]
- `claude_code.tool_decision`: `decision` (accept/reject), `tool_source` (builtin/mcp/sdk_host_builtin_mcp), `source` (config, hook, user_permanent, user_temporary, user_abort, user_reject); `tool_parameters` with details flag. [DOC S744]
- `claude_code.mcp_server_connection`: `status` (connected/failed/disconnected), `transport_type`, `server_scope`, `duration_ms`, `error_code`, `is_plugin`; `server_name` and `error` only with `OTEL_LOG_TOOL_DETAILS=1`. [DOC S744]
- Without `OTEL_LOG_TOOL_DETAILS`, user-configured MCP tools are redacted to `tool_name = "mcp_tool"` and argument content is omitted. [DOC S744]
- `OTEL_LOG_TOOL_CONTENT=1` includes tool content in the `tool.output` span event (tracing beta). [DOC S745]
- `OTEL_LOG_USER_PROMPTS=1` includes prompt text (redacted by default). [DOC S745]
- `claude_code.user_prompt` is logged when a user submits a prompt, with `prompt_length`, `prompt` (redacted unless `OTEL_LOG_USER_PROMPTS=1`) and `message.uuid` (the transcript entry; v2.1.214+). [DOC S744]
- `prompt.id` (UUID v4) links every event produced while processing one user prompt: filtering on it returns the `user_prompt` event, its `api_request` events and its `tool_result` events. The same id reaches hooks as the `prompt_id` input field (`claude/hooks.md`). [DOC S744, S743]
- `claude_code.token.usage` (unit tokens) and `claude_code.cost.usage` (unit USD) are counters incremented after each API request; both carry all standard attributes (including `session.id`, on by default and switched off with `OTEL_METRICS_INCLUDE_SESSION_ID=false`) plus `model`, `query_source`, `speed`, `effort` and `agent.name`, `skill.name`, `plugin.name`, `marketplace.name`, `mcp_server.name`, `mcp_tool.name`; `token.usage` adds `type` with the values `input`, `output`, `cacheRead` and `cacheCreation`. [DOC S744]
- On the metrics, `query_source` is one of `main`, `subagent` or `auxiliary`, and the `subagent` category also counts requests from agent-based hooks; `agent.name` is absent when no named subagent type issued the request, and `agent.name`, `skill.name` and `plugin.name` show a redacted `custom` or `third-party` placeholder unless `OTEL_LOG_TOOL_DETAILS=1`. [DOC S744]
- The docs say to roll subagent tokens and cost up from the token and cost counters filtered to `query_source` `subagent`, because `claude_code.subagent_completed` has `total_tokens` for only the subagent's final API request (its context size at completion, not a sum), alongside `agent_type`, `total_tool_uses`, `duration_ms`, `is_async`, `model` and `agent.source`. [DOC S744]
- `claude_code.api_request` (one event per API request) carries `model`, `cost_usd`, `cost_usd_micros`, `duration_ms`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `request_id`, `client_request_id`, `speed`, `effort`, `query_source` (there `repl_main_thread`, `compact` or a subagent name, not the metric's three values) and the same `agent.name`/`skill.name`/`plugin.name` attribution; events, unlike metrics, also carry `prompt.id`, so cost per prompt comes from events and cost per session from either. [DOC S744]
- Event correlation keys that match the session transcript: `message.uuid` (the transcript entry; on `user_prompt`, `assistant_response`, `api_response_body`), `request_id` (persisted as `requestId` on the transcript's assistant entries) and `tool_use_id`; the docs call these joins version-specific because the transcript entry format is internal and changes between versions. `event.sequence` is a per-process counter, so within a resumed session it can repeat or go backwards and events sort by `event.timestamp` first. [DOC S744]
- Each streaming response counts toward the cost and token metrics once, including gateways that stream usage over several frames; before v2.1.214 such streams inflated both counters by about one extra request per extra frame. [DOC S744]
- Admin monitoring guidance: set `OTEL_LOG_TOOL_DETAILS=1` to see which MCP servers and tools users invoke. [DOC S741]
- PostToolUse `updatedToolOutput` does not affect telemetry, which captures the original output. [DOC S743]

## Reference
| Event | Key MCP attributes | Needs OTEL_LOG_TOOL_DETAILS |
|---|---|---|
| mcp_server_connection | status, transport_type, server_scope | server_name, error |
| tool_decision | decision, source, tool_source | mcp_server_name, mcp_tool_name |
| tool_result | success, duration_ms, mcp_server_scope, sizes | tool_parameters, tool_input, error |

## Examples
`CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_LOGS_EXPORTER=otlp OTEL_EXPORTER_OTLP_ENDPOINT=http://otel.corp.example.com:4317`
