---
topic: auth/msal-public-client
priority: P0
applies_to: "MSAL Python (msal[broker] 1.33.x), Windows 10/11, Windows Server 2019+"
retrieved_utc: 2026-09-24
sources: [S1270, S1271, S1272, S1273, S1274, S1227, S1296]
status: partial
---

# MSAL Python on Windows: WAM broker, device code, Token Protection

## Summary
- WAM (Web Account Manager) broker support in MSAL Python needs the `msal[broker]` extra and requires Windows 10+ / Server 2019+; a specific redirect URI form is mandatory. [DOC S1270]
- Conditional Access can target and block the device code flow specifically via the *authentication flows* condition. [DOC S1272, S1273]
- Token Protection binds sign-in session tokens to the device; for native apps it is enforceable on Exchange Online, SharePoint Online and Microsoft Teams (plus Azure Virtual Desktop and Windows 365 on Windows). Microsoft Graph is not a listed resource, so general MSAL public-client Graph calls are not a stated target. [DOC S1274, S1227]

## Facts
- Installing `pip install msal[broker]>=1.33,<2` adds the broker-capable variant of MSAL Python needed to use WAM. [DOC S1270]
- WAM is only available on Windows 10 and above and Windows Server 2019 and above; on unsupported platforms MSAL falls back to a non-broker flow. [DOC S1270]
- The redirect URI registered on the app must be in the form `ms-appx-web://microsoft.aad.brokerplugin/<client_id>` for the broker to work. [DOC S1270]
- WAM requires a parent window handle; MSAL Python offers `CONSOLE_WINDOW_HANDLE` as a stand-in for console/CLI apps with no visible window, so a CLI tool can use the broker without a GUI. [DOC S1270] — directly relevant to any workstation CLI.
- A `SerializableTokenCache` (or msal-extensions persistent cache) is needed to persist the token cache across CLI invocations. [DOC S1270]
- Public client apps can get tokens silently via Integrated Windows Authentication (Kerberos) when the app runs on a domain- or Entra-joined Windows machine; this is separate from the WAM broker path. [DOC S1271]
- Conditional Access exposes an "Authentication flows" condition; checking "Device code flow" and setting the grant control to Block stops all OAuth 2.0 Device Authorization Grant attempts in the tenant (or for the assigned scope). [DOC S1272][DOC S1273]
- Microsoft's own guidance recommends blocking device code flow wherever possible, calling it high-risk (phishing, code-of-conduct on unmanaged devices). [DOC S1272] — a `client`/`site` instance that assumed device-code fallback as a resiliency path must not rely on it if the tenant follows this guidance.
- Token Protection (Conditional Access) requires the sign-in session tokens (such as the PRT) that apps present to be bound to the device. On Windows it is documented for an enumerated list of Microsoft native apps (Office apps, Outlook, Teams, OneDrive, Microsoft Graph PowerShell with WAM, Visual Studio Code, Windows App and others) accessing **Exchange Online, SharePoint Online, Microsoft Teams, Azure Virtual Desktop and Windows 365**; arbitrary Graph-calling public clients are not stated as covered. [DOC S1274, S1227]
- Token Protection is documented as supporting **native applications only** ("Mobile apps and desktop clients" in the Client Apps condition); browser-based apps (MSAL.js, e.g. Teams Web) are explicitly excluded and can be blocked if the Client Apps condition is left unscoped. [DOC S1274]
- The Windows deployment guide requires Microsoft Entra ID P1 and says Token Protection policies are currently available only for Windows and Apple devices. [DOC S1274]
- Platform coverage per the concept page: native apps are generally available on Windows, iOS/iPadOS and macOS (its device-requirements heading still reads "Apple (Preview)"); browser-based support is in preview only for selected web apps that access Azure Resource Manager, on Windows and macOS. [DOC S1227]
- Nothing in the fetched pages names MSAL Python specifically. The documented boundary is by client *type* (native vs. browser), not by MSAL language binding, so a Windows MSAL Python public client CLI falls on the "native application" side; but the Windows guide enumerates its supported applications (all Microsoft apps), and its unbound status code 1008 (client not integrated with the platform broker, WAM) indicates binding depends on WAM integration, so such a client is at most a candidate, not a documented supported app. [DER S1274]
- CAE readiness (`cp1`) is a separate mechanism from Token Protection: `PublicClientApplication(client_id, client_capabilities=["cp1"])` tells Entra the client can handle claims challenges, which lets Entra issue CAE-capable access tokens to that client for CAE-aware resources (e.g. Graph); the app must then handle a claims challenge from the resource by decoding the returned `claims` and re-acquiring a token with `claims=<that value>`. [DOC S1296]
- `cp1` and Token Protection are independent: declaring `cp1` makes the client CAE-aware; it does not itself bind tokens to the device (that is Token Protection's job, enforced by Conditional Access, not by the `client_capabilities` flag). [DER S1296,S1274]

## Reference
| Behaviour | Requirement | Source |
|---|---|---|
| WAM broker | `msal[broker]`, Windows 10+/Server 2019+, redirect URI `ms-appx-web://microsoft.aad.brokerplugin/<client_id>`, window handle (or `CONSOLE_WINDOW_HANDLE`) | S1270 |
| IWA silent token | domain- or Entra-joined Windows machine | S1271 |
| Device code flow block | Conditional Access → Conditions → Authentication flows → Device code flow → Block | S1272, S1273 |
| Token Protection | registered device, native apps; resources EXO, SPO, Teams (+ AVD, Windows 365 on Windows); Entra ID P1 | S1274, S1227 |

## Examples
- A workstation CLI on engineer workstation `PL-LT-00123`, tenant `00000000-0000-0000-0000-000000000000`: `PublicClientApplication(..., enable_broker_on_windows=True)` with `parent_window_handle=msal.CONSOLE_WINDOW_HANDLE`.

## Open items
- QA5 (MSAL Python + WAM requirements, redirect URI, headless/jump-host behaviour, CA blocking device code) — answered above; jump-host/headless WAM behaviour on Windows Server itself beyond "supported OS" is [UNK] (no explicit statement of headless-session caveats found in three searches).
- QA6 (Token Protection applying to MSAL Python public clients / Graph calls; cp1 in MSAL Python) — answered: Token Protection scopes to native clients on Windows, macOS and iOS/iPadOS (GA per the concept page), P1-licensed, and is client-type-based not language-binding-based, so a Windows MSAL Python CLI qualifies as a candidate client even though no page names MSAL Python specifically [DER S1274, S1227]; `cp1`/CAE-readiness is a separate, directly-supported MSAL Python constructor argument [DOC S1296].
