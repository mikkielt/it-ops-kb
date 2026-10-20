"""kbmon's cleanup panel (kb/_self/monitoring.md): every leftover `backlog.py tidy` lists, with the verdict of
`bl_clean.safe_to_remove`, its reason and the bytes a removal frees, and a count of each class.

The data is `bl_selfcheck.leftovers`, the read `selfcheck`'s leftovers line shares: `rows` (each `{class, verdict, reason,
bytes}` with the `path` or the `branch`, the `item` when a record names one and `approximate` where the walk that measures
the bytes was cut), `counts` ({class: {remove, keep}} for worktree, branch, sandbox and scratch), `removable` (the rows
with verdict `remove`), `bytes` (what they free), `approximate`, `free_gib` of the clone's volume, `limit_gib` (tidy's
disk-pressure limit) and `pressure`. The bytes of all the `remove` rows are walked for `bl_selfcheck.BYTES_BUDGET_S`
seconds together, so the panel stays inside its timeout; a row past the budget keeps 0 bytes and is `approximate`. The
text view shows the removable rows first, `ROWS_SHOWN` at most, then the kept ones, with the count of the rest.

The panel reads and removes nothing: it takes the verdict, never acts on it (`tidy --apply` removes). It reads the local coord
store (`--store`, else `KB_COORD_STORE`, else the clone's default); `--url` is `unsupported`. A clone with no integration
main is `unsupported`. Imports `mon_base`; `bl_base` and `bl_selfcheck` (which reads `bl_clean`) where it reads them.
"""
import contextlib
import os
from pathlib import Path

import mon_base

REFRESH_S = 30  # seconds the live view serves the last result: the verdicts move with a landing, the bytes with a walk
ROWS_SHOWN = 12  # rows in the text view, the removable ones first
LABEL = 8  # columns of a row's class
SIZE = 10  # columns of a row's bytes


@contextlib.contextmanager
def coord_store(store):
    """`KB_COORD_STORE` set to STORE (when given) for the length of the block: `bl_clean.coord_state` runs `coord.py`, which
    reads it. The coord panel takes `ctx.store` before the variable, so it does not read this one."""
    if not store:
        yield
        return
    old = os.environ.get("KB_COORD_STORE")
    os.environ["KB_COORD_STORE"] = str(Path(store).expanduser())
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("KB_COORD_STORE", None)
        else:
            os.environ["KB_COORD_STORE"] = old


def collect(ctx):
    if ctx.url:
        raise mon_base.Unsupported("the leftovers are read from the local coord store, not through --url")
    import bl_base
    import bl_selfcheck
    bl_base.load_settings(ctx.root)
    bl = bl_base.Backlog(ctx.root)
    try:
        with coord_store(ctx.store):
            return bl_selfcheck.leftovers(bl)
    except bl_base.Rejected as e:  # no integration main to compare against, or an unreadable coord store
        raise mon_base.Unsupported(str(e)) from None


def size_text(n, approximate=False):
    import bl_clean
    return (bl_clean.fmt_size(n) + (" or more" if approximate else "")) if n else "-"


def lines(data):
    """The body rows: the removable count, bytes and free space, a count of each class, then the rows."""
    counts = data.get("counts") or {}
    rows = sorted(data.get("rows") or [], key=lambda r: r.get("verdict") != "remove")
    free = data.get("free_gib")
    head = (f"{data.get('removable', 0)} removable ({size_text(data.get('bytes', 0), data.get('approximate'))}) of {len(rows)}"
            + (f", {free:g} GiB free of the {data.get('limit_gib', 0):g} GiB limit" if free is not None else "")
            + ("; disk pressure" if data.get("pressure") else ""))
    out = ["! " + head if data.get("pressure") else head,
           "  ".join(f"{cls} {c.get('remove', 0)}/{c.get('remove', 0) + c.get('keep', 0)}" for cls, c in counts.items())
           + "  (remove/all)"]
    for r in rows[:ROWS_SHOWN]:
        name = r.get("branch") or Path(str(r.get("path", ""))).name
        out.append(f"{r.get('verdict', '?'):6} {r.get('class', '?'):{LABEL}} "
                   f"{size_text(r.get('bytes', 0), r.get('approximate')):>{SIZE}}  {name}: {r.get('reason', '')}")
    if len(rows) > ROWS_SHOWN:
        out.append(f"+{len(rows) - ROWS_SHOWN} more in --json")
    return out
