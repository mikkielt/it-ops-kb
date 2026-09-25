---
topic: graph/throttling
priority: P1
applies_to: "Microsoft Graph (throttling-limits ms.date 01/14/2025)"
retrieved_utc: 2026-09-24
sources: [S525, S526, S527, S528, S529]
status: partial
---

# Graph throttling limits: directory (devices) and Intune

## Summary
- Global: 130,000 requests per 10 seconds per app across all tenants.
- Directory (`device` included): token bucket in ResourceUnits; app+tenant 3,500 / 5,000 / 8,000 RU per 10 s for S / M / L tenants.
- Device writes: 3,000 per 2 min 30 s per app per tenant, 25 per 10 s per user per tenant.
- Intune devices (`managedDevice`): 2,000 requests / 20 s per app per tenant, 4,000 / 20 s per tenant (any request type).
- Autopilot identities are not listed in any Intune throttling group. [UNK]

## Facts
- Microsoft states the specific limits are subject to change. [DOC S525]
- Global limit: 130,000 requests per 10 seconds per app across all tenants. [DOC S525]
- Identity and access limits apply to `device` among other directory resources: app+tenant pair S 3,500, M 5,000, L 8,000 ResourceUnits per 10 s (S under 50 users, M 50-500, L above 500); write quota 3,000 requests per 2 min 30 s. [DOC S526]
- Per application: 150,000 RU per 20 s and 35,000 writes per 5 min; per tenant: 18,000 writes per 5 min. [DOC S526]
- Base cost of an unlisted identity GET is 1 RU; `$select` lowers cost by 1, `$expand` raises it by 1, `$top` under 20 lowers it by 1; minimum cost 1. [DOC S526]
- Header `x-ms-throttle-priority` (low/normal/high) changes throttling order but not limits; `x-ms-resource-unit` and `x-ms-throttle-limit-percentage` (from 0.8) are returned on responses. [DOC S526]
- Device write quota (POST, PATCH, DELETE on `device`): 3,000 per 2 min 30 s per app per tenant; 25 per 10 s per user per tenant. [DOC S527]
- Intune devices service (includes `managedDevice`, `windowsManagedDevice`): writes 200 / 20 s per app per tenant and 400 / 20 s per tenant; any request 2,000 / 20 s per app per tenant and 4,000 / 20 s per tenant. [DOC S528]
- Throttled requests return 429 with `Retry-After`; wait that many seconds and retry; with no `Retry-After`, use exponential backoff. [DOC S529]
- Requests in a JSON batch are evaluated individually; a throttled item fails with 429 while the batch returns 200. [DOC S529]
- `windowsAutopilotDeviceIdentity` does not appear in any Intune throttling include. [UNK]

## Reference
| Scope | Resource | Limit | Source |
|---|---|---|---|
| app, all tenants | all Graph | 130,000 req / 10 s | S525 |
| app+tenant | directory incl. device | 3,500/5,000/8,000 RU / 10 s | S526 |
| app+tenant | device writes | 3,000 / 150 s | S527 |
| user+tenant | device writes | 25 / 10 s | S527 |
| app+tenant | Intune devices, any | 2,000 / 20 s | S528 |
| tenant | Intune devices, any | 4,000 / 20 s | S528 |

## Examples
- `GET /devices?$select=id,deviceId` is not in the cost table, so base cost 1; `$select` would lower it but the floor is 1, so 1 RU per page. (Derived from S526.)
