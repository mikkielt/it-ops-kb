---
topic: security/linux-cis-ssg-openscap
priority: P3
applies_to: "CIS Benchmarks, SCAP Security Guide profiles, OpenSCAP and Lynis for Debian, Ubuntu, AlmaLinux (and the RHEL products it is built from) and Alpine servers"
retrieved_utc: 2026-10-13
sources: [S-dibgi2xt, S-2yuq6xw2, S-kbvw7lhl, S1485, S-c3ytabe2, S-kvmwtqw2, S-3ccfvo3t, S-vvr4ensf, S-e3oi3dog, S-5ucxfabx, S-q7m3pvv2, S-4qyumgua, S-n6xxzrrl, S-ovklfzvf, S-afsk2gm4, S-v6qk7hcn, S-3yrjvfu3, S-4oqrbtvs, S-cxnklaym, S-g4lr43wm, S-z7bfg2a3, S-sotu6mmv, S-fzqtd2e3, S-mn6raxsi, S-hdm6j6sh, S-c7zaz35y, S-m2ry72iv, S-v65tqmnq, S-suunbp43, S-fwapji3y, S-xff3wkn5, S-fbnsylla]
status: partial
---

# Linux server baselines: CIS Benchmarks, SCAP Security Guide, OpenSCAP and Lynis

