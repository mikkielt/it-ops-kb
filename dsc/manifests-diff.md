---
topic: dsc/manifests-diff
priority: P0
applies_to: "Microsoft DSC 3.3.0 and 3.4.0-preview.1, Windows x64 release zips"
retrieved_utc: 2026-09-23
sources: [S105, S106, S114, S115, S120, S121, S122]
status: complete
---

# DSC resource manifests: 3.3.0 vs 3.4.0-preview.1

## Summary
- Every `*.dsc.resource.json`, `*.dsc.manifests.json` and `*.dsc.extension.json` in both Windows x64 zips is saved verbatim (MIT, Microsoft) under `manifests/3.3.0/` and `manifests/3.4.0-preview.1/` (hashes in `_parts/dsc/artifacts.csv`).
- 3.3.0 ships 27 manifest files (29 resource, adapter and extension types); 3.4.0-preview.1 ships 29 files (32 types).
- New in 3.4.0-preview.1: `Microsoft.Windows/EnvironmentVariable`, `Microsoft.Windows/EnvironmentVariableList`, `Microsoft.Filesystem.File/Content`. Changed: `Microsoft.Windows/UpdateList` 0.1.0 → 0.1.1 (gains native what-if and `requireSecurityContext: elevated`).
- Neither zip contains the Group Policy template adapter nor `Microsoft.Windows/Personalization`.
- Full table: `manifests-diff.csv` (one row per type).

## Facts
- The 3.3.0 Windows x64 zip contains 27 manifest files; the 3.4.0-preview.1 zip contains the same 27 plus `environment_variable.dsc.manifests.json` and `filecontent.dsc.resource.json` (and their executables). [DOC S114,S115]
- Only three manifest files differ in bytes between the zips: `environment_variable.dsc.manifests.json` (new), `filecontent.dsc.resource.json` (new), `windowsupdate.dsc.resource.json` (changed). [DER S114,S115: byte comparison of the extracted files]
- In 3.3.0, `Microsoft.Windows/UpdateList` 0.1.0 has `set.args: ["set"]` and a `preTest: true` key (not `implementsPretest`), and no `requireSecurityContext`; in 3.4.0-preview.1 (0.1.1) `set` adds `{"whatIfArg": "--what-if"}`, `implementsPretest: true`, `requireSecurityContext: elevated`, `whatIfReturns: state`. [DOC S114,S115]
- The Group Policy template adapter (`Microsoft.Adapter/GroupPolicyTemplate` 0.1.0, source `adapters/group_policy_template`) exists in the 3.4.0-preview.1 source tree but is not in `data.build.json` package lists and not in the 3.4.0-preview.1 zip. [DER S120,S121,S115: absent from package list and zip listing]
- `Microsoft.Windows/Personalization` 1.0.0 is an adapted resource YAML (`*.dsc.adaptedResource.yaml`, `requireAdapter: Microsoft.Windows.Adapter/Registry`, capabilities get/set, HKCU values) present in source for 3.3.0 and 3.4.0-preview.1 but not packaged in either zip. [DER S122,S114,S115: file in source, absent in zips]
- `Microsoft.DSC/PowerShell` and `Microsoft.Windows/WindowsPowerShell` carry a `deprecationMessage` pointing to the `Microsoft.Adapter/PowerShell` and `Microsoft.Adapter/WindowsPowerShell` adapters. [DOC S114]
- dsc derives capabilities from the manifest: `set` present → set; `set.handlesExist: true` → setHandlesExist; a `whatIfArg` in `set.args` or a legacy top-level `whatIf` operation → whatIf (SetWhatIf); `delete` with `whatIfArg` → deleteWhatIf; `test`, `export`, `resolve` present → those capabilities. [DOC S106]
- Resources whose manifest declares `requireSecurityContext: elevated` on an operation fail that operation unless dsc runs elevated (Administrator). [DOC S105]

