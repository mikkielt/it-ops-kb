---
topic: agents/mcp-server-lifecycle
priority: P2
applies_to: "MCP specification 2026-07-28; modelcontextprotocol/registry (preview, API freeze v0.1 since 2025-10-24)"
retrieved_utc: 2026-09-27
sources: [S2135, S2012, S-7xsfc3ct, S1862, S-qpqoaaqj]
status: complete
---

# MCP server lifecycle: versioning, deprecation, listChanged, registry, contract tests

## Summary
A server that may change its tool set declares `listChanged: true` and sends `notifications/tools/list_changed`;
clients are expected to re-`tools/list` and are encouraged to cache a deterministic ordering for both correctness
and LLM prompt-cache hit rate. The spec has no per-tool version field; versioning is left to the tool name (e.g.
`DATA_EXPORT_v2`) or to the server-level `server.json` manifest used by the community MCP Registry (schema 2025-12-11: `name`, `description` and
`version` required). A generated, byte-for-byte-compared contract test already exceeds
the spec's own SHOULD-level validation guidance.

## Facts
- A server declares `"capabilities": {"tools": {"listChanged": true}}` to promise change notifications; on a
  change it sends `notifications/tools/list_changed` to clients that opened a `subscriptions/listen` stream with
  `toolsListChanged: true`; clients then re-issue `tools/list`. [DOC S2135 (modelcontextprotocol.io/specification/
  2026-07-28/server/tools; identical URL already recorded under id S2135 in `_sources.csv`
  — reused per the id-reuse rule)]
- Servers SHOULD return tools in a deterministic order across calls when the set is unchanged, specifically to let
  clients cache the list and to keep LLM prompt caches warm when tool definitions sit in the cached system context.
  [DOC S2135]
- Tool identity fields: `name` (unique per server, 1-128 chars, restricted charset, case-sensitive), `title`,
  `description`, `inputSchema`/`outputSchema` (JSON Schema, default draft 2020-12), `annotations` (untrusted unless
  the server is trusted). No dedicated per-tool version field exists in the spec; the spec's own example tool name
  `DATA_EXPORT_v2` shows version-in-name as the de facto approach. [DOC S2135]
- Security guidance: servers MUST validate all tool inputs, implement access controls, rate-limit invocations, and
  sanitize outputs; clients SHOULD prompt for confirmation on sensitive operations, show tool inputs to the user
  before calling, validate results against `outputSchema`, implement call timeouts, and log tool usage for audit.
  [DOC S2135]
- The MCP Registry (`github.com/modelcontextprotocol/registry`, community Registry Working Group; licence in
  transition from MIT to Apache-2.0: new code Apache-2.0, documentation CC-BY-4.0, contributions without
  relicensing consent stay MIT) is a
  directory of MCP servers analogous to a package registry; a `server.json` manifest (fields at least `name`,
  `version`, `packages`, `remotes`) is the unit of registration. It launched in preview 2025-09-08 and entered a
  v0.1 API freeze (no breaking changes) on 2025-10-24; it is not yet GA. [DOC S2012]
- The `server.json` schema (`$id` `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`,
  embedded in the registry's validators): a server entry requires `name`, `description` and `version`. `name` is
  3-200 characters in reverse-DNS form with exactly one slash (pattern `^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$`),
  `description` 1-100 characters, optional `title` 1-100 characters, `version` at most 255 characters, SHOULD be
  semantic, and version ranges such as `^1.2.3` or `1.x` are rejected. A package entry requires `registryType`,
  `identifier` and `transport`. [DOC S-7xsfc3ct]
- Client reaction in Claude Code: when a server sends a `list_changed` notification, Claude Code refreshes that
  server's tools, prompts and resources without a reconnect. [DOC S1862]
- Client reaction in the Claude API MCP connector: the beta header `mcp-client-2026-09-15` records each server's tool
  list as an `mcp_tool_listing` block and lets the caller pin it (the toolset's `tools` field), so a server that
  changes its tools mid-conversation does not change what Claude sees; it includes everything `mcp-client-2025-11-20`
  does. Beta. [DOC S-qpqoaaqj]
- No Claude Code or MCP page read on 2026-09-27 says whether a changed tool description re-triggers a permission
  prompt. [DER S1862: absence on the page read; see _gaps.md]

## Reference
| Mechanism | What it signals | Client reaction |
|---|---|---|
| `listChanged` capability + `notifications/tools/list_changed` | tool set changed | re-`tools/list`, refresh cache |
| Deterministic tool ordering | no change since last list | keep cached list, keep LLM prompt cache warm |
| Tool name suffix (e.g. `_v2`) | de facto version marker | none mandated by spec |
| `server.json` (MCP Registry) | server-level version/packages/remotes | registry consumers resolve install source |
| `outputSchema` + client-side validation | structured result contract | client SHOULD validate before use |

The full `server.json` schema (namespaces/verification, package types, remote servers, versioning rules,
`mcp-publisher`/GitHub Actions publishing, aggregators, moderation), plus the separate MCP extensions
framework (MCP Apps, Skills over MCP, auth extensions), is documented in `mcp/registry-and-extensions.md`.

## Examples
If a stdio MCP server renamed a tool such as `client.refresh_policy` to `device.refresh`, a long-lived client
session with a stale cached tool list would keep offering the old name until it re-lists; sending
`notifications/tools/list_changed` at startup after any such rename (or simply restarting the server process, which
is often such a server's only deployment path) forces a fresh `tools/list` on next connect [DER S2135].

### Contract-testing implication
A generated `contracts/mcp-tools.json` compared byte-for-byte in CI is already stricter than the MCP spec's
own SHOULD-level input/output validation guidance, so that CI gate substitutes for anything a registry's
versioning machinery would otherwise catch (a client silently using a stale tool definition) — and a stdio-only
server that is never published to the MCP Registry stays consistent with a one-repository, no-external-pin scope.
