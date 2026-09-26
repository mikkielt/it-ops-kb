---
topic: auth/workload-identity
priority: P0
applies_to: "Microsoft Entra workload identity federation, Azure Arc-enabled servers (docs current 2026-09-24)"
retrieved_utc: 2026-09-24
sources: [S1302, S1278, S1276, S1289, S1290, S1303, S1304, S1305, S1306, S1307, S1308, S1309]
status: partial
---

# Workload identity: GitLab OIDC federation and Azure Arc managed identity

## Summary
- Entra federated identity credentials let a `ci` (GitLab-hosted) or `site` (Arc-enrolled on-prem host) instance get app-only Graph tokens with no stored client secret or certificate. [DOC S1278, S1289]
- Flexible/wildcard federated identity credential subjects exist as a distinct, separately-documented feature from the classic exact-subject-match FIC. [DOC S1278]
- Azure Arc-enabled servers expose a localhost IMDS-like endpoint with a challenge-response step, so a local, unprivileged process cannot silently mint a token for the host's managed identity. [DOC S1289][DOC S1290]

## Facts
- A federated identity credential (FIC) on an app registration binds `issuer` + `subject` (+ `audience`) to that app; Entra validates the incoming GitLab-issued JWT against those fields and, if it matches, issues a normal app-only access token — no client secret or certificate is exchanged or stored. [DOC S1278, DER from S1276's `sub` values]
- Microsoft documents a separate "mutable subject" / flexible-FIC capability that allows a subject template with variable segments, distinct from the original one-subject-per-credential model; this directly addresses matching multiple GitLab tags without one FIC per tag. [DOC S1278]
- The per-app-registration (or per user-assigned managed identity) limit is **20 federated identity credentials**; FICs don't consume the tenant's service-principal object quota. [DOC S1293]
- Flexible federated identity credentials (status: **preview**) exist precisely to work around that 20-FIC ceiling: one flexible FIC uses a restricted expression language to match a claim (`sub` plus, for GitLab, one or more of `project_id`, `namespace_id`, `user_id`) instead of one exact-match FIC per subject value. [DOC S1294]
- Flexible FIC issuer support is explicitly documented for **GitHub, GitLab, and Terraform Cloud** tokens — GitLab is a supported issuer today (in preview). [DOC S1294]
- A flexible FIC expression has three parts: claim lookup, operator, comparand (e.g. matching `project_id` equals a fixed value, `ref_type` equals `tag`), letting one credential cover `release-*` tag pipelines by matching `project_id` (stable) and `ref_type=tag`, rather than a wildcard on the tag name itself. [DOC S1294]
- Flexible FICs can only be created/managed via Microsoft Graph or the Azure portal (not, e.g., the classic add-federated-credential blade for exact-match FICs). [DOC S1294]
- The FIC `issuer` must be an OIDC-Discovery-compliant URL, and Entra ID uses it to fetch the keys that validate the external token. [DOC S1302]
- So a self-managed GitLab used as issuer must serve `/.well-known/openid-configuration` and its JWKS where Entra ID can fetch them (the public internet); a GitLab reachable only inside the corporate network cannot be a federation issuer. [DER S1302,S1276: Entra fetches keys from the issuer URL]
- For an on-prem host (the `site` kind), Azure Arc-enabled servers provide a system-assigned managed identity; the connected-machine agent exposes a local endpoint (`http://localhost:40342/metadata/identity/oauth2/token`) that issues Entra tokens for that identity. [DOC S1289][DOC S1290]
- Unlike an Azure VM's IMDS, the Arc agent's endpoint uses a challenge-response step: the caller must first read a challenge, then prove it can read a file only a privileged local account can read, before the token is issued — this stops an unprivileged local process on the same host from minting tokens for the managed identity. [DOC S1289]
- This gives the `site` instance a way to get Graph app-only tokens (and Key Vault, Storage, etc.) "without the need to manage a client secret or a certificate" — directly answering QA20 for the on-prem, Arc-enrolled case. [DOC S1289][DOC S1290]
- Arc-enabled servers require the Azure Connected Machine agent installed and the server "Arc-onboarded" to a subscription/resource group (an Azure control-plane object even though the box itself never leaves on-prem); this brings a per-server Azure cost/entitlement and an additional network egress requirement (outbound HTTPS to Arc endpoints), which a design with no gateway/service beyond the CLI and MCP server does not currently budget for. [DER S1289 — Arc introduces an additional always-on agent on the `site` host]

## Reference
| Path to app-only Graph token, no stored secret | Mechanism | Requirement | Source |
|---|---|---|---|
| `ci` (GitLab pipeline) | Entra federated identity credential, `issuer=https://gitlab.com`, `subject` = GitLab `sub` | FIC configured on the `sync`/`runner` app; protected tag/branch | S1278, S1276 |
| `site` (on-prem host) | Azure Arc-enabled server system-assigned managed identity | Connected Machine agent installed, host Arc-onboarded, outbound HTTPS to Arc | S1289, S1290 |

## Examples
- A `sync` app registration, FIC subject `project_path:corp/example-project:ref_type:tag:ref:release-2026.09.24.1` (or the flexible/mutable-subject equivalent for the `release-*` pattern).

## Open items
- QA4 (per-app FIC limit; flexible FIC status): answered — 20 FICs per app/user-assigned managed identity [DOC S1293]; flexible FIC is preview, supports GitLab as an issuer, expression-language matching on `sub`/`project_id`/`namespace_id`/`user_id` [DOC S1294].
- QA20 (Arc managed identity / workload identity federation with no stored secret): answered — both routes exist; Arc adds an extra always-on agent and Azure enrollment not currently in the design, which is a design-affecting finding (see flow-facts.md).

## Update (S1293, S1294)
- 20 FICs/app is comfortably above what a `sync`/`runner` app needs (one flexible FIC can cover the whole `release-*` tag pattern), so the FIC-count ceiling is not itself a design constraint — the 20-limit only matters if many unrelated workloads share one app registration. [DER S1293,S1294]
- Because flexible FIC is preview, not GA, a general preference for stable mechanisms ("CI confirms, never discovers") argues for starting with a small number of exact-match FICs (one per protected tag pattern needed at the outset) rather than adopting the preview expression language before it's GA. [DER S1294]

## Certificate credentials for confidential clients

- MSAL Python's certificate `client_credential` takes a dict of `private_key` (PEM, plain text),
  `thumbprint`, and optionally `public_certificate` and `passphrase`; from 1.29.0 it can instead load a
  PFX file directly via `private_key_pfx_path`, computing the SHA-256 thumbprint automatically. [DOC S1303]
- MSAL Python's documented certificate paths all require the **private key material in a form MSAL
  itself can read** (PEM text or a PFX file it opens) to build the client-assertion JWT signature —
  none of the documented options pass a key reference to a non-exportable CNG/TPM-backed key and let
  Windows CNG sign on MSAL's behalf; **MSAL Python does not appear to support a non-exportable
  CNG/TPM-backed certificate for confidential-client authentication out of the box.** [DER S1303 — no
  CNG/TPM/key-handle-based `client_credential` option is documented]
- `public_certificate` is sent via the JWT's `x5c` header specifically to support Subject Name/Issuer
  (SNI) authentication, which is documented as making certificate rotation easier (the relying party
  matches on issuer+subject rather than a pinned thumbprint). [DOC S1303]
- The client-assertion JWT MSAL builds carries `aud`, `exp`, `iss`, `jti`, `nbf`, `sub` claims (no
  `x5t`/`x5t#S256` header named explicitly in the fetched page's assertion-claims list, though the
  certificate flow uses `thumbprint` to populate the standard `x5t` JWT header per the OAuth client-
  assertion spec this implements). [DOC S1303]
- Certificate rotation: an app registration can hold multiple `keyCredentials` at once; Microsoft's
  security guidance recommends a maximum certificate lifetime of 180 days and rotating on that cadence,
  which multiple concurrent `keyCredentials` entries make possible without downtime (add the new cert,
  cut over, remove the old one). [DOC S1304]
- App instance property lock: for a multitenant app, this locks sensitive properties (including
  credentials of usage type "Sign" and "Verify") from being modified once the app is provisioned in
  another tenant; Microsoft's guidance is to lock every sensitive property available. This is a
  multitenant-app control — a project's single-tenant app registrations (`sync-app`, `client-app`, etc.)
  are not the scenario this protects, so it is not a control such a design needs. [DOC S1304]

### Design implication
- Because MSAL Python's documented certificate credential paths need a PEM/PFX private key MSAL can
  read directly, a "non-exportable CNG/TPM key" idea for key-management options is
  **not directly satisfiable through MSAL Python's own certificate `client_credential` API** as
  documented; achieving hardware-backed non-exportability for a confidential-client credential would
  need a custom client-assertion signer that calls into CNG/TPM itself and hands MSAL only the
  resulting JWT (MSAL supports supplying a pre-built `client_assertion` callable), not something
  confirmed by a source in this pass — flagged [UNK].

## Conditional Access and CAE for workload identities

- Conditional Access policies scoped to service principals ("workload identities") require a
  **Workload Identities Premium** licence to create or modify; in an unlicensed tenant, existing such
  policies keep running but cannot be changed. [DOC S1305]
- Scope is **single-tenant service principals registered in the tenant only** — third-party SaaS and
  multitenant apps are out of scope; a policy assigned to a *group* containing a service principal is
  **not enforced** for that service principal — it must be assigned to the service principal directly.
  [DOC S1305]
- Supported conditions are location (block outside known public IP ranges) and risk (Entra ID
  Protection workload-identity risk detections); this is a narrower condition set than user Conditional
  Access. [DOC S1305]
- CAE for workload identities extends this to real-time enforcement: it applies **only to access
  requests made to Microsoft Graph as the resource provider**, only to **single-tenant service
  principals**, and explicitly **does not currently support managed identities** (so a `site` instance
  authenticating via Arc managed identity is out of CAE-for-workload-identities' scope, even though it
  is in scope for the plain Conditional-Access-for-workload-identities location/risk policies above,
  which are not stated as excluding managed identities the way CAE is). [DOC S1306]
- To opt in, the service principal's token request must declare the `cp1` client capability in its
  `claims` parameter (same capability name as user-flow CAE, S1296), and Entra then issues a CAE-
  enabled token; workload-identity CAE tokens are long-lived (**up to 24 hours**) rather than the
  ~1 hour default. [DOC S1306]
- Net effect: a `ci`/`site` app-only Graph call through a plain (certificate or FIC)
  confidential-client credential can be brought under location/risk Conditional Access with a Workload
  Identities Premium licence; near-real-time revocation via CAE specifically requires the caller to be
  a service principal (not a managed identity) opted in with `cp1` — so choosing the Arc-managed-
  identity route for `site` (workload-identity.md above) trades away CAE-for-workload-identities'
  real-time revocation for the "no stored secret" benefit. [DER S1306, S1289]

## Azure Arc managed identity: cost and app-role assignment

- The Azure Arc **core control plane** (resource representation, tags, Azure Resource Graph search,
  RBAC, and the ability to run extensions, SSH, Run Command, Custom Script Extension) is free; you only
  pay for optional add-on services layered on top (e.g. Defender for Servers Plan 1 $5/server/month,
  Plan 2 $15/server/month; Azure Policy guest configuration ~$6/server/month). The managed identity
  itself, as a core-control-plane capability, is not separately billed. [DOC S1307]
- Assigning a Graph app role (application permission) to a managed identity's service principal is
  **not exposed in the Entra/Azure portal** for managed identities the way it is for a normal app
  registration; Microsoft's documented path is PowerShell (`New-MgServicePrincipalAppRoleAssignment`,
  needing the managed identity's service-principal object id, the resource API's service-principal
  object id, and the app role id) or the equivalent Graph API call. [DOC S1308][DOC S1309]

