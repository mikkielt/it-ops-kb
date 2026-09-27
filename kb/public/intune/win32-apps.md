---
topic: intune/win32-apps
priority: P2
applies_to: "Microsoft Intune Win32 app management (Windows app (Win32) and Enterprise App Catalog app types), docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-wc6e3fba, S-ec3hg7rx, S-fipq4ix4, S-tnes5beq, S-6lyy6mvq, S-lficatwr, S-oljccwue, S-vywsads7, S-ta4g5get]
status: complete
---

# Intune Win32 apps

## Summary
Win32 apps are packaged with the Microsoft Win32 Content Prep Tool (`IntuneWinAppUtil.exe`) into a `.intunewin` file, capped at 30 GB, and delivered by the Intune Management Extension (IME), which installs automatically when a Win32 app or PowerShell script is assigned. Apps must install silently; requirement, detection, dependency (max 100 in the graph) and supersedence (max 10 nodes) rules control targeting and app lifecycle. Return codes classify install results as Success, Failed, Hard reboot, Soft reboot or Retry (3 attempts, 5 min apart). The Graph API creates a `win32LobApp` object and uploads content through a multi-step encrypted file commit flow.

## Facts

### Packaging and prerequisites
- The Microsoft Win32 Content Prep Tool converts app installer files into the `.intunewin` format; it zips all files and subfolders of the setup folder into that file. [DOC S-fipq4ix4]
- Content Prep Tool command-line parameters: `-h` (help), `-c <setup_folder>` (folder with all setup files), `-s <setup_file>` (e.g. `setup.exe` or `setup.msi`), `-o <output_folder>`, `-q` (quiet mode). [DOC S-fipq4ix4]
- Example: `IntuneWinAppUtil -c c:\testapp\v1.0 -s c:\testapp\v1.0\setup.exe -o c:\testappoutput\v1.0 -q` generates the `.intunewin` file; if the output file already exists it is overwritten, and a missing output folder is created automatically. [DOC S-fipq4ix4]
- Windows app size is capped at 30 GB per app. [DOC S-fipq4ix4, S-wc6e3fba, S-ec3hg7rx]
- Win32 apps require a supported Windows version (Enterprise, Pro, or Education) and devices Microsoft Entra registered, Microsoft Entra joined, Microsoft Entra hybrid joined, or (per `add-win32`) also group policy enrolled. [DOC S-fipq4ix4, S-wc6e3fba, S-ec3hg7rx]
- Apps must support silent/unattended installation; Intune does not support interactive installs, and techniques that force interaction with the signed-in session (e.g. `serviceui.exe`) are unsupported. [DOC S-fipq4ix4, S-wc6e3fba, S-ec3hg7rx]
- Win32 app management supports x86, x64 and ARM64 architectures, and Windows S mode devices. [DOC S-ec3hg7rx]
- The IME is installed automatically when a PowerShell script or Win32 app is assigned to the user or device, and checks every hour (or on service/device restart) for new Win32 app assignments. [DOC S-ec3hg7rx]
- Mixing Win32 and line-of-business (LOB) apps during Windows Autopilot enrollment can cause install failures because both may try to use the Trusted Installer service at once; mixing them during Windows Autopilot device preparation is supported. [DOC S-ec3hg7rx]

### Install command and PowerShell script installer
- Calling `powershell.exe` directly in the Install/Uninstall command fields launches a 32-bit PowerShell instance; to force 64-bit, use `%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe`. [DOC S-wc6e3fba]
- Environment variable expansion is not supported in the Uninstall command field; use a custom wrapper script instead. [DOC S-wc6e3fba]
- A PowerShell script can replace the standard install command (Installer type = PowerShell script); it is packaged with the app content, runs in the same context as the app installer, and install results are based on the script's return code. [DOC S-wc6e3fba, S-ec3hg7rx]
- PowerShell script installer size limit: 50 KB. [DOC S-wc6e3fba, S-ec3hg7rx]
- If Multi-Admin Approval (MAA) is enabled for the tenant, PowerShell scripts cannot be uploaded during app creation; the app must be created first, then the script added or modified. `enforceSignatureCheck` and `runAs32Bit` can currently be edited without an MAA request, but this is planned to change. [DOC S-wc6e3fba, S-ec3hg7rx]
- Installation time required: default 60 minutes, maximum 1440 minutes (1 day); if install exceeds this, the system fails the install. [DOC S-wc6e3fba]
- If a Win32 app has dependencies or is itself a dependency, Company Portal does not show the uninstall option even when "Allow available uninstall" is Yes. [DOC S-wc6e3fba]
- Install behavior is System or User; when set to User and the signed-in user has admin rights, install/uninstall runs under admin privilege by default. [DOC S-wc6e3fba]

