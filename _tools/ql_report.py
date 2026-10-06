"""The query log's reporting (kb/_self/querylog.md, Reporting): the weekly digest of the committed store, shown once
per ISO week by a SessionStart hook, `status` (open source findings, open conflict merge requests, reverted
automatic commits) and `show` (one run, entry, usage sidecar, the findings under a filter, or the local spool). Only
the store and the week go into the digest, so every clone at one commit prints the same lines.
"""
import datetime, json, math, re, sys, time
from pathlib import Path

from ql_base import HOME, STORE, logging_off, places, run_cmd, write_text
from ql_deliver import BRANCH, CONFLICT_BRANCH_PREFIX, REMOTE, auto_log, forge_list, origin_forge
from ql_learn import FAILED, host_fetches, is_miss
from ql_store import (DAY, ENTRY_KEYS, FETCH_KEYS, FINDING_KINDS, FINDING_STATES, JUDGED, ROW_SURFACES, RULES_ROOT,
                      RUN_ID, SURFACES, finding_id, finding_states, findings_files, load_run, records, resolve_id, run_files,
                      run_ids, store_entries, usage_files, usage_records, work_files, work_line_problems, ops_files,
                      ops_line_problems)
from ql_capture import VERDICTS

DIGEST_MARKER = "digest-week"  # beside the spool: the ISO week in which the SessionStart digest was last shown
DIGEST_BUDGET_S = 3  # the SessionStart digest prints nothing when reading the store took longer
DIGEST_HOOK_TIMEOUT_S = 10  # the digest hook's `timeout` in .claude/settings.json and the plugin
BACKLOG = HOME / "kb" / "_self" / "backlog"  # the item files, which `intake --file` writes drafts into
DETECTOR_LINK = "detector "  # the last link of an item intake files (bl_intake.DETECTOR_LINK; no import of it here)
WEEK = re.compile(r"(\d{4})-W(\d{2})")
WORK_TOP = 5  # the items the digest's work lines list, most tokens first
MISS_KINDS = ("eval", "gap")  # one finding per judged miss: an eval finding with a best article, else a gap finding


def iso_week(day):
    """`YYYY-Www`, the ISO week of a date."""
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def week_days(week):
    """(Monday, Sunday) of the ISO week `YYYY-Www`; ValueError for anything else."""
    m = WEEK.fullmatch(str(week or ""))
    if not m:
        raise ValueError(f"not an ISO week (YYYY-Www): {week!r}")
    monday = datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    return monday, monday + datetime.timedelta(days=6)


def run_day(run_id):
    """The UTC date of a run id, or None when it is not one."""
    m = RUN_ID.fullmatch(str(run_id))
    return datetime.date(int(run_id[:4]), int(run_id[4:6]), int(run_id[6:8])) if m else None


def latest_week(store):
    """The ISO week of the newest entry's day in the store, else of its newest run or findings file; None when the
    store holds neither."""
    days = [e["day"] for _, e in store_entries(store) if isinstance(e.get("day"), str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["day"])]
    if days:
        return iso_week(datetime.date.fromisoformat(max(days)))
    runs = [d for d in (run_day(p.stem) for p in run_files(store) + findings_files(store)) if d]
    return iso_week(max(runs)) if runs else None


def _counts(pairs):
    return ", ".join(f"{k} {n}" for k, n in pairs)


def rank(values, p):
    """The nearest-rank `p` quantile of a list of numbers, `-` when it is empty."""
    v = sorted(values)
    return v[max(0, math.ceil(p * len(v)) - 1)] if v else "-"


def usage_lines(entries, usage):
    """The digest's usage lines for the week's entries and the store's usage sidecar lines ({entry id: line})."""
    have = [usage[e["id"]] for e in entries if e.get("id") in usage]
    if not have:
        return [f"usage: 0 of {len(entries)} lookups"]

    def models(u):
        yield from (u.get("main") or {}).values()
        for group in (u.get("sub") or {}).values():
            yield from group.values()

    def inp(c):
        return c["in"] + c["cw"] + c["cr"]

    per_in = [sum(inp(c) for c in models(u)) for u in have]
    per_out = [sum(c["out"] for c in models(u)) for u in have]
    total = sum(per_in)
    cread = sum(c["cr"] for u in have for c in models(u))
    sub = sum(inp(c) for u in have for g in (u.get("sub") or {}).values() for c in g.values())
    kb = [s for u in have for s in u.get("steps") or []
          if s.get("tools") and all(str(t.get("tool", "")).startswith("kb_") for t in s["tools"])]
    grow = [s["grow"] for s in kb if isinstance(s.get("grow"), int)]
    chars = [sum(t["chars"] for t in s["tools"]) for s in kb]
    pct = (lambda n: f"{round(100 * n / total)}%") if total else (lambda n: "0%")
    out = [f"usage: {len(have)} of {len(entries)} lookups; input tokens per lookup median {rank(per_in, 0.5)}, "
           f"p90 {rank(per_in, 0.9)}; output median {rank(per_out, 0.5)}; cache reads {pct(cread)} of input, "
           f"subagents {pct(sub)}"]
    if kb:
        out.append(f"kb results: {len(kb)} steps, context growth median {rank(grow, 0.5)} tokens, "
                   f"result characters median {rank(chars, 0.5)}")
    return out


