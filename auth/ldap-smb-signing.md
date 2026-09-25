---
topic: auth/ldap-smb-signing
priority: P0
applies_to: "Windows Server 2025, Windows 11 24H2, ldap3 2.10.x"
retrieved_utc: 2026-09-24
sources: [S1228, S1201, S1202, S1203, S1208, S1209, S1220, S1221]
status: partial
---

# LDAP/SMB signing and channel-binding defaults; Python LDAP + Kerberos

## Summary
- Windows Server 2025 raises defaults: new AD deployments require LDAP signing by default, LDAP channel binding defaults to "when supported", and outbound SMB signing becomes required by default on Windows 11 24H2 (Enterprise/Pro/Education) and Windows Server 2025; SMB encryption stays optional. [DOC S1201,S1202,S1228]
- This affects `site` reading AD via LDAP and `ci`/devices reading the package SMB share: both must support Kerberos-signed LDAP and signed SMB, with no fallback to unsigned. [DER S1201,S1202]
- Python: `ldap3`'s GSSAPI/Kerberos SASL bind does not implement SASL security layers (signing/sealing) itself — if the DC enforces LDAP signing on the *transport* (not just the bind), `ldap3` can still complete a Kerberos bind over LDAPS or with channel binding, but cannot provide its own encrypt/sign wrapper for the LDAP protocol layer. [DOC S1208, COMMUNITY S1209]

## Facts
- Windows Server 2025 new AD forests/domains enable "Domain controller: LDAP server signing requirements" enforcement by default; existing upgraded domains keep prior settings unless changed. [DOC S1201]
- LDAP channel binding on Server 2025 defaults to "When supported" (accept CBT when the client offers it) with auditing of unsigned/uncorrelated binds enabled by default. [DOC S1201]
- SMB signing: Windows 11 24H2 Enterprise, Pro and Education require outbound and inbound SMB signing by default; Windows Server 2025 requires outbound signing only; 24H2 Home requires neither. [DOC S1202]
- SMB encryption: SMB encryption is not mandatory by default. Windows 11 24H2 / Server 2025 add a client option to mandate encryption for all outbound connections; once enabled, the client connects only to SMB 3.0+ servers that support encryption. [DOC S1228]
- `ldap3`'s Kerberos SASL mechanism uses the `gssapi` (or `winkerberos` on Windows) package; it supports **authentication** via GSSAPI/Kerberos and channel binding (via a `ChannelBinding` computed from the peer TLS certificate over LDAPS), but the library raises an error if the server's SASL negotiation requires a security layer (sign/seal) that `ldap3` does not implement — `ldap3` only supports GSSAPI for authentication, not for wrapping subsequent LDAP messages. [DOC S1208, COMMUNITY S1209]
- For a `site`-kind instance using `ldap3`, the only transport protection available against a DC that requires signing is LDAPS (TLS), with Kerberos/GSSAPI used for the bind; `ldap3` cannot supply LDAP-layer sign/seal. [DER S1201,S1208]
- `python-ldap`'s documented SASL support (`ldap.sasl` module) provides a `sasl_gssapi_bind_s()` convenience method for GSSAPI/Kerberos binds; because `python-ldap` is a thin ctypes/C wrapper over the platform's native LDAP/SASL libraries (OpenLDAP + Cyrus SASL on Linux; on Windows it links against the Windows SDK's `wldap32`/SSPI rather than Cyrus SASL), its ability to negotiate a true SASL security layer (signing/sealing) on a plain `ldap://` connection depends on the underlying platform library's GSSAPI/SSPI SASL implementation, not on `python-ldap` itself — the official `python-ldap` documentation describes the Python-level API only, and does not state whether the Windows build negotiates sign/seal. [DOC S1220]
- Microsoft's ADSI documentation for the Windows-native option (usable from Python via `pywin32`'s COM bindings to `ADsOpenObject`/`IADsOpenDSObject::OpenDSObject`) is explicit: `ADS_USE_SIGNING` (0x40) requires `ADS_SECURE_AUTHENTICATION` and verifies data integrity; `ADS_USE_SEALING` (0x80) also requires `ADS_SECURE_AUTHENTICATION`, encrypts data, and automatically implies signing; both require Kerberos authentication, which in turn requires the calling machine to be logged on to a Windows domain (or one trusted by it). [DOC S1221]
- This makes the pywin32/ADSI route the one **Microsoft-documented** Python-reachable path (via COM) with confirmed sign+seal support on Windows, at the cost of being Windows-only and COM-based rather than pure Python — acceptable only if the calling instance is Windows-only by design. [DER S1221]
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
