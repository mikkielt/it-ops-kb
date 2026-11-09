"""`backlog.py runs`: each item's run state in coord beside what git and the claims ledger show of it, and
`runs --reconcile`, which makes coord follow git (kb/_self/backlog.md, Running a sprint; kb/_self/coordination.md, section
"The run states").

  runs [SP|ID]              one line per item: its coord run state (the value of `run/<id>`, `none` when no move wrote it),
                            its item file status, the open gates of the item file on its work branch (`work/<id>`) and
                            whether its worker pid runs (the pid of the coord process record `dispatch` writes, which every
                            tree and clone sees, else the one of this tree's claims-ledger record; at the run state `staging`
                            or `landing` the pid is named `stage-back pid` or `land pid`, since the process record is the one
                            that run wrote); then one `drift` line for each item
                            whose run state contradicts git, exit 1 when any is listed. SP: the sprint's items; ID: that
                            item; neither: the items of the active sprints and every item that holds a run key
  runs [SP|ID] --reconcile  write the state git shows to each drifted run key and exit 0 once none is left

A run state contradicts git in five ways, checked in this order and each item named once, with the state `--reconcile` writes:
the item file is `done`, its done commit is on the integration main (the item file reads done on it as last fetched) and the run state
is not `landed`, `none` included (writes `landed`; a done item whose commit is not on it yet keeps its key until `land` moves it); the run state is `landed` and the
item file is not done (a reopened item: writes `none`, which moves to `claimed`, where `landed` moves nowhere; `reopen` writes it
too, `reset_landed`); the run state is `working` and the worker pid is
gone or was never recorded anywhere (`failed`); the run state is `staging` or `landing` and no process record of the item
(coord `own/`, which a stage-back and a land write for their run) names a pid that runs (`returned`, `refused`: a stage-back or land
killed before its last move); the run state is none of `landed`, `released` or `none` and no claim holds the
item, that is neither a record in its claims ledger nor the status `doing` of its item file, which a claim sets, nor the same in
another working tree of the repository, nor an `own/` record of coord that names the item (`released`). `--reconcile` writes the key with `put` at the
revision it read, outside the state table (the table has no move from `working` to `landed`: the point is to follow a
crash), and posts a `progress` event with `step=reconcile` beside it (none for `none`, which no event carries), so `coord.py wait` and the digest show the correction.
A key that moved on between the read and the write is read again, three tries. Exit codes: 0 no drift (or all reconciled),
1 drift listed (or a reconcile write failed), 2 coord cannot be read or the argument names no item.

Standard library only; imports `bl_base`, `bl_cli`, `bl_clean` (the coord runner and the CAS writer), `bl_dispatch` (the
branch name), `bl_items` (the worker's pid) and `kbpublic` (the integration remote's name), never `backlog` (a layer rule). It registers its own subcommand when imported, so `backlog.py` carries only
the import."""
import json
import subprocess
from pathlib import Path

import bl_cli
import bl_clean
from bl_base import Refused, claims_ledger, open_gates, rel_dir, say

RUN_KEYS = "run/"  # coord.py's RUN_KEYS: an item's run state is the value of run/<item id>
NONE = "none"
SETTLED = ("landed", "released", NONE)  # the run states from which no claim is needed
GATE_KINDS = ("blocking", "provisional")
TRIES = 3
HELD = {"staging": ("returned", "stage-back"), "landing": ("refused", "land")}  # state a tool holds while it runs: (where a key none runs goes, the tool); as bl_land.RUN_TOOLS and RUN_HEALED


def run_states():
    """{item id: state} of every run key coord holds with a value, or raises Refused when coord cannot be read."""
    code, body, err = bl_clean.run_coord("list", "--prefix", RUN_KEYS)
    if code != 0 or not isinstance(body, list):
        raise Refused(f"runs: cannot read the run keys: {err or 'coord.py exited ' + str(code)}")
    return {row["key"][len(RUN_KEYS):]: row["value"] for row in body if row.get("value")}


