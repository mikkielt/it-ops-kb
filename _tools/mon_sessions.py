"""kbmon's sessions panel (kb/_self/monitoring.md): the processes working in a checkout of the clone, the clone's worktrees
with their branches and the stalled items with their signals.

The processes are `backlog.py procs`' inventory (`bl_procs.snapshot`): pid, age and class (`orphan`, `hook`, `detached` or `foreign`; an orphan whose session's transcript was written under `bl_procs.FRESH_S` seconds ago is `detached`),
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
usage rows of the session's own spool file, null without one) and `silent_s` (the seconds since the newest write to the
session's transcript or its subagents' transcripts, `mon_coord.transcript_age`; with none found, since the newer of its newest spool row
and its process's start, `silence`; null only where none is known) and
`agent_state` (the state the project's `agent_states` command gives the session's pid, else its session id: `working`,
`blocked`, `idle` or `done`; null for neither, and the panel's `agent_states_unread` says why a command gave none) and, only while the session waits on the person, `blocked`:
{`on` (`permission` or `question`), `since`, `age_s`}, from the session's newest `blocked` event of the coord store (the coord
hook posts it at a permission request or a notification that waits on the person and clears it at the session's next tool
event; a session that is only silent has no such key). `overlaps` lists each pair of live sessions whose
intents' items or touches meet, with the shared `files` and the `strategy` (`undecided`, else the one a `coordinate` event
between their items announced), and `needs_you_after_min` is the setting `mon_needs` ages an undecided one against (`overlap_rows`,
`after_minutes`; both left out with `intents`, and left out with `overlaps_unread`, the reason, where a coord store is there
but its digest or events do not read, so no age reads 0 for want of events). A session's id is read from a dispatch record of a claims
ledger (the pid, then the session), the claim records of its checkout's ledger, the coord intents and leases and the
hook's per-session state file names under its checkout, never from a command line or an environment; a raw id leaves
this module as its label only, `live_sessions` apart (a return value for another tool in this process). A host that cannot list working
directories (no `/proc` and no `lsof`) gives no processes and `procs_unreadable`, the reason, so the operator and the
intents still show. Windows exposes no working directory, so the processes are `bl_procs.windows_snapshot`'s: those whose
command line names a checkout of the clone (matched and dropped, never kept), and `procs_limit` says what Windows cannot
show; a PowerShell that does not answer gives `procs_unreadable`. A root with no backlog items has no `stalled` key. `session_line` turns one `sessions` entry into the one line the view and
`mon_status` print. `waits` lists, for each process that holds `wait/<pid>/<item>` keys (a blocking `coord.py wait --kind
progress --item`, `list --prefix wait/`), the session it runs under (the label of the `sessions` entry whose process is its
ancestor, else null) and the items it waits on as {id, title}, a process that no longer runs left out; it is left out with
`intents`. `drift` is `backlog.py runs`' answer for the active sprints' items and every item with a run key: `count`, the `oldest`
item id (by its newest progress event) and `items`, each {item, title, state (the run state), git (the state git shows), why,
age_s}; it is left out where the store is a url, `runs` cannot read coord or the root has no backlog items. `live_sessions(root)` gives a
tool in this process one row for each live session with the raw `session` id, the absolute `checkout` and the `pid` besides
the `label`, `role`, `item` and `sprint` (the `sessions` binding, read light: at most two git processes, no stall
signal, ops row or spool); the panel never holds the first two. `alerts` raises
`sessions.orphan` and, while `drift` counts one, `runs.drift` (kind `drift`). Imports `mon_base` and `mon_view`; `bl_procs`,
`bl_stall`, `bl_base`, `bl_runs`, `bl_items`, `bl_cost`, `ql_base`, `ql_distill` and `ql_report` where it reads them.
"""
import contextlib
import datetime
import json
import os
import re
import subprocess
import sys
import threading
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
OVERLAPS_KEPT = 20  # overlaps in the data
OVERLAPS_SHOWN = 4  # overlaps in the text view
UNDECIDED = "undecided"  # the strategy of an overlap no coordinate event decided
TITLE_CHARS = 40  # characters of an item title in a session line
SPRINT_CHARS = 20  # characters of a sprint's title in a session line
LINE_CHARS = 120  # characters of a session line at most
SILENT_SHOWN_S = 600  # seconds of silence from which a session line names it (`silent 15m`)
CLAIM_TOPIC = "backlog-claim"  # the topic of the intent a `backlog.py claim` posts (the dispatching session's, not the worker's)
REMEDIATE = "remediate/"  # the coord key `kbask.py remediate` claims while its observer session runs
HOOK_STATE = ("_cache", "coord_hook")  # under a checkout: the hook's `<session id>.json` of each session it announced
BARE_DIR = "bare"  # the sandbox directory of a benchmark's bare twins (`bench_multi.BARE`): `<dir>/bare/agentN`
AGENT_DIR = re.compile(r"agent\d+")
MULTI_DIR = re.compile(r"multi-[0-9a-f]{8}")  # `bench_multi.clone_path`: `<scratch>/multi-<hash>/agentN`
PLAN_KINDS = ("epic", "sprint")  # the items a planner works on
WAIT_KEYS = "wait/"  # the keys a blocking `coord.py wait --kind progress --item` holds: wait/<pid>/<item id>
WAITS_KEPT = 20  # waiting sessions in the data
WAITS_SHOWN = 4  # waiting sessions in the text view
DRIFT_KEPT = 20  # drifted run states in the data
DRIFT_SHOWN = 3  # drifted run states in the text view
ANCESTORS = 64  # process generations climbed from a wait to the Claude Code process that ran it
PLACEMENT_LOCK = threading.Lock()  # one placement at a time shares a single worktree listing
STORE_LOCK = threading.Lock()  # one panel run at a time points the environment's coord store at the clone's
WINDOWS_LIMIT = ("Windows shows no working directory: a process is listed when its command line names a checkout of "
                 "the clone, so one that names none, an orphan told by working directory, is not shown")
