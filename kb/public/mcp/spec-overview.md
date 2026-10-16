---
topic: mcp/spec-overview
priority: P1
applies_to: "MCP specification 2026-07-28"
retrieved_utc: 2026-10-16
sources: [S700, S701, S703, S704, S717, S719, S711, S714, S-q6ob42dw, S-gxbtrq7d]
status: complete
files: [mcp/schema/2026-07-28/README.md, mcp/schema/2026-07-28/schema.ts, mcp/schema/2026-07-28/schema.json]
---
# MCP specification 2026-07-28: overview

## Summary
Revision 2026-07-28 exists and is marked "latest" in the docs navigation; revisions present in the repository are
2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28 and draft. 2026-07-28 makes MCP stateless: no `initialize`
handshake, no protocol sessions, per-request `_meta` carries version and capabilities, servers must implement
`server/discover`, and server-to-client requests are replaced by Multi Round-Trip Requests (MRTR).

## Facts
- The specification repository's GitHub release `2026-07-28` was published on 2026-07-28, after a `2026-07-28-RC` release on 2026-05-29; the previous release was `2025-11-25`. [DOC S-q6ob42dw]
- Spec directories present: 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28, draft; docs.json labels "Version 2026-07-28 (latest)". [DOC S719]
- The authoritative protocol requirements are based on the TypeScript schema `schema/2026-07-28/schema.ts`; it declares `LATEST_PROTOCOL_VERSION = "2026-07-28"`. [DOC S700, S711]
- Licence: new code and specification contributions are Apache-2.0; unrelicensed earlier contributions remain MIT; documentation (excluding specifications) is CC-BY-4.0. [DOC S717]
- The `initialize`/`notifications/initialized` handshake is removed; every request carries `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities` in `_meta` (both required). [DOC S701, S704]
- A request missing a required `_meta` field is malformed; server must reject with `-32602` (HTTP: 400). [DOC S704]
- Clients SHOULD send `io.modelcontextprotocol/clientInfo`; servers SHOULD put `io.modelcontextprotocol/serverInfo` in each result `_meta`; both are self-reported and SHOULD NOT be used for security decisions. [DOC S704]
- Servers MUST implement `server/discover`; clients MAY call it first; version mismatch returns `UnsupportedProtocolVersionError` (`-32022`) listing supported versions. [DOC S703]
- A server MUST NOT rely on undeclared client capabilities; it returns `MissingRequiredClientCapabilityError` (`-32021`). [DOC S704]
- Protocol-level sessions and the `Mcp-Session-Id` header are removed; cross-call state uses server-minted handles passed as tool arguments. [DOC S701]
- The spec's Statelessness section: a server processes each request independently and infers no state from earlier requests, even on the same connection or stream; state that spans requests (its examples: long-running tasks, application-level handles) MUST be referenced by an explicit identifier the client passes on each request. [DOC S704]
- An open connection, such as a stdio process, is not a conversation or session: clients may interleave unrelated requests on one transport, so a server must not treat connection or process identity as session continuity; a long-lived `subscriptions/listen` request keeps its state scoped to that request, not the connection. [DOC S704]
- SEP-2567 (Final, "Sessionless MCP via Explicit State Handles") says an explicit state handle is "not a new protocol construct": there is no schema, wire format or `handles/*` method, and the protocol change is the removal of sessions; from the wire a handle is a string in a tool result and a string in a tool argument. [DOC S-gxbtrq7d]
- SEP-2567 gives the pattern: an explicit creation tool (its example `create_basket()`) returns an id and later tools (`add_item(basket_id, ...)`) take it as an argument; it states the model decides what is shared and what is isolated, and that agent orchestrators can share or not share application state as needed. [DOC S-gxbtrq7d]
- SEP-2567 states the spec does not say when a session begins or ends and that "A subagent might share its parent's session or get its own — there is no convention"; clients scoped sessions per tool call, per app launch or per page load. [DOC S-gxbtrq7d]
- SEP-2567's worked case: an orchestrator spawns subagents to research products, which should share one cart but keep separate browser state; one session scope shares both or isolates both, while with explicit ids the orchestrator calls `create_basket()` once and passes the `basket_id` to each subagent, and each subagent calls `create_browser()` for its own `browser_id`. [DOC S-gxbtrq7d]
- SEP-2567 says a session gives exactly one scope per connection, whereas explicit ids give as many scopes as the model creates, each shared or isolated on its own; anything a session expresses is expressible with one id created at the start of a conversation, and the reverse does not hold. [DOC S-gxbtrq7d]
- SEP-2567 states explicit ids make state addressable from outside the creating session (resume in a new conversation, hand off to another agent, share with a colleague), and that handles in tool results persist in the chat transcript of clients that persist chats. [DOC S-gxbtrq7d]
- SEP-2567's non-normative handle guidance: opaque handles, durability policy written in the `create_*` tool's description (its example "baskets expire after 24h idle"), clear errors for an expired handle, and optional `destroy_*(handle)` and `list_*()` tools; the client duty is keeping the handle through context compaction, else the state is orphaned. [DOC S-gxbtrq7d]
- List endpoints (`tools/list`, `resources/list`, `prompts/list`) no longer vary per connection; SEP-2567 adds that, with sessions gone, a subagent can inherit its parent's cached lists at zero cost, where session-scoped servers forced `O(subagents × servers)` list calls. [DOC S701, S-gxbtrq7d]
- SEP-2567 notes that gateways using `Mcp-Session-Id` for sticky routing lose their key, and that with state keyed by a handle in the tool arguments "any replica can serve it from shared storage"; the residual case is a gateway that spawns one stdio subprocess per session. [DOC S-gxbtrq7d]
- SEP-2567 leaves open a follow-up that would mark a result field as a handle (shared JSON Schema `$defs` or a tool annotation) so orchestrators can tell live state from other values for compaction, hand-off or cleanup; no such marker exists, and the relation between `create_basket`'s output and `add_item`'s input is inferred from names and descriptions. [DOC S-gxbtrq7d]
- `ping`, `logging/setLevel` and `notifications/roots/list_changed` are removed; log level is set per request via `io.modelcontextprotocol/logLevel`. [DOC S701]
- All results carry `resultType` (`"complete"` or `"input_required"`); clients MUST treat results from earlier servers without the field as `"complete"`. [DOC S701]
- `traceparent`, `tracestate`, `baggage` are reserved `_meta` keys for OpenTelemetry context propagation (W3C formats). [DOC S704]
- Error-code policy: `-32000..-32019` implementation-defined, `-32020..-32099` reserved for the MCP specification. [DOC S701]
- Eras: "legacy" = handshake revisions (2025-11-25 and earlier); "modern" = 2026-07-28 and later; "dual-era" implementations support both. A dual-era server selects legacy semantics when the client opens with `initialize`. [DOC S703]
- Extensions are negotiated through an `extensions` map in client/server capabilities; identifiers need a vendor prefix; official ones use `io.modelcontextprotocol/`. [DOC S703, S714]
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

See mcp/resources-prompts.md for the `resources`, `prompts`, `completion` and `server/discover` RPCs that run on top of this per-request `_meta` model, and their pagination/caching/logging utilities. See mcp/transports-stdio.md and mcp/transports-streamable-http.md for how `_meta` and the removed sessions/`Mcp-Session-Id` (see line 27 above) map onto each binding.

## Examples
A 2026-07-28 `tools/call` from a client on PL-LT-00123 carries in `params._meta`:
`{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{"elicitation":{"form":{}}}}`.
