---
topic: gitlab/protected-branches-tags
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97); protected branches and protected tags API pages @9f1632e2 (2026-09-27)"
retrieved_utc: 2026-10-11
sources: [S444, S445, S446, S-lu25cylz, S-mi3mmhpi, S450, S-4o7kkuoi, S-r2hatifx, S-ozrs7es3, S-m5gqjzvs, S-fi4hv5qp, S-7wdbu4r4, S-hxmsaqdu, S-onmjrpyd, S-zn23gmjw]
status: partial
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
- **Allowed to merge**: who can merge through MRs and create protected branches. When every selection is cleared, no one can merge (unless they have Allowed to push and merge). [DOC S444]
- **Allowed to push and merge**: who can push directly and merge. When every selection is cleared, no one can push. This setting implies merge rights. [DOC S444]
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
- Wildcard protected tags: `v*` matches `v1.0.0` and also `version-9.1`; when two wildcards match the same tag (`*-stable` and `production-*` on `production-stable`) a setting such as **Allowed to create** on any one of them applies to the tag. [DOC S445]
- A protected tag rule with **Allowed to create** set to **No one** stops tags from being created under a branch's name while branches can still be created; after a pattern is unprotected any user with the Developer, Maintainer or Owner role can delete the tags matching it, and protected tags can be deleted only through GitLab's UI or API, not through local Git commands. [DOC S445]
- So with a `v*` rule whose **Allowed to create** is Maintainers, a Developer can neither create a `v1.0.0` tag nor start or run a pipeline for it, and the same rule also covers a tag named `version-9.1`. [DER S445: the create and pipeline rules and the wildcard table]
- The protected-tag API accepts the access levels `0` (No access), `30` (Developer) and `40` (Maintainer); the protected-branch API adds `60` (Administrator, GitLab Self-Managed only). [DOC S-r2hatifx, S-ozrs7es3]
- A protected tag is created with `POST /projects/:id/protected_tags`: `name` (a tag or a wildcard), `allowed_to_create` (an array of `{user_id}`, `{group_id}`, `{deploy_key_id}` or `{access_level}` hashes; `user_id`, `group_id` and `access_level` are Premium and Ultimate only) and `create_access_level` (integer, default `40`). The response lists `create_access_levels`, each with `id`, `access_level`, `access_level_description`, `user_id`, `group_id` and `deploy_key_id`. [DOC S-r2hatifx]
- The tags API has list, get, protect and unprotect (`DELETE /projects/:id/protected_tags/:name`, `204`) and no update call. [DOC S-r2hatifx]
- A protected branch is created with `POST /projects/:id/protected_branches`: `name`, `push_access_level`, `merge_access_level` and `unprotect_access_level` (integers, default `40`, and `0` is invalid for unprotect), or the arrays `allowed_to_push`, `allowed_to_merge` and `allowed_to_unprotect` of `{user_id}`, `{group_id}`, `{member_role_id}` or `{access_level}` hashes (`allowed_to_push` alone also takes `{deploy_key_id}`), plus `allow_force_push` and, in Premium and Ultimate, `code_owner_approval_required`. The response carries `push_access_levels`, `merge_access_levels` and `unprotect_access_levels`. [DOC S-ozrs7es3]
- An existing branch rule is changed with `PATCH /projects/:id/protected_branches/:name`, naming an access-level record by its `id` and removing it with `_destroy: true`; `id` must not be sent on creation (an unknown `id` answers `404`). [DOC S-ozrs7es3]
- In the API several access levels can be set at once and the most permissive decides who may act, unlike the user interface, which clears the other roles when **No one** is chosen. [DOC S-ozrs7es3]
- A group in `allowed_to_create`, `allowed_to_push` or `allowed_to_merge` must have the project shared with it (for a branch with the Developer, Maintainer or Owner role in the project), and a user must have access to the project; for tags the project must be shared with the group directly, membership inherited from a parent group is not enough. [DOC S-r2hatifx, S-ozrs7es3, S445]
- A deploy key can be named in `allowed_to_create` (tags) and `allowed_to_push` (branches) only, never in a merge or unprotect list; it must be enabled for the project with write access, its owner needs at least read access to the project and must be a member; the setting moved from Premium to Free in GitLab 18.10 (introduced in 17.5). [DOC S-r2hatifx, S-ozrs7es3, S444, S445]
- So `create_access_levels` of a protected tag and `push_access_levels` of a protected branch have one element shape (`access_level`, `access_level_description`, `user_id`, `group_id`, `deploy_key_id`, `id`), but a tag has one list (who may create, which also gates its pipelines) while a branch separates push from merge and unprotect, and only branch lists take `member_role_id` (a custom role, Ultimate, generally available in 19.4 for creating a rule and 19.5 for updating one) and `60`. [DER S-r2hatifx, S-ozrs7es3: the two response tables and valid access levels]
- The page for protected branches now words this consistently: when every selection in **Allowed to push and merge** is cleared on an existing rule, no one can push; a newly created branch rule preselects **Maintainers**; to block direct pushes set **No one**. The earlier two-way wording (a note saying an unset value does not restrict pushes) is gone. [DOC S444]
- A wildcard rule (`*`, case-sensitive like every branch name) protects each branch whose name matches it, and when several rules match one branch the most permissive one controls. [DOC S444]
- Users with the Maintainer or Owner role can delete a protected branch, in the web interface (**Code** > **Branches** > **Delete protected branch**, confirmed by typing the branch name); "You can only delete protected branches with the GitLab UI or API", never with local Git commands or third-party Git clients. [DOC S444]
- A push that deletes a protected branch is refused with "You are not allowed to delete protected branches from this project. Only a project maintainer or owner can delete a protected branch." when the user lacks the right, and with "You can only delete protected branches using the web interface." when the update did not come from the web; the default branch can never be deleted ("The default branch of a project cannot be deleted."). [CODE S-m5gqjzvs: lib/gitlab/checks/branch_check.rb#protected_branch_deletion_checks]
- `Gitlab::UserAccess#can_delete_branch?` answers for a protected branch with the project ability `destroy_protected_branch` and for any other branch with the right to push; this commit's `project_policy.rb` files (CE and EE) do not name that ability, so where it is granted is not read. [CODE S-fi4hv5qp: lib/gitlab/user_access.rb#can_delete_branch?]
- After a merge that asked for the source branch to be removed, `MergeRequests::DeleteSourceBranchWorker` (unless the source branch moved from the sha it was queued with) retargets the merge requests chained on it and calls `Projects::DeleteBranchWorker` with the id of the user who merged; that worker calls `Branches::DeleteService`, which answers `405` ("You dont have push access to repo") without the `push_code` ability and otherwise runs `rm_branch` as that user. [CODE S-7wdbu4r4: app/workers/merge_requests/delete_source_branch_worker.rb#perform; CODE S-hxmsaqdu: app/workers/projects/delete_branch_worker.rb#perform; CODE S-onmjrpyd: app/services/branches/delete_service.rb#execute]
- `Projects::DeleteBranchWorker` raises (so Sidekiq retries) only when the delete answers `400`, "to avoid permission and non existent branch error": a refusal that is not a `400` ends silently, and none of these three files tests whether the branch is protected, so the protected-branch rule above is the one the delete meets when `rm_branch` runs the repository hooks. [CODE S-hxmsaqdu: app/workers/projects/delete_branch_worker.rb#perform; CODE S-onmjrpyd: app/services/branches/delete_service.rb#execute]
- In the merge requests API `force_remove_source_branch` is documented as "If `true`, the project settings force the deletion of the source branch after merge" and `should_remove_source_branch` as "If `true`, the source branch is removed after merge": both report a setting asked for, not that the branch was deleted. [DOC S-zn23gmjw]
- So a branch that matches a protected pattern (a `code/*` rule, for example) is not exempt from deletion after a merge, and "protected branches cannot be deleted" is not what GitLab says: the delete runs as the merging user and succeeds only for one a Maintainer or Owner may delete protected branches for; for a merge run as a lower role or a token with a lower role the branch stays, with no error on the merge request. [DER S444, S-fi4hv5qp, S-hxmsaqdu, S-m5gqjzvs, S-7wdbu4r4: the delete rule, the user passed on and the silent non-`400` end]
- Open: whether the post-merge delete also satisfies the "web interface" condition of `protected_branch_deletion_checks` (the protocol the repository hook call carries) and why one merged request that asked for the source branch's removal still has its protected-pattern branch are not shown by the pages or code read; the merging account's role decides it, and a run with a Maintainer token against a throwaway protected branch would settle it. [UNK: see `_gaps.md`]

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

See also `gitlab/github-branch-rules-and-auto-merge.md` (the GitHub counterpart), `gitlab/detecting-mr-merges-in-ci.md` (telling a merge request merge from a direct push after the fact), `gitlab/repository-mirroring.md` (mirrors of protected branches), `gitlab/deploy-keys-and-tokens.md` (deploy keys in push and create rules), `gitlab/project-settings-api.md` (merge method, squash and pipeline settings of the project), `gitlab/commit-signing-and-provenance.md` (signed commits with GPG keys and the push rules that require them).

## Examples
Protected tag wildcard `release-*`, Allowed to create: Maintainers. Protected tag `v*`, Allowed to create: Maintainers.
