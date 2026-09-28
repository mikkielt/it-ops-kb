---
topic: intune/configuration-policies
priority: P2
applies_to: "Microsoft Intune service 2026-09, Windows 10/11 client, Graph beta deviceManagementConfigurationPolicy"
retrieved_utc: 2026-09-27
sources: [S-lz7th2mw, S-ld2qiclx, S-hw4p6ks6, S-v3kf7d4m, S-vmpbvsv4, S-ytjbd4n5, S-4krq7dui, S-wz4ujka5, S-4gg3zmhr, S-v5cttaej, S1593, S-l5tq6fyo, S-xggskgmu, S-rhemzip3, S-hyfjrtuc, S-h7ijeucf, S-d2p4emn5, S-sjt243fo, S-jicw45tl, S-77gkdi7q]
status: complete
---

# Intune configuration policies: settings catalog, custom OMA-URI, ADMX, refresh

## Summary
The **settings catalog** is the current way to build a Windows device configuration profile: pick individual CSP-backed
settings (including built-in Administrative Templates/ADMX) instead of a fixed template. Settings not yet in the
catalog can be set with a **custom OMA-URI** profile pointing at a CSP node. Third-party or custom ADMX/ADML can be
**imported** (public preview) as a new profile type, or **ingested at runtime** via the `ADMXInstall` CSP node inside a
custom OMA-URI profile. All of these are delivered to the device on Intune's policy refresh/check-in schedule and are
exposed in Graph (beta) as `deviceManagementConfigurationPolicy` (`/deviceManagement/configurationPolicies`). See
`security/policy-precedence.md` for how a settings-catalog/custom/ADMX policy interacts with GPO and `MDMWinsOverGP`,
and `security/baselines-catalog.md` for the security-baseline flavor of settings-catalog policies.

## Facts
### Settings catalog
- Create path: **Devices > Manage devices > Configuration > Create > New policy**, platform (e.g. Windows 10 and later), profile type **Settings catalog**; requires at least the **Policy and Profile Manager** built-in role. [DOC S-lz7th2mw]
- Windows settings catalog settings are "directly generated from the Windows configuration service providers (CSPs)"; thousands of settings, including ADMX-backed ones, and more are added continually. [DOC S-lz7th2mw]
- A setting left at the minus sign (`-`) is **Not configured**: Intune does not manage it, removes it from the policy, and on the next check-in the setting is unlocked on the device (another writer can change it). [DOC S-lz7th2mw]
- Settings can be filtered in the picker by properties such as Windows OS edition, or user vs device scope; filtering to a specific Windows edition hides the Microsoft Edge, Office and OneDrive settings, because OS version or edition doesn't decide whether they apply. [DOC S-lz7th2mw]
- A settings catalog policy can be **exported to JSON** and **imported** to create a new policy (Devices > Configuration > `…` > Export JSON / Create > Import policy). [DOC S-lz7th2mw]
- A setting tagged `(User)` or `(Device)` in the picker is scoped accordingly: user-scoped writes to `HKCU`, device-scoped writes to `HKLM`. If the same setting is assigned to a device both as user scope and device scope, **user scope wins**. [DOC S-lz7th2mw]
- Reporting: per-policy device status, and **per-setting status** (count of devices with the setting applied/in conflict/in error, exportable to CSV); **Devices > Monitor > Assignment failures** lists settings-catalog policies that failed to deploy from a conflict or error. [DOC S-lz7th2mw]
- Conflicts: a settings-catalog (configuration) policy setting that conflicts with another configuration-policy setting is only reported, not auto-resolved — "manually resolve these conflicts." Compliance-policy settings always take precedence over configuration-policy settings on the same setting (cf. `intune/compliance-policies.md:24`). [DOC S-v5cttaej]
- A device-configuration profile (including settings catalog) can be scoped further with **applicability rules** (OS edition include/exclude; OS version min/max, e.g. `10.0.16299.0`–`10.0.17134.0`). [DOC S-xggskgmu]
- Starting with the **December 2412** service release, the **Templates > Administrative Templates** profile type is deprecated and **read-only** in the admin center; the equivalent built-in ADMX settings live in the settings catalog's Administrative Templates category instead. Custom ADMX templates can still be imported (see below). [DOC S-hw4p6ks6]
- A settings-catalog policy, whatever its contents, is governed entirely by the co-management **Device Configuration** slider (see `intune/co-management.md:23`). [DOC S1593]

