"""kbmon's sessions panel (kb/_self/monitoring.md): the processes working in a checkout of the clone, the clone's worktrees
with their branches and the stalled items with their signals.

The processes are `backlog.py procs`' inventory (`bl_procs.snapshot`): pid, age and class (`orphan`, `hook` or `foreign`),
each with its checkout as a path relative to the clone (`.` is the clone itself; a worktree outside it is its directory
name, with the parents that tell it from a same-named one), never an absolute one. A process whose command name is `claude` is a Claude Code session: `headless`, with its item,
when its checkout is a worktree on a `work/<id>` branch, else `interactive`; any other process has no session. The worktrees
are `git worktree list`'s, and the stalled items are `bl_stall.collect`'s, only those with a signal. `operator` is this
clone's operator id and role (`kbwho.operator()`, never an email) and `intents` the live session intents of the coord store
(`coord.py digest`: session, item and the `operator` the hook posted, none for an intent that carries no operator; a
session id or operator that is a session id is the label `mon_view.session_label` gives, never the raw id); a
store that is not there or does not answer leaves `intents` out. The panel makes no
forge request, so the `mr-dead` signal is never read here (`backlog.py stalled` reads it). `dispatch` lists the dispatch runs
of this clone, read from the claims ledger of its git dir (`bl_base.claims_ledger`): for each record that `dispatch` gave a
`worker_pid` or a `worker_session`, the item, the pid, the session (the label `mon_view.session_label` gives) and whether
the worker is `alive` (its pid still runs; none where the host cannot tell), so a dead worker shows beside the live ones;
a ledger that is not there or does not read gives an empty list. `sessions` lists the live Claude Code sessions: one
entry for each `claude` process in a checkout of the clone, with its `label` (`mon_view.session_label`, null when nothing
names the session's id), `role` (the first row of `ROLES` that fits), `item` and `item_title`, `sprint` and
`sprint_title`, `step`, `started` (the process's start), `last_activity` and `spend_usd` (the newest row and the priced
usage rows of the session's own spool file, null without one). A session's id is read from a dispatch record of a claims
ledger (the pid, then the session), the claim records of its checkout's ledger, the coord intents and leases and the
hook's per-session state file names under its checkout, never from a command line or an environment; a raw id leaves
this module as its label only. A host that cannot list working
directories gives no processes and `procs_unreadable`, the reason, so the operator and the intents still show; a root with
no backlog items has no `stalled` key. Imports `mon_base` and `mon_view`; `bl_procs`,
`bl_stall`, `bl_base`, `bl_cost`, `ql_base`, `ql_distill` and `ql_report` where it reads them.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import mon_base
import mon_view

CLAUDE = "claude"  # the command name of a Claude Code process
REFRESH_S = 30  # seconds the live view serves the last result: the stalled signals read git for each claimed item
WORK_BRANCH = re.compile(r"work/([^/\s]+)")
PROCS_SHOWN = 12  # processes in the text view, orphans first
TREES_SHOWN = 12  # worktrees in the text view, those on a work/ branch first
LABEL = 10  # columns of a body row's label
MIN_CHECKOUT = 8
INTENTS_KEPT = 20  # live session intents in the data
INTENTS_SHOWN = 6  # live session intents in the text view
COORD_SECONDS = 10  # the longest the digest may take
DISPATCH_KEPT = 20  # dispatch runs in the data
DISPATCH_SHOWN = 6  # dispatch runs in the text view, live ones first
DIGEST_LINES = 200  # digest lines read: the live leases and intents the sessions list is built from
SESSIONS_KEPT = 30  # sessions in the data
SESSIONS_SHOWN = 8  # sessions in the text view
TITLE_CHARS = 40  # characters of an item title in the text view
CLAIM_TOPIC = "backlog-claim"  # the topic of the intent a `backlog.py claim` posts (the dispatching session's, not the worker's)
REMEDIATE = "remediate/"  # the coord key `kbask.py remediate` claims while its observer session runs
HOOK_STATE = ("_cache", "coord_hook")  # under a checkout: the hook's `<session id>.json` of each session it announced
BARE_DIR = "bare"  # the sandbox directory of a benchmark's bare twins (`bench_multi.BARE`): `<dir>/bare/agentN`
AGENT_DIR = re.compile(r"agent\d+")
MULTI_DIR = re.compile(r"multi-[0-9a-f]{8}")  # `bench_multi.clone_path`: `<scratch>/multi-<hash>/agentN`
PLAN_KINDS = ("epic", "sprint")  # the items a planner works on
ROLES = ("worker", "sprint runner", "planner", "reviewer", "interactive", "benchmark agent", "bare twin", "observer",
         "unknown")  # the roles `role_of` gives


def no_request(argv, cwd=None):
    """The runner of bl_stall's forge reads: the panel starts no network request, so every read fails at once."""
    raise OSError("kbmon makes no forge request")


