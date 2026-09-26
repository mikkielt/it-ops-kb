---
topic: intune/collect-diagnostics
priority: P1
applies_to: "Intune device action Collect diagnostics, doc ms.date 2025-10-27"
retrieved_utc: 2026-09-24
sources: [S-6epv7qzl]
status: complete
---
# Collect diagnostics (Windows)

## Summary
Intune device action that gathers a fixed set of registry keys, command outputs, event logs and files from a
corporate Windows device and uploads a zip. Full contents list: `intune/collect-diagnostics.csv` (74 rows:
14 registry keys, 17 commands, 17 event logs, 26 file paths). It includes `%windir%\ccm\logs\*.log`, so ConfigMgr
client logs travel through this path too.

## Facts
- Platforms: Windows (corporate-owned), Windows Holographic, plus Android/iOS via app protection. [DOC S-6epv7qzl]
- RBAC: Help Desk Operator, School Administrator, or a custom role with **Remote tasks/Collect diagnostics** plus device read permissions. [DOC S-6epv7qzl]
- Diagnostics can't be collected or downloaded by calling Microsoft Graph directly; use the admin center. [DOC S-6epv7qzl]
- Bulk action: up to 25 Windows devices at a time. [DOC S-6epv7qzl]
- Stored 28 days then deleted; up to 10 collections per device. [DOC S-6epv7qzl]
- Autopilot failure auto-capture: one set of logs per device per day; enabled by default; can be disabled under Tenant administration > Device diagnostics. [DOC S-6epv7qzl]
- The action is enabled by default for Windows 10 1909+ / Windows 11 corporate devices and can be disabled tenant-wide. [DOC S-6epv7qzl]
- Device must receive the action within a 24-hour window; offline devices fail. [DOC S-6epv7qzl]
- Upload targets are regional `*lmsas.blob.core.windows.net` hosts (Europe: amsub0101 … amsub0901) that must not be blocked. [DOC S-6epv7qzl]
- Microsoft personnel might access device diagnostics; diagnostics may include user or device names. [DOC S-6epv7qzl]
- App-protection diagnostics above 50 diagnostics or 4 MB can't be downloaded from the portal (mobile app diagnostics zone). [DOC S-6epv7qzl]
- With KB5011543 (Win10) / KB5011563 (Win11) the zip is flattened, files named after the data collected. [DOC S-6epv7qzl]
- `mdmdiagnosticstool.exe` appears in the command list without `-area` arguments; which areas the action requests is not stated. [UNK]

## Reference
See `collect-diagnostics.csv` (columns kind, item, notes, source_id). Two paths are reproduced with the spelling
published by Microsoft (`%Program Files%\...`, `%ProgramData Microsoft Update Health Tools\...`).

See also `intune/remote-actions.md`: the full table of Graph `managedDevice` remote actions, of which
Collect diagnostics is the one action that cannot be called directly through Graph (admin-center only).

## Examples
Engineer downloads the zip for `PL-LT-00123` from Devices > Monitor > Device diagnostics; the ConfigMgr logs are in the `%windir%\ccm\logs` folder of the zip.
