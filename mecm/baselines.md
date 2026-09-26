---
topic: mecm/baselines
priority: P0
applies_to: "ConfigMgr current branch 2603 (docs at MicrosoftDocs/memdocs 4b5429df)"
retrieved_utc: 2026-09-23
sources: [S-f6ejsacc, S-smzttlyd, S-6war5y2t, S-pm6pjuef, S-xcvlnpgb, S-eswaciiy]
status: partial
---

## Summary
A configuration baseline holds CIs (specific revision or "Always Use Latest") and is deployed to a user or device collection
with a simple or custom evaluation schedule (default from the client setting "Schedule compliance evaluation"). The client
adds a 2-hour randomization window and launch conditions (power, idle; 24 h deadline on first run). Results are cached 15
minutes on manual re-evaluation. No minimum evaluation interval is documented.

## Facts
- Baselines contain CIs and optionally other baselines; name max 255 characters, description max 512. [DOC S-f6ejsacc]
- Each CI in a baseline uses a specific revision or **Always Use Latest**. [DOC S-f6ejsacc]
- CI evaluation order inside a baseline cannot be specified; it is non-deterministic. [DOC S-f6ejsacc]
- Max 1000 software updates per baseline. [DOC S-f6ejsacc]
- Purpose (application CIs only): Required, Optional, Prohibited. [DOC S-f6ejsacc]
- Modifying a baseline increments its content version; clients must evaluate the new version before reporting updates. [DOC S-f6ejsacc]
- A changed CI in a deployed baseline is not evaluated until the next scheduled evaluation. [DOC S-smzttlyd]
- Deployment options: remediate noncompliant rules when supported (WMI, registry, scripts, MDM settings); allow remediation outside the maintenance window; alert below a compliance % by a date; collection; evaluation schedule (simple or custom). [DOC S-smzttlyd]
- Device-targeted deployments: after first evaluation, the baseline runs within a 2-hour randomization window of each scheduled start. [DOC S-smzttlyd]
- First evaluation on Windows client needs power above low-battery threshold and user idle; otherwise it waits until both are true or a 24-hour (1440-minute) internal deadline passes. [DOC S-smzttlyd]
- Later evaluations: pending timer shortened to 1 minute for recurring schedules of daily or longer cadence, so they run within the 2-hour window regardless of idle/power. [DOC S-smzttlyd]
- Windows Server skips the idle check; every evaluation runs within the 2-hour window. [DOC S-smzttlyd]
- Idle detection uses hidden task `\Microsoft\Configuration Manager\Configuration Manager Idle Detection` (On idle trigger, runs as SYSTEM). [DOC S-smzttlyd]
- User-targeted deployments evaluate the next time the target user signs in; no 2-hour randomization. [DOC S-smzttlyd]
- `Scheduler.log` identifies the schedule as `Machine/{AssignmentUniqueID}` or `<UserSID>/{AssignmentUniqueID}`; `DEADLINE:<id>` prefixed auxiliary schedules exist. [DOC S-smzttlyd]
- Condition bitmask `0xa` in Scheduler.log = on-battery-above-low + idle. [DOC S-smzttlyd]
- `Get-CMBaselineDeployment` returns `AssignmentUniqueID` (the ID seen on the client). [DOC S-smzttlyd]
- Manual evaluation from Control Panel > Configuration Manager > Configurations > Evaluate; results cached 15 minutes. [DOC S-smzttlyd,S-6war5y2t]
- Default schedule for baseline deployments is set by client setting **Schedule compliance evaluation**; can be changed per deployment. [DOC S-pm6pjuef]
- Minimum evaluation interval for a baseline deployment: not documented in the compliance docs. [UNK]
- The schedule token class `SMS_ST_RecurInterval` accepts `MinuteSpan` 0-59, `HourSpan` 0-23, `DaySpan` 0-31, so the token format itself can express sub-hour intervals; whether the console or client enforces a floor for baselines is not documented. [DER S-xcvlnpgb,S-eswaciiy: EvaluationSchedule is a schedule-token string on SMS_CIAssignmentBaseClass; token ranges from S-xcvlnpgb]
- Baselines can be included in compliance policy assessment only when deployed to device collections. [DOC S-f6ejsacc]
- Logs for baseline evaluation in compliance policy assessment: ComplianceHandler.log, SettingsAgent.log, DCMAgent.log, CIAgent.log. [DOC S-f6ejsacc]
- Monitoring shows states including **Unknown** (did not report compliance). [DOC S-6war5y2t]
- Report parameters Device filter / User filter require the `%` wildcard. [DOC S-6war5y2t]

## Reference
| Parameter | Value | Tag |
|---|---|---|
| Randomization window (device) | 2 hours | [DOC S-smzttlyd] |
| First-run launch-condition deadline | 24 h (1440 min) | [DOC S-smzttlyd] |
| Manual re-evaluation cache | 15 min | [DOC S-6war5y2t] |
| Minimum schedule interval | not documented | [UNK] |
| Schedule token ranges | MinuteSpan 0-59, HourSpan 0-23, DaySpan 0-31 | [DOC S-xcvlnpgb] |

## Examples
Scheduler.log line for a device deployment on `PL-LT-00123`:
`SMSTrigger 'DA089D0000100008' for scheduler 'Machine/{01234567-89AB-CDEF-0123-456789ABCDEF}' will fire at ... with randomization.` (format from S-smzttlyd)
