"""The plan side of backlog.py (kb/_self/backlog.md, Planning a sprint; kb/_self/tools.md): the rules about code and its
docs (`stale_touches`, `docs_after_code`, `docs_warnings`, with the `touch_paths`, `dependencies` and `dependents`
they share), the host-check gates, where a dependency outside a sprint stands (`outside_deps`) and `start`, which
refuses a sprint on them and warns of the rest.

Standard library only; imports `bl_base` and never `backlog` or `bl_check`: `bl_check` imports this module for the
rules `check` runs, so the two form no cycle. `backlog.py` registers `start` with `bl_cli`, in its usage order, with the
handler defined here."""
import re
import subprocess

from bl_base import (
    APPROVALS, OPEN, RECURRING_MIN, Refused, START_GATE, commit_written, glob_re, in_scope, live_runners, need,
    runner_overlaps, say, scope,
)

OPEN_STATUSES = OPEN  # the statuses of an item still to do


def start_approved(sp):
    """True when the operator answered the sprint's start gate with an approval."""
    g = next((g for g in sp.get("gates", []) if g.get("id") == START_GATE), {})
    return g.get("by") in ("operator", "autopilot") and str(g.get("answer", "")).strip().lower() in APPROVALS


CODE_DIRS = ("_tools/", ".claude/", ".claude-plugin/")  # with CODE_FILES: the paths whose change needs /kb-self
CODE_FILES = (".gitlab-ci.yml",)
EVERY_TOOL = "_tools/*.py"  # a map pattern that matches this glob, read as a path, covers every tool: a standard doc


def is_code(path):
    return path in CODE_FILES or path.startswith(CODE_DIRS)


