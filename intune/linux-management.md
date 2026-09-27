---
topic: intune/linux-management
priority: P3
applies_to: "Microsoft Intune Linux device management (Ubuntu Desktop, RedHat Enterprise Linux), docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-nvad3j6y, S-dvnl6gdu, S-5vopvhhm, S-vbmaayv5, S-37nh7xwg, S-iw63dqdc, S-qnpsgfc5, S-sdxlqqs5, S-mrquhzdn, S-ogsl4hbo]
status: complete
---

# Intune management for Linux

## Summary
Intune manages Linux desktops (Ubuntu Desktop and RHEL) as user-associated, corporate-owned or BYOD devices enrolled through the **Microsoft Intune app for Linux** plus **Microsoft Edge**; bulk enrollment and device-enrollment-manager accounts are not supported. Linux compliance settings come from the **settings catalog** (no predetermined template as on other platforms) and cover allowed distributions, device encryption (dm-crypt/LUKS), password policy and custom compliance; devices are also subject to tenant-wide compliance policy settings shared with other platforms. Custom compliance on Linux uses a POSIX-compliant/any-interpreter discovery script (run in user context, 5-minute limit) plus a JSON rules file, the same mechanism as Windows/macOS but with Linux-specific limits and error codes. Custom device settings not built in to Intune are delivered by importing Bash scripts. Microsoft Defender for Endpoint on Linux can be managed by Intune either through normal MDM enrollment or, for devices not enrolled in Intune, through security settings management using the Defender for Endpoint agent.

## Facts

### Supported platforms and enrollment
- Intune Linux enrollment supports Ubuntu Desktop 26.04 LTS and 24.04 LTS on x86/64, and RedHat Enterprise Linux (RHEL) 9 or 10. [DOC S-5vopvhhm]
- The Linux compliance and Intune-app pages state Ubuntu Desktop support as physical or Hyper-V machines with x86/64 CPUs. [DOC S-dvnl6gdu, S-qnpsgfc5]
- Azure VM support and a GNOME desktop requirement for Ubuntu Desktop are not stated on the current enrollment guide. [UNK: not in S-5vopvhhm as re-read 2026-09-27]
- Linux enrollment is supported for both organization-owned and personal/BYOD devices; employees with an assigned Intune license can enroll their personal Linux devices themselves whenever they want. [DOC S-5vopvhhm, S-nvad3j6y]
- Enrollment is not supported for: Ubuntu Server, bulk enrollment (each device must be enrolled individually via the Microsoft Intune app), userless/kiosk or dedicated devices (a user must sign in with an org account), and device enrollment manager (DEM) accounts. [DOC S-5vopvhhm]
- Enrolling a Linux device already enrolled in another MDM provider "hasn't been tested by Microsoft" — an untested, not officially unsupported, scenario. [DOC S-5vopvhhm]
- Prerequisites for a Linux device: Microsoft Edge web browser version 102.x or later, and the Microsoft Intune app for Linux (which performs the actual registration with Microsoft Entra ID and Intune enrollment). [DOC S-nvad3j6y]
- Enrollment flow: user installs Edge and the Intune app, opens the Intune app and signs in with their org account (`user@corp.example.com`); enrollment starts, registering the device with Microsoft Entra ID and creating an Intune device record; compliance evaluation then begins. The user separately signs in to Edge with the same account to access protected Microsoft 365 web resources. [DOC S-nvad3j6y]
- If a Conditional Access policy targets Edge, users are prompted to enroll their Linux device before they can access Microsoft 365 web apps with their work account in Edge. [DOC S-nvad3j6y]
- Admins take no explicit action to enable Linux enrollment — it's automatically available once Intune prerequisites (add users/groups, assign licenses, set MDM authority) are met; enrolled Linux devices show under **Devices > By platform > Linux** in the admin center. [DOC S-nvad3j6y, S-5vopvhhm]
- Microsoft Identity Broker versions 2.0.2 and later, bundled with the Microsoft Intune app for Linux, replace the earlier Java-based broker; when a device updates across this boundary, Intune automatically re-registers and re-enrolls it, creating **new** Intune device IDs and Microsoft Entra device IDs. Admins should review device-based assignments, filters, and Entra ID group memberships that key off device ID after this update, since old IDs become stale. [DOC S-nvad3j6y, S-5vopvhhm]
- Recommend enabling disk encryption during OS installation rather than after: encrypting after install is possible but can be difficult and potentially very time-consuming. [DOC S-5vopvhhm, S-nvad3j6y, S-dvnl6gdu]

