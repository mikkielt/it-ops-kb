---
topic: mecm/run-scripts
priority: P0
applies_to: "ConfigMgr current branch 2603"
retrieved_utc: 2026-09-27
sources: [S-igpzfey7, S-o6f7ibqo, S-sxtmngif, S-e5qqwdcj, S1520, S-kln2au6a, S-aaryifxi, S-hmjlvsck, S335, S336, S337, S-5v5lco6w, S350, S-p2yatbfh]
status: complete
---

# Run Scripts

## Summary
Run Scripts runs approved PowerShell scripts on a device or a collection, as SYSTEM, over the client notification fast channel. The run times out after 1 hour.
Script output is truncated to 4 KB. A script takes at most 10 parameters, of type string, integer or list, and parameter values cannot contain a single quote.
By default an author cannot approve their own script.
`Invoke-CMScript -ScriptParameter` (2010+) is the documented way to pass parameters. No AdminService `v1.0` route for running a script is documented. Script size limits and a script-signing requirement are not documented.

## Facts
- Only PowerShell is supported. Parameter types are integer, string and list. [DOC S1520]
- A script can have up to 10 parameters. Each parameter can have validation: minimum length, maximum length, a .NET regex and a custom error. [DOC S1520]
- Parameter values cannot contain a single quote (known issue). Default values in the script are shown in the UI, but ConfigMgr does not apply them at run time. [DOC S1520]
- Clients need PowerShell 3.0 or later and client version 1706 or later. [DOC S1520]
- Scripts must be approved before they run. Editing or copying a script resets its approval. [DOC S1520]
- By default users cannot approve scripts they authored. The hierarchy setting "Script authors require additional script approver" can be cleared, and Microsoft recommends doing so only in a lab. [DOC S1520]
- Execution is "launched quickly through a high priority system that times out in one hour". Offline targets must be re-run. [DOC S1520]
- Scheduled runs (2309+) are in UTC, and at most 25 scheduled scripts are processed every 5 minutes. [DOC S1520]
- Scripts run as the SYSTEM/computer account, which has limited network access. [DOC S1520]
- Output is returned as JSON via `ConvertTo-Json` where possible and is truncated to 4 KB. [DOC S1520]
- Client output under 80 KB uses the fast channel, and larger output uses state messages. This is stated for script and query output from 1810 clients. [DOC S-sxtmngif]
- No size limit on the script body is documented: re-read 2026-09-27, the page's Limitations section names only the language (PowerShell) and parameter types, and the only size stated is the 4 KB output truncation. [DER S1520: absence in Limitations]
- ConfigMgr documents no signing requirement for Run Scripts. The security guidance recommends "Sign your scripts" after vetting, not storing secrets, validating parameters with regex, and using predefined parameters. [DOC S-kln2au6a]
- Microsoft warns that parameters open a PowerShell injection surface. [DOC S1520]
- Security software should exclude `%windir%\CCM\ScriptStore`. [DOC S1520]
- Script status data is removed by the "Delete Aged Client Operations" maintenance task or when the script is deleted. [DOC S1520]
- Client operation Type 135 is probably the Run Script operation: the CMPivot troubleshooting page shows smsprov.log logging 'Type parameter is 135' next to 'ran script <CMPivot script GUID>' (1902), and 'initiated client operation 135' for CMPivot in 1810 and earlier; no official page names 135 as Run Script. [DER S-e5qqwdcj: 135 appears only alongside a CMPivot run-as-script audit line]
- Logs: client Scripts.log and CcmMessaging.log, MP MP_RelayMsgMgr.log, site server SMS_Message_Processing_Engine.log. [DOC S1520]
- `Invoke-CMScript` targets a script with `-ScriptGuid` or `-InputObject`, and a device or collection with `-Collection*` or `-Device`. `-ScriptParameter <Hashtable>` applies to 2010 and later. `-ScheduleTime <DateTime>` sets a UTC schedule. [DOC S335]
- `New-CMScript` takes `-ScriptName` with `-ScriptText` or `-ScriptFile` (.ps1). `Approve-CMScript` takes `-InputObject` and `-Comment`. [DOC S336,S337]
- Run Script is a permission on the Collection object; the built-in roles holding it are Full Administrator, Infrastructure Administrator and Operations Administrator. [DOC S-hmjlvsck]
- From the Intune admin center (tenant attach, 2207+ with Intune RBAC), the Intune permission "Cloud attached devices\Run script" controls running scripts on tenant-attached devices. [DOC S-5v5lco6w]
- Scripts that have parameters are not shown in the Intune admin center and cannot be run from there. [DOC S-aaryifxi]
- Run Script over the AdminService: the AdminService overview lists console-run PowerShell scripts (Run Scripts) as a custom caller of the AdminService; neither it nor the usage page documents a route to start one. [DOC S-o6f7ibqo, S-igpzfey7]
- No official source documents a `v1.0` Run Script action or its parameter format: a Learn search (2026-09-27) for `AdminService.RunScript`/`ScriptResult` returns only `Invoke-CMScript`, and the usage page lists only CMPivot and other v1.0 routes. Use `Invoke-CMScript` or the console for a supported path. [DER S-igpzfey7, S335: absence on the usage page; the cmdlet is the documented path]
- A community sample posts a body with only `ScriptGuid` to `v1.0/Device(<id>)/AdminService.RunScript`, then polls `AdminService.ScriptResult(OperationId=...)` on the same device. It was not verified. [COMMUNITY S350]
- Folders for scripts exist from 2403, and the Full Administrator and Operations Administrator roles can manage them. [DOC S-p2yatbfh]

## Reference
| Role (custom, not built in) | Collection: Run Script | Site: Read | SMS Scripts |
|---|---|---|---|
| Script Runners | Yes | Yes | Read |
| Script Authors | No | Yes | Create, Read, Delete, Modify |
| Script Approvers | No | Yes | Read, Approve, Modify |
Source: S1520. Built-in roles with Run Script: Full, Infrastructure and Operations Administrator (S-hmjlvsck).

## Examples
- SNIPPET: run an approved script with a hashtable parameter against one device; context: ConfigMgr current branch 2603, client 1706+/PowerShell 3.0+, `-ScriptParameter` requires 2010+; checked: no [DOC S335: `Invoke-CMScript` `-ScriptGuid`/`-Device`/`-ScriptParameter` parameters]
```powershell
$p = @{ ServiceName = 'Spooler' }
Invoke-CMScript -ScriptGuid '00000000-0000-0000-0000-000000000001' -Device (Get-CMDevice -Name 'PL-LT-00123') -ScriptParameter $p
```
