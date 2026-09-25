---
topic: graph/csdl-device
priority: P1
applies_to: "Microsoft Graph v1.0 and beta, msgraph-metadata commit b8cbef92f695"
retrieved_utc: 2026-09-24
sources: [S500, S501, S504, S505, S530]
status: complete
files: [graph/csdl/device.v1.0.xml, graph/csdl/device.beta.xml]
---

# Graph `device` (Entra device object): CSDL excerpt and property table

## Summary
- CSDL excerpts: `csdl/device.v1.0.xml`, `csdl/device.beta.xml` (EntityType `device`, base types `directoryObject` and `entity`, referenced complex/enum types, and Annotations for those types and the `devices` entity set). MIT, attribution header inside each file.
- Property table (both versions): `csdl-device.properties.csv`. Columns: version, property, kind, type, declared_on, nullable, filterable, filter_ops, select_only, evidence (csdl/docs), note.
- v1.0: 32 structural properties, 5 navigation properties; 17 carry a `$filter` note. Beta: 40 properties, 8 navigation.
- `$select`-only in v1.0: `isManagementRestricted`, `onPremisesSecurityIdentifier`.

## Facts
- `device` derives from `directoryObject` and is an open type (`OpenType="true"`). [DOC S500]
- `deviceId` is "set by Azure Device Registration Service at the time of registration", is an alternate key, and supports `$filter` (`eq`, `ne`, `not`, `startsWith`). [DOC S500]
- `id` is the directory object key; the resource page lists `$filter` (`eq`, `ne`, `not`, `in`) for it (not stated in the CSDL description). [DOC S504]
- `trustType` values: `Workplace` (personal/registered), `AzureAd` (cloud-only joined), `ServerAd` (on-premises domain joined devices joined to Entra ID); supports `$filter` (`eq`, `ne`, `not`, `in`). [DOC S504]
- `approximateLastSignInDateTime` is read-only and supports `$filter` (`eq`, `ne`, `not`, `ge`, `le`, `eq` on null) and `$orderby`. [DOC S504]
- `onPremisesSecurityIdentifier` "Requires `$select` to retrieve" and supports `$filter` (`eq`). [DOC S504]
- `physicalIds` is "For internal use only", not nullable, and supports `$filter` (`eq`, `not`, `ge`, `le`, `startsWith`, `/$count eq 0`, `/$count ne 0`). [DOC S504]
- `onPremisesSyncEnabled`: `true` when synced from on-premises, `false` when no longer synced, `null` when never synced. [DOC S504]
- Specific `$filter` and `$search` usages need `ConsistencyLevel: eventual` plus `$count` (advanced query capabilities). [DOC S504,S530]
- The CSDL marks `microsoft.graph.device` with `Org.OData.Capabilities.V1.ChangeTracking Supported=true` (delta). [DOC S500]
- The v1.0 resource page lists `extensionAttributes` (onPremisesExtensionAttributes), but the v1.0 CSDL `device` EntityType does not declare it; beta CSDL does. [DER S500,S504: property absent from v1.0 EntityType, present in docs table; see conflicts]
- Beta adds, among others, `alternativeNames`, `domainName`, `hostnames`, `kind`, `name`, `platform`, `status`, navigation `usageRights`, `commands`, `deviceTemplate`. [DOC S501]

## Reference
- `csdl-device.properties.csv` (85 rows). "filterable = not stated" means neither the CSDL nor the resource page mentions `$filter` for that property; it does not mean filtering fails.
- Excerpt hashes: see `_artifacts.csv`.

## Examples
- `GET /v1.0/devices?$filter=deviceId eq '00000000-0000-0000-0000-000000000000'&$select=id,deviceId,displayName,trustType`
- `GET /v1.0/devices?$filter=displayName eq 'PL-LT-00123'`
