"""`backlog.py own` and `backlog.py tidy`: the record of what this clone's tools make and leave behind, and the one verdict
on whether a leftover may go (kb/_self/backlog.md, Leftovers; kb/_self/tools.md).

  own PATH --class worktree|sandbox|scratch [--item ID] [--sprint SP] [--session ID]   record the directory
  own PID  --class process [--item ID] [--sprint SP] [--session ID]                   record the process
  own TARGET --class C --drop                                                          clear the record
  tidy [--apply] [--json] [--older-than HOURS] [--disk-free-gb GB] [--class C]         list the recorded leftovers
  tidy --report                                                                        one line of counts and bytes a class
  tidy --path PATH [--apply] ...                                                       only the recorded leftover at PATH
  tidy --decide KEY remove|keep                                                        record the operator's answer to a row
  tidy --class process [--apply]                                                       list, and end, the recorded processes
  tidy --remote [--json]                                                               list the merged code/<id> branches of the remote

A record is one coord key, `own/<class>/<digest>`, whose value is a JSON object: the `path` (normalised) or the `pid`, the
class, the item, sprint and session when given, and `at`, the time it was recorded in seconds since the epoch; a process's
record also holds its `start` time when the host's process table gives one. The digest is the first 16
hex digits of the sha256 of the normalised path or of the pid's decimal text, so one directory is one key however it was
spelled (`norm_path`: realpath of its parents, then no `\\\\?\\` prefix, normcase, one case for a drive letter), on every
platform; a symlink at its end is not followed, so a link's record is the link's own path. The
coord store is the one `coord.py` finds (`--store`, else KB_COORD_STORE, else the common git directory of the clone
`--root` names, whatever the working directory; `kb-coord-home` under `--root` where that is no git clone), shared by the clone's worktrees. coord keeps no delete: `--drop` writes an empty value, which readers skip (`recorded`).

`record_owner` is the one writer: `dispatch` records the worker's worktree, scratch directory and pid through it, `bench
multi` its sandbox, and the sprint skill's run and review steps their worktrees with the `own` command. A record is a claim of
nothing: it says who made the path or process, never that it may be removed. Exit codes of `own`: 0 recorded or dropped, 1
coord refused or did not run, 2 a bad request.

`safe_to_remove(candidate, snapshot, coord_state)` is the one verdict, `(verdict, reason)` with the verdict `remove`,
`keep` or `ask` (below): a candidate goes only when its owner is recorded, no live coord lease or claim names it (or its branch, item or
session), no live process has it as its working directory, its item is done, dropped or gone with its closed sprint, it is
clean and every commit of it is on the integration main (`git cherry`), and its last activity is older than --older-than
hours; a recorded scratch or sandbox directory also lies in its class's own directories (`own_dirs`), is no symlink and
holds no worktree of this repository (`misplaced`); the main checkout, the worktree tidy runs in and
`_cache/querylog/worktree` always stay, and so does everything no record names. A plan reads the commit time of every
worktree head and branch tip, and whether the integration main lacks it, with two git processes (`prime`; one more a
`BATCH` of commits), however many candidates there are; only a commit it lacks is judged by `git cherry`, and `git status`
runs for a worktree only once every other check leaves it removable. `--apply` looks at a path again with lstat
(`is_recorded_dir`) and never removes a symlink's target. `tidy` lists each recorded worktree, local branch, bench sandbox and scratch directory with that verdict, its
reason and the bytes it frees (a walk of at most `BYTES_SECONDS` a candidate, `approximate` past it), one summary line a class;
--json prints the rows. Under disk pressure (free space below --disk-free-gb) the bench sandboxes come first and their age
limit is waived. --apply removes the `remove` rows with `git worktree remove` (never --force; a directory Windows refuses
to rename is kept and reported), a branch only once `git cherry` finds its commits on the integration main, then `git
worktree prune`. Exit codes of `tidy`: 0 listed, or removed all it planned; 1 an --apply removal failed or a claim appeared
on a candidate; 2 a refusal (bad arguments, no integration main, an unreadable coord store); 3 the coord store stayed locked.
A candidate that is recorded, clean, merged and idle but whose item is still claimed (`doing`) with no live coord lease or
claim naming it gets the verdict `ask`, as does a recorded process that outlives its session's lease while its item is
still claimed: nothing in the record tells whether the work went on, so only the operator settles it. Each row carries its
`key` (`worktree/<16 hex digits>`, from `cand_key`). `tidy --decide KEY remove|keep` writes the answer as the coord value
of `tidy-answer/<KEY>` with the time (refused, exit 2, in an agent session: `bl_authority.in_agent_session`); an answer
made before the candidate's record is stale. The next run reads it: `keep` is a `keep` row, `remove` a `remove` row with
`answer` set. `--apply` removes such a row only after it claims `clean/<KEY>` (`CLAIM_TTL` seconds, holder `tidy`): while
another holder has that claim it removes nothing, says so and exits 1; it releases the claim and clears the answer once the
candidate is gone. An uncommitted worktree is `keep` before it can ask, so a dirty one is reported for a hand clean.
`tidy --report` reads only and prints one line, the count that would go and the bytes it frees, and the count kept, for each
class; the bytes of all the rows share a `REPORT_SECONDS` walk, the figure `or more` past it, so the line comes within seconds
on a clone with many worktrees (the SessionStart hook prints it and removes nothing).

`tidy --path PATH` (repeatable) keeps only the recorded leftovers at those paths, listed or, with `--apply`, removed under the
same verdict as every row, so a session removes its own worktree and no other's; a path no `own` record names is refused
(exit 2) naming it, and nothing is removed. It takes neither `--report` nor `--class process`.

`tidy --class process` adds the class `process`, which no other run lists: each pid an own record names, and each process in a
checkout of the clone that no record names (`bl_procs.snapshot`; kept, never signalled, however old or orphaned: a parent of 1
proves nothing, a live detached worker has it). A recorded process goes only when it still runs as recorded (its start time
is the record's, within `START_SLOP_S`: a pid is reused), its record names a session that holds no coord lease or claim
(`session/<id>`), its item is finished and the record is older than --older-than; one that no longer runs goes with its
record alone, with no signal. `--apply` ends the `remove` rows with SIGTERM, then SIGKILL after `bl_procs.END_WAIT_S`
(`end_process`, after it reads the process table again), and is refused (exit 2) in an agent session
(`bl_authority.in_agent_session`). `tidy --remote` reads only: it lists the `code/<id>` branches of the integration remote,
as last fetched, whose commits `git cherry` finds on the integration main; no tidy run deletes a remote branch, and `--remote`
with --apply is refused (exit 2).

`land` and `close` call the two functions below for the leftovers of their own item or sprint, as processes of their own: `land_leftovers`
removes the landed item's recorded scratch directory (and the records of its worktrees git no longer lists), `close_leftovers`
the closed sprint's recorded scratch directories and worker worktrees, each with `safe_to_remove`'s verdict and the age limit
waived. The orchestrator's and the reviewer's worktrees (a record with a sprint and no item) stay for `tidy --apply`.

Standard library only; imports `bl_authority`, `bl_base`, `bl_cli`, `bl_close` and `bl_procs`, never `backlog` (a layer rule). It registers its own
subcommands when imported, so `backlog.py` carries only the import."""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import bl_authority
import bl_cli
import bl_close
import bl_procs
from bl_base import OUTPUT_ROOT, Refused, Rejected, git, git_text, run, say, scratch_dir
from bl_close import AGENT_BRANCH, WORK_PREFIX, WORKER_NAME

