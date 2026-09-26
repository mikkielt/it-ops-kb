---
topic: windows/kiosk-assigned-access
priority: P2
applies_to: "Windows 10/11 client (single-app kiosk since 1803, ShellLauncher since 1803/v2, multi-app via provisioning/CSP), Intune kiosk profile template and settings catalog, Microsoft Edge kiosk mode 87+"
retrieved_utc: 2026-09-26
sources: [S-c6tea7ux, S-ocgh5a3g, S-snqf6qj3, S-hkbq4xlj, S-grpxcouj, S-mti33mjr, S-pjgeqktu, S-jnbupokh, S-qd4qftlt]
status: partial
---

# Windows kiosk: Assigned Access, AssignedAccess CSP, Shell Launcher, and Intune kiosk profiles

## Summary
Windows kiosk/restricted user-experience is built on the **AssignedAccess CSP**, applied via an XML *AssignedAccessConfiguration*
file (single-app or multi-app), the older `ShellLauncher` node (replaces `Explorer.exe` with a custom shell for
kiosks/ATMs/signage), or the local `Set-AssignedAccess`/Windows Settings path for a single device with a local account.
[DOC S-c6tea7ux] Intune exposes the same mechanism through the **Templates > Kiosk** profile (single-app, full-screen or
multi-app) and through **Templates > Custom** OMA-URI against the CSP directly; see `intune/configuration-policies.md`
for how any custom OMA-URI profile is delivered and refreshed, and `windows/app-control.md` for how a multi-app kiosk's
allowed-apps list is enforced with generated AppLocker rules under the hood.

## Facts
### AssignedAccess CSP nodes
- `./Vendor/MSFT/AssignedAccess` has five nodes: `Configuration`, `KioskModeApp` (deprecated), `ShellLauncher`, `Status`, `StatusConfiguration`; once the CSP is executed, the *next* user sign-in tied to the Assigned Access profile puts the device in kiosk mode. [DOC S-c6tea7ux]
- `Configuration` (string, Add/Delete/Get/Replace) takes the AssignedAccessConfiguration XML; scope is device-only, editions Pro/Enterprise/Education/IoT Enterprise, from Windows 10 1709 (10.0.16299) onward. [DOC S-c6tea7ux]
- `KioskModeApp` (string, Windows 10 1507+) takes JSON `{"Account":"domain\\user","AUMID":"..."}`; from 1803 onward it is a no-op if `Configuration` is set, and the two nodes **cannot both be set** on a device at the same time. It is deprecated in favor of the single-app kiosk profile inside `Configuration`. [DOC S-c6tea7ux]
- `ShellLauncher` (string, Windows 10 1803+, Enterprise/Education/IoT Enterprise editions only — **not supported on Pro**) takes a ShellLauncherConfiguration XML; setting it via CSP automatically enables the Shell Launcher feature if present in the SKU. `ShellLauncher` and `KioskModeApp`/single-app `Configuration` also cannot coexist. [DOC S-c6tea7ux]
- `Status` (read-only, Windows 10 1809+) reports kiosk health only when `StatusConfiguration` is `On`/`OnWithAlerts`; status codes: `0` Unknown, `1` Running, `2` AppNotFound (kiosk app not deployed), `3` ActivationFailed (sign-in failed), `4` AppNoResponse (app launched but hung). Payload also includes `profileId` and an `OperationList` of failed apply operations. [DOC S-c6tea7ux]
- `StatusConfiguration` takes `StatusEnabled` = `Off` (default)/`On`/`OnWithAlerts`; `OnWithAlerts` makes Assigned Access push an MDM alert (`MDMAlertType: com.microsoft.mdm.assignedaccess.status`, `MDMAlertMark: Critical`) immediately when the runtime status changes to an error. [DOC S-c6tea7ux]