## Summary
Debian, Ubuntu and AlmaLinux each have a CIS Benchmark with Level 1 and Level 2 Server profiles; the CIS pages offer the benchmark as a free PDF, and the scanning content (CIS-CAT Pro) is for CIS SecureSuite members. The SCAP Security Guide (ComplianceAsCode) ships open, machine-readable CIS-aligned profiles, usually a benchmark version or two behind, but not for every product it has: at the pinned commit Debian 12 and 13, Ubuntu 22.04 and Ubuntu 24.04, AlmaLinux 9 and RHEL 8 and 10 carry CIS profiles, while Debian 11 has none and Ubuntu 26.04 has only a default profile. AlmaLinux 8 and 10 have no upstream product; AlmaLinux's own `scap-security-guide` package builds one from the RHEL product (a sample for 8 lists four CIS AlmaLinux 8 profiles), so the CIS profiles for them come from that package, not from the upstream repository. Alpine has neither a CIS Benchmark nor SSG content in the sources read; Lynis is the open scanner the kb can name there, with Alpine support unconfirmed. For the Windows side of baselines see `security/baselines-catalog.md`.

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
- The same `products/` directory also has `rhel8`, `rhel9` and `rhel10`, the Red Hat products that AlmaLinux and other rebuilds track. [CODE S-c3ytabe2: content/products#directory-listing]
- `products/rhel8/profiles` and `products/rhel10/profiles` each hold `cis`, `cis_server_l1`, `cis_workstation_l1` and `cis_workstation_l2` among their other profiles (ANSSI, HIPAA, OSPP, PCI-DSS, STIG and more); `cis` is titled "CIS Red Hat Enterprise Linux 8 Benchmark for Level 2 - Server" and the RHEL 10 file has the same title for 10. [CODE S-3yrjvfu3: products/rhel8/profiles#directory-listing; CODE S-4oqrbtvs: products/rhel10/profiles#directory-listing; CODE S-mn6raxsi: cis.profile#title; CODE S-hdm6j6sh: cis.profile#title]
- The RHEL 8 `cis_server_l1` profile aligns to benchmark v4.0.0, released 2025-08-28, and the RHEL 10 one to v1.0.1, released 2025-09-30; the RHEL 10 profiles also set `var_authselect_profile=local`. [CODE S-sotu6mmv: cis_server_l1.profile#description; CODE S-fzqtd2e3: cis_server_l1.profile#description]
- `products/debian11/profiles` holds ANSSI (`anssi_np_nt28_*`), `default` and `standard` profiles and no CIS profile file, so no SSG scan of Debian 11 tests a CIS profile. [CODE S-cxnklaym: products/debian11/profiles#directory-listing]
- `products/ubuntu2204/profiles` has `cis_level1_server`, `cis_level1_workstation`, `cis_level2_server` and `cis_level2_workstation` (plus `default`, `standard` and `stig`); the Level 1 Server file aligns to benchmark v2.0.0, released 2024-03-28. [CODE S-g4lr43wm: products/ubuntu2204/profiles#directory-listing; CODE S-c7zaz35y: cis_level1_server.profile#description]
- `products/ubuntu2604/profiles` holds only `default.profile`, which is hidden and described as a minimal default profile "to ensure benchmark generation", so the Ubuntu 26.04 product has no CIS profile at the pinned commit. [CODE S-z7bfg2a3: products/ubuntu2604/profiles#directory-listing; CODE S-m2ry72iv: default.profile#description]
- The CIS Ubuntu page lists 22.04 LTS at v3.0.0 while the SSG 22.04 profile pins v2.0.0, so the lag of a profile behind the CIS page applies to Ubuntu 22.04 as well. [DER S-2yuq6xw2, S-c7zaz35y: version numbers compared]
- The upstream RHEL 8 platform check `installed_OS_is_rhel8` tests that the RPM package `redhat-release` has a version matching `^8\.\d{1,2}$` and, as a separate branch, a Red Hat Virtualization Host based on RHEL 8; the upstream AlmaLinux 9 check instead tests that `/etc/almalinux-release` exists and reads `AlmaLinux release 9.`. [CODE S-v65tqmnq: installed_OS_is_rhel8.xml#test_rhel8; CODE S-suunbp43: installed_OS_is_almalinux9.xml#test_almalinux9]
- AlmaLinux's own OpenSCAP guide for 8 installs `openscap`, `openscap-utils` and `scap-security-guide` from the AppStream repository, and its sample `oscap info` of `ssg-almalinux8-xccdf.xml` (generated 2022-05-03) lists CIS AlmaLinux OS 8 profiles `cis` (Level 2 - Server), `cis_server_l1`, `cis_workstation_l1` and `cis_workstation_l2`. [DOC S-fwapji3y]
- AlmaLinux's packaging commit "Add AlmaLinux 10 support" (2026-03-31) moves its package to the SSG 0.1.80 tarball and adds a patch `1001-add-almalinux10-os-detection.patch` with an `installed_OS_is_almalinux10` check. [DOC S-xff3wkn5]
- The script that commit adds copies `products/rhel10` to `products/almalinux10`, and its `sed` calls over the copied `profiles/*` replace "Red Hat Enterprise Linux" and "RHEL" with "AlmaLinux OS", the reference `red_hat_linux` with `almalinuxos_linux`, every "released YYYY-MM-DD" with "released 2025-09-30" and `rhel10:` with `almalinux10:`, so the AlmaLinux 10 profiles are the RHEL 10 profile content rebranded. [CODE S-fbnsylla: add-almalinux10-support.sh#products/almalinux10/profiles]
- AlmaLinux 8 and 10 can be scanned with a CIS profile through the AlmaLinux package of the SSG (its `ssg-almalinux8` content, whose sample lists the same four CIS profile ids as the RHEL 8 product, and its AlmaLinux 10 product built from RHEL 10); the upstream repository at the pinned commit has no AlmaLinux 8 or 10 product to build from. [DER S-c3ytabe2, S-fwapji3y, S-fbnsylla: upstream product list against the AlmaLinux guide and packaging script]
- Whether the upstream `ssg-rhel8-ds.xml` or `ssg-rhel10-ds.xml` evaluates its CIS rules on an AlmaLinux host unchanged is not stated on the pages read: the RHEL 8 check reads the `redhat-release` package, and no page read says whether AlmaLinux supplies a package of that name; the docs of the `oscap` platform filter were not read. [UNK]
- Whether the profile files of AlmaLinux's 8 and 10 packages align to the CIS AlmaLinux benchmarks the CIS page lists (v4.0.0 for 8, v1.0.0 for 10) is not stated: the guide's sample for 8 is dated 2022, and for 10 the script's rewrite keeps the RHEL 10 benchmark text (v1.0.1) under the AlmaLinux name, so which benchmark the profiles test is not the CIS AlmaLinux OS 10 v1.0.0 text unless the profile files say so. [UNK]
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
| Debian | 13 v1.1.0, 12 v2.0.0 | debian11, debian12, debian13 | Level 1 and Level 2 Server (12, 13); none for 11 |
| Ubuntu | 26.04 v1.0.0, 24.04 v2.0.0, 22.04 v3.0.0 | ubuntu2204, ubuntu2404, ubuntu2604 | Level 1 and Level 2 Server (22.04, 24.04); 26.04 has only `default` |
| AlmaLinux | 10 v1.0.0, 9 v3.0.0, 8 v4.0.0 | almalinux9 only upstream; 8 and 10 from AlmaLinux's own package | 9: `cis_server_l1`, `cis` (Level 2 Server); 8: the same ids in AlmaLinux's sample; 10: not read |
| RHEL (base of the AlmaLinux 8 and 10 products) | not read | rhel8 (v4.0.0), rhel10 (v1.0.1) | `cis_server_l1`, `cis` (Level 2 Server), `cis_workstation_l1`, `cis_workstation_l2` |
| Alpine | none listed | none | none |

Control mappings per option are in `security/linux-nftables.md`, `security/linux-auditd.md`, `security/linux-sshd-hardening.md` and `security/linux-time-sync.md`.

## Examples
- SNIPPET: list the rules a profile selects, then scan with it; context: OpenSCAP installed, SSG data stream path as in the manual's examples (file name for the distribution is a placeholder); checked: no [DER S-afsk2gm4: `oscap info --list-rules`, `oscap xccdf eval` syntax]
```
oscap info --profile cis_level1_server --list-rules /usr/share/xml/scap/ssg/content/ssg-PRODUCT-ds.xml
oscap xccdf eval --profile cis_level1_server --results-arf results.xml --report report.html /usr/share/xml/scap/ssg/content/ssg-PRODUCT-ds.xml
```
