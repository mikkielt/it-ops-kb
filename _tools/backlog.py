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
                                          printed); warns of an open bug whose repro only matches text in a
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
  backlog.py answer ID GATE (--answer TEXT --by operator|agent|autopilot [--record] | --provisional | --confirm)
                                          record a gate's answer: --provisional takes the recommendation as the
                                          agent's answer (provisional gates only); --confirm --by operator makes an
                                          agent's answer the operator's (no --by: exit 2);
                                          --record (with --by operator) also writes it as an active
                                          decision of kb/_self through kbdecide.py, its context the item (exit 2 with
                                          --provisional, --confirm or a --by other than operator or autopilot);
                                          a gate of class secrets or push takes
                                          an answer only with --by operator (--provisional, --confirm included);
                                          --by autopilot answers any gate but one of class secrets or push (exit 2,
                                          the item unchanged) and --record then writes the decision with maker
                                          autopilot and a review_by, which an operator's answer supersedes
  backlog.py set ID [--notes TEXT] [--link T]... [--touch GLOB]... [--check CMD]... [--depends ID]...
                 [--relates ID]... [--priority P1|P2|P3] [--rank N] [--sprint ID] [--add] [--clear FIELD]...
                                          change an item after new: each list option replaces its list (--add:
                                          appends what is missing, so a second run changes nothing; for --notes,
                                          appends the text unless the notes hold it), --clear FIELD removes one.
                                          The result is validated as check does and written only when it adds no
                                          error; status, claimed_by, evidence, id, kind, parent, title and the
                                          fields set does not name are refused, a sprint takes notes and links
                                          only, and a done item keeps its checks and touches (its evidence proves
                                          them); exit 2 for each refusal, the item file unchanged
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
                                          stress_test.py, rag.py eval and the lint when the landing changes _tools/,
                                          kbgit.py sync --push; an item with a code-lane commit not on that main:
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
  backlog.py close SPRINT [--summary]     delete a finished sprint, its items and the epics they finished
                                          (--summary: only list each of them with its status and the commit done
                                          recorded, the close commit's body, and change nothing; with --commit
                                          refused)
  backlog.py horizon [--sprint ID] [--hook]   how far each active sprint can go without the operator: reachable
                                          items, what waits on which gate or trigger, the critical path, the
                                          knowledge state of the next item's asks and refs (--hook runs no pack)
  backlog.py goal ID                      a /goal condition for the item: its end state, checks and scope
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
                                          second run files nothing. --status FP: exit 1 while a detector still reports
                                          that fingerprint (or one cannot run), 0 once none does; the repro of every bug
                                          intake files. Exit 1 also when a detector failed, 2 for a bad fingerprint
                                          or --status with --file. --hook (the async SessionStart form, run as
                                          --file --hook, offline): silent, exit 0 always, runs drift after the other
                                          detectors, stops waiting for them after
                                          INTAKE_HOOK_BUDGET_S and files what the finished ones found, as uncommitted
                                          drafts, never commits or pushes
  backlog.py stalled [--json | --ladder | --took ID SIGNAL REMEDY]
                                          each claimed or ready item with its stall signals and the next remedy of
                                          the ladder (bl_stall.py); --took records a remedy taken as an ops row and
                                          an autopilot decision
  backlog.py bounds [report | stop | file] [--sprint SP] [--budget K --landed N] [--json]
                                          the limits of the autopilot's work (bl_bounds.py): the report counts
                                          findings per sprint, open drafts, draft inflow against the done outflow of
                                          the last sprints and each item's rework; `stop` says whether the manager
                                          stops (sprint-budget, inflow-guard or no-ready; exit 1 when it does);
                                          `file --origin review|retro|mid-sprint --sprint SP --title T --goal G
                                          --evidence commit:SHA|test:ID|ops:ID [--kind story|bug --severity S
                                          --repro CMD --check CMD --touch GLOB]` files a finding as a draft, merges
                                          it into a near-duplicate's notes, or keeps it for the close commit body

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
import argparse, copy, csv, json, os, re, shlex, subprocess, sys, threading
from pathlib import Path

import bl_authority
import bl_check
import bl_cli
import bl_intake
import bl_land
import bl_plan
from bl_base import (
    Backlog, COMMITS, IN_SPRINT, KINDS, OPEN, OUTPUT_ROOT, PRIORITIES,
    REL_DIR, RESEARCH_CHECKS, REVIEW_CHECKS, ROOT, Refused, Rejected, SEVERITIES, SIMILAR_MIN, SIMILAR_SHOWN,
    SIMILAR_WORDS, STARTS, START_GATE, STOP_WORDS, TEXT_MAX, canonical, commit_written, git, in_scope,
    line, need, new_id, open_gates, research_in_planned, run, say, scope, trailer_problem, waits, withhold,
)
from bl_check import (  # the checks and the readers of knowledge: bl_check holds them, backlog.py's commands use them
    knowledge_lines, noop_warnings, text_only_repro, validate,
)
from bl_land import run_check  # the runner of a check: bl_land holds it with done, which host-check and new's repro share
from bl_base import RESEARCH_KINDS, research_touches  # noqa: F401 - kg_trailers reads them as backlog.NAME
from bl_base import touches_overlap  # bl_base holds it: held --overlaps and start's runner check share it
from bl_plan import (  # the plan rules and start: bl_plan holds them, backlog.py's commands use them
    has_scope, host_gates, stale_touches, start_approved, tracked_files, where_outside,
)


# ------------------------------------------------------------------ readiness

