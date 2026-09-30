"""The merge and ledger repair of kbgit.py (kb/_self/git.md): `kbgit.py fix` and `fmt`. Reads and writes through git and
the working tree, resolves the _sources.csv, _fetch_state.csv, _anchors.csv and Markdown ledgers a merge left
(conflict markers, duplicates, colliding ids and the citations of renumbered ones), the lint baseline and the pinned
block of .gitattributes, then rebuilds each root's generated files. Standard library only; kbgit.py imports it and runs
`run` for both commands; it imports no facade.
"""
import csv, io, os, re, subprocess, sys
from collections import Counter

import kbcommon, kbid
import build_index
import ql_store
import kg_base
from kg_base import BASELINE, Problem, repo_roots

ROOT = kbcommon.PUBLIC  # the root fix and the history commands work on now (use_root); the public root by default
CUR = None  # its kbcommon.Root; None: the public root, before roots() was read


def R(rel):
    """A path relative to the current root (ROOT) as a repository path (what git takes and prints)."""
    return kbcommon.repo_rel(rel, ROOT)


def cur_root():
    return CUR or kbcommon.public()


def use_root(r):
    """Point ROOT and the ledger paths (SOURCES, STATE, ARTIFACTS, ANSWERS, COVERAGE, MD_LEDGERS) at root r."""
    global ROOT, CUR, SOURCES, STATE, ARTIFACTS, ANSWERS, COVERAGE, MD_LEDGERS
    ROOT, CUR = r.path, r
    SOURCES, STATE, ARTIFACTS = R(kbcommon.SOURCES), R(kbcommon.STATE), R(kbcommon.ARTIFACTS)
    ANSWERS, COVERAGE = R(kbcommon.ANSWERS), R(kbcommon.COVERAGE_CSV)
    MD_LEDGERS = (ANSWERS, R(kbcommon.GAPS), R(kbcommon.CONFLICTS))


def bi_root():
    """The root build_index works on for the current root."""
    return ROOT


def bi(fn, *args, **kw):
    """build_index's fn for the current root."""
    return fn(*args, root=cur_root(), **kw)


def FB(path):
    """A path build_index names (relative to the root it reads) as a repository path."""
    return kbcommon.repo_rel(path, bi_root())


def B(path):
    """A repository path as build_index names it: relative to the root it reads (may climb out with `..`)."""
    return os.path.relpath(os.path.join(kg_base.KB, path), bi_root()).replace(os.sep, "/")


SOURCES, STATE, ARTIFACTS = R(kbcommon.SOURCES), R(kbcommon.STATE), R(kbcommon.ARTIFACTS)
ANSWERS, COVERAGE = R(kbcommon.ANSWERS), R(kbcommon.COVERAGE_CSV)
MD_LEDGERS = (ANSWERS, R(kbcommon.GAPS), R(kbcommon.CONFLICTS))
ATTRS = ".gitattributes"
LINT = os.path.join(".claude", "skills", "kb-verify", "lint.py")
PIN_START, PIN_END = "# pinned:start", "# pinned:end"
MIN_ITEM = 20  # shorter list items (`- none`) may repeat on purpose


# ---------------------------------------------------------------- io and git
# The repository is kg_base.KB. read, git_run, git and show take `kb`, another directory, for a caller that runs its
# own commands elsewhere (kbgit.py passes its KB).

def read(rel, kb=None):
    return kbcommon.read(os.path.join(kb or kg_base.KB, rel), newline="", strict=True)


