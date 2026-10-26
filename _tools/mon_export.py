"""kbmon's metric points (kb/_self/monitoring.md): a snapshot as a flat list of points, each with a name, a unit, a kind
(`gauge` or `sum`), a number and attributes. Standard library only; imports `mon_base` and, at the first attribute check,
`mon_view` and `redact`.

  points(snap)           the points of a snapshot, in panel order: every panel's state and seconds, then what the panel's
                         exporter takes from its data; a panel whose data an exporter cannot read gives no point
  render(snap)           `{"schema", "taken", "points"}` as JSON text, what `kbmon.py --metrics` prints

The names are `kbmon.<panel>.<measure>`. An attribute value is a number, a flag or an identifier (letters, digits and
`_ . : / # @ -`, 120 characters at most) that `redact.redact` leaves as it is; a point with any other attribute value is
left out whole, so the export never carries free text, a path or a host name. An attribute named `holder` is never set:
claims are counted by state, and a claim's key is an attribute only when it is a backlog item id; a topic, a kb article's
path, is one on the day's cost points.
"""
import json
import math
import re

import mon_base

ID_VALUE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:/#@-]{0,119}")
ITEM_ID = re.compile(r"[A-Z]{2}-[0-9a-z]{8}")  # a backlog item id, the one claim key an attribute may carry
FORBIDDEN = frozenset({"holder"})


class Rejected(Exception):
    """An attribute value that is no number, flag or redaction-stable identifier."""


_known = None


def stable(text):
    """True when `text` is an identifier that `redact.redact` leaves unchanged."""
    global _known
    if not ID_VALUE.fullmatch(text):
        return False
    import redact
    import mon_view
    _known = _known or mon_view.LazyKnown()
    return redact.redact(text, _known) == text


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def attributes(attrs):
    """`attrs` when each value is a number, a flag or a stable identifier and no name is forbidden, else Rejected."""
    for name, value in attrs.items():
        if name in FORBIDDEN or not isinstance(name, str) or not ID_VALUE.fullmatch(name):
            raise Rejected(name)
        if isinstance(value, bool) or number(value):
            continue
        if not (isinstance(value, str) and stable(value)):
            raise Rejected(name)
    return attrs


def point(name, unit, kind, value, **attrs):
    """One point, or None when its value is no number or an attribute value is rejected."""
    if kind not in ("gauge", "sum") or not number(value):
        return None
    try:
        return {"name": name, "unit": unit, "kind": kind, "value": value, "attributes": attributes(attrs)}
    except Rejected:
        return None


def kb_points(data):
    out = []
    for r in data.get("roots", []):
        out.append(point("kbmon.kb.articles", "{article}", "gauge", r.get("articles"), root=r.get("root")))
        for tag, n in (r.get("facts") or {}).items():
            out.append(point("kbmon.kb.facts", "{fact}", "gauge", n, root=r.get("root"), tag=tag))
    out.append(point("kbmon.kb.gaps", "{gap}", "gauge", data.get("gaps")))
    out.append(point("kbmon.kb.conflicts", "{conflict}", "gauge", data.get("conflicts")))
    out.append(point("kbmon.kb.index_age", "s", "gauge", data.get("index_age_s")))
    ev = data.get("eval")
    if isinstance(ev, dict) and ev.get("state") in ("passed", "failed"):
        out.append(point("kbmon.kb.eval_passed", "1", "gauge", 1 if ev["state"] == "passed" else 0))
    return out


def coord_points(data):
    claims = [c for c in data.get("claims", []) if isinstance(c, dict)]
    over = sum(1 for c in claims if c.get("over_budget") is True)
    out = [point("kbmon.coord.claims", "{claim}", "gauge", len(claims) - over, state="live"),
           point("kbmon.coord.claims", "{claim}", "gauge", over, state="over_budget")]
    for c in claims:
        key = c.get("key")
        if isinstance(key, str) and ITEM_ID.fullmatch(key):
            out += [point("kbmon.coord.claim.left", "s", "gauge", c.get("left_s"), item=key),
                    point("kbmon.coord.claim.budget", "USD", "gauge", c.get("budget_usd"), item=key),
                    point("kbmon.coord.claim.spend", "USD", "gauge", c.get("spend_usd"), item=key)]
    out += run_points(data.get("runs"))
    seqs = [e.get("seq") for e in data.get("events", []) if isinstance(e, dict) and number(e.get("seq"))]
    if seqs:
        out.append(point("kbmon.coord.event_seq", "{event}", "sum", max(seqs)))
    return out


