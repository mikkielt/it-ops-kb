---
topic: auth/delegation-kcd-obo
priority: P2
applies_to: "Entra OBO, Kerberos constrained/resource-based delegation, Entra Application Proxy + KCD, MCP authorization 2026-07-28, Teams bot SSO (docs current 2026-09-24)"
retrieved_utc: 2026-09-26
sources: [S1297, S1298, S1299, S1300, S1301, S1205, S-lbitjans, S-q2j6mx4q, S-l74ozdea, S-6mj4jpce]
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
- Kerberos RBCD (Windows Server 2012 / 2012 R2 onwards) moves the delegation decision to the resource
  owner: it is configured on the back-end resource's account (PowerShell `PrincipalsAllowedToDelegateToAccount`),
  which can be in another domain; classic constrained delegation is configured by a domain admin on the
  front-end service account and restricted to a single domain. [DOC S1298]
- Entra Application Proxy's KCD path needs the connector server and the application server
  domain-joined (same domain or trusting domains) and the connector granted permission in AD to
  impersonate users, which it uses to negotiate Kerberos on the user's behalf. [DOC S1299]
- MCP's Enterprise-Managed Authorization extension (which defines the ID-JAG grant, built on RFC 8693
  token exchange and RFC 7523 JWT bearer grants, from an enterprise IdP to an MCP authorization server)
  went **stable on 2026-06-18**; Okta is the only IdP shipping support at launch, so an organization on
  Entra ID (Azure AD) cannot turn the flow on yet. [COMMUNITY S1300]
- Teams bot SSO requires a Microsoft Entra app registration plus a bot resource with a client secret,
  messaging endpoint and OAuth connection, a `webApplicationInfo` entry in the app manifest, and an OAuth
  card flow in which the bot exchanges the Teams-supplied token through the Bot Framework Token Service,
  which stores it in the Bot Framework Token Store. [DOC S1301]
- The manifest's `validDomains` must include `token.botframework.com` for bots using Bot Framework.
  [DOC S-lbitjans]

## Facts
- OBO: every middle-tier app in the chain is a confidential client (secret or certificate); public
  clients/SPAs cannot be a middle tier. [DOC S1297]
- OBO: the assertion submitted to the token endpoint must have an `aud` matching the app making the
  OBO request; an app can't redeem a token meant for a different app (e.g. a token for Microsoft Graph).
  [DOC S1297]
- OBO: a token obtained via OBO being usable as the assertion for a further OBO hop when its `aud`
  matches the next middle tier. [UNK: not in S1297 as re-read 2026-09-27]
- OBO: only user (delegated) identities flow through OBO; an app-only client-credentials token
  cannot be exchanged via OBO. [DOC S1297]
- OBO: a middle-tier API that uses a custom token-signing key cannot be used in an OBO chain, because
  the downstream API can't validate a signature from a client-controlled key. [DOC S1297]
