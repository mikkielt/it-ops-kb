---
topic: windows/windows-365
priority: P2
applies_to: "Windows 365 Cloud PC (Enterprise, Frontline/Flex, Business, Government, Link, Boot), Graph v1.0, docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-3vcy7oqc, S-7haqmv5t, S-6bbkebpi, S-n5j76cvh, S-cklvv7d5, S-egljiuze, S-5alhdr35, S-lvqy67bp, S-vavpj2l2, S-pixm6i65, S-77ejmtcy, S-s4d4qbht, S-j3m43d2a, S-i3gqas6g, S-n3hgvxzn, S-k6rj6uel, S-qrxf7f4h, S-mbwkcgji]
status: complete
---

# Windows 365 (Cloud PC): editions, provisioning policies, remote actions, Graph API

## Summary
Windows 365 provisions a per-user Cloud PC virtual machine and streams it to any device; admins configure who
gets one (and which image/network) via a **provisioning policy**, and Windows 365 then checks licensing and
creates the Cloud PC automatically — admins don't create Cloud PCs manually. [DOC S-6bbkebpi, S-3vcy7oqc] Five
editions: Business, Enterprise, Government, Flex (formerly Frontline), Reserve; the overview page also lists the
AI-agent variant "Windows 365 for Agents" (preview). [DOC S-7haqmv5t, S-3vcy7oqc] Graph exposes the same objects under
`/deviceManagement/virtualEndpoint/...`, gated mostly by `CloudPC.ReadWrite.All`. [DOC S-n5j76cvh, S-cklvv7d5]

## Facts

### Editions and identity
- Windows 365 Business: up to 300 users, simple buy/deploy/manage; the feature table marks Intune policy-driven
  provisioning/management, custom images and Graph API enablement as Enterprise-only. [DOC S-7haqmv5t]
- Windows 365 Enterprise: no license limit; requires Windows 11/10 Enterprise, Microsoft Intune, and Microsoft
  Entra ID P1 per user; managed through Intune with Entra ID and Defender for Endpoint integration; unattended
  RPA/bot use needs a Microsoft 365 Unattended License. [DOC S-7haqmv5t]
- Windows 365 Government: spans a regulated US Government Community Cloud (GCC) and a public-facing cloud;
  Windows 365 Enterprise itself has been assessed by a FedRAMP-authorized auditor to meet FedRAMP requirements
  at data centers within the Continental US. [DOC S-7haqmv5t, S-3vcy7oqc]
- Windows 365 Flex, **Dedicated mode**: a single license lets you provision up to three Cloud PCs for
  non-concurrent use, each assigned to one user, with one concurrent session per license. **Shared mode**: a
  single license provisions one Cloud PC shared non-concurrently among a group of users (the licences set up for
  a group give that many Cloud PCs); user data is deleted at sign-out. [DOC S-77ejmtcy]
- Flex (then Frontline) GA since service release 2306, previously preview. [UNK: not in S-77ejmtcy as re-read 2026-09-27]
- Windows 365 Reserve: each user can have a single Reserve Cloud PC in addition to their per-SKU Enterprise
  Cloud PCs. [DOC S-6bbkebpi]
- In Enterprise, Business, and Government, users have a 1:1 relationship with their Cloud PC; with Flex, multiple
  users can non-concurrently access a single Cloud PC. [DOC S-3vcy7oqc]
- Windows 365 Link is a purpose-built thin-client device that connects directly to a Cloud PC: discrete TPM 2.0,
  Secure Boot, VBS, HVCI, BitLocker, strict Application Control, no local admin user, no local data/apps, no
  local storage; managed via Intune alongside other devices. [DOC S-s4d4qbht]
- Windows 365 Link device must be Microsoft Entra joined (by a user who can join devices to Entra ID); it can
  connect to Cloud PCs that are Entra joined or Entra hybrid joined; it enrolls into Intune via automatic
  enrollment during OOBE, which requires the joining user to hold an Entra ID Premium licence; optionally gated
  by Intune corporate-identifier enrollment (pre-uploaded serial/manufacturer/model). [DOC S-j3m43d2a]
  (see `autopilot/device-preparation.md` for the corporate-identifiers / device-association onboarding pattern
  it reuses, and `entra/device-identity.md` for Entra join vs. hybrid join)

### Provisioning policy and process
- Provisioning is one-time per user and per licence; each user can have up to one Cloud PC per Enterprise SKU, one
  Reserve Cloud PC, and multiple Flex Cloud PCs. [DOC S-6bbkebpi]
- A provisioning policy requires: **Network** (Microsoft-hosted network, or an Azure network connection (ANC)
  which can carry the Azure subscription, domain/OU, and AD credentials for hybrid join), **Image** (a gallery
  image or a custom image), optional **Configuration**, and **Assignment** (one or more Entra user groups —
  licensed users in the group are auto-provisioned, including ones added later). [DOC S-6bbkebpi]