def ready(bl, sprint=None, any_sprint=False):
    ids = [i for i in bl.items if not waits(bl, i, any_sprint)
           and (sprint is None or bl.sprint_of(i) == sprint)]
    return sorted(ids, key=bl.order_key)


# ------------------------------------------------------------------ near-duplicates and recurring work

def words(text):
    """The words similar compares: lowercased runs of letters and digits, stop words and single characters left out."""
    return {w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if len(w) > 1 and w not in STOP_WORDS}


def similar(bl, text, exclude=()):
    """Open items ranked by word overlap with text: (score, shared count, id) for each item that shares a word, the
    score the share of text's words found in the item's title and goal; highest first, then most shared, then id."""
    q = words(text)
    out = []
    for iid, it in bl.items.items():
        if iid in exclude or it.get("kind") == "sprint" or it.get("status") not in OPEN:
            continue
        shared = q & words(f"{it.get('title', '')} {it.get('goal', '')}")
        if shared:
            out.append((round(len(shared) / len(q), 2), len(shared), iid))
    return sorted(out, key=lambda r: (-r[0], -r[1], r[2]))


def is_near(row):
    return row[0] >= SIMILAR_MIN and row[1] >= SIMILAR_WORDS


# ------------------------------------------------------------------ git and checks

SYNTAX_ERROR = re.compile(r"(SyntaxError|IndentationError|TabError)\b")
FRAME = re.compile(r'File "([^"]*)", line \d+')
NOT_FOUND = re.compile(r"is not recognized as an internal or external command"
                       r"|^\S+: (line \d+: )?\S+: command not found$", re.M)


def own_code(argv, path):
    """True when a frame's file is the repro's own code: the -c string, or the script python runs (argv[1])."""
    if path == "<string>":
        return True
    script = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else None
    if not script:
        return False
    p, s = (os.path.normcase(os.path.normpath(x)) for x in (path, script))
    return p == s or p.endswith(os.sep + s)


def own_failure(argv, code, out):
    """Why a failing repro failed for its own error rather than the defect, or None when its failure may be the
    defect's: it cannot start (not found; exit 127 or 9009, or a shell's or python -m's lone not-found message);
    Python cannot compile its own code (a
    SyntaxError in the -c string or the script it names, before anything is tested); the tool it runs rejects its
    arguments (argparse's exit 2 with usage: and error:); or a pytest run selected no tests (exit 5, or no tests ran).
    A failed assertion, a traceback from the code under test or a finding with exit 1 is a failure it accepts."""
    lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    last = lines[-1][:200] if lines else ""
    alone = len(lines) <= 3  # a shell's or interpreter's one message, not a tool's output that mentions one
    if ((code is None and out.startswith("cannot start")) or code in (127, 9009)
            or (alone and NOT_FOUND.search(out)) or (alone and argv[1:2] == ["-m"] and "No module named " in out)):
        msg = next((ln[:200] for ln in lines if NOT_FOUND.search(ln) or "No module named " in ln), last)
        return f"the command cannot start ({msg or f'exit {code}'})"
    if code is None:
        return None
    for i, ln in enumerate(lines):
        if not SYNTAX_ERROR.match(ln):
            continue
        frame = next((m for m in map(FRAME.search, reversed(lines[:i])) if m), None)  # the frame it points at
        if frame and own_code(argv, frame.group(1)):
            return (f"Python cannot compile the repro's own code ({ln[:200]}): it fails before it tests anything, "
                    "whatever the defect does (a backslash in a Python string, or newlines lost in --repro's "
                    "split: use / in paths and ; between statements, or put the code in a script)")
    if code == 2 and re.search(r"^usage: ", out, re.M) and re.search(r"^\S+: error: ", out, re.M):
        err = next((ln for ln in lines if re.match(r"\S+: error: ", ln)), last)[:200]
        return (f"the tool rejects the repro's arguments ({err}): a usage error tests nothing (when the rejection is "
                "the defect, write a repro that runs the tool and exits 1 on it)")
    if re.search(r"\bno tests ran\b", out) or (code == 5 and re.search(r"\bdeselected\b", out)):
        return f"the test run selected no tests (exit {code}: {last}): a -k or path that matches nothing reproduces nothing"
    return None

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
        why = own_failure(it["repro"]["run"], code, out)
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


def cmd_similar(bl, a):
    text = f"{a.title} {a.goal or ''}"
    if not words(text):
        raise Refused("similar: the title holds no word to compare")
    rows = similar(bl, text)
    for row in rows[:SIMILAR_SHOWN]:
        say(f"{row[0]:.2f}  {row[1]:>2}  {'near' if is_near(row) else '    '}  {bl.label(row[2])}")
    say(f"similar: {len(rows)} open item(s) share a word, {sum(map(is_near, rows))} near-duplicate(s)")
    return 0


def cmd_fmt(bl, a):
    n = 0
    for iid, it in bl.items.items():
        if bl.raw.get(iid) != canonical(it):
            bl.save(it)
            n += 1
    say(f"fmt: rewrote {n}")
    return 0


def cmd_list(bl, a):
    for iid in sorted(bl.items, key=lambda i: (bl.items[i].get("kind") != "sprint", bl.order_key(i)
                                               if bl.items[i].get("kind") != "sprint" else i)):
        it = bl.items[iid]
        if (a.kind and it.get("kind") != a.kind) or (a.status and it.get("status") != a.status) \
                or (a.sprint and bl.sprint_of(iid) != a.sprint and iid != a.sprint):
            continue
        say(line(bl, iid))
    return 0


