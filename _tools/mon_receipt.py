"""kbmon's receipt: the agent's one-line view of the snapshot's alerts and a fingerprint of them (stdlib only).

  receipt(snap)    {"line": str, "fingerprint": str} from the alerts of a scrubbed snapshot (`mon_view.scrub`)

The line is at most MAX_LINE characters and unchanged by `redact.redact`. It names up to NAMED alert messages, how many more
there are and the command that prints the state of the first alert's panel; with no alert it says so. The fingerprint is
the hash of the sorted kinds and ids of the alerts, so it moves when an alert appears, goes or changes kind, not when an
alert's message or since changes. Docs: kb/_self/monitoring.md.
"""
import hashlib
import json

MAX_LINE = 200
NAMED = 2  # alert messages the line names
FINGERPRINT_CHARS = 12
DEFAULT_PANELS = ("querylog", "sessions", "host")
COMMAND = "python3 _tools/kbmon.py --once --panel "


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


def assemble(alerts, panel, budget):
    """The alert line with `budget` characters for the messages in all."""
    named = [message(a) for a in alerts[:NAMED]]
    each = max(1, (budget - 2 * (len(named) - 1)) // len(named))
    shown = [clip(m, each) for m in named]
    rest = len(alerts) - len(named)
    return ("ALERT " + "; ".join(shown) + (f" (+{rest} more)" if rest else "") + " — state on ask: " + COMMAND + panel)


def line(alerts, names):
    """The line: the alert one, shrunk until `redact.redact` leaves it as it is and it fits; with no alert, a line that
    says which panels were read."""
    import redact
    if not alerts:
        return redact.redact(clip("kbmon: no alert on " + ", ".join(names), MAX_LINE))
    first = alerts[0] if isinstance(alerts[0], dict) else {}
    panel = one_line(first.get("panel") or (names[0] if names else "host"))
    budget = MAX_LINE
    while True:
        text = redact.redact(assemble(alerts, panel, budget))
        if len(text) <= MAX_LINE or budget <= 2:
            return clip(text, MAX_LINE)
        budget -= len(text) - MAX_LINE


def receipt(snap, names=DEFAULT_PANELS):
    alerts = [a for a in snap.get("alerts") or []]
    return {"line": line(alerts, names), "fingerprint": fingerprint(alerts)}
