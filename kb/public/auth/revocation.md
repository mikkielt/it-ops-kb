---
topic: auth/revocation
priority: P1
applies_to: "AD DS, Entra ID, ConfigMgr AdminService, Microsoft Graph, SQL Server, SMB, GitLab"
retrieved_utc: 2026-09-27
sources: [S1380, S1378, S1344, S1345, S1347, S1348, S1354, S1355, S1306, S1375, S1376, S1377, S-iqal4gqk, S-dhnetmt7, S-sjlqevgj, S-m45iz65n, S-yg2usmqp]
status: complete
---

## Summary
Answers QA19 for the systems this agent could research directly. Two corrections from this file's earlier
drafts: (1) **Microsoft Graph is a CAE-enabled resource**, not excluded from it -- it sends a
claims-challenge (401 + `insufficient_claims`) and honours critical events (account disable/delete,
password change, `revokeSignInSessions`, high risk) **if and only if the calling client declares the
`cp1` client capability**; without `cp1`, Graph's normal 1-hour access-token expiry is the only bound.
(2) **AD account disable has three windows, not one**: a brand-new sign-on is blocked immediately, but a
*new session on an existing TGT* is blocked only once MS-KILE's account re-check fires -- Windows uses
**20 minutes** as the TGT-age threshold -- and a session/connection **already open** before the disable
keeps working until its own service ticket expires (default 600 minutes / 10 hours). SQL Server, SMB and
GitLab all follow the same underlying shape: disabling/blocking the identity stops *new* authentications
(immediately for GitLab, within ~20 minutes for Kerberos-backed systems) but does not, by itself,
terminate an *existing* connection/session/token -- an explicit kill/revoke or the credential's own expiry
is what ends it.

## Facts

### (a) AD account disabled -- three separate windows, not one
Plain Kerberos V5 "does not provide account revocation checking for TGS requests, which allows TGT
renewals and service tickets to be issued as long as the TGT is valid even if the account has been
revoked." [DOC S1378] Windows's KILE implementation narrows this gap with an explicit re-check on service
ticket requests, so the real picture has three windows:
- **New AS-REQ** (fresh sign-on, or after `klist purge`): the KDC always validates account state at
  initial authentication; a disabled account is rejected immediately. [DER S1378: contrasted against the
  TGS-REQ gap Kerberos V5 otherwise has]
- **New TGS-REQ on an existing TGT** (e.g. a `client` opening a *new* connection to AdminService or SQL
  while still holding an older TGT): MS-KILE's check-account-policy behaviour requires the account-domain
  KDC to verify the account is still in good standing (not disabled/expired/locked/outside logon hours)
  once the TGT is older than an implementation-specific time, returning `KDC_ERR_CLIENT_REVOKED` if not.
  [DOC S1380] Windows KDCs use **20 minutes** as that time. [DOC S1378] So a disabled account can obtain
  **no new service tickets**, and therefore open no new AdminService/SQL/SMB connection, more than about
  20 minutes after the disable, even while its TGT itself is still unexpired.
- **Already-issued service tickets** (an AdminService/SQL/SMB connection already open at disable time):
  the target server validates the ticket cryptographically and does not call back to the KDC to check
  revocation, so the connection keeps working until that service ticket's own lifetime runs out.
  Microsoft's Kerberos policy guidance states this directly: "users whose accounts have been disabled
  might be able to continue accessing network services by using valid service tickets that were issued
  before their account was disabled," with `Maximum lifetime for service ticket` defaulting to **600
  minutes (10 hours)** in the Default Domain Policy. [DOC S1376]
- **The TGT itself** can be used for up to `Maximum lifetime for user ticket`: 10 hours in the Default Domain
  Policy (0 means TGTs never expire); Microsoft recommends 4 to 10 hours and warns that a long value lets a
  disabled account keep using tickets issued before the disable. [DOC S1344]
- **Net effect:** after an AD disable, a `client` cannot start any new AdminService/SQL/SMB session
  more than ~20 minutes later, but a session that was already open keeps working for up to the remaining
  service-ticket lifetime -- worst case ~10 hours under the default policy -- until it is explicitly
  killed or drops for another reason. [DER S1380, S1378, S1376]
