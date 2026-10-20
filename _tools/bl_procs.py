"""`backlog.py procs`: the processes whose working directory lies in a checkout of this clone (the main checkout or any
worktree `git worktree list` names, and, in a workspace whose backlog.json declares `repositories`, each repository's
checkout and worktrees), each as an orphan or foreign (kb/_self/backlog.md, Processes left running; kb/_self/tools.md).

  procs                 list them (read only): pid, parent, age, class, command name, and where it runs

Classes: `orphan` (its parent is gone: a background run a session left behind), `detached` (its parent is gone, but it
leads its own process group, started with `start_new_session`, and still has a live child: a launcher a session started
apart and left at work; named in no alert and by no `selfcheck`), `hook` (an orphan whose standard output
is the query log's distill.log and that is still at work: the run a session's end hook started, which waits for the
distill lock up to the query log's USAGE_LOCK_WAIT_S, delivers with its parent gone, and ends on its own; it is at work
while the distill lock records its pid, or while it is younger than USAGE_LOCK_WAIT_S plus HOOK_MARGIN_S) and `foreign`
(anything else: a live session's own work). `procs` signals nothing: an orphan is named for the operator, who ends it
when it is theirs, and `backlog.py selfcheck` fails while one runs. Two callers signal, through `end_pids` (SIGTERM, then
SIGKILL after END_WAIT_S): `end_orphans(worktree)`, which `dispatch` calls once the worker has exited, to end the orphans in
the worker's worktree (the MCP servers its session started), and prints each pid and command name it ended, and `bl_clean`'s
`tidy --class process --apply` for a process an own record names. A hook in flight is named with its age and fails
nothing, and a distill run past both is a stuck one, an orphan. HOOK_GRACE_S is the shorter wait `land` makes. A
process's command line and environment are never read: only its command name is printed, and a hook is told by the file
its standard output is. Where a host cannot list working directories (Windows) it says so. The one exception is
`windows_snapshot`, which kbmon's sessions panel reads on Windows: the host's process table through PowerShell
(`Get-CimInstance Win32_Process`: pid, parent, start, command name and command line as JSON) places a process in the
checkout whose path its command line names; the command line is only matched against the checkout paths, never printed
or kept, and a process whose command line names no checkout is not listed. Exit codes: 0 listed (also on a host that
cannot check), 2 a bad request.

Standard library only; imports `bl_base` and `bl_cli`, never `backlog` (a layer rule). It registers its own subcommand
when imported, so `backlog.py` carries only the import.
"""
import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import bl_base
import bl_cli
from bl_base import Refused, say

REAPERS = ("init", "systemd", "launchd")  # a parent with one of these names has adopted an orphan
ORPHAN, HOOK, DETACHED, FOREIGN = "orphan", "hook", "detached", "foreign"
HOOK_GRACE_S = 60  # how long `land` waits for a session-end hook's run to end
HOOK_MARGIN_S = 120  # past the query log's USAGE_LOCK_WAIT_S, how long a distill run that holds no lock is still at work
END_WAIT_S = 3  # how long `end_orphans` waits for a process to end on SIGTERM before it sends SIGKILL
HOOK_LOG =("_cache", "querylog")  # under a checkout: the directory ql_base.places() gives a clone, whose distill.log is
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


def lock_holders(bases):
    """The pids the distill lock of each checkout in BASES records (`ql_base.acquire` writes its holder's own)."""
    import ql_base
    out = set()
    for b in bases:
        data = ql_base.read_json(os.path.join(b, *HOOK_LOG, ql_base.LOCK_NAME), {})
        if isinstance(data, dict) and isinstance(data.get("pid"), int):
            out.add(data["pid"])
    return out


def hook_run_s():
    """How long a distill run that holds no lock is still at work: the wait for the lock plus HOOK_MARGIN_S."""
    import ql_distill
    return ql_distill.USAGE_LOCK_WAIT_S + HOOK_MARGIN_S


# ---------------------------------------------------------------- Windows: no working directory

WIN_SHELLS = ("powershell", "pwsh")  # Windows PowerShell first, then PowerShell 7; each found on PATH by `shutil.which`
WIN_QUERY = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine,"
             "@{n='Start';e={if ($_.CreationDate) {[int64]([DateTimeOffset]$_.CreationDate).ToUnixTimeSeconds()}}} "
             "| ConvertTo-Json -Compress")


def windows_rows():
    """The process table of a Windows host as JSON rows (`ProcessId`, `ParentProcessId`, `Name`, `CommandLine`,
    `Start`) read through PowerShell's `Get-CimInstance Win32_Process`, or None when no PowerShell answers. A single
    process comes as an object, not a list."""
    for shell in WIN_SHELLS:
        if not shutil.which(shell):
            continue
        text = run_quiet([shell, "-NoProfile", "-NonInteractive", "-Command", WIN_QUERY])
        try:
            rows = json.loads(text or "")
        except ValueError:
            continue
        rows = [rows] if isinstance(rows, dict) else rows
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return None


def windows_name(name):
    """The command name of a Windows image name: `claude.exe` is `claude`, as a POSIX host names it."""
    name = command_name(str(name or ""))
    return name[:-4] if name.lower().endswith(".exe") else name


def windows_base(command_line, bases):
    """The checkout in BASES whose path appears in COMMAND_LINE (the longest, so a worktree inside the main checkout wins;
    case and the kind of slash ignored), or None. The command line is only searched: nothing of it is returned."""
    text = command_line.replace("\\", "/").lower()
    found = [b for b in bases if re.search(re.escape(b.replace("\\", "/").lower().rstrip("/")) + r"(?![\w.-])", text)]
    return max(found, key=len, default=None)


