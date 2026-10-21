---
topic: graph/microsoft365dsc
priority: P3
applies_to: "Microsoft365DSC PowerShell module 2.26.1015.1 (2026-10-14); resource-shape facts for 1.26.909.1 (2026-09-11)"
retrieved_utc: 2026-10-21
sources: [S1010, S-jya6izpo, S-l6j5dpwj, S-44mrima5, S-ahgkqifj, S-2fvvbt5t, S-zmngjhe5, S-prjyny3b, S-3aphi7n2, S-f7j4lqgl, S-5htwkeoz, S-n6v6mw4o, S-c6kla37l, S-fylt7wwn, S-acz6ela7, S-q7dr7aea]
status: complete
---

# Microsoft365DSC

## Summary
Microsoft365DSC is a community-maintained (Microsoft-hosted, MIT-licensed) PowerShell DSC resource module that automates
export, deployment, reporting and drift monitoring of Microsoft 365 tenant configuration (Entra ID, Exchange Online,
SharePoint/OneDrive, Teams, Intune, Power Platform, Defender for Office 365, Security & Compliance Center). It works at
the tenant-configuration level, the same layer as Microsoft Graph's Tenant Configuration Management (TCM) APIs
(`graph/tcm-apis.md`), but ships its own PowerShell cmdlets and classic DSC (`Get`/`Test`/`Set`) resources instead of
calling the TCM Graph endpoints. Latest release/package version confirmed 2026-10-21 on both the GitHub releases page
and the PowerShell Gallery package page: **2.26.1015.1**, released 2026-10-14 (the previously recorded 1.26.909.1, 2026-09-11, is
now superseded; `prior-art/drift-detection.md` and `prior-art/projects.csv`, source `S1010`, still need the new version). Docs below (microsoft365dsc.com) are the project's own site, not Microsoft Learn.

## Facts
- The GitHub repository `microsoft/Microsoft365DSC` (now redirecting to `Microsoft365DSC/Microsoft365DSC`) is MIT-licensed,
  written in PowerShell, and describes the module as managing, configuring, extracting and monitoring Microsoft 365
  tenant configurations. [DOC S1010]
- Install with `Install-Module Microsoft365DSC -Force`, run from an elevated **Windows PowerShell 5.1** window; from a
  non-elevated window the module lands in the Current User scope, which the docs say will not work. [COMMUNITY S-zmngjhe5]
- Installing the module gives only the core component; the docs recommend running `Update-M365DSCDependencies` afterwards, in both
  Windows PowerShell and PowerShell 7, to download the prerequisite modules (for example MSCloudLoginAssistant, which handles
  authentication for the workloads, plus further PowerShell Gallery modules) listed in the module's `Dependencies/Manifest.psd1`. [COMMUNITY S-zmngjhe5]
- `Update-M365DSCModule` upgrades both the main module and its dependencies and uninstalls outdated versions; `Get-Module Microsoft365DSC -ListAvailable | select ModuleBase, Version` verifies the installed version. [COMMUNITY S-zmngjhe5]
- Latest stable release/package version as of 2026-10-21: **2.26.1015.1**, released 2026-10-14 (GitHub marks it Latest; the PowerShell Gallery
  page shows the same version, last published 2026-10-14; the previous stable listing was 2.26.1007.1, before it 1.26.909.1). [DOC S-l6j5dpwj, S-jya6izpo]
- The 2.26.1015.1 release notes list resource fixes (for example `AADDomainFederation` gained `SystemBrowserEnabledOn`, `SCDLPCompliancePolicy`
  and `SCDLPComplianceRule` gained `DisplayName`) and dependency bumps (`DSCParser` 3.1.0.7, `M365DSC.PSDSC` 3.1.10). [DOC S-l6j5dpwj]
- The GitHub repository (now under `Microsoft365DSC/Microsoft365DSC`) describes the project as automating "deployment, configuration, reporting and
  monitoring of Microsoft 365 Tenants via PowerShell Desired State Configuration." [COMMUNITY S-prjyny3b]
- Licensing: resources covering Defender for Office 365 (for example `EXOAntiPhishPolicy`, `EXOSafeAttachmentPolicy`, `EXOSafeLinksPolicy`,
  `EXOAtpPolicyForO365`, `EXOAtpProtectionPolicyRule`, `EXOMalwareFilterPolicy`) need Microsoft 365 E5, or E3 plus the Defender for Office 365 Plan 2 add-on;
  a plain E3 tenant has only Exchange Online Protection and these resources fail against it. [COMMUNITY S-prjyny3b]
- Workload acronyms accepted by `Export-M365DSCConfiguration -Workloads`: AAD, ADO (Azure DevOps), AZURE, Commerce, Defender, EXO, Fabric, Intune, O365,
  OD (OneDrive), Planner, PP (Power Platform), SC (Security and Compliance), Sentinel, SH (Services Hub), SPO, Teams. [COMMUNITY S-ahgkqifj]
