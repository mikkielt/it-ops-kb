---
topic: mecm/baselines
priority: P0
applies_to: "ConfigMgr current branch 2603 (docs at MicrosoftDocs/memdocs 4b5429df)"
retrieved_utc: 2026-09-23
sources: [S201, S202, S203, S204, S231, S232]
status: partial
---

## Summary
A configuration baseline holds CIs (specific revision or "Always Use Latest") and is deployed to a user or device collection
with a simple or custom evaluation schedule (default from the client setting "Schedule compliance evaluation"). The client
adds a 2-hour randomization window and launch conditions (power, idle; 24 h deadline on first run). Results are cached 15
minutes on manual re-evaluation. No minimum evaluation interval is documented.

## Facts
- Baselines contain CIs and optionally other baselines; name max 255 characters, description max 512. [DOC S201]
- Each CI in a baseline uses a specific revision or **Always Use Latest**. [DOC S201]
- CI evaluation order inside a baseline cannot be specified; it is non-deterministic. [DOC S201]
- Max 1000 software updates per baseline. [DOC S201]
- Purpose (application CIs only): Required, Optional, Prohibited. [DOC S201]
- Modifying a baseline increments its content version; clients must evaluate the new version before reporting updates. [DOC S201]
- A changed CI in a deployed baseline is not evaluated until the next scheduled evaluation. [DOC S202]
- Deployment options: remediate noncompliant rules when supported (WMI, registry, scripts, MDM settings); allow remediation outside the maintenance window; alert below a compliance % by a date; collection; evaluation schedule (simple or custom). [DOC S202]
- Device-targeted deployments: after first evaluation, the baseline runs within a 2-hour randomization window of each scheduled start. [DOC S202]
- First evaluation on Windows client needs power above low-battery threshold and user idle; otherwise it waits until both are true or a 24-hour (1440-minute) internal deadline passes. [DOC S202]
- Later evaluations: pending timer shortened to 1 minute for recurring schedules of daily or longer cadence, so they run within the 2-hour window regardless of idle/power. [DOC S202]
- Windows Server skips the idle check; every evaluation runs within the 2-hour window. [DOC S202]
- Idle detection uses hidden task `\Microsoft\Configuration Manager\Configuration Manager Idle Detection` (On idle trigger, runs as SYSTEM). [DOC S202]
- User-targeted deployments evaluate the next time the target user signs in; no 2-hour randomization. [DOC S202]
- `Scheduler.log` identifies the schedule as `Machine/{AssignmentUniqueID}` or `<UserSID>/{AssignmentUniqueID}`; `DEADLINE:<id>` prefixed auxiliary schedules exist. [DOC S202]
- Condition bitmask `0xa` in Scheduler.log = on-battery-above-low + idle. [DOC S202]
- `Get-CMBaselineDeployment` returns `AssignmentUniqueID` (the ID seen on the client). [DOC S202]
- Manual evaluation from Control Panel > Configuration Manager > Configurations > Evaluate; results cached 15 minutes. [DOC S202,S203]
- Default schedule for baseline deployments is set by client setting **Schedule compliance evaluation**; can be changed per deployment. [DOC S204]
- Minimum evaluation interval for a baseline deployment: not documented in the compliance docs. [UNK]
- The schedule token class `SMS_ST_RecurInterval` accepts `MinuteSpan` 0-59, `HourSpan` 0-23, `DaySpan` 0-31, so the token format itself can express sub-hour intervals; whether the console or client enforces a floor for baselines is not documented. [DER S231,S232: EvaluationSchedule is a schedule-token string on SMS_CIAssignmentBaseClass; token ranges from S231]
- Baselines can be included in compliance policy assessment only when deployed to device collections. [DOC S201]
- Logs for baseline evaluation in compliance policy assessment: ComplianceHandler.log, SettingsAgent.log, DCMAgent.log, CIAgent.log. [DOC S201]
- Monitoring shows states including **Unknown** (did not report compliance). [DOC S203]
- Report parameters Device filter / User filter require the `%` wildcard. [DOC S203]

## Reference
| Parameter | Value | Tag |
|---|---|---|
| Randomization window (device) | 2 hours | [DOC S202] |
| First-run launch-condition deadline | 24 h (1440 min) | [DOC S202] |
| Manual re-evaluation cache | 15 min | [DOC S203] |
| Minimum schedule interval | not documented | [UNK] |
| Schedule token ranges | MinuteSpan 0-59, HourSpan 0-23, DaySpan 0-31 | [DOC S231] |

## Examples
Scheduler.log line for a device deployment on `PL-LT-00123`:
`SMSTrigger 'DA089D0000100008' for scheduler 'Machine/{01234567-89AB-CDEF-0123-456789ABCDEF}' will fire at ... with randomization.` (format from S202)
