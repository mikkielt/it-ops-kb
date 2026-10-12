---
topic: sqlserver/availability-group-seeding
priority: P2
applies_to: "SQL Server 2016 and later (Always On availability groups, traditional and distributed); Learn documentation version sql-server-ver17"
retrieved_utc: 2026-10-12
sources: [S-7u5iv73w, S-bvigwggq]
status: complete
---

# Always On availability group automatic seeding

## Summary
- Automatic seeding (SQL Server 2016 and later) initializes a secondary replica's databases over the network from the primary, with no backup, copy and restore. Set `SEEDING_MODE = AUTOMATIC` on the secondary replica; the default is `MANUAL`.
- After the secondary joins, run `ALTER AVAILABILITY GROUP [<AGName>] GRANT CREATE ANY DATABASE` **on the secondary**; without that grant the availability group may not create databases there, and the instance logs a warning.
- Monitor with `sys.dm_hadr_automatic_seeding` (history, with `current_state` and `failure_state_desc`) and `sys.dm_hadr_physical_seeding_stats` (running seeds only), plus the SQL Server error log and extended events.
- Seeding uses the database mirroring endpoint, needs the full recovery model, and keeps the primary's transaction log from truncating until it finishes.
- `SEEDING_MODE = MANUAL` on the primary cancels seeds in progress; `DENY CREATE ANY DATABASE` on the secondary blocks new ones without changing the mode.

