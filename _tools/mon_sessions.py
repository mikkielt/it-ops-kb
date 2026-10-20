"""kbmon's sessions panel (kb/_self/monitoring.md): the processes working in a checkout of the clone, the clone's worktrees
with their branches and the stalled items with their signals.

The processes are `backlog.py procs`' inventory (`bl_procs.snapshot`): pid, age and class (`orphan`, `hook` or `foreign`),
each with its checkout as a path relative to the clone (`.` is the clone itself; a worktree outside it is its directory
name), never an absolute one. A process whose command name is `claude` is a Claude Code session: `headless`, with its item,
when its checkout is a worktree on a `work/<id>` branch, else `interactive`; any other process has no session. The worktrees
are `git worktree list`'s, and the stalled items are `bl_stall.collect`'s, only those with a signal. `operator` is this
clone's operator id and role (`kbwho.operator()`, never an email) and `intents` the live session intents of the coord store
(`coord.py digest`: session, item and the `operator` the hook posted, none for an intent that carries no operator); a
store that is not there or does not answer leaves `intents` out. The panel makes no
forge request, so the `mr-dead` signal is never read here (`backlog.py stalled` reads it). A host that cannot list working
directories gives no processes and `procs_unreadable`, the reason, so the operator and the intents still show; a root with
no backlog items has no `stalled` key. Imports `mon_base`; `bl_procs`,
`bl_stall` and `bl_base` where it reads them.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import mon_base

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


def no_request(argv, cwd=None):
    """The runner of bl_stall's forge reads: the panel starts no network request, so every read fails at once."""
    raise OSError("kbmon makes no forge request")


def display_names(root, bases):
    """{directory name: path relative to the clone} for the checkouts BASES: `.` for the clone itself, the path under it
    for a worktree inside it, else the directory name alone."""
    base = os.path.realpath(root)
    out = {}
    for b in bases:
        name = Path(b).name
        if b == base:
            out[name] = "."
        else:
            rel = os.path.relpath(b, base)
            out[name] = name if rel.startswith("..") or os.path.isabs(rel) else rel.replace(os.sep, "/")
    return out


def branches(root):
    """([{path, branch}] of the clone's worktrees, paths as `display_names` gives them; {directory name: branch}). A
    directory name that two worktrees share tells no worktree a process is in, so it has no branch in the map."""
    import bl_stall
    found = [(os.path.realpath(p), b) for p, b in bl_stall.worktrees(str(root)) or []]
    names = display_names(root, [p for p, _ in found])
    rows = [{"path": names[Path(p).name], "branch": b} for p, b in found]
    count = {}
    for p, _ in found:
        count[Path(p).name] = count.get(Path(p).name, 0) + 1
    return rows, {Path(p).name: b for p, b in found if count[Path(p).name] == 1}


def session_of(proc, by_name):
    """(session, item) of a process: none for a process that is no Claude Code one."""
    if proc["comm"] != CLAUDE:
        return None, None
    first = proc["where"].split("/", 1)[0]
    m = WORK_BRANCH.fullmatch(by_name.get(first) or "")
    return ("headless", m.group(1)) if m else ("interactive", None)


def stalled(root):
    """[{item, signals}] of the items that show a signal, or None when the root has no backlog items."""
    import bl_base
    import bl_stall
    bl = bl_base.Backlog(root)
    if not bl.items:
        return None
    bl_base.load_settings(root)
    report = bl_stall.collect(bl, run=no_request)
    return [{"item": r["id"], "signals": r["signals"]} for r in report["items"] if r["signals"]]


