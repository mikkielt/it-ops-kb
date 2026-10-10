"""`backlog.py procs`: the processes whose working directory lies in a checkout of this clone (the main checkout or any
worktree `git worktree list` names, and, in a workspace whose backlog.json declares `repositories`, each repository's
checkout and worktrees), each as an orphan or foreign (kb/_self/backlog.md, Processes left running; kb/_self/tools.md).

  procs                 list them (read only): pid, parent, age, class, command name, and where it runs

Classes: `orphan` (its parent is gone: a background run a session left behind), `hook` (an orphan younger than
HOOK_GRACE_S whose standard output is the query log's distill.log: the run a session's end hook started, which delivers
for a few seconds with its parent gone, and ends on its own) and `foreign` (anything else: a live session's own work).
Nothing is ever signaled: an orphan is named for the operator, who ends it when it is theirs, and `backlog.py selfcheck`
fails while one runs; a hook in flight is named with its age and fails nothing until it is older than HOOK_GRACE_S. A
process's command line and environment are never read: only its command name is printed, and a hook is told by the file
its standard output is. Where a host cannot list working directories (Windows) it says so. Exit codes: 0 listed (also on
a host that cannot check), 2 a bad request.

Standard library only; imports `bl_base` and `bl_cli`, never `backlog` (a layer rule). It registers its own subcommand
when imported, so `backlog.py` carries only the import.
"""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import bl_base
import bl_cli
from bl_base import Refused, say

REAPERS = ("init", "systemd", "launchd")  # a parent with one of these names has adopted an orphan
ORPHAN, HOOK, FOREIGN = "orphan", "hook", "foreign"
HOOK_GRACE_S = 60  # how long a session-end hook's run is no orphan, and how long `land` waits for one to end
HOOK_LOG = ("_cache", "querylog")  # under a checkout: the directory ql_base.places() gives a clone, whose distill.log is
#                                    the standard output of every run `ql_distill.detach` starts


# ---------------------------------------------------------------- the host's process table

def unsupported():
    """Why this host cannot list processes by working directory, or None. Windows exposes no working directory to
    the standard library; elsewhere /proc (Linux) or `lsof` (macOS and other POSIX hosts) is needed."""
    if os.name == "nt":
        return "Windows does not expose a process's working directory"
    if Path("/proc/self/cwd").exists():
        return None
    return None if shutil.which("lsof") and shutil.which("ps") else "no /proc, and no lsof and ps, on this host"


def run_quiet(argv):
    """The stdout of a command (an argument list) run outside any checkout, so it is no process of the scan; None
    when it cannot run."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                           cwd=tempfile.gettempdir(), env=dict(os.environ, LC_ALL="C"))
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout


def command_name(text):
    """The last path component of an executable name: never a directory, never an argument."""
    return text.strip().replace("\\", "/").rsplit("/", 1)[-1]


def table_proc():
    """{pid: (ppid, start, command name)} read from /proc (Linux), or None. A zombie is left out. Reads only the
    kernel's stat and comm files, never cmdline or environ."""
    try:
        btime = next(int(ln.split()[1]) for ln in Path("/proc/stat").read_text(encoding="utf-8").splitlines()
                     if ln.startswith("btime "))
        tick = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, StopIteration, AttributeError):
        return None
    out = {}
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = (d / "stat").read_text(encoding="utf-8", errors="replace")
            rest = stat[stat.rindex(")") + 2:].split()
            comm = (d / "comm").read_text(encoding="utf-8", errors="replace").strip()
            if rest[0] == "Z":
                continue
            out[int(d.name)] = (int(rest[1]), int(btime + int(rest[19]) / tick), comm)
        except (OSError, ValueError, IndexError):  # gone while reading
            continue
    return out


