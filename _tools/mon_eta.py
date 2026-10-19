"""kbmon's duration history (kb/_self/monitoring.md): how long the backlog's items and sprint tails took, read from the lifecycle
commits of the local `origin/main` ref. No panel: `mon_sprint.py` reads it for its panel.

  read(root)    {"history": {kinds, all, tail, outliers}, "claimed": {item id: UTC time}}
  kind_of(item) review, research, bug, bench, content or code, from an item's JSON

An item's duration is the minutes from its last `chore(backlog): claim ID` first-parent commit before its newest
`chore(backlog): done ID` one; its kind is read from its item file as that claim commit has it. A closed sprint's tail is
the minutes from the done commit of its review story (an item of the sprint with `review` true) to its newest
`chore(backlog): close SP-ID` commit. Each kind keeps its last KEPT durations (newest done commit last); a kind of at
least OUTLIER_MIN of them drops each one above its p75 plus OUTLIER_SPREAD times its p25-p75 spread and counts them as
`outliers`. `kinds`, `all` (the kinds pooled after that) and `tail` (its last KEPT, no outlier drop) are each
`{n, p25, median, p75}` in minutes, one decimal, the statistics module's inclusive quantiles (a single duration is all three;
`kinds` lacks a kind with none). One `git log` and one `git cat-file --batch` read the history, kept in memory for the
same `origin/main` commit; nothing is written. Imports no sibling at load; `bl_base` and `bl_view` where it reads them.
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
