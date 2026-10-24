"""`backlog.py runs`: each item's run state in coord beside what git and the claims ledger show of it, and
`runs --reconcile`, which makes coord follow git (kb/_self/backlog.md, Running a sprint; kb/_self/coordination.md, section
"The run states").

  runs [SP|ID]              one line per item: its coord run state (the value of `run/<id>`, `none` when no move wrote it),
                            its item file status, the open gates of the item file on its work branch (`work/<id>`) and
                            whether the worker pid its claims-ledger record holds runs; then one `drift` line for each item
                            whose run state contradicts git, exit 1 when any is listed. SP: the sprint's items; ID: that
                            item; neither: the items of the active sprints and every item that holds a run key
  runs [SP|ID] --reconcile  write the state git shows to each drifted run key and exit 0 once none is left

A run state contradicts git in three ways, checked in this order and each item named once, with the state `--reconcile` writes:
the item file is `done` and the run state is not `landed` (writes `landed`); the run state is `working` and the worker pid is
gone or was never recorded (`failed`); the run state is none of `landed`, `released` or `none` and no claim holds the item, that
is neither a record in its claims ledger nor the status `doing` of its item file, which a claim sets (`released`). `--reconcile` writes the key with `put` at the
revision it read, outside the state table (the table has no move from `working` to `landed`: the point is to follow a
crash), and posts a `progress` event with `step=reconcile` beside it, so `coord.py wait` and the digest show the correction.
A key that moved on between the read and the write is read again, three tries. Exit codes: 0 no drift (or all reconciled),
1 drift listed (or a reconcile write failed), 2 coord cannot be read or the argument names no item.

Standard library only; imports `bl_base`, `bl_cli`, `bl_clean` (the coord runner and the CAS writer) and `bl_dispatch` (the
branch name), never `backlog` (a layer rule). It registers its own subcommand when imported, so `backlog.py` carries only
the import."""
import json
import subprocess

import bl_cli
import bl_clean
from bl_base import Refused, claims_ledger, open_gates, rel_dir, say

RUN_KEYS = "run/"  # coord.py's RUN_KEYS: an item's run state is the value of run/<item id>
NONE = "none"
SETTLED = ("landed", "released", NONE)  # the run states from which no claim is needed
GATE_KINDS = ("blocking", "provisional")
TRIES = 3


def run_states():
    """{item id: state} of every run key coord holds with a value, or raises Refused when coord cannot be read."""
    code, body, err = bl_clean.run_coord("list", "--prefix", RUN_KEYS)
    if code != 0 or not isinstance(body, list):
        raise Refused(f"runs: cannot read the run keys: {err or 'coord.py exited ' + str(code)}")
    return {row["key"][len(RUN_KEYS):]: row["value"] for row in body if row.get("value")}


