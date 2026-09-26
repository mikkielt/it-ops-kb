---
topic: mcp/registry-and-extensions
priority: P2
applies_to: "MCP Registry (preview, registry.modelcontextprotocol.io, server.json schema 2025-12-11); MCP extensions framework (spec 2026-07-28 and draft)"
retrieved_utc: 2026-09-26
sources: [S-gg2bczek, S-3j6fi7yk, S-bgodqwyo, S-w5egb2fu, S-rl4z6q5b, S-xmxnlqbx, S-uussqmqn, S-vl6444k5, S-vouhh5ur, S-wvioh66u, S-rji5dyla, S-blfb3mqc, S-4zkeipor, S-2hsm4de7, S-ovo7i7xn, S-rxtqmq47, S-3zrbebvf]
status: complete
---

# MCP Registry (server.json, publishing) and the extensions framework

## Summary
The official MCP Registry (`registry.modelcontextprotocol.io`) is a preview, centralized metadata
repository that maps reverse-DNS server names (`io.github.<user>/<name>`, verified by GitHub or DNS)
to installable packages (npm, PyPI, NuGet, Cargo, OCI, MCPB) and/or remote URLs, published with the
`mcp-publisher` CLI or a GitHub Actions workflow. `agents/mcp-server-lifecycle.md` already covers the
registry's existence, preview/API-freeze dates and that `server.json` has at least `name`, `version`,
`packages`, `remotes`; this article fills the schema, namespace verification, package types, versioning
rules, publishing tooling, aggregators and moderation that pass left as a gap. Separately, the MCP
**extensions** framework (`{vendor-prefix}/{extension-name}` identifiers, negotiated via
`extensions` capability fields) is how the ecosystem ships modular add-ons such as MCP Apps (UI iframes),
the Skills extension (serving Agent Skills over `resources/read`) and two authorization extensions
(machine-to-machine and enterprise-IdP-managed).

## Facts

### MCP Registry
- The MCP Registry is in preview; breaking changes or data resets may occur before GA. It is backed by
  Anthropic, GitHub, PulseMCP and Microsoft, hosts metadata only (not artifacts), and explicitly does
  **not** support private servers (internal hostnames or private package registries) — self-host a
  private registry for those. [DOC S-gg2bczek]
- `server.json` conforms to `$schema: https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`.
  Minimum required top-level fields shown in every example: `name`, `description`, `version`, plus at
  least one of `packages` (local/installable) or `remotes` (hosted); `title` and `repository` are common
  optional fields. [DOC S-3j6fi7yk, S-w5egb2fu]
- Namespace verification ties the server `name` to an authenticated identity: GitHub auth requires
  `io.github.<username-or-orgname>/*`; domain (DNS/HTTP) auth requires `<reverse-dns-of-domain>/*`
  (e.g. `io.modelcontextprotocol/everything` for domain `modelcontextprotocol.io`). [DOC S-xmxnlqbx]
- `mcp-publisher` CLI commands: `init` (generate a `server.json` template), `login` (`github`,
  `github-oidc`, `dns [google-kms|azure-key-vault]`, `http [...]`), `logout`, `publish`. Install via a
  prebuilt binary tarball, Homebrew (`brew install mcp-publisher`), or the equivalent PowerShell
  download on Windows. [DOC S-3j6fi7yk]
- DNS authentication: generate an Ed25519 or ECDSA P-384 key pair (locally, via Google Cloud KMS, or
  Azure Key Vault), publish a TXT record `"v=MCPv1; k=ed25519; p=<base64-pubkey>"` (or `k=ecdsap384`) at
  the apex of the domain, wait for propagation, then `mcp-publisher login dns --domain <d> --private-key <k>`.
  HTTP authentication uses the same key formats but hosts the proof string in a file at
  `https://<domain>/.well-known/mcp-registry-auth` instead of a DNS record. [DOC S-xmxnlqbx]
- npm packages (`"registryType": "npm"`): only `registry.npmjs.org` is supported; ownership is verified
  via an `mcpName` property in the package's `package.json`, which **MUST** equal `server.json`'s `name`.
  [DOC S-bgodqwyo]
- PyPI (`"registryType": "pypi"`, only `pypi.org`), NuGet (`"registryType": "nuget"`, only
  `api.nuget.org/v3/index.json`) and Cargo (`"registryType": "cargo"`, only `crates.io`) packages are
  verified by an `mcp-name: $SERVER_NAME` string in the package's rendered README; PyPI and NuGet accept
  it inside an HTML comment, but **crates.io strips HTML comments during markdown→HTML rendering**, so
  Cargo READMEs must show `mcp-name: ...` as visible text (e.g. a bullet point). [DOC S-bgodqwyo]
