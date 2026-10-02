"""`backlog.py bounds`: the autopilot's own work has an end (kb/_self/backlog.md, Bounds of the autopilot's work).
The kb-sprint skill tells the orchestrator when to run each form.

  bounds [report] [--sprint SP] [--json]
                               the limits and where the backlog stands against each: findings filed per sprint, open
                               drafts, draft inflow against the done outflow of the last sprints, each item's rework
  bounds stop --sprint SP [--budget K --landed N] [--json]
                               whether the manager stops starting work, and why: `sprint-budget` (N of K items
                               landed), `inflow-guard` (a cap of the report is passed) or `no-ready` (no item of SP is
                               ready that is not at its rework cap). Exit 1 when it stops, 0 when work goes on; the
                               first line is `bounds: stop CAUSE: DETAIL` or `bounds: go: ...`, which the digest quotes
  bounds file --origin review|retro|mid-sprint --sprint SP --title T --goal G --evidence KIND:REF
              [--kind story|bug] [--severity S --repro CMD] [--check CMD] [--touch GLOB]
                               what a review, a retro or a mid-sprint finding becomes: an item only when it names a
                               failure that happened with its evidence (`commit:<sha>`, `test:<test id>`,
                               `ops:<row id>`, each of which must exist) and `similar` finds no near-duplicate; a
                               near-duplicate gets the finding in its notes, no evidence leaves it for the close
                               commit body; an item is a draft outside any sprint (an S1 bug joins the running sprint),
                               and carries its origin and evidence as links

The rules, with their limits as named constants (the limits gate of the item that added this module):

  FINDINGS_PER_SPRINT   findings an item may be filed for, per sprint they came from
  REWORK_CAP            refused `done` rows (`done.refused`) plus committed reopens of one item: at the cap, the
                        manager dispatches it no more and it is dropped or escalated
  OUTFLOW_SPRINTS       the sprints whose `sprint.close` rows give the done outflow draft inflow is held under
  OPEN_DRAFTS_MAX       open drafts, of any origin

A sprint whose start gate the autopilot answered gains no story or bug after its start but an S1 bug: `new` refuses
one, `check` reports one that came by `set` or `move`, `close` refuses while `check` would. `check` also reports an
origin without evidence or in the wrong shape and a sprint with more findings than the cap.

Standard library only; imports `bl_base` and `bl_cli` at load and never `backlog` (a layer rule); the other `bl_`
modules and the query log are imported where used. It registers `bounds` when imported and puts the rules in front of
`check`, `new` and `close` (`install`), so `backlog.py` carries only the import.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import bl_base
import bl_cli
from bl_base import APPROVALS, IN_SPRINT, REL_DIR, START_GATE, TEXT_MAX, Refused, Rejected, say

FINDINGS_PER_SPRINT = 5
REWORK_CAP = 3
OUTFLOW_SPRINTS = 3
OPEN_DRAFTS_MAX = 60
ORIGINS = ("review", "retro", "mid-sprint")
RETRO_FREE_ORIGINS = ("review", "retro")  # a sprint made only of items these filed has no retro of its own
EVIDENCE_KINDS = ("commit", "test", "ops")
MODES = ("report", "stop", "file")
STOPS = ("sprint-budget", "inflow-guard", "no-ready")  # the causes `stop` names, in the order it reports them
ORIGIN_LINK = re.compile(r"origin (review|retro|mid-sprint) (SP-[a-z2-7]{8})")
EVIDENCE_LINK = re.compile(r"evidence (commit|test|ops) (\S+)")
COMMIT_REF = re.compile(r"[0-9a-f]{7,40}")
SIMILAR_NEAR = re.compile(r"^\s*\d+\.\d+\s+\d+\s+near\s+((?:EP|ST|TK|SB|BG)-[a-z2-7]{8})\b", re.M)
ORIGINAL = {}  # command name -> the handler this module put its rules in front of


# ---------------------------------------------------------------- what an item carries: its origin and its evidence

def origin_of(it):
    """(kind, sprint id) of the item's `origin <kind> <SP>` link, or None."""
    for x in it.get("links") or []:
        m = ORIGIN_LINK.fullmatch(x) if isinstance(x, str) else None
        if m:
            return m.group(1), m.group(2)
    return None


