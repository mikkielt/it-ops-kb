"""kbmon's event and span records (kb/_self/monitoring.md): the coord events, `done.refused` rows and the query log's apply
outcome as events, and each landing (with a child span per `land.step`), `agent.run`, `test.run`, timed delivery and each
finished run of an item (a `kb.item` span with `kb.worker` and `kb.landing` children, from its progress events) as spans,
and each sprint whose items have all ended their runs (a `kb.sprint` root over its `kb.item` spans),
newer than a cursor. Standard library only; imports `mon_log` (its readers of the coord store and the ops rows) and
`mon_export` (its attribute rules), and `mon_view`, `mon_sprint` (the sprint of a run's item), `bl_stall`, `ql_base` and
`ql_report` where it reads them.

  collect(ctx, since)    {"schema", "cursor", "events", "spans", "problems"}: the records newer than the cursor `since` (None:
                         the newest ones), and the cursor that holds the newest time of the spool rows with the keys of the
                         rows of that millisecond, the time of the delivery and the newest coord sequence read; text, whose
                         form a caller does not read
  render(ctx, since)     that object as JSON text with every string redacted, what `kbmon.py --events` prints
  worker_ids(events, item, sprint=None)  (trace, span id) of the `kb.worker` span of the item's run that is working now, from the coord
                         progress events; what `backlog.py dispatch` hands the worker as its TRACEPARENT

An event is `{name, time, attributes}` (`severity` `warn` on a `done.refused` row and a refused delivery); a span is `{name, id,
trace, parent, start, end, status, attributes}` (`status` `error` on a row with an `exit` and on a refused delivery), times in
Unix nanoseconds, `parent` left out of a root, `trace` the id of the root (32 hex characters for a run of an item or a sprint, so a worker's TRACEPARENT carries it). Ids are 16 hex characters taken from the ops row's own id, so a record has the same id on every call. A landing is a
span only once its `land.end` row is in the log, and then with the steps of its item the rows hold; a step with no `land.end`
is never exported. An attribute is kept only when it is a number, a flag or an identifier `redact.redact` leaves as it is (a
list of them as `name_n` and `name_1`..), never a `holder`; the other attributes of a record are left out, the record stays.
Nothing is written; a source that cannot be read adds a `problems` line and keeps its part of the cursor.
"""
import datetime
import hashlib
import json
import re

import mon_export
import mon_log
import mon_view

SCHEMA = 1
CURSOR = re.compile(r"1\.(\d+)\.(\d+)\.(\d+)(?:\.([0-9a-f]{8}(?:-[0-9a-f]{8})*))?")
FIRST_ROWS = 4000  # ops rows read when there is no cursor
FIRST_EVENTS = 1000  # coord events read when there is no cursor
LIST_KEPT = 4  # items of a list attribute that are kept
MAX_ATTRS = 16
STEP_SLACK_NS = 1_000_000_000  # a step this much older than its landing's start is another landing's
NOT_ATTRS = ("id", "ts", "surface", "v", "event")
EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def ns_of(ts):
    """Unix nanoseconds of a spool row's UTC time (`2026-10-18T10:00:00.123Z`), None when it is no time."""
    try:
        d = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00")) - EPOCH
    except ValueError:
        return None
    return (d.days * 86400 + d.seconds) * 10**9 + d.microseconds * 1000


def ns_of_epoch(seconds):
    return int(round(seconds * 1e6)) * 1000 if mon_export.number(seconds) else None


def span_id(row_id):
    """16 hex characters of an ops row's id: the same on every call, never the row id itself."""
    return hashlib.sha256(str(row_id).encode("utf-8")).hexdigest()[:16]


def one(value):
    """The value when it is a number, a flag or a stable identifier, else None."""
    if isinstance(value, bool) or mon_export.number(value):
        return value
    return value if isinstance(value, str) and mon_export.stable(value) else None


def attributes(values, skip=()):
    """{name: value} of the entries of VALUES an attribute may be, `skip` and the forbidden names left out."""
    out = {}
    for name, value in values.items():
        if (name in skip or name in mon_export.FORBIDDEN or not isinstance(name, str)
                or not mon_export.ID_VALUE.fullmatch(name)):
            continue
        if isinstance(value, list):
            kept = [one(x) for x in value[:LIST_KEPT]]
            if value and None not in kept and not any(isinstance(x, bool) for x in kept):
                out[f"{name}_n"] = len(value)
                out.update({f"{name}_{i}": x for i, x in enumerate(kept, 1)})
        elif one(value) is not None:
            out[name] = value
    return dict(list(out.items())[:MAX_ATTRS])


