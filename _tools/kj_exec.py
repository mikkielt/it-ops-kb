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

A workstation executor holds the lease `jobexec/<host>/<operator>` (`Presence`: EXEC_LEASE_TTL_S, renewed with the job leases, its value
`{"seen": TIME}` kept after the lease ends) on the queue it serves. An executor of kind server or ci (`Sync.offline`) takes a queued job placed on a
workstation whose lease is not held, since the later of `seen` and the job's submit, for the placement's `fallback_after_s`, when the
decision's `fallback` is its kind: the job's placement becomes its kind (`fallback_from`, `offline_since`) and one `job` event, step
`offline-since-<UTC time>-fallback-<kind>`, says so (`kj_store.reasoned` reads it as `reason` and `placement`); with no fallback the job
stays queued and one event with step `offline-since-<UTC time>` says why. `serve --kind K` with no --url serves the clone's own queue so
(`kj_store.LocalRemote` in place of the central queue's `Remote`).

`serve --kind K --url URL --key-file PATH --job JB-ID` (`serve(job=)`) serves one job of the central queue and no other, for a CI
pipeline started for it: `Sync.refusal` leaves a job that is not queued, not placed on K (or on an offline workstation whose fallback is K
once its delay has passed, as `Sync.offline` takes it) or naming another clone's url untouched, posting nothing, and exits 2 naming its
placement and state; otherwise `Sync` and `drain` take only that job, no recovery pass runs, and the exit is `job_exit`: 0 succeeded,
1 failed, refused, lost or cancelled on the queue, 2 when this executor never ran it.

A server executor (`serve --kind server [--data DIR]`) serves every integration remote url its queue's jobs name, not the clone it was started in:
`Home` keeps one clone per url under DIR (cloned at the first job, fetched before each, the tree detached on `origin/main`), runs the job's
argument list there as the CLI does on a workstation, and gives a land job the worktree `.claude/worktrees/agent-<id>` of the remote's `work/<id>`,
where `backlog.py land` finds the pushed worker branch; the jobs of one url run one at a time (`serial_key`). A job that tests.py refused over the
seconds of its test ceiling ends failed with the reason `host condition` (`host_condition`, `note_condition`) and is not run again.

A job of a central queue is taken only when its recorded placement is what the placement policy decides now (`verify_placement`, run by
`Sync.pull`): the executor asks the policy at its own KB_OPA_URL as `kbjob.py place` does, for the record's operation, subject and host and
the operator the queue's `queued` event names (the server's word, not the record's), and compares the decision's executor, identity,
decided_by and budget_cap_usd with the recorded ones. A job that differs, or whose policy cannot be asked (no policy decides the
workstation, identity none), stays queued with one `job` event, step `placement-mismatch`, and a line saying what differs, and is asked
about again after VERIFY_S; the mirror keeps the decision's placement, not the record's. A clone's own queue is not verified.

A job runs as the identity its placement names (`job_env`, `kj_cred.resolve`): `none` disables every push, `group-bot` and `operator` give git a
credential file or CI variable through a GIT_ASKPASS helper, never an argument or an environment value. A job whose identity has no usable
credential starts no process and ends refused at the step `credential` (`refuse_credential`), the `kj_cred.Refused` message its record's `reason`.
A job with no placement, or the decision of no policy (`decided_by` `default`), runs in the executor's environment.

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
import kj_cred
import kj_follow
import kj_land
import kj_ops
import kj_place
import kj_store

LOCK_NAME = "kb-jobs-serve.lock"
JOB_LEASE_TTL_S = 60
JOB_LEASE_RENEW_S = 20
EXEC_LEASE_TTL_S = 60  # how long a workstation executor's lease `jobexec/<host>/<operator>` lasts after its last renewal
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
HOST_CONDITION = "host condition"  # the reason of a job that tests.py refused over the seconds of its test ceiling: the host was busy, the code is not at fault
CEILING_LINE = re.compile(r"tests\.py: over the ceiling: the full run took \d+ s")  # the line tests.py prints for that refusal (`tests.ceiling_report`)


def host_condition(code, text):
    """Whether a job that ended with exit CODE and the output TEXT was refused by the seconds of the test ceiling: the line
    `tests.py: over the ceiling: the full run took N s, ...` (a count over the ceiling, ids or files, is a finding of the code)."""
    return code != 0 and bool(CEILING_LINE.search(text or ""))


def classify(code, text):
    """(state, step) of a job's end: exit CODE and the output TEXT it wrote. `refused` takes exit 1 and a stop line naming a
    step (the last one), the step as an ops token (lower case, other characters one `-`) because a job field holds no
    space; `failed` is every other end, a test ceiling refused over its seconds (`host_condition`) always; `succeeded` exit 0.
    The step is None unless the state is refused."""
    if code == 0:
        return "succeeded", None
    if host_condition(code, text):
        return "failed", None
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
        placed = (kj_store.read_record(store, job) or {}).get("placement")
        moved = placed if isinstance(placed, dict) and placed.get("fallback_from") else None
        with contextlib.suppress(kj_ops.Refusal):
            store.remote.amend(job, log_host=platform.node(), executor=store.kind, **({"placement": moved} if moved else {}))
            if moved:  # the job this executor took from an offline workstation: its event says why and where it went
                store.remote.note(job, kj_store.offline_step(moved["offline_since"], moved["executor"]), "running")


SYNC_S = 2.0  # the wait between two syncs of a mirror with its central queue
SERVER = "server"  # the executor kind that keeps one clone per integration remote url (`Home`)
NO_CLONE = "no-clone"  # the step of the event that says a queued job names an integration remote url this executor's clone lacks
MISMATCH = "placement-mismatch"  # the step of the event that says a queued job's recorded placement is not what the policy decides now
PLACED_MEMBERS = ("executor", "identity", "decided_by", "budget_cap_usd")  # the members of a recorded placement `verify_placement` compares
VERIFY_S = 60.0  # how long a job whose placement did not hold is left alone before the policy is asked about it again


def verify_placement(record, operator=None, environ=None):
    """(decision, why) for the queued job RECORD of a central queue: DECISION is what the placement policy (the url of KB_OPA_URL in ENVIRON,
    this process's by default; no url is the decision of no policy) decides now for the record's operation, subject, host and OPERATOR
    (default the record's own), asked as `kbjob.py place` asks it (`kj_place.build_input`: this clone's roots and their groups, the
    operator's groups, the capabilities of the closed table `kj_ops.OPS`); WHY is None when the record's placement holds, else the
    words of what differs: the members of PLACED_MEMBERS (executor, identity, decided_by, budget_cap_usd) the decision does not give
    as the record names them. A job taken from an offline workstation (`fallback_from`) holds when the decision is the workstation
    and names the record's executor as its fallback. A record with no placement has nothing to verify: (None, None)."""
    recorded = record.get("placement")
    if not isinstance(recorded, dict):
        return None, None
    op = record.get("op")
    if op not in kj_ops.OPS:
        return None, f"{str(op)[:40]!r} is no operation of the job queue"
    environ = os.environ if environ is None else environ
    url = environ.get(kj_place.ENV_URL, "")
    operator = operator or record.get("operator") or ""
    if not url:
        decision = kj_place.refused("no policy: no KB_OPA_URL")
    else:
        subject = record.get("subject") or str((record.get("options") or {}).get("name", ""))
        body = {**kj_place.build_input(op, subject, operator, kj_place.group_paths(operator)), "host": record.get("host") or platform.node()}
        decision = kj_place.ask(url, body)
    differ = [name for name in PLACED_MEMBERS if recorded.get(name) != decision[name]]
    if recorded.get("fallback_from"):
        since = recorded.get("offline_since")
        differ = [name for name in differ if name != "executor"]
        if recorded["fallback_from"] != decision["executor"] or recorded.get("executor") != decision["fallback"]:
            differ.insert(0, "executor")
        if isinstance(since, bool) or not isinstance(since, (int, float)) or not 0 <= since < 4e9:
            differ.append("offline_since")
    if not differ:
        return decision, None
    shown = ", ".join(f"{name} {str(recorded.get(name))[:40]!r} (decided {str(decision.get(name))[:40]!r})" for name in differ)
    return decision, f"the recorded placement differs from the policy's decision: {shown}; the decision: {decision['reason']}"


class Sync:
    """What an executor of a central queue does between two looks of `drain` at its jobs: `__call__` takes the queue's jobs for
    its kind into the mirror store and brings the two stores' states together (the central store's cancel, a move not posted)."""

    def __init__(self, root, store, clone, out, only=None):
        self.root, self.store, self.clone, self.out, self.only = root, store, clone, out, only
        self.remote, self.kind = store.remote, store.kind
        self.host, self.operator = platform.node(), kj_store.operator_id()
        self.last, self.noted, self.leases, self.owners, self.denied = None, {}, {}, {}, {}

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
        return [(job, record) for job, record in pending(self.store, self.clone, self.host, self.operator, coord.JOB_STATES)
                if self.only in (None, job)]

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

    def reason(self, job, step, why):
        """Say once per serve, as one `job` event and a line, why the queued JOB is left queued (WHY: the words of the line)."""
        if self.noted.get(job) != step:
            self.noted[job] = step
            self.remote.note(job, step)
            print(f"{job} stays queued: step {step} ({why})", file=self.out, flush=True)

    def fits(self, record):
        """Whether this executor's clone is the one the job names: the one with its integration remote url (a central queue's job),
        else the submitting clone (the clone's own queue); for a server executor, whether the job names an integration remote url."""
        if self.kind == SERVER:  # the server keeps a clone per url (`Home`): the job only has to name one
            return bool(record.get("remote"))
        if isinstance(self.remote, kj_store.LocalRemote):
            return record.get("clone") == self.clone
        url = kj_store.remote_url(self.clone)
        return bool(url) and record.get("remote") == url

    def refusal(self, job, record):
        """Why this executor does not take JOB (RECORD, its record on the queue) when it was started for that job alone, else None:
        the job must be queued and placed on this kind (a workstation executor: on this host, submitted by the operator of its own
        key file) or, as `offline` says for the whole queue, on a workstation that is offline whose decision's fallback is this kind
        and whose delay has passed, and it must fit this clone. Nothing is posted: the job is left as it was."""
        placed, state = kj_store.placement_of(record), record.get("state")
        where = placed["executor"] + (f" ({placed.get('host') or '-'})" if placed["executor"] == kj_store.WORKSTATION else "")
        say = f"{job} has placement {where} and state {state}: "
        if state != "queued":
            return say + f"an executor of kind {self.kind} runs only a queued job"
        if placed["executor"] != self.kind:
            if self.offline(job, record, placed, note=False) is None:
                return say + f"an executor of kind {self.kind} runs only a job placed on {self.kind}, or on a workstation whose offline fallback is {self.kind} once its delay has passed"
        elif self.kind == kj_store.WORKSTATION and (placed.get("host") != self.host or self.remote.owner(job) != self.remote.operator()):
            return say + "that workstation or its operator is not this one"
        if not self.fits(record):
            return say + ("the job names no integration remote url" if self.kind == SERVER else "no clone here has the job's integration remote url")
        return None

    def offline(self, job, record, placed, note=True):
        """The placement this executor's kind gives the queued JOB placed on a workstation whose executor is offline, else None.
        The workstation is offline when its lease `jobexec/<host>/<operator>` (host the placement's, operator the submitter's) is not
        held, and since the later of the lease's last renewal (`seen`) and the job's submit; the job moves when that was FALLBACK_AFTER_S
        seconds ago and the decision's fallback is this kind: the placement is this kind with `fallback_from` and `offline_since`.
        A decision with no fallback leaves the job queued, one event naming the time; a fallback of another kind is that kind's."""
        if self.kind == kj_store.WORKSTATION or placed["executor"] != kj_store.WORKSTATION:
            return None
        fallback = placed.get("fallback")
        if fallback is not None and fallback != self.kind:
            return None
        owner = self.owners.setdefault(job, self.remote.owner(job) or record.get("operator"))
        key = kj_store.exec_key(placed.get("host") or record.get("host"), owner)
        if key not in self.leases:
            self.leases[key] = self.remote.lease(key)
        lease = self.leases[key]
        if lease and lease.get("holder"):
            return None
        try:
            seen = float(json.loads(lease["value"]).get("seen", 0)) if lease and lease.get("value") else 0.0
        except (ValueError, TypeError, AttributeError):
            seen = 0.0
        since = max(seen, float(record.get("submitted_ts", 0)))
        if time.time() - since < float(placed.get("fallback_after_s") or 0):
            return None
        if fallback is None:
            if note:
                self.reason(job, kj_store.offline_step(since), f"executor offline since {kj_store.offline_step(since)[len('offline-since-'):]}, its decision has no fallback")
            return None
        return {**{name: value for name, value in placed.items() if name not in ("fallback", "fallback_after_s")}, "executor": self.kind,
                "fallback_from": kj_store.WORKSTATION, "offline_since": round(since, 3)}

    def confirm(self, job, record):
        """(go, placement) for the queued JOB (RECORD, its record on the central queue): whether the recorded placement holds against
        the policy's decision now (`verify_placement`, asked for the operator the queue's `queued` event names, the server's word, not
        the record's own) and, when it does, the placement the mirror keeps: the decision's members and the submitting host, never a
        member the record added; None when the record keeps its own (a record with no placement, a clone's own queue, where the
        submitter is the one who runs it). A job that does not hold stays queued: one `job` event, step MISMATCH, says why, and the
        policy is asked again for it after VERIFY_S."""
        recorded = record.get("placement")
        if not isinstance(recorded, dict) or isinstance(self.remote, kj_store.LocalRemote):
            return True, None
        key = json.dumps(recorded, sort_keys=True, default=str)
        seen = self.denied.get(job)
        if seen and seen[1] == key and time.monotonic() - seen[0] < VERIFY_S:
            return False, None
        server = self.owners.get(job) or self.remote.owner(job)
        decision, why = (None, "no `queued` event names the job's submitter") if not server else verify_placement(record, server)
        if why:
            self.denied[job] = (time.monotonic(), key)
            self.reason(job, MISMATCH, why)
            return False, None
        self.owners[job] = server
        placement = {**decision, "host": recorded.get("host") or record.get("host")}
        if recorded.get("fallback_from"):  # a job lost and queued again after an executor took it from an offline workstation
            placement = {**{k: v for k, v in placement.items() if k not in ("fallback", "fallback_after_s")}, "executor": recorded["executor"],
                         "fallback_from": recorded["fallback_from"], "offline_since": recorded["offline_since"]}
        return True, placement

    def pull(self):
        """Take each queued job of the central store placed on this kind into the mirror, in submit order, and each job placed on
        a workstation whose executor is offline when its decision's fallback is this kind (`offline`). A job whose recorded
        placement is not the policy's decision now is left queued (`confirm`), and the placement the mirror keeps is the decision's."""
        have = {job for job, _ in self.mirrored()}
        self.leases, self.owners = {}, {}
        for record in self.remote.records() if self.only is None else [self.remote.record(self.only) or {}]:
            job = record.get("job")
            if job is None or record.get("state") != "queued" or job in have:
                continue
            placed = kj_store.placement_of(record)
            moved = trusted = None
            if placed["executor"] != self.kind:
                if self.kind == kj_store.WORKSTATION or placed["executor"] != kj_store.WORKSTATION or placed.get("fallback") not in (None, self.kind):
                    continue  # no offline fallback of this kind
                go, trusted = self.confirm(job, record)
                if not go:
                    continue
                moved = self.offline(job, record, placed if trusted is None else trusted)
                if moved is None:
                    continue
            elif self.kind == kj_store.WORKSTATION and (placed.get("host") != self.host or self.remote.owner(job) != self.remote.operator()):
                continue
            if not self.fits(record):
                self.reason(job, NO_CLONE, "the job names no integration remote url" if self.kind == SERVER
                            else "no clone here with the job's integration remote url")
                continue
            if trusted is None:
                go, trusted = self.confirm(job, record)
                if not go:
                    continue
            mirrored = {k: v for k, v in record.items() if k not in ("state", "exit", "step")}
            mirrored.update(host=self.host, clone=self.clone, operator=self.operator)
            if moved or trusted is not None:
                mirrored["placement"] = moved or trusted
            with coord.Tx(self.store) as con:
                if con.execute("SELECT 1 FROM entries WHERE key = ?", (coord.JOB_KEYS + job,)).fetchone() is None:
                    con.execute("INSERT INTO entries (key, value, revision) VALUES (?, ?, 1)",
                                (coord.JOB_KEYS + job, json.dumps(mirrored, sort_keys=True, ensure_ascii=False)))
            kj_store.queue(self.store, job, mirrored)


class Presence:
    """The lease `jobexec/<host>/<operator>` a workstation executor holds on the queue it serves (`kj_store.exec_key`), so the
    executors of other kinds see it is live: `beat` takes it, renews it every JOB_LEASE_RENEW_S seconds and writes the time into the
    key's value (`seen`, which outlives the lease: the moment the executor was last known live), `drop` writes it a last time and
    releases the lease. Another executor of the same host and operator that holds it leaves this one with none, and `beat` tries again."""

    def __init__(self, remote):
        self.remote = remote
        self.key = kj_store.exec_key(platform.node(), remote.operator())
        self.token = self.revision = self.beaten = None

    def beat(self):
        """Take or renew the lease when due; a queue that cannot be reached leaves the lease to run out, as a dead executor's does."""
        if self.beaten is not None and time.monotonic() - self.beaten < JOB_LEASE_RENEW_S:
            return
        self.beaten = time.monotonic()
        with contextlib.suppress(kj_ops.Refusal, coord.Refused):
            if self.token is None:
                code, body = self.remote.claim(self.key, EXEC_LEASE_TTL_S, "jobexec")
                if code:
                    return
                self.token, self.revision = body["token"], body["revision"]
            elif not self.remote.renew(self.key, self.token, EXEC_LEASE_TTL_S):
                self.token = None
                return
            self.stamp()

    def stamp(self):
        value = json.dumps({"seen": round(time.time(), 3)})
        for _ in range(2):
            if self.remote.put(self.key, value, self.revision, self.token):
                self.revision += 1
                return
            found = self.remote.lease(self.key)
            if not found:
                return
            self.revision = found["revision"]

    def drop(self):
        if self.token is None:
            return
        with contextlib.suppress(kj_ops.Refusal, coord.Refused):
            self.stamp()
            self.remote.release(self.key, self.token)
        self.token = None


class Unprepared(Exception):
    """The clone a server job runs in could not be made ready: the message says why (a url, a clone, a fetch or a worktree)."""


class Home:
    """The clones of a server executor (`serve --kind server`): one directory per integration remote url under BASE, named by a short
    hash of the url, cloned at the first job that names the url and fetched before each. `prepare` brings the one of a job to the
    integration main (`origin/main`, detached: the executor's own tree, never a worker's) and, for a land job, makes the worktree
    `.claude/worktrees/agent-<id>` of the remote's branch `work/<id>`, where a workstation has the worker's own, so the CLI's `land`
    finds and releases it as it does there. Every git call is a child the executor's leases are kept up through (KEEP), under a
    time limit, with prompts off and only the transports of GIT_ALLOW_PROTOCOL."""

    CLONE_S, FETCH_S = 900.0, 300.0
    PROTOCOLS = "file:https:http:ssh:git"

    def __init__(self, base):
        self.base = Path(base)

    def dir_of(self, url):
        return self.base / hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]

    def run(self, args, cwd, limit, keep):
        """`git ARGS` in CWD: its last output line when it ends 0, else Unprepared naming the command and the line."""
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL=self.PROTOCOLS)
        group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        try:
            proc = subprocess.Popen(["git", *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **group)
        except OSError as error:
            raise Unprepared(f"git {args[0]} did not start: {str(error)[:150]}") from None
        until = time.monotonic() + limit
        try:
            while True:
                try:
                    text = proc.communicate(timeout=1.0)[0]
                    break
                except subprocess.TimeoutExpired:
                    keep()
                    if time.monotonic() > until:
                        kg_lock.end_group(proc)
                        proc.communicate()
                        raise Unprepared(f"git {args[0]} took more than {limit:g} s") from None
        except BaseException:
            if proc.poll() is None:
                kg_lock.end_group(proc)
            raise
        if proc.returncode != 0:
            raise Unprepared(f"git {args[0]} exit {proc.returncode}: {last_line(text)}")
        return (text or "").strip()

    def has_ref(self, clone, ref):
        p = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=clone, capture_output=True, text=True)
        return p.returncode == 0

    def prepare(self, record, keep=lambda: None):
        """The directory a job runs in: its url's clone made ready as the class says. Unprepared for a job with no usable url."""
        url = str(record.get("remote") or "")
        if not url or url.startswith("-") or any(c.isspace() or ord(c) < 32 for c in url):
            raise Unprepared(f"the job names no usable integration remote url: {url[:60]!r}")
        clone = self.dir_of(url)
        if not (clone / ".git").exists():
            self.base.mkdir(parents=True, exist_ok=True)
            self.run(["clone", "--quiet", "--", url, str(clone)], self.base, self.CLONE_S, keep)
        self.run(["fetch", "--quiet", "--prune", "origin"], clone, self.FETCH_S, keep)
        if self.has_ref(clone, "refs/remotes/origin/main"):
            self.run(["checkout", "--quiet", "--force", "--detach", "origin/main"], clone, self.FETCH_S, keep)
            self.run(["clean", "-fdq"], clone, self.FETCH_S, keep)
        if record.get("op") == "land":
            self.worktree(clone, str(record.get("subject") or ""), keep)
        return clone

    def worktree(self, clone, item, keep):
        """The worktree of the remote's `work/<item>` under the clone's .claude/worktrees (the name `agent-<item>` a worker's has), made
        again for each land job, so a stale one an earlier job left is replaced; Unprepared when the remote has no such branch."""
        branch = f"work/{item}"
        if not self.has_ref(clone, f"refs/remotes/origin/{branch}"):
            raise Unprepared(f"the integration remote has no branch {branch}: push the worker's branch there before the land job")
        path = clone / ".claude" / "worktrees" / f"agent-{item}"
        if path.exists():
            self.run(["worktree", "remove", "--force", str(path)], clone, self.FETCH_S, keep)
        self.run(["worktree", "prune"], clone, self.FETCH_S, keep)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.run(["worktree", "add", "--quiet", "-B", branch, str(path), f"origin/{branch}"], clone, self.FETCH_S, keep)


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


