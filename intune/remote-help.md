---
topic: intune/remote-help
priority: P2
applies_to: "Microsoft Intune Suite/standalone add-on Remote Help, Windows/macOS/Android/web app (docs current 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-f7i5faki, S-5h4qjmdq, S-f6g2wc4u, S-co4oj66f, S-xa4m3w2n]
status: complete
---

# Intune Remote Help

## Summary
Remote Help is an Intune Suite (or standalone) add-on that lets a helper view or take control of a
sharer's screen, entirely through Microsoft Entra ID sign-in and Intune RBAC — no third-party remote-control
tool. Attended sessions need the sharer to accept; unattended sessions (Windows, physical corporate-owned
devices only, and Android dedicated devices) skip that step and are gated by dedicated RBAC permissions.
Conditional Access can gate the helper's and sharer's sign-in (Windows/macOS only, attended sessions only).
Sessions are logged for reporting/audit (30 days) but never recorded.

## Facts

### Licensing and platforms
- Requires a Remote Help license for every targeted helper and sharer, in addition to Intune Plan 1 or
  Plan 2 (part of Intune Suite, or a standalone EPM-style add-on). [DOC S-f7i5faki]
- Supported for attended control: Windows x86/x64/ARM64, Windows 365, Azure Virtual Desktop (desktop and
  RemoteApp); macOS 13 (Ventura), 14 (Sonoma), 15 (Sequoia), and 26.0 (Remote Help client 1.0.2509231+);
  Android Enterprise dedicated-mode Samsung Knox and Zebra (MX 8.3+) devices; a web app for sharers on
  Safari 16.4.1+, Chrome 109+, Edge 109+, Firefox 122+ (view-only), including macOS 11–14 and Windows 11 —
  Linux isn't supported natively but the web app may work in a supported browser; VMs aren't supported for
  the web app. [DOC S-f7i5faki]
- Unattended control is supported only on Windows (physical, Intune-managed, corporate-owned, x64,
  Entra joined or hybrid joined — not Windows 365/AVD/BYOD/unenrolled) and on Android Enterprise dedicated
  Samsung Knox/Zebra devices (Zebra needs MX 9.3+ for unattended). [DOC S-f7i5faki]
- Government cloud: supported in GCC and GCC High (Windows, Windows ARM64, Windows 365, Samsung/Zebra
  Android dedicated, macOS 13/14/15) but not AVD in GCC/GCC High; not supported at all in DoD tenants.
  [DOC S-f7i5faki]
- Cross-tenant sessions aren't possible: helper, sharer, and target device must all belong to the same
  Entra tenant, since Remote Help's RBAC and compliance integration require it — an outsourced helpdesk
  across tenants needs devices joined to the sharer's tenant (or access to Windows 365/AVD devices joined
  to it). [DOC S-f7i5faki]

### Tenant configuration
- **Tenant administration > Remote Help > Settings**: **Enable Remote Help** (disabled by default),
  **Allow Remote Help to unenrolled devices** (disabled by default — Entra-registered-only devices),
  **Disable chat** (default No, chat enabled). [DOC S-5h4qjmdq]
- After enabling Remote Help or assigning new/trial licenses, activation can take 30 minutes up to several
  hours; sessions may still report "Remote Help isn't enabled" during that window. [DOC S-5h4qjmdq]
- Unenrolled-device support applies only to sharers (Entra-registered devices), never to helpers or to
  unattended control, which requires Intune enrollment. [DOC S-f6g2wc4u, S-f7i5faki]

### RBAC permissions
- Remote Help permission category (assignable in a custom Intune role, `create-custom-role`): **View
  screen**, **Take full control**, **Elevation** (Windows only — lets the helper answer UAC prompts; also
  implicitly grants view/control once the sharer allows it), **Android unattended control** (requires the
  Android device to be Intune-enrolled as a dedicated device; assign explicitly and scope to specific
  devices), **Windows unattended control remote sign-in** (starts an unattended remote-sign-in session to a
  targeted, physical, corporate-owned Windows device without sharer acceptance each time; assign explicitly
  and scope to specific devices). [DOC S-f7i5faki, S-xa4m3w2n]
- A helper also needs **Remote Tasks - Offer remote assistance** and **Remote Assistance Connector - Read**
  (lets the client detect whether Remote Help is configured for the tenant) in addition to at least one
  Remote Help permission above. [DOC S-f7i5faki]
- Built-in roles with Remote Help permissions: **Help Desk Operator** (View screen, Take full control,
  Elevation, Android unattended control, Offer remote assistance, Remote Assistance Connector Read — but
  **not** Windows unattended control remote sign-in) and **School Administrator** (same set minus Android
  unattended control). To grant Windows unattended control, create a custom role. [DOC S-f7i5faki, S-5h4qjmdq]
- If a sharer or their device falls outside a helper's RBAC scope group, that helper can't assist; the
  built-in **All Devices** scope group excludes unenrolled devices, so use a user-based scope group to
  cover unenrolled/BYOD sharers. [DOC S-f7i5faki]
