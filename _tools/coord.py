#!/usr/bin/env python3
"""Claims, leases and compare-and-swap on a local SQLite store (stdlib only), usable by any agent. Docs: kb/_self/tools.md.

  coord.py claim KEY --ttl SECONDS [--holder NAME]   create KEY if it is absent, held for SECONDS; prints the key, its
                                                     holder and the holder's token (exit 1, naming the holder, when a
                                                     live lease already holds KEY)
  coord.py renew KEY --token T [--ttl SECONDS]       extend the lease of the holder of T (SECONDS: the claim's own)
  coord.py release KEY --token T                     drop the lease of the holder of T
  coord.py get KEY                                   print KEY's holder, value and revision (exit 1 when absent)
  coord.py put KEY --value V --revision N            write V only while KEY is at revision N (an absent key is at
                                                     revision 0); prints the new revision (exit 1 when KEY moved on)
  coord.py list [--prefix P]                         print every live key that starts with P

The store is one SQLite file: `--store PATH` (before or after the command), else the environment variable
KB_COORD_STORE; with neither the command is refused (exit 2). Every command prints one JSON object on stdout with
sorted keys. A claimed key is a row with a holder, a token, a ttl and an expiry; `put` writes the row's value and
raises its revision by one (a claim starts at revision 1). A lease whose expiry has passed counts as absent: the
next write on that key removes the row, value included, and `get` and `list` skip it. A row `put` made has no lease
and stays until a claim-and-release or a later `put` replaces it. The token is shown once, to the claimer; `get`,
`list` and a refused claim never print it. Every write runs in one `BEGIN IMMEDIATE` transaction, so two processes
racing on one key serialise on SQLite's lock and exactly one wins; a writer waits up to 30 seconds for the lock.

Exit codes: 0 done; 1 the command's condition failed (key held, wrong or expired token, revision moved, key
absent); 2 a bad argument or no store.
"""
import argparse
import json
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path

BUSY_SECONDS = 30
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS entries ("
    "key TEXT PRIMARY KEY, value TEXT, revision INTEGER NOT NULL, holder TEXT, token TEXT, ttl REAL, expires REAL)"
)
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
    return parser


COMMANDS = {"claim": claim, "renew": renew, "release": release, "get": get, "put": put, "list": listing}


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
    print(json.dumps(body, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
