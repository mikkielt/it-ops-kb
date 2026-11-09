---
topic: defender/safe-links
priority: P3
applies_to: "Microsoft Defender for Office 365 Plan 1 and Plan 2 (Safe Links in email, Teams and Office apps); Exchange Online PowerShell *-SafeLinks* cmdlets; Microsoft Learn pages updated 2026-06 to 2026-10"
retrieved_utc: 2026-11-09
sources: [S-xzu77stx, S-63ycp5wz, S-nycr6lla, S-ds6ebpuo, S-jk4cmf6i, S-ecmsmyrh]
status: complete
---
# Safe Links in Microsoft Defender for Office 365

## Summary
Safe Links scans URLs in inbound email during mail flow and checks them again at the moment of the click, in email, Microsoft
Teams and supported Office apps. Who gets it is set by Safe Links policies: there is no default policy, but the **Built-in
protection** preset security policy covers every recipient not in a Standard, Strict or custom policy. Email links are rewritten
to a `safelinks.protection.outlook.com` address unless the policy says not to; Teams and Office app links are never rewritten and
are checked at click only. Plan 1 and Plan 2 both include it. Clicks show in the URL protection report and the advanced hunting
`UrlClickEvents` table. A policy is a policy object plus a rule object in PowerShell, one object in the portal.

