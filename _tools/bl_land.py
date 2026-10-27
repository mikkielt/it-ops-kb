"""The landing side of backlog.py (kb/_self/backlog.md, What done refuses, Landing; kb/_self/tools.md): `done`, which runs an
item's checks and records the evidence, `land`, which rebases a worker's branch and runs the steps to the integration
main, and `merge`; with what they share: the commits an item's trailers name (`unlanded_code`, `out_of_scope`,
`delivery_evidence`, the automatic query-log delivery a store-only story takes for a work commit, and the
ledger rows they changed for a source nothing names: `unrelated_baselines`), the runner of a check (`run_check`) and the
stuck merge request line.

Standard library only; imports `bl_base`, `bl_check` (the no-op rules `done` applies), `bl_clean` (the recorded leftovers `land` and
`close` remove once they are done: `land_cleanup`, and the handler it gives `close`), `bl_cli`, `bl_intake`, `bl_plan` and
the two modules cut from it: `bl_close` (`close` and the worker's worktree and branches `land` releases and
deletes) and `bl_precheck` (`researched`, `precheck` and `item_commits`), which import neither this module nor `backlog`.
The names the other modules read as `bl_land.NAME` stay importable from here. `bl_selfcheck` (the load a review story's
`done` refuses a whole-suite run at) is imported where `done` reads it. The branch `land` expects sync to open for code
commits is named by `kg_lane.lane_plan`, the one helper sync uses. It registers `done`, `land` and `merge` with `bl_cli`
itself when imported (`backlog.py`'s USAGE puts each in its usage position), and `host-check` and the repro rules there
call `run_check` from here."""
import argparse, csv, hashlib, importlib, io, json, os, re, shlex, shutil, subprocess, sys, time
from collections import namedtuple
from pathlib import Path

import bl_clean
import bl_cli
import bl_close
import bl_intake
import bl_plan
from bl_base import (  # run_check lives below bl_land, so bl_ci reaches it without bl_land (ST-ufpxla7r)
    ANSI_RE, Backlog, REF_HEADER, WORKSPACE, colourless_env, run_check, Refused, Rejected, commit_written, claims_ledger,
    external_description, git, id_re, in_scope, item_file, item_repos, line, need, rel_dir,
    repo_branch, repo_title_prefix, repositories, research_story, run, say, scope, setting, split_touch, waits,
    worker_dirs, main_worker_dir,
)  # worker_dirs, main_worker_dir: other modules read them as bl_land.NAME
from bl_check import HOST_BOUND_GATE, host_bound_accepted, is_test_run, noop_output, trivial_command
from bl_close import (  # the worker's worktree and the repositories' leftovers `land` shares with close and tidy
    AGENT_BRANCH, WORK_PREFIX, delete_landed_branch, detached_workers, gone_checks, has_ref, land_stop,
    add_landing_worktree, landing_lock, landing_worktree_path, own_checkout_drafts, release_worker_worktree,
    remove_landing_worktree, repo_worktree, set_aside_drafts, worktree_entries,
)
from bl_close import (  # noqa: F401 - bl_items and bl_dispatch read them as bl_land.NAME
    REOPENED_REFS, RESEARCH_DEFAULT_GOAL, WORKER_NAME, cleanup_gate_do, clauses_left_behind, prune_reopened_refs,
)
from bl_precheck import item_commits, research_rows, research_without_facts  # noqa: F401 - research_rows: read as bl_land.NAME


def store_only(globs):
    """True when GLOBS is not empty and every glob is inside the committed query-log store (bl_intake.STORE_REL)."""
    store = bl_intake.STORE_REL
    return bool(globs) and all(g == store or g.startswith(store + "/") for g in globs)


def delivery_evidence(root, ids, globs):
    """[short hashes], newest first, of the automatic query-log deliveries on HEAD (`querylog.py apply --push`: the
    trailer KB-Auto: querylog and no KB-Work) that a story of the query-log store only (`store_only`) takes as its
    evidence in place of a work commit: one that changed a file GLOBS match, that is on the integration main when that
    ref is fetched, and that was authored no earlier than the item's latest claim commit on HEAD (the author time, which
    a rebase keeps; no claim commit on HEAD, no bound). Its checks still run: they read what the delivery wrote."""
    if not store_only(globs):
        return []
    fmt = ("%H%x00%at%x00%s%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)%x00"
           "%(trailers:key=KB-Auto,valueonly,separator=%x2C)%x1e")
    claimed, auto = 0, []
    for rec in git(root, "log", "HEAD", "--no-merges", f"--format={fmt}").split("\x1e"):
        parts = rec.strip().split("\x00")
        if len(parts) != 5 or not parts[1].isdigit():
            continue
        sha, at, subject, work, kinds = parts[0], int(parts[1]), parts[2], parts[3], parts[4]
        if subject.startswith("chore(backlog): claim ") and set(id_re().findall(work)) & set(ids):
            claimed = max(claimed, at)
        if "querylog" in [k.strip() for k in kinds.split(",")]:
            auto.append((sha, at))
    import kbpublic
    ref = f"refs/remotes/{kbpublic.integration_remote(root)}/main"
    fetched = subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode == 0
    out = []
    for sha, at in auto:
        if at < claimed:
            continue
        paths = [p for p in git(root, "show", "--no-renames", "--name-only", "--format=", sha).splitlines() if p]
        if not any(p.startswith(bl_intake.STORE_REL + "/") and in_scope(p, globs) for p in paths):
            continue
        if fetched and subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=root,
                                      capture_output=True).returncode:
            continue  # not delivered yet: the push that makes it the integration main's has not happened
        out.append(sha[:10])
    return out


def research_carried(bl, iid, globs):
    """(commit, story id) of the newest KB-Work commit on HEAD of the sprint's goal research story (or one of its
    descendants) that changed a file GLOBS match, never an always-in-scope one; None when the item is that story or one
    of its descendants, is the review, has no sprint or research story, or none of the story's commits changed such a
    file. `done` takes it, for an item with no work commit of its own, as the work the item's checks read."""
    it = bl.items[iid]
    sid = bl.sprint_of(iid)
    story = research_story(bl, sid) if sid else None
    if not story or it.get("review") or iid == story or story in bl.ancestors(iid):
        return None
    commits = item_commits(bl.root, [story] + bl.descendants(story))
    hit = [sha for sha, paths in commits.items() if any(in_scope(p, globs) and not in_scope(p, ()) for p in paths)]
    return (hit[-1], story) if hit else None


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


def leak_hits(root, commits):
    """[(path, line, kind)] of the leak scan (`kbpublic.tree_hits`, the scan `test_leaks` runs over tracked files) of
    each file the item's COMMITS ({commit: [paths]}) changed, as HEAD holds it: an email address, a real-looking id or a
    secret outside the allowlist, so the worker fixes it in its worktree and not at the sync gate of the landing."""
    import kbpublic
    return kbpublic.tree_hits("HEAD", sorted({p for paths in commits.values() for p in paths}), root)


STATE_LEDGER, ANCHOR_LEDGER = "_fetch_state.csv", "_anchors.csv"
STATE_BASELINE = ("sha256", "text_sha256")  # fetch.py's hashes; with factdiff.BASELINE_KEYS, what detect compares a page with
GENERATED_DIRS = ("_census", "_snapshots", "_retrieval", "_querylog")  # written by tools over every source: cite none
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def blob_text(root, rev, path):
    """The text of PATH at REV, "" when REV has no such file."""
    p = subprocess.run(["git", "cat-file", "blob", f"{rev}:{path}"], cwd=root, capture_output=True)
    return p.stdout.decode("utf-8-sig", errors="replace") if p.returncode == 0 else ""


def ledger_rows(text, state):
    """{key: row} of a ledger's csv TEXT: a _fetch_state.csv row (STATE true) is keyed by its id, an _anchors.csv row
    by (fact, path, source_id)."""
    rows = {}
    for r in csv.DictReader(io.StringIO(text, newline="")):
        rows[(r.get("id") or "") if state else (r.get("fact"), r.get("path"), r.get("source_id"))] = r
    return rows


def ledger_change(state, key, b, a, detection):
    """(source id, [changed columns], what) of one ledger row from B to A (None when the row is absent there): a
    _fetch_state.csv row (STATE true) differs in the DETECTION columns, an _anchors.csv row is added, dropped or
    differs in a column other than verified_utc; no columns when it did not change, or when the row is absent at both
    ends (one commit added it and a later one dropped it)."""
    if state:
        cols = [c for c in detection if ((b or {}).get(c) or "") != ((a or {}).get(c) or "")]
        return key, cols, ", ".join(cols) if a else "row dropped"
    cols = ([] if b is None and a is None else ["added"] if b is None else ["dropped"] if a is None
            else [c for c in a.keys() | b.keys()
                  if isinstance(c, str) and c != "verified_utc" and (a.get(c) or "") != (b.get(c) or "")])
    return key[2] or "", cols, ", ".join(sorted(cols))


def article_sources(root, rev, path):
    """The source ids the facts of the article PATH cite at REV (a fact's UNK part cites none: no anchor run anchors
    it), None when REV has no such file."""
    import kbfacts
    text = blob_text(root, rev, path)
    if not text:
        return None
    units = kbfacts.csv_units(path, text) if path.endswith(".csv") else kbfacts.md_units(path, text)
    return {sid for u in units for part in u["tags"] if part["kind"] != "UNK" for sid in part["ids"]}


