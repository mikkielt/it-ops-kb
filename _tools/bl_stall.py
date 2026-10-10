"""`backlog.py stalled`: the claimed and the ready items that show a stall signal (kb/_self/backlog.md, Stalled
work; kb/_self/tools.md; the kb-sprint skill, Stalled work).

  stalled                      list each claimed (doing) or ready item that shows a signal, with its signals (read
                               only; exit 0, also when nothing stalls)
  stalled --json               the same as one JSON object

The signals are read from the claims (item files), git and the ops rows of the query log's spool and committed ops
sidecars (`ql_store` readers; a row's closed keys only, never event text), never from a process's arguments, and, for
`mr-dead` only, from one read of each claimed item's request through `bl_forge`, the one network call:

  claim-no-commit     a claim with no work commit past CLAIM_NO_COMMIT_S
  returned-no-commit  a worker's worktree with no live process, no work commit and a claim older than
                      RETURNED_GRACE_S
  returned-staged     the same, with staged or modified files left in the worktree (the worker waited for a
                      background-run completion notice that never came)
  done-refused        DONE_REFUSED_N `done.refused` rows of the item
  check-timeout       CHECK_TIMEOUT_N refused dones whose `ms` reached CHECK_TIMEOUT_S: a check ran out of its time
  land-same-step      LAND_SAME_STEP_N failed `land.step` rows of one step of the item
  mr-dead             the item's `code/<id>` request (claimed items) is not merged and will not merge by waiting: its
                      head pipeline failed, was canceled, skipped or is manual (MR_DEAD_PIPELINE), or its detailed
                      merge status is one of MR_DEAD_MERGE
  red-main            the newest `ci.pipeline` row is red (claimed items)
  lock-wait           the host test lock has been held, by a live process, for HOST_LOCK_WAIT_S (claimed items)

A signal whose input cannot be read is `unknown:<what>`, never a guess: a request read that fails, a forge CLI not
signed in or a remote that names no forge project is `unknown:forge`. Standard library only; imports `bl_base` and
`bl_cli` at load and never `backlog` (a layer rule); the query log, `tests`, `bl_procs`, `bl_forge` and `kg_lane` are
imported where used. It registers its own subcommand when imported, so `backlog.py` carries only the import.
"""
import datetime
import json
import os
import re
import subprocess
import time
from pathlib import Path

import bl_base
import bl_cli
from bl_base import CHECK_TIMEOUT_S, say

CLAIM_NO_COMMIT_S = 3600  # seconds a claim may go with no work commit before it is a stall
RETURNED_GRACE_S = 600  # seconds after a claim before a worktree with no live process counts as a returned worker
DONE_REFUSED_N = 2  # refused `done` rows of one item that make the repeat a stall
CHECK_TIMEOUT_N = 2  # refused dones that ran out of the check time that make a timeout a stall
LAND_SAME_STEP_N = 2  # failed rows of one `land` step of one item that make the repeat a stall
HOST_LOCK_WAIT_S = 1800  # seconds the host test lock may be held before the runs waiting for it are a stall
LOCK_NAME = "kb-tests.lock"  # tests.py's host lock file (tests.HOST_LOCK_NAME), read for its holder and start

# Head pipeline words of a request that never become `success` by waiting: the pipeline ended without it, or holds at a
# manual job.
MR_DEAD_PIPELINE = ("failed", "canceled", "skipped", "manual")
# Detailed merge statuses (GitLab's `detailed_merge_status`, kb/public/gitlab/automated-merge-requests.md) that no
# wait clears: each needs a push, a rebase, an approval, a resolved thread, an unlocked path, a finished external
# check or another request's merge. `conflict` is left out: the status names it also while the conflict check is still
# computing, and the request read carries no raw merge status to tell the two apart. A status not listed (`checking`,
# `unchecked`, `preparing`, `ci_still_running`, `merge_time`, ...) is no signal.
MR_DEAD_MERGE = ("not_open", "draft_status", "need_rebase", "commits_status", "discussions_not_resolved",
                 "not_approved", "requested_changes", "ci_must_pass", "jira_association_missing", "locked_paths",
                 "locked_lfs_files", "title_regex", "security_policy_violations", "status_checks_must_pass",
                 "merge_request_blocked")

SIGNALS = ("claim-no-commit", "returned-no-commit", "returned-staged", "done-refused", "check-timeout",
           "land-same-step", "mr-dead", "red-main", "lock-wait")