def work_tokens(models):
    """The tokens of a map of model counts: uncached input, cache writes, cache reads and output."""
    return sum(c["in"] + c["cw"] + c["cr"] + c["out"] for c in models.values())


def work_lines(files, week_run):
    """The digest's work lines for the work sidecars `files` whose run id `week_run` accepts: `work: N items, tokens
    T (main M%, subagents S%); top K by tokens` and one line per listed item, `  ID: T tokens, main M%, subagents
    S%`, the most tokens first and the id first among equals, at most WORK_TOP of them; [] when the week's sidecars
    hold no item line. Only item lines count (an id, or a sprint's, which holds the prompts inside several of its
    items' windows): a shared line is a session's, an overhead line the system's, and neither is an item's. An item's
    lines of the week's runs are summed. A sidecar that breaks the work gates is left out whole, as `backlog.py cost`
    does, so one bad file never skews a figure. Only ids and counts go in: the sidecar holds no text, session or
    prompt, and an item deleted at sprint close is listed by its id like any other. The work sidecar holds no kb tool
    counts, so there is no kb-tool share."""
    items = {}
    for p, objs in records(f for f in files if week_run(f.stem)):
        lines = [w for _, w in objs]
        if not lines or any(work_line_problems(w, p.stem) for w in lines):
            continue
        for w in lines:
            if "item" not in w:
                continue
            t = items.setdefault(w["item"], {"main": 0, "sub": 0})
            t["main"] += work_tokens(w.get("main") or {})
            t["sub"] += sum(work_tokens(m) for m in (w.get("sub") or {}).values())
    if not items:
        return []
    pct = lambda n, total: f"{round(100 * n / total)}%" if total else "0%"  # noqa: E731
    main, sub = sum(t["main"] for t in items.values()), sum(t["sub"] for t in items.values())
    top = sorted(items, key=lambda i: (-(items[i]["main"] + items[i]["sub"]), i))[:WORK_TOP]
    out = [f"work: {len(items)} items, tokens {main + sub} (main {pct(main, main + sub)}, subagents "
           f"{pct(sub, main + sub)}); top {len(top)} by tokens"]
    for i in top:
        t = items[i]
        total = t["main"] + t["sub"]
        out.append(f"  {i}: {total} tokens, main {pct(t['main'], total)}, subagents {pct(t['sub'], total)}")
    return out


OPS_TOP = 5  # the command classes the ops block names, most calls first
NOTHING_SELECTED = 5  # pytest's exit when no test was collected or selected: a test.run row with it is no failure
OPS_TIMED = ("land.end", "sync.gate", "test.run")  # the events whose count, failures and median ms the block gives


def row_day(row, run_id):
    """The UTC day of an ops row: its `ts`, else the day of the run that delivered it."""
    try:
        return datetime.date.fromisoformat(str(row.get("ts", ""))[:10])
    except ValueError:
        return run_day(run_id)


