---
topic: defender/mde-onboarding
priority: P1
applies_to: "Microsoft Defender for Endpoint device onboarding/offboarding (Windows client and server), docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-tkwapxy3, S-5ic2ryhm, S-ka3u6g4r, S-3wd7aoot, S-7aahdyrw, S-kgoe3xkx, S-jzszwiht, S-ptvxamvq, S-v7jhlfyz, S-gmhqowfa, S-bw54wpjr, S-qulvb6va, S-xzhocopu, S-qt5r5zbp, S-wqwf7kt5, S-mrquhzdn, S-6yngu4zf, S-tetnxwlo, S-g53qt6ya, S-334n7pqs, S-zimmfodc, S-vmgy5mjp, S-hssydh4l]
status: complete
---

# Microsoft Defender for Endpoint: onboarding, offboarding and connectivity

## Summary
Devices onboard to Defender for Endpoint (MDE) from the Defender portal's **Settings > Endpoints > Onboarding** page by
picking an OS, a **connectivity type** (Streamlined or Standard) and a **deployment method**: local script (up to 10
devices, proof-of-concept only), Group Policy, Microsoft Intune/MDM, Configuration Manager, or VDI scripts for
non-persistent VDI. Offboarding uses the same page and mirrors the deployment method; offboarding packages expire
**7 days** after download for local script, GPO and Intune/MDM, and **30 days** for Configuration Manager, and Defender
rejects an expired package. After offboarding, a device shows **inactive** after 7 days and its (data-free) profile
stays in device inventory up to 180 days, while historical alert/vulnerability data is retained per the tenant's
retention setting. Onboarding and offboarding policies must never target the same device at the same time. Device
tags identify devices for targeting; **Group Policy/registry tagging** on Windows writes the tag under
`HKLM\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection\DeviceTagging\Group`. **Security settings
management** lets Intune endpoint security policies reach devices onboarded to MDE but not enrolled in Intune. Proxy
connectivity for the EDR sensor is configured separately from Defender Antivirus's proxy settings, via
`TelemetryProxyServer`. The **MDE Client Analyzer** validates connectivity before and after onboarding.

## Facts

### Onboarding methods and connectivity type
- Windows 10/11 and Windows 365 client onboarding methods: local script (up to 10 devices), Microsoft Intune/MDM, Microsoft Configuration Manager, Group Policy, and VDI scripts; Windows 8.1/7 SP1 Enterprise or Pro use the Microsoft Monitoring Agent (MMA). [DOC S-tkwapxy3]
- Server onboarding methods for Windows Server 2012 R2+, Windows Server 1803+, and Azure Stack HCI OS 23H2+: local script (onboarding package), Microsoft Defender for Cloud/"Defender for Servers", Microsoft Configuration Manager, Group Policy, VDI scripts, or onboarding through Defender for Cloud, using the "modern, unified solution" for Server 2016 and 2012 R2. [DOC S-5ic2ryhm]
- On the Onboarding page, an admin selects the OS group, then **Connectivity type** (Streamlined or Standard; see prerequisites for streamlined connectivity), then **Deployment method**, and downloads the onboarding package/script for that combination. [DOC S-tkwapxy3]
- The local script is explicitly scoped to **10 or fewer devices**, for evaluation before selecting a deployment method for a larger environment; production deployments should use Group Policy, Configuration Manager, Intune, or the Defender deployment tool. [DOC S-ka3u6g4r]
- The Defender deployment tool is a lightweight, self-updating application that can deploy Defender endpoint security to Windows and (preview) Linux devices, as an alternative to the local script. [DOC S-ka3u6g4r, S-5ic2ryhm, S-tkwapxy3]
- Downloading onboarding/offboarding packages requires full access to Defender for Endpoint; the Entra **Security Administrator** role grants this. [DOC S-ka3u6g4r]
- Repackaging the Defender for Endpoint installation package is unsupported and can trigger tampering alerts or break updates. [DOC S-tkwapxy3]
- Non-persistent VDI, single-entry model: recreated desktops that keep the same final device name share one device entry; `Onboard-NonPersistentMachine.ps1` (which runs `WindowsDefenderATPOnboardingScript.cmd`) runs only after the VM has its final name and final provisioning restart. Existing legacy MMA-based single-entry deployments also need a `DeviceTagging\VDI = NonPersistent` (`REG_SZ`) registry value (registry import or `reg add`); Server 2012 R2 and later follow the server onboarding process. [DOC S-jzszwiht]

