---
topic: prior-art/drift-detection
priority: P2
applies_to: "detecting configuration drift without applying fixes (DSC test mode, no remediation)"
retrieved_utc: 2026-09-28
sources: [S1008, S1009, S1010, S-e4iemhin, S-2fvvbt5t, S-fylt7wwn, S-qlnd73w2, S-c6kla37l]
status: complete
---

## Summary
Puppet (`noop`/report mode), Chef InSpec, Ansible `--check` mode and Microsoft365DSC all separate
"detect and report a gap between desired and actual state" from "apply a fix," matching a
test-mode-only first milestone. For Microsoft365DSC the drift-only call is `Test-DscConfiguration`
(its docs name it for self-orchestrated monitoring) and `New-M365DSCDeltaReport` compares two
configuration files. Azure Machine Configuration, the Graph tenant configuration management APIs and
osquery/Fleet policies are covered elsewhere (`windows/azure-arc-servers.md`, `graph/tcm-apis.md`).

## Facts
- Puppet's agent run has a `--noop` (no-operation) mode: it evaluates the catalog and reports which
  resources *would* change (`corrective_change`/`out_of_sync` in the run report) without changing
  system state; this is the mechanism Puppet documents for drift *reporting* separate from
  enforcement. [DOC S1008]
- Puppet is licensed Apache-2.0; its GitHub repository (`puppetlabs/puppet`) is the open-source agent
  and catalog-application engine (language: Ruby). [DOC S1008]
- Chef InSpec is a distinct project from Chef's configuration-management agent: it is a
  compliance-as-code / testing framework that evaluates a target against declared `describe` controls
  and reports pass/fail per control, without itself applying any remediation — it is read-only by
  design, unlike Puppet noop which evaluates a full enforcement catalog in dry-run. [DOC S1009]
- Ansible's check mode (`ansible-playbook --check`) runs a playbook without changing the remote systems:
  modules that support check mode report the changes they would make, and modules that do not support it
  report nothing and do nothing; not every module supports it, and tasks conditioned on registered
  variables from earlier tasks produce no output in check mode. `--diff` adds before/after detail for
  modules that support diff mode. [DOC S-e4iemhin]
- Microsoft365DSC manages, configures, extracts and monitors Microsoft 365 tenant configurations through
  PowerShell DSC resources (resource families include Azure AD, Exchange, Intune, SharePoint, OneDrive,
  Planner and Power Platform). Repository licence MIT, language PowerShell. [DOC S1010]
- After a Microsoft365DSC configuration is applied, the DSC engine on that machine checks the tenant
  against the desired state (every 15 minutes by default) and Microsoft365DSC logs each detected drift,
  with the drifted component and properties, to the M365DSC event log; the `ApplyAndAutocorrect`
  configuration mode makes the engine also correct the drift. [DOC S-2fvvbt5t]
- Microsoft365DSC's own January 2026 post says drift monitoring runs from the compiled MOF by calling `Test-DSCConfiguration` (orchestrated by the caller) or `Start-DSCConfiguration` (on a schedule). [DOC S-qlnd73w2]
- `Test-DscConfiguration` tests whether the actual configuration matches the desired one and returns `True` or `False`; `-Detailed` adds the resources in and not in the desired state. It applies nothing, so it is the drift-only call. [DOC S-fylt7wwn]
- `New-M365DSCDeltaReport` compares two configuration files (`-Source`, `-Destination`) and writes an HTML delta report to `-OutputPath`; comparing a snapshot of one tenant with another's current state starts from `Export-M365DSCConfiguration`. [DOC S-c6kla37l]

## Reference
`prior-art/projects.csv` `latest_release` and `release_date` are GitHub's latest-release marker (`releases/latest`) at retrieval, not the newest tag: a project can carry newer tags on other release lines (Puppet 8.x, InSpec 7.x).

| project | drift-only mode | enforcement mode exists | licence | language |
|---|---|---|---|---|
| Puppet | `--noop` | yes (normal agent run) | Apache-2.0 | Ruby |
| Chef InSpec | yes, by design (no enforcement) | no (separate from Chef Infra) | UNK (repo reports NOASSERTION) | Ruby |
| Ansible | `--check` (per-module support varies) | yes (normal playbook run) | UNK (not fetched this session) | Python |
| Microsoft365DSC | DSC engine drift checks logged to the M365DSC event log | yes (`ApplyAndAutocorrect` mode) | MIT | PowerShell |

## Examples
No fixture data required (mechanism-only facts).
