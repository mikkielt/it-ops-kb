---
topic: security/purview-teams-retention
priority: P3
applies_to: "Microsoft Purview Data Lifecycle Management retention policies for Microsoft Teams (chats, channel messages, call logs); retention labels and Teams files; Microsoft Learn pages updated 2026-06 to 2026-11"
retrieved_utc: 2026-11-09
sources: [S-vorhqnuy, S-odnvg5rs, S-h2xchig6, S-aueazq6o, S-w2ery36y, S-aeg2g6gt]
status: partial
---
# Purview retention for Microsoft Teams: policies, labels and deletion timing

## Summary
Teams chats, channel messages and call logs are governed by Purview **retention policies** only; **retention labels are not
supported on Teams messages**. Labels reach Teams-related content only as files (for example meeting recordings with their
transcripts in OneDrive or SharePoint) through an auto-apply label policy. Teams messages need their own policy: a static
policy with a Teams location cannot hold other locations. Messages are kept as copies in hidden mailbox folders, and a delete
action is a multi-step job: a policy takes up to seven days to apply, expiry is processed in 1-7 days, items sit in
SubstrateHolds at least one more day, and permanent deletion takes another run, so a one-day delete can take about 16 days.
Retention wins over deletion, and the longest retention period wins.

## Facts
### Scope: what Teams retention covers
- Teams chat messages, channel messages and private channel messages can be retained or deleted by Teams retention policies; Facilitator interactions in meetings are included with chat messages, and shared channels inherit the settings of their parent team. [DOC S-vorhqnuy]
- Besides the text, video clips, embedded images, tables, hyperlinks, links to other messages and files, and card content can be retained; code snippets, recorded voice memos from the mobile client, thumbnails, announcement images and reactions from others are not retained. [DOC S-vorhqnuy]
- Some system-generated control messages are supported, the types being those of the Teams Export APIs. [DOC S-vorhqnuy]
- Emails and files used with Teams are not covered by Teams retention policies; they need policies on the **Microsoft 365 Group mailboxes & sites**, **SharePoint classic and communication sites** or **OneDrive accounts** locations. [DOC S-vorhqnuy, S-h2xchig6]
- Meeting recordings and transcripts from channel meetings fall under the team's files; for those from user chats, a policy must include the organizer's OneDrive account. [DOC S-vorhqnuy, S-h2xchig6]
- Files shared in chat sit in the sharer's OneDrive account and files uploaded to a channel in the team's SharePoint site; a policy on those can delete a file that a Teams message still links to, and the user then gets "File not found". [DOC S-h2xchig6]
- Teams call logs (call data records and other call metadata) are a separate location, retained indefinitely by default; a call-log policy can be created and edited only with PowerShell, applies only to call logs created after it is active, and shows read-only in the portal. [DOC S-vorhqnuy, S-h2xchig6]
- Before late April 2026 call data records for chats and channels were included in Teams chat policies; those already included stay with their old policies, new ones need a call-log policy. [DOC S-h2xchig6]
- Skype for Business interop chats that arrive as Teams thread messages are covered by Teams policies; conversation history saved by Skype for Business into a mailbox needs a Skype for Business policy. [DOC S-vorhqnuy]
- Guests: with a guest account in your tenant, messages also go into a shadow mailbox for the guest, which retention policies do not support; with an account from another Microsoft 365 organisation your policy cannot delete that user's copy, but still deletes your users' messages. [DOC S-vorhqnuy]
- When a user is deleted, their retained chat messages stay in an inactive mailbox under the policy that applied before. [DOC S-vorhqnuy]

### Locations and policy shape
- The Teams locations are **Teams channel messages** (standard and shared channel chats and meetings, plus private channel content after the migration), **Teams chats** (1:1, group, meeting chats and chat with yourself), **Teams private channel messages** (before migration only) and **Teams call logs**. [DOC S-h2xchig6, S-aueazq6o]
- Private channel messages moved to group mailboxes from late 2025; after that the **Teams channel messages** location covers them and a private channel inherits its parent team's setting, while earlier policies on the old private-channel location keep enforcing. [DOC S-vorhqnuy]
- A static retention policy that includes a Teams location (or a Viva Engage location) automatically excludes all other locations; an adaptive policy can combine Teams and Viva Engage locations in one policy. [DOC S-h2xchig6]
- The Teams policy can apply to the whole organisation or to chosen users (chats and private channels) or teams (channel messages); the Teams docs suggest separate policies for private chats, standard channels and private channels, since chat data is often treated as more of a liability. [DOC S-odnvg5rs, S-h2xchig6]
- Retention period start for Teams messages is always when the message was created, even if the portal offers last modified; for an edited message, a copy of the original keeps its original timestamp. [DOC S-odnvg5rs, S-h2xchig6]
- The Teams chats location can list guests and non-mailbox users, which retention policies are not designed for and should not be selected. [DOC S-h2xchig6]
- Legacy **Teams chats and Copilot interactions** policies will be treated as Teams-only from 15 January 2027; Microsoft 365 Copilot interactions then need a policy on **Microsoft Copilot experiences**; `Set-RetentionCompliancePolicy -Applications "User:TeamsChatUserInteractions"` makes a legacy policy Teams-only. [DOC S-h2xchig6]

