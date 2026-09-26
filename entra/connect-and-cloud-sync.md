---
topic: entra/connect-and-cloud-sync
priority: P1
applies_to: "Microsoft Entra Connect Sync 2.x, Microsoft Entra Cloud Sync (provisioning agent), Microsoft Graph synchronization API"
retrieved_utc: 2026-09-26
sources: [S-6q5tyxki, S-2vza23mx, S-lcd7y7ff, S-de2kio2b, S-bl4r6qrk, S-qwmc4yvw, S-i2npg2z3, S-t2wo7s3a, S-ze3aud2j, S-6clhfher, S-vra6j7cx, S-rb7ssjjy, S-plhfh6ev]
status: complete
---

# Microsoft Entra Connect Sync and Cloud Sync

## Summary
- Entra Connect Sync runs a full synchronization engine on-premises with configuration stored on that server; Entra Cloud Sync moves provisioning orchestration into the Microsoft Entra service, with lightweight provisioning agents acting only as a bridge to AD. [DOC S-2vza23mx]
- Full capability table: `sync-capability-comparison.csv`. Cloud Sync does not currently sync device objects, so hybrid Entra join (`entra/device-identity.md`, `entra/hybrid-deviceid-objectguid.md`) still requires Connect Sync or Cloud Kerberos Trust as the device-registration path. [DOC S-6q5tyxki]
- Connect Sync's default delta-sync interval and propagation-delay ceiling are covered in `auth/propagation-latency.md`; this article does not repeat those numbers.

