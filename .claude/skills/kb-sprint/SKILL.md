---
name: kb-sprint
description: Use when the user asks to plan, start, run, review or close a sprint of it-ops-kb's own backlog, or to orchestrate the backlog's work end to end: runs the sprint from kb/_self/backlog/ with backlog.py, dispatching ready items to subagents in worktrees and landing them one at a time.
argument-hint: "plan \"<goal>\" | start SP-... | run [SP-...] | review SP-... | close SP-..."
---

# Run a sprint

Read these sections of the `kb/_self/` docs first, not the whole docs, in one command (`selfdoc.py section` prints the section under each heading with its line numbers):

```
python3 _tools/selfdoc.py section backlog "Sprints" backlog "Dependencies, gates and triggers" backlog "Definition of done" backlog "Working on items" backlog "Git" maintaining "Conduct for changes" git.md "Workflow"
```

What each gives: `backlog "Git"` the `KB-Work` trailer; `maintaining "Conduct for changes"` the gate, commit messages; `git "Workflow"` sync and the gate.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a subagent brief, a commit), give its id and its title together, never a bare id.

## plan "<goal>"
1. Run `python3 _tools/backlog.py new sprint --title T --goal G`. It creates the sprint, its blocking `start` gate, its review story and its goal research story (a research item: claim and work it first, with the kb tools and the live docs for gaps, writing kb facts and gap entries through the kb skills, then `done`).
2. Check what covers the goal with `python3 _tools/backlog.py find WORDS`, then pick the stories and bugs with `python3 _tools/backlog.py tree --open` and `python3 _tools/backlog.py list --kind bug`: every `S1` and `P1`, then by priority and rank, as far as the goal needs. Put each in the sprint with `python3 _tools/backlog.py set ID --sprint SP` (every item edit goes through `set`, never a hand edit of its JSON; the planning commit names in `KB-Work` only the items whose files it changes). Break stories into tasks as `/kb-backlog` does, with `touches` and `checks` (`new task --parent ID --touch G --check CMD`, later `set ID --touch G --add`); a task that changes code carries the `kb/_self/` docs `kb/_self/map.csv` maps to it in its own `touches`, not a later docs task. A change to how agents read docs or call a tool puts every consumer of that route (skills, `.claude/agents/` definitions, `AGENTS.md`, headless runs such as `_tools/ql_research.py`) in some item's `touches`.
   Paths other sessions hold: after `git fetch`, `python3 _tools/backlog.py held --ref origin/main` (each claimed item's touches, claimer and sprint), never messages to those sessions.
3. Map the goal's clauses to items. Split the goal into its clauses and name, for each, the committed item that carries it (its `goal` or `touches`). A clause no item carries is either already met in the tree, so drop it from the goal and name the earlier item that delivered it (`git log --grep 'KB-Work: ID'`), or work still to plan: add an item for it. Never leave a clause with no item: `close --summary` could not name one for it.
4. Check each committed item's goal for its step order against the lane rules. Read the order the goal gives for done, `sync --push` and a push to `main`: for an item with a code-lane commit (`_tools/kblane.py`), `done` and a push to `main` come after its `code/<id>` merge request merges, and `sync --push` before then only opens that merge request. A goal that puts `done` or a push to `main` before the merge is rewritten to the lane's order (`python3 _tools/backlog.py set ID --goal G`), or, when the right order is a choice, gets a gate (`gate add`) naming the options and a recommendation; do it before `start`, since only the worker's brief would catch it (SP-bwlxievv, where a goal put `done` before `sync --push` for code items).
5. `fmt` and `check` (no warning about a committed item's docs: add the docs it names to that item's `touches`), then `python3 _tools/backlog.py horizon --sprint SP` (it shows the start gate as the one thing everything waits on).
6. Before asking, run `python3 _tools/backlog.py host-check SP`: it runs the `--host-check` command of each answered gate that names a host setup, on this host, and records the result; on exit 1 show the operator the failing gate and its output (the setup is not in place: enable it, or change the gate) and do not ask yet. Ask the operator to approve the goal and the committed items (AskUserQuestion: approve / change / cancel). Show each goal clause with the id and title of its item, any clause dropped as met with the earlier item that delivered it, and the gates the items will meet.

## start SP
Only on the operator's approval in this conversation:
1. `python3 _tools/backlog.py answer SP start --answer approve --by operator`.
2. `python3 _tools/backlog.py start SP`. It prints `warning:` lines for a sprint item whose mapped docs sit outside its `touches` (an item planned before `check` warned of it): before any claim, ask the operator to move each named doc into that item's `touches` (`set ID --touch G --add`), and rerun `backlog.py check`. It refuses while an answered gate with a host check has no passing `host-check` record: run `backlog.py host-check SP` first.

A start gate answered `--by autopilot` runs `start` only once that research story is done and every committed story and bug has `knowledge` asks or refs that read sufficient or partial: `start` refuses, naming each cause, otherwise.

Never answer the start gate yourself.

## run [SP]
You are the orchestrator. Run from your own clone or git worktree, never a checkout another session works in: a second orchestrator starts its own (`kb/_self/backlog.md`, Working on items). Loop:
1. Run `python3 _tools/backlog.py selfcheck` first (Self-check) and act on each failure before anything is claimed, then `python3 _tools/backlog.py horizon --sprint SP` and `python3 _tools/backlog.py next --sprint SP --all`.
2. From the ready list, take up to four items whose `touches` do not overlap each other or any item in flight: after `git fetch`, `python3 _tools/backlog.py held --overlaps ID --ref origin/main` lists the claimed items, of every session, whose touches an item would meet (exit 1 when there is one). Claim each: `python3 _tools/backlog.py claim ID --by <subagent name> --commit --trailer 'Co-Authored-By: ...'`, then push the claims once, the claim sync: `python3 _tools/kbgit.py sync --push`.
   - Shared-file move: a task that moves code out of a file other items edit (a split of `backlog.py` or `kbgit.py`) is announced first to the manager session; in-flight items on that file drain: no new claims on it, and `python3 _tools/backlog.py held --overlaps ID --ref origin/main` shows none of the mover's claimed touches overlapping before the move starts; the move is one atomic commit per file moved: new modules git-added, mapped in `kb/_self/map.csv`, the testmap and the tools map, docs in the same commit, tests keeping their names, patch targets repointed, and a `bl_` or `kg_` module never importing `backlog` or `kbgit` at any depth.
3. Start one subagent per item with `isolation: "worktree"`, on the agent its kind takes:
   - a task or subtask: `subagent_type: "kb-worker"` (`.claude/agents/kb-worker.md`, the newest Sonnet at high effort);
   - an `S1` or `S2` bug and its tasks and subtasks, and a story or bug with no tasks yet (its breakdown): a subagent on the session model (`subagent_type: "general-purpose"`).
   Never pass the Agent tool's `model`: it replaces the agent's own model.
   Workers start from your `HEAD`, not from `origin/main`: `.claude/settings.json` sets `worktree.baseRef` to `"head"`, which branches each isolation worktree from the `HEAD` of the checkout or worktree you run in. Your `HEAD` must include the pushed claim commits, so dispatch only after the claim sync of step 2. That is the session's own working directory: a session started in another checkout (a shared clone on an old `main`) while it orchestrates from its own clone branches its workers from that other checkout's `HEAD`, and only the worker's fetch-and-rebase brings them to `origin/main`; start the orchestrator's session in its own clone or worktree. The brief names no base to check out by hand: the worker checks its base against `origin/main` and rebases only if behind (`.claude/agents/kb-worker.md`, rule 2).
   A sprint in a second clone (another sprint holds the session's own clone): the Agent tool gives a subagent no working directory of its own (it starts in the session's), so `isolation: "worktree"` would branch from the wrong clone. Start a fresh Claude session in that clone and orchestrate from there. A session that cannot start there makes each worker's worktree by hand, after the claim sync: `git -C <clone> fetch origin`, then `git -C <clone> worktree add <clone>/.claude/worktrees/<id> -b work/<id> origin/main`; it starts the subagent without `isolation` and names that path in the brief, where the worker runs every command by absolute path into it (`python3 <path>/_tools/...`, `git -C <path> ...`), since its working directory stays the session's. Close step 5 cleans these worktrees up with its commands run against that clone (`git -C <clone>`).
   The one exception, a fallback: when the Agent tool does not list `kb-worker` (agent files load at session start, so a session that added or changed it cannot use it), start the task on `subagent_type: "general-purpose"` with `model: "sonnet"` (kb-worker's model; general-purpose would take the session's) and a brief that points the worker at `.claude/agents/kb-worker.md` and has it follow that file.
   Brief it with:
   - the item's JSON and its `/goal` text (`python3 _tools/backlog.py goal ID`);
   - the runbook's Working on items;
   - the in-flight sibling items (id and title) and the files their `touches` change, so the worker leaves them alone and no test of its reads them;
   - "run the item's checks and the fast tests, `python3 _tools/tests.py --changed origin/main`; never `python3 _tools/stress_test.py` or the full `tests.py`" (parallel full runs load the host into false timeouts);
   - "commit on a local branch `work/<id>` with `KB-Work: <id>` in the message's last paragraph, with `Co-Authored-By` and the other trailers; never push";
   - the known failing tests: each test you already know fails on the host (its test id), with the bug filed for it (id and title) and its cause, so the worker neither files it again nor guesses a cause; a failure the brief does not name is the worker's to file;
   - "run tests in the foreground, and end every background command and monitor you started before you return": `land` refuses a branch while a process still runs in its worker's worktree, naming each pid and command, and `python3 _tools/backlog.py procs` lists what workers left running in the clone (`procs --end` ends only an owned orphan);
   - "file a bug for any defect outside the item, do not fix it";
  - "a doc that needs an edit outside the touches stops the work with a report; `Self-Reviewed:` names only docs read and found still correct";
   - "a choice the goal leaves open: record a provisional gate with a recommendation (`gate add ID --kind provisional ...`), answer it `--provisional` and commit it with the work, never prose in the report only; a choice only the operator can make: a blocking gate, and stop";
   - "never write the operator's decisions into docs or code".
   An item with a single commit and a narrow `touches` may be done in this session instead.
4. When a subagent returns, land its branch yourself, one at a time:
   1. Land an item only after its gates are answered or provisional. Read them on its branch (`git show work/<id>:kb/_self/backlog/<id>.json`, its `gates`): an unanswered provisional gate, or a choice the report names that no gate records, goes back to the same subagent (SendMessage) to record and answer on its branch; an open blocking gate keeps the item waiting (step 5). Each provisional answer is the review's to confirm (review step 1).
   2. `git status --short` shows only your own changes (another session's files in your checkout: stop and move to your own clone or worktree); `land` refuses a branch checked out in another worktree, so `git worktree remove <path>` the worker's worktree first (its branch stays; never `--force`). A worker that left background work running leaves its worktree locked by Claude Code (`locked claude agent ...`): `land` itself unlocks and removes such a worktree when it is under `.claude/worktrees/` and has no uncommitted changes, and says so; any other lock, or uncommitted files, it refuses, naming why. While a process still runs in the worktree it refuses too, naming each pid: ask the worker to end it (SendMessage), or end it yourself, then land again;
   3. `/kb-verify` on the changed files;
   4. `python3 _tools/backlog.py land ID --trailer 'Co-Authored-By: ...'`, never the steps by hand. It runs `git fetch` and rebases `work/<id>` on `origin/main` (the integration remote's `main` as fetched, never local `main`, which your own clone or worktree cannot move while another worktree has it checked out), then:
      - a content-only item (its commits touch only kb roots and `kb/_self/*.md`): `done --commit`, then `sync --push` straight to `main`;
      - an item with a code-lane commit (`_tools/kblane.py`) not yet on the integration `main`: `sync --push` sends the range as a `code/<id>` merge request; `main` does not move and the item is not done. On the next pass, once the request has merged, run the same `land` again: it rebases onto the merged `main` (the merged commits keep their hashes), runs `done --commit` and pushes the item file;
      - it runs `python3 _tools/stress_test.py` once, when the landing changed `_tools/`, with the lookup eval and the contract lint, before `sync --push` (workers never run them).
   After a `land` that sent a `code/<id>` merge request, read the request: `glab mr view code/<id> -F json -R <project url>`. `state` `opened` with a `merge_error` is an auto-merge that failed: retry once with `glab mr merge code/<id> --auto-merge=false --yes -R <project url>` and name the error in your report; a retry that fails too is reported with its error and left to the operator, never tried a third time. `opened` with no `merge_error` waits for the next pass's `land`.
   It stops at the first failing step and names it (`land stopped at step <step>`): `clean tree`, `branch`, `fetch`, `rebase` (aborted, nothing changed: after `git fetch`, rebase the branch on `origin/main` by hand as `/kb-git-sync` does), `done`, `stress_test.py`, `rag.py eval`, `lint` or `kbgit.py sync --push` (`/kb-git-sync`). Fix the cause and run it again.
   If `done` refuses, send the reasons back to the same subagent (SendMessage) or release the item (`python3 _tools/backlog.py release ID`) and file what blocks it; for an unmerged `code/<id>` request it names the request to merge.
   A bug filed while landing is committed on its own, then claimed, before the commit that fixes it (`kb/_self/backlog.md`, Working on items).
5. A provisional gate: take the recommendation (`answer ID GATE --provisional`) and go on. A blocking gate: its items wait. In an interactive session ask the operator now, in one batch with the recommendations.
6. Stop when `next` prints nothing ready. Report the horizon: what landed, and what waits on which gate or trigger (each with its question).

### Headless (--headless)
`/kb-sprint run SP --headless [--landed K]` is the prompt `python3 _tools/autopilot.py runner start SP [--landed K]` sends (`autopilot.PROMPT`; `kb/_self/tools.md`, The autopilot runner). No operator reads the run: its stream is kept and its last message is read by the runner. Run the loop above with these changes, which win over it where they differ:
1. **No questions.** Never call AskUserQuestion, and never put a question to the operator in prose; nobody answers. Step 5's "ask the operator" becomes the gate of step 2 below. Name an item by id and title, as above.
2. **A choice only the operator can make** (an always-blocking kind, listed under `backlog "Dependencies, gates and triggers"` above, or an open blocking gate on a worker's branch) is recorded, never answered: when no gate on the item holds it yet, `python3 _tools/backlog.py gate add ID --question Q --option O --option O --recommendation R`, committed with `KB-Work: ID` and pushed with the claim sync (`python3 _tools/kbgit.py sync --push`). That item, and each item under it or after it, waits; set it aside for this run and go on with the rest of the ready list. Never `answer` a blocking gate and never use `--by operator`: the manager session reads the gate (`runner-status SP` lists the gates the run added or left open) and answers it.
3. **A provisional gate** takes its recommendation at once: `python3 _tools/backlog.py answer ID GATE --provisional`; a worker's branch lands only once each of its gates is answered or provisional (step 4.1).
4. **A refused command** (the run passes no permission flag, so the project's allow rules govern it) is not worked around: no other command that does the same, no sandbox override, no edit of a settings file. The item whose step it refused is blocked: `python3 _tools/backlog.py release ID` when it is claimed, set aside for this run, and named with the refused command in the final message.
5. **The landed count.** `K` is the number of items this run lands, counted from its start (a relaunch counts again from 0). An item is landed when its `land` has run `done` and pushed it; one whose `code/<id>` merge request has not merged is not landed yet (step 4). Claim at most `K` minus the items landed minus the items in flight, so the count never passes `K`; with no `--landed`, there is no limit.
6. **Where the last run stopped.** Keep nothing in the conversation: a relaunch starts at step 1 (`horizon`, `next --sprint SP --all`), and the repository holds the rest. Before step 2, `git fetch`, then `python3 _tools/backlog.py held --ref origin/main`: an item of this sprint it lists as claimed by `runner-SP-ID` belongs to an earlier run, whose worker ended with it. Land its `work/ID` branch (step 4) when `git branch --list work/ID` shows one with commits past `origin/main`, else `python3 _tools/backlog.py release ID`. Claim this run's items `--by runner-SP-ID`. The sprint's review story is the operator's (`## review SP`): the run never claims it.
7. **The end and its cause.** Stop when `K` items are landed, or when `next` prints nothing ready. Nothing is left running: no worker in flight, no background command. The last message is a short report (what landed, each with id and title; each gate recorded, with its question; each item set aside, with why; each unmerged `code/<id>` request), and its last line is exactly one of these, alone, with nothing after it (the runner records it; a message without one is recorded as `error`):
   - `sprint-runner: landed-limit`: `K` items landed, whatever is ready or waiting;
   - `sprint-runner: sprint-done`: nothing is ready and nothing waits: every item is done or dropped, or only the review story is left;
   - `sprint-runner: blocked`: nothing is ready and something waits on a blocking gate, a trigger, a refused command or an unmerged `code/<id>` request.

   The marker line appears only as that last line.

## review SP
The review story is ready once every other item is done or dropped. Its work:
1. Confirm or change each provisional answer with the operator (`answer ID GATE --confirm`, or a new answer plus a task or bug for the change), the ones workers recorded for choices their goals left open (run step 4.1) among them.
2. Print what the work cost, one command per id, each on its own: `python3 _tools/backlog.py cost --rework SP`, then the same for each story and each bug of the sprint (`python3 _tools/backlog.py tree --sprint SP` lists them). Keep each output for step 3 and the close retrospective, and show the operator what the sprint's work cost, which items had rework, and where shared tokens stand out. Rework is the tokens an item spent from the prompt that ran its first refused `backlog.py done` (a `done` that exited 1) to its `done`; the output lists each item that has it with its work and rework tokens, and an item with none is not listed. Say it as a measure of the work, never as blame: it names no one and no cause. It reports tokens only, no prices, and a figure whose output names an unresolved id (`no item file and no git history for ...` on stderr) is incomplete: say so with the figure.
3. Start a fresh-context reviewer subagent on the session model (`subagent_type: "general-purpose"`, no `model`) on the sprint's diff (`git log --grep "KB-Work"` over the sprint's items). Give it each item's goal and the cost outputs of step 2. It reports only gaps that affect correctness or a goal; the cost is context for them, not a gap to report.
4. File each gap as a bug (`/kb-backlog bug`): `S1` into this sprint, others to the backlog.
5. `python3 _tools/backlog.py done <review id>`.

## close SP
1. `python3 _tools/backlog.py close SP --summary` prints one line per item close will delete (id, title, kind, status and the commit `done` recorded, or `no evidence commit`) and changes nothing. It refuses while anything is open. Keep its `delivered by` list for the commit body.
2. **Retrospective.** From this sprint's evidence, list what went wrong in the process, not in the product:
   - a `done` that refused;
   - a check that passed although the item did not work;
   - a gate that should have been asked earlier;
   - a subagent brief that missed something;
   - a rule in `kb/_self/backlog.md` or a skill that got in the way;
   - what cost more than its size suggested, and the items with rework, from the review's `backlog.py cost --rework` outputs (tokens only; rerun one if the review is not in this session).
   Show the list to the operator. Each change they accept becomes a backlog story (`/kb-backlog`) naming the failure it answers. Write nothing into the docs directly.
3. `python3 _tools/backlog.py close SP --commit --trailer 'Co-Authored-By: ...'` deletes the sprint, its items and the epics they finished, and commits that with `KB-Work: SP-...` in the last trailer paragraph and a body that lists:
   - the `delivered by` list `close --summary` printed, as it is;
   - the retrospective's findings, each with the story it became or "no change", added above the trailers with `git commit --amend`.
4. `python3 _tools/kbgit.py sync --push`.
5. **Clean up** once the close commit is pushed: the sprint's subagent worktrees under `.claude/worktrees/` and its local work branches. Run `git fetch` first and compare against `origin/main`, never local `main`: from your own clone or worktree local `main` is checked out elsewhere and stays behind, so every landed branch would look unlanded. A branch is the sprint's when it is `work/<id>` for an id `close --summary` listed, or a `worktree-agent-*` branch whose commits' `KB-Work` trailers name one of those ids (`git log origin/main..<branch> --format='%(trailers:key=KB-Work,valueonly)'`). `git worktree list --porcelain` gives each worktree's path, branch and `locked` line. For each such branch, one command at a time:
   1. `git cherry origin/main <branch>`: any `+` line is a commit not on `origin/main`; keep the branch and its worktree;
   2. `git worktree remove <path>` for the worktree that has it checked out, never with `--force`: a worktree with uncommitted files is refused and kept. A worktree of this sprint's workers under `.claude/worktrees/` locked by Claude Code (its `locked` line starts with `claude agent`: the agent left background work running) with no uncommitted files (`git status --porcelain` in it prints nothing) is unlocked first, `git worktree unlock <path>`, then removed the same way;
   3. `git branch -D <branch>`: a branch landed by a rebase is not an ancestor of `origin/main`, so `-d` refuses it.
   Never touch a worktree with another lock reason, another sprint's branch or `_cache/querylog/worktree`. Report each worktree and branch kept and why (a `+` commit, uncommitted files, locked), and each one unlocked.

## Self-check
`python3 _tools/backlog.py selfcheck` (read only, no network, capped) opens every pass of `run`, before `stalled`: one line when all of six checks hold, else a line for each that failed (`FAIL`, exit 1) or could not be read (`UNKNOWN`, never a failure: read that input by hand), with its remedy. Act on a failure before dispatching, or record why you cannot (a gate, or the digest). The checks and what each does on failure:
- `allow-rules`: a command the skills run, or a tool the loop calls, has no allow rule in `.claude/settings.json`: `ask-operator`; the settings are the operator's, a run never edits them, and the item that needs the refused command is released and the command named (Headless, rule 4).
- `hooks`: the commit hooks or the plugin are not installed: run `/kb-setup` (`python3 _tools/kbgit.py install-hooks`) before any commit.
- `host`: the load is over its per-core limit, a host lock has been held past `HOST_LOCK_WAIT_S` by a live process, or a third sprint runner lives: for load and a lock the `lock-wait` ladder, `retry-narrower` (fewer workers, a `-k` selection) then `file-blocker`; for a runner, end the extra one.
- `claims`: a claimed item shows `claim-no-commit`, `returned-no-commit` or `returned-staged`: the next remedy of that signal's ladder (below), `release-redispatch` first for a returned worker.
- `orphans`: a process the autopilot recorded runs on without its parent: `procs --end`, which ends owned orphans only.
- `main`: the newest `ci.pipeline` row is red: `file-blocker` (`stalled --took ID red-main file-blocker`), take the next ready item, then `ask-operator`; with no row the check is `UNKNOWN`: `python3 _tools/backlog.py red-pipeline --status` reads the forge.

## Stalled work
Stalled work is claimed or ready work that makes no progress, or is hampered. `python3 _tools/backlog.py stalled` lists it (read only, exit 0, no network): each claimed or ready item, its id and title together, with its signals and the next remedy of each. Run it at step 1 of every pass of `run`, before claiming, and act on each listed item with the next remedy of its signal; `stalled --ladder` prints the ladder below from the code (`_tools/bl_stall.py`, whose named limits `CLAIM_NO_COMMIT_S`, `RETURNED_GRACE_S`, `DONE_REFUSED_N`, `CHECK_TIMEOUT_N`, `LAND_SAME_STEP_N` and `HOST_LOCK_WAIT_S` are in `kb/_self/backlog.md`). A signal whose input cannot be read shows as `unknown:<what>`: read that input by hand, never assume it is fine.

Each signal has a ladder, taken in order, each remedy once:
- `claim-no-commit`: `retry-narrower` > `release-redispatch` > `file-blocker` > `ask-operator` (a claim with no work commit past the limit)
- `returned-no-commit`: `retry-narrower` > `release-redispatch` > `file-blocker` > `ask-operator` (a worker's worktree with no live process and no commit)
- `returned-staged`: `finish-here` > `release-redispatch` > `file-blocker` > `ask-operator` (the same with staged or modified files left: the worker waited for a background-run completion notice that never came)
- `done-refused`: `retry-narrower` > `release-redispatch` > `file-blocker` > `ask-operator` (`done` refused repeatedly)
- `check-timeout`: `retry-narrower` > `release-redispatch` > `file-blocker` > `ask-operator` (a check ran out of its time twice)
- `land-same-step`: `retry-narrower` > `release-redispatch` > `file-blocker` > `ask-operator` (`land` stopped at the same step twice)
- `red-main`: `file-blocker` > `ask-operator` (the newest pipeline row is red)
- `lock-wait`: `retry-narrower` > `file-blocker` > `ask-operator` (the host test lock held past the limit)

The remedies:
- `finish-here`: finish the last steps in the orchestrator (stage, commit with `KB-Work: <id>` in the last trailer paragraph, run the item's checks), then run the checks in the foreground, never as a background command whose completion notice a session must wait for.
- `retry-narrower`: send the work back once (SendMessage) with a narrower request: one file, one test selector, a foreground run; for `lock-wait` a `-k` selection, which takes no host lock.
- `release-redispatch`: `python3 _tools/backlog.py release ID`, then dispatch it again (`run` step 3) with the failure named in the brief.
- `file-blocker`: file what blocks the item as a story (`stalled --took ID SIGNAL file-blocker` does it and prints the next ready item), release the item, and take the next ready item.
- `ask-operator`: record a gate (`gate add ID ...`) or put the question in the digest; in a headless run the gate of the headless rules.

The autopilot never idles while a ready item remains: after `file-blocker`, `release-redispatch` or a spent ladder it takes the next ready item that shows no signal, and it asks only when no such item is left. Record each remedy as it is taken: `python3 _tools/backlog.py stalled --took ID SIGNAL REMEDY` appends one `stall.remedy` ops row (`kb/_self/querylog.md`) and one autopilot decision of `kb/_self` with a `review_by` date, which the next commit carries; a remedy already taken for that item and signal is refused, and the listing then shows the next one.
