# MCP schema 2026-07-28 (digest)

Attribution: copied verbatim from the Model Context Protocol specification repository,
`modelcontextprotocol/modelcontextprotocol` at commit `a99bdd15ea9ff96bf4d758aac907bbb27e9329dc`,
paths `schema/2026-07-28/schema.ts` and `schema/2026-07-28/schema.json`. Licence: Apache-2.0 for
specification contributions, with contributions not yet relicensed remaining MIT (repository `LICENSE`, S717).
Files are unmodified so that their sha256 matches the source URL; this README carries the attribution.

| File | Source id | sha256 |
|---|---|---|
| schema.ts | S711 | 742750af0bb8c716e7030c4977c992b55d1adc4407e9e66997db5846baedc2cd |
| schema.json | S712 | ef70b61f99b6d2e5e3b46863822eab08dff6a45bedc7a08914e0e5b133f40203 |

## Digest
- `LATEST_PROTOCOL_VERSION = "2026-07-28"` (schema.ts).
- 155 exported interfaces/types in schema.ts.
- `ToolAnnotations` (schema.ts lines ~1900-1954): `title?`, `readOnlyHint?` (default false),
  `destructiveHint?` (default true, meaningful only when readOnlyHint false), `idempotentHint?`
  (default false, meaningful only when readOnlyHint false), `openWorldHint?` (default true). All are hints;
  clients should never make tool-use decisions based on annotations from untrusted servers.
- Result discriminator `resultType`: `"complete"` | `"input_required"` (core); `"task"` is added by the Tasks extension.
- MRTR types: `InputRequests`, `InputResponses`, `InputRequiredResult` (`inputRequests?`, `requestState?`).
- Error codes reserved by spec: `-32020` HeaderMismatch, `-32021` MissingRequiredClientCapability, `-32022` UnsupportedProtocolVersion.
- Examples directory (`schema/2026-07-28/examples/`) was not copied.