- Changing a provisioning policy does not reprovision existing Cloud PCs and does not affect them; only newly
  (re)provisioned Cloud PCs get the new settings. Experience type, License type, and Frontline type can't be
  changed after creation; for Flex Shared-mode policies, Experience, Entra join type, Network, Geography, and
  Region also can't be changed (create a new policy instead). [DOC S-6bbkebpi]
- A provisioning policy can be deleted only if it has no assignment; removing the assignment puts its Cloud PCs
  into a grace period, after which they're auto-deleted (Flex Shared-mode and Reserve Cloud PCs have no grace
  period — they're deleted immediately). [DOC S-6bbkebpi]
- Policy assignment style: **Discrete** (a dedicated group per policy, preferred for distinct configurations) or
  **Hybrid** (policy assigned directly to the group-based licensing group; simpler for small/uniform deployments).
  [DOC S-6bbkebpi]
- Conflict resolution: for Enterprise and Reserve, a user assigned to more than one provisioning policy is
  provisioned only from the first-assigned policy (others ignored); for Flex, a user can be assigned multiple
  policies and all are honored. A user with multiple Enterprise licences gets one Cloud PC per licence, all from
  that single first-assigned policy (you cannot target different policies to different licences for one user).
  [DOC S-6bbkebpi]
- Provisioning failure retries automatically twice; after a third failure the process stops, the Cloud PC is
  marked **Failed**, and an admin must resolve the cause and press **Retry**. [DOC S-6bbkebpi]
- If all licences are tied to Cloud PCs already in a grace period, new provisioning is blocked until the grace
  period ends or an admin deprovisions a Cloud PC in grace. [DOC S-6bbkebpi]
- Reprovision deletes and recreates the Cloud PC from the policy's *current* settings (any changed image/policy
  settings since original provisioning take effect); all user data, apps, and customizations are lost. Flex
  Shared-mode supports **bulk reprovision** with an admin-chosen percentage of Cloud PCs kept available for users
  during the operation. [DOC S-6bbkebpi]
- Post-failure or post-grace-period cleanup runs about 3 hours later, removing Intune objects, Entra device
  objects, and Azure vNICs; network security groups are not cleaned up (other objects may depend on them); any
  on-prem AD computer accounts joined during provisioning are disabled, not deleted (Windows 365 lacks the
  on-prem delete permission), and should be cleaned up by the org's own maintenance process. [DOC S-6bbkebpi]