### Retention policies versus labels for Teams
- Teams supports retention policies for chat and channel messages (retain, delete, or retain then delete) and Learn states that retention labels aren't supported for Teams. [DOC S-odnvg5rs]
- The retention page says Exchange public folders, Skype, Teams and Viva Engage messages don't support retention labels, and that retention policies are the way to retain or delete content from those locations; published labels reach Exchange, SharePoint, OneDrive and Microsoft 365 Groups. [DOC S-aueazq6o]
- Labels are not tied to Teams messages, but a label can be auto-applied to cloud attachments shared in a Teams chat or channel: a copy of the file is made in the Preservation Hold library at sharing time and the label is applied to that copy, not to the message or the original. [DOC S-aeg2g6gt, S-aueazq6o]
- To retain or delete only Teams meeting recordings with their transcripts, use an auto-apply retention label policy with the keyword query `ProgID:Media AND ProgID:Meeting`; it matches a transcript alone and a recording with its transcript, and a transcript stored with a recording cannot be targeted separately. [DOC S-aeg2g6gt, S-vorhqnuy]
- Auto-apply label policies on sensitive information, keywords or trainable classifiers can take up to seven days to apply. [DOC S-aeg2g6gt]

### How deletion works and how long it takes
- A new or changed retention policy can take up to seven days to be distributed and applied; a failed distribution can be retried with `Set-RetentionCompliancePolicy -Identity <policy> -RetryDistribution` (for Teams channel messages) or `Set-AppRetentionCompliancePolicy` for the private channel and Viva Engage locations. [DOC S-h2xchig6]
- Teams messages are copied into hidden mailbox folders (the mailboxes of chat participants, a group mailbox for standard channels, a substrate group mailbox for shared channels), not covered by Exchange mailbox retention policies, and searchable by eDiscovery; the Teams app view does not show what is retained. [DOC S-vorhqnuy]
- When a retention policy deletes a message it is deleted permanently from the mailbox copies and from the Azure chat service that is Teams' primary storage, and it disappears for all participants, including users with a longer or no policy; their mailbox copies remain until another policy deletes them. [DOC S-vorhqnuy]
- An Exchange timer job typically takes 1-7 days to run; expired items move to the hidden SubstrateHolds folder, stay at least 1 day, and the next job run deletes them permanently. [DOC S-vorhqnuy]
- If a user deletes a message during the retention period it vanishes from Teams but does not reach SubstrateHolds for 21 days; an edited message's original is copied there at once. [DOC S-vorhqnuy]
- A delete-only policy of one day can take 16 days before the message is permanently gone from eDiscovery; messages can stay visible in Teams for up to seven days after expiry. [DOC S-vorhqnuy, S-odnvg5rs]
- Retain-only: edited or deleted originals are kept in SubstrateHolds for the whole period (forever if no end date); unedited messages stay where they are. [DOC S-vorhqnuy]
- Permanent deletion is suspended while the mailbox is under another Teams policy for the same location, a Litigation Hold, a delay hold or an eDiscovery hold; deleted messages disappear from Teams but remain discoverable. [DOC S-vorhqnuy]
- Retention wins over deletion and the longest retention period wins; both rules also cover eDiscovery holds. [DOC S-aueazq6o, S-odnvg5rs]
- Deleting the mailbox of a user covered by a retaining Teams policy makes it an inactive mailbox; exclude the user and wait for the change before deleting if the data is not needed. [DOC S-vorhqnuy]
- Users see "We've deleted older messages due to your org's retention policy" at the top of 1:1 and group chats and, in channels, "This message has been deleted because of a Retention Policy"; the texts are not configurable. [DOC S-odnvg5rs]

