---
topic: auth/token-lifetimes-cae
priority: P1
applies_to: "Microsoft Entra Continuous Access Evaluation, Token Protection (docs current 2026-09-24)"
retrieved_utc: 2026-09-27
sources: [S1291, S1292, S1227, S1348]
status: partial
---

# CAE critical events and revocation speed

## Summary
- CAE lets CAE-capable resources reject unexpired tokens in near real time after a defined set of "critical events" (account deleted or disabled, password changed or reset, MFA enabled for the user, admin revocation of refresh tokens, high or elevated user risk), and separately enforces Conditional Access IP-location policy changes, rather than waiting for token expiry. [DOC S1291, S1292]
- `revokeSignInSessions` invalidates a user's refresh tokens; whether that ends an already-issued *access* token early depends on both the resource and the client being CAE-capable. [DOC S1348, S1291]

## Facts
- CAE critical events: user account deleted or disabled, password changed or reset, MFA enabled for the user, administrator revokes all refresh tokens (`revokeSignInSessions`), high user risk from ID Protection; the goal is near real time, with up to 15 minutes of event-propagation latency. Network-location changes are a separate scenario (Conditional Access policy evaluation), enforced instantly for IP-based location policies. [DOC S1292, S1291]
- User termination or password change/reset triggers session revocation "in near real time" for CAE-aware resources; network-location changes are similarly enforced near-real-time against location-based Conditional Access. [DOC S1292]
- `revokeSignInSessions` (Graph) invalidates the user's refresh tokens (possibly after a few minutes); a CAE-capable resource called by a CAE-capable client then rejects the still-valid access token with a 401 claim challenge; without CAE-capable clients the default access-token lifetime of 1 hour remains the bound. [DOC S1348, S1292, S1291]
- Token Protection is a separate Conditional Access session control: against token replay rather than for faster revocation, it makes Entra accept only device-bound sign-in session tokens such as the PRT. For native apps it is enforceable on Exchange Online, SharePoint Online and Microsoft Teams (plus Azure Virtual Desktop and Windows 365 on Windows); Microsoft Graph is not among the listed resources. [DOC S1227]
- Whether Microsoft Graph itself (as called by workstation client/site instances) and ConfigMgr AdminService are CAE-aware resources is not stated in the two CAE overview pages fetched; Graph is widely documented elsewhere as CAE-capable for many APIs, but AdminService (a non-Microsoft-hosted, on-prem API) is very unlikely to implement CAE and no source claims it does. [UNK for AdminService; DER for Graph general capability is plausible but not directly cited in this fetch]
- This directly narrows QA19 (revocation.md, not owned by this agent): for a resource that is *not* CAE-aware, "disable + revokeSignInSessions" caps exposure at the remaining access-token lifetime, not "near real time" — the near-real-time claim only holds for CAE-aware resources. [DER S1291,S1292]

## Reference
| Critical event | CAE-aware resource enforcement | Non-CAE resource |
|---|---|---|
| Account disabled/deleted | near real time | waits for access-token expiry |
| Password changed/reset | near real time | waits for access-token expiry |
| `revokeSignInSessions` | near real time (refresh tokens invalid, possibly after a few minutes; access token rejected if resource and client are CAE-capable) | access token still honoured until expiry |
| Conditional Access network-location change | near real time | not enforced until next token acquisition |

## Examples
- Offboarding `jan.kowalski`: Entra disable + `revokeSignInSessions` stops new Graph tokens immediately and stops live tokens near-real-time only for CAE-aware Graph endpoints; any cached AdminService/SQL Kerberos ticket is unaffected by this Entra-side action (Kerberos revocation is a separate mechanism — see `auth/kerberos.md`).

## Open items
- QA19 (per-system time-to-revoke): this file supplies the Graph/CAE half only; AdminService, SQL, SMB, GitLab timings belong to other agents' files and this agent's Kerberos/AD knowledge is out of scope (delegated to auth-a per the split). Feeds `revocation.md`, not owned here — recorded for the lead to merge.
