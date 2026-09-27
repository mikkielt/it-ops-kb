---
topic: entra/stale-devices
priority: P1
applies_to: "Microsoft Entra ID (doc ms.date 06/27/2025)"
retrieved_utc: 2026-09-26
sources: [S545, S547, S504]
status: complete
---

# Stale device guidance (Entra)

## Summary
- Stale = registered device that has not accessed cloud apps for a chosen timeframe, measured by `approximateLastSignInDateTime` (activity timestamp).
- The timestamp is updated only when the change exceeds 14 days (+/-5 days); do not treat anything younger than 21 days as stale.
- Disable before delete; hybrid-joined Windows 10+ devices are cleaned up in on-premises AD and synced.

## Facts
- Detection uses the property `ApproximateLastSignInDateTime` (activity timestamp). [DOC S545]
- The activity timestamp is evaluated on device authentication: Conditional Access requiring managed devices or approved apps, Windows 10+ joined/hybrid devices active on the network, Intune check-ins. [DOC S545]
- The timestamp is replaced only if the delta from the stored value exceeds 14 days (+/-5 days variance). [DOC S545]
- A timestamp younger than 21 days should not be taken as a stale indicator. [DOC S545]
- The timestamp is not an audit; some active devices may have a blank timestamp. [DOC S545]
- Best practice: disable a device for a grace period before deleting it, because deletion can't be undone. [DOC S545]
- Cleanup account needs Cloud Device Administrator or Intune Administrator. [DOC S545]
- MDM-managed devices should be retired in the MDM before disabling or deleting. [DOC S545]
- System-managed devices such as Autopilot should not be deleted; once deleted they can't be reprovisioned. [DOC S545]
- Hybrid joined Windows 10+: disable or delete in on-premises AD and let Entra Connect sync the change. [DOC S545]
- Deleting a Windows 10+ hybrid device only in Entra ID causes it to re-sync as a new object in "Pending" state; re-registration is required. [DOC S545]
- Removing a Windows 10+/Server 2016 device from sync scope deletes the Entra device; adding it back creates a new "Pending" object. [DOC S545]
- Deleting in AD or Entra doesn't remove the registration on the client. [DOC S545]
- Device soft delete (preview) keeps deleted devices recoverable for 30 days; see `bitlocker-key-deletion.md`. [DOC S547]

## Reference
| Parameter | Value | Source |
|---|---|---|
| Timestamp update granularity | 14 days +/- 5 days | S545 |
| Minimum stale threshold | 21 days | S545 |
| Soft-delete retention (preview) | 30 days | S547 |

## Examples
- `GET /v1.0/devices?$filter=approximateLastSignInDateTime le 2026-06-01T00:00:00Z&$count=true` with `ConsistencyLevel: eventual`.
