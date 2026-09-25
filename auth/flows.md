---
topic: auth/flows
priority: P0
applies_to: "ConfigMgr 2509+, Windows 11 24H2 / Windows Server 2025, Entra ID, SQL Server 2022/2025, GitLab"
retrieved_utc: 2026-09-24
sources: [S300, S301, S307, S311, S468, S469, S512, S518, S521, S621, S1201, S1202, S1205, S1208, S1215, S1228, S1270, S1276, S1286, S1289, S1293, S1297, S1298, S1302, S1345, S1347]
status: partial
---

# Identity flows

## Summary
- One row per flow (instance kind × target) in [flows.csv](flows.csv); least privilege per operation in [permissions-matrix.csv](permissions-matrix.csv).
- Current flows F01-F09 cover `client`, `site` and `ci`. F10 is an option (GitLab federation). F11-F14 are later flows for a broader deployment.
- Per-protocol detail lives in the topic files: [kerberos](kerberos.md), [ntlm-deprecation](ntlm-deprecation.md), [ldap-smb-signing](ldap-smb-signing.md), [gmsa-dmsa](gmsa-dmsa.md), [msal-public-client](msal-public-client.md), [workload-identity](workload-identity.md), [configmgr-rbac-auth](configmgr-rbac-auth.md), [sql-authz](sql-authz.md), [gitlab-ci-identity](gitlab-ci-identity.md). Revocation timing: [revocation](revocation.md).

## Facts
- The AdminService rejects NTLM from ConfigMgr 2509, so F01 and F07 work only when Kerberos works (FQDN, `HTTP/<fqdn>` SPN). [DOC S307]
- The AdminService applies ConfigMgr RBAC and the SMS Provider authentication level; the caller must be a ConfigMgr administrative user. [DOC S300,S311]
- The AdminService uses a self-signed site certificate on 443 unless a PKI certificate is bound, so a Python client must either trust that certificate or the site must bind a PKI one. [DER S301]
- Windows 11 24H2 Enterprise/Pro/Education require SMB signing (outbound and inbound) and Windows Server 2025 requires outbound signing; encryption is optional. F09 needs a share that signs. [DOC S1202,S1228]
- `ldap3` cannot provide LDAP-layer signing or sealing, so with a DC that requires signing, F06 from `ldap3` needs LDAPS. [DER S1201,S1208]
- A signed-in engineer's role check against a small set of role groups fits one `/me/checkMemberGroups` call under delegated `User.Read` (at most 20 group ids). [DOC S1286]
- Workload identity federation (F10) allows at most 20 federated credentials per app, and Entra fetches the issuer's OIDC keys, so a GitLab issuer must be reachable by Entra. [DOC S1293; DER S1302]
- An on-prem host can get app-only tokens without a stored secret through an Azure Arc managed identity, at the price of the Arc agent and an Azure resource per host. [DOC S1289]
- Accounts marked "sensitive and cannot be delegated", or in Protected Users, cannot be delegated by a broker (F12 via KCD). [DOC S1298,S1205]
- On-behalf-of works only for delegated tokens whose audience is the broker itself. [DOC S1297]
- `revokeSignInSessions` stops refresh tokens within minutes; an issued access token keeps working until it expires unless the resource enforces CAE. [DOC S1345,S1347]

## Reference
See [flows.csv](flows.csv): `flow_id, status (current|option|later), kind, target, protocol, identity, credential_and_storage, transport_and_key_exchange, minimal_permission, revocation_and_delay, sources`.

## Examples
- `client` on `PL-LT-00123` as `jan.kowalski` → `https://PL-SRV-0042.corp.example.com/AdminService/wmi/SMS_R_System` with a Kerberos ticket for `HTTP/PL-SRV-0042.corp.example.com` (F01).
- `site` on `PL-SRV-0042` as `corp\gmsa-sync$` → LDAPS to a DC of `corp.example.com` (F06).
