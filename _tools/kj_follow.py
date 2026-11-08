"""Watching and ending a job: follow, status, log and cancel of `kbjob.py` (stdlib only; kb/_self/coordination.md, section
"Operation jobs").

  follow(root, store, job, since, timeout, out)  -> exit code: one line per `job` event of JOB after sequence SINCE, flushed
                                                    at once; on a terminal state the line `JOB STATE [step=NAME] exit=N log=PATH`
                                                    and 0 (succeeded), 1 (failed, refused) or 3 (cancelled); past TIMEOUT the
                                                    line `follow: still running, continue with --since N` and 4
  active(store)                                  -> the records of every job not in a terminal state, oldest first
  tail_of(root, store, job, count, out)          -> the last COUNT lines of the job's output log
  cancel(root, store, job, out)                  -> exit code: a queued job moves to cancelled; a running one moves to cancelled
                                                    and its process group gets TERM, then KILL; for the submitting operator only

`follow` only reads: it waits with `coord.wait` on the `job` events of JOB, so the job outlives the session that follows it.
A line is `JOB STATE OP SUBJECT [step=NAME] [exit=N]` and never a line of the command's own output, which stays in the log.
"""
import os
import platform
import re
import signal
import subprocess
import sys
import time
from argparse import Namespace

import coord
import kj_ops
import kj_store

DEFAULT_TIMEOUT_S = 1500  # under the Monitor tool's effective deadline of 1800 s
SLICE_S = 30  # the longest single wait: the record is read again after it
TAIL_LINES = 40
TAIL_BYTES = 1 << 20  # how far from the end of a log a tail reads
FOLLOW_EXIT = {"succeeded": 0, "failed": 1, "refused": 1, "cancelled": 3}
STILL_RUNNING_EXIT = 4
TERM_GRACE_S = 10
KILL_GRACE_S = 5
HOLDER = re.compile(r"serve-([0-9]+)")


def record_of(store, job):
    """The record of JOB; kj_ops.Refusal for an id that is no job id or a job the store does not hold."""
    if not coord.FIELD_VALUE.fullmatch(str(job)) or "/" in str(job):
        raise kj_ops.Refusal(f"a job is the id JB- and 8 characters, not {str(job)[:40]!r}")
    record = kj_store.read_record(store, job)
    if not record:
        raise kj_ops.Refusal(f"{job} is no job of this store")
    return record


def event_line(fields):
    """`JOB STATE OP SUBJECT [step=NAME] [exit=N]` of a job event's fields (a dash for an operation or subject it lacks)."""
    parts = [fields["job"], fields["state"], fields.get("op", "-"), fields.get("item", "-")]
    parts += [f"{name}={fields[name]}" for name in ("step", "exit") if name in fields]
    return " ".join(parts)


def end_line(root, job, record):
    """`JOB STATE [step=NAME] exit=N log=PATH` of a job in a terminal state (a dash for what it has none of)."""
    path = kj_store.log_path(root, job)
    parts = [job, record["state"]]
    if record.get("step") is not None:
        parts.append(f"step={record['step']}")
    parts += [f"exit={'-' if record.get('exit') is None else record['exit']}", f"log={path if path is not None else '-'}"]
    return " ".join(parts)


def follow(root, store, job, since, timeout, out):
    record_of(store, job)
    cursor, deadline = int(since), time.monotonic() + float(timeout)
    while True:
        record = record_of(store, job)  # read before the events: a terminal record's events are all in the store
        state = record.get("state", "none")
        ended = state in kj_store.TERMINAL
        wait = 0 if ended else min(max(deadline - time.monotonic(), 0), SLICE_S)
        body = coord.wait(Namespace(store=store, since=cursor, timeout=wait, kind="job", item={job}, pid=[], recheck=None), time.time)
        for event in body["events"]:
            print(event_line(event["fields"]), file=out, flush=True)
        cursor = body["last"]
        if ended:
            print(end_line(root, job, record), file=out, flush=True)
            return FOLLOW_EXIT[state]
        if time.monotonic() >= deadline:
            print(f"follow: still running, continue with --since {cursor}", file=out, flush=True)
            return STILL_RUNNING_EXIT


def active(store):
    """The records of every job in a state with a move out, oldest submit first."""
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        rows = con.execute("SELECT value FROM entries WHERE key LIKE ? AND value IS NOT NULL", (coord.JOB_KEYS + "%",)).fetchall()
    finally:
        con.close()
    found = [r for r in (coord.job_record(row["value"]) for row in rows) if r and r.get("state", "none") not in kj_store.TERMINAL]
    return sorted(found, key=lambda r: (r.get("submitted_ts", 0), r.get("job", "")))


