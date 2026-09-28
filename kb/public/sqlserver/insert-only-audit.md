---
topic: sqlserver/insert-only-audit
priority: P0
applies_to: "SQL Server 2016+ / Azure SQL (permission model)"
retrieved_utc: 2026-09-28
sources: [S468, S469, S470, S471, S-deeqomz3, S-qkecle6c, S-yjcvd3to]
status: complete
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
- Table permissions that can be granted per object are DELETE, INSERT, REFERENCES, SELECT and UPDATE, so INSERT can be granted on one table alone; on a column only SELECT, REFERENCES, UPDATE and UNMASK can be granted; INSERT on an object is implied by CONTROL on it and by INSERT on its schema. [DOC S-deeqomz3]
- In an ownership chain, SQL Server compares the owner of each referenced object with the owner of the calling object; when they match, it doesn't evaluate permissions on the referenced object (an unbroken chain). [DOC S-qkecle6c]
- The current tutorial shows the effect: a user with no rights on the base tables reads them through a stored procedure whose schema owner also owns the tables. [DOC S-yjcvd3to]
- So a DENY on the audit table does not stop writes made through a procedure owned by the table's owner: the table's permissions are never evaluated in that chain. The DENY holds for direct access, and for a procedure owned by someone else (a broken chain). [DER S-qkecle6c, S-yjcvd3to: unbroken chains skip permission checks on the referenced object]

## Reference
| Grant | Effect | Source |
|---|---|---|
| `GRANT INSERT ON dbo.operation TO app_writer` | INSERT on that table only; INSERT is an object permission separate from UPDATE, DELETE and SELECT | S-deeqomz3 (GRANT object permissions) |
| `DENY UPDATE, DELETE ON dbo.operation TO app_writer` | blocks those permissions even if granted through another role | S468 |
| `GRANT INSERT ON SCHEMA::audit TO r` | insert on every object in the schema | S470 |

## Examples
- SNIPPET: create an insert-only role for an audit table by granting INSERT and denying UPDATE/DELETE; context: SQL Server 2016+ / Azure SQL; checked: no [DOC S468, S470: DENY takes precedence over a granted permission; INSERT/UPDATE/DELETE are separate object permissions]
```sql
CREATE ROLE app_audit_writer;
GRANT INSERT ON OBJECT::dbo.operation TO app_audit_writer;
DENY UPDATE, DELETE ON OBJECT::dbo.operation TO app_audit_writer;
ALTER ROLE app_audit_writer ADD MEMBER [CORP\jan.kowalski];
```
