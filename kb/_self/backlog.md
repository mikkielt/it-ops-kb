# Backlog: planning and shipping changes to this project

How a change to this project is planned, scheduled, worked on, proven done and closed. The work is tracked as epics, stories, tasks, subtasks, bugs and sprints, stored as one JSON file per item in `kb/_self/backlog/`. `_tools/backlog.py` is the only thing that computes state from those files, and three skills run the process: `/kb-backlog` plans, `/kb-sprint` runs a sprint end to end, and `/kb-item` works one item. Read this before any of them. Read `kb/_self/maintaining.md` before the change itself.

The backlog is the one queue of open work. `_gaps.md` and `_conflicts.md` stay content ledgers, and query-log findings stay in `kb/_querylog/`. An item may name a ledger entry or a finding in `links`; the ledger entry itself is not the work item.

## Why data, not prose

- An agent keeps its task list as structured data it may only flip from failing to passing after a check. A status written in prose invites a later session to declare the job done too early (`agents/agent-planning-and-done.md`, DOC S2150, DER S2150, S-o3v6ozch).
- Something other than the working agent decides it is done. Here that is `backlog.py done`, which runs the item's checks itself and records their exit codes (DOC S-o3v6ozch).
- One file per item means parallel agents never edit the same file. Random ids mean two writers never pick the same one.

## Levels

GitLab plans with an epic, issue and task hierarchy (`gitlab/work-items-planning.md`, DOC S-v2ztgtdn). Scrum names no epics, stories, subtasks or story points (`agents/agent-planning-and-done.md`, DER S-2wwcyoa4). The levels here are sized by what lands in git:

| kind | id | is | parent | needs |
|---|---|---|---|---|
| epic | `EP-` | an outcome across many pushes | none | title, priority |
| story | `ST-` | one verifiable capability; lands in one `kbgit.py sync --push` | epic or none | goal, checks |
| bug | `BG-` | a defect, sized like a story | epic or none | goal, severity, `repro` |
| task | `TK-` | one commit | story or bug | goal, checks, touches |
| subtask | `SB-` | one agent step inside a task (a `/goal` run, a subagent); no commit of its own | task | touches |
| sprint | `SP-` | a goal and the stories and bugs committed to it | none | goal, the `start` gate |

A story or bug too big for one push is split into two. A task too big for one commit is split into two. There are no estimates. Every id is the kind's prefix and 8 random base32 characters.

## The item file

`python3 _tools/backlog.py new KIND --title ...` creates a file. An agent edits the JSON, then runs `python3 _tools/backlog.py fmt` (canonical key order and layout) and `python3 _tools/backlog.py check`. Fields, in file order:

| field | holds |
|---|---|
| `id`, `kind`, `title` | identity; the title is a short name that is always printed with the id |
| `status` | `draft`, `todo`, `doing`, `done`, `dropped` (a sprint: `planned`, `active`) |
| `parent`, `sprint` | the hierarchy; only stories and bugs name a sprint, and their tasks and subtasks follow it |
| `review` | true on the sprint's review story |
| `priority`, `rank` | `P1` to `P3`, then an integer order within the priority |
| `severity`, `repro` | bugs: `S1` to `S4`, and the check that fails until the fix lands |
| `goal` | the end state, as a fact about the repository once done |
| `checks` | the commands that prove the goal: `{"run": [argv], "exit": 0, "match": "regex"}`, run without a shell |
| `touches` | path globs the item's commits may change (`*` within a directory, `**` across) |
| `depends_on`, `relates_to` | hard dependencies (not ready until they are done); soft links |
| `gates` | questions for the operator: `{"id", "kind": "blocking"\|"provisional", "question", "options", "recommendation", "answer", "by"}` |
| `trigger` | an outside event it waits for: `{"when": text, "fired": false}` |
| `links`, `notes` | ledger entries, answers and docs it relates to; present-state notes |
| `claimed_by`, `evidence` | written by `claim` and `done` only |

Items describe the present, never a history: no dated logs, no "tried X on Monday". What happened is in the commits. The git history keeps an item's earlier versions and the design choices of finished work, including items deleted at sprint close:
- `git log --grep "KB-Work: <id>"` lists the commits that worked on an item;
- `git log --all -- kb/_self/backlog/<id>.json` lists the versions of its file;
- `git show <commit>^:kb/_self/backlog/<id>.json` prints its last text before deletion.