def ops_lines(files, in_week):
    """The digest's ops block for the rows of the ops sidecars `files` whose own day (`ts`, else the sidecar's run
    day) `in_week` accepts, so a Monday distill does not move the last week's rows: `ops: N rows (event n,
    ...)`, then `  land.end|sync.gate|test.run: N, failed F, median M ms`, `  done.refused: N`, `  agent.run: N (group
    n, ...)`, `  call.tool: N calls, errors E, interrupts I; top classes: class n, ...` and one line per hook event
    kind present; [] when the week's sidecars hold no row. A sidecar that breaks the ops gates is left out whole, as
    work_lines does. Only event names, classes and counts go in."""
    rows = []
    for p, objs in records(files):
        lines = [w for _, w in objs]
        if lines and not any(ops_line_problems(w, p.stem) for w in lines):
            rows += [w for w in lines if in_week(row_day(w, p.stem))]
    if not rows:
        return []
    by = {}
    for r in rows:
        by.setdefault(r["event"], []).append(r)
    out = [f"ops: {len(rows)} rows ({_counts((e, len(by[e])) for e in sorted(by))})"]
    for e in OPS_TIMED:
        if e in by:
            empty = sum(1 for r in by[e] if e == "test.run" and r.get("exit") == NOTHING_SELECTED)
            failed = sum(1 for r in by[e] if r.get("exit") not in (0, None)) - empty
            out.append(f"  {e}: {len(by[e])}, failed {failed}, median {rank([r['ms'] for r in by[e]], 0.5)} ms"
                       + (f", selected nothing {empty}" if empty else ""))
    if "done.refused" in by:
        out.append(f"  done.refused: {len(by['done.refused'])}")
    if "agent.run" in by:
        groups = {}
        for r in by["agent.run"]:
            groups[r["group"]] = groups.get(r["group"], 0) + 1
        out.append(f"  agent.run: {len(by['agent.run'])} ({_counts(sorted(groups.items()))})")
    if "call.tool" in by:
        calls, classes = by["call.tool"], {}
        for r in calls:
            k = r.get("class") or r["tool"]
            classes[k] = classes.get(k, 0) + 1
        top = sorted(classes, key=lambda k: (-classes[k], k))[:OPS_TOP]
        out.append(f"  call.tool: {len(calls)} calls, errors {sum(1 for r in calls if r['outcome'] == 'error')}, "
                   f"interrupts {sum(1 for r in calls if r['outcome'] == 'interrupt')}; top classes: "
                   f"{_counts((k, classes[k]) for k in top)}")
    for e in ("permission.request", "permission.denied", "compact.pre", "compact.post", "turn.error"):
        if e in by:
            out.append(f"  {e}: {len(by[e])}")
    return out


def intake_line(backlog=None):
    """The digest's line for the backlog's intake: the open items (not done or dropped) `backlog.py intake --file`
    filed, counted by the detector named in their `detector <name>` link, such as `intake: 3 open (drift 1, trailers 2)`,
    or `intake: none open`. It reads the item files of `backlog` (default kb/_self/backlog) as they are in the working
    tree, uncommitted drafts included, and never runs a detector, which would take longer than the digest may."""
    found = {}
    d = Path(backlog or BACKLOG)
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            it = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(it, dict) or it.get("status") in ("done", "dropped"):
            continue
        for link in it.get("links") or []:
            if isinstance(link, str) and link.startswith(DETECTOR_LINK) and link[len(DETECTOR_LINK):].strip():
                name = link[len(DETECTOR_LINK):].strip()
                found[name] = found.get(name, 0) + 1
                break
    if not found:
        return "intake: none open"
    return f"intake: {sum(found.values())} open ({_counts(sorted(found.items()))})"


def rules_lines(rules, open_findings):
    """The digest's rules block, for the week's lookups in the rule docs (entries with `root` _self, which no public
    count holds) and the `rules` findings still open at its end: `rules lookups: N (verdict n, ...)`, the printed
    characters (sum and mean over the lookups that kept them), the sets run and the open findings. Nothing when the
    week has neither."""
    if not rules and not open_findings:
        return []
    verdicts = [(v, sum(1 for e in rules if e.get("verdict") == v)) for v in reversed(VERDICTS)]
    verdicts.append(("no verdict", sum(1 for e in rules if e.get("verdict") not in VERDICTS)))
    printed = [e["chars"] for e in rules if isinstance(e.get("chars"), int)]
    mean = round(sum(printed) / len(printed)) if printed else 0
    return [f"rules lookups: {len(rules)}" + (f" ({_counts(verdicts)})" if rules else ""),
            f"rules printed characters: {sum(printed)}, mean {mean}",
            f"rules sets run: {sum(1 for e in rules if e.get('set'))}, open rules findings: {open_findings}"]


