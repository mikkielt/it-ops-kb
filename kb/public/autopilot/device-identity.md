---
topic: autopilot/device-identity
priority: P1
applies_to: "Windows Autopilot (memdocs), Graph v1.0/beta windowsAutopilotDeviceIdentity"
retrieved_utc: 2026-09-27
sources: [S504, S508, S509, S545, S553, S554, S555, S-jjyryhyn, S-q7ach7kp, S-frph46kv, S-d3ml3kug, S-6i4enlqz]
status: complete
---

# Autopilot device identity: hardware hash, ZTDID, physicalIds, group tag

## Summary
- A device is identified to Autopilot by its hardware hash (4K HH); registration creates an Entra device object.
- The ZTDId is stored in the Entra device's `physicalIds` as `[ZTDId]:<value>`; group tag is `[OrderID]:<value>`; purchase order is `[PurchaseOrderId]:<value>`.
- The Graph `windowsAutopilotDeviceIdentity.id` is documented only as "The GUID for the object" (v1.0 and beta resource pages at microsoft-graph-docs-contrib 4ad99fd3, re-read 2026-09-27), and no Autopilot, Entra or Graph page says it equals the `[ZTDId]` value in the Entra device's `physicalIds`; match the two by serial number or hardware hash, not by assuming they are equal. [DER S508, S509, S-6i4enlqz: absence across the resource pages and Autopilot group docs]

## Facts
- Registration associates the device's hardware hash with the Autopilot service; registering automatically creates a Microsoft Entra object used to identify the device before user sign-in. [DOC S-jjyryhyn]
- If that Entra object is deleted, the device can fail to enroll through Autopilot. [DOC S-jjyryhyn]
- The hardware hash includes manufacturer, model, device serial number, hard drive serial number and generation time; it changes each time it is generated. [DOC S-jjyryhyn]
- All Windows Autopilot devices store ZTDId, "a unique value assigned to all imported Windows Autopilot devices", in the device `physicalIds` property. [DOC S553]
- Dynamic group rule for all Autopilot devices: `(device.devicePhysicalIDs -any (_ -startsWith "[ZTDid]"))`. [DOC S-frph46kv]
- Intune's group tag maps to the `OrderID` attribute on Entra devices: `[OrderID]:<tag>` in `devicePhysicalIds`. [DOC S-frph46kv,S554]
- `devicePhysicalIds` values used by Autopilot include `[ZTDId]`, `[OrderID]`, `[PurchaseOrderId]`. [DOC S554]
- Graph query for Autopilot devices: `devices?$filter=physicalIds/any(p: startswith(p, '[ZTDID]'))`. [DOC S-d3ml3kug]
- Graph `device.physicalIds` is documented as "For internal use only". [DOC S504]
- Import CSV header: `Device Serial Number,Windows Product ID,Hardware Hash,Group Tag,Assigned User`; serial number and hardware hash required; up to 500 rows per file. [DOC S-q7ach7kp]
- `windowsAutopilotDeviceIdentity.id` is described as "The GUID for the object". [DOC S508]
- The Autopilot identity carries `azureActiveDirectoryDeviceId` ("to be deprecated") and `managedDeviceId`; beta adds `azureAdDeviceId`. [DOC S508,S509]
- Deleting an Entra device associated with an Autopilot object: user-driven redeploys create a new Entra device without ZTDID; self-deploying and pre-provisioning fail with a ZTDID mismatch. [DOC S545]
- The Entra optional token claim `ztdid` (Zero-touch Deployment ID) is "The device identity used for Windows AutoPilot". [DOC S555]

## Reference
| physicalIds prefix | Meaning | Source |
|---|---|---|
| `[ZTDId]` | Autopilot zero-touch device id | S553, S554 |
| `[OrderID]` | Intune group tag | S-frph46kv, S554 |
| `[PurchaseOrderId]` | purchase order | S554 |

## Examples
- Dynamic group for group tag `PL-KRK`: `(device.devicePhysicalIds -any (_ -eq "[OrderID]:PL-KRK"))`.