CRED_STEP = "credential"  # the step of a job refused because its identity has no usable credential
JOB_NAMES = ("KB_JOB", "KB_JOB_OPERATOR")  # set for a job's process, never inherited from the executor's own environment
POLICY_LESS = "default"  # the `decided_by` of the decision `kj_place` gives when no policy answered: the job runs as it did before placements


def job_env(record, environ=None):
    """The environment of the process of the job RECORD: ENVIRON (this process's by default) without the names an earlier job's
    credential set, plus what `kj_cred.resolve` gives for the identity the record's placement names (a job whose placement is
    absent, or is the decision of no policy (`decided_by` `default`), keeps the environment as it is). The placement of a job of a
    central queue is the one `Sync.confirm` wrote into the mirror from the policy's decision (`verify_placement`), so the identity
    and the group path (`decided_by`) are the decision's, never a member the job's own record on the queue holds; only those two
    members are read here. `kj_cred.Refused` when the
    identity has no usable credential. The environment always names the job and its submitter, `KB_JOB` and `KB_JOB_OPERATOR`
    (`kg_trailers.job_trailers` reads them for the commit's `KB-Job` and `KB-Operator`), whatever identity the job runs as."""
    environ = kj_cred.clean(dict(os.environ if environ is None else environ))
    for name in JOB_NAMES:
        environ.pop(name, None)
    if record.get("job"):
        environ["KB_JOB"] = str(record["job"])
        if record.get("operator"):
            environ["KB_JOB_OPERATOR"] = str(record["operator"])
    placed = record.get("placement")
    if not isinstance(placed, dict) or placed.get("decided_by") == POLICY_LESS or "identity" not in placed:
        return environ
    return {**environ, **kj_cred.resolve(placed["identity"], placed.get("decided_by"), record.get("operator"),
                                         kj_cred.cred_dir(environ), environ)}


