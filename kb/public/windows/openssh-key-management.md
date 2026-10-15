---
topic: windows/openssh-key-management
priority: P3
applies_to: "Windows 10 1809+/Windows 11, Windows Server 2019/2022/2025 (in-box OpenSSH); Win32-OpenSSH releases where marked"
retrieved_utc: 2026-10-15
sources: [S-rsn4nacm, S-ju4lek45, S-tvueruxa, S-rkpdqecu, S-odc5ordf]
status: partial
---

# OpenSSH on Windows: key generation, authorized_keys, host keys and ssh-agent

## Summary
- A standard user's public keys go in `C:\Users\<user>\.ssh\authorized_keys`; an account in the local Administrators group is checked against `C:\ProgramData\ssh\administrators_authorized_keys` instead, and that file's ACL may hold only SYSTEM and Administrators.
- Host keys are created by `sshd` on first start under `C:\ProgramData\ssh`, owned by SYSTEM or Administrators; `ssh-agent` ships disabled and must be set to start.
- Key authentication works for local and Active Directory accounts, not for Microsoft Entra ID accounts, and keys cannot be fetched from AD by `AuthorizedKeysCommand`.
- Permission mistakes on these files are the usual cause of a refused key; the Win32-OpenSSH release ships repair functions.
- Install and the service are in `windows/openssh-server.md`; fleet deployment is in `windows/openssh-estate-deployment.md`.

