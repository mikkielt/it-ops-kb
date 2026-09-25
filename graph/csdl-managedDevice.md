---
topic: graph/csdl-managedDevice
priority: P1
applies_to: "Microsoft Graph v1.0 and beta, msgraph-metadata commit b8cbef92f695"
retrieved_utc: 2026-09-24
sources: [S500, S501, S506, S507]
status: complete
files: [graph/csdl/managedDevice.v1.0.xml, graph/csdl/managedDevice.beta.xml]
---

# Graph `managedDevice` (Intune): CSDL excerpt and property table

## Summary
- CSDL excerpts: `csdl/managedDevice.v1.0.xml`, `csdl/managedDevice.beta.xml` (EntityType, base `entity`, transitive complex/enum types, Annotations). MIT.
- Property table: `csdl-managedDevice.properties.csv` (both versions).
- v1.0: 56 properties, 6 navigation; 20 carry a `$filter` note. Beta: 84 properties, 11 navigation; 22 with a `$filter` note.
- The Intune `$filter` notes live mostly in *out-of-line* `Annotations` of the CSDL, not in the inline property descriptions or the resource page.

## Facts
- The entity set description says: limited `$filter` support; only properties whose descriptions mention `$filter` may be used, and combinations "must use 'and', not 'or'". [DOC S500]
- `azureADDeviceId` (Entra device id): out-of-line CSDL annotation says "Supports $filter operator 'eq', not combine with count"; the inline description and the v1.0 resource page do not mention `$filter`. [DOC S500,S506]
- `serialNumber`, `manufacturer`, `operatingSystem`, `imei`, `complianceState`, `managementAgent`: `$filter` `'eq' and 'or'`. [DOC S500]
- `deviceName`, `model`: `'eq' and 'contains'`; `userPrincipalName`: `'eq' and 'ne'`; `enrolledDateTime`, `lastSyncDateTime`: `'lt' and 'gt'`. [DOC S500]
- `$select`-only / non-default properties in v1.0 (returned only by a GET on one device with `$select`): `activationLockBypassCode`, `ethernetMacAddress`, `iccid`, `notes`, `physicalMemoryInBytes`, `remoteAssistanceSessionUrl`, `udid`. [DOC S506]
- Beta adds `$select`-only `hardwareInformation`, `chromeOSDeviceInfo`, `windowsActiveMalwareCount`, `windowsRemediatedMalwareCount`. [DOC S501,S507]
- No `delta` function is bound to `managedDevice` in v1.0 or beta CSDL, and no ChangeTracking annotation targets it. [DOC S502,S503]

## Reference
- `csdl-managedDevice.properties.csv` (157 rows). Column `note` flags every property where CSDL and resource page disagree on `$filter`.

## Examples
- `GET /v1.0/deviceManagement/managedDevices?$filter=serialNumber eq 'PL0012300'&$select=id,deviceName,azureADDeviceId,serialNumber`
- `GET /v1.0/deviceManagement/managedDevices/{id}?$select=ethernetMacAddress`
