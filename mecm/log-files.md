---
topic: mecm/log-files
priority: P0
applies_to: "ConfigMgr current branch 2603 (log-files.md ms.date 2025-08-11, memdocs 4b5429df)"
retrieved_utc: 2026-09-23
sources: [S212, S213, S214]
status: complete
---

## Summary
`log-files.csv` (sha256 `7f5532614548846a04e2b9b58a8994e9722c0d62d51a6585f95184f801431f46`) holds all 433 rows of the "Log file reference" tables, including the included
cloud management gateway table: columns log, location_or_role, component (doc section), description, source_id. Client-operation
and client-installation rows have location "Client". The same log can appear in several sections (e.g. DCMAgent.log).
Prose is CC BY 4.0 (MicrosoftDocs/memdocs); the table was normalized (markdown, links and footnote markers removed).

## Facts
- The doc lists client logs (client operations, client installation, Mac), server logs (site server, site install, data warehouse, FSP, MP, SCP, SUP) and logs by functionality. [DOC S212]
- Compliance settings logs (client): CIAgent.log, CITaskManager.log, DCMAgent.log, DCMReporting.log, DcmWmiProvider.log. [DOC S212]
- Client-side related: CIStateStore.log, CIStore.log (CI state/info), Diagnostics.log (client diagnostic actions), Scripts.log (Run Scripts), StateMessageProvider.log, PolicyAgent.log. [DOC S212]
- adminservice.log records SMS Provider administration service REST API actions, on the SMS Provider computer. [DOC S212]
- CMG logs CMGSetup/CMGService/CMGContentService are synced from Azure storage every five minutes (max delay 10 minutes). [DOC S213]
- WSUS server logs are in `%ProgramFiles%\Update Services\LogFiles`. [DOC S212]
- Default log folders: client `C:\Windows\CCM\logs`; server `C:\Program Files\Microsoft Configuration Manager\Logs`; MP `C:\SMS_CCM\Logs`; console `...\AdminConsole\AdminUILog`. [DOC S214]
- CmRcService.log has no location column in the doc; its description says "in the Client logs folder". [DOC S212]

## Reference
| Section | Rows |
|---|---|
| Client operations | 84 |
| Site server and site systems | 81 |
| OS deployment | 31 |
| Management point | 24 |
| Service connection point | 24 |
| Software updates | 20 |
| others (34 sections) | 169 |

## Examples
`grep -i dcm log-files.csv` returns the compliance-settings rows for triage on `PL-LT-00123`.
