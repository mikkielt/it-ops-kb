---
topic: prior-art/drift-detection
priority: P2
applies_to: "detecting configuration drift without applying fixes (DSC test mode, no remediation)"
retrieved_utc: 2026-09-24
sources: [S1008, S1009, S1010, S-e4iemhin]
status: partial
---

## Summary
Puppet (`noop`/report mode), Chef InSpec, Ansible `--check` mode and Microsoft365DSC all separate
"detect and report a gap between desired and actual state" from "apply a fix," matching a
test-mode-only first milestone. Azure Machine Configuration, Intune's tenant configuration management
and osquery/Fleet policies are named in the brief but were not independently fetched this session
(see Gaps); Microsoft365DSC facts below are drawn from its own repository, not from Microsoft's
official Learn docs (out of scope for this agent — see `mecm/`/`entra/` domains for ConfigMgr/Intune
facts sourced from Microsoft Learn).

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
- Microsoft365DSC packages PowerShell DSC resources for Microsoft 365 workloads (Exchange Online,
  SharePoint Online, Teams, Entra ID, Intune, etc.); like core PowerShell DSC, each resource exposes
  `Get`/`Test`/`Set`, so a `Test-DSCConfiguration` (or `Start-DSCConfiguration -WhatIf`) run reports
  drift against the declared `.ps1`/MOF configuration without invoking `Set`. Repository licence MIT,
  language PowerShell. [DOC S1010]

## Reference
`prior-art/projects.csv` `latest_release` and `release_date` are GitHub's latest-release marker (`releases/latest`) at retrieval, not the newest tag: a project can carry newer tags on other release lines (Puppet 8.x, InSpec 7.x).

| project | drift-only mode | enforcement mode exists | licence | language |
|---|---|---|---|---|
| Puppet | `--noop` | yes (normal agent run) | Apache-2.0 | Ruby |
| Chef InSpec | yes, by design (no enforcement) | no (separate from Chef Infra) | UNK (repo reports NOASSERTION) | Ruby |
| Ansible | `--check` (per-module support varies) | yes (normal playbook run) | UNK (not fetched this session) | Python |
| Microsoft365DSC | `Test-DSCConfiguration` / `-WhatIf` | yes (`Start-DSCConfiguration`) | MIT | PowerShell |

## Examples
No fixture data required (mechanism-only facts).
