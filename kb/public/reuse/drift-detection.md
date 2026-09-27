---
topic: reuse/drift-detection
priority: P2
applies_to: "detecting configuration drift with DSC v3 in test (report-only) mode via ConfigMgr baselines, with remediation left off"
retrieved_utc: 2026-09-26
sources: [S1008, S1009, S1010, S1104, S-3aphi7n2]
status: complete
---

## Summary
None of the three surveyed projects is reusable as code when DSC v3 is already the declared source of
truth, and none of Puppet, Chef InSpec or Microsoft365DSC ships a Python, DSC-compatible drift engine.
Their value here is confirmation of a pattern worth following generally: separate "report the gap"
from "apply the fix," and keep the reporting path enforcement-free until a deliberate milestone gate
opens remediation.

## Facts
- Puppet's `--noop` mode reports which resources would change without changing them (Apache-2.0,
  Ruby); it validates the drift-report-without-enforce pattern but runs its own catalog/agent model,
  incompatible with a stack that has already chosen DSC v3 as its declared source of truth -- nothing
  to import. [DOC S1008]
- Chef InSpec's repository `LICENSE`, fetched directly, confirms Apache-2.0 (the GitHub API had
  reported "NOASSERTION"); InSpec is read-only compliance-as-code by design (no enforcement path at
  all, unlike Puppet noop), which is an even closer conceptual match to a "test mode only, ever"
  posture -- but it is a Ruby framework with its own `describe`/control DSL, not portable into a
  pure-Python package. [DOC S1009,S1104]
- Microsoft365DSC (MIT) manages, configures, extracts and monitors Microsoft 365 tenant
  configurations; its repository topics include `powershell` and `desiredstateconfiguration`.
  [DOC S1010]
- At release 1.26.909.1 its resources (e.g. `MSFT_AADUser`) implement classic PowerShell DSC
  `Get-TargetResource`/`Set-TargetResource`/`Test-TargetResource` functions rather than DSC v3
  resource manifests. [CODE S-3aphi7n2: Modules/Microsoft365DSC/DscResources/MSFT_AADUser/MSFT_AADUser.psm1#Get-TargetResource]
- Its PowerShell resource code is out of scope for a Python-core tool and only becomes relevant if
  that tool ever ships its own DSC resources. [DER S1010, S-3aphi7n2: the resources are PowerShell modules]

## Reference
| project | drift-only mode | enforcement mode | licence | portable into a Python core? |
|---|---|---|---|---|
| Puppet | `--noop` | yes (normal run) | Apache-2.0 | no (own catalog model, Ruby) |
| Chef InSpec | yes, by design | no | Apache-2.0 (confirmed) | no (Ruby) |
| Microsoft365DSC | `Test-DSCConfiguration` | yes | MIT | no (PowerShell resources, wrong layer) |


## Examples
No fixture data required (mechanism-only facts).