def ledger_moves(root, commits):
    """{source id: [`<ledger>: <what changed>`]} of the ledger rows the item's own COMMITS ({commit: [paths]}, oldest
    first) changed and HEAD still has changed: a row counts when one of those commits changed it (each commit
    against its own parent, so a row only another item's commit advanced is not the item's), and it differs at HEAD
    from the parent of the first of them, so a later revert clears it. A _fetch_state.csv row changes when its
    detection columns (factdiff.BASELINE_KEYS and the text hashes, not checked_utc) differ, an _anchors.csv row
    when it is added, dropped or changed in a column other than verified_utc. A dropped _anchors.csv row of a source
    that no fact of its article cites at the item's base (the parent of the first commit) is an orphan row an anchor
    run prunes: it is no move."""
    import factdiff
    detection = tuple(factdiff.BASELINE_KEYS) + STATE_BASELINE
    first = {}  # (path, row key): the row at the parent of the first item commit that changed it
    for sha, paths in commits.items():
        for path in paths:
            if Path(path).name not in (STATE_LEDGER, ANCHOR_LEDGER):
                continue
            if blob_id(root, f"{sha}^", path) == blob_id(root, sha, path):
                continue
            state = Path(path).name == STATE_LEDGER
            before = ledger_rows(blob_text(root, f"{sha}^", path), state)
            after = ledger_rows(blob_text(root, sha, path), state)
            for key in before.keys() | after.keys():
                if (path, key) not in first and ledger_change(state, key, before.get(key), after.get(key),
                                                              detection)[1]:
                    first[(path, key)] = before.get(key)
    base = f"{next(iter(commits))}^" if first else None
    now, cited = {}, {}
    out = {}
    for (path, key), b in first.items():
        if path not in now:
            now[path] = ledger_rows(blob_text(root, "HEAD", path), Path(path).name == STATE_LEDGER)
        sid, cols, what = ledger_change(Path(path).name == STATE_LEDGER, key, b, now[path].get(key), detection)
        if cols == ["dropped"] and Path(path).name == ANCHOR_LEDGER:
            article = (Path(path).parent / (key[1] or "")).as_posix()
            if article not in cited:
                cited[article] = article_sources(root, base, article)
            if cited[article] is not None and sid not in cited[article]:
                continue
        if cols:
            out.setdefault(sid, set()).add(f"{path}: {what}")
    return {sid: sorted(w) for sid, w in out.items()}


def cites_sources(path):
    """True for a changed file whose lines are facts or records of sources: not a ledger a tool rewrites for every
    source, a generated directory, a coverage table or an item file."""
    parts = path.split("/")
    return not (item_file(path) or parts[-1] in (STATE_LEDGER, ANCHOR_LEDGER) or parts[-1].startswith("_coverage.")
                or any(d in parts[:-1] for d in GENERATED_DIRS))


def token_words(text):
    """The tokens of TEXT, and the parts of each joined by a hyphen or underscore: S100-related and S100-S120 name
    S100 (and S120), S300_old names S300."""
    words = set()
    for tok in TOKEN_RE.findall(text):
        words.add(tok)
        words.update(p for p in re.split(r"[-_]+", tok) if p)
    return words


def cited_tokens(root, commits, texts):
    """The words (token_words) of TEXTS (the item's goal and title) and of every line the item's COMMITS ({commit:
    [paths]}) added or removed in a file that cites_sources: a source id in it is named, by the goal or by a fact the
    item touched."""
    words = set()
    for t in texts:
        words.update(token_words(t))
    for sha, paths in commits.items():
        paths = [p for p in paths if cites_sources(p)]
        for i in range(0, len(paths), 100):
            diff = git(root, "show", "--no-renames", "-U0", "--format=", sha, "--", *paths[i:i + 100])
            for ln in diff.splitlines():
                if ln[:1] in "+-" and not ln.startswith(("+++", "---")):
                    words.update(token_words(ln[1:]))
    return words


def census_ids(root, commits):
    """The source ids of the census log rows the item's COMMITS ({commit: [paths]}) added or changed, each commit
    against its own parent: a row of a csv under _census/, read by its `id` or `source_id` column."""
    ids = set()
    for sha, paths in commits.items():
        for path in paths:
            parts = path.split("/")
            if not path.endswith(".csv") or "_census" not in parts[:-1]:
                continue
            rows = {}
            for rev in (f"{sha}^", sha):
                rows[rev] = {tuple(r.items()) for r in csv.DictReader(io.StringIO(blob_text(root, rev, path), newline=""))}
            ids.update(dict(r).get("id") or dict(r).get("source_id") or "" for r in rows[sha] - rows[f"{sha}^"])
    ids.discard("")
    return ids


def unrelated_baselines(bl, iid, root, commits):
    """[(source id, [what changed])] of the ledger rows the item's COMMITS changed (ledger_moves) for a source that
    neither its goal (the family's goals and titles), a line it added or removed nor a census log row it added or
    changed (census_ids) names, sorted by id."""
    moves = ledger_moves(root, commits)
    if not moves:
        return []
    texts = [str(bl.items[i].get(k) or "") for i in [iid] + bl.descendants(iid) for k in ("goal", "title")]
    named = cited_tokens(root, commits, texts) | census_ids(root, commits)
    return sorted((sid, what) for sid, what in moves.items() if sid not in named)


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


def refuse_done(iid, t0, reasons, message, checks=(), record=True):
    """Append the `done.refused` ops row (the item, its closed reason classes, the failed checks' names and the
    milliseconds spent), then refuse with MESSAGE. Best effort: the row never changes the refusal. RECORD false (a
    `done --dry-run`) writes no row, so `ops` lists only the refusals of real done runs."""
    try:
        if record:
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


def rerun_done_checks(bl, sid, record=True, ids=None):
    """[(item id, check, exit code)] of each check and bug repro of the sprint's done items, the review story left
    out, that fails when run once more on the checkout as it is (the sprint's tip): a check that passed when its item
    was done and fails now (another item broke it, or it never passed on main) is named before the sprint closes. One
    whose test run selects no test (selected_nothing: a later change deleted the test it names) is said as `gone` and
    not counted, since a done item's check cannot be repointed to a run that passes; a new item's done still refuses
    such a selection as malformed (land_checks). A gone check is found once per sprint: it is recorded in its item's
    evidence (`gone`, saved: the review's done commits it with its own record, close names it in its summary) and is
    not run again at the sprint's next landing. RECORD false (a `done --dry-run`) writes no evidence, so the run that
    commits finds the check gone again and commits its record with the review's. IDS limits the run to those items
    (rerun_sibling_checks)."""
    out = []
    for i in sorted(bl.sprint_items(sid) if ids is None else ids):
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


def rerun_sibling_checks(bl, iid):
    """[(item id, check, exit code)] of each check and bug repro, as rerun_done_checks gives them, of the done items of
    IID's sprint whose touches share a file with IID's scope (bl_plan.touches_meet: a kb/_self doc is no shared file;
    IID's own family is left out): a landing that breaks a sibling's proof is named at its own landing, not at the
    sprint's review. Nothing is recorded: a check found gone is said and not saved. [] for an item outside a sprint
    or with no touches."""
    sid = bl.sprint_of(iid)
    mine = scope(bl, iid)
    if not sid or not mine:
        return []
    family = {iid, *bl.descendants(iid)}
    files = bl_plan.touch_files(bl.root)
    sibs = [i for i in bl.sprint_items(sid)
            if i not in family and bl.items[i].get("status") == "done"
            and any(bl_plan.touches_meet(t, m, files) for t in bl.items[i].get("touches", []) for m in mine)]
    return rerun_done_checks(bl, sid, record=False, ids=sibs) if sibs else []


def land_siblings(bl, iid):
    """The landing's sibling stage: rerun_sibling_checks before done, stopping at step `siblings` and naming each
    item and check that fails, so nothing is pushed for a landing that breaks another item's proof."""
    say("land: sibling checks")
    ops_mark("siblings")
    failed = rerun_sibling_checks(bl, iid)
    if failed:
        raise land_stop("siblings", f"{bl.label(iid)} breaks the proof of a done item of its sprint that shares a "
                                    "file with it; nothing was pushed: "
                                    + "; ".join(f"{bl.label(i)}: {shlex.join(c['run'])} exited {code}"
                                                for i, c, code in failed))


def is_whole_suite(argv):
    """True when the check is a whole-suite tests.py run: the script with no selection (-k, named files, --changed)."""
    argv = [str(x) for x in argv]
    return (len(argv) > 1 and Path(argv[1]).name == "tests.py"
            and all(x == "--no-reuse" for x in argv[2:]))


def loaded_host_for_suite(checks, load=None, cores=None):
    """The line that names this host when a check of CHECKS is a whole-suite tests.py run and the host's 5-minute load
    is over bl_selfcheck.SUITE_LOAD_PER_CORE per core (the load that run no longer fits its seconds ceiling at, which
    selfcheck's host check fails on too), else None. LOAD and CORES stand in for the host's own."""
    if not any(is_whole_suite(c["run"]) for c in checks):
        return None
    import bl_selfcheck  # where selfcheck's host check lives, imported where `done` reads it
    return bl_selfcheck.suite_load_problem(load, cores)