## Reference (additions)
| Control | Applies to | Licence | Source |
|---|---|---|---|
| Conditional Access for workload identities (location/risk) | single-tenant service principals, direct assignment only | Workload Identities Premium | S1305 |
| CAE for workload identities | single-tenant service principals calling Microsoft Graph; **not** managed identities | Workload Identities Premium (implied by S1305's general licensing) | S1306 |
| Arc core control plane incl. managed identity | any Arc-onboarded server | free | S1307 |
| App-role assignment to a managed identity | any managed identity | PowerShell/Graph only, no portal UI | S1308, S1309 |

- See also `entra/agent-id.md`: an agent identity blueprint's federated identity credentials follow the
  same Entra FIC mechanics documented here, applied to the `agentIdentityBlueprint` application resource
  instead of an ordinary app registration.
- See also `windows/azure-arc-servers.md`: the azcmagent CLI/config, agent networking and logs, extension
  and Machine Configuration governance, and ESU/Hotpatch-via-Arc facts around the same Arc-enabled server
  whose managed identity is documented here.

## Open items (additions)
- Certificate credentials + non-exportable CNG/TPM key: MSAL Python's documented certificate options
  need a readable private key (PEM/PFX); no documented option accepts a CNG/TPM key handle directly.
  [DER, see gaps.md for the exact follow-up: whether MSAL's `client_assertion` callable parameter is
  the supported escape hatch for a custom CNG/TPM signer]
- CAE for workload identities explicitly excludes managed identities — a directly relevant constraint
  for the `site` Arc-managed-identity design (see above).