## Status and readiness

Only `draft`, `todo`, `doing`, `done` and `dropped` are stored. Whether an item is ready or waiting is computed on every call, never stored, so it cannot go stale. `backlog.py show ID` prints what an item waits on. An item is ready when all of these hold:
- it is `todo` (or `doing`, claimed by you);
- its sprint is active (`/kb-item` may take an item outside any sprint: `next --any`, but its work lands only once it is in a started sprint, Git below);
- every `depends_on` item is `done`;
- no blocking gate on it or an ancestor is unanswered;
- every trigger on it or an ancestor has fired;
- it has no open children;
- if it is the review story, every other item of its sprint is done or dropped.

GitLab's status categories match these states: Triage for `draft`, To do, In progress for `doing`, Done, and Canceled for `dropped`. Only Done and Canceled close an item (`gitlab/work-items-planning.md`, DOC S-il7kjbdz).

`python3 _tools/backlog.py next` prints the first ready item. The order is:
1. `S1` bugs;
2. then the `priority` and `rank` of the story or bug on top;
3. then the item's own `rank`.

## Priority and severity

Priority says when an item is scheduled; severity says how much a bug hurts. They are separate axes, as in GitLab's triage (`gitlab/work-items-planning.md`, DOC S-25zwwcdx).

| priority | means |
|---|---|
| `P1` | next: it goes into the running sprint or the next one |
| `P2` | planned: the next few sprints |
| `P3` | wanted, no date |

| severity | in this project | example |
|---|---|---|
| `S1` | a wrong answer served as `good`, private data in a public root or the query-log store, a broken gate or CI for everyone, lost kb content | the leak scan misses a tenant id |
| `S2` | a tool, hook or skill fails, with a workaround or on one OS | `kb_ask.py` crashes on Windows paths |
| `S3` | wrong or stale output that misleads nobody for long: a doc that disagrees with its code, a weak verdict that should be good | `tools.md` names a removed flag |
| `S4` | cosmetic | a typo in a docstring |

An `S1` bug joins the active sprint when it is filed and goes to the front of `next`. It never waits for the next sprint.

## Dependencies, gates and triggers

- **`depends_on`**: the item is not ready until each named item is `done`. `check` rejects a cycle and a dependency on a dropped item. GitLab's equivalent is **is blocked by** (`gitlab/work-items-planning.md`, DOC S-evjlv5hf).
- **`relates_to`**: information only.
- **Gates** are questions only the operator can settle. Each gate records its question, its options and a recommendation.
  - `blocking`: the item, and every item under or after it, waits until the operator answers: `backlog.py answer ID GATE --answer TEXT --by operator`. These are always blocking:
    - a push anywhere but `origin`'s `main`;
    - deleting kb content or history;
    - secrets and credentials;
    - the query log's mode, redaction or what it sends to the API;
    - a rule in `AGENTS.md`;
    - a sprint's start.
  - `provisional`: the agent goes on with the recommendation (`answer ID GATE --provisional`, recorded as `by: agent`). The sprint's review story cannot finish until the operator confirms each such answer (`--confirm`) or changes it; a changed answer becomes a task or a bug.
- **Triggers** hold an item until something outside the repository happens, such as a Claude Code release or a spec change. A session that sees it happen runs `backlog.py fire ID`.
- **Escalation.** An agent that needs a decision records a gate with its recommendation and moves on to the next ready item. In an interactive session it also asks the operator at once (AskUserQuestion) with the same options.
- **The horizon.** `python3 _tools/backlog.py horizon` shows how far each active sprint can go without the operator:
  - how many items are done, and how many are still reachable;
  - which items wait on which gate or trigger (with its question and recommendation);
  - the next item;
  - the critical path, with the number of items that can run in parallel at each step.
  A `SessionStart` hook (`horizon --hook`) prints it at the start of every session in a clone except one `/clear` starts (matcher `startup|resume|compact|fork`).

## Definition of done