### Device restart behavior and return codes
- Device restart behavior options: "Determine behavior based on return codes" (hard reboot code restarts immediately, soft reboot code only notifies the user a restart is needed), "No specific action" (suppresses restarts for MSI-based apps), "App install may force a device restart" (hard reboot code notifies the user of a restart in 120 minutes; soft reboot code only notifies), "Intune will force a mandatory device restart" (always restarts after successful install). [DOC S-wc6e3fba]
- Return code types: Failed, Hard reboot (blocks the next Win32 app install without a reboot), Soft reboot (allows the next Win32 app install without a client reboot, though a reboot is still needed to finish the current app), Retry (agent retries the install 3 times, waiting 5 minutes between attempts), Success. [DOC S-wc6e3fba, S-tnes5beq]
- Restart grace period is only available when Device restart behavior is "Determine behavior based on return codes" or "Intune will force a mandatory device restart". Defaults: grace period 1440 minutes (24 h, max 2 weeks); restart countdown dialog shown 15 minutes before restart; snooze duration default 240 minutes (4 h), capped at the grace period. [DOC S-ec3hg7rx]
- Standard Windows Installer return codes (from `MsiExec.exe`/`InstMsi.exe`, not Intune-specific): `0` = `ERROR_SUCCESS`; `3010` = `ERROR_SUCCESS_REBOOT_REQUIRED` (install succeeded, reboot needed); `1641` = `ERROR_SUCCESS_REBOOT_INITIATED` (installer itself started the restart); `1618` = `ERROR_INSTALL_ALREADY_RUNNING` (another install already in progress); `1602` = `ERROR_INSTALL_USEREXIT`; `1603` = `ERROR_INSTALL_FAILURE`. [DOC S-oljccwue]

### Requirement rules
- Requirement types: File (detect a file/folder by date, version or size; "associated with a 32-bit app on 64-bit clients" controls whether path variables expand in the 32-bit or 64-bit context, default No/64-bit), Registry (detect a value/string/integer/version by key path; same 32-bit-on-64-bit toggle for the registry hive searched, default No/64-bit), Script (PowerShell; exit code 0 plus STDOUT detail, e.g. an integer; options to run as 32-bit on 64-bit clients, run using signed-in user credentials, and enforce script signature check). [DOC S-wc6e3fba]
- Requirement fields also include operating system architecture, minimum operating system, disk space required (MB), physical memory required (MB), minimum number of logical processors, and minimum CPU speed (MHz). [DOC S-wc6e3fba]

### Detection rules
- All configured detection rules must be met for Intune to consider the app installed; at least one rule is required. [DOC S-wc6e3fba]
- If Intune detects the app is not present, it re-offers the app to the device within approximately 24 hours (required-intent apps only). [DOC S-wc6e3fba]
- Manual detection rule types: MSI (product code, optional product version check; can be added only once), File (path, file/folder, detection method, 32-bit-on-64-bit toggle), Registry (key path e.g. `HKEY_LOCAL_MACHINE\Software\WinRAR` or `HKLM\Software\WinRAR`, value name, detection method, 32-bit-on-64-bit toggle). [DOC S-wc6e3fba]
- Custom detection script: the app is detected as installed only when the script both exits with code 0 and writes a string value to STDOUT; if the script exits non-zero, or writes anything to STDERR (even with exit 0 and STDOUT data), the app is evaluated as not installed. Microsoft recommends encoding the script as UTF-8 BOM. [DOC S-wc6e3fba]
- The Enterprise App Catalog app type allows up to 25 detection rules and adds a "report the detected registry/file value as the app version" option (only one detection rule can have it set). [DOC S-tnes5beq]

