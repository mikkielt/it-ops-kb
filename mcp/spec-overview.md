---
topic: mcp/spec-overview
priority: P1
applies_to: "MCP specification 2026-07-28"
retrieved_utc: 2026-09-23
sources: [S700, S701, S703, S704, S717, S719, S711]
status: complete
---
# MCP specification 2026-07-28: overview

## Summary
Revision 2026-07-28 exists and is marked "latest" in the docs navigation; revisions present in the repository are
2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28 and draft. 2026-07-28 makes MCP stateless: no `initialize`
handshake, no protocol sessions, per-request `_meta` carries version and capabilities, servers must implement
`server/discover`, and server-to-client requests are replaced by Multi Round-Trip Requests (MRTR).

## Facts
- Spec directories present: 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28, draft; docs.json labels "Version 2026-07-28 (latest)". [DOC S719]
- The authoritative protocol requirements are based on the TypeScript schema `schema/2026-07-28/schema.ts`; it declares `LATEST_PROTOCOL_VERSION = "2026-07-28"`. [DOC S700]
- Licence: new code and specification contributions are Apache-2.0; unrelicensed earlier contributions remain MIT; documentation (excluding specifications) is CC-BY-4.0. [DOC S717]
- The `initialize`/`notifications/initialized` handshake is removed; every request carries `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities` in `_meta` (both required). [DOC S701]
- A request missing a required `_meta` field is malformed; server must reject with `-32602` (HTTP: 400). [DOC S704]
- Clients SHOULD send `io.modelcontextprotocol/clientInfo`; servers SHOULD put `io.modelcontextprotocol/serverInfo` in each result `_meta`; both are self-reported and SHOULD NOT be used for security decisions. [DOC S704]
- Servers MUST implement `server/discover`; clients MAY call it first; version mismatch returns `UnsupportedProtocolVersionError` (`-32022`) listing supported versions. [DOC S703]
- A server MUST NOT rely on undeclared client capabilities; it returns `MissingRequiredClientCapabilityError` (`-32021`). [DOC S704]
- Protocol-level sessions and the `Mcp-Session-Id` header are removed; cross-call state uses server-minted handles passed as tool arguments. [DOC S701]
- `ping`, `logging/setLevel` and `notifications/roots/list_changed` are removed; log level is set per request via `io.modelcontextprotocol/logLevel`. [DOC S701]
- All results carry `resultType` (`"complete"` or `"input_required"`); clients MUST treat results from earlier servers without the field as `"complete"`. [DOC S701]
- `traceparent`, `tracestate`, `baggage` are reserved `_meta` keys for OpenTelemetry context propagation (W3C formats). [DOC S704]
- Error-code policy: `-32000..-32019` implementation-defined, `-32020..-32099` reserved for the MCP specification. [DOC S701]
- Eras: "legacy" = handshake revisions (2025-11-25 and earlier); "modern" = 2026-07-28 and later; "dual-era" implementations support both. A dual-era server selects legacy semantics when the client opens with `initialize`. [DOC S703]
- Extensions are negotiated through an `extensions` map in client/server capabilities; identifiers need a vendor prefix; official ones use `io.modelcontextprotocol/`. [DOC S703]
- Spec security principles: hosts must obtain explicit user consent before invoking any tool; tool annotations are untrusted unless from a trusted server. [DOC S700]

## Reference
| Reserved `_meta` key | Required on request | Purpose |
|---|---|---|
| io.modelcontextprotocol/protocolVersion | yes | protocol version |
| io.modelcontextprotocol/clientCapabilities | yes | capabilities for this request |
| io.modelcontextprotocol/clientInfo | no (SHOULD) | client name/version |
| io.modelcontextprotocol/logLevel | no | per-request log level |
| io.modelcontextprotocol/subscriptionId | n/a (notifications) | correlates subscriptions/listen notifications |
| io.modelcontextprotocol/serverInfo | result `_meta` (SHOULD) | server name/version |
| progressToken | no | opt in to progress |

## Examples
A 2026-07-28 `tools/call` from a client on PL-LT-00123 carries in `params._meta`:
`{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{"elicitation":{"form":{}}}}`.
