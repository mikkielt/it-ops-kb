---
topic: auth/kerberos
priority: P0
applies_to: "Windows Server 2025 / Windows 11 24H2, ConfigMgr 2603, SQL Server 2022/2025"
retrieved_utc: 2026-09-27
sources: [S-7jumyiid, S1604, S-6m7klb4f, S1200, S-q5hl3fyg, S1205, S1213, S1214, S1215, S1216, S1217, S-5yckwasl, S-7bouxzdg, S-7bjorbzz, S-ffangyfp, S-6ca4b7bg]
status: complete
---

# Kerberos for workstation-CLI flows (AdminService, SQL)

## Summary
- `client` reaches AdminService and SQL as the engineer's own Kerberos identity (Negotiate); ConfigMgr 2603 (base 2509+) rejects NTLM on the AdminService, so a working SPN and Kerberos path is required, not optional. [DOC S-7jumyiid]
- A Python CLI can do the AdminService Negotiate (SPNEGO) step with `requests-gssapi`, which needs a Kerberos TGT already in the credential cache (`kinit`, or `KRB5CCNAME` pointing at a cache with a valid TGT) and does not obtain credentials itself; with NTLM rejected, a missing TGT or SPN fails the call rather than falling back. [DER S-7jumyiid, S1604: AdminService requires Kerberos + the library uses an existing TGT]
- RC4 in Kerberos has a firm, dated retirement: domain controllers change their `DefaultDomainSupportedEncTypes` default to AES-only (bitmask 0x18) starting with updates released on/after 2026-04-14, and the RC4 audit/compatibility path (`RC4DefaultDisablementPhase`) is retired in 2026-07. [DOC S1215]
- SQL Kerberos uses `MSSQLSvc/<fqdn>[:port]` SPNs registered on the service account; AdminService uses HTTP SPNs on the SMS Provider's computer/service account, resolved by IIS/HTTP.sys via Negotiate.
- **Protected Users** membership forces AES-only tickets, no NTLM, no delegation, and caps the TGT at 4 hours (240 min) with no renewal — compatible with the `client` design (Kerberos-only, no delegation) but breaks anything relying on ticket renewal beyond 4h or on NTLM fallback. [DOC S1205]
- The general Windows NTLM deprecation programme (audit → block) reinforces that Kerberos must be the primary path for such flows going forward. [DOC S1200]

