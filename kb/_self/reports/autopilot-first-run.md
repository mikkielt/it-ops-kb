# Autopilot: the first supervised run

The log of `kb/_self/autopilot-test.md` run by an operator-agent (an interactive session that did not write the plan), stage by stage, on the host, with the runner supervised. Placeholders only: `SP-xxxxxxxx` a sprint, `ST-xxxxxxxx` and `BG-xxxxxxxx` items.

Scope given by the manager: the host stages only; the container stages are skipped (a later operator-present item). The agent answers only the throwaway sprint's own gates, never a `secrets`, `push` or `agents-rule` gate of real work, and never runs `kbgit.py publish`. It stops at any surprise and reports.

## Pre-run checklist

| # | step | result | evidence |
|---|---|---|---|
| 1 | the runner's deploy key | PARTIAL | both key files exist under the config directory, the private one mode 0600; the project's deploy-key registration and branch protection are server-side settings the agent has not read |
| 2 | the runner runs in its own container | SKIPPED by the manager's scope | the container page's own checks are the later operator-present item |
| 3 | the file-event daemon restarted | FAIL (operator-only) | the daemon's resident memory is about 9.7 GB; only the operator can restart it |
| 4 | no refused-class answer awaiting re-confirmation | PASS | `backlog.py check` prints no re-confirm warning, errors=0 |
| 5 | the manager session has `KB_NO_PUBLISH_HOOK=1`, no `KB_HEADLESS_RUNNER` | DEVIATION | the supervising session was not started with the variable (its environment cannot be changed from inside); every command of the run sets it explicitly; `KB_HEADLESS_RUNNER` is unset |
| 6 | runner credentials stripped, public push URL fails | PASS | `runner_child_holds_no_credentials` and `runner_deploy_key` tests pass |
| 7 | settings and hooks as the tests say | PASS | `settings_allow`, `headless_pretooluse_guard`, `headless_guard_case_dup_worktree`, `autopilot_status_compaction_hooks`: 155 passed |
| 8 | the self-check | PASS | `selfcheck: 0 failed, 1 unknown of 6 checks`; the one unknown is `main` (no pipeline row read) |
| 9 | the rehearsal | PASS | `rehearse: ok (11 steps)` |
| 10 | the runbook's start checks | DEVIATION | the integration remote answers and `glab` is signed in; the clone is on a sprint branch, not `main`; the cloud connectors (mail, drive, calendar) are connected to the account the runner's `claude` would use |

## Setup of the throwaway sprint

`SP-7kbrqaol`, two doc-only stories (`ST-6hquudym`, `ST-v6c2gq6e`) that touch only the scratch file kb/_self/reports/autopilot-throwaway.md (a file the throwaway items create; not in the repository yet), its research story dropped (no research question), its start gate answered by the operator-agent for this sprint only, started and pushed. Environment of every run: `KB_TEST_WORKERS=3`, `KB_NO_PUBLISH_HOOK=1`, one runner. The manager clone was put on `main` as the manager asked.

## Stages

| stage | command | result | evidence |
|---|---|---|---|
| 0 dry look at a tick | `autopilot.py status`, `backlog.py next --sprint SP --all`, `backlog.py bounds stop --sprint SP` | PASS | `status` exit 0 with its sections; `next` names `ST-6hquudym`; `bounds: go: 1 item(s) ready of SP-7kbrqaol`, exit 0 |
| 1 one runner, watched | `autopilot.py runner start SP-7kbrqaol --landed 1`, `runner-status` | PASS by the plan's words, FAIL in effect | exit 0, cause `blocked`, `landed 0`; the worktree `.claude/worktrees/runner-SP-7kbrqaol`, the stream, `status.json` and the tool-written `runs.jsonl` line are there; `runner-status` is under 1000 characters; the runner claimed the item, pushed its claim to the integration main, started a worker, was refused, released the item and pushed the release (the push path works) |

### Stage 1 finding

The worker the runner started got its isolation worktree under the operator's main checkout (`.claude/worktrees/agent-...` of the checkout whose `.git` the manager clone shares), not under the runner's own project. Its first write was denied by the headless guard (`...is outside the project`), which is the guard working. The runner stopped on the refusal, as its rule says, released the item and ended `blocked`: no item can ever land from a clone like this one. The manager clone used here, `it-ops-kb-fourth`, is a linked worktree of the operator's checkout (`git rev-parse --git-common-dir` is the operator's `.git`), not a clone of its own, which the runbook's "a clone no other session works in" does not allow. Filed: `BG-7tqa65mp` (selfcheck and runner start refuse such a clone). Nothing was left behind in the operator's checkout (the worker's worktree was removed).

Process note, for the retrospective: the runner's release commit took three amends because the commit-msg hook asks for `KB-Work` in the trailer paragraph but refuses it for an item that is no longer claimed.
