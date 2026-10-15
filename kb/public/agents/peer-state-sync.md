---
topic: agents/peer-state-sync
priority: P3
applies_to: "Syncing agent state between workstations without a shared server: Syncthing (docs at commit 25904513, 2026-10-07), DFS Replication (Windows Server), Automerge (docs at commit b4cfd9a1, 2026-09-04), git v2.55.0 documentation; read 2026-10-15"
retrieved_utc: 2026-10-15
sources: [S-zdnk4m6k, S-fmrgts5l, S-bskvvicf, S-trssy6ht, S-y6tixlbj, S-vpl4l5cd, S-5nz523b7, S-5fvc6but, S-tfj3n5g7, S-qinq7hxq, S-zmmh2aoz, S-o3lg5zce, S-syegds5m, S-3ztu6fdi, S-ygtpb7no, S-nv6io42x, S-l6s4hfqp]
status: complete
---

# Syncing agent state between workstations without a server

## Summary
- Four ways to keep agent state (memory files, caches, task lists) the same on several machines
  without a central state server, and what each does when two machines change the same thing:
  file sync (Syncthing), multi-master file replication (DFS Replication), a CRDT document library
  (Automerge) and git. None of the file-level tools merges two edits of one file: one copy wins and
  the other is kept aside. [DER S-zdnk4m6k, S-trssy6ht, S-5nz523b7, S-syegds5m: each tool's conflict
  rule, below]
- **Syncthing**: of two different edits of one file, the one with the older modification time is
  renamed to `<filename>.sync-conflict-<date>-<time>-<modifiedBy>.<ext>`, and that copy is then
  synced to every device like any other file. File versioning (off by default) keeps the old
  version of a file replaced or deleted by a change from another device, in `.stversions`.
  [DER S-zdnk4m6k, S-fmrgts5l: the conflict and versioning sections, below]
- **DFS Replication**: last writer wins by time stamp; the losing file goes to the hidden
  `DfsrPrivate\ConflictandDeleted` folder of the member that resolved the conflict, which is not
  replicated and is cleaned like a cache, so a losing copy is not guaranteed to survive. It runs only
  between Windows Server members of a domain, not on workstations. [DER S-trssy6ht, S-y6tixlbj: the
  FAQ entries below]
- **Automerge**: each document carries its history, so any two copies merge without a server;
  concurrent edits of different keys or list positions are all kept, and two writes of the same
  property pick the same winner on every peer while the loser stays readable through `getConflicts`.
  [DER S-qinq7hxq, S-5fvc6but, S-5nz523b7: the concept, merge-rule and conflict pages, below]
- **git**: the documentation tells users to move work between machines with `git push` and `git
  fetch`, never by syncing a repository with a cloud sync service, and to push to a shared bare
  repository, which refuses a push that is not a fast-forward until the pusher fetches and merges.
  [DER S-syegds5m, S-3ztu6fdi, S-l6s4hfqp: the gitfaq and gitcvs-migration pages, below]

## Facts

### Syncthing: conflicts
- Syncthing keeps, per file, the local version, the versions other connected devices announce and
  a "global" version (usually the most recent) that every device works to reach. [DOC S-zdnk4m6k]
- When a file was changed on two devices at once and the contents differ, one copy is renamed to
  `<filename>.sync-conflict-<date>-<time>-<modifiedBy>.<ext>`. [DOC S-zdnk4m6k]
- The copy with the older modification time is the one renamed; with equal times, the copy from the
  device whose ID has the larger value in its first 63 bits is renamed. [DOC S-zdnk4m6k]
- When a change and a deletion of one file conflict and the deletion wins, the changed file is kept
  as a `sync-conflict` copy in the same way. [DOC S-zdnk4m6k]
- A `sync-conflict` file is a normal file once created and is propagated to the other devices: the
  conflict is resolved on one device, and Syncthing cannot tell which copy the user wants.
  [DOC S-zdnk4m6k]
- Syncthing never writes into the destination file: it writes a temporary copy
  (`.syncthing.<name>.tmp`, `~syncthing~<name>.tmp` on Windows) and moves it over the old version.
  [DOC S-zdnk4m6k]
- Paths are case-sensitive in Syncthing; a remote file whose name differs only in case from a local
  one on a case-insensitive system (Windows, macOS) is reported as a case conflict and not synced,
  and which of two such remote variants wins is not predictable. [DOC S-zdnk4m6k]

### Syncthing: folder types
- A send-only folder ignores changes from other devices; an out-of-sync one shows "Override
  Changes", which overwrites the other devices' copies with this host's state and deletes files it
  lacks. [DOC S-bskvvicf]
- A receive-only folder applies changes from the cluster but does not send local ones; a local file
  that the cluster then changes becomes a sync conflict the cluster version wins, and that conflict
  copy is not sent to the cluster. [DOC S-bskvvicf]

### Syncthing: file versioning
- File versioning is set per folder and per device and is off by default (no old copies kept); it
  archives only versions replaced or deleted by a change received from another device, never a
  version the user changes locally. [DOC S-fmrgts5l]
