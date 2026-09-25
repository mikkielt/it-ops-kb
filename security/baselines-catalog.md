---
topic: security/baselines-catalog
priority: P0
applies_to: "Windows 11 Enterprise 24H2/25H2, Windows Server 2025"
retrieved_utc: 2026-09-24
sources: [S1470, S1471, S1472, S1598, S1400, S1401, S1402, S1403, S1404, S1405, S1406, S1407, S1408, S1409, S1410, S1411, S1418, S1419, S1420, S1421, S1422, S1423, S1424, S1425, S1426]
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
- Microsoft published a Windows 11 version 24H2 security baseline blog post announcing the release,
  covering changed protections to LAN Manager, Kerberos, UAC and Defender Antivirus [DOC S1401].
- Microsoft published a Windows 11 version 25H2 security baseline blog post [DOC S1402]; exact
  publication date not extracted this pass [UNK].
- CIS Microsoft Windows 11 Enterprise Benchmark current version is v5.1.0 (previous: v5.0.0, then
  bugfix v5.0.1) [DOC S1405, S1406, S1407, S1408]; the front matter of v5.0.x tests against release
  23H2, so applicability to 24H2/25H2 devices should be confirmed against the v5.1.0 front matter
  before use — not independently opened this pass [UNK].
- A CIS Microsoft Intune for Windows 11 benchmark exists (v4.0.0 per a third-party mirror of CIS
  release notes); the CIS site itself was not independently opened for this row [COMMUNITY].
- DISA publishes STIG and SCAP content for Microsoft Windows without any sign-in requirement, at
  `public.cyber.mil` and `cyber.mil` [DOC S1409, S1411].
- The current Microsoft Windows 11 STIG is **V2R9**, XCCDF dated 2026-08-06, zip
  `U_MS_Windows_11_V2R9_STIG.zip` at `dl.dod.cyber.mil` (pinned artifact obtained by the
  coordinator) [DOC S1470].
- A DISA STIG for Windows Server 2025 exists: **V1R3**, zip
  `U_MS_Windows_Server_2025_V1R3_STIG.zip` (pinned artifact obtained by the coordinator; its exact
  XCCDF date was not independently confirmed by Part A) [DOC S1471].
- Unclassified STIGs posted on public.cyber.mil / dl.dod.cyber.mil carry Distribution Statement A
  ("approved for public release, distribution unlimited") per DoDI 5230.24 and the DoD Cyber
  Exchange's unclassified-STIG posting policy; no sign-in or licence acceptance click-through is
  required to download them [DOC S1409, S1411, and the DoDI 5230.24 / public.cyber.mil README
  digest found this pass — the README PDF itself was not directly opened, so the *licence statement
  wording* is tagged `COMMUNITY` pending a direct read of a STIG zip's own Readme, while the *fact
  that unclassified STIGs require no sign-in* is `DOC` per S1409/S1411].
- Windows Server 2025 has its own SCT baseline line, separate from Windows 11's: version 2506
  released 2025-06-25, and version 2602 released 2026-02-23, both via techcommunity announcement
  posts [DOC S1418, S1419]; the 2602 post's own delta-list content (settings changed vs 2506) was
  not independently re-extracted by fetch in this pass, only via search-engine digest, so specific
  setting counts from that delta are tagged `COMMUNITY` rather than `DOC` until confirmed.
- Intune ships three separate baseline products: a Windows security baseline, a
  Defender for Endpoint baseline (explicitly *not recommended* for virtual machines or VDI
  endpoints per Microsoft Learn), and an Edge baseline (settings format changed May 2023) [DOC
  S1421, S1422, S1423]. Exact current version identifiers for each were not extracted this pass
  [UNK].
- OSConfig for Windows Server 2025 ships as the `Microsoft.OSConfig` PowerShell module (PSGallery),
  with role-based baseline profiles (Domain Controller, Member Server, Workgroup Member) enforcing
  over 300 settings (TLS 1.2+, SMB 3.0+, credential protections cited as examples) [DOC S1424].
  Once applied, OSConfig baseline settings are described as protected from drift automatically —
  i.e. OSConfig **remediates**, unlike a ConfigMgr baseline kept deliberately in test (visibility-only)
  mode. [DOC S1424; DER: a general implication for any drift-visibility-first design: expect this
  contrast with any remediating baseline mechanism it is compared against]
- CIS Benchmark PDFs for non-members are distributed under **CC BY-NC-SA 4.0** (free, attribution
  required, non-commercial, share-alike); CIS-SecureSuite members are separately barred from
  redistributing or creating derivative "images" incorporating benchmark content [DOC:
  cisecurity.org terms-of-use pages, summarized via search digest — the terms page itself returned
  404 on direct fetch, so this is tagged `COMMUNITY` pending a direct re-read of
  cisecurity.org/terms-of-use-for-non-member-cis-products]. Under CC BY-NC-SA 4.0, an ID plus a
  short paraphrase of the recommendation title is allowed with attribution, for non-commercial
  internal use; a crosswalk CSV may therefore carry CIS IDs and short paraphrases,
  attributed, once a direct citation is confirmed — recorded as a residual gap.
- ACSC's Essential Eight maturity model was first published June 2017, with a maturity-model
  revision seen dated November 2023 and an FAQ revision dated April 2024; a more recent 2026
  revision was not confirmed this pass [DOC S1425, partial]. ACSC's Windows 11 hardening guide
  ("Hardening Microsoft Windows 11 workstations") has a filename-dated September 2025 edition, with
  a January 2026 change-log also found, suggesting at least one further 2026 revision exists beyond
  what was opened this pass [DOC S1426, partial]. ACSC materials are Australian Commonwealth
  content, generally reusable with attribution [DER: standard ACSC copyright notice pattern, not
  independently re-confirmed this pass].
- NCSC (UK) device guidance, BSI IT-Grundschutz/SiSyPHuS and ANSSI recommendations remain UNK; rows
  are placeholders in the CSV [UNK].

- Coordinator addendum: the OSConfig Server 2025 baseline is also published as machine-readable CSV (MIT) in `microsoft/osconfig`, versions 2409-2606. Version 2606 has 361 settings with registry or CSP paths, per-role expected values, CIS RuleIDs and STIG ids. [DOC S1598]
- Coordinator addendum: the Microsoft Windows 11 v24H2 baseline package was retrieved (426 settings). DISA Windows 11 V2R9 and Server 2025 V1R3 were both retrieved, with benchmark date 2026-08-10. See `settings-crosswalk.md`. [DOC S1472,S1470,S1471]

## Reference

See `baselines-catalog.csv`.

## Examples

None (catalog of publisher sources; no device-specific content).
