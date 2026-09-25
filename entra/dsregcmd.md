---
topic: entra/dsregcmd
priority: P1
applies_to: "Windows 10/11 dsregcmd (doc ms.date 06/27/2025)"
retrieved_utc: 2026-09-24
sources: [S544, S548]
status: partial
files: [entra/dsregcmd-fields.csv]
---

# `dsregcmd /status` field reference

## Summary
- `dsregcmd-fields.csv`: 74 fields (section, field, description) extracted from the Microsoft Entra docs page (MIT licence, verbatim).
- Sections: Device state, Device details, User state, SSO state, Pre-join and Post-join diagnostics, NGC prerequisites.
- The Tenant details section is not in the CSV (the page documents it only through a sample output). [UNK]

## Facts
- `DeviceId` is "The unique ID of the device in the Microsoft Entra tenant". [DOC S544]
- Device details are shown only for Entra joined or hybrid joined devices, not for registered ones. [DOC S544]
- `DeviceAuthStatus` returns SUCCESS, "FAILED. Device is either disabled or deleted", or "FAILED. ERROR"; it was added in Windows 10 21H1 and needs network connectivity in the system context. [DOC S544]
- `TpmProtected` YES means the device private key is in a hardware TPM. [DOC S544]
- A device can't be both EnterpriseJoined and AzureAdJoined. [DOC S544]
- After registration the device ID is saved on the device and is viewable with `dsregcmd.exe /status`. [DOC S548]
- `AzureAdPrt` YES means a Primary Refresh Token is present for the signed-in user; `AzureAdPrtUpdateTime` is in UTC. [DOC S544]

## Reference
- `dsregcmd-fields.csv` (this directory). Source attribution: MicrosoftDocs/entra-docs, MIT, commit 8fcc223342e1.

## Examples
- On `PL-LT-00123`: `dsregcmd /status` -> Device State: AzureAdJoined YES, DomainJoined YES, DomainName CORP (hybrid joined).
