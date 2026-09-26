---
topic: intune/remediations
priority: P1
applies_to: "Intune service, docs ms.date 2025-09-08 / 2025-10-02 / 2026-04-07"
retrieved_utc: 2026-09-24
sources: [S609, S610, S611]
status: partial
---
# Remediations (formerly Proactive Remediations)

## Summary
Script packages (detection + optional remediation) run by the Intune Management Extension (IME). Documented limits:
200 packages, 2,048-character output, hourly schedule must be under 24 h, policy retrieval every 8 h, 7-day reporting
cycle. Needs Windows Enterprise/Education E3/E5/A3/A5 or VDA per-user licences. A maximum *script size* for remediation
scripts is not documented (the 200 KB limit is documented only for platform PowerShell scripts).

## Facts
- Device requirements: Entra joined or hybrid joined, and either Intune-enrolled Windows Enterprise/Pro/Education or co-managed. [DOC S609]
- Licensing: Windows Enterprise E3/E5 (in Microsoft 365 F3/E3/E5), Windows Education A3/A5 (in Microsoft 365 A3/A5), or Windows VDA per user. [DOC S609]
- Permissions: rights under the **Device configurations** category; an Intune Service Administrator must confirm licensing before first use. [DOC S609]
- Up to 200 script packages. [DOC S609]
- Remediation script runs only when the detection script exits with `exit 1`; empty output means *issue isn't found*. [DOC S609]
- Scripts must be UTF-8; with **Enforce script signature check** they must be UTF-8 without BOM. [DOC S609]
- Maximum output size: 2,048 characters. [DOC S609]
- Without signature check scripts run with execution policy **Bypass**; with it, the device execution policy applies (client default Restricted, server default RemoteSigned). [DOC S609]
- Schedule options: Once, Hourly (interval every n hours, must be less than 24), Daily; device local time by default, optional UTC; missed runs run as soon as the device is online. [DOC S609]
- The same page also says custom script packages "are rerun every 24 hours" (see _conflicts). [DOC S609]
- On-demand **Run remediation** (preview): single Windows device, needs **Remote tasks > Run remediation** (plus Organization: Read during preview), device online with WNS reachable; only one at a time per device, rapid repeats can overwrite each other. [DOC S609]
- Policy retrieval: after device or IME restart, after user sign-in, and every 8 hours (fixed from IME service start). [DOC S609]
- Reporting: run-once scripts report after running; recurring scripts report within days 1-6 only on change, and every 7 days regardless. [DOC S609]
- IME check-in for new/updated installations every 8 hours, independent of MDM check-in; admin-center Sync triggers MDM and IME check-in. [DOC S611]
- IME requires version 1.58.103.0 or later for remediations and other IME payloads. [DOC S611]
- Remediation schedule health is logged in `HealthScripts.log`. [DOC S611]
- Platform (non-remediation) PowerShell scripts: must be less than 200 KB (ASCII) and time out after 30 minutes. [DOC S610]
- Maximum remediation script file size and remediation script timeout: not stated in S609. [UNK]

## Reference
See also `intune/remote-actions.md`: the Graph action behind the on-demand "Run remediation" button is
`initiateOnDemandProactiveRemediation` (beta), `POST /deviceManagement/managedDevices/{id}/initiateOnDemandProactiveRemediation`
with a `scriptPolicyId` parameter.

| Limit | Value | Source |
|---|---|---|
| Script packages per tenant | 200 | S609 |
| Output size | 2,048 characters | S609 |
| Hourly interval | < 24 h | S609 |
| Policy retrieval | every 8 h + restart + sign-in | S609 |
| Full report | every 7 days | S609 |
| Platform script size / timeout | < 200 KB / 30 min (platform scripts only) | S610 |

## Examples
Detection script for `PL-LT-00123` writes one line (`drift: service Spooler running`, < 2,048 chars) and `exit 1` to trigger the remediation script.
