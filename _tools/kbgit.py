#!/usr/bin/env python3
"""Git helpers for the kb (stdlib only): post-merge cleanup, canonical ledger formatting, and a queryable history.

  kbgit.py fix [--check] [--base REV] [--upstream REV] [--side REV ...]   post-merge cleanup; safe any time, idempotent
  kbgit.py fmt [--check]                                   only canonical CSV formatting and order (never adds or drops a row)
  kbgit.py trailers [--staged | REV | --amend] [--verified YYYY-MM-DD]   the KB-* trailers of the staged change or a commit
  kbgit.py install-hooks [--uninstall]                     core.hooksPath=.githooks: KB-* trailers, and the gate on a plain push
  kbgit.py check-trailers [A..B | REV]                     exit 1 listing kb commits whose KB-* trailers are missing or wrong
  kbgit.py lane [A..B | REV]                               each commit's lane (content or code) and the code paths that decided it
  kbgit.py log <S-id | topic | QK-id | path> [-n N]        commits that touched it (trailers first, then diff/path history)
  kbgit.py blame <path:line>                               the commit that wrote that line, and the sources it cites
  kbgit.py asof <YYYY-MM-DD | tag | rev> <path>            the file as of the last commit on or before that date (or at the tag)
  kbgit.py tag-census YYYY-MM-DD                           annotated tag census-YYYY-MM-DD on HEAD: "kb confirmed current" (no push)
  kbgit.py sync [--push] [--dry-run] [--remote R] [--branch main]   fetch, rebase, fix, gate, push: the way to push
  kbgit.py publish [--remote R] [--dry-run] [--rewrite]    push the integration main without kb/_querylog to the public home
  kbgit.py check-public [REV]                              exit 1 when REV's history touches kb/_querylog (kbpublic.py)

Roots. Every root in this repository's kb/ (kb/public and any kb/<name>/ with a _root.md; KB_ROOTS roots belong to
other repositories) has its own ledgers: fix and fmt work on each root in turn, sync treats every root's ledgers and
coverage files as mechanical, and the pinned block of .gitattributes covers every root's artifacts. A root cites only
its own sources, so renumbering rewrites citations within that root. History arguments take a qualified name
(`public/auth/kerberos.md:42`, `team/mdm/enrol`, `team:QK-...`) or a bare one, which is the public root's.

History (trailers). Every commit that changes kb content ends with git trailers, so `git log` can answer "which commits
changed topic X / source S / answer QK-..." without reading diffs:
  KB-Topics:              qualified topic ids (`public/intune/win32-apps`) whose article or data files changed (the
                          topic -> files mapping of each root's _coverage.csv at both ends of the diff; an article not
                          in it counts under its own path)
  KB-Sources-Added:       _sources.csv ids of new rows
  KB-Sources-Changed:     ids of rows edited (used_in, which is generated, is ignored) or removed
  KB-Sources-Superseded:  ids whose superseded_by became non-empty (not also listed as changed)
  KB-Answers:             _answers.md answer ids (`<root>:<id>` outside public) whose section was added, edited or removed
  KB-Verified: YYYY-MM-DD only on request (`trailers --verified`, or KB_VERIFIED=YYYY-MM-DD in the hook's environment, or
                          `git commit --trailer "KB-Verified: 2026-09-25"`): the commit confirms its sources are current.
  KB-Auto:                written by querylog.py on its automatic commits, once, values from AUTO_VALUES (querylog,
                          eval, alias, expansion, gap, research, revert); never computed here. check-trailers flags a
                          second KB-Auto line or a value outside the list.
  KB-Work:                written by the agent on a commit that works on backlog items (kb/_self/backlog.md), once,
                          comma-separated item ids; never computed here. check-trailers flags a second line or an id
                          whose item file is in neither the commit nor its parent, and, on a commit not yet on
                          origin/main, an id whose item is not claimed (doing or done at the commit) or is not in a
                          started sprint (its sprint active at the commit). Exempt from that: a backlog-planning commit
                          (only kb/_self/backlog/*.json changed), a sprint and a sprint's review story. The commit-msg
                          hook warns about it; the pre-push hook and sync's gate refuse it.
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
check-trailers catches that. pre-push runs the sync gate plus `fix --check` before a plain `git push` of the checked-out
branch and blocks it (exit 1) when a check fails; first, for any push, it refuses a ref whose history touches
kb/_querylog on its way to the public home (kbpublic.py); the gate skips sync's own push (KB_GATE_DONE=1), tags and deletes, and a
pushed ref that is not HEAD (with a note: the checks read the working tree). `git push --no-verify` skips it. Fix unpushed commits with `trailers --amend` (HEAD) or
`git rebase --exec "python3 _tools/kbgit.py trailers --amend" @{upstream}`.

check-trailers without a range: in GitLab CI, CI_COMMIT_BEFORE_SHA..CI_COMMIT_SHA (only CI_COMMIT_SHA when the
before sha is all zeros or unknown); elsewhere @{upstream}..HEAD, or HEAD alone without an upstream.
Census tags: an annotated tag `census-YYYY-MM-DD` marks "the kb was confirmed current as of that date"; its message
counts the sources and the _fetch_state.csv checks. `asof census-2026-09-26 PATH` reads a file as of a census.

Sync (the only way to push; people push straight to main, CI is a safety net):
  a. refuses (exit 2) with uncommitted tracked changes (lists staged/unstaged: commit or stash them), or while a
     rebase/merge/cherry-pick/revert is in progress; untracked files do not count.
  b. git fetch REMOTE BRANCH; prints how far HEAD is ahead of / behind REMOTE/BRANCH.
  c. git -c merge.conflictStyle=diff3 rebase REMOTE/BRANCH (diff3: see MERGE_CFG; merge commits are linearised: they
     would carry no trailers). A step that conflicts only
     in MECHANICAL paths (the union ledgers, _coverage.csv, _tools/lint_baseline.txt, the coverage table page) is
     resolved with `fix --base <merge-base> --upstream REMOTE/BRANCH --side <old HEAD>`, `git add -u`, `git rebase
     --continue`. Any other conflicted path (an article, a tool, docs, the coverage page outside the table) stops with exit 3
     and the rebase left in progress: `needs-human: PATH` lines, a `sync-state: base=.. upstream=.. orig_head=..` line
     and the commands to finish (or `git rebase --abort`). Article text is never resolved automatically.
  d. fix (with --base/--side when both sides had commits); what it changed is committed on its own as
     "chore(kb): kbgit fix after sync" with KB-* trailers. Unpushed commits whose trailers no longer match their diff
     (conflict resolution, renumbered ids) get them rewritten (`git rebase --exec "kbgit.py trailers --amend"`).
     Gate: build_index.py --check, check.py, fetch.py --offline, doc2query.py stale, selfdoc.py stale --since
     REMOTE/BRANCH (a `Self-Reviewed:` trailer clears a doc), tests.py with KB_TESTS_FAST=1 (no git scenarios;
     KB_SYNC_NO_TESTS=1 skips it, for the tool's own tests), check-trailers REMOTE/BRANCH..HEAD. A red gate: exit 1,
     nothing pushed.
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
                 Two different non-empty title/publisher/licence/reuse/artifact_sha256 values: the latest row wins and
                 the conflict is reported (a tie on retrieved_utc, or two different superseded_by, needs a human).
               - different urls: a real collision (two branches both took the next legacy number, e.g. S2205).
                 Needs --base: an id present at base keeps its base url, else the --upstream side's url keeps it
                 (it is already pushed: published ids are never renumbered); every other url gets its own id (the
                 existing id of that url if it has a row, else its hash id `kbid.py url`). Citations are rewritten
                 line by line: a line citing the id that only one side's version of the file has (and the base's
                 has not) belongs to that side; a line no side has (a resolved conflict) belongs to the one side
                 whose version of the file cites the id at all. A line on both sides, a new line in a file both
                 sides cite the id in, or an old citation of an id the base did not have, is ambiguous: reported,
                 exit 2, nothing written.
               Canonical form: legacy ids numerically, then hash ids sorted; csv module quoting; `\\n`; no BOM.
_anchors.csv   one row per (fact, path, source_id): the latest verified_utc wins (factdiff.py).
_fetch_state.csv  one row per id: checked_utc/error from the row with the latest check, the fetch columns
               (fetched_utc, sha256, text_sha256, bytes) from the row with the latest fetch, factdiff.py's columns
               (etag ... simhash, detected_utc) from the row with the latest detected_utc, changed_utc the max.
_answers.md, _gaps.md, _conflicts.md  conflict markers dropped (union semantics); verbatim duplicate `##`/`###`
               sections, duplicate list items (20+ characters) in one section and duplicate rows in one table removed.
               With the merge's sides known, a `##` section that a merge cut short is made whole: git keeps lines that
               two blocks added at one place both end with (an `_Agent: kb-research_` footer) only once, at the end
               of the second block (repair_splices; sync avoids it with diff3, see MERGE_CFG).
               Answer ids: one id heading two different
               questions: the heading at base or on --upstream keeps it (else the first), the others get their
               QK-<slug>, and lines naming the id follow their side (as citations do). The same heading twice
               with different bodies: reported, exit 2.
_tools/lint_baseline.txt  if a merge touched it (markers, unsorted or duplicate lines), it becomes the current lint
               errors that either side had accepted, sorted: a merge never accepts new lint debt by itself.
.gitattributes  the block between `# pinned:start` and `# pinned:end` lists every _artifacts.csv path as `-text`.
Then build_index.py regenerates _coverage.csv, the coverage table in kb/_self/coverage.md (conflict markers inside the
table go with it) and used_in. Conflict markers left anywhere else in a ledger, that page or an article: exit 2.
kb/_querylog/  one run file per distill run, never edited after it: an entry id in two run files (the same lookup
               distilled twice) is reported, exit 2 (querylog.duplicate_ids; kb/_self/querylog.md, Store).

Sides of the merge (for collisions): --side REV (repeatable), else MERGE_HEAD during a merge (HEAD + MERGE_HEAD),
else the parents of HEAD when HEAD is a merge commit. Base: --base REV (e.g. `git merge-base A B`). --upstream REV is
a side that is already pushed (sync passes REMOTE/BRANCH; after a cherry-pick or a rebase by hand, pass the branch you
put your commits on): its source and answer ids win a collision.

Exit (fix, fmt): 0 clean (or fixed), 1 --check and something would change, 2 a problem needs a human (nothing is written).
Exit (history): 0 ok; 1 check-trailers found bad commits, log found nothing, asof/blame found no such file or line;
2 bad arguments, not a git clone, or a git error. Hooks always exit 0.
"""
import argparse, csv, datetime, io, json, os, re, shlex, stat, subprocess, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon, kbid  # noqa: E402
import build_index  # noqa: E402
import ql_store  # noqa: E402
import kbpublic  # noqa: E402
import kblane  # noqa: E402

