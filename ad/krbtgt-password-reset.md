---
topic: ad/krbtgt-password-reset
priority: P1
applies_to: "Active Directory Domain Services (all supported Windows Server versions); Microsoft Defender for Identity"
retrieved_utc: 2026-09-26
sources: [S-4ikiakpi, S-nl7th7fi, S-6mj4jpce, S-4cv3kd2v, S-6ca4b7bg, S-vhwb6zo5]
status: complete
---

# KRBTGT account password reset

## Summary
- Reset the KRBTGT password **twice**, waiting at least the domain's Kerberos ticket-lifetime policy (default 10 hours) between the two resets, so both entries in the account's 2-deep password history are replaced.
- Resetting KRBTGT invalidates every outstanding Kerberos TGT domain-wide; existing service tickets keep working until they are next used to reauthenticate, and NTLM is unaffected. Rebooting a computer is the only reliable way to force it to get a new TGT immediately.
- RODCs hold their own, separate `krbtgt_<number>` account and password; forest-recovery guidance says not to delete an RODC's krbtgt account, and the writable-DC reset procedure does not apply to it.
- Microsoft's `New-KrbtgtKeys.ps1` is referenced by Microsoft Incident Response as a scripted, repeatable way to reset KRBTGT and related keys while reducing Kerberos-issue risk; it is a community/GitHub script, not an in-box AD DS cmdlet.
- Microsoft Incident Response lists a double KRBTGT reset among the tactical containment steps for a ransomware/domain-compromise response, alongside isolating known-good domain controllers and disabling privileged accounts.
- Defender for Identity's security posture assessments flag any krbtgt account whose password was last set over 180 days ago, and recommend resetting it twice at least 10 hours apart to invalidate Golden Ticket attacks.
- Defender for Identity's classic alert catalog includes several "Suspected Golden Ticket usage" detections (ticket anomaly, ticket anomaly using RBCD, time anomaly, nonexistent account, encryption downgrade) that flag forged TGTs built from a stolen KRBTGT hash.