RAW_KEYS = ("session", "base", "quiet")  # the keys of a `session_entries` entry that the panel's data never holds
AGENT_STATES = ("working", "blocked", "idle", "done")  # the states an `agent_states` line may give
AGENT_STATES_SECONDS = 5  # the longest the `agent_states` command may take
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
        if p.get("base"):  # a Windows process, placed by the checkout path in its command line
            out[p["pid"]] = p["base"]
            continue
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


EVENT_KINDS = ("intent", "coordinate", "progress", "blocked")  # the event kinds the panel reads, one `coord.py wait --kind` each


def read_events(conn):
    """({session id: [(time, items, touch paths, claim)] of its intent events, oldest first, `claim` whether the intent is a
    `backlog-claim` one}, [(item, other, strategy, session id, time)] of the `coordinate` events, newest first,
    {item: time of its newest `progress` event}, {session id: (what it waits on, time)} of the sessions whose newest `blocked`
    event says waiting) from one `coord.py wait --kind K` of each of EVENT_KINDS over the connection
    arguments CONN; None where any of them cannot be read."""
    import mon_coord
    events = []
    for kind in EVENT_KINDS:
        try:
            p = subprocess.run([sys.executable, str(mon_coord.COORD), *conn, "wait", "--since", "0", "--timeout", "0",
                                "--kind", kind], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=COORD_SECONDS, stdin=subprocess.DEVNULL)
            got = json.loads(p.stdout)["events"] if p.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(got, list):
            return None
        events += got
    first, chosen, moved, blocked = {}, [], {}, {}
    for e in events:
        fields = e.get("fields") if isinstance(e, dict) and isinstance(e.get("fields"), dict) else {}
        if e.get("kind") == "intent" and isinstance(fields.get("session"), str) and isinstance(e.get("at"), (int, float)):
            first.setdefault(fields["session"], []).append((e["at"], split_list(fields.get("item")),
                                                            split_list(fields.get("touch")), fields.get("topic") == CLAIM_TOPIC))
        elif e.get("kind") == "coordinate" and fields.get("item") and fields.get("other") and fields.get("strategy"):
            chosen.insert(0, (fields["item"], fields["other"], fields["strategy"], fields.get("session"), e.get("at")))
        elif e.get("kind") == "progress" and isinstance(fields.get("item"), str) and isinstance(e.get("at"), (int, float)):
            moved[fields["item"]] = e["at"]
        elif e.get("kind") == "blocked" and isinstance(fields.get("session"), str) and isinstance(e.get("at"), (int, float)):
            if fields.get("state") == "waiting":
                blocked[fields["session"]] = (fields.get("on") or "permission", e["at"])
            else:
                blocked.pop(fields["session"], None)
    return first, chosen, moved, blocked


def split_list(value):
    """The words of VALUE, a comma-separated string as an intent field holds it; empty for anything else."""
    return [w for w in value.split(",") if w] if isinstance(value, str) else []


def coord_conn(ctx):
    """coord.py's connection arguments for the url or the local store of CTX, None when the store is not there or the url
    has no key file."""
    import mon_coord
    if ctx.url:
        return ["--url", ctx.url, "--key-file", ctx.key_file] if ctx.key_file else None
    store = mon_coord.local_store(ctx)
    return ["--store", store] if store and Path(store).is_file() else None


def coord_list(ctx, prefix):
    """The rows `coord.py list --prefix PREFIX` prints for the coord store of CTX; None when it does not answer."""
    import mon_coord
    conn = coord_conn(ctx)
    if conn is None:
        return None
    try:
        p = subprocess.run([sys.executable, str(mon_coord.COORD), *conn, "list", "--prefix", prefix], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=COORD_SECONDS, stdin=subprocess.DEVNULL)
        rows = json.loads(p.stdout) if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


