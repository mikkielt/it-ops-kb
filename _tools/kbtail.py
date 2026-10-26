#!/usr/bin/env python3
"""kbtail: follow Claude Code sessions' transcripts live in a terminal, redacted and cut (stdlib only).

  kbtail.py [--history N] [--once] TARGET
  kbtail.py [--history N] [--once] [--root DIR] [--item ID] [--role ROLE] [ITEM]

TARGET is a transcript path, or a session id: the newest `<id>.jsonl` under the Claude config directory's projects
(`kbusage.find_transcript`). It prints the last N lines (default 20) and, unless `--once`, each line appended later within
2 seconds of its write until interrupted; a half-written last line is read once its newline is there.

With no TARGET, or an item id (ITEM, as `--item` keeps), it follows every live Claude Code session of the clone at `--root`
(default: the one this script is in), its main checkout and each worktree, as `mon_sessions.live_sessions` finds and binds them.
Each line starts with the session's role and item (`worker ST-3k2m5n7q`, `interactive`; the sessions' label is added when two
sessions have the same words, never a raw session id) in a column as wide as the longest; a subagent's lines
(`<session>/subagents/agent-*.jsonl`) are indented under its session's. `--item ID` and `--role ROLE` keep the matching
sessions only. A followed session whose process ends gets a line `HH:MM:SS ended` within 2 seconds and the others go on. The
session list is read again when the coord store has changed (5 seconds apart at most), after a session ended and every 30
seconds, for sessions that began since. At most 16 sessions are followed, the rest named in one line. `--history N` is each
file's.

A line is the time (local, HH:MM:SS), a kind and a text:
  prompt   a user prompt's first line
  reply    an assistant text's first line
  tool     a tool call's name and key input: a Bash command's first line, a path relative to the session's cwd (or `~`)
  result   a tool result's first non-empty line, after `!` when the call failed
Thinking is never shown. Every text passes `redact.redact` with none of the public root's names allowed (reading them takes seconds), so it redacts
more than the query log does; a text that the leak scan (`kbcommon.leak_hits`) still hits
after it prints as `[withheld: KIND]`. Control characters are dropped, a command is cut at 100 characters, a result at 80,
and each line at the terminal's columns less one (COLUMNS, else the terminal's size, else 80), as kbmon's view does.

An entry of an unknown type, or a line that is not a JSON object, is skipped and counted; the types Claude Code writes
that are no conversation (attachment, mode, system, summary and the like) are ignored uncounted. `--once` ends with
`kbtail: skipped N` on stderr. While following, the process waits on the stat of coord's store file (a store that exists:
KB_COORD_STORE, else the project's; it opens no connection, so a lock another process holds does not delay a read) and
otherwise sleeps; either way it reads only the bytes appended since its last read. A file replaced by another (a new
identity, a smaller size or other first bytes) shows its last `--history` lines, and what is appended after them. It writes no file. Exit codes: 0 done (also an interrupt), 2 a bad argument or a TARGET with no transcript.
`kbmon.py --follow ARGS` runs it with ARGS.

Answers: what a session, or every live session of the clone, is doing right now, as a redacted line for each tool call, result and message
Use: python3 _tools/kbtail.py [--history N] [--once] [--root DIR] [--item ID] [--role ROLE] [TARGET]
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import kbcommon
import kbusage
import ql_capture
import redact

HISTORY = 20  # lines printed before following
WAKE_S = 1.0  # longest wait between two reads of a followed file
STORE_POLL_S = 0.05  # seconds between two looks at the coord store file's stat
HEAD_BYTES = 1024  # first bytes of a followed file kept to tell a replacement from an append
MAX_SESSIONS = 16 # sessions followed at once; the rest are named in one line
SCAN_S = 30  # seconds after which the live sessions are listed again
SCAN_MIN_S = 5  # the least seconds between two lists a change of the coord store asks for
SUBAGENTS_SHOWN = 4  # the newest subagent files of a session whose history is printed
INDENT = "  "  # a subagent's lines are indented by this under its session's
ITEM_ID = re.compile(r"[A-Z]{2}-[a-z2-7]{8}")
COMMAND_CUT = 100  # characters of a tool call's key input
RESULT_CUT = 80  # characters of a tool result's line
READ_CAP = 4000  # characters of a text that are redacted; its first line is within them
KNOWN = redact.scan_known(())  # nothing of the public root is read (some seconds of CPU): a display may redact more than the query log
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
            name = cut(safe(str(b.get("name", "tool"))) or "tool", 40)
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


def signature(store):
    """What the store file's stat shows (modification time and size of it and its write-ahead log), else None. It opens no
    connection, so another process holding the store's write lock does not hold this back."""
    sig = []
    for suffix in ("", "-wal"):
        try:
            st = os.stat(store + suffix)
            sig.append((st.st_mtime_ns, st.st_size))
        except OSError:
            sig.append(None)
    return tuple(sig)


def wake(since, store, timeout=WAKE_S):
    """Wait up to `timeout` seconds for the coord store to change after `since` (without a store: just sleep); the cursor to
    wait from next."""
    if store is None:
        time.sleep(timeout)
        return since
    end = time.monotonic() + timeout
    while True:
        now = signature(store)
        if now != since or time.monotonic() >= end:
            return now
        time.sleep(min(STORE_POLL_S, max(end - time.monotonic(), 0)))


