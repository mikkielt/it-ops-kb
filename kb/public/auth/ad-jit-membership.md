---
topic: auth/ad-jit-membership
priority: P1
applies_to: "AD DS PAM optional feature (Windows Server 2016 forest functional level+)"
retrieved_utc: 2026-09-28
sources: [S1211, S1219, S-bwyxgvxj, S-rparnwbm, S-y4ohln4f, S-st444pl7, S-a3advgfv, S-ffrzumip, S-v5wjmc3h]
status: complete
---

# AD temporary (TTL) group membership — PAM optional feature

## Summary
- Windows Server 2016 AD DS supports time-limited group membership (expiring links with a TTL), set with `Add-ADGroupMember -MemberTimeToLive`; an expired membership is evaluated in real time, so it ends on every domain controller without an external process. [DOC S1211, S1219, S-bwyxgvxj]
- PAM is a Windows Server 2016 forest functional level feature. [DOC S-rparnwbm]
- Enabling the PAM optional feature is irreversible: its feature object carries only the forest-scope flag, not the flag that makes an optional feature disablable. [DER S-y4ohln4f, S-st444pl7]
- Not evaluated for a design that avoids temporary collections/boundary groups, but relevant if a future JIT-elevation flow through a broker is considered.

## Facts
- `Add-ADGroupMember -MemberTimeToLive <TimeSpan>` sets a time to live for the new group members. [DOC S-bwyxgvxj]
- With Windows Server 2016 or later the membership is tied to a time limit in AD; an expired link is evaluated in real time by the Security Accounts Manager, so removal takes effect at once on any DC, while adding a member still needs replication. [DOC S1211]
- Privileged access management (PAM) using MIM is listed among the Windows Server 2016 forest functional level features. [DOC S-rparnwbm]
- The "Privileged Access Management Feature" object has `msDS-OptionalFeatureFlags` = FOREST_OPTIONAL_FEATURE, GUID `ec43e873-cce8-4640-b4ab-07ffe4ab5bcd`, and requires forest functional level Windows Server 2016. [DOC S-y4ohln4f]
- An optional feature can be disabled only if its flags include DISABLABLE_OPTIONAL_FEATURE; without it the feature can't be disabled once enabled. [DOC S-st444pl7]
- So enabling PAM in a forest can't be undone. [DER S-y4ohln4f, S-st444pl7: no DISABLABLE_OPTIONAL_FEATURE flag on the PAM feature]
- Effect on Kerberos ticket lifetime, now confirmed: Windows Server 2016's "expiring links" feature is what implements PAM's TTL group membership, and its TTL value is **propagated directly into the issued Kerberos ticket's lifetime** — the KDC caps the TGT's lifetime to the remaining TTL of the shortest-lived time-bound group the user belongs to. If a user is in two time-bound groups with different remaining TTLs, the TGT lifetime is capped to the *lower* of the two. This means a TTL membership does not "silently" expire while an old, longer-lived ticket remains valid: the ticket itself is only ever issued for at most the TTL that was current at logon. [DOC S1219]
- Removing a TTL membership early (an administrator deletes the link before it expires) is a group membership change, and such a change doesn't affect the current TGT or service tickets made from it, so the user keeps the group in already-issued tickets until they expire, at most the TTL that was current at logon; domain-local groups of the resource's domain are the exception, re-read for each new service ticket. No page states this case directly, so confirm it in a lab. [DER S1219, S-ffrzumip, S-v5wjmc3h: ticket lifetime capped to the TTL; membership changes reach only new TGTs]
- MIM PAM (the Microsoft Identity Manager workflow on top of this AD feature) ships in MIM 2016, whose end of support was extended from 2026-01-13 to 2029-01-09; MIM 2016 SP3 is the current service pack, and MIM PAM approvals that used Microsoft Entra MFA Server must move to other MFA providers since that server stopped servicing MFA requests on 2024-09-30. [DOC S-a3advgfv]

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
