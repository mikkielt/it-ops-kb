---
topic: defender/asr-and-antivirus
priority: P2
applies_to: "Microsoft Defender Antivirus and Attack Surface Reduction (ASR) rules on Windows 10/11 and Windows Server, managed via Intune, Configuration Manager, Group Policy, MDM CSP or local PowerShell; docs retrieved 2026-09-26"
retrieved_utc: 2026-09-28
sources: [S-oc7bghb6, S-jlx5q3eb, S-tn7i36es, S-4adqmykc, S-bmoruabr, S-mxlwzhw5, S-3odg3w3u, S-tateky4b, S-kp35fytq, S-sfs6hoqq, S-f4gw3rhj, S-3ed4q5kx, S1472, S-oeh7ui3h, S-wqwf7kt5, S-pfbl6p36, S1402, S-bzyxqg37]
status: complete
files: [defender/asr-rules.csv]
---

# Attack surface reduction (ASR) rules and Defender Antivirus core settings

## Summary
Attack surface reduction (ASR) rules are a Microsoft Defender Antivirus feature (present on any Windows edition that
includes Defender AV) that blocks, audits or warns on risky behaviors (Office child processes, script obfuscation,
credential theft from LSASS, USB execution, etc.). Each rule is identified by a GUID and set to one of five modes:
`0`/Disabled, `1`/Block, `2`/Audit, `5`/Not configured, `6`/Warn (`Warn` lets the user bypass for 24 hours, and since
platform `4.18.26060` needs admin approval to unblock). Two rules (LSASS credential theft, Office code injection into
other processes) do not support Warn. Rules require Defender AV to be the active (not passive/EDR-block-mode/LPS/off)
antivirus with real-time and cloud-delivered protection on. Exclusion support varies per rule: full support (Defender
AV file/folder exclusions + global ASR exclusions + per-rule exclusions + IoC file/certificate allow) vs. limited
support (only global/per-rule exclusions and some IoCs, no plain Defender AV exclusions) — see `asr-rules.csv`.
Rules are managed centrally via Intune endpoint security policies (recommended), the Defender portal, Configuration
Manager, Group Policy, MDM Policy CSP, or locally via `Set/Add/Remove-MpPreference -AttackSurfaceReductionRules_Ids/
_Actions`. Complementary Defender AV controls covered here: cloud protection level (`CloudBlockLevel`), tamper
protection, and `Get-MpComputerStatus` device-state fields (`AMRunningMode`). The Windows 11 24H2 security baseline
enables 15 of the 19 documented ASR rules in Block mode; the baseline's exact rows and source ids are in
`security/settings-crosswalk.csv` (cited below, not duplicated here).

## Facts