COORD = Path(__file__).resolve().parent / "coord.py"
CLASSES = ("worktree", "sandbox", "scratch", "process")
PREFIX = "own/"  # the coord keys of the records: own/<class>/<digest>
DIGEST_LENGTH = 16
COORD_SECONDS = 60
EXTENDED = "\\\\?\\"  # the Windows extended-length prefix
EXTENDED_UNC = EXTENDED + "UNC\\"
DRIVE = re.compile(r"[A-Za-z]:")
AGE_HOURS = 4  # --older-than: how long a leftover's last activity must be past
DISK_FREE_GB = 20  # --disk-free-gb: free space below it is disk pressure
BATCH = 400  # commit ids one batched git read takes (`prime`): the command line stays short on every host
BYTES_SECONDS = 2  # the longest walk that measures what one candidate frees
REPORT_SECONDS = 4  # the longest walk that measures what all the candidates of `tidy --report` free
TIDY_PREFIXES = (WORK_PREFIX, AGENT_BRANCH + WORKER_NAME, "orch/")  # the local branches tidy lists
TIDY_CLASSES = ("worktree", "branch", "sandbox", "scratch")
PROCESS = "process"  # tidy lists it only under `--class process`
REMOTE_BRANCHES = "code/"  # the branches `tidy --remote` lists on the integration remote
START_SLOP_S = 2  # how far a process's start time may differ from its record's: the table's seconds
FINISHED = ("done", "dropped")
REMOVE, KEEP, ASK = "remove", "keep", "ask"
ANSWER_PREFIX = "tidy-answer/"  # the coord keys of the operator's answers: tidy-answer/<candidate key>
CLAIM_PREFIX = "clean/"  # the coord key an --apply claims before it removes an answered candidate: clean/<candidate key>
CLAIM_TTL = 600  # seconds a removal's claim lasts
CLAIM_HOLDER = "tidy"
KEY_FORM = re.compile(r"(?:worktree|branch|sandbox|scratch|process)/[0-9a-f]{16}")


def strip_extended(path):
    """PATH without the `\\\\?\\` prefix (`\\\\?\\UNC\\host\\share` is `\\\\host\\share`)."""
    if path.startswith(EXTENDED_UNC):
        return "\\\\" + path[len(EXTENDED_UNC):]
    return path[len(EXTENDED):] if path.startswith(EXTENDED) else path


def is_link(path):
    """Whether PATH itself (not what it points at) is a symlink, or on Windows a junction."""
    return os.path.islink(path) or getattr(os.path, "isjunction", lambda _p: False)(path)


def spell(text):
    """TEXT without the extended-length prefix, normcase, and one (lower) case for a drive letter."""
    text = os.path.normcase(strip_extended(text))
    return text[0].lower() + text[1:] if DRIVE.match(text) else text


def norm_real(path):
    """PATH with every symlink resolved (realpath), spelled by `spell`: where a directory really is."""
    return spell(os.path.realpath(strip_extended(os.fspath(path))))


def norm_path(path):
    """The one spelling of a directory every record is keyed by: realpath of its parent, then its own name, without the
    extended-length prefix, normcase, and one (lower) case for a drive letter. A trailing separator, a relative path and
    (on Windows) a case or slash difference all give the same text; a symlink in the parents is resolved, but PATH
    itself being a symlink is not followed, so a record of a link is the link's own path, never its target's."""
    raw = strip_extended(os.fspath(path))
    bare = raw.rstrip("/\\")
    if bare and is_link(bare):
        parent, name = os.path.split(bare)
        return spell(os.path.join(os.path.realpath(parent or os.curdir), name))
    return norm_real(raw)


def subject(cls, target):
    """({"path": P} or {"pid": N}, the text the key's digest is of) for the TARGET of class CLS. Raises Rejected."""
    if cls not in CLASSES:
        raise Rejected(f"own: --class is one of {', '.join(CLASSES)}, not {cls!r}")
    if cls == "process":
        if not re.fullmatch(r"[0-9]{1,10}", str(target)) or int(target) < 1:
            raise Rejected(f"own: a process is recorded by its pid, a positive whole number, not {str(target)[:40]!r}")
        return {"pid": int(target)}, str(int(target))
    if not str(target):
        raise Rejected("own: a path is needed")
    path = norm_path(target)
    return {"path": path}, path


def owner_key(cls, ident):
    """The coord key of the record of IDENT (the normalised path, or the pid's text) of class CLS."""
    return f"{PREFIX}{cls}/{hashlib.sha256(ident.encode('utf-8')).hexdigest()[:DIGEST_LENGTH]}"


def in_clone(root):
    """Whether ROOT is in a git clone (what `coord.store_of` asks: git answers, else a `.git` in ROOT)."""
    if git_text(root, "rev-parse", "--git-dir"):
        return True
    return Path(root, ".git").exists()


def run_coord(*args):
    """(exit code, the JSON object coord.py printed or None, its last stderr line) of one coord.py command, run in the
    clone `--root` names (the script's own where none) so its default store is that clone's, whatever the working
    directory. A `--root` that is no git clone has no store of its own, and coord.py would fall back to the script's own
    clone's, so there the project coord.py serves is `kb-coord-home` under the root, whose `.git` directory marks it a
    clone and holds `kb-coord/coord.sqlite` (KB_COORD_STORE and `--store` still win)."""
    root = str(OUTPUT_ROOT[0])
    project = root
    if not os.environ.get("KB_COORD_STORE") and "--store" not in args and not in_clone(root):
        project = str(Path(root, "kb-coord-home"))
        try:
            Path(project, ".git").mkdir(parents=True, exist_ok=True)
        except OSError as error:
            return 2, None, f"no coord store under the root: {error.__class__.__name__}"
    env = {**os.environ, "CLAUDE_PROJECT_DIR": project}
    try:
        p = subprocess.run([sys.executable, str(COORD), *args], capture_output=True, text=True, encoding="utf-8",
                           stdin=subprocess.DEVNULL, timeout=COORD_SECONDS, cwd=root, env=env)
    except (OSError, subprocess.SubprocessError) as error:
        return 2, None, f"coord.py did not run: {error.__class__.__name__}"
    try:
        body = json.loads(p.stdout)
    except ValueError:
        body = None
    lines = [x.strip() for x in p.stderr.splitlines() if x.strip()]
    return p.returncode, body, lines[-1] if lines else ""


def host_table(root):
    """{pid: (ppid, start epoch seconds, command name)} of this host's processes, or None when it cannot be read (a
    Windows host reads it through PowerShell, the others from /proc or `ps`)."""
    if os.name == "nt":
        return bl_procs.windows_snapshot(str(root))[1]
    return bl_procs.process_table()


def put_value(key, text, who="own"):
    """Write TEXT as the value of KEY, a new key or its next revision; Refused when coord does not take it."""
    for _try in range(3):
        code, body, err = run_coord("get", key)
        if code not in (0, 1):
            raise Refused(f"{who}: cannot read {key}: {err or 'coord.py exited ' + str(code)}")
        revision = body.get("revision", 0) if isinstance(body, dict) else 0
        code, body, err = run_coord("put", key, f"--value={text}", "--revision", str(revision))
        if code == 0:
            return
        if code != 1:
            raise Refused(f"{who}: cannot write {key}: {err or 'coord.py exited ' + str(code)}")
    raise Refused(f"{who}: {key} keeps moving on")


