---
topic: mcp/resources-prompts
priority: P2
applies_to: "MCP specification 2026-07-28"
retrieved_utc: 2026-09-26
sources: [S-uq2hafxi, S-mjxgvchf, S-dwlcyci7, S-twgov237, S-3s4qysez, S-7uw4d77y, S-onc3gpse]
status: complete
---
# Resources, prompts, completion, discovery and their utilities (2026-07-28)

## Summary
Resources (application-driven context: files, schemas, data) and prompts (user-controlled
templates) are declared as separate capabilities and listed/read with paginated,
cacheable RPCs. Argument values for prompts and resource templates can be
auto-completed via `completion/complete`. `server/discover` (mandatory) reports a
server's supported versions, capabilities and identity before any other call. List-change
notifications and resource updates are delivered over a `subscriptions/listen` stream, not
a per-resource `subscribe` RPC. Logging is deprecated in this revision (Active/Deprecated/
Removed lifecycle, minimum 12-month window); servers should migrate to stderr (stdio) or
OpenTelemetry.

## Facts
### Resources
- Servers supporting resources MUST declare the `resources` capability; it has two independent optional sub-features, `listChanged` and `subscribe`, and may declare neither. [DOC S-uq2hafxi]
- `resources/list` MUST return the set currently available to the requesting client; the set MUST NOT vary per-connection or as a side effect of other requests, but MAY vary by the authorization on the request (credentials are per-request input). [DOC S-uq2hafxi]
- `resources/list`, `resources/templates/list` support pagination (`cursor`/`nextCursor`) and caching (`ttlMs`, `cacheScope`). [DOC S-uq2hafxi]
- `resources/read` takes `uri`; response `contents` is an array (servers MAY return multiple contents, e.g. a directory read); supports caching. [DOC S-uq2hafxi]
- `resources/read` MAY answer with `InputRequiredResult` (MRTR); retry adds `inputResponses` and echoed `requestState`. [DOC S-uq2hafxi]
- If `uri` scheme is `https://`, clients MAY fetch the resource directly from the web instead of via the server. [DOC S-uq2hafxi]
- Resource templates use RFC 6570 URI templates (`resources/templates/list`, field `uriTemplate`); template arguments may be auto-completed via the completion API. [DOC S-uq2hafxi]
- `notifications/resources/list_changed` is sent (SHOULD) when the resource list changes and the server declared `listChanged`. [DOC S-uq2hafxi]
- Subscriptions to a specific resource's updates go through `subscriptions/listen` with the URI listed in `notifications.resourceSubscriptions`; the server then delivers `notifications/resources/updated` on that stream. [DOC S-uq2hafxi]
- Resource fields: `uri`, `name`, `title?`, `description?`, `icons?`, `mimeType?`, `size?`. Contents are either `text` or base64 `blob`, each with `uri` and `mimeType`. [DOC S-uq2hafxi]
- Annotations (on resources, resource templates and content blocks): `audience` (`"user"`/`"assistant"`), `priority` (0.0-1.0, 1 = required, 0 = entirely optional), `lastModified` (ISO 8601). [DOC S-uq2hafxi]
- Standard URI schemes: `https://` (client fetches directly, servers SHOULD use it only then), `file://` (may use an XDG MIME type like `inode/directory` for non-regular files), `git://`; custom schemes MUST follow RFC 3986. [DOC S-uq2hafxi]
- Resource-not-found error: servers MUST return `-32602` (Invalid Params); MUST NOT return an empty `contents` array for a non-existent resource (ambiguous with "exists but empty"); servers SHOULD return `-32603` for internal errors; clients SHOULD also accept `-32002` for backwards compatibility with earlier protocol versions. [DOC S-uq2hafxi]
- Security: servers MUST validate all resource URIs and sanitize file paths against directory traversal for `file://`; access controls and permission checks SHOULD apply to sensitive resources; binary data MUST be properly encoded. [DOC S-uq2hafxi]

### Prompts
- Servers supporting prompts MUST declare the `prompts` capability (with optional `listChanged`) in their `DiscoverResult`. [DOC S-mjxgvchf]
- `prompts/list` MUST NOT vary per-connection or as a side effect of other requests, but MAY vary by request authorization; supports pagination and caching. [DOC S-mjxgvchf]
- `prompts/get` takes `name` and `arguments`; arguments may be auto-completed via the completion API; response has `description` and `messages` (each `role`: user/assistant, and `content`). MAY answer with `InputRequiredResult` (MRTR), same retry pattern as resources. [DOC S-mjxgvchf]
- `notifications/prompts/list_changed` is sent (SHOULD) to clients that opened a `subscriptions/listen` stream with `promptsListChanged: true`. [DOC S-mjxgvchf]
- Prompt content types: text, image (base64 + MIME type), audio (base64 + MIME type), `resource_link` (URI reference, not embedded), and embedded `resource` (text or base64 blob, with URI and MIME type required). All content types support the same annotations as resources. [DOC S-mjxgvchf]
- Prompt error handling: invalid name or missing required arguments both use `-32602`; internal errors `-32603`. [DOC S-mjxgvchf]

