---
topic: windows/winget
priority: P2
applies_to: "Windows Package Manager (WinGet) CLI, App Installer package, WinGet Configuration (v2/v3), Group Policy/CSP; Windows 10 1809+, Windows 11, Windows Server 2025; docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-bx6tsyla, S-vrwvsimi, S-x6zzi6h7, S-td3e5ov5, S-bbyce4yg, S-7ddssdnb, S-sgplcdqr, S-ht6fligp, S-dgnfikws, S-fbg5dkgs, S-7symcqej, S-xgfg5ggj, S-ig43wzxm, S-h66nieow]
status: complete
files: [windows/winget-policies.csv]
---

# Windows Package Manager (WinGet)

## Summary
WinGet is the command-line client for the Windows Package Manager, shipped inside the **App Installer** MSIX package (`Microsoft.DesktopAppInstaller_8wekyb3d8bbwe`) and updated through the Microsoft Store on client OSes. It installs, upgrades, lists, exports/imports and pins packages, and can drive a declarative **WinGet Configuration** file (`.winget`) built on PowerShell DSC — v2 files use DSC schema 0.2 under a `properties:` root, v3 files use the native DSC v3 document schema directly (see `dsc/cli-reference.md`, `dsc/functions.md` for the DSC v3 engine itself; this article covers only the WinGet-specific wrapper and resources). Enterprises manage WinGet with `DesktopAppInstaller.admx`/CSP policies under `HKLM\Software\Policies\Microsoft\Windows\AppInstaller`, full table in `windows/winget-policies.csv`. WinGet's own CLI is unsupported as SYSTEM; the `Microsoft.WinGet.Client` PowerShell module is the supported path for machine-wide/system-context automation. Intune's "Microsoft Store app (new)" app type uses WinGet/the Microsoft Store catalog under the hood.

## Facts

### CLI: install, upgrade, sources
- `winget install [-q <query>] [options]` (alias `add`); by default the query is a case-insensitive substring match against name, ID and moniker (no wildcards); `-e`/`--exact` requires an exact, case-sensitive match; `--id`, `--name`, `--moniker` restrict which field is searched. [DOC S-bx6tsyla]
- Key install options: `-v/--version`, `-s/--source`, `--scope <user|machine>`, `-a/--architecture`, `--installer-type`, `-i/--interactive`, `-h/--silent`, `--locale`, `-o/--log <path>`, `--custom` (extra installer args appended to defaults), `--override` (a string passed directly to the installer), `-l/--location`, `--ignore-security-hash`, `--allow-reboot`, `--skip-dependencies`, `--accept-package-agreements` (accepts the package's own EULA only), `--accept-source-agreements` (accepts the source's terms of use, separate from the package EULA), `--no-upgrade`, `--dependency-source`, `--authentication-mode <silent|silentPreferred|interactive>`, `--disable-interactivity`, `--proxy`/`--no-proxy`. [DOC S-bx6tsyla]
- `winget install --id Git.Git -e --source winget` disambiguates by exact ID plus source when multiple sources could match; the `msstore` source's package IDs are unique so `-e` isn't required for it. `winget install A B C` installs multiple package IDs in one command, in sequence. [DOC S-bx6tsyla]
- Local-manifest install (`-m/--manifest <path or directory>`) is disabled by default and must be enabled first: `winget settings --enable LocalManifestFiles` (disable with `--disable`); it is also gated by the `EnableLocalManifestFiles` policy. [DOC S-bx6tsyla, S-x6zzi6h7]
- WinGet log files, unless redirected with `-o`, live at `%LOCALAPPDATA%\Packages\Microsoft.DesktopAppInstaller_8wekyb3d8bbwe\LocalState\DiagOutputDir\*.log`. [DOC S-bx6tsyla]
- Supported installer types: EXE (Silent/SilentWithProgress), ZIP, INNO, NULLSOFT, MSI, WIX, APPX, MSIX, BURN, PORTABLE, FONT. [DOC S-dgnfikws]
- Top-level commands: `install`, `show`, `source`, `search`, `list`, `upgrade`, `uninstall`, `hash`, `validate`, `settings`, `features`, `export`, `import`, `pin`, `configure`, `download`, `repair`, `dscv3` (PowerShell DSC v3 resource commands). [DOC S-dgnfikws]
- `winget source` subcommands: `add`, `edit`, `list`, `update`, `remove`, `reset`, `export`; default sources are `msstore` (Microsoft Store catalog), `winget` (community repository) and `winget-font`. `add` accepts an optional type: `Microsoft.PreIndexed.Package` (default) or `Microsoft.Rest` (a Microsoft REST API source). `winget source reset --force` removes all sources except the defaults and requires admin privileges. `edit --explicit <true|false>` toggles whether a source must be targeted with `--source`/`-s` to be searched (`winget-font` is explicit by default). [DOC S-fbg5dkgs]
- WinGet requires the user to have logged in once so the Microsoft Store can asynchronously register the package; to force registration: `Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe`. [DOC S-dgnfikws]
- WinGet ships on Windows 10 1809+ (build 17763+), Windows 11 and Windows Server 2025 as part of App Installer; on Windows Server 2025 App Installer updates via Windows Update rather than the Store. [DOC S-dgnfikws]

