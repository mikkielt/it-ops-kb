"""The query log's export (kb/_self/querylog.md, Reporting): the store's entries, findings, usage, work and ops rows
printed as JSON Lines, one record in the OTLP-JSON field names of an OpenTelemetry log record, for a tool that reads logs.

  {"timeUnixNano", "severityNumber", "severityText", "eventName", "body": {}, "attributes": [{"key", "value"}],
   "resource": {"attributes": [{"key": "service.name", ...}, {"key": "kb.run", ...}]}}

Read-only: no file of the store is written, no model, no git and no network. Redaction happens at read time, row by
row, with the store's own gates: a key the row's format does not have is dropped, the row's values are checked in their
closed shapes (entry_problems, record_problems, usage_line_problems, work_line_problems, ops_line_problems, which for
an ops row is ql_capture.ops_problems), and the leak scan (redact.scan) runs over every value. A row that fails a shape
check or the scan, or that cannot be read, is left out and counted on stderr by its file and line, never by a value.
The question of an entry is left out unless asked for. The order is the records' time, event and id.
"""
import calendar, datetime, json, sys
from pathlib import Path

import ql_store
from ql_base import STORE
from ql_capture import OPS_EVENTS

FORMATS = ("jsonl",)
SERVICE = "it-ops-kb"
SEVERITY = {"INFO": 9, "WARN": 13}  # OpenTelemetry's severity numbers
NOT_SCANNED = ("id", "entry", "run", "kb_commit")  # identifiers that name runs, entries and findings
WORK_KEYS = ql_store.WORK_ITEM_KEYS + ql_store.WORK_SHARED_KEYS + ql_store.WORK_OVERHEAD_KEYS


def event_name(family, kind=None):
    """The flat event name of a row: its family and its surface, kind or ops event joined by underscores, no dot."""
    return family if kind is None else f"{family}_{kind}".replace(".", "_")


EVENTS = tuple(event_name(f, k) for f, ks in (
    ("entry", ql_store.SURFACES), ("finding", ql_store.FINDING_KINDS), ("usage", (None,)),
    ("work", ("item", "shared", "overhead")), ("ops", tuple(OPS_EVENTS))) for k in ks)


def run_time(run):
    """The UTC time a run id (`yyyymmddThhmmssZ-xxxxxxxx`) names, as `yyyy-mm-ddThh:mm:ssZ`."""
    s = str(run)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}Z"


def lines_of(path):
    """[(line number, object or None)] of a store file after its header; None is a line that is no JSON object."""
    out = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return [(0, None)]
    first = True
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            obj = None
        if first:
            first = False
            continue
        out.append((n, obj if isinstance(obj, dict) else None))
    return out


def strings(x):
    """The strings of a JSON value, nested ones included."""
    if isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)
    elif isinstance(x, str):
        yield x


def leaks(attributes, k):
    """True when the leak scan flags any value of `attributes` but the identifiers of NOT_SCANNED."""
    import redact
    return any(redact.scan(v, k) for v in strings({a: b for a, b in attributes.items() if a not in NOT_SCANNED}))


def severity(family, kind, attributes):
    """WARN for a row that records a failure (a refused done, a nonzero exit, an apply that failed), else INFO."""
    if kind == "done.refused" or attributes.get("state") == ql_store.APPLY_FAILED:
        return "WARN"
    code = attributes.get("exit")
    return "WARN" if family == "ops" and type(code) is int and code != 0 else "INFO"


def nanos(iso):
    """The decimal string of the nanoseconds since the epoch of `yyyy-mm-ddThh:mm:ss[.fff]Z` (OTLP-JSON's int64)."""
    whole, _, frac = iso.rstrip("Z").partition(".")
    t = datetime.datetime.strptime(whole, "%Y-%m-%dT%H:%M:%S")
    return str(calendar.timegm(t.timetuple()) * 10**9 + int((frac + "000000000")[:9]))


def any_value(v):
    """`v` as an OTLP AnyValue: bool, int (a decimal string, as OTLP-JSON writes an int64), float, string, array, map;
    null is the empty AnyValue."""
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, str):
        return {"stringValue": v}
    if isinstance(v, (list, tuple)):
        return {"arrayValue": {"values": [any_value(x) for x in v]}}
    if isinstance(v, dict):
        return {"kvlistValue": {"values": key_values(v)}}
    return {}


def key_values(d):
    return [{"key": str(k), "value": any_value(v)} for k, v in d.items()]


def record(timestamp, family, kind, rid, run, attributes):
    """(the ISO time, the event name, the record id, the OTLP-JSON record). The family and the original surface, kind
    or ops event stay as attributes `kb.record` and `kb.type`, the id as `kb.id`."""
    sev = severity(family, kind, attributes)
    name = event_name(family, kind)
    own = {"kb.record": family, **({"kb.type": kind} if kind else {}), "kb.id": rid}
    return (timestamp, name, rid, {
        "timeUnixNano": nanos(timestamp), "severityNumber": SEVERITY[sev], "severityText": sev, "eventName": name,
        "body": {}, "attributes": key_values({**own, **attributes}),
        "resource": {"attributes": key_values({"service.name": SERVICE, "kb.run": run})}})


def keep(obj, keys):
    """`obj` with the keys the format has, in the format's order: an unknown key is dropped here."""
    return {key: obj[key] for key in keys if key in obj}


