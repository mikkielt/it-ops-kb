---
topic: auth/propagation-latency
priority: P1
applies_to: "AD DS, Entra ID, ConfigMgr 2603, Intune, SQL Server 2022/2025, GitLab (docs.gitlab.com current)"
retrieved_utc: 2026-09-26
sources: [S1344, S-fn2rot77, S1346, S1347, S1354, S1355, S1306, S1380, S1378]
status: partial
---

## Summary
See `propagation-latency.csv` for the full table (QA2, QA8, QA9 partially, QA10 out of this agent's scope).
The hard numbers this agent confirmed: AD group membership changes wait for a new Kerberos TGT (bounded
by the default 10h TGT / 7-day renewal window, [[kerberos]] to be written by agent A) -- a different and
longer window than AD account disable/lockout, which MS-KILE's 20-minute account re-check narrows for new
sessions (see [[revocation]]); and Entra Connect Sync's default sync-cycle interval is 30
minutes. Several rows stay `[UNK]` because they belong to ConfigMgr RBAC, SQL authz, GitLab and
PIM-for-Groups topics other agents in this run own; this agent did not duplicate their research.

## Facts
- `Maximum lifetime for user ticket` (Kerberos policy) defaults to 10 hours in the Default Domain Policy;
  when a user's TGT expires a new one must be requested or the existing one renewed.
  `Maximum lifetime for user ticket renewal` defaults to 7 days in the Default Domain Policy. [DOC S1344, S-fn2rot77]
- If the PAC's group SIDs are fixed when the TGT is issued and every service ticket derived from that TGT
  inherits the same PAC, an AD group change reaches an engineer's Kerberos-authenticated `client` flows
  (AdminService, SQL) only at the next fresh TGT -- in the worst case up to 10 hours after the change if the
  user does not log off/on or run `klist purge`. [UNK: PAC-at-issuance behaviour not in S1344 as re-read 2026-09-27; whether a TGT renewal refreshes PAC group SIDs is an open gap, see gaps.md]
- This is a different, and longer, window than account-disable/lockout/expiry: MS-KILE's account-revocation
  check (the account KDC re-checks the account on a TGS-REQ once the TGT is older than 20 minutes) only tests
  good standing (not expired, locked, disabled, or outside logon hours), not group membership, so it does not
  shorten a group-change propagation delay the way it shortens a disable's effective window
  (see [[revocation]]). [DER S1380, S1378: the good-standing list has no group-membership item]
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
