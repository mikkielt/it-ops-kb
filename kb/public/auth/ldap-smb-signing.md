---
topic: auth/ldap-smb-signing
priority: P0
applies_to: "Windows Server 2025, Windows 11 24H2, ldap3 2.10.x"
retrieved_utc: 2026-09-27
sources: [S1228, S1201, S1202, S1203, S1208, S1209, S1220, S1221, S-7u4b7p5q, S-tcoyec5r]
status: partial
---

# LDAP/SMB signing and channel-binding defaults; Python LDAP + Kerberos

## Summary
- Windows Server 2025 raises defaults: new AD deployments require LDAP signing by default, LDAP channel binding defaults to "when supported", and outbound SMB signing becomes required by default on Windows 11 24H2 (Enterprise/Pro/Education) and Windows Server 2025; SMB encryption stays optional. [DOC S1201,S1202,S1228]
- This affects `site` reading AD via LDAP and `ci`/devices reading the package SMB share: both must support Kerberos-signed LDAP and signed SMB, with no fallback to unsigned. [DER S1201,S1202]
- Python: the stable `ldap3` release (2.9.1) uses Kerberos (GSSAPI) SASL for authentication only and fails when the server demands a SASL security layer, so against a DC that requires signing it needs LDAPS; the current `ldap3` documentation (2.10.2, still a pre-release on PyPI) adds a Kerberos data security layer for encryption, enabled with `session_security=ENCRYPT`. [DOC S1208, S-7u4b7p5q; COMMUNITY S1209]

## Facts
- Windows Server 2025 new AD forests/domains enable "Domain controller: LDAP server signing requirements" enforcement by default; existing upgraded domains keep prior settings unless changed. [DOC S1201]
- LDAP channel binding on Server 2025 defaults to "When supported" (accept CBT when the client offers it), channel binding auditing is enabled by default, and LDAP client encryption is "preferred" by default. [DOC S1201]
- SMB signing: Windows 11 24H2 Enterprise, Pro and Education require outbound and inbound SMB signing by default; Windows Server 2025 requires outbound signing only; 24H2 Home requires neither. [DOC S1202]
- Before Windows 11 24H2 / Server 2025, SMB signing was required by default only for connections to the SYSVOL and NETLOGON shares, and domain controllers required it of their clients. The same releases let the SMB client block NTLM for outbound connections (with per-server exceptions) and make the SMB server wait 2 seconds after each failed NTLM or local KDC Kerberos authentication by default. [DOC S1203]
- SMB encryption: SMB encryption is not mandatory by default. Windows 11 24H2 / Server 2025 add a client option to mandate encryption for all outbound connections; once enabled, the client connects only to SMB 3.0+ servers that support encryption. [DOC S1228]
- `ldap3`'s Kerberos SASL mechanism needs the `gssapi` package (docs page 2.10.2). In the stable 2.9.1 line it authenticates only: a server that requires a sign or seal layer makes the bind fail (the 2019 issue: "ldap3 does not support any security layers"). The 2.10.2 docs say ldap3 now supports SASL data security layers for encryption; a server that requires a strong SSF needs `session_security=ENCRYPT` on the `Connection`. On PyPI, 2.9.1 (2021-07-18) is still the latest stable release and 2.10.2 exists only as release candidates (rc4, 2026-04-18). [DOC S1208, S-7u4b7p5q; COMMUNITY S1209]
- For a `site`-kind instance on the stable `ldap3` 2.9.1, the only transport protection available against a DC that requires signing is LDAPS (TLS), with Kerberos/GSSAPI used for the bind; LDAP-layer sealing over plain `ldap://` needs the 2.10.2 pre-release with `session_security=ENCRYPT`, which is not yet a stable release. [DER S1201,S1208,S-7u4b7p5q: DC signing requirement + ldap3 docs + PyPI release status]
- `python-ldap`'s `ldap.sasl` reference (3.3.0 docs) lists a `gssapi` class for SASL GSSAPI (Kerberos V) binds and points to the convenience method `sasl_gssapi_bind_s()`; the page documents the Python-level API only and says nothing about SASL security layers (signing/sealing) or about how Windows builds negotiate them. [DOC S1220]
- `python-ldap` is a wrapper over the platform's native LDAP/SASL client libraries, so whether a GSSAPI bind on plain `ldap://` negotiates sign/seal depends on that underlying library, not on the Python API. [UNK: not stated on S1220; lab check below]
- ADSI Kerberos encryption: binding with `ADsOpenObject` or `IADsOpenDSObject::OpenDSObject` and the `ADS_USE_SEALING` flag encrypts LDAP traffic and automatically sets `ADS_USE_SIGNING`; both flags need Kerberos, which works only when the client computer is logged on to the domain (or a trusted one) and the call passes null credentials (no alternate credentials). [DOC S1221]
- In `ADS_AUTHENTICATION_ENUM`, `ADS_USE_SIGNING` is 0x40 (verifies data integrity) and `ADS_USE_SEALING` is 0x80 (encrypts with Kerberos); each requires `ADS_SECURE_AUTHENTICATION` (0x1) as well. [DOC S-tcoyec5r]
- So on Windows the ADSI route (secure authentication + signing + sealing, running as the service's own identity) is a Microsoft-documented way to get a Kerberos-signed and sealed LDAP bind, at the cost of being Windows-only and COM-based rather than pure Python. [DER S1221,S-tcoyec5r: sealing implies signing + flag requirements]
- Reaching `ADsOpenObject` from Python through `pywin32`'s COM bindings is not described in these Microsoft pages. [UNK: not in S1221 as re-read 2026-09-27]
- `python-ldap` on Windows and its sign/seal behaviour against a signing-enforced DC over plain LDAP: still not independently confirmed; recorded as a lab check. [UNK]

## Reference
| Setting | Server 2025 default | Effect |
|---|---|---|
| LDAP server signing requirement | Required (new domains) | `site`→AD LDAP must sign/use LDAPS |
| LDAP channel binding | When supported | CBT sent when client offers it (TLS transport) |
| SMB client outbound signing | Required (24H2 Ent/Pro/Edu: outbound + inbound; Server 2025: outbound) | `ci`/device→SMB artifact share must sign |
| SMB client outbound encryption | Not required by default (client mandate available) | only if the mandate or share encryption is enabled |

## Examples
- `site` LDAP bind target: `ldaps://PL-SRV-0042.corp.example.com:636` with Kerberos SASL via `ldap3`, not plain `ldap://`.

Verification: on an isolated Windows host against a Server 2025 DC with LDAP signing enforced, attempt (a) an `ldap3` GSSAPI bind over plain `ldap://`, (b) a `python-ldap` `sasl_gssapi_bind_s()` bind over plain `ldap://`, and (c) a `pywin32` `ADsOpenObject` bind with `ADS_USE_SIGNING|ADS_USE_SEALING` → proves which of the three actually negotiates a security layer against an enforcing DC.
