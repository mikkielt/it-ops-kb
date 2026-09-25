---
topic: sqlserver/temporal-tables
priority: P0
applies_to: "SQL Server 2016-2025 (Windows and Linux), Azure SQL Database, Azure SQL Managed Instance"
retrieved_utc: 2026-09-24
sources: [S460, S461, S462, S463, S464, S465, S466]
status: complete
---

# System-versioned temporal tables: history retention

## Summary
- Temporal tables (`SYSTEM_VERSIONING = ON`) exist from SQL Server 2016. They are "Yes" in **every** edition in the 2017, 2019, 2022 and 2025 feature tables (Express included).
- `HISTORY_RETENTION_PERIOD` (per table: DAYS/WEEKS/MONTHS/YEARS/INFINITE) is documented for **SQL Server 2017 and later** (Windows and Linux), Azure SQL Database, Azure SQL MI and Fabric SQL database. No edition limit is stated.
- Cleanup is a background task. It runs only when the database flag `is_temporal_history_retention_enabled` is ON (default ON; set OFF after a point-in-time restore).
- Finite retention needs a clustered B-tree history index that starts with the period end column, or a clustered columnstore.

## Facts
- The retention article's monikerRange covers Azure SQL Database, SQL Server 2017 and later, SQL Server on Linux 2017 and later, Azure SQL MI, and Fabric SQL database. [DOC S460]
- `SYSTEM_VERSIONING = ON` in CREATE TABLE applies to SQL Server 2016 and later, Azure SQL Database and Azure SQL MI. [DOC S461]
- If you don't name a history table, it is `MSSQL_TemporalHistoryFor<object_id>` and is PAGE-compressed by default. [DOC S461]
- Edition tables list "Temporal" as Yes for Enterprise, Standard, Web, Express with Advanced Services and Express (2017, 2019, 2022). SQL Server 2025 lists "Temporal tables" as Yes for Enterprise, Standard and Express. [DOC S463,S464,S465,S466]
- In SQL Server 2025, Enterprise Developer and Evaluation editions have the Enterprise feature set. Standard Developer has the Standard feature set. [DOC S466]
- Retention is set with `HISTORY_RETENTION_PERIOD` at CREATE or through `ALTER TABLE ... SET (SYSTEM_VERSIONING = ON (HISTORY_RETENTION_PERIOD = n UNIT))`. Units: DAYS, WEEKS, MONTHS, YEARS. The default is INFINITE. [DOC S460]
- Setting SYSTEM_VERSIONING OFF loses the retention value. Turning it ON again without the parameter gives INFINITE. [DOC S460]
- The database flag `is_temporal_history_retention_enabled` defaults to ON. Enable it with `ALTER DATABASE ... SET TEMPORAL_HISTORY_RETENTION ON`. The engine sets it OFF after a point-in-time restore. With the flag OFF, retention can be configured but no automatic cleanup runs. [DOC S460]
- Rows are eligible when the period end value is older than the retention period. Cleanup is a scheduled background task. [DOC S460]
- Finite retention needs a clustered rowstore index whose first column is the period end column, or a clustered columnstore index. Otherwise configuration fails. That index can't be dropped while retention is finite. [DOC S460]
- Rowstore cleanup deletes in chunks of up to 10,000 rows, in no guaranteed order. Columnstore cleanup removes whole row groups (about 1 million rows each). [DOC S460]
- Catalog columns: `sys.databases.is_temporal_history_retention_enabled`; `sys.tables.history_retention_period` and `history_retention_period_unit_desc`. [DOC S460]
- `sys.sp_cleanup_temporal_history` removes all aged rows immediately in a single transaction. It works only for tables with finite retention. [DOC S462]

## Reference
| Platform | Temporal tables | HISTORY_RETENTION_PERIOD | Source |
|---|---|---|---|
| SQL Server 2016 | yes | not in monikerRange | S461,S460 |
| SQL Server 2017, 2019, 2022, 2025 (all editions) | yes | yes | S460,S463-S466 |
| SQL Server on Linux 2017+ | yes | yes | S460 |
| Azure SQL Database / MI | yes | yes | S460 |

## Examples
```sql
CREATE TABLE dbo.device_assignment (
  device_key  UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
  owner_upn   NVARCHAR(256) NULL,
  valid_from  DATETIME2 GENERATED ALWAYS AS ROW START NOT NULL,
  valid_to    DATETIME2 GENERATED ALWAYS AS ROW END NOT NULL,
  PERIOD FOR SYSTEM_TIME (valid_from, valid_to))
WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = dbo.device_assignment_history,
                              HISTORY_RETENTION_PERIOD = 400 DAYS));
```
