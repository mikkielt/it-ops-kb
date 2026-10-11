---
topic: gitlab/webhooks
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27); project webhooks Free, Premium and Ultimate, group webhooks Premium and Ultimate"
retrieved_utc: 2026-10-11
sources: [S-wqhdylac, S-3exaesy6, S-ulsd42b4, S-jz6gfnwh]
status: complete
---

# GitLab webhooks: authentication, event kinds, the push event payload

## Summary
A project webhook (Maintainer or Owner role) posts JSON to a url when chosen events happen. The receiver can check a request in two ways: the plain-text `X-Gitlab-Token` header, which carries the secret token as set (weak, not recommended for new webhooks), or an HMAC-SHA256 `webhook-signature` header computed with a signing token (introduced in 19.0, generally available in 19.1). Event kinds are chosen with booleans such as `push_events` and `merge_requests_events`, and each delivery names its kind in `X-Gitlab-Event`. A push event has `object_kind` `push`, the `before` and `after` commit ids, `ref`, `ref_protected`, a capped `commits` array and `total_commits_count`; tags come as a separate tag event, and a push of more than three branches or tags sends nothing. A receiver that fails four times in a row is disabled for a while, and after forty failures for good.

## Facts
- Project webhooks need the Maintainer or Owner role for the project; group webhooks are Premium and Ultimate and need the Owner role for the group. A webhook is created under **Settings > Webhooks** or with `POST /projects/:id/hooks`. [DOC S-wqhdylac]
- If the same webhook exists in a project and in its group, both fire for an event in that project. [DOC S-wqhdylac]
- The **secret token** is sent as plain text in the `X-Gitlab-Token` header, only when one is configured; the page rates it weaker than a signing token and not recommended for new webhooks. [DOC S-wqhdylac]
- The `token` attribute of the API carries the secret token and is not returned in a response; changing the webhook's url on update resets the secret token and does not keep it. [DOC S-ulsd42b4]
- A **signing token** (introduced in 19.0 behind the `webhook_signing_token` flag, generally available in 19.1) makes GitLab add a `webhook-signature` header: space-separated signatures of the form `v1,{base64_signature}`, each an HMAC-SHA256 over `{message_id}.{timestamp}.{body}` where the first two are the `webhook-id` and `webhook-timestamp` headers and the body is the raw JSON. [DOC S-wqhdylac]
- The signing key is the token without its `whsec_` prefix, base64-decoded; through the API a `signing_token` must be `whsec_<base64>` encoding a 32-byte key and is not returned. The receiver compares in constant time and should reject a stale `webhook-timestamp` against replay. [DOC S-wqhdylac, S-ulsd42b4]
- A webhook may hold both tokens during a migration: `X-Gitlab-Token` is still sent while a secret token is set, and `webhook-signature` is sent while a signing token is set. [DOC S-wqhdylac]
- Every delivery carries `X-Gitlab-Event` (the event type as `<EVENT> Hook`, for example `Push Hook`), `X-Gitlab-Instance` (the sending host), `X-Gitlab-Webhook-UUID`, `X-Gitlab-Event-UUID`, `User-Agent` `Gitlab/<VERSION>`, `webhook-id`, `webhook-timestamp` and `Idempotency-Key`; `webhook-id` equals `Idempotency-Key` and stays the same across retries. [DOC S-wqhdylac]
- Project and group webhooks can be sent for these event kinds: comment (note), deployment, emoji, feature flag, job, merge request, milestone, pipeline, project or group access token expiry, push, release, tag, vulnerability, wiki page, work item and a flow callback event; group webhooks alone add group member, project and subgroup events. [DOC S-3exaesy6]
- The `X-Gitlab-Event` values include `Push Hook`, `Tag Push Hook`, `Issue Hook`, `Note Hook`, `Merge Request Hook`, `Pipeline Hook`, `Job Hook`, `Deployment Hook`, `Release Hook`, `Wiki Page Hook`, `Resource Access Token Hook` and `Resource Deploy Token Hook`. [DOC S-3exaesy6]
- The create and update calls select events with booleans: `push_events`, `tag_push_events`, `merge_requests_events`, `pipeline_events`, `job_events`, `deployment_events`, `releases_events`, `note_events`, `issues_events`, `wiki_page_events`, `resource_access_token_events` and `resource_deploy_token_events`, among others; `PUT` and `POST` also take `url`, `enable_ssl_verification`, `custom_headers`, `custom_webhook_template`, `name` and `description`. [DOC S-ulsd42b4]
- Push events can be limited to branches with `push_events_branch_filter` and `branch_filter_strategy`, one of `wildcard` (the default), `regex` or `all_branches`; the regular-expression syntax is RE2. [DOC S-ulsd42b4, S-wqhdylac]
- A push event fires when pushing to the repository, except when the push carries tags or changes more than three branches; the limit is the `push_event_hooks_limit` setting (default 3), which an administrator of GitLab Self-Managed can change, and above it no webhook fires for the push at all. [DOC S-3exaesy6, S-wqhdylac]
- A tag event (`X-Gitlab-Event: Tag Push Hook`, `object_kind` `tag_push`) fires when tags are created or deleted, under the same three-reference limit; the example payload for a created tag has an all-zero `before`, `ref` `refs/tags/v1.0.0` and `ref_protected`. [DOC S-3exaesy6]
- The push event payload has `object_kind` (`push`), `event_name`, `before`, `after`, `ref` (for example `refs/heads/master`), `ref_protected`, `checkout_sha`, `message`, `user_id`, `user_name`, `user_username`, `user_email`, `user_avatar`, `project_id`, `project` (id, name, description, `web_url`, `git_ssh_url`, `git_http_url`, `namespace`, `visibility_level`, `path_with_namespace`, `default_branch`, `ci_config_path`, urls), `commits`, `total_commits_count`, `push_options` and `repository`. [DOC S-3exaesy6]
- Each entry of `commits` has `id`, `message`, `title`, `timestamp`, `url`, `author` (`name`, `email`) and the lists `added`, `modified` and `removed`; the array holds the newest 20 commits only, `total_commits_count` is the real number, and a branch pushed with no new commits has an empty `commits`. [DOC S-3exaesy6]
- An author without a public email in the profile has `[REDACTED]` as the payload's `email`; timestamps changed in 19.0 from `YYYY-MM-DD HH:MM:SS` with a zone to ISO 8601 with milliseconds. [DOC S-3exaesy6]
- GitLab disables a project or group webhook that fails four consecutive times (a `4xx` or `5xx` response, a timeout or another HTTP error): first for one minute, with the delay growing on later failures up to 24 hours, then it is enabled again; after 40 consecutive failures it is disabled permanently and returns only through a successful test request (a `2xx` response). The page says the feature's availability is controlled by a feature flag (`auto_disabling_web_hooks`, disabled on GitLab Self-Managed for project webhooks since 15.10). [DOC S-wqhdylac]
- A receiver should answer `200` or `201` quickly and queue the work, expect duplicate events after a timeout, and avoid `5xx` for events it accepted; `4xx` is for a misconfigured webhook. [DOC S-wqhdylac]
- Webhook management calls: `GET /projects/:id/hooks/:hook_id/events` (history, `status` filter), `POST .../events/:hook_event_id/resend`, `POST .../test/:trigger` (a trigger such as `push_events`) and `PUT`/`DELETE` of custom headers and url variables. [DOC S-ulsd42b4]
- Access token expiry events (`object_kind` `access_token`, `event_name` `expiring_access_token`, header `Resource Access Token Hook`) fire 7 days before expiry, and 30 and 60 days before when configured; the payload names the project or group and the token's `id`, `name`, `user_id`, `expires_at` and `last_used_at`. [DOC S-3exaesy6, S-jz6gfnwh]
- Pipeline webhooks triggered by blocked users are not processed. [DOC S-3exaesy6]
- So a receiver for pushes to the default branch compares `ref` with `refs/heads/` plus `project.default_branch`, takes `before` and `after` as the range, and treats `commits` as possibly cut at 20 by comparing its length with `total_commits_count`. [DER S-3exaesy6: the payload fields and the 20-commit cap]