- RBCD: delegation rights are set on the target resource's account (`PrincipalsAllowedToDelegateToAccount`,
  stored in its `msDS-AllowedToActOnBehalfOfOtherIdentity` attribute, which is checked to decide whether a
  requestor may act on behalf of other identities to services running as that account), so the resource
  owner (not the calling service's admin) controls who may delegate to it. [DOC S1298, S-q2j6mx4q]
- Classic (front-end-configured) constrained delegation requires the front-end and back-end service
  accounts to be in the same domain; cross-domain/cross-forest scenarios require RBCD instead.
  [DOC S1298]
- The "Account is sensitive and cannot be delegated" setting is set on the account whose identity would be
  delegated (the user, e.g. an engineer's admin account), not on the service; it restricts only
  delegation scenarios such as constrained or unconstrained Kerberos delegation, not sign-in or the
  account's permissions. [DOC S-6mj4jpce]
- Protected Users members cannot be delegated with unconstrained or constrained delegation. [DOC S1205]
- The flag or Protected Users membership also blocking protocol transition and RBCD specifically.
  [UNK: not in S1298 as re-read 2026-09-27]
- Entra Application Proxy + KCD: connector and application servers must be domain-joined, same domain
  or trusting domains; the connector server must be able to read users' `TokenGroupsGlobalAndUniversal`
  attribute (add it to the Windows Authorization Access group) and needs permission in AD to impersonate
  users to negotiate Kerberos on the signed-in user's behalf; a connector is configured for either SPNEGO
  or a standard Kerberos token, not both, and all connectors in a connector group must agree on that choice.
  [DOC S1299]
- The App Proxy connector service having to run as local system rather than a custom service account.
  [UNK: not in S1299 as re-read 2026-09-27]
- MCP Enterprise-Managed Authorization (ID-JAG): stable as of 2026-06-18 (per community/vendor
  reporting, not yet cross-checked against a modelcontextprotocol.io spec revision date in this pass
  — see `gaps.md`); it lets an enterprise IdP issue a short-lived, scoped Identity Assertion JWT
  Authorization Grant (RFC 8693 token-exchange semantics) so an MCP client/agent can reach an MCP
  server's authorization server without a per-app user consent screen. [COMMUNITY S1300 for
  the "stable June 2026" date and Okta-first-mover claim — this is vendor/community reporting, not an
  official modelcontextprotocol.io or Microsoft page; treat the date as provisional]
- Entra ID's own native issuance of ID-JAG is **not available** as of this retrieval (the post names Okta as
  the only IdP shipping it at launch). [COMMUNITY S1300]
- Whether Microsoft documents an Entra ID + Azure App Service authorization boundary in front of an MCP
  server as the interim pattern: not in S1300, which does not mention it. [UNK: claim previously attributed
  to S1300; needs a Microsoft source]
- This means a future broker component wanting MCP OAuth via Entra-issued ID-JAG cannot do
  so with a stable, Microsoft-native mechanism today; any interim pattern (such as Entra as the
  Conditional-Access/consent layer in front of a separately hosted authorization server) is an additional
  service component that a design with no gateway/service beyond the CLI and MCP server would need to
  explicitly re-scope for. [DER S1300: Okta-only at launch, so Entra needs an extra component]
- Enabling Teams bot SSO includes creating a bot resource and configuring its client secret, messaging
  endpoint and OAuth connection; a bot created with a user-assigned managed identity gets no app
  registration automatically, so a separate one is needed for `webApplicationInfo`. [DOC S1301]
- Teams bot SSO is supported in one-on-one and group chat scope, not in channel scope. [DOC S1301]
- The manifest's `webApplicationInfo` carries the Entra app ID (`id`) and the application ID URI
  (`resource`), needs manifest version 1.5 or later, and `validDomains` must include
  `token.botframework.com` for bots using Bot Framework. [DOC S-lbitjans]
- After the token exchange the bot can parse the token for the user's details, and the app can be
  extended with Microsoft Graph scopes and permissions. [DOC S1301]
- A further OBO hop from the bot service to another downstream API would make the bot service an OBO
  middle tier, subject to the OBO rules above (confidential middle tier, `aud` matching,
  delegated-identity-only). [DER S1297: OBO rules applied to the bot service as middle tier]

## Reference
| Mechanism | Where delegation is configured | Domain/trust requirement | Blockable by target account | Source |
|---|---|---|---|---|
| Classic constrained delegation | front-end account (`msDS-AllowedToDelegateTo`, a list of SPNs) | single domain | "sensitive, cannot be delegated" setting on the user (constrained and unconstrained delegation) | S1298, S-l74ozdea, S-6mj4jpce |
| Resource-based constrained delegation | target/back-end resource (`msDS-AllowedToActOnBehalfOfOtherIdentity`) | cross-domain capable | not stated in S1298 (UNK) | S1298, S-q2j6mx4q |
| Entra App Proxy + KCD | connector computer account (constrained delegation, impersonate-user permission) | connector and app server same/trusting domain | AD account controls as above | S1299 |
| Entra OBO | confidential middle-tier app registration | n/a (OAuth, not Kerberos) | not stated in S1297 | S1297 |
| Teams bot SSO | bot resource OAuth connection + app manifest | n/a (cloud) | not stated in S1301 | S1301, S-lbitjans |
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
