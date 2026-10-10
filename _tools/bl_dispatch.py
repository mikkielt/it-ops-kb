"""The worker's brief and its start (kb/_self/backlog.md, Running a sprint; kb/_self/tools.md): `backlog.py brief ID`
prints the brief a sprint worker is given, and `backlog.py dispatch ID` makes the worker's worktree and scratch
directory, writes the brief there and starts the headless session from it, recording the session's pid and id on the
item's claim. `--dry-run` prints what it would run and writes and starts nothing.

The brief is the item's JSON and goal text, its external tracker ids with their urls, the worker's role file, its
worktree and scratch directory, the in-flight sibling items with the files their touches change, the known failing
tests the orchestrator names, the fixed worker rules and the rules of the project's own docs (`rules_section`, the
one function that builds that part: backlog.json's `kb_root` gives the cited fact lines of a kb root, its `docs_map`
the docs and `##` headings the item's touches map to). Standard library only; imports `bl_base`, `bl_cli`,
`bl_items` (for the `goal` text) and `bl_land` (the worker's branch and worktree names), never `backlog`."""
import argparse
import contextlib
import csv
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import bl_cli
import bl_items
from bl_base import (Refused, Rejected, canonical, external_lines, git, id_re, need, research_touches, say, scope,
                     setting, touches_overlap, withhold, worker_dir)
from bl_land import WORK_PREFIX, WORKER_NAME

ROLE_FILE = ".claude/agents/kb-worker.md"  # the worker's role file: its brief makes the session read and follow it
SCRATCH_REL = "_cache/scratch"  # + /<id>/: outside the worktree, for the worker's throwaway files and staging copies
BRIEF_NAME = "brief.md"
RESULT_NAME = "result.json"  # the session's --output-format json output
STDERR_NAME = "stderr.log"
STAGING = "staging"  # under the scratch directory: copies of the `.claude/` files the item's touches name
DEFAULT_MODEL = "sonnet"
EFFORT = "high"
CLAIMS_LEDGER = "kb-backlog-claims.json"  # in the git dir: the claims made in this working tree (bl_items.cmd_claim)
# --max-turns by item kind (kb/public/claude/ci-and-headless.md: print mode only, an error at the limit, no default)
TURNS = {"task": 60, "subtask": 60, "bug": 100, "story": 100, "epic": 100, "sprint": 100}
RESEARCH_TURNS = 200  # a research story or an investigation bug
INVESTIGATION_RE = re.compile(r"investigat", re.I)  # a bug whose title or goal says so is an investigation bug
PACK_TIMEOUT_S = 120
SELF_ROOT = "_self"  # the kb root of the kb's own rule docs: the one `rag.py pack --item` serves
PACK_BUDGET = "600"
RULES_DOCS_MAX = 12  # a mapped project's rules section names this many docs, then counts the rest
RULES_HEADINGS_MAX = 30  # ... and this many `##` headings of one doc

WORKER_RULES = (
    "Run the item's own checks; you may run `python3 _tools/tests.py`, which takes the host test lock and waits its "
    "turn; never `tests.py --changed` (parallel runs load the host into false timeouts).",
    "Add a test only within the ceiling in `_tools/tests_ceiling.json` and only of the four kinds "
    "`kb/_self/backlog.md` names; a bug you fix gets its fix and a retrospective finding, not a regression test, "
    "unless no log or gate output can show it again.",
    "Commit on the local branch `{branch}` with `KB-Work: {id}` in the message's last paragraph, with "
    "`Co-Authored-By` and the other trailers; never push.",
    "Run tests in the foreground, and end every background command and monitor you started before you return: "
    "`land` refuses a branch while a process still runs in your worktree.",
    "File a bug for any defect outside the item, do not fix it: commit the new item file alone, in a commit of its "
    "own on `{branch}` whose `KB-Work` names the new bug, and name the bug in your report.",
    "A doc that needs an edit outside the touches stops the work with a report; `Self-Reviewed:` names only docs "
    "read and found still correct.",
    "A stacked item (its base holds another item's commits not yet landed): each commit names in its own "
    "`Self-Reviewed` trailer every doc `selfdoc.py stale --since <the item's base>` lists for its change, not the "
    "stack's.",
    "A choice the goal leaves open (a name, a default, a width, an opt-in, a limit, a price): record a provisional "
    "gate with your recommendation (`python3 _tools/backlog.py gate add {id} --kind provisional ...`), answer it "
    "`--provisional` and commit it with the work, never prose in the report only: a choice your report names and no "
    "gate on `{branch}` records sends the item back. A choice only the operator can make, or any choice on an item "
    "whose touches are rule-guarding: a blocking gate with its options and your recommendation, commit it, and "
    "stop. `gate add` prints the class it gives the gate; never reword a gate to change its class; one that prints "
    "`made blocking` is committed as printed, and you stop with a report.",
    "A change to what a function returns or takes runs `python3 _tools/backlog.py referrers SYMBOL --item {id}` "
    "first and covers every consumer it lists in the same item; a consumer outside the touches stops the work with "
    "a report.",
    "Never write the operator's decisions into docs or code.",
    "Make no git worktree of your own, never `git worktree add`: `git worktree remove` is denied to agents, so one "
    "you add is left for the operator. A baseline run uses `git stash push -u -m <tag>` (apply it by its sha and drop "
    "it by tag) or a clone under your scratch directory that you delete yourself.",
    "Run each shell command on its own (no `;`, `&&`, pipes), from your worktree directory; never `git push`, "
    "`backlog.py done`, `land` or `dispatch`: the orchestrator lands.",
)
REPORT = ("End with: branch, commits (hash + subject + KB-Work), each goal clause with the check or test assertion "
          "that proves it, each check's exit code and last lines, `tests.py` result, `selfdoc.py stale --since "
          "origin/main` result, the staging-copy changes, any bug filed (id and title), each gate recorded (id, "
          "question, kind, recommendation).")


