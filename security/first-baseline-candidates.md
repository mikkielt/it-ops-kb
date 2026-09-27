---
topic: security/first-baseline-candidates
priority: P0
applies_to: "Windows 11 Enterprise 24H2/25H2; Microsoft baseline 24H2 package; DISA STIG Windows 11 V2R9 (2026-08-10); DSC 3.3.0"
retrieved_utc: 2026-09-26
sources: [S1470, S1471, S1472, S-oeh7ui3h, S1477, S1478, S1479, S1590, S1591, S1592, S1593, S-ycuzbjvk]
status: partial
---

# Evidence for the first baseline

## Summary
- **Only one** of the eight first-baseline candidates is recommended by both the Microsoft baseline and the STIG: SMB1 disabled (C3). The Microsoft baseline disables it through the registry, the STIG through the feature plus the registry. PowerShell 2.0 absent (C5) is in the STIG only.
- The other five candidates (long paths, `wuauserv` start type, RDP denied, Remote Registry, DSC version) and the marker (C8) are in **neither** baseline. They are operational settings, not security guidance.
- C5 is now nearly empty: PowerShell 2.0 was removed from Windows 11 24H2 in the August 2025 update, so "absent" holds on any patched 24H2 or 25H2 device.
- **84 settings** are set by both the Microsoft 24H2 baseline and the Windows 11 STIG and have a native DSC v3 path. 38 of them are also in the Intune 24H2 baseline by name. They are listed in `settings-crosswalk.csv`, filter `ms_and_stig=yes` and `dsc_v3_path` starting `native`.
- Every Microsoft-baseline row is, by construction, a setting that Microsoft ships as a GPO. Whether the estate's GPOs set it is known only from the GPO export (`gpo/gpo-export.md`).

## Facts
- The Microsoft 24H2 baseline sets `LanmanServer\Parameters\SMB1=0` ("Configure SMB v1 server") and `MrxSmb10\Start=4` ("Configure SMB v1 client driver"). STIG rules `WN11-00-000165` and `WN11-00-000170` require the same values, and `WN11-00-000160` requires the SMBv1 protocol disabled. [DOC S1472,S1470]
- SMBv1 is not installed by default in any edition of Windows 11, or in Windows Server 2019 and later. Disabling or enabling it with `Disable-WindowsOptionalFeature` restarts the computer. Registry changes to SMB1 need a restart. [DOC S1590]
- In Windows 11 24H2 and Windows Server 2025, SMB signing is required by default. This can block connections to workgroup computers, guest shares and third-party SMB servers without signing. [DOC S1590]
- PowerShell 2.0 removal:
  - removed from Windows 11 24H2 starting with the August 2025 update, and from Windows Server 2025 starting September 2025 (KB5065506, published 2025-08-11);
  - scripts that ask for `-Version 2` start the default PowerShell 5.1 instead. [DOC S1479]
- STIG `WN11-00-000155` requires the PowerShell 2.0 feature disabled, but its check text marks it Not Applicable for Windows 11 24H2 and newer, so it is not a live requirement in the 24H2 comparison. The Microsoft 24H2 baseline has no such setting. [DOC S1470,S1472]
- Long paths:
  - `LongPathsEnabled=1` under `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem` only affects applications that declare `longPathAware`;
  - each process caches the value, so a reboot might be needed before all apps see it;
  - GP *Enable Win32 long paths* controls the same value. [DOC S1591]
- LSA protection (not a gate candidate; in both baselines):
  - since Windows 11 22H2 it is on by default for new installs that are enterprise-joined and HVCI-capable, without a UEFI lock;
  - LSA plug-ins must be Microsoft-signed or they fail to load;
  - audit mode is on by default from 22H2 (CodeIntegrity events 3065/3066);
  - changes need a restart. [DOC S1477]
- Credential Guard (not a gate candidate; in both baselines):
  - on by default from Windows 11 22H2 and Windows Server 2025 for domain-joined, non-DC devices that meet the licence and hardware requirements, without a UEFI lock, unless it was explicitly disabled before the upgrade;
  - it breaks applications that need Kerberos DES, unconstrained delegation, TGT extraction or NTLMv1. [DOC S1478]
