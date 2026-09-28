---
topic: arch/workload-identity-onprem-k8s
priority: P1
applies_to: "Microsoft Entra Workload ID, Azure Arc-enabled Kubernetes (GA since agent 1.32.7), SQL Server 2022/2025 Arc (docs current 2026-09-24)"
retrieved_utc: 2026-09-28
sources: [S1609, S1206, S1207, S-snz3myo2, S1200, S-vspquxtf]
status: complete
---

# Entra workload identity federation for on-prem/self-managed Kubernetes

## Summary
- Workload identity federation needs the cluster to act as an OIDC token issuer: Entra must be able to reach `{IssuerURL}/.well-known/openid-configuration` and `{IssuerURL}/openid/v1/jwks` to validate the projected service-account token before exchanging it for an Entra token — i.e. the issuer discovery + JWKS endpoints must be publicly (Entra-)reachable. [DOC S1609, S-vspquxtf]
- Self-managed/on-prem clusters get this through **Azure Arc-enabled Kubernetes workload identity federation**, generally available since agent 1.32.7 (February 2026) though the conceptual page is still labelled preview, requiring Arc agent version ≥1.21, Azure CLI ≥2.64, `az connectedk8s` ≥1.10.0. [DOC S1609]
- The federated credential subject is `system:serviceaccount:<namespace>:<service-account-name>` (the Arc deploy guide passes it to `az identity federated-credential create --subject`). [DOC S-snz3myo2]
- Service accounts map to Entra objects one-to-one, many-to-one or one-to-many (via changing the client-ID annotation). [DOC S1609]
- Workload identity replaces app-only Graph auth (no stored secret), but it is Entra-token-only: it does **not** give Kerberos to AdminService/LDAP/SMB, and only reaches SQL Server on-prem if that SQL Server instance is itself configured for Entra authentication (via Azure Arc, or for SQL Server on Windows the manual non-Arc setup) (extends `auth/sql-authz.md`). [DER from S1207, S1609]

## Facts
- OIDC issuer requirement, stated as a table in the Arc doc: `{IssuerURL}/.well-known/openid-configuration` (the discovery document, issuer metadata) and `{IssuerURL}/openid/v1/jwks` (public signing keys) are the two endpoints Entra ID needs to validate the service-account token. [DOC S1609]
- The Arc-enabled Kubernetes cluster itself acts as the OIDC token issuer using Kubernetes' built-in Service Account Token Volume Projection; no separate token-issuing service is introduced. [DOC S1609]
- Feature status: the conceptual page title still says "(preview)", while the release notes announce general availability with agent 1.32.7 (see below); requires Arc agent version 1.21+ on the cluster, and current Azure CLI / `az connectedk8s` versions on the operator side. [DOC S1609]
- Federated identity credential (FIC) mapping options: one service account → one Entra object (typical), many service accounts → one Entra object, or one service account → many Entra objects (via distinct client-ID annotations per binding). [DOC S1609]
- Current limitations: max 20 FICs per managed identity (same limit already recorded in `auth/workload-identity.md` S1293); new FICs take a few seconds to propagate; FIC creation on user-assigned managed identities is unsupported in certain regions. [DOC S1609]
- No key-rotation mechanism is described beyond ordinary Kubernetes service-account token rotation (short-lived projected tokens, refreshed by the kubelet) — Entra never sees a long-lived secret to rotate because the whole point of federation is to avoid one. [DOC S1609]
- Workload identity federation is scoped to Entra-protected resources (Graph, Key Vault, Blob Storage, Azure SQL/Arc SQL with Entra auth) reached via the Azure Identity client libraries or MSAL; it is not a general Kerberos/NTLM replacement and carries no ability to reach classic on-prem AdminService (HTTP Kerberos SPN), LDAP, or SMB, none of which are Entra-protected resources. [DER from S1609's scope + DOC S1200-series Kerberos facts already in kb]
- SQL Server 2022+ on-prem Entra authentication is set up through Azure Arc, or for SQL Server on Windows through a documented manual non-Arc setup; SQL Server 2025's "primary managed identity" needs an Arc connection and the latest Azure Extension for SQL Server. So workload identity federation for a Kubernetes-hosted tool would still need the *target* SQL Server to be separately Entra-auth-configured — workload identity federation alone does not make an arbitrary on-prem SQL Server reachable. [DER S1206, S1207, S1609: the server-side prerequisites come from S1206/S1207; federation only issues the client token]

## Reference
| Question | Answer | Source |
|---|---|---|
| Does Entra Workload ID for self-managed/on-prem K8s exist and is it GA? | Exists, documented for Azure Arc-enabled Kubernetes; GA since agent 1.32.7 (release notes), conceptual page still says preview | DOC S1609, S-vspquxtf |
| What must be publicly reachable? | `{issuer}/.well-known/openid-configuration` and `{issuer}/openid/v1/jwks` | DOC S1609 |
| FIC subject format | `system:serviceaccount:<ns>:<sa>` | DOC S-snz3myo2 |
| Does workload identity replace Kerberos for AdminService/LDAP/SMB? | No — those are not Entra-protected resources | DER |
| Does workload identity reach on-prem SQL Server directly? | Only if that SQL Server is itself Entra-auth-configured (Arc, or manual non-Arc setup on Windows; separate requirement) | DER S1206,S1207,S1609 |

## Examples
- Fixture: a tool's `sync` role running as a Kubernetes pod in a self-managed cluster, Arc-enrolled, with service account `system:serviceaccount:example-ns:example-sync-sa` federated to an Entra app registration for Graph-only calls (roster pulls). SQL, AdminService, LDAP and SMB access for the same pod would still need one of the other mechanisms in `arch/k8s-gmsa-windows.md` / `arch/kerberos-linux-containers.md`.

## Gaps
- Workload identity federation for Arc-enabled Kubernetes became generally available with agent version 1.32.7 (February 2026); the conceptual page's title still says "(preview)". [DOC S-vspquxtf]