### Settings, exit codes and troubleshooting
- `winget settings` (alias `config`) opens the JSON settings file in the default editor; sub-commands `export`, `set`, `reset`. Administrator-scoped toggles use `--enable`/`--disable` (e.g. `LocalManifestFiles`). [DOC S-vrwvsimi]
- `source.autoUpdateIntervalInMinutes`: default 15, `0` disables the periodic index re-check (checks only happen when a source is used and the interval elapsed); the matching `SourceAutoUpdateInterval` policy notes that the interval has no effect on REST-based sources. [DOC S-vrwvsimi, S-x6zzi6h7]
- `installBehavior.preferences` (soft preference; sorts choices) vs `installBehavior.requirements` (hard filter; can produce zero applicable installers and a failure) both cover `scope`, `locale`, `architectures`, `installerTypes`; any matching CLI argument overrides the `requirements` setting for that invocation only. [DOC S-vrwvsimi]
- `logging.file` cleanup runs at the start of every WinGet process against the default log directory only: `ageLimitInDays` (default 7, 0 disables), `totalSizeLimitInMB` (default 128, 0 disables), `countLimit` (default 0 = disabled), `individualSizeLimitInMB` (default 16, 0 disables, oversized files wrap instead). [DOC S-vrwvsimi]
- `telemetry.disable: true` stops WinGet writing ETW events; `network.downloader` selects `do` (Delivery Optimization, default, can be Group-Policy managed) or `wininet`. [DOC S-vrwvsimi]
- WinGet's own CLI is delivered as an MSIX (packaged) app and MSIX packages can't be registered for `NT AUTHORITY\SYSTEM`, so **the WinGet CLI is not supported in the system context**; the `Microsoft.WinGet.Client` PowerShell module can be used in system context for machine-wide-installed applications instead. [DOC S-bbyce4yg]
- Exit codes: WinGet returns HRESULT-style codes in the `APPINSTALLER_CLI_ERROR_*` (and `WINGET_INSTALLED_STATUS_*`) namespace, generated into `doc/windows/package-manager/winget/returnCodes.md` in the winget-cli repo (MIT) by running `winget error --output <file>`. Examples: `0x8A150002`/-1978335230 `APPINSTALLER_CLI_ERROR_INVALID_CL_ARGUMENTS`; `0x8A15003A`/-1978335174 `APPINSTALLER_CLI_ERROR_BLOCKED_BY_POLICY` ("Operation is blocked by Group Policy"); `0x8A15010F`/-1978334961 `APPINSTALLER_CLI_ERROR_INSTALL_BLOCKED_BY_POLICY`; `0x8A150019`/-1978335207 `APPINSTALLER_CLI_ERROR_COMMAND_REQUIRES_ADMIN`; `0x8A150047`/-1978335161 `APPINSTALLER_CLI_ERROR_CUSTOMHEADER_EXCEEDS_MAXLENGTH` ("Header size exceeds the allowable limit of 1024 characters"); `0x8A15002C`/-1978335188 `APPINSTALLER_CLI_ERROR_UPDATE_ALL_HAS_FAILURE` (`winget upgrade --all` completed with failures). Full 190+ row table in the cited source; not reproduced here. [DOC S-7ddssdnb]
- `winget error <code>` displays a description for known WinGet, MSIX and MSI installer error codes; many EXE-based installers use non-standard codes that may not be displayed. [DOC S-bbyce4yg]
- Package-scope behavior is not fully deterministic for EXE installers: MSIX-based packages honor `--scope` reliably; MSI-based packages usually do; EXE-based installers may ignore the scope argument or infer it from local-admin group membership, and a user-scope install can still trigger UAC. [DOC S-bbyce4yg]
- A `403 Forbidden` on download can mean the ISV's server blocks the WinGet user-agent string (`winget-cli WindowsPackageManager/{version} DesktopAppInstaller/Microsoft.DesktopAppInstaller {version}`) even though a browser download of the same installer works. [DOC S-bbyce4yg]

