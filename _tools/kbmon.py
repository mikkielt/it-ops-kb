#!/usr/bin/env python3
"""kbmon: the kb, coord, running sessions, the query log and the host in one snapshot (stdlib only). Docs: kb/_self/monitoring.md.

  kbmon.py --json              print one snapshot as a JSON object of schema 1: a panel for each of kb, coord, sessions,
                               querylog, host, sprint, cleanup, bench and log, each with its state (ok, timeout, error, absent or
                               unsupported), its seconds and, unless it timed out or is absent, its data
  kbmon.py --once              print the same panels as plain text, with no escape byte
  kbmon.py --once --shared [--max-age S]
                               the same text, served from the clone's one shared snapshot (`_cache/kbmon/shared.json`) when
                               it is younger than S seconds (default 60), with a last line that says so and its age; else
                               one fresh run, written there under a lock, so panes that fall due together make one refresh;
                               --max-age 0 always refreshes
  kbmon.py --metrics           print the snapshot as one JSON object of metric points (name kbmon.<panel>.<measure>, unit,
                               kind gauge or sum, value, attributes of numbers, flags and redacted ids; no claim holder)
  kbmon.py --receipt           print one JSON object of `line` and `fingerprint` for an agent: the line (at most 200
                               characters) names up to two alerts of the querylog, sessions and host panels (or of the
                               panels --panel names), how many more there are and the command for the state on ask; the
                               fingerprint moves only when the set of alert kinds and ids does
  kbmon.py --events [--since CURSOR]
                               print one JSON object of schema 1: a cursor, the events (coord events, `done.refused` rows
                               and the query log's apply outcome) and the spans (each landing with a child span per
                               `land.step`, each `agent.run` and `test.run`, each timed delivery) newer than CURSOR, with
                               times in Unix nanoseconds and attributes of numbers, flags and redacted ids; the cursor is
                               the caller's to keep, and a call with the one it was given repeats none of them
  kbmon.py --split [--dry-run] open the live view (`kbmon.py --interval 60`) in a pane beside the session: tmux where TMUX is
                               set, WezTerm where WEZTERM_PANE is set, Windows Terminal where WT_SESSION is set; elsewhere
                               print the command to run in a second terminal; --dry-run prints the command it would run
                               and runs nothing; --root, --panel, --store, --url and --key-file go to the live view
  kbmon.py --follow ARGS       run `kbtail.py ARGS` and print what it prints: one session's transcript followed live in a
                               terminal, redacted and cut (ARGS: TARGET, --history N, --once; `--follow` comes first)
  kbmon.py --status [TOPIC]    print a short plain-words answer (at most 25 lines) for TOPIC: sessions, cost, querylog, coord,
                               sprints, load or all (the default), from one snapshot of the panels the topic needs; with
                               --json an object of schema 1, topic, taken, lines and facts; a claim's holder is never named;
                               it calls no model and writes no file, and exits 0 also when the snapshot has an alert
  kbmon.py --status sprints [--detail]
                               one row for each sprint, the active one first (a short name of at most 40 characters, its
                               state, done of total, the percentage and the ETA, at most 100 characters), the sprints
                               waiting for the operator's answer and the host load; --detail prints the full lines
                               instead, with the items left by their short titles
  kbmon.py --status sprints --backtest N
                               replay the sprint estimate over the last N closed sprints on `origin/main` (N of 1 or more) at 25,
                               50 and 75 percent of the time from each one's start commit to its close commit, a sprint only
                               when another closed before its start: a line for each sprint and the line `backtest: sprints=S
                               points=P median absolute error=E min median relative error=R% inside the range=C%`; with
                               --json an object of schema 1, topic, sprints and summary
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

A run reads and writes nothing (except `--shared`, which keeps the one snapshot file named above): no index is built, no
eval is run, no file of the clone, the query log home or `_cache/` is written. Every string printed passes `redact.redact`, a saved snapshot's too (not the command `--split` prints, which
must run as printed). Exit codes: 0 shown (also `--receipt`, with or without an alert, and `--split` in every case), 1 shown and an alert is in the snapshot, 2 a bad argument or an unreadable snapshot. Each panel is `mon_<name>.py` (`mon_base.py` holds the
run, `mon_view.py` the output, `mon_export.py` the metric points, `mon_events.py` the event and span records).

Answers: which sessions are running and what is stalled or waiting on the operator
Answers: what state the kb, coord, the query log, the host and the sprint are in
Answers: how a sprint, the load or the cost stands, in plain words
Use: python3 _tools/kbmon.py [--once|--json|--status TOPIC|--metrics|--events]
MCP: kb_monitor_status prints the plain-words status, or with panel NAME that panel's --json
"""
import argparse
import contextlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import mon_base
import mon_events
import mon_export
import mon_receipt
import mon_split
import mon_status
import mon_view

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT = 10.0  # seconds a panel may take
DEFAULT_INTERVAL = 5  # seconds between live frames
MAX_INTERVAL = 300
SHARED_FILE = Path("_cache") / "kbmon" / "shared.json"  # under the clone: the snapshot its interactive panes share
SHARED_MAX_AGE = 60.0  # seconds a shared snapshot is served when --max-age is not given
SHARED_LOCK_STALE_S = 120.0  # a refresh lock file older than this is a crashed run's
SHARED_POLL_S = 0.2


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