- Versions go to the `.stversions` folder in the shared folder unless `fsPath` sets another path,
  which should be on the same file system. [DOC S-fmrgts5l]
- Strategies (`folder.versioning.type`): `trashcan`, `simple`, `staggered`, `external`, or empty for
  none. [DOC S-fmrgts5l]
- Trash can: a replaced or deleted file moves to `.stversions`, replacing an older copy of the same
  name there; `cleanoutDays` removes files older than that many days, and 0 keeps them for good.
  [DOC S-fmrgts5l]
- Simple: like trash can but keeps up to `keep` time-stamped versions per file, plus `cleanoutDays`.
  [DOC S-fmrgts5l]
- Staggered: keeps the oldest version in every 30 seconds for the first hour, every hour for the
  first day, every day for the first 30 days and every week up to the maximum age, then deletes it;
  a maximum age of 0 keeps versions forever. The page gives the age in days in the GUI text and
  `maxAge` in seconds in the option reference. [DOC S-fmrgts5l]
- External: runs a command just before a file is replaced, with `%FOLDER_PATH%` and `%FILE_PATH%`
  (also `$FOLDER_PATH` and `$FILE_PATH` from 2.1.2); the command must remove the file, the paths are
  untrusted input, and shell wrapping such as `sh -c` is invalid and may be rejected. [DOC S-fmrgts5l]
- `cleanupIntervalS` sets how often the versions folder is cleaned, in seconds (0 turns periodic
  cleaning off, at most one year). [DOC S-fmrgts5l]

### DFS Replication: conflicts and the losing copy
- When two users change one file on different servers, DFS Replication keeps the version saved last
  and moves the other to the `DfsrPrivate\ConflictandDeleted` folder under the replicated folder's
  local path on the server that resolved the conflict. [DOC S-trssy6ht]
- The Conflict and Deleted folder is not replicated; DFS Replication treats it as a cache and cleans
  it when it exceeds its configured size or the disk runs out of space, so a conflicting file is not
  guaranteed to be kept. [DOC S-trssy6ht]
- A conflict writes an informational event to the DFS Replication event log, seen only by server
  administrators, and may sit on a server other than the one where it started. [DOC S-trssy6ht]
- DFS Replication does not merge files, text files included. [DOC S-trssy6ht]
- It uses time stamps to decide which file wins a conflict and needs no time sync of its own, but
  server clocks must be within five minutes of each other (the Kerberos default). [DOC S-trssy6ht]
- It has no distributed locking or file checkout: a file locked on one server can still be changed
  on another, and the FAQ says not to use it where several users change the same files at once on
  different servers. [DOC S-trssy6ht]
- It replicates only between servers running Windows Server, relies on Active Directory Domain
  Services for configuration and does not work in a workgroup. [DOC S-trssy6ht]
- It does not replicate files in chronological order, and a file another application holds open
  with an exclusive lock is not replicated until it is closed. [DOC S-trssy6ht]
- During initial replication, the primary member's files win conflicts with other members' versions.
  [DOC S-trssy6ht]
- The Conflict and Deleted folder's default size limit is 660 MB. [DOC S-y6tixlbj]
- Its contents are listed in `ConflictAndDeletedManifest.xml` (pre-existing files, overwritten at
  initial sync, in `PreexistingManifest.xml`); `Get-DfsrPreservedFiles -Path <manifest>` lists the
  preserved files and `Restore-DfsrPreservedFiles` restores them. [DOC S-vpl4l5cd, S-trssy6ht]
- Whether a member keeps deleted files depends on its membership settings, changed with
  `Set-DfsrMembership`. [DOC S-vpl4l5cd]

### Automerge: merging without a server
- Automerge is a CRDT: concurrent changes on different devices merge automatically without a central
  server, over any connection-oriented transport (client/server, peer-to-peer or local). [DOC S-tfj3n5g7]
- A document has a history of commits like a git repository, and that history plus conflict rules
  means any two Automerge documents can always be merged. [DOC S-qinq7hxq]
- Merge rules for maps: different keys set on two sides are both kept; a delete of a key the other
  side did not change removes it; a delete against a new value keeps the new value; two values set
  for one key give one value chosen the same way on every node. [DOC S-5fvc6but]
- Lists and text: concurrent inserts and deletes are all kept; two inserts at one position are
  ordered the same on every node; an update beats a concurrent delete of the same element. [DOC S-5fvc6but]
- Counters merge by adding every node's increments. [DOC S-5fvc6but]
- Two concurrent writes of one property (or one list index) are the one case with no well-defined
  resolution: Automerge picks one winner, the same on every node, and the other values remain
  readable with `Automerge.getConflicts(doc, key)`. [DOC S-5nz523b7]
- The winner is chosen by operation ID (a counter, then the actor ID to break ties), not by wall
  clock; reading the property gives last-writer-wins, `getConflicts` gives all values, and the next
  assignment to the property clears the conflict. [DOC S-5nz523b7]
- `automerge-repo` stores documents as chunks keyed by document ID, chunk type and the document's
  heads or the change's hash, so compaction by several processes needs no concurrency control from
  the storage backend. [DOC S-zmmh2aoz]
