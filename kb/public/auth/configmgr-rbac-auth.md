---
topic: auth/configmgr-rbac-auth
priority: P0
applies_to: "ConfigMgr 2603, extends mecm/rbac.md and mecm/adminservice.md"
retrieved_utc: 2026-09-27
sources: [S-7jumyiid, S-6m7klb4f, S1212, S1213, S1210, S1218]
status: partial
---

# ConfigMgr RBAC resolution, MFA for SMS Provider, and Tier-0 status

## Summary
- The Kerberos/NTLM rejection facts already live in `mecm/adminservice.md`; this file adds when a new AD group membership takes effect, MFA for SMS Provider calls, and ConfigMgr's place in Microsoft's tiering guidance.
- QA2 (when does a new AD group granting a ConfigMgr role take effect) is **UNK from official sources** this session — general AD/Kerberos group-membership refresh rules apply (new logon / new TGT, since group SIDs are baked into the Kerberos PAC), but no ConfigMgr-specific provider-cache document was found.
- ConfigMgr is not labelled "Tier 0" in the Microsoft enterprise access model page; that page makes the control plane (expanded Tier 0) the centralized-identity-based access-control layer and puts "enterprise-wide IT management functions" in the management plane, so on its wording alone ConfigMgr reads as management plane, and treating it as control-plane-equivalent is a local judgement, not a documented Microsoft classification; MFA for SMS Provider calls has existed since ConfigMgr CB 1702. [DER S1210,S1212: plane definitions and MFA lever read from the two pages, ConfigMgr placement inferred]

## Facts
- A ConfigMgr administrative user's *administrative scope* is the combination of the security roles, security scopes and collections assigned to it; it controls which objects the user sees in the console and the permissions on them (details in `mecm/rbac.md`). [DOC S1218]
- Since ConfigMgr version 1702, MFA can be enabled for SMS Provider calls: a Full Administrator with the All scope runs `SetAuthenticationLevel` on `SMS_Site`, setting the global `AuthenticationLevel` (0 default, 10 PIN or smart card, 20 PIN) and an optional `ExceptionList` of user/group SIDs. [DOC S1212]
- Plan for the SMS Provider: the provider enforces ConfigMgr security by returning only what the user is authorized to view, and a site-wide minimum authentication level applies to every component that reaches it (console, SDK methods, PowerShell cmdlets, administration service): Windows authentication (default), certificate authentication (Windows sign-in with a PKI certificate), or Windows Hello for Business, under which the user's token must carry an MFA claim from Windows Hello for Business or the site rejects the action. [DOC S-6m7klb4f]
- Since 2509, the AdminService rejects NTLM authentication attempts, and `AdminService.log` records "Rejecting NTLM authentication." (also in `mecm/adminservice.md`). [DOC S-7jumyiid]
- A community forum thread reports the same 2509 change and log message. [COMMUNITY S1213]
- Clients that relied on NTLM fallback (e.g. a non-FQDN name or a missing SPN) failing after the upgrade, with the fix being the FQDN and correct Kerberos SPNs rather than re-enabling NTLM. [UNK: not in S1213 as re-read 2026-09-27]
- Because Kerberos group membership (SIDs) is embedded in the ticket-granting ticket's PAC at ticket-issue time, a newly added AD group generally does not take effect for a signed-in session until a new TGT is obtained — normally a new logon, or (for machine accounts / long sessions) the next TGT renewal — this is a general Kerberos mechanism, not confirmed in ConfigMgr-specific SMS Provider documentation. [DER general Kerberos PAC behaviour; UNK for a ConfigMgr-specific provider cache layer on top of this]
- Role-based administration fundamentals says role-based administration configurations replicate to every site as global data and are applied to all administrative connections, and that intersite replication delays can stop a site receiving role-based administration changes; the page does not say how the SMS Provider resolves AD group membership, whether it caches it, or when it refreshes it. [DOC S1218]
- Searched: Role-based administration fundamentals (S1218), Configure role-based administration, Plan for the SMS Provider, and the `SMS_Admin` WMI class reference — none of the three official pages found states a provider-side cache refresh interval or ties the refresh explicitly to Kerberos ticket renewal. Treated as confirmed UNK after 3 distinct official-source attempts, per rule 4 of PROMPT-auth.md. [UNK]
- No official Microsoft statement classifying ConfigMgr/SMS Provider explicitly as "Tier 0" was found; Microsoft's enterprise access model says Tier 0 expands into the control plane (all aspects of access control, based on centralized enterprise identity systems), splits the old Tier 1 into a management plane (enterprise-wide IT management) and a data/workload plane, and names no specific product such as ConfigMgr. [DOC S1210]

## Reference
| Question | Answer | Confidence |
|---|---|---|
| QA2: when does a new AD group→role mapping take effect | New logon / new TGT (Kerberos PAC), ConfigMgr-provider-cache behaviour on top of this is unconfirmed | DER + UNK |
| QA17: is ConfigMgr officially "Tier 0"? | Not found as an explicit Microsoft label; the enterprise access model's wording puts enterprise-wide IT management in the management plane, so control-plane treatment is a local choice | DER |
| MFA for SMS Provider | Available since CB 1702 | DOC |

## Examples
- After adding `jan.kowalski` to `SG-Engineer` (which is mapped, via a ConfigMgr collection/role assignment, to the `engineer` security role), expect the change to require a new logon on the workstation used for AdminService calls before it is honoured.

Verification: on an isolated ConfigMgr lab site, add a test admin account to a security-role-granting AD group, call the AdminService immediately (existing ticket), then again after `klist purge` + re-logon → proves whether the SMS Provider itself adds any delay beyond the Kerberos PAC refresh.