### Group Policy / CSP (DesktopAppInstaller ADMX)
- All DesktopAppInstaller policies are Computer Configuration, ADMX-backed (`DesktopAppInstaller.admx`), under registry key `HKLM\Software\Policies\Microsoft\Windows\AppInstaller`, path **Windows Components > Desktop App Installer**; MDM delivery is `./Device/Vendor/MSFT/Policy/Config/DesktopAppInstaller/<Name>` and requires SyncML `Format: chr` (ADMX-backed policy encoding). [DOC S-x6zzi6h7]
- Full policy table (ADMX name, friendly name, registry value, effect of Enable/Disable/Not configured, minimum OS): `windows/winget-policies.csv`. [DOC S-x6zzi6h7]
- Additional WinGet Group Policy ADMX/ADML templates (the page says these began with Windows 11) are downloaded as the `DesktopAppInstallerPolicies.zip` release asset on the winget-cli GitHub releases page, and new settings may arrive with each WinGet release. Deploy by copying the `.admx` file to `C:\Windows\PolicyDefinitions` and the matching `.adml` to its language subfolder (e.g. `...\PolicyDefinitions\en-US`), or into the domain Central Store on a DC. [DOC S-7symcqej]
- If `EnableAppInstaller` is disabled, `winget` and `winget -?` still run and show help; every other command reports that the operation is disabled by policy — the binary itself isn't blocked from launching. [DOC S-x6zzi6h7]
- `EnableWindowsPackageManagerCommandLineInterfaces` (Windows 11 24H2+) is a separate gate for the CLI/PowerShell path specifically; it doesn't override `EnableAppInstaller`, and `EnableAppInstaller` isn't overridden by it either — both must allow use for the CLI to work. [DOC S-x6zzi6h7]
- `winget --info` prints the effective Group Policy state (only shown if a policy is manually configured), alongside version, architecture, MSIX version, WinGet directories, legal links and admin settings — useful for confirming which policy is blocking a given behavior. [DER S-bbyce4yg: info fields cross-referenced against the policy table's effects]
- Cross-link: the GroupPolicyTemplate DSC v3 adapter (`Microsoft.Adapter/GroupPolicyTemplate`, ADMX-only) is unrelated to WinGet's own policies — it is a generic adapter for consuming ADMX templates as DSC v3 resources (status in `dsc/releases-feature-matrix.md` and `gpo/dsc-group-policy-adapter.md`), and would not add coverage here since the DesktopAppInstaller policies above are all registry-backed already. [DER S-x6zzi6h7: every policy's ADMX mapping names a registry key under Software\Policies\Microsoft\Windows\AppInstaller, so a GP-object adapter path is unnecessary]

