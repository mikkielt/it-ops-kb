---
topic: auth/delegation-kcd-obo
priority: P2
applies_to: "Entra OBO, Kerberos constrained/resource-based delegation, Entra Application Proxy + KCD, MCP authorization 2026-07-28, Teams bot SSO (docs current 2026-09-24)"
retrieved_utc: 2026-09-27
sources: [S1297, S1298, S1299, S1300, S1301, S1205, S-lbitjans, S-q2j6mx4q, S-l74ozdea, S-6mj4jpce, S-hrri7kcy, S-3zrbebvf, S-uw3gpx3u, S-62odry4k, S-cqnp7ckg, S-ws2x5bdf]
status: complete
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
  went **stable on 2026-06-18** (the ext-auth pull request promoting it merged that day). [DOC S-hrri7kcy]
  Okta is reported as the only IdP shipping support at launch [COMMUNITY S1300], and no Microsoft page
  documents Entra issuing ID-JAG, so an organization on Entra ID cannot turn the flow on with Entra as the
  IdP. [DER S-uw3gpx3u: no ID-JAG issuance documented]
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
- OBO chaining: the OBO page states no explicit multi-hop rule, but its two conditions (the assertion's
  `aud` must be the app making the request; the flow exists to pass a user's identity and permissions
  through the request chain) mean a token obtained by OBO for the next middle tier can be that tier's
  assertion. [DER S1297: aud rule plus stated purpose; no explicit multi-hop sentence]
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
- Classic constrained delegation is configured in `msDS-AllowedToDelegateTo` on the front-end service account
  (computer or user object): a multi-valued Unicode string list of SPNs for which the service can obtain
  service tickets for constrained delegation. [DOC S-l74ozdea]
- The "Account is sensitive and cannot be delegated" setting is set on the account whose identity would be
  delegated (the user, e.g. an engineer's admin account), not on the service; it restricts only
  delegation scenarios such as constrained or unconstrained Kerberos delegation, not sign-in or the
  account's permissions. [DOC S-6mj4jpce]
- Protected Users members cannot be delegated with unconstrained or constrained delegation. [DOC S1205]
- In MS-SFU, when the principal's `DelegationNotAllowed` is set the KDC should not set the FORWARDABLE
  flag on the S4U2self service ticket [DOC S-cqnp7ckg], and for RBCD the KDC must reject an S4U2proxy
  request whose evidence ticket is not forwardable (`KRB-ERR-BADOPTION`, `STATUS_ACCOUNT_RESTRICTION`)
  [DOC S-ws2x5bdf]. So the "sensitive" setting blocks protocol transition and RBCD as well; no Microsoft
  page says in so many words that Protected Users membership sets `DelegationNotAllowed`, so for that
  group the RBCD block is inferred, not stated. [DER S-cqnp7ckg, S-ws2x5bdf, S1205]
- Entra Application Proxy + KCD: connector and application servers must be domain-joined, same domain
  or trusting domains; the connector server must be able to read users' `TokenGroupsGlobalAndUniversal`
  attribute (add it to the Windows Authorization Access group) and needs permission in AD to impersonate
  users to negotiate Kerberos on the signed-in user's behalf; a connector is configured for either SPNEGO
  or a standard Kerberos token, not both, and all connectors in a connector group must agree on that choice.
  [DOC S1299]
- The private network (App Proxy) connector services run as fixed accounts: the connector (`WAPCSvc`) as
  Network Service and the updater (`WAPCUpdaterSvc`) as NT Authority\System; running them in another user
  context is not supported. [DOC S-62odry4k] (Corrects an earlier note that the connector runs as local
  system.)
- MCP Enterprise-Managed Authorization (ID-JAG) is marked Stable in the ext-auth specification: the MCP
  client sends an RFC 8693 token-exchange request with the user's ID token or refresh token to the IdP,
  gets an Identity Assertion JWT Authorization Grant, and presents it as an RFC 7523 JWT grant to the MCP
  server's authorization server. [DOC S-hrri7kcy, S-3zrbebvf]
- No Microsoft Learn page documents Entra ID issuing ID-JAG (searched 2026-09-27); the launch reporting
  names Okta as the only IdP. [DER S-uw3gpx3u: absence; COMMUNITY S1300]
- Microsoft documents Entra ID as the standard OAuth authorization server for an MCP server (protected
  resource metadata pointing at Entra, v2 tokens, Application ID URI matching `resource`), and on Azure App
  Service lets the platform's built-in authentication (Easy Auth) validate tokens; this is plain MCP OAuth,
  not an ID-JAG interim. [DOC S-uw3gpx3u]
- This means a future broker component wanting MCP OAuth via Entra-issued ID-JAG cannot do
  so with a stable, Microsoft-native mechanism today; any interim pattern (such as Entra as the
  Conditional-Access/consent layer in front of a separately hosted authorization server) is an additional
  service component that a design with no gateway/service beyond the CLI and MCP server would need to
  explicitly re-scope for. [DER S1300, S-uw3gpx3u: Okta-only at launch and no Entra ID-JAG issuance documented, so Entra needs an extra component]
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
| Resource-based constrained delegation | target/back-end resource (`msDS-AllowedToActOnBehalfOfOtherIdentity`) | cross-domain capable | "sensitive" user blocks it (non-forwardable S4U2self ticket rejected by S4U2proxy; DER) | S1298, S-q2j6mx4q, S-cqnp7ckg, S-ws2x5bdf |
| Entra App Proxy + KCD | connector computer account (constrained delegation, impersonate-user permission) | connector and app server same/trusting domain | AD account controls as above | S1299 |
| Entra OBO | confidential middle-tier app registration | n/a (OAuth, not Kerberos) | not stated in S1297 | S1297 |
| Teams bot SSO | bot resource OAuth connection + app manifest | n/a (cloud) | not stated in S1301 | S1301, S-lbitjans |
| MCP Enterprise-Managed Authorization (ID-JAG) | enterprise IdP + MCP authorization server | n/a | IdP-side revocation | S-hrri7kcy (stable 2026-06-18); Entra issuance not documented |

## Examples
- A future broker component doing OBO to Graph on behalf of `jan.kowalski`: the broker is the confidential
  middle tier; the token it receives from the client must carry `aud=<broker app id>`, never
  `aud=https://graph.microsoft.com` directly, or the OBO exchange is rejected.

## Open items
- Resolved 2026-09-27: the stable date is confirmed from the ext-auth repository (S-hrri7kcy); Entra
  ID-JAG issuance is a documented absence; "Okta only at launch" stays COMMUNITY (S1300).
