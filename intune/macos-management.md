---
topic: intune/macos-management
priority: P2
applies_to: "Microsoft Intune service, macOS 13 and later, docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-arxx6gr5, S-rdfxhqsp, S-euxtbsnm, S-3t6iud2k, S-wqz6uke5, S-rsfjlxrr, S-4vuqeywj, S-u2qh2hnr, S-hubiwt4q, S-iw63dqdc, S-vtmdq4xp, S-643xsvbr, S-23euutj5, S-wl7oot25]
status: complete
---

# Intune macOS management

## Summary
macOS devices enroll in Intune via **Automated Device Enrollment (ADE)** (formerly Apple DEP, corporate-owned, zero-touch via Apple Business/School Manager), **direct enrollment** (Apple Configurator, no user affinity), or **BYOD device enrollment** (Company Portal, user-driven). **Platform SSO** (settings catalog, Extensible SSO payload) replaces the local-account sign-in with Secure Enclave (recommended, passwordless, phishing-resistant), Smart Card, or Password authentication, and can be pushed during ADE Setup Assistant. **FileVault** disk encryption is configured via an endpoint security Disk encryption policy or the settings catalog, with Intune escrowing and rotating personal recovery keys. **Shell scripts** and **custom attributes** extend management beyond native MDM, both run by the separately-installed **Intune management agent** (`IntuneMdmAgent`), which checks in roughly every 8 hours and logs to `/Library/Logs/Microsoft/Intune` and `~/Library/Logs/Microsoft/Intune`. macOS app deployment types are **LOB (.pkg)**, **DMG (.pkg-free .app bundles)**, and VPP-licensed Store apps. See `intune/compliance-policies.md` for macOS compliance settings and `intune/remote-actions.md` for macOS-supported remote actions.

## Facts

### Enrollment
- Automated Device Enrollment (ADE, formerly Apple DEP) is for corporate-owned Macs purchased through Apple Business Manager or Apple School Manager; devices are supervised by default, support zero-touch/bulk enrollment, single-assigned-user or userless (kiosk) scenarios; BYOD/personal devices and device enrollment manager (DEM) accounts are **not** supported with ADE. [DOC S-arxx6gr5]
- ADE devices already enrolled in another MDM must unenroll from that MDM before enrolling in Intune (no side-by-side management). [DOC S-arxx6gr5]
- ADE supports the ACME protocol for the device's management-profile certificate (better protection than SCEP); ACME requires **macOS 13.1 or later**; already-enrolled devices don't get an ACME cert unless they re-enroll. [DOC S-arxx6gr5]
- Setting up ADE has three tasks: (1) get an enrollment program token (.p7m, trust relationship with Apple Business/School Manager), (2) create and assign an enrollment profile (renamed "enrollment policy" in the newer admin-center experience under **Enrollment program tokens > Enrollment policies**), (3) sync device records from Apple Business Manager and distribute devices. [DOC S-arxx6gr5, S-rdfxhqsp]
- ADE prerequisites: access to Apple Business or Apple School Manager, MDM authority set to Intune, an Apple MDM push certificate in Intune, and an active ADE token (.p7m). [DOC S-arxx6gr5, S-rdfxhqsp]
- A recommendation to create the push certificate with a Managed Apple ID rather than a personal Apple ID is not stated on the ADE overview or setup pages. [UNK: not in S-arxx6gr5 or S-rdfxhqsp as re-read 2026-09-27]
- To make Entra SSO available during Setup Assistant with modern authentication, create the Platform SSO settings-catalog policy **before** devices enroll — it is deployed to enrolling devices during ADE. [DOC S-rdfxhqsp]
- Other enrollment methods: **Direct enrollment** (Apple Configurator, organization-owned kiosk-style devices without user affinity; "Enroll with user affinity" shows in the UI but won't work); **BYOD device enrollment** (user approved enrollment: the user downloads and runs the Company Portal installer package, since Company Portal for macOS isn't in the App Store or VPP, signs in and approves the enrollment policy; devices are marked personal by default). A **device enrollment manager (DEM)** account can be used for BYOD device enrollment but not with ADE or Direct enrollment. [DOC S-euxtbsnm]
- The `https://aka.ms/EnrollMyMac` link, the 1,000-device DEM limit, and Direct enrollment's USB connection and no-wipe behavior are not stated on the macOS enrollment guide. [UNK: not in S-euxtbsnm as re-read 2026-09-27]