def parse(since):
    """(ops time, coord sequence, delivery time, keys of the ops rows of the ops time already read) of a cursor, zeros and
    no keys for none; ValueError for text this tool did not give."""
    if since is None:
        return 0, 0, 0, frozenset()
    found = CURSOR.fullmatch(since.strip())
    if not found:
        raise ValueError(f"--since is not a cursor of --events: {since[:40]!r}")
    ops, seq, delivery, keys = found.groups()
    return int(ops), int(seq), int(delivery), frozenset((keys or "").split("-")) - {""}


def row_key(row):
    """8 hex characters that tell an ops row from the others of its millisecond: of its id, else of its whole content."""
    return span_id(row.get("id") or json.dumps(row, sort_keys=True, default=str))[:8]


def id_list(values):
    """VALUES with each string of comma-separated parts (a coord `item`, `topic` or `touch` list) as the list of its parts."""
    return {k: [x.strip() for x in v.split(",")] if isinstance(v, str) and "," in v else v for k, v in values.items()}


def status(row):
    return "error" if mon_export.number(row.get("exit")) and row["exit"] != 0 else "ok"


def span(name, row, end, trace=None, parent=None):
    ms = row.get("ms") if mon_export.number(row.get("ms")) else 0
    out = {"name": name, "id": span_id(row["id"]), "trace": trace or span_id(row["id"])}
    if parent:
        out["parent"] = parent
    out.update({"start": end - int(ms * 1e6), "end": end, "status": status(row),
                "attributes": attributes(row, NOT_ATTRS)})
    return out


def sprint_of(ctx, items):
    """{item id: its sprint's id} of ITEMS, from the backlog `mon_sprint.backlog_at` reads; {} where it cannot be read."""
    import mon_sprint
    try:
        bl = mon_sprint.backlog_at(ctx.root)[0]
    except Exception:  # noqa: BLE001 - no backlog: the spans keep no sprint attribute
        return {}
    return {i: bl.items[i]["sprint"] for i in items if isinstance(bl.items.get(i), dict) and bl.items[i].get("sprint")}


def run_span(name, first, last, end, trace, parent, extra):
    """A span of the progress events FIRST to LAST: its id the hash of FIRST's sequence and NAME, `error` when LAST is
    `failed` or `refused`; END the sequence its export waits for."""
    out = {"name": name, "id": span_id(f"{name}-{first['seq']}"), "trace": trace, "start": first["ns"], "end": last["ns"],
           "status": "error" if last["state"] in ("failed", "refused") else "ok",
           "attributes": attributes({**extra, "state": last["state"], "exit": last["fields"].get("exit"),
                                     **id_list({"gates": last["fields"].get("gates")})})}
    if parent:
        out["parent"] = parent
    return out, end


def trace_id(first, sprint=None):
    """32 hex characters, the trace of the run whose first progress move is FIRST (W3C Trace Context's width, so a worker's
    TRACEPARENT can carry it); that of the `kb.sprint` span of SPRINT, derived from its id, when the item has one."""
    seed = f"kb.sprint-trace-{sprint}" if sprint else f"kb.item-{first['seq']}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def sprint_span_id(sprint):
    return span_id(f"kb.sprint-{sprint}")


def item_runs(events):
    """[(item id, moves)] of the progress EVENTS (every coord event, oldest first), a move being `{seq, ns, state, fields}`.
    A run of an item is cut where it ends (`landed`, `refused`, `released`; one that follows `refused` starts at its next
    move)."""
    moves = {}
    for e in events:
        fields = e.get("fields") if isinstance(e.get("fields"), dict) else {}
        at = ns_of_epoch(e.get("at"))
        if e.get("kind") == "progress" and at is not None and isinstance(fields.get("item"), str) \
                and isinstance(fields.get("state"), str):
            moves.setdefault(fields["item"], []).append({"seq": e["seq"], "ns": at, "state": fields["state"], "fields": fields})
    runs = []
    for item, rows in moves.items():
        run = []
        for m in rows:
            run.append(m)
            if m["state"] in ("landed", "refused", "released"):
                runs.append((item, run))
                run = []
        if run:
            runs.append((item, run))
    return runs


