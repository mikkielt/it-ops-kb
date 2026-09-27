---
topic: arch/sql-auth-containers
priority: P1
applies_to: "SQL Server 2022/2025, ODBC Driver 18 for SQL Server, Azure Arc-enabled SQL Server (docs current 2026-09-24)"
retrieved_utc: 2026-09-26
sources: [S1605, S1206, S1207, S1610, S-jyoprgy5, S-z74feu7u]
status: complete
---

# SQL Server authentication from containers

## Summary
- Two officially supported paths from a container to on-prem SQL Server: (1) Windows/Kerberos integrated auth via ODBC Driver 18 on Linux, using `kinit`/keytab + `Trusted_Connection=yes`; (2) Microsoft Entra authentication, configured on the SQL Server 2022+ instance through Azure Arc, or for SQL Server on Windows through a documented manual setup without Arc (extends `auth/sql-authz.md`, `sqlserver/linux-container.md`). [DOC S1605, S1207]
- `msodbcsql18` supports Entra auth modes including `Authentication=ActiveDirectoryMsi` (managed identity) and `ActiveDirectoryServicePrincipal`; its keyword list has no workload-identity mode. [DOC S1610]
- `Authentication=Active Directory Workload Identity` is a Microsoft.Data.SqlClient (ADO.NET) mode, 5.2.0+, that takes the client ID from `User Id` and otherwise from `AZURE_CLIENT_ID`, with `AZURE_TENANT_ID` and `AZURE_FEDERATED_TOKEN_FILE`. [DOC S-z74feu7u]
- A SQL login (username/password) remains the fallback when neither Kerberos nor Entra auth is feasible for a given container/host combination — always available, but outside an AD/Entra-group authorization model. [DER from general SQL Server auth model already in `sqlserver/`]

## Facts
- ODBC Driver 18 on Linux/macOS: enable with `Trusted_Connection=yes` in the connection string (or DSN); the client must already hold a Kerberos TGT (via `kinit` or PAM) before connecting, and the driver does not renew credentials — a cron/script must refresh them. [DOC S1605] (fully detailed in `arch/kerberos-linux-containers.md`)
- On Kerberos failure, the Linux/macOS ODBC driver does not fall back to NTLM. [DOC S1605]
- Entra authentication for SQL Server 2022+ on-premises (Windows and Linux) is set up by registering the instance with **Azure Arc**; for SQL Server on Windows a manual setup without Arc (certificates, registry settings, app registration) is also documented; failover cluster instances are not supported. [DOC S1207]
- SQL Server 2025 (17.x) on Windows can use a **primary managed identity** for Entra authentication; prerequisites are an Arc connection and the latest Azure Extension for SQL Server, and the identity needs the Graph application permissions `User.Read.All`, `GroupMember.Read.All` and `Application.Read.All`. [DOC S1206]
- A Microsoft Entra group can be made a SQL Server login (`CREATE LOGIN [group] FROM EXTERNAL PROVIDER`) and a database user (`CREATE USER [group] FROM LOGIN [group]`, or a contained user `FROM EXTERNAL PROVIDER`). [DOC S-jyoprgy5] (see `auth/sql-authz.md`)
- Entra group membership changes taking effect only on the next connection (new token), not mid-session. [UNK: not in S1207 as re-read 2026-09-27]
- `msodbcsql18` supports `Authentication=ActiveDirectoryMsi` for both system-assigned managed identity (no UID needed) and user-assigned managed identity (`UID` = client ID on Azure App Service or Azure Container Instance, otherwise object ID); ODBC 18.3+ supports it on Azure Arc. [DOC S1610]
- SqlClient's `Active Directory Workload Identity` is distinct from its `Active Directory Managed Identity`: it uses a federated user-assigned managed identity from environments enabled for workload identity, and only the client ID can be overridden in the connection string. [DOC S-z74feu7u]
- These Entra auth modes (`ActiveDirectoryMsi`, workload identity) only obtain a token on the client side; against an on-prem SQL Server they work once that instance has Entra authentication configured (via Arc, or the manual non-Arc setup on Windows) and a login exists for the identity. [DER S1207, S1610: the driver acquires a Microsoft Entra token; the server side must accept Entra logins]
- No doc found describing `ActiveDirectoryDefault` behavior specifically for the Linux/msodbcsql18 driver against on-prem/Arc SQL Server (search results centered on Azure SQL Database/Managed Instance). [UNK]

## Reference
| Path | Requires | SQL Server must be Arc-enabled? | Source |
|---|---|---|---|
| Kerberos (kinit/keytab, Windows Auth login) | Client Kerberos setup + `Trusted_Connection=yes`; SQL login mapped from AD group | No | DOC S1605 |
| Entra auth (`ActiveDirectoryMsi` / SqlClient workload identity) | Managed identity or federated workload identity + SQL Server with Entra auth configured | Arc, or the manual non-Arc setup (Windows only) | DOC S1207, S1610, S-z74feu7u |
| SQL login | Username + password | No | DER |

## Examples
```
# Kerberos (Linux container, keytab already kinit'd)
Driver={ODBC Driver 18 for SQL Server};Server=PL-SRV-0042.corp.example.com;Encrypt=yes;Trusted_Connection=yes

# Entra workload identity (Microsoft.Data.SqlClient 5.2+; SQL Server with Entra auth configured)
Server=PL-SRV-0042.corp.example.com;Authentication=Active Directory Workload Identity;Encrypt=yes;User Id=<workload-identity-client-id>;Database=example
```