### Onboarding via Group Policy, Configuration Manager, Intune (EDR policy)
- Group Policy onboarding deploys the onboarding script to target devices as an immediate scheduled task in a GPO; Group Policy doesn't report deployment status to Defender for Endpoint, so confirm the GPO applied (Group Policy Results) and then find the device in the Defender portal Device inventory (onboarded, sensor health active), typically within several minutes. [DOC S-7aahdyrw]
- Configuration Manager onboarding: on the Defender portal Onboarding page choose **Windows 10 and 11** (the file also covers supported up-level Windows Server) and deployment method **Microsoft Endpoint Configuration Manager current branch and later**, create an onboarding policy from the downloaded file and deploy it to a device collection; the console keeps the legacy labels **Microsoft Defender ATP Policies** / **Create Microsoft Defender ATP Policy**. Version 2207 and later can deploy the modern unified client to Server 2012 R2/2016. [DOC S-3wd7aoot]
- Intune deploys onboarding/offboarding as an **endpoint detection and response (EDR) policy**: an EDR policy's **Package type** is set to **Onboard** (paste the onboarding blob) or **Offboard** (paste the offboarding blob); an existing offboarding policy can be updated by replacing its blob content. [DOC S-v7jhlfyz]
- The Intune/MDM offboarding OMA-URI is `./Device/Vendor/MSFT/WindowsAdvancedThreatProtection/Offboarding`, data type String, value = the contents of the downloaded offboarding file. [DOC S-kgoe3xkx]
- Deploying an Intune offboarding EDR policy disables the Defender for Endpoint sensor on the device but does not remove the client; the device stops sending telemetry and shows "inactive" after 7 days, while the Intune EDR policy shows compliant deployment. [DOC S-v7jhlfyz]

### Offboarding: expiry, effects, retention
- Local-script, Group Policy and Intune/MDM offboarding packages expire **7 days** after download (embedded in the filename as `..._valid_until_YYYY-MM-DD...`); Defender for Endpoint rejects an expired package. [DOC S-ka3u6g4r, S-kgoe3xkx, S-7aahdyrw]
- Configuration Manager current-branch offboarding configuration files expire **30 days** after download; expired files are rejected. [DOC S-3wd7aoot]
- Onboarding and offboarding must never be deployed to, or run on, the same device at the same time — for Group Policy specifically, unlink/remove the onboarding GPO before deploying the offboarding GPO. [DOC S-ka3u6g4r, S-7aahdyrw]
- After offboarding: no new detection/vulnerability/security data is sent; the device's status becomes **inactive** 7 days later; devices inactive for the last 30 days are excluded from the org's exposure score; historical data (alerts, vulnerabilities, device timeline) is retained until the tenant's configured retention period expires, and the (data-free) device profile stays in inventory up to **180 days**. [DOC S-ptvxamvq]

### Connectivity: standard vs. streamlined, proxy, sensor
- **Streamlined connectivity** consolidates Defender for Endpoint cloud traffic behind `*.endpoint.security.microsoft.com` (or `*.endpoint.security.microsoft.us` for the equivalent Gov cloud domain); proxies and network security policies must bypass inspection (no SSL/TLS inspection, no MITM) for this traffic. [DOC S-bw54wpjr, S-gmhqowfa]
- **Standard connectivity** instead requires a longer, per-service URL allowlist (commercial vs. US Government/GCC/DoD lists), open by geography (`WW` rows always, others per data location); `*.blob.core.windows.net` must not be excluded from inspection wholesale — only the specific Defender for Endpoint blob URLs. [DOC S-bw54wpjr]
- Windows 10 versions 1607–1803 support onboarding only via the streamlined package with a longer URL list and cannot be re-onboarded in place — they must be fully offboarded before changing connectivity type; Windows 7/8.1/Server 2008 R2 with MMA must keep using the MMA onboarding method. [DOC S-bw54wpjr]
- Defender for Endpoint requires IPv4 connectivity; an IPv6-only network needs a transition mechanism (e.g., DNS64/NAT64). [DOC S-qulvb6va]
- The portal's streamlined-by-default setting applies only to newly onboarded devices (existing devices aren't reonboarded automatically); to move already-onboarded devices, follow "Migrate devices to streamlined connectivity" and apply the streamlined package with that article's OS-specific restart guidance. [DOC S-bw54wpjr, S-gmhqowfa]
- The Windows EDR sensor runs as `LocalSystem` and uses WinHTTP (independent of WinINet); three proxy configuration options: automatic discovery (transparent proxy or WPAD, no extra setting needed), an **EDR sensor static proxy** (component-specific), or a system-wide WinHTTP static proxy set with `netsh winhttp`; Defender Antivirus uses its own separate proxy configuration for cloud-delivered protection. [DOC S-qulvb6va]
- EDR sensor static proxy (`TelemetryProxyServer`) is configured only via Group Policy (never MDM): GPO **Configure connected user experiences and telemetry** sets registry value `HKLM\Software\Policies\Microsoft\Windows\DataCollection!TelemetryProxyServer` (`REG_SZ`, format `<server-name-or-ip>:<port>`, no protocol prefix, no spaces), alongside **Configure Authenticated Proxy usage for the Connected User Experience and Telemetry Service** set to Enabled/"Disable Authenticated Proxy usage" (`DisableEnterpriseAuthProxy=1`, `REG_DWORD`). [DOC S-qulvb6va]
- Authenticated proxies aren't supported for the EDR sensor's destinations, since connections originate from OS/Defender services with no user context. [DOC S-qulvb6va, S-bw54wpjr]
- Setting `PreferStaticProxyForHttpRequest=1` (`REG_DWORD`) under `HKLM\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection` makes a compatible EDR sensor (MsSense.exe `10.8210.*` or `10.8049.*` and later branches) prefer the static `TelemetryProxyServer`, for devices that can't use the default WinHTTP proxy for certificate revocation lists or Windows Update; it doesn't apply to the legacy MMA-based sensor. [DOC S-qulvb6va]
- Defender Antivirus cloud protection proxy is configured separately: GPO **Define proxy server for connecting to the network**, or PowerShell `Set-MpPreference -ProxyServer "<protocol>://<server>:<port>"` / `-ProxyPacUrl` / `-ProxyBypass`; it does not use the static proxy for Windows Update/Microsoft Update downloads. [DOC S-qulvb6va]
- If `TelemetryProxyServer` is set but Defender for Endpoint can't reach the defined proxy, the sensor falls back to direct connectivity. [DOC S-xzhocopu]

