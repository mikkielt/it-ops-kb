# Autopilot: checklist and test plan for the first supervised run

The autopilot is a manager session that runs the `/kb-autopilot` tick under `/loop` (`.claude/skills/kb-autopilot/SKILL.md`) and starts headless sprint runners, each a `claude -p` that `python3 _tools/autopilot.py runner start SP` launches in a worktree of its own (`kb/_self/tools.md`, The autopilot runner). This page is for the operator and for the agent who supervises its first run on their behalf, neither of whom needs to have built it. It names, for each step, the command, what a pass looks like and when to stop. Every claim cites the code (a file and the function or constant) or the runbook (`kb/_self/backlog.md`, Starting the autopilot); the runbook's start order stays the source of truth, and this page adds the checks around it.

The text rules (permission allow and deny lists, the edit guard, refusals inside the tools) are defence in depth: an agent that can edit code and then run it can step around them. The real boundary is the runner's credentials and the place it runs in, which the operator sets up (the checklist below, and the container of the last stage). Supervise the first run end to end.

Placeholders only: `SP-xxxxxxxx` is a sprint, `ST-xxxxxxxx` and `BG-xxxxxxxx` items, `G` a gate id, `PL-LT-00123` a host, `corp.example.com` a domain.

## Pre-run checklist

Operator-only steps first, then checks anyone can run. Each says what it protects. Do not start until every line holds.

| # | step | what it protects | how to check |
|---|---|---|---|
| 1 | The runner's own deploy key: the private key `~/.config/it-ops-kb/runner_deploy_key` (mode 0600, outside every clone; `KB_RUNNER_DEPLOY_KEY` names another), added to the integration project as the deploy key `kb-runner` with write access; the integration `main` protected with push for Maintainers and that key, force push off; `code/*` protected with push for Maintainers and that key, force push on (land replaces a `code/<id>` branch); the key is never added to the public repository | everything the text rules cannot stop: the runner's child pushes over ssh with this key only (`_tools/autopilot.py`, `runner_ssh_command`: no agent, no user ssh config, no key at all when the file is missing), so code it edits and then runs cannot use the operator's identity | the project's Settings, Repository, Deploy keys and Protected branches; `python3 _tools/tests.py -n 1 -k runner_deploy_key` passes |
| 2 | The runner runs in its own container (the page autopilot-container.md of kb/_self, once that page exists), not as the operator | the operator's other credentials and files | the container doc's own checks, once it exists |
| 3 | The host's file-event daemon (fseventsd on macOS) restarted after heavy churn, by the operator | the host's memory: it grows with every worktree and test run | the daemon's resident memory in Activity Monitor is small again |
| 4 | Gates a runner or the autopilot answered in a class only the operator answers are re-confirmed | that no agent answer stands in the operator's place | `python3 _tools/backlog.py check` prints no `answered by ... in a refused class: the operator re-confirms` warning (`_tools/bl_check.py`, the refused-class check) |
| 5 | The manager session is started with `KB_NO_PUBLISH_HOOK=1`, never with `KB_HEADLESS_RUNNER` | no publish from a session hook; the manager keeps recording the operator's answers (`backlog.md`, Starting the autopilot) | `echo "$KB_NO_PUBLISH_HOOK"` prints `1`, `echo "$KB_HEADLESS_RUNNER"` prints nothing |
| 6 | Runner credentials are stripped and the public push URL fails | a runner never inherits the operator's ssh agent or tokens (`_tools/autopilot.py`, `child_env`, `CREDENTIAL_NAMES`, `CREDENTIAL_RE`; the per-worktree public push URL `file:///dev/null/no-push-from-a-runner`) | `python3 _tools/tests.py -n 1 -k runner_child_holds_no_credentials` passes |
| 7 | Settings and hooks are as the tests say | the allow and deny lists and the edit guard (`.claude/settings.json`; `_tools/kb_hook.py`, `headless_guard`) | `python3 _tools/tests.py -n 1 -k "settings_allow or headless_pretooluse_guard or headless_guard_case_dup_worktree or autopilot_status_compaction_hooks"` passes |
| 8 | The self-check passes | allow rules cover the skills, hooks installed, host load, stale claims, orphans, main green (`_tools/bl_selfcheck.py`) | `python3 _tools/backlog.py selfcheck` prints `selfcheck: ok (6 checks passed)`, or one `UNKNOWN main` with exit 0; a `FAIL name: detail -> remedy` line means stop and act on the remedy |
| 9 | The rehearsal passes | one whole tick on a scratch sprint with a stub `claude` (`_tools/autopilot_rehearse.py`) | `python3 _tools/autopilot_rehearse.py` ends `rehearse: ok (N steps)`, exit 0 |
| 10 | The runbook's start checks hold | a clean `main`, a remote and `glab` that work unattended, MCP servers connected | the commands of `backlog.md`, Starting the autopilot |

The rehearsal does not test permissions, hooks, `land`, the sync gate, compaction or the real backlog (`backlog.md`, Starting the autopilot): the stages below do.