def evidence_of(it):
    """[(kind, ref)] of the item's `evidence <kind> <ref>` links."""
    return [m.groups() for x in it.get("links") or [] if isinstance(x, str) and (m := EVIDENCE_LINK.fullmatch(x))]


def findings(bl, sid):
    """The ids of the items an origin link of sprint `sid` names, in id order."""
    return sorted(i for i, it in bl.items.items() if (origin_of(it) or (None, None))[1] == sid)


def is_bounded(bl, sid):
    """Whether sprint `sid` is a running sprint whose start gate the autopilot answered: the sprints these rules hold."""
    sp = bl.items.get(sid) or {}
    g = next((g for g in sp.get("gates", []) if g.get("id") == START_GATE), {})
    return sp.get("kind") == "sprint" and sp.get("status") == "active" and g.get("by") == "autopilot" \
        and str(g.get("answer", "")).lower() in APPROVALS


def work_items(bl, sid):
    """The stories and bugs sprint `sid` committed to (the review and the research story, dropped items left out)."""
    return [i for i in bl.sprint_items(sid) if bl.items[i].get("kind") in IN_SPRINT and not bl.items[i].get("review")
            and not bl.items[i].get("goal_research") and bl.items[i].get("status") != "dropped"]


def retro_free(bl, sid):
    """True when every story and bug of the sprint (and there is one) was filed by a review or a retro: the sprint
    answers findings, so it has no retrospective of its own."""
    its = work_items(bl, sid)
    return bool(its) and all((origin_of(bl.items[i]) or ("",))[0] in RETRO_FREE_ORIGINS for i in its)


# ---------------------------------------------------------------- git: when an item joined a sprint, how often it reopened

def git_out(root, *args):
    """The stdout of a git command, or None when it fails (the answer is then unknown, never a guess)."""
    p = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout if p.returncode == 0 else None


def first_commit(root, needle, rel):
    """The oldest commit whose change of the file `rel` adds or removes `needle`, '' when no commit has one, None
    when git cannot say."""
    out = git_out(root, "log", "--reverse", "--format=%H", "-S" + needle, "--", rel)
    return None if out is None else (out.split() or [""])[0]


def started_at(root, sid):
    """The commit that made sprint `sid` active, or None (not committed yet, or git cannot say)."""
    return first_commit(root, '"status": "active"', f"{REL_DIR}/{sid}.json") or None


def gained_late(bl, sid):
    """The ids of the stories and bugs of the running, autopilot-started sprint `sid` that joined it after its start
    and are no S1 bug: an item whose `sprint` field no commit has yet, or whose first commit with it comes after the
    start commit. [] when the sprint's start is not committed or git cannot say."""
    if not is_bounded(bl, sid):
        return []
    start = started_at(bl.root, sid)
    if not start:
        return []
    late = []
    for i in sorted(work_items(bl, sid)):
        it = bl.items[i]
        if it.get("kind") == "bug" and it.get("severity") == "S1":
            continue
        joined = first_commit(bl.root, f'"sprint": "{sid}"', f"{REL_DIR}/{i}.json")
        if joined is None:
            continue
        if joined == "":
            late.append(i)
            continue
        if joined != start and subprocess.run(["git", "merge-base", "--is-ancestor", start, joined], cwd=str(bl.root),
                                              capture_output=True).returncode == 0:
            late.append(i)
    return late


def reopens(root, iid):
    """How many commits took item `iid` back from done (its `"status": "done"` line removed, none added), or None when
    git cannot say. A reopen not yet committed is not counted."""
    out = git_out(root, "log", "-p", "--format=%x00", "-S" + '"status": "done"', "--", f"{REL_DIR}/{iid}.json")
    if out is None:
        return None
    n = 0
    for chunk in out.split("\x00"):
        gone = any(ln.startswith("-") and '"status": "done"' in ln for ln in chunk.splitlines())
        back = any(ln.startswith("+") and '"status": "done"' in ln for ln in chunk.splitlines())
        n += gone and not back
    return n


