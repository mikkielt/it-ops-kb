---
topic: arch/postgres-backup-age-s3-git-bundle
priority: P3
applies_to: "age 1.3.x and rage 0.12 / pyrage 1.4 (encryption), git 2.56 git-bundle, Amazon S3 user guide (versioning, Object Lock, multipart upload, checksums) as the reference for S3-compatible stores, PostgreSQL 18 pg_dump, pg_restore and psql"
retrieved_utc: 2026-10-11
sources: [S-ax3gmu7j, S-bi6fdfos, S-iwytfp7z, S-duamtyj7, S-vh25ss57, S-tvr6yltg, S-srrxgn7s, S-j2a6zjok, S-izv6sxd6, S-2faaoioj, S-wec2qrob, S-o3ecr65r, S-vykvhstk, S-gmljtlvr, S-oo2r576d]
status: partial
---

# Nightly encrypted Postgres dumps and git bundles to S3-compatible storage, restore tested in CI

## Summary
Each piece of a nightly backup of a PostgreSQL database and git repositories to an S3-compatible bucket has vendor documentation: `pg_dump` writes a snapshot, `git bundle` writes a repository to one file or to stdout, `age` encrypts a stream to public-key recipients, S3 multipart upload takes a stream of unknown size in parts, and `pg_restore` or `psql` with error-stopping options can replay the result in a throwaway database. What the vendors do not document is the S3-compatible part: Object Lock, additional checksums and multipart limits are documented for Amazon S3 only. The pipeline at the end is derived from those pages and has not been run. For the dump bytes themselves see `arch/postgres-dump-canonical-hash.md`; for age recipients and key handling see `auth/sops-age-recipients.md` and `auth/key-management-options.md`.