## Facts
- Since ConfigMgr 2509, the AdminService rejects NTLM authentication outright; `AdminService.log` logs "Rejecting NTLM authentication" on an NTLM attempt. This is already recorded in `mecm/adminservice.md`. [DOC S-7jumyiid]
- A community forum post (2026-01-19) restates the 2509 change: the AdminService rejects NTLM and `AdminService.log` records "Rejecting NTLM authentication". [COMMUNITY S1213]
- By default Windows does not attempt Kerberos for a host named by an IP address and falls back to other enabled protocols such as NTLM; Kerberos for IP addresses needs the client `TryIPSPN` setting plus an SPN registered for the IP. [DOC S-5yckwasl]
- A missing or duplicate SPN makes the KDC return KDC_ERR_S_PRINCIPAL_UNKNOWN or KDC_ERR_PRINCIPAL_NOT_UNIQUE; an SPN specific to a service must be unique in the forest, while common service classes (such as the web service) map to the computer account's automatic HOST SPN. [DOC S-7bouxzdg]
- So callers that used to reach the AdminService by IP address, or with a missing or duplicate SPN, now fail instead of degrading to NTLM; the fix is the FQDN with one correct SPN, not re-enabling NTLM. Short-name access was not checked against a source. [DER S-7jumyiid, S-5yckwasl, S-7bouxzdg: 2509 NTLM rejection plus the documented fallback and SPN errors]
- Kerberoasting detection: event 4769 records the ticket encryption type (0x11 and 0x12 AES, 0x17 RC4-HMAC), and Microsoft advises monitoring for types other than 0x11 and 0x12. [DOC S-7bjorbzz] Microsoft also advises checking for one user requesting many service tickets for Kerberoasting-prone accounts in a short time, and Defender raises external ID 2410 for suspected Kerberos SPN exposure. [DOC S-ffangyfp, S-6ca4b7bg]
- The SMS Provider authentication level setting (Windows / certificate / Windows Hello for Business) applies to the AdminService too, as already recorded in `mecm/adminservice.md`. [DOC S-6m7klb4f]
- Protected Users group: members cannot authenticate with NTLM; Kerberos preauthentication cannot use DES or RC4, only AES; members cannot be delegated via unconstrained or constrained delegation; TGT lifetime is fixed at 4 hours with no renewal, and this cannot be overridden by domain policy. [DOC S1205]
- Protected Users also stops Kerberos caching the user's plaintext credentials or long-term keys after the initial TGT, and no cached verifier is created (no offline sign-in). [DOC S1205]
- So once the 4-hour TGT expires the session cannot silently get a new one: a flow expecting an unattended session longer than 4 hours without re-authentication fails. [DER S1205: no cached long-term keys + 240-minute non-renewable TGT]
- Microsoft's Windows NTLM deprecation programme: enhanced NTLM auditing is available now on Windows 11 24H2 and later and Windows Server 2025; in the second half of 2026 IAKerb and a local KDC (pre-release) remove common causes of NTLM fallback; network NTLM is disabled by default in the next major Windows Server release (undated), still re-enablable by policy. [DOC S1200]
- Separately, NTLMv1-derived SSO credentials are audited (Event ID 4024) from the September 2025 updates on Windows 11 24H2 clients and November 2025 on Windows Server 2025, and `BlockNtlmv1SSO` defaults to Enforce (1) from October 2026 where the value is not deployed. [DOC S-q5hl3fyg]
- Windows Server 2025 removes NTLMv1 and deprecates LANMAN and NTLMv2 (NTLMv2 still works but is to be removed in a future release; use Negotiate); it also deprecates RC4 in Kerberos and removes DES. [DOC S1214]
- RC4-in-Kerberos deprecation, dated: a KDC-side change tied to CVE-2026-20833 (KB5073381, original publish date 2026-01-13) alters how the KDC uses RC4 for **service-account** ticket issuance. Updates released on/after 2026-01-13 add KDCSVC audit events 201-209 in the System log and the temporary `RC4DefaultDisablementPhase` value (0 = no audit, no change; 1 = warning events, the phase 1 default; 2 = assume RC4 not enabled by default, the phase 2 default; restart required). Updates on/after 2026-04-14 start enforcement with manual rollback; updates released in or after July 2026 stop honouring the key. [DOC S1215]
- The domain-wide default (`DefaultDomainSupportedEncTypes`, DDSET) changes on updates released on/after 2026-04-14: for accounts with no explicit `msDS-SupportedEncryptionTypes`, the default becomes AES128-SHA1 + AES256-SHA1 only (bitmask 0x18), removing the RC4 fallback that domain controllers previously used. [DOC S1215]
- The audit-mode registry key (`RC4DefaultDisablementPhase`) loses support in updates released in or after July 2026, when enforcement is enabled on all domain controllers and the AES-only default becomes unconditional. [DOC S1215]
- The Windows Server blog frames the same change as updating the domain controllers' default assumed supported encryption types (for service accounts without explicit configuration) by mid-2026, notes AES-SHA1 has worked on all supported Windows versions since Windows Server 2008, and links the KB above for rollout dates. [DOC S1216]
- Microsoft's AskDS explainer (2026-01-26) confirms the same phases: January 2026 cumulative updates start removing RC4 from the KDC's assumed encryption types and add auditing; April 2026 updates enforce with rollback to audit possible; July 2026 updates behave the same but without rollback. It adds that, as of January 2026, there are no plans to remove RC4 from Windows, that System log events 201, 202, 206 and 207 flag at-risk interactions (4768/4769 alone do not), and that an explicitly set `DefaultDomainSupportedEncTypes` or an `msDS-SupportedEncryptionTypes` including RC4 avoids breakage; the author later replied there is no plan to remove the `DefaultDomainSupportedEncTypes` functionality. [DOC S1217]

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
- SPN check on the SMS Provider host: `setspn -L PL-SRV-0042$` shows the automatic `HOST/PL-SRV-0042.corp.example.com`, which covers HTTP when the site runs as the computer account; an explicit `HTTP/` SPN is needed only on a custom service account, and must then be unique in the forest.
- SQL SPN check: `setspn -L svc-sql-app` should show `MSSQLSvc/PL-SRV-0042.corp.example.com:1433`.
