"""kbmon's host panel (kb/_self/monitoring.md): the load, the holders of the host's two locks and the suite against the
numbers of the tests ceiling.

The panel reads and changes nothing. The load is `os.getloadavg()` with the core count (`unsupported` where the host has
no such call); the locks are the files `tests.py` and `kg_lock.py` write in the host lock directory, read through their
readers (`tests.read_holder`, `tests.pid_alive`, `kg_lock.holder_step`): a holder whose pid no longer runs is none. A
holder's clone is `this` (the clone the panel reads) or `other`, never a path. The ceiling is `tests.read_ceiling`'s, the
suite's files the `test_*.py` of the clone, and its ids and the seconds of the last full run the newest passing `test.run`
row of mode `full` that ran pytest, from the ops rows. `land_lock` is the clone's landing lock (`bl_close.landing_lock_path`,
read through the same readers): when a live process holds it, {item, title, step (the newest `land.step` of the item's
landing in the ops rows, null before its first), since, pid, clone, queue}, `queue` being the other items whose coord run
state is `landing` as {id, title} in id order, each title that of the clone's item file; null while no live process holds
it. The CPU groups come from one `ps -A -o pid=,pcpu=,args=` listing: each
command line is matched against fixed patterns in memory and only its kind, clone, CPU and count are kept (`unsupported`
where there is no `ps`). Imports `mon_base`; `tests`, `kg_lock`, `bl_stall`, `bl_close` and `mon_sessions` (the clone's backlog, the run states and the landing steps) where it reads them.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import mon_base

LOW_DISK_PCT = 10  # percent free below which the clone's file system is an alert
CELLS = 10  # cells of a bar
WARN_PCT = 80  # a bar from here on is a warning, at 100 an error
LABEL = 10  # columns of a body row's label
GUTTER = 2  # columns the view puts before a body row
UNSUPPORTED = "unsupported"
PS_TIMEOUT = 5  # seconds the process listing may take


def load():
    """[1, 5, 15 minute load] or `unsupported` where the host has no `os.getloadavg` or it fails."""
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        return UNSUPPORTED


def kind_of(args, root):
    """(kind, clone) of one process from its command line ARGS, by fixed patterns: `kbmon`, `fseventsd`, `tests` (pytest or the
    clone's `tests.py` or `test_*.py`), `kb-tools` (any other script of a `_tools` directory), `claude` or `other`; `clone`
    is `this` for an absolute script path under ROOT, `other` for one elsewhere, else None (a relative path, which the
    listing cannot place without the process's working directory, is None too). Only the pair leaves the function."""
    words = args.split()
    first = os.path.basename(words[0]) if words else ""
    script = next((w for w in words if re.search(r"(^|/)_tools/[\w.-]+\.py$", w)), "")
    name = os.path.basename(script)
    if name == "kbmon.py":
        kind = "kbmon"
    elif first == "fseventsd":
        return "fseventsd", None
    elif "pytest" in words or name == "tests.py" or re.match(r"test_[\w-]*\.py$", name):
        kind = "tests"
    elif script:
        kind = "kb-tools"
    elif first == "claude":
        return "claude", None
    else:
        return "other", None
    if not script or not os.path.isabs(script):
        return kind, None
    mine = tuple(str(p) + "/" for p in {str(root), os.path.realpath(root)})
    return kind, "this" if script.startswith(mine) else "other"


def groups(root):
    """The CPU consumers of one `ps -A -o pid=,pcpu=,args=` listing as [{kind, clone, cpu, procs}] in CPU order, or
    `unsupported` where the host has no `ps` or it fails. The command lines are matched in memory and dropped."""
    if sys.platform == "win32" or not shutil.which("ps"):
        return UNSUPPORTED
    try:
        p = subprocess.run(["ps", "-A", "-o", "pid=,pcpu=,args="], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=PS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return UNSUPPORTED
    if p.returncode != 0:
        return UNSUPPORTED
    sums = {}
    for line in p.stdout.splitlines():
        parts = line.split(None, 2)
        try:
            cpu = float(parts[1].replace(",", "."))
        except (IndexError, ValueError):
            continue
        key = kind_of(parts[2] if len(parts) > 2 else "", root)
        cell = sums.setdefault(key, [0.0, 0])
        cell[0] += cpu
        cell[1] += 1
    made = [{"kind": k, "clone": c, "cpu": round(v[0], 1), "procs": v[1]} for (k, c), v in sums.items()]
    return sorted(made, key=lambda g: (-g["cpu"], g["kind"], g["clone"] or ""))


def holder(path, root):
    """{pid, clone, started[, step]} of the lock file PATH when a live process holds it, else None; `clone` is `this`
    when the holder's clone is ROOT."""
    import kg_lock
    import tests
    text = tests.read_lock(path)
    rec = tests.parse_holder(text) if text is not None else None
    if rec is None or not tests.pid_alive(rec["pid"]):
        return None
    same = os.path.realpath(rec["clone"]) == os.path.realpath(root)
    out = {"pid": rec["pid"], "clone": "this" if same else "other", "started": rec["started"]}
    if os.path.basename(path) == kg_lock.LOCK_NAME:
        out["step"] = kg_lock.holder_step(text)
    return out


def land_lock(ctx):
    """The landing lock's holder as `collect` describes `land_lock`, or None when no live process holds it (or the clone
    has no landing lock path)."""
    import bl_close
    import mon_sessions
    import tests
    try:
        path = bl_close.landing_lock_path(ctx.root)
    except Exception:  # noqa: BLE001 - a directory git cannot read has no landing lock
        return None
    text = tests.read_lock(str(path))
    rec = tests.parse_holder(text) if text is not None else None
    if rec is None or not tests.pid_alive(rec["pid"]):
        return None
    item = bl_close.landing_holder_item(text)
    bl = mon_sessions.backlog(ctx.root)

    def title(ident):
        return None if bl is None or ident in bl.withheld else (bl.items.get(ident) or {}).get("title")

    states = mon_sessions.run_states(ctx) or {}
    queue = [{"id": i, "title": title(i)} for i in sorted(states) if states[i] == "landing" and i != item]
    same = os.path.realpath(rec["clone"]) == os.path.realpath(ctx.root)
    return {"item": item, "title": title(item), "step": mon_sessions.landing_steps(ctx.root).get(item), "since": rec["started"],
            "pid": rec["pid"], "clone": "this" if same else "other", "queue": queue}


def last_full_run(root):
    """(ids, seconds) of the newest passing full `test.run` row that ran pytest, or (None, None)."""
    try:
        import bl_stall
        rows = [r for r in bl_stall.ops_rows(str(root)) if r.get("event") == "test.run" and r.get("mode") == "full"
                and r.get("exit") == 0 and not r.get("reused")]
    except Exception:  # noqa: BLE001 - an unreadable log is no run
        return None, None
    if not rows:
        return None, None
    last = rows[-1]
    ids = sum(last.get(k) or 0 for k in ("passed", "failed", "skipped"))
    ms = last.get("ms")
    return ids, (round(ms / 1000, 1) if isinstance(ms, (int, float)) else None)


def ceiling(root):
    """{max_ids, max_files, max_seconds, profile, ids, files, last_run_s} against the clone's `tests_ceiling.json`, its
    max_seconds times the CI factor and the factor of the clone's profile (`_private/host.json`); `{"error": ...}` for
    the file when `tests.read_ceiling` refuses it."""
    import tests
    root = Path(root)
    try:
        c = tests.read_ceiling(str(root / "_tools" / "tests_ceiling.json"), str(root / "kb" / "_self" / "_decisions.csv"))
    except tests.CeilingError as e:
        return {"error": " ".join(str(e).split())[:mon_base.ERROR_CHARS]}
    ids, seconds = last_full_run(root)
    files = sum(1 for p in (root / "_tools").glob("test_*.py"))
    profile = tests.read_profile(root)
    limit = c["max_seconds"].get(sys.platform)
    return {"max_ids": c["max_ids"], "max_files": c["max_files"],
            "max_seconds": None if limit is None else limit * tests.seconds_factor() * tests.PROFILES[profile],
            "profile": profile, "ids": ids, "files": files, "last_run_s": seconds}


def disk(root):
    """{free_bytes, total_bytes, free_pct} of the file system that holds ROOT (`free_pct` rounded to one decimal), or
    `{"error": ...}` where `shutil.disk_usage` refuses it."""
    try:
        u = shutil.disk_usage(root)
    except OSError as e:
        return {"error": " ".join(str(e).split())[:mon_base.ERROR_CHARS]}
    return {"free_bytes": u.free, "total_bytes": u.total, "free_pct": round(u.free * 100 / u.total, 1) if u.total else 0.0}


def alerts(data):
    """The alerts of the panel's data: one `disk` alert (id `host.disk`) while the clone's file system has under LOW_DISK_PCT
    percent free."""
    d = data.get("disk")
    pct = d.get("free_pct") if isinstance(d, dict) else None
    if not isinstance(pct, (int, float)) or isinstance(pct, bool) or pct >= LOW_DISK_PCT:
        return []
    return [{"kind": "disk", "id": "host.disk", "panel": "host", "since": "",
             "message": f"disk low: {pct:g}% free ({gigabytes(d.get('free_bytes'))} of {gigabytes(d.get('total_bytes'))})"}]


def gigabytes(n):
    return f"{n / 10 ** 9:.1f} GB" if isinstance(n, (int, float)) and not isinstance(n, bool) else "? GB"


def collect(ctx):
    import kg_lock
    import tests
    base = tests.host_lock_dir()
    cores = os.cpu_count()
    return {"load": load(), "cores": cores if isinstance(cores, int) else None,
            "suite_lock": holder(os.path.join(base, tests.HOST_LOCK_NAME), ctx.root),
            "main_lock": holder(os.path.join(base, kg_lock.LOCK_NAME), ctx.root),
            "land_lock": land_lock(ctx), "ceiling": ceiling(ctx.root), "disk": disk(ctx.root), "groups": groups(ctx.root),
            "cpu_basis": "recent" if sys.platform == "darwin" else "lifetime"}


def bar(used, limit):
    """`used/limit [|||||.....] pct%` with CELLS cells; the percentage and the cells are blank for a number not known."""
    shown = "?" if used is None else f"{used:g}"
    if not isinstance(limit, (int, float)) or isinstance(limit, bool) or limit <= 0 or used is None:
        return f"{shown}/{'?' if limit is None else limit}", "[" + "." * CELLS + "]", "-"
    pct = round(used * 100 / limit)
    full = min(CELLS, max(0, pct * CELLS // 100))
    return f"{shown}/{limit:g}", "[" + "|" * full + "." * (CELLS - full) + "]", f"{pct}%"


def flag(used, limit):
    """The gutter of a bar's row: `!!` at 100% and more, `! ` from WARN_PCT, else nothing."""
    if used is None or not isinstance(limit, (int, float)) or limit <= 0:
        return ""
    pct = used * 100 / limit
    return "!!" if pct >= 100 else "! " if pct >= WARN_PCT else ""


def since(started):
    """`YYYY-MM-DD HH:MMZ` of a holder's start stamp, else the stamp as it is."""
    s = str(started)
    return s[:16].replace("T", " ") + "Z" if len(s) == 20 and s[10] == "T" and s.endswith("Z") else s


def lock_row(label, rec):
    if rec is None:
        return label.ljust(LABEL) + "none"
    parts = [f"pid {rec['pid']}", f"{rec['clone']} clone", f"since {since(rec['started'])}"]
    if "step" in rec:
        parts.append(f"step {rec['step']}")  # free text: last, so a narrow terminal cuts it first
    return label.ljust(LABEL) + " · ".join(parts)


def land_row(rec):
    """The landing lock's row: `landing` and the item (its title, else its id), its step, since when, and the titles of the
    items queued behind it (a title cut to 30 characters); `none` while no live process holds the lock."""
    if not isinstance(rec, dict):
        return "landing".ljust(LABEL) + "none"
    parts = [str(rec.get("title") or rec.get("item")), f"step {rec.get('step') or '-'}", f"since {since(rec.get('since'))}"]
    queue = [q for q in rec.get("queue") or [] if isinstance(q, dict)]
    if queue:
        names = [str(q.get("title") or q.get("id"))[:30] for q in queue[:3]]
        parts.append(f"{len(queue)} queued: " + ", ".join(names) + (f", +{len(queue) - 3} more" if len(queue) > 3 else ""))
    return "landing".ljust(LABEL) + " · ".join(parts)


def ceiling_rows(c, width):
    """The ceiling's three measures: `ids`, `files` and `last run` (named with the clone's profile when it is not
    `usual`), as one row of the worst gutter where the joined row fits WIDTH columns, else three aligned rows each with
    its own gutter."""
    if "error" in c:
        return ["! " + "ceiling".ljust(LABEL) + str(c["error"])]
    run = "last run" + (f" ({c['profile']})" if c.get("profile", "usual") != "usual" else "")
    cells = [("ids", c["ids"], c["max_ids"], ""), ("files", c["files"], c["max_files"], ""),
             (run, c["last_run_s"], c["max_seconds"], " s")]
    made = [(name, flag(used, limit), bar(used, limit), unit) for name, used, limit, unit in cells]
    text = " · ".join(f"{name} {n}{unit} {b} {p}" for name, _, (n, b, p), unit in made)
    if GUTTER + LABEL + len(text) <= width:
        worst = max((f for _, f, _, _ in made), key=lambda f: {"": 0, "! ": 1, "!!": 2}[f])
        return [worst + "ceiling".ljust(LABEL) + text]
    name_w = max(len(n) for n, *_ in made)
    num_w = max(len(b[0]) + len(u) for _, _, b, u in made)
    out = []
    for i, (name, f, (n, b, p), unit) in enumerate(made):
        label = "ceiling" if i == 0 else ""
        out.append(f + label.ljust(LABEL) + f"{name.ljust(name_w)}  {(n + unit).rjust(num_w)} {b} {p}")
    return out


def lines(data, width=80):
    """The body rows: the load with the cores, the two locks' holders, the landing lock's holder with its queue, then the ceiling's bars (`! ` from 80%, `!!` at 100%)."""
    ld = data.get("load")
    shown = "unsupported" if ld == UNSUPPORTED or not isinstance(ld, list) else " · ".join(f"{x:.2f}" for x in ld)
    cores = data.get("cores")
    rows = ["load".ljust(LABEL) + shown + (f" · {cores} cores" if cores else "")]
    rows += [lock_row("suite", data.get("suite_lock")), lock_row("main", data.get("main_lock")), land_row(data.get("land_lock"))]
    return rows + ceiling_rows(data.get("ceiling") or {"error": "no ceiling"}, width)