def start_child(record, clone, log):
    """Start the job's process in CLONE as the leader of a process group of its own, stdin closed, its stdout and stderr
    appended to LOG, in the environment `job_env` gives: (the process, the size LOG had before it: where this run's output
    begins). `kj_cred.Refused` before anything starts when the job's identity has no usable credential."""
    env = job_env(record)
    log.parent.mkdir(parents=True, exist_ok=True)
    start = log.stat().st_size if log.exists() else 0
    options = record.get("options")
    if record["op"] == "land":  # a land job's passes never wait inside the CLI: the job waits for the merge request (`LandRun`)
        options = {**(options or {}), "wait_merge": 0}
    argv = [sys.executable] + kj_ops.argv(record["op"], record.get("subject", ""), options)
    group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    with open(log, "ab") as sink:
        proc = subprocess.Popen(argv, cwd=clone, env=env, stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT, **group)
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


FOLLOWER = "follower"  # the origin of the `job.run` row `kbjob.py follow` writes in the submitting clone
CI = "ci"  # the executor kind of a job a GitLab pipeline runs: it writes no row


def run_origin(store):
    """The origin an executor gives its `job.run` rows: the kind of the executor serving STORE (`server`, `workstation`, `ci`), the
    workstation for a clone's own queue."""
    return getattr(store, "kind", None) or kj_store.WORKSTATION


