---
topic: security/baselines-catalog
priority: P0
applies_to: "Windows 11 Enterprise 24H2/25H2, Windows Server 2025"
retrieved_utc: 2026-09-27
sources: [S1470, S1471, S1472, S1598, S1400, S1401, S1402, S1403, S1404, S1405, S1406, S1407, S1408, S1418, S1419, S1421, S1422, S1423, S1424, S1425, S-uzuvf3vo, S-nwnif62g, S-3vkajr2c, S-ycjlut3h]
status: partial
---

## Summary

Microsoft ships a GPO-backup-plus-spreadsheet security baseline for Windows 11 24H2 and 25H2, and
Windows Server 2025 has its own SCT baseline line (version 2506, then 2602) through the Security
Compliance Toolkit. Intune ships separate security baselines for Windows, Defender for Endpoint
(not recommended on VM/VDI) and Edge. OSConfig ships role-based baselines (Domain Controller,
Member Server, Workgroup Member) for Windows Server 2025, published as CSV (v2606: 361 settings), that *auto-correct* drift, unlike a
test-mode (visibility-only) DSC baseline approach. CIS publishes a Windows 11 Enterprise benchmark (v5.1.0) and an Intune for
Windows 11 benchmark, both free-to-read PDFs, reported (COMMUNITY, terms page not fetched) as CC BY-NC-SA 4.0 for non-members (no bulk
machine-readable export without CIS-SecureSuite/WorkBench). DISA's Windows 11 STIG is at V2R9 and the Server 2025 STIG at V1R3 (both benchmark date 2026-08-10), public, no registration. ACSC publishes both
an Essential Eight maturity model and a Windows 11 hardening guide, both freely reusable with
attribution. NCSC (UK)/BSI/ANSSI rows remain UNK.

## Facts

- The Security Compliance Toolkit 1.0 download page (id 55319) lists separate packages for Windows 11
  23H2, 24H2 and 25H2 baselines (alongside Windows Server 2025, Edge, Microsoft 365 Apps, LGPO and
  Policy Analyzer); the page's HTML embeds a direct `download.microsoft.com` URL for each file, so a
  plain HTTP fetch of the page yields the file list without the interactive selection flow [DOC S1400].
- The Learn guide to the Security Compliance Toolkit lists Windows 11 baselines only up to version 24H2 (plus Windows 10, Windows Server 2016 to 2025, Microsoft 365 Apps for Enterprise 2412 and Edge 128) and four tools: Policy Analyzer, LGPO, Set Object Security and GPO to Policy Rules (which converts GPO backups to `.PolicyRules` files), so the download page above is newer than the guide. [DOC S1403]
- Microsoft's security baselines guide says the baselines assume standard users without administrative rights, enforce a setting only if it mitigates a contemporary threat without causing worse operational issues, and can be applied with Group Policy, Configuration Manager or Intune; Windows Pro, Enterprise and Education editions support them. [DOC S1404]
- Microsoft announced the Windows 11 version 24H2 security baseline on 2024-10-01 (techcommunity post),
  covering changed protections to LAN Manager, Kerberos, UAC and Defender Antivirus; a later update to the
  post says the two Administrator protection (UAC) settings are visible but not yet functional [DOC S1401].
- Microsoft announced the Windows 11 version 25H2 security baseline on 2025-09-30 (techcommunity post);
  changes since 24H2 include disabling NetBIOS name resolution on all adapters, adding the PSExec/WMI
  process-creation ASR rule in Audit (2), enabling command line in process creation events, and removing
  WDigest and Scan packed executables [DOC S1402].
- CIS Microsoft Windows 11 Enterprise Benchmark current version is v5.1.0 (previous: v5.0.0, then
  bugfix v5.0.1) [DOC S1405, S1406, S1407, S1408]; the front matter of v5.0.x tests against release
  23H2, so applicability to 24H2/25H2 devices should be confirmed against the v5.1.0 front matter
  before use — not independently opened this pass [UNK].
- A CIS Microsoft Intune for Windows 11 benchmark exists; the CIS Intune benchmark page lists it at v5.0.0 on
  2026-09-26 (a third-party mirror of CIS release notes had given v4.0.0), beside Intune benchmarks for Windows 10,
  Edge, Office and Microsoft Defender Antivirus [DOC S-3vkajr2c].
- DISA's STIG packages say parties with a DoW common access card (CAC) obtain STIGs from the DoW Cyber
  Exchange at `cyber.mil`, and those without one from `public.cyber.mil` (Windows 11 V2R9 Overview,
  section 1.4) [DOC S1470].
- The current Microsoft Windows 11 STIG is **V2R9**, XCCDF dated 2026-08-06, zip
  `U_MS_Windows_11_V2R9_STIG.zip` at `dl.dod.cyber.mil` (pinned artifact obtained by the
  coordinator) [DOC S1470].
- A DISA STIG for Windows Server 2025 exists: **V1R3**, zip
  `U_MS_Windows_Server_2025_V1R3_STIG.zip` (pinned artifact obtained by the coordinator; its exact
  XCCDF date was not independently confirmed by Part A) [DOC S1471].