def cmd_find(bl, a):
    want = [w.lower() for w in a.words if w.strip()]
    if not want:
        raise Refused("find: give at least one word")
    hits = sorted((i for i, it in bl.items.items() if it.get("kind") != "sprint" and it.get("status") in OPEN
                   and all(w in f"{it.get('title', '')} {it.get('goal', '')}".lower() for w in want)),
                  key=bl.order_key)
    if not hits:
        say(f"find: no open item holds {' '.join(want)}")
        return 1
    for i in hits:
        say(line(bl, i))
        for p in bl.ancestors(i):
            say(f"  parent: {bl.label(p)}")
    return 0


def cmd_tree(bl, a):
    def shown(i):
        return not a.open or bl.items[i].get("status") not in ("done", "dropped")

    def walk(i, depth):
        say("  " * depth + line(bl, i))
        for c in sorted(bl.children(i), key=bl.order_key):
            if shown(c):
                walk(c, depth + 1)

    if a.id:
        walk(need(bl, a.id), 0)
        return 0
    if a.sprint:
        need(bl, a.sprint)
        say(line(bl, a.sprint))
        for i in sorted((i for i in bl.sprint_items(a.sprint) if bl.items[i].get("sprint") and shown(i)),
                        key=bl.order_key):
            walk(i, 1)
        return 0
    for i in sorted((i for i, it in bl.items.items() if not it.get("parent") and it.get("kind") != "sprint"
                     and shown(i)), key=bl.order_key):
        walk(i, 0)
    return 0


def cmd_show(bl, a):
    iid = need(bl, a.id)
    say(canonical(bl.items[iid]).rstrip())
    for p in bl.ancestors(iid):
        say(f"parent: {bl.label(p)}")
    sp = bl.sprint_of(iid)
    if sp:
        say(f"sprint: {bl.label(sp)}")
    for c in bl.children(iid):
        say(f"child: {line(bl, c)}")
    for x in knowledge_lines(bl, iid, indent=""):
        say(x)
    w = waits(bl, iid)
    say("ready" if not w else "waits on:\n  " + "\n  ".join(w))
    return 0


def cmd_next(bl, a):
    ids = ready(bl, a.sprint, a.any)
    if not ids:
        say("nothing ready" + (f" in {bl.label(a.sprint)}" if a.sprint else "") + ": python3 _tools/backlog.py horizon")
        return 1
    for i in ids if a.all else ids[:1]:
        say(line(bl, i))
        for x in knowledge_lines(bl, i):
            say(x)
    return 0


def items_at(root, ref):
    """{id: item} of the item files as git REF has them (a fetched origin/main holds every pushed claim); a file
    that is not a JSON object is left out. Exit 2 (Rejected) for a ref git cannot read."""
    try:
        names = [n for n in git(root, "ls-tree", "--name-only", f"{ref}:{REL_DIR}").splitlines() if n.endswith(".json")]
    except Refused as e:
        raise Rejected(f"held --ref {ref}: {e}") from e
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True,
                       input="".join(f"{ref}:{REL_DIR}/{n}\n" for n in names).encode("utf-8"))
    data, out, at = p.stdout, {}, 0
    for n in names:
        nl = data.find(b"\n", at)
        if nl < 0:
            break
        head = data[at:nl].split()
        if len(head) != 3 or head[1] != b"blob":  # `<name> missing`: nothing follows the header
            at = nl + 1
            continue
        size = int(head[2])
        body, at = data[nl + 1:nl + 1 + size], nl + 2 + size
        try:
            item = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            out[n[:-len(".json")]] = item
    return out


def held_line(bl, iid, glob):
    it = bl.items[iid]
    sp = bl.sprint_of(iid)
    return f"{glob}  {bl.label(iid)}  by {it.get('claimed_by')}  {bl.label(sp) if sp else 'no sprint'}"


def cmd_held(bl, a):
    """The touches of every claimed (doing) item, one line per glob: the glob, the item, its claimer and its sprint.
    --overlaps ID: only the claimed items outside ID's own chain whose touches overlap ID's scope (its touches and
    its descendants'), each line naming the glob of ID's it meets; exit 1 when there is one."""
    mine = bl
    if a.ref:
        bl = Backlog(bl.root)
        bl.items, bl.raw = items_at(bl.root, a.ref), {}
    doing = sorted(i for i, it in bl.items.items() if it.get("status") == "doing" and it.get("claimed_by")
                   and it.get("kind") != "sprint")
    if not a.overlaps:
        rows = sorted((t, i) for i in doing for t in bl.items[i].get("touches", []) or [] if isinstance(t, str) and t)
        for t, i in rows:
            say(held_line(bl, i, t))
        if not rows:
            say("held: no claimed item holds a path")
        return 0
    src = mine if a.overlaps in mine.items else bl
    iid = need(src, a.overlaps)
    chain = {iid, *src.ancestors(iid), *src.descendants(iid)}
    own = [t for t in scope(src, iid) if isinstance(t, str) and t]
    files = tracked_files(bl.root)
    hits = []
    for i in doing:
        if i in chain:
            continue
        for t in bl.items[i].get("touches", []) or []:
            met = [m for m in own if isinstance(t, str) and t and touches_overlap(m, t, files)]
            if met:
                hits.append(f"{held_line(bl, i, t)}  meets {', '.join(met)}")
    for x in sorted(hits):
        say(x)
    if not hits:
        say(f"held: no claimed item's touches overlap {src.label(iid)}")
    return 1 if hits else 0


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
    it.update(status="doing", claimed_by=a.by)
    bl.save(it)
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


