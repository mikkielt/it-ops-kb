"""kbmon's kb panel (kb/_self/monitoring.md): the roots with their articles and facts by tag, the open gaps and conflicts,
the newest refresh and census dates, the last recorded lookup-eval outcome, the age of the pack index and the command-line
tools the catalog of `kbtools.py` lists, with those whose module docstring lacks its `Answers:` or `Use:` line.

The counts are `rag.py audit`'s (`kbfacts.audit`'s rows without the gap and conflict entries it links to each article,
which the panel does not show and which take most of its time), read in this process and read again only when a file of a
root changed (its name, time or size). The panel reads and writes nothing: it builds no index (KB_INDEX=0 for the rest of the
process, so the fingerprint memo is not written either), runs no eval (the outcome is the newest `land.step` row of
`rag.py-eval` in the ops rows) and starts no network request. Imports `mon_base`; `kbfacts`, `kbcommon`, `bl_stall`
and `kbtools` where it reads them.
"""
import collections
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import mon_base

CENSUS_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.csv")
REFRESH_S = 10  # seconds the live view serves the last result
EVAL_STEP = "rag.py-eval"  # the `land.step` row of the lookup eval at a landing
COUNTED = {"lock": threading.Lock(), "signature": None, "value": None}  # the counts of the last read and the files they came from


def index_age(kbfacts):
    """Seconds since the newest pack index file was written or last used (the index marks its file used while it serves
    a lookup), or None when there is none or no index directory."""
    where = kbfacts.index_dir()
    if not where or not Path(where).is_dir():
        return None
    times = []
    for p in Path(where).glob("kbindex-*.sqlite"):
        try:
            times.append(p.stat().st_mtime)
        except OSError:
            continue
    return max(0, int(time.time() - max(times))) if times else None


def open_entries(kbfacts, name, tag=""):
    """The entries of a ledger (`_gaps.md`, `_conflicts.md`) in every root that no continuation line has settled and whose
    text holds `tag` (the gaps' `[UNK`, as `bench_pool.open_gaps` reads them; none for the conflicts)."""
    return sum(1 for e in kbfacts.ledger_entries(name) if tag in e["text"] and not kbfacts.OPEN_GAP.search(e["text"]))


def census_date(kbcommon):
    """The newest census file name's date over the roots (`_census/YYYY-MM-DD.csv`), or None."""
    dates = [p.stem for r in kbcommon.roots() for p in Path(r.path, "_census").glob("*.csv") if CENSUS_FILE.fullmatch(p.name)]
    return max(dates) if dates else None


def census_tag(root):
    """The newest `census-*` tag of the clone, or None (no tag, no git)."""
    try:
        done = subprocess.run(["git", "for-each-ref", "--sort=-creatordate", "--count=1", "--format=%(refname:short)",
                               "refs/tags/census-*"], cwd=root, capture_output=True, text=True, timeout=5,
                              env={**os.environ, "GIT_NO_LAZY_FETCH": "1"})
    except (OSError, subprocess.SubprocessError):
        return None
    return (done.stdout.strip() or None) if done.returncode == 0 else None


def last_eval(root):
    """{"state": passed|failed, "when": UTC time} of the newest recorded lookup eval at a landing, or None."""
    try:
        import bl_stall
        rows = [r for r in bl_stall.ops_rows(str(root)) if r.get("event") == "land.step" and r.get("step") == EVAL_STEP]
    except Exception:  # noqa: BLE001 - an unreadable log is no outcome
        return None
    if not rows:
        return None
    last = rows[-1]
    return {"state": "passed" if last.get("exit") == 0 else "failed", "when": last.get("ts")}


def tool_counts(root):
    """{"count": the command-line tools of `_tools/`, "missing": the names of those lacking the `Answers:` or `Use:` line}."""
    import kbtools
    entries = kbtools.tool_entries(root)
    return {"count": len(entries), "missing": sorted(e["tool"] for e in entries if e["missing"])}


def alerts(data):
    """The alerts of the panel's data: one `eval` alert (id `kb.eval`) while the newest recorded lookup eval at a landing
    failed; none while it passed or none is recorded."""
    ev = data.get("eval")
    if not isinstance(ev, dict) or ev.get("state") != "failed":
        return []
    when = ev.get("when")
    return [{"kind": "eval", "id": "kb.eval", "panel": "kb", "message": "lookup eval FAILED at the last landing",
             "since": str(when)[:16].replace("T", " ") + " UTC" if when else ""}]


def tree_signature(kbcommon):
    """The name, time and size of every file under the roots: what the counts are read from."""
    out = []
    for r in kbcommon.roots():
        for where, _, names in os.walk(r.path):
            for name in names:
                try:
                    st = os.stat(os.path.join(where, name))
                except OSError:
                    continue
                out.append((where, name, st.st_mtime_ns, st.st_size))
    return out


