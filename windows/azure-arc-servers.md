---
topic: windows/azure-arc-servers
priority: P2
applies_to: "Azure Arc-enabled servers, Azure Connected Machine agent (azcmagent), Azure Machine Configuration (docs current 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-gma7exwg, S-arygyiia, S-ojs4qilv, S-3ajkoikd, S-lpj5aefn, S-szyeetyp, S-efadnhwv, S-nevhri3m, S-5d7caeeq, S-h7fejg6k, S-oacfa6ee, S-wwbtoald, S-jfzhzjgu, S-nibv7ci5, S-4xar7ise, S-zfc5iphl, S-w3pkna2x, S-ldykf7ob, S-wftu7kvv, S-ucwyn46f, S-d4ny3ufk, S-epoqec7s]
status: partial
files: [windows/azcmagent-config.csv]
---

# Azure Arc-enabled servers: Connected Machine agent, networking, extensions, and Machine Configuration

## Summary
- Azure Arc-enabled servers projects a non-Azure Windows or Linux machine into Azure as a resource, via the **Azure Connected Machine agent**, whose CLI is `azcmagent`; on-prem managed identity/token mechanics for the agent are already covered in `auth/workload-identity.md` and are not repeated here. [DOC S-arygyiia, S-wwbtoald]
- The agent communicates outbound only, over TCP 443, to a fixed set of Azure endpoints (no inbound ports required for the agent itself); `azcmagent config` manages local, per-machine settings such as the extension allow/block lists, proxy, monitor mode, and incoming-connection controls. Full config-key table: `windows/azcmagent-config.csv`. [DOC S-szyeetyp, S-gma7exwg]
- Azure Machine Configuration (formerly Azure Policy Guest Configuration) extends Azure Policy inside the OS using PowerShell DSC (v2 on Windows, v3 on Linux) as its validation engine, applying policy effects `AuditIfNotExists`/`DeployIfNotExists`; it is a separate product from this kb's DSC v3 CLI coverage in `dsc/` — see Reference below for how the two relate. [DOC S-epoqec7s, S-4xar7ise]
- Windows Server 2012/2012 R2 Extended Security Updates and Windows Server 2025 Hotpatch can both be delivered to on-prem/other-cloud machines via Arc enrollment, billed pay-as-you-go through Azure rather than requiring purchased keys. [DOC S-ucwyn46f, S-ldykf7ob]
- At-scale onboarding uses a Microsoft Entra service principal (or managed identity) granted the built-in **Azure Connected Machine Onboarding** role, scoped to a subscription or resource group; this role only creates/reads Arc server resources and cannot manage extensions or delete servers. [DOC S-5d7caeeq, S-h7fejg6k]

## Facts

