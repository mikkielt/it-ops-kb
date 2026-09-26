---
topic: arch/k8s-gmsa-windows
priority: P1
applies_to: "Kubernetes (kubernetes.io, stable since v1.18), Windows containers (Windows Server 2019+), AKS/AKS Arc (docs current 2026-09-24)"
retrieved_utc: 2026-09-26
sources: [S1600, S1601, S1602, S1603]
status: complete
---

# gMSA for Windows containers and Kubernetes

## Summary
- Windows containers get a gMSA identity through a **CredentialSpec** file that Docker/containerd reads; on a domain-joined container host this is a direct AD lookup, on a non-domain-joined host it goes through a **ccg.exe plug-in** (`ICcgDomainAuthCredentials`); Windows Server itself ships none, AKS ships one for Azure Key Vault (S1602). [DOC S1601], extends `windows/gmsa.md`.
- Kubernetes wraps the same CredentialSpec mechanism in a `GMSACredentialSpec` CRD plus an admission webhook (`kubernetes-sigs/windows-gmsa`) that expands `securityContext.windowsOptions.gmsaCredentialSpecName` into the full credspec JSON on the pod. [DOC S1600]
- Kubernetes' own gMSA feature assumes **domain-joined Windows nodes**; the node needs AD access to retrieve the password (`Test-ADServiceAccount`-style access), same as a bare-metal host. [DOC S1600]
- AKS's gMSA path requires classic AD DS or on-prem AD (not Entra ID), but its Windows nodes are **not** domain-joined: a standard domain user credential stored in Azure Key Vault is read by the kubelet managed identity through a CCG plug-in named in the credential spec (`PluginGUID {CCC2A336-D7F3-4818-A213-272B7924213E}`, `PluginInput ObjectId=...;SecretUri=...`). So Microsoft does ship a CCG plug-in, for AKS with Key Vault. [DOC S1602]
- A gMSA under a Windows container gets ordinary Kerberos: the computer/container identity can get service tickets for HTTP SPNs (AdminService) and `MSSQLSvc` SPNs (SQL) exactly as a domain-joined Windows host would, because from AD's point of view it is the same machine/service-account Kerberos flow — this is a derivation from the existing `windows/gmsa.md` facts, not a new Kubernetes-specific claim.

## Facts
- The `GMSACredentialSpec` CRD stores the credential spec cluster-wide as YAML/JSON (`ActiveDirectoryConfig.GroupManagedServiceAccounts`, `CmsPlugins`, `DomainJoinConfig`); it contains no secret, only AD metadata (domain SID, gMSA name, scope). [DOC S1600]
- Two admission webhooks from `kubernetes-sigs/windows-gmsa` are required: a mutating webhook that expands the named `GMSACredentialSpec` reference into the full JSON on the pod spec, and a validating webhook that checks the pod's service account is authorized (via RBAC `use` verb) to reference that credspec. [DOC S1600]
- `securityContext.windowsOptions.gmsaCredentialSpecName` is settable at pod level (all containers) or per-container (overrides pod level); this feature has been Stable since Kubernetes v1.18. [DOC S1600]
- Kubernetes' gMSA doc states Windows worker nodes "must be configured in Active Directory to access the secret credentials associated with the desired GMSA" — i.e. domain-joined nodes, no non-domain-joined/ccg.exe path documented at the Kubernetes level. [DOC S1600]
- Multiple pods/containers can reference and use the *same* gMSA simultaneously via RBAC role bindings on the shared `GMSACredentialSpec`, subject to the same AD-side host/hostname caveats as bare containers (see next facts). [DOC S1600, S1601]
- On Windows Server 2019+, using one gMSA across more than one container running simultaneously with an explicit `--hostname` can hit a documented race condition against the DC unless each container's `--hostname` is unique — a container identity/naming caveat that also applies inside Kubernetes pods that set a hostname. [DOC S1601]
- Non-domain-joined container hosts need the credential-spec `HostAccountConfig` section (`PortableCcgVersion: "1"`, `PluginGUID`, `PluginInput`) and a **plug-in DLL/COM object implementing `ICcgDomainAuthCredentials`** that talks to a secret store; Windows does not ship a built-in plug-in. This is the Container Credential Guard (`ccg.exe`) mechanism — Microsoft's own broker-like indirection for the non-domain-joined case, but the plug-in itself is not provided by Microsoft (it must be sourced or written). [DOC S1601]
- Non-domain-joined-host events land in `Microsoft-Windows-Containers-CCG` (Event Viewer), confirming `ccg.exe` is the mediator between the container runtime and the plug-in/secret store on hosts that are not in the domain. [DOC S1601]
- AKS's documented gMSA path requires AD DS or on-prem AD — "At this time, you can't use Microsoft Entra ID to configure GMSA with an AKS cluster" — plus a Key Vault holding "a standard domain user credential to access the GMSA credential", the kubelet identity granted `get` on that secret, and the domain controller reachable (AD Web Services on 9389, DNS including TCP 53). The node pools are not domain-joined; the credential spec's `HostAccountConfig` names the AKS Key Vault CCG plug-in. [DOC S1602]
- No Microsoft or kubernetes.io page states a Windows-Server-version floor different from the general Windows container gMSA requirement (Windows Server 2019+ for the fixes noted above; Windows Server 2016/1709/1803 has the extra "hostname must equal gMSA SAM name" limitation, fixed in 2019). [DOC S1601]
- Kerberos to AdminService (HTTP SPN) and SQL (`MSSQLSvc` SPN) from a gMSA-identified Windows container: no doc found that calls this out explicitly for containers, but it follows directly from the existing gMSA Kerberos facts in `windows/gmsa.md` (correct SPNs + DNS + firewall + supported enc types) — the container's network identity *is* the gMSA computer/service identity once CCG/`ADServiceAccount` resolves it, so an SPN'd HTTP or SQL service is reachable the same way. [DER S400,S1600,S1601: same Kerberos ticket-request path, container vs. bare host]

## Reference
| Path | Node/host domain-joined? | Mechanism | Plug-in needed? |
|---|---|---|---|
| Windows container, domain-joined host | Yes | CredentialSpec → direct AD lookup | No |
| Windows container, non-domain-joined host | No | CredentialSpec `HostAccountConfig` → `ccg.exe` → plug-in → secret store | Yes (bring-your-own) |
| Kubernetes (upstream) | Yes (documented requirement) | `GMSACredentialSpec` CRD + admission webhook, same underlying CredentialSpec | No (assumes domain-joined nodes) |
| AKS gMSA (AD DS / on-prem AD only) | No | CredentialSpec `HostAccountConfig` → `ccg.exe` → AKS Key Vault plug-in → standard domain user secret | Yes (shipped by AKS) |

## Examples
- Fixture: a Windows container running on `PL-SRV-0042` (domain-joined) with `MachineAccountName: gmsa-example-sync`, `Scope: corp.example.com`, retrieving Kerberos tickets to call `HTTP/adminservice.corp.example.com` and `MSSQLSvc/PL-SRV-0042.corp.example.com:1433` — same SPN pattern as `windows/gmsa.md`'s bare-host example, just inside a container.
