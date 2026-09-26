---
topic: intune/remote-actions
priority: P1
applies_to: "Microsoft Intune managedDevice remote actions, Graph v1.0 and beta, docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-mrrxrahv, S-s7srrfx2, S-hzezniod, S-x23bve2k, S-yl6lujud, S-f5w33mek, S-4krmuswc, S-lorbg35k, S-f6okqmo4, S-5jodj5ne, S-qe4vs4v7, S-iyxigs24, S-rsgl4z3v, S-v32a7r4i, S-ed2sjtub, S-oo6cpieu, S-zne522mq, S-cprqxpsz, S-sthrw3uz, S-cjehjzoc, S-3s4pyls4, S-n7sr56za, S-yuwg4jgb, S-2laa2ngs, S616, S609]
status: partial
files: [intune/remote-actions.csv]
---

# Intune managed-device remote actions

## Summary
Remote actions are `managedDevice` methods under `/deviceManagement/managedDevices/{id}/...` in Microsoft Graph
(most in v1.0, some newer ones only in beta), each exposed in the Intune admin center as a device-overview icon.
Full endpoint/permission/parameter table: `intune/remote-actions.csv` (17 rows). Retire, Wipe and Delete take
precedence over any other pending action on a device and count against tenant-wide daily limits; several actions
can be gated by a Multi Admin Approval access policy; most use the `DeviceManagementManagedDevices.PrivilegedOperations.All`
permission, least to most privileged.

## Facts
- The `managedDevice` resource's device-action methods include: retire, wipe, resetPasscode, remoteLock,
  requestRemoteAssistance, disableLostMode, locateDevice, bypassActivationLock, rebootNow, shutDown,
  recoverPasscode, cleanWindowsDevice, logoutSharedAppleDeviceActiveUser, deleteUserFromSharedAppleDevice,
  syncDevice, windowsDefenderScan, windowsDefenderUpdateSignatures, updateWindowsDeviceAccount. [DOC S-mrrxrahv]
- Wipe: `POST /deviceManagement/managedDevices/{id}/wipe`; delegated and application permission (least to most
  privileged) is `DeviceManagementManagedDevices.PrivilegedOperations.All`; personal Microsoft accounts aren't
  supported; parameters `keepEnrollmentData`, `keepUserData`, `macOsUnlockCode` (6-digit macOS MDM unlock PIN),
  `obliterationBehavior` (fallback wipe method on modern Macs), `persistEsimDataPlan`. [DOC S-s7srrfx2]
- Wipe daily tenant limit: 500 per day, cumulative across single-device actions, bulk actions and Graph API
  requests. [DOC S-cprqxpsz]
- Wipe on Windows uses the `doWipe` node of the RemoteWipe CSP, and can roll back to the previous state if
  interrupted (or require a full Windows reinstall if rollback fails). [DOC S-cprqxpsz]
- Wipe (and other actions) may be governed by an Intune access policy requiring Multiple Administrative Approval
  (MAA): a second administrator must approve before the wipe proceeds; see `intune/assignment-filters-and-rbac.md`
  for MAA's protected resource types (Device actions — wipe, retire, delete — is one of them). [DOC S-cprqxpsz]
- Retire: `POST /deviceManagement/managedDevices/{id}/retire`, no request body, least-privileged permission
  `DeviceManagementManagedDevices.PrivilegedOperations.All`; removes company data/settings and leaves personal
  data intact; daily tenant limit 1,000. [DOC S-hzezniod, S-zne522mq]
- Delete: `DELETE /deviceManagement/managedDevices/{id}`, least-privileged permission
  `DeviceManagementManagedDevices.ReadWrite.All` (not PrivilegedOperations.All); the actual command triggered
  depends on platform/enrollment: Windows, Apple mobile, macOS, and Android (device administrator or
  personally-owned work profile) trigger **Retire**; Android corporate-owned Fully Managed/Dedicated/Work
  Profile and AOSP trigger **Wipe**. [DOC S-x23bve2k, S-sthrw3uz]
- Delete daily tenant limit: 1,000 per day; this limit applies to Delete requests even when the delete triggers
  a Retire or Wipe command underneath. [DOC S-sthrw3uz]
- After a Delete, the device is immediately hidden from the admin center; the Device actions report shows
  `Completed` once the request is processed server-side, which for MDM devices does not confirm the client
  finished the underlying Retire. [DOC S-sthrw3uz]
- **Retire, Wipe and Delete take precedence over all other pending actions**: a device with several queued
  actions only carries out a Retire, Wipe or Delete; every other pending action is ignored. [DOC S-zne522mq]
- cleanWindowsDevice: `POST /deviceManagement/managedDevices/{id}/cleanWindowsDevice`, parameter `keepUserData`
  (Boolean), least-privileged permission `DeviceManagementManagedDevices.PrivilegedOperations.All`; this is the
  Graph action underlying the admin-center "Fresh Start" action, which reinstalls the latest Windows version and
  removes OEM-installed apps. [DOC S-yl6lujud, S-zne522mq]
