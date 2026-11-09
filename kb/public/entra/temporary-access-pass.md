---
topic: entra/temporary-access-pass
priority: P3
applies_to: "Microsoft Entra ID Temporary Access Pass (doc updated 2026-06-15)"
retrieved_utc: 2026-11-09
sources: [S-ceqkuljp]
status: complete
---

# Entra Temporary Access Pass (TAP)

## Summary
- A TAP is a time-limited passcode, single-use or multi-use, that lets a user sign in to onboard passwordless methods or to recover after losing a strong authentication method.
- Two steps: an Authentication Policy Administrator enables TAP in the Authentication methods policy, then an Authentication Administrator (or higher) adds a TAP to the user under **Authentication methods**.
- The pass value is shown once; note it before selecting OK.

## Facts
- A TAP is a time-limited passcode that can be configured for single use or multiple sign-ins; users sign in with it to onboard other passwordless methods, and it eases recovery when a user loses or forgets a strong authentication method. [DOC S-ceqkuljp]
- Before users can sign in with a TAP, the method must be enabled in the Authentication methods policy for chosen users and groups (**Entra ID > Authentication methods > Policies > Temporary Access Pass**, **Enable**, then **Save**); a TAP can be created for any user, but only users in the policy can sign in with it. [DOC S-ceqkuljp]
- Updating the TAP policy needs the Authentication Policy Administrator role. [DOC S-ceqkuljp]
- Policy defaults and ranges: minimum lifetime 1 hour, maximum lifetime 8 hours, default lifetime 1 hour, each within 10 to 43,200 minutes (30 days); one-time use default False; passcode length 8, range 8 to 48 characters. [DOC S-ceqkuljp]
- With one-time use set to True in the policy, every pass created in the tenant is one-time use; with False, a pass can be used once or several times within its validity. [DOC S-ceqkuljp]
- Roles that act on a TAP: Privileged Authentication Administrator creates, deletes and views a TAP for admins and members except themselves; Authentication Administrator does the same for members except themselves; Global Reader views TAP details without reading the code. [DOC S-ceqkuljp]
- To create one in the admin center: **Entra ID > Users**, select the user, **Authentication methods > Add authentication method > Temporary Access Pass**, set a custom activation time or duration, **Add**. The page warns the value cannot be viewed again after **OK**. [DOC S-ceqkuljp]
- Graph PowerShell creates and reads one with `New-MgUserAuthenticationTemporaryAccessPassMethod` and `Get-MgUserAuthenticationTemporaryAccessPassMethod`; the body takes `isUsableOnce` and `startDateTime`, and a get returns the pass without its code. [DOC S-ceqkuljp]
- A user signs in with a TAP at Security info (`mysignins.microsoft.com/security-info`) by entering the UPN and then the pass; a TAP does not replace the password, and for a federated domain it is preferred over federation (no redirect to the federated IdP). [DOC S-ceqkuljp]
- After signing in with a TAP to replace lost credentials or a lost device, the user should remove the old authentication methods. [DOC S-ceqkuljp]
- Each user has at most one TAP; creating a new one overrides an existing valid or expired one. [DOC S-ceqkuljp]
- A one-time TAP used to register a passwordless method (FIDO2 key, phone sign-in) requires the registration to finish within 10 minutes of the sign-in; this does not apply to a multi-use TAP. If device enrollment outlasts 10 minutes, the page offers two single-use TAPs or one multi-use TAP. [DOC S-ceqkuljp]
- On Windows 10 and 11, a TAP can complete Microsoft Entra join and Windows Hello for Business setup with no password; on an already-joined or hybrid-joined device the user first signs in with another method (password, smartcard, FIDO2 key) before using a TAP for Windows Hello for Business. [DOC S-ceqkuljp]
- With Web sign-in enabled on Windows, a TAP can sign the user in to the device, intended only for initial setup or recovery when the user has no password. [DOC S-ceqkuljp]
- A TAP can register Microsoft Authenticator (passkeys and passwordless phone sign-in) by adding a work or school account and signing in with the pass. [DOC S-ceqkuljp]
- Guests: a TAP can be added to an internal guest (UserType Guest with methods registered in Entra ID) but not to an external guest, which gives the error "Temporary Access Pass cannot be added to an external guest user". [DOC S-ceqkuljp]
- An expired or deleted TAP cannot authenticate interactively or non-interactively; tokens issued in a TAP sign-in have their maximum lifetime capped at the TAP expiry at issuance, but expiry does not end sessions already established, so Conditional Access sign-in frequency limits how long access lasts. [DOC S-ceqkuljp]
- An expired TAP is deleted under the user's **Authentication methods** (**Delete**) or with `Remove-MgUserAuthenticationTemporaryAccessPassMethod`. [DOC S-ceqkuljp]
- Limitations: users in scope of the SSPR registration policy or the ID Protection MFA registration policy are sent to interrupt-mode combined registration after a browser TAP sign-in, which does not support FIDO2 and phone sign-in; a TAP does not work with the NPS extension or the AD FS adapter; replication can take minutes. [DOC S-ceqkuljp]
- Troubleshooting: if no TAP prompt appears, check the user is in policy scope and holds a valid, unused TAP; "sign in was blocked due to User Credential Policy" means a multi-use TAP while the policy requires one-time, an already-used one-time TAP, or a user out of scope. [DOC S-ceqkuljp]
- How it fits (lost MFA method): an Authentication Administrator adds a TAP for the user, hands over the value out of band, and the user registers a new method at Security info within the pass's lifetime; the policy must already include the user. [DER S-ceqkuljp: create, use and policy-scope sections combined]

## Reference
| Setting | Default | Range | Source |
|---|---|---|---|
| Minimum lifetime | 1 hour | 10 to 43,200 minutes | S-ceqkuljp |
| Maximum lifetime | 8 hours | 10 to 43,200 minutes | S-ceqkuljp |
| Default lifetime | 1 hour | 10 to 43,200 minutes | S-ceqkuljp |
| One-time use | False | True/False | S-ceqkuljp |
| Length | 8 | 8 to 48 characters | S-ceqkuljp |

## Examples
- SNIPPET: create a one-time TAP starting at a given time with Microsoft Graph PowerShell; context: Microsoft.Graph.Identity.SignIns module, user in TAP policy scope; checked: no [DER S-ceqkuljp: parameters from the page's PowerShell sample]
```powershell
$properties = @{ isUsableOnce = $true; startDateTime = '2026-11-10 06:00:00' } | ConvertTo-Json
New-MgUserAuthenticationTemporaryAccessPassMethod -UserId jan.kowalski@corp.example.com -BodyParameter $properties
```
