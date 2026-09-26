---
topic: logs/sources
priority: P1
applies_to: "Windows 10/11, ConfigMgr current branch, Intune, Autopilot, Entra ID (docs 2021-2026)"
retrieved_utc: 2026-09-24
sources: [S603, S608, S611, S616, S617, S618, S619, S632, S633, S634, S635, S636, S637, S638, S648, S649]
status: partial
---
# Device log sources (files, event channels, commands)

## Summary
`logs/sources.csv` lists 50 log sources with exact channel names or paths, product, component, scenario and source id.
`kind` is file | event_channel | command; a few rows are registry values that switch logging on — they carry
kind `file` and say "Registry value (not a file)" in `scenario`. ConfigMgr writes to log files, not to its own event
channels; the full ConfigMgr log table is `mecm/log-files.csv` (another agent).

## Facts
- MDM channels: `Microsoft-Windows-DeviceManagement-Enterprise-Diagnostics-Provider/Admin` (on by default) and `/Debug` (enable via Show Analytic and Debug logs). [DOC S617]
- Autopilot logs to Event Viewer > Application and Services Logs > Microsoft > Windows > ModernDeployment-Diagnostics-Provider > Autopilot. [DOC S619]
- Channel name `Microsoft-Windows-ModernDeployment-Diagnostics-Provider/Autopilot`: derived from that Event Viewer path using the naming shown for other channels (e.g. `Microsoft-Windows-AAD/Operational` ↔ Microsoft > Windows > AAD). [DER S619,S632]
- Hybrid join failures: `User Device Registration` log under Microsoft > Windows (event IDs 201, 204, 304, 305). [DOC S632]
- Exact channel name `Microsoft-Windows-User Device Registration/Admin`. [DOC S649]
- PRT/CloudAP events: Microsoft > Windows > AAD. Event 1006 (start) and 1007 (end, with the final error code) of PRT acquisition are in the Analytic log; the CloudAP plug-in writes errors to Operational and info events to Analytic, and both logs are needed. [DOC S632]
- ESP/runtime provisioning evtx files: DeviceManagement-Enterprise-Diagnostics-Provider%4Admin, Provisioning-Diagnostics-Provider%4Admin, AAD%4Operational under `%windir%\System32\winevt\Logs`. [DOC S618]
- Intune Connector for AD logs moved to Applications and Services Logs > Microsoft > Intune > ODJConnectorService. [DOC S619]
- GPSvc debug: create `HKLM\Software\Microsoft\Windows NT\CurrentVersion\Diagnostics`, DWORD `GPSvcDebugLevel` = 0x30002, then `gpupdate /force`; log `%windir%\debug\usermode\gpsvc.log`; not created if the usermode folder is missing. [DOC S633]
- `gpresult /h` and `gpresult /r` capture RSoP; `wevtutil export-log Microsoft-Windows-GroupPolicy/Operational` exports GP events. [DOC S633]
- Netlogon debug: `Nltest /DBFlag:2080FFFF` (off: `/DBFlag:0x0`) or registry `...\Netlogon\Parameters\DBFlag`; log `%windir%\debug\netlogon.log`; restart usually not needed on 2012 R2+. [DOC S634]
- Netlogon.log default max 20 MB, then renamed Netlogon.bak (`MaximumLogFileSize` changes it). [DOC S634]
- Kerberos: `HKLM\SYSTEM\CurrentControlSet\Control\Lsa\Kerberos\Parameters\LogLevel` (REG_DWORD, default 0); non-zero logs all Kerberos events to the System event log, including false positives. [DOC S635]
- `Get-WindowsUpdateLog` merges Windows Update `.etl` files into `WindowsUpdate.log` (default on the current user's Desktop, `-LogPath` to change); Windows Update no longer writes WindowsUpdate.log directly; pre-1709 logs need a symbol server. [DOC S638]
- CBS: `C:\Windows\Logs\CBS\CBS.log`, archives `CbsPersist_*.log/.cab`; DISM: `C:\Windows\Logs\DISM\dism.log`. [DOC S637]
- Setup (Panther): down-level `C:\$WINDOWS.~BT\Sources\Panther\setupact.log`/`setuperr.log`; WinPE `X:\$WINDOWS.~BT\...`; online configuration and Welcome `C:\WINDOWS\PANTHER\setupact.log`; drivers `C:\WINDOWS\INF\setupapi.dev.log`. [DOC S636]
- IME logs: `C:\ProgramData\Microsoft\IntuneManagementExtension\Logs`. [DOC S611]
- Tenant attach logs: CMGatewaySyncUploadWorker.log, CMGatewayNotificationWorker.log, GenericUploadWorker.log (site server), BgbServer.log (MP), CcmNotificationAgent.log (client). [DOC S608]
- A `DeviceManagement-Enterprise-Diagnostics-Provider/Operational` channel is not documented in the cloned sources. [UNK]

## Reference
`sources.csv`: path_or_channel, kind, product, component, scenario, source_id.
- WEF/WEC subscription setup and Sysmon (install, event IDs, built-in optional feature status): `windows/event-forwarding-sysmon.md`.
- Centralized cloud collection of these same event channels via Azure Monitor Agent, DCR `windowsEventLogs`/XPath filters, and the Logs Ingestion API: `logs/azure-monitor-agent.md`.

## Examples
On `PL-LT-00123`: `wevtutil qe "Microsoft-Windows-User Device Registration/Admin" /c:20 /f:text`;
`Get-WindowsUpdateLog -LogPath C:\Temp\PL-LT-00123-WindowsUpdate.log`.
