---
topic: agents/genai-telemetry
priority: P2
applies_to: "open-telemetry/semantic-conventions-genai @ e57c543b4889619eb2a05702471937db5119165d (2026-09-24)"
retrieved_utc: 2026-09-26
sources: [S2000, S2001, S2002, S2003, S2004]
status: complete
---

# OpenTelemetry GenAI semantic conventions for agents, tools and MCP

## Summary
GenAI semantic conventions moved from `open-telemetry/semantic-conventions` into a dedicated repository,
`open-telemetry/semantic-conventions-genai` (Apache-2.0); this does not affect the general logs/code conventions
already cited in `logs/`. All agent, tool and MCP conventions here are status "Development" (pre-stable). This
file extends, and does not repeat, `claude/otel-monitoring.md`, which documents Claude Code's own proprietary
`claude_code.*` events rather than these vendor-neutral `gen_ai.*`/`mcp.*` attributes.

## Facts
- Repository split: GenAI spans/metrics/events, including MCP-specific conventions, now live in
  `open-telemetry/semantic-conventions-genai`; the old repo's GenAI pages carry a "moved" notice. [DOC S2000, S2001]
- Agent spans (span kind CLIENT unless noted): `create_agent` — name `"create_agent {gen_ai.agent.name}"`; required
  `gen_ai.operation.name=create_agent`, `gen_ai.provider.name`; conditionally required `gen_ai.agent.name`,
  `.id`, `.description`, `.version`, `error.type`, and `server.port` when `server.address` is set; recommended `server.address`. `invoke_agent` —
  name `"invoke_agent {gen_ai.agent.name}"` (or bare `"invoke_agent"`); CLIENT variant requires `gen_ai.provider.name`
  and adds `gen_ai.conversation.id`, token-usage counts, `gen_ai.response.finish_reasons`; an INTERNAL-span variant
  exists for a purely in-process invocation and drops the provider-name requirement. [DOC S2002]
- Tool-call span: `execute_tool`, span kind INTERNAL, name `"execute_tool {gen_ai.tool.name}"`; required
  `gen_ai.operation.name=execute_tool` and `gen_ai.tool.name`; conditionally required `error.type` (on failure);
  recommended when available `gen_ai.tool.call.id`, `gen_ai.tool.description` and `gen_ai.tool.type`. [DOC
  S2004]
- MCP conventions: `mcp.method.name` (required; e.g. `tools/call`, `initialize`, `prompts/list`),
  `mcp.protocol.version` (recommended; e.g. `2025-06-18`), `mcp.session.id` (recommended), `mcp.resource.uri`
  (conditional). Span kinds `mcp.client` (CLIENT, outbound) and `mcp.server` (SERVER, inbound); name pattern
  `"{mcp.method.name} {target}"`. `network.transport`: stdio → `"pipe"`; Streamable HTTP → `"tcp"`/`"quic"` with
  `network.protocol.name="http"`; a custom WebSocket transport → `"tcp"` with `network.protocol.name="websocket"`.
  Four Development-status histogram metrics: `mcp.client.operation.duration`, `mcp.server.operation.duration`,
  `mcp.client.session.duration`, `mcp.server.session.duration`. [DOC S2003]
- No documented off-the-shelf Python instrumentation package auto-emits these MCP/GenAI spans as of this fetch; a
  Python MCP server would set the attributes above manually around its `tools/call`/`initialize` handlers. [DER
  S2003, S2004: inferred from the attribute registry, no how-to guide found — recorded as a minor gap]

## Reference
| Span/metric | Kind | Status | Key attributes |
|---|---|---|---|
| create_agent | CLIENT | Development | gen_ai.operation.name, gen_ai.provider.name, gen_ai.agent.* |
| invoke_agent (client) | CLIENT | Development | + gen_ai.conversation.id, usage tokens, finish_reasons |
| invoke_agent (internal) | INTERNAL | Development | as above minus provider.name requirement |
| execute_tool | INTERNAL | Development | gen_ai.tool.name/.type/.call.id/.description |
| mcp.client / mcp.server | CLIENT / SERVER | Development | mcp.method.name, .protocol.version, .session.id |
| mcp.*.operation.duration, mcp.*.session.duration | (histogram) | Development | — |

## Examples
A Python stdio MCP server handling `tools/call` for a `device.recheck`-style operation on an example device
`PL-LT-00123` could open an `mcp.server` span named `"tools/call device.recheck"` with `mcp.method.name=tools/call`,
`mcp.protocol.version=2025-06-18`, and nest an `execute_tool` INTERNAL span with `gen_ai.tool.name=device.recheck`,
`gen_ai.tool.type=function`, distinct from whatever `claude_code.tool_result` event the calling Claude Code session
emits on its own side (`claude/otel-monitoring.md`) — the two telemetry vocabularies are complementary, not
overlapping [DER S2003, S2004].

### Sensitive-data-declaration tension
A "secrets declared and redacted at every sink" policy would need to cover any OTel exporter path exactly as it
already covers CLI/MCP output and logs, since `mcp.resource.uri` or a tool's arguments could carry a device name or
other classified value if a server sets span attributes directly from tool input.
