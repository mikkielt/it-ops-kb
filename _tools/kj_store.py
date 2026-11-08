"""The job queue's store: submit an operation as a job, read a job's state (stdlib only; kb/_self/coordination.md, section
"Operation jobs").

A job is the coord key `job/JB-<8 characters>` holding one JSON record, `{job, op, subject, host, clone, operator, by,
options, state, attempt, submitted_ts}`, and moving by coord's own job table (`coord.JOB_TRANSITIONS`; the move none to
queued is `coord.job_transition`'s). The clone's idempotence is a second key, `jobkey/<sha256 of the clone, the operation
and the subject>`, holding the id of the newest job of that triple.

  submit(root, op, subject, by, options=None, store=None)  -> {job, state, deduped, seq, follow}
  status(root, job, since=0, store=None)                    -> {job, state, exit, step, log, events, last}

`submit` reads the triple's key and that job's record, writes the key and a new job's record in one `BEGIN IMMEDIATE`
transaction (so racing submits meet one winner and the rest read its job), then moves the record from none to queued. A job
in a live state (every state with a move out: queued, running, waiting-lock, waiting-merge, lost) is returned with `deduped`
true, options aside; after a terminal state a submit makes a new job with `attempt` raised by one. A record the winner wrote
and did not yet move (it died between the two) is moved by the next submit. `status` is the one interface the kb MCP
server calls. A refusal is a `kj_ops.Refusal`.
"""
import base64
import hashlib
import json
import os
import platform
import secrets
import sys
import time
from argparse import Namespace
from pathlib import Path

import bl_base
import coord
import kj_ops

JOB_KEYS = coord.JOB_KEYS
TRIPLE_KEYS = "jobkey/"  # the key of one clone, operation and subject: its value is the id of that triple's newest job
ID_PREFIX = "JB-"
TERMINAL = frozenset(state for state, moves in coord.JOB_TRANSITIONS.items() if not moves)
LIVE = frozenset(coord.JOB_STATES) - TERMINAL  # a job in one of these still has a move out: a second submit joins it
LOG_DIR = "kb-jobs"  # in the clone's common git directory: <job id>/output.log, where an executor writes a job's output
LOG_NAME = "output.log"


def resolve_store(root, store):
    """STORE, else KB_COORD_STORE, else the coord store of the clone at ROOT (the one its worktrees share)."""
    found = store or os.environ.get("KB_COORD_STORE") or coord.store_of(root)
    if not found:
        raise kj_ops.Refusal("no coord store: pass --store PATH or set KB_COORD_STORE (ROOT is in no git clone)")
    return str(found)


def clone_path(root):
    """The top of the clone at ROOT as its main checkout, the same for every worktree of it."""
    store = coord.store_of(root)
    if store is None:
        return str(Path(root).resolve())
    common = Path(store).parent.parent
    return str(common.parent if common.name == ".git" else common)


def new_id():
    return ID_PREFIX + base64.b32encode(secrets.token_bytes(5)).decode().lower()


def triple_key(clone, op, subject):
    return TRIPLE_KEYS + hashlib.sha256("\0".join((clone, op, subject)).encode("utf-8")).hexdigest()


def operator_id():
    try:
        import kbwho
        return kbwho.operator().get("id")
    except Exception:  # noqa: BLE001 - no operator id is a record without one, never a refused submit
        return None


def latest_seq(store, job):
    """The newest `job` event of JOB, 0 when it has none."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT seq, fields FROM events WHERE kind = 'job' AND fields LIKE ? ORDER BY seq DESC",
                           (f'%"job": "{job}"%',)).fetchall()
    finally:
        con.close()
    return next((r["seq"] for r in rows if json.loads(r["fields"]).get("job") == job), 0)


def read_record(store, job):
    """The record of JOB, or None when the key is absent or holds no JSON object."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        row = con.execute("SELECT value FROM entries WHERE key = ?", (JOB_KEYS + job,)).fetchone()
    finally:
        con.close()
    return coord.job_record(row["value"]) if row is not None and row["value"] is not None else None


