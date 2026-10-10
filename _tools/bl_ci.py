"""The CI side of backlog.py (kb/_self/backlog.md, red pipeline and Bug intake; kb/_self/tools.md): the pipeline readers
with this module's `run` (`latest_pipeline`, `covered_by_revert`), the failure fingerprint helpers (`normalise_error_line`,
`first_failure`), the red-main bug (`red_bug`, `bug_with_fingerprint`, `add_pipeline`) and the `red-pipeline` and
`intake` commands with the async SessionStart form `hook_intake`.

Standard library only; imports `bl_base`, `bl_intake` (the CI detector and the intake's detectors) and `bl_land` (the
runner of a check), never `backlog`. It registers `red-pipeline` and `intake` with `bl_cli` itself when
imported, and `backlog.py`'s USAGE puts them in the usage order."""
import sys
import threading
from pathlib import Path

import bl_cli
import bl_intake
from bl_base import new_id, run, say, withhold, worker_dir
from bl_base import run_check


# The pipeline reader, the failure fingerprint and the red-main bug are the CI detector's (bl_intake.py); this
# module passes its own `run` and `run_check`, which a test replaces (bl_ci.run, bl_ci.run_check), and keeps the names
# its callers use.
GITLAB_FINISHED = bl_intake.GITLAB_FINISHED
S1_JOBS = bl_intake.S1_JOBS
STATUS_REPRO = list(bl_intake.PIPELINE_REPRO)  # a red-main bug adds --job <its job>
MAIN_PIPELINES = bl_intake.MAIN_PIPELINES
LOG_PREFIX_RE = bl_intake.LOG_PREFIX_RE
failure_fingerprint = bl_intake.failure_fingerprint
names_pipeline = bl_intake.names_pipeline


def normalise_error_line(line):
    """`bl_intake.normalise_error_line` with this module's LOG_PREFIX_RE."""
    return bl_intake.normalise_error_line(line, LOG_PREFIX_RE)


def first_failure(log):
    """`bl_intake.first_failure` with this module's LOG_PREFIX_RE."""
    return bl_intake.first_failure(log, LOG_PREFIX_RE)


def bug_with_fingerprint(bl, fp):
    """The id of an open bug (not done or dropped) whose links carry `fingerprint <fp>`, or None."""
    for iid, it in sorted(bl.items.items()):
        if (it.get("kind") == "bug" and it.get("status") not in ("done", "dropped")
                and f"fingerprint {fp}" in it.get("links", [])):
            return iid
    return None


def add_pipeline(bl, iid, pid):
    """Add `pipeline <pid>` to the links of item `iid` (a bug that already carries its fingerprint) and save it."""
    it = bl.items[iid]
    marker = f"pipeline {pid}"
    if marker not in it.get("links", []):
        it["links"] = list(it.get("links", [])) + [marker]
        bl.save(it)


def latest_pipeline(root, job=None):
    """(pipeline, note): `bl_intake.latest_pipeline` read through this module's `run`."""
    return bl_intake.latest_pipeline(root, job, run)


def covered_by_revert(root, sha):
    """`bl_intake.covered_by_revert` read through this module's `run`."""
    return bl_intake.covered_by_revert(root, sha, run)


def red_bug(pid, sha, sev, jobs=(), url=None, extra="", fingerprint=None, job=None):
    """A red-main bug item (not saved): `bl_intake.pipeline_candidate` written as the item red-pipeline files."""
    return bl_intake.item_of(bl_intake.pipeline_candidate(pid, sha, sev, jobs, url, extra, fingerprint, job),
                             new_id("bug"))


def cmd_red_pipeline(bl, a):
    if not a.status:
        import kbpublic
        run(["git", "fetch", "-q", kbpublic.integration_remote(bl.root), "main"], cwd=bl.root)
    p, note = latest_pipeline(bl.root, getattr(a, "job", None))
    if p is None:
        say(f"red-pipeline: not checked: {note}")
        return 1 if a.status else 0
    unpassed = p.get("unverified") or []
    state = "red" if p["red"] else "unverified" if unpassed else "green"
    why = f": a gate job did not pass: {', '.join(unpassed)}" if state == "unverified" else ""
    if not getattr(a, "job", None):  # the ops row `ci.pipeline`, only when this pipeline's state changed
        try:
            import ql_deliver
            ql_deliver.record_pipeline(p.get("id"), state, p.get("calls"), p.get("sha"))
        except Exception:  # noqa: BLE001 - red-pipeline never fails for its log
            pass
    if a.status:
        say(f"red-pipeline: {p['how']} pipeline {p['id']} of main is {state}{why} ({note})")
        return 0 if state == "green" else 1
    if not p["red"]:
        say(f"red-pipeline: {p['how']} pipeline {p['id']} of main is {state}{why}: nothing to file")
        return 0
    marker = f"pipeline {p['id']}"
    for iid, it in bl.items.items():
        if names_pipeline(it, marker):
            say(f"red-pipeline: {marker} already filed as {bl.label(iid)}")
            return 0
    if covered_by_revert(bl.root, p["sha"]) is not False:
        say(f"red-pipeline: {marker} is covered by an automatic revert (or its history is unreadable): nothing to file")
        return 0
    cand = bl_intake.pipeline_finding(p)  # the CI detector's candidate
    sev = cand.severity
    active = [i for i, it in bl.items.items() if it.get("kind") == "sprint" and it.get("status") == "active"]
    fp = p.get("fingerprint")
    it = bl_intake.item_of(cand, new_id("bug"))
    if sev == "S1" and len(active) == 1:
        it.update(sprint=active[0], status="todo")
    ok, code, _ = run_check(bl.root, it["repro"])
    if ok:
        say(f"red-pipeline: {marker} is green on a second read (repro exit {code}): nothing to file")
        return 0
    dup = bug_with_fingerprint(bl, fp) if fp else None
    if dup:
        add_pipeline(bl, dup, p["id"])
        say(f"red-pipeline: {marker} fails the same way (fingerprint {fp}): added to {bl.label(dup)}")
        return 0
    bl.save(it)
    say(f"red-pipeline: new bug {bl.label(it['id'])}")
    return 0


