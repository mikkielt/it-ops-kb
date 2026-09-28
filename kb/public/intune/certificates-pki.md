---
topic: intune/certificates-pki
priority: P2
applies_to: "Microsoft Intune service 2026-09, Certificate Connector for Microsoft Intune, Microsoft Cloud PKI (Intune Suite/standalone add-on)"
retrieved_utc: 2026-09-27
sources: [S-h44fxget, S-lcamnncm, S-hxbyw5pm, S-qe32ky2d, S-6fwniw6n, S-weleekge, S-4txttdx2, S-7war6bpq, S-wlkxstj4, S-hv24mjpy, S1224]
status: complete
files: [intune/certificate-variables.csv]
---

# Intune certificates and PKI: SCEP, PKCS, Cloud PKI, and the certificate connector

## Summary
Intune deploys client certificates for Wi-Fi, VPN, 802.1X, and app/email authentication through three
certificate-profile mechanisms: **SCEP** (device requests its own key pair; needs on-prem NDES + the
**Certificate Connector for Microsoft Intune**, or the newer **Microsoft Cloud PKI** SCEP service), **PKCS**
(the connector generates the key pair on-prem and delivers a PFX; also needs an Enterprise CA + the connector), and
**imported PFX** (pre-generated certificates uploaded and pushed per user, covered in `imported-pfx-profiles`, not
detailed here). Every SCEP/PKCS profile references a **trusted certificate profile** that provisions the root/issuing
CA certificate first. KB5014754 (see `auth/enterprise-access-model.md`) requires certificates used for KDC
authentication to carry a **strong-mapping SID** in the SAN — Intune adds this via the `OnPremisesSecurityIdentifier`
variable (SCEP) or a certificate-connector registry flag (PKCS). Microsoft Cloud PKI is an Intune Suite/add-on
service that replaces the on-prem CA, NDES, and connector with a cloud-hosted two-tier PKI and SCEP registration
authority.

