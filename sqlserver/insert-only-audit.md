---
topic: sqlserver/insert-only-audit
priority: P0
applies_to: "SQL Server 2016+ / Azure SQL (permission model)"
retrieved_utc: 2026-09-25
sources: [S468, S469, S470, S471]
status: partial
---

# Roles and permissions for an insert-only audit table

## Summary
- Permissions on tables are granular: INSERT, UPDATE, DELETE and SELECT are separate. Grant only INSERT to a custom role.
- DENY beats GRANT, including GRANTs inherited through roles. It doesn't apply to object owners or sysadmin members.
- Schema-level INSERT/UPDATE/DELETE apply to every object in the schema. Schema CONTROL implies all of them.
- Don't use `db_datawriter`: it grants add, delete and change on all user tables.

## Facts
- DENY stops a principal from getting a permission through group or role membership. It takes precedence over all permissions, except that it doesn't apply to object owners or `sysadmin` members. [DOC S468]
- A table-level DENY does not override a column-level GRANT. This is kept for backward compatibility, and Common Criteria compliance mode changes it. [DOC S468,S469]
- Schema permissions: INSERT, UPDATE, DELETE and SELECT on a schema are each implied by schema CONTROL and by the same-named database permission. ALTER is implied by ALTER ANY SCHEMA. [DOC S470]
- `db_datawriter` can add, delete or change data in all user tables. `db_denydatawriter` can't add, modify or delete in any user table. [DOC S471]
- Whether ownership chaining lets a stored procedure bypass a DENY on the audit table was not read in this pass. [UNK]

## Reference
| Grant | Effect | Source |
|---|---|---|
| `GRANT INSERT ON dbo.operation TO app_writer` | insert only on that table | S469 (object permissions) |
| `DENY UPDATE, DELETE ON dbo.operation TO app_writer` | blocks those permissions even if granted through another role | S468 |
| `GRANT INSERT ON SCHEMA::audit TO r` | insert on every object in the schema | S470 |

## Examples
```sql
CREATE ROLE app_audit_writer;
GRANT INSERT ON OBJECT::dbo.operation TO app_audit_writer;
DENY UPDATE, DELETE ON OBJECT::dbo.operation TO app_audit_writer;
ALTER ROLE app_audit_writer ADD MEMBER [CORP\jan.kowalski];
```
