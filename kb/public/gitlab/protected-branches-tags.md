---
topic: gitlab/protected-branches-tags
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97)"
retrieved_utc: 2026-09-29
sources: [S444, S445, S446, S-lu25cylz, S-mi3mmhpi, S450, S-4o7kkuoi]
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
- Protection is per branch (a name or wildcard), never per path: the settings above decide who can push or merge to a branch, whatever the commit changes. [DER S444: the settings list has no path or content scope]
- Push rules (Premium, Ultimate; GitLab.com, Self-Managed, Dedicated) are `pre-receive` hooks with a user interface: they can require or reject commit-message expressions, restrict branch names, reject unsigned commits, set a maximum file size and reject prohibited file names; expressions use RE2 and each is limited to 511 characters. [DOC S-lu25cylz]
- **Prohibited filenames** checks only files that do not yet exist in the repository, comparing every file name in the push with the expression, so it cannot refuse a change to an existing file; push rules are copied into projects created after they are set and do not follow later changes to the global or group rules. [DOC S-lu25cylz]
- Server hooks (`pre-receive`, `post-receive`, `update`) are Free, Premium and Ultimate on GitLab Self-Managed only: an administrator sets them with `gitaly hooks set` for one repository (a tarball with a `custom_hooks` directory) or in a global hook directory (`custom_hooks_dir`), on every Gitaly node that holds a replica when Gitaly Cluster (Praefect) is used; Geo does not replicate them. [DOC S-mi3mmhpi]
- CODEOWNERS, which ties an approval requirement to file paths, is Premium and Ultimate. [DOC S450]
- A Free GitLab project (self-managed included) can therefore enforce "merge request only" for a whole branch (Allowed to push and merge: No one) but not "merge request only for these paths": path rules are Premium (push rules, Code Owners) or need an administrator's server hook, so a rule that code paths take merge requests while content paths take direct pushes is enforced by the client and by a CI check after the push. [DER S444, S450, S-lu25cylz, S-mi3mmhpi: tier and scope of each mechanism]
- A protected-branch push mirror sends only the protected branches (**Only mirror protected branches**) and has no path filter. [DOC S-4o7kkuoi]

## Reference
| Feature | Tier | Source |
|---|---|---|
| Protect branch (project) | Free | S444 |
| Protect branch (group) | Premium | S444 |
| Protected tags (roles) | Free | S445 |
| Protected tags (users/groups) | Premium | S445 |
| Require Code Owner approval | Premium | S444 |
| Push rules (commit message, branch name, file name, size) | Premium | S-lu25cylz |
| Server hooks (`pre-receive`, `update`) | Free, Self-Managed only | S-mi3mmhpi |

See also `gitlab/github-branch-rules-and-auto-merge.md` (the GitHub counterpart), `gitlab/detecting-mr-merges-in-ci.md` (telling a merge request merge from a direct push after the fact), `gitlab/repository-mirroring.md` (mirrors of protected branches).

## Examples
Protected tag wildcard `release-*`, Allowed to create: Maintainers. Protected tag `v*`, Allowed to create: Maintainers.
