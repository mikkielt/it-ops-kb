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
  coord.py list --by-operator [--prefix P]           print {"operators": [{operator, claims, budget}]}: the live claims
                                                     under P per operator, read from the holders behind serve
  coord.py post --kind K --field NAME=VALUE ...      add an event (kinds incl. ask, answer); prints its sequence number as seq
                                                     (exit 2 for a kind off the closed list or a value that is not a short id)
  coord.py transition run/ITEM --to STATE [--field NAME=VALUE ...]
                                                     move ITEM's run state to STATE when the state table allows it from the
                                                     state the key holds (an absent key holds none): writes the state, raises
                                                     the revision and posts a progress event (item, state, fields exit, gates,
                                                     step), in one transaction; a move the table does not allow exits 1,
                                                     naming the state and the states it may move to, and writes nothing
  coord.py digest --key K ... --lines N              print at most N lines (plain text, not JSON), newest first, of the
                                                     live intents and claims that overlap a key K (repeatable)
  coord.py wait --since N --timeout S [--kind KIND] [--item IDS] [--pid PID ...]
                                                     print the events after sequence N, blocking until one arrives or
                                                     S seconds pass; --kind keeps one kind, --item the events whose
                                                     item field is one of IDS (comma-separated); --pid (repeatable,
                                                     local store only) also ends the wait when that process has ended
  coord.py dedup QUESTION [--holder NAME] [--topic PATH] [--token T] [--ttl S] [--code REPO:PATH[#SYMBOL] ...]
                                                     claim the question's lack terms (and each --code target) that no
                                                     overlapping live claim covers (through --url too: the server runs
                                                     the pack on its own kb)

The store is one SQLite file: `--store PATH` (before or after the command), else the environment variable
KB_COORD_STORE, else `kb-coord/coord.sqlite` in the common git directory of the project (CLAUDE_PROJECT_DIR, else the
working directory's clone) when that is not the clone that holds this script, else of the clone that holds this script (shared by
its worktrees, and the store the coord hook uses; read from `.git` where git cannot run); a script in no git clone with neither, run outside a git clone, is refused (exit 2). Every command prints one JSON object on stdout with
sorted keys. A claimed key is a row with a holder, a token, a ttl and an expiry; `put` writes the row's value and
raises its revision by one (a claim of an absent key starts at revision 1). The end of a lease, a `release` or an expiry,
clears the row's holder, token and expiry and keeps its value and revision: `get` and `list` show the key with no
holder, and a claim of a key that holds no live lease (one a `put` made included) succeeds and leaves its value and
revision as they were. A row no `put` wrote has nothing to keep, so the end of its lease removes it and the key is
absent. The token is shown once, to the claimer; `get`,
`list` and a refused claim never print it. Every write runs in one `BEGIN IMMEDIATE` transaction, so two processes
racing on one key serialise on SQLite's lock and exactly one wins; a writer waits up to 30 seconds for the lock and reads the time (a lease's start, an expiry's test, an event's `at`) once it holds it, so a lease runs its full length from the moment it was taken.

A claim made with `--budget USD` carries the budget the operator approved for the item its key names. `list` prints,
beside each live claim, `budget_usd` (null without one), `spend_usd` (what the query log's work sidecars hold for the
item and its descendants, read through `bl_cost.spend_usd`, the reader `backlog.py cost` uses, and priced with
`bench_core.PRICE`; null without a budget) and `over_budget` (true when the spend is above the budget), and `digest`
adds `over budget` to the line of such a claim. Nothing is stopped: the claim, its renewals and its holder go on.

An event is a kind from a closed list (claim, release, dedup, fact_added, code_added, gap_opened, dup_of, lesson, heartbeat, intent, progress, ask, answer, coordinate) and up to
eight fields, each NAME=VALUE: an event carries references only, so a VALUE is an id of at most 120 characters of
letters, digits and `_ . : / # @ -` (a source id, a `path:line` fact key, a QK answer id, a backlog item id, a pack
handle) and free text is refused. `post` numbers events 1, 2, 3 ... in the store; `wait` polls the store every 50 ms
for events past N and prints `events`, `last` (the newest sequence it scanned, else N) and `timed_out`; a wait whose
S passes with no event exits 0 with `timed_out` true, and a post from any other process on the same store wakes it.
With `--kind` and `--item` the wait returns only the events of that kind whose `item` field is one of IDS (an intent's
comma-separated `item` list matches when it holds one of them); an event of another kind or item does not end the wait,
and `last` is the newest sequence scanned, filtered-out events included, so the next `--since` skips them.
A local `wait --kind progress --item IDS` that blocks (a `--timeout` above 0) holds a lease on the key `wait/PID/ITEM` for
each id, PID being its own process id, for its `--timeout` and five seconds more, with the holder KB_COORD_HOLDER (else `anonymous`),
and ends the leases when it returns: `list --prefix wait/` shows who waits on which item, which `kbmon` reads. A wait that is
killed leaves its keys until the lease ends; a wait behind `serve` holds none.
`wait --pid PID` (repeatable, local only: a process id means nothing to a server) also returns, with exit 0 and `timed_out`
false, as soon as a watched process no longer runs (one that has exited and not been reaped no longer runs), and names each such pid in `ended`; with every watched process alive and
no event it goes on until `--timeout`. A pid that has ended before the wait starts ends it at once.

Two kinds carry a session's plan: `intent` (fields session, item, topic, touch, operator; at least one of item, topic and touch;
item and topic hold a comma-separated list of ids, touch of globs with * and ?, up to 120 characters; operator is the id of
the operator the session runs for, which a server's own `operator` field replaces) and `progress`
(fields item and state, state one of claimed, working, blocked, returned, failed, staging, landing, landed, refused, released or
done, and the optional fields exit, gates (a comma-separated list of ids) and step). `transition` moves an item's run state, the
value of the key `run/ITEM` (an absent key holds `none`), by this table, and posts the progress event of the move; the item file
keeps todo, doing and done, so `done` is no run state: none to claimed; claimed to working, released or landed; working to
returned, failed or blocked; blocked to working, returned or failed; returned to staging, landing, working or released; failed to working
or released; staging to returned or refused; landing to landed or refused; refused to working, staging, landing or released; released to claimed
(a released item is claimed again); landed moves nowhere. Two kinds carry a question and its reply between
agents: `ask` (fields id, to, ref: to is a session, item or agent id, or `any`; ref is the coord key whose `put` value
holds the question) and `answer` (fields id, state, ref: state is one of working, input-required, completed, failed,
rejected, the names A2A gives its task states; ref is the key whose `put` value holds the answer text). An event keeps
references only, so the text is put under a key such as `ask/ID` and `answer/ID` first; an ask or answer without id or
ref, an ask without to, or an answer with another state exits 2. Behind `serve`, an ask carries the server's `operator`
field like every event. `blocked` (fields session, state waiting or cleared, and the optional on, permission or question, item and
operator) says a session waits on the person or no longer does; the coord hook posts it. `digest` is the one command that prints text, not JSON:
one line per live intent (posted within a day, its items not all done, landed or released by a later progress event, and, when it names a
session, that session's presence lease `session/<id>` still held: a release or an expiry drops the session's intents) or
live claim (a held lease) with a value that overlaps a key (equal, a directory-style prefix either way, or a glob match either
way), newest first, cut at N lines; an intent line ends with `state=` and `age=` (seconds since the newest of those moves) when a
later progress event moved its items, those of its items that overlap a key when any do (an intent for A,B read for B shows B's
state, not A's), else all of them; with nothing to show it prints nothing.

A `claim` of a research key (`research:TOPIC:TERM`), a code key (`code:REPO:PATH[#SYMBOL]`) or a backlog item id leaves a `claim` event (fields key, holder), its `release`
a `release` event and a claim the store refuses a `dup_of` event (key, holder of the refused claim, held_by); a session's presence
lease `session/ID` and any other key leave none. `dedup` leaves a `claim` event for each key it claims and one `dedup` event
(holder, topic, terms, claimed, overlapping, held: lack terms, comma-separated, `-` for none).

`dedup` runs `rag.py pack QUESTION` and takes its fingerprint: the anchor topic (the first article's path without `.md`,
else `unanchored`) and the terms of its `kb lacks:` lines, lowercased and mapped to their canonical form by
`_tools/aliases.csv` and each root's `_retrieval/aliases.csv`; `--topic PATH` anchors the claim on the article PATH (without
`.md`) instead. A live claim of another holder (a `research:TOPIC:TERM` key) overlaps when it is on the same topic and
shares at least half of the smaller of the two term sets; the shared terms count as covered. A claim under the caller's own
holder name is its own only when `--token` is that claim's token (the one an earlier `dedup` printed): the same name from a
session that holds no such token is another holder. A question whose pack names no lack term claims the topic as a whole
(`research:TOPIC:WHOLE`, listed in `claimed` with `uncovered` empty): it overlaps every other holder's claim on the topic, and
another holder's whole-topic claim covers every term of a later question on it. In one transaction `dedup`
claims every term not covered (one lease, one token, shown once, for the keys in `claimed`) and prints `topic`, `terms`,
`uncovered`, `overlaps` (each: `holder`, `topic`, shared `terms`), `held` (each uncovered term another live claim
already holds, below the overlap threshold: `term`, `holder`; `dedup` claims no key a live claim holds), `claimed`,
`ttl`, `token` (only when it claimed) and `seq` (the newest event, for `wait --since`). A question every term of which
is covered prints `uncovered` empty and claims nothing; exit 0 either way.

`dedup --code REPO:PATH[#SYMBOL]` (repeatable) claims code targets beside the research terms, each under the key `code:` and the
target, in the same transaction, lease and token. A target is a repository name, a path and, after `#`, an optional symbol, an id
like an event's field value (REPO has no `:`, the whole target at most 115 characters). Another holder's live claim covers a target
when it is the same target or a claim on its path (a claim on a path covers its symbols): the target is listed in `overlaps` as
`{holder, targets}` and claimed by nobody, while the targets not covered are claimed (their keys in `claimed`, the targets in
`code_uncovered`). A claim on a path while another holder holds symbols under it is made and lists those symbols in `held`
(`term` the symbol's target, `holder`). A token holder's own claims are never an overlap. The holder posts each code fact or map
entry it adds as a `code_added` event (fields `target`, REPO:PATH[#SYMBOL], and optionally `ref`, `path:line`), which
`wait --kind code_added` returns: an agent that waits on the claim reads those events instead of reading the code.

  coord.py serve --bind [HOST:]PORT --keys DIR       answer every command above as a JSON request over HTTP, on the store
  coord.py --url URL --key-file PATH COMMAND ...     send COMMAND to such a server instead of a local store

`serve` binds 127.0.0.1 unless --bind names a host (port 0 picks a free port) and prints `coord.py: serving URL` as
its first line. DIR holds one file per operator, named for the operator and holding that operator's token, and a file in
a subdirectory named for a team (DIR/TEAM/OPERATOR) makes its operator TEAM/OPERATOR, beside flat files whose operators
have no team; the server reads DIR on every request, so removing a file revokes that operator at once. An event carries
`operator` TEAM/OPERATOR, a claim or `dedup` of such an operator holds as TEAM/OPERATOR/HOLDER, and its `claim` or `put`
of a key under another team's `team/NAME/` prefix exits 1 (a flat operator's too): its own team's keys and every other
key stay open. A client sends its own token, read from
the file --key-file names (never from argv or the environment), as `Authorization: Bearer TOKEN` in `POST /v1/run`
with the body {"argv": [the command and its arguments]}; the server answers 401 to a token no file holds (or two
files hold) and runs the command on its store otherwise, answering {"code": N, "body": ...}, where code and body are
what the command would have printed and exited with; a `wait` checks the token again once a second and before it
replies, and answers 401 instead of an event when the file is gone. The server adds the operator's name as the field `operator` to
each event it records (a client's own `operator` field on an intent is replaced by it) and never serves `--store`. `wait` is a long-poll: the request is held
until an event arrives or S seconds pass. The request carries the token in the clear over plain http, so reach a server
beyond loopback through a TLS front end (an https URL is accepted): a plain http --url whose host is not loopback, and a
`serve --bind` host that is not loopback, exit 2 naming plain http and TLS, unless the global flag --plain-http is given
before the command (`coord.py --plain-http serve ...`; `--plain-http --url ... --key-file ...`).

Without `--holder`, `claim` and `dedup` take the holder from the environment variable KB_COORD_HOLDER, else `anonymous`.

Exit codes: 0 done; 1 the command's condition failed (key held, wrong or expired token, revision moved, key
absent); 2 a bad argument, no store, or a server that refuses (401) or cannot be reached.

Answers: who holds an item, a key or a file right now, and what other sessions posted
Answers: how to claim, renew, release, wait for an event or write a value only while its revision holds
Use: python3 _tools/coord.py claim|renew|release|get|put|list|post|digest|wait|dedup [ARGS]
MCP: coord_claim claims a key
MCP: coord_renew renews a claim
MCP: coord_release releases a claim
MCP: coord_post posts an event
MCP: coord_get reads a value
MCP: coord_put writes an ask's or answer's text
MCP: coord_digest lists live intents and claims
MCP: coord_wait waits for events
"""
import argparse
import csv
import hashlib
import http.client
import http.server
import ipaddress
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
import unicodedata
import urllib.parse
from fnmatch import fnmatchcase
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUSY_SECONDS = 30
PACK_SECONDS = 120
RESEARCH = "research:"  # a research claim's key: research:<anchor topic>:<lack term>
WHOLE = "WHOLE"  # the term of a research claim on a topic as a whole: research:<anchor topic>:WHOLE (upper case: no term id is)
KEY_TOPIC = 80  # the most characters of an anchor topic a research key holds; a longer one is cut and hashed, which leaves the term room
PLAIN_LETTERS = str.maketrans({"ł": "l", "đ": "d", "ø": "o", "ß": "ss", "æ": "ae", "œ": "oe", "ð": "d", "þ": "th"})
CODE = "code:"  # a code claim's key: code:<repository>:<path>[#<symbol>]
HOLDER_ENV = "KB_COORD_HOLDER"
DEDUP_SECONDS = 3600
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS entries ("
    "key TEXT PRIMARY KEY, value TEXT, revision INTEGER NOT NULL, holder TEXT, token TEXT, ttl REAL, expires REAL, budget REAL)"
)
EVENTS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    "seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, fields TEXT NOT NULL, at REAL NOT NULL)"
)
KINDS = ("claim", "release", "dedup", "fact_added", "code_added", "gap_opened", "dup_of", "lesson", "heartbeat", "intent", "progress", "ask", "answer", "coordinate", "blocked")
KIND_FIELDS = {"intent": ("session", "item", "topic", "touch", "operator"), "progress": ("item", "state", "exit", "gates", "step"),
               "ask": ("id", "to", "ref"), "answer": ("id", "state", "ref"), "code_added": ("target", "ref"),
               "coordinate": ("item", "other", "strategy", "touch", "session", "operator"),
               "blocked": ("session", "state", "on", "item", "operator")}
STRATEGIES = ("wait", "ask", "after", "join", "proceed")  # what a coordinate event says its session will do about the other item
BLOCKED_STATES = ("waiting", "cleared")  # what a `blocked` event says of its session: it waits on the person, or no longer does
BLOCKED_ON = ("permission", "question")  # what a session waits on: a permission prompt, or a question put to the person
RUN_STATES = ("claimed", "working", "blocked", "returned", "failed", "staging", "landing", "landed", "refused", "released")
TRANSITIONS = {"none": ("claimed",), "claimed": ("working", "released", "landed"), "working": ("returned", "failed", "blocked"),
               "blocked": ("working", "returned", "failed"), "returned": ("staging", "landing", "working", "released"),
               "failed": ("working", "released"), "staging": ("returned", "refused"), "landing": ("landed", "refused"),
               "refused": ("working", "staging", "landing", "released"), "landed": (), "released": ("claimed",)}  # none: a run key no move has written
STATES = RUN_STATES + ("done",)  # what a progress event may carry; `done` is the item file's own, no run state moves to it
FINISHED = ("done", "landed", "released")  # the states after which a digest no longer shows an intent
RUN_KEYS = "run/"  # an item's run state: key run/<item id>, its value the state's name
WAIT_KEYS = "wait/"  # the lease a blocking `wait --kind progress --item` holds: key wait/<pid>/<item id>
WAIT_SLACK = 5  # seconds a wait's lease outlasts its --timeout, so a killed wait's key ends by itself
STEP_FIELDS = ("exit", "gates", "step")  # the fields of a progress event besides item and state
ANSWER_STATES = ("working", "input-required", "completed", "failed", "rejected")  # A2A's task states
FIELD_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
FIELD_VALUE = re.compile(r"[A-Za-z0-9_.:/#@-]{1,120}")
CODE_TARGET = re.compile(r"(?=.{1,%d}$)([A-Za-z0-9_.@-]+):([A-Za-z0-9_./@-]+)(?:#([A-Za-z0-9_.:@-]+))?" % (120 - len(CODE)))
CODE_REF = re.compile(r"[A-Za-z0-9_.:/#@-]+:[0-9]+")  # a path:line fact key
ID_LIST = re.compile(r"(?=.{1,120}$)[A-Za-z0-9_.:/#@-]+(,[A-Za-z0-9_.:/#@-]+)*")
GLOB_LIST = re.compile(r"(?=.{1,120}$)[A-Za-z0-9_.:/#@*?-]+(,[A-Za-z0-9_.:/#@*?-]+)*")
LIST_VALUES = {("intent", "item"): ID_LIST, ("intent", "topic"): ID_LIST, ("intent", "touch"): GLOB_LIST,
               ("progress", "gates"): ID_LIST, ("coordinate", "touch"): GLOB_LIST}
INTENT_SECONDS = 86400
TEAM_KEYS = "team/"  # a team's keys: team/<team>/<name>, written by that team's operators alone behind `serve`
SESSION_LEASE = "session/"  # the presence lease of a session: key session/<id>, held while the session lives
MAX_FIELDS = 8
POLL_SECONDS = 0.05
RECHECK_SECONDS = 1.0
OPERATOR_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
BODY_LIMIT = 65536
SQLITE_MAX_INT = 2**63 - 1
REQUEST_SECONDS = 60
ENDPOINT = "/v1/run"
LIVE = "(expires IS NULL OR expires > :now OR value IS NOT NULL)"  # a row with a value outlives its lease
PUBLIC = ("key, value, revision, CASE WHEN expires > :now THEN holder END AS holder, "
          "CASE WHEN expires > :now THEN expires END AS expires")


class Revoked(Exception):
    """A served command found its caller's token no longer names its operator."""


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
    """The claim's --holder, else `anonymous`: an id like an event's field value, so a digest line never carries free text.
    `main` fills a missing --holder of a local command from KB_COORD_HOLDER; a server never reads its own environment.
    Behind `serve`, a caller holds as `operator/HOLDER` (`team/operator/HOLDER` for an operator of a team)."""
    holder = args.holder or "anonymous"
    if not FIELD_VALUE.fullmatch(holder):
        raise Refused({"ok": False, "error": f"--holder is an id of 1 to 120 characters of letters, digits and _ . : / # @ -, not {holder[:40]!r}"}, 2)
    operator = getattr(args, "operator", None) or ""
    return f"{operator}/{holder}" if operator else holder


def team_refusal(args):
    """Refuse, exit 1, a served caller's claim or put of a key under another team's `team/NAME/` prefix: its own team's
    keys, every key outside `team/` and a local command's keys stay open."""
    operator = getattr(args, "operator", None)
    if not operator or not args.key.startswith(TEAM_KEYS):
        return
    owner = args.key.split("/")[1]
    if "/" in args.key[len(TEAM_KEYS):] and owner != operator.partition("/")[0]:
        raise Refused({"ok": False, "key": args.key,
                       "error": f"{args.key} is under team {owner}'s keys, which {operator} does not write"})


def recorded(key):
    """Whether a claim of KEY leaves events: a research key, a code key or a backlog item id, never a session's presence lease (the
    coord hook renews those all session long)."""
    if key.startswith((RESEARCH, CODE)):
        return True
    if key.startswith(SESSION_LEASE):
        return False
    import bl_base
    return bl_base.id_re().fullmatch(key) is not None


def add_event(con, args, kind, fields, now):
    """Insert an event inside the open transaction, with the serving operator's name like `post` does."""
    if getattr(args, "operator", None):
        fields = {**fields, "operator": args.operator}
    return con.execute("INSERT INTO events (kind, fields, at) VALUES (?, ?, ?)",
                       (kind, json.dumps(fields, sort_keys=True, ensure_ascii=False), now)).lastrowid


def term_list(items):
    """ITEMS (lack term ids) as one event field value: comma-separated, `-` for none."""
    return ",".join(items) or "-"


def claim(args, clock):
    holder = holder_name(args)
    if not FIELD_VALUE.fullmatch(args.key):
        raise Refused({"ok": False, "error": f"a claim's key is an id of 1 to 120 characters of letters, digits and _ . : / # @ -, not {args.key[:40]!r}"}, 2)
    team_refusal(args)
    budget = getattr(args, "budget", None)
    if budget is not None:
        import bl_base
        if not bl_base.id_re().fullmatch(args.key):
            raise Refused({"ok": False, "key": args.key, "error": f"--budget is for a claim of a backlog item id, not {args.key[:40]!r}"}, 2)
    token = secrets.token_hex(16)
    refusal = None
    with Tx(args.store) as con:
        now = clock()
        row = live_row(con, args.key, now)
        if row is not None and row["holder"] is not None:
            refusal = {"ok": False, "key": args.key, "holder": row["holder"], "revision": row["revision"],
                       "expires": row_json(row)["expires"], "error": f"{args.key} is held by {row['holder']}"}
            if recorded(args.key):
                add_event(con, args, "dup_of", {"key": args.key, "holder": holder, "held_by": row["holder"]}, now)
        else:
            revision = take(con, args.key, holder, token, args.ttl, now, budget)
            if recorded(args.key):
                add_event(con, args, "claim", {"key": args.key, "holder": holder}, now)
    if refusal:
        raise Refused(refusal)
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


def renew(args, clock):
    with Tx(args.store) as con:
        now = clock()
        row = held_by(con, args.key, args.token, now)
        ttl = args.ttl if args.ttl is not None else row["ttl"]
        con.execute("UPDATE entries SET ttl = ?, expires = ? WHERE key = ?", (ttl, now + ttl, args.key))
    return {"ok": True, "key": args.key, "holder": row["holder"], "ttl": ttl, "expires": round(now + ttl, 3)}


def release(args, clock):
    with Tx(args.store) as con:
        now = clock()
        row = held_by(con, args.key, args.token, now)
        if row["value"] is None:
            con.execute("DELETE FROM entries WHERE key = ?", (args.key,))
        else:
            con.execute("UPDATE entries SET holder = NULL, token = NULL, ttl = NULL, expires = NULL, budget = NULL WHERE key = ?", (args.key,))
        if recorded(args.key):
            add_event(con, args, "release", {"key": args.key, "holder": row["holder"]}, now)
    return {"ok": True, "key": args.key, "holder": row["holder"], "released": True}


def get(args, clock):
    con = connect(args.store)
    now = clock()
    try:
        con.execute(SCHEMA)
        row = con.execute(f"SELECT {PUBLIC} FROM entries WHERE key = :key AND {LIVE}", {"key": args.key, "now": now}).fetchone()
    finally:
        con.close()
    if row is None:
        raise Refused({"ok": False, "key": args.key, "revision": 0, "error": f"{args.key} is absent"})
    return {"ok": True, **row_json(row)}


def put(args, clock):
    team_refusal(args)
    with Tx(args.store) as con:
        now = clock()
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


def listing(args, clock):
    con = connect(args.store)
    now = clock()
    try:
        ensure_schema(con)
        rows = con.execute(f"SELECT {PUBLIC}, CASE WHEN expires > :now THEN budget END AS budget FROM entries "
                           f"WHERE {LIVE} ORDER BY key", {"now": now}).fetchall()
    finally:
        con.close()
    if getattr(args, "by_operator", False):
        return {"operators": by_operator(rows, args.prefix, getattr(args, "keys", None))}
    out = []
    for r in rows:
        if r["key"].startswith(args.prefix):
            out.append({**row_json({k: r[k] for k in r.keys() if k != "budget"}), **budget_view(r["key"], r["budget"])})
    return out


def by_operator(rows, prefix, keys_dir):
    """One row per operator of the live claims under PREFIX: {operator, claims, budget}, budget the sum of the budgets
    approved at the claims (a claim with none adds 0). The operator is read from the claim's holder, which behind `serve`
    starts with the operator's name and a `/`: the longest name of a key file in KEYS_DIR that the holder starts with. A
    claim whose holder names none (every claim of a local store) is left out."""
    names = sorted((name for name, _path in key_files(keys_dir)), key=len, reverse=True) if keys_dir else []
    totals = {}
    for r in rows:
        if r["holder"] is None or not r["key"].startswith(prefix):
            continue
        who = next((n for n in names if r["holder"].startswith(n + "/")), None)
        if who is not None:
            claims, budget = totals.get(who, (0, 0.0))
            totals[who] = (claims + 1, budget + (r["budget"] or 0))
    return [{"operator": who, "claims": claims, "budget": round(budget, 6)} for who, (claims, budget) in sorted(totals.items())]


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
    """The closed field names (and the closed states) of the intent, progress, ask, answer, coordinate and blocked kinds."""
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
            raise Refused({"ok": False, "error": f"progress takes item and state (one of {', '.join(STATES)}) and optionally "
                                                 f"{', '.join(STEP_FIELDS)}"}, 2)
    if kind == "coordinate" and (not {"item", "other"} <= set(fields) or fields.get("strategy") not in STRATEGIES):
        raise Refused({"ok": False, "error": "a coordinate takes item (the item of the session that chose), other (the item it coordinates "
                                             "with) and strategy (one of " + ", ".join(STRATEGIES) + "), and optionally touch, session "
                                             "and operator"}, 2)
    if kind == "blocked" and ("session" not in fields or fields.get("state") not in BLOCKED_STATES
                              or fields.get("on", BLOCKED_ON[0]) not in BLOCKED_ON):
        raise Refused({"ok": False, "error": "a blocked takes session, state (one of " + ", ".join(BLOCKED_STATES) + "), and optionally "
                                             "on (one of " + ", ".join(BLOCKED_ON) + "), item and operator"}, 2)
    if kind == "code_added":
        if "target" not in fields or CODE_TARGET.fullmatch(fields["target"]) is None:
            raise Refused({"ok": False, "error": "a code_added takes target (REPO:PATH[#SYMBOL]) and optionally ref (path:line)"}, 2)
        if "ref" in fields and CODE_REF.fullmatch(fields["ref"]) is None:
            raise Refused({"ok": False, "error": f"a code_added ref is a path:line, not {fields['ref'][:40]!r}"}, 2)
    if kind == "ask" and not {"id", "to", "ref"} <= set(fields):
        raise Refused({"ok": False, "error": "an ask takes id, to (a session, item or agent id, or any) and ref (the key whose value holds the question)"}, 2)
    if kind == "answer" and ("id" not in fields or "ref" not in fields or fields.get("state") not in ANSWER_STATES):
        raise Refused({"ok": False, "error": "an answer takes id, state (one of " + ", ".join(ANSWER_STATES)
                                             + ") and ref (the key whose value holds the answer)"}, 2)


def event_json(row):
    return {"seq": row["seq"], "kind": row["kind"], "fields": json.loads(row["fields"]), "at": round(row["at"], 3)}


def post(args, clock):
    if args.kind not in KINDS:
        raise Refused({"ok": False, "error": f"unknown kind {args.kind[:40]!r}: one of {', '.join(KINDS)}"}, 2)
    fields = parse_fields(args.field, args.kind)
    check_kind(args.kind, fields)
    if getattr(args, "operator", None):
        fields["operator"] = args.operator
    with Tx(args.store) as con:
        seq = con.execute("INSERT INTO events (kind, fields, at) VALUES (?, ?, ?)",
                          (args.kind, json.dumps(fields, sort_keys=True, ensure_ascii=False), clock())).lastrowid
    return {"ok": True, "seq": seq, "kind": args.kind, "fields": fields}


def transition(args, clock):
    """Move the run state of the item KEY (run/<item id>) to --to, when TRANSITIONS allows it from the state the key holds
    (an absent key holds `none`): the value, the revision and one progress event are written in one transaction. A move the
    table does not allow exits 1 naming the state and the states it may move to, and writes nothing."""
    item = args.key[len(RUN_KEYS):] if args.key.startswith(RUN_KEYS) else ""
    if not FIELD_VALUE.fullmatch(item) or "/" in item:
        raise Refused({"ok": False, "error": f"a run key is {RUN_KEYS}<item id>, the id of 1 to 120 characters of letters, digits and _ . : # @ -, not {args.key[:40]!r}"}, 2)
    if args.to not in RUN_STATES:
        raise Refused({"ok": False, "error": f"--to is one of {', '.join(RUN_STATES)}, not {args.to[:40]!r}"}, 2)
    fields = parse_fields(args.field, "progress")
    extra = sorted(set(fields) - set(STEP_FIELDS))
    if extra:
        raise Refused({"ok": False, "error": f"transition takes only the fields {', '.join(STEP_FIELDS)}, not {', '.join(extra)}"}, 2)
    team_refusal(args)
    with Tx(args.store) as con:
        now = clock()
        row = live_row(con, args.key, now)
        have = row["value"] if row is not None and row["value"] is not None else "none"
        allowed = TRANSITIONS.get(have, ())
        if args.to not in allowed:
            raise Refused({"ok": False, "key": args.key, "state": have, "allowed": list(allowed),
                           "revision": row["revision"] if row is not None else 0,
                           "error": f"{args.key} is {have}, which does not move to {args.to}: it may move to "
                                    f"{', '.join(allowed) or 'no state'}"})
        if row is None:
            con.execute("INSERT INTO entries (key, value, revision) VALUES (?, ?, 1)", (args.key, args.to))
            revision = 1
        else:
            con.execute("UPDATE entries SET value = ?, revision = revision + 1 WHERE key = ?", (args.to, args.key))
            revision = row["revision"] + 1
        event = {"item": item, "state": args.to, **fields}
        seq = add_event(con, args, "progress", event, now)
    return {"ok": True, "key": args.key, "previous": have, "state": args.to, "revision": revision, "seq": seq, "fields": event}


def hold_wait(args, items):
    """Lease the key wait/<pid>/<item> for each of ITEMS (the ids a blocking `wait --kind progress --item` waits on) for the
    wait's --timeout and a few seconds more, held by KB_COORD_HOLDER (else `anonymous`): the keys `kbmon` reads to show who
    waits on which item. Returns the keys leased; a store that cannot take them leaves the wait as it was."""
    holder = os.environ.get(HOLDER_ENV) or "anonymous"
    holder = holder if FIELD_VALUE.fullmatch(holder) else "anonymous"
    keys = []
    try:
        with Tx(args.store) as con:
            now = time.time()
            for item in sorted(items):
                key = f"{WAIT_KEYS}{os.getpid()}/{item}"
                end_leases(con, now, key)
                take(con, key, holder, secrets.token_hex(16), args.timeout + WAIT_SLACK, now)
                keys.append(key)
    except sqlite3.Error:
        return []
    return keys


def drop_wait(args, keys):
    """End the leases `hold_wait` took, a lease that is gone already included."""
    if not keys:
        return
    try:
        with Tx(args.store) as con:
            con.executemany("DELETE FROM entries WHERE key = ? AND value IS NULL", [(k,) for k in keys])
    except sqlite3.Error:
        pass


def process_runs(pid):
    """Whether process PID runs. POSIX asks with signal 0 (a process of another user runs), and a process that has exited
    but not been reaped (a zombie, state Z in `ps`) does not run; Windows opens it, as signal 0 would end it there."""
    if os.name == "posix":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:
            state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return True
        return not state.strip().startswith("Z")
    import ctypes
    handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        return False
    alive = ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT
    ctypes.windll.kernel32.CloseHandle(handle)
    return alive


def wait(args, _clock):
    """Events after --since, held until one arrives or --timeout passes. Behind `serve`, args.recheck says whether the
    caller's token still names its operator: asked about once a second and before any reply, and a revoked caller
    gets Revoked, not an event."""
    recheck = getattr(args, "recheck", None)
    kind, items = getattr(args, "kind", None), getattr(args, "item", None)
    pids = getattr(args, "pid", None) or []
    ended = []
    deadline = time.monotonic() + args.timeout
    next_recheck = time.monotonic() + RECHECK_SECONDS
    scanned = args.since
    con = connect(args.store)
    keys = hold_wait(args, items) if kind == "progress" and items and not recheck and args.timeout > 0 else []
    try:
        con.execute(EVENTS_SCHEMA)
        while True:
            rows = con.execute("SELECT * FROM events WHERE seq > ? ORDER BY seq", (scanned,)).fetchall()
            if rows:
                scanned = rows[-1]["seq"]
                if kind is not None:
                    rows = [r for r in rows if r["kind"] == kind]
                if items is not None:
                    rows = [r for r in rows if items & set(json.loads(r["fields"]).get("item", "").split(","))]
            ended = [p for p in pids if not process_runs(p)]
            if rows or ended or time.monotonic() >= deadline:
                break
            if recheck and time.monotonic() >= next_recheck:
                if not recheck():
                    raise Revoked
                next_recheck = time.monotonic() + RECHECK_SECONDS
            time.sleep(min(POLL_SECONDS, max(deadline - time.monotonic(), 0)))
    finally:
        con.close()
        drop_wait(args, keys)
    if recheck and not recheck():
        raise Revoked
    body = {"ok": True, "since": args.since, "last": scanned,
            "events": [event_json(r) for r in rows], "timed_out": not rows and not ended}
    if pids:
        body["ended"] = ended
    return body


def overlaps(a, b):
    """Two keys overlap when they are equal, one is a directory-style prefix of the other or one globs the other."""
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/") or fnmatchcase(a, b) or fnmatchcase(b, a)


def one_line(text, limit=80):
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", re.sub(r"\s+", "_", str(text)))[:limit]


def digest(args, clock):
    """The live intents and claims that overlap the keys, newest first, as at most N lines of text (no JSON)."""
    con = connect(args.store)
    now = clock()
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
            state[fields.get("item")] = (row["seq"], fields.get("state"), row["at"])
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
        if items and all(i in state and state[i][0] > seq and state[i][1] in FINISHED for i in items):
            continue
        values = [v for n in ("item", "topic", "touch") for v in fields.get(n, "").split(",") if v]
        if not any(overlaps(v, k) for v in values for k in args.key):
            continue
        text = "intent " + " ".join(f"{n}={fields[n]}" for n in KIND_FIELDS["intent"] if n in fields)
        asked = [i for i in items if any(overlaps(i, k) for k in args.key)] or items
        moves = [state[i] for i in asked if i in state and state[i][0] > seq]
        now_states = sorted({move[1] for move in moves})
        lines.append((at, text + (f" state={'/'.join(now_states)} age={int(now - max(move[2] for move in moves))}s" if moves else "")))
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


def topic_path(text):
    """A --topic path as the anchor topic: without `.md`, an id of 1 to 120 characters with no `:` (a research key splits there)."""
    topic = text[:-3] if text.endswith(".md") else text
    if not FIELD_VALUE.fullmatch(topic) or ":" in topic:
        raise argparse.ArgumentTypeError("must be an article path of letters, digits and _ . / # @ -, up to 120 characters")
    return topic


def fingerprint(question, topic=None):
    """(anchor topic, lack terms) of the question's pack: the first article's path without `.md` (`unanchored` when
    the pack names none; TOPIC, when given, instead of either) and the words of its `kb lacks:` lines, lowercased and
    mapped to their canonical alias."""
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
    found = article.group(1) if article else "unanchored"
    return (topic or found), terms


def term_id(term, room):
    """A lack term as an id a claim key takes, within ROOM characters: lowercased, each run of characters outside letters,
    digits and `_ . -` a `-`, and, when that changed the term (or cut it), a short hash of the term after it, so two terms
    never share an id. A letter with an accent is its plain letter in the slug (`ł` and a few others by table), so a
    non-ASCII term keeps a readable form. WHOLE and a term that is already an id stay as they are."""
    if term == WHOLE or (re.fullmatch(r"[a-z0-9_.-]+", term) and len(term) <= room):
        return term
    plain = unicodedata.normalize("NFKD", term.lower().translate(PLAIN_LETTERS))
    slug = re.sub(r"[^a-z0-9_.-]+", "-", plain.encode("ascii", "ignore").decode("ascii")).strip("-")
    tag = hashlib.sha256(term.encode("utf-8")).hexdigest()[:6]
    return f"{slug[:max(0, room - len(tag) - 1)].rstrip('-')}-{tag}".lstrip("-")


def topic_key(topic):
    """The anchor topic as a research key holds it: as it is within KEY_TOPIC characters, else cut with a six-character
    hash of the whole topic after it."""
    if len(topic) <= KEY_TOPIC:
        return topic
    return f"{topic[:KEY_TOPIC - 7]}-{hashlib.sha256(topic.encode('utf-8')).hexdigest()[:6]}"


def research_key(topic, term):
    return f"{RESEARCH}{topic_key(topic)}:{term}"


def code_target(text):
    """A --code value as REPO:PATH[#SYMBOL], an id the claim key `code:` + target takes (at most 115 characters)."""
    if CODE_TARGET.fullmatch(text) is None:
        raise argparse.ArgumentTypeError("must be REPO:PATH or REPO:PATH#SYMBOL, up to 115 characters of letters, digits and _ . / @ - "
                                         "(a : only after REPO or inside SYMBOL)")
    return text


def covers(theirs, mine):
    """Whether a claim on the code target THEIRS covers MINE: the same target, or THEIRS is the path of MINE's symbol."""
    a, b = CODE_TARGET.fullmatch(theirs), CODE_TARGET.fullmatch(mine)
    return bool(a and b and a.group(1, 2) == b.group(1, 2) and (a.group(3) is None or a.group(3) == b.group(3)))


def code_claims(con, holder, token, code, ttl, now, fresh):
    """Claim the code targets CODE that no live claim covers, inside dedup's transaction. A claim of another holder (or of
    this holder without the caller's TOKEN) that covers a target is an overlap and is not claimed again; the caller's own
    is skipped; FRESH is the token of the new claims.
    Returns (uncovered targets, overlaps as {holder, targets}, held as {term, holder}, claimed keys, claimed targets)."""
    live, own = {}, set()
    for row in con.execute("SELECT key, holder, token FROM entries WHERE holder IS NOT NULL AND substr(key, 1, ?) = ? ORDER BY key",
                           (len(CODE), CODE)):
        target = row["key"][len(CODE):]
        if row["holder"] == holder and token and row["token"] == token:
            own.add(target)
        else:
            live.setdefault(row["holder"], []).append(target)
    shared, uncovered, held, keys = {}, [], [], []
    for target in dict.fromkeys(code):
        if any(covers(o, target) for o in own):
            continue
        who = next((w for w, held_by in sorted(live.items(), key=lambda pair: str(pair[0])) if any(covers(t, target) for t in held_by)), None)
        if who is not None:
            shared.setdefault(who, []).append(target)
            continue
        uncovered.append(target)
        if CODE_TARGET.fullmatch(target).group(3) is None:
            held += [{"term": t, "holder": w} for w, held_by in sorted(live.items(), key=lambda pair: str(pair[0]))
                     for t in held_by if covers(target, t) and t != target]
        take(con, CODE + target, holder, fresh, ttl, now)
        keys.append(CODE + target)
    return uncovered, [{"holder": w, "targets": t} for w, t in sorted(shared.items(), key=lambda pair: str(pair[0]))], held, keys


def dedup(args, clock):
    """Claim the lack terms of the question's pack that no overlapping live claim covers; name the claims that do.
    A claim on the same anchor topic overlaps when it shares at least half of the smaller lack-set's terms. A pack with
    no lack term claims the topic as a whole (the term WHOLE), which overlaps every other holder's claim on the topic,
    and a whole-topic claim of another holder covers every term. A live claim under the caller's own holder name is its
    own only when --token is that claim's token: the same name from another session is an overlap. Each lack term is
    mapped to an id (`term_id`) first, so a key, a claim event and a dedup event hold only the characters a claim key takes."""
    holder = holder_name(args)
    topic, found = fingerprint(args.question, args.topic)
    room = 120 - len(research_key(topic, ""))
    terms = []
    for word in found:
        if term_id(word, room) not in terms:
            terms.append(term_id(word, room))
    token = secrets.token_hex(16)
    code = getattr(args, "code", None) or []
    overlapping, covered, own, taken, others = [], set(), set(), [], []
    code_uncovered, shared, code_held, code_keys = [], [], [], []
    with Tx(args.store) as con:
        now = clock()
        end_leases(con, now)
        theirs, holders = {}, {}
        for row in con.execute("SELECT key, holder, token FROM entries WHERE holder IS NOT NULL AND substr(key, 1, ?) = ? ORDER BY key",
                               (len(RESEARCH), RESEARCH)):
            their_topic, _colon, term = row["key"][len(RESEARCH):].partition(":")
            if their_topic != topic_key(topic):
                continue
            if row["holder"] == holder and args.token and row["token"] == args.token:
                own.add(term)
            else:
                theirs.setdefault(row["holder"], set()).add(term)
                holders.setdefault(term, row["holder"])
        for who, held in sorted(theirs.items(), key=lambda pair: str(pair[0])):
            if not terms:
                overlapping.append({"holder": who, "topic": topic, "terms": sorted(held)})
            elif WHOLE in held:
                covered.update(terms)
                overlapping.append({"holder": who, "topic": topic, "terms": list(terms)})
            else:
                shared = [t for t in terms if t in held]
                if shared and len(shared) * 2 >= min(len(terms), len(held)):
                    covered.update(shared)
                    overlapping.append({"holder": who, "topic": topic, "terms": shared})
        uncovered = [t for t in terms if t not in covered]
        wanted = uncovered if terms else ([] if overlapping or WHOLE in own else [WHOLE])
        for term in wanted:
            if term in holders:
                others.append({"term": term, "holder": holders[term]})
            elif term not in own:
                take(con, research_key(topic, term), holder, token, args.ttl, now)
                taken.append(research_key(topic, term))
                add_event(con, args, "claim", {"key": taken[-1], "holder": holder}, now)
        if code:
            code_uncovered, shared, code_held, code_keys = code_claims(con, holder, args.token, code, args.ttl, now, token)
            for key in code_keys:
                add_event(con, args, "claim", {"key": key, "holder": holder}, now)
        add_event(con, args, "dedup", {
            "holder": holder, "topic": topic, "terms": term_list(terms),
            "claimed": term_list(t for t in wanted if research_key(topic, t) in taken),
            "overlapping": term_list(sorted(covered or {t for o in overlapping for t in o["terms"]})),
            "held": term_list(o["term"] for o in others),
            **({"code": term_list(k[len(CODE):] for k in code_keys)} if code else {})}, now)
        last = con.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]
    body = {"ok": True, "topic": topic, "holder": holder, "terms": terms, "uncovered": uncovered, "overlaps": overlapping,
            "held": others, "claimed": taken, "ttl": args.ttl, "seq": last}
    if code:
        body.update({"overlaps": overlapping + shared, "held": others + code_held, "claimed": taken + code_keys,
                     "code_uncovered": code_uncovered})
    if taken or code_keys:
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
    if value > SQLITE_MAX_INT:
        raise argparse.ArgumentTypeError(f"must be at most {SQLITE_MAX_INT} (SQLite's largest integer)")
    return value


def seconds(text):
    value = finite(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def kind_name(text):
    if text not in KINDS:
        raise argparse.ArgumentTypeError(f"must be one of {', '.join(KINDS)}")
    return text


def item_ids(text):
    """A --item list as a set of ids: comma-separated, each an id of 1 to 120 characters."""
    ids = text.split(",")
    if not all(FIELD_VALUE.fullmatch(i) and "," not in i for i in ids):
        raise argparse.ArgumentTypeError("must be a comma-separated list of ids of 1 to 120 characters of letters, digits and _ . : / # @ -")
    return set(ids)


def process_id(text):
    value = int(text)
    if value < 1 or value > SQLITE_MAX_INT:
        raise argparse.ArgumentTypeError("must be a process id above 0")
    return value


def token(text):
    if not text or not text.isascii() or not text.isprintable() or " " in text:
        raise argparse.ArgumentTypeError("must be one line of printable ASCII, no spaces")
    return text


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
    store.add_argument("--store", default=argparse.SUPPRESS, help="the SQLite file (else KB_COORD_STORE, else the project's or the clone's common git directory)")
    parents = [] if remote else [store]
    parser = parser_class(prog="coord.py", description=__doc__.split("\n", 1)[0], parents=parents,
                         epilog="post --kind: " + ", ".join(KINDS) + ". ask takes id, to, ref; answer takes id, state, ref "
                                "(state: " + ", ".join(ANSWER_STATES) + "); coordinate takes item, other, strategy (" + ", ".join(STRATEGIES)
                                + ") and optionally touch, session, operator")
    if not remote:
        parser.add_argument("--url", help="send the command to the server at URL (with --key-file) instead of a local store")
        parser.add_argument("--key-file", help="the file holding this operator's token for --url")
        parser.add_argument("--plain-http", action="store_true", help="allow a plain http --url, or a serve --bind, on a host that is not loopback")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("claim", parents=parents)
    p.add_argument("key")
    p.add_argument("--ttl", type=positive, required=True, help="lease length in seconds")
    p.add_argument("--holder", help=f"name shown to a second claimer (else {HOLDER_ENV}, else anonymous)")
    p.add_argument("--budget", type=positive, help="USD the operator approved for the claimed item (KEY is its id)")
    p = sub.add_parser("renew", parents=parents)
    p.add_argument("key")
    p.add_argument("--token", type=token, required=True)
    p.add_argument("--ttl", type=positive, help="new lease length in seconds (default: the claim's own)")
    p = sub.add_parser("release", parents=parents)
    p.add_argument("key")
    p.add_argument("--token", type=token, required=True)
    p = sub.add_parser("get", parents=parents)
    p.add_argument("key")
    p = sub.add_parser("put", parents=parents)
    p.add_argument("key")
    p.add_argument("--value", required=True)
    p.add_argument("--revision", type=not_negative, required=True, help="the revision the key must still be at (absent: 0)")
    p.add_argument("--token", type=token, help="the holder's token: needed to write a key a live lease holds, refused for a key none holds")
    p = sub.add_parser("list", parents=parents)
    p.add_argument("--prefix", default="")
    p.add_argument("--by-operator", action="store_true", help="print {operators: [...]}, one row per operator of the live claims "
                   "(operator, claims, budget), read from the holders behind serve, instead of the array of keys")
    p = sub.add_parser("post", parents=parents)
    p.add_argument("--kind", required=True, help="one of " + ", ".join(KINDS))
    p.add_argument("--field", action="append", default=[], metavar="NAME=VALUE", help="an id field, repeatable")
    p = sub.add_parser("transition", parents=parents)
    p.add_argument("key", help=f"{RUN_KEYS}<item id>")
    p.add_argument("--to", required=True, metavar="STATE", help="the state to move to, one of " + ", ".join(RUN_STATES))
    p.add_argument("--field", action="append", default=[], metavar="NAME=VALUE", help="one of " + ", ".join(STEP_FIELDS) + ", repeatable")
    p = sub.add_parser("digest", parents=parents)
    p.add_argument("--key", action="append", required=True, metavar="K", help="an item id, topic key or path; repeatable")
    p.add_argument("--lines", type=not_negative, required=True, help="at most this many lines")
    p = sub.add_parser("wait", parents=parents)
    p.add_argument("--since", type=not_negative, required=True, help="the highest sequence the caller has seen (0: all)")
    p.add_argument("--timeout", type=seconds, required=True, help="seconds to block when no event is past SINCE")
    p.add_argument("--kind", type=kind_name, help="return only events of this kind; others do not end the wait")
    p.add_argument("--item", type=item_ids, metavar="IDS", help="return only events whose item field is one of these ids "
                   "(comma-separated); others do not end the wait")
    if not remote:
        p.add_argument("--pid", type=process_id, action="append", metavar="PID", help="also return as soon as this process has "
                       "ended (repeatable; not through --url)")
    p = sub.add_parser("dedup", parents=parents)
    p.add_argument("question")
    p.add_argument("--holder", help=f"name shown to a later question that overlaps this one (else {HOLDER_ENV}, else anonymous)")
    p.add_argument("--topic", type=topic_path, help="the article path to anchor the claim on, instead of the pack's first article")
    p.add_argument("--token", type=token, help="the token an earlier dedup printed: its claims under --holder are yours, not an overlap")
    p.add_argument("--ttl", type=positive, default=DEDUP_SECONDS, help=f"lease length in seconds (default {DEDUP_SECONDS})")
    p.add_argument("--code", type=code_target, action="append", default=[], metavar="REPO:PATH[#SYMBOL]",
                   help="a code target to claim beside the research terms; a claim on a path covers its symbols; repeatable")
    if not remote:
        p = sub.add_parser("serve", parents=parents)
        p.add_argument("--bind", required=True, metavar="[HOST:]PORT", help="host (default 127.0.0.1) and port (0: a free one)")
        p.add_argument("--keys", required=True, metavar="DIR", help="one file per operator, named for it, holding its token")
    return parser


COMMANDS = {"claim": claim, "renew": renew, "release": release, "get": get, "put": put, "list": listing,
            "post": post, "transition": transition, "digest": digest, "wait": wait, "dedup": dedup}


def run(args, clock):
    """One parsed command on args.store: its body and exit code. CLOCK is the function that gives the time in seconds;
    a write command calls it inside its transaction, after the wait for the store's write lock, so a lease runs from
    the time it was granted."""
    try:
        return COMMANDS[args.command](args, clock), 0
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


def open_key_mode(path):
    """The mode of a key file as four octal digits when group or other hold any permission bit, else None (a platform
    without those bits, or a file that cannot be read, is the caller's to meet)."""
    if os.name == "nt":
        return None
    try:
        mode = os.stat(path).st_mode
    except OSError:
        return None
    return f"{mode & 0o7777:04o}" if mode & 0o077 else None


def open_key_text(path, mode):
    return f"coord.py: key file {path} has mode {mode}, so others can read the token: chmod 0600 {path}"


def key_files(keys_dir):
    """The files authenticate reads in keys_dir: (name, path) for each regular file named for an operator, and for each
    one in a subdirectory named for a team, whose name is `team/operator`."""
    out = []
    for name in sorted(os.listdir(keys_dir)):
        path = Path(keys_dir) / name
        if not OPERATOR_NAME.fullmatch(name):
            continue
        if path.is_file():
            out.append((name, path))
        elif path.is_dir():
            for member in sorted(os.listdir(path)):
                if OPERATOR_NAME.fullmatch(member) and (path / member).is_file():
                    out.append((f"{name}/{member}", path / member))
    return out


def authenticate(keys_dir, header):
    """The operator a request comes from, else None: the one file in keys_dir (named for the operator, `team/operator`
    for a file in a team's subdirectory) that holds the bearer token in the Authorization header. Every request reads
    the directory again, so removing a file revokes its operator; a token that two files hold names no one. An OAuth2 bearer-token check replaces or joins this."""
    scheme, _space, token = (header or "").partition(" ")
    token = token.strip().encode("utf-8")
    if scheme.lower() != "bearer" or not token:
        return None
    found = []
    try:
        files = key_files(keys_dir)
    except OSError:
        return None
    for name, path in files:
        if open_key_mode(path):
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
        operator = authenticate(self.server.keys, self.headers.get("Authorization"))
        if operator is None:
            return self.refuse(401, "unknown or revoked token", [("WWW-Authenticate", "Bearer")])
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.refuse(400, "bad Content-Length")
        if not 0 <= size <= BODY_LIMIT:
            return self.refuse(413, f"a request is at most {BODY_LIMIT} bytes")
        if self.path != ENDPOINT:
            return self.refuse(404, f"only POST {ENDPOINT}")
        raw = self.rfile.read(size)
        try:
            argv = json.loads(raw.decode("utf-8"))["argv"]
            if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            return self.refuse(400, 'the body is {"argv": [strings]}')
        try:
            args = build_parser(QuietParser, True).parse_args(argv)
            args.store, args.operator, args.keys = self.server.store, operator, self.server.keys
            header = self.headers.get("Authorization")
            args.recheck = lambda: authenticate(self.server.keys, header) == operator
            body, code = run(args, time.time)
        except Revoked:
            return self.refuse(401, "unknown or revoked token", [("WWW-Authenticate", "Bearer")])
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


def is_loopback(host):
    """True for localhost and a loopback IP address (127.0.0.0/8, ::1, and ::ffff:127.x.x.x)."""
    if host.lower().rstrip(".") == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or bool(getattr(ip, "ipv4_mapped", None) and ip.ipv4_mapped.is_loopback)


def plain_http_refusal(what, host):
    return (f"coord.py: {what} {host} is not loopback and the request carries the token over plain http, in the clear: "
            "reach it through a TLS front end (an https URL), or pass --plain-http to accept the risk")


def serve(args):
    try:
        host, port = split_bind(args.bind)
    except Refused as refused:
        print(f"coord.py: {refused.body['error']}", file=sys.stderr)
        return 2
    if not args.plain_http and not is_loopback(host):
        print(plain_http_refusal("--bind host", host), file=sys.stderr)
        return 2
    if not Path(args.keys).is_dir():
        print(f"coord.py: --keys {args.keys} is not a directory", file=sys.stderr)
        return 2
    try:
        files = key_files(args.keys)
    except OSError as error:
        print(f"coord.py: --keys {args.keys}: {error}", file=sys.stderr)
        return 2
    loose = 0
    for _name, path in files:
        mode = open_key_mode(path)
        if mode:
            print(open_key_text(path, mode), file=sys.stderr)
            loose += 1
    if loose:
        return 2
    try:
        httpd = Server((host, port), args.keys, args.store)
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


def send(url, key_file, argv, plain_http=False):
    """Run the command on the server at url as the operator whose token key_file holds; a plain http url to a host
    that is not loopback is refused unless plain_http."""
    parsed = build_parser(argparse.ArgumentParser, True).parse_args(argv)
    mode = open_key_mode(key_file)
    if mode:
        print(open_key_text(key_file, mode), file=sys.stderr)
        return 2
    try:
        token = Path(key_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        print(f"coord.py: key file {key_file}: {error}", file=sys.stderr)
        return 2
    if not token or not token.isascii() or not token.isprintable() or " " in token:
        print(f"coord.py: key file {key_file} holds no token (one line of printable ASCII, no spaces)", file=sys.stderr)
        return 2
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError as error:
        print(f"coord.py: --url {url[:60]!r} cannot be split: {error}", file=sys.stderr)
        return 2
    if parts.scheme not in ("http", "https") or not parts.hostname:
        print(f"coord.py: --url is http://HOST:PORT or https://HOST[:PORT], not {url[:60]!r}", file=sys.stderr)
        return 2
    if parts.scheme == "http" and not plain_http and not is_loopback(parts.hostname):
        print(plain_http_refusal("--url host", parts.hostname), file=sys.stderr)
        return 2
    where = f"{parts.scheme}://{parts.netloc.rpartition('@')[2]}"
    try:
        port = parts.port
    except ValueError:
        print(f"coord.py: --url port is 0 to 65535, not {parts.netloc.rpartition(':')[2][:20]!r}", file=sys.stderr)
        return 2
    seconds_to_wait = REQUEST_SECONDS + (parsed.timeout if parsed.command == "wait" else PACK_SECONDS if parsed.command == "dedup" else 0)
    try:
        with socket.socket() as probe:
            probe.settimeout(seconds_to_wait)
    except (OverflowError, ValueError):
        print(f"coord.py: --timeout {parsed.timeout:g} is too large for a socket timeout", file=sys.stderr)
        return 2
    connect_to = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    try:
        conn = connect_to(parts.hostname, port, timeout=seconds_to_wait)
        try:
            conn.request("POST", parts.path.rstrip("/") + ENDPOINT, json.dumps({"argv": argv}),
                         {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            response = conn.getresponse()
            status, data = response.status, response.read()
        finally:
            conn.close()
    except (OSError, UnicodeError, http.client.HTTPException) as error:
        print(f"coord.py: cannot reach {where[:80]}: {error}", file=sys.stderr)
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


def git_dir_of(root):
    """The common git directory of the clone at ROOT, which its worktrees share, read from ROOT/.git without git: the
    directory itself, or the directory a `gitdir:` file names less its `commondir` file; None when it is neither."""
    dot = Path(root, ".git")
    try:
        if dot.is_dir():
            return dot
        if not dot.is_file():
            return None
        first = dot.read_text(encoding="utf-8").splitlines()[0]
        if not first.startswith("gitdir:"):
            return None
        git_dir = Path(root, first[len("gitdir:"):].strip())
        common = git_dir / "commondir"
        if common.is_file():
            return Path(git_dir, common.read_text(encoding="utf-8").strip())
        return git_dir if git_dir.is_dir() else None
    except (OSError, UnicodeError, IndexError):
        return None


def store_of(root):
    """kb-coord/coord.sqlite in the common git directory of the clone at ROOT: from `git rev-parse --git-common-dir`,
    else, where git cannot run, from ROOT/.git (`git_dir_of`); None when ROOT is in no git clone."""
    common = None
    try:
        p = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"], capture_output=True, text=True,
                           encoding="utf-8", timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            common = Path(root, p.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    if common is None:
        common = git_dir_of(root)
    return str(common / "kb-coord" / "coord.sqlite") if common else None


def own_store():
    """kb-coord/coord.sqlite in the common git directory of the clone that holds this script, which its worktrees share;
    None when the script is in no git clone (the plugin's installed copy, often)."""
    return store_of(HERE.parent)


def project_store():
    """The store of the project this process serves, when that is not the script's own clone: the clone of
    CLAUDE_PROJECT_DIR (set in a hook), else the one of the working directory. None when no such clone exists, or when
    it is the script's own (its worktrees share the common git directory)."""
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    store = store_of(project if project and Path(project).is_dir() else Path.cwd())
    own = own_store()
    return store if store and (not own or os.path.realpath(store) != os.path.realpath(own)) else None


def default_store():
    """The store a command without --store or KB_COORD_STORE uses: the project's own store (`project_store`, so each
    workspace that installs the plugin has one and no project writes into the plugin's copy), else the script's own
    clone's (the store the coord hook uses there)."""
    return project_store() or own_store()


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    argv = sys.argv[1:] if argv is None else list(argv)
    remote = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    remote.add_argument("--url")
    remote.add_argument("--key-file")
    remote.add_argument("--plain-http", action="store_true")
    named, rest = remote.parse_known_args(argv)
    if named.url or named.key_file:
        if not (named.url and named.key_file):
            print("coord.py: --url and --key-file go together", file=sys.stderr)
            return 2
        try:
            sent = build_parser(QuietParser, True).parse_args(rest)
        except Refused:
            sent = None
        if sent is not None and sent.command in ("claim", "dedup") and not sent.holder and os.environ.get(HOLDER_ENV):
            cut = rest.index("--") if "--" in rest else len(rest)
            rest = [*rest[:cut], "--holder", os.environ[HOLDER_ENV], *rest[cut:]]
        return send(named.url, named.key_file, rest, named.plain_http)
    args = build_parser().parse_args(argv)
    if args.command in ("claim", "dedup") and not args.holder:
        args.holder = os.environ.get(HOLDER_ENV)
    args.store = getattr(args, "store", None) or os.environ.get("KB_COORD_STORE") or default_store()
    if not args.store:
        print("coord.py: no store: pass --store PATH or set KB_COORD_STORE (neither the project nor this script's directory is in "
              "a git clone, which would hold the default)", file=sys.stderr)
        return 2
    if args.command == "serve":
        return serve(args)
    try:
        body, code = run(args, time.time)
    except sqlite3.Error as error:
        print(f"coord.py: store {args.store}: {error}", file=sys.stderr)
        return 2
    emit(body, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
