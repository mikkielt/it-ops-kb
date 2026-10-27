"""`backlog.py peers`: what the other live sessions and the integration main's plans work on (kb/_self/backlog.md,
Sessions plan with each other; kb/_self/tools.md).

  peers [--sprint SP | --item ID | --touch GLOB...]
                               print, read only and with no model call (exit 0 unless a file is shared), the other
                               sessions of the clone, each with its label, `live` or `ended` (a Claude Code process of the
                               clone runs it or none does), role, topics, items and files and the open asks addressed to it
                               (those addressed to this session follow them: an ask records no asker); the
                               active and planned sprints on the integration main (`bl_plan.history_ref`) with their
                               items and the files of those; and the held claims there (doing items and their files).
                               With a sprint, an item or touches it also names each file that work shares with them,
                               one line each: `doc` for a kb/_self doc (`bl_plan.shared_doc`: the landing's rebase
                               merges its sections, so it orders nothing and is shown for the landing order), `overlap`
                               for any other file (`bl_plan.touches_meet`); exit 1 when an overlap is found.

A session's items and files come from its live coord intents (`mon_sessions.read_coord`, one `coord.py digest`) and the
files of the items it names; the sessions from `mon_sessions.live_sessions`, one for each `claude` process of the
clone, with a session that holds a lease and an intent but shows no process. This session's own intents (the id in
`CLAUDE_CODE_SESSION_ID`) are left out, and a session shows as its label (`mon_view.session_label`), never its id or its
checkout's path. The work's own sprint (or the sprint of its item) is left out of the plans, since its items are
planned together. `reach` tells `kbask.py ask` whether a session id has ended, and which live session works on its items. `peer_overlaps` is the same comparison for `precheck`: each committed item's file that a peer also plans,
unless a depends_on or a `coordinate` event settles the pair. Standard library only; imports `bl_base`, `bl_cli`, `bl_plan` and `bl_view` at load, and the monitor's
modules where it reads the sessions. It registers its own subcommand when imported.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import bl_cli
from bl_base import Backlog, Rejected, glob_re, need, operator_who, resolved_touch, say, scope
from bl_clean import run_coord
from bl_plan import history_ref, shared_doc, touch_files, touches_meet
from bl_view import items_at


HOLDERS_SHOWN = 6  # the holders one shared-file line names; a doc most items name would fill the screen
ASK_SECONDS = 10  # the longest one coord.py read of the asks may take
ASK_CHARS = 60  # characters of a question peers prints
PLAN_TOUCH_CHARS = 120  # the width of an intent's touch field (coord.py refuses more)
PLAN_WORD = re.compile(r"[A-Za-z0-9_.:/#@*?-]+")  # what coord accepts in a touch path
PLAN_SESSION = re.compile(r"[A-Za-z0-9_.:/#@-]{1,120}")  # what coord accepts as a field value


def args_peers(p):
    work = p.add_mutually_exclusive_group()
    work.add_argument("--sprint", help="the sprint whose items' files are compared with the peers'")
    work.add_argument("--item", help="the item whose scope (its touches and its descendants') is compared")
    work.add_argument("--touch", nargs="+", action="extend", metavar="GLOB", help="the files or globs to compare")


def split_list(value):
    return [w for w in value.split(",") if w] if isinstance(value, str) else []


def read_found(root, events):
    """`mon_sessions.read_coord`'s answer for the clone ROOT, with the coordinate events read when EVENTS; an empty answer
    where no coord store answers."""
    import mon_base
    import mon_sessions
    return mon_sessions.read_coord(mon_base.Ctx(Path(root).resolve()), events=events) or {"intents": [], "leases": {}, "coordinate": []}


def live_peers(root, own, found=None):
    """[{label, role, topics, items, files}] of the live sessions other than OWN (a raw session id or None), oldest first,
    and the claim-less rest: a lease with an intent but no process comes last. [] where no coord store answers. FOUND is
    an answer of `read_found` already read."""
    import mon_sessions
    import mon_view
    found = found or read_found(root, False)
    out, seen = [], set()
    for s in mon_sessions.live_sessions(root):
        sid = s["session"]
        if sid and sid == own:
            continue
        seen.add(sid)
        out.append({"sid": sid, "label": s["label"] or "unbound", "role": s["role"], "live": True,
                    "items": [s["item"]] if s["item"] else []})
    for sid in found["leases"]:
        if sid not in seen and sid != own and mon_view.SESSION_ID.fullmatch(sid) and any(f.get("session") == sid for f in found["intents"]):
            out.append({"sid": sid, "label": mon_view.session_label(sid), "role": "no process seen", "live": False, "items": []})
    for s in out:
        intents = [f for f in found["intents"] if s["sid"] and f.get("session") == s["sid"]]
        s["topics"] = list(dict.fromkeys(f["topic"] for f in intents if f.get("topic")))
        s["items"] = list(dict.fromkeys(s["items"] + [i for f in intents for i in split_list(f.get("item"))]))
        s["touch"] = list(dict.fromkeys(t for f in intents for t in split_list(f.get("touch"))))
    return out


def ask_events(root, kind):
    """The events of the kind KIND (`ask` or `answer`) in the coord store of the clone ROOT, oldest first; [] where it does not answer."""
    import mon_base
    import mon_coord
    import mon_sessions
    conn = mon_sessions.coord_conn(mon_base.Ctx(Path(root).resolve()))
    if conn is None:
        return []
    try:
        p = subprocess.run([sys.executable, str(mon_coord.COORD), *conn, "wait", "--since", "0", "--timeout", "0", "--kind", kind],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=ASK_SECONDS,
                           stdin=subprocess.DEVNULL)
        got = json.loads(p.stdout)["events"] if p.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return []
    return [e for e in got if isinstance(e, dict) and isinstance(e.get("fields"), dict)]


def open_asks(root, targets):
    """{target: [(ask id, question)]} of the asks to each of TARGETS (raw session ids) that no closing answer ended
    (`mon_coord.CLOSED`), oldest first, the question redacted and cut to ASK_CHARS. An ask records no asker, so these are the
    asks addressed to the session, whoever sent them."""
    import mon_coord
    import redact
    closed = {e["fields"].get("id") for e in ask_events(root, "answer") if e["fields"].get("state") in mon_coord.CLOSED}
    out = {}
    for e in ask_events(root, "ask"):
        f = e["fields"]
        if f.get("to") in targets and f.get("id") and f["id"] not in closed:
            code, body, _err = run_coord("get", f["ref"]) if f.get("ref") else (2, None, "")
            text = " ".join(str(body.get("value") or "").split()) if code == 0 and isinstance(body, dict) else ""
            text = redact.redact(text)
            out.setdefault(f["to"], []).append((f["id"], text if len(text) <= ASK_CHARS else text[:ASK_CHARS - 3] + "..."))
    return out


def reach(root, target, asker, store=None):
    """(state, items, successors) for the session id TARGET as the session id ASKER (None for none) sees it from the clone ROOT:
    `live` when a Claude Code process of the clone is bound to it, `ended` when none is and it either announced an intent or
    the asker is no live session of the clone (a caller that is none cannot be told apart from a session that never ran),
    else `unknown` (it left no trace and a live asker may be seeing it start). Windows lists no process by working directory,
    so it is always `unknown`, as is a clone with a process no session id binds (it may be the target). ITEMS are the items
    the target's intents name and SUCCESSORS the labels of the other live sessions, the asker left out, whose intents or
    item name one of them. STORE, when given, is the coord store the ask goes to."""
    import mon_sessions
    import mon_view
    if os.name == "nt":
        return "unknown", [], []
    saved = os.environ.get("KB_COORD_STORE")
    if store:
        os.environ["KB_COORD_STORE"] = store
    try:
        live = mon_sessions.live_sessions(root)
        found = read_found(root, False)
    except Exception:  # a host that cannot list its processes or read the store leaves the ask allowed
        return "unknown", [], []
    finally:
        if store and saved is None:
            os.environ.pop("KB_COORD_STORE", None)
        elif store:
            os.environ["KB_COORD_STORE"] = saved
    ids = {s["session"] for s in live if s["session"]}
    if target in ids:
        return "live", [], []
    intents = [f for f in found["intents"] if f.get("session") == target]
    if any(s["session"] is None for s in live) or not (intents or asker not in ids):
        return "unknown", [], []
    items = list(dict.fromkeys(i for f in intents for i in split_list(f.get("item"))))
    successors = []
    for s in live:
        sid = s["session"]
        if sid and sid != asker and (set(items) & ({s["item"]} | {i for f in found["intents"] if f.get("session") == sid
                                                                for i in split_list(f.get("item"))})):
            successors.append(mon_view.session_label(sid))
    return "ended", items, successors


def item_touches(items, iid):
    return [t for t in (items.get(iid) or {}).get("touches", []) or [] if isinstance(t, str) and t]


def plan_rows(main, skip_sprint, skip_items):
    """[(sprint id, title, status, [(item id, title, [touch])])] of the active and planned sprints of MAIN (a Backlog read
    at the integration main), SKIP_SPRINT and the items in SKIP_ITEMS left out."""
    out = []
    for sid, sp in sorted(main.items.items()):
        if sp.get("kind") != "sprint" or sp.get("status") not in ("active", "planned") or sid == skip_sprint:
            continue
        rows = [(i, main.items[i].get("title", ""), item_touches(main.items, i)) for i in sorted(main.sprint_items(sid))
                if i not in skip_items and main.items[i].get("status") not in ("done", "dropped")]
        out.append((sid, sp.get("title", ""), sp.get("status"), rows))
    return out


def claim_rows(main, skip_items):
    """[(item id, title, claimer, sprint id or None, [touch])] of the doing items of MAIN that a session claimed."""
    return [(i, it.get("title", ""), it.get("claimed_by"), main.sprint_of(i), item_touches(main.items, i))
            for i, it in sorted(main.items.items())
            if it.get("status") == "doing" and it.get("claimed_by") and it.get("kind") != "sprint" and i not in skip_items]


def work_of(bl, a):
    """(touches, items to leave out of the plans, sprint to leave out) of the work the arguments name: ([], set(), None)
    for none."""
    if a.touch:
        return list(dict.fromkeys(a.touch)), set(), None
    if a.item:
        iid = need(bl, a.item)
        sid = bl.sprint_of(iid)
        return [t for t in scope(bl, iid) if isinstance(t, str) and t], {iid, *bl.descendants(iid)}, sid
    if a.sprint:
        sid = need(bl, a.sprint)
        items = bl.sprint_items(sid)
        return list(dict.fromkeys(t for i in items for t in scope(bl, i) if isinstance(t, str) and t)), set(items), sid
    return [], set(), None


def shown_path(work, other):
    """The path to name for two touches that meet: the one without glob characters, else the work's."""
    plain = lambda t: not any(c in t for c in "*?[")
    return resolved_touch(other) if plain(other) and not plain(work) else resolved_touch(work)