- `Export-M365DSCConfiguration` captures current tenant settings into a DSC configuration `.ps1` file (default file name
  `M365TenantConfig.ps1` if `-FileName` is omitted). Current versions run unattended by default (no component-picker GUI): without
  other parameters the cmdlet prompts for user credentials and starts the capture; `-LaunchWebUI` opens a web page that builds the export command instead. [COMMUNITY S-ahgkqifj]
- `-Components` selects specific resource components to capture; omitting it defaults to capturing all components in the
  default component list. [COMMUNITY S-ahgkqifj]
- `-Workloads` selects service areas by acronym (e.g. AAD, EXO, SPO, Teams, Intune); a workload on its own exports only
  that workload's default component list, and `-Mode Full` must be added to capture every component of it. [COMMUNITY S-ahgkqifj]
- `-Mode` controls export scope: `Default` captures configuration objects only; `Full` also captures data objects. [COMMUNITY S-ahgkqifj]
- `-Path` sets the output directory; if omitted, the export prompts for a destination path at the end of the capture. [COMMUNITY S-ahgkqifj]
- Service-principal authentication for export uses `-ApplicationId` and `-TenantId` paired with either an application
  secret or `-CertificateThumbprint`; the generated configuration file re-implements the same authentication mechanism used for the capture
  (service-principal values go into a `ConfigurationData.psd1` stored next to it). [COMMUNITY S-ahgkqifj]
- Additional export switches: `-ConfigurationName` (names the DSC configuration object), `-Filters` (resource-level
  filtering), `-GenerateInfo` (adds explanatory comments), `-Parallel`/`-ThrottleLimit` (concurrent export, 8GB+ RAM
  recommended; `-ThrottleLimit` defaults to 5 workers), `-WithStatistics` (prints an export summary), `-IncludeDependencies` (exports dependent resources
  automatically), `-TokenReplacement` (swaps tenant-specific tokens for variables, useful across tenants). [COMMUNITY S-ahgkqifj]
- The docs name two ways to authenticate, user credentials or a service principal (application ID and tenant ID with a
  secret or certificate); the per-workload table also has columns for certificate thumbprint, certificate path,
  application secret, managed identity and access tokens, and support differs by workload. [COMMUNITY S-44mrima5]
- The docs state service principals "offer the most granular levels of security and do not introduce the risk of having
  to send high privileged credentials across the wire." [COMMUNITY S-44mrima5]
- `Get-M365DSCCompiledPermissionList -ResourceNameList @('AADUser','AADApplication')` returns the permissions a given
  resource set needs, split into `ReadPermissions` (export/snapshot) and `UpdatePermissions` (deployment); by default it outputs the delegated
  permissions, and `-PermissionType 'Application' -AccessType 'Read'` selects application permissions. [COMMUNITY S-44mrima5]
- Every Microsoft Graph component also needs `Organization.Read.All`: `Get-M365DSCCompiledPermissionList` always includes it, but the per-resource
  permission lists on the docs site do not, so add it when granting manually; without it Graph components fail with "Failed to initialize Graph HTTP client". [COMMUNITY S-44mrima5]
- `Update-M365DSCAllowedGraphScopes` consents the permissions needed by the listed components (or all resources with
  `-All`) to the delegated "Microsoft Graph PowerShell" application in the tenant; you choose Read or Update permissions. [COMMUNITY S-44mrima5]
- `Update-M365DSCAzureAdApplication` automates custom service-principal setup (app registration, permission assignment,
  admin consent, credential generation as secret or certificate); the docs' example combines `-ApplicationName`,
  `-Permissions`, `-AdminConsent`, `-Type Certificate -CreateSelfSignedCertificate -CertificatePath` and `-Credential`;
  `-Type ManagedIdentity` instead assigns the permissions to an existing managed identity (`-ApplicationName` then takes its display name, object id or
  client id; no application, consent or credential is created and the permissions apply immediately). [COMMUNITY S-44mrima5]
- For the Power Apps workload, certificate-thumbprint authentication requires the certificate's private key (`.pfx`) in
  the current user's store (`Cert:\CurrentUser\My\`), because the underlying Power Apps module needs it. [COMMUNITY S-44mrima5]
- Workload-specific auth modules: Microsoft.Graph.Authentication (Entra ID/Graph-backed workloads), ExchangeOnlineManagement
  (Exchange Online, Security & Compliance via `Connect-IPPSSession`), PnP.PowerShell (SharePoint/OneDrive: certificate thumbprint, certificate path and
  application secret all marked supported), MicrosoftTeams (Teams: of the service-principal options only
  certificate thumbprint is marked supported, not certificate path or application secret). [COMMUNITY S-44mrima5]
- Drift monitoring performs regular checks comparing the remote tenant's configuration against the declared desired
  state, by default every 15 minutes; detected drifts are logged to the Windows Event Viewer under an **M365DSC**
  journal/log. [COMMUNITY S-2fvvbt5t]
- The DSC engine can be configured in `ApplyAndAutoCorrect` mode to automatically remediate detected drift and restore
  the declared state, as opposed to report-only monitoring. [COMMUNITY S-2fvvbt5t]
