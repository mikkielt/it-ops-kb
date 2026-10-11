---
topic: security/linux-auditd
priority: P3
applies_to: "Linux Audit (auditd): rules.d fragments, augenrules and the immutable flag"
retrieved_utc: 2026-10-11
sources: [S-5anwnaht, S-inxocyfb, S-pay33npd, S-ycjp6jnv]
status: complete
---

# auditd rules under /etc/audit/rules.d, augenrules and immutable mode

## Summary
Audit rules are written as `.rules` fragments in `/etc/audit/rules.d/`, merged by `augenrules` into `/etc/audit/audit.rules` and loaded into the kernel. `-e 2` locks the configuration until reboot. In the SCAP Security Guide's CIS Debian 12 mapping every auditd recommendation, immutability included, is Level 2, not Level 1.

## Facts
- `augenrules` merges the component files of `/etc/audit/rules.d` into `/etc/audit/audit.rules`; only files whose names end in `.rules` are processed and all other files in the directory are ignored. [DOC S-5anwnaht]
- The fragments are concatenated in natural sort order (`ls -v`) and stripped of empty and `#` comment lines. [DOC S-5anwnaht]
- In the merged file the last `-D` without an option comes first, the last `-b` second, the last `-f` third and the last `-e` last; a `-D` with an option stays in place. [DOC S-5anwnaht]
- The merged file is copied to `audit.rules` only if it differs; `augenrules --check` tests for a change without overwriting, and `augenrules --load` loads old or new rules into the kernel. [DOC S-5anwnaht]
- `auditctl -e 0` temporarily disables auditing, `-e 1` enables it and `-e 2` locks the configuration: it is meant as the last command in `audit.rules`, later attempts to change the configuration are audited and denied, and only a reboot unlocks it. [DOC S-inxocyfb]
- `auditctl --loginuid-immutable` makes login uids unchangeable once set, which is tamper-proof but can cause problems in some containers. [DOC S-inxocyfb]
- Audit rules come in three kinds, control, file and syscall; control rules (delete all rules, backlog size, failure mode, rate limit, ignore syntax errors) usually sit at the top of the rules file. [DOC S-pay33npd]
- io_uring rules take no arch field, for example `-a always,io_uring -S openat,openat2 -F key=access`. [DOC S-pay33npd]
- In the SSG control file for CIS Debian 12 (benchmark v1.1.0 mapping) all of section 6.2 (auditd installed and active, backlog limit, log storage, 6.2.3.1 to 6.2.3.19 event collection) is Level 2 Server and Level 2 Workstation; none is Level 1. [CODE S-ycjp6jnv: controls/cis_debian12.yml#6.2]
- The same file maps "Ensure the audit configuration is immutable" (6.2.3.20) to rule `audit_rules_immutable` and marks "running and on disk configuration is the same" (6.2.3.21) as manual. [CODE S-ycjp6jnv: controls/cis_debian12.yml#6.2.3.20]
- Because `augenrules` always emits the last `-e` last, one late-sorting fragment (for example a `99-finalize.rules` carrying `-e 2`) is enough to lock the merged ruleset. [DER S-5anwnaht: last `-e` is emitted as the last line]
- A host locked with `-e 2` takes new rules only after a reboot, so a pull agent that changes audit rules must treat the change as reboot-gated or leave `-e 2` out on hosts where it applies rules. [DER S-inxocyfb: only a reboot changes a locked configuration]

## Reference
| file or command | role | source |
|---|---|---|
| `/etc/audit/rules.d/*.rules` | fragments, natural sort order | S-5anwnaht |
| `/etc/audit/audit.rules` | merged output of `augenrules` | S-5anwnaht |
| `augenrules --check` / `--load` | test for change / load into kernel | S-5anwnaht |
| `auditctl -e 0|1|2` | off / on / locked until reboot | S-inxocyfb |

Not read: the `auditd.conf` options and the distributions' package defaults for `rules.d` (see `_gaps.md`, topic `security/linux-auditd`).

## Examples
- SNIPPET: a fragment that audits changes to the sudoers file and locks the configuration; context: auditd with augenrules, file name sorts last; checked: no [DER S-5anwnaht, S-inxocyfb, S-pay33npd: `.rules` suffix, last `-e` emitted last, `-e 2` locks]
```
# /etc/audit/rules.d/99-finalize.rules
-w /etc/sudoers -p wa -k scope
-e 2
```