KB = kbcommon.HOME  # the repository: git runs here, and every path kbgit names is relative to it
ROOT = kbcommon.PUBLIC  # the root fix and the history commands work on now (use_root); the public root by default
CUR = None  # its kbcommon.Root; None: the public root, before roots() was read
KB_DIR_REL = kbcommon.repo_rel(kbcommon.KB_DIR)  # `kb`: the roots are the directories kb/<name>/


def R(rel):
    """A path relative to the current root (ROOT) as a repository path (what git takes and prints)."""
    return kbcommon.repo_rel(rel, ROOT)


def repo_roots():
    """The roots inside this repository's kb/ (KB_ROOTS roots live in other repositories): what fix, sync and the
    trailers work on, public first."""
    kbd = os.path.realpath(kbcommon.KB_DIR)
    return [r for r in kbcommon.roots() if os.path.dirname(os.path.realpath(r.path)) == kbd]


def cur_root():
    return CUR or kbcommon.public()


def use_root(r):
    """Point ROOT and the ledger paths (SOURCES, STATE, ARTIFACTS, ANSWERS, COVERAGE, MD_LEDGERS) at root r."""
    global ROOT, CUR, SOURCES, STATE, ARTIFACTS, ANSWERS, COVERAGE, MD_LEDGERS
    ROOT, CUR = r.path, r
    SOURCES, STATE, ARTIFACTS = R(kbcommon.SOURCES), R(kbcommon.STATE), R(kbcommon.ARTIFACTS)
    ANSWERS, COVERAGE = R(kbcommon.ANSWERS), R(kbcommon.COVERAGE_CSV)
    MD_LEDGERS = (ANSWERS, R(kbcommon.GAPS), R(kbcommon.CONFLICTS))


