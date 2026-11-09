"""The job queue's store: submit an operation as a job, read a job's state (stdlib only; kb/_self/coordination.md, section
"Operation jobs").

A job is the coord key `job/JB-<8 characters>` holding one JSON record, `{job, op, subject, host, clone, operator, by,
options, state, attempt, submitted_ts, placement}`, and moving by coord's own job table (`coord.JOB_TRANSITIONS`; the move none to
queued is `coord.job_transition`'s). The clone's idempotence is a second key, `jobkey/<sha256 of the clone, the operation
and the subject, for a check its name>`, holding the id of the newest job of that triple.

  submit(root, op, subject, by, options=None, store=None, placement=None)  -> {job, state, deduped, seq, follow}
  status(root, job, since=0, store=None)                    -> {job, state, exit, step, reason, log, placement, events, last}

`submit` reads the triple's key and that job's record, writes the key and a new job's record in one `BEGIN IMMEDIATE`
transaction (so racing submits meet one winner and the rest read its job), then moves the record from none to queued. A job
in a live state (every state with a move out: queued, running, waiting-lock, waiting-merge, lost) is returned with `deduped`
true, options aside; after a terminal state a submit makes a new job with `attempt` raised by one. A record the winner wrote
and did not yet move (it died between the two) is moved by the next submit. `status` is the one interface the kb MCP
server calls. A refusal is a `kj_ops.Refusal`.

A central queue is a `coord.py serve` reached with --url and --key-file (`Remote`, which runs coord.py itself, so its plain-http
refusal and key file mode rule are coord's). `submit_remote` and `status_remote` are `submit` and `status` on it; its job record
adds `remote` (the url of the submitting clone's integration remote); a job's `placement` (the decision of `kj_place`, with `host`;
a job with none is placed on the workstation, `placement_of`) is on the local queue too and, once an executor runs it, `log_host` and `executor`. The central store holds states and
events only: the output log stays on the executor's host. A queued job placed on a workstation whose executor is offline (`jobexec/<host>/<operator>`
unheld) is the executor's of its fallback kind (`kj_exec.Sync.offline`): its `status` has the member `reason`, `executor offline since T`.

A paid job (`kj_ops.PAID`) carries its `budget` (USD) in its options. When the placement decision has a `budget_cap_usd`, `submit`
queues the job only if the spend of its group's finished jobs of the UTC day it is submitted on (`bl_cost.spend_usd` of each
finished job's item, once per item), the budgets of the group's live jobs and this budget stay within the cap, else it raises
`kj_ops.OverCap` naming the three figures and the cap and queues nothing; a group is the jobs placed by the same `decided_by`.
The live budgets are read in the transaction that writes the job, so racing submits meet one cap. Nothing running is stopped.
"""
import base64
import hashlib
import json
import os
import platform
import re
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


def key_subject(subject, given):
    """What the triple's key names besides the operation: the SUBJECT, for an operation with none the check's `name` of its options
    GIVEN, so two checks are two jobs and never one."""
    return subject or str(given.get("name", ""))


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


def records_of(con):
    """The records of every job the store holds, read on CON."""
    rows = con.execute("SELECT value FROM entries WHERE key LIKE ?", (JOB_KEYS + "%",)).fetchall()
    return [r for r in (coord.job_record(row["value"]) for row in rows if row["value"]) if r and r.get("job")]


def budget_of(record):
    """The budget in USD of RECORD's options, 0 for a job with none."""
    value = (record.get("options") or {}).get("budget")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def group_of(record):
    """The group a job's spend counts to: the level that decided its placement (`decided_by`), None for a job with none."""
    placed = record.get("placement")
    return placed.get("decided_by") if isinstance(placed, dict) else None