def coord_store():
    """The coord store file that exists, else None (a missing one is not made)."""
    import coord
    path = os.environ.get("KB_COORD_STORE") or coord.default_store()
    return str(path) if path and Path(path).is_file() else None


def identify(path):
    """(identity, first bytes) of the file at PATH, as they tell a later read that the file was replaced, not appended to;
    taken before the file is read, so a replacement between that read and the next one is seen."""
    try:
        st = path.stat()
        with open(path, "rb") as f:
            return (st.st_dev, st.st_ino), f.read(HEAD_BYTES)
    except OSError:
        return None, b""


def mark(offset, known):
    """The read position at OFFSET of the file `identify` returned KNOWN for: [offset, rest of a half-written line, identity,
    first bytes]."""
    return [offset, b"", known[0], known[1][:offset]]


def replaced(path, state, size):
    """Whether PATH is no longer the file STATE was read from: another identity, a smaller size, or other first bytes."""
    offset, _, ident, head = state
    st = path.stat()
    if size < offset or (ident is not None and ident != (st.st_dev, st.st_ino)):
        return True
    if not head:
        return False
    with open(path, "rb") as f:
        return f.read(len(head)) != head


def read_new(path, state, count):
    """[lines to print]: what the whole lines appended to PATH after the position STATE holds show (STATE is updated; its
    rest holds the bytes of a half-written last line). A file that was replaced by another, smaller or larger, shows its last
    COUNT lines, as at the start, and following goes on after them."""
    size = path.stat().st_size
    if replaced(path, state, size):
        known = identify(path)
        lines, _, end = history(path, count)
        state[:] = mark(end, known)
        return lines
    offset, rest = state[0], state[1]
    lines = []
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
                    lines += parse(raw.decode("utf-8", "replace"))[0]
        if len(state[3]) < HEAD_BYTES:
            state[3] = identify(path)[1][:offset]
    state[0], state[1] = offset, rest
    return lines


def follow(path, state, columns, out, count=HISTORY):
    """Print the lines appended after the read position STATE (`mark`'s) as they become whole, until interrupted."""
    store = coord_store()
    since = wake(0, store, 0)
    while True:
        try:
            lines = read_new(path, state, count)
            for line in lines:
                out.write(fit(line, columns) + "\n")
            if lines:
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


class Followed:
    """A live session being followed: its `live_sessions` row, its transcript and, for that and each subagent's, the read
    position {path: [offset, rest]}."""

    def __init__(self, row, transcript):
        self.row = row
        self.transcript = transcript
        self.files = {}


def subagent_files(transcript):
    """The subagent transcripts of the session whose transcript is TRANSCRIPT: `<session>/subagents/agent-*.jsonl`, oldest
    first."""
    try:
        found = list(transcript.with_suffix("").joinpath("subagents").glob("agent-*.jsonl"))
        return sorted(found, key=lambda p: (p.stat().st_mtime, str(p)))
    except OSError:
        return []


def tags(followed):
    """{pid: the words that name a session}: its role and item, with its label (else its pid) added when another followed
    session has the same words, never a raw session id."""
    words = {pid: " ".join(w for w in (f.row["role"], f.row["item"]) if w) for pid, f in followed.items()}
    same = Counter(words.values())
    return {pid: w if same[w] == 1 else f"{w} {followed[pid].row['label'] or 'pid ' + str(pid)}" for pid, w in words.items()}


def prefixed(followed, pid, subagent, line, columns):
    """LINE of the followed session PID behind its tag (as wide as the longest), a subagent's indented, within COLUMNS."""
    names = tags(followed)
    width = max(len(n) for n in names.values())
    return fit(f"{names[pid]:<{width}}  {INDENT if subagent else ''}{line}", columns)