def root_of_path(path):
    """(root name, path in the root) of a repository path under kb/<name>/, else (None, None)."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == KB_DIR_REL and not parts[1].startswith(("_", ".")):
        return parts[1], "/".join(parts[2:])
    return None, None


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
    return os.path.relpath(os.path.join(KB, path), bi_root()).replace(os.sep, "/")


def user_path(arg):
    """A path given on the command line as a repository path: qualified (`public/auth/kerberos.md`), bare
    root-relative (`auth/kerberos.md`: the public root) or repository-relative; as given when it names nothing."""
    arg = arg[2:] if arg.startswith("./") else arg
    head, _, rest = arg.partition("/")
    for r in repo_roots():
        if head == r.name and rest and os.path.exists(os.path.join(r.path, rest)):
            return kbcommon.repo_rel(rest, r.path)
    return kbcommon.repo_rel(arg, kbcommon.PUBLIC) if os.path.exists(os.path.join(kbcommon.PUBLIC, arg)) else arg


def with_legacy(path):
    """[path] plus, for a file under the public root, its path before the kb moved (root-relative), for history."""
    rel = kbcommon.kb_rel(path, kbcommon.PUBLIC)
    return [path] + ([rel] if rel and rel != path else [])


SOURCES, STATE, ARTIFACTS = R(kbcommon.SOURCES), R(kbcommon.STATE), R(kbcommon.ARTIFACTS)
ANSWERS, COVERAGE = R(kbcommon.ANSWERS), R(kbcommon.COVERAGE_CSV)
MD_LEDGERS = (ANSWERS, R(kbcommon.GAPS), R(kbcommon.CONFLICTS))
BASELINE = "_tools/lint_baseline.txt"
ATTRS = ".gitattributes"
LINT = os.path.join(".claude", "skills", "kb-verify", "lint.py")
PIN_START, PIN_END = "# pinned:start", "# pinned:end"
MIN_ITEM = 20  # shorter list items (`- none`) may repeat on purpose


class Problem(Exception):
    pass


# ---------------------------------------------------------------- io and git

def read(rel):
    return kbcommon.read(os.path.join(KB, rel), newline="", strict=True)


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
    # cat-file, not show: `git show REV:PATH` checks its argument as a file name, which fails as "Filename too long"
    # on Windows in a deep checkout
    return git("cat-file", "blob", f"{rev}:./{rel}")


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
    return [f for f in out if os.path.isfile(os.path.join(KB, f))]


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
    p = subprocess.run([sys.executable, os.path.join(KB, LINT)], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
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


# ---------------------------------------------------------------- history: trailers

# The last commit before KB-* trailers existed: it and its ancestors are exempt from check-trailers.
TRAILERS_SINCE = "e5dadde122a08111128e48eec9656c5d617ab631"
MAX_IDS = 40  # more values than this: "N ids (see diff)" instead of the list
KEYS = ("KB-Topics", "KB-Sources-Added", "KB-Sources-Changed", "KB-Sources-Superseded", "KB-Answers")
VERIFIED = "KB-Verified"
AUTO = "KB-Auto"  # querylog.py's automatic commits (kb/_self/querylog.md, Delivery)
AUTO_VALUES = ("querylog", "eval", "alias", "expansion", "gap", "research", "revert")
WORK = "KB-Work"  # the backlog items a commit works on (kb/_self/backlog.md); written by the agent, never computed
WORK_ID = re.compile(r"(?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}")
BACKLOG = "kb/_self/backlog"
WORK_LINE = re.compile(r"KB-Work\s*:\s*(.*\S)\s*$", re.I)
NOUN = {"KB-Topics": "topics", "KB-Answers": "answers"}
SUMMARY = re.compile(r"^(\d+) (?:ids|topics|answers) \(see diff\)$")
KEY_LINE = re.compile(r"^(" + "|".join(re.escape(k) for k in KEYS) + r")\s*:", re.I)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
INDEX = None  # compute() target: the index (staged changes)
HOOKS_DIR = ".githooks"
HOOKS = ("prepare-commit-msg", "commit-msg", "pre-push")
ZERO = "0" * 40


def hooks_path_is_ours(cur):
    """core.hooksPath names this clone's .githooks, relative or absolute (a clone set up by hand may use either)."""
    cur = (cur or "").strip()
    if not cur:
        return False
    if cur.rstrip("/") == HOOKS_DIR:
        return True
    return os.path.realpath(os.path.join(KB, os.path.expanduser(cur))) == os.path.realpath(os.path.join(KB, HOOKS_DIR))
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
    return git("cat-file", "blob", (":" if rev is INDEX else rev + ":") + "./" + rel)  # not `git show` (see show)


def changed_paths(base, target):
    """Paths that differ between base (a commit or the empty tree) and target (a commit, or INDEX)."""
    base = base or empty_tree()
    out = (git("diff-index", "--cached", "--name-only", "-z", base) if target is INDEX
           else git("diff-tree", "-r", "--name-only", "-z", base, target))
    if out is None:
        raise Problem(f"git diff {base[:12]} {'(index)' if target is INDEX else target[:12]} failed")
    return sorted(p for p in out.split("\0") if p)


def content_rel(path):
    """(root name, path in the root) of a repository path of a domain file (under kb/<root>/, in a directory not
    named `_*` or `.*`), else (None, None)."""
    name, rel = root_of_path(path)
    if rel and "/" in rel and not rel.split("/", 1)[0].startswith(("_", ".")):
        return name, rel
    return None, None


def is_content(path):
    """A repository path of a domain file of a root."""
    return content_rel(path)[0] is not None


def legacy_content_rel(path):
    """The path of a domain file in the flat layout before the kb moved (`intune/x.md` at the repository root), or
    None: history before the move is the public root's."""
    top = path.split("/", 1)[0]
    return path if "/" in path and not top.startswith(("_", ".")) and top != KB_DIR_REL else None