def worker_ids(events, item, sprint=None):
    """(trace, span) ids, as `--events` gives them, of the `kb.worker` span of ITEM's run that is working now: its newest
    `working` move when it is the run's last move; None when the item has no run or its run is not working. The trace is
    the `kb.sprint` span's when ITEM has a SPRINT."""
    runs = [run for name, run in item_runs(events) if name == item]
    if not runs or runs[-1][-1]["state"] != "working":
        return None
    return trace_id(runs[-1][0], sprint), span_id(f"kb.worker-{runs[-1][-1]['seq']}")


def sprint_records(runs, sprints):
    """[(`kb.sprint` span, sequence of its last move)] of the sprints whose items with a run have all ended it: for each
    sprint of SPRINTS ({item: sprint}) the RUNS ((item, moves) as `item_runs` gives them) of its items, once the last move of
    every item is `landed` or `released`. The span runs from the first move of the first run to the last move of the last,
    its id and trace derived from the sprint id."""
    by = {}
    for item, run in runs:
        if sprints.get(item):
            by.setdefault(sprints[item], {}).setdefault(item, []).append(run)
    out = []
    for sprint, items in by.items():
        if any(rs[-1][-1]["state"] not in ("landed", "released") for rs in items.values()):
            continue
        every = [run for rs in items.values() for run in rs]
        out.append(({"name": "kb.sprint", "id": sprint_span_id(sprint), "trace": trace_id(None, sprint),
                     "start": min(r[0]["ns"] for r in every), "end": max(r[-1]["ns"] for r in every), "status": "ok",
                     "attributes": attributes({"sprint": sprint, "items": len(every)})},
                    max(r[-1]["seq"] for r in every)))
    return out


def run_records(ctx, events, after):
    """The spans of the runs the progress EVENTS (every coord event, oldest first) hold, those finished above sequence AFTER.
    A run of an item (`item_runs`) becomes a `kb.item` span from its first move to its last, a `kb.worker` child for each
    `working` to `returned`, `failed` or `blocked` stretch and a `kb.landing` child for each `landing` to `landed` or
    `refused`. An item with a sprint takes the sprint's trace and the `kb.sprint` span (`sprint_records`) as the parent of
    its `kb.item` span."""
    runs = item_runs(events)
    sprints = sprint_of(ctx, {item for item, run in runs})
    done = sprint_records(runs, sprints)
    for item, run in runs:
        first = run[0]
        trace, root = trace_id(first, sprints.get(item)), span_id(f"kb.item-{first['seq']}")
        extra = {"item": item, "sprint": sprints.get(item)}
        mark = None
        for m in run:
            if m["state"] == "working":
                mark = m
            elif mark and m["state"] in ("returned", "failed", "blocked"):
                done.append(run_span("kb.worker", mark, m, m["seq"], trace, root, extra))
                mark = None
            elif m["state"] == "landing":
                mark = m
            elif mark and m["state"] in ("landed", "refused") and mark["state"] == "landing":
                done.append(run_span("kb.landing", mark, m, m["seq"], trace, root, extra))
                mark = None
        if run[-1]["state"] in ("landed", "refused", "released"):
            done.append(run_span("kb.item", first, run[-1], run[-1]["seq"], trace,
                                 sprint_span_id(sprints[item]) if sprints.get(item) else None, extra))
    return [s for s, seq in done if seq > after]


def coord_records(ctx, after):
    """(events, newest sequence, spans) of the coord events above AFTER, the newest FIRST_EVENTS when AFTER is 0, and the run
    spans finished above it."""
    args = mon_log.coord_args(ctx)
    if args is None:
        return [], after, []
    events = [e for e in json.loads(mon_log.coord_wait(args))["events"] if mon_export.number(e.get("seq"))]
    spans = run_records(ctx, events, after)
    events = [e for e in events if e["seq"] > after][-(FIRST_EVENTS if after == 0 else len(events)):]
    out = []
    for e in events:
        at = ns_of_epoch(e.get("at"))
        if at is None:
            continue
        kind = e.get("kind") if isinstance(e.get("kind"), str) else ""
        values = e.get("fields") if isinstance(e.get("fields"), dict) else {}
        out.append({"name": "coord." + (kind if kind and mon_export.stable(kind) else "event"), "time": at,
                    "attributes": attributes({"seq": e["seq"], **id_list(values)})})
    return out, max([after] + [e["seq"] for e in events]), spans


