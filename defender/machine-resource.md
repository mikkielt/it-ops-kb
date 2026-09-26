---
topic: defender/machine-resource
priority: P1
applies_to: "Microsoft Defender for Endpoint API v1.0 (api.security.microsoft.com), docs ms.date 2025-12-11 / 2026-06-28"
retrieved_utc: 2026-09-26
sources: [S620, S621, S622, S627, S628, S629, S630, S631]
status: partial
files: [defender/machine-properties.csv]
---
# Defender for Endpoint Machine resource

## Summary
The MDE `Machine` entity (`GET /api/machines`, `/api/machines/{id}`) has 21 documented properties; `id` is the MDE
device id (40-hex string). `aadDeviceId` is documented only as "Microsoft Entra Device ID (when machine is Microsoft Entra
joined)" — Microsoft does not say whether it is filled for **hybrid-joined** devices (Q11: UNK). Advanced hunting
`DeviceInfo` has `AadDeviceId` and `JoinType`. Property table: `machine-properties.csv`.

## Facts
- `aadDeviceId`: Nullable Guid, "Microsoft Entra Device ID (when machine is Microsoft Entra joined)". [DOC S620]
- No official page found stating whether `aadDeviceId` is populated for Microsoft Entra hybrid joined devices. [UNK]
- Response examples include `isAadJoined` (boolean) which is not in the property table. [DOC S621,S622]
- `lastSeen` is the time of the last full device report (typically every 24 h) and does not correspond to the portal's last seen. [DOC S620]
- `GET /api/machines` supports OData `$filter` on computerDnsName, id, version, deviceValue, aadDeviceId, machineTags, lastSeen, exposureLevel, onboardingStatus, lastIpAddress, healthStatus, osPlatform, riskScore, rbacGroupId; `$top` max 10,000; `$skip`. [DOC S621]
- The OData samples page lists a shorter filterable set for Machine (ComputerDnsName, LastSeen, exposureLevel, HealthStatus, OsPlatform, onboardingStatus, RiskScore, RbacGroupId). [DOC S628]
- Returned devices are limited to the configured retention period; if there are no recent machines the list call returns 404 Not Found. [DOC S621]
- `GET /api/machines/{id}` accepts device ID or computer name; 404 when not found. [DOC S622]
- Delegated calls return only devices the user can access by device-group settings. [DOC S621]
- Advanced hunting `DeviceInfo` columns include DeviceId, DeviceName, IsAzureADJoined, JoinType ("The device's Microsoft Entra ID join type"), AadDeviceId, OnboardingStatus, MergedDeviceIds, MergedToDeviceId, HardwareUuid. [DOC S627]
- Graph `security.deviceEvidence` has `azureAdDeviceId` ("assigned ... when device is Microsoft Entra joined") and `mdeDeviceId`. [DOC S630]
- Community report: an MDE API call returned `"isAadJoined": false, "aadDeviceId": null` while the portal showed values; Microsoft support attributed it to macOS not being a full Entra join type. [COMMUNITY S631]
- The `JoinType` value set (e.g. whether "Hybrid Azure AD Join" is a value) is not documented on S627. [UNK]

## Reference
See `machine-properties.csv` (property, type, description_summary, filterable_get_machines, source_id).
See `defender/advanced-hunting.md` for the `DeviceInfo` advanced hunting table (join key for `AadDeviceId`/`JoinType`) and its quotas.
See `defender/mde-onboarding.md` for onboarding/offboarding methods, streamlined vs. standard connectivity, device tagging, and security settings management that produce this resource's `onboardingStatus` and tag fields.

## Examples
`GET https://api.security.microsoft.com/api/machines?$filter=computerDnsName eq 'pl-lt-00123.corp.example.com'`
`GET https://api.security.microsoft.com/api/machines?$filter=aadDeviceId eq 00000000-0000-0000-0000-000000000000` (filter syntax for Guid values not shown in the docs).
