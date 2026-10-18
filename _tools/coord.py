#!/usr/bin/env python3
"""Claims, leases, compare-and-swap and events on a local SQLite store (stdlib only), usable by any agent. Docs: kb/_self/tools.md.

  coord.py claim KEY --ttl SECONDS [--holder NAME] [--budget USD]
                                                     lease KEY for SECONDS, creating it if it is absent; prints the key,
                                                     its holder and the holder's token (exit 1, naming the holder, when a
                                                     live lease already holds KEY); --budget is the USD the operator
                                                     approved for the claimed item, so KEY is then an item id
  coord.py renew KEY --token T [--ttl SECONDS]       extend the lease of the holder of T (SECONDS: the claim's own)
  coord.py release KEY --token T                     drop the lease of the holder of T
  coord.py get KEY                                   print KEY's holder, value and revision (exit 1 when absent)
  coord.py put KEY --value V --revision N [--token T] write V only while KEY is at revision N (an absent key is at
                                                     revision 0); prints the new revision (exit 1 when KEY moved on);
                                                     a key a live lease holds takes the put only with the holder's T
                                                     (exit 1 without it), and the lease goes on
  coord.py list [--prefix P]                         print, as a JSON array, every live key that starts with P
  coord.py post --kind K --field NAME=VALUE ...      add an event; prints its sequence number as seq (exit 2 for a kind
                                                     off the closed list or a value that is not a short id)
  coord.py digest --key K ... --lines N              print at most N lines (plain text, not JSON), newest first, of the
                                                     live intents and claims that overlap a key K (repeatable)
  coord.py wait --since N --timeout S                print the events after sequence N, blocking until one arrives or
                                                     S seconds pass
  coord.py dedup QUESTION [--holder NAME] [--ttl S]  claim the question's lack terms that no overlapping live claim
                                                     covers (local store only, not through --url)

The store is one SQLite file: `--store PATH` (before or after the command), else the environment variable
KB_COORD_STORE, else `kb-coord/coord.sqlite` in the common git directory of the clone that holds this script (shared by
its worktrees, and the store the coord hook uses); a script in no git clone with neither is refused (exit 2). Every command prints one JSON object on stdout with
sorted keys. A claimed key is a row with a holder, a token, a ttl and an expiry; `put` writes the row's value and
raises its revision by one (a claim of an absent key starts at revision 1). The end of a lease, a `release` or an expiry,
clears the row's holder, token and expiry and keeps its value and revision: `get` and `list` show the key with no
holder, and a claim of a key that holds no live lease (one a `put` made included) succeeds and leaves its value and
revision as they were. A row no `put` wrote has nothing to keep, so the end of its lease removes it and the key is
absent. The token is shown once, to the claimer; `get`,
`list` and a refused claim never print it. Every write runs in one `BEGIN IMMEDIATE` transaction, so two processes
racing on one key serialise on SQLite's lock and exactly one wins; a writer waits up to 30 seconds for the lock.

A claim made with `--budget USD` carries the budget the operator approved for the item its key names. `list` prints,
beside each live claim, `budget_usd` (null without one), `spend_usd` (what the query log's work sidecars hold for the
item and its descendants, read through `bl_cost.spend_usd`, the reader `backlog.py cost` uses, and priced with
`bench_core.PRICE`; null without a budget) and `over_budget` (true when the spend is above the budget), and `digest`
adds `over budget` to the line of such a claim. Nothing is stopped: the claim, its renewals and its holder go on.

An event is a kind from a closed list (claim, release, fact_added, gap_opened, dup_of, lesson, heartbeat) and up to
eight fields, each NAME=VALUE: an event carries references only, so a VALUE is an id of at most 120 characters of
letters, digits and `_ . : / # @ -` (a source id, a `path:line` fact key, a QK answer id, a backlog item id, a pack
handle) and free text is refused. `post` numbers events 1, 2, 3 ... in the store; `wait` polls the store twice a second
for events past N and prints `events`, `last` (the highest sequence it returned, else N) and `timed_out`; a wait whose
S passes with no event exits 0 with `timed_out` true, and a post from any other process on the same store wakes it.

Two kinds carry a session's plan: `intent` (fields session, item, topic, touch; at least one of item, topic and touch;
item and topic hold a comma-separated list of ids, touch of globs with * and ?, up to 120 characters) and `progress`
(fields item and state, state one of working, blocked, done). `digest` is the one command that prints text, not JSON:
one line per live intent (posted within a day, its items not all done by a later progress event, and, when it names a
session, that session's presence lease `session/<id>` still held: a release or an expiry drops the session's intents) or
live claim (a held lease) with a value that overlaps a key (equal, a directory-style prefix either way, or a glob match either
way), newest first, cut at N lines; with nothing to show it prints nothing.

`dedup` runs `rag.py pack QUESTION` and takes its fingerprint: the anchor topic (the first article's path without `.md`,
else `unanchored`) and the terms of its `kb lacks:` lines, lowercased and mapped to their canonical form by
`_tools/aliases.csv` and each root's `_retrieval/aliases.csv`. A live claim of another holder (a `research:TOPIC:TERM` key;
the same holder under a name other than `anonymous` is itself, never an overlap) overlaps when it is on the same topic and
shares at least half of the smaller of the two term sets; the shared terms count as covered. In one transaction `dedup`
claims every term not covered (one lease, one token, shown once, for the keys in `claimed`) and prints `topic`, `terms`,
`uncovered`, `overlaps` (each: `holder`, `topic`, shared `terms`), `held` (each uncovered term another live claim
already holds, below the overlap threshold: `term`, `holder`; `dedup` claims no key a live claim holds), `claimed`,
`ttl`, `token` (only when it claimed) and `seq` (the newest event, for `wait --since`). A question every term of which
is covered prints `uncovered` empty and claims nothing; exit 0 either way.

  coord.py serve --bind [HOST:]PORT --keys DIR       answer every command above as a JSON request over HTTP, on the store
  coord.py --url URL --key-file PATH COMMAND ...     send COMMAND to such a server instead of a local store

`serve` binds 127.0.0.1 unless --bind names a host (port 0 picks a free port) and prints `coord.py: serving URL` as
its first line. DIR holds one file per operator, named for the operator and holding that operator's token; the server
reads DIR on every request, so removing a file revokes that operator at once. A client sends its own token, read from
the file --key-file names (never from argv or the environment), as `Authorization: Bearer TOKEN` in `POST /v1/run`
with the body {"argv": [the command and its arguments]}; the server answers 401 to a token no file holds (or two
files hold) and runs the command on its store otherwise, answering {"code": N, "body": ...}, where code and body are
what the command would have printed and exited with. The server adds the operator's name as the field `operator` to
each event it records (a client cannot set it) and never serves `--store`. `wait` is a long-poll: the request is held
until an event arrives or S seconds pass. The request carries the token in the clear, so reach a server beyond
loopback through a TLS front end (an https URL is accepted).

Exit codes: 0 done; 1 the command's condition failed (key held, wrong or expired token, revision moved, key
absent); 2 a bad argument, no store, or a server that refuses (401) or cannot be reached.
"""
import argparse
import csv
import http.client
import http.server
import json
import math
import os
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from fnmatch import fnmatchcase
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUSY_SECONDS = 30
PACK_SECONDS = 120
RESEARCH = "research:"  # a research claim's key: research:<anchor topic>:<lack term>
DEDUP_SECONDS = 3600
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS entries ("
    "key TEXT PRIMARY KEY, value TEXT, revision INTEGER NOT NULL, holder TEXT, token TEXT, ttl REAL, expires REAL, budget REAL)"
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
SESSION_LEASE = "session/"  # the presence lease of a session: key session/<id>, held while the session lives
MAX_FIELDS = 8
POLL_SECONDS = 0.05
OPERATOR_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
BODY_LIMIT = 65536
REQUEST_SECONDS = 60
ENDPOINT = "/v1/run"
LIVE = "(expires IS NULL OR expires > :now OR value IS NOT NULL)"  # a row with a value outlives its lease
PUBLIC = ("key, value, revision, CASE WHEN expires > :now THEN holder END AS holder, "
          "CASE WHEN expires > :now THEN expires END AS expires")


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
        ensure_schema(self.con)
        return self.con

    def __exit__(self, kind, _value, _trace):
        self.con.execute("ROLLBACK" if kind else "COMMIT")
        self.con.close()
        return False


def ensure_schema(con):
    """Both tables, and the `budget` column on a store made before a claim carried one."""
    con.execute(SCHEMA)
    con.execute(EVENTS_SCHEMA)
    if "budget" not in {r[1] for r in con.execute("PRAGMA table_info(entries)")}:
        con.execute("ALTER TABLE entries ADD COLUMN budget REAL")


def row_json(row):
    out = {k: row[k] for k in row.keys()}
    if out.get("expires") is not None:
        out["expires"] = round(out["expires"], 3)
    return out


def end_leases(con, now, key=None):
    """End every lease (of KEY alone, when given) whose expiry has passed: a row holding a value loses its holder,
    token, ttl, expiry and budget and keeps value and revision; a row a claim made and no put wrote is removed."""
    where = "expires IS NOT NULL AND expires <= ?" + (" AND key = ?" if key is not None else "")
    params = (now,) if key is None else (now, key)
    con.execute(f"DELETE FROM entries WHERE value IS NULL AND {where}", params)
    con.execute(f"UPDATE entries SET holder = NULL, token = NULL, ttl = NULL, expires = NULL, budget = NULL WHERE {where}", params)


def live_row(con, key, now):
    """The key's row inside a write transaction, an expired lease ended first (the row then holds no lease)."""
    end_leases(con, now, key)
    return con.execute("SELECT * FROM entries WHERE key = ?", (key,)).fetchone()


def take(con, key, holder, token, ttl, now, budget=None):
    """Lease KEY to HOLDER: a new row at revision 1, else the row that holds no lease, its value and revision kept."""
    con.execute("INSERT INTO entries (key, value, revision, holder, token, ttl, expires, budget) VALUES (?, NULL, 1, ?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET holder = excluded.holder, token = excluded.token, ttl = excluded.ttl, "
                "expires = excluded.expires, budget = excluded.budget",
                (key, holder, token, ttl, now + ttl, budget))
    return con.execute("SELECT revision FROM entries WHERE key = ?", (key,)).fetchone()["revision"]


def holder_name(args):
    """The claim's --holder, else `anonymous`: an id like an event's field value, so a digest line never carries free text."""
    holder = args.holder or "anonymous"
    if not FIELD_VALUE.fullmatch(holder):
        raise Refused({"ok": False, "error": f"--holder is an id of 1 to 120 characters of letters, digits and _ . : / # @ -, not {holder[:40]!r}"}, 2)
    return holder


def claim(args, now):
    holder = holder_name(args)
    if not FIELD_VALUE.fullmatch(args.key):
        raise Refused({"ok": False, "error": f"a claim's key is an id of 1 to 120 characters of letters, digits and _ . : / # @ -, not {args.key[:40]!r}"}, 2)
    budget = getattr(args, "budget", None)
    if budget is not None:
        import bl_base
        if not bl_base.id_re().fullmatch(args.key):
            raise Refused({"ok": False, "key": args.key, "error": f"--budget is for a claim of a backlog item id, not {args.key[:40]!r}"}, 2)
    token = secrets.token_hex(16)
    with Tx(args.store) as con:
        row = live_row(con, args.key, now)
        if row is not None and row["holder"] is not None:
            raise Refused({"ok": False, "key": args.key, "holder": row["holder"], "revision": row["revision"],
                           "expires": row_json(row)["expires"], "error": f"{args.key} is held by {row['holder']}"})
        revision = take(con, args.key, holder, token, args.ttl, now, budget)
    body = {"ok": True, "key": args.key, "holder": holder, "token": token, "ttl": args.ttl, "revision": revision,
            "expires": round(now + args.ttl, 3)}
    if budget is not None:
        body["budget_usd"] = budget
    return body


def held_by(con, key, token, now):
    row = live_row(con, key, now)
    if row is None:
        raise Refused({"ok": False, "key": key, "error": f"{key} is not claimed (absent or its lease expired)"})
    if row["token"] is None or not secrets.compare_digest(row["token"].encode("utf-8"), token.encode("utf-8")):
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
        if row["value"] is None:
            con.execute("DELETE FROM entries WHERE key = ?", (args.key,))
        else:
            con.execute("UPDATE entries SET holder = NULL, token = NULL, ttl = NULL, expires = NULL, budget = NULL WHERE key = ?", (args.key,))
    return {"ok": True, "key": args.key, "holder": row["holder"], "released": True}


def get(args, now):
    con = connect(args.store)
    try:
        con.execute(SCHEMA)
        row = con.execute(f"SELECT {PUBLIC} FROM entries WHERE key = :key AND {LIVE}", {"key": args.key, "now": now}).fetchone()
    finally:
        con.close()
    if row is None:
        raise Refused({"ok": False, "key": args.key, "revision": 0, "error": f"{args.key} is absent"})
    return {"ok": True, **row_json(row)}


def put(args, now):
    with Tx(args.store) as con:
        if args.token is not None:
            row = held_by(con, args.key, args.token, now)
        else:
            row = live_row(con, args.key, now)
            if row is not None and row["holder"] is not None:
                raise Refused({"ok": False, "key": args.key, "holder": row["holder"],
                               "error": f"{args.key} is held by {row['holder']}: put needs the holder's --token"})
        have = row["revision"] if row is not None else 0
        if have != args.revision:
            raise Refused({"ok": False, "key": args.key, "revision": have,
                           "error": f"{args.key} is at revision {have}, not {args.revision}"})
        if row is None:
            con.execute("INSERT INTO entries (key, value, revision) VALUES (?, ?, 1)", (args.key, args.value))
        else:
            con.execute("UPDATE entries SET value = ?, revision = revision + 1 WHERE key = ?", (args.value, args.key))
    return {"ok": True, "key": args.key, "value": args.value, "revision": have + 1}


def spend_of(key):
    """The USD the query log holds for the backlog item KEY (`bl_cost.spend_usd`), on the clone this tool is in."""
    import bl_base
    import bl_cost
    bl_base.load_settings(HERE.parent)
    return round(bl_cost.spend_usd(bl_base.Backlog(HERE.parent), key)[0], 6)


def budget_view(key, budget):
    """{budget_usd, spend_usd, over_budget} of a live claim: null and false for a claim with no budget."""
    if budget is None:
        return {"budget_usd": None, "spend_usd": None, "over_budget": False}
    spend = spend_of(key)
    return {"budget_usd": budget, "spend_usd": spend, "over_budget": spend > budget}


def listing(args, now):
    con = connect(args.store)
    try:
        ensure_schema(con)
        rows = con.execute(f"SELECT {PUBLIC}, CASE WHEN expires > :now THEN budget END AS budget FROM entries "
                           f"WHERE {LIVE} ORDER BY key", {"now": now}).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        if r["key"].startswith(args.prefix):
            out.append({**row_json({k: r[k] for k in r.keys() if k != "budget"}), **budget_view(r["key"], r["budget"])})
    return out


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
    if getattr(args, "operator", None):
        fields["operator"] = args.operator
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
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", re.sub(r"\s+", "_", str(text)))[:limit]


def digest(args, now):
    """The live intents and claims that overlap the keys, newest first, as at most N lines of text (no JSON)."""
    con = connect(args.store)
    try:
        ensure_schema(con)
        claims = con.execute("SELECT key, holder, ttl, expires, budget FROM entries WHERE holder IS NOT NULL AND expires > ?", (now,)).fetchall()
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
    live = {row["key"] for row in claims}
    for at, seq, fields, items in found:
        if "session" in fields and SESSION_LEASE + fields["session"] not in live:
            continue
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
            cost = budget_view(row["key"], row["budget"])
            spent = (f" budget_usd={cost['budget_usd']} spend_usd={cost['spend_usd']}"
                     + (" over budget" if cost["over_budget"] else "")) if row["budget"] is not None else ""
            lines.append((row["expires"] - row["ttl"],
                          f"claim {one_line(row['key'])} holder={one_line(row['holder'])} left={int(row['expires'] - now)}s{spent}"))
    lines.sort(key=lambda pair: pair[0], reverse=True)
    return "\n".join(text for _at, text in lines[:args.lines])


def alias_map():
    """{term: canonical} from the shared product aliases (`_tools/aliases.csv`) and each root's own `aliases.csv`."""
    files = [HERE / "aliases.csv", *sorted((HERE.parent / "kb").glob("*/_retrieval/aliases.csv"))]
    out = {}
    for path in files:
        try:
            with open(path, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    term = " ".join((row.get("term") or "").lower().split())
                    canon = " ".join((row.get("canonical") or "").lower().split())
                    if term and canon:
                        out.setdefault(term, canon)
        except OSError:
            pass
    return out


def fingerprint(question):
    """(anchor topic, lack terms) of the question's pack: the first article's path without `.md` (`unanchored` when
    the pack names none) and the words of its `kb lacks:` lines, lowercased and mapped to their canonical alias."""
    pack = HERE / "rag.py"
    try:
        p = subprocess.run([sys.executable, str(pack), "pack", question, "--format", "concise", "--budget", "300"],
                           capture_output=True, text=True, encoding="utf-8", timeout=PACK_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused({"ok": False, "error": f"the pack of the question did not run: {error.__class__.__name__}"}, 2)
    if p.returncode != 0:
        raise Refused({"ok": False, "error": f"rag.py pack exited {p.returncode}: {p.stderr.strip()[:120]}"}, 2)
    article = re.search(r"^## (\S+?)(?:\.md)?  ", p.stdout, re.M)
    names = alias_map()
    terms = []
    for line in re.findall(r"^kb lacks: (.*\S)\s*$", p.stdout, re.M):
        for word in line.split(","):
            word = " ".join(word.lower().split())
            word = names.get(word, word)
            if word and word != "-" and word not in terms:
                terms.append(word)
    return (article.group(1) if article else "unanchored"), terms


def research_key(topic, term):
    return f"{RESEARCH}{topic}:{term}"


def dedup(args, now):
    """Claim the lack terms of the question's pack that no overlapping live claim covers; name the claims that do.
    A claim on the same anchor topic overlaps when it shares at least half of the smaller lack-set's terms."""
    holder = holder_name(args)
    topic, terms = fingerprint(args.question)
    token = secrets.token_hex(16)
    overlapping, covered, own, taken, others = [], set(), set(), [], []
    with Tx(args.store) as con:
        end_leases(con, now)
        theirs, holders = {}, {}
        for row in con.execute("SELECT key, holder FROM entries WHERE holder IS NOT NULL AND substr(key, 1, ?) = ? ORDER BY key",
                               (len(RESEARCH), RESEARCH)):
            their_topic, _colon, term = row["key"][len(RESEARCH):].partition(":")
            if their_topic != topic:
                continue
            if row["holder"] == holder and holder != "anonymous":
                own.add(term)
            else:
                theirs.setdefault(row["holder"], set()).add(term)
                holders.setdefault(term, row["holder"])
        for who, held in sorted(theirs.items(), key=lambda pair: str(pair[0])):
            shared = [t for t in terms if t in held]
            if shared and len(shared) * 2 >= min(len(terms), len(held)):
                covered.update(shared)
                overlapping.append({"holder": who, "topic": topic, "terms": shared})
        uncovered = [t for t in terms if t not in covered]
        for term in uncovered:
            if term in holders:
                others.append({"term": term, "holder": holders[term]})
            elif term not in own:
                take(con, research_key(topic, term), holder, token, args.ttl, now)
                taken.append(research_key(topic, term))
        last = con.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]
    body = {"ok": True, "topic": topic, "holder": holder, "terms": terms, "uncovered": uncovered, "overlaps": overlapping,
            "held": others, "claimed": taken, "ttl": args.ttl, "seq": last}
    if taken:
        body["token"] = token
    return body


def finite(text):
    value = float(text)
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError("must be a finite number")
    return value


def positive(text):
    value = finite(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be above 0")
    return value


def not_negative(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def seconds(text):
    value = finite(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


class QuietParser(argparse.ArgumentParser):
    """The parser of a request: a bad argument or a help request raises Refused (exit 2) and prints nothing."""

    def _print_message(self, message, file=None):
        pass

    def error(self, message):
        raise Refused({"ok": False, "error": message}, 2)

    def exit(self, status=0, message=None):
        raise Refused({"ok": False, "error": message or "no help is served"}, 2)


def build_parser(parser_class=argparse.ArgumentParser, remote=False):
    """The command line; remote leaves out what a request must not carry (--store, serve, --url, --key-file)."""
    store = argparse.ArgumentParser(add_help=False)
    store.add_argument("--store", default=argparse.SUPPRESS, help="the SQLite file (else KB_COORD_STORE, else the clone's common git directory)")
    parents = [] if remote else [store]
    parser = parser_class(prog="coord.py", description=__doc__.split("\n", 1)[0], parents=parents)
    if not remote:
        parser.add_argument("--url", help="send the command to the server at URL (with --key-file) instead of a local store")
        parser.add_argument("--key-file", help="the file holding this operator's token for --url")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("claim", parents=parents)
    p.add_argument("key")
    p.add_argument("--ttl", type=positive, required=True, help="lease length in seconds")
    p.add_argument("--holder", help="name shown to a second claimer (default anonymous)")
    p.add_argument("--budget", type=positive, help="USD the operator approved for the claimed item (KEY is its id)")
    p = sub.add_parser("renew", parents=parents)
    p.add_argument("key")
    p.add_argument("--token", required=True)
    p.add_argument("--ttl", type=positive, help="new lease length in seconds (default: the claim's own)")
    p = sub.add_parser("release", parents=parents)
    p.add_argument("key")
    p.add_argument("--token", required=True)
    p = sub.add_parser("get", parents=parents)
    p.add_argument("key")
    p = sub.add_parser("put", parents=parents)
    p.add_argument("key")
    p.add_argument("--value", required=True)
    p.add_argument("--revision", type=not_negative, required=True, help="the revision the key must still be at (absent: 0)")
    p.add_argument("--token", help="the holder's token: needed to write a key a live lease holds, refused for a key none holds")
    p = sub.add_parser("list", parents=parents)
    p.add_argument("--prefix", default="")
    p = sub.add_parser("post", parents=parents)
    p.add_argument("--kind", required=True, help="one of " + ", ".join(KINDS))
    p.add_argument("--field", action="append", default=[], metavar="NAME=VALUE", help="an id field, repeatable")
    p = sub.add_parser("digest", parents=parents)
    p.add_argument("--key", action="append", required=True, metavar="K", help="an item id, topic key or path; repeatable")
    p.add_argument("--lines", type=not_negative, required=True, help="at most this many lines")
    p = sub.add_parser("wait", parents=parents)
    p.add_argument("--since", type=not_negative, required=True, help="the highest sequence the caller has seen (0: all)")
    p.add_argument("--timeout", type=seconds, required=True, help="seconds to block when no event is past SINCE")
    if not remote:
        p = sub.add_parser("dedup", parents=parents)
        p.add_argument("question")
        p.add_argument("--holder", help="name shown to a later question that overlaps this one (default anonymous)")
        p.add_argument("--ttl", type=positive, default=DEDUP_SECONDS, help=f"lease length in seconds (default {DEDUP_SECONDS})")
        p = sub.add_parser("serve", parents=parents)
        p.add_argument("--bind", required=True, metavar="[HOST:]PORT", help="host (default 127.0.0.1) and port (0: a free one)")
        p.add_argument("--keys", required=True, metavar="DIR", help="one file per operator, named for it, holding its token")
    return parser


COMMANDS = {"claim": claim, "renew": renew, "release": release, "get": get, "put": put, "list": listing,
            "post": post, "digest": digest, "wait": wait, "dedup": dedup}


def run(args, now):
    """One parsed command on args.store: its body and exit code."""
    try:
        return COMMANDS[args.command](args, now), 0
    except Refused as refused:
        return refused.body, refused.code


def emit(body, code):
    if code and isinstance(body, dict):
        print(f"coord.py: {body.get('error', 'refused')}", file=sys.stderr)
    if isinstance(body, str):
        if body:
            print(body)
    else:
        print(json.dumps(body, sort_keys=True, ensure_ascii=False))


def authenticate(keys_dir, header):
    """The operator a request comes from, else None: the one file in keys_dir (named for the operator) that holds the
    bearer token in the Authorization header. Every request reads the directory again, so removing a file revokes
    its operator; a token that two files hold names no one. An OAuth2 bearer-token check replaces or joins this."""
    scheme, _space, token = (header or "").partition(" ")
    token = token.strip().encode("utf-8")
    if scheme.lower() != "bearer" or not token:
        return None
    found = []
    try:
        names = sorted(os.listdir(keys_dir))
    except OSError:
        return None
    for name in names:
        path = Path(keys_dir) / name
        if not OPERATOR_NAME.fullmatch(name) or not path.is_file():
            continue
        try:
            secret = path.read_text(encoding="utf-8").strip().encode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if secret and secrets.compare_digest(secret, token):
            found.append(name)
    return found[0] if len(found) == 1 else None


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "coord"
    protocol_version = "HTTP/1.0"
    timeout = 30

    def log_message(self, *_args):
        pass

    def reply(self, status, payload, headers=()):
        data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def refuse(self, status, text, headers=()):
        self.reply(status, {"ok": False, "error": text}, headers)

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.refuse(400, "bad Content-Length")
        if not 0 <= size <= BODY_LIMIT:
            return self.refuse(413, f"a request is at most {BODY_LIMIT} bytes")
        raw = self.rfile.read(size)
        operator = authenticate(self.server.keys, self.headers.get("Authorization"))
        if operator is None:
            return self.refuse(401, "unknown or revoked token", [("WWW-Authenticate", "Bearer")])
        if self.path != ENDPOINT:
            return self.refuse(404, f"only POST {ENDPOINT}")
        try:
            argv = json.loads(raw.decode("utf-8"))["argv"]
            if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            return self.refuse(400, 'the body is {"argv": [strings]}')
        try:
            args = build_parser(QuietParser, True).parse_args(argv)
            args.store, args.operator = self.server.store, operator
            body, code = run(args, time.time())
        except Refused as refused:
            body, code = refused.body, refused.code
        except sqlite3.Error as error:
            body, code = {"ok": False, "error": f"store: {error.__class__.__name__}"}, 2
        self.reply({0: 200, 1: 409}.get(code, 400), {"code": code, "body": body})

    def do_other(self):
        self.refuse(405, f"only POST {ENDPOINT}", [("Allow", "POST")])

    do_GET = do_HEAD = do_PUT = do_DELETE = do_PATCH = do_other


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, keys, store):
        self.keys, self.store = keys, store
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, Handler)


def split_bind(text):
    """[HOST:]PORT to (host, port); the host is 127.0.0.1 unless named."""
    host, _colon, port = text.rpartition(":")
    try:
        number = int(port)
    except ValueError:
        number = -1
    if not 0 <= number <= 65535:
        raise Refused({"ok": False, "error": f"--bind is [HOST:]PORT with PORT 0 to 65535, not {text[:40]!r}"}, 2)
    return host.strip("[]") or "127.0.0.1", number


def serve(args):
    if not Path(args.keys).is_dir():
        print(f"coord.py: --keys {args.keys} is not a directory", file=sys.stderr)
        return 2
    try:
        host, port = split_bind(args.bind)
        httpd = Server((host, port), args.keys, args.store)
    except Refused as refused:
        print(f"coord.py: {refused.body['error']}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"coord.py: cannot bind {args.bind}: {error}", file=sys.stderr)
        return 2
    name, port = httpd.server_address[:2]
    print(f"coord.py: serving http://{f'[{name}]' if ':' in name else name}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def send(url, key_file, argv):
    """Run the command on the server at url as the operator whose token key_file holds."""
    parsed = build_parser(argparse.ArgumentParser, True).parse_args(argv)
    try:
        token = Path(key_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        print(f"coord.py: key file {key_file}: {error}", file=sys.stderr)
        return 2
    if not token or not token.isascii() or not token.isprintable() or " " in token:
        print(f"coord.py: key file {key_file} holds no token (one line of printable ASCII, no spaces)", file=sys.stderr)
        return 2
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        print(f"coord.py: --url is http://HOST:PORT or https://HOST[:PORT], not {url[:60]!r}", file=sys.stderr)
        return 2
    where = f"{parts.scheme}://{parts.netloc.rpartition('@')[2]}"
    seconds_to_wait = REQUEST_SECONDS + (parsed.timeout if parsed.command == "wait" else 0)
    connect_to = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    try:
        conn = connect_to(parts.hostname, parts.port, timeout=seconds_to_wait)
        try:
            conn.request("POST", parts.path.rstrip("/") + ENDPOINT, json.dumps({"argv": argv}),
                         {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            response = conn.getresponse()
            status, data = response.status, response.read()
        finally:
            conn.close()
    except (OSError, http.client.HTTPException) as error:
        print(f"coord.py: cannot reach {where}: {error}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(data.decode("utf-8"))
        code, body = payload["code"], payload["body"]
    except (ValueError, KeyError, TypeError):
        try:
            text = json.loads(data.decode("utf-8")).get("error", "")
        except (ValueError, AttributeError):
            text = ""
        print(f"coord.py: {where} answered HTTP {status}{': ' + text if text else ''}", file=sys.stderr)
        return 2
    emit(body, code)
    return code


def default_store():
    """kb-coord/coord.sqlite in the common git directory of the clone that holds this script, which its worktrees share
    (the store the coord hook uses); None when the script is in no git clone."""
    root = HERE.parent
    try:
        p = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"], capture_output=True, text=True,
                           encoding="utf-8", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    common = p.stdout.strip()
    if p.returncode != 0 or not common:
        return None
    return str(Path(root, common, "kb-coord", "coord.sqlite"))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    argv = sys.argv[1:] if argv is None else list(argv)
    remote = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    remote.add_argument("--url")
    remote.add_argument("--key-file")
    named, rest = remote.parse_known_args(argv)
    if named.url or named.key_file:
        if not (named.url and named.key_file):
            print("coord.py: --url and --key-file go together", file=sys.stderr)
            return 2
        return send(named.url, named.key_file, rest)
    args = build_parser().parse_args(argv)
    args.store = getattr(args, "store", None) or os.environ.get("KB_COORD_STORE") or default_store()
    if not args.store:
        print("coord.py: no store: pass --store PATH or set KB_COORD_STORE (this script's directory is in no git "
              "clone, which would hold the default)", file=sys.stderr)
        return 2
    if args.command == "serve":
        return serve(args)
    try:
        body, code = run(args, time.time())
    except sqlite3.Error as error:
        print(f"coord.py: store {args.store}: {error}", file=sys.stderr)
        return 2
    emit(body, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