def utc_day(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def finished_spend(root, records, group, now):
    """USD the query log holds for the items of the finished jobs of GROUP submitted on the UTC day of NOW (`bl_cost.spend_usd`,
    once per item: a scenario or a job with no item adds nothing)."""
    import bl_cost
    day = utc_day(now)
    items = sorted({r.get("subject") for r in records if group_of(r) == group and r.get("state") in TERMINAL
                    and utc_day(r.get("submitted_ts", 0)) == day and kj_ops.ITEM.fullmatch(r.get("subject") or "")})
    if not items:
        return 0.0
    bl_base.load_settings(root)
    backlog = bl_base.Backlog(Path(root))
    return round(sum(bl_cost.spend_usd(backlog, item)[0] for item in items), 6)


def read_records(store):
    """The records of every job the store holds."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        return records_of(con)
    finally:
        con.close()


def cap_guard(placement, budget, spent):
    """The function the transaction calls with the records of the store before it writes a paid job: it raises `kj_ops.OverCap` when
    SPENT, the group's live budgets and BUDGET pass the placement's `budget_cap_usd`; None when PLACEMENT has no cap."""
    cap = placement.get("budget_cap_usd") if isinstance(placement, dict) else None
    if cap is None or not budget:
        return None
    group = placement.get("decided_by")

    def guard(records):
        live = sum(budget_of(r) for r in records if group_of(r) == group and r.get("state") in LIVE)
        if spent + live + budget > cap:
            raise kj_ops.OverCap(f"the budget {budget:g} USD would take {group} past its cap of {cap:g} USD a day: spend today {spent:g} USD "
                                 f"+ live jobs' budgets {live:g} USD + this budget {budget:g} USD = {spent + live + budget:g} USD; nothing is queued")
    return guard


def enqueue(store, key, record, guard=None):
    """(job id, deduped) after one transaction: the triple's live job when it has one, else RECORD written as a new job
    (its attempt raised by one over the newest job of the triple, when that ended) and the triple's key pointing at it. GUARD,
    called with the store's job records before a new job is written, may refuse it by raising."""
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
        if guard is not None:
            guard(records_of(con))
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


def placed(decision):
    """The placement member of a job record: the decision of `kj_place` (a dict) with the submitting host, None for no decision."""
    return {**decision, "host": platform.node()} if isinstance(decision, dict) else None


def submit(root, op, subject, by, options=None, store=None, placement=None):
    """Queue the operation OP on SUBJECT (a backlog id, empty for an operation with none) for the clone at ROOT, or return
    the live job of the same clone, operation and subject. {job, state, deduped, seq, follow}. PLACEMENT, the decision of
    `kj_place.place`, is kept in the record of a new job as `placement`; a live job keeps the one it was queued with."""
    subject = subject or ""
    by = by or None
    given = kj_ops.check_job(op, subject, by, options)
    if kj_ops.item_subject(op):
        bl_base.load_settings(root)
        if not (Path(root) / bl_base.rel_dir() / f"{subject}.json").is_file():
            raise kj_ops.Refusal(f"{subject} is no item of this clone's backlog: a subject is the id of an item file under {bl_base.rel_dir()}")
    store = resolve_store(root, store)
    clone = clone_path(root)
    record = {"job": new_id(), "op": op, "subject": subject, "host": platform.node(), "clone": clone, "operator": operator_id(),
              "by": by, "options": given, "attempt": 1, "submitted_ts": round(time.time(), 3)}
    if placement is not None:
        record["placement"] = placed(placement)
    guard = None
    if op in kj_ops.PAID:
        spent = finished_spend(root, read_records(store), (placement or {}).get("decided_by"), time.time()) if (placement or {}).get("budget_cap_usd") is not None else 0
        guard = cap_guard(placement, given["budget"], spent)
    job, deduped = enqueue(store, triple_key(clone, op, key_subject(subject, given)), record, guard)
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
    """{job, state, exit, step, reason, log, placement, events, last} of JOB: the record's state, exit and step (null when it has none), the path
    of its output file (null before the job has run and written it), its placement (`placement_of`), its `job` events after sequence SINCE and the newest
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
        every = con.execute("SELECT * FROM events WHERE seq <= ? AND kind = 'job' AND fields LIKE ? ORDER BY seq", (int(since), f'%"job": "{job}"%')).fetchall()
    finally:
        con.close()
    mine = lambda found: [coord.event_json(r) for r in found if r["kind"] == "job" and json.loads(r["fields"]).get("job") == job]
    events = reasoned(mine(rows))
    state = record.get("state", "none")
    path = log_path(root, job)
    log = str(path) if path is not None and path.is_file() else None
    return {"job": job, "state": state, "exit": record.get("exit"), "step": record.get("step"), "reason": reason_of(state, reasoned(mine(every)) + events),
            "log": log, "placement": placement_of(record), "events": events, "last": rows[-1]["seq"] if rows else int(since)}


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

    def put(self, key, value, revision, token=None):
        """Whether the write at REVISION (0: the key is new) was made; TOKEN is the lease token of a key whose lease the writer holds."""
        return self.call(["put", key, "--value", value, "--revision", str(revision)] + (["--token", token] if token else []))[0] == 0

    def claim(self, key, ttl, holder):
        """(code, body) of a lease on KEY for TTL seconds: 0 with the body's `token` and `revision`, 1 when another holds it."""
        return self.call(["claim", key, "--ttl", str(ttl), "--holder", holder])

    def renew(self, key, token, ttl):
        """Whether the lease on KEY, held with TOKEN, was renewed for TTL seconds."""
        return self.call(["renew", key, "--token", token, "--ttl", str(ttl)])[0] == 0

    def release(self, key, token):
        self.call(["release", key, "--token", token])

    def lease(self, key):
        """{holder, value, revision} of KEY: `holder` is None once its lease has ended; None when the store holds no such key."""
        code, body = self.call(["get", key])
        return None if code else {"holder": body.get("holder"), "value": body.get("value"), "revision": body.get("revision")}

    def note(self, job, step, state="queued"):
        """Post one `job` event of JOB that moves nothing (it stays in STATE), its step STEP."""
        self.call(["post", "--kind", "job", "--field", f"job={job}", "--field", f"state={state}", "--field", f"step={step}"])

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


def amend_record(store, job, **members):
    """Set the members of JOB's record on STORE (a member given as None is dropped), keeping its state, exit and step as they are."""
    with coord.Tx(store) as con:
        row = con.execute("SELECT value FROM entries WHERE key = ? AND value IS NOT NULL", (JOB_KEYS + job,)).fetchone()
        record = coord.job_record(row["value"]) if row is not None else None
        if not record:
            return
        for name, value in members.items():
            if value is None:
                record.pop(name, None)
            else:
                record[name] = value
        con.execute("UPDATE entries SET value = ?, revision = revision + 1 WHERE key = ?",
                    (json.dumps(record, sort_keys=True, ensure_ascii=False), JOB_KEYS + job))


class LocalRemote:
    """A coord store of this host used as the queue an executor serves, with the calls of `Remote` that `kj_exec` makes: a
    `serve --kind K` with no --url takes the queued jobs of the clone's store placed on K as a central queue's executor does,
    and a workstation executor holds its lease on it. The operator is this host's (`operator_id`), and so is every job's owner."""

    def __init__(self, store):
        self.store, self.url = str(store), "local:" + os.path.realpath(str(store))

    def operator(self):
        return operator_id() or "anonymous"

    def record(self, job):
        return read_record(self.store, job)

    def records(self):
        return sorted(read_records(self.store), key=lambda r: (r.get("submitted_ts", 0), r["job"]))

    def owner(self, job):
        return (self.record(job) or {}).get("operator")

    def move(self, job, state, fields=()):
        """(code, body) of the job table's move of JOB to STATE with FIELDS: 0 done, 1 the table says no, a kj_ops.Refusal for a bad field."""
        try:
            return 0, coord.job_transition(Namespace(key=JOB_KEYS + job, to=state, field=list(fields), store=self.store), time.time)
        except coord.Refused as refused:
            if refused.code != 1:
                raise kj_ops.Refusal(str(refused)) from None
            return 1, refused.body

    def amend(self, job, **members):
        amend_record(self.store, job, **members)
        return True

    def note(self, job, step, state="queued"):
        coord.post(Namespace(kind="job", field=[f"job={job}", f"state={state}", f"step={step}"], store=self.store, operator=None), time.time)

    def lease_call(self, command, **given):
        """(code, body) of coord's COMMAND (claim, renew, release, put) on the store: 1 when its condition fails."""
        try:
            return 0, getattr(coord, command)(Namespace(store=self.store, operator=None, budget=None, **given), time.time)
        except coord.Refused as refused:
            if refused.code != 1:
                raise kj_ops.Refusal(str(refused)) from None
            return 1, refused.body

    def claim(self, key, ttl, holder):
        return self.lease_call("claim", key=key, ttl=ttl, holder=holder)

    def renew(self, key, token, ttl):
        return self.lease_call("renew", key=key, token=token, ttl=ttl)[0] == 0

    def release(self, key, token):
        self.lease_call("release", key=key, token=token)

    def put(self, key, value, revision, token=None):
        return self.lease_call("put", key=key, value=value, revision=revision, token=token)[0] == 0

    def lease(self, key):
        code, body = self.lease_call("get", key=key)
        return None if code else {"holder": body.get("holder"), "value": body.get("value"), "revision": body.get("revision")}


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


EXEC_KEYS = "jobexec/"  # the lease a workstation executor holds while it serves: jobexec/<host>/<operator>, its value {"seen": last renewal}
OFFLINE = re.compile(r"offline-since-(\d{8}T\d{6}Z)(?:-fallback-(workstation|server|ci))?")  # the step of an event that says an executor is offline


def exec_key(host, operator):
    """The key of the lease of the workstation executor of HOST for OPERATOR: `jobexec/<host>/<operator>`, each name cut to the
    characters of a coord key (the others become `-`)."""
    clean = lambda text: re.sub(r"[^A-Za-z0-9_.:@/#-]", "-", str(text or "")).strip("/") or "-"
    return f"{EXEC_KEYS}{clean(host)}/{clean(operator or 'anonymous')}"


def offline_step(since, moved_to=None):
    """The step of the `job` event that says the executor of a queued job's workstation is offline since SINCE (epoch seconds):
    `offline-since-<UTC time>`, with `-fallback-<kind>` when the job moved to the executor kind MOVED_TO."""
    return f"offline-since-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(since))}" + (f"-fallback-{moved_to}" if moved_to else "")


def reasoned(events):
    """EVENTS (`coord.event_json` rows) with, on each whose step is an `offline_step`, the member `reason` (`executor offline since
    <UTC time>`) and, when the job moved, `placement` (the executor kind it moved to)."""
    out = []
    for event in events:
        found = OFFLINE.fullmatch(str((event.get("fields") or {}).get("step") or ""))
        if found:
            since = time.strptime(found.group(1), "%Y%m%dT%H%M%SZ")
            event = {**event, "reason": f"executor offline since {time.strftime('%Y-%m-%dT%H:%M:%SZ', since)}",
                     **({"placement": found.group(2)} if found.group(2) else {})}
        out.append(event)
    return out


def reason_of(state, events):
    """Why a job still queued stays queued: the `reason` of its newest event that has one, null for a job in another state."""
    return next((e["reason"] for e in reversed(events) if "reason" in e), None) if state == "queued" else None


def submit_remote(root, remote, op, subject, by, options=None, placement=None):
    """`submit` on a central queue: {job, state, deduped, seq, follow} of the live job of the same clone (its integration remote's
    url), operator, operation and subject, or of a new job placed as PLACEMENT (a decision of `kj_place.place`) says, else on the
    workstation of this host; a live job keeps its first placement. The triple's key is taken by
    a revision-checked write first, so racing submits meet one winner."""
    subject, by = subject or "", by or None
    given = kj_ops.check_job(op, subject, by, options)
    if kj_ops.item_subject(op):
        bl_base.load_settings(root)
        if not (Path(root) / bl_base.rel_dir() / f"{subject}.json").is_file():
            raise kj_ops.Refusal(f"{subject} is no item of this clone's backlog: a subject is the id of an item file under {bl_base.rel_dir()}")
    url = remote_url(clone_path(root))
    if not url:
        raise kj_ops.Refusal("this clone has no integration remote url to name: a job on a central queue runs in the clone with that url")
    me = remote.operator()
    key = triple_key(url + "\0" + me, op, key_subject(subject, given))
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
            if op in kj_ops.PAID and (placement or {}).get("budget_cap_usd") is not None:  # not atomic: the central store has no transaction to read in
                records = remote.records()
                group = placement.get("decided_by")
                cap_guard(placement, given["budget"], finished_spend(root, records, group, time.time()))(records)
            job = new_id()
            if not remote.put(key, job, revision):
                continue  # another submit won the key
            record = {"job": job, "op": op, "subject": subject, "host": platform.node(), "remote": url, "operator": me, "by": by,
                      "options": given, "attempt": attempt, "submitted_ts": round(time.time(), 3),
                      "placement": placed(placement) or {"executor": WORKSTATION, "host": platform.node()}}
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
    """`status` on a central queue: {job, state, exit, step, reason, log, log_host, placement, events, last}; `log` is null (the output
    log is on the executor's host, `log_host`, null before a job ran)."""
    record = remote_record(remote, job)
    body = remote.events(job, since)
    events = reasoned(body.get("events", []))
    state = record.get("state", "none")
    earlier = reasoned(remote.events(job, 0).get("events", [])) if int(since) and state == "queued" else events
    return {"job": job, "state": state, "exit": record.get("exit"), "step": record.get("step"), "reason": reason_of(state, earlier),
            "log": None, "log_host": record.get("log_host"), "placement": placement_of(record), "events": events,
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
