---
topic: mcp/tools
priority: P1
applies_to: "MCP specification 2026-07-28; MCP Python SDK 2.2.0"
retrieved_utc: 2026-09-26
sources: [S708, S711, S701, S710, S725, S726, S736]
status: complete
---
# Tools: annotations, outputSchema, structuredContent (2026-07-28)

## Summary
Tools are model-controlled; the spec says there SHOULD always be a human able to deny invocations. `ToolAnnotations`
are hints (readOnly/destructive/idempotent/openWorld) and are untrusted unless the server is trusted. `outputSchema`
(any JSON Schema 2020-12) obliges servers to return conforming `structuredContent`; for compatibility the serialized
JSON SHOULD also appear as a TextContent block. `tools/call` may answer with `InputRequiredResult` (MRTR).

## Facts
- Human in the loop: there SHOULD always be a human able to deny tool invocations; apps SHOULD show confirmation prompts. [DOC S708]
- `tools/list` MUST NOT vary per connection; it MAY vary by the authorization on the request; SHOULD be in deterministic order. [DOC S708]
- List results must carry `ttlMs` and `cacheScope` (`public`/`private`) via `CacheableResult`. [DOC S701]
- Tool fields: `name`, `title?`, `description`, `icons?`, `inputSchema` (MUST be a JSON Schema object, default dialect 2020-12), `outputSchema?`, `annotations?`. [DOC S708]
- No-parameter tools: `{"type":"object","additionalProperties":false}` is recommended. [DOC S708]
- Tool names SHOULD be 1-128 chars from `A-Za-z0-9_-.`, case-sensitive, unique within a server. [DOC S708]
- Clients MUST consider tool annotations untrusted unless they come from trusted servers. [DOC S708]
- `ToolAnnotations`: `title`, `readOnlyHint` (default false), `destructiveHint` (default true; meaningful only when readOnlyHint is false), `idempotentHint` (default false; only when readOnlyHint false), `openWorldHint` (default true). [DOC S711]
- `structuredContent` may be any JSON value; if `outputSchema` is given, servers MUST conform and clients SHOULD validate. [DOC S708]
- A tool returning structured content SHOULD also return the serialized JSON in a TextContent block. [DOC S708]
- 2026-07-28 loosened `inputSchema`/`outputSchema` to any JSON Schema 2020-12 keywords and added `$ref` resolution requirements. [DOC S701]
- Two error channels: protocol errors (JSON-RPC error, e.g. unknown tool `-32602`) and tool execution errors (`isError: true` in the result, for the model to self-correct). [DOC S708]
- `tools/call` MAY return `InputRequiredResult`; the retry carries `inputResponses` and echoed `requestState` with a new JSON-RPC id. [DOC S708]
- Stateful tools: no protocol session; servers return explicit handles and SHOULD validate caller authorization against the handle on every call. [DOC S708]
- Servers MUST validate inputs, implement access control, rate-limit invocations and sanitize outputs; clients SHOULD show inputs before calling, implement timeouts, and log tool usage. [DOC S708]
- `x-mcp-header` mirrors parameters into HTTP headers; clients on other transports (e.g. stdio) MAY ignore it. [DOC S708]
- Python SDK: `@mcp.tool(title=..., annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))`; snake_case fields in Python. [DOC S736]
- Python SDK: return type annotation is the output schema; scalars/lists are wrapped as `{"result": ...}`; results validated against the schema, mismatch becomes a tool error; `structured_output=False` opts out. [DOC S726]

## Reference
| Annotation | Default | Meaningful when |
|---|---|---|
| readOnlyHint | false | always |
| destructiveHint | true | readOnlyHint = false |
| idempotentHint | false | readOnlyHint = false |
| openWorldHint | true | always |

See mcp/resources-prompts.md for the sibling `resources`/`prompts` capabilities, `completion/complete`, `server/discover`, and the shared pagination/caching/subscriptions utilities `tools/list` also uses.

## Examples
A tier-0 read tool `device.get` for `PL-LT-00123` would declare `readOnlyHint: true, openWorldHint: false`; per the table, `destructiveHint`/`idempotentHint` carry no meaning when `readOnlyHint` is true. [DER S711: defaults table above]
