---
topic: gitlab/detecting-mr-merges-in-ci
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27): predefined CI/CD variables, Commits API, job token access, merge methods, GIT_DEPTH; GitHub Docs (github/docs @aff94963b07a8), webhook push payload and REST OpenAPI description (rest-api-description @2f44eaca, version 1.1.4), actions/checkout v7.0.1"
retrieved_utc: 2026-09-29
sources: [S-74hldnly, S-ijtwicvp, S-7zthwzzb, S-6aknk2k6, S-cnz6lcyx, S-hvhro6n5, S-mogzcl4y, S453, S-ghaubuwp, S-l4z4kyf6, S-o6lmrcgh, S-a3twjpzx, S-ldxeltib, S-gifxe3nj, S-xjpkoakf, S-yavpjhat]
status: complete
---

# Telling a merge request or pull request merge from a direct push, in CI

## Summary
A CI job that runs after a push to the default branch gets the push range from the platform (`CI_COMMIT_BEFORE_SHA` and `CI_COMMIT_SHA` on GitLab; `before` and `after` in the push event payload on GitHub) and can ask the platform's API which merge request or pull request introduced a commit: `GET /projects/:id/repository/commits/:sha/merge_requests` on GitLab (a job token may call it) and `GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls` on GitHub. The pipeline source alone does not tell the two cases apart, the merge commit message is a project template, and fast-forward, squash and rebase merges leave no merge commit, so the API association is the documented signal. A shallow clone limits how much of the range the job can read.

## Facts
- `CI_COMMIT_BEFORE_SHA` is the previous latest commit present on the branch or tag; it is always `0000000000000000000000000000000000000000` for merge request pipelines, scheduled pipelines, the first commit in a branch or tag pipeline, and manually run pipelines. [DOC S-74hldnly]
- `CI_COMMIT_BRANCH` is set in branch pipelines (the default branch's included) and not in merge request or tag pipelines; `CI_DEFAULT_BRANCH` is the default branch's name; `CI_COMMIT_REF_PROTECTED` is `true` when the job runs for a protected ref. [DOC S-74hldnly]
- `CI_MERGE_REQUEST_EVENT_TYPE` is `detached`, `merged_result` or `merge_train` in a merge request pipeline; `CI_COMMIT_DEFAULT_BRANCH_BASE_SHA` (GitLab 19.1) is the merge base with the default branch and exists only in non-default-branch pipelines. [DOC S-74hldnly]
- `CI_PIPELINE_SOURCE` is `push` for a Git push (branches and tags) and `merge_request_event` when a merge request is created or updated; the values match the `source` field of the pipelines API. [DOC S453]
- The pages read do not state which `CI_PIPELINE_SOURCE` the pipeline on the default branch has after a merge request is merged, nor whether it differs from the pipeline of a direct push. [UNK: not stated on the pages read; see _gaps.md]
- `GET /projects/:id/repository/commits/:sha/merge_requests` (Free, all offerings) returns the merge request that originally introduced the commit; its optional `state` parameter (GitLab 18.2) takes `opened`, `closed`, `locked` or `merged`; each merge request has `iid`, `source_branch`, `target_branch`, `state`, `merge_commit_sha` and `squash_commit_sha`. [DOC S-ijtwicvp]
- A CI/CD job token can call `GET /projects/:id/repository/commits/:sha`, `.../commits/:sha/merge_requests` and `.../commits/:sha/refs` (the last since 19.4), and `GET /projects/:id/merge_requests`, without a personal access token, sent in the `JOB-TOKEN` header. [DOC S-7zthwzzb]
- Merge methods: **Merge commit** always creates a merge commit (like `git merge --no-ff`), also when squashing; **semi-linear history** creates a merge commit but only when a fast-forward is possible; **Fast-forward merge** (like `--ff-only`) creates none, and with squash the single squash commit is fast-forwarded. [DOC S-6aknk2k6]
- The default merge commit message is `Merge branch '%{source_branch}' into '%{target_branch}'` plus the title, the issues and `See merge request %{reference}`; the template is a project setting (500 characters at most), and the default squash message is `%{title}`. [DOC S-cnz6lcyx]
- `GIT_DEPTH` makes the runner's `git fetch` and `git clone` shallow; new projects default to a Git shallow clone depth of 20 (settable up to 1000; empty or `0` disables it), and a value too small for the commit under test ends in `unresolved reference` in the job log. [DOC S-hvhro6n5, S-mogzcl4y]
- The `push` webhook payload has `before` and `after` (the newest commit on the ref before and after the push), `ref`, `created`, `deleted`, `forced`, `base_ref`, `compare`, `pusher`, `head_commit` and `commits`, which holds the pushed commits (those in the compare between `before` and `after`) up to a maximum of 2048; more come from the Commits API. [DOC S-ghaubuwp]
- No push event is created when more than 5000 branches are pushed at once, or for tags when more than three tags are pushed at once. [DOC S-ghaubuwp]
- `GITHUB_EVENT_PATH` is the path of a file on the runner holding the full event payload and `GITHUB_EVENT_NAME` the event name; `GITHUB_BASE_REF` is set only for `pull_request` and `pull_request_target`. [DOC S-l4z4kyf6]
- `GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls` lists the merged pull request that introduced the commit to the repository; for a commit not in the default branch it returns merged and open pull requests, and `commit_sha` can be a branch name; it takes `per_page` (default 30, at most 100) and `page` (default 1) and answers `409` on a conflict. [DOC S-o6lmrcgh]
- The fine-grained token for `GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls` needs the "Pull requests" repository permission (read); it works with GitHub App user and installation access tokens and fine-grained personal access tokens, and needs no token or permission when only public resources are requested. [DOC S-xjpkoakf]
- A workflow's `GITHUB_TOKEN` takes `pull-requests: read|write|none` in its `permissions` key, and when any permission is specified every one not specified is set to `none`; a job that calls the pulls endpoint therefore lists `pull-requests: read` (and `contents: read` if it also checks out). [DER S-xjpkoakf, S-yavpjhat: the endpoint's permission mapped to the token key]
- `actions/checkout` fetches a single commit by default (`fetch-depth: 1`); `fetch-depth: 0` fetches all history for all branches and tags. [DOC S-a3twjpzx]
- Rebase and merge creates new commit SHAs and squash and merge one new commit, so a commit's SHA on the base branch differs from the SHA on the pull request branch; a pull request is also marked merged when its commits reach the default branch by a direct push. [DOC S-gifxe3nj, S-ldxeltib]
- A check that runs on a push to the default branch takes the pushed range (`CI_COMMIT_BEFORE_SHA..CI_COMMIT_SHA` on GitLab, `before..after` from the event file on GitHub), lists its commits and, for each commit that changes protected paths, asks the platform for the merge request or pull request that introduced it; a commit with none reached the branch directly. A new branch has an all-zero before value on GitLab, so the range is the branch's commits not on the default branch. [DER S-74hldnly, S-ijtwicvp, S-ghaubuwp, S-o6lmrcgh: range variables and association endpoints]
- Reading the merge commit message (`See merge request`) proves nothing, because the template is configurable and fast-forward or squash merges produce no such message, and the commit-message text of a direct push can be typed by anyone; the association endpoints are the documented signal. [DER S-cnz6lcyx, S-6aknk2k6, S-gifxe3nj]
- The job must have the range in its clone: raise `GIT_DEPTH` (or set it to `0`) on GitLab and `fetch-depth: 0` on GitHub, or fetch the missing commits before the range check, since a push of more commits than the depth leaves the before commit absent. [DER S-hvhro6n5, S-mogzcl4y, S-a3twjpzx: default depths]

