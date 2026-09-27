---
topic: security/dsc-coverage
priority: P0
applies_to: "DSC 3.3.0 / 3.4.0-preview.1; Microsoft Windows 11 24H2 baseline; DISA STIG Windows 11 V2R9, Windows Server 2025 V1R3"
retrieved_utc: 2026-09-26
sources: [S1598, S1599, S1470, S1471, S1472, S1473, S1474, S1413, S1414, S1415, S1416, S1594, S1595, S1596, S-nkhgboup, S-ly6m2llb]
status: complete
---

# How much of each baseline native DSC v3 can express

## Summary
- **Microsoft Windows 11 24H2 baseline: 371 of 426 settings (87.1%)** have a native DSC v3 path: `Microsoft.Windows/Registry` or `Microsoft.Windows/Service`. Without the Internet Explorer 11 GPOs, the share is 236 of 291 (81.1%).
- The remaining **55 settings** have no native path: 9 account policies, 23 user rights and 23 advanced-audit subcategories. They are reachable only through community modules under the `Microsoft.Adapter/WindowsPowerShell` adapter.
- **STIG Windows 11 V2R9:** 131 of 257 rules (51.0%) are native. 80 (31.1%) are adapter-only, and 44 (17.1%) have no DSC path; most of those are procedural checks.
- **STIG Server 2025 V1R3:** 97 of 291 (33.3%) are native.
- The community modules for security policy (`SecurityPolicyDsc`) and audit policy (`AuditPolicyDsc`) are script/MOF resources, not class-based. Their last stable releases are from 2019.

## Facts
- 32 of the Microsoft baseline's 41 `security_policy` rows are registry-backed security options (`MACHINE\...` lines in `GptTmpl.inf`). `Microsoft.Windows/Registry` can read and write the same value that GPO writes through secedit. [DER S1472: line format `MACHINE\path\value=type,data`]
- 5 native registry rows are per-user (HKCU; 3 IE, 2 Windows). A baseline that runs as SYSTEM sees its own hive, not the signed-in user's. [DER S1472]
- `Microsoft.Windows/WindowsPowerShell` runs PSDSC resources in Windows PowerShell, including script-based ones. `Microsoft.DSC/PowerShell` discovers and invokes class-based PSDSC resources in PowerShell 7. [DOC S1473,S1474]
- The 3.3.0 manifests mark `Microsoft.DSC/PowerShell` and `Microsoft.Windows/WindowsPowerShell` as deprecated in favour of `Microsoft.Adapter/PowerShell` and `Microsoft.Adapter/WindowsPowerShell`. [DOC S114, via `dsc/manifests-diff.md`]
- `SecurityPolicyDsc` ships four MOF resources: `MSFT_AccountPolicy`, `MSFT_SecurityOption`, `MSFT_SecurityTemplate`, `MSFT_UserRightsAssignment`. It has no `source/Classes` folder, so it is not class-based. [DOC S1596]
- `SecurityPolicyDsc` releases:
  - last stable: 2.10.0.0 (2019-09-19);
  - last prerelease: 3.0.0-preview0006 (2021-05-21). [DOC S1594]
