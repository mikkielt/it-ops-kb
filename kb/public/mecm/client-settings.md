---
topic: mecm/client-settings
priority: P0
applies_to: "ConfigMgr current branch 2603 (about-client-settings.md ms.date 2025-12-08)"
retrieved_utc: 2026-09-26
sources: [S-pm6pjuef, S-le4dru57]
status: partial
---

## Summary
Client settings are managed in Administration > Client Settings; default settings apply to all clients, custom settings
assigned to collections override them. Full tables below cover Client policy, Compliance settings, Computer agent,
Hardware inventory, Software deployment and State messaging; other groups are listed by name only.

## Facts
- Default client settings apply hierarchy-wide; custom client settings override defaults when assigned to collections. [DOC S-pm6pjuef]
- Client policy polling interval: default 60 minutes. [DOC S-pm6pjuef]
- User policy for multiple user sessions is disabled by default on multi-session devices at new install. [DOC S-pm6pjuef]
- Compliance settings: Enable compliance evaluation on clients; Schedule compliance evaluation (default schedule for baseline deployments); Enable User Data and Profiles; Script Execution Timeout (seconds) 60-600, default 60 (2207+). [DOC S-pm6pjuef]
- PowerShell execution policy: Bypass / Restricted / All Signed; default All Signed; requires PowerShell 2.0+. [DOC S-pm6pjuef]
- Grace period for enforcement after deadline: 0-120 hours. [DOC S-pm6pjuef]
- Disable deadline randomization: applies only to manual software update deployments. [DOC S-pm6pjuef]
- Hardware inventory: default every 7 days; max random delay 0-480 min, default 240; custom MIF 1-5,120 KB, default 250 KB. [DOC S-pm6pjuef]
- Software deployment: Schedule re-evaluation for deployments default every 7 days; Microsoft doesn't recommend lower. [DOC S-pm6pjuef]
- State message reporting cycle: default 15 minutes. [DOC S-pm6pjuef]
- Remote tools group: remote control, Remote Assistance, Remote Desktop settings (not tabulated). [DOC S-pm6pjuef]

## Reference
| Group | Setting | Values / default | Tag |
|---|---|---|---|
| Client policy | Client policy polling interval | default 60 min | [DOC S-pm6pjuef] |
| Client policy | Enable user policy on clients | Yes/No | [DOC S-pm6pjuef] |
| Client policy | Enable user policy requests from internet clients | Yes/No | [DOC S-pm6pjuef] |
| Client policy | Enable user policy for multiple user sessions | default disabled | [DOC S-pm6pjuef] |
| Compliance settings | Enable compliance evaluation on clients | Yes/No | [DOC S-pm6pjuef] |
| Compliance settings | Schedule compliance evaluation | schedule (default for baseline deployments) | [DOC S-pm6pjuef] |
| Compliance settings | Enable User Data and Profiles | Yes/No | [DOC S-pm6pjuef] |
| Compliance settings | Script Execution Timeout (seconds) | 60-600, default 60 | [DOC S-pm6pjuef] |
| Computer agent | Deadline reminder intervals (>24h, <24h, <1h) | hours/minutes | [DOC S-pm6pjuef] |
| Computer agent | Organization name displayed in Software Center | text | [DOC S-pm6pjuef] |
| Computer agent | Use new Software Center | default Yes | [DOC S-pm6pjuef] |
| Computer agent | Install permissions | All Users / Only Administrators / Only Administrators and primary users / No Users | [DOC S-pm6pjuef] |
| Computer agent | Suspend BitLocker PIN entry on restart | Always / Never | [DOC S-pm6pjuef] |
| Computer agent | Additional software manages deployment | Yes/No | [DOC S-pm6pjuef] |
| Computer agent | PowerShell execution policy | Bypass / Restricted / All Signed (default) | [DOC S-pm6pjuef] |
| Computer agent | Show notifications for new deployments | Yes/No | [DOC S-pm6pjuef] |
| Computer agent | Disable deadline randomization | Yes/No (randomization up to 2 h) | [DOC S-pm6pjuef] |
| Computer agent | Grace period for enforcement after deadline | 0-120 h | [DOC S-pm6pjuef] |
| Computer agent | Enable Endpoint analytics data collection | Yes/No | [DOC S-pm6pjuef] |
| Hardware inventory | Schedule | default 7 days | [DOC S-pm6pjuef] |
| Hardware inventory | Maximum random delay | 0-480 min, default 240 | [DOC S-pm6pjuef] |
| Hardware inventory | Maximum custom MIF file size | 1-5120 KB, default 250 | [DOC S-pm6pjuef] |
| Software deployment | Schedule re-evaluation for deployments | default 7 days | [DOC S-pm6pjuef] |
| State messaging | State message reporting cycle | default 15 min | [DOC S-pm6pjuef] |

Other groups (names only): BITS, Client cache settings, Cloud services, Computer restart, Delivery Optimization, Endpoint
Protection, Enrollment, Metered internet connections, Power management, Remote tools, Software Center, Software inventory,
Software metering, Software updates, User and device affinity. [DOC S-pm6pjuef]

Note: the "Deadline randomization" wording in S-pm6pjuef says "activation delay of up to two hours", and "Grace period ... 0 to 120 hours" in client settings vs "1 and 120 hours" in S-le4dru57 (see conflicts).

## Examples
Custom client setting "lab-settings" assigned to a lab collection containing `PL-LT-00123`: Script Execution Timeout 300 s.