# ------------------------------------------------------------------ paths and the turn cap

def clone_top(root):
    """The git toplevel of ROOT: where the clone's worker worktrees and scratch directories sit."""
    return Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()


def worktree_path(root, iid):
    return clone_top(root).joinpath(*worker_dir(), WORKER_NAME + iid)


def scratch_path(root, iid):
    return clone_top(root).joinpath(*SCRATCH_REL.split("/"), iid)


def worker_branch(iid):
    return WORK_PREFIX + iid


def max_turns(bl, iid):
    """The `--max-turns` of an item's worker: 200 for a research story (the goal research story, or a story whose
    scope is kb content only) or an investigation bug (its title or goal says investigat...), else by kind."""
    it = bl.items[iid]
    kind = it.get("kind")
    if kind == "story" and (it.get("goal_research") or research_touches(scope(bl, iid))):
        return RESEARCH_TURNS
    if kind == "bug" and INVESTIGATION_RE.search(f"{it.get('title', '')} {it.get('goal', '')}"):
        return RESEARCH_TURNS
    return TURNS.get(kind, TURNS["story"])


def staged_files(bl, iid):
    """The repository paths under `.claude/` that the item's touches name, as files: a session in permission mode
    default or acceptEdits cannot write there, so its brief names a staging copy of each (a glob names no file)."""
    out = []
    for g in scope(bl, iid):
        if g.startswith(".claude/") and not re.search(r"[*?\[]", g) and g not in out:
            out.append(g)
    return out


# ------------------------------------------------------------------ the brief

def known_failures(bl, known):
    """The `--known TEST=BUG` pairs as brief lines: the test id, then the bug filed for it with its title."""
    out = []
    for k in known:
        test, _, bug = k.rpartition("=")
        if not test or not id_re().fullmatch(bug):
            raise Rejected(f"--known {k!r}: expected TEST=BUG, BUG a backlog id")
        out.append(f"- `{test}`: {bl.label(bug)}" if bug in bl.items else f"- `{test}`: {bug}")
    return out


def siblings(bl, iid):
    """The in-flight items (status doing) outside the item's own chain, each with the files its touches change."""
    own = {iid, *bl.ancestors(iid), *bl.descendants(iid)}
    out = []
    for i in sorted(bl.items):
        it = bl.items[i]
        if i not in own and it.get("status") == "doing":
            globs = scope(bl, i)
            out.append(f"- {bl.label(i)}: " + (", ".join(globs) if globs else "no touches"))
    return out