- `New-M365DSCDeltaReport` compares two configurations: mandatory `-Source` and `-Destination`, with `-OutputPath`, `-Type` (`HTML` or `JSON`), `-DriftOnly`, `-HeaderFilePath`, `-ExcludedProperties`, `-ExcludedResources` and variable-substitution options. [CODE S-acz6ela7: Modules/Microsoft365DSC/Modules/M365DSCReport.psm1#New-M365DSCDeltaReport]
- The project's guide uses it to compare two exported configurations, or one tenant's snapshot with another tenant's, writing an HTML report. [DOC S-c6kla37l]
- `Test-M365DSCAgent` takes no parameters and checks the agent machine, not a tenant: the PowerShell version (at 2.26.1015.1 it raises an issue unless the session is PowerShell 7.6 or later, Core edition; earlier it recommended 5.1), the WinRM MaxEnvelopeSize (recommends at least 10 MB) and the module dependencies, and reports issues and recommendations. It is not a drift report. [CODE S-5htwkeoz: Modules/Microsoft365DSC/Modules/M365DSCAgent.psm1#Test-M365DSCAgent]
- In release 1.26.909.1 each Microsoft365DSC resource follows classic PowerShell DSC's `Get-TargetResource`/`Test-TargetResource`/
  `Set-TargetResource` (MOF-based) pattern rather than DSC v3's resource-manifest model, so `Test-DscConfiguration`
  reports drift without applying `Set`, matching the report-only mode covered in `prior-art/drift-detection.md`. [DER S-3aphi7n2, S-fylt7wwn: MSFT_AADUser at the release tag has a `.schema.mof` and Get/Set/Test-TargetResource functions; Test-DscConfiguration only tests]
- On the default branch (commit `ec5bf30ecd96`) `MSFT_AADUser` is a class-based DSC resource: `class AADUser : M365DSCResourceBase` with `Get()`, `Set()`, `Test()` and `Export()` methods and no `Get-TargetResource` function. [CODE S-q7dr7aea: Modules/Microsoft365DSC/DscResources/MSFT_AADUser/MSFT_AADUser.psm1#AADUser]
- The development line converts resources to class-based `[DscResource()]` classes deriving from a shared `M365DSCResourceBase`
  (`DscResources/_Base/M365DSCResourceBase.psm1`, defining `M365DSCResourceBase` plus property/resource metadata classes; at commit 7c2e9790e17b it is source-only and
  emitted into a generated `Classes/_Shared.psm1`). The 2.26.1015.1 release tree also contains the `_Base` directory and its agent check requires PowerShell 7.6, so 2.x releases are
  probably not the MOF-based, Windows PowerShell 5.1 shape described for 1.26.909.1; this was not confirmed from a resource file at the release tag, and the install docs still say Windows PowerShell 5.1. [COMMUNITY S-f7j4lqgl, S-5htwkeoz, S-n6v6mw4o]
- Release 2.26.1015.1 ships 168 Intune resources named `MSFT_Intune*` (for example `MSFT_IntuneAccountProtectionLocalAdministratorPasswordSolutionPolicy`, `MSFT_IntuneAntivirusPolicyLinux`; 1.26.909.1 had 166). [DER S-n6v6mw4o: count of the `DscResources` directory at the release commit]

## Reference
- Tenant-level configuration monitoring/drift at the Graph API layer (not PowerShell/DSC-based): `graph/tcm-apis.md`
  (this file is now cross-linked from that article's Reference section).
- Drift-only vs. enforcement comparison across projects, including Microsoft365DSC's `Test-DscConfiguration` /
  `Start-DscConfiguration` behavior: `prior-art/drift-detection.md`.
- Project metadata (license, version, repo URL) already tracked in `prior-art/projects.csv` (source `S1010`).
- Classic MOF-based DSC resource shape vs. DSC v3's resource manifest / `dsc` CLI model: `dsc/cli-reference.md`.

## Examples
- SNIPPET: install Microsoft365DSC, discover needed permissions, and export Intune + Entra ID config with certificate auth; context: elevated Windows PowerShell 5.1 as in the install docs (2.26.1015.1 agent check wants PowerShell 7.6, see Facts); checked: no [COMMUNITY S-zmngjhe5, S-44mrima5, S-ahgkqifj]
```powershell
# Install and prep dependencies (elevated Windows PowerShell 5.1)
Install-Module Microsoft365DSC -Force
Update-M365DSCDependencies

# Discover permissions needed to export/deploy two Entra ID resources
Get-M365DSCCompiledPermissionList -ResourceNameList @('AADUser', 'AADApplication')

# Export current Intune + Entra ID config using app-only (certificate) auth
Export-M365DSCConfiguration -Workloads @('Intune', 'AAD') `
    -ApplicationId '00000000-0000-0000-0000-000000000000' `
    -TenantId 'corp.example.com' `
    -CertificateThumbprint '0000000000000000000000000000000000AAAA' `
    -Path 'C:\M365DSC\PL-SRV-0042' `
    -FileName 'TenantConfig.ps1'
```