### Licensing
- Users under a Teams retention policy need an appropriate licence such as Office 365 E3 or A3. [DOC S-odnvg5rs]
- The Purview service description lists, for Teams chat, channel and private channel locations, Microsoft 365 E5/G5/A5/E3/G3/A3/F3/F1, Business Basic, Business Standard and Business Premium, Office 365 E5/G5/A5/E3/G3/A3/F3/E1/G1 and the Purview Suite FLW add-ons, and says the retention or deletion period must be more than 30 days for the underlined plans; the underlining does not survive in the text read, so which plans carry the 30-day limit is not confirmed. [UNK]
- Adaptive policy scopes need Microsoft 365 E5/A5/G5, a Purview Suite, or Office 365 E5/A5/G5; Microsoft 365 Group owners and members need a licence when a policy applies to the group's Teams messages. [DOC S-w2ery36y]
- Retention policies on Microsoft Copilot experiences, Enterprise AI apps or Other AI apps need pay-as-you-go billing; Microsoft 365 Copilot interactions are not charged. [DOC S-h2xchig6, S-w2ery36y]

### Configuration steps
- Portal path: Purview portal (`https://purview.microsoft.com/`) > **Solutions** > **Data Lifecycle Management** > **Policies** > **Retention policies** > **New retention policy**. [DOC S-h2xchig6]
- Steps: name the policy; keep **Full directory** (admin units are not supported); choose **Adaptive** or **Static** (adaptive scopes must exist first, and a User scope offers Teams chats but not channel messages); pick the Teams locations (all teams and users by default, refine with **Choose** or **Exclude**); choose retain, delete or both and the period; save. [DOC S-h2xchig6]
- After saving, the name, the scope type and the retention settings other than the period cannot be changed. [DOC S-h2xchig6]
- A Teams call-log policy is created with `New-AppRetentionCompliancePolicy -Applications "User:MicrosoftTeamsCallLog" -ExchangeLocation "All"` followed by `New-AppRetentionComplianceRule ... -RetentionDuration 365 -RetentionDurationDisplayHint Days -RetentionComplianceAction Delete`. [DOC S-h2xchig6]
- The roles needed to create and edit retention policies are on a separate page (the permissions section of "Get started with data lifecycle management"), not read for this article. [UNK]

### How it fits
- For an estate that must prove Teams chats are gone, the retention policy is the enforcement point and eDiscovery, not the Teams app, is the check; plan for weeks of lag on short delete periods (seven days to distribute, then the page's 16 days for a one-day delete). [DER S-vorhqnuy: timer-job and SubstrateHolds timings; S-h2xchig6: seven-day distribution]
- Retention labels cannot control chat or channel messages, so a label-based design needs a Teams-location policy beside it; labels fit only the files around Teams (recordings, attachments). [DER S-odnvg5rs, S-aeg2g6gt: labels unsupported for Teams, supported for files and cloud attachments]

## Reference
- Learn: Teams retention (`https://learn.microsoft.com/purview/retention-policies-teams`), Teams admin page (`https://learn.microsoft.com/microsoftteams/retention-policies`), creating policies (`https://learn.microsoft.com/purview/create-retention-policies`), retention concepts (`https://learn.microsoft.com/purview/retention`), auto-apply labels, Purview service description.
- See `auth/audit-log-apis.md` for Purview audit retention (a different mechanism from content retention) and `defender/safe-links.md` for Safe Links in Teams.

## Examples
- SNIPPET: create a Teams call-log retention policy and a delete-after-one-year rule; context: Security & Compliance PowerShell, call logs created after the policy is active; checked: no [DER S-h2xchig6: the page's two cmdlet examples with the policy name left as placeholders]
```powershell
New-AppRetentionCompliancePolicy -Name "<PolicyName>" -Applications "User:MicrosoftTeamsCallLog" -ExchangeLocation "All"
New-AppRetentionComplianceRule -Name "<RuleName>" -Policy "<PolicyName>" -RetentionDuration 365 -RetentionDurationDisplayHint Days -RetentionComplianceAction Delete
```
- SNIPPET: keyword query for an auto-apply label policy that finds Teams meeting recordings and transcripts; context: Purview auto-apply retention label policy, OneDrive and SharePoint locations; checked: no [DER S-aeg2g6gt: the page's query]
```text
ProgID:Media AND ProgID:Meeting
```
