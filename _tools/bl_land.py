"""The landing side of backlog.py (kb/_self/backlog.md, What done refuses, Landing; kb/_self/tools.md): `done`, which runs an
item's checks and records the evidence, `land`, which rebases a worker's branch and runs the steps to the integration
main, `close`, which deletes a finished sprint, and `researched`, the goal research story's check by done's rules;
with what they share: the commits an item's trailers name (`item_commits`, `unlanded_code`, `out_of_scope`), the runner of a check (`run_check`), the worker's worktree
(`live_processes`, `release_worker_worktree`), the landed work/<id> branch (`delete_landed_branch`) and the stuck merge
request line.

Standard library only; imports `bl_base`, `bl_check` (the no-op rules `done` applies), `bl_cli` and `bl_intake` (the
time windows of the detectors that `precheck` names) and never `backlog`. The branch `land` expects sync to open for code commits is named by
`kg_lane.lane_plan`, the one helper sync uses. It registers `done`, `researched`, `land`, `merge` and `close` with `bl_cli` itself when
imported (`backlog.py`'s USAGE puts each in its usage position), and `host-check` and the repro rules there call `run_check` from
here."""
import argparse, datetime, hashlib, importlib, json, os, re, shlex, shutil, subprocess, sys, time
from collections import namedtuple
from pathlib import Path

import bl_cli
import bl_intake
from bl_base import (  # run_check lives below bl_land, so bl_ci reaches it without bl_land (ST-ufpxla7r)
    ANSI_RE, Backlog, REF_HEADER, WORKSPACE, colourless_env, run_check, Refused, commit_written, external_description,
    clause_commands, git, goal_clauses, id_re, in_scope, item_file, item_repos, line, main_worktree_spool, need, rel_dir,
    repositories, run, say, scope, setting, split_touch, waits, worker_dir,
)
from bl_check import HOST_BOUND_GATE, host_bound_accepted, is_test_run, noop_output, trivial_command


def item_commits(root, ids):
    """{commit: [paths]} of the commits on HEAD whose KB-Work trailer names any of the ids, oldest first. Only work
    counts: a commit that changes nothing but item files (a claim, a gate, a sprint's plan) is not the item's work."""
    log = git(root, "log", "HEAD", "--reverse", "--no-merges",
              "--format=%H%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)%x1e")
    out = {}
    for rec in log.split("\x1e"):
        sha, _, vals = rec.strip().partition("\x00")
        if sha and set(id_re().findall(vals)) & set(ids):
            paths = [p for p in git(root, "show", "--no-renames", "--name-only", "--format=", sha).splitlines() if p]
            if any(not item_file(p) for p in paths):
                out[sha] = paths
    return out


def unlanded_code(root, ids):
    """(short hashes, remote, owners) of the code-lane KB-Work commits on HEAD naming any of the ids that are not
    ancestors of refs/remotes/<integration>/main as last fetched; the hashes are [] when all are, and ["(no such ref)"]
    when the ref is missing and there is a code-lane commit. The owners are the ids the late commits name, first seen
    first, for the code/<id> branches sync opened. Content-lane commits never count; a commit's paths are
    kblane.commit_paths', which leaves out a .gitattributes change confined to the pinned block. A project whose
    `lane_module` is empty has no code lane: every commit is content, and nothing is late."""
    import kbpublic
    remote = kbpublic.integration_remote(root)
    if not setting("lane_module"):
        return [], remote, []
    kblane = importlib.import_module(setting("lane_module"))
    code = []
    for sha, paths in item_commits(root, ids).items():
        lane_paths = kblane.commit_paths(root, sha)
        if kblane.paths_lane(paths if lane_paths is None else lane_paths)[0] == kblane.CODE:
            code.append(sha)
    if not code:
        return [], remote, []
    ref = f"refs/remotes/{remote}/main"
    if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode:
        return ["(no such ref)"], remote, []
    late = [sha for sha in code
            if subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=root,
                              capture_output=True).returncode]
    owners = []
    for sha in late:
        named = id_re().findall(git(root, "log", "-1", "--format=%(trailers:key=KB-Work,valueonly,separator=%x2C)", sha))
        owners += [i for i in named if i in ids and i not in owners][:1]
    return [sha[:10] for sha in late], remote, owners


def sync_code_branch(root, upstream, owners, iid):
    """The code/<id> branch sync --push opens for the range UPSTREAM..HEAD, named by kg_lane.lane_plan, the one helper
    sync uses; the late commits' first owner (else the item's own id) when git cannot say."""
    import kg_lane
    _, branch = kg_lane.lane_plan(str(root), upstream, "HEAD")
    return branch or "code/" + (owners[0] if owners else iid)


def blob_id(root, rev, path):
    p = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{rev}:{path}"], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip() if p.returncode == 0 else None


def out_of_scope(root, commits, globs):
    """[(commit, path)] of the paths outside the globs that the item's commits changed and HEAD still has changed:
    a later commit that restored a file (a revert) clears it."""
    first = {}
    for sha, paths in commits.items():
        for p in paths:
            if not in_scope(p, globs):
                first.setdefault(p, sha)
    return [(sha, p) for p, sha in first.items() if blob_id(root, f"{sha}^", p) != blob_id(root, "HEAD", p)]


def own_globs(globs):
    """GLOBS (touches) as they read in the workspace's own tree: with a `repositories` map, `workspace/<glob>` without
    its prefix and the repositories' touches left out (their files are in other repositories, which land reads
    through their merge requests); the globs as given in a project with no map."""
    out = []
    for g in globs:
        repo, rest = split_touch(g)
        if repo is None:
            out.append(g)
        elif repo == WORKSPACE:
            out.append(rest)
    return out


def stale_since(root, commits):
    """The revision done's docs check compares with: the merge base of HEAD and the integration main as last fetched
    (the range land's step stale reads after its rebase), else, with no such ref or no common history, the parent of
    the oldest of COMMITS (the item's KB-Work commits, oldest first); None when neither exists."""
    import kbpublic
    p = subprocess.run(["git", "merge-base", "HEAD", f"refs/remotes/{kbpublic.integration_remote(root)}/main"],
                       cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode == 0 and p.stdout.strip():
        return p.stdout.strip()
    first = next(iter(commits), None)
    if first is None:
        return None
    p = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{first}^"], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None


def stale_docs(root, commits):
    """([(doc, [the item's changed files it describes])], since): the kb/_self docs `selfdoc.py stale --since SINCE`
    lists (stale_since: a doc edited in the range, or named in a `Self-Reviewed:` trailer of a commit in it, is up to
    date, as at the sync gate) that describe a file the item's COMMITS ({commit: [paths]}) changed. Another change's
    stale doc in the range is not the item's; a landed item's commits are below the merge base, so they are not read
    again."""
    import selfdoc
    since = stale_since(root, commits)
    if since is None:
        return [], None
    mine = {p for paths in commits.values() for p in paths}
    out = []
    for doc, _, hit in selfdoc.stale(root=Path(root), since=since):
        own = [p for p in hit if p in mine]
        if own:
            out.append((doc, own))
    return out, since


def noop_proof(bl, iid, passed):
    """done's rule for checks that passed ([(check, output)]) without doing their work: one that runs no test or tool
    code is warned of; one whose output says it did nothing in this clone (noop_output) is warned of too, and refuses
    done unless another passing check runs tests and did its work, or the operator accepted the host-bound proof
    (gate HOST_BOUND_GATE answered accept or approve)."""
    noops = []
    for c, out in passed:
        why = noop_output(out)
        if why:
            noops.append((c, why))
        why = why or trivial_command(c["run"])
        if why:
            say(f"warning: {shlex.join(c['run'])} passed without doing its work in this clone: {why}")
    proven = [c for c, out in passed if is_test_run(c["run"]) and not noop_output(out)]
    if not noops or proven or host_bound_accepted(bl.items[iid]):
        return
    c, why = noops[0]
    raise Refused(f"{bl.label(iid)} is not done: {shlex.join(c['run'])} passed without doing its work in this clone "
                  f"({why}), and no check that runs tests proves the fix. Name one: backlog.py set {iid} "
                  "--add-check CMD, a check that does its work in this clone (a tool run on a planted input); or ask the operator to "
                  f"accept the host-bound proof: backlog.py gate add {iid} --id {HOST_BOUND_GATE} --question "
                  "'Accept a proof that does nothing in this clone?' --option accept --option add-test "
                  f"--recommendation add-test, answered with backlog.py answer {iid} {HOST_BOUND_GATE} --answer "
                  "accept --by operator")


def check_token(run):
    """A check's name as an ops token, never its text: the -k selector of a test run, else the script it runs, else
    its program (`done.refused`'s `checks`)."""
    run = [str(x) for x in run]
    name = run[run.index("-k") + 1] if "-k" in run[:-1] else next(
        (Path(x).stem for x in run[1:] if x.endswith(".py")), Path(run[0]).stem if run else "check")
    tok = ops_token(name)
    return tok if tok[:1].isalpha() else f"c-{tok}"[:40]


def refuse_done(iid, t0, reasons, message, checks=()):
    """Append the `done.refused` ops row (the item, its closed reason classes, the failed checks' names and the
    milliseconds spent), then refuse with MESSAGE. Best effort: the row never changes the refusal."""
    try:
        from ql_deliver import ops_row
        fields = {"item": iid, "reasons": sorted(set(reasons)), "ms": int((time.monotonic() - t0) * 1000)}
        if checks:
            fields["checks"] = [check_token(c) for c in checks][:20]
        ops_row("done.refused", **fields)
    except Exception:  # noqa: BLE001 - a refusal never fails for its log
        pass
    raise Refused(message)


EMPTY_SELECTION = re.compile(r"^tests\.py: the selection .* collects no test in ", re.M)  # tests.py's refusal, exit 2


def selected_nothing(code, out):
    """True when a test run selected no tests: tests.py's refusal (exit 2 and its `collects no test` line), or a pytest
    run's own (exit 5 with everything deselected, or no tests ran)."""
    return bool((code == 2 and EMPTY_SELECTION.search(out)) or re.search(r"\bno tests ran\b", out)
                or (code == 5 and re.search(r"\bdeselected\b", out)))


def gone_checks(it):
    """The commands (argument lists) of a done item's checks that an earlier rerun found gone: its evidence's `gone`."""
    ev = it.get("evidence")
    return [list(g) for g in ev.get("gone", []) if isinstance(g, list)] if isinstance(ev, dict) else []


def rerun_done_checks(bl, sid, record=True):
    """[(item id, check, exit code)] of each check and bug repro of the sprint's done items, the review story left
    out, that fails when run once more on the checkout as it is (the sprint's tip): a check that passed when its item
    was done and fails now (another item broke it, or it never passed on main) is named before the sprint closes. One
    whose test run selects no test (selected_nothing: a later change deleted the test it names) is said as `gone` and
    not counted, since a done item's check cannot be repointed to a run that passes; a new item's done still refuses
    such a selection as malformed (land_checks). A gone check is found once per sprint: it is recorded in its item's
    evidence (`gone`, saved: the review's done commits it with its own record, close names it in its summary) and is
    not run again at the sprint's next landing. RECORD false (a `done --dry-run`) writes no evidence, so the run that
    commits finds the check gone again and commits its record with the review's."""
    out = []
    for i in sorted(bl.sprint_items(sid)):
        it = bl.items[i]
        if it.get("status") != "done" or it.get("review"):
            continue
        gone = gone_checks(it)
        for c in list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else []):
            if [str(x) for x in c["run"]] in gone:
                say(f"gone rerun {i}: {shlex.join(c['run'])} was found gone at an earlier landing; not run again")
                continue
            ok, code, text = run_check(bl.root, c)
            if not ok and selected_nothing(code, text):
                say(f"gone rerun {i}: {shlex.join(c['run'])} selects no test (a later change deleted it); not counted")
                if record:
                    gone.append([str(x) for x in c["run"]])
                    it["evidence"] = {**(it["evidence"] if isinstance(it.get("evidence"), dict) else {}), "gone": gone}
                    bl.save(it)
                continue
            say(f"{'ok  ' if ok else 'FAIL'} rerun {i}: {shlex.join(c['run'])}")
            if not ok:
                out.append((i, c, code))
    return out


# a goal research story that needs no outside facts is done with no work commit when its notes say why: the notes hold
# `No outside facts: <reason>` at their start, on a line of its own or after a sentence's end (`set --add-notes` joins
# notes with a space)
NO_OUTSIDE_FACTS = re.compile(r"(?:^|(?<=[.;!?]) |\n)No outside facts:[ \t]*\S")


def research_without_facts(it):
    """True for a story that is the sprint's goal research and whose notes say `No outside facts: <reason>`."""
    return bool(it.get("kind") == "story" and it.get("goal_research") and NO_OUTSIDE_FACTS.search(it.get("notes") or ""))


