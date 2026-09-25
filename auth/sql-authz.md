---
topic: auth/sql-authz
priority: P0
applies_to: "SQL Server 2022/2025, extends kb/sqlserver/"
retrieved_utc: 2026-09-24
sources: [S1206, S1207]
status: partial
---

# SQL Server authorization: AD group logins, Entra auth on-prem

## Summary
- AD group logins map to database users the same way regardless of ConfigMgr; membership changes take effect the next time the principal connects (a new login token), not mid-session, because SQL Server evaluates Windows group membership from the access token at connection time.
- SQL Server 2025 supports Microsoft Entra authentication on-premises, but **requires the instance to be Arc-enabled** and (for the newer "primary managed identity" model) a recent Azure Extension for SQL Server; group support exists through the same Entra security groups used elsewhere.

## Facts
- Microsoft Entra authentication for on-premises SQL Server needs the instance registered with Azure Arc; SQL Server 2025 (17.x) adds a "primary managed identity" concept enabling credential-free inbound and outbound authentication once Arc-enabled, configured via the latest Azure Extension for SQL Server (not via the same Azure portal steps used for the general Arc Entra-auth setup, which explicitly do not apply to 17.x). [DOC S1206]
- The general Entra-authentication-for-SQL-Server overview describes the feature working with Entra security groups for authorization the same way Windows AD groups do for classic Windows Authentication logins — a group is created as a login/user in SQL Server and members inherit its permissions. [DOC S1207]
- Requirement for the connecting Entra identity to reach Azure Arc-enablement: membership in the "Azure Connected Machine Onboarding" group, or Contributor / Azure Connected Machine Resource Administrator role on the target resource group (this is about onboarding the SQL Server host to Arc, not the ongoing DB permission model). [DOC S1206]
- QA13 answer: **yes**, Azure Arc is required for Entra authentication on an on-premises SQL Server 2022/2025 instance, and Entra groups are supported for authorization. [DOC S1206,S1207]
- Windows-Authentication AD group login membership changes: SQL Server reads the Windows access token's group SIDs at connection/login time; a group change is honoured on the *next* connection (new login), not for an already-open session — this matches general Windows/Kerberos token behaviour and is consistent with, but not independently re-derived beyond, general SQL Server Windows Authentication documentation already implied by `sqlserver/` topic files. [DER from Windows Authentication token model]

## Reference
| Question | Answer | Source |
|---|---|---|
| QA13: Arc required for on-prem Entra auth? | Yes | S1206 |
| QA13: groups supported? | Yes, same model as AD groups | S1206,S1207 |
| When do AD/Entra group changes apply to a SQL login? | Next connection (new access token), not mid-session | DER |

## Examples
- `gmsa-sync` connects to SQL as a Windows Authentication login mapped from an AD group; if the gMSA's group memberships change, it takes effect on the account's next connection, i.e. the next scheduled sync job run.
