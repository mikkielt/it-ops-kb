"""kbmon's duration history (kb/_self/monitoring.md): how long the backlog's items and sprint tails took, read from the lifecycle
commits of the local `origin/main` ref. No panel: `mon_sprint.py` reads it for its panel.

  read(root)    {"history": {kinds, all, tail, outliers}, "claimed": {item id: UTC time}}
  kind_of(item) review, research, bug, bench, content or code, from an item's JSON
  estimate(row, history, now)
                {low_min, high_min, confidence, basis} of an active sprint's time left, or None

An item's duration is the minutes from its last `chore(backlog): claim ID` first-parent commit before its newest
`chore(backlog): done ID` one; its kind is read from its item file as that claim commit has it. A closed sprint's tail is
the minutes from the done commit of its review story (an item of the sprint with `review` true) to its newest
`chore(backlog): close SP-ID` commit. Each kind keeps its last KEPT durations (newest done commit last); a kind of at
least OUTLIER_MIN of them drops each one above its p75 plus OUTLIER_SPREAD times its p25-p75 spread and counts them as
`outliers`. `kinds`, `all` (the kinds pooled after that) and `tail` (its last KEPT, no outlier drop) are each
`{n, p25, median, p75}` in minutes, one decimal, the statistics module's inclusive quantiles (a single duration is all three;
`kinds` lacks a kind with none). One `git log` and one `git cat-file --batch` read the history, kept in memory for the
same `origin/main` commit; nothing is written. `estimate` turns a sprint-panel row and that history into the sprint's time left
as a range (docstring of the function). Imports no sibling at load; `bl_base` and `bl_view` where it reads them.
"""
import json
import re
import statistics
import subprocess
from datetime import datetime, timezone

REF = "origin/main"
LIFECYCLE = re.compile(r"^chore\(backlog\): (claim|done|close) ([A-Z]{2}-[a-z0-9]+)")  # the commits `backlog.py` makes
KEPT = 30  # durations of each kind (and of the tail) the history keeps, the newest
OUTLIER_MIN = 4  # durations a kind needs before its outliers are dropped
OUTLIER_SPREAD = 3  # p25-p75 spreads above p75 that make a duration an outlier
POOL_MIN = 4  # durations a kind needs before its own figures are used, and the confidence `medium` needs
CONFIDENT_N = 10  # durations behind every figure of an estimate for the confidence `high`
FLOOR_MIN = 5  # minutes an item in progress, or the tail once the review is done, still counts
WORKERS = 4  # items the estimate runs side by side, the number a sprint run takes at once
KINDS = ("review", "research", "bug", "bench", "content", "code")
BENCH_RESULTS = "kb/_self/reports/benchmarks.csv"  # the file whose touch makes a paid item a bench one
CODE_DIRS = ("_tools/", ".claude/", ".claude-plugin/", ".githooks/", "otel/")  # a touch under one makes an item code
_CACHE = {}  # (root, REF commit) -> read's result


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def kind_of(item):
    """The kind of an item's JSON: review, research, bug, bench, content or code, the first that holds."""
    touches = [t for t in item.get("touches") or [] if isinstance(t, str)]
    if item.get("review"):
        return "review"
    if item.get("goal_research"):
        return "research"
    if item.get("kind") == "bug":
        return "bug"
    if BENCH_RESULTS in touches and re.search(r"\bpaid\b", str(item.get("goal") or ""), re.IGNORECASE):
        return "bench"
    if not any(t.startswith(CODE_DIRS) or t + "/" in CODE_DIRS for t in touches):
        return "content"
    return "code"


def spread(durations):
    """(p25, median, p75) of a list of at least one duration, the inclusive method; a single duration is all three."""
    if len(durations) == 1:
        return durations[0], durations[0], durations[0]
    return tuple(statistics.quantiles(durations, n=4, method="inclusive"))


def stats(durations):
    """{n, p25, median, p75} of DURATIONS in minutes, one decimal; the three are None for none."""
    if not durations:
        return {"n": 0, "p25": None, "median": None, "p75": None}
    p25, median, p75 = (round(x, 1) for x in spread(durations))
    return {"n": len(durations), "p25": p25, "median": median, "p75": p75}


