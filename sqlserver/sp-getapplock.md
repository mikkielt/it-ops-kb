---
topic: sqlserver/sp-getapplock
priority: P0
applies_to: "SQL Server 2017+ (Windows/Linux), Azure SQL Database, Azure SQL MI"
retrieved_utc: 2026-09-26
sources: [S467]
status: complete
---

# `sp_getapplock` semantics

## Summary
- Named application lock. The resource is `nvarchar(255)`, compared as binary (case-sensitive), and scoped to the current database and `@DbPrincipal`.
- Modes: Shared, Update, IntentShared, IntentExclusive, Exclusive. Owner: `Transaction` (default; must be inside a transaction) or `Session`.
- `@LockTimeout` is in milliseconds. The default is `@@LOCK_TIMEOUT` (-1 = wait forever). 0 returns -1 at once if the lock isn't free.
- Return codes: 0 granted, 1 granted after waiting, -1 timeout, -2 cancelled, -3 deadlock victim, -999 parameter or call error.

## Facts
- `@Resource` is nvarchar(255). Longer values are truncated. It is hashed internally, compared as binary whatever the collation, and only the first 32 characters can be read back in plain text. [DOC S467]
- `@LockMode` is varchar(32) with no default: Shared, Update, IntentShared, IntentExclusive or Exclusive. [DOC S467]
- `@LockOwner` is `Transaction` (default) or `Session`. With Transaction, the call must be inside a transaction. [DOC S467]
- `@LockTimeout` is an int in ms. The default is the `@@LOCK_TIMEOUT` value; -1 means no timeout. 0 returns -1 immediately if the lock can't be granted. [DOC S467]
- `@DbPrincipal` defaults to `public`. The caller must be a member of that principal, dbo or db_owner. [DOC S467]
- Return values: 0, 1 success; -1 timeout; -2 cancelled; -3 deadlock victim; -999 validation or other error. [DOC S467]
- Transaction-owned locks are released at commit or rollback. Session-owned locks are released at logout. All locks are released at server shutdown. [DOC S467]
- The lock identity is database ID + `@DbPrincipal` + `@Resource`. The same name in another database is a different lock. [DOC S467]
- Calls are counted: `sp_releaseapplock` must be called as many times as `sp_getapplock`. [DOC S467]
- Repeated calls with different modes hold the union, usually the stronger mode, until final release. [DOC S467]
- A deadlock on an application lock doesn't roll back the requesting transaction. The caller must roll back on -3. [DOC S467]
- Permission: membership in the public role. [DOC S467]
- Inspect with `sys.dm_tran_locks` or `sp_lock`. [DOC S467]

## Reference
| Return | Meaning |
|---|---|
| 0 | granted synchronously |
| 1 | granted after wait |
| -1 | timed out |
| -2 | cancelled |
| -3 | deadlock victim |
| -999 | parameter/call error |

## Examples
```sql
DECLARE @rc INT;
EXEC @rc = sp_getapplock @Resource = N'app.sync.intune', @LockMode = 'Exclusive',
                         @LockOwner = 'Session', @LockTimeout = 0;
IF @rc < 0 THROW 50001, 'sync already running', 1;
-- ... work ...
EXEC sp_releaseapplock @Resource = N'app.sync.intune', @LockOwner = 'Session';
```
