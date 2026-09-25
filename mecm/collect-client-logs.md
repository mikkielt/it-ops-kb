---
topic: mecm/collect-client-logs
priority: P2
applies_to: "ConfigMgr current branch 2603 (memdocs 4b5429df)"
retrieved_utc: 2026-09-23
sources: [S221, S222, S223, S224, S226, S235]
status: partial
---

## Summary
Client Diagnostics (device or device collection, console) offers Enable verbose logging, Disable verbose logging and
Collect Client Logs. Collection uses a client notification; the client uploads a compressed `Support_<guid>.zip` (limit 100 MB)
to the MP through the software-inventory file-collection channel. Files are stored on the site server in
`Inboxes\sinv.box\FileCol` and viewed via Resource Explorer > Diagnostic Files. Needs the **Notify resource** permission.
Cleanup: "Delete Aged Collected Diagnostic Files" (default 14 days, 2010+).

## Facts
- Actions: Enable verbose logging (global CCM log level verbose + debug logging), Disable verbose logging, Collect Client Logs. [DOC S221]
- Collect Client Logs: the site sends a client notification; the client sends the CCM logs to the MP by the same channel as software inventory file collection; software inventory need not be enabled. [DOC S221]
- Size limit for the compressed client logs: 100 MB. [DOC S221]
- Status: `diagnostics.log` on the client; `MP_SinvCollFile.log` on the MP; `sinvproc.log` on the site server. [DOC S221]
- Storage: site server `Inboxes\sinv.box\FileCol`; stored per software inventory file collection settings; "no defined limit to the number of versions". [DOC S221,S223]
- Retrieval: console Devices > device > Start > Resource Explorer > Diagnostic Files; name format `Support_<guid>.zip`; actions Open Support Center, Copy, View file, Save, Export, Refresh, Properties (2002+). [DOC S222]
- Permission: **Notify resource**; built-in Full Administrator and Infrastructure Administrator have it. [DOC S221]
- The 1912 technical preview note named Full Administrator and Operations Administrator instead. [DOC S224]
- Maintenance task **Delete Aged Collected Diagnostic Files** (2010+, enabled on primary site, default 14 days) deletes them; 2006 and earlier used Delete Aged Collected Files. [DOC S223]
- Collected files in general: SMS Provider class `SMS_G_System_CollectedFile` (CollectionDate, FileData, FileName, FilePath, FileSize, LocalFilePath, ResourceID, RevisionID) and SQL view `v_GS_CollectedFile`. [DOC S226,S235]
- Whether diagnostic `Support_*.zip` files appear in `SMS_G_System_CollectedFile` / `v_GS_CollectedFile` or in AdminService is not documented. [UNK]
- The client notification operation type value for Collect Client Logs: covered by agent mecm2 (client notification); not checked here. [UNK]

## Reference
| Item | Value | Tag |
|---|---|---|
| Size limit (compressed) | 100 MB | [DOC S221] |
| Site storage | `<install dir>\Inboxes\sinv.box\FileCol` | [DOC S221] |
| File name | `Support_<guid>.zip` | [DOC S222] |
| Cleanup | 14 days default | [DOC S223] |
| RBAC | Notify resource | [DOC S221] |

## Examples
Engineer collects logs from `PL-LT-00123` (console > Client Diagnostics > Collect Client Logs), then reads
`Support_<guid>.zip` from Resource Explorer > Diagnostic Files.
