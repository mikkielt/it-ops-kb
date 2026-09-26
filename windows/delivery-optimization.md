---
topic: windows/delivery-optimization
priority: P2
applies_to: "Windows 10/11 Delivery Optimization (DeliveryOptimization CSP/GPO); Microsoft Connected Cache for Enterprise and Education (GA)"
retrieved_utc: 2026-09-26
sources: [S-7olkz3h6, S-3dmxye5u, S-op3zxbbu, S-yrwncj3y, S-4h5a6snd, S-k64d62id, S-wlvfiru4, S-kyd2lkfv, S-6t23b25h, S-3ul4mkos, S-vil7lhvw, S-ufysm5nk]
status: complete
files: [windows/delivery-optimization.csv]
---

# Delivery Optimization: CSP/GPO settings, peer caching, and Microsoft Connected Cache for Enterprise

## Summary
- Delivery Optimization (DO) is Windows' cloud-coordinated, multi-source download client: it can pull the same content in parallel from the original HTTP/CDN source, peer devices, and Microsoft Connected Cache (MCC) servers, verifying every peer-delivered piece by SHA-256 hash before use. [DOC S-6t23b25h]
- All DO configuration is exposed as one CSP/GPO surface, `./Device/Vendor/MSFT/Policy/Config/DeliveryOptimization/*` (GPO: Computer Configuration > Administrative Templates > Windows Components > Delivery Optimization); the full setting/OMA-URI/value/default table is in `windows/delivery-optimization.csv`. [DOC S-3dmxye5u, S-7olkz3h6]
- `DODownloadMode` selects the content sources DO may use (0 HTTP-only, 1 LAN, 2 Group, 3 Internet, 99 Simple/offline, 100 Bypass-deprecated); Group mode (2) is Microsoft's recommended option for most organizations. [DOC S-7olkz3h6, S-3dmxye5u]
- Microsoft Connected Cache for Enterprise and Education is a free, software-only, Azure-managed cache: it runs on customer-provided Windows or Linux host machines, is configured on clients purely via the `DOCacheHost`/`DOCacheHostSource` DO policies (e.g. through Intune), and requires no ConfigMgr distribution point. [DOC S-op3zxbbu, S-yrwncj3y]
- Peer-to-peer transfers use a DO binary protocol over TCP port 7680; Teredo NAT traversal for cross-NAT Group/Internet peering uses UDP port 3544; the DO cloud service and HTTPS content use port 443. [DOC S-6t23b25h, S-kyd2lkfv]
- Diagnose from an elevated PowerShell prompt with `Get-DeliveryOptimizationStatus` (per-job snapshot, incl. `BytesFromCacheServer`/`BytesFromLanPeers`/etc.) and `Get-DeliveryOptimizationPerfSnap`; both ship in Windows 10 1703+. [DOC S-ufysm5nk]

## Facts