def shares(touches, holders, files):
    """{(kind, path): [holder]} for each touch in TOUCHES that a holder's touches share: `overlap` where touches_meet says
    so, `doc` where both are kb/_self docs that name one file. HOLDERS is [(text, [touch])]."""
    out = {}
    for w in touches:
        for who, theirs in holders:
            for t in theirs:
                if touches_meet(w, t, files):
                    kind = "overlap"
                elif shared_doc(w) and shared_doc(t) and (glob_re(resolved_touch(w)).match(resolved_touch(t))
                                                          or glob_re(resolved_touch(t)).match(resolved_touch(w))):
                    kind = "doc"
                else:
                    continue
                held = out.setdefault((kind, shown_path(w, t)), [])
                if who not in held:
                    held.append(who)
    return out


def ordered(items, a, b):
    """True when the depends_on edges of ITEMS (a dict of item dicts) lead from A to B or from B to A, through other items."""
    def reaches(start, goal):
        seen, todo = set(), [start]
        while todo:
            cur = todo.pop()
            if cur == goal:
                return True
            if cur not in seen:
                seen.add(cur)
                todo += [d for d in (items.get(cur) or {}).get("depends_on", []) or [] if isinstance(d, str)]
        return False
    return reaches(a, b) or reaches(b, a)


