#!/usr/bin/env python3
"""kbtail: follow one Claude Code session's transcript live in a terminal, redacted and cut (stdlib only).

  kbtail.py [--history N] [--once] TARGET

TARGET is a transcript path, or a session id: the newest `<id>.jsonl` under the Claude config directory's projects
(`kbusage.find_transcript`). It prints the last N lines (default 20) and, unless `--once`, each line appended later within
2 seconds of its write until interrupted; a half-written last line is read once its newline is there.

A line is the time (local, HH:MM:SS), a kind and a text:
  prompt   a user prompt's first line
  reply    an assistant text's first line
  tool     a tool call's name and key input: a Bash command's first line, a path relative to the session's cwd (or `~`)
  result   a tool result's first non-empty line, after `!` when the call failed
Thinking is never shown. Every text passes `redact.redact`; a text that the leak scan (`kbcommon.leak_hits`) still hits
after it prints as `[withheld: KIND]`. Control characters are dropped, a command is cut at 100 characters, a result at 80,
and each line at the terminal's columns less one (COLUMNS, else the terminal's size, else 80), as kbmon's view does.

An entry of an unknown type, or a line that is not a JSON object, is skipped and counted; the types Claude Code writes
that are no conversation (attachment, mode, system, summary and the like) are ignored uncounted. `--once` ends with
`kbtail: skipped N` on stderr. While following, the process waits on coord's event log (`coord.wait`, a store that exists:
KB_COORD_STORE, else the project's) and otherwise sleeps; either way it reads only the bytes appended since its last
read. It writes no file. Exit codes: 0 done (also an interrupt), 2 a bad argument or a TARGET with no transcript.
`kbmon.py --follow ARGS` runs it with ARGS.

Answers: what a session is doing right now, as a redacted line for each tool call, result and message
Use: python3 _tools/kbtail.py [--history N] [--once] TARGET
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import kbcommon
import kbusage
import mon_view
import ql_capture
import redact

HISTORY = 20  # lines printed before following
WAKE_S = 1.0  # longest wait between two reads of a followed file
COMMAND_CUT = 100  # characters of a tool call's key input
RESULT_CUT = 80  # characters of a tool result's line
READ_CAP = 4000  # characters of a text that are redacted; its first line is within them
KNOWN = mon_view.LazyKnown()  # the public root is read only when a rule needs it (some seconds), not at the first line
DISPLAYED = ("user", "assistant")
IGNORED = frozenset(("attachment", "mode", "permission-mode", "last-prompt", "ai-title", "file-history-snapshot",
                     "system", "summary", "cost-state", "atis-latch"))
IGNORED_PREFIX = ("api-request",)
INPUT_KEYS = ("file_path", "notebook_path", "path", "command", "pattern", "url", "query", "skill", "description",
              "prompt", "name")
PATH_KEYS = ("file_path", "notebook_path", "path")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def clean(text):
    """`text` without control characters (no escape sequence reaches the terminal); tabs become spaces."""
    return CONTROL.sub("", text.replace("\t", " "))


def safe(text):
    """The first non-empty line of `text`, home shown as `~`, redacted, `[withheld: KIND]` when the leak scan still hits."""
    text = clean(text[:READ_CAP]).replace(str(Path.home()), "~")
    text = redact.redact(text, KNOWN)
    hits = kbcommon.leak_hits(text)
    if hits:
        return f"[withheld: {hits[0][0]}]"
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def cut(text, n):
    return text if len(text) <= n else text[:n - 1] + "…"


def relative(value, cwd):
    """A path under the session's cwd as a relative one; anything else as it is."""
    if cwd and isinstance(value, str):
        try:
            return Path(value).relative_to(cwd).as_posix()
        except ValueError:
            pass
    return value


def key_input(name, inp, cwd):
    """The one value of a tool call's input that says what it does."""
    if not isinstance(inp, dict):
        return ""
    for key in INPUT_KEYS:
        value = inp.get(key)
        if isinstance(value, str) and value.strip():
            return relative(value, cwd) if key in PATH_KEYS else value
    return next((v for v in inp.values() if isinstance(v, str) and v.strip()), "")


def block_text(content):
    """The text of a message's content or a tool result's: a string, or the `text` of its text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def stamp(entry):
    try:
        return datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except (KeyError, AttributeError, ValueError, OSError, OverflowError):
        return "--:--:--"


def rows_of(entry):
    """[(kind, text)] an entry shows: a message's text, its tool calls and its tool results; thinking is none."""
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    cwd = entry.get("cwd") if isinstance(entry.get("cwd"), str) else None
    user = entry.get("type") == "user"
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    rows = []
    for b in content if isinstance(content, list) else ():
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text" and isinstance(b.get("text"), str):
            rows.append(("prompt" if user else "reply", safe(b["text"])))
        elif b.get("type") == "tool_use":
            name = clean(str(b.get("name", "tool")))[:40]
            rows.append(("tool", f"{name} {cut(safe(key_input(name, b.get('input'), cwd)), COMMAND_CUT)}".rstrip()))
        elif b.get("type") == "tool_result":
            mark = "! " if b.get("is_error") else ""
            rows.append(("result", mark + cut(safe(block_text(b.get("content"))), RESULT_CUT)))
    return rows


