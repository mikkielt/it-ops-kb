---
topic: mecm/osd-task-sequences
priority: P1
applies_to: "ConfigMgr current branch (osd/* docs, checked 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-lydse5ww, S-nmfqbv57, S-dz6j2643, S-kwn2lclu, S-ruy2unms, S-6pxhq347, S-jjjidz73, S-bf2nomrq, S-xigzahvp, S-qethz2s6, S212]
status: partial
files: [mecm/task-sequence-variables.csv]
---

# ConfigMgr OS deployment task sequences: steps, variables, boot media, smsts.log

## Summary
A task sequence is an ordered list of steps and groups (`SMS_TaskSequence`/`SMS_TaskSequence_Step` WMI classes) that
Configuration Manager runs to deploy or service an OS: apply an OS image or upgrade package, apply Windows/network
settings, install apps and updates, and restart. It starts from a boot image (a WinPE build from a supported Windows
ADK release) delivered by PXE, bootable media, prestaged media or the client's own policy. Built-in, read-only
variables (prefixed `_`, e.g. `_SMSTSMachineName`, `_SMSTSInWinPE`) describe the running environment; settable
variables (built-in without the underscore, action, or custom) configure step behavior and can be read/written from
a PowerShell script through the `Microsoft.SMS.TSEnvironment` COM object. The task sequence log **smsts.log** moves
through several paths as the destination disk becomes available and the client installs; `mecm/log-files.csv` has
the row cited by every phase below.

## Facts

### Steps and structure
- A task sequence is built from `SMS_TaskSequence` (the sequence) and `SMS_TaskSequence_Step`-derived classes: `SMS_TaskSequence_Group` for groups and `SMS_TaskSequence_Action`-derived classes for built-in or custom actions, run sequentially. [DOC S-dz6j2643]
- Core OS deployment steps: Apply Operating System Image (WinPE only; sets `OSDTargetSystemDrive`), Setup Windows and ConfigMgr (transitions WinPE to the full OS, installs the client, replaces `%WINDIR%`/`%ProgramFiles%`-style variables with the WinPE path `X:\Windows` during the WinPE portion), Apply Windows Settings, Apply Network Settings, Apply Driver Package / Apply Device Drivers, Install Application, Install Package, Install Software Updates, Run Command Line, Run PowerShell Script, Set Task Sequence Variable, Set Dynamic Variables, Run Task Sequence (child task sequence), Restart Computer. [DOC S-dz6j2643]
- Non-OS-deployment custom task sequences support only a subset of steps: Check Readiness, Connect To Network Folder, Download Package Content, Install Application, Install Package, Install Software Updates, Restart Computer, Run Command Line, Run PowerShell Script, Run Task Sequence, Set Dynamic Variables, Set Task Sequence Variable. [DOC S-dz6j2643]
- Apply Operating System Image runs only in Windows PE, deletes existing files on the target volume (keeping ConfigMgr control files), applies the WIM volumes to disk, and sets `OSDTargetSystemDrive` to the resulting drive letter. [DOC S-bf2nomrq, S-dz6j2643]
- Setup Windows and ConfigMgr must be added during the WinPE portion of the sequence even though it runs across the WinPE-to-full-OS transition; it downloads and stages the ConfigMgr client package, substitutes task sequence variables in the unattend.xml, and (for image-based installs) disables client autostart in the image, restarts to the deployed OS, and runs Windows mini-setup with the answer file (joining the domain if Apply Network Settings supplied one). [DOC S-nmfqbv57]
- Run Command Line and Run PowerShell Script fail if they specify a run-as account while executing in Windows PE, because WinPE cannot join a domain; the failure is recorded in smsts.log. [DOC S-dz6j2643]
- Pre-provision BitLocker (Windows PE only) encrypts used space on a drive before the OS installs and requires a supported, enabled TPM; by default it skips devices without a functional TPM (logs a warning to smsts.log and status message 11912) unless that option is cleared. Key-management options (recovery key location, protector type) are applied afterward by the full-OS-only Enable BitLocker step, which requires the TPM in Enabled/Activated/Ownership-Allowed state for TPM-based protectors. [DOC S-dz6j2643]
- Pre-provision BitLocker's disk encryption mode accepts AES_128, AES_256, XTS_AES256 or XTS_AES128; an unsupported algorithm on the running OS falls back to the OS default and logs status message 11911. Managed with `Get/New/Remove/Set-CMTSStepOfflineEnableBitLocker`. [DOC S-dz6j2643]
- Task sequence conditions on a step or group can test file/folder properties, OS version/architecture, a WMI query, a registry value, installed software, or a task sequence variable (Exists, Not exists, Equals, Not equals, greater/less than[-or-equals], Like/Not like with `*`/`?` wildcards, "Not like" from version 2103); conditions can be grouped as any/all/none. [DOC S-nmfqbv57]