### Install / uninstall the Microsoft Intune app for Linux
- The Microsoft Intune app package is published at `https://packages.microsoft.com/` (the Linux Software Repository for Microsoft Products). [DOC S-qnpsgfc5]
- That the same repository serves .NET, PowerShell, Defender for Endpoint and SQL Server, and the `packages.microsoft.com/config/<Distribution>/<Version>/prod.(repo|list)` config paths, are not stated on the Intune app page. [UNK: not in S-qnpsgfc5 as re-read 2026-09-27]
- A sample install script for the Intune app and its dependencies, for both Ubuntu Desktop and RHEL, is published on GitHub (linked via `https://go.microsoft.com/fwlink/?linkid=2358529`). [DOC S-qnpsgfc5]
- Uninstall on Ubuntu Desktop: `sudo apt remove intune-portal` (removes the app), then `sudo apt purge intune-portal` (also removes local device-registration configuration data). [DOC S-qnpsgfc5]
- Uninstall on RHEL: `sudo dnf remove intune-portal`, then manually remove local registration data at `/var/opt/microsoft/mdatp`, `/etc/opt/microsoft/mdatp`, and `/opt/microsoft/mdatp`. [DOC S-qnpsgfc5]

### Device compliance policy for Linux
- Linux compliance settings are configured from the **settings catalog** rather than a per-platform predetermined template (unlike other platforms): the admin browses and selects individual settings to build the policy. [DOC S-dvnl6gdu]
- Linux devices are also governed by the tenant-wide compliance policy settings. [DOC S-dvnl6gdu]
- **Allowed Distributions**: entries defining a minimum and maximum OS version per Linux distribution type; a device outside the defined min/max/type range must have a different distro or version installed to become compliant. [DOC S-dvnl6gdu]
- **Device Encryption > Require Device Encryption**: requires device-level encryption for writable fixed disks. Intune recognizes any encryption system built on the **dm-crypt** subsystem (the long-standing Linux disk-encryption standard); the preferred method is the **LUKS** format via the **cryptsetup** tool. Ignored partitions: read-only partitions, pseudo-filesystems (`/proc`, `tmpfs`), and `/boot` or `/boot/efi`. [DOC S-dvnl6gdu]
- **Password Policy** settings: Minimum Lowercase, Minimum Uppercase, Minimum Symbols, Minimum Length, Minimum Digits — each specifying the minimum count of that character class required in the device password. [DOC S-dvnl6gdu]
- **Custom Compliance** is its own settings-catalog category, used to add custom compliance settings (discovery script + JSON) to a Linux policy. [DOC S-dvnl6gdu]
- Feature applies to: Ubuntu Desktop 24.04 LTS or 26.04 LTS (physical or Hyper-V, x86/64), RHEL 9, RHEL 10 — the same platform matrix as enrollment. [DOC S-dvnl6gdu]
- Refreshing compliance status on Linux: use **Refresh** on the device-details or compliance-issues page in the running Microsoft Intune app; if the app isn't running, starting it and signing in also triggers a check-in; the app additionally runs a periodic background check-in task while the machine is on and the user is logged in. [DOC S-dvnl6gdu]
- User-facing compliance states surfaced by the Microsoft Intune app on Linux: **Compliant**, **Checking status**, **Not compliant** (with a **View Issues** option showing the required action, e.g. "Upgrade your operating system", the reason, and an optional "How to resolve this" help link). [DOC S-sdxlqqs5]

### Custom compliance (Linux discovery scripts + JSON)
- Custom compliance device-platform requirements: Windows (excluding Windows Home), macOS, and Linux — Ubuntu Desktop 24.04 LTS/26.04 LTS or RHEL 9/RHEL 10. [DOC S-37nh7xwg]
- Windows uses a PowerShell discovery script; Linux and macOS use a POSIX-compliant shell script; each compliance policy supports exactly one discovery script, and one script can discover multiple settings. [DOC S-37nh7xwg]
- On Linux, discovery scripts run in the **user's context** and cannot check system-level settings that require elevation (example given: the state/hash of `/etc/sudoers`). [DOC S-iw63dqdc]
- Linux discovery scripts can call any interpreter installed and configured on the target device (not limited to shell): specify it with a shebang line, e.g. `#!/bin/bash` for Bash or `#!/usr/bin/python3` / `#!/usr/bin/env python3` for Python. [DOC S-iw63dqdc]
- Recommended practice: Linux discovery scripts should catch termination signals (`SIGINT`, `SIGTERM`) and perform graceful cleanup (closing files, releasing locks, removing temp resources) on interrupt/cancellation. [DOC S-iw63dqdc]
- Discovery script limits (all platforms): script no larger than **1 MB**; script output no larger than **1 MB**; run-time limit **5 minutes on Linux**, 10 minutes on Windows/macOS. [DOC S-iw63dqdc]
- Discovery scripts assigned to a compliance policy can't be deleted until unassigned from that policy; each discovery script can be used with only one compliance policy. [DOC S-iw63dqdc]
- Custom compliance error codes (shared across platforms, reported in device compliance reports): `65007` script returned failure, `65008` setting missing in the script result, `65009` invalid JSON for the discovered setting, `65010` invalid datatype for the discovered setting. [DOC S-37nh7xwg]
- It can take up to **8 hours** after a device fixes a custom-compliance issue before a subsequent sync shows the device as compliant again. [DOC S-37nh7xwg]
- On Linux, a user manually triggers a re-check via the Microsoft Intune app's **Refresh** control on the device-details page or the compliance-issues page, starting a new check-in with Intune (equivalent to the Company Portal website sync on Windows or **Check Status** in Company Portal on macOS). [DOC S-37nh7xwg]
- Custom compliance settings feed into Conditional Access decisions the same way built-in compliance settings do, forming one compound rule set with them. [DOC S-37nh7xwg]
- Prerequisite device states for custom compliance: Microsoft Entra joined (including Entra hybrid joined) or Microsoft Entra registered/Workplace joined (WPJ) devices. [UNK: not in S-37nh7xwg as re-read 2026-09-26; an older version of the page listed these prerequisites]

