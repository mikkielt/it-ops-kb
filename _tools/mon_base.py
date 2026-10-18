"""kbmon's shared ground (kb/_self/monitoring.md): the panels, a panel's run in a daemon thread under a timeout, the
snapshot and the reading of a saved one. Standard library only; every `mon_` module imports it and it imports no sibling.

  PANELS                 the seven panels, in the order a snapshot lists them
  Ctx                    what a panel reads: the clone `root`, the coord `store`, `url` and `key_file`
  Unsupported            a panel's `collect(ctx)` raises it when this host or this setting cannot give the panel
  panel_module(name)     the module `mon_<name>`, or None while no item has written it (the panel is then `absent`)
  snapshot(ctx, names, timeout, kept=None)
                         one dict of schema 1: every named panel run at once, each bounded by `timeout` seconds; the
                         ops rows are read once for all the panels (`OpsMemo`); with `kept` (a `Kept`, the live view's) a
                         panel that asks for it is served from its last result, and a run that outlasted its timeout is
                         waited for again instead of started a second time
  Kept                   the live view's memory between snapshots: the last `ok` result of each panel whose module sets
                         `REFRESH_S`, the run still going of a panel that timed out, and the ops rows
  OpsMemo                `bl_stall.ops_rows` read again only when its files changed and the last read is `floor` seconds old
  load_snapshot(path)    a saved snapshot, ValueError when it is no snapshot of schema 1

A panel module `mon_<name>.py` has `collect(ctx)`, which returns its data as a dict of JSON values and reads without
writing, and may have `lines(data)`, its text lines for `--once`, and `REFRESH_S`, the seconds the live view serves its
last result before it runs the panel again.
"""
import contextlib, datetime, importlib, json, os, threading, time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 1
PANELS = ("kb", "coord", "sessions", "querylog", "host", "sprint", "log")
STATES = ("ok", "timeout", "error", "absent", "unsupported")
ERROR_CHARS = 300  # characters of an exception's text a panel in state error keeps
OPS_PANELS = ("kb", "sessions", "host", "sprint", "log")  # the panels that read `bl_stall.ops_rows`
OPS_FLOOR_S = 30  # seconds the live view serves the ops rows read last, however its files changed meanwhile


@dataclass(frozen=True)
class Ctx:
    root: Path
    store: str | None = None
    url: str | None = None
    key_file: str | None = None


class Unsupported(Exception):
    """The panel cannot be shown here; its text is the reason."""


def panel_module(name):
    """The module `mon_<name>`, or None when it does not exist (a module that exists and fails to import is an error of
    the panel, so it raises)."""
    mod = "mon_" + name
    try:
        return importlib.import_module(mod)
    except ModuleNotFoundError as e:
        if e.name == mod:
            return None
        raise


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _one_line(text, n=ERROR_CHARS):
    return " ".join(str(text).split())[:n]


def _worker(module, ctx, box):
    start = time.monotonic()
    try:
        box["data"] = module.collect(ctx)
        box["state"] = "ok"
    except Unsupported as e:
        box["state"], box["data"] = "unsupported", {"reason": _one_line(e)}
    except Exception as e:  # noqa: BLE001 - a panel that fails is its own state, never a failure of the snapshot
        box["state"], box["data"] = "error", {"error": f"{type(e).__name__}: {_one_line(e)}"}
    box["seconds"] = time.monotonic() - start


class OpsMemo:
    """`bl_stall.ops_rows(root)` for the panels of one snapshot, or of a live view's snapshots. A read is served again while
    the spool and the committed sidecars (their names, times and sizes) are as they were or the read is under `floor`
    seconds old; one call at a time reads, the others wait for it, so panels that start together read once."""

    def __init__(self, floor=0.0):
        self.floor = floor
        self.lock = threading.Lock()
        self.kept = {}  # root -> (signature, taken, rows)

    @staticmethod
    def signature(root):
        import ql_capture
        import ql_store
        spool = ql_capture.spool_dir()
        files = sorted(Path(spool).glob("tools-*.jsonl")) if spool is not None and Path(spool).is_dir() else []
        files += ql_store.ops_files(Path(root) / "kb" / "_querylog")
        out = []
        for f in files:
            try:
                st = os.stat(f)
            except OSError:
                continue
            out.append((str(f), st.st_mtime_ns, st.st_size))
        return out

    def rows(self, read, root):
        with self.lock:
            kept = self.kept.get(root)
            if kept and time.monotonic() - kept[1] < self.floor:
                return kept[2]
            sig = self.signature(root)
            if kept and kept[0] == sig:
                self.kept[root] = (sig, time.monotonic(), kept[2])
                return kept[2]
            rows = read(root)
            self.kept[root] = (sig, time.monotonic(), rows)
            return rows