def audit_rows(kbfacts):
    """`kbfacts.audit()`'s rows (path, retrieved_utc and the fact counts by kind) with no ledger entries linked."""
    tfiles = kbfacts.topic_files()
    rows = []
    for rel, meta in sorted(kbfacts.articles().items()):
        units = [u for f in tfiles.get(meta["topic"], [rel])
                 for u in (kbfacts.md_units if f.endswith(".md") else kbfacts.csv_units)(f, kbfacts.read(f) or "")]
        counts = collections.Counter(k for u in units for k in kbfacts.kinds_of(u["tags"]))
        rows.append({"path": rel, "retrieved_utc": meta.get("retrieved_utc", ""),
                     **{k: counts.get(k, 0) for k in kbfacts.EVIDENCE_KINDS}})
    return rows


def counts(kbfacts, kbcommon):
    """(roots, refreshed): the articles and facts by tag of each root and the newest refresh date, served again while no file
    of a root changed."""
    with COUNTED["lock"]:
        sig = tree_signature(kbcommon)
        if COUNTED["signature"] != sig:
            os.environ["KB_INDEX"] = "0"
            rows = audit_rows(kbfacts)
            roots = []
            for r in kbcommon.roots():
                mine = [x for x in rows if x["path"].startswith(r.name + "/")]
                roots.append({"root": r.name, "articles": len(mine),
                              "facts": {k: sum(x.get(k, 0) for x in mine) for k in kbfacts.EVIDENCE_KINDS}})
            dates = [x["retrieved_utc"] for x in rows if x.get("retrieved_utc")]
            COUNTED.update(signature=sig, value=(roots, max(dates) if dates else None))
        return COUNTED["value"]


def collect(ctx):
    import kbcommon
    if Path(ctx.root).resolve() != Path(kbcommon.HOME).resolve():
        raise mon_base.Unsupported("the kb panel reads the clone this script is in; --root names another")
    import kbfacts
    age = index_age(kbfacts)
    roots, refreshed = counts(kbfacts, kbcommon)
    return {"roots": roots, "gaps": open_entries(kbfacts, kbcommon.GAPS, "[UNK"), "conflicts": open_entries(kbfacts, kbcommon.CONFLICTS),
            "refreshed": refreshed, "census": census_date(kbcommon), "census_tag": census_tag(ctx.root),
            "eval": last_eval(ctx.root), "index_age_s": age, "tools": tool_counts(ctx.root)}


GUTTER = 2  # columns the view puts before each body row
CONTINUE = 10  # a wrapped row continues at column 12 of the view, 10 of the panel's own row


def wrapped(head, items, sep, width):
    """`head` and ITEMS joined by SEP, wrapped at an item within WIDTH columns of the view (the gutter included) and continued
    at column 12; an item is never split, and a row that one item keeps too long is left to the view's cut. No wrap without
    WIDTH. An empty `head` starts the first row with the first item."""
    room = (width or 10 ** 6) - GUTTER
    rows, cur = [], head
    for n, item in enumerate(items):
        glue = " " if n == 0 and head else sep
        if n == 0 and not head:
            cur = item
        elif len(cur) + len(glue) + len(item) <= room or n == 0:
            cur += glue + item
        else:
            rows.append(cur + sep.rstrip())
            cur = " " * CONTINUE + item
    rows.append(cur)
    return rows


def lines(data, width=None):
    """The text lines of the panel: roots, facts by tag, open ledger entries, then the refresh line and the tools line, each
    wrapped at an item within WIDTH columns (counts, dates and states stay whole)."""
    out = []
    for r in data["roots"]:
        facts = [f"{k} {n}" for k, n in r["facts"].items()]
        out += wrapped(f"{r['root']}: {r['articles']} articles;", facts, " ", width)
    out.append(f"open: {data['gaps']} gaps, {data['conflicts']} conflicts")
    ev = data.get("eval")
    ev_text = f"{ev['state']} {ev['when']}" if ev else "none recorded"
    age = data.get("index_age_s")
    parts = [f"refreshed {data.get('refreshed') or '-'}", f"census {data.get('census') or '-'} ({data.get('census_tag') or 'no tag'})",
             f"eval {ev_text}", f"index {f'{age}s old' if age is not None else 'none'}"]
    out += wrapped("", parts, "; ", width)
    tools = data.get("tools")
    if tools:
        missing = list(tools["missing"][:3]) + (["..."] if len(tools["missing"]) > 3 else [])
        head = f"tools: {tools['count']} cataloged, {len(tools['missing'])} missing their Answers:/Use: lines"
        out += wrapped(head + (":" if missing else ""), [x + "," for x in missing[:-1]] + missing[-1:], " ", width)
    return out
