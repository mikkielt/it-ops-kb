#!/usr/bin/env python3
"""Git helpers for the kb (stdlib only): post-merge cleanup, canonical ledger formatting, and a queryable history.

  kbgit.py fix [--check] [--base REV] [--side REV ...]   post-merge cleanup; safe to run any time, idempotent
  kbgit.py fmt [--check]                                   only canonical CSV formatting and order (never adds or drops a row)
  kbgit.py trailers [--staged | REV | --amend] [--verified YYYY-MM-DD]   the KB-* trailers of the staged change or a commit
  kbgit.py install-hooks [--uninstall]                     core.hooksPath=.githooks: commits get their KB-* trailers
  kbgit.py check-trailers [A..B | REV]                     exit 1 listing kb commits whose KB-* trailers are missing or wrong
  kbgit.py log <S-id | topic | QK-id | path> [-n N]        commits that touched it (trailers first, then diff/path history)
  kbgit.py blame <path:line>                               the commit that wrote that line, and the sources it cites
  kbgit.py asof <YYYY-MM-DD | tag | rev> <path>            the file as of the last commit on or before that date (or at the tag)
  kbgit.py tag-census YYYY-MM-DD                           annotated tag census-YYYY-MM-DD on HEAD: "kb confirmed current" (no push)
  kbgit.py sync [--push] [--dry-run] [--remote origin] [--branch main]   fetch, rebase, fix, gate, push: the way to push

History (trailers). Every commit that changes kb content ends with git trailers, so `git log` can answer "which commits
changed topic X / source S / answer QK-..." without reading diffs:
  KB-Topics:              topic ids whose article or data files changed (the topic -> files mapping of _coverage.csv at
                          both ends of the diff; an article not in it counts under its own path)
  KB-Sources-Added:       _sources.csv ids of new rows
  KB-Sources-Changed:     ids of rows edited (used_in, which is generated, is ignored) or removed
  KB-Sources-Superseded:  ids whose superseded_by became non-empty (not also listed as changed)
  KB-Answers:             _answers.md answer ids whose section was added, edited or removed
  KB-Verified: YYYY-MM-DD only on request (`trailers --verified`, or KB_VERIFIED=YYYY-MM-DD in the hook's environment, or
                          `git commit --trailer "KB-Verified: 2026-09-25"`): the commit confirms its sources are current.
One line per key, values sorted and joined by ", ". A key with more than MAX_IDS (40) values is written as a count,
e.g. `KB-Sources-Added: 312 ids (see diff)`: trailers cannot wrap, and `log` finds such commits by their diff anyway.
A commit is diffed against its first parent (the empty tree for a root commit). Merge commits carry no trailers and
are not checked: their content is attributed to the commits they merge. Commits up to TRAILERS_SINCE (the last
commit before trailers existed) are exempt; history is never rewritten.

Hooks (`install-hooks`, once per clone): sets `git config core.hooksPath .githooks` (versioned scripts). commit-msg
replaces any KB-Topics/KB-Sources-*/KB-Answers lines with the computed ones via `git interpret-trailers` (so
re-running, `-m`, editor commits and --amend never duplicate them), skips merges, skips a rebase re-application whose
message already has KB-* trailers, and never blocks a commit (any error is a warning). prepare-commit-msg only
notes an --amend so commit-msg diffs against HEAD's parent. `git commit --no-verify` skips commit-msg: CI's
check-trailers catches that. Fix unpushed commits with `trailers --amend` (HEAD) or
`git rebase --exec "python3 _tools/kbgit.py trailers --amend" @{upstream}`.

check-trailers without a range: in GitLab CI, CI_COMMIT_BEFORE_SHA..CI_COMMIT_SHA (only CI_COMMIT_SHA when the
before sha is all zeros or unknown); elsewhere @{upstream}..HEAD, or HEAD alone without an upstream.
Census tags: an annotated tag `census-YYYY-MM-DD` marks "the kb was confirmed current as of that date"; its message
counts the sources and the _fetch_state.csv checks. `asof census-2026-09-25 PATH` reads a file as of a census.

Sync (the only way to push; people push straight to main, CI is a safety net):
  a. refuses (exit 2) with uncommitted tracked changes (lists staged/unstaged: commit or stash them), or while a
     rebase/merge/cherry-pick/revert is in progress; untracked files do not count.
  b. git fetch REMOTE BRANCH; prints how far HEAD is ahead of / behind REMOTE/BRANCH.
  c. git rebase REMOTE/BRANCH (merge commits are linearised: they would carry no trailers). A step that conflicts only
     in MECHANICAL paths (the union ledgers, _coverage.csv, _tools/lint_baseline.txt, the README coverage table) is
     resolved with `fix --base <merge-base> --side REMOTE/BRANCH --side <old HEAD>`, `git add -u`, `git rebase
     --continue`. Any other conflicted path (an article, a tool, docs, README outside the table) stops with exit 3
     and the rebase left in progress: `needs-human: PATH` lines, a `sync-state: base=.. upstream=.. orig_head=..` line
     and the commands to finish (or `git rebase --abort`). Article text is never resolved automatically.
  d. fix (with --base/--side when both sides had commits); what it changed is committed on its own as
     "chore(kb): kbgit fix after sync" with KB-* trailers. Unpushed commits whose trailers no longer match their diff
     (conflict resolution, renumbered ids) get them rewritten (`git rebase --exec "kbgit.py trailers --amend"`).
     Gate: build_index.py --check, check.py, tests.py with KB_TESTS_FAST=1 (no git scenarios; KB_SYNC_NO_TESTS=1
     skips it, for the tool's own tests), check-trailers REMOTE/BRANCH..HEAD. A red gate: exit 1, nothing pushed.
  e. --push: git push REMOTE HEAD:BRANCH, never --force. Rejected because the remote moved: fetch and rebase once more,
     then give up (exit 1).
  f. a report: commits rebased, conflicts resolved, fix, ids renumbered, trailers refreshed, gate, pushed or not.
  --dry-run fetches and reports ahead/behind, the incoming commits and the files both sides changed; nothing else.
Exit (sync): 0 done, 1 gate failed or push rejected/failed, 2 refused (dirty tree, operation in progress, bad
arguments, fetch failed), 3 a conflict or a fix problem needs a human or /kb-git-sync.

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

Exit (fix, fmt): 0 clean (or fixed), 1 --check and something would change, 2 a problem needs a human (nothing is written).
Exit (history): 0 ok; 1 check-trailers found bad commits, log found nothing, asof/blame found no such file or line;
2 bad arguments, not a git clone, or a git error. Hooks always exit 0.
"""
import argparse, csv, datetime, io, os, re, shlex, stat, subprocess, sys

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