@contextlib.contextmanager
def ops_memo(memo):
    """`bl_stall.ops_rows` read through `memo` for the length of the block (the panels call it by that name)."""
    import bl_stall
    read = bl_stall.ops_rows
    bl_stall.ops_rows = lambda root: memo.rows(read, root)
    try:
        yield
    finally:
        bl_stall.ops_rows = read


class Kept:
    """What the live view remembers between snapshots (see `snapshot`)."""

    def __init__(self):
        self.ops = OpsMemo(OPS_FLOOR_S)
        self.results = {}  # panel -> (taken, entry): the last `ok` result of a panel with a `REFRESH_S`
        self.running = {}  # panel -> (thread, box) of a run that outlasted its timeout

    def fresh(self, name, module):
        got = self.results.get(name)
        if got and time.monotonic() - got[0] < getattr(module, "REFRESH_S", 0):
            return got[1]
        return None

    def keep(self, name, module, entry):
        if entry["state"] == "ok" and getattr(module, "REFRESH_S", 0):
            self.results[name] = (time.monotonic(), entry)


def run_panels(ctx, names, timeout, kept=None):
    """{name: {state, seconds[, data]}} for `names`. Every panel with a module runs in its own daemon thread, all at
    once, and the caller waits for each until `timeout` seconds after the start: a thread still running then is left
    behind (a daemon thread never holds the process at exit) and its panel is `timeout`. With `kept`, a panel is served
    from its last result inside its module's `REFRESH_S`, and the thread left behind is the one waited for next time."""
    started, runs, out = time.monotonic(), {}, {}
    for name in names:
        try:
            module = panel_module(name)
        except Exception as e:  # noqa: BLE001
            out[name] = {"state": "error", "seconds": 0.0, "data": {"error": f"{type(e).__name__}: {_one_line(e)}"}}
            continue
        if module is None:
            out[name] = {"state": "absent", "seconds": 0.0}
            continue
        if kept is not None and (hit := kept.fresh(name, module)) is not None:
            out[name] = hit
            continue
        if kept is not None and name in kept.running:
            runs[name] = (*kept.running.pop(name), module)
            continue
        box = {}
        thread = threading.Thread(target=_worker, args=(module, ctx, box), name="kbmon-" + name, daemon=True)
        thread.start()
        runs[name] = (thread, box, module)
    for name, (thread, box, module) in runs.items():
        thread.join(max(0.0, started + timeout - time.monotonic()))
        if thread.is_alive():
            out[name] = {"state": "timeout", "seconds": round(timeout, 3)}
            if kept is not None:
                kept.running[name] = (thread, box)
        else:
            out[name] = {"state": box["state"], "seconds": round(box["seconds"], 3), "data": box["data"]}
            if kept is not None:
                kept.keep(name, module, out[name])
    return {name: out[name] for name in names}


def snapshot(ctx, names, timeout, kept=None):
    """One snapshot: `{"schema": 1, "taken": UTC time, "panels": {...}, "alerts": []}`. `alerts` is what the panels that
    judge their data add (a later item); a non-empty list makes kbmon exit 1. The ops rows are read once for the panels
    that need them (`OpsMemo`); `kept` is the live view's memory (`Kept`)."""
    reads = set(names) & set(OPS_PANELS)
    with ops_memo(kept.ops if kept is not None else OpsMemo()) if reads else contextlib.nullcontext():
        return {"schema": SCHEMA, "taken": now_iso(), "panels": run_panels(ctx, names, timeout, kept), "alerts": []}


def load_snapshot(path, names=None):
    """A snapshot saved by `--json`, narrowed to `names` when given. ValueError when the file is unreadable, is no JSON
    object of schema 1 or has no `panels` object."""
    try:
        snap = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read a snapshot from {path}: {_one_line(e)}") from None
    if not isinstance(snap, dict) or snap.get("schema") != SCHEMA or not isinstance(snap.get("panels"), dict):
        raise ValueError(f"{path} is no kbmon snapshot of schema {SCHEMA}")
    if not isinstance(snap.get("alerts", []), list):
        raise ValueError(f"{path}: alerts is no list")
    snap.setdefault("alerts", [])
    if names:
        snap["panels"] = {n: p for n, p in snap["panels"].items() if n in names}
    return snap