### Cloud PC object and remote actions (Graph)
- Resource: `cloudPC` under `/deviceManagement/virtualEndpoint/cloudPCs/{id}`; also enrolled into Intune (has a
  corresponding `managedDeviceId`) except for Windows 365 Business Cloud PCs, whose `managedDeviceId` and
  `managedDeviceName` are always null (Business Cloud PCs aren't auto-enrolled in Intune). [DOC S-egljiuze]
- Key `cloudPC` properties: `aadDeviceId`, `displayName` (max 64 chars, rename only via the rename action),
  `gracePeriodEndDateTime`, `imageDisplayName`, `onPremisesConnectionName`, `provisioningPolicyId`,
  `provisioningPolicyName` (max 120 chars), `provisioningType` (`dedicated` default, or `shared`),
  `servicePlanId`/`servicePlanName`, `userPrincipalName`. [DOC S-egljiuze]
- Cloud PC remote-action methods on `cloudPC`: List, Get, **End grace period**, **Reboot**, **Rename**,
  **Reprovision**, **Resize**, **Restore** (from a snapshot), **Troubleshoot**, List for user, Retrieve launch
  detail. [DOC S-egljiuze]
- `POST /deviceManagement/virtualEndpoint/cloudPCs/{id}/resize`, body `{"targetServicePlanId": "<guid>"}`,
  returns `204 No Content`; least-privileged permission (delegated and application) is `CloudPC.ReadWrite.All`;
  not supported for personal Microsoft accounts; available in the global service and US Government L4, not in
  US Government L5 (DOD) or China (21Vianet). [DOC S-5alhdr35]
- `POST /deviceManagement/virtualEndpoint/cloudPCs/{id}/restore`, body
  `{"cloudPcSnapshotId": "<snapshot id>"}`, returns `204 No Content`; same `CloudPC.ReadWrite.All` permission and
  same national-cloud availability as resize. [DOC S-lvqy67bp]
- `POST /deviceManagement/virtualEndpoint/cloudPCs/{id}/reprovision` uses the same `CloudPC.ReadWrite.All`
  permission model. [DOC S-vavpj2l2]
- Creating a provisioning policy (`POST /deviceManagement/virtualEndpoint/provisioningPolicies`, returns
  `201 Created` with a `cloudPcProvisioningPolicy`) also uses `CloudPC.ReadWrite.All` (delegated and
  application, least-privileged; personal Microsoft accounts not supported). [DOC S-cklvv7d5]
- `cloudPcProvisioningPolicy` key properties: `cloudPcNamingTemplate` (tokens `%USERNAME:x%`, `%RAND:x%`; total
  generated name ≤15 characters), `displayName` (required), `domainJoinConfigurations` (ordered list, priority
  for how Cloud PCs join Entra ID; required), `enableSingleSignOn` (bool, default `false` — lets Windows 365
  users authenticate to Entra ID passwordlessly, e.g. FIDO keys, to reach their Cloud PC), `imageDisplayName`,
  `cloudPcGroupDisplayName` (read-only), `autopatch` (Windows Autopatch settings, effective only when the tenant
  is enrolled in Autopatch and `microsoftManagedDesktop.managedType` is `starterManaged`), `alternateResourceUrl`
  (read-only). [DOC S-n5j76cvh, S-cklvv7d5]
- Other Graph `cloudPc*` resources: `cloudPcDeviceImage` and `cloudPcGalleryImage` (custom/gallery OS images),
  `cloudPcOnPremisesConnection` (Azure network connections, incl. health checks and AD password rotation),
  `cloudPcAuditEvent` (audit log), `cloudPcUserSetting`. [DOC S-k6rj6uel, S-pixm6i65]

### Windows 365 Boot
- Windows 365 Boot lets a shared or dedicated Windows 11 physical device sign a user in directly to their Cloud
  PC instead of the physical desktop; requires the physical device and the Cloud PC to run Windows 11 Enterprise,
  Professional, or IoT Enterprise, version 22621.3374 or later, and a Windows 365 Enterprise licence to create
  Boot provisioning policies. [DOC S-i3gqas6g, S-n3hgvxzn, S-qrxf7f4h]
- Two modes: **Shared** (multiple users per device, each routed to their own Cloud PC; supports FIDO
  authentication) and **Dedicated** (one user per device; supports Windows Hello for Business). Authentication
  support matrix: username/password (both modes), Windows Hello for Business (Dedicated only), FIDO key (both),
  convenience PIN (neither). [DOC S-i3gqas6g]
- Enabled through the `CloudDesktop` CSP (shared mode also applies `SharedPC` settings); troubleshooting
  registry entries to verify: `HKLM\Software\Microsoft\PolicyManager\current\device\CloudDesktop\BootToCloudMode=1`,
  `HKLM\...\WindowsLogon\OverrideShellProgram=1`, `HKLM\Software\Microsoft\Windows\CurrentVersion\SharedPC\NodeValues`
  entries `18=1` and `01=1`. [DOC S-mbwkcgji, S-qrxf7f4h]
- Deployment onboards the physical device through Windows Autopilot (`Get-WindowsAutopilotInfo -Online`) and
  requires the Windows App (package family name `MicrosoftCorporationII.Windows365_8wekyb3d8bbwe`) installed in
  **System** context so it's available to every signed-in user; an allowlist-style application-control policy on
  the device must explicitly allow this package or Windows 365 Boot fails to launch. [DOC S-n3hgvxzn, S-qrxf7f4h]

## Reference
- `autopilot/device-preparation.md`: device preparation (v2) is the closest Autopilot analogue for onboarding
  trusted devices (corporate identifiers vs. device association) and already documents the Automatic mode /
  Cloud PC provisioning policy link for Windows 365 Frontline shared mode; this article is the Windows 365-side
  counterpart for provisioning policies, editions, and the Graph `cloudPC`/`cloudPcProvisioningPolicy` objects.
- `intune/remote-actions.md`: covers the general Intune `managedDevice` remote-action model (wipe, retire, sync,
  MAA gating, daily limits); Cloud PC-specific actions (resize, restore, reprovision, end grace period) live on
  the separate `cloudPC` Graph resource documented here, not on `managedDevice`.
- `entra/device-identity.md`: Windows 365 Link and Cloud PC domain-join configurations use the same Entra join /
  hybrid join / trustType model documented there.

## Examples
- SNIPPET: Resize a Cloud PC to a new service plan (placeholders only); context: Graph v1.0, `CloudPC.ReadWrite.All`, not supported for personal Microsoft accounts, not available in US Gov L5/China; checked: no [DOC S-5alhdr35: same `POST .../cloudPCs/{id}/resize` request with a `targetServicePlanId` body]
```http
POST https://graph.microsoft.com/v1.0/deviceManagement/virtualEndpoint/cloudPCs/00000000-0000-0000-0000-000000000000/resize
Content-Type: application/json

{
  "targetServicePlanId": "30d0e128-de93-41dc-89ec-33d84bb662a0"
}
```
List a user's Cloud PCs (delegated, `CloudPC.ReadWrite.All`), user `jan.kowalski@corp.example.com`:
`GET /v1.0/users/jan.kowalski@corp.example.com/cloudPCs`.
