"""The `cost` command of backlog.py (kb/_self/backlog.md, Cost; kb/_self/tools.md): what the query log's work sidecars hold
for an item and its descendants, the work and rework split, a sprint's research and overhead apart, and the research
items' tokens against the gap findings their commits closed (`cost --research`).

Standard library only; imports `bl_base` and `bl_cli` and never `backlog`. It registers `cost` itself (`bl_cli.register`
at the end), and `backlog.py` imports it at its registration point so the usage text keeps its order. The query log's
store (`ql_store`) is imported where it is read."""
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import bl_cli
from bl_base import ID_RE, REL_DIR, RESEARCH_KINDS, Rejected, research_touches, say, scope


# `cost ID`: what the query log's work sidecars (kb/_querylog/work/<yyyy-mm>/<run-id>.jsonl, written by distill) hold
# for an item and its descendants: tokens per model, the counts of its own prompts (direct, the `main` of its lines)
# apart from those of the subagents routed to it (attributed, the `sub`), cache writes (cw) as a figure of their own.
# A sprint line (`item: SP-...`) is the sprint's, and a shared line (`items`: the ids its session claimed) is its
# session's, not an item's: its counts, `main` and `sub` together, are the `shared` figure of a report, counted once
# for every line that names any id in the report's scope, never once per item it names, and the session total is
# direct + attributed + shared (`cost_report`). Reads no command text, session or prompt id: the sidecar has none. An id with a line and no item file (deleted at sprint close)
# is resolved from the last version of its file in git history (`history_items`), so the totals of its ancestors and
# of its sprint, open or closed, include its lines.
COST_KEYS = ("requests", "in", "cw", "cw1h", "cr", "out")
# one entry per figure group a cost report prints: (report key, sidecar field, label); a later total adds an entry
COST_GROUPS = (("direct", "main", "direct (main)"), ("attributed", "sub", "attributed (sub)"))
COST_SHARED, COST_TOTAL = "shared", "session_total"  # the report's figures beside COST_GROUPS, never an item's own


def cost_add(total, models):
    """Add {model: counts} into `total`: all six counts, a missing one as 0."""
    for m, c in models.items():
        t = total.setdefault(m, dict.fromkeys(COST_KEYS, 0))
        for k in COST_KEYS:
            t[k] += c.get(k, 0)


def cost_models(w, field):
    """{model: counts} of a work line's `main`, or its `sub` summed over the agent groups."""
    maps = [w.get(field) or {}] if field == "main" else list((w.get(field) or {}).values())
    out = {}
    for models in maps:
        cost_add(out, models)
    return out


def cost_row_of(run, w, ids, rework):
    """The report row of one work line of run `run`, or None when it names none of `ids` (every line when None)."""
    if "item" in w and (ids is None or w["item"] in ids):  # a shared line has `items`, no `item`
        row = {"run": run, "item": w["item"], "prompts": w["prompts"],
               **{key: cost_models(w, field) for key, field, _ in COST_GROUPS}}
        if rework and "rework" in w:
            row["rework"] = {"prompts": w["rework"]["prompts"],
                             **{key: cost_models(w["rework"], field) for key, field, _ in COST_GROUPS}}
        return row
    if "items" in w and (ids is None or ids.intersection(w["items"])):
        both = {}
        for _, field, _ in COST_GROUPS:
            cost_add(both, cost_models(w, field))
        return {"run": run, "items": w["items"], "prompts": w["prompts"], COST_SHARED: both}
    return None


def cost_lines(root, ids, rework=False):
    """([line], [skipped run id]): the lines of the work sidecars under root/kb/_querylog that name one of `ids`
    (every line when `ids` is None), oldest run first: an item line {run, item, prompts, <report key>: {model:
    counts}}, and a shared line {run, items, prompts, shared: {model: counts}} (its `main` and `sub` together) that
    names one of `ids` among its `items`; a sidecar that breaks the store's work gates (`ql_store.work_line_problems`) is skipped whole and named, so a bad
    file never skews a sum. With `rework`, an item line that has a `rework` block also has `rework`: {prompts,
    <report key>: {model: counts}}, a part of the line's own figures; without it no line has the key."""
    import ql_store
    out, skipped = [], []
    for p in ql_store.work_files(Path(root) / "kb" / "_querylog"):
        try:
            objs = ql_store.load_run(p)
        except (OSError, ValueError):
            objs = []
        lines = [w for _, w in objs[1:]]
        if not objs or any(ql_store.work_line_problems(w, p.stem) for w in lines):
            skipped.append(p.stem)
            continue
        out += [r for r in (cost_row_of(p.stem, w, ids, rework) for w in lines) if r]
    return out, skipped