def cmd_done(bl, a):
    t0 = time.monotonic()
    iid = need(bl, a.id)
    it = bl.items[iid]
    kind = it["kind"]
    if kind == "sprint":
        raise Refused("a sprint is closed with backlog.py close")
    reasons = []
    carried = None  # (commit, story id) of the goal research story's commit that stands for the item's work
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
                and not item_commits(bl.root, family)):
            carried = research_carried(bl, iid, mine)
            delivered = [] if carried else delivery_evidence(bl.root, family, globs)
            if carried:  # the goal research story's commit already changed a file of the touches: its checks the proof
                say(f"{bl.label(iid)}: no KB-Work commit of its own; the evidence is {carried[0][:10]}, a commit of the "
                    f"goal research story {bl.label(carried[1])} that changed a file of its touches")
            elif delivered:  # a story of the query-log store only: the delivery is the work, its checks the proof
                say(f"{bl.label(iid)}: no KB-Work commit; the evidence is the automatic query-log delivery "
                    f"{', '.join(delivered[:3])} (trailer KB-Auto: querylog), which its checks read")
            else:
                reasons.append("no-work-commit")
                problems.append(f"no commit on HEAD carries the trailer KB-Work: {iid} or one of its descendants' ids "
                                "and changes a file other than item files (git reads a trailer only in the message's "
                                "last paragraph, with the others; a claim or planning commit is not the work; a goal "
                                "research story needing no outside facts says so in its notes: No outside facts: "
                                "<reason>; a KB-Work commit of the sprint's goal research story that changed a file "
                                "of its touches is its work too)"
                                + ("; the work of an item with `repos` is merged in its repositories, which land reads "
                                   "through their merge requests: run land" if item_repos(it) else "")
                                + ("; a story whose touches are the query-log store only is also done by an automatic "
                                   "querylog.py apply --push commit (trailer KB-Auto: querylog) that changed one of "
                                   "them, on the integration main, authored after the claim: fetch it, then run done "
                                   "again" if store_only(globs) else ""))
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
            leaks = leak_hits(bl.root, commits)
        except Exception as e:  # noqa: BLE001 - a git error is said, not raised
            leaks = []
            say(f"warning: the leak scan could not run: {e}")
        if leaks:
            reasons.append("leaks")
            problems.append("leaks: the leak scan (test_leaks, which the sync gate runs) flags a file the item's commits "
                            "changed: " + "; ".join(f"{path}{f':{n}' if n else ''} ({kind})" for path, n, kind in leaks[:8])
                            + (f"; and {len(leaks) - 8} more" if len(leaks) > 8 else "")
                            + " (use a placeholder, or give the value a reviewed line in _tools/tests_allowlist.txt; the "
                              "value itself is not printed)")
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
        try:
            unrelated = unrelated_baselines(bl, iid, bl.root, commits)
        except Exception as e:  # noqa: BLE001 - a ledger or git error refuses done, naming it, never passes it unchecked
            unrelated = []
            reasons.append("outside-touches")
            problems.append(f"ledger rows: reading _fetch_state.csv, _anchors.csv or their git history failed ({e}); "
                            "repair the ledger, then run done again")
        if unrelated:
            reasons.append("outside-touches")
            problems.append("ledger rows of sources the goal and the facts the item touched do not name: "
                            + "; ".join(f"{sid} ({', '.join(what)})" for sid, what in unrelated[:8])
                            + (f"; and {len(unrelated) - 8} more" if len(unrelated) > 8 else "")
                            + " (restore those rows, or name each source id in the goal: backlog.py set "
                              f"{iid} --goal TEXT)")
    if problems:
        refuse_done(iid, t0, reasons, f"{bl.label(iid)} is not done:\n  " + "\n  ".join(problems), record=not a.dry_run)
    checks = list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else [])
    loaded = loaded_host_for_suite(checks) if it.get("review") else None
    if loaded:  # before the run, which on a loaded host takes minutes and refuses over its seconds ceiling
        refuse_done(iid, t0, ["not-ready"], f"{bl.label(iid)} is not done: {loaded}; run done again once the load has "
                    "fallen (selfcheck's host check names the same limit)", record=not a.dry_run)
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
                    [c["run"] for c, _, _ in failed], record=not a.dry_run)
    try:
        noop_proof(bl, iid, passed)
    except Refused as e:
        refuse_done(iid, t0, ["no-op-proof"], str(e), [c["run"] for c, out in passed if noop_output(out)],
                    record=not a.dry_run)
    if it.get("review"):  # every done item's proof, once more on the sprint's tip: one that fails here does not close
        stale = rerun_done_checks(bl, bl.sprint_of(iid), record=not a.dry_run)
        if stale:  # the gone checks it recorded are committed first, so the next landing does not run them again
            if not a.dry_run:
                commit_written(bl, a, "record gone checks for", iid)
            refuse_done(iid, t0, ["check-failed"], f"{bl.label(iid)} is not done: {len(stale)} check(s) of done items "
                        "fail on the sprint's tip:\n  " + "\n  ".join(f"{bl.label(i)}: `{shlex.join(c['run'])}` exits "
                                                                     f"{code}" for i, c, code in stale)
                        + "\nreopen each (backlog.py reopen ID --why ...) and fix it, or fix its check",
                        [c["run"] for _, c, _ in stale], record=not a.dry_run)
    if a.dry_run:
        say(f"{bl.label(iid)} would be done")
        return 0
    head = git(bl.root, "rev-parse", "HEAD").strip()
    at = carried[0] if carried else head  # a carried item's evidence commit is the research story's, which close names
    it.update(status="done", evidence={"commit": at, **({"carried_by": carried[1]} if carried else {}),
                                       "checks": results, **({"repositories": repos} if repos else {})})
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"done {bl.label(iid)} at {at[:10]}" + ("" if a.commit else f"; commit this with the trailer KB-Work: {iid}"))
    # the run key stays where it is: `landed` means the done commit is on the integration main, which `land` finds
    # (verify) and moves it for, a key still at `claimed` too (no worker started: the orchestrator finished the item itself)
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
    """The push step: the project's `land_push` command, named by its program (`kbgit.py sync --push` for the kb), an
    program word cut to its last part and any other absolute path in it too. A project that names none stops the
    landing here, naming the key."""
    argv = setting("land_push")
    if not argv:
        raise land_stop("push", "the project's backlog.json names no `land_push` (the argument list of the command that "
                                'sends the landed work to the integration main, e.g. ["git", "push", "origin", "HEAD:main"])')
    return (" ".join([Path(argv[0]).name] + [Path(a).name if os.path.isabs(a) else a for a in argv[1:]]), argv)


LAND_TAIL = 30  # output lines shown of a step that passed (sync's report is shown whole)
FETCH_RETRIES = 1  # times land runs a failed git fetch again (a refused key, a timeout) before it stops at that step


# land's ops rows (kb/_self/querylog.md, ops events): a `land.step` row per step, a `land.end` row at every end, and
# after a landing that exited 0 the line `ops_work_rows` gives when the item's work rows are not in the committed work
# sidecars (late, undelivered or missing). Best effort: nothing here changes land's exit or output beyond that line.
LAND_OPS = {"step": None, "t": 0.0, "exit": 0, "lane": None, "item": None}


def ops_token(label):
    """A step label as an ops token: lower case, every run of other characters one `-`, at most 40 characters."""
    return re.sub(r"[^a-z0-9_.]+", "-", label.lower()).strip("-")[:40] or "step"


def ops_write(**fields):
    """Append a land ops row (`ql_deliver.ops_row`: nothing inside a test run or in a probe from another working
    directory, so a fixture's landing never reaches the clone's spool); a landing never fails for its log."""
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


PUSH_LOG_TAIL = 200_000  # bytes of the end of a store's distill.log read for the last `apply --push`
PUSH_FAILED = re.compile(r"apply --push: (?:kbgit\.py sync exit [1-9]|refused|commit failed|conflict|the worktree|the push was refused|the revert of|git clone|the findings a|.*nothing pushed)")
PUSH_DONE = re.compile(r"apply --push: (?:pushed [0-9a-f]+ to |nothing to push)")
PUSH_GATE = re.compile(r"\s+gate (.+?): FAILED(?: \(exit \d+\))?: (.*)")  # check-trailers' FAILED has no exit
PUSH_GATE_OUTPUT = re.compile(r"\s+gate (.+?) whole output: (.+) \(\d+ test ids\)")
GATE_OUTPUT_READ = 200_000  # bytes of the start of a gate's kept output file read for its first error line
GATE_ERROR_LINE = re.compile(r"(?:ERROR|FAILED)\b|E {2,}\S|[A-Za-z_.]+(?:Error|Exception): ")


def gate_first_error(path):
    """The first error line (`ERROR ...`, `FAILED ...`, a pytest `E` line or an `...Error: ...` line, up to 200
    characters) of the failed gate's whole output that `kg_sync.gate_output_file` kept at PATH under `_cache/gate`;
    None when PATH is no such file, cannot be read, or holds no such line."""
    p = Path(path)
    if p.parent.name != "gate" or p.parent.parent.name != "_cache":
        return None
    try:
        with open(p, "rb") as f:
            text = f.read(GATE_OUTPUT_READ).decode("utf-8", errors="replace")
    except OSError:
        return None
    for ln in text.splitlines():
        ln = ln.strip()
        if GATE_ERROR_LINE.match(ln):
            return re.sub(r"^E {2,}", "", ln)[:200]
    return None


def last_push_failure(store):
    """The phrase naming why the last `apply --push` the distill.log beside STORE records delivered nothing: its first
    failed gate and that gate's first error line (`gate check.py: ERROR ...`, with the count of the other failed
    gates; the first error line of the output file the log names for that gate, else the gate's summary line, which
    holds only the last line its output ended in; check-trailers' summary line has no exit code), else the line that
    stopped it; None when its last outcome is a push or nothing to push, or the log has none or cannot be read."""
    try:
        from ql_distill import LOG_NAME
        log = Path(store).parent / LOG_NAME
        with open(log, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - PUSH_LOG_TAIL))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, ImportError):
        return None
    for i in range(len(lines) - 1, -1, -1):
        if PUSH_DONE.match(lines[i]):
            return None
        if not PUSH_FAILED.match(lines[i]):
            continue
        gates, kept, j = [], {}, i - 1
        while j >= 0 and lines[j].startswith("  "):
            m = PUSH_GATE.fullmatch(lines[j])
            if m:
                gates.insert(0, m.groups())
            m = PUSH_GATE_OUTPUT.fullmatch(lines[j])
            if m:
                kept[m[1]] = m[2]
            j -= 1
        if gates:
            name, first = gates[0]
            first = (gate_first_error(kept[name]) if name in kept else None) or first
            more = f", and {len(gates) - 1} other gate(s) failed" if len(gates) > 1 else ""
            return f"gate {name}: {first[:200]}{more}"
        return lines[i][len("apply --push: "):][:200]
    return None


def ledger_worker_session(root, iid):
    """The `worker_session` that `dispatch` recorded for IID in this working tree's claims ledger
    (`bl_dispatch.record_worker`, a file in the git dir), or None: no ledger, no record or no session in it."""
    ledger = claims_ledger(root)[1]
    try:
        rec = json.loads(Path(ledger).read_text(encoding="utf-8")).get(iid) if ledger else None
    except (OSError, ValueError, AttributeError):
        return None
    session = rec.get("worker_session") if isinstance(rec, dict) else None
    return session if isinstance(session, str) and session else None


