---
topic: auth/transport-crypto
priority: P2
applies_to: "Windows Server 2025 / Windows 11 24H2, Microsoft Entra ID"
retrieved_utc: 2026-09-26
sources: [S1201, S1202, S1203, S1215, S1222, S1223, S1227, S-ipmyihvs, S1274]
status: partial
---

# Transport crypto defaults touched by this research pass

## Summary
- Windows Server 2025 supports TLS 1.3 in Schannel with its own prioritized default cipher-suite list (distinct from Server 2022's); LDAP/SMB signing-and-encryption defaults are in `auth/ldap-smb-signing.md`.
- Kerberos moves to AES-only by default from 2026-04-14 (see `auth/kerberos.md`), removing RC4 as a session/ticket-encryption fallback.
- Entra's proof-of-possession direction is DPoP (RFC 9449) replacing the older Signed HTTP Request (SHR) mechanism; MSAL's PoP token support and Entra's Windows-Hello/PRT-based Token Protection are documented, but DPoP's general-availability status specifically for Entra access tokens (beyond MSAL PoP/Token Protection) was not confirmed as GA this session.
- Entra does not support RFC 8693 OAuth 2.0 Token Exchange as a grant type; it offers On-Behalf-Of (OBO) and client-credentials flows instead; a token-exchange grant request fails with `AADSTS70003` per a Microsoft Q&A accepted answer. [COMMUNITY S-ipmyihvs]

## Facts
- Windows Server 2025 and later has its own prioritized, enabled-by-default Schannel cipher-suite list, headed by the TLS 1.3 suites `TLS_AES_256_GCM_SHA384` and `TLS_AES_128_GCM_SHA256`; `SCH_USE_STRONG_CRYPTO` filters out RC4, DES, export and null suites. [DOC S1222]
- TLS 1.3 support was introduced in Windows with Windows 11/Server 2022 and carried into Server 2025. [UNK: not in S1222 as re-read 2026-09-27]
- LDAP channel binding and signing, and SMB client outbound signing/encryption defaults for Server 2025 / Windows 11 24H2, are as recorded in `auth/ldap-smb-signing.md`. [DOC S1201,S1202,S1203]
- Kerberos AES enctypes become the domain default (`DefaultDomainSupportedEncTypes` = 0x18, AES128-SHA1 + AES256-SHA1) for updates released on/after 2026-04-14, with RC4 fallback removed for accounts lacking an explicit `msDS-SupportedEncryptionTypes`; full detail and dates are in `auth/kerberos.md`. [DOC S1215]
- Microsoft Entra Token Protection is a Conditional Access session control that accepts only device-bound sign-in session tokens such as the PRT, which is cryptographically bound to the registered device; native apps are GA on Windows, iOS/iPadOS and macOS (browser apps for Azure Resource Manager in preview), it requires Microsoft Entra ID P1, and it is not a general DPoP-for-every-access-token mechanism. [DOC S1227, S1274]
- The MSAL.NET PoP page says Entra ID aims to support two PoP types, mTLS PoP (RFC 8705, service-to-service) and DPoP (RFC 9449, public clients); the older Signed HTTP Request (SHR) PoP is being phased out and replaced with DPoP; public-client PoP goes through the WAM broker and is available on Windows 10+/Server 2019+. [DOC S1223]
- Whether DPoP/RFC 9449 is GA (vs. preview) for general Entra ID access tokens issued to a confidential/public client outside the specific MSAL PoP and Windows Token Protection scenarios documented above: [UNK] — not confirmed from an official Microsoft source this session.
- RFC 8693 (OAuth 2.0 Token Exchange) support in Entra ID as a token-endpoint grant type: no official Microsoft statement was found either confirming or denying support this session; community sources describe Entra as not supporting the RFC 8693 grant type directly and instead offering On-Behalf-Of (OBO) and client-credentials flows (re-searched 2026-09-26 on Microsoft Learn: still only a Microsoft Q&A answer, no product page). [UNK: no official Microsoft statement]
- SMB 3.1.1 cipher details beyond the signing/encryption defaults already in `auth/ldap-smb-signing.md` (e.g. AES-128-GCM vs AES-256-GCM negotiation specifics): [UNK] — not separately researched this session.

## Reference
| Mechanism | Status (this session's sources) | Tag |
|---|---|---|
| TLS 1.3 in Schannel, Server 2025 | Supported, own default cipher list | DOC |
| Kerberos AES-only domain default | 2026-04-14 (updates), full detail in kerberos.md | DOC |
| Entra Token Protection (PRT binding) | Documented, requires Entra ID P1, Windows sign-in sessions | DOC |
| MSAL PoP / DPoP (RFC 9449) for public clients | Documented as MSAL's PoP mechanism, replacing SHR | DOC |
| DPoP GA for general Entra access tokens | Unconfirmed | UNK |
| RFC 8693 Token Exchange in Entra | No official confirmation either way found | UNK |

## Examples
(none — this is a reference-only topic file)
