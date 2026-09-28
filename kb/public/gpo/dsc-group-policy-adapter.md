---
topic: gpo/dsc-group-policy-adapter
priority: P2
applies_to: "PowerShell/DSC main @ 30ced1f5"
retrieved_utc: 2026-09-27
sources: [S924, S118, S-3yuoi2qa]
status: complete
---

# DSC v3 Group Policy (ADMX) adapter (pointer)

## Summary
Pointer only. Which DSC release ships the adapter, its manifest diff and behaviour are covered in `dsc/`
(release notes / feature matrix, resource manifests). One identifying fact is recorded here.

## Facts
- On PowerShell/DSC `main` (commit 30ced1f5, 2026-09-22) the adapter manifest `adapters/group_policy_template/group_policy_template.dsc.resource.json` declares type `Microsoft.Adapter/GroupPolicyTemplate`, version `0.1.0`, kind `adapter`, description "Adapts Windows Group Policy ADMX templates into DSC resources". [CODE S924: adapters/group_policy_template/group_policy_template.dsc.resource.json#type]
- The v3.3.0 release notes (2026-09-17) list "Add Group Policy template adapter" (PR #1686). [DOC S118]
- The manifest is in the source tree at tag v3.3.0 with the same type, version `0.1.0` and kind `adapter`; it is absent at v3.3.0-rc.2, rc.1, preview.1, preview.4 and v3.2.3, so v3.3.0 is the first release that carries it (v3.4.0-preview.1 also has it). [DER S-3yuoi2qa, S118: file present at the v3.3.0 tag, 404 at the earlier tags checked 2026-09-27]

## Reference
- ../dsc/ (manifests, release notes, feature matrix)

## Examples
None.
