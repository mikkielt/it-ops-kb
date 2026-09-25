---
topic: auth/entra-intune-rbac
priority: P1
applies_to: "Microsoft Entra Connect Sync, Cloud Sync, PIM for Groups (docs current 2026-09-24)"
retrieved_utc: 2026-09-25
sources: [S1279, S1280, S1281, S1282, S1283]
status: partial
---

# Sync intervals and PIM for Groups latency

## Summary
- Entra Connect Sync's default and minimum supported cycle is 30 minutes; it cannot be shortened below that and still be supported. [DOC S1279]
- Cloud Sync runs user/group provisioning roughly every 10-20 minutes and password hash sync every 2-5 minutes; group writeback via Cloud Sync provisions to on-prem AD roughly every 20 minutes. [DOC S1280, S1281]
- PIM for Groups only manages cloud-only Entra groups directly; reaching an on-prem AD group needs Cloud Sync group writeback, adding that provisioning job's own latency on top of activation. [DOC S1282, S1283]

## Facts
- Entra Connect Sync: default sync cycle is every 30 minutes; `AllowedSyncCycleInterval` is the shortest interval Entra ID will accept, and running faster is unsupported. [DOC S1279]
- Cloud Sync: user/group provisioning cycle runs approximately every 10-20 minutes (varies with queued change volume); password hash sync every 2-5 minutes. [DOC S1280]
- Group writeback with Cloud Sync: the group-provisioning job to on-prem AD runs on an approximately 20-minute schedule. [DOC S1281]
- PIM for Groups activates membership/ownership of a cloud-only Entra ID group; on-prem AD groups are not directly PIM-managed. [DOC S1282][DOC S1283]
- Reaching on-prem AD from a PIM-for-Groups activation requires that the PIM-managed group be writeback-enabled via Cloud Sync; propagation to AD then follows the group-writeback job's own cycle (~20 min), stacked after PIM's own token/claim propagation. [DER S1282,S1283,S1281]
- A newly-issued access token already carries group membership as of issuance; PIM activation/deactivation does not retroactively change a token already in a client's cache — the change is only visible once the client acquires (or is forced to acquire) a new token. [DOC S1282] (consistent with general Entra token-caching behaviour)

## Reference
| Sync mechanism | Interval | Reaches on-prem AD | Source |
|---|---|---|---|
| Entra Connect Sync (delta) | 30 min default/min | yes (native, AD is the source) | S1279 |
| Cloud Sync (user/group provisioning) | ~10-20 min | only with group writeback enabled | S1280, S1281 |
| Cloud Sync (password hash sync) | 2-5 min | n/a | S1280 |
| Group writeback (Cloud Sync) | ~20 min | yes, into AD | S1281 |
| PIM for Groups activation → token visibility | immediate at next token acquisition; no forced refresh of existing tokens | no (cloud group only, unless writeback) | S1282, S1283 |

## Examples
- Engineer `jan.kowalski` activates PIM membership in `SG-ENGINEER` (cloud group, writeback-enabled): visible to a fresh Graph token immediately; visible in AD only after the next ~20-minute writeback cycle; a workstation client process holding a cached Kerberos ticket for AdminService/SQL will not see it until that ticket is renewed (see `auth/kerberos.md`).

## Open items
- QA9 (PIM for Groups activation latency in tokens/`checkMemberGroups`, reach to on-prem AD): answered above — token-side is next-acquisition, not real-time push; AD-side needs writeback and its own ~20 min cycle.
- QA8 (Entra Connect Sync/Cloud Sync intervals, group writeback status in 2026): answered above.