def write(rel, text):
    with open(os.path.join(kg_base.KB, rel), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def git_run(*args, stdin=None, kb=None):
    """The finished git process (bytes output), or None when git cannot be started."""
    try:
        return subprocess.run(["git", *args], cwd=kb or kg_base.KB, capture_output=True, input=stdin)
    except OSError:
        return None


def git(*args, stdin=None, kb=None):
    """stdout of a git command in the kb, or None when git or the object is unavailable."""
    p = git_run(*args, stdin=stdin, kb=kb)
    return p.stdout.decode("utf-8", "replace") if p is not None and p.returncode == 0 else None


def show(rev, rel, kb=None):
    # cat-file, not show: `git show REV:PATH` checks its argument as a file name, which fails as "Filename too long"
    # on Windows in a deep checkout
    return git("cat-file", "blob", f"{rev}:./{rel}", kb=kb)


def merge_sides(given):
    if given:
        return given
    head = (git("rev-parse", "-q", "--verify", "HEAD") or "").strip()
    mh = read(os.path.join(".git", "MERGE_HEAD")) if os.path.isdir(os.path.join(kg_base.KB, ".git")) else None
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


csv_text = kbcommon.csv_text


def parse_csv(text, name, required=("id",)):
    """(header, rows as dicts, repeated header lines dropped) of a ledger; Problem on a malformed row."""
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r]
    if not rows:
        raise Problem(f"{name}: empty")
    header = rows[0]
    out, dropped = [], 0
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

MERGE_CONFLICT = ("title", "publisher", "licence", "reuse", "artifact_sha256")


def merge_rows(sid, rows, report):
    """One row from rows that share an id and a normalized url."""
    rows = sorted(rows, key=lambda r: r.get("retrieved_utc", ""), reverse=True)  # stable otherwise
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


def resolve_sources(text, base_rows, sides, report, upstream=None):
    """(header, rows, renames) where renames = {old id: [(url, new id, side names), ...]}. `upstream` names the side
    in `sides` that is already pushed: on a collision of an id the base did not have, its url keeps the id."""
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
    out, renames, dups, stale, merged = [], {}, [], [], []
    strip = lambda r: {k: v for k, v in r.items() if k != "used_in" and v}  # noqa: E731  (a missing column = empty)
    for sid in order:
        g = []
        for r in groups[sid]:
            if r not in g:
                g.append(r)
        if len(groups[sid]) > len(g):
            dups.append(sid)
        if len(g) > 1 and base_rows is not None and sid in base_rows:
            edited = [r for r in g if strip(r) != strip(base_rows[sid])]
            if edited and len(edited) < len(g):
                stale.append(sid)
                g = edited
        urls = {}
        for r in g:
            urls.setdefault(kbid.normalize_url(r["url"]), []).append(r)
        if len(urls) == 1:
            if len(g) > 1:
                merged.append(sid)
            out.append(merge_rows(sid, g, report))
            continue
        # a real collision: one id, several urls
        if kbid.is_hash_id(sid) or not re.fullmatch(kbid.LEGACY_ID, sid):  # only S has legacy ids to renumber
            raise Problem(f"{SOURCES}: hash id {sid} names {len(urls)} urls: {' | '.join(sorted(urls))}")
        if base_rows is None:
            raise Problem(f"{SOURCES}: {sid} names {len(urls)} different urls (two branches took the same id); "
                          f"rerun with --base <merge-base> so the new one(s) can be renumbered")
        keep = kbid.normalize_url(base_rows[sid]["url"]) if sid in base_rows else None
        if keep is None and upstream and sid in sides.get(upstream, {}):
            keep = kbid.normalize_url(sides[upstream][sid]["url"])  # already pushed: never renumbered
            report.append(f"{SOURCES}: {sid}: the pushed side ({upstream}) keeps the id")
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
    for ids, what in ((dups, "removed exact duplicate rows"), (stale, "dropped the unedited base copy of the row"),
                      (merged, "merged the rows")):
        if ids:
            report.append(f"{SOURCES}: {what} of {len(ids)} id(s): {', '.join(ids[:8])}" + (", ..." if len(ids) > 8 else ""))
    if len({r["id"] for r in out}) != len(out):
        dup = sorted({r["id"] for r in out if sum(1 for x in out if x["id"] == r["id"]) > 1})
        raise Problem(f"{SOURCES}: renumbering produced duplicate ids {', '.join(dup)}")
    return header, sorted(out, key=lambda r: id_key(r["id"])), renames