- Cargo has no per-invocation runner equivalent to `npx`/`uvx`/`dnx`: `cargo install <crate>` places a
  compiled binary on `PATH` once, so a Cargo `server.json` package entry intentionally omits
  `runtimeHint`. The alternative packaging path for Rust servers needing no toolchain on the end-user
  machine is MCPB (`registryType: mcpb`, a prebuilt binary via GitHub/GitLab Releases). [DOC S-bgodqwyo]
- OCI/Docker images (`"registryType": "oci"`) are supported from Docker Hub (`docker.io`), GitHub
  Container Registry (`ghcr.io`), Google Artifact Registry (`*.pkg.dev`), Azure Container Registry
  (`*.azurecr.io`) and Microsoft Container Registry (`mcr.microsoft.com`); `identifier` is
  `registry/namespace/repository:tag` (tag or digest); ownership is verified by a Dockerfile
  `LABEL io.modelcontextprotocol.server.name="<server-name>"`. [DOC S-bgodqwyo]
- MCPB packages (`"registryType": "mcpb"`) must be hosted on a GitHub or GitLab release; the `identifier`
  URL **MUST** contain the string "mcp" (in the `.mcpb` filename or repo name); `server.json` **MUST**
  include `fileSha256` (compute with `openssl dgst -sha256 <file>.mcpb`) — the registry itself does not
  validate this hash, but MCP clients validate it before installing. [DOC S-bgodqwyo]
- Remote servers use the `remotes` array with `"type": "streamable-http"` or `"type": "sse"` (SSE is
  deprecated; publish it only for legacy client compatibility) and a `url`; a remote **MUST** be publicly
  accessible. `remotes` entries support `{curly_brace}` URL template `variables` (with `description`,
  `isRequired`, `default`, `choices`, `isSecret`) for multi-tenant deployments, and a `headers` array
  (`name`, `description`, `isRequired`, `isSecret`) telling clients which HTTP headers to send.
  `remotes` and `packages` can coexist in one `server.json` so a host can pick its preferred install
  method. [DOC S-w5egb2fu]
- Versioning: `server.json`'s `version` string **MUST** be unique per publication and, once published,
  that version's metadata is immutable — updates require a new version string, not an edit. Semantic
  versioning is recommended but any string is accepted; the registry attempts semver parsing to sort
  versions and mark "latest", and explicitly **prohibits** version-range syntax (`^1.2.3`, `~1.2.3`,
  `>=1.2.3`, `1.x`, `1.2.*`, `1 - 2`, `1.2||1.3`). If a server later publishes a non-semver version after
  using semver, that non-semver version is still marked "latest". A semver prerelease published *after*
  its corresponding release version (e.g. `1.2.3-1` after `1.2.3`) sorts before it and will **not** become
  "latest" — recommended pattern for registry-only metadata updates that don't change the underlying
  package. Guidance: align the server version with the underlying package version (or, for remotes, with
  the API version); if multiple packages exist, the server version indicates the overall release.
  Aggregators should treat "latest"-marked versions as later, use semver comparison when both sides
  parse, else compare published timestamp, and treat a valid semver as later than a non-semver string.
  [DOC S-rl4z6q5b]
- GitHub Actions publishing: trigger on a version tag push (`on: push: tags: ["v*"]`); after building and
  publishing the underlying package (e.g. `npm publish`), install `mcp-publisher` from the latest GitHub
  release tarball, authenticate (`mcp-publisher login github-oidc` needs no dedicated secret and
  `permissions: id-token: write`; PAT auth needs an `MCP_GITHUB_TOKEN` secret with `read:org`+`read:user`
  scopes; DNS auth needs an `MCP_PRIVATE_KEY` secret), then `mcp-publisher publish`. [DOC S-uussqmqn]
- Aggregators (downstream marketplaces) consume the unauthenticated read-only REST API at
  `https://registry.modelcontextprotocol.io`: `GET /v0.1/servers` (cursor pagination via `limit`/`cursor`,
  and `updated_since` RFC 3339 filtering), `GET /v0.1/servers/{serverName}/versions`, and
  `GET /v0.1/servers/{serverName}/versions/{version}` (special version `latest`); path parameters must be
  URL-encoded (e.g. `io.modelcontextprotocol/everything` → `io.modelcontextprotocol%2Feverything`). The
  registry gives **no uptime or data durability guarantees**; aggregators are expected to scrape roughly
  hourly and persist their own copy. [DOC S-vl6444k5]
- Server `status` may later change to `"deprecated"` or `"deleted"` (all other metadata is immutable); a
  subregistry is an aggregator that also implements the registry's OpenAPI spec, and may inject custom
  metadata under a `_meta` key named after itself (e.g. `"com.example.subregistry/custom"`), e.g. ratings
  or security-scan results. [DOC S-vl6444k5]
