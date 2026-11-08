"""The job executor: `kbjob.py serve` runs the queued jobs of its host, clone and operator, one after another (stdlib only;
kb/_self/coordination.md, section "Operation jobs").

  classify(exit, text)  -> (state, step)  the end of a job's process as the job table's state: exit 0 succeeded; exit 1 and a
                                          line `NAME stopped at step STEP: ...` (`land stopped at step rebase: ...`, as
                                          bl_land.land_refused_step reads it) refused, naming that step; any other end failed
  serve(root, store, once, poll, out)  -> exit code of `kbjob.py serve`
  recover(root, store, alive, leased)  -> the moves made on the jobs an executor that died left: a job in running,
                                          waiting-lock or waiting-merge whose lease `jobrun/<job id>` has expired and whose
                                          recorded pid no longer runs moves to lost (step lost), then to queued with its attempt
                                          raised by one the first time and to failed the second time; a job whose child still
                                          runs and names the job's operation is adopted (the lease taken again)

A job is taken with the lease `jobrun/<job id>` (JOB_LEASE_TTL_S, renewed every JOB_LEASE_RENEW_S while the child runs), moved
queued to running, and run as `python <argv of kj_ops.OPS>` in the job's clone: the leader of a process group of its own, stdin
closed, stdout and stderr appended to the job's `kb-jobs/<job id>/output.log` under the clone's common git directory. Every
move goes through `coord.job_transition`, the job table. A job of another operator, host or clone stays queued. One serve
runs per host: an exclusive file `kb-jobs-serve.lock` in the host lock directory (`tests.host_lock_dir`) holds its pid, clone
and start time and is cleared when that pid is gone, as `kg_lock.main_lock` clears the main lock.

The job's record keeps the pid of its child (the member `pid`, written after the child starts, dropped when the job is queued
again). Serve runs `recover` at its start and every RECOVER_S seconds, and follows each adopted child (the lease renewed
until its pid ends) instead of starting a second process. An adopted child's exit is not known to serve, so its end is a
loss: the job is requeued once or failed, like any lost job.
"""
import contextlib
import datetime
import json
import os
import platform
import re
import signal
import sqlite3
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

import coord
import kg_lock
import kj_follow
import kj_ops
import kj_store

LOCK_NAME = "kb-jobs-serve.lock"
JOB_LEASE_TTL_S = 60
JOB_LEASE_RENEW_S = 20
RECOVER_S = 30  # the wait between two recovery passes of a serve
MAX_LOST = 2  # a job lost this many times is failed, not run again: a crash loop ends at attempt 2
RECOVERABLE = ("running", "waiting-lock", "waiting-merge", "lost")  # the states a dead executor leaves a job in
POLL_S = 5.0  # the wait between two looks at the queue of a serve that does not stop when it is empty (KB_JOB_POLL)
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


def pending(store, clone, host, operator):
    """[(job id, record)] of the queued jobs of this host, clone and operator, in submit order."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT key, value FROM entries WHERE key LIKE ? AND value IS NOT NULL", (coord.JOB_KEYS + "%",)).fetchall()
    finally:
        con.close()
    found = []
    for row in rows:
        record = coord.job_record(row["value"])
        if (record and record.get("state") == "queued" and record.get("host") == host and record.get("clone") == clone
                and record.get("operator") == operator and record.get("job") == row["key"][len(coord.JOB_KEYS):]):
            found.append((record["job"], record))
    return sorted(found, key=lambda one: (one[1].get("submitted_ts", 0), one[0]))


def move(store, job, state, **fields):
    """Move JOB to STATE by coord's job table, with the fields given (exit, step); coord.Refused when the table says no."""
    given = [f"{name}={value}" for name, value in fields.items() if value is not None]
    return coord.job_transition(Namespace(key=coord.JOB_KEYS + job, to=state, field=given, store=store), time.time)


def take_lock(clone):
    """Take the host's serve lock: (path, None) when this process now holds it, (None, holder) when a live process does, holder
    being {pid, clone, started}. A lock whose pid no longer runs, or whose record stays unwritten past the grace, is cleared."""
    import tests as tests_py  # the test lock's helpers, as kg_lock uses them
    path = os.path.join(tests_py.host_lock_dir(), LOCK_NAME)
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
    argv = [sys.executable] + kj_ops.argv(record["op"], record.get("subject", ""), record.get("options"))
    group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    with open(log, "ab") as sink:
        proc = subprocess.Popen(argv, cwd=clone, stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT, **group)
    return proc, start


def finish_text(log, start):
    with open(log, "rb") as f:
        f.seek(start)
        return f.read().decode("utf-8", errors="replace")


