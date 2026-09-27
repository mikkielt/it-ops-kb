---
topic: windows/powershell-remoting-jea
priority: P2
applies_to: "WinRM-based PowerShell Remoting (WMF 5.1+/PowerShell 7); Just Enough Administration (JEA); PowerShell remoting over SSH (Windows/Linux/macOS)"
retrieved_utc: 2026-09-26
sources: [S-twfugriu, S-p5lwby5b, S-xe3uwlpq, S-jwo36v2t, S-azyqynh4, S-tabagcvn, S-c7yxdr7e, S-fmtt7m5j, S-o3cdlg27, S-zopt2et4, S-hcszfxta, S-j2g6dv6n, S-sgyc73tt, S-utydlnf7]
status: complete
files: [windows/jea-config-fields.csv]
---

# PowerShell Remoting security: WinRM, the second hop, and JEA

Read `windows/openssh-server.md` first (in-box `sshd`/`ssh` service, firewall rule, host keys) and
`windows/powershell-7.md` first (install/lifecycle of `pwsh`) — not repeated here. This article covers
WinRM-based PowerShell Remoting hardening, the multi-hop ("second hop") delegation problem and its
fixes, Just Enough Administration (JEA), and PowerShell remoting over SSH. `auth/delegation-kcd-obo.md`
covers RBCD/classic KCD mechanics and the "sensitive, cannot be delegated" flag in depth (Kerberos and
Entra scenarios generally); this article adds only the second-hop-specific comparison table and how JEA
fits alongside those mechanisms.

## Summary
- JEA (Just Enough Administration) is Microsoft's security technology for delegated administration of
  anything reachable through PowerShell: it reduces the number of standing administrators on a machine
  and lets you audit exactly which commands a connecting user ran. [DOC S-twfugriu]
- `Enable-PSRemoting` (or `winrm quickconfig`) starts and auto-starts the WinRM service, creates a
  listener (HTTP by default), and opens the firewall for the current profile. WinRM 2.0's default ports
  are **TCP 5985 (HTTP)** and **TCP 5986 (HTTPS)**; `winrm quickconfig -transport:https` adds the HTTPS
  listener (open port 5986 separately).
- Kerberos/NTLM PowerShell Remoting authenticates to the remote machine without sending the user's
  credentials to it, so a command on that remote machine cannot use those credentials to reach a
  *third* machine — the **second hop problem**. Fixes, in Microsoft's stated order of preference:
  CredSSP, resource-based Kerberos constrained delegation (RBCD), classic (front-end) constrained
  delegation, unconstrained Kerberos delegation (not recommended), **JEA**, `PSSessionConfiguration`
  with `RunAsCredential`, or passing credentials inside an `Invoke-Command` script block.
- **JEA** constrains a WinRM/PowerShell Remoting endpoint to a specific, auditable set of commands, and
  can solve the second-hop problem itself by running the session as a virtual account (local-only) or a
  group-managed service account (gMSA, for a network second hop) — without ever handing the connecting
  user standing admin rights or storable credentials.
- A JEA endpoint is defined by a **role capability file** (`.psrc`: which cmdlets/functions/providers/
  external commands a role may use) and a **session configuration file** (`.pssc`: which users map to
  which roles, the run-as identity, transcript directory, and other session-wide settings), registered
  with `Register-PSSessionConfiguration`. Field-by-field reference: `windows/jea-config-fields.csv`.
- PowerShell Remoting over SSH (`Subsystem powershell ...` in `sshd_config`, cross-referenced in
  `windows/openssh-server.md`) does **not** currently support JEA or custom endpoint configuration: SSH
  remoting hosts a plain PowerShell process, and the connecting SSH user gets that user's own OS
  privileges (an administrator gets an elevated shell; a standard user does not) — there is no separate
  constrained endpoint to register over SSH. [DOC S-hcszfxta]

## Facts

