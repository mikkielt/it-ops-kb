---
topic: windows/openssh-estate-deployment
priority: P3
applies_to: "Windows 10 1809+/Windows 11, Windows Server 2019/2022/2025 (in-box OpenSSH Feature on Demand), Group Policy, WSUS and Intune"
retrieved_utc: 2026-10-15
sources: [S-tvueruxa, S-gceir6ge, S-yk5jqwiu, S-45qw32rr, S-worv22b3, S-ju4lek45, S-nl6j4vzt, S-cuqswt4k, S430, S-p4fis3e4]
status: partial
---

# Deploying and configuring OpenSSH across a Windows estate (Group Policy, WSUS, Intune)

## Summary
- Microsoft documents one OpenSSH-specific Group Policy: the startup mode of the **OpenSSH SSH Server** service. Installing the capability is governed by the optional component source policy, not by an OpenSSH setting.
- Where devices cannot reach Windows Update (isolated, or behind WSUS on Server 2019/2022, Windows 10, Windows 11 21H2), the capability needs a Features on Demand source on a network share.
- Config (`sshd_config`, `DefaultShell`) and keys are files and registry values; no Microsoft page read names an ADMX or Intune settings catalog item for them, so they travel with a script (Intune platform script or remediation, Group Policy script or preference).
- Facts about the server itself are in `windows/openssh-server.md`, keys in `windows/openssh-key-management.md`.