Not closed by row 1, and left to the container of row 2:

- On a GitLab plan without push rules a write deploy key can push any branch that is not protected (a scratch name), so only `main` and `code/*` are bounded by the server.
- The runner can still read files of the operator's account, the `glab` sign-in among them, which `backlog.py merge` and `land` use for the forge's API.
- The public repository's `main` carries no branch protection, since the operator's own `kbgit.py publish --rewrite` force-pushes it; the runner never holds a key for it.

Undoing row 1, in the integration project's Settings, Repository: remove the deploy key `kb-runner` (which also takes it out of both protected branches), unprotect `code/*`, and delete the key files under `~/.config/it-ops-kb/`.

## Test plan

Run the stages in order on a throwaway sprint (`SP-xxxxxxxx`, one or two small content items, filed and started the usual way). Each stage gives the command, the expected result and the abort condition. On an abort, stop the autopilot (the last section), record the failure and do not go on.

**Stage 0. Dry look at a tick.** There is no dry-run of the tick itself (`SKILL.md` takes only `[tick]`). These read-only commands show what it would decide:

```
python3 _tools/autopilot.py status
python3 _tools/backlog.py next --sprint SP-xxxxxxxx --all
python3 _tools/backlog.py bounds stop --sprint SP-xxxxxxxx
```

Expected: `status` prints its sections, or `autopilot idle: ...`; `bounds stop` exits 0 with `bounds: go: N item(s) ready of SP-xxxxxxxx` (`_tools/bl_bounds.py`, `cmd_bounds`). Abort if `status` exits 1 or `bounds stop` names a cause.

**Stage 1. One runner, watched.** In the manager session, start one run by hand:

```
python3 _tools/autopilot.py runner start SP-xxxxxxxx --landed 1
python3 _tools/autopilot.py runner-status SP-xxxxxxxx
```

Expected: the worktree `.claude/worktrees/runner-SP-xxxxxxxx` on `orch/SP-xxxxxxxx`, the stream in `_cache/autopilot/SP-xxxxxxxx/<stamp>.jsonl`, `status.json` beside it; exit 0 with a cause `landed-limit`, `sprint-done` or `blocked` (`_tools/autopilot.py`, module docstring, exit codes). `runner-status` prints under 1000 characters, its first line `SP-xxxxxxxx exit cause CAUSE`; a run that landed an item through its `code/<id>` merge request shows `landed 1` there and in the `runs.jsonl` line, since the count reads the integration remote's main, not the worktree's `HEAD` (`autopilot.integration_tip`; `tests.py -k run_landed_counts_origin_main`). Abort on exit 1 (`error`, `timeout`) or exit 2 (refused), and read `status.json` and the stream's `.stderr`.

**Stage 2. Headless guards.** In the runner's worktree, with `KB_HEADLESS_RUNNER=1` and `KB_RUNNER_SPRINT=SP-xxxxxxxx` set as the runner sets them, each command must be refused:

| attempt | expected refusal | source |
|---|---|---|
| an Edit of `.claude/settings.json`, `_tools/kb_hook.py`, a gate's `answer` or `by` in an item, or a path outside the project | PreToolUse deny `headless run (KB_HEADLESS_RUNNER): ... holds the rules this run works under` | `_tools/kb_hook.py`, `headless_guard` |
| `python3 _tools/backlog.py answer ST-xxxxxxxx G --answer A --by operator` | exit 2, `answering with --by operator is the operator's and KB_HEADLESS_RUNNER is set` | `_tools/backlog.py`, `cmd_answer`; `_tools/bl_authority.py` |
| `... --by autopilot` | exit 2, `a headless runner answers --by agent only` | `_tools/backlog.py`, `cmd_answer` |
| `python3 _tools/autopilot.py runner start SP-xxxxxxxx` (or `runner reset`) | exit 2, `runs only in the manager session, not inside a headless run` | `_tools/autopilot.py`, `headless_refusal` |
| `python3 _tools/kbgit.py sync --push --branch scratch` (or `--remote R`) | exit 2, `syncs only to the integration remote's main ... nothing was pushed` | `_tools/kg_sync.py`, `headless_target_refusal` |
| `git checkout REV -- .claude/settings.json` | a permission deny with no message (rule `git checkout * -- *`) | `.claude/settings.json`, deny |
| `python3 _tools/backlog.py merge BG-xxxxxxxx` of an item in another sprint | refused, `a headless run merges only its own sprint's items` (exit 1: see Known gaps) | `_tools/bl_land.py`, `merge_target` |

Abort if any of them is not refused. The rules are defence in depth (the introduction); a refusal that holds here is still no proof of the boundary.

