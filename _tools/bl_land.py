"""The landing side of backlog.py (kb/_self/backlog.md, What done refuses, Landing; kb/_self/tools.md): `done`, which runs an
item's checks and records the evidence, `land`, which rebases a worker's branch and runs the steps to the integration
main, and `close`, which deletes a finished sprint; with what they share: the commits an item's trailers name
(`item_commits`, `unlanded_code`, `out_of_scope`), the runner of a check (`run_check`), the worker's worktree
(`live_processes`, `release_worker_worktree`), the landed work/<id> branch (`delete_landed_branch`) and the stuck merge
request line.

Standard library only; imports `bl_base`, `bl_check` (the no-op rules `done` applies), `bl_cli` and `bl_intake` (the
colour codes) and never `backlog`. The branch `land` expects sync to open for code commits is named by
`kg_lane.lane_plan`, the one helper sync uses. It registers `done`, `land`, `merge` and `close` with `bl_cli` itself when
imported (`backlog.py`'s USAGE puts each in its usage position), and `host-check` and the repro rules there call `run_check` from
here."""
import argparse, hashlib, json, os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path

import bl_cli
from bl_base import (  # run_check lives below bl_land, so bl_ci reaches it without bl_land (ST-ufpxla7r)
    ANSI_RE, Backlog, ID_RE, REL_DIR, colourless_env, run_check, Refused, commit_written, git, in_scope, item_file, line, main_worktree_spool,
    need, run, say, scope, waits,
)
from bl_check import HOST_BOUND_GATE, host_bound_accepted, is_test_run, noop_output, trivial_command


def item_commits(root, ids):
    """{commit: [paths]} of the commits on HEAD whose KB-Work trailer names any of the ids, oldest first. Only work
    counts: a commit that changes nothing but item files (a claim, a gate, a sprint's plan) is not the item's work."""
    log = git(root, "log", "HEAD", "--reverse", "--no-merges",
              "--format=%H%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)%x1e")
    out = {}
    for rec in log.split("\x1e"):
        sha, _, vals = rec.strip().partition("\x00")
        if sha and set(ID_RE.findall(vals)) & set(ids):
            paths = [p for p in git(root, "show", "--no-renames", "--name-only", "--format=", sha).splitlines() if p]
            if any(not item_file(p) for p in paths):
                out[sha] = paths
    return out


def unlanded_code(root, ids):
    """(short hashes, remote, owners) of the code-lane KB-Work commits on HEAD naming any of the ids that are not
    ancestors of refs/remotes/<integration>/main as last fetched; the hashes are [] when all are, and ["(no such ref)"]
    when the ref is missing and there is a code-lane commit. The owners are the ids the late commits name, first seen
    first, for the code/<id> branches sync opened. Content-lane commits never count; a commit's paths are
    kblane.commit_paths', which leaves out a .gitattributes change confined to the pinned block."""
    import kblane, kbpublic
    remote = kbpublic.integration_remote(root)
    code = []
    for sha, paths in item_commits(root, ids).items():
        lane_paths = kblane.commit_paths(root, sha)
        if kblane.paths_lane(paths if lane_paths is None else lane_paths)[0] == kblane.CODE:
            code.append(sha)
    if not code:
        return [], remote, []
    ref = f"refs/remotes/{remote}/main"
    if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode:
        return ["(no such ref)"], remote, []
    late = [sha for sha in code
            if subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=root,
                              capture_output=True).returncode]
    owners = []
    for sha in late:
        named = ID_RE.findall(git(root, "log", "-1", "--format=%(trailers:key=KB-Work,valueonly,separator=%x2C)", sha))
        owners += [i for i in named if i in ids and i not in owners][:1]
    return [sha[:10] for sha in late], remote, owners


def sync_code_branch(root, upstream, owners, iid):
    """The code/<id> branch sync --push opens for the range UPSTREAM..HEAD, named by kg_lane.lane_plan, the one helper
    sync uses; the late commits' first owner (else the item's own id) when git cannot say."""
    import kg_lane
    _, branch = kg_lane.lane_plan(str(root), upstream, "HEAD")
    return branch or "code/" + (owners[0] if owners else iid)


def blob_id(root, rev, path):
    p = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{rev}:{path}"], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip() if p.returncode == 0 else None


def out_of_scope(root, commits, globs):
    """[(commit, path)] of the paths outside the globs that the item's commits changed and HEAD still has changed:
    a later commit that restored a file (a revert) clears it."""
    first = {}
    for sha, paths in commits.items():
        for p in paths:
            if not in_scope(p, globs):
                first.setdefault(p, sha)
    return [(sha, p) for p, sha in first.items() if blob_id(root, f"{sha}^", p) != blob_id(root, "HEAD", p)]


def noop_proof(bl, iid, passed):
    """done's rule for checks that passed ([(check, output)]) without doing their work: one that runs no test or tool
    code is warned of; one whose output says it did nothing in this clone (noop_output) is warned of too, and refuses
    done unless another passing check runs tests and did its work, or the operator accepted the host-bound proof
    (gate HOST_BOUND_GATE answered accept or approve)."""
    noops = []
    for c, out in passed:
        why = noop_output(out)
        if why:
            noops.append((c, why))
        why = why or trivial_command(c["run"])
        if why:
            say(f"warning: {shlex.join(c['run'])} passed without doing its work in this clone: {why}")
    proven = [c for c, out in passed if is_test_run(c["run"]) and not noop_output(out)]
    if not noops or proven or host_bound_accepted(bl.items[iid]):
        return
    c, why = noops[0]
    raise Refused(f"{bl.label(iid)} is not done: {shlex.join(c['run'])} passed without doing its work in this clone "
                  f"({why}), and no check that runs tests proves the fix. Name one: backlog.py set {iid} --add "
                  "--check 'python3 _tools/tests.py -k <the test that plants the defect>'; or ask the operator to "
                  f"accept the host-bound proof: backlog.py gate add {iid} --id {HOST_BOUND_GATE} --question "
                  "'Accept a proof that does nothing in this clone?' --option accept --option add-test "
                  f"--recommendation add-test, answered with backlog.py answer {iid} {HOST_BOUND_GATE} --answer "
                  "accept --by operator")


def check_token(run):
    """A check's name as an ops token, never its text: the -k selector of a test run, else the script it runs, else
    its program (`done.refused`'s `checks`)."""
    run = [str(x) for x in run]
    name = run[run.index("-k") + 1] if "-k" in run[:-1] else next(
        (Path(x).stem for x in run[1:] if x.endswith(".py")), Path(run[0]).stem if run else "check")
    tok = ops_token(name)
    return tok if tok[:1].isalpha() else f"c-{tok}"[:40]


def refuse_done(iid, t0, reasons, message, checks=()):
    """Append the `done.refused` ops row (the item, its closed reason classes, the failed checks' names and the
    milliseconds spent), then refuse with MESSAGE. Best effort: the row never changes the refusal."""
    try:
        from ql_deliver import ops_row
        fields = {"item": iid, "reasons": sorted(set(reasons)), "ms": int((time.monotonic() - t0) * 1000)}
        if checks:
            fields["checks"] = [check_token(c) for c in checks][:20]
        ops_row("done.refused", **fields)
    except Exception:  # noqa: BLE001 - a refusal never fails for its log
        pass
    raise Refused(message)


def rerun_done_checks(bl, sid):
    """[(item id, check, exit code)] of each check and bug repro of the sprint's done items, the review story left
    out, that fails when run once more on the checkout as it is (the sprint's tip): a check that passed when its item
    was done and fails now (another item broke it, or it never passed on main) is named before the sprint closes."""
    out = []
    for i in sorted(bl.sprint_items(sid)):
        it = bl.items[i]
        if it.get("status") != "done" or it.get("review"):
            continue
        for c in list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else []):
            ok, code, _ = run_check(bl.root, c)
            say(f"{'ok  ' if ok else 'FAIL'} rerun {i}: {shlex.join(c['run'])}")
            if not ok:
                out.append((i, c, code))
    return out