def display_names(root, bases):
    """{real path: name shown} for the checkouts BASES: `.` for the clone itself, the path under it for a worktree inside
    it, else the directory name, with as many parent directories added as tell it from another outside worktree of the
    same name (`a/wt`, `b/wt`), never an absolute path."""
    base = os.path.realpath(root)
    out = {}
    outside = []
    for b in bases:
        if b == base:
            out[b] = "."
            continue
        rel = os.path.relpath(b, base)
        if rel.startswith("..") or os.path.isabs(rel):
            outside.append(b)
        else:
            out[b] = rel.replace(os.sep, "/")
    parts = {b: [x for x in Path(b).parts if x != Path(b).anchor] for b in outside}
    depth = dict.fromkeys(outside, 1)
    while True:
        names = {b: "/".join(parts[b][-depth[b]:]) for b in outside}
        clash = [b for b in outside if list(names.values()).count(names[b]) > 1 and depth[b] < len(parts[b])]
        if not clash:
            break
        for b in clash:
            depth[b] += 1
    out.update(names)
    return out


def branches(root):
    """([{path, branch}] of the clone's worktrees, paths as `display_names` gives them; {real path: branch})."""
    import bl_stall
    found = [(os.path.realpath(p), b) for p, b in bl_stall.worktrees(str(root)) or []]
    names = display_names(root, [p for p, _ in found])
    return [{"path": names[p], "branch": b} for p, b in found], dict(found)


def checkout_paths(procs, bases):
    """{pid: real path of the checkout the process is in}. A process's `where` holds the checkout's directory name only: a
    name that two checkouts share is told apart by the process's working directory, and a process that cannot be placed
    is left out."""
    import bl_procs
    by_name = {}
    for b in bases:
        by_name.setdefault(Path(b).name, []).append(b)
    cwds = None
    out = {}
    for p in procs:
        found = by_name.get(p["where"].split("/", 1)[0], [])
        if len(found) > 1:
            if cwds is None:
                cwds = bl_procs.cwd_map()[0] or {}
            cwd = cwds.get(p["pid"])
            found = [max((b for b in found if cwd and bl_procs.inside(cwd, b)), key=len, default=None)]
        if found and found[0]:
            out[p["pid"]] = found[0]
    return out


def session_of(base, by_path):
    """(session, item) of a Claude Code process in the checkout BASE (None when unplaced) whose worktrees' branches are
    BY_PATH."""
    m = WORK_BRANCH.fullmatch(by_path.get(base) or "")
    return ("headless", m.group(1)) if m else ("interactive", None)


def backlog(root):
    """The `bl_base.Backlog` of ROOT's item files (the project settings of ROOT loaded first), or None when the root has no
    backlog items."""
    import bl_base
    bl_base.load_settings(root)
    bl = bl_base.Backlog(root)
    return bl if bl.items else None