### ASR rule modes, requirements, GUIDs
- ASR rule modes and their numeric/CSP codes: `0` Off/Disabled, `1` Block/Activated, `2` Audit/Audit mode, `5` Not configured (functionally same as disabled but avoids policy conflicts), `6` Warn/Warning. [DOC S-jlx5q3eb]
- Warn mode lets the end user select **Unblock** in the notification to bypass the block for 24 hours, after which they must bypass again; as of platform version `4.18.26060`, admin approval is required to use Unblock. Warn mode is not available in Configuration Manager, requires Windows 10 1809+, and requires Defender AV platform `4.18.2008.9`+ and engine `1.1.17400.5`+; on unsupported Windows versions a rule set to Warn behaves as Block (no bypass). [DOC S-jlx5q3eb]
- Two rules do not support Warn mode: **Block credential stealing from the Windows local security authority subsystem** and **Block Office applications from injecting code into other processes**. [DOC S-jlx5q3eb, S-oc7bghb6]
- ASR rules require Defender AV to be enabled and in **Active** mode: they do not function when Defender AV is Passive, Passive with EDR in block mode, Limited periodic scanning, or Off. Real-time protection must be on, and cloud-delivered protection (MAPS) is critical to rule functionality (some rules have extra cloud-protection-level requirements for EDR alerts/notifications). [DOC S-jlx5q3eb]
- Full rule details (name, Intune name, Configuration Manager name where different, GUID, advanced-hunting `ActionType` values, dependencies) and the complete GUID/category table are in `asr-rules.csv`, sourced from the ASR rules reference and overview pages. [DOC S-oc7bghb6, S-jlx5q3eb]
- Rules are grouped **Standard protection rules** (Microsoft recommends enabling in Block mode without extensive testing: vulnerable signed drivers, LSASS credential theft, WMI persistence) vs. **Other ASR rules** (recommended to test in Audit mode first). [DOC S-jlx5q3eb]
- OS/deployment-method support (Intune, Configuration Manager, MDM CSP, Group Policy) per rule, including minimum Windows 10/11 build and Windows Server version, is in `asr-rules.csv`; PowerShell and local Group Policy support all ASR rules on individual devices. [DOC S-oc7bghb6, S-tn7i36es]
- ASR rules are unavailable on Linux and macOS, even when those devices are onboarded to Defender for Endpoint. [DOC S-jlx5q3eb]
- Windows Server 2016 and Windows Server 2012 R2 need onboarding via the modern unified solution package for ASR rule support; several rules are additionally not supported when deployed via Intune to those OS versions using that package (WMI persistence, JavaScript/VBScript download-launch, ransomware protection, Webshell creation). [DOC S-oc7bghb6]
- **Block use of copied or impersonated system tools** treats executables in `%windir%\System32` and `%windir%\SysWOW64` as system tools and blocks copies/same-named files run from other locations, including Microsoft-signed copies; it also uses heuristics to flag third-party executables run from nondefault paths. [DOC S-oc7bghb6]
- **Block Webshell creation for Servers** targets Windows servers running Microsoft Exchange; if ASR is managed via Defender for Endpoint, this rule must be left `Not Configured` in Group Policy/local settings — any other GPO value can cause conflicts. [DOC S-oc7bghb6]
- **Block all Office applications from creating child processes**, **Block Office applications from injecting code into other processes**, and **Block Office communication application from creating child processes** are enforced only when Office is installed under `%ProgramFiles%` or `%ProgramFiles(x86)%` (default `C:\Program Files` / `C:\Program Files (x86)`); **Block Office applications from creating executable content** is not affected by the Office install location. [DOC S-oc7bghb6]
- **Block Office applications from injecting code into other processes** applies to Word, Excel, OneNote and PowerPoint, and requires restarting Microsoft 365 Apps for the configuration change to take effect. [DOC S-oc7bghb6]
- **Block executable files from running unless they meet a prevalence, age, or trusted list criterion**, **Block execution of potentially obfuscated scripts**, and **Use advanced protection against ransomware** each require cloud-delivered protection to be enabled to function. [DOC S-oc7bghb6]
- **Block process creations originating from PSExec and WMI commands** and **Block persistence through WMI event subscription**: if Configuration Manager manages the device, don't enable these rules via another deployment method without extensive Audit-mode testing first, because the Configuration Manager client relies heavily on WMI. [DOC S-oc7bghb6, S-jlx5q3eb]