def cmd_researched(bl, a):
    """The goal research story's check (bl_base.RESEARCH_CHECKS): exit 0 once its research is written, by done's own
    rules, a work commit on HEAD naming it or one of its descendants (`item_commits`) or its notes' `No outside facts:
    <reason>` (`research_without_facts`); exit 1 before. Read-only."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    if research_without_facts(it):
        say(f"researched {bl.label(iid)}: its notes say No outside facts")
        return 0
    commits = item_commits(bl.root, [iid] + bl.descendants(iid))
    if commits:
        say(f"researched {bl.label(iid)}: {len(commits)} work commit(s), the first {next(iter(commits))[:10]}")
        return 0
    say(f"not researched {bl.label(iid)}: no commit on HEAD carries KB-Work: {iid} and changes a file other than item "
        "files, and its notes hold no `No outside facts: <reason>`")
    return 1


def cmd_done(bl, a):
    t0 = time.monotonic()
    iid = need(bl, a.id)
    it = bl.items[iid]
    kind = it["kind"]
    if kind == "sprint":
        raise Refused("a sprint is closed with backlog.py close")
    reasons = []
    if kind == "epic":
        problems = [f"open child {line(bl, c)}" for c in bl.children(iid)
                    if bl.items[c].get("status") not in ("done", "dropped")]
        reasons += ["children-open"] * bool(problems)
    else:
        problems = [x for x in waits(bl, iid, any_sprint=True)
                    if not x.startswith(("status doing", "not in an active sprint"))]
        reasons += ["not-ready"] * bool(problems)
    if it.get("status") not in ("todo", "doing", "draft" if kind == "epic" else "todo"):
        problems.append(f"status {it.get('status')}")
        reasons.append("status")
    if it.get("review"):
        sp = bl.sprint_of(iid)
        for s in bl.sprint_items(sp) + [sp]:
            for g in bl.items[s].get("gates", []):
                if g.get("by") == "agent":
                    problems.append(f"provisional answer to confirm: {bl.label(s)} gate {g['id']}: {g['answer']}")
                    reasons.append("provisional-answer")
    globs = scope(bl, iid)
    repos = getattr(a, "repositories", None)  # land's {repository: {request, commit}}: the work merged in each
    if not globs and kind != "epic" and not it.get("review"):  # start's rule, for an item filed into a running sprint
        problems.append("no touches of its own or under it: a work item needs a scope (backlog.py set ID --touch "
                        "GLOB, or tasks that have touches), which start requires of every work item")
        reasons.append("not-ready")
    if globs:
        mine = own_globs(globs)  # this tree's: a multi-repository item's other touches are in its repositories
        dirty = [ln[3:] for ln in git(bl.root, "status", "--porcelain").splitlines()
                 if in_scope(ln[3:].strip('"'), mine) and not in_scope(ln[3:].strip('"'), ())]
        if dirty:
            problems.append("uncommitted changes in scope (checks run on HEAD): " + ", ".join(dirty[:5]))
            reasons.append("uncommitted")
        family = [iid] + bl.descendants(iid)
        if (it.get("touches") and not research_without_facts(it) and not repos
                and not item_commits(bl.root, [iid] + bl.descendants(iid))):
            reasons.append("no-work-commit")
            problems.append(f"no commit on HEAD carries the trailer KB-Work: {iid} or one of its descendants' ids "
                            "and changes a file other than item files (git reads a trailer only in the message's last "
                            "paragraph, with the others; a claim or planning commit is not the work; a goal research story "
                            "needing no outside facts says so in its notes: No outside facts: <reason>)"
                            + ("; the work of an item with `repos` is merged in its repositories, which land reads "
                               "through their merge requests: run land" if item_repos(it) else ""))
        late, remote, owners = unlanded_code(bl.root, family)
        if late:
            reasons.append("unlanded-code")
        if late == ["(no such ref)"]:
            problems.append(f"code commits of the item, and refs/remotes/{remote}/main is not fetched: fetch {remote}, "
                            "then run done again")
        elif late:
            branch = sync_code_branch(bl.root, f"refs/remotes/{remote}/main", owners, iid)
            problems.append(f"code commit(s) {', '.join(late)} are not on {remote}/main: merge the merge request sync "
                            f"opened for them (branch {branch}, named for the first KB-Work id of the range sync "
                            f"pushes), fetch {remote} and run done again")
        commits = item_commits(bl.root, family)
        for sha, path in out_of_scope(bl.root, commits, mine):
            problems.append(f"commit {sha[:10]} changed {path}, outside touches (revert it, or widen touches)")
            reasons.append("outside-touches")
        try:
            behind, since = stale_docs(bl.root, commits)
        except Exception as e:  # noqa: BLE001 - selfdoc's own error (a git failure, an unreadable map) is said, not raised
            behind, since = [], None
            say(f"warning: the docs check could not run: {e}")
        if behind:
            reasons.append("stale-docs")
            problems.append(f"stale-docs: kb/_self docs older than the item's change (python3 _tools/selfdoc.py stale --since "
                            f"{since[:10]}): " + "; ".join(f"{doc} is older than {', '.join(own[:8])}"
                                                           for doc, own in behind)
                            + " (edit each in the item's touches, or name one read and found still correct in the "
                              "Self-Reviewed: trailer of a commit of the item)")
    if problems:
        refuse_done(iid, t0, reasons, f"{bl.label(iid)} is not done:\n  " + "\n  ".join(problems))
    checks = list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else [])
    results, failed, passed = [], [], []
    for c in checks:
        ok, code, out = run_check(bl.root, c)
        results.append({"run": c["run"], "exit": code, "sha256": hashlib.sha256(out.encode()).hexdigest()[:16]})
        say(f"{'ok  ' if ok else 'FAIL'} exit={code} {shlex.join(c['run'])}")
        if not ok:
            failed.append((c, code, out))
        else:
            passed.append((c, out))
    if failed:
        for c, code, out in failed:
            tail = "\n".join(out.strip().splitlines()[-8:])
            say(f"--- {shlex.join(c['run'])} (want exit {c.get('exit', 0)}"
                + (f", output matching {c['match']!r}" if c.get("match") else "") + f"):\n{tail}")
        refuse_done(iid, t0, ["check-failed"], f"{bl.label(iid)} is not done: {len(failed)} check(s) failed",
                    [c["run"] for c, _, _ in failed])
    try:
        noop_proof(bl, iid, passed)
    except Refused as e:
        refuse_done(iid, t0, ["no-op-proof"], str(e), [c["run"] for c, out in passed if noop_output(out)])
    if it.get("review"):  # every done item's proof, once more on the sprint's tip: one that fails here does not close
        stale = rerun_done_checks(bl, bl.sprint_of(iid), record=not a.dry_run)
        if stale:  # the gone checks it recorded are committed first, so the next landing does not run them again
            if not a.dry_run:
                commit_written(bl, a, "record gone checks for", iid)
            refuse_done(iid, t0, ["check-failed"], f"{bl.label(iid)} is not done: {len(stale)} check(s) of done items "
                        "fail on the sprint's tip:\n  " + "\n  ".join(f"{bl.label(i)}: `{shlex.join(c['run'])}` exits "
                                                                     f"{code}" for i, c, code in stale)
                        + "\nreopen each (backlog.py reopen ID --why ...) and fix it, or fix its check",
                        [c["run"] for _, c, _ in stale])
    if a.dry_run:
        say(f"{bl.label(iid)} would be done")
        return 0
    head = git(bl.root, "rev-parse", "HEAD").strip()
    it.update(status="done", evidence={"commit": head, "checks": results, **({"repositories": repos} if repos else {})})
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"done {bl.label(iid)} at {head[:10]}" + ("" if a.commit else f"; commit this with the trailer KB-Work: {iid}"))
    commit_written(bl, a, "done", iid)
    return 0


# land: the steps after a worker's branch comes back, each a command run from the clone's root with this interpreter
# each step's command is a project setting (backlog.json); an empty one is a step the project does not have
def land_stale():
    return ("stale", setting("land_stale"))  # + the integration main; seconds, so it runs first


def land_eval():
    return ("rag.py eval", setting("land_eval"))


def land_lint():
    """A landing that changes articles and not _tools/ runs it on those articles' paths only."""
    return ("lint", setting("land_lint"))


def land_heavy():
    """The steps run once, when the landing changes _tools/; the full tests.py is no step here: it runs once at the
    sprint's review story."""
    return tuple(step for step in (land_eval(), land_lint()) if step[1])


def land_push():
    """The push step: the project's `land_push` command, named by its program (`kbgit.py sync --push` for the kb)."""
    argv = setting("land_push")
    return (" ".join([Path(argv[0]).name, *argv[1:]]), argv)


LAND_TAIL = 30  # output lines shown of a step that passed (sync's report is shown whole)


# land's ops rows (kb/_self/querylog.md, ops events): a `land.step` row per step, a `land.end` row at every end, and
# after a landing that exited 0 the line `ops_work_rows` gives when the item's work rows are not in the committed work
# sidecars (late, undelivered or missing). Best effort: nothing here changes land's exit or output beyond that line.
LAND_OPS = {"step": None, "t": 0.0, "exit": 0, "lane": None, "item": None}


def ops_token(label):
    """A step label as an ops token: lower case, every run of other characters one `-`, at most 40 characters."""
    return re.sub(r"[^a-z0-9_.]+", "-", label.lower()).strip("-")[:40] or "step"


def ops_write(**fields):
    """Append a land ops row (`ql_deliver.ops_row`: nothing inside a test run, so a fixture's landing never reaches the
    clone's spool); a landing never fails for its log."""
    try:
        from ql_deliver import ops_row
        ops_row(fields.pop("event"), **fields)
    except Exception:  # noqa: BLE001 - a landing never fails for its log
        pass


def ops_close(code=0):
    """Write the row of the step that is open (if one is), with CODE as its exit."""
    if LAND_OPS["step"] and LAND_OPS["item"]:
        ops_write(event="land.step", item=LAND_OPS["item"], step=LAND_OPS["step"], exit=code,
                  ms=int((time.monotonic() - LAND_OPS["t"]) * 1000))
    LAND_OPS["step"] = None


def ops_mark(label):
    """The next step starts: the one before it passed."""
    ops_close()
    LAND_OPS.update(step=ops_token(label), t=time.monotonic(), exit=1)


def ops_work_rows(root, iid):
    """[line] the landing of IID says about its work rows, none when nothing is amiss. A line of the committed work
    sidecars (`bl_cost.cost_lines`) that names the item or a descendant of it ends it: the rows are delivered. Else
    the clone's spool and the main worktree's (`bl_cost.spool_dirs`; read only: a session started in the main checkout
    that orchestrates a clone writes its rows there) and the local store beside each (`<spool>/../store`, where distill
    writes the sidecars before `querylog.py apply --push` delivers them) are read:
    - a work sidecar of a local store that names the item and that neither the checkout's `kb/_querylog` nor the
      integration main holds: `warning: ... undelivered`, naming the store and its count of sidecars (a session end
      left it unpushed), and nothing more;
    - a worker's row of the item in a spool, a `branch` row (the row that opens a headless worker's window,
      `ql_capture.BRANCH_ACTION`) or an `agent-start` or `agent-stop` row (`ql_capture.AGENT_ACTIONS`: a worker
      started with the Agent tool runs inside the orchestrator's session and writes those, never a `branch` row), is
      no warning: its session is open or not distilled yet, so its rows are late, said as a `land:` line naming the
      session and its state;
    - none of these: `warning: ... missing`, the line a worker that ran without the capture hooks leaves. The
      orchestrator's own `claim`, `done` and `release` rows are no worker's: it claims every item it delegates, so its
      row would always be met.
    [] too when capture is off, no spool directory exists (and no store holds an undelivered sidecar) or
    anything cannot be read."""
    try:
        import bl_cost, kbpublic, ql_capture, ql_distill, ql_store
        dirs = bl_cost.spool_dirs(root)
        if not dirs:
            return []
        ids = {iid, *Backlog(root).descendants(iid)}
        if bl_cost.cost_lines(root, ids)[0]:
            return []
        remote = kbpublic.integration_remote(root)
        main_ref = f"refs/remotes/{remote}/main:kb/_querylog"
        stores = [d.parent / "store" for d in dirs]
        late = []
        for store in stores:
            held = []
            for p in ql_store.work_files(store):
                rel = p.relative_to(store).as_posix()
                if (Path(root) / "kb" / "_querylog" / rel).is_file() or subprocess.run(
                        ["git", "cat-file", "-e", f"{main_ref}/{rel}"], cwd=root, capture_output=True).returncode == 0:
                    continue
                try:
                    named = any(bl_cost.cost_row_of(p.stem, w, ids, False) for _, w in ql_store.load_run(p)[1:])
                except (OSError, ValueError):
                    continue
                if named:
                    held.append(p.name)
            if held:
                return [f"warning: {iid} landed with no work rows on {remote}/main (undelivered): {store} holds "
                        f"{len(held)} work sidecar(s) naming it that {remote}/main lacks, a session end left the "
                        f"store unpushed (`python3 _tools/querylog.py apply --push` delivers it)"]
        spools = [d for d in dirs if d.is_dir()]
        if not spools:
            return []
        worker_actions = (ql_capture.BRANCH_ACTION, *ql_capture.AGENT_ACTIONS)
        for d in spools:
            for sid, s in sorted(ql_distill.read_spool(d, time.time())[0].items()):
                if any(r.get("surface") == "work" and r.get("item") in ids and r.get("action") in worker_actions
                       for r in s["rows"]):
                    late.append(f"session {sid[:8]} of it is {'closed and not distilled' if s['closed'] else 'still open'}"
                                f" in {d}")
        if late:
            return [f"land: {iid}'s work rows are late: {'; '.join(late)}; `backlog.py cost` shows its figures once "
                    "the session has ended and distill has run"]
        where = ", ".join(str(d) for d in spools)
        return [f"warning: {iid} landed with no work rows (missing): no worker session of it left a branch, "
                f"agent-start or agent-stop row in {where} and no committed work sidecar names it (a worker started "
                "without the capture hooks?)"]
    except Exception:  # noqa: BLE001
        return []


def ops_land(handler):
    """Wrap `cmd_land`: the open step's row and the `land.end` row at every end, and the lines `ops_work_rows` gives
    after a run that returned 0."""
    def wrapped(bl, a):
        LAND_OPS.update(step=None, exit=1, lane=None, item=getattr(a, "id", None))
        t0, done = time.monotonic(), False
        try:
            code = handler(bl, a)
            done = code == 0
            if done:
                for text in ops_work_rows(bl.root, a.id):
                    say(text)
            return code
        finally:
            ops_close(0 if done else LAND_OPS["exit"])
            ops_write(event="land.end", item=LAND_OPS["item"], exit=0 if done else 1,
                      ms=int((time.monotonic() - t0) * 1000), lane=LAND_OPS["lane"])
    wrapped.__doc__ = handler.__doc__
    return wrapped


def land_stop(step, why):
    return Refused(f"land stopped at step {step}: {why}")


def land_run(root, step, argv, whole=False, program=False):
    """Run one landing step; its output (the tail of it, unless WHOLE or it failed) goes through say(). The steps
    are Python scripts run under this interpreter; with PROGRAM an ARGV whose first element does not end in `.py` is
    the program to run itself (the push step's `git push ...`)."""
    say(f"land: {step}")
    ops_mark(step)
    own = not program or argv[0].endswith(".py")
    try:
        p = subprocess.run([sys.executable, *argv] if own else argv, cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=colourless_env())
        code, out = p.returncode, ANSI_RE.sub("", (p.stdout or "") + (p.stderr or "")).rstrip()
    except OSError as e:
        code, out = None, f"cannot start: {e}"
    lines = out.splitlines()
    shown = lines if whole or code else lines[-LAND_TAIL:]
    if shown:
        say("\n".join(shown))
    LAND_OPS["exit"] = code if isinstance(code, int) else 1
    if code != 0:
        raise land_stop(step, f"{'python3 ' if own else ''}{shlex.join(argv)} exited {code}")


def land_git_network(root, step, *args):
    """A git network call (fetch, push, ls-remote) with the bounded wait of kg_lock.run_git_bounded; a timeout
    stops the land at STEP, the main lock released by the block it leaves. Returns the CompletedProcess."""
    import kg_lock
    try:
        return kg_lock.run_git_bounded(args, root, step)
    except kg_lock.GitNetworkTimeout as e:
        raise land_stop(step, str(e)) from None


