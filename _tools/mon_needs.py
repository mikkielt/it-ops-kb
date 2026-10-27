"""kbmon's list of what waits on the operator (kb/_self/monitoring.md), built from one snapshot: the text view prints it as the
`needs you` line under its header and `kbmon.py --status all` starts with the same line. Standard library only; imports
nothing at load, `mon_sessions` (its age text) and `mon_status` (`short_name`) where they are used.

  entries(snap)   [{kind, text, ...}] in this order: `gate` (each open blocking gate of an active, approved or planned sprint
                  or of one of its open items, `SP-… gate NAME`), `run` (each open item whose coord run state is `blocked`, with
                  the ids of its gates, `failed` or `refused`, with the step that stopped it, from the sprint panel's `runs`:
                  `ST-… blocked on gates g1, g2, 5m`, `ST-… run failed at step X, 5m`, `ST-… landing refused at step rebase,
                  5m`; a gate it names is left out of the `gate` entries), `ask` (each ask addressed to `operator` that no closing
                  answer has ended, from the coord panel: `ask ID since DATE TIME: the first words of the question`, redacted;
                  an Alertmanager alert, a cleanup verdict or a session's question posted as an ask shows here), `prompt` (each
                  session of the sessions panel that carries `blocked`, the coord hook's record of a permission request or a
                  question that waits on the person, longest first: `s-… worker ST-… blocked on a permission prompt, 2m`; a
                  session that is only silent has none), `overlap` (each
                  overlap of two live sessions in the sessions panel that no coordinate event decided and that is
                  `announce.needs_you_after_min` minutes old, `overlap ST-… (s-…) with ST-… (s-…), undecided for 12m`),
                  `finished` (each item of the sessions panel's `stalled` list with the `finished-alive` signal: its worker's work is
                  recorded as done and the worker's process still runs past the grace period, `ST-… finished, its worker still runs`),
                  `stalled-claim` (each claimed item whose session in the sessions panel (`item` set, so it holds a claim) or whose
                  working run in the coord panel has been silent for over STALLED_CLAIM_S, the limit of the `KbmonRunStalled` rule,
                  once per item, longest first: `ST-… claim silent 1h05m`; a session with no item, idle or not, has none),
                  `blocked` (an active sprint with items left, none ready and
                  none in progress), `delivery` (the query log's last delivery was refused, with the gate that failed),
                  `orphan` (each process of class `orphan`, oldest first), `disk` (under LOW_DISK_PCT percent free, from the byte counts as the host alert reads them; none for a total of 0 bytes) and
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
KINDS = ("gate", "run", "ask", "prompt", "overlap", "finished", "stalled-claim", "blocked", "delivery", "orphan", "disk", "fast-forward")
MANY = {"gate": "gates", "run": "runs", "ask": "asks", "prompt": "prompts", "overlap": "overlaps", "finished": "finished workers", "stalled-claim": "stalled claims", "blocked": "blocked sprints", "delivery": "deliveries", "orphan": "orphans", "disk": "disk",
        "fast-forward": "fast-forward"}  # the noun after `+N more`
STALLED_CLAIM_S = 3600  # seconds of silence from which a claim's session or run is stalled (monitoring.md, `KbmonRunStalled`)
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


STOPPED = {"blocked": "blocked", "failed": "run failed", "refused": "landing refused"}  # the run states the line names


def run_entries(data):
    """The `run` entries of the sprint panel's DATA: an open item whose run state is blocked, failed or refused."""
    import mon_sessions
    out = []
    for r in data.get("runs") or []:
        if not isinstance(r, dict) or r.get("state") not in STOPPED or not r.get("item"):
            continue
        gates = [str(g) for g in r.get("gates") or []] if r["state"] == "blocked" else []
        at = f" at step {cause(str(r['step']))}" if r["state"] != "blocked" and r.get("step") else ""
        age = f", {mon_sessions.age_text(number(r['age_s']))}" if isinstance(r.get("age_s"), int) else ""
        out.append({"kind": "run", "text": f"{r['item']} {STOPPED[r['state']]}" + (f" on gate{'' if len(gates) == 1 else 's'} {', '.join(gates)}" if gates else "")
                    + at + age, "item": r["item"], "state": r["state"], "gates": gates, "step": r.get("step")})
    return out


def sprint_entries(data):
    gates, blocked = [], []
    named = {(e["item"], g) for e in run_entries(data) for g in e["gates"]}  # a gate a blocked run names shows once
    for s in data.get("sprints") or []:
        if not isinstance(s, dict):
            continue
        for w in s.get("waiting") or []:
            if isinstance(w, dict) and w.get("gate") and (w.get("item"), w["gate"]) not in named:
                gates.append({"kind": "gate", "text": f"{s.get('id')} gate {w['gate']}", "sprint": s.get("id"),
                              "item": w.get("item"), "gate": w["gate"]})
        counts = s.get("items") if isinstance(s.get("items"), dict) else {}
        left = sum(number(v) for k, v in counts.items() if k not in ("done", "dropped"))
        if s.get("state") == "active" and left and not s.get("next") and not number(counts.get("doing")):
            blocked.append({"kind": "blocked", "text": f"{s.get('id')} blocked: {left} item{'' if left == 1 else 's'} left, none ready",
                            "sprint": s.get("id"), "left": left})
    return gates + run_entries(data) + blocked