def read_coord(ctx, events=True):
    """{intents: [fields], leases: {session id: seconds left}, claims: [(key, seconds left)], dispatched: {items with a
    dispatch record in the claims ledger}, intent_at, coordinate, moved, blocked} of the live leases and intents in the coord store (`coord.py digest`), the intents newest first, as coord.py
    prints them (a raw session id, never printed by this module); `intent_at`, `coordinate`, `moved` and `blocked` are `read_events`'
    answer, empty and `events_unread` true where it is None; with EVENTS false they are not read (four processes fewer) and
    are empty without `events_unread`. None when the store is not there, is not reachable or does not answer."""
    import mon_coord
    conn = coord_conn(ctx)
    if conn is None:
        return None
    try:
        p = subprocess.run([sys.executable, str(mon_coord.COORD), *conn, "digest", "--key", "*", "--lines", str(DIGEST_LINES)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=COORD_SECONDS,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    found = {"intents": [], "leases": {}, "claims": [], "dispatched": {i for i, r in ledger_records(ctx.root).items() if any(worker_of(r))},
             "intent_at": {}, "coordinate": [], "moved": {}, "blocked": {}}
    read = read_events(conn) if events else (found["intent_at"], found["coordinate"], found["moved"], found["blocked"])
    if read is None:
        found["events_unread"] = True
    else:
        found["intent_at"], found["coordinate"], found["moved"], found["blocked"] = read
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


def run_states(ctx):
    """{item id: run state} of the `run/` keys of the coord store of CTX; None when the store does not answer."""
    rows = coord_list(ctx, "run/")
    return None if rows is None else {r["key"][len("run/"):]: r["value"] for r in rows if r.get("value")}


def ancestor_session(pid, table, by_pid):
    """The `sessions` entry whose process is an ancestor of PID in the process TABLE ({pid: (ppid, start, comm)}), else None."""
    for _ in range(ANCESTORS):
        if pid in by_pid:
            return by_pid[pid]
        entry = table.get(pid)
        if not entry or not entry[0] or entry[0] == pid:
            return None
        pid = entry[0]
    return None


def wait_rows(ctx, sessions, bl):
    """[{session, pid, items: [{id, title}]}] of the processes that hold `wait/<pid>/<item>` keys in the coord store (the
    waits of `coord.py wait --kind progress --item`), WAITS_KEPT at most; `session` the label of the entry of SESSIONS whose
    process runs the wait (null when none does or the host cannot tell). A pid that no longer runs, where the host can tell,
    is left out. None where the store does not answer."""
    import bl_procs
    rows = coord_list(ctx, WAIT_KEYS)
    if rows is None:
        return None
    waits = {}
    for r in rows:
        pid, _, item = str(r.get("key"))[len(WAIT_KEYS):].partition("/")
        if r.get("holder") is None or not pid.isdigit() or not item:
            continue
        waits.setdefault(int(pid), []).append(item)
    if os.name != "nt":
        waits = {pid: items for pid, items in waits.items() if bl_procs.running(pid)}
    table = bl_procs.process_table() if waits and os.name != "nt" else None
    by_pid = {s["pid"]: s for s in sessions if s.get("pid")}
    titles = {}
    for item in {i for items in waits.values() for i in items}:
        shown = bl is not None and item in bl.items and item not in bl.withheld
        titles[item] = bl.items[item].get("title") if shown else None
    out = []
    for pid, items in sorted(waits.items()):
        owner = ancestor_session(pid, table, by_pid) if table else None
        out.append({"session": owner.get("label") if owner else None, "pid": pid,
                    "items": [{"id": i, "title": titles[i]} for i in sorted(items)]})
    return out[:WAITS_KEPT]


@contextlib.contextmanager
def coord_store(ctx):
    """The environment's coord store (`KB_COORD_STORE`, which the backlog tools' coord calls read) set to the store of CTX for
    the length of the block, one block at a time."""
    import mon_coord
    with STORE_LOCK:
        before = os.environ.get("KB_COORD_STORE")
        os.environ["KB_COORD_STORE"] = mon_coord.local_store(ctx) or ""
        try:
            yield
        finally:
            if before is None:
                os.environ.pop("KB_COORD_STORE", None)
            else:
                os.environ["KB_COORD_STORE"] = before


def tree_ledger(root):
    """(top, claims ledger) of the working tree ROOT as `bl_base.claims_ledger` gives them, read from the tree's `.git`
    entry (a directory, or a file that names the git dir) instead of a git process; `claims_ledger` itself where the entry
    says nothing."""
    import bl_base
    top = Path(root)
    entry = top / ".git"
    try:
        if entry.is_dir():
            return str(top), entry / bl_base.CLAIMS_LEDGER
        line = entry.read_text(encoding="utf-8").splitlines()[0] if entry.is_file() else ""
    except (OSError, IndexError, UnicodeDecodeError):
        line = ""
    if line.startswith("gitdir:"):
        return str(top), (top / line[len("gitdir:"):].strip()) / bl_base.CLAIMS_LEDGER
    return bl_base.claims_ledger(root)


@contextlib.contextmanager
def bounded_git():
    """`bl_runs` and `bl_items` reading each working tree's claims ledger from its `.git` entry and leaving out the open
    gates of each work branch (one git process each, which the drift read never uses), so the run-state read starts the
    git processes of the worktree list and nothing that grows with the run keys or the worktrees. Held under STORE_LOCK by
    the caller, one block at a time."""
    import bl_items
    import bl_runs
    saved = (bl_runs.claims_ledger, bl_items.claims_ledger, bl_runs.branch_gates)
    bl_runs.claims_ledger = bl_items.claims_ledger = tree_ledger
    bl_runs.branch_gates = lambda root, iid: None
    try:
        yield
    finally:
        bl_runs.claims_ledger, bl_items.claims_ledger, bl_runs.branch_gates = saved


def drift_data(ctx, bl, found, now):
    """{count, oldest, items: [{item, title, state, git, why, age_s}]} of the run states `backlog.py runs` finds drifted
    from git (`bl_runs.collect` over the default scope), the oldest first (by the item's newest progress event in FOUND;
    one that has none after the others), DRIFT_KEPT at most; `oldest` is the first item's id, null without drift.
    None where the store is a url or not there, the root has no backlog items or coord cannot be read."""
    import bl_base
    import bl_runs
    if bl is None or ctx.url or coord_conn(ctx) is None:
        return None
    try:
        with coord_store(ctx), bounded_git():
            states = bl_runs.run_states()
            rows = bl_runs.collect(bl, states, bl_runs.scope_of(bl, states, None))
    except bl_base.Refused:
        return None
    moved = (found or {}).get("moved", {})
    drifted = sorted((r for r in rows if r["drift"]), key=lambda r: (r["id"] not in moved, moved.get(r["id"], 0), r["id"]))
    items = [{"item": r["id"], "title": None if r["id"] in bl.withheld else (bl.items.get(r["id"]) or {}).get("title"),
              "state": r["state"], "git": r["drift"][0], "why": r["drift"][1],
              "age_s": max(0, int(now - moved[r["id"]])) if r["id"] in moved else None} for r in drifted]
    return {"count": len(items), "oldest": items[0]["item"] if items else None, "items": items[:DRIFT_KEPT]}


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


def after_minutes(root):
    """`announce.needs_you_after_min` for the clone at ROOT (kbsettings, the workspace file and the kb root's), the default
    where the settings do not read."""
    import kbsettings
    import mon_coord
    try:
        return kbsettings.effective(root, mon_coord.kb_root_of(root))["coordination"]["announce"]["needs_you_after_min"]
    except (kbsettings.SettingsError, KeyError, OSError):
        return kbsettings.DEFAULTS["announce"]["needs_you_after_min"]


def agent_states(root):
    """(({pid: state}, {session id: state}), why) from the `agent_states` setting of the project at ROOT: the command's
    stdout is JSON lines, each an object with a `pid` (a positive integer) or a `session` (a string) and a `state`, one of
    AGENT_STATES; a line that is none of that is skipped, a later line for the same pid or session wins. The command runs in
    ROOT with stdin closed and at most AGENT_STATES_SECONDS. With no setting, the maps are empty and WHY is None; a command
    that does not start, ends non-zero or takes too long gives empty maps and WHY, the reason."""
    import bl_base
    argv = bl_base.read_settings(root)[0]["agent_states"]
    pids, sessions = {}, {}
    if not argv:
        return (pids, sessions), None
    try:
        p = subprocess.run(argv, cwd=str(root), stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=AGENT_STATES_SECONDS)
    except (OSError, subprocess.SubprocessError) as e:
        return (pids, sessions), f"the agent_states command did not run: {type(e).__name__}"
    if p.returncode:
        return (pids, sessions), f"the agent_states command exited {p.returncode}"
    for line in p.stdout.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("state") not in AGENT_STATES:
            continue
        pid, session = row.get("pid"), row.get("session")
        if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
            pids[pid] = row["state"]
        elif isinstance(session, str) and session:
            sessions[session] = row["state"]
    return (pids, sessions), None


def dispatching(found, session, items):
    """Whether a `backlog-claim` intent of SESSION on ITEMS is a dispatching session's: one of the items has a dispatch
    record in the claims ledger, or an intent of another session without the claim topic (a worker's own) names it. An
    interactive session's claim is neither, and stays an intent of that session."""
    items = set(items)
    if items & found.get("dispatched", set()):
        return True
    return any(f.get("topic") != CLAIM_TOPIC and f.get("session") != session and items & set(split_list(f.get("item")))
               for f in found["intents"])


def merged_intents(found):
    """{session id: {items, touch, operator}} of the live intents in FOUND that a session announced for itself (the claim
    topic's intent of a session that dispatched a worker on its item is left out), each session's intents merged."""
    out = {}
    for f in found["intents"]:
        who = f.get("session")
        if not who or (f.get("topic") == CLAIM_TOPIC and dispatching(found, who, split_list(f.get("item")))):
            continue
        s = out.setdefault(who, {"items": [], "touch": [], "operator": None})
        s["items"] += [i for i in f.get("item", "").split(",") if i and i not in s["items"]]
        s["touch"] += [t for t in f.get("touch", "").split(",") if t and t not in s["touch"]]
        s["operator"] = s["operator"] or f.get("operator")
    return out


def met_events(found, session):
    """The intent events of SESSION in FOUND (`read_events`' list), without the claim ones of a dispatching session, as
    (time, items, touch paths)."""
    return [(t, i, p) for t, i, p, claim in found.get("intent_at", {}).get(session, [])
            if not (claim and dispatching(found, session, i))]


def live_part(events, live):
    """EVENTS (`met_events`' list) cut to what the LIVE intents ({items, touch}, one session's `merged_intents` entry)
    still name: each event keeps its items that LIVE names and its touch paths that meet a live one, and an event with
    neither is dropped."""
    import coord
    out = []
    for t, items, paths in events:
        kept_items = [i for i in items if i in live["items"]]
        kept_paths = [p for p in paths if any(coord.overlaps(p, q) for q in live["touch"])]
        if kept_items or kept_paths:
            out.append((t, kept_items, kept_paths))
    return out


def meeting_time(ea, eb):
    """The time of the oldest moment two sessions met, from the intent events EA and EB of each (`live_part`'s lists): the
    smallest, over the pairs of an intent of each whose items or touch paths meet, of the newer intent of the pair; None
    where no pair meets."""
    import coord
    met = [max(ta, tb) for ta, ia, pa in ea for tb, ib, pb in eb
           if set(ia) & set(ib) or any(coord.overlaps(p, q) for p in pa for q in pb)]
    return min(met) if met else None


def overlap_rows(found, now=None):
    """[{a, b, files, strategy, age_s}] of the pairs of live sessions in FOUND (`read_coord`'s answer; None gives None, as
    does one whose events were not read: every age would read 0)
    whose intents' items or touches meet, OVERLAPS_KEPT at most, longest first. `a` and `b` are {session (the label),
    operator, item} (the session's first item); `files` the touch paths of either that meet a path of the other; `strategy`
    `undecided`, else the one the newest `coordinate` event between an item of each announced, posted by one of the two
    sessions at or after the moment they met (an older event, or one of a session outside the pair, decides nothing); `age_s` the seconds since
    the oldest moment an intent of each met an intent of the other on the items and paths the two sessions' live intents
    still name (the newer of the two intents; an older pair on other items or files counts nothing), the later of the two
    sessions' first intent where no event pair meets."""
    if found is None or found.get("events_unread"):
        return None
    import coord
    now = time.time() if now is None else now
    sessions = merged_intents(found)
    out = []
    ids = sorted(sessions, key=mon_view.session_label)
    for n, ida in enumerate(ids):
        for idb in ids[n + 1:]:
            sa, sb = sessions[ida], sessions[idb]
            files = sorted({t for t in sa["touch"] if any(coord.overlaps(t, u) for u in sb["touch"])}
                           | {u for u in sb["touch"] if any(coord.overlaps(t, u) for t in sa["touch"])})
            if not files and not set(sa["items"]) & set(sb["items"]):
                continue
            ea, eb = met_events(found, ida), met_events(found, idb)
            since = meeting_time(live_part(ea, sa), live_part(eb, sb))
            if since is None:
                since = max((ea or [(now,)])[0][0], (eb or [(now,)])[0][0])
            strategy = next((s for i, o, s, who, t in found.get("coordinate", [])
                             if who in (ida, idb) and isinstance(t, (int, float)) and t >= since
                             and ((i in sa["items"] and o in sb["items"]) or (i in sb["items"] and o in sa["items"]))), UNDECIDED)
            side = [mon_view.session_fields({"session": i, "operator": s["operator"]}) | {"item": (s["items"] or [None])[0]}
                    for i, s in ((ida, sa), (idb, sb))]
            out.append({"a": side[0], "b": side[1], "files": files, "strategy": strategy, "age_s": max(0, int(now - since))})
    out.sort(key=lambda o: (-o["age_s"], o["a"]["session"], o["b"]["session"]))
    return out[:OVERLAPS_KEPT]


def overlap_text(o):
    """One overlap as words: `s-1a2b3c ST-… with s-4d5e6f ST-… sharing PATHS, undecided`."""
    files = ", ".join(o["files"][:3]) + (f" and {len(o['files']) - 3} more" if len(o["files"]) > 3 else "")
    return (f"{o['a']['session']} {o['a'].get('item') or '-'} with {o['b']['session']} {o['b'].get('item') or '-'}"
            + (f" sharing {files}" if files else " on one item") + f", {o['strategy']}")


def ledger_records(root):
    """{item: record} of the claims ledger in the git dir of the checkout ROOT (`tree_ledger`, no git process), the records
    that are objects; {} where the ledger is not there or does not read."""
    ledger = tree_ledger(root)[1]
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
    most. `session` is the session's label, never its id, and null while the pid runs (a re-dispatched worker's record still holds the last run's session); `alive` is whether the pid
    still runs, null where the host cannot tell (Windows, where `os.kill` ends a process) or the record has no pid. A ledger
    that is not there or does not read gives []."""
    import bl_procs
    out = []
    for item, rec in ledger_records(root).items():
        pid, session = worker_of(rec)
        if pid is None and session is None:
            continue
        alive = bl_procs.running(pid) if pid is not None and os.name != "nt" else None
        out.append({"item": item, "pid": pid, "session": None if alive else mon_view.session_label(session), "alive": alive})
    out.sort(key=lambda r: (r["alive"] is not True, r["item"]))
    return out[:DISPATCH_KEPT]


def guid(value):
    """VALUE when it is a session id (a whole GUID), else None."""
    return value if isinstance(value, str) and mon_view.SESSION_ID.fullmatch(value) else None


def iso(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hook_sessions(base):
    """The session ids the coord hook left a state file for in the checkout BASE: the sessions that started there and did
    not end. The hook keeps the file in `_cache/coord_hook/<id>.json` of the clone that holds its script, else (a project
    the plugin serves) in the `hook` directory beside the project's store (`kb-coord/hook` of its common git directory,
    found without running git); both are read. Only the file names are read, never a file."""
    import coord
    git_dir = coord.git_dir_of(base)
    found = set()
    for where in (os.path.join(base, *HOOK_STATE), os.path.join(git_dir, "kb-coord", "hook") if git_dir else None):
        try:
            names = os.listdir(where) if where else []
        except OSError:
            continue
        found |= {n[:-len(".json")] for n in names if n.endswith(".json") and guid(n[:-len(".json")])}
    return found


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


def transcript_quiet(session, now):
    """The seconds since the newest write to the transcript of SESSION (a session id or None) or its subagents'; None with no id
    or no transcript."""
    import mon_coord
    return mon_coord.transcript_age([session], now) if session is not None else None


def silence(quiet, last_activity, started, now):
    """The seconds a live session has gone quiet: QUIET, the seconds since the newest write to its transcript or its subagents'
    (`transcript_quiet`); with none found (None) since the newer of its newest spool row (LAST_ACTIVITY, an ISO time or None)
    and its process's start (STARTED, epoch seconds or None); None only where none of them is known."""
    if quiet is not None:
        return quiet
    known = [t for t in (epoch(last_activity) if last_activity else None, started) if t is not None]
    return max(0, int(now - max(known))) if known else None


def landing_steps(root):
    """{item: the newest `land.step` of its landing in progress} from the ops rows of ROOT; {} when they cannot be read. A
    landing whose `land.end` row has exit 0 is over: a `land.step` row after it (a step's row written late) opens no landing,
    while a step after a `land.end` with another exit is a retry's and does."""
    try:
        import bl_stall
        rows = bl_stall.ops_rows(str(root))
    except Exception:  # noqa: BLE001 - an unreadable log shows no landing
        return {}
    cur, ended = {}, set()
    for r in rows:
        item = r.get("item")
        if r.get("event") == "land.end":
            cur.pop(item, None)
            if r.get("exit") == 0:
                ended.add(item)
        elif r.get("event") == "land.step" and isinstance(item, str) and isinstance(r.get("step"), str) and item not in ended:
            cur[item] = r["step"]
    return cur


def role_of(base, worker, review, runner, planner, observer, listed):
    """The role of a session, the first row that fits (a fixed table, read from the checkout's path and branch, the
    claims ledgers, the item files and the coord leases, never a command line or an environment): `bare twin` (the
    checkout is `bare/agentN`), `benchmark agent` (`multi-<hash>/agentN`), `observer` (nothing names the session and a
    `remediate/` claim is live), `reviewer` (its item is a review story), `worker` (a dispatch record names the process,
    or the checkout is on a `work/<id>` branch), `sprint runner` (the checkout's ledger holds a dispatch record whose worker pid runs, or one whose item's run state is
    `working`; with neither the session is only a session in a worktree, `interactive`),
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
    session id in this order: the one session that made the claims of its checkout's ledger (not for a process a dispatch
    record names: its `worker_session` is the previous run's, written when that run exited), the one intent of its item that is not a claim's (a worker's), the one hook session of
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
        if found_rec:  # `worker_session` is written when a run exits: for a pid that still runs it is the last run's
            sid, items = None, [found_rec[0]]
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


def session_rows(ctx, procs, placed, by_path, found, bl, names, states=None):
    """[{label, role, item, item_title, sprint, sprint_title, step, started, last_activity, silent_s, spend_usd, agent_state, pid, checkout}] of
    the Claude Code processes PROCS placed in a checkout (PLACED), oldest first, SESSIONS_KEPT at most; FOUND is
    `read_coord`'s answer (None without one), BL the root's `backlog` (None without items) and NAMES the checkouts as
    shown (`bind_sessions` says how a process gets its session id, a process nothing binds has no label). A dispatch record whose pid
    still runs and that the process table does not list gives a session too, its `started` null."""
    rows = session_entries(ctx, procs, placed, by_path, found, bl, names, states=states)[:SESSIONS_KEPT]
    return [{k: v for k, v in r.items() if k not in RAW_KEYS} for r in rows]


def session_entries(ctx, procs, placed, by_path, found, bl, names, light=False, states=None):
    """`session_rows`' entries, all of them, each with the raw `session` id (null where nothing binds it) and the absolute
    `base` of its checkout besides: for `live_sessions`, never for the panel's data. LIGHT leaves out what costs a read of
    the ops rows or a spool file: `step`, `last_activity` and `spend_usd` are null. STATES is `agent_states`' pair of maps (None
    without them): a session's `agent_state` is the state its pid has there, else its session id, null for neither."""
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
    now = time.time()
    bound = bind_sessions(claude, placed, by_path, ledgers, found)
    landing = landing_steps(ctx.root) if bl is not None and not light else {}
    remediating = any(key.startswith(REMEDIATE) for key, _ in (found or {}).get("claims", []))
    items_of = bl.items if bl is not None else {}

    states_read = []

    def runs():
        """{item: run state} of the coord store, read once and only for a session a dispatch record is the sign of a runner of."""
        if not states_read:
            states_read.append(run_states(ctx) or {})
        return states_read[0]

    def title(item):
        return None if item is None or bl is None or item in bl.withheld else (items_of.get(item) or {}).get("title")

    out = []
    for p in claude:
        base = placed[p["pid"]]
        sid, items, worker = bound[p["pid"]]
        records = ledgers[base]
        dispatched = [i for i, r in records.items() if any(worker_of(r))]
        if not worker:  # a session's claims, else its intents'; the ones still open
            items = [i for i in items or intents_of(found, sid) if (items_of.get(i) or {}).get("status") in ("todo", "doing")]
        known = [items_of[i] for i in items if i in items_of]
        sprints = {it.get("sprint") for it in known}
        live_workers = os.name != "nt" and any(bl_procs.running(w) for w in (worker_of(r)[0] for r in records.values()) if w is not None)
        runner = not worker and bool(dispatched) and (live_workers or any(runs().get(i) == "working" for i in dispatched))
        role = role_of(base, worker, any(it.get("review") for it in known), runner,
                       bool(known) and all(it.get("kind") in PLAN_KINDS for it in known),
                       sid is None and not hook_sessions(base) and remediating, base in by_path)
        item = items[0] if len(items) == 1 else None
        sprint = sprints.pop() if len(sprints) == 1 else None
        stamp, spend = spool_figures(sid) if sid is not None and not light else (None, None)
        quiet = None if light else transcript_quiet(sid, now)
        silent = None if light else silence(quiet, stamp, p["start"], now)
        step = step_of(role, items + [i for i in dispatched if runner and i not in items], bl, landing, live_workers) \
            if bl is not None and not light else None
        out.append({"label": mon_view.session_label(sid) if sid else None, "role": role, "item": item,
                    "item_title": title(item), "sprint": sprint, "sprint_title": title(sprint), "step": step,
                    "started": iso(p["start"]) if p["start"] is not None else None, "last_activity": stamp, "silent_s": silent, "spend_usd": spend,
                    "agent_state": (states[0].get(p["pid"]) or states[1].get(sid)) if states else None, "pid": p["pid"],
                    "checkout": names.get(base, "."), "session": sid, "base": base, "quiet": quiet})
        waits_on = ((found or {}).get("blocked") or {}).get(sid) if sid is not None and not light else None
        if waits_on:  # only a blocked session has the key: a silent one shows no blocked field
            out[-1]["blocked"] = {"on": waits_on[0], "since": iso(waits_on[1]), "age_s": max(0, int(time.time() - waits_on[1]))}
    return out


