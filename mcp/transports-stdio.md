---
topic: mcp/transports-stdio
priority: P1
applies_to: "MCP specification 2026-07-28; MCP Python SDK 2.2.0"
retrieved_utc: 2026-09-23
sources: [S705, S706, S703, S707, S724, S735]
status: complete
---
# stdio transport (2026-07-28)

## Summary
The client launches the server as a subprocess; newline-delimited JSON-RPC over stdin/stdout; stderr for logs.
In 2026-07-28 the server MUST NOT write JSON-RPC requests to stdout: server-to-client interaction travels inside
`InputRequiredResult` replies (MRTR). Legacy-era sessions (initialize handshake) keep the older bidirectional model.

## Facts
- Server reads JSON-RPC from stdin and writes to stdout; messages are newline-delimited and MUST NOT contain embedded newlines. [DOC S705]
- Server MAY write UTF-8 to stderr for logging; client SHOULD NOT assume stderr output indicates errors. [DOC S705]
- Server MUST NOT write anything to stdout that is not a valid MCP message. [DOC S705]
- Client MUST NOT write JSON-RPC responses; server MUST NOT write JSON-RPC requests to stdout (2026-07-28). [DOC S705]
- All request metadata is inline in the JSON-RPC body `_meta`; there is no header layer on stdio. [DOC S705]
- Cancellation: client sends `notifications/cancelled`; server SHOULD stop and MUST NOT send further messages for that request. [DOC S705]
- Shutdown: client closes stdin, waits, then force-terminates (Windows: `TerminateProcess` or Job Objects); server SHOULD exit on stdin EOF. [DOC S705]
- On unexpected exit the client SHOULD restart the server; in-flight requests are lost and may be retried. [DOC S705]
- Backward compatibility: a dual-era client SHOULD probe with `server/discover`; any non-modern error or timeout means a legacy server, and the fallback MUST NOT be keyed to one error code. [DOC S705]
- Authorization spec: stdio implementations SHOULD NOT follow the HTTP authorization spec and instead retrieve credentials from the environment. [DOC S707]
- Python SDK: `mcp.run()` with no argument uses stdio; while serving, the SDK diverts flushed stdout writes to stderr; use `logging` for output. [DOC S724]
- Python SDK low-level `Server.run` uses `serve_dual_era_loop`, i.e. the stdio server answers both `initialize` (legacy) and modern requests. [DOC S735]

## Reference
| Message kind on stdout (server) | Allowed in 2026-07-28 |
|---|---|
| Responses (by id) | yes |
| Request-scoped notifications (`notifications/progress`, `notifications/message`) | yes |
| Notifications for an active `subscriptions/listen` (with subscriptionId) | yes |
| JSON-RPC requests | no |

## Examples
Claude Code on PL-LT-00123 starts an MCP server as a child process; the server logs to stderr only.