def ask_entries(data):
    out = []
    for a in data.get("asks") or []:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        since = str(a.get("since") or "")[:16].replace("T", " ")
        out.append({"kind": "ask", "text": f"ask {a['id']}" + (f" since {since}" if since else "")
                    + (f": {' '.join(str(a['text']).split())}" if a.get("text") else ""), "ask": a["id"]})
    return out


WAITS_ON = {"permission": "a permission prompt", "question": "a question"}  # what a blocked session's `on` says in the line


def prompt_entries(data):
    import mon_sessions
    found = [s for s in data.get("sessions") or [] if isinstance(s, dict) and isinstance(s.get("blocked"), dict)]
    out = []
    for s in sorted(found, key=lambda s: -number(s["blocked"].get("age_s"))):
        b = s["blocked"]
        name = " ".join(str(w) for w in (s.get("label") or "-", s.get("role"), s.get("item")) if w)
        out.append({"kind": "prompt", "text": f"{name} blocked on {WAITS_ON.get(b.get('on'), 'the person')}"
                    + (f", {mon_sessions.age_text(number(b['age_s']))}" if isinstance(b.get("age_s"), int) else ""),
                    "session": s.get("label"), "item": s.get("item"), "on": b.get("on")})
    return out


def overlap_entries(data):
    import mon_sessions
    after = number(data.get("needs_you_after_min"), 10) * 60
    out = []
    for o in data.get("overlaps") or []:
        if not isinstance(o, dict) or o.get("strategy") != mon_sessions.UNDECIDED or number(o.get("age_s")) < after:
            continue
        a, b = (o.get(x) if isinstance(o.get(x), dict) else {} for x in ("a", "b"))
        name = [f"{s.get('item') or '-'} ({s.get('session') or '-'})" for s in (a, b)]
        out.append({"kind": "overlap", "text": f"overlap {name[0]} with {name[1]}, undecided for "
                    + mon_sessions.age_text(number(o.get("age_s"))), "a": a, "b": b})
    return out


def finished_entries(data):
    """The `finished` entries of the sessions panel's DATA: a stalled item whose worker is finished and still runs."""
    return [{"kind": "finished", "text": f"{r['item']} finished, its worker still runs", "item": r["item"]}
            for r in data.get("stalled") or []
            if isinstance(r, dict) and r.get("item") and "finished-alive" in (r.get("signals") or [])]


def stalled_claim_entries(sessions, coord):
    """The `stalled-claim` entries from the sessions panel's data SESSIONS and the coord panel's data COORD (None when it is
    not read): an item named by a session with `silent_s` over STALLED_CLAIM_S, else by a working run with `silent_s` over it."""
    import mon_sessions
    silent = {}
    for s in (sessions or {}).get("sessions") or []:
        if isinstance(s, dict) and s.get("item") and number(s.get("silent_s")) > STALLED_CLAIM_S:
            silent[s["item"]] = max(silent.get(s["item"], 0), number(s["silent_s"]))
    for r in (coord or {}).get("runs") or []:
        if isinstance(r, dict) and r.get("item") and r.get("state") == "working" and number(r.get("silent_s")) > STALLED_CLAIM_S:
            silent[r["item"]] = max(silent.get(r["item"], 0), number(r["silent_s"]))
    return [{"kind": "stalled-claim", "text": f"{item} claim silent {mon_sessions.age_text(secs)}", "item": item, "silent_s": int(secs)}
            for item, secs in sorted(silent.items(), key=lambda kv: (-kv[1], kv[0]))]


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
    free, total = disk.get("free_bytes"), disk.get("total_bytes")
    if all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in (free, total)):
        if total <= 0:
            return []
        pct = free * 100 / total
    else:
        pct = disk.get("free_pct")
    if not isinstance(pct, (int, float)) or isinstance(pct, bool) or pct >= LOW_DISK_PCT:
        return []
    pct = round(pct, 2)
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
    for name, found in (("sprint", sprint_entries), (COORD_PANEL, ask_entries), ("sessions", prompt_entries), ("sessions", overlap_entries), ("sessions", finished_entries), ("querylog", delivery_entries),
                        ("sessions", orphan_entries),
                        ("host", disk_entries), ("sprint", fast_forward_entries)):
        data = data_of(snap, name)
        if data is not None:
            out += found(data)
    if data_of(snap, "sessions") is not None:
        out += stalled_claim_entries(data_of(snap, "sessions"), data_of(snap, COORD_PANEL))
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