- No ConfigMgr page read (Configure role-based administration, Plan for the SMS Provider, role-based
  administration fundamentals, the AdminService pages) documents a per-call AD account-state check by the
  AdminService/SMS Provider beyond the Kerberos ticket, so the ticket windows above are the documented
  bound; a lab check can still show a shorter one. [DER S-iqal4gqk, S1380: absence in the ConfigMgr pages]

### (b) Entra user disabled + `revokeSignInSessions`
- `revokeSignInSessions` (Graph `POST /users/{id}/revokeSignInSessions`) invalidates all of a user's
  refresh tokens and session cookies by resetting `signInSessionsValidFromDateTime`; Microsoft notes a
  possible delay of a few minutes before tokens are revoked, and that after disable/revoke a user of an
  app that uses access tokens loses access only **when the access token expires**. [DOC S1348, S1345]
- **Corrected finding on Graph and CAE:** Microsoft Graph does implement CAE -- it returns a 401 with a
  `WWW-Authenticate: ... error="insufficient_claims"` claims challenge when a previously issued, not-yet-
  expired access token has been invalidated by a critical event, but **only for a calling client that has
  declared the `cp1` client capability** (`.WithClientCapabilities(new[] {"cp1"})` in MSAL); Microsoft
  names Graph as a service that sends claims challenges only to client apps that declare, through client
  capabilities, that they can handle them. [DOC S1354, S1355] A `cp1`-declaring client also receives long-lived (up to ~24-28 hour)
  CAE access tokens instead of the default 1-hour ones, because revocation is expected to come from the
  critical-event channel rather than expiry. [DOC S1354, S1306]
- Practical consequence: an MSAL client (`client` engineer delegated calls, `site` app-only
  calls) that declares `cp1` and correctly handles the 401 claims challenge gets near-real-time
  revocation from Entra disable/`revokeSignInSessions`/password-reset events on its Graph calls -- the
  same critical-event list documented for Exchange/SharePoint/Teams (account deleted/disabled, password
  changed/reset, MFA enabled, admin revokes refresh tokens, high user risk). [DER S1347, S1354: CAE revokes tokens on the critical events S1347 lists; S1347 names Exchange/SharePoint/Teams, not Graph, as subscribers] A client
  that does **not** declare `cp1` gets ordinary tokens, and Graph does not send it a challenge, so it can
  keep using an already-issued access token until its normal expiry (default 1 hour) even after a critical
  event. This makes `cp1` support in a workstation client's MSAL configuration a real, low-cost revocation-latency
  decision, not just a resiliency feature. [DER S1354,S1355]
- Workload-identity (app-only) CAE is a separate, narrower feature: CAE for workload identities is
  supported only for access requests to Microsoft Graph (not other resource providers), also gated on the
  service principal declaring `cp1`, with long-lived tokens up to ~24 hours. [DOC S1306]

### (c) Removal from a role group
- No effect on an already-issued Kerberos ticket's PAC group SIDs (AD-sourced roles) or an already-issued,
  non-CAE Graph/access token (Entra-sourced roles); effective at the next token/ticket issuance, or
  immediately via a claims challenge if the client is CAE (`cp1`)-aware and the removal is surfaced as a
  critical event -- group/role changes are not on Entra's documented critical-event list (only account
  disable/delete, password change, MFA enablement, explicit token revocation, and high risk are), so a
  bare group removal does **not** get the fast CAE path; it waits for ordinary token/ticket expiry, per
  [[propagation-latency]]. [DER S1347: group/role membership change is absent from the critical-event list]

### (d) Password reset
- Documented CAE critical event; for a `cp1`-aware Graph client, near-real-time (Microsoft's stated goal,
  up to ~15 minutes attributed to event-propagation latency for the services it names explicitly). [DOC
  S1347] For AD-only Kerberos authentication, a password reset does not itself invalidate an
  already-issued TGT or service ticket -- it only changes what a *new* AS-REQ must present -- so the same
  three-window shape as (a) applies: existing service tickets keep working at the target server up to
  their own lifetime (default 600 minutes), a fresh TGS-REQ on the old TGT is not specially checked against
  a password change the way it is for disable/expire/lockout (`good standing` in MS-KILE's check does not
  include "password was changed"), and only a fresh AS-REQ is forced to use the new password. [DER S1376,
  S1380: `good standing` is defined as not expired/locked/disabled/outside logon hours, which does not list
  a password change]