def goal_text(bl, iid):
    """What `backlog.py goal ID` prints: the item's /goal condition and the answered gates above it."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        bl_items.cmd_goal(bl, argparse.Namespace(id=iid))
    return buf.getvalue().rstrip("\n")


def rag_tool(root, kb_root):
    """The rag.py that serves KB_ROOT for the project at ROOT: the project's own `_tools/rag.py`, else, for a root
    other than `_self` (the rule docs of the project that holds the tool), the one beside this module, the installed
    plugin's, whose kb serves the project's root. None when there is none."""
    own = Path(root) / "_tools" / "rag.py"
    if own.is_file():
        return own
    here = Path(__file__).resolve().with_name("rag.py")
    return here if kb_root != SELF_ROOT and here.is_file() else None


def pack_lines(bl, iid, tool, kb_root):
    """The cited fact lines (`path:line`, tag) of KB_ROOT for the item, as lines: `rag.py pack --root _self --item
    ID` for the kb's own rule docs, else `pack --root ROOT` on the item's title and goal (`--item` serves `_self`
    only). A tool that fails gives one line naming why: the brief is still written."""
    item = bl.items[iid]
    shown = "_tools/rag.py" if Path(tool) == Path(bl.root) / "_tools" / "rag.py" else str(tool)
    ask = f"python3 {shown} pack --root {kb_root}"
    if kb_root == SELF_ROOT:
        argv_tail, again = ["--item", iid], f"{ask} --item {iid} --budget {PACK_BUDGET}"
        hint = (f"(`{ask} --set kb-worker` before the first step; any other rule: `{ask} \"<question>\"`.)")
    else:
        argv_tail, again = [f"{item.get('title', '')}. {item.get('goal', '')}".strip()], f"{ask} \"<question>\""
        hint = f"(the cited fact lines of the kb root `{kb_root}` for this item; any other rule: `{again}`.)"
    argv = [sys.executable, str(tool), "pack", "--root", kb_root, "--budget", PACK_BUDGET, *argv_tail]
    try:
        p = subprocess.run(argv, cwd=str(bl.root), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=PACK_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as e:
        return [hint, f"The rules pack could not run ({e}): ask for it with `{again}`."]
    if p.returncode:
        why = (p.stderr or p.stdout).strip().splitlines()[:1]
        return [hint, f"The rules pack exited {p.returncode}" + (f" ({why[0]})" if why else "")
                + f": ask for it with `{again}`."]
    return [hint, *(p.stdout.rstrip("\n").splitlines() or ["The rules pack printed nothing for this item."])]


def doc_headings(path):
    """[(line, text)] of the `## ` headings of the Markdown file at PATH, fenced code left out; [] when unreadable."""
    out, fenced = [], False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for n, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and ln.startswith("## "):
            out.append((n, ln[3:].strip()))
    return out


def mapped_lines(bl, iid, docs_map):
    """The docs DOCS_MAP (a `doc,pattern` CSV, repository-relative paths) maps to the item's touches, as lines: each
    doc's path with its `##` headings and their lines, so the worker reads those sections and not the whole doc."""
    try:
        with open(Path(bl.root) / docs_map, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except (OSError, ValueError, csv.Error) as e:
        return [f"The docs map `{docs_map}` could not be read ({e}): follow the role file and the item's touches."]
    touches = scope(bl, iid)
    docs = sorted({r["doc"].strip() for r in rows if (r.get("doc") or "").strip() and (r.get("pattern") or "").strip()
                   and any(touches_overlap(r["pattern"].strip(), t, ()) for t in touches)})
    if not docs:
        return [f"No doc of the docs map `{docs_map}` maps to this item's touches: follow the role file."]
    out = [f"(from the docs map `{docs_map}`: read these sections of the docs your touches map to, not the whole doc)"]
    for d in docs[:RULES_DOCS_MAX]:
        heads = doc_headings(Path(bl.root) / d)
        shown = "; ".join(f"## {t} (line {n})" for n, t in heads[:RULES_HEADINGS_MAX])
        more = f"; +{len(heads) - RULES_HEADINGS_MAX} more" if len(heads) > RULES_HEADINGS_MAX else ""
        out.append(f"- {d}: " + (shown + more if heads else "no `##` heading" if (Path(bl.root) / d).is_file()
                                 else "not in this checkout"))
    if len(docs) > RULES_DOCS_MAX:
        out.append(f"+{len(docs) - RULES_DOCS_MAX} more docs in `{docs_map}`.")
    return out


def rules_section(bl, iid):
    """The brief's rules of the project's own docs, as lines. backlog.json's `kb_root` names the kb root whose cited
    fact lines the worker gets (`pack_lines`); else its `docs_map` the docs, with their `##` headings, the item's
    touches map to (`mapped_lines`); a project with neither one gets one line saying no docs map is set."""
    docs_map, kb_root = setting("docs_map"), setting("kb_root")
    if kb_root:
        tool = rag_tool(bl.root, kb_root)
        if tool is not None:
            return pack_lines(bl, iid, tool, kb_root)
    if docs_map and (Path(bl.root) / docs_map).is_file():
        return mapped_lines(bl, iid, docs_map)
    named = [f"docs_map `{docs_map}` is no file" if docs_map else "", f"kb_root `{kb_root}` has no `rag.py` here"
             if kb_root else ""]
    why = "; ".join(n for n in named if n) or "docs_map and kb_root are empty in backlog.json"
    return [f"No docs map is set for this project ({why}): follow the role file and the item's touches."]


def compose_brief(bl, iid, known=(), probe=None):
    """The brief for ITEM's worker, as text. Reads the backlog and runs the rules pack; writes nothing."""
    it = bl.items[iid]
    wt, scratch, branch = worktree_path(bl.root, iid), scratch_path(bl.root, iid), worker_branch(iid)
    facts = [it.get("kind")]
    if bl.children(iid) or it.get("kind") in ("story", "bug"):
        facts.append(f"{len(bl.children(iid))} children" if bl.children(iid) else "no tasks")
    for label, value in (("sprint", bl.sprint_of(iid)), ("parent", it.get("parent"))):
        if value:
            facts.append(f"{label} {bl.label(value)}")
    head = f"{bl.label(iid)} ({', '.join(facts)})"
    out = [f"You are a sprint worker for this project's backlog. Your role file is `{ROLE_FILE}`: read it first and "
           "follow it.", "",
           f"Worktree (work only here): {wt}, on branch `{branch}` (made for you; the item is already claimed).",
           f"Scratch directory for throwaway files: {scratch}/ (never /tmp, never the worktree).", "",
           "## Item", head, "", "```json", canonical(it).rstrip("\n"), "```", "",
           "Its goal text (`python3 _tools/backlog.py goal " + iid + "`):", goal_text(bl, iid), ""]
    ext = external_lines(it)
    if ext:
        out += ["External tracker ids:", *[f"- {line}" for line in ext], ""]
    if probe:
        out += ["## Probe", probe, ""]
    staged = staged_files(bl, iid)
    if staged:
        out += ["## Staging copies",
                "`.claude/` is protected for you (a headless session in permission mode `default`): do NOT edit "
                "these files in the worktree. Edit the staging copy instead, never commit it and never copy it "
                "into the worktree; the orchestrator copies it back, runs `selfdoc.py check` and the item's "
                "checks, and commits it on your branch. In your report, say what you changed in each and which "
                "headings or anchors other docs point at that you touched.",
                *[f"- {p} -> {scratch / STAGING / p}" for p in staged], ""]
    out += ["## In-flight siblings"]
    sib = siblings(bl, iid)
    out += (sib + ["Leave those files alone, and write no test that depends on their content."]) if sib else ["None."]
    out += ["", "## Known failing tests on this host"]
    kf = known_failures(bl, known)
    out += (kf + ["A failure not named here is yours to file as a bug."]) if kf else \
        ["None known to the orchestrator. A failure you meet is yours to file as a bug."]
    out += ["", "## Fixed rules", *[f"- {r.format(id=iid, branch=branch)}" for r in WORKER_RULES], "",
            "## Rules of the docs your touches map to", *rules_section(bl, iid), "",
            "## Report", REPORT]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ the session

def claude_argv(bl, iid, model=None, turns=None):
    """The headless session's argument list: the brief goes on stdin, never as a trailing prompt argument, which
    `--add-dir` swallows (it takes several paths)."""
    return ["claude", "-p", "--model", model or DEFAULT_MODEL, "--effort", EFFORT, "--output-format", "json",
            "--add-dir", str(scratch_path(bl.root, iid)), "--max-turns", str(turns or max_turns(bl, iid))]


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def ledger_path(root):
    gitdir = git(root, "rev-parse", "--absolute-git-dir").strip()
    return Path(gitdir) / CLAIMS_LEDGER


def record_worker(root, iid, **fields):
    """Add FIELDS (`worker_pid`, `worker_session`) to the item's record in this working tree's claims ledger, which
    `claim` writes in the git dir and git never commits: a session id is no part of a committed item file."""
    path = ledger_path(root)
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ledger = {}
    rec = ledger.get(iid)
    ledger[iid] = {**(rec if isinstance(rec, dict) else {"by": rec} if rec else {}), **fields}
    tmp = path.with_name(path.name + ".tmp")
    write_text(tmp, json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, path)


def make_worktree(root, iid, wt):
    """Make the worker's worktree on its branch from the HEAD of the checkout dispatch runs in (the orchestrator's
    branch tip, which holds the pushed claim), or reuse the one already there."""
    if wt.is_dir():
        return
    branch = worker_branch(iid)
    exists = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", f"refs/heads/{branch}"],
                            capture_output=True, text=True).returncode == 0
    argv = ["git", "-C", str(root), "worktree", "add", str(wt)] + ([branch] if exists else ["-b", branch])
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise Refused(f"dispatch: {shlex.join(argv)} failed: {(p.stderr or p.stdout).strip()}")


