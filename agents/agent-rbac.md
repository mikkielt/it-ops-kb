---
topic: agents-authz/agent-rbac
priority: P1
applies_to: "MCP specification draft (post 2026-07-28), Claude Code 2.1.x, Microsoft Entra Agent ID (public preview, 2026-03 docs), Microsoft Entra role-assignable groups / PIM for Groups"
retrieved_utc: 2026-09-25
sources: [S707, S1282, S1297, S2040, S2041, S2042, S2045, S2050, S2051, S2052, S2053, S2058]
status: complete
---

# RBAC for agents and MCP tools

Extends, does not repeat, `mcp/authorization.md` (MCP OAuth 2.1, RFC 9728/8707, CIMD, `S707`) and
`auth/role-source-options.md`, `auth/group-claims.md`, `auth/entra-intune-rbac.md` (checkMemberGroups,
group claims/overage, PIM-for-Groups sync latency).

## Summary
- MCP's draft revision (later than the pinned 2026-07-28 spec `mcp/authorization.md` documents) adds a
  named least-privilege mechanism: servers advertise the minimal required scope in a 401's
  `WWW-Authenticate` header, and clients must union rather than replace scopes on step-up. [DOC S2045]
- Claude Code layers two independent tool-level RBAC mechanisms on top of MCP's own auth: a local
  `permissions.mcp_tools` allow/deny list by tool-name pattern, and, for organization-managed connectors,
  a per-tool `ask`/`blocked` setting enforced regardless of the session's permission mode. [DOC S2041]