- Recommended pattern: split view-only (tier 1) from full-control/elevation (tier 2), and scope a
  dedicated custom role for unattended control (Windows remote sign-in + Android unattended) to a narrow
  tier-3/senior-admin group and device scope. [DOC S-f7i5faki]

### Conditional Access
- Conditional Access (MFA, compliant device, location) can be applied to helper and sharer sign-in, but
  only for **attended** sessions on **Windows and macOS**; it doesn't apply to unattended access. [DOC S-f7i5faki]

### Sessions: attended vs. unattended
- Attended: the sharer must accept a view or full-control request; the helper can additionally request
  **Elevation** to answer UAC prompts on the sharer's device — enabling elevation also grants view/control
  once accepted. A compliance warning banner appears if the sharer's device fails its assigned compliance
  policy, but compliance doesn't block the session. [DOC S-f6g2wc4u]
- The Windows policy `EnableSecureCredentialPrompting` (Policy CSP AdmxCredUI) blocks the elevation UAC flow
  during Remote Help sessions when enabled; disable it to allow helper elevation. [DOC S-f6g2wc4u]
- Unattended (Windows): initiated from the admin center (**Devices > All devices > select device > New
  remote assistance session > Remote Help > Initiate unattended control**); creates a **separate,
  authenticated Windows session** (not the active user's desktop) governed by sign-in, RBAC and auditing;
  the helper signs in inside the session using a local account (`ComputerName\UserName`), AD domain account
  (`Domain\UserName`), UPN, or Entra UPN — least-privilege applies (a standard account signing in doesn't
  gain admin rights). Only one helper/one unattended session can be active on a device at a time. [DOC S-f6g2wc4u]
- If a user is signed in when unattended control starts, they're notified and can allow/deny; with no
  response the session proceeds automatically after a **30-second** timeout, locking the user's session
  (work preserved) and connecting to a separate Windows session; the user can reclaim control any time by
  signing back in, which notifies the helper. [DOC S-f6g2wc4u]
- Unattended (Android): starts immediately without sharer acceptance on dedicated-mode devices; supported
  helper-app combos and the full attended/unattended support matrix by helper/sharer platform are in
  `intune/remote-help.csv`. [DOC S-f7i5faki]
- Only one helper can hold an unattended connection to a device at a time, and only one unattended session
  can be active on a device at a time. [DOC S-f6g2wc4u]

### Windows unattended control prerequisites
- Target device: physical, Intune-managed, corporate-owned, x64, Entra joined or hybrid joined (not
  virtual/Windows 365/AVD, not BYOD/unenrolled). [DOC S-f7i5faki]
- Requires the **Azure Virtual Desktop Agent** and **Azure Virtual Desktop Agent Bootloader** installed on
  the target device (agent first, then bootloader — deployed as Win32 apps); during bootloader install, leave
  the auto-populated `INVALID_TOKEN` registration token unchanged. [DOC S-f7i5faki, S-5h4qjmdq]
- Requires the **Intune Management Extension (IME)** installed (also needed for remote-launch notifications
  on attended sessions) — see `intune/ime-logs.md`. [DOC S-f7i5faki]
- Requires **Remote Desktop** enabled on the device, deployable via a Windows settings catalog profile
  (**Allow users to connect remotely by using Remote Desktop Services** = Enabled) — firewall must allow RDP
  traffic first. [DOC S-f7i5faki, S-5h4qjmdq]
- Device must be powered on and internet-connected; asleep/hibernating/shut-down devices can't receive
  unattended support. [DOC S-f7i5faki]
- The helper needs **Remote Help app - Windows unattended control remote sign-in** scoped to the target
  device(s). [DOC S-f7i5faki]

### Network endpoints
- Both helper and sharer need outbound access over **port 443 (HTTPS)** to Remote Help's Azure cloud
  endpoints; the service endpoint is `https://remotehelp.microsoft.com`, using RDP over TLS 1.2. SSL
  inspection/"break and inspect" on the corporate proxy breaks the connection unless the Remote Help domains
  are excluded. Full FQDN list: `intune/fundamentals/endpoints#remote-help` (live docs, not duplicated
  here). [DOC S-f7i5faki]

### Windows client and firewall
- Windows Remote Help executables to allow through the firewall for attended sessions: `C:\Program
  Files\Remote help\RemoteHelp.exe`, `RHService.exe`, `RemoteHelpRDP.exe`. [DOC S-5h4qjmdq]
- Latest Remote Help client versions at time of writing: Windows **5.2.1037.0**
  (`https://aka.ms/downloadremotehelp`), macOS **1.0.2509231** (`https://aka.ms/downloadremotehelpmacos`);
  Android client is distributed via Google Play. [DOC S-5h4qjmdq]
- Remote Help requires **Microsoft Edge WebView2** on Windows; install errors 1001 (internal component init
  failed), 1002 (WebView2 load failed), 1003 (WebView2 install failed) point to an Edge/WebView2 problem —
  update Edge, then install WebView2 manually if still failing. WebView2 should already be present on
  Windows 11 or wherever Edge is installed. [DOC S-co4oj66f]
- macOS requires OS permission grants for **Accessibility** and **Screen sharing** (Privacy Preferences
  Policy Control, deployable via settings catalog, bundle id `com.microsoft.remotehelp`); screen sharing's
  "Allow" state can't be pushed silently by MDM even though Accessibility's can — screen sharing can only be
  set to allow a standard user to grant it themselves. [DOC S-5h4qjmdq]
- macOS unenrolled/no-user-affinity devices need the Microsoft Enterprise SSO plug-in configured and the
  user signed in to Company Portal for Remote Help to recognize enrollment; Company Portal isn't supported
  on devices enrolled without user affinity, so those need **Remote Help to unenrolled devices** set to
  Allowed instead. [DOC S-f7i5faki]
- Android requires Managed Google Play set up, the Intune app newer than 5.0.5541.0, CAMERA permission
  (auto-grantable via app configuration policy), and no device policy blocking screen capture; dedicated
  Zebra/Samsung devices need OEM-specific overlay/OEMConfig permission grants (see the deploy page for the
  per-OEM package names and signing certificates). [DOC S-5h4qjmdq]

### Monitoring, logs and reporting
- **Tenant admin > Remote Help > Monitor** shows active session counts and history; the **Remote Help
  sessions** tab lists helper (Provider ID), sharer (Recipient ID), target device, session start/end times,
  and control type (view only, full control, unattended). Android Enterprise dedicated devices show `--`
  for Recipient ID/name (no user affinity). Use of the Windows elevation capability is **not** reported in
  the sessions report. [DOC S-co4oj66f]
- Session metadata (start/end time, who helped whom on what device, features used) is retained on
  Microsoft servers for **30 days**; session content (screen images, keystrokes) is never recorded or
  accessible to Microsoft. [DOC S-f7i5faki, S-co4oj66f]
- Windows install logs: `C:\Users\<username>\AppData\Local\Temp\Remote_help_*_QuickAssist_Win10_x64.msi.log`
  and `Remote_help_*.log`. Operational/session logs: **Event Viewer > Applications and Services Logs >
  Microsoft > Windows > RemoteHelp** (on both helper and sharer devices). [DOC S-co4oj66f]
- Known issues: remote-launch notifications fail if the **Microsoft Intune Management Service** isn't
  running on the sharer's device; a short delay after reboot before that service restarts; newly enrolled
  Windows/Android devices can take up to **1 hour** (Windows) or **15 minutes** (Android) before receiving
  session-initiation push notifications. [DOC S-co4oj66f]

## Reference
- `intune/remote-actions.md`: the admin-center "New remote assistance session" entry point sits alongside
  the Graph `managedDevice` remote actions covered there, but Remote Help itself has no Graph action —
  sessions are started and monitored only through the admin center UI.
- `intune/assignment-filters-and-rbac.md`: Intune RBAC fundamentals (built-in roles, custom role
  permission categories, scope groups/tags) that Remote Help's permission model builds on.
- `entra/conditional-access-devices.md`: grant controls and the Filter for devices condition usable in a
  Remote Help Conditional Access policy (Windows/macOS attended sessions only).
- `intune/endpoint-privilege-management.md`: a separate Intune Suite add-on for standing elevation of
  specific files without an admin present — contrast with Remote Help's Elevation permission, which needs
  a live helper session to answer UAC prompts.
- `intune/ime-logs.md`: Intune Management Extension, required on the Windows target device for Remote
  Help notifications and to orchestrate unattended sessions.
- `intune/remote-help.csv`: helper/sharer platform support matrix (attended view-only/full
  control/elevation, unattended) by client combination.

## Examples
Enable Remote Help and Windows unattended control for a scoped helpdesk group, then start an unattended
session on a lost/locked corporate laptop `PL-LT-00123` (admin center, no Graph API exists for this):

1. **Tenant administration > Remote Help > Settings**: set Enable Remote Help = Enabled.
2. Create a custom Intune role `Remote Help - Unattended` with permission **Remote Help app - Windows
   unattended control remote sign-in**, plus **Remote Tasks - Offer remote assistance** and **Remote
   Assistance Connector - Read**; assign it to the `PL-Helpdesk-Tier3` admin group scoped to the
   `PL-Corp-Windows-Devices` device group.
3. Ensure `PL-LT-00123` has the AVD Agent + Bootloader, Intune Management Extension, and a settings-catalog
   profile enabling Remote Desktop.
4. **Devices > All devices > PL-LT-00123 > New remote assistance session > Remote Help > Initiate
   unattended control**; sign in to the launched session as `corp.example.com\jan.kowalski` or
   `jan.kowalski@corp.example.com`.
