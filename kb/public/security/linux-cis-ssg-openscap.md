---
topic: security/linux-cis-ssg-openscap
priority: P3
applies_to: "CIS Benchmarks, SCAP Security Guide profiles, OpenSCAP and Lynis for Debian, Ubuntu, AlmaLinux and Alpine servers"
retrieved_utc: 2026-10-11
sources: [S-dibgi2xt, S-2yuq6xw2, S-kbvw7lhl, S1485, S-c3ytabe2, S-kvmwtqw2, S-3ccfvo3t, S-vvr4ensf, S-e3oi3dog, S-5ucxfabx, S-q7m3pvv2, S-4qyumgua, S-n6xxzrrl, S-ovklfzvf, S-afsk2gm4, S-v6qk7hcn]
status: partial
---

# Linux server baselines: CIS Benchmarks, SCAP Security Guide, OpenSCAP and Lynis

## Summary
Debian, Ubuntu and AlmaLinux each have a CIS Benchmark with Level 1 and Level 2 Server profiles; the CIS pages offer the benchmark as a free PDF, and the scanning content (CIS-CAT Pro) is for CIS SecureSuite members. The SCAP Security Guide (ComplianceAsCode) ships open, machine-readable CIS-aligned profiles for Debian 11 to 13, Ubuntu 22.04 to 26.04 and AlmaLinux 9, usually a benchmark version or two behind. Alpine has neither a CIS Benchmark nor SSG content in the sources read; Lynis is the open scanner the kb can name there, with Alpine support unconfirmed. For the Windows side of baselines see `security/baselines-catalog.md`.

