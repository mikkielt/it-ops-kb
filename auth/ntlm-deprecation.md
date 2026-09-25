---
topic: auth/ntlm-deprecation
priority: P0
applies_to: "Windows 11 24H2/25H2, Windows Server 2025"
retrieved_utc: 2026-09-24
sources: [S1200, S1214, S1215, S1216, S1217]
status: complete
---

# NTLM deprecation timeline and RC4-in-Kerberos

## Summary
- Microsoft is retiring NTLM in phases: audit → NTLMv1 disabled by default (Oct 2026) → NTLM-fallback-reducing features (H2 2026) → network NTLM off by default (undated future release). [DOC S1200]
- A Kerberos-only design is unaffected in principle, but every flow must have a working SPN/Negotiate path before NTLM stops being a silent fallback.

## Facts
- Windows 11 version 24H2 (and later builds) get enhanced NTLM auditing, logging Event ID 4024 when NTLM is used, with rollout beginning around September 2025; Windows Server 2025 rollout of the same auditing follows around November 2025. [DOC S1200]
- Phase two (second half of 2026) introduces IAKerb and a Local KDC, intended to remove common causes of NTLM fallback (e.g. no line of sight to a DC). [DOC S1200]
- In October 2026, Microsoft changes the default of the `BlockNTLMv1SSO` registry value from 0 (Audit) to 1 (Enforce), which disables NTLMv1 authentication by default. [DOC S1200]
- Phase three disables network NTLM by default in a future release (undated); NTLM remains present in the OS and can be re-enabled by policy. [DOC S1200]
- `removed-deprecated-features-windows-server-2025` is the per-release tracking page for exact NTLM-adjacent removals/changes; it should be re-checked against the current Windows Server 2025 build before the sprint that hardens `site`/`ci` hosts. [DOC S1214]
- RC4-in-Kerberos deprecation is dated, in three steps (see `auth/kerberos.md` for the full detail and reference table): a KDC-side change for service-account ticket issuance tied to CVE-2026-20833 (Nov 2025 update, phased via `RC4DefaultDisablementPhase`); `DefaultDomainSupportedEncTypes` defaults to AES-only (0x18) on updates released on/after 2026-04-14; the audit-mode registry key is removed in the 2026-07 update, making AES-only unconditional. [DOC S1215,S1216,S1217]

## Reference
| Phase | Date/build | Effect |
|---|---|---|
| NTLM auditing | Sep 2025 (24H2), Nov 2025 (Server 2025) | Event ID 4024 logged on NTLM use, no blocking |
| NTLMv1 disabled by default | Oct 2026 | `BlockNTLMv1SSO` default flips to Enforce |
| Fallback-reduction features | H2 2026 | IAKerb, Local KDC |
| Network NTLM off by default | Future, undated | NTLM stays present, policy re-enable possible |

## Examples
- Watch Event ID 4024 on `PL-LT-00123` and `PL-SRV-0042` to confirm no flow is silently using NTLM before Oct 2026.
