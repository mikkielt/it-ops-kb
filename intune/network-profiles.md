---
topic: intune/network-profiles
priority: P2
applies_to: "Microsoft Intune service 2026-09, Windows 10/11 device configuration profiles (Wi-Fi, wired network, VPN), Microsoft Tunnel, Microsoft Entra Private Access"
retrieved_utc: 2026-09-26
sources: [S-t6z76jtq, S-qftwfatf, S-pp7wx433, S-j3m2icav, S-2ne6yzmx, S-qbkbk5wb, S-y3enttcg, S-sq5keqpx, S-3xdtjgi4, S-kdhgvxwh, S-lkrznc4c, S-aprlzyvz]
status: partial
---

# Intune network profiles: Wi-Fi, wired 802.1X, VPN, Microsoft Tunnel, and Entra Private Access

## Summary
Intune configures three built-in Windows network profile types under **Devices > Configuration > Create > Templates**:
**Wi-Fi** (Basic/personal WPA-PSK, or Enterprise EAP), **Wired network** (802.1X port authentication via the
**WiredNetwork CSP**), and **VPN** (native Windows protocols or third-party VPN client apps via the **VPNv2 CSP**).
Enterprise Wi-Fi, wired, and VPN certificate-based auth all reuse the SCEP/PKCS certificate profiles documented in
`intune/certificates-pki.md`. VPN profiles support device tunnel (always-connected, machine-cert IKEv2), per-app VPN,
split/force tunneling, and trusted network detection. **Microsoft Tunnel** is a separate Linux-container VPN gateway
for iOS/iPadOS and Android Enterprise only (not Windows). **Microsoft Entra Private Access** (part of Global Secure
Access) is the Zero Trust successor Microsoft points customers toward for VPN replacement on Windows and other
platforms, using per-app or "Quick Access" broad-segment tunneling instead of a classic VPN profile.

## Facts
### Wi-Fi profiles (Windows)
- Profile types: **Basic** (WPA/WPA2-Personal with an optional pre-shared key, 8-63 ASCII chars or 64 hex chars; the same PSK is shared by every device the profile targets) and **Enterprise** (EAP-based); settings use the **Wi-Fi CSP**. [DOC S-pp7wx433]
- Common fields on both types: **Wi-Fi name (SSID)**, **Connection name** (user-facing), **Connect automatically when in range**, **Connect to more preferred network if available**, **Connect even when SSID isn't broadcast (hidden network)**, **Metered Connection Limit** (Unrestricted default / Fixed / Variable). [DOC S-pp7wx433]
- Enterprise **Authentication mode**: Not configured (default: User or machine), **User**, **Machine**, **User or machine**, **Guest** (no credentials; open or externally handled auth). [DOC S-pp7wx433]
- Enterprise timers/limits: **Authentication period** 1-3600s (default 18s), **Authentication retry delay** 1-3600s (default 1s), **Start period** (EAPOL-Start delay) 1-3600s (default 5s), **Maximum EAPOL-start** 1-100 messages (default 3), **Maximum authentication failures** 1-100 (default 1). [DOC S-pp7wx433]
- **Single sign-on (SSO)**: Disable / Enable before user signs into device / Enable after user signs into device, plus **Maximum time to authenticate before timeout** (1-120s) and an option to allow Windows to prompt for additional credentials. [DOC S-pp7wx433]
- **PMK caching**: enable/disable; **Maximum time a PMK is stored in cache** 5-1440 minutes, **Maximum number of PMKs stored in cache** 1-255, **Enable pre-authentication** (re-authenticate to every in-range access point ahead of time) with **Maximum pre-authentication attempts** 1-16. [DOC S-pp7wx433]
- **EAP type** options: EAP-SIM, **EAP-TLS** (cert server names, root cert for server validation, auth method SCEP/PKCS certificate/derived credential), **EAP-TTLS** and **Protected EAP (PEAP)** (both add Username+Password with inner method PAP/CHAP/MS-CHAP/MS-CHAPv2, identity privacy/outer identity, or SCEP/PKCS certificate/derived credential); PEAP adds **Perform server validation**, **Disable user prompts for server validation**, and **Require cryptographic binding**. [DOC S-pp7wx433]
- **Force Wi-Fi profile to be FIPS 140-2 compliant**: Yes/No, required for US federal agencies using cryptography-based security systems. [DOC S-pp7wx433]
- Company proxy settings: None, manual (server IP + port), or automatic (PAC script URL). [DOC S-pp7wx433]
- Settings not exposed by the Wi-Fi template can be imported: export an XML from another Windows device's Wi-Fi settings and import it as the profile (`import-wifi-settings-windows`). [DOC S-pp7wx433]

