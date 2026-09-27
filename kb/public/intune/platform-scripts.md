---
topic: intune/platform-scripts
priority: P2
applies_to: "Intune Devices > Scripts and remediations > Platform scripts (Windows 10 and later), docs ms.date/retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-p4fis3e4, S-s27f6na4, S-4elqlqiz, S-ta4g5get, S-q7b6fqko, S-ssg5k6nr]
status: complete
---

# Intune platform scripts (Windows PowerShell scripts)

## Summary
Platform scripts are standalone PowerShell scripts uploaded under **Devices > Scripts and remediations > Platform
scripts > Add > Windows 10 and later**, run once per assignment change by the Intune Management Extension (IME), with
no built-in detection/remediation pairing (contrast `intune/remediations.md`) or scheduling (contrast the Hourly/Daily
schedule on remediation scripts). Size limit 200 KB (ASCII); timeout 30 minutes; failure retries 3 times over the next
3 IME check-ins; results are logged in `AgentExecutor.log` (see `intune/ime-logs.md`). Graph exposes them as
`deviceManagementScript` (beta).

## Facts
### Authoring and settings
- Script location must point to a file less than 200 KB (ASCII). [DOC S-p4fis3e4]
- **Run this script using the logged on credentials**: Yes (default) runs with the signed-in user's credentials; No runs in the system context. [DOC S-p4fis3e4]
- **Enforce script signature check**: Yes (default) requires the script be signed by a trusted publisher; No has no signing requirement. [DOC S-p4fis3e4]
- **Run script in 64-bit PowerShell host**: No (default) runs in a 32-bit PowerShell host (works on 32-bit and 64-bit architectures); Yes runs in a 64-bit host on 64-bit clients (on 32-bit clients it still runs 32-bit). Changing this setting on an *existing* assigned script only opens (doesn't run) the script in the new host on the next run, then reports results; a genuinely new script runs directly in the selected host. [DOC S-p4fis3e4]
- Scope tags are optional on the platform script policy. [DOC S-p4fis3e4]
- Assignment targets Microsoft Entra device or user security groups; for workplace-joined (WPJ) devices only device security groups are honored (user targeting is ignored). [DOC S-p4fis3e4]
- PowerShell scripts time out after 30 minutes. [DOC S-p4fis3e4]
- Scripts don't run on Surface Hubs or on Windows in S mode. [DOC S-p4fis3e4]
- Best-practice guidance: don't put secrets or personal data in scripts, and don't use scripts to collect personal data from devices. [DOC S-p4fis3e4]

### Run behavior and retries
- A script runs once per assignment: when first assigned to a user/device, and again only if the script content or the policy is changed and re-uploaded; user sign-in alone does not re-trigger it (except per note below). [DOC S-p4fis3e4]
- Device-targeted scripts do run for every new user signing in to that device, except on multi-session SKUs where user check-in is disabled. [DOC S-p4fis3e4]
- Platform scripts run before Win32 apps on the same check-in (scripts execute first, then Win32 apps). [DOC S-p4fis3e4]
- On failure, the IME retries the script 3 times across the next 3 IME check-ins after the failing run (documented example: fails at 8 AM, retries at 9/10/11 AM = retry counts 1-3, then stops retrying at 12 PM check-in if the script/policy is unchanged). [DOC S-p4fis3e4]
- The IME also re-checks for new/changed scripts after every device reboot. [DOC S-p4fis3e4]
- If a device's system clock is far out of date (months/years), deployed scripts fail to run until the clock is corrected. [DOC S-p4fis3e4]
- When a Windows device becomes unmanaged, the IME detects this and cancels script runs only at its next check-in (usually every 8 hours); any already-locally-stored script could still run meanwhile. If the IME can't check in at all, it retries for up to 24 hours of device-awake time, then removes itself. [DOC S-p4fis3e4, S-ta4g5get]

### IME prerequisites and check-in (shared with Win32 apps/remediations)
- Devices must run IME version 1.58.103.0 or later; earlier versions don't receive Win32 app, PowerShell script, remediation, or platform-script payloads. The IME auto-updates. [DOC S-ta4g5get]
- IME install is automatic once prerequisites are met and a PowerShell script, Win32 app, Microsoft Store app, custom compliance script, or remediation is assigned; it requires a supported Windows version (not Home, not S mode) and the device to be Microsoft Entra joined, Microsoft Entra hybrid joined, or Microsoft Entra registered/workplace-joined (WPJ, BYOD via "Access work or school"), plus Intune enrollment (including GPO-enrolled or co-managed devices). [DOC S-ta4g5get]
- On co-managed devices, PowerShell scripts run regardless of the **Apps** workload setting (Configuration Manager vs. Pilot Intune/Intune); the IME still requires Entra join/hybrid join and a supported Windows version. [DOC S-ta4g5get]
- IME checks for new/updated installations (scripts, Win32 apps, etc.) with Intune every 8 hours, independent of the MDM check-in; it also performs periodic health checks. [DOC S-ta4g5get]
- After Windows Enrollment Status Page (ESP) or Autopilot device preparation finishes, the IME immediately checks for new Windows app assignments (reduces delay for required Win32 apps skipped during provisioning). [DOC S-ta4g5get]
- Manual IME check-in: Company Portal > **Settings** > **Sync** (also triggers MDM check-in), or restart the **IntuneManagementExtension** service in Task Manager/services.msc. [DOC S-ta4g5get, S-p4fis3e4]
- The IME is removed when: no PowerShell scripts remain assigned to the device, the device is no longer managed, or it stays in an irrecoverable state for over 24 hours of device-awake time. [DOC S-ta4g5get]
- The IME agent files install to `C:\ProgramData\Microsoft\IntuneManagementExtension\Logs`; it appears as service **IntuneManagementExtension** and does not show in the Start menu. [DOC S-ta4g5get]

### Troubleshooting
- To test a script outside Intune, run it as SYSTEM locally with `psexec -i -s` (Sysinternals PsExec). [DOC S-p4fis3e4]
- If a script reports success in Intune but did not actually run correctly, antivirus may be sandboxing `AgentExecutor.exe`; check `AgentExecutor.log` — a genuinely executed script produces output/error file content of length greater than 2. [DOC S-p4fis3e4]
- `AgentExecutor.exe` (`C:\Program Files (x86)\Microsoft Intune Management Extension\agentexecutor.exe`) invokes the 32-bit PowerShell host at `C:\Windows\SysWOW64\WindowsPowerShell\v1.0` with parameters `-powershell <scriptPath> <outputPath> <errorPath> <timeoutPath> <timeoutMs> <PSFolder> 0 0`; the IME normally cleans up the `.output`/`.error`/`.timeout` files after the script runs. [DOC S-p4fis3e4]
- Common non-run causes: device not joined to Microsoft Entra ID (the scripts page says devices only registered in Entra ID do not receive scripts), no script assigned to the device/user's groups, no connectivity to the Intune service or Windows Push Notification Services (WNS), device in S mode, or a corrupted/manually-altered `Microsoft.Management.Services.IntuneWindowsAgent.exe.config` file. [DOC S-p4fis3e4, S-ta4g5get]

### Graph API (`deviceManagementScript`, beta only — no v1.0 equivalent documented)
- Resource: `deviceManagementScript` under `/deviceManagement/deviceManagementScripts` (beta); Microsoft recommends v1.0 where available, but this resource is beta-only. [DOC S-s27f6na4]
- Key properties: `id`, `displayName`, `description`, `scriptContent` (Binary), `createdDateTime`, `lastModifiedDateTime` (read-only), `runAsAccount` (`system` or `user`), `enforceSignatureCheck` (Boolean), `fileName`, `roleScopeTagIds`, `runAs32Bit` (Boolean). [DOC S-s27f6na4]
- Relationships: `groupAssignments` (`deviceManagementScriptGroupAssignment`), `assignments` (`deviceManagementScriptAssignment`), `runSummary` (`deviceManagementScriptRunSummary`), `deviceRunStates` (`deviceManagementScriptDeviceState` collection), `userRunStates` (`deviceManagementScriptUserState` collection). [DOC S-s27f6na4]
- `deviceManagementScriptRunSummary` carries a read-only `id` plus four Int32 counters: `successDeviceCount`, `errorDeviceCount`, `successUserCount`, `errorUserCount`; methods are Get and Update. [DOC S-q7b6fqko]
- CRUD methods: List/Get/Create/Delete/Update `deviceManagementScript`, plus actions `assign` and `hasPayloadLinks`. [DOC S-s27f6na4]
- `deviceManagementScriptDeviceState.runState` values: `unknown`, `success`, `fail`, `scriptError`, `pending`, `notApplicable`; also carries `resultMessage`, `lastStateUpdateDateTime`, `errorCode`, `errorDescription`, and a `managedDevice` relationship. [DOC S-ssg5k6nr]
- Assign: `POST /deviceManagement/deviceManagementScripts/{deviceManagementScriptId}/assign` with body `deviceManagementScriptGroupAssignments` and/or `deviceManagementScriptAssignments`; returns `204 No Content`. [DOC S-4elqlqiz]
- Permissions for `assign` (delegated or application): `DeviceManagementScripts.ReadWrite.All` or `DeviceManagementConfiguration.ReadWrite.All` (listed in that order in a column headed "most to least privileged"); personal Microsoft accounts are not supported. [DOC S-4elqlqiz]
- Available in Global service, US Gov L4, US Gov L5 (DOD), and China (21Vianet) national clouds. [DOC S-4elqlqiz]
- `deviceManagementScript` and its full CRUD/assign surface (List/Get/Create/Update/Delete/`assign`/`hasPayloadLinks`, `deviceManagementScriptRunSummary`, `deviceManagementScriptDeviceState`, `deviceManagementScriptUserState`) are documented only under `graph-rest-beta`; no v1.0 `deviceManagementScript` resource or method page exists on Microsoft Learn (confirmed via a Microsoft Learn documentation search covering the resource and each CRUD method — all results resolve to `view=graph-rest-beta` pages only). [DOC S-s27f6na4, S-4elqlqiz]

## Reference
- The platform-scripts page points to **Remediations** for related information and applies the same privacy best practices to PowerShell and remediation scripts; detection+remediation script pairs, their scheduling and limits are covered in `intune/remediations.md` (which cross-links back to this one for platform scripts). [DOC S-p4fis3e4]
- Full IME log file list and folder path (`AgentExecutor.log` for platform-script executions): `intune/ime-logs.md`.
- Win32 app packaging, detection rules, dependency/supersedence graphs and the same IME 8-hour check-in cadence: `intune/win32-apps.md` (platform scripts run before Win32 apps on a shared check-in).
- macOS shell scripts (a separate Intune payload with its own size/format rules) are documented in `intune/macos-management.md`, not repeated here.

## Examples
Upload a platform script for `PL-LT-00123`'s device group, run as system, no signature check, 64-bit host:
1. **Devices > Scripts and remediations > Platform scripts > Add > Windows 10 and later**.
2. Script settings: browse to a `.ps1` under 200 KB; **Run this script using the logged on credentials** = No; **Enforce script signature check** = No; **Run script in 64-bit PowerShell host** = Yes.
3. Assign to the Entra device group containing `PL-LT-00123`.

- SNIPPET: assign an existing `deviceManagementScript` to a group via Graph (beta); context: Graph beta `deviceManagementScripts/{id}/assign`; checked: no [DOC S-4elqlqiz, S-s27f6na4]
```http
POST https://graph.microsoft.com/beta/deviceManagement/deviceManagementScripts/00000000-0000-0000-0000-000000000001/assign
Content-Type: application/json

{
  "deviceManagementScriptGroupAssignments": [
    {
      "@odata.type": "#microsoft.graph.deviceManagementScriptGroupAssignment",
      "id": "00000000-0000-0000-0000-000000000002",
      "targetGroupId": "00000000-0000-0000-0000-000000000003"
    }
  ]
}
```

- SNIPPET: force-fail test script (per Microsoft's troubleshooting guidance) to verify `AgentExecutor.log` reporting on `PL-LT-00123`; context: Windows platform script, run as system; checked: no [DOC S-p4fis3e4]
```powershell
Write-Error -Message "Forced Fail" -Category OperationStopped
mkdir "C:\temp"
"Forced Fail" | Out-File C:\temp\Fail.txt
```