def autopilot_rows(bl, iid, gate):
    """The active decisions of kb/_self the autopilot made as the answer to a gate (its source names the item and the gate)."""
    path = Path(bl.root) / "kb" / "_self" / "_decisions.csv"
    try:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return []
    return [r for r in rows if r.get("status") == "active" and r.get("by") == bl_authority.AUTOPILOT
            and r.get("source") == f"backlog item {iid} gate {gate}"]


def run_decide(bl, *argv):
    tool = Path(bl.root) / "_tools" / "kbdecide.py"
    p = subprocess.run([sys.executable, str(tool), *argv], cwd=str(bl.root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if p.returncode:
        raise Refused(f"--record: {(p.stdout + p.stderr).strip()}")
    return p.stdout.strip()


def record_decision(bl, iid, gate, text, by="operator"):
    """Keep a gate's answer as an active decision of kb/_self (`kbdecide.py record`, so check.py guards the write): its
    source names the item and the gate, its context is the item. The autopilot's carries a review_by and its maker
    `autopilot`; the operator's supersedes each active autopilot decision on the same gate (`kbdecide.py supersede`),
    its text ending ` (ratified)` when it repeats theirs, as the same text and context make the same decision id.
    Refused with kbdecide's reason."""
    old = autopilot_rows(bl, iid, gate) if by == "operator" else []
    if any(r.get("text") == text for r in old):
        text += " (ratified)"
    argv = ["record", "--root", "_self", "--source", f"backlog item {iid} gate {gate}", "--context", f"item:{iid}",
            "--by", by, "--maker", by]
    if by == bl_authority.AUTOPILOT:
        argv += ["--review-by", bl_authority.review_by()]
    out = run_decide(bl, *argv, "--", text)
    for r in old:
        run_decide(bl, "supersede", r["id"], out.split("\t")[0], "--root", "_self", "--by", "operator")
    say(out)


def cmd_answer(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    g = next((g for g in it.get("gates", []) if g.get("id") == a.gate), None)
    if g is None:
        raise Refused(f"{bl.label(iid)} has no gate {a.gate}")
    if bl_authority.headless():  # the parsed values, so no argument order or abbreviation of --by gets past it
        what = "--by operator" if a.by == "operator" else "--confirm" if a.confirm and a.by != "autopilot" else ""
        if what:  # --confirm records the operator's confirmation unless --by autopilot
            raise Rejected(f"gate {a.gate} of {bl.label(iid)} unchanged: "
                           + bl_authority.headless_operator_refusal(f"answering with {what}"))
    if a.record and (a.provisional or a.confirm or a.by not in ("operator", "autopilot") or not a.answer):
        raise Rejected("--record keeps the operator's or the autopilot's answer as a decision: --answer TEXT --by "
                       "operator|autopilot, never --provisional or --confirm")
    members = [bl.items[i] for i in bl.sprint_items(iid)] if it.get("kind") == "sprint" else []
    scope = bl_authority.sprint_scope(it, g, members)
    if a.by == "autopilot":
        ok, cls = bl_authority.autopilot_may_answer(scope, g)
        if not ok:
            raise Rejected(f"gate {a.gate} of {bl.label(iid)} is class {cls}: only the operator answers it")
        if g.get("by") == "operator":
            raise Rejected(f"gate {a.gate} of {bl.label(iid)} has the operator's answer: the autopilot does not replace it")
    if a.confirm and not a.by:
        raise Rejected(f"gate {a.gate} of {bl.label(iid)}: --confirm needs --by operator, which an agent passes only "
                       "after the operator said so")
    if a.by != "operator" and (a.by or a.provisional):
        cls = bl_authority.derived_class(scope, g)
        if cls in bl_authority.AUTOPILOT_REFUSED:
            refuse = Rejected if a.provisional or a.confirm else Refused  # --answer by an agent: exit 1, as a blocking gate
            raise refuse(f"gate {a.gate} of {bl.label(iid)} is class {cls}: only the operator answers it "
                         "(--by operator)")
    if a.confirm:
        if g.get("by") != "agent":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} has no agent answer to confirm")
        g["by"] = "autopilot" if a.by == "autopilot" else "operator"
    elif a.provisional:
        if g["kind"] != "provisional":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} is blocking: only the operator answers it")
        g.update(answer=g["recommendation"], by="autopilot" if a.by == "autopilot" else "agent")
    else:
        if not a.answer or not a.by:
            raise Refused("--answer TEXT and --by operator|agent|autopilot")
        if g["kind"] == "blocking" and a.by not in ("operator", "autopilot"):
            raise Refused(f"gate {a.gate} of {bl.label(iid)} is blocking: only the operator answers it")
        g.update(answer=a.answer, by=a.by)
        if a.record:
            record_decision(bl, iid, a.gate, a.answer, a.by)
    bl.save(it)
    say(f"gate {a.gate} of {bl.label(iid)}: {g['answer']} (by {g['by']})")
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
SET_FIELDS = ("notes", "priority", "rank", "sprint") + SET_LISTS  # what set changes; the others are refused
SET_REFUSED = {  # a field set refuses, with the rule it states
    "status": "changes only through claim, release, start, close, drop and done",
    "claimed_by": "changes only through claim and release",
    "evidence": "is written only by done",
    "id": "is the item's identity",
    "kind": "is the item's identity",
    "parent": "is the item's identity",
    "title": "is the item's identity",
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
    if it.get("status") == "done" and {"checks", "touches"} & set(named):
        raise Rejected(f"set refuses checks and touches on {bl.label(iid)}: it is done, and its evidence proves the "
                       "checks and touches it had")
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
    if gate["class"] in bl_authority.AUTOPILOT_REFUSED and gate["kind"] != "blocking":
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


def horizon(bl, sid):
    """(reachable open ids, {cause: [stuck ids]}, critical path [ids], level widths) for a sprint."""
    items = [i for i in bl.sprint_items(sid) if bl.items[i].get("status") not in ("done", "dropped")]
    cause = {}
    if bl.items[sid].get("status") != "active":
        g = next((g for g in bl.items[sid].get("gates", []) if g.get("id") == START_GATE), {})
        why = (STARTS + sid if start_approved(bl.items[sid])
               else f"the sprint's start gate: {g.get('question', 'not started')}")
        cause = {i: why for i in items}
    for i in items:
        outside = []
        for x in [i] + bl.ancestors(i):
            it = bl.items[x]
            for g in open_gates(it):
                cause[i] = f"gate {x}/{g['id']} ({bl.items[x]['title']}): {g['question']}" + (
                    f" [recommended: {g['recommendation']}]" if g.get("recommendation") else "")
            if it.get("trigger") and not it["trigger"].get("fired"):
                cause[i] = f"trigger on {bl.label(x)}: {it['trigger']['when']}"
            for d in it.get("depends_on", []):
                if d not in items and bl.items.get(d, {}).get("status") != "done" and d not in outside:
                    outside.append(d)
        if outside:
            cause[i] = "outside this sprint: " + ", ".join(
                f"{bl.label(d)} ({where_outside(bl, d) if d in bl.items else 'not found'})" for d in outside)
    # propagate: an item waits on what its own and its ancestors' dependencies, its children
    # and (for the review) the sprint wait on
    edges = {i: list(dict.fromkeys(d for x in [i] + bl.ancestors(i) for d in bl.items[x].get("depends_on", [])
                                   if d in items))
             + [c for c in bl.children(i) if c in items] for i in items}
    for i in items:
        if bl.items[i].get("review"):
            edges[i] += [s for s in items if s != i and bl.items[s].get("kind") in IN_SPRINT]
    changed = True
    while changed:
        changed = False
        for i in items:
            if i not in cause:
                src = next((cause[d] for d in edges[i] if d in cause), None)
                if src:
                    cause[i], changed = src, True
    reach = [i for i in items if i not in cause]
    depth = {}

    def d(i, seen=()):
        if i not in depth:
            depth[i] = 1 + max((d(x, seen + (i,)) for x in edges[i] if x in reach and x not in seen), default=0)
        return depth[i]

    for i in reach:
        d(i)
    path = []
    if reach:
        cur = max(reach, key=lambda i: (depth[i], i))
        while cur:
            path.append(cur)
            nxt = [x for x in edges[cur] if x in reach and depth.get(x) == depth[cur] - 1]
            cur = min(nxt) if nxt else None
    widths = [sum(1 for i in reach if depth[i] == k) for k in range(1, (max(depth.values()) if depth else 0) + 1)]
    by_cause = {}
    for i, c in cause.items():
        by_cause.setdefault(c, []).append(i)
    return reach, by_cause, list(reversed(path)), widths


def cmd_horizon(bl, a):
    sprints = [a.sprint] if a.sprint else sorted(i for i, it in bl.items.items()
                                                  if it.get("kind") == "sprint" and it.get("status") == "active")
    lines = []
    if not sprints:
        planned = [i for i, it in bl.items.items() if it.get("kind") == "sprint"]
        n = sum(1 for it in bl.items.values() if it.get("kind") != "sprint" and it.get("status") not in ("done", "dropped"))
        lines.append(f"backlog: no active sprint; {n} open item(s)"
                     + (", planned: " + ", ".join(bl.label(s) + (" (approved, not started)" if start_approved(bl.items[s])
                                                                 else "") for s in planned) if planned else "")
                     + " (python3 _tools/backlog.py tree)")
    for sid in sprints:
        need(bl, sid)
        items = bl.sprint_items(sid)
        done = sum(1 for i in items if bl.items[i].get("status") in ("done", "dropped"))
        reach, stuck, path, widths = horizon(bl, sid)
        starts = len(stuck.get(STARTS + sid, []))  # approved: they wait on backlog.py start, not on the operator
        waiting = sum(map(len, stuck.values())) - starts
        if a.hook:  # every session reads it: id and title, counts and the next id; horizon without --hook has the rest
            nxt = ready(bl, sid)
            lines.append(f"sprint {sid} “{clip(bl.items[sid].get('title', ''), HOOK_TITLE)}”: "
                         f"{done}/{len(items)} done, {len(reach)} reachable"
                         + (f", {starts} wait on backlog.py start" if starts else "")
                         + (f", {waiting} wait on the operator or a trigger" if waiting else "")
                         + (f", next {nxt[0]}" if nxt else ""))
            for c, ids in stuck.items():
                lines.append(f"  waiting on {clip(c, HOOK_CAUSE)}: " + ", ".join(ids[:5]))
            continue
        lines.append(f"sprint {bl.label(sid)} [{bl.items[sid].get('status')}]: goal {bl.items[sid].get('goal')}")
        lines.append(f"  {done}/{len(items)} done; {len(reach)} more reachable without the operator; "
                     + (f"{starts} wait on backlog.py start {sid}; " if starts else "")
                     + f"{waiting} wait on the operator or a trigger")
        nxt = ready(bl, sid)
        if nxt:
            lines.append(f"  next: {bl.label(nxt[0])}")
            if not a.hook:  # the SessionStart hook runs no pack
                lines += knowledge_lines(bl, nxt[0], indent="    ")
        if path:
            lines.append(f"  critical path ({len(path)} steps, parallel width per step {widths}): "
                         + " -> ".join(bl.label(i) for i in path))
        for c, ids in stuck.items():
            lines.append(f"  waiting on {c}")
            for i in ids[:5 if a.hook else 50]:
                lines.append(f"    {bl.label(i)}")
    text = withhold("\n".join(lines))
    if a.hook:
        print(hook_json(text))
    else:
        say(text)
    return 0


HOOK_MAX = 1000  # characters of the hook's whole stdout (its newline included), which every session in a clone reads
HOOK_TITLE = 48  # characters of a sprint title on a hook line
HOOK_CAUSE = 100  # characters of a waiting cause (a gate's question, a trigger) on a hook line


def clip(s, n):
    """s cut to n characters, its last one an ellipsis when cut."""
    return s if len(s) <= n else s[:n - 1] + "…"


def hook_json(text):
    """The SessionStart hook's JSON for text, under HOOK_MAX: its last lines give way, newest first, to one line
    naming how many were left out and the command that prints them, whatever the number of sprints."""
    def dump(t):
        return json.dumps({"systemMessage": t, "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": t + "\nGoals and critical paths: python3 _tools/backlog.py horizon. "
                                     "The backlog runbook is kb/_self/backlog.md."}}, ensure_ascii=False)
    lines, cut, out = text.split("\n"), 0, dump(text)
    while len(out) + 1 >= HOOK_MAX and lines:
        lines.pop()
        cut += 1
        out = dump("\n".join(lines + [f"(+{cut} more line(s): python3 _tools/backlog.py horizon)"]))
    return out


# The pipeline reader, the failure fingerprint and the red-main bug are the CI detector's (bl_intake.py); this
# facade passes its own `run`, which a test replaces, and keeps the names its callers use.
GITLAB_FINISHED = bl_intake.GITLAB_FINISHED
S1_JOBS = bl_intake.S1_JOBS
STATUS_REPRO = list(bl_intake.PIPELINE_REPRO)  # a red-main bug adds --job <its job>
MAIN_PIPELINES = bl_intake.MAIN_PIPELINES
LOG_PREFIX_RE = bl_intake.LOG_PREFIX_RE
failure_fingerprint = bl_intake.failure_fingerprint
names_pipeline = bl_intake.names_pipeline


def normalise_error_line(line):
    """`bl_intake.normalise_error_line` with this module's LOG_PREFIX_RE."""
    return bl_intake.normalise_error_line(line, LOG_PREFIX_RE)


def first_failure(log):
    """`bl_intake.first_failure` with this module's LOG_PREFIX_RE."""
    return bl_intake.first_failure(log, LOG_PREFIX_RE)


def bug_with_fingerprint(bl, fp):
    """The id of an open bug (not done or dropped) whose links carry `fingerprint <fp>`, or None."""
    for iid, it in sorted(bl.items.items()):
        if (it.get("kind") == "bug" and it.get("status") not in ("done", "dropped")
                and f"fingerprint {fp}" in it.get("links", [])):
            return iid
    return None


def add_pipeline(bl, iid, pid):
    """Add `pipeline <pid>` to the links of item `iid` (a bug that already carries its fingerprint) and save it."""
    it = bl.items[iid]
    marker = f"pipeline {pid}"
    if marker not in it.get("links", []):
        it["links"] = list(it.get("links", [])) + [marker]
        bl.save(it)


def latest_pipeline(root, job=None):
    """(pipeline, note): `bl_intake.latest_pipeline` read through this module's `run`."""
    return bl_intake.latest_pipeline(root, job, run)


def covered_by_revert(root, sha):
    """`bl_intake.covered_by_revert` read through this module's `run`."""
    return bl_intake.covered_by_revert(root, sha, run)


def red_bug(pid, sha, sev, jobs=(), url=None, extra="", fingerprint=None, job=None):
    """A red-main bug item (not saved): `bl_intake.pipeline_candidate` written as the item red-pipeline files."""
    return bl_intake.item_of(bl_intake.pipeline_candidate(pid, sha, sev, jobs, url, extra, fingerprint, job),
                             new_id("bug"))


def cmd_red_pipeline(bl, a):
    if not a.status:
        import kbpublic
        run(["git", "fetch", "-q", kbpublic.integration_remote(bl.root), "main"], cwd=bl.root)
    p, note = latest_pipeline(bl.root, getattr(a, "job", None))
    if p is None:
        say(f"red-pipeline: not checked: {note}")
        return 1 if a.status else 0
    unpassed = p.get("unverified") or []
    state = "red" if p["red"] else "unverified" if unpassed else "green"
    why = f": a gate job did not pass: {', '.join(unpassed)}" if state == "unverified" else ""
    if not getattr(a, "job", None):  # the ops row `ci.pipeline`, only when this pipeline's state changed
        try:
            import ql_deliver
            ql_deliver.record_pipeline(p.get("id"), state, p.get("calls"), p.get("sha"))
        except Exception:  # noqa: BLE001 - red-pipeline never fails for its log
            pass
    if a.status:
        say(f"red-pipeline: {p['how']} pipeline {p['id']} of main is {state}{why} ({note})")
        return 0 if state == "green" else 1
    if not p["red"]:
        say(f"red-pipeline: {p['how']} pipeline {p['id']} of main is {state}{why}: nothing to file")
        return 0
    marker = f"pipeline {p['id']}"
    for iid, it in bl.items.items():
        if names_pipeline(it, marker):
            say(f"red-pipeline: {marker} already filed as {bl.label(iid)}")
            return 0
    if covered_by_revert(bl.root, p["sha"]) is not False:
        say(f"red-pipeline: {marker} is covered by an automatic revert (or its history is unreadable): nothing to file")
        return 0
    cand = bl_intake.pipeline_finding(p)  # the CI detector's candidate
    sev = cand.severity
    active = [i for i, it in bl.items.items() if it.get("kind") == "sprint" and it.get("status") == "active"]
    fp = p.get("fingerprint")
    it = bl_intake.item_of(cand, new_id("bug"))
    if sev == "S1" and len(active) == 1:
        it.update(sprint=active[0], status="todo")
    ok, code, _ = run_check(bl.root, it["repro"])
    if ok:
        say(f"red-pipeline: {marker} is green on a second read (repro exit {code}): nothing to file")
        return 0
    dup = bug_with_fingerprint(bl, fp) if fp else None
    if dup:
        add_pipeline(bl, dup, p["id"])
        say(f"red-pipeline: {marker} fails the same way (fingerprint {fp}): added to {bl.label(dup)}")
        return 0
    bl.save(it)
    say(f"red-pipeline: new bug {bl.label(it['id'])}")
    return 0


def cmd_intake(bl, a):
    if a.status is not None and not bl_intake.FP_RE.fullmatch(a.status):
        print(f"intake: {a.status!r} is not a fingerprint (12 hex characters)", file=sys.stderr)
        return 2
    if a.status is not None and a.file:
        print("intake: --status and --file do not go together", file=sys.stderr)
        return 2
    found, failures = bl_intake.collect(bl.root, network=a.network, record=a.status is None)
    for why in failures:
        print(withhold(f"intake: detector failed: {why}"), file=sys.stderr)
    if a.status is not None:
        hit = next((c for c in found if c.fp == a.status), None)
        if hit:
            say(f"intake: {a.status} is still reported by {hit.detector}: {bl_intake.one(hit.title)}")
            return 1
        if failures:
            say(f"intake: {a.status} is not reported, but a detector failed to run")
            return 1
        say(f"intake: {a.status} is no longer reported")
        return 0
    new = skipped = 0
    for c in found:
        dup = bl_intake.open_with_fingerprint(bl.items, c.fp) or bl_intake.named_by(bl.items, c)
        for ln in bl_intake.lines(c, bl.label(dup) if dup else None):
            say(ln)
        if dup:
            skipped += 1
            continue
        new += 1
        if a.file:
            it = bl_intake.item_of(c, new_id(c.kind))
            bl.save(it)
            say(f"  filed {bl.label(it['id'])}")
    say(f"intake: {len(found)} candidate(s), {new} new{' filed' if a.file else ''}, {skipped} skipped" if found
        else "intake: no candidates")
    return 1 if failures else 0


INTAKE_HOOK_BUDGET_S = 50  # intake --hook stops waiting for the detectors after this; the hook's own timeout is 60
INTAKE_HOOK_SLOW = {"drift"}  # intake --hook runs these after the other offline detectors: drift runs item checks


def hook_intake(bl, a, budget=None):
    """`intake --file --hook`, the async SessionStart form: runs the fast offline detectors first, then the slow ones
    (INTAKE_HOOK_SLOW, on what is left of the budget), then the network ones (only with `--network`), and stops
    waiting after `budget` seconds (default INTAKE_HOOK_BUDGET_S); what the detectors that finished by then found is
    filed, so a slow one costs only its own findings. It writes each new candidate as an uncommitted draft item as
    `--file` does, prints nothing, never commits or pushes, and returns 0 whatever happens."""
    budget = INTAKE_HOOK_BUDGET_S if budget is None else budget
    names = sorted(bl_intake.DETECTORS, key=lambda n: (n in bl_intake.NETWORK_DETECTORS, n in INTAKE_HOOK_SLOW, n))
    found = []  # candidates of the detectors that finished, in order

    def read():
        for name in names:
            if name in bl_intake.NETWORK_DETECTORS and not a.network:
                continue
            try:
                found.extend(bl_intake.collect(bl.root, only=name, record=True)[0])
            except Exception:  # noqa: BLE001 - a session starts whatever the detectors do
                pass

    t = threading.Thread(target=read, daemon=True)
    t.start()
    t.join(budget)
    if a.file:
        seen = set()
        for c in list(found):
            if c.fp in seen or bl_intake.open_with_fingerprint(bl.items, c.fp) or bl_intake.named_by(bl.items, c):
                continue
            seen.add(c.fp)
            bl.save(bl_intake.item_of(c, new_id(c.kind)))
    return 0


def referrer_patterns(term, files):
    """The patterns that name term: a tracked file by its path (a .py also by its module name, word-bounded), any
    other term as a symbol, word-bounded."""
    if term in files:
        pats = [re.compile(re.escape(term))]
        if term.endswith(".py"):
            pats.append(re.compile(r"\b" + re.escape(Path(term).stem) + r"\b"))
        return pats
    return [re.compile(r"(?<![\w])" + re.escape(term) + r"(?![\w])")]


def referrers_of(root, term, files):
    """(path, first line number, matching line count) of each tracked text file other than term itself that names it."""
    pats = referrer_patterns(term, files)
    out = []
    for f in files:
        path = Path(root) / f
        if f == term or not path.is_file() or path.stat().st_size > 4_000_000:
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


def args_similar(p):
    p.add_argument("title")
    p.add_argument("--goal")


def args_list(p):
    p.add_argument("--kind", choices=list(KINDS))
    p.add_argument("--status")
    p.add_argument("--sprint")


def args_tree(p):
    p.add_argument("id", nargs="?")
    p.add_argument("--sprint")
    p.add_argument("--open", action="store_true")


def args_find(p):
    p.add_argument("words", nargs="+")


def args_show(p):
    p.add_argument("id")


def args_next(p):
    p.add_argument("--sprint")
    p.add_argument("--any", action="store_true")
    p.add_argument("--all", action="store_true")


def args_held(p):
    p.add_argument("--overlaps", metavar="ID", help="only the claimed items whose touches overlap this item's")
    p.add_argument("--ref", help="read the claims from this git ref (origin/main after git fetch) instead of the files")


def args_claim(p):
    p.add_argument("id")
    p.add_argument("--by", required=True)


def args_release(p):
    p.add_argument("id")


def args_answer(p):
    p.add_argument("id")
    p.add_argument("gate")
    p.add_argument("--answer")
    p.add_argument("--by", choices=("operator", "agent", "autopilot"))
    p.add_argument("--provisional", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--record", action="store_true", help="with --answer TEXT --by operator|autopilot: keep the answer as an active decision")


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


def args_horizon(p):
    p.add_argument("--sprint")
    p.add_argument("--hook", action="store_true")


def args_goal(p):
    p.add_argument("id")


def args_referrers(p):
    p.add_argument("terms", nargs="+", help="a tracked file path or a symbol a task will move or delete")
    p.add_argument("--item", help="mark the files outside this item's scope (touches and its descendants')")


def args_red_pipeline(p):
    p.add_argument("--status", action="store_true")
    p.add_argument("--job", help="read the newest pipeline of main in which this job succeeded or failed on its own account (a red-main bug's repro)")
    p.add_argument("--hook", action="store_true")


def args_intake(p):
    p.add_argument("--file", action="store_true", help="write each new candidate as a draft item outside any sprint")
    p.add_argument("--status", metavar="FINGERPRINT",
                   help="exit 1 while a detector still reports this fingerprint (a filed bug's repro)")
    p.add_argument("--network", action="store_true",
                   help="also run the detectors that call the network (ci: the newest pipeline of main, as red-pipeline reads it)")
    p.add_argument("--hook", action="store_true",
                   help="the async SessionStart form: silent, bounded, exit 0 always; with --file it writes the drafts uncommitted")


bl_cli.register("new", cmd_new, args_new)
bl_cli.register("similar", cmd_similar, args_similar)
bl_cli.register("check", bl_check.cmd_check)
bl_cli.register("fmt", cmd_fmt)
bl_cli.register("selectors", bl_check.cmd_selectors)
bl_cli.register("list", cmd_list, args_list)
bl_cli.register("tree", cmd_tree, args_tree)
bl_cli.register("find", cmd_find, args_find)
bl_cli.register("show", cmd_show, args_show)
bl_cli.register("next", cmd_next, args_next)
bl_cli.register("held", cmd_held, args_held)
bl_cli.register("claim", cmd_claim, args_claim)
bl_cli.register("release", cmd_release, args_release)
bl_cli.register("answer", cmd_answer, args_answer)
bl_cli.register("set", cmd_set, args_set)
bl_cli.register("move", cmd_move, args_move)
bl_cli.register("reopen", cmd_reopen, args_reopen)
bl_cli.register("gate", cmd_gate, args_gate)
bl_cli.register("fire", cmd_fire, args_fire)
bl_cli.register("done", bl_land.cmd_done, bl_land.args_done)
bl_cli.register("land", bl_land.cmd_land, bl_land.args_land)
bl_cli.register("drop", cmd_drop, args_drop)
bl_cli.register("start", bl_plan.cmd_start, bl_plan.args_start)
bl_cli.register("host-check", cmd_host_check, args_host_check)
bl_cli.register("close", bl_land.cmd_close, bl_land.args_close)
bl_cli.register("horizon", cmd_horizon, args_horizon)
bl_cli.register("goal", cmd_goal, args_goal)
bl_cli.register("referrers", cmd_referrers, args_referrers)
import bl_cost  # noqa: F401 - registers `cost` here, so the usage text keeps its order
bl_cli.register("red-pipeline", cmd_red_pipeline, args_red_pipeline)
bl_cli.register("intake", cmd_intake, args_intake)
import bl_procs  # noqa: F401 - registers procs
import bl_stall  # noqa: F401 - registers stalled
import bl_selfcheck  # noqa: F401 - registers `selfcheck`
import bl_bounds  # noqa: F401 - registers bounds


def main(argv=None):
    ap = bl_cli.build_parser(__doc__.split("\n\n")[0], str(ROOT))
    a = ap.parse_args(argv)
    OUTPUT_ROOT[0] = a.root
    for s in (sys.stdout, sys.stderr):  # refusals go to stderr; on Windows a pipe defaults to the ANSI code page
        s.reconfigure(encoding="utf-8")
    if a.cmd in ("red-pipeline", "intake") and a.hook and bl_intake.headless_runner():
        return 0  # a headless runner's worktree stays clean: these hooks write uncommitted drafts
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