### Download behavior and download mode
- `DODownloadMode` values: 0 = HTTP only, no peering (CSP default); 1 = LAN, peering behind the same NAT (DO's own operating default when unconfigured); 2 = Group, peering across a custom or auto-derived group; 3 = Internet peering; 99 = Simple mode, disables DO cloud services entirely (used automatically for offline environments or content under 50 MB); 100 = Bypass, deprecated in Windows 11 (forces BITS instead of DO — Microsoft says not to configure it). [DOC S-7olkz3h6, S-3dmxye5u]
- In Group mode (2), the Group ID is taken from `DOGroupId` (a GUID) if set, else from `DOGroupIdSource`, else automatically in order: AD Site (1) -> authenticated domain SID (2) -> Microsoft Entra tenant ID (5); `DOGroupIdSource` also supports DHCP Option 234 (3) and DNS suffix (4), falling back to the default order if those fail. [DOC S-7olkz3h6]
- `DORestrictPeerSelectionBy` (Windows 10 1803+) further narrows peer discovery within LAN/Group modes: 0 none, 1 subnet mask, 2 Local Peer Discovery (DNS-SD, mDNS-based, doesn't use DO cloud services for peer resolution); Windows 11 restricts LAN mode (1) to the local subnet by default, unlike Windows 10. [DOC S-7olkz3h6]
- Cache defaults (overridable by policy): cache location `%SYSTEMDRIVE%\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache`; max cache age 259,200 s (3 days); max cache size 20% of disk; minimum file size to cache 50 MB; minimum RAM to peer 4 GB; minimum disk size to peer 32 GB. [DOC S-6t23b25h, S-7olkz3h6]
- A device with cached, peerable content has only 4 upload "slots" available to peers at any time; DO rotates content through those slots rather than serving unlimited concurrent peer uploads. [DOC S-vil7lhvw]
- Bandwidth throttling targets no more than ~45% of available bandwidth for a background download and ~90% for an interactive/foreground download by default, measured dynamically every few minutes against the HTTP source and Group/Internet peers; LAN peer transfers are never throttled by the percentage or KB/s bandwidth policies. [DOC S-vil7lhvw, S-3dmxye5u]

### Microsoft Connected Cache for Enterprise and Education
- MCC for Enterprise/Education is generally available, Azure-portal-managed (or Azure CLI), and free to use (the Connected Cache Azure resource incurs no Azure cost); it is a standalone alternative aimed at customers moving away from ConfigMgr distribution points (a separate "Microsoft Connected Cache in Configuration Manager" product exists for ConfigMgr environments). [DOC S-yrwncj3y]
- Supported scenarios: Windows Autopilot provisioning, co-managed clients getting updates/Win32 apps from Intune, and cloud-only Intune-enrolled devices without the ConfigMgr client; supported content types include Windows feature/quality updates, Microsoft 365 Apps (Click-to-Run), Intune/Store client apps, and Windows Defender definition updates. [DOC S-op3zxbbu]
- Licensing: every Windows Desktop device pulling from an MCC node needs Windows Enterprise E3/E5 (incl. via Microsoft 365 F3/E3/E5), Windows Education A3/A5 (incl. via Microsoft 365 A3/A5), or Windows Enterprise per-device; every Windows Server device needs Windows Server Standard, Datacenter, or Datacenter: Azure Edition; there's no cap on the number of licensed devices that can concurrently pull from one node. [DOC S-4h5a6snd]
- Host machine requirements common to both OSes: uninstall any prior MCC install first; reachable to the endpoints in `windows/delivery-optimization.csv`'s companion endpoint list; no other service on port 80; no pre-existing Azure IoT Edge modules; at least 4 GB free memory and 100 GB free disk; inbound/outbound 80 and 443 open. [DOC S-4h5a6snd]
- Windows host additional requirements: Windows 11 (OS build 22631.3296+) or Windows Server 2022+ (build 20348.2227+) with latest CU; nested virtualization supported (e.g. not blocked by Azure VM Trusted Launch); Hyper-V PowerShell management tools installed for deployment (removable after); WSL 2 installed (`wsl.exe --install --no-distribution`); the deployment PowerShell scripts require Windows PowerShell 5.1 (not 7.x) — management afterward works with either. [DOC S-4h5a6snd]
- MCC on a Windows host relies on WSL, which runs under a user context, so it requires a gMSA, local user account, or domain user account for the container; on the host, the `iphlpsvc` (IP Helper) service must be running because MCC uses `netsh portproxy` to forward the host IP to the WSL-hosted container — if `iphlpsvc` is disabled, the container never receives external client requests. [DOC S-op3zxbbu, S-4h5a6snd]
- Linux host requirement: Ubuntu Server 24.04, or RHEL 8.x/9.x (RHEL requires replacing the default Podman container engine with Moby). [DOC S-4h5a6snd]
- Recommended hardware by deployment size: branch office (4 CPU, 8 GB RAM/4 GB free, 100 GB free disk, 1 Gbps NIC); small/medium enterprise (8 CPU, 16 GB/4 GB free, 500 GB free, 5 Gbps NIC); large enterprise (16 CPU, 32 GB/4 GB free, 2x 200-500 GB free, 10 Gbps NIC); MCC does not support multiple NICs on one host. [DOC S-4h5a6snd]
- Sizing/throughput reference: a large-enterprise host sustaining 6.5 Gbps can serve roughly 35,000 managed devices downloading a 2 GB payload within 24 hours; branch-office nodes at 50-500 Mbps deliver roughly 180-900 GB over 8 hours. [DOC S-4h5a6snd, S-op3zxbbu]
- MCC is a reverse proxy and doesn't work behind a forward proxy that caches by default or expects absolute-form URLs (most Squid-based proxies); such proxies must allow the MCC node direct origin access. [DOC S-4h5a6snd]
- Client configuration is entirely via `DOCacheHost` (comma-separated FQDNs/IPs of one or more MCC nodes — clients round-robin across multiple configured hosts and can pull from several concurrently) and/or `DOCacheHostSource` (1 = DHCP Option 235, 2 = DHCP Option 235 Force to override a configured `DOCacheHost`); a `LocalPolicyMerge` security-baseline setting can interfere with the DHCP client and block Option 235 retrieval, notably during Autopilot. [DOC S-3dmxye5u, S-7olkz3h6]
- Reported customer bandwidth savings from combined DO + MCC exceed 90% for Windows 11 upgrades, Autopilot provisioning, Intune app installs, and monthly update deployments; no NDA is required to use the service, and it's supported for production, not just lab testing. [DOC S-k64d62id]
- Content delivery is HTTP between CDN, MCC node, and DO client today (not HTTPS); the DO client independently verifies content authenticity and integrity via metadata/content hashes and signature checks regardless of transport, and HTTPS support end-to-end is planned. [DER S-op3zxbbu: the overview names DOCacheHost/CSP config as the client-side mechanism and the requirements/FAQ pages describe HTTP-based node communication and the DO client's independent hash verification]

### Ports, endpoints, and protocol
- Required ports: TCP 7680 (peer-to-peer content sharing — blocking it disables all P2P but downloads still work via CDN fallback over 80/443); UDP 3544 (Teredo NAT traversal, needed only for Group (2) or Internet (3) download mode); TCP 443 (DO cloud service / HTTPS content); TCP 80 (content metadata and CDN payload); UDP 67/68 (DHCP, for DHCP-based groups or cache-server discovery). [DOC S-kyd2lkfv]
- Port 7680 is opened by the `dosvc` service only while active transfers are in progress; it goes idle (and appears closed) with no downloads/uploads running, Simple mode (99), low battery, Connected Standby, a cellular connection, or a VPN setting that blocks peering. [DOC S-vil7lhvw]
- Firewall allow-list for DO cloud/metadata: `*.do.dsp.mp.microsoft.com` (DO cloud service), `*.dl.delivery.mp.microsoft.com` and `*.windowsupdate.com` (content metadata/payload), `win1910.ipv6.microsoft.com` (Teredo group-peer discovery). [DOC S-kyd2lkfv]
- MCC-specific endpoints (all outbound): Windows Update/Defender/Store content via `*.dl.delivery.mp.microsoft.com`/`*.windowsupdate.com` (HTTP/80); Microsoft 365 app updates via `*.officecdn.microsoft.com`/`*.cdn.office.net`/`*.static.microsoft` (HTTP/80); Intune Win32 apps via `*.manage.microsoft.com` (HTTP/80, HTTPS/443); node deployment/management needs `*.azure-devices.net`, `*.blob.core.windows.net`, `*.mcr.microsoft.com`, `packages.microsoft.com`, `download.microsoft.com`, and WSL's own Ubuntu/GitHub package endpoints. [DOC S-wlvfiru4]
- The content metadata file (Pieces Hash File, PHF) carries per-piece SHA-256 hashes (pieces are typically 1 MB); if the PHF can't be fetched or fails verification, DO falls back to Simple mode (HTTP-only, no peering) as a security safeguard; a peer sending multiple invalid pieces is banned for a period of hours. [DOC S-6t23b25h]

### PowerShell and troubleshooting
- `Get-DeliveryOptimizationStatus` (Windows 10 1703+) returns a real-time snapshot per download job: `FileId`, `FileSize`, `TotalBytesDownloaded`, `PercentPeerCaching`, `BytesFromPeers`, `BytesFromHTTP` (includes `BytesFromCacheServer`), `BytesFromCacheServer`, `BytesFromLanPeers`/`GroupPeers`/`InternetPeers`, `Status` (Downloading/Complete/Caching/Paused), `Priority` (foreground/background); the `-PeerInfo` switch (2004+) lists real-time candidate/connected peers and bytes sent/received per peer. [DOC S-ufysm5nk, S-3ul4mkos]
- `Get-DeliveryOptimizationPerfSnap` returns aggregate keys: `InternetConnectionCount`, `DownloadMode`, `SourceURL`, `CacheHost`, `NumPeers`, `PredefinedCallerApplication`, `ExpireOn`, `IsPinned`. [DOC S-ufysm5nk]
- Cache/file management: `Set-DeliveryOptimizationStatus -Pin $true -FileId <id>` excludes a file from cache-quota deletion until `-ExpireOn` is set; `Delete-DeliveryOptimizationCache [-FileId <id>] [-IncludePinnedFiles] [-Force]` clears cached files and their persisted metadata. [DOC S-ufysm5nk]
- Logging: `Enable-DeliveryOptimizationVerboseLogs` / `Disable-DeliveryOptimizationVerboseLogs` (2004+); `Get-DeliveryOptimizationLog [-Path <etl>] [-Flush]` (1803+); `Get-DeliveryOptimizationLogAnalysis [<etl path>] [-ListConnections]` summarizes file/peer efficiency counts — run `Get-DeliveryOptimizationLog -Flush` first for best results, and the analysis cmdlet can take several minutes. [DOC S-ufysm5nk]
- If no peer bytes appear: check `Get-DeliveryOptimizationStatus`'s `DODownloadMode` is 1/2/3 (99 suggests the client can't reach `*.do.dsp.mp.microsoft.com`); confirm two test devices share the same public IP for LAN mode, or switch to Group mode (2) with a custom `DOGroupID` if they don't; verify port 7680 reachability between peers with `Test-NetConnection -ComputerName <ip> -Port 7680` (or `telnet <ip> 7680`, enabled via `dism /online /Enable-Feature /FeatureName:TelnetClient`). [DOC S-3ul4mkos]
- Zero peers can also mean the min-RAM, min-disk-size, VPN-peering, or on-battery-upload policies are too restrictive for the fleet; check those four settings first. [DOC S-3ul4mkos]
- General error-code lookup: the Delivery Optimization Troubleshooter (`aka.ms/do-fix`). [DOC S-vil7lhvw]

## Reference
- `intune/win32-apps.md` documents Win32 app packaging/deployment; Win32 app content downloaded to Intune-managed devices flows through Delivery Optimization by default and can be served from an MCC node — this article is the DO/MCC settings and troubleshooting reference for that download path. Cross-linked from there.
- `windows/windows-update-management.md` documents the Update CSP/Autopatch/hotpatch/WUfB-reports surface that rides on top of Delivery Optimization for Windows Update content; this article covers the underlying DO/MCC transport and caching layer shared by updates, Win32 apps, and Microsoft 365 apps. Back-linked from there.
- `mecm/software-updates.md:67-68` documents ConfigMgr's own Delivery Optimization client setting (boundary-group DO Group IDs, the version-2203 Delta Download interaction); this article is the underlying DO/MCC CSP-and-cache reference for that ConfigMgr integration, and for "Microsoft Connected Cache in Configuration Manager" (the ConfigMgr-hosted MCC variant, out of scope here — see Microsoft's ConfigMgr MCC docs).
- `windows/winget.md:35` documents WinGet's `network.downloader: do` setting, which routes WinGet package downloads through the same Delivery Optimization client and policy surface documented here.
- Microsoft Connected Cache for Internet Service Providers is a separate, unrelated product for ISPs, not for enterprise networks, and remains out of scope here.
- DHCP-based Connected Cache discovery: `DOCacheHostSource` (MDM/CSP `./Device/Vendor/MSFT/Policy/Config/DeliveryOptimization/DOCacheHostSource`, GPO "Cache Server Hostname Source") takes `1` = query **DHCP Option 235** for the cache server hostname/IP (comma-separated FQDNs or IPs), or `2` = **DHCP Option 235 Force**, which overrides a statically configured `DOCacheHost`. Separately, `DOGroupIDSource` (peer-selection grouping, not cache-server discovery) supports a value `3` = query **DHCP Option 234** for a GUID used as the Group ID. Precedence when both `DOCacheHost` and `DOCacheHostSource` are set: `DOCacheHostSource=1` lets the static `DOCacheHost` list win; `DOCacheHostSource=2` (Force) makes DHCP Option 235 override it. A misformatted DHCP option value falls back to the `DOCacheHost` policy value if configured. The `LocalPolicyMerge` Windows Firewall setting (often disabled by security baselines, notably in Autopilot) can block the DHCP client from retrieving Option 235 — use static `DOCacheHost` instead in that case. Server-side DHCP scope configuration of custom option 234/235 (as text-type options) is standard DHCP server administration, not a Delivery Optimization-specific procedure, and isn't documented on Delivery Optimization's own pages. [DOC S-7olkz3h6]

## Examples
- Configure a pilot device group to use Group download mode with a Connected Cache node, via Intune Graph (Settings Catalog / custom OMA-URI policy, placeholders only):
  ```http
  POST https://graph.microsoft.com/beta/deviceManagement/configurationPolicies
  Content-Type: application/json

  {
    "name": "DO - Connected Cache pilot - PL-SRV-0042",
    "platforms": "windows10",
    "technologies": "mdm",
    "settings": [
      { "settingInstance": { "settingDefinitionId": "device_vendor_msft_policy_config_deliveryoptimization_dodownloadmode", "simpleSettingValue": { "value": 2 } } },
      { "settingInstance": { "settingDefinitionId": "device_vendor_msft_policy_config_deliveryoptimization_docachehost", "simpleSettingValue": { "value": "mcc01.corp.example.com" } } }
    ]
  }
  ```
- Check current DO status and confirm a device is pulling from the Connected Cache node on `PL-LT-00123`:
  ```powershell
  Get-DeliveryOptimizationStatus | Select-Object FileId, Status, BytesFromCacheServer, BytesFromLanPeers, PercentPeerCaching
  Get-DeliveryOptimizationPerfSnap
  ```
- Test peer-to-peer reachability between two devices on port 7680 and confirm they share a public IP for LAN mode:
  ```powershell
  Test-NetConnection -ComputerName 192.0.2.17 -Port 7680
  ```
- Flush and analyze DO logs after a stalled rollout:
  ```powershell
  Get-DeliveryOptimizationLog -Flush
  Get-DeliveryOptimizationLogAnalysis -ListConnections
  ```
- Clear the DO cache (excluding pinned files) to force a re-download during troubleshooting:
  ```powershell
  Delete-DeliveryOptimizationCache -Force
  ```
