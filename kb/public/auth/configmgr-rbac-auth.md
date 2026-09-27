---
topic: auth/configmgr-rbac-auth
priority: P0
applies_to: "ConfigMgr 2603, extends mecm/rbac.md and mecm/adminservice.md"
retrieved_utc: 2026-09-27
sources: [S-7jumyiid, S-6m7klb4f, S1212, S1213, S1210, S1218, S-5yckwasl, S-7bouxzdg, S-ffrzumip, S-iqal4gqk, S-7nbamxyc]
status: complete
---

# ConfigMgr RBAC resolution, MFA for SMS Provider, and Tier-0 status

## Summary
- The Kerberos/NTLM rejection facts already live in `mecm/adminservice.md`; this file adds when a new AD group membership takes effect, MFA for SMS Provider calls, and ConfigMgr's place in Microsoft's tiering guidance.
- QA2 (when does a new AD group granting a ConfigMgr role take effect): Microsoft documents that a group change does not affect the current TGT or the service tickets made from it, so it reaches Kerberos-authenticated AdminService calls only with a new TGT (lock, sign-out or expiry); whether the SMS Provider adds its own cache on top is not documented (lab check below).
- ConfigMgr is not named in the enterprise access model page, which puts "enterprise-wide IT management functions" in the management plane; the AD DS tier model page puts systems that patch or run agents on Tier 0 identity systems in Tier 0 and IT infrastructure management of Tier 1 servers in Tier 1, so ConfigMgr is Tier 0 when it manages domain controllers or other Tier 0 systems and Tier 1 otherwise; MFA for SMS Provider calls has existed since ConfigMgr CB 1702. [DER S1210, S-7nbamxyc, S1212: tier and plane definitions read from the pages, ConfigMgr placement applied from them]

## Facts
- A ConfigMgr administrative user's *administrative scope* is the combination of the security roles, security scopes and collections assigned to it; it controls which objects the user sees in the console and the permissions on them (details in `mecm/rbac.md`). [DOC S1218]
- Since ConfigMgr version 1702, MFA can be enabled for SMS Provider calls: a Full Administrator with the All scope runs `SetAuthenticationLevel` on `SMS_Site`, setting the global `AuthenticationLevel` (0 default, 10 PIN or smart card, 20 PIN) and an optional `ExceptionList` of user/group SIDs. [DOC S1212]
- Plan for the SMS Provider: the provider enforces ConfigMgr security by returning only what the user is authorized to view, and a site-wide minimum authentication level applies to every component that reaches it (console, SDK methods, PowerShell cmdlets, administration service): Windows authentication (default), certificate authentication (Windows sign-in with a PKI certificate), or Windows Hello for Business, under which the user's token must carry an MFA claim from Windows Hello for Business or the site rejects the action. [DOC S-6m7klb4f]
- Since 2509, the AdminService rejects NTLM authentication attempts, and `AdminService.log` records "Rejecting NTLM authentication." (also in `mecm/adminservice.md`). [DOC S-7jumyiid]
- A community forum thread reports the same 2509 change and log message. [COMMUNITY S1213]
- Callers that reached the AdminService through NTLM fallback now fail: Windows does not try Kerberos for a host given as an IP address and falls back to NTLM, and a missing or duplicate SPN makes the KDC answer KDC_ERR_S_PRINCIPAL_UNKNOWN or KDC_ERR_PRINCIPAL_NOT_UNIQUE; the fix is the FQDN with one correct SPN (or, for IP access, `TryIPSPN` plus an IP SPN), not NTLM. [DER S-7jumyiid, S-5yckwasl, S-7bouxzdg: 2509 NTLM rejection combined with the documented fallback and SPN errors]
- A change in group membership does not affect the current TGT or any service tickets created from it, because the ticket-granting service copies the group information from the TGT; the TGT is not renewed until the user locks the client, signs out, or the TGT expires (typically 10 hours). [DOC S-ffrzumip]
- So a newly added AD group reaches Kerberos-authenticated AdminService calls only after a new TGT; whether the SMS Provider caches the resolved administrative user on top of that is not stated in any ConfigMgr page read. [DER S-ffrzumip, S1218, S-iqal4gqk: ticket rule applied to the AdminService; provider cache absent from the ConfigMgr pages]
- An administrative user in the Protected Users group can run the Configuration Manager console for only 4 hours at a time; the console then closes and unsaved work is lost. [DOC S-iqal4gqk]
- Role-based administration fundamentals says role-based administration configurations replicate to every site as global data and are applied to all administrative connections, and that intersite replication delays can stop a site receiving role-based administration changes; the page does not say how the SMS Provider resolves AD group membership, whether it caches it, or when it refreshes it. [DOC S1218]
- The AD DS tier model puts in Tier 0 the systems that operate or manage Tier 0 identity systems, including backup, monitoring, patching, hypervisor, antivirus and EDR solutions, puts IT infrastructure management solutions that control Tier 1 servers in Tier 1, and warns against collapsing everything into Tier 0. [DOC S-7nbamxyc]
- No official Microsoft statement naming ConfigMgr/SMS Provider as "Tier 0" was found; Microsoft's enterprise access model says Tier 0 expands into the control plane (all aspects of access control, based on centralized enterprise identity systems), splits the old Tier 1 into a management plane (enterprise-wide IT management) and a data/workload plane, and names no specific product such as ConfigMgr. [DOC S1210]

## Reference
| Question | Answer | Confidence |
|---|---|---|
| QA2: when does a new AD group→role mapping take effect | New TGT (lock, sign-out or expiry, typically 10 h); a provider cache on top is undocumented (lab check) | DOC + DER |
| QA17: is ConfigMgr officially "Tier 0"? | Not named; by the AD DS tier model, Tier 0 when it patches or runs agents on DCs or other Tier 0 systems, else Tier 1 | DER |
| MFA for SMS Provider | Available since CB 1702 | DOC |

## Examples
- After adding `jan.kowalski` to `SG-Engineer` (which is mapped, via a ConfigMgr collection/role assignment, to the `engineer` security role), expect the change to require a new logon on the workstation used for AdminService calls before it is honoured.

Verification: on an isolated ConfigMgr lab site, add a test admin account to a security-role-granting AD group, call the AdminService immediately (existing ticket), then again after `klist purge` + re-logon → proves whether the SMS Provider itself adds any delay beyond the Kerberos PAC refresh.
