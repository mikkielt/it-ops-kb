"""The git hooks of kbgit.py (kb/_self/git.md, Commands): the hook scripts the clone installs (`install-hooks`), whether
core.hooksPath runs them in a checkout, the pre-push hook (the push guard, the code-lane refusal and the sync gate
before a plain `git push`) and the `hook` command that runs the three (prepare-commit-msg notes an --amend, commit-msg
adds the KB-* trailers). Runs git in KB, this module's own copy of the repository directory (a caller may point it
at a scratch clone). Standard library only; kbgit.py imports it, and it imports no facade: the gate and the dirty paths
come in as arguments.
"""
import os, stat, subprocess, sys
from pathlib import Path

import kblane
import kbpublic
import kg_lane
import kg_merge
from kg_base import KB
from kg_trailers import (INDEX, KEY_LINE, STRAY_WORK, WORK, apply_trailers, blob, changed_paths, compute, message_trailers,
                         stray_work, valid_date, WORK_RULE, work_ids_ok, work_state)

HOOKS_DIR = ".githooks"
HOOKS = ("prepare-commit-msg", "commit-msg", "pre-push")
ZERO = "0" * 40
AMEND_MARK = "kb-trailers-base"


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


def to_integration(remote, url=None):
    """Whether a push to REMOTE (a remote name or a url; URL is the url git pushes to, when known) reaches the
    integration remote: by its name, or by a url equal to one of its fetch or push urls (the way kbpublic.is_public
    reads the public home), so a push by url or through another remote name pointing at it is judged like `origin`."""
    named = kbpublic.integration_remote(KB)
    if remote == named:
        return True
    if url is None:
        url = (git("remote", "get-url", remote) or "").strip() or remote
    urls = set()
    for flags in ((), ("--push",)):
        urls |= {u.strip() for u in (git("remote", "get-url", "--all", *flags, named) or "").splitlines()}
    urls.discard("")
    return bool(urls & {url, remote})


def new_lanes(spec):
    """[(short hash, lane, code paths)] of `git log SPEC`, oldest first, like kblane.commit_lanes except that a merge
    commit is judged on the paths it changes against every parent: what a side brings is judged in that side's own
    commits, so a merge-pull of content over a merged code merge request is content. A git failure on a merge counts
    as code, never as content. None when git fails."""
    log = git("log", "--reverse", "--format=%H %h %p", *spec)
    if log is None:
        return None
    res = []
    for ln in log.splitlines():
        sha, short, *parents = ln.split()
        if len(parents) < 2:
            lanes = kblane.commit_lanes(KB, [sha + "^!"])
            if lanes is None:
                return None
            res += lanes
            continue
        paths = git("diff-tree", "-r", "--no-renames", "--name-only", "-z", "--no-commit-id", "-c", sha)
        if paths is None:
            res.append((short, kblane.CODE, ["(merge unreadable)"]))
            continue
        lane, code = kblane.paths_lane([x for x in paths.split("\0") if x])
        res.append((short, lane, code))
    return res


def lane_refusals(remote, stdin, url=None):
    """[(remote ref, short hash, code paths)] of the new code-lane commits pushed to the integration remote's main
    (pre-push stdin lines `local ref, local sha, remote ref, remote sha`): remote sha..local sha, or for a new ref
    (or a remote sha this clone lacks) the commits no remote-tracking ref of REMOTE reaches. Merge commits already on
    the remote are not new, and a new one is judged on what neither parent brings (new_lanes). The integration remote
    is reached by its name or by a url equal to its own (to_integration). No API call. Other remotes and branches are
    not judged."""
    if not to_integration(remote, url):
        return []
    named = kbpublic.integration_remote(KB)
    res = []
    for ln in stdin.splitlines():
        parts = ln.split()
        if len(parts) != 4 or parts[2] != f"refs/heads/{kg_lane.LANE_BRANCH}" or parts[1] == ZERO:
            continue
        _, local_sha, ref, remote_sha = parts
        if remote_sha != ZERO and git("cat-file", "-e", remote_sha + "^{commit}") is not None:
            spec = [f"{remote_sha}..{local_sha}"]
        else:
            spec = [local_sha, "--not", f"--remotes={named}"]
        for short, lane, code in new_lanes(spec) or []:
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
    refused = lane_refusals(remote, stdin, args[1] if len(args) > 1 else None)
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


