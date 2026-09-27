---
topic: security/policy-precedence
priority: P0
applies_to: "Windows 11 Enterprise 24H2/25H2, AD DS Group Policy, Intune MDM, ConfigMgr current branch co-management, DSC 3.3.0"
retrieved_utc: 2026-09-27
sources: [S1412, S1592, S1593, S1591, S1477, S-oeh7ui3h, S-ycuzbjvk, S-d24ri6px, S-vzmmy23x, S-37hjm3ml, S-z4y7mew3, S-is2wluoa, S-jtwizv2p]
status: complete
---

# What wins: local policy, domain GPO, MDM, co-management, ConfigMgr, DSC

## Summary
- **Order of Group Policy:** local GPO, then site, domain and OU GPOs. The GPO closest to the object wins, unless a higher link is *enforced*.
- **Refresh:** the background refresh runs every 90 minutes plus up to 30 random minutes (every 5 minutes on DCs). By default an extension reapplies settings only when its GPOs or its GPO list changed.
- So a DSC `set` that changes a GPO-managed value is **not** necessarily reverted at the next refresh. It is reverted at the next change to the GPO or its GPO list, or at the next forced refresh (`gpupdate /force` reapplies all settings); whether a startup (foreground) run reapplies unchanged settings is not stated. [DER S1592,S-ycuzbjvk: the refresh rule plus the /force parameter]
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
- By default, during a policy refresh a client-side extension reapplies its settings only when it detects a change to one of its GPOs or to its GPO list, for performance reasons. [DOC S1592]
- `gpupdate /force` reapplies all policy settings; by default only settings that changed are applied. [DOC S-ycuzbjvk]
- So a local change to a GPO-managed registry value can stay until the GPO or the GPO list changes, or a forced refresh runs. [DER S1592,S-ycuzbjvk: the refresh rule plus the /force parameter]
- An extension can be set to reapply even when its GPOs have not changed: each extension's processing policy (for example *Configure registry policy processing*, or `ADMX_GroupPolicy/CSE_Security` for security settings) has a **Process even if the Group Policy objects haven't changed** option, for reapplying a setting a user has changed, and a **Do not apply during periodic background processing** option. [DOC S-d24ri6px]
- For registry policy that option is off by default, and Microsoft's firewall guidance advises leaving it off, because with it every background refresh rewrites the firewall policy and restarts WFP filtering, once per GPO. [DOC S-vzmmy23x]
- No current Microsoft page gives the security-settings extension its own periodic reapply interval: the Group Policy processing page states only the change-driven default, and the `CSE_Security` policy offers the process-even-if-unchanged option; the "every 16 hours" figure often quoted is not on these pages (read 2026-09-27). [DER S1592, S-d24ri6px: absence on both pages]
- All Group Policy processing must finish within 60 minutes. This timeout cannot be changed. [DOC S1592]
- Tattooing, as Microsoft's pages state it:
  - Group Policy **preferences** do not remove their settings when a GPO no longer applies unless the item has **Remove this item when it is no longer applied** (which forces the Replace action); preference items reapply at every refresh unless set to apply once. [DOC S-37hjm3ml]
  - FSLogix's ADMX writes its app, logging and profile settings under `HKLM\SOFTWARE\FSLogix`, which Microsoft calls preferences, not policies: they remain when the GPO is removed or the setting is set to *Not Configured*, while its settings under `HKLM\SOFTWARE\Policies\FSLogix\ODFC` "correctly reset themselves". [DOC S-z4y7mew3]
  - But `Remove-GPRegistryValue` says removing a registry-based policy setting from a GPO does not delete the value on clients; to delete it the setting must be set to disabled (example key under `...\Policies\...`). [DOC S-is2wluoa]
