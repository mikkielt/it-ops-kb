---
topic: security/settings-crosswalk
priority: P0
applies_to: "Windows 11 Enterprise 24H2 (Microsoft baseline package 24H2), DISA STIG Windows 11 V2R9 and Windows Server 2025 V1R3 (2026-08-10), Intune Windows baseline 24H2 pivot, DSC 3.3.0"
retrieved_utc: 2026-09-24
sources: [S1470, S1471, S1472, S1598, S1473, S1475, S1477, S1478, S1479, S1590, S1591, S1413, S1414, S1415, S1416, S1594, S1595, S1596]
status: partial
files: [security/artifacts/disa/, security/artifacts/microsoft/, security/artifacts/osconfig/]
---

# Settings crosswalk: Microsoft baseline × STIG × Intune × DSC v3

## Summary
- `settings-crosswalk.csv` has **540 rows**: all **426** settings of the Microsoft Windows 11 24H2 security baseline, **106** DISA Windows 11 V2R9 rules the Microsoft baseline does not set, and **8** first-baseline candidates.
- Rows come from machine-readable files: the baseline's `MSFT-Win11-v24H2.PolicyRules` and settings workbook, and the STIG XCCDF. Joins match registry path plus value name, audit subcategory, or user-right name. The Server 2025 STIG id is added where the same registry value appears there.
- 138 Microsoft baseline rows have a matching Windows 11 STIG rule. 84 of those use a native DSC v3 path.
- CIS columns are empty. The CIS benchmark text needs registration, so no CIS id was mapped (see `gaps.md`).
- The newest Microsoft package retrieved is 24H2. The 25H2 package file could not be found on the download host, so 25H2 deltas are in `baselines-catalog.md` only.

## Facts
- The Microsoft Windows 11 24H2 baseline package contains `Documentation/MSFT-Win11-v24H2.PolicyRules`. This XML lists every setting: 330 computer and 5 user registry values, 68 security-template lines and 23 advanced-audit subcategories. [DOC S1472]
- The 68 security-template lines split into 32 registry-backed security options (`MACHINE\...=type,value`), 9 account/system-access values, 23 user-rights assignments and 4 service start types (the Xbox services, all `4` = disabled). [DER S1472: parsed line prefixes]
- 135 of the 335 registry values belong to the two Internet Explorer 11 GPOs (132 computer, 3 user). [DER S1472: count by `PolicyName`]
- Windows 11 STIG V2R9 has 257 rules. 123 of them state a registry path and value in the check text. The rest are audit (43), user rights (28), account policy (9), optional features (7), firewall (2), service (1) and 44 procedural or other checks. [DER S1470: parsed XCCDF check-content; the mechanism comes from the rule-id prefix and the title, so it is heuristic]
- Windows Server 2025 STIG V1R3 has 291 rules, 96 of them with a registry path. [DER S1471]
- The Intune Windows baseline for 24H2 says it takes its settings from the Windows 11 24H2 security baseline in the Security Compliance Toolkit, and keeps only the settings that apply to Windows devices managed through Intune. [DOC S1475]
- Column `intune_baseline` is `yes` when the setting name from the Microsoft workbook appears as a setting name in the Intune 24H2 pivot. This is true for 164 of 335 registry rows. `no_name_match` does not prove absence, because CSP names can differ from GPO names. [DER S1472,S1475]
- The OSConfig Server 2025 baseline v2606 (MIT) has 361 settings. It maps 329 of them to a CIS RuleID and 147 to a Server 2025 STIG id. 165 crosswalk rows match an OSConfig registry setting, and 152 of those carry a CIS RuleID. [DOC S1598] [DER S1598: join on registry key + value]
- `SecurityPolicyDsc` and `AuditPolicyDsc` are the adapter paths for security policy, user rights and advanced audit policy (see `dsc-coverage.md`). [DOC S1413,S1415,S1594,S1595]

## Reference
Columns in `settings-crosswalk.csv`:

| Column | Meaning |
|---|---|
| `setting` | Workbook path > name. If the workbook has no match: `HKLM\key!value`, or the STIG rule title for STIG-only rows |
| `mechanism` | `registry`, `security_policy`, `user_rights`, `audit_policy`, `service`, `optional_feature`, `firewall`, `other` |
| `registry_path`, `value_name`, `value_type` | For registry-backed rows. For audit rows, `value_name` holds the subcategory GUID |
| `ms_baseline_value` | Value in the Microsoft 24H2 baseline, or `not set` |
| `ms_gpo` | Baseline GPO that sets it (for example `MSFT Windows 11 24H2 - Computer`) |
| `stig_id`, `stig_value` | Windows 11 V2R9 rule id(s) and the required value (decimal) |
| `stig_server2025_id` | Server 2025 V1R3 rule with the same registry value |
| `cis_id`, `cis_level` | Windows 11 CIS: empty, needs the registered benchmark (see `gaps.md`) |
| `osconfig_ws2025_2606` | OSConfig Server 2025 v2606 expected value (member server) for the same registry value; 165 rows match |
| `cis_ws2025_id_via_osconfig` | CIS RuleID that Microsoft's OSConfig 2606 file maps to that setting (CIS Windows Server 2025 benchmark, version not stated in the file) |
| `intune_baseline` | `yes` / `no_name_match` (registry rows only) |
| `dsc_v3_path` | `native:<type>`, `adapter:<module>` (with maintenance state), or `none` |
| `known_compat_risk` | Only risks that an official source documents |
| `first_baseline_candidate` | `C1`-`C8` for first-baseline candidates. `C3-related` marks the baseline rows that disable SMB1 through the registry |
| `ms_and_stig` | `yes` when both the Microsoft baseline and the STIG set it |

Artifacts beside this file (digests in `artifacts/*/README.md`):
- `artifacts/microsoft/win11-24h2-baseline-policyrules.csv`: a factual extract of the `.PolicyRules` file, without its local build paths.
- `artifacts/disa/*-xccdf.xml`: verbatim XCCDF files.
- `artifacts/disa/stig-*-rules.csv`: the parsed rules.
- `artifacts/microsoft/intune-baseline-*.md`: pinned Intune reference pages.

## Examples
- A drift report on `PL-LT-00123` for `HKLM\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters!SMB1` would cite `WN11-00-000165`. The Microsoft baseline value is `0`; DSC reads it with `Microsoft.Windows/Registry`.