- syncDevice: `POST /deviceManagement/managedDevices/{id}/syncDevice`, no body, least-privileged permission
  `DeviceManagementManagedDevices.PrivilegedOperations.All`. [DOC S-f5w33mek]
- rebootNow: `POST /deviceManagement/managedDevices/{id}/rebootNow`, no body, same least-privileged permission. [DOC S-4krmuswc]
- remoteLock: `POST /deviceManagement/managedDevices/{id}/remoteLock`, no body, same least-privileged permission;
  locks the device and (on supported platforms) resets its password. [DOC S-lorbg35k, S-zne522mq]
- locateDevice: `POST /deviceManagement/managedDevices/{id}/locateDevice`, no body; least-privileged permission
  is `DeviceManagementManagedDevices.ReadWrite.All` — lower-tier than the PrivilegedOperations.All most other
  actions need. [DOC S-f6okqmo4]
- windowsDefenderScan: `POST /deviceManagement/managedDevices/{id}/windowsDefenderScan`, parameter `quickScan`
  (Boolean: true = Quick Scan, false/omitted = Full Scan), least-privileged permission
  `DeviceManagementManagedDevices.PrivilegedOperations.All`. [DOC S-5jodj5ne]
- windowsDefenderUpdateSignatures: `POST /deviceManagement/managedDevices/{id}/windowsDefenderUpdateSignatures`,
  no body, same least-privileged permission. [DOC S-qe4vs4v7]
- rotateBitLockerKeys (beta): `POST /deviceManagement/managedDevices/{id}/rotateBitLockerKeys` (also under
  `comanagedDevices` and under `deviceHealthScripts`/`deviceManagementScripts` run-state paths), no body,
  least-privileged permission `DeviceManagementManagedDevices.ReadWrite.All`, Windows only. [DOC S-iyxigs24]
- rotateLocalAdminPassword (beta): `POST /deviceManagement/managedDevices/{id}/rotateLocalAdminPassword`, no
  body, least-privileged permission `DeviceManagementManagedDevices.PrivilegedOperations.All`; supported
  platforms are Windows (corporate-owned) and macOS enrolled via Automated Device Enrollment (ADE); manually
  triggers a Windows LAPS-managed local admin password rotation outside the scheduled cadence (see
  `windows/laps.md` for the policy that governs rotation itself). [DOC S-rsgl4z3v, S-yuwg4jgb]
- rotateLocalAdminPassword RBAC: a custom role needs **Remote tasks/Rotate Local Admin Password** plus
  read visibility into managed devices (e.g. Organization/Read, Managed devices/Read). [DOC S-yuwg4jgb]
- pauseConfigurationRefresh (beta): `POST /deviceManagement/managedDevices/{id}/pauseConfigurationRefresh`,
  parameter `pauseTimePeriodInMinutes` (Int32), least-privileged permission
  `DeviceManagementManagedDevices.PrivilegedOperations.All`; pauses ConfigMgr co-management ConfigRefresh
  reconciliation on the device for troubleshooting, maintenance, or making changes. [DOC S-v32a7r4i]
- initiateOnDemandProactiveRemediation (beta): `POST /deviceManagement/managedDevices/{id}/initiateOnDemandProactiveRemediation`,
  parameter `scriptPolicyId` (String), least-privileged permission
  `DeviceManagementManagedDevices.PrivilegedOperations.All`; this is the Graph action behind the admin-center
  "Run remediation" (preview) action documented in `intune/remediations.md` (RBAC **Remote tasks > Run
  remediation**, single device, device must be online with WNS reachable, only one run at a time per device). [DOC S-ed2sjtub, S609]
- collectDiagnostics is **not callable directly through Microsoft Graph**; it must be run from the admin center.
  Full contents and RBAC are documented in `intune/collect-diagnostics.md`. [DOC S616]
- Autopilot reset (admin-center action): documentation reference-links it to the **wipe** Graph action, not to
  a distinct Graph method; RBAC requires Help Desk Operator, School Administrator, or a custom role with
  **Remote tasks/Wipe** plus device-read visibility. [DOC S-cjehjzoc]
- Remote (not local) Windows Autopilot Reset does not start immediately: it runs when the device next checks in
  and receives updated policy; an admin can force this sooner with **Sync**. It requires the device to be MDM
  managed and Entra ID joined, and the initiating admin needs the Intune Service Administrator role; WinRE must
  be enabled (`reagentc.exe /enable`) on the device. [DOC S-3s4pyls4, S-n7sr56za]
- A remote Autopilot Reset removes the device's primary user and Microsoft Entra device owner; the next
  signed-in user becomes the new primary user/owner. Shared devices remain shared after the reset. [DOC S-n7sr56za]