def live_intents(ctx):
    """[{session, item, operator}] of the live session intents in the coord store (`coord.py digest`), or None when the
    store is not there, is not reachable or does not answer."""
    import mon_coord
    if ctx.url:
        if not ctx.key_file:
            return None
        conn = ["--url", ctx.url, "--key-file", ctx.key_file]
    else:
        store = mon_coord.local_store(ctx)
        if not store or not Path(store).is_file():
            return None
        conn = ["--store", store]
    try:
        p = subprocess.run([sys.executable, str(mon_coord.COORD), *conn, "digest", "--key", "*", "--lines", str(INTENTS_KEPT)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=COORD_SECONDS,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    out = []
    for line in p.stdout.splitlines():
        if not line.startswith("intent "):
            continue
        fields = dict(w.split("=", 1) for w in line.split()[1:] if "=" in w)
        row = {"session": fields.get("session"), "item": fields.get("item"), "operator": fields.get("operator")}
        if row["session"] and row not in out:
            out.append(row)
    return out


def collect(ctx):
    import bl_procs
    import kbwho
    procs, _, why = bl_procs.snapshot(str(ctx.root))
    now = time.time()
    rows, by_name = branches(ctx.root)
    names = display_names(ctx.root, bl_procs.checkouts(str(ctx.root))) if procs is not None else {}
    out = []
    for p in procs or []:
        session, item = session_of(p, by_name)
        first, _, rest = p["where"].partition("/")
        shown = names.get(first, first)
        out.append({"pid": p["pid"], "age_s": max(0, int(now - p["start"])), "class": p["kind"],
                    "checkout": shown + ("/" + rest if rest else ""), "session": session, "item": item})
    me = kbwho.operator()
    data = {"procs": out, "worktrees": rows, "operator": {"id": me.get("id"), "role": me.get("role")}}
    if procs is None:
        data["procs_unreadable"] = why
    intents = live_intents(ctx)
    if intents is not None:
        data["intents"] = intents
    items = stalled(ctx.root)
    if items is not None:
        data["stalled"] = items
    return data


def alerts(data):
    """The alerts of the panel's data: one `orphan` alert (id `sessions.orphan`) while a process of class `orphan` is listed;
    its message counts them and names the oldest one's pid."""
    orphans = [p for p in data.get("procs") or [] if isinstance(p, dict) and p.get("class") == "orphan"]
    if not orphans:
        return []
    oldest = max(orphans, key=lambda p: p.get("age_s") or 0)
    return [{"kind": "orphan", "id": "sessions.orphan", "panel": "sessions", "since": "",
             "message": f"{len(orphans)} orphan process{'' if len(orphans) == 1 else 'es'}, the oldest pid {oldest.get('pid')} "
                        f"for {age_text(oldest.get('age_s') or 0)}"}]


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


def lines(data, width=80):
    """The body rows: the processes table (an orphan's row starts `! `, orphans first, PROCS_SHOWN at most), the worktrees
    with their branches, and the stalled items, each a `! ` row of its id and signals; first the clone's operator and the live
    session intents (session, item, operator)."""
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
    if procs:
        shown = procs[:PROCS_SHOWN]
        rows += [("! " if flag else "") + text for flag, text in table(shown, width - 2)]
        if len(procs) > len(shown):
            rows.append(f"+{len(procs) - len(shown)} more")
    elif data.get("procs_unreadable"):
        rows.append("processes unreadable: " + str(data["procs_unreadable"]))
    else:
        rows.append("processes none")
    trees = sorted(data.get("worktrees", []), key=lambda w: not (w.get("branch") or "").startswith("work/"))
    parts = [f"{w['path']}  {w.get('branch') or '(detached)'}" for w in trees[:TREES_SHOWN]]
    if len(trees) > TREES_SHOWN:
        parts.append(f"+{len(trees) - TREES_SHOWN} more")
    rows += joined("worktrees", parts, width - 2) if trees else ["worktrees none"]
    if "stalled" in data:
        items = data["stalled"]
        for i, s in enumerate(items):
            rows.append("! " + ("stalled".ljust(LABEL - 2) if i == 0 else " " * (LABEL - 2)) + f"{s['item']}  "
                        + ", ".join(s["signals"]))
        if not items:
            rows.append("stalled".ljust(LABEL) + "none")
    return rows
