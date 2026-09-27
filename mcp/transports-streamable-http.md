---
topic: mcp/transports-streamable-http
priority: P2
applies_to: "MCP specification 2026-07-28"
retrieved_utc: 2026-09-26
sources: [S-l4qgsnr4, S706, S703, S-ssijfmsu, S-gm6b6ci6, S704, S716, S707]
status: complete
---
# Streamable HTTP transport (2026-07-28)

## Summary
A single MCP endpoint accepts POST for every JSON-RPC message; the server replies with a JSON object or a
request-scoped SSE stream. 2026-07-28 removes the GET stream endpoint and protocol-level sessions (no
`Mcp-Session-Id`): cross-call state moves to server-minted handles in tool arguments (see mcp/spec-overview.md).
Selected `_meta` fields are mirrored into headers (`MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`,
`Mcp-Param-*`) so intermediaries can route without parsing the body; mismatches are rejected. Cancellation is an
SSE-stream close, not a notification; progress and version negotiation are unchanged from the base protocol
patterns.

## Facts
- The server MUST provide a single HTTP endpoint (the MCP endpoint) supporting POST, e.g. `https://example.com/mcp`. [DOC S-l4qgsnr4]
- The client MUST use POST, MUST include an `Accept` header listing both `application/json` and `text/event-stream`, and MUST NOT send JSON-RPC responses. [DOC S-l4qgsnr4]
- A notification POST the server accepts gets `202 Accepted` with no body; one it cannot accept gets an HTTP error status (e.g. `400`). [DOC S-l4qgsnr4]
- A request POST gets back `Content-Type: application/json` (single object) or `text/event-stream` (SSE); the client MUST support both. [DOC S-l4qgsnr4]
- Removed in 2026-07-28: the GET stream endpoint and protocol-level sessions; a server receiving GET or DELETE on the MCP endpoint SHOULD respond `405 Method Not Allowed`, and SHOULD ignore any `Mcp-Session-Id` header rather than mint or echo one. [DOC S-l4qgsnr4]
- Resumable SSE streams via `Last-Event-ID` are not supported in this revision; a server SHOULD ignore a `Last-Event-ID` header. [DOC S-l4qgsnr4]
- On the response SSE stream the server MAY send request-scoped notifications (`notifications/progress`, `notifications/message`) before the final response, but MUST NOT send independent JSON-RPC requests; server-to-client interactions (sampling, elicitation, roots) travel as `InputRequiredResult` per MRTR instead. [DOC S-l4qgsnr4]
- Long-lived change notifications (list-changed, resource updates) are obtained by a `subscriptions/listen` request; its own SSE response stream stays open and carries only the notification types the client opted into. [DOC S-l4qgsnr4]
- Servers SHOULD send `X-Accel-Buffering: no` when opening an SSE stream so reverse proxies (e.g. nginx) do not buffer events. [DOC S-l4qgsnr4]
- For long-lived streams, especially `subscriptions/listen`, servers are encouraged to periodically emit an SSE comment line (`:\r\n`) as a keep-alive; clients must ignore such lines (a non-normative note citing the SSE specification). [DOC S-l4qgsnr4]
- Servers MUST validate the `Origin` header on every connection to prevent DNS rebinding; an invalid `Origin` MUST get `403 Forbidden`. [DOC S-l4qgsnr4]
- When running locally, servers SHOULD bind only to `127.0.0.1`, not `0.0.0.0`; servers SHOULD implement proper authentication for all connections. [DOC S-l4qgsnr4]
- Every POST to the MCP endpoint MUST include an `MCP-Protocol-Version` header, whose value MUST match `_meta.io.modelcontextprotocol/protocolVersion` in the body; a mismatch is `400 Bad Request` with a `HeaderMismatch` JSON-RPC error. [DOC S-l4qgsnr4]
- If the server does not implement the requested protocol version it MUST return `400 Bad Request` with `UnsupportedProtocolVersionError` listing its supported versions; an unimplemented RPC method gets `404 Not Found` with JSON-RPC `-32601`. [DOC S-l4qgsnr4]
- A server supporting pre-`2025-06-18` clients (no `MCP-Protocol-Version` header defined then) MAY treat a header-less request as protocol version `2025-03-26`; a server that does not MUST reject a header-less request. [DOC S-l4qgsnr4]
- Standard request headers mirrored from the body: `Mcp-Method` (from `method`, required on all requests) and `Mcp-Name` (from `params.name`/`params.uri`, required for `tools/call`, `resources/read`, `prompts/get`). [DOC S-l4qgsnr4]
- Servers MAY mark tool `inputSchema` properties with `x-mcp-header` so their values are mirrored into `Mcp-Param-{Name}` headers; clients MUST support this even though server use is optional. [DOC S-l4qgsnr4]
- A header value that is not plain ASCII (0x21-0x7E, space, tab) MUST be Base64-encoded as `=?base64?{value}?=`; a plain value matching that sentinel pattern MUST also be encoded to avoid ambiguity. [DOC S-l4qgsnr4]
- Servers MUST reject requests where a header value does not match the corresponding body value, returning `400 Bad Request` with JSON-RPC error `-32020` (`HeaderMismatch`); intermediaries not enforcing header-body validation SHOULD reject when `MCP-Protocol-Version` is old or absent rather than trust unvalidated headers. [DOC S-l4qgsnr4]
- Header names are case-insensitive (RFC 9110); header values (e.g. method names) are case-sensitive. [DOC S-l4qgsnr4]
- A dual-era client detects a legacy server by attempting a modern request first: a recognized modern JSON-RPC error in the `400` body means a modern server (retry with a supported version); an empty or unrecognized body means fall back to `initialize`. [DOC S-l4qgsnr4]
- 2025-03-26 through 2025-11-25 Streamable HTTP used `Mcp-Session-Id` (session via HTTP DELETE), GET for a standalone SSE stream, server-sent requests on SSE, and `Last-Event-ID` resumability; none of these are part of 2026-07-28. [DOC S-l4qgsnr4]
- The 2024-11-05 HTTP+SSE transport is Deprecated since 2025-03-26 and eligible for removal in a future revision; new implementations SHOULD NOT adopt it. [DOC S-l4qgsnr4]
- Cancellation: closing the SSE response stream MUST be treated by the server as cancellation of that request (unambiguous because each request has its own stream); the server SHOULD stop work and MUST NOT send further messages for it. [DOC S-l4qgsnr4]
- This revision defines no client-to-server notifications over Streamable HTTP; `notifications/cancelled` is used only on stdio, not HTTP. [DOC S-l4qgsnr4]
- Cancellation notification body (stdio, and any transport that still uses it): `{"method":"notifications/cancelled","params":{"requestId":"123","reason":"..."}}`; a server MUST send `notifications/cancelled` only when tearing down a `subscriptions/listen` stream. [DOC S-ssijfmsu]
- Implementations SHOULD set per-request timeouts and, on timeout, cancel the request (close the stream on HTTP, send `notifications/cancelled` on stdio); implementations MAY reset the timeout clock on a progress notification but SHOULD still enforce a maximum timeout regardless. [DOC S-ssijfmsu]
- A server MAY ignore a cancellation for a request that is unknown, already completed, or not cancellable; the client SHOULD ignore any late response to a cancelled request. [DOC S-ssijfmsu]
- Progress: a client opts in by placing a string/integer `progressToken` (unique across active requests) in `params._meta`; the server MAY send `notifications/progress` with `progressToken`, `progress`, optional `total` and `message`. [DOC S-gm6b6ci6]
- The `progress` value MUST increase with each notification even if `total` is unknown; `progress`/`total` MAY be floating point; a server MAY choose not to send any progress notifications for a token it was given. [DOC S-gm6b6ci6]
- Transports bind the same protocol semantics: only framing, metadata mirroring and cancellation signaling differ; stdio and Streamable HTTP are the two standard bindings, and custom transports MUST preserve JSON-RPC, the message patterns and the per-request `_meta` model. [DOC S706]
- A custom transport over a reliable bidirectional byte stream (Unix domain sockets, TCP) SHOULD reuse stdio's newline-delimited JSON-RPC framing rather than invent a new one. [DOC S706]
- Protocol version negotiation has no handshake: every request's `_meta` states the version; on HTTP it is also the `MCP-Protocol-Version` header; `UnsupportedProtocolVersionError` is `-32022` with `data.supported` and `data.requested`. [DOC S703]
- Terminology: "modern" = per-request metadata (2026-07-28+), "legacy" = `initialize`-handshake revisions (2025-11-25 and earlier), "dual-era" = supports both; era is a property of the server, cached by the client for the process (stdio) or origin (HTTP) lifetime. [DOC S703]
- Compatibility matrix highlight: Legacy client vs Modern server fails (HTTP: request missing required headers, rejected `400`); Dual-era client vs Legacy server works by falling back to `initialize` after a `4xx` with no recognized modern error body. [DOC S703]
- Authorization for Streamable HTTP SHOULD conform to the MCP authorization spec (OAuth 2.1 subset); see mcp/authorization.md. [DOC S704, S707]
- Streamable HTTP security controls (Origin validation, localhost binding) sit alongside the broader guidance in mcp/security-best-practices.md (SSRF blocking of private IP ranges, state-handle binding, local-server consent). [DOC S716]