ROW_KEYS = ("id", "ts", "surface", "v")  # the spool row's own keys, which ops_problems does not read


# ---------------------------------------------------------------- the inputs: git, the ops rows, the host lock

def now_epoch():
    return time.time()


def iso_epoch(ts):
    """Seconds since the epoch of a row's UTC time (`2026-10-02T10:00:00.000Z`), or None."""
    try:
        return datetime.datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return None


def git_lines(root, *args):
    """The stdout lines of a git command, or None when it fails (a missing input is `unknown`, never a guess)."""
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout.splitlines() if p.returncode == 0 else None


def commits_of(root, iid):
    """[(epoch, subject, [KB-Work ids])] of the commits on any ref whose last paragraph carries `KB-Work: iid`, or
    None when git cannot be read."""
    out = git_lines(root, "log", "--all", "--fixed-strings", f"--grep={iid}", "--format=%ct%x1f%s%x1f"
                    "%(trailers:key=KB-Work,valueonly,separator=%x2C)")
    if out is None:
        return None
    found = []
    for ln in out:
        parts = ln.split("\x1f")
        if len(parts) == 3 and parts[0].isdigit():
            ids = [x.strip() for x in parts[2].split(",")]
            if iid in ids:
                found.append((int(parts[0]), parts[1], ids))
    return found


PLANNING = "chore(backlog):"  # the subject prefix of a planning commit (claim, file, gate, done): never the work


def claim_facts(root, iid):
    """{claimed, work, branches}: the epoch of the item's newest claim commit (None when no commit claims it), the
    epochs of the work commits at or after it (a planning commit is no work), and the branches `work/ID` and
    `code/ID` that exist. None when git cannot be read."""
    commits = commits_of(root, iid)
    refs = git_lines(root, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    if commits is None or refs is None:
        return None
    claims = [t for t, s, _ in commits if s.startswith(f"{PLANNING} claim ")]
    claimed = max(claims) if claims else None
    work = [t for t, s, _ in commits if not s.startswith(PLANNING) and claimed is not None and t >= claimed]
    names = {f"work/{iid}", f"code/{iid}"}
    return {"claimed": claimed, "work": work,
            "branches": sorted({re.sub(r"^refs/(?:heads|remotes/[^/]+)/", "", r) for r in refs} & names)}


def worktrees(root):
    """[(path, branch or None)] of the clone's worktrees, or None when git cannot list them."""
    out = git_lines(root, "worktree", "list", "--porcelain")
    if out is None:
        return None
    found, cur = [], None
    for ln in out + [""]:
        if ln.startswith("worktree "):
            cur = [ln[9:], None]
        elif ln.startswith("branch ") and cur:
            cur[1] = ln[7:].removeprefix("refs/heads/")
        elif not ln and cur:
            found.append(tuple(cur))
            cur = None
    return found


def worktree_of(root, iid):
    """The path of the worktree that works `iid` (on the branch `work/ID`, or named ID), None when there is none,
    False when worktrees cannot be listed."""
    wts = worktrees(root)
    if wts is None:
        return False
    root_real = os.path.realpath(root)
    for path, branch in wts:
        if os.path.realpath(path) != root_real and (branch == f"work/{iid}" or Path(path).name == iid):
            return path
    return None


def left_in(path):
    """Whether a worktree holds staged or modified tracked files (an untracked file alone is not), None when git
    cannot say."""
    out = git_lines(path, "status", "--porcelain")
    return None if out is None else any(ln and not ln.startswith("??") for ln in out)


def live_in(path):
    """(whether a process but this one runs with its working directory in `path`, why not told). The scan is
    `bl_procs.cwd_map`'s, which reads no process's command line."""
    import bl_procs
    cwds, why = bl_procs.cwd_map()
    if cwds is None:
        return None, why
    base = os.path.realpath(path)
    for pid, cwd in cwds.items():
        real = os.path.realpath(cwd)
        if pid != os.getpid() and (real == base or real.startswith(base + os.sep)):
            return True, None
    return False, None


def ops_rows(root):
    """The ops rows of this host's spool and of the committed sidecars of `root`, each row id once, as the store keeps
    them: a row with a closed event and closed keys (`ql_capture.ops_problems`), the rest left out."""
    import ql_capture
    import ql_distill
    import ql_store
    rows = []
    spool = ql_capture.spool_dir()
    for f in sorted(Path(spool).glob("tools-*.jsonl")) if spool is not None and Path(spool).is_dir() else []:
        rows += [r for r in ql_distill.spool_rows(f)[0] if r.get("surface") == ql_capture.OPS]
    for _, objs in ql_store.records(ql_store.ops_files(Path(root) / "kb" / "_querylog")):
        rows += [o for _, o in objs]
    seen, out = set(), []
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str) or r["id"] in seen:
            continue
        if ql_capture.ops_problems({k: v for k, v in r.items() if k not in ROW_KEYS}):
            continue
        seen.add(r["id"])
        out.append(r)
    return sorted(out, key=lambda r: (str(r.get("ts")), r["id"]))


