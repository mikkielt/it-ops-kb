---
topic: graph/microsoft365dsc
priority: P3
applies_to: "Microsoft365DSC PowerShell module 1.26.909.1 (2026-09-11)"
retrieved_utc: 2026-09-26
sources: [S1010, S-jya6izpo, S-l6j5dpwj, S-44mrima5, S-ahgkqifj, S-2fvvbt5t, S-zmngjhe5, S-prjyny3b]
status: partial
---

# Microsoft365DSC

## Summary
Microsoft365DSC is a community-maintained (Microsoft-hosted, MIT-licensed) PowerShell DSC resource module that automates
export, deployment, reporting and drift monitoring of Microsoft 365 tenant configuration (Entra ID, Exchange Online,
SharePoint/OneDrive, Teams, Intune, Power Platform, Defender for Office 365, Security & Compliance Center). It works at
the tenant-configuration level, the same layer as Microsoft Graph's Tenant Configuration Management (TCM) APIs
(`graph/tcm-apis.md`), but ships its own PowerShell cmdlets and classic DSC (`Get`/`Test`/`Set`) resources instead of
calling the TCM Graph endpoints. Latest release/package version confirmed 2026-09-26 on both the GitHub releases page
and the PowerShell Gallery package page: **1.26.909.1**, published 2026-09-11 (also recorded in `prior-art/drift-detection.md`
and `prior-art/projects.csv`, source `S1010`). Docs below (microsoft365dsc.com) are the project's own site, not Microsoft Learn.

## Facts
- Install with `Install-Module Microsoft365DSC -Force`, run from an elevated **Windows PowerShell 5.1** window — a non-elevated
  window causes the install to not work correctly. [COMMUNITY S-zmngjhe5]
- After installing the module, run `Update-M365DSCDependencies` to download prerequisite modules (MSCloudLoginAssistant,
  Microsoft Graph PowerShell modules); current versions of Microsoft365DSC no longer bundle all prerequisites by default. [COMMUNITY S-zmngjhe5]
- `Update-M365DSCModule` upgrades both the main module and its dependencies; `Get-Module Microsoft365DSC -ListAvailable | select ModuleBase, Version` verifies the installed version. [COMMUNITY S-zmngjhe5]
- Latest stable release/package version as of 2026-09-26: **1.26.909.1**, released/published 2026-09-11. [DOC S-l6j5dpwj, S-jya6izpo]
- The GitHub repository is MIT-licensed and describes the project as automating "deployment, configuration, reporting and
  monitoring of Microsoft 365 Tenants via PowerShell Desired State Configuration." [COMMUNITY S-prjyny3b]
- Supported workload areas named in the repository overview: Entra ID (AAD), Exchange Online (EXO), Intune, SharePoint
  Online, OneDrive, Microsoft Teams, Power Platform, Defender for Office 365, Security & Compliance Center, Skype for
  Business. [COMMUNITY S-prjyny3b]
- `Export-M365DSCConfiguration` captures current tenant settings into a DSC configuration `.ps1` file (default file name
  `M365TenantConfig.ps1` if `-FileName` is omitted). [COMMUNITY S-ahgkqifj]
- `-Components` selects specific resource components to capture; omitting it defaults to capturing all components in the
  default component list. [COMMUNITY S-ahgkqifj]
- `-Workloads` selects service areas by acronym (e.g. AAD, EXO, SPO, Teams, Intune); specifying a workload without
  `-Components` still only exports the default component list for that workload. [COMMUNITY S-ahgkqifj]
- `-Mode` controls export scope: `Default` captures configuration objects only; `Full` also captures data objects. [COMMUNITY S-ahgkqifj]
- `-Path` sets the output directory; if omitted, the export prompts for a destination path at the end of the capture. [COMMUNITY S-ahgkqifj]
- Service-principal authentication for export uses `-ApplicationId` and `-TenantId` paired with either an application
  secret or `-CertificateThumbprint`; the generated configuration file re-implements the same authentication mechanism used for the capture. [COMMUNITY S-ahgkqifj]