def git_run(*args, stdin=None):
    """The finished git process (bytes output), or None when git cannot be started."""
    try:
        return subprocess.run(["git", *args], cwd=KB, capture_output=True, input=stdin)
    except OSError:
        return None


def git(*args, stdin=None):
    """stdout of a git command in the kb, or None when git or the object is unavailable."""
    p = git_run(*args, stdin=stdin)
    return p.stdout.decode("utf-8", "replace") if p is not None and p.returncode == 0 else None


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

MARKER_LINE = re.compile(r"(<<<<<<<|>>>>>>>|\|\|\|\|\|\|\|)( |$)")


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
                if not cite_count(ln, sid) or MARKER_LINE.match(ln):
                    continue  # a conflict marker line carries a commit subject, not a citation
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


# ---------------------------------------------------------------- history: trailers

# The last commit before KB-* trailers existed: it and its ancestors are exempt from check-trailers.
TRAILERS_SINCE = "e5dadde122a08111128e48eec9656c5d617ab631"
MAX_IDS = 40  # more values than this: "N ids (see diff)" instead of the list
KEYS = ("KB-Topics", "KB-Sources-Added", "KB-Sources-Changed", "KB-Sources-Superseded", "KB-Answers")
VERIFIED = "KB-Verified"
NOUN = {"KB-Topics": "topics", "KB-Answers": "answers"}
SUMMARY = re.compile(r"^(\d+) (?:ids|topics|answers) \(see diff\)$")
KEY_LINE = re.compile(r"^(" + "|".join(re.escape(k) for k in KEYS) + r")\s*:", re.I)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
INDEX = None  # compute() target: the index (staged changes)
HOOKS_DIR = ".githooks"
HOOKS = ("prepare-commit-msg", "commit-msg")
AMEND_MARK = "kb-trailers-base"


def valid_date(s):
    if not DATE.fullmatch(s or ""):
        return False
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def rev_parse(rev):
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}") or "").strip() or None


def empty_tree():
    return (git("hash-object", "-t", "tree", "--stdin", stdin=b"") or "").strip()


def git_path(name):
    p = (git("rev-parse", "--git-path", name) or "").strip()
    return os.path.join(KB, p) if p else None


def blob(rev, rel):
    """Text of rel at a commit, in the index (rev INDEX) or nowhere (rev "" = the empty tree): None when absent."""
    if rev == "":
        return None
    return git("show", (":" if rev is INDEX else rev + ":") + "./" + rel)


def changed_paths(base, target):
    """Paths that differ between base (a commit or the empty tree) and target (a commit, or INDEX)."""
    base = base or empty_tree()
    out = (git("diff-index", "--cached", "--name-only", "-z", base) if target is INDEX
           else git("diff-tree", "-r", "--name-only", "-z", base, target))
    if out is None:
        raise Problem(f"git diff {base[:12]} {'(index)' if target is INDEX else target[:12]} failed")
    return sorted(p for p in out.split("\0") if p)


def is_content(path):
    top = path.split("/", 1)[0]
    return "/" in path and not top.startswith(("_", "."))


def topic_map(coverage_texts):
    """({file: {topic}}, [(dir/, topic)]) from _coverage.csv texts."""
    files, dirs = {}, []
    for t in coverage_texts:
        if not t:
            continue
        try:
            t = strip_markers(lf(t), "_coverage.csv")[0]
            rows = list(csv.DictReader(io.StringIO(t)))
        except (Problem, csv.Error):
            continue
        for r in rows:
            for f in (r.get("files") or "").split(";"):
                f = f.strip()
                if f.endswith("/"):
                    dirs.append((f, r.get("topic", "")))
                elif f:
                    files.setdefault(f, set()).add(r.get("topic", ""))
    return files, dirs


def source_rows_of(text):
    if not text:
        return {}
    try:
        text = strip_markers(lf(text), SOURCES)[0]
    except Problem:
        pass
    try:
        return {r["id"]: r for r in csv.DictReader(io.StringIO(text)) if r.get("id") and r["id"] != "id"}
    except csv.Error:
        return {}


def answer_sections(text):
    """{answer id: section text} of _answers.md."""
    out = {}
    for part in re.split(r"(?m)^(?=## )", text or ""):
        m = kbid.ANSWER_HEAD.match(part)
        if m:
            out[m.group(1)] = out.get(m.group(1), "") + part.rstrip() + "\n"
    return out


def trailers_from(paths, old, new):
    """{key: sorted values} for a change of `paths`; old(rel)/new(rel) give a file's text before/after (None: absent)."""
    out = {}
    content = [p for p in paths if is_content(p)]
    if content:
        files, dirs = topic_map([new("_coverage.csv"), old("_coverage.csv")])
        topics = set()
        for p in content:
            t = set(files.get(p, ())) | {topic for d, topic in dirs if p.startswith(d)}
            if not t and p.endswith(".md"):
                fm = build_index.front_matter(lf(new(p) or old(p) or ""))
                if fm is not None:
                    t.add(p[:-3])
            topics |= t
        out["KB-Topics"] = sorted(t for t in topics if t)
    if SOURCES in paths:
        a, b = source_rows_of(old(SOURCES)), source_rows_of(new(SOURCES))
        strip = lambda r: {k: v for k, v in r.items() if k != "used_in" and v}  # noqa: E731  (a new empty column is no edit)
        sup = {i for i in b if (b[i].get("superseded_by") or "").strip() and not (a.get(i, {}).get("superseded_by") or "").strip() and i in a}
        out["KB-Sources-Added"] = sorted(set(b) - set(a), key=id_key)
        out["KB-Sources-Superseded"] = sorted(sup, key=id_key)
        out["KB-Sources-Changed"] = sorted(({i for i in a if i in b and strip(a[i]) != strip(b[i])} - sup) | (set(a) - set(b)), key=id_key)
    if "_answers.md" in paths:
        a, b = answer_sections(old("_answers.md")), answer_sections(new("_answers.md"))
        out["KB-Answers"] = sorted(i for i in set(a) | set(b) if a.get(i) != b.get(i))
    return {k: out[k] for k in KEYS if out.get(k)}


def compute(base, target):
    """Trailers for base (commit sha, or "" for the empty tree) -> target (commit sha, or INDEX)."""
    return trailers_from(changed_paths(base, target), lambda rel: blob(base, rel), lambda rel: blob(target, rel))