def cmd_done(bl, a):
    t0 = time.monotonic()
    iid = need(bl, a.id)
    it = bl.items[iid]
    kind = it["kind"]
    if kind == "sprint":
        raise Refused("a sprint is closed with backlog.py close")
    reasons = []
    if kind == "epic":
        problems = [f"open child {line(bl, c)}" for c in bl.children(iid)
                    if bl.items[c].get("status") not in ("done", "dropped")]
        reasons += ["children-open"] * bool(problems)
    else:
        problems = [x for x in waits(bl, iid, any_sprint=True)
                    if not x.startswith(("status doing", "not in an active sprint"))]
        reasons += ["not-ready"] * bool(problems)
    if it.get("status") not in ("todo", "doing", "draft" if kind == "epic" else "todo"):
        problems.append(f"status {it.get('status')}")
        reasons.append("status")
    if it.get("review"):
        sp = bl.sprint_of(iid)
        for s in bl.sprint_items(sp) + [sp]:
            for g in bl.items[s].get("gates", []):
                if g.get("by") == "agent":
                    problems.append(f"provisional answer to confirm: {bl.label(s)} gate {g['id']}: {g['answer']}")
                    reasons.append("provisional-answer")
    globs = scope(bl, iid)
    if not globs and kind != "epic" and not it.get("review"):  # start's rule, for an item filed into a running sprint
        problems.append("no touches of its own or under it: a work item needs a scope (backlog.py set ID --touch "
                        "GLOB, or tasks that have touches), which start requires of every work item")
        reasons.append("not-ready")
    if globs:
        dirty = [ln[3:] for ln in git(bl.root, "status", "--porcelain").splitlines()
                 if in_scope(ln[3:].strip('"'), globs) and not in_scope(ln[3:].strip('"'), ())]
        if dirty:
            problems.append("uncommitted changes in scope (checks run on HEAD): " + ", ".join(dirty[:5]))
            reasons.append("uncommitted")
        family = [iid] + bl.descendants(iid)
        if it.get("touches") and not item_commits(bl.root, [iid] + bl.descendants(iid)):
            reasons.append("no-work-commit")
            problems.append(f"no commit on HEAD carries the trailer KB-Work: {iid} or one of its descendants' ids "
                            "and changes a file other than item files (git reads a trailer only in the message's last "
                            "paragraph, with the others; a claim or planning commit is not the work)")
        late, remote, owners = unlanded_code(bl.root, family)
        if late:
            reasons.append("unlanded-code")
        if late == ["(no such ref)"]:
            problems.append(f"code commits of the item, and refs/remotes/{remote}/main is not fetched: fetch {remote}, "
                            "then run done again")
        elif late:
            branch = sync_code_branch(bl.root, f"refs/remotes/{remote}/main", owners, iid)
            problems.append(f"code commit(s) {', '.join(late)} are not on {remote}/main: merge the merge request sync "
                            f"opened for them (branch {branch}, named for the first KB-Work id of the range sync "
                            f"pushes), fetch {remote} and run done again")
        for sha, path in out_of_scope(bl.root, item_commits(bl.root, family), globs):
            problems.append(f"commit {sha[:10]} changed {path}, outside touches (revert it, or widen touches)")
            reasons.append("outside-touches")
    if problems:
        refuse_done(iid, t0, reasons, f"{bl.label(iid)} is not done:\n  " + "\n  ".join(problems))
    checks = list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else [])
    results, failed, passed = [], [], []
    for c in checks:
        ok, code, out = run_check(bl.root, c)
        results.append({"run": c["run"], "exit": code, "sha256": hashlib.sha256(out.encode()).hexdigest()[:16]})
        say(f"{'ok  ' if ok else 'FAIL'} exit={code} {shlex.join(c['run'])}")
        if not ok:
            failed.append((c, code, out))
        else:
            passed.append((c, out))
    if failed:
        for c, code, out in failed:
            tail = "\n".join(out.strip().splitlines()[-8:])
            say(f"--- {shlex.join(c['run'])} (want exit {c.get('exit', 0)}"
                + (f", output matching {c['match']!r}" if c.get("match") else "") + f"):\n{tail}")
        refuse_done(iid, t0, ["check-failed"], f"{bl.label(iid)} is not done: {len(failed)} check(s) failed",
                    [c["run"] for c, _, _ in failed])
    try:
        noop_proof(bl, iid, passed)
    except Refused as e:
        refuse_done(iid, t0, ["no-op-proof"], str(e), [c["run"] for c, out in passed if noop_output(out)])
    if it.get("review"):  # every done item's proof, once more on the sprint's tip: one that fails here does not close
        stale = rerun_done_checks(bl, bl.sprint_of(iid))
        if stale:
            refuse_done(iid, t0, ["check-failed"], f"{bl.label(iid)} is not done: {len(stale)} check(s) of done items "
                        "fail on the sprint's tip:\n  " + "\n  ".join(f"{bl.label(i)}: `{shlex.join(c['run'])}` exits "
                                                                     f"{code}" for i, c, code in stale)
                        + "\nreopen each (backlog.py reopen ID --why ...) and fix it, or fix its check",
                        [c["run"] for _, c, _ in stale])
    if a.dry_run:
        say(f"{bl.label(iid)} would be done")
        return 0
    head = git(bl.root, "rev-parse", "HEAD").strip()
    it.update(status="done", evidence={"commit": head, "checks": results})
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"done {bl.label(iid)} at {head[:10]}" + ("" if a.commit else f"; commit this with the trailer KB-Work: {iid}"))
    commit_written(bl, a, "done", iid)
    return 0


# land: the steps after a worker's branch comes back, each a command run from the clone's root with this interpreter
LAND_STALE = ("stale", ["_tools/selfdoc.py", "stale", "--since"])  # + the integration main; seconds, so it runs first
# run once, when the landing changes _tools/; stress_test.py is no step here: it runs once at the sprint's review story
LAND_HEAVY = (("rag.py eval", ["_tools/rag.py", "eval"]),
              ("lint", [".claude/skills/kb-verify/lint.py"]))
LAND_SYNC = ("kbgit.py sync --push", ["_tools/kbgit.py", "sync", "--push"])
LAND_TAIL = 30  # output lines shown of a step that passed (sync's report is shown whole)


# land's ops rows (kb/_self/querylog.md, ops events): a `land.step` row per step, a `land.end` row at every end, and
# a warning when the item's work left no `work` row in this host's spool or the committed work sidecars. Best effort: nothing here changes land's
# exit or output beyond the warning line.
LAND_OPS = {"step": None, "t": 0.0, "exit": 0, "lane": None, "item": None}


def ops_token(label):
    """A step label as an ops token: lower case, every run of other characters one `-`, at most 40 characters."""
    return re.sub(r"[^a-z0-9_.]+", "-", label.lower()).strip("-")[:40] or "step"


def ops_write(**fields):
    """Append a land ops row (`ql_deliver.ops_row`: nothing inside a test run, so a fixture's landing never reaches the
    clone's spool); a landing never fails for its log."""
    try:
        from ql_deliver import ops_row
        ops_row(fields.pop("event"), **fields)
    except Exception:  # noqa: BLE001 - a landing never fails for its log
        pass


def ops_close(code=0):
    """Write the row of the step that is open (if one is), with CODE as its exit."""
    if LAND_OPS["step"] and LAND_OPS["item"]:
        ops_write(event="land.step", item=LAND_OPS["item"], step=LAND_OPS["step"], exit=code,
                  ms=int((time.monotonic() - LAND_OPS["t"]) * 1000))
    LAND_OPS["step"] = None


def ops_mark(label):
    """The next step starts: the one before it passed."""
    ops_close()
    LAND_OPS.update(step=ops_token(label), t=time.monotonic(), exit=1)


def ops_no_work_rows(root, iid):
    """Whether neither this host's spool, the spool of the main worktree of the clone's git common dir (read only,
    and only when it is another directory than this one: a session started in the main checkout that orchestrates a
    clone writes its rows there) nor the committed work sidecars hold a `work` row (claim, done, release) of the item
    or of a descendant of it: distill moves the spool's work rows into the sidecars (an item line, or a shared line
    naming the item), so a consumed spool is not an item that was worked without the capture hooks. False when capture
    is off, no spool directory exists or anything cannot be read."""
    try:
        import bl_cost, ql_capture, ql_distill
        own = ql_capture.spool_dir()
        if own is None:
            return False
        spools = [Path(own)]
        main = main_worktree_spool(root)
        if main is not None and not (spools[0].exists() and main.exists() and os.path.samefile(spools[0], main)):
            spools.append(main)
        spools = [d for d in spools if d.is_dir()]
        if not spools:
            return False
        ids = {iid, *Backlog(root).descendants(iid)}
        if any(r.get("surface") == "work" and r.get("item") in ids and r.get("action") in ql_capture.WORK_ACTIONS
               for d in spools for p in sorted(d.glob("*.jsonl")) for r in ql_distill.spool_rows(p)[0]):
            return False
        return not bl_cost.cost_lines(root, ids)[0]
    except Exception:  # noqa: BLE001
        return False


def ops_land(handler):
    """Wrap `cmd_land`: the open step's row and the `land.end` row at every end, and the warning after a run that
    returned 0 for an item with no work rows."""
    def wrapped(bl, a):
        LAND_OPS.update(step=None, exit=1, lane=None, item=getattr(a, "id", None))
        t0, done = time.monotonic(), False
        try:
            code = handler(bl, a)
            done = code == 0
            if done and ops_no_work_rows(bl.root, a.id):
                say(f"warning: {a.id} landed with no work rows (a worker started without the capture hooks?)")
            return code
        finally:
            ops_close(0 if done else LAND_OPS["exit"])
            ops_write(event="land.end", item=LAND_OPS["item"], exit=0 if done else 1,
                      ms=int((time.monotonic() - t0) * 1000), lane=LAND_OPS["lane"])
    wrapped.__doc__ = handler.__doc__
    return wrapped


def land_stop(step, why):
    return Refused(f"land stopped at step {step}: {why}")


def land_run(root, step, argv, whole=False):
    """Run one landing step; its output (the tail of it, unless WHOLE or it failed) goes through say()."""
    say(f"land: {step}")
    ops_mark(step)
    try:
        p = subprocess.run([sys.executable, *argv], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=colourless_env())
        code, out = p.returncode, ANSI_RE.sub("", (p.stdout or "") + (p.stderr or "")).rstrip()
    except OSError as e:
        code, out = None, f"cannot start: {e}"
    lines = out.splitlines()
    shown = lines if whole or code else lines[-LAND_TAIL:]
    if shown:
        say("\n".join(shown))
    LAND_OPS["exit"] = code if isinstance(code, int) else 1
    if code != 0:
        raise land_stop(step, f"python3 {shlex.join(argv)} exited {code}")


def land_git_network(root, step, *args):
    """A git network call (fetch, push, ls-remote) with the bounded wait of kg_lock.run_git_bounded; a timeout
    stops the land at STEP, the main lock released by the block it leaves. Returns the CompletedProcess."""
    import kg_lock
    try:
        return kg_lock.run_git_bounded(args, root, step)
    except kg_lock.GitNetworkTimeout as e:
        raise land_stop(step, str(e)) from None