def coordinated(events, iid, names):
    """True when a `coordinate` event of EVENTS (`mon_sessions.read_events`' tuples) has IID on one side and any of NAMES
    (an item, a topic or a session label of the other work) on the other."""
    return any((i == iid and o in names) or (o == iid and i in names) for i, o, _strategy, _who, _at in events)


def peer_overlaps(bl, sid, ids):
    """[(item id, path, [other work])] for each of the sprint SID's items IDS and each file of its scope that another live
    session's plan or another active or planned sprint's item of the integration main also plans, a kb/_self doc left out
    (`shares`, `overlap`), the other work named as `session LABEL ...` or `ITEM in sprint SP`. A pair that is ordered (the
    item `depends_on` the other, or the other way, through other items) or that a `coordinate` event names (the item and the
    other work's item, topic or session label) is settled and left out. The sprint's own items are not peers. [] where
    none of the items has a touch. A ref that holds no item directory gives no sprint plans, and the sessions are still compared."""
    mine = {i: [t for t in scope(bl, i) if isinstance(t, str) and t] for i in ids}
    if not any(mine.values()):
        return []
    found = read_found(bl.root, True)
    main = Backlog(bl.root)
    try:
        main.items, main.raw = items_at(bl.root, history_ref(bl.root)), {}
    except Rejected:  # the ref holds no item directory yet: no held plans
        main.items, main.raw = {}, {}
    known = {**main.items, **bl.items}
    holders = []  # ((text, items, names), [touch])
    for s in live_peers(bl.root, os.environ.get("CLAUDE_CODE_SESSION_ID") or None, found):
        touch = list(dict.fromkeys(s["touch"] + [t for i in s["items"] for t in item_touches(main.items, i)]))
        text = f"session {s['label']}" + (f" (topic {', '.join(s['topics'])})" if s["topics"] else "")
        holders.append(((text, s["items"], s["topics"] + [s["label"]]), touch))
    for psid, _title, _status, rows in plan_rows(main, sid, set(bl.sprint_items(sid))):
        holders += [((f"{iid} in sprint {psid}", [iid], []), touch) for iid, _t, touch in rows]
    events = found.get("coordinate") or []
    files = touch_files(bl.root)
    out = []
    for iid in ids:
        for (kind, path), who in sorted(shares(mine[iid], holders, files).items(), key=lambda kv: kv[0][1]):
            left = [w[0] for w in who if not any(ordered(known, iid, j) for j in w[1])
                    and not coordinated(events, iid, {*w[1], *w[2]})]
            if kind == "overlap" and left:
                out.append((iid, path, left))
    return out