### Wired network (802.1X) profiles (Windows)
- Platform: Windows only for the Windows-specific reference (macOS and iOS/iPadOS also supported by the Wired network template generally); uses the **WiredNetwork CSP**; create via **Templates > Wired network**. [DOC S-j3m2icav, S-2ne6yzmx]
- **Authentication mode**: same options as Wi-Fi (Not configured/User/Machine/User or machine/Guest). [DOC S-j3m2icav]
- Timers/limits identical defaults to Wi-Fi Enterprise: Authentication period default 18s, retry delay default 1s, start period default 5s, Maximum EAPOL-start default 3, Maximum authentication failures default 1, **Block period (minutes)** 0-1440 after a failed attempt. [DOC S-j3m2icav]
- **802.1x** setting: **Enforce** (Wired AutoConfig service requires 802.1X port authentication) or **Do not enforce** (default); misconfiguring Enforce against a network that doesn't match blocks all internet access on the device (no way to re-pull policy — must manually remove the profile). [DOC S-j3m2icav]
- **EAP type**: EAP-SIM, **EAP-TLS**, **EAP-TTLS**, **Protected EAP (PEAP)** (same sub-options as Wi-Fi, plus **PFX Import certificate** as a client-auth option, absent from the Wi-Fi Enterprise list), and **Tunnel EAP (TEAP)** — TEAP adds a **Primary authentication method** (user auth: Username/Password, SCEP, PKCS, derived credential) and a **Secondary authentication method** (machine auth, same options, default Not configured); if the primary fails and no secondary is configured, authentication fails outright. [DOC S-j3m2icav]
- Tip: deploy the wired network profile, the certificate profile, and the trusted root certificate profile to the same assignment groups so every device recognizes the CA. [DOC S-2ne6yzmx]

