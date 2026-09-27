---
topic: auth/role-source-options
priority: P1
applies_to: "Microsoft Graph v1.0 checkMemberGroups/getMemberGroups (docs current 2026-09-24)"
retrieved_utc: 2026-09-27
sources: [S1310, S1286, S1287, S524, S526, S1355, S-yc5geeul]
status: complete
---

# Role source: checkMemberGroups / getMemberGroups least privilege

Facts only, per the design's role-source-options table. Windows logon token groups, Entra token `groups`
claim, Entra app roles, and ConfigMgr RBAC-by-403 are covered by other kb areas / agents; this file
covers only the two Graph calls this agent was assigned.

## Summary
- Least privilege depends on the target. `checkMemberGroups` for the signed-in user (`/me`): delegated `User.Read`; app-only is not supported for `/me`. For other users: `User.ReadBasic.All` + `GroupMember.Read.All` (delegated or application). For any directory object: `Directory.Read.All`. [DOC S1286]
- `getMemberGroups` for a user: `User.ReadBasic.All` + `GroupMember.Read.All` (delegated or application); for any directory object `Directory.Read.All`. [DOC S1287]
- `checkMemberGroups` accepts at most 20 group ids per request, and checks transitive membership. [DOC S1286]
- `/me/checkMemberGroups` requires a signed-in user (delegated only); application permissions are not usable against `/me`. [DOC S1286]

## Facts
- Group-based assignment to an application (and so app roles assigned to a group) reaches only direct members: it does not cascade to nested groups, and it requires Entra ID P1 or P2. [DOC S1310]
- `checkMemberGroups` on a device object: see the per-target tables on the API page; `Directory.Read.All` covers every object type. [DOC S1286]
- An engineer role check by a workstation `client` (`/me/checkMemberGroups` against a small set of role-group ids) needs only delegated `User.Read`. [DER S1286: signed-in user table, ≤20 ids]
- `getMemberGroups` on `/directoryObjects/{id}` (any object type) needs `Directory.Read.All` (delegated or application); the page has lower-privileged per-type tables for users, groups, service principals and devices. It is transitive and returns at most 11,000 group ids (beyond that a 400 `Directory_ResultSizeLimitExceeded`; use transitive memberOf instead). [DOC S1287]
- `/me/checkMemberGroups` needs a signed-in user context (delegated permission); application-only calls must instead target the object by id (`/users/{id}/checkMemberGroups`, `/devices/{id}/checkMemberGroups`). [DOC S1286]
- Throttling: both calls fall under the Graph identity-and-access limits (a token bucket of resource units per application+tenant pair, 3,500 / 5,000 / 8,000 per 10 seconds for tenants under 50 / 50-500 / over 500 users); `me/checkMemberGroups` costs 4 resource units and `me/getMemberGroups` 2, and the same costs apply to `users/{id}/...` paths. [DOC S526]
- CAE: these are ordinary Graph calls, so Graph sends claims challenges for them only to a client that declares the `cp1` capability. [DER S1355, S-yc5geeul: Graph's CAE behaviour applied to these two calls]
- Permission naming and scope descriptions come from the Graph permissions reference, which lists each Graph permission with its application and delegated identifiers, display text, description and admin-consent requirement; it gives no caching guidance. [DOC S524]

## Reference
| Method | Target | Delegated least privilege | Application least privilege | Source |
|---|---|---|---|---|
| `checkMemberGroups` (signed-in user) | `/me` | `User.Read` | not supported | S1286 |
| `checkMemberGroups` / `getMemberGroups` (other user) | user | `User.ReadBasic.All` + `GroupMember.Read.All` | same | S1286, S1287 |
| `checkMemberGroups` (any object) | directory object | `Directory.Read.All` | `Directory.Read.All` | S1286 |
| `getMemberGroups` | any directory object | `Directory.Read.All` | `Directory.Read.All` | S1287 |

## Examples
- Checking whether device `PL-LT-00123`'s Entra device object is a transitive member of collection-mirroring group `SG-BASELINE-TEST`: `POST /devices/{id}/checkMemberGroups` with `Directory.Read.All` (the object-generic least privilege; app-only, `site` instance).

## Open items
- QA18 (least-privileged delegated/application permission for `checkMemberGroups`/`getMemberGroups`; limits; caching; CAE interplay): permissions answered [DOC S1286, S1287]; the 20-group-id limit of `checkMemberGroups` and the 11,000-group-id result limit of `getMemberGroups` are on their pages; throttling costs and CAE interplay are answered above [DOC S526; DER S1355]. Caching guidance: no Microsoft page states one for these calls (API pages S1286/S1287 and the throttling include S526 checked 2026-09-27); a short client-side cache is a local design choice, not documented policy.