### Exclusions
- Exclusion mechanisms for ASR rules: (1) Defender AV file/folder exclusions — not all rules honor these, but all rules honor Defender AV **process** exclusions; (2) global ASR rule exclusions (`AttackSurfaceReductionOnlyExclusions`), applying to every rule, supported by every configuration method; (3) per-rule exclusions, supported only via Group Policy (and the corresponding registry values), Intune endpoint security policies, and Defender portal endpoint security policies; (4) indicators of compromise (IoCs) for blocked files/certificates, honored by most rules. [DOC S-jlx5q3eb, S-tn7i36es]
- Per-rule Defender-AV/global/per-rule/IoC exclusion support (full vs. limited, per rule) is tabulated in `asr-rules.csv`. [DOC S-jlx5q3eb]
- PowerShell global ASR exclusion syntax: `<Add-MpPreference | Set-MpPreference | Remove-MpPreference> -AttackSurfaceReductionOnlyExclusions "<path1>","<path2>",...`; `Set-MpPreference` overwrites all existing exclusions, `Add-`/`Remove-MpPreference` modify without affecting other values; current exclusions are read with `(Get-MpPreference).AttackSurfaceReductionOnlyExclusions`. [DOC S-tn7i36es]
- Exclusion path wildcards may use system environment variables (not user environment variables) and cannot define a drive letter; `\*\` matches nested folders (e.g. `c:\Folder\*\*\Test`) and `?` matches a single unknown character (e.g. for randomly generated filenames); Configuration Manager additionally supports `*`/`?` wildcards. Exclusions apply only when the excluded application/service starts — an already-running service keeps triggering detections until restarted. [DOC S-jlx5q3eb]

### PowerShell configuration
- `<Add-MpPreference | Set-MpPreference | Remove-MpPreference> -AttackSurfaceReductionRules_Ids <Guid1>,<Guid2>,... -AttackSurfaceReductionRules_Actions <Mode1>,<Mode2>,...` sets/adds/removes one or more rules by GUID and mode in an elevated PowerShell session; `Set-MpPreference` overwrites all existing rule/mode pairs, `Add-`/`Remove-MpPreference` change only the specified rules. [DOC S-tn7i36es]
- Valid values for `-AttackSurfaceReductionRules_Actions`: `0`/`Disabled`, `1`/`Enabled` (Block), `2`/`AuditMode`/`Audit`, `5`/`NotConfigured`, `6`/`Warn`. [DOC S-tn7i36es]
- To list currently configured ASR rules and their actions: `$p = Get-MpPreference; 0..([math]::Min($p.AttackSurfaceReductionRules_Ids.Count,$p.AttackSurfaceReductionRules_Actions.Count)-1) | % {[pscustomobject]@{Id=$p.AttackSurfaceReductionRules_Ids[$_];Action=$p.AttackSurfaceReductionRules_Actions[$_]}} | Format-Table -AutoSize`. [DOC S-tn7i36es]
- If devices are managed by Intune, Configuration Manager or another enterprise management platform, that platform overwrites any conflicting PowerShell-set ASR values on startup. [DOC S-tn7i36es]
- `Set-MpPreference` also configures broader Defender AV preferences relevant to ASR/AV operation, including `-CloudBlockLevel`, `-EnableNetworkProtection`, `-EnableControlledFolderAccess`, `-PUAProtection`, `-DisableRealtimeMonitoring`, `-DisableIOAVProtection`, `-DisableScriptScanning`, `-DisableBehaviorMonitoring`, and per-threat-severity remediation actions (`-UnknownThreatDefaultAction`, `-LowThreatDefaultAction`, `-ModerateThreatDefaultAction`, `-HighThreatDefaultAction`, `-SevereThreatDefaultAction`, using values `Clean`(1)/`Quarantine`(2)/`Remove`(3)/`Allow`(6)/`UserDefined`(8)/`NoAction`(9)/`Block`(10)/`None`(11); default is `0`, apply the Security Intelligence Update's action). [DOC S-tn7i36es, S-3ed4q5kx]
- Non-remediating actions `Allow`(6) and `None`(11) cannot be configured while tamper protection is enabled, and Microsoft recommends them only for specialized environments (e.g. industrial control systems) with compensating controls. [DOC S-3ed4q5kx]

### Cloud protection level
- Cloud protection level is set with `Set-MpPreference -CloudBlockLevel <Default|High|HighPlus|ZeroTolerance>`; verify with `Get-MpPreference | Select-Object MAPSReporting, SubmitSamplesConsent, CloudBlockLevel` (`MAPSReporting` = `2`/Advanced confirms cloud protection is on). [DOC S-kp35fytq]
- MDM Policy CSP `Defender/CloudBlockLevel` values: `0` Default (not configured), `2` High (aggressively block unknowns, optimizes performance, more false positives), `4` HighPlus (aggressive blocking + extra protection measures, may affect performance), `6` ZeroTolerance (block all unknown executables); requires "Join Microsoft MAPS" enabled; maps to GPO "Select cloud protection level" (policy `MpEngine_MpCloudBlockLevel`) at `Computer Configuration > Windows Components > Microsoft Defender Antivirus > MpEngine`, registry key `Software\Policies\Microsoft\Windows Defender\MpEngine`. [DOC S-f4gw3rhj]
- Two ASR rules (Adobe Reader child process, executable content from email/webmail) and one scripted-download rule generate EDR alerts only when the cloud protection level is High plus or Zero tolerance, and generate user-notification pop-ups only at High, High plus, or Zero tolerance. [DOC S-oc7bghb6]

### Windows 11 24H2 baseline coverage (cross-reference, not duplicated)
- The MSFT Windows 11 24H2 security baseline enables `ExploitGuard_ASR_Rules` (`HKLM\Software\Policies\Microsoft\Windows Defender\Windows Defender Exploit Guard\ASR!ExploitGuard_ASR_Rules = 1`) plus 14 individual rule GUIDs at value `1` (Block) under `...\Windows Defender Exploit Guard\ASR\Rules`; the full setting rows (registry path, value name/type, baseline value, per-GUID) are in `security/settings-crosswalk.csv` lines 321-335 (line 321 is the enable switch, 322-335 the 14 rules), cited `[DOC S1472, S-oeh7ui3h]` there — not reproduced in `asr-rules.csv` to avoid duplication. [DOC S1472, S-oeh7ui3h]
- The same baseline package also sets core Defender AV registry values referenced by this article's rules (PUA protection, exclusion visibility, real-time protection sub-features, cloud block level `MpCloudBlockLevel = 2`/High, Spynet reporting, block-at-first-sight, network protection, sample submission consent) — see `security/settings-crosswalk.csv` lines 297-320 and 336, `[DOC S1472, S-oeh7ui3h]`. [DOC S1472, S-oeh7ui3h]
- The Windows 11 25H2 baseline changes three Defender settings: it adds the PSExec/WMI process-creation rule `d1e49aac-8f56-4280-b9ba-993a6d77406c` at `2` (Audit), removes *Scan packed executables* because Windows always scans packed executables, and leaves *Control whether exclusions are visible to local users* (`HKLM\Software\Policies\Microsoft\Windows Defender!HideExclusionsFromLocalUsers`) Not Configured because the parent setting for Local Admins (`HideExclusionsFromLocalAdmins`, still `1`) overrides it. Rows: `security/settings-crosswalk.csv` lines 299, 301 and 543. [DOC S1402, S-bzyxqg37]

### Device state, events, tamper protection
- `Get-MpComputerStatus | Select AMRunningMode` reports the Defender AV operating mode: `Normal` (Active — Defender AV is the primary AV and remediates in real time), `Passive`/`Passive Mode` (not primary AV, no real-time remediation; requires the device be onboarded to Defender for Endpoint), `EDR Block Mode` (Defender AV passive + EDR in block mode enabled for post-breach protection), or `SxS Passive Mode` (running alongside another AV product using limited periodic scanning). [DOC S-mxlwzhw5, S-3odg3w3u, S-tateky4b, S-pfbl6p36]
- `ForceDefenderPassiveMode` registry value forces Defender AV to passive mode on Windows Server: `HKLM\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection`, `REG_DWORD` `ForceDefenderPassiveMode`, value `1` (passive) or `0` (active); must be set before onboarding to Defender for Endpoint on Windows Server. On Windows 10+, Defender AV enters passive mode automatically when a non-Microsoft AV is installed and registered; on Windows Server 2016+/1803+/2012 R2/Azure Local 23H2+, it does not do so automatically and the registry value must be set explicitly. [DOC S-mxlwzhw5, S-tateky4b]
- Once tamper protection has switched Defender AV to Active mode, tamper protection prevents it from returning to Passive mode even if `ForceDefenderPassiveMode` is set to `1` (starting platform `4.18.2208.0`+). [DOC S-tateky4b]
- EDR in block mode requirements: Defender AV in active or passive mode, cloud-delivered protection enabled, `AMProductVersion` ≥ `4.18.2001.10`, `AMEngineVersion` ≥ `1.1.16700.2` (all via `Get-MpComputerStatus`); it honors Defender AV exclusions but not Defender for Endpoint indicators; disabling it can take up to 30 minutes to take effect. [DOC S-wqwf7kt5, S-3odg3w3u]
- ASR rule events are in Windows Event Viewer, **Applications and Services Logs > Microsoft > Windows > Windows Defender > Operational**: event ID `1121` (rule fired in Block mode), `1122` (rule fired in Audit mode), `1129` (user overrode a Warn-mode block), `5007` (ASR/AV settings changed). [DOC S-4adqmykc, S-bmoruabr]
- Advanced hunting query for ASR audit-mode detections: `DeviceEvents | where ActionType startswith "Asr" | where ActionType endswith "Audited"` (cross-link `defender/advanced-hunting.md`). [DOC S-jlx5q3eb]
- To troubleshoot a misbehaving ASR rule, switch it to Audit mode using the same tool that originally deployed it (Group Policy, Intune, or PowerShell), reproduce the action, then review event IDs 1121 (block)/1122 (audit)/1129 (warn override)/5007 (config change). [DOC S-bmoruabr]
- Tamper protection (Windows) locks: virus/threat protection enabled, real-time protection on, behavior monitoring on, antivirus/IOAV protection enabled, cloud protection enabled, signature updates, automatic remediation actions, Security Center notifications, archived-file scanning, and blocks exclusion changes and registry-based Defender AV setting changes; management-tool changes (including Group Policy) may appear to succeed but are silently blocked — use troubleshooting mode to make protected changes temporarily. [DOC S-sfs6hoqq]
- Tamper protection requirements vary by management method: via the Defender portal, Defender AV platform `4.18.2010.7`+ and engine `1.1.17600.5`+ with cloud-delivered protection on (platform `4.18.2111.5`+ auto-enables cloud protection when tamper protection is turned on); via Intune, platform `4.18.1906.3`+ and engine `1.1.15500.X`+ (co-managed devices not supported); via Configuration Manager, tenant attach must be set up. [DOC S-sfs6hoqq]

## Reference
- ASR rule GUIDs, categories, per-rule OS/deployment/exclusion/Warn support: `defender/asr-rules.csv` (this topic).
- Windows 11 24H2 baseline's ASR and core Defender AV registry rows: `security/settings-crosswalk.csv` (lines ~297-336) — cited above, not duplicated.
- Advanced hunting `DeviceEvents` ASR `ActionType` values and query practice: `defender/advanced-hunting.md` (back-linked to this topic below).
- App Control for Business (WDAC) policy rules, a separate code-integrity control layered under Smart App Control: `windows/app-control.md`.
- Smart App Control states and management: `windows/smart-app-control.md`.
- Intune Windows compliance policy's Defender/antivirus and Microsoft Defender for Endpoint risk-score settings: `intune/compliance-policies.md`.

## Examples
- SNIPPET: set ASR rule modes by GUID, add a global exclusion, and read back rule/mode pairs and Defender AV state; context: elevated Windows PowerShell, `Set-MpPreference`/`Add-MpPreference`/`Get-MpPreference`/`Get-MpComputerStatus`; checked: no [DOC S-tn7i36es, S-oc7bghb6, S-kp35fytq, S-mxlwzhw5]
```powershell
# Set two ASR rules to Block, one to Audit, on device PL-LT-00123 (elevated PowerShell)
Set-MpPreference -AttackSurfaceReductionRules_Ids `
  "d4f940ab-401b-4efc-aadc-ad5f3c50688a", `
  "5beb7efe-fd9a-4556-801d-275e5ffc04cc", `
  "01443614-cd74-433a-b99e-2ecdc07bfc25" `
  -AttackSurfaceReductionRules_Actions Enabled, Enabled, AuditMode

# Add a global ASR exclusion for a line-of-business app
Add-MpPreference -AttackSurfaceReductionOnlyExclusions "C:\Data\LOBApp\app1.exe"

# Check current ASR rule/mode pairs
$p = Get-MpPreference
0..([math]::Min($p.AttackSurfaceReductionRules_Ids.Count,$p.AttackSurfaceReductionRules_Actions.Count)-1) |
  % {[pscustomobject]@{Id=$p.AttackSurfaceReductionRules_Ids[$_];Action=$p.AttackSurfaceReductionRules_Actions[$_]}} |
  Format-Table -AutoSize

# Confirm Defender AV mode and cloud protection level
Get-MpComputerStatus | Select-Object AMRunningMode
Get-MpPreference | Select-Object MAPSReporting, SubmitSamplesConsent, CloudBlockLevel
```
