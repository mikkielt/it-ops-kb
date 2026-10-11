---
topic: security/linux-sshd-hardening
priority: P3
applies_to: "OpenSSH sshd on Linux: sshd_config options graded by the CIS mapping, and sshd -T"
retrieved_utc: 2026-10-11
sources: [S-o5hziwt7, S-rkyl5ijj, S-ycjp6jnv]
status: complete
---

# sshd_config options CIS grades and sshd -T

## Summary
`sshd -T` prints the effective configuration after `Include` and `Match` are applied, so it is the read to compare against a baseline rather than the file. The SCAP Security Guide's CIS Debian 12 mapping names 22 sshd recommendations (5.1.1 to 5.1.22); most are Level 1 Server, two are Level 2 Server only. This article is about OpenSSH on Linux; OpenSSH on Windows is in `windows/openssh-server.md`.

## Facts
- `sshd -T` is extended test mode: it checks the configuration file, writes the effective configuration to standard output and exits; `sshd -t` only checks validity and key sanity and is meant for updating sshd reliably. [DOC S-rkyl5ijj]
- `sshd -T -C addr=...,user=...,host=...` (keywords `addr`, `user`, `host`, `laddr`, `lport`, `rdomain`) applies the `Match` blocks that fit those connection parameters before the configuration is printed. [DOC S-rkyl5ijj]
- For each `sshd_config` keyword the first obtained value is used, keywords are case-insensitive and arguments case-sensitive; a `Match` block overrides the global section until the next `Match` or the end of the file, and if a keyword is set in several satisfied `Match` blocks only the first applies. [DOC S-o5hziwt7]
- `Include` pulls in further files, processes them in lexical order, resolves relative names under `/etc/ssh`, and may appear inside a `Match` block. [DOC S-o5hziwt7]
- `AllowUsers`, `AllowGroups`, `DenyUsers` and `DenyGroups` may each appear several times and append to their list; `AllowGroups` is not consulted for groups matched by `DenyGroups`. [DOC S-o5hziwt7]
- Level 1 Server recommendations in the SSG control file for CIS Debian 12 (benchmark v1.1.0 mapping): permissions of `sshd_config` and host key files (5.1.1 to 5.1.3), access limited by Allow/Deny keywords (5.1.4), `Banner`, `Ciphers`, `ClientAliveInterval` and `ClientAliveCountMax`, `HostbasedAuthentication` off, `IgnoreRhosts` on, `KexAlgorithms`, `LoginGraceTime`, `LogLevel`, `MACs`, `MaxAuthTries`, `MaxSessions`, `MaxStartups`, `PermitEmptyPasswords` off, `PermitRootLogin` off, `PermitUserEnvironment` off and `UsePAM` on. [CODE S-ycjp6jnv: controls/cis_debian12.yml#5.1]
- In that file `DisableForwarding` enabled (5.1.8) and `GSSAPIAuthentication` disabled (5.1.9) are graded Level 1 Workstation and Level 2 Server, not Level 1 Server. [CODE S-ycjp6jnv: controls/cis_debian12.yml#5.1.8]
- The mapping's variables for the numeric options are: login grace time 60, max auth tries 4, max sessions 10, `MaxStartups` `10:30:60`, idle timeout 5 minutes and keepalive count 3; its notes say remediation of the access rule is not automated to avoid lockout. [CODE S-ycjp6jnv: controls/cis_debian12.yml#5.1]
- Comparing a host to these options by reading `sshd_config` alone is unreliable because of first-value-wins, `Include` and `Match`; reading the `sshd -T` output (lower-case keys) gives the values sshd actually uses. [DER S-rkyl5ijj, S-o5hziwt7: effective configuration after Include and Match]
- The CIS PDF itself, which carries the authoritative audit text for each option, is not read here (CIS terms allow paraphrase only); the grades above are the SSG project's mapping, not CIS's own text. [DER S-ycjp6jnv: mapping file, not the benchmark]

## Reference
| need | command | source |
|---|---|---|
| validate before reload | `sshd -t` | S-rkyl5ijj |
| effective config | `sshd -T` | S-rkyl5ijj |
| effective config for one connection | `sshd -T -C user=U,host=H,addr=A` | S-rkyl5ijj |

## Examples
- SNIPPET: read the effective values of three graded options; context: OpenSSH sshd on Linux, root; checked: no [DER S-rkyl5ijj: `-T` prints effective configuration]
```
sshd -T | grep -E '^(permitrootlogin|maxauthtries|logingracetime) '
```
