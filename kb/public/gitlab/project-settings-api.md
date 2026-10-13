---
topic: gitlab/project-settings-api
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27); Free tier and CE unless stated"
retrieved_utc: 2026-10-11
sources: [S-4yvdwu5c, S-gqpmeuse, S-j2fhtiru, S-6aknk2k6, S-rivqro7b, S-4abgkvor, S-2d2dlaeq]
status: complete
---

# Project settings API: the attributes that encode a merge regime

## Summary
`PUT /projects/:id` (Maintainer or Owner) sets the whole merge regime of a project in one call, and `GET /projects/:id` reads it back. Nine attributes carry it: `only_allow_merge_if_pipeline_succeeds`, `remove_source_branch_after_merge`, `merge_method`, `squash_option`, `lfs_enabled`, `shared_runners_enabled`, `public_jobs` and the two feature-visibility levels `container_registry_access_level` and `merge_requests_access_level`. The merge-related ones are project defaults; a single merge request or push can still set its own squash and source-branch deletion. Values are booleans, `merge`/`rebase_merge`/`ff` for the method, `never`/`always`/`default_on`/`default_off` for squashing and `disabled`/`private`/`enabled` for the two visibility levels.

## Facts
- Reading a project's properties needs any default role on the project; editing them needs the Maintainer or Owner role. [DOC S-4yvdwu5c]
- A project is edited with `PUT /projects/:id` and created with `POST /projects`; `:id` is the project ID or its URL-encoded path. Most attributes below appear in both the create and the update table. `container_registry_access_level` and `merge_requests_access_level` appear in neither: both calls take them from the page's shared **Project feature visibility level** table. `automatic_rebase_enabled`, `squash_commit_template`, `merge_commit_template`, `ci_skip_branch_pipelines_for_mrs`, `protect_merge_request_pipelines`, `ci_push_repository_for_job_token_allowed` and `ci_pipeline_variables_minimum_override_role` appear in the update table only. [DOC S-4yvdwu5c]
- `only_allow_merge_if_pipeline_succeeds` (boolean) is the API name of the **Pipelines must succeed** setting: merge requests merge only with a successful pipeline. The create table words it as successful "pipelines" and the update table as successful "jobs". [DOC S-4yvdwu5c]
- `allow_merge_on_skipped_pipeline` (boolean) sets whether a merge request can merge with skipped jobs; the setting of that behaviour in the user interface is **Skipped pipelines are considered successful**, which matters only when **Pipelines must succeed** is on. [DER S-4yvdwu5c, S-rivqro7b: the attribute's description against the setting's page]
- `only_allow_merge_if_all_discussions_are_resolved` (boolean) requires every discussion to be resolved before a merge; `only_allow_merge_if_all_status_checks_passed` (boolean, Ultimate only) blocks a merge until the external status checks have passed. [DOC S-4yvdwu5c]
- `remove_source_branch_after_merge` (boolean) turns the **Delete source branch** option on by default for all new merge requests. [DOC S-4yvdwu5c]
- A single merge request has its own switch: `should_remove_source_branch` on the merge request and on `PUT .../merge`, and the push option `merge_request.remove_source_branch` for a push that opens one. [DOC S-4abgkvor, S-2d2dlaeq]
- `merge_method` (string) is `merge` (merge commit), `rebase_merge` (merge commit with semi-linear history) or `ff` (fast-forward merge). [DOC S-4yvdwu5c]
- With the semi-linear or fast-forward method a merge request can be accepted only when a fast-forward is possible; the user is then offered a rebase. `automatic_rebase_enabled` (boolean, introduced in 19.4) rebases the source branch on the target automatically before merge for those two methods. [DOC S-4yvdwu5c, S-6aknk2k6]
- An automatic rebase before merge does not run the pipeline again on the rebased result, needs a rebase without conflicts, and removes GPG signatures from the rebased commits. [DOC S-6aknk2k6]
- `squash_option` (string) is one of `never`, `always`, `default_on` or `default_off`. [DOC S-4yvdwu5c]
- The squash page describes four project choices: **Do not allow** (never squashed, option not shown), **Allow** (off by default), **Encourage** (on by default) and **Require** (always squashed, users cannot change it); it pairs none of them with an API value. [DOC S-j2fhtiru]
- So `never` is **Do not allow**, `default_off` is **Allow**, `default_on` is **Encourage** and `always` is **Require**: the value names say what the page's descriptions say. [DER S-4yvdwu5c, S-j2fhtiru: value names against the described behaviours]
- Squash options are set per project by the Maintainer or Owner role; a single merge request can still choose squashing when the project allows it, through `squash` on `PUT .../merge` or `merge_request.squash` (17.2+) on a push. [DOC S-j2fhtiru, S-4abgkvor, S-2d2dlaeq]
- `squash_commit_template` and `merge_commit_template` (strings) set the project's templates for the squash commit message and the merge commit message. [DOC S-4yvdwu5c]
- `lfs_enabled` (boolean) is written as "Enable LFS" and read back as whether Git LFS is enabled for the project. [DOC S-4yvdwu5c]
- `shared_runners_enabled` (boolean) is written as "Enable instance runners for this project" and read back as whether shared runners are enabled; `group_runners_enabled` is the matching switch for group runners. The page's own example toggles instance runners with `PUT` and `shared_runners_enabled=true`. [DOC S-4yvdwu5c]
- `public_jobs` (boolean) is written as "jobs can be viewed by non-project members" and read back as whether job logs are publicly accessible; `public_builds` is its deprecated name. [DOC S-4yvdwu5c]
- `container_registry_access_level` and `merge_requests_access_level` are feature-visibility attributes: each takes `disabled`, `private` (**Only project members**) or `enabled` (**Everyone with access**); `public` exists only for `pages_access_level`. [DOC S-4yvdwu5c]
- For the container registry, `private` means visible only to project members with the Reporter role or higher, and `enabled` (the default) follows the project's own visibility. [DOC S-gqpmeuse]
- `container_registry_enabled` is deprecated in favour of `container_registry_access_level`, and `merge_requests_enabled` in favour of `merge_requests_access_level`; the deprecation table spells the second alternative `merge_request_access_level`, a name that no attribute table lists. [DOC S-4yvdwu5c]
- Attributes of the same call that bear on automated merges and pipelines: `merge_pipelines_enabled` (merged results pipelines), `merge_trains_enabled`, `merge_train_enforcement` (generally available in 19.3; `allow_bypass`, `enforce_for_all_users` or `enforce_with_owner_override`), `ci_skip_branch_pipelines_for_mrs` (19.4), `protect_merge_request_pipelines` (18.10), `ci_push_repository_for_job_token_allowed` (17.2) and `ci_pipeline_variables_minimum_override_role`. [DOC S-4yvdwu5c]
- A project's merge regime is therefore read with one `GET /projects/:id` and compared field by field with the wanted values; the page says the fields returned vary with the permissions of the authenticated user, so a token with a lower role may see fewer of them. [DER S-4yvdwu5c: the read tables and the permissions note]