def table_ps():
    """The same from `ps` (macOS and other POSIX hosts), or None: `pid ppid stat lstart comm`, the command name
    only (`comm`, never `args`). A zombie is left out."""
    text = run_quiet(["ps", "-axo", "pid=,ppid=,stat=,lstart=,comm="])
    if text is None:
        return None
    out = {}
    for ln in text.splitlines():
        parts = ln.split(None, 8)
        if len(parts) < 9 or not parts[0].isdigit() or not parts[1].isdigit() or parts[2].startswith("Z"):
            continue
        try:
            start = int(time.mktime(time.strptime(" ".join(parts[3:8]), "%a %b %d %H:%M:%S %Y")))
        except ValueError:
            continue
        out[int(parts[0])] = (int(parts[1]), start, command_name(parts[8]))
    return out or None


def process_table():
    """{pid: (ppid, start epoch seconds, command name)} for this host's processes, or None."""
    return (table_proc() if Path("/proc/self/cwd").exists() else None) or table_ps()


def cwd_map():
    """({pid: working directory}, None), or (None, why) when this host gives no way to tell."""
    why = unsupported()
    if why:
        return None, why
    out = {}
    if Path("/proc/self/cwd").exists():
        for d in Path("/proc").iterdir():
            if d.name.isdigit():
                try:
                    out[int(d.name)] = os.readlink(d / "cwd")
                except OSError:  # gone, or another user's
                    continue
        return out, None
    text = run_quiet(["lsof", "-n", "-P", "-w", "-d", "cwd", "-Fpn"])
    pid = None
    for ln in (text or "").splitlines():
        if ln.startswith("p") and ln[1:].isdigit():
            pid = int(ln[1:])
        elif ln.startswith("n") and pid is not None:
            out[pid] = ln[1:]
    if not out:  # lsof lists at least itself: nothing read means it could not look
        return None, "lsof listed no process"
    return out, None


def stdout_map(pids):
    """{pid: real path of the file its standard output is} for the PIDS that have one this host lets us read: /proc's
    fd 1 (Linux) or `lsof -d 1` (macOS). A pid it cannot read is left out. Never reads a command line."""
    out = {}
    pids = sorted(set(pids))
    if not pids or os.name == "nt":
        return out
    if Path("/proc/self/cwd").exists():
        for pid in pids:
            try:
                out[pid] = os.path.realpath(os.readlink(f"/proc/{pid}/fd/1"))
            except OSError:  # gone, or another user's
                continue
        return out
    if not shutil.which("lsof"):
        return out
    pid = None
    for ln in (run_quiet(["lsof", "-n", "-P", "-w", "-a", "-d", "1", "-p", ",".join(map(str, pids)), "-Fpn"]) or
               "").splitlines():
        if ln.startswith("p") and ln[1:].isdigit():
            pid = int(ln[1:])
        elif ln.startswith("n") and pid is not None:
            out[pid] = os.path.realpath(ln[1:])
    return out


def hook_logs(bases):
    """The real paths of the files a session-end hook's run has as its standard output, for the checkouts BASES."""
    import ql_distill
    return {os.path.realpath(os.path.join(b, *HOOK_LOG, ql_distill.LOG_NAME)) for b in bases}


def hook_pids(root, pids, bases=None):
    """The subset of PIDS whose standard output is the query log's distill.log of a checkout of the clone at ROOT."""
    logs = hook_logs(checkouts(root) if bases is None else bases)
    return {pid for pid, path in stdout_map(pids).items() if path in logs}


# ---------------------------------------------------------------- the clone's checkouts

def worktrees(path):
    """The real paths of the checkout at PATH and its worktrees (`git worktree list`); [] when git cannot say."""
    try:
        text = bl_base.git(path, "worktree", "list", "--porcelain")
    except (Refused, OSError):
        return []
    return [os.path.realpath(ln[len("worktree "):]) for ln in text.splitlines() if ln.startswith("worktree ")]


def checkouts(root):
    """The real paths of the main checkout and each worktree of the clone at ROOT; [ROOT] when git cannot say. With a
    `repositories` map, each repository's checkout and worktrees (the ones `dispatch` makes of a multi-repository
    item's repositories) are listed too: a process in one holds it as it holds a workspace worktree."""
    found = worktrees(root) or [os.path.realpath(root)]
    for sub in bl_base.repositories().values():
        found += [p for p in worktrees(Path(root) / sub) if p not in found]
    return found