- Additional export switches: `-ConfigurationName` (names the DSC configuration object), `-Filters` (resource-level
  filtering), `-GenerateInfo` (adds explanatory comments), `-Parallel`/`-ThrottleLimit` (concurrent export, 8GB+ RAM
  recommended), `-WithStatistics` (prints an export summary), `-IncludeDependencies` (exports dependent resources
  automatically). [COMMUNITY S-ahgkqifj]
- Microsoft365DSC supports four authentication approaches: user credentials, service principal with certificate
  thumbprint, service principal with application secret, and managed identity. [COMMUNITY S-44mrima5]
- The docs state service principals "offer the most granular levels of security and do not introduce the risk of having
  to send high privileged credentials across the wire." [COMMUNITY S-44mrima5]
- `Get-M365DSCCompiledPermissionList -ResourceNameList @('AADUser','AADApplication')` returns the permissions a given
  resource set needs, split into `ReadPermissions` (export/snapshot) and `UpdatePermissions` (deployment). [COMMUNITY S-44mrima5]
- `Update-M365DSCAllowedGraphScopes` grants delegated-permission consent for the required scopes without manual Azure
  portal configuration. [COMMUNITY S-44mrima5]
- `Update-M365DSCAzureAdApplication` automates custom service-principal setup (app registration, permission assignment,
  admin consent, credential generation as secret or certificate); example: `Update-M365DSCAzureAdApplication
  -ApplicationName 'Microsoft365DSC' -AdminConsent -Type Certificate -CreateSelfSignedCertificate`. [COMMUNITY S-44mrima5]
- Certificate-based authentication requires the certificate's private key (`.pfx`) to be registered in the current
  user's certificate store. [COMMUNITY S-44mrima5]
- Workload-specific auth modules: Microsoft.Graph.Authentication (Entra ID/Graph-backed workloads), ExchangeOnlineManagement
  (Exchange Online), PnP.PowerShell (SharePoint/OneDrive), MicrosoftTeams (Teams, limited service-principal support). [COMMUNITY S-44mrima5]
- Drift monitoring performs regular checks comparing the remote tenant's configuration against the declared desired
  state, by default every 15 minutes; detected drifts are logged to the Windows Event Viewer under an **M365DSC**
  journal/log. [COMMUNITY S-2fvvbt5t]
- The DSC engine can be configured in `ApplyAndAutoCorrect` mode to automatically remediate detected drift and restore
  the declared state, as opposed to report-only monitoring. [COMMUNITY S-2fvvbt5t]
- `New-M365DSCDeltaReport` and `Test-M365DSCAgent` are cmdlets for drift/compliance reporting, listed in the project's
  navigation and cmdlet index, but their parameter-level syntax was not found on a working page during this research
  pass (the dedicated `/cmdlets/New-M365DSCDeltaReport/` page returned HTTP 404). [UNK]
- Each Microsoft365DSC resource follows classic PowerShell DSC's `Get-TargetResource`/`Test-TargetResource`/
  `Set-TargetResource` (MOF-based) pattern rather than DSC v3's resource-manifest model, so `Test-DscConfiguration`
  (or `Start-DscConfiguration -WhatIf`) reports drift without applying `Set`, matching the report-only mode covered in
  `prior-art/drift-detection.md`. [DER S1010, dsc/cli-reference.md]
- Individual Intune resource names (e.g. resource types beginning `Intune*`) were not independently confirmed on a
  working documentation page this session; the repository overview confirms Intune as a supported workload but lists
  no resource names. [UNK]

## Reference
- Tenant-level configuration monitoring/drift at the Graph API layer (not PowerShell/DSC-based): `graph/tcm-apis.md`
  (this file is now cross-linked from that article's Reference section).
- Drift-only vs. enforcement comparison across projects, including Microsoft365DSC's `Test-DscConfiguration` /
  `Start-DscConfiguration` behavior: `prior-art/drift-detection.md`.
- Project metadata (license, version, repo URL) already tracked in `prior-art/projects.csv` (source `S1010`).
- Classic MOF-based DSC resource shape vs. DSC v3's resource manifest / `dsc` CLI model: `dsc/cli-reference.md`.

## Examples
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
