"""kbmon's coord panel (kb/_self/monitoring.md): the live claims with their holder, seconds left and budget beside spend,
the newest events with their sequence numbers, and the live intent and progress digest.

The panel runs `coord.py list`, `coord.py wait --since 0 --timeout 0` and `coord.py digest` as three child processes at
once, on the local store (`--store`, else `KB_COORD_STORE`, else the clone's default) or on a `coord.py serve` server
(`--url` with `--key-file`, which coord.py reads: the panel never opens the key file). A local store that is not there
is `absent` and is not created. A server that cannot be reached, or that answers no command within `CHILD_SECONDS`, is
`timeout`. Imports `mon_base`; `coord` only to name the default store.
"""
import atexit
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import mon_base

COORD = Path(__file__).resolve().with_name("coord.py")
CHILD_SECONDS = 30  # the longest the three commands may take; the panel's own bound is kbmon's --timeout
EVENTS_KEPT = 10  # newest events in the data
EVENTS_SHOWN = 5  # newest events in the text view
DIGEST_LINES = 20
SIDE_WIDTH = 100  # columns from which the events sit beside the claims
SIDE_COLUMN = 50  # where they start in a body row: column 52 less the two gutter columns
MIN_KEY = 8
SUBJECTS = ("key", "item", "topic", "touch", "path", "fact", "session")
WHOS = ("holder", "operator", "session")
UNREACHABLE = "cannot reach"  # what coord.py prints when it cannot connect to a --url

_children = set()
_declared = {}  # thread id -> the state its collect asked for


def _reap():
    for child in list(_children):
        if child.poll() is None:
            child.kill()


atexit.register(_reap)


def _worker(module, ctx, box):
    """mon_base's worker, then the state `declare` asked for in place of unsupported: a panel can say absent and timeout
    for itself, which mon_base's own worker cannot."""
    _inner(module, ctx, box)
    state = _declared.pop(threading.get_ident(), None)
    if state:
        box["state"] = state


if getattr(mon_base._worker, "__module__", None) != __name__:
    _inner = mon_base._worker
    mon_base._worker = _worker


def declare(state, reason):
    """End collect in `state` (absent or timeout) with `reason` as its data."""
    _declared[threading.get_ident()] = state
    raise mon_base.Unsupported(reason)


def local_store(ctx):
    store = ctx.store or os.environ.get("KB_COORD_STORE")
    if not store:
        import coord
        store = coord.default_store()
    return str(Path(store).expanduser()) if store else None


def connection(ctx):
    """(coord.py's connection arguments, the data's source) for the url or the local store; absent when no store file is
    there."""
    if ctx.url:
        if not ctx.key_file:
            raise mon_base.Unsupported("--url needs --key-file")
        return ["--url", ctx.url, "--key-file", ctx.key_file], "url"
    store = local_store(ctx)
    if not store or not Path(store).is_file():
        declare("absent", "no coord store file")
    return ["--store", store], "local"


