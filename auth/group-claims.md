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
- App roles assigned to groups are Microsoft's recommended pattern over raw `groups` claims for authorization, precisely because they keep the token small and separate assignment from app config. [DOC S1285]

## Facts
- Group-based assignment to an application (and so app roles assigned to a group) reaches only direct members: it does not cascade to nested groups, and it requires Entra ID P1 or P2. [DOC S1310]
- The group-count limits (200 JWT / 150 SAML) count nested group memberships, i.e. transitive membership is what is being counted against the cap. [DOC S1284]
- On overage, the token carries an overage claim (`_claim_names`/`hasgroups`-style indirection) telling the app to call Graph (`getMemberGroups`/`memberOf`) instead of reading `groups` from the token. [DOC S1284]
- Group claims configured as "all groups" include nested groups; group claims configured as "groups assigned to the application" do **not** include nested groups — an app relying on nested-group membership must not use the assigned-groups restriction. [DOC S1285]
- App roles assigned to groups: Microsoft's stated rationale is (a) smaller token, (b) more secure, (c) separates the user/group assignment decision from the app's own configuration. [DOC S1285]

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
