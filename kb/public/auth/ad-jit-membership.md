---
topic: auth/ad-jit-membership
priority: P1
applies_to: "AD DS PAM optional feature (Windows Server 2016 forest functional level+)"
retrieved_utc: 2026-09-26
sources: [S1211, S1219, S-bwyxgvxj, S-rparnwbm]
status: complete
---

# AD temporary (TTL) group membership — PAM optional feature

## Summary
- Windows Server 2016 AD DS supports time-limited group membership (expiring links with a TTL), set with `Add-ADGroupMember -MemberTimeToLive`; an expired membership is evaluated in real time, so it ends on every domain controller without an external process. [DOC S1211, S1219, S-bwyxgvxj]
- PAM is a Windows Server 2016 forest functional level feature. [DOC S-rparnwbm]
- Whether enabling the PAM optional feature is irreversible (schema extension) is not in the Microsoft docs read. [UNK: not in S1211 as re-read 2026-09-27]
- Not evaluated for a design that avoids temporary collections/boundary groups, but relevant if a future JIT-elevation flow through a broker is considered.

## Facts
- `Add-ADGroupMember -MemberTimeToLive <TimeSpan>` sets a time to live for the new group members. [DOC S-bwyxgvxj]
- With Windows Server 2016 or later the membership is tied to a time limit in AD; an expired link is evaluated in real time by the Security Accounts Manager, so removal takes effect at once on any DC, while adding a member still needs replication. [DOC S1211]
- Privileged access management (PAM) using MIM is listed among the Windows Server 2016 forest functional level features. [DOC S-rparnwbm]
- Enabling the "Privileged Access Management Feature" optional feature being irreversible (extends the schema, cannot be disabled). [UNK: not in S1211 as re-read 2026-09-27]
- Effect on Kerberos ticket lifetime, now confirmed: Windows Server 2016's "expiring links" feature is what implements PAM's TTL group membership, and its TTL value is **propagated directly into the issued Kerberos ticket's lifetime** — the KDC caps the TGT's lifetime to the remaining TTL of the shortest-lived time-bound group the user belongs to. If a user is in two time-bound groups with different remaining TTLs, the TGT lifetime is capped to the *lower* of the two. This means a TTL membership does not "silently" expire while an old, longer-lived ticket remains valid: the ticket itself is only ever issued for at most the TTL that was current at logon. [DOC S1219]
- This still leaves one edge case unconfirmed: what happens if the TTL group is removed (e.g. by an administrator) *before* its natural expiry, mid-ticket — whether the already-issued ticket (capped to the original, now-stale TTL) remains valid until its own expiry. [UNK — not stated in S1219; treat as a lab check]
- MIM PAM (the higher-level Microsoft Identity Manager Privileged Access Management workflow product) sits on top of this AD feature; status of MIM PAM itself (support lifecycle, whether Microsoft still actively develops it) was not confirmed this session. [UNK]

## Reference
| Aspect | Fact | Tag |
|---|---|---|
| Requirement | Forest functional level 2016+ | DOC S-rparnwbm |
| Enablement | Irreversible, forest-wide | UNK |
| Effect on Kerberos ticket lifetime | TGT capped to the remaining TTL of the shortest-lived time-bound group at logon | DOC |
| Effect of mid-ticket TTL group removal by an admin | Unconfirmed | UNK |
| MIM PAM product status in 2026 | Unconfirmed | UNK |

## Examples
- Not used in the reference design here; recorded for a possible future JIT elevation flow only.

Verification: in an isolated AD forest with PAM enabled, add a test principal to a TTL group, then have an administrator remove the membership before the TTL expires, and check whether an already-issued TGT (capped to the original TTL) is honoured until its own expiry or invalidated immediately → proves the mid-ticket revocation edge case.