def parent_args(pid):
    """(the parent pid, the argv) of process PID: /proc on Linux, `ps` on other POSIX hosts; (None, []) when this host
    gives no way to tell (Windows)."""
    proc = Path("/proc") / str(pid)
    if (proc / "stat").exists():
        try:
            fields = (proc / "stat").read_text(encoding="utf-8", errors="replace")
            argv = (proc / "cmdline").read_bytes().split(b"\0")
            return int(fields.rsplit(")", 1)[1].split()[1]), [a.decode("utf-8", "replace") for a in argv if a]
        except (OSError, ValueError, IndexError):
            return None, []
    if os.name == "nt":
        return None, []
    try:
        p = subprocess.run(["ps", "-o", "ppid=", "-o", "command=", "-p", str(pid)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=5)
        ppid, _, cmd = p.stdout.strip().partition(" ")
        return int(ppid), cmd.split()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, []


def amend_running(levels=6):
    """True when a `git commit --amend` is among this process's ancestors (the hook script and the interpreter
    launcher sit between): with -F, -m or -t git passes prepare-commit-msg only `message` or `template`, not
    `commit HEAD`, so the hook's arguments cannot tell an amend (BG-eyuf3cxw)."""
    pid = os.getppid()
    for _ in range(levels):
        if not pid or pid <= 1:
            return False
        ppid, argv = parent_args(pid)
        if any(os.path.basename(a).startswith("git") for a in argv[:1]) and "commit" in argv and "--amend" in argv:
            return True
        pid = ppid
    return False


def hook_prepare(args):
    """Note an --amend, so commit-msg diffs against HEAD's parent, not HEAD: git passes `commit HEAD` (-c/-C pass
    `commit <rev>`), and with a message given by -F, -m or -t only `message` or `template`, read then from the
    `git commit --amend` among the hook's ancestors (amend_running)."""
    mark = git_path(AMEND_MARK)
    if mark and os.path.exists(mark):
        os.remove(mark)
    amend = len(args) >= 3 and args[1] == "commit" and rev_parse(args[2]) == rev_parse("HEAD")
    amend = amend or (len(args) >= 2 and args[1] in ("message", "template") and rev_parse("HEAD") and amend_running())
    if mark and amend:
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
    if stray_work(new):  # warnings only: the commit goes through, and check-trailers refuses it before a push
        print(f"kbgit.py commit-msg: {STRAY_WORK}; check-trailers (the pre-push hook, sync's gate) refuses this "
              "commit", file=sys.stderr)
    work = message_trailers(new)[1].get(WORK, [])
    if work:  # the checks check-trailers runs on this commit before a push, with the rule they apply said once
        staged = lambda rel: blob(INDEX, rel) if blob(INDEX, rel) is not None else blob(base, rel)  # noqa: E731
        if not work_ids_ok(work, staged):
            whys = [f"has {', '.join(work)}; expected one line of backlog item ids that exist"]
        else:
            whys = work_state(work, changed_paths(base, INDEX), staged)
        for why in whys:
            print(f"kbgit.py commit-msg: {WORK}: {why}; check-trailers (the pre-push hook, sync's gate) refuses this "
                  "commit: work lands only for a claimed item of a started sprint", file=sys.stderr)
        if whys:
            print(f"kbgit.py commit-msg: the rule: {WORK_RULE}", file=sys.stderr)


def cmd_hook(a, gate, dirty_paths):
    if a.name == "pre-push":
        return hook_pre_push(a.args, sys.stdin.read(), gate, dirty_paths)
    try:
        (hook_prepare if a.name == "prepare-commit-msg" else hook_commit_msg)(a.args)
    except Exception as e:  # noqa: BLE001 - a hook must never block a commit
        print(f"kbgit.py {a.name}: KB trailers not added ({type(e).__name__}: {e})", file=sys.stderr)
    return 0