**Stage 3. Land and worker worktrees.** When the runner lands an item, the run's log, or a `land` by hand, prints `land: removed the finished worker's worktree ...` for a clean `agent-*` worktree, then `land: ... landed` and `land: deleted the landed branch work/ST-xxxxxxxx` (`_tools/bl_land.py`, `release_worker_worktree`, `delete_landed_branch`). Expected: no `.claude/worktrees/agent-*` worktree and no `work/` branch of a landed item is left. Abort if `land stopped at step ...` repeats on a second pass.

**Stage 4. No-progress stop.** Let two runs of a sprint end without landing anything (a sprint whose only item waits on a gate does). Expected: the tick does not start a third, because `bounds stop`, reading the sprint's run history, `_cache/autopilot/<SP>/runs.jsonl`, which the runner writes at each run's end (the skill never passes `--runs-landed`, which replaces it; `_tools/bl_bounds.py`, its `stop` usage), exits 1 with `bounds: stop no-progress: 2 consecutive runs landed nothing` (`NO_PROGRESS_RUNS`); the tick names it in the digest and in one PushNotification. Abort if a third run starts. The run history lives in `_cache/autopilot/<SP>/runs.jsonl`; `python3 _tools/backlog.py bounds reset-runs --sprint SP` clears it after the cause is fixed (`SKILL.md`, the runner step).

**Stage 5. Bounds.** `python3 _tools/backlog.py bounds --sprint SP-xxxxxxxx` prints the limits (findings per sprint, rework cap, open drafts, inflow) and how far each is used (`_tools/bl_bounds.py`, `FINDINGS_PER_SPRINT`, `REWORK_CAP`, `OPEN_DRAFTS_MAX`). File findings past the limit with `bounds file` and expect `bounds file: SP-xxxxxxxx has n findings filed already (at most ...)`, exit 1. Abort if a sixth finding is filed.

**Stage 6. Stall remedies.** `python3 _tools/backlog.py stalled` lists each stalled item with its signal and next remedy; `stalled --ladder` the order (`_tools/bl_stall.py`). Leave a claimed item without a commit past its threshold and expect it listed. Abort if the tick takes the same remedy twice for one signal (it is refused: `stalled --took`).

**Stage 7. Digest and notifications.** The tick runs `python3 _tools/kbdecide.py digest --commit` (prints `digest\tN unratified\t<path>`) and sends a PushNotification only for a gate the operator keeps that the last tick did not name, and for a sprint stopped by no-progress (`SKILL.md`, the notify step). Expected: no notification for an error, a finished sprint or a refused command. Abort on any other notification.

**Stage 8. Operator gates.** For a gate of class `secrets`, `push` or `agents-rule` (`_tools/bl_authority.py`, `AUTOPILOT_REFUSED`):

```
python3 _tools/backlog.py answer ST-xxxxxxxx G --answer A --by autopilot --record
```

exits 2, `gate G of ... is class C: only the operator answers it`, the item unchanged. Expected: the tick lists the gate as kept and never answers it. Abort if any such gate carries an autopilot answer.

**Stage 9. Run inside the container.** Repeat stages 1 to 3 with the runner inside the container of the page autopilot-container.md of kb/_self, once that page exists, following its own start and checks. Without it this stage is skipped and the run stays supervised on the host.

## What the supervising agent records

- **A log per stage:** the stage, the command run, pass or fail, and on a fail the shortest decisive output line and the paths of `status.json` and the stream. One line per stage when it passes.
- **Each failure as a bug:** `python3 _tools/backlog.py new bug --title T --severity S --repro "CMD" --goal G` with a repro that fails now for the defect (`backlog.md`, Working on items), filed through `bounds file` when a sprint's finding limit applies.
- **Each process finding as a retrospective item:** through the sprint's review and close, as `/kb-sprint` close describes, never edited into the docs directly.
- **Within the autopilot's own limits:** no answer to a kept gate, no edit of the settings or hooks, no push beyond `sync --push`; what needs the operator goes on the operator's list.

## Stop and cleanup

In this order (`backlog.md`, Starting the autopilot):

1. Cancel the scheduled `/kb-autopilot` and leave the manager session.
2. `python3 _tools/autopilot.py status` lists each live runner as `SP-xxxxxxxx pid N alive`; `kill N` ends it as `ended error` with `runner ended by SIGTERM` (`_tools/autopilot.py`, `RunnerEnded`).
3. `python3 _tools/autopilot.py runner reset SP-xxxxxxxx` frees a refused worktree: uncommitted files go to a stash named `autopilot reset SP-xxxxxxxx STAMP`, a diverged branch is kept as `stale/SP-xxxxxxxx-STAMP` (`_tools/autopilot.py`, `reset_worktree`).
4. `python3 _tools/backlog.py procs` lists processes by class; `procs --end` ends only owned orphans after the grace, `ended pid N (...): owned orphan ...` (`_tools/bl_procs.py`). Foreign processes and unrecorded orphans are listed, `not started by the autopilot; for the operator, never signaled`, and ended by the operator by hand.

## Known gaps

Where the code and the docs disagree; the code is what runs:

- `backlog.py merge` exits 1 when it refuses (its `Refused` goes through `backlog.py`'s main), while `kb/_self/tools.md` says exit 2.
- The skill's notify and gate steps name the kept classes `secrets` and `push`; the code also keeps `agents-rule` (`AUTOPILOT_REFUSED`).
