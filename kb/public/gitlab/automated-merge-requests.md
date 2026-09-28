---
topic: gitlab/automated-merge-requests
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27); Free tier and CE unless stated"
retrieved_utc: 2026-09-28
sources: [S-2d2dlaeq, S-rivqro7b, S-zh7oqkup, S-7zthwzzb, S446]
status: complete
---

# Merge requests from automation: push options, auto-merge, job-token pushes

## Summary
A script can open a merge request, set it to auto-merge and ask for its source branch to be deleted in the same `git push`, with push options and no API token. Auto-merge is in every tier and merges only when all merge checks pass, a successful pipeline among them. A CI job can push back to its own project with `CI_JOB_TOKEN` once a Maintainer turns on **Allow Git push requests to the repository** (GA in 18.4); such a push starts no pipeline. Merged results pipelines, which would test the merge with the target, are Premium and Ultimate only.

## Facts
- Git push options need Git 2.10 or later. [DOC S-2d2dlaeq]
- Merge-request push options: `merge_request.create` (from the default branch it needs `merge_request.target`), `merge_request.target=<branch>`, `merge_request.target_project=<project>`, `merge_request.auto_merge`, `merge_request.remove_source_branch`, `merge_request.squash` (17.2+), `merge_request.title`, `merge_request.description`, `merge_request.draft`, `merge_request.milestone`, `merge_request.label`/`unlabel`, `merge_request.assign`/`unassign`. [DOC S-2d2dlaeq]
- `merge_request.merge_when_pipeline_succeeds` was deprecated in GitLab 17.11 in favour of `merge_request.auto_merge`; the auto-merge page at the same commit still names the old option for the command line. [DOC S-2d2dlaeq, S-rivqro7b]
- Several options combine with repeated `-o`, for example `git push -o merge_request.create -o merge_request.target=<branch> -o merge_request.auto_merge`; option values cannot contain a literal newline (`fatal: push options must not have new line characters`). [DOC S-2d2dlaeq]
- CI push options (`ci.input`, `ci.skip`, `ci.no_pipeline`, `ci.variable`) are not available for merge request pipelines; `ci.skip` and `ci.variable` affect branch pipelines only. [DOC S-2d2dlaeq]
- Auto-merge is Free, Premium and Ultimate on GitLab.com, Self-Managed and Dedicated; enhanced auto-merge (merge when all checks pass) has been generally available since GitLab 17.7. [DOC S-rivqro7b]
- An auto-merge MR merges only when every merge check passes: required approvals, no blocking MR, no conflicts, a successful CI/CD pipeline (regardless of the project setting), resolved discussions, not a draft, external status checks passed, MR open, no denied policies, and any configured title pattern, Jira link or **Merge after** date. [DOC S-rivqro7b]
- Setting auto-merge needs the Developer, Maintainer or Owner role, all required approvals and, if configured, resolved threads. [DOC S-rivqro7b]
- When the pipeline fails, a retried job that succeeds merges the MR; new commits on the MR cancel auto-merge; new commits on the target cancel it under **Merge commit with semi-linear history** or **Fast-forward merge** unless automatic rebase before merge is on. [DOC S-rivqro7b]
- **Pipelines must succeed** (Maintainer or Owner) also blocks an MR that has no pipeline, and a skipped pipeline blocks too unless **Skipped pipelines are considered successful** is set; the project must run a pipeline for every MR. [DOC S-rivqro7b]
- Merged results pipelines are Premium and Ultimate only; on Free, MR pipelines use the source branch contents only. [DOC S-zh7oqkup, S446]
- `CI_JOB_TOKEN` has the access level of the user who triggered the pipeline (by push, manual job or schedule ownership). [DOC S-7zthwzzb]
- **Allow Git push requests to the repository** (Settings > CI/CD > Job token permissions, Maintainer or Owner; API parameter `ci_push_repository_for_job_token_allowed`) is off by default; introduced in 17.2 behind the flag `allow_push_repository_for_job_token`, generally available in 18.4. Only job tokens from the project's own pipelines can then push. [DOC S-7zthwzzb]
- A push authenticated with a job token triggers no CI/CD pipeline, and the token has the permissions of the user who started the job. The docs warn against turning the setting on for pull mirrors. [DOC S-7zthwzzb]
- Cross-project job-token pushes from allowlisted projects need a second setting and are generally available since 19.1. [DOC S-7zthwzzb]

- A bot branch on a Free or CE project is tested only as it stands, so it must be rebased on the target branch right before its push for its MR pipeline to test it against current `main`; auto-merge still merges only after that pipeline succeeds. [DER S-zh7oqkup, S-rivqro7b: no merged results pipelines below Premium; auto-merge needs a successful pipeline]
- A push with `merge_request.create`, `merge_request.target=main`, `merge_request.auto_merge` and `merge_request.remove_source_branch` opens an MR that merges itself once checks pass, over SSH, with no personal or project access token. [DER S-2d2dlaeq, S-rivqro7b]
- A failed auto-merge MR does not close itself: a retried job can still merge it. An automation that must never retry a red MR has to remove the possibility itself, for example by deleting the source branch from a failure job with a job-token push (`git push --delete`), which starts no pipeline. [DER S-rivqro7b, S-7zthwzzb: retry-merges rule; job-token push rules]
- A job-token push that records an outcome on `main` starts no pipeline, so it is not itself tested, and it runs with the rights of the user who started the job: branch protection cannot tell it from that user. [DER S-7zthwzzb]

## Reference
| Push option | Effect | Source |
|---|---|---|
| `merge_request.create` | open an MR for the pushed branch | S-2d2dlaeq |
| `merge_request.target=<b>` | target branch | S-2d2dlaeq |
| `merge_request.auto_merge` | set auto-merge | S-2d2dlaeq |
| `merge_request.remove_source_branch` | delete source branch on merge | S-2d2dlaeq |
| `merge_request.merge_when_pipeline_succeeds` | deprecated 17.11 | S-2d2dlaeq |

See also `gitlab/pipelines-rules.md` (MR pipelines, `merge_request_event`), `gitlab/mr-approvals.md` (approval tiers), `gitlab/protected-branches-tags.md`, `agents/docs-maintenance-agents.md` (committing machine-written data).

## Examples
- SNIPPET: push a bot branch as an auto-merging MR that deletes its branch on merge; context: Git 2.10+, GitLab 17.11+ (`auto_merge`), SSH remote; checked: no [DER S-2d2dlaeq: options from the push-options table]
```bash
git push -o merge_request.create -o merge_request.target=main \
  -o merge_request.auto_merge -o merge_request.remove_source_branch \
  origin querylog/PL-RUN-0001-alias
```