def rows(store, with_question, k):
    """(records, refused) of the store: each readable row that passes its gates as a record, in file order; `refused`
    is [(where, why)] for the rows left out, `why` `shape`, `leak scan` or `unreadable`."""
    store = Path(store)
    out, refused = [], []

    def add(where, make):
        try:
            made = make()
        except Exception:  # noqa: BLE001 a row no gate can read is left out, never a crash
            refused.append((where, "unreadable"))
            return
        if made is None:
            refused.append((where, "shape"))
        elif made == "leak":
            refused.append((where, "leak scan"))
        else:
            out.append(made)

    def checked(problems, attributes, make):
        if problems:
            return None
        return "leak" if leaks(attributes, k) else make()

    entry_ids, seen = set(), set()
    for p in ql_store.run_files(store):
        for n, e in lines_of(p):
            where = f"{p.relative_to(store).as_posix()}:{n}"
            if e is None:
                refused.append((where, "unreadable"))
                continue
            if isinstance(e.get("id"), str):
                entry_ids.add(e["id"])
                if e["id"] in seen:
                    continue
                seen.add(e["id"])
            kept = keep(e, ql_store.ENTRY_KEYS)
            if not with_question:
                kept.pop("question", None)
            attrs = {a: b for a, b in kept.items() if a != "id"}
            add(where, lambda: checked(ql_store.entry_problems(kept, where, k), attrs, lambda: record(
                f"{kept['day']}T00:00:00Z", "entry", kept["surface"], kept["id"], p.stem, attrs)))
    for p in ql_store.findings_files(store):
        for n, r in lines_of(p):
            where = f"{p.relative_to(store).as_posix()}:{n}"
            if r is None:
                refused.append((where, "unreadable"))
                continue
            kept = keep(r, ql_store.FINDING_KEYS)
            attrs = {a: b for a, b in kept.items() if a != "id"}
            add(where, lambda: checked(ql_store.record_problems(kept, where, entry_ids, k), attrs, lambda: record(
                run_time(p.stem), "finding", kept["kind"], f"{kept['id']}/{p.stem}", p.stem, attrs)))
    for p in ql_store.usage_files(store):
        for n, u in lines_of(p):
            where = f"{p.relative_to(store).as_posix()}:{n}"
            if u is None:
                refused.append((where, "unreadable"))
                continue
            kept = keep(u, ql_store.USAGE_KEYS)
            attrs = {"entry": kept.get("id"), **{a: b for a, b in kept.items() if a != "id"}}
            add(where, lambda: checked(ql_store.usage_line_problems(kept, where), attrs, lambda: record(
                run_time(p.stem), "usage", None, kept["id"], p.stem, attrs)))
    for p in ql_store.work_files(store):
        for n, w in lines_of(p):
            where = f"{p.relative_to(store).as_posix()}:{n}"
            if w is None:
                refused.append((where, "unreadable"))
                continue
            kept = keep(w, WORK_KEYS)
            kind = "item" if "item" in kept else "overhead" if "overhead" in kept else "shared"
            add(where, lambda: checked(ql_store.work_line_problems(kept, where), kept, lambda: record(
                run_time(p.stem), "work", kind, f"{p.stem}:{n}", p.stem, kept)))
    for p in ql_store.ops_files(store):
        for n, o in lines_of(p):
            where = f"{p.relative_to(store).as_posix()}:{n}"
            if o is None:
                refused.append((where, "unreadable"))
                continue
            spec = OPS_EVENTS.get(o.get("event")) if isinstance(o.get("event"), str) else None
            kept = keep(o, ql_store.OPS_LINE_KEYS + tuple(spec or ()))
            attrs = {a: b for a, b in kept.items() if a not in ql_store.OPS_LINE_KEYS}
            add(where, lambda: checked(ql_store.ops_line_problems(kept, where), attrs, lambda: record(
                kept["ts"], "ops", kept["event"], kept["id"], p.stem, attrs)))
    return out, refused


def export(store=None, fmt="jsonl", since=None, event=None, with_question=False, out=print, err=None):
    """`export --format jsonl [--since DAY] [--event E] [--with-question] [--store DIR]`: the records of the store
    (default kb/_querylog), `out` one JSON line each in the order of time, event name and record id. 0, also for an
    empty answer and when rows were left out (counted on `err`); 2 refused: a format other than jsonl, a `--since` that
    is no day, an `--event` outside EVENTS, a store that is no directory."""
    err = err or (lambda s: print(s, file=sys.stderr))
    store = Path(store) if store else STORE
    if fmt not in FORMATS:
        err(f"export: refused: --format is one of {', '.join(FORMATS)}")
        return 2
    if since is not None:
        try:
            datetime.date.fromisoformat(since)
        except ValueError:
            err("export: refused: --since is a day, YYYY-MM-DD")
            return 2
    if event is not None and event not in EVENTS:
        err(f"export: refused: --event is one of {', '.join(EVENTS)}")
        return 2
    if not store.is_dir():
        err("export: refused: the store is not a directory")
        return 2
    import redact
    records, refused = rows(store, with_question, redact.known())
    records = [r for r in records if (since is None or r[0][:10] >= since) and (event is None or r[1] == event)]
    for r in sorted(records, key=lambda r: r[:3]):
        out(json.dumps(r[3], separators=(",", ":")))
    if refused:
        err(f"export: left out {len(refused)} row(s) that fail a gate of the store or the leak scan")
        for where, why in sorted(refused)[:20]:
            err(f"  {where}: {why}")
    return 0
