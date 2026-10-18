#!/usr/bin/env python3
"""kbmon: the kb, coord, running sessions, the query log and the host in one snapshot (stdlib only). Docs: kb/_self/monitoring.md.

  kbmon.py --json              print one snapshot as a JSON object of schema 1: a panel for each of kb, coord, sessions,
                               querylog, host, sprint and log, each with its state (ok, timeout, error, absent or
                               unsupported), its seconds and, unless it timed out or is absent, its data
  kbmon.py --once              print the same panels as plain text, with no escape byte
  kbmon.py --metrics           print the snapshot as one JSON object of metric points (name kbmon.<panel>.<measure>, unit,
                               kind gauge or sum, value, attributes of numbers, flags and redacted ids; no claim holder)
  kbmon.py --events [--since CURSOR]
                               print one JSON object of schema 1: a cursor, the events (coord events, `done.refused` rows
                               and the query log's apply outcome) and the spans (each landing with a child span per
                               `land.step`, each `agent.run` and `test.run`, each timed delivery) newer than CURSOR, with
                               times in Unix nanoseconds and attributes of numbers, flags and redacted ids; the cursor is
                               the caller's to keep, and a call with the one it was given repeats none of them
  kbmon.py                     show the text view every --interval seconds, --count times (default: until interrupted); on a
                               terminal it is redrawn in place with ANSI escapes (and again, from the last snapshot,
                               when the window is resized), on a pipe or under NO_COLOR it is plain frames one after
                               another

  --root DIR                   the clone to read (default: the one this script is in)
  --panel NAME                 only this panel (repeatable)
  --timeout S                  seconds each panel may take; one still running then is shown as timeout (default 10)
  --ansi                       colour the text view and redraw live frames in place (an escape byte), also on a pipe
                               or under NO_COLOR
  --interval S, --count N      the live view's pause between frames, 1 to 300 seconds (default 5), and number of frames
                               (1 or more)
  --store PATH, --url URL, --key-file PATH   the coord store, or the coord server and its operator's key file
  --from-snapshot FILE         show a snapshot saved with --json instead of reading the sources

A run reads and writes nothing: no index is built, no eval is run, no file of the clone, the query log home or `_cache/`
is written. Every string printed passes `redact.redact`, a saved snapshot's too. Exit codes: 0 shown, 1 shown and an alert
is in the snapshot, 2 a bad argument or an unreadable snapshot. Each panel is `mon_<name>.py` (`mon_base.py` holds the
run, `mon_view.py` the output, `mon_export.py` the metric points, `mon_events.py` the event and span records).
"""
import argparse
import contextlib
import os
import shutil
import sys
import time
from pathlib import Path

import mon_base
import mon_events
import mon_export
import mon_view

DEFAULT_TIMEOUT = 10.0  # seconds a panel may take
DEFAULT_INTERVAL = 5  # seconds between live frames
MAX_INTERVAL = 300


def positive(text):
    value = float(text)
    if not value > 0:
        raise argparse.ArgumentTypeError("must be above 0")
    return value


def interval(text):
    value = int(text)
    if not 1 <= value <= MAX_INTERVAL:
        raise argparse.ArgumentTypeError(f"must be 1 to {MAX_INTERVAL}")
    return value


