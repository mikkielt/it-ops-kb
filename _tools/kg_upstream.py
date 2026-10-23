"""The upstream command of kbgit.py (kb/_self/git.md, Bringing the upstream in): fetch the upstream remote alone and bring
its `main` into the clone by the scope `kbpublic.clone_scope` reads (`me` rebases the clone's local commits onto it,
`team` and `org` merge it, so no commit the integration remote holds is rewritten), after listing each local commit that
changes a path the upstream main also tracks. Pushes nothing and runs no gate: that stays `kbgit.py sync --push`. Runs git
in KB, this module's own copy of the repository directory. Standard library only; kbgit.py imports it, and it imports no
facade.
"""
import re

import kbpublic
from kg_base import KB
from kg_contrib import cherry_pick, named
from kg_sync import MERGE_CFG, NO_EDITOR, REBASE, dirty_paths, gitx, gitx_net, in_progress, short

BRANCH = "main"  # the branch brought in and the one it is brought into
REVERTS = re.compile(r"This reverts commit ([0-9a-f]{40})")
REBASING = ("me",)  # the scopes that rebase; the others merge


def out(*args):
    return kbpublic.out(list(args), KB)


def local_commits(head, up):
    """[(sha, subject, [reverted sha], [parent], [(status, old blob, new blob, path, mode)])] of the commits UP..HEAD, oldest
    first; a merge is listed with its parents and its changes against the first."""
    changes = kbpublic.history_changes(head, up, KB)
    parents = {ln.split()[0]: ln.split()[1:] for ln in (out("rev-list", "--parents", f"{up}..{head}") or "").splitlines()}
    msgs = {}
    for chunk in (out("log", "--format=%x01%H%x00%s%x00%B", f"{up}..{head}") or "").split("\x01")[1:]:
        sha, subject, body = (chunk.split("\0") + ["", ""])[:3]
        msgs[sha] = (subject, REVERTS.findall(body))
    return [(sha, msgs.get(sha, ("", []))[0], msgs.get(sha, ("", []))[1], parents.get(sha, []), ch) for sha, ch in changes]


def owned_changes(commits, up):
    """[(sha, subject, [path], state, parent)] of the single-parent commits that change a path the upstream main tracks,
    skipping a commit a later local commit reverts and the revert itself. STATE: `resolved` when the commit's change is
    already on the upstream main (applied onto it, it adds nothing), `conflicts` when it does not apply, else `differs`.
    None when git cannot tell."""
    tracked = set(kbpublic.tree_files(up, KB) or [])
    here = {c[0] for c in commits}
    undone = {t for _, _, targets, _, _ in commits for t in targets if t in here}
    up_tree = out("rev-parse", f"{up}^{{tree}}")
    res = []
    for sha, subject, targets, parents, ch in commits:
        if len(parents) != 1 or sha in undone or any(t in here for t in targets):
            continue
        paths = sorted({x for _, _, _, x, _ in ch} & tracked)
        if not paths:
            continue
        tree, why = cherry_pick(up, sha, parents[0])
        if tree is None and "merge-tree" in why:
            print(f"git error: {why}")
            return None
        res.append((sha, subject, paths, "conflicts" if tree is None else "resolved" if tree == up_tree else "differs", parents[0]))
    return res


def print_owned(rows, scope):
    print(f"local commits that change a path the upstream main also tracks ({len(rows)}):")
    for sha, subject, paths, state, _ in rows:
        line = f"  {short(sha)} {subject}: {named(paths)}"
        if state == "resolved":
            line += ": resolved upstream, the upstream main holds its change; " + (
                "the rebase drops it" if scope in REBASING else f"drop it with `git revert --no-edit {short(sha)}` before the bring-in")
        elif state == "conflicts":
            line += ": conflicts with the upstream main"
        print(line)


def predicted_conflicts(head, up):
    """The paths `git merge-tree` finds conflicting between HEAD and UP, [] for none, None when git cannot tell."""
    code, o, _ = kbpublic.run(["merge-tree", "--write-tree", "--name-only", head, up], KB)
    if code == 0:
        return []
    if code != 1:
        return None
    lines = o.decode("utf-8", "replace").splitlines()[1:]
    return lines[:lines.index("")] if "" in lines else lines


def blocker(branch):
    """Why a real run would not start (an unsaved change, an operation in progress, another branch), else ''."""
    busy = in_progress()
    if busy:
        return f"{busy[0]} is in progress ({busy[1]})"
    staged, unstaged = dirty_paths()
    if staged or unstaged:
        return f"{len(staged) + len(unstaged)} tracked path(s) have uncommitted changes (commit them first)"
    if branch != BRANCH:
        return f"HEAD is on {branch or 'no branch'}, not {BRANCH}: the upstream is brought into {BRANCH}"
    return ""