@contextlib.contextmanager
def one_listing():
    """`bl_procs.worktrees` and `bl_stall.worktrees` answering from one `git worktree list` for each checkout asked about,
    so a placement starts one listing however many of its reads ask for the worktrees. Held under PLACEMENT_LOCK by the
    caller, one block at a time."""
    import bl_procs
    import bl_stall
    saved = (bl_procs.worktrees, bl_stall.worktrees)
    listed = {}

    def worktrees(path):
        key = os.path.realpath(path)
        if key not in listed:
            listed[key] = saved[1](str(path))
        return listed[key]

    bl_stall.worktrees = worktrees
    bl_procs.worktrees = lambda path: [os.path.realpath(p) for p, _ in worktrees(path) or []]
    try:
        yield
    finally:
        bl_procs.worktrees, bl_stall.worktrees = saved


def placement(ctx):
    """(procs, why, blind, worktree rows, {real path: branch}, names, placed): the processes in a checkout of the clone
    (`bl_procs.snapshot`, on Windows `windows_snapshot`; `procs` None and `why` the reason where the host cannot list them,
    `blind` the Windows count of processes with no command line, else None), the worktrees with their branches, the checkouts
    as `display_names` shows them and the real path each process is placed in."""
    import bl_procs
    blind = None
    with PLACEMENT_LOCK, one_listing():
        if os.name == "nt":
            procs, _, why, blind = bl_procs.windows_snapshot(str(ctx.root))
        else:
            procs, _, why = bl_procs.snapshot(str(ctx.root))
        rows, by_path = branches(ctx.root)
        bases = bl_procs.checkouts(str(ctx.root)) if procs is not None else []
    return procs, why, blind, rows, by_path, display_names(ctx.root, bases), checkout_paths(procs or [], bases)


