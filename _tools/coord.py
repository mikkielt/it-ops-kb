#!/usr/bin/env python3
"""Claims, leases, compare-and-swap and events on a local SQLite store (stdlib only), usable by any agent. Docs: kb/_self/tools.md.

  coord.py claim KEY --ttl SECONDS [--holder NAME]   create KEY if it is absent, held for SECONDS; prints the key, its
                                                     holder and the holder's token (exit 1, naming the holder, when a
                                                     live lease already holds KEY)
  coord.py renew KEY --token T [--ttl SECONDS]       extend the lease of the holder of T (SECONDS: the claim's own)
  coord.py release KEY --token T                     drop the lease of the holder of T
  coord.py get KEY                                   print KEY's holder, value and revision (exit 1 when absent)
  coord.py put KEY --value V --revision N            write V only while KEY is at revision N (an absent key is at
                                                     revision 0); prints the new revision (exit 1 when KEY moved on)
  coord.py list [--prefix P]                         print every live key that starts with P
  coord.py post --kind K --field NAME=VALUE ...      add an event; prints its sequence number as seq (exit 2 for a kind
                                                     off the closed list or a value that is not a short id)
  coord.py digest --key K ... --lines N              print at most N lines (plain text, not JSON), newest first, of the
                                                     live intents and claims that overlap a key K (repeatable)
  coord.py wait --since N --timeout S                print the events after sequence N, blocking until one arrives or
                                                     S seconds pass

The store is one SQLite file: `--store PATH` (before or after the command), else the environment variable
KB_COORD_STORE; with neither the command is refused (exit 2). Every command prints one JSON object on stdout with
sorted keys. A claimed key is a row with a holder, a token, a ttl and an expiry; `put` writes the row's value and
raises its revision by one (a claim starts at revision 1). A lease whose expiry has passed counts as absent: the
next write on that key removes the row, value included, and `get` and `list` skip it. A row `put` made has no lease
and stays until a claim-and-release or a later `put` replaces it. The token is shown once, to the claimer; `get`,
`list` and a refused claim never print it. Every write runs in one `BEGIN IMMEDIATE` transaction, so two processes
racing on one key serialise on SQLite's lock and exactly one wins; a writer waits up to 30 seconds for the lock.

An event is a kind from a closed list (claim, release, fact_added, gap_opened, dup_of, lesson, heartbeat) and up to
eight fields, each NAME=VALUE: an event carries references only, so a VALUE is an id of at most 120 characters of
letters, digits and `_ . : / # @ -` (a source id, a `path:line` fact key, a QK answer id, a backlog item id, a pack
handle) and free text is refused. `post` numbers events 1, 2, 3 ... in the store; `wait` polls the store twice a second
for events past N and prints `events`, `last` (the highest sequence it returned, else N) and `timed_out`; a wait whose
S passes with no event exits 0 with `timed_out` true, and a post from any other process on the same store wakes it.

Two kinds carry a session's plan: `intent` (fields session, item, topic, touch; at least one of item, topic and touch;
item and topic hold a comma-separated list of ids, touch of globs with * and ?, up to 120 characters) and `progress`
(fields item and state, state one of working, blocked, done). `digest` is the one command that prints text, not JSON:
one line per live intent (posted within a day, its items not all done by a later progress event) or live claim (a
held lease) with a value that overlaps a key (equal, a directory-style prefix either way, or a glob match either
way), newest first, cut at N lines; with nothing to show it prints nothing.

Exit codes: 0 done; 1 the command's condition failed (key held, wrong or expired token, revision moved, key
absent); 2 a bad argument or no store.
"""
import argparse
import json
import os
import re
import secrets
import sqlite3
import sys
import time
from fnmatch import fnmatchcase
from pathlib import Path

BUSY_SECONDS = 30
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS entries ("
    "key TEXT PRIMARY KEY, value TEXT, revision INTEGER NOT NULL, holder TEXT, token TEXT, ttl REAL, expires REAL)"
)
EVENTS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    "seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, fields TEXT NOT NULL, at REAL NOT NULL)"
)
KINDS = ("claim", "release", "fact_added", "gap_opened", "dup_of", "lesson", "heartbeat", "intent", "progress")
KIND_FIELDS = {"intent": ("session", "item", "topic", "touch"), "progress": ("item", "state")}
STATES = ("working", "blocked", "done")
FIELD_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
FIELD_VALUE = re.compile(r"[A-Za-z0-9_.:/#@-]{1,120}")
ID_LIST = re.compile(r"(?=.{1,120}$)[A-Za-z0-9_.:/#@-]+(,[A-Za-z0-9_.:/#@-]+)*")
GLOB_LIST = re.compile(r"(?=.{1,120}$)[A-Za-z0-9_.:/#@*?-]+(,[A-Za-z0-9_.:/#@*?-]+)*")
LIST_VALUES = {("intent", "item"): ID_LIST, ("intent", "topic"): ID_LIST, ("intent", "touch"): GLOB_LIST}
INTENT_SECONDS = 86400
MAX_FIELDS = 8
POLL_SECONDS = 0.05
LIVE = "(expires IS NULL OR expires > ?)"
PUBLIC = "key, value, revision, holder, expires"