### Platform SSO
- Platform SSO (part of the Microsoft Enterprise SSO plug-in, which also includes the separate "SSO app extension" feature) signs users into the Mac itself using Entra ID credentials, replacing local-account sign-in; it is included with all Intune licensing plans. [DOC S-3t6iud2k]
- Requirements: macOS **13.0+**; Company Portal for macOS **5.2404.0+** (older versions make Platform SSO fail); browsers Edge, Chrome (+ Microsoft Single Sign On extension), Safari, or Firefox (MicrosoftEntraSSO policy) for browser SSO. [DOC S-3t6iud2k]
- Three authentication methods: **Secure Enclave** (recommended; passwordless/phishing-resistant, hardware-bound keys, usable as a WebAuthn passkey, requires local-password unlock after reboot then Touch ID, macOS 13.x+), **Smart Card** (passwordless, cert+PIN, macOS 14+ only), **Password** (Entra password replaces/syncs with the local password, Touch ID after first unlock, macOS 13.x+). All three leave the local account intact because FileVault uses the local password as its unlock key. [DOC S-3t6iud2k]
- Required settings-catalog settings (category Authentication > Extensible SSO, then Platform SSO): **Extension Identifier** = `com.microsoft.CompanyPortalMac.ssoextension`; **Authentication Method (Deprecated)** for macOS 13 only (`Password` or `UserSecureEnclaveKey`); **Platform SSO > Authentication Method** for macOS 14+ (`Password`, `UserSecureEnclaveKey`, or `SmartCard`); **Platform SSO > FileVault Policy** = `AttemptAuthentication` (macOS 15+, Password method only); **Platform SSO > Use Shared Device Keys** = Enabled (macOS 14+, shared signing/encryption keys per device); **Registration Token** = `{{DEVICEREGISTRATION}}`; **Screen Locked Behavior** = Do Not Handle; **Token To User Mapping > Account Name** = `com.apple.PlatformSSO.AccountShortName` or `preferred_username`; **Token To User Mapping > Full Name** = `name`; **Team Identifier** = `UBF8T346G9`; **Type** = Redirect; **URLs** = `https://login.microsoftonline.com`, `https://login.microsoft.com`, `https://sts.windows.net` (plus sovereign-cloud urls if needed). Only one SSO policy can be assigned per group. [DOC S-3t6iud2k]
- If both macOS 13 and 14+ devices exist, configure **both** `Authentication Method (Deprecated)` and `Platform SSO > Authentication Method` in the same profile. [DOC S-3t6iud2k]
- Changing **Authentication Method** or **Use Shared Device Keys** on a device with an existing Platform SSO policy forces the device to re-register in Entra; changing/unassigning-then-reassigning any other setting also re-registers it. [DOC S-3t6iud2k]
- Minimum Intune permission to create the settings-catalog policy: Device Configuration Read/Create/Update/Assign (built into the **Policy and Profile Manager** role). [DOC S-3t6iud2k]
- Common errors: `10001` = a required setting is missing or a setting not valid for the redirect payload is present; `10002` = multiple SSO extension payloads on the device (unassign any legacy Device Features "SSO app extension" profile — only the settings-catalog profile should remain). [DOC S-3t6iud2k]
- Company Portal **2508+** is required for Kerberos SSO to on-prem AD/Entra via Platform SSO's Extension Data setting (Apple's Kerberos SSO extension). [DOC S-rsfjlxrr]
- Platform SSO during ADE: requires Company Portal **5.2604.0+**, deployed as a required LOB app (`com.microsoft.CompanyPortalMac` bundle ID only) assigned to the same groups as the Platform SSO policy so Intune prioritizes delivering Company Portal during enrollment. [DOC S-wqz6uke5]
- For Platform SSO during ADE with `Account Name = preferred_username`, that setting overwrites/ignores the LAPS `SamAccountName` value; to keep `onPremisesSamAccountName` working with LAPS, deploy Company Portal **2608.0+** and set **Enable Create First User During Setup** to **false** (user must then authorize three times during enrollment). [DOC S-3t6iud2k]