## Facts
- Reset the krbtgt password by opening Active Directory Users and Computers with Advanced Features on, then using Reset Password on the krbtgt user account in the domain's Users container; this procedure applies to writable DCs, not RODCs. [DOC S-4ikiakpi]
- "You should perform this operation twice. You must wait 10 hours between password resets," matching the default Maximum lifetime for user ticket / Maximum lifetime for service ticket policy; if that policy value is raised, the wait between resets must be greater than the configured value. [DOC S-4ikiakpi]
- The krbtgt account's password history holds 2 entries, so resetting the password twice clears any older password from history and stops another DC from replicating using a stale krbtgt password. [DOC S-4ikiakpi]
- A customized password filter (e.g. `passfilt.dll`) on a DC can cause an error when resetting the krbtgt password; Microsoft KB 2549833 documents a workaround. [DOC S-4ikiakpi]
- The KRBTGT account is a built-in, non-deletable, non-renameable, disabled-by-default service account for the KDC, created automatically with the domain; it is the security principal defined by RFC 4120 for the domain's Kerberos service. [DOC S-nl7th7fi]
- Resetting the KRBTGT password requires membership in Domain Admins (or delegated authority) plus membership in the local Administrators group (or delegated authority); after the reset, Kerberos Key-Distribution-Center event ID 9 should appear in the System event log. [DOC S-nl7th7fi]
- For all account types, all previously issued TGTs become invalid immediately after a KRBTGT reset because DCs reject tickets encrypted with the old key; already-established service-ticket sessions to a resource keep working until that service ticket must be renewed; NTLM-authenticated connections are not affected. [DOC S-nl7th7fi]
- Rebooting a computer is described as the only reliable way to recover functionality after a KRBTGT reset, because reboot forces both the computer and user accounts to sign in again and obtain new TGTs valid under the new KRBTGT key. [DOC S-nl7th7fi]
- An RODC advertises itself as the KDC for its branch office and signs/encrypts TGT requests using its own, separate KRBTGT account and password, distinct from the writable DCs' KRBTGT account. [DOC S-nl7th7fi]
- The forest-recovery procedure warns not to delete an RODC's krbtgt account (listed as `krbtgt_<number>`) when RODCs will also be recovered, and lists resetting the krbtgt password twice as one of the initial-recovery steps for the first restored writable DC, "because the krbtgt password history is two passwords." [DOC S-4ikiakpi]
- Microsoft Incident Response's ransomware containment steps include resetting the krbtgt password twice in rapid succession, and recommend the GitHub `New-KrbtgtKeys.ps1` script as "a scripted, repeatable process" to do this while minimizing Kerberos authentication issues; the krbtgt ticket lifetime can be shortened beforehand to shorten the required wait before the first reset, and every DC that will be kept online must be online during the process. [DOC S-4cv3kd2v]
- Defender for Identity's "Change password for krbtgt account" posture assessment lists any krbtgt account with a password set more than 180 days ago, and its remediation is to reset the password twice, "waiting at least 10 hours between resets," citing the same official forest-recovery procedure as the supported method. [DOC S-6mj4jpce]
- Defender for Identity's Golden Ticket description: an attacker with domain admin rights who compromises the KRBTGT account can forge a TGT that authorizes access to any resource with an arbitrary expiration ("Golden Ticket"), so closely monitoring and regularly changing the krbtgt password is presented as essential to mitigating this risk. [DOC S-6mj4jpce]
- Defender for Identity's classic alert list documents multiple Golden Ticket detections keyed off KRBTGT abuse: "Suspected Golden Ticket usage (ticket anomaly)" (external ID 2022 family), "(ticket anomaly using RBCD)" (ID 2040), "(nonexistent account)" (ID 2027), and "(encryption downgrade)" — all mapped to MITRE T1558.001 (Golden Ticket) under Persistence/Privilege Escalation/Lateral Movement. [DOC S-6ca4b7bg]
- The "(time anomaly)" Golden Ticket alert (formerly "Kerberos golden ticket") fires when a TGT is used for longer than the domain's Maximum lifetime for user ticket policy allows. [DOC S-6ca4b7bg]
- The `microsoft/New-KrbtgtKeys.ps1` GitHub repository (MIT) was archived on 2024-03-08 and is read-only: its maintainers state that development has ended and point to community forks; the archived version errors on offline domain controllers still registered in AD (remove them with ntdsutil first). The ransomware playbook still links it, so treat it as an unmaintained aid, not a supported tool. [DOC S-vhwb6zo5, S-4cv3kd2v]
- Microsoft gives no fixed routine interval: KRBTGT and trust account passwords should be changed "on a regular schedule, as you would with any privileged service account"; the only number is Defender for Identity's posture check, which flags a krbtgt password older than 180 days. [DOC S-nl7th7fi, S-6mj4jpce]

## Reference
| Step / control | Value | Source |
|---|---|---|
| Times to reset KRBTGT password | 2 (matches 2-entry password history) | S-4ikiakpi, S-6mj4jpce |
| Minimum wait between the two resets | 10 hours (= default Kerberos max ticket/service-ticket lifetime); longer if that policy is raised | S-4ikiakpi, S-6mj4jpce |
| KDC event logged after a reset | Event ID 9, source Kerberos Key-Distribution-Center, System log | S-nl7th7fi |
| Defender for Identity posture check | Flags krbtgt password last set > 180 days ago | S-6mj4jpce |
| RODC krbtgt account naming | `krbtgt_<number>`, separate account/password per RODC | S-4ikiakpi, S-nl7th7fi |
| Repeatable reset tooling | `New-KrbtgtKeys.ps1` (github.com/microsoft/New-KrbtgtKeys.ps1), referenced by MS Incident Response | S-4cv3kd2v |
| Golden Ticket MITRE mapping | T1558.001 (Steal or Forge Kerberos Tickets: Golden Ticket) | S-6ca4b7bg |

## Examples
- Manual reset path: ADUC with Advanced Features on -> domain container -> Users -> right-click **krbtgt** -> Reset Password -> any value in New/Confirm password (the account gets a strong system-generated password regardless of what is typed). [DOC S-4ikiakpi]
- Forest-recovery order for the first restored writable DC in domain `corp.example.com`: invalidate the RID pool, reset the DC's computer account password twice, then reset the krbtgt password twice before bringing the domain back into normal operation. [DOC S-4ikiakpi]