def record_owner(cls, target, item=None, sprint=None, session=None, drop=False):
    """Record TARGET (a path, or a pid for the class `process`) as made by this clone's tools, with the ITEM, SPRINT and
    SESSION that made it (each left out when empty) and the time; with DROP clear the record instead. Returns the coord key.
    Raises Rejected for a bad class or target and Refused when coord does not take the write."""
    ident, text = subject(cls, target)
    key = owner_key(cls, text)
    if drop:
        code, body, _err = run_coord("get", key)
        if code != 1 and not (code == 0 and isinstance(body, dict) and not body.get("value")):
            put_value(key, "")  # a key coord does not hold, or already dropped, has nothing to clear
        return key
    value = {"class": cls, **ident, "at": int(time.time())}
    if cls == PROCESS:  # the start time tells this process from a later one with the same pid
        seen = (host_table(Path.cwd()) or {}).get(ident["pid"])
        if seen:
            value["start"] = seen[1]
    value.update({k: v for k, v in (("item", item), ("sprint", sprint), ("session", session)) if v})
    put_value(key, json.dumps(value, sort_keys=True))
    return key


def recorded(entry):
    """The record in a `coord.py list` entry (its JSON value as a dict), None for a key that is no live record: a
    value that is empty (dropped) or not a JSON object."""
    try:
        value = json.loads(entry.get("value") or "")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def cmd_own(bl, a):
    key = record_owner(a.cls, a.target, a.item, a.sprint, a.session, a.drop)
    say(f"own: {'dropped' if a.drop else 'recorded'} {a.cls} {a.target} as {key}")
    return 0


def args_own(p):
    p.add_argument("target", metavar="PATH|PID", help="the directory, or for --class process the pid")
    p.add_argument("--class", dest="cls", required=True, choices=CLASSES, help="what the target is")
    p.add_argument("--item", help="the backlog item the target was made for")
    p.add_argument("--sprint", help="the sprint it was made in")
    p.add_argument("--session", help="the session that made it")
    p.add_argument("--drop", action="store_true", help="clear the record instead of making it")


class CoordLocked(Exception):
    """The coord store stayed locked past coord.py's wait."""


def coord_state():
    """{"owners": [record], "held": [coord row], "answers": {candidate key: answer}} of the coord store now: every live
    `own/` record, every live key that a holder's lease or claim holds, and the operator's answers (`decide`). Raises
    CoordLocked when the store stayed locked, Rejected when it cannot be read."""
    code, body, err = run_coord("list")
    if code != 0 or not isinstance(body, list):
        if "locked" in err or "TimeoutExpired" in err:
            raise CoordLocked(err)
        raise Rejected(f"tidy: cannot read the coord store: {err or 'coord.py exited ' + str(code)}")
    owners, held, answers = [], [], {}
    for row in body:
        if not isinstance(row, dict) or not isinstance(row.get("key"), str):
            continue
        if row["key"].startswith(PREFIX):
            rec = recorded(row)
            if rec:
                owners.append(rec)
        elif row["key"].startswith(ANSWER_PREFIX):
            rec = recorded(row)
            if rec:
                answers[row["key"][len(ANSWER_PREFIX):]] = rec
        elif row.get("holder"):
            held.append(row)
    return {"owners": owners, "held": held, "answers": answers}


def inside(outer, inner):
    """Whether the normalised path INNER is OUTER or under it."""
    return inner == outer or inner.startswith(outer.rstrip(os.sep) + os.sep)


def fmt_size(n):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def tree_bytes(path, seconds=BYTES_SECONDS):
    """(bytes under PATH, whether the figure is approximate): a walk with os.scandir that never follows a link and stops
    after SECONDS, the sum so far then being a floor."""
    deadline = time.monotonic() + seconds
    total, stack = 0, [str(path)]
    while stack:
        if time.monotonic() > deadline:
            return total, True
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total, False


def dir_activity(path, limit=2000):
    """The newest modification time of the directory PATH and of its direct entries (the first LIMIT)."""
    newest = 0.0
    try:
        newest = os.stat(path).st_mtime
        with os.scandir(path) as it:
            for n, e in enumerate(it):
                if n >= limit:
                    break
                try:
                    newest = max(newest, e.stat(follow_symlinks=False).st_mtime)
                except OSError:
                    continue
    except OSError:
        pass
    return newest


def git_time(path, *args):
    """The commit time (an int) git prints for ARGS in PATH, else None. `--no-optional-locks`: asking never rewrites the
    index file, whose own time is no activity."""
    code, out, _ = run(["git", "--no-optional-locks", *args], cwd=path)
    word = out.split()[0] if not code and out.split() else ""
    return int(word) if word.isdigit() else None


def prime(snap, revs):
    """Read, for all of REVS (commit ids), the commit time and whether the integration main lacks the commit into SNAP,
    with two git processes per BATCH commits however many REVS there are: `commit_time` and `merged` then answer from SNAP.
    A rev git cannot read is left out, and those two functions ask git for it one at a time."""
    seen = snap.setdefault("batched", set())
    todo = sorted({r for r in revs if r and r not in seen})
    when, ahead = snap.setdefault("when", {}), snap.setdefault("ahead", set())
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        code, out, _ = run(["git", "--no-optional-locks", "log", "--no-walk=unsorted", "--format=%H %ct", *part, "--"],
                           cwd=snap["root"])
        if code:
            continue
        code2, lacks, _ = run(["git", "--no-optional-locks", "rev-list", "--no-walk=unsorted", *part, "--not",
                               snap["upstream"], "--"], cwd=snap["root"])
        if code2:
            continue
        for ln in out.splitlines():
            rev, _, word = ln.partition(" ")
            if word.isdigit():
                when[rev] = int(word)
        ahead.update(lacks.split())
        seen.update(part)


def commit_time(snap, path, rev):
    """The commit time (an int) of REV, from `prime`, else asked of git in PATH; None when git cannot tell."""
    if rev in snap.get("when", {}):
        return snap["when"][rev]
    return git_time(path, "log", "-1", "--format=%ct", rev)


def merged(snap, rev):
    """Whether every commit of REV is on the integration main: a commit `prime` found on it is, a commit it found off it
    is judged by `bl_close.merged_into` (a rebased landing counts), and a rev it did not read is asked of git."""
    if rev in snap.get("batched", ()) and rev not in snap["ahead"]:
        return True
    return bl_close.merged_into(snap["root"], rev, snap["upstream"])


def integration_main(root):
    """The integration main's ref of the clone ROOT (`refs/remotes/<remote>/main`, else `refs/heads/main`), or None."""
    import kbpublic
    for ref in (f"refs/remotes/{kbpublic.integration_remote(root)}/main", "refs/heads/main"):
        if bl_close.has_ref(root, ref):
            return ref
    return None