class Refused(Exception):
    """A command's condition failed: the JSON to print and the exit code."""

    def __init__(self, body, code=1):
        super().__init__(body.get("error", ""))
        self.body = body
        self.code = code


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=BUSY_SECONDS, isolation_level=None)
    con.row_factory = sqlite3.Row
    return con


class Tx:
    """One write transaction: BEGIN IMMEDIATE takes SQLite's write lock before the first read."""

    def __init__(self, path):
        self.con = connect(path)

    def __enter__(self):
        self.con.execute("BEGIN IMMEDIATE")
        self.con.execute(SCHEMA)
        self.con.execute(EVENTS_SCHEMA)
        return self.con

    def __exit__(self, kind, _value, _trace):
        self.con.execute("ROLLBACK" if kind else "COMMIT")
        self.con.close()
        return False


def row_json(row):
    out = {k: row[k] for k in row.keys()}
    if out.get("expires") is not None:
        out["expires"] = round(out["expires"], 3)
    return out


def live_row(con, key, now):
    """The key's row inside a write transaction, an expired lease removed first (it counts as absent)."""
    con.execute("DELETE FROM entries WHERE key = ? AND expires IS NOT NULL AND expires <= ?", (key, now))
    return con.execute("SELECT * FROM entries WHERE key = ?", (key,)).fetchone()


def claim(args, now):
    holder = args.holder or "anonymous"
    token = secrets.token_hex(16)
    with Tx(args.store) as con:
        row = live_row(con, args.key, now)
        if row is not None:
            raise Refused({"ok": False, "key": args.key, "holder": row["holder"], "revision": row["revision"],
                           "expires": row_json(row)["expires"],
                           "error": f"{args.key} is held by {row['holder'] or 'no lease (a put value)'}"})
        con.execute("INSERT INTO entries (key, value, revision, holder, token, ttl, expires) VALUES (?, NULL, 1, ?, ?, ?, ?)",
                    (args.key, holder, token, args.ttl, now + args.ttl))
    return {"ok": True, "key": args.key, "holder": holder, "token": token, "ttl": args.ttl, "revision": 1,
            "expires": round(now + args.ttl, 3)}


def held_by(con, key, token, now):
    row = live_row(con, key, now)
    if row is None:
        raise Refused({"ok": False, "key": key, "error": f"{key} is not claimed (absent or its lease expired)"})
    if row["token"] is None or not secrets.compare_digest(row["token"], token):
        raise Refused({"ok": False, "key": key, "holder": row["holder"],
                       "error": f"the token does not hold {key}: it is held by {row['holder'] or 'no lease'}"})
    return row


def renew(args, now):
    with Tx(args.store) as con:
        row = held_by(con, args.key, args.token, now)
        ttl = args.ttl if args.ttl is not None else row["ttl"]
        con.execute("UPDATE entries SET ttl = ?, expires = ? WHERE key = ?", (ttl, now + ttl, args.key))
    return {"ok": True, "key": args.key, "holder": row["holder"], "ttl": ttl, "expires": round(now + ttl, 3)}


def release(args, now):
    with Tx(args.store) as con:
        row = held_by(con, args.key, args.token, now)
        con.execute("DELETE FROM entries WHERE key = ?", (args.key,))
    return {"ok": True, "key": args.key, "holder": row["holder"], "released": True}


def get(args, now):
    con = connect(args.store)
    try:
        con.execute(SCHEMA)
        row = con.execute(f"SELECT {PUBLIC} FROM entries WHERE key = ? AND {LIVE}", (args.key, now)).fetchone()
    finally:
        con.close()
    if row is None:
        raise Refused({"ok": False, "key": args.key, "revision": 0, "error": f"{args.key} is absent"})
    return {"ok": True, **row_json(row)}


def put(args, now):
    with Tx(args.store) as con:
        row = live_row(con, args.key, now)
        have = row["revision"] if row is not None else 0
        if have != args.revision:
            raise Refused({"ok": False, "key": args.key, "revision": have,
                           "error": f"{args.key} is at revision {have}, not {args.revision}"})
        if row is None:
            con.execute("INSERT INTO entries (key, value, revision) VALUES (?, ?, 1)", (args.key, args.value))
        else:
            con.execute("UPDATE entries SET value = ?, revision = revision + 1 WHERE key = ?", (args.value, args.key))
    return {"ok": True, "key": args.key, "value": args.value, "revision": have + 1}


