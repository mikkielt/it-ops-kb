---
topic: intune/device-query
priority: P1
applies_to: "Intune Advanced Analytics, docs ms.date 2026-09-01"
retrieved_utc: 2026-09-24
sources: [S-oaxxx7xc, S-x35diqus, S-dlqk4ney, S-fol5b2wh]
status: complete
---
# Device query (single device) and device query for multiple devices

## Summary
Single-device query runs KQL live on one Windows device via WNS (15 queries/min, 128 kb result, 2,048-char query).
Multi-device query runs KQL over collected inventory (properties catalog) — 10 queries/min, 1,000/month, ~50,000 records,
max 3 joins. Both are Advanced Analytics features needing an add-on licence on top of Intune Plan 1/2.

## Facts
- Advanced Analytics requires a subscription in addition to Intune Plan 1 or Plan 2. [DOC S-dlqk4ney]
- Advanced Analytics supports Windows devices managed by Intune, co-managed, Entra joined or hybrid joined; DoD cloud excludes device query. [DOC S-dlqk4ney]
- Single device query: Windows devices managed by Intune and marked corporate, Entra joined or hybrid joined; runs in real time over WNS, which cannot be bypassed — if WNS is blocked the query fails. [DOC S-oaxxx7xc]
- Single device query RBAC: custom role with **Managed Devices/Query** plus device visibility permissions. [DOC S-oaxxx7xc]
- Single device limits: result string limited to 128 kb characters (truncated with message); 15 queries per minute; query input max 2,048 characters. [DOC S-oaxxx7xc]
- Single device known gaps: no `!like`; `now()` without offset; WindowsRegistry cannot return root RegistryKey, 64-bit shared keys or binary ValueData; FileInfo fails on in-use files; local admins can alter client-side results. [DOC S-oaxxx7xc]
- Single device entities: BiosInfo, Certificate, Cpu, DiskDrive, EncryptableVolume, FileInfo, LocalGroup, LocalUserAccount, LogicalDrive, MemoryInfo, OsVersion, Process, SystemEnclosure, SystemInfo, Tpm, WindowsAppCrashEvent, WindowsDriver, WindowsEvent, WindowsQfe, WindowsRegistry, WindowsService. [DOC S-oaxxx7xc]
- Multi-device query platforms: Windows, Android Enterprise corporate (COSU/COBO/COPE), iOS/iPadOS, macOS; corporate-owned; Windows needs a properties catalog policy. [DOC S-x35diqus]
- Multi-device RBAC: Help Desk Operator or a custom role with device read permissions. [DOC S-x35diqus]
- Multi-device limits: max 3 `join` per query; ~50,000 records returned; 10 queries per minute; 1,000 queries per month; export up to 50,000 rows; client-side search/filter only when ≤ 50 items. [DOC S-x35diqus]
- Multi-device `Device` entity properties include DeviceId (Intune), EntraDeviceId, DeviceName, SerialNumber, Ownership, LastSeenDateTime; joins must use `on Device` (not `on Device.DeviceId`). [DOC S-x35diqus]
- Properties catalog: initial collection up to 24 h; registry inventory HKLM only, 6 KB per value, 100 keys per device; deleted policy data visible up to 28 days. [DOC S-fol5b2wh]
- KQL subset (both): table operators count, distinct, join, order by, project, take, top, where (+ summarize in multi-device table); functions ago, bin, case, datetime_add, datetime_diff, iif, indexof, isnotnull, isnull, now, strcat, strlen, substring, tostring. [DOC S-oaxxx7xc,S-x35diqus]

## Reference
| Limit | Single device | Multiple devices |
|---|---|---|
| Rate | 15 / minute | 10 / minute, 1,000 / month |
| Result | 128 kb characters | ~50,000 records |
| Query length | 2,048 characters | [UNK] |
| Joins | – | max 3 |
| Data | live via WNS | collected inventory |

See also `intune/device-inventory-analytics.md` for Endpoint analytics/Advanced Analytics scores, anomalies, device timeline and battery health, which build on this properties catalog and device query data.

## Examples
Single device (`PL-LT-00123`): `WindowsService | take 5` (column names: see Intune Data Platform Schema, not captured here)
Multi-device: `Cpu | where Device.DeviceName == "PL-LT-00123"`
