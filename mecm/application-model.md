---
topic: mecm/application-model
priority: P0
applies_to: "ConfigMgr current branch 2603 (memdocs 4b5429df)"
retrieved_utc: 2026-09-23
sources: [S227, S228, S229, S204]
status: complete
---

## Summary
Deployment types carry detection methods: rule clauses (File System, Registry, Windows Installer product code; groupable
with And/Or) or a custom script (PowerShell/VBScript/JScript, max 32 KB). File rules can test Version, Date Modified,
Date Created or Size. Script detection: exit 0 + STDOUT non-empty = Installed; exit 0 + empty STDOUT and STDERR = Not
installed; any non-zero exit or exit 0 with only STDERR = Unknown. Supersedence replaces a deployment type (optional
uninstall); keep chains at most five deep. Required deployments install at the deadline.

## Facts
- Detection method options: rule clauses or custom script. [DOC S227]
- File System clause: file or folder, local path (no network share), name; option "associated with a 32-bit application on 64-bit systems" checks 32-bit locations first then 64-bit. [DOC S227]
- A clause can require existence or satisfy a rule on properties Date Modified, Date Created, Version or Size (file version detection). [DOC S227]
- Registry clause: hive, key, optional value (or (Default)); a value requires a Data Type; 32-bit-on-64-bit option. [DOC S227]
- Windows Installer clause: MSI product code. [DOC S227]
- Three or more clauses can be grouped (parentheses) with And/Or connectors. [DOC S227]
- Script detection: PowerShell (`-NoProfile`), VBScript or JScript; "Run script as 32-bit process on 64-bit clients" option; max script size 32 KB. [DOC S227]
- Script detection results: non-zero exit = Unknown; exit 0 with empty STDOUT and empty STDERR = Not installed; exit 0, empty STDOUT, non-empty STDERR = Unknown (failure); exit 0 with STDOUT non-empty = Installed (regardless of STDERR). [DOC S227]
- Dependency chains: max five. [DOC S227]
- Return code value range -2147483648..2147483647; code types Success (no reboot), Failure (no reboot), Hard Reboot, Soft Reboot, Fast Retry (retry every 2 hours, 10 times). [DOC S227]
- Default MSI return codes: 0 and 1707 success, 3010 soft reboot, 1641 hard reboot, 1618 fast retry. [DOC S227]
- Supersedence: specify a new deployment type replacing the superseded one; optionally **Uninstall** the superseded one first; default doesn't uninstall. [DOC S228]
- "It's best to limit supersedence chains to five levels deep at a maximum." [DOC S228]
- With Uninstall, a DT deployed to a device collection can't be superseded by one deployed to a user collection (and vice versa). [DOC S228]
- Upgrade same app ID: don't select Uninstall; replace with different app ID: select Uninstall. [DOC S228]
- PowerShell: Get-CMDeploymentTypeSupersedence, Set-CMApplicationSupersedence. [DOC S228]
- Required purpose: client installs per schedule; user may install early from Software Center; Uninstall action forces Required. [DOC S229]
- Deployment option "Automatically upgrade any superseded versions of this application". [DOC S229]
- Implicit uninstall (2107+): device-targeted Required deployments only. [DOC S229]
- Installation deadline default: as soon as possible. [DOC S229]
- Grace period (client setting) with "Delay enforcement ... up to the grace period": 1-120 hours per deploy doc. [DOC S229]
- Deployment requirement re-evaluation: default every 7 days. [DOC S204]

## Reference
| Script detection: exit code | STDOUT | STDERR | State |
|---|---|---|---|
| 0 | empty | empty | Not installed |
| 0 | empty | not empty | Unknown |
| 0 | not empty | any | Installed |
| non-zero | any | any | Unknown |

## Examples
File version clause: `%ProgramFiles%\Contoso\agent.exe` Version Greater than or equal to `5.2.0.0` on `PL-LT-00123`.
