---
topic: mecm/compliance-script-ci
priority: P0
applies_to: "ConfigMgr current branch 2603 (docs at MicrosoftDocs/memdocs 4b5429df)"
retrieved_utc: 2026-09-26
sources: [S-mmydokhp, S-pm6pjuef, S-nejxr76b, S-5lqbi3py, S-j2tke6bb, S-7s2aa2cm, S1520]
status: partial
---

## Summary
Script settings in a custom "Windows Desktops and Servers" configuration item (CI) run a discovery script whose returned
value is compared by compliance rules; an optional remediation script runs only for value rules with the Equals operator.
Scripts may be PowerShell (started with `-NoProfile`), VBScript or JScript, run as SYSTEM unless "logged on user credentials"
is set. Since 2207 a client setting sets the script execution timeout (60-600 s, default 60 s). No documented size limit for
a CI script's output was found. The full list of script data types and the 32-bit/64-bit host option are not documented.

## Facts
- A script setting's discovery script "is used to find the value"; the value returned by the script is used to assess compliance (VBScript example: `WScript.Echo Result`). [DOC S-mmydokhp]
- Discovery and remediation scripts can be Windows PowerShell, VBScript or JScript. [DOC S-mmydokhp]
- When PowerShell runs a discovery or remediation script, the client calls PowerShell with `-NoProfile`. [DOC S-mmydokhp]
- Remediation script is optional and remediates noncompliant setting values. [DOC S-mmydokhp]
- To report a remediation failure correctly, scripts must throw exceptions rather than return a nonzero exit code. [DOC S-mmydokhp]
- "Run scripts by using the logged on user credentials": when enabled, the script runs with the signed-in user's credentials. [DOC S-mmydokhp]
- Without that option the script runs in the client's default context; the doc does not name the account. [UNK]
- A signed PowerShell script must be loaded with **Open**; copy/paste of a signed script is not supported. [DOC S-mmydokhp]
- Setting name and description: max 256 characters each. [DOC S-mmydokhp]
- Data type is chosen per setting ("format in which the condition returns the data"); the list is not shown for all setting types; Floating point supports only three digits after the decimal point. [DOC S-mmydokhp]
- The full enumeration of data types available for a script setting is not listed in the docs. [UNK]
- A global-condition script returning multiple values must put them on a single line separated by semicolons; values on separate lines make evaluation fail. [DOC S-7s2aa2cm]
- Whether the same multi-value rule applies to CI script settings is not stated in the CI doc. [UNK]
- Before a setting is evaluated it must have at least one compliance rule; WMI, registry and script settings can remediate. [DOC S-mmydokhp]
- Rule types: **Value** (compare returned value with a specified value) and **Existential** (exists / must not exist / occurs N times). [DOC S-mmydokhp]
- "Remediate noncompliant rules when supported" works for Registry value, Script (runs the remediation script) and WQL query rules, and only when the rule operator is **Equals**. [DOC S-mmydokhp]
- "Report noncompliance if this setting instance is not found" makes a missing setting report noncompliant. [DOC S-mmydokhp]
- Noncompliance severity: None, Information, Warning, Critical, Critical with event (Critical plus a Windows Application event log entry). [DOC S-mmydokhp]
- "Track remediation history when supported" (version 2002+) makes each remediation generate a state message stored in the site database; exposed through view `v_CIRemediationHistory` (`RemediationDate` UTC, `ResourceID`). [DOC S-mmydokhp]
- Script Execution Timeout (seconds) is a client setting in the **Compliance settings** group, introduced in 2207; range 60-600 s; the default is 60 s; described as giving "more flexibility for configuration items when you need to run scripts that may exceed the default of 60 seconds". [DOC S-pm6pjuef,S-nejxr76b]
- The CI doc links this timeout to compliance settings scripts ("Starting in 2207, you can define a Script Execution Timeout (seconds) when configuring client settings for compliance settings"). [DOC S-mmydokhp]
- Whether this timeout also applies to application detection scripts or global-condition scripts is not stated. [UNK]
- Client setting **PowerShell execution policy** (Computer agent) governs PowerShell scripts used "for detection in configuration items for compliance settings": Bypass, Restricted, All Signed; default **All Signed**. [DOC S-pm6pjuef]
- Unsigned-script failures under that setting show error 0x87D00327 "Script is not signed" (Discovery Error), or 0x87D00320 "The script host has not been installed yet"; `DcmWmiProvider.log` records "Script is not signed (Error: 87D00327; Source: CCM)". [DOC S-pm6pjuef]
- The CI wizard for a script setting has no documented 32-bit / 64-bit host option; the 64-bit options documented are for File system, Registry key/value and XPath settings. [DER S-mmydokhp: option lists per setting type, script section has none]
- Application detection scripts (a different feature) have "Run script as 32-bit process on 64-bit clients" and a 32 KB max script size. [DOC S-j2tke6bb]
- Size limit on the output (discovered value) of a CI script: not documented. Run Scripts (a different feature) truncates output to 4 KB. [UNK] [DOC S1520]
- File system settings: UNC paths unsupported; `%USERPROFILE%` searches all profiles; inaccessible path or file in use gives a discovery error. [DOC S-mmydokhp]
- An invalid XPath query evaluates noncompliant; an encrypted XML file yields no results and no error. [DOC S-mmydokhp]
- SQL query settings run only read-only SQL on a local instance. [DOC S-mmydokhp]

## Reference
| Item | Value | Tag |
|---|---|---|
| Script languages | PowerShell, VBScript, JScript | [DOC S-mmydokhp] |
| PowerShell launch | `-NoProfile` | [DOC S-mmydokhp] |
| Remediation allowed when | Value rule, operator Equals, setting type Registry value / Script / WQL | [DOC S-mmydokhp] |
| Failure signalling from remediation | throw exception (not nonzero exit code) | [DOC S-mmydokhp] |
| Script Execution Timeout | 60-600 s, default 60 s, client settings > Compliance settings, 2207+ | [DOC S-pm6pjuef] |
| PowerShell execution policy default | All Signed | [DOC S-pm6pjuef] |
| Relevant client logs | DcmWmiProvider.log, DCMAgent.log, CIAgent.log, DCMReporting.log, CITaskManager.log | [DOC S-5lqbi3py] |

Learn URL (derived from repo path): https://learn.microsoft.com/intune/configmgr/compliance/deploy-use/create-custom-configuration-items-for-windows-desktop-and-server-computers-managed-with-the-client

## Examples
- SNIPPET: Discovery script (PowerShell, String data type) on `PL-LT-00123`, output compared by a Value rule "Equals Enabled"; context: ConfigMgr current branch 2603, PowerShell run with `-NoProfile`; checked: no [DOC S-mmydokhp: a script setting's discovery script "is used to find the value"; PowerShell scripts run with `-NoProfile`]
```powershell
$v = (Get-ItemProperty 'HKLM:\SOFTWARE\Contoso\Agent' -Name State -ErrorAction Stop).State
Write-Output $v
```
Remediation script: sets the value; on failure uses `throw "..."` rather than `exit 1` (per S-mmydokhp).
