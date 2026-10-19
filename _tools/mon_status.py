"""kbmon's status answer (kb/_self/monitoring.md): a short plain-words answer to one question about the monitored work, built
from one snapshot of the panels the topic needs (stdlib only).

  TOPICS                 sessions, cost, querylog, coord, sprints, load and all (the default)
  panels(topic)          the panels a topic reads, in `mon_base.PANELS` order
  answer(snap, topic, root=None)
                         {"schema": 1, "topic", "taken", "lines", "facts"} from a scrubbed snapshot (`mon_view.scrub`)
                         that holds those panels; `root` is the clone whose backlog gives an item its title

An answer is at most MAX_LINES lines, every one passed through `redact.redact` and cleared of absolute paths, and a claim's
holder is never read. A panel that is not `ok` gives one line that says so. It speaks results, an item by its title, and an
id only on a line where the operator acts. It calls no model and writes no file. Imports `mon_base`, `mon_sessions` (its
age text) and `mon_view`; `bl_base` where it reads titles.
"""
import re

import mon_base
import mon_sessions
import mon_view

SCHEMA = 1
TOPICS = ("sessions", "cost", "querylog", "coord", "sprints", "load", "all")
TOPIC_PANELS = {"sessions": ("sessions",), "cost": ("querylog",), "querylog": ("querylog",), "coord": ("coord",),
                "sprints": ("sprint",), "load": ("host", "sessions")}
ALL_ORDER = ("sessions", "cost", "querylog", "coord", "sprints", "load")  # the topics `all` answers, in this order
MAX_LINES = 25
ALL_LINES = 4  # lines each topic gives in `all`
ROWS = 6  # processes, claims, sprints or gates one topic names before it counts the rest
WHY_CHARS = 120
ABSOLUTE = re.compile(r"(?<![\w.:/])(?:~|\.\.)?/[^\s'\",;)]+|\b[A-Za-z]:\\[^\s'\",;)]*")


def panels(topic):
    names = {n for t in (ALL_ORDER if topic == "all" else (topic,)) for n in TOPIC_PANELS[t]}
    return tuple(n for n in mon_base.PANELS if n in names)


def titles(root):
    """{id: title} of the clone's backlog, or {} where it has none or cannot be read."""
    if root is None:
        return {}
    try:
        import bl_base
        bl_base.load_settings(root)
        return {i: str(v.get("title") or "") for i, v in bl_base.Backlog(root).items.items()}
    except Exception:  # noqa: BLE001 - a clone with no readable backlog names its items by id
        return {}


class Reader:
    """What a topic reads from the snapshot: a panel's data, or the line that says why it has none."""

    def __init__(self, snap, titles_of):
        self.panels = snap.get("panels") or {}
        self.titles = titles_of

    def data(self, name):
        panel = self.panels.get(name)
        if not isinstance(panel, dict):
            return None, f"the {name} panel is not in the snapshot"
        state = panel.get("state")
        if state != "ok" or not isinstance(panel.get("data"), dict):
            return None, f"the {name} panel is not readable ({state or 'no state'})"
        return panel["data"], ""

    def item(self, ident, act=False):
        """An item by its title; with `act`, or when the backlog has no title for it, with its id as well."""
        title = self.titles.get(ident)
        if not title:
            return str(ident)
        return f"{title} ({ident})" if act else title


def number(value, default=0):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def short(n):
    n = number(n)
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k" if n >= 1e3 else str(int(n))


def usd(value):
    return f"${number(value):.2f}"


def when(text):
    return str(text)[:16].replace("T", " ") if text else "-"


def more(count, noun):
    return [f"+{count} more {noun}"] if count > 0 else []


def sessions(r):
    data, why = r.data("sessions")
    if data is None:
        return [f"Sessions: {why}."], {"state": "unread"}
    procs = [p for p in data.get("procs") or [] if isinstance(p, dict)]
    orphans = sorted((p for p in procs if p.get("class") == "orphan"), key=lambda p: -number(p.get("age_s")))
    claude = [p for p in procs if p.get("session")]
    headless = [p for p in claude if p["session"] == "headless"]
    stalled = [s for s in data.get("stalled") or [] if isinstance(s, dict)]
    facts = {"processes": len(procs), "orphans": len(orphans), "headless": len(headless),
             "interactive": len(claude) - len(headless), "stalled": len(stalled)}
    if orphans:
        lines = [f"Sessions: {len(orphans)} orphan process{'' if len(orphans) == 1 else 'es'} left running, nothing waits for them:"]
    else:
        lines = [f"Sessions: no orphan; {len(headless)} headless and {len(claude) - len(headless)} interactive Claude "
                 f"session{'' if len(claude) == 1 else 's'}, {len(procs)} process{'' if len(procs) == 1 else 'es'} in the clone."]
    lines += [f"  orphan pid {p.get('pid')}, running {mon_sessions.age_text(number(p.get('age_s')))}, in {p.get('checkout') or '?'}"
              for p in orphans[:ROWS]] + [("  " + x) for x in more(len(orphans) - ROWS, "orphans")]
    if stalled:
        lines.append(f"  {len(stalled)} stalled item{'' if len(stalled) == 1 else 's'}:")
        lines += [f"  {r.item(s.get('item'), True)}: {', '.join(str(x) for x in s.get('signals') or []) or 'no signal named'}"
                  for s in stalled[:ROWS]] + [("  " + x) for x in more(len(stalled) - ROWS, "stalled items")]
    else:
        lines.append("  no stalled item.")
    if orphans or stalled:
        lines.append("  Why: python3 _tools/kbask.py summary \"why is it stuck\" (a read-only session answers).")
    if headless:
        lines.append("  Workers running: " + "; ".join(r.item(p.get("item")) for p in headless[:ROWS]) + ".")
    return lines, facts