def land_git(root, step, *args):
    if args and args[0] in ("fetch", "push", "ls-remote"):
        p = land_git_network(root, step, *args)
    else:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise land_stop(step, f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def has_ref(root, ref):
    return subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode == 0


def checked_out_elsewhere(root, branch):
    """(path, lock reason or None) of another worktree that has BRANCH checked out, or None (git rebase cannot check
    it out here). A locked worktree with no reason has the reason ""."""
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    for block in git(root, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("worktree ") or f"branch refs/heads/{branch}" not in lines:
            continue
        path = Path(lines[0][len("worktree "):]).resolve()
        if path != here:
            lock = next((ln[len("locked "):] for ln in lines if ln == "locked" or ln.startswith("locked ")), None)
            return path, lock
    return None


# the lock Claude Code puts on a subagent's worktree, which outlives the agent when it left background work running
WORKER_LOCK = "claude agent"
WORKER_NAME = "agent-"  # how the Agent tool names a worker's isolation worktree: an unlocked one is removed only so
WORK_PREFIX = "work/"  # the local branch a worker commits on: land deletes it once it has landed
AGENT_BRANCH = "worktree-"  # + the worktree's name: the branch the Agent tool made the worker's worktree on


def live_processes(path):
    """([(pid, command)], None) of the processes whose working directory is PATH or under it, or (None, why) when this
    host gives no way to tell: Linux reads /proc/<pid>/cwd, other POSIX hosts (macOS) ask `lsof -d cwd` for every
    process's working directory; Windows exposes no process's working directory to the standard library, so it is
    never listed there (release_worker_worktree tries held_by_process instead). Never signals a process."""
    target = os.path.realpath(path)

    def inside(cwd):
        return cwd == target or cwd.startswith(target.rstrip(os.sep) + os.sep)

    if os.name == "nt":
        return None, "Windows does not expose a process's working directory"
    proc = Path("/proc")
    if (proc / "self" / "cwd").exists():
        out = []
        for d in proc.iterdir():
            if not d.name.isdigit():
                continue
            try:
                cwd = os.readlink(d / "cwd")
                comm = (d / "comm").read_text(encoding="utf-8", errors="replace").strip()
            except OSError:  # gone, or another user's
                continue
            if inside(cwd):
                out.append((int(d.name), comm))
        return sorted(out), None
    lsof = shutil.which("lsof")
    if not lsof:
        return None, "no /proc and no lsof on this host"
    try:
        p = subprocess.run([lsof, "-n", "-P", "-w", "-d", "cwd", "-Fpcn"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"lsof failed: {e}"
    out, pid, comm, seen = [], None, "", False
    for ln in p.stdout.splitlines():
        if ln.startswith("p") and ln[1:].isdigit():
            pid, comm, seen = int(ln[1:]), "", True
        elif ln.startswith("c"):
            comm = ln[1:]
        elif ln.startswith("n") and pid is not None and inside(ln[1:]):
            out.append((pid, comm))
    if not seen:  # lsof lists at least itself: nothing read means it could not look
        return None, f"lsof listed no process (exit {p.returncode})"
    return sorted(set(out)), None


HOOK_POLL_S = 1  # seconds between two looks at a worktree's processes while land waits for a session's end hook


def wait_for_hooks(path, procs, root=None, wait=None, poll=HOOK_POLL_S, clock=time.monotonic, sleep=time.sleep):
    """([(pid, command)] still there, seconds waited, pids of the session-end hooks seen): of the processes
    live_processes found in the worktree PATH (PROCS), once none is left or after at most WAIT seconds (default
    `bl_procs.HOOK_GRACE_S`). A finished worker's session-end hook (the querylog.py distill its SessionEnd starts
    detached, its parent gone from the start) runs for seconds after the session exits, so only a process whose parent
    is gone is waited for; one whose parent lives is a session's own work, and a host that cannot read the process
    table is not waited on. A hook is told by the file its standard output is (`bl_procs.hook_pids`), never by a
    command line. Never signals a process."""
    import bl_procs
    wait = bl_procs.HOOK_GRACE_S if wait is None else wait
    start = clock()
    hooks = set()
    while procs:
        tab = bl_procs.process_table()
        if tab is None or any(pid in tab and not bl_procs.orphaned(tab, pid) for pid, _ in procs):
            break
        hooks |= bl_procs.hook_pids(root or path, [pid for pid, _ in procs])
        if clock() - start >= wait:
            break
        sleep(poll)
        again, _ = live_processes(path)
        procs = again or []
    return procs, max(0, int(clock() - start)), hooks


PROBE_SUFFIX = ".land-probe"  # + pid: the sibling name held_by_process renames a worktree to and back


def held_by_process(path):
    """Why the directory PATH cannot be moved, or None once it was renamed to a sibling and back: Windows locks a
    process's current directory while it runs ("That prevents the directory from being deleted, moved, or renamed",
    SetCurrentDirectory), and a file a process holds open, so a refused rename tells what live_processes cannot list
    there. On POSIX hosts the rename succeeds whatever runs there, so it proves nothing beyond the path being movable."""
    probe = path.with_name(f"{path.name}{PROBE_SUFFIX}-{os.getpid()}")
    if os.path.lexists(probe):
        return f"its probe name {probe.name} is taken"
    try:
        os.rename(path, probe)
    except OSError as e:
        return f"{type(e).__name__}: {e.strerror or e}"
    try:
        os.rename(probe, path)
    except OSError as e:
        return f"it was renamed to {probe} and could not be renamed back ({e.strerror or e}): rename it back by hand"
    return None


def worker_dirs(root):
    """The .claude/worktrees/ directory whose worktrees are the workers of the clone land runs in ROOT, as a set: the
    one of the toplevel there (`git rev-parse --show-toplevel`: a linked worktree is its own clone)."""
    top = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    return {top.joinpath(*worker_dir()).resolve()}


def main_worker_dir(root):
    """The .claude/worktrees/ directory of the main checkout the clone land runs in ROOT is a linked worktree of (the
    Agent tool makes its workers there, whichever worktree its session runs in), or None when ROOT is the main
    checkout itself or the repository has no working tree. worker_dirs, which tidy and close read, never holds it."""
    code, out, _ = run(["git", "rev-parse", "--git-common-dir"], cwd=root)
    if code or not out.strip():
        return None
    common = Path(root, out.strip()).resolve()
    if common.name != ".git":
        return None
    main = common.parent
    top = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    return None if main == top else main.joinpath(*worker_dir()).resolve()


def detached_workers(root, branch):
    """[(path, lock reason or None)] of the worktrees named as the Agent tool names a worker's (WORKER_NAME) that
    are detached at the tip of BRANCH, other than the one land runs in: a worker that detached to free the branch."""
    tip = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/heads/{branch}"], cwd=root,
                         capture_output=True, text=True).stdout.strip()
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    out = []
    for block in git(root, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.strip().splitlines()
        if not tip or not lines or not lines[0].startswith("worktree ") or "detached" not in lines \
                or f"HEAD {tip}" not in lines:
            continue
        path = Path(lines[0][len("worktree "):]).resolve()
        if path != here and path.name.startswith(WORKER_NAME):
            lock = next((ln[len("locked "):] for ln in lines if ln == "locked" or ln.startswith("locked ")), None)
            out.append((path, lock))
    return out


def intake_draft_re():
    """An untracked item file of the intake, in `git status --porcelain` form."""
    return re.compile(r"\?\? (" + re.escape(rel_dir()) + r"/[^/\"]+\.json)")


def intake_drafts(path, status_lines, branch=None):
    """[relative path] of the untracked kb/_self/backlog/*.json files in `git status --porcelain -uall` STATUS_LINES of
    the worktree PATH that no commit of BRANCH (or of the worktree's HEAD) names: the drafts the SessionStart intake
    hook files (`backlog.py intake --file --hook`); any other line (modified, staged, another untracked file) is not one."""
    found = []
    for line in status_lines:
        m = intake_draft_re().fullmatch(line)
        if not m:
            continue
        named = subprocess.run(["git", "log", "-1", "--format=%H", branch or "HEAD", "--", m.group(1)], cwd=path,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not named.returncode and not named.stdout.strip():
            found.append(m.group(1))
    return found


def own_checkout_drafts(root, status_lines):
    """[relative path] of the intake drafts of the checkout ROOT that land runs in, when `git status --porcelain -uall`
    STATUS_LINES hold nothing else: each an untracked kb/_self/backlog/*.json that no commit of HEAD names and whose
    links carry a `fingerprint` and a `detector` (a filed intake candidate, not a hand-filed item). One other line,
    or one untracked item file that is no such draft, makes it [], so nothing is moved and `clean tree` refuses."""
    drafts = intake_drafts(root, status_lines)
    if len(drafts) < len(status_lines):
        return []
    for rel in drafts:
        try:
            links = json.loads((Path(root) / rel).read_text(encoding="utf-8")).get("links")
        except (OSError, ValueError, AttributeError):
            return []
        links = [x for x in links if isinstance(x, str)] if isinstance(links, list) else []
        if not (bl_intake.detector_of({"links": links}) and any(
                x.startswith(bl_intake.FP_LINK) and bl_intake.FP_RE.fullmatch(x[len(bl_intake.FP_LINK):])
                for x in links)):
            return []
    return drafts


def set_aside_drafts(root, path, drafts):
    """Move the DRAFTS (relative paths) of the worktree PATH, a worker's or the checkout land runs in, to
    `bl_intake.INTAKE_ASIDE` of ROOT, under the worktree's name, never over a file there. Returns [(source,
    destination)] of those moved."""
    moved = []
    for rel in drafts:
        src = Path(path) / rel
        dest = Path(root).joinpath(*bl_intake.INTAKE_ASIDE, Path(path).name, src.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = dest.with_name(f"{dest.stem}-{int(time.time())}{dest.suffix}")
        shutil.move(str(src), str(dest))
        moved.append((src, dest))
    return moved


def release_worker_worktree(root, path, lock, branch=None, repo=None, check_only=False):
    """Remove the finished worker's worktree PATH that holds the branch land needs, with `git worktree remove` (never
    --force), unlocking it first when Claude Code locked it: agents' shells may not remove a worktree
    (.claude/settings.json denies it), so land, a process of its own, does. Only a worktree under the clone's
    .claude/worktrees/ of the clone land runs in (`git rev-parse --show-toplevel` there: a linked worktree is its own
    clone, its workers sit under its own directory; with BRANCH given, also that of the main checkout it is a linked
    worktree of, `main_worker_dir`: the Agent tool made the worker there) that is not the one land runs in, has no
    uncommitted changes
    (except untracked intake drafts that no commit of BRANCH names: moved to INTAKE_ASIDE of ROOT, and said) and no
    live process (one whose parent has exited, a session-end hook's, is waited for, at most
    `bl_procs.HOOK_GRACE_S`: wait_for_hooks; where live_processes cannot list them, Windows, one the worktree cannot be
    renamed and back past:
    held_by_process), is on BRANCH when that is given, and is either locked by a Claude Code agent (WORKER_LOCK) or,
    unlocked, named as the Agent tool names a worker's (WORKER_NAME, `agent-*`; the test
    land_removes_clean_unlocked_worker_worktree) or by the item id of BRANCH (`work/<id>`; the test
    land_removes_worker_worktree_of_a_linked_clone_named_by_item_id). Returns None once it is removed,
    else why it was left as it was (a remove that fails puts the lock back). REPO is the checkout of a repository of a
    multi-repository workspace whose worktree PATH is (`<worker dir>/<id>/<repository>`, `repo_worktree`): the
    worktree commands run there, any lock refuses it (no Claude Code agent made it), and the name rule is the
    directory's, the item id. With CHECK_ONLY it only answers: None means every rule above holds and `land` would
    remove it, and nothing is moved, unlocked or removed."""
    home = Path(repo) if repo is not None else Path(root)

    def run_git(*args, cwd=None):
        p = subprocess.run(["git", *args], cwd=cwd or home, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return p.returncode, (p.stdout if not p.returncode else (p.stderr or p.stdout)).strip()

    state = "not locked" if lock is None else f"locked ({lock})"
    item_id = branch[len(WORK_PREFIX):] if branch and branch.startswith(WORK_PREFIX) else None
    if lock is not None and (repo is not None or not lock.startswith(WORKER_LOCK)):
        return f"it is locked ({lock or 'no reason given'})" + ("" if repo is not None else
                                                                ", not by a Claude Code agent")
    parent = path.resolve().parent
    expected = set(worker_dirs(root))
    main_dir = main_worker_dir(root) if branch and repo is None else None
    if main_dir is not None:  # land of one item's branch from a linked worktree: the main checkout's workers too
        expected.add(main_dir)
    if repo is not None:  # <worker dir>/<id>/<repository>
        outside = parent.parent not in expected or parent.name != item_id
    else:
        outside = parent not in expected
    if outside:
        return f"it is {state} but not under {' or '.join(str(d) for d in sorted(expected))}"
    if path.resolve() == Path(root).resolve():
        return f"it is {state} and is the worktree land runs in"
    if repo is None and lock is None and not path.name.startswith(WORKER_NAME) and path.name != item_id:
        return f"it is not locked and not a worker's ({WORKER_NAME}*)"
    if branch:
        code, out = run_git("symbolic-ref", "-q", "HEAD", cwd=path)
        if code:  # detached: accepted only at the branch's tip (the worker detached there to free the branch)
            head, tip = run_git("rev-parse", "HEAD", cwd=path), run_git("rev-parse", "-q", "--verify", f"refs/heads/{branch}")
            if head[0] or tip[0] or head[1] != tip[1]:
                return f"it is {state} but not on {branch}"
        elif out != f"refs/heads/{branch}":
            return f"it is {state} but not on {branch}"
    code, out = run_git("status", "--porcelain", "-uall", cwd=path)
    dirty = out.splitlines()
    drafts = [] if code or repo is not None else intake_drafts(path, dirty, branch)  # a repository holds no intake
    if code or len(drafts) < len(dirty):
        return f"it is {state} and has uncommitted changes: commit or discard them there, then run land again"
    procs, unchecked = live_processes(path)
    if procs:  # a finished session's end hook runs on for seconds: wait for it, then refuse what is still there
        procs, waited, hooks = wait_for_hooks(path, procs, root)
        if procs:  # the worker left background work running there: removing the worktree would pull it from under it
            named = ", ".join(f"pid {pid} ({comm or '?'}{', a session-end hook' if pid in hooks else ''})"
                              for pid, comm in procs)
            return (f"it is {state} and a process still runs there{f' after {waited}s' if waited else ''}: {named}; "
                    f"end it (the worker ends every background command and monitor it started), then run land again")
        if waited:
            say(f"land: waited {waited}s in {path.name} for the session-end hook to end"
                if hooks else f"land: waited {waited}s in {path.name} for a process whose parent had exited to end")
    if unchecked:  # Windows: a rename to a sibling and back fails while a process has it as its working directory
        held = held_by_process(path)
        if held:
            return (f"it is {state} and could not be moved ({held}): a process may still run there, its working "
                    f"directory in it ({unchecked}, so land cannot name it); end it, then run land again")
        if not check_only:
            say(f"land: could not check {path} for live processes ({unchecked}); it could be renamed and back, so "
                "no process holds it; removing it as a clean worker's")
    if check_only:
        return None
    kept = set_aside_drafts(root, path, drafts)

    def put_back():
        for src, dest in kept:
            if dest.is_file() and not src.exists():
                shutil.move(str(dest), str(src))
    if lock is not None:
        code, out = run_git("worktree", "unlock", str(path))
        if code:
            put_back()
            return f"git worktree unlock: {out}"
    code, out = run_git("worktree", "remove", str(path))
    if code:
        put_back()
        if lock is not None:
            run_git("worktree", "lock", "--reason", lock, str(path))
        return f"git worktree remove: {out}"
    for _, dest in kept:
        say(f"land: moved the untracked intake draft {dest.name} out of the worker's worktree to {dest.parent} "
            "(copy it back to kb/_self/backlog/ to triage it)")
    say(f"land: removed the finished worker's worktree {path} ({'unlocked; its lock was: ' + lock if lock else 'it was not locked'})")
    return None


def delete_landed_branch(root, branch, upstream, who="land", prefixes=None):
    """Delete the local work/<id> BRANCH, or the worktree-agent-* branch the Agent tool made a removed worker's
    worktree on (or a branch starting with one of PREFIXES, when given), once every commit of it is on UPSTREAM (`git cherry` lists
    no `+` line), with `git branch -D` (a branch landed by a rebase is not an ancestor, so -d refuses it): agents'
    shells may not delete a branch. Any other branch, one with a commit UPSTREAM lacks, or one checked out anywhere is
    kept, and WHO says why. Returns True once it is deleted."""
    if not branch.startswith(prefixes or (WORK_PREFIX, AGENT_BRANCH + WORKER_NAME)) or not has_ref(root, f"refs/heads/{branch}"):
        return False
    code, out, err = run(["git", "cherry", upstream, branch], cwd=root)
    if code or any(ln.startswith("+") for ln in out.splitlines()):
        say(f"{who}: kept {branch}: {'git cherry failed' if code else 'it has commits ' + upstream + ' lacks'}")
        return False
    code, out, err = run(["git", "branch", "-D", branch], cwd=root)
    say(f"{who}: deleted the landed branch {branch}" if not code else f"{who}: kept {branch}: {(err or out).strip()}")
    return not code


RepoLand = namedtuple("RepoLand", "name checkout worktree upstream tip evidence")
# a repository of a multi-repository item that land has read: its checkout, its worktree (None when none is made),
# the default branch's remote ref after a fetch, the tip of its work/<id> branch ("" when it has none) and its
# evidence, {"request": the merge request's url or !iid, "commit": the merge commit ("" when none is found)}


def repo_worktree(root, iid, name):
    """The worktree dispatch makes of repository NAME for item IID: `<worker dir>/<id>/<repository>`."""
    return next(iter(worker_dirs(root))) / iid / name


def repo_stop(name, why):
    return land_stop("repositories", f"repository {name!r}: {why}")


def repo_network(name, checkout, *args):
    """The standard output of a git network call (fetch, ls-remote) in the repository's CHECKOUT, with the bounded
    wait of kg_lock.run_git_bounded; a failure or a timeout stops the land naming the repository."""
    import kg_lock
    try:
        p = kg_lock.run_git_bounded(args, checkout, "repositories")
    except kg_lock.GitNetworkTimeout as e:
        raise repo_stop(name, str(e)) from None
    if p.returncode:
        raise repo_stop(name, f"git {' '.join(args)} failed: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def repo_default_ref(name, checkout):
    """`refs/remotes/origin/<default branch>` of the repository's CHECKOUT after `git fetch origin`: the default branch
    is read from the remote itself (`ls-remote --symref origin HEAD`), since a local `origin/HEAD` is made once and never
    moves (dispatch reads it the same way)."""
    repo_network(name, checkout, "fetch", "--quiet", "origin")
    found = re.search(r"^ref: refs/heads/(\S+)\tHEAD$", repo_network(name, checkout, "ls-remote", "--symref", "origin",
                                                                      "HEAD"), re.M)
    if found is None:
        raise repo_stop(name, "git ls-remote --symref origin HEAD gave no default branch")
    return f"refs/remotes/origin/{found.group(1)}"


def local_default_ref(checkout):
    """`refs/remotes/origin/<default>` as the checkout has it (`origin/HEAD`, else origin's main or master), or None;
    nothing is fetched (close reads it)."""
    p = subprocess.run(["git", "symbolic-ref", "-q", "refs/remotes/origin/HEAD"], cwd=checkout, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    for ref in ([p.stdout.strip()] if p.returncode == 0 else []) + [f"refs/remotes/origin/{b}" for b in ("main", "master")]:
        if ref and has_ref(checkout, ref):
            return ref
    return None


def merge_commit(checkout, tip, upstream, request_iid):
    """The commit that merged a request into UPSTREAM, "" when none is found: the first merge commit on the path from
    the branch's TIP up to UPSTREAM (a merge made with a merge commit), TIP itself when it is on UPSTREAM with no merge
    commit above it (a fast-forward), else, with no branch or a squashed one, the newest first-parent commit of UPSTREAM
    that GitLab's message `See merge request <project>!<iid>` names."""
    def out(*args):
        p = subprocess.run(["git", *args], cwd=checkout, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return p.stdout.strip() if p.returncode == 0 else ""

    if tip and subprocess.run(["git", "merge-base", "--is-ancestor", tip, upstream], cwd=checkout,
                              capture_output=True).returncode == 0:
        merges = out("rev-list", "--merges", "--ancestry-path", "--topo-order", "--reverse", f"{tip}..{upstream}")
        return merges.splitlines()[0] if merges else tip
    return out("log", "-1", "--first-parent", "--format=%H", f"--grep=See merge request .*!{request_iid}$", upstream)


def land_repositories(bl, iid):
    """The repositories of a multi-repository item (`bl_base.item_repos`) as land finds them, [RepoLand] in the order
    the item names them; [] for an item with none, whose one worktree and branch land handles as ever. Each
    repository's merge request, the one titled `<id>:`, is read once through bl_forge in its own checkout; one that is
    not merged (or none, or one that cannot be read) stops the land at step `requests` naming the repository and its
    state, every repository in one message. When all are merged, each repository's origin is fetched and its default
    branch read, every worktree dispatch made (`repo_worktree`) is checked first (a dirty, locked or live-process one
    stops the land at step `repositories` naming it, with nothing removed) and then removed, never with --force; the
    branches are deleted once the item has landed (`delete_repo_branches`)."""
    names = item_repos(bl.items[iid])
    if not names:
        return []
    import bl_forge
    root = bl.root
    say(f"land: requests: {iid}: of {', '.join(names)}")
    ops_mark("requests")
    found, bad = [], []
    for name in names:
        checkout = Path(root) / repositories()[name]
        try:
            request = bl_forge.read_request(checkout, title_prefix=f"{iid}:", run=run)
        except (Refused, bl_forge.ForgeError) as e:
            bad.append(f"repository {name!r} ({checkout}): the merge request cannot be read: {e}")
            continue
        found.append((name, checkout, request))
        if request is None:
            bad.append(f"repository {name!r}: no merge request titled '{iid}:' (state none)")
        elif request.state != "merged":
            bad.append(f"repository {name!r}: merge request !{request.iid} ({request.url or 'no url'}) is "
                       f"{request.state}, not merged")
    if bad:
        raise land_stop("requests", "; ".join(bad) + "; nothing was removed or changed: merge each, then run land again")
    ops_mark("repositories")
    staged, held = [], []
    branch = WORK_PREFIX + iid
    for name, checkout, request in found:
        upstream = repo_default_ref(name, checkout)
        p = subprocess.run(["git", "for-each-ref", "--format=%(refname) %(objectname)", f"refs/heads/{branch}", upstream],
                           cwd=checkout, capture_output=True, text=True, encoding="utf-8", errors="replace")
        refs = dict(ln.split(" ", 1) for ln in p.stdout.splitlines() if " " in ln)
        if upstream not in refs:
            raise repo_stop(name, f"the default branch {upstream[len('refs/remotes/origin/'):]!r} is not among the "
                                  "refs the fetch made")
        say(f"land: repository {name}: merge request {request.url or '!' + str(request.iid)} is {request.state} "
            f"on {upstream[len('refs/remotes/'):]}")
        wt = repo_worktree(root, iid, name)
        entry = next((e for e in worktree_entries(checkout) if e["path"] == wt.resolve()), None) if wt.is_dir() else None
        why = release_worker_worktree(root, entry["path"], entry["lock"], branch, repo=checkout,
                                      check_only=True) if entry else None
        if why:
            held.append(f"repository {name!r}: its worktree {wt} {why}")
        staged.append((name, checkout, request, upstream, refs.get(f"refs/heads/{branch}", ""),
                       entry["path"] if entry else None))
    if held:
        raise land_stop("repositories", "; ".join(held) + "; nothing was removed: end or commit what is there, then "
                                                          "run land again")
    out = []
    for name, checkout, request, upstream, tip, worktree in staged:
        commit = merge_commit(checkout, tip, upstream, request.iid)
        if not commit:
            say(f"land: repository {name}: no merge commit found for the request (its branch is gone or squashed): "
                "its evidence names the request only")
        if worktree is not None:  # clean, unlocked and free of processes as checked above: git itself refuses a dirty one
            p = subprocess.run(["git", "worktree", "remove", str(worktree)], cwd=checkout, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            if p.returncode:
                raise repo_stop(name, f"its worktree {worktree}: git worktree remove: {(p.stderr or p.stdout).strip()}")
            say(f"land: repository {name}: removed its worktree {worktree}")
        out.append(RepoLand(name, checkout, worktree, upstream, tip,
                            {"request": request.url or f"!{request.iid}", "commit": commit}))
    return out


def repo_evidence(repos):
    """The `repositories` of an item's evidence: {name: {request, commit}} of `land_repositories`'s RepoLand list."""
    return {r.name: dict(r.evidence) for r in repos}


def delete_repo_branches(repos, iid):
    """Delete each repository's `work/<id>` once the item has landed, when `git cherry` shows every commit of it on the
    repository's default branch (delete_landed_branch: a squashed or unmerged one is kept, and said). Returns the
    names of the repositories whose branch it deleted."""
    return [r.name for r in repos if r.tip and delete_landed_branch(r.checkout, WORK_PREFIX + iid, r.upstream,
                                                                    who=f"land: repository {r.name}")]


def clean_repository_leftovers(root, iid, checkouts):
    """What `land` left of the item IID's repositories CHECKOUTS ([(name, checkout)]), for close: each worktree
    dispatch made (`repo_worktree`) that is clean, unlocked, free of processes and has every commit on the
    repository's default branch as the checkout has it last fetched (the directory `<worker dir>/<id>` goes with the
    last one), then the `work/<id>` branch when every commit of it is there. Anything else is kept and `close: kept
    ...: why` says why. Returns the number kept."""
    kept, branch = 0, WORK_PREFIX + iid

    def keep(what, why):
        nonlocal kept
        kept += 1
        say(f"close: kept {what}: {why}")

    for name, checkout in checkouts:
        wt = repo_worktree(root, iid, name)
        if not (checkout / ".git").exists():
            if wt.is_dir():
                keep(wt, f"repository {name!r} has no checkout at {checkout}")
            continue
        upstream = local_default_ref(checkout)
        entry = next((e for e in worktree_entries(checkout) if e["path"] == wt.resolve()), None)
        if upstream is None:
            if entry or has_ref(checkout, f"refs/heads/{branch}"):
                keep(f"repository {name!r}", "no default branch of its origin as fetched to compare against")
            continue
        if entry:
            if not merged_into(checkout, entry["head"], upstream):
                keep(wt, f"it has commits {upstream} lacks")
                continue
            why = release_worker_worktree(root, entry["path"], entry["lock"], branch, repo=checkout)
            if why:
                keep(wt, why)
                continue
        if has_ref(checkout, f"refs/heads/{branch}") and not delete_landed_branch(checkout, branch, upstream,
                                                                                  who=f"close: repository {name}"):
            kept += 1
    try:  # the item's directory of repository worktrees, once nothing is left in it
        repo_worktree(root, iid, "x").parent.rmdir()
    except OSError:
        pass
    return kept


# head pipeline states after which GitLab's auto-merge ("merge when the pipeline succeeds") never fires
STUCK_PIPELINES = ("skipped",)


def mr_stuck(request):
    """True for a merge request (a `bl_forge.Request`) that is open, mergeable, set to auto-merge, and whose head
    pipeline ended in a state in STUCK_PIPELINES: auto-merge waits for a pipeline to succeed, which a skipped one never
    does, so the request sits until someone merges it."""
    return (request is not None and request.state == "opened" and request.auto_merge and request.mergeable
            and request.pipeline in STUCK_PIPELINES)


def read_code_request(root, branch):
    """The `bl_forge.Request` of BRANCH on the integration remote's forge project, read once for a land pass and used
    by every step of it. None, and nothing said, when there is no request, the remote names no forge project (a local
    path) or the forge cannot be read (a CLI not signed in, a failed or unreadable call): land cannot tell."""
    import bl_forge
    try:
        return bl_forge.read_request(root, branch=branch, run=run)
    except (Refused, bl_forge.ForgeError):
        return None


def stuck_merge_request(request, branch):
    """The line land adds while it waits for the merge request of BRANCH: when REQUEST is stuck (`mr_stuck`), it names
    the request and the command that merges it. None when it is not, or when `forge` is not gitlab: the gh arm merges
    nothing, so no command would carry the line out."""
    if not mr_stuck(request) or setting("forge") != "gitlab":
        return None
    return (f"land: merge request !{request.iid} ({request.url or branch}) is mergeable and set to auto-merge, "
            f"but its pipeline was {request.pipeline}, so auto-merge will not fire: merge it with "
            f"python3 _tools/backlog.py merge {branch[len('code/'):] if branch.startswith('code/') else branch}")


def family_external(bl, iid):
    """The `external` map of the item and its descendants together (tracker -> ids, first seen first): the references
    its merge request carries. A shape `check` refuses is left out."""
    out = {}
    for i in [iid] + bl.descendants(iid):
        ext = bl.items[i].get("external")
        for tracker, ids in (ext.items() if isinstance(ext, dict) else ()):
            have = out.setdefault(tracker, [])
            have += [x for x in ids if isinstance(x, str) and x and x not in have] if isinstance(ids, list) else []
    return {t: ids for t, ids in out.items() if ids}


def describe_merge_request(bl, iid, request):
    """Put the item's external ids and their urls (`bl_base.external_description`) into the description of REQUEST,
    the open merge request `read_code_request` read, after what it holds and in place of a block of land's own from an
    earlier run (REF_HEADER to the end). Says one line when it changed it; a request it cannot change is said and
    never fails the landing, and no request, or an item with no external id, says nothing."""
    block = external_description({"external": family_external(bl, iid)})
    if not block or request is None or request.state != "opened":
        return
    import bl_forge
    have = request.description or ""
    text = (have.partition(REF_HEADER)[0].rstrip() + "\n\n" + block).strip()
    if text == have.strip():
        return
    try:
        ok, err = bl_forge.set_description(bl.root, request, text, run=run)
    except (Refused, bl_forge.ForgeError) as e:
        ok, err = False, str(e)
    say(f"land: merge request !{request.iid} description holds the tracker references of {iid}" if ok
        else f"land: could not set the description of merge request !{request.iid}: {err[:200]}")


LAND_REF = "refs/land"  # refs/land/<id>: the done commit land made, kept until the landing is verified


def unpicked(root, upstream, head, commits_of):
    """The commits of HEAD that no patch-equivalent commit of UPSTREAM or of the branch COMMITS_OF has, oldest first
    (`git cherry`: a claim that sync rewrote on the integration main, or that the branch carries already, is not
    one)."""
    def plus(*args):
        p = subprocess.run(["git", "cherry", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return [ln[2:].strip() for ln in p.stdout.splitlines() if ln.startswith("+ ")]
    ahead = set(plus(upstream, head))
    return [sha for sha in plus(commits_of, head) if sha in ahead]


def missing_claims(root, family, start, upstream, branch):
    """The claim commits of the item's family on START (the checkout land began on) that the branch lacks and the
    integration main does not have: a claim made after the branch was cut, or never pushed. Oldest first."""
    out = []
    for sha in unpicked(root, upstream, start, branch):
        subject, _, vals = git(root, "log", "-1", "--format=%s%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)",
                               sha).partition("\x00")
        if subject.startswith("chore(backlog): claim ") and set(id_re().findall(vals)) & set(family):
            out.append(sha)
    return out


def carry_claims(root, claims, upstream, branch):
    """Rebase BRANCH on UPSTREAM with CLAIMS (commits, oldest first) under its own commits: they are cherry-picked on
    the detached upstream, then the branch's commits are replayed on that. A conflict aborts and changes nothing."""
    def undo():
        subprocess.run(["git", "cherry-pick", "--abort"], cwd=root, capture_output=True)
        subprocess.run(["git", "rebase", "--abort"], cwd=root, capture_output=True)
    land_git(root, "rebase", "switch", "-q", "--detach", upstream)
    p = subprocess.run(["git", "cherry-pick", *claims], cwd=root, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode:
        undo()
        raise land_stop("rebase", f"the claim commit(s) {', '.join(c[:10] for c in claims)} do not apply on "
                                  f"{upstream} (cherry-pick aborted, nothing changed): push the claim first "
                                  f"(kbgit.py sync --push), then run land again\n{(p.stderr or p.stdout).strip()}")
    tip = git(root, "rev-parse", "HEAD").strip()
    return subprocess.run(["git", "rebase", "--quiet", "--onto", tip, upstream, branch], cwd=root,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def item_state(root, rev, iid):
    """The status the item's file has at REV, None when it has none there."""
    blob = blob_id(root, rev, f"{rel_dir()}/{iid}.json")
    if not blob:
        return None
    try:
        return json.loads(git(root, "cat-file", "-p", blob)).get("status")
    except ValueError:
        return None


def verify_landed(root, remote, upstream, iid):
    """After sync --push reported success: fetch the integration main and require that the item's done commit (the
    last commit on HEAD that wrote its file) is on it and that its file reads done there. Stops, naming the step,
    when it is not: a sync that gave up quietly must never end in `landed`."""
    land_git(root, "verify", "fetch", "--quiet", remote, f"+refs/heads/main:{upstream}")
    done = git(root, "log", "-1", "--format=%H", "HEAD", "--", f"{rel_dir()}/{iid}.json").strip()
    on_main = bool(done) and subprocess.run(["git", "merge-base", "--is-ancestor", done, upstream], cwd=root,
                                            capture_output=True).returncode == 0
    if not on_main:
        raise land_stop("verify", f"sync --push exited 0, but the done commit {done[:10] or '(none)'} is not on "
                                  f"{remote}/main after a fetch: it stays on the branch, run land again once the push can go through")
    if item_state(root, upstream, iid) != "done":
        raise land_stop("verify", f"{iid}'s file on {remote}/main does not read done (it reads "
                                  f"{item_state(root, upstream, iid)}): run land again")


def restore_done(root, iid):
    """The done commit land kept in refs/land/<id> back on HEAD (the branch) when the branch lost it, in place of
    running done again: cherry-picked, only when it is the item's own done commit. True once HEAD has it."""
    ref = f"{LAND_REF}/{iid}"
    if not has_ref(root, ref) or item_state(root, ref, iid) != "done":
        return False
    p = subprocess.run(["git", "cherry-pick", ref], cwd=root, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode:
        subprocess.run(["git", "cherry-pick", "--abort"], cwd=root, capture_output=True)
        return False
    return item_state(root, "HEAD", iid) == "done"


SYNTAX_ERROR = re.compile(r"(SyntaxError|IndentationError|TabError)\b")
FRAME = re.compile(r'File "([^"]*)", line \d+')
NOT_FOUND = re.compile(r"^'?(?P<cmd>[^'\s]+)'? is not recognized as an internal or external command"
                       r"|^\S+: (line \d+: )?(?P<sh>\S+): command not found$", re.M)
PY_OPT_ARG = ("-X", "-W", "--check-hash-based-pycs")  # python options that take the next word as their value
SHELLS = {"sh", "bash", "zsh", "dash", "cmd", "cmd.exe", "pwsh", "powershell"}


def launched(argv):
    """(program, script, code): what a repro runs, read through python's options and a shell's -c (or cmd's /c)
    string. PROGRAM is the command's first word as the shell or the OS sees it; SCRIPT the file python or a shell
    runs (None for -c, -m or no script); CODE true when python runs a -c string."""
    argv = list(argv)
    for _ in range(3):  # a shell's -c string may run a shell or python in turn
        if not argv:
            return None, None, False
        prog = os.path.basename(argv[0]).lower()
        if prog in SHELLS:
            rest = argv[1:]
            while rest and rest[0].startswith("-") and rest[0].lower() not in ("-c", "-command"):
                rest = rest[1:]
            if rest and rest[0].lower() in ("-c", "/c", "-command") and len(rest) > 1:
                try:
                    argv = shlex.split(rest[1], posix=prog not in ("cmd", "cmd.exe"))
                except ValueError:
                    return (rest[1].split() or [None])[0], None, False
                continue
            return argv[0], (rest[0] if rest else None), False
        if re.fullmatch(r"python(\d+(\.\d+)?)?(\.exe)?", prog):
            i = 1
            while i < len(argv) and argv[i].startswith("-") and argv[i] not in ("-c", "-m", "-"):
                i += 2 if argv[i] in PY_OPT_ARG else 1
            nxt = argv[i] if i < len(argv) else None
            return argv[0], (None if nxt in (None, "-c", "-m", "-") else nxt), nxt == "-c"
        return argv[0], None, False
    return argv[0] if argv else None, None, False


def tracked(root, path):
    """True when git tracks PATH in the clone at ROOT: a repository tool, not a file a repro wrote for itself."""
    try:
        p = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path], cwd=root or ".", capture_output=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0


def own_code(argv, path, root=None):
    """True when a frame's file is the repro's own code: the -c string, or the script python runs when git does not
    track it (a file the repro wrote for itself; a repository tool's SyntaxError, such as a 3.12-only construct run
    on 3.11, is a genuine reproduction)."""
    _, script, code = launched(argv)
    if path == "<string>":
        return code
    if not script:
        return False
    p, s = (os.path.normcase(os.path.normpath(x)) for x in (path, script))
    return (p == s or p.endswith(os.sep + s)) and not tracked(root, script)


IMPORT_ERROR = re.compile(r"(ModuleNotFoundError|ImportError|AttributeError): (.*)")
EXC_LINE = re.compile(r"[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt)\b(: |$)")


OWN_CODE_ERRORS = ("TypeError", "NameError", "UnboundLocalError")  # the repro's code is wrong, not the value it tests


NONE_TYPE_ERROR = re.compile(r"'NoneType' object is not (subscriptable|iterable)|object of type 'NoneType' has no len\(\)")


def own_exception(argv, lines, root=None):
    """Why a repro failed by a Python error in its own code, or None: the traceback's last exception is one that says
    the repro's code itself is wrong (OWN_CODE_ERRORS: a TypeError from calling a function with the wrong arguments, a
    NameError, an UnboundLocalError), raised with the innermost frame in the repro's own code (the -c string or an
    untracked script, own_code), so it fails before the defect is tested (ST-ikh2h7m5). An exception on a value the
    code under test returned (an AttributeError on its None, a TypeError of subscripting, len() or iterating it, a
    KeyError of its output), one raised inside the code under test, and an AssertionError are failures it accepts."""
    if not any(ln.startswith("Traceback (most recent call last)") for ln in lines):
        return None
    for i in range(len(lines) - 1, -1, -1):
        m = EXC_LINE.match(lines[i])
        if not m:
            continue
        cls = lines[i].split(":", 1)[0].rsplit(".", 1)[-1]
        if cls not in OWN_CODE_ERRORS or (cls == "TypeError" and NONE_TYPE_ERROR.search(lines[i])):
            return None
        frame = next((f for f in map(FRAME.search, reversed(lines[:i])) if f), None)
        if frame and own_code(argv, frame.group(1), root):
            return (f"the repro's own code raised {cls} ({lines[i][:200]}): it fails before it tests the defect; "
                    "exit 1 on the defect (sys.exit(1 if ... else 0)) instead")
        return None
    return None


def own_import_error(argv, lines, root=None):
    """Why a repro failed importing its own names, or None: the traceback's last exception is a ModuleNotFoundError,
    an ImportError or a module's missing attribute (`module 'x' has no attribute`) raised in the repro's own code (the
    -c string or an untracked script, as own_code reads it), so it names something the code never had; or it is pytest
    missing from a test module the repro imports, which the system python3 cannot run (tests.py runs them). An error
    raised inside the code under test is a failure it accepts."""
    exc = [i for i, ln in enumerate(lines) if EXC_LINE.match(ln)]
    if not exc:
        return None
    i = exc[-1]
    m = IMPORT_ERROR.match(lines[i])
    if not m or (m.group(1) == "AttributeError" and not m.group(2).startswith("module ")):
        return None
    frames = [f for f in map(FRAME.search, lines[:i]) if f and not f.group(1).startswith("<frozen")]
    if not frames:
        return None
    where = frames[-1].group(1)
    if m.group(1) == "ModuleNotFoundError" and re.match(r"No module named '_?pytest\b", m.group(2)) \
            and re.match(r"(test_|conftest)", os.path.basename(where)):
        return (f"the repro imports a test module that needs pytest ({lines[i][:200]}): python3 without pytest cannot "
                "run it; select the test with tests.py -k instead")
    if own_code(argv, where, root):
        return (f"the repro's own code names what it cannot import ({lines[i][:200]}): it fails before it tests "
                "anything; import only names the module has")
    return None


CHAIN = {"&&", "||", ";", "|", "&", "|&"}  # the shell's list and pipeline operators: each starts a command of its own


RESERVED = {"if", "then", "elif", "else", "do", "while", "until", "!", "{", "(", "time"}  # the next word is a command
CLOSERS = {"fi", "done", "esac", "}", ")"}  # end a compound command: no command word
PREFIX_RUNNERS = {"env", "command", "exec", "nohup", "nice"}  # run the utility named after their options and assignments
RUNNER_ARG_OPTS = {"-u", "--unset", "-n", "-C", "--chdir", "-S"}  # options of a prefix runner that take a value
TIMEOUT_ARG_OPTS = {"-s", "--signal", "-k", "--kill-after"}  # options of timeout that take a value


def command_word(tokens):
    """(the command word of one simple command's TOKENS, the tokens after it): reserved words, `!`, `name=value`
    assignments and a prefix runner (env, command, exec, nohup, nice) with its options and assignments are skipped,
    as POSIX reads them; (None, []) when nothing is left."""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in RESERVED or t in CLOSERS or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
            i += 1
            while t == "time" and i < len(tokens) and tokens[i].startswith("-") and tokens[i] != "--":
                i += 1  # time's own options (-p)
        elif os.path.basename(t) in PREFIX_RUNNERS or os.path.basename(t) == "timeout":
            timeout = os.path.basename(t) == "timeout"
            i += 1
            opts = TIMEOUT_ARG_OPTS if timeout else RUNNER_ARG_OPTS
            while i < len(tokens) and (tokens[i].startswith("-") or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[i])):
                i += 2 if tokens[i] in opts else 1
            if timeout and i < len(tokens):
                i += 1  # timeout's duration
        else:
            return t, tokens[i + 1:]
    return None, []


def is_c_flag(arg):
    """True when ARG makes a shell read its next argument as the command string: -c, cmd's /c, -command, or short
    flags combined with c (-ec, -xc)."""
    return arg.lower() in ("-c", "/c", "-command") or bool(re.fullmatch(r"-[a-z]{0,3}c[a-z]{0,3}", arg))


def own_words(argv, depth=3):
    """The command words a repro runs itself: argv[0], or for a shell's -c (or cmd's /c) string the command word of
    every command in it (command_word: after a reserved word such as if, then, do or !, an assignment or a prefix
    runner such as env), split at && || ; | & ( ) and a newline (POSIX runs each, and any can exit 127), and through a
    nested shell's -c string anywhere in it, up to DEPTH shells deep (BG-zvh7cvyo, BG-bapadqdl)."""
    argv = list(argv)
    if not argv:
        return set()
    prog = os.path.basename(argv[0]).lower()
    rest = argv[1:]
    while prog in SHELLS and rest and rest[0].startswith("-") and not is_c_flag(rest[0]):
        rest = rest[1:]
    if not (prog in SHELLS and rest and is_c_flag(rest[0]) and len(rest) > 1) or depth <= 0:
        return {os.path.basename(argv[0])}
    try:
        lex = shlex.shlex(rest[1].replace("\n", " ; "), posix=prog not in ("cmd", "cmd.exe"), punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return {w for w in rest[1].split()[:1]}
    commands, cur = [], []
    for t in tokens:
        if t in CHAIN or t in ("(", ")", ";;"):
            commands.append(cur)
            cur = []
        else:
            cur.append(t)
    commands.append(cur)
    words = set()
    for cmd in commands:
        word, args = command_word(cmd)
        if word is None:
            continue
        if os.path.basename(word).lower() in SHELLS:
            words |= own_words([word, *args], depth - 1)
        else:
            words.add(os.path.basename(word))
    return words


def missing_inside(argv, out):
    """True when the output's not-found message names only commands the repro does not run itself (own_words): a
    wrapper (a shell script, a hook) that started and could not find a tool inside it, which may be the defect. A name
    that is any command word of the repro's own -c string is its own error."""
    own = own_words(argv)
    names = {m.group("cmd") or m.group("sh") for m in NOT_FOUND.finditer(out)}
    return bool(names) and bool(own) and all(os.path.basename(n) not in own for n in names)


def own_failure(argv, code, out, root=None):
    """Why a failing repro failed for its own error rather than the defect, or None when its failure may be the
    defect's: it cannot start (not found; exit 127 or 9009, or a shell's or python -m's lone not-found message, unless the
    message names a tool inside a wrapper the repro started); Python cannot compile its own code (a SyntaxError in
    the -c string or in a script git does not track in ROOT, the clone, default the working directory, before
    anything is tested; python's options and a shell's -c string are read for the script they run); the tool it runs rejects its
    arguments (argparse's exit 2 with usage: and error:); its own code raised an uncaught exception (own_exception); or
    a pytest run selected no tests (exit 5, or no tests ran).
    A failed assertion, a traceback from the code under test or a finding with exit 1 is a failure it accepts."""
    lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    last = lines[-1][:200] if lines else ""
    alone = len(lines) <= 3  # a shell's or interpreter's one message, not a tool's output that mentions one
    if code is not None and (code in (127, 9009) or (alone and NOT_FOUND.search(out))) and missing_inside(argv, out):
        return None  # a wrapper started and a tool inside it is missing: that may be the defect
    if ((code is None and out.startswith("cannot start")) or code in (127, 9009)
            or (alone and NOT_FOUND.search(out)) or (alone and argv[1:2] == ["-m"] and "No module named " in out)):
        msg = next((ln[:200] for ln in lines if NOT_FOUND.search(ln) or "No module named " in ln), last)
        return f"the command cannot start ({msg or f'exit {code}'})"
    if code is None:
        return None
    for i, ln in enumerate(lines):
        if not SYNTAX_ERROR.match(ln):
            continue
        frame = next((m for m in map(FRAME.search, reversed(lines[:i])) if m), None)  # the frame it points at
        if frame and own_code(argv, frame.group(1), root):
            return (f"Python cannot compile the repro's own code ({ln[:200]}): it fails before it tests anything, "
                    "whatever the defect does (a backslash in a Python string, or newlines lost in --repro's "
                    "split: use / in paths and ; between statements, or put the code in a script)")
    why = own_import_error(argv, lines, root) or own_exception(argv, lines, root)
    if why:
        return why
    if code == 2 and re.search(r"^usage: ", out, re.M) and re.search(r"^\S+: error: ", out, re.M):
        err = next((ln for ln in lines if re.match(r"\S+: error: ", ln)), last)[:200]
        return (f"the tool rejects the repro's arguments ({err}): a usage error tests nothing (when the rejection is "
                "the defect, write a repro that runs the tool and exits 1 on it)")
    if selected_nothing(code, out):
        return f"the test run selected no tests (exit {code}: {last}): a -k or path that matches nothing reproduces nothing"
    return None


def land_checks(bl, iid):
    """The code lane's checks stage: run the item's checks and a bug's repro, as done does, before sync --push opens
    the auto-merging code/<id> merge request, so nothing is pushed for an item whose proof fails. A check whose test
    run selected nothing is named as malformed, as a repro's own error is when the bug is filed."""
    it = bl.items[iid]
    checks = list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else [])
    say("land: checks")
    ops_mark("checks")
    failed = []
    for c in checks:
        ok, code, out = run_check(bl.root, c)
        say(f"{'ok  ' if ok else 'FAIL'} exit={code} {shlex.join(c['run'])}")
        if not ok:
            failed.append((c, code, out))
    if not failed:
        return
    for c, code, out in failed:
        why = own_failure(c["run"], code, out, bl.root)
        tail = "\n".join(out.strip().splitlines()[-8:])
        say(f"--- {shlex.join(c['run'])} (want exit {c.get('exit', 0)}"
            + (f", output matching {c['match']!r}" if c.get("match") else "") + ")"
            + (f" is a malformed check: {why}" if why else "") + f":\n{tail}")
    raise land_stop("checks", f"{len(failed)} check(s) of {bl.label(iid)} failed: nothing was pushed")


def fast_forward_start(root, remote, start_ref, upstream):
    """After a pushed landing, bring the checkout `land` started on level with the integration main: `git merge
    --ff-only` when it is on a branch whose `@{upstream}` is REMOTE/main and has no uncommitted changes. Anything
    else is left alone and said, and the exit status never depends on it: the next `claim --commit` must start from
    the pushed main, and a refusal here only costs a manual fast-forward."""
    if not start_ref.startswith("refs/heads/"):
        return
    name = start_ref[len("refs/heads/"):]
    p = subprocess.run(["git", "rev-parse", "--abbrev-ref", f"{name}@{{upstream}}"], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode or p.stdout.strip() != f"{remote}/main" or not has_ref(root, upstream):
        return
    behind = subprocess.run(["git", "rev-list", "--count", f"HEAD..{upstream}"], cwd=root, capture_output=True,
                            text=True, encoding="utf-8", errors="replace").stdout.strip()
    if behind in ("", "0"):
        return
    if git(root, "status", "--porcelain").strip():
        say(f"land: left {name} {behind} commit(s) behind {remote}/main: it has uncommitted changes "
            f"(git merge --ff-only {remote}/main once they are committed)")
        return
    p = subprocess.run(["git", "merge", "--ff-only", "--quiet", upstream], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode:
        why = ((p.stderr or p.stdout).strip().splitlines() or ["diverged"])[-1]
        say(f"land: left {name} {behind} commit(s) behind {remote}/main: it cannot fast-forward ({why})")
    else:
        say(f"land: fast-forwarded {name} {behind} commit(s) to {remote}/main")


def changed_articles(changed):
    """The qualified paths (`<root>/<path in the root>`, as lint.py takes them) of the .md files CHANGED (repository
    paths) holds under a kb root, in order."""
    return ["/".join(parts[1:]) for parts in (p.split("/") for p in changed)
            if len(parts) > 2 and parts[0] == "kb" and parts[-1].endswith(".md")]


def land_once(bl, a):
    """Land a finished item's branch: rebase it on the integration main, then by lane. Content: done --commit, the
    heavy checks when _tools/ changed (else the lint on the changed articles), sync --push. Code not yet on the integration main: the item's checks and
    a bug's repro, the heavy checks, sync --push (a code/<id> merge request; main does not move), and a re-run once
    it has merged finishes it as content does. Stops at the first failing step, naming it. Every run and every stop ends
    on the branch (or the detached commit) it started on: the rebase switches to the landed branch, and a claim
    --commit made after land must not ride on it into its merge request."""
    import kbpublic
    import kg_lock  # the host's main lock: the fetch and rebase hold it, the sync --push it runs takes it itself
    iid = need(bl, a.id)
    root = bl.root
    remote = kbpublic.integration_remote(root)
    branch = a.branch or f"work/{iid}"
    upstream = f"refs/remotes/{remote}/main"
    landed = False  # set once the item is done on the integration main: then its work/<id> branch is deleted
    pushed = False  # set once this run's push went through (a landing or a code item's merge request)
    drafts = own_checkout_drafts(root, git(root, "status", "--porcelain", "-uall").splitlines())
    for _, dest in set_aside_drafts(root, root, drafts):  # the checkout's own SessionStart hook filed them
        say(f"land: moved the untracked intake draft {dest.name} out of this checkout to {dest.parent} "
            "(copy it back to kb/_self/backlog/ to triage it)")
    if git(root, "status", "--porcelain").strip():
        raise land_stop("clean tree", "uncommitted changes: commit or stash them first (git status --short)")
    if not has_ref(root, f"refs/heads/{branch}"):
        raise land_stop("branch", f"no local branch {branch} (--branch names another)")
    repos = land_repositories(bl, iid)  # a multi-repository item: each repository's request merged, worktrees removed
    other = checked_out_elsewhere(root, branch)
    agent_branch = None
    if other:  # a finished worker's clean worktree, locked by Claude Code or an unlocked agent-*, is removed
        why = release_worker_worktree(root, *other, branch=branch)
        if why:
            raise land_stop("branch", f"{branch} is checked out in the worktree {other[0]} and {why}: land it from "
                                      "there, or remove that worktree first")
        agent_branch = AGENT_BRANCH + other[0].name  # the Agent tool's branch of that worktree, deleted once landed
    else:  # a worker detached at the branch's tip holds no branch: remove it too, and go on when it has to stay
        for path, lock in detached_workers(root, branch):
            why = release_worker_worktree(root, path, lock, branch=branch)
            if why:
                say(f"land: kept the worktree {path}: {why}")
            else:
                agent_branch = AGENT_BRANCH + path.name
    start = git(root, "rev-parse", "HEAD").strip()
    start_ref = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.strip()
    try:
        with kg_lock.guarded("backlog.py land: fetch and rebase", "backlog.py", clone=str(root)):
            say(f"land: fetch {remote} main")
            ops_mark("fetch")
            land_git(root, "fetch", "fetch", "--quiet", remote, f"+refs/heads/main:{upstream}")
            say(f"land: rebase {branch} on {remote}/main")
            ops_mark("rebase")
            claims = missing_claims(root, [iid] + bl.descendants(iid), start, upstream, branch)
            if claims:  # claimed after the branch was cut, or never pushed: the claim goes under the worker's commits
                say(f"land: carry the claim commit(s) {', '.join(c[:10] for c in claims)} under {branch}")
                p = carry_claims(root, claims, upstream, branch)
            else:
                p = subprocess.run(["git", "rebase", "--quiet", upstream, branch], cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
        if p.returncode:
            subprocess.run(["git", "rebase", "--abort"], cwd=root, capture_output=True)
            raise land_stop("rebase", f"{branch} does not rebase cleanly on {remote}/main (rebase aborted, nothing "
                                      f"changed): rebase it by hand, then run land again\n"
                                      f"{(p.stderr or p.stdout).strip()}")
        bl = Backlog(root)  # the item files as the rebased branch has them
        need(bl, iid)
        family = [iid] + bl.descendants(iid)
        late, _, owners = unlanded_code(root, family)
        LAND_OPS["lane"] = "code" if late else "content"
        if late == ["(no such ref)"]:
            raise land_stop("fetch", f"{upstream} does not exist after the fetch")
        if late:
            code_branch = sync_code_branch(root, upstream, owners, iid)  # the branch sync --push opens for this range
            tracking = f"refs/remotes/{remote}/{code_branch}"
            fetched = land_git_network(root, "fetch", "fetch", "--quiet", remote,
                                       f"+refs/heads/{code_branch}:{tracking}").returncode == 0
            if fetched and git(root, "rev-parse", f"{tracking}^{{tree}}") == git(root, "rev-parse", "HEAD^{tree}"):
                say(f"land: {bl.label(iid)} waits for its merge request (branch {code_branch} on {remote}, already "
                    f"pushed with this content): merge it, then run backlog.py land {iid} again")
                LAND_OPS["pending"] = ([git(root, "rev-parse", tracking).strip()], code_branch)
                request = read_code_request(root, code_branch)  # the pass's one read of the request
                describe_merge_request(bl, iid, request)
                stuck = stuck_merge_request(request, code_branch)
                if stuck:
                    say(stuck)
                return 0
        if not late:
            if bl.items[iid].get("status") == "done":
                say(f"land: done: {bl.label(iid)} is done already")
            elif restore_done(root, iid):  # a run before this one made the done commit and the branch lost it
                say(f"land: done: {bl.label(iid)} has its done commit from the last run ({LAND_REF}/{iid}), "
                    "not run again")
            else:
                say("land: done --commit")
                ops_mark("done")
                try:
                    cmd_done(bl, argparse.Namespace(id=iid, dry_run=False, commit=True, trailer=a.trailer,
                                                    repositories=repo_evidence(repos)))
                except Refused as e:
                    raise land_stop("done", str(e)) from None
                land_git(root, "done", "update-ref", f"{LAND_REF}/{iid}", "HEAD")
        if late:  # the code lane pushes an auto-merging merge request: its proof runs before that, not after
            stray = out_of_scope(root, item_commits(root, family), own_globs(scope(bl, iid)))
            if stray:  # done's scope rule, read before the merge request opens rather than after it merged
                raise land_stop("scope", f"{bl.label(iid)}'s commits change files outside its touches, so done would "
                                         "refuse it once the merge request merged; nothing was pushed: "
                                + "; ".join(f"commit {sha[:10]} changed {p}" for sha, p in stray)
                                + " (revert it, or widen touches: backlog.py set ID --add-touch PATH)")
            land_checks(bl, iid)
        changed = git(root, "diff", "--name-only", upstream, "HEAD").splitlines()
        if any(p.startswith("_tools/") for p in changed):
            stale = land_stale()
            if stale[1]:
                land_run(root, stale[0], [*stale[1], upstream])  # a missing Self-Reviewed fails in seconds
            for step, argv in land_heavy():
                land_run(root, step, argv)
        else:  # lint.py takes qualified article paths: the changed articles only, before sync --push
            articles = changed_articles(changed)
            lint = land_lint()
            if articles and lint[1]:
                land_run(root, lint[0], [*lint[1], *articles])
        land_run(root, *land_push(), whole=True, program=True)
        if late:
            # the request sync opened by push options: this pass's one read of it
            describe_merge_request(bl, iid, read_code_request(root, code_branch))
            tip = pushed_tip(root, remote, code_branch)
            LAND_OPS["pending"] = (tip, code_branch) if tip else None
            say(f"land: {bl.label(iid)} is not done yet: its code goes as the merge request of branch {code_branch}; "
                f"once it has merged, run backlog.py land {iid} again (fetch, rebase, done --commit, sync --push)")
            pushed = True
        else:
            verify_landed(root, remote, upstream, iid)
            subprocess.run(["git", "update-ref", "-d", f"{LAND_REF}/{iid}"], cwd=root, capture_output=True)
            say(f"land: {bl.label(iid)} landed")
            landed = pushed = True
        return 0
    except kg_lock.MainLockTimeout as e:  # a live holder kept the main lock for the whole bound: report blocked
        raise land_stop("fetch and rebase", str(e)) from None
    finally:  # back to where land started, whatever happened after the rebase switched to BRANCH
        back = (["switch", "-q", start_ref[len("refs/heads/"):]] if start_ref.startswith("refs/heads/")
                else ["switch", "-q", "--detach", start])
        p = subprocess.run(["git", *back], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if p.returncode:
            say(f"land: could not return to {start_ref or start[:10]}: {(p.stderr or p.stdout).strip()}")
        else:
            if pushed:  # a refusal is said and changes no exit status
                fast_forward_start(root, remote, start_ref, upstream)
            if landed:  # the worker's branches, landed: never the one land runs on
                for done_branch in (branch, agent_branch):
                    if done_branch and start_ref != f"refs/heads/{done_branch}":
                        delete_landed_branch(root, done_branch, upstream)
                delete_repo_branches(repos, iid)


def pushed_tip(root, remote, code_branch):
    """[the tip of CODE_BRANCH on REMOTE] as sync pushed it, fetched: sync may rebase the range onto a newer main
    before it pushes, so the commits --wait-merge waits for are the pushed ones, not the ones land rebased. None when
    the fetch fails (git dies with exit 128 on a ref the remote lacks), times out or leaves no ref, said once: a stale
    or missing tip is never waited for, and the first pass still ends as not done yet (BG-bd547fvz)."""
    import kg_lock
    tracking = f"refs/remotes/{remote}/{code_branch}"
    try:
        p = kg_lock.run_git_bounded(("fetch", "--quiet", remote, f"+refs/heads/{code_branch}:{tracking}"), root,
                                    "wait-merge")
    except kg_lock.GitNetworkTimeout as e:
        say(f"land: could not fetch {code_branch} from {remote} after the push ({e}): no tip to wait for")
        return None
    if p.returncode:
        say(f"land: could not fetch {code_branch} from {remote} after the push "
            f"({(p.stderr or p.stdout).strip() or f'exit {p.returncode}'}): no tip to wait for")
        return None
    tip = subprocess.run(["git", "rev-parse", "-q", "--verify", tracking], cwd=root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout.strip()
    return [tip] if tip else None


WAIT_POLL = 60  # seconds between land --wait-merge's reads of the integration main


def merged_on_main(root, remote, shas):
    """True when every one of SHAS is an ancestor of the integration main after a fetch: git, not the forge CLI, says
    the code merge request merged (a merge commit or a fast-forward keeps the commits)."""
    ref = f"refs/remotes/{remote}/main"
    land_git_network(root, "wait-merge", "fetch", "--quiet", remote, f"+refs/heads/main:{ref}")
    return all(subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=root,
                              capture_output=True).returncode == 0 for sha in shas)


def wait_merge(root, remote, shas, bound, poll=WAIT_POLL, sleep=time.sleep):
    """The number of reads of the integration main it took for SHAS to be on it, reading every POLL seconds for at
    most BOUND seconds; None when they are not on it by then."""
    reads, waited = 0, 0
    while True:
        reads += 1
        if merged_on_main(root, remote, shas):
            return reads
        if waited + poll > bound:
            return None
        sleep(poll)
        waited += poll


@ops_land
def cmd_land(bl, a):
    """Land a finished item's branch (land_once). With --wait-merge SECONDS a code item's first pass is followed by a
    bounded wait for its merge request, read from git (a fetch of the integration main every WAIT_POLL seconds, not
    the forge CLI), then the second pass in the same run; a wait that runs out stops at step wait-merge naming the
    merge request."""
    LAND_OPS["pending"] = None
    code = land_once(bl, a)
    pending, bound = LAND_OPS.get("pending"), getattr(a, "wait_merge", None)
    if code or not pending or bound is None:
        return code
    import kbpublic
    shas, code_branch = pending
    remote = kbpublic.integration_remote(bl.root)
    say(f"land: wait-merge: reading {remote}/main every {WAIT_POLL} s for up to {bound} s")
    ops_mark("wait-merge")
    reads = wait_merge(bl.root, remote, shas, bound)
    if reads is None:
        raise land_stop("wait-merge", f"the merge request of branch {code_branch} has not merged into {remote}/main "
                                      f"within {bound} s: merge it (backlog.py merge {a.id}), then run backlog.py land "
                                      f"{a.id} again")
    say(f"land: merged on {remote}/main ({reads} read(s)): second pass")
    LAND_OPS["pending"] = None
    return land_once(Backlog(bl.root), a)


def summary_key(bl, iid):
    """Tree order: each item under its parent, the tops (epics, then the sprint's stories and bugs) in work order."""
    return [bl.order_key(x) for x in reversed([iid] + bl.ancestors(iid))]


def summary_line(bl, iid, gone):
    """One commit-body line for an item close deletes: its id, title, kind, status and the commit done recorded, with
    the checks the review's rerun found gone (gone_checks)."""
    it = bl.items[iid]
    depth = sum(1 for p in bl.ancestors(iid) if p in gone)
    ev = (it.get("evidence") or {}).get("commit") if isinstance(it.get("evidence"), dict) else None
    at = f" at {ev[:10]}" if ev else ", no evidence commit"
    dead = "".join(f"; gone check: {shlex.join(g)}" for g in gone_checks(it))
    return f"{'  ' * depth}- {bl.label(iid)} ({it.get('kind', '')}): {it.get('status', '')}{at}{dead}"


def refused_dones(root, ids):
    """How many `done.refused` ops rows name one of `ids`: the rows of the local spool's tools files and of the
    committed ops sidecars (`kb/_querylog/ops/`), each row id once."""
    import ql_capture, ql_store
    rows = []
    spool = ql_capture.spool_dir()
    for f in sorted(Path(spool).glob("tools-*.jsonl")) if spool is not None else []:
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(ln))
            except ValueError:
                continue
    for _, objs in ql_store.records(ql_store.ops_files(Path(root) / "kb" / "_querylog")):
        rows += [o for _, o in objs]
    return len({r.get("id") for r in rows if isinstance(r, dict) and r.get("event") == "done.refused"
                and r.get("item") in ids})


def close_row(bl, sid, items):
    """The keys of the `sprint.close` ops row of sprint `sid` whose item ids are `items`, or None when the sprint's
    planning commit cannot be read: the items `landed` (done) and `dropped`, the `bugs` among them, the provisional
    gates of the items and the sprint that the operator `confirmed`, the `refused` dones the ops rows
    name for them (`refused_dones`) and `ms` from the commit that added the sprint's file to now."""
    its = [bl.items[i] for i in items]
    gates = [g for it in its + [bl.items[sid]] for g in it.get("gates", [])]
    added = [int(x) for x in git(bl.root, "log", "--diff-filter=A", "--format=%ct", "--",
                                 f"{rel_dir()}/{sid}.json").split()]
    if not added:
        return None
    return {"sprint": sid,
            "landed": sum(1 for it in its if it.get("status") == "done"),
            "dropped": sum(1 for it in its if it.get("status") == "dropped"),
            "bugs": sum(1 for it in its if it.get("kind") == "bug"),
            "confirmed": sum(1 for g in gates if g.get("kind") == "provisional" and g.get("by") == "operator"),
            "refused": refused_dones(bl.root, set(items)),
            "ms": max(0, (int(time.time()) - min(added)) * 1000)}


def record_close(bl, sid, items):
    """Append the `sprint.close` ops row (`ql_deliver.ops_row`) before close deletes the items; best effort: whatever
    goes wrong, close goes on."""
    try:
        from ql_deliver import ops_row
        fields = close_row(bl, sid, items)
        if fields is not None:
            ops_row("sprint.close", **fields)
    except Exception:  # noqa: BLE001 - a close never fails for its log
        pass


def worktree_entries(root):
    """[{path, head, branch, lock}] of `git worktree list --porcelain` in ROOT: branch is None when detached, lock
    None when not locked (a lock with no reason is "")."""
    code, text, _ = run(["git", "worktree", "list", "--porcelain"], cwd=root)
    out = []
    for block in text.split("\n\n") if not code else []:
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("worktree "):
            continue
        e = {"path": Path(lines[0][len("worktree "):]).resolve(), "head": "", "branch": None, "lock": None}
        for ln in lines[1:]:
            if ln.startswith("HEAD "):
                e["head"] = ln[len("HEAD "):]
            elif ln.startswith("branch refs/heads/"):
                e["branch"] = ln[len("branch refs/heads/"):]
            elif ln == "locked" or ln.startswith("locked "):
                e["lock"] = ln[len("locked "):]
        out.append(e)
    return out


def merged_into(root, rev, upstream):
    """True when every commit of REV is on UPSTREAM (`git cherry` lists no `+` line: a rebased landing counts)."""
    code, out, _ = run(["git", "cherry", upstream, rev], cwd=root)
    return not code and not any(ln.startswith("+") for ln in out.splitlines())


REOPENED_REFS = "refs/kb-reopened/"  # reopen keeps a done item's file there, one ref per item id (bl_items)


def tree_item_ids(root, rev, rel):
    """The ids of the item files in directory REL of REV's tree (empty when REV or REL cannot be read)."""
    code, out, _ = run(["git", "ls-tree", "--name-only", f"{rev}:{rel}"], cwd=root)
    return set() if code else {n[:-len(".json")] for n in out.split() if n.endswith(".json")}


def prune_reopened_refs(bl):
    """Delete each refs/kb-reopened/<id> whose item file <id>.json no longer exists in the backlog directory: close and
    drop outside a sprint call it after their deletions, so the clone keeps no reopen mark of a removed item, the
    items they remove now and any left by earlier removals alike. The refs are shared by every worktree of the
    clone, so the checkout alone does not judge: a ref of an item the integration main holds that this checkout
    never held (its file is on `<remote>/main`, in neither HEAD nor the merge base) is kept, since it was filed on
    main after the checkout branched; and with no `<remote>/main` to read, every ref is kept. A ref of an existing
    item stays. Returns the ids whose ref was deleted."""
    import kbpublic
    root = bl.root
    code, out, _ = run(["git", "for-each-ref", "--format=%(refname)", REOPENED_REFS], cwd=root)
    refs = [] if code else out.split()
    main = f"refs/remotes/{kbpublic.integration_remote(root)}/main"
    if not refs or not has_ref(root, main):
        return []
    rel = bl.dir.relative_to(root).as_posix()
    known = tree_item_ids(root, "HEAD", rel)
    code, base, _ = run(["git", "merge-base", "HEAD", main], cwd=root)
    if not code and base.strip():
        known |= tree_item_ids(root, base.strip(), rel)
    filed_since = tree_item_ids(root, main, rel) - known
    gone = []
    for ref in refs:
        iid = ref[len(REOPENED_REFS):]
        if not iid or iid in filed_since or (bl.dir / f"{iid}.json").exists():
            continue
        if not run(["git", "update-ref", "-d", ref], cwd=root)[0]:
            gone.append(iid)
    if gone:
        say(f"deleted {len(gone)} reopen mark(s) of removed items: {', '.join(gone)}")
    return gone


def clean_worker_leftovers(root, sid, ids):
    """Remove what the closed sprint SID's workers left in the clone ROOT, as a process of its own because agents'
    shells may not run `git worktree remove` or `git branch -D` (.claude/settings.json; the repositories of a
    multi-repository item are cleaned by `clean_repository_leftovers`): the clean `agent-*` worktrees
    of the sprint's items IDS (on `work/<id>`, or detached at a commit whose KB-Work trailer names one), the sprint's
    `work/<id>` branches and the `worktree-agent-*` branches whose tip is on the integration main (one whose
    `agent-<x>` worktree, read before any removal, is another sprint's worker is kept). Worktrees go before branches;
    never with --force. A branch with a commit the integration main lacks, or a locked, dirty or process-holding
    worktree, is kept, and `close: kept ...: reason` says why. Returns the number kept."""
    import kbpublic
    kept = 0

    def keep(what, why):
        nonlocal kept
        kept += 1
        say(f"close: kept {what}: {why}")

    if not id_re().fullmatch(sid):
        keep(sid, "not a sprint id")
        return kept
    remote = kbpublic.integration_remote(root)
    upstream = f"refs/remotes/{remote}/main"
    if not has_ref(root, upstream):
        upstream = "refs/heads/main"
    if not has_ref(root, upstream):
        keep("the worker leftovers", "no integration main to compare against")
        return kept
    dirs = worker_dirs(root)
    entries = [e for e in worktree_entries(root) if e["path"].parent in dirs]
    wanted = {f"{WORK_PREFIX}{i}" for i in ids}

    def sprints(e):
        """Whether the worker worktree E is this sprint's: on one of its work/<id> branches, or detached at a commit
        whose KB-Work trailer names one of its items."""
        if e["branch"] in wanted:
            return True
        if e["branch"] is not None:
            return False
        _, trailer, _ = run(["git", "log", "-1", "--format=%(trailers:key=KB-Work,valueonly)", e["head"]], cwd=root)
        return bool({t.strip() for t in re.split(r"[,\s]+", trailer) if t.strip()} & set(ids))

    # read before any removal: the agent-<x> worktree each worktree-agent-<x> branch belongs to, and whose it is
    workers = {e["path"].name: (e, sprints(e)) for e in entries if e["path"].name.startswith(WORKER_NAME)}
    for e, ours in workers.values():  # the sprint's workers first
        on_branch = e["branch"] in wanted
        if not ours:
            continue
        if not merged_into(root, e["head"], upstream):
            keep(e["path"], f"it has commits {upstream} lacks")
            continue
        why = release_worker_worktree(root, e["path"], e["lock"], branch=e["branch"] if on_branch else None)
        if why:
            keep(e["path"], why)
    here = {e["branch"] for e in worktree_entries(root) if e["branch"]}
    code, out, _ = run(["git", "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"], cwd=root)
    for ln in out.splitlines() if not code else []:
        branch, _, tip = ln.partition(" ")
        if branch in here:
            continue
        if branch in wanted:
            delete_landed_branch(root, branch, upstream, who="close")
        elif branch.startswith(AGENT_BRANCH + WORKER_NAME):
            owner = workers.get(branch[len(AGENT_BRANCH):])
            if owner and not owner[1]:  # its worktree is another sprint's worker, still there: not this close's
                keep(branch, f"its worktree {owner[0]['path']} is on {owner[0]['branch'] or 'a detached commit'}, "
                             "not one of this sprint's items")
                continue
            anc = run(["git", "merge-base", "--is-ancestor", tip, upstream], cwd=root)[0] == 0
            if anc:
                delete_landed_branch(root, branch, upstream, who="close")
    return kept


TIDY_PREFIXES = (WORK_PREFIX, AGENT_BRANCH + WORKER_NAME, "orch/")  # orch/: a retired runner's branch left in a clone


def integration_main(root):
    """The integration main's ref of the clone ROOT (`refs/remotes/<remote>/main`, else `refs/heads/main`), or None."""
    import kbpublic
    for ref in (f"refs/remotes/{kbpublic.integration_remote(root)}/main", "refs/heads/main"):
        if has_ref(root, ref):
            return ref
    return None


def tidy_worktree_kept(root, entry, upstream):
    """Why the agent worktree ENTRY stays, or None when tidy may remove it: the worktree tidy runs in, any lock (a Claude
    Code agent's too: tidy is clone-wide and cannot tell a finished worker from one that has not committed yet; close,
    which knows its sprint's items, releases those), uncommitted changes, a live process, or a commit UPSTREAM lacks."""
    path = entry["path"]
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    cwd = Path.cwd().resolve()
    if path == here or path == cwd or path in cwd.parents:
        return "it is the worktree tidy runs in"
    if entry["lock"] is not None:
        return f"it is locked ({entry['lock'] or 'no reason given'}): a worker may still be using it"
    code, out, err = run(["git", "status", "--porcelain"], cwd=path)
    if code or out.strip():
        return "it has uncommitted changes" if not code else f"git status failed: {err.strip()}"
    procs, _ = live_processes(path)
    if procs:
        return "a process still runs there: " + ", ".join(f"pid {pid} ({comm or '?'})" for pid, comm in procs)
    if not merged_into(root, entry["head"], upstream):
        return f"it has commits {upstream} lacks"
    return None


def cmd_tidy(bl, a):
    """List (and with --apply remove) the clone's leftovers: the clean, process-free agent-* worktrees under its
    .claude/worktrees/ whose commits are all on the integration main, then the local work/*, worktree-agent-* and
    orch/* branches whose commits are all on it and that no worktree has checked out; every other one is printed with
    why it stays. Removal goes through close's helpers, never --force."""
    root = bl.root
    upstream = integration_main(root)
    if upstream is None:
        raise Refused("tidy: no integration main to compare against (fetch the integration remote first)")
    verb = "removed" if a.apply else "would remove"
    removable, kept = 0, 0
    dirs = worker_dirs(root)
    for e in worktree_entries(root):
        if e["path"].parent not in dirs or not e["path"].name.startswith(WORKER_NAME):
            continue
        why = tidy_worktree_kept(root, e, upstream)
        if why is None and a.apply:
            why = release_worker_worktree(root, e["path"], e["lock"])
        if why:
            kept += 1
            say(f"tidy: kept {e['path']}: {why}")
        else:
            removable += 1
            say(f"tidy: {verb} the worktree {e['path']}")
    here = {e["branch"] for e in worktree_entries(root) if e["branch"]}
    code, out, _ = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=root)
    for branch in out.split() if not code else []:
        if not branch.startswith(TIDY_PREFIXES):
            continue
        if branch in here:
            kept += 1
            say(f"tidy: kept {branch}: it is checked out in a worktree")
        elif not merged_into(root, f"refs/heads/{branch}", upstream):
            kept += 1
            say(f"tidy: kept {branch}: it has commits {upstream} lacks")
        elif a.apply and not delete_landed_branch(root, branch, upstream, who="tidy", prefixes=TIDY_PREFIXES):
            kept += 1
        else:
            removable += 1
            if not a.apply:
                say(f"tidy: would remove the branch {branch}")
    say(f"tidy: {verb} {removable}, kept {kept}" + ("" if a.apply else " (--apply removes them)"))
    return 0


def args_tidy(p):
    p.add_argument("--apply", action="store_true", help="remove what tidy lists (default: only list it)")


def cleanup_gate_do(bl, dead):
    """Drop every gate `do` entry of a remaining item that names (by item id) an item in DEAD, which close deletes: the
    work that entry waited for is done or dropped, and check refuses a `do` naming an item that does not exist. An
    emptied `do` goes with its last entry. Returns [(item id, gate id, option, the deleted item's id)]."""
    out = []
    for i, it in sorted(bl.items.items()):
        if i in dead:
            continue
        touched = False
        for g in it.get("gates") or []:
            do = g.get("do") if isinstance(g, dict) else None
            if not isinstance(do, dict):
                continue
            hit = [o for o, how in do.items() if isinstance(how, str) and how in dead]
            for opt in hit:
                out.append((i, g.get("id"), opt, do.pop(opt)))
            if hit and not do:
                g.pop("do")
            touched = touched or bool(hit)
        if touched:
            bl.save(it)
    return out


PART_SPLIT = re.compile(r",\s+(?:and\s+)?|\s+and\s+")  # a list clause's parts: split at ', ' and ' and '
CLAUSE_COVER = 0.5 # the share of a clause's words an item's title and goal must hold to carry it


def clause_words(text):
    return {w for w in re.findall(r"[a-z0-9_]+", str(text).lower()) if len(w) > 3}


def clause_parts(clause):
    """A clause that is a list of independent statements, split at ', ' and ' and ' into its parts with words."""
    return [p for p in (x.strip(" .") for x in PART_SPLIT.split(clause)) if clause_words(p)]


def goal_clause_lines(bl, sid, items):
    """close --summary's clause lines: the sprint's goal split into its clauses, each with the done item of the sprint
    whose title and goal hold at least CLAUSE_COVER of its words, or `unmet` and the open item outside the sprint that
    carries it now (moved out mid-sprint), or none."""
    clauses = goal_clauses(bl.items[sid].get("goal", ""))
    if len(clauses) < 2 and not (clauses and len(clause_parts(clauses[0])) > 1):
        return []

    def best(cw, ids):
        scored = [(len(cw & clause_words(f"{bl.items[i].get('title', '')} {bl.items[i].get('goal', '')}")) / len(cw), i)
                  for i in ids]
        top = max(scored, default=(0, None))
        return top[1] if top[0] >= CLAUSE_COVER else None
    done = [i for i in items if bl.items[i].get("status") == "done" and not bl.items[i].get("review")
            and not bl.items[i].get("goal_research")]
    elsewhere = [i for i, it in bl.items.items() if i not in items and it.get("kind") not in ("sprint", "epic")
                 and it.get("status") not in ("done", "dropped")]
    out = ["goal clauses:"]
    def verdict(cw):
        by = best(cw, done) if cw else None
        if by:
            return bl.label(by)
        now = best(cw, elsewhere) if cw else None
        return f"unmet, carried by {bl.label(now) if now else 'no item'}"
    for n, c in enumerate(clauses, 1):
        cw = clause_words(c)
        parts = clause_parts(c)
        if len(parts) > 1 and not (cw and best(cw, done)):
            out.append(f"  {n}. {c[:120]}:")
            out.extend(f"     - {p[:100]}: {verdict(clause_words(p))}" for p in parts)
        else:
            out.append(f"  {n}. {c[:120]}: {verdict(cw)}")
    return out


def cmd_close(bl, a):
    if a.summary and a.commit:
        raise Refused("close --summary only prints and commits nothing: run close --commit without --summary")
    sid = need(bl, a.sprint)
    items = bl.sprint_items(sid)
    left = [i for i in items if bl.items[i].get("status") not in ("done", "dropped")]
    if left:
        raise Refused(f"{bl.label(sid)} is not finished:\n  " + "\n  ".join(line(bl, i) for i in left))
    gone = set(items)
    epics = {p for i in items for p in bl.ancestors(i) if bl.items[p].get("kind") == "epic"}
    for e in epics:
        rest = [c for c in bl.descendants(e) if c not in gone]
        if bl.items[e].get("status") == "done" and not rest:
            gone.add(e)
    summary = [f"delivered by {bl.label(sid)}:"] + [summary_line(bl, i, gone)
                                                  for i in sorted(gone, key=lambda i: summary_key(bl, i))]
    if a.summary:
        summary += goal_clause_lines(bl, sid, items)
    if a.summary:  # the runbook prints the list, writes the retrospective, then closes: --summary changes nothing
        for x in summary:
            say(x)
        return 0
    title = bl.items[sid].get("title", "")
    record_close(bl, sid, items)  # the facts of the sprint that the deletion below takes from the tree
    for i in gone:
        say(f"deleted {line(bl, i)}")
    # a remaining item's relates_to is information only, and a depends_on on a deleted item that is not dropped is
    # satisfied (close refuses while anything is open): drop those ids, or check fails on dangling links and horizon
    # counts the item as waiting outside its sprint. A dependency on a dropped item stays for check to report.
    dead = gone | {sid}
    for i, it in sorted(bl.items.items()):
        if i in dead:
            continue
        cut = []
        for f in ("relates_to", "depends_on"):
            ids = it.get(f)
            if not isinstance(ids, list):
                continue
            off = [r for r in ids if r in dead and (f == "relates_to" or bl.items[r].get("status") != "dropped")]
            if not off:
                continue
            keep = [r for r in ids if r not in off]
            if keep:
                it[f] = keep
            else:
                it.pop(f)
            cut.append(f"{f} {', '.join(off)}")
        if cut:
            bl.save(it)
            say(f"dropped {'; '.join(cut)} from {bl.label(i)}")
    for i, gate, opt, target in cleanup_gate_do(bl, dead):  # a gate's do names an item by id too
        say(f"dropped gate {gate} do {opt!r} (item {target}) from {bl.label(i)}")
    declared = repositories()  # each item's repositories, read before the deletion
    in_repos = {i: [(n, Path(bl.root) / declared[n]) for n in item_repos(bl.items[i])] for i in sorted(gone)
                if item_repos(bl.items[i])}
    for i in gone:
        bl.delete(i)
    label = bl.label(sid)
    bl.delete(sid)
    say(f"closed {label}; its items stay in git history (git log --grep 'KB-Work: <id>')")
    prune_reopened_refs(bl)
    # the body is the summary: the retrospective's findings, written by hand, go in with git commit --amend
    commit_written(bl, a, "close", sid, body="\n".join(summary), title=title)
    try:  # the workers' leftovers go last, and whatever goes wrong there never undoes or fails the close
        clean_worker_leftovers(bl.root, sid, sorted(gone))
        for i, checkouts in in_repos.items():  # what land left of a multi-repository item's repositories
            clean_repository_leftovers(bl.root, i, checkouts)
    except Exception as e:  # noqa: BLE001
        say(f"close: kept the worker leftovers of {sid}: {e}")
    return 0


PRECHECK_NOTE = "passes before the work"  # an item's notes saying so keep its passing checks out of precheck's warnings
PRECHECK_TAIL = 20  # lines of a failing check's output that precheck prints under the check's line
TRACEBACK = "Traceback (most recent call last)"


def precheck_items(bl, sid):
    """The ids of the sprint's open committed items precheck reads, in order: the review and research stories are left
    out, since the review's checks pass by design and the research story's (`researched`) fails until its research is
    written."""
    return [iid for iid in sorted(bl.sprint_items(sid))
            if bl.items[iid].get("status") in ("draft", "todo", "doing")
            and not bl.items[iid].get("review") and not bl.items[iid].get("goal_research")]


def precheck_rows(bl, sid):
    """[(item id, check, exit code, passed, output)] of each check, and of a bug its repro after them, of the sprint's
    open committed items (`precheck_items`), run once on the checkout as it is (before any work commit), as `done`
    runs them."""
    rows = []
    for iid in precheck_items(bl, sid):
        for c in clause_commands(bl.items[iid]):
            ok, code, out = run_check(bl.root, c)
            rows.append((iid, c, code if code is not None else -1, ok, out))
    return rows


def clause_map(bl, iid):
    """(lines, warnings, unread) of an item's goal clauses and the check or repro that reads each, from its `clauses`
    mapping ({clause, check} entries, the check an index into `clause_commands`): a line for each clause and a warning
    for each that no check reads (the mapping names it with no index in range, or has no entry for it), and for an
    entry that names no clause of the goal. An item whose goal is one clause with no mapping has nothing to say; one
    of several clauses with no mapping gets one warning, so the planner records which check reads each."""
    it = bl.items[iid]
    clauses = goal_clauses(it.get("goal"))
    cmds = clause_commands(it)
    entries = [e for e in it.get("clauses") or [] if isinstance(e, dict)]
    if len(clauses) < 2 and not entries:
        return [], [], 0
    label = bl.label(iid)
    if not entries:
        lines = [f"  {n}. {c[:120]}: no check recorded" for n, c in enumerate(clauses, 1)]
        return lines, [f"warning: {label}: its goal has {len(clauses)} clauses and the item records no clauses mapping: "
                       f"say which check or repro reads each (set {iid} --add-clause CLAUSE=N, N the index of the "
                       "check, the repro after them)"], len(clauses)
    lines, warns, unread = [], [], 0
    for n, c in enumerate(clauses, 1):
        at = sorted({e.get("check") for e in entries if e.get("clause") == c
                     and isinstance(e.get("check"), int) and 0 <= e["check"] < len(cmds)})
        if at:
            lines.append(f"  {n}. {c[:120]}: "
                         + "; ".join(f"check {i} `{shlex.join(map(str, cmds[i].get('run') or []))}`" for i in at))
            continue
        unread += 1
        lines.append(f"  {n}. {c[:120]}: no check reads it")
        warns.append(f"warning: {label}: goal clause {n} ({c[:80]}) is read by no check or repro: add one that proves "
                     f"it, then map it (set {iid} --add-clause CLAUSE=N), or reword the goal")
    for e in entries:
        if e.get("clause") not in clauses:
            warns.append(f"warning: {label}: its clauses mapping names {str(e.get('clause'))[:80]!r}, which is no "
                         "clause of its goal: reword the entry to a clause as the goal spells it")
    return lines, warns, unread


def intake_fingerprint(c):
    """The fingerprint FP of a check that is `backlog.py intake --status FP` (bl_intake.STATUS_REPRO and one more
    word), else None."""
    argv = c.get("run") or []
    n = len(bl_intake.STATUS_REPRO)
    if len(argv) == n + 1 and list(argv[:n]) == bl_intake.STATUS_REPRO and bl_intake.FP_RE.fullmatch(str(argv[n])):
        return argv[n]
    return None


def windowed_detector(root, fp, calls):
    """(detector, what it judges, when the check can first pass) when the fingerprint `fp` is a finding of a detector
    that judges a window of time, so the check follows time and no work: `trailers` (the commits within
    bl_intake.TRAILER_WINDOW_DAYS days of main's tip, so it passes once main has moved that far past the newest
    flagged commit, whatever the clock says) and `repeats` (the latest closed ISO week, so it can first pass once the
    running week has closed); else None. `calls` is a dict that holds the command classes of the committed ops
    sidecars once read, for the first repeats fingerprint that INSTEAD's keys do not name."""
    today = datetime.datetime.now(datetime.timezone.utc).date()
    days = bl_intake.TRAILER_WINDOW_DAYS
    if fp == bl_intake.fingerprint("trailers", bl_intake.WHOLE_KEY):
        when = (f"once main's tip is more than {days} days past the commits it names: the window follows main's tip, "
                "not the calendar")
        try:
            found = bl_intake.trailer_findings(root)
            times = git(root, "log", "--no-walk=unsorted", "--format=%ct", *[s for s, _ in found]).split() if found else []
        except (Refused, RuntimeError, OSError, ValueError):
            found, times = [], []
        if found and len(times) == len(found):
            newest = max(zip((int(t) for t in times), (s for s, _ in found)))
            day = datetime.datetime.fromtimestamp(newest[0], datetime.timezone.utc).date() + datetime.timedelta(days=days)
            when = (f"no earlier than {day}, and only once main's tip is more than {days} days past the newest commit it "
                    f"names ({newest[1]}): the window follows main's tip, not the calendar")
        return "trailers", f"the commits within {days} days of main's tip", when
    classes = set(bl_intake.INSTEAD)
    if not any(fp == bl_intake.fingerprint("repeats", k) for k in classes):
        if "classes" not in calls:
            try:
                calls["classes"] = {k for _, k in bl_intake.committed_calls(root)[0]}
            except (OSError, ValueError):
                calls["classes"] = set()
        classes = calls["classes"]
    if any(fp == bl_intake.fingerprint("repeats", k) for k in classes):
        year, week, _ = today.isocalendar()
        monday = today + datetime.timedelta(days=8 - today.isoweekday())  # the Monday after the running week
        return "repeats", "the latest closed ISO week", f"on {monday}, once the week {year}-W{week:02d} has closed"
    return None


def cmd_precheck(bl, a):
    """precheck SP: run each committed item's checks, and a bug's repro, once before any work and warn (exit 0) of each
    that passes already: it proves nothing yet, unless the item's notes say the check passes before the work (one that
    pins behaviour that must stay). It also warns, whether the check or repro passes or not, of one that is the
    `intake --status` of a time-windowed detector (repeats, trailers), naming when it can first pass, so the item is
    moved or gated before the start. A check that fails prints its line and the last PRECHECK_TAIL lines of its output
    (stdout and stderr together) under it, so a planner sees whether it fails for the premise or for another reason; a
    traceback in that output is said to be a broken check, not a failing premise. After the checks it prints each
    committed item's goal clauses (split as close --summary splits a sprint goal) with the check or repro that reads each,
    from the item's `clauses` mapping (`set ID --add-clause CLAUSE=N`), and warns of a clause no check reads and of a
    goal of several clauses with no mapping (`clause_map`). kb-sprint plan runs it before the start gate is asked, so
    start stays fast."""
    sid = need(bl, a.sprint)
    if bl.items[sid].get("kind") != "sprint":
        raise Refused(f"precheck needs a sprint: {bl.label(sid)} is a {bl.items[sid].get('kind')}")
    rows = precheck_rows(bl, sid)
    passing = 0
    calls = {}
    for iid, c, code, ok, out in rows:
        fp = intake_fingerprint(c)
        win = windowed_detector(bl.root, fp, calls) if fp else None
        if win:
            name, judges, when = win
            tail = (f"it passes now, but its result follows time, not the work: it can change {when}" if ok else
                    f"it can first pass {when}; move the item to a sprint that starts after that, or gate it, before the start")
            say(f"warning: {bl.label(iid)}: `{shlex.join(c['run'])}` is the intake --status of the time-windowed "
                f"detector {name}: it judges {judges}; {tail}")
        if not ok:
            lines = out.strip().splitlines()
            broken = ("; the output holds a traceback: the check is broken (an exception), not a failing premise"
                      if TRACEBACK in out else "")
            say(f"{bl.label(iid)}: `{shlex.join(c['run'])}` fails before the work (exit {code}){broken}; "
                + (f"the last {min(len(lines), PRECHECK_TAIL)} of {len(lines)} lines of its output:" if lines
                   else "it printed nothing"))
            for line in lines[-PRECHECK_TAIL:]:
                say(f"    {line}")
            continue
        if PRECHECK_NOTE in (bl.items[iid].get("notes") or ""):
            continue
        passing += 1
        say(f"warning: {bl.label(iid)}: `{shlex.join(c['run'])}` already exits {code} before the work: it proves "
            f"nothing yet; make it fail until the work is done, or say in the item's notes that it {PRECHECK_NOTE} "
            "and why (a check that pins behaviour that must stay)")
    unread = 0
    for iid in precheck_items(bl, sid):
        lines, warns, n = clause_map(bl, iid)
        unread += n
        if lines:
            say(f"goal clauses of {bl.label(iid)}, and the check or repro that reads each:")
            for text in lines:
                say(text)
        for text in warns:
            say(text)
    say(f"precheck {bl.label(sid)}: checks={len(rows)} passing={passing} unread={unread}")
    return 0


def args_done(p):
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")


def args_land(p):
    p.add_argument("id")
    p.add_argument("--branch", help="the local branch to land (default work/ID)")
    p.add_argument("--wait-merge", type=int, metavar="SECONDS",
                   help="after a code item's first pass, wait up to SECONDS for its merge request (read from git "
                        "every 60 s), then run the second pass")
    p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                   help="a trailer of the session's own for the done --commit commit (repeatable)")


def merge_target(bl, iid):
    """(branch, project url) `backlog.py merge ID` merges: the item's own code/ID on the integration remote's forge
    project (`bl_forge.target`: `forge_project`, else the remote's URL); Refused for an unknown item or a remote that
    names no forge project."""
    import bl_forge
    need(bl, iid)
    t = bl_forge.target(bl.root, run)
    return f"code/{iid}", f"https://{t.host}/{t.project}"


def cmd_merge(bl, a):
    """Merge the item's own code/ID merge request on the integration remote's project, now (`bl_forge.merge_own`:
    `glab mr merge --auto-merge=false --yes`): the one way an agent merges, since .claude/settings.json allows no
    `glab mr merge`. Another item's branch and another project are refused (exit 2), and so is every merge on the gh
    arm. Its state is read first: one auto-merge already merged is reported merged, exit 0, so land runs next; a
    closed one, no request of the branch and a forge that cannot be read are exit 1; only an open one is merged, by its
    number, the newest open one when the branch has several."""
    import bl_forge
    branch, project = merge_target(bl, a.id)
    try:
        outcome, request, text = bl_forge.merge_own(bl.root, branch, run=run)
    except bl_forge.ForgeError as e:
        say(f"merge {branch} ({project}): could not read the merge request: {e}")
        return 1
    if outcome == "already":
        say(f"merge {branch} ({project}): already merged" + (f" at {request.merged_at}" if request.merged_at else ""))
        return 0
    if outcome == "closed":
        say(f"merge {branch} ({project}): the merge request is closed, not merged")
        return 1
    if outcome == "none":
        say(f"merge {branch} ({project}): no merge request of the branch")
        return 1
    say(f"merge {branch} ({project}): {outcome}")
    if text:
        say(text[-600:])
    return 0 if outcome == "merged" else 1


def args_merge(p):
    p.add_argument("id", help="the item whose code/ID merge request to merge")


def args_close(p):
    p.add_argument("sprint")
    p.add_argument("--summary", action="store_true",
                   help="only print each item close would delete with its status and evidence commit (the close "
                        "commit's body); changes nothing")


bl_cli.register("done", cmd_done, args_done)
bl_cli.register("researched", cmd_researched, lambda p: p.add_argument("id"))
bl_cli.register("precheck", cmd_precheck, lambda p: p.add_argument("sprint"))
bl_cli.register("land", cmd_land, args_land)
bl_cli.register("merge", cmd_merge, args_merge)
bl_cli.register("close", cmd_close, args_close)
bl_cli.register("tidy", cmd_tidy, args_tidy)
