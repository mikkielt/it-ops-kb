---
topic: windows/powershell-7
priority: P2
applies_to: "PowerShell 7.0-7.7 (pwsh); side-by-side with Windows PowerShell 5.1; Microsoft.PowerShell.SecretManagement/SecretStore, PSResourceGet"
retrieved_utc: 2026-09-26
sources: [S-7rfzq5p7, S-rwd5gx6b, S-qb6m7uly, S-iw3ehpxb, S-x4puowoc, S-onrxwhf7, S-z7wzbalz, S-6vnttaga, S-62djuv2f, S-66rxa5r3, S-awsrthdz, S-zghw4ytw, S-fzd5uvn2, S-vx532wl3, S-cfculwad, S-gzff3gao, S-54flhyvx]
status: complete
files: [windows/powershell-lifecycle.csv]
---

# PowerShell 7.x: lifecycle, install, compatibility, secrets and modules

## Summary
- PowerShell 7 alternates **LTS** (Long Term Servicing, tied to a .NET LTS release, security/servicing
  fixes only) and **STS** ("Stable", called just "Stable" by Microsoft, between LTS releases) releases.
  As of retrieval, current LTS is 7.6 (.NET 10.0), current Stable is 7.5 (.NET 9.0), previous LTS 7.4
  (.NET 8.0, supported until 10-Nov-2026). Version/date/`.NET` table: `windows/powershell-lifecycle.csv`.
- `pwsh.exe` (PowerShell 7) installs side by side with `powershell.exe` (Windows PowerShell 5.1) in its
  own `$PSHOME`; it does not replace 5.1. Windows PowerShell modules load automatically through the
  Windows PowerShell Compatibility feature unless the manifest says otherwise.
- Install: WinGet (recommended for clients, installs MSIX by default since 7.6.0), MSI (servers/enterprise,
  with `ADD_PATH`, `ENABLE_PSREMOTING`, `USE_MU`, `DISABLE_TELEMETRY` properties), MSIX/Store, ZIP,
  `dotnet tool install --global PowerShell`.
- `Microsoft.PowerShell.SecretManagement` + `SecretStore` give a vault abstraction and a local encrypted
  vault; Microsoft has frozen further development (feature-complete, security/critical fixes only,
  repo archived) and points to passwordless/Entra ID as the future direction. For a broader survey of
  secret-at-rest mechanisms (sops, age, Vault transit, Fernet, git-crypt) see `prior-art/secret-vault-encryption.md`;
  for a threat-model comparison of local secret storage options (Python keyring, msal-extensions, Key
  Vault, HashiCorp Vault, GitLab CI variables, Claude Code's own stores) see `agents/secret-storage-options.csv`
  — neither covers SecretStore's own default-vs-unattended posture, which this article adds.
- `Microsoft.PowerShell.PSResourceGet` replaces PowerShellGet v2's `Install-Module`/`Install-Script` with
  `Install-PSResource`, calling the NuGet APIs directly instead of the PackageManagement module.
- Execution policy defaults, precedence and signing requirements are covered in
  `windows/execution-policy-signing.md` (not repeated here); this article cross-links it for the
  `-ExecutionPolicy` install/session behavior specific to `pwsh`.

## Facts

### Lifecycle (LTS vs STS)
- PowerShell as a product follows the Microsoft Modern Lifecycle Policy; support dates on the lifecycle
  page are shown in Pacific Time (PT). [DOC S-7rfzq5p7]
- A **Stable** (non-LTS) release occurs between LTS releases, can contain new features, and is supported
  for about six months after the next LTS release ships. An **LTS** release is defined as "an LTS release
  of .NET": updates to it contain only critical security updates and servicing fixes. [DOC S-cfculwad]
- Version/type/date/.NET-base table (release date, end-of-support, .NET base per version 7.0-7.7):
  `windows/powershell-lifecycle.csv`. [DOC S-cfculwad]
- PowerShell 7.4 (LTS) and 7.5 (Stable) share the same end-of-support date, 10-Nov-2026, because 7.4 is
  built on .NET 8.0 and 7.5 on .NET 9.0, and .NET 8.0 and 9.0 happen to both end support around that date
  under the .NET support policy PowerShell follows. [DER S-cfculwad: same table, two rows]
- The Microsoft Lifecycle "Products" page for PowerShell lists retirement dates one calendar day later
  than the PowerShell Support Lifecycle page for the same releases (e.g. 7.4/7.5 end-of-support
  "11/11/2026 6:59:59 AM" PT there vs "10-Nov-2026" here; 7.2 "11/9/2024" vs "08-Nov-2024"; 7.0 "12/4/2022"
  vs "03-Dec-2022") — see `_conflicts.md`. [DOC S-7rfzq5p7, S-cfculwad]
- `[System.Runtime.InteropServices.RuntimeInformation]::FrameworkDescription` prints the exact .NET build
  a running `pwsh` session is on. [DOC S-cfculwad]
- Support for a PowerShell version also depends on the platform it runs on: support ends when either the
  PowerShell version or the target platform reaches end of life. The same page lists supported macOS
  versions and per-version end dates for Alpine, Debian, RHEL and Ubuntu; Windows support follows the
  Windows lifecycle. [DOC S-cfculwad]
- PowerShell modules that ship separately from the PowerShell release package (e.g. `ActiveDirectory`,
  shipped with Windows Server) are **not** covered by the PowerShell support lifecycle; they follow their
  own product's (here, Windows Server's) lifecycle. [DOC S-cfculwad]