### Completion
- Servers supporting completions MUST declare the `completions` capability. [DOC S-twgov237]
- `completion/complete` params: `ref` (`{"type":"ref/prompt","name":...}` or `{"type":"ref/resource","uri":...}`, the latter for a resource URI or URI template), `argument` (`name`, `value`), and optional `context.arguments` (already-resolved argument name/value pairs, for prompts or URI templates with multiple arguments). [DOC S-twgov237]
- `CompleteResult.completion`: `values` (max 100 items, ranked by relevance), optional `total`, boolean `hasMore`. [DOC S-twgov237]
- Completion error handling: method not found `-32601` (capability not supported), invalid prompt name or missing arguments `-32602`, internal errors `-32603`. [DOC S-twgov237]
- Servers SHOULD rate-limit completion requests and sort by relevance; clients SHOULD debounce rapid requests. [DOC S-twgov237]

### Discovery (server/discover)
- `server/discover` lets a client query supported protocol versions, capabilities and identity before any other request; servers MUST implement it. The request carries no body beyond the standard `_meta`. [DOC S-dwlcyci7]
- `DiscoverResult` fields: `supportedVersions` (array, client picks one), `capabilities`, `_meta['io.modelcontextprotocol/serverInfo']` (name/version, servers SHOULD include it), `instructions` (optional natural-language guidance for LLMs). Response supports caching (`ttlMs`, `cacheScope`). [DOC S-dwlcyci7]
- Calling `server/discover` is optional for clients — any RPC can be invoked inline, handling `UnsupportedProtocolVersionError` if unsupported. It is useful to get identity/capabilities/versions in one call instead of probing `tools/list`/`prompts/list`/`resources/list` separately, and as a stdio backward-compatibility probe: since stdio has no per-request HTTP status to drive fallback, a client supporting both modern and legacy (`initialize`-handshake) servers SHOULD send `server/discover` first. [DOC S-dwlcyci7]
- `serverInfo` is self-reported and not verified by the protocol; clients SHOULD NOT change behavior based on it or rely on it for security decisions. [DOC S-dwlcyci7]

### Pagination
- Cursor-based, not numbered pages: the cursor is an opaque string token; page size is server-determined and clients MUST NOT assume a fixed size. [DOC S-7uw4d77y]
- Operations supporting pagination: `resources/list`, `resources/templates/list`, `prompts/list`, `tools/list`. [DOC S-7uw4d77y]
- Response carries `nextCursor` when more results exist; clients SHOULD treat a missing `nextCursor` as end of results, and support both paginated and non-paginated flows. [DOC S-7uw4d77y]
- Clients MUST treat cursors as opaque: never parse or modify them, and never infer end-of-results from the cursor's value beyond whether it is non-null — an empty string is a valid cursor and MUST NOT be treated as end of results. [DOC S-7uw4d77y]
- Invalid cursor: error `-32602` (Invalid params). [DOC S-7uw4d77y]

### Logging (deprecated)
- Logging is Deprecated as of 2026-07-28 (SEP-2577); under the feature lifecycle policy it remains specified for at least 12 months after this revision before removal is eligible. New implementations SHOULD NOT adopt it; existing ones SHOULD migrate to stderr logging (stdio transports) or OpenTelemetry (structured observability). [DOC S-3s4qysez]
- Servers emitting log notifications MUST declare the `logging` capability. Levels follow RFC 5424 syslog severities: debug, info, notice, warning, error, critical, alert, emergency. [DOC S-3s4qysez]
- Per-request opt-in: a client includes `io.modelcontextprotocol/logLevel` in that request's `_meta`; the server MUST NOT emit `notifications/message` for a request that omits this field, and MAY send messages at or above the requested level on that request's own response stream before the final response. `notifications/message` is request-scoped: the server MUST NOT deliver it on a `subscriptions/listen` stream or any stream other than the one carrying the response to the request that set the level. [DOC S-3s4qysez]
- `notifications/message` fields: `level`, optional `logger`, `data` (arbitrary JSON). An unrecognized `io.modelcontextprotocol/logLevel` value SHOULD be rejected with `-32602`. [DOC S-3s4qysez]
- Log messages MUST NOT contain credentials/secrets, personal identifying information, or internal system details that could aid attacks. [DOC S-3s4qysez]

