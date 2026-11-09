"""The job executor: `kbjob.py serve` runs the queued jobs of its host, clone and operator, in submit order, at most SLOTS at a
time (stdlib only; kb/_self/coordination.md, section "Operation jobs").

  classify(exit, text)  -> (state, step)  the end of a job's process as the job table's state: exit 0 succeeded; exit 1 and a
                                          line `NAME stopped at step STEP: ...` (`land stopped at step rebase: ...`, as
                                          bl_land.land_refused_step reads it) refused, naming that step; any other end failed
  serve(root, store, once, poll, out)  -> exit code of `kbjob.py serve`
  next_runnable(jobs, running, holders, slots) -> (run, wait): which queued jobs start now and which wait for a lock
  lock_holders(root)                    -> {lock: {pid, clone, step}}: the host main, host test and the clone's landing lock holders
  running_pid(root, store)              -> the pid the store's host file names while it runs, else None
  ping(root, store, out)                -> exit code of `kbjob.py ping` (0 printing the pid, 1 none)
  ensure(root, store, wait)             -> (pid, started, error): starts a detached serve when none runs and waits for the host file
  login_item(root, store, out)          -> prints a LaunchAgent plist and a systemd user unit; writes nothing
  recover(root, store, alive, leased)  ->the moves made on the jobs an executor that died left: a job in running,
                                          waiting-lock or waiting-merge whose lease `jobrun/<job id>` has expired and whose
                                          recorded pid no longer runs moves to lost (step lost), then to queued with its attempt
                                          raised by one the first time and to failed the second time; a job whose child still
                                          runs and names the job's operation is adopted (the lease taken again)

Placement is `next_runnable`: land jobs of one clone run one at a time (the clone's landing lock), sync-push jobs of the host one
at a time (the host main lock), a check tests-full one at a time (the host test lock), done and stage-back jobs one at a time per
item, every other pair in parallel up to SLOTS (`serve --parallel N`), and inside a class in submit order. The executor takes no lock:
the CLI a job runs does, so a hand-run land or sync in a session serialises with it. A job whose class has a lock holder outside
the executor (`lock_holders` less its own children) is moved to waiting-lock, its event step naming the lock only (`lock:host-main`, `lock:landing`, `lock:tests`) and the
record's member `holder` the holder's pid, clone and step (dropped at the next move), and starts when the lock is free, so no child burns the main lock's wait.

A land job runs as `kj_land.drive` in a thread of the executor (`LandRun`): its first pass is `backlog.py land ID --wait-merge 0` as
a child like any job's; a code item's pass that left a merge request moves the job to waiting-merge (event step `merge:<branch>`,
the record's member `pending` holding the shas and the branch) and the thread reads the integration main every 60 s for up to
the job's `wait_merge` option while no child runs, so the wait holds neither a slot nor the landing lock; once the shas are on the
main the thread asks the executor for a slot and the class's turn, moves the job to running and runs the second pass, the same
command, which finishes the item. The job never merges the request. A job found in waiting-merge with a recorded `pending`
(an executor restarted: `recover` leaves it) is taken again by `drain`, which polls from that record without a first pass.

A job is taken with the lease `jobrun/<job id>` (JOB_LEASE_TTL_S, renewed every JOB_LEASE_RENEW_S while the child runs), moved
queued to running, and run as `python <argv of kj_ops.OPS>` in the job's clone: the leader of a process group of its own, stdin
closed, stdout and stderr appended to the job's `kb-jobs/<job id>/output.log` under the clone's common git directory. Every
move goes through `coord.job_transition`, the job table. A job of another operator, host or clone stays queued. One serve
runs per store and host: an exclusive file in the host lock directory (`tests.host_lock_dir`), `kb-jobs-serve.lock` for the clone's own
store and the same name with a short hash of the store path for any other (`lock_name`), holds its pid, clone and start time and
is cleared when that pid is gone, as `kg_lock.main_lock` clears the main lock.

An executor of a central queue (`serve --kind K --url URL --key-file PATH`, `Sync`) keeps its jobs in a mirror store of its own
(`kj_store.Mirror`) and runs them with the code above unchanged: every SYNC_S seconds, from the loop of `drain`, it takes from the
central store each queued job whose placement executor is K (a workstation executor only one placed on this host and submitted by
the operator of its own key file, read from the server's `queued` event), when the clone it serves has the integration remote url the
job names (else the job stays queued and one `job` event with step `no-clone` says why), as a job of the mirror; `move` makes each
move on the central store first, so one job is run by one executor, and a move it could not post is made again by the next sync;
a job the central store cancelled is cancelled in the mirror (`kj_follow.cancel`, which ends its process group). The central store
holds states and events only; the output log stays in this clone's `kb-jobs`, and the job's record names this host as `log_host`.

The job's record keeps the pid of its child (the member `pid`, written after the child starts, dropped when the job is queued
again). Serve runs `recover` at its start and every RECOVER_S seconds, and follows each adopted child (the lease renewed
until its pid ends) instead of starting a second process. An adopted child's exit is not known to serve, so its end is a
loss: the job is requeued once or failed, like any lost job.
"""
import contextlib
import datetime
import hashlib
import json
import os
import platform
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from argparse import Namespace
from pathlib import Path

import coord
import kg_lock
import kj_follow
import kj_land
import kj_ops
import kj_store

LOCK_NAME = "kb-jobs-serve.lock"
JOB_LEASE_TTL_S = 60
JOB_LEASE_RENEW_S = 20
RECOVER_S = 30  # the wait between two recovery passes of a serve
MAX_LOST = 2  # a job lost this many times is failed, not run again: a crash loop ends at attempt 2
IDLE_EXIT_S = 60.0  # how long a serve that `ensure` started for a store of its own waits with no live job before it ends
RECOVERABLE = ("running", "waiting-lock", "waiting-merge", "lost")  # the states a dead executor leaves a job in
LIVE_STATES = ("queued",) + RECOVERABLE  # the states of a job that still has work to do
SLOTS = 3  # how many jobs run at once by default (kbjob.py serve --parallel N)
TICK_S = 0.5  # the wait between two looks of a drain at its children, its waiting jobs and the queue
POLL_S = 5.0  # the wait between two looks at the queue of a serve that does not stop when it is empty (KB_JOB_POLL)
ENSURE_WAIT_S = 10.0  # how long `ensure` waits for the host file to name the executor it started
LOGIN_LABEL = "dev.it-ops-kb.jobs"  # the LaunchAgent label and the systemd unit's name that `login-item --print` gives
LOG_FALLBACK = "serve.log"
STOP_LINE = re.compile(r"^[a-z][a-z-]* stopped at step ([^:\n]+):", re.MULTILINE)