### FileVault
- FileVault deployment options: **endpoint security Disk encryption policy** (Devices > Endpoint security > Disk encryption > Create Policy > platform macOS > profile MacOS FileVault) or **Settings catalog** under Full Disk Encryption (settings catalog gives the most complete option set, including Setup Assistant enforcement). [DOC S-4vuqeywj]
- **Enable FileVault**: Not configured (default) or Yes — enables XTS-AES 128 full-disk encryption on macOS 10.13+; FileVault activates when the user next signs out. [DOC S-u2qh2hnr]
- **Personal recovery key rotation**: Not configured (default) or **1–12 months**. **Number of times allowed to bypass** the enable prompt: Not configured (default, encryption required at next sign-in), **1–10**, or "No limit, always prompt" (never enforced). **Allow deferral until sign out**: Not configured (default) or Yes. [DOC S-u2qh2hnr]
- Two-stage rollout: (1) **key escrow preparation**, (2) **disk encryption initiation** after the key is escrowed; the personal recovery key is shown to the user once, at first encryption. [DOC S-4vuqeywj]
- Admins can view/rotate FileVault recovery keys only for devices marked **Corporate**; Personal/BYOD device recovery keys are never accessible to admins. Viewing a key requires Intune RBAC **Remote tasks > Rotate FileVault key = Yes** and generates an audit-log entry. [DOC S-4vuqeywj]
- Intune can assume management of a device the user already encrypted, two ways: (1) user uploads the existing personal recovery key via the Company Portal website, which Intune validates then rotates and escrows; or (2) on the device, Terminal: `cd /Applications/Utilities` then `sudo fdesetup changerecovery -personal` to generate a new key, followed by a device check-in. [DOC S-4vuqeywj]
- Setup Assistant FileVault enforcement (encrypt during initial device setup) requires **macOS 14+** and, for the interactively-created Setup Assistant account to work, that account must have Administrator role before macOS 14.4 (later versions relax this); it additionally needs ADE/ASM enrollment with **Await final configuration = Yes** and an `EnrollmentProfileName`-based device filter. [DOC S-4vuqeywj]
- Intune's FileVault settings don't expose every native FileVault capability — only what the endpoint security template or settings catalog surfaces. [DOC S-4vuqeywj]

### Shell scripts and custom attributes
- Shell script policy (Devices > By platform > macOS > Manage devices > Scripts > Add): upload a script **<1 MB**; **Run script as signed-in user** (default No = runs as root); **Script frequency** (default Not configured = runs once, but any configured frequency also reruns after a device restart); **Max number of times to retry if script fails** (default Not configured = no retry). Assigning to a user group applies the script for any user who signs in to that Mac. [DOC S-hubiwt4q]
- Custom attribute profile (Devices > By platform > macOS > Organize devices > Custom attributes for macOS > Add): script's data type must be **String**, **Integer**, or **Date** and must match what the shell script echoes; `Date` values must be ISO-8601 (with or without UTC `Z`); the returned result must be **≤20 KB**. Custom attribute shell scripts run **every 8 hours** on managed Macs. [DOC S-hubiwt4q]
- Custom attribute run statuses: **Failed** (non-zero exit code or malformed script) or **Success** (zero exit code; echoed output shown in the Result column). [DOC S-hubiwt4q]
- macOS custom compliance discovery scripts are **Bash** (vs. PowerShell on Windows, any installed interpreter on Linux); must start with a valid shebang (`#!/bin/bash`), be UTF-8 without BOM, and return exit code 0 for success / non-zero for failure; each compliance policy uses exactly one discovery script, and a script can't be deleted while assigned. [DOC S-iw63dqdc]
- Log collection for macOS shell script/custom attribute policies: admin supplies absolute log file paths separated **only by semicolons, no spaces**; max **60 MB compressed or 25 files**; allowed extensions `.log .zip .gz .tar .txt .xml .crash .rtf`; logs collect at the device's next check-in (~8 hours) and are stored encrypted in Azure for **30 days**. In addition to admin-specified files, the agent always also collects `/Library/Logs/Microsoft/Intune` and `~/Library/Logs/Microsoft/Intune` (`IntuneMDMDaemon date--time.log`, `IntuneMDMAgent date--time.log`). [DOC S-hubiwt4q]
- Log collection error codes: `0X87D300D1`/2016214834 log >60 MB; `0X87D300D1`/2016214831 invalid/system-user path; `0X87D300D2`/2016214830 upload URL expired; `0X87D300D3`/`D5`/`D7` encryption failure on upload; `2016214828` >25 files; `0X87D300D6` zip error. [DOC S-hubiwt4q]

### Intune management agent (macOS)
- The Intune management agent (`IntuneMdmAgent`) is required for management capabilities native macOS MDM doesn't support, such as shell scripts; it installs automatically and silently at `/Library/Intune/Microsoft Intune Agent.app` the first time a Mac is assigned any shell script, and does not appear under Finder > Applications. [DOC S-wl7oot25]
- The agent authenticates and checks for new/updated scripts independently of the MDM check-in, **usually every 8 hours**; a manual check-in can be forced via Company Portal > local device > **Check status**, or Terminal `sudo killall IntuneMdmAgent` (the process restarts and re-checks in immediately). The admin-center **Sync** device action triggers only an MDM check-in, not an agent check-in. [DOC S-wl7oot25]
- The agent is removed from a device when scripts are no longer assigned, the device is no longer managed, or the agent is in an irrecoverable state for more than 24 hours of device-awake time. [DOC S-wl7oot25]