def stalled(root, bl=None):
    """[{item, signals}] of the items that show a signal, or None when the root has no backlog items. BL is the root's
    `backlog` when the caller has read it."""
    import bl_stall
    bl = bl or backlog(root)
    if bl is None:
        return None
    report = bl_stall.collect(bl, run=no_request)
    return [{"item": r["id"], "signals": r["signals"]} for r in report["items"] if r["signals"]]


def read_coord(ctx):
    """{intents: [fields], leases: {session id: seconds left}, claims: [(key, seconds left)]} of the live leases and
    intents in the coord store (`coord.py digest`), the intents newest first, as coord.py prints them (a raw session id,
    never printed by this module); None when the store is not there, is not reachable or does not answer."""
    import mon_coord
    if ctx.url:
        if not ctx.key_file:
            return None
        conn = ["--url", ctx.url, "--key-file", ctx.key_file]
    else:
        store = mon_coord.local_store(ctx)
        if not store or not Path(store).is_file():
            return None
        conn = ["--store", store]
    try:
        p = subprocess.run([sys.executable, str(mon_coord.COORD), *conn, "digest", "--key", "*", "--lines", str(DIGEST_LINES)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=COORD_SECONDS,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    found = {"intents": [], "leases": {}, "claims": []}
    for line in p.stdout.splitlines():
        words = line.split()
        fields = dict(w.split("=", 1) for w in words[1:] if "=" in w)
        if words[:1] == ["intent"]:
            found["intents"].append(fields)
        elif words[:1] == ["claim"] and len(words) > 1:
            left = fields.get("left", "").removesuffix("s")
            left = int(left) if left.isdigit() else 0
            found["claims"].append((words[1], left))
            if words[1].startswith("session/"):
                found["leases"][words[1][len("session/"):]] = left
    return found


def intent_rows(found):
    """[{session, item, operator}] of the live session intents in FOUND (`read_coord`'s answer, None gives None),
    INTENTS_KEPT at most, a session id as its label."""
    if found is None:
        return None
    out = []
    for fields in found["intents"]:
        row = mon_view.session_fields({"session": fields.get("session"), "item": fields.get("item"),
                                       "operator": fields.get("operator")})
        if row["session"] and row not in out:
            out.append(row)
    return out[:INTENTS_KEPT]


def ledger_records(root):
    """{item: record} of the claims ledger in the git dir of the checkout ROOT (`bl_base.claims_ledger`), the records that
    are objects; {} where the ledger is not there or does not read."""
    import bl_base
    ledger = bl_base.claims_ledger(root)[1]
    try:
        records = json.loads(Path(ledger).read_text(encoding="utf-8")) if ledger else {}
    except (OSError, ValueError):
        return {}
    return {i: r for i, r in records.items() if isinstance(r, dict)} if isinstance(records, dict) else {}


def worker_of(rec):
    """(pid, session id) a dispatch record names: `worker_pid` as a positive integer and `worker_session` as a non-empty
    string, else None for each."""
    pid, session = rec.get("worker_pid"), rec.get("worker_session")
    return (pid if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 else None,
            session if isinstance(session, str) and session else None)


def dispatch_runs(root):
    """[{item, pid, session, alive}] of the dispatch runs in the claims ledger of ROOT's git dir: a record with a
    `worker_pid` or a `worker_session` (`bl_dispatch.record_worker`), live workers first, then by item, DISPATCH_KEPT at
    most. `session` is the session's label, never its id, and null before the session ended; `alive` is whether the pid
    still runs, null where the host cannot tell (Windows, where `os.kill` ends a process) or the record has no pid. A ledger
    that is not there or does not read gives []."""
    import bl_procs
    out = []
    for item, rec in ledger_records(root).items():
        pid, session = worker_of(rec)
        if pid is None and session is None:
            continue
        alive = bl_procs.running(pid) if pid is not None and os.name != "nt" else None
        out.append({"item": item, "pid": pid, "session": mon_view.session_label(session), "alive": alive})
    out.sort(key=lambda r: (r["alive"] is not True, r["item"]))
    return out[:DISPATCH_KEPT]


def guid(value):
    """VALUE when it is a session id (a whole GUID), else None."""
    return value if isinstance(value, str) and mon_view.SESSION_ID.fullmatch(value) else None


def iso(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hook_sessions(base):
    """The session ids the coord hook left a state file for in the checkout BASE (`_cache/coord_hook/<id>.json`): the
    sessions that started there and did not end. Only the file names are read, never a file."""
    try:
        names = os.listdir(os.path.join(base, *HOOK_STATE))
    except OSError:
        return set()
    return {n[:-len(".json")] for n in names if n.endswith(".json") and guid(n[:-len(".json")])}


def spool_figures(session):
    """(newest row's time, USD of the usage rows) of the session's own spool file in the query log home of this copy of
    the tools (`<spool>/<session id>.jsonl`): the time is null without a row, the USD null without a usage row. The
    prompts' usage is counted as the querylog panel counts it (`ql_report.usage_counts`, priced by `bl_cost.price_usd`)."""
    import bl_cost
    import ql_base
    import ql_distill
    import ql_report
    path = ql_base.places()[0] / "spool" / f"{session}.jsonl"
    rows = ql_distill.spool_rows(path)[0] if path.is_file() else []
    stamps = [r["ts"] for r in rows if isinstance(r.get("ts"), str)]
    by_prompt = {}
    for r in rows:
        if r.get("surface") == "usage" and isinstance(r.get("prompt_id"), str):
            by_prompt.setdefault(r["prompt_id"], []).append(r)
    models, counted = {}, 0
    for rs in by_prompt.values():
        counts = ql_report.usage_counts(ql_distill.usage_of(rs))
        if counts:
            counted += 1
            ql_report.add_usage_models(models, counts)
    return (max(stamps) if stamps else None), (round(bl_cost.price_usd(models)[0], 4) if counted else None)


def landing_steps(root):
    """{item: the newest `land.step` of its landing in progress} from the ops rows of ROOT; {} when they cannot be read."""
    try:
        import bl_stall
        rows = bl_stall.ops_rows(str(root))
    except Exception:  # noqa: BLE001 - an unreadable log shows no landing
        return {}
    cur = {}
    for r in rows:
        item = r.get("item")
        if r.get("event") == "land.end":
            cur.pop(item, None)
        elif r.get("event") == "land.step" and isinstance(item, str) and isinstance(r.get("step"), str):
            cur[item] = r["step"]
    return cur


def role_of(base, worker, review, runner, planner, observer, listed):
    """The role of a session, the first row that fits (a fixed table, read from the checkout's path and branch, the
    claims ledgers, the item files and the coord leases, never a command line or an environment): `bare twin` (the
    checkout is `bare/agentN`), `benchmark agent` (`multi-<hash>/agentN`), `observer` (nothing names the session and a
    `remediate/` claim is live), `reviewer` (its item is a review story), `worker` (a dispatch record names the process,
    or the checkout is on a `work/<id>` branch), `sprint runner` (the checkout's ledger holds a dispatch record),
    `planner` (its items are all epics or sprints), `interactive` (the checkout is a worktree of the clone) and else
    `unknown`."""
    parts = Path(base).parts
    tail = [parts[-2] if len(parts) > 1 else "", parts[-1] if parts else ""]
    if AGENT_DIR.fullmatch(tail[1]) and tail[0] == BARE_DIR:
        return "bare twin"
    if AGENT_DIR.fullmatch(tail[1]) and MULTI_DIR.fullmatch(tail[0]):
        return "benchmark agent"
    for role, fits in (("observer", observer), ("reviewer", review), ("worker", worker), ("sprint runner", runner),
                       ("planner", planner), ("interactive", listed)):
        if fits:
            return role
    return "unknown"


def step_of(role, items, bl, landing, live_workers):
    """What the session is doing: the landing's step while one of ITEMS is in a landing (LANDING, {item: step}), `review`
    for a reviewer, `waiting` while an item has an open blocking gate or a sprint runner has a worker running, else
    `claim` (an item still `todo`) or `work` (`doing`); null for a session with no such item."""
    import bl_base
    for i in items:
        if i in landing:
            return landing[i]
    if role == "reviewer":
        return "review"
    if any(bl_base.open_gates(bl.items[i]) for i in items if i in bl.items) or (role == "sprint runner" and live_workers):
        return "waiting"
    status = {(bl.items.get(i) or {}).get("status") for i in items}
    return "claim" if "todo" in status else "work" if "doing" in status else None


def intents_of(found, session):
    """The item ids the live intents of SESSION name, in the order of the digest."""
    return list(dict.fromkeys(i for f in (found or {}).get("intents", []) if f.get("session") == session
                              for i in f.get("item", "").split(",") if i))


def intent_session(found, item, taken, own):
    """The session id of the one live intent that names ITEM without the claim topic (a worker's own, not the dispatching
    session's) and is not in TAKEN; of several, the one in OWN (the checkout's hook sessions); else None."""
    ids = []
    for f in (found or {}).get("intents", []):
        if item in f.get("item", "").split(",") and f.get("topic") != CLAIM_TOPIC and guid(f.get("session")) \
                and f["session"] not in taken and f["session"] not in ids:
            ids.append(f["session"])
    ids = ids if len(ids) < 2 else [i for i in ids if i in own]
    return ids[0] if len(ids) == 1 else None


def bind_sessions(claude, placed, by_path, ledgers, found):
    """{pid: [session id or None, [item ids], worker]} for the processes CLAUDE (oldest first). A process is bound to a
    session id in this order: the dispatch record that names its pid (its `worker_session`), the one session that made the
    claims of its checkout's ledger, the one intent of its item that is not a claim's (a worker's), the one hook session of
    its checkout that holds a coord lease; an id binds to one process, the oldest first. `worker` is a dispatch record
    naming the pid or a checkout on a `work/<id>` branch, which then gives the item."""
    dispatch = {}
    for records in ledgers.values():
        for item, rec in records.items():
            if worker_of(rec)[0] is not None:
                dispatch[worker_of(rec)[0]] = (item, rec)
    leases = (found or {}).get("leases", {})
    taken, bound = set(), {}
    for p in claude:  # the ledgers name a session
        found_rec = dispatch.get(p["pid"])
        if found_rec:
            sid, items = guid(worker_of(found_rec[1])[1]), [found_rec[0]]
        else:
            claimed = {i: guid(r.get("session")) for i, r in ledgers[placed[p["pid"]]].items() if guid(r.get("session"))}
            sid = next(iter(claimed.values())) if len(set(claimed.values())) == 1 else None
            items = sorted(claimed) if sid else []
        sid = None if sid in taken else sid
        taken.add(sid)
        bound[p["pid"]] = [sid, items, found_rec is not None]
    taken.discard(None)
    for p in claude:  # the coord store and the hook's state name the rest
        base = placed[p["pid"]]
        m = WORK_BRANCH.fullmatch(by_path.get(base) or "")
        sid, items, worker = bound[p["pid"]]
        worker = worker or bool(m)
        items = items or ([m.group(1)] if m else [])
        own = {s for s in hook_sessions(base) if s in leases and s not in taken}
        if sid is None and worker and items:
            sid = intent_session(found, items[0], taken, own)
        if sid is None and len(own) == 1:
            sid = next(iter(own))
        if sid is not None:
            taken.add(sid)
        bound[p["pid"]] = [sid, items, worker]
    return bound


def session_rows(ctx, procs, placed, by_path, found, bl, names):
    """[{label, role, item, item_title, sprint, sprint_title, step, started, last_activity, spend_usd, pid, checkout}] of
    the Claude Code processes PROCS placed in a checkout (PLACED), oldest first, SESSIONS_KEPT at most; FOUND is
    `read_coord`'s answer (None without one), BL the root's `backlog` (None without items) and NAMES the checkouts as
    shown (`bind_sessions` says how a process gets its session id, a process nothing binds has no label). A dispatch record whose pid
    still runs and that the process table does not list gives a session too, its `started` null."""
    import bl_procs
    claude = [p for p in procs if p["comm"] == CLAUDE and placed.get(p["pid"])]
    ledgers = {b: ledger_records(b) for b in sorted({placed[p["pid"]] for p in claude} | {os.path.realpath(ctx.root)})}
    placed = dict(placed)
    by_branch = {b: path for path, b in by_path.items() if b}
    listed = {p["pid"] for p in procs}
    for records in list(ledgers.values()):  # a dispatched worker the process table does not show (a host that cannot list
        for item, rec in records.items():  # processes, a process it hides): its pid still runs, its worktree is on its branch
            pid, base = worker_of(rec)[0], by_branch.get(f"work/{item}")
            if pid and base and pid not in listed and os.name != "nt" and bl_procs.running(pid):
                claude.append({"pid": pid, "start": None, "comm": CLAUDE})
                placed[pid] = base
                ledgers.setdefault(base, ledger_records(base))
    claude.sort(key=lambda p: (p["start"] is None, p["start"] or 0, p["pid"]))
    if not claude:
        return []
    bound = bind_sessions(claude, placed, by_path, ledgers, found)
    landing = landing_steps(ctx.root) if bl is not None else {}
    remediating = any(key.startswith(REMEDIATE) for key, _ in (found or {}).get("claims", []))
    items_of = bl.items if bl is not None else {}

    def title(item):
        return None if item is None or bl is None or item in bl.withheld else (items_of.get(item) or {}).get("title")

    out = []
    for p in claude:
        base = placed[p["pid"]]
        sid, items, worker = bound[p["pid"]]
        records = ledgers[base]
        dispatched = [i for i, r in records.items() if any(worker_of(r))]
        runner = not worker and bool(dispatched)
        if not worker:  # a session's claims, else its intents'; the ones still open
            items = [i for i in items or intents_of(found, sid) if (items_of.get(i) or {}).get("status") in ("todo", "doing")]
        known = [items_of[i] for i in items if i in items_of]
        sprints = {it.get("sprint") for it in known}
        live_workers = any(bl_procs.running(w) for w in (worker_of(r)[0] for r in records.values()) if w is not None)
        role = role_of(base, worker, any(it.get("review") for it in known), runner,
                       bool(known) and all(it.get("kind") in PLAN_KINDS for it in known),
                       sid is None and not hook_sessions(base) and remediating, base in by_path)
        item = items[0] if len(items) == 1 else None
        sprint = sprints.pop() if len(sprints) == 1 else None
        stamp, spend = spool_figures(sid) if sid is not None else (None, None)
        step = step_of(role, items + [i for i in dispatched if runner and i not in items], bl, landing, live_workers) \
            if bl is not None else None
        out.append({"label": mon_view.session_label(sid) if sid else None, "role": role, "item": item,
                    "item_title": title(item), "sprint": sprint, "sprint_title": title(sprint), "step": step,
                    "started": iso(p["start"]) if p["start"] is not None else None, "last_activity": stamp, "spend_usd": spend, "pid": p["pid"],
                    "checkout": names.get(base, ".")})
    return out[:SESSIONS_KEPT]


def collect(ctx):
    import bl_procs
    import kbwho
    procs, _, why = bl_procs.snapshot(str(ctx.root))
    now = time.time()
    rows, by_path = branches(ctx.root)
    bases = bl_procs.checkouts(str(ctx.root)) if procs is not None else []
    names = display_names(ctx.root, bases)
    placed = checkout_paths(procs or [], bases)
    out = []
    for p in procs or []:
        base = placed.get(p["pid"])
        session, item = session_of(base, by_path) if p["comm"] == CLAUDE else (None, None)
        _, _, rest = p["where"].partition("/")
        shown = names.get(base, p["where"].split("/", 1)[0])
        out.append({"pid": p["pid"], "age_s": max(0, int(now - p["start"])), "class": p["kind"],
                    "checkout": shown + ("/" + rest if rest else ""), "session": session, "item": item})
    me = kbwho.operator()
    data = {"procs": out, "worktrees": rows, "operator": {"id": me.get("id"), "role": me.get("role")}}
    if procs is None:
        data["procs_unreadable"] = why
    found = read_coord(ctx)
    intents = intent_rows(found)
    if intents is not None:
        data["intents"] = intents
    data["dispatch"] = dispatch_runs(ctx.root)
    bl = backlog(ctx.root)
    data["sessions"] = session_rows(ctx, procs or [], placed, by_path, found, bl, names)
    items = stalled(ctx.root, bl)
    if items is not None:
        data["stalled"] = items
    return data


def alerts(data):
    """The alerts of the panel's data: one `orphan` alert (id `sessions.orphan`) while a process of class `orphan` is listed;
    its message counts them and names the oldest one's pid."""
    orphans = [p for p in data.get("procs") or [] if isinstance(p, dict) and p.get("class") == "orphan"]
    if not orphans:
        return []
    oldest = max(orphans, key=lambda p: p.get("age_s") or 0)
    return [{"kind": "orphan", "id": "sessions.orphan", "panel": "sessions", "since": "",
             "message": f"{len(orphans)} orphan process{'' if len(orphans) == 1 else 'es'}, the oldest pid {oldest.get('pid')} "
                        f"for {age_text(oldest.get('age_s') or 0)}"}]


def age_text(seconds):
    import bl_procs
    return bl_procs.age_text(seconds)


def cut_left(text, n):
    return text if len(text) <= n else "…/" + text[-max(1, n - 2):]


def table(procs, limit):
    """The processes as rows [(flag, text)]: a header and a row each, no wider than `limit` characters; the checkout is cut
    from the left first."""
    head = ("pid", "age", "class", "session", "item", "checkout")
    body = [(str(p["pid"]), age_text(p["age_s"]), p["class"], p.get("session") or "-", p.get("item") or "-",
             p["checkout"]) for p in procs]
    widths = [max(len(h), *(len(r[i]) for r in body)) for i, h in enumerate(head)]
    widths[-1] = max(MIN_CHECKOUT, widths[-1] - max(0, sum(widths) + 2 * (len(head) - 1) - limit))

    def row(cells):
        cells = list(cells)
        cells[-1] = cut_left(cells[-1], widths[-1])
        return "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()

    return [(False, row(head))] + [(p["class"] == "orphan", row(r)) for p, r in zip(procs, body)]


def joined(label, parts, width):
    """`label` padded to LABEL, then PARTS joined by ` · `, wrapped at a part and continued at column LABEL."""
    rows, cur = [], ""
    for part in parts:
        if cur and LABEL + len(cur) + 3 + len(part) > width:
            rows.append(cur)
            cur = part
        else:
            cur = cur + " · " + part if cur else part
    rows.append(cur)
    return [(label if i == 0 else "").ljust(LABEL) + r for i, r in enumerate(rows)]


def session_lines(sessions, width):
    """The sessions as rows, SESSIONS_SHOWN at most then `+N more`: `label  role  item  step  title`, the title (the item's,
    else the sprint's) cut to what the width leaves, then the spend where it is known."""
    sessions = [s for s in sessions if isinstance(s, dict)]
    if not sessions:
        return []
    cells = [(s.get("label") or "-", s.get("role") or "unknown", s.get("item") or s.get("sprint") or "-", s.get("step") or "-",
              s.get("item_title") or s.get("sprint_title") or "", s.get("spend_usd")) for s in sessions[:SESSIONS_SHOWN]]
    widths = [max(len(c[i]) for c in cells) for i in range(4)]
    rows = []
    for n, (label, role, item, step, title, spend) in enumerate(cells):
        head = "  ".join(c.ljust(w) for c, w in zip((label, role, item, step), widths))
        tail = f"  ${spend:.2f}" if isinstance(spend, (int, float)) else ""
        room = min(TITLE_CHARS, width - 2 - LABEL - len(head) - len(tail) - 2)
        text = head + ("  " + (title if len(title) <= room else title[:room - 1] + "…") if title and room > 1 else "")
        rows.append(("sessions" if n == 0 else "").ljust(LABEL) + text.rstrip() + tail)
    if len(sessions) > len(cells):
        rows.append(" " * LABEL + f"+{len(sessions) - len(cells)} more")
    return rows


def lines(data, width=80):
    """The body rows: the processes table (an orphan's row starts `! `, orphans first, PROCS_SHOWN at most), the worktrees
    with their branches, the dispatch runs (item, pid, session, `alive` or `ended`, live ones first, DISPATCH_SHOWN at most) and
    the stalled items, each a `! ` row of its id and signals; first the clone's operator and the live session intents
    (session, item, operator)."""
    procs = sorted(data.get("procs", []), key=lambda p: (p["class"] != "orphan", p["pid"]))
    rows = []
    me = data.get("operator") or {}
    rows.append("operator".ljust(LABEL) + f"{me.get('id') or 'none'} ({me.get('role') or '-'})")
    intents = data.get("intents") or []
    if intents:
        shown_intents = intents[:INTENTS_SHOWN]
        parts = [f"{i['session']}  {i.get('item') or '-'}  {i.get('operator') or '-'}" for i in shown_intents]
        if len(intents) > len(shown_intents):
            parts.append(f"+{len(intents) - len(shown_intents)} more")
        rows += joined("intents", parts, width - 2)
    rows += session_lines(data.get("sessions") or [], width)
    if procs:
        shown = procs[:PROCS_SHOWN]
        rows += [("! " if flag else "") + text for flag, text in table(shown, width - 2)]
        if len(procs) > len(shown):
            rows.append(f"+{len(procs) - len(shown)} more")
    elif data.get("procs_unreadable"):
        rows.append("processes unreadable: " + str(data["procs_unreadable"]))
    else:
        rows.append("processes none")
    trees = sorted(data.get("worktrees", []), key=lambda w: not (w.get("branch") or "").startswith("work/"))
    parts = [f"{w['path']}  {w.get('branch') or '(detached)'}" for w in trees[:TREES_SHOWN]]
    if len(trees) > TREES_SHOWN:
        parts.append(f"+{len(trees) - TREES_SHOWN} more")
    rows += joined("worktrees", parts, width - 2) if trees else ["worktrees none"]
    runs = [r for r in data.get("dispatch") or [] if isinstance(r, dict)]
    if runs:
        shown_runs = runs[:DISPATCH_SHOWN]
        parts = [f"{r.get('item')}  {r.get('pid') or '-'}  {r.get('session') or '-'}  "
                 f"{'alive' if r.get('alive') else 'ended' if r.get('alive') is False else 'unknown'}" for r in shown_runs]
        if len(runs) > len(shown_runs):
            parts.append(f"+{len(runs) - len(shown_runs)} more")
        rows += joined("dispatch", parts, width - 2)
    if "stalled" in data:
        items = data["stalled"]
        for i, s in enumerate(items):
            rows.append("! " + ("stalled".ljust(LABEL - 2) if i == 0 else " " * (LABEL - 2)) + f"{s['item']}  "
                        + ", ".join(s["signals"]))
        if not items:
            rows.append("stalled".ljust(LABEL) + "none")
    return rows
