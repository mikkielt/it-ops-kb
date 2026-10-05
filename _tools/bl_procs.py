"""`backlog.py procs`: the processes whose working directory lies in a checkout of this clone (the main checkout or any
worktree `git worktree list` names), each as an orphan or foreign (kb/_self/backlog.md, Processes left running;
kb/_self/tools.md).

  procs                 list them (read only): pid, parent, age, class, command name, and where it runs

Classes: `orphan` (its parent is gone: a background run a session left behind) and `foreign` (anything else: a live
session's own work). Nothing is ever signaled: an orphan is named for the operator, who ends it when it is theirs, and
`backlog.py selfcheck` fails while one runs. A process's command line and environment are never read: only its command
name is printed. Where a host cannot list working directories (Windows) it says so. Exit codes: 0 listed (also on a host
that cannot check), 2 a bad request.

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
ORPHAN, FOREIGN = "orphan", "foreign"


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


# ---------------------------------------------------------------- the clone's checkouts

def checkouts(root):
    """The real paths of the main checkout and each worktree of the clone at ROOT; [ROOT] when git cannot say."""
    try:
        text = bl_base.git(root, "worktree", "list", "--porcelain")
    except (Refused, OSError):
        return [os.path.realpath(root)]
    found = [os.path.realpath(ln[len("worktree "):]) for ln in text.splitlines() if ln.startswith("worktree ")]
    return found or [os.path.realpath(root)]


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


def classify(procs, tab):
    """Each process of PROCS with its `kind`: orphan when its parent is gone, foreign otherwise."""
    return [dict(p, kind=ORPHAN if orphaned(tab, p["pid"]) else FOREIGN) for p in procs]


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
    return classify(inventory(root, tab, cwds), tab), tab, None


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
    counts = {k: sum(p["kind"] == k for p in procs) for k in (ORPHAN, FOREIGN)}
    say("procs: " + ", ".join(f"{n} {k}" for k, n in counts.items()) + "; nothing is signaled: an orphan is named for "
        "the operator, who ends it when it is theirs")
    return 0


bl_cli.register("procs", cmd_procs, args_procs, help="list the processes left in this clone's checkouts, orphans named")