### Boot images, WinPE and PXE
- A boot image is a WinPE image built from a supported Windows ADK release; the site auto-generates default x86 and x64 boot images under `\\<SiteServer>\SMS_<sitecode>\osd\boot\` and regenerates them when the ADK is upgraded and Configuration Manager is updated via updates and servicing; custom boot images are left unmodified. [DOC S-qethz2s6]
- Only a boot image based on the WinPE version from the site's supported Windows ADK can be customized from the console; a boot image on a different WinPE version must be customized externally with DISM, then imported. [DOC S-qethz2s6, S-ruy2unms]
- ADK 10.1.25398.1 (updated September 2023) WinPE boot images are **not supported** with Configuration Manager: VBScript doesn't work in WinPE, the Pre-provision BitLocker task fails, and UFS-storage devices (e.g. Surface Go 4) don't work; use ADK 10.1.26100.x (May/Dec 2024) or newer instead. [DOC S-ruy2unms]
- The last Windows ADK release that supports 32-bit WinPE is the WinPE add-on for Windows 10, version 2004 (10.1.19041); later WinPE add-ons for Windows 11/Server 2022 drop 32-bit WinPE support, though Configuration Manager still supports using an older 32-bit boot image (uncustomizable from the console). [DOC S-ruy2unms]
- A PXE-enabled distribution point can use Windows Deployment Services (WDS, installed automatically when PXE is enabled) or the built-in **PXE responder without Windows Deployment Service**, which also supports IPv6 and can share a server with DHCP; enabling it suspends WDS on that DP. [DOC S-6pxhq347]
- WDS and DHCP on the same server both default to UDP port 67; either move one service or reconfigure WDS's listening port. Required PXE-related ports: 67 (DHCP), 69 (TFTP), 4011 (PXE). [DOC S-6pxhq347]
- Option 82 during the PXE DHCP handshake is supported only with the PXE responder without WDS; Configuration Manager does not support option 82 with WDS. [DOC S-jjjidz73]
- Using DHCP options to steer PXE requests across subnets is not supported by Microsoft; the supported method is IP helpers configured on routers. [DOC S-jjjidz73]
- When the PXE responder without WDS shares a server with DHCP, set `HKLM\Software\Microsoft\SMS\DP\DoNotListenOnDhcpPort` (DWORD) to `1`, set DHCP option 60 to `PXEClient`, and restart the SCCMPXE and DHCP services. [DOC S-jjjidz73]

### Task sequence variables
- Variable kinds: built-in (initialized by the engine before steps run, available for the whole run), action (initialized per step, removed from the environment after the step completes), custom (user-defined), read-only (name begins with `_`; can be read but never set by a step), and array (e.g. Apply Network Settings, Format and Partition Disk use per-object array elements). [DOC S-nmfqbv57]
- Custom variable names: letters, digits, `_` and `-` only; 1-256 characters; must start with a letter; cannot start with `_` (reserved for read-only variables); not case-sensitive; no leading/trailing spaces. [DOC S-nmfqbv57]
- The total task sequence environment is limited to 8 KB, which caps the practical number/size of variables. [DOC S-nmfqbv57]
- A single variable value is limited to 4,000 characters; read-only variables (`_`-prefixed) cannot be changed by a step. [DOC S-nmfqbv57]
- Precedence when the same variable is set multiple ways: collection variables evaluate first, device (per-computer) variables override the same variable set on a collection, and any variable set by a method during the task sequence run overrides both collection and device variables. [DOC S-nmfqbv57]
- A device supports at most 1,000 assigned (per-device) task sequence variables; per-device and per-collection variables can be hidden from the console, the log and the debugger with "Do not display this value" / "Do not display this value in the Configuration Manager console" (the value still works at run time). [DOC S-nmfqbv57]
- If a Run Command Line step's command line embeds a variable, smsts.log logs the full expanded command line (including the value); set `OSDDoNotLogCommand` to `TRUE` to suppress logging a sensitive command line. [DOC S-nmfqbv57]
- Ways to set a variable: Set Task Sequence Variable step, Set Dynamic Variables step, Run PowerShell Script step ("Output to task sequence variable"), collection/device variables, the `Microsoft.SMS.TSEnvironment` COM object, a prestart command (media/PXE only), the Task Sequence Wizard, and the Task Sequence Media Wizard. Deleting a variable means setting its value to an empty string. [DOC S-nmfqbv57]
- Variable syntax in a step field is `%varname%` (e.g. `cmd.exe /c echo %_SMSTSMachineName% > C:\File.txt`); the same `%varname%` form is used in a Windows setup answer file, replaced by the Setup Windows and ConfigMgr step (embedded task sequence variables cannot be used in numeric-only unattend.xml fields). [DOC S-nmfqbv57]
- `OSDComputerName` defaults to `%_SMSTSMachineName%` and applies to the Apply Windows Settings step; `_SMSTSMachineName` itself only stores/reports the computer name used for status messages -- renaming the OS requires `OSDComputerName`. [DOC S-lydse5ww]
- Full built-in/read-only, action and custom variable reference (45+ entries relevant to OSD, including `_SMSTSLogPath`, `_SMSTSInWinPE`, `_SMSTSLaunchMode`, `OSDDiskIndex`, `SMSTSPersistContent` vs `SMSTSPreserveContent`, USMT capture/restore variables) is in `mecm/task-sequence-variables.csv`, one row per variable with read-only/settable, type, default and source. [DOC S-lydse5ww]

### smsts.log locations and logging
- `Smsts.log` (client, OS deployment) "Records task sequence activities"; use it with `TSDTHandler.log` and `AppEnforce.log` when troubleshooting the Install Application task sequence step. [DOC S212 mecm/log-files.csv:393, mecm/log-files.csv:260]
- smsts.log's location depends on the task sequence phase: (1) in Windows PE before Format and Partition Disk: `X:\Windows\temp\smstslog\smsts.log` (X = the WinPE RAM drive); (2) in WinPE after Format and Partition Disk: `X:\smstslog\smsts.log`, copied to `C:\_SMSTaskSequence\Logs\smstslog\smsts.log` once the drive is ready; (3) in the new Windows OS before the ConfigMgr client installs: `C:\_SMSTaskSequence\Logs\smstslog\smsts.log`; (4) in Windows after the client installs: `C:\Windows\CCM\Logs\smstslog\smsts.log`; (5) after the task sequence completes: `C:\Windows\CCM\Logs\smsts.log`. [DOC S-kwn2lclu]
- The read-only variable `_SMSTSLogPath` always contains the current smsts.log directory, so a script can locate it without hardcoding the phase-dependent path. [DOC S-kwn2lclu, S-lydse5ww]
- Default client, server, management point, console and IIS log root locations (for cross-reference while triaging OSD failures): client `C:\Windows\CCM\logs`, server `C:\Program Files\Microsoft Configuration Manager\Logs`, management point `C:\SMS_CCM\Logs`, console `C:\Program Files (x86)\Microsoft Endpoint Manager\AdminConsole\AdminUILog`, IIS `C:\inetpub\logs\logfiles\w3svc1`. [DOC S-kwn2lclu]
- A common failure-recovery pattern: on a group with "Continue on error" set, add an error-handler group after it, condition it on `_SMSTSLastActionSucceeded = false`, and in WinPE copy the log with `smsswd.exe /run: cmd /c copy x:\windows\temp\smsts.log \\<server>\<share>\%_SMSTSClientGuid%-smsts.log` (condition `_SMSTSInWinPE` true) or, in the full OS, `copy %windir%\system32\ccm\logs\smsts.log \\server\share\%_SMSTSClientGuid%-smsts.log` (condition `_SMSTSInWinPE` false). [DOC S-xigzahvp]

## Reference
- `mecm/application-model.md` documents deployment types, detection methods and Install Application return-code handling that the Install Application task sequence step and `TSDTHandler.log` rely on; back-linked from there.
- `mecm/software-updates.md` covers the Install Software Updates step's server-side pipeline (SUP sync, ADRs, WSUS maintenance) that supplies the updates this step installs, and the client log files (`WUAHandler.log`, `UpdatesDeployment.log`, etc.) for the software-update side of a task sequence run.
- `windows/bitlocker.md` covers BitLocker management policy and recovery-key handling after deployment; this article covers only the OSD-time Pre-provision BitLocker / Enable BitLocker task sequence steps.
- `autopilot/device-preparation.md` covers Autopilot device preparation (Entra-join, no on-prem task sequence); cross-linked here because it is the alternative, ConfigMgr-free provisioning path for the same "get a new device to a usable Windows state" goal.
- `mecm/log-files.csv` has the full log reference cited by row above (`Smsts.log`, `TSDTHandler.log`, `smstsvc.log`) rather than duplicated here.
- The full list of common/specific step properties for every step type (success codes, continue-on-error, per-step settings) and the complete PowerShell cmdlet set per step (`Get/New/Remove/Set-CMTSStep*`) were reviewed only for the steps named above. [UNK: not exhaustively reviewed for every step type]
- Windows 11 in-place upgrade task sequence specifics (SetupCompletePause timing variable, `_SMSTSOSUpgradeActionReturnCode`) were found in the variable reference but not cross-checked against a dedicated in-place-upgrade walkthrough page. [UNK]

## Examples
Read the log path and set a custom variable from a `Run PowerShell Script` step using the `Microsoft.SMS.TSEnvironment` COM object:
```powershell
# Create an object to access the task sequence environment
$tsenv = New-Object -ComObject Microsoft.SMS.TSEnvironment

