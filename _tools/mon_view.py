"""kbmon's output (kb/_self/monitoring.md): the redaction every printed string passes and the text view of a snapshot.
Standard library only; imports `mon_base` and `redact` (at the first redaction).

  scrub(obj)                     a copy of a snapshot with every string, key and value, passed through `redact.redact`
                                 (its `LazyKnown` reads the public root only when a rule needs it); a snapshot also gets
                                 the alerts its `ok` panels judge (`judged`: each module's `alerts(data)`)
  render_text(snap, ansi=False, width=80, height=None, frame=1, interval=5, root=".")
                                 one frame of the text view, laid out as the Layout section of the doc gives it: no line
                                 past `width` less one columns, each string redacted, an escape byte only with `ansi`
                                 (colour), and no control character of a panel's own text ever reaches the terminal
  enable_vt()                    True when the console takes ANSI escapes: always off Windows, there the console's
                                 virtual terminal processing switched on, False when it cannot be
  CLEAR                          the cursor-home and erase sequences that start a frame redrawn in place
  ResizeWatch(size=None, use_signal=None)
                                 a context manager that reports a terminal size change: `poll()` gives `(old, new)` (columns,
                                 lines) once the size differs from the last `mark()`, on SIGWINCH where there is one, else
                                 by reading the size; `slice` is the seconds to wait between polls
  render_json(snap)              the snapshot as JSON text
"""
import inspect
import json
import re
import shutil
import signal
import sys

import mon_base

CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
COLOURS = {"ok": "32", "timeout": "33", "error": "31", "absent": "90", "unsupported": "90"}
GUTTER_COLOURS = {"! ": "33", "!!": "31"}  # a warning row, an error row
ALERT_COLOUR = "1;97;41"
CLEAR = "\x1b[H\x1b[2J"
MIN_LOG_ROWS = 3
VT_FLAG = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
STD_OUTPUT_HANDLE = -11
FIELD_CHARS = 200  # characters of a value the generic view of a panel prints


class LazyKnown:
    """`redact.known()` read at the first attribute a rule asks for. `redact.redact` takes it for what the public root
    already contains and a rule needs it only for a string that matches an identifier shape, so a snapshot of plain words,
    numbers and dates pays no read of the whole public root (some seconds) and one with a host name or a path does."""

    def __getattr__(self, name):
        import redact
        return getattr(redact.known(), name)


def judged(snap):
    """The snapshot with the alerts its `ok` panels judge (a panel module's `alerts(data)`, a list of {kind, id, message,
    since}) added to its `alerts`; an alert whose id the snapshot already holds is not added twice, so a saved snapshot
    shown again keeps one."""
    alerts = list(snap.get("alerts") or [])
    seen = {a.get("id") for a in alerts if isinstance(a, dict)}
    for name, panel in snap["panels"].items():
        if not isinstance(panel, dict) or panel.get("state") != "ok" or not isinstance(panel.get("data"), dict):
            continue
        try:
            module = mon_base.panel_module(name)
            found = module.alerts(panel["data"]) if hasattr(module, "alerts") else []
        except Exception:  # noqa: BLE001 - a saved snapshot may hold data the module's judgement does not take
            continue
        for alert in found:
            if alert.get("id") not in seen:
                seen.add(alert.get("id"))
                alerts.append(alert)
    return {**snap, "alerts": alerts}


def scrub(obj, memo=None):
    """The snapshot with each string redacted (`redact.redact`), also the keys of an object; numbers, booleans and
    null stay. A string is redacted once however often it occurs. A snapshot (an object with `panels`) also gets the
    alerts its panels judge (`judged`)."""
    import redact
    if isinstance(obj, dict) and isinstance(obj.get("panels"), dict):
        obj = judged(obj)
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


