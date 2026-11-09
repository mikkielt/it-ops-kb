---
topic: intune/onedrive-known-folder-move
priority: P3
applies_to: "OneDrive sync app, Known Folder Move policies on Windows via Intune settings catalog or Group Policy (docs updated 2025-11-17 and 2026-10-12)"
retrieved_utc: 2026-11-09
sources: [S-rfdi5zvq, S-z4uxqpit, S-tutw6o6q]
status: complete
---

# OneDrive Known Folder Move through Intune

## Summary
- Known Folder Move (KFM) redirects and moves the Windows known folders (Desktop, Documents, Pictures; the page also lists Screenshots and Camera Roll) to OneDrive.
- On Windows the silent route is the OneDrive policy **Silently move Windows known folders to OneDrive** (`KFMSilentOptIn`, needs the tenant ID), delivered through an Intune **Settings catalog** profile (platform Windows 10 and later, category **OneDrive**) or Group Policy.
- Pair it with the prompt policy so a failed silent move asks the user to fix the error.

## Facts
- OneDrive policies can be set with Group Policy, the Intune settings catalog or registry settings; four policies control KFM: prompt users to move, silently move, prevent users from turning off KFM, and prevent users from moving known folders. [DOC S-rfdi5zvq]
- Intune route: **Devices > Configuration > Create**, platform **Windows 10 and later**, profile type **Settings catalog**; in **Configuration settings > Add settings** pick **OneDrive** in the settings picker, configure, assign. [DOC S-z4uxqpit]
- Some OneDrive settings need the tenant ID; the Intune page links to how to find it. [DOC S-z4uxqpit]
- The silent policy (`Applies to: Group Policy, Intune`) moves Documents, Pictures and Desktop with no user interaction; all folders at once or a chosen selection. [DOC S-tutw6o6q]
- Once a folder has been moved, the silent policy does not act on it again, even if its checkbox is later cleared. [DOC S-tutw6o6q]
- Enabling it writes `HKLM\SOFTWARE\Policies\Microsoft\OneDrive` value `KFMSilentOptIn` as a string holding the tenant ID; `KFMSilentOptInWithNotification` = 1 shows a notification after a successful redirect. [DOC S-tutw6o6q]
- Without folder selectors the default moves Desktop, Documents and Pictures; to choose, set `KFMSilentOptInDesktop`, `KFMSilentOptInDocuments` or `KFMSilentOptInPictures` to 1. [DOC S-tutw6o6q]
- If the policy is disabled or not configured, known folders are not silently redirected. [DOC S-tutw6o6q]
- The Group Policy **User Configuration > Administrative Templates > Desktop > Prohibit User from manually redirecting Profile Folders** must be Disabled or Not configured, or folders do not move. [DOC S-tutw6o6q]
- The prompt policy (**Prompt users to move Windows known folders to OneDrive**, `KFMOptInWithWizard` with the tenant ID) shows a window asking users to protect their folders; if the silent move fails, users are prompted to correct the error, so Microsoft recommends using the two together. [DOC S-rfdi5zvq, S-tutw6o6q]
- Rollout guidance: use the silent policy on existing and new devices, limited to 1,000 existing devices a day and 4,000 a week across macOS and Windows; use the prompt policy for existing devices only, up to 5,000 a day and 20,000 a week. [DOC S-rfdi5zvq]
- For many files, roll out slowly and temporarily set **Limit the sync app upload rate to a percentage of throughput** (10 to 99 percent), then disable it after uploads finish. [DOC S-rfdi5zvq, S-tutw6o6q]
- **Prevent users from turning off Known Folder Move** (`KFMBlockOptOut`) requires users to keep known folders in OneDrive; **Prevent users from moving their Windows known folders to OneDrive** (`KFMBlockOptIn` 1, or 2 to also redirect folders back to the device) blocks the move. [DOC S-rfdi5zvq, S-tutw6o6q]
- KFM does not work for users syncing OneDrive files in SharePoint Server. [DOC S-rfdi5zvq]
- Folders earlier redirected with Windows Folder Redirection Group Policy: the OneDrive KFM policies do not work until that policy is disabled; local-PC redirects then move to OneDrive, OneDrive redirects stay, and a network-share redirect needs its contents copied into the user's OneDrive first (Migration Manager) so they merge. [DOC S-rfdi5zvq]
- Music and Videos are not affected by the OneDrive KFM policies, so they can stay redirected by Windows Folder Redirection. [DOC S-rfdi5zvq]
- If a user's folders are redirected to OneDrive of another organization, redirecting to yours creates new empty folders; disable the other redirect first. [DOC S-rfdi5zvq]
- `KfmForceWindowsDisplayLanguage` makes known folders be provisioned in the Windows display language even if the user set another preferred language. [DOC S-tutw6o6q]

## Reference
| Policy | Registry value | Source |
|---|---|---|
| Silently move Windows known folders | `KFMSilentOptIn` (tenant ID string) | S-tutw6o6q |
| Silent move notification | `KFMSilentOptInWithNotification` = 1 | S-tutw6o6q |
| Prompt users to move | `KFMOptInWithWizard` (tenant ID string) | S-tutw6o6q |
| Block moving to OneDrive | `KFMBlockOptIn` = 1 or 2 | S-tutw6o6q |
| Prevent turning KFM off | `KFMBlockOptOut` | S-tutw6o6q |

## Examples
- SNIPPET: registry values the silent policy writes; context: tenant ID shown as the placeholder; checked: no [DER S-tutw6o6q: values from the policy page]
```
[HKLM\SOFTWARE\Policies\Microsoft\OneDrive]
"KFMSilentOptIn"="00000000-0000-0000-0000-000000000000"
"KFMSilentOptInWithNotification"=dword:00000001
```
