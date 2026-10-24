"""The housekeeping side of backlog.py (kb/_self/backlog.md, Landing and Running a sprint; kb/_self/tools.md): `close`,
which deletes a finished sprint with its items and finished epics, with the goal clauses it reports (`clause_words`,
`goal_clause_lines`, `clauses_left_behind`) and `cleanup_gate_do`; with the worker's worktree and branches that `land`
shares with it and with `tidy`, which lives in `bl_clean` (`process_cwds`, `live_processes`, `release_worker_worktree`,
`delete_landed_branch`, `held_by_process`, `wait_for_hooks`, `worktree_entries`, `merged_into`) and the repositories'
leftovers `close` cleans (`clean_repository_leftovers`).

Standard library only; imports `bl_base` and `bl_intake` and never `bl_land` or `backlog`: `bl_land` imports this module,
so every name the other modules read as `bl_land.NAME` stays importable from there. It registers `close` with
`bl_cli` itself when imported (`backlog.py`'s USAGE puts it in its usage position)."""
import contextlib, json, os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path

import bl_cli
import bl_intake
from bl_base import (
    Refused, commit_written, git, goal_clauses, id_re, item_repos, line, main_worker_dir, main_worktree, need,
    rel_dir, repo_branch, repositories, research_touches, run, say, worker_dirs,
)


def gone_checks(it):
    """The commands (argument lists) of a done item's checks that an earlier rerun found gone: its evidence's `gone`."""
    ev = it.get("evidence")
    return [list(g) for g in ev.get("gone", []) if isinstance(g, list)] if isinstance(ev, dict) else []


def land_stop(step, why):
    return Refused(f"land stopped at step {step}: {why}")


def has_ref(root, ref):
    return subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode == 0


# the lock Claude Code puts on a subagent's worktree, which outlives the agent when it left background work running
WORKER_LOCK = "claude agent"


WORKER_NAME = "agent-"  # how the Agent tool names a worker's isolation worktree: an unlocked one is removed only so


WORK_PREFIX = "work/"  # the local branch a worker commits on: land deletes it once it has landed


AGENT_BRANCH = "worktree-"  # + the worktree's name: the branch the Agent tool made the worker's worktree on


def process_cwds():
    """([(pid, command, working directory)], None) of every process this host lets the user read, or (None, why) when it
    gives no way to tell: Linux reads /proc/<pid>/cwd, other POSIX hosts (macOS) ask `lsof -d cwd` once for every
    process's working directory; Windows exposes no process's working directory to the standard library. Never signals
    a process."""
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
            out.append((int(d.name), comm, cwd))
        return out, None
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
        elif ln.startswith("n") and pid is not None:
            out.append((pid, comm, ln[1:]))
    if not seen:  # lsof lists at least itself: nothing read means it could not look
        return None, f"lsof listed no process (exit {p.returncode})"
    return out, None


def processes_in(table, path):
    """[(pid, command)], sorted, of the processes in TABLE (`process_cwds`) whose working directory is PATH or under it."""
    target = os.path.realpath(path)
    prefix = target.rstrip(os.sep) + os.sep
    return sorted({(pid, comm) for pid, comm, cwd in table if cwd == target or cwd.startswith(prefix)})


def live_processes(path):
    """([(pid, command)], None) of the processes whose working directory is PATH or under it, or (None, why) when this
    host gives no way to tell (`process_cwds`; Windows: release_worker_worktree tries held_by_process instead). Never
    signals a process."""
    table, why = process_cwds()
    return (None, why) if table is None else (processes_in(table, path), None)


HOOK_POLL_S = 1  # seconds between two looks at a worktree's processes while land waits for a session's end hook


def wait_for_hooks(path, procs, root=None, wait=None, poll=HOOK_POLL_S, clock=time.monotonic, sleep=time.sleep):
    """([(pid, command)] still there, seconds waited, pids of the session-end hooks seen): of the processes
    live_processes found in the worktree PATH (PROCS), once none is left or after at most WAIT seconds (default
    `bl_procs.HOOK_GRACE_S`). A finished worker's session-end hook (the querylog.py distill its SessionEnd starts
    detached, its parent gone from the start) runs for seconds after the session exits, so only a process whose parent
    is gone is waited for; one whose parent lives is a session's own work, and a host that cannot read the process
    table is not waited on. A hook is told by the file its standard output is (`bl_procs.hook_pids`), never by a
    command line. Never signals a process."""
    import bl_procs
    wait = bl_procs.HOOK_GRACE_S if wait is None else wait
    start = clock()
    hooks = set()
    while procs:
        tab = bl_procs.process_table()
        if tab is None or any(pid in tab and not bl_procs.orphaned(tab, pid) for pid, _ in procs):
            break
        hooks |= bl_procs.hook_pids(root or path, [pid for pid, _ in procs])
        if clock() - start >= wait:
            break
        sleep(poll)
        again, _ = live_processes(path)
        procs = again or []
    return procs, max(0, int(clock() - start)), hooks