def topic_map(coverage_texts):
    """({file: {topic}}, [(dir/, topic)]) from _coverage.csv texts."""
    files, dirs = {}, []
    for t in coverage_texts:
        if not t:
            continue
        try:
            t = strip_markers(lf(t), COVERAGE)[0]
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
    """{key: sorted values} for a change of `paths` (repository paths); old(rel)/new(rel) give a file's text
    before/after (None: absent). Every root under kb/ counts; topics are qualified (`public/intune/win32-apps`),
    source ids are bare (unique by their root's prefix), answer ids are `<root>:<id>` outside the public root. A
    commit from before the kb moved (a flat tree with `_sources.csv` at the top) is the public root's."""
    groups = {}  # root name -> (repository prefix of the root, [content paths in the root])
    for p in paths:
        name, rel = content_rel(p)
        if name:
            groups.setdefault(name, (f"{KB_DIR_REL}/{name}/", []))[1].append(rel)
    flat = new(kbcommon.SOURCES) is not None or old(kbcommon.SOURCES) is not None
    if flat:
        legacy = [r for r in map(legacy_content_rel, paths) if r]
        if legacy:
            groups.setdefault("public", ("", []))[1].extend(legacy)
    roots_touched = {n: pre for n, (pre, _) in groups.items()}
    for p in paths:
        name, rel = root_of_path(p)
        if name and rel in (kbcommon.SOURCES, kbcommon.ANSWERS):
            roots_touched.setdefault(name, f"{KB_DIR_REL}/{name}/")
        elif flat and p in (kbcommon.SOURCES, kbcommon.ANSWERS):
            roots_touched.setdefault("public", "")
    out = {}
    topics = set()
    for name, (pre, rels) in groups.items():
        files, dirs = topic_map([new(pre + kbcommon.COVERAGE_CSV), old(pre + kbcommon.COVERAGE_CSV)])
        for rel in rels:  # _coverage.csv names files relative to its root
            t = set(files.get(rel, ())) | {topic for d, topic in dirs if rel.startswith(d)}
            if not t and rel.endswith(".md"):
                fm = build_index.front_matter(lf(new(pre + rel) or old(pre + rel) or ""))
                if fm is not None:
                    t.add(rel[:-3])
            topics |= {f"{name}/{x}" for x in t if x}
    if topics:
        out["KB-Topics"] = sorted(topics)
    strip = lambda r: {k: v for k, v in r.items() if k != "used_in" and v}  # noqa: E731  (a new empty column is no edit)
    for name, pre in sorted(roots_touched.items()):
        src = pre + kbcommon.SOURCES
        if src in paths:
            a, b = source_rows_of(old(src)), source_rows_of(new(src))
            sup = {i for i in b if (b[i].get("superseded_by") or "").strip()
                   and not (a.get(i, {}).get("superseded_by") or "").strip() and i in a}
            out.setdefault("KB-Sources-Added", []).extend(set(b) - set(a))
            out.setdefault("KB-Sources-Superseded", []).extend(sup)
            out.setdefault("KB-Sources-Changed", []).extend(
                ({i for i in a if i in b and strip(a[i]) != strip(b[i])} - sup) | (set(a) - set(b)))
        ans = pre + kbcommon.ANSWERS
        if ans in paths:
            a, b = answer_sections(old(ans)), answer_sections(new(ans))
            q = "" if name == "public" else f"{name}:"
            out.setdefault("KB-Answers", []).extend(q + i for i in set(a) | set(b) if a.get(i) != b.get(i))
    for k in ("KB-Sources-Added", "KB-Sources-Superseded", "KB-Sources-Changed"):
        if k in out:
            out[k] = sorted(set(out[k]), key=id_key)
    if "KB-Answers" in out:
        out["KB-Answers"] = sorted(set(out["KB-Answers"]))
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
    canon = {k.lower(): k for k in KEYS + (VERIFIED, AUTO, WORK)}
    for ln in (text or "").splitlines():
        k, sep, v = ln.partition(":")
        if sep and k.strip().lower() in canon:
            out.setdefault(canon[k.strip().lower()], []).append(v.strip())
    return out


def values_match(actual, want):
    """Does a trailer value (list of occurrences) state exactly the ids `want`? A public topic matches with or
    without its root (`public/intune/x` or `intune/x`, as trailers wrote it before topics were qualified)."""
    if not actual:
        return not want
    if len(actual) > 1:
        return False
    m = SUMMARY.match(actual[0])
    if m:
        return len(want) > MAX_IDS and int(m.group(1)) == len(want)
    bare = lambda v: v[len("public/"):] if v.startswith("public/") else v  # noqa: E731
    return sorted(bare(x.strip()) for x in actual[0].split(",") if x.strip()) == sorted(map(bare, want))


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
        with open(mark, "w", encoding="utf-8", newline="\n") as f:
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
    work = [m.group(1) for m in (WORK_LINE.match(ln) for ln in new.splitlines()) if m]
    if len(work) == 1:  # a warning only: the commit goes through, and check-trailers refuses it before a push
        staged = lambda rel: blob(INDEX, rel) if blob(INDEX, rel) is not None else blob(base, rel)  # noqa: E731
        for why in work_state(work, changed_paths(base, INDEX), staged):
            print(f"kbgit.py commit-msg: {WORK}: {why}; check-trailers (the pre-push hook, sync's gate) refuses this "
                  "commit: work lands only for a claimed item of a started sprint", file=sys.stderr)


def cmd_hook(a):
    if a.name == "pre-push":
        return hook_pre_push(a.args, sys.stdin.read())
    try:
        (hook_prepare if a.name == "prepare-commit-msg" else hook_commit_msg)(a.args)
    except Exception as e:  # noqa: BLE001 - a hook must never block a commit
        print(f"kbgit.py {a.name}: KB trailers not added ({type(e).__name__}: {e})", file=sys.stderr)
    return 0