def take_snapshot(bl, older_than=AGE_HOURS, disk_free_gb=DISK_FREE_GB, now=None):
    """What `safe_to_remove` reads of the clone besides the coord store: the integration main, the worktrees, the item
    statuses, every process's working directory (read once), the age limit and the disk-pressure limit. Raises Rejected
    when there is no integration main to compare against."""
    root = bl.root
    upstream = integration_main(root)
    if upstream is None:
        raise Rejected("tidy: no integration main to compare against (fetch the integration remote first)")
    entries = bl_close.worktree_entries(root)
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    table, why = bl_close.process_cwds()
    return {"root": root, "upstream": upstream, "entries": entries, "here": norm_path(here),
            "main": norm_path(entries[0]["path"] if entries else here), "cwd": norm_path(Path.cwd()),
            "items": {i: it.get("status") for i, it in bl.items.items()}, "table": table, "table_why": why,
            "age": float(older_than) * 3600, "free_gb": float(disk_free_gb), "now": time.time() if now is None else now,
            "disk": {}, "planned": set()}


def free_gib(snap, path):
    """The free space, in GiB, of the volume that holds PATH (or its nearest existing parent)."""
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    key = str(p)
    if key not in snap["disk"]:
        try:
            snap["disk"][key] = shutil.disk_usage(p).free / 2 ** 30
        except OSError:
            snap["disk"][key] = float("inf")
    return snap["disk"][key]


def always_kept(path, snap):
    """Why the normalised PATH is never removed, or None: the query log's worktree, the main checkout, the worktree tidy
    runs in (each also when PATH holds it) and the directory tidy's process stands in."""
    for base in (snap["main"], snap["here"]):
        if path == norm_path(Path(base) / "_cache" / "querylog" / "worktree"):
            return "it is the query log's worktree (_cache/querylog/worktree)"
    if inside(path, snap["main"]):
        return "it is, or holds, the main checkout"
    if inside(path, snap["here"]):
        return "it is, or holds, the worktree tidy runs in"
    if inside(path, snap["cwd"]):
        return "tidy runs inside it"
    return None


def own_dirs(cls, snap):
    """({directory a record of CLS may sit strictly under}, {directory it may be, or sit under}), each really resolved, for
    the classes scratch and sandbox: a scratch directory is made under the `scratch_dir` of a checkout of this clone (the
    main checkout's or a linked worktree's); a bench multi sandbox is the sandbox root `bench_multi.default_dir` names or a
    directory under the benchmarks' scratch directory (`bench_core.scratch_dir`) that holds its clones."""
    cache = snap.setdefault("own_dirs", {})
    if cls not in cache:
        if cls == "scratch":
            tops = {snap["main"], snap["here"], *(norm_path(e["path"]) for e in snap["entries"])}
            cache[cls] = ({norm_real(Path(t).joinpath(*scratch_dir())) for t in tops}, set())
        else:
            import bench_core
            import bench_multi
            cache[cls] = ({norm_real(bench_core.scratch_dir())}, {norm_real(bench_multi.default_dir())})
    return cache[cls]


def misplaced(cls, path, snap):
    """Why the recorded directory PATH of class scratch or sandbox is not one tidy removes, or None: it is a symlink (a
    link is no directory tidy made, and what it points at is never removed), it lies outside the directories of its class
    (`own_dirs`: the checkout itself and its tracked tree are in none), or it holds a worktree of this repository."""
    if is_link(path):
        return "it is a symlink, not the directory the record names"
    strict, whole = own_dirs(cls, snap)
    if not (any(path != d and inside(d, path) for d in strict) or any(inside(d, path) for d in whole)):
        return f"it lies outside the directories tidy removes {cls} records from"
    for e in snap["entries"]:
        wt = norm_path(e["path"])
        if inside(path, wt) and os.path.isdir(wt):
            return f"it holds the worktree {wt} of this repository"
    return None


def live_claim(names, state):
    """What names one of NAMES (a path, branch, item or session) in a key or value a live coord lease or claim holds, or None."""
    for row in state["held"]:
        text = f"{row['key']} {row.get('value') or ''}"
        for name in names:
            if name and name in text:
                return f"{row['key']} (held by {row['holder']})"
    return None


def names_of(cand):
    """The texts a lease or claim names the candidate by: its path, branch, item and session."""
    rec = cand.get("record") or {}
    return [cand.get("path"), cand.get("branch"), rec.get("item"), rec.get("session")]


def cand_key(cand):
    """The key of the candidate CAND: its class and the first 16 hex digits of the sha256 of its normalised path, branch
    or pid (a recorded process: the pid and its start time), `worktree/<digest>`. The answer to a verdict `ask` is the
    coord value of `ANSWER_PREFIX` + this key and a removal's claim is `CLAIM_PREFIX` + this key."""
    cls, rec = cand["class"], cand.get("record") or {}
    if cls == PROCESS:
        ident = f"{cand['pid']}:{rec['start']}" if isinstance(rec.get("start"), int) else str(cand["pid"])
    else:
        ident = cand["branch"] if cls == "branch" else cand["path"]
    return owner_key(cls, ident)[len(PREFIX):]


def item_of(cand):
    """The id of the backlog item CAND was made for (its record's, else the one its `work/<id>` branch names), or None."""
    branch = cand.get("branch")
    return (cand.get("record") or {}).get("item") or (branch[len(WORK_PREFIX):] if branch and branch.startswith(WORK_PREFIX) else None)


def still_claimed(cand, snap):
    """Whether the item of CAND is `doing`: claimed, which no live coord lease names (the caller has found none)."""
    iid = item_of(cand)
    return bool(iid) and snap["items"].get(iid) == "doing"


def item_finished(cand, snap):
    """(True, None) when the candidate's item (else its sprint) is done, dropped or gone with its closed sprint, or names
    none; else (False, why)."""
    rec = cand.get("record") or {}
    iid = item_of(cand)
    for what, ident in (("item", iid), ("sprint", None if iid else rec.get("sprint"))):
        if ident and snap["items"].get(ident) not in FINISHED + (None,):
            return False, f"its {what} {ident} is {snap['items'][ident]}"
    return True, None


def idle_reason(last, snap, waived=None):
    """(True, None) when LAST (seconds since the epoch) is older than the age limit or the limit is WAIVED (a reason), else
    (False, why)."""
    idle = snap["now"] - last
    if waived:
        return True, waived
    if idle < snap["age"]:
        return False, f"its last activity was {idle / 3600:.1f} h ago, under the {snap['age'] / 3600:g} h limit"
    return True, None


def label(thing):
    """What names a candidate or a row: its branch, its path, else its pid."""
    return thing.get("branch") or thing.get("path") or f"pid {thing['pid']}" + (f" ({thing['comm']})" if thing.get("comm") else "")


def process_verdict(cand, snap, state):
    """(verdict, reason) for a candidate of class `process`. Only a process a record names goes, and only when it is still
    the process the record names (its start time is the record's: a pid is reused), its recorded session has no live
    coord lease or claim, its item is finished and the record is older than the age limit. A process that is no longer
    running leaves its record alone to go. A process no record names stays, whatever its parent."""
    pid, rec = cand["pid"], cand.get("record")
    if rec is None:
        return KEEP, "no owner record names it (the process was not made by this clone's tools, or never recorded)"
    if pid in (os.getpid(), os.getppid()):
        return KEEP, "it is the process tidy runs in, or its parent"
    table = snap.get("ptable")
    if table is None:
        return KEEP, "this host's process table cannot be read"
    seen = table.get(pid)
    if seen is None:
        return REMOVE, "it is no longer running; only its record is left"
    start = rec.get("start")
    if not isinstance(start, int) or isinstance(start, bool):
        return KEEP, "its record holds no start time, so the pid cannot be told from a later process"
    if abs(seen[1] - start) > START_SLOP_S:
        return KEEP, f"pid {pid} was started {int(abs(seen[1] - start))} s apart from its record: the pid was reused"
    if not rec.get("session"):
        return KEEP, "its record names no session, so nothing shows its owner is gone"
    held = live_claim(names_of(cand), state)
    if held:
        return KEEP, f"a live coord lease or claim names it: {held}"
    ok, why = item_finished(cand, snap)
    asking = None
    if not ok:
        if not still_claimed(cand, snap):
            return KEEP, why
        asking = f"its item {item_of(cand)} is still claimed"
    ok, why = idle_reason(rec.get("at") or snap["now"], snap)
    if not ok:
        return KEEP, why
    idle = f"idle for {(snap['now'] - (rec.get('at') or snap['now'])) / 3600:.1f} h"
    if asking:
        return ASK, (f"{asking}, and the process outlives its session {rec['session']}'s lease (none is held), started as "
                     f"recorded, {idle}: the operator decides")
    return REMOVE, f"owned, its session {rec['session']} holds no coord lease, started as recorded, {idle}"


