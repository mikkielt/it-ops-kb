---
topic: auth/workload-identity
priority: P0
applies_to: "Microsoft Entra workload identity federation, Azure Arc-enabled servers (docs current 2026-09-24)"
retrieved_utc: 2026-09-27
sources: [S1302, S1278, S1276, S1289, S1290, S1293, S1294, S1296, S1303, S1304, S1305, S1306, S1308, S1309, S-w6ryunvm, S-e2hdn5as, S-uoxtujn6, S-rye46ky7, S-zb4abl74, S-ftk5lzj7, S-wk6ahp72, S-5qxktcen, S-gyp6fxzq]
status: complete
---

# Workload identity: GitLab OIDC federation and Azure Arc managed identity

## Summary
- Entra federated identity credentials let a `ci` (GitLab-hosted) or `site` (Arc-enrolled on-prem host) instance get app-only Graph tokens with no stored client secret or certificate. [DOC S-w6ryunvm, S1289]
- Flexible/wildcard federated identity credential subjects exist as a distinct, separately-documented feature from the classic exact-subject-match FIC. [DOC S1278]
- Azure Arc-enabled servers expose a localhost IMDS-like endpoint with a challenge-response step, so a local, unprivileged process cannot silently mint a token for the host's managed identity. [DOC S1290]

## Facts
- A federated identity credential (FIC) on an app registration binds `issuer` + `subject` (+ `audience`) to that app; Entra checks the incoming external token's `issuer`, `sub` and `aud` against those values and, if they match, issues an access token — no client secret or certificate has to be managed. [DOC S1293, S-w6ryunvm]
- Microsoft's "mutable subjects" page is a risk article, not a matching feature: a `sub` built from renameable names (GitLab's default leads with `project_path`) can be recycled by another party, so it recommends trusting an immutable subject (GitLab can lead `sub` with `project_id` via `ci_id_token_sub_claim_components`) and deleting dangling FICs. [DOC S1278]
- Matching several GitLab tags without one FIC per tag is the flexible FIC feature (S1294): the mutable-subjects page shows a flexible FIC matching `claims['sub'] matches 'project_id:<id>:*'`. [DOC S1278]
- The per-app-registration (or per user-assigned managed identity) limit is **20 federated identity credentials**; FICs don't consume the tenant's service-principal object quota. [DOC S1293]
- Flexible federated identity credentials (status: **preview**) exist precisely to work around that 20-FIC ceiling: one flexible FIC uses a restricted expression language to match the incoming `sub` claim (and certain allowed custom claims) instead of one exact-match FIC per subject value. [DOC S1294]
- For GitLab, the flexible FIC page lists only `sub` (`eq`, `matches`) and `project_id` (`eq`) as supported claims, and requires `sub` plus `project_id` when the subject is mutable. [DOC S1294]
- The mutable-subjects page instead says a GitLab flexible FIC must match `sub` and one or more of `project_id`, `namespace_id`, `user_id`, whether `sub` leads with `project_path` or `project_id`. [DOC S1278]
- Flexible FIC issuer support is explicitly documented for **GitHub, GitLab, and Terraform Cloud** tokens — GitLab is a supported issuer today (in preview). [DOC S1294]
- A flexible FIC expression has three parts: claim lookup (`claims['<name>']`), operator (`matches` with `?`/`*` wildcards, `eq`, joined by `and`), and a single-quoted comparand. [DOC S1294]
- So one credential can cover `release-*` tag pipelines with a wildcard inside `sub` (e.g. `claims['sub'] matches 'project_id:<id>:ref_type:tag:ref:release-*' and claims['project_id'] eq '<id>'`); `ref_type` is not a separately matchable GitLab claim. [DER S1294, S1278: GitLab supports only `sub` and `project_id`, and `matches` allows `*` in `sub`]
- Azure CLI, Azure PowerShell and Terraform providers have no explicit flexible FIC support (they error on create, and on reading one made elsewhere); configure it through Microsoft Graph or the Azure portal, or with `az rest` against Graph (apps) or Azure Resource Manager (user-assigned managed identities). [DOC S1294]
- The FIC `issuer` must be an OIDC-Discovery-compliant URL, and Entra ID uses it to fetch the keys that validate the external token. [DOC S1302]
- So a self-managed GitLab used as issuer must serve `/.well-known/openid-configuration` and its JWKS where Entra ID can fetch them (the public internet); a GitLab reachable only inside the corporate network cannot be a federation issuer. [DER S1302,S1276: Entra fetches keys from the issuer URL]
- For an on-prem host (the `site` kind), Azure Arc-enabled servers provide a system-assigned managed identity; the connected-machine agent exposes a local endpoint (`http://localhost:40342/metadata/identity/oauth2/token`) that issues Entra tokens for that identity. [DOC S1289, S1290]
- The Arc agent's endpoint answers any local process, but a request that would return a token must carry a secret: the first call's `WWW-Authenticate` header names a file, and the caller sends that file's content back as a Basic authorization value. Only higher-privileged users can read the file (the docs require local Administrators or Hybrid Agent Extension Applications on Windows, `himds` on Linux), which stops an unprivileged local process from minting tokens. [DOC S1290]
- This gives the `site` instance a way to get Graph app-only tokens (and tokens for Azure services such as Key Vault or Storage) without storing credentials on the host — directly answering QA20 for the on-prem, Arc-enrolled case. [DOC S1289, S1290, S1308]
- Arc-enabled servers require the Azure Connected Machine agent installed and the server "Arc-onboarded" to a subscription/resource group (an Azure control-plane object even though the box itself never leaves on-prem); this brings a per-server Azure cost/entitlement and an additional network egress requirement (outbound HTTPS to Arc endpoints), which a design with no gateway/service beyond the CLI and MCP server does not currently budget for. [DER S1289 — Arc introduces an additional always-on agent on the `site` host]