## Facts
- The CIS Debian Linux page (retrieved 2026-10-11) lists Debian Linux 13 (v1.1.0), 12 (v2.0.0), 11 (v2.0.0), 11 STIG (v1.0.0), 10 (v2.0.0) and 9 (v1.0.1). [DOC S-dibgi2xt]
- The CIS Ubuntu Linux page lists 26.04 LTS (v1.0.0), 24.04 LTS (v2.0.0), 22.04 LTS (v3.0.0) and 20.04 LTS (v3.0.0), STIG variants for 24.04, 22.04 and 20.04, and older releases down to 12.04. [DOC S-2yuq6xw2]
- The CIS AlmaLinux OS page lists AlmaLinux OS 10 (v1.0.0), 9 (v3.0.0) and 8 (v4.0.0). [DOC S-kbvw7lhl]
- On those three pages the benchmark is a PDF freely available for non-commercial use; CIS-CAT Pro scanning content and Build Kits (GPO and shell scripts) are labelled CIS SecureSuite members only, and the pages do not name the file format of the CIS-CAT content. [DOC S-dibgi2xt, S-2yuq6xw2, S-kbvw7lhl]
- The CIS benchmarks index lists AlmaLinux OS but has no Alpine Linux entry, and a web search for an Alpine benchmark found none, so Alpine has no CIS Benchmark in the sources read. [DER S1485, S-kbvw7lhl: Alpine absent from the index, AlmaLinux present]
- The SSG repository's `products/` directory at the pinned commit has `almalinux9`, `debian11`, `debian12`, `debian13`, `ubuntu2204`, `ubuntu2404` and `ubuntu2604`, and no Alpine, AlmaLinux 8 or AlmaLinux 10 product. [CODE S-c3ytabe2: content/products#directory-listing]
- Debian 12, Debian 13 and Ubuntu 24.04 each have profile files `cis_level1_server`, `cis_level1_workstation`, `cis_level2_server` and `cis_level2_workstation` (Debian 12 and Debian 13 add ANSSI profiles; Ubuntu 24.04 adds `stig`). [CODE S-3ccfvo3t: products/debian12/profiles#directory-listing; CODE S-vvr4ensf: products/debian13/profiles#directory-listing; CODE S-e3oi3dog: products/ubuntu2404/profiles#directory-listing]
- AlmaLinux 9 has `cis_server_l1`, `cis_workstation_l1` and `cis_workstation_l2` plus `cis`, whose title is "CIS AlmaLinux OS 9 Benchmark for Level 2 - Server". [CODE S-kvmwtqw2: products/almalinux9/profiles#directory-listing; CODE S-n6xxzrrl: cis.profile#title]
- The SSG profile files state the benchmark version they align to: Debian 12 v1.1.0 (released 2024-09-26), AlmaLinux 9 v2.0.0 (2024-06-20), Ubuntu 24.04 v1.0.0 (2024-08-26). [CODE S-5ucxfabx: cis_level1_server.profile#description; CODE S-q7m3pvv2: cis_server_l1.profile#description; CODE S-4qyumgua: cis_level1_server.profile#description]
- Compared with the CIS pages of the same day (Debian 12 v2.0.0, AlmaLinux 9 v3.0.0, Ubuntu 24.04 v2.0.0) each SSG profile pins an older benchmark version, so a scan with the SSG profile does not test the newest CIS text. [DER S-dibgi2xt, S-kbvw7lhl, S-2yuq6xw2, S-5ucxfabx, S-q7m3pvv2, S-4qyumgua: version numbers compared]
- Canonical's Ubuntu Security Guide documents four CIS profile names (`cis_level1_workstation`, `cis_level1_server`, `cis_level2_workstation`, `cis_level2_server`), installed with `sudo apt install usg-benchmarks-1`. [DOC S-ovklfzvf]
- OpenSCAP evaluates a source data stream with `oscap xccdf eval --profile PROFILE_ID --results-arf FILE --report FILE DATASTREAM`; a profile id may be shortened to its suffix (`--profile ospp`). [DOC S-afsk2gm4]
- `oscap info --profile PROFILE --list-rules DATASTREAM` prints the rule ids a profile selects, one per line, as machine-readable output; `--list-vars` prints the resolved variables and both options require `--profile`. [DOC S-afsk2gm4]
- The OpenSCAP manual's examples read SSG data streams from `/usr/share/xml/scap/ssg/content/` (`ssg-rhel8-ds.xml`, from the `scap-security-guide` package). [DOC S-afsk2gm4]
- Lynis is a security auditing tool for UNIX-based systems (Linux, macOS, BSD) that runs on the host itself, licensed GPLv3; it can run from a git clone with `./lynis audit system` and needs no compilation or installation. [DOC S-v6qk7hcn]
- Lynis names compliance testing against ISO27001, PCI-DSS and HIPAA among its goals, not CIS; the project's own packages are for RPM and DEB distributions (CentOS, Debian, Fedora, OEL, openSUSE, RHEL, Ubuntu "and others"). [DOC S-v6qk7hcn]
- For Alpine no CIS or SSG content exists in the sources read, so a scanner there is Lynis run from a clone, or the agent's own checks against a hand-built list; the README does not name Alpine, so that use is unconfirmed. [DER S-v6qk7hcn, S-c3ytabe2: no Alpine product, Lynis needs no install]
- Which datastream file names Debian and Ubuntu SSG packages install, and whether Ubuntu Security Guide needs a paid Ubuntu subscription, are not stated on the pages read. [UNK: logged in `_gaps.md`]

## Reference
| family | CIS Benchmark (latest on page) | SSG product (pinned commit) | SSG CIS server profiles |
|---|---|---|---|
| Debian | 13 v1.1.0, 12 v2.0.0 | debian11, debian12, debian13 | Level 1 and Level 2 Server (12, 13) |
| Ubuntu | 26.04 v1.0.0, 24.04 v2.0.0 | ubuntu2204, ubuntu2404, ubuntu2604 | Level 1 and Level 2 Server (24.04) |
| AlmaLinux | 10 v1.0.0, 9 v3.0.0, 8 v4.0.0 | almalinux9 only | `cis_server_l1`, `cis` (Level 2 Server) |
| Alpine | none listed | none | none |

Control mappings per option are in `security/linux-nftables.md`, `security/linux-auditd.md`, `security/linux-sshd-hardening.md` and `security/linux-time-sync.md`.

## Examples
- SNIPPET: list the rules a profile selects, then scan with it; context: OpenSCAP installed, SSG data stream path as in the manual's examples (file name for the distribution is a placeholder); checked: no [DER S-afsk2gm4: `oscap info --list-rules`, `oscap xccdf eval` syntax]
```
oscap info --profile cis_level1_server --list-rules /usr/share/xml/scap/ssg/content/ssg-PRODUCT-ds.xml
oscap xccdf eval --profile cis_level1_server --results-arf results.xml --report report.html /usr/share/xml/scap/ssg/content/ssg-PRODUCT-ds.xml
```
