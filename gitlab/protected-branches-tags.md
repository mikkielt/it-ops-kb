---
topic: gitlab/protected-branches-tags
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97)"
retrieved_utc: 2026-09-24
sources: [S444, S445, S446]
status: complete
---

# Protected branches and tags

## Summary
- Protected branches: Free tier. Group-level protection, per-user/group permissions, Require Code Owner approval and "who can unprotect" are Premium/Ultimate.
- The default branch is protected by default. The project **Protected branches** settings are moving to **Settings > Repository > Branch rules**.
- Protected tags: Free. Only people in **Allowed to create** can create or delete matching tags. Wildcards (`*`) are supported. Adding users or groups (not just roles) is Premium/Ultimate.
- Pipeline rights follow protection: running pipelines and jobs on a protected branch or tag needs merge/push rights (branch) or create rights (tag).

## Facts
- The protected branches page tier is Free, Premium, Ultimate. The "In a group", "With group permissions", "Require Code Owner approval" and "Control who can unprotect branches" sections are Premium, Ultimate. [DOC S444]
- The default branch is protected by default. [DOC S444]
- **Allowed to merge**: who can merge through MRs and create protected branches. If not configured, no one can merge. [DOC S444]
- **Allowed to push and merge**: who can push directly and merge. If not configured, no one can push. This setting implies merge rights. [DOC S444]
- To force MRs, set Allowed to merge = Developers + Maintainers and Allowed to push and merge = No one. [DOC S444]
- Merge or push permission on a protected branch decides whether a user can run pipelines and act on jobs. An MR pipeline isn't created if the user can't merge or push to the source branch. [DOC S444]
- Protected tags control who can create tags and prevent update or deletion after creation. Tiers: Free, Premium, Ultimate. [DOC S445]
- To create or delete a protected tag you must be in its **Allowed to create** list. Configuring protected tags needs the Maintainer or Owner role. [DOC S445]
- Premium/Ultimate can add groups or individual users to Allowed to create. [DOC S445]
- Permission to create protected tags decides who can start and run pipelines, and act on jobs, for those tags. [DOC S445]
- Protected variables and runners are available to MR pipelines only when the project allows it, both branches are protected, the user has push/merge access to the target, and both branches are in the same project (GitLab 18.1+). [DOC S446]

## Reference
| Feature | Tier | Source |
|---|---|---|
| Protect branch (project) | Free | S444 |
| Protect branch (group) | Premium | S444 |
| Protected tags (roles) | Free | S445 |
| Protected tags (users/groups) | Premium | S445 |
| Require Code Owner approval | Premium | S444 |

## Examples
Protected tag wildcard `release-*`, Allowed to create: Maintainers. Protected tag `v*`, Allowed to create: Maintainers.
