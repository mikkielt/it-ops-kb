"""kbmon's log panel (kb/_self/monitoring.md): the newest coord events, ops rows and query-log delivery outcomes in one list,
oldest first, each as time, source, event, subject and the fields whose values are ids or numbers.

The sources are `coord.py wait --since 0 --timeout 0` on the local store or `--url` server (as the coord panel connects; a
store that is not there gives no coord row), the ops rows `bl_stall.ops_rows` reads (this host's spool and the committed
sidecars: `land.step`, `land.end`, `done.refused` and `test.run` only) and the query log's last apply outcome
(`ql_report.last_outcomes`). A source that cannot be read adds a `problems` entry and the others still show. A field is kept
only when its value is a number or an id-shaped word (a list of them joined by `,`) that `redact.redact` leaves as it is, so
no free text of an event reaches the view; the subject too, else `-`. A row with `warn` (a `done.refused` row, a refused or
failed delivery) takes the `! ` gutter. The panel writes nothing. Imports `mon_view` (`LazyKnown`) and, where it reads
them, `coord`, `bl_stall`, `ql_capture`, `ql_distill`, `ql_base` and `ql_report`; no other panel module.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import mon_view

REFRESH_S = 10  # seconds the live view serves the last result: the spool is read whole to put rows in order
COORD = Path(__file__).resolve().with_name("coord.py")
CHILD_SECONDS = 30  # the longest `coord.py wait` may take; the panel's own bound is kbmon's --timeout
LOG_KEPT = 100  # newest rows in the data
SOURCE_WIDTH = 8  # columns of the source in a row
OPS_SHOWN = ("land.step", "land.end", "done.refused", "test.run")  # the ops events the log lists
DELIVERY_FAILED = ("refused", "fetch-failed")  # the apply outcomes that take the warning gutter
WARN_EVENTS = ("done.refused",)
MAX_FIELDS = 8
VALUE_CHARS = 60
NO_TIME = "--:--:--"
ID = re.compile(r"[A-Za-z0-9][\w./:@-]*")
SUBJECTS = ("key", "item", "topic", "touch", "path", "fact", "session")  # a coord event's subject, the first present
WHOS = ("holder", "operator", "session")  # the coord fields shown first
OPS_SUBJECTS = ("item", "sprint", "mode")
NOT_FIELDS = ("id", "ts", "surface", "v", "event")


def iso_of(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"


def scalar(value):
    """The text of a number, an id-shaped word or a list of them; None for anything else (free text, a flag, a table)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value if len(value) <= VALUE_CHARS and ID.fullmatch(value) else None
    if isinstance(value, list) and value and not any(isinstance(x, (list, dict)) for x in value):
        parts = [scalar(x) for x in value]
        return ",".join(parts) if None not in parts else None
    return None


class Clean:
    """What `redact.redact` leaves as it is: the text of a value kept in the data, else None."""

    def __init__(self):
        self.known = mon_view.LazyKnown()

    def __call__(self, value):
        text = scalar(value)
        if text is None:
            return None
        import redact
        return text if redact.redact(text, self.known) == text else None


def fields_of(values, skip, order, clean):
    """{key: text} of the values that pass `clean`, `order` first (then sorted), without the keys of `skip`."""
    keys = [k for k in order if k in values] + sorted(k for k in values if k not in order)
    out = {}
    for k in keys:
        text = None if k in skip or not isinstance(k, str) or not ID.fullmatch(k) else clean(values[k])
        if text is not None and len(out) < MAX_FIELDS:
            out[k] = text
    return out


def row(ts, source, event, subject, fields, warn=False):
    return {"ts": ts, "source": source, "event": event, "subject": subject, "fields": fields, "warn": warn}


def coord_args(ctx):
    """coord.py's connection arguments for the url or the local store (`--store`, else `KB_COORD_STORE`, else the clone's
    default); None when no store file is there."""
    if ctx.url:
        if not ctx.key_file:
            raise RuntimeError("--url needs --key-file")
        return ["--url", ctx.url, "--key-file", ctx.key_file]
    store = ctx.store or os.environ.get("KB_COORD_STORE")
    if not store:
        import coord
        store = coord.default_store()
    store = str(Path(store).expanduser()) if store else None
    return ["--store", store] if store and Path(store).is_file() else None