# ---------------------------------------------------------------- citations of renumbered ids

MARKER_LINE = re.compile(r"(<<<<<<<|>>>>>>>|\|\|\|\|\|\|\|)( |$)")


def cite_count(text, sid):
    return len(re.findall(rf"(?<![\w-]){re.escape(sid)}(?![\w-])", text or ""))


def id_files():
    """Text files of the current root that may cite a source id or name an answer id: its content files and ledgers
    (`_*.md`, `_*.csv`); a root cites only its own sources. README.md, AGENTS.md and the tools mention ids only as
    examples and are never rewritten."""
    out = [FB(f) for f in bi(build_index.content_files) or []]
    out += sorted(R(f) for f in os.listdir(ROOT) if f.startswith("_") and f.endswith((".md", ".csv"))
                  and R(f) not in (SOURCES, STATE, COVERAGE))
    out += [R(kbcommon.data_rel("index_extra.csv"))]
    return [f for f in out if os.path.isfile(os.path.join(kg_base.KB, f))]


def source_plan(renames, rows):
    """rewrite_ids plan for renumbered source ids: each side's lines get the id of that side's url."""
    kept = {r["id"] for r in rows}
    return {sid: {"by_side": {o: new for url, new, owners in targets for o in owners}, "default": None,
                  "strict_base": sid not in kept, "what": "url"} for sid, targets in renames.items()}


def rewrite_ids(plan, base_rev, side_revs, texts, pinned, problems, report):
    """Apply id renames to texts {path: text} (loaded on demand), line by line. A merge (union or not) keeps each
    side's lines verbatim, so a line naming an id that only one side's version of the file has belongs to that side
    and gets that side's new id. A line no side has (written while resolving a conflict) belongs to the one side
    whose version of the file names the id at all. A line both sides have, or still no side, is ambiguous and goes
    to problems.
    A plan entry with a `default` (a single new id; the old one names nothing any more) renames it on every line the
    base did not have, except lines a side outside its `owners` has (e.g. the pushed side's own text). Lines are
    attributed on their text before any rename, so one line may carry several ids.
    plan = {old id: {"by_side": {side: new id}, "default": new id or None, "owners": sides the default applies to,
    "strict_base": a base line naming the old id is an error, "what": noun for messages}}."""
    if not plan:
        return
    rx = {old: re.compile(rf"(?<![\w-]){re.escape(old)}(?![\w-])") for old in plan}
    for f in id_files():
        cur = texts.get(f) if f in texts else read(f)
        if not cur or not any(r.search(cur) for r in rx.values()):
            continue
        base_lines = set((show(base_rev, f) or "").splitlines()) if base_rev else set()
        side_text = {s: show(rev, f) or "" for s, rev in side_revs.items()}
        side_lines = {s: set(st.splitlines()) for s, st in side_text.items()}
        lines, n, bad = cur.split("\n"), {}, False
        for k, ln in enumerate(lines):
            if MARKER_LINE.match(ln):
                continue  # a conflict marker line carries a commit subject, not a citation
            new_ln = ln
            for old, p in plan.items():
                if not rx[old].search(ln):
                    continue
                if ln in base_lines:
                    if p["strict_base"]:
                        problems.append(f"{f}:{k + 1} cited {old} before the merge, when it named no source")
                        bad = True
                    continue
                on = [s for s, sl in side_lines.items() if ln in sl]
                if p["default"]:
                    if any(s not in p.get("owners", ()) for s in on):
                        continue  # a line of a side without the renamed answer: it means something else
                    want = [p["default"]]
                else:
                    if not on:  # a line no side has (a resolved conflict): the side whose file cites the id at all
                        on = [s for s, st in side_text.items() if cite_count(st, old)]
                    want = sorted({p["by_side"].get(s, old) for s in on})
                if len(want) != 1:
                    problems.append(f"{f}:{k + 1}: cannot tell which {p['what']} {old} means here "
                                    + (f"(the line is on several sides: {', '.join(want)})" if want else "(no side has this line)"))
                    bad = True
                    continue
                if want[0] != old:
                    new_ln = rx[old].sub(lambda _m, w=want[0]: w, new_ln)
                    n[old] = n.get(old, 0) + 1
            lines[k] = new_ln
        if n and f in pinned:
            problems.append(f"{f} is a pinned artifact naming {', '.join(sorted(n))}; not rewritten")
        elif n and not bad:
            texts[f] = "\n".join(lines)
            for old, c in sorted(n.items()):
                report.append(f"{f}: {old} renumbered on {c} line(s)")


