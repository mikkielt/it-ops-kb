---
topic: auth/kerberos
priority: P0
applies_to: "Windows Server 2025 / Windows 11 24H2, ConfigMgr 2603, SQL Server 2022/2025"
retrieved_utc: 2026-09-24
sources: [S-7jumyiid, S1604, S-6m7klb4f, S1200, S1205, S1213, S1215, S1216, S1217]
status: partial
---

# Kerberos for workstation-CLI flows (AdminService, SQL)

## Summary
- `client` reaches AdminService and SQL as the engineer's own Kerberos identity (Negotiate); ConfigMgr 2603 (base 2509+) rejects NTLM on the AdminService, so a working SPN and Kerberos path is required, not optional. [DOC S-7jumyiid]
- A Python CLI can do the AdminService Negotiate (SPNEGO) step with `requests-gssapi`, which needs a Kerberos TGT already in the credential cache (`kinit`, or `KRB5CCNAME` pointing at a cache with a valid TGT) and does not obtain credentials itself; with NTLM rejected, a missing TGT or SPN fails the call rather than falling back. [DER S-7jumyiid, S1604: AdminService requires Kerberos + the library uses an existing TGT]
- RC4 in Kerberos has a firm, dated retirement: domain controllers change their `DefaultDomainSupportedEncTypes` default to AES-only (bitmask 0x18) starting with updates released on/after 2026-04-14, and the RC4 audit/compatibility path (`RC4DefaultDisablementPhase`) is retired in 2026-07. [DOC S1216]
- SQL Kerberos uses `MSSQLSvc/<fqdn>[:port]` SPNs registered on the service account; AdminService uses HTTP SPNs on the SMS Provider's computer/service account, resolved by IIS/HTTP.sys via Negotiate.
- **Protected Users** membership forces AES-only tickets, no NTLM, no delegation, and caps the TGT at 4 hours (240 min) with no renewal — compatible with the `client` design (Kerberos-only, no delegation) but breaks anything relying on ticket renewal beyond 4h or on NTLM fallback. [DOC S1205]
- The general Windows NTLM deprecation programme (audit → block) reinforces that Kerberos must be the primary path for such flows going forward. [DOC S1200]

## Facts
- Since ConfigMgr 2509, the AdminService rejects NTLM authentication outright; `AdminService.log` logs "Rejecting NTLM authentication" on an NTLM attempt. This is already recorded in `mecm/adminservice.md`. [DOC S-7jumyiid]
- A community forum thread reports that after the 2509 change, clients that previously fell back to NTLM (e.g. because of a missing/duplicate SPN, or access by IP/short name instead of FQDN) start failing outright instead of degrading; the fix is to ensure the FQDN is used and the SPN is registered, not a workaround for NTLM. [COMMUNITY S1213]
- The SMS Provider authentication level setting (Windows / certificate / Windows Hello for Business) applies to the AdminService too, as already recorded in `mecm/adminservice.md`. [DOC S-6m7klb4f]
- Protected Users group: members cannot authenticate with NTLM; Kerberos preauthentication cannot use DES or RC4, only AES; members cannot be delegated via unconstrained or constrained delegation; TGT lifetime is fixed at 4 hours with no renewal, and this cannot be overridden by domain policy. [DOC S1205]
- Protected Users also disables credential caching (no long-term keys cached after the initial TGT), so a 4-hour-old session that needs a fresh service ticket still works (service tickets are requested against the TGT while it is valid), but any flow expecting an 8+ hour unattended session without re-authentication will fail once the TGT expires. [DOC S1205]
- Microsoft's Windows NTLM deprecation programme: Windows 11 24H2 and Windows Server 2025 get enhanced NTLM auditing (Event ID 4024) starting with updates from around September 2025; a later phase changes `BlockNTLMv1SSO` default from Audit (0) to Enforce (1) in October 2026, disabling NTLMv1 by default; a further phase (H2 2026) adds IAKerb and a local KDC to remove common causes of NTLM fallback; full network-NTLM-off-by-default is a later, undated release. [DOC S1200]
- `removed-deprecated-features-windows-server-2025` tracks NTLM-adjacent removals per release; check per current Windows Server 2025 build before relying on any specific NTLM behaviour. [DOC S1214]
- RC4-in-Kerberos deprecation, dated: a KDC-side change tied to CVE-2026-20833 (KB5073381, original publish date 2026-01-13) alters how the KDC uses RC4 for **service-account** ticket issuance. Updates released on/after 2026-01-13 add KDCSVC audit events 201-209 in the System log and the temporary `RC4DefaultDisablementPhase` value (0 = no audit, no change; 1 = warning events, the phase 1 default; 2 = assume RC4 not enabled by default, the phase 2 default; restart required). Updates on/after 2026-04-14 start enforcement with manual rollback; updates released in or after July 2026 stop honouring the key. [DOC S1215]
- The domain-wide default (`DefaultDomainSupportedEncTypes`, DDSET) changes on updates released on/after 2026-04-14: for accounts with no explicit `msDS-SupportedEncryptionTypes`, the default becomes AES128-SHA1 + AES256-SHA1 only (bitmask 0x18), removing the RC4 fallback that domain controllers previously used. [DOC S1216]
- The audit-mode registry key (`RC4DefaultDisablementPhase`) is planned for removal in the 2026-07 update, after which the AES-only default is unconditional. [DOC S1216]
- Microsoft's own explainer of the RC4-in-Kerberos change (rationale: RC4 is the basis of Kerberoasting) confirms the same phased approach without adding new dates beyond S1216. [DOC S1217]

## Reference
- `auth/windows-hello-for-business.md` — WHfB deployment models and trust types (cloud Kerberos, key, certificate) that use Kerberos to reach on-premises AD; the Protected Users and RC4/NTLM deprecation facts above also apply to accounts signing in with WHfB.

| Protected Users effect | Detail | Breaks a Kerberos-only client? |
|---|---|---|
| No NTLM | Kerberos/Negotiate only | No — client design already assumes Kerberos-only |
| AES-only tickets | No RC4/DES | No — AES is already the target state; see `auth/ntlm-deprecation.md` for RC4-in-Kerberos deprecation |
| No delegation | Unconstrained/constrained delegation blocked | No — design has no delegation for `client` (only a possible future broker component needs delegation, and that instance would not be in Protected Users) |
| 4h TGT, no renewal | Re-authentication needed every 4h | Possible — a long engineer session (all-day) needs a new logon or re-auth every 4h; confirms QA3 answer below |

| RC4-in-Kerberos milestone | Date | Effect |
|---|---|---|
| KDC RC4 change for service-account tickets (CVE-2026-20833, KB5073381) | Updates on/after 2026-01-13 | Audit events KDCSVC 201-209; phased audit→enforce via `RC4DefaultDisablementPhase` |
| `DefaultDomainSupportedEncTypes` defaults to AES-only (0x18) | Updates on/after 2026-04-14 | No RC4 fallback for accounts without an explicit `msDS-SupportedEncryptionTypes` |
| `RC4DefaultDisablementPhase` audit key removed | 2026-07 update | AES-only becomes unconditional |

## Examples
- SPN check on the SMS Provider host: `setspn -L PL-SRV-0042$` should show `HTTP/PL-SRV-0042.corp.example.com`.
- SQL SPN check: `setspn -L svc-sql-app` should show `MSSQLSvc/PL-SRV-0042.corp.example.com:1433`.
