#!/usr/bin/env python3
"""kbmon: the kb, coord, running sessions, the query log and the host in one snapshot (stdlib only). Docs: kb/_self/monitoring.md.

  kbmon.py --json              print one snapshot as a JSON object of schema 1: a panel for each of kb, coord, sessions,
                               querylog, host, sprint and log, each with its state (ok, timeout, error, absent or
                               unsupported), its seconds and, unless it timed out or is absent, its data
  kbmon.py --once              print the same panels as plain text, with no escape byte
  kbmon.py                     print the text view every --interval seconds, --count times (0: until interrupted)

  --root DIR                   the clone to read (default: the one this script is in)
  --panel NAME                 only this panel (repeatable)
  --timeout S                  seconds each panel may take; one still running then is shown as timeout (default 10)
  --ansi                       colour the text view (an escape byte); a clear of the screen between live frames
  --interval S, --count N      the live view's pause between frames and number of frames
  --store PATH, --url URL, --key-file PATH   the coord store, or the coord server and its operator's key file
  --from-snapshot FILE         show a snapshot saved with --json instead of reading the sources

A run reads and writes nothing: no index is built, no eval is run, no file of the clone, the query log home or `_cache/`
is written. Every string printed passes `redact.redact`, a saved snapshot's too. Exit codes: 0 shown, 1 shown and an alert
is in the snapshot, 2 a bad argument or an unreadable snapshot. Each panel is `mon_<name>.py` (`mon_base.py` holds the
run, `mon_view.py` the output).
"""
import argparse
import sys
import time
from pathlib import Path

import mon_base
import mon_view

DEFAULT_TIMEOUT = 10.0  # seconds a panel may take
DEFAULT_INTERVAL = 2.0  # seconds between live frames
CLEAR = "\x1b[H\x1b[2J"


def positive(text):
    value = float(text)
    if not value > 0:
        raise argparse.ArgumentTypeError("must be above 0")
    return value


def whole(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def parser():
    ap = argparse.ArgumentParser(prog="kbmon.py", description=__doc__.split("\n\n")[0].splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--panel", action="append", choices=mon_base.PANELS, help="a panel to show (repeatable; default: all)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="print one snapshot as JSON")
    mode.add_argument("--once", action="store_true", help="print one snapshot as plain text")
    ap.add_argument("--ansi", action="store_true", help="colour the text view")
    ap.add_argument("--interval", type=positive, default=DEFAULT_INTERVAL, metavar="S")
    ap.add_argument("--count", type=whole, default=0, metavar="N")
    ap.add_argument("--timeout", type=positive, default=DEFAULT_TIMEOUT, metavar="S")
    ap.add_argument("--store", metavar="PATH")
    ap.add_argument("--url", metavar="URL")
    ap.add_argument("--key-file", metavar="PATH")
    ap.add_argument("--from-snapshot", metavar="FILE")
    return ap


def take(a, names):
    """The snapshot to show: the saved one, or one read now, with every string redacted."""
    if a.from_snapshot:
        snap = mon_base.load_snapshot(a.from_snapshot, names if a.panel else None)
    else:
        ctx = mon_base.Ctx(root=a.root.resolve(), store=a.store, url=a.url, key_file=a.key_file)
        snap = mon_base.snapshot(ctx, names, a.timeout)
    return mon_view.scrub(snap)


def live(a, names, out):
    """The text view again and again; the exit code is that of the last snapshot."""
    code, frame = 0, 0
    try:
        while not a.count or frame < a.count:
            snap = take(a, names)
            code = 1 if snap["alerts"] else 0
            out.write((CLEAR if a.ansi else "") + mon_view.render_text(snap, a.ansi) + "\n" + ("" if a.ansi else "\n"))
            out.flush()
            frame += 1
            if not a.count or frame < a.count:
                time.sleep(a.interval)
    except KeyboardInterrupt:
        pass
    return code


def main(argv=None, out=None):
    out = out or sys.stdout
    ap = parser()
    a = ap.parse_args(argv)
    names = tuple(dict.fromkeys(a.panel)) if a.panel else mon_base.PANELS
    names = tuple(n for n in mon_base.PANELS if n in names)
    try:
        if a.json or a.once:
            snap = take(a, names)
            out.write((mon_view.render_json(snap) if a.json else mon_view.render_text(snap, a.ansi)) + "\n")
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
