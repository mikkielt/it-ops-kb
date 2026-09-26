---
topic: auth/role-source-options
priority: P1
applies_to: "Microsoft Graph v1.0 checkMemberGroups/getMemberGroups (docs current 2026-09-24)"
retrieved_utc: 2026-09-25
sources: [S1310, S1286, S1287, S524]
status: partial
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
- `getMemberGroups`: delegated and application permission required is `Directory.Read.All` (or `Directory.ReadWrite.All`). [DOC S1287]
- `/me/checkMemberGroups` needs a signed-in user context (delegated permission); application-only calls must instead target the object by id (`/users/{id}/checkMemberGroups`, `/devices/{id}/checkMemberGroups`). [DOC S1286]
- Neither API reference page states an explicit throttling limit specific to these two methods; general Graph throttling guidance applies but is not itself part of this agent's fetch set. [UNK]
- Permission naming and scope descriptions come from the Graph permissions reference, which lists Graph permissions per resource/verb but does not add call-specific caching guidance beyond the API pages themselves. [DOC S524]

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
- QA18 (least-privileged delegated/application permission for `checkMemberGroups`/`getMemberGroups`; limits; caching; CAE interplay): permissions answered [DOC S1286, S1287]; the 20-group-id limit of `checkMemberGroups` is on its page (see above); other limits and CAE interplay for these calls are [UNK] — not covered by the two API-reference pages fetched. Caching guidance: none stated on these pages; general advice would be to cache the boolean/group-id result client-side with a short TTL, but that is a recommendation, not a documented Microsoft caching policy for this call — flagged as unconfirmed rather than derived, since no source states a caching pattern for these endpoints specifically.