def classify(code, text):
    """(state, step) of a job's end: exit CODE and the output TEXT it wrote. `refused` takes exit 1 and a stop line naming a
    step (the last one), the step as an ops token (lower case, other characters one `-`) because a job field holds no
    space; `failed` is every other end; `succeeded` exit 0. The step is None unless the state is refused."""
    if code == 0:
        return "succeeded", None
    if code == 1:
        found = STOP_LINE.findall(text or "")
        if found:
            return "refused", re.sub(r"[^a-z0-9_.]+", "-", found[-1].lower()).strip("-")[:40] or "step"
    return "failed", None


def exit_number(code):
    """The exit a record keeps: CODE, where a signal ended the child (a negative code) 128 plus the signal, as a shell does."""
    return 128 - code if code < 0 else code


def poll_seconds():
    try:
        n = float(os.environ.get("KB_JOB_POLL", ""))
    except ValueError:
        return POLL_S
    return n if n > 0 and n != float("inf") else POLL_S


def pending(store, clone, host, operator, states=("queued",)):
    """[(job id, record)] of the jobs of this host, clone and operator in one of STATES (the queued ones by default), in submit order."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT key, value FROM entries WHERE key LIKE ? AND value IS NOT NULL", (coord.JOB_KEYS + "%",)).fetchall()
    finally:
        con.close()
    found = []
    for row in rows:
        record = coord.job_record(row["value"])
        if (record and record.get("state") in states and record.get("host") == host and record.get("clone") == clone
                and record.get("operator") == operator and record.get("job") == row["key"][len(coord.JOB_KEYS):]):
            found.append((record["job"], record))
    return sorted(found, key=lambda one: (one[1].get("submitted_ts", 0), one[0]))


def move(store, job, state, **fields):
    """Move JOB to STATE by coord's job table, with the fields given (exit, step); coord.Refused when the table says no."""
    given = [f"{name}={value}" for name, value in fields.items() if value is not None]
    if getattr(store, "remote", None) is not None:
        post_move(store, job, state, given)
    done = coord.job_transition(Namespace(key=coord.JOB_KEYS + job, to=state, field=given, store=store), time.time)
    if state != "waiting-lock":
        drop_holder(store, job)
    return done


def post_move(store, job, state, given):
    """Make the move of JOB to STATE on the central queue of a mirror store first (`coord.Refused` when the queue's job table says
    no, so the job is not run twice): a central queue that cannot be reached refuses a move to running, the one that takes a
    job, and lets any other go on in the mirror, for `Sync` to post again."""
    try:
        code, body = store.remote.move(job, state, given)
    except kj_ops.Refusal as error:
        if state == "running":
            raise coord.Refused({"ok": False, "error": str(error)}, 2) from None
        return
    if code == 1 and body.get("state") != state:
        raise coord.Refused(body, 1)
    if code == 0 and state == "running":
        with contextlib.suppress(kj_ops.Refusal):
            store.remote.amend(job, log_host=platform.node(), executor=store.kind)


SYNC_S = 2.0  # the wait between two syncs of a mirror with its central queue
NO_CLONE = "no-clone"  # the step of the event that says a queued job names an integration remote url this executor's clone lacks


class Sync:
    """What an executor of a central queue does between two looks of `drain` at its jobs: `__call__` takes the queue's jobs for
    its kind into the mirror store and brings the two stores' states together (the central store's cancel, a move not posted)."""

    def __init__(self, root, store, clone, out):
        self.root, self.store, self.clone, self.out = root, store, clone, out
        self.remote, self.kind = store.remote, store.kind
        self.host, self.operator = platform.node(), kj_store.operator_id()
        self.last, self.noted = None, {}

    def __call__(self):
        if self.last is not None and time.monotonic() - self.last < SYNC_S:
            return
        self.last = time.monotonic()
        try:
            self.reconcile()
            self.pull()
        except kj_ops.Refusal as error:
            print(f"kbjob.py: central queue: {error}", file=self.out, flush=True)

    def mirrored(self):
        return pending(self.store, self.clone, self.host, self.operator, coord.JOB_STATES)

    def reconcile(self):
        """The central store's cancel applied to the mirror (the job's process group ended), a job another executor took dropped
        from the mirror, and a state the mirror reached and the queue lacks posted."""
        for job, local in self.mirrored():
            central = self.remote.record(job)
            if central is None or central.get("state") == local.get("state"):
                continue
            theirs, mine = central.get("state", "none"), local.get("state")
            if theirs == "cancelled" and mine not in kj_store.TERMINAL:
                kj_follow.cancel(self.root, self.store, job, open(os.devnull, "w", encoding="utf-8"))
            elif mine == "queued" and theirs != "queued":
                kj_follow.move_cancelled(self.store, job)
            elif theirs not in kj_store.TERMINAL:
                fields = [f"{name}={local[name]}" for name in ("exit", "step") if local.get(name) is not None]
                if self.remote.move(job, mine, fields)[0] and mine != "running":
                    self.remote.move(job, "running")
                    self.remote.move(job, mine, fields)

    def reason(self, job, step):
        """Say once per serve, as one `job` event and a line, why the queued JOB is left queued."""
        if self.noted.get(job) != step:
            self.noted[job] = step
            self.remote.call(["post", "--kind", "job", "--field", f"job={job}", "--field", "state=queued", "--field", f"step={step}"])
            print(f"{job} stays queued: step {step} (no clone here with the job's integration remote url)", file=self.out, flush=True)

    def pull(self):
        """Take each queued job of the central store placed on this kind into the mirror, in submit order."""
        have = {job for job, _ in self.mirrored()}
        url = kj_store.remote_url(self.clone)
        for record in self.remote.records():
            job = record["job"]
            if record.get("state") != "queued" or job in have:
                continue
            placed = kj_store.placement_of(record)
            if placed["executor"] != self.kind:
                continue
            if self.kind == kj_store.WORKSTATION and (placed.get("host") != self.host or self.remote.owner(job) != self.remote.operator()):
                continue
            if not url or record.get("remote") != url:
                self.reason(job, NO_CLONE)
                continue
            mirrored = {k: v for k, v in record.items() if k not in ("state", "exit", "step")}
            mirrored.update(host=self.host, clone=self.clone, operator=self.operator)
            with coord.Tx(self.store) as con:
                if con.execute("SELECT 1 FROM entries WHERE key = ?", (coord.JOB_KEYS + job,)).fetchone() is None:
                    con.execute("INSERT INTO entries (key, value, revision) VALUES (?, ?, 1)",
                                (coord.JOB_KEYS + job, json.dumps(mirrored, sort_keys=True, ensure_ascii=False)))
            kj_store.queue(self.store, job, mirrored)


def own_store(root, store):
    """Whether STORE is the clone's own coord store, the one its sessions share (a clone with none has no other)."""
    own = coord.store_of(root)
    return own is None or os.path.realpath(store) == os.path.realpath(own)


