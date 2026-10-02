"""The public-bridge command of kbgit.py (kb/_self/git.md, Public home): a branch of the public home to the integration
remote, its commits rebased onto the integration main on a local branch and sent through sync. Runs git in KB, this
module's own copy of the repository directory (a caller may point it at a scratch clone). Standard library only;
kbgit.py imports it, and it imports no facade: sync comes in as an argument.
"""
import argparse

import kbpublic
import kg_lane
import kg_merge
from kg_base import KB
from kg_sync import dirty_paths, do_rebase, gitx, in_progress, new_report, short


def git(*args, stdin=None):
    return kg_merge.git(*args, stdin=stdin, kb=KB)


def rev_parse(rev):
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}") or "").strip() or None


BRIDGE_PREFIX = "bridge/"


def bridge_dry_run(a, pub, main, tip, commits):
    """What bridge would do, from the public commits alone: their lane and the target branch."""
    print(f"dry run: {len(commits)} commit(s) of {pub}/{a.branch} not on {pub}/main")
    lane, branch = kg_lane.lane_plan(KB, main, tip)
    print(f"lane: {lane}; " + (f"would push branch {branch} with merge-request push options, main would not move"
                              if branch else f"would push to {a.remote}/main"))
    print("nothing checked out, rebased, fixed, committed or pushed")
    return 0


def cmd_bridge(a, cmd_sync):
    """A branch of the public home to the integration remote (kb/_self/git.md, Public home): its commits not on the
    public main, rebased onto the integration main on a local branch bridge/BRANCH and sent through sync (gate, lane
    routing). Exit as sync: 0 pushed (or nothing to do, or no --push), 1 refused or gate red, 2 bad arguments, 3 conflict."""
    a.remote = a.remote or kbpublic.integration_remote(KB)
    pub = kbpublic.publish_remote(KB)
    if git("rev-parse", "--is-inside-work-tree") is None or not rev_parse("HEAD"):
        print("refused: not a git clone with commits (or git is missing)")
        return 2
    if pub and pub == a.remote:
        print(f"refused: {pub!r} is both the public home and the integration remote")
        return 2
    if git("remote", "get-url", a.remote) is None:
        print(f"refused: no integration remote {a.remote!r}")
        return 2
    busy = in_progress()
    if busy:
        print(f"refused: {busy[0]} is in progress; finish it first ({busy[1]})")
        return 2
    staged, unstaged = dirty_paths()
    if (staged or unstaged) and not a.dry_run:
        print("refused: uncommitted changes; commit them (git commit) or stash them (git stash) first")
        for p in staged:
            print(f"  staged:   {p}")
        for p in unstaged:
            print(f"  unstaged: {p}")
        return 2
    try:
        main_sha, tip, commits = kbpublic.bridge_range(pub, a.branch, KB)
    except kbpublic.BridgeError as e:
        print(f"refused: {e}")
        return e.code
    print(f"{pub}/{a.branch}: {len(commits)} commit(s) not on {pub}/main")
    if not commits:
        print("bridge: nothing to bridge")
        return 0
    if a.dry_run:
        return bridge_dry_run(a, pub, main_sha, tip, commits)
    code, o = gitx("fetch", "--quiet", a.remote, f"+refs/heads/main:refs/remotes/{a.remote}/main")
    if code:
        print(f"git fetch {a.remote} failed:\n" + o.rstrip())
        return 2
    up = rev_parse(f"refs/remotes/{a.remote}/main")
    if not up:
        print(f"refused: {a.remote}/main has no commit")
        return 2
    head = (git("symbolic-ref", "--quiet", "--short", "HEAD") or "").strip()
    was = head or rev_parse("HEAD")
    tmp = BRIDGE_PREFIX + a.branch
    code, o = gitx("checkout", "-q", "-B", tmp, tip)
    if code:
        print(f"git checkout {tmp} failed:\n" + o.rstrip())
        return 2
    r = new_report(a.push)
    r["target"] = f"{a.remote}/main"
    base = (git("merge-base", up, tip) or "").strip() or None
    code = do_rebase(r, up, base, tip, since=main_sha)
    if code == 3:
        print(f"The bridged commits are on {tmp}, the rebase is in progress. After resolving, run "
              "python3 _tools/kbgit.py sync --push there; your branch " + (head or short(was)) + " is untouched.")
        return 3
    if not code:
        r["rebased"] = len(commits)
        # session "": the bridged commits are the public home's, already pushed there, not a local session's
        a2 = argparse.Namespace(remote=a.remote, branch="main", push=a.push, dry_run=False, session="")
        code = cmd_sync(a2, r)
    if code == 3:
        return 3
    pushed = str(r["pushed"]).startswith("yes")
    listing = (git("log", "--reverse", "--format=%h", "-n", str(r["ahead"] + (1 if r["fixed"] else 0)), "HEAD") or "").split()
    gitx("checkout", "-q", *(["--detach"] if not head else []), was)
    if pushed:
        gitx("branch", "-D", tmp)
        print(f"public branch: {pub}/{a.branch}")
        print("integration commits: " + " ".join(listing))
        print(f"the pull request on the public home is closed by a person once publish brings these commits ({pub} was only read)")
    else:
        print(f"the bridged commits stay on {tmp}; {head or short(was)} is checked out again")
    return code
