#!/usr/bin/env python3
"""The observed signals (LOG rows) of a root or of kb/_self (stdlib only): agents record them, the operator confirms them.

  kblog.py record --root R OBSERVATION --runs ID;ID --from DATE --to DATE --context C [--links TEXT]
                                         add a row with status `proposed` and print its id
  kblog.py confirm ID --root R --by operator
                                         make a proposed row `active`; refused without `--by operator`
  kblog.py invalidate ID --root R --reason TEXT [--date DATE]
                                         withdraw a proposed or an active row; the row stays. Open to agents
  kblog.py sweep [--root R] [--dry-run] [--date DATE]
                                         invalidate every proposed or active row whose context is broken (rules
                                         below), naming the context in the reason; open to agents
  kblog.py list [--root R] [--status S] [--context REF]
                                         the rows of one root, or of every root and kb/_self, one per line:
                                         root, id, status, observed_from, observed_to, context, observation
                                         (tab-separated)

R is a root's name (`python3 _tools/kbroot.py list`) or `_self` for kb/_self; there is no default. The rows go to the
root's `_logs.csv`; its format and rules are check.py's (LOGS, LOG_COLS, LOG_ID) and `kb/_self/content-rules.md`, Logs.

The row store is kbdecide.py's (`Ledger`, `Store`, `load`, `save`, `find`, `invalidate`, `sweep`), shared with the
operator's decisions and not copied: a row written here is checked by check.py (`check_logs`) after the write, and a
change that adds an error is undone and refused, exit 2.

  - A row's id is `L-` and 8 base32 characters of the sha256 of its observation, context, runs and dates, so the same
    observation of the same runs is one id and the second is refused.
  - A row is a derived aggregate (a count, a median, a range over some days) with the query-log runs it came from and
    the dates it covers, never raw event text: `record` is refused where check.py refuses it (a line break, a JSON
    object, a timestamp with a time of day, a leak-scan hit, an observation with no number, a free-text cell over
    `check.LOG_TEXT_MAX`), and the observation is kept as given, never reflowed into something that passes.
  - `confirm` is the operator's: it needs `--by operator`, which an agent passes only after the operator said so. A
    row names no maker, so confirming records nothing but the status.
  - A row stays active until its context stops holding. `sweep` covers every root and kb/_self, or the one `--root`,
    and invalidates a proposed or active row when a context reference no longer holds, as kbdecide.py's sweep reads
    it: an `item:` is dropped, a `source:` has a `superseded_by`, an `article:` or a `domain:` is gone, and, unlike a
    decision, a `fact:` whose key no fact has any more (the observation was about a fact that was reworded or
    removed, so a pointer to another fact would claim what was not observed). The reason names the reference
    (`item:TK-x dropped`), several joined by `; `, and the day goes to `links`. The row stays in its file; nothing is
    deleted. `--dry-run` prints what it would invalidate and writes nothing.

Exit: 0 done, 2 refused (a rule above, an unknown root or id, or a file that cannot be read) or bad arguments.
"""
import argparse, sys

import kbcommon, kbdecide
from kbdecide import LOGS, OPERATOR, Refused, Store, day, field, find, load, need, need_operator, row_id, save


def cmd_record(a):
    store = Store(a.root, LOGS)
    rows = load(store)
    observation = a.observation.strip()  # as given: check.py refuses a line break, never one flattened here
    runs = "; ".join(kbcommon.split_list(a.runs))
    context = "; ".join(kbcommon.split_list(a.context))
    for what, value in (("an observation", observation), ("--runs (the query-log runs it came from)", runs),
                        ("--context", context)):
        if not value:
            raise Refused(f"a log row needs {what}")
    first, last = day(a.observed_from), day(a.observed_to)
    lid = row_id(LOGS, observation, context, runs, first, last)
    if any(field(r, "id") == lid for r in rows):
        raise Refused(f"{lid} is already in {store.label}: the same observation of the same runs and days")
    row = dict.fromkeys(LOGS.cols, "")
    row.update(id=lid, observation=observation, source_run_ids=runs, observed_from=first, observed_to=last,
               context=context, status="proposed", links=(a.links or "").strip())
    save(store, rows + [row])
    print(f"{lid}\tproposed\t{store.name}")
    return 0


def cmd_confirm(a):
    need_operator(a, "confirms a log row")
    store = Store(a.root, LOGS)
    rows = load(store)
    row = find(rows, a.id, store)
    need(row, ("proposed",), a.id, "confirmed", LOGS.noun)
    row["status"] = "active"
    save(store, rows)
    print(f"{a.id}\tactive\t{store.name}")
    return 0


def cmd_invalidate(a):
    return kbdecide.invalidate(a, LOGS)


def cmd_sweep(a):
    return kbdecide.sweep(a, LOGS)


def matches(row, ref):
    """Whether the row's context names `ref`: a `kind:value` part, or a bare value of any kind."""
    ref = ref.strip()
    return any(ref in (f"{kind}:{value}", value) for kind, value in kbcommon.context_refs(row.get("context")))


def cmd_list(a):
    n = 0
    for store in kbdecide.stores(a.root, LOGS):
        for r in load(store):
            if a.status and field(r, "status") != a.status:
                continue
            if a.context and not matches(r, a.context):
                continue
            n += 1
            print("\t".join([store.name, field(r, "id"), field(r, "status"), field(r, "observed_from"),
                             field(r, "observed_to"), field(r, "context"), field(r, "observation")]))
    print(f"logs={n}")
    return 0


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, help, root_required=True):
        p = sub.add_parser(name, help=help)
        p.add_argument("--root", required=root_required, help=f"a root's name, or {kbdecide.SELF_ROOT} for kb/_self")
        return p

    p = add("record", "add a proposed log row")
    p.add_argument("observation", help="the derived aggregate, one line with a number in it")
    p.add_argument("--runs", required=True, help="`;`-separated query-log run ids it was derived from")
    p.add_argument("--from", dest="observed_from", required=True, help="YYYY-MM-DD, the first day it covers")
    p.add_argument("--to", dest="observed_to", required=True, help="YYYY-MM-DD, the last day it covers")
    p.add_argument("--context", required=True, help="`;`-separated kind:value references (item, fact, source, article, domain)")
    p.add_argument("--links", help="free text")
    p = add("confirm", "the operator confirms a proposed log row")
    p.add_argument("id")
    p.add_argument("--by", help=f"must be {OPERATOR}")
    p = add("invalidate", "withdraw a proposed or active log row, keeping it")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = add("sweep", "invalidate the log rows whose context is broken", root_required=False)
    p.add_argument("--dry-run", action="store_true", help="print what would be invalidated and write nothing")
    p.add_argument("--date", help="YYYY-MM-DD, the day taken as today (default: today)")
    p = add("list", "the log rows of one root or of all", root_required=False)
    p.add_argument("--status", choices=LOGS.status)
    p.add_argument("--context", help="only the rows whose context names this kind:value (or bare value)")
    return ap


COMMANDS = {"record": cmd_record, "confirm": cmd_confirm, "invalidate": cmd_invalidate, "sweep": cmd_sweep,
            "list": cmd_list}


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        return COMMANDS[a.cmd](a)
    except Refused as e:
        print(f"refused: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