def safe_to_remove(cand, snap, state):
    """(verdict, reason) for the candidate CAND, the one rule tidy, kbmon and the remediation agent read. CAND is a dict:
    `class` (worktree, branch, sandbox, scratch or process), `path` (normalised; not for a branch or a process), `branch`,
    `pid` (a process), `record` (its coord record, or None), and for a worktree its `entry` (git's, or None), for a branch
    its `tip` and `checked_out` paths. The verdict is `remove` or `keep`, or `ask` for a candidate that is recorded, clean,
    merged and idle whose item is still claimed (`doing`) with no live coord lease naming it, or whose process outlives its
    session's lease: only the operator's answer (`decide`) settles it. The reason names the first rule that keeps it, else
    what holds. SNAP is `take_snapshot`'s, STATE `coord_state`'s."""
    if cand["class"] == PROCESS:
        return process_verdict(cand, snap, state)
    cls, path, rec = cand["class"], cand.get("path"), cand.get("record")
    for p in ([path] if path else []) + cand.get("checked_out", []):
        why = always_kept(p, snap)
        if why:
            return KEEP, f"it is checked out in a path that stays ({why})" if cls == "branch" else why
    if rec is None:
        return KEEP, f"no owner record names it ({cand.get('branch') or path} was not made by this clone's tools, or never recorded)"
    entry = cand.get("entry")
    if cls in ("worktree", "sandbox", "scratch") and not os.path.lexists(path):
        return REMOVE, "its directory is already gone; only the record and git's worktree entry are left"
    if cls in ("sandbox", "scratch"):
        why = misplaced(cls, path, snap)
        if why:
            return KEEP, why
    if cls == "worktree" and entry is None:
        return KEEP, "git does not list it as a worktree"
    if cls == "worktree" and entry["lock"] is not None:
        return KEEP, f"it is locked ({entry['lock'] or 'no reason given'})"
    held = live_claim(names_of(cand), state)
    if held:
        return KEEP, f"a live coord lease or claim names it: {held}"
    if cls == "branch":
        out = [p for p in cand["checked_out"] if p not in snap["planned"]]
        if out:
            return KEEP, f"it is checked out in the worktree {out[0]}"
    elif snap["table"] is not None:
        procs = bl_close.processes_in(snap["table"], path)
        if procs:
            return KEEP, "a process still runs there: " + ", ".join(f"pid {pid} ({comm or '?'})" for pid, comm in procs)
    ok, why = item_finished(cand, snap)
    asking = None
    if not ok:
        if not still_claimed(cand, snap):
            return KEEP, why
        asking = f"its item {item_of(cand)} is still claimed and no live coord lease names it"
    waived = None
    rev = None
    if cls in ("worktree", "branch"):
        rev = entry["head"] if cls == "worktree" else cand.get("tip") or f"refs/heads/{cand['branch']}"
        last = commit_time(snap, path if cls == "worktree" else snap["root"], rev)
    else:
        last = dir_activity(path)
        if cls == "sandbox":
            free = free_gib(snap, path)
            if free < snap["free_gb"]:
                waived = f"disk pressure ({free:.1f} GiB free, under {snap['free_gb']:g} GiB): its age limit is waived"
    last = max(last or snap["now"], rec.get("at") or 0)
    ok, why = idle_reason(last, snap, waived)
    if not ok:
        return KEEP, why
    if rev is not None and not merged(snap, rev):
        return KEEP, f"it has commits {snap['upstream']} lacks"
    if cls == "worktree":
        code, out, err = run(["git", "--no-optional-locks", "status", "--porcelain"], cwd=path)
        if code or out.strip():
            return KEEP, "it has uncommitted changes" if not code else f"git status failed: {err.strip()}"
    done = {"worktree": f"owned, item finished, clean, on {snap['upstream']}, idle",
            "branch": f"owned, item finished, on {snap['upstream']}, idle",
            "sandbox": "owned, nothing runs in it, idle", "scratch": "owned, item finished, nothing runs in it, idle"}[cls]
    idle = why if why else f"{done} for {(snap['now'] - last) / 3600:.1f} h"
    if asking:
        return ASK, f"{asking}; {idle}: the operator decides"
    return REMOVE, idle


def process_candidates(snap, state):
    """The candidates of class `process`: each pid an own record names, then each process in a checkout of the clone that
    no record names (kept, never signalled). Reads the host's process table into SNAP once."""
    root = snap["root"]
    snap["ptable"] = host_table(root)
    recs = {r["pid"]: r for r in state["owners"] if r.get("class") == PROCESS and isinstance(r.get("pid"), int)}
    out = []
    for pid, rec in sorted(recs.items()):
        seen = (snap["ptable"] or {}).get(pid)
        out.append({"class": PROCESS, "pid": pid, "record": rec, **({"comm": seen[2]} if seen else {})})
    found = bl_procs.windows_snapshot(str(root))[0] if os.name == "nt" else bl_procs.snapshot(str(root))[0]
    for p in found or []:
        if p["pid"] not in recs:
            out.append({"class": PROCESS, "pid": p["pid"], "record": None, "comm": p["comm"], "where": p["where"],
                        "kind": p["kind"]})
    return out


