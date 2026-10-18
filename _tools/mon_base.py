"""kbmon's shared ground (kb/_self/monitoring.md): the panels, a panel's run in a daemon thread under a timeout, the
snapshot and the reading of a saved one. Standard library only; every `mon_` module imports it and it imports no sibling.

  PANELS                 the seven panels, in the order a snapshot lists them
  Ctx                    what a panel reads: the clone `root`, the coord `store`, `url` and `key_file`
  Unsupported            a panel's `collect(ctx)` raises it when this host or this setting cannot give the panel
  panel_module(name)     the module `mon_<name>`, or None while no item has written it (the panel is then `absent`)
  snapshot(ctx, names, timeout)   one dict of schema 1: every named panel run at once, each bounded by `timeout` seconds
  load_snapshot(path)    a saved snapshot, ValueError when it is no snapshot of schema 1

A panel module `mon_<name>.py` has `collect(ctx)`, which returns its data as a dict of JSON values and reads without
writing, and may have `lines(data)`, its text lines for `--once`.
"""
import datetime, importlib, json, threading, time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 1
PANELS = ("kb", "coord", "sessions", "querylog", "host", "sprint", "log")
STATES = ("ok", "timeout", "error", "absent", "unsupported")
ERROR_CHARS = 300  # characters of an exception's text a panel in state error keeps


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


def run_panels(ctx, names, timeout):
    """{name: {state, seconds[, data]}} for `names`. Every panel with a module runs in its own daemon thread, all at
    once, and the caller waits for each until `timeout` seconds after the start: a thread still running then is left
    behind (a daemon thread never holds the process at exit) and its panel is `timeout`."""
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
        box = {}
        thread = threading.Thread(target=_worker, args=(module, ctx, box), name="kbmon-" + name, daemon=True)
        thread.start()
        runs[name] = (thread, box)
    for name, (thread, box) in runs.items():
        thread.join(max(0.0, started + timeout - time.monotonic()))
        if thread.is_alive():
            out[name] = {"state": "timeout", "seconds": round(timeout, 3)}
        else:
            out[name] = {"state": box["state"], "seconds": round(box["seconds"], 3), "data": box["data"]}
    return {name: out[name] for name in names}


def snapshot(ctx, names, timeout):
    """One snapshot: `{"schema": 1, "taken": UTC time, "panels": {...}, "alerts": []}`. `alerts` is what the panels that
    judge their data add (a later item); a non-empty list makes kbmon exit 1."""
    return {"schema": SCHEMA, "taken": now_iso(), "panels": run_panels(ctx, names, timeout), "alerts": []}


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
