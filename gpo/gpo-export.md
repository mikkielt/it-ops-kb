---
topic: gpo/gpo-export
priority: P2
applies_to: "GroupPolicy PowerShell module (RSAT/GPMC), windowsserver2025-ps reference"
retrieved_utc: 2026-09-23
sources: [S920, S921, S922, S923]
status: complete
---

# Exporting GPOs as XML: Get-GPOReport and Backup-GPO

## Summary
`Get-GPOReport -ReportType Xml` writes an XML (or HTML) report of one GPO (by `-Guid`/`-Name`) or all GPOs (`-All`) in a domain,
to a file (`-Path`) or to the console. `Backup-GPO` writes a restorable backup of one or all GPOs into an existing directory and
returns a `GpoBackup` object. Both come from the GroupPolicy module, available on Windows Server and on Windows client with RSAT.
The reference pages carry ms.date 12/20/2016 in all docsets (2016/2019/2022/2025).

## Facts
- The GroupPolicy module cmdlets are for Windows Server and for Windows client with RSAT installed (RSAT includes GPMC and the cmdlets). [DOC S922]
- `Get-GPOReport` generates an XML or HTML report of properties and settings for one GPO or all GPOs in a domain: details, links, security filtering, WMI filtering, delegation, computer and user configuration. [DOC S920]
- Parameter sets: `ByGUID` (default, `-Guid`, alias `Id`), `ByName` (`-Name`, alias `DisplayName`), `ReportAll` (`-All`). `-ReportType` is required, values `Xml` or `Html` (case-insensitive). [DOC S920]
- Without `-Path` the report goes to the display; with `-Path` it is written to the file. [DOC S920]
- `-Server` (alias `DC`) selects the domain controller; if omitted the PDC emulator is contacted. [DOC S920]
- `-Domain` (alias `DomainName`) must be an FQDN; default is the domain of the running user (computer's domain for startup/shutdown scripts); a different domain requires a trust. [DOC S920]
- `-Name` display names are not guaranteed unique; a duplicate name causes an error; use `-Guid` to be unambiguous. [DOC S920]
- Piped GPO collections: the first GPO's DomainName sets the domain; GPOs from other domains give non-terminating errors. [DOC S920]
- The OUTPUTS section of `Get-GPOReport` says "None", while the description says the report is printed to the display when no `-Path` is given. [DER S920] (see conflicts)
- `Backup-GPO` backs up one GPO (`-Guid` alias `Id`, or `-Name` alias `DisplayName`) or all GPOs (`-All`) to a backup directory; the directory must already exist. [DOC S921]
- `Backup-GPO -Path` (alias `BackupLocation`) is required and may be local or UNC; `-Comment` is stored in the backup; supports `-WhatIf`/`-Confirm`. [DOC S921]
- `Backup-GPO` returns `Microsoft.GroupPolicy.GpoBackup` (DisplayName, GpoId, Id = backup id, BackupDirectory, CreationTime, DomainName, Comment in the example). [DOC S921]
- The on-disk layout of a GPO backup folder is not described in the cmdlet reference. [UNK]
- `Get-GPResultantSetOfPolicy [-Computer] [-User] -ReportType <Xml|Html> -Path` writes RSoP for a user, computer or both to a file. [DOC S923]

## Reference
| Cmdlet | Required | Selection | Output [S920, S921, S923] |
|---|---|---|---|
| Get-GPOReport | `-ReportType` (+ `-Guid`/`-Name`/`-All`) | one or all GPOs | XML/HTML to file or console |
| Backup-GPO | `-Path` (+ `-Guid`/`-Name`/`-All`) | one or all GPOs | backup dir + GpoBackup object |
| Get-GPResultantSetOfPolicy | `-ReportType`, `-Path` | computer and/or user | RSoP XML/HTML file |

DSC v3 Group Policy (ADMX) adapter: see `gpo/dsc-group-policy-adapter.md` (pointer to dsc/).

## Examples
```powershell
Get-GPOReport -All -ReportType Xml -Domain corp.example.com -Server PL-SRV-0042 -Path C:\gpo\all.xml
Backup-GPO -Name "Workstation Baseline" -Path \\PL-SRV-0042\GpoBackups -Comment "release-2026.09.24.1"
```
