---
topic: graph/csdl-windowsAutopilotDeviceIdentity
priority: P1
applies_to: "Microsoft Graph v1.0 and beta, msgraph-metadata commit b8cbef92f695"
retrieved_utc: 2026-09-24
sources: [S500, S501, S508, S509]
status: complete
files: [graph/csdl/windowsAutopilotDeviceIdentity.v1.0.xml, graph/csdl/windowsAutopilotDeviceIdentity.beta.xml]
---

# Graph `windowsAutopilotDeviceIdentity`: CSDL excerpt and property table

## Summary
- CSDL excerpts: `csdl/windowsAutopilotDeviceIdentity.v1.0.xml`, `.beta.xml`. MIT.
- Property table: `csdl-windowsAutopilotDeviceIdentity.properties.csv`.
- v1.0: 17 properties, no navigation. Beta: 27 properties, 2 navigation.
- Neither CSDL nor the resource pages state `$filter` or `$select`-only support for any property.

## Facts
- `id` is described only as "The GUID for the object". [DOC S508]
- v1.0 properties include `serialNumber`, `groupTag`, `purchaseOrderIdentifier`, `productKey`, `manufacturer`, `model`, `enrollmentState`, `lastContactedDateTime`, `azureActiveDirectoryDeviceId`, `managedDeviceId`, `userPrincipalName`, `displayName`. [DOC S508]
- `azureActiveDirectoryDeviceId` is marked "AAD Device ID - to be deprecated"; beta adds `azureAdDeviceId` ("AAD Device ID"). [DOC S508,S509]
- `enrollmentState` values (v1.0): `unknown`, `enrolled`, `pendingReset`, `failed`, `notContacted`; beta adds `blocked`. [DOC S508,S509]
- Beta adds `deploymentProfileAssignmentStatus`, `deploymentProfileAssignedDateTime`, `remediationState`, `userlessEnrollmentStatus`, Surface Hub fields. [DOC S509]
- No `delta` function is bound to this type in either CSDL version. [DOC S502,S503]
- No property on this type is documented as the ZTDID. [UNK]

## Reference
- `csdl-windowsAutopilotDeviceIdentity.properties.csv` (46 rows).

## Examples
- `GET /v1.0/deviceManagement/windowsAutopilotDeviceIdentities/{id}`
