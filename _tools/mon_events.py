"""kbmon's event and span records (kb/_self/monitoring.md): the coord events, `done.refused` rows and the query log's apply
outcome as events, and each landing (with a child span per `land.step`), `agent.run`, `test.run` and timed delivery as spans,
newer than a cursor. Standard library only; imports `mon_log` (its readers of the coord store and the ops rows) and
`mon_export` (its attribute rules), and `mon_view`, `bl_stall`, `ql_base` and `ql_report` where it reads them.

  collect(ctx, since)    {"schema", "cursor", "events", "spans", "problems"}: the records newer than the cursor `since` (None:
                         the newest ones), and the cursor that holds the newest time of the spool rows and of the delivery
                         and the newest coord sequence read; text, whose form a caller does not read
  render(ctx, since)     that object as JSON text with every string redacted, what `kbmon.py --events` prints

An event is `{name, time, attributes}` (`severity` `warn` on a `done.refused` row and a refused delivery); a span is `{name, id,
trace, parent, start, end, status, attributes}`, times in Unix nanoseconds, `parent` left out of a root, `trace` the id of the
root. Ids are 16 hex characters taken from the ops row's own id, so a record has the same id on every call. A landing is a
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
CURSOR = re.compile(r"1\.(\d+)\.(\d+)\.(\d+)")
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
    """(ops time, coord sequence, delivery time) of a cursor, zeros for none; ValueError for text this tool did not give."""
    if since is None:
        return 0, 0, 0
    found = CURSOR.fullmatch(since.strip())
    if not found:
        raise ValueError(f"--since is not a cursor of --events: {since[:40]!r}")
    return tuple(int(x) for x in found.groups())


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


def coord_records(ctx, after):
    """(events, newest sequence) of the coord events above AFTER, the newest FIRST_EVENTS when AFTER is 0."""
    args = mon_log.coord_args(ctx)
    if args is None:
        return [], after
    events = [e for e in json.loads(mon_log.coord_wait(args))["events"] if mon_export.number(e.get("seq"))]
    events = [e for e in events if e["seq"] > after][-(FIRST_EVENTS if after == 0 else len(events)):]
    out = []
    for e in events:
        at = ns_of_epoch(e.get("at"))
        if at is None:
            continue
        kind = e.get("kind") if isinstance(e.get("kind"), str) else ""
        values = e.get("fields") if isinstance(e.get("fields"), dict) else {}
        out.append({"name": "coord." + (kind if kind and mon_export.stable(kind) else "event"), "time": at,
                    "attributes": attributes({"seq": e["seq"], **values})})
    return out, max([after] + [e["seq"] for e in events])


def landing(end_row, end, steps):
    """The spans of one landing: the root of its `land.end` row and a child of each of its steps."""
    root = span("kb.land", end_row, end)
    start = root["start"] - STEP_SLACK_NS
    kids = [span("kb.land.step", r, t, root["id"], root["id"]) for t, r in steps if t >= start]
    return [root] + kids


def ops_records(ctx, after):
    """(events, spans, newest time) of the ops rows newer than AFTER (the newest FIRST_ROWS rows when AFTER is 0)."""
    import bl_stall
    rows = mon_log.in_spool_order(bl_stall.ops_rows(str(ctx.root)))
    rows = rows[-FIRST_ROWS:] if after == 0 else rows
    events, spans, steps, newest = [], [], {}, after
    for r in rows:
        t = ns_of(r.get("ts"))
        if t is None:
            continue
        newest = max(newest, t)
        event, item = r.get("event"), r.get("item")
        if event == "land.step":
            steps.setdefault(item, []).append((t, r))
        elif event == "land.end":
            mine = steps.pop(item, [])
            if t > after:
                spans += landing(r, t, mine)
        elif t > after and event == "done.refused":
            events.append({"name": "kb.done.refused", "time": t, "severity": "warn",
                           "attributes": attributes(r, NOT_ATTRS)})
        elif t > after and event in ("agent.run", "test.run"):
            spans.append(span("kb." + event, r, t))
    return events, spans, newest


def delivery_records(after):
    """(events, spans, time) of the last apply outcome when the log gives its time and it is newer than AFTER."""
    import ql_base
    import ql_report
    last = ql_report.last_outcomes(ql_base.places()[0])["apply"]
    when = ns_of(last.get("when")) if last and last.get("when") else None
    if when is None or when <= after:
        return [], [], after
    row = {"id": f"delivery-{when}", "outcome": last["outcome"], "ms": 0}
    event = {"name": "kb.delivery.apply", "time": when, "attributes": attributes({"outcome": last["outcome"]})}
    if last["outcome"] in mon_log.DELIVERY_FAILED:
        event["severity"] = "warn"
    return [event], [span("kb.delivery", row, when)], when


def collect(ctx, since=None):
    ops_after, seq_after, delivery_after = parse(since)
    events, spans, problems = [], [], []
    seq, ops_at, delivery_at = seq_after, ops_after, delivery_after
    for name, read in (("coord", lambda: coord_records(ctx, seq_after)),
                       ("ops", lambda: ops_records(ctx, ops_after)),
                       ("delivery", lambda: delivery_records(delivery_after))):
        try:
            got = read()
        except Exception as e:  # noqa: BLE001 - a source that fails is a line of the output, never a failure of the call
            problems.append(f"{name} unavailable: {type(e).__name__}: {' '.join(str(e).split())[:120]}")
            continue
        if name == "coord":
            events, seq = events + got[0], got[1]
        else:
            events, spans = events + got[0], spans + got[1]
            ops_at, delivery_at = (got[2], delivery_at) if name == "ops" else (ops_at, got[2])
    events.sort(key=lambda x: x["time"])
    spans.sort(key=lambda x: (x["start"], x["end"]))
    return {"schema": SCHEMA, "cursor": f"1.{ops_at}.{seq}.{delivery_at}", "events": events, "spans": spans,
            "problems": problems}


def render(ctx, since=None):
    return json.dumps(mon_view.scrub(collect(ctx, since)), ensure_ascii=False, indent=1)
