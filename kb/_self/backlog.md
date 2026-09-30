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
| `knowledge` | the kb facts the work rests on: `{"ask": [questions], "refs": [...]}`, each ref a topic (`<domain>/<slug>` or `<root>/<domain>/<slug>`), a QK answer id (`QK-...`, `<root>:QK-...` outside `public`), a source id, or a fact (`<root>/<path>#<fact key>`, the 12-hex key `_anchors.csv` uses); `check` fails on a ref the clone's kb does not hold and reports a fact key no longer in its file as `stale knowledge` without failing |
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

**Knowledge state.** `show`, `next` and `horizon` run `pack` in process (no network, no model) on each `ask` and each `ref` of an item's `knowledge` (The item file) and print one state for each:
- `sufficient`: coverage `good` with no `check:` line (a `good` with one is `partial`);
- `partial`: coverage `weak`;
- `unknown`: coverage `none`, or a ref the kb does not hold;
- `stale`: a fact key no longer found in its file, or a source the pack cites has `superseded_by` set in `_sources.csv`;
- `conflicting`: the lead article (for a source ref, that source) has an open `_conflicts.md` entry: one that no `Resolved <date>`, `Superseded <date>` or `Reviewed <date>, not a source disagreement` note closes (`Reviewed <date>, still open` leaves it open).

`stale` wins over `conflicting`, which wins over coverage. There is no other state. The state is computed on every call, never stored, and never changes readiness; `horizon --hook` runs no pack, and an item without `knowledge` costs nothing.

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
    - a push anywhere but the integration `main`, a `code/<id>` branch or a publish;
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

  For a planned sprint (`horizon --sprint SP`), an unanswered start gate, or one answered with anything but an approval (`approve`, `approved`, `yes`), is the operator's question, and every item waits on it. Once the operator approved it, the sprint is reported as approved, not started, with `backlog.py start SP` as the step that remains, and its items are counted as waiting on that start, not on the operator or a trigger.
  A `SessionStart` hook (`horizon --hook`) prints a short form of it, each active sprint's id, title, counts and next item id without its goal or critical path, plus what waits on a gate, a trigger or a start (with no active sprint, the planned ones, each approved one marked approved, not started), at the start of every session in a clone except one `/clear` starts (matcher `startup|resume|compact|fork`).

## Definition of done

Every item meets the shared minimum, the same bar for every item (`agents/agent-planning-and-done.md`, DOC S-2wwcyoa4):
- the gate in `kb/_self/maintaining.md` passes, and the tests pass on Linux and Windows in CI;
- every new check or gate has a test with a planted failure that makes it fail (DER S1896);
- no new dependency; the tools stay standard library only;
- portability: files are read and written with `encoding="utf-8"` (and `newline="\n"` when writing), paths go through `pathlib`, and subprocesses take argument lists;
- `/kb-self` has run when `_tools/`, `.claude/`, `.claude-plugin/` or `.gitlab-ci.yml` changed;
- the commits carry their KB-* trailers and `KB-Work`, and went through `kbgit.py sync --push`.

Each item adds three parts of its own: the end state (`goal`), the commands that prove it (`checks`), and what must not change (`touches`). Scrum has no acceptance criteria (DER S-2wwcyoa4), so the checks are the item's part of the bar. Where the kb has real inputs for what an item changes (its own data, such as the lookup eval set), one of its checks runs over them besides the planted ones, since a check that passes on inputs its author chose can miss what those inputs would show. A check that runs a Python tool names `python3`; `done`, a bug's repro and `red-pipeline` run it with the interpreter that runs `backlog.py`, so a check proves the item on any host where the tool itself runs, a Windows Store `python3` alias or none on `PATH` included.

`python3 _tools/backlog.py done ID` is the only way to `done`. It refuses when any of these hold:
- the item waits on anything;
- a file in scope has uncommitted changes (the checks run on `HEAD`);
- the item has `touches` of its own and no commit reachable from `HEAD` carries a `KB-Work` trailer, as git reads trailers, naming the item or one of its descendants (a story or bug whose tasks carried the work needs no commit of its own);
- a code-lane commit whose `KB-Work` trailer names the item or one of its descendants (lanes: `_tools/kblane.py`) is not an ancestor of `refs/remotes/<integration>/main` as last fetched, or that ref does not exist: it names the commits and the merge requests `sync` opened for them (branch `code/<id>`, the id each commit names); merge them, fetch, run `done` again. `done` does not fetch, and a content-lane commit never needs to be on the integration `main`;
- a commit whose `KB-Work` trailer names the item or one of its descendants left a file outside the scope (the item's `touches` with its descendants') changed at `HEAD` (a later revert clears that);
- one of its checks fails;
- a review story still has an agent's provisional answer.

