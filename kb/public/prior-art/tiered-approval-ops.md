---
topic: prior-art/tiered-approval-ops
priority: P2
applies_to: "a small numbered tier scheme, tiers >=2 always confirmed"
retrieved_utc: 2026-09-28
sources: [S1015, S1016, S1017, S1018, S-p6qlnhra, S-nnzeoxyh, S-smmzgplg, S-askzkdnt, S-bmjfyz5c, S-uh67gxyw]
status: complete
---

## Summary
Rundeck, StackStorm, Teleport and Ansible AWX each gate operational actions behind some form of
role/ACL and, for the higher-risk ones, an approval step. Rundeck's job ACL policies and StackStorm's
RBAC were confirmed from their documentation; Teleport's just-in-time Access Requests
(approval by a configurable number of reviewers, no self-approval) are an Enterprise feature, and AWX
workflows carry approval nodes with an "approver" role and an optional timeout, per their repository
docs.

## Facts
- Rundeck is described as letting an operator "give specific users access to your existing tools,
  services, and scripts" — i.e. scoped, delegated execution rather than full shell access; licensed
  Apache-2.0, written primarily in Groovy. [DOC S1015]
- StackStorm is described as "event-driven automation for auto-remediation, incident responses,
  troubleshooting, deployments, and more" that includes a rules engine, workflow and ChatOps;
  licensed Apache-2.0, written in Python. [DOC S1016]
- Teleport is described as providing secure access to infrastructure; its repository licence is
  AGPL-3.0, language Go. [DOC S1017]
- Teleport's just-in-time Access Requests grant a role or a resource for a limited time after a configurable number of approvers approve; users cannot approve their own requests, and automatic reviews exist. [DOC S-bmjfyz5c]
- Access Requests are a Teleport Enterprise feature: Community Edition users can only request roles from the CLI, and an approver there runs `tctl` on the Auth Service, because approval rules need Enterprise. [DOC S-uh67gxyw]
- Ansible AWX is described as providing "a web-based user interface, REST API, and task engine built
  on top of Ansible," and is stated to be "one of the upstream projects for Red Hat Ansible Automation
  Platform"; licence unresolved by the GitHub API ("NOASSERTION"), language Python. Its README says
  releases have been paused since 24.6.1 (2024-07-02) during a large-scale refactoring. [DOC S1018]
- AWX's repository docs say its RBAC system has moved to the `django-ansible-base` library. [DOC S-askzkdnt]
- AWX workflows can hold approval nodes: a user approves when they are a Superuser, Workflow Admin, Organization Admin or hold the explicit "approver" role; creating one needs Superuser, Org Admin, Workflow Admin or admin of that workflow; each node takes a timeout, default `0` (no expiry). [DOC S-smmzgplg]
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