def tail_of(root, store, job, count, out):
    """Print the last COUNT lines of JOB's output log; 1 (and a note on stderr) when it has written none."""
    record_of(store, job)
    if count < 0:
        raise kj_ops.Refusal("--tail is a count of lines, 0 or more")
    path = kj_store.log_path(root, job)
    if path is None or not path.is_file():
        print(f"kbjob.py: {job} has no output log yet", file=sys.stderr)
        return 1
    with open(path, "rb") as f:
        size = f.seek(0, os.SEEK_END)
        f.seek(max(size - TAIL_BYTES, 0))
        data = f.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    if size > TAIL_BYTES and lines:
        lines = lines[1:]  # the first line of a read that began mid-file is cut
    for line in lines[max(len(lines) - count, 0):] if count else []:
        print(line, file=out)
    return 0


def group_of(store, job):
    """The leader pid of the process group the executor runs JOB in, None when it has none to find: the holder of the lease
    jobrun/JOB is `serve-PID` and runs one job at a time, so its child that leads a group of its own is the job's."""
    if os.name != "posix":
        return None
    con = coord.connect(store)
    try:
        coord.ensure_schema(con)
        row = con.execute("SELECT holder, expires FROM entries WHERE key = ?", ("jobrun/" + job,)).fetchone()
    finally:
        con.close()
    found = HOLDER.fullmatch(row["holder"] or "") if row is not None and (row["expires"] or 0) > time.time() else None
    if found is None:
        return None
    try:
        text = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,pgid="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in text.splitlines():
        numbers = line.split()
        if len(numbers) == 3 and all(n.isdigit() for n in numbers):
            pid, ppid, pgid = (int(n) for n in numbers)
            if ppid == int(found.group(1)) and pgid == pid:
                return pid
    return None


def group_runs(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def end_group(pgid):
    """TERM the process group PGID, KILL it after a grace; whether it is gone."""
    for sig, grace in ((signal.SIGTERM, TERM_GRACE_S), (signal.SIGKILL, KILL_GRACE_S)):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        until = time.monotonic() + grace
        while time.monotonic() < until:
            if not group_runs(pgid):
                return True
            time.sleep(0.1)
    return not group_runs(pgid)


def move_cancelled(store, job):
    """Move JOB to cancelled by coord's job table: None when it moved, else the refusal (the job left that state)."""
    try:
        coord.job_transition(Namespace(key=coord.JOB_KEYS + job, to="cancelled", field=[], store=store), time.time)
    except coord.Refused as refused:
        return refused
    return None


def cancel(root, store, job, out):
    """Cancel JOB for its submitting operator: 0 when it is cancelled (or was), 1 when it is another operator's, ended in
    another state, runs on another host or cannot be ended here. A queued job only moves; a running job moves first, then its
    process group gets TERM and KILL, so the executor's own end of it finds a job that no move leaves."""
    for _ in range(3):  # a queued job an executor starts meanwhile is met again as a running one
        record = record_of(store, job)
        if record.get("operator") != kj_store.operator_id():
            print(f"kbjob.py: {job} was submitted by another operator: only the submitting operator cancels it", file=sys.stderr)
            return 1
        state = record.get("state", "none")
        if state == "cancelled":
            print(f"{job} cancelled", file=out, flush=True)
            return 0
        if state in kj_store.TERMINAL or state == "lost" or "cancelled" not in coord.JOB_TRANSITIONS.get(state, ()):
            print(f"kbjob.py: {job} is {state}, which does not move to cancelled", file=sys.stderr)
            return 1
        pgid = None
        if state != "queued":
            if record.get("host") != platform.node():
                print(f"kbjob.py: {job} runs on host {record.get('host')}: cancel it there", file=sys.stderr)
                return 1
            if os.name != "posix":
                print("kbjob.py: ending a running job's process group is for POSIX hosts", file=sys.stderr)
                return 1
            pgid = group_of(store, job)
        if move_cancelled(store, job) is not None:
            continue
        note = "queued"
        if pgid is not None:
            note = "running, process group ended" if end_group(pgid) else "running, process group still runs"
        elif state != "queued":
            note = "running, no process group found"
        print(f"{job} cancelled ({note})", file=out, flush=True)
        return 0 if pgid is None or not group_runs(pgid) else 1
    print(f"kbjob.py: {job} moved while it was cancelled: try again", file=sys.stderr)
    return 1