### WinGet Configuration (v2/v3) and DSC v3
- `winget configure -f <file.winget|.dsc.yaml>` (aliases `configuration`, `dsc`) applies a WinGet Configuration file; requires WinGet v1.6.2631+ on Windows 10 1809+/Windows 11. Sub-commands: `show` (display a file's contents without applying), `list` (history of applied configurations), `test` (compare current vs. desired state without applying), `validate`, `export` (`--all`, `--package-id`, or `--module`+`--resource`; appends to an existing output file). Options include `--module-path` (default `%LOCALAPPDATA%\Microsoft\WinGet\Configuration\Modules`), `--processor-path`, `--accept-configuration-agreements`, `-h/--history`. [DOC S-td3e5ov5]
- A v2 configuration file's root is `properties:` containing `configurationVersion` (e.g. `0.2.0`), `assertions:` and `resources:`; each resource is named `{ModuleName}/{DscResource}` and WinGet auto-installs the module from the PowerShell Gallery. The schema comment on the first line (`# yaml-language-server: $schema=https://aka.ms/configuration-dsc-schema/0.2`) establishes the schema the file follows; linked to it, VS Code with the Red Hat YAML extension gives validation and auto-completion. [DOC S-ht6fligp]
- v3 configuration files require WinGet 1.11+ with the `dscv3` processor (distributed as the separate `Microsoft.DesiredStateConfiguration` package, auto-installed by WinGet); they use the DSC v3 document schema directly — `resources:` is a top-level array (not nested under `properties:`), and `metadata.winget.processor.identifier: dscv3` selects the v3 engine. Same `.winget` extension and YAML format as v2; convention is `./.config/configuration.winget`. A conversion guide and a GitHub Copilot CLI skill for v2→v3 migration are published in the WinGet DSC samples repo (`aka.ms/winget-samples`). [DOC S-sgplcdqr]
- v3-only resource types: `Microsoft.DSC.Transitional/RunCommandOnSet` (runs an executable; always reports "not in desired state" on test since it has no test operation; properties `executable`, `arguments`, `exitCode` default 0), `Microsoft.DSC.Transitional/PowerShellScript` (separate `getScript`/`testScript`/`setScript`, runs under pwsh 7), `Microsoft.DSC.Transitional/WindowsPowerShellScript` (same shape, runs under Windows PowerShell 5.1 — use when a script needs a module/feature only available there). [DOC S-sgplcdqr]
- v3 "adapted resources" are PowerShell class-based DSC v2 resources run through a compatibility adapter (`Microsoft.Windows.Developer/*`, `Microsoft.Windows.Settings/*`, `PSDscResources/*` e.g. `Registry`, `Script`, `Service`): unlike v2, the dscv3 processor does **not** auto-install their PowerShell modules — a `RunCommandOnSet` resource (e.g. `Install-PSResource`) must install the module first and every dependent resource needs `dependsOn` on it. Prefer a native v3 resource (`Microsoft.Windows/Registry`) over its adapted v2 equivalent (`PSDscResources/Registry`) — native resources bypass the PowerShell adapter and are markedly faster (a 22-resource `PSDscResources/Registry` block dropping from 30+ minutes to under 2 minutes as `Microsoft.Windows/Registry`). [DOC S-sgplcdqr]
- Measured `winget configure test` evaluation cost per resource: `Microsoft.WinGet/Package` ~8-16s (linear), `RunCommandOnSet` ~5s (linear), native `Microsoft.Windows/Registry` ~3s (linear), `Microsoft.Windows.Settings/*` (adapted) ~95s (variable), `Microsoft.Windows.Developer/*` (adapted) ~30-122s (super-linear, worse elevated), `PSDscResources/Registry` (adapted) ~89-228s and **super-linear** (grows per additional resource); fixed dscv3 processor startup overhead ~23s. Figures are relative guidance from one reference system, not guarantees. [DOC S-sgplcdqr]
- Group Policy can block the WinGet Configuration feature entirely via the `EnableWindowsPackageManagerConfiguration` device policy (Windows 11 24H2+) — same ADMX as the rest of DesktopAppInstaller, see `windows/winget-policies.csv`. [DOC S-x6zzi6h7]
- Always review a configuration file's contents and the trustworthiness of referenced resources/modules before running it; WinGet shows a configuration warning prompt unless it is accepted up front with `--accept-configuration-agreements`. [DOC S-td3e5ov5]
- The DSC v3 engine itself (`dsc` CLI, resource manifest schema, functions, exit codes) is documented in `dsc/cli-reference.md`, `dsc/functions.md`, `dsc/schemas.md` and `dsc/manifests` — this article does not repeat that content; WinGet Configuration v3 is a thin YAML wrapper that shells out to the same `dsc` engine underneath the `dscv3` processor package. [DER S-sgplcdqr: v3 schema doc points at the DSC v3 document schema hosted in the PowerShell/DSC repo, which `dsc/cli-reference.md` already documents from the binary]

### PowerShell module and enterprise/Intune integration
- `Microsoft.WinGet.Client` (PowerShell Gallery) is the PowerShell module for scripting WinGet and can be used in the system context with machine-wide installed applications; bootstrap pattern: `Install-PackageProvider -Name NuGet -Force; Install-Module -Name Microsoft.WinGet.Client -Force -Repository PSGallery; Repair-WinGetPackageManager [-AllUsers] [-Force] [-Latest] [-IncludePrerelease]`. `-Scope AllUsers` on `Install-Module` installs the module in machine scope. [DOC S-bbyce4yg, S-dgnfikws]
- Intune's **Microsoft Store app (new)** app type creates apps from the Microsoft Store catalog (the page links this to the Microsoft Store for Business retirement); it supports UWP, MSIX-packaged desktop apps, and (preview) Win32 apps packaged as `.exe`/`.msi` distributed via the Store; requires the Intune Management Extension on the client and at least two CPU cores. System context is required when the device is Microsoft Entra-registered-only. [DOC S-xgfg5ggj]
- The Microsoft Store app management experience in Intune that replaced the retired Microsoft Store for Business leverages Windows Package Manager. [DOC S-h66nieow]
- For a Microsoft-Store-sourced Win32 app deployed via Intune, `winget show [PackageId]` on a test system reveals the **Installer Url** — either the ISV's external download location or the Microsoft-hosted fallback cache (`cdn.storeedgefd.dsx.mp.microsoft.com`), useful for firewall/proxy allow-listing; this is distinct from `intune/win32-apps.md`'s own (non-Store) Win32 app content pipeline via IntuneWinAppUtil/IME. [DOC S-ig43wzxm]
- Cross-link: packaging and delivering a traditional (non-Store) `.intunewin` Win32 app — Content Prep Tool, detection/requirement rules, dependency and supersedence graphs, Graph `win32LobApp` — is in `intune/win32-apps.md`; that article does not cover WinGet itself, only IME-based Win32 delivery. [DER S-xgfg5ggj: this page covers only Store-sourced apps; non-Store Win32 packaging lives in the linked kb article]

## Reference
- `dsc/cli-reference.md` — the `dsc` binary's own CLI (independent of WinGet); `dsc/functions.md` — DSC v3 configuration-expression functions used inside `dsc`/DSC v3 resource properties (WinGet Configuration v3 resources can use the same function syntax, e.g. `envvar()`, since the underlying engine is the same `dsc` binary).
- `intune/win32-apps.md` — Win32 app packaging/delivery via IntuneWinAppUtil and the Intune Management Extension; back-linked from that article's Reference section to this one for the WinGet/Microsoft-Store app path and WinGet Configuration.
- `gpo/dsc-group-policy-adapter.md`, `dsc/releases-feature-matrix.md` — the unrelated, still-source-only `Microsoft.Adapter/GroupPolicyTemplate` DSC v3 adapter for arbitrary ADMX templates (not WinGet-specific).
- `windows/winget-policies.csv` — full DesktopAppInstaller ADMX/CSP policy table.

## Examples
- SNIPPET: silent, unattended machine-scope install on `PL-LT-00123`, accepting all agreements; context: WinGet CLI, elevated for `--scope machine`; checked: no [DOC S-bx6tsyla: `-e`/`--exact` exact ID match, `--scope machine`, `-h`/`--silent`, `--accept-package-agreements`, `--accept-source-agreements` are all documented install options]
```powershell
winget install --id Git.Git -e --scope machine --silent --accept-package-agreements --accept-source-agreements
```

- SNIPPET: install the `Microsoft.WinGet.Client` module machine-wide and repair a broken WinGet registration, for use from a SYSTEM-context scheduled task on `PL-SRV-0042`; context: PowerShell Gallery, WinGet CLI unsupported as SYSTEM; checked: no [DOC S-bbyce4yg, S-dgnfikws: the module's documented bootstrap pattern (`Install-PackageProvider`, `Install-Module -Scope AllUsers`, `Repair-WinGetPackageManager -AllUsers -Force`) and that this module, not the CLI, is the supported system-context path]
```powershell
Install-PackageProvider -Name NuGet -Force
Install-Module -Name Microsoft.WinGet.Client -Scope AllUsers -Force -Repository PSGallery
Repair-WinGetPackageManager -AllUsers -Force
```

- SNIPPET: minimal v3 WinGet Configuration file that installs a package then sets a registry value with the native resource; context: WinGet 1.11+, `dscv3` processor; checked: no [DOC S-sgplcdqr: `resources:` as a top-level array, `metadata.winget.processor.identifier: dscv3`, `Microsoft.WinGet/Package` and native `Microsoft.Windows/Registry` resource types, `dependsOn`]
```yaml
$schema: https://raw.githubusercontent.com/PowerShell/DSC/main/schemas/2023/08/config/document.json
metadata:
  winget:
    processor:
      identifier: dscv3
resources:
- type: Microsoft.WinGet/Package
  name: InstallVSCode
  properties:
    id: Microsoft.VisualStudioCode
    source: winget
- type: Microsoft.Windows/Registry
  name: EnableLongPaths
  dependsOn:
  - InstallVSCode
  properties:
    keyPath: HKLM\SYSTEM\CurrentControlSet\Control\FileSystem
    valueName: LongPathsEnabled
    valueData:
      DWord: 1
  metadata:
    winget:
      securityContext: elevated
```

- SNIPPET: diagnose a Group-Policy-blocked install (`APPINSTALLER_CLI_ERROR_BLOCKED_BY_POLICY`, `0x8A15003A`) on `PL-LT-00123`; context: WinGet CLI; checked: no [DOC S-7ddssdnb, S-vrwvsimi: `0x8A15003A` is the documented `APPINSTALLER_CLI_ERROR_BLOCKED_BY_POLICY` code (S-7ddssdnb); `winget --info` prints the effective Group Policy state (S-vrwvsimi)]
```cmd
winget --info
winget error 0x8A15003A
```