def cmd_intake(bl, a):
    if a.status is not None and not bl_intake.FP_RE.fullmatch(a.status):
        print(f"intake: {a.status!r} is not a fingerprint (12 hex characters)", file=sys.stderr)
        return 2
    if a.status is not None and a.file:
        print("intake: --status and --file do not go together", file=sys.stderr)
        return 2
    found, failures = bl_intake.collect(bl.root, network=a.network, record=a.status is None)
    for why in failures:
        print(withhold(f"intake: detector failed: {why}"), file=sys.stderr)
    if a.status is not None:
        hit = next((c for c in found if c.fp == a.status), None)
        if hit:
            say(f"intake: {a.status} is still reported by {hit.detector}: {bl_intake.one(hit.title)}")
            return 1
        if failures:
            say(f"intake: {a.status} is not reported, but a detector failed to run")
            return 1
        say(f"intake: {a.status} is no longer reported")
        return 0
    if a.file:
        return bl_intake.file_found(bl, found, failures, say, new_id, withhold)
    new = skipped = 0
    for c in found:
        dup = bl_intake.open_with_fingerprint(bl.items, c.fp) or bl_intake.named_by(bl.items, c)
        for ln in bl_intake.lines(c, bl.label(dup) if dup else None):
            say(ln)
        if dup:
            skipped += 1
            continue
        new += 1
    say(f"intake: {len(found)} candidate(s), {new} new, {skipped} skipped" if found else "intake: no candidates")
    return 1 if failures else 0


INTAKE_HOOK_BUDGET_S = 50  # intake --hook stops waiting for the detectors after this; the hook's own timeout is 60
INTAKE_HOOK_SLOW = {"drift"}  # intake --hook runs these after the other offline detectors: drift runs item checks


def in_worker_worktree(root):
    """True when ROOT is a linked git worktree directly under the project's worktree directory (`worktree_dir`, by
    default `.claude/worktrees/`: a headless worker's): its `.git` is a file, not a directory."""
    p = Path(root).resolve()
    parts = worker_dir()
    return p.parent.parts[-len(parts):] == parts and (p / ".git").is_file()


def hook_intake(bl, a, budget=None):
    """`intake --file --hook`, the async SessionStart form: runs the fast offline detectors first, then the slow ones
    (INTAKE_HOOK_SLOW, on what is left of the budget), then the network ones (only with `--network`), and stops
    waiting after `budget` seconds (default INTAKE_HOOK_BUDGET_S); what the detectors that finished by then found is
    filed, so a slow one costs only its own findings. It writes each new candidate as an uncommitted draft item as
    `--file` does, prints nothing, never commits or pushes, and returns 0 whatever happens. With `--file` in a
    worker's linked worktree (in_worker_worktree) it files nothing and prints one line on stderr saying so: the
    drafts would be untracked files there that `land` refuses."""
    if a.file and in_worker_worktree(bl.root):
        print("intake: files nothing in a worker's worktree (a linked worktree under the worktree directory)", file=sys.stderr)
        return 0
    budget = INTAKE_HOOK_BUDGET_S if budget is None else budget
    names = sorted(bl_intake.DETECTORS, key=lambda n: (n in bl_intake.NETWORK_DETECTORS, n in INTAKE_HOOK_SLOW, n))
    found = []  # candidates of the detectors that finished, in order

    def read():
        for name in names:
            if name in bl_intake.NETWORK_DETECTORS and not a.network:
                continue
            try:
                found.extend(bl_intake.collect(bl.root, only=name, record=True)[0])
            except Exception:  # noqa: BLE001 - a session starts whatever the detectors do
                pass

    t = threading.Thread(target=read, daemon=True)
    t.start()
    t.join(budget)
    if a.file:
        seen = set()
        for c in list(found):
            if c.fp in seen or bl_intake.open_with_fingerprint(bl.items, c.fp) or bl_intake.named_by(bl.items, c):
                continue
            seen.add(c.fp)
            bl.save(bl_intake.item_of(c, new_id(c.kind)))
    return 0


def args_red_pipeline(p):
    p.add_argument("--status", action="store_true")
    p.add_argument("--job", help="read the newest pipeline of main in which this job succeeded or failed on its own account (a red-main bug's repro)")
    p.add_argument("--hook", action="store_true")


def args_intake(p):
    p.add_argument("--file", action="store_true", help="write each new candidate as a draft item outside any sprint")
    p.add_argument("--status", metavar="FINGERPRINT",
                   help="exit 1 while a detector still reports this fingerprint (a filed bug's repro)")
    p.add_argument("--network", action="store_true",
                   help="also run the detectors that call the network (ci: the newest pipeline of main, as red-pipeline reads it)")
    p.add_argument("--hook", action="store_true",
                   help="the async SessionStart form: silent, bounded, exit 0 always; with --file it writes the drafts uncommitted")


bl_cli.register("red-pipeline", cmd_red_pipeline, args_red_pipeline)
bl_cli.register("intake", cmd_intake, args_intake)