def frames(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def parser():
    ap = argparse.ArgumentParser(prog="kbmon.py", description=__doc__.split("\n\n")[0].splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--panel", action="append", choices=mon_base.PANELS, help="a panel to show (repeatable; default: all)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="print one snapshot as JSON")
    mode.add_argument("--once", action="store_true", help="print one snapshot as plain text")
    mode.add_argument("--metrics", action="store_true", help="print one snapshot as JSON metric points")
    mode.add_argument("--events", action="store_true", help="print events and spans newer than --since as JSON")
    ap.add_argument("--since", metavar="CURSOR", help="with --events: the cursor an earlier call printed (default: the newest records)")
    ap.add_argument("--ansi", action="store_true", help="colour the text view")
    ap.add_argument("--interval", type=interval, default=DEFAULT_INTERVAL, metavar="S")
    ap.add_argument("--count", type=frames, default=None, metavar="N")
    ap.add_argument("--timeout", type=positive, default=DEFAULT_TIMEOUT, metavar="S")
    ap.add_argument("--store", metavar="PATH")
    ap.add_argument("--url", metavar="URL")
    ap.add_argument("--key-file", metavar="PATH")
    ap.add_argument("--from-snapshot", metavar="FILE")
    return ap


def take(a, names, kept=None):
    """The snapshot to show: the saved one, or one read now (`kept`: the live view's memory of the earlier ones), with
    every string redacted."""
    if a.from_snapshot:
        snap = mon_base.load_snapshot(a.from_snapshot, names if a.panel else None)
    else:
        ctx = mon_base.Ctx(root=a.root.resolve(), store=a.store, url=a.url, key_file=a.key_file)
        snap = mon_base.snapshot(ctx, names, a.timeout, kept)
    return mon_view.scrub(snap)


def colour(a, out, live_view):
    """Whether the text view carries escape bytes: with `--ansi`; else a live view on a terminal without NO_COLOR. Where
    the console cannot take them (`mon_view.enable_vt()` is False, Windows only) the frames are plain."""
    if not (a.ansi or (live_view and out.isatty() and not os.environ.get("NO_COLOR"))):
        return False
    return mon_view.enable_vt()


def frame_text(snap, a, ansi, out, frame):
    """One frame, laid out for the terminal's columns (and, redrawn in place on a terminal, its lines)."""
    size = shutil.get_terminal_size()
    root = "." if a.root.resolve() == Path(__file__).resolve().parent.parent else str(a.root)
    height = size.lines if ansi and out.isatty() else None
    return mon_view.render_text(snap, ansi, size.columns, height, frame, a.interval, root)


def draw(snap, a, ansi, out, frame):
    out.write((mon_view.CLEAR if ansi else "") + frame_text(snap, a, ansi, out, frame) + "\n" + ("" if ansi else "\n"))
    out.flush()


def pause(seconds, watch, redraw):
    """Wait `seconds`, calling `redraw()` whenever the terminal's size changes meanwhile (without a watch: just wait)."""
    if watch is None:
        time.sleep(seconds)
        return
    end = time.monotonic() + seconds
    while end > time.monotonic():
        watch.wait(end - time.monotonic())
        if watch.poll():
            redraw()


def live(a, names, out):
    """The text view again and again, redrawn in place with ANSI escapes or one plain frame after another; the exit code
    is that of the last snapshot. On a terminal redrawn in place the last snapshot is drawn again, from the start of the
    screen, as soon as the terminal's size changes, without reading the panels. The next frame is read one `--interval`
    after the last was drawn, and between frames the process waits without work; a panel that is slow to read keeps its
    last result for its `REFRESH_S` seconds (`mon_base.Kept`)."""
    ansi = colour(a, out, True)
    in_place = ansi and out.isatty()
    code, frame, kept = 0, 0, mon_base.Kept()
    try:
        with (mon_view.ResizeWatch() if in_place else contextlib.nullcontext()) as watch:
            while a.count is None or frame < a.count:
                snap = take(a, names, kept)
                code = 1 if snap["alerts"] else 0
                frame += 1
                if watch:
                    watch.mark()
                draw(snap, a, ansi, out, frame)
                if a.count is None or frame < a.count:
                    pause(a.interval, watch, lambda: draw(snap, a, ansi, out, frame))
    except KeyboardInterrupt:
        pass
    return code


def main(argv=None, out=None):
    out = out or sys.stdout
    ap = parser()
    a = ap.parse_args(argv)
    if a.since is not None and not a.events:
        ap.error("--since needs --events")
    if a.events and (a.panel or a.from_snapshot):
        ap.error("--events reads the sources and takes neither --panel nor --from-snapshot")
    names = tuple(dict.fromkeys(a.panel)) if a.panel else mon_base.PANELS
    names = tuple(n for n in mon_base.PANELS if n in names)
    try:
        if a.events:
            ctx = mon_base.Ctx(root=a.root.resolve(), store=a.store, url=a.url, key_file=a.key_file)
            out.write(mon_events.render(ctx, a.since) + "\n")
            out.flush()
            return 0
        if a.json or a.once or a.metrics:
            snap = take(a, names)
            if a.metrics:
                text = mon_export.render(snap)
            else:
                text = mon_view.render_json(snap) if a.json else frame_text(snap, a, colour(a, out, False), out, 1)
            out.write(text + "\n")
            out.flush()
            return 1 if snap["alerts"] else 0
        return live(a, names, out)
    except ValueError as e:
        print(f"kbmon: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main())
