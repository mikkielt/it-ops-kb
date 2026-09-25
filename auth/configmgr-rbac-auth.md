---
topic: auth/configmgr-rbac-auth
priority: P0
applies_to: "ConfigMgr 2603, extends kb/mecm/rbac.md and kb/mecm/adminservice.md"
retrieved_utc: 2026-09-24
sources: [S307, S311, S1212, S1213, S1210, S1218]
status: partial
---

# ConfigMgr RBAC resolution, MFA for SMS Provider, and Tier-0 status

## Summary
- The Kerberos/NTLM rejection facts already live in `mecm/adminservice.md`; this file adds when a new AD group membership takes effect, MFA for SMS Provider calls, and ConfigMgr's place in Microsoft's tiering guidance.
- QA2 (when does a new AD group granting a ConfigMgr role take effect) is **UNK from official sources** this session — general AD/Kerberos group-membership refresh rules apply (new logon / new TGT, since group SIDs are baked into the Kerberos PAC), but no ConfigMgr-specific provider-cache document was found.
- ConfigMgr is not explicitly labelled "Tier 0" in the Microsoft enterprise-access-model docs found this session, but MFA for SMS Provider calls has existed since ConfigMgr CB 1702, and Microsoft's general enterprise access model treats systems that grant broad device/config control over an estate as control-plane (Tier 0) equivalent — this is a derived judgement, not a documented Microsoft classification. [DER S1210,S1212]

## Facts
- A ConfigMgr administrative user's effective permission is a Windows/AD security principal (user or, indirectly, a group) mapped to security roles/scopes/collections; this is documented in `mecm/rbac.md` (unchanged here). [DOC S1218]
- Since ConfigMgr version 1702, MFA can be enabled for SMS Provider calls; this uses the `AuthenticationLevel`-style policy referenced by the troubleshooting doc for enabling MFA for SMS Provider calls. [DOC S1212]
- Since 2509, the AdminService rejects NTLM (already in `mecm/adminservice.md`, sources S307). A community report describes clients that relied on NTLM fallback (e.g., accessed by non-FQDN name or with a missing SPN) failing after the upgrade instead of degrading; the documented fix is to use the FQDN and ensure Kerberos SPNs are correct, not to re-enable NTLM. [COMMUNITY S1213]
- Because Kerberos group membership (SIDs) is embedded in the ticket-granting ticket's PAC at ticket-issue time, a newly added AD group generally does not take effect for a signed-in session until a new TGT is obtained — normally a new logon, or (for machine accounts / long sessions) the next TGT renewal — this is a general Kerberos mechanism, not confirmed in ConfigMgr-specific SMS Provider documentation. [DER general Kerberos PAC behaviour; UNK for a ConfigMgr-specific provider cache layer on top of this]
- Role-based administration fundamentals describes role-based admin as combining security roles, security scopes and assigned collections into a per-administrative-user scope, computed by the SMS Provider from the caller's Windows/AD identity (via the `SMS_Admin` object created for each administrative user or group) at call time; the page does not state whether the SMS Provider re-reads AD group membership on every call, caches it, or only refreshes it on a new logon/ticket. [DOC S1218]
- Searched: Role-based administration fundamentals (S1218), Configure role-based administration, Plan for the SMS Provider, and the `SMS_Admin` WMI class reference — none of the three official pages found states a provider-side cache refresh interval or ties the refresh explicitly to Kerberos ticket renewal. Treated as confirmed UNK after 3 distinct official-source attempts, per rule 4 of PROMPT-auth.md. [UNK]
- No official Microsoft statement classifying ConfigMgr/SMS Provider explicitly as "Tier 0" was found; Microsoft's enterprise access model defines Tier 0/control plane generically as systems whose compromise grants control of the environment, and treats admin workstations, PAWs and MFA as universal controls rather than naming ConfigMgr specifically. [DOC S1210]

## Reference
| Question | Answer | Confidence |
|---|---|---|
| QA2: when does a new AD group→role mapping take effect | New logon / new TGT (Kerberos PAC), ConfigMgr-provider-cache behaviour on top of this is unconfirmed | DER + UNK |
| QA17: is ConfigMgr officially "Tier 0"? | Not found as an explicit Microsoft label; general enterprise-access-model guidance implies control-plane treatment | DER |
| MFA for SMS Provider | Available since CB 1702 | DOC |

## Examples
- After adding `jan.kowalski` to `SG-Engineer` (which is mapped, via a ConfigMgr collection/role assignment, to the `engineer` security role), expect the change to require a new logon on the workstation used for AdminService calls before it is honoured.

Verification: on an isolated ConfigMgr lab site, add a test admin account to a security-role-granting AD group, call the AdminService immediately (existing ticket), then again after `klist purge` + re-logon → proves whether the SMS Provider itself adds any delay beyond the Kerberos PAC refresh.
