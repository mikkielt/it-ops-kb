---
topic: security/settings-crosswalk
priority: P0
applies_to: "Windows 11 Enterprise 24H2/25H2 (Microsoft baseline packages 24H2 and 25H2), Windows Server 2025 (Microsoft baseline 2602), DISA STIG Windows 11 V2R9 and Windows Server 2025 V1R3 (2026-08-10), Intune Windows baseline 24H2 pivot, DSC 3.3.0"
retrieved_utc: 2026-09-28
sources: [S1470, S1471, S1472, S1598, S1473, S-oeh7ui3h, S1477, S1478, S1479, S1590, S1591, S1413, S1414, S1415, S1416, S1594, S1595, S1596, S114, S-lzzhbeao, S-3yywfx4r, S-ww7anzs7, S1400, S-bzyxqg37, S-p6phzp72, S1402, S-4krq7dui]
status: complete
files: [security/artifacts/disa/, security/artifacts/microsoft/, security/artifacts/osconfig/]
---

# Settings crosswalk: Microsoft baseline × STIG × Intune × DSC v3

## Summary
- `settings-crosswalk.csv` has **542 rows**: all **426** settings of the Microsoft Windows 11 24H2 security baseline, **106** DISA Windows 11 V2R9 rules the Microsoft baseline does not set, **8** first-baseline candidates, and **2** settings new in the 25H2 baseline.
- Rows come from machine-readable files: the baseline's `MSFT-Win11-v24H2.PolicyRules` and settings workbook, and the STIG XCCDF. Joins match registry path plus value name, audit subcategory, or user-right name. The Server 2025 STIG id is added where the same registry value appears there.
- 138 Microsoft baseline rows have a matching Windows 11 STIG rule. 84 of those use a native DSC v3 path.
- The Windows 11 CIS columns are empty: the CIS benchmark text needs registration, so no Windows 11 CIS id was mapped (see `gaps.md`). CIS Server 2025 ids reach the file through Microsoft's OSConfig CSV.
- Every row also carries the Windows 11 25H2 baseline value and the Windows Server 2025 v2602 member-server value, parsed from the packages' `.PolicyRules` files (2026-09-28).

## Facts
- The Microsoft Windows 11 24H2 baseline package contains `Documentation/MSFT-Win11-v24H2.PolicyRules`. This XML lists every setting: 330 computer and 5 user registry values, 68 security-template lines and 23 advanced-audit subcategories. [DOC S1472]
- The 68 security-template lines split into 32 registry-backed security options (`MACHINE\...=type,value`), 9 account/system-access values, 23 user-rights assignments and 4 service start types (the Xbox services, all `4` = disabled). [DER S1472: parsed line prefixes]
- 135 of the 335 registry values belong to the two Internet Explorer 11 GPOs (132 computer, 3 user). [DER S1472: count by `PolicyName`]
- Windows 11 STIG V2R9 has 257 rules. 123 of them state a registry path and value in the check text. The rest are audit (43), user rights (28), account policy (9), optional features (7), firewall (2), service (1) and 44 procedural or other checks. [DER S1470: parsed XCCDF check-content; the mechanism comes from the rule-id prefix and the title, so it is heuristic]
- Windows Server 2025 STIG V1R3 has 291 rules, 96 of them with a registry path. [DER S1471]
- The Windows 11 25H2 baseline package's `MSFT-Win11-v25H2.PolicyRules` lists 330 computer and 5 user registry values, 67 security-template lines and 23 advanced-audit subcategories. [DOC S-bzyxqg37]
- Against 24H2, the 25H2 `.PolicyRules` adds three registry values (command line in process creation events, IE11 launch via COM disabled, the PSExec/WMI ASR rule `d1e49aac-8f56-4280-b9ba-993a6d77406c` at `2`), changes NetBIOS settings from `2` to `0`, adds one SID to *Impersonate a client after authentication*, and drops four settings: WDigest `UseLogonCredential`, Defender *Scan packed executables*, Defender *exclusions visible to local users* and the security option `NoLMHash`. User-rights lines that only reorder their SIDs are not changes. [DER S1472, S-bzyxqg37: key-by-key comparison of the two extracts]
- Microsoft's 25H2 announcement names the same changes and says the added *Impersonate a client* member is `RESTRICTED SERVICES\PrintSpoolerService`. [DOC S1402]
- The announcement's change table does not mention `NoLMHash`, yet the setting is absent from both the 25H2 `.PolicyRules` and its settings workbook. [DER S1402, S-bzyxqg37: `NoLMHash` searched in the package and the post]
- The Windows Server 2025 v2602 package's `MSFT-WS2025-v2602.PolicyRules` has separate Member Server and Domain Controller GPOs (each with its own Credential Guard/VBS GPO) plus Domain Security, Defender Antivirus and IE11 GPOs: 389 computer and 3 user registry values, 118 security-template lines and 54 audit subcategories in all. [DOC S-p6phzp72]
- Column `ms_ws2025` reads every GPO but the Domain Controller ones. 346 of the Windows 11 24H2 baseline rows have a Server 2025 member-server value, and 19 of those differ: among them account lockout (threshold 3 against 10, duration and reset 15 against 10 minutes), deny-network and deny-RDP logon for `S-1-5-114` and Guests instead of `S-1-5-113`, *Allow log on locally* for Administrators only, and Success and Failure auditing for Audit Policy Change and Sensitive Privilege Use. [DER S1472, S-p6phzp72: join on registry key and value name, user right, policy name or audit GUID]
- The Intune Windows baseline for 24H2 says it takes its settings from the Windows 11 24H2 security baseline in the Security Compliance Toolkit, and keeps only the settings that apply to Windows devices managed through Intune. [DOC S-oeh7ui3h]
- Column `intune_baseline` is `yes` when the setting name from the Microsoft workbook appears as a setting name in the Intune 24H2 pivot. This is true for 164 of 335 registry rows. `no_name_match` does not prove absence, because CSP names can differ from GPO names. [DER S1472,S-oeh7ui3h]
- The Intune pivot links most settings to their Policy CSP section, and ADMX-backed CSP sections name the registry key and value they write. Joining those on registry key and value marks 28 more registry rows `yes_csp` (192 of 335 in all); 111 name-matched rows have no registry mapping on their CSP page (non-ADMX policies such as MSSecurityGuide, Audit and DeviceLock). [DER S-oeh7ui3h, S-4krq7dui: the 45 CSP pages the 24H2 pivot links, read 2026-09-28]
- The OSConfig Server 2025 baseline v2606 (MIT) has 361 settings. It maps 329 of them to a CIS RuleID and 147 to a Server 2025 STIG id. [DOC S1598]
- 165 crosswalk rows match an OSConfig registry setting, and 152 of those carry a CIS RuleID. [DER S1598: join on registry key + value]
- `SecurityPolicyDsc` and `AuditPolicyDsc` are the adapter paths for security policy, user rights and advanced audit policy (see `dsc-coverage.md`). [DOC S1413, S1414, S1415, S1416, S1594, S1595]
- Those `adapter:` rows run through `Microsoft.Adapter/WindowsPowerShell`: the 3.3.0 manifests deprecate `Microsoft.Windows/WindowsPowerShell` in its favour, and the Windows PowerShell adapter runs PSDSC resources, including script-based ones such as `SecurityPolicyDsc`'s four `MSFT_*` MOF resources. [DOC S114, S1473, S1596]
- `known_compat_risk` for the Credential Guard rows: Credential Guard is turned on with *Turn On Virtualization Based Security* (registry `EnableVirtualizationBasedSecurity=1` with `LsaCfgFlags` 1 for UEFI lock or 2 without lock), a restart applies it, and only *Enabled without lock* can be turned off remotely; applications that need Kerberos DES, unconstrained delegation, TGT extraction or NTLMv1 break. [DOC S-lzzhbeao, S1478]
- `known_compat_risk` for the LSA protection row: LSA plug-ins and drivers must carry a Microsoft signature or they fail to load; audit mode logs CodeIntegrity events 3065 and 3066 (Operational log) for those that would fail; enabling needs a restart. [DOC S1477]
- `known_compat_risk` for candidates C1, C3 and C5: long paths only help apps that declare `longPathAware`; SMB1 is not installed by default on Windows 11 and changing the feature restarts the computer; PowerShell 2.0 is removed from patched Windows 11 24H2 and Server 2025, and `-Version 2` calls start PowerShell 5.1. [DOC S1591, S1590, S1479]

