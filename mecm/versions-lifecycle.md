---
topic: mecm/versions-lifecycle
priority: P0
applies_to: "ConfigMgr current branch 2603 (latest as of memdocs 4b5429df, 2026-09-02)"
retrieved_utc: 2026-09-26
sources: [S-334svlym, S-qfo4gvbb, S-qhlzdpie, S-ebuvm65r, S-actyzzlw]
status: complete
---

## Summary
2603 exists and is the latest current branch version (5.00.9146.1000, early ring 2026-05-05, globally available
2026-05-27, support ends 2027-11-05). Supported: 2603, 2509, 2503 (2503 ends 2026-09-30). Each version is supported 18
months; only the latest gets critical (non-security) fixes. 2603 highlights: SQL Server 2025 support, SQL Native Client
dependency removed, NAA hardening, CMG weak ciphers off, and management points need internet access for Entra token
validation (MISE) where Entra auth is used.

## Facts
- Each current branch version is supported 18 months from GA; latest version is in "Security and Critical Updates", older supported ones get security updates only. [DOC S-334svlym]
- Supported versions table: 2603 (5.00.9146.1000) available 2026-05-05, support end 2027-11-05, in-console only; 2509 (5.00.9141) 2025-11-12 to 2027-05-12, baseline and update; 2503 (5.00.9135) 2025-03-31 to 2026-09-30, in-console only. [DOC S-qfo4gvbb]
- 2409 support ended 2026-06-04. [DOC S-qfo4gvbb]
- Availability date = early update ring release. [DOC S-qfo4gvbb]
- 2603 is an in-console update for sites on 2409 or later. [DOC S-qhlzdpie]
- As of 2026-05-27, 2603 is globally available. [DOC S-qhlzdpie]
- 2603: NAA access restricted to supported OSD media scenarios (KB37447175). [DOC S-qhlzdpie]
- 2603: CMG weak DHE ciphers disabled; TLS 1.3 and TLS 1.2 ECDHE remain; EnableCertPaddingCheck set on CMG VMSS. [DOC S-qhlzdpie]
- 2603: SQL Server 2025 (RTM) supported for CAS, primary, secondary; recommended compatibility level 160. [DOC S-qhlzdpie]
- 2603: SQL Server Native Client dependency removed; SMO updated to SMO 17. [DOC S-qhlzdpie]
- 2603: PKI certificates supported for site system-to-SQL Server communication. [DOC S-qhlzdpie]
- 2603: MP uses MISE for Entra token validation, requires internet access (login.microsoftonline.com, sts.windows.net) in system context when Entra-joined devices/users are supported (typically CMG); pure on-prem AD environments unaffected. [DOC S-qhlzdpie]
- 2603 deprecations: an internal service for device compliance checks deprecated October 2026 (co-managed with Compliance workload in Intune); Asset Intelligence sync point removed from UI; Software Update Health Troubleshooting Dashboard hidden. [DOC S-qhlzdpie]
- 2603 fixes include: CMPivot via AdminService no longer fails with 400 Bad Request (KustoParser); Run Script Boolean default True checkbox now matches value passed. [DOC S-ebuvm65r]
- KB38982839 (2026-08): security update for SMS Provider and AdminService for 2603 (and 2509/2503 with rollups); requires site reset; since August 2026 marked superseded by KB39398030. [DOC S-actyzzlw]

## Reference
| Version | Build | Available | Support end | Baseline |
|---|---|---|---|---|
| 2603 | 5.00.9146.1000 | 2026-05-05 | 2027-11-05 | No |
| 2509 | 5.00.9141 | 2025-11-12 | 2027-05-12 | Yes |
| 2503 | 5.00.9135 | 2025-03-31 | 2026-09-30 | No |
| 2409 | 5.00.9132 | 2024-12-04 | 2026-06-04 | No |

## Examples
A new lab site is installed from the 2509 baseline media, then updated in-console to 2603 (per S-qfo4gvbb baseline guidance).