def digest(store=None, week=None, backlog=None):
    """(week, lines, whether the week holds anything) of the committed store (default kb/_querylog) for the ISO week
    `week` (default: the week of the newest entry). Only the store and `week` go in, so every clone at the same
    commit prints the same lines, except the last, the `intake_line` of the item files in `backlog`: kb/_self/backlog
    when `store` is the default store too, else none unless given. Entries count by their `day`, run and findings
    files by their run id's date, and findings states are each finding's last record in the findings files dated up
    to the week's Sunday."""
    if backlog is None and store is None:
        backlog = BACKLOG
    store = Path(store or STORE)
    week = week or latest_week(store)
    if week is None:
        return None, ["query log digest: the store holds no run file"], False
    monday, sunday = week_days(week)
    lo, hi = monday.isoformat(), sunday.isoformat()

    def inside(d):
        return d is not None and monday <= d <= sunday

    week_entries = [e for _, e in store_entries(store) if isinstance(e.get("day"), str) and lo <= e["day"] <= hi]
    rules = [e for e in week_entries if e.get("root") == RULES_ROOT]
    entries = [e for e in week_entries if e.get("root") != RULES_ROOT]
    runs, dropped = 0, 0
    for p in run_files(store):
        if not inside(run_day(p.stem)):
            continue
        runs += 1
        try:
            counts = load_run(p)[0][1].get("counts")
        except (OSError, ValueError, IndexError):
            continue
        if isinstance(counts, dict) and isinstance(counts.get("dropped"), int):
            dropped += counts["dropped"]
    state, recorded = {}, 0
    dated = [p for p in findings_files(store) if run_day(p.stem) is not None and run_day(p.stem) <= sunday]
    for p, objs in records(dated):
        recs = [r for _, r in objs if isinstance(r.get("id"), str)]
        recorded += len(recs) if inside(run_day(p.stem)) else 0
        state.update((r["id"], r) for r in recs)
    surfaces = [(s, sum(1 for e in entries if e.get("surface") == s)) for s in SURFACES]
    verdicts = [(v, sum(1 for e in entries if e.get("verdict") == v)) for v in reversed(VERDICTS)]
    verdicts.append(("no verdict", sum(1 for e in entries if e.get("verdict") not in VERDICTS)))
    judged_ = [(j, sum(1 for e in entries if e.get("judged") == j)) for j in JUDGED]
    judged_.append(("not judged", sum(1 for e in entries if e.get("judged") not in JUDGED)))
    misses = [e for e in entries if is_miss(e)]
    fixed = {"by the kb since": 0, "by apply": 0, "by research": 0}
    for e in misses:  # once per miss, by the finding that stands for it: its eval finding when it has one (learn
        # turns a gap candidate into an eval finding and records the gap fixed-since), else its gap finding
        recs = [(kind, state.get(finding_id(kind, e["id"]))) for kind in MISS_KINDS]
        recs = [(kind, r) for kind, r in recs if r is not None]
        if not recs or any(r.get("state") == "open" for _, r in recs):
            continue
        kind, r = recs[0]
        if r.get("state") == "fixed-since":
            fixed["by the kb since"] += 1
        elif r.get("state") == "applied" and kind == "eval":
            fixed["by apply"] += 1
        elif r.get("state") == "applied" and r.get("stage") == "claim":
            fixed["by research"] += 1
    items = []
    for e in entries:
        items += [f for f in e.get("fetches") or [] if isinstance(f, dict)]
        if e.get("outcome"):
            items.append({k: e[k] for k in FETCH_KEYS if k in e})
    nfetch = sum(f["n"] if isinstance(f.get("n"), int) else 1 for f in items)
    failed = sum(f["n"] if isinstance(f.get("n"), int) else 1 for f in items
                 if isinstance(f.get("outcome"), str) and FAILED.fullmatch(f["outcome"]))
    chars = sum(f["chars"] for f in items if isinstance(f.get("chars"), int))
    lines = [f"query log digest {week} ({lo} to {hi})",
             f"lookups: {len(entries)}" + (f" ({_counts((s, n) for s, n in surfaces if n)})" if entries else ""),
             f"verdicts: {_counts(verdicts)}",
             f"judged: {_counts(judged_)}",
             f"misses: {len(misses)}, fixed: {sum(fixed.values())} ({_counts(fixed.items())})",
             f"fetches: {nfetch}, failed {failed}, result characters {chars}",
             *rules_lines(rules, sum(1 for r in state.values() if r.get("kind") == "rules" and r.get("state") == "open")),
             *usage_lines(entries, usage_records(store)),
             *work_lines(work_files(store), lambda stem: inside(run_day(stem))),
             *ops_lines(ops_files(store), inside),
             f"runs: {runs}, entries dropped by redaction {dropped}",
             f"finding records written: {recorded}"]
    table = {}
    for r in state.values():
        if r.get("kind") in FINDING_KINDS and r.get("state") in FINDING_STATES:
            table.setdefault(r["kind"], {}).setdefault(r["state"], 0)
            table[r["kind"]][r["state"]] += 1
    lines.append("findings by kind and state at the week's end:" + ("" if table else " none"))
    for kind in FINDING_KINDS:
        if kind in table:
            lines.append(f"  {kind}: " + _counts((s, table[kind][s]) for s in FINDING_STATES if s in table[kind]))
    if backlog is not None:
        lines.append(intake_line(backlog))
    return week, lines, bool(week_entries or runs or recorded)


