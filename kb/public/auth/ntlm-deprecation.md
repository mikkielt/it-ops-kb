---
topic: auth/ntlm-deprecation
priority: P0
applies_to: "Windows 11 24H2/25H2, Windows Server 2025"
retrieved_utc: 2026-09-28
sources: [S1200, S-q5hl3fyg, S1214, S1215, S1216, S1217, S-wg5cdpjs]
status: complete
---

# NTLM deprecation timeline and RC4-in-Kerberos

## Summary
- Microsoft is retiring NTLM in three phases: enhanced NTLM auditing (available now) → features that remove common NTLM fallbacks (second half of 2026) → network NTLM disabled by default in the next major Windows Server release and its associated client releases; Microsoft says the timelines may change. [DOC S1200]
- Separately, NTLMv1-derived Single Sign-On credentials move from audit to block by default in October 2026 (`BlockNtlmv1SSO`). [DOC S-q5hl3fyg]
- A Kerberos-only design is unaffected in principle, but every flow must have a working SPN/Negotiate path before NTLM stops being a silent fallback.

## Facts
- Enhanced NTLM auditing (phase one) is available now on Windows Server 2025 and Windows 11 version 24H2 and later, to find where and why NTLM is still used. [DOC S1200]
- KB5066470 audits NTLMv1-derived credentials used for Single Sign-On (not every NTLM use): in Audit mode, Event ID 4024 (Warning) is written to `Microsoft-Windows-NTLM/Operational` and authentication still succeeds; in Enforce mode the request is blocked with Event ID 4025 (Error). Rollout: Windows 11 24H2 and later clients with the September 2025 and later updates (timeline row: late August 2025), Windows Server 2025 from November 2025. [DOC S-q5hl3fyg]
- Phase two (second half of 2026, for Windows Server 2025 and Windows 11 24H2 and later) brings IAKerb and a local KDC (both pre-release) for cases with no line of sight to a DC and for local accounts, and moves core Windows components that hardcode NTLM to negotiate Kerberos first. [DOC S1200]
- In October 2026 a Windows update changes the default of the `BlockNtlmv1SSO` value (REG_DWORD under `HKLM\SYSTEM\CurrentControlSet\Control\Lsa\MSV1_0`) from 0 (Audit) to 1 (Enforce), blocking NTLMv1-derived SSO credentials (e.g. MS-CHAPv2 Wi-Fi/VPN SSO); the new default applies only where the value has not been deployed, and not on devices with Credential Guard enabled. Dates are tentative. [DOC S-q5hl3fyg]
- The older NTLMv1 control is `LMCompatibilityLevel` under `HKLM\System\CurrentControlSet\Control\LSA`, levels 0 to 5: at level 5 clients send only NTLMv2 and domain controllers refuse LM and NTLM (accept only NTLMv2); levels 0 to 3 leave domain controllers accepting LM, NTLM and NTLMv2. [DOC S-wg5cdpjs]
- Phase three disables network NTLM by default in the next major Windows Server release and associated client releases (no date given); NTLM remains present in the OS and can be re-enabled through new policy controls. [DOC S1200]
- The Windows Server removed/deprecated features page (Windows Server 2025 tab) lists NTLMv1 as removed and LANMAN and NTLMv2 as deprecated (NTLMv2 keeps working until removal in a future release), tells callers to replace NTLM with Negotiate, and says the list is subject to change, so re-check it before hardening `site`/`ci` hosts. [DOC S1214]
- RC4-in-Kerberos deprecation is dated, in three steps (see `auth/kerberos.md` for the full detail and reference table): a KDC-side change for service-account ticket issuance tied to CVE-2026-20833 (updates on/after 2026-01-13, KB5073381, phased via `RC4DefaultDisablementPhase`; key no longer honoured from the July 2026 updates); `DefaultDomainSupportedEncTypes` defaults to AES-only (0x18) on updates released on/after 2026-04-14; the audit-mode registry key is removed in the 2026-07 update, making AES-only unconditional. [DOC S1215,S1216,S1217]

## Reference
| Phase | Date/build | Effect |
|---|---|---|
| NTLM auditing | Available now (Server 2025, Win 11 24H2+) | Enhanced NTLM auditing, no blocking |
| NTLMv1-derived SSO audit | Sep 2025 updates (24H2 clients), Nov 2025 (Server 2025) | Event ID 4024 on NTLMv1-derived SSO credential use |
| NTLMv1-derived SSO blocked by default | Oct 2026 | `BlockNtlmv1SSO` default flips to Enforce (Event ID 4025) |
| Fallback-reduction features | H2 2026 | IAKerb, Local KDC, Kerberos-first core components |
| Network NTLM off by default | Next major Windows Server release, undated | NTLM stays present, policy re-enable possible |

## Examples
- Watch Event ID 4024 in `Microsoft-Windows-NTLM/Operational` on `PL-LT-00123` and `PL-SRV-0042` to find NTLMv1-derived SSO use before the Oct 2026 enforce default; use enhanced NTLM auditing for NTLM use in general.
