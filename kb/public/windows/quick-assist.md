---
topic: windows/quick-assist
priority: P3
applies_to: "Quick Assist on Windows 10/11 (Store app) and macOS (doc updated 2025-09-30)"
retrieved_utc: 2026-11-09
sources: [S-epdbw32e]
status: complete
---

# Quick Assist: connecting to a user's PC

## Summary
- Quick Assist shares a Windows or macOS device over a remote connection: the helper (support staff) can view, annotate or, with permission, take control.
- Flow: the helper starts Quick Assist, selects **Help someone**, signs in with a Microsoft account or Entra ID, and reads out the time-limited security code; the sharer types it and allows screen sharing.
- It involves no roles, policies or domain; for one Entra tenant Microsoft points to Intune Remote Help instead.

## Facts
- Quick Assist lets a person share a Windows or macOS device with another person; support staff can view the display, annotate or take full control to troubleshoot. [DOC S-epdbw32e]
- Requirements: both parties need internet access allowing HTTPS to the required Microsoft endpoints; no roles, permissions or policies are involved and neither party needs to be in a domain. [DOC S-epdbw32e]
- The helper must have a Microsoft account (sign-in with an MSA or Microsoft Entra ID; local Active Directory authentication is not supported); the sharer does not have to authenticate. [DOC S-epdbw32e]
- Either side can start it: search for Quick Assist, press Ctrl+Windows+Q, or find it in the Start menu (Windows Accessories on Windows 10, All Apps on Windows 11). [DOC S-epdbw32e]
- Session steps: the helper selects **Help someone** (and may need to choose an account or sign in) and Quick Assist generates a time-limited security code; the helper passes it to the sharer by phone or messaging; the sharer enters it under **Security code from assistant** in **Get help** and selects **Submit**; the sharer selects **Allow** for screen sharing; the helper may then select **Request control** and the sharer answers **Allow** or **Deny**. [DOC S-epdbw32e]
- Where helper and sharer differ in keyboard layout or mouse settings, the sharer's are used. [DOC S-epdbw32e]
- Network: port 443 to the Remote Assistance Service `https://remoteassistance.support.services.microsoft.com` over RDP, TLS 1.2; both sides must reach a list of endpoints including `*.support.services.microsoft.com`, `login.microsoftonline.com`, `aadcdn.msauth.net`, `*.live.com` and Azure Communication Service hosts. [DOC S-epdbw32e]
- Quick Assist uses the Edge WebView2 control: built in on Windows 11; on Windows 10 the Store app installs it at launch if missing. [DOC S-epdbw32e]
- Install: Microsoft Store, or deploy through Intune as a Microsoft Store app; Quick Assist for macOS is distributed only through Microsoft Support interactions. [DOC S-epdbw32e]
- Microsoft's page recommends Intune Remote Help over Quick Assist when an organization works within a single Entra tenant, naming Conditional Access enforcement, RBAC, session logging and auditing, tenant isolation and Defender for Endpoint integration. [DOC S-epdbw32e]
- Privacy: Microsoft logs session start and end times, Quick Assist errors and feature use; no logs are created on either device; the sharer sees only the helper's first name and last initial; data is kept at most three days. [DOC S-epdbw32e]
- Disabling in an organization: block traffic to `remoteassistance.support.services.microsoft.com`, or uninstall with `Get-AppxPackage -Name MicrosoftCorporationII.QuickAssist | Remove-AppxPackage -AllUsers`; blocking the endpoint also disrupts Remote Help, which relies on it. [DOC S-epdbw32e]
- Safety guidance: allow a helper to connect only if you initiated the contact with Microsoft Support or your IT staff; disconnect and report if the connecting person seems malicious. [DOC S-epdbw32e]
- How it fits (help desk): in an Intune-managed Entra tenant the page's own advice is Remote Help; see `intune/remote-help.md`. [DER S-epdbw32e: the page's comparison of Remote Help and Quick Assist]

## Reference
| Item | Value | Source |
|---|---|---|
| Shortcut | Ctrl+Windows+Q | S-epdbw32e |
| Transport | RDP over HTTPS port 443, TLS 1.2 | S-epdbw32e |
| Primary endpoint | `remoteassistance.support.services.microsoft.com` | S-epdbw32e |
| Helper sign-in | Microsoft account or Entra ID | S-epdbw32e |

## Examples
- None.