- Unclassified STIGs posted on public.cyber.mil / dl.dod.cyber.mil carry Distribution Statement A
  ("approved for public release, distribution unlimited") per DoDI 5230.24 and the DoD Cyber
  Exchange's unclassified-STIG posting policy; no sign-in or licence acceptance click-through is
  required to download them [DOC S1470, and the DoDI 5230.24 / public.cyber.mil README
  digest found this pass — the Windows 11 V2R9 zip's own `U_Readme_SRG_and_STIG.pdf` (V3R6) and
  Overview carry no distribution statement, so the *licence statement wording* stays `COMMUNITY`,
  while the *fact that STIGs are offered to people without a CAC at public.cyber.mil* is `DOC` per
  the S1470 Overview, section 1.4].
- Windows Server 2025 has its own SCT baseline line, separate from Windows 11's: version 2506
  released 2025-06-25, and version 2602 released 2026-02-23, both via techcommunity announcement
  posts [DOC S1418, S1419]. The 2602 delta vs 2506 (read from the post on 2026-09-27) adds the three
  Restrict NTLM audit settings, blocks ROCA-vulnerable WHfB keys on DCs, disables sudo and IE11 COM
  launch, applies Mark of the Web, sets the print RPC listener to Kerberos on member servers and adds
  `RESTRICTED SERVICES\PrintSpoolerService` to Impersonate a client after authentication [DOC S1419].
- Intune lists separate baselines for Windows (Security Baseline for Windows 10 and later, latest
  version 25H2), Defender for Endpoint (latest version 24H1; optimized for physical devices and *not
  recommended* for virtual machines or VDI endpoints) and Edge (latest version 139, April 2026; its
  settings moved to a new format in May 2023), besides Microsoft 365 Apps, HoloLens 2, Windows 365,
  Windows 365 for Agents, a Local AI Agent (OpenClaw) preview and a GCC High-only STIG audit
  baseline (re-read 2026-09-27) [DOC S1421, S1422, S1423].
- OSConfig for Windows Server 2025 ships as the `Microsoft.OSConfig` PowerShell module (PSGallery),
  with role-based baseline profiles (Domain Controller, Member Server, Workgroup Member); examples
  of its settings are TLS 1.2 or higher, a minimum of SMB 3.0 and credential-theft protections such
  as Credential Guard [DOC S1424].
  Once applied, OSConfig baseline settings are described as protected from drift automatically —
  i.e. OSConfig **remediates**, unlike a ConfigMgr baseline kept deliberately in test (visibility-only)
  mode. [DOC S1424; DER: a general implication for any drift-visibility-first design: expect this
  contrast with any remediating baseline mechanism it is compared against]
- CIS Benchmark PDFs for non-members are distributed under **CC BY-NC-SA 4.0** (free, attribution
  required, non-commercial, share-alike), per the non-member terms page read 2026-09-26 [DOC S-ycjlut3h];
  that CIS-SecureSuite members are separately barred from redistributing or creating derivative "images"
  incorporating benchmark content comes from a search digest of the member terms, not re-read
  [UNK: member terms page not fetched]. Under CC BY-NC-SA 4.0, an ID plus a
  short paraphrase of the recommendation title is allowed with attribution, for non-commercial
  internal use; a crosswalk CSV may therefore carry CIS IDs and short paraphrases,
  attributed, once a direct citation is confirmed — recorded as a residual gap.
- ACSC's Essential Eight maturity model page gives first published 30 June 2017 and last updated
  27 November 2023 (the November 2023 model PDF is its attachment), and defines Maturity Levels Zero to
  Three; read from the Internet Archive capture of 2026-08-27, since cyber.gov.au times out from here.
  [DOC S1425]
- ACSC's "Hardening Microsoft Windows 11 workstations" (first published May 2017) was last updated
  January 2026; that edition takes its settings from Windows 11 version 25H2, and ACSC's January 2026
  change log records the move from the September 2025 (24H2) edition, adding measures for auditing,
  printers, widgets, app installations and SMB sessions [DOC S-uzuvf3vo, S-nwnif62g].
- Apart from the Coat of Arms, the ACSC Windows 11 hardening guide is © Commonwealth of Australia
  under CC BY 4.0, so it is reusable with attribution [DOC S-uzuvf3vo].
- NCSC (UK) device guidance, BSI IT-Grundschutz/SiSyPHuS and ANSSI recommendations remain UNK; rows
  are placeholders in the CSV [UNK].

- Coordinator addendum: the OSConfig Server 2025 baseline version 2606 is published as a machine-readable CSV in `microsoft/osconfig`, with 361 settings carrying registry or CSP paths, per-role expected values, CIS RuleIDs and STIG ids. [DOC S1598]
- The same `security/` folder at commit `82a54b9e` also holds versions 2409, 2411, 2504 and 2510, and the repository is MIT-licensed. [DER S1598: file names beside the pinned file and the repository licence at the same commit]
- Coordinator addendum: the Microsoft Windows 11 v24H2 baseline package was retrieved (426 settings). DISA Windows 11 V2R9 and Server 2025 V1R3 were both retrieved, with benchmark date 2026-08-10. See `settings-crosswalk.md`. [DOC S1472,S1470,S1471]

## Reference

See `baselines-catalog.csv`.

## Examples

None (catalog of publisher sources; no device-specific content).
