---
topic: auth/propagation-latency
priority: P1
applies_to: "AD DS, Entra ID, ConfigMgr 2603, Intune, SQL Server 2022/2025, GitLab (docs.gitlab.com current)"
retrieved_utc: 2026-09-24
sources: [S1344, S1346, S1347, S1354, S1355, S1306, S1380, S1378]
status: partial
---

## Summary
See `propagation-latency.csv` for the full table (QA2, QA8, QA9 partially, QA10 out of this agent's scope).
The hard numbers this agent confirmed: AD group membership changes wait for a new Kerberos TGT (bounded
by the default 10h TGT / 7-day renewal window, [[kerberos]] to be written by agent A) -- a different and
longer window than AD account disable/lockout, which MS-KILE's 20-minute account re-check narrows for new
sessions (see [[revocation]]); and Entra Connect Sync's default and minimum delta-sync interval is 30
minutes. Several rows stay `[UNK]` because they belong to ConfigMgr RBAC, SQL authz, GitLab and
PIM-for-Groups topics other agents in this run own; this agent did not duplicate their research.

## Facts
- `Maximum lifetime for user ticket` (Kerberos policy) defaults to 10 hours in the Default Domain Policy;
  `Maximum lifetime for user ticket renewal` defaults to 7 days. A ticket-granting ticket is renewed
  (fresh session key) up to every 10 hours for up to 7 days before a brand-new TGT must be requested.
  Because the PAC's group SIDs are fixed at ticket-issuance time and every service ticket derived from a
  TGT inherits that same PAC unchanged, an AD group change an engineer's Kerberos-authenticated `client`
  flows (AdminService, SQL) only takes effect at the next fresh TGT -- in the worst case, up to 10 hours
  after the change if the user does not log off/on or run `klist purge`. [DER S1344: lifetime defaults are DOC; whether a TGT renewal refreshes PAC group SIDs is UNK, see gaps.md] This is a different,
  and longer, window than account-disable/lockout/expiry: MS-KILE's account-revocation check (which fires
  on a TGS-REQ once the TGT is older than 20 minutes) only tests good standing, not group membership, so
  it does not shorten a group-change propagation delay the way it shortens a disable's effective window
  (see [[revocation]]). [DER S1380, S1378]
- Microsoft Entra Connect Sync's scheduler runs a delta sync every 30 minutes by default; 30 minutes is
  also enforced as the minimum interval a tenant can configure. `Start-ADSyncSyncCycle -PolicyType Delta`
  forces an out-of-band cycle. [DOC S1346]
- Continuous access evaluation's critical-event path (account disabled/deleted, password reset, MFA
  enabled, admin token revocation, high user risk) is evaluated "near real time" by Exchange Online,
  SharePoint Online and Teams automatically, with latency of up to 15 minutes attributed to event
  propagation. Microsoft Graph gets the same critical-event fast path too, but only for a calling client
  that declares the `cp1` client capability (see the CAE-aware-client bullet below and [[revocation]]);
  it is not automatic for every Graph caller the way it is for those three first-party services. [DOC
  S1347, S1354, S1355]
- Conditional Access policy and **group membership** changes synced into Exchange/SharePoint/Teams for
  their own (non-critical-event) enforcement can take up to **one day**, reduced to about **two hours**
  with an unspecified subset of optimizations Microsoft has since applied; this is the officially
  documented ceiling for policy/group-driven access changes in those services, separate from the
  15-minute critical-event path above. [DOC S1347]
- CAE-aware client sessions get long-lived access tokens (up to ~28 hours for delegated, ~24 hours for
  workload identities) instead of the default 1 hour, because revocation is expected to come from critical
  events, not token expiry. **Correction from an earlier draft of this file:** Microsoft Graph itself is a
  CAE-enabled resource -- it issues these long-lived tokens and sends a claims-challenge on revocation --
  but only for a calling client that declares the `cp1` client capability (MSAL `WithClientCapabilities`).
  A `client`/`site` MSAL application that does **not** declare `cp1` gets ordinary tokens and the
  default 1-hour Graph access-token ceiling, with no CAE fast-revocation path; one that does declare `cp1`
  gets both the longer token lifetime and near-real-time revocation on the documented critical events
  (account disable/delete, password change, `revokeSignInSessions`, high risk) -- but *not* on a bare
  group/role membership change, which is not on that critical-event list. [DOC S1354, S1355, S1306; see
  [[revocation]] for the full correction and reasoning]

## Reference
See `propagation-latency.csv`.

## Examples
No fixture-specific configuration; mechanism-only facts.