# ---------------------------------------------------------------- the ops rows: refused dones, the done outflow

def ops_rows(root):
    """The ops rows of this host's spool and the committed sidecars (`bl_stall.ops_rows`), or None when they cannot be
    read."""
    try:
        import bl_stall
        return bl_stall.ops_rows(str(root))
    except Exception:  # noqa: BLE001 - an unreadable log is no count; the callers say it is unknown
        return None


def refusals(rows, iid):
    """How many `done.refused` rows name item `iid` (none is written by anything yet: zero is a valid answer)."""
    return sum(1 for r in rows or [] if r.get("event") == "done.refused" and r.get("item") == iid)


def rework(root, rows, iid):
    """(refused dones, committed reopens) of an item; the second is None when git cannot say."""
    return refusals(rows, iid), reopens(root, iid)


def at_cap(counts):
    refused, reopened = counts
    return refused + (reopened or 0) >= REWORK_CAP


def outflow(rows):
    """(items landed by the last OUTFLOW_SPRINTS sprints closed, how many of them), from the `sprint.close` rows (the
    newest row of each sprint); (None, 0) when there is no such row: the guard cannot judge then."""
    last = {}
    for r in sorted((r for r in rows or [] if r.get("event") == "sprint.close"), key=lambda r: str(r.get("ts"))):
        last[r.get("sprint")] = r
    recent = sorted(last.values(), key=lambda r: str(r.get("ts")))[-OUTFLOW_SPRINTS:]
    if not recent:
        return None, 0
    return sum(int(r.get("landed") or 0) for r in recent), len(recent)


def inflow(bl):
    """The drafts that findings filed and nobody has taken into a sprint yet."""
    return sum(1 for it in bl.items.values() if origin_of(it) and it.get("status") == "draft")


def open_drafts(bl):
    return sum(1 for it in bl.items.values() if it.get("status") == "draft")


def guard_trips(bl, rows):
    """[text] of each cap the backlog is over: a sprint with more findings than FINDINGS_PER_SPRINT, more open drafts
    than OPEN_DRAFTS_MAX, draft inflow above the done outflow of the last OUTFLOW_SPRINTS sprints."""
    trips = []
    counts = {}
    for it in bl.items.values():
        o = origin_of(it)
        if o:
            counts[o[1]] = counts.get(o[1], 0) + 1
    trips += [f"{sid} has {n} findings filed (at most {FINDINGS_PER_SPRINT})" for sid, n in sorted(counts.items())
              if n > FINDINGS_PER_SPRINT]
    n = open_drafts(bl)
    if n > OPEN_DRAFTS_MAX:
        trips.append(f"{n} open drafts (at most {OPEN_DRAFTS_MAX})")
    out, _ = outflow(rows)
    if out is not None and inflow(bl) > out:
        trips.append(f"draft inflow {inflow(bl)} is above the done outflow {out} of the last {OUTFLOW_SPRINTS} sprints")
    return trips


# ---------------------------------------------------------------- what check and close report

def item_problems(bl, iid, it):
    """The errors of one item's origin and evidence links."""
    errs = []
    links = [x for x in it.get("links") or [] if isinstance(x, str)]
    origins = [x for x in links if x.startswith("origin ")]
    if origins and (len(origins) > 1 or not ORIGIN_LINK.fullmatch(origins[0])):
        errs.append(f"{bl.label(iid)}: its origin link is not one `origin review|retro|mid-sprint SP-xxxxxxxx`")
    for x in links:
        if x.startswith("evidence ") and not EVIDENCE_LINK.fullmatch(x):
            errs.append(f"{bl.label(iid)}: the link {x!r} is not `evidence commit|test|ops REF`")
    if origin_of(it) and not evidence_of(it):
        errs.append(f"{bl.label(iid)}: a finding that a review, a retro or a sprint filed names the failure's evidence "
                    "(a link `evidence commit|test|ops REF`), or it is kept in the close commit body only")
    return errs


