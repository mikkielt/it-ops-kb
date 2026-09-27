---
topic: windows/openssh-server
priority: P0
applies_to: "Windows 10 1809+/Windows 11, Windows Server 2019/2022/2025 (in-box OpenSSH)"
retrieved_utc: 2026-09-26
sources: [S430, S431, S432]
status: complete
---

# OpenSSH Server on Windows

## Summary
- Capability names: `OpenSSH.Server~~~~0.0.1.0` and `OpenSSH.Client~~~~0.0.1.0` (install with `Add-WindowsCapability -Online -Name ...`).
- Service `sshd` (display name "OpenSSH SSH Server"). Firewall rule `OpenSSH-Server-In-TCP` opens TCP 22.
- Windows Server 2025 installs OpenSSH by default. You only enable the `sshd` service (Server Manager "Remote SSH Access").
- Configuration is in `%programdata%\ssh\sshd_config`. Admin keys go in `C:\ProgramData\ssh\administrators_authorized_keys`. The default shell is set in `HKLM\SOFTWARE\OpenSSH\DefaultShell`.

## Facts
- Minimum OS: Windows Server 2019 or Windows 10 build 1809. You also need PowerShell 5.1 or later and membership in Administrators. [DOC S430]
- The in-box Feature on Demand is serviced through Windows Update. PowerShell/openssh-portable releases can differ from it. [DOC S430]
- `Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH*'` lists `OpenSSH.Client~~~~0.0.1.0` and `OpenSSH.Server~~~~0.0.1.0`. [DOC S430]
- Start and enable: `Start-Service sshd`; `Set-Service -Name sshd -StartupType 'Automatic'`. [DOC S430]
- Install creates and enables firewall rule `OpenSSH-Server-In-TCP` (inbound TCP 22). [DOC S430]
- Windows Server 2025: OpenSSH is installed by default. On that version, use the **OpenSSH Users** group to allow or restrict users. [DOC S430]
- sshd reads `%programdata%\ssh\sshd_config` by default. `sshd.exe -f` selects another file. [DOC S431]
- The default shell starts as `cmd.exe`. Change it with the string value `DefaultShell` under `HKLM:\SOFTWARE\OpenSSH`, set to the full path of the shell. [DOC S431]
- Directive order: `DenyUsers`, `AllowUsers`, `DenyGroups`, `AllowGroups`. [DOC S431]
- Host keys are stored in `C:\ProgramData\ssh`. [DOC S432]
- Keys for administrator accounts go in `C:\ProgramData\ssh\administrators_authorized_keys`, with an ACL that gives access only to Administrators and SYSTEM. [DOC S432]
- The `ssh-agent` service is disabled by default. [DOC S432]

## Reference
| Item | Value | Source |
|---|---|---|
| Capability | `OpenSSH.Server~~~~0.0.1.0` | S430 |
| Service | `sshd` | S430 |
| Firewall rule | `OpenSSH-Server-In-TCP` (TCP 22) | S430 |
| Config | `%programdata%\ssh\sshd_config` | S431 |
| Default shell key | `HKLM\SOFTWARE\OpenSSH` `DefaultShell` (REG_SZ) | S431 |

## Examples
- SNIPPET: install and start the OpenSSH Server capability, then set the default shell to PowerShell 7; context: Windows Server 2019+/Windows 10 1809+, elevated prompt; checked: no [DOC S430, S431: `Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0`, `Start-Service sshd`, `Set-Service -Name sshd -StartupType Automatic` (S430); `DefaultShell` string value under `HKLM:\SOFTWARE\OpenSSH` (S431)]
```powershell
# on PL-SRV-0042
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd; Set-Service -Name sshd -StartupType Automatic
New-ItemProperty -Path HKLM:\SOFTWARE\OpenSSH -Name DefaultShell -PropertyType String -Force `
  -Value 'C:\Program Files\PowerShell\7\pwsh.exe'
```