- So values written outside a `Policies` key persist after the GPO goes. For values under `Policies`, only the FSLogix page says they reset, and `Remove-GPRegistryValue` says removing a setting from a GPO leaves the value, so setting it to *Disabled* is the one documented way to clear it (see `_conflicts.md`). [DER S-37hjm3ml, S-z4y7mew3, S-is2wluoa: the three statements read together]
- The only official statement found is the LSA protection page: setting the policy to *Not Configured* after it was enabled does not clean up the earlier setting, which "continues to be enforced". [DOC S1477]
- The GP setting *Enable Win32 long paths* controls the same value (`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled`) that a DSC `Microsoft.Windows/Registry` resource would write. That value is not under a `Policies` key. [DOC S1591]
- `MDMWinsOverGP` (Policy CSP `ControlPolicyConflict`):
  - default is `0`, and with `0` Group Policy is not blocked;
  - it applies only to policies represented in the Policy CSP with a GP mapping (ADMX-backed or mapped), not to other CSPs such as Defender. [DOC S1412]
- When `MDMWinsOverGP` is `1`, the policy should be set at every MDM sync. Each sync then removes conflicting values that scripts or users set outside GP. [DOC S1412]
- Co-management has seven workloads: compliance policies, Windows Update policies, resource access, Endpoint Protection, device configuration, Office Click-to-Run apps and client apps. Until a workload is switched, ConfigMgr keeps managing it. [DOC S1593]
- When the *Device configuration* workload is switched to Intune:
  - ConfigMgr settings can still reach co-managed devices through a configuration baseline with **Always apply this baseline even for co-managed clients**;
  - the option can be set when the baseline is created or later on its General tab;
  - switching Device configuration also moves Resource access and Endpoint Protection. [DOC S1593]
- When the Endpoint Protection workload is switched, ConfigMgr policies stay on the device until Intune policies overwrite them. [DOC S1593]
- Removing tattooed Endpoint Protection settings also needs the Device configuration workload switched. [DOC S1593]
- The Intune Windows security baseline is derived from the same Security Compliance Toolkit baseline. So a device that gets both the GPO baseline and the Intune baseline receives two writers for many of the same values. [DOC S-oeh7ui3h]
- How DSC `test` behaves when GPO also manages a value:
  - `Microsoft.Windows/Registry` `test` compares the live value with the document;
  - if GPO holds the same value, `test` reports in desired state;
  - if GPO holds a different value, `test` reports drift at every evaluation, and a `set` would last only until the next GPO reapplication;
  - there is no "managed by" field in the resource output. [DER S1592, `dsc/manifests-diff.md`]
- A ConfigMgr registry configuration item with **Remediate noncompliant rules when supported** sets the value (or creates it) when it is noncompliant; remediation needs the rule operator **Equals**. [DOC S-jtwizv2p]
- ConfigMgr compliance *remediation* can be kept off deliberately (visibility-first design). With remediation on, a baseline and a GPO that disagree each rewrite the value on their own schedule: Microsoft's compliance pages give no precedence between a configuration item and Group Policy (only ASR rules, which ConfigMgr applies through the Policy CSP, have a documented order). [DER S-jtwizv2p, S1592: remediation rule plus GP reapply, no precedence stated]

## Reference

| Writer | When it writes | Scope of the precedence rule | Source |
|---|---|---|---|
| Local GPO / LGPO | foreground + background refresh | overridden by any domain GPO | S1592 |
| Domain GPO (Administrative Templates) | startup, logon, every 90 min + ≤30 min when changed; DC 5 min | LSDOU; enforced > block inheritance | S1592 |
| Intune MDM (Policy CSP) | each MDM sync | loses to GP unless `MDMWinsOverGP=1`, and only for GP-mapped Policy CSP settings | S1412 |
| Co-management workload | per workload slider | Intune authority for switched workloads; baselines apply to co-managed devices only with *Always apply…* | S1593 |
| ConfigMgr baseline remediation | on baseline evaluation schedule | no documented precedence against GPO | UNK |
| DSC `set` | when run | none; last writer wins until the next reapply by another writer | DER |

See `intune/configuration-policies.md` for how settings-catalog, custom OMA-URI and ADMX (built-in, imported or
runtime-ingested) configuration policies are built and refreshed; this article covers only their precedence against
GPO, compliance policy and co-management.

## Examples
- `PL-LT-00123` is co-managed with Device configuration switched to Intune. A ConfigMgr baseline that lacks *Always apply this baseline even for co-managed clients* is not evaluated on that device. Treated as `unknown`, not compliant. [DER S1593]
