"""kbmon's status answer (kb/_self/monitoring.md): a short plain-words answer to one question about the monitored work, built
from one snapshot of the panels the topic needs (stdlib only).

  TOPICS                 sessions, cost, querylog, coord, sprints, load and all (the default)
  panels(topic)          the panels a topic reads, in `mon_base.PANELS` order
  answer(snap, topic, root=None)
                         {"schema": 1, "topic", "taken", "lines", "facts"} from a scrubbed snapshot (`mon_view.scrub`)
                         that holds those panels; `root` is the clone whose backlog gives an item its title
  topic_of(question)     the topic a plain question about the monitored work asks, by fixed cue words (CUES), `all` where it
                         asks for several, or None: a question about the docs (how sessions resume, what a licence costs) is
                         no status question
  run(topic, timeout)    (text, None) of `kbmon.py --status TOPIC` run as a subprocess, or (None, what failed)

An answer is at most MAX_LINES lines, every one passed through `redact.redact` and cleared of absolute paths, and a claim's
holder is never read. A panel that is not `ok` gives one line that says so. It speaks results, an item by its title, and an
id only on a line where the operator acts. The sprints answer rests on the sprint panel's data (items read from `origin/main`,
the commits the checkout is behind it, the duration history) and the host panel's load, so a saved
snapshot gives the same answer; its ETA is a range from `mon_eta.estimate` taken at the snapshot's time. The
load answer also gives the host panel's CPU groups with a fixed cause and remedy each (GROUP_TEXT), as lines and as a
top-level `groups` list. It calls no model and writes no file (`run` starts `kbmon.py`, which writes none). Imports `mon_base`, `mon_eta`, `mon_sessions` (its
age text) and `mon_view`; `bl_base` where it reads titles.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import mon_base
import mon_eta
import mon_sessions
import mon_view

SCHEMA = 1
TOPICS = ("sessions", "cost", "querylog", "coord", "sprints", "load", "all")
TOPIC_PANELS = {"sessions": ("sessions",), "cost": ("querylog",), "querylog": ("querylog",), "coord": ("coord",),
                "sprints": ("sprint", "host"), "load": ("host", "sessions")}
ALL_ORDER = ("sessions", "cost", "querylog", "coord", "sprints", "load")  # the topics `all` answers, in this order
MAX_LINES = 25
ALL_LINES = 4  # lines each topic gives in `all`
ROWS = 6  # processes, claims, sprints or gates one topic names before it counts the rest
WHY_CHARS = 120
GROUP_TEXT = {  # kind: (cause, remedy), fixed words
    "kbmon": ("the monitor reads every panel on each refresh",
              "a longer refresh interval, fewer live views, or this status answer in place of a view"),
    "fseventsd": ("the system reports file changes in the clone and its worktrees",
                  "fewer parallel workers and pruned worktrees"),
    "kb-tools": ("kb scripts are running, such as a long pack, an index build or a check",
                 "wait for it, or look for a stalled item in the sessions answer"),
    "claude": ("Claude Code sessions are working", "fewer parallel sessions"),
    "tests": ("the test suite is running", "one whole-suite run at a time, which the host lock keeps"),
    "other": ("processes outside the kb", "nothing the kb can change; find the biggest in the system's activity monitor"),
}
BASIS = {"recent": "ps's decaying recent average of each process (macOS)",
         "lifetime": "ps's CPU time over each process's whole life"}
RUN_TIMEOUT = 60  # seconds `run` waits for kbmon.py
KBMON = Path(__file__).resolve().parent / "kbmon.py"
# topic_of: a topic is asked when every group of one of its cues has a match in the question's lower-cased words or text.
# A cue pairs a word that names the monitored thing with a word that asks for its state, so a docs question that holds
# one of them (how sessions resume, what a licence costs, a ConfigMgr deployment's status) matches none.
HOST = r"\b(?:my|this|the) (?:computer|machine|laptop|mac|pc|host)\b"
CUES = {
    "sprints": [(r"\bsprints?\b", r"\b(?:status|progress|percent\w*|done|finished|left|remaining|eta|how far)\b")],
    "load": [(HOST, r"\b(?:load|cpu|slow|busy|overloaded|hot|fan|lag\w*|freez\w*)\b")],
    "sessions": [(r"\b(?:sessions?|workers?|agents?)\b", r"\b(?:running|active|stuck|stalled|orphan\w*|hung|left running)\b"),
                 (r"\b(?:anything|something|any)\b", r"\b(?:stuck|orphan\w*|stalled|hung)\b")],
    "cost": [(r"\b(?:cost|costs|spent|spend|spending)\b", r"\b(?:today|so far|this session|right now|tokens?|usage)\b")],
    "querylog": [(r"\bquery log\b", r"\b(?:deliver\w*|undelivered|spool\w*|pushed|stuck)\b")],
    "coord": [(r"\bcoord\b", r"\b(?:claims?|budget|live|active|left|status)\b")],
    "all": [(r"\bkbmon\b", r"")],
}
ABSOLUTE = re.compile(r"(?<![\w.:/])(?:~|\.\.)?/[^\s'\",;)]+|\b[A-Za-z]:\\[^\s'\",;)]*")


def topic_of(question):
    """The status topic a plain question asks, by the fixed cues of CUES: the one topic that matches, `all` when several do
    (or only `kbmon` is named), None when none does."""
    text = " ".join(str(question or "").lower().split())
    found = [topic for topic, groups in CUES.items() for named, state in groups
             if re.search(named, text) and re.search(state, text)]
    found = list(dict.fromkeys(found))
    return found[0] if len(found) == 1 else "all" if found else None


def run(topic, timeout=RUN_TIMEOUT):
    """(the lines `kbmon.py --status TOPIC` printed, None), or (None, what failed): a command that cannot start, runs past
    TIMEOUT seconds or exits non-zero."""
    shown = f"kbmon.py --status {topic}"
    try:
        p = subprocess.run([sys.executable, str(KBMON), "--status", topic], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, cwd=str(KBMON.parent.parent), env=dict(os.environ, PYTHONUTF8="1"))
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"`{shown}` could not run: {type(e).__name__}"
    if p.returncode != 0:
        last = ((p.stderr or p.stdout).strip().splitlines() or ["no output"])[-1]
        return None, f"`{shown}` exited {p.returncode}: {last}"
    return p.stdout.rstrip(), None


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
        self.now = mon_eta.seconds_of(snap.get("taken"))  # the time estimates are taken at
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

    def learn(self, rows):
        """Titles the panel carries ({id, title} rows) for the items the clone's backlog does not hold (a stale checkout)."""
        for x in rows:
            if isinstance(x, dict) and x.get("id") and x.get("title"):
                self.titles.setdefault(x["id"], str(x["title"]))


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