def missing_reasons(root, iid, ids, seen, where):
    """[phrase] why no worker's row of the item is in a spool (`ops_work_rows`' missing case). SEEN is {session id:
    (spool directory, session)} of every session the spools hold (`ql_distill.read_spool`). The session `dispatch`
    recorded for the item says what its spool file is: absent from every spool read, or there and open or closed
    and not distilled, with no `branch`, `agent-start` or `agent-stop` row naming the item. A `claim` row of the item
    in another session says it was claimed, and worked, in the orchestrator's own session: its window (the prompts
    from the claim to the done, `ql_distill.work_windows`) is the item's in `backlog.py cost` once that session has
    closed and distill has run. Empty when neither is found."""
    def state(s):
        return "closed and not distilled" if s["closed"] else "still open"

    out, worker = [], ledger_worker_session(root, iid)
    if worker:
        if worker in seen:
            d, s = seen[worker]
            out.append(f"dispatch recorded worker session {worker[:8]} for it: its spool file {d / (worker + '.jsonl')} "
                       f"is {state(s)} and holds no branch, agent-start or agent-stop row naming it (its first prompt "
                       f"was not on `work/{iid}` with the item doing, or the capture hooks did not run there)")
        else:
            out.append(f"dispatch recorded worker session {worker[:8]} for it: no spool file of it in {where}, so the "
                       "capture hooks did not write it or distill already took it and no committed work sidecar "
                       "names the item")
    for sid in sorted(seen):
        d, s = seen[sid]
        if sid != worker and any(r.get("surface") == "work" and r.get("item") in ids and r.get("action") == "claim"
                                 for r in s["rows"]):
            out.append(f"it was claimed and worked in the orchestrator's own session {sid[:8]} ({state(s)} in {d}): "
                       f"`backlog.py cost {iid}` attributes the prompts of that claim's window, from the claim to the "
                       "done, once the session has ended and distill has run")
    return out


def distill_in_flight(spools):
    """[phrase] naming each distill that holds the lock (`ql_base.LOCK_NAME`, not older than `ql_base.LOCK_STALE_S`) of
    the query log directory beside a spool of SPOOLS, with its pid and age: a session-end distill takes its session's
    spool file under that lock and delivers the sidecar when it is done. Empty when no such lock is held."""
    import ql_base
    out = []
    for d in spools:
        lock = d.parent / ql_base.LOCK_NAME
        age = ql_base.lock_age(lock)
        if age is None or age >= ql_base.LOCK_STALE_S:
            continue
        pid = ql_base.read_json(lock, {}).get("pid")
        out.append(f"a distill{f' (pid {pid})' if pid else ''} holds the lock of {d.parent}, taken {int(age)}s ago")
    return out


def ops_work_rows(root, iid):
    """[line] the landing of IID says about its work rows, none when nothing is amiss. A line of the committed work
    sidecars (`bl_cost.cost_lines`) that names the item or a descendant of it ends it: the rows are delivered. Else
    the clone's spool and the main worktree's (`bl_cost.spool_dirs`; read only: a session started in the main checkout
    that orchestrates a clone writes its rows there) and the local store beside each (`<spool>/../store`, where distill
    writes the sidecars before `querylog.py apply --push` delivers them) are read:
    - a work sidecar of a local store that names the item and that neither the checkout's `kb/_querylog` nor the
      integration main holds: `warning: ... undelivered`, naming the store and its count of sidecars (a session end
      left it unpushed) and, from the store's distill.log, why its last `apply --push` delivered nothing
      (`last_push_failure`), and nothing more;
    - a worker's row of the item in a spool, a `branch` row (the row that opens a headless worker's window,
      `ql_capture.BRANCH_ACTION`) or an `agent-start` or `agent-stop` row (`ql_capture.AGENT_ACTIONS`: a worker
      started with the Agent tool runs inside the orchestrator's session and writes those, never a `branch` row), is
      no warning: its session is open or not distilled yet, so its rows are late, said as a `land:` line naming the
      session and its state;
    - none of these while a distill holds the lock of a spool read (`distill_in_flight`: the worker's session-end
      distill has taken its spool file and not yet delivered the sidecar): the same `land:` line, naming the distill;
    - none of these: `warning: ... missing`, the line a worker that ran without the capture hooks leaves, with the
      reasons `missing_reasons` finds: the state of the spool file of the session `dispatch` recorded for the item,
      and a `claim` row of the item in the orchestrator's own session. The orchestrator's own `claim`, `done` and
      `release` rows are no worker's: it claims every item it delegates, so its row would always be met.
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
        late, seen = [], {}
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
                why = last_push_failure(store)
                return [f"warning: {iid} landed with no work rows on {remote}/main (undelivered): {store} holds "
                        f"{len(held)} work sidecar(s) naming it that {remote}/main lacks, a session end left the "
                        f"store unpushed (`python3 _tools/querylog.py apply --push` delivers it)"
                        + (f"; its last run did not deliver, {why}" if why else "")]
        spools = [d for d in dirs if d.is_dir()]
        if not spools:
            return []
        worker_actions = (ql_capture.BRANCH_ACTION, *ql_capture.AGENT_ACTIONS)
        for d in spools:
            for sid, s in sorted(ql_distill.read_spool(d, time.time())[0].items()):
                seen.setdefault(sid, (d, s))
                if any(r.get("surface") == "work" and r.get("item") in ids and r.get("action") in worker_actions
                       for r in s["rows"]):
                    late.append(f"session {sid[:8]} of it is {'closed and not distilled' if s['closed'] else 'still open'}"
                                f" in {d}")
        if late:
            return [f"land: {iid}'s work rows are late: {'; '.join(late)}; `backlog.py cost` shows its figures once "
                    "the session has ended and distill has run"]
        flight = distill_in_flight(spools)
        if flight:
            return [f"land: {iid}'s work rows are late: no spool file of its worker is left to read and {'; '.join(flight)}"
                    f"; `backlog.py cost` shows its figures once that distill has delivered the sidecar"]
        where = ", ".join(str(d) for d in spools)
        why = missing_reasons(root, iid, ids, seen, where)
        if why:
            return [f"warning: {iid} landed with no work rows (missing): no worker session of it left a branch, "
                    f"agent-start or agent-stop row in {where} and no committed work sidecar names it; "
                    + "; ".join(why)]
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


# a gate's kept whole-output file, as a failed step names it: an absolute path after `: ` (it may hold spaces, and
# backslashes under Windows), else any one word
GATE_KEPT_PATH = re.compile(r"(?<=: )(?:/|[A-Za-z]:[\\/])[^\n]*?[\\/]_cache[\\/]gate[\\/][^\\/\s]+|\S+[\\/]_cache[\\/]gate[\\/][^\\/\s]+")


def keep_gate_outputs(root, keep_to, out):
    """OUT, the output of a failed landing step run in the landing worktree ROOT, with each kept gate output file it
    names under ROOT's `_cache/gate` copied to the same directory of KEEP_TO (the invoking checkout, which outlives
    the landing worktree) and its path there. A copy, not a move: a retry reads the same name. A path that is no file
    under ROOT's `_cache/gate`, or cannot be copied, stays as the step printed it."""
    gate = (Path(root) / "_cache" / "gate").resolve()
    keep = Path(keep_to) / "_cache" / "gate"

    def copy(m):
        src = Path(m[0])
        try:
            if not src.is_file() or src.resolve().parent != gate or keep.resolve() == gate:
                return m[0]
            keep.mkdir(parents=True, exist_ok=True)
            return str(Path(shutil.copy2(src, keep / src.name)))
        except OSError:
            return m[0]
    return GATE_KEPT_PATH.sub(copy, out)


def land_run(root, step, argv, whole=False, program=False, keep_to=None):
    """Run one landing step; its output (the tail of it, unless WHOLE or it failed) goes through say(). The steps
    are Python scripts run under this interpreter; with PROGRAM an ARGV whose first element does not end in `.py` is
    the program to run itself (the push step's `git push ...`). A step that failed in ROOT, a landing worktree that
    goes with the run, has its kept gate output files copied to KEEP_TO's `_cache/gate` and named there."""
    say(f"land: {step}")
    ops_mark(step)
    own = not program or argv[0].endswith(".py")
    try:
        p = subprocess.run([sys.executable, *argv] if own else argv, cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=colourless_env())
        code, out = p.returncode, ANSI_RE.sub("", (p.stdout or "") + (p.stderr or "")).rstrip()
    except OSError as e:
        code, out = None, f"cannot start: {e}"
    if code and keep_to is not None:
        out = keep_gate_outputs(root, keep_to, out)
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


def land_git_fetch(root, step, *args):
    """A git fetch through land_git_network, run again FETCH_RETRIES times after a failure (a refused key, a timeout:
    the two that stopped landings at step fetch and passed when run again minutes later); the last failure is the
    result, a timeout the last one's land_stop."""
    for attempt in range(FETCH_RETRIES + 1):
        last = attempt == FETCH_RETRIES
        try:
            p = land_git_network(root, step, *args)
        except Refused as e:
            if last:
                raise
            say(f"land: git fetch failed ({e}); running it again")
            continue
        if p.returncode == 0 or last:
            return p
        say(f"land: git fetch failed ({(p.stderr or p.stdout).strip()}); running it again")