### SQL Server
- `ALTER LOGIN ... DISABLE` "doesn't affect the behavior of logins that are already connected. (Use the
  `KILL` statement to terminate an existing connection.) Disabled logins retain their permissions and can
  still be impersonated." [DOC S1375]
- An authenticated connection caches the login's identity (for a Windows-authentication login, including
  its Windows group membership) for as long as the connection lasts; changes such as a password reset or
  a Windows group membership change take effect only after the login signs out and in again, and a
  sysadmin member or a login with `ALTER ANY CONNECTION` can `KILL` the connection to force that. `ALTER
  LOGIN ... DISABLE` cannot be used to deny access to a Windows group login. [DOC S1375]

### SMB
- Same underlying Kerberos mechanism as (a): an SMB session established with a service ticket keeps
  working after that session's own authentication step; "after a connection is authenticated, it no longer
  matters whether the session ticket remains valid, as session tickets are used only to authenticate new
  connections" -- so disabling the AD account of an engineer or a `gmsa-*` account does not drop an
  already-open SMB session to a artifact share. [DOC S1376] Establishing a *new* SMB session needs a new
  service ticket, so it follows the same ~20-minute MS-KILE re-check window as (a), not "next AS-REQ": a
  new SMB session can be refused well before the disabled account's TGT itself expires. [DER S1380, S1378]

### GitLab
- Revoking a personal access token is done "to immediately invalidate it and prevent further use" -- this is an
  explicit, synchronous action, not something that happens automatically on user block/disable by default.
  [DOC S1377] For an **Enterprise user** (GitLab's term for a managed user under a verified domain,
  Premium/Ultimate), GitLab documents that deleting or blocking that user's account **automatically**
  revokes their personal access tokens. [DOC S1377]
- A blocked user cannot sign in or access any repositories, and a deactivated user cannot access
  repositories or the API. [DOC S-dhnetmt7] So a plain account's PATs stop working once the account is
  blocked or deactivated, even though they are not revoked (they work again if it is unblocked); revoke
  them explicitly when the block is meant to be permanent. [DER S-dhnetmt7, S1377] The effect of a block
  on CI/CD job tokens, runner authentication tokens (`glrt-`) and open web sessions is not stated in these
  pages (see `_gaps.md`).
- A membership removal is not evaluated live per request: project access, with group membership
  already applied, is stored in the `project_authorizations` table [DOC S-sjlqevgj], and creating or
  destroying a membership queues an asynchronous `AuthorizedProjectsWorker` refresh (Sidekiq, high
  priority). [CODE S-m45iz65n: app/models/member.rb#refresh_member_authorized_projects; CODE S-yg2usmqp: app/services/user_project_access_changed_service.rb#execute]

## Reference
| Step | AdminService | Graph | SQL Server | SMB | GitLab |
|---|---|---|---|---|---|
| AD account disabled | new session refused after ~20 min (TGS-REQ recheck); existing session up to ~10h (service-ticket lifetime); no extra AdminService check documented | n/a (AD-only) | existing connection unaffected until `KILL`; new connections refused after ~20 min (TGS-REQ recheck), not next AS-REQ | existing SMB session unaffected; new session refused after ~20 min (TGS-REQ recheck) | n/a (AD-only unless SSO-linked) |
| Entra disable + revokeSignInSessions | n/a unless AdminService trusts Entra tokens (via CMG, see configmgr-rbac-auth.md) | near-real-time **only if the client declared `cp1`**; otherwise up to 1h (default access-token lifetime) | Entra auth only: open connection keeps its identity until `KILL`; new connections need a new token (bounded by access-token lifetime; SQL Server is not a CAE resource) | n/a | Enterprise-user block/delete auto-revokes PATs; a plain block stops API use without revoking PATs |
| Removal from a role group | only with a new TGT (lock, sign-out or TGT expiry, typically 10 h); see propagation-latency.csv | not a CAE critical event -- waits for next token issuance carrying the groups/roles claim | next connection (sign out and in, or `KILL`) | n/a | asynchronous `project_authorizations` refresh (background job) |
| PAT/token explicit revoke | n/a | n/a | n/a | n/a | immediate, synchronous |

## Examples
No fixture-specific configuration; mechanism-only facts.