def minutes(n):
    """N minutes as `45 min`, `3.5 h` or `2.0 days`."""
    return f"{n:.0f} min" if n < 180 else f"{n / 60:.1f} h" if n < 2880 else f"{n / 1440:.1f} days"


def minutes_range(low, high):
    """LOW to HIGH minutes as `33-69 min`, or in hours as `3.5-5.0 h` from 180 minutes (by the high end)."""
    return f"{low:.0f}-{high:.0f} min" if high < 180 else f"{low / 60:.1f}-{high / 60:.1f} h"


def sprint_lines(r, s, facts, hist):
    """The lines of one sprint and its entry of the answer's facts; HIST is the sprint panel's duration history."""
    counts = s.get("items") if isinstance(s.get("items"), dict) else {}
    total = sum(number(v) for v in counts.values())
    done = number(counts.get("done")) + number(counts.get("dropped"))
    name = s.get("title") or r.item(s.get("id"))
    entry = facts["progress"][s.get("id")] = {"state": s.get("state"), "done": done, "total": total}
    if s.get("state") != "active":
        return [f"  {name}: " + ("approved, not started yet" if s.get("state") == "approved" else "waits for its start gate")]
    pct = round(done * 100 / total) if total else 0
    entry["percent"] = pct
    text = f"{done}/{total} done ({pct}%), {number(counts.get('doing'))} in progress, {number(counts.get('todo'))} to do"
    if s.get("next"):
        text += f"; next: {s.get('next_title') or r.item(s['next'])}"
    lines = [f"  {name}: {text}"]
    left = [x for x in s.get("open") or [] if isinstance(x, dict)]
    if left:
        names = [str(x.get("title") or x.get("id")) + (" (in progress)" if x.get("status") == "doing" else "") for x in left[:ROWS]]
        rest = total - done - len(names)
        lines.append("    left: " + "; ".join(names) + (f"; +{rest} more" if rest > 0 else ""))
    got = mon_eta.estimate(s, hist, r.now)
    entry.update(open=total - done, eta_low_min=None if got is None else got["low_min"],
                 eta_high_min=None if got is None else got["high_min"],
                 confidence=None if got is None else got["confidence"], basis=None if got is None else got["basis"])
    if got is None:
        lines.append("    No ETA yet: no durations of finished items on origin/main to estimate from.")
    else:
        lines.append(f"    ETA about {minutes_range(got['low_min'], got['high_min'])}, {got['confidence']} confidence; "
                     f"basis: {got['basis']}.")
    return lines


