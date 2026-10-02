#!/usr/bin/env python3
"""The observed signals (LOG rows) of a root or of kb/_self (stdlib only): agents record them, the operator confirms them.

  kblog.py record --root R OBSERVATION --runs ID;ID --from DATE --to DATE --context C [--links TEXT]
                                         add a row with status `proposed` and print its id
  kblog.py propose --root R --since DAY [--until DAY] [--store DIR] [--context REF] [--dry-run]
                                         derive aggregates from the ops sidecar's rows and add each as a `proposed`
                                         row; print one line per row added and a count line
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

`propose` reads the ops sidecar of the query log's store (`kb/_querylog/ops/`, `--store DIR` for another; kb/_self/querylog.md,
Distill) through ql_store's readers and gates, never a spool file, and makes a small closed set of aggregates from the rows
of the days `--since` to `--until` (default: no end): one row for each event and context, its observation a count of the
event's rows, how many of them ended with a nonzero `exit`, and the median and the range of its `ms`, written by this
tool from numbers only (`ops land.step: 7 rows, 2 with a nonzero exit, ms median 1200, range 300 to 9000`). A row's runs are
the runs that held those rows, its dates the first and last day of them, and its context `item:ID` of the item (or sprint)
the event names. An event with no item key (`sync.gate`, `test.run`, `ci.pipeline`, `intake.detect`, an `agent.run` with
no item) has no context of its own: it is aggregated only when `--context REF` names what it is about, else left out and
counted. A row of the sidecar that is not the closed shape (ql_store.ops_line_problems) is left out and counted. No
event, id of a row, time of day, person or text reaches a row, and a row goes through the same path as `record`, one
`save`, so check.py's rules apply and one refusal leaves the file as it was. The id is `record`'s, so an aggregate of the
same runs and days is the row already there (any status, an invalidated one included) and the second run adds nothing;
only the operator confirms (`confirm --by operator`), `propose` never activates. Exit 0 also when it proposes nothing.

Exit: 0 done, 2 refused (a rule above, an unknown root or id, or a file that cannot be read) or bad arguments.
"""
import argparse, sys
from pathlib import Path

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


# The aggregates `propose` makes, closed: the rows of one event and context, a count, the rows whose `exit` is not 0
# and, for the event's `ms`, the median (the whole number between the two middle values, rounded down) and the range.
NO_CONTEXT = "no-context"


def middle(values):
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) // 2


def observation_of(event, rows):
    """The one-line aggregate of the rows of one event (each a closed ops line): numbers and the event's name only."""
    out = [f"{len(rows)} row" + ("" if len(rows) == 1 else "s")]
    codes = [r["exit"] for r in rows if "exit" in r]
    if codes:
        out.append(f"{sum(1 for c in codes if c != 0)} with a nonzero exit")
    times = [r["ms"] for r in rows if "ms" in r]
    if times:
        out.append(f"ms median {middle(times)}, range {min(times)} to {max(times)}")
    return f"ops {event}: " + ", ".join(out)


def ops_rows(store_dir, since, until):
    """([(run id, day, closed ops line)] of the days since..until, how many lines were left out as not closed): a line
    is read with ql_store's readers and kept when ql_store.ops_line_problems finds nothing."""
    import ql_store
    rows, bad = [], 0
    for p, objs in ql_store.records(ql_store.ops_files(store_dir)):
        for n, o in objs:
            if ql_store.ops_line_problems(o, f"{p.name}:{n}"):
                bad += 1
                continue
            d = o["ts"][:10]
            if d >= since and (until is None or d <= until):
                rows.append((p.stem, d, o))
    return rows, bad


def aggregates(rows, fallback):
    """[(event, context, runs, first day, last day, observation)] sorted, and how many rows had no context: a row's own
    `item` (or `sprint`) is its context, else `fallback` (the `--context` text) when there is one."""
    groups, none = {}, 0
    for run, d, o in rows:
        own = o.get("item") or o.get("sprint")
        context = f"item:{own}" if own else fallback
        if not context:
            none += 1
            continue
        groups.setdefault((o["event"], context), []).append((run, d, o))
    out = []
    for (event, context), g in sorted(groups.items()):
        days = sorted(d for _, d, _ in g)
        out.append((event, context, sorted({run for run, _, _ in g}), days[0], days[-1], observation_of(event, [o for _, _, o in g])))
    return out, none


def cmd_propose(a):
    store = Store(a.root, LOGS)
    since, until = day(a.since), day(a.until) if a.until else None
    if until is not None and until < since:
        raise Refused(f"--until {until} is before --since {since}")
    fallback = "; ".join(kbcommon.split_list(a.context))
    if any(not kind for kind, _ in kbcommon.context_refs(fallback)):
        raise Refused(f"--context {fallback!r} is not kind:value references ({', '.join(kbcommon.CONTEXT_KINDS)})")
    import ql_base
    store_dir = Path(a.store) if a.store else ql_base.STORE
    if not store_dir.is_dir():
        raise Refused(f"{store_dir} is no query-log store")
    rows = load(store)
    have = {field(r, "id") for r in rows}
    read, bad = ops_rows(store_dir, since, until)
    new, kept = [], 0
    found, none = aggregates(read, fallback)
    for _, context, runs, first, last, observation in found:
        run_ids = "; ".join(runs)
        lid = row_id(LOGS, observation, context, run_ids, first, last)
        if lid in have:
            kept += 1
            continue
        have.add(lid)
        row = dict.fromkeys(LOGS.cols, "")
        row.update(id=lid, observation=observation, source_run_ids=run_ids, observed_from=first, observed_to=last,
                   context=context, status="proposed")
        new.append(row)
    if new and not a.dry_run:
        save(store, rows + new)
    for r in new:
        print(f"{r['id']}\tproposed\t{store.name}\t{r['context']}\t{r['observation']}")
    print(f"proposed={len(new)} known={kept} {NO_CONTEXT}={none} not-closed={bad}" + (" dry-run" if a.dry_run else ""))
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
    p = add("propose", "derive proposed log rows from the ops sidecar")
    p.add_argument("--since", required=True, help="YYYY-MM-DD, the first day of the ops rows read")
    p.add_argument("--until", help="YYYY-MM-DD, the last day (default: no end)")
    p.add_argument("--store", help="a query-log store directory (default: kb/_querylog)")
    p.add_argument("--context", help="`;`-separated kind:value references for the events that name no item")
    p.add_argument("--dry-run", action="store_true", help="print what would be proposed and write nothing")
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


COMMANDS = {"record": cmd_record, "propose": cmd_propose, "confirm": cmd_confirm, "invalidate": cmd_invalidate, "sweep": cmd_sweep,
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
