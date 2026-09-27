---
topic: gpo/admx-central-store
priority: P1
applies_to: "Group Policy Central Store, Windows Server domain controllers, Windows 10/11 clients (incl. 24H2/25H2)"
retrieved_utc: 2026-09-26
sources: [S-iymw4lcl, S-z4lluk64, S-xtwd545o, S-2lf5j2iv, S-6glsfens, S-gvgapsup]
status: complete
---

# Group Policy Central Store for Administrative Templates (ADMX/ADML)

## Summary
- The Central Store is a `PolicyDefinitions` folder in SYSVOL on a domain controller that Group Policy tools check by default and replicate to every DC in the domain; it holds `.admx` (language-neutral) and `.adml` (language-specific) files instead of the old per-GPO `.adm` files. [DOC S-iymw4lcl]
- Update it with a new versioned folder (e.g. `PolicyDefinitions-24H2`), not by overwriting the live one in place, then swap names once validated. [DOC S-iymw4lcl]
- Use the downloaded ADMX packages only to populate the Central Store: the article states that replacing files in `C:\Windows\PolicyDefinitions` isn't supported; a client's `C:\Windows\PolicyDefinitions` is named only as a source folder to copy from. [DOC S-iymw4lcl]
- Third-party and Microsoft application ADMX (LAPS, WinGet, Microsoft Edge, and similarly Office) are not part of the in-box template set and must be copied into the Central Store manually; see `windows/laps.md` and `windows/winget.md` for their specific file names and steps.
- Both documented Central Store errors follow updates that put newer files next to older ones: the "already defined as the target namespace" error after overwriting the store with Windows 10 templates, and the missing `Win7Only` resource error when a 1803 `SearchOCR.adml` meets an older `SearchOCR.admx`; the Central Store article says a pristine folder built from a base OS release avoids both. [DOC S-iymw4lcl, S-z4lluk64]

