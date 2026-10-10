"""The read-only views of backlog.py (kb/_self/backlog.md, The horizon and Item commands; kb/_self/tools.md): what is
ready (`ready`), the near-duplicates (`words`, `similar`, `is_near`), `horizon` and its SessionStart hook form
(`hook_json`, `clip`), and the `similar`, `list`, `tree`, `find`, `show`, `next`, `held` and `horizon` commands.
They read the backlog and write nothing.

Standard library only; imports `bl_base` and `bl_check` (the knowledge lines `show`, `next` and `horizon` print), never
`backlog`. It registers the commands with `bl_cli` itself when imported, and `backlog.py`'s USAGE puts them in
the usage order."""
import json, re, subprocess

import bl_cli
from bl_base import (
    IN_SPRINT, OPEN, REL_DIR, SIMILAR_MIN, SIMILAR_SHOWN, SIMILAR_WORDS, STARTS, START_GATE, STOP_WORDS, Backlog,
    KINDS, Refused, Rejected, canonical, external_lines, external_refs, git, line, need, open_gates, say, scope,
    waits, withhold,
)
from bl_check import knowledge_lines
from bl_plan import start_approved, touches_meet, tracked_files, where_outside


def ready(bl, sprint=None, any_sprint=False):
    ids = [i for i in bl.items if not waits(bl, i, any_sprint)
           and (sprint is None or bl.sprint_of(i) == sprint)]
    return sorted(ids, key=bl.order_key)


def words(text):
    """The words similar compares: lowercased runs of letters and digits, stop words and single characters left out."""
    return {w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if len(w) > 1 and w not in STOP_WORDS}


def similar(bl, text, exclude=()):
    """Open items ranked by word overlap with text: (score, shared count, id) for each item that shares a word, the
    score the share of text's words found in the item's title and goal; highest first, then most shared, then id."""
    q = words(text)
    out = []
    for iid, it in bl.items.items():
        if iid in exclude or it.get("kind") == "sprint" or it.get("status") not in OPEN:
            continue
        shared = q & words(f"{it.get('title', '')} {it.get('goal', '')}")
        if shared:
            out.append((round(len(shared) / len(q), 2), len(shared), iid))
    return sorted(out, key=lambda r: (-r[0], -r[1], r[2]))


def is_near(row):
    return row[0] >= SIMILAR_MIN and row[1] >= SIMILAR_WORDS


def cmd_similar(bl, a):
    text = f"{a.title} {a.goal or ''}"
    if not words(text):
        raise Refused("similar: the title holds no word to compare")
    rows = similar(bl, text)
    for row in rows[:SIMILAR_SHOWN]:
        say(f"{row[0]:.2f}  {row[1]:>2}  {'near' if is_near(row) else '    '}  {bl.label(row[2])}")
    say(f"similar: {len(rows)} open item(s) share a word, {sum(map(is_near, rows))} near-duplicate(s)")
    return 0


def cmd_list(bl, a):
    for iid in sorted(bl.items, key=lambda i: (bl.items[i].get("kind") != "sprint", bl.order_key(i)
                                               if bl.items[i].get("kind") != "sprint" else i)):
        it = bl.items[iid]
        if (a.kind and it.get("kind") != a.kind) or (a.status and it.get("status") != a.status) \
                or (a.sprint and bl.sprint_of(iid) != a.sprint and iid != a.sprint):
            continue
        say(line(bl, iid))
    return 0


def cmd_find(bl, a):
    want = [w.lower() for w in a.words if w.strip()]
    if not want:
        raise Refused("find: give at least one word")
    def text(it):  # the title and goal, and the external ids and their refs as words of the title
        ids = " ".join(f"{x} {ref}" for _, x, ref, _ in external_refs(it))
        return f"{it.get('title', '')} {it.get('goal', '')} {ids}".lower()

    hits = sorted((i for i, it in bl.items.items() if it.get("kind") != "sprint" and it.get("status") in OPEN
                   and all(w in text(it) for w in want)), key=bl.order_key)
    if not hits:
        say(f"find: no open item holds {' '.join(want)}")
        return 1
    for i in hits:
        say(line(bl, i))
        for p in bl.ancestors(i):
            say(f"  parent: {bl.label(p)}")
    return 0


def cmd_tree(bl, a):
    def shown(i):
        return not a.open or bl.items[i].get("status") not in ("done", "dropped")

    def walk(i, depth):
        say("  " * depth + line(bl, i))
        for c in sorted(bl.children(i), key=bl.order_key):
            if shown(c):
                walk(c, depth + 1)

    if a.id:
        walk(need(bl, a.id), 0)
        return 0
    if a.sprint:
        need(bl, a.sprint)
        say(line(bl, a.sprint))
        for i in sorted((i for i in bl.sprint_items(a.sprint) if bl.items[i].get("sprint") and shown(i)),
                        key=bl.order_key):
            walk(i, 1)
        return 0
    for i in sorted((i for i, it in bl.items.items() if not it.get("parent") and it.get("kind") != "sprint"
                     and shown(i)), key=bl.order_key):
        walk(i, 0)
    return 0


