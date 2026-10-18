"""kbmon's sprint panel (kb/_self/monitoring.md): every sprint of the backlog with its state, its items' counts by status, its
next item and its waiting gates, and each landing in progress.

The sprints are the backlog's items of kind `sprint` whose status is `active` or `planned`, read through `bl_base.Backlog`
and `bl_view.ready`: the state is `active`, `approved` (planned, its start gate answered with an approval, so only
`backlog.py start` is left) or `planned`, in that order. `items` counts the sprint's items by status; `next` is the item
`backlog.py next` offers (an active sprint only); `waiting` is each open blocking gate of the sprint or of one of its
open items, `{item, gate}`. A landing in progress is an item whose newest `land.step` row has no later `land.end` row in the
ops rows: `{item, step, since}`, the last step recorded and the time of the landing's first step. A root with no backlog
has no sprints. The panel writes nothing and makes no request. Imports no sibling at load; `bl_base`, `bl_view`, `bl_plan`,
`bl_stall`, `ql_capture` and `ql_distill` where it reads them.
"""
from pathlib import Path

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


def sprint_row(bl, sid, state):
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
    return {"id": sid, "state": state, "items": counts, "next": nxt[0] if nxt else None, "waiting": waiting}


def sprints(root):
    import bl_base
    import bl_plan
    bl_base.load_settings(root)
    bl = bl_base.Backlog(root)
    rows = []
    for sid, sp in sorted(bl.items.items()):
        state = sprint_state(sp, bl_plan.start_approved) if sp.get("kind") == "sprint" else None
        if state:
            rows.append(sprint_row(bl, sid, state))
    return sorted(rows, key=lambda r: SPRINT_STATES.index(r["state"]))  # stable: ids stay in order within a state


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
    return {"sprints": sprints(ctx.root), "landings": landings(ctx.root)}


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
    """The body rows: a row for each sprint (id, state padded to STATE_WIDTH, progress) with its first waiting gates
    under it, then `landing` rows (item, last step, since)."""
    rows = []
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
