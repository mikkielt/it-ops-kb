---
topic: python/sqlalchemy-asyncio-asyncpg
priority: P3
applies_to: "SQLAlchemy 2.0.54 (rel_2_0_54) asyncio extension with the postgresql+asyncpg dialect; asyncpg 0.32.0; PostgreSQL"
retrieved_utc: 2026-10-11
sources: [S-4zo5mcqa, S-4eztl5ck, S-ukfbblnj, S-xhpt3onl, S-oh5jmzp6, S-4dfwedi7, S-anvb7ol7, S-stp2kczx]
status: complete
---

# SQLAlchemy 2 asyncio with asyncpg

## Summary
SQLAlchemy 2.0 ships an asyncio extension (`sqlalchemy.ext.asyncio`): `create_async_engine()` gives an
`AsyncEngine`, `async_sessionmaker` makes `AsyncSession` objects, and `postgresql+asyncpg://` selects
the asyncpg driver. Using it correctly means avoiding implicit IO (lazy loads, expired attributes),
using one `AsyncSession` per task, disposing the engine with `await`, and knowing how asyncpg's
prepared statements interact with PgBouncer. The pages read document SQLAlchemy 2.0.54 (the latest 2.0
tag when read; a 2.1 series also exists and was not read) and asyncpg 0.32.0. Alembic's async setup is
not covered here. Starting a test database with `driver="asyncpg"` is in
`python/testcontainers-postgres-pytest.md`.

## Facts
- The asyncio extension (added in SQLAlchemy 1.4) needs Python 3 and the `greenlet` package, which
  installs by default on x86_64, aarch64, ppc64le, amd64 and win32 where wheels exist; on other
  platforms (Apple M1 is named) use `pip install sqlalchemy[asyncio]` to force it. For Core,
  `create_async_engine()` returns an `AsyncEngine` whose `connect()` and `begin()` are asynchronous
  context managers delivering an `AsyncConnection`; `execute()` returns a buffered result and
  `stream()` a server-side `AsyncResult`. [DOC S-4zo5mcqa]
- The URL form is `postgresql+asyncpg://user:password@host:port/dbname[?key=value]`. The dialect page
  says it is SQLAlchemy's first asyncio dialect, was added in 1.4 and should normally be used only with
  `create_async_engine()`. SQLAlchemy replaces asyncpg's default string results for `json` and `jsonb`
  with decoding through `json.loads` (change it with `json_deserializer`). [DOC S-4eztl5ck]
