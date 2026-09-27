---
topic: auth/transport-crypto
priority: P2
applies_to: "Windows Server 2025 / Windows 11 24H2, Microsoft Entra ID"
retrieved_utc: 2026-09-27
sources: [S1201, S1202, S1203, S1215, S1222, S1223, S1227, S-ipmyihvs, S1274, S-rrvvi6lx, S-furaoufn, S-btl752nc, S-ygq2kmmq, S-77zvblfr]
status: complete
---

# Transport crypto defaults touched by this research pass

## Summary
- Windows Server 2025 supports TLS 1.3 in Schannel with its own prioritized default cipher-suite list (distinct from Server 2022's); LDAP/SMB signing-and-encryption defaults are in `auth/ldap-smb-signing.md`.
- Kerberos moves to AES-only by default from 2026-04-14 (see `auth/kerberos.md`), removing RC4 as a session/ticket-encryption fallback.
- Entra's proof-of-possession direction is DPoP (RFC 9449) replacing the older Signed HTTP Request (SHR) mechanism; MSAL's PoP token support and Entra's Windows-Hello/PRT-based Token Protection are documented, but no Microsoft page states DPoP as generally available for Entra access tokens, and Entra's discovery document advertises mTLS-bound tokens but no DPoP algorithms. [DER S1223, S-btl752nc]
- Entra does not support RFC 8693 OAuth 2.0 Token Exchange as a grant type; it offers On-Behalf-Of (OBO) and client-credentials flows instead; a token-exchange grant request fails with `AADSTS70003` per a Microsoft Q&A accepted answer. [COMMUNITY S-ipmyihvs] No Microsoft product page lists a token-exchange grant for Entra (see Facts). [DER S-ygq2kmmq, S-btl752nc]

## Facts
- Windows Server 2025 and later has its own prioritized, enabled-by-default Schannel cipher-suite list, headed by the TLS 1.3 suites `TLS_AES_256_GCM_SHA384` and `TLS_AES_128_GCM_SHA256`; `SCH_USE_STRONG_CRYPTO` filters out RC4, DES, export and null suites. [DOC S1222]
- Schannel supports TLS 1.3 starting with Windows 11 and Windows Server 2022; Microsoft says enabling TLS 1.3 on earlier Windows versions is not a safe configuration. [DOC S-rrvvi6lx]
- LDAP channel binding and signing, and SMB client outbound signing/encryption defaults for Server 2025 / Windows 11 24H2, are as recorded in `auth/ldap-smb-signing.md`. [DOC S1201,S1202,S1203]
- Kerberos AES enctypes become the domain default (`DefaultDomainSupportedEncTypes` = 0x18, AES128-SHA1 + AES256-SHA1) for updates released on/after 2026-04-14, with RC4 fallback removed for accounts lacking an explicit `msDS-SupportedEncryptionTypes`; full detail and dates are in `auth/kerberos.md`. [DOC S1215]
- Microsoft Entra Token Protection is a Conditional Access session control that accepts only device-bound sign-in session tokens such as the PRT, which is cryptographically bound to the registered device; native apps are GA on Windows, iOS/iPadOS and macOS (browser apps for Azure Resource Manager in preview), it requires Microsoft Entra ID P1, and it is not a general DPoP-for-every-access-token mechanism. [DOC S1227, S1274]
- The MSAL.NET PoP page says Entra ID aims to support two PoP types, mTLS PoP (RFC 8705, service-to-service) and DPoP (RFC 9449, public clients); the older Signed HTTP Request (SHR) PoP is being phased out and replaced with DPoP; public-client PoP goes through the WAM broker and is available on Windows 10+/Server 2019+. [DOC S1223]
- Microsoft Identity Web says mTLS PoP (token binding) is in private preview, so not every client may obtain mTLS PoP certificates. [DOC S-furaoufn]
- Entra's v2.0 discovery document advertises `tls_client_certificate_bound_access_tokens: true` with an mTLS token endpoint alias, and publishes no `dpop_signing_alg_values_supported`. [DOC S-btl752nc]
- So DPoP (RFC 9449) has no GA statement for general Entra ID access tokens outside the MSAL PoP and Token Protection scenarios: the MSAL page states only an aim, and the discovery document advertises no DPoP support. [DER S1223, S-btl752nc: stated aim plus absent discovery metadata]
- The Entra Agent ID protocols page lists the grant types supported for agent applications (blueprints and agent identities) as `client_credentials`, `jwt-bearer` (client credentials and on-behalf-of) and `refresh_token`, with no RFC 8693 token-exchange grant; this covers agent applications only, not every Entra app; the discovery document publishes no `grant_types_supported`. [DOC S-ygq2kmmq, S-btl752nc]
- So no Microsoft product page documents RFC 8693 token exchange as an Entra token-endpoint grant; the only explicit denial is the Microsoft Q&A answer above. [DER S-ygq2kmmq, S-btl752nc, S-ipmyihvs: absence in product docs plus the COMMUNITY answer]
- SMB 3.1.1 uses AES-128-GCM by default (older dialects AES-128-CCM); AES-256-CCM and AES-256-GCM are available from Windows Server 2022 and Windows 11; Windows negotiates the most advanced cipher both sides support, and Group Policy can mandate one. [DOC S-77zvblfr]

## Reference
| Mechanism | Status (this session's sources) | Tag |
|---|---|---|
| TLS 1.3 in Schannel, Server 2025 | Supported, own default cipher list | DOC |
| Kerberos AES-only domain default | 2026-04-14 (updates), full detail in kerberos.md | DOC |
| Entra Token Protection (PRT binding) | Documented, requires Entra ID P1, Windows sign-in sessions | DOC |
| MSAL PoP / DPoP (RFC 9449) for public clients | Documented as MSAL's PoP mechanism, replacing SHR | DOC |
| DPoP GA for general Entra access tokens | No GA statement; discovery document advertises mTLS binding, not DPoP | DER |
| RFC 8693 Token Exchange in Entra | Not among documented grant types; only a Q&A answer denies it | DER |
| SMB 3.1.1 default cipher | AES-128-GCM (AES-256 from Server 2022 / Windows 11) | DOC |

## Examples
(none — this is a reference-only topic file)
