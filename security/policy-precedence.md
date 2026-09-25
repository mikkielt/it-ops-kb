---
topic: security/policy-precedence
priority: P0
applies_to: "Windows 11 Enterprise 24H2/25H2, AD DS Group Policy, Intune MDM, ConfigMgr current branch co-management, DSC 3.3.0"
retrieved_utc: 2026-09-24
sources: [S1412, S1592, S1593, S1591, S1477, S1475]
status: partial
---

# What wins: local policy, domain GPO, MDM, co-management, ConfigMgr, DSC

## Summary
- **Order of Group Policy:** local GPO, then site, domain and OU GPOs. The GPO closest to the object wins, unless a higher link is *enforced*.
- **Refresh:** the background refresh runs every 90 minutes plus up to 30 random minutes (every 5 minutes on DCs). By default an extension reapplies settings only when its GPOs or its GPO list changed.
- So a DSC `set` that changes a GPO-managed value is **not** necessarily reverted at the next refresh. It is reverted at the next change to the GPO, or at the next forced run (`gpupdate /force`, startup). [DER S1592]
- **MDM versus GP:** `MDMWinsOverGP` is off by default. When on, it covers only Policy CSP settings that have a GP equivalent.
- **Co-management:** when the *Device configuration* workload is moved to Intune, ConfigMgr configuration baselines stop applying to co-managed devices unless the baseline has **"Always apply this baseline even for co-managed clients"** enabled.
- **DSC `test`** reports only the live value against the document. It cannot tell which writer set the value.

## Facts
- GPO processing order: 1) the local GPO; 2) GPOs linked to sites; 3) GPOs linked to domains; 4) GPOs linked to OUs, parent OU first. Each later policy can override earlier ones. Domain-based GPOs override local policy. [DOC S1592]
- Link order and inheritance:
  - Among GPOs linked to the same container, the link with the lowest link order has precedence.
  - An *enforced* link stops lower containers from overriding it.
  - Enforced takes precedence over *block inheritance*. [DOC S1592]
- Computer policy applies at startup and user policy at logon (foreground). After that, policy refreshes in the background every 90 minutes, with a random addition of up to 30 minutes. Domain controllers check for computer policy changes every 5 minutes. [DOC S1592]
- "During a policy refresh, by default, a client-side extension reapplies policy settings only if it detects a change to one of its GPOs or to its list of GPOs." [DOC S1592] (quoted, 31 words; CC BY 4.0)
- So a local change to a GPO-managed registry value can stay until one of these happens:
  - the GPO or the GPO list changes;
  - a forced refresh;
  - the extension is set to process even when the GPOs have not changed.

  The page does not say whether the security-settings extension has a separate periodic reapply. [DER S1592] [UNK]
- All Group Policy processing must finish within 60 minutes. This timeout cannot be changed. [DOC S1592]
- Tattooing: none of the pages fetched this pass states whether registry values under `...\Policies\...` are removed when a GPO stops applying, or whether values outside `Policies` persist. [UNK, see `gaps.md`]
- The only official statement found is the LSA protection page: setting the policy to *Not Configured* after it was enabled does not clean up the earlier setting, which "continues to be enforced". [DOC S1477]
- The GP setting *Enable Win32 long paths* controls the same value (`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled`) that a DSC `Microsoft.Windows/Registry` resource would write. That value is not under a `Policies` key. [DOC S1591]
- `MDMWinsOverGP` (Policy CSP `ControlPolicyConflict`):
  - default is `0`, and with `0` Group Policy is not blocked;
  - it applies only to policies represented in the Policy CSP with a GP mapping (ADMX-backed or mapped), not to other CSPs such as Defender. [DOC S1412]
- When `MDMWinsOverGP` is `1`, it must be reapplied at every MDM sync. Each sync then removes conflicting out-of-band changes. [DOC S1412]
- Co-management has seven workloads: compliance policies, Windows Update policies, resource access, Endpoint Protection, device configuration, Office Click-to-Run apps and client apps. Until a workload is switched, ConfigMgr keeps managing it. [DOC S1593]
- When the *Device configuration* workload is switched to Intune:
  - ConfigMgr settings can still reach co-managed devices through a configuration baseline with **Always apply this baseline even for co-managed clients**;
  - the option can be set when the baseline is created or later on its General tab;
  - switching Device configuration also moves Resource access and Endpoint Protection. [DOC S1593]
- When the Endpoint Protection workload is switched, ConfigMgr policies stay on the device until Intune policies overwrite them. [DOC S1593]
- Removing tattooed Endpoint Protection settings also needs the Device configuration workload switched. [DOC S1593]
- The Intune Windows security baseline is derived from the same Security Compliance Toolkit baseline. So a device that gets both the GPO baseline and the Intune baseline receives two writers for many of the same values. [DOC S1475]
- How DSC `test` behaves when GPO also manages a value:
  - `Microsoft.Windows/Registry` `test` compares the live value with the document;
  - if GPO holds the same value, `test` reports in desired state;
  - if GPO holds a different value, `test` reports drift at every evaluation, and a `set` would last only until the next GPO reapplication;
  - there is no "managed by" field in the resource output. [DER S1592, `dsc/manifests-diff.md`]
- ConfigMgr compliance *remediation* can be kept off deliberately (visibility-first design). With remediation on, a baseline and a GPO that disagree would each rewrite the value on their own schedule. Microsoft states no precedence rule between them. [UNK]

## Reference

| Writer | When it writes | Scope of the precedence rule | Source |
|---|---|---|---|
| Local GPO / LGPO | foreground + background refresh | overridden by any domain GPO | S1592 |
| Domain GPO (Administrative Templates) | startup, logon, every 90 min + ≤30 min when changed; DC 5 min | LSDOU; enforced > block inheritance | S1592 |
| Intune MDM (Policy CSP) | each MDM sync | loses to GP unless `MDMWinsOverGP=1`, and only for GP-mapped Policy CSP settings | S1412 |
| Co-management workload | per workload slider | Intune authority for switched workloads; baselines apply to co-managed devices only with *Always apply…* | S1593 |
| ConfigMgr baseline remediation | on baseline evaluation schedule | no documented precedence against GPO | UNK |
| DSC `set` | when run | none; last writer wins until the next reapply by another writer | DER |

## Examples
- `PL-LT-00123` is co-managed with Device configuration switched to Intune. A ConfigMgr baseline that lacks *Always apply this baseline even for co-managed clients* is not evaluated on that device. Treated as `unknown`, not compliant. [DER S1593]