def live_sessions(root):
    """[{pid, session, checkout, role, item, sprint, label}] of the live Claude Code sessions of the clone at ROOT, one for
    each `claude` process in a checkout of it, oldest first, for a tool to follow: `session` is the raw session id (null
    where nothing binds the process to one), `checkout` the absolute real path, `label` the label `mon_view.session_label`
    gives. It is the sessions panel's binding and roles (`session_entries`) read without the stall signals, the ops rows
    and the spool, so a caller can ask again every few seconds. It starts at most two git processes however many checkouts
    the clone has: the one `git worktree list` that every read of the worktrees shares (one more for each repository of
    a `repositories` map), and a `rev-parse` only for a checkout whose `.git` entry names no git dir; each checkout's
    claims ledger is read from its `.git` entry, not by a git call. The raw id and the path stay in this process, the
    panel's data and text never hold them. [] where the host lists no process."""
    ctx = mon_base.Ctx(Path(root).resolve())
    procs, _, _, _, by_path, names, placed = placement(ctx)
    found = read_coord(ctx, events=False)
    rows = session_entries(ctx, procs or [], placed, by_path, found, backlog(ctx.root), names, light=True)
    return [{"pid": r["pid"], "session": r["session"], "checkout": r["base"], "role": r["role"], "item": r["item"],
             "sprint": r["sprint"], "label": r["label"]} for r in rows]


