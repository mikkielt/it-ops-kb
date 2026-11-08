---
topic: gitlab/codeowners
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97)"
retrieved_utc: 2026-11-08
sources: [S450, S444, S440, S-iavvx4cz, S-25vbkrdv]
status: complete
---

# CODEOWNERS

## Summary
- CODEOWNERS is a Premium/Ultimate feature on GitLab.com, Self-Managed and Dedicated.
- One file per repository. GitLab takes the first one it finds in `./CODEOWNERS`, `./docs/CODEOWNERS` or `./.gitlab/CODEOWNERS`.
- It becomes a merge gate only with **Require Code Owner approval** on a protected branch (Premium/Ultimate).

## Facts
- Tier: Premium, Ultimate. Offerings: GitLab.com, Self-Managed, Dedicated. [DOC S450]
- Lookup order: root, then `docs/`, then `.gitlab/`. The first file found is used and the others are ignored. [DOC S450]
- "Require Code Owner approval" is configured per protected branch and is Premium, Ultimate. [DOC S444]
- The approval setting "Remove approvals by Code Owners if their files changed" removes only those owners' approvals when a later commit touches their files. [DOC S440]
- Code owners who commit to an MR can't approve it if it touches files they own. [DOC S440]

### Syntax
- A `CODEOWNERS` file holds file path patterns, owners named by user, group or role mentions, comment lines starting with `#` (inline comments are not supported) and optional sections opened by `[Section name]`. [DOC S-iavvx4cz]
- Paths are matched against the repository root: a leading `/` anchors a path there, a path without it matches at any depth (`README.md` matches every `README.md`), a trailing `/` covers a directory and its subdirectories, and `*` and `**` are wildcards. [DOC S-iavvx4cz]
- Each section enforces its rules separately: where several entries of one section match a file, only the last matching entry counts, and a file matched in several sections takes the last match of each. [DOC S-iavvx4cz]
- A section requires approval by default; a `^` prefix makes it optional, `[Section name][2]` requires that number of approvals, and owners written after the header are the section's default owners. [DOC S-iavvx4cz]
- Every entry needs at least one owner, and owners may be users, groups and subgroups, a nested group written by its full path such as `@group/subgroup`. [DOC S-iavvx4cz]
- A group or nested group named as owner contributes only its direct members, never inherited ones, and the group must be the project's group or an ancestor of it, a group invited to the project with the Developer, Maintainer or Owner role, or a group shared with the project's group or its ancestors. [DOC S-iavvx4cz]
- To make a group's direct members code owners, the group must be invited to the project; with the global SAML group memberships lock on, GitLab 18.6 and later accept a group invited to a parent group of the project instead. [DOC S-iavvx4cz]

### Groups and subgroups
- On every tier (Free, Premium, Ultimate), a subgroup has one immediate parent, groups nest up to 20 levels, and GitLab advises five levels or fewer to avoid performance problems. [DOC S-25vbkrdv]
- A member added to a group is added to all its subgroups, inheriting the group's permissions there; to give a higher role in one subgroup, the member is added again to that subgroup with that role. [DOC S-25vbkrdv]
- A mention of a subgroup notifies its direct members only; inherited members are not notified. [DOC S-25vbkrdv]
- So a code-owner group for a nested group's files names the nested group by its full path, and the people who approve must be direct members of that group: inheriting membership from a parent group is enough for access but not for ownership. [DER S-iavvx4cz, S-25vbkrdv: only direct members of a referenced group are eligible; members inherit into subgroups]

## Reference
Syntax (sections, patterns, owners): `doc/user/project/codeowners/reference.md` at commit a1faf261 (S-iavvx4cz), summarized above. Subgroups: `doc/user/group/subgroups/_index.md` at the same commit (S-25vbkrdv).

## Examples
- SNIPPET: a `.gitlab/CODEOWNERS` file with one section owning a path; context: GitLab 19.5 CODEOWNERS syntax (Premium/Ultimate); checked: no [DOC S450, S-iavvx4cz: `[Section name]` header followed by `path @owner` rows (the syntax reference, S-iavvx4cz)]
```
# .gitlab/CODEOWNERS (fixture)
[baselines]
/dsc/ @jan.kowalski
```
