"""The contribute command of kbgit.py (kb/_self/git.md, Contributing upstream): the commits of this clone that touch only
shared roots and tools and add none of the private names, cherry-picked onto the upstream's main on a local branch.
Nothing is pushed and the working tree and index are never touched: a commit is applied with `git merge-tree` and
written with `git commit-tree`. Runs git in KB, this module's own copy of the repository directory. Standard library
only; kbgit.py imports it, and it imports no facade.
"""
import kbcommon
import kbpublic
from kg_base import KB
from kg_sync import gitx, gitx_net, short

DEFAULT_BRANCH = "contribute/"  # + the upstream remote's name: the branch when --branch is not given
MAX_NAMED = 3  # paths a reason names before it counts the rest


def out(*args):
    return kbpublic.out(list(args), KB)


def named(paths):
    """The first MAX_NAMED of PATHS, sorted, with ` ...` when there are more."""
    paths = sorted(set(paths))
    return ", ".join(paths[:MAX_NAMED]) + (" ..." if len(paths) > MAX_NAMED else "")


def classify_paths(changes, internal, pointers):
    """([reason], [shared path]) of the paths a commit writes or deletes. A path is private when it lies under an
    internal root's directory INTERNAL (or an internal pointer's `kb/<name>`), is a pointer file (under POINTERS) or
    `.gitmodules`, or is one of kbpublic's PRIVATE paths; every other path is shared (the tools, the docs, a public root)."""
    roots, ptrs, priv, shared = {}, [], [], []
    for _, _, _, x in changes:
        hit = next((r for r in internal if not r or x == r or x.startswith(r + "/")), None)
        if hit is not None:
            roots.setdefault(hit or ".", x)
        elif x.startswith(pointers) or x == ".gitmodules":
            ptrs.append(x)
        elif kbpublic.FORBIDDEN_RE.search(x) or any(x == p or x.startswith(p + "/") for p in kbpublic.PRIVATE) \
                or x.rsplit("/", 1)[-1] in kbpublic.PRIVATE_NAMES:
            priv.append(x)
        else:
            shared.append(x)
    reasons = [f"the internal root {r}" for r in sorted(roots)]
    if ptrs:
        reasons.append(f"the pointer {named(ptrs)}")
    if priv:
        reasons.append(f"a private path {named(priv)}")
    return reasons, shared


def internal_dirs(head, up, changes):
    """({internal root directory}, {internal pointer's directory}) as the publish guard reads them (kbpublic.tree_refusals):
    a `_root.md` or pointer file saying `visibility: internal` (no line counts as internal, as kbcommon reads it) in HEAD's
    tree, the upstream tip's or any commit of the range, so a root made public later is still held back."""
    rooted, pointed = {}, {}
    pdir = f"kb/{kbcommon.POINTERS_DIR}/"
    for rev in (head, up):
        for x in kbpublic.tree_files(rev, KB) or []:
            if x.rsplit("/", 1)[-1] == kbcommon.ROOT_FILE:
                rooted.setdefault(f"{rev}:{x}", x)
            elif x.startswith(pdir) and x.endswith(".md") and "/" not in x[len(pdir):]:
                pointed.setdefault(f"{rev}:{x}", x)
    for _, ch in changes:
        for st, _, new, x in ch:
            if st != "D" and x.rsplit("/", 1)[-1] == kbcommon.ROOT_FILE:
                rooted.setdefault(new, x)
            elif st != "D" and x.startswith(pdir) and x.endswith(".md") and "/" not in x[len(pdir):]:
                pointed.setdefault(new, x)
    got = kbpublic.texts([*rooted, *pointed], KB)
    roots = {kbpublic.root_dir(x) for s, x in rooted.items() if kbcommon._meta(got.get(s, "")).get("visibility", "internal") == "internal"}
    ptrs = {f"kb/{x[len(pdir):-len('.md')]}" for s, x in pointed.items()
            if kbcommon._meta(got.get(s, "")).get("visibility", "internal") == "internal"}
    return roots, ptrs