## Reference
| Path to app-only Graph token, no stored secret | Mechanism | Requirement | Source |
|---|---|---|---|
| `ci` (GitLab pipeline) | Entra federated identity credential, `issuer=https://gitlab.com`, `subject` = GitLab `sub` | FIC configured on the `sync`/`runner` app; protected tag/branch | S1278, S1276 |
| `site` (on-prem host) | Azure Arc-enabled server system-assigned managed identity | Connected Machine agent installed, host Arc-onboarded; token caller in local Administrators or Hybrid Agent Extension Applications (Windows) or `himds` (Linux) | S1289, S1290 |

## Examples
- A `sync` app registration, FIC subject `project_path:corp/example-project:ref_type:tag:ref:release-2026.09.24.1` (or the flexible/mutable-subject equivalent for the `release-*` pattern).

## Open items
- QA4 (per-app FIC limit; flexible FIC status): answered — 20 FICs per app/user-assigned managed identity [DOC S1293]; flexible FIC is preview, supports GitLab as an issuer, expression-language matching on `sub` and `project_id` [DOC S1294] (the mutable-subjects page also names `namespace_id` and `user_id`, see Facts).
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
  (SNI) authentication, which is documented as an approach that allows easier certificate rotation. [DOC S1303]
- The default claims MSAL signs into its client assertion are `aud` (the token endpoint), `iss` and
  `sub` (the client id), `exp` (now + 10 minutes), `iat` and `jti`; `client_claims` can add or override
  claims. A pre-signed assertion passed as `client_assertion` is described as a JWT with `aud`, `exp`,
  `iss`, `jti`, `nbf` and `sub`, and a callable may be passed so MSAL fetches a fresh one on demand. [DOC S1303]
- Microsoft recommends limiting application certificate lifetime to 180 days (rotate at least every
  180 days, shorter for highly sensitive apps) and automating rotation with Azure Key Vault; an
  application management policy can enforce the limit on `keyCredentials`. [DOC S-e2hdn5as]
- Rotation without downtime: register the new certificate alongside the existing one, since Entra ID
  accepts tokens signed by any registered certificate, then switch the app and remove the old one;
  `keyCredentials` is multi-valued, so several certificates can be registered at once. [DOC S-rye46ky7, S-zb4abl74]
- App instance property lock: for a multitenant app, this locks sensitive properties (credentials of
  usage type `Sign` or `Verify`, and `tokenEncryptionKeyId`) from being modified after the app is
  provisioned in another tenant; the lock can cover all properties at once and is on by default for apps
  created in the Microsoft Entra admin center. It is a multitenant-app control, so single-tenant app
  registrations (`sync-app`, `client-app`, etc.) are not the scenario it protects. [DOC S1304]