def candidates(snap, state, classes=TIDY_CLASSES):
    """The candidates of each class, in TIDY_CLASSES order: every git worktree (the unrecorded ones too, kept), every
    recorded worktree git no longer lists, the local TIDY_PREFIXES branches, and the recorded sandboxes and scratch
    directories; with `process` among CLASSES also its processes (`process_candidates`)."""
    recs = {(r.get("class"), r["path"]): r for r in state["owners"] if isinstance(r.get("path"), str)}
    by_item = {}
    for r in recs.values():
        if r.get("item") and r.get("class") in ("worktree", "scratch", "sandbox"):
            by_item.setdefault(r["item"], r)
    out = {c: [] for c in TIDY_CLASSES + (PROCESS,)}
    listed = set()
    branch_rec = {}
    for e in snap["entries"]:
        p = norm_path(e["path"])
        listed.add(p)
        rec = recs.get(("worktree", p))
        if rec and e["branch"]:
            branch_rec[e["branch"]] = rec
        out["worktree"].append({"class": "worktree", "path": p, "record": rec, "entry": e, "branch": e["branch"]})
    for (cls, p), rec in sorted(recs.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        if cls == "worktree" and p not in listed:
            out["worktree"].append({"class": "worktree", "path": p, "record": rec, "entry": None, "branch": None})
        elif cls in ("sandbox", "scratch"):
            out[cls].append({"class": cls, "path": p, "record": rec})
    code, text, _ = run(["git", "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"], cwd=snap["root"])
    for ln in sorted(text.splitlines()) if not code else []:
        branch, _, tip = ln.partition(" ")
        if not branch.startswith(TIDY_PREFIXES):
            continue
        rec = branch_rec.get(branch) or (by_item.get(branch[len(WORK_PREFIX):]) if branch.startswith(WORK_PREFIX) else None)
        out["branch"].append({"class": "branch", "branch": branch, "tip": tip, "record": rec,
                              "checked_out": [norm_path(e["path"]) for e in snap["entries"] if e["branch"] == branch]})
    prime(snap, [e["head"] for e in snap["entries"]] + [c["tip"] for c in out["branch"]])
    if PROCESS in classes:
        out[PROCESS] = process_candidates(snap, state)
    return out


def row_of(cand, verdict, reason):
    row = {"class": cand["class"], "verdict": verdict, "reason": reason, "bytes": 0, "key": cand_key(cand), "_cand": cand}
    if cand["class"] == PROCESS:
        row.update({k: cand[k] for k in ("pid", "comm", "where", "kind") if k in cand})
    else:
        row.update({"branch": cand["branch"]} if cand["class"] == "branch" else {"path": cand["path"]})
    item = (cand.get("record") or {}).get("item")
    if item:
        row["item"] = item
    return row


def answer_of(cand, state):
    """The operator's answer (`remove` or `keep`) to CAND's verdict `ask`, or None: none given, or given before the
    candidate's record was made (a path used again is a new candidate)."""
    given = state.get("answers", {}).get(cand_key(cand))
    if not isinstance(given, dict) or given.get("answer") not in (REMOVE, KEEP):
        return None
    at, made = given.get("at"), (cand.get("record") or {}).get("at") or 0
    return given["answer"] if isinstance(at, (int, float)) and not isinstance(at, bool) and at >= made else None


def plan(snap, state, only=None, budget=None, classes=TIDY_CLASSES):
    """The rows of every candidate with its verdict, reason and the bytes it frees; the bench sandboxes first when the
    disk is under pressure, else by class. A worktree judged `remove` is no longer a checkout for its branch. ONLY, a
    predicate on a candidate, keeps the rows it accepts; BUDGET is the seconds all the walks of one plan share (the
    figure of a row the budget did not reach is 0, `approximate`). CLASSES are the classes planned."""
    cands = candidates(snap, state, classes)
    deadline = None if budget is None else time.monotonic() + budget
    rows = []
    for cls in classes:
        for cand in cands[cls]:
            if only is not None and not only(cand):
                continue
            verdict, reason = safe_to_remove(cand, snap, state)
            answer = answer_of(cand, state) if verdict == ASK else None
            if answer:
                verdict, reason = answer, f"the operator answered {answer} ({reason.removesuffix(': the operator decides')})"
            row = row_of(cand, verdict, reason)
            if answer:
                row["answer"] = answer
            if verdict == REMOVE and cls == "worktree":
                snap["planned"].add(cand["path"])
            if verdict == REMOVE and cls in ("worktree", "sandbox", "scratch") and os.path.isdir(cand["path"]):
                left = BYTES_SECONDS if deadline is None else min(BYTES_SECONDS, deadline - time.monotonic())
                row["bytes"], approx = tree_bytes(cand["path"], left) if left > 0 else (0, True)
                if approx:
                    row["approximate"] = True
            if cls == "sandbox" and "disk pressure" in reason:
                row["_pressure"] = True
            rows.append(row)
    rows.sort(key=lambda r: 0 if r.get("_pressure") else 1)
    return rows


def public(row):
    return {k: v for k, v in row.items() if not k.startswith("_")}


def rmtree_writable(path):
    """Remove the directory tree PATH, making a read-only file writable first (git's object files on Windows); an error
    that remains (a file a process holds open) is raised."""
    def retry(func, name, exc):
        if isinstance(exc, PermissionError) and os.path.lexists(name):
            os.chmod(name, stat.S_IWRITE)
            func(name)
        else:
            raise exc
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=lambda f, n, e: retry(f, n, e))
    else:
        shutil.rmtree(path, onerror=lambda f, n, i: retry(f, n, i[1]))


def drop_record(cand):
    target = cand.get("path") or cand.get("pid")
    if cand.get("record") is not None and target:
        try:
            record_owner(cand["class"], target, drop=True)
        except Refused as e:
            say(f"tidy: {e}")


def end_process(snap, cand):
    """End the process of CAND with SIGTERM, then SIGKILL after `bl_procs.END_WAIT_S`, and clear its record; returns None
    once it is gone, else why it was kept. The process table is read again first: a pid that now has another start time
    than the record is another process and is never signalled."""
    pid, rec = cand["pid"], cand["record"]
    seen = (host_table(snap["root"]) or {}).get(pid)
    if seen is not None:
        start = rec.get("start")
        if not isinstance(start, int) or abs(seen[1] - start) > START_SLOP_S:
            return "its start time is no longer the record's: the pid was reused"
        bl_procs.end_pids([pid])
        if bl_procs.alive(pid):
            return "it still runs after SIGKILL"
    drop_record(cand)
    return None


def is_recorded_dir(path):
    """Whether the normalised PATH, looked at with lstat, is a real directory at the place its record names: no symlink or
    junction at its end, none in its parents (realpath of it is itself)."""
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode) and not is_link(path) and norm_path(path) == path
    except OSError:
        return False


def remove_one(snap, row, removed):
    """Remove the candidate of ROW; returns None once it is gone, else why it was kept. REMOVED collects the worktree
    paths removed so far (a branch checked out only in those is free to go)."""
    cand, root = row["_cand"], snap["root"]
    cls, path = cand["class"], cand.get("path")
    if cls == PROCESS:
        return end_process(snap, cand)
    if cls == "branch":
        if any(p not in removed for p in cand["checked_out"]):
            return "its worktree stays"
        if bl_close.delete_landed_branch(root, cand["branch"], snap["upstream"], who="tidy", prefixes=TIDY_PREFIXES):
            return None
        return "see the line above"
    if os.path.lexists(path):
        if not is_recorded_dir(path):  # replaced by a link, or by a file, since the listing
            return "it is no longer the recorded directory (a symlink or a file stands there)"
        if snap["table"] is None:  # Windows: a rename to a sibling and back fails while a process holds the directory
            held = bl_close.held_by_process(Path(path))
            if held:
                return f"it could not be moved ({held}): a process may hold it"
        if cls == "worktree":
            code, out, err = run(["git", "worktree", "remove", path], cwd=root)
            if code:
                return f"git worktree remove: {(err or out).strip()}"
        else:
            try:
                rmtree_writable(path)
            except OSError as e:
                return f"{type(e).__name__}: {e.strerror or e}"
    if cls == "worktree":
        removed.add(path)
    drop_record(cand)
    return None