- Microsoft Entra Agent ID makes "agent identity vs the user's delegated identity" a first-class,
  named platform construct: an agent identity is a credential-less service principal that a shared
  **blueprint** acquires tokens for, in three modes (app token as itself, user token acting on behalf of
  a user, or as a token's audience). Public preview since early 2026. [DOC S2040, S2051]

## Facts

### MCP-level: scope minimization and per-tool authorization
- Not yet in `mcp/authorization.md` (pinned to 2026-07-28): the fetched draft revision requires servers
  to **SHOULD** include a `scope` parameter on their `WWW-Authenticate: Bearer` 401 challenge, "following
  the principle of least privilege and preventing clients from requesting excessive permissions"; clients
  follow a strict priority order — challenge `scope` first, else `scopes_supported` from Protected
  Resource Metadata, which itself is defined as "the minimal set of scopes necessary for basic
  functionality." [DOC S2045]
- Runtime step-up: a tool call with insufficient scope gets `403` + `WWW-Authenticate: Bearer
  error="insufficient_scope", scope="files:write", resource_metadata=...`; the client **MUST** union the
  challenge's scopes with previously granted ones (not replace them) before re-authorizing, and servers
  **MUST** account for scope hierarchies (a broader scope implying narrower ones). [DOC S2045]
- This scope-elevation mechanism is the OAuth-native analogue of a tiered confirmation gate (a system
  that always confirms tier-≥2 actions), but it only applies to HTTP-transport MCP servers; stdio servers
  SHOULD NOT follow the authorization spec at all — unchanged from `mcp/authorization.md`. [DER S2045, S707]

### Claude Code: local and organization tool-level RBAC
- Local rule: `permissions.mcp_tools` is a list of `{pattern, allowed}` entries matching
  `mcp__<server>__<tool>` (or `mcp__plugin_<plugin>_<server>__<tool>` for a plugin-bundled server),
  letting an operator allow/deny individual MCP tools independent of the server's own authentication.
  [DOC S2041]
- Organization-managed connector tools carry a separate, non-overridable per-tool setting: `ask` (always
  prompts, even in `acceptEdits`/`auto`/`bypassPermissions`; denied outright in `dontAsk` mode) or
  `blocked` (filtered out of the tool list before the model ever sees it, in both the desktop app and
  claude.ai chat). `/mcp` shows which setting applies to which tool. [DOC S2041]
- `managed-settings.json` policy applies "above every other level," with a short, documented list of
  security-sensitive exceptions where a *stricter* lower-level value still counts; it carries
  `allowedMcpServers`/`deniedMcpServers` (by server name or URL pattern), `managedMcpServers`
  (organization-supplied server definitions) and `disabledMcpjsonServers` (reject project-scoped
  servers). [DOC S2042]

### Microsoft Entra Agent ID: agent identity as a first-class construct
- An **agent identity** is "a special service principal... that represents an identity that the agent
  identity blueprint created and is authorized to impersonate." It has no credentials of its own. [DOC S2040]
- Three token-acquisition modes, stated explicitly: (a) autonomous agent → app token, subject = agent
  identity; (b) interactive agent called with a user token → user token acquired **on behalf of** the
  agent identity, subject = the user, **actor = the agent identity**; (c) agent identity as the token's
  audience (incoming calls). [DOC S2040]
- All credentials (federated identity credentials, certificates, client secrets) live on the reusable
  **agent identity blueprint**, never on the agent identity; the blueprint acquires tokens on the agent
  identity's behalf. Agent identities are always single-tenant, even when created from a multitenant
  blueprint (which creates one tenant-local agent identity per tenant it's added to), and can only be
  issued tokens in the tenant where they were created. [DOC S2040]
- The blueprint's stated purpose is fleet-wide policy: because every agent identity of one "kind" shares
  a blueprint, an admin can apply one Conditional Access policy, disable all agents of that kind, or
  revoke a permission grant, in a single action across the whole fleet. [DOC S2040]
- Status: public preview via "Microsoft Agent 365, available through Frontier" since early 2026, with a
  stated six-month roadmap for more access-management, security and governance capabilities, and future
  support for Security Copilot, M365 Copilot and third-party agents. [DOC S2051 — reached via WebSearch
  synthesis, not independently WebFetched; see gaps.md]
- Not confirmed whether an agent identity can itself be an eligible PIM member/owner of a role-assignable
  group. [UNK, see gaps.md]

### Role-assignable groups (the PIM-for-Groups prerequisite `entra-intune-rbac.md` assumes)
- A group must have `isAssignableToRole: true` set **at creation time only** — Microsoft's own UI warns
  "creating a group to which Microsoft Entra roles can be assigned is a setting that cannot be changed
  later"; requires Entra ID P1/P2 and `Privileged Role Administrator` to create; cannot be a
  dynamic-membership group; capped at **500 role-assignable groups per tenant**. [DOC S2050]
- PIM for Groups' own activation page states the active-assignment write itself completes "within
  seconds" in both directions (activate and deactivate), separately from how soon a client's *cached*
  token reflects it (covered in `auth/entra-intune-rbac.md`). [DOC S1282]
- PIM will not remove the **last active owner** of a group: if the sole active owner leaves while another
  member holds only an *eligible* (PIM-activatable) ownership, PIM retries deactivating that eligible
  owner's activated ownership for up to **30 days**, then gives up and leaves them permanently active if
  no other active owner was added in that window. [DOC S1282]

### On-behalf-of (OBO) as an agent authorization pattern
- OBO exchanges a token already issued to a middle-tier API for a token to call a downstream API, while
  keeping the *original user's* delegated scopes attached to the *user*, never the calling application —
  "roles remain attached to the principal (the user) and never to the application operating on the user's
  behalf, to prevent the user gaining permission to resources they shouldn't have access to." [DOC S1297]
- OBO only works for **user (delegated)** tokens; a service principal with an app-only token cannot use
  OBO and must use the client-credentials flow instead — relevant to distinguishing an interactive,
  delegated engineer-identity workload acting through a hypothetical middle tier from an app-only
  scheduled/service workload, which could not use OBO at all. [DOC S1297]
- Relaying an access token to the original caller instead of letting it acquire its own is explicitly
  warned against: "DO NOT send access tokens that were issued to the middle tier to anywhere except the
  intended audience," because it raises interception risk and breaks Conditional Access step-up (MFA,
  sign-in frequency) and device-based (MDM, location) policies on the downstream call. [DOC S1297]

### App roles vs group claims, for a service principal / agent specifically (deepening QG25)
- Assigning an app role to a **group that contains a service principal does not produce a `roles` claim**
  for that service principal — Microsoft states this as a current limitation, not a configuration error:
  "Currently, if you add a service principal to a group, and then assign an app role to that group,
  Microsoft Entra ID doesn't add the `roles` claim to tokens it issues." A service principal (the identity
  shape of a scheduled/service workload, or of an Entra Agent ID agent identity acting autonomously) needs
  its **own direct app-role assignment** for the claim to appear — the group-claims convenience
  `auth/group-claims.md` documents for human users does not carry over. [DOC S2053]
- App roles are defined per application registration, can target `Users/Groups`, `Applications`, or both,
  and — when assigned to an application — become **application permissions** requiring admin consent, the
  documented shape for "daemon apps or back-end services that... authenticate and make authorized API
  calls as themselves, without user interaction." [DOC S2053] Microsoft's own stated reason to prefer app
  roles over group claims: an app role's value is fixed by the API's own registration, so "an app using
  groups for authorization will break in the next tenant as both the group ID and name could be
  different" — a portability property groups do not have. [DOC S2053]

### OWASP Non-Human Identities Top 10, mapped to this part's own findings (deepening QG25)
- OWASP's ten NHI risks (2025): NHI1 Improper Offboarding, NHI2 Secret Leakage, NHI3 Vulnerable
  Third-Party NHI, NHI4 Insecure Authentication, NHI5 Overprivileged NHI, NHI6 Insecure Cloud Deployment
  Configurations, NHI7 Long-Lived Secrets, NHI8 Environment Isolation, NHI9 NHI Reuse, NHI10 Human Use of
  NHI. [DOC S2058]
