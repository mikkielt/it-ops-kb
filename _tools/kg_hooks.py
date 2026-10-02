"""The git hooks of kbgit.py (kb/_self/git.md, Commands): the hook scripts the clone installs (`install-hooks`), whether
core.hooksPath runs them in a checkout, and the pre-push hook (the push guard, the code-lane refusal and the sync gate
before a plain `git push`). Runs git in KB, this module's own copy of the repository directory (a caller may point it
at a scratch clone). Standard library only; kbgit.py imports it, and it imports no facade: the gate and the dirty paths
come in as arguments.
"""
import os, stat, sys
from pathlib import Path

import kblane
import kbpublic
import kg_lane
import kg_merge
from kg_base import KB

HOOKS_DIR = ".githooks"
HOOKS = ("prepare-commit-msg", "commit-msg", "pre-push")
ZERO = "0" * 40


def git(*args, stdin=None):
    return kg_merge.git(*args, stdin=stdin, kb=KB)


def rev_parse(rev):
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}") or "").strip() or None


def git_path(name):
    p = (git("rev-parse", "--git-path", name) or "").strip()
    return os.path.join(KB, p) if p else None


def worktree_tops():
    """The top level of every worktree of this clone (`git worktree list --porcelain`), this checkout's included."""
    out = git("worktree", "list", "--porcelain") or ""
    return [ln[len("worktree "):] for ln in out.splitlines() if ln.startswith("worktree ")]


def hooks_path_is_ours(cur):
    """core.hooksPath CUR runs the kb's hooks in this checkout. git runs a commit hook in the worktree's top level and
    reads core.hooksPath from the config every `git worktree` of a clone shares, so a relative `.githooks` (what
    install-hooks sets) names each worktree's own scripts, and an absolute path (a clone set up by hand) names one
    directory for all of them. Ours: this checkout's .githooks, by either form, or the .githooks of another worktree
    of the clone that holds the hook scripts (a sprint worker's worktree under the main clone's absolute value)."""
    cur = (cur or "").strip()
    if not cur:
        return False
    if cur.rstrip("/") == HOOKS_DIR:
        return True
    d = (Path(KB) / Path(cur).expanduser()).resolve()
    if d == (Path(KB) / HOOKS_DIR).resolve():
        return True
    others = {(Path(t) / HOOKS_DIR).resolve() for t in worktree_tops()}
    return d in others and all((d / h).is_file() for h in HOOKS)


def lane_refusals(remote, stdin):
    """[(remote ref, short hash, code paths)] of the new code-lane commits pushed to the integration remote's main
    (pre-push stdin lines `local ref, local sha, remote ref, remote sha`): remote sha..local sha, or for a new ref
    (or a remote sha this clone lacks) the commits no remote-tracking ref of REMOTE reaches. Merge commits already on
    the remote are not new. No API call. Other remotes and branches are not judged."""
    if remote != kbpublic.integration_remote(KB):
        return []
    res = []
    for ln in stdin.splitlines():
        parts = ln.split()
        if len(parts) != 4 or parts[2] != f"refs/heads/{kg_lane.LANE_BRANCH}" or parts[1] == ZERO:
            continue
        _, local_sha, ref, remote_sha = parts
        if remote_sha != ZERO and git("cat-file", "-e", remote_sha + "^{commit}") is not None:
            spec = [f"{remote_sha}..{local_sha}"]
        else:
            spec = [local_sha, "--not", f"--remotes={remote}"]
        for short, lane, code in kblane.commit_lanes(KB, spec) or []:
            if lane == kblane.CODE:
                res.append((ref, short, code))
    return res


def hook_pre_push(args, stdin, gate, dirty_paths):
    """The pre-push hook: run the sync gate (plus `fix --check`, which sync runs itself) before a plain `git push` of
    a branch. Exit 1 blocks the push. Skipped when `sync` pushes (it gated already: KB_GATE_DONE=1), for tag-only and
    delete-only pushes, and with a note when the pushed commit is not HEAD (the checks read the working tree). GATE and
    DIRTY_PATHS are the facade's: the sync gate with its trailer audit, and the staged and unstaged paths."""
    remote = args[0] if args else kbpublic.integration_remote(KB)
    pushed = [(p[0], p[1]) for p in (ln.split() for ln in stdin.splitlines()) if len(p) == 4]
    blocked = kbpublic.guard_push(remote, args[1] if len(args) > 1 else None, pushed, KB)
    for ref, why in blocked:
        print(f"kb pre-push: refused: {remote} is the public home and {ref} {why}; publish with "
              "python3 _tools/kbgit.py publish (kb/_self/git.md, Public home)", file=sys.stderr)
    if blocked:
        return 1
    refused = lane_refusals(remote, stdin)
    for ref, short, code in refused:
        print(f"kb pre-push: refused: {short} is a code-lane commit ({' '.join(code)}) and {ref} of {remote} is main; "
              "code reaches main through a merge request: python3 _tools/kbgit.py sync --push sends it as a "
              f"{kg_lane.CODE_BRANCH_PREFIX}<id> branch", file=sys.stderr)
    if refused:
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