def late_errors(bl, sid):
    return [f"{bl.label(i)}: joined {bl.label(sid)} after its start and is no S1 bug (a running sprint gains no "
            "item: file it to the backlog)" for i in gained_late(bl, sid)]


def cap_errors(bl, sid):
    n = len(findings(bl, sid))
    return [f"{sid}: {n} findings were filed for it (at most {FINDINGS_PER_SPRINT})"] if n > FINDINGS_PER_SPRINT else []


def sprint_problems(bl, sid):
    """The errors that hold sprint `sid` back from a close: an item it gained after its start, more findings than the
    cap came from it."""
    return late_errors(bl, sid) + cap_errors(bl, sid)


def problems(bl):
    """([error], [warning]) of the whole backlog, as `check` reports them: a malformed origin or evidence, a running
    sprint that gained an item, a sprint with more findings than the cap; open drafts above the cap are a warning."""
    errs = []
    for iid, it in sorted(bl.items.items()):
        errs += item_problems(bl, iid, it)
    sprints = {i for i, it in bl.items.items() if it.get("kind") == "sprint"}
    named = {o[1] for it in bl.items.values() if (o := origin_of(it))}
    for sid in sorted(sprints):
        errs += late_errors(bl, sid)
    for sid in sorted(sprints | named):
        errs += cap_errors(bl, sid)
    warns = []
    n = open_drafts(bl)
    if n > OPEN_DRAFTS_MAX:
        warns.append(f"{n} open drafts (at most {OPEN_DRAFTS_MAX}): triage before filing more")
    return errs, warns


# ---------------------------------------------------------------- the manager's stop

def ready_items(bl, sid, rows):
    """([ready ids], [(id, refused, reopened) set aside at the rework cap]): the items of sprint `sid` the manager may
    dispatch, in work order, as `next` lists them (todo, nothing waits, not the review story), without those at the
    cap."""
    ids = sorted((i for i in bl.sprint_items(sid) if bl.items[i].get("status") == "todo" and not bl_base.waits(bl, i)
                  and not bl.items[i].get("review")), key=bl.order_key)
    ready, aside = [], []
    for i in ids:
        counts = rework(bl.root, rows, i)
        if at_cap(counts):
            aside.append((i, counts[0], counts[1] or 0))
        else:
            ready.append(i)
    return ready, aside


def stop_state(bl, sid, budget=None, landed=0, rows=None):
    """Whether the manager stops starting work on sprint `sid`, and why: {stop, cause, causes, detail, ready, aside,
    guard}. `causes` lists every cause that holds, in STOPS order; `cause` is the first."""
    rows = ops_rows(bl.root) if rows is None else rows
    causes = []
    if budget is not None and landed >= budget:
        causes.append(("sprint-budget", f"{landed} of {budget} item(s) landed"))
    trips = guard_trips(bl, rows)
    if trips:
        causes.append(("inflow-guard", "; ".join(trips)))
    ready, aside = ready_items(bl, sid, rows)
    if not ready:
        why = f"; {len(aside)} set aside at the rework cap" if aside else ""
        causes.append(("no-ready", f"no item of {sid} is ready{why}"))
    return {"stop": bool(causes), "cause": causes[0][0] if causes else None, "causes": [c for c, _ in causes],
            "detail": {c: d for c, d in causes}, "ready": ready, "aside": [list(x) for x in aside], "guard": trips}


# ---------------------------------------------------------------- filing a finding

def evidence_exists(root, kind, ref, rows):
    """Whether the evidence a finding names is there: the commit in the repository, the test (`name` or
    `file.py::name`) defined in a `_tools/test_*.py`, the ops row by its id."""
    if kind == "commit":
        return bool(COMMIT_REF.fullmatch(ref)) and git_out(root, "cat-file", "-e", f"{ref}^{{commit}}") is not None
    if kind == "test":
        file, _, name = ref.rpartition("::")
        files = [Path(root) / "_tools" / file] if file else sorted((Path(root) / "_tools").glob("test_*.py"))
        pat = re.compile(rf"^\s*(?:async\s+)?def {re.escape(name)}\(", re.M)
        return bool(name) and any(f.is_file() and pat.search(f.read_text(encoding="utf-8", errors="replace"))
                                  for f in files)
    return any(r.get("id") == ref for r in rows or [])


