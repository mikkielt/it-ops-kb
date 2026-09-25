#!/usr/bin/env python3
"""Git helpers for the kb (stdlib only): deterministic cleanup after a merge, and canonical ledger formatting.

  kbgit.py fix [--check] [--base REV] [--side REV ...]   post-merge cleanup; safe to run any time, idempotent
  kbgit.py fmt [--check]                                   only canonical CSV formatting and order (never adds or drops a row)

Why: `.gitattributes` merges the append-only ledgers with git's built-in union driver, so two branches that
each add rows or answers merge without conflict markers. Union keeps every line of both sides, so a row both
sides touched can appear twice. `fix` turns that into one clean, canonical state:

_sources.csv   conflict markers (a merge made without our .gitattributes) are dropped with union semantics; repeated
               header lines and exact duplicate rows are removed. Rows sharing an id:
               - same normalized url: merged field-wise. With --base, a row identical to the base's row is the stale
                 copy and yields to the edited one. retrieved_utc/version_or_date come from the row with the latest
                 retrieved_utc; a non-empty value beats an empty one; superseded_by is kept if either row has it.
                 Two different non-empty title/publisher/licence/artifact_sha256 values: the latest row wins and
                 the conflict is reported (a tie on retrieved_utc, or two different superseded_by, needs a human).
               - different urls: a real collision (two branches both took the next legacy number, e.g. S2205).
                 Needs --base: an id present at base keeps its base url; every other url gets its own id (the
                 existing id of that url if it has a row, else its hash id `kbid.py url`). Citations are rewritten
                 line by line: a line citing the id that only one side's version of the file has (and the base's
                 has not) belongs to that side. A line on both sides or on none, or an old citation of an id the
                 base did not have, is ambiguous: reported, exit 2, nothing written.
               Canonical form: legacy ids numerically, then hash ids sorted; csv module quoting; `\\n`; no BOM.
_fetch_state.csv  one row per id: checked_utc/error from the row with the latest check, the fetch columns
               (fetched_utc, sha256, text_sha256, bytes) from the row with the latest fetch, changed_utc the max.
_answers.md, _gaps.md, _conflicts.md  conflict markers dropped (union semantics); verbatim duplicate `##`/`###`
               sections, duplicate list items (20+ characters) in one section and duplicate rows in one table removed.
               The same answer id heading twice with different text: reported, exit 2.
_tools/lint_baseline.txt  if a merge touched it (markers, unsorted or duplicate lines), it becomes the current lint
               errors that either side had accepted, sorted: a merge never accepts new lint debt by itself.
.gitattributes  the block between `# pinned:start` and `# pinned:end` lists every _artifacts.csv path as `-text`.
Then build_index.py regenerates _coverage.csv, the README coverage table (conflict markers inside the table go
with it) and used_in. Conflict markers left anywhere else in a ledger, README or an article: exit 2.

Sides of the merge (for collisions): --side REV (repeatable), else MERGE_HEAD during a merge (HEAD + MERGE_HEAD),
else the parents of HEAD when HEAD is a merge commit. Base: --base REV (e.g. `git merge-base A B`).

Exit: 0 clean (or fixed), 1 --check and something would change, 2 a problem needs a human (nothing is written).
"""
import argparse, csv, io, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbid  # noqa: E402
import build_index  # noqa: E402

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES, STATE, ARTIFACTS = "_sources.csv", "_fetch_state.csv", "_artifacts.csv"
MD_LEDGERS = ("_answers.md", "_gaps.md", "_conflicts.md")
BASELINE = "_tools/lint_baseline.txt"
ATTRS = ".gitattributes"
LINT = os.path.join(".claude", "skills", "kb-verify", "lint.py")
PIN_START, PIN_END = "# pinned:start", "# pinned:end"
MIN_ITEM = 20  # shorter list items (`- none`) may repeat on purpose


class Problem(Exception):
    pass


# ---------------------------------------------------------------- io and git

def read(rel):
    try:
        with open(os.path.join(KB, rel), encoding="utf-8", newline="") as f:
            return f.read()
    except FileNotFoundError:
        return None