def enable_vt():
    """True when this console takes ANSI escape sequences. Off Windows every terminal does; on Windows the console's
    virtual terminal processing is switched on for standard output, and False says it cannot be (no console, an old
    console host, a redirected output)."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_ulong()
        if not handle or not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | VT_FLAG))
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError):
        return False


class ResizeWatch:
    """Tells the live view that the terminal changed size. Where the platform has SIGWINCH the signal sets a flag and
    `poll` then reads the size; where it has not (Windows) `poll` reads the size itself, so the caller polls it a few times a
    second. `mark` records the size of the frame just drawn; `poll` returns `(old, new)` sizes once they differ, else None.
    `size` and `use_signal` can be given for a planted size sequence."""

    SIGNAL_SLICE = 0.1  # seconds between flag checks (the flag is a bool read, so this is cheap)
    POLL_SLICE = 0.25  # seconds between size reads without SIGWINCH

    def __init__(self, size=None, use_signal=None):
        self.size = size or shutil.get_terminal_size
        self.use_signal = hasattr(signal, "SIGWINCH") if use_signal is None else use_signal
        self.slice = self.SIGNAL_SLICE if self.use_signal else self.POLL_SLICE
        self.flag = False
        self.last = tuple(self.size())
        self.previous = None

    def __enter__(self):
        if self.use_signal:
            try:
                self.previous = signal.signal(signal.SIGWINCH, self.on_winch)
            except ValueError:  # not the main thread: read the size instead
                self.use_signal, self.slice = False, self.POLL_SLICE
        return self

    def __exit__(self, *exc):
        if self.use_signal and self.previous is not None:
            signal.signal(signal.SIGWINCH, self.previous)

    def on_winch(self, *_):
        self.flag = True

    def mark(self):
        self.flag = False
        self.last = tuple(self.size())

    def poll(self):
        if self.use_signal:
            if not self.flag:
                return None
            self.flag = False
        now = tuple(self.size())
        if now == self.last:
            return None
        old, self.last = self.last, now
        return old, now


def takes_width(view):
    try:
        params = inspect.signature(view).parameters.values()
    except (TypeError, ValueError):
        return False
    return len(params) >= 2 or any(x.kind is x.VAR_POSITIONAL for x in params)


def panel_lines(name, data, width):
    """The body rows of a panel: its module's `lines(data[, width])` (a second parameter gets the columns it may use), each
    cut into printable lines; the generic view when it has none or fails."""
    try:
        module = mon_base.panel_module(name)
        view = getattr(module, "lines", None)
        if view is not None:
            rows = view(data, width) if takes_width(view) else view(data)
            return [part for x in rows for part in (plain(x).expandtabs(4).splitlines() or [""])]
    except Exception:  # noqa: BLE001 - a saved snapshot may hold data the module's view does not take
        pass
    return generic_lines(data)


def reason(name, state, panel):
    """The text after a title's dash: why a panel that is not ok shows nothing."""
    data = panel.get("data") if isinstance(panel.get("data"), dict) else {}
    if state == "timeout":
        return "no answer in time"
    if state == "absent":
        return f"no mon_{name}.py"
    if state in ("error", "unsupported"):
        return one_line(data.get("error" if state == "error" else "reason", ""))
    return ""


def one_line(text):
    return " ".join(plain(text).split())


def title_row(name, panel):
    """`name  state  S.Ss` at column 0, then `  — reason` unless ok: the name bold, the state coloured, the rest dim."""
    state = one_line(panel.get("state", "?"))
    seconds = panel.get("seconds")
    shown = f"{seconds:.1f}s" if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else "?"
    dim = "" if state == "ok" else "90"
    row = [(one_line(name), "1"), ("  ", ""), (state, COLOURS.get(state, "")), (f"  {shown}", dim)]
    why = reason(name, state, panel)
    if state != "ok" and why:
        row.append((f"  \u2014 {why}", "90"))
    return row