### Dependencies
- Win32 app dependencies can only be added after the app itself has been added and uploaded to Intune. [DOC S-wc6e3fba]
- Maximum 100 dependencies in the dependency graph, counting the parent app itself: e.g. 100 dependency apps + 1 parent app = graph size 101. [DOC S-wc6e3fba]
- Graph size example: a parent with 3 dependencies, one of which has 2 further dependencies, has a total graph size of 6 (1 + 3 + 2). [DOC S-wc6e3fba]
- If an app appears as a dependency in multiple separate dependency graphs, it is counted once toward the combined total, but the graphs' sizes are otherwise summed (example in the source: graphs of 23, 62 and 20 apps sharing one common dependency app total 103, which exceeds the 100 limit). [DOC S-wc6e3fba]
- A dependency must itself be a Win32 app; other app types (single MSI LOB, Microsoft Store) cannot be dependencies. [DOC S-wc6e3fba]
- Each dependency install follows the same retry logic as the parent (3 attempts, 5 minutes apart) and the global 24-hour reevaluation cadence. Dependencies do not apply when uninstalling the parent app. [DOC S-wc6e3fba]
- An app in a dependency relationship (as parent or child) cannot be deleted until the dependency relationship is removed. [DOC S-wc6e3fba]

### Supersedence
- Supersedence lets one app version update or replace another: disable "Uninstall previous version" to update in place, enable it to uninstall the old app and install the new one. [DOC S-wc6e3fba]
- Maximum 10 nodes in a supersedence relationship graph, including references to other apps that are themselves superseded; all apps in that graph count toward the maximum. [DOC S-wc6e3fba]
- The dedicated supersedence page gives 10 nodes in its step note and for supersedence chains, but its limitations section states a maximum of 11 nodes in a single supersedence graph (superseding app, superseded apps and all related apps); the pages are inconsistent, so plan for 10 (see `_conflicts.md`). [DOC S-vywsads7]

### App relationship viewer and assignments
- The app relationship viewer shows an app's directly connected dependency and supersedence child apps, and is available for the Windows app (Win32) and Windows catalog app (Win32) types. [DOC S-ec3hg7rx]
- Assignment intents: Required, Available for enrolled devices, Uninstall. [DOC S-wc6e3fba]
- If a Win32 app is assigned to users and needs admin rights the signed-in standard user lacks, the install fails. [DOC S-wc6e3fba, S-tnes5beq]
- Win32 apps installed by Intune are not automatically uninstalled from a device when the device is unenrolled. [DOC S-ec3hg7rx]
- Apps assigned as "Available for enrolled devices" are not automatically reinstalled by Intune if a user uninstalls them. [DOC S-ec3hg7rx]
- Enterprise App Catalog apps come with install/uninstall commands prepopulated with Microsoft-recommended values, which can be overridden with an uploaded PowerShell script; Enterprise App Management (EAM) only supports managed Windows devices running 64-bit Windows. [DOC S-tnes5beq]
- The Enterprise App Catalog is part of Enterprise App Management (EAM), part of Microsoft Intune Suite and available for trial and purchase. [DOC S-tnes5beq]

### Graph API
- Create a Win32 app: `POST /deviceAppManagement/mobileApps` with `@odata.type: "#microsoft.graph.win32LobApp"`; least-privileged permission listed is `DeviceManagementConfiguration.ReadWrite.All`, more privileged is `DeviceManagementApps.ReadWrite.All` (delegated or application). [DOC S-6lyy6mvq]
- Key `win32LobApp` properties: `installCommandLine`, `uninstallCommandLine`, `applicableArchitectures` (`none`, `x86`, `x64`, `arm`, `neutral`; forced to `none` when `allowedArchitectures` is non-null), `allowedArchitectures` (`null`, `x86`, `x64`, `arm64`), `minimumFreeDiskSpaceInMB`, `minimumMemoryInMB`, `minimumNumberOfProcessors` (minimum `0`), `minimumCpuSpeedInMHz`, `rules` (collection of `win32LobAppRule`), `installExperience` (`win32LobAppInstallExperience`, includes `runAsAccount` and `deviceRestartBehavior`), `returnCodes` (collection of `win32LobAppReturnCode`), `msiInformation` (`win32LobAppMsiInformation`), `setupFilePath` (relative path of the setup file inside the encrypted package), `minimumSupportedWindowsRelease` (e.g. `Windows11_23H2`). [DOC S-6lyy6mvq]
- `rules` subtypes: `Win32LobAppFileSystemRule`, `Win32LobAppPowerShellScriptRule`, `Win32LobAppProductCodeRule`, `Win32LobAppRegistryRule`. [DOC S-6lyy6mvq]
- Committing an uploaded content file: `POST /deviceAppManagement/mobileApps/{mobileAppId}/contentVersions/{mobileAppContentId}/files/{mobileAppContentFileId}/commit` with a `fileEncryptionInfo` body (`encryptionKey`, `initializationVector`, `mac`, `macKey`, `profileIdentifier`, `fileDigest`, `fileDigestAlgorithm`); permissions same as app create (`DeviceManagementConfiguration.ReadWrite.All` or `DeviceManagementApps.ReadWrite.All`). A successful commit returns `204 No Content`. [DOC S-lficatwr]
- A PowerShell sample of the full upload flow using the `ProfileVersion1` encryption scheme is published at `https://aka.ms/fileencryptioninfo`. [DOC S-lficatwr]