### Custom OMA-URI (Templates > Custom)
- Create path: **Devices > Manage devices > Configuration > Create > New policy**, platform **Windows 10 and later**, profile type **Custom** or **Templates > Custom**; then add one OMA-URI row per setting under **Configuration settings**. [DOC S-l5tq6fyo, S-v3kf7d4m]
- Each OMA-URI row has: **Name**, **Description**, **OMA-URI** (case sensitive), **Data type**, **Value**. Data type options: Base64 (file), Boolean, String (XML file), Date and time, String, Floating point, Integer. [DOC S-v3kf7d4m]
- To be usable from Intune, the target CSP node must support **Add, Replace and Get**; if the value Intune reads back with Get does not match what Add/Replace set, Intune reports a **compliance error**. [DOC S-v3kf7d4m]
- Values stored as string, base64 or XML data types are **obscured** in the console; only a role with **Device configurations > Create/Read/Update** (e.g. Policy and Profile Manager) or the Intune Administrator Entra role can see them. [DOC S-v3kf7d4m]
- Intune does not evaluate the payload of a custom OMA-URI (or Apple custom) policy — it is only the delivery mechanism; if a custom policy's settings conflict with another custom/compliance/configuration policy, **Apple randomly applies the settings** on iOS/macOS (Windows conflict handling for custom OMA-URI is not stated on this page). [DOC S-v5cttaej]
- Example custom OMA-URI target: `./Vendor/MSFT/Policy/Config/System/AllowTelemetry`, Integer, value `1` (minimum = required/basic diagnostic data). [DOC S-rhemzip3]