OPEN_RUN = "open-"  # the run name of a line read from an open session's spool (`open_lines`), never a sidecar's


def open_lines(root, rework=True):
    """([line], [{session, worked, missing}]): the work of the sessions whose spool has no end marker and is not idle
    (`ql_distill.read_spool`: not closed), computed from their spool rows with the pure work-window code distill
    runs for a closed session (`ql_distill.plan_work`, one session at a time), as report lines named `open-<session>`.
    Reads the spool only: no sidecar, no marker, no row is written, and a session that claimed no item gives
    nothing. `worked` is the set of items the session claimed and `missing` its window prompts with no usable
    `usage` row (a prompt is counted once its Stop row has written its usage). No spool directory: nothing."""
    import time

    import ql_capture
    import ql_distill
    spool = ql_capture.spool_dir()
    if spool is None or not Path(spool).is_dir():
        return [], []
    sessions = ql_distill.read_spool(spool, time.time())[0]
    sprint_of = ql_distill.sprint_finder(Path(root) / REL_DIR)
    out, info = [], []
    for sid in sorted(sessions):
        s = sessions[sid]
        worked = ql_distill.work_windows(s["rows"])[1]
        if s["closed"] or not worked:
            continue
        lines, missing, _ = ql_distill.plan_work({sid: {**s, "closed": True}}, {}, sprint_of)
        run = OPEN_RUN + sid[:8]
        out += [r for r in (cost_row_of(run, w, None, rework) for w in lines) if r]
        info.append({"session": sid, "worked": worked, "missing": missing})
    return out, info


def cost_scope(bl, iid):
    """The ids whose lines an item's cost sums: it and its descendants, and for a sprint also the items in it."""
    ids = {iid, *bl.descendants(iid)}
    if bl.items[iid].get("kind") == "sprint":
        ids |= set(bl.sprint_items(iid))
    return ids


HISTORY_CHUNK = 100  # item files named in one `git log`, so the command line stays short on every OS
HISTORY_TIMEOUT_S = 60


def history_parse(text):
    """{id: item JSON} from the patch text of `git log -p --diff-filter=D` over item files, newest deletion first: the
    removed lines of each deleted file, the first (newest) deletion of an id kept; a version that is not a JSON
    object is left out."""
    body, cur, hunk = {}, None, False
    for ln in text.splitlines():
        if ln.startswith("diff --git "):
            m = re.search(r"/([^/ ]+)\.json$", ln)
            cur = m.group(1) if m and m.group(1) not in body else None
            hunk = False
            if cur:
                body[cur] = []
        elif cur and ln.startswith("@@"):
            hunk = True
        elif cur and hunk and ln.startswith("-"):
            body[cur].append(ln[1:])
    out = {}
    for iid, rows in body.items():
        try:
            it = json.loads("\n".join(rows))
        except ValueError:
            continue
        if isinstance(it, dict):
            out[iid] = it
    return out


def history_items(root, ids):
    """{id: the last version of its item file} for the ids whose file git history shows deleted: one `git log --all`
    per `HISTORY_CHUNK` ids, run in `root` (a worktree shares its history). An id with no deletion in the history
    this clone holds (never committed, or a shallow clone cut it) is absent; git missing, failing or timing out
    leaves the chunk's ids absent, never an error."""
    found = {}
    ids = sorted({i for i in ids if ID_RE.fullmatch(i)})
    for n in range(0, len(ids), HISTORY_CHUNK):
        paths = [f"{REL_DIR}/{i}.json" for i in ids[n:n + HISTORY_CHUNK]]
        argv = ["git", "--literal-pathspecs", "-C", str(root), "log", "--all", "--diff-filter=D", "--no-renames",
                "--no-ext-diff", "--no-textconv", "--format=", "-p", "--", *paths]
        try:
            p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=HISTORY_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError):
            continue
        if p.returncode == 0:
            found.update(history_parse(p.stdout))
    return found


def cost_view(bl, ids):
    """(view, {id: item} restored from history, [id asked of history and not found]): a copy of `bl` whose items also
    hold each of `ids` that has no item file (and, in turn, the parent of each such item that has none), so the
    parent chain and the sprint of an item deleted at sprint close resolve. An id is asked of git once per run."""
    view = copy.copy(bl)
    view.items = dict(bl.items)
    restored, asked = {}, set()
    want = {i for i in ids if i not in view.items}
    while want:
        asked |= want
        got = history_items(bl.root, want)
        restored.update(got)
        view.items.update(got)
        want = {it["parent"] for it in got.values() if isinstance(it.get("parent"), str)} - asked - set(view.items)
    return view, restored, sorted(asked - set(restored))


