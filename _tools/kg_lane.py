"""The lane plan of kbgit.py (kb/_self/git.md): which lane a commit range is in and the code/<id> branch a range with
a code-lane commit goes to. The plan reads git in the root it is given, never a module global, so `kbgit.py sync` (its clone) and
`backlog.py land` (a worktree or clone root) name the same branch through the same helper. Standard library only;
kbgit.py and backlog.py import it, and it imports no facade. Its `lane` and `check-lanes` commands
read git in KB, this module's own copy of the repository directory (a caller may point it at a scratch clone); the
default range comes in as an argument.
"""
import os, re

import kblane
import kg_merge
from kg_base import KB

WORK = "KB-Work"  # the backlog items a commit works on (kb/_self/backlog.md); written by the agent, never computed
CODE_BRANCH_PREFIX = "code/"  # a range with a code-lane commit goes to code/<id>, never to main
LANE_BRANCH = "main"  # lanes route a push to this branch only; a push to another branch (a cloud session's working
# branch, which its git proxy allows alone) goes to that branch whatever its lane


def code_branch(root, up, rev):
    """code/<id> of the commits up..REV (all of REV's history without UP) in the repository at ROOT when any of them is
    code-lane, else None (None too when git fails). <id> names the item whose code the range carries: the first KB-Work
    id of the first code-lane commit that has one, so a content commit of another item riding along (its claim, an item
    file) does not name the branch; else the first KB-Work id of the range; else REV's short hash. The one place the
    name is chosen: sync and bridge (lane_plan) and backlog.py land call it."""
    spec = [f"{up}..{rev}"] if up else [rev]
    lanes = kblane.commit_lanes(root, spec)
    if not lanes or not any(lane == kblane.CODE for _, lane, _ in lanes):
        return None
    out = kg_merge.git("log", "--reverse", f"--format=%h%x00%(trailers:key={WORK},valueonly,unfold)%x1e", *spec,
                       kb=root) or ""
    work = {}
    for rec in out.split("\x1e"):
        h, _, ids = rec.strip("\n").partition("\0")
        if h:
            work[h] = [x for x in re.split(r"[,\s]+", ids) if x]
    in_code = [i for h, lane, _ in lanes if lane == kblane.CODE for i in work.get(h, [])]
    in_range = [i for h, _, _ in lanes for i in work.get(h, [])]
    ids = in_code or in_range
    if not ids:
        tip = (kg_merge.git("rev-parse", "-q", "--verify", rev + "^{commit}", kb=root) or "").strip()
        ids = [tip[:9]]
    return CODE_BRANCH_PREFIX + ids[0]


def lane_plan(root, up, rev, target=LANE_BRANCH):
    """(lane, branch) of the commits up..REV (all of REV's history without UP) in the repository at ROOT: the branch is
    code_branch's code/<id> for a range with a code-lane commit, else None. A push to a TARGET branch other than
    LANE_BRANCH is not routed: (None, None)."""
    if target != LANE_BRANCH:
        return None, None
    branch = code_branch(root, up, rev)
    if branch is None:
        return kblane.CONTENT, None
    return kblane.CODE, branch


def cmd_lane(a, default_range):
    rng = a.range or default_range()
    lanes = kblane.commit_lanes(KB, kblane.spec_of(rng))
    if lanes is None:
        print(f"{rng}: not a valid revision range here")
        return 2
    for short, lane, code in lanes:
        print(f"{short} {lane}" + (f" {' '.join(code)}" if code else ""))
    return 0


def cmd_check_lanes(a, default_range):
    rng = a.range or default_range()
    try:
        bad = kblane.check_lanes(KB, kblane.spec_of(rng), kblane.forge_associate(a.forge, os.environ))
    except kblane.ForgeError as e:
        print(f"check-lanes {rng}: cannot read the forge's association API, so nothing passes: {e}")
        return 2
    if bad is None:
        print(f"{rng}: not a valid revision range here")
        return 2
    for short, code in bad:
        print(f"{short} code {' '.join(code)}: no merged merge request or pull request introduced it")
    print(f"check-lanes {rng}: unmerged_code_commits={len(bad)}")
    if bad:
        print("code goes to main through a merge request: python3 _tools/kbgit.py sync --push")
    return 1 if bad else 0
