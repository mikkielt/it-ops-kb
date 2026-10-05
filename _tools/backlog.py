#!/usr/bin/env python3
"""The kb's own backlog: epics, stories, tasks, subtasks, bugs and sprints, one JSON file per item in
kb/_self/backlog/ (kb/_self/backlog.md is the runbook). Standard library only; no model, and no network except `red-pipeline` and `intake --network`.

  backlog.py new KIND --title T [--parent ID] [--sprint ID] [--priority P1|P2|P3] [--rank N] [--goal TEXT]
                 [--severity S1..S4] [--check CMD]... [--touch GLOB]... [--depends ID]... [--repro CMD]
                 [--repro-reason TEXT]
                                          a new item (KIND: epic, story, task, subtask, bug, sprint); prints its id
                                          and title. A bug's --repro must fail now, and for the defect: one that
                                          cannot start, dies of a SyntaxError in its own code, gets a usage error
                                          (argparse exit 2) or runs no tests (pytest exit 5) is refused with the
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
  backlog.py find WORD...                 the open items whose title or goal holds every word (case-insensitive), each
                                          with its parent chain; no match prints one line and exits 1
  backlog.py show ID                      one item, its parent chain, children, the knowledge state of each ask and
                                          ref of its `knowledge` and what it waits on
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
  backlog.py answer ID GATE (--answer TEXT --by operator|agent [--record] | --provisional | --confirm)
                                          record a gate's answer: --provisional takes the recommendation as the
                                          agent's answer (provisional gates only); --confirm --by operator makes an
                                          agent's answer the operator's (no --by: exit 2);
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
                 [--repro CMD] [--repro-reason T] [--severity S1..S4] [--parent ID] [--add] [--clear FIELD]...
                                          change an item after new: each list option replaces its list (--add:
                                          appends what is missing, so a second run changes nothing; for --notes,
                                          appends the text unless the notes hold it), --clear FIELD removes one.
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
  backlog.py land ID [--branch B] [--trailer 'KEY: VALUE']...
                                          land a finished item's branch (default work/ID) from a clean tree: fetch
                                          and rebase it on the integration main, then a content item: done --commit,
                                          rag.py eval and the lint when the landing changes _tools/ (stress_test.py
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
  backlog.py horizon [--sprint ID] [--hook]   how far each active sprint can go without the operator: reachable
                                          items, what waits on which gate or trigger, the critical path, the
                                          knowledge state of the next item's asks and refs (--hook runs no pack)
  backlog.py goal ID                      a /goal condition for the item: its end state, checks and scope; then
                                          the answered gates of its parent chain, which its work keeps to
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
  backlog.py intake [--file [--hook] | --status FINGERPRINT] [--network]
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
                                          drafts, never commits or pushes
  backlog.py stalled [--json]               each claimed or ready item with its stall signals (bl_stall.py), read
                                          only

claim, done, new, start and close take --commit [--trailer 'KEY: VALUE']...: after the command succeeds, commit the
item files it wrote or deleted and nothing else (`git commit --only`: what was staged before stays staged), subject
`chore(backlog): claim|done|file|start|close ID "title"`, and a last paragraph of trailers: KB-Work: <ids> (the item;
a new sprint and its review story), then each --trailer (the session's own, e.g. Co-Authored-By; a KB-* key is
refused). close's commit body is its --summary list.

--root DIR (before the command) runs against another clone. Exit: 0 ok, 1 a refused command or check errors,
2 bad arguments, an unknown id, or a refused `set` or `gate add`.

Knowledge state (show, next, horizon): one line `knowledge <state> ask|ref: <text>` per ask and per ref of an item's
`knowledge`, each run through kbfacts.pack (no network, no model) and reported as one of sufficient (coverage good, no
`check:` line), partial (weak, or good with a `check:` line), unknown (none, or a ref the kb does not hold), stale (a
fact key no longer in its file, or a source with `superseded_by` set that the ref is or cites) or conflicting (an open
`_conflicts.md` entry on its article); stale, then conflicting, override the coverage. Derived on every call, never
stored, and no part of readiness. An item without `knowledge` costs nothing: the pack is not loaded.

Every line that names an item prints its id and its title together, except a title check found holding a piece of
this host's computer or user name, which is withheld.
"""
import argparse, copy, re, shlex, subprocess, sys
from pathlib import Path

import bl_authority
import bl_check  # noqa: F401 - registers its commands
import bl_ci  # noqa: F401 - registers its commands
import bl_cli
import bl_land  # noqa: F401 - registers its commands
import bl_plan  # noqa: F401 - registers its commands
import bl_view  # noqa: F401 - registers its commands
from bl_base import (
    Backlog, COMMITS, IN_SPRINT, KINDS, OUTPUT_ROOT, PRIORITIES, RESEARCH_CHECKS, REVIEW_CHECKS, ROOT, Refused, Rejected, SEVERITIES, START_GATE, TEXT_MAX, canonical,
    commit_message, commit_written, git, in_scope, item_file, need, new_id, research_in_planned, say, scope,
    trailer_problem, waits, withhold,
)
from bl_check import (  # the checks and the readers of knowledge: bl_check holds them, backlog.py's commands use them
    ITEM_FILES_ROUTE, item_files_only, noop_warnings, text_only_repro, validate,
)
from bl_land import run_check, own_failure  # the runner of a check and the reading of a repro's own error: bl_land holds them with done, which host-check, new's repro and land share
from bl_base import RESEARCH_KINDS, research_touches  # noqa: F401 - tests read them as backlog.NAME
from bl_base import run  # noqa: F401 - tests read the real runner as backlog.run
from bl_ci import (  # noqa: F401 - the CI readers and red-pipeline: bl_ci holds them; main and ql_deliver use them as backlog.NAME
    GITLAB_FINISHED, LOG_PREFIX_RE, MAIN_PIPELINES, S1_JOBS, STATUS_REPRO, add_pipeline, bug_with_fingerprint,
    cmd_red_pipeline, failure_fingerprint, first_failure, hook_intake, names_pipeline, normalise_error_line, red_bug,
)
from bl_view import (  # noqa: F401 - the read-only views: bl_view holds them; new uses similar, main cmd_horizon, tests ready
    cmd_horizon, is_near, ready, similar,
)
from bl_base import touches_overlap  # noqa: F401 - tests read it as backlog.touches_overlap; bl_view's held uses it
from bl_plan import (  # the plan rules and start: bl_plan holds them, backlog.py's commands use them
    has_scope, host_gates, stale_touches, tracked_files,
)
from bl_base import REL_DIR  # noqa: F401 - tests read it as backlog.REL_DIR
from bl_plan import start_approved  # noqa: F401 - test_layout reads it as backlog.start_approved