def write(rel, text):
    with open(os.path.join(KB, rel), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def git(*args):
    """stdout of a git command in the kb, or None when git or the object is unavailable."""
    try:
        p = subprocess.run(["git", *args], cwd=KB, capture_output=True)
    except OSError:
        return None
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def show(rev, rel):
    return git("show", f"{rev}:./{rel}")


def merge_sides(given):
    if given:
        return given
    head = (git("rev-parse", "-q", "--verify", "HEAD") or "").strip()
    mh = read(os.path.join(".git", "MERGE_HEAD")) if os.path.isdir(os.path.join(KB, ".git")) else None
    if head and mh:
        return [head] + mh.split()
    parents = (git("rev-list", "--parents", "-n", "1", "HEAD") or "").split()[1:]
    return parents if len(parents) >= 2 else []


# ---------------------------------------------------------------- text helpers

def strip_markers(text, name):
    """Drop conflict markers the way the union driver would (both sides kept, a diff3 base section dropped).
    Returns (text, number of conflict regions)."""
    out, state, n = [], None, 0
    for ln in text.splitlines(keepends=True):
        bare = ln.rstrip("\r\n")
        if state is None and ln.startswith("<<<<<<<"):
            state, n = "ours", n + 1
        elif state and ln.startswith("|||||||"):
            state = "base"
        elif state and bare == "=======":
            state = "theirs"
        elif state and ln.startswith(">>>>>>>"):
            state = None
        elif state != "base":
            out.append(ln)
    if state:
        raise Problem(f"{name}: unterminated conflict region")
    return "".join(out), n


def has_markers(text):
    return re.search(r"^(<<<<<<<|>>>>>>>)( |$)", text or "", re.M) is not None


def lf(text):
    text = text.lstrip("﻿").replace("\r\n", "\n")
    return text if text.endswith("\n") or not text else text + "\n"


def csv_text(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows([[r.get(c, "") for c in header] for r in rows])
    return buf.getvalue()


def parse_csv(text, name, required=("id",)):
    """(header, rows as dicts, repeated header lines dropped) of a ledger; Problem on a malformed row."""
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r]
    if not rows:
        raise Problem(f"{name}: empty")
    header, out, dropped = rows[0], [], 0
    missing = [c for c in required if c not in header]
    if missing:
        raise Problem(f"{name}: lacks column(s) {', '.join(missing)}")
    for n, r in enumerate(rows[1:], 2):
        if r == header:
            dropped += 1
            continue
        if len(r) != len(header):
            raise Problem(f"{name}: record {n} has {len(r)} fields, the header {len(header)} ({r[0][:20]!r}...)")
        out.append(dict(zip(header, r)))
    return header, out, dropped


def id_key(sid):
    return kbid.sort_key(sid) if kbid.is_source_id(sid) else (2, 0, sid)


# ---------------------------------------------------------------- _sources.csv

MERGE_CONFLICT = ("title", "publisher", "licence", "artifact_sha256")


def merge_rows(sid, rows, report):
    """One row from rows that share an id and a normalized url."""
    rows = sorted(rows, key=lambda r: r.get("retrieved_utc", ""), reverse=True)  # stable: first seen wins a tie
    latest = rows[0]
    out = dict(latest)
    for col in latest:
        if col in ("id", "used_in"):
            continue
        vals = []
        for r in rows:
            v = r.get(col, "")
            if v and v not in vals:
                vals.append(v)
        if not vals:
            continue
        if col == "superseded_by" and len(vals) > 1:
            raise Problem(f"{SOURCES}: {sid} has two superseded_by values: {' vs '.join(vals)}")
        winner = next(r for r in rows if r.get(col))
        if len(vals) > 1 and col in MERGE_CONFLICT:
            tied = [r for r in rows if r.get(col) and r.get("retrieved_utc", "") == winner.get("retrieved_utc", "")]
            if len({r[col] for r in tied}) > 1:
                raise Problem(f"{SOURCES}: {sid} {col} differs between rows with the same retrieved_utc "
                              f"{winner.get('retrieved_utc')!r}: {' vs '.join(vals)}")
            report.append(f"WARN {SOURCES}: {sid} {col}: kept {winner[col]!r} (latest retrieved_utc), dropped "
                          + ", ".join(repr(v) for v in vals if v != winner[col]))
        out[col] = winner[col]
    return out


def resolve_sources(text, base_rows, sides, report):
    """(header, rows, renames) where renames = {old id: [(url, new id, side names), ...]}."""
    text, n = strip_markers(lf(text), SOURCES)
    if n:
        report.append(f"{SOURCES}: dropped markers of {n} conflict region(s) (union)")
    header, rows, dropped = parse_csv(text, SOURCES, ("id", "url"))
    if dropped:
        report.append(f"{SOURCES}: removed {dropped} repeated header line(s)")
    groups, order = {}, []
    for r in rows:
        if r["id"] not in groups:
            order.append(r["id"])
        groups.setdefault(r["id"], []).append(r)
    by_url = {}
    for r in rows:
        by_url.setdefault(kbid.normalize_url(r["url"]), set()).add(r["id"])
    out, renames = [], {}
    for sid in order:
        g = []
        for r in groups[sid]:
            if r not in g:
                g.append(r)
        if len(groups[sid]) > len(g):
            report.append(f"{SOURCES}: {sid}: removed {len(groups[sid]) - len(g)} exact duplicate row(s)")
        if len(g) > 1 and base_rows is not None and sid in base_rows:
            strip = lambda r: {k: v for k, v in r.items() if k != "used_in"}  # noqa: E731
            edited = [r for r in g if strip(r) != strip(base_rows[sid])]
            if edited and len(edited) < len(g):
                report.append(f"{SOURCES}: {sid}: dropped the unedited base copy of the row")
                g = edited
        urls = {}
        for r in g:
            urls.setdefault(kbid.normalize_url(r["url"]), []).append(r)
        if len(urls) == 1:
            if len(g) > 1:
                report.append(f"{SOURCES}: {sid}: merged {len(g)} rows")
            out.append(merge_rows(sid, g, report))
            continue
        # a real collision: one id, several urls
        if kbid.is_hash_id(sid):
            raise Problem(f"{SOURCES}: hash id {sid} names {len(urls)} urls: {' | '.join(sorted(urls))}")
        if base_rows is None:
            raise Problem(f"{SOURCES}: {sid} names {len(urls)} different urls (two branches took the same id); "
                          f"rerun with --base <merge-base> so the new one(s) can be renumbered")
        keep = kbid.normalize_url(base_rows[sid]["url"]) if sid in base_rows else None
        for u, rs in urls.items():
            row = merge_rows(sid, rs, report)
            if u == keep:
                out.append(row)
                continue
            other = sorted(by_url.get(u, set()) - {sid}, key=id_key)
            new = other[0] if other else kbid.source_id(u)
            owners = [name for name, srows in sides.items() if srows.get(sid) and kbid.normalize_url(srows[sid]["url"]) == u]
            renames.setdefault(sid, []).append((u, new, owners))
            if not other:
                out.append({**row, "id": new})
            report.append(f"{SOURCES}: {sid} collision: {u} -> {new}" + (" (its existing id)" if other else " (hash id)"))
    if len({r["id"] for r in out}) != len(out):
        dup = sorted({r["id"] for r in out if sum(1 for x in out if x["id"] == r["id"]) > 1})
        raise Problem(f"{SOURCES}: renumbering produced duplicate ids {', '.join(dup)}")
    return header, sorted(out, key=lambda r: id_key(r["id"])), renames


# ---------------------------------------------------------------- citations of renumbered ids

def cite_count(text, sid):
    return len(re.findall(rf"(?<![\w-]){re.escape(sid)}(?![\w-])", text or ""))


def citing_files(sid):
    """Text files outside tools/config that may cite a source id: content files and root ledgers."""
    out = [f for f in build_index.content_files()]
    out += sorted(f for f in os.listdir(KB) if f.endswith((".md", ".csv")) and f not in (SOURCES, STATE, "_coverage.csv"))
    out += [build_index.EXTRA]
    return [f for f in out if cite_count(read(f) if os.path.isfile(os.path.join(KB, f)) else "", sid)]


def rewrite_citations(renames, base_rev, base_ids, side_revs, texts, pinned, problems, report):
    """Apply renames to texts {path: text} (loaded on demand), line by line: a merge (union or not) keeps each
    side's lines verbatim, so a line citing the id that only one side's version of the file has belongs to that
    side. A line both sides have, or that neither has, is ambiguous and goes to problems."""
    for sid, targets in renames.items():
        by_side = {o: new for url, new, owners in targets for o in owners}
        kept = sid in base_ids  # the id still names its base url
        for f in citing_files(sid):
            cur = texts.get(f) if f in texts else read(f)
            base_lines = set((show(base_rev, f) or "").splitlines())
            side_lines = {s: set((show(rev, f) or "").splitlines()) for s, rev in side_revs.items()}
            lines, n, bad = cur.split("\n"), 0, False
            for k, ln in enumerate(lines):
                if not cite_count(ln, sid):
                    continue
                if ln in base_lines:
                    if not kept:
                        problems.append(f"{f}:{k + 1} cited {sid} before the merge, when it named no source")
                        bad = True
                    continue
                want = sorted({by_side.get(s, sid) for s, sl in side_lines.items() if ln in sl})
                if len(want) != 1:
                    problems.append(f"{f}:{k + 1}: cannot tell which url {sid} means here "
                                    + (f"(the line is on several sides: {', '.join(want)})" if want else "(no side has this line)"))
                    bad = True
                    continue
                if want[0] != sid:
                    lines[k] = re.sub(rf"(?<![\w-]){re.escape(sid)}(?![\w-])", want[0], ln)
                    n += 1
            if n and f in pinned:
                problems.append(f"{f} is a pinned artifact citing {sid}; not rewritten")
            elif n and not bad:
                texts[f] = "\n".join(lines)
                report.append(f"{f}: {sid} renumbered on {n} line(s)")


# ---------------------------------------------------------------- _fetch_state.csv

def resolve_state(text, renames, report):
    text, n = strip_markers(lf(text), STATE)
    if n:
        report.append(f"{STATE}: dropped markers of {n} conflict region(s) (union)")
    header, rows, dropped = parse_csv(text, STATE, ("id", "checked_utc", "fetched_utc"))
    if dropped:
        report.append(f"{STATE}: removed {dropped} repeated header line(s)")
    for r in rows:
        for url, new, _ in renames.get(r["id"], []):
            if kbid.normalize_url(r.get("url", "")) == url:
                report.append(f"{STATE}: {r['id']} -> {new} (by url)")
                r["id"] = new
    groups = {}
    for r in rows:
        groups.setdefault(r["id"], []).append(r)
    out = []
    for sid, g in groups.items():
        if len(g) == 1:
            out.append(g[0])
            continue
        checked = max(g, key=lambda r: r.get("checked_utc", ""))
        fetched = max(g, key=lambda r: r.get("fetched_utc", ""))
        row = dict(checked)
        for c in ("fetched_utc", "sha256", "text_sha256", "bytes"):
            if c in row:
                row[c] = fetched.get(c, "")
        if "changed_utc" in row:
            row["changed_utc"] = max(r.get("changed_utc", "") for r in g)
        report.append(f"{STATE}: {sid}: merged {len(g)} rows (latest check {row.get('checked_utc')})")
        out.append(row)
    return csv_text(header, sorted(out, key=lambda r: id_key(r["id"])))


# ---------------------------------------------------------------- Markdown ledgers

HEADING = re.compile(r"^(#{1,6}) ")
ITEM = re.compile(r"^(?:[-*+]|\d+[.)]) ")
TABLE_SEP = re.compile(r"^\|[\s:|-]+\|?\s*$")


def fences(lines):
    inside, out = False, []
    for ln in lines:
        if ln.lstrip().startswith("```"):
            out.append(True)
            inside = not inside
        else:
            out.append(inside)
    return out


def split_at(lines, fence, level):
    """Chunks of lines, a new chunk at every heading of `level` or higher outside code fences."""
    chunks, cur = [], []
    for ln, f in zip(lines, fence):
        m = HEADING.match(ln)
        if m and not f and len(m.group(1)) <= level and cur:
            chunks.append(cur)
            cur = []
        cur.append((ln, f))
    if cur:
        chunks.append(cur)
    return chunks


def dedupe_chunks(chunks, what, report):
    seen, out = set(), []
    for c in chunks:
        key = "\n".join(ln for ln, _ in c).rstrip("\n ")
        if HEADING.match(c[0][0]) and not c[0][1] and key in seen:
            report.append(f"{what}: removed a duplicate section {c[0][0][:60]!r}")
            continue
        seen.add(key)
        out.append(c)
    return out


def dedupe_items(chunk, what, report):
    """Drop list items repeated in this section and rows repeated in one table."""
    out, seen_items, seen_rows, i = [], set(), set(), 0
    while i < len(chunk):
        ln, f = chunk[i]
        if not f and ln.startswith("|"):
            if ln in seen_rows and not TABLE_SEP.match(ln):
                report.append(f"{what}: removed a duplicate table row {ln[:60]!r}")
            else:
                seen_rows.add(ln)
                out.append(chunk[i])
            i += 1
            continue
        if not ln.startswith("|"):
            seen_rows = set()
        if f or not ITEM.match(ln):
            out.append(chunk[i])
            i += 1
            continue
        j = i + 1
        while j < len(chunk) and chunk[j][0].strip() and not chunk[j][1] and not HEADING.match(chunk[j][0]) \
                and not ITEM.match(chunk[j][0]) and not chunk[j][0].startswith("|") and not chunk[j][0].lstrip().startswith("```"):
            j += 1
        key = "\n".join(ln for ln, _ in chunk[i:j])
        if key in seen_items and len(key) >= MIN_ITEM:
            report.append(f"{what}: removed a duplicate item {ln[:60]!r}")
            if j < len(chunk) and not chunk[j][0].strip() and (not out or not out[-1][0].strip()):
                j += 1
        else:
            seen_items.add(key)
            out.extend(chunk[i:j])
        i = j
    return out


def resolve_md(text, name, report, problems):
    text, n = strip_markers(lf(text), name)
    if n:
        report.append(f"{name}: dropped markers of {n} conflict region(s) (union)")
    lines = text.split("\n")
    fence = fences(lines)
    kept = []
    for sec in dedupe_chunks(split_at(lines, fence, 2), name, report):
        subs = dedupe_chunks(split_at([ln for ln, _ in sec], [f for _, f in sec], 3), name, report)
        for sub in subs:
            kept.extend(dedupe_items(sub, name, report))
    out = "\n".join(ln for ln, _ in kept)
    if name == "_answers.md":
        ids = kbid.answer_ids(out)
        for d in sorted({i for i in ids if ids.count(i) > 1}):
            problems.append(f"{name}: answer id {d} appears {ids.count(d)} times with different text; "
                            f"keep one (or give the other a new id: kbid.py answer)")
    return out


# ---------------------------------------------------------------- lint baseline, .gitattributes

def lint_errors():
    p = subprocess.run([sys.executable, os.path.join(KB, LINT)], cwd=KB, capture_output=True, text=True, errors="replace")
    return {ln.strip() for ln in (p.stdout + p.stderr).splitlines() if ln.startswith("ERROR")}


def resolve_baseline(text, report):
    """None when the baseline was not touched by a merge, else its new text."""
    stripped, n = strip_markers(lf(text), BASELINE)
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if not n and lines == sorted(set(lines)):
        return None
    now = lint_errors()
    keep = sorted(set(lines) & now)
    report.append(f"{BASELINE}: merged; {len(keep)} known lint errors still present, "
                  f"{len(set(lines)) - len(keep)} fixed ones dropped")
    new = now - set(lines)
    if new:
        report.append(f"WARN {BASELINE}: {len(new)} current lint error(s) were accepted by neither side; "
                      f"fix them, or accept them with python3 _tools/tests.py --write-lint-baseline")
    return "".join(e + "\n" for e in keep)


def pinned_paths(artifacts_text):
    return [r["path"] for r in csv.DictReader(io.StringIO(lf(artifacts_text or "")))] if artifacts_text else []


def resolve_attrs(text, pinned):
    """.gitattributes with its pinned block regenerated from _artifacts.csv (None if the file has no block)."""
    if text is None or PIN_START not in text or PIN_END not in text:
        return None
    for p in pinned:
        if re.search(r"[\s*?\[\]\\!#\"]", p):
            raise Problem(f"{ARTIFACTS}: path {p!r} cannot be written to .gitattributes as-is")
    i, j = text.index(PIN_START), text.index(PIN_END)
    head = text[:i].rstrip("\n") + "\n" if text[:i].strip() else ""
    block = PIN_START + "\n" + "".join(f"{p} -text\n" for p in sorted(set(pinned))) + PIN_END
    return head + block + text[j + len(PIN_END):]


# ---------------------------------------------------------------- commands

def canon_csv(text, sort):
    """csv-module quoting, `\n`, no BOM, no blank records; rows sorted by id (first column) when `sort`."""
    rows = [r for r in csv.reader(io.StringIO(lf(text))) if r]
    if not rows:
        return text
    body = sorted(rows[1:], key=lambda r: id_key(r[0])) if sort else rows[1:]
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows([rows[0]] + body)
    return buf.getvalue()


def fmt_texts(report):
    """Canonical CSV ledgers without changing the set of rows: {path: new text}."""
    out = {}
    for name, sort in ((SOURCES, True), (STATE, True), (ARTIFACTS, False)):
        text = read(name)
        if text is None:
            continue
        if has_markers(text):
            raise Problem(f"{name} has conflict markers; run kbgit.py fix")
        out[name] = canon_csv(text, sort)
    attrs = resolve_attrs(read(ATTRS), pinned_paths(read(ARTIFACTS)))
    if attrs is not None:
        out[ATTRS] = attrs
    return out


def fix_texts(a, report, problems):
    out = {}
    base = None
    base_rows = None
    if a.base:
        rev = (git("rev-parse", "--verify", "-q", a.base + "^{commit}") or "").strip()
        if not rev:
            raise Problem(f"--base {a.base}: not a commit here (is this a git clone?)")
        base = {"rev": rev}
        bt = show(rev, SOURCES)
        base_rows = {r["id"]: r for r in parse_csv(lf(bt), f"{a.base}:{SOURCES}")[1]} if bt else {}
    side_revs = {}
    for s in merge_sides(a.side):
        rev = (git("rev-parse", "--verify", "-q", s + "^{commit}") or "").strip()
        if not rev:
            raise Problem(f"--side {s}: not a commit here")
        side_revs[s[:12]] = rev
    side_rows = {}
    for name, rev in side_revs.items():
        st = show(rev, SOURCES)
        side_rows[name] = {r["id"]: r for r in parse_csv(lf(st), f"{name}:{SOURCES}")[1]} if st else {}

    text = read(SOURCES)
    if text is None:
        raise Problem(f"cannot read {SOURCES}")
    header, rows, renames = resolve_sources(text, base_rows, side_rows, report)
    if renames:
        if not side_revs:
            raise Problem("ids were renumbered but the merge's sides are unknown (not in a merge, HEAD is no merge commit); "
                          "pass --side REV for each merged branch")
        for sid, targets in renames.items():
            for url, new, owners in targets:
                if not owners:
                    problems.append(f"{SOURCES}: no side of the merge has {sid} -> {url}; cannot attribute its citations")
        # superseded_by pointing at a renumbered id: resolve like a citation, per row
        for r in rows:
            sup = r.get("superseded_by", "")
            if sup in renames:
                intro = sorted({new for url, new, owners in renames[sup] for o in owners
                                if side_rows[o].get(r["id"], {}).get("superseded_by") == sup
                                and (base_rows or {}).get(r["id"], {}).get("superseded_by") != sup})
                if len(intro) == 1:
                    report.append(f"{SOURCES}: {r['id']} superseded_by {sup} -> {intro[0]}")
                    r["superseded_by"] = intro[0]
                elif sup not in (base_rows or {}):
                    problems.append(f"{SOURCES}: {r['id']} superseded_by {sup}: cannot tell which url it means")
    out[SOURCES] = csv_text(header, rows)
    pinned = set(pinned_paths(read(ARTIFACTS)))
    if renames:
        rewrite_citations(renames, base["rev"], set(base_rows), side_revs, out, pinned, problems, report)

    st = read(STATE)
    if st is not None:
        out[STATE] = resolve_state(out.get(STATE, st), renames, report)
    for name in MD_LEDGERS:
        t = out.get(name, read(name))
        if t is not None:
            out[name] = resolve_md(t, name, report, problems)
    for name in ("_coverage.csv",):
        t = read(name)
        if t is not None and has_markers(t):
            out[name] = strip_markers(t, name)[0]  # rebuilt below anyway
            report.append(f"{name}: conflict markers dropped; regenerated")
    bl = read(BASELINE)
    if bl is not None:
        new = resolve_baseline(bl, report)
        if new is not None:
            out[BASELINE] = new
    arts = read(ARTIFACTS)
    if arts is not None:
        if has_markers(arts):
            problems.append(f"{ARTIFACTS} has conflict markers; resolve them by hand (pinned sha256 values)")
        else:
            out[ARTIFACTS] = canon_csv(arts, sort=False)
            attrs = resolve_attrs(read(ATTRS), pinned_paths(arts))
            if attrs is not None:
                out[ATTRS] = attrs
    return out


def run(a):
    report, problems = [], []
    try:
        out = fmt_texts(report) if a.cmd == "fmt" else fix_texts(a, report, problems)
        if a.cmd == "fix" and not problems:
            try:
                result, _, warnings = build_index.build(out)
            except build_index.BuildError as e:
                raise Problem(f"build_index: {e}")
            for p, (_, new) in result.items():
                out[p] = new
            if has_markers(out["README.md"]):
                problems.append("README.md has conflict markers outside the coverage table; resolve them by hand")
            for f in build_index.content_files():
                t = out.get(f)
                if t is None and f.endswith((".md", ".csv", ".yaml", ".yml", ".json")):
                    t = build_index.read(f)
                if has_markers(t):
                    problems.append(f"{f} has conflict markers; resolve them by hand")
    except Problem as e:
        problems.append(str(e))
    if problems:
        for ln in report:
            print(ln if ln.startswith("WARN") else "  " + ln)
        for p in problems:
            print("PROBLEM", p)
        print(f"problems={len(problems)}: nothing written; resolve them (or pass --base/--side) and rerun")
        return 2
    changed = [p for p, t in out.items() if read(p) != t]
    for ln in report:
        print(ln if ln.startswith("WARN") else "  " + ln)
    if a.check:
        for p in changed:
            print("WOULD CHANGE", p)
        print(f"{a.cmd}: changed={len(changed)}" + (f" (run python3 _tools/kbgit.py {a.cmd})" if changed else ""))
        return 1 if changed else 0
    for p in changed:
        write(p, out[p])
        print("wrote", p)
    unmerged = sorted(set((git("diff", "--name-only", "--diff-filter=U") or "").split()))
    if unmerged:
        print("unmerged in the index (check, then `git add` them): " + " ".join(unmerged))
    print(f"{a.cmd}: changed={len(changed)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fix", help="post-merge cleanup of the ledgers, then build_index.py")
    f.add_argument("--check", action="store_true", help="write nothing; exit 1 if fix would change something")
    f.add_argument("--base", help="the merge base (git merge-base A B); needed to renumber colliding legacy ids")
    f.add_argument("--side", action="append", default=[], help="a merged branch/commit (repeatable; default: MERGE_HEAD or HEAD's parents)")
    m = sub.add_parser("fmt", help="canonical CSV quoting, order and newlines of the ledgers")
    m.add_argument("--check", action="store_true", help="write nothing; exit 1 if fmt would change something")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()