### VPN profiles (Windows) — VPNv2 CSP
- Settings use the **VPNv2 CSP** (`./User|Device/Vendor/MSFT/VPNv2/{ProfileName}`, profile name must not contain `/`; nodes include `AlwaysOn`, `AlwaysOnActive`, `IPv4InterfaceMetric`, `IPv6InterfaceMetric`, `EdpModeId`); create a device configuration profile, platform Windows 10/holographic, profile type **VPN** (or **Templates > VPN**); the available settings depend on the chosen **Connection type**. [DOC S-t6z76jtq, S-qftwfatf, S-qbkbk5wb]
- **Connection types** for Windows: Check Point Capsule VPN, Cisco AnyConnect, Citrix SSO, F5 Access, Palo Alto Networks GlobalProtect, Pulse Secure, SonicWall Mobile Connect, **Automatic (Native)**, **IKEv2 (Native)**, **L2TP (Native)**, **PPTP (Native)**. Microsoft Tunnel is **not** a Windows connection type — Windows isn't a supported platform for Microsoft Tunnel. [DOC S-qftwfatf, S-t6z76jtq, S-3xdtjgi4]
- **User scope vs. device scope**: user-scope profiles install per signed-in account (unavailable to other users on the device); device-scope profiles apply to all users. New VPN profiles default to user scope, **except** profiles with **Device tunnel** enabled, which always use device scope; Windows Holographic devices support device scope only. [DOC S-t6z76jtq]
- **Always On**: automatically connects at sign-in, on network change, and on screen wake; required to be **Enable** for device-tunnel connections. [DOC S-t6z76jtq]
- **Device tunnel** (IKEv2 only): connects automatically with no user sign-in, for Microsoft Entra-joined devices; requires Connection type = IKEv2, Always On = Enable, Authentication method = Machine certificates; **only one device-tunnel profile may be assigned per device**. [DOC S-t6z76jtq]
- **Authentication method** options: Certificates (user client cert profile — enables per-app VPN and on-demand), Username and password, Derived credential (Windows VPN support for this is currently broken — no ETA), EAP (IKEv2 only, cert profile + EAP XML), Machine certificates (IKEv2 only, required for device tunnel). PKCS **imported certificate** profiles are not supported for VPN auth; PKCS **certificate** (connector-issued) profiles are. [DOC S-t6z76jtq, S-qftwfatf]
- **IKE Security Association Parameters** (phase 1: encryption algorithm, integrity check algorithm, Diffie-Hellman group) and **Child Security Association Parameters** (phase 2: cipher transform, authentication transform, PFS group) apply to IKEv2 only and must match the VPN server; **Windows 11 requires configuring either all of both parameter groups, or none of them** — partially configuring causes loss of VPN functionality. [DOC S-t6z76jtq]
- **Per-app VPN**: under Apps and Traffic Rules, associate a WIP domain or specific apps with the connection; **Restrict VPN connection to these apps** = Enable makes it a true per-app VPN (traffic rules auto-generated); app identifiers are package family name (universal apps, e.g. `Microsoft.Office.OneNote_8wekyb3d8bbwe`, found via `Get-AppxPackage`) or full file path (desktop apps, e.g. `%windir%\system32\notepad.exe`); import via CSV. [DOC S-t6z76jtq]
- **Network traffic rules**: per rule set Name, Rule type (None/Split tunnel/Force tunnel — applies only when the rule is app-associated), Direction (Inbound or Outbound, default Outbound — need two rules for both), Protocol (0-255, e.g. 6=TCP, 17=UDP), Local/Remote port ranges (TCP/UDP only), Local/Remote IPv4 address ranges; recommended to always add a least-restrictive catch-all rule. If no traffic rule is defined, all protocols/ports/addresses are allowed on that VPN connection. [DOC S-t6z76jtq]
- **Split tunneling**: Enable lets the device route only VPN-destined traffic over the tunnel and everything else over the normal network path; **Split tunneling routes** add destination-prefix routes for third-party VPN providers. VPN **proxy settings** (PAC/WPAD or server+port) apply only to Force Tunnel connections — Split Tunnel connections use the device's general proxy settings. [DOC S-t6z76jtq, S-y3enttcg]
- **Trusted Network Detection**: list of trusted DNS suffixes; while connected to a trusted-suffix network, the VPN doesn't auto-trigger even from Always On, app-based triggers, or DNS auto-triggers; configured via `VPNv2/<ProfileName>/TrustedNetworkDetection`. Users who manually uncheck "Connect automatically" have their preference remembered in `HKLM\SYSTEM\CurrentControlSet\Services\RasMan\Config\AutoTriggerDisabledProfilesList` (REG_MULTI_SZ) so a re-pushed AlwaysOn=true profile doesn't silently re-enable it. [DOC S-t6z76jtq, S-sq5keqpx]
- **DNS settings**: DNS suffix search list (ordered, drag to reorder) and **NRPT rules** (per-domain DNS server, proxy, Automatically connect, Persistent — Persistent rules survive VPN disconnect; non-persistent are removed on disconnect). [DOC S-t6z76jtq]
- **Conditional Access for this VPN connection**: the VPN client gets a short-lived certificate from Microsoft Entra ID for device-compliance-gated connections; requires certificate-based VPN auth and a VPN server that trusts the Entra-issued certificate; optional alternate SSO certificate (name/OID/issuer hash) for Kerberos. [DOC S-t6z76jtq]
- **Custom XML / EAP XML** fields allow vendor-specific ProfileXML blobs (Pulse Secure, F5 Edge, SonicWALL, CheckPoint examples documented) for settings not exposed by the UI; ProfileXML can also be delivered wholesale via a custom OMA-URI profile at `./user/vendor/MSFT/VPNv2/<ProfileName>/ProfileXML` with data type String (XML file). [DOC S-t6z76jtq, S-y3enttcg]
- **Known Windows 11 issue**: a device with one or more Intune VPN profiles can lose VPN connectivity when multiple VPN profile changes are processed simultaneously (editing an existing profile, two new profiles landing at once, or a removal + new assignment at once); recovers automatically on the device's next Intune check-in. Doesn't affect a device receiving its first VPN profile with none previously assigned, or an additional profile with no changes to existing ones. [DOC S-qftwfatf]
- Windows 10 reached end of support 2025-10-14 but remains an **allowed** (not guaranteed) Intune-managed OS version. [DOC S-qftwfatf]
- VPN profiles for a **device tunnel** are also supported on Windows Enterprise multi-session (Azure Virtual Desktop) remote desktops. [DOC S-qftwfatf]

