---
topic: gitlab/codeowners
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97)"
retrieved_utc: 2026-09-26
sources: [S450, S444, S440]
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

## Reference
Syntax (sections, patterns, owners) is in `doc/user/project/codeowners/reference.md` at the same commit. It was not summarized here.

## Examples
```
# .gitlab/CODEOWNERS (fixture)
[baselines]
/dsc/ @jan.kowalski
```