def first_parent(rev):
    """The commit a commit's trailers are computed against: its first parent, or "" (empty tree) for a root."""
    parents = (git("rev-list", "--parents", "-n", "1", rev) or "").split()[1:]
    return parents[0] if parents else ""


def trailer_lines(computed, verified=None):
    out = []
    for k in KEYS:
        v = computed.get(k)
        if v:
            out.append(f"{k}: " + (", ".join(v) if len(v) <= MAX_IDS else f"{len(v)} {NOUN.get(k, 'ids')} (see diff)"))
    if verified:
        out.append(f"{VERIFIED}: {verified}")
    return out


def parse_trailers(text):
    """{canonical key: [values]} of the KB-* trailers in `git log %(trailers:only,unfold)` output."""
    out = {}
    canon = {k.lower(): k for k in KEYS + (VERIFIED,)}
    for ln in (text or "").splitlines():
        k, sep, v = ln.partition(":")
        if sep and k.strip().lower() in canon:
            out.setdefault(canon[k.strip().lower()], []).append(v.strip())
    return out


def values_match(actual, want):
    """Does a trailer value (list of occurrences) state exactly the ids `want`?"""
    if not actual:
        return not want
    if len(actual) > 1:
        return False
    m = SUMMARY.match(actual[0])
    if m:
        return len(want) > MAX_IDS and int(m.group(1)) == len(want)
    return sorted(x.strip() for x in actual[0].split(",") if x.strip()) == sorted(want)


def comment_char():
    c = (git("config", "--get", "core.commentChar") or "#").strip()
    return c if len(c) == 1 else "#"


def apply_trailers(message, computed, verified=None):
    """The message with its KB-* trailers replaced by the computed ones (appended with git interpret-trailers).
    An empty message (the user aborted in the editor) is returned unchanged, so the commit still aborts."""
    cc = comment_char()
    if not any(ln.strip() and not ln.startswith(cc) for ln in message.splitlines()):
        return message
    drop = lambda ln: KEY_LINE.match(ln) or (verified and ln.lower().startswith(VERIFIED.lower() + ":"))  # noqa: E731
    kept = "".join(ln for ln in message.splitlines(keepends=True) if not drop(ln))
    lines = trailer_lines(computed, verified)
    if not lines:
        return kept
    args = ["interpret-trailers", "--if-exists", "replace"]
    for ln in lines:
        args += ["--trailer", ln]
    out = git(*args, stdin=kept.encode("utf-8"))
    if out is None:
        raise Problem("git interpret-trailers failed")
    return out


def cmd_trailers(a):
    if a.verified and not valid_date(a.verified):
        print(f"--verified {a.verified!r}: expected YYYY-MM-DD")
        return 2
    if a.amend:
        head = rev_parse("HEAD")
        if not head:
            print("no commit to amend")
            return 2
        if (git("rev-list", "--parents", "-n", "1", "HEAD") or "").count(" ") > 1:
            print("HEAD is a merge commit: merges carry no trailers")
            return 2
        if git("diff-index", "--cached", "--quiet", "HEAD") is None:
            print("staged changes present: commit or unstage them first (--amend only rewrites the message)")
            return 2
        msg = git("log", "-1", "--format=%B", "HEAD") or ""
        new = apply_trailers(msg, compute(first_parent(head), head), a.verified)
        if new.strip() == msg.strip():
            print("trailers already correct")
            return 0
        p = git_run("commit", "--amend", "--no-verify", "--allow-empty", "--cleanup=whitespace", "-F", "-", stdin=new.encode("utf-8"))
        if p is None or p.returncode:
            print("git commit --amend failed: " + (p.stderr.decode("utf-8", "replace") if p else "no git"))
            return 2
        print(git("log", "-1", "--format=%h %s%n%(trailers:only,unfold)", "HEAD") or "")
        return 0
    if a.rev and not a.staged:
        rev = rev_parse(a.rev)
        if not rev:
            print(f"{a.rev}: not a commit here")
            return 2
        computed = compute(first_parent(rev), rev)
    else:
        computed = compute(rev_parse("HEAD") or "", INDEX)
    for ln in trailer_lines(computed, a.verified):
        print(ln)
    return 0


# ---------------------------------------------------------------- history: hooks

def hook_prepare(args):
    """Note an --amend (git passes `commit HEAD`; -c/-C pass `commit <rev>`), so commit-msg diffs against HEAD's parent, not HEAD."""
    mark = git_path(AMEND_MARK)
    if mark and os.path.exists(mark):
        os.remove(mark)
    if mark and len(args) >= 3 and args[1] == "commit" and rev_parse(args[2]) == rev_parse("HEAD"):
        parents = (git("rev-list", "--parents", "-n", "1", "HEAD") or "").split()[1:]
        with open(mark, "w", encoding="utf-8") as f:
            f.write("merge" if len(parents) > 1 else (parents[0] if parents else "root"))


def hook_commit_msg(args):
    mark, base = git_path(AMEND_MARK), None
    if mark and os.path.exists(mark):
        with open(mark, encoding="utf-8") as f:
            base = f.read().strip()
        os.remove(mark)
    if base == "merge" or rev_parse("MERGE_HEAD"):
        return  # merge commits carry no trailers
    with open(args[0], encoding="utf-8", errors="replace", newline="") as f:
        msg = f.read()
    rebasing = any(os.path.isdir(p or "") for p in (git_path("rebase-merge"), git_path("rebase-apply")))
    if rebasing and any(KEY_LINE.match(ln) for ln in msg.splitlines()):
        return
    if base is None:
        base = rev_parse("HEAD") or ""
    elif base == "root":
        base = ""
    verified = os.environ.get("KB_VERIFIED", "").strip() or None
    if verified and not valid_date(verified):
        print(f"kbgit.py: KB_VERIFIED={verified!r} is not YYYY-MM-DD; not added", file=sys.stderr)
        verified = None
    new = apply_trailers(msg, compute(base, INDEX), verified)
    if new != msg:
        with open(args[0], "w", encoding="utf-8", newline="") as f:
            f.write(new)


def cmd_hook(a):
    try:
        (hook_prepare if a.name == "prepare-commit-msg" else hook_commit_msg)(a.args)
    except Exception as e:  # noqa: BLE001 - a hook must never block a commit
        print(f"kbgit.py {a.name}: KB trailers not added ({type(e).__name__}: {e})", file=sys.stderr)
    return 0