## Reference
See mcp/spec-overview.md for the per-request `_meta` fields (`io.modelcontextprotocol/protocolVersion`,
`clientCapabilities`, etc.) that every Streamable HTTP POST body carries, and for the removal of protocol-level
sessions and `Mcp-Session-Id` (mcp/spec-overview.md:27). See mcp/transports-stdio.md for the stdio binding
(newline-delimited JSON-RPC, no headers, `notifications/cancelled` for cancellation) that Streamable HTTP replaces
`Mcp-Session-Id`/GET-stream mechanics for. See mcp/authorization.md for the OAuth 2.1 subset that Streamable HTTP
SHOULD implement, and mcp/security-best-practices.md for Origin/SSRF/local-server-compromise guidance that applies
to any HTTP-based MCP server.

| Removed in 2026-07-28 | Replacement |
|---|---|
| `Mcp-Session-Id` header / session | server-minted handles in tool arguments (mcp/spec-overview.md) |
| GET stream endpoint (standalone SSE) | `subscriptions/listen` POST request with its own SSE response stream |
| Server-sent JSON-RPC requests on SSE | `InputRequiredResult` via MRTR |
| `Last-Event-ID` resumability | not supported; streams are not resumable |

| Header | Source field | Required for |
|---|---|---|
| `MCP-Protocol-Version` | `_meta.io.modelcontextprotocol/protocolVersion` | every POST |
| `Mcp-Method` | `method` | every request |
| `Mcp-Name` | `params.name` or `params.uri` | `tools/call`, `resources/read`, `prompts/get` |
| `Mcp-Param-{Name}` | tool parameter marked `x-mcp-header` | that parameter, when present |