def age_seconds(text):
    value = float(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def parser():
    ap = argparse.ArgumentParser(prog="kbmon.py", description=__doc__.split("\n\n")[0].splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--panel", action="append", choices=mon_base.PANELS, help="a panel to show (repeatable; default: all)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="print one snapshot as JSON")
    mode.add_argument("--once", action="store_true", help="print one snapshot as plain text")
    mode.add_argument("--metrics", action="store_true", help="print one snapshot as JSON metric points")
    mode.add_argument("--receipt", action="store_true", help="print the agent's one-line receipt and an alert fingerprint as JSON")
    mode.add_argument("--events", action="store_true", help="print events and spans newer than --since as JSON")
    mode.add_argument("--split", action="store_true", help="open the live view in a pane beside the session")
    mode.add_argument("--follow", action="store_true", help="run kbtail.py with the arguments after --follow (it comes first)")
    ap.add_argument("--status", nargs="?", const="all", choices=mon_status.TOPICS, metavar="TOPIC",
                    help="print a short plain-words answer for TOPIC (%s; default all); with --json an object" % ", ".join(mon_status.TOPICS))
    ap.add_argument("--backtest", type=int, metavar="N", help="with --status sprints: replay the sprint estimate over the last N closed sprints")
    ap.add_argument("--detail", action="store_true", help="with --status sprints: the full lines in place of one row for each sprint")
    ap.add_argument("--dry-run", action="store_true", help="with --split: print the command, run nothing")
    ap.add_argument("--since", metavar="CURSOR", help="with --events: the cursor an earlier call printed (default: the newest records)")
    ap.add_argument("--shared", action="store_true", help="with --once: serve the clone's shared snapshot while it is fresh")
    ap.add_argument("--max-age", type=age_seconds, default=SHARED_MAX_AGE, metavar="S",
                    help="with --shared: the age in seconds up to which the snapshot is served (default %d; 0 always refreshes)" % SHARED_MAX_AGE)
    ap.add_argument("--ansi", action="store_true", help="colour the text view")
    ap.add_argument("--interval", type=interval, default=DEFAULT_INTERVAL, metavar="S")
    ap.add_argument("--count", type=frames, default=None, metavar="N")
    ap.add_argument("--timeout", type=positive, default=DEFAULT_TIMEOUT, metavar="S")
    ap.add_argument("--store", metavar="PATH")
    ap.add_argument("--url", metavar="URL")
    ap.add_argument("--key-file", metavar="PATH")
    ap.add_argument("--from-snapshot", metavar="FILE")
    return ap


def split_args(a):
    """The options of this run the split pane's live view takes along."""
    extra = []
    if a.root.resolve() != DEFAULT_ROOT:
        extra += ["--root", str(a.root.resolve())]
    for name in a.panel or ():
        extra += ["--panel", name]
    for flag, value in (("--store", a.store), ("--url", a.url), ("--key-file", a.key_file)):
        if value:
            extra += [flag, value]
    return extra


def take(a, names, kept=None):
    """The snapshot to show: the saved one, or one read now (`kept`: the live view's memory of the earlier ones), with
    every string redacted."""
    if a.from_snapshot:
        snap = mon_base.load_snapshot(a.from_snapshot, names if a.panel else None)
    else:
        ctx = mon_base.Ctx(root=a.root.resolve(), store=a.store, url=a.url, key_file=a.key_file)
        snap = mon_base.snapshot(ctx, names, a.timeout, kept)
    return mon_view.scrub(snap)


def shared_age(path):
    """Seconds since the shared snapshot at `path` was written, or None when there is none."""
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


@contextlib.contextmanager
def shared_lock(path, timeout):
    """Hold the refresh lock of the shared snapshot for the block: the file `<path>.lock` made by exclusive create (the same
    on every OS) and removed on exit. A waiter polls; a lock older than `SHARED_LOCK_STALE_S` is a crashed run's and is
    removed. Past `timeout` seconds of waiting the block runs without the lock, so a stuck file never blocks a pane."""
    lock = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + timeout
    held = False
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            held = True
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > SHARED_LOCK_STALE_S:
                    lock.unlink()
                    continue
            except OSError:
                continue
        except OSError:
            break
        if time.monotonic() > deadline:
            break
        time.sleep(SHARED_POLL_S)
    try:
        yield
    finally:
        if held:
            with contextlib.suppress(OSError):
                lock.unlink()


def shared(a, names):
    """The snapshot of `--once --shared` and its age in seconds: the clone's shared snapshot when it is younger than
    `--max-age`, else a fresh one of every panel (age 0), written to the file by a temporary file of this process's own
    under the lock and stamped with the time its run began, so its age counts from when its data was read. A pane that waited on the lock finds the snapshot the holder wrote and serves it, so panes due
    together make one refresh. A snapshot that cannot be read or written is refreshed or served from memory."""
    path = a.root.resolve() / SHARED_FILE

    def fresh_enough():
        age = shared_age(path)
        if age is None or age >= a.max_age:
            return None
        try:
            return mon_base.load_snapshot(path, names if a.panel else None), age
        except ValueError:
            return None

    found = fresh_enough()
    if found:
        return found
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
    with shared_lock(path, a.timeout * len(mon_base.PANELS)):
        found = fresh_enough()
        if found:
            return found
        began = time.time()
        snap = take(argparse.Namespace(**{**vars(a), "panel": None, "from_snapshot": None}), mon_base.PANELS)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(mon_view.render_json(snap), encoding="utf-8", newline="\n")
            os.utime(tmp, (began, began))
            os.replace(tmp, path)
        except OSError:
            with contextlib.suppress(OSError):
                tmp.unlink()
        if a.panel:
            snap = {**snap, "panels": {n: p for n, p in snap["panels"].items() if n in names}}
        return snap, 0.0


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


def status(a, out):
    """The status answer for the topic of `--status`: the panels it needs in one snapshot, as lines or, with `--json`, as an
    object. Exit 0: an alert is the answer's content, not a failure of the command."""
    snap = take(a, mon_status.panels(a.status))
    found = mon_status.answer(snap, a.status, a.root.resolve(), a.detail)
    out.write((json.dumps(found, ensure_ascii=False, indent=1) if a.json else "\n".join(found["lines"])) + "\n")
    out.flush()
    return 0


def backtest(a, out):
    """The estimate replayed over the last `--backtest` closed sprints (`mon_eta.backtest`), as lines or, with `--json`, as an
    object of schema 1, topic, sprints and summary. Exit 0."""
    import mon_eta
    import redact
    result = mon_eta.backtest(a.root.resolve(), a.backtest)
    if a.json:
        out.write(json.dumps({"schema": 1, "topic": "sprints", **result}, ensure_ascii=False, indent=1) + "\n")
    else:
        out.write("\n".join(redact.redact(x) for x in mon_eta.backtest_lines(result)) + "\n")
    out.flush()
    return 0


def main(argv=None, out=None):
    out = out or sys.stdout
    args = sys.argv[1:] if argv is None else list(argv)
    if args[:1] == ["--follow"]:
        import kbtail
        return kbtail.main(args[1:], out)
    ap = parser()
    a = ap.parse_args(args)
    if a.follow:
        ap.error("--follow comes first: kbmon.py --follow [--history N] [--once] TARGET")
    if a.status is not None:
        if a.once or a.metrics or a.receipt or a.events or a.split or a.follow:
            ap.error("--status takes only --json beside the snapshot's own options")
        if a.panel:
            ap.error("--status reads the panels its topic needs and takes no --panel")
    if a.backtest is not None and (a.status != "sprints" or a.backtest < 1):
        ap.error("--backtest N (1 or more) needs --status sprints")
    if a.shared and not a.once:
        ap.error("--shared needs --once")
    if a.shared and a.from_snapshot:
        ap.error("--shared reads the sources and takes no --from-snapshot")
    if any(x == "--max-age" or x.startswith("--max-age=") for x in args) and not a.shared:
        ap.error("--max-age needs --shared")
    if a.detail and (a.status != "sprints" or a.backtest is not None):
        ap.error("--detail needs --status sprints and no --backtest")
    if a.since is not None and not a.events:
        ap.error("--since needs --events")
    if a.dry_run and not a.split:
        ap.error("--dry-run needs --split")
    if a.events and (a.panel or a.from_snapshot):
        ap.error("--events reads the sources and takes neither --panel nor --from-snapshot")
    names = tuple(dict.fromkeys(a.panel)) if a.panel else (mon_receipt.DEFAULT_PANELS if a.receipt else mon_base.PANELS)
    names = tuple(n for n in mon_base.PANELS if n in names)
    try:
        if a.backtest is not None:
            return backtest(a, out)
        if a.status is not None:
            return status(a, out)
        if a.split:
            return mon_split.split(Path(__file__).resolve(), a.root.resolve(), split_args(a), a.dry_run, out=out)
        if a.events:
            ctx = mon_base.Ctx(root=a.root.resolve(), store=a.store, url=a.url, key_file=a.key_file)
            out.write(mon_events.render(ctx, a.since) + "\n")
            out.flush()
            return 0
        if a.receipt:
            out.write(json.dumps(mon_receipt.receipt(take(a, names), names), ensure_ascii=False) + "\n")
            out.flush()
            return 0
        if a.json or a.once or a.metrics:
            note = None
            if a.shared:
                snap, age = shared(a, names)
                note = "shared snapshot, %s" % ("refreshed now" if age == 0 else f"{round(age)} s old (max age {a.max_age:g} s)")
            else:
                snap = take(a, names)
            if a.metrics:
                text = mon_export.render(snap)
            else:
                text = mon_view.render_json(snap) if a.json else frame_text(snap, a, colour(a, out, False), out, 1)
            out.write(text + "\n" + (note + "\n" if note else ""))
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