## Reference
| Need | GitLab | GitHub | Source |
|---|---|---|---|
| Push range | `CI_COMMIT_BEFORE_SHA`, `CI_COMMIT_SHA` | `before`, `after` in `GITHUB_EVENT_PATH` | S-74hldnly, S-ghaubuwp, S-l4z4kyf6 |
| New ref | before is 40 zeros | not stated on the page read | S-74hldnly |
| Default branch name | `CI_DEFAULT_BRANCH` | repository setting (API) | S-74hldnly |
| Merge request or pull request of a commit | `GET /projects/:id/repository/commits/:sha/merge_requests` | `GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls` | S-ijtwicvp, S-o6lmrcgh |
| Token in CI | `CI_JOB_TOKEN` (`JOB-TOKEN` header) | workflow token (`GITHUB_TOKEN`), `pull-requests: read` | S-7zthwzzb, S-xjpkoakf, S-yavpjhat |
| History available | `GIT_DEPTH` (default 20 in new projects) | `fetch-depth` (default 1) | S-hvhro6n5, S-mogzcl4y, S-a3twjpzx |
| Merge without a merge commit | fast-forward merge, squash | squash and merge, rebase and merge | S-6aknk2k6, S-gifxe3nj |

See also `gitlab/pipelines-rules.md` (`CI_PIPELINE_SOURCE` and rules), `gitlab/automated-merge-requests.md` (pipelines API, job-token pushes), `gitlab/github-branch-rules-and-auto-merge.md`, `gitlab/git-trailers-and-hooks.md` (a `pre-push` hook reads the same range client-side).

## Examples
- SNIPPET: list the merge requests that introduced the newest pushed commit from a GitLab CI job; context: GitLab CI job with `GIT_DEPTH` large enough for the range, `CI_JOB_TOKEN` allowed for the Commits API, `jq` on the runner; checked: no [DER S-ijtwicvp, S-7zthwzzb, S-74hldnly: endpoint, `JOB-TOKEN` header, variables]
```bash
curl --silent --header "JOB-TOKEN: $CI_JOB_TOKEN" \
  "$CI_API_V4_URL/projects/$CI_PROJECT_ID/repository/commits/$CI_COMMIT_SHA/merge_requests?state=merged" \
  | jq '[.[] | {iid, target_branch, merge_commit_sha}]'
```