def start(argv):
    child = subprocess.Popen([sys.executable, str(COORD), *argv], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8")
    _children.add(child)
    return child


def last_line(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    return lines[-1].removeprefix("coord.py: ") if lines else ""


def fetch(conn):
    """The output of list, wait and digest, started together and each read until CHILD_SECONDS after the start."""
    commands = {"list": ["list"], "wait": ["wait", "--since", "0", "--timeout", "0"],
                "digest": ["digest", "--key", "*", "--lines", str(DIGEST_LINES)]}
    children = {name: start(conn + argv) for name, argv in commands.items()}
    deadline = time.monotonic() + CHILD_SECONDS
    out = {}
    try:
        for name, child in children.items():
            try:
                text, err = child.communicate(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                declare("timeout", f"coord.py {name} gave no answer in {CHILD_SECONDS} seconds")
            if child.returncode != 0:
                why = last_line(err) or f"exit {child.returncode}"
                if UNREACHABLE in why:
                    declare("timeout", why)
                raise RuntimeError(f"coord.py {name}: {why}")
            out[name] = text
    finally:
        for child in children.values():
            if child.poll() is None:
                child.kill()
            child.wait()
            for pipe in (child.stdout, child.stderr):
                pipe.close()
            _children.discard(child)
    return out


def claim_of(row, now):
    return {"key": row["key"], "holder": row["holder"], "left_s": max(0, int(row["expires"] - now)),
            "budget_usd": row.get("budget_usd"), "spend_usd": row.get("spend_usd"),
            "over_budget": bool(row.get("over_budget"))}


def collect(ctx):
    conn, source = connection(ctx)
    out = fetch(conn)
    now = time.time()
    claims = [claim_of(r, now) for r in json.loads(out["list"]) if r.get("holder")]
    events = json.loads(out["wait"])["events"][-EVENTS_KEPT:]
    return {"source": source, "claims": claims,
            "events": [{"seq": e["seq"], "kind": e["kind"], "fields": e.get("fields", {})} for e in reversed(events)],
            "digest": [x for x in out["digest"].splitlines() if x.strip()]}


def usd(value):
    return "-" if value is None else f"${value:.2f}"


def cell(text, n):
    return text if len(text) <= n else text[:max(1, n - 1)] + "…"


def table(claims, limit):
    """The claims as rows [(flag, text)]: a header and a row for each claim, no wider than `limit` characters, the key cut
    first, then the holder, with the gap between columns 2 and, where that is too wide, 1."""
    head = ("key", "holder", "left", "budget", "spend")
    body = [(c["key"], c["holder"], f"{c['left_s']}s", usd(c["budget_usd"]), usd(c["spend_usd"])) for c in claims]
    widths = [max(len(h), *(len(r[i]) for r in body)) for i, h in enumerate(head)]
    gap = 2
    for floor, index in ((MIN_KEY, 0), (6, 1)):
        while sum(widths) + gap * 4 > limit and widths[index] > floor:
            widths[index] -= 1
    if sum(widths) + gap * 4 > limit:
        gap = 1
    gap_text = " " * gap

    def row(cells):
        return gap_text.join(cell(c, w).ljust(w) for c, w in zip(cells, widths)).rstrip()

    return [(False, row(head))] + [(c["over_budget"], row(r)) for c, r in zip(claims, body)]


def event_text(event):
    fields = event["fields"] if isinstance(event.get("fields"), dict) else {}
    pick = lambda names: next((str(fields[n]) for n in names if fields.get(n)), "")  # noqa: E731
    subject = pick(SUBJECTS) or next((str(v) for v in fields.values()), "")
    who = pick(WHOS)
    kind = str(event["kind"])
    kind = kind.ljust(10) if len(kind) < 10 else kind + " "
    return f"#{event['seq']}  {kind}{subject}" + (f"  {who}" if who and who != subject else "")


def lines(data, width=80):
    """The body rows: the claims table (a row over budget starts `! `) with the newest events beside it from column 52 at
    100 columns or more, else under it, then two lines of the intent digest."""
    claims, events = data.get("claims", []), data.get("events", [])[:EVENTS_SHOWN]
    side = width >= SIDE_WIDTH
    left = table(claims, SIDE_COLUMN - 2 if side else width - 2) if claims else [(False, "claims    none")]
    right = ["events"] + [event_text(e) for e in events] if events else ["events    none"]
    rows = []
    if side:
        for i in range(max(len(left), len(right))):
            flag, text = left[i] if i < len(left) else (False, "")
            rows.append(("! " if flag else "") + (text.ljust(SIDE_COLUMN) + (right[i] if i < len(right) else "")).rstrip())
    else:
        rows = [("! " if flag else "") + text for flag, text in left] + right
    intents = [x for x in data.get("digest", []) if x.startswith("intent ")][:2]
    rows.append("intents   " + (intents[0] if intents else "none"))
    rows += ["          " + x for x in intents[1:]]
    return rows