- The `NodeFSStorageAdapter` stores data in a local directory and is safe for several processes to
  use on the same data directory. [DOC S-o3lg5zce]

### git: a repository several machines push to
- gitfaq: git works best when work moves with `git push` and `git fetch`; it is not designed to share
  a working tree across systems, which risks repository corruption or data loss. [DOC S-syegds5m]
- gitfaq says never to sync any part of a git repository with a cloud syncing service: such services
  sync file by file and can cause missing objects, broken refs and partial updates. [DOC S-syegds5m]
- Its example: conflicting ref states leave each side with commits the other lacks, and objects that
  become unreferenced can be pruned by `git gc`. [DOC S-syegds5m]
- Uncommitted work can move between machines as stashes: `git stash export --to-ref <ref>`, push
  and fetch that ref, then `git stash import <ref>` (git 2.51 and later); gitfaq calls this the most
  robust approach. [DOC S-syegds5m]
- If a working tree is synced anyway, gitfaq recommends `rsync -a --delete-after` on the repository
  root while nothing (not even `git gc` or an editor) runs on it, with worktrees and a separate git
  directory synced together, backups, and `git fsck` afterwards. [DOC S-syegds5m]
- A single shared repository emulates a central model, since no git repository is inherently more
  important than another; when someone pushed more recently, `git push` complains and the pusher
  must pull before pushing again. [DOC S-3ztu6fdi]
- A shared repository is a bare repository made with `git --bare init --shared`, writable by the
  committers' group. [DOC S-3ztu6fdi]
- `--shared` lets users of the same group push into the repository and sets `core.sharedRepository`;
  in shared repositories `receive.denyNonFastForwards` is on by default, so a forced non-fast-forward
  push is refused. [DOC S-nv6io42x]
- `receive.denyCurrentBranch` (default `refuse`) refuses a push to the checked-out branch of a
  non-bare repository; `updateInstead` updates a clean working tree instead, for syncing working
  directories. [DOC S-ygtpb7no]

### How it fits
- Agent state synced with Syncthing or DFS Replication is safe only with one writer per file: two
  agents writing one memory file on two machines leave one result in a conflict copy (Syncthing,
  synced to all devices) or the `ConflictandDeleted` cache of one server (DFS Replication, which may
  purge it). Per-machine file names, or Syncthing send-only and receive-only folders, keep each file
  to one writer. [DER S-zdnk4m6k, S-bskvvicf, S-trssy6ht: the conflict rules above]
- DFS Replication is not a workstation-to-workstation option: it needs Windows Server members in an
  Active Directory domain, so syncing state between workstations through it means a server hop.
  [DER S-trssy6ht: replication only between Windows Server members, domain only]
- A store that must take concurrent writes from several machines and keep both is a merge problem
  for a CRDT such as Automerge (every key and list insert kept, one deterministic winner per
  property with the loser kept), not for a file syncer. [DER S-5fvc6but, S-5nz523b7, S-zdnk4m6k,
  S-trssy6ht: Automerge merges by operation, the file tools keep whole files]
- A git repository that holds agent state is never placed in a Syncthing, DFS Replication or cloud
  sync folder; machines exchange commits by push and fetch to a bare repository (which may itself
  live on one of the workstations), and a rejected push is the signal to fetch, merge and retry.
  [DER S-syegds5m, S-3ztu6fdi, S-ygtpb7no, S-l6s4hfqp: gitfaq on cloud sync, shared bare
  repository, fast-forward refusal]

## Reference
- Syncthing: `users/syncing.rst` (S-zdnk4m6k), `users/versioning.rst` (S-fmrgts5l),
  `users/foldertypes.rst` (S-bskvvicf) in `syncthing/docs`, CC BY 4.0.
- DFS Replication FAQ (S-trssy6ht); KB 951010 on the folder's size limit (S-y6tixlbj);
  `Get-DfsrPreservedFiles` (S-vpl4l5cd).
- Automerge: Welcome (S-tfj3n5g7), Concepts (S-qinq7hxq), Merge Rules (S-5fvc6but), Conflicts
  (S-5nz523b7), storage pages (S-zmmh2aoz, S-o3lg5zce).
- git v2.55.0: gitfaq "How do I sync a working tree across systems?" (S-syegds5m),
  gitcvs-migration (S-3ztu6fdi), git-init `--shared` (S-nv6io42x), `receive.*` (S-ygtpb7no).
- Related kb articles:
  - `agents/shared-state-concurrency.md`: conditional writes, leases and locks for a store with a
    server.
  - `claude/cross-session-messaging.md`: messages between Claude Code sessions on several machines.
  - `gitlab/git-trailers-and-hooks.md`: fast-forward pushes, `--force-with-lease` and
    `receive.denyNonFastForwards`.

## Examples
- SNIPPET: move uncommitted work from one machine to another as exported stashes; context: git
  2.51+ on both machines, a remote `origin` both can push to; checked: no [DOC S-syegds5m: the
  gitfaq stash export and import commands]
```bash
git stash push
git stash export --to-ref refs/heads/stashes
git push origin stashes
# on the other machine
git fetch origin +stashes:stashes
git stash import stashes
git stash apply
```