def parse(line):
    """([line to print], counted): what one transcript line shows, and whether it is skipped (not an object, or of a type
    that is neither shown nor known to be no conversation)."""
    entry = kbusage.loads(line)
    if entry is None:
        return [], True
    kind = entry.get("type")
    if kind in DISPLAYED:
        when = stamp(entry)
        return [f"{when} {k:<6} {t}" for k, t in rows_of(entry)], False
    if kind in IGNORED or (isinstance(kind, str) and kind.startswith(IGNORED_PREFIX)):
        return [], False
    return [], True


def fit(text, columns):
    return cut(text, max(columns - 1, 20))


def history(path, count):
    """(lines, skipped, end): the last `count` lines the whole lines of the file show, and the offset after its last
    newline, where following starts. Read from the end in growing windows."""
    size = path.stat().st_size
    window = kbusage.BLOCK
    while True:
        start = max(0, size - window)
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(size - start)
        cut_at = data.rfind(b"\n")
        if cut_at < 0 and start > 0:
            window *= 4
            continue
        whole = data[:cut_at + 1]
        pieces = whole.split(b"\n")[:-1]
        if start > 0 and pieces:
            pieces = pieces[1:]  # the first piece may begin before the window
        shown, skipped = [], 0
        for raw in reversed(pieces):
            if not raw.strip():
                continue
            got, counted = parse(raw.decode("utf-8", "replace"))
            skipped += counted
            shown = got + shown
            if len(shown) >= count:
                break
        if len(shown) >= count or start == 0:
            return (shown[-count:] if count else []), skipped, start + cut_at + 1
        window *= 4


def wake(since, store, timeout=WAKE_S):
    """Wait up to `timeout` seconds for a coord event after `since` (without a store: just sleep); the cursor to wait from
    next."""
    if store is None:
        time.sleep(timeout)
        return since
    import coord
    args = argparse.Namespace(store=store, since=since, timeout=timeout, kind=None, item=None, pid=None)
    try:
        return coord.wait(args, time.time)["last"]
    except Exception:  # a store that cannot be read: wait as without one
        time.sleep(timeout)
        return since


def coord_store():
    """The coord store file that exists, else None (a missing one is not made)."""
    import coord
    path = os.environ.get("KB_COORD_STORE") or coord.default_store()
    return str(path) if path and Path(path).is_file() else None


def follow(path, offset, columns, out):
    """Print the lines appended after `offset` as they become whole, until interrupted."""
    store = coord_store()
    since = wake(0, store, 0)
    rest = b""
    while True:
        try:
            size = path.stat().st_size
            if size < offset:  # the file was replaced
                offset, rest = 0, b""
            if size > offset:
                with open(path, "rb") as f:
                    f.seek(offset)
                    data = f.read(size - offset)
                offset += len(data)
                rest += data
                cut_at = rest.rfind(b"\n")
                if cut_at >= 0:
                    whole, rest = rest[:cut_at + 1], rest[cut_at + 1:]
                    for raw in whole.split(b"\n"):
                        if raw.strip():
                            for line in parse(raw.decode("utf-8", "replace"))[0]:
                                out.write(fit(line, columns) + "\n")
                    out.flush()
        except OSError:
            pass
        since = wake(since, store)


def resolve(target):
    """The transcript path for TARGET (a file, else a session id), or None."""
    if Path(target).is_file():
        return Path(target)
    if ql_capture.SAFE_SESSION.fullmatch(target):
        return kbusage.find_transcript(target)
    return None


def count(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def main(argv=None, out=None, err=None):
    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(prog="kbtail.py", description=__doc__.split("\n\n")[0].splitlines()[0])
    ap.add_argument("target", metavar="TARGET", help="a transcript path or a session id")
    ap.add_argument("--history", type=count, default=HISTORY, metavar="N", help="lines printed first (default %d)" % HISTORY)
    ap.add_argument("--once", action="store_true", help="print the history and stop")
    a = ap.parse_args(argv)
    path = resolve(a.target)
    if path is None:
        print(f"kbtail: no transcript for {a.target}", file=err)
        return 2
    columns = shutil.get_terminal_size().columns
    try:
        lines, skipped, end = history(path, a.history)
        for line in lines:
            out.write(fit(line, columns) + "\n")
        out.flush()
        if a.once:
            print(f"kbtail: skipped {skipped}", file=err)
            return 0
        follow(path, end, columns, out)
    except BrokenPipeError:
        return 0
    except OSError as e:
        print(f"kbtail: {type(e).__name__}", file=err)
        return 2
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main())