## Facts
### What it does
- Safe Links gives URL scanning and rewriting of inbound email during mail flow, and time-of-click verification of URLs and links in email, Teams and supported Office apps; it runs in addition to anti-spam and anti-malware protection. [DOC S-xzu77stx]
- Email links are rewritten ("wrapped") with the prefix `https://<DataCenterLocation>.safelinks.protection.outlook.com` (for example `nam01`); the original URL shows when a user hovers over the link, and a click is scanned before the user reaches the page. [DOC S-xzu77stx]
- With Safe Links on, URLs are scanned before delivery whether or not they are rewritten; with rewriting on, links are scanned at click; with rewriting off, unwrapped URLs get a client-side Safe Links API call at click in supported Outlook (Windows, Mac, iOS, Android, Outlook on the web). [DOC S-xzu77stx]
- URLs without a valid reputation are detonated asynchronously in the background, and the same page describes the click check as a comparison with a list of known malicious URLs. [DOC S-xzu77stx]
- If rewriting is on, a manually forwarded or replied-to message is rewritten per recipient, internal and external, including links added later; for automatic forwarding (Inbox rules, SMTP forwarding) the final recipient's copy is not rewritten unless that recipient is also protected or the URL was already rewritten. [DOC S-xzu77stx]
- A message sent between two internal users is protected only if the policy that applies to the recipient has **Apply Safe Links to email messages sent within the organization** turned on. [DOC S-xzu77stx]
- Email limits: no support for mail-enabled public folders; only HTTP, HTTPS and FTP links; no protection for URLs in rich text (TNEF) messages; S/MIME signed messages are ignored. [DOC S-xzu77stx]
- Safe Links no longer wraps URLs that point to SharePoint or OneDrive sites, but the service still processes them; wrapping links with another service before Defender for Office 365 might stop Safe Links processing them. [DOC S-xzu77stx]
- When Safe Links is set to not rewrite and check via the API only, a user in a client without the Safe Links API (the page's example is an alternative email client) is not protected against a link that was clean at delivery and later weaponised. [DOC S-xzu77stx]
- If reading the policy fails in some apps (the page names classic Outlook), the user gets no Safe Links protection and is sent on to the clicked link; in Office desktop clients, if scanning cannot finish the user is warned before proceeding. [DOC S-xzu77stx]

### Teams and Office apps
- Teams: protection covers conversations, group chats, channels and tabs in Teams desktop, web and mobile (Android, iOS); URLs are checked at click and not rewritten; turning it on or off can take up to 24 hours. [DOC S-xzu77stx]
- In Teams the clicked link opens a warning page in the default browser, or inside the tab for a pinned tab, where the open-in-browser option is disabled; the Teams and Office web apps do not honour the policy's "Do not rewrite the following URLs" list. [DOC S-xzu77stx]
- Office apps: Safe Links checks links in Office documents, not links in email, though a document attached to an email is checked once opened; clients are Microsoft 365 Apps or Microsoft 365 Business Premium (Word, Excel, PowerPoint on Windows, Mac or web, Office apps on iOS and Android, Visio on Windows, OneNote on the web, Outlook for Windows opening saved EML or MSG), with modern authentication and a work or school sign-in. [DOC S-xzu77stx]
- Office apps URLs are not rewritten and are checked at click; the page warns it can take several seconds at session start to confirm Safe Links is available. [DOC S-xzu77stx]
- A Safe Links warning page is one of: scan in progress, suspicious message, phishing attempt (all URLs in the message are blocked), malicious website, or error. [DOC S-xzu77stx]

### Policies and precedence
- There is no default Safe Links policy; the **Built-in protection** preset security policy gives Safe Links and Safe Attachments to all recipients not in Standard, Strict or custom policies, for customers with at least one Defender for Office 365 licence. [DOC S-xzu77stx, S-nycr6lla]
- Standard and Strict preset policies are assigned to no one until profiles are turned on and users assigned; Built-in protection applies to all recipients by default and takes only recipient exceptions (portal: **Add exclusions (not recommended)**; PowerShell: `Set-ATPBuiltInProtectionRule -Identity "ATP Built-In Protection Rule" -ExceptIfSentTo ...`). [DOC S-nycr6lla]
- Order of precedence for a recipient in several policies: Strict preset, Standard preset, evaluation policies, custom policies by priority (lower number first, 0 highest), then Built-in protection last; processing stops at the first policy that applies. [DOC S-nycr6lla, S-xzu77stx]
- Built-in protection differs from Standard and Strict in three Safe Links settings: `AllowClickThrough` is true (Standard and Strict: false), `DisableURLRewrite` is true (false), and `EnableForInternalSenders` is false (true). [DOC S-nycr6lla]
- The policies named Standard Preset Security Policy, Strict Preset Security Policy and Built-in protection (Microsoft) cannot be edited, disabled or removed on the Safe Links page; they are managed on the Preset security policies page. [DOC S-63ycp5wz]
- Recipient filters: users, groups (distribution or mail-enabled security groups, Microsoft 365 Groups; no dynamic distribution groups or dynamic Entra groups) and accepted domains; a policy needs at least one condition; different condition types combine with AND, values of one condition with OR, and exceptions all with OR. [DOC S-xzu77stx, S-63ycp5wz]
- Leaving users, groups and domains blank in the portal wizard makes a policy that applies to all recipients; subdomains are included unless excluded. [DOC S-63ycp5wz]
- Allow up to 6 hours for a new or updated Safe Links policy to apply. [DOC S-63ycp5wz]
- Each policy has a "Do not rewrite the following URLs" list; only the list of the first policy that applies to a user is used; up to three wildcards per entry; entries are skipped during mail flow but may still be blocked at click (an allow entry in the Tenant Allow/Block List covers click and mail flow). [DOC S-xzu77stx]

### Settings
- Email settings: turn on email protection; internal senders; real-time URL scanning for suspicious links and links that point to files, with **Wait for URL scanning to complete before delivering the message** (held until scanning ends when on; delivered anyway if scanning cannot complete when off); and **Do not rewrite URLs, do checks via SafeLinks API only**. [DOC S-xzu77stx]
- Click settings for all three workloads: **Track user clicks**, **Let users click through to the original URL** (recommended off) and organisation branding on warning pages; the custom notification text on the wizard's Notification page cannot exceed 200 characters. [DOC S-xzu77stx, S-63ycp5wz]
- If **Track user clicks** is off in the effective policy, the URL protection report has no click data. [DOC S-jk4cmf6i]

### Licensing
- Plan 1 and Plan 2 both include Safe Links and Safe Links in Teams; Plan 1 is in Microsoft 365 Business Premium and, per the service description, from 1 July 2026 in Office 365 E3 and Microsoft 365 E3 (a Plan 1 addition only); Plan 2 is in Microsoft 365 E5, A5 and GCC G5. [DOC S-ds6ebpuo]
- Safe Documents is not part of Plan 1 or Plan 2; it needs Microsoft 365 A5, E5 or the Defender Suite. [DOC S-ds6ebpuo]
- Built-in protection applies to organisations with any number of Defender for Office 365 licences, so by default there is no licence breach, though Microsoft recommends buying enough licences to cover everyone; users without a licence can be excluded with user or group exceptions. [DOC S-nycr6lla, S-63ycp5wz]

### Configuration
- Portal path: Defender portal, **Email & collaboration** > **Policies & rules** > **Threat policies** > **Safe Links** (`https://security.microsoft.com/safelinksv2`); the wizard has Name, Users and domains, URL & click protection settings, Notification and Review pages. [DOC S-63ycp5wz]
- Permissions to create, modify or delete policies: Organization Management or Security Administrator role groups in Email & collaboration RBAC plus Organization Management in Exchange Online RBAC, or the Entra roles Global Administrator or Security Administrator; read-only via Global Reader or Security Reader (or the unified RBAC Core Security settings read or manage permission for the portal only). [DOC S-63ycp5wz]
- In PowerShell (Exchange Online) a Safe Links policy is a `*-SafeLinksPolicy` object holding the settings and a `*-SafeLinksRule` object holding priority and recipient filters; create the policy first, then the rule that names it; a policy not tied to a rule is not visible in the portal. [DOC S-63ycp5wz]
- Removing a policy in PowerShell does not remove its rule, and the reverse; `Disable-SafeLinksRule` or `Enable-SafeLinksRule` turns the whole policy off or on; the policy has no name parameter, so a portal rename only renames the rule. [DOC S-63ycp5wz]
- PowerShell can create a rule disabled (`-Enabled $false`) and set priority at creation, which the portal cannot. [DOC S-63ycp5wz]

### Reporting
- The URL protection report (`https://security.microsoft.com/URLProtectionActionReport`) shows click actions: Allowed, Allowed by tenant admin, Blocked, Blocked by tenant admin, Blocked and clicked through, Blocked by tenant admin and clicked through, Clicked through during scan, Pending scan; its click-protection-action details table covers the last 30 days and the by-application details table the last seven days. [DOC S-jk4cmf6i]
- PowerShell report cmdlets for Safe Links are `Get-SafeLinksAggregateReport` and `Get-SafeLinksDetailReport`. [DOC S-jk4cmf6i]
- `UrlClickEvents` in advanced hunting holds Safe Links clicks from email, Teams and Office apps, with `ActionType`, `IsClickedThrough`, `ThreatTypes`, `DetectionMethods`, `UrlChain`, `Workload` (Email, Office, Teams) and `NetworkMessageId`; it is filled by Defender for Office 365 and returns nothing if the service is not deployed in Defender XDR. [DOC S-ecmsmyrh]
- Clicks on links wrapped by Safe Links have `AppName` value `Mail` in `UrlClickEvents`; for clicks from Drafts or Sent items the `NetworkMessageId` join to `Email*` tables does not work. [DOC S-xzu77stx, S-ecmsmyrh]

### How it fits
- For an estate that ties a Microsoft 365 tenant to managed Windows devices, Safe Links needs no endpoint agent: it acts in the service and in signed-in Office, Teams and Outlook clients, so device onboarding does not give or withhold it. [DER S-xzu77stx, S-ds6ebpuo: protection is described per recipient, policy and client, with no device requirement]
- A Safe Links policy managed as configuration is two objects, so a script or desired-state tool must create or remove the policy and the rule as a pair. [DER S-63ycp5wz: deleting one leaves the other]

## Reference
- Learn: Safe Links overview (`https://learn.microsoft.com/defender-office-365/safe-links-about`), Safe Links policies (`.../safe-links-policies-configure`), preset security policies (`.../preset-security-policies`), service description, reports and `UrlClickEvents`.
- See `defender/advanced-hunting.md` for advanced hunting limits, `graph/microsoft365dsc.md` for the `EXOSafeLinksPolicy` resource and its licensing note, and `defender/mde-onboarding.md` for the endpoint side of Defender.

## Examples
- SNIPPET: create a Safe Links policy and the rule that applies it to every accepted domain, URL rewriting and Teams and Office protection on, no click-through; context: Exchange Online PowerShell, Defender for Office 365; checked: no [DER S-63ycp5wz: from the page's two-step example, domain replaced by the accepted-domain call it also shows]
```powershell
New-SafeLinksPolicy -Name "Corp All" -EnableSafeLinksForEmail $true -EnableSafeLinksForOffice $true -EnableSafeLinksForTeams $true -ScanUrls $true -DeliverMessageAfterScan $true -EnableForInternalSenders $true -AllowClickThrough $false
New-SafeLinksRule -Name "Corp All" -SafeLinksPolicy "Corp All" -RecipientDomainIs (Get-AcceptedDomain).Name
```
- SNIPPET: list clicks on phish URLs that a user went through; context: Defender portal advanced hunting; checked: no [DER S-ecmsmyrh: the page's own example query]
```kusto
UrlClickEvents
| where ActionType == "ClickAllowed" or IsClickedThrough != "0"
| where ThreatTypes has "Phish"
| summarize by ReportId, IsClickedThrough, AccountUpn, NetworkMessageId, ThreatTypes, Timestamp
```