def sprints(r):
    data, why = r.data("sprint")
    if data is None:
        return [f"Sprints: {why}."], {"state": "unread"}
    rows = [s for s in data.get("sprints") or [] if isinstance(s, dict)]
    landing = [x for x in data.get("landings") or [] if isinstance(x, dict)]
    for s in rows:
        r.learn([{"id": s.get("id"), "title": s.get("title")}, *(s.get("open") or [])])
    behind = data.get("behind") if isinstance(data.get("behind"), int) and not isinstance(data.get("behind"), bool) else None
    source = data.get("source") or "?"
    facts = {"sprints": len(rows), "landings": len(landing), "progress": {}, "source": source, "behind": behind}
    where = (f"read from {source}" + ("" if behind is None else f"; this checkout is {behind} commit{'' if behind == 1 else 's'} behind it")
             if source == "origin/main" else "read from this checkout's files, origin/main was not readable")
    head = f"Sprints: {len(rows)} active or planned, {where}:" if rows else f"Sprints: none active or planned, {where}."
    lines = [head]
    for s in rows[:ROWS]:
        lines += sprint_lines(r, s, facts, data.get("history") if isinstance(data.get("history"), dict) else {})
        waiting = [w for w in s.get("waiting") or [] if isinstance(w, dict) and not (w.get("item") == s.get("id") and w.get("gate") == "start")]
        lines += [f"    your answer is needed: gate {w.get('gate')} of {r.item(w.get('item'), True)}" for w in waiting[:2]]
        lines += ["    " + x for x in more(len(waiting) - 2, "gates waiting")]
    lines += ["  " + x for x in more(len(rows) - ROWS, "sprints")]
    lines += [f"  landing {r.item(x.get('item'))}, at step {x.get('step')}" for x in landing[:ROWS]]
    host, hwhy = r.data("host")
    ld, cores = (host.get("load"), number(host.get("cores"), 0)) if host else (None, 0)
    if isinstance(ld, list) and len(ld) >= 3:
        facts["host_load1"] = ld[0]
        lines.append(f"  host load {ld[0]:.2f} / {ld[1]:.2f} / {ld[2]:.2f} over 1, 5 and 15 minutes on {cores or '?'} cores{load_word(ld[0], cores)}.")
    else:
        lines.append("  host load: " + (hwhy or "this host gives no load average") + ".")
    return lines, facts


def load_word(load1, cores):
    """` (calm)`, ` (busy)` or ` (overloaded)` for a one-minute load on CORES; "" where the cores are not known."""
    ratio = number(load1) / cores if cores else None
    return "" if ratio is None else " (calm)" if round(ratio, 2) < 0.7 else " (busy)" if round(ratio, 2) < 1.0 else " (overloaded)"


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
        word = load_word(ld[0], cores)
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
    lines += consumer_lines(data, facts)
    return lines, facts


def consumer_lines(data, facts):
    """The lines of the CPU groups (those using CPU, ROWS at most, each with its cause and remedy), and `facts["groups"]`
    with all of them as {kind, clone, cpu, procs, cause, remedy}."""
    found = data.get("groups")
    if not isinstance(found, list):
        facts["groups"] = []
        return ["  CPU by kind: not available on this host (no ps)."]
    made = [g for g in found if isinstance(g, dict) and g.get("kind") in GROUP_TEXT]
    facts["groups"] = [{"kind": g["kind"], "clone": g.get("clone"), "cpu": number(g.get("cpu"), 0.0), "procs": number(g.get("procs")),
                        "cause": GROUP_TEXT[g["kind"]][0], "remedy": GROUP_TEXT[g["kind"]][1]} for g in made]
    using = [g for g in facts["groups"] if g["cpu"] > 0]
    basis = BASIS.get(data.get("cpu_basis"), "as ps gives it")
    if not using:
        return [f"  No process group uses CPU ({basis})."]
    lines = [f"  CPU by kind, the percent being {basis}:"]
    for g in using[:ROWS]:
        what = g["kind"] + (f" ({g['clone']} clone)" if g["clone"] else "")
        lines.append(f"  {what} {g['cpu']:g}%, {int(g['procs'])} process{'' if g['procs'] == 1 else 'es'}: {g['cause']}. Remedy: {g['remedy']}.")
    return lines + ["  " + x for x in more(len(using) - ROWS, "groups")]


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
    groups = facts.pop("groups", []) if topic == "load" else []
    lines, facts = clean(lines, facts)
    found = {"schema": SCHEMA, "topic": topic, "taken": snap.get("taken"), "lines": lines, "facts": facts}
    if topic == "load":
        found["groups"] = mon_view.scrub({"groups": groups})["groups"]
    return found