## Facts
### SCEP certificate profiles
- Create path: **Devices > Manage devices > Configuration > Create**, platform, profile type **SCEP certificate**; the device must also receive the trusted certificate profile that provisions the Trusted Root CA (the SCEP profile references it as **Root Certificate**), and Microsoft recommends deploying both profiles to the same groups. [DOC S-h44fxget]
- **Certificate type**: **User** (subject/SAN may hold user or device attributes) or **Device** (device attributes only; used for user-less devices/kiosks and for Windows, where the certificate lands in the Local Computer store). [DOC S-h44fxget]
- **Subject name format** (User): free text with variables `{{UserName}}`, `{{UserPrincipalName}}`, `{{AAD_Device_ID}}`, `{{DeviceId}}` (avoid on Windows — can break Intune sync), `{{SERIALNUMBER}}`, `{{IMEINumber}}`, `{{OnPrem_Distinguished_Name}}` (needs `onpremisesdistinguishedname` synced via Entra Connect; quote the CN if it contains a comma), `{{OnPremisesSamAccountName}}` (needs `onPremisesSamAccountName` synced), plus `E={{EmailAddress}}`; static text and OU/O/L/ST/C strings can be combined, e.g. `CN={{UserName}},E={{EmailAddress}},OU=Mobile,O=Finance Group,L=Redmond,ST=Washington,C=US`. [DOC S-h44fxget]
- **Subject name format** (Device): variables `{{AAD_Device_ID}}`/`{{AzureADDeviceId}}`, `{{DeviceId}}`, `{{Device_Serial}}`, `{{Device_IMEI}}`, `{{SerialNumber}}`, `{{IMEINumber}}`, `{{WiFiMacAddress}}`, `{{IMEI}}`, `{{DeviceName}}`, `{{FullyQualifiedDomainName}}` (Windows/domain-joined only), `{{MEID}}`; a device missing a referenced attribute (e.g. no IMEI) fails profile install. [DOC S-h44fxget]
- **Subject alternative name (SAN)** attributes: Email address, User principal name (UPN), DNS, URI; the certificate type determines which SAN variables are usable, and Android's *Fully Managed/Dedicated/Corporate-Owned Work Profile* SCEP profiles don't support `{{UserName}}` in the SAN. [DOC S-h44fxget]
- **KB5014754 strong mapping**: add `{{OnPremisesSecurityIdentifier}}` to the SAN's **URI** attribute; Intune resolves it and appends `tag:microsoft.com,2022-09-14:sid:<value>` to the SAN. Supported in user certificates (Windows, iOS, macOS) and in device certificates only for Microsoft Entra hybrid-joined Windows devices; requires users/devices synced from on-prem AD to Entra ID. Cross-reference `auth/enterprise-access-model.md:14` (Full Enforcement 2025-02-11) and `auth/windows-hello-for-business.md` (certificate trust also needs strongly-mapped certs). [DOC S1224, S-h44fxget]
- Third-party/non-Microsoft CAs must support the `tag:microsoft.com,...:sid:` URI format in the SAN or certificate issuance can fail; Microsoft AD CS servers patched with KB5014754 support it natively. [DOC S-weleekge]
- **Certificate validity period**: up to 24 months, and must be lower than both the certificate template's validity and the issuing CA certificate's remaining validity; recommended minimum 5 days (shorter risks the cert expiring or being near-expiry before the MDM agent installs it). [DOC S-h44fxget]
- **Renewal threshold (%)**: percentage of lifetime remaining when the device requests renewal — e.g. 20 triggers renewal at 80% expired; retried until successful; renewal always generates a new key pair. On iOS/iPadOS and macOS, renewal only happens inside the threshold window and only while the device is unlocked during sync; a missed renewal leaves the expired cert on the device with no further retry or redeploy option (must exclude the device from the profile to clear it, then reassign). [DOC S-h44fxget]
- **Key storage provider (KSP)** (Windows only): *Enroll to TPM KSP if present, otherwise Software KSP*; *Enroll to TPM KSP, otherwise fail*; *Enroll to Windows Hello for Business, otherwise fail*; *Enroll to Software KSP*. [DOC S-h44fxget]
- **Key size**: 1024, 2048, 4096 (Windows, Android, iOS 14+, macOS 11+); on Windows, 4096-bit keys are supported only by the **Software KSP** — the hardware TPM and Windows Hello for Business KSPs don't support that size (no workaround for WHfB). [DOC S-h44fxget]
- **SCEP Server URLs**: one or more NDES URLs (e.g. `https://ndes.contoso.com/certsrv/mscep/mscep.dll`); HTTPS is required for Android device administrator, Android Enterprise device owner, corporate-owned work profile and personally owned work profile. A device makes three separate NDES calls per request (capabilities, public key, signing request); with multiple load-balanced URLs, if a different backend answers a later call in the same request the request fails. Windows and Android randomize and try the URL list in order; iOS/iPadOS gets a single randomized URL from Intune and fails if it's unreachable. [DOC S-h44fxget]
- Known CSR-encoding issue: an escaped special character (`+ , ; =`) in the subject name (preceded by `\`) produces an incorrect CSR and the SCEP challenge validation fails with no certificate issued; work around by quoting the whole CN value or removing the character (not by escaping it). [DOC S-h44fxget]
- Subject name >64 characters may need **Disable DN Length Enforcement** on the internal CA. [DOC S-h44fxget]
- Android Enterprise **Fully Managed/Dedicated/Corporate-Owned Work Profile** SCEP profiles: no certificate reporting under Monitoring, and Intune can't revoke certificates they issued (must be revoked externally or at the CA); on Android Enterprise dedicated devices they're supported for Wi-Fi/VPN/authentication but not app authentication. Android (AOSP) SCEP profiles: no certificate reporting, no Intune revocation, Wi-Fi only (no VPN yet), and `onPremisesSamAccountName`/`OnPrem_Distinguished_Name`/`Department` variables aren't yet available. [DOC S-h44fxget]
- Beginning Android 12, personally-owned work-profile devices no longer report Serial number, IMEI, or MEID; a SCEP/PKCS profile that keys the subject/SAN on those variables fails to provision on such devices enrolled after the Android 12 upgrade (devices enrolled pre-upgrade keep working if Intune already had the identifiers). [DOC S-h44fxget]
- **S/MIME baseline requirement (from 2025-07-16)**: CA/Browser Forum requires sponsor-validated S/MIME certificates to include Given Name and Surname in the subject; add `G={{GivenName}}` and `SN={{SurName}}` to the SCEP profile's subject name format for third-party public CA S/MIME scenarios, or the public CA rejects new/renewed requests. Editing the profile to add these triggers reissuance of all certificates (possible CA cost impact); Intune does not update existing profiles automatically. [DOC S-h44fxget]
- SCEP certificate storage: macOS places SCEP certs in the system keychain unless the user deployment channel is selected; Android always stores SCEP certs in the VPN-and-apps store (also copied to the Wi-Fi store when linked to a Wi-Fi profile); Windows Device-type certificates go to the Local Computer store. [DOC S-h44fxget]

### PKCS certificate profiles
- Infrastructure: AD-domain-joined Enterprise CA (not Standalone), the exported CA root certificate, and the **Certificate Connector for Microsoft Intune**. Unlike SCEP, the private key is generated **on the connector server**, not on the device; the certificate template must allow **private key export**, and after delivery the key is marked non-exportable on the device. [DOC S-qe32ky2d]
- Certificate template setup on the CA: Compatibility = CA "Windows Server 2008 R2" / recipient "Windows 7 / Server 2008 R2"; Subject Name = **Supply in the request**; Application Policies must include Encrypting File System, Secure Email, Client Authentication (iOS/iPadOS templates also need "Signature is proof of origin" deselected under Key Usage); grant the connector server's computer account **Read**+**Enroll** on the template and **Issue and Manage Certificates**+**Request Certificates** on the CA. [DOC S-qe32ky2d]
- **Renewal threshold (%)**: recommended value **20%**; **Certificate validity period**: 5 days to 24 months (same near-expiry-rejection risk as SCEP). [DOC S-qe32ky2d]
- Subject name/SAN variable set mirrors SCEP (`{{UserName}}`, `{{UserPrincipalName}}`, `{{AAD_Device_ID}}`, `{{DeviceId}}`, `{{SERIALNUMBER}}`, `{{IMEINumber}}`, `{{OnPrem_Distinguished_Name}}`, `{{onPremisesSamAccountName}}`, device variables `{{Device_Serial}}`, `{{Device_IMEI}}`, `{{WiFiMacAddress}}`, `{{AzureADDeviceId}}`, `{{DeviceName}}`, `{{FullyQualifiedDomainName}}`, `{{MEID}}`); the same escaped-special-character CSR issue applies. [DOC S-qe32ky2d]
- **KB5014754 strong mapping for PKCS**: requires certificate connector **6.2406.0.1001** or later, plus a registry change on the connector server — `HKLM\Software\Microsoft\MicrosoftIntune\PFXCertificateConnector` DWORD `EnableSidSecurityExtension` = **1** — then restart the **PFX Create Legacy Connector** and **PFX Create Certificate Connector** services; applies to new and renewed PKCS certificates; rollback restores the registry value, restarts the same services, and requires reissuing a fresh PKCS profile without the SID attribute. DigiCert CAs need separate templates for users with vs. without the SID attribute. [DOC S-qe32ky2d]
- Android Enterprise PKCS-deployed certificates are not visible on the device; confirm delivery via the Intune admin center profile status instead. [DOC S-qe32ky2d]
- macOS-only **Allow all apps access to private key** setting (`AllowAllAppsAccess` in Apple's Certificate Payload) grants every configured app access to the PKCS certificate's private key. [DOC S-qe32ky2d]

### Certificate Connector for Microsoft Intune
- Beginning 2021-07-29 it replaces the separate *PFX Certificate Connector* and *Microsoft Intune Connector*; with the release of version 6.2109.51.0 those legacy connectors are no longer supported. [DOC S-hxbyw5pm]
- Capabilities per instance (chosen at install): PKCS #12 requests, PKCS imported (PFX) certificates, SCEP issuance (with a Microsoft CA, requires NDES on the same server), certificate revocation. SCEP against a **third-party** CA does not require the connector. [DOC S-hxbyw5pm]
- Up to **100 connector instances** per tenant, one per Windows Server; Intune routes each certificate request type only to instances that support it; instances should share the same version and, for PKCS, the same permissions/CA connectivity since routing to a specific instance isn't controllable. The connector must not be installed on the same server as the issuing CA or as the Intune Connector for Active Directory. [DOC S-hxbyw5pm, S-6fwniw6n]
- General prerequisites: **Windows Server 2012 R2+**, **.NET 4.7.2**, **TLS 1.2** enabled, Enhanced Security Configuration disabled, outbound access to `autoupdate.msappproxy.net:443` for auto-update, and the same network endpoints as an Intune-managed device. [DOC S-6fwniw6n]
- SCEP-specific prerequisites: **IIS 7+**; Server Roles **AD CS** + **Web Server (IIS)**; Features **.NET Framework 4.7 (ASP.NET 4.7, WCF HTTP Activation)** and **.NET Framework 3.5 + HTTP Activation** (for NDES); AD CS Role Service **Network Device Enrollment Service**; IIS Role Services **Request Filtering**, **.NET Extensibility 4.7**, **ASP.NET 4.7**, **IIS Management Console**, **IIS 6 Metabase/WMI Compatibility**. The CA must be an **Enterprise CA** on Windows Server 2008 R2 SP1+ (Standalone unsupported) and stay in Microsoft support; 2008 R2 SP1 CAs need KB2483564. [DOC S-6fwniw6n, S-weleekge]
- Connector service account: **SYSTEM** or a domain user that is a local admin on the connector server; needs Logon as Service, **Issue and Manage Certificates** on the CA (revocation only), **Read**+**Enroll** on every certificate template used, and access to the Key Storage Provider used by PFX Import. The Microsoft Entra account used to configure the connector needs the **Intune Administrator** role and an Intune license. The NDES application-pool account needs Read+Enroll on SCEP templates and membership in **IIS_IUSRS**. [DOC S-6fwniw6n]
- NDES server-authentication certificate SAN must list every FQDN NDES responds to (internal and, unless behind Entra application proxy, external); bound to IIS Default Web Site on port 443. [DOC S-weleekge]
- **Connector lifecycle**: each release is supported for **6 months**, keeps functioning (unsupported) for **18 months** after release, then may stop communicating with Intune. Status shows **Warning** for a deprecated connector during the 6-month grace period and **Error** after. [DOC S-hxbyw5pm]
- Connectors older than **6.2101.13.0** were deprecated (April 2022, status Error), lost revocation (August 2022) and issuance (September 2022); this covers both the PFX Certificate Connector and the Microsoft Intune Connector, which the Certificate Connector for Microsoft Intune replaced on 2021-07-29 (the note sits in the page's "What's new for the Certificate Connector" section, confirmed 2026-09-27). [DOC S-hxbyw5pm]
- **Allowed SCEP OIDs** (from connector version **6.2510.3.2002**, "SCEP validation service"): only `2.5.29.19` Basic Constraints, `2.5.29.14` Subject Key Identifier, `1.3.6.1.4.1.311.21.8` CA Version, `1.3.6.1.4.1.311.20.2` Certificate Template Name, `2.5.29.1` Authority Identifier (deprecated), `2.5.29.3` Certificate Policies (deprecated), `2.16.840.1.113730.1.11` Netscape Certificate Extension are allowed; unknown extensions are blocked. [DOC S-hxbyw5pm]
- Logging: **Event Viewer > Applications and Services Logs > Microsoft > Intune > Certificate Connectors**, with an **Admin log** (one event per request) and an **Operational log** (more detail, ongoing operations), each defaulting to 50 MB with auto-archive; debug logging can be enabled per log. Event ID ranges: 0001-0999 general, 1000-1999 PKCS, 2000-2999 PKCS Import, 3000-3999 Revoke, 4000-4999 SCEP, 5000-5999 Connector Health. Selected SCEP events: 4003 request received, 4004/4005 verify success/failure, 4006/4007 issue success/failure, 4008/4009 notify success/attempt-failed. [DOC S-hxbyw5pm]
- Diagnostic codes returned by the connector (`troubleshoot-certificate-connector-events`): `0x00000400` CA unavailable/unreachable; `0x00000402` RevokeCert access denied; `0x00000403`/`0x00000404` certificate not found (re-enroll connector); `0x00000405` certificate expired (re-enroll connector); `0x00000408` CRP SCEP encryption cert not found; `0x00000409` CRP SCEP signing cert not found; `0x00000410` SCEP challenge deserialize failed; `0x00000411` SCEP challenge expired (client retries with a new challenge); `0x0FFFFFFFF` unknown server-side error. [DOC S-hv24mjpy]

### Microsoft Cloud PKI (Intune Suite / standalone add-on)
- Cloud-hosted two-tier PKI: replaces on-prem CA, NDES, and the certificate connector entirely — Cloud PKI runs its own SCEP registration authority (**SCEP service** + **SCEP validation service**) that requests certificates from the Cloud PKI issuing CA on behalf of Intune-enrolled devices. [DOC S-lcamnncm]
- Licensing: requires Intune Plan 1 or Plan 2 **plus** a Cloud PKI subscription (Intune Suite, or the standalone Cloud PKI add-on); available in **GCC High**, not available in **DoD**; a data-residency option is not currently available for Cloud PKI. [DOC S-lcamnncm]
- Supported device platforms: Android, iOS/iPadOS, macOS, Windows — any platform supporting the Intune SCEP certificate profile. [DOC S-lcamnncm]
- Cloud PKI RBAC permissions (assignable to custom Intune roles): **Read CAs**, **Create certificate authorities**, **Revoke issued leaf certificates** (also needs Read CAs); scope tags can be applied to root/issuing CAs. [DOC S-lcamnncm]
- Cryptography: signing/encryption algorithm **RSA** with key sizes **2048/3072/4096**; hash algorithms **SHA-256/384/512**; production CAs use **Azure Managed HSM**-backed keys (no separate Azure subscription needed); CAs created during an Intune Suite/Cloud PKI **trial** use software-backed keys (`System.Security.Cryptography.RSA`) and can't later convert to HSM-backed keys even after purchase. [DOC S-lcamnncm]
- CRL: Intune hosts the CRL distribution point per CA; CRL validity is **7 days**, publish/refresh cadence **every 3.5 days**, plus an update on every revocation. AIA endpoints are also hosted by Intune per issuing CA. [DOC S-lcamnncm]
- Tenant CA capacity: **up to 3 CAs** total (Root CA, Issuing CA, and BYOCA Issuing CA all count toward the limit) — same 3-CA cap during a trial. [DOC S-lcamnncm]
- **Bring your own CA (BYOCA)**: anchors a Cloud PKI issuing CA to an existing private/on-prem CA (AD CS or non-Microsoft), supporting external N+1 hierarchies; coexists with Intune-managed two-tier root/issuing CAs (e.g. one root + two issuing, or one root + one issuing + one BYOCA). [DOC S-lcamnncm, S-wlkxstj4]
- Issuing-CA creation (Intune-managed): choose CA type **Issuing CA**, Root CA source **Intune**, pick an existing Intune root CA to anchor to; **Validity period** 2/4/6/8/10 years (can't be longer than the root CA's; a custom period needs Microsoft Graph); **Extended Key Usages** must be specific purposes — **Any Purpose (2.5.29.37.0)** is blocked as overly permissive. [DOC S-7war6bpq]
- **CA renewal**: eligible once a CA reaches half its validity lifetime (or has expired); renewing creates a **staged CA** with a **temporary staged SCEP URI**, usable to validate issuance (up to **50 test certificates**) before cutover; the staged CA is available for up to **90 days**, then goes inactive with an additional **30-day grace period** before deletion (HSM resources reclaimed). **Activate** promotes the staged CA, retires the old version, disables the staged URI, and restores the original production SCEP URI (existing SCEP profiles need no update). Renewal notification banners fire at half-life, 6 months, 90 days, and 30 days before expiration. [DOC S-4txttdx2]
- CA status values: **Active**, **Expired**, **Revoked**, **Paused**, **Signing required** (BYOCA renewal awaiting a signed CSR); renewal states include **Staged**. [DOC S-4txttdx2]
- Reporting: a Cloud PKI dashboard shows active/expired/revoked leaf certificates per CA, refreshed every **24 hours**; admin actions (create, revoke, search) are audited. [DOC S-lcamnncm]

## Reference
- `auth/enterprise-access-model.md` — KB5014754 timeline and Full Enforcement date (2025-02-11); this article's strong-mapping SAN/URI variable is the Intune-side implementation of that KDC requirement. Back-link added there is not required per that article's scope, but the enforcement date and mode transitions are the shared fact.
- `auth/windows-hello-for-business.md` — certificate trust requires an enterprise PKI/CRA and issues authentication certificates whose strong mapping follows the same KB5014754 rules as SCEP/PKCS profiles here.
- `intune/configuration-policies.md` — Wi-Fi/VPN/802.1X profiles that consume these certificates are configured as separate device-configuration profiles; both are delivered on the same policy check-in/refresh cadence described there.
- `intune/network-profiles.md` — Windows Wi-Fi (Enterprise EAP-TLS/PEAP), wired 802.1X, and VPN (VPNv2 CSP) profiles that reference the SCEP/PKCS certificate profiles documented here as their client/root certificate source.
- `intune/macos-management.md` and `intune/ios-android-management.md` — ACME as an alternative to SCEP for the ADE/DEP management-profile certificate specifically (not for user/Wi-Fi/VPN certificates, which still use SCEP/PKCS as documented here).
- `intune/export-report-names.csv` — `CertificatesByRAPolicy` report (Devices > Monitor > Certificates) surfaces certificates issued by a specific PKCS/SCEP (RA) policy.
- Not covered in this pass (`UNK`): imported PFX certificate profile field-by-field configuration (see `imported-pfx-profiles` on Microsoft Learn), DigiCert/other third-party public CA SCEP partner-specific SAN mapping tables beyond the general OID allow-list, and Graph `deviceManagementConfigurationPolicy`/certificate-profile REST bodies.

## Examples
- SNIPPET: SCEP profile device certificate SAN with the KB5014754 strong-mapping URI attribute; context: SCEP certificate profile, Windows/iOS/macOS, hybrid-joined device synced from on-prem AD; checked: no [DOC S-h44fxget]
```
# SCEP profile: device certificate SAN with KB5014754 strong mapping (URI attribute)
Subject name format (Device): CN={{DeviceName}}
Subject alternative name:
  Attribute: URI
  Value: {{OnPremisesSecurityIdentifier}}
# Intune appends: tag:microsoft.com,2022-09-14:sid:<resolved SID>
```

- SNIPPET: SCEP profile NDES server URLs for load-balanced issuance; context: SCEP certificate profile Server URLs field, NDES bound to IIS Default Web Site port 443; checked: no [DOC S-weleekge]
```
# SCEP profile: NDES server URLs for load-balanced issuance
SCEP Server URLs:
  https://ndes1.corp.example.com/certsrv/mscep/mscep.dll
  https://ndes2.corp.example.com/certsrv/mscep/mscep.dll
```

- SNIPPET: PKCS connector strong-mapping registry change, run on the connector server, then restart services; context: Certificate Connector for Microsoft Intune 6.2406.0.1001+; checked: no [DOC S-qe32ky2d]
```
# PKCS connector strong-mapping registry change (run on the connector server, then restart services)
reg add "HKLM\Software\Microsoft\MicrosoftIntune\PFXCertificateConnector" /v EnableSidSecurityExtension /t REG_DWORD /d 1 /f
# Restart services: "PFX Create Legacy Connector for Microsoft Intune", "PFX Create Certificate Connector for Microsoft Intune"
```

```
# Example device PL-LT-00123 enrolled in tenant 00000000-0000-0000-0000-000000000000:
# a SCEP profile using {{AAD_Device_ID}} in the subject and {{OnPremisesSecurityIdentifier}}
# in the SAN URI attribute fails to strongly map unless the device is Microsoft Entra
# hybrid-joined and its SID has synced from on-premises AD (jan.kowalski's UPN-based user
# cert has no such restriction).
```