### Configuration XML: profiles, configs, versioning
- The XML root is `AssignedAccessConfiguration`; it has one or more `Profiles` (each an app allow-list) and one or more `Configs` (each maps a user/group to a profile). [DOC S-ocgh5a3g]
- Namespace/version selects available features: default (`.../2017/config`), `rs5` (`.../201810/config`, Windows 10), `v3` (`.../2020/config`, Windows 10), `v5` for Windows 10 (`.../202010/config`) and separately `v4` for Windows 11 21H2 (`.../2021/config`) and `v5` for Windows 11 22H2+ (`.../2022/config`); version-specific elements must be tagged with their namespace alias (e.g. `v5:StartPins`). [DOC S-ocgh5a3g]
- A profile is either `KioskModeApp` (single UWP app via `AppUserModelId`, or a desktop app via `v4:ClassicAppPath`/`v4:ClassicAppArguments`) — only one such profile per XML file and it can only target a user, never a group — or `AllAppList` (multiple UWP/desktop apps in `AllowedApps`, each `App` with `AppUserModelId` or `DesktopAppPath`, optional `rs5:AutoLaunch`/`rs5:AutoLaunchArguments` on exactly one app); multiple `AllAppList` profiles are allowed. [DOC S-ocgh5a3g]
- Default kiosk-exit sequence is Ctrl+Alt+Del; `<BreakoutSequence Key="...">` overrides it for a `KioskModeApp` profile. [DOC S-ocgh5a3g]
- Multi-app (`AllAppList`) generates AppLocker rules for the allowed apps; a dependency app must also be explicitly listed. [DOC S-ocgh5a3g]
- `FileExplorerNamespaceRestrictions` controls folder browsing in a restricted experience: empty/absent blocks everything; `rs5:AllowedNamespace Name="Downloads"` allows Downloads; `v3:AllowRemovableDrives` allows removable drives (combinable); `v3:NoRestriction` removes all restriction. Add `Explorer.exe` to the allowed-apps list and pin it to grant File Explorer access at all. [DOC S-ocgh5a3g]
- Start layout: Windows 10 uses `<StartLayout>` with an exported LayoutModificationTemplate XML in CDATA; Windows 11 uses `<v5:StartPins>` with an exported JSON pin list instead. Taskbar visibility is `<Taskbar ShowTaskbar="true|false"/>` on both; Windows 10 restricted experiences cannot pin apps to the taskbar (`CustomTaskbarLayoutCollection` unsupported there), while Windows 11 supports `v5:TaskbarLayout` with a full custom pinned layout. An app referenced in the Start layout but not installed for the user simply doesn't show. [DOC S-ocgh5a3g]
- `Configs/Config` targets an `<Account>` (local `user`/`.\user`/`devicename\user`, AD `domain\samAccountName`, or Entra `AzureAD\{UPN}`) or a `<UserGroup Type="LocalGroup|ActiveDirectoryGroup|AzureActiveDirectoryGroup" Name="...">`; group configs can only use a restricted-experience (`AllAppList`) profile, never a kiosk (`KioskModeApp`) profile, and nested groups are not evaluated (a user in a sub-group of the targeted group is not covered). [DOC S-ocgh5a3g]
- `<AutoLogonAccount>` makes Assigned Access create/manage a local standard-user account that signs in automatically on restart (optionally with `rs5:DisplayName`); it does not work while Exchange ActiveSync password restrictions are active on the device. `<v3:GlobalProfile Id="{GUID}">` applies a profile to every non-admin sign-in (frontline/shared-device scenario); a user with a non-global profile assigned does not also get the global one. [DOC S-ocgh5a3g]
- Constraints: the account/group targeted by a Config must already exist on the device before applying (local accounts especially); an **admin account cannot** be assigned a restricted-experience profile; and a profile must not be assigned to users/groups subject to conditional access requiring interaction (MFA, Terms of Use) or sign-in fails. [DOC S-ocgh5a3g]
- On Entra-joined/domain-joined devices, local accounts are hidden from the sign-in screen by default; showing them needs GPO **Computer Configuration > Administrative Templates > System > Logon > Enumerate local users on domain-joined computers**, or the Policy CSP `./Device/Vendor/MSFT/Policy/Config/WindowsLogon/EnumerateLocalUsersOnDomainJoinedComputers`. [DOC S-ocgh5a3g]