- **NHI7 (Long-Lived Secrets)** names exactly the failure mode this part's GitLab-PAT and
  `keyring`/`msal-extensions` findings in `agents/api-tokens-issue-and-store.md` describe concretely.
  **NHI10 (Human Use of NHI)** — misusing a service identity "for manual tasks that should be performed
  using individual human identities" — is the named risk mitigated by a general policy of "interactive
  calls use the engineer's own identity; shared state written only by scheduled jobs under read-only
  identities," independent of and prior to this OWASP list existing. [DOC S2058; DER — general implication]

### PIM-for-Groups: numbered activation latency, and what it actually measures (deepening QG26)
- Three distinct latency regimes exist under "PIM for Groups," not one: (1) the **active-assignment
  write** itself (adding/removing the group membership or ownership record) completes "within seconds"
  (S1282, reused); (2) **downstream SCIM provisioning** of that membership into a target application takes
  **2-10 minutes**, for "the first five users within a 10-second period activating their group membership
  for a specific application" — a sixth-or-later activation in the same 10-second window instead falls
  back to the **ordinary 40-minute sync cycle** (an explicit, numbered rate limit: "five requests per 10
  seconds," scoped "per enterprise application") (S2052, new); (3) a **client's own cached token** not
  reflecting a membership change until its next acquisition — the case `auth/entra-intune-rbac.md`
  already documents and this part does not repeat. [DOC S2052, S1282; DER: three regimes, not one]
- Microsoft's own documented advice **against** using PIM for Groups where speed matters: "to avoid
  activation delays, use PIM for Microsoft Entra roles instead of PIM for Groups to provide just-in-time
  access to SharePoint, Exchange, or Microsoft Purview portal" — the group-mediated path is measurably
  slower for those workloads, not merely architecturally different. [DOC S2052]
- **Role-assignable and PIM-for-Groups-enabled are independent group properties**: any non-dynamic,
  non-on-prem-synced group can be PIM-for-Groups-enabled regardless of whether it is role-assignable; only
  a role-assignable group can hold an actual Entra role assignment; the **500-group cap applies only to
  role-assignable groups**, not to PIM-for-Groups-enabled groups generally (more than 500 of the latter
  can exist per tenant). A role-assignable group cannot have another group as an *active* member (an
  *eligible* nested membership is still allowed). [DOC S2052]
- **Agent identities remain unconfirmed as PIM-eligible members/owners** of a role-assignable group —
  S2052 (like S2040, S2051) never mentions agent identities in this role. [UNK, see gaps.md]

## Reference
| Mechanism | Grain | Applies to | Source |
|---|---|---|---|
| MCP `WWW-Authenticate: scope=` least-privilege challenge | per resource/operation | HTTP-transport MCP servers only | S2045 |
| MCP step-up (`insufficient_scope`) | per operation, additive | HTTP-transport MCP servers only | S2045 |
| Claude Code `permissions.mcp_tools` | per tool, local policy | any MCP server the client connects to | S2041 |
| Claude Code connector `ask`/`blocked` | per tool, org policy | organization-managed connectors only | S2041 |
| Entra Agent ID agent identity | per agent instance | any product adopting Agent 365 / Agent ID | S2040, S2051 |
| App role on a service principal (direct) | per app registration | agents/service principals; no group claim path | S2053 |
| Role-assignable group + PIM for Groups | per Entra role, per group; 2-10 min app provisioning, "within seconds" write | Entra ID P1/P2 tenants | S2050, S2052, S1282 |
| OBO flow | per downstream API call, user-scoped only | confidential-client middle tiers | S1297 |

## Examples
- Engineer `jan.kowalski` on `PL-LT-00123` runs a stdio MCP server: no MCP OAuth scope challenge
  applies (S707); Claude Code's local `permissions.mcp_tools` rule could still deny a specific
  device-action tool by pattern even though the server itself has no auth boundary.
- If a stdio-only MCP server is ever extended with a remote-MCP path, a tier-≥2 tool could be
  scoped as `device:act` in `scopes_supported`, minimally granted, with any additional scope obtained only
  via the step-up flow (S2045) rather than requesting a broad scope up front.

## Open items
- QG25: MCP/Claude Code tool-level RBAC, Entra agent-identity vs delegated-identity split, app roles vs
  group claims for a service principal, and the OWASP NHI Top 10 mapping — answered. OWASP's
  "Agentic AI – Threats and Mitigations" PDF content specifically was not rendered by WebFetch; see
  gaps.md.
- QG26: PIM-for-Groups write-latency (within seconds), SCIM-provisioning latency (2-10 min, throttled to
  40 min past 5/10s) and role-assignable-group constraints (500-group cap, independence from
  PIM-for-Groups enablement) — answered above. Whether an agent identity can be a PIM-eligible group
  member remains [UNK] after two passes; see gaps.md.
