---
topic: arch/uuidv7-identifiers
priority: P3
applies_to: "UUIDv7 as a primary key: RFC 9562 layout and monotonicity, and PostgreSQL 18 uuidv7()"
retrieved_utc: 2026-10-11
sources: [S-chjxpvbv, S-a6c5zane, S-5rgjgp6v]
status: complete
---

# UUIDv7: RFC 9562 layout, monotonicity and PostgreSQL `uuidv7()`

## Summary
A UUIDv7 puts a millisecond Unix timestamp in the top 48 bits and random (or counter) bits below, so values sort by creation time and a B-tree index stays local. The timestamp alone does not make values strictly increasing: within one millisecond ordering needs a counter or extra clock bits. PostgreSQL 18 ships `uuidv7()` that fills 12 bits with a sub-millisecond fraction and guarantees increase within one session. The value is an identifier, never a secret. For hash-derived ids see `arch/content-addressed-ids-jsonl.md`.

## Facts

### Layout and monotonicity (RFC 9562)
- A UUIDv7 holds `unix_ts_ms` (48 bits, big-endian, milliseconds since 1970-01-01 UTC with leap seconds excluded), `ver` (4 bits, 0b0111), `rand_a` (12 bits), `var` (2 bits, 0b10) and `rand_b` (62 bits). [DOC S-chjxpvbv]
- The 74 bits that are not timestamp, version or variant are random by default; an implementation may instead fill them, in this order, with an optional sub-millisecond fraction (at most 12 bits), an optional seeded counter and random data. [DOC S-chjxpvbv]
- The embedded timestamp makes values monotonic across milliseconds; inside one millisecond, and for batches, the RFC offers a dedicated counter (method 1), a monotonic random counter (method 2) or more clock precision in `rand_a` (method 3). [DOC S-chjxpvbv]
- For a counter the RFC's general guidance is at least 12 and at most 42 bits, seeded randomly with each new timestamp, with rollover handled by the application: freeze the counter and wait for the clock, or advance the timestamp. [DOC S-chjxpvbv]
- Implementations SHOULD check that each new value is greater than the previous one and handle a clock rollback, a leap second or a counter rollover when it is not. [DOC S-chjxpvbv]
- Values are meant to sort as opaque big-endian bytes, which gives index locality that the RFC says can differ from random inserts by one order of magnitude or more. [DOC S-chjxpvbv]
- A database should store a UUID as the 128-bit binary value, not text, and a monolithic database that generates the values itself gets the best monotonicity compared with client-generated ones. [DOC S-chjxpvbv]
- Applications should treat UUIDs as opaque and avoid parsing them (the version, variant or timestamp) unless a requirement needs it. [DOC S-chjxpvbv]
- UUIDs MUST NOT be used as security capabilities (identifiers whose possession grants access), implementations SHOULD NOT assume them hard to guess, and where a UUID is used within a security operation UUIDv4 SHOULD be used because the UUIDv7 timestamp reveals the creation order and time. [DOC S-chjxpvbv]

### PostgreSQL 18
- `uuidv7([shift interval])` returns a version 7 UUID whose timestamp is the Unix time in milliseconds plus a sub-millisecond part plus random bits; the optional `shift` moves the timestamp by an interval and must stay within 1970-01-01 UTC to about year 10889, else an error is raised. [DOC S-a6c5zane]
- `gen_random_uuid()` and `uuidv4()` generate version 4 values; `uuid_extract_timestamp(uuid)` returns a `timestamptz` for version 1 and 7 and null for others, and the page warns it is not necessarily exactly the generation time. [DOC S-a6c5zane]
- `uuid_extract_version(uuid)` returns the version of any RFC 9562 UUID and null for other variants. [DOC S-a6c5zane]
- The server code uses method 3: 12 bits of `rand_a` carry 1/4096 fractions of a millisecond and the rest is random bytes. [CODE S-5rgjgp6v: src/backend/utils/adt/uuid.c#generate_uuidv7]
- Each backend keeps the last timestamp it used in a static variable and makes the next one at least a minimal step later, so values from one session are strictly increasing even when the clock stands still. [CODE S-5rgjgp6v: src/backend/utils/adt/uuid.c#get_real_time_ns_ascending]
- On platforms whose real-time clock has microsecond resolution (macOS is the named example) fewer sub-millisecond bits carry real information. [CODE S-5rgjgp6v: src/backend/utils/adt/uuid.c, comment on the sub-millisecond bits]
- Because the memory of the last timestamp is per backend, two sessions that insert in the same millisecond can produce values out of commit order, and a server clock set backwards can yield lower values in a new session; across sessions the order follows the clock only. [DER S-5rgjgp6v, S-chjxpvbv: the static is per backend; RFC says clock rollback needs a guard]
- A key meant to sort by time in a table written by one service through one connection pool is therefore ordered per connection, not globally: a column that needs a total order needs its own sequence or a `created_at` sorted on the database clock. [DER S-5rgjgp6v: ordering guarantee is per backend]
- Using `uuidv7()` as the default of a primary key keeps the generating clock on the database server, which the RFC prefers over client generation, and the embedded creation time is readable by anyone who sees the id. [DER S-chjxpvbv, S-a6c5zane: database-generated values; timestamp in the top bits]

## Reference
| Field | Bits | Content |
|---|---|---|
| `unix_ts_ms` | 48 | milliseconds since 1970-01-01 UTC |
| `ver` | 4 | `0111` |
| `rand_a` | 12 | random, or sub-millisecond fraction, or counter bits |
| `var` | 2 | `10` |
| `rand_b` | 62 | random, or counter and random |

## Examples
- SNIPPET: a table whose primary key is generated by the database as UUIDv7; context: PostgreSQL 18 or later; checked: no [DOC S-a6c5zane: `uuidv7()`, `uuid_extract_timestamp`]
```sql
CREATE TABLE site_event (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    site_id uuid NOT NULL,
    payload jsonb NOT NULL
);
SELECT id, uuid_extract_timestamp(id) FROM site_event ORDER BY id LIMIT 10;
```