### Custom device configuration (Bash scripts)
- Custom device settings that aren't built in to Intune are delivered by importing an existing **Bash script** as a platform script, at **Devices > Manage devices > Scripts and remediations > Platform scripts > Add > Linux**. [DOC S-vbmaayv5]
- Prerequisites: Linux Ubuntu Desktop, RHEL 8, or RHEL 9 (this specific article's stated support list — see `_conflicts.md` for the version discrepancy against the current platform matrix), and the device already enrolled in Intune. [DOC S-vbmaayv5]
- Configuration settings for a Linux Bash script policy: **Execution context** — `User` (default; script runs at user sign-in, doesn't run if no user ever signs in / no user affinity) or `Root` (script always runs at device level, with or without a signed-in user; may require one-time end-user consent on first run); **Execution frequency** (default **every 15 minutes**); **Execution retries** (default **no retries**) if the script fails; **Execution Script** — upload of an existing `.sh` file only. [DOC S-vbmaayv5]
- Microsoft publishes sample Bash scripts for Linux configuration at `https://github.com/microsoft/shell-intune-samples/tree/master/Linux`. [DOC S-vbmaayv5]
- Custom configuration profiles (Bash scripts) shouldn't be used to deliver sensitive information such as Wi-Fi connection secrets or app/site authentication credentials. [DOC S-vbmaayv5]
- Like other device configuration profiles, a Linux Bash script profile supports optional scope tags and standard user/group assignment before creation completes. [DOC S-vbmaayv5]

### Microsoft Defender for Endpoint relationship
- For devices not enrolled in Intune, Intune's **security settings management** feature can still push Microsoft Defender for Endpoint policy to them: the device is first surveyed for an existing Intune MDM presence; if none, it's enabled for security settings management and, for devices not fully Microsoft Entra registered, a synthetic Entra device identity is created so the device can retrieve policy; Defender for Endpoint on the device then enforces the policy retrieved from Intune. [DOC S-mrquhzdn]
- Security settings management for Linux requires the Microsoft Defender for Endpoint for Linux agent version **101.23052.0009** or later, and is then supported across all Linux distributions listed in Defender's own supported-distributions reference. [DOC S-mrquhzdn]
- Security settings management (all platforms, including Linux) requires connectivity to the `*.dm.microsoft.com` endpoint (wildcard, since cloud-service endpoints for enrollment/check-in/reporting scale and change); it's also supported in US GCC, GCC High and DoD government tenants. [DOC S-mrquhzdn]

## Reference
- `intune/compliance-policies.md`: documents the Windows equivalent of the compliance-policy settings and custom-compliance mechanism described above (tenant-wide compliance policy settings, `windows10CompliancePolicy` Graph resource, PowerShell discovery scripts, the same `65007`-`65010` custom compliance error codes) — this article is the Linux-specific counterpart using the settings catalog and POSIX/any-interpreter discovery scripts instead. See that article's Reference section for the back-link.
- `defender/machine-resource.md` and `defender/permissions-limits.md`: cover the Microsoft Defender for Endpoint Graph machine resource and RBAC that security settings management ultimately drives on Linux devices onboarded to Defender for Endpoint.
- `intune/co-management.md`: co-management and the ConfigMgr client are Windows-only concepts; they don't apply to Linux, which is Intune-MDM-only.

## Examples
- SNIPPET: uninstall the Microsoft Intune app and its local registration data on an Ubuntu Desktop device (placeholders only); context: Ubuntu Desktop, `apt`; checked: no [DOC S-qnpsgfc5]
```bash
sudo apt remove intune-portal
sudo apt purge intune-portal
```

- SNIPPET: Linux custom compliance discovery script skeleton for device `PL-LT-00123`, using Python via a shebang, checking whether a required package is installed and emitting single-line JSON for the matching JSON rule; context: Linux custom compliance discovery script, any interpreter via shebang; checked: no [DOC S-iw63dqdc]
```bash
#!/usr/bin/env python3
import json
import shutil

result = {
    "RequiredPackageInstalled": shutil.which("cryptsetup") is not None
}
print(json.dumps(result))
```

- SNIPPET: matching custom compliance JSON rules file (`en_US` remediation string required); context: custom compliance JSON, shared Windows/macOS/Linux shape; checked: syntax [DOC S-ogsl4hbo]
```json
{
  "Rules": [
    {
      "SettingName": "RequiredPackageInstalled",
      "Operator": "IsEquals",
      "DataType": "Boolean",
      "Operand": true,
      "MoreInfoUrl": "https://corp.example.com/help/cryptsetup",
      "RemediationStrings": [
        { "Language": "en_US", "Title": "cryptsetup is not installed", "Description": "Install cryptsetup and re-run compliance check." }
      ]
    }
  ]
}
```