def cost_is_research(view, iid):
    """True for a research item (backlog.md, Sprints): a story, task or subtask whose touches, its descendants' too,
    are all kb content (`research_touches`)."""
    return view.items[iid].get("kind") in RESEARCH_KINDS and research_touches(scope(view, iid))


def cost_sum(lines):
    """{runs, prompts, <report key>: {model: counts}, by_item, items} of item lines."""
    out = {"runs": len({w["run"] for w in lines}), "prompts": sum(w["prompts"] for w in lines),
           **{key: {} for key, _, _ in COST_GROUPS}, "by_item": {}}
    for w in lines:
        one = out["by_item"].setdefault(w["item"], {"prompts": 0, **{key: {} for key, _, _ in COST_GROUPS}})
        one["prompts"] += w["prompts"]
        for key, _, _ in COST_GROUPS:
            cost_add(out[key], w[key])
            cost_add(one[key], w[key])
    out["items"] = sorted(out["by_item"])
    return out


def cost_take(total, models):
    """Subtract {model: counts} from `total` (the counterpart of cost_add): a part of what `total` holds."""
    for m, c in models.items():
        t = total.setdefault(m, dict.fromkeys(COST_KEYS, 0))
        for k in COST_KEYS:
            t[k] -= c.get(k, 0)
        if not any(t.values()):  # a model all of whose counts were the part's has no row left
            del total[m]


def cost_part():
    """An empty figure set of the work/rework split: prompts and each report key's {model: counts}."""
    return {"prompts": 0, **{key: {} for key, _, _ in COST_GROUPS}}


def cost_part_add(into, part, sign=1):
    """Add (or, with sign -1, take) `part`'s prompts and figures into `into`."""
    into["prompts"] += sign * part["prompts"]
    for key, _, _ in COST_GROUPS:
        (cost_add if sign > 0 else cost_take)(into[key], part[key])


def cost_split(lines):
    """The work/rework split of item lines (cost_lines with `rework`): {items, work, rework, by_item}. `rework` sums the
    lines' rework blocks and `work` is what is left of their figures (the prompts and counts before an item's first
    refused done, and all of an item with none), each {prompts, <report key>: {model: counts}}; `items` are the ids
    with a rework block, sorted, and `by_item` holds, for those only, the item's `work` and `rework` the same way."""
    whole, rw, per, has = cost_part(), cost_part(), {}, set()
    for w in lines:
        cost_part_add(whole, {"prompts": w["prompts"], **{key: w[key] for key, _, _ in COST_GROUPS}})
        one = per.setdefault(w["item"], {"all": cost_part(), "rework": cost_part()})
        cost_part_add(one["all"], {"prompts": w["prompts"], **{key: w[key] for key, _, _ in COST_GROUPS}})
        if "rework" in w:
            has.add(w["item"])
            cost_part_add(rw, w["rework"])
            cost_part_add(one["rework"], w["rework"])
    work = cost_part()
    cost_part_add(work, whole)
    cost_part_add(work, rw, -1)
    out = {"items": sorted(has), "work": work, "rework": rw, "by_item": {}}
    for i in out["items"]:
        part = cost_part()
        cost_part_add(part, per[i]["all"])
        cost_part_add(part, per[i]["rework"], -1)
        out["by_item"][i] = {"work": part, "rework": per[i]["rework"]}
    return out