def landing(end_row, end, steps):
    """The spans of one landing: the root of its `land.end` row and a child of each of its steps."""
    root = span("kb.land", end_row, end)
    start = root["start"] - STEP_SLACK_NS
    kids = [span("kb.land.step", r, t, root["id"], root["id"]) for t, r in steps if t >= start]
    return [root] + kids


def ops_records(ctx, after, seen=frozenset()):
    """(events, spans, newest time, keys of the rows of that time) of the ops rows newer than AFTER, and those of AFTER's
    millisecond whose key SEEN lacks (the newest FIRST_ROWS rows when AFTER is 0)."""
    import bl_stall
    rows = mon_log.in_spool_order(bl_stall.ops_rows(str(ctx.root)), ctx.root)
    rows = rows[-FIRST_ROWS:] if after == 0 else rows
    events, spans, steps, newest, keys = [], [], {}, after, set(seen)
    for r in rows:
        t = ns_of(r.get("ts"))
        if t is None:
            continue
        if t > newest:
            newest, keys = t, set()
        if t == newest:
            keys.add(row_key(r))
        new = t > after or (t == after and row_key(r) not in seen)
        event, item = r.get("event"), r.get("item")
        if event == "land.step":
            steps.setdefault(item, []).append((t, r))
        elif event == "land.end":
            mine = steps.pop(item, [])
            if new:
                spans += landing(r, t, mine)
        elif new and event == "done.refused":
            events.append({"name": "kb.done.refused", "time": t, "severity": "warn",
                           "attributes": attributes(r, NOT_ATTRS)})
        elif new and event in ("agent.run", "test.run"):
            spans.append(span("kb." + event, r, t))
    return events, spans, newest, frozenset(keys)


def delivery_records(after):
    """(events, spans, time) of the apply outcome that stands last in the log (only its run's spool-rows line may follow
    it), newer than AFTER. Any other line written after it leaves the log's last write (the outcome's time) moved and the
    outcome no longer standing last: it is exported once."""
    import ql_base
    import ql_report
    last = ql_report.last_outcomes(ql_base.places()[0])["apply"]
    when = ns_of(last.get("when")) if last and last.get("when") and last.get("standing") else None
    if when is None or when <= after:
        return [], [], after
    failed = last["outcome"] in mon_log.DELIVERY_FAILED
    event = {"name": "kb.delivery.apply", "time": when, "attributes": attributes({"outcome": last["outcome"]})}
    out = span("kb.delivery", {"id": f"delivery-{when}", "outcome": last["outcome"]}, when)
    if failed:
        event["severity"], out["status"] = "warn", "error"
    return [event], [out], when


def collect(ctx, since=None):
    ops_after, seq_after, delivery_after, ops_seen = parse(since)
    events, spans, problems = [], [], []
    seq, ops_at, delivery_at, ops_keys = seq_after, ops_after, delivery_after, ops_seen
    for name, read in (("coord", lambda: coord_records(ctx, seq_after)),
                       ("ops", lambda: ops_records(ctx, ops_after, ops_seen)),
                       ("delivery", lambda: delivery_records(delivery_after))):
        try:
            got = read()
        except Exception as e:  # noqa: BLE001 - a source that fails is a line of the output, never a failure of the call
            problems.append(f"{name} unavailable: {type(e).__name__}: {' '.join(str(e).split())[:120]}")
            continue
        if name == "coord":
            events, seq, spans = events + got[0], got[1], spans + got[2]
        else:
            events, spans = events + got[0], spans + got[1]
            ops_at, delivery_at = (got[2], delivery_at) if name == "ops" else (ops_at, got[2])
            if name == "ops":
                ops_keys = got[3]
    events.sort(key=lambda x: x["time"])
    spans.sort(key=lambda x: (x["start"], x["end"]))
    keys = "." + "-".join(sorted(ops_keys)) if ops_keys else ""
    return {"schema": SCHEMA, "cursor": f"1.{ops_at}.{seq}.{delivery_at}{keys}", "events": events, "spans": spans,
            "problems": problems}


def render(ctx, since=None):
    got = collect(ctx, since)
    out = mon_view.scrub(got)
    for kept, span in zip(out["spans"], got["spans"]):  # redact reads 32 bare hex characters as a GUID; a trace is our hash
        kept["trace"] = span["trace"]
    return json.dumps(out, ensure_ascii=False, indent=1)
