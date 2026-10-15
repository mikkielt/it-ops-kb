---
topic: security/almalinux-elevate
priority: P3
applies_to: "ELevate: in-place major-version upgrades of RHEL-family hosts to AlmaLinux with Leapp (7 to 8, 8 to 9, 9 to 10), its steps, the --target option and the offline mirror variant"
retrieved_utc: 2026-10-15
sources: [S-fvvvkcwq, S-zdchbjj6, S-leb3x6jn, S-4jok2hag, S-23s23lr2]
status: partial
---

# ELevate: in-place major upgrades to AlmaLinux

## Summary
ELevate is the AlmaLinux project's in-place upgrade path between major versions of RHEL-family systems. It runs Leapp with AlmaLinux's patches and data packages: a `preupgrade` check writes a report without installing anything, `upgrade` stages the transaction and reboots into an upgrade initramfs. It does one major step at a time, so a CentOS 7 host reaches AlmaLinux 10 in stages. Minor-release dates are in `security/almalinux-lifecycle-rhel-relation.md`, repositories in `security/almalinux-repositories-vault-pins.md`. Read from the project's wiki at commit `be0a2222` on 2026-10-15.

## Facts
- The project supports upgrades between major versions of RHEL derivatives; Leapp and a few patches handle CentOS 7 to EL8, EL8 to EL9 and EL9 to EL10, and the Red Hat Upgrade Tool handles CentOS 6 to CentOS 7. [DOC S-fvvvkcwq]
- It is designed for one-step upgrades: a CentOS 7 host going to AlmaLinux 10 follows a three-stage guide. [DOC S-fvvvkcwq]
- The source system must be CentOS 7 for EL8, AlmaLinux 8 or CentOS Stream 8 for EL9, and AlmaLinux 9 or CentOS Stream 9 for EL10, and must be fully updated and rebooted first. [DOC S-zdchbjj6]
- The quickstart installs the `elevate-release` package from `repo.almalinux.org/elevate/`, then `leapp-upgrade` and one data package: `leapp-data-almalinux`, `leapp-data-almalinux-kitten` (AlmaLinux 9 to Kitten 10) or `leapp-data-centos` (to CentOS Stream). [DOC S-zdchbjj6]
- `leapp preupgrade` writes `/var/log/leapp/leapp-report.txt` and installs no RPM packages; the page warns that the check fails on a default install because requirements are not met. [DOC S-zdchbjj6]
- In some configurations Leapp writes `/var/log/leapp/answerfile` with true/false questions that must be answered before the upgrade proceeds, with `leapp answer --section <name>=True`. [DOC S-zdchbjj6]
- The popular fixes for an RHEL8-based source are `AllowZoneDrifting=no` in `/etc/firewalld/firewalld.conf` and `leapp answer --section check_vdo.confirm=True`; for an RHEL9-based source the page names unsupported x86_64_v2 hardware as the usual inhibitor. [DOC S-zdchbjj6]
- `leapp upgrade` is followed by a reboot into a GRUB entry `ELevate-Upgrade-Initramfs`, and the page recommends checking `/etc/redhat-release`, the leftover `el7`, `el8` or `el9` packages and `/var/log/leapp/leapp-upgrade.log` afterwards. [DOC S-zdchbjj6]
- The pages warn to have backups or snapshots and to rehearse in a sandbox before production; ELevate does not support the Raspberry Pi images. [DOC S-zdchbjj6]
- Upgrades to AlmaLinux 10 or Kitten 10 on `x86_64_v2` hardware are supported only by the ELevate NG version of Leapp, which the project documents separately for testing. [DOC S-fvvvkcwq]
- Third-party repository support covers EPEL (upgrades to AlmaLinux only, and only for EL9 packages that exist for EL10, the rest stay as they are), Docker CE, MariaDB, nginx, PostgreSQL, Imunify, KernelCare, TuxCare and ELevate's own. [DOC S-fvvvkcwq]
- An entry dated 2024-10-18 in the changelog added a `--target` option to elevate to AlmaLinux 8.7 to 8.10 and 9.0 to 9.4, and removed 9.5 until it was released; a later entry (2024-11-18) made the upgrade repository files use `$releasever` instead of the major version. [DOC S-leb3x6jn]
- For an air-gapped host the offline guide needs a host with Internet access that mirrors `rsync://rsync.repo.almalinux.org/almalinux/` and `.../almalinux-elevate/` to local directories, sized at least 500 GB per major version (1.5 TB for 8, 9 and 10), refreshed by cron every 3 hours. [DOC S-4jok2hag]
- CentOS 7's own repositories are offline, so the quickstart tells CentOS 7 sources to swap to the CentOS vault or to the project's `el7.repo.almalinux.org` copy of `CentOS-Base.repo`. [DOC S-zdchbjj6]
- Separate from ELevate, the FAQ points CentOS and CentOS Stream hosts at the `almalinux-deploy` tool, which migrates a host to AlmaLinux from other Linux distributions. [DOC S-23s23lr2]
- An agent should treat `leapp preupgrade` as the read-only step of an upgrade runbook and `leapp upgrade` as an operation that reboots a host into an initramfs, so it needs the approval tier of a reboot, a snapshot first and a local mirror on an isolated host. [DER S-zdchbjj6, S-4jok2hag: preupgrade installs no package, the upgrade ends in a reboot, the offline guide needs mirrors]
- The target minor an unqualified `leapp upgrade` reaches today, whether a `--target` value still exists in the current Leapp data, and ELevate NG's release status were not read. [UNK: logged in `_gaps.md`]

## Reference
| step | command | writes |
|---|---|---|
| prepare | `yum update -y`, reboot | fully updated host |
| install | `yum install -y http://repo.almalinux.org/elevate/elevate-release-latest-el$(rpm --eval %rhel).noarch.rpm`, then `leapp-upgrade leapp-data-almalinux` | ELevate repo, GPG key, Leapp |
| check | `leapp preupgrade` | `/var/log/leapp/leapp-report.txt`, `answerfile` |
| upgrade | `leapp upgrade`, reboot | `ELevate-Upgrade-Initramfs` GRUB entry, `leapp-upgrade.log` |

Related: `security/almalinux-lifecycle-rhel-relation.md`, `security/almalinux-repositories-vault-pins.md`, `security/linux-patching-and-pins.md`.

## Examples
- SNIPPET: the read-only check of an 8 to 9 upgrade; context: AlmaLinux 8 host, fully updated, as root through sudo; checked: no [DER S-zdchbjj6: the quickstart's install and preupgrade commands, without the upgrade step]
```
sudo yum install -y http://repo.almalinux.org/elevate/elevate-release-latest-el$(rpm --eval %rhel).noarch.rpm
sudo yum install -y leapp-upgrade leapp-data-almalinux
sudo leapp preupgrade
```
