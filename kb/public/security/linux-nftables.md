---
topic: security/linux-nftables
priority: P3
applies_to: "nftables ruleset files, sets and atomic load with nft -f on Linux hosts"
retrieved_utc: 2026-10-13
sources: [S-nvc4ejpk, S-oz7g4upk, S-h3233m5r, S-ycjp6jnv, S-t7vpftda]
status: partial
---

# nftables ruleset files, sets and atomic load

## Summary
`nft -f FILE` loads a whole ruleset file as one transaction, so a host never runs a half-built firewall. A ruleset file is an `nft` script: a `#!/usr/sbin/nft -f` header, `define` variables, `include` of further files, and tables, chains and named sets. Sets are named (updatable) or anonymous (inline, fixed). `flush table` empties one table; `flush ruleset` removes every table on the host, so a file that starts with it owns the whole ruleset. The CIS Debian 12 mapping in the SCAP Security Guide treats nftables as a Level 1 Server control.

## Facts
- `nft -f file` reads all included files, builds the new configuration next to the running one and swaps it in with one atomic operation; the nftables wiki contrasts this with a shell script of many `nft` calls, which leaves a partly configured firewall for a moment. [DOC S-nvc4ejpk]
- Loading a ruleset file again without a flush adds every rule twice; putting `flush table <name>` first in the file makes flush and load one kernel transaction, equivalent to `iptables-restore`. [DOC S-nvc4ejpk]
- `flush table` does not clear sets defined in that table; `flush ruleset` (Linux 3.17 and later) or deleting the sets explicitly does. [DOC S-nvc4ejpk]
- A flush statement in any included file runs when the swap happens, not when that file is read, and two included files that both add rules to one table both end up in the chain. [DOC S-nvc4ejpk]
- The wiki notes that loading a file exported with `nft list table` may fail because the table does not exist yet, so the table may have to be created first (`nft create table ip filter`); it adds that newer nftables releases behave more consistently. [DOC S-nvc4ejpk]
- `flush ruleset` clears the whole ruleset: the manual says that, unlike iptables, it removes all tables and whatever they contain, leaving an empty ruleset with no packet filtering, so the kernel accepts any valid packet. [DOC S-t7vpftda]
- `flush ruleset` can be limited to one address family; `flush table [family] table` flushes all chains and rules of the one named table, and `flush set` removes all elements of one set. [DOC S-t7vpftda]
- Compared with `flush table <family> <name>`, which limits the clearing to the file's own table, an `nft -f` file whose first statement is a bare `flush ruleset` removes every table on the host, including the tables other roles or tools created, in the same transaction that adds the file's own tables. [DER S-nvc4ejpk, S-t7vpftda: the manual's "all tables" plus the wiki's single transaction]
- `-c`/`--check` makes `nft` check the validity of commands without applying the changes, so `nft -c -f FILE` can test a file that starts with `flush ruleset` before it empties the host's ruleset. [DER S-t7vpftda: the manual's `-c, --check` option applied to an `-f` file]
- A table created with the `owner` flag "excludes other processes from manipulating it or its contents" and by default is removed when its owning process exits; the `persist` flag keeps it as an orphan that accepts a new owner. [DOC S-t7vpftda]
- Open: the manual does not say whether `flush ruleset` from another process skips or fails on an `owner` table. [UNK: not stated on the manual page read]
- A native script file starts with the header `#!/usr/sbin/nft -f`, is restored with `nft -f my-ruleset.file`, and supports `#` comments, `include` and `define`. [DOC S-h3233m5r]
- `include` accepts shell wildcards (`*`, `?`, `[]`): matches load in alphabetical order, files starting with a dot are not matched, and a wildcard include with no match is not an error, so an empty drop-in directory is safe. [DOC S-h3233m5r]
- The include search path is set with `-I`/`--includepath`; a leading `./` forces the working directory and a leading `/` an absolute path. [DOC S-h3233m5r]
- `define NAME = { a, b }` defines a variable that can hold a set; it is referenced as `$NAME` in rules. [DOC S-h3233m5r, S-oz7g4upk]
- An anonymous set is written inline in a rule (`tcp dport { 22, 23 }`), is released with its rule and cannot be updated afterwards; a named set (`nft add set ... `) can be updated at any time and is referenced as `@name`. [DOC S-oz7g4upk]
- A named set takes `type` or `typeof` (`typeof` since nftables 0.9.4), `flags` (`constant`, `interval`, `timeout`), `timeout`, `gc-interval`, `elements`, `size`, `policy` and `counter` (since 0.9.5). [DOC S-oz7g4upk]
- Interval sets with overlapping elements fail to load with "conflicting intervals specified" unless the set has `auto-merge`, which collapses adjacent or overlapping elements. [DOC S-oz7g4upk]
- The wiki states that a set name has at most 16 characters and that a set `comment` needs nftables 0.9.7 and kernel 5.10. [DOC S-oz7g4upk]
- In the SSG control file for CIS Debian 12 (benchmark v1.1.0 mapping), recommendations 4.3.1 to 4.3.10 cover nftables (installed, a table exists, base chains exist, loopback traffic, default deny policy, service enabled, rules permanent); all are Level 1 Server and Level 1 Workstation, two are manual (outbound and established connections; iptables flushed). [CODE S-ycjp6jnv: controls/cis_debian12.yml#4.3.1]
- A ruleset file whose first statement is `flush table inet NAME` and that is applied with `nft -f` is a single idempotent step for a pull agent that owns only that table: a second run swaps in the same content and clears nothing else, so the tables other roles own on the host stay. The table has to exist before the file loads (`nft create table inet NAME`, as the wiki advises). The same file with a bare `flush ruleset` first removes every table on the host, so it fits only a host the agent owns outright. [DER S-nvc4ejpk, S-t7vpftda: atomic swap plus flush-first avoids duplicate rules; `flush table` limits the clearing to one table, `flush ruleset` removes all tables]

## Reference
| need | form | source |
|---|---|---|
| load atomically | `nft -f FILE` | S-nvc4ejpk |
| replace one role's table | `flush table inet NAME` first in the file | S-nvc4ejpk, S-t7vpftda |
| replace the host's whole ruleset | `flush ruleset` (optionally one family) first in the file | S-t7vpftda |
| script header | `#!/usr/sbin/nft -f` | S-h3233m5r |
| variable | `define NAME = { ... }`, `$NAME` | S-h3233m5r |
| drop-in directory | `include "/etc/nftables.d/*.nft"` style wildcard | S-h3233m5r |
| named set | `set NAME { type ...; flags ...; elements = {...} }`, `@NAME` | S-oz7g4upk |

Not read: how each distribution loads `/etc/nftables.conf` at boot (see `_gaps.md`, topic `security/linux-nftables`).

## Examples
- SNIPPET: a ruleset file that replaces only the agent's own table `inet filter` atomically (the tables other roles own are not touched; a bare `flush ruleset` first would remove them too, as in the facts above) and keeps an updatable allow set; context: nftables 0.9.4 or later, the table created beforehand with `nft create table inet filter`, placeholder documentation addresses; `flush table` leaves a loaded set's elements in place, so a reload onto a table whose set already holds elements is not covered by the sources read; checked: no [DER S-nvc4ejpk, S-t7vpftda, S-h3233m5r, S-oz7g4upk: flush-first file, `define`, named set]
```
#!/usr/sbin/nft -f
flush table inet filter
define ssh_admins = { 192.0.2.10, 192.0.2.11 }
table inet filter {
  set admin_nets { type ipv4_addr; flags interval; elements = $ssh_admins }
  chain input {
    type filter hook input priority 0; policy drop;
    ct state established,related accept
    iif lo accept
    tcp dport 22 ip saddr @admin_nets accept
  }
}
```