def land_git(root, step, *args):
    if args and args[0] in ("fetch", "push", "ls-remote"):
        p = land_git_network(root, step, *args)
    else:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise land_stop(step, f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def has_ref(root, ref):
    return subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode == 0


def checked_out_elsewhere(root, branch):
    """(path, lock reason or None) of another worktree that has BRANCH checked out, or None (git rebase cannot check
    it out here). A locked worktree with no reason has the reason ""."""
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    for block in git(root, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("worktree ") or f"branch refs/heads/{branch}" not in lines:
            continue
        path = Path(lines[0][len("worktree "):]).resolve()
        if path != here:
            lock = next((ln[len("locked "):] for ln in lines if ln == "locked" or ln.startswith("locked ")), None)
            return path, lock
    return None


# the lock Claude Code puts on a subagent's worktree, which outlives the agent when it left background work running
WORKER_LOCK = "claude agent"
WORKER_DIR = (".claude", "worktrees")  # under the clone's main checkout
WORKER_NAME = "agent-"  # how the Agent tool names a worker's isolation worktree: an unlocked one is removed only so
WORK_PREFIX = "work/"  # the local branch a worker commits on: land deletes it once it has landed
AGENT_BRANCH = "worktree-"  # + the worktree's name: the branch the Agent tool made the worker's worktree on


def live_processes(path):
    """([(pid, command)], None) of the processes whose working directory is PATH or under it, or (None, why) when this
    host gives no way to tell: Linux reads /proc/<pid>/cwd, other POSIX hosts (macOS) ask `lsof -d cwd` for every
    process's working directory; Windows exposes no process's working directory to the standard library, so it is
    never checked there. Never signals a process."""
    target = os.path.realpath(path)

    def inside(cwd):
        return cwd == target or cwd.startswith(target.rstrip(os.sep) + os.sep)

    if os.name == "nt":
        return None, "Windows does not expose a process's working directory"
    proc = Path("/proc")
    if (proc / "self" / "cwd").exists():
        out = []
        for d in proc.iterdir():
            if not d.name.isdigit():
                continue
            try:
                cwd = os.readlink(d / "cwd")
                comm = (d / "comm").read_text(encoding="utf-8", errors="replace").strip()
            except OSError:  # gone, or another user's
                continue
            if inside(cwd):
                out.append((int(d.name), comm))
        return sorted(out), None
    lsof = shutil.which("lsof")
    if not lsof:
        return None, "no /proc and no lsof on this host"
    try:
        p = subprocess.run([lsof, "-n", "-P", "-w", "-d", "cwd", "-Fpcn"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"lsof failed: {e}"
    out, pid, comm, seen = [], None, "", False
    for ln in p.stdout.splitlines():
        if ln.startswith("p") and ln[1:].isdigit():
            pid, comm, seen = int(ln[1:]), "", True
        elif ln.startswith("c"):
            comm = ln[1:]
        elif ln.startswith("n") and pid is not None and inside(ln[1:]):
            out.append((pid, comm))
    if not seen:  # lsof lists at least itself: nothing read means it could not look
        return None, f"lsof listed no process (exit {p.returncode})"
    return sorted(set(out)), None


def worker_dirs(root):
    """The .claude/worktrees/ directory whose worktrees are the workers of the clone land runs in ROOT, as a set: the
    one of the toplevel there (`git rev-parse --show-toplevel`: a linked worktree is its own clone)."""
    top = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    return {top.joinpath(*WORKER_DIR).resolve()}


def detached_workers(root, branch):
    """[(path, lock reason or None)] of the worktrees named as the Agent tool names a worker's (WORKER_NAME) that
    are detached at the tip of BRANCH, other than the one land runs in: a worker that detached to free the branch."""
    tip = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/heads/{branch}"], cwd=root,
                         capture_output=True, text=True).stdout.strip()
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    out = []
    for block in git(root, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.strip().splitlines()
        if not tip or not lines or not lines[0].startswith("worktree ") or "detached" not in lines \
                or f"HEAD {tip}" not in lines:
            continue
        path = Path(lines[0][len("worktree "):]).resolve()
        if path != here and path.name.startswith(WORKER_NAME):
            lock = next((ln[len("locked "):] for ln in lines if ln == "locked" or ln.startswith("locked ")), None)
            out.append((path, lock))
    return out


def release_worker_worktree(root, path, lock, branch=None):
    """Remove the finished worker's worktree PATH that holds the branch land needs, with `git worktree remove` (never
    --force), unlocking it first when Claude Code locked it: agents' shells may not remove a worktree
    (.claude/settings.json denies it), so land, a process of its own, does. Only a worktree under the clone's
    .claude/worktrees/ of the clone land runs in (`git rev-parse --show-toplevel` there: a linked worktree is its own
    clone, its workers sit under its own directory) that is not the one land runs in, has no uncommitted changes and
    no live process, is on BRANCH when that is given, and is either locked by a Claude Code agent (WORKER_LOCK) or,
    unlocked, named as the Agent tool names a worker's (WORKER_NAME, `agent-*`; the test
    land_removes_clean_unlocked_worker_worktree) or by the item id of BRANCH (`work/<id>`; the test
    land_removes_worker_worktree_of_a_linked_clone_named_by_item_id). Returns None once it is removed,
    else why it was left as it was (a remove that fails puts the lock back)."""
    def run_git(*args, cwd=root):
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout if not p.returncode else (p.stderr or p.stdout)).strip()

    state = "not locked" if lock is None else f"locked ({lock})"
    if lock is not None and not lock.startswith(WORKER_LOCK):
        return f"it is locked ({lock or 'no reason given'}), not by a Claude Code agent"
    if path.resolve().parent not in worker_dirs(root):
        return f"it is {state} but not under {'/'.join(WORKER_DIR)}/ of the clone"
    if path.resolve() == Path(root).resolve():
        return f"it is {state} and is the worktree land runs in"
    item_id = branch[len(WORK_PREFIX):] if branch and branch.startswith(WORK_PREFIX) else None
    if lock is None and not path.name.startswith(WORKER_NAME) and path.name != item_id:
        return f"it is not locked and not a worker's ({WORKER_NAME}*)"
    if branch:
        code, out = run_git("symbolic-ref", "-q", "HEAD", cwd=path)
        if code:  # detached: accepted only at the branch's tip (the worker detached there to free the branch)
            head, tip = run_git("rev-parse", "HEAD", cwd=path), run_git("rev-parse", "-q", "--verify", f"refs/heads/{branch}")
            if head[0] or tip[0] or head[1] != tip[1]:
                return f"it is {state} but not on {branch}"
        elif out != f"refs/heads/{branch}":
            return f"it is {state} but not on {branch}"
    code, out = run_git("status", "--porcelain", cwd=path)
    if code or out:
        return f"it is {state} and has uncommitted changes: commit or discard them there, then run land again"
    procs, unchecked = live_processes(path)
    if procs:  # the worker left background work running there: removing the worktree would pull it from under it
        named = ", ".join(f"pid {pid} ({comm or '?'})" for pid, comm in procs)
        return (f"it is {state} and a process still runs there: {named}; end it (the worker ends every "
                f"background command and monitor it started), then run land again")
    if unchecked:
        say(f"land: could not check {path} for live processes ({unchecked}); removing it as a clean worker's")
    if lock is not None:
        code, out = run_git("worktree", "unlock", str(path))
        if code:
            return f"git worktree unlock: {out}"
    code, out = run_git("worktree", "remove", str(path))
    if code:
        if lock is not None:
            run_git("worktree", "lock", "--reason", lock, str(path))
        return f"git worktree remove: {out}"
    say(f"land: removed the finished worker's worktree {path} ({'unlocked; its lock was: ' + lock if lock else 'it was not locked'})")
    return None


def delete_landed_branch(root, branch, upstream, who="land", prefixes=None):
    """Delete the local work/<id> BRANCH, or the worktree-agent-* branch the Agent tool made a removed worker's
    worktree on (or a branch starting with one of PREFIXES, when given), once every commit of it is on UPSTREAM (`git cherry` lists
    no `+` line), with `git branch -D` (a branch landed by a rebase is not an ancestor, so -d refuses it): agents'
    shells may not delete a branch. Any other branch, one with a commit UPSTREAM lacks, or one checked out anywhere is
    kept, and WHO says why. Returns True once it is deleted."""
    if not branch.startswith(prefixes or (WORK_PREFIX, AGENT_BRANCH + WORKER_NAME)) or not has_ref(root, f"refs/heads/{branch}"):
        return False
    code, out, err = run(["git", "cherry", upstream, branch], cwd=root)
    if code or any(ln.startswith("+") for ln in out.splitlines()):
        say(f"{who}: kept {branch}: {'git cherry failed' if code else 'it has commits ' + upstream + ' lacks'}")
        return False
    code, out, err = run(["git", "branch", "-D", branch], cwd=root)
    say(f"{who}: deleted the landed branch {branch}" if not code else f"{who}: kept {branch}: {(err or out).strip()}")
    return not code


# head pipeline states after which GitLab's auto-merge ("merge when the pipeline succeeds") never fires
STUCK_PIPELINES = ("skipped",)


def mr_stuck(mr):
    """True for a GitLab merge request, as the single-request API (`projects/:id/merge_requests/:iid`) answers it,
    that is open, mergeable (`detailed_merge_status` mergeable; `merge_status` can_be_merged on a GitLab without the
    detailed field), set to auto-merge, and whose head pipeline ended in a state in STUCK_PIPELINES: auto-merge waits
    for a pipeline to succeed, which a skipped one never does, so the request sits until someone merges it."""
    if not isinstance(mr, dict):
        return False
    pipe = mr.get("head_pipeline") if isinstance(mr.get("head_pipeline"), dict) else {}
    detailed = mr.get("detailed_merge_status")
    mergeable = detailed == "mergeable" if detailed is not None else mr.get("merge_status") == "can_be_merged"
    return (mr.get("state") == "opened" and mr.get("merge_when_pipeline_succeeds") is True and mergeable
            and pipe.get("status") in STUCK_PIPELINES)


def stuck_merge_request(root, remote, branch):
    """The line land adds while it waits for the merge request of BRANCH: when an open request of BRANCH into main on
    REMOTE's GitLab is stuck (`mr_stuck`), it names the request and the command that merges it. None when no request
    is stuck, and also, saying nothing, when it cannot tell: a remote that is a local path, a forge that is not GitLab,
    glab not signed in, a failed or unreadable call."""
    import urllib.parse
    from ql_deliver import forge_list, origin_forge
    code, url, _ = run(["git", "remote", "get-url", remote], cwd=root)
    url = (url or "").strip()
    if code or not url or url.lower().startswith("file:") or Path(url).exists():
        return None  # a local remote names no forge
    forge, host, project = origin_forge(url)
    if forge != "gitlab":
        return None
    quoted = urllib.parse.quote(project, safe="")
    listed, _, _ = forge_list(url, run, None, lambda p: (
        f"projects/{p}/merge_requests?state=opened&source_branch={urllib.parse.quote(branch, safe='')}"
        f"&target_branch=main&per_page=20"))
    for summary in listed or []:
        iid = summary.get("iid") if isinstance(summary, dict) else None
        if not isinstance(iid, int):
            continue
        code, out, _ = run(["glab", "api", "--hostname", host, f"projects/{quoted}/merge_requests/{iid}"])
        try:
            mr = json.loads(out) if code == 0 else None
        except ValueError:
            mr = None
        if mr_stuck(mr):
            status = mr["head_pipeline"].get("status")
            return (f"land: merge request !{iid} ({mr.get('web_url') or branch}) is mergeable and set to auto-merge, "
                    f"but its pipeline was {status}, so auto-merge will not fire: merge it with "
                    f"python3 _tools/backlog.py merge {branch[len('code/'):] if branch.startswith('code/') else branch}")
    return None


LAND_REF = "refs/land"  # refs/land/<id>: the done commit land made, kept until the landing is verified


def unpicked(root, upstream, head, commits_of):
    """The commits of HEAD that no patch-equivalent commit of UPSTREAM or of the branch COMMITS_OF has, oldest first
    (`git cherry`: a claim that sync rewrote on the integration main, or that the branch carries already, is not
    one)."""
    def plus(*args):
        p = subprocess.run(["git", "cherry", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return [ln[2:].strip() for ln in p.stdout.splitlines() if ln.startswith("+ ")]
    ahead = set(plus(upstream, head))
    return [sha for sha in plus(commits_of, head) if sha in ahead]


def missing_claims(root, family, start, upstream, branch):
    """The claim commits of the item's family on START (the checkout land began on) that the branch lacks and the
    integration main does not have: a claim made after the branch was cut, or never pushed. Oldest first."""
    out = []
    for sha in unpicked(root, upstream, start, branch):
        subject, _, vals = git(root, "log", "-1", "--format=%s%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)",
                               sha).partition("\x00")
        if subject.startswith("chore(backlog): claim ") and set(ID_RE.findall(vals)) & set(family):
            out.append(sha)
    return out


def carry_claims(root, claims, upstream, branch):
    """Rebase BRANCH on UPSTREAM with CLAIMS (commits, oldest first) under its own commits: they are cherry-picked on
    the detached upstream, then the branch's commits are replayed on that. A conflict aborts and changes nothing."""
    def undo():
        subprocess.run(["git", "cherry-pick", "--abort"], cwd=root, capture_output=True)
        subprocess.run(["git", "rebase", "--abort"], cwd=root, capture_output=True)
    land_git(root, "rebase", "switch", "-q", "--detach", upstream)
    p = subprocess.run(["git", "cherry-pick", *claims], cwd=root, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode:
        undo()
        raise land_stop("rebase", f"the claim commit(s) {', '.join(c[:10] for c in claims)} do not apply on "
                                  f"{upstream} (cherry-pick aborted, nothing changed): push the claim first "
                                  f"(kbgit.py sync --push), then run land again\n{(p.stderr or p.stdout).strip()}")
    tip = git(root, "rev-parse", "HEAD").strip()
    return subprocess.run(["git", "rebase", "--quiet", "--onto", tip, upstream, branch], cwd=root,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def item_state(root, rev, iid):
    """The status the item's file has at REV, None when it has none there."""
    blob = blob_id(root, rev, f"{REL_DIR}/{iid}.json")
    if not blob:
        return None
    try:
        return json.loads(git(root, "cat-file", "-p", blob)).get("status")
    except ValueError:
        return None


def verify_landed(root, remote, upstream, iid):
    """After sync --push reported success: fetch the integration main and require that the item's done commit (the
    last commit on HEAD that wrote its file) is on it and that its file reads done there. Stops, naming the step,
    when it is not: a sync that gave up quietly must never end in `landed`."""
    land_git(root, "verify", "fetch", "--quiet", remote, f"+refs/heads/main:{upstream}")
    done = git(root, "log", "-1", "--format=%H", "HEAD", "--", f"{REL_DIR}/{iid}.json").strip()
    on_main = bool(done) and subprocess.run(["git", "merge-base", "--is-ancestor", done, upstream], cwd=root,
                                            capture_output=True).returncode == 0
    if not on_main:
        raise land_stop("verify", f"sync --push exited 0, but the done commit {done[:10] or '(none)'} is not on "
                                  f"{remote}/main after a fetch: it stays on the branch, run land again once the push can go through")
    if item_state(root, upstream, iid) != "done":
        raise land_stop("verify", f"{iid}'s file on {remote}/main does not read done (it reads "
                                  f"{item_state(root, upstream, iid)}): run land again")


def restore_done(root, iid):
    """The done commit land kept in refs/land/<id> back on HEAD (the branch) when the branch lost it, in place of
    running done again: cherry-picked, only when it is the item's own done commit. True once HEAD has it."""
    ref = f"{LAND_REF}/{iid}"
    if not has_ref(root, ref) or item_state(root, ref, iid) != "done":
        return False
    p = subprocess.run(["git", "cherry-pick", ref], cwd=root, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode:
        subprocess.run(["git", "cherry-pick", "--abort"], cwd=root, capture_output=True)
        return False
    return item_state(root, "HEAD", iid) == "done"


SYNTAX_ERROR = re.compile(r"(SyntaxError|IndentationError|TabError)\b")
FRAME = re.compile(r'File "([^"]*)", line \d+')
NOT_FOUND = re.compile(r"^'?(?P<cmd>[^'\s]+)'? is not recognized as an internal or external command"
                       r"|^\S+: (line \d+: )?(?P<sh>\S+): command not found$", re.M)
PY_OPT_ARG = ("-X", "-W", "--check-hash-based-pycs")  # python options that take the next word as their value
SHELLS = {"sh", "bash", "zsh", "dash", "cmd", "cmd.exe", "pwsh", "powershell"}


def launched(argv):
    """(program, script, code): what a repro runs, read through python's options and a shell's -c (or cmd's /c)
    string. PROGRAM is the command's first word as the shell or the OS sees it; SCRIPT the file python or a shell
    runs (None for -c, -m or no script); CODE true when python runs a -c string."""
    argv = list(argv)
    for _ in range(3):  # a shell's -c string may run a shell or python in turn
        if not argv:
            return None, None, False
        prog = os.path.basename(argv[0]).lower()
        if prog in SHELLS:
            rest = argv[1:]
            while rest and rest[0].startswith("-") and rest[0].lower() not in ("-c", "-command"):
                rest = rest[1:]
            if rest and rest[0].lower() in ("-c", "/c", "-command") and len(rest) > 1:
                try:
                    argv = shlex.split(rest[1], posix=prog not in ("cmd", "cmd.exe"))
                except ValueError:
                    return (rest[1].split() or [None])[0], None, False
                continue
            return argv[0], (rest[0] if rest else None), False
        if re.fullmatch(r"python(\d+(\.\d+)?)?(\.exe)?", prog):
            i = 1
            while i < len(argv) and argv[i].startswith("-") and argv[i] not in ("-c", "-m", "-"):
                i += 2 if argv[i] in PY_OPT_ARG else 1
            nxt = argv[i] if i < len(argv) else None
            return argv[0], (None if nxt in (None, "-c", "-m", "-") else nxt), nxt == "-c"
        return argv[0], None, False
    return argv[0] if argv else None, None, False


def tracked(root, path):
    """True when git tracks PATH in the clone at ROOT: a repository tool, not a file a repro wrote for itself."""
    try:
        p = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path], cwd=root or ".", capture_output=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0


def own_code(argv, path, root=None):
    """True when a frame's file is the repro's own code: the -c string, or the script python runs when git does not
    track it (a file the repro wrote for itself; a repository tool's SyntaxError, such as a 3.12-only construct run
    on 3.11, is a genuine reproduction)."""
    _, script, code = launched(argv)
    if path == "<string>":
        return code
    if not script:
        return False
    p, s = (os.path.normcase(os.path.normpath(x)) for x in (path, script))
    return (p == s or p.endswith(os.sep + s)) and not tracked(root, script)


IMPORT_ERROR = re.compile(r"(ModuleNotFoundError|ImportError|AttributeError): (.*)")
EXC_LINE = re.compile(r"[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt)\b(: |$)")


OWN_CODE_ERRORS = ("TypeError", "NameError", "UnboundLocalError")  # the repro's code is wrong, not the value it tests


def own_exception(argv, lines, root=None):
    """Why a repro failed by a Python error in its own code, or None: the traceback's last exception is one that says
    the repro's code itself is wrong (OWN_CODE_ERRORS: a TypeError from calling a function with the wrong arguments, a
    NameError, an UnboundLocalError), raised with the innermost frame in the repro's own code (the -c string or an
    untracked script, own_code), so it fails before the defect is tested (ST-ikh2h7m5). An exception on a value the
    code under test returned (an AttributeError on its None, a KeyError of its output), one raised inside the code
    under test, and an AssertionError are failures it accepts."""
    if not any(ln.startswith("Traceback (most recent call last)") for ln in lines):
        return None
    for i in range(len(lines) - 1, -1, -1):
        m = EXC_LINE.match(lines[i])
        if not m:
            continue
        cls = lines[i].split(":", 1)[0].rsplit(".", 1)[-1]
        if cls not in OWN_CODE_ERRORS:
            return None
        frame = next((f for f in map(FRAME.search, reversed(lines[:i])) if f), None)
        if frame and own_code(argv, frame.group(1), root):
            return (f"the repro's own code raised {cls} ({lines[i][:200]}): it fails before it tests the defect; "
                    "exit 1 on the defect (sys.exit(1 if ... else 0)) instead")
        return None
    return None


def own_import_error(argv, lines, root=None):
    """Why a repro failed importing its own names, or None: the traceback's last exception is a ModuleNotFoundError,
    an ImportError or a module's missing attribute (`module 'x' has no attribute`) raised in the repro's own code (the
    -c string or an untracked script, as own_code reads it), so it names something the code never had; or it is pytest
    missing from a test module the repro imports, which the system python3 cannot run (tests.py runs them). An error
    raised inside the code under test is a failure it accepts."""
    exc = [i for i, ln in enumerate(lines) if EXC_LINE.match(ln)]
    if not exc:
        return None
    i = exc[-1]
    m = IMPORT_ERROR.match(lines[i])
    if not m or (m.group(1) == "AttributeError" and not m.group(2).startswith("module ")):
        return None
    frames = [f for f in map(FRAME.search, lines[:i]) if f and not f.group(1).startswith("<frozen")]
    if not frames:
        return None
    where = frames[-1].group(1)
    if m.group(1) == "ModuleNotFoundError" and re.match(r"No module named '_?pytest\b", m.group(2)) \
            and re.match(r"(test_|conftest)", os.path.basename(where)):
        return (f"the repro imports a test module that needs pytest ({lines[i][:200]}): python3 without pytest cannot "
                "run it; select the test with tests.py -k instead")
    if own_code(argv, where, root):
        return (f"the repro's own code names what it cannot import ({lines[i][:200]}): it fails before it tests "
                "anything; import only names the module has")
    return None


CHAIN = {"&&", "||", ";", "|", "&", "|&"}  # the shell's list and pipeline operators: each starts a command of its own


RESERVED = {"if", "then", "elif", "else", "do", "while", "until", "!", "{", "(", "time"}  # the next word is a command
CLOSERS = {"fi", "done", "esac", "}", ")"}  # end a compound command: no command word
PREFIX_RUNNERS = {"env", "command", "exec", "nohup", "nice"}  # run the utility named after their options and assignments
RUNNER_ARG_OPTS = {"-u", "--unset", "-n", "-C", "--chdir", "-S"}  # options of a prefix runner that take a value


def command_word(tokens):
    """(the command word of one simple command's TOKENS, the tokens after it): reserved words, `!`, `name=value`
    assignments and a prefix runner (env, command, exec, nohup, nice) with its options and assignments are skipped,
    as POSIX reads them; (None, []) when nothing is left."""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in RESERVED or t in CLOSERS or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
            i += 1
        elif os.path.basename(t) in PREFIX_RUNNERS:
            i += 1
            while i < len(tokens) and (tokens[i].startswith("-") or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[i])):
                i += 2 if tokens[i] in RUNNER_ARG_OPTS else 1
        else:
            return t, tokens[i + 1:]
    return None, []


def own_words(argv, depth=3):
    """The command words a repro runs itself: argv[0], or for a shell's -c (or cmd's /c) string the command word of
    every command in it (command_word: after a reserved word such as if, then, do or !, an assignment or a prefix
    runner such as env), split at && || ; | & ( ) and a newline (POSIX runs each, and any can exit 127), and through a
    nested shell's -c string anywhere in it, up to DEPTH shells deep (BG-zvh7cvyo, BG-bapadqdl)."""
    argv = list(argv)
    if not argv:
        return set()
    prog = os.path.basename(argv[0]).lower()
    rest = argv[1:]
    while prog in SHELLS and rest and rest[0].startswith("-") and rest[0].lower() not in ("-c", "-command"):
        rest = rest[1:]
    if not (prog in SHELLS and rest and rest[0].lower() in ("-c", "/c", "-command") and len(rest) > 1) or depth <= 0:
        return {os.path.basename(argv[0])}
    try:
        lex = shlex.shlex(rest[1].replace("\n", " ; "), posix=prog not in ("cmd", "cmd.exe"), punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return {w for w in rest[1].split()[:1]}
    commands, cur = [], []
    for t in tokens:
        if t in CHAIN or t in ("(", ")", ";;"):
            commands.append(cur)
            cur = []
        else:
            cur.append(t)
    commands.append(cur)
    words = set()
    for cmd in commands:
        word, args = command_word(cmd)
        if word is None:
            continue
        if os.path.basename(word).lower() in SHELLS:
            words |= own_words([word, *args], depth - 1)
        else:
            words.add(os.path.basename(word))
    return words


def missing_inside(argv, out):
    """True when the output's not-found message names only commands the repro does not run itself (own_words): a
    wrapper (a shell script, a hook) that started and could not find a tool inside it, which may be the defect. A name
    that is any command word of the repro's own -c string is its own error."""
    own = own_words(argv)
    names = {m.group("cmd") or m.group("sh") for m in NOT_FOUND.finditer(out)}
    return bool(names) and bool(own) and all(os.path.basename(n) not in own for n in names)


def own_failure(argv, code, out, root=None):
    """Why a failing repro failed for its own error rather than the defect, or None when its failure may be the
    defect's: it cannot start (not found; exit 127 or 9009, or a shell's or python -m's lone not-found message, unless the
    message names a tool inside a wrapper the repro started); Python cannot compile its own code (a SyntaxError in
    the -c string or in a script git does not track in ROOT, the clone, default the working directory, before
    anything is tested; python's options and a shell's -c string are read for the script they run); the tool it runs rejects its
    arguments (argparse's exit 2 with usage: and error:); its own code raised an uncaught exception (own_exception); or
    a pytest run selected no tests (exit 5, or no tests ran).
    A failed assertion, a traceback from the code under test or a finding with exit 1 is a failure it accepts."""
    lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    last = lines[-1][:200] if lines else ""
    alone = len(lines) <= 3  # a shell's or interpreter's one message, not a tool's output that mentions one
    if code is not None and (code in (127, 9009) or (alone and NOT_FOUND.search(out))) and missing_inside(argv, out):
        return None  # a wrapper started and a tool inside it is missing: that may be the defect
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
        if frame and own_code(argv, frame.group(1), root):
            return (f"Python cannot compile the repro's own code ({ln[:200]}): it fails before it tests anything, "
                    "whatever the defect does (a backslash in a Python string, or newlines lost in --repro's "
                    "split: use / in paths and ; between statements, or put the code in a script)")
    why = own_import_error(argv, lines, root) or own_exception(argv, lines, root)
    if why:
        return why
    if code == 2 and re.search(r"^usage: ", out, re.M) and re.search(r"^\S+: error: ", out, re.M):
        err = next((ln for ln in lines if re.match(r"\S+: error: ", ln)), last)[:200]
        return (f"the tool rejects the repro's arguments ({err}): a usage error tests nothing (when the rejection is "
                "the defect, write a repro that runs the tool and exits 1 on it)")
    if re.search(r"\bno tests ran\b", out) or (code == 5 and re.search(r"\bdeselected\b", out)):
        return f"the test run selected no tests (exit {code}: {last}): a -k or path that matches nothing reproduces nothing"
    return None


def land_checks(bl, iid):
    """The code lane's checks stage: run the item's checks and a bug's repro, as done does, before sync --push opens
    the auto-merging code/<id> merge request, so nothing is pushed for an item whose proof fails. A check whose test
    run selected nothing is named as malformed, as a repro's own error is when the bug is filed."""
    it = bl.items[iid]
    checks = list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else [])
    say("land: checks")
    ops_mark("checks")
    failed = []
    for c in checks:
        ok, code, out = run_check(bl.root, c)
        say(f"{'ok  ' if ok else 'FAIL'} exit={code} {shlex.join(c['run'])}")
        if not ok:
            failed.append((c, code, out))
    if not failed:
        return
    for c, code, out in failed:
        why = own_failure(c["run"], code, out, bl.root)
        tail = "\n".join(out.strip().splitlines()[-8:])
        say(f"--- {shlex.join(c['run'])} (want exit {c.get('exit', 0)}"
            + (f", output matching {c['match']!r}" if c.get("match") else "") + ")"
            + (f" is a malformed check: {why}" if why else "") + f":\n{tail}")
    raise land_stop("checks", f"{len(failed)} check(s) of {bl.label(iid)} failed: nothing was pushed")


def land_once(bl, a):
    """Land a finished item's branch: rebase it on the integration main, then by lane. Content: done --commit, the
    heavy checks when _tools/ changed, sync --push. Code not yet on the integration main: the item's checks and
    a bug's repro, the heavy checks, sync --push (a code/<id> merge request; main does not move), and a re-run once
    it has merged finishes it as content does. Stops at the first failing step, naming it. Every run and every stop ends
    on the branch (or the detached commit) it started on: the rebase switches to the landed branch, and a claim
    --commit made after land must not ride on it into its merge request."""
    import kbpublic
    import kg_lock  # the host's main lock: the fetch and rebase hold it, the sync --push it runs takes it itself
    iid = need(bl, a.id)
    root = bl.root
    remote = kbpublic.integration_remote(root)
    branch = a.branch or f"work/{iid}"
    upstream = f"refs/remotes/{remote}/main"
    landed = False  # set once the item is done on the integration main: then its work/<id> branch is deleted
    if git(root, "status", "--porcelain").strip():
        raise land_stop("clean tree", "uncommitted changes: commit or stash them first (git status --short)")
    if not has_ref(root, f"refs/heads/{branch}"):
        raise land_stop("branch", f"no local branch {branch} (--branch names another)")
    other = checked_out_elsewhere(root, branch)
    agent_branch = None
    if other:  # a finished worker's clean worktree, locked by Claude Code or an unlocked agent-*, is removed
        why = release_worker_worktree(root, *other, branch=branch)
        if why:
            raise land_stop("branch", f"{branch} is checked out in the worktree {other[0]} and {why}: land it from "
                                      "there, or remove that worktree first")
        agent_branch = AGENT_BRANCH + other[0].name  # the Agent tool's branch of that worktree, deleted once landed
    else:  # a worker detached at the branch's tip holds no branch: remove it too, and go on when it has to stay
        for path, lock in detached_workers(root, branch):
            why = release_worker_worktree(root, path, lock, branch=branch)
            if why:
                say(f"land: kept the worktree {path}: {why}")
            else:
                agent_branch = AGENT_BRANCH + path.name
    start = git(root, "rev-parse", "HEAD").strip()
    start_ref = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.strip()
    try:
        with kg_lock.guarded("backlog.py land: fetch and rebase", "backlog.py", clone=str(root)):
            say(f"land: fetch {remote} main")
            ops_mark("fetch")
            land_git(root, "fetch", "fetch", "--quiet", remote, f"+refs/heads/main:{upstream}")
            say(f"land: rebase {branch} on {remote}/main")
            ops_mark("rebase")
            claims = missing_claims(root, [iid] + bl.descendants(iid), start, upstream, branch)
            if claims:  # claimed after the branch was cut, or never pushed: the claim goes under the worker's commits
                say(f"land: carry the claim commit(s) {', '.join(c[:10] for c in claims)} under {branch}")
                p = carry_claims(root, claims, upstream, branch)
            else:
                p = subprocess.run(["git", "rebase", "--quiet", upstream, branch], cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
        if p.returncode:
            subprocess.run(["git", "rebase", "--abort"], cwd=root, capture_output=True)
            raise land_stop("rebase", f"{branch} does not rebase cleanly on {remote}/main (rebase aborted, nothing "
                                      f"changed): rebase it by hand, then run land again\n"
                                      f"{(p.stderr or p.stdout).strip()}")
        bl = Backlog(root)  # the item files as the rebased branch has them
        need(bl, iid)
        family = [iid] + bl.descendants(iid)
        late, _, owners = unlanded_code(root, family)
        LAND_OPS["lane"] = "code" if late else "content"
        if late == ["(no such ref)"]:
            raise land_stop("fetch", f"{upstream} does not exist after the fetch")
        if late:
            code_branch = sync_code_branch(root, upstream, owners, iid)  # the branch sync --push opens for this range
            tracking = f"refs/remotes/{remote}/{code_branch}"
            fetched = land_git_network(root, "fetch", "fetch", "--quiet", remote,
                                       f"+refs/heads/{code_branch}:{tracking}").returncode == 0
            if fetched and git(root, "rev-parse", f"{tracking}^{{tree}}") == git(root, "rev-parse", "HEAD^{tree}"):
                say(f"land: {bl.label(iid)} waits for its merge request (branch {code_branch} on {remote}, already "
                    f"pushed with this content): merge it, then run backlog.py land {iid} again")
                LAND_OPS["pending"] = ([git(root, "rev-parse", tracking).strip()], code_branch)
                stuck = stuck_merge_request(root, remote, code_branch)
                if stuck:
                    say(stuck)
                return 0
        if not late:
            if bl.items[iid].get("status") == "done":
                say(f"land: done: {bl.label(iid)} is done already")
            elif restore_done(root, iid):  # a run before this one made the done commit and the branch lost it
                say(f"land: done: {bl.label(iid)} has its done commit from the last run ({LAND_REF}/{iid}), "
                    "not run again")
            else:
                say("land: done --commit")
                ops_mark("done")
                try:
                    cmd_done(bl, argparse.Namespace(id=iid, dry_run=False, commit=True, trailer=a.trailer))
                except Refused as e:
                    raise land_stop("done", str(e)) from None
                land_git(root, "done", "update-ref", f"{LAND_REF}/{iid}", "HEAD")
        if late:  # the code lane pushes an auto-merging merge request: its proof runs before that, not after
            stray = out_of_scope(root, item_commits(root, family), scope(bl, iid))
            if stray:  # done's scope rule, read before the merge request opens rather than after it merged
                raise land_stop("scope", f"{bl.label(iid)}'s commits change files outside its touches, so done would "
                                         "refuse it once the merge request merged; nothing was pushed: "
                                + "; ".join(f"commit {sha[:10]} changed {p}" for sha, p in stray)
                                + " (revert it, or widen touches: backlog.py set ID --touch PATH --add)")
            land_checks(bl, iid)
        changed = git(root, "diff", "--name-only", upstream, "HEAD").splitlines()
        if any(p.startswith("_tools/") for p in changed):
            land_run(root, LAND_STALE[0], [*LAND_STALE[1], upstream])  # a missing Self-Reviewed fails in seconds
            for step, argv in LAND_HEAVY:
                land_run(root, step, argv)
        land_run(root, *LAND_SYNC, whole=True)
        if late:
            tip = pushed_tip(root, remote, code_branch)
            LAND_OPS["pending"] = (tip, code_branch) if tip else None
            say(f"land: {bl.label(iid)} is not done yet: its code goes as the merge request of branch {code_branch}; "
                f"once it has merged, run backlog.py land {iid} again (fetch, rebase, done --commit, sync --push)")
        else:
            verify_landed(root, remote, upstream, iid)
            subprocess.run(["git", "update-ref", "-d", f"{LAND_REF}/{iid}"], cwd=root, capture_output=True)
            say(f"land: {bl.label(iid)} landed")
            landed = True
        return 0
    except kg_lock.MainLockTimeout as e:  # a live holder kept the main lock for the whole bound: report blocked
        raise land_stop("fetch and rebase", str(e)) from None
    finally:  # back to where land started, whatever happened after the rebase switched to BRANCH
        back = (["switch", "-q", start_ref[len("refs/heads/"):]] if start_ref.startswith("refs/heads/")
                else ["switch", "-q", "--detach", start])
        p = subprocess.run(["git", *back], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if p.returncode:
            say(f"land: could not return to {start_ref or start[:10]}: {(p.stderr or p.stdout).strip()}")
        elif landed:  # the worker's branches, landed: never the one land runs on
            for done_branch in (branch, agent_branch):
                if done_branch and start_ref != f"refs/heads/{done_branch}":
                    delete_landed_branch(root, done_branch, upstream)


def pushed_tip(root, remote, code_branch):
    """[the tip of CODE_BRANCH on REMOTE] as sync pushed it, fetched: sync may rebase the range onto a newer main
    before it pushes, so the commits --wait-merge waits for are the pushed ones, not the ones land rebased. None when
    the fetch fails (git dies with exit 128 on a ref the remote lacks) or leaves no ref, said once: a stale or
    missing tip is never waited for, and the first pass still ends as not done yet (BG-bd547fvz)."""
    tracking = f"refs/remotes/{remote}/{code_branch}"
    p = land_git_network(root, "wait-merge", "fetch", "--quiet", remote, f"+refs/heads/{code_branch}:{tracking}")
    if p.returncode:
        say(f"land: could not fetch {code_branch} from {remote} after the push "
            f"({(p.stderr or p.stdout).strip() or f'exit {p.returncode}'}): no tip to wait for")
        return None
    tip = subprocess.run(["git", "rev-parse", "-q", "--verify", tracking], cwd=root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout.strip()
    return [tip] if tip else None


WAIT_POLL = 60  # seconds between land --wait-merge's reads of the integration main


def merged_on_main(root, remote, shas):
    """True when every one of SHAS is an ancestor of the integration main after a fetch: git, not the forge CLI, says
    the code merge request merged (a merge commit or a fast-forward keeps the commits)."""
    ref = f"refs/remotes/{remote}/main"
    land_git_network(root, "wait-merge", "fetch", "--quiet", remote, f"+refs/heads/main:{ref}")
    return all(subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=root,
                              capture_output=True).returncode == 0 for sha in shas)


def wait_merge(root, remote, shas, bound, poll=WAIT_POLL, sleep=time.sleep):
    """The number of reads of the integration main it took for SHAS to be on it, reading every POLL seconds for at
    most BOUND seconds; None when they are not on it by then."""
    reads, waited = 0, 0
    while True:
        reads += 1
        if merged_on_main(root, remote, shas):
            return reads
        if waited + poll > bound:
            return None
        sleep(poll)
        waited += poll


@ops_land
def cmd_land(bl, a):
    """Land a finished item's branch (land_once). With --wait-merge SECONDS a code item's first pass is followed by a
    bounded wait for its merge request, read from git (a fetch of the integration main every WAIT_POLL seconds, not
    the forge CLI), then the second pass in the same run; a wait that runs out stops at step wait-merge naming the
    merge request."""
    LAND_OPS["pending"] = None
    code = land_once(bl, a)
    pending, bound = LAND_OPS.get("pending"), getattr(a, "wait_merge", None)
    if code or not pending or bound is None:
        return code
    import kbpublic
    shas, code_branch = pending
    remote = kbpublic.integration_remote(bl.root)
    say(f"land: wait-merge: reading {remote}/main every {WAIT_POLL} s for up to {bound} s")
    ops_mark("wait-merge")
    reads = wait_merge(bl.root, remote, shas, bound)
    if reads is None:
        raise land_stop("wait-merge", f"the merge request of branch {code_branch} has not merged into {remote}/main "
                                      f"within {bound} s: merge it (backlog.py merge {a.id}), then run backlog.py land "
                                      f"{a.id} again")
    say(f"land: merged on {remote}/main ({reads} read(s)): second pass")
    LAND_OPS["pending"] = None
    return land_once(Backlog(bl.root), a)


def summary_key(bl, iid):
    """Tree order: each item under its parent, the tops (epics, then the sprint's stories and bugs) in work order."""
    return [bl.order_key(x) for x in reversed([iid] + bl.ancestors(iid))]


def summary_line(bl, iid, gone):
    """One commit-body line for an item close deletes: its id, title, kind, status and the commit done recorded."""
    it = bl.items[iid]
    depth = sum(1 for p in bl.ancestors(iid) if p in gone)
    ev = (it.get("evidence") or {}).get("commit") if isinstance(it.get("evidence"), dict) else None
    at = f" at {ev[:10]}" if ev else ", no evidence commit"
    return f"{'  ' * depth}- {bl.label(iid)} ({it.get('kind', '')}): {it.get('status', '')}{at}"


def refused_dones(root, ids):
    """How many `done.refused` ops rows name one of `ids`: the rows of the local spool's tools files and of the
    committed ops sidecars (`kb/_querylog/ops/`), each row id once."""
    import ql_capture, ql_store
    rows = []
    spool = ql_capture.spool_dir()
    for f in sorted(Path(spool).glob("tools-*.jsonl")) if spool is not None else []:
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(ln))
            except ValueError:
                continue
    for _, objs in ql_store.records(ql_store.ops_files(Path(root) / "kb" / "_querylog")):
        rows += [o for _, o in objs]
    return len({r.get("id") for r in rows if isinstance(r, dict) and r.get("event") == "done.refused"
                and r.get("item") in ids})


def close_row(bl, sid, items):
    """The keys of the `sprint.close` ops row of sprint `sid` whose item ids are `items`, or None when the sprint's
    planning commit cannot be read: the items `landed` (done) and `dropped`, the `bugs` among them, the provisional
    gates of the items and the sprint that the operator `confirmed`, the `refused` dones the ops rows
    name for them (`refused_dones`) and `ms` from the commit that added the sprint's file to now."""
    its = [bl.items[i] for i in items]
    gates = [g for it in its + [bl.items[sid]] for g in it.get("gates", [])]
    added = [int(x) for x in git(bl.root, "log", "--diff-filter=A", "--format=%ct", "--",
                                 f"{REL_DIR}/{sid}.json").split()]
    if not added:
        return None
    return {"sprint": sid,
            "landed": sum(1 for it in its if it.get("status") == "done"),
            "dropped": sum(1 for it in its if it.get("status") == "dropped"),
            "bugs": sum(1 for it in its if it.get("kind") == "bug"),
            "confirmed": sum(1 for g in gates if g.get("kind") == "provisional" and g.get("by") == "operator"),
            "refused": refused_dones(bl.root, set(items)),
            "ms": max(0, (int(time.time()) - min(added)) * 1000)}


def record_close(bl, sid, items):
    """Append the `sprint.close` ops row (`ql_deliver.ops_row`) before close deletes the items; best effort: whatever
    goes wrong, close goes on."""
    try:
        from ql_deliver import ops_row
        fields = close_row(bl, sid, items)
        if fields is not None:
            ops_row("sprint.close", **fields)
    except Exception:  # noqa: BLE001 - a close never fails for its log
        pass


def worktree_entries(root):
    """[{path, head, branch, lock}] of `git worktree list --porcelain` in ROOT: branch is None when detached, lock
    None when not locked (a lock with no reason is "")."""
    code, text, _ = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    out = []
    for block in text.split("\n\n") if not code else []:
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("worktree "):
            continue
        e = {"path": Path(lines[0][len("worktree "):]).resolve(), "head": "", "branch": None, "lock": None}
        for ln in lines[1:]:
            if ln.startswith("HEAD "):
                e["head"] = ln[len("HEAD "):]
            elif ln.startswith("branch refs/heads/"):
                e["branch"] = ln[len("branch refs/heads/"):]
            elif ln == "locked" or ln.startswith("locked "):
                e["lock"] = ln[len("locked "):]
        out.append(e)
    return out


def merged_into(root, rev, upstream):
    """True when every commit of REV is on UPSTREAM (`git cherry` lists no `+` line: a rebased landing counts)."""
    code, out, _ = run(["git", "cherry", upstream, rev], cwd=root)
    return not code and not any(ln.startswith("+") for ln in out.splitlines())


def clean_worker_leftovers(root, sid, ids):
    """Remove what the closed sprint SID's workers left in the clone ROOT, as a process of its own because agents'
    shells may not run `git worktree remove` or `git branch -D` (.claude/settings.json): the clean `agent-*` worktrees
    of the sprint's items IDS (on `work/<id>`, or detached at a commit whose KB-Work trailer names one), the sprint's
    `work/<id>` branches and the `worktree-agent-*` branches whose tip is on the integration main (one whose
    `agent-<x>` worktree, read before any removal, is another sprint's worker is kept). Worktrees go before branches;
    never with --force. A branch with a commit the integration main lacks, or a locked, dirty or process-holding
    worktree, is kept, and `close: kept ...: reason` says why. Returns the number kept."""
    import kbpublic
    kept = 0

    def keep(what, why):
        nonlocal kept
        kept += 1
        say(f"close: kept {what}: {why}")

    if not ID_RE.fullmatch(sid):
        keep(sid, "not a sprint id")
        return kept
    remote = kbpublic.integration_remote(root)
    upstream = f"refs/remotes/{remote}/main"
    if not has_ref(root, upstream):
        upstream = "refs/heads/main"
    if not has_ref(root, upstream):
        keep("the worker leftovers", "no integration main to compare against")
        return kept
    dirs = worker_dirs(root)
    entries = [e for e in worktree_entries(root) if e["path"].parent in dirs]
    wanted = {f"{WORK_PREFIX}{i}" for i in ids}

    def sprints(e):
        """Whether the worker worktree E is this sprint's: on one of its work/<id> branches, or detached at a commit
        whose KB-Work trailer names one of its items."""
        if e["branch"] in wanted:
            return True
        if e["branch"] is not None:
            return False
        _, trailer, _ = run(["git", "log", "-1", "--format=%(trailers:key=KB-Work,valueonly)", e["head"]], cwd=root)
        return bool({t.strip() for t in re.split(r"[,\s]+", trailer) if t.strip()} & set(ids))

    # read before any removal: the agent-<x> worktree each worktree-agent-<x> branch belongs to, and whose it is
    workers = {e["path"].name: (e, sprints(e)) for e in entries if e["path"].name.startswith(WORKER_NAME)}
    for e, ours in workers.values():  # the sprint's workers first
        on_branch = e["branch"] in wanted
        if not ours:
            continue
        if not merged_into(root, e["head"], upstream):
            keep(e["path"], f"it has commits {upstream} lacks")
            continue
        why = release_worker_worktree(root, e["path"], e["lock"], branch=e["branch"] if on_branch else None)
        if why:
            keep(e["path"], why)
    here = {e["branch"] for e in worktree_entries(root) if e["branch"]}
    code, out, _ = run(["git", "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"], cwd=root)
    for ln in out.splitlines() if not code else []:
        branch, _, tip = ln.partition(" ")
        if branch in here:
            continue
        if branch in wanted:
            delete_landed_branch(root, branch, upstream, who="close")
        elif branch.startswith(AGENT_BRANCH + WORKER_NAME):
            owner = workers.get(branch[len(AGENT_BRANCH):])
            if owner and not owner[1]:  # its worktree is another sprint's worker, still there: not this close's
                keep(branch, f"its worktree {owner[0]['path']} is on {owner[0]['branch'] or 'a detached commit'}, "
                             "not one of this sprint's items")
                continue
            anc = run(["git", "merge-base", "--is-ancestor", tip, upstream], cwd=root)[0] == 0
            if anc:
                delete_landed_branch(root, branch, upstream, who="close")
    return kept


TIDY_PREFIXES = (WORK_PREFIX, AGENT_BRANCH + WORKER_NAME, "orch/")  # orch/: a retired runner's branch left in a clone


def integration_main(root):
    """The integration main's ref of the clone ROOT (`refs/remotes/<remote>/main`, else `refs/heads/main`), or None."""
    import kbpublic
    for ref in (f"refs/remotes/{kbpublic.integration_remote(root)}/main", "refs/heads/main"):
        if has_ref(root, ref):
            return ref
    return None


def tidy_worktree_kept(root, entry, upstream):
    """Why the agent worktree ENTRY stays, or None when tidy may remove it: the worktree tidy runs in, any lock (a Claude
    Code agent's too: tidy is clone-wide and cannot tell a finished worker from one that has not committed yet; close,
    which knows its sprint's items, releases those), uncommitted changes, a live process, or a commit UPSTREAM lacks."""
    path = entry["path"]
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    cwd = Path.cwd().resolve()
    if path == here or path == cwd or path in cwd.parents:
        return "it is the worktree tidy runs in"
    if entry["lock"] is not None:
        return f"it is locked ({entry['lock'] or 'no reason given'}): a worker may still be using it"
    code, out, err = run(["git", "status", "--porcelain"], cwd=path)
    if code or out.strip():
        return "it has uncommitted changes" if not code else f"git status failed: {err.strip()}"
    procs, _ = live_processes(path)
    if procs:
        return "a process still runs there: " + ", ".join(f"pid {pid} ({comm or '?'})" for pid, comm in procs)
    if not merged_into(root, entry["head"], upstream):
        return f"it has commits {upstream} lacks"
    return None


def cmd_tidy(bl, a):
    """List (and with --apply remove) the clone's leftovers: the clean, process-free agent-* worktrees under its
    .claude/worktrees/ whose commits are all on the integration main, then the local work/*, worktree-agent-* and
    orch/* branches whose commits are all on it and that no worktree has checked out; every other one is printed with
    why it stays. Removal goes through close's helpers, never --force."""
    root = bl.root
    upstream = integration_main(root)
    if upstream is None:
        raise Refused("tidy: no integration main to compare against (fetch the integration remote first)")
    verb = "removed" if a.apply else "would remove"
    removable, kept = 0, 0
    dirs = worker_dirs(root)
    for e in worktree_entries(root):
        if e["path"].parent not in dirs or not e["path"].name.startswith(WORKER_NAME):
            continue
        why = tidy_worktree_kept(root, e, upstream)
        if why is None and a.apply:
            why = release_worker_worktree(root, e["path"], e["lock"])
        if why:
            kept += 1
            say(f"tidy: kept {e['path']}: {why}")
        else:
            removable += 1
            say(f"tidy: {verb} the worktree {e['path']}")
    here = {e["branch"] for e in worktree_entries(root) if e["branch"]}
    code, out, _ = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=root)
    for branch in out.split() if not code else []:
        if not branch.startswith(TIDY_PREFIXES):
            continue
        if branch in here:
            kept += 1
            say(f"tidy: kept {branch}: it is checked out in a worktree")
        elif not merged_into(root, f"refs/heads/{branch}", upstream):
            kept += 1
            say(f"tidy: kept {branch}: it has commits {upstream} lacks")
        elif a.apply and not delete_landed_branch(root, branch, upstream, who="tidy", prefixes=TIDY_PREFIXES):
            kept += 1
        else:
            removable += 1
            if not a.apply:
                say(f"tidy: would remove the branch {branch}")
    say(f"tidy: {verb} {removable}, kept {kept}" + ("" if a.apply else " (--apply removes them)"))
    return 0


def args_tidy(p):
    p.add_argument("--apply", action="store_true", help="remove what tidy lists (default: only list it)")


def cleanup_gate_do(bl, dead):
    """Drop every gate `do` entry of a remaining item that names (by item id) an item in DEAD, which close deletes: the
    work that entry waited for is done or dropped, and check refuses a `do` naming an item that does not exist. An
    emptied `do` goes with its last entry. Returns [(item id, gate id, option, the deleted item's id)]."""
    out = []
    for i, it in sorted(bl.items.items()):
        if i in dead:
            continue
        touched = False
        for g in it.get("gates") or []:
            do = g.get("do") if isinstance(g, dict) else None
            if not isinstance(do, dict):
                continue
            hit = [o for o, how in do.items() if isinstance(how, str) and how in dead]
            for opt in hit:
                out.append((i, g.get("id"), opt, do.pop(opt)))
            if hit and not do:
                g.pop("do")
            touched = touched or bool(hit)
        if touched:
            bl.save(it)
    return out


CLAUSE_SPLIT = re.compile(r";\s+|,\s+and\s+")  # a sprint goal's clauses: split at '; ' and ', and '
CLAUSE_COVER = 0.5  # the share of a clause's words an item's title and goal must hold to carry it


def clause_words(text):
    return {w for w in re.findall(r"[a-z0-9_]+", str(text).lower()) if len(w) > 3}


def goal_clause_lines(bl, sid, items):
    """close --summary's clause lines: the sprint's goal split into its clauses, each with the done item of the sprint
    whose title and goal hold at least CLAUSE_COVER of its words, or `unmet` and the open item outside the sprint that
    carries it now (moved out mid-sprint), or none."""
    clauses = [c.strip(" .") for c in CLAUSE_SPLIT.split(str(bl.items[sid].get("goal", ""))) if c.strip(" .")]
    if len(clauses) < 2:
        return []

    def best(cw, ids):
        scored = [(len(cw & clause_words(f"{bl.items[i].get('title', '')} {bl.items[i].get('goal', '')}")) / len(cw), i)
                  for i in ids]
        top = max(scored, default=(0, None))
        return top[1] if top[0] >= CLAUSE_COVER else None
    done = [i for i in items if bl.items[i].get("status") == "done" and not bl.items[i].get("review")
            and not bl.items[i].get("goal_research")]
    elsewhere = [i for i, it in bl.items.items() if i not in items and it.get("kind") not in ("sprint", "epic")
                 and it.get("status") not in ("done", "dropped")]
    out = ["goal clauses:"]
    for n, c in enumerate(clauses, 1):
        cw = clause_words(c)
        by = best(cw, done) if cw else None
        if by:
            out.append(f"  {n}. {c[:120]}: {bl.label(by)}")
        else:
            now = best(cw, elsewhere) if cw else None
            out.append(f"  {n}. {c[:120]}: unmet, carried by {bl.label(now) if now else 'no item'}")
    return out


def cmd_close(bl, a):
    if a.summary and a.commit:
        raise Refused("close --summary only prints and commits nothing: run close --commit without --summary")
    sid = need(bl, a.sprint)
    items = bl.sprint_items(sid)
    left = [i for i in items if bl.items[i].get("status") not in ("done", "dropped")]
    if left:
        raise Refused(f"{bl.label(sid)} is not finished:\n  " + "\n  ".join(line(bl, i) for i in left))
    gone = set(items)
    epics = {p for i in items for p in bl.ancestors(i) if bl.items[p].get("kind") == "epic"}
    for e in epics:
        rest = [c for c in bl.descendants(e) if c not in gone]
        if bl.items[e].get("status") == "done" and not rest:
            gone.add(e)
    summary = [f"delivered by {bl.label(sid)}:"] + [summary_line(bl, i, gone)
                                                  for i in sorted(gone, key=lambda i: summary_key(bl, i))]
    if a.summary:
        summary += goal_clause_lines(bl, sid, items)
    if a.summary:  # the runbook prints the list, writes the retrospective, then closes: --summary changes nothing
        for x in summary:
            say(x)
        return 0
    title = bl.items[sid].get("title", "")
    record_close(bl, sid, items)  # the facts of the sprint that the deletion below takes from the tree
    for i in gone:
        say(f"deleted {line(bl, i)}")
    # a remaining item's relates_to is information only, and a depends_on on a deleted item that is not dropped is
    # satisfied (close refuses while anything is open): drop those ids, or check fails on dangling links and horizon
    # counts the item as waiting outside its sprint. A dependency on a dropped item stays for check to report.
    dead = gone | {sid}
    for i, it in sorted(bl.items.items()):
        if i in dead:
            continue
        cut = []
        for f in ("relates_to", "depends_on"):
            ids = it.get(f)
            if not isinstance(ids, list):
                continue
            off = [r for r in ids if r in dead and (f == "relates_to" or bl.items[r].get("status") != "dropped")]
            if not off:
                continue
            keep = [r for r in ids if r not in off]
            if keep:
                it[f] = keep
            else:
                it.pop(f)
            cut.append(f"{f} {', '.join(off)}")
        if cut:
            bl.save(it)
            say(f"dropped {'; '.join(cut)} from {bl.label(i)}")
    for i, gate, opt, target in cleanup_gate_do(bl, dead):  # a gate's do names an item by id too
        say(f"dropped gate {gate} do {opt!r} (item {target}) from {bl.label(i)}")
    for i in gone:
        bl.delete(i)
    label = bl.label(sid)
    bl.delete(sid)
    say(f"closed {label}; its items stay in git history (git log --grep 'KB-Work: <id>')")
    # the body is the summary: the retrospective's findings, written by hand, go in with git commit --amend
    commit_written(bl, a, "close", sid, body="\n".join(summary), title=title)
    try:  # the workers' leftovers go last, and whatever goes wrong there never undoes or fails the close
        clean_worker_leftovers(bl.root, sid, sorted(gone))
    except Exception as e:  # noqa: BLE001
        say(f"close: kept the worker leftovers of {sid}: {e}")
    return 0


PRECHECK_NOTE = "passes before the work"  # an item's notes saying so keep its passing checks out of precheck's warnings


def precheck_rows(bl, sid):
    """[(item id, check, exit code, passed)] of each check of the sprint's open committed items, run once on the checkout as
    it is (before any work commit); the review and research stories, whose checks pass by design, are left out."""
    rows = []
    for iid in sorted(bl.sprint_items(sid)):
        it = bl.items[iid]
        if it.get("status") not in ("draft", "todo", "doing") or it.get("review") or it.get("goal_research"):
            continue
        for c in it.get("checks", []) or []:
            ok, code, _ = run_check(bl.root, c)
            rows.append((iid, c, code if code is not None else -1, ok))
    return rows


def cmd_precheck(bl, a):
    """precheck SP: run each committed item's checks once before any work and warn (exit 0) of each that passes
    already: it proves nothing yet, unless the item's notes say the check passes before the work (one that pins
    behaviour that must stay). kb-sprint plan runs it before the start gate is asked, so start stays fast."""
    sid = need(bl, a.sprint)
    if bl.items[sid].get("kind") != "sprint":
        raise Refused(f"precheck needs a sprint: {bl.label(sid)} is a {bl.items[sid].get('kind')}")
    rows = precheck_rows(bl, sid)
    passing = 0
    for iid, c, code, ok in rows:
        if not ok or PRECHECK_NOTE in (bl.items[iid].get("notes") or ""):
            continue
        passing += 1
        say(f"warning: {bl.label(iid)}: `{shlex.join(c['run'])}` already exits {code} before the work: it proves "
            f"nothing yet; make it fail until the work is done, or say in the item's notes that it {PRECHECK_NOTE} "
            "and why (a check that pins behaviour that must stay)")
    say(f"precheck {bl.label(sid)}: checks={len(rows)} passing={passing}")
    return 0


def args_done(p):
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")


def args_land(p):
    p.add_argument("id")
    p.add_argument("--branch", help="the local branch to land (default work/ID)")
    p.add_argument("--wait-merge", type=int, metavar="SECONDS",
                   help="after a code item's first pass, wait up to SECONDS for its merge request (read from git "
                        "every 60 s), then run the second pass")
    p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                   help="a trailer of the session's own for the done --commit commit (repeatable)")


def merge_target(bl, iid):
    """(branch, project url) `backlog.py merge ID` merges: the item's own code/ID on the integration remote's GitLab
    project; Refused for an unknown item or a remote that names no GitLab project."""
    import kbpublic
    from ql_deliver import origin_forge
    need(bl, iid)
    remote = kbpublic.integration_remote(bl.root)
    code, url, _ = run(["git", "remote", "get-url", remote], cwd=bl.root)
    url = (url or "").strip()
    if code or not url or url.lower().startswith("file:") or Path(url).exists():
        raise Refused(f"the integration remote {remote} names no GitLab project ({url or 'no url'})")
    forge, host, project = origin_forge(url)
    if forge != "gitlab":
        raise Refused(f"the integration remote {remote} is on {forge}, not GitLab")
    return f"code/{iid}", f"https://{host}/{project}"


def cmd_merge(bl, a):
    """Merge the item's own code/ID merge request on the integration remote's project, now (`glab mr merge
    --auto-merge=false --yes`): the one way an agent merges, since .claude/settings.json allows no `glab mr merge`.
    Another item's branch and another project are refused (exit 2). Its state is read first (`glab mr view -F json`):
    one auto-merge already merged is reported merged, exit 0, so land runs next; a closed one is exit 1; only an open
    one is merged (glab refuses a merged one before any call)."""
    branch, project = merge_target(bl, a.id)
    # its state first: auto-merge may have merged it seconds before, and glab then refuses with no open request
    vcode, vout, _ = run(["glab", "mr", "view", branch, "-F", "json", "-R", project], cwd=bl.root)
    try:
        view = json.loads(vout) if not vcode else {}
    except ValueError:
        view = {}
    state = view.get("state") if isinstance(view, dict) else None
    if state == "merged":
        say(f"merge {branch} ({project}): already merged" + (f" at {view['merged_at']}" if view.get("merged_at") else ""))
        return 0
    if state == "closed":
        say(f"merge {branch} ({project}): the merge request is closed, not merged")
        return 1
    code, out, err = run(["glab", "mr", "merge", branch, "--auto-merge=false", "--yes", "-R", project], cwd=bl.root)
    say(f"merge {branch} ({project}): {'merged' if code == 0 else 'failed'}")
    text = (out or err or "").strip()
    if text:
        say(text[-600:])
    return 0 if code == 0 else 1


def args_merge(p):
    p.add_argument("id", help="the item whose code/ID merge request to merge")


def args_close(p):
    p.add_argument("sprint")
    p.add_argument("--summary", action="store_true",
                   help="only print each item close would delete with its status and evidence commit (the close "
                        "commit's body); changes nothing")


bl_cli.register("done", cmd_done, args_done)
bl_cli.register("precheck", cmd_precheck, lambda p: p.add_argument("sprint"))
bl_cli.register("land", cmd_land, args_land)
bl_cli.register("merge", cmd_merge, args_merge)
bl_cli.register("close", cmd_close, args_close)
bl_cli.register("tidy", cmd_tidy, args_tidy)