def hook_pre_push(args, stdin):
    """The pre-push hook: run the sync gate (plus `fix --check`, which sync runs itself) before a plain `git push` of
    a branch. Exit 1 blocks the push. Skipped when `sync` pushes (it gated already: KB_GATE_DONE=1), for tag-only and
    delete-only pushes, and with a note when the pushed commit is not HEAD (the checks read the working tree)."""
    remote = args[0] if args else kbpublic.integration_remote(KB)
    pushed = [(p[0], p[1]) for p in (ln.split() for ln in stdin.splitlines()) if len(p) == 4]
    blocked = kbpublic.guard_push(remote, args[1] if len(args) > 1 else None, pushed, KB)
    for ref, why in blocked:
        print(f"kb pre-push: refused: {remote} is the public home and {ref} {why}; publish with "
              "python3 _tools/kbgit.py publish (kb/_self/git.md, Public home)", file=sys.stderr)
    if blocked:
        return 1
    if os.environ.get("KB_GATE_DONE") == "1":
        return 0
    head = rev_parse("HEAD")
    ups, other = [], []
    for ln in stdin.splitlines():
        parts = ln.split()
        if len(parts) != 4 or not parts[2].startswith("refs/heads/") or parts[1] == ZERO:
            continue  # a tag, a delete or a malformed line (the local ref may be `HEAD` for `git push origin HEAD:main`)
        local_ref, local_sha, remote_ref, remote_sha = parts
        if local_sha != head:
            other.append(local_ref)
            continue
        if remote_sha != ZERO and git("cat-file", "-e", remote_sha + "^{commit}") is not None:
            ups.append(remote_sha)
        else:  # a new remote branch: gate against where it left the remote's main
            base = rev_parse(f"refs/remotes/{remote}/main")
            ups.append((git("merge-base", base, head) or "").strip() if base else None)
    for ref in other:
        print(f"kb pre-push: {ref} is not HEAD; not checked (the checks read the working tree). "
              "Check it out and push again, or use python3 _tools/kbgit.py sync --push", file=sys.stderr)
    if not ups:
        return 0
    staged, unstaged = dirty_paths()
    if staged or unstaged:
        print("kb pre-push: the working tree has uncommitted changes; the checks include them", file=sys.stderr)
    r = {"target": remote, "gate": []}
    ok = gate(r, ups[0], fix_check=True)
    for label, result, _ in r["gate"]:
        print(f"kb pre-push {label}: {result}", file=sys.stderr)
    if not ok:
        print("kb pre-push: a check failed; nothing pushed. Fix the cause (python3 _tools/kbgit.py sync --push "
              "fixes the ledgers itself); `git push --no-verify` skips this and CI reports it instead", file=sys.stderr)
        return 1
    return 0


def cmd_install_hooks(a):
    if git("rev-parse", "--git-dir") is None:
        print("not a git clone (or git is missing)")
        return 2
    cur = (git("config", "--get", "core.hooksPath") or "").strip()
    if a.uninstall:
        if hooks_path_is_ours(cur):
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
    if cur and not hooks_path_is_ours(cur):
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


def cmd_lane(a):
    rng = a.range or default_range()
    lanes = kblane.commit_lanes(KB, kblane.spec_of(rng))
    if lanes is None:
        print(f"{rng}: not a valid revision range here")
        return 2
    for short, lane, code in lanes:
        print(f"{short} {lane}" + (f" {' '.join(code)}" if code else ""))
    return 0


def commit_changes(spec):
    """{sha: (first parent or "", [changed paths])} for the non-merge commits of `git log SPEC`, from one git call:
    the paths diff-tree gives against the first parent (no rename detection; a root commit lists every file)."""
    out = git("-c", "log.showRoot=true", "log", "--no-merges", "--no-renames", "--name-only", "-z",
              "--format=%x1e%H%x1f%P", *spec)
    if out is None:
        return None
    res = {}
    for rec in out.split("\x1e")[1:]:
        head, _, rest = rec.partition("\0")
        sha, _, parents = head.partition("\x1f")
        res[sha] = ((parents.split() or [""])[0], sorted(p for p in rest.lstrip("\n").split("\0") if p))
    return res


class BlobReader:
    """File texts at commits through one `git cat-file --batch` process (blob() starts a git process per file)."""

    def __init__(self):
        try:
            self.p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=KB, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        except OSError:
            self.p = None

    def __call__(self, rev, rel):
        if rev == "" or self.p is None:
            return blob(rev, rel)
        self.p.stdin.write(f"{rev}:./{rel}\n".encode())
        self.p.stdin.flush()
        head = self.p.stdout.readline().split()
        if len(head) != 3:  # "<name> missing" (or ambiguous): not in that commit
            return None
        data = self.p.stdout.read(int(head[2]))
        self.p.stdout.read(1)
        return data.decode("utf-8", "replace") if head[1] == b"blob" else None

    def close(self):
        if self.p is not None:
            self.p.stdin.close()
            self.p.wait()


_WANT = {}  # sha -> computed trailers: sync audits the same commits twice


def trailer_audit(rng, quiet=False, work_state_on=True):
    """(commits checked, kb commits, [(sha, lines describing what is wrong)]) for a range A..B or one commit;
    None when the range is not valid here. `work_state_on`: also judge the KB-Work items of the commits not yet on
    origin/main (work_state); refresh_trailers leaves it off, since rewriting trailers cannot fix that."""
    spec = [rng] if ".." in rng else [rng + "^!"]
    since = rev_parse(TRAILERS_SINCE)
    if since:
        spec.append("^" + since)
    elif not quiet:
        print(f"note: exemption cutoff {TRAILERS_SINCE[:12]} is not in this clone; every commit in the range is checked")
    recs = log_records("--no-merges", *spec)
    if recs is None:
        return None
    changes = commit_changes(spec) or {}
    blobs = BlobReader()
    bad, kb = [], 0
    try:
        for sha, *_ in recs:
            if sha in _WANT:
                continue
            if sha in changes:
                base, paths = changes[sha]
                _WANT[sha] = trailers_from(paths, lambda rel: blobs(base, rel), lambda rel: blobs(sha, rel))
            else:
                _WANT[sha] = compute(first_parent(sha), sha)
    finally:
        blobs.close()
    for sha, short, date, subject, trailers in recs:
        want = _WANT[sha]
        have = parse_trailers(trailers)
        wrong = [k for k in KEYS if not values_match(have.get(k), want.get(k, []))]
        v = have.get(VERIFIED)
        if v and (len(v) > 1 or not valid_date(v[0])):
            wrong.append(VERIFIED)
        auto = have.get(AUTO)
        if auto and (len(auto) > 1 or not all(x.strip() in AUTO_VALUES for x in auto[0].split(","))):
            wrong.append(AUTO)
        work = have.get(WORK)
        state = []
        if work and not work_ok(sha, work):
            wrong.append(WORK)
        elif work and work_state_on and not on_origin_main(sha):
            paths = changes[sha][1] if sha in changes else changed_paths(first_parent(sha), sha)
            state = work_state(work, paths, lambda rel: at_or_parent(sha, rel))
        kb += bool(want)
        if wrong or state:
            lines = [f"BAD {short} {date} {subject[:70]}"]
            for k in wrong:
                exp = next((ln for ln in trailer_lines(want) if ln.startswith(k + ":")), {VERIFIED: "YYYY-MM-DD, once", AUTO: "once, of " + "|".join(AUTO_VALUES),
                                                                                                 WORK: "once, backlog item ids that exist at the commit or its parent"}.get(k, f"(no {k})"))
                lines.append(f"    {k}: has {', '.join(have.get(k, [])) or '(none)'}; expected {exp}")
            for why in state:
                lines.append(f"    {WORK}: {why}; work lands only for a claimed item of a started sprint")
            bad.append((sha, lines))
    return len(recs), kb, bad


