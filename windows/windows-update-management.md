---
topic: windows/windows-update-management
priority: P2
applies_to: "Windows 10/11 Update policy CSP; Intune update rings/feature/quality/driver update policies; Windows Autopatch (incl. hotpatch); Microsoft Graph windowsUpdates (beta); Windows Update for Business reports"
retrieved_utc: 2026-09-26
sources: [S-6soaabdg, S-nxcrbrj4, S-2z6lunfo, S-dlg7lumx, S-4oi245yf, S-xoerk6of, S-qffa6b5k, S-jpgvmrt5, S-vrrtfarn, S-hdprezk3, S-p4dpx2og, S-34u26yld, S-rek3chkd]
status: partial
files: [windows/windows-update-management.csv]
---

# Windows Update management: Update CSP, Autopatch, hotpatch, WUfB reports, and lifecycle

## Summary
- Intune's Windows Update client policy surface (update rings, feature update, quality update incl. hotpatch/expedite, driver update policies) is built entirely on the `./Device/Vendor/MSFT/Policy/Config/Update` CSP; the full setting/OMA-URI/range/default table is in `windows/windows-update-management.csv`. [DOC S-2z6lunfo, S-nxcrbrj4]
- Windows Autopatch layers approval, scheduling, gradual rollout, expedite, and safeguard holds on top of the same client policy surface, and for Autopatch-managed devices its own update rings and quality/feature/hotpatch policies normally replace admin-created custom update rings. [DOC S-6soaabdg, S-dlg7lumx]
- Hotpatch updates are monthly, no-restart security updates that require Windows Autopatch, Windows 11 24H2+, VBS, an eligible licence, and the latest quarterly baseline; devices failing any prerequisite silently fall back to the standard restart-required Latest Cumulative Update (LCU). [DOC S-xoerk6of]
- Windows Update for Business reports (Log Analytics-backed) and the Microsoft Graph `windowsUpdates` beta API (used by Windows Autopatch) are the two ways to monitor/drive updates outside the Intune UI. [DOC S-jpgvmrt5, S-qffa6b5k]
- Windows 10 reached end of support 2025-10-14; Windows 11 servicing is 24 months (Home/Pro/Pro Education/Pro for Workstations) or 36 months (Enterprise/Education/IoT Enterprise/Enterprise multi-session) per annual feature update. [DOC S-hdprezk3, S-p4dpx2og]

## Facts

### Update policy types and precedence
- Intune's Windows Update policy surface has four independent policy types: update ring policies (general Update CSP surface: deferral, deadlines, active hours, pause/uninstall), feature update policies (pin a device to a specific Windows version), quality update policies (incl. hotpatch and expedite), and driver update policies. [DOC S-6soaabdg]
- When a device managed by Windows Autopatch isn't targeted by any Autopatch policy for a given content type (quality, feature, driver), it receives all latest content by default rather than being held back. [DOC S-6soaabdg]
- Windows Update ring policies require the *Microsoft Account Sign-In Assistant* service (`wlidsvc`) to be enabled and running on the device; if disabled, the device stops being offered feature updates. [DOC S-nxcrbrj4]
- Update ring policies apply to Pro, Pro Education, Enterprise, Education, Windows IoT Enterprise, Windows Team (Surface Hub), and (partially) Windows Holographic for Business editions; Windows Enterprise/IoT Enterprise LTSC support quality updates only — feature-update pause, feature deferral, feature uninstall period, pre-release builds, and feature-update deadlines aren't supported on LTSC. [DOC S-nxcrbrj4]
- Pausing an update ring blocks feature or quality updates for up to 35 days from the pause command; the pause auto-expires after 35 days, and resuming then re-pausing resets the period back to a full 35 days; **Extend** also resets the pause to 35 days without first resuming. [DOC S-nxcrbrj4]
- A device can uninstall (roll back) its latest installed feature update only within the configured uninstall period (`ConfigureFeatureUpdateUninstallPeriod`, 2-60 days); rollback isn't possible once that window has elapsed, and isn't possible at all if the feature update was applied via an Enablement Package. [DOC S-nxcrbrj4]
- Deleting an update ring from Intune stops Intune from enforcing it but does not revert any setting already applied on assigned devices; devices retain no history of prior settings and can still receive settings from other active rings. [DOC S-nxcrbrj4]