# ---------------------------------------------------------------- answer ids

def answer_heads(text):
    """[(id, heading line, question)] of the `## <ID>. <question>` headings of _answers.md, in order."""
    out = []
    for ln in (text or "").split("\n"):
        m = kbid.ANSWER_HEAD.match(ln)
        if m:
            out.append((m.group(1), ln, ln[m.end():].strip()))
    return out


def answer_plan(text, base_text, upstream_text, side_texts, report, problems):
    """rewrite_ids plan for _answers.md ids a merge left doubled: one id heading several different questions (two
    branches took the same id). The heading the base or the pushed side (`upstream_text`) already has keeps the id,
    else the first one; the others get new ids (kbid.answer_id(question), made unique with -2, -3...), and each line
    naming the id gets the id of the question on its side (`side_texts` {side: _answers.md text}).
    An id whose headings are identical is left to resolve_md (verbatim duplicates dropped, different bodies: a human)."""
    heads = answer_heads(strip_markers(lf(text or ""), ANSWERS)[0])
    protected = {ln for _, ln, _ in answer_heads(base_text) + answer_heads(upstream_text)}
    taken = {i for i, _, _ in heads}
    lines_of = {}
    for aid, ln, q in heads:
        lines_of.setdefault(aid, {}).setdefault(ln, q)
    plan = {}

    def fresh(question):
        cand = kbid.answer_id(question)
        new, k = cand, 2
        while new in taken:
            new, k = f"{cand}-{k}", k + 1
        taken.add(new)
        return new

    for aid, hl in lines_of.items():
        if len(hl) == 1:
            continue
        prot = [ln for ln in hl if ln in protected]
        if len(prot) > 1:
            problems.append(f"_answers.md: {aid} heads {len(prot)} different published questions; resolve by hand")
            continue
        keep = prot[0] if prot else next(iter(hl))
        renamed = {ln: fresh(q) for ln, q in hl.items() if ln != keep}
        by_side = {}
        for ln, new in renamed.items():
            owners = [s for s, t in side_texts.items() if ln in (t or "").split("\n")]
            if not owners:
                problems.append(f"_answers.md: no side of the merge has the heading {ln[:60]!r}; cannot rename {aid}")
            for o in owners:
                if o in by_side:
                    problems.append(f"_answers.md: side {o} has {aid} twice; resolve by hand")
                by_side[o] = new
            report.append(f"_answers.md: {aid} collision: {ln[len(aid) + 5:][:50]!r} -> {new}")
        plan[aid] = {"by_side": by_side, "default": None, "strict_base": False, "what": "answer"}
    return plan


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
        detected = max(g, key=lambda r: r.get("detected_utc", ""))  # factdiff.py detect's columns travel together
        for c in ("etag", "last_modified", "version", "doc_sha256", "final_url", "http_status", "simhash", "detected_utc"):
            if c in row:
                row[c] = detected.get(c, "")
        if "changed_utc" in row:
            row["changed_utc"] = max(r.get("changed_utc", "") for r in g)
        report.append(f"{STATE}: {sid}: merged {len(g)} rows (latest check {row.get('checked_utc')})")
        out.append(row)
    return csv_text(header, sorted(out, key=lambda r: id_key(r["id"])))