## Facts
- Connect Sync default/minimum scheduler interval: 30 minutes (see `auth/propagation-latency.md` for the full derivation); `Set-ADSyncScheduler -CustomizedSyncCycleInterval d.HH:mm:ss` changes it, e.g. `-CustomizedSyncCycleInterval 03:00:00` for every 3 hours. [DOC S-de2kio2b]
- `Set-ADSyncScheduler` also accepts `NextSyncCyclePolicyType`, `PurgeRunHistoryInterval`, `SyncCycleEnabled`, `MaintenanceEnabled`; setting `IsStagingModeEnabled` directly is unsupported, as is modifying `SchedulerSuspended` (Connect sets it during an upgrade). [DOC S-de2kio2b]
- `Set-ADSyncScheduler -SyncCycleEnabled $false` disables the scheduler (needed before filtering or sync-rule changes); `-SyncCycleEnabled $true` re-enables it; `Start-ADSyncSyncCycle -PolicyType Delta` (or `Initial` for a full cycle) forces an out-of-band cycle. [DOC S-de2kio2b]
- Cloud Sync scheduling differs by workload: password hash sync every 2-5 minutes; user/group provisioning cycles roughly every 10-20 minutes, with actual latency depending on the volume of pending changes. [DOC S-lcd7y7ff]
- A Connect Sync staging server is placed into staging mode via the wizard's "Configure staging mode"/"Enable staging mode" checkbox; `Get-ADSyncScheduler` (module `ADSync`) then shows `StagingModeEnabled: True`. In staging mode, imports and synchronization still run but exports to Microsoft Entra ID are suppressed. [DOC S-bl4r6qrk, S-de2kio2b]
- Only one active Connect Sync server may use Password Writeback at a time: switching a staging server to active while another active server also has Password Writeback disrupts that other server's service-bus communication. [DOC S-bl4r6qrk]
- Cloud Sync capability comparison highlights (full table in the CSV): device synchronization (hybrid join) is Connect-only; disconnected-forest sync, multiple active agents/failover, group provisioning to AD, and on-demand provisioning are Cloud-Sync-only; device writeback is Connect-only and is described as discontinued in favor of Cloud Kerberos Trust. [DOC S-6q5tyxki]
- Cloud Sync's default source anchor is `ms-DS-ConsistencyGuid`, falling back to `objectGUID`; there is no supported way to change the Cloud Sync source anchor. [DOC S-lcd7y7ff]
- For Connect Sync, a custom install lets an admin choose "Let Azure manage the source anchor" (uses `ms-DS-ConsistencyGuid` logic) or pick a specific attribute such as `objectGUID`; the source anchor cannot later be changed, is case-sensitive, can't contain `@`, and is also called `immutableID` in federation scenarios. [DOC S-plhfh6ev]
- Cloud Sync auto-upgrades its provisioning agents; there is no supported way to disable auto-upgrade. [DOC S-lcd7y7ff]
- Device writeback (Connect Sync only): requires Entra ID P1 or P2; enables Windows Hello for Business hybrid certificate trust device registration and AD FS-based Conditional Access; devices must be in the same forest as users (single-forest only); only one device-registration configuration object is allowed per forest; it can take up to 3 hours for device objects to be written back to AD after enablement. [DOC S-qwmc4yvw]
- Device-writeback prerequisite: the target forest's schema must be at Windows Server 2012 R2 level or higher for the device object and its attributes to exist; the wizard runs `Initialize-ADSyncDeviceWriteBack -domainname <domain.com>` (from `AdSyncPrep.psm1`) per domain to prepare AD, requiring Enterprise Administrator credentials. [DOC S-qwmc4yvw]
- Entra Connect Sync 2.x versions retire 12 months after a newer version releases (policy effective 15 March 2023); a retired version can stop working unexpectedly, loses new security fixes and diagnostic tooling, and may not receive full support. [DOC S-i2npg2z3]
- Mandatory upgrade deadline: all Connect Sync services stop working on 30 September 2026 for tenants not on at least version 2.5.79.0 (a May 2025 release that hardened a back-end service). [DOC S-i2npg2z3]
- Azure AD Connect V1 (pre-2.x) retired 31 August 2022; as of 1 October 2023 Entra cloud services stopped accepting connections from V1 servers and identities no longer synchronize; all 1.x versions are now non-functional. [DOC S-t2wo7s3a]
- Cloud Sync provisioning agent prerequisites: a group Managed Service Account (gMSA), created automatically as `provAgentgMSA$` or supplied as a custom gMSA; a Hybrid Identity Administrator account (not a guest); a domain-joined host, recommended Windows Server 2025 or 2022 (older versions in extended support are usable but may need a paid support program); the host should be a Tier 0 server per the AD administrative tier model (installing on a domain controller is supported); AD schema must have `msDS-ExternalDirectoryObjectId` (available Windows Server 2016+); the Windows Credential Manager service (`VaultSvc`) must not be disabled; Microsoft recommends 3 active agents for high availability. [DOC S-ze3aud2j]
- gMSA creation prerequisites: the AD schema in the gMSA domain's forest must be at Windows Server 2012 level or later; PowerShell RSAT modules on a domain controller; at least one Windows Server 2012+ domain controller; the install host must run Windows Server 2016, 2019, or 2022 (or later, per the prerequisites page above). [DOC S-6clhfher]
- Cloud Sync agent install (PowerShell): `Add-AADCloudSyncGMSA -CustomGMSAName <name>$` for a precreated gMSA; `Add-AADCloudSyncADDomain -DomainName <domain> -Credential <cred> [-PreferredDomainControllers @(...)]` to add a domain (optionally pinning preferred DCs); `Restart-Service -Name AADConnectProvisioningAgent` after configuration changes. [DOC S-6clhfher]
- Sign-in role for both installing the provisioning agent and running the migration tool: Hybrid Identity Administrator (minimum). [DOC S-6clhfher]
- Cloud Sync device sync is a preview capability distinct from user/group provisioning; see `entra/hybrid-deviceid-objectguid.md` for its attribute mapping (`DeviceId <- objectGUID`, `DeviceTrustType` always `ServerAd`). [DER S-lcd7y7ff, cross-reference: entra/hybrid-deviceid-objectguid.md already documents the Cloud Sync device-sync mapping]
- Connect Sync filtering methods, combinable with a logical AND: domain-based, OU-based, attribute-based, and group-based (pilot-only, set only at initial custom install, cannot be re-enabled once disabled, and not supported to configure outside the wizard). [DOC S-rb7ssjjy]
- Both Connect Sync and Cloud Sync filter out AD objects with `isCriticalSystemObject=True` by default (e.g., built-in `Administrator`, `DomainAdmins`, `EnterpriseAdmins`), so those two groups do not sync to Entra ID by default; other objects later added to those groups are not filtered and do sync. [DOC S-rb7ssjjy]
- OU-based filtering hazard: renaming a filtered-in OU changes its DistinguishedName, silently dropping it from sync scope; the next full import then obsoletes (deletes) its objects in Entra ID unless the OU is reselected in the wizard first. [DOC S-rb7ssjjy]
- Graph synchronization API: `POST /servicePrincipals/{id}/synchronization/jobs` creates a `synchronizationJob` in a disabled state; `POST .../jobs/{jobId}/start` starts it (continues from a paused point, clears quarantine); `.../pause` and `.../restart` (with `{"criteria":{"resetScope":"Full"}}` to reprocess every object) round out job control; all return `204 No Content`. [DOC S-vra6j7cx]
- Least-privileged Graph permission for starting/creating a synchronization job: delegated `Synchronization.ReadWrite.All`, or application `Application.ReadWrite.OwnedBy` (higher-privileged: `Synchronization.ReadWrite.All`); delegated calls need the signed-in user to be an owner/member of the relevant object or hold Application Administrator, Cloud Application Administrator, or Hybrid Identity Administrator (the role needed to configure Cloud Sync). [DOC S-vra6j7cx]
- Warning in the synchronizationJob API: do not script continuous calls to start a running job, since that can stop the service; only call start when the job is paused or in quarantine. [DOC S-vra6j7cx]
- The Cloud Sync feature-comparison migration-tool prerequisites cap eligible environments to one AD forest with <=2,000 in-scope objects and additive OU inclusion scoping of <=30 containers per domain, and block migration when custom sync rules, group filtering, a custom UPN, directory extensions, device synchronization, or unsupported writeback scenarios are present. [DOC S-6q5tyxki]