- executeAction (beta, bulk): `POST /deviceManagement/managedDevices/executeAction` (also
  `/comanagedDevices/executeAction`), least-privileged permission
  `DeviceManagementManagedDevices.PrivilegedOperations.All`; body takes `actionName`
  (`managedDeviceRemoteAction` enum), `deviceIds` (collection), plus per-action parameters
  (`keepEnrollmentData`, `keepUserData`, `persistEsimDataPlan`, `notificationTitle`, `notificationBody`,
  `deviceName`, `carrierUrl`, `deprovisionReason`, `organizationalUnitPath`); returns `200 OK` with a
  `bulkManagedDeviceActionResult` listing `successfulDeviceIds`, `failedDeviceIds`, `notFoundDeviceIds`,
  `notSupportedDeviceIds`. [DOC S-oo6cpieu]
- Admin-center bulk device actions (a separate UI wizard, not necessarily the same Graph call as `executeAction`)
  operate on **up to 100 devices** at a time; bulk Wipe/Retire/Delete count toward each action's daily tenant
  limit. [DOC S-zne522mq]
- Device cleanup rules (Devices > Organize devices > Device cleanup rules) **hide** stale devices from the
  admin center and reports after they fail to check in for an admin-set number of days, between **30 and 270**;
  they don't wipe or retire the device, and a device reappears if it checks in again before its device
  certificate expires (after which it needs re-enrollment). One rule per platform; if both an all-platforms
  rule and a platform-specific rule exist, the rule with the fewer days wins. [DOC S-2laa2ngs]
- Device cleanup rules require the Intune Administrator role, or a custom role with **Managed Device Cleanup
  Rules/Update** and **Managed Device Cleanup Settings/Update** plus device-read visibility; they aren't
  available for Jamf-managed devices, and hiding a device in Intune does not remove it from Entra ID. [DOC S-2laa2ngs]
- Executing a single device action from the admin center follows the same general steps regardless of action:
  Devices > All devices > select device > select the action icon (or the "..." overflow) > confirm. [DOC S-zne522mq]
- RBAC preconditions for device actions are not uniform: some actions (e.g. wipe, retire, delete, rotate local
  admin password, run remediation, Autopilot reset) map to a named **Remote tasks** permission in a custom
  role (see `intune/assignment-filters-and-rbac.md` and `intune/rbac-built-in-roles.csv` for the built-in Help
  Desk Operator / School Administrator role grants); others (locateDevice, rotateBitLockerKeys) use the more
  general `DeviceManagementManagedDevices.ReadWrite.All` least-privileged Graph permission without a named
  RBAC permission documented on the API page. [DOC S-f6okqmo4, S-iyxigs24, S-yuwg4jgb]
- Whether Multi Admin Approval covers actions beyond wipe (e.g. retire, delete individually, or the beta
  actions) is not stated on the actions' own Graph or admin-center pages. [UNK]

## Reference
- `intune/remote-actions.csv`: one row per action (action, HTTP endpoint, v1.0/beta, least permission,
  platforms, parameters, notes, source).
- `intune/collect-diagnostics.md`: full detail on the Collect diagnostics action (not callable via Graph).
- `intune/remediations.md`: Run remediation / Proactive Remediations detail behind `initiateOnDemandProactiveRemediation`.
- `windows/laps.md`: the Windows LAPS policy that `rotateLocalAdminPassword` triggers an out-of-band rotation of.
- `windows/bitlocker.md`: BitLocker recovery-key policy that `rotateBitLockerKeys` rotates on demand.
- `intune/assignment-filters-and-rbac.md`: Intune RBAC (built-in roles, custom role Remote tasks permissions)
  and Multi Admin Approval, which can gate the wipe (and possibly other) remote actions.
- `graph/permissions.md`: least-privileged Graph permissions for reading/deleting the `managedDevice` and
  `device` resources themselves (as opposed to the action calls in this article).
- `intune/tenant-attach.md`: ConfigMgr-managed (tenant-attached) devices expose only Sync Machine/User Policy
  and App Evaluation Cycle from the admin center, not the Graph `managedDevice` actions in this article.
- `intune/remote-help.md`: the "New remote assistance session > Remote Help" entry point on the same
  device-overview action bar is a separate Intune Suite add-on with its own RBAC permission category and no
  Graph API — not one of the `managedDevice` methods documented here.

## Examples
Engineer `jan.kowalski` retires `PL-LT-00123` after a role change:
```http
POST https://graph.microsoft.com/v1.0/deviceManagement/managedDevices/{managedDeviceId}/retire
Authorization: Bearer {token}
```
Wiping a lost device `PL-LT-00123` while keeping enrollment data (device stays Autopilot-registered for
re-provisioning):
```http
POST https://graph.microsoft.com/v1.0/deviceManagement/managedDevices/{managedDeviceId}/wipe
Content-Type: application/json

{
  "keepEnrollmentData": true,
  "keepUserData": false
}
```