def cost_report(bl, iid, rework=False):
    """The report of `cost ID`: {id, items, runs, prompts, <report key>: {model: counts}, shared, session_total,
    shared_prompts, by_item, run_lines, shared_lines, skipped, restored, unresolved, view}. `shared` sums the shared
    lines that name any id in the scope, each line once however many of its items are in it (and so once for an
    epic or a sprint), and `session_total` is direct + attributed + shared; `by_item` and `run_lines` hold item
    lines only, so a shared line is in no item's own row. `restored` are the ids in the sum whose item file is gone, read from git history;
    `unresolved` the ids with a line (or the parents of those) that have no file and no history, left out of every
    sum; `view` the backlog with the restored items, for labels. Raises KeyError for an id with neither a file nor
    a history. A sprint's report also has `research` (the lines of its research items, `cost_is_research`: {items,
    runs, prompts, direct, attributed, total, by_item}), kept out of `items`, `runs`, `prompts`, `direct`,
    `attributed` and `session_total`, which are the item work, and `overhead` (`cost_overhead`), in no figure of
    either; `run_lines` keeps every item line. With `rework`, the report also has `rework_split` (cost_split) of the
    item work lines, research left out as in the figures above; without it, no line and no key of the report
    differs from a report that never heard of rework. With `rework` the report also has `open`: the sessions still open
    with work in the scope (`open_lines`), their prompts and the `split` of their figures, kept apart from every figure
    above, which stay the sidecars'."""
    all_lines, skipped = cost_lines(bl.root, None, rework=True) if rework else cost_lines(bl.root, None)
    extra, opened = open_lines(bl.root) if rework else ([], [])  # sessions still open: no sidecar line yet
    named = {i for w in all_lines + extra for i in (w["items"] if "items" in w else [w["item"]])}
    view, restored, unresolved = cost_view(bl, named | {iid})
    if iid not in view.items:
        raise KeyError(iid)
    keep = cost_scope(view, iid)
    lines = [w for w in all_lines if w.get("item") in keep]
    shared = [w for w in all_lines if keep.intersection(w.get("items", ()))]  # each line once, however many items
    sprint = view.items[iid].get("kind") == "sprint"
    research = {w["item"] for w in lines if sprint and cost_is_research(view, w["item"])}
    work = cost_sum([w for w in lines if w["item"] not in research])
    rep = {"id": iid, "runs": work["runs"], "prompts": work["prompts"],
           **{key: work[key] for key, _, _ in COST_GROUPS}, COST_SHARED: {}, COST_TOTAL: {},
           "shared_prompts": sum(w["prompts"] for w in shared), "by_item": work["by_item"], "run_lines": lines,
           "shared_lines": shared, "skipped": skipped, "unresolved": unresolved, "view": view}
    for w in shared:
        cost_add(rep[COST_SHARED], w[COST_SHARED])
    for key in (*(g[0] for g in COST_GROUPS), COST_SHARED):
        cost_add(rep[COST_TOTAL], rep[key])
    rep["items"] = work["items"]
    if rework:
        rep["rework_split"] = cost_split([w for w in lines if w["item"] not in research])
        mine = [o for o in opened if o["worked"] & keep]
        own = [w for w in extra if w.get("item") in keep and w["item"] not in research]
        rep["open"] = {"sessions": len(mine), "missing": sum(o["missing"] for o in mine),
                       "prompts": cost_sum(own)["prompts"], "split": cost_split(own)}
    rep["restored"] = sorted(({w["item"] for w in lines} | {iid}) & set(restored))
    if sprint:
        res = cost_sum([w for w in lines if w["item"] in research])
        res["total"] = {}
        for key, _, _ in COST_GROUPS:
            cost_add(res["total"], res[key])
        rep["research"] = res
        rep["overhead"] = cost_overhead(bl.root, iid)
    return rep


# `cost SP`, overhead: the `overhead` lines of the work sidecars (usage.md) are the kb's own background runs, in
# no item's or sprint's figure. A sprint's window runs from its start commit to its close commit: the oldest commit
# that adds `"status": "active"` to the sprint's item file (`start`), to the newest commit that deletes the file
# (`close`; none while the file exists: the window is open, with no upper bound). A run belongs to it when the time
# in its run id (UTC) is at or after the start and at or before the close. Git decides, as in `history_items`: a
# shallow clone, no git or no start commit leaves the overhead unresolved, never guessed.
GIT_TIMEOUT_S = 30


def git_times(root, *args):
    """[epoch seconds] of the commits `git log --all` lists for `args` (`%ct` of each), or None when git fails."""
    argv = ["git", "--literal-pathspecs", "-C", str(root), "log", "--all", "--format=%ct", *args]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    return [int(x) for x in p.stdout.split()] if p.returncode == 0 else None


def sprint_window(root, sid):
    """(start, end, reason): the sprint's window in epoch seconds (`end` None while the sprint is open), or
    (None, None, why) when git history cannot say."""
    try:
        shallow = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None, None, "git is unavailable"
    if shallow.returncode != 0:
        return None, None, "git history is unavailable"
    if shallow.stdout.strip() == "true":
        return None, None, "shallow clone: the sprint's start commit may be cut from history"
    path = f"{REL_DIR}/{sid}.json"
    starts = git_times(root, "--diff-filter=AM", "-S", '"status": "active"', "--", path)
    if not starts:
        return None, None, "no commit in history sets the sprint active"
    if (Path(root) / path).is_file():
        return min(starts), None, None
    closes = git_times(root, "--diff-filter=D", "--", path)
    if not closes:
        return None, None, "the sprint's file is gone and no commit in history deletes it"
    return min(starts), max(closes), None


