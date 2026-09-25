---
topic: arch/sql-auth-containers
priority: P1
applies_to: "SQL Server 2022/2025, ODBC Driver 18 for SQL Server, Azure Arc-enabled SQL Server (docs current 2026-09-24)"
retrieved_utc: 2026-09-24
sources: [S1605, S1206, S1207, S1610]
status: complete
---

# SQL Server authentication from containers

## Summary
- Two officially supported paths from a container to on-prem SQL Server: (1) Windows/Kerberos integrated auth via ODBC Driver 18 on Linux, using `kinit`/keytab + `Trusted_Connection=yes`; (2) Microsoft Entra authentication, but only if the SQL Server instance is Azure-Arc-enabled (extends `auth/sql-authz.md`, `sqlserver/linux-container.md`). [DOC S1605, S1206]
- `msodbcsql18` supports Entra auth modes including `Authentication=ActiveDirectoryMsi` (managed identity) and a distinct `Authentication=Active Directory Workload Identity` mode that reads the workload identity's client ID from the `User Id`/`UID` connection parameter. [DOC S1610]
- A SQL login (username/password) remains the fallback when neither Kerberos nor Entra auth is feasible for a given container/host combination — always available, but outside an AD/Entra-group authorization model. [DER from general SQL Server auth model already in `sqlserver/`]

## Facts
- ODBC Driver 18 on Linux/macOS: enable with `Trusted_Connection=yes` in the connection string (or DSN); the client must already hold a Kerberos TGT (via `kinit` or PAM) before connecting, and the driver does not renew credentials — a cron/script must refresh them. [DOC S1605] (fully detailed in `arch/kerberos-linux-containers.md`)
- On Kerberos failure, the Linux/macOS ODBC driver does not fall back to NTLM. [DOC S1605]
- Entra authentication for on-premises SQL Server (2022/2025) requires the instance to be registered with **Azure Arc**; SQL Server 2025 (17.x) additionally offers a "primary managed identity" concept for credential-free inbound/outbound auth, configured through the latest Azure Extension for SQL Server rather than the classic Arc Entra-auth portal steps. [DOC S1206] (already in `auth/sql-authz.md`)
- Entra groups are supported for SQL authorization the same way AD groups are for Windows Authentication logins — a group becomes a login/user and members inherit its permissions; group membership changes apply on next connection (new token), not mid-session. [DOC S1207] (already in `auth/sql-authz.md`)
- `msodbcsql18` (and the JDBC/ADO.NET drivers) support `Authentication=ActiveDirectoryMsi` for both system-assigned managed identity (no UID needed) and user-assigned managed identity (`UID=<clientOrObjectId>`). [DOC S1610]
- A separate, newer `Authentication=Active Directory Workload Identity` mode exists distinct from `ActiveDirectoryMsi`; it uses the `User Id` connection-string value as the workload identity's client ID rather than a managed-identity object ID. [DOC S1610]
- These Entra auth modes (`ActiveDirectoryMsi`, workload identity) are Azure-managed-identity/workload-identity constructs; against an on-prem SQL Server they only work once that instance is Arc-enabled per S1206 — an on-prem, non-Arc SQL Server has no managed-identity or workload-identity endpoint to authenticate against. [DER S1206, S1610]
- No doc found describing `ActiveDirectoryDefault` behavior specifically for the Linux/msodbcsql18 driver against on-prem/Arc SQL Server (search results centered on Azure SQL Database/Managed Instance). [UNK]

## Reference
| Path | Requires | SQL Server must be Arc-enabled? | Source |
|---|---|---|---|
| Kerberos (kinit/keytab, Windows Auth login) | Client Kerberos setup + `Trusted_Connection=yes`; SQL login mapped from AD group | No | DOC S1605 |
| Entra auth (`ActiveDirectoryMsi` / workload identity) | Managed identity or federated workload identity + Arc-enabled SQL Server | Yes | DOC S1206, S1610 |
| SQL login | Username + password | No | DER |

## Examples
```
# Kerberos (Linux container, keytab already kinit'd)
Driver={ODBC Driver 18 for SQL Server};Server=PL-SRV-0042.corp.example.com;Encrypt=yes;Trusted_Connection=yes

# Entra workload identity (Arc-enabled SQL Server only)
Server=PL-SRV-0042.corp.example.com;Authentication=Active Directory Workload Identity;Encrypt=yes;User Id=<workload-identity-client-id>;Database=example
```