### Design implication
- MSAL Python's certificate `client_credential` options need a private key MSAL can read (PEM or PFX),
  so a non-exportable CNG/TPM key cannot go through them; MSAL does accept a completely pre-signed
  `client_assertion` (since 1.13.0) or a callable that returns one, so a custom signer that calls CNG/TPM
  can build the JWT and MSAL only carries it. [DOC S-ftk5lzj7; CODE S-wk6ahp72: msal/application.py#ClientApplication.__init__]
  That Entra accepts such an assertion from a non-exportable key end to end is a lab check (see
  `auth/key-management-options.md`). [DER S-ftk5lzj7, S-zb4abl74]

## Conditional Access and CAE for workload identities

- Conditional Access policies scoped to service principals ("workload identities") require a
  **Workload Identities Premium** licence to create or modify; in an unlicensed tenant, existing such
  policies keep running but cannot be changed. [DOC S1305]
- Scope is **single-tenant service principals registered in the tenant only** — third-party SaaS and
  multitenant apps are out of scope; a policy assigned to a *group* containing a service principal is
  **not enforced** for that service principal — it must be assigned to the service principal directly.
  [DOC S1305]
- Policies can block service principals from outside known public IP ranges, based on Entra ID
  Protection risk, or in combination with authentication contexts; **Block access** is the only grant
  control. [DOC S1305]
- Managed identities aren't covered by Conditional Access for workload identities (Microsoft suggests
  access reviews for them instead). [DOC S1305]
- CAE for workload identities extends this to real-time enforcement: it applies **only to access
  requests made to Microsoft Graph as the resource provider**, only to **single-tenant service
  principals**, and explicitly **does not currently support managed identities** (so a `site` instance
  authenticating via Arc managed identity is out of its scope, as it is for plain Conditional Access
  for workload identities). [DOC S1306]
- To opt in, the service principal's token request must declare the `cp1` client capability in its
  `claims` parameter, and Entra then issues a CAE-enabled token; workload-identity CAE tokens are
  long-lived (**up to 24 hours**); when Entra and the resource see different IP addresses, Entra issues
  a one-hour CAE token instead. [DOC S1306]
- `cp1` is the same client capability MSAL apps declare for user-flow CAE. [DOC S1296]
- Net effect: a `ci`/`site` app-only Graph call through a plain (certificate or FIC)
  confidential-client credential can be brought under location/risk Conditional Access with a Workload
  Identities Premium licence, and under CAE if it opts in with `cp1`; a managed identity is excluded
  from both, so choosing the Arc-managed-identity route for `site` trades away Conditional Access and
  CAE for workload identities for the "no stored secret" benefit. [DER S1305, S1306, S1289: both pages
  exclude managed identities; S1289 is the Arc managed identity route]

## Azure Arc managed identity: cost and app-role assignment

- The Azure Arc-enabled servers control plane (management groups and tags, Azure Resource Graph
  search and indexing, Azure RBAC, templates and extensions) comes at no extra cost; any Azure service
  used on the server (e.g. Defender for Cloud, Azure Monitor) is billed at that service's pricing. [DOC S-uoxtujn6]
- Defender for Servers list prices (Azure Retail Prices API, westeurope, USD, read 2026-09-27): Plan 1
  $0.00672 per node per hour, Plan 2 $0.02 per node per hour. [DOC S-5qxktcen] No page states the Arc
  managed identity's own price; it belongs to the control plane billed at no extra cost. [DER S-uoxtujn6]
  Guest configuration prices were not looked up.
- Assigning an app role (application permission, e.g. for Microsoft Graph) to a managed identity's
  service principal is documented with PowerShell (`New-MgServicePrincipalAppRoleAssignment`) or Azure
  CLI, needing the managed identity's service-principal object id, the resource API's service-principal
  object id, and the app role id; role changes can take significant time to apply because tokens are
  cached. [DOC S1308, S1309]
- No portal step is documented for this assignment: the PowerShell page uses Microsoft Graph cmdlets,
  and the Azure CLI page says the functionality isn't directly exposed in the CLI and uses a REST call to
  Graph instead. [DER S1308, S-gyp6fxzq: only PowerShell and REST paths documented]

## Reference (additions)
| Control | Applies to | Licence | Source |
|---|---|---|---|
| Conditional Access for workload identities (location/risk) | single-tenant service principals, direct assignment only | Workload Identities Premium | S1305 |
| CAE for workload identities | single-tenant service principals calling Microsoft Graph; **not** managed identities | Workload Identities Premium | S1306 |
| Arc control plane (tags, Resource Graph, RBAC, templates/extensions) | any Arc-onboarded server | no extra cost | S-uoxtujn6 |
| App-role assignment to a managed identity | any managed identity | PowerShell or Azure CLI (documented path) | S1308, S1309 |

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
