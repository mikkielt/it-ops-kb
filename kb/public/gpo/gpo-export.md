---
topic: gpo/gpo-export
priority: P2
applies_to: "GroupPolicy PowerShell module (RSAT/GPMC), windowsserver2025-ps reference"
retrieved_utc: 2026-10-21
sources: [S920, S921, S922, S923, S-moam7wlp, S-sxznlh57, S-mpefr5wx]
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
- A GPMC backup transfers a GPO's contents from Active Directory to the file system and includes its policy settings, its GPO ID and its ACLs; the same method is used to export GPOs. [DOC S-moam7wlp]
- No page for the GroupPolicy cmdlets or GPMC describes the on-disk layout of a `Backup-GPO` backup folder: re-read 2026-09-27, the Backup-GPO reference and the GPMC Backup method give only the directory and the returned backup object. Treat the folder as opaque and restore with `Restore-GPO` / `Import-GPO` rather than parsing it. [DER S921, S-moam7wlp: absence on both pages]
- The Microsoft Entra Domain Services GPO backup feature (public preview) keeps backups on the PDC in the hidden share `GPOBackupsShare$`, path `GPO\Backups`, as timestamp folders named `MMddyyyyHHmm` that hold one `{GPO-GUID}` folder per GPO; the page's layout recap lists `backup.xml` (metadata, if present), `GPO.tmf`, `Gpt.ini`, `Machine` and `User`, and says the exact file set may vary with the provider implementation. [DOC S-sxznlh57]
- An archived GPO in the Advanced Group Policy Management (AGPM) archive holds `gpreport.xml` (settings, GPO name and times, security descriptor), `Backup.xml` (security principals, the GPO's settings, security descriptor, options, user and machine version numbers, CSE GUIDs) and a hidden `bkupInfo.xml`, an excerpt of the archive's hidden `Manifest.xml` for that GPO; the post says AGPM's archive copy closely resembles a standard GPMC backup and that GPMC logs it as a backup. [DOC S-mpefr5wx]
- Caveat: the managed-domain layout and the AGPM archive layout are not `Backup-GPO` output (one is a service feature of Entra Domain Services, the other the AGPM archive of a 2011 post on Windows Server 2008 R2), so the files of a `Backup-GPO` backup folder stay unconfirmed until a listing of one is read from a lab domain. [DER S-sxznlh57, S-mpefr5wx, S921: neither page describes Backup-GPO output]
- `Get-GPResultantSetOfPolicy [-Computer] [-User] -ReportType <Xml|Html> -Path` writes RSoP for a user, computer or both to a file. [DOC S923]

## Reference
| Cmdlet | Required | Selection | Output [S920, S921, S923] |
|---|---|---|---|
| Get-GPOReport | `-ReportType` (+ `-Guid`/`-Name`/`-All`) | one or all GPOs | XML/HTML to file or console |
| Backup-GPO | `-Path` (+ `-Guid`/`-Name`/`-All`) | one or all GPOs | backup dir + GpoBackup object |
| Get-GPResultantSetOfPolicy | `-ReportType`, `-Path` | computer and/or user | RSoP XML/HTML file |

DSC v3 Group Policy (ADMX) adapter: see `gpo/dsc-group-policy-adapter.md` (pointer to dsc/).

## Examples
- SNIPPET: export all GPOs as XML and back up one GPO by name; context: GroupPolicy module, RSAT or Windows Server; checked: no [DOC S920, S921: Get-GPOReport `-All`/`-ReportType`/`-Domain`/`-Server`/`-Path` and Backup-GPO `-Name`/`-Path`/`-Comment` parameters]
```powershell
Get-GPOReport -All -ReportType Xml -Domain corp.example.com -Server PL-SRV-0042 -Path C:\gpo\all.xml
Backup-GPO -Name "Workstation Baseline" -Path \\PL-SRV-0042\GpoBackups -Comment "release-2026.09.24.1"
```
