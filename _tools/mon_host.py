"""kbmon's host panel (kb/_self/monitoring.md): the load, the holders of the host's two locks and the suite against the
numbers of the tests ceiling.

The panel reads and changes nothing. The load is `os.getloadavg()` with the core count (`unsupported` where the host has
no such call); the locks are the files `tests.py` and `kg_lock.py` write in the host lock directory, read through their
readers (`tests.read_holder`, `tests.pid_alive`, `kg_lock.holder_step`): a holder whose pid no longer runs is none. A
holder's clone is `this` (the clone the panel reads) or `other`, never a path. The ceiling is `tests.read_ceiling`'s, the
suite's files the `test_*.py` of the clone, and its ids and the seconds of the last full run the newest passing `test.run`
row of mode `full` that ran pytest, from the ops rows. Imports `mon_base`; `tests`, `kg_lock` and `bl_stall` where it
reads them.
"""
import os
import sys
from pathlib import Path

import mon_base

CELLS = 10  # cells of a bar
WARN_PCT = 80  # a bar from here on is a warning, at 100 an error
LABEL = 10  # columns of a body row's label
WIDE = 100  # columns from which the three bars share one row
UNSUPPORTED = "unsupported"


def load():
    """[1, 5, 15 minute load] or `unsupported` where the host has no `os.getloadavg` or it fails."""
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        return UNSUPPORTED


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
    """{max_ids, max_files, max_seconds, ids, files, last_run_s} against the clone's `tests_ceiling.json`; `{"error": ...}`
    for the file when `tests.read_ceiling` refuses it."""
    import tests
    root = Path(root)
    try:
        c = tests.read_ceiling(str(root / "_tools" / "tests_ceiling.json"), str(root / "kb" / "_self" / "_decisions.csv"))
    except tests.CeilingError as e:
        return {"error": " ".join(str(e).split())[:mon_base.ERROR_CHARS]}
    ids, seconds = last_full_run(root)
    files = sum(1 for p in (root / "_tools").glob("test_*.py"))
    return {"max_ids": c["max_ids"], "max_files": c["max_files"], "max_seconds": c["max_seconds"].get(sys.platform),
            "ids": ids, "files": files, "last_run_s": seconds}


def collect(ctx):
    import kg_lock
    import tests
    base = tests.host_lock_dir()
    cores = os.cpu_count()
    return {"load": load(), "cores": cores if isinstance(cores, int) else None,
            "suite_lock": holder(os.path.join(base, tests.HOST_LOCK_NAME), ctx.root),
            "main_lock": holder(os.path.join(base, kg_lock.LOCK_NAME), ctx.root),
            "ceiling": ceiling(ctx.root)}


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


def ceiling_rows(c, width):
    """The ceiling's three measures: `ids`, `files` and `last run`, as one row of the worst gutter from WIDE columns,
    else three aligned rows each with its own gutter."""
    if "error" in c:
        return ["! " + "ceiling".ljust(LABEL) + str(c["error"])]
    cells = [("ids", c["ids"], c["max_ids"], ""), ("files", c["files"], c["max_files"], ""),
             ("last run", c["last_run_s"], c["max_seconds"], " s")]
    made = [(name, flag(used, limit), bar(used, limit), unit) for name, used, limit, unit in cells]
    if width >= WIDE:
        worst = max((f for _, f, _, _ in made), key=lambda f: {"": 0, "! ": 1, "!!": 2}[f])
        text = " · ".join(f"{name} {n}{unit} {b} {p}" for name, _, (n, b, p), unit in made)
        return [worst + "ceiling".ljust(LABEL) + text]
    name_w = max(len(n) for n, *_ in made)
    num_w = max(len(b[0]) + len(u) for _, _, b, u in made)
    out = []
    for i, (name, f, (n, b, p), unit) in enumerate(made):
        label = "ceiling" if i == 0 else ""
        out.append(f + label.ljust(LABEL) + f"{name.ljust(name_w)}  {(n + unit).rjust(num_w)} {b} {p}")
    return out


def lines(data, width=80):
    """The body rows: the load with the cores, the two locks' holders, then the ceiling's bars (`! ` from 80%, `!!` at 100%)."""
    ld = data.get("load")
    shown = "unsupported" if ld == UNSUPPORTED or not isinstance(ld, list) else " · ".join(f"{x:.2f}" for x in ld)
    cores = data.get("cores")
    rows = ["load".ljust(LABEL) + shown + (f" · {cores} cores" if cores else "")]
    rows += [lock_row("suite", data.get("suite_lock")), lock_row("main", data.get("main_lock"))]
    return rows + ceiling_rows(data.get("ceiling") or {"error": "no ceiling"}, width)