## Facts
- To create the Central Store, make a folder named `PolicyDefinitions` under `\\<domain>\SYSVOL\<domain>\policies\`, e.g. `\\contoso.com\SYSVOL\contoso.com\policies\PolicyDefinitions`; the Group Policy tools use every `.admx` file found there. [DOC S-iymw4lcl]
- Files in the Central Store replicate to all domain controllers in the domain because SYSVOL itself replicates (via DFSR on current domains, or FRS on legacy ones); the article does not name the replication engine explicitly. [DER S-iymw4lcl: SYSVOL is the well-known DFSR-replicated share, and the Central Store is a folder inside it]
- Source files for populating or refreshing the store come from either `C:\Windows\PolicyDefinitions` on a Windows 10/11 client, or `C:\Program Files (x86)\Microsoft Group Policy\<version>\PolicyDefinitions` when Administrative Templates were downloaded separately. [DOC S-iymw4lcl]
- `.adml` files are language-specific and sit in a subfolder named for the locale, e.g. `en-US` for English (United States), `ko-KR` for Korean; additional languages need their own `.adml` subfolder copied in. [DOC S-iymw4lcl]
- Recommended update procedure: build a new folder named for the target version (e.g. `PolicyDefinitions-24H2`), copy in the OS's ADMX/ADML set, merge in any OS-extension or application ADMX/ADML, then rename the current `PolicyDefinitions` to a prior-version name (e.g. `PolicyDefinitions-23H2`) and rename the new folder to the production `PolicyDefinitions` name. [DOC S-iymw4lcl]
- Rollback after a bad update: because the prior version was renamed rather than deleted, you can revert by renaming the folders back; the old folder can later be moved to an archive location outside SYSVOL once the new set is confirmed stable. [DOC S-iymw4lcl]
- Windows 10 and later don't include Administrative Templates with the `.adm` extension, and the article recommends Windows 10 or later computers for Group Policy administration. [DOC S-iymw4lcl]
- Group Policy tools ignore a legacy custom `.adm` file that an `.admx` file supersedes (e.g. `System.adm`, `Inetres.adm`). [UNK: not in S-iymw4lcl as re-read 2026-09-27]
- The article links Administrative Templates (.admx) packages for Windows 11 2025 Update (25H2), 2024 Update (24H2), 2023 Update (23H2), 2022 Update (22H2, v3.0 and original), Windows 10 2022 Update (22H2), and Windows 10 1607/Windows Server 2016, plus Group Policy Settings Reference Spreadsheets for 25H2, 24H2, 23H2 (v2.0 and original) and Windows 10 22H2. [DOC S-iymw4lcl]
- Caution: use the ADMX download packages only to populate the Central Store; replacing the files in `C:\Windows\PolicyDefinitions` (the per-machine local store) with them isn't supported. [DOC S-iymw4lcl]
- The sysvol `PolicyDefinitions` folder is not auto-updated when local `.admx`/`.adml` files change on a client (by design, to limit network/disk load and avoid file-version conflicts); an admin must manually copy updated files to the Central Store to publish them. [DOC S-iymw4lcl]
- A registry override, `EnableLocalStoreOverride` (`REG_DWORD`) under `HKLM\SOFTWARE\Policies\Microsoft\Windows\Group Policy`, controls store precedence for the Group Policy Editor: `0` (default) uses the SYSVOL `PolicyDefinitions` folder when present, `1` always uses the local `C:\Windows\PolicyDefinitions` folder instead. [DOC S-xtwd545o]
- When the Central Store's ADMX/ADML are a different version than what a given DC or RSAT client expects, settings can show as "Extra Registry Settings" and become uneditable in the GUI (they can still be changed with `Set-GPRegistryValue` / `Remove-GPRegistryValue`); mismatched ADMX/ADML file sets with the same file names can't simply be merged. [DOC S-xtwd545o]
- Known issue 1: after overwriting the Central Store with the Windows 10 templates, selecting the Policies node can raise `Namespace '<X>' is already defined as the target namespace for another file in the store`, naming the `.admx` file, line and column. [DOC S-iymw4lcl]
- The cause of that error is two ADMX files in the store declaring the same target namespace (e.g. an old add-on file superseded by a new in-box one). [UNK: not in S-iymw4lcl as re-read 2026-09-27]
- Known ADML/ADMX mismatch error: `Resource $(string id="Win7Only)' referenced in attribute displayName could not be found` when opening `gpedit.msc` after updating to the Windows 10 1803 files, because the 1803 `SearchOCR.ADML` dropped the `Win7Only` string; fixed by taking the updated `SearchOCR.ADMX` and `SearchOCR.ADML` from the 1803 package, or worked around by adding the string back to the ADML. [DOC S-z4lluk64]
- General guidance to avoid both known-issue classes: build the new `PolicyDefinitions` folder from a single, pristine base-OS release rather than layering partial updates over an existing store. [DOC S-iymw4lcl]
- Third-party/vendor ADMX merge pattern (general, matches the Central Store layout): copy the vendor's `.admx` to the `PolicyDefinitions` folder and its `.adml` to the matching language subfolder (e.g. `en-US`); shown for Microsoft Edge's `msedge.admx`/`msedge.adml` copied into `%systemroot%\sysvol\domain\policies\PolicyDefinitions` and its `en-US` subfolder (Edge's second template, `msedgeupdate.admx`, manages Edge updates), after which new ADMX files replicate to other DCs at the next domain replication interval. [DOC S-2lf5j2iv]
- Microsoft Edge Group Policy settings appear immediately in the Group Policy Editor once the ADMX/ADML files are placed in the checked `PolicyDefinitions` location (Central Store on a domain controller/RSAT workstation, or the local folder for a standalone computer). [DOC S-2lf5j2iv]
- Office and LAPS/WinGet-style app ADMX merges follow the same shape as the Edge example above: copy the app's `.admx` into `PolicyDefinitions` and its `.adml` into the matching language subfolder, without deleting or renaming files that other vendors' ADMX still reference; for LAPS's and WinGet's own file names and exact steps, see `windows/laps.md` and `windows/winget.md` (not duplicated here). [DER S-iymw4lcl, S-2lf5j2iv: same copy-to-PolicyDefinitions-plus-language-subfolder pattern documented for Edge and generalized in the Central Store article for "operating system extensions ... and also third-party applications"]
- `EnableLocalStoreOverride` (REG_DWORD under `HKLM\SOFTWARE\Policies\Microsoft\Windows\Group Policy`) = `0`, the default, uses the SYSVOL `PolicyDefinitions` folder when it is present; `1` always uses the local `C:\Windows\PolicyDefinitions`. [DOC S-xtwd545o]
- AD DS replicates SYSVOL (and so the Central Store) with DFS Replication in domains at the Windows Server 2008 domain functional level or later; FRS is deprecated since Windows Server 2008 R2, and from Windows Server 2019 a new domain controller cannot be promoted into a domain that still replicates SYSVOL with FRS (migrate with `dfsrmig`). [DOC S-6glsfens, S-gvgapsup]

## Reference
| Item | Location | Source |
|---|---|---|
| Central Store folder | `\\<domain>\SYSVOL\<domain>\policies\PolicyDefinitions` | S-iymw4lcl |
| Versioned update folder | `\\<domain>\SYSVOL\<domain>\policies\PolicyDefinitions-24H2` | S-iymw4lcl |
| Client-side ADMX source | `C:\Windows\PolicyDefinitions` | S-iymw4lcl |
| Separately downloaded ADMX source | `C:\Program Files (x86)\Microsoft Group Policy\<version>\PolicyDefinitions` | S-iymw4lcl |
| ADML language subfolder example | `PolicyDefinitions\en-US` | S-iymw4lcl |
| Local-store override registry value | `HKLM\SOFTWARE\Policies\Microsoft\Windows\Group Policy\EnableLocalStoreOverride` (`REG_DWORD`, `0`=Central Store if present, `1`=always local) | S-xtwd545o |
| Windows 11 24H2 ADMX download | https://www.microsoft.com/download/details.aspx?id=106254 | S-iymw4lcl |
| Windows 11 25H2 ADMX download | https://www.microsoft.com/download/details.aspx?id=108394 | S-iymw4lcl |
| Microsoft Edge ADMX/ADML | `msedge.admx` / `msedge.adml` into `PolicyDefinitions` and its `en-US` subfolder (`msedgeupdate.admx` is the separate update-policy template) | S-2lf5j2iv |

## Examples
- Build and swap a versioned Central Store update on a DC named `PL-SRV-0042` (placeholders only):
  1. Create `\\corp.example.com\SYSVOL\corp.example.com\policies\PolicyDefinitions-24H2`.
  2. Copy the OS ADMX/ADML from a pristine Windows 11 24H2 client's `C:\Windows\PolicyDefinitions`, then merge in vendor ADMX (Edge, LAPS, WinGet, Office) per each product's own doc.
  3. Rename the current `PolicyDefinitions` to `PolicyDefinitions-23H2`.
  4. Rename `PolicyDefinitions-24H2` to `PolicyDefinitions`.
  5. Wait for SYSVOL replication to reach every DC before relying on the update domain-wide.
  6. If GPMC shows a namespace-conflict or missing-resource error afterward, rebuild the folder from a single pristine OS release rather than patching file-by-file. [DOC S-iymw4lcl], [DOC S-z4lluk64]
- Force a single admin workstation to use its local `C:\Windows\PolicyDefinitions` instead of the Central Store while testing a new ADMX set: set `EnableLocalStoreOverride=1` under `HKLM\SOFTWARE\Policies\Microsoft\Windows\Group Policy`, test, then reset to `0`. [DOC S-xtwd545o]
