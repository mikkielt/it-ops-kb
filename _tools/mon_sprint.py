"""kbmon's sprint panel (kb/_self/monitoring.md): every sprint of the backlog with its state, its items' counts by status, its
next item, its open items, the times of its last done commits and its waiting gates, and each landing in progress.

The sprints are the backlog's items of kind `sprint` whose status is `active` or `planned`, read through `bl_base.Backlog`
and `bl_view.ready` from the item files of the local `origin/main` ref (`bl_view.items_at`, no fetch; the checkout's own
files where the ref cannot be read), with the count of commits the checkout is behind that ref: the state is `active`, `approved` (planned, its start gate answered with an approval, so only
`backlog.py start` is left) or `planned`, in that order. `items` counts the sprint's items by status; `next` is the item
`backlog.py next` offers (an active sprint only); `waiting` is each open blocking gate of the sprint or of one of its
open items, `{item, gate}`. A landing in progress is an item whose newest `land.step` row has no later `land.end` row in the
ops rows: `{item, step, since}`, the last step recorded and the time of the landing's first step. A root with no backlog
has no sprints. The panel writes nothing and makes no request. Imports no sibling at load; `bl_base`, `bl_view`, `bl_plan`,
`bl_stall`, `ql_capture` and `ql_distill` where it reads them.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

REF = "origin/main"  # the ref the items are read from: the integration branch as this clone last fetched it
CHECKOUT = "checkout"  # `source` where REF cannot be read
DONE_SUBJECT = re.compile(r"^chore\(backlog\): done ([A-Z]{2}-[a-z0-9]+)")  # the commit `backlog.py done` makes
DONE_KEPT = 5  # done commits of a sprint the panel keeps the times of
OPEN_KEPT = 20  # open items of a sprint the panel keeps
REFRESH_S = 30  # seconds the live view serves the last result: a sprint's state changes with a commit or a landing
SPRINT_STATES = ("active", "approved", "planned")  # the order the panel lists them in
SPRINT_ROWS = 12  # sprints in the text view
LANDING_ROWS = 6  # landings in the text view
WAITING_ROWS = 2  # waiting gates under a sprint in the text view
STATE_WIDTH = 10  # columns of a sprint row's state


def sprint_state(sp, approved):
    """`active`, `approved` or `planned` for a sprint item; None for a sprint that is neither (closed)."""
    if sp.get("status") == "active":
        return "active"
    if sp.get("status") == "planned":
        return "approved" if approved(sp) else "planned"
    return None


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def backlog_at(root):
    """(backlog, source, behind): the backlog of the item files of REF and `origin/main`, with the commits HEAD is behind
    it; where REF cannot be read, the checkout's own backlog, `checkout` and None."""
    import bl_base
    import bl_view
    bl_base.load_settings(root)
    bl = bl_base.Backlog(root)
    try:
        items = bl_view.items_at(root, REF)
        behind = bl_base.git(root, "rev-list", "--count", f"HEAD..{REF}").strip()
    except Exception:  # noqa: BLE001 - no such ref, no repository: the checkout's files answer
        return bl, CHECKOUT, None
    bl.items, bl.raw = items, {}
    return bl, REF, int(behind) if behind.isdigit() else None


def done_commits(root):
    """{item id: UTC time} of the newest first-parent commit of REF that is `chore(backlog): done ID`; {} where it has none."""
    import bl_base
    try:
        text = bl_base.git(root, "log", "--first-parent", "-E", "--grep=^chore\\(backlog\\): done ", "--format=%ct%x09%s", REF)
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for ln in text.splitlines():
        at, _, subject = ln.partition("\t")
        m = DONE_SUBJECT.match(subject)
        if m and at.isdigit():
            out.setdefault(m.group(1), stamp(int(at)))
    return out


def sprint_row(bl, sid, state, done_at):
    import bl_base
    import bl_view
    items = bl.sprint_items(sid)
    counts = {}
    for i in items:
        status = str(bl.items[i].get("status"))
        counts[status] = counts.get(status, 0) + 1
    holders = [sid] + [i for i in items if bl.items[i].get("status") not in ("done", "dropped")]
    waiting = [{"item": i, "gate": g["id"]} for i in holders for g in bl_base.open_gates(bl.items[i])]
    nxt = bl_view.ready(bl, sid) if state == "active" else []
    left = sorted((i for i in items if bl.items[i].get("status") not in ("done", "dropped")), key=bl.order_key)
    open_items = [{"id": i, "title": str(bl.items[i].get("title") or ""), "status": str(bl.items[i].get("status"))} for i in left]
    times = sorted(done_at[i] for i in items if i in done_at)[-DONE_KEPT:]
    return {"id": sid, "title": str(bl.items[sid].get("title") or ""), "state": state, "items": counts,
            "next": nxt[0] if nxt else None, "next_title": str(bl.items[nxt[0]].get("title") or "") if nxt else None,
            "open": open_items[:OPEN_KEPT], "done_at": times, "waiting": waiting}