- Moderation policy is deliberately permissive: only illegal content, malware, spam (mass duplicate
  submissions, marketing-only "servers") and completely non-functioning servers are removed; low quality,
  bugs, security vulnerabilities, duplicated functionality and adult content are explicitly **not**
  removed. A removed server's `status` is set to `"deleted"` but its metadata stays queryable via the API
  (metadata may be overwritten only in extreme, e.g. unlawful-content, cases). Report spam/malware to the
  underlying package registry and open a GitHub issue titled `Abuse report: `. [DOC S-vouhh5ur]
- FAQ: servers currently **cannot** be deleted/unpublished (open GitHub discussion at time of writing);
  updating metadata means publishing a new `server.json` with a new, unique version string; custom
  metadata under `_meta.io.modelcontextprotocol.registry/publisher-provided` is preserved on publish, up
  to a **4 KB (4096-byte) JSON size limit** — publishing fails if exceeded. [DOC S-wvioh66u]

### Extensions framework
- Extensions are optional additions to the MCP spec identified as `{vendor-prefix}/{extension-name}`
  (e.g. `io.modelcontextprotocol/oauth-client-credentials`); a third party should use a reverse-DNS
  domain it owns as its prefix (e.g. `com.example/my-extension`) to avoid collisions. Official
  extensions use vendor prefix `io.modelcontextprotocol` and live in `modelcontextprotocol/ext-*`
  GitHub repos; experimental incubation repos use `experimental-ext-*` and must be tied to a Working/
  Interest Group. [DOC S-rji5dyla]
- Extensions are **always disabled by default** and opt-in on both sides. Clients declare support in
  `_meta["io.modelcontextprotocol/clientCapabilities"].extensions` on every request; servers declare
  theirs in the `extensions` field of the `capabilities` object returned by `server/discover`. An empty
  extension settings object (`{}`) means "supported, no settings"; if only one side supports an
  extension, the other side must fall back to core-protocol behavior or reject the request if the
  extension is mandatory for that call. [DOC S-rji5dyla]
- Extension lifecycle: propose via a SEP (type "Extensions Track"), build at least one reference
  implementation in an official SDK before review, Core Maintainers review and approve, then publish to
  the extension repo; a breaking change (removed/renamed field, changed type, changed semantics, new
  required field) needs a new identifier (e.g. `...my-extension-v2`) rather than breaking the existing
  one in place. [DOC S-rji5dyla]
- Four official extension families exist: MCP Apps (`io.modelcontextprotocol/ui`), Skills over MCP
  (`io.modelcontextprotocol/skills`), MCP Tasks (see `mcp/tasks-extension.md`), and two authorization
  extensions — OAuth Client Credentials (`io.modelcontextprotocol/oauth-client-credentials`) and
  Enterprise-Managed Authorization (`io.modelcontextprotocol/enterprise-managed-authorization`). [DOC
  S-rji5dyla, S-blfb3mqc]
- Client support matrix (community-maintained, as of the 2026-07-28-era snapshot): MCP Apps is supported
  by Claude (web), Claude Desktop, VS Code GitHub Copilot, Microsoft 365 Copilot, Goose, Postman, MCPJam,
  ChatGPT, Cursor, Archestra.AI and PostHog Code; Enterprise-Managed Auth is supported by Archestra.AI;
  Skills over MCP has partial support in ChatGPT, fast-agent and MCP Inspector; no client in the table
  yet shows a full checkmark for OAuth Client Credentials. [DOC S-blfb3mqc]
- MCP Apps: a tool declares an interactive UI via `_meta.ui.resourceUri` pointing to a `ui://` resource;
  the host fetches and renders that HTML resource inside a sandboxed iframe (no access to parent DOM,
  cookies, or localStorage); the resource's `_meta.ui` object can set `permissions` (e.g. microphone,
  camera) and `csp` (allowed external origins). App↔host communication is a `postMessage`-based JSON-RPC
  dialect reusing some core methods (e.g. `tools/call`) plus new `ui/`-prefixed methods (e.g.
  `ui/initialize`); the `@modelcontextprotocol/ext-apps` `App` class is a convenience wrapper, not
  required — the postMessage protocol can be implemented directly. [DOC S-4zkeipor]