def lock_name(root, store):
    """The name of the serve lock file of STORE: LOCK_NAME for the clone's own store (the one its sessions share), else the same
    name with a short hash of the resolved store path, so a serve of another store neither blocks nor is blocked by it."""
    if own_store(root, store):
        return LOCK_NAME
    return f"{LOCK_NAME[:-len('.lock')]}-{hashlib.sha256(os.path.realpath(store).encode('utf-8')).hexdigest()[:8]}.lock"


def take_lock(clone, name=LOCK_NAME):
    """Take the serve lock NAME of the host: (path, None) when this process now holds it, (None, holder) when a live process does, holder
    being {pid, clone, started}. A lock whose pid no longer runs, or whose record stays unwritten past the grace, is cleared."""
    import tests as tests_py  # the test lock's helpers, as kg_lock uses them
    path = os.path.join(tests_py.host_lock_dir(), name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    me = f"pid={os.getpid()}\nclone={clone}\nstarted={stamp}\n"
    until = time.monotonic() + tests_py.lock_grace() + 1
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            text = tests_py.read_lock(path)
            holder = tests_py.parse_holder(text or "")
            if text is None and not os.path.exists(path):  # released: look again
                continue
            if holder is None and time.monotonic() < until:  # its holder has not written the record yet
                time.sleep(0.1)
                continue
            if holder is not None and tests_py.pid_alive(holder["pid"]):
                return None, holder
            tests_py.clear_stale(path, text)
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(me)
        return path, None


def drop_lock(path):
    import tests as tests_py
    holder = tests_py.read_holder(path)
    if holder and holder["pid"] == os.getpid():
        with contextlib.suppress(OSError):
            os.unlink(path)


def last_line(text):
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1][:200] if lines else ""


def start_child(record, clone, log):
    """Start the job's process in CLONE as the leader of a process group of its own, stdin closed, its stdout and stderr
    appended to LOG: (the process, the size LOG had before it: where this run's output begins)."""
    log.parent.mkdir(parents=True, exist_ok=True)
    start = log.stat().st_size if log.exists() else 0
    options = record.get("options")
    if record["op"] == "land":  # a land job's passes never wait inside the CLI: the job waits for the merge request (`LandRun`)
        options = {**(options or {}), "wait_merge": 0}
    argv = [sys.executable] + kj_ops.argv(record["op"], record.get("subject", ""), options)
    group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    with open(log, "ab") as sink:
        proc = subprocess.Popen(argv, cwd=clone, stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT, **group)
    return proc, start


def finish_text(log, start):
    with open(log, "rb") as f:
        f.seek(start)
        return f.read().decode("utf-8", errors="replace")


RUN_BUCKETS = {"queued": "queued_ms", "lost": "queued_ms", "waiting-lock": "wait_ms", "waiting-merge": "wait_ms", "running": "run_ms"}
RUN_ENDS = ("succeeded", "refused", "failed", "cancelled")  # the terminal states, each of which writes one job.run row (a lost job writes none until it ends)


def job_events(store, job):
    """[(state, at)] of JOB's `job` events in sequence order, `at` in seconds."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT fields, at FROM events WHERE kind = 'job' AND fields LIKE ? ORDER BY seq", (f"%{job}%",)).fetchall()
    finally:
        con.close()
    found = []
    for row in rows:
        fields = json.loads(row["fields"])
        if fields.get("job") == job:
            found.append((fields.get("state"), row["at"]))
    return found


def run_times(events):
    """{queued_ms, wait_ms, run_ms} of the last attempt in EVENTS ([(state, at)]): the time between each event and the next
    counted to its state (queued and lost: queued_ms; waiting-lock and waiting-merge: wait_ms; running: run_ms), from the
    last `lost` event on, so a job a dead executor lost counts the attempt that ended it."""
    first = max((i for i, (state, _) in enumerate(events) if state == "lost"), default=0)
    times = {"queued_ms": 0, "wait_ms": 0, "run_ms": 0}
    for (state, at), (_, later) in zip(events[first:], events[first + 1:]):
        if state in RUN_BUCKETS:
            times[RUN_BUCKETS[state]] += max(0, round((later - at) * 1000))
    return times


def record_run(store, job, record, state):
    """Write the ops row `job.run` of a job that ended in STATE (succeeded, refused, failed or cancelled; none for another): its operation,
    the end as `class`, its attempt and the milliseconds it queued, waited for a lock or a merge, and ran, read from the job's own
    events (`ql_deliver.ops_row`: nothing in a test run). Never raises: a job never fails for its log."""
    try:
        if state not in RUN_ENDS:
            return
        import ql_deliver
        now = kj_store.read_record(store, job) or record
        ql_deliver.ops_row("job.run", op=record["op"], **{"class": state}, attempt=int(now.get("attempt", 1)), **run_times(job_events(store, job)))
    except Exception:  # noqa: BLE001 - see the docstring
        pass


def start_job(store, job, record, clone, log, out):
    """Start the child of a job already in running: (the process, the size LOG had before it) and the pid recorded in the job's record.
    A process that cannot start moves the job to failed (exit 127), prints one line and returns (None, 0)."""
    try:
        proc, start = start_child(record, clone, log)
    except OSError as error:
        move(store, job, "failed", exit=127)
        record_run(store, job, record, "failed")
        print(f"{job} {record['op']} {record.get('subject') or '-'}: failed, exit 127: {str(error)[:200]}", file=out, flush=True)
        return None, 0
    with contextlib.suppress(sqlite3.Error):
        amend(store, job, pid=proc.pid)
    return proc, start


def finish_job(store, job, record, code, text, out):
    """Move a job whose child ended with exit CODE and output TEXT to the state classify gives, with one line printed; returns the
    state it moved to. A job cancelled meanwhile (kbjob.py cancel) stays cancelled, one line says so and cancelled is returned."""
    state, step = classify(code, text)
    number = exit_number(code)
    try:
        move(store, job, state, exit=number, step=step)
    except coord.Refused as refusal:
        if refusal.body.get("state") != "cancelled":
            raise
        record_run(store, job, record, "cancelled")
        print(f"{job} {record['op']} {record.get('subject') or '-'}: cancelled", file=out, flush=True)
        return "cancelled"
    record_run(store, job, record, state)
    note = f"{job} {record['op']} {record.get('subject') or '-'}: {state}"
    if state == "refused":
        note += f" at step {step}"
    elif state == "failed":
        note += f", exit {number}: {last_line(text)}"
    print(note, file=out, flush=True)
    return state


def run_job(store, job, record, clone, log, token, out):
    """Run one taken job (already in running) to its end with the lease renewed, in the calling thread; returns the state it moved
    to: `start_job`, a wait that renews the lease, then `finish_job`. A process that cannot start moves the job to failed (exit
    127); a signal to this process ends the child's group and moves the job to lost, then goes on; a job cancelled meanwhile
    (kbjob.py cancel) stays cancelled, one line says so and cancelled is returned. `drain` runs its jobs by the same two steps."""
    proc, start = start_job(store, job, record, clone, log, out)
    if proc is None:
        return "failed"
    try:
        while True:
            try:
                code = proc.wait(timeout=JOB_LEASE_RENEW_S)
                break
            except subprocess.TimeoutExpired:
                with contextlib.suppress(coord.Refused):
                    coord.renew(Namespace(key=lease_key(job), token=token, ttl=None, store=store), time.time)
    except BaseException:
        kg_lock.end_group(proc)
        with contextlib.suppress(coord.Refused):
            move(store, job, "lost")
        raise
    return finish_job(store, job, record, code, finish_text(log, start), out)


def lease_key(job):
    return "jobrun/" + job


def take_job(store, job):
    """The lease token of JOB, or None when another executor holds the lease."""
    try:
        got = coord.claim(Namespace(key=lease_key(job), holder=f"serve-{os.getpid()}", ttl=JOB_LEASE_TTL_S, store=store, budget=None), time.time)
    except coord.Refused:
        return None
    return got["token"]


def drop_holder(store, job):
    """Drop the member `holder` (the lock holder a waiting-lock job names) from JOB's record, if it has one: every move out of
    waiting-lock, to running or to a terminal state, leaves none."""
    with contextlib.suppress(sqlite3.Error):
        record = kj_store.read_record(store, job)
        if record and "holder" in record:
            amend(store, job, holder=None)


def amend(store, job, **members):
    """Set the members of JOB's record (a member given as None is dropped), keeping its state, exit and step as they are."""
    with coord.Tx(store) as con:
        row = con.execute("SELECT value, revision FROM entries WHERE key = ? AND value IS NOT NULL", (coord.JOB_KEYS + job,)).fetchone()
        record = coord.job_record(row["value"]) if row is not None else None
        if not record:
            return
        for name, value in members.items():
            if value is None:
                record.pop(name, None)
            else:
                record[name] = value
        con.execute("UPDATE entries SET value = ?, revision = revision + 1 WHERE key = ?",
                    (json.dumps(record, sort_keys=True, ensure_ascii=False), coord.JOB_KEYS + job))