def digest_hook(now_dt=None, store=None, backlog=None):
    """The SessionStart digest: the JSON line `{"systemMessage": ...}` the first SessionStart of an ISO week prints
    (last week's digest), or None: logging off (mode `off`, the DISABLED marker), already shown this week (the marker
    beside the spool names the week), an empty week, or reading the store took more than DIGEST_BUDGET_S. The
    marker is written before the store is read, so a slow or failed digest is not tried again that week."""
    t0 = time.monotonic()
    qdir, cfg = places()
    if logging_off(qdir, cfg):
        return None
    today = (now_dt or datetime.datetime.now(datetime.timezone.utc)).date()
    this = iso_week(today)
    marker = qdir / DIGEST_MARKER
    try:
        if marker.read_text(encoding="utf-8").strip() == this:
            return None
    except OSError:
        pass
    write_text(marker, this + "\n")
    _, lines, found = digest(store, iso_week(today - datetime.timedelta(days=7)), backlog)
    if not found or time.monotonic() - t0 > DIGEST_BUDGET_S:
        return None
    return json.dumps({"systemMessage": "\n".join(lines)}, ensure_ascii=False)


def hook_digest():
    """`digest --hook`: the SessionStart event on stdin is read and left unused; at most one JSON line; exit 0."""
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.read()
    except Exception:  # noqa: BLE001 - the event carries nothing the digest needs
        pass
    try:
        line = digest_hook()
    except Exception:  # noqa: BLE001 - a session starts whatever happens here
        line = None
    if line:
        sys.stdout.reconfigure(encoding="utf-8")
        print(line)
    return 0


def conflict_mrs(url, run):
    """([(number, branch, title, url)] (`!iid` on GitLab, `#number` on GitHub) of the open merge requests from a
    CONFLICT_BRANCH_PREFIX branch to BRANCH on origin's forge, None and a note when glab or gh is not signed in or
    the call fails). The API filters by one whole branch name, so the open ones targeting BRANCH are listed and the
    prefix is matched here."""
    forge = origin_forge(url)[0]
    data, _, note = forge_list(
        url, run, lambda repo: ["gh", "pr", "list", "-R", repo, "--base", BRANCH, "--state", "open",
                                "--json", "number,title,headRefName,url", "-L", "100"],
        lambda project: f"projects/{project}/merge_requests?state=opened&target_branch={BRANCH}&per_page=100",
        named=3)
    if data is None:
        return None, note
    out = []
    for r in data:
        if not isinstance(r, dict):
            continue
        branch = r.get("headRefName") if forge == "github" else r.get("source_branch")
        if isinstance(branch, str) and branch.startswith(CONFLICT_BRANCH_PREFIX):
            num = f"#{r.get('number')}" if forge == "github" else f"!{r.get('iid')}"
            out.append((num, branch, str(r.get("title") or ""), str(r.get("url") or r.get("web_url") or "")))
    return sorted(out, key=lambda m: m[1]), note


def reverted_commits(home, run):
    """[(short hash, subject)] of the commits at HEAD whose KB-Auto trailer holds `revert`, newest first."""
    return [(h, subject) for h, subject, values in auto_log(run, home, "HEAD", sha="%h") if "revert" in values]


def status(store=None, home=None, run=None, out=print):
    """Three lists from the committed store and the clone at `home`: open source findings, most result characters
    first (the characters the store's fetches of the host returned); open conflict merge requests on origin's forge
    (skipped with a note when glab or gh is not signed in, or there is no origin); automatic commits that were
    reverted (KB-Auto: revert). 0."""
    store, home, run = Path(store or STORE), Path(home or HOME), run or run_cmd
    hosts = host_fetches(store_entries(store))
    found = [r for r in finding_states(store).values() if r.get("kind") == "source" and r.get("state") == "open"]
    chars = {r["id"]: hosts.get(r.get("host"), {}).get("chars", 0) for r in found}
    found.sort(key=lambda r: (-chars[r["id"]], str(r.get("host")), str(r.get("signal")), r["id"]))
    out(f"open source findings, most result characters first: {len(found)}")
    for r in found:
        if r.get("signal") == "stage":
            what = f"stage: level {r.get('level')}, needs {r.get('needs')} ({', '.join(r.get('triggers') or [])})"
        else:
            what = f"route: {r.get('tool')} read a host of `{r.get('route')}`"
        out(f"  {chars[r['id']]} chars  {r.get('host')}  {what}  {r['id']}")
    code, url, _ = run(["git", "remote", "get-url", REMOTE], cwd=str(home))
    if code:
        out(f"open conflict merge requests: not checked: no remote {REMOTE}")
    else:
        mrs, note = conflict_mrs(url.strip(), run)
        if mrs is None:
            out(f"open conflict merge requests: not checked: {note}")
        else:
            out(f"open conflict merge requests ({note}): {len(mrs)}")
            for num, branch, title, link in mrs:
                out(f"  {num} {branch}  {title}  {link}".rstrip())
    reverts = reverted_commits(home, run)
    out(f"reverted automatic commits: {len(reverts)}")
    for h, subject in reverts:
        out(f"  {h} {subject}")
    return 0


