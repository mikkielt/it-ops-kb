---
topic: python/alembic-migrations
priority: P3
applies_to: "Alembic 1.20.0 (tag rel_1_20_0) with PostgreSQL 18 documentation; SQLAlchemy async engine"
retrieved_utc: 2026-10-11
sources: [S-2ggil3io, S-772ppm55, S-7zk6ggvu, S-plfldpyl, S-b6msep5g, S-zcvw2nun, S-h2z7tktj, S-4k3e652e, S-hqy2uu3t, S-qh5ieidx, S-xf26uevo, S-7losxrcq, S-5mw7raax]
status: partial
---

# Alembic migrations: revision files, async env, transactional DDL, expand-and-contract

## Summary
Alembic is the migration tool for SQLAlchemy: each revision is a Python file with `upgrade()` and
`downgrade()`, the database remembers its position in an `alembic_version` table, and `alembic upgrade
head` walks the revision graph. The `async` env template runs the same migrations through a
SQLAlchemy async engine. On PostgreSQL, Alembic wraps the whole run in one transaction by default
(transactional DDL), which can be narrowed to one transaction per revision, and statements that must
run outside a transaction block (such as `CREATE INDEX CONCURRENTLY`) need an `autocommit_block`.
Alembic's docs do not define "expand and contract"; the name comes from a community write-up, and the
steps in this article are derived from PostgreSQL's documented lock levels, not taken from Alembic.

## Facts
- `alembic list_templates` shows the env templates `generic`, `pyproject` (added in Alembic 1.16.0),
  `async` and `multidb`; `alembic init --template <name> <dir>` creates the migrations directory with
  `alembic.ini`, `env.py`, `script.py.mako` and a `versions/` directory. Documented at rel_1_20_0.
  [DOC S-2ggil3io]
- `alembic init -t async <dir>` (templates `async` or `pyproject_async`) bootstraps an env for an async
  DBAPI such as asyncpg. Alembic itself has no async API: the recipe builds a SQLAlchemy async engine
  with `async_engine_from_config(..., poolclass=pool.NullPool)`, opens `connectable.connect()` and calls
  `await connection.run_sync(do_run_migrations)`, then `asyncio.run(...)` from
  `run_migrations_online()`. The page calls SQLAlchemy's asyncio support experimental since 1.4.
  [DOC S-7zk6ggvu]
- `alembic upgrade head` first checks for the `alembic_version` table (creates it if missing), reads
  the current version, computes the path to the target and calls each file's `upgrade()`. Revision ids
  may be partial prefixes (`ae1`) and relative (`upgrade +2`, `downgrade -1`, `ae10+2`).
  [DOC S-2ggil3io]
- `alembic current` prints the database's revision and marks it `(head)` only when it equals the head
  revision; `alembic history` (with `-r start:end`, `--verbose`) and `alembic heads` show the revision
  graph without changing the database. [DOC S-2ggil3io]
- Revisions form a directed acyclic graph. When two branches exist there are multiple heads, the
  `alembic_version` table then holds one row per head, `alembic merge` writes a merge revision that
  joins them, and `alembic upgrade heads` upgrades every head. [DOC S-b6msep5g]
- `--sql` on any `upgrade` or `downgrade` ("offline mode") writes the SQL script to stdout instead of
  running it, with `BEGIN;`/`COMMIT;` around it on PostgreSQL. The `start:end` revision syntax is
  allowed only in offline mode; a migration that reads rows into memory with `SELECT` does not work
  there. [DOC S-plfldpyl]
