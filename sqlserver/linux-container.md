---
topic: sqlserver/linux-container
priority: P0
applies_to: "mcr.microsoft.com/mssql/server (tag list retrieved 2026-09-24)"
retrieved_utc: 2026-09-26
sources: [S460, S466, S473, S474, S475, S476, S477, S478]
status: partial
files: [sqlserver/mssql-server-tags.json]
---

# SQL Server Linux container image for CI

## Summary
- Image `mcr.microsoft.com/mssql/server:<tag>`. Tags: `<year>-latest`, `<year>-CU<n>[-GDR<n>]-ubuntu-<22.04|24.04>`, `latest`. The full list is at `https://mcr.microsoft.com/v2/mssql/server/tags/list` (saved: `mssql-server-tags.json`, 284 tags).
- Required env: `ACCEPT_EULA=Y` and `MSSQL_SA_PASSWORD`. `MSSQL_PID` selects the edition. The quickstart image runs **Developer** by default, which is free and non-production.
- SQL Server 2025 renames Developer: `MSSQL_PID` values are `EnterpriseDeveloper` and `StandardDeveloper`. 2022 and earlier use `Developer`.
- Microsoft docs give no digest-pinning policy (see Gaps).

## Facts
- Docs examples use `2017-latest`, `2019-latest`, `2022-latest` and `2025-latest`. To pin, pull a specific tag such as `2019-CU18-ubuntu-20.04`. [DOC S473,S477]
- All tags can be listed at `https://mcr.microsoft.com/v2/mssql/server/tags/list`. [DOC S473]
- Tag list on 2026-09-24: 284 tags. Highest CUs: 2022-CU27, 2025-CU9 (`2025-CU9-ubuntu-22.04`, `2025-CU9-ubuntu-24.04`). Moving tags: `latest`, `latest-ubuntu`, `2017-latest`, `2017-latest-ubuntu`, `2019-latest`, `2022-latest`, `2025-latest`. [DOC S478]
- `ACCEPT_EULA` is required for the image. `MSSQL_SA_PASSWORD` sets the sa password; `SA_PASSWORD` is deprecated. [DOC S474]
- The quickstart creates a Developer edition container by default. `MSSQL_PID` "specifies the freely licensed Developer Edition of SQL Server for non-production use". [DOC S477,S474]
- MSSQL_PID for 2022 and earlier: Evaluation, Developer, Express, Web, Standard, Enterprise (legacy CAL, max 20 cores), EnterpriseCore, or a product key. [DOC S476]
- MSSQL_PID for 2025 and later: Evaluation, Express, StandardDeveloper, Standard, EnterpriseDeveloper, Enterprise (legacy), EnterpriseCore, or a product key. [DOC S475]
- Production use needs a valid licence. With `ACCEPT_EULA=Y` and a production `MSSQL_PID` you state that you have one. The Developer image can run production editions. [DOC S473]
- Other env vars: `MSSQL_TCP_PORT` (default 1433), `MSSQL_MEMORY_LIMIT_MB` (default 80% of RAM), `MSSQL_COLLATION`, `MSSQL_AGENT_ENABLED` (default off). [DOC S474]
- Developer editions have the Enterprise (or Standard) feature set, so temporal retention works in CI. [DER S466,S460]
- Microsoft docs don't give a digest (`@sha256:`) pinning policy for mssql/server. [UNK]

## Reference
Artifact: `sqlserver/mssql-server-tags.json` (sha256 `058736f6cdb5ab26a766cb3a491e785c8f6f26c098cec38b74e7276d27bc4c83`). It is a live endpoint, so re-fetching gives a different hash as tags are added.

## Examples
```bash
docker run -e ACCEPT_EULA=Y -e MSSQL_PID=EnterpriseDeveloper -e "MSSQL_SA_PASSWORD=$CI_SA_PASSWORD" \
  -p 1433:1433 -d mcr.microsoft.com/mssql/server:2025-CU9-ubuntu-24.04
```