def hit_reasons(path, hits):
    kinds = sorted({k for k, _ in hits})
    return f"a private name in {path} ({', '.join(kinds)})" if any(k.startswith("private-") for k in kinds) \
        else f"a leak-scan hit in {path} ({', '.join(kinds)})"


def added_hits(commits, head):
    """{sha: [reason]} of the leak scan (file_hits, so the private names the registry knows too) over the lines each of
    COMMITS adds to a shared file; COMMITS is [(sha, [(status, old blob, new blob, path)])]. The values are never named."""
    allow = kbpublic.parse_allowlist(kbpublic.blobs(head, [kbpublic.ALLOWLIST_PATH], KB).get(kbpublic.ALLOWLIST_PATH, ""))
    files = kbpublic.tree_files(head, KB) or []
    pinned = kbpublic.pinned_paths(head, files, KB)
    specs = [s for _, ch in commits for st, old, new, _ in ch if st != "D" for s in (old, new) if not kbpublic.ZERO_RE.match(s)]
    got, res = kbpublic.texts(specs, KB), {}
    for sha, ch in commits:
        for st, old, new, x in ch:
            if st == "D" or new not in got:
                continue
            seen = set(got.get(old, "").splitlines())
            added = "\n".join(ln for ln in got[new].splitlines() if ln not in seen)
            hits = kbpublic.file_hits(x, added, allow, pinned)
            if hits:
                res.setdefault(sha, []).append(hit_reasons(x, hits))
    return res


def cherry_pick(tip, sha, parent):
    """(tree, '') of SHA applied onto TIP with PARENT as the merge base, or (None, why) when it conflicts or git cannot."""
    code, o, e = kbpublic.run(["merge-tree", "--write-tree", f"--merge-base={parent}", tip, sha], KB)
    if code == 1:
        return None, "it conflicts with the upstream main and the commits taken before it"
    if code:
        return None, "git merge-tree --write-tree failed (git 2.38 or later is needed): " + e.strip()[-200:]
    return o.decode("utf-8", "replace").split("\n", 1)[0].strip(), ""


def write_commit(tree, tip, sha):
    """The new commit: SHA's message and author on TREE, the current identity as committer, TIP its parent; (sha, '') or
    (None, git's complaint)."""
    meta = out("log", "-1", "--date=raw", "--format=%an%x00%ae%x00%ad", sha) or ""
    name, email, date = (meta.split("\0") + ["", "", ""])[:3]
    msg = (kbpublic.out(["log", "-1", "--format=%B", sha], KB) or "") + "\n"
    code, o, e = kbpublic.run(["commit-tree", tree, "-p", tip, "-F", "-"], KB, stdin=msg.encode("utf-8"),
                              env={"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": date})
    return (o.decode().strip(), "") if code == 0 else (None, e.strip()[-300:])


def refuse_branch(branch):
    """Why BRANCH may not be written (the checked-out branch of any worktree, `main`, an invalid name), else ''."""
    if out("check-ref-format", "--branch", branch) is None:
        return f"{branch!r} is not a valid branch name"
    if branch == "main":
        return "main is the upstream's branch name; give the contribute branch another name"
    held = [ln.split(" ", 1)[1] for ln in (out("worktree", "list", "--porcelain") or "").splitlines()
            if ln.startswith("branch ")]
    if f"refs/heads/{branch}" in held:
        return f"{branch} is checked out; give the contribute branch another name"
    return ""