def work_ok(sha, values):
    """A KB-Work trailer: one line of comma-separated backlog ids, each an item file at the commit or its parent (a
    commit that closes a sprint deletes the files)."""
    if len(values) > 1:
        return False
    ids = [x.strip() for x in values[0].split(",") if x.strip()]
    return bool(ids) and all(WORK_ID.fullmatch(i) and (blob(sha, f"{BACKLOG}/{i}.json") is not None
                                                      or blob(sha + "^", f"{BACKLOG}/{i}.json") is not None)
                             for i in ids)


WORKED = ("doing", "done")  # a claimed item (done drops claimed_by but was claimed to get there)
BACKLOG_FILE = re.compile(re.escape(BACKLOG) + r"/[^/]+\.json")


def work_state(values, paths, load):
    """[problem lines] for the KB-Work ids of a commit not yet on origin/main (kb/_self/backlog.md, Git): each id's
    item must be claimed (doing, or done) and in a started (active) sprint, read from the backlog at the commit.
    `load(rel)` is a file's text at the commit, else at its parent (a sprint close deletes the files), or None.
    Exempt: a backlog-planning commit (it changes only item files: new items, claims, gates, a sprint's plan, start
    or close), and the sprint and review items themselves. An id with no item file is work_ok's to report."""
    if paths and all(BACKLOG_FILE.fullmatch(p) for p in paths):
        return []
    cache = {}

    def get(i):
        if i not in cache:
            text = load(f"{BACKLOG}/{i}.json")
            try:
                cache[i] = json.loads(text) if text else None
            except ValueError:
                cache[i] = None
        return cache[i] if isinstance(cache[i], dict) else None

    out = []
    for i in (x.strip() for x in values[0].split(",") if x.strip()):
        it = get(i)
        if it is None or it.get("kind") == "sprint" or it.get("review"):
            continue
        if it.get("status") not in WORKED:
            out.append(f"{i} is {it.get('status')}, not claimed (backlog.py claim)")
        sp, cur, seen = None, it, {i}
        while cur is not None:
            sp = cur.get("sprint")
            if sp or not cur.get("parent") or cur["parent"] in seen:
                break
            seen.add(cur["parent"])
            cur = get(cur["parent"])
        state = (get(sp) or {}).get("status") if sp else None
        if state != "active":
            out.append(f"{i} is not in a started sprint" + (f" ({sp} is {state or 'missing'})" if sp else " (no sprint)"))
    return out


def at_or_parent(sha, rel):
    """A file's text at a commit, else at its first parent (a sprint close deletes the item files), else None."""
    text = blob(sha, rel)
    return text if text is not None else blob(sha + "^", rel)


def on_origin_main(sha):
    """True when the commit is already on the integration remote's main: its KB-Work items are history, judged when
    it landed."""
    main = rev_parse(f"refs/remotes/{kbpublic.integration_remote(KB)}/main")
    if not main:
        return False
    p = git_run("merge-base", "--is-ancestor", sha, main)
    return p is not None and p.returncode == 0


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


def split_arg(arg):
    """(Root, rest) of a history argument: `<root>/<rest>` or `<root>:<answer id>` names that root; anything else is
    the public root's."""
    for sep in ("/", ":"):
        head, s, rest = arg.partition(sep)
        if s and rest:
            for r in repo_roots():
                if r.name == head:
                    return r, rest
    return kbcommon.public(), arg


def classify(arg):
    """(kind, what, root): a source id, an answer id, a topic (qualified or bare = public) or a path."""
    if kbid.is_source_id(kbid.canonical_id(arg)) and not os.path.exists(os.path.join(KB, user_path(arg))):
        sid = kbid.canonical_id(arg)
        return "source", sid, kbcommon.root_of_prefix(sid.split("-", 1)[0] if "-" in sid else "S") or kbcommon.public()
    r, rest = split_arg(arg)
    ans = kbcommon.read(os.path.join(r.path, kbcommon.ANSWERS)) or ""
    if (kbid.QK_ID.fullmatch(rest) and ":" in arg) or kbid.QK_ID.fullmatch(arg) or rest in kbid.answer_ids(ans):
        return "answer", rest, r
    topics = {x["topic"] for x in csv.DictReader(io.StringIO(lf(kbcommon.read(os.path.join(r.path, kbcommon.COVERAGE_CSV)) or "")))}
    if rest in topics or (os.path.isfile(os.path.join(r.path, rest + ".md"))
                          and is_content(kbcommon.repo_rel(rest + ".md", r.path))):
        return "topic", rest, r
    return "path", user_path(arg), None


