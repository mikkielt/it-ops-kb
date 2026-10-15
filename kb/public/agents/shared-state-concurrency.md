---
topic: agents/shared-state-concurrency
priority: P3
applies_to: "Concurrency control for state several agents write: Amazon S3 conditional writes, Azure Blob Storage ETags and leases, Redis distributed locks (Redlock), LangGraph PostgresStore; self-hosted MinIO, Garage and SeaweedFS conditional writes, NATS JetStream key-value, Valkey without persistence, etcd leases and transactions; docs read 2026-10-14 and 2026-10-15"
retrieved_utc: 2026-10-15
sources: [S-qdltospe, S-4qurlvvy, S-4oanvdmr, S-2fthx3xp, S-srqpsf7c, S-5lu6lddr, S-f3dlrjtw, S-26trg6rj, S-ukfteilx, S-opdaj4dk, S-oa3slfgh, S-a3umo362, S-ntlmfsuw, S-zv2dqsow, S-ulnpjwb7, S-pheyvvix, S-x3firlbx, S-eoyz3p4t, S-6hgplow2, S-vseohdra, S-75jmw3lf, S-s7uvhjek, S-3l6vhq2q, S-jnn4ww4t, S-bayxg4xz, S-523ddbfr, S-v7s32e7q]
status: partial
---

# Concurrency control for state several agents write

## Summary
- Two agents that read a shared object, change it and write it back lose one update unless the
  store checks something at write time. The stores here offer two kinds of check: **optimistic**
  (a conditional write that fails when the object changed since it was read: S3 `If-Match`, Azure
  `If-Match` on an ETag) and **pessimistic** (a lock or lease held while writing: Azure blob leases,
  a Redis lock). Without either, S3 and Azure Blob Storage both resolve concurrent writes as last
  writer wins. [DER S-qdltospe, S-4oanvdmr, S-2fthx3xp: the stores' own descriptions of their
  conditional writes, leases and default behaviour, below]
- **Amazon S3** conditional writes: `If-None-Match: *` creates an object only when its key does not
  exist, `If-Match: <ETag>` overwrites only the version that was read; a failed condition answers
  `412 Precondition Failed`. [DOC S-qdltospe]
- **Azure Blob Storage**: `If-Match` with the ETag gives optimistic concurrency; a blob lease
  (15 to 60 seconds, or infinite) gives pessimistic concurrency, and a write without the active
  lease id fails with `412`. With neither, the last writer wins. [DOC S-2fthx3xp]
- **Redis**: the Redis documentation's Redlock algorithm gives mutual exclusion only within the
  lock's validity time and assumes bounded clock drift; the page tells users who need correctness to
  add fencing tokens, and says a wall-clock shift can let two processes hold the lock. [DOC S-5lu6lddr]
