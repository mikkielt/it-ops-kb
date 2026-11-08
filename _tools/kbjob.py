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

OP is one of the closed table `kj_ops.OPS`, so `publish`, `answer` and any operator-only command are no operation:
  land SUBJECT          options wait_merge=SECONDS, trailer='Key: value' (repeatable)
  done SUBJECT          options commit=true, trailer='Key: value' (repeatable)
  stage-back SUBJECT    options check=true, self_reviewed=DOC (repeatable), trailer='Key: value' (repeatable)
  sync-push             no subject, no option
  check --name NAME     no subject; NAME is backlog-check, tests-full or tests-changed
SUBJECT is the id of an item of this clone's backlog. --by is claude- and 8 lowercase hex digits, never a full session id.
The store is --store, else KB_COORD_STORE, else the clone's own (coord.py's). Exit codes: 0 queued or joined; 2 an operation,
subject, option or --by the table does not allow (the message names what is), or no store. `kj_store.submit` and
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
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        try:
            return kj_exec.serve(str(ROOT), kj_store.resolve_store(ROOT, args.store), once=args.once)
        except (kj_ops.Refusal, coord.Refused, sqlite3.Error) as error:
            print(f"kbjob.py: {error}", file=sys.stderr)
            return 2
    try:
        body =kj_store.submit(str(ROOT), args.op, args.subject, args.by, options_of(args), store=args.store)
    except kj_ops.Refusal as refusal:
        print(f"kbjob.py: {refusal}", file=sys.stderr)
        return 2
    except coord.Refused as refused:
        print(f"kbjob.py: {refused}", file=sys.stderr)
        return 2
    except sqlite3.Error as error:
        print(f"kbjob.py: store: {error}", file=sys.stderr)
        return 2
    print(json.dumps(body, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
