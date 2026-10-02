"""`backlog.py procs`: the processes whose working directory lies in a checkout of this clone (the main checkout or any
worktree `git worktree list` names), each as owned, orphaned or foreign, and the end of the owned orphans
(kb/_self/backlog.md, Working on items; kb/_self/tools.md).

  procs                 list them (read only): pid, parent, age, class, command name, and where it runs
  procs --record PID    note that the autopilot started PID: its pid, start time and command name go to
                        `_cache/procs/owned.json` under the clone's main checkout (never committed)
  procs --end [--grace SECONDS]
                        end each owned orphan that is still an owned orphan after the grace, with the process-tree
                        end the intake drift check uses (`bl_intake.end_tree`: the process group, `taskkill /T /F`),
                        and every process under it; prints each action

Classes: `owned` (recorded, parent alive), `owned orphan` (recorded, parent gone), `orphan` (parent gone, not
recorded) and `foreign` (anything else: another session's). A record matches on the pid AND the start time, so a
reused pid is not owned. Only an owned orphan is ever signaled, never this process or one it descends from; an orphan
nobody recorded and a foreign process are named for the operator and left alone. A process's command line and
environment are never read: only its command name is printed. Where a host cannot list working directories (Windows)
it says so. Exit codes: 0 listed (also: nothing to end, or a host that cannot check, for a plain list), 1 an owned
orphan could not be ended, or `--end`/`--record` on a host that cannot check, 2 a bad request.

Standard library only; imports `bl_base`, `bl_cli` and `bl_intake`, never `backlog` (a layer rule). It registers its
own subcommand when imported, so `backlog.py` carries only the import.
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import bl_base
import bl_cli
import bl_intake
from bl_base import Refused, Rejected, say

REAPERS = ("init", "systemd", "launchd")  # a parent with one of these names has adopted an orphan
GRACE_S = 10.0  # seconds an owned orphan must stay one before it is ended
GONE_S = 5.0  # seconds to wait for an ended process to leave the table
RECORDS = ("_cache", "procs", "owned.json")  # under the clone's main checkout; `_cache/` is never committed
OWNED, OWNED_ORPHAN, ORPHAN, FOREIGN = "owned", "owned orphan", "orphan", "foreign"


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


# ---------------------------------------------------------------- the clone's checkouts and the record

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


def main_checkout(root):
    """The clone's main checkout, where the record lives, so a record made in one worktree is read in another."""
    try:
        common = (Path(root) / bl_base.git(root, "rev-parse", "--git-common-dir").strip()).resolve()
        return common.parent
    except (Refused, OSError):
        return Path(root).resolve()


def records_path(root):
    return main_checkout(root).joinpath(*RECORDS)