def cmd_contribute(a):
    """The commits of upstream/main..HEAD that touch only shared roots and tools and add none of the private names, on a
    local branch at the upstream main (kb/_self/git.md, Contributing upstream). Exit 0 every commit taken (or none to
    take), 1 a commit left out (each named with its reason), 2 bad arguments, no such upstream or a git error. Pushes nothing."""
    up_name = a.upstream
    branch = a.branch or DEFAULT_BRANCH + up_name
    if out("rev-parse", "--is-inside-work-tree") is None or not out("rev-parse", "--verify", "-q", "HEAD^{commit}"):
        print("refused: not a git clone with commits (or git is missing)")
        return 2
    if out("remote", "get-url", up_name) is None:
        print(f"refused: no upstream remote {up_name!r}")
        return 2
    why = refuse_branch(branch)
    if why:
        print(f"refused: {why}")
        return 2
    code, o = gitx_net("fetch", "--quiet", up_name, f"+refs/heads/main:refs/remotes/{up_name}/main")
    if code:
        print(f"git fetch {up_name} main failed:\n" + o.rstrip())
        return 2
    up = out("rev-parse", "--verify", "-q", f"refs/remotes/{up_name}/main^{{commit}}")
    head = out("rev-parse", "--verify", "-q", "HEAD^{commit}")
    if not up:
        print(f"refused: {up_name}/main has no commit")
        return 2
    try:
        changes = kbpublic.history_changes(head, up, KB)
    except RuntimeError as e:
        print(f"git error: {e}")
        return 2
    parents = {ln.split()[0]: ln.split()[1:] for ln in (out("rev-list", "--parents", f"{up}..{head}") or "").splitlines()}
    print(f"contribute: {len(changes)} commit(s) of {up_name}/main..HEAD")
    if not changes:
        print("nothing to contribute: HEAD holds no commit the upstream main lacks")
        return 0
    roots, ptr_roots = internal_dirs(head, up, changes)
    internal = sorted(roots | ptr_roots)
    pointers = f"kb/{kbcommon.POINTERS_DIR}/"
    single = [(c, ch) for c, ch in changes if len(parents.get(c, [])) == 1]
    classes = {c: classify_paths(ch, internal, pointers) for c, ch in single}
    hits = added_hits([(c, [w for w in ch if w[3] in set(classes[c][1])]) for c, ch in single], head)
    tip, took, left = up, [], []
    for sha, ch in changes:
        subject = out("log", "-1", "--format=%s", sha) or ""
        label = f"{short(sha)} {subject}"
        if len(parents.get(sha, [])) != 1:
            left.append((label, "a merge or root commit: only a commit with one parent can be picked"))
            continue
        private, shared = classes[sha]
        reasons = []
        if private and shared:
            reasons.append(f"a mixed commit, shared files ({named(shared)}) with " + "; ".join(private))
        elif private:
            reasons.append("; ".join(private))
        reasons += hits.get(sha, [])
        names = kbcommon.leak_hits(out("log", "-1", "--format=%B", sha) or "")
        if names:
            reasons.append(hit_reasons("its message", names))
        if reasons:
            left.append((label, "; ".join(reasons)))
            continue
        tree, why = cherry_pick(tip, sha, parents[sha][0])
        if tree is None:
            left.append((label, why))
        elif tree != out("rev-parse", f"{tip}^{{tree}}"):
            new, why = write_commit(tree, tip, sha)
            if new is None:
                print(f"git commit-tree failed: {why}")
                return 2
            tip = new
            took.append(label)
        else:
            took.append(label + " (its change is already on the upstream main)")
    for label in took:
        print(f"  took      {label}")
    for label, why in left:
        print(f"  left out  {label}: {why}")
    if tip == up:
        print(f"no branch made: no commit could be taken; {up_name}/main is untouched and nothing was pushed")
        return 1 if left else 0
    was = out("rev-parse", "--verify", "-q", f"refs/heads/{branch}")
    code, o = gitx("update-ref", "-m", "kbgit.py contribute", f"refs/heads/{branch}", tip)
    if code:
        print(f"git update-ref {branch} failed:\n" + o.rstrip())
        return 2
    print(f"branch {branch} at {short(tip)}: {up_name}/main and {len([t for t in took if 'already' not in t])} commit(s); "
          f"{len(left)} left out; nothing was pushed" + (f"; it held {short(was)} before" if was else ""))
    return 1 if left else 0