- PowerShell is released under the MIT license; without a paid Microsoft support agreement, users get
  community support only (the most active channels are Discord and Slack; GitHub takes bug reports but
  the team doesn't provide support there), with no guaranteed responsiveness or fixes. [DOC S-cfculwad]
- Experimental features are not intended for production; Microsoft gives them best-effort support
  only. [DOC S-cfculwad]
- PowerShell 7.5.11 is built on the .NET 9.0.20 runtime. [DOC S-rwd5gx6b]

### Side-by-side with Windows PowerShell 5.1
- PowerShell 7 doesn't replace Windows PowerShell 5.1; it installs to its own directory and runs
  side-by-side. Some Windows PowerShell modules run via the Windows Compatibility feature; others must
  run in Windows PowerShell 5.1 itself. [DOC S-qb6m7uly]
- Unless a module's manifest declares PowerShell Core compatibility, modules under
  `%windir%\system32\WindowsPowerShell\v1.0\Modules` are loaded in a background Windows PowerShell 5.1
  process by the Windows PowerShell Compatibility feature. [DOC S-vx532wl3]
- On first compatibility-feature module import, PowerShell creates a remote session named
  `WinPSCompatSession` in that background 5.1 process; the session closes when the last such module is
  removed (`Remove-Module`) or the PowerShell process exits. [DOC S-vx532wl3]
- Modules loaded into `WinPSCompatSession` are reflected into the current PS7 session via **implicit
  remoting** — the same transport PowerShell jobs use — generating a proxy module under `$Env:TEMP` that
  is imported into the current session so PowerShell can detect it was loaded via compatibility. [DOC S-vx532wl3]
- The compatibility session can be driven directly for operations that don't work correctly on
  deserialized objects: the entire pipeline runs in Windows PowerShell and only the final result returns:
  `Invoke-Command -Session (Get-PSSession -Name WinPSCompatSession) -ScriptBlock { ... }`. [DOC S-vx532wl3]
- PowerShell Remoting over SSH accepts an SSH-style connection string: `Enter-PSSession -HostName
  user@host:port`. [DOC S-awsrthdz]
- Deleting a `DELETE_ME_TO_DISABLE_CONSOLEHOST_TELEMETRY` file no longer disables telemetry; the
  differences page names the `POWERSHELL_TELEMETRY_OPTOUT` environment variable (`true`/`yes`/`1`) as the
  opt-out (about_Telemetry adds a Windows setting from 7.6.2, see Install below). [DOC S-awsrthdz]

### Install (Windows)
- Install methods and their intended scenario: **WinGet** (recommended for Windows clients; `winget
  install --id Microsoft.PowerShell --source winget` installs the MSIX by default since the 7.6.0 winget
  package, add `--installer-type wix` for the MSI), **MSI** (best for Windows Server / enterprise
  deployment), **MSIX** (casual users, some limitations), **ZIP** (side-load / multiple versions /
  Server Core, IoT, Arm), **.NET Global tool** (`dotnet tool install --global PowerShell`, for .NET
  developers). [DOC S-qb6m7uly]
- MSI silent-install properties: `USE_MU` (1=default, opt into Microsoft Update/WSUS/ConfigMgr updates;
  0=opt out), `ENABLE_MU` (1=default, opt into Microsoft Update for Automatic Updates generally; setting
  it to 0 does not remove a previously-set opt-in), `ADD_EXPLORER_CONTEXT_MENU_OPENPOWERSHELL`,
  `ADD_FILE_CONTEXT_MENU_RUNPOWERSHELL`, `ENABLE_PSREMOTING`, `REGISTER_MANIFEST`, `ADD_PATH`,
  `DISABLE_TELEMETRY` (sets `POWERSHELL_TELEMETRY_OPTOUT`), `INSTALLFOLDER` (default
  `$Env:ProgramFiles\PowerShell\`, versioned subfolder `7` for current releases, `7-preview` for
  preview — the subfolder name itself can't be changed). [DOC S-qb6m7uly]
- Example silent MSI install: `msiexec /package PowerShell-7.6.6-win-x64.msi /quiet
  ADD_EXPLORER_CONTEXT_MENU_OPENPOWERSHELL=1 ADD_FILE_CONTEXT_MENU_RUNPOWERSHELL=1 ENABLE_PSREMOTING=1
  REGISTER_MANIFEST=1 USE_MU=1 ENABLE_MU=1 ADD_PATH=1`. [DOC S-qb6m7uly]
- MSIX/Store-based installs are single-user only and run in an application sandbox that blocks changes
  to the application's root folder (`$PSHOME`), so they **don't support PowerShell remoting** (inbound
  WSMan config can't be changed). Commands that need write access to `$PSHOME` are also unsupported:
  `Register-PSSessionConfiguration`, `Update-Help -Scope AllUsers`, `Enable-ExperimentalFeature -Scope AllUsers`,
  `Set-ExecutionPolicy -Scope LocalMachine`, and creating or modifying `$PROFILE.AllUsersAllHosts`/`AllUsersCurrentHost`.
  User-level config and outbound SSH remoting still work. [DOC S-qb6m7uly]
- To find how PowerShell was installed, check `$PSHOME`: `$HOME\.dotnet\tools` = .NET Global tool;
  `$Env:ProgramFiles\PowerShell\7` = likely MSI; a path under `$Env:ProgramFiles\WindowsApps\` = MSIX;
  anything else = likely ZIP. [DOC S-qb6m7uly]
- Upgrade check via WinGet: `winget list --id Microsoft.PowerShell --upgrade-available`, then
  `winget upgrade --id Microsoft.PowerShell` (uses the same package format, MSI or MSIX, as the current
  install when the new version offers it). [DOC S-qb6m7uly]
- Update notifications: PowerShell waits 3 seconds after startup, then (if it's been >24h since the last
  check) checks for a newer version, and only shows the notification once that newer release is more than
  7 days old. Controlled by `POWERSHELL_UPDATECHECK`: `Off` disables it; `Default` (same as unset) has GA
  releases notify only of GA updates and preview/RC releases notify of GA+preview updates; `LTS` notifies
  only of updates to LTS GA releases. Must be set before `pwsh` starts. [DOC S-66rxa5r3]
- Telemetry: sent to Microsoft via Application Insights at startup (OS name/version, PS version,
  `POWERSHELL_DISTRIBUTION_CHANNEL`, App Insights SDK version, geo-located-by-IP host location — the IP
  itself isn't stored — the effective Execution Policy, session/user GUIDs) and periodically during the
  session (names/versions of imported Microsoft-owned modules, experimental feature names, `$PSNativeCommandUseErrorActionPreference`
  value, etc.); opt out with `POWERSHELL_TELEMETRY_OPTOUT=true|yes|1` set before the process starts, or
  (from PowerShell 7.6.2 on Windows) by turning off **Send optional diagnostic data** under
  Settings > Privacy & security > Diagnostics & feedback. [DOC S-62djuv2f, S-6vnttaga]
- `POWERSHELL_DIAGNOSTICS_OPTOUT` (added 7.6-preview.5) controls the named pipe PowerShell opens at
  startup for IPC (e.g. `Enter-PSHostProcess`). [DOC S-6vnttaga]

### SecretManagement / SecretStore
- `Microsoft.PowerShell.SecretManagement` is a vault-abstraction module: a common cmdlet set
  that talks to whatever extension vault is registered, so scripts don't hardcode a specific vault's API; switching vaults across
  local/test/production is "change one parameter, **Vault**". It imposes no authentication model itself —
  each extension vault defines its own. [DOC S-iw3ehpxb]
- Both modules are Microsoft-stated **feature complete**: no further active development, security/critical
  bug fixes only, and the source repository is archived. Latest published versions:
  SecretManagement v1.1.2, SecretStore v1.0.6. Microsoft's stated rationale is that passwordless auth
  (passkeys, SSO, federated credentials such as Entra ID, biometrics, hardware keys) is "the future" of
  secret handling. [DOC S-iw3ehpxb]
- `Microsoft.PowerShell.SecretStore` is the first-party local extension vault: cross-platform, stores
  secrets in a file for the current user, encrypted using .NET Core cryptographic APIs. Community
  extension vaults on the Gallery include `Az.KeyVault` (Microsoft-owned), and third-party
  `SecretManagement.KeePass`, `.LastPass`, `.Hashicorp.Vault.KV`, `.KeyChain`,
  `.JustinGrote.CredMan`. [DOC S-iw3ehpxb]
- `Get-SecretStoreConfiguration` default output: `Scope=CurrentUser, Authentication=Password,
  PasswordTimeout=900, Interaction=Prompt`. **Scope** is always `CurrentUser` (`AllUsers` isn't
  supported despite being an accepted enum value). [DOC S-z7wzbalz, S-x4puowoc]
- `Set-SecretStoreConfiguration` parameters: **`-Authentication`** `Password` (default) or `None` (no
  password required — Microsoft's own caution: "less secure ... may be useful for testing scenarios but
  shouldn't be used with important secrets"); **`-PasswordTimeout`** seconds the store stays unlocked
  after a password is supplied (default 900 = 15 min) before the session password is invalidated again;
  **`-Interaction`** `Prompt` (default, interactively asks for the password when needed) or `None` (never
  prompts — if a password is then required and none is cached, the vault throws
  `Microsoft.PowerShell.SecretStore.PasswordRequiredException`); **`-Password`** a `SecureString`, used
  either as the new password (switching `None`→`Password`) or to authorize a change (switching
  `Password`→`None`); **`-Default`** resets to the factory configuration; **`-PassThru`** returns the
  resulting config object (no output by default). [DOC S-x4puowoc, S-z7wzbalz]
- `Unlock-SecretStore` supplies the session password for the current PowerShell session (used when
  `Interaction=None` and a password is still required); the vault stays unlocked until
  `PasswordTimeout` elapses. `Set-SecretStorePassword` changes the vault's stored password but is
  interactive-only (prompts for old/new password, takes no parameters). [DOC S-z7wzbalz]
- Vault configuration and data files: Windows — `$env:LOCALAPPDATA\Microsoft\PowerShell\secretmanagement\localstore\`;
  non-Windows — `$HOME/.secretmanagement/localstore/`. [DOC S-z7wzbalz]
- Microsoft's own unattended-automation walkthrough exports the vault password as a DPAPI-encrypted
  `SecureString` XML (`Export-Clixml`), then applies it in one `Set-SecretStoreConfiguration` call with
  `Authentication='Password'` (not `None`), `PasswordTimeout=3600`, `Interaction='None'` and
  `-Confirm:$false`, then unlocks with `Unlock-SecretStore` in the script — i.e. its example still requires a password (imported via `Import-CliXml`) rather than removing
  authentication entirely; `Authentication=None` is a further step beyond what Microsoft's own example
  uses. [DOC S-onrxwhf7]

### PSResourceGet
- `Microsoft.PowerShell.PSResourceGet` is an updated PowerShellGet written entirely in C#: it drops the
  dependency on the `PackageManagement` module and calls the NuGet APIs directly, simplifies the code
  base, fixes long-standing usability issues that would have been breaking changes in PowerShellGet v2,
  and improves search/install performance. [DOC S-fzd5uvn2]
- `Install-PSResource` combines `Install-Module` and `Install-Script` from PowerShellGet v2 into one
  cmdlet; it does not load the newly installed module into the current session (import it or start a new
  session). It does not install NuGet-v3-protocol dependencies automatically (install those
  individually). Alias: `isres`. [DOC S-zghw4ytw]
- `Update-PSResource` replaces `Update-Module`/`Update-Script`; it installs the newest version
  side-by-side with older ones and does not delete or provide a way to uninstall the older versions
  (delete their files/folders manually), and (like `Install-PSResource`) doesn't auto-load the update.
  Alias: `udres`. [DOC S-gzff3gao]
- On first use, PSResourceGet registers the PowerShell Gallery (`PSGallery`) as a repository with
  priority 50, marked **untrusted** by default; trust it explicitly with
  `Set-PSResourceRepository -Name PSGallery -Trusted -PassThru`. [DOC S-fzd5uvn2]
- `Get-InstalledPSResource` (aliases `Get-PSResource`, `gres`) returns the combined equivalent of
  PowerShellGet v2's `Get-InstalledModule` + `Get-InstalledScript`. [DOC S-54flhyvx]

## Reference
| release | type | .NET base | end-of-support | notes |
|---|---|---|---|---|
| 7.7 | preview | .NET 11.0 | n/a (preview) | not for production, best-effort feedback only |
| 7.6 | LTS (current) | .NET 10.0 | 2028-11-14 | |
| 7.5 | Stable (current) | .NET 9.0 | 2026-11-10 | |
| 7.4 | LTS (previous) | .NET 8.0 | 2026-11-10 | same end date as 7.5 — see Facts |
| 7.0 | LTS | .NET Core 3.1 | 2022-12-03 | first LTS release |

Full table with all released versions: `windows/powershell-lifecycle.csv`. [DOC S-cfculwad]

| SecretStore setting | default | unattended value | effect |
|---|---|---|---|
| Authentication | Password | None | no password required to open the vault (Microsoft: "less secure", testing only) |
| Interaction | Prompt | None | never prompts; a still-required password throws `PasswordRequiredException` instead |
| PasswordTimeout | 900s | n/a (moot once Authentication=None) | seconds the unlocked state persists after a password is supplied |

## Reference (cross-links)
- `windows/powershell-static-analysis.md`: reading `#Requires`, module manifests and the AST without running code, and PSScriptAnalyzer compatibility rules against target versions.
- `windows/execution-policy-signing.md`: execution policy scopes/precedence, `AllSigned`/`RemoteSigned`
  defaults, Authenticode signing — covers the `-ExecutionPolicy` behavior this article's install/session
  facts build on; back-linked from there.
- `windows/powershell-remoting-jea.md`: WinRM/PowerShell Remoting hardening, the second-hop problem and
  Just Enough Administration (JEA) — covers the `WinPSCompatSession`/Windows PowerShell Compatibility
  feature above as a command a JEA role must never expose, since it creates a new (unconstrained)
  runspace.
- `prior-art/secret-vault-encryption.md`: encryption-at-rest mechanisms (sops, age, Vault `transit`,
  Fernet, git-crypt) for a vault builder's own store — SecretStore is a sixth, first-party option in the
  same design space, using .NET Core crypto APIs rather than any of those five.
- `agents/secret-storage-options.csv`: per-mechanism threat coverage table (Python keyring,
  msal-extensions, Azure Key Vault, HashiCorp Vault, GitLab CI variables/secrets, Claude Code stores) —
  add a SecretStore row there if that table is extended: covers "not held in a flat unencrypted file" but
  documents its own `Authentication=None` bypass explicitly, unlike most rows in that table.

## Examples
Unattended SecretStore for a scheduled task: one-time setup (interactive, run once as the account the
scheduled task will run under) registers the default vault and switches it to no-password,
no-interaction mode so a non-interactive scheduled job can read secrets without a prompt or a cached
session password:

- SNIPPET: one-time interactive setup that registers the default SecretStore vault and switches it to no-password, no-interaction mode for unattended use, then stores a secret; context: `Microsoft.PowerShell.SecretManagement`/`SecretStore`, run once as the service/task account; checked: no [DOC S-iw3ehpxb, S-x4puowoc, S-z7wzbalz: `Set-SecretStoreConfiguration -Authentication None -Interaction None` matches the documented `-Authentication`/`-Interaction` parameters and their effect (S-x4puowoc, S-z7wzbalz); `Register-SecretVault`/`Set-Secret` are the vault-abstraction cmdlets S-iw3ehpxb describes]
```powershell
# One-time setup, interactive, as the service/task account:
Install-PSResource Microsoft.PowerShell.SecretManagement, Microsoft.PowerShell.SecretStore -Repository PSGallery -TrustRepository
Register-SecretVault -Name LocalStore -ModuleName Microsoft.PowerShell.SecretStore -DefaultVault

# Caution: Authentication None removes the vault's password requirement entirely (Microsoft:
# "shouldn't be used with important secrets"). Interaction None must be paired with it for a
# scheduled task, which has no console to prompt on.
Set-SecretStoreConfiguration -Authentication None -Interaction None -Confirm:$false

Set-Secret -Name 'svc-PL-SRV-0042-api-token' -Secret (ConvertTo-SecureString 'placeholder-token' -AsPlainText -Force)
```

Reading the secret back inside the scheduled task's own script is an illustration of the counterpart read cmdlet, not backed by a source in this article, and not itself SNIPPET-tagged:
```powershell
# Inside the scheduled task's script (runs as the same account, non-interactively):
$token = Get-Secret -Name 'svc-PL-SRV-0042-api-token' -AsPlainText
Invoke-RestMethod -Uri 'https://api.corp.example.com/v1/status' -Headers @{ Authorization = "Bearer $token" }
```

Registering the scheduled task itself is a standard Task Scheduler pattern not backed by a source in this article (Task Scheduler cmdlets are covered, differently, in `windows/gmsa.md`):
```powershell
# Registering the scheduled task itself (Windows Task Scheduler, PowerShell 7):
$action = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument '-NoProfile -File C:\automation\Invoke-StatusCheck.ps1'
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName 'PL-Automation-StatusCheck' -Action $action -Trigger $trigger `
  -User 'corp.example.com\jan.kowalski' -RunLevel Limited
```