## Reference
Column `whatif_*` = how `dsc ... set --what-if` behaves for that resource (see `what-if.md`): *native* = dsc passes the resource's `whatIfArg`; *synthetic* = dsc returns the `test` result without calling set; *error* = resource implements pre-test and has no what-if, so dsc returns "cannot process what-if execution type". `require_security_context` and `capabilities` are taken from 3.4.0-preview.1 (identical in 3.3.0 except `Microsoft.Windows/UpdateList`, which has no whatIf and no security context in 3.3.0).

| type | kind | in_3_3_0 | in_3_4_0_preview_1 | version_3_3_0 | version_3_4_0_preview_1 | capabilities_3_4_0_preview_1 | whatif_3_3_0 | whatif_3_4_0_preview_1 | require_security_context | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| `Microsoft.Adapter/PowerShell` | adapter | yes | yes | 0.1.0 | 0.1.0 | get set test export | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.Adapter/WindowsPowerShell` | adapter | yes | yes | 0.1.0 | 0.1.0 | get set test export | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.DSC.Debug/Echo` | resource | yes | yes | 1.0.0 | 1.0.0 | get set test export | synthetic (test result) | synthetic (test result) |  |  |
| `Microsoft.DSC.Transitional/PowerShellScript` | resource | yes | yes | 0.2.0 | 0.2.0 | get set test | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.DSC.Transitional/RunCommandOnSet` | resource | yes | yes | 0.1.0 | 0.1.0 | get set | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.DSC.Transitional/WindowsPowerShellScript` | resource | yes | yes | 0.2.0 | 0.2.0 | get set test | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.DSC/Assertion` | group | yes | yes | 0.1.0 | 0.1.0 | get set test | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.DSC/Group` | group | yes | yes | 0.1.0 | 0.1.0 | get set test | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.DSC/Include` | importer | yes | yes | 0.1.0 | 0.1.0 | get set test | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  |  |
| `Microsoft.DSC/PowerShell` | adapter | yes | yes | 0.1.0 | 0.1.0 | get set test export | none: error (implementsPretest, no what-if) | none: error (implementsPretest, no what-if) |  | deprecated |
| `Microsoft.Filesystem.File/Content` | resource | no | yes |  | 0.1.0 | get set test export |  | synthetic (test result) |  |  |
| `Microsoft.OpenSSH.SSHD/Subsystem` | resource | yes | yes | 0.2.0 | 0.2.0 | get set setHandlesExist whatIf | native (set whatIfArg) | native (set whatIfArg) |  |  |
| `Microsoft.OpenSSH.SSHD/SubsystemList` | resource | yes | yes | 0.2.0 | 0.2.0 | get set whatIf | native (set whatIfArg) | native (set whatIfArg) |  |  |
| `Microsoft.OpenSSH.SSHD/Windows` | resource | yes | yes | 0.1.0 | 0.1.0 | get set whatIf | native (set whatIfArg) | native (set whatIfArg) |  |  |
| `Microsoft.OpenSSH.SSHD/sshd_config` | resource | yes | yes | 0.2.0 | 0.2.0 | get set whatIf export | native (set whatIfArg) | native (set whatIfArg) |  |  |
| `Microsoft.PowerShell/Discover` | extension | yes | yes | 0.1.1 | 0.1.1 | discover |  |  |  |  |
| `Microsoft.Windows.Adapter/Registry` | adapter | yes | yes | 0.1.0 | 0.1.0 | get set export | synthetic (test result) | synthetic (test result) |  |  |
| `Microsoft.Windows.Appx/Discover` | extension | yes | yes | 0.1.0 | 0.1.0 | discover |  |  |  |  |
| `Microsoft.Windows/EnvironmentVariable` | resource | no | yes |  | 0.1.0 | get set setHandlesExist test |  | synthetic (test result) |  |  |
| `Microsoft.Windows/EnvironmentVariableList` | resource | no | yes |  | 0.1.0 | get set setHandlesExist test |  | synthetic (test result) |  |  |
| `Microsoft.Windows/FeatureOnDemandList` | resource | yes | yes | 0.1.1 | 0.1.1 | get set export | synthetic (test result) | synthetic (test result) | get=elevated set=elevated export=elevated |  |
| `Microsoft.Windows/FirewallRuleList` | resource | yes | yes | 0.3.0 | 0.3.0 | get set setHandlesExist whatIf export | native (set whatIfArg) | native (set whatIfArg) | set=elevated |  |
| `Microsoft.Windows/OptionalFeatureList` | resource | yes | yes | 0.1.1 | 0.1.1 | get set export | synthetic (test result) | synthetic (test result) | get=elevated set=elevated export=elevated |  |
| `Microsoft.Windows/RebootPending` | resource | yes | yes | 0.1.0 | 0.1.0 | get | n/a (no set) | n/a (no set) |  |  |
| `Microsoft.Windows/Registry` | resource | yes | yes | 1.0.0 | 1.0.0 | get set whatIf delete deleteWhatIf | native (set whatIfArg) | native (set whatIfArg) |  |  |
| `Microsoft.Windows/RegistryList` | resource | yes | yes | 1.0.0 | 1.0.0 | get set setHandlesExist whatIf | native (set whatIfArg) | native (set whatIfArg) |  |  |
| `Microsoft.Windows/Service` | resource | yes | yes | 0.1.1 | 0.1.1 | get set whatIf export | native (set whatIfArg) | native (set whatIfArg) | set=elevated |  |
| `Microsoft.Windows/UpdateList` | resource | yes | yes | 0.1.0 | 0.1.1 | get set whatIf export | synthetic (test result) | native (set whatIfArg) | set=elevated | changed keys: schema,set,version |
| `Microsoft.Windows/WMI` | adapter | yes | yes | 1.0.0 | 1.0.0 | get set | synthetic (test result) | synthetic (test result) |  |  |
| `Microsoft.Windows/WindowsFeatureList` | resource | yes | yes | 0.1.1 | 0.1.1 | get set whatIf export | native (set whatIfArg) | native (set whatIfArg) | set=elevated |  |
| `Microsoft.Windows/WindowsPowerShell` | adapter | yes | yes | 0.1.0 | 0.1.0 | get set test export | synthetic (test result) | synthetic (test result) |  | deprecated |
| `Microsoft/OSInfo` | resource | yes | yes | 0.1.0 | 0.1.0 | get test export | n/a (no set) | n/a (no set) |  |  |

Manifest files (3.3.0 zip): appx.dsc.extension.json, assertion, echo, featureondemand, group, include, optionalfeature, osinfo, PowerShell_adapter, powershell.dsc.extension.json, powershell, psscript, reboot_pending, registry.dsc.manifests.json (Registry, RegistryList, Registry adapter), RunCommandOnSet, sshd_config, sshd-subsystem, sshd-subsystemList, sshd-windows, windows_feature, windows_firewall, windows_service, WindowsPowerShell_adapter, windowspowershell, windowsupdate, winpsscript, wmi.

Other files in both zips (not saved except settings/examples): `dsc.exe`, resource executables, `dsc_default.settings.json` and `dsc.settings.json` (saved in `zip-extras/`), `windows_baseline.dsc.yaml` and `windows_inventory.dsc.yaml` (sample documents, saved in `zip-extras/`), `dsc-bicep-ext.exe`, `y2j.exe`, psDscAdapter and WMI adapter scripts.

## Examples
Check which types a host's dsc really has (read-only):
```powershell
dsc resource list --output-format json | ConvertFrom-Json | Select-Object type, version, capabilities
```
On PL-SRV-0042 running 3.3.0 this lists no `Microsoft.Windows/EnvironmentVariable` and no `Microsoft.Filesystem.File/Content`.
