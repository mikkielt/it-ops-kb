---
topic: mcp/elicitation
priority: P1
applies_to: "MCP specification 2026-07-28 (with legacy 2025-11-25 contrast); MCP Python SDK 2.2.0"
retrieved_utc: 2026-09-25
sources: [S709, S710, S701, S720, S721, S733]
status: complete
---
# Elicitation and Multi Round-Trip Requests (MRTR)

## Summary
In 2026-07-28 a server asks the user for input by returning `InputRequiredResult` (`resultType: "input_required"`)
carrying `elicitation/create` entries; the client collects answers and retries the same `tools/call` with
`inputResponses` and the echoed `requestState`. The original request terminates: nothing is pushed server-to-client.
In legacy revisions (2025-11-25 and earlier) the server sent `elicitation/create` as a live request mid-call.

## Facts
- MRTR replaces server-initiated requests (`roots/list`, `sampling/createMessage`, `elicitation/create`); servers MUST use MRTR; the old pattern is no longer supported (breaking change). [DOC S710]
- `InputRequiredResult` MAY be returned only on `prompts/get`, `resources/read`, `tools/call`. [DOC S710]
- `inputRequests` values MUST be `ElicitRequest`, `CreateMessageRequest` or `ListRootsRequest`; servers MUST include at least one of `inputRequests`/`requestState`. [DOC S710]
- `requestState` is attacker-controlled input; if it influences authorization, resource access or business logic, servers MUST integrity-protect it (HMAC/AEAD) and reject failures; SHOULD bind principal, short TTL and originating request. [DOC S710]
- Clients MUST echo `requestState` exactly, MUST use a different JSON-RPC id for the retry, and MUST NOT use it for parallel requests. [DOC S710]
- Servers MUST NOT send an inputRequest the client did not declare capability for, and MUST NOT assume the client will fulfil or retry. [DOC S710]
- Client capability: `elicitation: {form:{}, url:{}}` in `_meta` clientCapabilities; empty `{}` means form only. [DOC S709]
- Modes: `form` (flat object of primitive fields: string with formats email/uri/date/date-time, number/integer, boolean, single/multi-select enum) and `url` (out-of-band). [DOC S709]
- Servers MUST NOT use form mode for passwords, API keys, tokens or payment credentials; MUST use URL mode for them. [DOC S709]
- Clients MUST show which server is asking, provide decline and cancel, and let users review/modify form responses before sending. [DOC S709]
- Response actions: `accept` (with `content` for form), `decline`, `cancel`. [DOC S709]
- URL mode `accept` means consent to open the URL, not completion; `notifications/elicitation/complete` and `elicitationId` (added 2025-11-25) were removed in 2026-07-28. [DOC S701]
- Clients MUST NOT pre-fetch or open a URL without consent, MUST show the full URL. [DOC S709]
- Python SDK: `ctx.elicit()` / `ctx.elicit_url()` are server-to-client requests that exist only on legacy connections (2025-11-25 or earlier); on a 2026-07-28 connection they fail. [DOC S720]
- Python SDK: a parameter `Annotated[T, Resolve(fn)]` whose resolver returns `Elicit(...)` works on every connection: live `elicitation/create` on legacy, `InputRequiredResult` on 2026-07-28. [DOC S720]
- Python SDK: elicitation schemas must be flat primitive fields; a nested model makes `ctx.elicit` raise before sending. [DOC S720]
- Python SDK: if the client registered no elicitation capability, the call fails with protocol error "Elicitation not supported" (not a decline). [DOC S720]
- Python SDK: `MCPServer` seals `requestState` by default with a process-local key (default TTL 600 s); multi-instance deployments pass `RequestStateSecurity(keys=[...])`. [DOC S721]

## Reference
| Era | How a tool asks mid-call | Python SDK API |
|---|---|---|
| Legacy (<= 2025-11-25) | server sends `elicitation/create` request, tool awaits answer | `ctx.elicit()`, `ctx.elicit_url()`, or `Resolve(...)` |
| Modern (2026-07-28) | tool returns `InputRequiredResult`; client retries call | `Resolve(...)`/`Elicit`, or return `InputRequiredResult` |

## Examples
A confirmation for `client.refresh_policy` on PL-LT-00123 could be a form schema `{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}` (pattern of S733).