def enqueue(store, key, record):
    """(job id, deduped) after one transaction: the triple's live job when it has one, else RECORD written as a new job
    (its attempt raised by one over the newest job of the triple, when that ended) and the triple's key pointing at it."""
    with coord.Tx(store) as con:
        now = time.time()
        krow = coord.live_row(con, key, now)
        if krow is not None and krow["value"]:
            job = krow["value"]
            jrow = coord.live_row(con, JOB_KEYS + job, now)
            have = coord.job_record(jrow["value"]) if jrow is not None else None
            if have is not None and have.get("state", "none") not in TERMINAL:
                return job, True
            record["attempt"] = int(have.get("attempt", 1)) + 1 if have else 1
        job = record["job"]
        con.execute("INSERT INTO entries (key, value, revision) VALUES (?, ?, 1)",
                    (JOB_KEYS + job, json.dumps(record, sort_keys=True, ensure_ascii=False)))
        if krow is None:
            con.execute("INSERT INTO entries (key, value, revision) VALUES (?, ?, 1)", (key, job))
        else:
            con.execute("UPDATE entries SET value = ?, revision = revision + 1 WHERE key = ?", (job, key))
    return job, False


def queue(store, job, record):
    """Move JOB from none to queued by coord's job table; a job another submit moved first is as it was left."""
    if "queued" not in coord.JOB_TRANSITIONS["none"]:
        raise kj_ops.Refusal("coord's job table no longer moves a new job from none to queued")
    fields = [f"item={record['subject']}"] if record.get("subject") else []
    try:
        coord.job_transition(Namespace(key=JOB_KEYS + job, to="queued", field=fields, store=store), time.time)
    except coord.Refused as refused:
        if refused.code != 1:
            raise


def submit(root, op, subject, by, options=None, store=None):
    """Queue the operation OP on SUBJECT (a backlog id, empty for an operation with none) for the clone at ROOT, or return
    the live job of the same clone, operation and subject. {job, state, deduped, seq, follow}."""
    subject = subject or ""
    by = by or None
    given = kj_ops.check_job(op, subject, by, options)
    if kj_ops.OPS[op]["subject"]:
        bl_base.load_settings(root)
        if not (Path(root) / bl_base.rel_dir() / f"{subject}.json").is_file():
            raise kj_ops.Refusal(f"{subject} is no item of this clone's backlog: a subject is the id of an item file under {bl_base.rel_dir()}")
    store = resolve_store(root, store)
    clone = clone_path(root)
    record = {"job": new_id(), "op": op, "subject": subject, "host": platform.node(), "clone": clone, "operator": operator_id(),
              "by": by, "options": given, "attempt": 1, "submitted_ts": round(time.time(), 3)}
    job, deduped = enqueue(store, triple_key(clone, op, subject), record)
    have = read_record(store, job) or {}
    if have.get("state", "none") == "none":
        queue(store, job, have or record)
        have = read_record(store, job) or {}
    seq = latest_seq(store, job)
    follow = f"python3 _tools/kbjob.py follow {job}"
    return {"job": job, "state": have.get("state", "none"), "deduped": deduped, "seq": seq, "follow": follow}


def log_path(root, job):
    """The job's output file, kb-jobs/<job id>/output.log under the clone's common git directory (None where ROOT is in no clone)."""
    store = coord.store_of(root)
    return Path(store).parent.parent / LOG_DIR / job / LOG_NAME if store else None


def status(root, job, since=0, store=None):
    """{job, state, exit, step, log, events, last} of JOB: the record's state, exit and step (null when it has none), the path
    of its output file (null before the job has run and written it), its `job` events after sequence SINCE and the newest
    sequence the store holds (the next SINCE)."""
    store = resolve_store(root, store)
    if not coord.FIELD_VALUE.fullmatch(str(job)) or "/" in str(job):
        raise kj_ops.Refusal(f"a job is the id JB- and 8 characters, not {str(job)[:40]!r}")
    record = read_record(store, job)
    if not record:
        raise kj_ops.Refusal(f"{job} is no job of this store")
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT * FROM events WHERE seq > ? ORDER BY seq", (int(since),)).fetchall()
    finally:
        con.close()
    events = [coord.event_json(r) for r in rows if r["kind"] == "job" and json.loads(r["fields"]).get("job") == job]
    path = log_path(root, job)
    log = str(path) if path is not None and path.is_file() else None
    return {"job": job, "state": record.get("state", "none"), "exit": record.get("exit"), "step": record.get("step"),
            "log": log, "events": events, "last": rows[-1]["seq"] if rows else int(since)}