def collect(ctx):
    import kbwho
    import bl_procs
    procs, why, blind, rows, by_path, names, placed = placement(ctx)
    now = time.time()
    found = read_coord(ctx)
    bl = backlog(ctx.root)
    states, why_states = agent_states(ctx.root)
    entries = session_entries(ctx, procs or [], placed, by_path, found, bl, names, states=states)
    fresh = {e["pid"] for e in entries if e["quiet"] is not None and e["quiet"] < bl_procs.FRESH_S}  # a session at work
    out = []
    for p in procs or []:
        base = placed.get(p["pid"])
        session, item = session_of(base, by_path) if p["comm"] == CLAUDE else (None, None)
        _, _, rest = p["where"].partition("/")
        shown = names.get(base, p["where"].split("/", 1)[0])
        kind = bl_procs.DETACHED if p["kind"] == bl_procs.ORPHAN and p["pid"] in fresh else p["kind"]
        out.append({"pid": p["pid"], "age_s": max(0, int(now - p["start"])), "class": kind,
                    "checkout": shown + ("/" + rest if rest else ""), "session": session, "item": item})
    me = kbwho.operator()
    data = {"procs": out, "worktrees": rows, "operator": {"id": me.get("id"), "role": me.get("role")}}
    if procs is None:
        data["procs_unreadable"] = why
    elif blind is not None:
        data["procs_limit"] = WINDOWS_LIMIT + (f"; {blind} process{' shows' if blind == 1 else 'es show'} no command line "
                                               "(another account's, unless run elevated)" if blind else "")
    intents = intent_rows(found)
    if intents is not None:
        data["intents"] = intents
    overlaps = overlap_rows(found, now)
    if overlaps is not None:
        data["overlaps"] = overlaps
        data["needs_you_after_min"] = after_minutes(ctx.root)
    elif coord_conn(ctx) is not None:
        data["overlaps_unread"] = "the coord store does not answer" if found is None else "its events do not read"
    data["dispatch"] = dispatch_runs(ctx.root)
    if why_states:
        data["agent_states_unread"] = why_states
    data["sessions"] = [{k: v for k, v in e.items() if k not in RAW_KEYS} for e in entries[:SESSIONS_KEPT]]
    waits = wait_rows(ctx, data["sessions"], bl)
    if waits is not None:
        data["waits"] = waits
    drift = drift_data(ctx, bl, found, now)
    if drift is not None:
        data["drift"] = drift
    items = stalled(ctx.root, bl)
    if items is not None:
        data["stalled"] = items
    return data