Every item meets the shared minimum, the same bar for every item (`agents/agent-planning-and-done.md`, DOC S-2wwcyoa4):
- the gate in `kb/_self/maintaining.md` passes, and the tests pass on Linux and Windows in CI;
- every new check or gate has a test with a planted failure that makes it fail (DER S1896);
- no new dependency; the tools stay standard library only;
- portability: files are read and written with `encoding="utf-8"` (and `newline="\n"` when writing), paths go through `pathlib`, and subprocesses take argument lists;
- `/kb-self` has run when `_tools/`, `.claude/`, `.claude-plugin/` or `.gitlab-ci.yml` changed;
- the commits carry their KB-* trailers and `KB-Work`, and went through `kbgit.py sync --push`.

Each item adds three parts of its own: the end state (`goal`), the commands that prove it (`checks`), and what must not change (`touches`). Scrum has no acceptance criteria (DER S-2wwcyoa4), so the checks are the item's part of the bar. A check that runs a Python tool names `python3`; `done`, a bug's repro and `red-pipeline` run it with the interpreter that runs `backlog.py`, so a check proves the item on any host where the tool itself runs, a Windows Store `python3` alias or none on `PATH` included.

`python3 _tools/backlog.py done ID` is the only way to `done`. It refuses when any of these hold:
- the item waits on anything;
- a file in scope has uncommitted changes (the checks run on `HEAD`);
- a commit with its `KB-Work` trailer left a file outside `touches` changed at `HEAD` (a later revert clears that);
- one of its checks fails;
- a review story still has an agent's provisional answer.

When it succeeds it records the commit and each check's exit code and output digest in `evidence`. A bug is done when its `repro` passes as well. `backlog.py goal ID` prints a `/goal` condition naming the same end state, checks and scope, so a transcript-only judge sees the proof (`agents/agent-planning-and-done.md`, DOC S-vp5onm7b).

## Sprints

A sprint is a goal and the stories and bugs committed to it. It ends when its goal is met, not on a date. That departs from Scrum's fixed length but keeps the Sprint Goal as the one commitment (`agents/agent-planning-and-done.md`, DER S-2wwcyoa4).

1. **Plan** (`/kb-backlog epic "<outcome>"` or `/kb-backlog`, then `/kb-sprint plan`):
   - `backlog.py new sprint --title T --goal G` creates the sprint with its blocking `start` gate and its review story;
   - stories and bugs join the sprint with `"sprint": "SP-..."`, and tasks are broken down with `touches` and `checks`;
   - everything stays `draft`: `backlog.py check` reports an item whose status is `todo`, `doing` or `done` while its sprint is planned (not in a started sprint), and `new` creates a task or subtask under such a sprint's story as `draft`.
2. **Start**: the operator approves the goal and the committed items (`answer SP start --answer approve --by operator`). Then `backlog.py start SP` turns the drafts into `todo`.
   - Inside a running sprint, agents add tasks, subtasks and bugs freely.
   - A new story goes to the backlog for a later sprint, unless the operator adds it.
3. **Run** (`/kb-sprint run`): work ready items in `next` order until the horizon shows nothing reachable. Then report what waits on whom.
4. **Review**: the review story depends on every other item of the sprint. Its work:
   - the operator confirms or changes each provisional answer;
   - a fresh-context reviewer subagent reads the sprint's diff against each item's goal and reports only gaps that affect correctness or a goal (DOC S-o3v6ozch);
   - every gap becomes a bug, in this sprint if it is `S1`, else in the backlog;
   - `backlog.py check` and `tests.py` pass.
5. **Retrospective**: from the sprint's evidence, list the process failures: refused `done`s, checks that passed on broken work, late gates, briefs that missed something, rules that got in the way. The operator picks which to act on. Each accepted change becomes a backlog story naming its failure (Changing this process, below). The findings go in the close commit's body, never into the docs.
6. **Close**: `backlog.py close SP` refuses while anything is open. Otherwise it deletes the sprint, its items and the epics they finished, and the commit carries `KB-Work: SP-...`. The git history keeps all of it (The item file, above).

Several sprints may be active at once. Each has its own horizon.

## Working on items

- **One item** (`/kb-item ID`, or `/kb-item` for `next --any`):
  1. claim it: `backlog.py claim ID --by <session>`;
  2. print its `/goal` condition;
  3. do the work within `touches`, and commit with `KB-Work: ID`;
  4. run `backlog.py done ID`;
  5. commit the item file with the same trailer, then run `/kb-verify` and `kbgit.py sync --push`.