def sessions_points(data):
    out = []
    procs = [p for p in data.get("procs", []) if isinstance(p, dict)]
    for cls in sorted({p.get("class") for p in procs if isinstance(p.get("class"), str)}):
        out.append(point("kbmon.sessions.procs", "{process}", "gauge", sum(1 for p in procs if p.get("class") == cls),
                         **{"class": cls}))
    if isinstance(data.get("worktrees"), list):
        out.append(point("kbmon.sessions.worktrees", "{worktree}", "gauge", len(data["worktrees"])))
    if isinstance(data.get("stalled"), list):
        out.append(point("kbmon.sessions.stalled", "{item}", "gauge", len(data["stalled"])))
    if isinstance(data.get("sessions"), list):  # the most `silent_s` of a live session, 0 with none
        secs = [s["silent_s"] for s in data["sessions"] if isinstance(s, dict) and number(s.get("silent_s"))]
        out.append(point("kbmon.sessions.silent", "s", "gauge", max(secs, default=0)))
    return out


def cleanup_points(data):
    out = []
    for cls, c in (data.get("counts") or {}).items():
        for verdict in ("remove", "keep"):
            out.append(point("kbmon.cleanup.leftovers", "{leftover}", "gauge", c.get(verdict), **{"class": cls, "verdict": verdict}))
    out.append(point("kbmon.cleanup.removable_bytes", "By", "gauge", data.get("bytes")))
    out.append(point("kbmon.cleanup.free", "GiBy", "gauge", data.get("free_gib")))
    return out


def run_points(runs):
    """The run states of the items: every state's count, the seconds the oldest blocked run has waited since its newest progress
    event and the most seconds a working run has gone silent (`silent_s`: with its worker running, the lesser of the seconds
    since its newest progress event and since its transcript's last write; with the worker gone, the first of them), 0 for none;
    nothing where the coord data holds no `runs` list."""
    if not isinstance(runs, list):
        return []
    import coord
    runs = [r for r in runs if isinstance(r, dict)]
    out = [point("kbmon.coord.runs", "{run}", "gauge", sum(1 for r in runs if r.get("state") == state), state=state)
           for state in coord.RUN_STATES]
    for name, state, field in (("blocked_wait", "blocked", "age_s"), ("working_silent", "working", "silent_s")):
        secs = [r[field] for r in runs if r.get("state") == state and number(r.get(field))]
        out.append(point(f"kbmon.coord.run.{name}", "s", "gauge", max(secs, default=0)))
    return out


def querylog_points(data):
    """The UTC day's cost in USD (`usage_today`): the day's total, and one point for each topic (a kb article, the
    costliest first) that the day's prompts named, whose cost is shared evenly over the topics a prompt named; the
    claim spend points carry the item. A topic that is no stable identifier leaves its point out."""
    u = data.get("usage_today")
    if not isinstance(u, dict):
        return []
    out = [point("kbmon.querylog.cost", "USD", "gauge", u.get("usd"))]
    for topic, usd in (u.get("by_topic") or {}).items():
        out.append(point("kbmon.querylog.cost", "USD", "gauge", usd, topic=topic))
    return out


EXPORTERS = {"kb": kb_points, "coord": coord_points, "sessions": sessions_points, "cleanup": cleanup_points,
             "querylog": querylog_points}


def points(snap):
    out = []
    for name, panel in snap.get("panels", {}).items():
        if not isinstance(panel, dict) or name not in mon_base.PANELS:
            continue
        out.append(point("kbmon.panel.up", "1", "gauge", 1 if panel.get("state") == "ok" else 0, panel=name))
        out.append(point("kbmon.panel.seconds", "s", "gauge", panel.get("seconds"), panel=name))
        export = EXPORTERS.get(name)
        if export and panel.get("state") == "ok" and isinstance(panel.get("data"), dict):
            try:
                out += export(panel["data"])
            except (AttributeError, TypeError, ValueError):  # a saved snapshot may hold data the exporter does not take
                pass
    out.append(point("kbmon.alerts", "{alert}", "gauge", len(snap.get("alerts") or [])))
    return [x for x in out if x]


def render(snap):
    return json.dumps({"schema": mon_base.SCHEMA, "taken": snap.get("taken"), "points": points(snap)},
                      ensure_ascii=False, indent=1)
