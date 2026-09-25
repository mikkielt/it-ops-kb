---
topic: ansible/windows-ssh
priority: P3
applies_to: "Ansible docs 'latest' (ansible-core 2.18+), retrieved 2026-09-23"
retrieved_utc: 2026-09-23
sources: [S933]
status: complete
---

# Ansible to Windows over SSH

## Summary
Ansible officially supports SSH to Windows from ansible-core 2.18, only with the Windows-shipped OpenSSH (>= 7.9.0.0, so Windows
Server 2022+ in practice). Set `ansible_connection: ssh` and `ansible_shell_type` (powershell or cmd, matching the host's DefaultShell).
Auth: key (no delegation), GSSAPI/Kerberos (delegation possible), password (delegates, not recommended).

## Facts
- SSH to Windows could be used since Ansible 2.8 but became officially supported in 2.18. [DOC S933]
- Only the OpenSSH shipped with Windows (capability) is supported, not upstream Win32-OpenSSH; minimum 7.9.0.0; Server 2019 ships 7.7.2.1, so support effectively starts with Server 2022. [DOC S933]
- Install: `Add-WindowsCapability` for `OpenSSH.Server*`, service `sshd` set to Automatic/Running, firewall rule for TCP 22. [DOC S933]
- The default shell is cmd.exe; PowerShell is recommended via `HKLM:\SOFTWARE\OpenSSH` value `DefaultShell`; takes effect on the next connection (use `meta: reset_connection`). [DOC S933]
- Required vars: `ansible_connection=ssh`, `ansible_shell_type=powershell|cmd`. [DOC S933]
- Auth matrix: Key (local yes, AD yes, delegation no); GSSAPI (local no, AD yes, delegation yes); Password (yes, yes, yes). Key or GSSAPI recommended. [DOC S933]
- Admin users' keys live in `C:\ProgramData\ssh\administrators_authorized_keys` (sshd_config `Match Group administrators`). [DOC S933]
- Key auth has the double-hop problem (no network credentials); workaround is `become`. [DOC S933]
- GSSAPI needs `GSSAPIAuthentication yes` in `C:\ProgramData\ssh\sshd_config` and a Kerberos ticket on the control node (kinit); delegation needs a forwardable ticket and `-o GSSAPIDelegateCredentials=yes`. [DOC S933]
- The SSH plugin cannot obtain a Kerberos TGT from an explicit username/password (unlike psrp/winrm); a ticket must exist beforehand. [DOC S933]
- Password auth needs `sshpass` on the control node and performs unconstrained delegation (like CredSSP). [DOC S933]

## Reference
See `windows/` for the OpenSSH Server capability name and service (windows agent).

## Examples
```ini
[lab]
PL-LT-00123.corp.example.com

[lab:vars]
ansible_connection=ssh
ansible_shell_type=powershell
ansible_user=jan.kowalski@CORP.EXAMPLE.COM
```