### Microsoft Tunnel (mobile only — not Windows)
- Microsoft Tunnel is a VPN gateway solution that runs in a **Podman (RHEL) or Docker container** on a Linux server (on-prem or cloud) and provides access to on-prem resources from **iOS/iPadOS and Android Enterprise** devices only, using modern auth and Conditional Access; **Windows is not a supported Tunnel client platform**. [DOC S-3xdtjgi4]
- Licensing: core Microsoft Tunnel requires **Intune Plan 1**; **Microsoft Tunnel for Mobile Application Management (MAM)** — extending the gateway to unenrolled iOS/Android devices — requires **Intune Plan 2** (an Intune add-on/advanced capability). [DOC S-kdhgvxwh, S-3xdtjgi4]
- Prerequisites: Azure subscription; Intune Plan 1; the account registering the Tunnel Gateway needs the Entra **Intune Administrator** role plus an Intune license; a TLS certificate for the Linux server; devices running Android or iOS/iPadOS. Sovereign cloud: supported in **US GCC High**, not supported on Azure operated by 21Vianet. [DOC S-kdhgvxwh]
- Microsoft Tunnel does **not** use FIPS-140-compliant algorithms. [DOC S-3xdtjgi4]
- **Tunnel and Global Secure Access (GSA) cannot be used simultaneously on the same device.** [DOC S-kdhgvxwh]
- Traffic channel uses **TCP, TLS, UDP, and DTLS over port 443** between the device and the public-facing Tunnel Gateway IP/FQDN (can be a load balancer); split-tunnel configurations send only some traffic to the Tunnel, the rest direct to the public internet. [DOC S-3xdtjgi4]
- Role-based access: the **Microsoft Tunnel Gateway** permission group (Create/Update/Delete/Read of server configurations and Sites) is granted by default to Intune Administrators and Entra administrators, and can be added to custom Intune roles. [DOC S-kdhgvxwh]
- Install flow: run the Microsoft Tunnel readiness tool, then download and run the `mstunnel-setup` script as root on the Linux server (`mst_rootless_mode=1 ./mstunnel-setup` for a rootless Podman container); the script always installs the latest Tunnel version. [DOC S-kdhgvxwh]

### Microsoft Entra Private Access / Global Secure Access (Windows successor pointer)
- **Microsoft Entra Private Access** (part of the Global Secure Access / SASE product set) is Microsoft's Zero Trust Network Access replacement for classic VPN and DirectAccess: remote workers with the **Global Secure Access client** reach FQDNs/IPs marked private without a VPN profile at all. [DOC S-lkrznc4c]
- Two configuration models: **Quick Access** (broad IP-range/FQDN segments that mimic full-tunnel VPN — the recommended fast VPN-replacement starting point, feeding traffic into Application Discovery) and **per-app access** (Global Secure Access application with narrow app segments — least-privilege target state). [DOC S-lkrznc4c]
- The **Global Secure Access client** uses a lightweight filter (LWF) driver rather than a VPN stack, so — unlike a VPN client — it can coexist with other VPN/SSE agents on the same device; clients are available for **Windows, Android, macOS, and iOS**. [DOC S-aprlzyvz]
- This kb pass treats Entra Private Access/GSA as a status pointer only: full configuration (Quick Access setup, per-app segmentation, private DNS, Private Network Connector) is out of scope here — see `auth/` domain for a dedicated topic if added. [UNK]

## Reference
- `intune/certificates-pki.md` — SCEP and PKCS certificate profiles referenced by name from every Enterprise Wi-Fi, 802.1X wired, and certificate-authenticated VPN profile above (subject/SAN variables, connector, Cloud PKI). Back-link added there.
- `intune/configuration-policies.md` — Wi-Fi/VPN/802.1X profiles are device-configuration profiles delivered on the same policy check-in/refresh cadence as other configuration policies.
- Not covered in this pass (`UNK`): macOS/iOS/Android Wi-Fi, wired, and VPN profile field references (separate per-platform Learn articles); Microsoft Tunnel install/upgrade/troubleshooting procedure detail beyond the prerequisites summarized here; full Global Secure Access/Entra Private Access configuration (connectors, Quick Access, per-app segmentation, Conditional Access integration).

## Examples
```
# Windows VPN profile: per-app VPN app list import (CSV), package family name and full path forms
%windir%\system32\notepad.exe,desktop
Microsoft.Office.OneNote_8wekyb3d8bbwe,universal

# Custom OMA-URI profile to deliver a native VPN ProfileXML blob (Windows 10 and later)
OMA-URI: ./user/vendor/MSFT/VPNv2/ContosoVPN/ProfileXML
Data type: String (XML file)
Value: <path to exported ProfileXML file>

# Wired 802.1X profile: EAP-TLS with a SCEP device certificate (PL-LT-00123 test device)
Authentication mode: Machine
EAP type: EAP-TLS
Client Authentication method: SCEP certificate -> "Wired 802.1X device cert" profile
802.1x: Do not enforce   # validate before switching to Enforce
```