def resolve_anchors(text, renames, report):
    """_anchors.csv after a union merge: markers dropped, one row per (fact, path, source_id), the one found last
    (verified_utc; a located row over an unlocated one on the same day); a source id kbgit renamed follows its one
    new id."""
    name = R(kbcommon.ANCHORS)
    text, n = strip_markers(lf(text), name)
    if n:
        report.append(f"{name}: dropped markers of {n} conflict region(s) (union)")
    header, rows, dropped = parse_csv(text, name, ("fact", "path", "source_id", "status", "verified_utc"))
    if dropped:
        report.append(f"{name}: removed {dropped} repeated header line(s)")
    best = {}
    for r in rows:
        new = renames.get(r["source_id"], [])
        if len(new) == 1:
            r["source_id"] = new[0][1]
        k = (r["fact"], r["path"], r["source_id"])
        rank = (r.get("verified_utc", ""), r.get("status") == "located")
        if k not in best or rank > best[k][0]:
            if k in best:
                report.append(f"{name}: {k[2]} {k[1]} {k[0]}: kept the row of {rank[0]}")
            best[k] = (rank, r)
    return csv_text(header, sorted((r for _, r in best.values()), key=lambda r: (r["path"], r["fact"], id_key(r["source_id"]))))


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


ANY_ID = re.compile(r"(?<![\w-])(?:S\d+|S-[a-z2-7]{8}|QK[\w-]*)(?![\w-])")


def repair_splices(text, name, side_texts, report):
    """Undo git's "zealous" interleaving of two blocks added at one place (see MERGE_CFG). When both blocks end with the
    same lines (every kb-research answer ends in `_Agent: kb-research_`), the merge keeps those lines once, at the end
    of the second block: the first `##` section loses its tail. Signature: a merged section that is a strict prefix of
    its own version on one side, whose missing lines end the next merged section. The tail is copied back from there
    (lines already renumbered by fix), so the first section is whole again. Ids are ignored when comparing, as fix may
    have renamed them. side_texts: the ledger's text on each side of the merge."""
    def norm(lines):
        return [ANY_ID.sub("<id>", ln) for ln in lines]

    def trim(lines):
        lines = list(lines)
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    def key(ln):
        m = kbid.ANSWER_HEAD.match(ln)
        return ln[m.end():].strip() if m else ANY_ID.sub("<id>", ln)

    side_secs = []
    for t in side_texts:
        if not t:
            continue
        ls = strip_markers(lf(t), name)[0].split("\n")
        secs = {}
        for c in split_at(ls, fences(ls), 2):
            if HEADING.match(c[0][0]) and not c[0][1]:
                secs.setdefault(key(c[0][0]), norm(trim(ln for ln, _ in c)))
        side_secs.append(secs)
    if not side_secs:
        return text
    lines = text.split("\n")
    chunks = [[ln for ln, _ in c] for c in split_at(lines, fences(lines), 2)]
    heads = [HEADING.match(c[0]) and len(HEADING.match(c[0]).group(1)) == 2 for c in chunks]
    fixed = 0
    for i in range(len(chunks) - 1):
        if not heads[i] or not heads[i + 1]:
            continue
        cur, nxt = trim(chunks[i]), trim(chunks[i + 1])
        for secs in side_secs:
            want = secs.get(key(chunks[i][0]))
            if not want or len(want) <= len(cur) or want[:len(cur)] != norm(cur):
                continue
            tail = want[len(cur):]
            while tail and not tail[0].strip():
                tail = tail[1:]
            if not tail or len(nxt) <= len(tail) or norm(nxt[-len(tail):]) != tail:
                continue
            gap = len(want) - len(cur) - len(tail)
            chunks[i] = cur + [""] * gap + nxt[-len(tail):] + (chunks[i][len(cur):] or [""])
            fixed += 1
            report.append(f"{name}: restored {len(tail)} line(s) a merge moved out of {chunks[i][0][:60]!r}")
            break
    return "\n".join(ln for c in chunks for ln in c) if fixed else text


