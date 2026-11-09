#!/usr/bin/env python3
"""kbjob: queue an operation as a job in coord's store (stdlib only). Docs: kb/_self/coordination.md, section "Operation jobs".

  kbjob.py [--store PATH] submit OP [SUBJECT] [--by claude-<8 hex>] [--option KEY=VALUE]... [--name CHECK] [--no-ensure]
                                        after `ensure` (a job is never queued for nobody: when it had to start the executor it prints
                                        `kbjob: no executor, started pid N` on stderr, and when none comes up it queues nothing and
                                        exits 1; --no-ensure skips it), queue the operation OP on SUBJECT for this clone and print one JSON object,
                                        {job, state, deduped, seq, follow}: the job is the key job/JB-<8 characters>, its
                                        state queued, `follow` the command line `python3 _tools/kbjob.py follow JOB`.
                                        A second submit of the same clone, operation and subject (options aside) while the
                                        job is queued, running, waiting-lock, waiting-merge or lost returns that job with
                                        deduped true, also when submits race (one job); after a terminal state (succeeded,
                                        failed, refused, cancelled) a submit makes a new job with its attempt raised by one

  kbjob.py [--store PATH] serve [--once] [--parallel N] [--idle-exit S]
                                        run the queued jobs of this host, clone and operator in submit order, at most N at once
                                        (--parallel, default 3; `kj_exec.next_runnable`): lands of the clone, sync-pushes of the host,
                                        a tests-full check and the done and stage-back of one item each run one at a time, in submit order,
                                        and a job whose lock a process outside the executor holds (a session's own land or sync) waits as
                                        waiting-lock, (its event step `lock:host-main`, `lock:landing` or `lock:tests`, the holder's pid, clone and step in the record's `holder`), until the lock is free. Each is leased as jobrun/JOB, moved queued to running, run as the leader of a
                                        process group of its own in the clone with its output appended to the job's output.log,
                                        and moved to succeeded (exit 0), refused (exit 1 and a line `... stopped at step NAME:`)
                                        or failed. --once drains the queue and exits 0 (1 when a job failed); without it serve
                                        keeps polling, or ends after S seconds with no live job (--idle-exit, which `ensure` sets for a store of its own). One
                                        serve runs per store and host (a lock file per store in the host lock directory): a second serve
                                        for the same store exits 0 naming the running one's pid, one for another store runs beside it.
                                        At its start and every 30 s serve recovers the jobs a dead executor left in running, waiting-lock
                                        or waiting-merge (lease jobrun/JOB expired, pid gone): lost, then queued again with attempt
                                        raised by one the first time, failed the second; a child still running is adopted.

  kbjob.py [--store PATH] follow JOB [--since SEQ] [--timeout S]
                                        print one line per `job` event of JOB after sequence SEQ (default 0), flushed at once:
                                        `JOB STATE OP SUBJECT [step=NAME] [exit=N]`, never a line of the command's own output.
                                        On a terminal state it prints `JOB STATE [step=NAME] exit=N log=PATH` and exits 0
                                        (succeeded), 1 (failed, refused) or 3 (cancelled). Past --timeout (default 1500 s, under the
                                        Monitor tool's deadline of 1800 s) it prints `follow: still running, continue with --since N`
                                        and exits 4: the next follow from N misses no move. It only reads.

  kbjob.py [--store PATH] status [JOB | --active]
                                        print the JSON of kj_store.status for JOB (with `holder`, {pid, clone, step}, while the job waits
                                        in waiting-lock for a lock a process outside the executor holds), or the JSON list of the records of every job
                                        not in a terminal state, oldest first
  kbjob.py [--store PATH] log JOB [--tail N]
                                        print the last N lines (default 40) of the job's output log; exit 1 before it has one
  kbjob.py [--store PATH] ping          print the pid of this host's executor of the store (the pid its host file names, while that
                                        process runs) and exit 0; print `kbjob: no executor on this host` and exit 1 when none runs
  kbjob.py [--store PATH] ensure        ping; when none runs, start `serve` detached (a session of its own, stdin closed, output appended
                                        to kb-jobs/serve.log in the git common directory, so it outlives the session that started it),
                                        wait up to 10 s for the host file to name a live pid and print `kbjob: serving pid N` (exit 0);
                                        exit 1 printing the log's last line when none came up. The child inherits the environment; for
                                        a --store other than the clone's own it ends by itself after 60 s with no live job
  kbjob.py [--store PATH] login-item --print
                                        print a macOS LaunchAgent plist (Label, ProgramArguments serve, RunAtLoad, KeepAlive,
                                        StandardErrorPath) and a systemd user unit that run serve at login; it writes nothing and
                                        touches no file under the home directory: the operator saves and loads what they choose
  kbjob.py [--store PATH] stats         print for each operation one line from the `job.run` ops rows (one per finished job, written by the
                                        executor; `kb/_self/querylog.md`) of this clone's query log: `OP n=N queued_ms=MEDIAN (p95 P)
                                        wait_ms=MEDIAN (p95 P) run_ms=MEDIAN (p95 P)`, the median and the nearest-rank 95th percentile
                                        in ms of the time a job queued, waited in waiting-lock or waiting-merge, and ran, as
                                        `backlog.py landings` measures a landing; operations in name order; exit 0, a note when no row
  kbjob.py [--store PATH] cancel JOB    move a queued job to cancelled; move a running one to cancelled and end its process group
                                        with TERM, then KILL (a POSIX host, the job's own); for the submitting operator only,
                                        exit 1 for another's

OP is one of the closed table `kj_ops.OPS`, so `publish`, `answer` and any operator-only command are no operation:
  land SUBJECT          options wait_merge=SECONDS, trailer='Key: value' (repeatable)
  done SUBJECT          options commit=true, trailer='Key: value' (repeatable)
  stage-back SUBJECT    options check=true, self_reviewed=DOC (repeatable), trailer='Key: value' (repeatable)
  sync-push             no subject, no option
  check --name NAME     no subject; NAME is backlog-check, tests-full or tests-changed
SUBJECT is the id of an item of this clone's backlog. --by is claude- and 8 lowercase hex digits, never a full session id.
The store is --store, else KB_COORD_STORE, else the clone's own (coord.py's). Exit codes of submit: 0 queued or joined; 2 an
operation, subject, option or --by the table does not allow (the message names what is), or no store; of follow, status, log and
cancel: as each says, 2 for a job the store does not hold. `kj_store.submit` and
`kj_store.status` are the same as a function, the interface the kb MCP server calls.

Answers: how to queue an operation (land, done, stage-back, sync-push, a check) as a job and get the live job back when it is already queued
Use: python3 _tools/kbjob.py [--store PATH] submit OP [SUBJECT] [--by claude-<8 hex>] [--option KEY=VALUE]... [--name CHECK]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

import bl_base
import coord
import kj_exec
import kj_follow
import kj_ops
import kj_store

ROOT = Path(__file__).resolve().parent.parent


def build_parser():
    parser = argparse.ArgumentParser(prog="kbjob.py", description=__doc__.split("\n", 1)[0])
    parser.add_argument("--store", default=None, help="the coord SQLite file (default: KB_COORD_STORE, else the clone's)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("submit", help="queue an operation as a job, or return the live one")
    p.add_argument("op", help="one of " + ", ".join(kj_ops.OPS))
    p.add_argument("subject", nargs="?", default="", help="the backlog id of land, done and stage-back")
    p.add_argument("--by", default=None, help="claude- and 8 lowercase hex digits")
    p.add_argument("--option", action="append", default=[], metavar="KEY=VALUE", help="an option of the operation, repeatable")
    p.add_argument("--name", default=None, help="the check of the operation check")
    p.add_argument("--no-ensure", action="store_true", help="queue the job without starting an executor when none runs")
    sub.add_parser("ping", help="print the pid of this host's executor and exit 0, or exit 1 when none runs")
    sub.add_parser("ensure", help="start the executor detached when none runs, wait for it, print `kbjob: serving pid N`")
    li = sub.add_parser("login-item", help="print a macOS LaunchAgent plist and a systemd user unit that run serve at login")
    li.add_argument("--print", dest="show", action="store_true", help="print them (the only mode: nothing is installed)")
    s = sub.add_parser("serve", help="run the queued jobs of this host, clone and operator, at most --parallel at once")
    s.add_argument("--once", action="store_true", help="drain the queue and exit (1 when a job failed)")
    s.add_argument("--parallel", type=int, default=kj_exec.SLOTS, metavar="N", help="run at most N jobs at once (default %(default)s)")
    s.add_argument("--idle-exit", type=float, default=None, metavar="S", help="exit 0 after S seconds with no live job (`ensure` sets it for a store of its own)")
    f = sub.add_parser("follow", help="print one line per move of a job and exit with its result (0, 1, 3; 4 past --timeout)")
    f.add_argument("job")
    f.add_argument("--since", type=int, default=0, help="the event sequence after which to print (default 0)")
    f.add_argument("--timeout", type=float, default=kj_follow.DEFAULT_TIMEOUT_S, help="seconds before `still running` and exit 4 (default %(default)s)")
    t = sub.add_parser("status", help="print a job's JSON, or every job not in a terminal state")
    t.add_argument("job", nargs="?", default=None)
    t.add_argument("--active", action="store_true", help="every job not in a terminal state")
    g = sub.add_parser("log", help="print the end of a job's output log")
    g.add_argument("job")
    g.add_argument("--tail", type=int, default=kj_follow.TAIL_LINES, help="lines to print (default %(default)s)")
    sub.add_parser("stats", help="print each operation's count and the median and p95 of its queue wait, lock wait and run time")
    c = sub.add_parser("cancel", help="cancel a job of the submitting operator, ending a running one's process group")
    c.add_argument("job")
    return parser


def options_of(args):
    """The --option pairs and --name as the dict kj_store.submit takes (a repeated key a list)."""
    given = {}
    for pair in args.option:
        name, equals, value = pair.partition("=")
        if not equals or not name:
            raise kj_ops.Refusal(f"an option is KEY=VALUE, not {pair[:40]!r}")
        given.setdefault(name, []).append(value)
    if args.name is not None:
        given.setdefault("name", []).append(args.name)
    return {name: values if len(values) > 1 else values[0] for name, values in given.items()}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, parser)
    except (kj_ops.Refusal, coord.Refused) as error:
        print(f"kbjob.py: {error}", file=sys.stderr)
        return 2
    except sqlite3.Error as error:
        print(f"kbjob.py: store: {error}", file=sys.stderr)
        return 2


def ensure_command(store):
    """`kbjob.py ensure`: 0 printing `kbjob: serving pid N`, 1 printing the last line of the serve log."""
    pid, _, error = kj_exec.ensure(str(ROOT), store)
    if error is not None:
        print(f"kbjob: no executor: {error}", file=sys.stderr)
        return 1
    print(f"kbjob: serving pid {pid}")
    return 0


def with_holder(body, store):
    """BODY (kj_store.status's JSON) with the member `holder` ({pid, clone, step}) of a job in waiting-lock: the lock holder it waits for."""
    held = (kj_store.read_record(store, body["job"]) or {}).get("holder")
    return {**body, "holder": held} if held else body


def stat_lines(rows):
    """One line per operation of the `job.run` ROWS, in name order: `OP n=N queued_ms=MEDIAN (p95 P) wait_ms=... run_ms=...`
    (`bl_ops.median` and `nearest_rank`, as `backlog.py landings` computes them)."""
    import bl_ops
    groups = {}
    for row in rows:
        if row.get("event") == "job.run" and isinstance(row.get("op"), str):
            groups.setdefault(row["op"], []).append(row)
    lines = []
    for op, found in sorted(groups.items()):
        parts = [f"{op} n={len(found)}"]
        for key in ("queued_ms", "wait_ms", "run_ms"):
            values = sorted(r[key] for r in found if bl_ops.number(r.get(key)))
            parts.append(f"{key}={bl_ops.median(values):.0f} (p95 {bl_ops.nearest_rank(values, 95):.0f})" if values else f"{key}=-")
        lines.append(" ".join(parts))
    return lines


def stats_command():
    """`kbjob.py stats`: 0 printing the lines of `stat_lines` over this clone's ops rows, or a note when it has no job.run row."""
    import bl_stall
    try:
        lines = stat_lines(bl_stall.ops_rows(str(ROOT)))
    except Exception as error:  # noqa: BLE001 - an unreadable log is said, never read as no row
        print(f"kbjob.py: the ops rows could not be read: {str(error)[:200]}", file=sys.stderr)
        return 1
    print("\n".join(lines) if lines else "kbjob: no job.run row yet")
    return 0


def run(args, parser):
    if args.command == "stats":
        return stats_command()
    if args.command == "serve":
        return kj_exec.serve(str(ROOT), kj_store.resolve_store(ROOT, args.store), once=args.once, idle_exit=args.idle_exit,
                             slots=args.parallel)
    if args.command == "login-item":
        if not args.show:
            parser.error("login-item only prints: pass --print")
        return kj_exec.login_item(str(ROOT), args.store)
    if args.command == "ping":
        return kj_exec.ping(str(ROOT), kj_store.resolve_store(ROOT, args.store))
    if args.command == "ensure":
        return ensure_command(kj_store.resolve_store(ROOT, args.store))
    if args.command == "submit":
        if not args.no_ensure:
            given = options_of(args)
            kj_ops.check_job(args.op, args.subject, args.by or None, given)  # a refused job starts no executor
            if kj_ops.OPS[args.op]["subject"]:
                bl_base.load_settings(str(ROOT))
                if not (ROOT / bl_base.rel_dir() / f"{args.subject}.json").is_file():
                    raise kj_ops.Refusal(f"{args.subject} is no item of this clone's backlog: a subject is the id of an item file under {bl_base.rel_dir()}")
            pid, started, error = kj_exec.ensure(str(ROOT), kj_store.resolve_store(ROOT, args.store))
            if error is not None:
                print(f"kbjob: no executor and none started, job not queued: {error}", file=sys.stderr)
                return 1
            if started:
                print(f"kbjob: no executor, started pid {pid}", file=sys.stderr, flush=True)
        body = kj_store.submit(str(ROOT), args.op, args.subject, args.by, options_of(args), store=args.store)
        print(json.dumps(body, sort_keys=True, ensure_ascii=False))
        return 0
    store = kj_store.resolve_store(ROOT, args.store)
    if args.command == "follow":
        return kj_follow.follow(str(ROOT), store, args.job, args.since, args.timeout, sys.stdout)
    if args.command == "status":
        if (args.job is None) == (not args.active):
            parser.error("status takes a JOB or --active, one of them")
        body = kj_follow.active(store) if args.active else with_holder(kj_store.status(str(ROOT), args.job, store=store), store)
        print(json.dumps(body, sort_keys=True, ensure_ascii=False))
        return 0
    if args.command == "log":
        return kj_follow.tail_of(str(ROOT), store, args.job, args.tail, sys.stdout)
    return kj_follow.cancel(str(ROOT), store, args.job, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