def alerts(data):
    """The alerts of the panel's data: one `orphan` alert (id `sessions.orphan`) while a process of class `orphan` is listed,
    its message counting them and naming the oldest one's pid, and one `drift` alert (id `runs.drift`) while the `drift` data
    counts a run state that differs from git, its message counting them and naming the oldest item."""
    out = []
    orphans = [p for p in data.get("procs") or [] if isinstance(p, dict) and p.get("class") == "orphan"]
    if orphans:
        oldest = max(orphans, key=lambda p: p.get("age_s") or 0)
        out.append({"kind": "orphan", "id": "sessions.orphan", "panel": "sessions", "since": "",
                    "message": f"{len(orphans)} orphan process{'' if len(orphans) == 1 else 'es'}, the oldest pid "
                               f"{oldest.get('pid')} for {age_text(oldest.get('age_s') or 0)}"})
    drift = data.get("drift")
    items = [i for i in (drift.get("items") if isinstance(drift, dict) else None) or [] if isinstance(i, dict)]
    count = drift.get("count") if isinstance(drift, dict) else None
    if items and isinstance(count, int) and not isinstance(count, bool) and count > 0:
        out.append({"kind": "drift", "id": "runs.drift", "panel": "sessions", "since": "",
                    "message": f"{count} run state{' differs' if count == 1 else 's differ'} from git, the oldest {drift_text(items[0])}"
                               "; `backlog.py runs --reconcile` makes coord follow git"})
    return out


def drift_text(i):
    """One drifted run state as words: `ST-… Title (run working, git shows landed, 3h00m)`."""
    age = i.get("age_s")
    return (f"{i.get('item')}" + (f" {clipped(i['title'], TITLE_CHARS)}" if i.get("title") else "")
            + f" (run {i.get('state')}, git shows {i.get('git')}" + (f", {age_text(age)} since its last move" if isinstance(age, int) else "") + ")")


def waits_text(w):
    """One wait as words: `s-1a2b3c waits on Title, Title`; the id where a title is not known."""
    names = ", ".join(clipped(i.get("title") or str(i.get("id")), TITLE_CHARS) for i in w.get("items") or [] if isinstance(i, dict))
    return f"{w.get('session') or '-'} waits on {names or '-'}"


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