## Reference
| Header | Meaning | Source |
|---|---|---|
| `X-Gitlab-Token` | secret token, plain text, only when configured | S-wqhdylac |
| `webhook-signature` | `v1,{base64}` HMAC-SHA256, only with a signing token | S-wqhdylac |
| `webhook-id`, `webhook-timestamp` | message id (stable across retries), unix seconds | S-wqhdylac |
| `X-Gitlab-Event` | `<EVENT> Hook` | S-wqhdylac, S-3exaesy6 |

See also `gitlab/detecting-mr-merges-in-ci.md` (telling a merge from a push after the fact), `gitlab/deploy-keys-and-tokens.md` (expiry events for tokens), `gitlab/automated-merge-requests.md` and `gitlab/project-settings-api.md`.

## Examples
- SNIPPET: verify a GitLab signing-token webhook delivery in Python; context: GitLab 19.1+, the signing token is held by the receiver as `whsec_...`, headers read case-insensitively; checked: syntax [DER S-wqhdylac: the documented verification steps]
```python
import base64
import hashlib
import hmac


def valid_signature(signing_token, message_id, timestamp, body, received_signatures):
    raw_key = base64.b64decode(signing_token.removeprefix("whsec_"))
    message = f"{message_id}.{timestamp}.{body}".encode("utf-8")
    digest = hmac.new(raw_key, message, hashlib.sha256).digest()
    expected = "v1," + base64.b64encode(digest).decode("utf-8")
    return any(hmac.compare_digest(expected, sig) for sig in received_signatures.split(" "))
```