# ---------------------------------------------------------------- show (Reporting, Show)

SHOW_LIMIT = 40  # lines of a list `show` prints unless --limit says otherwise
SHOW_ID = re.compile(r"[0-9A-Za-z-]{1,40}")  # a run id, an entry id, or the start of one
SHOW_ARTICLE = re.compile(r"[\w.-]+(?:/[\w.-]+)*")  # an article path or its tail, `laps.md` included
SHOW_QUESTION_CHARS = 80  # the question a run's entry list keeps of each entry
FINDING_FIELDS = ("expect", "article", "terms", "tried", "signal", "host", "level", "needs", "triggers", "tool",
                  "route")  # what `show --findings` prints of a record besides its id, kind, state, stage and entry


class ShowRefused(ValueError):
    """A request `show` refuses: exit 2, the rule in the message."""


def _flat(v):
    """A value on one line: a string as it is, a list of strings joined by commas, anything else as compact JSON."""
    if isinstance(v, str):
        return " ".join(v.split())
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return ", ".join(" ".join(x.split()) for x in v)
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _capped(lines, limit, hint, out):
    """Print `lines`, at most `limit` of them (0: all), then one line saying how many were left out."""
    for line in lines if not limit else lines[:limit]:
        out(line)
    if limit and len(lines) > limit:
        out(f"... {len(lines) - limit} more ({hint})")


def _pick(names, given, what):
    """The one name of `names` that `given` is or starts with, else ShowRefused with the rule."""
    if not SHOW_ID.fullmatch(given):
        raise ShowRefused(f"{what} {given!r} is not an id: it is letters, digits and hyphens, up to 40 characters")
    found, hits = resolve_id(names, given)
    if found is None and not hits:
        raise ShowRefused(f"unknown {what} {given!r}: no {what} id of the store starts with it")
    if found is None:
        more = f", {len(hits) - 3} more" if len(hits) > 3 else ""
        raise ShowRefused(f"{what} {given!r} is ambiguous: {len(hits)} ids start with it ({', '.join(hits[:3])}{more});"
                          " give more characters")
    return found


def _read(p):
    """[(line number, object)] of a store file, ShowRefused naming the file when it does not read."""
    try:
        return load_run(p)
    except (OSError, ValueError) as e:
        raise ShowRefused(f"{p.name} does not read ({type(e).__name__}): run `querylog.py check`") from None


def _rank(r):
    return FINDING_KINDS.index(r["kind"]) if r.get("kind") in FINDING_KINDS else len(FINDING_KINDS), str(r.get("id"))


def _entry_line(e):
    cites = e.get("citations")
    return (f"  {e.get('id')} {e.get('surface', '-')} {e.get('day', '-')} {e.get('verdict', '-')} "
            f"{e.get('judged', '-')} {len(cites) if isinstance(cites, list) else 0} lines  "
            f"{_flat(e.get('question', ''))[:SHOW_QUESTION_CHARS]}").rstrip()


def _finding_line(r, entry=True):
    fields = " ".join(f"{k}={_flat(r[k])}" for k in FINDING_FIELDS if k in r)
    return " ".join(x for x in (str(r.get("id")), str(r.get("kind")), str(r.get("state")),
                                f"stage={r['stage']}" if "stage" in r else "",
                                f"entry={r['entry']}" if entry and "entry" in r else "", fields) if x)