def body_rows(name, panel, width):
    """The rows under a title, each behind the two-column gutter: a row of the panel's own that starts `! ` or `!!` keeps
    it (its colour is the whole row's), any other gets two spaces. A panel that is not ok has none."""
    if panel.get("state") != "ok" or "data" not in panel:
        return []
    rows = []
    for x in panel_lines(name, panel["data"], width):
        x = x.rstrip()
        if x[:2] not in GUTTER_COLOURS and x:
            x = "  " + x
        rows.append([(x, GUTTER_COLOURS.get(x[:2], ""))])
    return rows


def cut(row, width):
    """The row within `width` characters: a longer one ends in an ellipsis in the colour of the run it cuts."""
    if sum(len(t) for t, _ in row) <= width:
        return row
    out, used = [], 0
    for text, sgr in row:
        room = width - 1 - used
        if room <= 0:
            break
        out.append((text[:room], sgr))
        used += min(len(text), room)
        if len(text) > room:
            break
    out.append(("\u2026", out[-1][1] if out else ""))
    return out


def alert_text(alerts, cols=None):
    """`!! ALERT message — since HH:MM (+N more)` of the first alert; with `cols` a message too long for the line is cut
    with an ellipsis so that the since and the count stay."""
    first = alerts[0]
    if isinstance(first, dict):
        message = first.get("message") or first.get("id") or json.dumps(first, ensure_ascii=False)
        since = first.get("since")
    else:
        message, since = first, None
    head = "!! ALERT "
    tail = (f" \u2014 since {one_line(since)}" if since else "") + (f" (+{len(alerts) - 1} more)" if len(alerts) > 1 else "")
    message = one_line(message)
    if cols and len(head) + len(message) + len(tail) > cols:
        message = message[:max(1, cols - len(head) - len(tail) - 1)].rstrip() + "\u2026"
    return head + message + tail


def to_text(row, ansi):
    if not ansi:
        return "".join(t for t, _ in row)
    return "".join(f"\x1b[{s}m{t}\x1b[K\x1b[0m" if s == ALERT_COLOUR else f"\x1b[{s}m{t}\x1b[0m" if s and t else t
                   for t, s in row)


def render_text(snap, ansi=False, width=80, height=None, frame=1, interval=5, root="."):
    """One frame of the text view (the layout in kb/_self/monitoring.md): the alert line when the snapshot has an alert
    (and, without colour, a row of `=` under it), the header, a blank row, then each panel's title and body rows with a
    blank row between, the log last. With `height` the log's rows are cut to what the screen has left (three at least)
    and the frame to `height` less one rows. `width` is the terminal's columns: no line passes `width` less one."""
    cols = max(20, int(width) - 1)
    taken = one_line(snap.get("taken", "?")).replace("T", " ", 1)
    rows = [[("kbmon", "1"), (f" \u00b7 {taken} \u00b7 refresh {interval}s \u00b7 frame {frame} \u00b7 {root}", "")], []]
    panels = [(n, p if isinstance(p, dict) else {}) for n, p in snap.get("panels", {}).items()]
    for name, panel in panels:
        if name == "log":
            continue
        rows += [title_row(name, panel)] + body_rows(name, panel, cols) + [[]]
    for name, panel in panels:
        if name == "log":
            tail = body_rows(name, panel, cols)
            if height:
                tail = tail[:max(MIN_LOG_ROWS, int(height) - 2 - len(rows))]
            rows += [title_row(name, panel)] + tail
    while rows and not rows[-1]:
        rows.pop()
    texts = scrub([t for row in rows for t, _ in row])  # a panel's own view may join redacted values into a new shape
    it = iter(texts)
    rows = [[(next(it), s) for _, s in row] for row in rows]
    alerts = snap.get("alerts") or []
    if alerts:
        head = [[(scrub([alert_text(alerts, cols)])[0], ALERT_COLOUR)]]
        rows = head + ([] if ansi else [[("=" * cols, "")]]) + rows
    if height:
        rows = rows[:max(1, int(height) - 1)]
    return "\n".join(to_text(cut(row, cols), ansi) for row in rows)
