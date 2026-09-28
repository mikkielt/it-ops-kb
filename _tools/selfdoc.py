#!/usr/bin/env python3
"""Which of the kb's own docs (kb/_self/, AGENTS.md, README.md) are behind the files they describe (stdlib only).

  selfdoc.py stale                 docs whose described files changed in a commit after the doc's last commit, or in
                                   the working tree while the doc did not; exit 1 when any
  selfdoc.py stale --since REV     docs whose described files differ between REV and the working tree (untracked files
                                   included) while the doc does not: the check before a commit or a push
                                   (`--since @{upstream}`); exit 1 when any
  selfdoc.py map PATH [PATH ...]   the docs that describe these paths
  selfdoc.py check                 map rows naming a missing doc or matching no file, and kb/_self/*.md docs with no row;
                                   exit 1 when any

kb/_self/map.csv (doc,pattern) says what each doc describes: one row per doc and glob, repository-relative paths; `*` stays within a
directory, `**` crosses directories. A pattern of `-` marks a doc that describes no file (a state file such as
work-left.md): it is never stale. Reports under kb/_self/reports/ are measurements, each section stating its setup, and need no row. /kb-self is the
runbook that updates what `stale` lists. A doc that was checked against a change and needed no edit is recorded
with a commit trailer, `Self-Reviewed: kb/_self/plugin.md, AGENTS.md`: from that commit on, `stale` counts it as up to
date for everything before. A repository tool like kbgit.py: it reads this clone, never KB_ROOT.
Exit 0 nothing to do, 1 stale docs or map problems, 2 bad arguments, no git, or an unreadable map.
"""
import argparse, csv, functools, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon  # noqa: E402

KB = kbcommon.HOME  # this repository
SELF_REL = kbcommon.repo_rel(kbcommon.SELF)  # the kb's own docs, relative to the repository (`_self`)
MAP = f"{SELF_REL}/map.csv"
REVIEWED = "Self-Reviewed"  # commit trailer: docs checked against the change that needed no edit


class SelfdocError(Exception):
    pass


@functools.lru_cache(maxsize=None)
def glob_rx(pattern):
    """A compiled regex for a map glob: `**` any path, `*` any name part, `?` one character (never `/`)."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches(pattern, path):
    return pattern != "-" and bool(glob_rx(pattern).match(path))


def load_map(root=KB):
    """{doc: [pattern, ...]} in file order."""
    try:
        with open(os.path.join(root, MAP), encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as e:
        raise SelfdocError(f"cannot read {MAP}: {e.strerror}")
    if rows and not {"doc", "pattern"} <= rows[0].keys():
        raise SelfdocError(f"{MAP} needs the columns doc,pattern")
    out = {}
    for r in rows:
        doc, pat = (r.get("doc") or "").strip(), (r.get("pattern") or "").strip()
        if doc and pat:
            out.setdefault(doc, []).append(pat)
    return out


def describing(docs, paths):
    """{doc: [paths it describes]} for the given paths, docs without a match left out."""
    out = {}
    for doc, pats in docs.items():
        hit = [p for p in paths if p != doc and any(matches(pat, p) for pat in pats)]
        if hit:
            out[doc] = hit
    return out


def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise SelfdocError(f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def lines(text):
    return [ln for ln in text.splitlines() if ln]


def worktree_changes(root, rev="HEAD"):
    """Paths that differ between REV and the working tree (staged or not), plus untracked files."""
    return set(lines(git(root, "diff", "--name-only", rev))) | set(lines(git(root, "ls-files", "--others", "--exclude-standard")))


def reviews(root, rev_range=None):
    """[(short hash, {docs})] newest first: the commits (all of HEAD's history, or REV_RANGE) whose message carries
    a `Self-Reviewed: <doc>, <doc>` trailer (the docs were checked against the change and needed no edit)."""
    fmt = f"%h%x1f%(trailers:key={REVIEWED},valueonly,separator=%x2C)%x1e"
    out = []
    for rec in git(root, "log", f"--format={fmt}", *([rev_range] if rev_range else [])).split("\x1e"):
        h, _, docs = rec.strip().partition("\x1f")
        names = {d.strip() for d in docs.replace("\n", ",").split(",") if d.strip()}
        if h and names:
            out.append((h, names))
    return out


def stale(root=KB, since=None):
    """[(doc, reference, [changed described paths])]: the docs that are behind what they describe. A doc edited in
    the change, or named in a `Self-Reviewed:` trailer of a commit since, counts as up to date."""
    docs = load_map(root)
    out = []
    if since:
        git(root, "rev-parse", "--verify", "--quiet", since + "^{commit}")
        changed = worktree_changes(root, since)
        updated = changed | {d for _, names in reviews(root, f"{since}..HEAD") for d in names}  # a review is no change
        for doc, hit in describing(docs, sorted(changed)).items():
            if doc not in updated:
                out.append((doc, since, hit))
        return out
    local = worktree_changes(root)
    reviewed = reviews(root)
    for doc in docs:
        if doc in local:
            continue  # being edited now: the edit is the update
        last = git(root, "log", "-1", "--format=%h", "--", doc).strip()
        if not last:
            continue  # never committed: new, so not behind anything yet
        seen = next((h for h, names in reviewed if doc in names), None)
        if seen and subprocess.run(["git", "merge-base", "--is-ancestor", last, seen], cwd=root).returncode == 0:
            last = seen  # reviewed after its last edit: the review is the reference
        later = set(lines(git(root, "diff", "--name-only", last, "HEAD"))) | local
        hit = describing({doc: docs[doc]}, sorted(later)).get(doc)
        if hit:
            out.append((doc, last, hit))
    return out


def check(root=KB):
    """Problems with the map: missing docs, patterns that match no file, top-level _self docs with no row."""
    docs = load_map(root)
    files = set(lines(git(root, "ls-files"))) | set(lines(git(root, "ls-files", "--others", "--exclude-standard")))
    problems = []
    for doc, pats in docs.items():
        if not os.path.exists(os.path.join(root, doc)):
            problems.append(f"{doc}: the doc does not exist")
        for pat in pats:
            if pat != "-" and not any(matches(pat, f) for f in files):
                problems.append(f"{doc}: pattern {pat} matches no file")
    for f in sorted(files):
        if f.startswith(SELF_REL + "/") and "/" not in f[len(SELF_REL) + 1:] and f.endswith(".md") and f not in docs:
            problems.append(f"{f}: no row in {MAP} (pattern - if it describes no file)")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stale", help="docs behind the files they describe")
    s.add_argument("--since", metavar="REV", help="compare REV with the working tree instead of each doc's last commit")
    m = sub.add_parser("map", help="the docs that describe these paths")
    m.add_argument("paths", nargs="+")
    sub.add_parser("check", help="map rows naming a missing doc or matching no file; _self docs with no row")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "map":
            found = describing(load_map(), [os.path.normpath(p).replace(os.sep, "/") for p in a.paths])
            for doc, hit in found.items():
                print(f"{doc}: {', '.join(hit)}")
            print(f"docs={len(found)}")
            return 0
        if a.cmd == "check":
            problems = check()
            for p in problems:
                print("PROBLEM", p)
            print(f"problems={len(problems)}")
            return 1 if problems else 0
        result = stale(since=a.since)
        for doc, ref, hit in result:
            more = f" +{len(hit) - 8} more" if len(hit) > 8 else ""
            print(f"STALE {doc} (since {ref}): {', '.join(hit[:8])}{more}")
        print(f"stale={len(result)}" + (" (update them: /kb-self)" if result else ""))
        return 1 if result else 0
    except SelfdocError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("ERROR git is not installed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