def item_label(bl, main, iid):
    """The item's id and title as this clone's item files give it, else as the integration main's, else the bare id."""
    for known in (bl, main):
        if iid in known.items:
            return known.label(iid)
    return iid


def plan_chunks(touches):
    """[[path]] of the whole paths of TOUCHES that fit a coord intent's touch field, each list at most PLAN_TOUCH_CHARS
    characters joined by commas, in order; a path coord refuses (an unusual character, or alone over the width) is left out."""
    out, size = [], 0
    for path in dict.fromkeys(touches):
        if not PLAN_WORD.fullmatch(path) or len(path) > PLAN_TOUCH_CHARS:
            continue
        if out and size + 1 + len(path) <= PLAN_TOUCH_CHARS:
            out[-1].append(path)
            size += 1 + len(path)
        else:
            out.append([path])
            size = len(path)
    return out


def post_plan(bl, sid):
    """Post this session's plan for sprint SID to coord: one `intent` event with the session (`CLAUDE_CODE_SESSION_ID`), the
    sprint as its item, the topic `plan` and, as touch, the files of the sprint's open items (their scopes), several events
    when those exceed the field's width. Posts nothing, and says nothing, without a session id, for an unknown sprint, with
    `announce.to_other_sessions` false, or when coord cannot be run; a coord failure is said on one line and never fails
    the command. Returns the number of events posted."""
    own = os.environ.get("CLAUDE_CODE_SESSION_ID") or None
    if not own or bl.items.get(sid, {}).get("kind") != "sprint" or not PLAN_SESSION.fullmatch(own):
        return 0
    try:
        import kbsettings
        if not kbsettings.effective(bl.root)["coordination"]["announce"]["to_other_sessions"]:
            return 0
    except Exception:  # bad settings files leave the default: announce
        pass
    items = [i for i in sorted(bl.sprint_items(sid)) if bl.items[i].get("status") not in ("done", "dropped")]
    touches = [t for i in items for t in scope(bl, i) if isinstance(t, str) and t]
    oid = operator_who()[0]
    posted = 0
    for chunk in plan_chunks(touches):
        extra = ["--field", "operator=" + oid] if oid else []
        code, _body, err = run_coord("post", "--kind", "intent", "--field", "session=" + own, "--field", "item=" + sid,
                                     "--field", "topic=plan", "--field", "touch=" + ",".join(chunk), *extra)
        if code:
            say(f"plan: no coord intent posted for {sid}: {err or 'coord.py exited ' + str(code)}")
            break
        posted += 1
    return posted