## Reference
Columns in `settings-crosswalk.csv`:

| Column | Meaning |
|---|---|
| `setting` | Workbook path > name. If the workbook has no match: `HKLM\key!value`, or the STIG rule title for STIG-only rows |
| `mechanism` | `registry`, `security_policy`, `user_rights`, `audit_policy`, `service`, `optional_feature`, `firewall`, `other` |
| `registry_path`, `value_name`, `value_type` | For registry-backed rows. For audit rows, `value_name` holds the subcategory GUID |
| `ms_baseline_value` | Value in the Microsoft 24H2 baseline, or `not set` |
| `ms_gpo` | Baseline GPO that sets it (for example `MSFT Windows 11 24H2 - Computer`) |
| `ms_25h2` | Value in the Windows 11 25H2 baseline, `-` when it does not set it (empty for candidates C3 feature, C7, C8) |
| `ms_ws2025` | Value in the Windows Server 2025 v2602 baseline's member-server GPOs (Domain Controller GPOs not read), `-` when it does not set it |
| `stig_id`, `stig_value` | Windows 11 V2R9 rule id(s) and the required value (decimal) |
| `stig_server2025_id` | Server 2025 V1R3 rule with the same registry value |
| `cis_id`, `cis_level` | Windows 11 CIS: empty, needs the registered benchmark (see `gaps.md`) |
| `osconfig_ws2025_2606` | OSConfig Server 2025 v2606 expected value (member server) for the same registry value; 165 rows match |
| `cis_ws2025_id_via_osconfig` | CIS RuleID that Microsoft's OSConfig 2606 file maps to that setting (CIS Windows Server 2025 benchmark, version not stated in the file) |
| `intune_baseline` | `yes` (name match), `yes_csp` (the linked CSP section writes the same registry value) or `no_name_match` (registry rows only) |
| `dsc_v3_path` | `native:<type>`, `adapter:<module>` (with maintenance state), or `none` |
| `known_compat_risk` | Only risks that an official source documents |
| `first_baseline_candidate` | `C1`-`C8` for first-baseline candidates. `C3-related` marks the baseline rows that disable SMB1 through the registry |
| `ms_and_stig` | `yes` when both the Microsoft baseline and the STIG set it |

Artifacts beside this file (digests in `artifacts/*/README.md`):
- `artifacts/microsoft/win11-24h2-baseline-policyrules.csv`, `win11-25h2-baseline-policyrules.csv` and `ws2025-2602-baseline-policyrules.csv`: factual extracts of the `.PolicyRules` files, without their local build paths.
- `artifacts/disa/*-xccdf.xml`: verbatim XCCDF files.
- `artifacts/disa/stig-*-rules.csv`: the parsed rules.
- `artifacts/microsoft/intune-baseline-*.md`: pinned Intune reference pages.

## Examples
- A drift report on `PL-LT-00123` for `HKLM\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters!SMB1` would cite `WN11-00-000165`. The Microsoft baseline value is `0`; DSC reads it with `Microsoft.Windows/Registry`.