def lease_live(store, key):
    """Whether the lease KEY is held and not expired."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        row = con.execute("SELECT holder, expires FROM entries WHERE key = ?", (key,)).fetchone()
    finally:
        con.close()
    return row is not None and row["holder"] is not None and (row["expires"] or 0) > time.time()


def child_runs(pid, record):
    """Whether PID runs and its command line names the job's operation: the script of the operation's argument list and, for
    a job with a subject, that item id. POSIX only (the command line is read with `ps`); False elsewhere and for no pid."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or os.name != "posix" or not coord.process_runs(pid):
        return False
    try:
        text = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
        argv = kj_ops.argv(record["op"], record.get("subject", ""), record.get("options"))
    except (OSError, subprocess.SubprocessError, KeyError, kj_ops.Refusal):
        return False
    names = [Path(argv[0]).name] + ([record["subject"]] if record.get("subject") else [])
    return all(name in text for name in names)


def lost_count(store, job):
    """How many times JOB has been moved to lost."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT fields FROM events WHERE kind = 'job' AND fields LIKE ?", (f'%"job": "{job}"%',)).fetchall()
    finally:
        con.close()
    fields = [json.loads(r["fields"]) for r in rows]
    return sum(1 for f in fields if f.get("job") == job and f.get("state") == "lost")


def settle_lost(store, job, record):
    """The move that follows a loss of JOB, now in lost: queued again with its attempt raised by one the first time, failed
    (step lost) when it was lost MAX_LOST times. The move made as {job, op, subject, move, attempt}."""
    one = {"job": job, "op": record.get("op"), "subject": record.get("subject", "")}
    if lost_count(store, job) >= MAX_LOST:
        move(store, job, "failed", step="lost")
        record_run(store, job, record, "failed")
        return {**one, "move": "failed", "attempt": int(record.get("attempt", 1))}
    attempt = int(record.get("attempt", 1)) + 1
    amend(store, job, attempt=attempt, pid=None)
    move(store, job, "queued", attempt=attempt)
    return {**one, "move": "queued", "attempt": attempt}


def recover(root, store=None, alive=None, leased=None):
    """One recovery pass over the jobs of this host, clone and operator that a dead executor left in running, waiting-lock,
    waiting-merge or lost, except a land job in waiting-merge with a recorded `pending`, which `drain` resumes. A job whose lease `jobrun/<job id>` is held is left alone (`leased(key)`, by default the store's
    lease). One whose recorded pid still runs (`alive(pid)`, by default `child_runs`: the pid runs and its command line names
    the job's operation) is adopted: the lease is taken again and the move `adopted` returned with its pid and lease token.
    Any other moves to lost (step lost; a waiting job through running, as coord's table has it), then settle_lost. Returns the
    moves made, in order, each {job, op, subject, move, ...}; a job another process moved meanwhile is skipped."""
    store = kj_store.resolve_store(root, store)
    clone, host, operator = kj_store.clone_path(root), platform.node(), kj_store.operator_id()
    leased = leased or (lambda key: lease_live(store, key))
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT key, value FROM entries WHERE key LIKE ? AND value IS NOT NULL", (coord.JOB_KEYS + "%",)).fetchall()
    finally:
        con.close()
    found = []
    for row in rows:
        record = coord.job_record(row["value"])
        if (record and record.get("state") in RECOVERABLE and record.get("host") == host and record.get("clone") == clone
                and record.get("operator") == operator and record.get("job") == row["key"][len(coord.JOB_KEYS):]):
            found.append(record)
    moves = []
    for record in sorted(found, key=lambda r: (r.get("submitted_ts", 0), r["job"])):
        job, state = record["job"], record["state"]
        one = {"job": job, "op": record.get("op"), "subject": record.get("subject", "")}
        if leased(lease_key(job)):
            continue
        if state == "waiting-merge" and record.get("op") == "land" and kj_land.recorded_pending(record):
            continue  # a land job in its wait: `drain` takes it again and polls from its recorded pending, no first pass
        try:
            if state != "lost":
                pid = record.get("pid")
                if (alive(pid) if alive is not None else child_runs(pid, record)):
                    token = take_job(store, job)
                    if token is not None:
                        moves.append({**one, "move": "adopted", "pid": pid, "token": token})
                    continue
                if state != "running":
                    move(store, job, "running")
                move(store, job, "lost", step="lost")
                moves.append({**one, "move": "lost"})
            moves.append(settle_lost(store, job, record))
        except coord.Refused:
            continue
    return moves


def follow_adopted(store, adopted, out):
    """Follow the child an adopted job runs as, with the lease renewed until its pid no longer runs (or the job is cancelled,
    which ends the child's group), then release the lease. The child's exit is unknown, so its end is a loss: the job moves
    to lost and settle_lost requeues or fails it. Returns the move made, None when the job left its state meanwhile."""
    job, pid, token = adopted["job"], adopted["pid"], adopted["token"]
    renewed = time.monotonic()
    try:
        while isinstance(pid, int) and coord.process_runs(pid):
            record = kj_store.read_record(store, job) or {}
            if record.get("state") == "cancelled":
                kj_follow.end_group(pid)
                return None
            if time.monotonic() - renewed >= JOB_LEASE_RENEW_S:
                with contextlib.suppress(coord.Refused):
                    coord.renew(Namespace(key=lease_key(job), token=token, ttl=None, store=store), time.time)
                renewed = time.monotonic()
            time.sleep(1)
        record = kj_store.read_record(store, job) or {}
        try:
            if record.get("state") != "running":
                move(store, job, "running")
            move(store, job, "lost", step="lost")
            return settle_lost(store, job, record)
        except coord.Refused:
            return None
    finally:
        with contextlib.suppress(coord.Refused):
            coord.release(Namespace(key=lease_key(job), token=token, store=store, operator=None), time.time)


def recovery_pass(root, store, out):
    """recover, then follow each adopted child; the ids of the jobs it failed, one line printed per move."""
    failed = []
    for one in recover(root, store):
        followed = [one]
        if one["move"] == "adopted":
            print(f"{one['job']} {one['op']} {one['subject'] or '-'}: adopted, pid {one['pid']} runs on", file=out, flush=True)
            end = follow_adopted(store, one, out)
            followed = [end] if end else []
        for done in followed:
            if done["move"] == "adopted":
                continue
            note = f"{done['job']} {done['op']} {done['subject'] or '-'}: {done['move']}"
            if done["move"] == "queued":
                note += f" again, attempt {done['attempt']}"
            elif done["move"] == "failed":
                note += ", lost twice"
                failed.append(done["job"])
            print(note, file=out, flush=True)
    return failed


class Stopped(Exception):
    """The executor is ending: a land thread leaves its job as it is (a job in the wait stays in waiting-merge for the next serve)."""


class Cancelled(Exception):
    """The job was cancelled (kbjob.py cancel) while its thread ran."""


class Ended(Exception):
    """The job already moved to a final state (args[0]) before `kj_land.drive` posted one: a process that could not start."""


class LandRun(threading.Thread):
    """One land job in a thread of the executor, run by `kj_land.drive`: the passes are children as any job's (the thread waits
    for them with the lease renewed), the wait for the merge request is a read of the integration main every `kj_land.POLL_S`
    seconds with no child, and `passing` says whether the job holds a slot and its class (a pass runs; the wait does not).
    The drain places it: `want` is set when the shas are on the main and the second pass asks for its turn, `granted` is
    what the drain sets when `next_runnable` gives it. `state` is the job's end (succeeded, refused, failed, lost,
    cancelled) once the thread is over, None when the executor left a waiting job as it was."""

    CHECK_S = 5.0  # the wait between two looks at whether the job was cancelled

    def __init__(self, store, clone, record, token, out):
        super().__init__(daemon=True)
        self.store, self.clone, self.record, self.token, self.out = store, clone, record, token, out
        self.job = record["job"]
        self.log = kj_store.log_path(clone, self.job)
        self.at = "waiting-merge" if record.get("state") == "waiting-merge" else "running"  # the state the job table holds
        self.passing, self.want, self.state, self.proc, self.text = self.at == "running", False, None, None, ""
        self.halt, self.granted = threading.Event(), threading.Event()
        self.renewed = self.checked = time.monotonic()

    def label(self):
        return f"{self.job} land {self.record.get('subject') or '-'}"

    def keep(self):
        """Renew the lease when due and look whether the job was cancelled (Cancelled)."""
        now = time.monotonic()
        if now - self.renewed >= JOB_LEASE_RENEW_S:
            with contextlib.suppress(coord.Refused):
                coord.renew(Namespace(key=lease_key(self.job), token=self.token, ttl=None, store=self.store), time.time)
            self.renewed = now
        if now - self.checked >= self.CHECK_S:
            self.checked = now
            if (kj_store.read_record(self.store, self.job) or {}).get("state") == "cancelled":
                raise Cancelled

    def sleep(self, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            if self.halt.wait(min(until - time.monotonic(), 1.0)):
                raise Stopped
            self.keep()

    def place(self):
        """Wait until the drain gives the second pass its slot and its class's turn."""
        self.want = True
        while not self.granted.wait(0.2):
            if self.halt.is_set():
                raise Stopped
            self.keep()
        self.granted.clear()
        self.want, self.passing = False, True

    def merged(self, shas):
        """Whether SHAS are on the integration main (a fetch, as `land` reads it); when they are, the second pass's place is taken first."""
        import bl_land
        import kbpublic
        try:
            on_main = bl_land.merged_on_main(self.clone, kbpublic.integration_remote(self.clone), shas)
        except bl_land.Refused:  # a fetch that timed out: read again at the next poll
            return False
        if on_main:
            self.place()
        return on_main

    def pending(self):
        import bl_land
        return bl_land.pending_merge(self.clone, self.record.get("subject", ""))

    def run_pass(self, second):
        """One pass of the CLI as a child: (exit, its output, the merge request a first pass left, or None)."""
        proc, start = start_job(self.store, self.job, self.record, self.clone, self.log, self.out)
        if proc is None:
            raise Ended("failed")
        self.proc = proc
        try:
            while True:
                try:
                    code = proc.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    if self.halt.is_set():
                        raise Stopped from None
                    self.keep()
        except BaseException:
            kg_lock.end_group(proc)
            raise
        finally:
            self.proc = None
        self.text = finish_text(self.log, start)
        code = exit_number(code)
        wait = (self.record.get("options") or {}).get("wait_merge", kj_land.WAIT_MERGE_S)
        return code, self.text, (self.pending() if not second and code == 0 and wait else None)

    def post(self, state, **fields):
        """Move the job to STATE through the job table (`pending` in FIELDS: the merge request the waiting-merge move records)."""
        pending = fields.pop("pending", None)
        if state == "running" and self.at == "running":  # the drain moved it before the first pass
            return
        if state == "waiting-merge":
            amend(self.store, self.job, pending={"shas": list(pending[0]), "branch": pending[1]}, pid=None)
        try:
            if self.at == "waiting-merge" and state not in ("running", "waiting-merge"):  # the table ends a job from running only
                move(self.store, self.job, "running")
                self.at = "running"
            move(self.store, self.job, state, **fields)
        except coord.Refused as refusal:
            if refusal.body.get("state") == "cancelled":
                raise Cancelled from None
            raise
        self.at = state
        if state == "waiting-merge":
            self.passing = False
            print(f"{self.label()}: waiting-merge, {fields['step'][len('merge:'):]} not merged yet", file=self.out, flush=True)
            return
        with contextlib.suppress(sqlite3.Error):
            amend(self.store, self.job, pending=None)
        if state in RUN_ENDS:
            record_run(self.store, self.job, self.record, state)
            note = f"{self.label()}: {state}"
            if state == "refused":
                note += f" at step {fields.get('step')}"
            elif state == "failed":
                note += f", exit {fields.get('exit')}: {last_line(self.text)}"
            print(note, file=self.out, flush=True)

    def lose(self):
        """The executor ended while a pass ran (the child's group is ended): the job moves to lost, as any running job's does."""
        with contextlib.suppress(coord.Refused):
            if self.at == "running":
                move(self.store, self.job, "lost")
        self.state = "lost"

    def run(self):
        try:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log, "a", encoding="utf-8", newline="\n") as sink:
                _, self.state = kj_land.drive(self.record, self.run_pass, self.merged, self.sleep, self.post, out=sink)
        except Cancelled:
            self.state = "cancelled"
            record_run(self.store, self.job, self.record, "cancelled")
            print(f"{self.label()}: cancelled", file=self.out, flush=True)
        except Ended as ended:
            self.state = ended.args[0]
        except Stopped:
            if self.at == "running":
                self.lose()
        except BaseException as error:  # noqa: BLE001 - a thread's failure ends its job, never the executor
            self.state = "failed"
            with contextlib.suppress(Exception):
                if self.at != "running":
                    move(self.store, self.job, "running")
                move(self.store, self.job, "failed", exit=1)
                record_run(self.store, self.job, self.record, "failed")
            print(f"{self.label()}: failed, exit 1: {type(error).__name__}: {str(error)[:200]}", file=self.out, flush=True)


