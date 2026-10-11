---
topic: security/linux-patching-and-pins
priority: P3
applies_to: "Automatic upgrades off and package pins by date, point release or branch on Debian, Ubuntu, AlmaLinux and Alpine"
retrieved_utc: 2026-10-11
sources: [S-4npfgqu6, S-cgiu2l7l, S-eln4odmb, S-jv7bm5xz, S-ha4j7gxc, S-jc64e5xb, S-e5dd7vv5, S-l6wf2hvq, S-mt66jy4n, S-6w34pn5d]
status: partial
---

# Automatic upgrades off and package pins

## Summary
Hosts that a pull agent keeps at a known package state need the distribution's own upgrade jobs off and the package source fixed to a date, a point release or a release branch. Debian and Ubuntu have dated archive snapshots, AlmaLinux has a vault of older minor releases, Alpine fixes the branch in the repository URL (`vX.Y`). No source read describes pinning by an index hash.

## Facts
- Debian's `apt.systemd.daily` script is driven by `APT::Periodic` options: `Update-Package-Lists`, `Download-Upgradeable-Packages` and `Unattended-Upgrade` each take a number of days with 0 disabling the job, and `APT::Periodic::Enable "0"` disables the whole script. [DOC S-4npfgqu6]
- `APT::Periodic::Unattended-Upgrade` runs the `unattended-upgrade` script, needs the `unattended-upgrades` package and logs under `/var/log/unattended-upgrades`. [DOC S-4npfgqu6]
- `apt-daily.timer` fires at 06:00 and 18:00 with `RandomizedDelaySec=12h` and `Persistent=true`; `apt-daily-upgrade.timer` fires daily at 06:00 with `RandomizedDelaySec=60m`, ordered after `apt-daily.timer`. [DOC S-cgiu2l7l, S-eln4odmb]
- unattended-upgrades is activated by `APT::Periodic::Update-Package-Lists "1";` and `APT::Periodic::Unattended-Upgrade "1";`, which checks daily and installs when possible; by default only the stable and security archives are applied. [DOC S-jv7bm5xz]
- Its origins are `Unattended-Upgrade::Allowed-Origins` or `Origins-Pattern` in `/etc/apt/apt.conf.d/50unattended-upgrades`; local changes belong in a separate fragment that sorts later (for example `52unattended-upgrades-local`), and `Package-Blacklist` holds regular expressions of packages never upgraded. [DOC S-jv7bm5xz]
- `unattended-upgrade --debug --dry-run` shows what it would do and writes `/var/log/unattended-upgrades/unattended-upgrades.log`. [DOC S-jv7bm5xz]
- Both apt timers only start jobs that the `APT::Periodic` options gate, so one apt configuration fragment with `APT::Periodic::Enable "0"` turns the periodic update and upgrade off without editing units. [DER S-4npfgqu6, S-cgiu2l7l, S-eln4odmb: script exits when Enable is 0; the service files that call it were not read]
- `dnf-automatic` reads `/etc/dnf/automatic.conf` and is started by a systemd timer; the units `dnf-automatic-notifyonly`, `dnf-automatic-download` and `dnf-automatic-install` override the file to notify only, download only, or download and install. [DOC S-ha4j7gxc]
- In `[commands]`, `apply_updates` defaults to False, `upgrade_type` is `default` or `security`, and `reboot` is `never`, `when-changed` or `when-needed` with default `never`; the timers add a random delay of up to one hour. [DOC S-ha4j7gxc]
- On a host where no `dnf-automatic*.timer` is enabled, dnf-automatic does nothing; keeping it off is a state of enabled timers, not a configuration key. [DER S-ha4j7gxc: the tool runs only from its timer units]
- snapshot.debian.org is described as a wayback machine for old packages by date and version numbers, usable like a normal apt repository, with archives `debian`, `debian-security`, `debian-backports`, `debian-ports` and others. [DOC S-jc64e5xb]
- The Ubuntu snapshot service serves the archive as of any UTC time after 1 March 2023; a snapshot id is `YYYYMMDDTHHMMSSZ`, used as `apt install PKG --update --snapshot ID` (short `-S`). [DOC S-e5dd7vv5]
- Ubuntu 24.04 and later need no source change; 22.04 needs apt 2.4.11 or later and 20.04 apt 2.0.10 or later, with `[snapshot=yes]` added to each `sources.list` entry; without the option apt reads the normal archive again. [DOC S-e5dd7vv5]
- The Ubuntu page warns that a snapshot can hold package versions with known vulnerabilities, so a snapshot date is a pin to review, not a security baseline. [DOC S-e5dd7vv5]
- AlmaLinux moved its vault, the repositories of older versions, to `https://vault.almalinux.org` as the official HTTP(S) endpoint in 2024; `https://repo.almalinux.org/vault` stays as a redirect, and the rsync source became `rsync.vault.almalinux.org`. [DOC S-l6wf2hvq]
- Each stable Alpine release branch has its own `main` and `community` repositories; `testing` exists only on `edge`; the wiki says not to use `edge` where deterministic, repeatable installation by pinning is wanted. [DOC S-mt66jy4n]
- `/etc/apk/repositories` lists one repository URL per line; the Alpine wiki's examples use the form `https://dl-cdn.alpinelinux.org/alpine/vX.Y/community`, with an optional `@tag` prefix. [DOC S-mt66jy4n, S-6w34pn5d]
- `apk add pkg=1.6.0.21-r0` holds a package at a version, `apk add 'pkg=~1.6'` at a minor series; `/etc/apk/world` stores the constraints as `[!]NAME{@tag}{[<>~=]version}`; the wiki warns that a pinned version can disappear from the repository. [DOC S-6w34pn5d]
- Pinning by an index hash (a hash of a repository index or `Release` file) is described by none of the pages read for apt, dnf or apk; the nearest read mechanisms are the dated snapshots and the release-branch path. [UNK: no source found, logged in `_gaps.md`]
- A pin per family follows from these facts: Debian a `snapshot.debian.org` timestamp URL, Ubuntu a snapshot id, AlmaLinux a vault minor-release path, Alpine the `vX.Y` branch; each is set in the package source file the agent writes. [DER S-jc64e5xb, S-e5dd7vv5, S-l6wf2hvq, S-mt66jy4n: one dated or versioned source per family]

## Reference
| family | pin by | upgrade jobs to keep off | source |
|---|---|---|---|
| Debian | snapshot.debian.org timestamp | `APT::Periodic` options, apt-daily timers | S-jc64e5xb, S-4npfgqu6 |
| Ubuntu | `--snapshot YYYYMMDDTHHMMSSZ` | same | S-e5dd7vv5, S-4npfgqu6 |
| AlmaLinux | vault minor release | `dnf-automatic*.timer` | S-l6wf2hvq, S-ha4j7gxc |
| Alpine | `vX.Y` repository path, `pkg=ver` | none stated (no periodic job in the pages read) | S-mt66jy4n, S-6w34pn5d |

## Examples
- SNIPPET: switch the periodic apt jobs off with one fragment; context: Debian or Ubuntu with apt; checked: no [DER S-4npfgqu6: `APT::Periodic::Enable` 0 disables the script]
```
// /etc/apt/apt.conf.d/99-no-periodic
APT::Periodic::Enable "0";
```