def land_git(root, step, *args):
    if args and args[0] == "fetch":
        p = land_git_fetch(root, step, *args)
    elif args and args[0] in ("push", "ls-remote"):
        p = land_git_network(root, step, *args)
    else:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise land_stop(step, f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


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


RepoLand = namedtuple("RepoLand", "name checkout worktree upstream tip evidence")
# a repository of a multi-repository item that land has read: its checkout, its worktree (None when none is made),
# the default branch's remote ref after a fetch, the tip of its work/<id> branch ("" when it has none) and its
# evidence, {"request": the merge request's url or !iid, "commit": the merge commit ("" when none is found)}


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
    repository's merge request, the one titled `<id>:` (the text of the `naming` setting's mr_title up to its
    `{title}`, `repo_title_prefix`), is read once through bl_forge in its own checkout; one that is
    not merged (or none, or one that cannot be read) stops the land at step `requests` naming the repository and its
    state, every repository in one message. When all are merged, each repository's origin is fetched and its default
    branch read, every worktree dispatch made (`repo_worktree`) is checked first (a dirty, locked or live-process one
    stops the land at step `repositories` naming it, with nothing removed) and then removed, never with --force; the
    branches are deleted once the item has landed (`delete_repo_branches`)."""
    names = item_repos(bl.items[iid])
    if not names:
        return []
    import bl_forge
    prefix, branch = repo_title_prefix(bl.items[iid], iid), repo_branch(bl.items[iid], iid)
    root = bl.root
    say(f"land: requests: {iid}: of {', '.join(names)}")
    ops_mark("requests")
    found, bad = [], []
    for name in names:
        checkout = Path(root) / repositories()[name]
        try:
            request = bl_forge.read_request(checkout, title_prefix=prefix, run=run)
        except (Refused, bl_forge.ForgeError) as e:
            bad.append(f"repository {name!r} ({checkout}): the merge request cannot be read: {e}")
            continue
        found.append((name, checkout, request))
        if request is None:
            bad.append(f"repository {name!r}: no merge request titled '{prefix}' (state none)")
        elif request.state != "merged":
            bad.append(f"repository {name!r}: merge request !{request.iid} ({request.url or 'no url'}) is "
                       f"{request.state}, not merged")
    if bad:
        raise land_stop("requests", "; ".join(bad) + "; nothing was removed or changed: merge each, then run land again")
    ops_mark("repositories")
    staged, held = [], []
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
                                      check_only=True, iid=iid) if entry else None
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


def delete_repo_branches(repos, iid, branch=None):
    """Delete each repository's BRANCH (the `naming` branch, `repo_branch`; `work/<id>` by default) once the item has landed, when `git cherry` shows every commit of it on the
    repository's default branch (delete_landed_branch: a squashed or unmerged one is kept, and said). Returns the
    names of the repositories whose branch it deleted."""
    branch = branch or WORK_PREFIX + iid
    return [r.name for r in repos if r.tip and delete_landed_branch(r.checkout, branch, r.upstream, prefixes=(branch,),
                                                                    who=f"land: repository {r.name}")]


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
    path) or the forge cannot be read (a CLI not signed in, a failed or unreadable call): land cannot tell. A project
    with no forge (an empty `forge` setting) has no request to read: land says so and reads nothing."""
    import bl_forge
    if bl_forge.no_forge():
        say(f"land: {bl_forge.NO_FORGE}")
        return None
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
    return rebase_merging_doc_rows(root, upstream, branch, onto=tip)


DOC_ROW_FILE = re.compile(r"kb/_self/[^/]+\.md\Z")
WORD_RE = re.compile(r"\s*\S+\s*")


def merge_line_hunks(base, ours, theirs):
    """BASE's line with the changes of OURS and THEIRS both made, word by word (each word keeps its trailing
    whitespace), or None when the two changed the same words or touching ones, or a line is not whole words."""
    import difflib
    words = {name: WORD_RE.findall(text) for name, text in (("b", base), ("o", ours), ("t", theirs))}
    if any("".join(words[name]) != text for name, text in (("b", base), ("o", ours), ("t", theirs))):
        return None
    changes = []  # (start, end, replacement words) in BASE's words
    for side in ("o", "t"):
        sm = difflib.SequenceMatcher(None, words["b"], words[side], autojunk=False)
        changes += [(i1, i2, tuple(words[side][j1:j2])) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]
    changes = sorted(set(changes))  # a change both sides made the same way counts once
    out, at = [], 0
    for n, (i1, i2, repl) in enumerate(changes):
        if n and i1 <= changes[n - 1][1]:  # overlaps or touches the change before it
            return None
        out += words["b"][at:i1] + list(repl)
        at = i2
    return "".join(out + words["b"][at:])


CONFLICT_HUNK = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^\|\|\|\|\|\|\| [^\n]*\n(.*?)^=======\r?\n(.*?)^>>>>>>> [^\n]*\n",
                           re.M | re.S)


def merged_doc_hunks(text, final_newline=True):
    """(TEXT with each diff3 conflict hunk merged line by line, the merged lines), or None when a hunk's sides do not
    hold the same number of lines or one line's words clash. A text with no hunk is None. Lines end at a line feed
    only, so a carriage return stays on its line and a U+2028, U+0085 or form feed inside one never splits it. FINAL_NEWLINE says whether
    the doc's sides end in a newline (git writes one after the last conflict line either way): False takes the
    one it added off a hunk at the end of TEXT, None (the sides differ) refuses such a hunk."""
    merged = []
    ends = []

    def one(m):
        ours, base, theirs = (part.split("\n")[:-1] for part in m.groups())
        if not base or not len(base) == len(ours) == len(theirs):
            raise ValueError("not line for line")
        lines = [merge_line_hunks(*trio) for trio in zip(base, ours, theirs)]
        if None in lines:
            raise ValueError("same words")
        if m.end() == len(text):
            if final_newline is None:
                raise ValueError("final newline differs")
            ends.append(final_newline)
        merged.extend(lines)
        return "".join(line + "\n" for line in lines)
    try:
        out = CONFLICT_HUNK.sub(one, text)
    except ValueError:
        return None
    if ends == [False]:
        out = out[:-1]
    return (out, merged) if merged and not re.search(r"^(<<<<<<<|=======|>>>>>>>)", out, re.M) else None


def stages_end_in_newline(root, name):
    """True when every side of the conflicted file NAME in the index (base, ours, theirs; a side the file lacks is
    skipped) ends in a newline, False when none does, None when they differ or no side can be read."""
    ends = []
    for stage in (1, 2, 3):
        p = subprocess.run(["git", "show", f":{stage}:{name}"], cwd=root, capture_output=True)
        if p.returncode == 0 and p.stdout:
            ends.append(p.stdout.endswith(b"\n"))
    return ends[0] if ends and len(set(ends)) == 1 else None


def read_whole_doc(path):
    """PATH's text exactly as stored (no newline translation), or None when it is not UTF-8."""
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None


def rebase_merging_doc_rows(root, upstream, branch, onto=None):
    """`git rebase UPSTREAM BRANCH` (`--onto ONTO` with it): where it stops only on kb/_self/*.md lines both sides
    changed at different words (a table row, a one-line paragraph), the lines are merged word by word keeping both
    sides, said, and the rebase continues. A conflict on the same words or in another file, or a doc that is not
    UTF-8, is aborted, nothing changed; the process returned is the failed one. A merged doc keeps every byte
    outside the merged words (its line endings and whether it ends in a newline)."""
    def git_run(*args):
        return subprocess.run(["git", "-c", "merge.conflictStyle=diff3", "-c", "core.editor=true", *args], cwd=root,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env={**os.environ, "GIT_EDITOR": "true"})
    p = git_run("rebase", "--quiet", *(["--onto", onto] if onto else []), upstream, branch)
    while p.returncode:
        files = git_run("diff", "--name-only", "--diff-filter=U").stdout.split()
        fixed = {}
        for name in files:
            text = read_whole_doc(Path(root) / name) if DOC_ROW_FILE.match(name) else None
            result = None if text is None else merged_doc_hunks(text, stages_end_in_newline(root, name))
            if result is None:
                break
            fixed[name] = result
        if not files or len(fixed) < len(files):
            git_run("rebase", "--abort")
            p.conflicts = files  # the paths that clashed, for the stop's message (the abort has cleared them)
            return p
        for name, (text, lines) in fixed.items():
            (Path(root) / name).write_text(text, encoding="utf-8", newline="\n")
            git_run("add", "--", name)
            for line in lines:
                say(f"land: merged the line of {name} word by word, both sides kept: {line}")
        p = git_run("rebase", "--continue")
    return p