def listing(args, now):
    con = connect(args.store)
    try:
        con.execute(SCHEMA)
        rows = con.execute(f"SELECT {PUBLIC} FROM entries WHERE {LIVE} ORDER BY key", (now,)).fetchall()
    finally:
        con.close()
    return {"ok": True, "prefix": args.prefix, "entries": [row_json(r) for r in rows if r["key"].startswith(args.prefix)]}


def parse_fields(pairs, kind=""):
    """NAME=VALUE pairs to a dict; a bad name, a value that is no short id or a repeated name is refused (exit 2).
    The intent kind's item, topic and touch fields hold a comma-separated list of ids, touch's of globs."""
    fields = {}
    if len(pairs) > MAX_FIELDS:
        raise Refused({"ok": False, "error": f"at most {MAX_FIELDS} fields, got {len(pairs)}"}, 2)
    for pair in pairs:
        name, equals, value = pair.partition("=")
        if not equals or not FIELD_NAME.fullmatch(name):
            raise Refused({"ok": False, "error": f"a field is NAME=VALUE with NAME of lowercase letters, digits, _: {pair[:40]!r}"}, 2)
        if name in fields:
            raise Refused({"ok": False, "error": f"field {name} is given twice"}, 2)
        if not LIST_VALUES.get((kind, name), FIELD_VALUE).fullmatch(value):
            raise Refused({"ok": False, "error": f"field {name}: a value is an id of 1 to 120 characters of letters, digits and "
                                                 "_ . : / # @ - (no spaces); events carry references, not free text"
                                                 + (" (a comma-separated list of ids here, of globs with * ? for touch)"
                                                    if (kind, name) in LIST_VALUES else "")}, 2)
        fields[name] = value
    return fields


def check_kind(kind, fields):
    """The closed field names (and, for progress, the closed states) of the intent and progress kinds."""
    names = KIND_FIELDS.get(kind)
    if names is None:
        return
    extra = sorted(set(fields) - set(names))
    if extra:
        raise Refused({"ok": False, "error": f"{kind} takes only the fields {', '.join(names)}, not {', '.join(extra)}"}, 2)
    if kind == "intent" and not set(fields) & {"item", "topic", "touch"}:
        raise Refused({"ok": False, "error": "an intent names at least one of item, topic and touch"}, 2)
    if kind == "progress":
        if "item" not in fields or fields.get("state") not in STATES:
            raise Refused({"ok": False, "error": f"progress takes item and state, state one of {', '.join(STATES)}"}, 2)


def event_json(row):
    return {"seq": row["seq"], "kind": row["kind"], "fields": json.loads(row["fields"]), "at": round(row["at"], 3)}


def post(args, now):
    if args.kind not in KINDS:
        raise Refused({"ok": False, "error": f"unknown kind {args.kind[:40]!r}: one of {', '.join(KINDS)}"}, 2)
    fields = parse_fields(args.field, args.kind)
    check_kind(args.kind, fields)
    with Tx(args.store) as con:
        seq = con.execute("INSERT INTO events (kind, fields, at) VALUES (?, ?, ?)",
                          (args.kind, json.dumps(fields, sort_keys=True, ensure_ascii=False), now)).lastrowid
    return {"ok": True, "seq": seq, "kind": args.kind, "fields": fields}


def wait(args, now):
    deadline = time.monotonic() + args.timeout
    con = connect(args.store)
    try:
        con.execute(EVENTS_SCHEMA)
        while True:
            rows = con.execute("SELECT * FROM events WHERE seq > ? ORDER BY seq", (args.since,)).fetchall()
            if rows or time.monotonic() >= deadline:
                break
            time.sleep(min(POLL_SECONDS, max(deadline - time.monotonic(), 0)))
    finally:
        con.close()
    return {"ok": True, "since": args.since, "last": rows[-1]["seq"] if rows else args.since,
            "events": [event_json(r) for r in rows], "timed_out": not rows}


def overlaps(a, b):
    """Two keys overlap when they are equal, one is a directory-style prefix of the other or one globs the other."""
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/") or fnmatchcase(a, b) or fnmatchcase(b, a)


def one_line(text, limit=80):
    return re.sub(r"\s+", "_", str(text))[:limit]


