#!/usr/bin/env python3
"""The kb's own backlog: epics, stories, tasks, subtasks, bugs and sprints, one JSON file per item in
kb/_self/backlog/ (kb/_self/backlog.md is the runbook). Standard library only; no model, and no network except `red-pipeline` and `intake --network`.

  backlog.py new KIND --title T [--parent ID] [--sprint ID] [--priority P1|P2|P3] [--rank N] [--goal TEXT]
                 [--severity S1..S4] [--check CMD]... [--touch GLOB]... [--depends ID]... [--repro CMD]
                 [--repro-reason TEXT] [--external TRACKER=ID]...
                                          a new item (KIND: epic, story, task, subtask, bug, sprint); prints its id
                                          and title. A bug's --repro must fail now, and for the defect: one that
                                          cannot start, dies of a SyntaxError in its own code, gets a usage error
                                          (argparse exit 2) or runs no tests (tests.py's exit 2 that names a
                                          selection collecting no test, or pytest's exit 5) is refused with the
                                          cause; one that only matches text in a file (grep, a python -c that
                                          reads a file) is refused (exit 2, nothing written) without
                                          --repro-reason, kept as repro_reason; a warning names a check or repro that runs no test or tool code,
                                          a repro whose output says it did nothing here, and a bug whose repro
                                          runs a tool with no check that runs tests; a sprint gets its start gate and its review story. A new item that
                                          is a near-duplicate of an open one (similar, below) gets a warning naming
                                          it; the item is still written and the exit code is unchanged
  backlog.py similar TITLE [--goal G]     open items ranked by word overlap of TITLE (and G) with their title and
                                          goal: the share of the query's words found (stop words left out), the
                                          shared count, `near` from 0.60 and 2 words; the first 10; exit 0
  backlog.py check                        validate every item (fields, links, cycles, canonical form, a planned
                                          sprint's items still draft but a claimed research item, and the kb
                                          references of its `knowledge`: a missing one is an error, a fact key no
                                          longer found is reported as stale knowledge; no item may hold a piece of
                                          this host's computer or user name, read from the environment and never
                                          printed, and none a leak-scan hit, its kind named and never its value); warns of an open bug whose repro only matches text in a
                                          file (a grep of _tools/ source among them) with no repro_reason; exit 1
                                          on errors
  backlog.py fmt                          rewrite every item in canonical form
  backlog.py selectors                    one line per `tests.py -k` selector in the checks of open items: how many
                                          tests pytest --collect-only finds for it now (NONE marks zero, error a
                                          collection that failed), the item's id and title; exit 0 whatever the
                                          counts (a selector often names a test its item has yet to write), 1
                                          without pytest
  backlog.py list [--kind K] [--status S] [--sprint ID]   one line per item: id, kind, status, priority, title
  backlog.py tree [ID] [--sprint ID] [--open]  the hierarchy under an item, a sprint or everything (--open: no done or
                                          dropped item)
  backlog.py find WORD...                 the open items whose title, goal or external ids hold every word
                                          (case-insensitive), each with its parent chain; no match prints one
                                          line and exits 1
  backlog.py show ID                      one item, its parent chain, children, an `external TRACKER REF URL` line
                                          for each external id, the knowledge state of each ask and ref of its
                                          `knowledge` and what it waits on; an item whose file was
                                          deleted (a closed sprint's) prints its last version from git history
  backlog.py next [--sprint ID] [--any] [--all]   the ready item to work on first (--all: every ready item in
                                          order; --any: items outside an active sprint too, for single-item work),
                                          with the knowledge state of each of its asks and refs
  backlog.py held [--overlaps ID] [--ref REF]   the paths other sessions hold: one line per touches glob of each
                                          claimed (doing) item, with the item, its claimer and its sprint; --ref
                                          reads the item files as REF has them (origin/main after git fetch, where
                                          every claim sync lands; exit 2 for a ref git cannot read). --overlaps ID:
                                          only the claimed items outside ID's chain whose touches overlap ID's own or
                                          its descendants' (a glob read as a path matches the other, or a tracked file
                                          matches both), each naming the glob it meets; exit 1 when there is one
  backlog.py claim ID --by NAME          status doing, claimed by NAME;  backlog.py release ID  back to todo
                                          (a research item of a planned sprint, one whose touches are all inside kb
                                          roots: claimed from draft, released to draft; check accepts it doing or
                                          done, and done proves it before the sprint starts)
  backlog.py answer ID GATE (--answer TEXT --by operator|agent [--record] | --provisional | --confirm
                            --by operator|delegate:NAME)
                                          record a gate's answer: --provisional takes the recommendation as the
                                          agent's answer (provisional gates only); --confirm --by operator makes an
                                          agent's answer the operator's (no --by: exit 2); --by delegate:NAME
                                          confirms only under an operator grant on the sprint (set SP
                                          --delegate NAME --by operator), recorded as that delegate;
                                          --record (with --by operator) also writes it as an active
                                          decision of kb/_self through kbdecide.py, its context the item (exit 2 with
                                          --provisional, --confirm or a --by other than operator);
                                          a gate of class secrets, push or agents-rule takes
                                          an answer only with --by operator (--provisional, --confirm included);
                                          --record commits what it wrote, the item file (chore(backlog): answer ID
                                          "title", KB-Work: ID, then each --trailer 'KEY: VALUE') and the decisions
                                          row (no KB-Work), so the tree is clean for the next kbgit.py sync
  backlog.py set ID [--notes TEXT] [--link T]... [--touch GLOB]... [--check CMD]... [--depends ID]...
                 [--relates ID]... [--priority P1|P2|P3] [--rank N] [--sprint ID] [--title T] [--goal T]
                 [--repro CMD] [--repro-reason T] [--severity S1..S4] [--parent ID]
                 [--delegate NAME --by operator] [--add-notes T]... [--add-link T]... [--add-touch GLOB]...
                 [--add-check CMD]... [--add-depends ID]... [--add-relates ID]... [--external TRACKER=ID]...
                 [--add-external TRACKER=ID]... [--clear FIELD]...
                                          change an item after new: each list option replaces its list, and its
                                          --add-<option> twin appends what is missing to it, so a second run changes
                                          nothing (--add-notes appends the text unless the notes hold it); a call
                                          that names both for one field is refused, naming it. --clear FIELD
                                          removes one. --external replaces the external ids whole, and only a
                                          tracker backlog.json's trackers names takes an id its pattern matches.
                                          The result is validated as check does and written only when it adds no
                                          error; title, goal and parent, and a bug's repro (one that fails now, as
                                          new bug's), repro_reason and severity are replaced whole; status,
                                          claimed_by, evidence, id, kind, a done item's goal, repro, checks and
                                          touches (its evidence proves them) and the fields set does not name
                                          are refused, and a sprint takes notes and links only; exit 2 for each
                                          refusal (exit 1 for a repro that passes), the item file unchanged
  backlog.py move ID --sprint SP|none     set a story's or bug's sprint (none: no sprint) and write the status that
                                          sprint's state gives: todo in an active sprint, draft in a planned one or
                                          in none; its draft and todo tasks and subtasks follow. Refused (exit 2, the
                                          file unchanged): a task, subtask or review story, a doing, done or dropped
                                          item or one with a doing task, a missing sprint, an item without touches
                                          into an active sprint; a second run changes nothing
  backlog.py reopen ID --why TEXT         a done item back to work: evidence and claimed_by cleared, status todo (draft
                                          while its sprint is planned); any other status is refused (exit 2). The
                                          reason is printed, never written to the item
  backlog.py gate add ID --question Q --option O... --recommendation R [--kind blocking|provisional] [--id GATE]
                                          add a gate (kind blocking unless given; two or more options, the
                                          recommendation one of them; a gate about a capped file (AGENTS.md,
                                          README.md) needs each option to state the file's measured size, as
                                          'N bytes'; the id defaults to g1, g2, ...), validated as
                                          check does; the same gate again changes nothing, a different gate with an
                                          existing question or id is refused, as is one on a done or dropped item
                                          (exit 2); `answer` answers it
                                          --do OPTION=CMD|ID: the argv that carries the option out, or the id of the
                                          item whose work adds that command (repeatable); check warns of an
                                          unanswered blocking gate with none
                                          --host-check CMD: the command that proves the setup the gate's answer names
                                          holds on this host (exit 0), kept on the gate; `host-check` runs it
  backlog.py gate remove ID GATE [--by operator]
                                          remove an unanswered gate; an answered gate and a sprint's start gate are
                                          refused, and so is a gate of class secrets, push or agents-rule without --by
                                          operator (naming the class), so an agent cannot clear a gate only the
                                          operator answers; a reword is remove, then gate add, which classes the new
                                          text again (exit 2 for each refusal, the item file unchanged)
  backlog.py host-check SPRINT            run the host check of each answered gate of the sprint's open items, on this
                                          host, before the start gate is asked, and record each result on the gate
                                          (host_checked: ok, exit); exit 1, naming each gate and the command's output
                                          tail, when one fails; `start` refuses a sprint with an answered gate whose
                                          host check has no passing record
  backlog.py fire ID                      mark an item's external trigger as fired
  backlog.py done ID [--dry-run]          run the item's checks at a clean HEAD, check its commits' scope, record the
                                          evidence and set status done; exit 1 with the reasons otherwise, among
                                          them a check or repro that passed doing nothing here (its output a
                                          no-op marker, such as no public remote, or all tests skipped) with no
                                          other passing check that runs tests and no operator accept on gate
                                          host-bound; warns of each such check and of one that runs no code
  backlog.py researched ID                the goal research story's check, which new sprint gives it: exit 0 once
                                          its research is written by done's rules (a commit on HEAD whose KB-Work
                                          names it and changes a file other than item files, or its notes' No
                                          outside facts: <reason>), 1 before; read-only
  backlog.py land ID [--branch B] [--trailer 'KEY: VALUE']...
                                          land a finished item's branch (default work/ID) from a clean tree: fetch
                                          and rebase it on the integration main, then a content item: done --commit,
                                          rag.py eval and the lint when the landing changes _tools/ (the full tests.py
                                          runs once, at the review story), kbgit.py sync --push; an item with a code-lane commit not on that main:
                                          those checks and sync --push (the code/<id> merge request), and a re-run
                                          once it has merged ends as a content item does. A re-run before the merge
                                          says it waits, and when the request is open, mergeable, set to auto-merge
                                          and its pipeline was skipped (GitLab, glab signed in; else nothing more),
                                          names the glab mr merge command that merges it. A finished worker's clean
                                          worktree that Claude Code left locked is removed, unless a process still
                                          runs in it (refused, naming each pid; a host that cannot list them: a note,
                                          and it is removed). Stops at the first failing
                                          step, naming it (exit 1); a failed rebase is aborted
  backlog.py drop ID --why TEXT          status dropped (an item outside any sprint is deleted: git keeps it)
  backlog.py start SPRINT                 activate a sprint whose start gate the operator answered; drafts become todo;
                                          a warning (exit 0) for each open P1 item whose `recurs` names 2 or more
                                          sprint ids and that is not in the sprint
  backlog.py precheck SPRINT              run each committed item's checks once before any work and warn (exit
                                          0) of each that passes already, unless the item's notes say it
                                          passes before the work
  backlog.py close SPRINT [--summary]     delete a finished sprint, its items and the epics they finished
                                          (--summary: only list each of them with its status and the commit done
                                          recorded, the close commit's body, and change nothing; with --commit
                                          refused)
  backlog.py tidy [--apply]               list the clone's merged work/*, worktree-agent-* and orch/* branches and
                                          its clean agent-* worktrees, each other one with why it stays; --apply
                                          removes the listed ones (never --force)
  backlog.py horizon [--sprint ID] [--hook [--opt-in]]   how far each active sprint can go without the operator: reachable
                                          items, what waits on which gate or trigger, the critical path, the
                                          knowledge state of the next item's asks and refs (--hook runs no pack;
                                          --opt-in: only when backlog.json's `hooks` names horizon)
  backlog.py goal ID                      a /goal condition for the item: its end state, checks and scope; then
                                          the answered gates of its parent chain, which its work keeps to
  backlog.py brief ID [--known TEST=BUG]... [--probe TEXT]
                                          the brief a sprint worker is given, printed: the item's JSON and goal
                                          text, its external tracker ids with their urls, the role file, the
                                          worker's worktree and scratch directory (_cache/scratch/ID/), the
                                          in-flight sibling items with the files their touches change, the known
                                          failing tests (--known TEST=BUG, repeatable; BUG a backlog id), the fixed
                                          worker rules and the rules of the docs the item's touches map to
                                          (`rag.py pack --root _self --item ID`, or a line saying it is absent);
                                          writes nothing, starts nothing, exit 0
  backlog.py dispatch ID [--dry-run] [--model NAME] [--max-turns N] [--known TEST=BUG]... [--probe TEXT]
                                          start the item's headless worker: make its worktree
                                          (<worktree_dir>/agent-ID on work/ID from this checkout's HEAD) and the
                                          scratch directory, write the brief there (brief.md) and run `claude -p
                                          --model sonnet --effort high --output-format json --add-dir SCRATCH
                                          --max-turns N` in the worktree with the brief on stdin (never a prompt
                                          argument), in the foreground until the session exits: N by kind, 60 task
                                          or subtask, 100 bug or story with no tasks (and epic or sprint), 200
                                          research story or investigation bug (a bug whose title or goal says
                                          investigat...). The pid is recorded in the claims ledger of the git dir
                                          (worker_pid) when the session starts and its session_id (worker_session)
                                          when it exits; output goes to SCRATCH/result.json and SCRATCH/stderr.log.
                                          Refuses an item that is not doing (exit 1), a missing `claude` (exit 2);
                                          exit 1 when the session exits non-zero or reports is_error. --dry-run
                                          prints the worktree, scratch, brief path and argv and makes, writes and
                                          starts nothing; --model names another model than sonnet only when given
  backlog.py cost ID [--runs] [--rework] [--format text|json]
                                          the tokens the query log's work sidecars (kb/_querylog/work/) hold for the
                                          item and its descendants (for a sprint, its items too; a sprint's own line
                                          counts for a sprint only), per model: requests, in, cr, out and cw apart,
                                          direct (the item lines' main) and attributed (their routed subagents'
                                          sub). Shared lines, the session total and overhead are not printed yet.
                                          For a sprint, research items' lines (kb content only) are printed
                                          apart, and the overhead lines of the sidecar runs inside the sprint's
                                          window (its start commit to its close commit) as a total of their own,
                                          in no item or sprint figure; unresolved in a shallow clone.
                                          --rework adds the item work's split into work and rework (the counts
                                          from an item's first refused done; json: `rework_split`).
                                          --runs lists each run's line apart; json gives the same numbers. No
                                          sidecar: zeros, exit 0; an unknown id: exit 2. An item whose file is gone
                                          (deleted at sprint close, a closed sprint included) is read from its last
                                          version in git history; an id with none is named on stderr, left out
  backlog.py cost --research [--format text|json]
                                          every item with `research` true or a link naming a query-log gap finding:
                                          its tokens (in + cw + cr + out of its own direct + attributed lines), the
                                          gap findings closed by commits with its KB-Work trailer (a _gaps.md entry
                                          that gains a Resolved or Superseded note), and tokens per closed gap
                                          (integer division; n/a when none closed; unresolved in a shallow clone)
  backlog.py red-pipeline [--status [--job J]|--hook]   the newest pipeline of origin's main in which a job ran
                                          (--job: in which job J succeeded or failed on its own account, never
                                          canceled, manual or skipped; the newest finished one when none did; glab
                                          api, gh on GitHub; a note when neither is signed in), on GitLab read by its
                                          jobs: red when a job someone started failed (its script, a timeout, stuck),
                                          unverified when the job list is unreadable or a job
                                          in ql_deliver.GATE_JOBS (none) did not succeed. When red and no automatic revert covers it, one bug (S1 when
                                          the kb-tests job failed, else S2) unless an item already names that
                                          pipeline; a failure fingerprint (the first failed job and its first failing
                                          test or error line) in the bug's links, and a pipeline failing the same way
                                          joins that open bug's links instead. --status: exit 0 green, 1 red,
                                          unverified (naming any gate jobs) or unreadable; a bug's repro is --status
                                          --job <its first failed job> when its script ran, else --status. --hook:
                                          the async SessionStart form, silent
  backlog.py intake [--file [--hook [--opt-in]] | --status FINGERPRINT] [--network]
                                          the candidates of every detector in bl_intake.DETECTORS (deterministic: the
                                          repository's files, no network, no model; --network adds the `ci` detector,
                                          which reads main's newest pipeline as red-pipeline does and files the same
                                          bug: its `pipeline <id>` and `fingerprint` links, its red-pipeline repro),
                                          one block each: detector, kind,
                                          fingerprint (12 hex), title, then goal, repro (a bug's: intake --status
                                          FINGERPRINT) and links (`fingerprint <12 hex>` first, `detector <name>` last).
                                          Writes nothing; a
                                          candidate whose fingerprint an open item's links already carry is marked
                                          skipped. --file writes each new one as a draft item outside any sprint, so a
                                          second run files nothing; one that `similar` calls a near-duplicate of an
                                          open item of another detector goes into that item's notes once instead, and
                                          at bl_intake.OPEN_DRAFTS_MAX open drafts the rest are refused (exit 1, the
                                          cap message on stderr). --status FP: exit 1 while a detector still reports
                                          that fingerprint (or one cannot run), 0 once none does; the repro of every bug
                                          intake files. Exit 1 also when a detector failed, 2 for a bad fingerprint
                                          or --status with --file. --hook (the async SessionStart form, run as
                                          --file --hook, offline): silent, exit 0 always, runs drift after the other
                                          detectors, stops waiting for them after
                                          INTAKE_HOOK_BUDGET_S and files what the finished ones found, as uncommitted
                                          drafts, never commits or pushes. --opt-in (the plugin's entry): nothing
                                          runs unless backlog.json's `hooks` names intake
  backlog.py stalled [--json]               each claimed or ready item with its stall signals (bl_stall.py), read
                                          only
  backlog.py config                         the project settings (backlog.json at the root, or the file
                                          KB_BACKLOG_CONFIG names) with each value's source, file or default; a
                                          file with an unknown key or a wrong type is refused naming it, exit 2

claim, done, new, start and close take --commit [--trailer 'KEY: VALUE']...: after the command succeeds, commit the
item files it wrote or deleted and nothing else (`git commit --only`: what was staged before stays staged), subject
`chore(backlog): claim|done|file|start|close ID "title"`, and a last paragraph of trailers: KB-Work: <ids> (the item;
a new sprint and its review story), then each --trailer (the session's own, e.g. Co-Authored-By; a KB-* key is
refused). close's commit body is its --summary list.

Several ids after one --depends, --add-depends, --relates or --add-relates are taken as if each had its own flag
(bl_cli.parse).

--root DIR (before the command) runs against another clone or project, with that root's backlog.json settings (item
directory, id prefixes, trackers, worktree directory); without it the tool's own checkout, or, for a tool installed as a
plugin, the working directory's git root. Exit: 0 ok, 1 a refused command or check errors,
2 bad arguments, an unknown id, or a refused `set`, `gate add` or `gate remove`.

Knowledge state (show, next, horizon): one line `knowledge <state> ask|ref: <text>` per ask and per ref of an item's
`knowledge`, each run through kbfacts.pack (no network, no model) and reported as one of sufficient (coverage good, no
`check:` line), partial (weak, or good with a `check:` line), unknown (none, or a ref the kb does not hold), stale (a
fact key no longer in its file, or a source with `superseded_by` set that the ref is or cites) or conflicting (an open
`_conflicts.md` entry on its article); stale, then conflicting, override the coverage. Derived on every call, never
stored, and no part of readiness. An item without `knowledge` costs nothing: the pack is not loaded.

Every line that names an item prints its id and its title together, except a title check found holding a piece of
this host's computer or user name, which is withheld.
"""
import subprocess  # noqa: F401 - tests patch backlog.subprocess
import sys