def windows_snapshot(root):
    """(classified processes, table, None, blind), or (None, None, why, 0): the processes of a Windows host whose command
    line names a checkout of the clone at ROOT. Windows exposes no working directory, so a process is placed by a
    checkout path in its command line; one whose command line names none is not listed, and BLIND counts the processes
    whose command line could not be read at all (another account's, unless run elevated). Each process is
    `inventory`'s row with its `where` the checkout's directory name and `base` its real path. A command line is
    matched and dropped, never printed or kept."""
    rows = windows_rows()
    if rows is None:
        return None, None, "PowerShell did not answer Get-CimInstance Win32_Process", 0
    bases = checkouts(root)
    now = int(time.time())
    tab, placed, blind = {}, {}, 0
    for r in rows:
        pid, ppid = r.get("ProcessId"), r.get("ParentProcessId")
        if not isinstance(pid, int) or isinstance(pid, bool) or not isinstance(ppid, int) or isinstance(ppid, bool):
            continue
        start = r.get("Start")
        tab[pid] = (ppid, start if isinstance(start, int) and not isinstance(start, bool) else now,
                    windows_name(r.get("Name")))
        line = r.get("CommandLine")
        if not isinstance(line, str) or not line:
            blind += 1
            continue
        base = windows_base(line, bases)
        if base:
            placed[pid] = base
    procs = [{"pid": pid, "ppid": tab[pid][0], "start": tab[pid][1], "comm": tab[pid][2],
              "where": Path(base).name, "base": base} for pid, base in sorted(placed.items())]
    return classify(procs, tab, holders=lock_holders(bases)), tab, None, blind


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


def leads_group(pid):
    """True when PID leads its own process group (a process started with `start_new_session` does); False where the
    host has no process groups (Windows) or PID is gone."""
    try:
        return os.getpgid(pid) == pid
    except (AttributeError, OSError):
        return False


def classify(procs, tab, hooks=(), now=None, holders=()):
    """Each process of PROCS with its `kind`: foreign while its parent lives, else hook when its pid is in HOOKS (the
    runs whose standard output is a distill.log) and it is in HOLDERS (the pids a distill lock records) or started
    less than `hook_run_s()` before NOW, else detached when it is no hook's run, leads its own process group and a live
    process of TAB is its child (a launcher a session started apart and left at work), else orphan."""
    now = time.time() if now is None else now
    parents = {v[0] for v in tab.values()}
    out = []
    for p in procs:
        if not orphaned(tab, p["pid"]):
            kind = FOREIGN
        elif p["pid"] in hooks and (p["pid"] in holders or now - p["start"] < hook_run_s()):
            kind = HOOK
        elif p["pid"] not in hooks and p["pid"] in parents and leads_group(p["pid"]):
            kind = DETACHED
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
    bases = checkouts(root)
    procs = inventory(root, tab, cwds, bases)
    hooks = hook_pids(root, [p["pid"] for p in procs if orphaned(tab, p["pid"])], bases)
    return classify(procs, tab, hooks, holders=lock_holders(bases)), tab, None


# ---------------------------------------------------------------- the command

def end_orphans(worktree):
    """End the orphans (class `orphan` or `detached`) whose working directory lies in WORKTREE: the processes a headless
    worker session started there (its MCP servers) and left running when it exited. A process whose parent lives (foreign)
    and a hook's distill run at work are left alone. Each gets SIGTERM, and SIGKILL if it still runs END_WAIT_S later.
    Returns [(pid, command name)] of those ended, [] when none or when this host cannot list working directories."""
    base = os.path.realpath(worktree)
    cwds, _ = cwd_map()
    tab = process_table() if cwds is not None else None
    if cwds is None or tab is None:
        return []
    procs = inventory(base, tab, cwds, [base])
    hooks = hook_pids(base, [p["pid"] for p in procs if orphaned(tab, p["pid"])], [base])
    pids = {p["pid"]: p["comm"] for p in classify(procs, tab, hooks, holders=lock_holders([base])) if p["kind"] in (ORPHAN, DETACHED)}
    return [(pid, pids[pid]) for pid in end_pids(list(pids))]


def end_pids(pids):
    """Send SIGTERM to each of PIDS, and SIGKILL to those still alive END_WAIT_S later (a host with no SIGKILL, Windows,
    ends a process with the first). Returns the pids that took the SIGTERM; one gone since the scan, or not ours, is left
    out."""
    ended = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:  # gone since the scan, or not ours
            continue
        ended.append(pid)
    deadline = time.time() + END_WAIT_S
    for pid in ended:
        while time.time() < deadline and alive(pid):
            time.sleep(0.1)
        if alive(pid):
            with contextlib.suppress(OSError):
                os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
            for _ in range(10):  # a killed process leaves the table within a moment
                if not alive(pid):
                    break
                time.sleep(0.1)
    return ended


def running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def alive(pid):
    """Whether PID runs: a zombie, which the process table leaves out, does not."""
    if not running(pid):
        return False
    tab = process_table()
    return True if tab is None else pid in tab


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
    counts = {k: sum(p["kind"] == k for p in procs) for k in (ORPHAN, HOOK, DETACHED, FOREIGN)}
    say("procs: " + ", ".join(f"{n} {k}" for k, n in counts.items()) + "; nothing is signaled: an orphan is named for "
        f"the operator, who ends it when it is theirs, and a hook is a session's end distill run at work: it holds "
        f"the distill lock or is under {hook_run_s()}s old")
    return 0


bl_cli.register("procs", cmd_procs, args_procs, help="list the processes left in this clone's checkouts, orphans named")
