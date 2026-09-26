---
topic: mecm/cmpivot
priority: P0
applies_to: "ConfigMgr current branch 2603"
retrieved_utc: 2026-09-23
sources: [S-igpzfey7, S-ebuvm65r, S-2z2zfj3l, S-sxtmngif, S317, S-e5qqwdcj, S-dyvqhf4u, S-bprslswi, S321, S322, S-5v5lco6w, S-6l4nubjq]
status: partial
files: [mecm/cmpivot-entities.csv]
---

# CMPivot

## Summary
CMPivot sends a KQL-subset query to online clients over the client notification "fast channel". Results come back as state messages. The entity list is in `mecm/cmpivot-entities.csv`: 148 shared entities plus 5 that work only from the ConfigMgr console.
Per-entity column lists are **not** officially documented. That includes `CcmLog()` and `WinEvent()`: only the columns used in Microsoft's example queries are known.
`ago()`, `now()`, `datetime_diff()`, `datetime_add()` and `bin()` are documented. Datetime literals use `datetime(yyyy-mm-dd HH:MM:ss)`, in UTC.
Limits: 128 KB per client per query, 100,000 cells in the results, a 1-hour timeout (10 minutes from the Intune admin center), at most 5 joins and 64 columns.

## Facts
- CMPivot uses a subset of KQL: `entity | operator1 | operator2 ...`. [DOC S317]
- Table operators: count, distinct, join, order by, project, take, top, where, plus summarize for aggregations. `render` works only from ConfigMgr, not from the Intune admin center. [DOC S317]
- Scalar operators: `== != < > <= >= + - * / %`, `like`, `!like`, `contains`, `!contains`, `startswith`, `!startswith`, `endswith`, `!endswith`, `and`, `or`. [DOC S317]
- Aggregation functions: avg, count, countif, dcount, max, maxif (2107+), min, minif (2107+), percentile, sum, sumif. [DOC S317]
- Scalar functions: ago, bin, case, datetime_add, datetime_diff, iif, indexof, isnotnull, isnull, now, strcat, strlen, substring, tostring. [DOC S317]
- `ago()` subtracts a timespan from the current UTC time, for example `ago(1d)` or `ago(7d)`. `now()` returns the current UTC time. [DOC S-sxtmngif]
- Datetime values are UTC and measured in 1-second units. Literals are written in ISO 8601, e.g. `datetime(2015-12-31 23:59:59.9)`. [DOC S-sxtmngif]
- Datetime arithmetic works with timespans: `now() + 1d`, `now() - 1h`. [DOC S317]
- `datetime_diff('day', now(), QuickScanEndTime)` is used in an official example. [DOC S-sxtmngif]
- Timespan suffixes used in official examples: `h` (1h, 2h), `d` (1d, 7d, 120d). No other suffixes are listed. [DER S-sxtmngif,S321: set of suffixes seen in examples only]
- `CcmLog('<log name>'[, <timespan>])` returns lines from a Ccm log file, from the last 24 hours by default. Example: `CcmLog('Scripts',1h)`. [DOC S-sxtmngif,S317]
- `CcmLog()` result columns are not documented in any official source found. [UNK]
- `WinEvent(<logname>,[<timespan>])` reads Windows event logs and ETW log files, from the last 24 hours by default. Example: `WinEvent('Microsoft-Windows-HelloForBusiness/Operational', 1d)`. [DOC S-sxtmngif]
- The only `WinEvent()` column named in official docs is `LevelDisplayName`. Other columns are not documented. [DOC S-sxtmngif]
- `EventLog('<log>'[, <timespan>])` also defaults to 24 hours. An example uses column `EventID`. [DOC S-sxtmngif]
- Per-entity columns cannot be customized. [DOC S-2z2zfj3l] Official docs give no column list per entity. [UNK]
- Hardware inventory classes, including extended ones, can be queried as entities. These classes do not support array properties, Real32/Real64 or embedded objects. Cached inventory data is returned first, then live data. [DOC S-sxtmngif]
- Entities Administrators, Connection, IPConfig and SMBConfig need PowerShell 5.0 on the client. Other entities need PowerShell 4 or later. [DOC S-2z2zfj3l]
- Each client returns at most 128 KB per query. Larger results are truncated, and a warning is shown from 2103; they cannot be exported. [DOC S-sxtmngif]
- The results pane shows at most 100,000 cells (1810+). From 2103, larger results offer a CSV export. [DOC S-sxtmngif]
- Joins are always implicit on `Device`, with at most 5 joins and 64 combined columns per query. [DOC S-sxtmngif]
- A query times out after one hour, and clients that come online within that hour still answer. [DOC S-2z2zfj3l]
- From the Intune admin center, the query times out after 10 minutes. [DOC S-dyvqhf4u]
- Client output under 80 KB returns over the fast channel. Larger output is sent as a state message. [DOC S-sxtmngif,S-e5qqwdcj]
- CMPivot returns data only for clients of the current site, unless it runs from the CAS. A CAS with a remote SQL Server or provider needs Kerberos constrained delegation. [DOC S-2z2zfj3l,S-sxtmngif]
- Permissions (2107+): Run CMPivot on Collection and Read on Inventory Reports. Read on SMS Scripts and the default scope are no longer needed. SMS Scripts Read is still needed if the AdminService falls back to the SMS Provider on HTTP 503. [DOC S-2z2zfj3l,S-sxtmngif]
- Permissions in 1906–2103: Run CMPivot, Inventory Reports Read, SMS Scripts Read and default scope. In 1902 and earlier: Run Script instead of Run CMPivot. [DOC S-2z2zfj3l]
- Run Scripts is a superset of the Run CMPivot permission. [DOC S-sxtmngif]
- From the Intune admin center: Read and Run CMPivot on the Collection, plus an Intune role. With Intune RBAC, the permission is "Cloud attached devices\Run CMPivot query". [DOC S-bprslswi,S-5v5lco6w]
- Each CMPivot run creates an audit status message with MessageID 40805 (1810+). The CMPivot script GUID is `7DC6B6F1-E7F6-43C1-96E0-E1D16BC25C14`. [DOC S-sxtmngif]
- smsprov.log records "initiated client operation 145" for CMPivot in 1906+. [DOC S-e5qqwdcj]
- AdminService routes: POST `v1.0/Device(<id>)/AdminService.RunCMPivot` with body `{"InputQuery":"..."}`, then GET `.../AdminService.CMPivotResult(OperationId=<id>)`. [DOC S-igpzfey7]
- The response schemas of `RunCMPivot` and `CMPivotResult` are not documented. [UNK]
- 2603 fixed CMPivot-over-AdminService "400 Bad Request" parse failures. Before the fix, CMPivot fell back to the SMS Provider path, which needs Script Read. [DOC S-ebuvm65r]
- Entities not supported from the Intune admin center: AccountSID, FileContent(), NAPClient, NAPSystemHealthAgent, RegistryKey(). [DOC S317]
- Logs: server-side SmsProv.log, BgbServer.log, StateSys.log. Client-side CcmNotificationAgent.log, Scripts.log, StateMessage.log. [DOC S-2z2zfj3l]
- The monitoring view `vSMS_CMPivotStatus` is queried by TaskID in troubleshooting. [DOC S-e5qqwdcj]
- CMPivot standalone ships at `<site install path>\tools\CMPivot\CMPivot.msi` and is English only. It cannot open Community hub queries. [DOC S322,S-2z2zfj3l]
- Security software may block scripts in `%windir%\CCM\ScriptStore`. Microsoft recommends excluding that folder. [DOC S-2z2zfj3l]

## Reference
- Entities: `mecm/cmpivot-entities.csv`. Columns: entity, kind, description, parameters, columns seen in official examples, console_only, min_version, source.
- Version-scoped permission table: see `mecm/rbac.md` and `mecm/rbac-permissions.csv`.

## Examples
```kusto
CcmLog('Scripts', 1h)
WinEvent('Microsoft-Windows-DSC/Operational', 2d) | where LevelDisplayName == 'Error' | summarize count() by Device
OperatingSystem | where LastBootUpTime <= ago(7d) | summarize count() by bin(LastBootUpTime, 1d)
Device | where Device == 'PL-LT-00123'
```