def ledger_of(root):
    """The claims ledger of this working tree as a dict, {} when there is none or it cannot be read."""
    path = claims_ledger(root)[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path else {}
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def branch_gates(root, iid):
    """The number of open gates of the item file on its work branch, None when the branch or the file is not there."""
    import bl_dispatch
    p = subprocess.run(["git", "-C", str(root), "show", f"{bl_dispatch.worker_branch(iid)}:{rel_dir()}/{iid}.json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        return None
    try:
        return len(open_gates(json.loads(p.stdout), GATE_KINDS))
    except (ValueError, AttributeError):
        return None


def worker_of(record):
    """(pid, whether it runs) of a ledger record; (None, False) when it records no worker pid."""
    pid = record.get("worker_pid") if isinstance(record, dict) else None
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None, False
    import tests as tests_py
    return pid, tests_py.pid_alive(pid)


def drift_of(state, status, alive, claimed):
    """(the state git shows, why) for a run key that contradicts git, else None."""
    if state == NONE:
        return None
    if status == "done" and state != "landed":
        return "landed", f"the item file is done and the run state is {state}"
    if state == "working" and not alive:
        return "failed", "the run state is working and its worker pid is gone"
    if state not in SETTLED and not claimed:
        return "released", f"the run state is {state} and no claim holds the item"
    return None


def collect(bl, states, scope):
    """One row for each item of SCOPE (a list of ids; the ids with no item file too): id, run state, item file status,
    open gates on the work branch, worker pid and whether it runs, and the drift (state, why) or None."""
    ledger = ledger_of(bl.root)
    rows = []
    for iid in scope:
        it = bl.items.get(iid)
        rec = ledger.get(iid)
        pid, alive = worker_of(rec)
        state = states.get(iid, NONE)
        status = it.get("status") if it else None
        claimed = bool(rec) or status == "doing"
        rows.append({"id": iid, "state": state, "status": status, "gates": branch_gates(bl.root, iid) if it else None,
                     "pid": pid, "alive": alive, "drift": drift_of(state, status, alive, claimed)})
    return rows


def scope_of(bl, states, target):
    """The ids a `runs` call covers, or Refused when TARGET names no item."""
    if target is None:
        active = {s for s, it in bl.items.items() if it.get("kind") == "sprint" and it.get("status") == "active"}
        ids = {i for s in active for i in bl.sprint_items(s)} | set(states)
        return sorted(ids)
    it = bl.items.get(target)
    if it is None:
        raise Refused(f"runs: no item {target}")
    return sorted(bl.sprint_items(target)) if it.get("kind") == "sprint" else [target]


def line_of(row):
    gates = "no work branch" if row["gates"] is None else f"{row['gates']} open gate(s)"
    worker = ("no worker pid" if row["pid"] is None
              else f"worker pid {row['pid']} {'runs' if row['alive'] else 'gone'}")
    return f"{row['id']}  run {row['state']}  file {row['status'] or 'no item file'}  {gates}  {worker}"


def reconcile_one(iid, to):
    """Write the run key of ITEM the state TO, outside the state table, and post the progress event of the move.
    Returns an error text, None when both were written."""
    key = RUN_KEYS + iid
    for _try in range(TRIES):
        code, body, err = bl_clean.run_coord("get", key)
        if code not in (0, 1):
            return f"cannot read {key}: {err or 'coord.py exited ' + str(code)}"
        revision = body.get("revision", 0) if isinstance(body, dict) else 0
        code, _body, err = bl_clean.run_coord("put", key, f"--value={to}", "--revision", str(revision))
        if code == 0:
            break
        if code != 1:
            return f"cannot write {key}: {err or 'coord.py exited ' + str(code)}"
    else:
        return f"{key} keeps moving on"
    code, _body, err = bl_clean.run_coord("post", "--kind", "progress", "--field", f"item={iid}", "--field", f"state={to}",
                                          "--field", "step=reconcile")
    return None if code == 0 else f"{key} is {to}, but its progress event was not posted: {err or 'coord.py exited ' + str(code)}"


def args_runs(p):
    p.add_argument("target", nargs="?", metavar="SP|ID", help="a sprint (its items) or an item; default the active sprints' items "
                   "and every item with a run key")
    p.add_argument("--reconcile", action="store_true", help="write each drifted run key the state git shows")


def cmd_runs(bl, a):
    try:
        states = run_states()
        rows = collect(bl, states, scope_of(bl, states, a.target))
    except Refused as e:
        say(str(e))
        return 2
    for r in rows:
        say(line_of(r))
    drifted = [r for r in rows if r["drift"]]
    for r in drifted:
        say(f"drift: {r['id']}  {r['drift'][1]}; git shows {r['drift'][0]}")
    if not a.reconcile:
        say(f"runs: {len(rows)} item(s), {len(drifted)} drifted" + ("; `runs --reconcile` makes coord follow git" if drifted else ""))
        return 1 if drifted else 0
    failed = 0
    for r in drifted:
        error = reconcile_one(r["id"], r["drift"][0])
        if error:
            failed += 1
            say(f"reconcile: {r['id']}: {error}")
        else:
            say(f"reconcile: {r['id']} run {r['state']} to {r['drift'][0]}")
    say(f"runs: {len(rows)} item(s), {len(drifted) - failed} reconciled, {failed} failed")
    return 1 if failed else 0


bl_cli.register("runs", cmd_runs, args_runs,
                help="each item's coord run state beside its item file, work branch gates and worker pid; --reconcile "
                     "makes coord follow git")
