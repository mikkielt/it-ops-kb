"""`backlog.py own`: the record of what this clone's tools make and leave behind (kb/_self/backlog.md, Leftovers; kb/_self/tools.md).

  own PATH --class worktree|sandbox|scratch [--item ID] [--sprint SP] [--session ID]   record the directory
  own PID  --class process [--item ID] [--sprint SP] [--session ID]                   record the process
  own TARGET --class C --drop                                                          clear the record

A record is one coord key, `own/<class>/<digest>`, whose value is a JSON object: the `path` (normalised) or the `pid`, the
class, the item, sprint and session when given, and `at`, the time it was recorded in seconds since the epoch. The digest is the first 16
hex digits of the sha256 of the normalised path or of the pid's decimal text, so one directory is one key however it was
spelled (`norm_path`: realpath, then no `\\\\?\\` prefix, normcase, one case for a drive letter), on every platform. The
coord store is the one `coord.py` finds (`--store`, else KB_COORD_STORE, else the clone's common git directory), shared by
the clone's worktrees. coord keeps no delete: `--drop` writes an empty value, which readers skip (`recorded`).

`record_owner` is the one writer: `dispatch` records the worker's worktree, scratch directory and pid through it, `bench
multi` its sandbox, and the sprint skill's run and review steps their worktrees with the `own` command. A record is a claim of
nothing: it says who made the path or process, never that it may be removed. Exit codes: 0 recorded or dropped, 1 coord
refused or did not run, 2 a bad request.

Standard library only; imports `bl_base` and `bl_cli`, never `backlog` (a layer rule). It registers its own subcommand
when imported, so `backlog.py` carries only the import."""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import bl_cli
from bl_base import Refused, Rejected, say

COORD = Path(__file__).resolve().parent / "coord.py"
CLASSES = ("worktree", "sandbox", "scratch", "process")
PREFIX = "own/"  # the coord keys of the records: own/<class>/<digest>
DIGEST_LENGTH = 16
COORD_SECONDS = 60
EXTENDED = "\\\\?\\"  # the Windows extended-length prefix
EXTENDED_UNC = EXTENDED + "UNC\\"
DRIVE = re.compile(r"[A-Za-z]:")


def strip_extended(path):
    """PATH without the `\\\\?\\` prefix (`\\\\?\\UNC\\host\\share` is `\\\\host\\share`)."""
    if path.startswith(EXTENDED_UNC):
        return "\\\\" + path[len(EXTENDED_UNC):]
    return path[len(EXTENDED):] if path.startswith(EXTENDED) else path


def norm_path(path):
    """The one spelling of a directory every record is keyed by: realpath, without the extended-length prefix, normcase,
    and one (lower) case for a drive letter. A trailing separator, a symlink, a relative path and (on Windows) a case
    or slash difference all give the same text."""
    text = strip_extended(os.path.realpath(strip_extended(os.fspath(path))))
    text = os.path.normcase(text)
    return text[0].lower() + text[1:] if DRIVE.match(text) else text


def subject(cls, target):
    """({"path": P} or {"pid": N}, the text the key's digest is of) for the TARGET of class CLS. Raises Rejected."""
    if cls not in CLASSES:
        raise Rejected(f"own: --class is one of {', '.join(CLASSES)}, not {cls!r}")
    if cls == "process":
        if not re.fullmatch(r"[0-9]{1,10}", str(target)) or int(target) < 1:
            raise Rejected(f"own: a process is recorded by its pid, a positive whole number, not {str(target)[:40]!r}")
        return {"pid": int(target)}, str(int(target))
    if not str(target):
        raise Rejected("own: a path is needed")
    path = norm_path(target)
    return {"path": path}, path


def owner_key(cls, ident):
    """The coord key of the record of IDENT (the normalised path, or the pid's text) of class CLS."""
    return f"{PREFIX}{cls}/{hashlib.sha256(ident.encode('utf-8')).hexdigest()[:DIGEST_LENGTH]}"


def run_coord(*args):
    """(exit code, the JSON object coord.py printed or None, its last stderr line) of one coord.py command."""
    try:
        p = subprocess.run([sys.executable, str(COORD), *args], capture_output=True, text=True, encoding="utf-8",
                           stdin=subprocess.DEVNULL, timeout=COORD_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        return 2, None, f"coord.py did not run: {error.__class__.__name__}"
    try:
        body = json.loads(p.stdout)
    except ValueError:
        body = None
    lines = [x.strip() for x in p.stderr.splitlines() if x.strip()]
    return p.returncode, body, lines[-1] if lines else ""


def put_value(key, text):
    """Write TEXT as the value of KEY, a new key or its next revision; Refused when coord does not take it."""
    for _try in range(3):
        code, body, err = run_coord("get", key)
        if code not in (0, 1):
            raise Refused(f"own: cannot read {key}: {err or 'coord.py exited ' + str(code)}")
        revision = body.get("revision", 0) if isinstance(body, dict) else 0
        code, body, err = run_coord("put", key, f"--value={text}", "--revision", str(revision))
        if code == 0:
            return
        if code != 1:
            raise Refused(f"own: cannot write {key}: {err or 'coord.py exited ' + str(code)}")
    raise Refused(f"own: {key} keeps moving on")


def record_owner(cls, target, item=None, sprint=None, session=None, drop=False):
    """Record TARGET (a path, or a pid for the class `process`) as made by this clone's tools, with the ITEM, SPRINT and
    SESSION that made it (each left out when empty) and the time; with DROP clear the record instead. Returns the coord key.
    Raises Rejected for a bad class or target and Refused when coord does not take the write."""
    ident, text = subject(cls, target)
    key = owner_key(cls, text)
    if drop:
        code, body, _err = run_coord("get", key)
        if code != 1 and not (code == 0 and isinstance(body, dict) and not body.get("value")):
            put_value(key, "")  # a key coord does not hold, or already dropped, has nothing to clear
        return key
    value = {"class": cls, **ident, "at": int(time.time())}
    value.update({k: v for k, v in (("item", item), ("sprint", sprint), ("session", session)) if v})
    put_value(key, json.dumps(value, sort_keys=True))
    return key


def recorded(entry):
    """The record in a `coord.py list` entry (its JSON value as a dict), None for a key that is no live record: a
    value that is empty (dropped) or not a JSON object."""
    try:
        value = json.loads(entry.get("value") or "")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def cmd_own(bl, a):
    key = record_owner(a.cls, a.target, a.item, a.sprint, a.session, a.drop)
    say(f"own: {'dropped' if a.drop else 'recorded'} {a.cls} {a.target} as {key}")
    return 0


def args_own(p):
    p.add_argument("target", metavar="PATH|PID", help="the directory, or for --class process the pid")
    p.add_argument("--class", dest="cls", required=True, choices=CLASSES, help="what the target is")
    p.add_argument("--item", help="the backlog item the target was made for")
    p.add_argument("--sprint", help="the sprint it was made in")
    p.add_argument("--session", help="the session that made it")
    p.add_argument("--drop", action="store_true", help="clear the record instead of making it")


bl_cli.register("own", cmd_own, args_own, help="record a worktree, sandbox, scratch directory or process this clone's tools made")