def serial_key(job):
    """(the key of the one-at-a-time class of JOB, the lock a holder outside the executor keeps it waiting for), each None for none:
    land is one at a time per clone (the clone's landing lock `landing`), sync-push per host (the host main lock `host-main`),
    the check tests-full per host (the host test lock `host-test`), done and stage-back per item (the run-state table); every
    other job is of no class."""
    op, opts = job.get("op"), job.get("options") or {}
    if op == "land":
        return ("land", job.get("clone")), "landing"
    if op == "sync-push":
        return ("sync-push",), "host-main"
    if op == "check" and opts.get("name") == "tests-full":
        return ("tests-full",), "host-test"
    if op in ("done", "stage-back"):
        return ("item", job.get("subject")), None
    return None, None


def next_runnable(jobs, running, holders, slots=SLOTS):
    """(run, wait) for JOBS, the jobs of the queue in submit order (those in state queued or waiting-lock count, others are
    ignored). RUNNING holds the jobs the executor runs now (state running): they take a slot and their class. HOLDERS is
    {lock: {pid, clone, step}} of the locks a process outside the executor holds (`lock_holders`, `outside`). A job runs when
    no earlier job of its class (serial_key) is running or ahead of it and a slot is free (SLOTS less the running ones);
    the first job of a class whose lock has a holder is not started but waits: `wait` holds (job, lock, holder) for each such job
    still in queued (one already in waiting-lock is not told again), and a waiting job takes no slot. A job behind another of
    its class stays queued, so submit order holds inside a class."""
    taken = {key for key, _ in (serial_key(j) for j in running) if key is not None}
    free = slots - len(running)
    run, wait = [], []
    for job in jobs:
        state = job.get("state")
        if state not in ("queued", "waiting-lock"):
            continue
        key, lock = serial_key(job)
        if key is not None:
            if key in taken:
                continue
            taken.add(key)
        held = holders.get(lock) if lock else None
        if held:
            if state == "queued":
                wait.append((job, lock, held))
            continue
        if free > 0:
            free -= 1
            run.append(job)
    return run, wait