def trees_of(root):
    """The other working trees of ROOT's repository (`git worktree list`), as paths; [] when git cannot say. A clone of
    the repository is none of them: its claims reach this tree only through the coord store."""
    p = subprocess.run(["git", "-C", str(root), "worktree", "list", "--porcelain"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    here = claims_ledger(root)[0]
    paths = [line[len("worktree "):] for line in p.stdout.splitlines() if line.startswith("worktree ")] if p.returncode == 0 else []
    return [Path(x) for x in paths if Path(x) != Path(here)]


def ledgers_of(trees):
    """{tree: the ids its claims ledger holds}, a ledger that is not there or does not read giving no ids."""
    out = {}
    for tree in trees:
        try:
            data = json.loads(claims_ledger(tree)[1].read_text(encoding="utf-8"))
        except (OSError, ValueError, AttributeError):
            data = {}
        out[tree] = set(data) if isinstance(data, dict) else set()
    return out


def claimed_elsewhere(trees, ledgers, owned, iid):
    """Whether another working tree of the repository holds the claim of IID (a record in its claims ledger, or the status
    `doing` in its item file), or an `own/` record of coord (OWNED, the ids that have one) names the item: a claim made in
    that tree and not yet fetched here is none of this tree's."""
    if iid in owned:
        return True
    for tree in trees:
        if iid in ledgers.get(tree, ()):
            return True
        try:
            item = json.loads((tree / rel_dir() / f"{iid}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(item, dict) and item.get("status") == "doing":
            return True
    return False


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


def on_integration_main(root, iid, missing=True):
    """Whether the item's file reads `done` on the integration main as last fetched (the done commit is on it). MISSING
    is the answer when the ref is missing: git cannot say, so the item file is taken as the answer."""
    import kbpublic
    ref = f"refs/remotes/{kbpublic.integration_remote(root)}/main"
    if subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", ref], capture_output=True).returncode:
        return missing
    p = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{rel_dir()}/{iid}.json"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    try:
        return p.returncode == 0 and json.loads(p.stdout).get("status") == "done"
    except (ValueError, AttributeError):
        return False


def drift_of(state, status, alive, claimed, on_main=True, done_on_main=False):
    """(the state git shows, why) for a run key that contradicts git, else None. ON_MAIN: the item's done commit is on the
    integration main; a done item whose commit is not has no drift of the claim kinds either: `land` moves its key once it is.
    DONE_ON_MAIN: the item file reads done on the integration main as last fetched; a `landed` key over a file that is not
    done here is left alone then, since a checkout that has not pulled the landing is behind, not the key wrong."""
    if status == "done" and state != "landed" and on_main:
        return "landed", f"the item file is done and the run state is {state}"
    if state == "landed" and status not in (None, "done") and not done_on_main:
        return NONE, f"the run state is landed and the item file is {status}, not done"
    if state == NONE:
        return None
    if state == "working" and not alive:
        return "failed", "the run state is working and its worker pid is gone"
    if state in HELD and not alive:
        return HELD[state][0], f"the run state is {state} and no {HELD[state][1]} of the item runs"
    if state not in SETTLED and not claimed and on_main:
        return "released", f"the run state is {state} and no claim holds the item"
    return None


def collect(bl, states, scope):
    """One row for each item of SCOPE (a list of ids; the ids with no item file too): id, run state, item file status,
    open gates on the work branch, worker pid and whether it runs, and the drift (state, why) or None. The worker is the
    one `bl_items.worker_of` finds (the coord process record first, which every tree sees); a claim another working tree
    of the repository holds counts as a claim (`claimed_elsewhere`), read only for a drift that would release the key."""
    import bl_items
    ledger = ledger_of(bl.root)
    owners = bl_items.coord_owners()
    coord, table = bl_items.coord_workers(owners), bl_clean.host_table(bl.root)
    owned = {r["item"] for r in owners if r.get("item")}
    trees = ledgers = None
    rows = []
    for iid in scope:
        it = bl.items.get(iid)
        pid, alive = bl_items.worker_of(bl, iid, coord, table)
        state = states.get(iid, NONE)
        status = it.get("status") if it else None
        claimed = bool(ledger.get(iid)) or status == "doing"
        if not claimed and state not in SETTLED and status != "done":
            if trees is None:
                trees = trees_of(bl.root)
                ledgers = ledgers_of(trees)
            claimed = claimed_elsewhere(trees, ledgers, owned, iid)
        on_main = status != "done" or state == "landed" or on_integration_main(bl.root, iid)
        behind = state == "landed" and status not in (None, "done") and on_integration_main(bl.root, iid, missing=False)
        rows.append({"id": iid, "state": state, "status": status, "gates": branch_gates(bl.root, iid) if it else None,
                     "pid": pid, "alive": alive, "drift": drift_of(state, status, alive, claimed, on_main, behind)})
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
    tool = HELD[row["state"]][1] if row["state"] in HELD else None  # a key at staging or landing is held by that tool's process record
    who = f"{tool} pid" if tool else "worker pid"
    worker = f"no {who}" if row["pid"] is None else f"{who} {row['pid']} {'runs' if row['alive'] else 'gone'}"
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
    if to == NONE:  # a progress event carries no state `none`: the key's value is the whole record
        return None
    code, _body, err = bl_clean.run_coord("post", "--kind", "progress", "--field", f"item={iid}", "--field", f"state={to}",
                                          "--field", "step=reconcile")
    return None if code == 0 else f"{key} is {to}, but its progress event was not posted: {err or 'coord.py exited ' + str(code)}"


def reset_landed(iid):
    """Write the run key of a reopened item `none` when it holds `landed` (the state of its earlier landing, which moves
    nowhere), so the next `land` takes it to `landing`. Returns a text for the operator when the key could not be read or
    written, None when it was reset or held no `landed`."""
    code, body, err = bl_clean.run_coord("get", RUN_KEYS + iid)
    if code not in (0, 1):
        return f"cannot read {RUN_KEYS}{iid}: {err or 'coord.py exited ' + str(code)}"
    if not isinstance(body, dict) or body.get("value") != "landed":
        return None
    return reconcile_one(iid, NONE)


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
