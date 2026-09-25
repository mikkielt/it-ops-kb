---
topic: gpo/dsc-group-policy-adapter
priority: P2
applies_to: "PowerShell/DSC main @ 30ced1f5"
retrieved_utc: 2026-09-25
sources: [S924]
status: partial
---

# DSC v3 Group Policy (ADMX) adapter (pointer)

## Summary
Pointer only. Which DSC release ships the adapter, its manifest diff and behaviour are covered in `dsc/`
(release notes / feature matrix, resource manifests). One identifying fact is recorded here.

## Facts
- On PowerShell/DSC `main` (commit 30ced1f5, 2026-09-22) the adapter manifest `adapters/group_policy_template/group_policy_template.dsc.resource.json` declares type `Microsoft.Adapter/GroupPolicyTemplate`, version `0.1.0`, kind `adapter`, description "Adapts Windows Group Policy ADMX templates into DSC resources". [DOC S924]
- Which released DSC version first ships this adapter: see `dsc/` feature matrix; not verified here. [UNK]

## Reference
- ../dsc/ (manifests, release notes, feature matrix)

## Examples
None.