- The `SecurityPolicyDsc` repository is not archived and was last pushed on 2024-07-07. [UNK: not in S1596 as re-read 2026-09-27]
- `AuditPolicyDsc` 1.4.0.0 (2019-01-10), its last release, declares the DSC resources `AuditPolicySubcategory`, `AuditPolicyGUID`, `AuditPolicyOption` and `AuditPolicyCsv` in its PowerShell Gallery tags. [DOC S1595]
- That these are MOF (`MSFT_*`) resources and that the `AuditPolicyDsc` repository was last pushed on 2019-02-13. [UNK: not in S1596 as re-read 2026-09-27]
- So security policy, user rights and audit policy need a Windows PowerShell adapter plus a module whose last stable release is 5 to 7 years old. [DER S1473,S1594,S1595]
- No official page states that either module was tested with DSC v3. [UNK]
- The adapter declares `implementsPretest` and has no what-if, so `dsc config set --what-if` returns an error for those resources, not a dry run. [DOC S114, via `dsc/manifests-diff.md`]
- Neither the 3.3.0 nor the 3.4.0-preview.1 zip ships a native resource for secedit, user rights or audit policy. [DER S114,S115: absent from the manifest list in `dsc/manifests-diff.csv`]
- The GroupPolicyTemplate adapter (ADMX only) is in the 3.4 source tree but in neither release zip. ADMX registry policies already have a native Registry path, so it would not add coverage for the 55 non-registry settings. [DER S121,S115]
- OSConfig publishes its Windows Server 2025 security baselines as CSV files in `microsoft/osconfig` (MIT): versions 2409, 2411, 2504, 2510 and 2606. [DER S1598: file names beside the pinned 2606 file and the repository licence at commit `82a54b9e`]
- The 2606 file has 361 settings: Registry 216, Security Options 56, Security Policy 52, Audit Policy 34, SecuredCore 3. 271 give a registry key and 152 a CSP path. [DOC S1598]
- The OSConfig resource docs list four Windows resources: AccountPolicy, AuditPolicy, Registry and UserRightsAssignment. [DOC S1599]
- Their pages name the types `Microsoft.Windows/AccountPolicy`, `Microsoft.Windows/AuditPolicy`, `Microsoft.Windows/UserRightsAssignment` and `Microsoft.Windows/Registry`, and each documents `get` and `set` operations. [DOC S-nkhgboup]
- OSConfig releases are pre-releases; the latest is 1.3.12-preview5 (2026-05-20). [DOC S-ly6m2llb]
- These cover exactly the three mechanisms DSC 3.3.0 lacks natively. But they are OSConfig CLI resources: the repository has no `*.dsc.resource.json` manifest, and nothing states that `dsc.exe` can invoke them. [DER S1599,S114: no DSC manifest in the tree; type names only resemble DSC's] [UNK whether a DSC v3 manifest is planned]

## Reference

| Baseline (version, date) | Total | registry | security option (registry-backed) | account policy | user rights | audit | service | optional feature | firewall | other | **native** | adapter-only | none |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Microsoft Windows 11 24H2 (package 2024-09-30) | 426 | 335 | 32 | 9 | 23 | 23 | 4 | 0 | 0 | 0 | **371 (87.1%)** | 55 (12.9%) | 0 |
| same, without IE11 GPOs | 291 | 200 | 32 | 9 | 23 | 23 | 4 | 0 | 0 | 0 | **236 (81.1%)** | 55 (18.9%) | 0 |
| DISA Windows 11 V2R9 (2026-08-10) | 257 | 123 | (in registry) | 9 | 28 | 43 | 1 | 7 | 2 | 44 | **131 (51.0%)** | 80 (31.1%) | 44 (17.1%) + firewall 2 |
| DISA Server 2025 V1R3 (2026-08-10) | 291 | 96 | (in registry) | 8 | 22 | 38 | 0 | 1 | 1 | 125 | **97 (33.3%)** | 68 (23.4%) | 125 + firewall 1 |

The STIG counts classify rules by rule-id prefix and title (`WN11-AU` = audit, `-UR` = user rights, `-AC` = account policy; a registry path in the check text = registry). Server 2025 "other" includes the DC-only and member-server-only rules. [DER S1470,S1471]

`dsc_v3_path` counts in `settings-crosswalk.csv` (540 rows):

| dsc_v3_path | rows |
|---|---|
| `native:Microsoft.Windows/Registry` | 409 (3 of them candidates C1, C4, C8) |
| `native:Microsoft.Windows/Service` | 7 (2 candidates) |
| `native:Microsoft.Windows/OptionalFeatureList` | 9 (2 candidates) |
| `native:Microsoft.Windows/FirewallRuleList` | 2 |
| `adapter:SecurityPolicyDsc` | 39 |
| `adapter:AuditPolicyDsc/AuditPolicySubcategory` | 30 |
| `none` | 44 (43 STIG-only rules + candidate C7) |

## Examples
- A document for `PL-LT-00123` that needs `Advanced audit: Credential Validation = Success and Failure` would need `AuditPolicyDsc/AuditPolicySubcategory` through `Microsoft.Adapter/WindowsPowerShell`. That is a PowerShell script resource with no what-if.
