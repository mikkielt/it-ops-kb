---
topic: claude/otel-monitoring
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23)"
retrieved_utc: 2026-09-26
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
