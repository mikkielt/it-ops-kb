#!/usr/bin/env python3
"""The lanes of a commit (stdlib only): `content` or `code`.

  kblane.py [A..B | REV]        each commit's short hash, lane and the code paths that decided it (kbgit.py lane)

A path is content when it is written by the kb's own routine work, and code otherwise:

  content  kb/<name>/** for a name not starting with `_` (a root), kb/_querylog/**, a backlog item
           (kb/_self/backlog/*.json), a process doc directly in kb/_self/ (kb/_self/*.md), _tools/aliases.csv and
           _tools/lint_baseline.txt
  code     everything else: _tools/, .claude/, .claude-plugin/, .githooks/, the CI file, AGENTS.md, README.md, the
           other files of kb/_self/ (map.csv, a nested directory's files) and every path of a kb/_<name>/ other than
           the ones above

A commit is code when any path it changes against its first parent is code (a merge commit is judged the same way; a
root commit against the empty tree), else content. Every path the query log's writers accept (ql_deliver.auto_kinds)
and every path `kbgit.py fix` rewrites after a rebase (kbgit.MECHANICAL) is content, so a sync that rebases content
never turns into code (tests: test_kblane.py). This module imports no other kb module: the classifier is shared by
kbgit.py, backlog.py and CI, and only its CLI wiring lives in kbgit.py.
"""
import argparse, re, subprocess, sys
from pathlib import Path

CONTENT, CODE = "content", "code"
_ITEM = re.compile(r"kb/_self/backlog/[^/]+\.json")
_SELF_DOC = re.compile(r"kb/_self/[^/]+\.md")
_ROOT = re.compile(r"kb/[^/_][^/]*/.+")
_FILES = frozenset({"_tools/aliases.csv", "_tools/lint_baseline.txt"})


def path_lane(path):
    """CONTENT or CODE for a repository path (forward slashes, relative to the repository)."""
    p = path.replace("\\", "/")
    if p in _FILES or p.startswith("kb/_querylog/") or _ITEM.fullmatch(p) or _SELF_DOC.fullmatch(p) \
            or _ROOT.fullmatch(p):
        return CONTENT
    return CODE


def paths_lane(paths):
    """(lane, sorted code paths) of a change of `paths`: code when any path is code. No path is content."""
    code = sorted(p for p in paths if path_lane(p) == CODE)
    return (CODE if code else CONTENT), code


def _git(repo, *args):
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True)
    if p.returncode:
        return None
    return p.stdout.decode("utf-8", "replace")


def commit_paths(repo, sha):
    """Paths a commit changes against its first parent (the empty tree for a root commit); None when git fails."""
    parents = (_git(repo, "rev-list", "--parents", "-n", "1", sha) or "").split()[1:]
    base = parents[0] if parents else None
    if base is None:
        p = subprocess.run(["git", "hash-object", "-t", "tree", "--stdin"], cwd=str(repo), input=b"", capture_output=True)
        base = p.stdout.decode().strip() if p.returncode == 0 else None
        if not base:
            return None
    out = _git(repo, "diff-tree", "-r", "--no-renames", "--name-only", "-z", base, sha)
    if out is None:
        return None
    return sorted(x for x in out.split("\0") if x)


def commit_lanes(repo, spec):
    """[(short hash, lane, code paths)] of `git log SPEC` (A..B or one commit), oldest first; None when git fails."""
    out = _git(repo, "log", "--reverse", "--format=%H %h", *spec)
    if out is None:
        return None
    res = []
    for ln in out.splitlines():
        sha, short = ln.split()
        paths = commit_paths(repo, sha)
        if paths is None:
            return None
        lane, code = paths_lane(paths)
        res.append((short, lane, code))
    return res


def spec_of(rng):
    """The `git log` arguments of a range A..B or one commit."""
    return [rng] if ".." in rng else [rng + "^!"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="the lane of each commit: content or code")
    ap.add_argument("range", nargs="?", default="HEAD", help="A..B or one commit (default HEAD)")
    a = ap.parse_args(argv)
    lanes = commit_lanes(Path.cwd(), spec_of(a.range))
    if lanes is None:
        print(f"{a.range}: not a valid revision range here")
        return 2
    for short, lane, code in lanes:
        print(f"{short} {lane}" + (f" {' '.join(code)}" if code else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