When it succeeds it records the commit and each check's exit code and output digest in `evidence`. A bug is done when its `repro` passes as well. `backlog.py goal ID` prints a `/goal` condition naming the same end state, checks and scope, so a transcript-only judge sees the proof (`agents/agent-planning-and-done.md`, DOC S-vp5onm7b).

## Sprints

A sprint is a goal and the stories and bugs committed to it. It ends when its goal is met, not on a date. That departs from Scrum's fixed length but keeps the Sprint Goal as the one commitment (`agents/agent-planning-and-done.md`, DER S-2wwcyoa4).

1. **Plan** (`/kb-backlog epic "<outcome>"` or `/kb-backlog`, then `/kb-sprint plan`):
   - `backlog.py new sprint --title T --goal G` creates the sprint with its blocking `start` gate and its review story;
   - stories and bugs join the sprint with `"sprint": "SP-..."`, and tasks are broken down with `touches` and `checks`;
   - everything stays `draft`: `backlog.py check` reports an item whose status is `todo`, `doing` or `done` while its sprint is planned (not in a started sprint), and `new` creates a task or subtask under such a sprint's story as `draft`.
2. **Start**: the operator approves the goal and the committed items (`answer SP start --answer approve --by operator`). Then `backlog.py start SP` turns the drafts into `todo`. It refuses, changing nothing, while a story, task or bug other than the review story has no `touches` of its own and no tasks and subtasks that all have them, naming each (a dropped item is exempt): `done` checks a commit against that scope, and the orchestrator reads it to tell which items run in parallel. `check` does not report it, so a sprint already running stays valid.
   - Inside a running sprint, agents add tasks, subtasks and bugs freely; `new --sprint SP` writes an item filed into an active sprint as `todo`, ready to claim.
   - A new story goes to the backlog for a later sprint, unless the operator adds it.
3. **Run** (`/kb-sprint run`): work ready items in `next` order until the horizon shows nothing reachable. Then report what waits on whom.
4. **Review**: the review story depends on every other item of the sprint. Its work:
   - the operator confirms or changes each provisional answer;
   - a fresh-context reviewer subagent reads the sprint's diff against each item's goal and reports only gaps that affect correctness or a goal (DOC S-o3v6ozch);
   - every gap becomes a bug, in this sprint if it is `S1`, else in the backlog;
   - `backlog.py check` and `tests.py` pass.
5. **Retrospective**: from the sprint's evidence, list the process failures: refused `done`s, checks that passed on broken work, late gates, briefs that missed something, rules that got in the way. The operator picks which to act on. Each accepted change becomes a backlog story naming its failure (Changing this process, below). The findings go in the close commit's body, never into the docs.
6. **Close**: `backlog.py close SP` refuses while anything is open. Otherwise it deletes the sprint, its items and the epics they finished, drops their ids from every remaining item's `relates_to` and `depends_on` (a done dependency is satisfied; one on a dropped item stays for `check` to report), and the commit carries `KB-Work: SP-...`. `close SP --summary` first prints one line per item it deletes (tasks, subtasks, the review, dropped items and the finished epics included): its id, title, kind, status and the commit `done` recorded in `evidence`, or `no evidence commit` for a dropped one. That list is the close commit's body; only the retrospective's findings are written by hand. The git history keeps all of it (The item file, above).

Several sprints may be active at once. Each has its own horizon.

## Working on items

- **One item** (`/kb-item ID`, or `/kb-item` for `next --any`):
  1. claim it: `backlog.py claim ID --by <session>`, then commit the item file on its own with `KB-Work: ID` (a backlog-planning commit) before any work commit, since `check-trailers` reads the item as each commit has it;
  2. print its `/goal` condition;
  3. do the work within `touches`, and commit with `KB-Work: ID`;
  4. an item with a code-lane commit: run `/kb-verify` and `kbgit.py sync --push` first, which sends a `code/<id>` merge request; once it has merged, `git fetch` and rebase local `main` onto the integration `main`;
  5. run `backlog.py done ID`;
  6. commit the item file with the same trailer, then run `/kb-verify` and `kbgit.py sync --push` (a content-lane commit, straight to `main`). A content-only item skips the merge request.
