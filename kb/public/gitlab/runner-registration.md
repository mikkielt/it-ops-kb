---
topic: gitlab/runner-registration
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27); GitLab Runner docs (gitlab-org/gitlab-runner main @a278fd05, 2026-10-09); Free, Premium and Ultimate unless stated"
retrieved_utc: 2026-10-11
sources: [S-ytnvr75r, S-fsqu2grq, S-ssfsxd2n, S-5ohrrj7d, S-jk4rtq6g]
status: partial
---

# Runner registration by runner authentication token (`glrt-`) through the API

## Summary
A runner is created first in GitLab and registered after: `POST /user/runners` (an access token with the `create_runner` scope, held by an administrator or the Owner of the target group or project) returns a runner authentication token with the prefix `glrt-`, shown once, and `gitlab-runner register --non-interactive --token <that token>` writes it into `config.toml`. The older route, a runner registration token passed to `POST /runners`, is deprecated, disabled by default since GitLab 17.0 and scheduled for removal in 20.0. `POST /runners/verify` checks a token and needs `system_id` for a `glrt-` one. Whether a group access token may call `POST /user/runners` is not stated.

## Facts
- Connecting a runner takes an authentication token, which the register page says comes from creating an instance, group or project runner in GitLab or from the `config.toml` of an existing runner. The Runners API page names three more sources: registering with a legacy registration token, resetting the token of an existing runner, and `POST /user/runners`. [DOC S-ssfsxd2n, S-ytnvr75r]
- The authentication token goes into the runner's `config.toml` under `[[runners]]` as `token`; GitLab and the runner are then connected. [DOC S-ytnvr75r]
- `POST /user/runners` creates a runner linked to the current user, who is listed as its owner for audit; availability follows `runner_type`. [DOC S-fsqu2grq]
- Prerequisites of `POST /user/runners`: an administrator or the Owner role for the target namespace or project; an administrator for `instance_type`; for `group_type` or `project_type` with an Owner role, runner registration must be allowed in the settings; and an access token with the `create_runner` scope. [DOC S-fsqu2grq]
- Attributes: `runner_type` (required: `instance_type`, `group_type` or `project_type`), `group_id` (required for `group_type`), `project_id` (required for `project_type`), `description`, `paused`, `locked`, `run_untagged`, `tag_list` (comma-separated), `access_level` (`not_protected` or `ref_protected`), `maximum_timeout` (seconds) and `maintenance_note` (1024 characters). [DOC S-fsqu2grq]
- `token_expires_at` (ISO 8601, between 5 minutes and 15 days ahead, within any instance, group or project limit, applied to the initial token only) and `token_rotation_deadline` are Premium attributes; the response has `id`, `token` and `token_expires_at`, and the token cannot be retrieved again. [DOC S-fsqu2grq]
- `create_runner` and `manage_runner` are scopes of personal, group and project access tokens; `manage_runner` was introduced in 17.1. [DOC S-jk4rtq6g]
- Runner authentication tokens carry the prefix `glrt-`, or `glrtr-` when the runner was created through a registration token. [DOC S-5ohrrj7d]
- To register, `gitlab-runner register` asks for the GitLab url, the authentication token, a description, tags, a maintenance note and the executor; the non-interactive form takes `--non-interactive --url <url> --token <token> --executor <executor>` and further executor options, and the result is saved to `config.toml`. [DOC S-ssfsxd2n]
- The same authentication token registered on several host machines reuses one runner configuration. [DOC S-ssfsxd2n]
- `POST /runners/verify` with `token` returns `200` for valid credentials and `403` for invalid ones; `system_id` is required when the token starts with `glrt-`. [DOC S-ytnvr75r]
- `POST /runners` creates a runner from a registration token: it answers `201`, `403` for an invalid registration token and `410 Gone` when registration with registration tokens is disabled in the project or group; the endpoint is flagged deprecated, registration tokens are disabled by default in GitLab 17.0 and later, and `POST /user/runners` is the recommended route. [DOC S-ytnvr75r]
- Runner registration tokens and several registration arguments are deprecated and scheduled for removal in GitLab 20.0. [DOC S-ssfsxd2n]
- `POST /runners/:id/reset_authentication_token` (an access token with `manage_runner` and administrator, group Owner or project Maintainer or Owner rights) and `POST /runners/reset_authentication_token` with the current `token` both return a new `token` and its `token_expires_at`. [DOC S-ytnvr75r]
- `DELETE /runners/:id` needs `manage_runner` and the same rights; `DELETE /runners` with the runner's `token` form field removes a runner and answers `204`. [DOC S-ytnvr75r]
- The runner authentication token stays on the runner machine; the Docker Machine, Kubernetes, VirtualBox, Parallels and SSH executors' execution environments see only the job token. Anyone who reads `config.toml` can use the token to clone the runner. [DOC S-5ohrrj7d]
- A runner authentication token gives no API access and no direct repository access; it can only authenticate runners that then run jobs which do. [DOC S-5ohrrj7d]
- So an unattended registration is two calls with two credentials of different standing: an access token with `create_runner` held by an Owner (the creation), and the new `glrt-` token (the registration), which should be written to `config.toml` by the registration step and kept out of logs; the documented non-interactive form passes it as `--token`, a command-line value. [DER S-fsqu2grq, S-ssfsxd2n, S-5ohrrj7d: the prerequisites, the register command and where the token lives]
- Open: the documents say `POST /user/runners` is for "the current user" and list the Owner role as a prerequisite, but none says whether a group access token (a bot user) may call it. [UNK: not stated on the Users API, access token scopes or token overview pages]

## Reference
| Step | Call | Credential | Source |
|---|---|---|---|
| Create runner | `POST /user/runners` | access token, `create_runner`, Owner or administrator | S-fsqu2grq |
| Register | `gitlab-runner register --non-interactive --url U --token glrt-... --executor E` | the runner token | S-ssfsxd2n |
| Verify | `POST /runners/verify` (`token`, `system_id`) | the runner token | S-ytnvr75r |
| Rotate | `POST /runners/:id/reset_authentication_token` | `manage_runner` | S-ytnvr75r |
| Delete | `DELETE /runners/:id` or `DELETE /runners` | `manage_runner` or the runner token | S-ytnvr75r |

See also `windows/gitlab-runner-windows.md` (installing and running the runner on Windows), `gitlab/deploy-keys-and-tokens.md` (the access tokens that carry `create_runner`), `gitlab/hosted-runners-windows.md`.

## Examples
- SNIPPET: create a group runner and read its authentication token; context: GitLab 19.x, a token with the `create_runner` scope held by the group's Owner, `<group_id>` the numeric group ID; checked: no [DER S-fsqu2grq: attributes from the create table]
```bash
curl --request POST \
  --header "PRIVATE-TOKEN: $OWNER_TOKEN" \
  --data "runner_type=group_type" \
  --data "group_id=<group_id>" \
  --data "description=PL-SRV-0042" \
  --data "tag_list=windows" \
  --url "https://gitlab.corp.example.com/api/v4/user/runners"
```