# ------------------------------------------------------------------ git and checks

def parse_cmd(s):
    return shlex.split(s, posix=True)


# ------------------------------------------------------------------ commands

def cmd_new(bl, a):
    kind = a.kind
    it = {"id": new_id(kind), "kind": kind, "title": a.title.strip()}
    if kind == "sprint":
        it.update(status="planned", goal=a.goal or a.title,
                  gates=[{"id": START_GATE, "kind": "blocking",
                          "question": "Approve this sprint's goal and committed items?",
                          "options": ["approve", "change", "cancel"], "recommendation": "approve"}])
        bl.save(it)
        rv = {"id": new_id("story"), "kind": "story", "title": f"Review sprint: {it['title']}"[:TEXT_MAX],
              "status": "draft", "sprint": it["id"], "review": True, "priority": "P1", "rank": 999999,
              "goal": "Every committed item is done or dropped, provisional answers are confirmed by the operator, "
                      "and a fresh-context review of the sprint's diff found no unfiled defect.",
              "checks": REVIEW_CHECKS}
        bl.save(rv)
        rs = {"id": new_id("story"), "kind": "story", "title": f"Research sprint goal: {it['title']}"[:TEXT_MAX],
              "status": "draft", "sprint": it["id"], "goal_research": True, "priority": "P1", "rank": 0,
              "goal": "The sprint goal's open questions are answered with the kb tools first and the live docs for "
                      "the gaps, and the findings are written as kb facts and gap entries through the kb skills, so "
                      "each committed item can name the knowledge it needs.",
              "checks": RESEARCH_CHECKS, "touches": ["kb/public/**"]}
        bl.save(rs)
        say(f"new sprint {bl.label(it['id'])}, review story {bl.label(rv['id'])}, "
            f"research story {bl.label(rs['id'])}")
        commit_written(bl, a, "file", it["id"], [it["id"], rv["id"], rs["id"]])
        return 0
    if a.sprint and kind not in IN_SPRINT:
        raise Rejected(f"new {kind} refuses --sprint: only stories and bugs name a sprint; a {kind} follows its parent's")
    it.update(status="todo" if kind in ("task", "subtask") else "draft", priority=a.priority, rank=a.rank)
    for k in ("parent", "sprint", "goal"):
        if getattr(a, k):
            it[k] = getattr(a, k)
    if it["status"] == "todo" and a.parent in bl.items:  # a task of a planned sprint stays draft until its start
        sp = bl.sprint_of(a.parent)
        if bl.items.get(sp, {}).get("status") == "planned":
            it["status"] = "draft"
    if a.sprint and bl.items.get(a.sprint, {}).get("status") == "active":  # filed into a running sprint: ready now
        it["status"] = "todo"
    if kind == "bug":
        if not a.severity or not a.repro:
            raise Refused("a bug needs --severity and --repro")
        it["severity"] = a.severity
        it["repro"] = {"run": parse_cmd(a.repro)}
        ok, code, out = run_check(bl.root, it["repro"])
        if ok:
            raise Refused(f"--repro passes now (exit {code}): it must fail until the bug is fixed")
        why = own_failure(it["repro"]["run"], code, out, bl.root)
        if why:
            raise Refused(f"--repro fails for its own error, not the defect: {why}")
        why = text_only_repro(it["repro"]["run"])
        if why and not (a.repro_reason or "").strip():
            raise Rejected(f"--repro only matches text in a file ({why}): it proves the text, not the behaviour, and "
                           "can pass on a fix that does not work; run the behaviour (a test, a command on a planted "
                           "input), or state why it cannot with --repro-reason TEXT")
        if (a.repro_reason or "").strip():
            it["repro_reason"] = a.repro_reason.strip()
    elif a.repro_reason:
        raise Rejected("--repro-reason is for a bug's --repro")
    if a.check:
        it["checks"] = [{"run": parse_cmd(c)} for c in a.check]
    warns = noop_warnings(it, out if kind == "bug" else "")
    if a.touch:
        it["touches"] = a.touch
        if kind in ("story", "task", "subtask", "bug") and item_files_only(a.touch):
            warns.append(ITEM_FILES_ROUTE)
    if a.depends:
        it["depends_on"] = a.depends
    bl.save(it)
    errs = [x for x in validate(bl) if x.startswith(it["id"])]
    say(f"new {kind} {bl.label(it['id'])}")
    for x in errs:
        say(f"  to fill in: {x.split(': ', 1)[1]}")
    for x in warns:
        say(f"  warning: {x}")
    for row in filter(is_near, similar(bl, f"{it['title']} {it.get('goal', '')}", exclude={it["id"]})):
        say(f"  warning: near-duplicate of open {bl.label(row[2])} (word overlap {row[0]:.2f}); "
            "drop this one if it is the same work")
    commit_written(bl, a, "file", it["id"])
    return 0


def cmd_fmt(bl, a):
    n = 0
    for iid, it in bl.items.items():
        if bl.raw.get(iid) != canonical(it):
            bl.save(it)
            n += 1
    say(f"fmt: rewrote {n}")
    return 0