def cmd_log(a):
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    kind, what, r = classify(a.target)
    keys = {"source": ("KB-Sources-Added", "KB-Sources-Changed", "KB-Sources-Superseded"),
            "topic": ("KB-Topics",), "answer": ("KB-Answers",), "path": ()}[kind]
    # trailer values: topics qualified (bare in commits from before roots), answers `<root>:<id>` outside public
    if kind == "topic":
        want = {f"{r.name}/{what}"} | ({what} if r.name == "public" else set())
    elif kind == "answer":
        want = {what} if r.name == "public" else {f"{r.name}:{what}"}
    else:
        want = {what}
    recs = log_records("HEAD") or []
    how = {}
    for sha, _, _, _, trailers in recs:
        t = parse_trailers(trailers)
        if any(want & {x.strip() for v in t.get(k, []) for x in v.split(",")} for k in keys):
            how[sha] = "trailer"
    fallback = []
    if kind == "source":
        fallback = [("diff", ["-G", id_regex(what)])]
    elif kind == "answer":
        fallback = [("diff", ["-G", rf"^## {re.escape(what)}\. ", "--",
                              *with_legacy(kbcommon.repo_rel(kbcommon.ANSWERS, r.path))])]
    elif kind == "topic":
        cov = lf(kbcommon.read(os.path.join(r.path, kbcommon.COVERAGE_CSV)) or "")
        row = {x["topic"]: x for x in csv.DictReader(io.StringIO(cov))}.get(what)
        files = [f for f in (row["files"].split(";") if row else [what + ".md"]) if f]
        fallback = [("path", ["--"] + [p for f in files for p in with_legacy(kbcommon.repo_rel(f, r.path))])]
    if kind == "topic":
        what = f"{r.name}/{what}"
    elif kind == "answer" and r.name != "public":
        what = f"{r.name}:{what}"
    if kind == "path":
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
    shown = path[2:] if path.startswith("./") else path
    path = user_path(shown)
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    b = blame_line(path, int(line), True)
    if b is None:
        print(f"{shown}:{line}: no such tracked file or line")
        return 1
    zero = set(b["sha"]) == {"0"}
    when = datetime.datetime.fromtimestamp(int(b.get("author-time", "0")), datetime.timezone.utc).date() if not zero else ""
    print(f"{shown}:{line}: {b.get('text', '')}")
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
    rows, ledgers = {}, []
    for root in (repo_roots() if ids else []):
        led = kbcommon.repo_rel(kbcommon.SOURCES, root.path)
        ledgers += with_legacy(led)
        rows.update((x.get("id"), x) for x in source_rows_of(read(led)).values())
    for sid in ids:
        r = rows.get(sid)
        added = (git("log", "--reverse", "--format=%h %cs", "-G", rf"^{re.escape(sid)},", "HEAD", "--", *ledgers) or "").split("\n")[0]
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
    for cand in with_legacy(user_path(path)):  # before the kb moved, a root file sat at its root-relative path
        p = git_run("cat-file", "blob", f"{rev}:./{cand}")  # not `git show` (see show)
        if p is not None and not p.returncode:
            break
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
    print(f"not pushed; to share it: git push {kbpublic.integration_remote(KB)} {name}")
    return 0


# ---------------------------------------------------------------- sync: fetch, rebase, fix, gate, push

# Paths whose rebase conflicts are resolved mechanically: the union ledgers and the generated files. `fix` rebuilds
# them (the coverage page only when its markers are inside the table; otherwise fix reports it and sync stops).
def mechanical():
    """Every root's union ledgers, _coverage.csv and coverage page, and the lint baseline (repository paths)."""
    out = {BASELINE}
    try:
        rs = repo_roots()
    except kbcommon.RootError:
        rs = []  # a malformed root: sync still resolves the public root's ledgers; check.py names the root
    for r in rs or [None]:
        path = r.path if r else kbcommon.PUBLIC
        L = lambda n: kbcommon.repo_rel(n, path)  # noqa: E731
        out |= {L(kbcommon.SOURCES), L(kbcommon.STATE), L(kbcommon.ANSWERS), L(kbcommon.GAPS), L(kbcommon.CONFLICTS),
                L(kbcommon.COVERAGE_CSV), L(kbcommon.COVERAGE_MD)}
    return frozenset(out)


MECHANICAL = mechanical()
IN_PROGRESS = (("rebase-merge", "a rebase", "git rebase --continue, or git rebase --abort"),
               ("rebase-apply", "a rebase", "git rebase --continue, or git rebase --abort"),
               ("MERGE_HEAD", "a merge", "git merge --continue, or git merge --abort"),
               ("CHERRY_PICK_HEAD", "a cherry-pick", "git cherry-pick --continue, or git cherry-pick --abort"),
               ("REVERT_HEAD", "a revert", "git revert --continue, or git revert --abort"))
NO_EDITOR = {"GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"}
# Every rebase sync runs or tells a human to run. git's union driver (and plain conflicts) merge at the "zealous" level:
# lines both sides end (or start) with are pulled out of the conflict and kept once. Two answers that end in the same
# `_Agent: kb-research_` footer then interleave: the second is spliced into the first, above its footer, and the
# rebased commit edits the other side's section (its KB-Answers trailer names it). diff3 caps the level at "eager",
# which keeps each side's block whole (and adds the base to conflict markers, which fix and /kb-git-sync read anyway).
MERGE_CFG = ("-c", "merge.conflictStyle=diff3")
REBASE = (*MERGE_CFG, "rebase")
REBASE_HINT = "git -c merge.conflictStyle=diff3 rebase"
FIX_COMMIT = "chore(kb): kbgit fix after sync"
REJECTED = re.compile(r"\[rejected\]|non-fast-forward|fetch first|stale info", re.I)


def gitx(*args, env=None):
    """(exit code, stdout + stderr text) of a git command in the kb; (127, message) when git cannot be started."""
    try:
        p = subprocess.run(["git", *args], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, **(env or {})})
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout + p.stderr


def tool(name, *args, env=None):
    """(exit code, output) of a kb tool in this checkout (the files on disk, which a rebase may have updated)."""
    p = subprocess.run([sys.executable, os.path.join(KB, "_tools", name), *args], cwd=KB, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env={**os.environ, **(env or {})})
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


def fix_args(base, up, orig):
    """kbgit.py fix arguments after rebasing orig onto up: up is already pushed, so its ids and answer ids stay."""
    return ["fix"] + (["--base", base, "--upstream", up, "--side", orig] if base else [])


def renumbered(output):
    """fix's report lines about renumbered source ids and renamed answer ids."""
    return [ln.strip() for ln in output.splitlines() if " collision: " in ln]


def conflict_help(r, up, base, orig, manual, mech, step):
    fix_cmd = "python3 _tools/kbgit.py " + " ".join(fix_args(base, up, orig))
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
    print(f"  GIT_EDITOR=true {REBASE_HINT} --continue   (later local commits may stop again)")
    print("  python3 _tools/kbgit.py sync" + (" --push" if r.get("push") else ""))
    print(f"Or give up: git rebase --abort  (back to {short(orig)}, nothing lost)")


