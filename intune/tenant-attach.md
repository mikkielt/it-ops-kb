---
topic: intune/tenant-attach
priority: P1
applies_to: "ConfigMgr current branch (2002+ feature), Intune admin center 2026-09"
retrieved_utc: 2026-09-24
sources: [S604, S605, S606, S607, S608]
status: complete
---
# Tenant attach

## Summary
Tenant attach uploads ConfigMgr devices to the Intune admin center (shown with **Managed by = ConfigMgr**) and lets
admins run a few ConfigMgr actions (machine/user policy sync, app evaluation, approved Run Scripts without parameters,
CMPivot, app install, timeline, resource explorer). It needs a working AdminService, a Global Administrator for onboarding,
and users that are synced hybrid identities with ConfigMgr and Intune permissions. Devices do not appear in Graph device lists.

## Facts
- Onboarding needs an Entra Global Administrator; it creates a third-party app and a first-party service principal in the tenant. [DOC S605]
- The AdminService must be set up and functional. [DOC S605]
- Tenant geography and service connection point location should match. [DOC S605]
- Users performing device actions must be synced (hybrid) users, discovered by Entra user discovery or AD user discovery (2103+), and need the Intune permission **Remote tasks > Initiate Configuration Manager action**. [DOC S605]
- Limitation: ConfigMgr (tenant-attached) devices are not included when retrieving a device list through PowerShell or Microsoft Graph; workaround is Export from All devices. [DOC S605]
- Upload scope: all devices with Client = Yes, or a single collection (child collections included). [DOC S606]
- **Enforce Role-based Access Control** is checked by default: ConfigMgr RBAC is enforced together with Intune RBAC; uncheck for Intune-RBAC-only or cloud-only accounts. [DOC S606]
- Tenant-attached devices get the Intune default scope tag and cannot be assigned other scope tags; removing the default tag hides the device. [DOC S606]
- Device actions from the admin center: Sync Machine Policy, Sync User Policy, App Evaluation Cycle. [DOC S606]
- Offboarding from the admin center can take up to two hours (minutes for a healthy 2103+ site). [DOC S606]
- Client details fields Last policy request, Last active time and Management point update once an hour. [DOC S604]
- Tenant-attach setup for endpoint security policies needs collections to be *enabled* for those policies; Azure Government not supported in that wizard flow (per S604). [DOC S604]
- Run Scripts from the admin center: only scripts already created and approved in ConfigMgr; scripts with parameters are not supported and not shown; PowerShell 3.0+ on client. [DOC S607]
- Run Scripts permissions: Read and Read Resource on the device's collection, an Intune role, a ConfigMgr security role for scripts, and Run Script on Collections. [DOC S607]
- The admin center script list shows scripts run directly against the device (admin center, SDK or console), not collection-targeted runs. [DOC S607]
- Action path: admin center → service connection point (CMGatewayNotificationWorker.log) → SMS_NOTIFICATION_SERVER → management point (BgbServer.log) → client (CcmNotificationAgent.log); missing ConfigMgr permissions show `Unauthorized` in CMGatewayNotificationWorker.log. [DOC S608]

## Reference
| Log | Where | Purpose [S608] |
|---|---|---|
| CMGatewaySyncUploadWorker.log | site server Logs | device upload |
| CMGatewayNotificationWorker.log | site server Logs | admin-center actions |
| GenericUploadWorker.log | site server Logs | onboarding / device post errors |
| BgbServer.log | management point | notification to client |
| CcmNotificationAgent.log | client | action execution |

## Examples
`PL-LT-00123` appears in Intune > Devices > All devices with Managed by = `ConfigMgr`; engineer `jan.kowalski` (synced user) runs **Sync Machine Policy**.