def epoch(text):
    """UTC seconds of a `YYYY-MM-DDTHH:MM:SSZ` stamp, None for anything else."""
    try:
        return datetime.datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return None


def clipped(text, n):
    return text if len(text) <= n else text[:max(0, n - 1)] + "…"


def session_line(s, now=None, width=LINE_CHARS):
    """One session entry as one line of at most WIDTH (LINE_CHARS at most) characters, the one function the sessions panel
    and `kbmon.py --status sessions` print an entry with: `label  role  agent state  sprint  item title  step  blocked on permission 2m  up 1h00m  last 20m ago  silent 15m  $1.25` (the `blocked on` part only for a session that waits on the person).
    The sprint is its title cut to SPRINT_CHARS, the item title to the room the other fields leave (TITLE_CHARS at most; the
    id where the title is not known); a field the entry does not know is left out, `silent` too below SILENT_SHOWN_S. NOW is the time the elapsed and last
    activity are taken at (epoch seconds; the snapshot's taken time, else the clock)."""
    now = time.time() if now is None else now
    width = min(width, LINE_CHARS)
    started, last = epoch(s.get("started")), epoch(s.get("last_activity"))
    spend = s.get("spend_usd")
    silent = s.get("silent_s")
    sprint = s.get("sprint_title") or s.get("sprint")
    title = s.get("item_title") or s.get("item") or ""
    state = s.get("agent_state")
    blocked = s.get("blocked") if isinstance(s.get("blocked"), dict) else None
    before = [s.get("label") or "-", s.get("role") or "unknown"] + ([state] if isinstance(state, str) and state else []) \
        + ([clipped(sprint, SPRINT_CHARS)] if sprint else [])
    after = ([s["step"]] if s.get("step") else []) \
        + ([f"blocked on {blocked.get('on') or 'permission'} {age_text(blocked['age_s'])}"] if blocked and isinstance(blocked.get("age_s"), int) else []) \
        + ([f"up {age_text(now - started)}"] if started is not None else []) \
        + ([f"last {age_text(now - last)} ago"] if last is not None else []) \
        + ([f"silent {age_text(silent)}"] if isinstance(silent, (int, float)) and not isinstance(silent, bool)
           and silent >= SILENT_SHOWN_S else []) \
        + ([f"${spend:.2f}"] if isinstance(spend, (int, float)) and not isinstance(spend, bool) else [])
    room = min(TITLE_CHARS, width - len("  ".join(before + after)) - 2)
    mid = [clipped(title, room)] if title and room > 1 else []
    return clipped("  ".join(before + mid + after), width)


def session_lines(sessions, width, taken=None):
    """The sessions as rows, SESSIONS_SHOWN at most then `+N more`: `session_line` of each, behind the label `sessions` and
    within WIDTH columns; TAKEN is the snapshot's taken time."""
    sessions = [s for s in sessions if isinstance(s, dict)]
    now = epoch(taken)
    shown = sessions[:SESSIONS_SHOWN]
    rows = [("sessions" if n == 0 else "").ljust(LABEL) + session_line(s, now, width - 2 - LABEL) for n, s in enumerate(shown)]
    if len(sessions) > len(shown):
        rows.append(" " * LABEL + f"+{len(sessions) - len(shown)} more")
    return rows


def lines(data, width=80, taken=None):
    """The body rows: the processes table (an orphan's row starts `! `, orphans first, PROCS_SHOWN at most), the worktrees
    with their branches, the dispatch runs (item, pid, session, `alive` or `ended`, live ones first, DISPATCH_SHOWN at most) and
    the stalled items, each a `! ` row of its id and signals; first the clone's operator, the live session intents
    (session, item, operator) and the sessions, one `session_line` each (TAKEN is the snapshot's taken time)."""
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
    rows += session_lines(data.get("sessions") or [], width, taken)
    waits = [w for w in data.get("waits") or [] if isinstance(w, dict)]
    if waits:
        parts = [waits_text(w) for w in waits[:WAITS_SHOWN]]
        if len(waits) > WAITS_SHOWN:
            parts.append(f"+{len(waits) - WAITS_SHOWN} more")
        rows += joined("waits", parts, width - 2)
    drift = data.get("drift") if isinstance(data.get("drift"), dict) else {}
    drifted = [i for i in drift.get("items") or [] if isinstance(i, dict)]
    for n, i in enumerate(drifted[:DRIFT_SHOWN]):
        rows.append("! " + ("drift".ljust(LABEL - 2) if n == 0 else " " * (LABEL - 2)) + clipped(drift_text(i), width - 2 - LABEL))
    if len(drifted) > DRIFT_SHOWN:
        rows.append(" " * LABEL + f"+{len(drifted) - DRIFT_SHOWN} more")
    found = [o for o in data.get("overlaps") or [] if isinstance(o, dict)]
    if data.get("overlaps_unread"):
        rows.append("! " + clipped("overlaps not read: " + str(data["overlaps_unread"]), width - 2 - 2))
    if found:
        parts = [overlap_text(o) for o in found[:OVERLAPS_SHOWN]]
        if len(found) > OVERLAPS_SHOWN:
            parts.append(f"+{len(found) - OVERLAPS_SHOWN} more")
        rows += [("overlaps" if n == 0 else "").ljust(LABEL) + clipped(p, width - 2 - LABEL) for n, p in enumerate(parts)]
    if procs:
        shown = procs[:PROCS_SHOWN]
        rows += [("! " if flag else "") + text for flag, text in table(shown, width - 2)]
        if len(procs) > len(shown):
            rows.append(f"+{len(procs) - len(shown)} more")
    elif data.get("procs_unreadable"):
        rows.append("processes unreadable: " + str(data["procs_unreadable"]))
    else:
        rows.append("processes none")
    if data.get("procs_limit"):
        rows += joined("limit", str(data["procs_limit"]).split("; "), width - 2)
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