def cmd_show(bl, a):
    iid = need(bl, a.id)
    say(canonical(bl.items[iid]).rstrip())
    for p in bl.ancestors(iid):
        say(f"parent: {bl.label(p)}")
    sp = bl.sprint_of(iid)
    if sp:
        say(f"sprint: {bl.label(sp)}")
    for c in bl.children(iid):
        say(f"child: {line(bl, c)}")
    for x in external_lines(bl.items[iid]):
        say(x)
    for x in knowledge_lines(bl, iid, indent=""):
        say(x)
    w = waits(bl, iid)
    say("ready" if not w else "waits on:\n  " + "\n  ".join(w))
    return 0


def cmd_next(bl, a):
    ids = ready(bl, a.sprint, a.any)
    if not ids:
        say("nothing ready" + (f" in {bl.label(a.sprint)}" if a.sprint else "") + ": python3 _tools/backlog.py horizon")
        return 1
    for i in ids if a.all else ids[:1]:
        say(line(bl, i))
        for x in knowledge_lines(bl, i):
            say(x)
    return 0


def items_at(root, ref):
    """{id: item} of the item files as git REF has them (a fetched origin/main holds every pushed claim); a file
    that is not a JSON object is left out. Exit 2 (Rejected) for a ref git cannot read."""
    try:
        names = [n for n in git(root, "ls-tree", "--name-only", f"{ref}:{REL_DIR}").splitlines() if n.endswith(".json")]
    except Refused as e:
        raise Rejected(f"held --ref {ref}: {e}") from e
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True,
                       input="".join(f"{ref}:{REL_DIR}/{n}\n" for n in names).encode("utf-8"))
    data, out, at = p.stdout, {}, 0
    for n in names:
        nl = data.find(b"\n", at)
        if nl < 0:
            break
        head = data[at:nl].split()
        if len(head) != 3 or head[1] != b"blob":  # `<name> missing`: nothing follows the header
            at = nl + 1
            continue
        size = int(head[2])
        body, at = data[nl + 1:nl + 1 + size], nl + 2 + size
        try:
            item = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            out[n[:-len(".json")]] = item
    return out


def held_line(bl, iid, glob):
    it = bl.items[iid]
    sp = bl.sprint_of(iid)
    return f"{glob}  {bl.label(iid)}  by {it.get('claimed_by')}  {bl.label(sp) if sp else 'no sprint'}"


def cmd_held(bl, a):
    """The touches of every claimed (doing) item, one line per glob: the glob, the item, its claimer and its sprint.
    --overlaps ID: only the claimed items outside ID's own chain whose touches overlap ID's scope (its touches and
    its descendants'), each line naming the glob of ID's it meets; exit 1 when there is one. A kb/_self doc meets
    nothing (bl_plan.touches_meet): items that share only docs run at once."""
    mine = bl
    if a.ref:
        bl = Backlog(bl.root)
        bl.items, bl.raw = items_at(bl.root, a.ref), {}
    doing = sorted(i for i, it in bl.items.items() if it.get("status") == "doing" and it.get("claimed_by")
                   and it.get("kind") != "sprint")
    if not a.overlaps:
        rows = sorted((t, i) for i in doing for t in bl.items[i].get("touches", []) or [] if isinstance(t, str) and t)
        for t, i in rows:
            say(held_line(bl, i, t))
        if not rows:
            say("held: no claimed item holds a path")
        return 0
    src = mine if a.overlaps in mine.items else bl
    iid = need(src, a.overlaps)
    chain = {iid, *src.ancestors(iid), *src.descendants(iid)}
    own = [t for t in scope(src, iid) if isinstance(t, str) and t]
    files = tracked_files(bl.root)
    hits = []
    for i in doing:
        if i in chain:
            continue
        for t in bl.items[i].get("touches", []) or []:
            met = [m for m in own if isinstance(t, str) and t and touches_meet(m, t, files)]
            if met:
                hits.append(f"{held_line(bl, i, t)}  meets {', '.join(met)}")
    for x in sorted(hits):
        say(x)
    if not hits:
        say(f"held: no claimed item's touches overlap {src.label(iid)}")
    return 1 if hits else 0