def inside(cwd, base):
    return cwd == base or cwd.startswith(base.rstrip(os.sep) + os.sep)


# ---------------------------------------------------------------- inventory and classes

def orphaned(tab, pid):
    """True when the parent of PID is gone: pid 1 or less, a pid that no longer runs, or a process that only adopts
    orphans (REAPERS)."""
    ppid = tab[pid][0]
    return ppid <= 1 or ppid not in tab or tab[ppid][2] in REAPERS


def inventory(root, tab, cwds, bases=None):
    """[{pid, ppid, start, comm, cwd, where}] of the processes in TAB whose working directory (CWDS) lies in a
    checkout of the clone, this process left out, in pid order. `where` is the checkout's directory name and the
    path under it, never an absolute path."""
    bases = checkouts(root) if bases is None else bases
    out = []
    for pid in sorted(cwds):
        if pid == os.getpid() or pid not in tab:
            continue
        base = max((b for b in bases if inside(cwds[pid], b)), key=len, default=None)
        if base is None:
            continue
        rel = os.path.relpath(cwds[pid], base)
        ppid, start, comm = tab[pid]
        out.append({"pid": pid, "ppid": ppid, "start": start, "comm": comm,
                    "where": Path(base).name + ("" if rel == "." else "/" + rel.replace(os.sep, "/"))})
    return out


def classify(procs, tab, hooks=(), now=None):
    """Each process of PROCS with its `kind`: foreign while its parent lives, else hook when its pid is in HOOKS (the
    runs whose standard output is a distill.log) and it started less than HOOK_GRACE_S before NOW, else orphan."""
    now = time.time() if now is None else now
    out = []
    for p in procs:
        if not orphaned(tab, p["pid"]):
            kind = FOREIGN
        elif p["pid"] in hooks and now - p["start"] < HOOK_GRACE_S:
            kind = HOOK
        else:
            kind = ORPHAN
        out.append(dict(p, kind=kind))
    return out


def age_text(seconds):
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h{s % 3600 // 60:02d}m"
    return f"{s // 86400}d{s % 86400 // 3600:02d}h"


def line(p, now):
    return (f"  pid {p['pid']} parent {p['ppid']} age {age_text(now - p['start'])} {p['kind']} {p['comm']} "
            f"in {p['where']}")


def snapshot(root):
    """(classified processes, table, None), or (None, None, why) when the host cannot say."""
    cwds, why = cwd_map()
    tab = process_table() if cwds is not None else None
    if cwds is None or tab is None:
        return None, None, why or "the process table could not be read"
    procs = inventory(root, tab, cwds)
    hooks = hook_pids(root, [p["pid"] for p in procs if orphaned(tab, p["pid"])])
    return classify(procs, tab, hooks), tab, None


# ---------------------------------------------------------------- the command

def args_procs(p):
    pass  # a list, read only: no options


def cmd_procs(bl, a):
    procs, _, why = snapshot(str(bl.root))
    if procs is None:
        say(f"procs: cannot list processes by working directory on this host ({why})")
        return 0
    now = time.time()
    say(f"procs: {len(procs)} process(es) with a working directory in a checkout of this clone")
    for p in procs:
        say(line(p, now))
    counts = {k: sum(p["kind"] == k for p in procs) for k in (ORPHAN, HOOK, FOREIGN)}
    say("procs: " + ", ".join(f"{n} {k}" for k, n in counts.items()) + "; nothing is signaled: an orphan is named for "
        f"the operator, who ends it when it is theirs, and a hook is a session's end run, in flight for under "
        f"{HOOK_GRACE_S}s")
    return 0


bl_cli.register("procs", cmd_procs, args_procs, help="list the processes left in this clone's checkouts, orphans named")
