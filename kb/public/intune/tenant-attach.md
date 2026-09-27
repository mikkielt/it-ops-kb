---
topic: intune/tenant-attach
priority: P1
applies_to: "ConfigMgr current branch (2002+ feature), Intune admin center 2026-09"
retrieved_utc: 2026-09-26
sources: [S-2kbcc36i, S-ounncxk4, S-e7ymdl3x, S-aaryifxi, S-6q3ioupn]
status: complete
---
# Tenant attach

## Summary
Tenant attach uploads ConfigMgr devices to the Intune admin center (shown with **Managed by = ConfigMgr**) and lets
admins run a few ConfigMgr actions (machine/user policy sync, app evaluation, approved Run Scripts without parameters,
CMPivot, app install, timeline, resource explorer). It needs a working AdminService, a Global Administrator for onboarding,
and users that are synced hybrid identities with ConfigMgr and Intune permissions. Devices do not appear in Graph device lists.

## Facts
- Onboarding needs an Entra Global Administrator; it creates a third-party app and a first-party service principal in the tenant. [DOC S-ounncxk4]
- The AdminService must be set up and functional. [DOC S-ounncxk4]
- Tenant geography and service connection point location should match. [DOC S-ounncxk4]
- Users performing device actions must be synced (hybrid) users, discovered by Entra user discovery or AD user discovery (2103+), and need the Intune permission **Remote tasks > Initiate Configuration Manager action**. [DOC S-ounncxk4]
- Limitation: ConfigMgr (tenant-attached) devices are not included when retrieving a device list through PowerShell or Microsoft Graph; workaround is Export from All devices. [DOC S-ounncxk4]
- Upload scope: all devices with Client = Yes, or a single collection (child collections included). [DOC S-e7ymdl3x]
- **Enforce Role-based Access Control** is checked by default: ConfigMgr RBAC is enforced together with Intune RBAC; uncheck for Intune-RBAC-only or cloud-only accounts. [DOC S-e7ymdl3x]
- Tenant-attached devices get the Intune default scope tag and cannot be assigned other scope tags; removing the default tag hides the device. [DOC S-e7ymdl3x]
- Device actions from the admin center: Sync Machine Policy, Sync User Policy, App Evaluation Cycle. [DOC S-e7ymdl3x]
- Offboarding from the admin center can take up to two hours (minutes for a healthy 2103+ site). [DOC S-e7ymdl3x]
- Client details fields Last policy request, Last active time and Management point update once an hour. [DOC S-2kbcc36i]
- Tenant-attach setup for endpoint security policies needs collections to be *enabled* for those policies; Azure Government not supported in that wizard flow (per S-2kbcc36i). [DOC S-2kbcc36i]
- Run Scripts from the admin center: only scripts already created and approved in ConfigMgr; scripts with parameters are not supported and not shown; PowerShell 3.0+ on client. [DOC S-aaryifxi]
- Run Scripts permissions: Read and Read Resource on the device's collection, an Intune role, a ConfigMgr security role for scripts, and Run Script on Collections. [DOC S-aaryifxi]
- The admin center script list shows scripts run directly against the device (admin center, SDK or console), not collection-targeted runs. [DOC S-aaryifxi]
- Action path: admin center → service connection point (CMGatewayNotificationWorker.log) → SMS_NOTIFICATION_SERVER → management point (BgbServer.log) → client (CcmNotificationAgent.log); missing ConfigMgr permissions show `Unauthorized` in CMGatewayNotificationWorker.log. [DOC S-6q3ioupn]

## Reference
See also `intune/assignment-filters-and-rbac.md`: general Intune RBAC (built-in roles, scope tags, Multi
Admin Approval) that tenant-attached devices' default-scope-tag restriction above extends.

`intune/remote-actions.md` covers the Graph `managedDevice` remote actions (wipe, retire, sync, etc.); tenant-attached
(ConfigMgr) devices are outside that Graph resource and instead only expose Sync Machine Policy, Sync User Policy
and App Evaluation Cycle from the admin center, per the "Device actions from the admin center" fact above.

| Log | Where | Purpose [S-6q3ioupn] |
|---|---|---|
| CMGatewaySyncUploadWorker.log | site server Logs | device upload |
| CMGatewayNotificationWorker.log | site server Logs | admin-center actions |
| GenericUploadWorker.log | site server Logs | onboarding / device post errors |
| BgbServer.log | management point | notification to client |
| CcmNotificationAgent.log | client | action execution |

## Examples
`PL-LT-00123` appears in Intune > Devices > All devices with Managed by = `ConfigMgr`; engineer `jan.kowalski` (synced user) runs **Sync Machine Policy**.
