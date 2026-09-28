---
topic: intune/co-management
priority: P1
applies_to: "ConfigMgr current branch (docs in memdocs intune/configmgr/comanage), Intune service 2026-09"
retrieved_utc: 2026-09-27
sources: [S1593, S-evoxmu7g, S-4u7zysla, S-ygo5rdrm, S-plmd2yke, S-wnwinphx]
status: complete
---
# Co-management workloads

## Summary
Co-management = ConfigMgr client + Intune MDM enrolment on the same Windows device. Seven workloads can be moved
one by one (slider: Configuration Manager / Pilot Intune / Intune). A ConfigMgr **baseline** keeps
applying to a co-managed device whose *Device configuration* workload is in Intune only if the baseline has
**Always apply this baseline even for co-managed clients** set. Co-management state is visible in WMI class
`SMS_Client_ComanagementState` on the site server.

## Facts
- Supported workloads: Compliance policies, Windows Update policies, Resource access policies, Endpoint Protection, Device configuration, Office Click-to-Run apps, Client apps. [DOC S1593]
- Workloads you don't switch stay with ConfigMgr; a switched workload can be switched back, possibly with impact (e.g. Windows/Office versions stay at later versions). [DOC S1593]
- Switching the Device configuration workload also moves the Resource Access and Endpoint Protection workloads. [DOC S1593]
- With Device configuration in Intune, ConfigMgr settings can still be deployed through a configuration baseline with **Always apply this baseline even for co-managed clients** enabled (set at creation or on the baseline's General tab). [DOC S1593]
- A settings-catalog policy is controlled by the Device Configuration slider regardless of its contents. [DOC S1593]
- Resource access workload: not supported starting version 2203; from 2403 the node is removed and the slider is mandated to Intune. [DOC S1593]
- Compliance policies workload: evaluation of custom configuration baselines can be added as a compliance-policy assessment rule. [DOC S1593]
- Client apps workload: on Windows 10 1903+ PowerShell scripts from Intune run on co-managed devices even when Client Apps is not switched. [DOC S1593]
- Slider positions: Configuration Manager, Pilot Intune (only devices in the per-workload pilot collection on the Staging tab), Intune (all co-managed Windows devices). [DOC S-evoxmu7g]
- With Pilot Intune for Endpoint Protection and Device Configuration, Intune deploys policies but does not remove them on unassignment; removal needs the workload fully in Intune. [DOC S-evoxmu7g]
- Switching a workload makes co-managed devices synchronize MDM policy from Intune automatically. [DOC S-evoxmu7g]
- Console path: Administration > Cloud Services > Cloud Attach (Co-management node for 2103 and earlier) > Properties > Workloads / Staging tabs. [DOC S-evoxmu7g]
- Paths to co-management: existing ConfigMgr clients that become hybrid-joined and enrol in Intune; or Entra-joined internet devices that auto-enrol and then get the ConfigMgr client. [DOC S-4u7zysla]
- Licensing: Entra ID P1 or P2, plus at least one Intune licence for the administrator. [DOC S-4u7zysla]
- Co-management alone does not manage internet-connected clients with ConfigMgr; that needs a CMG (independent features). [DOC S-4u7zysla]
- `SMS_Client_ComanagementState` (namespace `ROOT\SMS\site_<SITECODE>`) fields: MachineId, MDMEnrolled, Authority, ComgmtPolicyPresent; device is co-managed when MDMEnrolled = 1 and ComgmtPolicyPresent = 1. [DOC S-ygo5rdrm]
- Documented WQL for co-managed devices also tests `MDMProvisioned = 1` (a field not in the S-ygo5rdrm field list). [DOC S-plmd2yke]
- Deployment policies CoMgmtSettingsProd (targeted to All Systems, applicability: Windows 10 or later, not server OS) and a pilot policy; they count only devices where ConfigMgr applied the policy, not Intune enrolment. [DOC S-ygo5rdrm]
- New co-managed devices (Windows 10 1803+) auto-enrol with the Entra *device* token, falling back to user token; see ComanagementHandler.log. [DOC S-ygo5rdrm]
- The co-management troubleshooting article's client log samples test workloads against a `workloadFlags` value with a bitwise AND: `ComplRelayAgent.log` checks workload **2** (compliance, the CA workload), `CIAgent.log` checks workload **4** (resource access) and `WUAHandler.log` checks workload **16** (Windows Update for Business); in the samples `CoManagementSettings_Capabilities` is `7`. Logs: `CoManagementHandler.log`, `ComplRelayAgent.log`, `CIAgent.log`, `WUAHandler.log` in `%WinDir%\CCM\logs`. [DOC S-wnwinphx]
- No page gives the full per-workload bit table (the values for Endpoint Protection, device configuration, Office Click-to-Run and client apps are not shown; re-read 2026-09-27); treat 2, 4 and 16 as the only documented values. [DER S-wnwinphx, S-ygo5rdrm: three values appear only in log samples]

## Reference
- `intune/compliance-policies.md` covers the Intune-side "Require device compliance from Configuration Manager" Windows compliance setting (co-managed devices only; Intune-only devices return not available) and the tenant-wide compliance policy settings — the counterpart to the Compliance policies workload below.

| Workload | Moves with it | Note |
|---|---|---|
| Compliance policies | – | baseline can feed compliance [S1593] |
| Windows Update policies | – | ConfigMgr client settings must be adjusted manually [S1593]; see `windows/windows-update-management.md` for the Update CSP settings, Autopatch, hotpatch, and WUfB reports this workload moves control to |
| Resource access | removed 2403 | – |
| Endpoint Protection | – | ConfigMgr policies stay until Intune overwrites [S1593] |
| Device configuration | Resource access + Endpoint Protection | baselines need "Always apply..." [S1593] |
| Office Click-to-Run apps | – | – |
| Client apps | – | – |

## Examples
WQL (fixture names only; site code `PL1`): `select Name from SMS_R_System inner join SMS_Client_ComanagementState on SMS_Client_ComanagementState.ResourceId = SMS_R_System.ResourceId where ComgmtPolicyPresent = 1 and MDMEnrolled = 1` returns e.g. `PL-LT-00123`.