def record_run(store, job, record, state, origin=None, events=None):
    """Write the ops row `job.run` of a job that ended in STATE (succeeded, refused, failed or cancelled; none for another): its operation,
    the end as `class`, its attempt, the milliseconds it queued, waited for a lock or a merge, and ran, read from the job's own
    events (EVENTS, else the store's), and the job id and the ORIGIN of the row (the executor kind that ended the job, else
    `follower` for `kbjob.py follow`, which counts the job once more than the executor does: `kbjob.py stats` and the digest take
    the executor's). A job of the ci executor writes none (the follower's row is then the job's only one). Rows go through
    `ql_deliver.ops_row`: nothing in a test run. Never raises: a job never fails for its log."""
    try:
        if state not in RUN_ENDS:
            return
        origin = origin or run_origin(store)
        now = record if origin == FOLLOWER else kj_store.read_record(store, job) or record
        if origin == CI:
            return
        import ql_deliver
        events = job_events(store, job) if events is None else events
        ql_deliver.ops_row("job.run", op=record["op"], **{"class": state}, attempt=int(now.get("attempt", 1)), job=job.lower(), origin=origin,
                           **run_times(events))
    except Exception:  # noqa: BLE001 - see the docstring
        pass


def refuse_credential(store, job, record, log, reason, out):
    """End JOB, in running and started no process, refused at the step CRED_STEP with REASON (the `kj_cred.Refused` message, naming the
    identity and the path or variable): kept as the member `reason` of the job's record, here and on the queue, as one line of its
    output log and as one line printed. A job cancelled meanwhile stays cancelled."""
    try:
        move(store, job, "refused", step=CRED_STEP)
    except coord.Refused as refusal:
        if refusal.body.get("state") != "cancelled":
            raise
        record_run(store, job, record, "cancelled")
        print(f"{job} {record['op']} {record.get('subject') or '-'}: cancelled", file=out, flush=True)
        return
    with contextlib.suppress(sqlite3.Error):
        amend(store, job, reason=reason)
    remote = getattr(store, "remote", None)
    if remote is not None:
        with contextlib.suppress(kj_ops.Refusal, coord.Refused):
            remote.amend(job, reason=reason)
    with contextlib.suppress(OSError):
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"{record['op']} stopped at step {CRED_STEP}: {reason}\n")
    record_run(store, job, record, "refused")
    print(f"{job} {record['op']} {record.get('subject') or '-'}: refused at step {CRED_STEP}: {reason}", file=out, flush=True)