- **LangGraph `PostgresStore`**: `put` is an upsert (`INSERT ... ON CONFLICT (prefix, key) DO
  UPDATE`) with no version check, so of two writers on one key the later statement's value stays
  (details in `agents/langgraph.md`). [CODE S-26trg6rj: libs/checkpoint-postgres/langgraph/store/postgres/base.py#BasePostgresStore._prepare_batch_PUT_queries]
- **Self-hosted and volatile stores**: NATS JetStream key-value (`create`/`update` compare-and-swap
  by revision, watches, create-only per-key TTL, memory or disk streams) and etcd (guarded
  transactions, leases with keep-alive) give compare-and-swap; Valkey can run with no persistence at
  all; Garage cannot do conditional writes; MinIO and SeaweedFS reject `If-None-Match: *` on an
  existing object in code, with race safety unconfirmed, and the open-source MinIO repository is no
  longer maintained. [DER S-ulnpjwb7, S-x3firlbx, S-zv2dqsow, S-6hgplow2, S-eoyz3p4t, S-oa3slfgh,
  S-75jmw3lf, S-jnn4ww4t, S-vseohdra: the sections below]

## Facts

### Amazon S3 conditional writes
- A conditional write adds `If-None-Match` or `If-Match` to a write request; `If-None-Match` checks
  that no object with the key exists, and `If-Match` compares the given ETag with the object's and
  fails the write when they differ. [DOC S-qdltospe]
- Without `If-None-Match`, an upload or copy to an existing key in an unversioned or
  version-suspended bucket overwrites the object. [DOC S-qdltospe]
- `If-None-Match` takes only the value `*` and needs `s3:PutObject`; `If-Match` takes the ETag as a
  string and needs both `s3:PutObject` and `s3:GetObject`. [DOC S-qdltospe]
- Both headers work on `PutObject`, `CompleteMultipartUpload` and `CopyObject`; in a versioned
  bucket `If-None-Match` applies only to the current version. [DOC S-qdltospe]
- `If-None-Match`: no object with the key gives `200 OK`, an existing one `412 Precondition
  Failed`; in a versioned bucket a write also succeeds when the current version is a delete marker.
  [DOC S-qdltospe]
- When several conditional writes or copies target one key, the first to finish succeeds and S3
  fails the later ones with `412 Precondition Failed`. [DOC S-qdltospe]
- `If-Match`: an existing object with a matching ETag gives `200 OK`, a different ETag `412`;
  concurrent requests can also get `409 Conflict`, and a delete that completes first gives
  `404 Not Found`, after which the page says to upload the object again. [DOC S-qdltospe]
- A `409 Conflict` on a conditional `PutObject` may be retried; on `CompleteMultipartUpload` the
  whole upload must start again with `CreateMultipartUpload`. [DOC S-qdltospe]
- Conditional writes ignore multipart uploads still in progress: another client's conditional
  write can land first, and the multipart upload's later conditional `CompleteMultipartUpload` then
  fails with `412`. [DOC S-qdltospe]
- A bucket policy can require conditional writes with the condition keys `s3:if-none-match` and
  `s3:if-match`; multipart uploads need `s3:ObjectCreationOperation` to exempt
  `CreateMultipartUpload`, `UploadPart` and `UploadPartCopy`, which take no conditional headers.
  [DOC S-4qurlvvy]
- With such a policy, copies into the bucket or prefix fail: `CopyObject` without the headers gets
  `403 Access Denied`, and with them `501 Not Implemented`. [DOC S-4qurlvvy]
- Conditional requests must be signed with AWS Signature Version 4. [DOC S-qdltospe]
- S3 gives strong read-after-write consistency for `PUT` and `DELETE`, and an update to one key is
  atomic: a concurrent `GET` sees the old or the new data, never a partial object. [DOC S-4oanvdmr]
- The consistency section says S3 does not support object locking for concurrent writers: of two
  simultaneous `PUT`s to one key the one with the latest timestamp wins, and an application that
  needs a lock must build its own. [DOC S-4oanvdmr]

### Azure Blob Storage: ETags and leases
- The Azure Storage client libraries do not support concurrent writes to the same blob, except
  append blobs when write order does not matter; an app with several writers to one blob needs a
  concurrency strategy. [DOC S-2fthx3xp]
- Azure Storage supports optimistic concurrency, pessimistic concurrency and last writer wins;
  without an explicit strategy, the last writer wins. [DOC S-2fthx3xp]
- Azure Storage is strongly consistent: after an insert or update, later reads and lists return
  it; snapshot isolation lets reads run beside writes within one partition. [DOC S-2fthx3xp]
- Optimistic: every write changes the object's ETag; a client sends the ETag it read in `If-Match`,
  and when the blob's current ETag differs the service answers `412 (Precondition Failed)` and the
  client should fetch the blob again. [DOC S-2fthx3xp]
- `If-Modified-Since`, `If-Unmodified-Since` and `If-None-Match` are also supported conditional
  headers. [DOC S-2fthx3xp]
- Pessimistic: a lease locks a blob for exclusive use; a finite lease lasts 15 to 60 seconds and
  an infinite one amounts to an exclusive lock; a finite lease can be renewed and is released
  automatically when it expires. [DOC S-2fthx3xp]
- While a lease is active, `Put Blob`, `Put Block`, `Put Block List`, `Append Block`, `Set Blob
  Metadata`, `Set Blob Properties`, `Delete Blob` and the destination of `Copy Blob` need the lease
  id and fail with `412` without it; a write with another lease id fails with `409`. [DOC S-srqpsf7c]
- Reads need no lease id: the lease enforces exclusive writes, and exclusive reads only when every
  client passes a lease id. [DOC S-2fthx3xp, S-srqpsf7c]
- `Lease Blob` actions are `acquire`, `renew`, `change`, `release` and `break`; any authorized
  request can break a lease without its id, and no new lease can be acquired until the break
  period (0 to 60 seconds, `x-ms-lease-break-period`) has passed. [DOC S-srqpsf7c]
- A lease that expires instead of being released can make a client wait up to one minute before a
  new lease is granted; the holder can renew its expired lease at once if the blob was not changed.
  [DOC S-srqpsf7c]
- A container lease locks only the container's deletion; every other container operation, and
  deleting a container whose blobs are leased, succeeds without it. [DOC S-2fthx3xp, S-srqpsf7c]
- `Lease Blob` needs `Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write`
  (least privileged built-in role: Storage Blob Data Contributor) or a SAS with Write permission.
  [DOC S-srqpsf7c]

### Redis distributed locks (Redlock)
- The Redis documentation names three minimum properties of a distributed lock: mutual exclusion
  (one holder at a time), deadlock freedom (a lock can always be taken eventually) and fault
  tolerance (locks work while a majority of Redis nodes are up). [DOC S-5lu6lddr]
- A single primary with a replica cannot keep mutual exclusion: replication is asynchronous, so a
  lock taken on the primary can be lost on failover and a second client then takes it. [DOC S-5lu6lddr]
- Single-instance lock: `SET resource_name my_random_value NX PX 30000`; the value must be unique
  across clients and requests so that release deletes the key only when it still holds that value
  (`DELEX key IFEQ value` from Redis 8.4, else a Lua script); a plain `DEL` can remove another
  client's lock. [DOC S-5lu6lddr]
- The page calls the single-instance lock a viable solution where an occasional race is
  acceptable. [DOC S-5lu6lddr]
- Redlock: the client tries all N independent primaries (N=5 in the page's examples) with the same
  key and value and short timeouts; it holds the lock only if a majority granted it in less than
  the lock validity time, and otherwise unlocks every instance. [DOC S-5lu6lddr]
- Mutual exclusion holds only if the holder finishes its work within the validity time, minus a
  few milliseconds for clock drift; the algorithm assumes clocks advance at about the same rate.
  [DOC S-5lu6lddr]
- A network partition costs up to the lock's TTL in availability, without bound under repeated
  partitions. [DOC S-5lu6lddr]
- Without persistence, a restarted instance can let a second client lock the same resource; the
  page's remedies are `fsync=always`, or delaying a crashed instance's restart beyond the maximum TTL.
  [DOC S-5lu6lddr]
- The page's consistency disclaimer says to implement fencing tokens for correctness, not to assume
  a lock lasts as long as its holder, and that Redis does not use a monotonic clock for TTL, so a
  wall-clock shift can give two processes the lock. [DOC S-5lu6lddr]

### Upserts in PostgreSQL
- `INSERT ... ON CONFLICT DO UPDATE` guarantees an atomic insert-or-update outcome even under high
  concurrency, unless an independent error occurs. [DOC S-f3dlrjtw]

### Self-hosted S3-compatible servers
- MinIO AIStor's S3 compatibility page lists `If-Match` on `GetObject`, `HeadObject`, `PutObject`,
  `CopyObject`, `DeleteObject` and `CreateMultipartUpload`, and `If-None-Match` on the same
  operations except `DeleteObject`; `DeleteObjects` takes conditional deletes through an `<ETag>`
  element. [DOC S-ukfteilx]
- The AIStor page does not say whether the `If-None-Match: *` create-if-absent form is accepted;
  the community code answers it for the open-source server (below). [DER S-ukfteilx, S-75jmw3lf: the
  page lists headers only, and the code handles `*`]
- The open-source `minio/minio` repository's README now opens with "THIS REPOSITORY IS NO LONGER
  MAINTAINED", and calls its historical binary releases no longer maintained. [DOC S-vseohdra]
- In that code, `isETagEqual` treats an `If-None-Match` or `If-Match` value of `*` (after trimming
  spaces) as equal to any ETag, so `checkPreconditionsPUT` fails a `PUT` or `POST` with
  `PreconditionFailed` when the object exists, unless its top version is a delete marker.
  [CODE S-75jmw3lf: cmd/object-handlers-common.go#checkPreconditionsPUT]
- The PUT-side check is wired in, as `CheckPrecondFn`, only when the request carries `If-Match` or
  `If-None-Match` (or a preserve-ETag option), in `PutObjectHandler` and in
  `NewMultipartUploadHandler` and `CompleteMultipartUploadHandler`. [CODE S-s7uvhjek, S-3l6vhq2q:
  cmd/object-handlers.go#PutObjectHandler]
- Whether MinIO runs that check and the write as one atomic step when two clients race on one key
  is not shown by the handler code read; the check runs in a callback the object layer calls.
  [UNK]
- A 2024 GitHub issue that reported MinIO rejecting `If-None-Match: *` was closed after the
  maintainers showed the server accepting the bare `*`; the failing request came from a Go client
  that sent the value quoted. [COMMUNITY S-opdaj4dk]
- Garage's known-issues page lists no conditional writes, locking or WORM support: they are
  "structurally impossible" because Garage has no consensus algorithm, so `If-None-Match` cannot give
  mutual exclusion between concurrent writers. [DOC S-oa3slfgh]
- Garage's lack of consensus also leaves concurrent `CreateBucket` requests for one name without
  mutual exclusion. [DOC S-oa3slfgh]
- SeaweedFS's S3 API wiki lists "S3 Conditional Operations": `If-Match`, `If-None-Match`,
  `If-Modified-Since` and `If-Unmodified-Since`, without saying which operations or bucket modes they
  cover. [DOC S-a3umo362]
- In SeaweedFS's S3 gateway, `checkConditionalHeaders` resolves the latest version of the object
  (a missing object or a delete marker counts as absent) and `validateConditionalHeaders` fails
  `If-None-Match: *` with `PreconditionFailed` when the object exists, and other `If-None-Match`
  values when the ETag matches. [CODE S-jnn4ww4t: weed/s3api/s3api_object_handlers_put.go#validateConditionalHeaders]
- That check reads the entry and returns before the write, so whether two racing conditional
  writes can both pass is not settled by this function; no serialization is shown in it. [UNK]

### NATS JetStream key-value store
- A NATS key-value bucket is a JetStream stream named `KV_<bucket>` with subjects `$KV.<bucket>.>`;
  each key is the last subject token and each value a message on it. [DOC S-ntlmfsuw]
- JetStream streams can be stored in memory or on disk, and a bucket inherits every configuration
  option of its backing stream. [DOC S-zv2dqsow]
- So a bucket can be created on a memory-backed stream and lose its contents when the server
  stops; the key-value pages read do not show a memory bucket being created. [DER S-zv2dqsow,
  S-ntlmfsuw: streams take memory storage, and a bucket is a stream]
- Every write gets the next revision of one bucket-wide counter, and history keeps a key's earlier
  revisions up to the bucket's depth, which caps at 64. [DOC S-ulnpjwb7]
- `create` writes a key only when it does not exist (compare-and-swap against revision 0), and
  `update` writes only when the key is still at the revision the caller names; a mismatch rejects
  the write and nothing is overwritten. [DOC S-ulnpjwb7]
- A watch first delivers the current value of every matching key, then streams each later change
  as it lands; underneath it is an ephemeral ordered consumer on the backing stream. [DOC S-pheyvvix]
- A per-key TTL is set on `create` only and needs limit markers enabled on the bucket, which
  requires nats-server 2.11 or newer. [DOC S-x3firlbx]
- `put` and `update` take no TTL, and writing the key again appends a value without one, so the key
  stops expiring; changing a TTL means delete and create again. [DOC S-x3firlbx]
- A per-key TTL that fires leaves a marker with the reason `MaxAge`, which watchers see; a bucket
  can also have a bucket-wide maximum age, history depth and size cap. [DOC S-x3firlbx]
- JetStream streams are configurable for replication, and the concepts page describes the key-value
  store as having built-in replication and durability. [DOC S-zv2dqsow]

### NATS JetStream object store
- The object store splits an object's bytes into chunks, writes each chunk as a message and then
  one metadata message for the whole object; a read replays the chunks in order and verifies them.
  [DOC S-523ddbfr]
- Unlike the key-value store, the object store keeps only the latest metadata per object, so it
  holds the current version, not a history; each object carries a SHA-256 digest checked on read.
  [DOC S-523ddbfr]
- An object store bucket can be listed as a snapshot and watched for new objects in real time, and
  objects can carry a description, headers, a metadata map and links to other objects. [DOC S-523ddbfr]
- The object store pages read describe no create-if-absent or revision-checked put, unlike the
  key-value store's `create` and `update`. [UNK]

### NATS security
- NATS authentication accepts a password, a token or a bearer JWT, or a signature with a secret:
  mTLS, or NKeys, optionally with non-bearer JWTs. [DOC S-v7s32e7q]
- Authorization limits each admitted user to the subjects it is granted to publish or subscribe on;
  the server denies everything else. [DOC S-v7s32e7q]
- An account is an isolated tenant with its own users and subject space; two accounts see each
  other's messages only through a deliberate export and import, and a server with no accounts
  configured uses the implicit global account `$G`. [DOC S-v7s32e7q]
- TLS protects each connection, a client certificate can serve as the identity, and an operator
  mode makes the server trust an operator's public key instead of a configured user list; an auth
  callout lets an external service authenticate clients for the server. [DOC S-v7s32e7q]

### Valkey without persistence
- Valkey's persistence modes are RDB snapshots, AOF, both, or none; disabling persistence "is
  sometimes used when caching". [DOC S-eoyz3p4t]
- RDB snapshots are on by default; `save ""` (or `--save ""` on the command line) turns them off.
  [DOC S-eoyz3p4t]
- Valkey Pub/Sub delivers at most once: a message a subscriber cannot handle (an error or a
  disconnect) is lost for good; Streams persist messages and support at-least-once delivery.
  [DOC S-bayxg4xz]
- Valkey's lock semantics follow the Redis lock facts above: the persistence caveat there (a
  restarted instance without persistence can let a second client take the same lock) applies in
  full to an instance run with persistence off. [DER S-eoyz3p4t, S-5lu6lddr: no persistence, and
  the Redis page's restart caveat]

### etcd leases and transactions
- An etcd transaction is an atomic If/Then/Else over the key-value store: a conjunction of
  comparisons, each on one key's existence, value, revision or version, guards a success block and
  a failure block. [DOC S-6hgplow2]
- A transaction can update several keys under one store revision, but may not modify one key twice.
  [DOC S-6hgplow2]
- Each key records its creation and modification revisions; etcd's client locks wait for ownership
  by creation revision. [DOC S-6hgplow2]
- A lease is a client-liveness mechanism: the cluster grants it with a TTL, and it expires when no
  keep-alive arrives within that TTL. [DOC S-6hgplow2]
- A key can be attached to at most one lease; when the lease expires or is revoked, every attached
  key is deleted and each deletion is an event in the history. [DOC S-6hgplow2]
- Leases are refreshed over a bidirectional `LeaseKeepAlive` stream, and each response returns the
  lease's remaining TTL. [DOC S-6hgplow2]

### How it fits
- An agent that updates shared state in object storage reads the object with its ETag and writes
  it back with `If-Match`; a `412` means another agent wrote first, so it re-reads and re-applies its
  change instead of overwriting. Creating a per-run or per-claim object with `If-None-Match: *`
  turns S3 or Blob Storage into a first-writer-wins claim, with no lock to expire. [DER S-qdltospe,
  S-2fthx3xp: the conditional-write behaviour above]
- A blob lease or a Redis lock bounds how long one agent may hold exclusive access; neither stops
  a holder that overruns its lease from writing to another system afterwards. A write that must not
  run twice also carries a check the target enforces (an ETag condition, a fencing token, or a lease
  id the store itself checks). [DER S-srqpsf7c, S-5lu6lddr: leases expire on their own, and the
  Redis page's fencing-token and validity-time caveats]
- A LangGraph store item written by several agents gets no conflict detection from `PostgresStore`:
  per-agent keys (one writer per key) avoid the overwrite, and a read-modify-write that must not lose
  updates needs its own check outside the store API, such as a PostgreSQL advisory lock
  (`arch/postgres-advisory-locks.md`). [DER S-26trg6rj, S-f3dlrjtw: put is an unconditional upsert]
- Of the self-hosted object stores, only those that enforce conditional writes can serve as a
  claim store: Garage cannot, and MinIO and SeaweedFS list the headers but their create-if-absent
  behaviour needs a test on the deployed version before claims rely on it. [DER S-oa3slfgh,
  S-ukfteilx, S-a3umo362, S-opdaj4dk: Garage has no compare-and-swap; the others list the headers
  without stating the `*` form or bucket-mode limits]
- On NATS, a claim is `create` with a per-key TTL, and progress is an `update` against the last
  revision. A heartbeat cannot extend the claim: an `update` drops the TTL, so the key stops
  expiring. A renewing claim therefore needs delete-then-create, which is not atomic, or a
  bucket-wide maximum age. [DER S-ulnpjwb7, S-x3firlbx: create-only TTLs, and an update that appends a
  value without one]
- An etcd lease with keep-alive gives a renewable claim whose keys disappear on their own when the
  holder stops: the pattern blob leases give for one object, but for any number of keys and with
  history events. [DER S-6hgplow2, S-srqpsf7c: etcd leases delete attached keys; blob leases expire
  on their own]
- The open-source MinIO server handles `If-None-Match: *` as create-if-absent in code, but its
  repository is no longer maintained, so a new deployment that wants MinIO's conditional writes is
  on AIStor or on a server whose fixes still ship. [DER S-vseohdra, S-75jmw3lf: the README's
  maintenance notice and the `*` handling]
- For several operators sharing one NATS server, an account per team keeps subject spaces apart,
  and per-user publish and subscribe grants decide who may write claims; a coordination subject
  shared across teams is an explicit export and import. [DER S-v7s32e7q: accounts, subject
  permissions and exports as the security page describes them]
- Valkey Pub/Sub suits wake-up signals only, since a missed message is gone; claims and progress
  belong in keys or Streams, which a restarted subscriber can read again. [DER S-bayxg4xz:
  at-most-once Pub/Sub and persisted Streams]
- A volatile coordination store loses every claim on restart, so it can hold only state git or a
  durable store can rebuild: claims, leases and progress, not facts or results. [DER S-eoyz3p4t,
  S-zv2dqsow: no-persistence and memory-storage modes keep data in memory only]

## Reference
- `agents/langgraph.md`: the LangGraph store API, and the `PostgresStore` put path read in its
  source.
- `arch/postgres-advisory-locks.md`: PostgreSQL advisory locks as a single-writer lock inside the
  database.
- `claude/skills-and-subagents.md`: agent team task lists, which use file locking on one machine.
- Kleppmann's analysis of Redlock and antirez's answer, linked from the Redis page's "Analysis of
  Redlock" section, were not read for this topic.
- `agents/agent-memory-services.md`: managed memory services for agents (Foundry agent memory, Claude
  Managed Agents memory stores, Cloudflare Durable Objects state).

## Examples
- SNIPPET: compare-and-swap of a shared JSON state object in S3 with the AWS CLI: read the ETag,
  write only if it is unchanged; context: AWS CLI v2, bucket `amzn-s3-demo-bucket`, credentials with
  `s3:GetObject` and `s3:PutObject`; checked: no [DER S-qdltospe: `--if-match` and the `412` outcome]
```bash
etag=$(aws s3api head-object --bucket amzn-s3-demo-bucket --key agents/state.json \
  --query ETag --output text)
aws s3api get-object --bucket amzn-s3-demo-bucket --key agents/state.json state.json
# ... change state.json locally ...
aws s3api put-object --bucket amzn-s3-demo-bucket --key agents/state.json \
  --body state.json --if-match "$etag"
# a 412 Precondition Failed error: another writer won; read again and retry
```
