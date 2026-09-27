---
topic: auth/sql-authz
priority: P0
applies_to: "SQL Server 2022/2025, extends sqlserver/"
retrieved_utc: 2026-09-27
sources: [S1206, S1207, S-jyoprgy5, S1375, S-2vmabspl]
status: complete
---

# SQL Server authorization: AD group logins, Entra auth on-prem

## Summary
- AD group logins map to database users the same way regardless of ConfigMgr; membership changes take effect the next time the principal connects (a new login token), not mid-session, because SQL Server evaluates Windows group membership from the access token at connection time.
- SQL Server 2022 and later support Microsoft Entra authentication on-premises, usually through Azure Arc; on Windows it can also be set up **without Arc** (manual certificate, registry and app-registration configuration). SQL Server 2025's "primary managed identity" model does require Arc and a recent Azure Extension for SQL Server. Entra groups can be created as SQL Server logins.

## Facts
- Managed identity with Entra authentication for SQL Server enabled by Azure Arc applies to SQL Server 2025 (17.x) and later on Windows; prerequisites are an Arc-connected SQL Server and the latest Azure Extension for SQL Server. The primary managed identity is enabled in the portal (Microsoft Entra ID and Purview page) or manually via registry, and needs the Graph application permissions `User.Read.All`, `GroupMember.Read.All` and `Application.Read.All`. [DOC S1206]
- A Microsoft Entra group can be created as a SQL Server login (`CREATE LOGIN [group] FROM EXTERNAL PROVIDER`) and as a database user (`FROM LOGIN` or as a contained user `FROM EXTERNAL PROVIDER`). [DOC S-jyoprgy5]
- To connect SQL Server to Azure Arc, the Microsoft Entra account needs membership in the Azure Connected Machine Onboarding group or the Contributor role, plus the Azure Connected Machine Resource Administrator and Reader roles, in the resource group (onboarding the host, not the database permission model). [DOC S1207]
- QA13 answer (corrected 2026-09-27): **no**, Azure Arc is not strictly required: the Entra-auth overview describes setup with Arc and also on Windows without Arc (manual certificates, registry, app registration); Arc is required for the SQL Server 2025 primary-managed-identity setup. Entra groups can be SQL Server logins. [DOC S1207, S1206, S-jyoprgy5]
- Windows-Authentication AD group login membership changes: an authenticated connection caches the login's identity, including its Windows group membership, for as long as it lasts; a group change applies only after the login signs out and in again, and `KILL` forces the reconnect. [DOC S1375] SQL Server learns Windows group membership from the token at connection time and gets no updates afterwards. [DOC S-2vmabspl]

## Reference
| Question | Answer | Source |
|---|---|---|
| QA13: Arc required for on-prem Entra auth? | No on Windows (manual setup without Arc exists); yes for the SQL Server 2025 managed-identity setup | S1207, S1206 |
| QA13: groups supported? | Yes, Entra group as login/user | S-jyoprgy5 |
| When do AD/Entra group changes apply to a SQL login? | Next connection (new access token), not mid-session | DOC (S1375, S-2vmabspl) |

## Examples
- `gmsa-sync` connects to SQL as a Windows Authentication login mapped from an AD group; if the gMSA's group memberships change, it takes effect on the account's next connection, i.e. the next scheduled sync job run.