def do_rebase(r, up, base, orig):
    """Rebase HEAD onto up, resolving conflicts in MECHANICAL paths with fix. 0 done, 2 git refused, 3 manual."""
    code, out = gitx(*REBASE, up, env=NO_EDITOR)
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
                code, out = gitx(*REBASE, "--skip", env=NO_EDITOR)
                r["notes"].append(f"dropped {step}: empty after the rebase")
            else:
                code, out = gitx(*REBASE, "--continue", env=NO_EDITOR)
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
        fcode, fout = tool("kbgit.py", *fix_args(base, up, orig))
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
        code, out = gitx(*REBASE, "--continue", env=NO_EDITOR)
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
                       input=msg, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        print("git commit of the fix failed:\n" + (p.stdout + p.stderr).rstrip())
        return False
    r["fix_commit"] = rev_parse("HEAD")
    return True


def refresh_trailers(r, up):
    """Rewrite the KB-* trailers of the unpushed commits whose trailers no longer match their diff
    (a rebase that resolved conflicts or renumbered ids changes the diffs). Only up..HEAD is touched."""
    audit = trailer_audit(f"{up}..HEAD", quiet=True, work_state_on=False)
    if not audit or not audit[2]:
        return True
    exe = " ".join(shlex.quote(x) for x in (sys.executable, os.path.join(KB, "_tools", "kbgit.py"), "trailers", "--amend"))
    code, out = gitx(*REBASE, "--exec", exe, up, env=NO_EDITOR)
    if code or rebasing():
        print("refreshing trailers failed:\n" + out.rstrip())
        if rebasing():
            gitx("rebase", "--abort")
        return False
    r["refreshed"] = len(audit[2])
    return True


def gate(r, up, fix_check=False):
    """build_index --check, check.py, fetch.py --offline, doc2query.py stale, selfdoc.py stale --since UP (the kb's
    own docs behind the files they describe; a `Self-Reviewed:` trailer clears one), tests.py (KB_TESTS_FAST=1: no
    git scenarios) and check-trailers on up..HEAD. `fix_check` (the pre-push hook) adds `fix --check` first: sync
    runs fix itself before its gate."""
    results = []
    checks = [("kbgit.py fix --check", "kbgit.py", ["fix", "--check"], None)] if fix_check else []
    checks += [("build_index.py --check", "build_index.py", ["--check"], None),
               ("check.py", "check.py", [], None),
               ("fetch.py --offline", "fetch.py", ["--offline"], None),
               ("doc2query.py stale", "doc2query.py", ["stale"], None)]
    if up:
        checks.append((f"selfdoc.py stale --since {short(up)}", "selfdoc.py", ["stale", "--since", up], None))
    checks.append(("tests.py (fast)", "tests.py", [], {"KB_TESTS_FAST": "1"}))
    for label, name, args, env in checks:
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
    code, out = tool("kbgit.py", *fix_args(base if both_sides else None, up, orig))
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
    code, out = gitx("push", a.remote, f"HEAD:refs/heads/{a.branch}", env={"KB_GATE_DONE": "1"})  # gated above
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
    a.remote = a.remote or kbpublic.integration_remote(KB)
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
    if kbpublic.is_public(a.remote, KB) and kbpublic.private_commits("HEAD", KB, limit=1):
        print(f"refused: {a.remote} is the public home and HEAD's history touches {', '.join(kbpublic.PRIVATE)}; "
              "sync pushes to the integration remote, publish to the public one (python3 _tools/kbgit.py publish)")
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
    if not hooks_path_is_ours(git("config", "--get", "core.hooksPath")):
        print("note: commit hooks not installed (python3 _tools/kbgit.py install-hooks); sync repairs trailers of what it rebases")
    r = {"push": a.push, "ahead": 0, "behind": 0, "rebased": 0, "auto": [], "fixed": [], "renumbered": [], "refreshed": 0,
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
    f.add_argument("--upstream", help="the side that is already pushed (sync: REMOTE/BRANCH): on a collision its source and answer ids stay")
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
    ln = sub.add_parser("lane", help="each commit's lane, content or code, and the code paths that decided it")
    ln.add_argument("range", nargs="?", help="A..B or one commit (default: the CI push range, else @{upstream}..HEAD)")
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
    y.add_argument("--remote", help=f"the remote (default: the integration remote, git config {kbpublic.INTEGRATION_KEY}, else origin)")
    y.add_argument("--branch", default="main", help="the remote branch to rebase onto and push to (default main)")
    g = sub.add_parser("tag-census", help="annotated tag census-YYYY-MM-DD on HEAD (not pushed)")
    g.add_argument("date", metavar="YYYY-MM-DD")
    pb = sub.add_parser("publish", help="push the projection of the integration main (no kb/_querylog) to the public home")
    pb.add_argument("--remote", help=f"the public remote (default: git config {kbpublic.CONFIG_KEY})")
    pb.add_argument("--source", help="REMOTE/BRANCH to project (default: the integration remote's main)")
    pb.add_argument("--branch", default="main", help="the public remote's branch (default main)")
    pb.add_argument("--dry-run", action="store_true", help="fetch, project and report; push nothing")
    pb.add_argument("--rewrite", action="store_true", help="replace a public branch that is not an ancestor (force with lease)")
    cp = sub.add_parser("check-public", help="exit 1 listing commits of REV whose history touches kb/_querylog")
    cp.add_argument("rev", nargs="?", help="a commit (default HEAD)")
    h = sub.add_parser("hook", help="internal: run by the .githooks scripts")
    h.add_argument("name", choices=HOOKS)
    h.add_argument("args", nargs="*")
    a = ap.parse_args()
    cmds = {"trailers": cmd_trailers, "install-hooks": cmd_install_hooks, "check-trailers": cmd_check_trailers, "lane": cmd_lane,
            "log": cmd_log, "blame": cmd_blame, "asof": cmd_asof, "tag-census": cmd_tag_census, "hook": cmd_hook,
            "sync": cmd_sync, "publish": lambda a: kbpublic.cmd_publish(a, KB),
            "check-public": lambda a: kbpublic.cmd_check_public(a, KB)}
    if a.cmd in cmds:
        try:
            sys.exit(cmds[a.cmd](a))
        except Problem as e:
            print(f"ERROR {e}")
            sys.exit(2)
    sys.exit(run(a))


if __name__ == "__main__":
    main()
