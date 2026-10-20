"""The shared ground of kbgit.py's modules (kb/_self/git.md): the repository directory, the git helpers every stage
runs its commands through, the lint baseline's path, the error the merge code raises and the roots inside this
repository. Standard library only; the other kg_ modules and kbgit.py import it, and it imports no sibling but kbcommon.
"""
import subprocess

import kbcommon
from kbcommon import repo_roots  # noqa: F401  (the kg_ modules import it from here; kbcommon holds the one definition)

KB = kbcommon.HOME  # the repository: git runs here, and every path kbgit names is relative to it
BASELINE = "_tools/lint_baseline.txt"


class Problem(Exception):
    pass


def git_run(*args, stdin=None, kb=None):
    """The finished git process (bytes output), run in the repository or in `kb`, another directory, for a caller that
    runs its own commands elsewhere; None when git cannot be started."""
    try:
        return subprocess.run(["git", *args], cwd=kb or KB, capture_output=True, input=stdin)
    except OSError:
        return None


def git(*args, stdin=None, kb=None):
    """stdout of a git command in the repository (or in `kb`), or None when git or the object is unavailable."""
    p = git_run(*args, stdin=stdin, kb=kb)
    return p.stdout.decode("utf-8", "replace") if p is not None and p.returncode == 0 else None


def rev_parse(rev, kb=None):
    """The commit hash REV names, or None when it names no commit."""
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}", kb=kb) or "").strip() or None
