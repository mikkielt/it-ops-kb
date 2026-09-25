---
topic: dsc/open-bugs-windows
priority: P0
applies_to: "PowerShell/DSC GitHub issues, state=open, label Issue-Bug, snapshot 2026-09-23"
retrieved_utc: 2026-09-23
sources: [S126]
status: complete
files: [dsc/open-bugs.csv]
---

# Open DSC bugs affecting Windows resources

## Summary
- 55 open issues carry the label `Issue-Bug` (snapshot 2026-09-23). All 55 are in `open-bugs.csv` with number, title, labels, created date, affected area (keyword-classified), platform and URL.
- 19 of them touch Windows-side components. Nearly all are in the PowerShell / Windows PowerShell adapters (class-based resources, CIM serialization, WinPS module scope). One (#1727) is on the new `Microsoft.Filesystem.File/Content` (3.4.0-preview.1 only).
- No open `Issue-Bug` issue names `Microsoft.Windows/Registry`, `Service`, `FirewallRuleList`, `WindowsFeatureList`, `OptionalFeatureList` or `UpdateList` in its title.
- The `directives.version` lib-version defect and the trace-level secret leak found for this kb (`directives.md`, `secrets.md`) have no matching open bug title in this snapshot.

## Facts
- The repo's bug label is `Issue-Bug`. Other labels include `Resolution-*`, `Needs Triage`, `Backport-Needed`. [DOC S126]
- Open Issue-Bug count on 2026-09-23: 55 (pull requests excluded). [DOC S126]
- Engine issues that also affect Windows use: #1245 "Exit codes not reliable", #817 "DSC doesnt propagate exit code correctly", #962 "DSC does not validate Test method returns _inDesiredState", #963 "DSC Set does not error when return is not defined and resource returns stdout", #1209 "Parameter `secureString` transforms input incorrectly on adapter", #677 "Tracing is not being flushed before `dsc` exits", #883 "DSC config does discovery on every resource instance". [DOC S126]
- The affected-area column in the CSV comes from keywords in each title, not from the issue body. [DER S126: keyword match on title]

## Reference
Windows-side open bugs (from `open-bugs.csv`):

| # | Title | Affected area | Opened |
|---|---|---|---|
| 1727 | Microsoft.Filesystem.File/Content - Export don't work / SET strange behaviour | Microsoft.Filesystem.File/Content | 2026-09-20 |
| 1355 | Command: Resource 'powershell' [exit code 1] manifest description: Error | PowerShell adapter | 2026-01-16 |
| 1296 | DSC seems to inject "Verbose" key into resource properties... | PowerShell adapter | 2025-11-28 |
| 1292 | Explicitly defining PowerShell resources doesn't allow for delete | PowerShell adapter | 2025-11-26 |
| 1283 | Calling "PSDesiredStateConfiguration/WindowsOptionalFeature" Fails with Error | Windows PowerShell adapter | 2025-11-21 |
| 1021 | Implement PowerShell import extension | PowerShell adapter/extension | 2025-07-31 |
| 1001 | Failed to serialize properties into CimInstance | PowerShell adapter | 2025-07-24 |
| 854 | Class-based resource leveraging types from another module failure | PowerShell adapter | 2025-05-29 |
| 853 | Class-based resources with Export does not show capability | PowerShell adapter | 2025-05-29 |
| 833 | Output during module import or Get output interrupts parsing for class-based resources | PowerShell adapter | 2025-05-24 |
| 818 | Error while testing the `winps_script.dsc.yaml` example | Windows PowerShell adapter | 2025-05-17 |
| 810 | Class-based resources in Windows PowerShell not found when called from PowerShell | Windows PowerShell adapter | 2025-05-13 |
| 805 | PS Adapter implementedAs property | PowerShell adapter | 2025-05-10 |
| 794 | PS Adapter doesn't exit if background runspace is busy | PowerShell adapter | 2025-05-09 |
| 791 | PS Adapter Export does not serialize enums correctly | PowerShell adapter | 2025-05-08 |
| 765 | Doc: WinPS resources need to be installed for AllUsers | Windows PowerShell adapter | 2025-04-25 |
| 698 | PowerShell DSC resource is not registered as a WMI DSC resource | PowerShell adapter | 2025-03-14 |
| 697 | MSIX bundle missing from release artifacts | packaging | 2025-03-14 |
| 640 | Microsoft.DSC/PowerShell resource or config file size limit | PowerShell adapter | 2025-02-11 |

## Examples
Re-run the snapshot (throttled, unauthenticated):
`GET https://api.github.com/repos/PowerShell/DSC/issues?state=open&labels=Issue-Bug&per_page=100`