## Reference
| Attribute | Type | Values or effect | Source |
|---|---|---|---|
| `only_allow_merge_if_pipeline_succeeds` | boolean | **Pipelines must succeed** | S-4yvdwu5c |
| `allow_merge_on_skipped_pipeline` | boolean | merge with skipped jobs | S-4yvdwu5c |
| `remove_source_branch_after_merge` | boolean | **Delete source branch** on by default for new merge requests | S-4yvdwu5c |
| `merge_method` | string | `merge`, `rebase_merge`, `ff` | S-4yvdwu5c |
| `squash_option` | string | `never`, `always`, `default_on`, `default_off` | S-4yvdwu5c |
| `lfs_enabled` | boolean | Git LFS | S-4yvdwu5c |
| `shared_runners_enabled` | boolean | instance runners | S-4yvdwu5c |
| `public_jobs` | boolean | job logs visible to non-members | S-4yvdwu5c |
| `container_registry_access_level` | string | `disabled`, `private`, `enabled` | S-4yvdwu5c, S-gqpmeuse |
| `merge_requests_access_level` | string | `disabled`, `private`, `enabled` | S-4yvdwu5c |

See also `gitlab/automated-merge-requests.md` (auto-merge, push options, `detailed_merge_status`), `gitlab/protected-branches-tags.md` (who may push and merge), `gitlab/package-registries.md` (registry visibility), `gitlab/deploy-keys-and-tokens.md` (tokens that may call this API).

## Examples
- SNIPPET: set a project's merge regime in one call (pipelines must succeed, squash encouraged, source branch deleted by default, semi-linear history); context: GitLab 19.x, token with the `api` scope and the Maintainer role, `<project_id>` is the numeric project ID; checked: no [DER S-4yvdwu5c: attributes and values from the update table]
```bash
curl --request PUT \
  --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"only_allow_merge_if_pipeline_succeeds": true, "squash_option": "default_on", "remove_source_branch_after_merge": true, "merge_method": "rebase_merge"}' \
  --url "https://gitlab.corp.example.com/api/v4/projects/<project_id>"
```