def trimmed(durations):
    """(kept, outliers): DURATIONS without those above p75 plus OUTLIER_SPREAD spreads, in a list of OUTLIER_MIN or more."""
    if len(durations) < OUTLIER_MIN:
        return list(durations), 0
    p25, _, p75 = spread(durations)
    kept = [d for d in durations if d <= p75 + OUTLIER_SPREAD * (p75 - p25)]
    return kept, len(durations) - len(kept)


def lifecycle(root):
    """(claims, dones, closes): the lifecycle commits of REF, oldest first, as `{id: [(position, time, sha)]}` for claims
    and `{id: (position, time)}` for the newest done and close commit of an id."""
    import bl_base
    text = bl_base.git(root, "log", "--first-parent", "--reverse", "-E", "--grep=^chore\\(backlog\\): (claim|done|close) ",
                       "--format=%H%x09%ct%x09%s", REF)
    claims, dones, closes, n = {}, {}, {}, 0
    for ln in text.splitlines():
        sha, _, rest = ln.partition("\t")
        ts, _, subject = rest.partition("\t")
        m = LIFECYCLE.match(subject)
        if not (m and ts.isdigit()):
            continue
        n += 1
        verb, iid = m.groups()
        if verb == "claim":
            claims.setdefault(iid, []).append((n, int(ts), sha))
        elif verb == "done":
            dones[iid] = (n, int(ts))
        else:
            closes[iid] = (n, int(ts))
    return claims, dones, closes


def claim_items(root, pairs):
    """{id: item JSON} of each (id, claim sha) of PAIRS as that commit has its item file, by one `git cat-file --batch`;
    an item whose file is missing or no JSON object at that commit is left out."""
    import bl_base
    rel = bl_base.rel_dir()
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True,
                       input="".join(f"{sha}:{rel}/{iid}.json\n" for iid, sha in pairs).encode("utf-8"))
    data, out, at = p.stdout, {}, 0
    for iid, _ in pairs:
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
            out[iid] = item
    return out


def history(root, claims, dones, closes):
    """The `history` object of the lifecycle commits."""
    done = sorted((dones[i][0], i, next((c for c in reversed(claims[i]) if c[0] < dones[i][0]), None))
                  for i in dones if i in claims)
    done = [(pos, iid, c) for pos, iid, c in done if c]
    items = claim_items(root, [(iid, c[2]) for _, iid, c in done]) if done else {}
    by_kind, reviews = {}, {}
    for pos, iid, c in done:
        if iid not in items:
            continue
        minutes = (dones[iid][1] - c[1]) / 60
        if minutes >= 0:
            by_kind.setdefault(kind_of(items[iid]), []).append(minutes)
        if items[iid].get("review") and items[iid].get("sprint"):
            reviews.setdefault(items[iid]["sprint"], []).append((pos, dones[iid][1]))
    tail = []
    for sid, (pos, ts) in sorted(closes.items(), key=lambda kv: kv[1]):
        before = [r for r in reviews.get(sid, []) if r[0] < pos]
        if before and ts >= max(before)[1]:
            tail.append((ts - max(before)[1]) / 60)
    kinds, pooled, outliers = {}, [], 0
    for k in KINDS:
        kept, dropped = trimmed(by_kind.get(k, [])[-KEPT:])
        outliers += dropped
        if kept:
            kinds[k] = stats(kept)
            pooled += kept
    return {"kinds": kinds, "all": stats(pooled), "tail": stats(tail[-KEPT:]), "outliers": outliers}


def seconds_of(text):
    """UTC seconds of a `YYYY-MM-DDTHH:MM:SSZ` stamp, None for anything else."""
    try:
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def figures(item, hist, now):
    """(low, high, n, pooled, kind) minutes one open ITEM adds: its kind's p25 and p75 of HIST, less the minutes since its
    claim when it is in progress (never below FLOOR_MIN); a kind of fewer than POOL_MIN durations takes the pooled figures
    (`pooled` true). None where HIST has no such figures."""
    kind = item.get("kind") if item.get("kind") in KINDS else "code"
    st = (hist.get("kinds") or {}).get(kind) or {}
    pooled = (st.get("n") or 0) < POOL_MIN
    if pooled:
        st = hist.get("all") or {}
    if st.get("p25") is None or st.get("p75") is None:
        return None
    low, high = st["p25"], st["p75"]
    if item.get("status") == "doing":
        claimed = seconds_of(item.get("claimed"))
        gone = max(0.0, (now - claimed) / 60) if claimed is not None and now is not None else 0.0
        low, high = max(low - gone, FLOOR_MIN), max(high - gone, FLOOR_MIN)
    return low, high, st.get("n") or 0, pooled, kind


