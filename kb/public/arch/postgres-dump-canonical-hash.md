---
topic: arch/postgres-dump-canonical-hash
priority: P3
applies_to: "PostgreSQL 18 pg_dump (docs 18, source tag REL_18_6): which parts of a plain-format dump vary between runs, which options change the bytes, and a derived recipe for hashing a dump"
retrieved_utc: 2026-10-11
sources: [S-vykvhstk, S-aae3vzxi, S-vor6jmfj, S-v246rdbb]
status: partial
---

# pg_dump output: what is deterministic, what is not, and hashing a dump

## Summary
A plain-format `pg_dump` is a text script that is a consistent snapshot of one database, so it can be hashed, but three things stop two dumps of an unchanged database from being byte-identical by default: the random `\restrict` key that PostgreSQL 18 writes at the top and bottom of every plain dump, the version header lines, and (with `-v`) start and completion timestamps. The custom and directory archive formats embed their creation time in the header and compress table data, so they are poor candidates for a byte hash. The vendor docs do not promise a row order for table data; the source shows `COPY ... TO stdout` with no `ORDER BY`. The recipe at the end of Facts is our derivation and has not been run.

## Facts
- `pg_dump` makes consistent exports while the database is in use and does not block readers or writers; the docs add that except in simple cases it is "generally not the right choice" for regular backups of production databases. PostgreSQL 18 docs. [DOC S-vykvhstk]
- The default format is plain (`-F p`, a SQL script fed to `psql`); `-F c` custom and `-F d` directory are archives for `pg_restore`, compressed by default (gzip at a moderate level for table-data segments), `-F t` tar is not compressed, and the directory format is the only one that supports parallel dumps (`-j`). [DOC S-vykvhstk]
- For plain output a nonzero `-Z` level or method (`--compress`) compresses the whole file as if piped through gzip, lz4 or zstd, and the default is no compression. [DOC S-vykvhstk]
- Custom-format header: `WriteHead` writes the creation time (`createDate`, set with `time(NULL)` when the archive handle is created) as broken-down local time fields (seconds to year, plus `tm_isdst`), then the database name, the remote server version string and `PG_VERSION`; so two custom or directory dumps of identical data made at different moments differ in the header even before compression is considered. Source REL_18_6. [CODE S-aae3vzxi: pg_backup_archiver.c#WriteHead]
- `--restrict-key=KEY` sets the `\restrict` key used in the dump; it works only for plain-text dumps, a random key is generated if none is given, and keys may hold only alphanumeric characters. The docs say the option is meant for testing and "repeatable output (e.g., comparing dump files)" and not for general use, because a malicious server that knows the key in advance may be able to inject code that `psql` then runs. [DOC S-vykvhstk]
- In source, a plain dump with no key given calls `generate_restrict_key()`, which fills a 64-byte buffer from `pg_strong_random` and maps each of the first 63 bytes onto a 62-character alphanumeric set (letters of both cases and digits), so a default plain dump differs on every run even if the data does not; passing `--restrict-key` with a non-plain format is a fatal error. [CODE S-v246rdbb: dumputils.c#generate_restrict_key]
- The key appears twice: `\restrict KEY` after the `-- PostgreSQL database dump` banner and `\unrestrict KEY` at the very end of the script, after the "dump complete" banner; the archiver also emits `\unrestrict` and `\restrict` around a `\connect` it must run in between. [CODE S-aae3vzxi: pg_backup_archiver.c#RestoreArchive]
- The header carries `-- Dumped from database version X` and `-- Dumped by pg_dump version Y` lines when those version strings are known; a `-- Started on` and a `-- Completed on` timestamp line are written only when `-v` is used. [CODE S-aae3vzxi: pg_backup_archiver.c#RestoreArchive, dumpTimestamp]
- The script starts with fixed `SET` lines (`statement_timeout = 0`, `lock_timeout = 0`, `idle_in_transaction_session_timeout = 0`, `transaction_timeout = 0`, `client_encoding`, `standard_conforming_strings`, `check_function_bodies = false`, `xmloption = content`, `client_min_messages = warning`, `row_security`), so they do not vary run to run with the same database encoding; `SET default_table_access_method` is written per table unless `--no-table-access-method` is given (docs: option removes commands that select table access methods). [CODE S-aae3vzxi: pg_backup_archiver.c#_doSetFixedOutputState]
- On its own connection `pg_dump` runs `BEGIN` and `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY` (or `SERIALIZABLE, READ ONLY, DEFERRABLE` with `--serializable-deferrable`), and sets `extra_float_digits` to 3 unless `--extra-float-digits` is given, `intervalstyle` to postgres and `synchronize_seqscans` off "to prevent unpredictable changes in row ordering across a dump and reload". [CODE S-vor6jmfj: pg_dump.c#setup_connection]
- Table data in a plain dump is read with `COPY table (columns) TO stdout` (or `COPY (SELECT ... FROM table filter) TO stdout` when a filter or foreign table applies); no `ORDER BY` is added, so rows come out in whatever order that scan returns. [CODE S-vor6jmfj: pg_dump.c#dumpTableData_copy]
- The pg_dump docs page does not state that table-data row order is stable between dumps of the same logical content; the order is not promised there. [UNK]
- `--serializable-deferrable` makes the dump consistent with later serial states by waiting for a safe point, which can delay the start for an indeterminate time but not change the performance once running; the docs say it is not beneficial for a dump meant only for disaster recovery. `--lock-wait-timeout` only makes the dump fail if shared table locks are not acquired in time. [DOC S-vykvhstk]
- `-j njobs` is for the directory format only, opens `njobs + 1` connections and needs synchronized snapshots (PostgreSQL 9.2 primaries, 10 standbys); a parallel dump writes one file per table, so a single plain script cannot come from `-j`. [DOC S-vykvhstk]
- Options that remove content from the script: `--no-comments`, `-x`/`--no-privileges` (`--no-acl`), `-O`/`--no-owner`, `--no-security-labels`, `--no-tablespaces`, `--no-publications`, `--no-subscriptions`, `--no-unlogged-table-data`, `--no-table-access-method`; `-n`/`-t` and their exclusions select objects, and with `-n` or `-t` the docs say large objects are not dumped unless `--large-objects` is added and that dependencies are not followed. Several are ignored for archive formats, where they belong to `pg_restore`. [DOC S-vykvhstk]
- `--inserts` and `--column-inserts` write `INSERT` statements instead of `COPY` (slow to restore, meant for non-PostgreSQL targets); `--rows-per-insert=N` also switches to `INSERT` with at most N rows per statement; `--extra-float-digits` is "not for routine backup dumps" per the docs because it lowers float precision. All of these change the bytes. [DOC S-vykvhstk]
- Canonical hash recipe (derived, not run): take a plain-format dump with every option fixed in a script (format `p`, no `-v`, no `-Z`, one pinned `pg_dump` major version, the same schema/table selection flags, the no-owner/no-privileges flags the restore target needs, `--restrict-key` set to a constant alphanumeric string kept in the pipeline configuration), then hash the bytes after either pinning both server and `pg_dump` versions or removing exactly the two `-- Dumped` lines. [DER S-vykvhstk, S-aae3vzxi, S-v246rdbb: the key, the header lines and the timestamps are the only run-dependent lines found in the source read]
- The recipe still has two open points: row order (above, UNK) and that the output text of `pg_dump` may differ between minor or major releases, which would change the hash on upgrade; the hash is therefore a "same database state and same tool" check, not a data-equality proof across tool versions. [DER S-vykvhstk, S-vor6jmfj: no ordering in the COPY statement; the docs describe version portability of output only as loadable by newer servers]

## Reference
| Source of byte differences | Plain format | Option or cure | Source |
|---|---|---|---|
| `\restrict`/`\unrestrict` key | random per run | `--restrict-key=KEY` (plain only) | S-vykvhstk, S-v246rdbb |
| `-- Dumped from/by` version lines | server and tool version | pin versions or drop the two lines | S-aae3vzxi |
| `-- Started on` / `Completed on` | only with `-v` | omit `-v` | S-aae3vzxi |
| Custom/directory header creation time | always | use plain format for hashing | S-aae3vzxi |
| Row order in `COPY` | scan order, no `ORDER BY` | not controllable by option; UNK | S-vor6jmfj |
| Float text | `extra_float_digits` 3 by default | leave default | S-vor6jmfj, S-vykvhstk |
| Ownership, grants, comments | in script by default | `--no-owner`, `--no-privileges`, `--no-comments` | S-vykvhstk |

## Examples
- SNIPPET: a plain dump with a fixed restrict key, no verbose timestamps and no ownership or privilege statements, hashed with SHA-256 (`restrictkey0001` is a placeholder); context: PostgreSQL 18 `pg_dump`, POSIX shell, `sha256sum` from coreutils; checked: no [DER S-vykvhstk: option names from the 18 docs]

```sh
pg_dump --format=plain --no-owner --no-privileges \
  --restrict-key=restrictkey0001 \
  --dbname=appdb --host=PL-SRV-0042 --username=jan.kowalski \
  | sha256sum
```
