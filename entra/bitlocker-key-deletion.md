---
topic: entra/bitlocker-key-deletion
priority: P1
applies_to: "Microsoft Entra ID (manage-device-identities ms.date 06/17/2026; soft delete preview ms.date 04/05/2026)"
retrieved_utc: 2026-09-25
sources: [S545, S546, S547, S531]
status: complete
---

# Deleting an Entra device deletes its BitLocker keys

## Summary
- BitLocker recovery keys are stored on the Entra device object; deleting the device deletes them.
- Device soft delete (preview, since 2026) keeps keys for 30 days before hard delete; hard delete loses them permanently.
- The device-management page still calls deletion "nonrecoverable" (see conflicts).

## Facts
- BitLocker keys for Windows 10+ devices are stored on the device object; deleting a stale device also deletes those keys. [DOC S545]
- Caution: back up BitLocker recovery keys, or confirm they are no longer needed, before deleting devices; otherwise data may be lost. [DOC S545]
- Deleting a device removes all details attached to it, for example BitLocker keys, and is a nonrecoverable activity. [DOC S546]
- Deleting requires Cloud Device Administrator, Intune Administrator or Windows 365 Administrator; Autopilot devices can't be deleted before they're deleted from Intune. [DOC S546]
- Soft delete (preview): a deleted device moves to a soft-deleted container; BitLocker keys and LAPS passwords remain accessible; after 30 days it's hard deleted automatically. [DOC S547]
- Soft-deleted devices are hidden from portal, Intune and Graph queries (HTTP 404); their DeviceId stays reserved. [DOC S547]
- Soft delete covers joined, hybrid joined and registered devices; devices without a recognized trust type (for example created via Graph) and some specialty types are hard deleted immediately. [DOC S547]
- Hard-deleted devices, BitLocker keys and LAPS passwords can't be recovered. [DOC S547]
- Entra Connect can auto-restore a soft-deleted hybrid device on the next sync when it recreates a device with the same DeviceId. [DOC S547]
- Viewing a key (Show Recovery Key) creates an audit entry in the `KeyManagement` category. [DOC S546]

## Reference
| State | Keys recoverable | Source |
|---|---|---|
| Disabled | yes (object kept) | S545 |
| Soft deleted (preview, <= 30 days) | yes | S547 |
| Hard deleted | no | S546, S547 |
| LAPS policy/settings/retrieval reference | see `windows/laps.md` | DOC |
| BitLocker CSP, silent encryption policy, encryption events | see `windows/bitlocker.md` | DOC |

## Examples
- Before any delete of `PL-LT-00123`, list keys: `GET /v1.0/informationProtection/bitlocker/recoveryKeys?$filter=deviceId eq '{deviceId}'` (least privileged BitlockerKey.ReadBasic.All; filter by deviceId is documented in S531).
