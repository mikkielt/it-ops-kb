"""`backlog.py ops`: the operational rows of one sprint's items (kb/_self/backlog.md, Stalled work; kb/_self/tools.md).

  ops SP                       print, as text and read only (exit 0, also when the sprint has no row), each ops row that
                               names one of the sprint's items: `land.step` and `land.end` of a landing, `done.refused`
                               with its reasons and `agent.run` (a worker's run: its group is the agent type), oldest
                               first

  landings                     print, as text and read only (exit 0), one line per landing step and one for `land.end`
                               (whole landings) from every ops row of the clone: `n`, `failed` (exit not 0), `median`
                               and `p95` in ms (nearest rank), slowest median first; `step_stats(rows)` computes them

The rows are `bl_stall.ops_rows`': this host's spool and the committed ops sidecars, each row id once, a closed event
with its closed keys only, never event text. A row that names no item (a `sync.gate`, a `test.run`, an `agent.run` of a
subagent with no item) and a row of an item outside the sprint are left out. An id the backlog holds no file for is
refused, exit 2, as any command refuses one; so is an id that is no sprint. Standard library only; imports `bl_base`,
`bl_cli` and `bl_stall` at load and never `backlog` (a layer rule). It registers its own subcommand when imported, so
`backlog.py` carries only the import.
"""
import bl_base
import bl_cli
import bl_stall
from bl_base import Rejected, say

ROW_OWN = ("id", "ts", "surface", "v", "event", "item")  # a row's own keys: a line prints them in its own places


def sprint_items(bl, sid):
    """The ids of the items of the sprint `sid`. KeyError (an id with no item file) is `main`'s to refuse; Rejected
    (an id that is no sprint) exits 2."""
    bl_base.need(bl, sid)
    kind = bl.items[sid].get("kind")
    if kind != "sprint":
        raise Rejected(f"ops takes a sprint id: {sid} is a {kind}, not a sprint (`backlog.py show {sid}` names its "
                       "sprint)")
    return set(bl.sprint_items(sid))


def value_text(v):
    return ",".join(str(x) for x in v) if isinstance(v, list) else str(v)


def row_line(bl, r):
    """`ts  event  item label  key=value ...`: the row's closed keys, as the store keeps them."""
    rest = " ".join(f"{k}={value_text(v)}" for k, v in r.items() if k not in ROW_OWN)
    return f"{r.get('ts')}  {r.get('event')}  {bl.label(r['item'])}" + (f"  {rest}" if rest else "")


def args_ops(p):
    p.add_argument("id", help="the sprint (SP-...)")


def cmd_ops(bl, a):
    ids = sprint_items(bl, a.id)
    try:
        rows = [r for r in bl_stall.ops_rows(str(bl.root)) if r.get("item") in ids]
    except Exception:  # noqa: BLE001 - an unreadable log is said, never read as no row
        say("ops: the ops rows could not be read")
        return 1
    for r in rows:
        say(row_line(bl, r))
    say(f"ops: {len(rows)} row(s) of {len(ids)} item(s) of {bl.label(a.id)}")
    return 0


bl_cli.register("ops", cmd_ops, args_ops, help="print the operational rows of a sprint's items")


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def median(values):
    """The middle of the sorted `values`; the mean of the two middle ones for an even count."""
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    total = values[mid - 1] + values[mid]
    return total // 2 if total % 2 == 0 else total / 2


def nearest_rank(values, pct):
    """The nearest-rank percentile of the sorted `values`: the value at rank ceil(pct/100 * n)."""
    return values[max(1, -(-len(values) * pct // 100)) - 1]


def step_stats(rows):
    """`{name: {count, failed, median_ms, p95_ms}}` over the ops `rows`: a name for each step of the `land.step` rows
    and `land.end` for whole landings. `failed` counts the rows whose exit is not 0; a row without a numeric `ms` is
    left out."""
    groups = {}
    for r in rows:
        name = r.get("step") if r.get("event") == "land.step" else "land.end" if r.get("event") == "land.end" else None
        if not isinstance(name, str) or not number(r.get("ms")):
            continue
        groups.setdefault(name, []).append((r["ms"], r.get("exit") != 0))
    out = {}
    for name, pairs in groups.items():
        ms = sorted(m for m, _ in pairs)
        out[name] = {"count": len(ms), "failed": sum(1 for _, bad in pairs if bad), "median_ms": median(ms),
                     "p95_ms": nearest_rank(ms, 95)}
    return out


def stat_line(name, s):
    return f"{name}  n={s['count']} failed={s['failed']} median={s['median_ms']:.0f} p95={s['p95_ms']:.0f}"


def args_landings(p):
    pass


def cmd_landings(bl, a):
    try:
        rows = bl_stall.ops_rows(str(bl.root))
    except Exception:  # noqa: BLE001 - an unreadable log is said, never read as no row
        say("landings: the ops rows could not be read")
        return 1
    stats = step_stats(rows)
    for name, s in sorted(stats.items(), key=lambda kv: (-kv[1]["median_ms"], kv[0])):
        say(stat_line(name, s))
    say(f"landings: {len(stats)} step name(s) (land.end: whole landings), slowest median first")
    return 0


bl_cli.register("landings", cmd_landings, args_landings,
                help="print each landing step's count, failures, median and 95th percentile duration")