| Signal | Meaning |
|---|---|
| Closing the request's SSE stream (client) | cancels that request; no `notifications/cancelled` on HTTP |
| `202 Accepted`, no body | notification accepted |
| `400` + `HeaderMismatch` (`-32020`) | header does not match body, or required header missing/malformed |
| `400` + `UnsupportedProtocolVersionError` (`-32022`) | requested protocol version not supported |
| `404` + JSON-RPC `-32601` | method not found on the modern MCP endpoint |
| `405 Method Not Allowed` | GET or DELETE sent to the MCP endpoint (2026-07-28 has neither) |

## Examples
A client on PL-LT-00123 calls a tool on `https://mcp.corp.example.com/mcp`:

```http
POST /mcp HTTP/1.1
Host: mcp.corp.example.com
Content-Type: application/json
Accept: application/json, text/event-stream
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: get_weather

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": { "location": "Seattle, WA" },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientInfo": { "name": "ExampleClient", "version": "1.0.0" },
      "io.modelcontextprotocol/clientCapabilities": {}
    }
  }
}
```
The server streams progress then the result over SSE:
```
HTTP/1.1 200 OK
Content-Type: text/event-stream
X-Accel-Buffering: no

data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"abc123","progress":50,"total":100}}

data: {"jsonrpc":"2.0","id":1,"result":{"resultType":"complete","content":[{"type":"text","text":"62F, partly cloudy"}]}}
```
jan.kowalski's client cancels a slow request by closing that stream; no `notifications/cancelled` is sent because the
transport is Streamable HTTP, not stdio. [DER S-l4qgsnr4, S-ssijfmsu: HTTP cancellation is stream-close, not a notification]