def horizon(bl, sid):
    """(reachable open ids, {cause: [stuck ids]}, critical path [ids], level widths) for a sprint."""
    items = [i for i in bl.sprint_items(sid) if bl.items[i].get("status") not in ("done", "dropped")]
    cause = {}
    if bl.items[sid].get("status") != "active":
        g = next((g for g in bl.items[sid].get("gates", []) if g.get("id") == START_GATE), {})
        why = (STARTS + sid if start_approved(bl.items[sid])
               else f"the sprint's start gate: {g.get('question', 'not started')}")
        cause = {i: why for i in items}
    for i in items:
        outside = []
        for x in [i] + bl.ancestors(i):
            it = bl.items[x]
            for g in open_gates(it):
                cause[i] = f"gate {x}/{g['id']} ({bl.items[x]['title']}): {g['question']}" + (
                    f" [recommended: {g['recommendation']}]" if g.get("recommendation") else "")
            if it.get("trigger") and not it["trigger"].get("fired"):
                cause[i] = f"trigger on {bl.label(x)}: {it['trigger']['when']}"
            for d in it.get("depends_on", []):
                if d not in items and bl.items.get(d, {}).get("status") != "done" and d not in outside:
                    outside.append(d)
        if outside:
            cause[i] = "outside this sprint: " + ", ".join(
                f"{bl.label(d)} ({where_outside(bl, d) if d in bl.items else 'not found'})" for d in outside)
    # propagate: an item waits on what its own and its ancestors' dependencies, its children
    # and (for the review) the sprint wait on
    edges = {i: list(dict.fromkeys(d for x in [i] + bl.ancestors(i) for d in bl.items[x].get("depends_on", [])
                                   if d in items))
             + [c for c in bl.children(i) if c in items] for i in items}
    for i in items:
        if bl.items[i].get("review"):
            edges[i] += [s for s in items if s != i and bl.items[s].get("kind") in IN_SPRINT]
    changed = True
    while changed:
        changed = False
        for i in items:
            if i not in cause:
                src = next((cause[d] for d in edges[i] if d in cause), None)
                if src:
                    cause[i], changed = src, True
    reach = [i for i in items if i not in cause]
    depth = {}

    def d(i, seen=()):
        if i not in depth:
            depth[i] = 1 + max((d(x, seen + (i,)) for x in edges[i] if x in reach and x not in seen), default=0)
        return depth[i]

    for i in reach:
        d(i)
    path = []
    if reach:
        cur = max(reach, key=lambda i: (depth[i], i))
        while cur:
            path.append(cur)
            nxt = [x for x in edges[cur] if x in reach and depth.get(x) == depth[cur] - 1]
            cur = min(nxt) if nxt else None
    widths = [sum(1 for i in reach if depth[i] == k) for k in range(1, (max(depth.values()) if depth else 0) + 1)]
    by_cause = {}
    for i, c in cause.items():
        by_cause.setdefault(c, []).append(i)
    return reach, by_cause, list(reversed(path)), widths


def finishable(bl, items):
    """The open items of ITEMS whose children are all done or dropped (at least one): a story or bug whose own
    `done` is the step left, which next never offers since it waits on no child (ST-bywuxi6d)."""
    out = []
    for i in items:
        kids = bl.descendants(i)
        if bl.items[i].get("status") not in ("done", "dropped") and kids \
                and all(bl.items[k].get("status") in ("done", "dropped") for k in kids):
            out.append(i)
    return out


