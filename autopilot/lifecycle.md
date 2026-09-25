---
topic: autopilot/lifecycle
priority: P1
applies_to: "Windows Autopilot (memdocs, deregister include ms.date 02/27/2026)"
retrieved_utc: 2026-09-24
sources: [S580, S581, S582, S583, S545, S523]
status: complete
---

# Autopilot lifecycle: hybrid placeholder objects, motherboard replacement, deregistration

## Summary
- Hybrid join via Autopilot produces two Entra device objects by design: the pre-created Autopilot object and the hybrid-joined one.
- Motherboard replacement breaks hash matching: deregister, repair, capture a new 4K hash, reregister.
- Deregister order: delete from Intune, then delete from Autopilot; don't delete the Entra object by hand.

## Facts
- An Entra device object is pre-created when a device is registered in Autopilot; a hybrid Entra deployment creates another device object by design, resulting in duplicate entries. [DOC S583]
- Autopilot hybrid join naming supports only prefixes, not variables such as `%SERIAL%`. [DOC S583]
- The Intune Connector for Active Directory (ODJ connector) needs Windows Server 2016+ and .NET Framework 4.7.2+. [DOC S583]
- Large hardware changes such as a motherboard replacement don't match the registered hash; a new hash must be generated and uploaded. [DOC S580]
- Motherboard replacement procedure: deregister, replace, reimage with BIOS info and DPK reinjected, capture new 4K HH, reregister, reset. [DOC S582]
- BIOS fields Autopilot looks for include DiskSerialNumber, SmbiosSystemSerialNumber, SmbiosSystemManufacturer, SmbiosSystemProductName, SmbiosUuid, TPM EKPub, MacAddress, ProductKeyID. [DOC S582]
- A device should be deregistered whenever it permanently leaves the organization (repair or end of life). [DOC S581]
- Before deregistering from Autopilot, delete the device from Intune; then delete it in the Autopilot devices list (unassign user first if available). [DOC S581]
- Entra joined devices: no further steps after deregistration; avoid manually deleting the Entra device. Hybrid joined: delete the AD computer object to stop resync; avoid manually deleting the Entra device. [DOC S581]
- After deregistration, the Entra device object may be removed for devices not enrolled in MDM, but remains for devices that are or were MDM enrolled. [DOC S581]
- Graph deregistration call: `DELETE /deviceManagement/windowsAutopilotDeviceIdentities/{id}` with `DeviceManagementServiceConfig.ReadWrite.All`. [DOC S523]
- System-managed devices such as Autopilot shouldn't be deleted in Entra; once deleted they can't be reprovisioned. [DOC S545]

## Reference
| Step | Where | Source |
|---|---|---|
| 1 Delete managed device | Intune | S581 |
| 2 Delete Autopilot identity | Intune Autopilot devices / Graph | S581, S523 |
| 3 Hybrid only: delete AD computer | on-premises AD | S581 |

## Examples
- Retiring `PL-LT-00123`: note serial number in Intune, delete the managed device, then delete the Autopilot identity with that serial.
