---
topic: prior-art/drift-detection
priority: P2
applies_to: "detecting configuration drift without applying fixes (DSC test mode, no remediation)"
retrieved_utc: 2026-10-11
sources: [S1008, S1009, S1010, S-e4iemhin, S-2fvvbt5t, S-fylt7wwn, S-qlnd73w2, S-c6kla37l, S-wbcdphyr, S-im2mzbgr]
status: partial
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
- `ansible-pull` inverts Ansible's push model: it checks a playbook repository out on the target (`-U` url, `-C` branch, tag or commit, `-d` directory) and runs a playbook from it, meant to be scheduled by cron; the docs say to use an external scheduler or locking so runs do not clash. [DOC S-wbcdphyr]
- `ansible-pull -o` runs the playbook only if the repository changed, `-s N` sleeps a random 0 to N seconds first to spread git requests, `--verify-commit` aborts when the checked-out commit's GPG signature fails, and `--check` and `--diff` give the dry-run and difference views of the normal playbook run. [DOC S-wbcdphyr]
- Without a playbook argument `ansible-pull` looks for a playbook named after the host's fully qualified domain name, then its hostname, then `local.yml`. [DOC S-wbcdphyr]
- The TUF specification's version rule is the usual form of "refuse a backwards version": a client must not replace metadata with a version number lower than the one it already trusts, and a rollback attack is an attacker getting a client to install software older than it knew to be available. [DOC S-im2mzbgr]
- In TUF's update workflow a new timestamp whose version is lower than the trusted one is discarded and reported as a possible rollback attack, while an equal version is discarded and the cycle ends without error, which the spec calls normal; clients also must not trust expired metadata. [DOC S-im2mzbgr]
- A pull agent that fetches a git branch tip can apply the same three outcomes to the commit it is offered: newer than the last applied one runs the steps, equal does nothing and is no error, older is refused and reported. [DER S-im2mzbgr, S-wbcdphyr: lower refused and equal ends quietly in TUF; ansible-pull checks out a repository on the target]
- Each step of such an agent has a `check` that reads state and returns in-sync or drifted, an `apply` that runs only when `check` says drifted, and a dry-run mode that runs `check` for every step and applies none; this is the Puppet `--noop`, Ansible `--check` and DSC what-if split (`dsc/what-if.md`), and a second run of `apply` then changes nothing. [DER S1008, S-e4iemhin, S-wbcdphyr: noop and check modes report what would change without changing it]
- No official source read describes a static agent binary that compares the ancestry of two git commits before applying; the git primitives for it (`merge-base --is-ancestor`, `pull --ff-only`) were not read. [UNK: logged in `_gaps.md`]

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
