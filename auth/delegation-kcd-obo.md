---
topic: auth/delegation-kcd-obo
priority: P2
applies_to: "Entra OBO, Kerberos constrained/resource-based delegation, Entra Application Proxy + KCD, MCP authorization 2026-07-28, Teams bot SSO (docs current 2026-09-24)"
retrieved_utc: 2026-09-24
sources: [S1297, S1298, S1299, S1300, S1301]
status: partial
---

# Delegation, KCD/RBCD and OBO (A.1, later)

Read `mcp/authorization.md` first (done); this file adds only what it does not already cover:
ID-JAG / Enterprise-Managed Authorization status. It does not re-state the base MCP authorization
facts (audience validation, `resource` parameter, `iss` validation, DCR deprecation), already in
`mcp/authorization.md`.

## Summary
- Entra OBO exchanges a delegated user token at a confidential middle-tier for a new delegated token
  to a downstream API; it only works for user (delegated) identities, never for app-only tokens, and
  the assertion must be issued for the middle tier, never for the downstream API directly. [DOC S1297]
- Kerberos RBCD (Windows Server 2012+) moves delegation control to the target resource
  (`msDS-AllowedToActOnBehalfOfOtherIdentity`); classic constrained delegation needs front-end and
  back-end in the same domain (or trust) and is configured on the front-end account instead. The
  "account is sensitive and cannot be delegated" flag on a *user* account stops any service from
  delegating that user's identity, under either model. [DOC S1298]
- Entra Application Proxy's KCD path needs the connector server and the application server
  domain-joined (same domain or trusted domains), the connector service running as local system
  (not a custom identity), and the connector granted permission to impersonate users in AD to
  negotiate Kerberos on the user's behalf. [DOC S1299]
- MCP's Enterprise-Managed Authorization extension (which defines the ID-JAG grant, RFC 8693 token
  exchange from an enterprise IdP to an MCP authorization server) went **stable in June 2026**; Entra
  ID does not yet natively issue ID-JAG (not GA as of this retrieval) — Microsoft has shown Entra ID +
  App Service as an authorization boundary for MCP servers, but Okta is the IdP shipping support at
  EMA's launch, not Entra. [COMMUNITY S1300]
- Teams bot SSO requires an Azure-managed Bot Service resource (the OAuth connection lives in Azure
  Bot Service, not in a self-hosted bot), specific app-manifest entries (`webApplicationInfo`,
  `token.botframework.com` in `validDomains`), and an OAuth dialog flow that fetches the token from
  the Bot Framework Token Service; from there the bot can call Graph directly or run its own OBO
  exchange to a further downstream API. [DOC S1301]

## Facts
- OBO: every middle-tier app in the chain is a confidential client (secret or certificate); public
  clients/SPAs cannot be a middle tier. [DOC S1297]
- OBO: the assertion submitted to the token endpoint must have an `aud` matching the app making the
  OBO request, and must never be issued directly for the downstream API — a token obtained via OBO
  can itself be used as the next assertion in a further OBO hop provided that `aud` match holds.
  [DOC S1297]
- OBO: only user (delegated) identities flow through OBO; an app-only client-credentials token
  cannot be exchanged via OBO. [DOC S1297]
- OBO: a middle-tier API that uses a custom token-signing key cannot be used in an OBO chain, because
  the downstream API can't validate a signature from a client-controlled key. [DOC S1297]
- RBCD: delegation rights live on the target resource's `msDS-AllowedToActOnBehalfOfOtherIdentity`
  attribute, so the resource owner (not the calling service's admin) controls who may delegate to it.
  [DOC S1298]
- Classic (front-end-configured) constrained delegation requires the front-end and back-end service
  accounts to be in the same domain; cross-domain/cross-forest scenarios require RBCD instead.
  [DOC S1298]
- The "Account is sensitive and cannot be delegated" flag is set on the account whose identity would be
  delegated (the user, e.g. an engineer's admin account), not on the service. With it set, no service
  can obtain a delegated ticket for that user under classic KCD, protocol transition or RBCD.
  Protected Users membership has the same effect. [DOC S1298; DER S1298,S1205]
- Entra Application Proxy + KCD: connector and application servers must be domain-joined, same domain
  or trusted domains; the connector service must run as local system (not a custom service account);
  the connector's computer account needs read access to user attributes needed for Kerberos (e.g. via
  the Windows Authorization Access Group) and needs "impersonate a user" rights in AD to negotiate
  Kerberos on the signed-in user's behalf; a connector is configured for either SPNEGO or a standard
  Kerberos token, not both, and all connectors in a connector group must agree on that choice.
  [DOC S1299]
- MCP Enterprise-Managed Authorization (ID-JAG): stable as of June 2026 (per community/vendor
  reporting, not yet cross-checked against a modelcontextprotocol.io spec revision date in this pass
  — see `gaps.md`); it lets an enterprise IdP issue a short-lived, scoped Identity Assertion JWT
  Authorization Grant (RFC 8693 token-exchange semantics) so an MCP client/agent can reach an MCP
  server's authorization server without a per-app user consent screen. [COMMUNITY S1300 for
  the "stable June 2026" date and Okta-first-mover claim — this is vendor/community reporting, not an
  official modelcontextprotocol.io or Microsoft page; treat the date as provisional]