def stage_copies(bl, iid, wt):
    """Copy each `.claude/` file the touches name from the worker's worktree (else this checkout) to its staging
    path in the scratch directory, unless a copy is already there (the worker's edits are kept)."""
    scratch = scratch_path(bl.root, iid)
    for p in staged_files(bl, iid):
        dest = scratch.joinpath(STAGING, *p.split("/"))
        src = next((c for c in (wt / p, Path(bl.root) / p) if c.is_file()), None)
        if src is not None and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)


def cmd_brief(bl, a):
    iid = need(bl, a.id)
    sys.stdout.write(withhold(compose_brief(bl, iid, a.known, a.probe)))
    return 0


def cmd_dispatch(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    turns = a.max_turns or max_turns(bl, iid)
    argv = claude_argv(bl, iid, a.model, turns)
    wt, scratch = worktree_path(bl.root, iid), scratch_path(bl.root, iid)
    brief = scratch / BRIEF_NAME
    if a.dry_run:
        say(f"dispatch {bl.label(iid)} (dry run: nothing made, written or started)")
        say(f"worktree: {wt} (" + ("exists" if wt.is_dir() else f"would be made on {worker_branch(iid)} from HEAD") + ")")
        say(f"scratch: {scratch}")
        say(f"brief: {brief} (stdin)")
        say(f"cwd: {wt}")
        say("argv: " + shlex.join(argv))
        return 0
    if it.get("status") != "doing":
        raise Refused(f"{bl.label(iid)} is {it.get('status')}, not doing: claim it (and push the claim) before dispatch")
    if shutil.which(argv[0]) is None:
        raise Rejected(f"dispatch: {argv[0]} is not on PATH")
    text = compose_brief(bl, iid, a.known, a.probe)
    make_worktree(bl.root, iid, wt)
    scratch.mkdir(parents=True, exist_ok=True)
    stage_copies(bl, iid, wt)
    write_text(brief, text)  # the worker needs the paths as they are: no name guard
    result, errlog = scratch / RESULT_NAME, scratch / STDERR_NAME
    with open(brief, encoding="utf-8") as stdin, open(result, "w", encoding="utf-8", newline="\n") as out, \
            open(errlog, "w", encoding="utf-8", newline="\n") as err:
        proc = subprocess.Popen(argv, cwd=str(wt), stdin=stdin, stdout=out, stderr=err)
        record_worker(bl.root, iid, worker_pid=proc.pid)
        say(f"dispatched {bl.label(iid)}: pid {proc.pid}, brief {brief}, output {result}")
        sys.stdout.flush()
        code = proc.wait()
    session, failed = None, code != 0
    try:
        data = json.loads(result.read_text(encoding="utf-8"))
        session = data.get("session_id") if isinstance(data, dict) else None
        failed = failed or bool(isinstance(data, dict) and data.get("is_error"))
    except (OSError, ValueError):
        failed = True
    if session:
        record_worker(bl.root, iid, worker_session=session)
    say(f"worker of {iid} exited {code}: session {session or 'unknown'} (resume it with `claude -p --resume "
        f"<session>`), output {result}, stderr {errlog}")
    return 1 if failed else 0


def args_brief(p):
    p.add_argument("id")
    p.add_argument("--known", action="append", default=[], metavar="TEST=BUG",
                   help="a test known to fail on this host and the bug filed for it (repeatable)")
    p.add_argument("--probe", metavar="TEXT", help="the result of the one probe run for a bug of unproven cause")


def args_dispatch(p):
    args_brief(p)
    p.add_argument("--dry-run", action="store_true",
                   help="print the worktree, scratch, brief path and argv; make, write and start nothing")
    p.add_argument("--model", metavar="NAME", help=f"another model than {DEFAULT_MODEL}, only when the operator asks")
    p.add_argument("--max-turns", type=int, metavar="N", help="instead of the cap of the item's kind")


bl_cli.register("brief", cmd_brief, args_brief, help="print the worker's brief for an item")
bl_cli.register("dispatch", cmd_dispatch, args_dispatch,
                help="make the worker's worktree and scratch, write its brief and start the headless session")
