---
topic: agents/mcp-server-lifecycle
priority: P2
applies_to: "MCP specification 2026-07-28; modelcontextprotocol/registry (preview, API freeze v0.1 since 2025-10-24)"
retrieved_utc: 2026-09-25
sources: [S2135, S2012]
status: partial
---

# MCP server lifecycle: versioning, deprecation, listChanged, registry, contract tests

## Summary
A server that may change its tool set declares `listChanged: true` and sends `notifications/tools/list_changed`;
clients are expected to re-`tools/list` and are encouraged to cache a deterministic ordering for both correctness
and LLM prompt-cache hit rate. The spec has no per-tool version field; versioning is left to the tool name (e.g.
`DATA_EXPORT_v2`) or to the server-level `server.json` manifest used by the community MCP Registry, whose exact
schema this pass could not pin (see `gaps.md`). A generated, byte-for-byte-compared contract test already exceeds
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
- The MCP Registry (`github.com/modelcontextprotocol/registry`, MIT, community Registry Working Group) is a
  directory of MCP servers analogous to a package registry; a `server.json` manifest (fields at least `name`,
  `version`, `packages`, `remotes`) is the unit of registration. It launched in preview 2025-09-08 and entered a
  v0.1 API freeze (no breaking changes) on 2025-10-24; it is not yet GA. The exact `server.json` schema (required
  vs. optional fields, `$schema` URL, deprecation markers) was not confirmed in this pass. [DOC S2012; gap noted]

## Reference
| Mechanism | What it signals | Client reaction |
|---|---|---|
| `listChanged` capability + `notifications/tools/list_changed` | tool set changed | re-`tools/list`, refresh cache |
| Deterministic tool ordering | no change since last list | keep cached list, keep LLM prompt cache warm |
| Tool name suffix (e.g. `_v2`) | de facto version marker | none mandated by spec |
| `server.json` (MCP Registry) | server-level version/packages/remotes | registry consumers resolve install source |
| `outputSchema` + client-side validation | structured result contract | client SHOULD validate before use |

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