def load_records(root):
    """[{pid, start, comm, recorded}] of what the autopilot started; [] when there is no readable file."""
    try:
        data = json.loads(records_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("owned") if isinstance(data, dict) else None
    return [r for r in rows or [] if isinstance(r, dict) and isinstance(r.get("pid"), int)
            and isinstance(r.get("start"), int)]


def save_records(root, rows):
    path = records_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"owned": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def ancestors(tab, pid):
    """The pids above PID in the table, nearest first."""
    out = []
    while pid in tab and tab[pid][0] > 1 and tab[pid][0] not in out:
        pid = tab[pid][0]
        out.append(pid)
    return out


def record(root, pids, tab=None):
    """Note that the autopilot started each pid in PIDS: its start time and command name are read now. A pid that
    does not run, this process and the processes above it are refused. Records of processes that are gone are
    dropped. Returns the lines to print."""
    tab = process_table() if tab is None else tab
    if tab is None:
        raise Refused("procs --record: cannot read the process table on this host")
    own = {os.getpid(), *ancestors(tab, os.getpid())}
    rows = [r for r in load_records(root) if r["pid"] in tab and tab[r["pid"]][1] == r["start"]]
    lines = []
    for pid in pids:
        if pid in own or pid <= 1:
            raise Refused(f"procs --record: pid {pid} is this process, one above it, or the system's: never recorded")
        if pid not in tab:
            raise Refused(f"procs --record: no process runs with pid {pid}")
        _, start, comm = tab[pid]
        rows = [r for r in rows if r["pid"] != pid] + [{"pid": pid, "start": start, "comm": comm,
                                                         "recorded": int(time.time())}]
        lines.append(f"recorded pid {pid} ({comm}) as started by the autopilot")
    save_records(root, sorted(rows, key=lambda r: r["pid"]))
    return lines


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


def classify(procs, tab, rows):
    """Each process of PROCS with its `kind`: owned and owned orphan when a record (ROWS) matches its pid and start
    time, orphan when its parent is gone and nothing recorded it, foreign otherwise."""
    mine = {(r["pid"], r["start"]) for r in rows}
    out = []
    for p in procs:
        gone = orphaned(tab, p["pid"])
        if (p["pid"], p["start"]) in mine:
            kind = OWNED_ORPHAN if gone else OWNED
        else:
            kind = ORPHAN if gone else FOREIGN
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
    return classify(inventory(root, tab, cwds), tab, load_records(root)), tab, None


# ---------------------------------------------------------------- the end

class Target:
    """What `bl_intake.end_tree` takes: a pid, and a kill that ends only it."""

    def __init__(self, pid):
        self.pid = pid

    def kill(self):
        os.kill(self.pid, signal.SIGKILL if os.name == "posix" else signal.SIGTERM)


def descendants(tab, pid):
    """The pids under PID in the table, deepest first."""
    kids = {}
    for q, (pp, _, _) in tab.items():
        kids.setdefault(pp, []).append(q)
    out, stack = [], list(kids.get(pid, []))
    while stack:
        q = stack.pop()
        out.append(q)
        stack.extend(kids.get(q, []))
    return out[::-1]


def end_pid(pid):
    """End PID with its process tree: the group it leads (`end_tree`), but never a group this process belongs to."""
    if os.name == "posix":
        try:
            if os.getpgid(pid) == os.getpgrp():
                os.kill(pid, signal.SIGKILL)
                return
        except (ProcessLookupError, PermissionError):
            return
    bl_intake.end_tree(Target(pid))


def gone(pid, start, wait=GONE_S):
    """True once no process runs with PID and START, waiting up to WAIT seconds."""
    deadline = time.monotonic() + wait
    while True:
        tab = process_table() or {}
        if pid not in tab or tab[pid][1] != start:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def end_owned_orphans(root, grace, say=say, sleep=time.sleep, snap=None, ender=end_pid):
    """End each owned orphan that is still one, with the same pid and start time, once GRACE seconds have passed
    since it was first seen. Never a foreign or unrecorded process, this process or one above it. Prints each action
    through SAY. Returns (ended, failed) counts; None when the host cannot say."""
    snap = snapshot if snap is None else snap
    procs, tab, why = snap(root)
    if procs is None:
        say(f"procs: cannot check this host ({why}); nothing ended")
        return None
    first = [p for p in procs if p["kind"] == OWNED_ORPHAN]
    for p in procs:
        if p["kind"] in (ORPHAN, FOREIGN):
            say(f"left pid {p['pid']} ({p['comm']}) in {p['where']}: {p['kind']}, not started by the autopilot; "
                "for the operator, never signaled")
    if not first:
        say("procs: no owned orphan to end")
        return 0, 0
    say(f"procs: {len(first)} owned orphan(s); waiting {grace:g}s before ending them")
    sleep(grace)
    procs, tab, why = snap(root)
    if procs is None:
        say(f"procs: cannot check this host ({why}); nothing ended")
        return None
    now = {(p["pid"], p["start"]): p for p in procs}
    protected = {os.getpid(), *ancestors(tab, os.getpid())}
    ended = failed = 0
    for p in first:
        cur = now.get((p["pid"], p["start"]))
        if cur is None:
            say(f"gone pid {p['pid']} ({p['comm']}): it ended within the grace")
        elif cur["kind"] != OWNED_ORPHAN:
            say(f"left pid {p['pid']} ({p['comm']}): no longer an owned orphan ({cur['kind']})")
        elif p["pid"] in protected:
            say(f"left pid {p['pid']} ({p['comm']}): this process or one above it")
        else:
            for q in descendants(tab, p["pid"]):
                if q not in protected:
                    ender(q)
            ender(p["pid"])
            if gone(p["pid"], p["start"]):
                ended += 1
                say(f"ended pid {p['pid']} ({p['comm']}) in {p['where']}: owned orphan after {grace:g}s, "
                    "its process tree with it")
            else:
                failed += 1
                say(f"could not end pid {p['pid']} ({p['comm']}) in {p['where']}: it still runs")
    return ended, failed


# ---------------------------------------------------------------- the command

def args_procs(p):
    p.add_argument("--record", type=int, action="append", default=[], metavar="PID",
                   help="note that the autopilot started PID (its pid, start time and command name)")
    p.add_argument("--end", action="store_true",
                   help="end each owned orphan still one after the grace; never a foreign or unrecorded process")
    p.add_argument("--grace", type=float, default=None, metavar="SECONDS",
                   help=f"with --end: how long an owned orphan must stay one first (default {GRACE_S:g})")


def cmd_procs(bl, a):
    if a.grace is not None and not a.end:
        raise Rejected("procs: --grace goes with --end")
    if a.grace is not None and a.grace < 0:
        raise Rejected("procs: --grace is not negative")
    root = str(bl.root)
    if a.record:
        for text in record(root, a.record):
            say(text)
    if a.end:
        result = end_owned_orphans(root, GRACE_S if a.grace is None else a.grace)
        return 1 if result is None or result[1] else 0
    procs, _, why = snapshot(root)
    if procs is None:
        say(f"procs: cannot list processes by working directory on this host ({why})")
        return 0
    now = time.time()
    say(f"procs: {len(procs)} process(es) with a working directory in a checkout of this clone")
    for p in procs:
        say(line(p, now))
    counts = {k: sum(p["kind"] == k for p in procs) for k in (OWNED, OWNED_ORPHAN, ORPHAN, FOREIGN)}
    say("procs: " + ", ".join(f"{n} {k}" for k, n in counts.items()) + "; only an owned orphan is ever ended "
        "(procs --end), the others are named for the operator and never signaled")
    return 0


bl_cli.register("procs", cmd_procs, args_procs, help="list the processes left in this clone's checkouts; --end ends owned orphans")
