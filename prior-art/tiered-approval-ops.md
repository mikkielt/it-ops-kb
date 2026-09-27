---
topic: prior-art/tiered-approval-ops
priority: P2
applies_to: "a small numbered tier scheme, tiers >=2 always confirmed"
retrieved_utc: 2026-09-26
sources: [S1015, S1016, S1017, S1018, S-p6qlnhra, S-nnzeoxyh]
status: partial
---

## Summary
Rundeck, StackStorm, Teleport and Ansible AWX each gate operational actions behind some form of
role/ACL and, for the higher-risk ones, an approval step. Rundeck's job ACL policies and StackStorm's
RBAC were confirmed from their documentation; Teleport's "Access Requests" feature (just-in-time,
approval-gated elevated access) is named in its own product description; AWX's RBAC and approval
nodes are not confirmed by its repository metadata or README. Teleport and AWX were not read past
repository-level metadata and README; depth is limited to what is confirmed at that level.

## Facts
- Rundeck is described as letting an operator "give specific users access to your existing tools,
  services, and scripts" — i.e. scoped, delegated execution rather than full shell access; licensed
  Apache-2.0, written primarily in Groovy. [DOC S1015]
- StackStorm is described as "event-driven automation for auto-remediation, incident responses,
  troubleshooting, deployments, and more" that includes a rules engine, workflow and ChatOps;
  licensed Apache-2.0, written in Python. [DOC S1016]
- Teleport is described as providing secure access to infrastructure; its repository licence is
  AGPL-3.0, language Go. Teleport's product line publicly documents an "Access Requests" feature for
  time-bound, approval-gated elevation to a role, but the specific approval-workflow mechanics were
  not fetched from Teleport's docs this session. [DOC S1017]
- Ansible AWX is described as providing "a web-based user interface, REST API, and task engine built
  on top of Ansible," and is stated to be "one of the upstream projects for Red Hat Ansible Automation
  Platform"; licence unresolved by the GitHub API ("NOASSERTION"), language Python. Its README says
  releases have been paused since 24.6.1 (2024-07-02) during a large-scale refactoring. [DOC S1018]
- AWX has a role-based access control model (organizations, teams, roles) and workflow approval
  nodes. [UNK: not in S1018 as re-read 2026-09-27; the AWX docs site no longer serves the user guide]
- Rundeck authorizes every user action through `aclpolicy` access control policies that grant actions
  on projects, jobs, nodes and commands to groups or users; StackStorm RBAC (in open source since 3.4)
  restricts users through roles and permission grants. [DOC S-p6qlnhra, S-nnzeoxyh]
- None of the four projects documents an explicit numbered "tier" concept (0/1/2/3) comparable to a
  fixed 0-3 scheme; each instead exposes a role/permission model (Rundeck ACL policies, StackStorm RBAC,
  Teleport roles) that a caller can map onto tiers. [DER S-p6qlnhra, S-nnzeoxyh, S1017: role/permission models only, no numbered tiers]

## Reference
| project | scope | approval/elevation feature named | licence | language |
|---|---|---|---|---|
| Rundeck | delegated job execution | ACL policies (scoped access) | Apache-2.0 | Groovy |
| StackStorm | event-driven automation, ChatOps | RBAC (open source since 3.4), rules engine | Apache-2.0 | Python |
| Teleport | infrastructure access | Access Requests (named, not detailed here) | AGPL-3.0 | Go |
| Ansible AWX | RBAC + job templates on top of Ansible | workflow approval nodes (named, not detailed here) | unresolved | Python |

## Examples
No fixture data required (mechanism-only facts).