def run_job(store, job, record, clone, log, token, out):
    """Run one taken job to its end with the lease renewed; returns the state it moved to. A process that cannot start moves
    the job to failed (exit 127); a signal to this process ends the child's group and moves the job to lost, then goes on; a
    job cancelled meanwhile (kbjob.py cancel) stays cancelled, one line says so and cancelled is returned."""
    try:
        proc, start = start_child(record, clone, log)
    except OSError as error:
        move(store, job, "failed", exit=127)
        print(f"{job} {record['op']} {record.get('subject') or '-'}: failed, exit 127: {str(error)[:200]}", file=out, flush=True)
        return "failed"
    with contextlib.suppress(sqlite3.Error):
        amend(store, job, pid=proc.pid)
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
    text = finish_text(log, start)
    state, step = classify(code, text)
    number = exit_number(code)
    try:
        move(store, job, state, exit=number, step=step)
    except coord.Refused as refusal:
        if refusal.body.get("state") != "cancelled":
            raise
        print(f"{job} {record['op']} {record.get('subject') or '-'}: cancelled", file=out, flush=True)
        return "cancelled"
    note = f"{job} {record['op']} {record.get('subject') or '-'}: {state}"
    if state == "refused":
        note += f" at step {step}"
    elif state == "failed":
        note += f", exit {number}: {last_line(text)}"
    print(note, file=out, flush=True)
    return state


def lease_key(job):
    return "jobrun/" + job


def take_job(store, job):
    """The lease token of JOB, or None when another executor holds the lease."""
    try:
        got = coord.claim(Namespace(key=lease_key(job), holder=f"serve-{os.getpid()}", ttl=JOB_LEASE_TTL_S, store=store, budget=None), time.time)
    except coord.Refused:
        return None
    return got["token"]


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
        return {**one, "move": "failed", "attempt": int(record.get("attempt", 1))}
    attempt = int(record.get("attempt", 1)) + 1
    amend(store, job, attempt=attempt, pid=None)
    move(store, job, "queued", attempt=attempt)
    return {**one, "move": "queued", "attempt": attempt}


def recover(root, store=None, alive=None, leased=None):
    """One recovery pass over the jobs of this host, clone and operator that a dead executor left in running, waiting-lock,
    waiting-merge or lost. A job whose lease `jobrun/<job id>` is held is left alone (`leased(key)`, by default the store's
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


def drain(store, clone, host, operator, out):
    """Run every queued job of this host, clone and operator, in submit order, one at a time; the ids of the jobs that failed
    or were lost. A job another executor leased, or that left queued before this one moved it, is passed over."""
    failed, passed = [], set()
    while True:
        todo = [one for one in pending(store, clone, host, operator) if one[0] not in passed]
        if not todo:
            return failed
        job, record = todo[0]
        passed.add(job)
        token = take_job(store, job)
        if token is None:
            continue
        try:
            log = kj_store.log_path(clone, job)
            try:
                move(store, job, "running")
            except coord.Refused:
                continue
            if run_job(store, job, record, clone, log, token, out) in ("failed", "lost"):
                failed.append(job)
        finally:
            with contextlib.suppress(coord.Refused):
                coord.release(Namespace(key=lease_key(job), token=token, store=store, operator=None), time.time)


def serve(root, store, once=False, out=None):
    """`kbjob.py serve`: 0 when the queue was drained (--once) or this process ended by a signal, 1 when --once ran a job that
    failed, 2 where the clone has no git directory; a second serve on the host prints the running one's pid and returns 0."""
    out = out or sys.stdout
    clone = kj_store.clone_path(root)
    if kj_store.log_path(clone, "JB-00000000") is None:
        print("kbjob.py: serve needs a git clone for its job logs", file=sys.stderr)
        return 2
    path, holder = take_lock(clone)
    if path is None:
        print(f"kbjob.py: serve already runs on this host: pid {holder['pid']} (clone {holder['clone']}, started {holder['started']})",
              file=out, flush=True)
        return 0
    before = None
    with contextlib.suppress(ValueError, OSError):  # not the main thread
        before = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    host, operator, failed, recovered = platform.node(), kj_store.operator_id(), [], None
    try:
        while True:
            if recovered is None or time.monotonic() - recovered >= RECOVER_S:
                failed += recovery_pass(root, store, out)
                recovered = time.monotonic()
            failed += drain(store, clone, host, operator, out)
            if once:
                break
            time.sleep(poll_seconds())
    finally:
        if before is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGTERM, before)
        drop_lock(path)
    return 1 if failed else 0