import bl_check  # noqa: F401 - registers its commands
import bl_ci  # noqa: F401 - registers its commands
import bl_cli
import bl_items  # noqa: F401 - registers the item writers (new, fmt, claim, ... goal)
import bl_land  # noqa: F401 - registers its commands
import bl_plan  # noqa: F401 - registers its commands
import bl_view  # noqa: F401 - registers its commands
from bl_base import Backlog, COMMITS, OUTPUT_ROOT, ROOT, Refused, Rejected, cmd_config, load_settings, rel_dir
from bl_base import setting, trailer_problem, withhold
from bl_base import canonical, in_scope, waits  # noqa: F401 - tests read them as backlog.NAME
from bl_check import item_files_only, validate  # noqa: F401 - tests read them as backlog.NAME
from bl_land import run_check, own_failure  # noqa: F401 - tests read them as backlog.NAME
from bl_base import RESEARCH_KINDS, research_touches  # noqa: F401 - tests read them as backlog.NAME
from bl_base import run  # noqa: F401 - tests read the real runner as backlog.run
from bl_ci import (  # noqa: F401 - the CI readers and red-pipeline: bl_ci holds them; main and ql_deliver use them as backlog.NAME
    GITLAB_FINISHED, LOG_PREFIX_RE, MAIN_PIPELINES, S1_JOBS, STATUS_REPRO, add_pipeline, bug_with_fingerprint,
    cmd_red_pipeline, failure_fingerprint, first_failure, hook_intake, names_pipeline, normalise_error_line, red_bug,
)
from bl_view import (  # noqa: F401 - the read-only views: bl_view holds them; main uses cmd_horizon, tests ready
    cmd_horizon, is_near, ready, similar,
)
from bl_base import touches_overlap  # noqa: F401 - tests read it as backlog.touches_overlap; bl_view's held uses it
from bl_plan import has_scope, stale_touches  # noqa: F401 - tests read them as backlog.NAME
from bl_plan import start_approved  # noqa: F401 - test_layout reads it as backlog.start_approved

