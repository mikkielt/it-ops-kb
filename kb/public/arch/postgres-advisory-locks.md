---
topic: arch/postgres-advisory-locks
priority: P3
applies_to: "PostgreSQL 18 documentation; PgBouncer features page (site listing 1.26.0)"
retrieved_utc: 2026-10-11
sources: [S-xf26uevo, S-utkuhqw3, S-5oeurmkp, S-o45hawqq, S-zwhssqbz]
status: complete
---

# PostgreSQL advisory locks as single-writer invariants

## Summary
PostgreSQL advisory locks are application-defined locks on a number the application picks; the server
tracks and releases them but never enforces their use. A session-level lock taken with
`pg_try_advisory_lock` is held until it is released or the session ends, which makes it a usable
"one writer at a time" guard that disappears when its holder dies. It is tied to one server and one
session, so it does not survive a failover and does not work through a transaction-pooling
PgBouncer. The SQL Server counterpart is `sp_getapplock` (`sqlserver/sp-getapplock.md`); the idea of
a database-layer single-writer guard for a sync job is in `arch/twelve-factor-readiness.md`.

## Facts
- Advisory locks have an application-defined meaning and are "advisory" because the server does not
  enforce their use. PostgreSQL's page says they are faster than a flag stored in a table, avoid table
  bloat and are cleaned up automatically by the server at the end of the session. [DOC S-xf26uevo]
- A session-level advisory lock is held until explicitly released or the session ends. It ignores
  transaction semantics: a lock taken in a transaction that later rolls back is still held, and an
  unlock stays effective even if the calling transaction fails afterwards. [DOC S-xf26uevo]
- The same session may acquire the same lock several times; each completed request needs its own
  unlock before the lock is actually released. If a session already holds a lock, further requests
  by it succeed even while other sessions are waiting, whether the earlier hold and the new request
  are session-level or transaction-level. [DOC S-xf26uevo]
- A transaction-level advisory lock is released automatically at the end of the transaction and has no
  explicit unlock. Session-level and transaction-level requests for the same identifier block each
  other. [DOC S-xf26uevo]
- The function table (PostgreSQL 18, Table 9.109) has, for a `bigint` key or a pair of `integer`
  keys: `pg_advisory_lock` (waits), `pg_try_advisory_lock` (returns false without waiting),
  `pg_advisory_unlock`, `pg_advisory_xact_lock`, `pg_try_advisory_xact_lock`, and the `_shared`
  variants of each; `pg_advisory_unlock_all()` releases every session-level lock of the session.
  [DOC S-utkuhqw3]
- `pg_try_advisory_lock` either takes the exclusive session-level lock immediately and returns `true`,
  or returns `false` if it cannot get it at once. `pg_advisory_unlock` returns `false` and raises an SQL
  warning when the lock was not held. [DOC S-utkuhqw3]
- `pg_advisory_unlock_all()` is invoked implicitly at session end, even if the client disconnects
  ungracefully. [DOC S-utkuhqw3]
- In `pg_locks` an advisory lock has `locktype = 'advisory'`. A `bigint` key shows its high half in
  `classid`, low half in `objid` and `objsubid = 1`; a two-integer key shows both halves with
  `objsubid = 2`. Advisory locks are local to each database, so the `database` column is meaningful;
  `pid` names the holding or waiting server process and `granted` tells held from awaited.
  [DOC S-5oeurmkp]
- Advisory locks and regular locks share one shared-memory pool sized by `max_locks_per_transaction`
  and `max_connections`; exhausting it means the server cannot grant any lock, which caps advisory
  locks at "typically in the tens to hundreds of thousands". [DOC S-xf26uevo]
- A locking function inside a query with `LIMIT` can lock rows the application did not expect,
  because `LIMIT` is not guaranteed to apply before the function runs; such locks stay held until the
  session ends and remain visible in `pg_locks`. The page's safe form puts the `LIMIT` in a subquery.
  [DOC S-xf26uevo]
- Advisory locks work in recovery (hot standby) but are never WAL-logged: a lock taken on the primary
  does not appear on the standby, and a lock "relate only to the server on which they are acquired".
  [DOC S-o45hawqq]
- PgBouncer's feature map lists "Session-level advisory locks" as supported in session pooling and
  "Never" in transaction pooling; the page says transaction pooling "breaks client expectations of
  the server by design" and can be used only if the application avoids such features. [DOC S-zwhssqbz]
- Single-writer guard at startup, derived: connect with a dedicated session (not a pooled or
  transaction-pooled connection), run `SELECT pg_try_advisory_lock(<key>)`, and continue as the writer
  only if it returns `true`; on `false` another session holds the key, so exit or retry. Use the
  session-level form and keep that connection open for the life of the process, because the
  transaction-level form is released at commit. [DER S-utkuhqw3, S-xf26uevo: semantics of
  `pg_try_advisory_lock` versus `pg_try_advisory_xact_lock`]
- Failure behaviour, derived: a crashed or disconnected holder releases the lock at session end with
  no cleanup job, unlike a lock row in a table. The reverse risk is a connection that is silently
  replaced (driver reconnect, pooler) or a failover to another server: the process then no longer
  holds the lock, so treat loss of that connection as fatal or re-take and re-check the lock.
  [DER S-utkuhqw3, S-o45hawqq, S-zwhssqbz: release at session end, per-server scope, no pooled session]
- Scope, derived: the lock is advisory, so every writer code path must take the same key, and the
  database will not stop a writer that skips it. The key space is per database and shared with every
  other application in that database, so a fixed two-integer key (application id, resource id) avoids
  accidental collisions. [DER S-xf26uevo, S-5oeurmkp: server does not enforce; keys are local to each
  database and their meaning is up to the user]

## Reference
| Need | Call | Waits | Released |
|---|---|---|---|
| Single-writer guard | `pg_try_advisory_lock(key)` | no | `pg_advisory_unlock`, `pg_advisory_unlock_all`, session end |
| Queue behind holder | `pg_advisory_lock(key)` | yes | same |
| Per-transaction mutex | `pg_advisory_xact_lock(key)` / `pg_try_advisory_xact_lock(key)` | yes / no | end of transaction |
| Read-side holders | `_shared` variants | as above | as above |
| Who holds it | `pg_locks` where `locktype = 'advisory'` | n/a | n/a |

Key forms: one `bigint`, or two `integer` values. Docs pinned: PostgreSQL 18 (`/docs/18/`).

## Examples
- SNIPPET: take a session-level lock as the single writer, then list advisory locks; context: PostgreSQL 18, one dedicated session; checked: no [DER S-utkuhqw3, S-5oeurmkp: `pg_try_advisory_lock`, `pg_locks`]
```sql
-- key is an application-chosen constant (here two integers: app id 42, resource id 1)
SELECT pg_try_advisory_lock(42, 1) AS i_am_the_writer;

-- who holds advisory locks in this database
SELECT pid, classid, objid, objsubid, mode, granted
FROM pg_locks
WHERE locktype = 'advisory'
  AND database = (SELECT oid FROM pg_database WHERE datname = current_database());
```
