---
topic: security/linux-nftables
priority: P3
applies_to: "nftables ruleset files, sets and atomic load with nft -f on Linux hosts"
retrieved_utc: 2026-10-11
sources: [S-nvc4ejpk, S-oz7g4upk, S-h3233m5r, S-ycjp6jnv]
status: complete
---

# nftables ruleset files, sets and atomic load

## Summary
`nft -f FILE` loads a whole ruleset file as one transaction, so a host never runs a half-built firewall. A ruleset file is an `nft` script: a `#!/usr/sbin/nft -f` header, `define` variables, `include` of further files, and tables, chains and named sets. Sets are named (updatable) or anonymous (inline, fixed). The CIS Debian 12 mapping in the SCAP Security Guide treats nftables as a Level 1 Server control.

## Facts
- `nft -f file` reads all included files, builds the new configuration next to the running one and swaps it in with one atomic operation; the nftables wiki contrasts this with a shell script of many `nft` calls, which leaves a partly configured firewall for a moment. [DOC S-nvc4ejpk]
- Loading a ruleset file again without a flush adds every rule twice; putting `flush table <name>` first in the file makes flush and load one kernel transaction, equivalent to `iptables-restore`. [DOC S-nvc4ejpk]
- `flush table` does not clear sets defined in that table; `flush ruleset` (Linux 3.17 and later) or deleting the sets explicitly does. [DOC S-nvc4ejpk]
- A flush statement in any included file runs when the swap happens, not when that file is read, and two included files that both add rules to one table both end up in the chain. [DOC S-nvc4ejpk]
- A native script file starts with the header `#!/usr/sbin/nft -f`, is restored with `nft -f my-ruleset.file`, and supports `#` comments, `include` and `define`. [DOC S-h3233m5r]
- `include` accepts shell wildcards (`*`, `?`, `[]`): matches load in alphabetical order, files starting with a dot are not matched, and a wildcard include with no match is not an error, so an empty drop-in directory is safe. [DOC S-h3233m5r]
- The include search path is set with `-I`/`--includepath`; a leading `./` forces the working directory and a leading `/` an absolute path. [DOC S-h3233m5r]
- `define NAME = { a, b }` defines a variable that can hold a set; it is referenced as `$NAME` in rules. [DOC S-h3233m5r, S-oz7g4upk]
- An anonymous set is written inline in a rule (`tcp dport { 22, 23 }`), is released with its rule and cannot be updated afterwards; a named set (`nft add set ... `) can be updated at any time and is referenced as `@name`. [DOC S-oz7g4upk]
- A named set takes `type` or `typeof` (`typeof` since nftables 0.9.4), `flags` (`constant`, `interval`, `timeout`), `timeout`, `gc-interval`, `elements`, `size`, `policy` and `counter` (since 0.9.5). [DOC S-oz7g4upk]
- Interval sets with overlapping elements fail to load with "conflicting intervals specified" unless the set has `auto-merge`, which collapses adjacent or overlapping elements. [DOC S-oz7g4upk]
- The wiki states that a set name has at most 16 characters and that a set `comment` needs nftables 0.9.7 and kernel 5.10. [DOC S-oz7g4upk]
- In the SSG control file for CIS Debian 12 (benchmark v1.1.0 mapping), recommendations 4.3.1 to 4.3.10 cover nftables (installed, a table exists, base chains exist, loopback traffic, default deny policy, service enabled, rules permanent); all are Level 1 Server and Level 1 Workstation, two are manual (outbound and established connections; iptables flushed). [CODE S-ycjp6jnv: controls/cis_debian12.yml#4.3.1]
- One ruleset file that begins with `flush ruleset` (or `flush table`) and is applied with `nft -f` is therefore a single idempotent step for a pull agent: a second run swaps in the same content. [DER S-nvc4ejpk: atomic swap plus flush-first avoids duplicate rules]

## Reference
| need | form | source |
|---|---|---|
| load atomically | `nft -f FILE` | S-nvc4ejpk |
| script header | `#!/usr/sbin/nft -f` | S-h3233m5r |
| variable | `define NAME = { ... }`, `$NAME` | S-h3233m5r |
| drop-in directory | `include "/etc/nftables.d/*.nft"` style wildcard | S-h3233m5r |
| named set | `set NAME { type ...; flags ...; elements = {...} }`, `@NAME` | S-oz7g4upk |

Not read: the `nft` manual's syntax-check-only option and how each distribution loads `/etc/nftables.conf` at boot (see `_gaps.md`, topic `security/linux-nftables`).

## Examples
- SNIPPET: a ruleset file that replaces its own table atomically and keeps an updatable allow set; context: nftables 0.9.4 or later, placeholder documentation addresses; checked: no [DER S-nvc4ejpk, S-h3233m5r, S-oz7g4upk: flush-first file, `define`, named set]
```
#!/usr/sbin/nft -f
flush ruleset
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
