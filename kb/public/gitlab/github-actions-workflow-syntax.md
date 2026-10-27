---
topic: gitlab/github-actions-workflow-syntax
priority: P3
applies_to: "GitHub Actions workflow files (.github/workflows/*.yml): workflow_dispatch inputs, job and step timeouts, status check functions, needs, and the standard GitHub-hosted runner for public repositories, as documented in the github/docs source at 4e811c0c read 2026-10-27"
retrieved_utc: 2026-10-27
sources: [S-or6ws3uz, S-zcsx2ltg, S-22hhnj7j, S-vvhj543i, S-eacxcx4x, S-n43vwkxh, S-v5kpgm6y, S-766tl7fe]
status: complete
---

# GitHub Actions workflow syntax: workflow_dispatch inputs, timeouts, status check functions and the public-repository runner

## Summary
A workflow that a person starts by hand declares `on: workflow_dispatch` with optional typed `inputs`; the run reads them from the `inputs` context, where a boolean stays a boolean, while `github.event.inputs` turns every value into a string. A job is cancelled after `timeout-minutes` (default 360, a positive integer, 360 at most for a step); a step or job that must run after an earlier failure needs a status check function in its `if`, because `success()` is the default. A job that `needs` another is skipped when that one fails or is skipped, unless its own `if` says otherwise. For a public repository the standard Linux runner (`ubuntu-latest`) has 4 CPUs, 16 GB of memory and 14 GB of storage, free and unlimited.

## Facts
### workflow_dispatch and its inputs
- A workflow runs by hand when its `on` lists `workflow_dispatch`; the "Run workflow" button shows only if the workflow file exists on the default branch, and the run takes the branch or tag it was dispatched against (`GITHUB_REF`) with the last commit on it as `GITHUB_SHA`. [DOC S-22hhnj7j, S-766tl7fe]
- `on.workflow_dispatch.inputs.<input_id>.type` is one of `boolean`, `choice`, `number`, `environment` or `string`, and `required` is a boolean saying whether the input must be supplied. [DOC S-or6ws3uz]
- The triggered workflow receives the inputs in the `inputs` context and also in `github.event.inputs`; the two are identical except that `inputs` keeps Boolean values as Booleans instead of converting them to strings, and a `choice` resolves to a string. [DOC S-n43vwkxh]
- Limits: at most 25 top-level properties for `inputs` on GitHub.com (the docs source gives 10 for the other, self-hosted product version), and a payload of at most 65,535 characters. [DOC S-n43vwkxh]
- A workflow that tests a boolean input should read `inputs.<name>`: through `github.event.inputs.<name>` a false boolean is the non-empty string `false`. [DER S-n43vwkxh: the note says that context converts Booleans to strings, and a non-empty string is not false in an expression]
- Events triggered with a workflow's `GITHUB_TOKEN` create no workflow runs, with the exception of `workflow_dispatch` and `repository_dispatch` (and `pull_request` runs that wait for approval). [DOC S-22hhnj7j]

### Timeouts
- `jobs.<job_id>.timeout-minutes` is the number of minutes GitHub lets a job run before cancelling it; the default is 360. [DOC S-or6ws3uz]
- `jobs.<job_id>.steps[*].timeout-minutes` kills the step's process after that many minutes, at most 360 on GitHub-hosted and self-hosted runners; fractional values are not supported and the value must be a positive integer. [DOC S-or6ws3uz]
- A job on a single-CPU runner (label `ubuntu-slim`) has a job timeout of 15 minutes, after which it is terminated and fails. [DOC S-zcsx2ltg]

### Status check functions and needs
- A default status check of `success()` is applied to an `if` unless it includes one of the status check functions (`success`, `always`, `cancelled`, `failure`), and `failure()` is true when any previous step of the job, or any ancestor job, failed; so a later step is skipped after an earlier failure. [DOC S-vvhj543i]
- `always()` makes a step run, and returns true, even when the run was cancelled; GitHub warns against it for a task that could fail critically, such as getting sources, because the workflow may then hang until it times out. [DOC S-vvhj543i]
- The documented alternative for "run whether the earlier steps succeeded or failed" is `if: ${{ !cancelled() }}`. [DOC S-vvhj543i]
- With `needs`, a job whose needed job failed or was skipped is skipped, as is every job after it in the chain, unless its `if` makes it continue; `if: ${{ always() }}` on that job runs it after its needed jobs whatever their result. [DOC S-v5kpgm6y]
- A check that must run after a failed test step either sits in a step with `if: ${{ !cancelled() }}` in the same job or is its own job that lists the test job in `needs` with the same `if`. [DER S-vvhj543i, S-v5kpgm6y: success() is the default, and a failed `needs` skips the dependent job]

### The standard runner for a public repository
- For public repositories, jobs on the standard runners run with the documented specification, and use of the standard GitHub-hosted runners is free and unlimited on public repositories. [DOC S-eacxcx4x]
- The table's Linux row (label `ubuntu-latest`) gives 4 CPUs, 16 GB of memory, 14 GB of SSD storage and the x64 architecture; the Windows row gives the same 4, 16 GB and 14 GB. [DOC S-eacxcx4x]

## Reference
- Related: [[github-branch-rules-and-auto-merge]], [[detecting-mr-merges-in-ci]], [[../python/pytest]] (`--durations=N`).
- Sources: workflow syntax, events that trigger workflows and expressions pages and the runner, `needs`, branch-requirement and inputs reusables of github/docs at commit 4e811c0c.

## Examples
- SNIPPET: a manual run with a boolean input and a check that still runs when the tests fail; context: GitHub Actions workflow YAML, runner `ubuntu-latest`; checked: no [DER S-or6ws3uz, S-vvhj543i: keys and the status check function from the facts above]
```yaml
on:
  workflow_dispatch:
    inputs:
      write_bytecode:
        type: boolean
        default: false
jobs:
  tests:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: nproc
      - run: python3 -m pytest --durations=10
      - run: echo "runs after a failed test step"
        if: ${{ !cancelled() }}
```