- Skills over MCP (`io.modelcontextprotocol/skills`, SEP-2640, status Final): a server supporting it
  **MUST** declare both the `resources` capability and the `io.modelcontextprotocol/skills` extension
  (optionally `{"directoryRead": true}`) in `server/discover`, and **MUST** implement `skills/list` and
  `skills/get`; skill file content is served through the existing `resources/read`. A skill is a
  directory with a `SKILL.md` (YAML frontmatter with `name` + `description`; the parent directory's final
  path segment **MUST** match `name`) plus optional supporting files, following the Agent Skills spec;
  servers **SHOULD NOT** exceed 512 files or 16 MiB per skill. `skills/list` and `skills/get` return a
  complete manifest per skill (`uri`, SHA-256 `digest`, byte `size` for every file), support pagination
  and caching (`ttlMs`, `cacheScope`), and an unknown skill/file URI returns JSON-RPC `-32602`. Hosts
  **MUST** verify each file's size and SHA-256 digest before use, verify `SKILL.md` frontmatter against
  the retained manifest entry, treat skill content as untrusted (per-skill approval required before any
  host-side execution or `allowed-tools` grants), and re-approve after any manifest change; reading
  `SKILL.md` as a supporting file does **not** itself activate that nested skill. [DOC S-2hsm4de7]
- Authorization extensions: OAuth Client Credentials (`io.modelcontextprotocol/oauth-client-credentials`)
  adds RFC 6749 §4.4 client-credentials machine-to-machine auth (JWT Bearer Assertions per RFC 7523, or a
  plain `client_id`/`client_secret` exchange) for background services, CI/CD and server-to-server
  integrations with no human in the loop. Enterprise-Managed Authorization
  (`io.modelcontextprotocol/enterprise-managed-authorization`) lets an organization's IdP (e.g. Okta,
  Entra ID) act as the authoritative access decision-maker: the client exchanges an ID Token for an
  Identity Assertion JWT Authorization Grant (ID-JAG) from the IdP, then exchanges the ID-JAG for an
  access token at the MCP server's own authorization server, so employees authenticate once with
  corporate SSO instead of authorizing each MCP server individually. Both extensions are specified in the
  `ext-auth` repo and require explicit client support — neither is on by default. [DOC S-ovo7i7xn,
  S-rxtqmq47, S-3zrbebvf]

## Reference
| Registry concept | Where documented | This kb |
|---|---|---|
| `listChanged`, tool identity, registry existence & preview dates | server/tools spec | `agents/mcp-server-lifecycle.md` |
| `server.json` schema, namespaces, package types, versioning, publishing, aggregators, moderation | `/registry/*` | this article |
| Extensions negotiation, MCP Apps, Skills, auth extensions | `/extensions/*` | this article |
| MCP Tasks extension | `/extensions/tasks/overview` | `mcp/tasks-extension.md` |
| Resources/prompts primitives used by Skills (`resources/read`, pagination, caching) | server/resources, utilities | `mcp/resources-prompts.md` |
| Streamable HTTP transport used by remote registry servers | basic/transports | `mcp/transports-streamable-http.md` |
| MRTR (roots/sampling/elicitation replacement) | basic/patterns/mrtr | `mcp/elicitation.md` |
| Windows on-device agent registry (ODR), a separate OS-local MCP discovery/containment layer, not this public registry | `windows/ai/mcp/*` | `agents/windows-agentic-platform.md` |

Back-link added to `agents/mcp-server-lifecycle.md`'s Reference table (registry row now points here for
the `server.json` schema this pass fills in).

## Examples
Minimal `server.json` for a placeholder Windows-endpoint-management server published under a personal
GitHub namespace, exposing a single stdio npm package with no remote fallback:

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.jan-kowalski/device-mgmt",
  "title": "Device Management",
  "description": "Query and remediate PL-LT-00123-class endpoints via ConfigMgr/Intune.",
  "version": "0.1.0",
  "packages": [
    {
      "registryType": "npm",
      "identifier": "@jan-kowalski/device-mgmt-mcp",
      "version": "0.1.0",
      "transport": {
        "type": "stdio"
      },
      "environmentVariables": [
        {
          "name": "DEVICE_MGMT_TENANT_ID",
          "description": "Entra tenant id (placeholder: 00000000-0000-0000-0000-000000000000)",
          "isRequired": true,
          "format": "string",
          "isSecret": false
        }
      ]
    }
  ]
}
```
Matching `package.json` ownership marker: `"mcpName": "io.github.jan-kowalski/device-mgmt"`. GitHub-based
auth requires the `name` to start with `io.github.jan-kowalski/`, so `mcp-publisher login github` (or
`login github-oidc` in CI) must authenticate as that same GitHub account before `mcp-publisher publish`
[DER: composed from the quickstart's own `mcpName`-must-match-name rule and the GitHub-namespace-format
rule, S-3j6fi7yk, S-xmxnlqbx]. To add a remote fallback later without breaking installed clients, a
`remotes` entry (`"type": "streamable-http", "url": "https://device-mgmt.corp.example.com/mcp"`) could sit
alongside `packages` in the same `server.json`, published as a new version (e.g. `0.2.0`) since published
versions are immutable [DER: from the coexistence and immutability facts above, S-w5egb2fu, S-rl4z6q5b].