## Reference
- `entra/sync-capability-comparison.csv`: the Connect Sync vs Cloud Sync feature table (users/groups, device sync, scale limits, filtering, writeback, provisioning direction).
- `entra/hybrid-deviceid-objectguid.md`: hybrid-join `deviceId`/`objectGUID` mapping for both Connect Sync and Cloud Sync device sync (preview); this article's Reference now also links back here for scheduler/staging/version-lifecycle context (back-link added).
- `entra/device-identity.md`: join types and `trustType` values that Connect Sync/Cloud Sync-driven hybrid join produces.
- `auth/propagation-latency.md`: the 30-minute default/minimum Connect Sync delta-sync interval and `Start-ADSyncSyncCycle -PolicyType Delta` as the documented propagation-delay mechanism; not repeated here in full.

## Examples
- Force an out-of-band delta cycle for tenant `corp.example.com` after a filtering change on `PL-SRV-0042`:
  ```powershell
  Import-Module ADSync
  Set-ADSyncScheduler -SyncCycleEnabled $false
  # ... make filtering/sync-rule changes ...
  Set-ADSyncScheduler -SyncCycleEnabled $true
  Start-ADSyncSyncCycle -PolicyType Delta
  ```
- Start a Cloud Sync provisioning job through Graph for a service principal in tenant `00000000-0000-0000-0000-000000000000`:
  ```http
  POST https://graph.microsoft.com/v1.0/servicePrincipals/{servicePrincipalId}/synchronization/jobs/{jobId}/start
  Authorization: Bearer {token}
  ```
- Add a Cloud Sync domain with preferred domain controllers on the agent host `PL-SRV-0042`:
  ```powershell
  $cred = New-Object System.Management.Automation.PSCredential -ArgumentList ("CORP\\svc-cloudsync", $securePassword)
  Add-AADCloudSyncADDomain -DomainName corp.example.com -Credential $cred -PreferredDomainControllers @("PL-SRV-0042")
  Restart-Service -Name AADConnectProvisioningAgent
  ```