def unstarted(store, job):
    """The end of a job whose process did not start (`start_job` gave None): refused for a credential, else failed."""
    return "refused" if (kj_store.read_record(store, job) or {}).get("state") == "refused" else "failed"


def start_job(store, job, record, clone, log, out):
    """Start the child of a job already in running: (the process, the size LOG had before it) and the pid recorded in the job's record.
    A process that cannot start moves the job to failed (exit 127), prints one line and returns (None, 0); a job whose identity has no
    usable credential (`kj_cred.Refused`) starts no process and ends refused (`refuse_credential`), the same return."""
    try:
        proc, start = start_child(record, clone, log)
    except kj_cred.Refused as error:
        refuse_credential(store, job, record, log, str(error), out)
        return None, 0
    except OSError as error:
        move(store, job, "failed", exit=127)
        record_run(store, job, record, "failed")
        print(f"{job} {record['op']} {record.get('subject') or '-'}: failed, exit 127: {str(error)[:200]}", file=out, flush=True)
        return None, 0
    with contextlib.suppress(sqlite3.Error):
        amend(store, job, pid=proc.pid)
    return proc, start


def note_log(store, job, log):
    """Keep the path of a server job's output log in its record, here and on the queue (`log_file`: the log is in the clone of the server
    that ran it, not in the submitting clone, so `kbjob.py log` reads it from there when it runs on that host)."""
    with contextlib.suppress(sqlite3.Error):
        amend(store, job, log_file=str(log))
    remote = getattr(store, "remote", None)
    if remote is not None:
        with contextlib.suppress(kj_ops.Refusal, coord.Refused):
            remote.amend(job, log_file=str(log))