### WinRM / PowerShell Remoting basics
- `Enable-PSRemoting` starts the WinRM service, sets it to auto-start, and creates a listener plus a
  firewall exception; on server SKUs it succeeds on all network profiles (opening private/domain
  broadly, public to the local subnet only); on client SKUs it fails on public networks unless
  `-SkipNetworkProfileCheck` is used (then it opens only the local subnet). [DOC S-zopt2et4, S-j2g6dv6n]
- WinRM 2.0 default listener ports: **5985 HTTP**, **5986 HTTPS**; `winrm quickconfig` (`winrm qc`)
  creates the HTTP listener and firewall exception for the current profile only — reapply after a
  firewall-profile change. [DOC S-o3cdlg27]
- `TrustedHosts` (WinRM client setting) suppresses the identity-verification error for NTLM connections
  to hosts not covered by Kerberos mutual authentication (e.g. workgroup members, cross-domain by name);
  it is **not** a trust statement — NTLM can't guarantee the client is really talking to the host it
  intended, so the list only names hosts whose unverifiable server identity you accept. IPv6 addresses in the list must be bracketed. [DOC S-o3cdlg27, DOC S-fmtt7m5j]
- On the wire, HTTPS connections are encrypted by TLS; HTTP connections are encrypted only by the
  authentication protocol's own message-level encryption — Basic auth gives **no** encryption, NTLM uses
  RC4-128, Kerberos uses the ticket's `etype` (AES-256 on modern systems), and CredSSP uses the
  negotiated TLS cipher suite. [DOC S-fmtt7m5j]
- `Get-CimInstance Win32_Service -Filter 'Name="WinRM"' | Select StartName` shows WinRM (and therefore
  PowerShell Remoting sessions on that box) runs as `NT AUTHORITY\NetworkService`, i.e. under the
  computer account, not a user account. [DOC S-c7yxdr7e]

### The second hop problem
- Scenario: you PowerShell-Remote from ServerA to ServerB; a command on ServerB then tries to reach
  ServerC; ServerC denies access because Kerberos/NTLM never handed your credentials to ServerB, so
  ServerB has nothing to present to ServerC. [DOC S-fmtt7m5j, DOC S-c7yxdr7e]
- Fix comparison (Microsoft's stated order of preference, with pros/cons):

  | Method | Pros | Cons |
  |---|---|---|
  | CredSSP | balances ease of use and security; works on Windows Server 2008+ | credentials are cached on the remote server (ServerB) — a compromise there exposes them; disabled by default on both client and server; incompatible with the Protected Users group |
  | Resource-based Kerberos constrained delegation (RBCD) | credentials never stored; PowerShell-cmdlet configurable, no Domain Admin rights needed; works cross-domain/forest | requires Windows Server 2012+; requires rights to update objects and SPNs; Microsoft's cons list also says it doesn't support the second hop for WinRM |
  | Classic (front-end) constrained delegation | no special coding; credentials not stored | requires Domain Administrator to configure; limited to one domain; configured on ServerB's AD object |
  | Unconstrained Kerberos delegation | credentials not stored | **not recommended** — no control over where delegated credentials are used; doesn't support WinRM's second hop |
  | JEA | best security ceiling; no password to maintain with a virtual account | requires WMF 5.0+; must be configured on every intermediate server (ServerB) |
  | `PSSessionConfiguration` + `RunAsCredential` | simple to configure; works on WMF 3.0+ | requires configuring `PSSessionConfiguration`/`RunAs` on every intermediate server; a domain RunAs account needs password maintenance |
  | Credentials in an `Invoke-Command` script block (`$Using:cred`) | no special server configuration; works on WMF 2.0+ | awkward code pattern; you must hold and pass the credential yourself |

  [DOC S-c7yxdr7e]
- CredSSP must be enabled on **both** the client (`Enable-WSManCredSSP -Role Client`, or the
  Administrative Templates "Allow CredSSP authentication" policy under WinRM Client) and the target
  server (`-Role Server`, or the same policy under WinRM Service); it also requires an HTTP or HTTPS
  listener on the server. [DOC S-sgyc73tt, S-utydlnf7]
- RBCD sets the **`msDS-AllowedToActOnBehalfOfOtherIdentity`** attribute on the resource (ServerC),
  configured with `Set-ADComputer -PrincipalsAllowedToDelegateToAccount` (accepts an array, for multiple
  front-end servers) — see `auth/delegation-kcd-obo.md` for the full attribute/ownership model shared
  with the Entra/Kerberos delegation article. The KDC negative-caches a prior denied attempt for 15
  minutes; `klist purge -li 0x3e7` on the intermediate server (ServerB) clears it without a reboot.
  [DOC S-c7yxdr7e]
- Under both classic and resource-based constrained delegation, Microsoft notes that Active Directory
  accounts with the **"Account is sensitive and can't be delegated"** property set can't be delegated. [DOC
  S-c7yxdr7e]
