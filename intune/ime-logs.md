---
topic: intune/ime-logs
priority: P1
applies_to: "Intune Management Extension 1.58.103.0+, doc ms.date 2026-09-24"
retrieved_utc: 2026-09-24
sources: [S-ta4g5get]
status: complete
---
# Intune Management Extension (IME) logs

## Summary
IME logs are in `C:\ProgramData\Microsoft\IntuneManagementExtension\Logs` (CMTrace format viewer recommended). Eleven
log files are documented. Service name `IntuneManagementExtension`.

## Facts
- Log folder: `C:\ProgramData\Microsoft\IntuneManagementExtension\Logs`; view with CMTrace.exe. [DOC S-ta4g5get]
- The IME appears as service **IntuneManagementExtension**; restarting it triggers a check-in. [DOC S-ta4g5get]
- Config file: `C:\Program Files (x86)\Microsoft Intune Management Extension\Microsoft.Management.Services.IntuneWindowsAgent.exe.config`. [DOC S-ta4g5get]
- IME is removed when no scripts are assigned, the device is no longer managed, or it is irrecoverable for over 24 h device-awake time. [DOC S-ta4g5get]
- Log file list is in the table below. [DOC S-ta4g5get]

## Reference
| Log file | Description (summarised) [S-ta4g5get] |
|---|---|
| IntuneManagementExtension.log | main log: check-ins, policy requests, processing, reporting |
| AgentExecutor.log | PowerShell script executions |
| AppActionProcessor.log | detection and applicability checks for assigned apps |
| AppWorkload.log | Win32 app deployment activity |
| ClientCertCheck.log | device client certificate checks |
| ClientHealth.log | IME health |
| DeviceHealthMonitoring.log | hardware readiness, inventory and other collectors |
| HealthScripts.log | remediations on a schedule |
| NotificationInfra.log | real-time notification channel |
| Sensor.log | Endpoint analytics collector |
| Win32AppInventory.log | app inventory collector |

Win32 app rules, return codes and dependency/supersedence limits: `intune/win32-apps.md` (cross-links `AppActionProcessor.log` and `AppWorkload.log` above).

## Examples
Remediation drift check on `PL-LT-00123`: look in `HealthScripts.log`.