def lock_state(now):
    """(state, detail): `none` (no host test lock), `held` (a live holder, with its pid and age in seconds),
    `stale` (a holder that is gone), or `unknown` (a lock file that cannot be read or has no record)."""
    try:
        import tests
        path = os.path.join(tests.host_lock_dir(), LOCK_NAME)
        if not os.path.exists(path):
            return "none", None
        holder = tests.read_holder(path)
        if holder is None:
            return "unknown", "the lock file has no readable record"
        if not tests.pid_alive(holder["pid"]):
            return "stale", {"pid": holder["pid"]}
        started = iso_epoch(holder["started"].replace("Z", ".000Z"))
        if started is None:
            return "unknown", "the lock record has no start time"
        return "held", {"pid": holder["pid"], "age": max(0, int(now - started))}
    except Exception as e:  # noqa: BLE001 - a lock that cannot be read is unknown, never an error of the listing
        return "unknown", type(e).__name__


# ---------------------------------------------------------------- the signals

def ops_signals(rows):
    """{item id: [signal]} read from the ops rows alone: the repeats of a refused `done`, of a check's timeout and of
    a failed `land` step."""
    refused, timeout, steps = {}, {}, {}
    for r in rows:
        iid, ev = r.get("item"), r.get("event")
        if ev == "done.refused":
            refused[iid] = refused.get(iid, 0) + 1
            if "check-failed" in r.get("reasons", []) and r.get("ms", 0) >= CHECK_TIMEOUT_S * 1000:
                timeout[iid] = timeout.get(iid, 0) + 1
        elif ev == "land.step" and r.get("exit") != 0:
            steps[(iid, r.get("step"))] = steps.get((iid, r.get("step")), 0) + 1
    found = {}
    for iid, n in refused.items():
        if n >= DONE_REFUSED_N:
            found.setdefault(iid, []).append("done-refused")
    for iid, n in timeout.items():
        if n >= CHECK_TIMEOUT_N:
            found.setdefault(iid, []).append("check-timeout")
    for (iid, _), n in steps.items():
        if n >= LAND_SAME_STEP_N and "land-same-step" not in found.get(iid, []):
            found.setdefault(iid, []).append("land-same-step")
    return found


def main_state(rows):
    """('red'|'ok'|'unknown', ts): the state of the newest `ci.pipeline` row; unknown when there is none."""
    last = [r for r in rows if r.get("event") == "ci.pipeline"]
    if not last:
        return "unknown", None
    r = last[-1]
    return ("red" if r.get("state") == "red" else "ok"), r.get("ts")


def claim_signals(root, iid, now):
    """([signal], [unknown]) of a claimed item from git and the worktree's processes."""
    facts = claim_facts(root, iid)
    if facts is None:
        return [], ["unknown:git"]
    if facts["claimed"] is None:
        return [], ["unknown:claim-time"]
    out, unknown = [], []
    age = now - facts["claimed"]
    if facts["work"] or age <= 0:
        return out, unknown
    if age > CLAIM_NO_COMMIT_S:
        out.append("claim-no-commit")
    if age > RETURNED_GRACE_S:
        wt = worktree_of(root, iid)
        if wt is False:
            unknown.append("unknown:worktrees")
        elif wt:
            live, why = live_in(wt)
            if live is None:
                unknown.append("unknown:procs")
            elif not live:
                out.append("returned-staged" if left_in(wt) else "returned-no-commit")
    return out, unknown


def request_dead(request):
    """Whether a `bl_forge.Request` will not merge by waiting. None (no request), a merged one (its `not_open` is the
    goal reached) and a status not listed in MR_DEAD_MERGE are no signal."""
    if request is None or request.state == "merged":
        return False
    return request.pipeline in MR_DEAD_PIPELINE or request.merge_status in MR_DEAD_MERGE