def still_running_remedy(pids, hooks):
    """What land tells the operator to do about the processes PIDS still running in a worker's worktree, HOOKS of them
    session-end hooks: a hook's distill waits up to ql_distill.USAGE_LOCK_WAIT_S for the lock, longer than land waits,
    and ends on its own, so land is run again; any other process is the worker's background work, ended."""
    others = [pid for pid in pids if pid not in hooks]
    steps = []
    if others:
        steps.append("end it (the worker ends every background command and monitor it started)")
    if len(others) < len(pids):
        try:
            from ql_distill import USAGE_LOCK_WAIT_S
            limit = f"USAGE_LOCK_WAIT_S ({USAGE_LOCK_WAIT_S} s)"
        except ImportError:
            limit = "USAGE_LOCK_WAIT_S"
        steps.append(f"a session-end distill waits up to {limit} for the distill lock and ends on its own")
    return f"{', and '.join(steps)}; then run land again"


PROBE_SUFFIX = ".land-probe"  # + pid: the sibling name held_by_process renames a worktree to and back


def held_by_process(path):
    """Why the directory PATH cannot be moved, or None once it was renamed to a sibling and back: Windows locks a
    process's current directory while it runs ("That prevents the directory from being deleted, moved, or renamed",
    SetCurrentDirectory), and a file a process holds open, so a refused rename tells what live_processes cannot list
    there. On POSIX hosts the rename succeeds whatever runs there, so it proves nothing beyond the path being movable."""
    probe = path.with_name(f"{path.name}{PROBE_SUFFIX}-{os.getpid()}")
    if os.path.lexists(probe):
        return f"its probe name {probe.name} is taken"
    try:
        os.rename(path, probe)
    except OSError as e:
        return f"{type(e).__name__}: {e.strerror or e}"
    try:
        os.rename(probe, path)
    except OSError as e:
        return f"it was renamed to {probe} and could not be renamed back ({e.strerror or e}): rename it back by hand"
    return None


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


def intake_draft_re():
    """An untracked item file of the intake, in `git status --porcelain` form."""
    return re.compile(r"\?\? (" + re.escape(rel_dir()) + r"/[^/\"]+\.json)")


