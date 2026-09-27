---
topic: auth/group-claims
priority: P1
applies_to: "Microsoft Entra ID token claims (docs current 2026-09-24)"
retrieved_utc: 2026-09-26
sources: [S1310, S1284, S1285]
status: partial
---

# Group claims, overage, and app roles

## Summary
- Entra tokens cap group membership lists at 200 (JWT) / 150 (SAML); above that, Entra emits an overage indicator instead of a partial list and the app must call Graph. [DOC S1284]
- Restricting the group claim to "groups assigned to the application" avoids overage but **excludes nested group members** from that claim. [DOC S1285]
- Microsoft recommends basing in-app authorization on app roles rather than groups for a new (or reconfigurable) app when nested groups aren't needed, because app roles limit what goes into the token, are more secure, and separate user assignment from app configuration. [DOC S1284]

## Facts
- Group-based assignment to an application (and so app roles assigned to a group) reaches only direct members: it does not cascade to nested groups, and it requires Entra ID P1 or P2. [DOC S1310]
- The group-count limits (200 JWT / 150 SAML) count nested group memberships, i.e. transitive membership is what is being counted against the cap. [DOC S1284]
- On overage the token has no `groups` claim; the app checks for a `hasgroups` claim (implicit flow) or a `_claim_names` claim with a `groups` member, and if either is present gets the membership from Microsoft Graph (transitive memberOf) instead; it should rely on the overage claim's presence, not its value. [DOC S1285]
- Group claims include nested groups except with the "groups assigned to the application" restriction, which emits only groups the user is a direct member of — an app relying on nested-group membership must not use the assigned-groups restriction. [DOC S1284,S1285]
- App roles instead of groups: Microsoft's stated rationale is (a) less information in the token, (b) more secure, (c) separates user assignment from the app's own configuration. [DOC S1284]

## Reference
| Claim configuration | Includes nested groups | Overage-prone | Source |
|---|---|---|---|
| `groups`: all security groups | yes | yes (200/150 cap) | S1284 |
| `groups`: groups assigned to the application | no | no (bounded by assignment) | S1285 |
| App roles assigned to groups (`roles` claim) | not confirmed either way | no | S1285 |

## Examples
- `SG-Engineer` assigned as an app role on a client app: role name `engineer` appears in `roles`, independent of how deep the group nesting is — but this depth-independence itself is [UNK], not confirmed.

## Open items
- QA7 (overage thresholds, recommended pattern, do nested groups count for app-role assignments): thresholds and recommended pattern (app roles) are answered [DOC S1284, S1285]; nested groups in app-role assignment: answered no [DOC S1310].