- **A sprint** (`/kb-sprint run SP`): one session is the orchestrator.
  - Ready items whose `touches` do not overlap run in parallel. Each goes to a subagent in its own git worktree (`isolation: "worktree"`) on a local branch `work/<id>`, never pushed.
  - A task or subtask goes to the `kb-worker` agent (`.claude/agents/kb-worker.md`: the newest Sonnet at high effort), started with no `model`, which would replace the agent's. An `S1` or `S2` bug with its tasks and subtasks, and a story or bug with no tasks yet (its breakdown), go to a subagent on the session model. The sprint review and every `/kb-census` subagent never use `kb-worker`.
  - When the Agent tool does not list `kb-worker` (agent files load at session start, so a session that added or changed it cannot use it), the task goes to `general-purpose` with `model: sonnet`, the one `model` the orchestrator passes, and a brief that points the worker at `.claude/agents/kb-worker.md`.
  - The orchestrator lands them one at a time: rebase on `main`, the gate, `kbgit.py sync --push` (code goes as a `code/<id>` merge request, several items' code may share one), and on a later pass, once the request has merged and been fetched, `backlog.py done` and a second `kbgit.py sync --push` for the item file. Content-only items go `done`, commit, `sync --push`.
  - Items that share a file run one after another.
  - A subagent in a worktree cannot run the lookup eval as a Bash command. Claude Code's worktree isolation check, not a repo or plugin hook and not a permission rule, refuses any Bash command with the word `eval` in it, even `grep eval`, as one that runs a string through `eval`. The subagent runs its pytest wrapper instead: `python3 _tools/tests.py _tools/test_kb.py -k "test_lookup_ and passes"` (`test_lookup_eval_passes`, which passes when the eval exits 0). A command inside a script file the subagent runs passes the check, and so does an item check that `backlog.py done` runs as a subprocess.
  - A subagent that finds a defect outside its item files a bug and does not fix it.
- **A bug filed while landing** (by the gate, a review or a refused `done`) is committed on its own first, a backlog-planning commit with only its item file, then claimed and committed as in step 1 above, before the commit that fixes it: `check-trailers` refuses a `KB-Work` id whose item file is in neither the commit nor its parent, and one that is not claimed.
- **Finding a defect**: `backlog.py new bug --title T --severity S --repro "CMD" --goal G`. The repro command must fail now, and because of the defect. `new` refuses one that passes. It also refuses one that fails for its own error, naming the cause but not dumping the output:
  - it cannot start: not found, exit 127 or 9009, or a shell's or `python -m`'s lone not-found message;
  - Python cannot compile its own code: a `SyntaxError` in the `-c` string or in the script it names, such as a Windows path like `kb\public\x.md` inside a Python string, or statements whose newlines `--repro`'s split lost (use `/` and `;`, or a script);
  - the tool it runs rejects its arguments: argparse's exit 2 with `usage:` and `error:`;
  - a test run selected no tests: pytest's `no tests ran`, or exit 5 with everything deselected, such as a `-k` that matches nothing.

  A failed assertion, a traceback from the code under test, or a tool that prints a finding and exits 1 counts as a reproduction. The repro that `red-pipeline` builds is its own command and does not go through this check. Bugs come from:
  - an agent at any time;
  - the operator;
  - a sprint review;
  - a red pipeline: `python3 _tools/backlog.py red-pipeline` reads, among the last 100 finished pipelines of the integration remote's `main`, the newest one in which a job ran (`ql_deliver.job_ran`: a start time, success, running, or a failure of its own), or the newest finished one when no job ran in any (`glab api`, `gh` on GitHub, where it reads the newest completed run; a note and no filing when neither is signed in; on GitLab one waiting on manual jobs counts as finished). Every job in `.gitlab-ci.yml` is manual, so most pipelines of `main` are ones nobody started, and a newer one of those hides nothing. On GitLab it reads the pipeline by its jobs, not by its status, since every job is manual with `allow_failure: true`, so the status says success whatever they did, and a job nobody started holds nothing (`ql_deliver.job_verdict`):
    - **red**: the pipeline failed, or a job someone started failed on its own account (`failure_reason` `script_failure`, `job_execution_timeout` or `stuck_or_timeout_failure`), whichever job;
    - **unverified**: the job list is unreadable, or a job named in `ql_deliver.GATE_JOBS` did not succeed (none is named while every job is manual, so a pipeline nobody ran is green);
    - **green**: neither.

    When it is red and no automatic revert (`KB-Auto: revert`) covers it, it files one bug for it: `S1` when the `kb-tests` job failed (the gate itself is red on `main`), else `S2`. An unverified pipeline files nothing. With every job manual, `red` means a job someone started failed its script; a pipeline no one started is green. The bug's `links` name `pipeline <id>` and `fingerprint <12 hex>`: a hash of the first failed job's name (by name, among the jobs whose script ran when there are any) and its first failure (the first failing test id, else its first error line with colours, hex ids and numbers taken out; GitLab.com's per-line timestamp and stream marker, such as `01O` or `01E`, come off every line before either is matched), read from the job's log. An item that already names `pipeline <id>` stops a second bug, and a pipeline whose fingerprint an open bug already carries is added to that bug's `links` instead of filing another. The bug's repro is `red-pipeline --status --job <that first failed job>`: `--job` reads the newest pipeline of `main` in which that job ran, so the repro exits 1 until the job runs again and passes, not when a later push starts nothing or another job passes (plain `--status`, when no failed job was read, exits 1 while the pipeline it reads is red or unverified, naming each gate job that did not pass when `GATE_JOBS` names any). An async `SessionStart` hook runs it silently in every clone, and the bug it files is an uncommitted item file until someone commits it. It answers the failure of a red `main` that nobody filed;
  - a query-log revert: the revert commit of a red automatic push adds one `S2` bug item of its own (the same repro, `red-pipeline --status --job <its first failed job>`), naming the failed pipeline and the reverted findings, with the same `pipeline` and `fingerprint` links, or joins the open bug that already carries its fingerprint (`kb/_self/querylog.md`, Delivery), so `red-pipeline` files no second one.

## Git

- Work lands through `python3 _tools/kbgit.py sync --push`, as for every change, by lane (`kb/_self/git.md`, The regime by role): content-only work (backlog items, `kb/_self/*.md`, kb roots) goes to the integration `main`; work with a code-lane commit goes as a `code/<id>` merge request, and the item is done once that request has merged and the commits are on the fetched integration `main`.
- Every commit that works on an item ends with `KB-Work: <id>[, <id>]`, one line, in the message's last paragraph together with the other trailers (`Co-Authored-By` and the KB-* trailers the hook adds after them). Git reads trailers only in that paragraph: a `KB-Work` line in an earlier one, or with a blank line before `Co-Authored-By`, is no trailer, and `done` finds no commit for the item. `python3 _tools/kbgit.py check-trailers` flags a second line, or an id whose item file is in neither the commit nor its parent.
- Work lands only for a claimed item of a started sprint. On a commit not yet on `origin/main`, `check-trailers` refuses a `KB-Work` id whose item, as the commit has it, is not `doing` or `done` (not claimed), or whose sprint is not active (not in a started sprint). The pre-push hook and `sync`'s gate run it, so such work is not pushed; the commit-msg hook warns when the commit is made. Exempt: a backlog-planning commit (it changes only item files: new items, claims, gates, a sprint's plan, start or close), and the sprint and review items themselves. An item outside any sprint joins a started sprint before its work lands. Commits already on `origin/main` are history and stay as they are.
- Changing an item's JSON (claim, gate answers, done) goes in the same commit as the work, or in its own commit with the same trailer.

## Writing about items

Every message, report, commit body or note that names an item gives its id and its title together: `ST-pbonxqx4 “Direct push on the real origin”`, never a bare id. The tool's own output does the same. A list of ids alone tells the reader nothing.

An item is published with the repository, so it never holds this host's computer name or its user's name: placeholders only (`PL-LT-00123`, `jan.kowalski`). `backlog.py check`, and so the push gate, refuses an item whose JSON holds a piece of either, naming the item's id and the field (`gates[0].question`) and withholding its title, the one exception to the rule above; its output never prints the name or the piece. It answers BG-477tasb3, where checks written to keep the names out of a report spelled pieces of them, and the leak scan (addresses, tokens, GUIDs) does not look for names. Checks that guard against host or user names read them from the environment at run time, never spell them: `COMPUTERNAME` and `HOSTNAME`, the socket host name's first label, `USERNAME`, `USER` and `LOGNAME` (getpass when none is set), and the profile folder's name (`USERPROFILE`, `HOME`). A name of more than 8 letters and digits also has its Windows 8.3 short form as a piece (`jankow~`, as a TEMP path's `JANKOW~1` profile folder), unless a generic name starts with its first six. No command prints a piece either: every line `backlog.py` writes (a title in `list`, `tree`, `show` or `done`, a repro's output, a refusal, the session hook's message) has it replaced by `<name withheld>`, so a name never reaches a line an agent copies into a commit message. A piece is the whole name, it without separators, each part between non-alphanumerics and each CamelCase part of those (`JanKowalskiCorp`: `jankowalskicorp`, `kowalski`; `XYZ-PC01`: `xyz-pc01`, `xyzpc01`, `pc01`), kept when it has a letter, 5 characters or 4 with a digit, and is not a name every CI runner, container or fresh install shares (`runner`, `container`, `desktop`, `project`: `backlog.GENERIC_NAMES`), so an ordinary short word never matches; it matches case-insensitively anywhere in a string value or key. The project's own repository paths, read from the git remotes' URLs (`namespace/project` and `namespace%2Fproject`), are left out of the match, since a namespace can equal a user's name; the name anywhere else is still refused.

## Changing this process

A new field, state, command or rule is added only for a failure that happened, and its commit names that failure. A mechanism that no longer catches anything is removed the same way. `_tools/test_backlog.py` has one planted failure per refusal. `backlog.py check` runs in the tests, so a broken item file fails the gate.