def cmd_peers(bl, a):
    """`peers`: see the module docstring. Exit 1 when the work shares a non-doc file, else 0; 2 for an unknown id."""
    work, skip_items, skip_sprint = work_of(bl, a)
    own = os.environ.get("CLAUDE_CODE_SESSION_ID") or None
    sessions = live_peers(bl.root, own)
    ref = history_ref(bl.root)
    main = Backlog(bl.root)
    main.items, main.raw = items_at(bl.root, ref), {}
    plans = plan_rows(main, skip_sprint, skip_items)
    claims = claim_rows(main, skip_items)
    files = touch_files(bl.root)
    alive = sum(1 for s in sessions if s["live"])
    say(f"peers: {alive} other live session{'' if alive == 1 else 's'}" + (f", {len(sessions) - alive} ended" if alive < len(sessions) else "")
        + f", {len(plans)} active or planned "
        f"sprint{'' if len(plans) == 1 else 's'} on {ref.rsplit('refs/remotes/', 1)[-1]}, {len(claims)} held claim{'' if len(claims) == 1 else 's'}")
    holders = []
    asks = open_asks(bl.root, {s["sid"] for s in sessions if s["sid"]} | ({own} if own else set()))
    for s in sessions:
        touch = list(dict.fromkeys(s["touch"] + [t for i in s["items"] for t in item_touches(main.items, i)]))
        say(f"session {s['label']}  {'live' if s['live'] else 'ended'}  {(s['role'] if s['live'] else '') or 'session'}"
            + (f"  topic {', '.join(s['topics'])}" if s["topics"] else "")
            + (f"  items {', '.join(item_label(bl, main, i) for i in s['items'])}" if s["items"] else ""))
        if touch:
            say("  files " + ", ".join(touch))
        for aid, text in asks.get(s["sid"], []):
            say(f"  open ask {aid} to it" + (f": {text}" if text else ""))
        holders.append((f"session {s['label']}", touch))
    for aid, text in asks.get(own, []) if own else []:
        say(f"open ask {aid} to this session" + (f": {text}" if text else ""))
    for sid, title, status, rows in plans:
        say(f"sprint {sid}  {status}  {title}")
        for iid, ititle, touch in rows:
            say(f"  {iid}  {ititle}" + (f"  files {', '.join(touch)}" if touch else ""))
            holders.append((f"{iid} in sprint {sid}", touch))
    for iid, title, who, sid, touch in claims:
        say(f"held {iid}  {title}  by {who}" + (f"  in {sid}" if sid else "") + (f"  files {', '.join(touch)}" if touch else ""))
        holders.append((f"held {iid}", touch))
    if not (a.touch or a.item or a.sprint):
        return 0
    found = shares(work, holders, files)
    for (kind, path), who in sorted(found.items(), key=lambda kv: (kv[0][0] != "overlap", kv[0][1])):
        more = f" and {len(who) - HOLDERS_SHOWN} more" if len(who) > HOLDERS_SHOWN else ""
        say(f"{kind} {path}  also in {', '.join(who[:HOLDERS_SHOWN])}{more}")
    if not found:
        say("no file of this work is in a peer's plan")
    return 1 if any(kind == "overlap" for kind, _ in found) else 0


bl_cli.register("peers", cmd_peers, args_peers,
                help="list the other live sessions' plans, files and sprints and name each file a plan shares with them")