### Subscriptions pattern (subscriptions/listen)
- `subscriptions/listen` opens a long-lived notification stream from server to client; it replaces the former `resources/subscribe` RPC and the HTTP GET endpoint (both removed in 2026-07-28; see mcp/deprecations.md). The stream stays open, delivering notifications until the client cancels it. [DOC S-onc3gpse]
- Request carries a `notifications` filter: `toolsListChanged` (bool), `promptsListChanged` (bool), `resourcesListChanged` (bool), `resourceSubscriptions` (string array of URIs). All fields optional; the server MUST NOT send a notification type the client did not request. [DOC S-onc3gpse]
- The server MUST send `notifications/subscriptions/acknowledged` as the first message, carrying the subscription id in `_meta['io.modelcontextprotocol/subscriptionId']` (the JSON-RPC id of the `subscriptions/listen` request), before any other notification on that subscription; on stdio, ordering is per subscription id, so other subscriptions' messages MAY interleave before it. The ack's `notifications` field reflects only the subset the server agreed to honor. [DOC S-onc3gpse]
- Every notification on the stream carries `io.modelcontextprotocol/subscriptionId` so a client can demultiplex multiple concurrent subscriptions (e.g. one for tools-list changes, one for resource updates). [DOC S-onc3gpse]
- A subscription ends when the client cancels it (close the SSE stream over HTTP, or send `notifications/cancelled` referencing the request id over stdio), the server tears it down (e.g. shutdown), or the transport itself closes (HTTP timeout, TCP disconnect, stdio process exit). [DOC S-onc3gpse]
- Graceful server-initiated closure: the server SHOULD respond to the original `subscriptions/listen` request with a completion result (`resultType: "complete"`, carrying the subscription id in `_meta`) before closing the stream; an abrupt transport drop carries no such response, and a client MAY treat its absence as a trigger to reconnect. [DOC S-onc3gpse]
- On stdio, the server holds no subscription state across reconnections: after a re-established connection, the client MUST re-send `subscriptions/listen` to re-establish its subscriptions. [DOC S-onc3gpse]

## Reference
| RPC | Purpose | Paginated | Cacheable |
|---|---|---|---|
| `resources/list` | list resources | yes | yes |
| `resources/read` | read resource contents | no | yes |
| `resources/templates/list` | list URI templates | yes | yes |
| `prompts/list` | list prompts | yes | yes |
| `prompts/get` | resolve a prompt with arguments | no | no |
| `completion/complete` | autocomplete a prompt/template argument | no | no |
| `server/discover` | versions, capabilities, identity | no | yes |
| `subscriptions/listen` | open a long-lived notification stream | no | no |

| Error code | Meaning here |
|---|---|
| -32602 | invalid params: bad resource/prompt name, missing arguments, invalid cursor, invalid log level; resource-not-found |
| -32603 | internal error |
| -32601 | completion capability not supported |
| -32002 | legacy resource-not-found code, still accepted by clients for backwards compatibility |

See mcp/spec-overview.md for the `_meta`/discover-era model this article's RPCs run under, mcp/tools.md for `tools/list`/`tools/call` (the fourth pagination-and-cache-bearing capability), and mcp/deprecations.md for the full removed/deprecated feature table (`resources/subscribe`, `ping`, logging's 12-month deprecation window).

## Examples
A client on PL-LT-00123 lists a server's file resources page by page:

- SNIPPET: a paginated `resources/list` JSON-RPC request; context: MCP specification 2026-07-28;
  checked: no [DOC S-uq2hafxi: `resources/list` params support `cursor`/`nextCursor` pagination]
```json
{"jsonrpc":"2.0","id":1,"method":"resources/list","params":{"cursor":null}}
```
then follows `nextCursor` until the field is absent, per the pagination rule above [DER S-7uw4d77y: missing nextCursor = end of results].

To watch `corp.example.com`'s config resource for changes without polling, the client opens one stream instead of subscribing per-resource:

- SNIPPET: a `subscriptions/listen` JSON-RPC request opening one notification stream for a resource
  URI; context: MCP specification 2026-07-28; checked: no [DOC S-uq2hafxi: `subscriptions/listen` with
  `notifications.resourceSubscriptions`]
```json
{"jsonrpc":"2.0","id":7,"method":"subscriptions/listen","params":{"notifications":{"resourceSubscriptions":["file:///project/config.json"]}}}
```
and demultiplexes further notifications by the `subscriptionId` `7` in their `_meta` [DER S-onc3gpse: subscription id = the listen request's JSON-RPC id].
