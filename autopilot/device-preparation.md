---
topic: autopilot/device-preparation
priority: P1
applies_to: "Windows Autopilot device preparation (v2), memdocs, docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-6htyzc3j, S-xp44rfad, S-7cxticpd, S-ogiphajf, S-3w5igyu3, S-kcoqv2wr, S-pvo4qjfp, S-ubpss7bf, S-oyfbtzrp, S-2dqskpmr, S-ww4g7luc, S-otgnfdud, S-lfd7criv, S-s3auwm6y, S-iqksiiaq, S-b6krqeqe, S-mgri56wc, S-nxjyvkmx, S-ec3hg7rx, S-pfq3p4yz]
status: complete
files: [autopilot/v1-vs-v2.csv]
---

# Windows Autopilot device preparation (v2): policy, ESP comparison, pre-provisioning, diagnostics

## Summary
- Windows Autopilot device preparation ("v2") is a re-architecture of Windows Autopilot: same OOBE experience to admins and users, different underlying architecture, no requirement to register devices. [DOC S-ogiphajf]
- It does not use the Enrollment Status Page (ESP); a `Setting up for work or school` screen with a percentage progress indicator shows instead. If ESP appears, device preparation is not running. [DOC S-ogiphajf]
- Admins configure a single device preparation policy (deployment/OOBE settings, apps, scripts) plus an assigned device security group owned by the **Intune Provisioning Client** service principal (AppId `f1346770-5b25-470b-88bd-d5744ab7952c`). [DOC S-6htyzc3j, S-kcoqv2wr]
- Pre-provisioning and self-deploying mode are not supported in device preparation; they remain Windows Autopilot (classic, "v1") scenarios. [DOC S-ogiphajf]
- LAPS event 20000 (CSP rejected because the device isn't joined yet) is expected and benign during the technician phase of classic Autopilot pre-provisioning. [DOC S-pfq3p4yz] (see `windows/laps.md`)

## Facts

### What device preparation is and requirements
- Device preparation supports user-driven and automatic (Windows 365 Frontline shared mode, preview) deployment flows, and only Microsoft Entra join (no hybrid join). [DOC S-6htyzc3j]
- Supported Windows versions: Windows 11 version 24H2 or later; 23H2 with KB5035942 or later; 22H2 with KB5035942 or later. [DOC S-6htyzc3j, S-xp44rfad]
- Windows 365 Cloud PC support additionally needs 24H2 with KB5052093 or later (or the image-gallery equivalents). [DOC S-xp44rfad]
- Supported editions: Windows 11 Pro, Pro Education, Pro for Workstations, Enterprise, Education, Enterprise LTSC. [DOC S-xp44rfad]
- Licensing: needs Microsoft Entra ID + Intune (or equivalent MDM) via M365 Business Premium, F1/F3, academic A1/A3/A5, E3/E5, EMS E3/E5, Intune for Education, or Entra ID P1/P2 + Intune. [DOC S-xp44rfad]
- Networking: DNS + HTTP(80)/HTTPS(443)/NTP(123 UDP) to all hosts at minimum; diagnostics upload needs `lgmsapeweu.blob.core.windows.net` reachable; diagnostics are retained 28 days. [DOC S-xp44rfad]
- Proxy settings for device preparation should be set on the proxy server itself; deploying them via Intune policy "isn't fully supported" and may cause issues with privileged-access deployments. [DOC S-xp44rfad]
- Required Intune RBAC permissions for an admin: Device configurations (Read/Delete/Assign/Create/Update), Enrollment programs → Enrollment time device membership assignment, Managed apps Read, Mobile apps Read, Organization Read. [DOC S-xp44rfad]
- If a device is registered with classic Autopilot: when it is not associated with the tenant, the classic Autopilot profile takes precedence; when associated, device association takes precedence and device preparation runs. To force device preparation on a registered device, deregister it first. [DOC S-6htyzc3j, S-oyfbtzrp]

### Device group (Enrollment Time Grouping)
- Device preparation uses an **assigned** (static) device security group, never a dynamic group; devices are added to it automatically during deployment ("Enrollment Time Grouping"), not by hand. [DOC S-2dqskpmr]
- The device group's **Microsoft Entra roles can be assigned to the group** setting must be **No**. [DOC S-2dqskpmr]
- The group's owner must be the **Intune Provisioning Client** service principal (AppId `f1346770-5b25-470b-88bd-d5744ab7952c`); in some tenants it displays as **Intune Autopilot ConfidentialClient** — the AppId, not the name, identifies it. [DOC S-kcoqv2wr]
- If that AppId is missing from the tenant, it must be added via PowerShell (`Install-Module Microsoft.Graph.Authentication` then a Graph call to create the service principal). [DOC S-kcoqv2wr]
- Missing/incorrect owner symptoms: policy shows **0 groups assigned**, or save errors `There was a problem with the device security group for <policy_name>...` / `Failed to update security group device preparation setting...`. [DOC S-kcoqv2wr]
- Only apps/scripts explicitly selected in the device preparation policy are delivered during OOBE; other apps/scripts/policies assigned to the same device group sync but are applied (and only tracked) after OOBE completes. [DOC S-6htyzc3j]

### Policy settings (user-driven, Microsoft Entra join)
- Deployment settings: Deployment mode = User-driven; Deployment type = Single user; Join type = Microsoft Entra joined; User account type = Standard User or Administrator. [DOC S-oyfbtzrp]
- If User account type = Standard User, Intune removes the user from the local Administrators group (which Entra join adds them to by default) before the user reaches the desktop. [DOC S-oyfbtzrp]
- OOBE settings: **Minutes allowed before showing installation error** — whole-deployment timeout, integer 15–720; **Custom error message**; **Allow users to skip setup after multiple attempts** (adds a Continue anyway button); **Show link to diagnostics** (adds a diagnostics-log link on failure). [DOC S-oyfbtzrp]
- OOBE customization settings (Language/Region, Automatically configure keyboard, Hide EULA, Hide privacy settings, Hide change account options, Apply device name template) apply only to devices bound via device association; they have no effect on devices onboarded only via corporate identifiers. Apps and Scripts sections apply to all device preparation deployments regardless of association. [DOC S-oyfbtzrp]
- Apply device name template: prefix plus `%RAND:4%` or `%SERIAL%`; result up to 63 characters. [DOC S-oyfbtzrp]
- Apps: up to 25 managed applications (LOB, Win32, Microsoft Store apps that support WinGet, Microsoft 365, Enterprise App Catalog); Win32 and LOB apps can be mixed in the same device preparation deployment (unlike classic Autopilot, where mixing them risks Trusted Installer service contention). [DOC S-oyfbtzrp, S-ec3hg7rx]
- Scripts: up to 10 PowerShell scripts. Apps and scripts should target the device security group and run in the **System** context (for scripts: **Run this script using the logged on credentials** = No), since OOBE has no signed-in user. [DOC S-oyfbtzrp]
- Automatic mode (Windows 365) policy: up to 10 apps and up to 10 scripts (not 25/10 as in user-driven). [DOC S-ww4g7luc]
- Policy priority: when multiple policies target a user, the one with the smallest **Priority** number wins; drag to reorder. A device-based assignment always takes precedence over a user-based one. Priority is grayed out / not honored for automatic-mode policies, which are assigned directly in the Cloud PC provisioning policy. [DOC S-oyfbtzrp, S-kcoqv2wr]
- Onboarding trusted devices: use **either** corporate identifiers (pre-uploaded serial/manufacturer/model, only needed if enrollment restrictions block personal devices) **or** device association — not both; device association also unlocks the OOBE-customization settings above. [DOC S-oyfbtzrp, S-6htyzc3j]
- Automatic mode for Windows 365: the device preparation policy is referenced from the Cloud PC provisioning policy's **Autopilot Device preparation policy** field; **Minutes allowed before device preparation fails** accepts 10–360 minutes (recommended minimum 30). [DOC S-otgnfdud]

### Comparison: device preparation vs. classic Windows Autopilot
- Device preparation does not require device registration; classic Autopilot does. [DOC S-7cxticpd]
- Device preparation supports Microsoft Entra join only; classic Autopilot also supports Microsoft Entra hybrid join. [DOC S-7cxticpd]
- Device preparation supported modes: user-driven, automatic. Classic Autopilot modes: user-driven, pre-provisioned, self-deploying, existing devices; only classic Autopilot supports Windows Autopilot Reset, HoloLens, Teams Meeting Room, DFCI management, and Autopilot-into-co-management. [DOC S-7cxticpd]
- Device preparation supports Windows 11 only (24H2, or 23H2/22H2 with KB5035942+); classic Autopilot supports all currently supported Windows 11 and Windows 10 GA versions. [DOC S-7cxticpd]
- Device preparation and classic Autopilot can run side by side in a tenant, but any one device runs only one of them; precedence follows the device's association state (see Facts above). [DOC S-7cxticpd]
- App limits: device preparation up to 25 apps + 10 scripts, device-based only, delivered during OOBE; classic Autopilot supports up to 100 apps (per ESP "block access" limit) across device ESP and user ESP phases. [DOC S-7cxticpd]
- Reporting: device preparation's deployment report shows all device preparation deployments, has more data, and is near real-time; classic Autopilot's deployment report only shows Autopilot-registered devices and is not real-time. [DOC S-7cxticpd]
- Device preparation supports GCC High and DoD (and Intune operated by 21Vianet) tenants; classic Autopilot does not (per the compare table). [DOC S-7cxticpd, S-ogiphajf]
- Device preparation is more consistent/reliable because it delivers apps and scripts serially, reducing conflicts between providers (e.g. Win32 vs LOB). [DOC S-ogiphajf]
- Full capability comparison table: `autopilot/v1-vs-v2.csv`. [DOC S-7cxticpd]

### Classic Autopilot ESP (v1) — for comparison
- The Enrollment Status Page (ESP) has a Device ESP phase (OOBE, device policies/apps) followed by a User ESP phase (user sign-in, user policies/apps); it does not exist in device preparation. [DOC S-lfd7criv]
- Default ESP is assigned to all devices with **Show app and profile configuration progress** off by default; Microsoft recommends a custom ESP with it turned on. [DOC S-lfd7criv]
- ESP timeout ("Show an error when installation takes longer than specified number of minutes") defaults to **60 minutes**. [DOC S-lfd7criv]
- Default ESP failure message: `Setup could not be completed. Please try again or contact your support person for help.` (customizable). [DOC S-lfd7criv]
- **Block device use until required apps are installed**: All (every assigned app must install first) or Selected (only chosen apps block usage); enabling blocking unlocks **Allow users to reset device on install error** and **Allow users to use device on install error**. [DOC S-lfd7criv]
- **Turn on log collection and diagnostics page for end users**: shows a Collect logs button on failure and (Windows 11 only) the Windows Autopilot diagnostics page. [DOC S-lfd7criv]
- Hybrid Microsoft Entra join deployments with ESP can take roughly 40 minutes longer than the configured timeout, to give the on-prem AD connector time to create the device record in Entra ID. [DOC S-b6krqeqe]
- `EnrollmentStatusTracking` CSP (Windows 10 1903+) writes ESP tracking state under `HKLM\SOFTWARE\Microsoft\Windows\Autopilot\EnrollmentStatusTracking`, including IME install status and Win32/LOB/Store app install status per phase. [DOC S-b6krqeqe]

### Pre-provisioning (white glove) — classic Autopilot only
- Pre-provisioning splits deployment: a technician/OEM/partner performs the time-consuming portion; the end user only completes a minimal set of steps and policies. [DOC S-s3auwm6y]
- Requires a currently supported Windows version (Pro/Enterprise/Education), an Intune subscription, and a physical device with TPM 2.0 plus device attestation (VMs are not supported — the process uses self-deploying capabilities under the hood); an ESP profile must be targeted to the device. [DOC S-s3auwm6y]
- Two scenarios: user-driven with Microsoft Entra join, and user-driven with Microsoft Entra hybrid join; both have a technician flow and a user flow, differing mainly in the authentication steps shown to the end user. [DOC S-s3auwm6y]
- Technician flow trigger: from the first OOBE screen, don't select Next — press the Windows key five times to open an options dialog, then select **Windows Autopilot provisioning** and Continue; the Windows Autopilot Configuration screen shows the assigned profile, org name and assigned user. [DOC S-s3auwm6y]
- Pre-provisioning has two ESP phases like other Autopilot user-driven flows: Device ESP (Windows configured, device apps/policies applied) then User ESP (user signs in, user apps/policies applied). [DOC S-iqksiiaq]
- A device cannot automatically re-enroll through Autopilot after an initial pre-provisioned deployment; the device record must be deleted in the Intune admin center (Devices > All devices > select > Delete) before it can be re-provisioned. [DOC S-s3auwm6y]
- Hybrid pre-provisioning postpones the reboot that would normally contact the on-prem domain controller: the device is resealed before that point, and the domain network is contacted only when the end user unboxes it on-premises — so pre-provisioning itself needs no access to on-prem AD infrastructure. [DOC S-s3auwm6y]
- Pre-provisioning is not currently supported in Windows Autopilot device preparation; it is planned for a future release. [DOC S-ogiphajf]

### Diagnostics and logs
- Windows Autopilot device preparation deployment report: **Devices | Monitor** → **Windows Autopilot device preparation deployments**. Per-device fields: Device name, Enrollment date, Deployment status (In progress/Success/Failed), Phase (Policy installation, Script installation, App installation), Serial number, Deployment time, UPN. [DOC S-pvo4qjfp]
- Device deployment details add: Device ID, Microsoft Entra device ID, Deployment policy name, Policy Version (increments on every saved policy change), OS version, plus per-app and per-script status (Installed, In progress, Skipped, Failed). [DOC S-pvo4qjfp]
- Diagnostics logs for failed device preparation deployments are automatically collected on error and downloadable from Device deployment details (added 2024-10-09); deployment records/logs are cleaned up automatically after 28 days. [DOC S-ubpss7bf, S-pvo4qjfp]
- Classic Autopilot diagnostics page (Windows 11, user-driven mode, work/school sign-in only — not personal Microsoft accounts): enable via the ESP profile (**Show app and profile configuration progress** = Yes and **Turn on log collection and diagnostics page for end users** = Yes); open with **View Diagnostics** or Ctrl+Shift+D. [DOC S-mgri56wc]
- Autopilot event log: Event Viewer → Applications and Services Logs → Microsoft → Windows → **ModernDeployment-Diagnostics-Provider** → **Autopilot**. [DOC S-mgri56wc]
- Manual log collection command (Windows 10 1809+, user-driven): `mdmdiagnosticstool.exe -area Autopilot -cab <pathToOutputCabFile>`; for self-deploying/white glove/other physical-device scenarios: `mdmdiagnosticstool.exe -area Autopilot;TPM -cab <pathToOutputCabFile>`. [DOC S-b6krqeqe]
- `Get-AutopilotDiagnostics` (PowerShell Gallery script, `Install-Script -Name Get-AutopilotDiagnostics -Force`) parses the generated CAB to summarize Autopilot/ESP failures: `Get-AutopilotDiagnostics -CABFile <pathToOutputCabFile>`. [COMMUNITY S-b6krqeqe]
- Intune's **Collect diagnostics** device action captures device logs; it cannot be run via Graph directly (portal/bulk action only, up to 25 devices at once), is retained 28 days, and up to 10 collections are stored per device; it can auto-trigger (one set per day) on an Autopilot deployment failure if automatic capture is enabled. [DOC S-nxjyvkmx]
- Automatic diagnostics upload from the client requires `lgmsapeweu.blob.core.windows.net` to be reachable; diagnostics are retained 28 days before removal. [DOC S-xp44rfad]

### Known issues (device preparation)
- Managed Installer policy during OOBE is not supported (can cause incorrect reporting); custom compliance and the device health script are not supported during device preparation deployments (initial release). [DOC S-3w5igyu3]
- A tenant-level Managed Installer policy causes Win32, Microsoft Store, and Enterprise App Catalog apps to be skipped during device preparation. [DOC S-3w5igyu3]
- Devices not in the UTC time zone could fail deployment (resolved July 2024); the documented workaround was `Set-TimeZone -Id "UTC"` in OOBE PowerShell. [DOC S-3w5igyu3]
- BitLocker could default to 128-bit even when 256-bit was configured, due to a race condition; resolved by KB5124012 and later updates. [DOC S-3w5igyu3]
- Conflict between Entra ID **Local administrator settings** and the policy's **User account type**: when User account type = Standard user and the Entra setting is Selected/None, provisioning is skipped and the user can reach the desktop without the intended apps. Documented safe combinations pair Entra "All" with policy "Administrator", or Entra "Selected" (admins chosen) with policy "Administrator", for an admin outcome; and Entra "None" with policy "Administrator", or Entra "Selected" (non-admins chosen) with policy "Standard user", or Entra "All" with policy "Standard user", for a standard-user outcome. [DOC S-3w5igyu3]
- A device can get stuck at 100% during OOBE; the documented workaround is a manual restart (fix in progress as of the known-issues page). [DOC S-3w5igyu3]

## Reference
| Setting | Value | Source |
|---|---|---|
| Apps per user-driven policy | up to 25 | S-oyfbtzrp |
| Apps per automatic (Windows 365) policy | up to 10 | S-ww4g7luc |
| Scripts per policy (any mode) | up to 10 | S-oyfbtzrp |
| OOBE install timeout range | 15-720 minutes | S-oyfbtzrp |
| Automatic mode failure timeout range | 10-360 minutes (recommended min. 30) | S-otgnfdud |
| Classic ESP default timeout | 60 minutes | S-lfd7criv |
| Device name template max length | 63 characters | S-oyfbtzrp |
| Diagnostics retention | 28 days | S-xp44rfad, S-nxjyvkmx |
| Intune Provisioning Client AppId | `f1346770-5b25-470b-88bd-d5744ab7952c` | S-kcoqv2wr |

Full v1-vs-v2 feature comparison: `autopilot/v1-vs-v2.csv` [DOC S-7cxticpd].

Cross-links: `autopilot/device-identity.md` (hardware hash, ZTDID, group tag used by classic Autopilot registration), `autopilot/lifecycle.md` (deregistration required before device preparation can run on a previously registered device, and back-links here), `intune/win32-apps.md` (Win32/LOB mixing behavior during device preparation vs. classic Autopilot enrollment), `windows/laps.md` (event 20000, benign during the pre-provisioning technician phase), `windows/windows-365.md` (the Cloud PC provisioning policy and editions that automatic-mode device preparation policies attach to for Windows 365 Frontline/Flex shared mode).

## Examples
- Deregister `PL-LT-00123` from classic Autopilot before running device preparation on it: `DELETE /deviceManagement/windowsAutopilotDeviceIdentities/{id}` (see `autopilot/lifecycle.md`), then associate or corporate-identify the device for device preparation.
- Manual log collection on a user-driven device preparation failure: `mdmdiagnosticstool.exe -area Autopilot -cab C:\temp\PL-LT-00123-autopilot.cab`.