### ADMX: built-in vs imported vs runtime-ingested
- Built-in ADMX (Windows-shipped, `%SystemRoot%\PolicyDefinitions`) is processed into MDM (Policy CSP) policies at OS build time and configured through the **settings catalog** (Administrative Templates category) or a custom profile; don't import these built-in files to configure them — import one only when another ADMX needs it as a parent namespace. [DOC S-hw4p6ks6, S-vmpbvsv4, S-ld2qiclx]
- **Import custom ADMX/ADML** (public preview): **Devices > Manage devices > Configuration > Import ADMX tab > Import**; requires the **Policy and Profile Manager** role, plus **Device configurations > Delete** to reset an ADMX-backed setting to **Not Configured**. [DOC S-ld2qiclx]
- Import limits: max **20 ADMX files**, each **≤1 MB**; **one ADML per ADMX**, **en-us only**; **combo box** setting type is not supported and fails import; dependency ADMX files (found via `policyNamespaces` `using prefix` in the ADMX) must be imported first, in order (e.g. `Windows.admx` before a file that needs it), and dependents must be deleted before their prerequisite. [DOC S-ld2qiclx]
- After import, create a profile with platform **Windows 10 and later**, profile type **Templates > Imported Administrative templates (Preview)**. [DOC S-ld2qiclx]
- Replacing an already-imported ADMX with the same settings fails with a namespace error; fix by deleting profiles + the ADMX then re-importing, or by publishing a new ADMX with a different (versioned) namespace. [DOC S-ld2qiclx]
- **Runtime ADMX ingestion** (separate from the Intune import feature): send the whole ADMX file as a string (`<Format>chr</Format>`) payload to `./Device/Vendor/MSFT/Policy/ConfigOperations/ADMXInstall/<AppName>/<SettingType>/<FileUid>`; the ingested file is processed into ADMX-backed MDM policies. [DOC S-ytjbd4n5, S-4krq7dui]
- After ingestion, set the ingested policy with a second custom OMA-URI: `./Device/Vendor/MSFT/Policy/Config/<AppName>~<SettingType>~<CategoryPathFromAdmx>/<PolicyName>`, value `<enabled/>` / `<disabled/>` (plus `<data id=.. value=..>` for each ADMX `<elements>` field), sent with `<Format>chr</Format>` in the raw SyncML. [DOC S-vmpbvsv4, S-ytjbd4n5]
- `ADMXInstall` requires **Windows 10, version 1709 (10.0.16299)** or later; `Replace` support needs specific 1709/1803/1809/1903 cumulative updates. [DOC S-4krq7dui, S-ytjbd4n5]
- Ingested ADMX policies are **blocked from writing** to `System`, `Software\Microsoft` and `Software\Policies\Microsoft`, except an explicit allow-list (e.g. `Software\Policies\Microsoft\Office\`, `Software\Microsoft\Windows\CurrentVersion\Explorer\`, `Software\Microsoft\Edge`, `Software\Microsoft\OneDrive`); settings outside the allow-list must be pushed by another mechanism (e.g. a PowerShell script). [DOC S-ytjbd4n5]
- Deleting an ingested ADMX file (`DELETE` on its `ADMXInstall/<AppName>/...` node) removes the file from disk, its metadata, and every policy set from it; deleting `ADMXInstall/{AppName}` removes all policies tied to that app. [DOC S-4krq7dui]
- ADMX policy states map to SyncML verbs: **Enabled** → `Replace` with `<enabled/>` (+ `<data>` per ADMX element); **Disabled** → `Replace` with `<disabled/>`; **Not Configured** → `Delete` on the node. [DOC S-vmpbvsv4]

### Policy refresh / check-in
- **Change-based sync**: assigning, updating or unassigning a policy/profile/app (or an Entra group-membership change) triggers a push notification to online devices; delivery can take from immediate up to a few hours and varies by platform. An offline/disconnected device gets the change on its next sync. [DOC S-v5cttaej]
- **Client-initiated maintenance sync**: ~every **8 hours** on all platforms, but a device is only allowed **one maintenance sync per 6.5 hours** regardless of the client's own schedule. [DOC S-v5cttaej]
- **Newly enrolled Windows device**: syncs **every 3 minutes for the first 15 minutes**, then **every 15 minutes for the next 2 hours**, then settles to the ~8-hour cadence (same table values for Android/AOSP; iOS/iPadOS and macOS start at every 15 minutes for 1 hour instead). [DOC S-v5cttaej]
- **Single-device sync**: an end user (Company Portal "sync") or admin action (device **Sync**, remote lock, reset passcode) forces an immediate check-in; "remotely assist users" does not trigger a check-in. [DOC S-v5cttaej]
- On Windows, admin-triggered **Sync** runs an on-demand sync across configuration-policy processing, app detection/deployment, and script/remediation processing (Graph `syncDevice` action; roles: Help Desk Operator, School Administrator, Endpoint Security Manager, or a custom role with `Remote tasks/Sync devices`). [DOC S-hyfjrtuc]
- If a user is removed from a group a profile targets, removal from that user can take **up to 7 hours or more**: the time for the policy-assignment change plus the platform-specific refresh cycle above. [DOC S-v5cttaej]
- When a profile is deleted/unassigned on Windows, whether the setting is removed or **tattooed** (left in place) "depends on the CSP"; some CSPs remove it, some do not. (See `security/policy-precedence.md` for the GPO/MDM tattooing precedent.) [DOC S-v5cttaej]

### Graph: deviceManagementConfigurationPolicy (beta)
- Resource `microsoft.graph.deviceManagementConfigurationPolicy`: key properties `id`, `name`, `description`, `platforms` (`windows10`, `windows10X`, `android`, `iOS`, `macOS`, `linux`, `androidEnterprise`, `aosp`, `visionOS`, `tvOS`, `unknownFutureValue`, `none`), `technologies` (`mdm`, `configManager`, `windows10XManagement`, `appleRemoteManagement`, `microsoftSense`, `exchangeOnline`, `mobileApplicationManagement`, `linuxMdm`, `extensibility`, `enrollment`, `endpointPrivilegeManagement`, `windowsOsRecovery`, `android`, `none`, `unknownFutureValue`), `settingCount`, `roleScopeTagIds`, `isAssigned` (read-only), `templateReference` (`templateId`, `templateFamily`, `templateDisplayName`, `templateDisplayVersion`), `priorityMetaData.priority`. [DOC S-wz4ujka5]
- Relationships: `settings` (`deviceManagementConfigurationSetting` collection) and `assignments` (`deviceManagementConfigurationPolicyAssignment` collection). [DOC S-wz4ujka5]
- `POST /deviceManagement/configurationPolicies` creates a policy; requires delegated or application permission `DeviceManagementConfiguration.ReadWrite.All` (or `DeviceManagementEndpointSecurity.ReadWrite.All`); not supported for personal Microsoft accounts. Success returns `201 Created` with the new policy. [DOC S-4gg3zmhr]
- Other operations on the same resource: List, Get, Update and Delete, and the `assign`, `createCopy` (body `displayName`, `description`; `POST .../configurationPolicies/{id}/createCopy`) and `reorder` actions; `GET /deviceManagement/configurationPolicies/{id}` accepts `DeviceManagementConfiguration.Read.All` in addition to the ReadWrite scopes. [DOC S-wz4ujka5, S-h7ijeucf, S-d2p4emn5]
- A setting instance can be `#microsoft.graph.deviceManagementConfigurationChoiceSettingInstance`: `settingDefinitionId` (inherited from `deviceManagementConfigurationSettingInstance`) plus `choiceSettingValue` with a string `value` and optional nested `children`. [DOC S-sjt243fo]
- The Graph create page's request-body table lists `platforms` (`none`, `android`, `iOS`, `macOS`, `windows10X`, `windows10`, `linux`, `androidEnterprise`, `aosp`, `visionOS`, `tvOS`, ...) and `technologies` (`none`, `mdm`, `configManager`, `microsoftSense`, `mobileApplicationManagement`, `endpointPrivilegeManagement`, `enrollment`, ...) among the properties "required when you create" a policy; its one example body sets both (`android` / `mdm`). [DOC S-4gg3zmhr]
- That table also lists generated and read-only properties (`id`, `createdDateTime`, `isAssigned`), so it does not separate truly required fields, and no Windows settings-catalog JSON example is published (re-read 2026-09-27): always set `platforms` (`windows10`) and `technologies` (`mdm`) explicitly on create. [DER S-4gg3zmhr: table and example read together]

## Reference
- `agents/security-copilot-endpoint.md` — the Policy Configuration Agent (public preview, retiring 2026-08-31) that parses uploaded documents/plain-language requirements into settings-catalog policies, and Copilot in Intune's policy-summarization prompts, both act on the settings-catalog objects documented here.
- `security/policy-precedence.md` (MDMWinsOverGP, GPO vs MDM precedence, co-management workload precedence) — do not repeat those facts here; add there instead. Back-link added there under Reference.
- `intune/co-management.md:23` — the Device Configuration slider governs settings-catalog policies regardless of content.
- `security/baselines-catalog.md:59` — security baselines are also delivered as settings-catalog-style policies.
- `intune/compliance-policies.md:24` — compliance policy settings always win over configuration (settings-catalog/custom/ADMX) policy settings on a conflicting setting.
- `intune/mdmdiagnosticstool.md` — on-device diagnostics tool and its `-area` values; use it (or Settings > Accounts > Access work or school > Info > **Create report**) to capture the on-device state of applied configuration policies (`MDMDiagHtmlReport.html`, registry dump) referenced below.
- `windows/smart-app-control.md:40` — another custom OMA-URI example (`ApplicationControl` CSP, Base64 policy, 350,000-byte limit).
- `intune/macos-management.md` — the settings-catalog-delivered Platform SSO and FileVault policies for macOS reuse this article's settings-catalog mechanics (Not configured semantics, per-setting status, applicability rules).
- `intune/certificates-pki.md` — SCEP/PKCS certificate profiles that the Wi-Fi/VPN/802.1X profiles built here reference for client authentication; delivered on the same policy check-in/refresh cadence described above.
- `windows/kiosk-assigned-access.md` — the Intune Kiosk template and any custom OMA-URI against the `AssignedAccess` CSP (`./Vendor/MSFT/AssignedAccess/Configuration`/`ShellLauncher`) are delivered and refreshed by the same policy check-in mechanics documented above.

### On-device diagnostics
- Applied device-scope Policy CSP values land under `HKLM\SOFTWARE\Microsoft\PolicyManager\current\device\<Area>`, and the MDM provider's copy under `HKLM\SOFTWARE\Microsoft\PolicyManager\Providers\<GUID>\default\Device\<Area>`. [DER S-jicw45tl, S-4krq7dui: the BitLocker troubleshooting page shows both keys for the BitLocker area; generalized to other `./Device/Vendor/MSFT/Policy/Config/<Area>` areas of the Policy CSP]
- `mdmdiagnosticstool.exe` collects an `MdmDiagReport_RegistryDump.reg` snapshot and `MDMDiagHtmlReport.html`/`MDMDiagReport.xml`, which include the applied Policy CSP / PolicyManager state for troubleshooting a configuration policy that did not apply — see `intune/mdmdiagnosticstool.md` for the sourced facts on the tool's areas and output.
- No dedicated event ID range for configuration-policy (Policy CSP) apply failures is documented (re-read 2026-09-27): Microsoft's guidance filters the `DeviceManagement-Enterprise-Diagnostics-Provider/Admin` channel by Critical/Error/Warning and searches for the CSP path, and failed commands appear as `MDM ConfigurationManager: Command failure status` entries naming the CSP URI and result. [DER S-jicw45tl, S-77gkdi7q: absence; guidance and message text from the two pages]

## Examples
- Custom OMA-URI, enable telemetry minimum level on `PL-LT-00123`: Name `Allow Telemetry`, OMA-URI `./Vendor/MSFT/Policy/Config/System/AllowTelemetry`, Data type Integer, Value `1`.
- Ingest a vendor ADMX (`contoso.admx`) then set one of its policies:
  1. Custom OMA-URI: Name `Contoso ADMX ingestion`, OMA-URI `./Device/Vendor/MSFT/Policy/ConfigOperations/ADMXInstall/Contoso/Policy/ContosoAdmx`, Data type String, Value = full text of `contoso.admx`.
  2. Custom OMA-URI: Name `Contoso: Enable feature X`, OMA-URI `./Device/Vendor/MSFT/Policy/Config/Contoso~Policy~ContosoCategory/EnableFeatureX`, Data type String, Value `<enabled/>`.
- Graph: `POST https://graph.microsoft.com/beta/deviceManagement/configurationPolicies` with header `Authorization: Bearer <token>` (scope `DeviceManagementConfiguration.ReadWrite.All`) and body `{"name": "PL-LT-00123 baseline", "platforms": "windows10", "technologies": "mdm"}`, then `POST .../{id}/assign` to target a group (tenant `00000000-0000-0000-0000-000000000000`).
