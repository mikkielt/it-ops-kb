---
topic: auth/entra-intune-rbac
priority: P1
applies_to: "Microsoft Entra Connect Sync, Cloud Sync, PIM for Groups (docs current 2026-09-24)"
retrieved_utc: 2026-09-26
sources: [S1279, S1280, S1281, S1282, S1283, S-4teqh3ha, S1347]
status: complete
---

# Sync intervals and PIM for Groups latency

## Summary
- Entra Connect Sync's default sync cycle is 30 minutes; it cannot run more often than the tenant's `AllowedSyncCycleInterval` and still be supported. [DOC S1279]
- Cloud Sync runs user/group provisioning roughly every 10-20 minutes and password hash sync every 2-5 minutes; group writeback via Cloud Sync provisions to on-prem AD roughly every 20 minutes. [DOC S1280, S1281]
- PIM for Groups cannot manage groups synchronized from on-premises (or dynamic groups); reaching on-prem AD needs a cloud group provisioned to AD by Cloud Sync group writeback, adding that job's ~20-minute schedule on top of activation. [DER S-4teqh3ha, S1281: PIM-manageable groups are cloud groups, and Cloud Sync provisions cloud security groups to AD every 20 minutes]

## Facts
- Entra Connect Sync: default sync cycle is every 30 minutes; `AllowedSyncCycleInterval` is the shortest interval Entra ID will accept, and running faster is unsupported. [DOC S1279]
- Cloud Sync: user/group provisioning cycle runs approximately every 10-20 minutes (varies with queued change volume); password hash sync every 2-5 minutes. [DOC S1280]
- Group writeback with Cloud Sync: the group-provisioning job to on-prem AD runs on an approximately 20-minute schedule. [DOC S1281]
- PIM for Groups gives just-in-time membership or ownership of a Microsoft Entra group; role settings (activation maximum duration of 1-24 hours, MFA or Conditional Access authentication context, justification, ticket, approval) are defined per role (member/owner) per group. [DOC S1282, S1283]
- Dynamic groups and groups synchronized from an on-premises environment can't be managed in PIM for Groups. [DOC S-4teqh3ha]
- Reaching on-prem AD from a PIM-for-Groups activation requires that the PIM-managed cloud group be provisioned to AD by Cloud Sync group writeback; the change then follows that provisioning job's 20-minute schedule, after PIM's own within-seconds membership change. [DER S1282,S-4teqh3ha,S1281: activation adds membership within seconds; only cloud groups are PIM-manageable; writeback runs every 20 minutes]
- On activation PIM adds the user as member or owner within seconds, and on deactivation removes them within seconds; applications that cached the user's membership may not reflect the change at once, and signing out and back in can help for some applications. [DOC S1282]
- A new membership reaches an app's access token only at the next token issuance: an already-issued, non-CAE token keeps its old groups, and group changes are not on CAE's critical-event list, so no early refresh is forced (see `auth/revocation.md`). [DER S1347, S-4teqh3ha: PIM changes membership within seconds + group change absent from CAE critical events]

## Reference
| Sync mechanism | Interval | Reaches on-prem AD | Source |
|---|---|---|---|
| Entra Connect Sync (delta) | 30 min default (floor: `AllowedSyncCycleInterval`) | AD is the source | S1279 |
| Cloud Sync (user/group provisioning) | ~10-20 min | only with group writeback enabled | S1280, S1281 |
| Cloud Sync (password hash sync) | 2-5 min | n/a | S1280 |
| Group writeback (Cloud Sync) | ~20 min | yes, into AD | S1281 |
| PIM for Groups activation → group membership | within seconds; apps that cached membership may lag (sign out/in can help) | no (cloud groups only, unless writeback) | S1282, S-4teqh3ha |

## Examples
- Engineer `jan.kowalski` activates PIM membership in `SG-ENGINEER` (cloud group, writeback-enabled): visible to a fresh Graph token immediately; visible in AD only after the next ~20-minute writeback cycle; a workstation client process holding a cached Kerberos ticket for AdminService/SQL will not see it until that ticket is renewed (see `auth/kerberos.md`).

See also `intune/assignment-filters-and-rbac.md`: the Intune-RBAC side of PIM elevation this article's
timing covers — Entra PIM on the Intune Administrator role applies in ~10 seconds, PIM for Groups backing
an Intune RBAC role assignment in ~15 minutes.

See also `entra/pim-and-governance.md`: per-role PIM activation policy (max duration, MFA/Conditional Access/approval
requirements), the Graph `unifiedRoleEligibilityScheduleRequest`/`unifiedRoleAssignmentScheduleRequest` APIs, PIM
security alerts, and Entitlement Management/access reviews licensing — this article's sync-interval and PIM-for-Groups
latency facts are the mechanics that article assumes rather than repeats.

## Open items
- QA9 (PIM for Groups activation latency in tokens/`checkMemberGroups`, reach to on-prem AD): answered above — token-side is next-acquisition, not real-time push; AD-side needs writeback and its own ~20 min cycle.
- QA8 (Entra Connect Sync/Cloud Sync intervals, group writeback status in 2026): answered above.