def show_run(store, given, limit, out):
    """One run file: its header, whether it has a usage sidecar, and one line per entry (id, surface, day, verdict,
    judged, citation count, the question's start)."""
    path = {p.stem: p for p in run_files(store)}
    run = _pick(sorted(path), given, "run")
    objs = _read(path[run])
    head = objs[0][1] if objs else {}
    counts = head.get("counts") if isinstance(head.get("counts"), dict) else {}
    out(f"run {run}: pipeline {head.get('pipeline', '-')}, retrieval {head.get('retrieval', '-')}, "
        f"kb_commit {str(head.get('kb_commit', '-'))[:12]}")
    out("counts: " + (_counts(counts.items()) or "none"))
    out("usage sidecar: " + ("yes" if any(p.stem == run for p in usage_files(store)) else "no"))
    lines = [_entry_line(e) for _, e in objs[1:]]
    out(f"entries: {len(lines)}")
    _capped(lines, limit, "--limit 0 prints all", out)


def show_entry(store, given, out):
    """One entry with every field it holds, the findings that name it and whether it has usage."""
    found = {e["id"]: (r, e) for r, e in store_entries(store)}
    entry_id = _pick(sorted(found), given, "entry")
    run, e = found[entry_id]
    out(f"entry {entry_id} (run {run})")
    for k in ENTRY_KEYS:
        if k == "id" or k not in e:
            continue
        v = e[k]
        if k == "citations" and isinstance(v, list):
            out(f"citations: {len(v)}")
            for c in v:
                c = c if isinstance(c, dict) else {}
                out("  " + " ".join(str(c[ck]) for ck in ("line", "tag", "verdict") if ck in c))
        elif k == "fetches" and isinstance(v, list):
            out(f"fetches: {len(v)}")
            for f in v:
                f = f if isinstance(f, dict) else {}
                out("  " + " ".join(f"{fk}={_flat(f[fk])}" for fk in FETCH_KEYS if fk in f))
        else:
            out(f"{k}: {_flat(v)}")
    recs = sorted((r for r in finding_states(store).values() if r.get("entry") == entry_id), key=_rank)
    out(f"findings: {len(recs)}")
    for r in recs:
        out("  " + _finding_line(r, entry=False))
    out("usage: " + ("yes, in the usage sidecar of its run" if entry_id in usage_records(store) else "none"))


def show_findings(store, kind, article, state, limit, out):
    """Each finding's last record (kind order, then id) that has `kind` and `state`, and `article` as its article or
    expected article (the whole path, or its tail after a `/`)."""
    def has_article(r):
        return any(isinstance(r.get(k), str) and (r[k] == article or r[k].endswith("/" + article))
                   for k in ("article", "expect"))
    recs = sorted((r for r in finding_states(store).values()
                   if (kind is None or r.get("kind") == kind) and (state is None or r.get("state") == state)
                   and (article is None or has_article(r))), key=_rank)
    named = [f"{k} {v}" for k, v in (("kind", kind), ("article", article), ("state", state)) if v is not None]
    out(f"findings: {len(recs)}" + (f" ({', '.join(named)})" if named else ""))
    _capped([_finding_line(r) for r in recs], limit, "narrow with --kind, --article, --state, or --limit 0", out)


def usage_totals(u):
    """{in, cw, cr, out, requests, sub_in, steps} of one usage line, reading only what is a whole number."""
    def n(c, k):
        v = c.get(k) if isinstance(c, dict) else None
        return v if isinstance(v, int) and not isinstance(v, bool) else 0

    def models(group):
        return list(group.values()) if isinstance(group, dict) else []
    main = models(u.get("main"))
    sub = [c for g in u["sub"].values() for c in models(g)] if isinstance(u.get("sub"), dict) else []
    t = {k: sum(n(c, k) for c in main + sub) for k in ("in", "cw", "cr", "out", "requests")}
    t["sub_in"] = sum(n(c, k) for c in sub for k in ("in", "cw", "cr"))
    t["steps"] = len(u["steps"]) if isinstance(u.get("steps"), list) else 0
    return t


def show_usage(store, given, limit, out):
    """One run's usage sidecar: its header and one line per entry with the input and output tokens."""
    run = _pick(run_ids(store), given, "run")
    files = [p for p in usage_files(store) if p.stem == run]
    if not files:
        out(f"usage {run}: no sidecar (no entry of the run had a usage row)")
        return
    objs = _read(files[0])
    head = objs[0][1] if objs else {}
    counts = head.get("counts") if isinstance(head.get("counts"), dict) else {}
    out(f"usage {run}: reader {head.get('reader', '-')}, entries {counts.get('entries', '-')}, "
        f"missing {counts.get('missing', '-')}")
    lines = []
    for _, u in objs[1:]:
        t = usage_totals(u)
        lines.append(f"  {u.get('id')} input {t['in'] + t['cw'] + t['cr']} (uncached {t['in']}, cache write "
                     f"{t['cw']}, cache read {t['cr']}), output {t['out']}, requests {t['requests']}, subagents "
                     f"input {t['sub_in']}, steps {t['steps']}"
                     + (f" (+{u['cut']} cut)" if isinstance(u.get("cut"), int) else ""))
    _capped(lines, limit, "--limit 0 prints all", out)


