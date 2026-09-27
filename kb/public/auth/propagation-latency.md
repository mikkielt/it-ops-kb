---
topic: auth/propagation-latency
priority: P1
applies_to: "AD DS, Entra ID, ConfigMgr 2603, Intune, SQL Server 2022/2025, GitLab (docs.gitlab.com current)"
retrieved_utc: 2026-09-27
sources: [S1344, S-fn2rot77, S1346, S1347, S1354, S1355, S1306, S1380, S1378, S-ffrzumip, S-ltkr37vz, S-v5wjmc3h, S-ivhcma7e, S-r6vi3iik, S-pq22l6q6, S-n6x3ci6g, S1282, S-jpsjsa5i, S-ljhugmcx, S1281, S1280, S-2vza23mx, S-h6idpd4a, S1375, S-sjlqevgj, S-m45iz65n, S-yg2usmqp]
status: complete
---

## Summary
See `propagation-latency.csv` for the full table (QA2, QA8, QA9, QA10). AD global and universal group
changes reach Kerberos flows only with a new TGT (lock, sign-out, `klist purge` or expiry, default 10 h), and
a TGT renewal does not refresh them; this is a longer window than AD account disable, which MS-KILE's
20-minute re-check narrows (see [[revocation]]). Entra Connect Sync runs every 30 minutes by default, dynamic
groups typically within a few hours, PIM activations within seconds (Intune roles via PIM for Groups up to 15
minutes), SQL Server on the next connection, and GitLab through an asynchronous authorization refresh.
[DER S-ffrzumip, S-r6vi3iik, S1346, S-pq22l6q6, S-jpsjsa5i, S-ljhugmcx, S1375, S-sjlqevgj: summary of the facts and table rows]

## Facts
- `Maximum lifetime for user ticket` (Kerberos policy) defaults to 10 hours in the Default Domain Policy;
  when a user's TGT expires a new one must be requested or the existing one renewed.
  `Maximum lifetime for user ticket renewal` defaults to 7 days in the Default Domain Policy. [DOC S1344, S-fn2rot77]
- A group membership change does not affect the current TGT or any service tickets created from it: the
  ticket-granting service takes the group information from the TGT, and the TGT is not replaced until the user
  locks the client, signs out, or it expires (typically 10 hours). [DOC S-ffrzumip] The KDC copies the
  populated PAC fields from the TGT into each service ticket's PAC [DOC S-ltkr37vz], and a renewal leaves every
  ticket field except the times and session key unchanged [DOC S-r6vi3iik] (the KDC only re-signs the PAC on
  renewal [DOC S-ivhcma7e]).
- Domain-local groups of the resource's domain are the exception: the KDC adds domain-local group membership to
  the PAC of every service ticket it issues, so those changes reach the next service ticket. [DOC S-v5wjmc3h]
- So an AD global or universal group change reaches an engineer's Kerberos-authenticated `client` flows
  (AdminService, SQL) only with a fresh TGT -- in the worst case up to 10 hours after the change if the user does
  not lock, sign out or run `klist purge`; a TGT renewal does not bring it. [DER S-ffrzumip, S-ltkr37vz, S-r6vi3iik]
- The VPN support article says a TGT can be renewed for 10 days, while the Kerberos policy page gives a 7-day
  default for `Maximum lifetime for user ticket renewal`; see `_conflicts.md`. [DOC S-ffrzumip, S-fn2rot77]
- This is a different, and longer, window than account-disable/lockout/expiry: MS-KILE's account-revocation
  check (the account KDC re-checks the account on a TGS-REQ once the TGT is older than 20 minutes) only tests
  good standing (not expired, locked, disabled, or outside logon hours), not group membership, so it does not
  shorten a group-change propagation delay the way it shortens a disable's effective window
  (see [[revocation]]). [DER S1380, S1378: the good-standing list has no group-membership item]
- Entra dynamic membership groups: membership changes are typically processed within a few hours, but processing can take more than 24 hours; there is no on-demand trigger, and editing the membership rule (for example adding a trailing space) makes Entra reprocess the group. [DOC S-pq22l6q6, S-n6x3ci6g]
- Microsoft Entra Connect Sync's built-in scheduler runs a synchronization cycle every 30 minutes by default;
  `CustomizedSyncCycleInterval` changes it, but a value below `AllowedSyncCycleInterval` (the shortest interval
  Entra ID allows) is replaced by that minimum. `Start-ADSyncSyncCycle -PolicyType Delta` runs a delta cycle
  on demand. [DOC S1346]
- Continuous access evaluation's critical events (account deleted or disabled, password changed or reset, MFA
  enabled for the user, admin revocation of all refresh tokens, high user risk) are evaluated near real time by
  Exchange Online, SharePoint Online and Teams, with up to 15 minutes of latency from event propagation.
  [DOC S1347] Microsoft Graph sends claims challenges (and CAE tokens) only to a calling client that declares
  the `cp1` client capability, so a Graph caller without `cp1` gets no CAE fast revocation (see the
  CAE-aware-client bullet below and [[revocation]]). [DOC S1354, S1355]
- Conditional Access policy and **group membership** changes made by administrators can take up to **one day**
  to become effective in resource providers such as Exchange Online and SharePoint Online (replication delay);
  some optimization reduces the delay for **policy updates** to **two hours**, but not in all scenarios. The
  documented workaround for immediate effect is revoking the user's refresh tokens/session. This is separate
  from the 15-minute critical-event path above. [DOC S1347]
- CAE-aware sessions get long-lived access tokens (up to 28 hours for users; up to 24 hours for workload
  identities, which CAE supports only against Microsoft Graph) instead of the default 1 hour. **Correction from
  an earlier draft of this file:** Microsoft Graph is a CAE-enabled resource -- it rejects revoked tokens with a
  claims challenge -- but only for a calling client that declares the `cp1` client capability (MSAL
  `WithClientCapabilities`); a client that does not declare `cp1` receives neither claims challenges nor CAE
  tokens. [DOC S1354, S1355, S1306]
- Consequently a `client`/`site` MSAL application without `cp1` keeps the default 1-hour access-token ceiling
  and no CAE fast-revocation path, while one with `cp1` gets the longer lifetime and near-real-time revocation
  on the critical events above -- but *not* on a bare group/role membership change, which is not on that
  critical-event list. [DER S1347, S1355: critical-event list plus the cp1 opt-in rule; see [[revocation]]]

## Reference
See `propagation-latency.csv`.

## Examples
No fixture-specific configuration; mechanism-only facts.