- On PostgreSQL the implementation class sets `transactional_ddl = True`, so Alembic assumes
  transactional DDL for PostgreSQL migrations. [CODE S-4k3e652e: alembic/ddl/postgresql.py#PostgresqlImpl]
- The `transactional_ddl` argument of `context.configure()` forces transactional DDL on or off and
  otherwise defaults to whether the dialect supports it; `context.begin_transaction()` then wraps the
  run in one real transaction online, or emits `BEGIN`/`COMMIT` offline.
  [CODE S-h2z7tktj: alembic/runtime/environment.py#EnvironmentContext.configure]
- `transaction_per_migration` (default `False`) in `context.configure()` nests each migration script
  in its own transaction instead of one transaction around the full series.
  [CODE S-h2z7tktj: alembic/runtime/environment.py#EnvironmentContext.configure]
- `op.get_context().autocommit_block()` runs statements outside any transaction block using the
  SQLAlchemy `AUTOCOMMIT` isolation level; the docstring warns that the transaction preceding the block
  is unconditionally committed and recommends `transaction_per_migration` for apps that use such
  blocks. [CODE S-zcvw2nun: alembic/runtime/migration.py#MigrationContext.autocommit_block]
- Autogenerate (`alembic revision --autogenerate`) is documented as "not intended to be perfect": its
  output is a candidate to review. It detects table and column additions and removals, nullable
  changes and basic index, named unique and foreign-key changes; type comparison is on by default,
  server-default comparison is off by default; table and column renames come out as drop plus add,
  and anonymous constraints are not detected. [DOC S-772ppm55]
- `alembic check` (added in 1.9.0) runs the autogenerate comparison without writing a file and returns
  an error code if a new revision would contain operations, so it can run in CI to catch a model
  change that has no migration; it has the same detection limits as autogenerate. [DOC S-772ppm55]
- The Alembic docs at rel_1_20_0 (tutorial, autogenerate, cookbook, offline, branches, operations,
  batch, naming, front, index) contain no page or term "expand and contract" and no zero-downtime
  migration guidance. [UNK]
- "Parallel change, also known as expand and contract" is a pattern of three phases, expand, migrate
  and contract, for backward-incompatible changes; the page says most database refactorings follow it,
  with the migrate phase as the transition period between old and new schema. This is a general
  engineering write-up, not a PostgreSQL or Alembic definition. [COMMUNITY S-5mw7raax]
- PostgreSQL 18 `ALTER TABLE` takes an `ACCESS EXCLUSIVE` lock unless a subform says otherwise, and that
  mode conflicts with every other lock mode, including the `ACCESS SHARE` lock of a plain `SELECT`.
  `ADD COLUMN` with a non-volatile default (or none) needs no table rewrite, the default is kept in
  metadata; a volatile default, stored generated column, identity column or constrained domain type
  rewrites the table and its indexes. The 11.0 release notes list the no-rewrite `ADD COLUMN` default.
  [DOC S-hqy2uu3t, S-xf26uevo, S-7losxrcq]
- PostgreSQL 18 `ADD CONSTRAINT ... NOT VALID` (foreign key, CHECK, not-null) skips the table scan and
  still enforces the constraint for new writes; `VALIDATE CONSTRAINT` then scans the table under a
  `SHARE UPDATE EXCLUSIVE` lock that does not lock out concurrent updates. `SET NOT NULL` scans the
  table unless a valid CHECK constraint already proves no NULL exists. [DOC S-hqy2uu3t]
- PostgreSQL 18 `CREATE INDEX CONCURRENTLY` does not lock out writes but makes two table scans and
  waits for older transactions; it cannot run inside a transaction block, and a failed build leaves
  an `INVALID` index that must be dropped and retried. `DROP COLUMN` only hides the column and
  reclaims no space; `RENAME` has no effect on stored data. [DOC S-qh5ieidx, S-hqy2uu3t]
- Expand-and-contract in Alembic, derived: (1) an expand revision adds only additive objects (new
  nullable column, new table, index via `autocommit_block` with `CREATE INDEX CONCURRENTLY`,
  constraint `NOT VALID`); (2) application code that writes both shapes ships and a backfill runs;
  (3) a later revision runs `VALIDATE CONSTRAINT` or `SET NOT NULL`; (4) a contract revision drops the
  old column or table only after no deployed code reads it. Autogenerate output is a starting point
  only, because renames appear as drop plus add and would lose data if applied unreviewed.
  [DER S-hqy2uu3t, S-qh5ieidx, S-zcvw2nun, S-772ppm55, S-5mw7raax: lock levels and
  non-transactional statements from the PostgreSQL pages, `autocommit_block` from the Alembic source,
  rename behaviour from the autogenerate page, phase names from the community write-up]

## Reference
| Item | Value |
|---|---|
| Version table | `alembic_version` (one row per head) |
| Apply / revert | `alembic upgrade head`, `alembic downgrade -1` |
| Position | `alembic current`, `alembic heads`, `alembic history -r start:end` |
| Offline SQL | `alembic upgrade <start>:<end> --sql` |
| CI drift check | `alembic check` (since 1.9.0) |
| Async template | `alembic init -t async <dir>` |
| Transaction scope | `context.configure(transaction_per_migration=True)` |
| Outside a transaction | `with op.get_context().autocommit_block():` |
| Docs / code pinned | tag rel_1_20_0 of github.com/sqlalchemy/alembic |

## Examples
- SNIPPET: async `run_migrations_online` from Alembic's asyncio recipe; context: Alembic 1.20.0, SQLAlchemy asyncio, async DBAPI such as asyncpg; checked: no [DOC S-7zk6ggvu]
```python
import asyncio
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())
```
- SNIPPET: an expand revision that adds a nullable column and builds its index outside the transaction; context: Alembic 1.20.0 on PostgreSQL 18, `transaction_per_migration=True` set in env.py; checked: no [DER S-zcvw2nun, S-qh5ieidx, S-hqy2uu3t: `autocommit_block`, `CREATE INDEX CONCURRENTLY`, `ADD COLUMN`]
```python
"""expand: add site_event.source_id (nullable)

Revision ID: 3f2a9c1d7b10
Revises: 1975ea83b712
"""
from alembic import op
import sqlalchemy as sa

revision = "3f2a9c1d7b10"
down_revision = "1975ea83b712"

def upgrade():
    op.add_column("site_event", sa.Column("source_id", sa.Uuid(), nullable=True))
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_site_event_source_id "
            "ON site_event (source_id)"
        )

def downgrade():
    op.drop_index("ix_site_event_source_id", table_name="site_event")
    op.drop_column("site_event", "source_id")
```
