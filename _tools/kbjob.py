#!/usr/bin/env python3
"""kbjob: queue an operation as a job in coord's store (stdlib only). Docs: kb/_self/coordination.md, section "Operation jobs".

  kbjob.py [--store PATH] submit OP [SUBJECT] [--by claude-<8 hex>] [--option KEY=VALUE]... [--name CHECK]
                                        queue the operation OP on SUBJECT for this clone and print one JSON object,
                                        {job, state, deduped, seq, follow}: the job is the key job/JB-<8 characters>, its
                                        state queued, `follow` the command line `python3 _tools/kbjob.py follow JOB`.
                                        A second submit of the same clone, operation and subject (options aside) while the
                                        job is queued, running, waiting-lock, waiting-merge or lost returns that job with
                                        deduped true, also when submits race (one job); after a terminal state (succeeded,
                                        failed, refused, cancelled) a submit makes a new job with its attempt raised by one

  kbjob.py [--store PATH] serve [--once]
                                        run the queued jobs of this host, clone and operator in submit order, one at a time
                                        (`kj_exec`): each is leased as jobrun/JOB, moved queued to running, run as the leader of a
                                        process group of its own in the clone with its output appended to the job's output.log,
                                        and moved to succeeded (exit 0), refused (exit 1 and a line `... stopped at step NAME:`)
                                        or failed. --once drains the queue and exits 0 (1 when a job failed); without it serve
                                        keeps polling. A second serve on the host exits 0 naming the running one's pid.
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
                                        print the JSON of kj_store.status for JOB, or the JSON list of the records of every job
                                        not in a terminal state, oldest first
  kbjob.py [--store PATH] log JOB [--tail N]
                                        print the last N lines (default 40) of the job's output log; exit 1 before it has one
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
    s = sub.add_parser("serve", help="run the queued jobs of this host, clone and operator, one at a time")
    s.add_argument("--once", action="store_true", help="drain the queue and exit (1 when a job failed)")
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


def run(args, parser):
    if args.command == "serve":
        return kj_exec.serve(str(ROOT), kj_store.resolve_store(ROOT, args.store), once=args.once)
    if args.command == "submit":
        body = kj_store.submit(str(ROOT), args.op, args.subject, args.by, options_of(args), store=args.store)
        print(json.dumps(body, sort_keys=True, ensure_ascii=False))
        return 0
    store = kj_store.resolve_store(ROOT, args.store)
    if args.command == "follow":
        return kj_follow.follow(str(ROOT), store, args.job, args.since, args.timeout, sys.stdout)
    if args.command == "status":
        if (args.job is None) == (not args.active):
            parser.error("status takes a JOB or --active, one of them")
        body = kj_follow.active(store) if args.active else kj_store.status(str(ROOT), args.job, store=store)
        print(json.dumps(body, sort_keys=True, ensure_ascii=False))
        return 0
    if args.command == "log":
        return kj_follow.tail_of(str(ROOT), store, args.job, args.tail, sys.stdout)
    return kj_follow.cancel(str(ROOT), store, args.job, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
