"""kbmon's list of what waits on the operator (kb/_self/monitoring.md), built from one snapshot: the text view prints it as the
`needs you` line under its header and `kbmon.py --status all` starts with the same line. Standard library only; imports
nothing at load, `mon_sessions` (its age text) and `mon_status` (`short_name`) where they are used.

  entries(snap)   [{kind, text, ...}] in this order: `gate` (each open blocking gate of an active, approved or planned sprint
                  or of one of its open items, `SP-… gate NAME`), `ask` (each ask addressed to `operator` that no closing
                  answer has ended, from the coord panel: `ask ID since DATE TIME: the first words of the question`, redacted;
                  an Alertmanager alert, a cleanup verdict or a session's question posted as an ask shows here), `blocked` (an active sprint with items left, none ready and
                  none in progress), `delivery` (the query log's last delivery was refused, with the gate that failed),
                  `orphan` (each process of class `orphan`, oldest first), `disk` (under LOW_DISK_PCT percent free) and
                  `fast-forward` (the checkout is behind `origin/main` and cannot fast-forward, with the panel's why)
  unread(snap)    the panels the list reads (sprint, querylog, sessions, host) that the snapshot lacks or holds not `ok`, and
                  the coord panel when the snapshot holds it in state `timeout` or `error` (a snapshot without it, or with
                  no coord store, has no asks to read)
  line(snap)      `needs you: ` and the entries joined with `; ` (at most SHOWN of a kind, then `+N more KINDs`), `nothing`
                  when there are none, then `; not read: PANELS` for the panels `unread` names

The list reads only the panels' data, so a saved snapshot gives the same line. It calls no model and writes no file.
"""

PANELS = ("sprint", "querylog", "sessions", "host")
COORD_PANEL = "coord"
KINDS = ("gate", "ask", "blocked", "delivery", "orphan", "disk", "fast-forward")
MANY = {"gate": "gates", "ask": "asks", "blocked": "blocked sprints", "delivery": "deliveries", "orphan": "orphans", "disk": "disk",
        "fast-forward": "fast-forward"}  # the noun after `+N more`
LOW_DISK_PCT = 10  # the host panel's alert threshold
SHOWN = 3  # entries of one kind the line names before it counts the rest
WHY_CHARS = 100  # characters of a refusal's or a fast-forward cause in the line
HEAD = "needs you: "


def number(value, default=0):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def data_of(snap, name):
    """The data of panel NAME when it is `ok`, else None."""
    panel = (snap.get("panels") or {}).get(name)
    if isinstance(panel, dict) and panel.get("state") == "ok" and isinstance(panel.get("data"), dict):
        return panel["data"]
    return None


def unread(snap):
    failed = ((snap.get("panels") or {}).get(COORD_PANEL) or {}).get("state") in ("timeout", "error")
    return [n for n in PANELS if data_of(snap, n) is None] + ([COORD_PANEL] if failed else [])


def cause(text):
    import mon_status
    return mon_status.short_name(text, WHY_CHARS)


def sprint_entries(data):
    gates, blocked = [], []
    for s in data.get("sprints") or []:
        if not isinstance(s, dict):
            continue
        for w in s.get("waiting") or []:
            if isinstance(w, dict) and w.get("gate"):
                gates.append({"kind": "gate", "text": f"{s.get('id')} gate {w['gate']}", "sprint": s.get("id"),
                              "item": w.get("item"), "gate": w["gate"]})
        counts = s.get("items") if isinstance(s.get("items"), dict) else {}
        left = sum(number(v) for k, v in counts.items() if k not in ("done", "dropped"))
        if s.get("state") == "active" and left and not s.get("next") and not number(counts.get("doing")):
            blocked.append({"kind": "blocked", "text": f"{s.get('id')} blocked: {left} item{'' if left == 1 else 's'} left, none ready",
                            "sprint": s.get("id"), "left": left})
    return gates + blocked


def ask_entries(data):
    out = []
    for a in data.get("asks") or []:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        since = str(a.get("since") or "")[:16].replace("T", " ")
        out.append({"kind": "ask", "text": f"ask {a['id']}" + (f" since {since}" if since else "")
                    + (f": {' '.join(str(a['text']).split())}" if a.get("text") else ""), "ask": a["id"]})
    return out


def delivery_entries(data):
    last = data.get("last_delivery")
    if not isinstance(last, dict) or last.get("outcome") != "refused":
        return []
    why = " ".join(str(last.get("why") or "").split())
    return [{"kind": "delivery", "text": "query-log delivery refused" + (f": {cause(why)}" if why else ""), "why": why}]


def orphan_entries(data):
    import mon_sessions
    if data.get("procs_unreadable"):
        return []
    found = sorted((p for p in data.get("procs") or [] if isinstance(p, dict) and p.get("class") == "orphan"),
                   key=lambda p: -number(p.get("age_s")))
    return [{"kind": "orphan", "text": f"orphan pid {p.get('pid')} ({mon_sessions.age_text(number(p.get('age_s')))}"
                                        + (f", in {p['checkout']}" if p.get("checkout") else "") + ")",
             "pid": p.get("pid")} for p in found]


def disk_entries(data):
    disk = data.get("disk") if isinstance(data.get("disk"), dict) else {}
    pct = disk.get("free_pct")
    if not isinstance(pct, (int, float)) or isinstance(pct, bool) or pct >= LOW_DISK_PCT:
        return []
    return [{"kind": "disk", "text": f"disk {pct:g}% free", "free_pct": pct}]


def fast_forward_entries(data):
    ff = data.get("fast_forward") if isinstance(data.get("fast_forward"), dict) else {}
    if ff.get("can") is not False or not data.get("behind"):
        return []
    why = " ".join(str(ff.get("why") or "").split())
    return [{"kind": "fast-forward", "text": "checkout cannot fast-forward to origin/main" + (f": {cause(why)}" if why else ""),
             "why": why}]


def entries(snap):
    """The list of what waits on the operator, from the `ok` panels of SNAP (see the module docstring)."""
    out = []
    for name, found in (("sprint", sprint_entries), (COORD_PANEL, ask_entries), ("querylog", delivery_entries), ("sessions", orphan_entries),
                        ("host", disk_entries), ("sprint", fast_forward_entries)):
        data = data_of(snap, name)
        if data is not None:
            out += found(data)
    return sorted(out, key=lambda e: KINDS.index(e["kind"]))  # stable: the panel's order within a kind


def line(snap):
    """The one `needs you` line of SNAP."""
    found = entries(snap)
    parts = []
    for kind in KINDS:
        of = [e["text"] for e in found if e["kind"] == kind]
        parts += of[:SHOWN] + ([f"+{len(of) - SHOWN} more {MANY[kind]}"] if len(of) > SHOWN else [])
    text = HEAD + ("; ".join(parts) or "nothing")
    missing = unread(snap)
    return text + (f"; not read: {', '.join(missing)}" if missing else "")