def digest(args, now):
    """The live intents and claims that overlap the keys, newest first, as at most N lines of text (no JSON)."""
    con = connect(args.store)
    try:
        con.execute(SCHEMA)
        con.execute(EVENTS_SCHEMA)
        claims = con.execute("SELECT key, holder, ttl, expires FROM entries WHERE holder IS NOT NULL AND expires > ?", (now,)).fetchall()
        events = con.execute("SELECT seq, fields, kind, at FROM events WHERE kind IN ('intent', 'progress') ORDER BY seq").fetchall()
    finally:
        con.close()
    state = {}
    found = []
    for row in events:
        fields = json.loads(row["fields"])
        if row["kind"] == "progress":
            state[fields.get("item")] = (row["seq"], fields.get("state"))
            continue
        if now - row["at"] > INTENT_SECONDS:
            continue
        items = [i for i in fields.get("item", "").split(",") if i]
        found.append((row["at"], row["seq"], fields, items))
    lines = []
    for at, seq, fields, items in found:
        if items and all(i in state and state[i][0] > seq and state[i][1] == "done" for i in items):
            continue
        values = [v for n in ("item", "topic", "touch") for v in fields.get(n, "").split(",") if v]
        if not any(overlaps(v, k) for v in values for k in args.key):
            continue
        text = "intent " + " ".join(f"{n}={fields[n]}" for n in KIND_FIELDS["intent"] if n in fields)
        now_states = sorted({state[i][1] for i in items if i in state})
        lines.append((at, text + (f" state={'/'.join(now_states)}" if now_states else "")))
    for row in claims:
        if any(overlaps(row["key"], k) for k in args.key):
            lines.append((row["expires"] - row["ttl"],
                          f"claim {one_line(row['key'])} holder={one_line(row['holder'])} left={int(row['expires'] - now)}s"))
    lines.sort(key=lambda pair: pair[0], reverse=True)
    return "\n".join(text for _at, text in lines[:args.lines])


def positive(text):
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be above 0")
    return value


def not_negative(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def seconds(text):
    value = float(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def build_parser():
    store = argparse.ArgumentParser(add_help=False)
    store.add_argument("--store", default=argparse.SUPPRESS, help="the SQLite file (else KB_COORD_STORE)")
    parser = argparse.ArgumentParser(prog="coord.py", description=__doc__.split("\n", 1)[0], parents=[store])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("claim", parents=[store])
    p.add_argument("key")
    p.add_argument("--ttl", type=positive, required=True, help="lease length in seconds")
    p.add_argument("--holder", help="name shown to a second claimer (default anonymous)")
    p = sub.add_parser("renew", parents=[store])
    p.add_argument("key")
    p.add_argument("--token", required=True)
    p.add_argument("--ttl", type=positive, help="new lease length in seconds (default: the claim's own)")
    p = sub.add_parser("release", parents=[store])
    p.add_argument("key")
    p.add_argument("--token", required=True)
    p = sub.add_parser("get", parents=[store])
    p.add_argument("key")
    p = sub.add_parser("put", parents=[store])
    p.add_argument("key")
    p.add_argument("--value", required=True)
    p.add_argument("--revision", type=not_negative, required=True, help="the revision the key must still be at (absent: 0)")
    p = sub.add_parser("list", parents=[store])
    p.add_argument("--prefix", default="")
    p = sub.add_parser("post", parents=[store])
    p.add_argument("--kind", required=True, help="one of " + ", ".join(KINDS))
    p.add_argument("--field", action="append", default=[], metavar="NAME=VALUE", help="an id field, repeatable")
    p = sub.add_parser("digest", parents=[store])
    p.add_argument("--key", action="append", required=True, metavar="K", help="an item id, topic key or path; repeatable")
    p.add_argument("--lines", type=not_negative, required=True, help="at most this many lines")
    p = sub.add_parser("wait", parents=[store])
    p.add_argument("--since", type=not_negative, required=True, help="the highest sequence the caller has seen (0: all)")
    p.add_argument("--timeout", type=seconds, required=True, help="seconds to block when no event is past SINCE")
    return parser


COMMANDS = {"claim": claim, "renew": renew, "release": release, "get": get, "put": put, "list": listing,
            "post": post, "digest": digest, "wait": wait}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    args = build_parser().parse_args(argv)
    args.store = getattr(args, "store", None) or os.environ.get("KB_COORD_STORE")
    if not args.store:
        print("coord.py: no store: pass --store PATH or set KB_COORD_STORE", file=sys.stderr)
        return 2
    try:
        body, code = COMMANDS[args.command](args, time.time()), 0
    except Refused as refused:
        body, code = refused.body, refused.code
        print(f"coord.py: {body['error']}", file=sys.stderr)
    except sqlite3.Error as error:
        print(f"coord.py: store {args.store}: {error}", file=sys.stderr)
        return 2
    if isinstance(body, str):
        if body:
            print(body)
    else:
        print(json.dumps(body, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