def claim_clean(key):
    """Claim `CLAIM_PREFIX` + KEY for a removal: (the token, None) once held, else (None, why) with the holder's name when
    another holds it. Raises CoordLocked when the store stayed locked."""
    code, body, err = run_coord("claim", CLAIM_PREFIX + key, "--ttl", str(CLAIM_TTL), "--holder", CLAIM_HOLDER)
    if code == 0 and isinstance(body, dict) and body.get("token"):
        return body["token"], None
    if "locked" in err or "TimeoutExpired" in err:
        raise CoordLocked(err)
    if code == 1 and isinstance(body, dict) and body.get("holder"):
        return None, f"{CLAIM_PREFIX}{key} is claimed by {body['holder']}"
    return None, f"cannot claim {CLAIM_PREFIX}{key}: {err or 'coord.py exited ' + str(code)}"


def remove_answered(snap, row, removed):
    """Remove the candidate of ROW, a verdict `ask` the operator answered `remove`, only while this run holds the coord
    claim `CLAIM_PREFIX` + its key; returns None once it is gone, else why it was kept. The claim is released after, and the
    answer cleared once the candidate is gone."""
    token, why = claim_clean(row["key"])
    if token is None:
        return why
    try:
        why = remove_one(snap, row, removed)
        if why is None:
            try:
                put_value(ANSWER_PREFIX + row["key"], "", who="tidy")
            except Refused as e:
                say(f"tidy: {e}")
        return why
    finally:
        run_coord("release", CLAIM_PREFIX + row["key"], "--token", token)


def apply_rows(snap, rows, say_to):
    """Remove the `remove` rows, setting each row's `result`. Before each removal the coord store is read again: a lease
    or claim that appeared since the listing keeps the candidate. A row the operator answered `remove` (`answer`) goes
    only once this run has claimed `CLAIM_PREFIX` + its key: while another holder has it nothing is removed and the row
    counts as a failure. Returns the number of failures; raises CoordLocked."""
    failed, removed, pruned = 0, set(), False
    with contextlib.redirect_stdout(say_to):
        for row in rows:
            if row["verdict"] != REMOVE:
                continue
            held = live_claim(names_of(row["_cand"]), coord_state())
            if held:
                row["result"], failed = f"kept: a live coord lease or claim names it now: {held}", failed + 1
                continue
            pruned = pruned or row["class"] == "worktree"
            why = remove_answered(snap, row, removed) if row.get("answer") else remove_one(snap, row, removed)
            if why:
                row["result"], failed = f"kept: {why}", failed + 1
            else:
                row["result"] = "removed"
        if pruned:
            run(["git", "worktree", "prune"], cwd=snap["root"])
    return failed


def class_counts(rows, applied, classes=TIDY_CLASSES):
    """[(class, rows that go, rows kept, bytes they free, whether the bytes are a floor)] for each of CLASSES: the rows
    removed (with --apply) or that would go, and the bytes of them, nested paths counted once."""
    out = []
    for cls in classes:
        mine = [r for r in rows if r["class"] == cls]
        gone = [r for r in mine if (r.get("result") == "removed" if applied else r["verdict"] == REMOVE)]
        paths = [r["path"] for r in gone if "path" in r]
        top = [r for r in gone if not any(o != r.get("path") and inside(o, r.get("path", "")) for o in paths)]
        out.append((cls, len(gone), len(mine) - len(gone), sum(r["bytes"] for r in top),
                    any(r.get("approximate") for r in top)))
    return out


def summary_lines(rows, applied, classes=TIDY_CLASSES):
    """One line a class: how many rows go (were removed, with --apply) and the bytes they free, nested paths counted once."""
    return [f"tidy: {cls}: {'removed' if applied else 'would remove'} {n}{f' ({fmt_size(size)})' if size else ''}, kept {kept}"
            for cls, n, kept, size, _ in class_counts(rows, applied, classes)]


def report_line(rows):
    """The one line of `tidy --report`: for each class the count that would go, the bytes it frees and the count kept."""
    parts = []
    for cls, n, kept, size, approx in class_counts(rows, False):
        freed = f" ({fmt_size(size)}{' or more' if approx else ''})" if size or approx else ""
        parts.append(f"{cls}: {n} would go{freed}, {kept} kept")
    return "tidy report: " + "; ".join(parts)


def apply_subset(bl, who, only, spare=None, items=None):
    """Remove, as `tidy --apply` does with `safe_to_remove`'s verdict and the age limit waived, the candidates ONLY accepts,
    except the ones SPARE accepts, which are said as left. ITEMS sets item statuses over the clone's (an item `land` just
    landed is done). Each result is said as a `WHO:` line. Returns the number kept. Never raises: what goes wrong is said
    and left to the next `tidy --apply`."""
    try:
        snap = take_snapshot(bl, older_than=0)
        snap["items"].update(items or {})
        rows = plan(snap, coord_state(), only=only)
        for r in rows:
            if spare is not None and spare(r["_cand"]) and r["verdict"] == REMOVE:
                r["verdict"], r["reason"] = KEEP, "the sprint's own worktree is left for tidy --apply"
        failed = apply_rows(snap, rows, io.StringIO())
    except (CoordLocked, Rejected, Refused, OSError) as e:
        say(f"{who}: kept its recorded leftovers: {e or e.__class__.__name__}")
        return 1
    kept = failed
    for r in rows:
        what = label(r)
        if r["verdict"] == REMOVE and r["result"] == "removed":
            say(f"{who}: removed {what}")
        else:
            kept += 1
            say(f"{who}: kept {what}: {(r.get('result') or r['reason']).removeprefix('kept: ')}")
    return kept


def land_leftovers(bl, iid):
    """What `land` removes once the item IID has landed: its recorded scratch directory, and the records of its worktrees
    git no longer lists (the worker's worktree `land` released). Returns the number kept."""
    def mine(cand):
        rec = cand.get("record") or {}
        return rec.get("item") == iid and (cand["class"] == "scratch"
                                           or (cand["class"] == "worktree" and cand.get("entry") is None))
    return apply_subset(bl, "land", mine, items={iid: "done"})


def close_leftovers(bl, sid):
    """What `close` removes once the sprint SID is closed: its items' recorded scratch directories and worker worktrees (a
    record with the sprint and an item; one `close` could not release stays, with the reason). The orchestrator's and the
    reviewer's worktrees (the sprint and no item) are said as left to `tidy --apply`. Returns the number kept."""
    def mine(cand):
        return (cand.get("record") or {}).get("sprint") == sid and cand["class"] in ("scratch", "worktree")
    def spare(cand):
        return cand["class"] == "worktree" and not cand["record"].get("item")
    return apply_subset(bl, "close", mine, spare)


def remote_merged(root):
    """([branch names, `code/<id>`], the number kept, the remote name, the integration main's ref) of the `code/` branches
    the integration remote had when last fetched (`refs/remotes/<remote>/code/*`; nothing is fetched): the ones whose
    commits `git cherry` finds on the integration main, and the number that have a commit it lacks. Raises Rejected when
    there is no integration main."""
    import kbpublic
    upstream = integration_main(root)
    if upstream is None:
        raise Rejected("tidy: no integration main to compare against (fetch the integration remote first)")
    remote = kbpublic.integration_remote(root)
    base = f"refs/remotes/{remote}/{REMOTE_BRANCHES}"
    code, text, err = run(["git", "for-each-ref", "--format=%(refname)", base], cwd=root)
    if code:
        raise Rejected(f"tidy: cannot list {base}: {err.strip()}")
    code, text2, _ = run(["git", "for-each-ref", "--format=%(refname)", f"--merged={upstream}", base], cwd=root)
    ancestors = set(text2.splitlines()) if not code else set()
    merged, kept = [], 0
    for ref in sorted(text.splitlines()):
        if ref in ancestors or bl_close.merged_into(root, ref, upstream):
            merged.append(ref[len(f"refs/remotes/{remote}/"):])
        else:
            kept += 1
    return merged, kept, remote, upstream


