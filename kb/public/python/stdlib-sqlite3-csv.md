---
topic: python/stdlib-sqlite3-csv
priority: P2
applies_to: [python, csv, sqlite3]
retrieved_utc: 2026-09-27
sources: [S-utoe3wfw, S-rle6nqpc, S-syrr7enn]
status: complete
---

# stdlib csv and sqlite3 (what this kb's tools rely on)

## Summary
`_tools/` is stdlib-only Python 3.11+: it reads and writes `_sources.csv` and friends with the `csv`
module and persists the pack/search index with `sqlite3` (`_self/tools.md`: "postings lists in a
stdlib `sqlite3` file"). Both modules have version-dependent behaviour a maintaining agent should
know: `csv`'s quoting constants gained two new members in 3.12, and `sqlite3`'s transaction-control
defaults changed in 3.12 (opt-in) with a documented future default change.

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

## Examples
- A tool built for Python 3.9+ compatibility must not rely on `csv.QUOTE_NOTNULL`/`QUOTE_STRINGS`
  (3.12+ only); `QUOTE_MINIMAL`/`QUOTE_ALL`/`QUOTE_NONNUMERIC`/`QUOTE_NONE` are safe back to very old
  Python 3 versions.
- A read-only index cache shared across worker processes (e.g. an on-disk `sqlite3` file rebuilt after
  kb file changes) should open connections per-thread or pass `check_same_thread=False` deliberately,
  and never assume a specific bundled SQLite feature-set without checking `sqlite3.sqlite_version_info`
  at runtime.
