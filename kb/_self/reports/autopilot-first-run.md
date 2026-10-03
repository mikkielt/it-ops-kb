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
| 1 again, in a real clone | a standalone clone of the integration remote (own `.git`, clean on `main`, commit hooks installed, `check.py` errors=0, `fetch.py --offline` mismatch=0, `selfcheck` 0 failed 1 unknown, a focused test created the venv), then the same `runner start SP-7kbrqaol --landed 1` | PASS by the plan's words, FAIL in effect | exit 0, cause `blocked`, `landed 0`, about 90 seconds; claim and release pushed to the integration main again; the worker's worktree was now `.claude/worktrees/agent-...` of that clone, and its Write was denied by the headless guard as "outside the project" |
| 1 third run, after the guard fix `BG-svzlkygp` | `runner start SP-7kbrqaol --landed 1` from the standalone clone, host load 8 | PASS with one defect | exit 0, cause `landed-limit`, about 3 minutes; the runner claimed `ST-6hquudym`, the worker wrote the scratch file (the guard now lets it), committed, the runner landed it through the `code/ST-6hquudym` merge request (merged, no `merge_error`) and a second `land` made the item done on the integration main; the change on main is exactly the scratch file and the item file; but `runner-status` and the tool-written `runs.jsonl` line say `landed 0` for that run: filed `BG-rgdrjsz6` |
| 3 land and worker worktrees | read from the same run's stream and the clone afterwards | FAIL | the first `land` stopped at step `branch`: `it is not locked but not under .claude/worktrees/ of the clone`, so no `land: removed the finished worker's worktree` line; the runner asked the worker to `git checkout --detach` and landed on the second pass (the plan's abort is a repeated stop: it did not repeat); the branch `work/ST-6hquudym` was deleted after landing, but the worker's `agent-*` worktree is still there: filed `BG-lv3tuhic` |
| 3 again, after `BG-lv3tuhic` | the fourth run (a landing of `ST-v6c2gq6e`) and the bug's repro on the fixed code | PARTIAL | the runner did this item in its own session (the skill allows one commit on one file), so no worker ran and `land` had no worker worktree to release: `land: removed the finished worker's worktree` was not seen in a live run; the bug's repro (a runner worktree and a sibling `agent-*` worktree) now prints that line and passes; the branch of the landed item was deleted and the run's landed count is right (`landed 1: ST-v6c2gq6e`, `runs.jsonl` `landed 1`), so `BG-rgdrjsz6` holds. The stray `agent-ab9c...` worktree of the first landing is still there, untouched by hand: `land` removes the worktree that holds the branch it needs, and that branch is long deleted; the sprint close's cleanup step (`/kb-sprint close`, clean up) is what removes such leftovers |
| 2 headless guards | in the runner's worktree with `KB_HEADLESS_RUNNER=1`, `KB_RUNNER_SPRINT=SP-7kbrqaol`, `KB_NO_PUBLISH_HOOK=1` exported; harmless targets for what would act if not refused (a remote that does not exist, an item of another sprint, the throwaway gate) | PASS, one row not exercised | the guard function on nine write cases: refused `.claude/settings.json` (also inside a worker worktree), `_tools/kb_hook.py`, a gate's `answer`+`by` written into an item, a path outside the project, another clone's worktrees, a `..` escape; allowed a kb doc in the project and in a worker worktree of the same clone. Commands: `answer --by operator` and `--by autopilot` exit 2 with the plan's text; `runner start` and `runner reset` exit 2; `sync --push --remote R` and `--branch B` exit 2, nothing pushed (`git ls-remote` shows no such ref); `merge` of an item of another sprint exit 1 `a headless run merges only its own sprint's items` (the plan's known gap). Not exercised live: the `git checkout REV -- path` deny rule (read from the settings, it needs a live headless agent); the guard was called as a function, the hook wiring in `.claude/settings.json` is the part of this row only a live run shows (the third run's stream shows it firing on a worker's write) |
| 4 no-progress stop | after `BG-rgdrjsz6` was on main: the history after a landing run (`landed 1`), then two real runs that can land nothing (the only open item waits on a gate), `bounds stop`, `bounds reset-runs`, `bounds stop` | PASS | a run that landed does not count: with the history ending in a landing `bounds stop` names only `no-ready`; after one zero run still only `no-ready`; after the second `stop no-progress: 2 consecutive runs landed nothing (causes: blocked)` (also `no-ready`), exit 1; `reset-runs` cleared 5 runs, then only `no-ready`; a history simulated with `--runs-landed 0,0` gives the same, one with a landing last does not; the runs took 18 and 31 seconds and pushed nothing. Not exercised: the tick's refusal to start a third run (the tick is not run here) |
| 5 bounds | `backlog.py bounds --sprint SP-7kbrqaol`, `bounds file ...` five times with `--origin retro` and `--evidence`, then a sixth | PASS | the report prints the limits and `findings ... 0 of 5`; five findings filed (`ST-p2a2rzkf`, `ST-dx57occz`, `ST-6vkh6qka`, `ST-w2hd2rbh`, `ST-rmgs774t`), the report then `5 of 5`; the sixth exit 1 `has 5 findings filed already (at most 5): keep this one in the close commit body only`, nothing filed. Two side facts: a finding without `--evidence` is kept for the close commit body whatever the count, and the filed findings need a check before `backlog check` has errors=0 |
| 6 stall remedies | `stalled` after the claim was 3600 s old (probe `ST-degka7at`), `stalled --took` twice with the same remedy, then the next | PASS | `claim-no-commit`, `next: retry-narrower`; `--took ... retry-narrower` exit 0 (decision `D-3owdbysk`, ops row); the same again exit 1 `was taken ... already; the ladder goes on with release-redispatch`; `--took ... release-redispatch` exit 0 (decision `D-jci6lkrb`) and `release`; `stalled` then 0 signals; the probe was dropped. The two decisions are autopilot decisions the digest lists for the operator to ratify or revert |
| 7 digest and notifications | `kbdecide.py digest` (without `--commit`) | PARTIAL, a documented gap | exit 0, `digest 0 unratified` (before stage 6's two decisions); the notification half is the scheduled manager tick's (`/kb-autopilot`) and a tick cannot be scoped to one sprint (the skill takes only `[tick]`; it refills runners over every started sprint, plans new ones and runs reviews and closes), so it would start real runs that push real work, which the operator reserves: not exercised, no notification was sent by anything else |
| 8 operator gates | three planted gates on the stall probe, classes `secrets`, `push`, `agents-rule` (checked in the item's `class` field), `answer ST G --answer no --by autopilot --record` | PASS | manager session: exit 2 `is class C: only the operator answers it`, three times; with the runner's variables and `--by agent`: exit 1 `is class C: only the operator answers it (--by operator)`, three times; `git status` clean after each; `horizon` lists the three as waiting on the operator; with `--by agent --record` the refusal is the flag rule, not the class (exit 2, `--record keeps ... --by operator\|autopilot`) |
| 9 run inside the container | not run | SKIPPED | the manager's scope: the host stages only; the container page's checks are a later operator-present item |

### Stage 1 finding

The worker the runner started got its isolation worktree under the operator's main checkout (`.claude/worktrees/agent-...` of the checkout whose `.git` the manager clone shares), not under the runner's own project. Its first write was denied by the headless guard (`...is outside the project`), which is the guard working. The runner stopped on the refusal, as its rule says, released the item and ended `blocked`: no item can ever land from a clone like this one. The manager clone used here, `it-ops-kb-fourth`, is a linked worktree of the operator's checkout (`git rev-parse --git-common-dir` is the operator's `.git`), not a clone of its own, which the runbook's "a clone no other session works in" does not allow. Filed: `BG-7tqa65mp` (selfcheck and runner start refuse such a clone). Nothing was left behind in the operator's checkout (the worker's worktree was removed).

### Stage 1 finding, revised after the repeat in a real clone

The linked-worktree diagnosis above was a cause but not the cause. In a standalone clone the worker is still refused: the guard's project is the runner's own worktree (`CLAUDE_PROJECT_DIR` = `.claude/worktrees/runner-SP-xxxxxxxx`), and the Agent tool puts a worker's isolation worktree at `.claude/worktrees/agent-...` of the clone's root, a sibling of the runner's worktree and so outside the project. Every worker of every headless runner is refused its first write, in any clone, so no item can land. Filed `BG-svzlkygp` (S1, SP-rq4t477t) with a repro that runs the guard on exactly that pair of paths and fails now. `BG-7tqa65mp` stays filed with its notes corrected; the manager decides whether to keep it.

### Residual of the guard fix (from its author)

After `BG-svzlkygp` a directory `agent-*` directly under the clone's `.claude/worktrees` counts as the project for the runner's guard. Any such directory is trusted, and the `agent-*` worktrees are not isolated from each other: one worker can write into another's. Other names, other clones, `..` and symlinks stay denied, and the guarded paths stay denied inside them.

### Bugs filed by the run

- `BG-7tqa65mp` (S2, kept, waits): selfcheck and runner start refuse a manager clone that is a linked worktree of another checkout.
- `BG-svzlkygp` (S1, fixed by another session and on main): the guard refused every worker's write in its sibling worktree.
- `BG-rgdrjsz6` (S3): a run that landed through the code lane records and prints `landed 0`; the count reads the runner worktree's `HEAD`, the done commit is on `origin/main`.
- `BG-lv3tuhic` (S2): `land` takes the runner's own worktree as the clone, so it never removes a worker's sibling worktree.

### Retrospective findings

Filed through `bounds file` (five of five); a sixth is kept for the close commit body only.

1. `ST-p2a2rzkf`: the commit-msg hook asks for `KB-Work` in the last paragraph but refuses it for an item that is not claimed, and its text does not say a release or a planning commit may name only the items it changes: the runner's release commit took three amends (the trailer after a blank line, an unclaimed `KB-Work`, then none), and a planning commit that gated a throwaway item needed one more; that last commit was warned as refused by the hook, and the push gate then accepted it.
2. `ST-dx57occz`: a blocked run leaves the worker's `work/<id>` and `worktree-agent-*` branches in the clone; the next worker's `git checkout -b work/<id>` fails and its `-B` retry silently resets the old branch.
3. `ST-6vkh6qka`: `land` refuses a branch checked out in a worker's worktree and the runner cannot remove that worktree itself (agents' shells may not run `git worktree remove`), so a message round trip asks the worker to detach; the brief and the runbook should say one thing about who frees it.
4. `ST-w2hd2rbh`: Stage 2 as written would push a branch to, or merge a request of, the real integration remote if a guard failed (`sync --push --branch scratch`, `merge BG-xxxxxxxx`); it should name harmless targets and say to export the variables.
5. `ST-rmgs774t`: the plan does not say how the `git checkout REV -- path` deny rule row is exercised from an operator-present session.

## Open follow-ups noted, not filed twice

- The report's `gates` and `bugs` lines still read the runner worktree (the run's report listed the dropped probe's three gates as open and a bug another session filed during the run): the manager's session `mac-sixth` is fixing it.
- `BG-7tqa65mp` (S2): a manager clone that is a linked worktree of another checkout; kept, waits.
- The residual of the guard fix: any `agent-*` directory under the clone's worktrees is trusted and the workers are not isolated from each other.

## Left behind by the run

- `kb/_self/reports/autopilot-throwaway.md` on the integration main (heading and two sentences): not deleted, deleting is the operator's call.
- The stray worker worktree `.claude/worktrees/agent-ab9c...` (clean, detached) and two empty `worktree-agent-*` branches in the clone `it-ops-kb-autopilot`.
- The throwaway sprint `SP-7kbrqaol`, still active, with its gated story `ST-mf3qe7en` (to be dropped) and its review story: not closed.
- The two autopilot decisions `D-3owdbysk` and `D-jci6lkrb` (Stage 6) for the operator's digest.
- The clone `it-ops-kb-autopilot` (standalone, query log set to `off` in its `_private/querylog.json`); no runner process is alive.

## Go / no-go for an unattended run

**GO for the run that was done**: one runner, one sprint, on the host, watched by a session, in a standalone clone, the push path through the deploy key. In that form the first landing, the second landing, the guards, the bounds, the stall ladder, the no-progress stop with its reset and the refusal of the operator-only gate classes all behaved as the plan says once three defects were fixed (`BG-svzlkygp`, `BG-rgdrjsz6`, `BG-lv3tuhic`).

**NO-GO for an unattended, tick-driven run** until the operator has set or decided what only the operator can:

1. The file-event daemon's memory (about 9.7 GB at the start), restarted with administrator rights: pre-run row 3.
2. Where the runner runs: the container (Stage 9, pre-run row 2) was not tested; on the host the runner's `claude` runs under the operator's account with the cloud connectors (mail, drive, calendar) connected, defended only by text rules (no tool allowed, no prompt in a headless run). Either disconnect those connectors for the runner's account or run the container.
3. Which sprints are open when the first real tick runs, and that the first tick is supervised: it refills to two runners over every started sprint and was not exercised (including its notifications, its refusal to start a third run and its refill).
4. The deploy key's reach: the integration main accepts the runner's key directly (`push` on main for the runner), so the branch protection is the only line between a headless run and main; the operator decides whether that is enough.
5. The query log mode for the unattended clone (set `off` for now), the ratification of the two Stage 6 decisions, and the throwaway scratch file and sprint.

And, before relying on it for long runs, the follow-ups above (the report's gates and bugs, `BG-7tqa65mp`, the isolation of the `agent-*` worktrees) and the retrospective items filed through `bounds file` (`ST-p2a2rzkf`, `ST-dx57occz`, `ST-6vkh6qka`, `ST-w2hd2rbh`, `ST-rmgs774t`).
