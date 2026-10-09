---
topic: python/stdlib-sqlite3-csv
priority: P2
applies_to: [python, csv, sqlite3]
retrieved_utc: 2026-10-09
sources: [S-utoe3wfw, S-rle6nqpc, S-syrr7enn, S-xq53ipsf, S-vc2lihhb, S-nnljaqtm]
status: complete
---

# stdlib csv and sqlite3 (what this kb's tools rely on)

## Summary
`_tools/` is stdlib-only Python 3.11+: it reads and writes `_sources.csv` and friends with the `csv`
module and persists the pack/search index with `sqlite3` (`_self/tools.md`: "postings lists in a
stdlib `sqlite3` file"). Both modules have version-dependent behaviour a maintaining agent should
know: `csv`'s quoting constants gained two new members in 3.12, and `sqlite3`'s transaction-control
defaults changed in 3.12 (opt-in) with a documented future default change. `VACUUM` and `auto_vacuum`
decide how a cache file shrinks after a `DELETE`, and `VACUUM` is refused inside a transaction, which the
module's implicit `BEGIN` before a `DELETE` opens.

## Facts
- Files used with the `csv` module should be opened with `newline=''` (both for `csv.reader`/`writer`
  and for `DictReader`/`DictWriter`), so the module's own newline handling is not double-processed by
  universal-newline translation; this applies on every supported platform, not just Windows. [DOC S-utoe3wfw]
- Quoting constants: `QUOTE_ALL` (quote every field), `QUOTE_MINIMAL` (quote only fields containing the
  delimiter, quote character, or characters in the line terminator — the default when `quotechar` is
  set), `QUOTE_NONNUMERIC` (writer quotes all non-numeric fields; reader converts all unquoted fields
  to `float`), `QUOTE_NONE` (writer never quotes, escaping special characters with `escapechar`
  instead; reader does no special quote processing). [DOC S-utoe3wfw]
- `QUOTE_NOTNULL` and `QUOTE_STRINGS` were added in Python **3.12** — code supporting 3.9-3.11 cannot
  use them. `QUOTE_NOTNULL` quotes every non-`None` field, writing `None` as an empty unquoted string
  (reader: empty unquoted -> `None`); `QUOTE_STRINGS` does the same but for string fields specifically,
  behaving like `QUOTE_NONNUMERIC` otherwise. [DOC S-utoe3wfw]
- `csv.field_size_limit([new_limit])` returns the current maximum field size the C parser accepts (and
  sets a new one if given); the built-in default, before any script changes it, is `128 * 1024` = 131072
  characters, set in the `_csv` C extension module. A field larger than the limit raises
  `csv.Error: field larger than field limit`. [DOC S-syrr7enn, DOC S-utoe3wfw]
- `Dialect.escapechar` and `Dialect.quotechar` reject an *empty-string* value (as opposed to `None`)
  since Python **3.11**; before that an empty string was accepted but behaved unpredictably. [DOC S-utoe3wfw]
- `DictReader(f, fieldnames=None, ...)` reads the first row as field names when `fieldnames` is
  omitted; `DictWriter(f, fieldnames, ...)` requires `fieldnames` explicitly (unlike `DictReader`, it
  is not optional) since a writer has no input row to infer them from. Both accept a `dialect`
  parameter (default `'excel'`) and arbitrary `**fmtparams` overrides on top of it, exactly like
  `csv.reader`/`csv.writer`. [DOC S-utoe3wfw]
- `DictWriter(f, fieldnames, restval='', extrasaction='raise', dialect='excel', *args, **kwds)`: a row
  dict missing a key of `fieldnames` gets `restval` (default the empty string) in that column; a dict
  with a key not in `fieldnames` raises `ValueError` under the default `extrasaction='raise'` and drops
  the extra key silently under `'ignore'`. Other keyword arguments go to the underlying `writer`. A
  writer row must be an iterable of strings or numbers (a `DictWriter` row a dict whose values are
  passed through `str` first); `writeheader()` (3.2+) writes the `fieldnames` row. [DOC S-utoe3wfw]
- The writer terminates each row with `Dialect.lineterminator`, default `'\r\n'`, so a `csv.writer`
  file opened with `newline=''` has CRLF line ends on every platform; `csv.reader` ignores
  `lineterminator` and recognises either `'\r'` or `'\n'` as end of line. A field containing the
  delimiter, the quote character, `'\r'`, `'\n'` or a `lineterminator` character is quoted under
  `QUOTE_MINIMAL`; with `doublequote=True` (default) a quote character inside a field is doubled, and
  with `doublequote=False` and no `escapechar` the writer raises `csv.Error` on a field holding one.
  Pass `lineterminator='\n'` for LF output. [DOC S-utoe3wfw]
- The `csv` docs say "there is no formal specification in existence" for CSV; RFC 4180 (October 2005,
  category Informational, not a standard) documents the format "followed by most implementations":
  records end with CRLF, the last record may or may not have a line break, an optional header line
  comes first, and each line should hold the same number of fields. [DOC S-xq53ipsf]
- RFC 4180: fields containing line breaks, double quotes or commas should be enclosed in double
  quotes, and a double quote inside a quoted field is escaped by preceding it with another double
  quote (`"b""bb"`); fields may or may not be quoted otherwise, spaces are part of a field, and the
  last field of a record is not followed by a comma. Python's default `excel` dialect with
  `QUOTE_MINIMAL` and `doublequote=True` produces this form apart from quoting only when needed.
  [DOC S-xq53ipsf; DER S-utoe3wfw: the dialect defaults quoted above match the RFC rules]
- `sqlite3` wraps a *third-party* SQLite C library, not one Python ships source for; the actual runtime
  version linked into a given Python build can therefore vary by platform/build and is only knowable
  at runtime via `sqlite3.sqlite_version` (a version string) or `sqlite3.sqlite_version_info` (a tuple
  of ints) — there is no fixed "the" SQLite version for a given Python release. [DER S-rle6nqpc: the
  docs describe sqlite3 as requiring "the third-party SQLite library" and expose the linked version
  only via these runtime attributes, with no compile-time guarantee of a specific version.]
- `sqlite3.connect(..., check_same_thread=True)` (the default) raises `ProgrammingError` if the
  connection object is used from a thread other than the one that created it; passing
  `check_same_thread=False` allows cross-thread use, but the caller must then serialize write
  operations itself to avoid corruption. The module-level `sqlite3.threadsafety` integer (DB-API 2.0
  meaning) is derived at import time from how the underlying SQLite library itself was compiled
  (single-thread=0, multi-thread=1, serialized=3), not hardcoded, as of Python 3.11 (previously always
  hardcoded to `1`). [DOC S-rle6nqpc]
- Python **3.12** added the `autocommit` parameter/attribute on `Connection`, alongside the pre-existing
  `isolation_level`. `autocommit` currently *defaults* to the sentinel `sqlite3.LEGACY_TRANSACTION_CONTROL`,
  under which the older `isolation_level` attribute (`"DEFERRED"` by default, or `"EXCLUSIVE"`/
  `"IMMEDIATE"`, or `None` to disable uv's — i.e. sqlite3's — implicit transaction handling) keeps
  controlling transactions exactly as it always did; `isolation_level` has *no effect at all* once
  `autocommit` is set to `True` or `False`. The docs record that the current
  `LEGACY_TRANSACTION_CONTROL` default for `autocommit` is expected to change to `False` in a future
  Python release. [DOC S-rle6nqpc]
- Under the default `autocommit=LEGACY_TRANSACTION_CONTROL` and an `isolation_level` that is not `None`,
  `execute` and `executemany` open a transaction implicitly before an `INSERT`, `UPDATE`, `DELETE` or
  `REPLACE` when none is open; other statements get no implicit transaction handling.
  `isolation_level=None` never opens one implicitly (SQLite's autocommit mode, queried with
  `Connection.in_transaction`), and `executescript` first commits any pending transaction. [DOC S-rle6nqpc]
- With `autocommit=False` the module keeps a transaction always open (`connect`, `commit` and `rollback`
  each open the next one with `BEGIN DEFERRED`); with `autocommit=True` SQLite's autocommit mode is used and
  `commit`/`rollback` do nothing. The `sqlite3` docs do not mention `VACUUM` or `auto_vacuum` anywhere. [DOC S-rle6nqpc]
- `VACUUM` rebuilds the database file into the least space: it copies the content into a temporary
  database and overwrites the original through the normal journal or WAL, so up to twice the original file
  size is needed as free disk space. It may change the `ROWID` of rows in tables without an explicit
  `INTEGER PRIMARY KEY`. [DOC S-vc2lihhb]
- `VACUUM` fails if the connection running it has an open transaction; unfinalized statements usually hold a
  read transaction open, so they can make it fail too, and another connection's lock that blocks writes
  fails it as well (`VACUUM INTO` is not a write to the source, so only the first two apply). [DOC S-vc2lihhb]
- After a large `DELETE` the file keeps its size unless `auto_vacuum=FULL`: the emptied pages go on a
  freelist for reuse and `VACUUM` is what shrinks the file; `VACUUM` also makes each table and index
  contiguous and can cut partially filled pages, which `auto_vacuum` never does. [DOC S-vc2lihhb]
- `PRAGMA auto_vacuum` is `0`/`NONE` by default (unless `SQLITE_DEFAULT_AUTOVACUUM` was compiled in):
  deleted pages stay in the file, are reused by later inserts, and only `VACUUM` shrinks it. [DOC S-nnljaqtm]
- `auto_vacuum=FULL` (`1`) moves freelist pages to the end of the file and truncates it at every
  transaction commit; it does not defragment or repack pages and can make fragmentation worse. [DOC S-nnljaqtm]
- `auto_vacuum=INCREMENTAL` (`2`) stores the bookkeeping but reclaims nothing at commit: `PRAGMA
  incremental_vacuum(N)` removes up to N freelist pages and truncates the file by as many; with no argument,
  N below 1 or N above the freelist length it clears the whole freelist, and it does nothing outside
  incremental mode or with an empty freelist. [DOC S-nnljaqtm]
- `auto_vacuum` must be set before the first table is created: `NONE` to `FULL`/`INCREMENTAL` on an existing
  database needs the pragma followed by `VACUUM`, `FULL` and `INCREMENTAL` can be switched at any time, and
  going back to `NONE` always needs `VACUUM`, even on an empty database. [DOC S-nnljaqtm]
- A `VACUUM` refused with `sqlite3.OperationalError` ("cannot VACUUM from within a transaction") is the
  usual result of a connection in the default legacy mode running `VACUUM` after a `DELETE` it has not
  committed, since `execute` opened a transaction for the `DELETE`; `commit()` first, or open the
  connection with `isolation_level=None` or `autocommit=True`. `autocommit=False` always has a transaction
  open, so it refuses `VACUUM` until the code leaves that mode. [DER S-rle6nqpc, S-vc2lihhb: the module opens a
  transaction before `DELETE`, and `VACUUM` fails inside an open transaction; the probe fact below confirms it]
- One probe (Python 3.13.2 with SQLite 3.45.3, macOS, 2026-10-09, a table of 2000 rows of 500 characters, `DELETE FROM t`
  without a `WHERE`): on a default `sqlite3.connect`, `in_transaction` was `True` after the `DELETE` and `execute("VACUUM")`
  raised `OperationalError: cannot VACUUM from within a transaction`; after `commit()` it ran; with
  `isolation_level=None` or `autocommit=True` it ran straight after the `DELETE`; with `autocommit=False` it was refused
  right after `commit()`; `executescript("DELETE FROM t; VACUUM;")` ran. A `VACUUM` straight after `CREATE TABLE` ran in
  legacy mode (`in_transaction` was `False`). Other Python or SQLite versions were not run. [DER S-rle6nqpc, S-vc2lihhb: probe run and read against the documented transaction rules]
- The same probe, file sizes after the `DELETE` and `commit()`: `NONE` stayed at its full-table size and `VACUUM` cut it
  to a page or two; `FULL` had already shrunk to a few pages at the commit; `INCREMENTAL` stayed at full size until
  `PRAGMA incremental_vacuum` ran. Python 3.13.2, SQLite 3.45.3, macOS; other versions not run. [DER S-nnljaqtm, S-vc2lihhb: probe read against the documented modes]
- The same probe: `con.execute("PRAGMA incremental_vacuum")` on its own freed one page of 250 on the freelist, and so did
  left the file almost unchanged; `.fetchall()` on it, or `executescript("PRAGMA incremental_vacuum;")`, cleared the whole
  freelist, and `incremental_vacuum(10)` with `.fetchall()` freed 10. Fetch the result of the pragma, or run it with
  `executescript`, when the whole freelist should go. Python 3.13.2, SQLite 3.45.3; other versions not run. [DER S-nnljaqtm, S-rle6nqpc: probe read against the documented pragma, whose pages say nothing of how a driver must step it]

## Reference
- SNIPPET: write a CSV with `newline=''` (correct on every platform) and open a shared sqlite3 cache from multiple threads; context: Python 3.11+ stdlib `csv`/`sqlite3`; checked: syntax [DOC S-utoe3wfw: `newline=''` and `QUOTE_MINIMAL` default; DOC S-rle6nqpc: `check_same_thread=False` and `sqlite3.sqlite_version`]
```python
import csv

with open("data.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)          # or csv.DictWriter(f, fieldnames=[...])
    w.writerow(["id", "url"])  # csv.QUOTE_MINIMAL is the implicit default quoting

import sqlite3

con = sqlite3.connect("cache.db", check_same_thread=False)  # e.g. a shared read-only index
print(sqlite3.sqlite_version)  # the actually-linked SQLite version, not a fixed constant
```
- SNIPPET: shrink a cache file after a bulk delete; context: Python 3.12+ stdlib `sqlite3`, any SQLite; checked: syntax [DER S-rle6nqpc, S-vc2lihhb: `isolation_level=None` opens no implicit transaction, and `VACUUM` needs none open]
```python
import sqlite3

con = sqlite3.connect("cache.db", isolation_level=None)  # autocommit mode: no implicit BEGIN
con.execute("DELETE FROM postings WHERE stale = 1")
con.execute("VACUUM")  # refused with OperationalError if a transaction were open
```

## Examples
- A tool built for Python 3.9+ compatibility must not rely on `csv.QUOTE_NOTNULL`/`QUOTE_STRINGS`
  (3.12+ only); `QUOTE_MINIMAL`/`QUOTE_ALL`/`QUOTE_NONNUMERIC`/`QUOTE_NONE` are safe back to very old
  Python 3 versions.
- A read-only index cache shared across worker processes (e.g. an on-disk `sqlite3` file rebuilt after
  kb file changes) should open connections per-thread or pass `check_same_thread=False` deliberately,
  and never assume a specific bundled SQLite feature-set without checking `sqlite3.sqlite_version_info`
  at runtime.