def cost_overhead(root, sid):
    """The overhead of sprint `sid`: {resolved, reason, start, end, runs, calls, kinds: {kind: {calls, main}}, total}
    (`start` and `end` UTC `YYYY-MM-DDThh:mm:ssZ`, `end` None while open): the overhead lines of the work sidecars of the runs
    inside the sprint's window, summed apart from every item. Unresolved (`resolved` False, a `reason`, no figures)
    when the window is unknown (`sprint_window`). A sidecar that breaks the store's work gates is left out, as
    `cost_lines` does."""
    import datetime
    import ql_store
    start, end, reason = sprint_window(root, sid)
    def iso(t):
        return None if t is None else datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = {"resolved": reason is None, "reason": reason, "start": iso(start), "end": iso(end)}
    if reason:
        return out
    out.update(runs=0, calls=0, kinds={}, total={})
    for p in ql_store.work_files(Path(root) / "kb" / "_querylog"):
        if not ql_store.RUN_ID.fullmatch(p.stem):
            continue
        when = datetime.datetime.strptime(p.stem[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc)
        if when.timestamp() < start or (end is not None and when.timestamp() > end):
            continue
        try:
            objs = ql_store.load_run(p)
        except (OSError, ValueError):
            continue
        lines = [w for _, w in objs[1:]]
        if not objs or any(ql_store.work_line_problems(w, p.stem) for w in lines):
            continue
        mine = [w for w in lines if "overhead" in w]
        out["runs"] += bool(mine)
        for w in mine:
            one = out["kinds"].setdefault(w["overhead"], {"calls": 0, "main": {}})
            one["calls"] += w["calls"]
            out["calls"] += w["calls"]
            cost_add(one["main"], w["main"])
            cost_add(out["total"], w["main"])
    return out


# `cost --research`: the items that did research against the query log's gap findings, each with its tokens and the gap
# findings closed by commits that carry its `KB-Work` trailer. An item is listed when its `research` field is true (a
# field only a later item adds; until then none is) or one of its `links` names a gap finding of the committed store
# (`F-<12 hex>` with kind `gap` in `kb/_querylog/findings`). Its tokens are its own lines' direct + attributed counts
# (`cost_lines`, no descendant, no shared line), the sum of `in`, `cw`, `cr` and `out` over the models (`TOKEN_KEYS`:
# `requests` is a count of calls, no tokens). A gap finding is closed by a commit when the commit's version of a
# root's `_gaps.md` has a settling note (`ql_research.SETTLED`: Resolved or Superseded, dated) under the entry that
# names the finding and its first parent's version has none (or has no entry or no file): the commit that settles the
# entry, the one `/kb-research` writes, never the query log's own record, which has no `KB-Work` trailer. Tokens per
# closed gap is the item's tokens divided by the count of its closed gaps, integer division (floor); `n/a` when it
# closed none, and unresolved, no figure, when git cannot say (a shallow clone, no git, a failing git).
TOKEN_KEYS = ("in", "cw", "cr", "out")
GAP_ID_RE = re.compile(r"\bF-[0-9a-f]{12}\b")
GAPS_PATHSPEC = ":(glob)kb/*/_gaps.md"
WORK_TRAILER = "KB-Work"


def cost_tokens(models):
    """The tokens of {model: counts}: `in` + `cw` + `cr` + `out` summed over the models."""
    return sum(c.get(k, 0) for c in models.values() for k in TOKEN_KEYS)


def gap_links(it, kinds):
    """The gap findings (id in `kinds` with kind `gap`) an item's `links` name, sorted."""
    ids = {m for x in it.get("links", []) if isinstance(x, str) for m in GAP_ID_RE.findall(x)}
    return sorted(i for i in ids if kinds.get(i) == "gap")


def gaps_settled(text):
    """The ids of the finding named by the _gaps.md entries (top-level bullets, with their indented lines) of `text`
    that carry a settling dated note, the rule of `ql_research.settled`: an id on the bullet's own lines, never one
    a note line mentions."""
    import ql_research
    lines, out, i = text.split("\n"), set(), 0
    while i < len(lines):
        if not lines[i].startswith("- "):
            i += 1
            continue
        end = i + 1
        while end < len(lines) and lines[end][:1] in (" ", "\t") and lines[end].strip():
            end += 1
        notes = [ql_research.NOTE.match(ln) for ln in lines[i + 1:end]]
        if any(m and m.group(1) in ql_research.SETTLED for m in notes):
            out.update(m for ln, n in zip(lines[i:end], [None, *notes]) if not n for m in GAP_ID_RE.findall(ln))
        i = end
    return out


def git_text(root, *args, timeout=GIT_TIMEOUT_S):
    """The stdout of `git -C root ARGS`, or None when git is missing, times out or fails."""
    try:
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def closed_gaps_by_item(root, wanted):
    """({item id: {gap finding id closed by a commit whose KB-Work trailer names it}}, reason): `reason` is None when
    git answered, else why it could not (a shallow clone, git missing or failing) and the map is None, never a guess.
    One `git log --all --no-merges` over the `_gaps.md` ledgers lists the commits that touch one with their
    trailers; each commit that names one of `wanted` is read at itself and at its first parent."""
    shallow = git_text(root, "rev-parse", "--is-shallow-repository")
    if shallow is None:
        return None, "git history is unavailable"
    if shallow.strip() == "true":
        return None, "shallow clone: the commits that closed a gap may be cut from history"
    log = git_text(root, "log", "--all", "--no-merges", "--no-renames", "--diff-filter=AM", "--name-only",
                   f"--format=%x1e%H%x1f%P%x1f%(trailers:key={WORK_TRAILER},valueonly)%x1f", "--", GAPS_PATHSPEC,
                   timeout=HISTORY_TIMEOUT_S)
    if log is None:
        return None, "git log failed"
    out = {i: set() for i in wanted}
    for rec in log.split("\x1e")[1:]:
        sha, parents, trailer, names = rec.split("\x1f", 3)
        ids = wanted.intersection(re.split(r"[,\s]+", trailer.strip()))
        if not ids:
            continue
        for path in sorted({n for n in names.split("\n") if n.strip()}):
            after = git_text(root, "show", f"{sha}:{path}")
            first = parents.split()[0] if parents.split() else None
            held = git_text(root, "ls-tree", "--name-only", first, "--", path) if first else ""  # "" when absent
            before = git_text(root, "show", f"{first}:{path}") if held and held.strip() else ""
            if after is None or before is None or held is None:
                return None, "git could not read a commit's ledger"
            closed = gaps_settled(after) - gaps_settled(before)
            for i in ids:
                out[i] |= closed
    return out, None


def cost_research(bl):
    """The report of `cost --research`: {items: [{id, title, selected_by, runs, prompts, direct, attributed, tokens,
    direct_tokens, attributed_tokens, closed_gaps, gap_status, tokens_per_gap}], git: {resolved, reason}, skipped,
    unresolved, view}, the items by tokens descending then id. `selected_by` holds `research` and `links`; `gap_status`
    is `closed` (`closed_gaps` sorted, `tokens_per_gap` their floor division), `none` (none closed: no ratio) or
    `unresolved` (git cannot say: `closed_gaps` and `tokens_per_gap` are None). An item with no work line has 0
    tokens. Items restored from git history (deleted at sprint close) count when a work line names them."""
    import ql_store
    all_lines, skipped = cost_lines(bl.root, None)
    named = {w["item"] for w in all_lines if "item" in w}
    view, _, unresolved = cost_view(bl, named)
    kinds = {i: r.get("kind") for i, r in ql_store.finding_states(Path(bl.root) / "kb" / "_querylog").items()}
    chosen = {}
    for iid, it in view.items.items():
        why = (["research"] if it.get("research") is True else []) + (["links"] if gap_links(it, kinds) else [])
        if why:
            chosen[iid] = why
    closed, reason = closed_gaps_by_item(bl.root, set(chosen)) if chosen else ({}, None)
    rows = []
    for iid, why in chosen.items():
        mine = [w for w in all_lines if w.get("item") == iid]
        parts = {key: {} for key, _, _ in COST_GROUPS}
        for w in mine:
            for key in parts:
                cost_add(parts[key], w[key])
        gaps = None if closed is None else sorted(closed[iid])
        tokens = sum(cost_tokens(m) for m in parts.values())
        rows.append({"id": iid, "title": view.items[iid].get("title"), "selected_by": why,
                     "runs": len({w["run"] for w in mine}), "prompts": sum(w["prompts"] for w in mine), **parts,
                     "tokens": tokens, "direct_tokens": cost_tokens(parts["direct"]),
                     "attributed_tokens": cost_tokens(parts["attributed"]), "closed_gaps": gaps,
                     "gap_status": "unresolved" if gaps is None else "closed" if gaps else "none",
                     "tokens_per_gap": tokens // len(gaps) if gaps else None})
    rows.sort(key=lambda r: (-r["tokens"], r["id"]))
    return {"items": rows, "git": {"resolved": reason is None, "reason": reason}, "skipped": skipped,
            "unresolved": unresolved, "view": view}


def cmd_cost_research(bl, a):
    rep = cost_research(bl)
    if rep["skipped"]:
        print(f"cost: skipped sidecars that break the store's gates: {', '.join(rep['skipped'])}", file=sys.stderr)
    if rep["unresolved"]:
        print(f"cost: no item file and no git history for {', '.join(rep['unresolved'])}: left out", file=sys.stderr)
    if a.format == "json":
        say(json.dumps({"research_items": rep["items"], "git": rep["git"], "skipped": rep["skipped"],
                        "unresolved": rep["unresolved"], "token_keys": list(TOKEN_KEYS)}, sort_keys=True, indent=2))
        return 0
    git = rep["git"]
    say(f"cost --research: {len(rep['items'])} item(s) with research true or a link to a gap finding; tokens = "
        f"{' + '.join(TOKEN_KEYS)} of direct + attributed (the item's own lines)")
    say("closed gaps: " + ("resolved" if git["resolved"] else f"unresolved ({git['reason']})"))
    for r in rep["items"]:
        gaps, per = r["closed_gaps"], r["tokens_per_gap"]
        shown = ("unresolved" if gaps is None else f"{len(gaps)} closed gap(s): {', '.join(gaps)}" if gaps
                 else "no closed gap")
        say(f"  {rep['view'].label(r['id'])}: {r['tokens']} tokens (direct {r['direct_tokens']}, attributed "
            f"{r['attributed_tokens']}), {shown}; tokens per closed gap: "
            + ("unresolved" if gaps is None else "n/a" if per is None else str(per)))
    return 0


def cost_row(name, c):
    return f"{name}  requests {c['requests']}  in {c['in']}  cr {c['cr']}  out {c['out']} | cw {c['cw']}"


def cost_figures(models, indent):
    """The rows of one figure group: a row per model, then the sum of the models (zeros when there are none)."""
    allm = {k: sum(c[k] for c in models.values()) for k in COST_KEYS}
    return [indent + cost_row(m, models[m]) for m in sorted(models)] + [indent + cost_row("all models", allm)]


def cost_block(part, indent):
    """The figure groups of `part`; a report (it has COST_SHARED) also prints shared and the session total."""
    out = []
    groups = [(key, label) for key, _, label in COST_GROUPS]
    if COST_SHARED in part:
        groups += [(COST_SHARED, f"shared (outside any window, {part['shared_prompts']} prompt(s))"),
                   (COST_TOTAL, "session total (direct + attributed + shared)")]
    for key, label in groups:
        out.append(f"{indent}{label}:")
        out += cost_figures(part[key], indent + "  ")
    return out


def cost_apart(rep, view):
    """The lines of a sprint's research and overhead, apart from the item work above them (none for any other id)."""
    out = []
    if "research" in rep:
        res = rep["research"]
        out.append(f"research ({len(res['items'])} item(s), {res['prompts']} prompt(s); in none of the figures above"
                   + (": " + ", ".join(view.label(i) for i in res["items"]) if res["items"] else "") + "):")
        for key, _, label in COST_GROUPS:
            out.append(f"  {label}:")
            out += cost_figures(res[key], "    ")
        out.append("  total (direct + attributed):")
        out += cost_figures(res["total"], "    ")
    if "overhead" in rep:
        ov = rep["overhead"]
        if not ov["resolved"]:
            out.append(f"system overhead: unresolved ({ov['reason']})")
        else:
            out.append(f"system overhead ({ov['start']} to {ov['end'] or 'now'}, {ov['runs']} run(s), "
                       f"{ov['calls']} call(s); in no item or sprint figure):")
            for kind in sorted(ov["kinds"]):
                out.append(f"  {kind} ({ov['kinds'][kind]['calls']} call(s)):")
                out += cost_figures(ov["kinds"][kind]["main"], "    ")
            out.append("  all kinds:")
            out += cost_figures(ov["total"], "    ")
    return out


def cost_part_tokens(part):
    """The tokens of a work/rework part: `in` + `cw` + `cr` + `out` of its direct and attributed figures."""
    return sum(cost_tokens(part[key]) for key, _, _ in COST_GROUPS)


def cost_split_json(split):
    """The `rework_split` of the json report: the split's parts, each with its `tokens` besides its prompts and
    figures, and `token_keys`."""
    def part(p):
        return {**p, "tokens": cost_part_tokens(p)}
    return {"items": split["items"], "work": part(split["work"]), "rework": part(split["rework"]),
            "by_item": {i: {"work": part(one["work"]), "rework": part(one["rework"])}
                        for i, one in split["by_item"].items()}, "token_keys": list(TOKEN_KEYS)}


def cost_split_text(split, view):
    """The lines of `cost --rework`: the work and rework figures of the report's item work, then the items that
    have rework with their tokens of each (none, when no item has)."""
    out = [f"work and rework (the counts before an item's first refused done and from it; {len(split['items'])} "
           f"item(s) with rework; tokens = {' + '.join(TOKEN_KEYS)}):"]
    for name, key in (("work", "work"), ("rework", "rework")):
        part = split[key]
        out.append(f"  {name} ({part['prompts']} prompt(s), {cost_part_tokens(part)} tokens):")
        for gkey, _, label in COST_GROUPS:
            out.append(f"    {label}:")
            out += cost_figures(part[gkey], "      ")
    if not split["items"]:
        out.append("  no item has rework")
    for i in split["items"]:
        one = split["by_item"][i]
        out.append(f"  {view.label(i)}: work {one['work']['prompts']} prompt(s), {cost_part_tokens(one['work'])} tokens; "
                   f"rework {one['rework']['prompts']} prompt(s), {cost_part_tokens(one['rework'])} tokens")
    return out


def cmd_cost(bl, a):
    if a.research:
        if a.id or a.runs or a.rework:
            raise Rejected("cost --research lists every research item: it takes no ID, no --runs and no --rework")
        return cmd_cost_research(bl, a)
    if not a.id:
        raise Rejected("cost needs an ID, or --research")
    rep = cost_report(bl, a.id, rework=True) if a.rework else cost_report(bl, a.id)
    iid, view = rep["id"], rep["view"]
    if rep["skipped"]:
        print(f"cost: skipped sidecars that break the store's gates: {', '.join(rep['skipped'])}", file=sys.stderr)
    if rep["unresolved"]:
        print(f"cost: no item file and no git history for {', '.join(rep['unresolved'])}: left out of every sum",
              file=sys.stderr)
    if a.format == "json":
        out = {k: rep[k] for k in ("id", "items", "runs", "prompts", "shared_prompts", "by_item", "skipped", "restored",
                                   "unresolved", COST_SHARED, COST_TOTAL, *(g[0] for g in COST_GROUPS))}
        out.update({k: rep[k] for k in ("research", "overhead") if k in rep})  # a sprint's report only
        if a.rework:
            out["rework_split"] = cost_split_json(rep["rework_split"])
            out["open_sessions"] = {**{k: rep["open"][k] for k in ("sessions", "missing", "prompts")},
                                    "rework_split": cost_split_json(rep["open"]["split"])}
        if a.runs:
            out["run_lines"] = rep["run_lines"]
            out["shared_lines"] = rep["shared_lines"]
        say(json.dumps(out, sort_keys=True, indent=2))
        return 0
    n = len(rep["items"])
    say(f"cost {view.label(iid)}: {rep['runs']} run(s), {n} item(s) with work lines, {rep['prompts']} prompt(s)"
        " (the item and its descendants)")
    if rep["restored"]:
        say("from git history (item file deleted): " + ", ".join(view.label(i) for i in rep["restored"]))
    for x in cost_block(rep, ""):
        say(x)
    for x in cost_apart(rep, view):
        say(x)
    if a.rework:
        for x in cost_split_text(rep["rework_split"], view):
            say(x)
        o = rep["open"]
        if o["sessions"]:
            say(f"open session figures (the session has not closed: provisional until it does): {o['sessions']} open "
                f"session(s) with work in this scope, {o['prompts']} prompt(s) read from their spool, not in the "
                f"figures above, {o['missing']} window prompt(s) without a usage row yet")
            if not o["prompts"]:
                say("no figure yet: the zeros mean the open session has no usage rows to read, not that no work happened")
            for x in cost_split_text(o["split"], view):
                say("  " + x)
    if rep["items"] not in ([], [iid]):
        say("by item:")
        for i in rep["items"]:
            say(f"  {view.label(i)}: {rep['by_item'][i]['prompts']} prompt(s)")
            for x in cost_block(rep["by_item"][i], "    "):
                say(x)
    if a.runs:
        say("shared lines (one per session):")
        for w in rep["shared_lines"]:
            say(f"  {w['run']}  {', '.join(view.label(i) for i in w['items'])}: {w['prompts']} prompt(s)")
            for x in cost_figures(w[COST_SHARED], "    "):
                say(x)
        say("runs:")
        for w in rep["run_lines"]:
            say(f"  {w['run']}  {view.label(w['item'])}: {w['prompts']} prompt(s)")
            for x in cost_block(w, "    "):
                say(x)
    return 0


def args_cost(p):
    p.add_argument("id", nargs="?")
    p.add_argument("--runs", action="store_true", help="also list each run's line apart")
    p.add_argument("--rework", action="store_true",
                   help="also split the work from the rework after an item's first refused done")
    p.add_argument("--research", action="store_true",
                   help="instead of an ID: every research item's tokens against the gap findings its commits closed")
    p.add_argument("--format", choices=("text", "json"), default="text")


bl_cli.register("cost", cmd_cost, args_cost)