- `create_async_engine()` takes the arguments of `create_engine()`; the dialect must be
  asyncio-compatible. Passing `server_side_cursors=True` to it raises `AsyncMethodRequired`; use
  `AsyncConnection.stream()` for streaming results instead. [CODE S-ukfbblnj: lib/sqlalchemy/ext/asyncio/engine.py#create_async_engine]
- `AsyncSession` gives the ORM in 2.0 style; `async_sessionmaker(engine, expire_on_commit=False)` is the
  factory for new sessions with fixed parameters, and `async with async_session() as session:` closes
  the session at the end of the block. `async with session.begin():` wraps a transaction, and the
  engine-level `async with engine.begin() as conn:` commits on exit. [DOC S-4zo5mcqa]
- Set `expire_on_commit=False` for asyncio: by default commit expires all attributes, and reading an
  expired attribute needs IO that cannot happen implicitly. The page also says to prefer
  `AsyncSession.refresh()` over `expire()`, and that expiration should normally not be needed. [DOC S-4zo5mcqa]
- Lazy loading does not work implicitly under asyncio (a lazy-loaded relationship or deferred column
  would emit IO on attribute access). The documented remedies: eager loading such as
  `select(A).options(selectinload(A.bs))` (called the most useful strategy); the `AsyncAttrs` mixin on
  the declarative base with `await obj.awaitable_attrs.rel` (new in 2.0.13); write-only relationships;
  `lazy="raise"`; and `await session.refresh(obj, ["bs"])`, which loads a named relationship since
  2.0.4. [DOC S-4zo5mcqa]
- Further asyncio rules from the same page: new objects need an explicit empty collection (for
  example `A(bs=[])`) so it is readable after flush; avoid the `all` cascade and list cascades
  explicitly; the legacy "dynamic" loader works only inside `run_sync` or through `.statement`; and on
  PostgreSQL, SQLite and MariaDB, 2.0 fetches server defaults with RETURNING automatically. [DOC S-4zo5mcqa]
- One `AsyncSession` is not safe for concurrent tasks: it is a mutable object representing a single
  transaction in progress, so concurrent work such as `asyncio.gather()` needs a separate session per
  task. SQLAlchemy does not recommend `async_scoped_session` (global mutable state) for new code and
  suggests passing the session to the functions that need it. [DOC S-4zo5mcqa]
- `AsyncConnection.run_sync(fn)` and `AsyncSession.run_sync(fn)` run a synchronous function in a
  greenlet; it is the documented way to call `MetaData.create_all`/`drop_all`, the `Inspector`, or
  sync-style ORM code including lazy loads and legacy `Query`. The page labels the technique
  "deepalchemy" and "controversial". [DOC S-4zo5mcqa]
- Call `await engine.dispose()` when an `AsyncEngine` created in function scope goes out of use; the
  pool cannot be cleaned in `__del__` because no `await` is possible, and skipping it may print
  `RuntimeError: Event loop is closed` during garbage collection. [DOC S-4zo5mcqa]
- `AsyncEngine.dispose(close=True)` calls `sync_engine.dispose` through `greenlet_spawn` and closes
  only connections currently checked in; checked-out ones are detached and close when released. With
  `close=False` the previous pool is only de-referenced. [CODE S-ukfbblnj: lib/sqlalchemy/ext/asyncio/engine.py#AsyncEngine.dispose]
- An `AsyncEngine` should not be shared between event loops with the default pool. If it is moved to a
  new loop, call `dispose()` first or a `RuntimeError` such as "got Future attached to a different loop"
  can follow; if sharing is required, use `poolclass=NullPool`. [DOC S-4zo5mcqa]
- For a test suite whose runner gives every test its own event loop, a module-level engine reused
  across tests meets the situation above, so create the engine per test or per loop (or use
  `NullPool`). [DER S-4zo5mcqa: the "multiple event loops" rule, applied to per-test loops]
- The asyncpg dialect returns `AsyncAdaptedQueuePool` as its pool class (or
  `FallbackAsyncAdaptedQueuePool` when the URL has `async_fallback=true`); that pool is `QueuePool`
  with an asyncio-compatible queue that does not use `threading.Lock`, and it takes the same arguments
  as `QueuePool`. [CODE S-4eztl5ck: lib/sqlalchemy/dialects/postgresql/asyncpg.py#PGDialect_asyncpg.get_pool_class]
- The pool class is used by default for engines from `create_async_engine`. [CODE S-xhpt3onl: lib/sqlalchemy/pool/impl.py#AsyncAdaptedQueuePool]
- Prepared statement cache: the dialect prepares all statements with `asyncpg.connection.prepare()`
  and caches the prepared objects per DBAPI connection, 100 per connection by default; set
  `?prepared_statement_cache_size=500` in the URL to resize it, `0` to disable. The page warns that
  DDL run from another process can leave pooled connections with stale prepared statements or type
  OIDs and raise `InvalidCachedStatementError` or `cache lookup failed for type <oid>`; the dialect
  clears its caches on such errors but cannot retry, because the transaction is invalidated. [DOC S-4eztl5ck]
- PgBouncer with SQLAlchemy: asyncpg numbers prepared statements, which can clash behind a proxy. The
  dialect page's workaround passes `connect_args={"prepared_statement_name_func": lambda:
  f"__asyncpg_{uuid4()}__"}` together with `poolclass=NullPool`, and says to configure PgBouncer to run
  `DISCARD` when connections return, otherwise prepared statements accumulate. [DOC S-4eztl5ck]
- asyncpg's own FAQ: "prepared statement ... does not exist" or "already exists" errors usually mean a
  PgBouncer in `transaction` or `statement` pool mode, which does not support prepared statements.
  Options: use asyncpg's own connection pool, pass `statement_cache_size=0` to `asyncpg.connect()` /
  `create_pool()` (and avoid `Connection.prepare()`), or set PgBouncer's `pool_mode` to `session`. [DOC S-4dfwedi7]
- The asyncpg-level `statement_cache_size` is not the SQLAlchemy URL option above. The dialect's
  `connect` pops `prepared_statement_cache_size`, `prepared_statement_name_func` and `async_fallback` and
  forwards the remaining keyword arguments to `asyncpg.connect`, so `connect_args={"statement_cache_size": 0}`
  reaches asyncpg. [DER S-4eztl5ck, S-4dfwedi7: dialect `connect` forwards leftover kwargs; FAQ names the asyncpg parameter]
- asyncpg's docs recommend its pool (`asyncpg.create_pool()`) for server-type applications and say it
  removes the need for an external pooler such as PgBouncer. [DOC S-oh5jmzp6]
- The `asyncpg.create_pool()` signature defaults are `min_size=10`, `max_size=10`,
  `max_queries=50000` and `max_inactive_connection_lifetime=300.0`. [CODE S-anvb7ol7: asyncpg/pool.py#create_pool]
- An SQLAlchemy engine pools asyncpg connections in its own `AsyncAdaptedQueuePool` and opens each with
  `asyncpg.connect`; it does not use `asyncpg.create_pool()`, so the two pools are not combined and
  the sizes in `create_pool` do not apply. [DER S-4eztl5ck, S-xhpt3onl: dialect `connect` calls `asyncpg.connect`, pool class is `AsyncAdaptedQueuePool`]
- asyncpg 0.32.0 is licensed Apache-2.0 and declares `requires-python >= 3.9`. [CODE S-stp2kczx: pyproject.toml#project]
- With PostgreSQL `ENUM` types, asyncpg may emit an expensive type-metadata query when a new
  connection opens; the dialect page suggests `connect_args={"server_settings": {"jit": "off"}}`
  to mitigate it. [DOC S-4eztl5ck]
- Event handlers stay synchronous: attach them to `engine.sync_engine` or `AsyncSession.sync_session`,
  and `AdaptedConnection.run_async()` runs an awaitable driver method such as asyncpg's
  `set_type_codec` from a pool `connect` handler (added in 1.4.30). [DOC S-4zo5mcqa]

## Reference
| Need | API (SQLAlchemy 2.0) |
| --- | --- |
| engine | `create_async_engine("postgresql+asyncpg://...")` |
| session factory | `async_sessionmaker(engine, expire_on_commit=False)` |
| DDL under async | `await conn.run_sync(Base.metadata.create_all)` |
| eager load | `select(A).options(selectinload(A.bs))` |
| lazy attribute | `await obj.awaitable_attrs.bs` (class with `AsyncAttrs`) |
| shutdown | `await engine.dispose()` |
| no pooling | `poolclass=NullPool` |
| asyncpg driver args | `connect_args={...}` (for example `statement_cache_size`, `server_settings`) |

## Examples
- SNIPPET: engine, session factory and one session per concurrent task, with eager loading; context:
  SQLAlchemy 2.0.x, asyncpg, a reachable PostgreSQL, models `A` with relationship `bs` assumed; checked: no [DER S-4zo5mcqa, S-4eztl5ck: documented API calls combined; URL uses placeholder host and credentials]
```python
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

engine = create_async_engine(
    "postgresql+asyncpg://jan.kowalski:change-me@PL-SRV-0042:5432/app"
)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def load(a_id: int):
    async with Session() as session:  # one AsyncSession per task
        stmt = select(A).where(A.id == a_id).options(selectinload(A.bs))
        return (await session.execute(stmt)).scalar_one()


async def main() -> None:
    await asyncio.gather(load(1), load(2))
    await engine.dispose()


asyncio.run(main())
```
- SNIPPET: engine behind PgBouncer in transaction pooling mode; context: SQLAlchemy 2.0.x,
  asyncpg, PgBouncer with `DISCARD` configured; checked: no [DER S-4eztl5ck, S-4dfwedi7: dialect page workaround with unique statement names, plus asyncpg's `statement_cache_size=0` option; use one of the two]
```python
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    "postgresql+asyncpg://jan.kowalski:change-me@PL-SRV-0042:6432/app",
    poolclass=NullPool,
    connect_args={
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        # alternative from asyncpg's FAQ: "statement_cache_size": 0,
    },
)
```
