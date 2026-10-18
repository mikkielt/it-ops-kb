"""kbmon's output (kb/_self/monitoring.md): the redaction every printed string passes and the text view of a snapshot.
Standard library only; imports `mon_base` and `redact` (at the first redaction).

  scrub(obj)                     a copy of a snapshot with every string, key and value, passed through `redact.redact`
                                 (its `LazyKnown` reads the public root only when a rule needs it)
  render_text(snap, ansi=False)  the lines of a snapshot as text, each redacted; an escape byte only with `ansi` (colour),
                                 and no control character of a panel's own text ever reaches the terminal
  render_json(snap)              the snapshot as JSON text
"""
import json
import re

import mon_base

CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
COLOURS = {"ok": "32", "timeout": "33", "error": "31", "absent": "90", "unsupported": "90"}
FIELD_CHARS = 200  # characters of a value the generic view of a panel prints


class LazyKnown:
    """`redact.known()` read at the first attribute a rule asks for. `redact.redact` takes it for what the public root
    already contains and a rule needs it only for a string that matches an identifier shape, so a snapshot of plain words,
    numbers and dates pays no read of the whole public root (some seconds) and one with a host name or a path does."""

    def __getattr__(self, name):
        import redact
        return getattr(redact.known(), name)


def scrub(obj, memo=None):
    """The snapshot with each string redacted (`redact.redact`), also the keys of an object; numbers, booleans and
    null stay. A string is redacted once however often it occurs."""
    import redact
    memo = {} if memo is None else memo
    known = LazyKnown()

    def clean(s):
        if s not in memo:
            memo[s] = redact.redact(s, known) if s else s
        return memo[s]

    def walk(o):
        if isinstance(o, str):
            return clean(o)
        if isinstance(o, dict):
            return {clean(k) if isinstance(k, str) else k: walk(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [walk(v) for v in o]
        return o

    return walk(obj)


def render_json(snap):
    return json.dumps(snap, ensure_ascii=False, indent=1)


def plain(text):
    """One printable line: control characters (an escape byte first) become `?`."""
    return CONTROL.sub("?", str(text))


def generic_lines(data):
    """The lines of a panel data object nobody wrote a view for: one `key: value` line each."""
    if not isinstance(data, dict):
        return [plain(json.dumps(data, ensure_ascii=False))[:FIELD_CHARS]]
    return [f"{plain(k)}: {plain(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))[:FIELD_CHARS]}"
            for k, v in data.items()]


def panel_lines(name, data):
    try:
        module = mon_base.panel_module(name)
        view = getattr(module, "lines", None)
        if view is not None:
            return [plain(x) for x in view(data)]
    except Exception:  # noqa: BLE001 - a saved snapshot may hold data the module's view does not take
        pass
    return generic_lines(data)


def paint(text, state, ansi):
    return f"\x1b[{COLOURS.get(state, '0')}m{text}\x1b[0m" if ansi else text


def render_text(snap, ansi=False):
    """The text view: a head line, then per panel a line `name  state  seconds` and the panel's lines, indented."""
    lines = [f"kbmon  schema {plain(snap.get('schema'))}  taken {plain(snap.get('taken', '?'))}"]
    for name, panel in snap.get("panels", {}).items():
        panel = panel if isinstance(panel, dict) else {}
        state = plain(panel.get("state", "?"))
        seconds = panel.get("seconds")
        shown = f"{seconds:.2f}s" if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else "?"
        lines.append(f"{plain(name):<9} {paint(f'{state:<11}', state, ansi)} {shown}")
        if state == "ok" and "data" in panel:
            lines += ["  " + x for x in panel_lines(name, panel["data"])]
        elif isinstance(panel.get("data"), dict):
            lines += ["  " + x for x in generic_lines(panel["data"])]
    for alert in snap.get("alerts", []):
        lines.append(paint("alert: ", "error", ansi) + plain(alert if isinstance(alert, str) else json.dumps(alert)))
    return "\n".join(scrub(lines))  # a panel's own view may join redacted values into a shape the rules change