### Shell Launcher (v1/v2)
- Shell Launcher replaces `Explorer.exe` with a custom shell (kiosks, ATMs, digital signage) but does **not** by itself block access to other apps/system components — that needs CSP/GPO/AppLocker on top. Supported editions: Enterprise/Enterprise LTSC, Education, IoT Enterprise/IoT Enterprise LTSC (not Pro). [DOC S-hkbq4xlj]
- v1 (original) replaces Explorer with `Eshell.exe` and can only launch a Win32 desktop app as the shell. v2 (Windows 10 1809+) replaces Explorer with `CustomShellHost.exe`, can launch either a Win32 or a UWP app as the shell, supports multi-monitor secondary views, and can launch other apps full-screen on demand from the custom shell. [DOC S-hkbq4xlj]
- Limitations: a custom shell cannot be set before OOBE (the resulting image can't then be deployed), and Shell Launcher cannot host an app that spawns a different process and exits (e.g. `write.exe` launching `wordpad.exe`) — it monitors the original process's exit code, not the child. [DOC S-hkbq4xlj]
- The custom shell runs with the signed-in account's rights; if the shell app needs elevation and UAC is enabled, UAC must be disabled for the shell to launch. [DOC S-hkbq4xlj]

### PowerShell and local setup
- `Set-AssignedAccess` (module `AssignedAccess`) configures a **single local user account** to a single Windows Store app by `-UserName`/`-UserSID` plus `-AppName` or `-AppUserModelId`; the account must have signed in at least once when using `-AppName`. Supported on Windows 10/11 client only (not Server). If a user is signed in, or the device has a PS/2 keyboard, a restart is required to apply. Exit assigned access on-device with five quick presses of the left Windows key; remove the config with `Clear-AssignedAccess`. [DOC S-jnbupokh, S-mti33mjr]
- `Get-AppxPackage -User "username"` lists the Store apps available to a user (source list for `-AppName`/`-AppUserModelId`). [DOC S-jnbupokh]
- Advanced local/off-CSP delivery uses the MDM Bridge WMI Provider `MDM_AssignedAccess` class (`root\cimv2\mdm\dmmap`, properties `Configuration`, `KioskModeApp`) run as SYSTEM (e.g. via `psexec -i -s powershell.exe`), or a provisioning package at path `AssignedAccess/MultiAppAssignedAccessSettings`. [DOC S-mti33mjr]

### Troubleshooting and logs
- Event log: **Applications and Services Logs > Microsoft > Windows > AssignedAccess > Operational**. [DOC S-grpxcouj]
- Registry: applied Assigned Access configuration lives under `HKLM\Software\Microsoft\Windows\AssignedAccessConfiguration` and `HKLM\Software\Microsoft\Windows\AssignedAccessCsp`; the per-signed-in-user configuration is under `HKCU\SOFTWARE\Microsoft\Windows\AssignedAccessConfiguration`. [DOC S-grpxcouj]
- Recommendation: use a least-privilege local standard account for public-facing kiosks (not an AD/Entra domain account, to limit blast radius if the kiosk is compromised); enable auto sign-in via the AutoLogonAccount XML element, or by hand via `HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon` values `AutoAdminLogon=1`, `DefaultUserName`, `DefaultPassword`, and (domain accounts only) `DefaultDomainName`. The Policy CSP `WindowsLogon/PreferredAadTenantDomainName` setting can break auto sign-in if misapplied. [DOC S-grpxcouj]

### Intune kiosk profile (Templates > Kiosk)
- Path: **Devices > Manage devices > Configuration > Create > New policy**, platform **Windows 10 and later**, profile type **Templates > Kiosk**; Intune supports **one kiosk profile per device** — a device needing several kiosk configurations instead needs a custom OMA-URI profile against the CSP. [DOC S-snqf6qj3]
- Kiosk mode choices: **Not configured** (default, Intune doesn't touch the setting), **Single app, full-screen kiosk**, **Multi app kiosk**. Multi-app kiosk via this template is documented for **Windows 10 only**; Windows 11 multi-app lockdown is configured separately (`windows/configuration/lock-down-windows-11-to-specific-apps`, not yet covered in this kb). Windows 10 reached end of support 2025-10-14 but remains an Intune-allowed OS version with no functionality guarantee. [DOC S-snqf6qj3]
- Single-app kiosk **User logon type** options: **Auto logon** (Windows 10 1803+, uses the AssignedAccess CSP, no user credential needed), **Local user account**, or **Microsoft Entra user or group** (Windows 10 1803+, multi-select). [DOC S-pjgeqktu]
- Single-app **Application type** options: Microsoft Edge (version 87+, configured further via the settings catalog — see `intune/configuration-policies.md`) with **Edge Kiosk URL**, **Edge kiosk mode type** (Public Browsing InPrivate, or Digital/Interactive Signage) and **Refresh browser after idle time** (0–1440 minutes); Microsoft Edge Legacy (77 and 45-and-older) configured via a device-restrictions profile instead; or the separately-installed **Kiosk browser** Store app (Default home page URL, home button show/hide). [DOC S-pjgeqktu]
- Multi-app kiosk lets an admin add several Store apps, Win32 apps, browsers or inbox Windows apps (referenced by AUMID); only the listed apps are available on the device. [DOC S-pjgeqktu, S-snqf6qj3]
- Creating the profile requires at minimum the **Policy and Profile Manager** built-in role (same as other device-configuration profile types — see `intune/configuration-policies.md`). [DER S-snqf6qj3: the article's Create-the-profile steps use the same Devices > Configuration workflow gated by that role in the settings-catalog article]

### Microsoft Edge kiosk mode (standalone, applies to 87+)
- Two lockdown experiences, both run in an Edge **InPrivate** session (autofill disabled): **Digital/Interactive Signage** (full-screen single site) and **Public-Browsing** (limited multi-tab InPrivate browser). [DOC S-qd4qftlt]
- Command-line invocation: `msedge.exe --kiosk <url> --edge-kiosk-type=fullscreen` (signage) or `--edge-kiosk-type=public-browsing`; `--kiosk-idle-timeout-minutes=<0-1440>` resets the session after idle time (default 0/off for full-screen, 5 minutes for public browsing) but does **not** restart Edge itself — Assigned Access or Shell Launcher must relaunch it. `--no-first-run` suppresses the first-run experience. [DOC S-qd4qftlt]
- Single-app kiosk support for Edge (via Assigned access) needs Windows 10 2004+ with KB4601382+, or 1909 with KB4601380+. Functional limitations: several Edge policies (InPrivateModeAvailability, IsolateOrigins, ManagedFavorites, Extensions, BackgroundModeEnabled, etc.) are **not supported** in kiosk mode and should be left/turned off. [DOC S-qd4qftlt]
- Common Open/Save file dialogs are not auto-locked-down in kiosk mode; use the `ConfigureKeyboardShortcuts` policy to disable the shortcuts that reach them. [DOC S-qd4qftlt]

## Reference
- `intune/configuration-policies.md` — settings catalog and custom OMA-URI delivery mechanics (check-in/refresh cadence, `deviceManagementConfigurationPolicy`, role requirements) that any custom `AssignedAccess` OMA-URI profile or Edge settings-catalog policy in a kiosk deployment relies on. Back-link added there under Reference.
- `windows/app-control.md` — AppLocker rules generated for a multi-app kiosk's allowed-apps list run under the same rule-collection mechanics documented there (Executable/Packaged apps collections).
- Whether Intune's Windows 11 multi-app kiosk equivalent (`lock-down-windows-11-to-specific-apps`) and its own settings/limits are the same as the Windows 10 template path was not researched this pass; flagged as a gap. [UNK]

## Examples
Single-app kiosk, AssignedAccess CSP custom OMA-URI (auto-logon local account running Microsoft Edge full-screen against an intranet site):
```xml
<?xml version="1.0" encoding="utf-8" ?>
<AssignedAccessConfiguration xmlns="http://schemas.microsoft.com/AssignedAccess/2017/config"
    xmlns:v4="http://schemas.microsoft.com/AssignedAccess/2021/config"
    xmlns:rs5="http://schemas.microsoft.com/AssignedAccess/201810/config">
    <Profiles>
        <Profile Id="{00000000-0000-0000-0000-000000000001}">
            <KioskModeApp v4:ClassicAppPath="%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
                          v4:ClassicAppArguments="--kiosk https://intranet.corp.example.com/ --edge-kiosk-type=fullscreen --kiosk-idle-timeout-minutes=5" />
        </Profile>
    </Profiles>
    <Configs>
        <Config>
            <AutoLogonAccount rs5:DisplayName="Lobby kiosk"/>
            <DefaultProfile Id="{00000000-0000-0000-0000-000000000001}"/>
        </Config>
    </Configs>
</AssignedAccessConfiguration>
```
OMA-URI row for the above: `./Vendor/MSFT/AssignedAccess/Configuration`, data type String (XML file), value = the XML above (escaped or CDATA-wrapped per the CSP's escaping rules).

Local single-device setup with PowerShell (Calculator UWP app, local account `kioskuser` on `PL-LT-00123`):
```powershell
Set-AssignedAccess -UserName "kioskuser" -AppUserModelId "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"
# remove later:
# Clear-AssignedAccess
```

Multi-app restricted experience: allow Calculator, Notepad and Explorer, autolaunch Notepad, allow Downloads-only File Explorer access:
```xml
<AllAppsList>
  <AllowedApps>
    <App AppUserModelId="Microsoft.WindowsCalculator_8wekyb3d8bbwe!App" />
    <App DesktopAppPath="C:\Windows\System32\notepad.exe" rs5:AutoLaunch="true" />
    <App DesktopAppPath="%windir%\explorer.exe" />
  </AllowedApps>
</AllAppsList>
<rs5:FileExplorerNamespaceRestrictions>
    <rs5:AllowedNamespace Name="Downloads"/>
</rs5:FileExplorerNamespaceRestrictions>
```