## Reference
- Log files for Win32 app activity are in the IME log folder: `AppActionProcessor.log` (detection/applicability checks) and `AppWorkload.log` (Win32 app deployment activity) — see `intune/ime-logs.md` for the full log list and folder path. [DOC S-ta4g5get]
- Return code fundamentals overlap with `mecm/application-model.md` (ConfigMgr deployment types use the same Windows Installer return code semantics and a 5-level supersedence-chain guideline; Intune Win32 apps use a 10-node supersedence and 100-app dependency graph limit instead — different limits, do not conflate).
- Content equivalent to the Learn page "Prepare Win32 app content for upload" (packaging) is folded into this article; no separate topic exists for the Content Prep Tool.
- WinGet-based deployment (the **Microsoft Store app (new)** app type, `winget show [PackageId]` for finding a Store Win32 app's Installer Url, WinGet Configuration, and the `Microsoft.WinGet.Client` PowerShell module) is a separate, Store-sourced pipeline from the `.intunewin`/IME flow documented here: see `windows/winget.md`.
- `windows/delivery-optimization.md` documents the Delivery Optimization CSP/GPO settings and Microsoft Connected Cache for Enterprise that Win32 app content download uses (by default, or from a Connected Cache node when `DOCacheHost`/`DOCacheHostSource` is configured).

## Examples
- SNIPPET: package and reference an app on `PL-LT-00123`'s build share; context: Win32 Content Prep Tool `IntuneWinAppUtil.exe`; checked: no [DOC S-fipq4ix4]
```
IntuneWinAppUtil.exe -c C:\Source\MyApp\1.0 -s C:\Source\MyApp\1.0\setup.exe -o C:\Source\MyAppOutput -q
```

- SNIPPET: create a Win32 app via Graph (placeholders only); context: Graph v1.0 `deviceAppManagement/mobileApps`, `win32LobApp`, needs `DeviceManagementConfiguration.ReadWrite.All`; checked: no [DOC S-6lyy6mvq]
```http
POST https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps
Content-Type: application/json

{
  "@odata.type": "#microsoft.graph.win32LobApp",
  "displayName": "Contoso Notepad Plugin",
  "publisher": "Contoso",
  "installCommandLine": "msiexec /i \"ContosoPlugin.msi\" /qn",
  "uninstallCommandLine": "msiexec /x \"{12345A67-89B0-1234-5678-000001000000}\" /qn",
  "applicableArchitectures": "x64",
  "minimumFreeDiskSpaceInMB": 100,
  "installExperience": {
    "@odata.type": "microsoft.graph.win32LobAppInstallExperience",
    "runAsAccount": "system",
    "deviceRestartBehavior": "basedOnReturnCode"
  },
  "returnCodes": [
    { "@odata.type": "microsoft.graph.win32LobAppReturnCode", "returnCode": 0, "type": "success" },
    { "@odata.type": "microsoft.graph.win32LobAppReturnCode", "returnCode": 3010, "type": "softReboot" }
  ]
}
```

- SNIPPET: detection check for `jan.kowalski`'s device via a custom script (exit 0 + STDOUT required, no STDERR); context: Win32 app custom detection script rule; checked: no [DOC S-wc6e3fba]
```powershell
if (Test-Path "C:\Program Files\Contoso\Plugin\plugin.dll") {
    Write-Output "Detected"
    exit 0
}
exit 1
```