def cmd_install_hooks(a):
    if git("rev-parse", "--git-dir") is None:
        print("not a git clone (or git is missing)")
        return 2
    cur = (git("config", "--get", "core.hooksPath") or "").strip()
    if a.uninstall:
        if cur.rstrip("/") == HOOKS_DIR:
            git("config", "--unset", "core.hooksPath")
            print(f"uninstalled: core.hooksPath unset ({HOOKS_DIR}/ stays in the repo)")
        else:
            print("not installed" + (f" (core.hooksPath is {cur!r}; left alone)" if cur else ""))
        return 0
    for name in HOOKS:
        p = os.path.join(KB, HOOKS_DIR, name)
        if not os.path.isfile(p):
            print(f"{HOOKS_DIR}/{name} is missing from this checkout")
            return 2
        mode = os.stat(p).st_mode
        if not mode & stat.S_IXUSR:
            os.chmod(p, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if cur and cur.rstrip("/") != HOOKS_DIR:
        print(f"core.hooksPath is already {cur!r}; not changed. Chain {HOOKS_DIR}/commit-msg and "
              f"{HOOKS_DIR}/prepare-commit-msg from there, or `git config --unset core.hooksPath` and rerun")
        return 2
    if cur:
        print(f"already installed (core.hooksPath={cur})")
        return 0
    old = git_path("hooks")  # .git/hooks while core.hooksPath is unset
    if old and os.path.isdir(old):
        own = sorted(f for f in os.listdir(old) if not f.endswith(".sample"))
        if own:
            print(f"WARN hooks in {os.path.relpath(old, KB)}/ stop running while core.hooksPath is set: {', '.join(own)}")
    if git("config", "core.hooksPath", HOOKS_DIR) is None:
        print("git config core.hooksPath failed")
        return 2
    print(f"installed: core.hooksPath={HOOKS_DIR} ({', '.join(HOOKS)}); kb commits now get KB-* trailers")
    return 0


# ---------------------------------------------------------------- history: check, log, blame, asof, census

def log_records(*args):
    """[(sha, short, date, subject, trailers text)] of `git log ARGS`, newest first."""
    out = git("log", "--format=%H%x1f%h%x1f%cs%x1f%s%x1f%(trailers:only,unfold)%x1e", *args)
    if out is None:
        return None
    recs = []
    for r in out.split("\x1e"):
        f = r.strip("\n").split("\x1f")
        if len(f) == 5:
            recs.append(tuple(f))
    return recs


def default_range():
    before, sha = os.environ.get("CI_COMMIT_BEFORE_SHA", ""), os.environ.get("CI_COMMIT_SHA", "")
    if sha:
        if before and set(before) != {"0"} and rev_parse(before):
            return f"{before}..{sha}"
        return sha
    return "@{upstream}..HEAD" if rev_parse("@{upstream}") else "HEAD"


def trailer_audit(rng, quiet=False):
    """(commits checked, kb commits, [(sha, lines describing what is wrong)]) for a range A..B or one commit;
    None when the range is not valid here."""
    spec = [rng] if ".." in rng else [rng + "^!"]
    since = rev_parse(TRAILERS_SINCE)
    if since:
        spec.append("^" + since)
    elif not quiet:
        print(f"note: exemption cutoff {TRAILERS_SINCE[:12]} is not in this clone; every commit in the range is checked")
    recs = log_records("--no-merges", *spec)
    if recs is None:
        return None
    bad, kb = [], 0
    for sha, short, date, subject, trailers in recs:
        want = compute(first_parent(sha), sha)
        have = parse_trailers(trailers)
        wrong = [k for k in KEYS if not values_match(have.get(k), want.get(k, []))]
        v = have.get(VERIFIED)
        if v and (len(v) > 1 or not valid_date(v[0])):
            wrong.append(VERIFIED)
        kb += bool(want)
        if wrong:
            lines = [f"BAD {short} {date} {subject[:70]}"]
            for k in wrong:
                exp = next((ln for ln in trailer_lines(want) if ln.startswith(k + ":")), f"(no {k})" if k != VERIFIED else "YYYY-MM-DD, once")
                lines.append(f"    {k}: has {', '.join(have.get(k, [])) or '(none)'}; expected {exp}")
            bad.append((sha, lines))
    return len(recs), kb, bad


def cmd_check_trailers(a):
    rng = a.range or default_range()
    audit = trailer_audit(rng)
    if audit is None:
        print(f"{rng}: not a valid revision range here")
        return 2
    n, kb, bad_list = audit
    for _, lines in bad_list:
        print("\n".join(lines))
    bad = len(bad_list)
    print(f"check-trailers {rng}: commits={n} kb_commits={kb} bad={bad}")
    if bad:
        print("fix unpushed commits: python3 _tools/kbgit.py trailers --amend (HEAD), or "
              "git rebase --exec \"python3 _tools/kbgit.py trailers --amend\" <base>; "
              "install the hook once per clone: python3 _tools/kbgit.py install-hooks")
    return 1 if bad else 0


def id_regex(sid):
    """POSIX ERE for a source id as a whole word (git log -G)."""
    return rf"(^|[^A-Za-z0-9_-]){re.escape(sid)}([^A-Za-z0-9_-]|$)"


def classify(arg):
    if kbid.is_source_id(kbid.canonical_id(arg)) and not os.path.exists(os.path.join(KB, arg)):
        return "source", kbid.canonical_id(arg)
    if kbid.QK_ID.fullmatch(arg) or arg in kbid.answer_ids(read("_answers.md") or ""):
        return "answer", arg
    topics = {r["topic"]: r for r in csv.DictReader(io.StringIO(lf(read("_coverage.csv") or "")))}
    if arg in topics or (os.path.isfile(os.path.join(KB, arg + ".md")) and is_content(arg + ".md")):
        return "topic", arg
    return "path", arg[2:] if arg.startswith("./") else arg


def cmd_log(a):
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    kind, what = classify(a.target)
    keys = {"source": ("KB-Sources-Added", "KB-Sources-Changed", "KB-Sources-Superseded"),
            "topic": ("KB-Topics",), "answer": ("KB-Answers",), "path": ()}[kind]
    recs = log_records("HEAD") or []
    how = {}
    for sha, _, _, _, trailers in recs:
        t = parse_trailers(trailers)
        if any(what in [x.strip() for v in t.get(k, []) for x in v.split(",")] for k in keys):
            how[sha] = "trailer"
    fallback = []
    if kind == "source":
        fallback = [("diff", ["-G", id_regex(what)])]
    elif kind == "answer":
        fallback = [("diff", ["-G", rf"^## {re.escape(what)}\. ", "--", "_answers.md"])]
    elif kind == "topic":
        row = {r["topic"]: r for r in csv.DictReader(io.StringIO(lf(read("_coverage.csv") or "")))}.get(what)
        files = [f for f in (row["files"].split(";") if row else [what + ".md"]) if f]
        fallback = [("path", ["--"] + files)]
    else:
        fallback = [("path", ["--follow", "--", what])]
    for label, args in fallback:
        for sha in (git("log", "--format=%H", "HEAD", *args) or "").split():
            how.setdefault(sha, label)
    hits = [r for r in recs if r[0] in how]
    print(f"# {kind} {what}: {len(hits)} commit(s)" + (f", newest {a.n}" if len(hits) > a.n else ""))
    for sha, short, date, subject, _ in hits[:a.n]:
        print(f"{short}  {date}  {subject[:80]}  [{how[sha]}]")
    return 0 if hits else 1


def blame_line(path, n, ignore_ws):
    args = ["blame", "--porcelain", "-M", "-C", "-L", f"{n},{n}"] + (["-w"] if ignore_ws else []) + ["--", path]
    out = git(*args)
    if not out:
        return None
    lines = out.splitlines()
    info = {"sha": lines[0].split()[0]}
    for ln in lines[1:]:
        if ln.startswith("\t"):
            info["text"] = ln[1:]
            break
        k, _, v = ln.partition(" ")
        info[k] = v
    return info


def cmd_blame(a):
    path, _, line = a.target.rpartition(":")
    if not path or not line.isdigit() or int(line) < 1:
        print(f"{a.target!r}: expected PATH:LINE")
        return 2
    path = path[2:] if path.startswith("./") else path
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    b = blame_line(path, int(line), True)
    if b is None:
        print(f"{path}:{line}: no such tracked file or line")
        return 1
    zero = set(b["sha"]) == {"0"}
    when = datetime.datetime.fromtimestamp(int(b.get("author-time", "0")), datetime.timezone.utc).date() if not zero else ""
    print(f"{path}:{line}: {b.get('text', '')}")
    if zero:
        print("  introduced by: not committed yet")
    else:
        rec = (log_records("-1", b["sha"]) or [("", b["sha"][:7], str(when), b.get("summary", ""), "")])[0]
        print(f"  introduced by: {rec[1]}  {rec[2]}  {rec[3][:80]}  ({b.get('author', '?')})"
              + (f"  [as {b['filename']}]" if b.get("filename") and b["filename"] != path else ""))
        plain = blame_line(path, int(line), False)
        later = int((git("rev-list", "--count", f"{b['sha']}..HEAD", "--", path) or "0").strip() or 0)
        if plain and plain["sha"] != b["sha"]:
            print(f"  touched since: whitespace only, in {plain['sha'][:7]}")
        else:
            print("  touched since: no" + (f" (the file changed in {later} later commit(s))" if later else ""))
    ids = sorted(set(build_index.CITE.findall(b.get("text", ""))), key=id_key)
    rows = {r.get("id"): r for r in kbid.read_sources()} if ids else {}
    for sid in ids:
        r = rows.get(sid)
        added = (git("log", "--reverse", "--format=%h %cs", "-G", rf"^{re.escape(sid)},", "HEAD", "--", SOURCES) or "").split("\n")[0]
        sup = (r or {}).get("superseded_by", "").strip()
        print(f"  {sid}  {(r or {}).get('url') or 'UNKNOWN id'}" + (f"  superseded by {sup}" if sup else "")
              + (f"  (row added in {added})" if added else ""))
    return 0


def cmd_asof(a):
    if valid_date(a.when):
        rev = (git("rev-list", "-1", "--first-parent", f"--before={a.when} 23:59:59", "HEAD") or "").strip()
        if not rev:
            print(f"no commit on or before {a.when}", file=sys.stderr)
            return 1
    else:
        rev = rev_parse(a.when)
        if not rev:
            print(f"{a.when!r}: neither YYYY-MM-DD nor a tag or commit here", file=sys.stderr)
            return 2
    path = a.path[2:] if a.path.startswith("./") else a.path
    p = git_run("show", f"{rev}:./{path}")
    rec = (log_records("-1", rev) or [("", rev[:7], "", "", "")])[0]
    if p is None or p.returncode:
        print(f"{path} did not exist at {rec[1]} ({rec[2]})", file=sys.stderr)
        return 1
    print(f"# {path} at {rec[1]}  {rec[2]}  {rec[3][:80]}", file=sys.stderr)
    sys.stdout.flush()
    sys.stdout.buffer.write(p.stdout)
    return 0


def census_message(date):
    lines = [f"kb confirmed current as of {date}", ""]
    rows = source_rows_of(blob("HEAD", SOURCES))
    sup = sum(1 for r in rows.values() if (r.get("superseded_by") or "").strip())
    lines.append(f"sources: {len(rows)} in {SOURCES} ({sup} superseded)")
    st = blob("HEAD", STATE)
    if st:
        state = list(csv.DictReader(io.StringIO(lf(st))))
        ok = [r for r in state if r.get("checked_utc") and not (r.get("error") or "").strip()]
        err = sum(1 for r in state if (r.get("error") or "").strip())
        latest = max((r.get("checked_utc", "") for r in state), default="")
        never = len(set(rows) - {r.get("id") for r in state})
        lines.append(f"fetch state: {len(ok)} sources verified (checked without error), {err} with an error, "
                     f"{never} never checked; latest check {latest[:10] or 'none'}")
    else:
        lines.append(f"fetch state: none ({STATE} is not committed)")
    return "\n".join(lines) + "\n"


def cmd_tag_census(a):
    if not valid_date(a.date):
        print(f"{a.date!r}: expected YYYY-MM-DD")
        return 2
    head = rev_parse("HEAD")
    if not head:
        print("not a git clone, or no commits")
        return 2
    name = f"census-{a.date}"
    if rev_parse(f"refs/tags/{name}"):
        print(f"tag {name} already exists")
        return 2
    if a.date > datetime.date.today().isoformat():
        print(f"WARN {a.date} is in the future")
    if (git("status", "--porcelain", "--untracked-files=no") or "").strip():
        print("WARN uncommitted changes are not part of the census (the tag is on HEAD)")
    msg = census_message(a.date)
    p = git_run("tag", "-a", name, "-F", "-", head, stdin=msg.encode("utf-8"))
    if p is None or p.returncode:
        print("git tag failed: " + (p.stderr.decode("utf-8", "replace") if p else "no git"))
        return 2
    print(f"created annotated tag {name} on {head[:12]}\n" + msg.rstrip())
    print(f"not pushed; to share it: git push origin {name}")
    return 0


# ---------------------------------------------------------------- sync: fetch, rebase, fix, gate, push

# Paths whose rebase conflicts are resolved mechanically: the union ledgers and the generated files. `fix` rebuilds
# them (README.md only when its markers are inside the coverage table; otherwise fix reports it and sync stops).
MECHANICAL = frozenset((SOURCES, STATE, *MD_LEDGERS, "_coverage.csv", BASELINE, "README.md"))
IN_PROGRESS = (("rebase-merge", "a rebase", "git rebase --continue, or git rebase --abort"),
               ("rebase-apply", "a rebase", "git rebase --continue, or git rebase --abort"),
               ("MERGE_HEAD", "a merge", "git merge --continue, or git merge --abort"),
               ("CHERRY_PICK_HEAD", "a cherry-pick", "git cherry-pick --continue, or git cherry-pick --abort"),
               ("REVERT_HEAD", "a revert", "git revert --continue, or git revert --abort"))
NO_EDITOR = {"GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"}
FIX_COMMIT = "chore(kb): kbgit fix after sync"
REJECTED = re.compile(r"\[rejected\]|non-fast-forward|fetch first|stale info", re.I)


def gitx(*args, env=None):
    """(exit code, stdout + stderr text) of a git command in the kb; (127, message) when git cannot be started."""
    try:
        p = subprocess.run(["git", *args], cwd=KB, capture_output=True, text=True, errors="replace",
                           env={**os.environ, **(env or {})})
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout + p.stderr


def tool(name, *args, env=None):
    """(exit code, output) of a kb tool in this checkout (the files on disk, which a rebase may have updated)."""
    p = subprocess.run([sys.executable, os.path.join(KB, "_tools", name), *args], cwd=KB, capture_output=True,
                       text=True, errors="replace", env={**os.environ, **(env or {})})
    return p.returncode, p.stdout + p.stderr


def in_progress():
    for name, what, how in IN_PROGRESS:
        p = git_path(name)
        if p and os.path.exists(p):
            return what, how
    return None


def rebasing():
    return any(os.path.isdir(git_path(n) or "") for n in ("rebase-merge", "rebase-apply"))


def dirty_paths():
    """(staged, unstaged) tracked paths that differ from HEAD / the index (untracked files do not count)."""
    return names("diff", "--cached", "--name-only"), names("diff", "--name-only")


def names(*args):
    return sorted(p for p in (git(*args, "-z") or "").split("\0") if p)


def short(rev):
    return (rev or "")[:9]


def fix_args(base, sides):
    return ["fix"] + (["--base", base] + [x for s in sides for x in ("--side", s)] if base else [])


def renumbered(output):
    return [ln.strip() for ln in output.splitlines() if " collision: " in ln]


def conflict_help(r, up, base, orig, manual, mech, step):
    fix_cmd = "python3 _tools/kbgit.py " + " ".join(fix_args(base, [up, orig]))
    print(f"CONFLICT rebasing onto {r['target']}, at local commit {step}")
    for p in manual:
        print(f"needs-human: {p}")
    for p in mech:
        print(f"mechanical: {p}  (kbgit.py fix rebuilds it)")
    print(f"sync-state: base={base} upstream={up} orig_head={orig}")
    print("The rebase is still in progress; nothing was pushed. Never resolve article text by taking one side blindly.")
    print("Resolve (or run /kb-git-sync), one command at a time:")
    print("  edit the needs-human files: keep both sides' facts, no conflict markers left")
    print(f"  {fix_cmd}")
    print("  git add <the resolved paths>")
    print("  git rebase --continue          (later local commits may stop again)")
    print("  python3 _tools/kbgit.py sync --push")
    print(f"Or give up: git rebase --abort  (back to {short(orig)}, nothing lost)")


def do_rebase(r, up, base, orig):
    """Rebase HEAD onto up, resolving conflicts in MECHANICAL paths with fix. 0 done, 2 git refused, 3 manual."""
    code, out = gitx("rebase", up, env=NO_EDITOR)
    for _ in range(1000):
        if not rebasing():
            if code:
                print("git rebase failed:\n" + out.rstrip())
                return 2
            return 0
        conflicted = names("diff", "--name-only", "--diff-filter=U")
        stopped = git("log", "-1", "--format=%h %s", "REBASE_HEAD") or ""
        step = stopped.strip() or "(unknown)"
        if not conflicted:
            if git_run("diff", "--cached", "--quiet", "HEAD").returncode == 0 and \
                    git_run("diff", "--quiet").returncode == 0:
                code, out = gitx("rebase", "--skip", env=NO_EDITOR)
                r["notes"].append(f"dropped {step}: empty after the rebase")
            else:
                code, out = gitx("rebase", "--continue", env=NO_EDITOR)
                if code and rebasing() and not names("diff", "--name-only", "--diff-filter=U"):
                    print(out.rstrip())
                    conflict_help(r, up, base, orig, ["(rebase stopped without a conflict; see git's message above)"], [], step)
                    return 3
            continue
        manual = [p for p in conflicted if p not in MECHANICAL]
        mech = [p for p in conflicted if p in MECHANICAL]
        if manual:
            conflict_help(r, up, base, orig, manual, mech, step)
            return 3
        fcode, fout = tool("kbgit.py", *fix_args(base, [up, orig]))
        if fcode:
            print(fout.rstrip())
            probs = [ln[len("PROBLEM "):] for ln in fout.splitlines() if ln.startswith("PROBLEM ")]
            conflict_help(r, up, base, orig, [p for p in mech if any(p in x for x in probs)] or mech, [], step)
            return 3
        left = [p for p in conflicted if has_markers(read(p))]
        if left:
            conflict_help(r, up, base, orig, left, [], step)
            return 3
        r["renumbered"] += renumbered(fout)
        r["auto"].append(f"{step}: {', '.join(mech)}")
        gitx("add", "-u")
        code, out = gitx("rebase", "--continue", env=NO_EDITOR)
    print("git rebase did not finish after 1000 steps; inspect with git status")
    return 3


def commit_fix(r):
    """Commit what fix changed as its own small commit, with KB-* trailers computed here (hook or not)."""
    gitx("add", "-u")
    body = f"{FIX_COMMIT}\n\nkbgit.py fix after rebasing onto {r['target']}: " + \
           ("renumbered colliding ids and their citations; " if r["renumbered"] else "") + \
           "merged the union-merged ledger rows and rebuilt the generated index.\n"
    msg = apply_trailers(body, compute(rev_parse("HEAD") or "", INDEX))
    p = subprocess.run(["git", "commit", "-q", "--no-verify", "--cleanup=whitespace", "-F", "-"], cwd=KB,
                       input=msg, capture_output=True, text=True, errors="replace")
    if p.returncode:
        print("git commit of the fix failed:\n" + (p.stdout + p.stderr).rstrip())
        return False
    r["fix_commit"] = rev_parse("HEAD")
    return True


def refresh_trailers(r, up):
    """Rewrite the KB-* trailers of the unpushed commits whose trailers no longer match their diff
    (a rebase that resolved conflicts or renumbered ids changes the diffs). Only up..HEAD is touched."""
    audit = trailer_audit(f"{up}..HEAD", quiet=True)
    if not audit or not audit[2]:
        return True
    exe = " ".join(shlex.quote(x) for x in (sys.executable, os.path.join(KB, "_tools", "kbgit.py"), "trailers", "--amend"))
    code, out = gitx("rebase", "--exec", exe, up, env=NO_EDITOR)
    if code or rebasing():
        print("refreshing trailers failed:\n" + out.rstrip())
        if rebasing():
            gitx("rebase", "--abort")
        return False
    r["refreshed"] = len(audit[2])
    return True


def gate(r, up):
    """build_index --check, check.py, tests.py (KB_TESTS_FAST=1: no git scenarios) and check-trailers on up..HEAD."""
    results = []
    for label, name, args, env in (("build_index.py --check", "build_index.py", ["--check"], None),
                                   ("check.py", "check.py", [], None),
                                   ("tests.py (fast)", "tests.py", [], {"KB_TESTS_FAST": "1"})):
        if name == "tests.py" and os.environ.get("KB_SYNC_NO_TESTS") == "1":
            results.append((label, "skipped (KB_SYNC_NO_TESTS=1)", True))
            continue
        code, out = tool(name, *args, env=env)
        tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or [""]
        results.append((label, ("ok" if code == 0 else f"FAILED (exit {code})") + f": {tail[0][:100]}", code == 0))
        if code:
            print(f"--- {label} output (last lines)\n" + "\n".join(out.strip().splitlines()[-25:]))
    rng = f"{up}..HEAD" if up else "HEAD"
    audit = trailer_audit(rng, quiet=True)
    if audit is None:
        results.append((f"check-trailers {rng}", "FAILED: not a valid range", False))
    else:
        for _, lines in audit[2]:
            print("\n".join(lines))
        results.append((f"check-trailers {r['target']}..HEAD", f"{'ok' if not audit[2] else 'FAILED'}: commits={audit[0]} bad={len(audit[2])}",
                        not audit[2]))
    r["gate"] = results
    return all(ok for _, _, ok in results)


def sync_once(a, r):
    """One fetch -> rebase -> fix -> gate -> push round. Returns an exit code, or "retry" when the push was rejected."""
    target = f"{a.remote}/{a.branch}"
    r["target"] = target
    code, out = gitx("fetch", "--quiet", a.remote, f"+refs/heads/{a.branch}:refs/remotes/{target}")
    missing = code and re.search(r"couldn't find remote ref", out, re.I)
    if code and not missing:
        print(f"git fetch {a.remote} failed:\n" + out.rstrip())
        return 2
    up = None if missing else rev_parse(f"refs/remotes/{target}")
    orig = rev_parse("HEAD")
    if up:
        base = (git("merge-base", up, orig) or "").strip()
        if not base:
            print(f"refused: HEAD and {target} share no history")
            return 2
        behind, ahead = (int(x) for x in (git("rev-list", "--left-right", "--count", f"{up}...{orig}") or "0 0").split())
    else:
        base, behind = None, 0
        ahead = int((git("rev-list", "--count", orig) or "0").strip())
    r.update(ahead=ahead, behind=behind)
    print(f"{target}: local {ahead} ahead, {behind} behind" + ("" if up else f" ({a.branch} does not exist on {a.remote} yet)"))

    if a.dry_run:
        if behind:
            incoming, local = names("diff", "--name-only", base, up), names("diff", "--name-only", base, orig)
            both = sorted(set(incoming) & set(local))
            print(f"incoming commits ({behind}):")
            print("  " + "\n  ".join((git("log", "--format=%h %s", "-n", "20", f"{orig}..{up}") or "").splitlines()))
            if ahead:
                print(f"would rebase {ahead} local commit(s) onto {target}; files changed on both sides: {len(both)}")
                for p in both:
                    print(f"  {'mechanical (fix)' if p in MECHANICAL else 'needs a human if it conflicts'}: {p}")
            else:
                print(f"would fast-forward to {target}")
        else:
            print("nothing incoming" + (f"; would push {ahead} commit(s) after the gate" if ahead else "; nothing to push"))
        print("dry run: nothing rebased, fixed, committed or pushed")
        return 0

    if up and behind:
        code = do_rebase(r, up, base, orig)
        if code:
            return code
        r["rebased"] += ahead
    both_sides = bool(up and behind and ahead)
    code, out = tool("kbgit.py", *fix_args(base if both_sides else None, [up, orig]))
    if code:
        print(out.rstrip())
        print("kbgit.py fix needs a human (listed above); the rebase is complete and nothing was written or pushed. "
              "Resolve, commit, then rerun python3 _tools/kbgit.py sync --push (or use /kb-git-sync)")
        return 3
    r["renumbered"] += renumbered(out)
    fixed = [ln[len("wrote "):] for ln in out.splitlines() if ln.startswith("wrote ")]
    if fixed:
        r["fixed"] += fixed
        if not commit_fix(r):
            return 1
    if up and not refresh_trailers(r, up):
        return 1
    if not gate(r, up):
        print("gate failed: nothing pushed")
        return 1
    if not a.push:
        r["pushed"] = "no (without --push)"
        return 0
    now_ahead = int((git("rev-list", "--count", f"{up}..HEAD" if up else "HEAD") or "0").strip())
    if not now_ahead:
        r["pushed"] = "nothing to push"
        return 0
    code, out = gitx("push", a.remote, f"HEAD:refs/heads/{a.branch}")
    if code:
        if REJECTED.search(out):
            print(f"push rejected ({target} moved):\n" + out.rstrip())
            return "retry"
        print("git push failed:\n" + out.rstrip())
        r["pushed"] = "no (push failed)"
        return 1
    r["pushed"] = f"yes: {now_ahead} commit(s) to {target} ({short(rev_parse('HEAD'))})"
    return 0


def cmd_sync(a):
    if git("rev-parse", "--is-inside-work-tree") is None or not rev_parse("HEAD"):
        print("refused: not a git clone with commits (or git is missing)")
        return 2
    if git("check-ref-format", "--branch", a.branch) is None or git("remote", "get-url", a.remote) is None:
        print(f"refused: no remote {a.remote!r}, or {a.branch!r} is not a valid branch name")
        return 2
    busy = in_progress()
    if busy:
        print(f"refused: {busy[0]} is in progress; finish it first ({busy[1]})")
        return 2
    staged, unstaged = dirty_paths()
    refuse = None
    if staged or unstaged:
        lines = ["refused: uncommitted changes; commit them (git commit) or stash them (git stash) first"]
        lines += [f"  staged:   {p}" for p in staged] + [f"  unstaged: {p}" for p in unstaged]
        refuse = "\n".join(lines)
        if not a.dry_run:
            print(refuse)
            return 2
    if (git("config", "--get", "core.hooksPath") or "").strip().rstrip("/") != HOOKS_DIR:
        print("note: commit hooks not installed (python3 _tools/kbgit.py install-hooks); sync repairs trailers of what it rebases")
    r = {"ahead": 0, "behind": 0, "rebased": 0, "auto": [], "fixed": [], "renumbered": [], "refreshed": 0,
         "fix_commit": None, "gate": [], "pushed": "no", "notes": []}
    code = sync_once(a, r)
    if code == "retry":
        print("fetching again and rebasing once more")
        code = sync_once(a, r)
        if code == "retry":
            print(f"push rejected twice ({a.remote}/{a.branch} keeps moving); giving up, nothing lost locally")
            r["pushed"] = "no (rejected twice)"
            code = 1
    if a.dry_run:
        if refuse:
            print(refuse)
            return 2
        return code
    print("--- sync report")
    print(f"target: {r.get('target')}; was {r['ahead']} ahead, {r['behind']} behind; commits rebased: {r['rebased']}")
    if r["auto"]:
        print("conflicts resolved mechanically: " + "; ".join(r["auto"]))
    print("fix: " + (f"{len(r['fixed'])} file(s) ({', '.join(r['fixed'])}), committed as {short(r['fix_commit'])} {FIX_COMMIT!r}"
                     if r["fixed"] else "nothing to change"))
    print("ids renumbered: " + ("; ".join(r["renumbered"]) if r["renumbered"] else "none"))
    if r["refreshed"]:
        print(f"trailers refreshed on {r['refreshed']} commit(s)")
    for n in r["notes"]:
        print("note: " + n)
    for label, result, _ in r["gate"]:
        print(f"gate {label}: {result}")
    print(f"pushed: {r['pushed']}")
    print(f"sync: exit {code}")
    return code


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fix", help="post-merge cleanup of the ledgers, then build_index.py")
    f.add_argument("--check", action="store_true", help="write nothing; exit 1 if fix would change something")
    f.add_argument("--base", help="the merge base (git merge-base A B); needed to renumber colliding legacy ids")
    f.add_argument("--side", action="append", default=[], help="a merged branch/commit (repeatable; default: MERGE_HEAD or HEAD's parents)")
    m = sub.add_parser("fmt", help="canonical CSV quoting, order and newlines of the ledgers")
    m.add_argument("--check", action="store_true", help="write nothing; exit 1 if fmt would change something")
    t = sub.add_parser("trailers", help="print the KB-* trailers of the staged change (default) or of a commit")
    t.add_argument("rev", nargs="?", help="a commit (diffed against its first parent)")
    t.add_argument("--staged", action="store_true", help="the staged change against HEAD (the default)")
    t.add_argument("--amend", action="store_true", help="rewrite HEAD's message with the correct trailers (no content change)")
    t.add_argument("--verified", metavar="YYYY-MM-DD", help="add KB-Verified: the commit confirms its sources are current")
    i = sub.add_parser("install-hooks", help="git config core.hooksPath .githooks (commit-msg adds KB-* trailers)")
    i.add_argument("--uninstall", action="store_true", help="unset core.hooksPath if it points at .githooks")
    c = sub.add_parser("check-trailers", help="exit 1 listing kb commits with missing or wrong KB-* trailers")
    c.add_argument("range", nargs="?", help="A..B or one commit (default: the CI push range, else @{upstream}..HEAD)")
    lg = sub.add_parser("log", help="commits that touched a source id, topic, answer id or path")
    lg.add_argument("target")
    lg.add_argument("-n", type=int, default=20, help="show at most N commits (default 20)")
    b = sub.add_parser("blame", help="the commit that introduced a line, and the sources it cites")
    b.add_argument("target", metavar="PATH:LINE")
    s = sub.add_parser("asof", help="a file as of a date (last commit on or before it) or a tag")
    s.add_argument("when", metavar="YYYY-MM-DD|TAG")
    s.add_argument("path")
    y = sub.add_parser("sync", help="fetch, rebase onto REMOTE/BRANCH, fix, run the gate, push with --push")
    y.add_argument("--push", action="store_true", help="push HEAD to REMOTE/BRANCH after a green gate (plain push, never --force)")
    y.add_argument("--dry-run", action="store_true", help="fetch and report what would happen; rebase, commit and push nothing")
    y.add_argument("--remote", default="origin", help="the remote (default origin)")
    y.add_argument("--branch", default="main", help="the remote branch to rebase onto and push to (default main)")
    g = sub.add_parser("tag-census", help="annotated tag census-YYYY-MM-DD on HEAD (not pushed)")
    g.add_argument("date", metavar="YYYY-MM-DD")
    h = sub.add_parser("hook", help="internal: run by the .githooks scripts")
    h.add_argument("name", choices=HOOKS)
    h.add_argument("args", nargs="*")
    a = ap.parse_args()
    cmds = {"trailers": cmd_trailers, "install-hooks": cmd_install_hooks, "check-trailers": cmd_check_trailers,
            "log": cmd_log, "blame": cmd_blame, "asof": cmd_asof, "tag-census": cmd_tag_census, "hook": cmd_hook,
            "sync": cmd_sync}
    if a.cmd in cmds:
        try:
            sys.exit(cmds[a.cmd](a))
        except Problem as e:
            print(f"ERROR {e}")
            sys.exit(2)
    sys.exit(run(a))


if __name__ == "__main__":
    main()