def cmd_claim(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    # a research item of a planned sprint is claimed from draft: its kb content lands before the sprint starts
    ok = ("status doing", "status draft") if research_in_planned(bl, iid) else ("status doing",)
    w = [x for x in waits(bl, iid, any_sprint=True, by=a.by) if not x.startswith(ok)]
    if w:
        raise Refused(f"{bl.label(iid)} is not ready:\n  " + "\n  ".join(w))
    if it.get("status") == "doing" and it.get("claimed_by") != a.by:
        raise Refused(f"{bl.label(iid)} is claimed by {it['claimed_by']}")
    # one session per checkout: the claims made in this working tree (its git toplevel; a worktree has its own) are
    # recorded in its own git dir, which git never commits whatever the ignore rules, and a claim by another session
    # while one of them is still doing here is refused before anything is written, so no claim commit lands on another
    # session's branch
    import json
    rev = subprocess.run(["git", "-C", str(bl.root), "rev-parse", "--show-toplevel", "--absolute-git-dir"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split("\n")
    top, gitdir = (rev + ["", ""])[:2] if len(rev) >= 2 and rev[1] else (str(bl.root), "")
    ledger = Path(gitdir) / "kb-backlog-claims.json" if gitdir else None
    try:
        here = json.loads(ledger.read_text(encoding="utf-8")) if ledger else {}
    except (OSError, ValueError):
        here = {}
    busy = sorted(i for i, by in here.items() if by != a.by and i != iid and i in bl.items
                  and bl.items[i].get("status") == "doing" and bl.items[i].get("claimed_by") == by)
    if busy:
        raise Refused(f"claim refuses {bl.label(iid)} for {a.by}: {here[busy[0]]} works in this checkout ({top}) on "
                      f"{', '.join(bl.label(i) for i in busy)}; each session works in its own worktree "
                      "(git worktree add), so its claim commits never land on another session's branch")
    it.update(status="doing", claimed_by=a.by)
    bl.save(it)
    here = {i: by for i, by in here.items() if i in bl.items and bl.items[i].get("status") == "doing"}
    here[iid] = a.by
    try:
        if ledger:
            ledger.write_text(json.dumps(here, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass  # the record guards the next claim; a checkout it cannot be written in is not refused for it
    say(f"claimed {bl.label(iid)} for {a.by}")
    commit_written(bl, a, "claim", iid)
    return 0


def cmd_release(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    if it.get("status") != "doing":
        raise Refused(f"{bl.label(iid)} is {it.get('status')}, not doing")
    it["status"] = "draft" if research_in_planned(bl, iid) else "todo"  # a planned sprint's items stay draft
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"released {bl.label(iid)}")
    return 0


def run_decide(bl, *argv):
    tool = Path(bl.root) / "_tools" / "kbdecide.py"
    p = subprocess.run([sys.executable, str(tool), *argv], cwd=str(bl.root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if p.returncode:
        raise Refused(f"--record: {(p.stdout + p.stderr).strip()}")
    return p.stdout.strip()


def record_decision(bl, iid, gate, text, by="operator"):
    """Keep a gate's answer as an active decision of kb/_self (`kbdecide.py record`, so check.py guards the write): its
    source names the item and the gate, its context is the item. Refused with kbdecide's reason."""
    argv = ["record", "--root", "_self", "--source", f"backlog item {iid} gate {gate}", "--context", f"item:{iid}",
            "--gate", gate, "--by", by, "--maker", by]
    say(run_decide(bl, *argv, "--", text))


DECISIONS_REL = "kb/_self/_decisions.csv"  # the file `kbdecide.py record` writes: --record commits it with the item file


def commit_answer(bl, a, iid, gate):
    """--record: commit what the answer wrote, as two commits so each passes `kbgit.py check-trailers` for an item that
    is not claimed: the item file (a backlog-planning commit, subject `chore(backlog): answer ID "title"`, KB-Work: the
    item, then each --trailer), then the decision row of kb/_self/_decisions.csv (no KB-Work: it is no planning commit
    and the item's scope is not its work). `git commit --only`, so what was staged before stays staged and out of both.
    A row left uncommitted would make the next `kbgit.py sync` refuse the dirty tree."""
    trailers = list(getattr(a, "trailer", None) or ())
    title = bl.items.get(iid, {}).get("title", "")
    for paths, msg in (
            ([p for p in bl.written if (bl.root / p).exists()],
             commit_message(withhold(f'chore(backlog): answer {iid} "{title}"'), [iid], trailers, f"Gate {gate}.")),
            ([DECISIONS_REL],
             "\n\n".join([withhold(f"chore(kb): decision for {iid} gate {gate}")] + (["\n".join(trailers)] if trailers else [])) + "\n")):
        git(bl.root, "add", "-A", "--", *paths)
        if not git(bl.root, "status", "--porcelain", "--", *paths).strip():
            continue
        p = subprocess.run(["git", "commit", "-q", "-F", "-", "--only", "--", *paths], cwd=bl.root, input=msg,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise Refused(f"--record: the answer and its decision are written but git commit failed: {(p.stderr or p.stdout).strip()}")
        say(f"committed {git(bl.root, 'rev-parse', '--short=10', 'HEAD').strip()} {msg.splitlines()[0]}")


def cmd_answer(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    g = next((g for g in it.get("gates", []) if g.get("id") == a.gate), None)
    if g is None:
        raise Refused(f"{bl.label(iid)} has no gate {a.gate}")
    if a.record and (a.provisional or a.confirm or a.by != "operator" or not a.answer):
        raise Rejected("--record keeps the operator's answer as a decision: --answer TEXT --by operator, never "
                       "--provisional or --confirm")
    if getattr(a, "trailer", None):
        if not a.record:
            raise Refused("--trailer goes with --record")
        why = next(filter(None, map(trailer_problem, a.trailer)), None)
        if why:
            raise Refused(why)
    members = [bl.items[i] for i in bl.sprint_items(iid)] if it.get("kind") == "sprint" else []
    scope = bl_authority.sprint_scope(it, g, members)
    if a.confirm and not a.by:
        raise Rejected(f"gate {a.gate} of {bl.label(iid)}: --confirm needs --by operator, which an agent passes only "
                       "after the operator said so")
    if a.by != "operator" and (a.by or a.provisional):
        cls = bl_authority.derived_class(scope, g)
        if cls in bl_authority.OPERATOR_CLASSES:
            refuse = Rejected if a.provisional or a.confirm else Refused  # --answer by an agent: exit 1, as a blocking gate
            raise refuse(f"gate {a.gate} of {bl.label(iid)} is class {cls}: only the operator answers it "
                         "(--by operator)")
    if a.confirm:
        if g.get("by") != "agent":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} has no agent answer to confirm")
        g["by"] = "operator"
    elif a.provisional:
        if g["kind"] != "provisional":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} is blocking: only the operator answers it")
        g.update(answer=g["recommendation"], by="agent")
    else:
        if not a.answer or not a.by:
            raise Refused("--answer TEXT and --by operator|agent")
        if g["kind"] == "blocking" and a.by != "operator":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} is blocking: only the operator answers it")
        g.update(answer=a.answer, by=a.by)
        if a.record:
            record_decision(bl, iid, a.gate, a.answer, a.by)
    bl.save(it)
    say(f"gate {a.gate} of {bl.label(iid)}: {g['answer']} (by {g['by']})")
    if a.record:
        commit_answer(bl, a, iid, a.gate)
    return 0


def changed_item(bl, iid, edit):
    """Apply `edit` to a copy of the item and write it when the copy differs and validates as `check` does: no error
    that was not there before (this item's, or another's that a dependency cycle or a review story's sprint would
    add). Returns True when it wrote the file, False when the edit leaves the item as it is; raises Rejected with the
    new errors and the item untouched."""
    return changed_items(bl, {iid: edit})


def changed_items(bl, edits):
    """`changed_item` for several items at once ({id: edit}): the copies are validated together, so either every
    changed item is written or none is. Returns True when it wrote any file."""
    olds = {i: bl.items[i] for i in edits}
    news = {}
    for i, edit in edits.items():
        news[i] = copy.deepcopy(olds[i])
        edit(news[i])
    news = {i: n for i, n in news.items() if canonical(n) != canonical(olds[i])}
    if not news:
        return False
    before = set(validate(bl) + stale_touches(bl))
    raws = {i: bl.raw[i] for i in news}
    for i, n in news.items():
        bl.items[i], bl.raw[i] = n, canonical(n)
    try:
        fresh = [x for x in validate(bl) + stale_touches(bl) if x not in before]
    finally:
        for i in news:
            bl.items[i], bl.raw[i] = olds[i], raws[i]
    if fresh:
        raise Rejected(f"{', '.join(bl.label(i) for i in news)} unchanged: the change would make `check` fail:\n  "
                       + "\n  ".join(fresh))
    for n in news.values():
        bl.save(n)
    return True


SET_LISTS = ("links", "touches", "checks", "depends_on", "relates_to")
SET_FIELDS = ("notes", "priority", "rank", "sprint", "title", "goal", "repro", "repro_reason", "severity",
              "parent") + SET_LISTS  # what set changes; the others are refused
SET_REFUSED = {  # a field set refuses, with the rule it states
    "status": "changes only through claim, release, start, close, drop and done",
    "claimed_by": "changes only through claim and release",
    "evidence": "is written only by done",
    "id": "is the item's identity",
    "kind": "is the item's identity",
    "gates": "changes through gate add and answer",
}


def set_refusal(field):
    """The rule that refuses `set` the field, or None when set changes it."""
    if field in SET_FIELDS:
        return None
    return f"set refuses {field}: it {SET_REFUSED.get(field, 'is not a field set changes')}"


def appended(old, values):
    """`old` with each of `values` it lacks added at the end, in order."""
    return old + [v for i, v in enumerate(values) if v not in old and v not in values[:i]]


def reclass_gate(item, gate):
    """Store the stricter of the gate's class and the one `item`'s touches and the gate's text derive now, so widened
    touches re-class a gate already written; a class never goes down here. An unanswered provisional gate that
    becomes one only the operator answers is made blocking, as `gate add` does."""
    stored = gate.get("class")
    d = bl_authority.derived_class(item, gate)
    if stored not in bl_authority.CLASSES or bl_authority.rank(d) < bl_authority.rank(stored):
        gate["class"] = d
    if bl_authority.gate_class(item, gate) in bl_authority.OPERATOR_CLASSES and gate.get("kind") != "blocking" \
            and "answer" not in gate:
        gate["kind"] = "blocking"


def cmd_set(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    for f in SET_REFUSED:
        if getattr(a, "no_" + f, None) is not None:
            raise Rejected(set_refusal(f))
    for f in a.clear:
        if set_refusal(f):
            raise Rejected(set_refusal(f))
    given = {"notes": a.notes, "priority": a.priority, "rank": a.rank, "sprint": a.sprint}
    given.update({f: getattr(a, f) for f in ("title", "goal", "repro", "repro_reason", "severity", "parent")})
    given.update({f: getattr(a, f) for f in SET_LISTS})
    given = {f: v for f, v in given.items() if v is not None}
    both = sorted(set(given) & set(a.clear))
    if both:
        raise Rejected(f"set: {', '.join(both)} given a value and --clear together")
    if not given and not a.clear:
        raise Rejected("set: nothing to change: name a field (" + ", ".join(SET_FIELDS) + ")")
    named = sorted(set(given) | set(a.clear))
    if it.get("kind") == "sprint" and set(named) - {"notes", "links"}:
        raise Rejected(f"set refuses {', '.join(sorted(set(named) - {'notes', 'links'}))} on a sprint: "
                       "a sprint takes notes and links only")
    if it.get("status") == "done" and {"checks", "touches", "goal", "repro", "repro_reason"} & set(named):
        raise Rejected(f"set refuses {', '.join(sorted({'checks', 'touches', 'goal', 'repro', 'repro_reason'} & set(named)))} "
                       f"on {bl.label(iid)}: it is done, and its evidence proves the goal, repro, checks and touches it had")
    if "title" in given:
        given["title"] = given["title"].strip()
        if not given["title"]:
            raise Rejected("set: --title is empty")
    if {"repro", "repro_reason", "severity"} & set(named) and it.get("kind") != "bug":
        raise Rejected(f"set refuses {', '.join(sorted({'repro', 'repro_reason', 'severity'} & set(named)))} on "
                       f"{bl.label(iid)}: only a bug has a repro and a severity")
    if {"repro", "severity"} & set(a.clear):
        raise Rejected("set refuses --clear repro or severity: a bug needs both")
    if "parent" in given and given["parent"] not in bl.items:
        raise Rejected(f"set refuses parent {given['parent']} for {bl.label(iid)}: no such item")
    if "repro" in given:  # as new bug: a command that fails now, for the defect, not for its own error
        try:
            given["repro"] = {"run": parse_cmd(given["repro"])}
        except ValueError as e:
            raise Rejected(f"set: --repro is not a command line ({e})") from e
        ok, code, out = run_check(bl.root, given["repro"])
        if ok:
            raise Refused(f"--repro passes now (exit {code}): it must fail until the bug is fixed")
        why = own_failure(given["repro"]["run"], code, out, bl.root)
        if why:
            raise Refused(f"--repro fails for its own error, not the defect: {why}")
    if "repro_reason" in given:
        given["repro_reason"] = given["repro_reason"].strip()
    if {"repro", "repro_reason"} & set(named):
        run = (given.get("repro") or it.get("repro") or {}).get("run") or []
        reason = "" if "repro_reason" in a.clear else given.get("repro_reason", it.get("repro_reason", ""))
        why = text_only_repro(run) if run else None
        if why and not reason:
            raise Rejected(f"--repro only matches text in a file ({why}): run the behaviour (a test, a command on a "
                           "planted input), or state why it cannot with --repro-reason TEXT")
    if a.sprint is not None and bl.items.get(a.sprint, {}).get("status") == "active" and it.get("status") == "draft":
        raise Rejected(f"set refuses sprint {a.sprint} for {bl.label(iid)}: the sprint is active and the item is "
                       "draft, so it would never be ready")
    if "checks" in given:
        try:
            given["checks"] = [{"run": parse_cmd(c)} for c in given["checks"]]
        except ValueError as e:
            raise Rejected(f"set: --check is not a command line ({e})") from e

    def edit(new):
        for f, v in given.items():
            if f in SET_LISTS and a.add:
                new[f] = appended(new.get(f, []) if isinstance(new.get(f, []), list) else [], v)
            elif f == "notes" and a.add:
                old = new.get("notes", "")
                new[f] = old if v in old else f"{old} {v}".strip()
            else:
                new[f] = v
        for f in a.clear:
            new.pop(f, None)
        if "touches" in given or "touches" in a.clear:  # new touches may put a gate in a stricter class: store it
            for g in new.get("gates", []) or []:
                reclass_gate(new, g)

    if changed_item(bl, iid, edit):
        say(f"set {bl.label(iid)}: {', '.join(named)}")
    else:
        say(f"set {bl.label(iid)}: unchanged")
    return 0


def cmd_move(bl, a):
    """move: a story's or bug's sprint, with the status that sprint's state gives it and its tasks."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    label = bl.label(iid)
    target = None if a.sprint == "none" else a.sprint
    if it.get("kind") not in IN_SPRINT:
        raise Rejected(f"move refuses {label}: only a story or a bug names a sprint; its tasks and subtasks follow it, "
                       "so move the story or bug above it")
    if it.get("review"):
        raise Rejected(f"move refuses {label}: a sprint needs exactly one review story, and this is its own")
    st = it.get("status")
    if st == "done":
        raise Rejected(f"move refuses {label}: it is done; reopen it first (backlog.py reopen ID --why TEXT)")
    if st == "dropped":
        raise Rejected(f"move refuses {label}: it is dropped, and a dropped item has no sprint to change")
    kids = bl.descendants(iid)
    claimed = [i for i in [iid] + kids if bl.items[i].get("status") == "doing"]
    if claimed:
        raise Rejected(f"move refuses {label}: {', '.join(bl.label(i) for i in claimed[:5])} is doing (claimed); "
                       "release it first, since a claimed item is in the middle of work")
    if target is not None:
        sp = bl.items.get(target)
        if sp is None:
            raise Rejected(f"move refuses sprint {target} for {label}: sprint {target} does not exist")
        if sp.get("kind") != "sprint":
            raise Rejected(f"move refuses {target} for {label}: it is not a sprint")
    state = "todo" if target is not None and bl.items[target].get("status") == "active" else "draft"
    if state == "todo" and not has_scope(bl, iid):
        raise Rejected(f"move refuses sprint {target} for {label}: the sprint is active and the item has no touches "
                       "(and no tasks that all have them), which start requires of every work item")

    def edit_story(new):
        if target is None:
            new.pop("sprint", None)
        else:
            new["sprint"] = target
        new["status"] = state

    def edit_child(new):
        new["status"] = state

    edits = {iid: edit_story}
    edits.update({c: edit_child for c in kids if bl.items[c].get("status") in ("draft", "todo")})
    if changed_items(bl, edits):
        say(f"moved {label} to {bl.label(target) if target else 'no sprint'}: status {state}"
            + (f", {len(edits) - 1} task(s) and subtask(s) follow" if len(edits) > 1 else ""))
    else:
        say(f"move {label}: unchanged")
    return 0


def cmd_reopen(bl, a):
    """reopen: a done item back to work, its evidence and claim cleared; the reason is printed, never stored."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    label = bl.label(iid)
    if not a.why.strip():
        raise Rejected("reopen: --why TEXT must not be empty")
    if it.get("kind") == "sprint":
        raise Rejected(f"reopen refuses {label}: a sprint has no done status")
    if it.get("status") != "done":
        raise Rejected(f"reopen refuses {label}: it is {it.get('status')}; reopen takes only a done item back to work "
                       "(a draft, todo or doing item is open already, and a dropped one is not reopened: file a new item)")
    sp = bl.sprint_of(iid)
    state = "draft" if sp in bl.items and bl.items[sp].get("status") == "planned" else "todo"

    def edit(new):
        new["status"] = state
        new.pop("evidence", None)
        new.pop("claimed_by", None)

    changed_item(bl, iid, edit)
    say(f"reopened {label}: status {state}, evidence and claim cleared. Why: {a.why.strip()}")
    return 0


GATE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
CAPPED_FILE_RE = re.compile(r"\b(?:AGENTS|README)\.md\b")
SIZE_WORD_RE = re.compile(r"\b(?:cap|capped|bytes|size|limit)\b", re.I)
MEASURED_SIZE_RE = re.compile(r"\b\d[\d,]*\s*bytes\b", re.I)


def cmd_gate(bl, a):
    """gate add: a gate with its question, options and recommendation."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    if it.get("status") in ("done", "dropped"):
        raise Rejected(f"gate add refuses {bl.label(iid)}: it is {it['status']}, so a gate would wait on nothing")
    options = [o.strip() for o in a.option]
    if len(options) < 2 or len(set(options)) != len(options) or not all(options):
        raise Rejected("gate add: --option twice or more, each different and not empty")
    if a.recommendation.strip() not in options:
        raise Rejected("gate add: --recommendation must be one of the --option values")
    about = " ".join([a.question, *options])
    if CAPPED_FILE_RE.search(about) and SIZE_WORD_RE.search(about):
        bare = [o for o in options if not MEASURED_SIZE_RE.search(o)]
        if bare:  # a size cap: the operator is asked once, on each option's measured result
            raise Rejected("gate add: the gate is about a capped file (AGENTS.md, README.md), so each --option states "
                           f"the file's measured size after it (`wc -c`, as 'N bytes'); without one: {', '.join(bare)}")
    gates = it.get("gates", [])
    gid = a.gate_id or next(f"g{n}" for n in range(1, len(gates) + 2) if f"g{n}" not in {g.get("id") for g in gates})
    if not GATE_ID_RE.fullmatch(gid) or gid == START_GATE:
        raise Rejected(f"gate add: the gate id {gid!r} must be lowercase letters, digits and hyphens (at most 40), "
                       f"and not {START_GATE!r}, the sprint's own")
    gate = {"id": gid, "kind": a.kind, "question": a.question.strip(), "options": options,
            "recommendation": a.recommendation.strip()}
    gate["class"] = bl_authority.derived_class(it, gate)
    if gate["class"] in bl_authority.OPERATOR_CLASSES and gate["kind"] != "blocking":
        gate["kind"] = "blocking"
        say(f"gate {gid} of {bl.label(iid)} is class {gate['class']}: made blocking, only the operator answers it")
    if a.do:
        gate["do"] = {}
        for d in a.do:
            opt, sep, how = d.partition("=")
            opt, how = opt.strip(), how.strip()
            if not sep or opt not in options or not how:
                raise Rejected("gate add: --do OPTION=COMMAND, OPTION one of the --option values")
            gate["do"][opt] = how if how in bl.items else parse_cmd(how)
            if not gate["do"][opt]:
                raise Rejected("gate add: --do needs a command or an item id after the =")
    if a.host_check:
        gate["host_check"] = {"run": parse_cmd(a.host_check)}
        if not gate["host_check"]["run"]:
            raise Rejected("gate add: --host-check needs a command")
    same = [g for g in gates if g.get("question") == gate["question"] or g.get("id") == gid]
    if same:
        known = same[0]
        if len(same) > 1 or any(known.get(k) != v for k, v in gate.items() if k not in ("id", "class")) \
                or (a.gate_id and known.get("id") != gid):  # an answer it already has does not make it different
            raise Rejected(f"gate add refuses a different gate with the question or id of gate {known.get('id')} "
                           f"of {bl.label(iid)}: it already has one (its answer is not overwritten)")
        say(f"gate {known.get('id')} of {bl.label(iid)}: unchanged")
        return 0

    def edit(new):
        new["gates"] = list(new.get("gates", [])) + [gate]

    changed_item(bl, iid, edit)
    say(f"gate {gid} ({gate['kind']}) added to {bl.label(iid)}: {gate['question']}")
    return 0


def cmd_host_check(bl, a):
    """host-check: run, on this host, the check of each answered gate that names a host setup; record the result."""
    sid = need(bl, a.sprint)
    if bl.items[sid].get("kind") != "sprint":
        raise Refused(f"{bl.label(sid)} is not a sprint")
    rows = host_gates(bl, sid)
    if not rows:
        say(f"{bl.label(sid)}: no answered gate names a host setup")
        return 0
    results, failed = {}, []
    for iid, g in rows:
        ok, code, out = run_check(bl.root, g["host_check"])
        results[(iid, g["id"])] = {"ok": ok, "exit": code}
        say(f"{'ok' if ok else 'FAILED'} {bl.label(iid)} gate {g['id']} ({g['answer']}): "
            f"{shlex.join(g['host_check']['run'])} exited {code}")
        if not ok:
            failed.append(f"{bl.label(iid)} gate {g['id']}: {g['question']}\n    " + "\n    ".join(out.strip().splitlines()[-5:]))

    def edits(iid):
        def edit(new):
            for g in new["gates"]:
                if (iid, g["id"]) in results:
                    g["host_checked"] = results[(iid, g["id"])]
        return edit

    changed_items(bl, {i: edits(i) for i in {i for i, _ in results}})
    if failed:
        say("host setup does not hold on this host:\n  " + "\n  ".join(failed))
        return 1
    return 0


def cmd_fire(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    if not it.get("trigger"):
        raise Refused(f"{bl.label(iid)} has no trigger")
    it["trigger"]["fired"] = True
    bl.save(it)
    say(f"trigger fired on {bl.label(iid)}: {it['trigger']['when']}")
    return 0


def cmd_drop(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    live = [c for c in bl.descendants(iid) if bl.items[c].get("status") not in ("done", "dropped")]
    if live:
        raise Refused(f"{bl.label(iid)} has open children: " + ", ".join(bl.label(c) for c in live[:5]))
    users = [i for i, x in bl.items.items() if iid in x.get("depends_on", []) and x.get("status") != "dropped"]
    if users:
        raise Refused(f"{bl.label(iid)} is a dependency of " + ", ".join(bl.label(u) for u in users[:5]))
    # a dropped item that depended on this one keeps no link to it: check reports a dependency on a dropped item
    for i, x in bl.items.items():
        if x.get("status") == "dropped" and iid in x.get("depends_on", []):
            left = [d for d in x["depends_on"] if d != iid]
            if left:
                x["depends_on"] = left
            else:
                x.pop("depends_on")
            bl.save(x)
    if not bl.sprint_of(iid):
        label = bl.label(iid)
        for d in bl.descendants(iid):
            bl.delete(d)
        bl.delete(iid)
        say(f"dropped and deleted {label} (not in a sprint; git keeps it): {a.why}")
        return 0
    it.update(status="dropped", notes=(it.get("notes", "") + " Dropped: " + a.why).strip()[:TEXT_MAX])
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"dropped {bl.label(iid)}: {a.why}")
    return 0


def referrer_patterns(term, files):
    """The patterns that name term: a tracked file by its path and its file name, word-bounded (a .py file's name is
    <stem>.py, and it is also named by an import line that holds its module name: `import stem`, `from stem import`),
    any other term as a symbol, word-bounded. The bare module name alone is no reference: prose and items say the
    word (`backlog`) without naming the file."""
    if term in files:
        name = Path(term).name
        pats = [re.compile(re.escape(term)), re.compile(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])")]
        if term.endswith(".py"):
            pats.append(re.compile(r"^\s*(?:from|import)\s.*\b" + re.escape(Path(term).stem) + r"\b"))
        return pats
    return [re.compile(r"(?<![\w])" + re.escape(term) + r"(?![\w])")]


def referrers_of(root, term, files):
    """(path, first line number, matching line count) of each tracked text file other than term itself that names it.
    Backlog item files are left out: an item naming the path in its touches is check's stale-touches error once the
    file moves, and an item's prose only says the word."""
    pats = referrer_patterns(term, files)
    out = []
    for f in files:
        path = Path(root) / f
        if f == term or item_file(f) or not path.is_file() or path.stat().st_size > 4_000_000:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        hit = [n for n, ln in enumerate(lines, 1) if any(p.search(ln) for p in pats)]
        if hit:
            out.append((f, hit[0], len(hit)))
    return out


def cmd_referrers(bl, a):
    """Every tracked file that names a file or symbol a task will move or delete: one line per file with its first
    line and its count of lines, read-only. --item ID marks each file outside the item's scope (its touches and its
    descendants') and exits 1 when there is one, so the touches hold them before the work starts."""
    files = tracked_files(bl.root)
    globs = scope(bl, need(bl, a.item)) if a.item else None
    stray = 0
    for term in a.terms:
        rows = referrers_of(bl.root, term, files)
        for f, first, n in rows:
            out = bool(globs is not None and not in_scope(f, globs))
            stray += out
            say(f"{term}  {f}:{first}  {n} line{'s' * (n != 1)}" + ("  outside touches" if out else ""))
        if not rows:
            say(f"{term}  no tracked file names it")
    return 1 if stray else 0


def cmd_goal(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    parts = [f"{bl.label(iid)} is done: {it.get('goal', it['title'])}"]
    for c in it.get("checks", []) + ([it["repro"]] if it.get("repro") else []):
        parts.append(f"`{shlex.join(c['run'])}` exits {c.get('exit', 0)}"
                     + (f" with output matching {c['match']!r}" if c.get("match") else ""))
    parts.append(f"`python3 _tools/backlog.py done {iid}` exits 0 and its output is shown")
    globs = scope(bl, iid)
    if globs:
        parts.append("no commit for it changes a file outside " + ", ".join(globs))
    say(", ".join(parts) + ", or stop after 60 turns")
    above = [(x, g) for x in bl.ancestors(iid) for g in bl.items[x].get("gates", []) or [] if g.get("answer")]
    if above:  # a brief built from the goal must not contradict an answer given above the item
        say("answered gates above it, which its work keeps to:")
        for x, g in above:
            by = g.get("by") or "?"
            say(f"  {bl.label(x)} {g['id']}: {g.get('question', '')} -> {g['answer']} (by {by}"
                + (", provisional" if g.get("provisional") else "") + ")")
    return 0


def args_new(p):
    p.add_argument("kind", choices=list(KINDS))
    p.add_argument("--title", required=True)
    p.add_argument("--parent")
    p.add_argument("--sprint")
    p.add_argument("--priority", choices=PRIORITIES, default="P2")
    p.add_argument("--rank", type=int, default=0)
    p.add_argument("--goal")
    p.add_argument("--severity", choices=SEVERITIES)
    p.add_argument("--check", action="append")
    p.add_argument("--touch", action="append")
    p.add_argument("--depends", action="append")
    p.add_argument("--repro")
    p.add_argument("--repro-reason", help="why a repro that only matches text in a file cannot run the behaviour")


def args_claim(p):
    p.add_argument("id")
    p.add_argument("--by", required=True)


def args_release(p):
    p.add_argument("id")


def args_answer(p):
    p.add_argument("id")
    p.add_argument("gate")
    p.add_argument("--answer")
    p.add_argument("--by", choices=("operator", "agent"))
    p.add_argument("--provisional", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--record", action="store_true", help="with --answer TEXT --by operator: keep the answer as an active decision, committed with the item file")
    p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                   help="a trailer of the session's own after KB-Work in the --record commit (repeatable)")


def args_set(p):
    p.add_argument("id")
    p.add_argument("--notes")
    p.add_argument("--link", dest="links", action="append")
    p.add_argument("--touch", dest="touches", action="append")
    p.add_argument("--check", dest="checks", action="append")
    p.add_argument("--depends", dest="depends_on", action="append")
    p.add_argument("--relates", dest="relates_to", action="append")
    p.add_argument("--priority")
    p.add_argument("--rank", type=int)
    p.add_argument("--sprint")
    p.add_argument("--title", help="the item's title")
    p.add_argument("--goal", help="the goal, replaced whole (refused on a done item)")
    p.add_argument("--repro", help="a bug's repro command, which must fail now as new bug's does (refused on a done item)")
    p.add_argument("--repro-reason", dest="repro_reason", help="why a bug's repro can only match text in a file")
    p.add_argument("--severity", choices=SEVERITIES, help="a bug's severity")
    p.add_argument("--parent", help="the item's parent, by the same kind rules check applies")
    p.add_argument("--add", action="store_true", help="append to a list (or to the notes) instead of replacing it")
    p.add_argument("--clear", action="append", default=[], metavar="FIELD", help="remove a field (repeatable)")
    for f in SET_REFUSED:  # accepted only to be refused with the rule that applies
        p.add_argument("--" + f.replace("_", "-"), dest="no_" + f, help=argparse.SUPPRESS)


def args_move(p):
    p.add_argument("id")
    p.add_argument("--sprint", required=True, metavar="SP|none")


def args_reopen(p):
    p.add_argument("id")
    p.add_argument("--why", required=True)


def args_gate(p):
    gsub = p.add_subparsers(dest="verb", required=True)
    p = gsub.add_parser("add")
    p.add_argument("id")
    p.add_argument("--question", required=True)
    p.add_argument("--option", action="append", required=True, help="an answer the operator may give (repeatable)")
    p.add_argument("--recommendation", required=True, help="the option the agent recommends")
    p.add_argument("--kind", default="blocking", help="blocking (default) or provisional")
    p.add_argument("--id", dest="gate_id", help="the gate's id (default g1, g2, ...)")
    p.add_argument("--do", action="append", metavar="OPTION=CMD|ID",
                   help="the command that carries OPTION out, or the id of the item whose work adds it (repeatable)")
    p.add_argument("--host-check", help="a command that exits 0 when the host setup the answer names holds here")


def args_fire(p):
    p.add_argument("id")


def args_drop(p):
    p.add_argument("id")
    p.add_argument("--why", required=True)


def args_host_check(p):
    p.add_argument("sprint")


def args_goal(p):
    p.add_argument("id")


def args_referrers(p):
    p.add_argument("terms", nargs="+", help="a tracked file path or a symbol a task will move or delete")
    p.add_argument("--item", help="mark the files outside this item's scope (touches and its descendants')")


bl_cli.register("new", cmd_new, args_new)
bl_cli.register("fmt", cmd_fmt)
bl_cli.register("claim", cmd_claim, args_claim)
bl_cli.register("release", cmd_release, args_release)
bl_cli.register("answer", cmd_answer, args_answer)
bl_cli.register("set", cmd_set, args_set)
bl_cli.register("move", cmd_move, args_move)
bl_cli.register("reopen", cmd_reopen, args_reopen)
bl_cli.register("gate", cmd_gate, args_gate)
bl_cli.register("fire", cmd_fire, args_fire)
bl_cli.register("drop", cmd_drop, args_drop)
bl_cli.register("host-check", cmd_host_check, args_host_check)
bl_cli.register("goal", cmd_goal, args_goal)
bl_cli.register("referrers", cmd_referrers, args_referrers)
import bl_cost  # noqa: F401 - registers `cost`
import bl_procs  # noqa: F401 - registers procs
import bl_stall  # noqa: F401 - registers stalled
import bl_selfcheck  # noqa: F401 - registers `selfcheck`

# The usage order of the subcommands: each module registers its own when imported, and this puts them in order.
USAGE = ("new", "similar", "check", "fmt", "selectors", "list", "tree", "find", "show", "next", "held", "claim",
         "release", "answer", "set", "move", "reopen", "gate", "fire", "done", "land", "merge", "drop", "start", "precheck",
         "host-check", "close", "tidy", "horizon", "goal", "referrers", "cost", "red-pipeline", "intake", "procs", "stalled",
         "selfcheck")
bl_cli.order(USAGE)


def main(argv=None):
    ap = bl_cli.build_parser(__doc__.split("\n\n")[0], str(ROOT))
    a = ap.parse_args(argv)
    OUTPUT_ROOT[0] = a.root
    for s in (sys.stdout, sys.stderr):  # refusals go to stderr; on Windows a pipe defaults to the ANSI code page
        s.reconfigure(encoding="utf-8")
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
        if a.cmd in COMMITS + ("land",):  # before the command writes anything
            if a.trailer and not getattr(a, "commit", True):
                raise Refused("--trailer goes with --commit")
            why = next(filter(None, map(trailer_problem, a.trailer)), None)
            if why:
                raise Refused(why)
        return bl_cli.handler_of(a.cmd)(bl, a)
    except KeyError as e:
        print(withhold(f"no item {e.args[0]}"), file=sys.stderr)
        return 2
    except Rejected as e:
        print(withhold(str(e)), file=sys.stderr)
        return 2
    except Refused as e:
        print(withhold(str(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