import bl_cost  # noqa: F401 - registers `cost`
import bl_dispatch  # noqa: F401 - registers `brief` and `dispatch`
import bl_procs  # noqa: F401 - registers procs
import bl_stall  # noqa: F401 - registers stalled
import bl_selfcheck  # noqa: F401 - registers `selfcheck`

# `config` reads the settings bl_base holds, which imports no bl_cli: the handler is bl_base's, registered here
bl_cli.register("config", cmd_config, help="print the project settings with each value's source")

# The usage order of the subcommands: each module registers its own when imported, and this puts them in order.
USAGE = ("new", "similar", "check", "fmt", "selectors", "list", "tree", "find", "show", "next", "held", "claim",
         "release", "answer", "set", "move", "reopen", "gate", "fire", "done", "researched", "land", "merge", "drop", "start", "precheck",
         "host-check", "close", "tidy", "horizon", "goal", "brief", "dispatch", "referrers", "cost", "red-pipeline", "intake", "procs", "stalled",
         "selfcheck", "config")
bl_cli.order(USAGE)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    root = bl_cli.root_of(argv, bl_cli.default_root(ROOT))
    load_settings(root)  # the project's settings, before a parser offers its kinds: every reader follows this root
    ap = bl_cli.build_parser(__doc__.split("\n\n")[0], root)
    a = bl_cli.parse(ap, argv)
    if a.root != root:  # an abbreviated --root the pre-scan did not read
        load_settings(a.root)
    OUTPUT_ROOT[0] = a.root
    for s in (sys.stdout, sys.stderr):  # refusals go to stderr; on Windows a pipe defaults to the ANSI code page
        s.reconfigure(encoding="utf-8")
    if a.cmd in ("horizon", "intake") and a.hook and a.opt_in and a.cmd not in setting("hooks"):
        return 0  # the plugin's entry in a project whose backlog.json leaves the hook off: nothing printed, nothing filed
    if a.cmd == "red-pipeline" and a.hook:  # async SessionStart: files a bug at most, prints nothing, never fails
        try:
            cmd_red_pipeline(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            pass
        return 0
    if a.cmd == "intake" and a.hook:  # async SessionStart: uncommitted drafts at most, prints nothing, never fails
        try:
            return hook_intake(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            return 0
    if a.cmd == "horizon" and a.hook:  # the SessionStart event on stdin carries nothing the horizon needs
        try:
            return cmd_horizon(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            return 0
    bl = Backlog(a.root)
    try:
        if getattr(a, "opt_in", False) and not a.hook:
            raise Refused("--opt-in goes with --hook")
        if a.cmd in COMMITS + ("land",):  # before the command writes anything
            if a.trailer and not getattr(a, "commit", True):
                raise Refused("--trailer goes with --commit")
            why = next(filter(None, map(trailer_problem, a.trailer)), None)
            if why:
                raise Refused(why)
        return bl_cli.handler_of(a.cmd)(bl, a)
    except KeyError as e:  # an id with no item file: a closed sprint's item is in git history
        iid = e.args[0]
        old = bl_cost.history_items(bl.root, [iid]).get(iid) if isinstance(iid, str) else None
        if old is not None and a.cmd == "show" and getattr(a, "id", None) == iid:
            print(withhold(f"{iid}: no item file (deleted, as a closed sprint's items are); its last version in git "
                           "history:"))
            print(withhold(canonical(old)), end="")
            return 0
        print(withhold(f"no item {iid}: its file was deleted (a closed sprint's item); `backlog.py show {iid}` prints "
                       "its last version" if old is not None else
                       f"no item {iid} in {rel_dir()}/ or its git history (`backlog.py find WORD` or `list` names the "
                       "items)"), file=sys.stderr)
        return 2
    except Rejected as e:
        print(withhold(str(e)), file=sys.stderr)
        return 2
    except Refused as e:
        print(withhold(str(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