## Facts
- age usage: `age [--encrypt] (-r RECIPIENT | -R PATH)... [--armor] [-o OUTPUT] [INPUT]` and `age --decrypt [-i PATH]... [-o OUTPUT] [INPUT]`; INPUT defaults to standard input and OUTPUT to standard output, so it composes in a pipe (the README example is `tar cvz ~/data | age -r KEY > file.age`). v1.3.2 README. [DOC S-ax3gmu7j]
- A recipient is an `age1...` public key from `age-keygen` or an SSH public key; `-R` reads recipients one per line (`#` comments, `-` for stdin); decryption needs an identity file (`AGE-SECRET-KEY-1...` lines) passed with `-i`. Encryption needs only public keys, so an unattended nightly job can hold no decryption key. [DOC S-ax3gmu7j]
- `-p/--passphrase` encrypts with a passphrase (generated if left empty) and passphrase files are detected at decrypt time; `-a/--armor` writes PEM text instead of binary. [DOC S-ax3gmu7j]
- The age format splits the payload in 64 KiB chunks, each sealed with ChaCha20-Poly1305 under a nonce with a chunk counter and a final-chunk flag byte; the spec says streaming decryption MUST signal an error if end of file arrives without a successfully decrypted final chunk. [DOC S-bi6fdfos]
- A download cut short therefore fails in `age -d` instead of yielding a short plaintext; the failure shows only at the end of the stream, so a pipe into `pg_restore` can already have executed part of the dump when `age` reports the error. [DER S-bi6fdfos: final-chunk rule; chunked streaming decryption]
- rage v0.12.1 is a Rust implementation of the same format with the same options (`-r`, `-R`, `-i`, `-p`, `-a`, `-o`), installable with `cargo install rage` (Rust 1.74+) and licensed Apache-2.0 or MIT at the user's option; the library is the `age` crate. The age README calls it an interoperable alternative implementation. [DOC S-iwytfp7z]
- pyrage v1.4.0 gives Python bindings to rage (`pip install pyrage`, MIT licence); its README examples call `encrypt(data_bytes, [recipients])`, `decrypt(data, [identities])` and `passphrase.encrypt/decrypt` on in-memory bytes, and show no file or stream interface. [DOC S-duamtyj7]
- A multi-gigabyte dump encrypted through the pyrage calls shown would sit in memory twice (plaintext and ciphertext); piping through the `age` or `rage` binary streams it instead. [DER S-duamtyj7, S-ax3gmu7j: bytes-in bytes-out examples; stdin/stdout streaming CLI]
- `git bundle create <file> <git-rev-list-args>` writes a bundle; `--all` packages all refs; `-` as the file writes the bundle to stdout (and `verify`, `list-heads`, `unbundle` read stdin with `-`). A full backup is `git bundle create backup.bundle --all`, restored with `git clone backup.bundle <dir>`. [DOC S-vh25ss57]
- A bundle holds only refs and the commits reachable from them, not the index, working tree, stash, per-repository config or hooks; the docs discourage `cp -r` of a repository because it may be written during the copy. [DOC S-vh25ss57]
- `git bundle verify <file>` checks that the bundle is valid and that the prerequisite commits exist in the current repository, listing missing commits; exit code zero on success and nonzero if the bundle is invalid. `git bundle list-heads <file>` lists the refs. [DOC S-vh25ss57]
- An incremental bundle uses a range (`old..new`, `--since=10.days master`, `-10 master`) and needs the prerequisite commits at the destination; only a bundle without prerequisites can be cloned from or unbundled into an empty repository. `--version` selects bundle format 2 (SHA-1 repositories only) or 3 (with capabilities). [DOC S-vh25ss57]
- The git-bundle page shows `fatal: Refusing to create empty bundle.` for ranges that do not resolve to a ref; whether an incremental range with no new commits also exits nonzero is not stated there. [UNK]
- Amazon S3 upload limits: a single PUT up to 5 GB; the console up to 160 GB; multipart upload up to 50 TB, for objects from 5 MB. The limits page gives maximum object size 48.8 TiB, up to 10,000 parts, part size 5 MiB to 5 GiB and no minimum size for the last part. [DOC S-tvr6yltg, S-srrxgn7s]
- Multipart upload is initiate, upload parts (numbers 1 to 10,000, in any order, in parallel), complete; it can start before the final object size is known and a failed part is retried alone. Parts are billed until the upload is completed or stopped and an upload does not expire, so the docs recommend a lifecycle rule with the `AbortIncompleteMultipartUpload` action. [DOC S-j2a6zjok]
- A streamed object of unknown size must fit in 10,000 parts, so the part size sets the largest object: 64 MiB parts allow up to 640 GiB. [DER S-srrxgn7s: 10,000-part limit and 5 MiB to 5 GiB part size; arithmetic]
- Checksums: S3 supports CRC64NVME (default), CRC32, CRC32C, SHA1, SHA256, MD5, XXHASH64, XXHASH3, XXHASH128 and SHA512; a client sends a checksum with the upload (header such as `x-amz-checksum-sha256`) and S3 validates it server side before storing; a multipart upload with a full-object checksum fails with `BadDigest` on mismatch. [DOC S-izv6sxd6, S-j2a6zjok]
- S3 Versioning is off by default; once enabled a bucket can only be suspended, never made unversioned; an overwrite makes a new version and a delete adds a delete marker. [DOC S-2faaoioj]
- S3 Object Lock works only in versioning-enabled buckets and gives write-once-read-many retention (retention period or legal hold) per object version; in compliance mode no user, including the account root, can overwrite or delete the version or shorten the retention, in governance mode a user with `s3:BypassGovernanceRetention` can. Locks do not stop new versions or delete markers being added on top. [DOC S-wec2qrob]
- The AWS CLI targets a non-AWS endpoint with `--endpoint-url` on a command (`aws s3 ls --endpoint-url http://localhost:4567`), `AWS_ENDPOINT_URL` or `AWS_ENDPOINT_URL_S3`, or `endpoint_url` in the shared config file. [DOC S-o3ecr65r]
- Whether a given S3-compatible store implements Object Lock, versioning, the additional checksums or the 5 MiB part minimum the same way as Amazon S3 is not stated on any AWS page read, and no store's own compatibility page was read. [UNK]
- pg_restore: reads archive formats only (custom, directory, tar); with no file it reads stdin; `-l` lists the table of contents; `-e/--exit-on-error` stops at the first SQL error (default is to continue and print an error count); `-1/--single-transaction` wraps the restore in BEGIN/COMMIT and implies `--exit-on-error`; `-C/--create` creates the database; `-j` needs a custom or directory archive that is a regular file or directory, not a pipe, and cannot combine with `--single-transaction`. [DOC S-gmljtlvr]
- A plain-format dump is replayed with `psql`; with variable `ON_ERROR_STOP` set psql stops at the first error and exits with status 3 (1 fatal error of its own, 2 lost connection), and with `-1/--single-transaction` it rolls back instead of committing; by default it continues after an error. The pg_dump docs recommend `-X` (no psqlrc) for restoring a plain dump. [DOC S-oo2r576d, S-vykvhstk]
- A dump restore executes arbitrary code of the source's superusers' choosing, which the pg_dump docs say may need inspection first; a disposable container is where a nightly restore test should run. [DOC S-vykvhstk]
- Derived pipeline (untested): dump or bundle to stdout, `age -r` to recipient keys, upload as multipart with a fixed part size; in CI download, `age -d -i`, into a throwaway PostgreSQL container with `pg_restore --exit-on-error --single-transaction` (archive) or `psql -X -v ON_ERROR_STOP=1 -1` (plain), then check the exit status and compare a probe such as table row counts or the canonical dump hash; for bundles `git bundle verify -`, `git clone`, and compare `git bundle list-heads` with the source refs. [DER S-ax3gmu7j, S-vh25ss57, S-j2a6zjok, S-gmljtlvr, S-oo2r576d: each stage is a documented command; the combination is not from a vendor source]
- Immutability recipe (derived, untested on a non-AWS store): enable versioning, then Object Lock with a default retention in governance or compliance mode, so a compromised uploader key can add versions but not remove the locked ones; keep the age identity file out of the uploader's reach. [DER S-2faaoioj, S-wec2qrob: Object Lock needs versioning and does not stop new versions; encryption needs only public keys per S-ax3gmu7j]
- Whether `aws s3 cp - s3://bucket/key` reads stdin, and what part size the CLI uses for it, was not read from a fetched page. [UNK]