### Update CSP: key settings (full table in the CSV)
- `DeferQualityUpdatesPeriodInDays` defers quality updates 0-30 days (default 0); pausing via `PauseQualityUpdatesStartTime` holds updates for 35 days from the specified date or until the field is cleared. [DOC S-2z6lunfo]
- `DeferFeatureUpdatesPeriodInDays` defers feature updates up to 365 days on the General Availability Channel (14 days on prerelease channels), default 0; feature-update pause similarly lasts 35 days from the start date, and quality updates keep flowing even while feature updates are paused. [DOC S-2z6lunfo]
- `ConfigureDeadlineForQualityUpdates` (0-30 days, default 1) and `ConfigureDeadlineForFeatureUpdates` (0-30 days, default 2) force installation regardless of active hours once the deadline passes; when either is configured, `AllowAutoUpdate`'s own download/install/reboot behavior is ignored; setting either to 0 installs immediately but may not finish the same day. [DOC S-2z6lunfo]
- `ConfigureDeadlineGracePeriod` (quality, 0-7 days, default 2) and `ConfigureDeadlineGracePeriodForFeatureUpdates` (0-7 days, default 7; falls back to `ConfigureDeadlineGracePeriod`'s value, then to 7, if unset) set the minimum days after installation before an automatic restart is forced; both only take effect when the matching deadline policy is configured. [DOC S-2z6lunfo]
- `ActiveHoursStart` (0-23, default 8) and `ActiveHoursEnd` (0-23, default 17) bound the no-auto-restart window; the effective maximum active-hours span is 18 hours from the start time unless overridden by `ActiveHoursMaxRange` (8-18 hours, default 18), which lets the device auto-expand active hours based on usage instead of a fixed end time. [DOC S-2z6lunfo]
- `BranchReadinessLevel` selects the feature-update servicing channel: 16 = Semi-Annual Enterprise Channel (the default, and the only channel from Windows 10 1903+ after the pre-1903 value 32 was merged into it), with 2/4/8/64/128 reserved for Insider/preview channels. [DOC S-2z6lunfo]
- `TargetReleaseVersion` (string, e.g. `23H2`) pins a device to a specific feature-update version and requires `ProductVersion` to also be set to work; `ProductVersion` (e.g. `"Windows 11"`) additionally lets an admin move a device to a new Windows product, with the admin implicitly attesting to holding the required volume-licensing/EULA rights when doing so. [DOC S-2z6lunfo]
- `AllowAutoUpdate` (default 2 = auto install and restart outside active hours) is the master automatic-update behavior switch; Microsoft recommends leaving it unconfigured except for systems under regulatory compliance, since a restrictive setting can also suppress security updates. [DOC S-2z6lunfo]
- `SetPolicyDrivenUpdateSourceForQualityUpdates`/`...FeatureUpdates`/`...DriverUpdates` each independently switch that content type's scan source between unmanaged Microsoft Update and policy-driven (WSUS/Windows Update for Business) sourcing — this "scan source" split is how an org can keep, e.g., driver updates on WSUS while quality/feature updates come from the cloud. [DOC S-2z6lunfo, S-4oi245yf]
- `DetectionFrequency` controls how often the client rescans Windows Update, up to 22 hours (which the expedited-update documentation confirms as the default scan interval); an expedited quality update deployment from Windows Autopatch bypasses this scan interval and starts immediately. [DOC S-2z6lunfo, S-qffa6b5k]

### Windows Autopatch and hotpatch
- Windows Autopatch requires one of: Microsoft 365 Business Premium, Windows 10/11 Education A3/A5, Windows 10/11 Enterprise E3/E5 (incl. via Microsoft 365 F3/E3/E5), or Windows Enterprise E3/E5 VDA; devices must be corporate-owned (BYOD is blocked at registration), Entra-joined or hybrid-joined, running one of Pro/Enterprise/Education/Pro Education/Pro for Workstations, and have checked in with Intune within the last 28 days. [DOC S-4oi245yf]
- Co-managed devices must have the Windows Update policies workload and the Device configuration workload both set to Intune or Pilot Intune (with devices in the matching ConfigMgr collections) before they can register with Windows Autopatch; Configuration-Manager-only-managed devices aren't supported. [DOC S-4oi245yf]
- Support requests to the Windows Autopatch Service Engineering Team require an E3+ or F3 licence; Business Premium and A3+ tenants get every other Autopatch feature (RBAC, update rings, Autopatch groups, quality/feature/driver updates, hotpatch, reporting) but not support requests. [DOC S-4oi245yf, S-dlg7lumx]
- Hotpatch prerequisites: an eligible licence (Windows 11 Enterprise E3/E5, Microsoft 365 F3, Windows 11 Education A3/A5, Microsoft 365 Business Premium, or Windows 365 Enterprise), Windows 11 version 24H2 or later, the device on the latest quarterly baseline release, VBS turned on, and an Intune Windows quality update policy with hotpatch set to **Allow**. [DOC S-xoerk6of]
- The hotpatch release cadence is quarterly: baseline (restart required) in January/April/July/October, hotpatch (no restart) in the other two months of each quarter (e.g. Q1: baseline January, hotpatch February and March); an occasional out-of-cycle baseline doesn't shift the planned quarterly cadence. [DOC S-xoerk6of]
- If a hotpatch-enrolled device isn't on the latest baseline during a hotpatch month, it receives both the baseline (restart required) and the hotpatch update that month; upgrading a hotpatch device to a new Windows version during a hotpatch month also forces a restart and drops it back to standard updates until the next baseline. [DOC S-xoerk6of]
- On Arm64 devices, hotpatch requires disabling Compiled Hybrid PE (CHPE) via the `DisableCHPE` System policy CSP or by setting the registry DWORD `HotPatchRestrictions=1` at `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management` and restarting once; this can break 32-bit x86 apps (e.g. legacy Office VBA/COM add-ins) with no 64-bit alternative, so affected devices should instead be excluded from hotpatch policy. [DOC S-xoerk6of]
- Devices that don't meet hotpatch prerequisites are silently offered the standard restart-required LCU instead, without altering the device's configured update-ring settings; automatic rollback of an installed hotpatch isn't supported, but a hotpatch can be manually uninstalled (which itself requires a restart). [DOC S-xoerk6of]
- Troubleshooting hotpatch: verify VBS via `System information` ("Virtualization-based security" = Running) or the Event Viewer `AllowRebootlessUpdates` payload (`"isEnrolled":1` = enrolled); on the device, **Settings > Windows Update > Advanced options > Configured update policies > Enable hotpatching when available** confirms enrollment; a hotpatch-specific inbox monitor service logs failures to the Windows Application log, and a critical error there causes the device to fall back to installing the standard LCU. [DOC S-xoerk6of]
- Expediting a quality update via Windows Autopatch overrides configured deferral/deadline policy to install as fast as possible (bypassing the ~22-hour scan interval) but is meant for exceptional compliance events, not routine monthly use; `equivalentContent: latestSecurity` (the default) means a device may receive a newer update than the one targeted rather than two updates in quick succession. [DOC S-qffa6b5k]

### Microsoft Graph windowsUpdates API (beta)
- The Windows Autopatch/Windows Updates API lives under `https://graph.microsoft.com/beta/admin/windows/updates/...`; core resources are `catalog/entries` (available content, e.g. `qualityUpdateCatalogEntry` with `isExpeditable`/`isHotpatchUpdate` flags), `deploymentAudiences` (device targeting), and `deployments` (what/how/when to deploy). [DOC S-qffa6b5k]
- Creating an expedited quality-update deployment: `POST .../admin/windows/updates/deployments` with `settings.expedite.isExpedited: true`; `settings.userExperience.daysUntilForcedReboot` sets the grace period after which an unrestarted device is forced to reboot. [DOC S-qffa6b5k]
- Deploying a hotpatch update: create a `deploymentAudience`, add member devices via `POST .../deploymentAudiences/{id}/updateAudience`, then `POST .../deployments` with `deploymentSettings.userExperience.isHotpatchEnabled: true`; the deployment prioritizes the latest hotpatch, falling back to the latest cumulative update if hotpatch is unavailable or the device is ineligible, and the device's own deferral policy is still honored. [DOC S-qffa6b5k]
- Devices are auto-registered as `azureADDevice` objects the first time they're added to a deployment audience's members or exclusions; a deployment keeps offering its update to newly-reconnected assigned devices for as long as the deployment object exists. [DOC S-qffa6b5k]
- Windows Autopatch capability matrix by content type: quality updates get Expedite only; feature updates get approval/scheduling, gradual rollout, and safeguard holds; driver/firmware updates get approval/scheduling only (no gradual rollout or safeguards). [DOC S-qffa6b5k]
- Safeguard holds (machine-learning-driven blocks on devices at higher risk of a post-upgrade issue) apply automatically to Windows 11 feature-update deployments driven by Windows Autopatch, on top of Microsoft's platform-wide safeguard holds. [DOC S-qffa6b5k]

### Windows Update for Business (WUfB) reports
- WUfB reports is a free, Log Analytics-backed cloud service (no ingestion/retention charges to the customer's Azure subscription) for Entra-joined Windows 10/11 devices; it is not available for US Government Community (GCC) High or DoD customers. [DOC S-jpgvmrt5]
- Report tables: `UCClient` (per-device snapshot), `UCClientReadinessStatus`, `UCClientUpdateStatus`, `UCDeviceAlert`, `UCDOAggregatedStatus`/`UCDOStatus` (Delivery Optimization), `UCServiceUpdateStatus`, `UCUpdateAlert`. [DOC S-jpgvmrt5]
- `UCClient` mirrors live Update CSP configuration per device, e.g. `WUQualityDeadlineDays` (CSP `ConfigureDeadlineForQualityUpdates`), `WUFeatureDeadlineDays` (CSP `ConfigureDeadlineForFeatureUpdates`), `WUQualityDeferralDays` (CSP `DeferQualityUpdates`), `WUFeatureDeferralDays` (CSP `DeferFeatureUpdates`); across these int fields, `-1` means "not configured", `0` means "configured and set to 0", any positive value is the configured setting. [DOC S-vrrtfarn]
- `UCClient.WUFeaturePauseState`/`WUQualityPauseState` report `Paused`, `NotPaused`, or `NotConfigured`; a feature-update pause is documented as lasting 35 days from its start date, consistent with the update-ring pause behavior above. [DOC S-vrrtfarn]
- WUfB reports replaced the now-discontinued Update Compliance service (deprecation announced November 2022). [DOC S-rek3chkd]

### Lifecycle and deprecations
- Windows 10 reached end of support on 2025-10-14: no further feature updates, quality updates, or technical support for versions that reached that date. [DOC S-hdprezk3]
- Windows 10 commercial/organizational ESU: a paid, per-device annual subscription (minimum 1 licence, no partial periods); Year One begins November 2025 and each subsequent year must also be purchased (cumulative pricing); enrolled devices can receive security updates for a maximum of three years past end of support; devices must be on Windows 10 version 22H2; ESU excludes new features, non-security fixes, design changes, and general technical support (only ESU activation/installation support is included). [DOC S-hdprezk3]
- Windows 10 consumer ESU: enroll via an in-Settings wizard requiring a Microsoft Account, through one of three no-purchase-required or paid options (sync settings to OneDrive, redeem 1,000 Microsoft Rewards points, or pay), covering security updates through 2026-10-13; requires Windows 10 22H2 with the prerequisite August 2025 cumulative update installed. [DOC S-hdprezk3]
- Windows 11 servicing: one feature update per year, released in the second half of the calendar year; Home, Pro, Pro Education, and Pro for Workstations editions get 24 months of servicing from release; Enterprise, Education, IoT Enterprise, and Enterprise multi-session get 36 months. [DOC S-p4dpx2og]
- Windows Server Update Services (WSUS) is deprecated (no new features) per the Windows Server 2025 removed/deprecated-features announcement, but remains supported for production deployments and continues to receive security and quality updates per its product lifecycle; it still requires a supported WSUS role on Windows Server 2016/2019/2022/2025. [DOC S-rek3chkd, S-34u26yld]

## Reference
- `intune/co-management.md:46` lists the Windows Update policies co-management workload (moves control from ConfigMgr client settings to Intune); this article is the detailed Update CSP/Autopatch/hotpatch/WUfB reference for that workload, and a back-link has been added there.
- `mecm/software-updates.md` is the on-premises ConfigMgr/WSUS counterpart (SUP sync, ADRs, maintenance windows, WSUS/SUP maintenance) for devices whose Windows Update policies workload is still with Configuration Manager, or for co-managed devices before that workload is switched.
- `intune/compliance-policies.md` and `intune/configuration-policies.md` cover the adjacent Intune device-configuration and compliance surfaces that update rings are commonly paired with in a device group's overall policy set, but don't themselves configure Windows Update behavior.
- `windows/laps.md` documents an unrelated Windows CSP (LAPS) using the same Policy CSP / OMA-URI conventions referenced here, useful as a pattern reference for reading `windows-update-management.csv`.
- `windows/delivery-optimization.md` documents the Delivery Optimization CSP/GPO settings and Microsoft Connected Cache for Enterprise that carry Windows Update, Win32 app, and Microsoft 365 app content to devices; the `UCDOAggregatedStatus`/`UCDOStatus` WUfB reports tables above surface that layer's peer/cache metrics.
- Full Windows Autopatch feature-entitlement matrix by licence tier, Windows Autopatch groups (multi-ring orchestration on top of update rings), and the Windows Autopatch RBAC role list are out of scope here. [UNK: not yet reviewed in depth]
- `windows/azure-arc-servers.md` covers ESU delivery for out-of-support Windows Server (2012/2012 R2) and Hotpatch enablement for Windows Server 2025 via Arc enrollment; Azure Update Manager's own patch orchestration (maintenance configurations, periodic assessment) for Arc-connected and Azure machines is the layer that then applies that content.
- `windows/azure-update-manager.md` is the detailed reference for Azure Update Manager itself (periodic assessment, maintenance configurations, patch orchestration modes, dynamic scoping, Arc pricing, hotpatch, Resource Graph queries, pre/post events, WSUS as a source) for Azure VMs and Arc-connected servers; that article notes Update Manager explicitly does not patch Windows 10/11 client devices, which remain this article's scope.
- Exact allowed-values lists for `AllowAutoUpdate`, `ManagePreviewBuilds`, and the four `SetPolicyDrivenUpdateSourceFor*` policies, the precise CSP default for `ConfigureFeatureUpdateUninstallPeriod`, and Windows 10 commercial ESU per-device pricing were not confirmed against a fetched CSP/pricing page in this pass; flagged in the CSV rather than stated as fact. [UNK]
- The complete Update CSP legacy-policy block (`AutoRestartDeadlinePeriodInDays`, `EngagedRestart*` family, `RequireDeferUpgrade`, `RequireUpdateApproval`) predates the deadline-based policies documented here and is out of scope for Windows 11 deployments; see the CSP reference page directly if managing pre-2019 GPO-era deferral behavior. [UNK]

## Examples
- Configure a pilot update ring (0-day quality deferral, 7-day feature deferral, 2-day quality deadline, 1-day grace period) via Intune Graph, using the Update CSP settings from the table above:
  ```
  PATCH https://graph.microsoft.com/beta/deviceManagement/deviceConfigurations/{ringPolicyId}
  Content-Type: application/json

  {
    "@odata.type": "#microsoft.graph.windowsUpdateForBusinessConfiguration",
    "qualityUpdatesDeferralPeriodInDays": 0,
    "featureUpdatesDeferralPeriodInDays": 7,
    "deadlineForQualityUpdatesInDays": 2,
    "deadlineGracePeriodInDays": 1,
    "automaticUpdateMode": "autoInstallAndRebootAtScheduledTime"
  }
  ```
- Turn on hotpatch for a quality update policy, then confirm enrollment on a pilot device (`PL-LT-00123`) via Event Viewer:
  ```powershell
  # On the device: verify VBS is Running, then check hotpatch enrollment
  Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard |
    Select-Object VirtualizationBasedSecurityStatus
  Get-WinEvent -LogName "Microsoft-Windows-WindowsUpdateClient/Operational" -MaxEvents 20 |
    Where-Object Message -like "*AllowRebootlessUpdates*"
  ```
- Deploy an expedited security update to a device audience via Graph (beta):
  ```
  POST https://graph.microsoft.com/beta/admin/windows/updates/deployments
  Content-Type: application/json

  {
    "@odata.type": "#microsoft.graph.windowsUpdates.deployment",
    "content": {
      "@odata.type": "#microsoft.graph.windowsUpdates.catalogContent",
      "catalogEntry": { "@odata.type": "#microsoft.graph.windowsUpdates.qualityUpdateCatalogEntry", "id": "catalog/entries/1" }
    },
    "settings": {
      "@odata.type": "microsoft.graph.windowsUpdates.deploymentSettings",
      "expedite": { "isExpedited": true, "isReadinessTest": false },
      "userExperience": { "daysUntilForcedReboot": 2 }
    }
  }
  ```
- Query the `UCClient` table in a WUfB reports Log Analytics workspace for devices with an unconfigured or long feature-update deadline (KQL):
  ```kusto
  UCClient
  | where WUFeatureDeadlineDays == -1 or WUFeatureDeadlineDays > 7
  | project DeviceName, OSVersion, WUFeatureDeadlineDays, WUFeaturePauseState
  ```
- Merge a device's Windows Update ETL traces into a readable log for offline analysis:
  ```powershell
  Get-WindowsUpdateLog -LogPath C:\Temp\WindowsUpdate.log
  ```