### macOS app types
- **macOS LOB app**: app type is `.pkg` only; the package must be a component package or contain multiple packages (no bundle, disk image, or `.app` inside), must be signed with a **"Developer ID Installer"** certificate from an Apple Developer account, and must contain a payload (a payload-less package keeps reinstalling as long as it's assigned). Max size **2 GB**; an app with no logo isn't shown in Company Portal. Updating a LOB `.pkg` requires incrementing `CFBundleShortVersionString`; a Required app's content update is retried every **24 hours** on install failure. [DOC S-643xsvbr]
- **Install as managed** (Yes/No, default No, macOS 11+): lets the LOB app be removed later via an uninstall assignment, and be auto-removed if the MDM profile is removed; only possible when the package installs a single app (no nested packages) to `/Applications`. [DOC S-643xsvbr]
- **macOS app (DMG)**: the disk image must contain one or more `.app` files (not other installer types); max size **8 GB**; requires the Intune management agent installed on the device, and macOS 13+ needs Full Disk Access (which Intune auto-requests when the DMG policy is assigned) to update/delete the app. A single DMG should hold one app, or several mutually-dependent apps (listed in order, parent app first, under Included apps/Detection rules) — bundling independent apps in one DMG means one install failure is reported as a failure for all and can retrigger reinstall of the others. Updating a DMG app needs agent version **2304.039+** and the same bundle identifier as the original. [DOC S-23euutj5]
- **macOS app (PKG)** (unmanaged) is a separate, simpler app type for uploading an unmanaged `.pkg` (distinct from the signed LOB `.pkg` type). [DOC S-vtmdq4xp]

## Reference
- `intune/compliance-policies.md` documents macOS-applicable compliance checks (custom compliance discovery scripts, JSON rule schema, error codes 65007-65010) that reuse the same Bash-script mechanism as this article's custom attributes; see that article's "Custom compliance settings" section for the shared JSON rule format. Back-link added there is not required since compliance-policies.md already covers Windows/macOS/Linux generically — this article adds the macOS Bash specifics.
- `intune/configuration-policies.md`: the settings catalog mechanics (Not configured semantics, per-setting status reporting, applicability rules) that this article's Platform SSO and FileVault settings-catalog policies are built from.
- `intune/remote-actions.md`: `remoteLock` and `delete` (retire/wipe) support macOS among their platforms; FileVault recovery-key rotation is reachable there via the Rotate FileVault key Remote tasks permission referenced above.
- `entra/device-identity.md`: covers Entra device join/registration generally; Platform SSO's Entra join and workplace-join (WPJ) certificate flow builds on that registration.
- `intune/ios-android-management.md`: iOS/iPadOS and Android enrollment types and ownership models (ADE without-user-affinity, Apple User Enrollment, Android Enterprise work profile/COBO/COSU/COPE, AOSP, deprecated Android DA); reuses this article's ABM/ASM token, Apple MDM push certificate, and ACME-vs-SCEP facts rather than repeating them.

## Examples
- SNIPPET: shell script that echoes a custom attribute (macOS build number) for a policy scoped to devices in tenant `00000000-0000-0000-0000-000000000000`; context: macOS custom attribute profile, data type String, result ≤20 KB; checked: no [DOC S-hubiwt4q]
```bash
#!/bin/sh
sw_vers -buildVersion
```

- SNIPPET: custom attribute error troubleshooting: collecting the Intune management agent's own log plus a custom attribute script's log from device `PL-LT-00123`, in one Collect logs request (paths separated only by semicolons, no spaces); context: macOS Collect logs, max 60 MB compressed or 25 files, allowed extensions `.log .zip .gz .tar .txt .xml .crash .rtf`; checked: no [DOC S-hubiwt4q]
```
/Library/Logs/Microsoft/Intune/IntuneMDMAgent.log;/var/log/mycompany/attribute-script.log
```

- SNIPPET: Terminal commands to hand FileVault management to Intune on a previously self-encrypted Mac (Method 2, generate a new key); context: macOS Terminal, followed by a device check-in; checked: no [DOC S-4vuqeywj]
```bash
cd /Applications/Utilities
sudo fdesetup changerecovery -personal
```
