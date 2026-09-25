---
topic: reuse/tiered-approval-ops
priority: P2
applies_to: "a small numbered tier scheme for action risk (tiers >=2 always confirmed), enforced in-process"
retrieved_utc: 2026-09-24
sources: [S1015, S1016, S1017, S1018, S1106]
status: complete
---

## Summary
All four are `pattern`-or-`no`, never `dependency`/`logic`. Their RBAC/approval concepts validate that
gating risky actions behind role and confirmation is an established idea, but a small, deliberately
scoped tier table enforced in a few dozen lines of in-code logic (not a rules engine) covers the need
for a fixed number of tiers. Running any of the four as a service would also violate a no-always-on-
service, no-gateway constraint.

## Facts
- Rundeck (Apache-2.0, Groovy) and StackStorm (Apache-2.0, Python) would both permit copying by
  licence, but both are full web/API automation platforms (always-on services); importing either adds
  exactly the kind of new service a no-always-on-service constraint rules out, for a surface that a
  small in-code tier table already covers deliberately. [DOC S1015,S1016]
- Teleport's repository licence is AGPL-3.0 (confirmed unchanged from prior-art fetch), so no copying
  is permitted regardless of fit; its "Access Requests" feature (time-bound, approval-gated role
  elevation) is a plausible pattern reference for a future, more general approval workflow, but that is
  a bigger-scope concern, not a small fixed-tier design. [DOC S1017]
- Ansible AWX's repository `LICENSE.md`, fetched directly, confirms Apache-2.0 (the GitHub API had
  reported "NOASSERTION"). Licence would permit copying, but AWX is a full web UI + REST API + task
  engine (a service, not a Python library) -- adopting it would add infrastructure that a
  no-always-on-service, pure-Python-package design explicitly avoids. [DOC S1018,S1106]
- None of the four projects' fetched metadata documents a small numbered tier concept comparable to a
  fixed 0-3 scheme; each instead exposes a role/permission model a caller maps onto tiers, which is
  exactly what a small hand-written tier table already does directly in code. [DER S1015,S1016,S1017,S1018]

## Reference
| project | licence | copying permitted | why not adopted |
|---|---|---|---|
| Rundeck | Apache-2.0 | yes | always-on service; a small in-code surface doesn't need it |
| StackStorm | Apache-2.0 | yes | always-on service; same reason |
| Teleport | AGPL-3.0 | no | licence bars copying; also a service |
| Ansible AWX | Apache-2.0 (confirmed) | yes | always-on service; adds infrastructure a lean design avoids |

## Examples
No fixture data required (mechanism-only facts).