# Query an existing variable
$LogPath = $tsenv.Value("_SMSTSLogPath")

# Or convert every current variable into a PowerShell variable
$tsenv.GetVariables() | ForEach-Object { Set-Variable -Name "$_" -Value "$($tsenv.Value($_))" }

# Write to the current smsts.log directory
Write-Output "Hello world!" | Out-File -FilePath "$LogPath\mylog.log" -Encoding Default -Append

# Set a custom variable
$tsenv.Value("startTime") = (Get-Date -Format HH:mm:ss) + ".000+000"
```
[DOC S-nmfqbv57]

Set `OSDComputerName` from a placeholder naming scheme (e.g. a `Run PowerShell Script` step earlier in the sequence, output variable disabled since this writes directly):
```powershell
$tsenv = New-Object -ComObject Microsoft.SMS.TSEnvironment

# Placeholder naming scheme: PL-LT-00123 (asset-tag-based laptop name)
$tsenv.Value("OSDComputerName") = "PL-LT-00123"
```
Or, without a script, add a **Set Task Sequence Variable** step: Task Sequence Variable `OSDComputerName`, Value `PL-LT-00123`. [DOC S-lydse5ww, S-nmfqbv57]

Copy smsts.log to a share on failure (error-handler group, `_SMSTSLastActionSucceeded` = `false`), Windows PE branch:
```cmd
smsswd.exe /run: cmd /c copy x:\windows\temp\smsts.log \\PL-SRV-0042\TSLogs\%_SMSTSClientGuid%-smsts.log
```
[DOC S-xigzahvp]