def cmd_remote(bl, a):
    """`tidy --remote`: list the `code/<id>` branches of the integration remote whose commits are on the integration main.
    Reads only: tidy never deletes a branch of a remote."""
    merged, kept, remote, upstream = remote_merged(bl.root)
    if a.json:
        print(json.dumps([{"class": "remote", "remote": remote, "branch": b, "merged": True,
                           "reason": f"every commit of it is on {upstream}"} for b in merged], indent=2))
        return 0
    for b in merged:
        say(f"tidy: {remote}/{b}: merged, every commit of it is on {upstream}")
    say(f"tidy: remote: {len(merged)} merged {REMOTE_BRANCHES}<id> branch(es) on {remote} (as last fetched), "
        f"{kept} with a commit {upstream} lacks")
    say("tidy: it deletes no remote branch: a merged one is removed by the operator's own command")
    return 0


def decide(key, answer):
    """Record the operator's ANSWER (`remove` or `keep`) to the verdict `ask` of the candidate KEY, as the coord value of
    `ANSWER_PREFIX` + KEY with the time. Refused in an agent session; Rejected for a bad key or answer."""
    if bl_authority.in_agent_session():
        raise Rejected("tidy: --decide records the operator's answer, which an agent session may not give: "
                       "the operator runs it from their own terminal")
    if not KEY_FORM.fullmatch(key):
        raise Rejected(f"tidy: --decide takes the key of a row (class/16 hex digits, `tidy --json` prints it), not {key[:40]!r}")
    if answer not in (REMOVE, KEEP):
        raise Rejected(f"tidy: --decide answers {REMOVE} or {KEEP}, not {answer[:20]!r}")
    put_value(ANSWER_PREFIX + key, json.dumps({"answer": answer, "at": int(time.time())}, sort_keys=True), who="tidy")
    say(f"tidy: recorded {answer} for {key}")


def cmd_tidy(bl, a):
    """List the recorded leftovers with `safe_to_remove`'s verdict, reason and bytes (and with --apply remove the ones
    it clears), under the exit codes in the module docstring."""
    if a.decide:
        if a.apply or a.json or a.report or a.remote or a.cls or a.paths:
            raise Rejected("tidy: --decide records one answer: it takes no other option")
        decide(*a.decide)
        return 0
    if a.older_than < 0 or a.disk_free_gb < 0:
        raise Rejected("tidy: --older-than and --disk-free-gb are not negative")
    if a.report and (a.apply or a.json):
        raise Rejected("tidy: --report reads only and prints one line: it takes neither --apply nor --json")
    if a.remote:
        if a.apply:
            raise Rejected("tidy: --remote reads only: tidy deletes no remote branch")
        if a.report or a.cls or a.paths:
            raise Rejected("tidy: --remote lists the merged remote branches: it takes none of --report, --class, --path")
        return cmd_remote(bl, a)
    if a.paths and (a.report or a.cls == PROCESS):
        raise Rejected("tidy: --path keeps the recorded directories at those paths: it takes neither --report nor --class process")
    if a.apply and a.cls == PROCESS and bl_authority.in_agent_session():
        raise Rejected("tidy: --apply with --class process ends processes, which an agent session may not do: "
                       "the operator runs it from their own terminal")
    classes = (a.cls,) if a.cls else TIDY_CLASSES
    snap = take_snapshot(bl, a.older_than, a.disk_free_gb)
    try:
        state = coord_state()
        only = None
        if a.paths:
            wanted = {norm_path(p) for p in a.paths}
            named = {r["path"] for r in state["owners"] if isinstance(r.get("path"), str)}
            unnamed = [p for p in a.paths if norm_path(p) not in named]
            if unnamed:
                raise Rejected("tidy: --path: no own record names " + ", ".join(repr(p) for p in unnamed))
            only = lambda cand: cand.get("path") in wanted and cand.get("record") is not None
        rows = plan(snap, state, only=only, budget=REPORT_SECONDS if a.report else None, classes=classes)
        failed = apply_rows(snap, rows, sys.stderr if a.json else sys.stdout) if a.apply else 0
    except CoordLocked:
        say("tidy: the coord store stayed locked: nothing more was removed; run tidy again")
        return 3
    if a.json:
        print(json.dumps([public(r) for r in rows], indent=2))
        return 1 if failed else 0
    if a.report:
        say(report_line(rows))
        return 0
    for r in rows:
        what = label(r)
        size = f" ({fmt_size(r['bytes'])}{' or more' if r.get('approximate') else ''})" if r["bytes"] else ""
        if a.apply and r["verdict"] == REMOVE:
            say(f"tidy: {r['result']} {what}{size}: {r['reason']}" if r["result"] == "removed" else f"tidy: {r['result']} {what}")
        else:
            say(f"tidy: {'would remove' if r['verdict'] == REMOVE else r['verdict'] if r['verdict'] == ASK else 'kept'} "
                f"{what}{size}: {r['reason']}")
    for ln in summary_lines(rows, a.apply, classes):
        say(ln)
    asks = [r for r in rows if r["verdict"] == ASK]
    if asks:
        say(f"tidy: {len(asks)} to ask: `tidy --decide KEY remove|keep` answers one; then --apply removes a `remove` "
            f"answer after it claims {CLAIM_PREFIX}KEY ({', '.join(r['key'] for r in asks)})")
    if not a.apply:
        say("tidy: --apply removes the ones listed as would remove (never --force)")
    return 1 if failed else 0


def args_tidy(p):
    p.add_argument("--apply", action="store_true", help="remove what tidy lists as safe (default: only list it)")
    p.add_argument("--json", action="store_true", help="print the rows as a JSON array")
    p.add_argument("--report", action="store_true", help="print one line of counts and bytes a class; reads only")
    p.add_argument("--class", dest="cls", choices=TIDY_CLASSES + (PROCESS,),
                   help="list only this class; `process` lists the processes an own record names (and those none names, "
                        "kept) and with --apply ends the ones it clears: refused in an agent session")
    p.add_argument("--path", dest="paths", action="append", metavar="PATH",
                   help="list, and with --apply remove, only the recorded leftover at this path (repeatable), under the same "
                        "verdict as every row; a path no own record names is refused (exit 2)")
    p.add_argument("--remote", action="store_true",
                   help="list the code/<id> branches of the integration remote that are merged (reads only; deletes none)")
    p.add_argument("--decide", nargs=2, metavar=("KEY", "ANSWER"),
                   help="record the operator's answer, remove or keep, to the row of that key whose verdict is ask "
                        "(`--json` prints each row's key); refused in an agent session")
    p.add_argument("--older-than", type=float, default=AGE_HOURS, metavar="HOURS",
                   help=f"a leftover's last activity must be older than this (default {AGE_HOURS})")
    p.add_argument("--disk-free-gb", type=float, default=DISK_FREE_GB, metavar="GB",
                   help=f"free space below this is disk pressure: sandboxes come first, age waived (default {DISK_FREE_GB})")


bl_cli.register("own", cmd_own, args_own, help="record a worktree, sandbox, scratch directory or process this clone's tools made")
bl_cli.register("tidy", cmd_tidy, args_tidy)
