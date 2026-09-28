---
topic: gitlab/pipelines-rules
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97)"
retrieved_utc: 2026-09-28
sources: [S446, S447, S448, S451, S453, S-zh7oqkup]
status: complete
---

# Merge-request pipelines, `rules:`, scheduled pipelines, release jobs

## Summary
- MR pipelines (Free) run only when `rules:` or `workflow:rules` in `.gitlab-ci.yml` match `$CI_PIPELINE_SOURCE == "merge_request_event"`. Rules pulled in through `include:` don't count.
- `rules` are checked in order, and the first match wins. With no match the job isn't added. `when: never` excludes it.
- Scheduled pipelines (Free) run with the **schedule owner's** permissions. Protected targets need merge rights (branch) or tag-create rights (tag).
- The `release` keyword now uses the `glab` CLI (v1.58.0+). `release-cli` won't be supported after GitLab 20.0.

## Facts
- MR pipelines run on MR creation, on a push to the source branch, or from **Run pipeline** on the MR's Pipelines tab. They use the source branch contents only. [DOC S446]
- Prerequisites: job or workflow rules matching `CI_PIPELINE_SOURCE == "merge_request_event"` defined directly in `.gitlab-ci.yml`; the Developer role or higher on the source project; a GitLab-hosted repository. [DOC S446]
- Merged results pipelines test the merge of source and target. [DOC S446]
- Merged results pipelines are Premium and Ultimate only (GitLab.com, Self-Managed, Dedicated): they test a temporary merged commit of source and target that exists in neither branch. [DOC S-zh7oqkup]
- Protected variable and runner access for MR pipelines is an opt-in project setting (GitLab 18.1). Fork MR pipelines never get it. [DOC S446]
- Each rule needs at least one of `if`, `changes`, `exists`, `when`. It can add `allow_failure`, `needs`, `variables`, `interruptible`. [DOC S447]
- A job is added if an `if`/`changes`/`exists` rule matches with `when` of `on_success` (default), `delayed` or `always`. It isn't added if nothing matches or the match has `when: never`. [DOC S447]
- `workflow:rules` controls the whole pipeline. It adds `workflow:rules:variables` and `workflow:rules:auto_cancel`. [DOC S447]
- Schedules use cron notation, limited by the instance's maximum scheduled-pipeline frequency. A schedule can have at most 20 inputs. [DOC S448]
- The creator becomes the schedule owner, and the pipeline runs with the owner's permissions. Running it manually uses the permissions of the user who runs it. [DOC S448]
- Creating or editing needs the Developer role or higher. Protected branches need merge permission, and protected tags need create permission. [DOC S448]
- If the owner is blocked or removed, the schedule becomes inactive. A Maintainer or Owner can **Take ownership**. [DOC S448]
- `CI_PIPELINE_SOURCE` tells rules which pipeline type is running: `merge_request_event` (MR created or updated; needed for MR pipelines, merged results and merge trains), `push` (Git push, branches and tags), `schedule`, `web`, `api`, `trigger`, `parent_pipeline`, `pipeline` and others; the values match the `source` field of the pipelines API. [DOC S453]
- Releases tier: Free, Premium, Ultimate. Release Metrics: Ultimate. [DOC S451]
- The `release` job needs `glab` on `$PATH`. It creates the release with `glab release create`. The release-cli image `v0.24.0` contains glab `v1.58.0`. [DOC S447,S451]
- The documented release job pattern uses `rules: - if: $CI_COMMIT_TAG` and `tag_name: '$CI_COMMIT_TAG'`. [DOC S451]

## Reference
| Pipeline source value | Meaning | Source |
|---|---|---|
| `merge_request_event` | MR created or updated (MR, merged results, merge trains) | S446,S453 |
| `push` | Git push, branches and tags | S453 |
| `schedule` | scheduled pipeline | S453 |

See also `gitlab/automated-merge-requests.md` (push options that open an auto-merging MR, job-token pushes).

## Examples
- SNIPPET: a pipeline gated to MR pipelines and tag pushes, with a tag-triggered `release` job using `glab`; context: GitLab CI, `release-cli` image v0.24.0 (glab v1.58.0+); checked: no [DER S446,S447,S451: `merge_request_event` workflow rule, the `if: $CI_COMMIT_TAG` release rule, and the `release:` keyword's `tag_name` field combined into one pipeline]
```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_TAG =~ /^(v|release-)/
checks:
  script: [python ci/checks.py]
release:
  rules:
    - if: $CI_COMMIT_TAG
  script: [echo "release $CI_COMMIT_TAG"]
  release:
    tag_name: $CI_COMMIT_TAG
    description: "release content $CI_COMMIT_TAG"
```

See also: `claude/ci-and-headless.md` — a Claude Code job gated with `rules: - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'`,
the pattern documented here.