## Facts
- To configure automatic seeding for an Always On availability group, set `SEEDING_MODE = AUTOMATIC` on each secondary replica in `CREATE AVAILABILITY GROUP` (in the SSMS wizard automatic seeding is the first and default choice), then run `ALTER AVAILABILITY GROUP [<AGName>] JOIN` and `GRANT CREATE ANY DATABASE` on each secondary; SQL Server then creates and seeds the databases without a manual backup and restore. [DOC S-7u5iv73w, S-bvigwggq]
- Automatic seeding was introduced in SQL Server 2016; it streams a backup by VDI over the log stream transport and the configured endpoints to the secondary for each database, at creation of the availability group or when a database is added, in all editions that support availability groups, for traditional and distributed groups. [DOC S-7u5iv73w]
- `SEEDING_MODE` is a replica option with values `AUTOMATIC` and `MANUAL`; `MANUAL`, the default, is the pre-2016 backup, copy and restore with `WITH NORECOVERY`. Setting it on the primary in `CREATE AVAILABILITY GROUP` has no effect until that replica is a secondary. [DOC S-7u5iv73w]
- For a traditional availability group the permission is granted to the availability group on the secondary as it joins: `ALTER AVAILABILITY GROUP [<AGName>] JOIN` then `ALTER AVAILABILITY GROUP [<AGName>] GRANT CREATE ANY DATABASE`, both run on the secondary instance. [DOC S-7u5iv73w, S-bvigwggq]
- If an instance joins as a secondary with `SEEDING_MODE` of `AUTOMATIC` and no grant, its SQL Server log says the replica has not been granted permission to create databases and to use `ALTER AVAILABILITY GROUP ... GRANT CREATE ANY DATABASE`. [DOC S-7u5iv73w]
- When the availability group creates a database on a secondary, "sa" (the account with sid 0x01) owns it; change the owner afterwards with `ALTER AUTHORIZATION`. [DOC S-7u5iv73w]
- For a distributed availability group: no extra grant is needed on a primary of the second group, a single-replica second group should grant `CREATE ANY DATABASE` to the second group's name or seeding may fail, and a secondary of the second group needs `ALTER AVAILABILITY GROUP [<2ndAGName>] GRANT CREATE ANY DATABASE`. [DOC S-7u5iv73w]
- Prerequisites: databases are in the full recovery model with a current full backup and log backup (not used for seeding, but required before joining a group); inbound firewall rules allow the database mirroring endpoint port, since seeding uses that endpoint. [DOC S-bvigwggq]
- Paths: in SQL Server 2016 and before the data and log folders must exist and equal the primary's; SQL Server 2017 allows different paths (for example Windows and Linux replicas) while recommending the same, and trace flag 9571 restores the earlier behaviour. [DOC S-7u5iv73w, S-bvigwggq]
- A database seeded to a secondary reaches `SYNCHRONIZED` when the replica is synchronous and caught up, or `SYNCHRONIZING` when asynchronous or not yet caught up. [DOC S-7u5iv73w]
- A secondary that was seeded by backup and restore can be switched with `ALTER AVAILABILITY GROUP [<AGName>] MODIFY REPLICA ON '<replica>' WITH (SEEDING_MODE = AUTOMATIC)` so later databases seed automatically; `MANUAL` turns it off. [DOC S-7u5iv73w]
- When the secondary already seeded automatically, adding a database to the group needs nothing more; when it was joined with backup and restore, change the seeding mode first and then use the `GRANT` statement while adding the database. [DOC S-7u5iv73w]
- A restore of the database with its logs on the secondary can be combined with automatic seeding to catch it up, as if a tail-log backup were restored. [DOC S-7u5iv73w]
- `DENY CREATE ANY DATABASE` on the availability group, run on the secondary instance, prevents it from creating databases (for a database that must not be seeded yet) without disabling `SEEDING_MODE`. [DOC S-7u5iv73w, S-bvigwggq]
- Run on the primary, `MODIFY REPLICA ... WITH (SEEDING_MODE = AUTOMATIC)` also forces a failed seed to restart (for example after adding disk space on the secondary), and `SEEDING_MODE = MANUAL` cancels replicas currently seeding without stopping synchronization of replicas already initialized. [DOC S-bvigwggq]
- During seeding the primary database's transaction log keeps growing and cannot be truncated until seeding of that database ends, then a log backup truncates it; Microsoft's own example is a 5 TB database over 1 Gb/s taking just over 11 hours at full bandwidth, longer in practice. [DOC S-7u5iv73w, S-bvigwggq]
- The concept page calls seeding single-threaded and able to handle up to five databases, while the how-to page says it uses one thread per LUN on the primary and on the secondary; the pages differ. [DOC S-7u5iv73w, S-bvigwggq]
- Compression of the seeding stream is off by default; trace flag 9567 turns it on (set on the primary), which reduces transfer time and raises CPU use. [DOC S-7u5iv73w, S-bvigwggq]
- Microsoft lists when not to use it: very large databases, a remote secondary, or a busy database whose log would grow during a long initialization; evaluate size, load and distance first. [DOC S-bvigwggq]
- `sys.dm_hadr_automatic_seeding` keeps the history of each run: `current_state` (COMPLETED or FAILED per the concept page), `failure_state`, `failure_state_desc`, `start_time`, `completion_time`, `is_source`, `performed_seeding`, `error_code`; it is populated on the primary and all secondaries, so query both when a database does not appear. [DOC S-7u5iv73w, S-bvigwggq]
- `sys.dm_hadr_physical_seeding_stats` shows only the seeds running now (not retained): `local_database_name`, `role_desc`, `internal_state_desc`, `transfer_rate_bytes_per_second`, `transferred_size_bytes`, `database_size_bytes`, `estimate_time_complete_utc`, `total_disk_io_wait_time_ms`, `total_network_wait_time_ms`, `is_compression_enabled`, and `failure_message` on failure. [DOC S-7u5iv73w, S-bvigwggq]
- The four ways to watch seeding are the SQL Server log, the two DMVs, the `msdb` backup history (a GUID `physical_device_name` in `backupmediafamily`, the primary's name in `backupset`) and extended events such as `hadr_automatic_seeding_state_transition`, `hadr_automatic_seeding_failure` and `hadr_physical_seeding_progress`. [DOC S-7u5iv73w, S-bvigwggq]
- Agent handling: the grant is run on each secondary instance, so a script that only touches the primary cannot finish seeding; check `sys.dm_hadr_automatic_seeding` on every replica before reporting success. [DER S-7u5iv73w, S-bvigwggq]

## Reference
| Item | Value | Source |
|---|---|---|
| Option | `SEEDING_MODE = AUTOMATIC` or `MANUAL` (default) on `ADD REPLICA ON` / `MODIFY REPLICA ON` | S-7u5iv73w |
| Grant (on secondary) | `ALTER AVAILABILITY GROUP [<AGName>] GRANT CREATE ANY DATABASE` | S-7u5iv73w, S-bvigwggq |
| Block new seeds (on secondary) | `ALTER AVAILABILITY GROUP [<AGName>] DENY CREATE ANY DATABASE` | S-7u5iv73w, S-bvigwggq |
| Stop seeding (on primary) | `... MODIFY REPLICA ON '<replica>' WITH (SEEDING_MODE = MANUAL)` | S-bvigwggq |
| History view | `sys.dm_hadr_automatic_seeding` | S-7u5iv73w, S-bvigwggq |
| Live view | `sys.dm_hadr_physical_seeding_stats` | S-7u5iv73w, S-bvigwggq |
| Compression | trace flag 9567 on primary, off by default | S-7u5iv73w, S-bvigwggq |
| Path rule revert | trace flag 9571 | S-7u5iv73w |
| Endpoint | database mirroring, TCP 5022 in the example | S-bvigwggq |

## Examples
- Create a two-replica group with automatic seeding, on the primary `PL-SRV-0042`: `CREATE AVAILABILITY GROUP [AG1] FOR DATABASE db1 REPLICA ON N'PL-SRV-0042' WITH (ENDPOINT_URL = N'TCP://PL-SRV-0042.corp.example.com:5022', FAILOVER_MODE = AUTOMATIC, AVAILABILITY_MODE = SYNCHRONOUS_COMMIT, SEEDING_MODE = AUTOMATIC), N'PL-SRV-0043' WITH (ENDPOINT_URL = N'TCP://PL-SRV-0043.corp.example.com:5022', FAILOVER_MODE = AUTOMATIC, AVAILABILITY_MODE = SYNCHRONOUS_COMMIT, SEEDING_MODE = AUTOMATIC);` [DOC S-7u5iv73w, S-bvigwggq]
- On the secondary `PL-SRV-0043`: `ALTER AVAILABILITY GROUP [AG1] JOIN;` then `ALTER AVAILABILITY GROUP [AG1] GRANT CREATE ANY DATABASE;`. [DOC S-bvigwggq]
- Check progress: `SELECT start_time, completion_time, is_source, current_state, failure_state, failure_state_desc FROM sys.dm_hadr_automatic_seeding;` and `SELECT * FROM sys.dm_hadr_physical_seeding_stats;`. [DOC S-bvigwggq]
- Turn a replica to automatic seeding later, on the primary: `ALTER AVAILABILITY GROUP [AG1] MODIFY REPLICA ON N'PL-SRV-0043' WITH (SEEDING_MODE = AUTOMATIC);`. [DOC S-7u5iv73w, S-bvigwggq]