def conflict_owners(root, upstream, branch, files):
    """[(path, ids of the `KB-Work` commit that last changed it on UPSTREAM since the branch's merge base, its short
    sha)] for each of FILES; ids and sha are empty when no such commit changed it."""
    out = subprocess.run(["git", "merge-base", upstream, branch], cwd=root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    span = f"{out.stdout.strip()}..{upstream}" if out.returncode == 0 and out.stdout.strip() else upstream
    owners = []
    for name in files:
        log = subprocess.run(["git", "log", "--format=%x1e%h%x1f%(trailers:key=KB-Work,valueonly,separator=%x2c)",
                              span, "--", name], cwd=root, capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
        found = ("", "")
        for record in log.stdout.split("\x1e"):
            sha, _, ids = record.partition("\x1f")
            ids = ", ".join(i.strip() for i in ids.replace("\n", ",").split(",") if i.strip())
            if sha.strip() and ids:
                found = (ids, sha.strip())
                break
        owners.append((name, *found))
    return owners


def rebase_conflict_text(root, upstream, branch, iid, remote, files):
    """The lines a rebase stop adds: each conflicting path with the item that last changed it on the integration
    main, and the remedy that sends the worker back."""
    lines = []
    for name, ids, sha in conflict_owners(root, upstream, branch, files):
        lines.append(f"  {name}: last changed on {remote}/main by {ids} (commit {sha})" if ids else
                     f"  {name}: no KB-Work commit on {remote}/main changed it since {branch} was cut")
    head = "conflicting file(s):\n" + "\n".join(lines) + "\n" if lines else ""
    return (f"{head}remedy: write the conflict to a file as the message (the paths above, what {remote}/main changed "
            f"in them), then `backlog.py dispatch --resume {iid} --message FILE` sends the worker back to rebase "
            f"{branch} on {remote}/main and resolve it, then run land again\n")


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
    when it is not: a sync that gave up quietly must never end in `landed`. The check is a step of its own in the ops
    rows (`land.step` `verify`), so a stop here is named by a row with exit 1 and not left to the push row."""
    ops_mark("verify")
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


def local_only(root, base, tip, names=False):
    """[(sha, subject)] of the commits TIP has that BASE lacks, a commit whose patch BASE holds under another hash
    left out (`git log --cherry-pick --right-only BASE...TIP`), oldest first; with NAMES the paths those commits change
    too: [(sha, subject, [paths])]. [] when git cannot say: a note about the checkout never stops a landing."""
    p = subprocess.run(["git", "log", "--cherry-pick", "--right-only", "--reverse", "--no-renames", "--name-only",
                        "--format=%x1e%H%x00%s", f"{base}...{tip}"], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = []
    for rec in (p.stdout.split("\x1e")[1:] if p.returncode == 0 else []):
        head, _, files = rec.partition("\n")
        sha, _, subject = head.partition("\x00")
        out.append((sha, subject, [f for f in files.splitlines() if f]) if names else (sha, subject))
    return out


NAMED_COMMITS = 8  # commits listed when land names the starting checkout's unpushed ones; the rest are counted


def name_unpushed(root, remote, start, start_ref, upstream, branch):
    """Before the push, say which commits the checkout `land` started on holds that are not on the integration main,
    and which of them the push carries: the push is the item's BRANCH alone (the claim commits under it among them),
    so a commit of the checkout that the branch lacks stays local, and `fast_forward_start` deals with it after. Said
    once, nothing when there are none or the checkout is on BRANCH itself."""
    if start_ref == f"refs/heads/{branch}":
        return
    held = local_only(root, upstream, start)
    if not held:
        return
    stays = {sha for sha, _ in local_only(root, branch, start)}
    name = start_ref[len("refs/heads/"):] if start_ref.startswith("refs/heads/") else f"detached HEAD {start[:10]}"
    say(f"land: {name} holds {len(held)} commit(s) not on {remote}/main; the push carries only {branch}, "
        f"{sum(1 for sha, _ in held if sha in stays)} of them stay local:")
    for sha, subject in held[:NAMED_COMMITS]:
        say(f"  {sha[:10]} {subject} ({'stays local' if sha in stays else 'goes with ' + branch})")
    if len(held) > NAMED_COMMITS:
        say(f"  ... and {len(held) - NAMED_COMMITS} more")


def rebase_local(root, remote, name, behind, upstream):
    """Diverged: the checkout on NAME is BEHIND commits behind the integration main and holds commits of its own. When
    those (the ones UPSTREAM lacks by patch) change item files only and none is a merge, `git rebase` puts them on the
    pushed main and says so; otherwise, or when the rebase conflicts (it is aborted, nothing changed), the one command
    is named and the checkout left alone."""
    ahead = git(root, "rev-list", "--count", f"{upstream}..HEAD").strip()
    merges = git(root, "rev-list", "--merges", "--count", f"{upstream}..HEAD").strip() != "0"
    other = [p for _, _, paths in local_only(root, upstream, "HEAD", names=True) for p in paths if not item_file(p)]
    left = f"land: left {name} {behind} commit(s) behind {remote}/main: it holds {ahead} local commit(s) "
    command = f"git rebase {remote}/main"
    if merges or other:
        why = "a merge commit among them" if merges else f"one changes {other[0]}, not an item file"
        say(f"{left}that it will not rebase on its own ({why}; {command})")
        return
    p = subprocess.run(["git", "rebase", "--quiet", upstream], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode:
        subprocess.run(["git", "rebase", "--abort"], cwd=root, capture_output=True)
        say(f"{left}that do not rebase cleanly (rebase aborted, nothing changed; {command})")
    else:
        say(f"land: rebased {name}'s {ahead} local commit(s), item files only, onto {remote}/main "
            f"({behind} commit(s) behind it; nothing pushed by the rebase)")


def fast_forward_start(root, remote, start_ref, upstream):
    """After a pushed landing, bring the checkout `land` started on level with the integration main: `git merge
    --ff-only` when it is on a branch whose `@{upstream}` is REMOTE/main and has no change to a tracked file (untracked
    files are git's to judge: they stay, and one the merge would overwrite is named in the said reason); a checkout
    that has diverged because it holds commits of its own that change item files only is rebased on it
    (`rebase_local`). Anything else is left alone and said, and the exit status never depends on it: the next `claim
    --commit` must start from the pushed main, and a refusal here only costs a manual fast-forward."""
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
    if git(root, "status", "--porcelain", "--untracked-files=no").strip():
        say(f"land: left {name} {behind} commit(s) behind {remote}/main: it has uncommitted changes "
            f"(git merge --ff-only {remote}/main once they are committed)")
        return
    p = subprocess.run(["git", "merge", "--ff-only", "--quiet", upstream], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode == 0:
        say(f"land: fast-forwarded {name} {behind} commit(s) to {remote}/main")
    elif git(root, "rev-list", "--count", f"{upstream}..HEAD").strip() != "0":
        rebase_local(root, remote, name, behind, upstream)
    else:
        lines = (p.stderr or p.stdout).strip().splitlines()
        colliding = []
        if any("untracked working tree files would be overwritten" in ln for ln in lines):
            colliding = [ln.strip() for ln in lines if ln.startswith(("\t", " ")) and ln.strip()]
        if colliding:
            why = (f"untracked file(s) it would overwrite: {', '.join(colliding[:5])}"
                   f"{f' and {len(colliding) - 5} more' if len(colliding) > 5 else ''}; "
                   f"move them, then git merge --ff-only {remote}/main")
        else:
            why = (lines or ["diverged"])[-1]
        say(f"land: left {name} {behind} commit(s) behind {remote}/main: it cannot fast-forward ({why})")


def changed_articles(changed):
    """The qualified paths (`<root>/<path in the root>`, as lint.py takes them) of the .md files CHANGED (repository
    paths) holds under a kb root, in order."""
    return ["/".join(parts[1:]) for parts in (p.split("/") for p in changed)
            if len(parts) > 2 and parts[0] == "kb" and parts[-1].endswith(".md")]


def changes_kb(changed):
    """True when CHANGED (repository paths) holds any file under a kb root, item files, coverage files and ledgers
    included. The query log store (`kb/_querylog`) is no kb root: `querylog.py apply --push` delivers it without
    `land`, and a landing that carries only its files runs no eval."""
    return any(len(parts) > 2 and parts[0] == "kb" and parts[1] != "_querylog"
               for parts in (p.split("/") for p in changed))


def worktree_back(root, released, branch, iid):
    """The lines a stop of land adds once it removed the worker worktrees RELEASED: the `git worktree add` command
    that checks BRANCH out again at each one's path, so the fix is made there and land run again (which removes it
    again). The path is relative to ROOT, the checkout the command runs in: every line backlog.py prints withholds
    the user's name, which an absolute path under a home directory holds. Empty when none was removed."""
    def where(path):
        try:
            return Path(os.path.relpath(path, root)).as_posix()
        except ValueError:  # another drive (Windows): no relative path
            return str(path)
    return "".join(f"\nland removed the worker's worktree {where(path)}; to fix {branch} there, check it out again "
                   f"from this checkout, then run backlog.py land {iid} again:\n"
                   f"  git worktree add {shlex.quote(where(path))} {branch}" for path in released)


def stop_with_worktree_back(text, back):
    """TEXT, a stop's message, with BACK (`worktree_back`) put before its `remedy:` line when it has one, else after
    it: the remedy sends the worker to the worktree, so the `git worktree add` that makes it exist is read first."""
    found = re.search(r"^remedy: ", text, re.M)
    if not back or not found:
        return text + back
    return f"{text[:found.start()]}{back.lstrip(chr(10))}\n{text[found.start():]}"


def land_once(bl, a):
    """Land a finished item's branch under the clone's landing lock (`bl_close.landing_lock`: landings of one clone run
    one at a time, a second one says which item holds the lock and waits): `land_locked`."""
    need(bl, a.id)
    with landing_lock(bl.root, a.id):
        return land_locked(bl, a)


def land_locked(bl, a):
    """Land a finished item's branch: rebase it on the integration main, then by lane. Content: done --commit, the
    heavy checks when _tools/ changed (else the lookup eval when any file under a kb root changed, and the lint on
    the changed articles), sync --push. Code not yet on the integration main: the item's checks and
    a bug's repro, the heavy checks, sync --push (a code/<id> merge request; main does not move), and a re-run once
    it has merged finishes it as content does. Stops at the first failing step, naming it. The fetch, the rebase, done, the checks and the push run in a landing
    worktree of land's own (`bl_close.add_landing_worktree`, `land-<id>` under the worker directory, made detached at
    the commit the checkout land was started in has), removed at every end: the checkout land was started in is never
    switched or read for its working tree, so an untracked or modified file there does not stop a landing. A landing
    from the checkout that has the item's branch itself checked out (or of a multi-repository item) runs in that
    checkout as ever: it must be clean, and every run and every stop ends on the branch (or the detached commit) it
    started on, as a claim --commit made after land must not ride on the landed branch into its merge request."""
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
    start = git(root, "rev-parse", "HEAD").strip()
    start_ref = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.strip()
    in_place = start_ref == f"refs/heads/{branch}" or bool(item_repos(bl.items[iid]))
    if in_place and git(root, "status", "--porcelain").strip():
        raise land_stop("clean tree", "uncommitted changes: commit or stash them first (git status --short)")
    if not has_ref(root, f"refs/heads/{branch}"):
        raise land_stop("branch", f"no local branch {branch} (--branch names another)")
    repos = land_repositories(bl, iid)  # a multi-repository item: each repository's request merged, worktrees removed
    leftover = landing_worktree_path(root, iid)  # an earlier killed landing's (the lock is ours): it may hold the branch
    if leftover.exists() and leftover.resolve() != Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve():
        remove_landing_worktree(root, leftover)
    other = checked_out_elsewhere(root, branch)
    agent_branch = None
    released = []  # the worker worktrees this run removed: a stop after that names how to check the branch out again
    if other:  # a finished worker's clean worktree, locked by Claude Code or an unlocked agent-*, is removed
        why = release_worker_worktree(root, *other, branch=branch)
        if why:
            raise land_stop("branch", f"{branch} is checked out in the worktree {other[0]} and {why}: land it from "
                                      "there, or remove that worktree first")
        agent_branch = AGENT_BRANCH + other[0].name  # the Agent tool's branch of that worktree, deleted once landed
        released.append(other[0])
    else:  # a worker detached at the branch's tip holds no branch: remove it too, and go on when it has to stay
        for path, lock in detached_workers(root, branch):
            why = release_worker_worktree(root, path, lock, branch=branch)
            if why:
                say(f"land: kept the worktree {path}: {why}")
            else:
                agent_branch = AGENT_BRANCH + path.name
                released.append(path)
    lroot, landing = root, None  # where the landing runs: a landing worktree of its own, else this checkout
    try:
        if not in_place:
            landing = lroot = add_landing_worktree(root, iid, start)
            bl = Backlog(lroot)
        with kg_lock.guarded("backlog.py land: fetch and rebase", "backlog.py", clone=str(root)):
            say(f"land: fetch {remote} main")
            ops_mark("fetch")
            land_git(lroot, "fetch", "fetch", "--quiet", remote, f"+refs/heads/main:{upstream}")
            say(f"land: rebase {branch} on {remote}/main")
            ops_mark("rebase")
            claims = missing_claims(lroot, [iid] + bl.descendants(iid), start, upstream, branch)
            if claims:  # claimed after the branch was cut, or never pushed: the claim goes under the worker's commits
                say(f"land: carry the claim commit(s) {', '.join(c[:10] for c in claims)} under {branch}")
                p = carry_claims(lroot, claims, upstream, branch)
            else:
                p = rebase_merging_doc_rows(lroot, upstream, branch)
        if p.returncode:
            subprocess.run(["git", "rebase", "--abort"], cwd=lroot, capture_output=True)
            raise land_stop("rebase", f"{branch} does not rebase cleanly on {remote}/main (rebase aborted, nothing "
                                      f"changed)\n"
                                      f"{rebase_conflict_text(lroot, upstream, branch, iid, remote, getattr(p, 'conflicts', []))}"
                                      f"{(p.stderr or p.stdout).strip()}")
        bl = Backlog(lroot)  # the item files as the rebased branch has them
        need(bl, iid)
        family = [iid] + bl.descendants(iid)
        late, _, owners = unlanded_code(lroot, family)
        LAND_OPS["lane"] = "code" if late else "content"
        if late == ["(no such ref)"]:
            raise land_stop("fetch", f"{upstream} does not exist after the fetch")
        if late:
            code_branch = sync_code_branch(lroot, upstream, owners, iid)  # the branch sync --push opens for this range
            tracking = f"refs/remotes/{remote}/{code_branch}"
            fetched = land_git_network(lroot, "fetch", "fetch", "--quiet", remote,
                                       f"+refs/heads/{code_branch}:{tracking}").returncode == 0
            if fetched and git(lroot, "rev-parse", f"{tracking}^{{tree}}") == git(lroot, "rev-parse", "HEAD^{tree}"):
                say(f"land: {bl.label(iid)} waits for its merge request (branch {code_branch} on {remote}, already "
                    f"pushed with this content): merge it, then run backlog.py land {iid} again")
                LAND_OPS["pending"] = ([git(lroot, "rev-parse", tracking).strip()], code_branch)
                request = read_code_request(lroot, code_branch)  # the pass's one read of the request
                describe_merge_request(bl, iid, request)
                stuck = stuck_merge_request(request, code_branch)
                if stuck:
                    say(stuck)
                return 0
        if not late:
            if bl.items[iid].get("status") == "done":
                say(f"land: done: {bl.label(iid)} is done already")
            elif restore_done(lroot, iid):  # a run before this one made the done commit and the branch lost it
                say(f"land: done: {bl.label(iid)} has its done commit from the last run ({LAND_REF}/{iid}), "
                    "not run again")
            else:
                land_siblings(bl, iid)
                say("land: done --commit")
                ops_mark("done")
                try:
                    cmd_done(bl, argparse.Namespace(id=iid, dry_run=False, commit=True, trailer=a.trailer,
                                                    repositories=repo_evidence(repos)))
                except Refused as e:
                    raise land_stop("done", str(e)) from None
                land_git(lroot, "done", "update-ref", f"{LAND_REF}/{iid}", "HEAD")
        if late:  # the code lane pushes an auto-merging merge request: its proof runs before that, not after
            if not getattr(a, "wait_merge", None):  # a two-pass landing is read before its push, not after it
                say(f"land: {bl.label(iid)} goes through the code lane: this run pushes the merge request of branch "
                    f"{code_branch} and stops there as not done yet, without waiting for it; to land it in one run "
                    f"(reading {remote}/main every {WAIT_POLL} s until the merge request has merged) run "
                    f"backlog.py land {iid} with --wait-merge SECONDS above 0, else run backlog.py land {iid} again "
                    "once it has merged")
            stray =out_of_scope(lroot, item_commits(lroot, family), own_globs(scope(bl, iid)))
            if stray:  # done's scope rule, read before the merge request opens rather than after it merged
                raise land_stop("scope", f"{bl.label(iid)}'s commits change files outside its touches, so done would "
                                         "refuse it once the merge request merged; nothing was pushed: "
                                + "; ".join(f"commit {sha[:10]} changed {p}" for sha, p in stray)
                                + " (revert it, or widen touches: backlog.py set ID --add-touch PATH)")
            land_checks(bl, iid)
            land_siblings(bl, iid)
        changed =git(lroot, "diff", "--name-only", upstream, "HEAD").splitlines()
        if any(p.startswith("_tools/") for p in changed):
            stale = land_stale()
            if stale[1]:
                land_run(lroot, stale[0], [*stale[1], upstream])  # a missing Self-Reviewed fails in seconds
            for step, argv in land_heavy():
                land_run(lroot, step, argv)
        else:  # lint.py takes qualified article paths: the changed articles only, before sync --push
            articles = changed_articles(changed)
            lint = land_lint()
            if changes_kb(changed) and land_eval()[1]:  # a fact can turn an off-kb eval row into a good answer
                land_run(lroot, *land_eval())
            if articles and lint[1]:
                land_run(lroot, lint[0], [*lint[1], *articles])
        name_unpushed(root, remote, start, start_ref, upstream, branch)
        land_run(lroot, *land_push(), whole=True, program=True, keep_to=root)
        if late:
            # the request sync opened by push options: this pass's one read of it
            describe_merge_request(bl, iid, read_code_request(lroot, code_branch))
            tip = pushed_tip(lroot, remote, code_branch)
            LAND_OPS["pending"] = (tip, code_branch) if tip else None
            say(f"land: {bl.label(iid)} is not done yet: its code goes as the merge request of branch {code_branch}; "
                f"once it has merged, run backlog.py land {iid} again (fetch, rebase, done --commit, sync --push)")
            pushed = True
        else:
            verify_landed(lroot, remote, upstream, iid)
            move_run(iid, "landed", "land")
            subprocess.run(["git", "update-ref", "-d", f"{LAND_REF}/{iid}"], cwd=lroot, capture_output=True)
            say(f"land: {bl.label(iid)} landed")
            landed = pushed = True
        return 0
    except kg_lock.MainLockTimeout as e:  # a live holder kept the main lock for the whole bound: report blocked
        raise land_stop("fetch and rebase", str(e) + worktree_back(root, released, branch, iid)) from None
    except Refused as e:  # a stop after the worker's worktree was removed: the branch keeps every commit
        if released:
            raise Refused(stop_with_worktree_back(str(e), worktree_back(root, released, branch, iid))) from None
        raise
    finally:  # the landing worktree goes, whatever happened; an in-place landing is back where land started
        returned = True
        if landing is not None:
            remove_landing_worktree(root, landing)
        else:
            back = (["switch", "-q", start_ref[len("refs/heads/"):]] if start_ref.startswith("refs/heads/")
                    else ["switch", "-q", "--detach", start])
            p = subprocess.run(["git", *back], cwd=root, capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            returned = not p.returncode
            if p.returncode:
                say(f"land: could not return to {start_ref or start[:10]}: {(p.stderr or p.stdout).strip()}")
        if returned:
            if pushed:  # a refusal is said and changes no exit status
                fast_forward_start(root, remote, start_ref, upstream)
            if landed:  # the worker's branches, landed: never the one land runs on
                for done_branch in (branch, agent_branch):
                    if done_branch and start_ref != f"refs/heads/{done_branch}":
                        delete_landed_branch(root, done_branch, upstream)
                if repos:
                    delete_repo_branches(repos, iid, repo_branch(bl.items[iid], iid))
                land_cleanup(Backlog(root), iid)


def land_cleanup(bl, iid):
    """Remove the landed item's recorded scratch directory (`bl_clean.land_leftovers`: a process of its own, the verdict of
    tidy with the age limit waived). Whatever goes wrong here is said and never fails or undoes the landing."""
    try:
        bl_clean.land_leftovers(bl, iid)
    except Exception as e:  # noqa: BLE001
        say(f"land: kept the recorded leftovers of {iid}: {e}")


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
WAIT_MERGE_DEFAULT = 1800  # seconds land waits for a code item's merge request when --wait-merge is not named


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


def run_state(iid):
    """The item's run state (the coord key run/<id>); '' when the key is absent or coord cannot be read."""
    code, body, _ = bl_clean.run_coord("get", f"run/{iid}")
    return str(body.get("value") or "") if code == 0 and isinstance(body, dict) else ""


def take_run(iid, state, who, **fields):
    """Move the item's run state (the coord key run/<id>) to STATE with `coord.py transition`, which posts the move's
    progress event with it; FIELDS are the event's exit, gates and step. (moved, held, why): HELD is the state the key
    held when the table refused the move ('' when coord gave none), WHY the refusal's text."""
    argv = ["transition", f"run/{iid}", "--to", state]
    for name, value in fields.items():
        argv += ["--field", f"{name}={value}"]
    code, body, err = bl_clean.run_coord(*argv)
    if code == 0:
        return True, "", ""
    why = (body.get("error") if isinstance(body, dict) else None) or err or f"coord.py exited {code}"
    return False, str(body.get("state") or "") if isinstance(body, dict) else "", why


def move_run(iid, state, who, **fields):
    """Move the item's run state to STATE (`take_run`). A coord that does not take the move, or a state the table does
    not allow it from, is said and never stops the step WHO runs. True when the state moved."""
    moved, held, why = take_run(iid, state, who, **fields)
    if not moved and held != state:  # a move to the state the key holds is no news
        say(f"{who}: run state of {iid} not moved to {state}: {why} (backlog.py runs --reconcile repairs it)")
    return moved


CLAIM_HELD = ("claimed", "working", "blocked", "returned", "failed", "staging", "landing", "refused")  # run states of a run in progress: a claim by another owner is refused while the key holds one
CLAIMER_STEP = "by:"  # the claimed event's `step` field starts with this, then the claimer's ops token


def run_claimer(iid):
    """The claimer the newest `claimed` progress event of the item names in its step (ops token), '' when coord cannot be
    read, the item has no such event or the event names none."""
    code, body, _ = bl_clean.run_coord("wait", "--kind", "progress", "--item", iid, "--since", "0", "--timeout", "0")
    events = body.get("events") if code == 0 and isinstance(body, dict) else None
    for event in reversed(events if isinstance(events, list) else []):
        fields = event.get("fields") if isinstance(event, dict) and isinstance(event.get("fields"), dict) else {}
        if fields.get("state") == "claimed":
            step = str(fields.get("step") or "")
            return step[len(CLAIMER_STEP):] if step.startswith(CLAIMER_STEP) else ""
    return ""


def take_claim(iid, by, mine=False):
    """Move the item's run state to `claimed` for BY, in one coord transition that records BY in the event (`run_claimer`).
    Raises Refused, changing nothing, when the key holds a state of CLAIM_HELD for another claimer (MINE: the item file
    of this checkout already names BY, which stands in for a claimer the event does not name). The same BY again is no
    news. A coord that cannot be reached, or a state the table never moves from (landed), is said and never refuses."""
    token = ops_token(by)
    moved, held, why = take_run(iid, "claimed", "claim", step=f"{CLAIMER_STEP}{token}")
    if moved:
        return True
    if held in CLAIM_HELD:
        owner = run_claimer(iid) or (token if mine else "")
        if owner == token:
            return False
        raise Refused(f"claim refuses {iid} for {by}: its run state is {held}, held by "
                      f"{owner or 'an owner the run state does not name'}; wait for that run to end, or, when it died, "
                      f"run python3 _tools/backlog.py runs --reconcile (it moves the state to released); nothing was changed")
    if held != "claimed":
        say(f"claim: run state of {iid} not moved to claimed: {why} (backlog.py runs --reconcile repairs it)")
    return False


RUN_TOOLS = {"staging": "stage-back", "landing": "land"}  # the tool that holds each of the two states while it runs
RUN_HEALED = {"staging": "returned", "landing": "refused"}  # where `runs --reconcile` moves a key nothing holds


def note_run_process(iid):
    """Record this process as a coord `own/` process record of the item, before the tool moves the run state, so that a
    key at staging or landing with no live record is one nothing runs for (`runs` lists it as drift). True when the
    record was written; a coord that does not take it is said and never stops the tool."""
    try:
        bl_clean.record_owner("process", os.getpid(), item=iid)
    except (Refused, Rejected) as e:
        say(f"run state of {iid}: this process is not recorded, so a rerun cannot tell it from a dead one: {e}")
        return False
    return True


def drop_run_process(iid, recorded):
    """Clear the record `note_run_process` wrote, when it wrote one."""
    if recorded:
        try:
            bl_clean.record_owner("process", os.getpid(), item=iid, drop=True)
        except (Refused, Rejected):
            pass


def run_holder(iid):
    """The pid of a live coord process record of the item other than this process (a worker, a stage-back or a land
    running), None when there is none or coord cannot be read. A pid runs by the rule of `bl_items.worker_of`: in the
    host's process table, with the recorded start time where there is one."""
    try:
        owners = bl_clean.coord_state()["owners"]
    except (bl_clean.CoordLocked, Rejected):
        return None
    table = bl_clean.host_table(Path.cwd())
    for rec in owners:
        pid, start = rec.get("pid"), rec.get("start")
        if rec.get("class") != bl_clean.PROCESS or rec.get("item") != iid:
            continue
        if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1 or pid == os.getpid():
            continue
        if table is None:
            import tests as tests_py
            if tests_py.pid_alive(pid):
                return pid
            continue
        seen = table.get(pid)
        if seen is not None and (start is None or seen[1] == start):
            return pid
    return None


def enter_run(iid, state, who, **fields):
    """The one transition by which stage-back (STATE staging) and land (landing) take the run state. (entered, refusal):
    ENTERED is true when the key is STATE for this run, moved to it or found there with no live holder (a stage-back or
    land that died; the move this run ends with then closes it); REFUSAL is a text, and the run does not start, when the
    key holds the other tool's state or STATE with a live process record of the item. A coord that cannot be reached or
    a state the table never moves from (failed, landed, none) is said, and the run goes on as before. A land also refuses
    a key at released, and at working while a process record of a worker runs."""
    moved, held, why = take_run(iid, state, who, **fields)
    if moved:
        return True, ""
    if held in RUN_TOOLS and held != state:
        return False, (f"the run state of {iid} is {held}: a {RUN_TOOLS[held]} is running on its branch; wait for it to "
                       f"end, or, when it died, run python3 _tools/backlog.py runs --reconcile (it moves the state to "
                       f"{RUN_HEALED[held]}); nothing was changed")
    if held == state:
        pid = run_holder(iid)
        if pid:
            return False, (f"the run state of {iid} is {state}: a {who} of pid {pid} is running on it; wait for it to "
                           f"end; nothing was changed")
        say(f"{who}: the run state of {iid} was left at {state} by a {who} that is gone: taken over")
        return True, ""
    if state == "landing" and held == "released":
        return False, (f"the run state of {iid} is released: its run was given up, so the branch is not landed; claim the "
                       f"item again (backlog.py claim {iid}), or, when the state is wrong, run python3 _tools/backlog.py "
                       "runs --reconcile; nothing was changed")
    if state == "landing" and held == "working":
        pid = run_holder(iid)
        if pid:
            return False, (f"the run state of {iid} is working: a worker of pid {pid} is running on it; wait for it to "
                           f"end; nothing was changed")
    say(f"{who}: run state of {iid} not moved to {state}: {why} (backlog.py runs --reconcile repairs it)")
    return False, ""


def land_refused_step(error):
    """The step a land stop names (`land stopped at step NAME: ...`); 'land' for any other error."""
    m = re.match(r"land stopped at step ([^:\n]+):", str(error))
    return m.group(1).strip() if m else "land"


def land_move_run(bl, a):
    """Land with the run state moved: landing before the first step (`enter_run`), refused with the step's name when land
    stops (landed is moved by land_locked once verify has found the done commit on main). Stops at step `run state`,
    before any other, changing nothing, while a stage-back holds the state at staging, or another land holds it at
    landing with a process record that runs; a land that died at landing is taken over."""
    iid = need(bl, a.id)
    recorded = note_run_process(iid)
    try:
        _entered, refusal = enter_run(iid, "landing", "land")
        if refusal:
            ops_mark("run state")
            raise land_stop("run state", refusal)
        try:
            code = land_pass(bl, a)
        except Exception as e:  # noqa: BLE001 - a stop of any kind leaves the state refused, naming its step
            move_run(iid, "refused", "land", step=ops_token(land_refused_step(e)))  # coord takes an id: no spaces
            raise
        if code:
            move_run(iid, "refused", "land", step="land")
        elif LAND_OPS.get("pending") and not getattr(a, "wait_merge", None):  # a merge request still to merge, no wait
            move_run(iid, "refused", "land", step=ops_token("merge request"))
        return code
    finally:
        drop_run_process(iid, recorded)


def land_pass(bl, a):
    """The passes of a landing: land_once, and for a code item whose merge request is pending the bounded wait for it
    and the second pass."""
    LAND_OPS["pending"] = None
    code = land_once(bl, a)
    pending, bound = LAND_OPS.get("pending"), getattr(a, "wait_merge", None)
    if code or not pending or not bound:
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


@ops_land
def cmd_land(bl, a):
    """Land a finished item's branch (land_once). A code item's first pass is followed by a bounded wait for its merge
    request, WAIT_MERGE_DEFAULT seconds or --wait-merge SECONDS, read from git (a fetch of the integration main every
    WAIT_POLL seconds, not the forge CLI), then the second pass in the same run; a wait that runs out stops at step
    wait-merge naming the merge request; --wait-merge 0 pushes and stops without waiting. The item's run state
    (coord key run/<id>) moves with it: land_move_run."""
    return land_move_run(bl, a)


def args_done(p):
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")


def args_land(p):
    p.add_argument("id")
    p.add_argument("--branch", help="the local branch to land (default work/ID)")
    p.add_argument("--wait-merge", type=int, metavar="SECONDS", default=WAIT_MERGE_DEFAULT,
                   help="after a code item's first pass, wait up to SECONDS for its merge request (read from git "
                        "every 60 s), then run the second pass; 0 pushes and stops (default: %(default)s)")
    p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                   help="a trailer of the session's own for the done --commit commit (repeatable)")


def merge_target(bl, iid):
    """(branch, project url) `backlog.py merge ID` merges: the item's own code/ID on the integration remote's forge
    project (`bl_forge.target`: `forge_project`, else the remote's URL, which a `repositories` map always uses);
    Refused for an unknown item or a remote that names no forge project."""
    import bl_forge
    need(bl, iid)
    t = bl_forge.target(bl.root, run)
    return f"code/{iid}", f"https://{t.host}/{t.project}"


def cmd_merge(bl, a):
    """Merge the item's own code/ID merge request on the integration remote's project, now (`bl_forge.merge_own`:
    `glab mr merge --auto-merge=false --yes`): the one way an agent merges, since .claude/settings.json allows no
    `glab mr merge`. Another item's branch and another project are refused (exit 2), and so is every merge on the gh
    arm and a project whose `forge` setting is empty (`bl_forge.NoForge`, raised here as `Rejected`). Its state is read first: one auto-merge already merged is reported merged, exit 0, so land runs next; a
    closed one, no request of the branch and a forge that cannot be read are exit 1; only an open one is merged, by its
    number, the newest open one when the branch has several."""
    import bl_forge
    try:
        branch, project = merge_target(bl, a.id)
    except bl_forge.NoForge as e:
        raise Rejected(str(e)) from None
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


def cmd_close(bl, a):
    """`close` (bl_close.cmd_close), then the closed sprint's recorded scratch directories and worker worktrees go with
    `bl_clean.close_leftovers`, as a process of its own: the worker worktrees `close` released leave their records, the
    ones it could not release stay with their reason. Whatever goes wrong there is said and never fails the close."""
    code = bl_close.cmd_close(bl, a)
    if not code and not a.summary:
        try:
            bl_clean.close_leftovers(bl, a.sprint)
        except Exception as e:  # noqa: BLE001
            say(f"close: kept the recorded leftovers of {a.sprint}: {e}")
    return code


bl_cli.register("done", cmd_done, args_done)
bl_cli.register("land", cmd_land, args_land)
bl_cli.register("merge", cmd_merge, args_merge)
bl_cli.COMMANDS["close"] = (cmd_close, *bl_cli.COMMANDS["close"][1:])  # bl_close registered it; this one wraps its handler
