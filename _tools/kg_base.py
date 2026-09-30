"""The shared ground of kbgit.py's modules (kb/_self/git.md): the repository directory, the lint baseline's path, the
error the merge code raises and the roots inside this repository. Standard library only; kg_merge.py and kbgit.py
import it, and it imports no sibling but kbcommon.
"""
import os

import kbcommon

KB = kbcommon.HOME  # the repository: git runs here, and every path kbgit names is relative to it
BASELINE = "_tools/lint_baseline.txt"


class Problem(Exception):
    pass


def repo_roots():
    """The roots inside this repository's kb/ (KB_ROOTS roots live in other repositories): what fix, sync and the
    trailers work on, public first."""
    kbd = os.path.realpath(kbcommon.KB_DIR)
    return [r for r in kbcommon.roots() if os.path.dirname(os.path.realpath(r.path)) == kbd]
