---
topic: gitlab/deploy-keys-and-tokens
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27); Free, Premium and Ultimate unless stated"
retrieved_utc: 2026-10-11
sources: [S-muzlee2k, S-zsu6jh7l, S-5imiypdp, S-ksmw56nm, S-jz6gfnwh, S-4ziu3orn, S-jk4rtq6g, S-swggstpk, S-5ohrrj7d, S-3exaesy6]
status: partial
---

# Deploy keys, deploy tokens and group access tokens

## Summary
Three credentials give automation access to GitLab without a person's account, with different reach. A **deploy key** is a public SSH key for Git over SSH only, per project or shared instance-wide, with no API or registry access. A **deploy token** is a username and token pair for Git over HTTP and the package and container registries, not for the GitLab public API except the package registry endpoints (URLs with `packages/<format>`), at project or group level, with no expiry unless one is set. A **group access token** is a bot user's token with a role and scopes (`api` among them) that reaches the group's subgroups and projects, created by a group Owner, expiring within 365 days by default. Only the group access token can call the API for a whole group.

## Facts
### Deploy keys
- A deploy key is a public SSH key generated on an external host, used to reach a repository over SSH from a build or CI server; the same key can be shared by several projects, even in different groups. [DOC S-muzlee2k]
- A deploy key cannot be used with the GitLab API or the registry, and cannot be used for Git operations when external authorization is on. [DOC S-5ohrrj7d, S-muzlee2k]
- The scope is fixed at creation: a **project deploy key** reaches only its project; a **public deploy key** can be granted to any project of the instance, each grant needing the Maintainer or Owner role of that project. Public deploy keys are created by an administrator, on GitLab Self-Managed and Dedicated. [DOC S-muzlee2k]
- A deploy key is read-only or read-write; the permission level can be changed later, and for a project deploy key the change applies to the current project only. [DOC S-muzlee2k]
- Creating a project deploy key needs the Maintainer or Owner role; the key is enabled in the project at once and has an optional **Expiration date**. [DOC S-muzlee2k]
- A push with a deploy key is authorized as the key's creator: for a protected branch the creator must have access to the branch, and for a pipeline the push starts the creator must have access to the CI/CD resources, protected environments and secret variables included. [DOC S-muzlee2k]
- A deploy key is rejected, for pulls and pushes alike, when its owner is blocked or the key has expired; it is not rejected when its owner is only removed from the group or project, and keeps working until revoked. [DOC S-muzlee2k]
- The page recommends creating deploy keys with a service account: a key made by another user gives that user privileges that last until the key is revoked. [DOC S-muzlee2k]
- When a deploy key is named in a protected branch rule, its creator gains access to the branch and, with a read-write key, can push to it even if the branch is protected against all users. [DOC S-muzlee2k]
- A project's deploy keys are managed with `POST /projects/:id/deploy_keys` (`key`, `title`, optional `can_push` and `expires_at` in ISO 8601, no expiry when omitted), `PUT .../:key_id` (`can_push` and `title` only), `POST .../:key_id/enable` for an existing key and `DELETE .../:key_id`, which also deletes a key used by no other project. [DOC S-zsu6jh7l]
- `POST /deploy_keys` creates an instance deploy key (administrator only, GitLab Self-Managed and Dedicated, since 17.5). [DOC S-zsu6jh7l]
### Deploy tokens
- A deploy token is a username and token pair; the default username is `gitlab+deploy-token-{n}` and a custom one can be set at creation; deploy tokens do not support SSH. [DOC S-5imiypdp]
- Deploy tokens authenticate to the package registry public API, to Git commands and to the virtual registry package operations; they cannot be used with the GitLab public API except for package registry endpoints (URLs with `packages/<format>`). [DOC S-5imiypdp]
- A deploy token belongs to a project or to a group; a group deploy token's permissions apply to all projects in the group. [DOC S-5imiypdp]
- By default a deploy token does not expire; an expiry date may be set at creation and takes effect at midnight UTC. The deploy token page states no maximum lifetime. [DOC S-5imiypdp]
- The scopes are `read_repository`, `read_registry`, `write_registry` (pushing needs `read_registry` too), `read_package_registry`, `write_package_registry`, and `read_virtual_registry` and `write_virtual_registry`, which exist only when the Dependency Proxy is enabled. [DOC S-5imiypdp]
- Creating or revoking a project deploy token needs the Maintainer or Owner role; a group deploy token needs the Owner role of the group, and a Maintainer of the group may list them. The value is shown once. [DOC S-5imiypdp, S-ksmw56nm]
- The API creates them with `POST /projects/:id/deploy_tokens` and `POST /groups/:id/deploy_tokens`: `name`, `scopes`, optional `expires_at` (ISO 8601, no expiry when omitted) and `username`. The project endpoint's scope list names the two virtual-registry scopes and the group endpoint's list does not. [DOC S-ksmw56nm]
- A deploy token named `gitlab-deploy-token` is exposed to the project's CI/CD jobs as `CI_DEPLOY_USER` and `CI_DEPLOY_PASSWORD`; defined in a group, the variables reach only the group's immediate child projects. [DOC S-5imiypdp]
- The token prefix is `gldt-`. [DOC S-5ohrrj7d]
- Expiry emails 60, 30 and 7 days before a deploy token expires, and a webhook event `Resource Deploy Token Hook` (`event_name` `expiring_deploy_token`), arrive only with the `project_deploy_token_expiring_notifications` feature flag, which is off by default (introduced in 18.3 for email, 18.4 for the webhook). [DOC S-5imiypdp, S-3exaesy6]
### Group access tokens
- A group access token is attached to a group, not to a user; it authenticates to the API and to Git over HTTPS (any non-blank username, the token as password) and cannot create other group, project or personal access tokens. [DOC S-jz6gfnwh]
- Creating one needs the Owner role for the group; on GitLab.com it needs a Premium or Ultimate subscription and is unavailable in a trial, while Self-Managed and Dedicated have it with any license. [DOC S-jz6gfnwh]
- Creating one makes a bot user named `group_{group_id}_bot_{random_string}`, a non-billable member of the group that inherits membership in subgroups and projects and cannot be added to other groups or projects. [DOC S-jz6gfnwh]
- The API `POST /groups/:id/access_tokens` takes `name`, `scopes` (required), `description` (255 characters at most), `access_level` (`10` Guest, `15` Planner, `20` Reporter, `25` Security Manager, `30` Developer, `40` Maintainer or `50` Owner; default `40`) and `expires_at`. [DOC S-4ziu3orn]
- Scopes available to a group access token: `api`, `read_api`, `read_repository`, `write_repository`, `read_registry`, `write_registry`, `self_rotate`, `read_virtual_registry`, `write_virtual_registry`, `create_runner`, `manage_runner`, `ai_features` and `k8s_proxy`; `admin_mode`, `read_service_ping`, `sudo` and `read_user` are personal-token scopes. [DOC S-jk4rtq6g]
- A group access token reaches the subgroups and projects of its group; a project access token only its project and a personal access token everything its user can reach. For group and project tokens `write_registry` needs `read_registry` alongside it. [DOC S-jk4rtq6g]
- The token prefix is `glpat-`, as for personal and project access tokens. [DOC S-5ohrrj7d]
- Without an expiry date in the UI the token expires 365 days from today, and by default a date may not be more than 365 days away; in the API an undefined `expires_at` defaults to the maximum allowable lifetime when the token must expire. Expiry is at midnight UTC. [DOC S-jz6gfnwh, S-4ziu3orn]
- An administrator on GitLab Self-Managed or Dedicated (Ultimate) can set a maximum lifetime for personal, group and project access tokens, 365 days at most by default and 400 days behind the `buffered_token_expiration_limit` feature flag (disabled by default, not on Dedicated); only an administrator can set it. [DOC S-swggstpk, S-jz6gfnwh]
- When a maximum lifetime is set, GitLab requires an expiry within it for new personal tokens and, after three hours, revokes old tokens with no expiry or a longer lifetime. [DOC S-swggstpk]
- Expiry emails go to direct Owners 7 days before, and 30 and 60 days before since 17.6; the webhook event `Resource Access Token Hook` (`event_name` `expiring_access_token`) fires 7 days before, and 30 and 60 days only when configured. [DOC S-jz6gfnwh, S-3exaesy6]
- `POST /groups/:id/access_tokens/:token_id/rotate` revokes the token at once and returns a new one (`expires_at` defaults to one week when the token must expire); `token_id` may be `self`, and rotating another token needs a personal access token with `api`, while self-rotation needs `api` or `self_rotate`. [DOC S-4ziu3orn]
- Rotating a token that was already revoked revokes the active tokens of its family (automatic reuse detection). [DOC S-4ziu3orn]
- A revoked group token is deleted after 30 days by default and an expired one stays in the inactive list until it is deleted automatically; a top-level group Owner can switch off the creation of group and project access tokens for the whole group (Premium or Ultimate on GitLab.com), and existing tokens stay valid until they expire or are revoked. [DOC S-jz6gfnwh]
- Open: whether the SSH key lifetime setting or the access token lifetime setting limits deploy keys or deploy tokens is not stated on any page read. [UNK: the deploy pages and the account and limit settings page name neither]
### How it fits
- Reach by token kind: deploy key, one project (or any project of the instance when public), Git over SSH; deploy token, one project or one group, Git over HTTP and registries; group access token, one group, API, Git and registries; project access token, one project. [DER S-muzlee2k, S-5imiypdp, S-jz6gfnwh, S-jk4rtq6g: scope of each page]
- An automation that only fetches code and packages for a group's projects can hold a group deploy token with `read_repository` and `read_package_registry`, which cannot call the GitLab public API except the package registry endpoints; one that opens merge requests, plays schedules or changes settings needs a group (or project) access token with `api`, whose role (default Maintainer) bounds what it may do. [DER S-5imiypdp, S-jk4rtq6g, S-4ziu3orn: the public API is closed to deploy tokens except the package registry endpoints, `api` is the scope that grants it]
- Because a deploy token has no lifetime limit and the lifetime setting names only access tokens, a deploy token needs an expiry set by the creator and a watch on the expiry events if it must not live forever. [DER S-5imiypdp, S-ksmw56nm, S-swggstpk: no maximum on the deploy token pages, the setting lists three access token kinds]

