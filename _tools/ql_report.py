"""The query log's reporting (kb/_self/querylog.md, Reporting): the weekly digest of the committed store, shown once
per ISO week by a SessionStart hook, and `status` (open source findings, open conflict merge requests, reverted
automatic commits). Only the store and the week go into the digest, so every clone at one commit prints the same
lines.
"""
import datetime, json, math, re, sys, time
from pathlib import Path

from ql_base import HOME, STORE, logging_off, places, run_cmd, write_text
from ql_deliver import BRANCH, CONFLICT_BRANCH_PREFIX, REMOTE, auto_log, forge_list, origin_forge
from ql_learn import FAILED, host_fetches, is_miss
from ql_store import (FETCH_KEYS, FINDING_KINDS, FINDING_STATES, JUDGED, RUN_ID, SURFACES, finding_id,
                      finding_states, findings_files, load_run, records, run_files, store_entries, usage_records)
from ql_capture import VERDICTS

DIGEST_MARKER = "digest-week"  # beside the spool: the ISO week in which the SessionStart digest was last shown
DIGEST_BUDGET_S = 3  # the SessionStart digest prints nothing when reading the store took longer
DIGEST_HOOK_TIMEOUT_S = 10  # the digest hook's `timeout` in .claude/settings.json and the plugin
WEEK = re.compile(r"(\d{4})-W(\d{2})")
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


def digest(store=None, week=None):
    """(week, lines, whether the week holds anything) of the committed store (default kb/_querylog) for the ISO week
    `week` (default: the week of the newest entry). Only the store and `week` go in, so every clone at the same
    commit prints the same lines. Entries count by their `day`, run and findings files by their run id's date, and
    findings states are each finding's last record in the findings files dated up to the week's Sunday."""
    store = Path(store or STORE)
    week = week or latest_week(store)
    if week is None:
        return None, ["query log digest: the store holds no run file"], False
    monday, sunday = week_days(week)
    lo, hi = monday.isoformat(), sunday.isoformat()

    def inside(d):
        return d is not None and monday <= d <= sunday

    entries = [e for _, e in store_entries(store) if isinstance(e.get("day"), str) and lo <= e["day"] <= hi]
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
             *usage_lines(entries, usage_records(store)),
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
    return week, lines, bool(entries or runs or recorded)


def digest_hook(now_dt=None, store=None):
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
    _, lines, found = digest(store, iso_week(today - datetime.timedelta(days=7)))
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
