---
topic: auth/token-lifetimes-cae
priority: P1
applies_to: "Microsoft Entra Continuous Access Evaluation, Token Protection (docs current 2026-09-24)"
retrieved_utc: 2026-09-24
sources: [S1291, S1292, S1227]
status: partial
---

# CAE critical events and revocation speed

## Summary
- CAE lets Entra revoke access in near real time for a defined set of "critical events" (account disabled, password change/reset, admin-initiated revocation, network-location change against a Conditional Access location policy), rather than waiting for token expiry. [DOC S1291, S1292]
- `revokeSignInSessions` invalidates a user's refresh tokens; whether that ends an already-issued *access* token immediately depends on the resource/API supporting CAE. [DOC S1291]

## Facts
- CAE-supported critical events include: user account disabled or deleted, password changed or reset, admin-initiated revocation (`revokeSignInSessions`), and a Conditional Access network-location policy change; each is enforced in near real time for CAE-aware resources. [DOC S1291][DOC S1292]
- User termination or password change/reset triggers session revocation "in near real time" for CAE-aware resources; network-location changes are similarly enforced near-real-time against location-based Conditional Access. [DOC S1292]
- `revokeSignInSessions` (Graph) invalidates the user's refresh tokens; a resource that is CAE-aware then rejects the still-live access token before its stated expiry; a resource that is not CAE-aware continues to honour the access token until it naturally expires. [DOC S1291]
- Whether Microsoft Graph itself (as called by workstation client/site instances) and ConfigMgr AdminService are CAE-aware resources is not stated in the two CAE overview pages fetched; Graph is widely documented elsewhere as CAE-capable for many APIs, but AdminService (a non-Microsoft-hosted, on-prem API) is very unlikely to implement CAE and no source claims it does. [UNK for AdminService; DER for Graph general capability is plausible but not directly cited in this fetch]
- This directly narrows QA19 (revocation.md, not owned by this agent): for a resource that is *not* CAE-aware, "disable + revokeSignInSessions" caps exposure at the remaining access-token lifetime, not "near real time" — the near-real-time claim only holds for CAE-aware resources. [DER S1291,S1292]

## Reference
| Critical event | CAE-aware resource enforcement | Non-CAE resource |
|---|---|---|
| Account disabled/deleted | near real time | waits for access-token expiry |
| Password changed/reset | near real time | waits for access-token expiry |
| `revokeSignInSessions` | near real time (refresh token immediately invalid; access token rejected if resource is CAE-aware) | access token still honoured until expiry |
| Conditional Access network-location change | near real time | not enforced until next token acquisition |

## Examples
- Offboarding `jan.kowalski`: Entra disable + `revokeSignInSessions` stops new Graph tokens immediately and stops live tokens near-real-time only for CAE-aware Graph endpoints; any cached AdminService/SQL Kerberos ticket is unaffected by this Entra-side action (Kerberos revocation is a separate mechanism — see `auth/kerberos.md`).

## Open items
- QA19 (per-system time-to-revoke): this file supplies the Graph/CAE half only; AdminService, SQL, SMB, GitLab timings belong to other agents' files and this agent's Kerberos/AD knowledge is out of scope (delegated to auth-a per the split). Feeds `revocation.md`, not owned here — recorded for the lead to merge.