### Connectivity verification (MDE Client Analyzer)
- The MDE Client Analyzer can run before onboarding (by default tests the standard URL set for US, UK and EU, or the streamlined set with `-o <onboarding script>` or `-g US|EU|UK`) or after onboarding (uses the device's actual onboarding parameters); on Windows, `MDEClientAnalyzer.cmd -o <path to onboarding .cmd>` tests connectivity for a not-yet-onboarded device using the onboarding script's own geo parameters. [DOC S-xzhocopu, S-gmhqowfa]
- On Windows 10/11, Server 2019/2022, and Server 2012 R2/2016 with the modern unified solution, the analyzer script calls `MDEClientAnalyzer.exe`; on Windows 8.1/Server 2016 (or earlier) using MMA, it calls `MDEClientAnalyzerPreviousVersion.exe` plus MMA's own `TestCloudConnection.exe`. [DOC S-6yngu4zf]
- Results are written to `MDEClientAnalyzerResult.txt`, one line per tested URL per connectivity method (default proxy, WPAD, proxy disabled, named proxy, command-line proxy); an HTTP 200 on any method means that connectivity path works. [DOC S-xzhocopu]
- The connectivity checks in the analyzer conflict with the ASR rule **Block process creations originating from PSExec and WMI commands**: temporarily disable that rule or add a global/per-rule exclusion for the analyzer before running it (see `defender/asr-and-antivirus.md`). [DOC S-xzhocopu]
- macOS/Linux use `mdatp connectivity test` after installation; before onboarding the Client Analyzer can run on macOS, and on Linux `MDESupportTool connectivitytest` takes `-o <onboarding script>` or `-g <US|UK|EU|AU|CH|IN>`. [DOC S-g53qt6ya, S-tetnxwlo]

### Device tags and targeting
- Windows registry-based device tagging: `HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection\DeviceTagging\` with a `REG_SZ` value named `Group` holding the tag name (max 200 characters); tags sync once daily, or immediately after a device restart; clearing (not deleting) the `Group` value data removes the tag. [DOC S-qt5r5zbp]
- A Windows 10+ custom Intune profile can instead set the tag via OMA-URI `./Device/Vendor/MSFT/WindowsAdvancedThreatProtection/DeviceTagging/Group`, data type String. [DOC S-qt5r5zbp]
- macOS/Linux tagging goes through a security-settings-management endpoint detection and response policy, or a native configuration profile (`.plist` for macOS domain `com.microsoft.wdav`, key `tags`, array of `{key: "GROUP", value: "<tag>"}`; `.json` preferences file for Linux). [DOC S-qt5r5zbp, S-zimmfodc]
- Android tagging uses a Managed apps app configuration policy key `DefenderDeviceTag` (string value); tags can take up to 18 hours to reach the Defender portal and require the user to open the Defender app at least once. [DOC S-334n7pqs]
- **Dynamic tags** (from Asset Rule Management rules) update roughly hourly and scale to thousands of devices; they're required for advanced scenarios such as custom data collection, whereas **manual tags** (applied via portal or API) don't scale and aren't supported for those scenarios. [DOC S-hssydh4l]
- Device tags feed **device groups** (up to 2,000 per tenant), which add RBAC scoping (Entra user-group assignment) and a remediation level (No automated response through Full remediation) on top of tag-based matching rules. [DOC S-vmgy5mjp]

### Security settings management (MDE-managed devices without Intune enrollment)
- Security settings management lets Intune endpoint security policies reach Windows, Windows Server 2012 R2+, Linux and macOS devices that are onboarded to Defender for Endpoint but not enrolled in Intune; a device already enrolled in Intune uses normal Intune policy delivery instead — the two are mutually exclusive per device. [DOC S-mrquhzdn]
- Enablement: in the Defender portal, **Settings > Endpoints > Configuration Management > Enforcement Scope**, enable the platform and choose scope **All devices** or **On tagged devices** (recommended initially, using a dedicated tag such as `MDE-Management`); a device can take up to 24 hours to complete enrollment. [DOC S-mrquhzdn]
- Devices without a full Microsoft Entra registration get a **synthetic device identity** created for policy delivery; this counts against Entra ID device-object quotas the same as a full registration, and is replaced transparently if the device later fully registers (e.g., completes hybrid join). [DOC S-mrquhzdn]
- A managed device shows **MDE Enrollment status: Success** on its device page, and **Managed by: MDE** in the Intune admin center's All Devices list; the recommended dynamic-group attribute for targeting is `deviceOSType`, or `managementType eq "MicrosoftSense"` to scope to security-settings-management devices only. [DOC S-mrquhzdn]
- Legacy system tags `MDEManaged`/`MDEJoined` (pre-September 25, 2023 opt-in preview behavior) are no longer applied to newly enrolled devices; dynamic groups built on them stop matching new devices. [DOC S-mrquhzdn]

### EDR in block mode
- EDR in block mode requires a Defender for Endpoint **Plan 2** license and is recommended primarily for devices running Defender Antivirus in **passive mode** (a non-Microsoft antivirus is the active real-time engine); it remediates post-breach, behavioral EDR detections that the non-Microsoft AV missed. [DOC S-wqwf7kt5]
- Enable tenant-wide in the Defender portal (**Settings > Endpoints > General > Advanced features > Enable EDR in block mode**), or, from Defender Antivirus platform `4.18.2202.X` and later, target specific device groups via the Intune-deployed `Defender CSP` node `Configuration/PassiveRemediation`, or via Group Policy. [DOC S-wqwf7kt5]
- See `defender/asr-and-antivirus.md` for the Defender Antivirus active/passive/EDR-block-mode state model that ASR rules and EDR in block mode both depend on. [DER: same active/passive AV state gates both features, S-wqwf7kt5]

## Reference
- `defender/asr-and-antivirus.md`: Defender AV active/passive/off state model (required for EDR in block mode and for ASR rules), and the MDEClientAnalyzer/ASR-rule conflict noted above.
- `defender/response-actions-api.md`: `POST /api/machines/{id}/<action>` response actions once a device is onboarded and visible as a `Machine` resource.
- `defender/machine-resource.md`: the `Machine` API resource (`aadDeviceId`, `onboardingStatus`, tags) returned for onboarded devices; this article's onboarding-status and device-tagging facts back the enrollment/tag fields there. Back-link added there.
- `intune/linux-management.md`: Defender for Endpoint on Linux managed either through normal Intune MDM enrollment or, for unenrolled devices, through the security settings management path documented above.
- `mecm/application-model.md`, `mecm/client-settings.md`: no MDE-onboarding-specific content found in either article at the time of writing (gap, not linked).

## Examples
Group Policy static proxy for the EDR sensor (registry values a GPO applies):
```
HKLM\Software\Policies\Microsoft\Windows\DataCollection
  DisableEnterpriseAuthProxy = 1 (REG_DWORD)
  TelemetryProxyServer       = "192.0.2.6:8080" (REG_SZ)
```

Manual device tag via registry (Windows, local or GPO Preferences):
```
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection\DeviceTagging" /v Group /t REG_SZ /d "PL-Site-Warsaw" /f
```

Client Analyzer pre-onboarding connectivity test using a downloaded (not-yet-run) onboarding script, from an elevated prompt on `PL-LT-00123`:
```
MDEClientAnalyzer.cmd -o %USERPROFILE%\Desktop\WindowsDefenderATPOnboardingScript.cmd
```