def note_condition(store, job, code, text, state, out):
    """A job that ended failed because tests.py refused the seconds of its test ceiling (`host_condition`) keeps the members `reason`
    (HOST_CONDITION) and `platform` (this host's, the central host's where the queue is central) in its record, on the queue
    too, and one line says so. The job is not run again, with this ceiling or another: a failed job is final, the ceiling is
    the project's file and no option of a job reaches it."""
    if state != "failed" or not host_condition(code, text):
        return
    members = {"reason": HOST_CONDITION, "platform": sys.platform}
    with contextlib.suppress(sqlite3.Error):
        amend(store, job, **members)
    remote = getattr(store, "remote", None)
    if remote is not None:
        with contextlib.suppress(kj_ops.Refusal, coord.Refused):
            remote.amend(job, **members)
    print(f"{job}: {HOST_CONDITION}: the seconds of the test ceiling were passed on this host ({sys.platform}); "
          "the job is not run again", file=out, flush=True)


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
    note_condition(store, job, number, text, state, out)
    return state


def run_job(store, job, record, clone, log, token, out):
    """Run one taken job (already in running) to its end with the lease renewed, in the calling thread; returns the state it moved
    to: `start_job`, a wait that renews the lease, then `finish_job`. A process that cannot start moves the job to failed (exit
    127); a signal to this process ends the child's group and moves the job to lost, then goes on; a job cancelled meanwhile
    (kbjob.py cancel) stays cancelled, one line says so and cancelled is returned. `drain` runs its jobs by the same two steps."""
    proc, start = start_job(store, job, record, clone, log, out)
    if proc is None:
        return unstarted(store, job)
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
    kj_store.amend_record(store, job, **members)


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
            raise Ended(unstarted(self.store, self.job))
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
            note_condition(self.store, self.job, fields.get("exit") or 0, self.text, state, self.out)

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
    other job is of no class. A job placed on a server (`Home`) is of the class of its integration remote url, whatever its operation:
    one at a time per clone (the lock a holder outside the executor keeps it waiting for stays the operation's)."""
    op, opts = job.get("op"), job.get("options") or {}
    key, lock = None, None
    if op == "land":
        key, lock = ("land", job.get("clone")), "landing"
    elif op == "sync-push":
        key, lock = ("sync-push",), "host-main"
    elif op == "check" and opts.get("name") == "tests-full":
        key, lock = ("tests-full",), "host-test"
    elif op in ("done", "stage-back"):
        key = ("item", job.get("subject"))
    if (job.get("placement") or {}).get("executor") == SERVER and job.get("remote"):
        key = ("server", job["remote"])  # one job at a time in a clone of the server (`Home`): a job moves its tree to the integration main
    return key, lock


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


def drain(store, clone, host, operator, out, slots=SLOTS, tick=None, home=None, only=None):
    """Run the queued jobs of this host, clone and operator to the end, at most SLOTS at a time and as `next_runnable` places them
    (submit order inside a class); the ids of the jobs that failed or were lost. A job whose lock a process outside the executor
    holds is moved to waiting-lock (event step: the lock; record member `holder`: its pid, clone and step) and started once the lock is free. A job another
    executor leased, or that left queued before this one moved it, is passed over. TICK, when given, is called at the start of each pass
    (an executor of a central queue syncs its mirror there, `Sync`). ONLY, a job id, leaves every other job of the store alone. HOME, a `Home` (a server executor), makes each job's clone ready
    before it starts and is where it runs, as the CLI would on a workstation; a job whose clone cannot be made ready ends failed."""
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

    def keep_up(job, token, one):
        """The leases of the jobs that run, and the job's own, renewed while its clone is made ready (a clone can take minutes)."""
        for other, mine in list(active.items()):
            if mine.get("run") is None:
                renew(other, mine["token"], mine)
        renew(job, token, one)

    def unprepared(job, record, token, error):
        """A job whose clone could not be made ready ends failed (exit 1), the reason in its log and in one line."""
        log = kj_store.log_path(clone, job)
        with contextlib.suppress(OSError):
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8", newline="\n") as sink:
                sink.write(f"kbjob.py: the clone could not be made ready: {error}\n")
        with contextlib.suppress(coord.Refused):
            move(store, job, "failed", exit=1)
        record_run(store, job, record, "failed")
        print(f"{job} {record['op']} {record.get('subject') or '-'}: failed, exit 1: the clone could not be made ready: {error}", file=out, flush=True)
        failed.append(job)
        release(job, token)

    def begin(job, record, token):
        """Take the job out of queued or waiting-lock into running and start its child; False when it did not start."""
        try:
            move(store, job, "running")
        except coord.Refused:
            release(job, token)
            return False
        where = clone
        if home is not None:
            one = {"renewed": time.monotonic()}
            try:
                where = str(home.prepare(record, lambda: keep_up(job, token, one)))
            except Unprepared as error:
                unprepared(job, record, token, error)
                return True
        if home is not None:
            note_log(store, job, kj_store.log_path(where, job))
        if record.get("op") == "land":  # a thread of its own drives the passes and the wait (`LandRun`)
            run = LandRun(store, where, {**record, "state": "running"}, token, out)
            active[job] = {"record": record, "token": token, "run": run, "renewed": time.monotonic()}
            run.start()
            return True
        log = kj_store.log_path(where, job)
        proc, start = start_job(store, job, record, where, log, out)
        if proc is None:
            if unstarted(store, job) == "failed":
                failed.append(job)
            release(job, token)
            return True
        active[job] = {"record": record, "token": token, "proc": proc, "start": start, "log": log, "renewed": time.monotonic()}
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
                    text = finish_text(one["log"], one["start"])
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
            seen = [(j, r) for j, r in pending(store, clone, host, operator, ("queued", "waiting-merge")) if j not in passed and only in (None, j)]
            for job, record in seen:  # a land job a dead executor left in its wait: polled again from its recorded pending
                if record["state"] == "waiting-merge" and job not in active and record.get("op") == "land" and kj_land.recorded_pending(record):
                    token = take_job(store, job)
                    if token is None:
                        passed.add(job)
                        continue
                    run = LandRun(store, str(home.dir_of(record["remote"])) if home is not None and record.get("remote") else clone, record, token, out)
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
            holders = outside(lock_holders(None if home is not None else clone), mine)  # a server's lands run in clones of its own: no landing lock of the executor's clone
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


def serve(root, store, once=False, out=None, idle_exit=None, slots=SLOTS, kind=None, remote=None, data=None, job=None):
    """`kbjob.py serve`: 0 when the queue was drained (--once), when IDLE_EXIT seconds passed with no live job of this host,
    clone and operator, or when this process ended by a signal; 1 when --once ran a job that failed, 2 where the clone has no
    git directory; a second serve for the same store on the host prints the running one's pid and returns 0. With REMOTE (a
    `kj_store.Remote`) and KIND (one of coord's placement executors) it serves the central queue: its jobs are kept in a mirror
    store (in DATA, else in the clone's `kb-jobs`) and `Sync` takes and posts them. With JOB (a job id; REMOTE and KIND needed) it
    runs that one job and ends (`job_exit`): its exit is 0 when the job succeeded, 1 when it failed or was refused, 2 when it was not
    taken."""
    out = out or sys.stdout
    clone = kj_store.clone_path(root)
    sync = home = None
    if remote is not None:
        where = data
        if kind == SERVER:  # the mirror and the clones of a server are one directory under DATA: its home
            base = Path(data) if data else Path(coord.store_of(root)).parent.parent / kj_store.LOG_DIR
            digest = hashlib.sha256("\0".join((remote.url, remote.operator())).encode("utf-8")).hexdigest()[:8]
            where = base / f"server-{digest}"
            home = Home(where / "clones")
        store = kj_store.Mirror(kj_store.mirror_path(root, remote, kind, where), remote, kind)
        sync = Sync(root, store, clone, out, job)
        if job is not None:  # a job this executor does not take is left as it was: no directory made, no move or event posted
            why = sync.refusal(job, kj_store.remote_record(remote, job))
            if why:
                print(f"kbjob.py: {why}; it stays as it was", file=sys.stderr)
                return 2
        if where is not None:
            Path(where).mkdir(parents=True, exist_ok=True)
    if kj_store.log_path(clone, "JB-00000000") is None:
        print("kbjob.py: serve needs a git clone for its job logs", file=sys.stderr)
        return 2
    path, holder = take_lock(clone, lock_name(root, store))
    if path is None:
        print(f"kbjob.py: serve already runs on this host: pid {holder['pid']} (clone {holder['clone']}, started {holder['started']})",
              file=out, flush=True)
        return 0 if job is None else 2
    presence = None  # a workstation executor holds its lease on the queue it serves: the clone's own, else the central one
    if remote is None or kind == kj_store.WORKSTATION:
        presence = Presence(remote if remote is not None else kj_store.LocalRemote(store))

    def tick():
        if presence is not None:
            presence.beat()
        if sync is not None:
            sync()
    before = None
    with contextlib.suppress(ValueError, OSError):  # not the main thread
        before = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    host, operator, failed, recovered, idle = platform.node(), kj_store.operator_id(), [], None, None
    try:
        while True:
            if job is None and (recovered is None or time.monotonic() - recovered >= RECOVER_S):
                failed += recovery_pass(root, store, out)
                recovered = time.monotonic()
            failed += drain(store, clone, host, operator, out, slots, tick, home, job)
            if once or job is not None:
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
        if presence is not None:
            presence.drop()
        drop_lock(path)
    if job is not None:
        return job_exit(store, job, out)
    return 1 if failed else 0


def job_exit(store, job, out):
    """The exit of a serve started for the one JOB, from its record in the mirror STORE once the drain ended: 0 succeeded; 1 failed,
    refused, lost, or cancelled on the queue; 2 when it never ran here (another executor took it first, or no record), a line saying so."""
    state = (kj_store.read_record(store, job) or {}).get("state")
    if state == "succeeded":
        return 0
    if state in ("failed", "refused", "lost") or (state == "cancelled" and (store.remote.record(job) or {}).get("state") == "cancelled"):
        return 1
    print(f"kbjob.py: {job} was not run here: state {state or 'none'} in this executor's mirror; it stays as the queue has it", file=sys.stderr)
    return 2