- Entra ID's own native issuance of ID-JAG is **not GA** as of this retrieval; Microsoft's public
  demonstrations use Entra ID plus Azure App Service as the authorization boundary in front of an MCP
  server, rather than Entra directly minting ID-JAG tokens. [COMMUNITY S1300]
- This means a future broker component wanting MCP OAuth via Entra-issued ID-JAG cannot do
  so with a stable, Microsoft-native mechanism today; the closest supported pattern is Entra as the
  Conditional-Access/consent layer in front of an App Service-hosted authorization server, which is
  an additional service component that a design with no gateway/service beyond the CLI and MCP server
  would need to explicitly re-scope for. [DER S1300]
- Teams bot SSO needs an Azure-managed Bot Service resource specifically — a self-hosted-only Bot
  Framework deployment cannot host the OAuth connection SSO depends on. [DOC S1301]
- The manifest must list the bot's resource URL under `webApplicationInfo` and add
  `token.botframework.com` to `validDomains`; SSO additionally requires the bot to declare 1:1 chat
  support in the manifest. [DOC S1301]
- After the bot obtains the Entra token for the signed-in Teams user, it may call Graph directly or
  perform its own OBO exchange to reach a further downstream API — i.e. Teams bot SSO is itself the
  first hop, with a conventional OBO hop optionally chained after it, subject to the same OBO rules
  above (confidential middle tier, `aud` matching, delegated-identity-only). [DOC S1301, DER S1297]

## Reference
| Mechanism | Where delegation is configured | Domain/trust requirement | Blockable by target account | Source |
|---|---|---|---|---|
| Classic constrained delegation | front-end account (`msDS-AllowedToDelegateTo`) | same domain | "sensitive, cannot be delegated" flag on the user | S1298 |
| Resource-based constrained delegation | target/back-end resource (`msDS-AllowedToActOnBehalfOfOtherIdentity`) | cross-domain/forest capable | "sensitive, cannot be delegated" flag on the user | S1298 |
| Entra App Proxy + KCD | connector (local system identity, impersonate-user right) | connector and app server same/trusted domain | AD account controls as above | S1299 |
| Entra OBO | confidential middle-tier app registration | tenant-wide (OAuth, not Kerberos) | app disablement / consent revocation | S1297 |
| Teams bot SSO | Azure Bot Service OAuth connection + app manifest | n/a (cloud) | bot/app registration disablement | S1301 |
| MCP Enterprise-Managed Authorization (ID-JAG) | enterprise IdP + MCP authorization server | n/a | IdP-side revocation | S1300 (community, not yet Microsoft-native for Entra) |

## Examples
- A future broker component doing OBO to Graph on behalf of `jan.kowalski`: the broker is the confidential
  middle tier; the token it receives from the client must carry `aud=<broker app id>`, never
  `aud=https://graph.microsoft.com` directly, or the OBO exchange is rejected.

## Open items
- QA (delegation-kcd-obo, P2, no numbered QA assigned in the brief beyond "extend for A.1"): the
  section above is a first pass; the "stable June 2026" EMA/ID-JAG date and Entra's non-GA native
  ID-JAG status come from vendor/community blogs (S1300), not an official modelcontextprotocol.io
  spec-revision page or a Microsoft Learn page — flagged `COMMUNITY`, and a follow-up should re-check
  `modelcontextprotocol.io/extensions/auth/enterprise-managed-authorization` directly and any Entra
  "what's new" page for a first-party status statement. LAB: none (this is a docs/status lookup, not
  something a lab can settle).