def lock_holders(root=None):
    """{lock: {pid, clone, step}} for each lock of the host a live process holds, read from the lock files as `kg_lock.main_lock`
    and `tests.py` write them: `host-main` (kb-main.lock, step as the holder gave it), `host-test` (kb-tests.lock, step `tests`)
    and, for a ROOT in a clone, `landing` (kb-landing.lock in the git common directory, step `land ITEM`). A lock with no file, no
    record or a pid that no longer runs is left out."""
    import tests as tests_py
    found = {}
    paths = {"host-main": os.path.join(tests_py.host_lock_dir(), kg_lock.LOCK_NAME),
             "host-test": os.path.join(tests_py.host_lock_dir(), tests_py.HOST_LOCK_NAME)}
    if root is not None:
        with contextlib.suppress(Exception):
            import bl_close
            paths["landing"] = str(bl_close.landing_lock_path(root))
    for lock, path in paths.items():
        text = tests_py.read_lock(path)
        holder = tests_py.parse_holder(text) if text is not None else None
        if holder is None or not tests_py.pid_alive(holder["pid"]):
            continue
        if lock == "host-main":
            step = kg_lock.holder_step(text)
        elif lock == "host-test":
            step = "tests"
        else:
            item = next((ln[len("item="):] for ln in text.splitlines() if ln.startswith("item=")), "")
            step = f"land {item}" if item else "land"
        found[lock] = {"pid": holder["pid"], "clone": holder["clone"], "step": step}
    return found


def inside(pid, pids):
    """Whether process PID is one of PIDS or a member of the process group one of them leads (a job's child leads its own)."""
    if pid in pids:
        return True
    try:
        return hasattr(os, "getpgid") and os.getpgid(pid) in pids
    except OSError:
        return False


def outside(holders, pids):
    """HOLDERS without those the executor itself runs: a holder whose pid is one of PIDS (the pids of its children and its own)
    or in the process group of one is a job in progress, which the class rules already serialise."""
    return {lock: held for lock, held in holders.items() if not inside(held["pid"], pids)}


LOCK_STEPS = {"host-main": "lock:host-main", "landing": "lock:landing", "host-test": "lock:tests"}


def wait_step(lock):
    """The step member of a job's waiting-lock event: `lock:` and the lock's name (`host-main`, `landing` or `tests`) only. The
    holder's pid, clone and step are in the job record (the member `holder`), never in an event, which monitors and digests read."""
    return LOCK_STEPS[lock]