- **A sprint** (`/kb-sprint run SP`): one session is the orchestrator.
  - Ready items whose `touches` do not overlap run in parallel. Each goes to a subagent in its own git worktree (`isolation: "worktree"`) on a local branch `work/<id>`, never pushed.
  - A task or subtask goes to the `kb-worker` agent (`.claude/agents/kb-worker.md`: the newest Sonnet at high effort), started with no `model`, which would replace the agent's. An `S1` or `S2` bug with its tasks and subtasks, and a story or bug with no tasks yet (its breakdown), go to a subagent on the session model. The sprint review and every `/kb-census` subagent never use `kb-worker`.
  - The orchestrator lands them one at a time: rebase on `main`, `backlog.py done`, the gate, `kbgit.py sync --push`.
  - Items that share a file run one after another.
  - A subagent that finds a defect outside its item files a bug and does not fix it.
- **Finding a defect**: `backlog.py new bug --title T --severity S --repro "CMD" --goal G`. The repro command must fail now; `new` refuses one that passes. Bugs come from:
  - an agent at any time;
  - the operator;
  - a sprint review;
  - a red pipeline: `python3 _tools/backlog.py red-pipeline` reads the newest finished pipeline of `origin`'s `main` (`glab api`, `gh` on GitHub; a note and no filing when neither is signed in) and, when it failed and no automatic revert (`KB-Auto: revert`) covers it, files one bug for it: `S1` when the `kb-tests` job failed (the gate itself is red on `main`), else `S2`. The bug's `links` name `pipeline <id>` and `fingerprint <12 hex>`: a hash of the first failed job's name and its first failure (the first failing test id, else its first error line with colours, timestamps, hex ids and numbers taken out), read from the job's log. An item that already names `pipeline <id>` stops a second bug, and a pipeline whose fingerprint an open bug already carries is added to that bug's `links` instead of filing another. The bug's repro is `red-pipeline --status`, which exits 1 while the newest finished pipeline is red, so the bug is done when `main` is green. An async `SessionStart` hook runs it silently in every clone, and the bug it files is an uncommitted item file until someone commits it. It answers the failure of a red `main` that nobody filed;
  - a query-log revert: the revert commit of a red automatic push adds one `S2` bug item of its own (same repro, `red-pipeline --status`), naming the failed pipeline and the reverted findings, with the same `pipeline` and `fingerprint` links, or joins the open bug that already carries its fingerprint (`kb/_self/querylog.md`, Delivery), so `red-pipeline` files no second one.

## Git

- Work lands on `main` directly through `python3 _tools/kbgit.py sync --push`, as for every change (`kb/_self/git.md`).
- Every commit that works on an item ends with `KB-Work: <id>[, <id>]`, one line, before the KB-* trailers the hook adds. `python3 _tools/kbgit.py check-trailers` flags a second line, or an id whose item file is in neither the commit nor its parent.
- Work lands only for a claimed item of a started sprint. On a commit not yet on `origin/main`, `check-trailers` refuses a `KB-Work` id whose item, as the commit has it, is not `doing` or `done` (not claimed), or whose sprint is not active (not in a started sprint). The pre-push hook and `sync`'s gate run it, so such work is not pushed; the commit-msg hook warns when the commit is made. Exempt: a backlog-planning commit (it changes only item files: new items, claims, gates, a sprint's plan, start or close), and the sprint and review items themselves. An item outside any sprint joins a started sprint before its work lands. Commits already on `origin/main` are history and stay as they are.
- Changing an item's JSON (claim, gate answers, done) goes in the same commit as the work, or in its own commit with the same trailer.

## Writing about items

Every message, report, commit body or note that names an item gives its id and its title together: `ST-pbonxqx4 “Direct push on the real origin”`, never a bare id. The tool's own output does the same. A list of ids alone tells the reader nothing.

## Changing this process

A new field, state, command or rule is added only for a failure that happened, and its commit names that failure. A mechanism that no longer catches anything is removed the same way. `_tools/test_backlog.py` has one planted failure per refusal. `backlog.py check` runs in the tests, so a broken item file fails the gate.
