---
topic: auth/msal-public-client
priority: P0
applies_to: "MSAL Python (msal[broker] 1.33.x), Windows 10/11, Windows Server 2019+"
retrieved_utc: 2026-09-26
sources: [S1270, S1271, S1272, S1273, S1274, S1227, S1296, S-o4jltpni, S-muxg36ky]
status: partial
---

# MSAL Python on Windows: WAM broker, device code, Token Protection

## Summary
- WAM (Web Account Manager) broker support in MSAL Python needs the `msal[broker]` extra and requires Windows 10+ / Server 2019+; a specific redirect URI form is mandatory. [DOC S1270]
- Conditional Access can target and block the device code flow specifically via the *authentication flows* condition. [DOC S1272, S1273]
- Token Protection binds sign-in session tokens to the device; for native apps it is enforceable on Exchange Online, SharePoint Online and Microsoft Teams (plus Azure Virtual Desktop and Windows 365 on Windows). Microsoft Graph is not a listed resource, so general MSAL public-client Graph calls are not a stated target. [DOC S1274, S1227]

## Facts
- The WAM article installs the broker-related packages with `pip install msal[broker]>=1.20,<2`; without them, using the broker raises an ImportError naming that command. The app then sets `enable_broker_on_windows=True` on `PublicClientApplication`. [DOC S1270]
- WAM is only available on Windows 10 and above and Windows Server 2019 and above. [DOC S1270]
- On Mac, Linux and earlier Windows versions MSAL falls back to a browser (stated on the identity-platform WAM page, whose sample is MSAL.NET). [DOC S1271]
- The redirect URI registered on the app must be in the form `ms-appx-web://microsoft.aad.brokerplugin/<client_id>` for the broker to work. [DOC S1270]
- WAM requires a parent window handle; MSAL Python offers `CONSOLE_WINDOW_HANDLE` as a stand-in for console/CLI apps with no visible window, so a CLI tool can use the broker without a GUI. [DOC S1270] — directly relevant to any workstation CLI.
- MSAL Python's default token cache is in memory for the app session; persisting it across sessions (e.g. CLI invocations) needs custom serialization, and for a public client the whole cache can be serialized to a file, with file locking if accessed concurrently (`SerializableTokenCache` example). [DOC S-muxg36ky]
- Integrated Windows Authentication (IWA) signs in a domain user silently on a domain- or Microsoft Entra-joined machine, only for federated+ (AD-backed) users, and it does not bypass MFA; the IWA page states the flow is not yet supported in MSAL Python. [DOC S-o4jltpni]
- Conditional Access exposes an "Authentication flows" condition; selecting "Device code flow" with the grant control Block access blocks device code flow for the users and resources in the policy's scope (Microsoft recommends all users and all resources, starting in report-only). [DOC S1272, S1273]
- Microsoft's own guidance recommends blocking device code flow wherever possible, calling it high-risk (it can be part of a phishing attack or used to reach corporate resources from unmanaged devices). [DOC S1272] — a `client`/`site` instance that assumed device-code fallback as a resiliency path must not rely on it if the tenant follows this guidance.
- Token Protection (Conditional Access) requires the sign-in session tokens (such as the PRT) that apps present to be bound to the device. On Windows it is documented for an enumerated list of Microsoft native apps (Office apps, Outlook, Teams, OneDrive, Microsoft Graph PowerShell with WAM, Visual Studio Code, Windows App and others) accessing **Exchange Online, SharePoint Online, Microsoft Teams, Azure Virtual Desktop and Windows 365**; arbitrary Graph-calling public clients are not stated as covered. [DOC S1274, S1227]
- Token Protection is documented as supporting **native applications only** ("Mobile apps and desktop clients" in the Client Apps condition); browser-based apps (MSAL.js, e.g. Teams Web) are explicitly excluded and can be blocked if the Client Apps condition is left unscoped. [DOC S1274]
- The Windows deployment guide requires Microsoft Entra ID P1 and says Token Protection policies are currently available only for Windows and Apple devices. [DOC S1274]
- Platform coverage per the concept page: native apps are generally available on Windows, iOS/iPadOS and macOS (its device-requirements heading still reads "Apple (Preview)"); browser-based support is in preview only for selected web apps that access Azure Resource Manager, on Windows and macOS. [DOC S1227]
- Nothing in the fetched pages names MSAL Python specifically. The documented boundary is by client *type* (native vs. browser), not by MSAL language binding, so a Windows MSAL Python public client CLI falls on the "native application" side; but the Windows guide enumerates its supported applications (all Microsoft apps), and its unbound status code 1008 (client not integrated with the platform broker, WAM) indicates binding depends on WAM integration, so such a client is at most a candidate, not a documented supported app. [DER S1274]
- CAE readiness (`cp1`) is a separate mechanism from Token Protection: `PublicClientApplication(client_id, client_capabilities=["cp1"])` tells Entra the client can handle claims challenges, and the app then receives CAE tokens for resource APIs that implement CAE; it must handle the claims challenge (401 with `WWW-Authenticate` carrying `error="insufficient_claims"` and a `claims` value) by re-acquiring a token with `claims_challenge=<that value>` in MSAL Python. [DOC S1296]
- `cp1` and Token Protection are independent: declaring `cp1` makes the client CAE-aware; it does not itself bind tokens to the device (that is Token Protection's job, enforced by Conditional Access, not by the `client_capabilities` flag). [DER S1296,S1274]

## Reference
| Behaviour | Requirement | Source |
|---|---|---|
| WAM broker | `msal[broker]`, Windows 10+/Server 2019+, redirect URI `ms-appx-web://microsoft.aad.brokerplugin/<client_id>`, window handle (or `CONSOLE_WINDOW_HANDLE`) | S1270 |
| IWA silent token | domain- or Entra-joined machine, AD-backed users; not in MSAL Python | S-o4jltpni |
| Device code flow block | Conditional Access → Conditions → Authentication flows → Device code flow → Block | S1272, S1273 |
| Token Protection | registered device, native apps; resources EXO, SPO, Teams (+ AVD, Windows 365 on Windows); Entra ID P1 | S1274, S1227 |

## Examples
- A workstation CLI on engineer workstation `PL-LT-00123`, tenant `00000000-0000-0000-0000-000000000000`: `PublicClientApplication(..., enable_broker_on_windows=True)` with `parent_window_handle=msal.CONSOLE_WINDOW_HANDLE`.

## Open items
- QA5 (MSAL Python + WAM requirements, redirect URI, headless/jump-host behaviour, CA blocking device code) — answered above; jump-host/headless WAM behaviour on Windows Server itself beyond "supported OS" is [UNK] (no explicit statement of headless-session caveats found in three searches).
- QA6 (Token Protection applying to MSAL Python public clients / Graph calls; cp1 in MSAL Python) — answered: Token Protection scopes to native clients on Windows, macOS and iOS/iPadOS (GA per the concept page), P1-licensed, and is client-type-based not language-binding-based, so a Windows MSAL Python CLI qualifies as a candidate client even though no page names MSAL Python specifically [DER S1274, S1227]; `cp1`/CAE-readiness is a separate, directly-supported MSAL Python constructor argument [DOC S1296].