## Facts
- Key-based authentication in OpenSSH for Windows works with local Windows accounts and Active Directory (domain) accounts; Microsoft Entra ID accounts don't support it. [DOC S-rsn4nacm]
- Windows OpenSSH does not support `AuthorizedKeysCommand` and `AuthorizedKeysCommandUser`, so keys cannot be fetched dynamically from Active Directory with those directives. [DOC S-rsn4nacm]
- `AuthenticationMethods` offers only `password` and `publickey` on Windows; sign-in with a Microsoft Entra account is not supported. [DOC S-ju4lek45]
- The built-in tools are `ssh-keygen` (generate, manage, convert keys), `ssh-agent` (stores private keys), `ssh-add`, `ssh-keyscan` (collects public host keys), `scp` and `sftp`. [DOC S-tvueruxa]
- `ssh-keygen.exe` can generate DSA, RSA, ECDSA and Ed25519 keys; with no algorithm given it uses Ed25519. The page's own example uses `ssh-keygen -t ecdsa`. [DOC S-rsn4nacm]
- The default key location is the user profile's `.ssh` folder (`id_ecdsa` private, `id_ecdsa.pub` public in the example). The page advises against an empty passphrase, since the passphrase and key file together act as two factors. [DOC S-rsn4nacm]
- `ssh-agent` is disabled by default: set it to start automatically (`Get-Service ssh-agent | Set-Service -StartupType Automatic`), start it, then load the key with `ssh-add $env:USERPROFILE\.ssh\id_ecdsa`. The page runs this in an elevated prompt. [DOC S-rsn4nacm]
- The page recommends backing up the private key to a secure place and deleting the local copy after `ssh-add`; a key with a strong algorithm cannot be retrieved from the agent, so a lost key means a new pair and a new public key on every system. [DOC S-rsn4nacm]
- Standard user: the public key text goes in a file named `authorized_keys` in `C:\Users\<user>\.ssh\` on the server. [DOC S-rsn4nacm]
- Administrative user: the public key text goes in `administrators_authorized_keys` in `C:\ProgramData\ssh\`, used instead of the file in the user's profile; its ACL must allow only administrators and the System user. [DOC S-rsn4nacm]
- `AuthorizedKeysFile` defaults to `.ssh/authorized_keys`, resolved against the user's home directory when not absolute; for a member of the administrator group `%programdata%/ssh/administrators_authorized_keys` is used instead. [DOC S-ju4lek45]
- `administrators_authorized_keys` must carry permission entries only for `NT Authority\SYSTEM` (full control required) and `BUILTIN\Administrators`; the documented fix is `icacls.exe` with `/inheritance:r` and grants of `Administrators:F` and `SYSTEM:F`. [DOC S-ju4lek45]
- On a non-English Windows, grant by SID instead of group name, with a leading asterisk (the Administrators group's well-known SID, ending in 544, written `*<SID>:F`); `Get-LocalGroup | Select-Object Name, SID` lists the SIDs. [DOC S-rsn4nacm]
- The first use of the `sshd` service generates the host key pair; as no user is associated with the service the host keys are stored under `C:\ProgramData\ssh`. By default `sshd` must be started manually. [DOC S-rsn4nacm]
- The default `HostKey` lines (commented) name `ssh_host_rsa_key`, `ssh_host_dsa_key`, `ssh_host_ecdsa_key` and `ssh_host_ed25519_key` under `__PROGRAMDATA__/ssh`; absent files are generated at service start. [DOC S-ju4lek45]
- A session opened with key authentication carries no user credentials, so it cannot authenticate outbound as that user; the page states this is by design. [DOC S-rsn4nacm]
- Host key files must be owned by SYSTEM or the Administrators group with no access for any other user; a host key owned by another user is flagged and fixed with `icacls /remove`. [DOC S-rkpdqecu]
- A user's `authorized_keys` must not be owned by, or readable through inheritance or explicit grant by, another user; the wiki fixes it with `icacls <file> /inheritance:r` then `/remove <user>`. [DOC S-rkpdqecu]
- A user's private key files must be owned by the user with no other user having access, and the user's `~/.ssh/config` has the same restriction. [DOC S-rkpdqecu]
- A signed-in administrator normally runs non-elevated; such a process does not have authority over resources locked only to the Administrators group, so editing `administrators_authorized_keys` needs an elevated session. [DOC S-rkpdqecu]
- The Win32-OpenSSH release payload carries `OpenSSHUtils` with `Repair-SshdConfigPermission`, `Repair-SshdHostKeyPermission`, `Repair-AuthorizedKeyPermission`, `Repair-UserSshConfigPermission` and `Repair-UserKeyPermission`, all with `-Confirm` and `-WhatIf` semantics. [DOC S-odc5ordf]
- Whether the in-box Feature on Demand ships `OpenSSHUtils` is not stated on the wiki page read. [UNK]
- Because `AuthorizedKeysCommand` is unsupported and the admin file has a strict ACL, a fleet has to write the key files themselves and then set the ACL, as a script or deployment step; deriving the key list from AD at connect time is not available. [DER S-rsn4nacm, S-ju4lek45]

## Reference
| Item | Value | Source |
|---|---|---|
| Standard user keys | `C:\Users\<user>\.ssh\authorized_keys` | S-rsn4nacm |
| Administrator keys | `C:\ProgramData\ssh\administrators_authorized_keys` | S-rsn4nacm |
| Required ACL (admin file) | SYSTEM full control, `BUILTIN\Administrators`, nothing else, no inheritance | S-ju4lek45 |
| Host keys | `C:\ProgramData\ssh\ssh_host_*_key` | S-ju4lek45 |
| Agent service | `ssh-agent`, disabled by default | S-rsn4nacm |
| Default key algorithm of `ssh-keygen` | Ed25519 | S-rsn4nacm |
| Unsupported | `AuthorizedKeysCommand`, `AuthorizedKeysCommandUser`, Entra ID accounts | S-rsn4nacm, S-ju4lek45 |

## Examples
- SNIPPET: place an administrator's public key and lock the file's ACL on the server; context: elevated PowerShell on Windows OpenSSH Server, English-language Windows, key text already in `$authorizedKey`; checked: no [DER S-rsn4nacm, S-ju4lek45: the `Add-Content` and `icacls.exe` lines of the key management page, with the ACL command of the configuration page]
```powershell
# on PL-SRV-0042
Add-Content -Force -Path $env:ProgramData\ssh\administrators_authorized_keys -Value $authorizedKey
icacls.exe "$env:ProgramData\ssh\administrators_authorized_keys" /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```
- SNIPPET: the same ACL for a non-English Windows, granting by SID; context: as above; checked: no [DOC S-rsn4nacm: the page's `*<SID>:F` form for the Administrators group]
```powershell
icacls.exe "$env:ProgramData\ssh\administrators_authorized_keys" /inheritance:r /grant "*S-1-5-32-544:F" /grant "SYSTEM:F"
```
