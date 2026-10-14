---
topic: agents/shared-state-concurrency
priority: P3
applies_to: "Concurrency control for state several agents write: Amazon S3 conditional writes, Azure Blob Storage ETags and leases, Redis distributed locks (Redlock), LangGraph PostgresStore; docs read 2026-10-14"
retrieved_utc: 2026-10-14
sources: [S-qdltospe, S-4qurlvvy, S-4oanvdmr, S-2fthx3xp, S-srqpsf7c, S-5lu6lddr, S-f3dlrjtw, S-avxyujaz]
status: complete
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
  (details in `agents/langgraph.md`). [CODE S-avxyujaz: libs/checkpoint-postgres/langgraph/store/postgres/base.py#BasePostgresStore._prepare_batch_PUT_queries]

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
  (`arch/postgres-advisory-locks.md`). [DER S-avxyujaz, S-f3dlrjtw: put is an unconditional upsert]

## Reference
- `agents/langgraph.md`: the LangGraph store API, and the `PostgresStore` put path read in its
  source.
- `arch/postgres-advisory-locks.md`: PostgreSQL advisory locks as a single-writer lock inside the
  database.
- `claude/skills-and-subagents.md`: agent team task lists, which use file locking on one machine.
- Kleppmann's analysis of Redlock and antirez's answer, linked from the Redis page's "Analysis of
  Redlock" section, were not read for this topic.

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