def intake_drafts(path, status_lines, branch=None):
    """[relative path] of the untracked kb/_self/backlog/*.json files in `git status --porcelain -uall` STATUS_LINES of
    the worktree PATH that no commit of BRANCH (or of the worktree's HEAD) names: the drafts the SessionStart intake
    hook files (`backlog.py intake --file --hook`); any other line (modified, staged, another untracked file) is not one."""
    found = []
    for line in status_lines:
        m = intake_draft_re().fullmatch(line)
        if not m:
            continue
        named = subprocess.run(["git", "log", "-1", "--format=%H", branch or "HEAD", "--", m.group(1)], cwd=path,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not named.returncode and not named.stdout.strip():
            found.append(m.group(1))
    return found


def own_checkout_drafts(root, status_lines):
    """[relative path] of the intake drafts of the checkout ROOT that land runs in, when `git status --porcelain -uall`
    STATUS_LINES hold nothing else: each an untracked kb/_self/backlog/*.json that no commit of HEAD names and whose
    links carry a `fingerprint` and a `detector` (a filed intake candidate, not a hand-filed item). One other line,
    or one untracked item file that is no such draft, makes it [], so nothing is moved and `clean tree` refuses."""
    drafts = intake_drafts(root, status_lines)
    if len(drafts) < len(status_lines):
        return []
    for rel in drafts:
        try:
            links = json.loads((Path(root) / rel).read_text(encoding="utf-8")).get("links")
        except (OSError, ValueError, AttributeError):
            return []
        links = [x for x in links if isinstance(x, str)] if isinstance(links, list) else []
        if not (bl_intake.detector_of({"links": links}) and any(
                x.startswith(bl_intake.FP_LINK) and bl_intake.FP_RE.fullmatch(x[len(bl_intake.FP_LINK):])
                for x in links)):
            return []
    return drafts


def set_aside_drafts(root, path, drafts):
    """Move the DRAFTS (relative paths) of the worktree PATH, a worker's or the checkout land runs in, to
    `bl_intake.INTAKE_ASIDE` of the clone's main worktree (ROOT itself when it is the main one, else the worktree
    `main_worktree` finds: where `bl_intake.set_aside_fingerprints` reads), under the worktree's name, never over a
    file there. Returns [(source, destination)] of those moved."""
    moved = []
    aside = Path(main_worktree(root))
    for rel in drafts:
        src = Path(path) / rel
        dest = aside.joinpath(*bl_intake.INTAKE_ASIDE, Path(path).name, src.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = dest.with_name(f"{dest.stem}-{int(time.time())}{dest.suffix}")
        shutil.move(str(src), str(dest))
        moved.append((src, dest))
    return moved


def release_worker_worktree(root, path, lock, branch=None, repo=None, check_only=False, iid=None):
    """Remove the finished worker's worktree PATH that holds the branch land needs, with `git worktree remove` (never
    --force), unlocking it first when Claude Code locked it: agents' shells may not remove a worktree
    (.claude/settings.json denies it), so land, a process of its own, does. Only a worktree under the clone's
    .claude/worktrees/ of the clone land runs in (`git rev-parse --show-toplevel` there: a linked worktree is its own
    clone, its workers sit under its own directory; with BRANCH given, also that of the main checkout it is a linked
    worktree of, `main_worker_dir`: the Agent tool made the worker there) that is not the one land runs in, has no
    uncommitted changes
    (except untracked intake drafts that no commit of BRANCH names: moved to INTAKE_ASIDE of ROOT's main worktree, and said) and no
    live process (one whose parent has exited, a session-end hook's, is waited for, at most
    `bl_procs.HOOK_GRACE_S`: wait_for_hooks; where live_processes cannot list them, Windows, one the worktree cannot be
    renamed and back past:
    held_by_process), is on BRANCH when that is given, and is either locked by a Claude Code agent (WORKER_LOCK) or,
    unlocked, named as the Agent tool names a worker's (WORKER_NAME, `agent-*`; the test
    land_removes_clean_unlocked_worker_worktree) or by the item id of BRANCH (`work/<id>`; the test
    land_removes_worker_worktree_of_a_linked_clone_named_by_item_id). Returns None once it is removed,
    else why it was left as it was (a remove that fails puts the lock back). REPO is the checkout of a repository of a
    multi-repository workspace (whose branch is the `naming` one, so IID names the item) whose worktree PATH is (`<worker dir>/<id>/<repository>`, `repo_worktree`): the
    worktree commands run there, any lock refuses it (no Claude Code agent made it), and the name rule is the
    directory's, the item id. With CHECK_ONLY it only answers: None means every rule above holds and `land` would
    remove it, and nothing is moved, unlocked or removed."""
    home = Path(repo) if repo is not None else Path(root)

    def run_git(*args, cwd=None):
        p = subprocess.run(["git", *args], cwd=cwd or home, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return p.returncode, (p.stdout if not p.returncode else (p.stderr or p.stdout)).strip()

    state = "not locked" if lock is None else f"locked ({lock})"
    item_id = iid or (branch[len(WORK_PREFIX):] if branch and branch.startswith(WORK_PREFIX) else None)
    if lock is not None and (repo is not None or not lock.startswith(WORKER_LOCK)):
        return f"it is locked ({lock or 'no reason given'})" + ("" if repo is not None else
                                                                ", not by a Claude Code agent")
    parent = path.resolve().parent
    expected = set(worker_dirs(root))
    main_dir = main_worker_dir(root) if branch and repo is None else None
    if main_dir is not None:  # land of one item's branch from a linked worktree: the main checkout's workers too
        expected.add(main_dir)
    if repo is not None:  # <worker dir>/<id>/<repository>
        outside = parent.parent not in expected or parent.name != item_id
    else:
        outside = parent not in expected
    if outside:
        return f"it is {state} but not under {' or '.join(str(d) for d in sorted(expected))}"
    if path.resolve() == Path(root).resolve():
        return f"it is {state} and is the worktree land runs in"
    if repo is None and lock is None and not path.name.startswith(WORKER_NAME) and path.name != item_id:
        return f"it is not locked and not a worker's ({WORKER_NAME}*)"
    if branch:
        code, out = run_git("symbolic-ref", "-q", "HEAD", cwd=path)
        if code:  # detached: accepted only at the branch's tip (the worker detached there to free the branch)
            head, tip = run_git("rev-parse", "HEAD", cwd=path), run_git("rev-parse", "-q", "--verify", f"refs/heads/{branch}")
            if head[0] or tip[0] or head[1] != tip[1]:
                return f"it is {state} but not on {branch}"
        elif out != f"refs/heads/{branch}":
            return f"it is {state} but not on {branch}"
    code, out = run_git("status", "--porcelain", "-uall", cwd=path)
    dirty = out.splitlines()
    drafts = [] if code or repo is not None else intake_drafts(path, dirty, branch)  # a repository holds no intake
    if code or len(drafts) < len(dirty):
        return f"it is {state} and has uncommitted changes: commit or discard them there, then run land again"
    procs, unchecked = live_processes(path)
    if procs:  # a finished session's end hook runs on for seconds: wait for it, then refuse what is still there
        procs, waited, hooks = wait_for_hooks(path, procs, root)
        if procs:  # the worker left background work running there: removing the worktree would pull it from under it
            named = ", ".join(f"pid {pid} ({comm or '?'}{', a session-end hook' if pid in hooks else ''})"
                              for pid, comm in procs)
            return (f"it is {state} and a process still runs there{f' after {waited}s' if waited else ''}: {named}; "
                    f"{still_running_remedy([pid for pid, _ in procs], hooks)}")
        if waited:
            say(f"land: waited {waited}s in {path.name} for the session-end hook to end"
                if hooks else f"land: waited {waited}s in {path.name} for a process whose parent had exited to end")
    if unchecked:  # Windows: a rename to a sibling and back fails while a process has it as its working directory
        held = held_by_process(path)
        if held:
            return (f"it is {state} and could not be moved ({held}): a process may still run there, its working "
                    f"directory in it ({unchecked}, so land cannot name it); end it, then run land again")
        if not check_only:
            say(f"land: could not check {path} for live processes ({unchecked}); it could be renamed and back, so "
                "no process holds it; removing it as a clean worker's")
    if check_only:
        return None
    kept = set_aside_drafts(root, path, drafts)

    def put_back():
        for src, dest in kept:
            if dest.is_file() and not src.exists():
                shutil.move(str(dest), str(src))
    if lock is not None:
        code, out = run_git("worktree", "unlock", str(path))
        if code:
            put_back()
            return f"git worktree unlock: {out}"
    code, out = run_git("worktree", "remove", str(path))
    if code:
        put_back()
        if lock is not None:
            run_git("worktree", "lock", "--reason", lock, str(path))
        return f"git worktree remove: {out}"
    for _, dest in kept:
        say(f"land: moved the untracked intake draft {dest.name} out of the worker's worktree to {dest.parent} "
            "(copy it back to kb/_self/backlog/ to triage it)")
    say(f"land: removed the finished worker's worktree {path} ({'unlocked; its lock was: ' + lock if lock else 'it was not locked'})")
    return None


LANDING_LOCK = "kb-landing.lock"  # in the clone's git common directory: one landing of the clone runs at a time
LANDING_NAME = "land-"  # + the item id: the landing worktree's directory name, neither a worker's (agent-*) nor an item id


def landing_lock_path(root):
    """The landing lock file of the clone ROOT belongs to: one for the main checkout and every linked worktree."""
    return (Path(root) / git(root, "rev-parse", "--git-common-dir").strip()).resolve() / LANDING_LOCK


def landing_holder_item(text):
    """The item id a landing lock file's text names, '?' when it names none."""
    for ln in (text or "").splitlines():
        if ln.startswith("item="):
            return ln[len("item="):] or "?"
    return "?"


@contextlib.contextmanager
def landing_lock(root, iid, poll=None):
    """Hold the clone's landing lock for the block: an O_EXCL file whose record names the item being landed (pid,
    clone, start, item). A second landing of the clone says which item holds it and waits, a holder whose pid no longer
    runs is cleared, and `kg_lock.max_wait()` seconds of waiting for a live one stop the landing at step `landing
    lock`. The lock is released on exit, on an error and on SIGTERM. The mechanism is the host main lock's
    (`kg_lock.main_lock`), on a file of the clone's own."""
    import signal
    import tests as tests_py
    import kg_lock
    path = str(landing_lock_path(root))
    poll = poll if poll is not None else float(os.environ.get("KB_HOST_LOCK_POLL", "1"))
    me = (f"pid={os.getpid()}\nclone={root}\nstarted={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
          f"item={iid}\n")
    told, waited, bound = None, 0.0, kg_lock.max_wait()
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            text = tests_py.read_lock(path)
            if text is None and not os.path.exists(path):  # released: look again
                continue
            holder = tests_py.parse_holder(text or "")
            if holder is None:
                try:
                    young = time.time() - os.stat(path).st_mtime < tests_py.lock_grace()
                except OSError:
                    continue
                if young:  # its holder has not written the record yet
                    time.sleep(poll)
                    continue
            if holder is None or not tests_py.pid_alive(holder["pid"]):
                if tests_py.clear_stale(path, text):
                    say(f"land: clearing a stale landing lock ({holder['pid'] if holder else 'unreadable'})")
                continue
            item = landing_holder_item(text)
            if holder != told:
                say(f"land: waiting for the landing lock of this clone, held by the landing of {item} "
                    f"(pid {holder['pid']}, started {holder['started']})")
                told = holder
            if waited >= bound:
                raise land_stop("landing lock", f"the landing of {item} (pid {holder['pid']}, started "
                                                f"{holder['started']}) still holds the clone's landing lock after "
                                                f"{bound:g} s: run land again once it has ended")
            began = time.monotonic()
            time.sleep(poll)
            waited += time.monotonic() - began
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(me)
        break
    prev = None
    try:
        prev = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    except (ValueError, OSError):  # not the main thread
        pass
    try:
        yield path
    finally:
        if prev is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGTERM, prev)
        holder = tests_py.read_holder(path)
        if holder and holder["pid"] == os.getpid():
            with contextlib.suppress(OSError):
                os.unlink(path)


def landing_worktree_path(root, iid):
    """Where item IID's landing worktree is: `land-<id>` in the worker directory of the clone ROOT belongs to."""
    return next(iter(worker_dirs(root))) / (LANDING_NAME + iid)


def remove_landing_worktree(root, path):
    """Remove the landing worktree PATH, whatever it holds (it is land's own, made detached for one run), and prune
    the clone's worktree records; the checkout land was started in is never touched."""
    subprocess.run(["git", "worktree", "remove", "--force", "--force", str(path)], cwd=root, capture_output=True)
    if Path(path).exists():
        shutil.rmtree(path, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=root, capture_output=True)


def add_landing_worktree(root, iid, rev):
    """Make item IID's landing worktree: a detached checkout of REV under the clone's worker directory, and return its
    path. A leftover of an earlier landing that was killed (the landing lock is held, so none is running) is removed
    first. Raises the landing stop at step `landing worktree` when git cannot make it."""
    path = landing_worktree_path(root, iid)
    remove_landing_worktree(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["git", "worktree", "add", "--detach", "-q", str(path), rev], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise land_stop("landing worktree", f"git worktree add {path.name}: {(p.stderr or p.stdout).strip()}")
    return path


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


def repo_worktree(root, iid, name):
    """The worktree dispatch makes of repository NAME for item IID: `<worker dir>/<id>/<repository>`."""
    return next(iter(worker_dirs(root))) / iid / name


def local_default_ref(checkout):
    """`refs/remotes/origin/<default>` as the checkout has it (`origin/HEAD`, else origin's main or master), or None;
    nothing is fetched (close reads it)."""
    p = subprocess.run(["git", "symbolic-ref", "-q", "refs/remotes/origin/HEAD"], cwd=checkout, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    for ref in ([p.stdout.strip()] if p.returncode == 0 else []) + [f"refs/remotes/origin/{b}" for b in ("main", "master")]:
        if ref and has_ref(checkout, ref):
            return ref
    return None


def repo_branch_or_none(it, iid):
    """The item's repository branch (`bl_base.repo_branch`), None (so the default `work/<id>`) for an item whose naming
    cannot be filled: close never stops on it."""
    try:
        return repo_branch(it, iid)
    except Refused:
        return None


def clean_repository_leftovers(root, iid, checkouts, branch=None):
    """What `land` left of the item IID's repositories CHECKOUTS ([(name, checkout)]), for close: each worktree
    dispatch made (`repo_worktree`) that is clean, unlocked, free of processes and has every commit on the
    repository's default branch as the checkout has it last fetched (the directory `<worker dir>/<id>` goes with the
    last one), then BRANCH (the `naming` branch, `repo_branch`; default `work/<id>`) when every commit of it is there. Anything else is kept and `close: kept
    ...: why` says why. Returns the number kept."""
    kept, branch = 0, branch or WORK_PREFIX + iid

    def keep(what, why):
        nonlocal kept
        kept += 1
        say(f"close: kept {what}: {why}")

    for name, checkout in checkouts:
        wt = repo_worktree(root, iid, name)
        if not (checkout / ".git").exists():
            if wt.is_dir():
                keep(wt, f"repository {name!r} has no checkout at {checkout}")
            continue
        upstream = local_default_ref(checkout)
        entry = next((e for e in worktree_entries(checkout) if e["path"] == wt.resolve()), None)
        if upstream is None:
            if entry or has_ref(checkout, f"refs/heads/{branch}"):
                keep(f"repository {name!r}", "no default branch of its origin as fetched to compare against")
            continue
        if entry:
            if not merged_into(checkout, entry["head"], upstream):
                keep(wt, f"it has commits {upstream} lacks")
                continue
            why = release_worker_worktree(root, entry["path"], entry["lock"], branch, repo=checkout, iid=iid)
            if why:
                keep(wt, why)
                continue
        if has_ref(checkout, f"refs/heads/{branch}") and not delete_landed_branch(checkout, branch, upstream,
                                                                                  who=f"close: repository {name}",
                                                                                  prefixes=(branch,)):
            kept += 1
    try:  # the item's directory of repository worktrees, once nothing is left in it
        repo_worktree(root, iid, "x").parent.rmdir()
    except OSError:
        pass
    return kept


def summary_key(bl, iid):
    """Tree order: each item under its parent, the tops (epics, then the sprint's stories and bugs) in work order."""
    return [bl.order_key(x) for x in reversed([iid] + bl.ancestors(iid))]


def summary_line(bl, iid, gone):
    """One commit-body line for an item close deletes: its id, title, kind, status and the commit done recorded, with
    the checks the review's rerun found gone (gone_checks)."""
    it = bl.items[iid]
    depth = sum(1 for p in bl.ancestors(iid) if p in gone)
    ev = (it.get("evidence") or {}).get("commit") if isinstance(it.get("evidence"), dict) else None
    at = f" at {ev[:10]}" if ev else ", no evidence commit"
    dead = "".join(f"; gone check: {shlex.join(g)}" for g in gone_checks(it))
    return f"{'  ' * depth}- {bl.label(iid)} ({it.get('kind', '')}): {it.get('status', '')}{at}{dead}"


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
                                 f"{rel_dir()}/{sid}.json").split()]
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


REOPENED_REFS = "refs/kb-reopened/"  # reopen keeps a done item's file there, one ref per item id (bl_items)


def tree_item_ids(root, rev, rel):
    """The ids of the item files in directory REL of REV's tree (empty when REV or REL cannot be read)."""
    code, out, _ = run(["git", "ls-tree", "--name-only", f"{rev}:{rel}"], cwd=root)
    return set() if code else {n[:-len(".json")] for n in out.split() if n.endswith(".json")}


def prune_reopened_refs(bl):
    """Delete each refs/kb-reopened/<id> whose item file <id>.json no longer exists in the backlog directory: close and
    drop outside a sprint call it after their deletions, so the clone keeps no reopen mark of a removed item, the
    items they remove now and any left by earlier removals alike. The refs are shared by every worktree of the
    clone, so the checkout alone does not judge: a ref of an item the integration main holds that this checkout
    never held (its file is on `<remote>/main`, in neither HEAD nor the merge base) is kept, since it was filed on
    main after the checkout branched; and with no `<remote>/main` to read, every ref is kept. A ref of an existing
    item stays. Returns the ids whose ref was deleted."""
    import kbpublic
    root = bl.root
    code, out, _ = run(["git", "for-each-ref", "--format=%(refname)", REOPENED_REFS], cwd=root)
    refs = [] if code else out.split()
    main = f"refs/remotes/{kbpublic.integration_remote(root)}/main"
    if not refs or not has_ref(root, main):
        return []
    rel = bl.dir.relative_to(root).as_posix()
    known = tree_item_ids(root, "HEAD", rel)
    code, base, _ = run(["git", "merge-base", "HEAD", main], cwd=root)
    if not code and base.strip():
        known |= tree_item_ids(root, base.strip(), rel)
    filed_since = tree_item_ids(root, main, rel) - known
    gone = []
    for ref in refs:
        iid = ref[len(REOPENED_REFS):]
        if not iid or iid in filed_since or (bl.dir / f"{iid}.json").exists():
            continue
        if not run(["git", "update-ref", "-d", ref], cwd=root)[0]:
            gone.append(iid)
    if gone:
        say(f"deleted {len(gone)} reopen mark(s) of removed items: {', '.join(gone)}")
    return gone


def clean_worker_leftovers(root, sid, ids):
    """Remove what the closed sprint SID's workers left in the clone ROOT, as a process of its own because agents'
    shells may not run `git worktree remove` or `git branch -D` (.claude/settings.json; the repositories of a
    multi-repository item are cleaned by `clean_repository_leftovers`): the clean `agent-*` worktrees
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

    if not id_re().fullmatch(sid):
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


def cleanup_gate_do(bl, dead):
    """Drop every gate `do` entry of a remaining item that names (by item id) an item in DEAD, which close deletes: the
    work that entry waited for is done or dropped, and check refuses a `do` naming an item that does not exist. An
    emptied `do` goes with its last entry. Returns [(item id, gate id, option, the deleted item's id)]."""
    out = []
    for i, it in sorted(bl.items.items()):
        if i in dead or bl.is_upstream(i):  # an upstream item is read-only in this clone
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


PART_SPLIT = re.compile(r",\s+(?:and\s+)?|\s+and\s+")  # a list clause's parts: split at ', ' and ' and '


CLAUSE_COVER = 0.5 # the share of a clause's words an item's title, goal and mapped clauses must hold to carry it


CLAUSE_SIMILAR = 2  # the words an open item outside the sprint shares with an unmet clause to be named beside it


def fold_word(w):
    """A word without its plural or verb `s` (`keeps` is `keep`, `class` stays), so `rows` and `row` are one word."""
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


# words of four letters or more that name no work: function words and the backlog's own vocabulary, which a title or
# goal holds whatever it is about, so sharing one proves nothing (`close --summary` credited a story with a clause on
# `that`, `each`, `goal`, `story` and `clause` alone)
CLAUSE_STOPWORDS = frozenset((
    "that this these those each with from into onto over than then them they their there what which when where who "
    "have been were will would should could does only also such some more most both same just like about after "
    "before goal story storie clause item sprint").split())


def clause_words(text):
    """The words a clause is matched on: four letters or more, a plural or verb `s` folded, `CLAUSE_STOPWORDS` left
    out."""
    found = (w for w in re.findall(r"[a-z0-9_]+", str(text).lower()) if len(w) > 3)
    return {fold_word(w) for w in found if w not in CLAUSE_STOPWORDS and fold_word(w) not in CLAUSE_STOPWORDS}


def clause_parts(clause):
    """A clause that is a list of independent statements, split at ', ' and ' and ' into its parts with words."""
    return [p for p in (x.strip(" .") for x in PART_SPLIT.split(clause)) if clause_words(p)]


def item_words(bl, iid):
    """The words of an item's title, goal and mapped clauses (its `clauses` mapping) that a goal clause is matched
    against."""
    it = bl.items[iid]
    mapped = " ".join(str(e.get("clause", "")) for e in it.get("clauses") or [] if isinstance(e, dict))
    return clause_words(f"{it.get('title', '')} {it.get('goal', '')} {mapped}")


# the goal `new sprint` files on the sprint's goal research story: a research story still holding it has no narrowed goal
RESEARCH_DEFAULT_GOAL = (
    "The sprint goal's open questions are answered with the kb tools first and the live docs for the gaps, and the "
    "findings are written as kb facts and gap entries through the kb skills, so each committed item can name the "
    "knowledge it needs. Tested rows for kb/_self/_retrieval/lookup_eval.csv are a code-lane path (_tools/kblane.py): "
    "a story finished with them lands through backlog.py land ID --wait-merge SECONDS, not done --commit.")


def research_words(bl, iid):
    """The words a goal research story's fallback credit reads: its narrowed goal (nothing from a goal that still
    starts with the generated default), its mapped clauses and the path words of its touches. Never its title, which
    `new sprint` generates from the sprint's own title."""
    it = bl.items[iid]
    goal = str(it.get("goal") or "")
    default_lead = RESEARCH_DEFAULT_GOAL.partition(",")[0]  # the generated goal's first clause: a narrowed goal replaces it
    narrowed = "" if goal.strip().startswith(default_lead) else goal
    mapped = " ".join(str(e.get("clause", "")) for e in it.get("clauses") or [] if isinstance(e, dict))
    return clause_words(f"{narrowed} {mapped}") | touch_words(bl, iid)


def touch_words(bl, iid):
    """The words of the path of each of a story's touches inside a named kb root (`kb/public/intune/*.md`: `intune`),
    the root's name and the globs left out: what a research story's touches say it covers."""
    out = set()
    for t in bl.items[iid].get("touches") or []:
        if research_touches([t]):
            out |= clause_words(re.sub(r"[^a-z0-9]+", " ", t.split("/", 2)[2].lower()))
    return out


def carries_clause(bl, cw, iid, fallback=False):
    """The one carrier filter, read by `goal_clause_lines` and `clauses_left_behind`: the share of the clause's words
    (cw) item `iid` holds, 0 when it cannot carry. A review story never carries a clause; a goal research story carries
    one only as a fallback (`fallback`: `close --summary`, and the `move` message that follows it), by its narrowed
    goal, mapped clauses and its touches' path words (`research_words`), never by its generated title."""
    it = bl.items[iid]
    if not cw or it.get("review"):
        return 0
    if it.get("goal_research"):
        if not fallback:
            return 0
        words = research_words(bl, iid)
    else:
        words = item_words(bl, iid)
    share = len(cw & words) / len(cw)
    return share if share >= CLAUSE_COVER else 0


def clause_carriers(bl, cw, ids):
    """The done items of `ids` that carry the clause, the story (any kind but a bug) before a bug filed from it, each
    kind highest share first; with none, the goal research stories that carry it as the fallback."""
    done = [i for i in ids if bl.items[i].get("status") == "done"]
    ranked = sorted(((bl.items[i].get("kind") == "bug", -carries_clause(bl, cw, i), i) for i in done))
    got = [i for bug, share, i in ranked if share]
    if got:
        return got
    return [i for _, share, i in sorted((0, -carries_clause(bl, cw, i, fallback=True), i) for i in done
                                        if bl.items[i].get("goal_research")) if share]


def goal_clause_lines(bl, sid, items):
    """close --summary's clause lines: the sprint's goal split into its clauses, each with every done item of the
    sprint whose title, goal and mapped clauses hold at least CLAUSE_COVER of its words (a story before a bug filed
    from it, highest share first; with none, the goal research story whose narrowed goal or touches carry it), or
    `unmet` and, beside it, the open item outside the sprint that shares at least CLAUSE_SIMILAR words with it (named
    as similar, never as the clause's carrier)."""
    clauses = goal_clauses(bl.items[sid].get("goal", ""))
    if len(clauses) < 2 and not (clauses and len(clause_parts(clauses[0])) > 1):
        return []

    def similar(cw, ids):
        scored = [(-len(cw & item_words(bl, i)), i) for i in sorted(ids)]
        top = min(scored, default=(0, None))
        return top[1] if -top[0] >= CLAUSE_SIMILAR else None
    elsewhere = [i for i, it in bl.items.items() if i not in items and it.get("kind") not in ("sprint", "epic")
                 and it.get("status") not in ("done", "dropped")]
    out = ["goal clauses:"]
    def verdict(cw):
        by = clause_carriers(bl, cw, items) if cw else []
        if by:
            return ", ".join(bl.label(i) for i in by)
        now = similar(cw, elsewhere) if cw else None
        return f"unmet; similar open item outside the sprint: {bl.label(now)}" if now else "unmet"
    for n, c in enumerate(clauses, 1):
        cw = clause_words(c)
        parts = clause_parts(c)
        if len(parts) > 1 and not (cw and clause_carriers(bl, cw, items)):
            out.append(f"  {n}. {c[:120]}:")
            out.extend(f"     - {p[:100]}: {verdict(clause_words(p))}" for p in parts)
        else:
            out.append(f"  {n}. {c[:120]}: {verdict(cw)}")
    return out


def clauses_left_behind(bl, sid, iid):
    """The goal clauses of sprint `sid` that item `iid` carries (its title, goal and mapped clauses hold at least
    CLAUSE_COVER of the clause's words) and no other item of the sprint that is not dropped does, a goal research
    story's fallback credit (`carries_clause` with `fallback`) counting as another's: what moving `iid` out leaves in
    the goal unmet in `close --summary`. Its tasks and subtasks go with it; a review or goal research story moved
    carries nothing."""
    moving = {iid, *bl.descendants(iid)}  # its tasks and subtasks leave with it
    others = [i for i in bl.sprint_items(sid) if i not in moving and bl.items[i].get("status") != "dropped"]
    left = []
    for c in goal_clauses(bl.items[sid].get("goal", "")):
        cw = clause_words(c)
        if carries_clause(bl, cw, iid) and not any(carries_clause(bl, cw, i, fallback=True) for i in others):
            left.append(c)
    return left


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
    # counts the item as waiting outside its sprint. A dependency on a dropped item stays for check to report. An item
    # that arrived from the clone's upstream main is read-only here: it stays as the upstream wrote it.
    dead = gone | {sid}
    for i, it in sorted(bl.items.items()):
        if i in dead or bl.is_upstream(i):
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
    declared = repositories()  # each item's repositories, read before the deletion
    in_repos = {i: ([(n, Path(bl.root) / declared[n]) for n in item_repos(bl.items[i])], repo_branch_or_none(bl.items[i], i))
                for i in sorted(gone) if item_repos(bl.items[i])}
    for i in gone:
        bl.delete(i)
    label = bl.label(sid)
    bl.delete(sid)
    say(f"closed {label}; its items stay in git history (git log --grep 'KB-Work: <id>')")
    prune_reopened_refs(bl)
    # the body is the summary: the retrospective's findings, written by hand, go in with git commit --amend
    commit_written(bl, a, "close", sid, body="\n".join(summary), title=title)
    try:  # the workers' leftovers go last, and whatever goes wrong there never undoes or fails the close
        clean_worker_leftovers(bl.root, sid, sorted(gone))
        for i, (checkouts, branch) in in_repos.items():  # what land left of a multi-repository item's repositories
            clean_repository_leftovers(bl.root, i, checkouts, branch)
    except Exception as e:  # noqa: BLE001
        say(f"close: kept the worker leftovers of {sid}: {e}")
    return 0


def args_close(p):
    p.add_argument("sprint")
    p.add_argument("--summary", action="store_true",
                   help="only print each item close would delete with its status and evidence commit (the close "
                        "commit's body); changes nothing")


bl_cli.register("close", cmd_close, args_close)