def resolve_md(text, name, report, problems, side_texts=()):
    text, n = strip_markers(lf(text), name)
    if n:
        report.append(f"{name}: dropped markers of {n} conflict region(s) (union)")
    text = repair_splices(text, name, side_texts, report)
    lines = text.split("\n")
    fence = fences(lines)
    kept = []
    for sec in dedupe_chunks(split_at(lines, fence, 2), name, report):
        subs = dedupe_chunks(split_at([ln for ln, _ in sec], [f for _, f in sec], 3), name, report)
        for sub in subs:
            kept.extend(dedupe_items(sub, name, report))
    out = "\n".join(ln for ln, _ in kept)
    if name == ANSWERS:
        ids = kbid.answer_ids(out)
        for d, n in sorted(Counter(ids).items()):
            if n < 2:
                continue
            problems.append(f"{name}: answer id {d} appears {n} times with different text; "
                            f"keep one (or give the other a new id: kbid.py answer)")
    return out


# ---------------------------------------------------------------- lint baseline, .gitattributes

def lint_errors():
    p = subprocess.run([sys.executable, os.path.join(kg_base.KB, LINT)], cwd=kg_base.KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
    """The repository paths of the pinned artifacts (_artifacts.csv names them relative to the public root)."""
    return [R(r["path"]) for r in csv.DictReader(io.StringIO(lf(artifacts_text or "")))] if artifacts_text else []


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
    return kbcommon.rows_text([rows[0]] + body)


def each_root():
    """Each root of this repository in turn, made current with use_root; the previous root is current again after."""
    prev = cur_root()
    try:
        for r in repo_roots():
            use_root(r)
            yield r
    finally:
        use_root(prev)


def fmt_texts(report):
    """Canonical CSV ledgers of every root without changing the set of rows: {path: new text}."""
    out, pinned = {}, []
    for _ in each_root():
        for name, sort in ((SOURCES, True), (STATE, True), (ARTIFACTS, False)):
            text = read(name)
            if text is None:
                continue
            if has_markers(text):
                raise Problem(f"{name} has conflict markers; run kbgit.py fix")
            out[name] = canon_csv(text, sort)
        pinned += pinned_paths(read(ARTIFACTS))
    attrs = resolve_attrs(read(ATTRS), pinned)
    if attrs is not None:
        out[ATTRS] = attrs
    return out


def fix_texts(a, report, problems):
    """fix of every root's ledgers, then the lint baseline and the pinned block of .gitattributes: {path: text}."""
    out, pinned = {}, []
    for _ in each_root():
        root_out, arts = fix_root_texts(a, report, problems)
        out.update(root_out)
        pinned += pinned_paths(arts)
    bl = read(BASELINE)
    if bl is not None:
        new = resolve_baseline(bl, report)
        if new is not None:
            out[BASELINE] = new
    if not any(f"{ARTIFACTS_NAME} has conflict markers" in p for p in problems):
        attrs = resolve_attrs(read(ATTRS), pinned)
        if attrs is not None:
            out[ATTRS] = attrs
    return out


ARTIFACTS_NAME = kbcommon.ARTIFACTS


def fix_root_texts(a, report, problems):
    """fix of the current root's ledgers: ({path: text}, its _artifacts.csv text or None)."""
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
    side_revs, upstream = {}, None
    upstream_arg = getattr(a, "upstream", None)
    for s in ([upstream_arg] if upstream_arg else []) + [x for x in merge_sides(a.side) if x != upstream_arg]:
        rev = (git("rev-parse", "--verify", "-q", s + "^{commit}") or "").strip()
        if not rev:
            raise Problem(f"--{'upstream' if s == upstream_arg else 'side'} {s}: not a commit here")
        if rev in side_revs.values():
            continue
        side_revs[s[:12]] = rev
        if s == upstream_arg:
            upstream = s[:12]
    side_rows = {}
    for name, rev in side_revs.items():
        st = show(rev, SOURCES)
        side_rows[name] = {r["id"]: r for r in parse_csv(lf(st), f"{name}:{SOURCES}")[1]} if st else {}

    text = read(SOURCES)
    if text is None:
        raise Problem(f"cannot read {SOURCES}")
    header, rows, renames = resolve_sources(text, base_rows, side_rows, report, upstream)
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
    plan = source_plan(renames, rows) if renames else {}
    ans = read(ANSWERS)
    if ans is not None:
        aplan = answer_plan(ans, show(base["rev"], ANSWERS) if base else None,
                            show(side_revs[upstream], ANSWERS) if upstream else None,
                            {s: show(rev, ANSWERS) for s, rev in side_revs.items()}, report, problems)
        if any(p["by_side"] for p in aplan.values()) and not side_revs:
            problems.append("answer ids collide but the merge's sides are unknown; pass --side REV for each merged branch")
        plan.update(aplan)
    rewrite_ids(plan, base["rev"] if base else None, side_revs, out, pinned, problems, report)

    st = read(STATE)
    if st is not None:
        out[STATE] = resolve_state(out.get(STATE, st), renames, report)
    an = read(R(kbcommon.ANCHORS))
    if an is not None:
        out[R(kbcommon.ANCHORS)] = resolve_anchors(an, renames, report)
    for name in MD_LEDGERS:
        t = out.get(name, read(name))
        if t is not None:
            out[name] = resolve_md(t, name, report, problems, [show(rev, name) for rev in side_revs.values()])
    for name in (COVERAGE,):
        t = read(name)
        if t is not None and has_markers(t):
            out[name] = strip_markers(t, name)[0]  # rebuilt below anyway
            report.append(f"{name}: conflict markers dropped; regenerated")
    arts = read(ARTIFACTS)
    if arts is not None:
        if has_markers(arts):
            problems.append(f"{ARTIFACTS} has conflict markers; resolve them by hand (pinned sha256 values)")
            arts = None
        else:
            out[ARTIFACTS] = canon_csv(arts, sort=False)
    return out, arts


def rebuild_root(out, problems):
    """build_index for the current root over the fixed texts `out` (updated in place with its generated files)."""
    texts = {}
    try:
        res = bi(build_index.build, {B(p): t for p, t in out.items()}, texts_out=texts)
    except build_index.BuildError as e:
        raise Problem(f"build_index ({cur_root().name}): {e}")
    if res is None:  # an older build_index serves the public root only
        return
    for p, (_, new) in res[0].items():
        out[FB(p)] = new
    pg = bi(build_index.coverage_page, {B(p): t for p, t in out.items()})
    page = FB(pg) if pg else None
    if page in out and has_markers(out[page]):
        problems.append(f"{page} has conflict markers outside the coverage table; resolve them by hand")
    for f in bi(build_index.content_files) or []:
        t = out.get(FB(f))
        if t is None and f.endswith((".md", ".csv", ".yaml", ".yml", ".json")):
            t = texts.get(f)  # read once, by build()
        if has_markers(t):
            problems.append(f"{FB(f)} has conflict markers; resolve them by hand")


def run(a):
    report, problems = [], []
    try:
        out = fmt_texts(report) if a.cmd == "fmt" else fix_texts(a, report, problems)
        if a.cmd == "fix" and not problems:
            for _ in each_root():
                rebuild_root(out, problems)
    except Problem as e:
        problems.append(str(e))
    if a.cmd == "fix":
        problems += [f"{kbcommon.repo_rel(str(ql_store.STORE))}/{p}" for p in ql_store.duplicate_ids(ql_store.STORE)]
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