- The Microsoft baseline sets both the policy (`LsaCfgFlags=1`, UEFI lock) and `RunAsPPL=1`. `RunAsPPL=1` means UEFI lock. [DOC S1472,S1477]
- A UEFI-locked setting cannot be changed back by registry or policy. [DOC S1477]
- On a co-managed device with Device configuration moved to Intune, a ConfigMgr baseline applies only with *Always apply this baseline even for co-managed clients*. [DOC S1593]
- By default a Group Policy refresh reapplies an extension's settings only when its GPOs or GPO list changed; `gpupdate /force` reapplies all settings. See `policy-precedence.md`. [DOC S1592,S-ycuzbjvk]
- For C2 (`wuauserv`), C4 (`fDenyTSConnections`) and C6 (`RemoteRegistry`), the Windows 11 default values were not confirmed from an official page this pass. [UNK]

## Reference

| # | Candidate | CIS L1 | MS baseline 24H2 | STIG W11 V2R9 | Intune 24H2 | Mechanism | DSC v3 path | Documented impact | Reboot | In a Microsoft GPO baseline |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Long paths enabled | UNK | no | no | UNK | registry | native `Microsoft.Windows/Registry` | only longPathAware apps [S1591] | may be needed for all processes [S1591] | no (GP setting exists) |
| C2 | `wuauserv` start type | UNK | no | no | UNK | service | native `Microsoft.Windows/Service` | UNK | UNK | no |
| C3 | SMB1 absent | UNK | yes (registry: server `SMB1=0`, client `MrxSmb10 Start=4`) | yes `WN11-00-000160/165/170` | yes | optional feature + registry | native `OptionalFeatureList` / `Registry` | SMB1-only devices stop working [S1590] | yes [S1590] | yes |
| C4 | RDP denied on workstations | UNK | no | no (only RDS hardening rules `WN11-CC-000270…290`) | UNK | registry | native `Microsoft.Windows/Registry` | UNK | UNK | no |
| C5 | PowerShell 2.0 absent | UNK | no | yes `WN11-00-000155` (N/A on 24H2 and newer); Server 2025 `WN25-00-000410` | UNK | optional feature | native `OptionalFeatureList` | already removed on patched 24H2 [S1479] | feature changes usually restart; UNK for an already-removed feature | no |
| C6 | Remote Registry disabled | UNK | no | no | UNK | service | native `Microsoft.Windows/Service` | UNK | UNK | no |
| C7 | DSC engine version present | n/a | n/a | n/a | n/a | other | none native in 3.3.0 | — | — | — |
| C8 | Marker `HKLM\SOFTWARE\<tool>\baseline` | n/a | n/a | n/a | n/a | registry | native `Microsoft.Windows/Registry` | — | no | no |

CIS L1 is `UNK` everywhere: the recommendation list needs registration (see `gaps.md`).

Examples of the 84 settings in both baselines with a native path (full list in the CSV):

| STIG | Setting | Value |
|---|---|---|
| WN11-CC-000190 | Turn off Autoplay | 255 |
| WN11-CC-000040 | Enable insecure guest logons | 0 |
| WN11-CC-000330 / -000345 | WinRM client / service Basic authentication | 0 |
| WN11-CC-000038 | WDigest Authentication | 0 |
| WN11-SO-000205 | `Lsa\LmCompatibilityLevel` | 5 |
| WN11-SO-000100 / -000120 | SMB client / server `RequireSecuritySignature` | 1 |
| WN11-SO-000270 | UAC `EnableLUA` | 1 |
| WN11-AU-000505 | Security event log maximum size (KB) | 196608 |

## Examples
- The ring 0 device `PL-LT-00123` runs a patched 24H2. `test` for C5 would find `MicrosoftWindowsPowerShellV2Root` absent or not found. How `OptionalFeatureList` reports a feature name that no longer exists is not documented. [UNK]