### azcmagent CLI and configuration
- Top-level `azcmagent` commands: `check`, `config`, `connect`, `disconnect`, `genkey`, `help`, `license`, `logs`, `show`, `upgrade`, `version` (plus internal `partnerconfig`). [DOC S-arygyiia]
- `azcmagent config` has five subcommands: `list` (all properties/values), `get <property>`, `set <property> <value>` (`-a/--add` appends to a multi-value property, `-r/--remove` removes one value; mutually exclusive), `clear <property>` (resets to default), and `info [property]` (describes available properties and supported values for the installed agent version — properties vary by agent version). [DOC S-gma7exwg]
- Full config key/value/default/effect table (config.mode, extensions.allowlist/blocklist, incomingconnections.enabled/ports, proxy.url, proxy.bypass, guestconfiguration.enabled): `windows/azcmagent-config.csv`. [DOC S-gma7exwg, S-efadnhwv, S-nevhri3m]
- `azcmagent connect --subscription-id ... --resource-group ... --location ...` onboards the server; flags include `--service-principal-id`/`--service-principal-secret`/`--service-principal-cert` (with `--tenant-id`), `--use-device-code`, `--use-azcli` (agent 1.59+, requires an active `az login`), `--private-link-scope`, `--cloud` (AzureCloud/AzureUSGovernment/AzureChinaCloud), `--enable-automatic-upgrade` (preview), and `--ignore-network-check`. [DOC S-ojs4qilv]
- `azcmagent disconnect` supports the same authentication flags as `connect` plus `-f/--force-local-only` (deletes only the local agent config, leaving the Azure resource, e.g. after the Azure resource was already deleted) and `--user-tenant-id` (when the onboarding account's tenant differs from the target tenant, e.g. Azure Lighthouse). [DOC S-3ajkoikd]
- `azcmagent extension list`/`extension remove --name <ext>|--all` manage extensions locally on the machine, even while disconnected; the extension manager service (`ExtensionService` on Windows) must be stopped first (`Stop-Service ExtensionService` / `systemctl stop extd`), then restarted afterward. [DOC S-lpj5aefn]
- All `azcmagent` commands accept common flags: `--config <file>` (JSON/YAML of key-value inputs; CLI flags override file values), `-h/--help`, `-j/--json`, `--log-stderr`, `--no-color`, `-v/--verbose`. [DOC S-arygyiia]

### Networking
- The agent communicates outbound only, over TCP 443/HTTPS with TLS 1.2+ (TLS 1.3 supported and recommended); no inbound ports are required for onboarding or normal operation. [DOC S-szyeetyp]
- Required service tags for firewall/NSG allow rules: `AzureActiveDirectory`, `AzureTrafficManager`, `AzureResourceManager`, `AzureArcInfrastructure`, `Storage`, `AzureFrontDoor.Frontend` (required as of April 2026), and `WindowsAdminCenter` if using Windows Admin Center. [DOC S-szyeetyp]
- Azure Arc-enabled servers does **not** support using a Log Analytics gateway as a proxy for the Connected Machine agent (Azure Monitor Agent does support it). [DOC S-szyeetyp]
- Indirectly-connected mode retired September 2025; every server must connect directly or through a supported proxy/gateway. Azure Arc gateway (GA) reduces the number of endpoints a proxy must allow for Arc-enabled servers. [DOC S-szyeetyp]
- Proxy: `azcmagent config set proxy.url "http://ProxyServerFQDN:port"` is the agent-specific proxy setting (checked before the system `HTTPS_PROXY` env var, available since agent 1.13) and takes precedence when both are set; `azcmagent show` reports the effective proxy. `proxy.bypass` (agent 1.15+) skips the proxy for named services (`AAD`, `ARM`, `AMA`, `Arc`, `ArcData`) — e.g. `proxy.bypass "Arc"` routes Entra/ARM traffic through the proxy while Arc's own endpoints (`his.arc.azure.com`, `guestconfiguration.azure.com`) go direct; `ArcData` (SQL Server enabled by Arc traffic only) needs agent 1.36+. [DOC S-nevhri3m]
- Private Link: an Azure Arc private link scope can replace public-endpoint/proxy connectivity; `azcmagent connect --private-link-scope <resource-id>` associates the server with it. [DOC S-ojs4qilv, S-szyeetyp]

### Onboarding at scale and RBAC
- Two built-in roles: **Azure Connected Machine Onboarding** (create/read Arc server resources only — no extension management, no delete) for onboarding accounts/service principals, and **Azure Connected Machine Resource Administrator** (read/create/delete servers, extensions, licenses, private link scopes) for ongoing management; generic Reader/Contributor/Owner also apply. [DOC S-h7fejg6k]
- Create the onboarding service principal with `New-AzADServicePrincipal -DisplayName "..." -Role "Azure Connected Machine Onboarding"` (Azure PowerShell) or `az ad sp create-for-rbac --name "..." --role "Azure Connected Machine Onboarding" --scopes "/subscriptions/<id>"` (Azure CLI); the printed secret is valid **one year** and must be rotated/regenerated after expiry. [DOC S-5d7caeeq]
- Certificate-based service principal authentication is recommended over client secrets for onboarding at scale (stronger security, supports Conditional Access, less credential exposure); scope each principal to the minimum resource group/subscription needed. [DOC S-h7fejg6k]
- The onboarding credential (interactive login, service principal, or short-lived access token) is only needed at `azcmagent connect` time; once connected, the server keeps working even if that credential is later expired or deleted. A compromised onboarding credential could be used to onboard rogue servers into the target subscription/resource group — private endpoints mitigate this. [DOC S-5d7caeeq]
- Supported at-scale deployment paths: Group Policy (via the `ArcEnabledServersGroupPolicy` project on GitHub, `DeployGPO.ps1`), Configuration Manager (custom task sequence or PowerShell scripts, requires ConfigMgr 1706+), and Ansible (control node's own managed identity, Azure VM or Arc-enabled server identity, granted the Onboarding role). [DOC S-5d7caeeq]
- Connecting a server that also runs Microsoft SQL Server auto-connects the SQL Server instance(s) to Azure Arc too (opt out with tag `ArcSQLServerExtensionDeployment=Disabled` at connect time). [DOC S-5d7caeeq]

### Extensions, monitor mode, and security
- By default the agent runs in **full mode**: all extensions can install (subject to allow/block lists or Azure Policy). `azcmagent config set config.mode monitor` switches to **monitor mode**, which restricts the agent to a Microsoft-maintained allow list of monitoring/security extensions (e.g. Azure Monitor Agent, Microsoft Defender for Cloud), blocks any extension that could change system configuration or run arbitrary scripts, and **disables the guest configuration (Machine Configuration) policy agent**. While in monitor mode the allow/block list can't be edited directly — switch back to `full` mode first. [DOC S-efadnhwv]
- Allow-list/block-list precedence: an extension in the allow list only → allowed; in the block list only, or in both lists → blocked for install/reconfigure/upgrade; **delete is always allowed** regardless of list membership, so an already-installed extension isn't auto-removed by adding it to a block list — it must be explicitly deleted. [DOC S-efadnhwv]
- `extensions.allowlist "Allow/None"` runs the extension manager but permits **no** extension installs — the recommended setting when using Arc only to deliver Windows Server 2012 ESUs without any other extension. [DOC S-efadnhwv]
- Windows local security group **"Hybrid agent extension applications"** controls which local users/processes can request Entra tokens for the system-assigned managed identity from the agent's local endpoint (the Linux equivalent is the `himds` group) — this is the local-access control layered on top of the Arc managed identity mechanics in `auth/workload-identity.md`. [DOC S-h7fejg6k]

### Logs
- HIMDS log (heartbeat, connect/disconnect attempts, IMDS/managed-identity token request history): Windows `%ProgramData%\AzureConnectedMachineAgent\Log\himds.log`, Linux `/var/opt/azcmagent/log/himds.log`. [DOC S-oacfa6ee]
- `azcmagent` CLI log (history of local `azcmagent` command invocations and parameters): Windows `%ProgramData%\AzureConnectedMachineAgent\Log\azcmagent.log`, Linux `/var/opt/azcmagent/log/azcmagent.log`. [DOC S-oacfa6ee]
- Extension manager log: Windows `%ProgramData%\GuestConfig\ext_mgr_logs\gc_ext.log`, Linux `/var/lib/GuestConfig/ext_mgr_logs/gc_ext.log`; per-extension logs (no guaranteed format) under `%ProgramData%\GuestConfig\extension_logs\*` / `/var/lib/GuestConfig/extension_logs/*`. [DOC S-oacfa6ee]
- Machine Configuration (guest configuration policy) log: Windows `%ProgramData%\GuestConfig\arc_policy_logs\gc_agent.log`, Linux `/var/lib/GuestConfig/arc_policy_logs/gc_agent.log`. `azcmagent logs` collects a compressed bundle of all current logs in one command. [DOC S-oacfa6ee]
- Agent status/heartbeat: the agent sends a heartbeat every 5 minutes; a machine shows **Disconnected** 15-30 minutes after heartbeats stop, and can move to **Expired** after 45 days disconnected (the managed identity credential is valid up to 90 days, renewing every 45 days — its expiry date sets the exact expiration date). An expired machine must be manually disconnected and reconnected. [DOC S-jfzhzjgu]

### Azure Machine Configuration (relation to DSC)
- Azure Machine Configuration (previously "Azure Policy Guest Configuration") extends Azure Policy's `AuditIfNotExists`/`DeployIfNotExists` effects into the guest OS of an Arc-enabled server (or Azure VM), giving GPO-like, Azure-scoped (subscription/resource group/machine) OS-setting control instead of AD OU-scoped GPO. [DOC S-epoqec7s]
- Under the hood, Machine Configuration validates/remediates using **PowerShell DSC v2 on Windows** and **PowerShell DSC v3 on Linux**, both side-loaded into a folder used only by Azure Policy (not added to the system PATH, and the Windows v2 side-load doesn't conflict with any separately installed Windows PowerShell DSC) — this is a different DSC engine/version selection than this kb's `dsc/` articles, which cover the standalone cross-platform `dsc` 3.x CLI and its own resource/config model. [DOC S-4xar7ise]
- Machine Configuration packages set their DSC mode (`Audit` = report only, no changes; `AuditandSet` = verify and remediate) **inside the configuration package itself**, not via the classic DSC Local Configuration Manager metaconfig, because one machine can be assigned several packages each needing a different mode. [DOC S-nibv7ci5]
- Policy `configurationParameter` values override static text in the package's compiled MOF at assignment time; Azure Policy can only pass **string**-typed parameters this way (no arrays), even if the underlying DSC resource supports array parameters. [DOC S-nibv7ci5]
- Assignment types (the `assignmentType` property, case-sensitive): `Audit` (report only), `ApplyAndMonitor` (apply once, then monitor for drift but don't auto-correct unless remediation is manually triggered), `ApplyAndAutoCorrect` (apply, and auto-correct on the next evaluation if drift is detected). [DOC S-zfc5iphl]
- The Machine Configuration agent polls for new/changed guest assignments every **5 minutes**; once received, that configuration's settings are then rechecked on a **15-minute** interval; multiple assigned configurations evaluate sequentially, so a long-running one delays the others. [DOC S-4xar7ise]
- Managed identity requirement: Machine Configuration uses the Arc/VM system-assigned managed identity to report compliance back to the service (no separate identity to provision) — see `auth/workload-identity.md` for the Arc managed identity token mechanics this relies on. [DER S-4xar7ise, cross-ref auth/workload-identity.md]
- On a disconnected Arc machine, an existing guest-configuration assignment continues to be evaluated locally for **14 days**; if the agent doesn't reconnect within that window the assignment is deleted and isn't reapplied once the 14 days pass. [DOC S-wwbtoald]
- Built-in Machine Configuration policies ship prebuilt DSC-backed packages (e.g. password complexity/age/history, time zone, certificate expiry, Windows Firewall, allowed services/applications) each naming its required DSC resource module (e.g. `SecurityPolicyDsc`, `WindowsTimeZone`, `CertificateManagement`); custom packages are authored with `New-GuestConfigurationPolicy`/`Get-GuestConfigurationPackageComplianceStatus` and published with `New-AzPolicyDefinition`. [DOC S-epoqec7s]

### Windows Server management, ESU, and Hotpatch via Arc
- Windows Server Management enabled by Azure Arc requires Connected Machine agent **1.47+**, Windows Server 2012+ (Standard/Datacenter), and a *Connected* (not disconnected/expired) server; it works over public endpoint, proxy, Arc Gateway, or private endpoint with no extra endpoints to allow. [DOC S-w3pkna2x]
- Windows Server 2012/2012 R2 reached end of support 2023-10-10; Arc-enrolled machines can get Extended Security Updates (ESU) pay-as-you-go, billed monthly through Azure, with no product key to install — the Connected Machine agent itself enables the entitlement, and patches are then delivered through normal tools including Azure Update Manager. [DOC S-ucwyn46f]
- ESU licensing for WS2012/2012 R2 via Arc offers two models: **vCore** (Standard-edition rate per vCore, 8-core minimum per VM, VM-only) or **pCore** (either edition, 16-core minimum per server, covers physical host/VM/mixed; Standard host covers up to 2 guest VMs free, Datacenter host covers all guest VMs) — mixing pCore and vCore across VMs in an estate is allowed. [DOC S-d4ny3ufk]
- Windows Server 2025 Datacenter/Standard Edition Hotpatch is available on Arc-enabled machines at **no extra cost**: enable it per-machine in the Arc portal (Machines > select machine > Hotpatch > Confirm, ~10 minutes to apply); prerequisites are Virtualization Based Security (VBS) enabled and the machine Arc-connected. Hotpatch delivers monthly no-reboot security updates, with a reboot required only for the periodic cumulative-update baseline (about every 3 months). [DOC S-ldykf7ob, S-wftu7kvv]

## Reference
| Concept | This article (Azure Arc-enabled servers) | Related kb article |
|---|---|---|
| Arc system-assigned managed identity, local token endpoint, challenge-response | not repeated here | `auth/workload-identity.md` (`http://localhost:40342/metadata/identity/oauth2/token`, challenge-response, cost/free-tier, app-role assignment via PowerShell/Graph) |
| Machine Configuration's DSC engine (v2 Windows / v3 Linux), side-loaded, distinct from the `dsc` CLI | Facts, "Azure Machine Configuration (relation to DSC)" | `dsc/cli-reference.md`, `dsc/directives.md`, `dsc/functions.md` (the standalone cross-platform DSC v3 `dsc` binary and its own manifest/resource model — not what Machine Configuration side-loads) |
| Windows Update policy CSP / Update Manager patch orchestration for Arc/Azure machines | ESU and Hotpatch enablement only | `windows/windows-update-management.md` (Update CSP settings, Windows Autopatch, WUfB reports for Windows 10/11 clients); `windows/azure-update-manager.md` (periodic assessment, maintenance configurations, patch orchestration modes, dynamic scoping, Arc pricing, hotpatch scheduling, Resource Graph queries — the update-orchestration layer that applies the ESU/Hotpatch content enabled here) |
| Azure Monitor Agent extension (`AzureMonitorWindowsAgent`/`AzureMonitorLinuxAgent`) deployed on an Arc server, DCR/DCRA/DCE plumbing | not repeated here | `logs/azure-monitor-agent.md` (AMA install via `New-AzConnectedMachineExtension`, DCR structure and XPath event filters, Logs Ingestion API) |

| azcmagent command | Purpose | Source |
|---|---|---|
| `check` | Network connectivity checks for Arc endpoints | S-arygyiia |
| `config` | Manage local agent settings (see `windows/azcmagent-config.csv`) | S-gma7exwg |
| `connect` | Onboard the server to Azure Arc | S-ojs4qilv |
| `disconnect` | Remove the server from Azure Arc | S-3ajkoikd |
| `extension list/remove` | Local extension inventory/removal, works offline | S-lpj5aefn |
| `genkey` | Key pair for asynchronous onboarding (e.g. Arc-enabled VMware) | S-arygyiia |
| `logs` | Collect a troubleshooting log bundle | S-oacfa6ee |
| `show` | Current agent/connection status, effective proxy | S-nevhri3m |
| `upgrade` | Upgrade the agent | S-arygyiia |

## Examples
- Onboard with a service principal (placeholders only):
  ```bash
  azcmagent connect --subscription-id "00000000-0000-0000-0000-000000000000" \
    --resource-group "HybridServers" --location "westeurope" \
    --service-principal-id "00000000-0000-0000-0000-000000000000" \
    --service-principal-secret "REDACTED" --tenant-id "00000000-0000-0000-0000-000000000000"
  ```
- Restrict a monitoring-only server to the Microsoft-managed extension set and disable Machine Configuration:
  ```bash
  azcmagent config set config.mode monitor
  ```
- Route Entra/ARM traffic through a proxy but let Arc's own endpoints bypass it:
  ```bash
  azcmagent config set proxy.url "http://proxy.corp.example.com:8080"
  azcmagent config set proxy.bypass "Arc"
  ```
- Lock a host down to ESU delivery only, no other extensions:
  ```bash
  azcmagent config set extensions.allowlist "Allow/None"
  ```

## Open items
- `--enable-automatic-upgrade` on `azcmagent connect` is explicitly documented as **public preview**; the general "automatic agent upgrade" mechanism it complements (referenced from `manage-agent#enable-automatic-agent-upgrade-preview`) was not itself fetched in this pass — flagged [UNK: automatic-upgrade GA status/other enablement methods not confirmed].
- SSH access over Arc and Run Command were named in scope but not confirmed against a fetched page in this pass — not included above; a follow-up lookup should fetch the SSH-over-Arc and Run Command articles directly before citing specifics.
- Azure Machine Configuration's Linux DSC v3 side-load version/build and whether it tracks this kb's `dsc/` 3.3.0 coverage was not confirmed — flagged [UNK].
