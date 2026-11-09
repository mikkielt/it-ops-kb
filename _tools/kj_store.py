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

A central queue is a `coord.py serve` reached with --url and --key-file (`Remote`, which runs coord.py itself, so its plain-http
refusal and key file mode rule are coord's). `submit_remote` and `status_remote` are `submit` and `status` on it; its job record
adds `remote` (the url of the submitting clone's integration remote), `placement` (`{executor, host}`; a job with none is placed on
the workstation, `placement_of`) and, once an executor runs it, `log_host` and `executor`. The central store holds states and
events only: the output log stays on the executor's host.
"""
import base64
import hashlib
import json
import os
import platform
import secrets
import subprocess
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
    return found if isinstance(found, str) else str(found)


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


LOG_TAIL_BYTES = 1 << 20  # how far from the end of a log a tail reads
WORKSTATION = "workstation"  # the executor kind of a job with no placement


class Remote:
    """A central coord serve: the url and the key file of one operator, every command run by coord.py itself (`call`)."""

    def __init__(self, url, key_file, plain_http=False):
        self.url, self.key_file, self.plain_http = url, key_file, plain_http
        self._operator = None

    def call(self, argv, wait=0):
        """(exit code, body) of coord.py's command ARGV on the server: 0 done, 1 the command's condition failed; a refusal of the
        client (plain http beyond loopback, a key file others can read, a server that cannot be reached or answers 401)
        is a kj_ops.Refusal."""
        cmd = [sys.executable, str(Path(coord.__file__).resolve()), "--url", self.url, "--key-file", self.key_file]
        cmd += ["--plain-http"] if self.plain_http else []
        try:
            done = subprocess.run(cmd + list(argv), capture_output=True, text=True, encoding="utf-8", timeout=wait + coord.REQUEST_SECONDS + 15)
        except subprocess.TimeoutExpired:
            raise kj_ops.Refusal(f"the central coord at {self.url[:60]} did not answer in time") from None
        if done.returncode not in (0, 1):
            lines = done.stderr.strip().splitlines()
            raise kj_ops.Refusal((lines[-1] if lines else "the central coord refused").removeprefix("coord.py: "))
        try:
            body = json.loads(done.stdout)
        except ValueError:
            body = {}
        return done.returncode, body

    def operator(self):
        """The operator this key file names on the server (`corp/jan.kowalski`), read from the holder of a short lease."""
        if self._operator is None:
            key = f"whoami/{secrets.token_hex(6)}"
            code, body = self.call(["claim", key, "--ttl", "30", "--holder", "kbjob"])
            holder = str(body.get("holder", "")) if code == 0 else ""
            if not holder.endswith("/kbjob") or len(holder) == len("/kbjob"):
                raise kj_ops.Refusal("the central coord names no operator for this key file")
            self._operator = holder[:-len("/kbjob")]
            self.call(["release", key, "--token", body["token"]])
        return self._operator

    def entry(self, key):
        """(revision, value) of KEY, None when it is absent."""
        code, body = self.call(["get", key])
        return None if code else (body["revision"], body.get("value"))

    def put(self, key, value, revision):
        """Whether the write at REVISION (0: the key is new) was made."""
        return self.call(["put", key, "--value", value, "--revision", str(revision)])[0] == 0

    def record(self, job):
        """The record of JOB, None when the central store has none."""
        found = self.entry(JOB_KEYS + job)
        return coord.job_record(found[1]) or None if found else None

    def records(self):
        """The records of every job the central store holds, oldest submit first."""
        code, body = self.call(["list", "--prefix", JOB_KEYS])
        rows = body if code == 0 and isinstance(body, list) else []
        found = [r for r in (coord.job_record(row.get("value")) for row in rows if row.get("value")) if r and r.get("job")]
        return sorted(found, key=lambda r: (r.get("submitted_ts", 0), r["job"]))

    def move(self, job, state, fields=()):
        """(code, body) of the job table's move of JOB to STATE with the FIELDS (`name=value`)."""
        argv = ["transition", JOB_KEYS + job, "--to", state]
        for field in fields:
            argv += ["--field", field]
        return self.call(argv)

    def events(self, job, since, wait=0):
        """The body of a `wait` on the `job` events of JOB after SINCE: {events, last, ...}."""
        return self.call(["wait", "--since", str(int(since)), "--timeout", str(int(wait + 0.999)), "--kind", "job", "--item", job], wait)[1]

    def amend(self, job, **members):
        """Set MEMBERS in the record of JOB (three tries against a record that moved meanwhile); whether it was written."""
        for _ in range(3):
            found = self.entry(JOB_KEYS + job)
            record = coord.job_record(found[1]) if found else None
            if not record:
                return False
            if self.put(JOB_KEYS + job, json.dumps({**record, **members}, sort_keys=True, ensure_ascii=False), found[0]):
                return True
        return False

    def owner(self, job):
        """The operator of the `queued` event of JOB, which the server wrote from the submitter's key: the record's own
        `operator` member is the client's word, this is the server's. None when the store holds no such event."""
        for event in self.events(job, 0).get("events", []):
            if event["fields"].get("state") == "queued":
                return event["fields"].get("operator")
        return None


class Mirror(str):
    """The path of the local store in which an executor of a central queue keeps the jobs it took; `remote` is the queue and
    `kind` the executor kind. Every move made on it is first made on the queue (`kj_exec.move`)."""

    def __new__(cls, path, remote, kind):
        found = super().__new__(cls, path)
        found.remote, found.kind = remote, kind
        return found


def mirror_path(root, remote, kind, data=None):
    """The mirror of the central queue of REMOTE for the executor kind KIND of this key file: in DATA, else in `kb-jobs` of the
    clone's git directory, named by a short hash of the queue's url, the operator and the kind."""
    base = Path(data) if data else Path(coord.store_of(root)).parent.parent / LOG_DIR
    digest = hashlib.sha256("\0".join((remote.url, remote.operator(), kind)).encode("utf-8")).hexdigest()[:8]
    return str(base / f"central-{digest}.sqlite")


def remote_url(clone):
    """The url of the integration remote of the clone at CLONE, empty when it has none."""
    import kbpublic
    return kbpublic.out(["remote", "get-url", kbpublic.integration_remote(clone)], clone) or ""


def placement_of(record):
    """The placement of RECORD: its own `{executor, host, ...}`, or for a job with none the workstation of the submitting host."""
    placed = record.get("placement")
    if isinstance(placed, dict) and placed.get("executor") in coord.PLACEMENT_EXECUTORS:
        return {**placed, "host": placed.get("host") or record.get("host")} if placed["executor"] == WORKSTATION else dict(placed)
    return {"executor": WORKSTATION, "host": record.get("host")}


def submit_remote(root, remote, op, subject, by, options=None):
    """`submit` on a central queue: {job, state, deduped, seq, follow} of the live job of the same clone (its integration remote's
    url), operator, operation and subject, or of a new job placed on the workstation of this host. The triple's key is taken by
    a revision-checked write first, so racing submits meet one winner."""
    subject, by = subject or "", by or None
    given = kj_ops.check_job(op, subject, by, options)
    if kj_ops.OPS[op]["subject"]:
        bl_base.load_settings(root)
        if not (Path(root) / bl_base.rel_dir() / f"{subject}.json").is_file():
            raise kj_ops.Refusal(f"{subject} is no item of this clone's backlog: a subject is the id of an item file under {bl_base.rel_dir()}")
    url = remote_url(clone_path(root))
    if not url:
        raise kj_ops.Refusal("this clone has no integration remote url to name: a job on a central queue runs in the clone with that url")
    me = remote.operator()
    key = triple_key(url + "\0" + me, op, subject)
    fields = [f"item={subject}"] if subject else []
    for _ in range(8):
        found = remote.entry(key)
        revision, attempt, deduped = 0, 1, False
        if found:
            revision, job = found[0], found[1]
            have = remote.record(job)
            if have is None:
                time.sleep(0.25)  # the winner has not written its record yet
                continue
            if have.get("state", "none") not in TERMINAL:
                deduped = True
            else:
                attempt = int(have.get("attempt", 1)) + 1
        if not deduped:
            job = new_id()
            if not remote.put(key, job, revision):
                continue  # another submit won the key
            record = {"job": job, "op": op, "subject": subject, "host": platform.node(), "remote": url, "operator": me, "by": by,
                      "options": given, "attempt": attempt, "submitted_ts": round(time.time(), 3),
                      "placement": {"executor": WORKSTATION, "host": platform.node()}}
            if not remote.put(JOB_KEYS + job, json.dumps(record, sort_keys=True, ensure_ascii=False), 0):
                raise kj_ops.Refusal(f"the central store refused the record of {job}")
            have = record
        if have.get("state", "none") == "none":
            remote.move(job, "queued", fields)  # a refusal means another submit moved it
        now = remote.record(job) or have
        seq = remote.events(job, 0).get("last", 0)
        follow = f"python3 _tools/kbjob.py --url {remote.url} --key-file {remote.key_file} follow {job}"
        return {"job": job, "state": now.get("state", "none"), "deduped": deduped, "seq": seq, "follow": follow}
    raise kj_ops.Refusal("the central store's key of this job kept moving: submit again")


def remote_record(remote, job):
    """The record of JOB on the central queue; a kj_ops.Refusal for an id that is no job id or a job the store does not hold."""
    if not coord.FIELD_VALUE.fullmatch(str(job)) or "/" in str(job):
        raise kj_ops.Refusal(f"a job is the id JB- and 8 characters, not {str(job)[:40]!r}")
    record = remote.record(job)
    if not record:
        raise kj_ops.Refusal(f"{job} is no job of this store")
    return record


def status_remote(remote, job, since=0):
    """`status` on a central queue: {job, state, exit, step, log, log_host, placement, events, last}; `log` is null (the output
    log is on the executor's host, `log_host`, null before a job ran)."""
    record = remote_record(remote, job)
    body = remote.events(job, since)
    return {"job": job, "state": record.get("state", "none"), "exit": record.get("exit"), "step": record.get("step"), "log": None,
            "log_host": record.get("log_host"), "placement": placement_of(record), "events": body.get("events", []),
            "last": body.get("last", int(since))}


def active_remote(remote):
    """The records of every job on the central queue in a state with a move out, with their placement."""
    return [{**r, "placement": placement_of(r)} for r in remote.records() if r.get("state", "none") not in TERMINAL]


def follow_remote(remote, job, since, timeout, out):
    """`follow` on a central queue (`kj_follow.follow`'s lines and exits; the end line names the host that has the log)."""
    import kj_follow
    remote_record(remote, job)
    cursor, deadline = int(since), time.monotonic() + float(timeout)
    while True:
        record = remote_record(remote, job)
        state = record.get("state", "none")
        ended = state in TERMINAL
        wait = 0 if ended else min(max(deadline - time.monotonic(), 0), kj_follow.SLICE_S)
        body = remote.events(job, cursor, wait)
        for event in body.get("events", []):
            print(kj_follow.event_line(event["fields"]), file=out, flush=True)
        cursor = body.get("last", cursor)
        if ended:
            parts = [job, state] + ([f"step={record['step']}"] if record.get("step") is not None else [])
            parts += [f"exit={'-' if record.get('exit') is None else record['exit']}", f"log=host:{record.get('log_host') or '-'}"]
            print(" ".join(parts), file=out, flush=True)
            return kj_follow.FOLLOW_EXIT[state]
        if time.monotonic() >= deadline:
            print(f"follow: still running, continue with --since {cursor}", file=out, flush=True)
            return kj_follow.STILL_RUNNING_EXIT


def log_remote(root, remote, job, count, out):
    """`log` on a central queue: the last COUNT lines of the output log when this host has it, else exit 1 naming the host that
    does (`log_host` of the record)."""
    record = remote_record(remote, job)
    host = record.get("log_host")
    if count < 0:
        raise kj_ops.Refusal("--tail is a count of lines, 0 or more")
    if not host:
        print(f"kbjob.py: {job} has no output log yet", file=sys.stderr)
        return 1
    path = log_path(root, job)
    if host != platform.node() or path is None or not path.is_file():
        print(f"kbjob.py: the output log of {job} is on host {host}", file=sys.stderr)
        return 1
    with open(path, "rb") as f:
        size = f.seek(0, os.SEEK_END)
        f.seek(max(size - LOG_TAIL_BYTES, 0))
        lines = f.read().decode("utf-8", errors="replace").splitlines()
    if size > LOG_TAIL_BYTES and lines:
        lines = lines[1:]
    for line in lines[max(len(lines) - count, 0):] if count else []:
        print(line, file=out)
    return 0


def cancel_remote(remote, job, out):
    """`cancel` on a central queue, for the submitting operator (the server's word, `Remote.owner`) only: the job moves to
    cancelled on the queue and the executor that holds it ends its process group. 0 when it is cancelled, else 1."""
    for _ in range(3):
        record = remote_record(remote, job)
        if remote.owner(job) != remote.operator():
            print(f"kbjob.py: {job} was submitted by another operator: only the submitting operator cancels it", file=sys.stderr)
            return 1
        state = record.get("state", "none")
        if state == "cancelled":
            print(f"{job} cancelled", file=out, flush=True)
            return 0
        if state in TERMINAL or "cancelled" not in coord.JOB_TRANSITIONS.get(state, ()):
            print(f"kbjob.py: {job} is {state}, which does not move to cancelled", file=sys.stderr)
            return 1
        if remote.move(job, "cancelled")[0] == 0:
            note = "queued" if state == "queued" else f"{state}, the executor on {record.get('log_host') or '?'} ends its process group"
            print(f"{job} cancelled ({note})", file=out, flush=True)
            return 0
    print(f"kbjob.py: {job} moved while it was cancelled: try again", file=sys.stderr)
    return 1