def sprints(root):
    """{sprints, source, behind}: the sprint rows, `origin/main` or `checkout` as the source of the items, and the commits
    the checkout is behind `origin/main` (None where unknown)."""
    import bl_plan
    bl, source, behind = backlog_at(root)
    done_at = done_commits(root) if source == REF else {}
    rows = []
    for sid, sp in sorted(bl.items.items()):
        state = sprint_state(sp, bl_plan.start_approved) if sp.get("kind") == "sprint" else None
        if state:
            rows.append(sprint_row(bl, sid, state, done_at))
    rows.sort(key=lambda r: SPRINT_STATES.index(r["state"]))  # stable: ids stay in order within a state
    return {"sprints": rows, "source": source, "behind": behind}


def in_spool_order(rows):
    """ROWS (`bl_stall.ops_rows`, sorted by time and id) with the rows of this host's spool that share a millisecond put
    back in the order the spool file holds them; the committed rows stay first and in their order."""
    import ql_capture
    import ql_distill
    spool = ql_capture.spool_dir()
    at = {}
    for f in sorted(Path(spool).glob("tools-*.jsonl")) if spool is not None and Path(spool).is_dir() else []:
        for r in ql_distill.spool_rows(f)[0]:
            at.setdefault(r.get("id"), len(at))
    return sorted(rows, key=lambda r: (str(r.get("ts")), at.get(r.get("id"), -1)))


def landings(root):
    """[{item, step, since}] of the landings in progress, newest first; [] when the ops rows cannot be read."""
    try:
        import bl_stall
        rows = in_spool_order(bl_stall.ops_rows(str(root)))
    except Exception:  # noqa: BLE001 - an unreadable log shows no landing
        return []
    cur = {}
    for r in rows:
        item = r.get("item")
        if r.get("event") == "land.end":
            cur.pop(item, None)
        elif r.get("event") == "land.step" and isinstance(item, str):
            cur.setdefault(item, {"item": item, "since": r.get("ts")})["step"] = r.get("step")
    return sorted(({"item": v["item"], "step": v["step"], "since": v["since"]} for v in cur.values()),
                  key=lambda v: (str(v["since"]), v["item"]), reverse=True)


def collect(ctx):
    return {**sprints(ctx.root), "landings": landings(ctx.root)}


def progress(sp):
    """`4/11 done · next ST-… · counts by status`, or `not started` or `waits on start gate`."""
    if sp["state"] == "approved":
        return "not started"
    if sp["state"] == "planned":
        return "waits on start gate"
    counts = sp.get("items", {})
    done = counts.get("done", 0) + counts.get("dropped", 0)
    parts = [f"{done}/{sum(counts.values())} done"]
    if sp.get("next"):
        parts.append(f"next {sp['next']}")
    parts.append(", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))) or "no items")
    return " · ".join(parts)


def lines(data):
    """The body rows: where the items were read from (and how far the checkout is behind it), a row for each sprint (id, state padded to STATE_WIDTH, progress) with its first waiting gates
    under it, then `landing` rows (item, last step, since)."""
    rows = []
    if data.get("sprints") and data.get("source"):
        behind = data.get("behind")
        rows.append(f"items from {data['source']}" + (f", checkout {behind} commit{'' if behind == 1 else 's'} behind" if behind else ""))
    shown = data.get("sprints", [])[:SPRINT_ROWS]
    for sp in shown:
        rows.append(f"{sp['id']}  {sp['state'].ljust(STATE_WIDTH)}{progress(sp)}")
        waiting = [w for w in sp.get("waiting", []) if not (w["item"] == sp["id"] and w["gate"] == "start")]
        for w in waiting[:WAITING_ROWS]:
            rows.append(f"    waiting  {w['item']}/{w['gate']}")
        if len(waiting) > WAITING_ROWS:
            rows.append(f"    +{len(waiting) - WAITING_ROWS} more waiting")
    if len(data.get("sprints", [])) > len(shown):
        rows.append(f"+{len(data['sprints']) - len(shown)} more sprints")
    if not data.get("sprints"):
        rows.append("sprints none")
    for lg in data.get("landings", [])[:LANDING_ROWS]:
        rows.append(f"landing  {lg['item']}  {lg['step']}  since {str(lg['since']).replace('T', ' ')}")
    if len(data.get("landings", [])) > LANDING_ROWS:
        rows.append(f"+{len(data['landings']) - LANDING_ROWS} more landings")
    return rows