def drain(store, clone, host, operator, out, slots=SLOTS, tick=None):
    """Run the queued jobs of this host, clone and operator to the end, at most SLOTS at a time and as `next_runnable` places them
    (submit order inside a class); the ids of the jobs that failed or were lost. A job whose lock a process outside the executor
    holds is moved to waiting-lock (event step: the lock; record member `holder`: its pid, clone and step) and started once the lock is free. A job another
    executor leased, or that left queued before this one moved it, is passed over. TICK, when given, is called at the start of each pass
    (an executor of a central queue syncs its mirror there, `Sync`)."""
    failed, passed, active, waiting = [], set(), {}, {}  # active: job -> child state; waiting: job -> {record, token, renewed}
    slots = max(1, int(slots))

    def release(job, token):
        with contextlib.suppress(coord.Refused):
            coord.release(Namespace(key=lease_key(job), token=token, store=store, operator=None), time.time)

    def renew(job, token, one):
        if time.monotonic() - one["renewed"] >= JOB_LEASE_RENEW_S:
            with contextlib.suppress(coord.Refused):
                coord.renew(Namespace(key=lease_key(job), token=token, ttl=None, store=store), time.time)
            one["renewed"] = time.monotonic()

    def begin(job, record, token):
        """Take the job out of queued or waiting-lock into running and start its child; False when it did not start."""
        try:
            move(store, job, "running")
        except coord.Refused:
            release(job, token)
            return False
        if record.get("op") == "land":  # a thread of its own drives the passes and the wait (`LandRun`)
            run = LandRun(store, clone, {**record, "state": "running"}, token, out)
            active[job] = {"record": record, "token": token, "run": run, "renewed": time.monotonic()}
            run.start()
            return True
        proc, start = start_job(store, job, record, clone, kj_store.log_path(clone, job), out)
        if proc is None:
            failed.append(job)
            release(job, token)
            return True
        active[job] = {"record": record, "token": token, "proc": proc, "start": start, "renewed": time.monotonic()}
        return True

    try:
        while True:
            if tick is not None:
                tick()
            for job, one in list(active.items()):  # the children that ended, the land threads that ended
                run = one.get("run")
                if run is not None:  # the thread renews its own lease
                    if not run.is_alive():
                        del active[job]
                        if run.state in ("failed", "lost"):
                            failed.append(job)
                        release(job, one["token"])
                    continue
                code = one["proc"].poll()
                if code is None:
                    renew(job, one["token"], one)
                    continue
                del active[job]
                try:
                    text = finish_text(kj_store.log_path(clone, job), one["start"])
                    if finish_job(store, job, one["record"], code, text, out) in ("failed", "lost"):
                        failed.append(job)
                finally:
                    release(job, one["token"])
            for job, one in list(waiting.items()):  # a waiting job cancelled meanwhile leaves the table
                now = kj_store.read_record(store, job) or {}
                if now.get("state") != "waiting-lock":
                    if now.get("state") == "cancelled":
                        record_run(store, job, one["record"], "cancelled")
                    drop_holder(store, job)
                    del waiting[job]
                    release(job, one["token"])
                else:
                    renew(job, one["token"], one)
            seen = [(j, r) for j, r in pending(store, clone, host, operator, ("queued", "waiting-merge")) if j not in passed]
            for job, record in seen:  # a land job a dead executor left in its wait: polled again from its recorded pending
                if record["state"] == "waiting-merge" and job not in active and record.get("op") == "land" and kj_land.recorded_pending(record):
                    token = take_job(store, job)
                    if token is None:
                        passed.add(job)
                        continue
                    run = LandRun(store, clone, record, token, out)
                    active[job] = {"record": record, "token": token, "run": run, "renewed": time.monotonic()}
                    run.start()
            queued = [(j, r) for j, r in seen if r["state"] == "queued" and j not in waiting]
            if not (queued or waiting or active):
                return failed
            asking = [{**one["record"], "state": "waiting-lock"} for one in active.values() if one.get("run") and one["run"].want]
            candidates = [{**one["record"], "state": "waiting-lock"} for one in waiting.values()] + asking + [r for _, r in queued]
            candidates.sort(key=lambda r: (r.get("submitted_ts", 0), r["job"]))
            mine = {os.getpid()} | {one["proc"].pid for one in active.values() if one.get("proc")}
            mine |= {one["run"].proc.pid for one in active.values() if one.get("run") and one["run"].proc}
            holders = outside(lock_holders(clone), mine)
            running = [one["record"] for one in active.values() if one.get("run") is None or one["run"].passing]
            run, wait = next_runnable(candidates, running, holders, slots)
            for record, lock, held in wait:
                job = record["job"]
                token = take_job(store, job)
                if token is None:
                    passed.add(job)
                    continue
                try:
                    move(store, job, "running")
                    move(store, job, "waiting-lock", step=wait_step(lock))
                    amend(store, job, holder={"pid": held["pid"], "clone": held["clone"], "step": held["step"]})
                except coord.Refused:
                    release(job, token)
                    continue
                waiting[job] = {"record": record, "token": token, "renewed": time.monotonic()}
                print(f"{job} {record['op']} {record.get('subject') or '-'}: waiting-lock, {lock} held by pid {held['pid']} "
                      f"(clone {held['clone']}, step {held['step']})", file=out, flush=True)
            for record in run:
                job = record["job"]
                if job in active:  # a land thread's second pass: its slot and its class's turn
                    active[job]["run"].passing, active[job]["run"].want = True, False
                    active[job]["run"].granted.set()
                    continue
                if job in waiting:
                    one = waiting.pop(job)
                    begin(job, record, one["token"])
                    continue
                token = take_job(store, job)
                if token is None:
                    passed.add(job)
                    continue
                begin(job, record, token)
            if active or waiting or queued:
                time.sleep(TICK_S)
    except BaseException:
        for job, one in list(active.items()):
            if one.get("run") is not None:  # the thread ends its own child and moves a running job to lost; a waiting one stays
                one["run"].halt.set()
                continue
            kg_lock.end_group(one["proc"])
            with contextlib.suppress(coord.Refused):
                move(store, job, "lost")
        for one in list(active.values()):
            if one.get("run") is not None:
                one["run"].join(timeout=JOB_LEASE_RENEW_S)
        for job in waiting:
            with contextlib.suppress(coord.Refused):
                move(store, job, "running")
                move(store, job, "lost")
        raise
    finally:
        for job, one in {**waiting, **active}.items():
            release(job, one["token"])


def running_pid(root, store):
    """The pid of the executor of STORE on this host (the pid its host file in the host lock directory names, when that process
    runs), else None. Only reads: a stale file is left for the next serve to clear."""
    import tests as tests_py
    holder = tests_py.read_holder(os.path.join(tests_py.host_lock_dir(), lock_name(root, store)))
    return holder["pid"] if holder is not None and tests_py.pid_alive(holder["pid"]) else None


