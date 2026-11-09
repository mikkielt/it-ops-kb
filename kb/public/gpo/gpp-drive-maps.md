---
topic: gpo/gpp-drive-maps
priority: P3
applies_to: "Group Policy preferences, Drive Maps extension (Windows Server and Windows client; MS-GPPREF 2024-10-30)"
retrieved_utc: 2026-11-09
sources: [S-37hjm3ml, S-ahtrer5d, S-pwena4zn]
status: partial
---

# Mapping network drives with Group Policy preferences (Drive Maps)

## Summary
- The Group Policy Drive Maps client-side extension creates, modifies or deletes mapped drives and sets drive visibility.
- A drive map item needs a UNC path and a drive letter, an action (Create, Replace, Update, Delete), and a choice between one fixed letter and "Use first available, starting at", which clears drives.
- Item-level targeting (for example a security group) limits who gets the drive; Drive Maps already runs in the user's security context.

## Facts
- Group Policy preferences are 20 client-side extensions; Group Policy Drive Maps "creates, modifies, or deletes mapped drives, and configures the visibility of all drives". [DOC S-37hjm3ml]
- Preferences are not enforced like policy settings: a user's change to a preference-managed setting lasts only until the next Group Policy refresh, when the preference reverts. [DOC S-37hjm3ml]
- A drive map item's path is a fully qualified UNC path (`\\server\sharename`, a hidden share ending in `$`, or `\\server\sharename\foldername`); leave it blank only to modify an existing mapping identified by its drive letter. [DOC S-ahtrer5d]
- The action is Create, Delete, Replace or Update; the default when unspecified is Update. [DOC S-ahtrer5d]
- Create makes a drive map only if none exists, with no error otherwise; Delete removes it and does nothing if absent; Replace deletes and re-creates it, overwriting all its settings, and creates it if missing; Update changes only the settings defined in the item and creates the drive if missing. [DOC S-ahtrer5d]
- `persistent`: when 1 the client restores the mapping at each logon (the **Reconnect** option); when 0 the client discards the mapping at logoff. [DOC S-ahtrer5d]
- Optional attributes: a `label` (descriptive text), `userName` in `domain\userName` form and `cpassword`, which holds the connect-as password encrypted with an AES-derived key. [DOC S-ahtrer5d]
- `thisDrive` and `allDrives` set visibility of the mapped drive and of all drives (no change, hide, show); `allDrives` defaults to no change, and a `HIDE` for `thisDrive` takes precedence over the all-drives setting. [DOC S-ahtrer5d]
- `useLetter` 1: `letter` is the single drive letter acted on; `useLetter` 0 ("Use first available, starting at"): `letter` is the start of a range. With Create and 0 the first unassigned letter from there to Z: gets the mapping; Delete and 0 deletes all mapped drives from that letter through Z:. [DOC S-ahtrer5d]
- The client ignores drive letters that map to local devices rather than remote file system paths. [DOC S-ahtrer5d]
- Known behaviour: with "Use first available, starting at" set, the extension clears all mapped drives from that letter through Z:, so manual mappings can vanish at logon. Microsoft's fixes: manual mappings use earlier letters than the GPP ones and only one drive map policy applies, or give every drive map a specific letter. [DOC S-pwena4zn]
- Common option **Run in logged-on user's security context**: user preference items run as SYSTEM by default, but Drive Maps and Printers automatically use the user's security context, so they do not need it. [DOC S-37hjm3ml]
- Common option **Stop processing items in this extension if an error occurs on this item** skips only later items of the same extension in the same GPO; items are processed top to bottom. [DOC S-37hjm3ml]
- Common option **Remove this item when it is no longer applied** sets the action to Replace and removes the setting when the item falls out of scope (for example through item-level targeting); **Apply once and do not reapply** applies the item a single time. [DOC S-37hjm3ml]
- Item-level targeting narrows an item to chosen users or computers: each targeting item is true or false, combined with AND or OR, with nested targeting collections; targets include Security Group, Site, Domain, IP Address Match, Environment Variables, File Match, Time Range and others. [DOC S-37hjm3ml]
- How it fits (a share for one group): one item per share, `useLetter` 1 with a fixed letter, action Update or Replace, Reconnect on, and a Security Group targeting item; use Replace plus "Remove this item when it is no longer applied" if the drive should disappear when a user leaves the group. [DER S-37hjm3ml, S-ahtrer5d: item attributes combined with the common options]
- The console path to the Drive Maps node (User Configuration > Preferences > Windows Settings) and the item dialog's tab labels were not read on an official page. [UNK]

## Reference
| Action | Item exists | Item missing | Source |
|---|---|---|---|
| Create | no change | creates | S-ahtrer5d |
| Replace | deletes and re-creates, overwriting all settings | creates | S-ahtrer5d |
| Update | changes only the settings in the item | creates | S-ahtrer5d |
| Delete | removes | no action | S-ahtrer5d |

## Examples
- None; Drive Maps items are authored in the Group Policy Management Editor.
