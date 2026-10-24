"""kbmon's receipt: the agent's one-line view of the snapshot's alerts and what waits on the operator, and a fingerprint of the
alerts (stdlib only; imports `mon_needs`, which imports nothing at load).

  receipt(snap)    {"line": str, "fingerprint": str} from a scrubbed snapshot (`mon_view.scrub`)

The line is at most MAX_LINE characters and unchanged by `redact.redact`. It names up to NAMED alert messages, how many more
there are and the command that prints the state of the first alert's panel (with no alert it says so), and ends with the
count of `mon_needs.entries` and the command that prints the `needs you` line, with the panels that count could not read.
The fingerprint is the hash of the sorted kinds and ids of the alerts only, so it moves when an alert appears, goes or changes
kind, not when an alert's message or since changes, nor when what waits on the operator does. Docs: kb/_self/monitoring.md.
"""
import hashlib
import json

import mon_needs

MAX_LINE = 200
NAMED = 2  # alert messages the line names
FINGERPRINT_CHARS = 12
DEFAULT_PANELS = ("querylog", "sessions", "host", "sprint", "coord")  # the alert panels and the panels the count reads
ALERT_PANELS = ("querylog", "sessions", "host")  # the panels of the line's alert part
COMMAND = "python3 _tools/kbmon.py --once --panel "
NEEDS_COMMAND = "python3 _tools/kbmon.py --status all"


def one_line(text):
    return " ".join(str(text).split())


def pairs(alerts):
    """The sorted, distinct `(kind, id)` of the alerts; an alert that is no object counts as kind and id `?`."""
    found = {(one_line(a.get("kind") or "?"), one_line(a.get("id") or "?")) if isinstance(a, dict) else ("?", "?")
             for a in alerts}
    return sorted(found)


def fingerprint(alerts):
    text = json.dumps(pairs(alerts), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:FINGERPRINT_CHARS]


def message(alert):
    if not isinstance(alert, dict):
        return "?"
    return one_line(alert.get("message") or alert.get("id") or "?")


def clip(text, n):
    return text if len(text) <= n else text[:max(1, n - 1)].rstrip() + "…"


def needs_tail(snap):
    """`; needs you: N — COMMAND`: N entries of `mon_needs.entries`, with `(not read: PANELS)` for the panels it lacks."""
    missing = mon_needs.unread(snap)
    return (f"; needs you: {len(mon_needs.entries(snap))}" + (f" (not read: {', '.join(missing)})" if missing else "")
            + " — " + NEEDS_COMMAND)


def assemble(alerts, panel, budget):
    """The alert part of the line with `budget` characters for the messages in all."""
    named = [message(a) for a in alerts[:NAMED]]
    each = max(1, (budget - 2 * (len(named) - 1)) // len(named))
    shown = [clip(m, each) for m in named]
    rest = len(alerts) - len(named)
    return ("ALERT " + "; ".join(shown) + (f" (+{rest} more)" if rest else "") + " — state on ask: " + COMMAND + panel)


def line(alerts, names, tail):
    """The line: the alert part, shrunk until `redact.redact` leaves the whole as it is and it fits, then TAIL; with no alert,
    a part that says which alert panels were read."""
    import redact
    if not alerts:
        return redact.redact(clip("kbmon: no alert on " + ", ".join(n for n in names if n in ALERT_PANELS), MAX_LINE - len(tail)) + tail)
    first = alerts[0] if isinstance(alerts[0], dict) else {}
    panel = one_line(first.get("panel") or (names[0] if names else "host"))
    budget = MAX_LINE - len(tail)
    while True:
        text = redact.redact(assemble(alerts, panel, budget) + tail)
        if len(text) <= MAX_LINE or budget <= 2:
            return clip(text, MAX_LINE)
        budget -= len(text) - MAX_LINE


def receipt(snap, names=DEFAULT_PANELS):
    alerts = [a for a in snap.get("alerts") or []]
    return {"line": line(alerts, names, needs_tail(snap)), "fingerprint": fingerprint(alerts)}