def show_spool(out, spool=None):
    """The local spool by file and by kind of row, never by what a row holds: the spool keeps prompts and answers as
    typed, and what the store holds is all `show` prints. A session file is named by its number (the store holds no
    session id), a tools file by its day; each line gives the file's rows by surface, the days they fall on, the
    rows distill cannot read, and whether its session ended. The last line counts the rows whose id an entry of the
    committed store carries (rows mode `auto` keeps until their run file is on origin/main)."""
    import ql_distill
    spool = Path(spool) if spool else places()[0] / "spool"
    files = sorted(spool.glob("*.jsonl")) if spool.is_dir() else []
    if not files:
        out("spool: empty")
        return
    held = {e["id"] for _, e in store_entries(STORE)}
    parsed, n_session = [], 0
    for p in files:
        rs, bad = ql_distill.spool_rows(p)
        if p.name.startswith("tools-"):
            label = "tools " + p.stem[len("tools-"):]
        else:
            n_session += 1
            label = f"session {n_session}, " + ("ended" if p.with_suffix(".end").exists() else "open")
        by = _counts((s, n) for s, n in ((s, sum(1 for r in rs if r["surface"] == s)) for s in ROW_SURFACES) if n)
        days = sorted({r["ts"][:10] for r in rs if DAY.fullmatch(r["ts"][:10])})
        span = f", days {days[0]}" + (f" to {days[-1]}" if days[-1] != days[0] else "") if days else ""
        parsed.append((rs, f"  {label}: {len(rs)} rows ({by or 'none'}){span}" + (f", {bad} unreadable" if bad else "")))
    out(f"spool: {len(files)} files, {sum(len(rs) for rs, _ in parsed)} rows")
    for _, line in parsed:
        out(line)
    out(f"rows whose id the committed store holds: {sum(1 for rs, _ in parsed for r in rs if r['id'] in held)}")


def show(store=None, run=None, entry=None, findings=False, usage=None, spool=False, kind=None, article=None,
         state=None, limit=SHOW_LIMIT, out=print, err=None):
    """`querylog.py show`: exactly one of `run`, `entry`, `findings`, `usage` (a run) or `spool`, read from the
    committed store (default kb/_querylog) or `store`, never written. `kind`, `article` and `state` filter
    `findings`. A refused request (the reason on `err`, default stderr) is 2; an answer, even an empty one, 0."""
    err = err or (lambda s: print(s, file=sys.stderr))
    try:
        modes = [m for m, on in (("--run", run is not None), ("--entry", entry is not None), ("--findings", findings),
                                 ("--usage", usage is not None), ("--spool", spool)) if on]
        if len(modes) != 1:
            raise ShowRefused("give one of --run, --entry, --findings, --usage or --spool"
                              + (f", not {' and '.join(modes)}" if modes else ""))
        if not findings and any(v is not None for v in (kind, article, state)):
            raise ShowRefused("--kind, --article and --state filter --findings only")
        if kind is not None and kind not in FINDING_KINDS:
            raise ShowRefused(f"--kind {kind!r} is not a finding kind: {', '.join(FINDING_KINDS)}")
        if state is not None and state not in FINDING_STATES:
            raise ShowRefused(f"--state {state!r} is not a finding state: {', '.join(FINDING_STATES)}")
        if article is not None and not SHOW_ARTICLE.fullmatch(article):
            raise ShowRefused(f"--article {article!r} is not an article path: a path or its tail, such as "
                              "public/windows/laps.md or laps.md")
        if limit < 0:
            raise ShowRefused("--limit is a number of lines, 0 or more (0 prints all)")
        if spool:
            if store is not None:
                raise ShowRefused("--spool reads the local spool, which is no store: --store does not apply")
            show_spool(out)
            return 0
        root = Path(store or STORE)
        if not root.is_dir():
            raise ShowRefused("--store names no directory: it is a store laid out as kb/_querylog")
        if run is not None:
            show_run(root, run, limit, out)
        elif entry is not None:
            show_entry(root, entry, out)
        elif usage is not None:
            show_usage(root, usage, limit, out)
        else:
            show_findings(root, kind, article, state, limit, out)
        return 0
    except ShowRefused as e:
        err(f"show: refused: {e}")
        return 2