def cost(r):
    data, why = r.data("querylog")
    if data is None:
        return [f"Cost: {why}."], {"state": "unread"}
    u = data.get("usage_today") if isinstance(data.get("usage_today"), dict) else {}
    unpriced = [str(m) for m in u.get("unpriced") or []]
    facts = {"usd": number(u.get("usd"), 0.0), "rows": number(u.get("rows")), "tokens": number(u.get("tokens")),
             "unpriced": unpriced}
    lines = [f"Cost today: ${number(u.get('usd'), 0.0):.2f} over {number(u.get('rows'))} usage rows, "
             f"{short(u.get('tokens'))} tokens."]
    if unpriced:
        lines.append(f"No price for {', '.join(unpriced)}: {'its' if len(unpriced) == 1 else 'their'} cost is not in the dollars.")
    return lines, facts


def querylog(r):
    data, why = r.data("querylog")
    if data is None:
        return [f"Query log: {why}."], {"state": "unread"}
    last = data.get("last_delivery") if isinstance(data.get("last_delivery"), dict) else None
    waiting = number(data.get("undelivered"))
    facts = {"outcome": last.get("outcome") if last else None, "undelivered": waiting,
             "undelivered_runs": number(data.get("undelivered_runs")), "mode": data.get("mode")}
    if last:
        text = f"Query log: the last delivery was {last.get('outcome')} ({when(last.get('when'))})"
        reason = " ".join(str(last.get("why") or "").split())[:WHY_CHARS]
        lines = [text + (f": {reason}" if last.get("outcome") == "refused" and reason else ".")]
    else:
        lines = ["Query log: no delivery outcome in the log yet."]
    since = f", the oldest from {when(data.get('undelivered_since'))}" if waiting and data.get("undelivered_since") else ""
    runs = number(data.get("undelivered_runs"))
    lines.append(f"  {waiting} entr{'y' if waiting == 1 else 'ies'} undelivered"
                 + (f" in {runs} run{'' if runs == 1 else 's'}" if waiting else "") + since + ".")
    spool = data.get("spool") if isinstance(data.get("spool"), dict) else {}
    lines.append(f"  {number(spool.get('rows'))} rows wait in the spool; mode {data.get('mode', '?')}"
                 + ("; DISABLED." if data.get("disabled") else "."))
    return lines, facts


def coord(r):
    data, why = r.data("coord")
    if data is None:
        return [f"Coord: {why}."], {"state": "unread"}
    claims = [c for c in data.get("claims") or [] if isinstance(c, dict)]
    over = [c for c in claims if c.get("over_budget")]
    facts = {"claims": len(claims), "over_budget": len(over), "keys": [str(c.get("key")) for c in claims]}
    if not claims:
        return ["Coord: no live claim."], facts
    lines = [f"Coord: {len(claims)} live claim{'' if len(claims) == 1 else 's'}" + (f", {len(over)} over budget:" if over else ":")]
    lines += [f"  {c.get('key')}: {mon_sessions.age_text(number(c.get('left_s')))} left, "
              + ("no budget" if c.get("budget_usd") is None else f"budget {usd(c.get('budget_usd'))}")
              + (f", spent {usd(c.get('spend_usd'))}" if c.get("spend_usd") is not None else "")
              + (" (over budget)" if c.get("over_budget") else "") for c in claims[:ROWS]]
    return lines + ["  " + x for x in more(len(claims) - ROWS, "claims")], facts