def cmd_horizon(bl, a):
    sprints = [a.sprint] if a.sprint else sorted(i for i, it in bl.items.items()
                                                  if it.get("kind") == "sprint" and it.get("status") == "active")
    lines = []
    if not sprints:
        planned = [i for i, it in bl.items.items() if it.get("kind") == "sprint"]
        n = sum(1 for it in bl.items.values() if it.get("kind") != "sprint" and it.get("status") not in ("done", "dropped"))
        lines.append(f"backlog: no active sprint; {n} open item(s)"
                     + (", planned: " + ", ".join(bl.label(s) + (f" (approved, not started: backlog.py start {s})"
                                                                 if start_approved(bl.items[s]) else "")
                                                for s in planned) if planned else "")
                     + " (python3 _tools/backlog.py tree)")
    elif not a.sprint:  # an approved sprint waits on start beside the active ones: first, so the hook never cuts it
        for sid in sorted(i for i, it in bl.items.items() if it.get("kind") == "sprint"
                          and it.get("status") == "planned" and start_approved(it)):
            title = clip(bl.items[sid].get("title", ""), HOOK_TITLE) if a.hook else bl.items[sid].get("title", "")
            lines.append(f"sprint {sid} “{title}”: approved, not started; next step: "
                         f"python3 _tools/backlog.py start {sid}")
    for sid in sprints:
        need(bl, sid)
        items = bl.sprint_items(sid)
        done = sum(1 for i in items if bl.items[i].get("status") in ("done", "dropped"))
        reach, stuck, path, widths = horizon(bl, sid)
        starts = len(stuck.get(STARTS + sid, []))  # approved: they wait on backlog.py start, not on the operator
        waiting = sum(map(len, stuck.values())) - starts
        if a.hook:  # every session reads it: id and title, counts and the next id; horizon without --hook has the rest
            nxt = ready(bl, sid)
            lines.append(f"sprint {sid} “{clip(bl.items[sid].get('title', ''), HOOK_TITLE)}”: "
                         f"{done}/{len(items)} done, {len(reach)} reachable"
                         + (f", close with backlog.py close {sid}" if items and done == len(items) else "")
                         + (f", {starts} wait on backlog.py start" if starts else "")
                         + (f", {waiting} wait on the operator or a trigger" if waiting else "")
                         + (f", next {nxt[0]}" if nxt else ""))
            for c, ids in stuck.items():
                lines.append(f"  waiting on {clip(c, HOOK_CAUSE)}: " + ", ".join(ids[:5]))
            continue
        lines.append(f"sprint {bl.label(sid)} [{bl.items[sid].get('status')}]: goal {bl.items[sid].get('goal')}")
        lines.append(f"  {done}/{len(items)} done; {len(reach)} more reachable without the operator; "
                     + (f"{starts} wait on backlog.py start {sid}; " if starts else "")
                     + f"{waiting} wait on the operator or a trigger")
        if items and done == len(items):
            lines.append(f"  all done: close with python3 _tools/backlog.py close {sid}")
        for i in finishable(bl, items):
            lines.append(f"  finish with python3 _tools/backlog.py done {i}: {bl.label(i)} (every child is done)")
        nxt = ready(bl, sid)
        if nxt:
            lines.append(f"  next: {bl.label(nxt[0])}")
            if not a.hook:  # the SessionStart hook runs no pack
                lines += knowledge_lines(bl, nxt[0], indent="    ")
        if path:
            lines.append(f"  critical path ({len(path)} steps, parallel width per step {widths}): "
                         + " -> ".join(bl.label(i) for i in path))
        for c, ids in stuck.items():
            lines.append(f"  waiting on {c}")
            for i in ids[:5 if a.hook else 50]:
                lines.append(f"    {bl.label(i)}")
    text = withhold("\n".join(lines))
    if a.hook:
        print(hook_json(text))
    else:
        say(text)
    return 0


HOOK_MAX = 1000  # characters of the hook's whole stdout (its newline included), which every session in a clone reads


HOOK_TITLE = 48  # characters of a sprint title on a hook line


HOOK_CAUSE = 100  # characters of a waiting cause (a gate's question, a trigger) on a hook line


def clip(s, n):
    """s cut to n characters, its last one an ellipsis when cut."""
    return s if len(s) <= n else s[:n - 1] + "…"


def hook_json(text):
    """The SessionStart hook's JSON for text, under HOOK_MAX: its last lines give way, newest first, to one line
    naming how many were left out and the command that prints them, whatever the number of sprints."""
    def dump(t):
        return json.dumps({"systemMessage": t, "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": t + "\nGoals and critical paths: python3 _tools/backlog.py horizon. "
                                     "The backlog runbook is kb/_self/backlog.md."}}, ensure_ascii=False)
    lines, cut, out = text.split("\n"), 0, dump(text)
    while len(out) + 1 >= HOOK_MAX and lines:
        lines.pop()
        cut += 1
        out = dump("\n".join(lines + [f"(+{cut} more line(s): python3 _tools/backlog.py horizon)"]))
    return out


def args_similar(p):
    p.add_argument("title")
    p.add_argument("--goal")


def args_list(p):
    p.add_argument("--kind", choices=list(KINDS))
    p.add_argument("--status")
    p.add_argument("--sprint")


def args_tree(p):
    p.add_argument("id", nargs="?")
    p.add_argument("--sprint")
    p.add_argument("--open", action="store_true")


def args_find(p):
    p.add_argument("words", nargs="+")


def args_show(p):
    p.add_argument("id")


def args_next(p):
    p.add_argument("--sprint")
    p.add_argument("--any", action="store_true")
    p.add_argument("--all", action="store_true")


def args_held(p):
    p.add_argument("--overlaps", metavar="ID", help="only the claimed items whose touches overlap this item's")
    p.add_argument("--ref", help="read the claims from this git ref (origin/main after git fetch) instead of the files")


def args_horizon(p):
    p.add_argument("--sprint")
    p.add_argument("--hook", action="store_true")


bl_cli.register("similar", cmd_similar, args_similar)
bl_cli.register("list", cmd_list, args_list)
bl_cli.register("tree", cmd_tree, args_tree)
bl_cli.register("find", cmd_find, args_find)
bl_cli.register("show", cmd_show, args_show)
bl_cli.register("next", cmd_next, args_next)
bl_cli.register("held", cmd_held, args_held)
bl_cli.register("horizon", cmd_horizon, args_horizon)