def span(weights, after, ids, pick):
    """The minutes ids of IDS take on WORKERS side by side: the larger of the longest chain along AFTER (summed WEIGHTS[PICK])
    and the sum divided by WORKERS."""
    longest, visiting = {}, set()

    def chain(i):
        if i not in longest:
            visiting.add(i)
            longest[i] = weights[i][pick] + max((chain(j) for j in after.get(i, []) if j in ids and j not in visiting), default=0)
            visiting.discard(i)
        return longest[i]

    if not ids:
        return 0.0
    return max(max(chain(i) for i in ids), sum(weights[i][pick] for i in ids) / WORKERS)


def estimate(row, hist, now):
    """An active sprint's time left from its sprint-panel ROW, the HISTORY object and NOW (UTC seconds; None counts no minutes
    since any claim): {low_min, high_min, confidence, basis}, or None where a figure it needs is missing (no history). Each open
    item adds its kind's p25 to the low end and its p75 to the high end (`figures`); the review story comes in full after the
    other items, which run in chains along their `after` lists WORKERS side by side; the review-to-close tail is added, less
    the minutes since `review_done` once the review is done (never below FLOOR_MIN). The confidence is `high` when the fewest
    durations behind any figure is CONFIDENT_N or more, `medium` at POOL_MIN or more, else `low`; a pooled figure makes it low."""
    open_items = [x for x in row.get("open") or [] if isinstance(x, dict) and x.get("id")]
    weights, used, pooled = {}, [], []
    for x in open_items:
        got = figures(x, hist, now)
        if got is None:
            return None
        weights[x["id"]] = got[:2]
        used.append(got)
        if got[3]:
            pooled.append(got[4])
    others = [x["id"] for x in open_items if x.get("kind") != "review"]
    ids = set(others)
    after = {x["id"]: [j for j in x.get("after") or [] if isinstance(j, str)] for x in open_items}
    low = span(weights, after, ids, 0)
    high = span(weights, after, ids, 1)
    for x in open_items:
        if x.get("kind") == "review":
            low, high = low + weights[x["id"]][0], high + weights[x["id"]][1]
    tail = hist.get("tail") or {}
    if tail.get("p25") is None or tail.get("p75") is None:
        return None
    t_low, t_high = tail["p25"], tail["p75"]
    if row.get("review_done"):
        done = seconds_of(row.get("review_done"))
        gone = max(0.0, (now - done) / 60) if done is not None and now is not None else 0.0
        t_low, t_high = max(t_low - gone, FLOOR_MIN), max(t_high - gone, FLOOR_MIN)
    counts = [u[2] for u in used] + [tail.get("n") or 0]
    fewest = min(counts)
    confidence = "low" if pooled else "high" if fewest >= CONFIDENT_N else "medium" if fewest >= POOL_MIN else "low"
    parts = {}
    for _, _, n, was_pooled, kind in used:
        key = (kind, n, was_pooled)
        parts[key] = parts.get(key, 0) + 1
    basis = ", ".join(f"{c} {k}" + (f" from the {n} pooled" if p else f" from {n}") for (k, n, p), c in parts.items())
    basis += (", " if basis else "") + f"tail from {tail.get('n') or 0}"
    return {"low_min": nearest(low + t_low), "high_min": nearest(high + t_high), "confidence": confidence, "basis": basis}


def nearest(x):
    """X rounded to the nearest whole minute, halves up."""
    return int(x + 0.5)


def empty():
    """What `read` gives where REF cannot be read."""
    return {"history": {"kinds": {}, "all": stats([]), "tail": stats([]), "outliers": 0}, "claimed": {}}


def read(root):
    """{"history", "claimed"} of REF: the history object and each item's last claim commit's UTC time; both empty where
    REF cannot be read."""
    import bl_base
    try:
        bl_base.load_settings(root)
        at = bl_base.git(root, "rev-parse", REF).strip()
        key = (str(root), at)
        if key not in _CACHE:
            claims, dones, closes = lifecycle(root)
            _CACHE.clear()
            _CACHE[key] = {"history": history(root, claims, dones, closes),
                           "claimed": {i: stamp(c[-1][1]) for i, c in claims.items()}}
        return _CACHE[key]
    except Exception:  # noqa: BLE001 - no such ref, no repository
        return empty()