def sprints(r):
    data, why = r.data("sprint")
    if data is None:
        return [f"Sprints: {why}."], {"state": "unread"}
    rows = [s for s in data.get("sprints") or [] if isinstance(s, dict)]
    landing = [x for x in data.get("landings") or [] if isinstance(x, dict)]
    facts = {"sprints": len(rows), "landings": len(landing), "progress": {}}
    if not rows:
        return ["Sprints: none active or planned."] + [f"  landing {r.item(x.get('item'))}, at step {x.get('step')}" for x in landing[:ROWS]], facts
    lines = [f"Sprints: {len(rows)} active or planned:"]
    for s in rows[:ROWS]:
        counts = s.get("items") if isinstance(s.get("items"), dict) else {}
        total = sum(number(v) for v in counts.values())
        done = number(counts.get("done")) + number(counts.get("dropped"))
        facts["progress"][s.get("id")] = {"state": s.get("state"), "done": done, "total": total}
        if s.get("state") == "active":
            pct = round(done * 100 / total) if total else 0
            text = f"{done} of {total} done ({pct}%)" + (f", {number(counts.get('doing'))} in progress" if counts.get("doing") else "")
            if s.get("next"):
                text += f"; next: {r.item(s['next'])}"
        else:
            text = "approved, not started yet" if s.get("state") == "approved" else "waits for its start gate"
        lines.append(f"  {r.item(s.get('id'))}: {text}")
        waiting = [w for w in s.get("waiting") or [] if isinstance(w, dict) and not (w.get("item") == s.get("id") and w.get("gate") == "start")]
        lines += [f"    your answer is needed: gate {w.get('gate')} of {r.item(w.get('item'), True)}" for w in waiting[:2]]
        lines += ["    " + x for x in more(len(waiting) - 2, "gates waiting")]
    lines += ["  " + x for x in more(len(rows) - ROWS, "sprints")]
    lines += [f"  landing {r.item(x.get('item'))}, at step {x.get('step')}" for x in landing[:ROWS]]
    return lines, facts


def holder_text(label, rec):
    if not isinstance(rec, dict):
        return f"{label} lock free"
    return f"{label} lock held by pid {rec.get('pid')} ({rec.get('clone')} clone, since {when(rec.get('started'))})"


def load(r):
    data, why = r.data("host")
    if data is None:
        return [f"Load: {why}."], {"state": "unread"}
    ld, cores = data.get("load"), number(data.get("cores"), 0)
    if not isinstance(ld, list) or len(ld) < 3:
        lines, facts = ["Load: this host gives no load average."], {"load": None}
    else:
        ratio = round(number(ld[0]) / cores, 2) if cores else None
        word = "" if ratio is None else " (calm)" if ratio < 0.7 else " (busy)" if ratio < 1.0 else " (overloaded)"
        facts = {"load1": ld[0], "load5": ld[1], "load15": ld[2], "cores": cores, "per_core": ratio}
        lines = [f"Load: {ld[0]:.2f} / {ld[1]:.2f} / {ld[2]:.2f} over 1, 5 and 15 minutes on {cores or '?'} cores{word}."]
    lines.append("  " + holder_text("suite", data.get("suite_lock")) + "; " + holder_text("main", data.get("main_lock")) + ".")
    s, _ = r.data("sessions")
    if s is not None:
        procs = [p for p in s.get("procs") or [] if isinstance(p, dict)]
        n = sum(1 for p in procs if p.get("class") == "orphan")
        facts.update(processes=len(procs), orphans=n)
        lines.append(f"  {len(procs)} process{'' if len(procs) == 1 else 'es'} work in the clone, {n} of them orphan.")
    disk = data.get("disk") if isinstance(data.get("disk"), dict) else {}
    if "free_pct" in disk:
        facts["disk_free_pct"] = disk["free_pct"]
        lines.append(f"  Disk {number(disk['free_pct']):g}% free.")
    return lines, facts


ANSWERS = {"sessions": sessions, "cost": cost, "querylog": querylog, "coord": coord, "sprints": sprints, "load": load}


def trimmed(lines, n, topic):
    """LINES cut to N, the last of them a pointer to the topic's own answer when anything was dropped."""
    if len(lines) <= n:
        return lines
    return lines[:n - 1] + [f"  +{len(lines) - n + 1} more: python3 _tools/kbmon.py --status {topic}"]


def clean(lines, facts):
    """LINES and FACTS with each string redacted and every absolute path replaced by `<path>`; at most MAX_LINES lines."""
    cut = mon_view.scrub({"lines": [ABSOLUTE.sub("<path>", x) for x in lines], "facts": facts})
    lines, facts = cut["lines"], cut["facts"]
    lines = [ABSOLUTE.sub("<path>", mon_view.plain(x)) for x in lines]  # redaction may have joined a path from parts
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [f"+{len(lines) - MAX_LINES + 1} more lines"]
    return lines, facts


def answer(snap, topic, root=None):
    if topic not in TOPICS:
        raise ValueError(f"no status topic {topic}: {', '.join(TOPICS)}")
    reader = Reader(snap, titles(root))
    lines, facts = [], {}
    for t in (ALL_ORDER if topic == "all" else (topic,)):
        got, found = ANSWERS[t](reader)
        lines += trimmed(got, ALL_LINES, t) if topic == "all" else got
        facts[t] = found
    if topic != "all":
        facts = facts[topic]
    lines, facts = clean(lines, facts)
    return {"schema": SCHEMA, "topic": topic, "taken": snap.get("taken"), "lines": lines, "facts": facts}
