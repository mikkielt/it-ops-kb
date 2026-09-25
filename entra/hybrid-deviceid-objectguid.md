---
topic: entra/hybrid-deviceid-objectguid
priority: P1
applies_to: "Microsoft Entra Connect Sync, Entra Cloud Sync device sync (preview), hybrid join"
retrieved_utc: 2026-09-25
sources: [S504, S544, S548, S549, S550, S551, S552]
status: partial
---

# Hybrid join: Entra `deviceId` and AD `objectGUID`

## Summary
- Two Microsoft Entra docs map the AD computer `objectGUID` to the Entra device `deviceID`/`DeviceId` attribute in sync.
- No page found states in words that the Graph `device.deviceId` of a hybrid-joined device *equals* the AD `objectGUID`.
- The hybrid-join walk-through says DRS "creates a device ID" at registration, which reads differently (see conflicts).
- The hybrid-join self-signed certificate in `userCertificate` has subject `CN={objectGUID}`.

## Facts
- Entra Connect "Windows 10" attribute table: `objectGUID` — "Also called deviceID"; `objectSID` — "Also called onPremisesSecurityIdentifier"; `userCertificate` is synced; a Windows 10 domain-joined computer is identified by a populated `userCertificate`. [DOC S549]
- Entra Cloud Sync device sync (preview) mapping: Entra `DeviceId` <- AD `objectGUID` (Direct); `SourceAnchor` <- `objectGUID`; `OnPremiseSecurityIdentifier` <- `objectSid`; `DeviceTrustType` always `ServerAd`. [DOC S550]
- Managed hybrid join: Entra Connect sends `userCertificate`, object GUID and computer SID to Azure DRS, which uses them to create the device object; later DRS "creates a device ID" and updates the device object. [DOC S548]
- Federated hybrid join: the enterprise DRS token carries claims for object GUID, computer SID and domain-joined state; AD FS must issue the `onpremobjectguid` claim with the computer account's `objectGUID`. [DOC S548,S551]
- Hybrid-join certificates in `userCertificate` are identified by a subject name matching `CN={ObjectGUID}`. [DOC S552]
- Graph describes `device.deviceId` as set by Azure Device Registration Service at registration, without mentioning `objectGUID`. [DOC S504]
- dsregcmd `DeviceId` is "The unique ID of the device in the Microsoft Entra tenant". [DOC S544]
- For devices synced by Entra Connect or Cloud Sync, the Entra device ID attribute is populated from `objectGUID`. [DER S549,S550: both sync references map objectGUID to the device ID attribute]
- An explicit statement that Graph `device.deviceId` equals AD `objectGUID` for every hybrid-joined device (including the AD FS-only path without sync) was not found. [UNK]
- Byte-order or string-format rules for comparing the 16-byte `objectGUID` with the Graph `deviceId` string are not documented in the sources read. [UNK]

## Reference
| Doc | Statement | Source |
|---|---|---|
| Entra Connect synchronized attributes | objectGUID "Also called deviceID" | S549 |
| Cloud Sync device sync (preview) | DeviceId <- objectGUID, Direct | S550 |
| How device registration works | DRS "creates a device ID" | S548 |
| Graph device resource | deviceId set by DRS at registration | S504 |

## Examples
- For `PL-LT-00123` in `corp.example.com`: compare `Get-ADComputer PL-LT-00123 -Properties objectGUID` with `GET /v1.0/devices?$filter=deviceId eq '{objectGUID}'`; a match is expected only from the sync mapping above, not from an explicit equality statement.