def ping(root, store, out=None):
    """`kbjob.py ping`: 0 printing the pid when an executor of STORE runs on this host, 1 printing that none does."""
    out = out or sys.stdout
    pid = running_pid(root, store)
    print(pid if pid is not None else "kbjob: no executor on this host", file=out, flush=True)
    return 0 if pid is not None else 1


def serve_log_path(root):
    """The log of a serve that `ensure` started, kb-jobs/serve.log under the clone's common git directory (None outside a clone)."""
    path = kj_store.log_path(root, "x")
    return None if path is None else path.parent.parent / "serve.log"


def ensure(root, store, wait=ENSURE_WAIT_S):
    """Start the executor when none runs: (pid, started, error). `serve` runs detached (a session of its own, stdin closed, its
    output appended to serve.log), so it outlives the session that started it; the wait ends when the host file names a live
    process (the new one, or one a racing ensure started) or at WAIT seconds. The child inherits this process's environment
    (KB_HOST_LOCK_DIR and the rest). For a STORE that is not the clone's own the serve ends by itself after IDLE_EXIT_S seconds
    with no live job, so a planted store leaves no executor behind. error is None when pid is set, else the last line of the
    log (or why serve could not start)."""
    pid = running_pid(root, store)
    if pid is not None:
        return pid, False, None
    log = serve_log_path(root)
    if log is None:
        return None, False, "serve needs a git clone for its job logs"
    log.parent.mkdir(parents=True, exist_ok=True)
    start = log.stat().st_size if log.exists() else 0
    group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)}
    argv = [sys.executable, str(Path(__file__).resolve().parent / "kbjob.py"), "--store", str(store), "serve"]
    if not own_store(root, store):
        argv += ["--idle-exit", f"{IDLE_EXIT_S:g}"]
    try:
        with open(log, "ab") as sink:
            proc = subprocess.Popen(argv, cwd=kj_store.clone_path(root), env=dict(os.environ), stdin=subprocess.DEVNULL, stdout=sink,
                                    stderr=subprocess.STDOUT, **group)
    except OSError as error:
        return None, False, f"serve did not start: {str(error)[:200]}"
    until = time.monotonic() + wait
    while time.monotonic() < until:
        pid = running_pid(root, store)
        if pid is not None:
            return pid, pid == proc.pid, None
        if proc.poll() is not None and running_pid(root, store) is None:
            break
        time.sleep(0.1)
    if proc.poll() is None:
        kg_lock.end_group(proc)
    return None, False, last_line(finish_text(log, start)) or f"no executor named its pid within {wait:g} s"


def plist_text(program, clone, log):
    """The macOS LaunchAgent plist that runs `kbjob.py serve` at login and again when it ends."""
    from xml.sax.saxutils import escape
    args = "".join(f"\n    <string>{escape(a)}</string>" for a in program)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- macOS: save as ~/Library/LaunchAgents/{LOGIN_LABEL}.plist, then run: launchctl bootstrap gui/$(id -u) that file -->
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LOGIN_LABEL}</string>
  <key>ProgramArguments</key>
  <array>{args}
  </array>
  <key>WorkingDirectory</key>
  <string>{escape(clone)}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardErrorPath</key>
  <string>{escape(log)}</string>
  <key>StandardOutPath</key>
  <string>{escape(log)}</string>
</dict>
</plist>
"""


def unit_text(program, clone, log):
    """The systemd user unit that runs `kbjob.py serve` at login and again when it ends."""
    quoted = " ".join('"' + a.replace("\\", "\\\\").replace('"', '\\"') + '"' for a in program)
    return f"""# Linux: save as ~/.config/systemd/user/{LOGIN_LABEL}.service, then run: systemctl --user enable --now {LOGIN_LABEL}.service
[Unit]
Description=it-ops-kb job executor

[Service]
ExecStart={quoted}
WorkingDirectory={clone}
Restart=always
RestartSec=30
StandardOutput=append:{log}
StandardError=append:{log}

[Install]
WantedBy=default.target
"""


def login_item(root, store=None, out=None):
    """`kbjob.py login-item --print`: the LaunchAgent plist and the systemd user unit of the executor, printed with where each goes
    and how it is loaded. Writes nothing and reads nothing under the home directory: the operator installs what they choose."""
    out = out or sys.stdout
    clone = kj_store.clone_path(root)
    log = serve_log_path(root) or Path(clone) / LOG_FALLBACK
    script = Path(clone) / "_tools" / "kbjob.py"  # the clone's own checkout outlasts a worktree this runs from
    script = script if script.is_file() else Path(__file__).resolve().parent / "kbjob.py"
    program = [sys.executable, str(script)] + (["--store", str(store)] if store else []) + ["serve"]
    out.write(plist_text(program, clone, str(log)) + "\n" + unit_text(program, clone, str(log)))
    return 0


def serve(root, store, once=False, out=None, idle_exit=None, slots=SLOTS, kind=None, remote=None, data=None):
    """`kbjob.py serve`: 0 when the queue was drained (--once), when IDLE_EXIT seconds passed with no live job of this host,
    clone and operator, or when this process ended by a signal; 1 when --once ran a job that failed, 2 where the clone has no
    git directory; a second serve for the same store on the host prints the running one's pid and returns 0. With REMOTE (a
    `kj_store.Remote`) and KIND (one of coord's placement executors) it serves the central queue: its jobs are kept in a mirror
    store (in DATA, else in the clone's `kb-jobs`) and `Sync` takes and posts them."""
    out = out or sys.stdout
    clone = kj_store.clone_path(root)
    sync = None
    if remote is not None:
        store = kj_store.Mirror(kj_store.mirror_path(root, remote, kind, data), remote, kind)
        sync = Sync(root, store, clone, out)
    if kj_store.log_path(clone, "JB-00000000") is None:
        print("kbjob.py: serve needs a git clone for its job logs", file=sys.stderr)
        return 2
    path, holder = take_lock(clone, lock_name(root, store))
    if path is None:
        print(f"kbjob.py: serve already runs on this host: pid {holder['pid']} (clone {holder['clone']}, started {holder['started']})",
              file=out, flush=True)
        return 0
    before = None
    with contextlib.suppress(ValueError, OSError):  # not the main thread
        before = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    host, operator, failed, recovered, idle = platform.node(), kj_store.operator_id(), [], None, None
    try:
        while True:
            if recovered is None or time.monotonic() - recovered >= RECOVER_S:
                failed += recovery_pass(root, store, out)
                recovered = time.monotonic()
            failed += drain(store, clone, host, operator, out, slots, sync)
            if once:
                break
            if idle_exit is not None:
                idle = None if pending(store, clone, host, operator, LIVE_STATES) else (idle if idle is not None else time.monotonic())
                if idle is not None and time.monotonic() - idle >= idle_exit:
                    break
            time.sleep(poll_seconds())
    finally:
        if before is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGTERM, before)
        drop_lock(path)
    return 1 if failed else 0
