---
topic: graph/permissions
priority: P1
applies_to: "Microsoft Graph v1.0 and beta, docs-contrib commit 4ad99fd37a9e"
retrieved_utc: 2026-09-28
sources: [S512, S513, S514, S515, S516, S517, S518, S519, S520, S521, S522, S523, S524, S531, S-ilovbr2g]
status: complete
files: [graph/permission-ids.csv]
---

# Least-privileged Graph permissions per device call

## Summary
- `permissions.csv`: one row per call (list/get/delta/delete for devices, managedDevices, windowsAutopilotDeviceIdentities), delegated and application.
- `permission-ids.csv`: permission GUIDs from the permissions reference.
- Read of Entra devices: `Device.Read.All`. Intune devices: `DeviceManagementManagedDevices.Read.All`. Autopilot identities: `DeviceManagementServiceConfig.Read.All`.
- Delegated Entra device reads also need a supported Entra role for the signed-in user.

## Facts
- List/Get devices: least privileged `Device.Read.All` (delegated and application). [DOC S512,S513]
- `GET /devices/delta`: `Device.Read.All`; no higher-privileged permission listed. [DOC S514]
- Delete device: delegated `Directory.AccessAsUser.All`, application `Device.ReadWrite.All`; delegated caller needs Intune Administrator, Windows 365 Administrator or Cloud Device Administrator. [DOC S515,S516]
- Delegated device reads require a supported Entra role; the include lists Users, Directory Readers, Global Reader, Device Managers and others. [DOC S517]
- The permissions reference says `Device.ReadWrite.All` (application) does not allow device creation, deletion or update of alternative security identifiers, yet the Delete device permissions table lists it as the application permission for that call. [DOC S524, S515]
- List/Get managedDevices: `DeviceManagementManagedDevices.Read.All` then `.ReadWrite.All` (table ordered least to most privileged). [DOC S518,S519]
- Delete managedDevice: `DeviceManagementManagedDevices.ReadWrite.All`. [DOC S520]
- List/Get windowsAutopilotDeviceIdentities: `DeviceManagementServiceConfig.Read.All`; Delete: `DeviceManagementServiceConfig.ReadWrite.All`. [DOC S521,S522,S523]
- Personal Microsoft accounts are not supported for any of these calls. [DOC S512,S518,S521]
- List BitLocker recoveryKeys (`GET /informationProtection/bitlocker/recoveryKeys`, `$filter` on `deviceId`, no `$top`) never returns the `key` property; a delegated caller must be the registered owner of the device the key was backed up from or hold a supported Entra role (Cloud device administrator, Helpdesk administrator, Intune service administrator, Security administrator, Security reader, Global reader). Permission names per call: `permissions.csv`. [DOC S531]
- The Graph API pages list scopes but no Intune RBAC role per call; Intune's Graph-access guide says a user who manages Intune settings through such an app needs at least the Intune Service Administrator role and an Intune licence (stated for a partner's account in a customer tenant). [DOC S-ilovbr2g]

## Reference
- `permissions.csv`, `permission-ids.csv` (this directory).
- BitLocker CSP silent-encryption policy and recovery-key rotation: `windows/bitlocker.md`.
- `intune/remote-actions.md`: least-privileged permissions for the `managedDevice` remote-action *methods*
  (wipe, retire, sync, etc.), as opposed to the list/get/delete calls on the resources themselves covered here.

## Examples
- Delegated token for engineer `jan.kowalski@corp.example.com` with scopes `Device.Read.All DeviceManagementManagedDevices.Read.All DeviceManagementServiceConfig.Read.All`.