## Reference
| Stage | Command or setting | Notes | Source |
|---|---|---|---|
| Dump | `pg_dump -Fc` (archive) or plain | plain bytes: see `arch/postgres-dump-canonical-hash.md` | S-vykvhstk |
| Bundle | `git bundle create - --all` | `-` is stdout; no hooks/config/stash | S-vh25ss57 |
| Encrypt | `age -r RECIPIENT` | public keys only; streaming | S-ax3gmu7j, S-bi6fdfos |
| Upload | multipart, 5 MiB to 5 GiB parts, 10,000 parts | single PUT up to 5 GB | S-srrxgn7s, S-tvr6yltg |
| Integrity | `x-amz-checksum-sha256` | CRC64NVME default | S-izv6sxd6, S-j2a6zjok |
| Immutability | Versioning + Object Lock | AWS-documented only | S-2faaoioj, S-wec2qrob |
| Non-AWS endpoint | `--endpoint-url`, `AWS_ENDPOINT_URL_S3` | | S-o3ecr65r |
| Restore archive | `pg_restore -e -1 -d DB` | `-j` needs a regular file | S-gmljtlvr |
| Restore plain | `psql -X -v ON_ERROR_STOP=1 -1 -f` | exit 3 on error | S-oo2r576d |
| Bundle check | `git bundle verify`, `list-heads` | nonzero if invalid | S-vh25ss57 |

## Examples
- SNIPPET: nightly backup stage that encrypts a custom-format dump and a bundle to one recipient and uploads both; context: POSIX shell, age 1.3.x, PostgreSQL 18 client tools, AWS CLI with a non-AWS `--endpoint-url`; `aws s3 cp` stdin handling was not read from a page (see UNK); checked: no [DER S-ax3gmu7j, S-vh25ss57, S-o3ecr65r, S-vykvhstk: option names from the pages read]

```sh
set -eu
pg_dump --format=custom --host=PL-SRV-0042 --username=jan.kowalski appdb \
  | age -r "$AGE_RECIPIENT" > appdb.dump.age
git -C /srv/repos/app.git bundle create - --all \
  | age -r "$AGE_RECIPIENT" > app.bundle.age
aws s3 cp appdb.dump.age s3://example-backups/pg/ --endpoint-url "$S3_ENDPOINT"
aws s3 cp app.bundle.age s3://example-backups/git/ --endpoint-url "$S3_ENDPOINT"
```

- SNIPPET: CI restore test that decrypts, restores into a throwaway database and verifies the bundle; context: POSIX shell, throwaway PostgreSQL 18 container reachable as PL-SRV-0042, identity file supplied as a CI file variable; checked: no [DER S-ax3gmu7j, S-gmljtlvr, S-vh25ss57: option names from the pages read]

```sh
set -eu
age --decrypt -i "$AGE_IDENTITY_FILE" appdb.dump.age > appdb.dump
pg_restore --exit-on-error --single-transaction \
  --host=PL-SRV-0042 --username=jan.kowalski --dbname=restore_test appdb.dump
age --decrypt -i "$AGE_IDENTITY_FILE" app.bundle.age > app.bundle
git bundle verify app.bundle
git clone app.bundle restored-app
```