def alive(pid):
    """Whether process PID runs (a cheap signal-0 test where the host has one)."""
    import coord
    if os.name != "posix":
        return coord.process_runs(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def wanted(root, item, role):
    """The `live_sessions` rows of the clone at ROOT that have a session id and match ITEM and ROLE (None keeps all)."""
    import mon_sessions
    return [r for r in mon_sessions.live_sessions(root)
            if r["session"] and item in (None, r["item"]) and role in (None, r["role"])]


def scan(root, item, role, followed, count):
    """Follow the live sessions that began since the last scan, up to MAX_SESSIONS: ([(time, pid, subagent, line)] of the
    history of each new session's files, how many lines were skipped, the tags of those left out)."""
    shown, skipped, over = [], 0, []
    for row in wanted(root, item, role):
        if row["pid"] in followed:
            continue
        transcript = kbusage.find_transcript(row["session"])
        if transcript is None:
            continue
        if len(followed) >= MAX_SESSIONS:
            over.append(" ".join(w for w in (row["role"], row["item"]) if w))
            continue
        f = followed[row["pid"]] = Followed(row, transcript)
        subs = subagent_files(transcript)
        for path, sub in [(transcript, False)] + [(p, True) for p in subs]:
            keep = count if not sub or path in subs[-SUBAGENTS_SHOWN:] else 0
            known = identify(path)
            try:
                lines, bad, end = history(path, keep)
            except OSError:
                continue
            f.files[path] = mark(end, known)
            skipped += bad
            shown += [(line[:8], row["pid"], sub, line) for line in lines]
    return sorted(shown, key=lambda x: x[0]), skipped, over


def drain(followed, pid, count=HISTORY):
    """[(pid, subagent, line)] appended to the files of the followed session PID since the last read, new subagent files
    included (read from their start); a file replaced by another shows its last COUNT lines."""
    f = followed[pid]
    for path in subagent_files(f.transcript):
        if path not in f.files:
            f.files[path] = mark(0, identify(path))
    out = []
    for path, state in list(f.files.items()):
        try:
            lines = read_new(path, state, count)
        except OSError:
            continue
        out += [(pid, path != f.transcript, line) for line in lines]
    return out


def show(followed, shown, over, columns, out):
    """Write the history lines SHOWN (`scan`'s list) and one line naming the sessions OVER the limit."""
    for _, pid, sub, line in shown:
        out.write(prefixed(followed, pid, sub, line, columns) + "\n")
    if over:
        out.write(fit(f"kbtail: {len(over)} more sessions not followed: {', '.join(over)}", columns) + "\n")


def follow_all(a, columns, out):
    """Print the history, then follow the live sessions of the clone at a.root until interrupted (the module doc says how)."""
    followed, last, over_shown = {}, None, []
    store = coord_store()
    since = wake(0, store, 0)
    rescan = True
    while True:
        now = time.monotonic()
        if rescan or now - last >= SCAN_S:
            rescan = False
            try:
                shown, _, over = scan(a.root, a.item, a.role, followed, a.history)
            except Exception:  # noqa: BLE001 - a list that fails once is tried again at the next scan
                shown, over = [], over_shown
            last = time.monotonic()
            show(followed, shown, over if over != over_shown else [], columns, out)
            over_shown = over
        for pid in list(followed):
            for who, sub, line in drain(followed, pid, a.history):
                out.write(prefixed(followed, who, sub, line, columns) + "\n")
        for pid in [p for p in followed if not alive(p)]:
            for who, sub, line in drain(followed, pid, a.history):
                out.write(prefixed(followed, who, sub, line, columns) + "\n")
            out.write(prefixed(followed, pid, False, f"{time.strftime('%H:%M:%S')} ended", columns) + "\n")
            del followed[pid]
            rescan = True
        out.flush()
        moved = wake(since, store)
        if moved != since and time.monotonic() - last >= SCAN_MIN_S:
            rescan = True
        since = moved


def count(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def main_all(a, out, err):
    """Follow every live session of the clone (a.root) that a.item and a.role keep; 0 or 2."""
    columns = shutil.get_terminal_size().columns
    try:
        if a.once:
            followed = {}
            shown, skipped, over = scan(a.root, a.item, a.role, followed, a.history)
            show(followed, shown, over, columns, out)
            out.flush()
            print(f"kbtail: skipped {skipped}", file=err)
            return 0
        follow_all(a, columns, out)
    except BrokenPipeError:
        return 0
    except OSError as e:
        print(f"kbtail: {type(e).__name__}", file=err)
        return 2
    except KeyboardInterrupt:
        pass
    return 0


def main(argv=None, out=None, err=None):
    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(prog="kbtail.py", description=__doc__.split("\n\n")[0].splitlines()[0])
    ap.add_argument("target", metavar="TARGET", nargs="?", help="a transcript path or a session id; an item id as --item; none: every live session")
    ap.add_argument("--history", type=count, default=HISTORY, metavar="N", help="lines printed first (default %d)" % HISTORY)
    ap.add_argument("--once", action="store_true", help="print the history and stop")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, metavar="DIR",
                    help="the clone whose live sessions are followed (default: the one this script is in)")
    ap.add_argument("--item", metavar="ID", help="keep the sessions working on this item")
    ap.add_argument("--role", metavar="ROLE", help="keep the sessions of this role (worker, interactive, ...)")
    a = ap.parse_args(argv)
    if a.target is None or (ITEM_ID.fullmatch(a.target) and not Path(a.target).is_file()):
        if a.target and a.item not in (None, a.target):
            print(f"kbtail: {a.target} and --item {a.item} name different items", file=err)
            return 2
        a.item = a.target or a.item
        return main_all(a, out, err)
    if a.item or a.role:
        print("kbtail: --item and --role keep live sessions: give no TARGET, or an item id", file=err)
        return 2
    path = resolve(a.target)
    if path is None:
        print(f"kbtail: no transcript for {a.target}", file=err)
        return 2
    columns = shutil.get_terminal_size().columns
    try:
        known = identify(path)
        lines, skipped, end = history(path, a.history)
        for line in lines:
            out.write(fit(line, columns) + "\n")
        out.flush()
        if a.once:
            print(f"kbtail: skipped {skipped}", file=err)
            return 0
        follow(path, mark(end, known), columns, out, a.history)
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
