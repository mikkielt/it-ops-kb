---
topic: mcp/deprecations
priority: P1
applies_to: "MCP specification 2026-07-28; MCP Python SDK 2.2.0"
retrieved_utc: 2026-09-25
sources: [S701, S702, S727]
status: complete
---
# Deprecations and removals in 2026-07-28

## Summary
2026-07-28 introduces a feature lifecycle (Active, Deprecated, Removed; minimum 12-month window). Deprecated:
Roots, Sampling, Logging, Dynamic Client Registration, HTTP+SSE transport, `includeContext` thisServer/allServers.
Removed outright: `initialize` handshake, sessions, `ping`, `logging/setLevel`, `notifications/roots/list_changed`,
`resources/subscribe`/`unsubscribe`, SSE resumability, `notifications/elicitation/complete`.

## Facts
- Lifecycle policy SEP-2596: Active, Deprecated, Removed; minimum twelve-month deprecation window. [DOC S701]
- Nothing has been removed under the policy yet (Removed section empty). [DOC S702]
- Python SDK: deprecated features warn with `MCPDeprecationWarning` (a `UserWarning` subclass) and still work on legacy sessions; `ping` raises "Method not found" on modern connections. [DOC S727]

## Reference
| Feature | Deprecated in | Replacement | Earliest removal |
|---|---|---|---|
| Roots | 2026-07-28 | tool params, resource URIs, server config | first revision on/after 2027-07-28 |
| Sampling | 2026-07-28 | call LLM provider APIs directly | first revision on/after 2027-07-28 |
| Logging | 2026-07-28 | stderr (stdio) / OpenTelemetry | first revision on/after 2027-07-28 |
| Dynamic Client Registration | 2026-07-28 | Client ID Metadata Documents | first revision on/after 2027-07-28 |
| includeContext thisServer/allServers | 2025-11-25 | omit or "none" | follows Sampling |
| HTTP+SSE transport | 2025-03-26 | Streamable HTTP | three months after SEP-2596 Final |

Removed (not deprecated) in 2026-07-28 [DOC S701]: initialize/initialized handshake; `Mcp-Session-Id`; `ping`;
`logging/setLevel`; `notifications/roots/list_changed`; HTTP GET endpoint and `resources/subscribe`/`unsubscribe`
(replaced by `subscriptions/listen`); SSE `Last-Event-ID` resumability; `notifications/elicitation/complete` and URL `elicitationId`;
core `tasks/*` (moved to extension).

See mcp/resources-prompts.md for the current logging RPC shape (still specified, deprecated) and for `subscriptions/listen`, the replacement for the removed `resources/subscribe`/`unsubscribe` and HTTP GET endpoint.

## Examples
A stdio server following the Logging migration path writes diagnostics to stderr instead of `notifications/message`. [DER S702: Logging row migration = stderr for stdio]