def parse_evidence(text):
    kind, _, ref = text.partition(":")
    if kind not in EVIDENCE_KINDS or not ref.strip():
        raise Rejected(f"bounds: --evidence {text!r} is not KIND:REF with KIND one of {', '.join(EVIDENCE_KINDS)}")
    return kind, ref.strip()


def tool_run(root, *argv):
    """(exit code, output) of this clone's backlog.py run with its own interpreter."""
    p = subprocess.run([sys.executable, str(Path(__file__).with_name("backlog.py")), "--root", str(root), *argv],
                       cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, (p.stdout + p.stderr).strip()


def near_duplicates(root, title, goal):
    """The ids of the open items `backlog.py similar` calls near-duplicates of the finding, best first."""
    code, out = tool_run(root, "similar", title, *(["--goal", goal] if goal else []))
    if code:
        raise Refused(f"bounds: similar failed: {out}")
    return SIMILAR_NEAR.findall(out)


def file_finding(bl, a, rows=None):
    """File, merge or keep one finding of a review, a retro or a running sprint. Returns (outcome, id or None) with
    the outcome `filed`, `merged` (into the near-duplicate with that id) or `kept` (in the close commit body only).
    Refused when an evidence ref is not there or a cap would be passed."""
    if a.origin not in ORIGINS or not a.sprint or not (a.title or "").strip() or not (a.goal or "").strip():
        raise Rejected("bounds file: --origin, --sprint, --title and --goal are required")
    sid = bl_base.need(bl, a.sprint)
    if bl.items[sid].get("kind") != "sprint":
        raise Rejected(f"bounds file: {bl.label(sid)} is not a sprint")
    rows = ops_rows(bl.root) if rows is None else rows
    refs = [parse_evidence(e) for e in a.evidence or []]
    missing = [f"{k}:{r}" for k, r in refs if not evidence_exists(bl.root, k, r, rows)]
    if missing:
        raise Refused(f"bounds file: the evidence is not there: {', '.join(missing)}")
    if not refs:
        say(f"bounds: kept in the close commit body only: {a.title.strip()} (no failure with its evidence: a commit, "
            "a test id or an ops row)")
        return "kept", None
    dups = near_duplicates(bl.root, a.title, a.goal)
    if dups:
        it = bl.items[dups[0]]
        note = f"Found again by the {a.origin} of {sid}: {a.title.strip()}. {a.goal.strip()} (" \
               + ", ".join(f"{k} {r}" for k, r in refs) + ")"
        text = f"{it['notes']}\n{note}" if it.get("notes") else note
        if len(text) > TEXT_MAX:
            raise Refused(f"bounds file: the notes of {bl.label(dups[0])} are full; keep the finding in the close "
                          "commit body only")
        it["notes"] = text
        bl.save(it)
        say(f"bounds: merged into the notes of {bl.label(dups[0])}, a near-duplicate")
        return "merged", dups[0]
    n = len(findings(bl, sid))
    if n >= FINDINGS_PER_SPRINT:
        raise Refused(f"bounds file: {bl.label(sid)} has {n} findings filed already (at most {FINDINGS_PER_SPRINT}): "
                      "keep this one in the close commit body only")
    if open_drafts(bl) >= OPEN_DRAFTS_MAX:
        raise Refused(f"bounds file: {open_drafts(bl)} open drafts (at most {OPEN_DRAFTS_MAX}): triage before filing")
    out, _ = outflow(rows)
    if out is not None and inflow(bl) + 1 > out:
        raise Refused(f"bounds file: draft inflow would pass the done outflow {out} of the last {OUTFLOW_SPRINTS} "
                      f"sprints ({inflow(bl)} drafts from findings now): keep this one in the close commit body only")
    argv = ["new", a.kind, "--title", a.title.strip(), "--goal", a.goal.strip()]
    if a.kind == "bug":
        argv += ["--severity", a.severity or "", "--repro", a.repro or ""]
        if a.severity == "S1" and is_bounded(bl, sid):
            argv += ["--sprint", sid]
    for flag, values in (("--check", a.check), ("--touch", a.touch)):
        for v in values or []:
            argv += [flag, v]
    before = set(bl.items)
    code, out = tool_run(bl.root, *argv)
    fresh = bl_base.Backlog(bl.root)
    new = sorted(set(fresh.items) - before)
    if code or len(new) != 1:
        raise Refused(f"bounds file: the item was not filed: {out}")
    it = fresh.items[new[0]]
    it["links"] = list(it.get("links") or []) + [f"origin {a.origin} {sid}"] + [f"evidence {k} {r}" for k, r in refs]
    fresh.save(it)
    say(f"bounds: filed {fresh.label(new[0])} from the {a.origin} of {sid}")
    return "filed", new[0]


# ---------------------------------------------------------------- the command

def report(bl, sid, rows):
    """The numbers of the report, as one dict."""
    out, n = outflow(rows)
    sprints = [sid] if sid else sorted({o[1] for it in bl.items.values() if (o := origin_of(it))})
    items = {}
    for i, it in sorted(bl.items.items()):
        if it.get("status") in ("todo", "doing", "draft") and (not sid or bl.sprint_of(i) == sid) \
                and it.get("kind") != "sprint":
            counts = rework(bl.root, rows, i)
            if counts[0] or counts[1]:
                items[i] = {"refused": counts[0], "reopened": counts[1] or 0, "at_cap": at_cap(counts)}
    return {"limits": {"findings_per_sprint": FINDINGS_PER_SPRINT, "rework_cap": REWORK_CAP,
                       "outflow_sprints": OUTFLOW_SPRINTS, "open_drafts_max": OPEN_DRAFTS_MAX},
            "open_drafts": open_drafts(bl), "inflow": inflow(bl), "outflow": out, "outflow_sprints": n,
            "findings": {s: len(findings(bl, s)) for s in sprints}, "rework": items, "trips": guard_trips(bl, rows)}


def args_bounds(p):
    p.add_argument("mode", nargs="?", choices=MODES, default="report", help="report (default), stop or file")
    p.add_argument("--sprint", help="the sprint to report on, to stop on, or the one a finding came from")
    p.add_argument("--budget", type=int, help="stop: the items the run may land (the runner's --landed)")
    p.add_argument("--landed", type=int, default=0, help="stop: the items landed so far")
    p.add_argument("--json", action="store_true", help="report and stop: print one JSON object")
    p.add_argument("--origin", choices=ORIGINS, help="file: what found it")
    p.add_argument("--kind", choices=("story", "bug"), default="story", help="file: the item to file")
    p.add_argument("--title")
    p.add_argument("--goal")
    p.add_argument("--severity", help="file a bug: its severity")
    p.add_argument("--repro", help="file a bug: its repro, as `new` takes it")
    p.add_argument("--check", action="append")
    p.add_argument("--touch", action="append")
    p.add_argument("--evidence", action="append", metavar="KIND:REF",
                   help="file: commit:<sha>, test:<test id> or ops:<row id> (repeatable)")


def cmd_bounds(bl, a):
    if a.mode == "file":
        file_finding(bl, a)
        return 0
    if a.sprint:
        bl_base.need(bl, a.sprint)
        if bl.items[a.sprint].get("kind") != "sprint":
            raise Rejected(f"bounds: {bl.label(a.sprint)} is not a sprint")
    rows = ops_rows(bl.root)
    if a.mode == "stop":
        if not a.sprint:
            raise Rejected("bounds stop: --sprint SP is required")
        st = stop_state(bl, a.sprint, a.budget, a.landed, rows)
        if a.json:
            print(json.dumps(st, indent=2, sort_keys=True))
        elif st["stop"]:
            say(f"bounds: stop {st['cause']}: {st['detail'][st['cause']]}")
            for c in st["causes"][1:]:
                say(f"bounds: also {c}: {st['detail'][c]}")
        else:
            say(f"bounds: go: {len(st['ready'])} item(s) ready of {a.sprint}")
        for i, refused, reopened in st["aside"]:
            say(f"bounds: set aside {bl.label(i)}: refused {refused}, reopened {reopened} (at the cap of "
                f"{REWORK_CAP}: drop it or escalate it)")
        return 1 if st["stop"] else 0
    rep = report(bl, a.sprint, rows)
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
        return 0
    lim = rep["limits"]
    say(f"bounds: limits: {lim['findings_per_sprint']} findings per sprint, {lim['rework_cap']} refusals and reopens "
        f"per item, draft inflow within the done outflow of the last {lim['outflow_sprints']} sprints, "
        f"{lim['open_drafts_max']} open drafts")
    say(f"bounds: open drafts {rep['open_drafts']} of {lim['open_drafts_max']}")
    say("bounds: draft inflow " + str(rep["inflow"]) + (f", done outflow {rep['outflow']} over {rep['outflow_sprints']} "
        "sprint(s)" if rep["outflow"] is not None else ", done outflow unknown (no sprint.close row)"))
    for s, n in rep["findings"].items():
        say(f"bounds: findings of {s}: {n} of {lim['findings_per_sprint']}")
    for i, r in rep["rework"].items():
        say(f"bounds: rework {bl.label(i)}: refused {r['refused']}, reopened {r['reopened']}"
            + (" (at the cap)" if r["at_cap"] else ""))
    for t in rep["trips"]:
        say(f"bounds: over: {t}")
    return 0


# ---------------------------------------------------------------- the rules in front of check, new and close

def cmd_check(bl, a):
    code = ORIGINAL["check"](bl, a)
    errs, warns = problems(bl)
    for x in errs:
        say(f"bounds: error: {x}")
    for x in warns:
        say(f"bounds: warning: {x}")
    if errs or warns:
        say(f"bounds check: errors={len(errs)} warnings={len(warns)}")
    return 1 if errs else code


def cmd_new(bl, a):
    if a.kind in IN_SPRINT and a.sprint and is_bounded(bl, a.sprint) and not (a.kind == "bug" and a.severity == "S1"):
        raise Refused(f"new: {bl.label(a.sprint)} is a running sprint the autopilot started: it gains no item after its "
                      f"start but an S1 bug; file the {a.kind} without --sprint (a finding of a review or a retro: "
                      "`backlog.py bounds file`)")
    return ORIGINAL["new"](bl, a)


def cmd_close(bl, a):
    sid = a.sprint
    free = False
    if sid in bl.items and bl.items[sid].get("kind") == "sprint":
        free = retro_free(bl, sid)
        errs = [] if a.summary else sprint_problems(bl, sid)
        if errs:
            raise Refused(f"close: {bl.label(sid)} breaks the bounds of the autopilot's work:\n  " + "\n  ".join(errs))
    code = ORIGINAL["close"](bl, a)
    if code == 0 and free:
        say(f"bounds: no retrospective for {sid}: every story and bug of it was filed by a review or a retro")
    return code


def install(registry=None):
    """Put the rules in front of `check`, `new` and `close`: the registered handler becomes this module's, and the
    module that owns `check` and `close` names the same function, so what reads either finds one handler. A command
    not registered yet, or already wrapped, is left as it is."""
    registry = bl_cli.COMMANDS if registry is None else registry
    mine = {"check": cmd_check, "new": cmd_new, "close": cmd_close}
    for name, wrapper in mine.items():
        if name not in registry or registry[name][0] is wrapper:
            continue
        handler, add_arguments, help = registry[name]
        ORIGINAL[name] = handler
        registry[name] = (wrapper, add_arguments, help)
        owner = sys.modules.get({"check": "bl_check", "close": "bl_land"}.get(name, ""))
        if owner is not None and registry is bl_cli.COMMANDS:
            setattr(owner, "cmd_" + name, wrapper)


install()
bl_cli.register("bounds", cmd_bounds, args_bounds,
                help="the limits of the autopilot's work: findings, rework, draft inflow; whether the manager stops")