## Facts
- Default install state: Windows Server 2019, 2022 and Windows 10 build 1809+ "not installed, install and enable using optional features"; Windows Server 2025 "installed but not enabled". [DOC S-tvueruxa]
- The in-box OpenSSH Feature on Demand is the option Microsoft recommends for most users; it is supported and serviced through Windows Update, and Microsoft's `PowerShell/openssh-portable` fork releases might differ from it. [DOC S-gceir6ge]
- `sshd` creates a default `sshd_config` at service start when none exists and reads it only at start, so a fleet that needs a non-default file places it before the first start or restarts the service afterwards. [DER S-ju4lek45: generated when missing, read at service start]
- Group Policy for the service: **Computer Configuration > Policies > Windows Settings > Security Settings > System Services > OpenSSH SSH Server**, define the policy and pick Automatic, Manual or Disabled. The page requires the in-box OpenSSH. [DOC S-yk5jqwiu]
- The Group Policy page documents only the service startup mode; it names no further OpenSSH setting. [DER S-yk5jqwiu: the page's steps end at the startup mode]
- Install fails with `0x800F0954`, `0x800F0950`, `0x8024402C`, `0x80240438` or `0x8024500C` when the computer is isolated from the internet, uses Group Policy for updates, or uses WSUS or another intranet update service. [DOC S-45qw32rr]
- A successfully installed capability still needs `Start-Service sshd` (and optionally Automatic startup) and a check of firewall rule `OpenSSH-Server-In-TCP`, on every supported Windows version, Server 2025 included. [DOC S-45qw32rr]
- WSUS cannot install the OpenSSH features on Windows Server 2022, Windows Server 2019, Windows 11 version 21H2 or Windows 10; those machines take the capability from a network location. [DOC S-45qw32rr]
- The controlling policy is **Specify settings for optional component installation and component repair** under `Computer Configuration\Administrative Templates\System`, exposed as Policy CSP `ADMX_Servicing`; `Update` CSP settings also apply. [DOC S-45qw32rr]
- On Windows 11 24H2 and Windows Server 2025 and later, the default source is Windows Update, with a network folder or intranet service as the fallback; the options "Never attempt to download payload from Windows Update" and "Download repair content ... instead of WSUS" were removed. [DOC S-45qw32rr, S-worv22b3]
- Windows 11 22H2 and later get FoDs and language packs from WSUS again through on-premises Unified Update Platform, so they no longer need the optional component policy for that. [DOC S-worv22b3]
- Windows 10 2004 through Windows 11 21H2 cannot download FoDs when the optional component policy is Windows Update and the feature or quality update source is WSUS; set both sources to Windows Update or configure no source selection. [DOC S-worv22b3]
- The optional component policy never changes how OS updates are distributed; they keep coming from WSUS or Configuration Manager. [DOC S-worv22b3]
- Network source: the FoD ISO must match the Windows version; for Server 2019 use the Windows 10 1809 FoD package for the OpenSSH `.cab` files plus the Server 2019 package; install with `dism /online /add-capability /capabilityname:OpenSSH.Server~~~~0.0.1.0 /source:<Drive>`. [DOC S-45qw32rr]
- Server 2019 version 1809 installation media was observed not to hold the `.cab` files for the OpenSSH features. [DOC S-45qw32rr]
- Microsoft's install troubleshooting page lists the `PowerShell/openssh-portable` and Win32-OpenSSH GitHub releases as a package source, and says a manual GitHub install leaves configuration and all future updates to you. [DOC S-45qw32rr]
- A Win32-OpenSSH release installs by `msiexec /i <msi>`; `ADDLOCAL=Client` or `ADDLOCAL=Server` limits it to one component, the default being both. [DOC S-cuqswt4k]
- Win32-OpenSSH preview releases from 8.9.1.0 are offered in WinGet as "openssh preview"; the wiki labels them preview releases. [DOC S-nl6j4vzt]
- The MSI installs to `ProgramFiles\OpenSSH`, and the folder must be appended to the system PATH for `scp` and `sftp`. [DOC S-cuqswt4k]
- The script install extracts to `C:\Program Files\OpenSSH` with write access only for SYSTEM and Administrators, runs `install-sshd.ps1`, opens a firewall rule by hand, and first start of `sshd` creates host keys under `%programdata%\ssh`. [DOC S-nl6j4vzt]
- Intune platform scripts run once per assignment change, in the system context when "Run this script using the logged on credentials" is No, and retry on failure at the next check-ins. [DOC S-p4fis3e4]
- A platform script (or a remediation) that runs the capability install, service start and file/registry writes is the Intune route to OpenSSH, since no Microsoft page read provides an OpenSSH payload type. [DER S-p4fis3e4, S430, S-45qw32rr: the script facts, the install commands and the absence of an Intune setting on the pages read]
- Whether the `Dism` cmdlets (`Add-WindowsCapability`) behave the same from Intune's default 32-bit PowerShell host is not stated on the pages read. [UNK]
- Whether an Intune settings catalog item or Policy CSP controls `sshd_config` or `DefaultShell` was searched for and not found on Microsoft Learn on 2026-10-15; it may still exist. [UNK]

## Reference
| Need | Mechanism | Source |
|---|---|---|
| Capability present | `Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0` (script) | S430 |
| Capability source offline | Policy `Specify settings for optional component installation and component repair` + network share | S-45qw32rr |
| Service startup mode | GPO System Services > OpenSSH SSH Server | S-yk5jqwiu |
| `sshd_config`, keys, `DefaultShell` | Files and registry values, written by script | S-ju4lek45 |
| Non-in-box build | Win32-OpenSSH MSI or `install-sshd.ps1` | S-cuqswt4k, S-nl6j4vzt |

## Examples
- SNIPPET: install the capability and set the service to start automatically from a platform script or startup script; context: elevated or SYSTEM, device can reach Windows Update or a configured FoD source; checked: no [DOC S430, S-45qw32rr: `Add-WindowsCapability`, `Start-Service`, `Set-Service`]
```powershell
# on PL-SRV-0042
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service -Name sshd -StartupType 'Automatic'
Start-Service sshd
```
- SNIPPET: install from a mounted network FoD source where WSUS blocks the capability; context: elevated command prompt, `<Drive>` the mounted FoD package; checked: no [DOC S-45qw32rr: the `dism /online /add-capability` lines]
```
dism /online /add-capability /capabilityname:OpenSSH.Server~~~~0.0.1.0 /source:<Drive>
```
