---
topic: security/almalinux-lifecycle-rhel-relation
priority: P3
applies_to: "AlmaLinux OS 8, 9 and 10: support windows per major and minor release, release table, ABI compatibility with RHEL and what the distribution adds"
retrieved_utc: 2026-10-15
sources: [S-w2hsvwk5, S-23s23lr2, S-frwlmyiy, S-76yqvj4g, S-46pbwuai, S-abrr4vdk, S-ecy4u4kc]
status: partial
---

# AlmaLinux release lifecycle and its relation to RHEL

## Summary
AlmaLinux gives each major version (8, 9, 10) a published active-support and security-support end date, and ends each minor release the day the next minor ships, so a host kept on one minor stops receiving fixes at that point. Since July 2023 the project aims at ABI compatibility with RHEL, not at a bit-for-bit rebuild, and builds from RHEL and CentOS Stream sources. Repository names, the vault and pins are in `security/almalinux-repositories-vault-pins.md`, upgrades between majors in `security/almalinux-elevate.md`. Facts below are read from the project's wiki at commit `be0a2222` on 2026-10-15.

## Facts
- AlmaLinux OS 10 has active support until 31 May 2030 and security support until 31 May 2035. [DOC S-w2hsvwk5]
- AlmaLinux OS 9 has active support until 31 May 2027 and security support until 31 May 2032. [DOC S-w2hsvwk5]
- AlmaLinux OS 8 had active support until 31 May 2024 and has security support until 31 May 2029; the page words all three in the future tense ("will have"), so on 2026-10-15 version 8 is in its security-only phase. [DOC S-w2hsvwk5]
- The FAQ states a commitment to security updates and bug fixes for 10 years for each major version; its support table lists only `8.x` (2029) and `9.x` (2032), with no row for 10. [DOC S-23s23lr2]
- Each minor version reaches end of life when the next minor is released; the page's examples are 9.2 ending with 9.3 and 8.9 ending with 8.10. [DOC S-w2hsvwk5, S-23s23lr2]
- The release table lists, with release date: 10.0 on 27 May 2025, 10.1 on 24 Nov 2025, 10.2 on 26 May 2026; 9.7 on 17 Nov 2025, 9.8 on 26 May 2026; 8.10 on 28 May 2024. Beta rows at retrieval are 10.3 (10 Sep 2026) and 9.9 (17 Sep 2026), with no 8.11 row. [DOC S-w2hsvwk5]
- Together these give, on 2026-10-15, the last released minors 10.2, 9.8 and 8.10 as the only supported minors, and a host on 10.1 or 9.7 as already past the minor's end of life. [DER S-w2hsvwk5: end of life of a minor is the next minor's release date, applied to the table]
- AlmaLinux OS Kitten 10 has its active support matched to the end of CentOS Stream 10; its first row is "Lion Cub", dated 22 Oct 2024. [DOC S-w2hsvwk5]
- Four architectures are supported: x86_64, aarch64, ppc64le and s390x, with parity with upstream. [DOC S-23s23lr2]
- The release table adds `x86_64_v2` for version 10 and marks i686 as userspace only, with no bootable installer and no 32-bit kernel; i686 repositories are kept in the vault. [DOC S-w2hsvwk5]
- The release is identified on a host by `cat /etc/almalinux-release`. [DOC S-w2hsvwk5]
- In July 2023 the project moved its goal from a downstream rebuild of RHEL to ABI compatibility with RHEL: applications and kernel modules that work on RHEL are to work on AlmaLinux, and a failure is treated as a bug. [DOC S-23s23lr2]
- The announcement defines binary/ABI compatibility as applications built to run on RHEL (or RHEL clones) running on AlmaLinux without issue, which covers kernel and application compatibility and removes the need for every package to be an exact copy of RHEL's source. [DOC S-76yqvj4g]
- AlmaLinux builds from package sources of both RHEL and CentOS Stream, plus other upstream sources, after Red Hat stopped publishing RHEL sources to git.centos.org in June 2023. [DOC S-frwlmyiy]
- The project's own comparison table lists AlmaLinux as aiming at compatibility with the corresponding RHEL minor version (CentOS Stream: the major version), a 10-year lifecycle, public errata at `errata.almalinux.org`, KernelCare for live patching and third-party commercial support. [DOC S-frwlmyiy]
- New releases follow RHEL's within about a day or two, and updates generally arrive within 24 hours. [DOC S-23s23lr2]
- The FAQ says AlmaLinux does not add packages to the distribution unless they are added to RHEL, and points to EPEL for anything else. [DOC S-23s23lr2]
- The repositories page lists packages beyond RHEL's set: `extras` (packages not available in RHEL) and `plus` (packages replacing a core component with patched functionality, not available upstream). [DOC S-46pbwuai]
- Taken together, the distribution's additions over RHEL are in separate, mostly disabled repositories (extras, plus, devel, testing, SIG and synergy content) plus the project's own errata, OVAL streams and CIS/SSG content; the base repositories follow RHEL's package set. [DER S-23s23lr2, S-46pbwuai, S-abrr4vdk, S-frwlmyiy: the FAQ rule on packages against the repositories pages]
- The `repo.almalinux.org/almalinux/9.4/` directory holds only a README that calls the directory and version deprecated, and says 9.4 no longer gets updates or security fixes (other old minor directories were not opened). [DOC S-ecy4u4kc]
- A pin to one minor release is therefore a bounded exception: the minor stops getting fixes when the next one ships, so a pull agent that pins a minor needs a review date that ends at the next minor's expected release. [DER S-w2hsvwk5, S-ecy4u4kc: end of life at the next release, no updates after it]
- Whether the project publishes an exact end-of-life date per minor in advance (as opposed to the next release's date) was not found. [UNK: logged in `_gaps.md`]

## Reference
| major | active support until | security support until | latest minor in the table (2026-10-15) |
|---|---|---|---|
| 10 | 31 May 2030 | 31 May 2035 | 10.2 (10.3 beta) |
| 9 | 31 May 2027 | 31 May 2032 | 9.8 (9.9 beta) |
| 8 | 31 May 2024 | 31 May 2029 | 8.10 |

Related: `security/almalinux-repositories-vault-pins.md`, `security/almalinux-elevate.md`, `security/linux-patching-and-pins.md`, `security/linux-cis-ssg-openscap.md`.

## Examples
- SNIPPET: read which AlmaLinux minor a host is on before comparing it with the release table; context: any AlmaLinux host; checked: no [DER S-w2hsvwk5: the release table is keyed by the string this file holds]
```
cat /etc/almalinux-release
```