def tracked_files(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    return r.stdout.splitlines() if r.returncode == 0 else []


def dependents(bl, iid):
    """The items that depend on iid, directly or through another item (later work)."""
    out, todo = set(), [iid]
    while todo:
        cur = todo.pop()
        for i, it in bl.items.items():
            if cur in it.get("depends_on", []) and i not in out and i != iid:
                out.add(i)
                todo.append(i)
    return out


def stale_touches(bl):
    """An error for each open item whose touches names a path without glob characters that the working tree lacks and
    that has a commit in git log: a file a move or a deletion stranded, so the item's scope (and `done`'s
    outside-touches refusal) names nothing. A path no commit ever had is a file the item is yet to create: no error."""
    history = {}
    out = []
    for iid, it in bl.items.items():
        if it.get("kind") == "sprint" or it.get("status") not in OPEN_STATUSES:
            continue
        for t in it.get("touches", []) or []:
            if not isinstance(t, str) or not t or re.search(r"[*?\[]", t) or (bl.root / t).exists():
                continue
            if t not in history:
                try:
                    r = subprocess.run(["git", "-C", str(bl.root), "log", "-1", "--format=%H", "HEAD", "--", t],
                                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                    history[t] = r.returncode == 0 and bool(r.stdout.strip())
                except (OSError, subprocess.SubprocessError):
                    history[t] = False
            if history[t]:
                out.append(f"{bl.label(iid)}: touches names {t}, which git history has and the working tree lacks "
                           f"(moved or deleted: name its new path, or drop it from touches)")
    return out


def touch_paths(item, files, literal):
    """The paths an item's touches name: each path as written, each glob expanded over FILES (tracked paths) and
    LITERAL (the paths a doc map names, which may not exist yet)."""
    paths = set()
    for t in item.get("touches", []) or []:
        if not isinstance(t, str) or not t:
            continue
        if not re.search(r"[*?]", t):
            paths.add(t)
            continue
        rx = glob_re(t)
        paths |= {p for p in list(files) + literal if rx.match(p)}
    return paths


def dependencies(bl, iid):
    """The items iid depends on, directly or through another item (earlier work)."""
    out, todo = set(), [iid]
    while todo:
        for d in bl.items.get(todo.pop(), {}).get("depends_on", []) or []:
            if d in bl.items and d not in out and d != iid:
                out.add(d)
                todo.append(d)
    return out


def docs_after_code(bl, ids):
    """One refusal for each open task or bug among IDS whose touches are only kb/_self docs that kb/_self/map.csv maps
    to the code another item touches, which it depends on: the sync gate's `selfdoc stale` reads the code and its docs
    in one range, and a task that waits for the code lands them apart. A standard doc (a map pattern that covers every
    _tools/*.py) describes no one change and is left out; a missing or unreadable map gives none."""
    import selfdoc
    try:
        docmap = selfdoc.load_map(str(bl.root))
    except selfdoc.SelfdocError:
        return []
    docmap = {d: pats for d, pats in docmap.items() if not any(selfdoc.matches(p, EVERY_TOOL) for p in pats)}
    literal = [p for pats in docmap.values() for p in pats if not re.search(r"[*?]", p)]
    files, out = None, []
    for iid in sorted(ids):
        it = bl.items[iid]
        touches = it.get("touches", []) or []
        if it.get("status") not in OPEN_STATUSES or it.get("kind") == "sprint" or not touches or \
                not all(isinstance(t, str) and t.startswith("kb/_self/") for t in touches):
            continue
        if files is None:
            files = tracked_files(bl.root)
        docs = touch_paths(it, files, literal)
        for dep in sorted(dependencies(bl, iid)):
            if bl.items[dep].get("status") not in OPEN_STATUSES:
                continue
            code = sorted(p for p in touch_paths(bl.items[dep], files, literal) if is_code(p))
            held = sorted(d for d in selfdoc.describing(docmap, code) if d in docs)
            if held:
                out.append(f"{bl.label(iid)}: touches only docs of code that {bl.label(dep)}, which it depends on, "
                           f"touches: {', '.join(held)} (put them in {bl.label(dep)}'s touches: the sync gate's "
                           "selfdoc stale needs code and its docs in one range)")
    return out


def docs_warnings(bl, only=None):
    """An open item whose own touches name code (CODE_DIRS, CODE_FILES) whose kb/_self/map.csv docs are in no open
    item's touches, or only in the touches of items that depend on it (a later task): kb/_self/git.md asks for a code
    change's doc lines in the same commit, and sync's selfdoc stale gate refuses the push without them. The item's own
    scope (its touches and its descendants') covers a doc; a missing or unreadable map gives no warning. A standard
    doc, one with a map pattern that covers every _tools/*.py (EVERY_TOOL), describes no one change: selfdoc stale
    still lists it, and a Self-Reviewed trailer clears it there, so it is no item's to carry. ONLY limits the items
    reported to those ids; the holders of a doc are still every open item."""
    import selfdoc
    try:
        docmap = selfdoc.load_map(str(bl.root))
    except selfdoc.SelfdocError:
        return []
    docmap = {d: pats for d, pats in docmap.items() if not any(selfdoc.matches(p, EVERY_TOOL) for p in pats)}
    files = None
    literal = [p for pats in docmap.values() for p in pats if not re.search(r"[*?]", p)]
    open_ids = [i for i, it in bl.items.items() if it.get("kind") != "sprint" and it.get("status") in OPEN_STATUSES]
    out = []
    for iid in open_ids:
        if only is not None and iid not in only:
            continue
        if files is None and any(re.search(r"[*?]", t) for t in bl.items[iid].get("touches", []) or []
                                 if isinstance(t, str)):
            files = tracked_files(bl.root)
        paths = touch_paths(bl.items[iid], files or [], literal)
        code = sorted(p for p in paths if is_code(p))
        if not code:
            continue
        own = scope(bl, iid)
        later = dependents(bl, iid)
        missing, deferred = [], {}
        for doc in sorted(selfdoc.describing(docmap, code)):
            if in_scope(doc, own):
                continue
            holders = [i for i in open_ids if i != iid and in_scope(doc, bl.items[i].get("touches", []) or [])]
            if not holders:
                missing.append(doc)
            elif all(h in later for h in holders):
                for h in holders:
                    deferred.setdefault(h, []).append(doc)
        if missing:
            out.append(f"{bl.label(iid)}: touches code whose kb/_self/map.csv docs are in no item's touches: "
                       f"{', '.join(missing)} (add them to this item's touches: kb/_self/git.md, code and its docs "
                       f"land in one commit)")
        for h, docs in sorted(deferred.items()):
            out.append(f"{bl.label(iid)}: the docs of its code are only in a later task's touches, "
                       f"{bl.label(h)} (it depends on this one): {', '.join(docs)} (move them to this item's touches)")
    return out


def recurring_left_out(bl, sid):
    """Open P1 items whose recurs list names RECURRING_MIN sprints or more and that are not in sprint sid."""
    return sorted((i for i, it in bl.items.items()
                   if it.get("kind") != "sprint" and it.get("status") in OPEN and it.get("priority") == "P1"
                   and isinstance(it.get("recurs"), list) and len(set(it["recurs"])) >= RECURRING_MIN
                   and bl.sprint_of(i) != sid), key=bl.order_key)


def host_gates(bl, sid, answered=True):
    """(item id, gate) for each gate of the sprint's open items that carries a host check, the answered ones only
    unless `answered` is False."""
    return [(i, g) for i in bl.sprint_items(sid) if bl.items[i].get("status") not in ("done", "dropped")
            for g in bl.items[i].get("gates", []) if "host_check" in g and (not answered or "answer" in g)]


def has_scope(bl, iid):
    """An item's work has a scope: it is dropped, has touches of its own, or has tasks or subtasks that are not
    dropped and every one of which has a scope (a story broken down into tasks is covered by them)."""
    it = bl.items[iid]
    if it.get("status") == "dropped" or it.get("touches"):
        return True
    kids = [c for c in bl.children(iid) if bl.items[c].get("status") != "dropped"]
    return bool(kids) and all(has_scope(bl, c) for c in kids)


def runner_conflicts(bl, sid):
    """One line for each live sprint runner of another sprint whose committed touches overlap sprint sid's: the holder
    sprint, its clone and the pairs of globs (sid's, then the holder's)."""
    return [f"{rec.get('sprint')} (runner pid {rec.get('pid')}, clone {rec.get('clone')}): "
            + ", ".join(f"{m} meets {t}" for m, t in hits)
            for rec, hits in runner_overlaps(bl, sid, live_runners())]


def cmd_start(bl, a):
    sid = need(bl, a.sprint)
    sp = bl.items[sid]
    if sp.get("kind") != "sprint":
        raise Refused(f"{bl.label(sid)} is not a sprint")
    g = next(g for g in sp["gates"] if g["id"] == START_GATE)
    if not start_approved(sp):
        raise Refused(f"{bl.label(sid)}: the operator has not approved it (gate {START_GATE}: {g.get('answer', 'open')})")
    items = bl.sprint_items(sid)
    if len(items) < 2:
        raise Refused(f"{bl.label(sid)} commits to no item besides its review")
    unchecked = [f"{bl.label(i)} gate {g['id']}" for i, g in host_gates(bl, sid)
                 if not g.get("host_checked", {}).get("ok")]
    if unchecked:
        raise Refused(f"{bl.label(sid)} has an answered gate whose host setup is not checked on this host "
                      "(`backlog.py host-check`, which must pass):\n  " + "\n  ".join(unchecked))
    bare = [i for i in items if not bl.items[i].get("review") and not has_scope(bl, i)]
    if bare:
        raise Refused(f"{bl.label(sid)} has work items without touches (give each its own touches, or tasks that "
                      "all have them):\n  " + "\n  ".join(bl.label(i) for i in bare))
    later = docs_after_code(bl, items)
    if later:
        raise Refused(f"{bl.label(sid)} has a task whose docs wait for the code they describe:\n  " + "\n  ".join(later))
    held = runner_conflicts(bl, sid)
    if held:
        raise Refused(f"{bl.label(sid)}'s committed touches overlap those of a sprint a runner holds on this host:\n  "
                      + "\n  ".join(held))
    for i in items:
        if bl.items[i].get("status") == "draft":
            bl.items[i]["status"] = "todo"
            bl.save(bl.items[i])
    sp["status"] = "active"
    bl.save(sp)
    say(f"started {bl.label(sid)}: {sp['goal']}")
    for w in docs_warnings(bl, set(items)):
        say(f"  warning: {w}")
    for i, d, where in outside_deps(bl, sid):
        say(f"  warning: {bl.label(i)} depends on {bl.label(d)}, outside this sprint ({where})")
    for i in recurring_left_out(bl, sid):
        say(f"  warning: recurring P1 item {bl.label(i)} (recurs in {len(set(bl.items[i]['recurs']))} sprints) "
            "is not in this sprint")
    commit_written(bl, a, "start", sid)
    return 0


def where_outside(bl, d):
    """Where a dependency outside a sprint stands: in no sprint, or in a sprint (started or not)."""
    sp = bl.sprint_of(d)
    if not sp or sp not in bl.items:
        return "in no sprint"
    return f"in sprint {bl.label(sp)}" + ("" if bl.items[sp].get("status") == "active" else ", not started")


def outside_deps(bl, sid):
    """[(item id, dependency id, where)] for each undone depends_on, own or an ancestor's, of an open item of sprint
    sid that points outside it, into no sprint or a sprint not started."""
    items = set(bl.sprint_items(sid))
    out = []
    for i in sorted(items):
        if bl.items[i].get("status") in ("done", "dropped"):
            continue
        for d in dict.fromkeys(d for x in [i] + bl.ancestors(i) for d in bl.items[x].get("depends_on", [])):
            sp = bl.sprint_of(d) if d in bl.items else None
            if d in items or d not in bl.items or bl.items[d].get("status") == "done" or (
                    sp and bl.items[sp].get("status") == "active"):
                continue
            out.append((i, d, where_outside(bl, d)))
    return out


def args_start(p):
    p.add_argument("sprint")