def forge_reads(root, ids, run=None):
    """{item id: whether its `code/<id>` request is dead} for the ids read, one `bl_forge` request read for each. The
    first read that fails (a CLI not installed or signed in, a failed call, a remote that names no forge project)
    ends the reads, as the rest would fail the same way: an id left out is `unknown:forge`."""
    import bl_forge
    from kg_lane import CODE_BRANCH_PREFIX
    dead = {}
    if not ids:
        return dead
    try:
        arm = bl_forge.arm(root, run)
        for iid in ids:
            dead[iid] = request_dead(arm.request(branch=CODE_BRANCH_PREFIX + iid))
    except Exception:  # noqa: BLE001 - a read that fails is unknown:forge, never an error of the listing
        pass
    return dead


def ready_items(bl):
    """The ready items (`next`'s list: todo, nothing it waits on, in an active sprint) in work order."""
    return sorted((i for i in bl.items if bl.items[i].get("status") == "todo" and not bl_base.waits(bl, i)),
                  key=bl.order_key)


def collect(bl, now=None, run=None):
    """{main, lock, ops_rows, forge_reads, items}: the stall signals of every claimed or ready item. `items` is a list
    of {id, label, state, claimed_by, signals, unknown} in work order, only items with a signal or an unknown. RUN is
    `bl_base.run`'s shape, the runner of the forge reads (the default is `bl_base.run`)."""
    now = now_epoch() if now is None else now
    root = str(bl.root)
    try:
        rows = ops_rows(root)
    except Exception:  # noqa: BLE001 - an unreadable log is no signal, said as unknown
        rows = None
    from_rows = ops_signals(rows or [])
    main, main_ts = main_state(rows or [])
    lock, lock_detail = lock_state(now)
    held_long = lock == "held" and lock_detail["age"] > HOST_LOCK_WAIT_S
    doing = [i for i, it in bl.items.items() if it.get("status") == "doing" and it.get("claimed_by")
             and it.get("kind") != "sprint"]
    dead = forge_reads(root, sorted(doing, key=bl.order_key), run)
    out = []
    for iid in sorted(set(doing) | set(ready_items(bl)), key=bl.order_key):
        signals, unknown = list(from_rows.get(iid, [])), []
        if iid in doing:
            more, unknown = claim_signals(root, iid, now)
            signals += more
            if iid not in dead:
                unknown.append("unknown:forge")
            elif dead[iid]:
                signals.append("mr-dead")
            if main == "red":
                signals.append("red-main")
            if held_long:
                signals.append("lock-wait")
            if lock == "unknown":
                unknown.append("unknown:lock")
        signals = [s for s in SIGNALS if s in signals]
        if signals or unknown:
            out.append({"id": iid, "label": bl.label(iid), "state": "doing" if iid in doing else "ready",
                        "claimed_by": bl.items[iid].get("claimed_by"), "signals": signals, "unknown": unknown})
    return {"main": {"state": main, "ts": main_ts}, "lock": {"state": lock, "detail": lock_detail},
            "ops_rows": None if rows is None else len(rows), "forge_reads": len(dead), "items": out}


# ---------------------------------------------------------------- the command

def args_stalled(p):
    p.add_argument("--json", action="store_true", help="print the signals as one JSON object")


def cmd_stalled(bl, a):
    report = collect(bl)
    if a.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    m, lk = report["main"], report["lock"]
    say(f"stalled: main {m['state']}" + (f" (ci.pipeline row of {m['ts']})" if m["ts"] else
                                         " (no ci.pipeline row read)"))
    if lk["state"] == "held":
        say(f"stalled: the host test lock is held by pid {lk['detail']['pid']} for {lk['detail']['age']}s")
    elif lk["state"] == "unknown":
        say(f"stalled: the host test lock is unknown ({lk['detail']})")
    for r in report["items"]:
        words = r["signals"] + r["unknown"]
        say(f"{r['label']}  {r['state']}" + (f" by {r['claimed_by']}" if r["claimed_by"] else "") +
            f"  {', '.join(words)}")
    say(f"stalled: {len(report['items'])} item(s) with a signal"
        + ("" if report["ops_rows"] is not None else "; the ops rows could not be read"))
    return 0


bl_cli.register("stalled", cmd_stalled, args_stalled,
                help="list claimed or ready items that show a stall signal")