- This is the same flag documented in `auth/delegation-kcd-obo.md` for Entra/on-prem Kerberos delegation
  generally — the second-hop scenario here is one more mechanism that flag blocks. [DER S-c7yxdr7e: its
  classic and RBCD sections both carry the same "can't be delegated" note]

### JEA: role capabilities and session configuration
- A JEA endpoint needs two authored files: a **role capability file** (`.psrc`, created with
  `New-PSRoleCapabilityFile`) listing the commands/providers a role may use, and a **session
  configuration file** (`.pssc`, created with `New-PSSessionConfigurationFile -SessionType
  RestrictedRemoteServer`) mapping users/groups to roles and setting session-wide options. Full field
  list: `windows/jea-config-fields.csv`. [DOC S-p5lwby5b, DOC S-xe3uwlpq]
- `SessionType RestrictedRemoteServer` puts the session in **NoLanguage** mode with only 8 default
  commands visible (`Clear-Host`, `Exit-PSSession`, `Get-Command`, `Get-FormatData`, `Get-Help`,
  `Measure-Object`, `Out-Default`, `Select-Object`) and no providers or external programs — everything
  else must be explicitly added via role capabilities or the session configuration file itself. [DOC
  S-xe3uwlpq]
- `.psrc` fields for exposing commands: **`VisibleCmdlets`**/**`VisibleFunctions`** (optionally per-
  cmdlet `Parameters` restricted to a `ValidateSet` or `ValidatePattern` — you cannot combine both on one
  parameter; `ValidatePattern` wins if both are given), **`VisibleExternalCommands`** (full path required
  — never a bare filename, so a same-named malicious binary elsewhere on `PATH` can't be substituted),
  **`VisibleProviders`** (none by default; Microsoft explicitly warns never to expose **FileSystem**
  (write access anywhere bypasses JEA entirely) or **Certificate** (exposes private keys)). [DOC
  S-p5lwby5b, DOC S-tabagcvn]
- Role-capability merge rules when a user's groups map to more than one role: a cmdlet visible in only
  one role keeps that role's constraints; if two roles both constrain the same parameter with
  `ValidateSet`, the sets are unioned; if one role constrains a parameter and another allows it
  unconstrained, the constraint is dropped entirely (the unconstrained role wins) — so adding a second,
  looser role to a user can silently widen an existing role's restriction. [DOC S-p5lwby5b]
- Custom functions defined in `FunctionDefinitions` run in the system's normal (full) language mode, not
  JEA's constrained mode — they can touch the filesystem/registry/anything, so a role author must treat
  each custom function as its own trust boundary and validate its own inputs (e.g. never pipe raw user
  input into `Invoke-Expression`). [DOC S-p5lwby5b]
- `.pssc` **run-as identity** choices and their effect on the second hop: **`RunAsVirtualAccount =
  $true`** creates a one-time account, destroyed at session end, whose credentials the connecting user never knows, that is
  a member server's local `Administrators` (or a DC's `Domain Admins`) by default — restrict its
  membership with `RunAsVirtualAccountGroups` when full admin isn't needed; a virtual account has **no**
  network identity of its own (network calls appear to come from the machine's own computer account), so
  it does not by itself solve a *network* second hop. **`GroupManagedServiceAccount`** gives the session
  a domain identity so JEA functions can reach network resources (a real second hop) — at the cost of
  every user's actions in that role appearing to come from the same gMSA (transcripts are then the only
  way to attribute an action to a person). Microsoft explicitly recommends **against** a fixed
  `RunAsCredential`/pass-through configuration for a JEA endpoint: it isn't JEA-aware (every connecting
  user gets the same role) and is hard to audit back to a person. [DOC S-xe3uwlpq, DOC S-tabagcvn]
- **`TranscriptDirectory`** is written to by the Local System account; standard users should have no
  access to the folder, and it's recommended for every production JEA endpoint for after-the-fact
  auditing (`Get-PSSessionCapability`, per-command transcripts). [DOC S-xe3uwlpq, DOC S-azyqynh4]
- **`RequiredGroups`** (conditional access) is layered *on top of* `RoleDefinitions` membership — a user
  can be in `RoleDefinitions` and still be denied the endpoint unless they also satisfy the `And`/`Or`
  group rule (e.g. a JIT-elevation or MFA/smartcard-logon group), available in PowerShell 5.1+. [DOC
  S-xe3uwlpq]
- Role capabilities are matched by **base filename only** (no `.psrc` extension) via `$Env:PSModulePath`
  search order, which is not guaranteed to be alphabetical when two role capabilities share a name — use
  unique role-capability filenames across the estate to avoid an unpredictable match. [DOC S-p5lwby5b,
  DOC S-xe3uwlpq]
- Register with `Register-PSSessionConfiguration -Path <pssc> -Name <endpointName> -Force`; this
  **restarts the WinRM service**, terminating every existing remoting session and any in-flight DSC
  configuration on that machine — schedule around production impact. `Get-PSSessionConfiguration` lists
  registered endpoints (built-in ones are named `microsoft.*`); the `.pssc` file itself isn't needed
  after registration and may be deleted. To change a JEA endpoint's settings you must unregister and
  re-register (there is no in-place update). [DOC S-jwo36v2t]
- The WinRM endpoint ACL (who may even connect) is independent of `RoleDefinitions` (who gets which
  commands once connected): with multiple role capabilities, the default ACL allows every mapped
  principal to invoke the endpoint; `Get-PSSessionConfiguration -Name <n> | Select Permission` audits it,
  and `Set-PSSessionConfiguration -ShowSecurityDescriptorUI` / `-SecurityDescriptorSddl` changes it. A
  user with *Invoke* rights but no matching role in `RoleDefinitions` can still connect but only gets the
  default commands. [DOC S-tabagcvn]
- JEA does **not** protect against users who already hold standing admin rights (Domain Admins, local
  Administrators): they can bypass any JEA endpoint via RDP, MMC, or an unconstrained PowerShell
  endpoint, and a local admin can edit the JEA configuration itself to widen it — JEA's benefit comes
  specifically from letting you *remove* standing admin membership from people who only ever needed a
  JEA-scoped task. [DOC S-tabagcvn]
- Auditing: `Get-PSSessionConfiguration | Where-Object SessionType -eq RestrictedRemoteServer` finds
  JEA-like endpoints on a box; virtual-account session identities appear in Security/Application logs as
  `WinRM Virtual Users\WinRM_VA_<n>_<domain>_<sAMAccountName>`, letting you trace a specific action back
  to the connecting user even though the account itself was ephemeral. [DOC S-azyqynh4, DOC S-tabagcvn]
- JEA security-considerations do-not-expose list beyond FileSystem/Certificate: don't expose commands
  that create new runspaces (the `*-Job` cmdlets, or anything that would trigger the Windows PowerShell
  Compatibility feature — see `windows/powershell-7.md`'s `WinPSCompatSession` facts for what that
  feature does when unconstrained); don't expose `Update-TypeData`/`Remove-TypeData`/`Update-FormatData`
  (their script blocks can run in full-language mode even inside a constrained session); don't expose
  `Trace-Command`; and never re-implement JEA's own restricted proxy commands (`Exit-PSSession`,
  `Get-Command`, `Get-FormatData`, `Get-Help`, `Measure-Object`, `Out-Default`, `Select-Object`) yourself.
  [DOC S-tabagcvn]

### PowerShell Remoting over SSH
- SSH remoting hosts a plain PowerShell process as an SSH subsystem, entirely separate from the WinRM
  endpoint model, and as of this retrieval doesn't support custom endpoint configuration or JEA at all;
  the connecting user gets their own OS-level privileges in that shell (an administrator gets an elevated
  shell over SSH, a standard user doesn't). [DOC S-hcszfxta]
- The Windows `sshd_config` subsystem line is `Subsystem powershell C:/progra~1/powershell/7/pwsh.exe
  -sshs` (an 8.3-style path segment or a symlink is needed to avoid a documented Win32-OpenSSH bug with
  spaces in the subsystem executable path); see `windows/openssh-server.md` for the rest of the in-box
  `sshd` service/config facts this reuses. Authentication (password, public key, or SSH-native MFA) is
  entirely SSH's own — PowerShell implements no authentication scheme of its own for SSH remoting. [DOC
  S-hcszfxta]

## Reference
| Item | Value | Source |
|---|---|---|
| WinRM ports | 5985 HTTP, 5986 HTTPS | S-o3cdlg27 |
| Enable command | `Enable-PSRemoting` / `winrm quickconfig` | S-zopt2et4, S-o3cdlg27 |
| JEA restricted session type | `RestrictedRemoteServer` (NoLanguage mode) | S-xe3uwlpq |
| JEA role file | `.psrc` (`New-PSRoleCapabilityFile`) | S-p5lwby5b |
| JEA session file | `.pssc` (`New-PSSessionConfigurationFile`) | S-xe3uwlpq |
| Register JEA endpoint | `Register-PSSessionConfiguration -Path <pssc> -Name <n> -Force` (restarts WinRM) | S-jwo36v2t |
| RBCD delegation attribute | `msDS-AllowedToActOnBehalfOfOtherIdentity` (`Set-ADComputer -PrincipalsAllowedToDelegateToAccount`) | S-c7yxdr7e |
| SSH remoting subsystem line (Windows) | `Subsystem powershell <path>\pwsh.exe -sshs` in `sshd_config` | S-hcszfxta |

Full `.psrc`/`.pssc` field list: `windows/jea-config-fields.csv`.

## Reference (cross-links)
- `windows/openssh-server.md`: in-box `sshd`/`ssh` capability, service, firewall rule, `sshd_config`
  location and host keys — the base OpenSSH facts this article's SSH-remoting section builds on.
- `windows/powershell-7.md`: `pwsh` install/lifecycle, and the Windows PowerShell Compatibility feature
  (`WinPSCompatSession`) that a JEA role must never expose (adding a `*-Job` or compatibility-triggering
  command breaks out of the NoLanguage sandbox); back-linked from there.
- `auth/delegation-kcd-obo.md`: classic vs. resource-based Kerberos constrained delegation mechanics, the
  Entra Application Proxy + KCD path, and the "sensitive, cannot be delegated" flag in full — this
  article only adds the second-hop-specific comparison table and how JEA sits alongside those mechanisms.

## Examples
Help-desk JEA endpoint that may restart exactly one named service and nothing else — **Get-LapsADPassword
is deliberately not exposed**, because LAPS password retrieval is a *data-disclosure* privilege (it
hands back a clear-text local-admin secret usable well outside the JEA session, e.g. for a subsequent RDP
logon), which is a different risk class from *executing* a narrowly-scoped action inside the session; JEA
role merging also has no way to attach a "consumed once, then invalid" constraint to a cmdlet's *output*,
only to its *parameters* — so once a role can call `Get-LapsADPassword`, the password is out of JEA's
control the moment it's returned to the user's screen. [DER S-p5lwby5b,S-tabagcvn: role-capability
parameter/value constraints govern *inputs*, not what a role's output can be reused for]

- SNIPPET: role capability file restricting a role to restarting one named service and read-only status; context: `.psrc`, `New-PSRoleCapabilityFile`; checked: no [DOC S-p5lwby5b, S-tabagcvn: `VisibleCmdlets` with per-cmdlet `Parameters`/`ValidateSet` and unconstrained `Get-Service` match the documented `.psrc` fields; `Get-LapsADPassword` deliberately omitted per the do-not-expose guidance]
```powershell
# HelpDeskServiceRestart.psrc — role capability: restart the Spooler service only, nothing else
@{
    Author           = 'jan.kowalski'
    Description      = 'Help desk: restart the print spooler on PL-SRV-0042 only.'
    VisibleCmdlets   = @(
        @{
            Name       = 'Restart-Service'
            Parameters = @{ Name = 'Name'; ValidateSet = 'Spooler' }
        }
        'Get-Service'   # unconstrained: read-only status check
    )
    # No VisibleProviders, no VisibleExternalCommands, no FunctionDefinitions.
    # Get-LapsADPassword is intentionally absent: see rationale above.
}
```

- SNIPPET: session configuration file mapping a role to a virtual-account JEA endpoint with transcripts on, then register it; context: `.pssc`, `New-PSSessionConfigurationFile`, `Register-PSSessionConfiguration` (restarts WinRM); checked: no [DOC S-xe3uwlpq, S-tabagcvn, S-jwo36v2t: `RunAsVirtualAccount`/`RunAsVirtualAccountGroups`, `TranscriptDirectory`, `RoleDefinitions` are documented `.pssc` fields (S-xe3uwlpq, S-tabagcvn); `Test-PSSessionConfigurationFile` before `Register-PSSessionConfiguration -Path ... -Name ... -Force` matches the documented registration flow (S-jwo36v2t)]
```powershell
# HelpDeskEndpoint.pssc — session configuration: register the role, virtual account, transcripts on
$parameters = @{
    SessionType          = 'RestrictedRemoteServer'
    Path                 = '.\HelpDeskEndpoint.pssc'
    RunAsVirtualAccount  = $true
    RunAsVirtualAccountGroups = 'HelpDeskOperators'   # not local Administrators
    TranscriptDirectory  = 'C:\ProgramData\JEAConfiguration\Transcripts'
    RoleDefinitions      = @{ 'CORP\HelpDesk-L1' = @{ RoleCapabilities = 'HelpDeskServiceRestart' } }
}
New-PSSessionConfigurationFile @parameters
Test-PSSessionConfigurationFile -Path .\HelpDeskEndpoint.pssc   # must return True before registering

Register-PSSessionConfiguration -Path .\HelpDeskEndpoint.pssc -Name 'HelpDesk-SpoolerRestart' -Force
```

- SNIPPET: connect to the registered JEA endpoint by configuration name and run the one allowed command; context: `Invoke-Command -ConfigurationName`, connecting user has no other standing rights on the endpoint; checked: no [DOC S-tabagcvn: a user connects and gets only the commands their role exposes; `Get-LapsADPassword` is not in `VisibleCmdlets` so it fails]
```powershell
# Help-desk technician's side, on PL-LT-00123, connecting to PL-SRV-0042
Invoke-Command -ComputerName PL-SRV-0042.corp.example.com `
  -ConfigurationName 'HelpDesk-SpoolerRestart' -Credential jan.kowalski `
  -ScriptBlock { Restart-Service -Name Spooler }
# Attempting Get-LapsADPassword in this session fails: it was never added to VisibleCmdlets.
```