def coord_wait(args):
    """The output of `coord.py wait --since 0 --timeout 0`; RuntimeError when it fails or takes over CHILD_SECONDS."""
    try:
        p = subprocess.run([sys.executable, str(COORD), *args, "wait", "--since", "0", "--timeout", "0"], capture_output=True,
                           text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=CHILD_SECONDS)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"coord.py gave no answer in {CHILD_SECONDS} seconds") from None
    if p.returncode != 0:
        lines = [x.strip() for x in p.stderr.splitlines() if x.strip()]
        raise RuntimeError("coord.py: " + (lines[-1].removeprefix("coord.py: ") if lines else f"exit {p.returncode}")[:120])
    return p.stdout


def coord_events(ctx, clean):
    """The coord store's events as rows (oldest first), [] when there is no local store."""
    args = coord_args(ctx)
    if args is None:
        return []
    rows = []
    for e in json.loads(coord_wait(args))["events"][-LOG_KEPT:]:
        values = e.get("fields") if isinstance(e.get("fields"), dict) else {}
        key = next((k for k in SUBJECTS if clean(values.get(k)) is not None), None)
        subject = clean(values[key]) if key else None
        kind = clean(e.get("kind"))
        rows.append(row(iso_of(e["at"]), "coord", kind or "-", subject or "-", fields_of(values, (key,), WHOS, clean)))
    return rows


def in_spool_order(rows):
    """ROWS (`bl_stall.ops_rows`, sorted by time and id) with the rows of this host's spool that share a millisecond put
    back in the order the spool file holds them; the committed rows stay first and in their order."""
    import ql_capture
    import ql_distill
    spool = ql_capture.spool_dir()
    at = {}
    for f in sorted(Path(spool).glob("tools-*.jsonl")) if spool is not None and Path(spool).is_dir() else []:
        for r in ql_distill.spool_rows(f)[0]:
            at.setdefault(r.get("id"), len(at))
    return sorted(rows, key=lambda r: (str(r.get("ts")), at.get(r.get("id"), -1)))


def ops_events(ctx, clean):
    """The ops rows of OPS_SHOWN as rows (oldest first, a millisecond shared by rows in the spool's order)."""
    import bl_stall
    import ql_capture
    rows = []
    for r in in_spool_order(bl_stall.ops_rows(str(ctx.root)))[-LOG_KEPT * 4:]:
        event = r.get("event")
        if event not in OPS_SHOWN:
            continue
        skip = tuple(k for k in OPS_SUBJECTS if k in r)[:1]
        spec = ql_capture.OPS_EVENTS.get(event, {})
        subject = clean(r[skip[0]]) if skip else None
        rows.append(row(str(r.get("ts")), "ops", event, subject or "-",
                        fields_of({k: v for k, v in r.items() if k not in NOT_FIELDS}, skip, tuple(spec), clean),
                        event in WARN_EVENTS))
    return rows[-LOG_KEPT:]


def delivery_event():
    """The last apply outcome of the query log as a row, or None; its time is the log's last write, set only on the outcome
    that stands last in the log (`ql_report.last_outcomes`), else unknown."""
    import ql_base
    import ql_report
    last = ql_report.last_outcomes(ql_base.places()[0])["apply"]
    if not last:
        return None
    when = last.get("when")
    return row(str(when) if when else "", "delivery", "apply", last["outcome"], {}, last["outcome"] in DELIVERY_FAILED)


def collect(ctx):
    clean, rows, problems = Clean(), [], []
    for name, read in (("coord", lambda: coord_events(ctx, clean)), ("ops", lambda: ops_events(ctx, clean)),
                       ("delivery", lambda: [x for x in [delivery_event()] if x])):
        try:
            rows += read()
        except Exception as e:  # noqa: BLE001 - a source that fails is a line of the log, never a failure of the panel
            problems.append(f"{name} unavailable: {type(e).__name__}: {' '.join(str(e).split())[:120]}")
    rows.sort(key=lambda r: r["ts"])  # stable: the sources keep their own order within a time; an unknown time first
    return {"events": rows[-LOG_KEPT:], "problems": problems}


def clock(ts):
    """`HH:MM:SS` (UTC) of an ISO time, or NO_TIME."""
    return ts[11:19] if isinstance(ts, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*", ts) else NO_TIME


def event_line(e):
    text = f"{clock(e['ts'])} {str(e['source'])[:SOURCE_WIDTH].ljust(SOURCE_WIDTH)} {e['event']} {e['subject']}"
    text += "".join(f" {k}={v}" for k, v in (e.get("fields") or {}).items())
    return ("! " if e.get("warn") else "") + text


def lines(data):
    """The body rows: a problem of a source (`! `), then the events oldest first, one each; `no events` when none."""
    rows = [f"! {p}" for p in data.get("problems", [])]
    rows += [event_line(e) for e in data.get("events", [])]
    return rows or ["no events"]