def bring_in(scope, up, name):
    """Bring UP into HEAD by SCOPE. Exit 0 done, 2 git refused, 3 a conflict (aborted: HEAD is as it was)."""
    before = out("rev-parse", "HEAD")
    if kbpublic.run(["merge-base", "--is-ancestor", "HEAD", up], KB)[0] == 0:
        code, o = gitx("merge", "--ff-only", up)
        verb = f"fast-forwarded {BRANCH} to {name}/{BRANCH}"
    elif scope in REBASING:
        code, o = gitx(*REBASE, up, env=NO_EDITOR)
        verb = f"rebased the local commits onto {name}/{BRANCH}"
    else:
        code, o = gitx(*MERGE_CFG, "merge", "--no-edit", "-m", f"chore: merge {name}/{BRANCH}", up, env=NO_EDITOR)
        verb = f"merged {name}/{BRANCH} into {BRANCH}"
    if code:
        paths = [p for p in (out("diff", "--name-only", "--diff-filter=U") or "").splitlines() if p]
        gitx(*(["rebase"] if scope in REBASING else ["merge"]), "--abort")
        if paths:
            print(f"conflict in {named(paths)}: stopped and put HEAD back at {short(before)}, nothing changed")
            print(f"by hand: git {'rebase' if scope in REBASING else 'merge'} {name}/{BRANCH}, resolve, then kbgit.py fix and "
                  "kbgit.py sync --push (/kb-git-sync)")
            return 3
        print("git refused:\n" + o.rstrip())
        return 2
    print(f"{verb}: HEAD {short(before)} -> {short(out('rev-parse', 'HEAD'))}")
    print("pushed nothing: the gate and the push are `python3 _tools/kbgit.py sync --push`")
    return 0


def cmd_upstream(a):
    """Bring the upstream remote's main into the clone by its scope (kb/_self/git.md, Bringing the upstream in). Exit 0
    done, up to date or planned, 2 refused (no scope, no upstream, an unsaved change, another branch) or a git error, 3 a
    conflict (aborted, nothing changed). `--dry-run` fetches the upstream's main and changes nothing else."""
    if out("rev-parse", "--is-inside-work-tree") is None or not out("rev-parse", "--verify", "-q", "HEAD^{commit}"):
        print("refused: not a git clone with commits (or git is missing)")
        return 2
    scope, name = kbpublic.clone_scope(KB), kbpublic.upstream_remote(KB)
    if not scope:
        print(f"refused: {kbpublic.SCOPE_KEY} is not one of {'|'.join(kbpublic.SCOPES)}; /kb-setup sets it")
        return 2
    if not name or out("remote", "get-url", name) is None:
        print(f"refused: no upstream remote ({kbpublic.UPSTREAM_KEY} {name or 'is unset'}); /kb-setup sets it")
        return 2
    if name == kbpublic.integration_remote(KB):
        print(f"refused: {name!r} is the integration remote; the upstream is another remote")
        return 2
    branch = out("symbolic-ref", "-q", "--short", "HEAD")
    block = blocker(branch)
    if block and not a.dry_run:
        print(f"refused: {block}")
        return 2
    code, o = gitx_net("fetch", "--quiet", name, f"+refs/heads/{BRANCH}:refs/remotes/{name}/{BRANCH}")
    if code:
        print(f"git fetch {name} {BRANCH} failed:\n" + o.rstrip())
        return 2
    up = out("rev-parse", "--verify", "-q", f"refs/remotes/{name}/{BRANCH}^{{commit}}")
    head = out("rev-parse", "--verify", "-q", "HEAD^{commit}")
    if not up:
        print(f"refused: {name}/{BRANCH} has no commit")
        return 2
    ahead, behind = (int(x) for x in (out("rev-list", "--left-right", "--count", f"{head}...{up}") or "0 0").split())
    print(f"upstream: scope {scope}, {name}/{BRANCH} at {short(up)}; {ahead} local commit(s) are not on it, {behind} of its commit(s) are not in HEAD")
    try:
        rows = owned_changes(local_commits(head, up), up)
    except RuntimeError as e:
        print(f"git error: {e}")
        return 2
    if rows is None:
        return 2
    if rows:
        print_owned(rows, scope)
    else:
        print("no local commit changes a path the upstream main also tracks")
    if not behind:
        print("up to date: the upstream main is already in HEAD")
        return 0
    plan = (f"fast-forward {BRANCH} to {name}/{BRANCH}" if not ahead else
            f"rebase the {ahead} local commit(s) onto {name}/{BRANCH}" if scope in REBASING else
            f"merge {name}/{BRANCH} into {BRANCH} (a merge commit; no local commit is rewritten)")
    print("plan: " + plan)
    if not a.dry_run:
        return bring_in(scope, up, name)
    if block:
        print(f"a real run would refuse: {block}")
    clash = predicted_conflicts(head, up) if ahead else []
    print("conflicts: " + ("git cannot tell (git 2.38 or later is needed)" if clash is None else named(clash) if clash else "none expected"))
    print("dry run: nothing merged, rebased or committed")
    return 0