## Reference
| Credential | Reach | Transport | Expiry default | Created by |
|---|---|---|---|---|
| Deploy key | project, or any project when public | Git over SSH | none (optional date) | Maintainer or Owner (public: administrator) |
| Deploy token | project or group | Git over HTTP, package and container registries | none (optional date) | Maintainer or Owner (group: Owner) |
| Group access token | group, its subgroups and projects | API, Git over HTTPS, registries | 365 days from creation | Owner of the group |

See also `agents/api-tokens-issue-and-store.md` (personal access tokens and storing secrets), `auth/revocation.md` (revoking tokens), `gitlab/project-settings-api.md` (the API that a token with `api` can call), `gitlab/webhooks.md` (expiry events), `gitlab/protected-branches-tags.md` (deploy keys in push and create rules) and `gitlab/package-registries.md` (using these credentials against the registries).

## Examples
- SNIPPET: create a group access token that can call the API for a group's projects and expires in a stated number of days; context: GitLab 19.x, the caller is the group Owner holding a token with the `api` scope, `<group_id>` is the numeric group ID; checked: no [DER S-4ziu3orn: attributes from the create table]
```bash
curl --request POST \
  --header "PRIVATE-TOKEN: $OWNER_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"name": "estate-automation", "scopes": ["api"], "access_level": 30, "expires_at": "2027-01-31"}' \
  --url "https://gitlab.corp.example.com/api/v4/groups/<group_id>/access_tokens"
```
