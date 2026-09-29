#!/usr/bin/env python3
"""The public home (stdlib only): what never reaches it, which remote it is, and the history published there.

  kbgit.py publish [--remote R] [--source REMOTE/main] [--branch main] [--dry-run] [--rewrite]
  kbgit.py check-public [REV]
  kbgit.py bridge BRANCH [--push] [--dry-run] [--remote R]

The integration remote (git config kb.integrationRemote, default `origin`) holds everything; the public home (GitHub) holds the same history without the
PRIVATE paths: the query log's store `kb/_querylog/` is kept on the integration remote only. Both hosts cannot carry
the same `main`, so the public home gets a projection of it:

  projection  every commit of the source is rewritten with the PRIVATE paths removed from its tree and its parents
              replaced by their projections; its author, committer, dates and message stay byte for byte (a
              signature goes, since it no longer matches). A commit whose tree carries no PRIVATE path and whose
              parents are unchanged is its own projection, so the history before the query log keeps its hashes (and
              the census tags stay valid). A commit that changed only PRIVATE paths becomes nothing: its projection is
              its parent's. The projection is a pure function of the source history, so every clone computes the same
              commits and each publish fast-forwards the last one.
  publish     fetches the source and the public home, projects the source, verifies the projection carries no
              PRIVATE path, checks its safety (below), and pushes it to the public home's BRANCH as a fast-forward. When the public home's branch
              is not an ancestor (a commit pushed there directly, or a history from before the projection) it refuses,
              exit 1, unless --rewrite, which pushes with --force-with-lease against the tip it fetched: the one-time
              move to the projection, or a decision to drop what was pushed there directly. `refs/kb/published` keeps
              the last projection. Without a public remote it prints a note and exits 0.
  safety      after the fast-forward check and before the push (a --dry-run runs them all and pushes nothing) every
              cause is reported, exit 1, in this order: the projection's tree holds a root whose `_root.md` says
              `visibility: internal`, or a path under a `_private` or `_cache` directory (any depth); a file the
              projection changes against the public tip (every file when there is none) has a leak-scan hit
              (kbcommon.leak_hits, allowing _tools/tests_allowlist.txt of the projection); the integration CI verdict of
              the source commit (ql_deliver.ci_pipeline on the source remote's url) is not `ok`: red, pending,
              unverified, none, or skip when glab or gh cannot read it. Content is refused, never filtered.
  guard       a push to a public remote of a ref whose history touches a PRIVATE path is refused: the pre-push hook
              (for every pushed branch and tag, sync's own push included), `kbgit.py sync` before it rebases, and the
              query log's push (ql_deliver) when `origin` is public. `check-public` is the same check for CI on the
              public home: exit 1 listing the commits of REV (default HEAD) that touch a PRIVATE path.

bridge      the way back: a branch pushed to the public home (a pull request there) reaches the integration remote.
              bridge_range fetches the public home's main and BRANCH (nothing is ever pushed there), takes the commits
              not on its main (main..BRANCH) and refuses, exit 1, when one touches a PRIVATE path. `kbgit.py bridge`
              rebases them (`git rebase --onto <integration>/main <public>/main`: cherry-picked, never merged, since
              the public main is a projection of the integration main) and hands them to sync's gate and lane routing.

The public home is set per clone: `git config kb.publishRemote <remote>`. A remote is public when it is that remote or
its url is that remote's url. A clone without it (a production clone on its own host) has no public home: nothing is
guarded there, and the query log pushes its store to `origin` as before. Exit (publish): 0 published or nothing to do, 1 refused (not a fast-forward, or the projection still
carries a PRIVATE path) or the push failed, 2 bad arguments, no source, or a git error. Exit (check-public): 0 clean,
1 a PRIVATE path found, 2 a git error.
"""
import os, re, subprocess, sys

PRIVATE = ("kb/_querylog",)  # repository paths kept on the integration remote only (kb/_self/git.md, Public home)
CONFIG_KEY = "kb.publishRemote"
INTEGRATION_KEY = "kb.integrationRemote"
CLONE_REMOTE = "origin"  # what `git clone` names its source: the integration remote unless INTEGRATION_KEY says otherwise
PUBLISHED_REF = "refs/kb/published"
ZERO_RE = re.compile(r"^0+$")
FORBIDDEN_RE = re.compile(r"(^|/)(_private|_cache)(/|$)")
ALLOWLIST_PATH = "_tools/tests_allowlist.txt"
URL_RX = re.compile(r"(?:https?|ssh|git)://\S+|(?<![\w.%+-])git@[\w.-]+:[\w./~-]+|\bssh(?:\s+-\w+)*\s+git@[\w.-]+")
CI_RUN = None  # a command runner (argv -> (code, stdout, stderr)) for the CI check; None: ql_base.run_cmd. Tests stub it.


def run(args, cwd, stdin=None, env=None):
    """(code, stdout bytes, stderr text) of git ARGS in CWD."""
    p = subprocess.run(["git", *args], cwd=cwd, input=stdin, capture_output=True,
                       env={**os.environ, **env} if env else None)
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")


def out(args, cwd):
    code, o, _ = run(args, cwd)
    return o.decode("utf-8", "replace").strip() if code == 0 else None


def publish_remote(cwd):
    """The configured public remote's name, or None."""
    return out(["config", "--get", CONFIG_KEY], cwd) or None


def integration_remote(cwd):
    """The integration remote's name: git config kb.integrationRemote, else the clone's source (CLONE_REMOTE)."""
    try:
        return out(["config", "--get", INTEGRATION_KEY], cwd) or CLONE_REMOTE
    except OSError:  # no such directory: not a clone yet
        return CLONE_REMOTE


def is_public(remote, cwd, url=None):
    """Whether pushing to REMOTE (a remote name or a url; URL is its url when known) reaches the public home. False
    in a clone without one."""
    named = publish_remote(cwd)
    if not named:
        return False
    if remote == named:
        return True
    if url is None:
        url = out(["remote", "get-url", remote], cwd) or remote
    return url == out(["remote", "get-url", named], cwd)


def private_commits(rev, cwd, limit=20):
    """The commits reachable from REV that touch a PRIVATE path (newest first, at most LIMIT), or None on a git
    error. A root commit that adds one counts, so an empty list means no tree in REV's history holds one."""
    code, o, _ = run(["log", f"-{limit}", "--format=%H", rev, "--", *PRIVATE], cwd)
    return o.decode().split() if code == 0 else None


class Projector:
    """Projects commits of the repository at CWD: projection(rev) is the commit of REV's history without PRIVATE."""

    def __init__(self, cwd):
        self.cwd = cwd
        self.hexlen = 64 if out(["rev-parse", "--show-object-format"], cwd) == "sha256" else 40
        self.cat = subprocess.Popen(["git", "cat-file", "--batch"], cwd=cwd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
        self.trees, self.commits, self.tree_of = {}, {}, {}
        self.private = [tuple(p.split("/")) for p in PRIVATE]

    def close(self):
        self.cat.stdin.close()
        self.cat.wait()

    def read(self, sha):
        self.cat.stdin.write(sha.encode() + b"\n")
        self.cat.stdin.flush()
        head = self.cat.stdout.readline().split()
        if len(head) != 3:
            raise RuntimeError(f"git cat-file: no object {sha}")
        body = self.cat.stdout.read(int(head[2]))
        self.cat.stdout.read(1)
        return head[1].decode(), body

    def write(self, kind, body):
        code, o, e = run(["hash-object", "-t", kind, "-w", "--stdin"], self.cwd, stdin=body)
        if code:
            raise RuntimeError(f"git hash-object: {e.strip()}")
        return o.decode().strip()

    def entries(self, tree):
        """[(mode, name, sha)] of a tree object, in stored order."""
        _, body = self.read(tree)
        n, i, res = self.hexlen // 2, 0, []
        while i < len(body):
            sp, nul = body.index(b" ", i), body.index(b"\0", i)
            res.append((body[i:sp], body[sp + 1:nul], body[nul + 1:nul + 1 + n].hex()))
            i = nul + 1 + n
        return res

    def filter_tree(self, tree, paths):
        """TREE without the PATHS (tuples of names), written when it changed; the same sha when it did not."""
        key = (tree, paths)
        if key in self.trees:
            return self.trees[key]
        here = {p[0] for p in paths if len(p) == 1}
        below = {}
        for p in paths:
            if len(p) > 1:
                below.setdefault(p[0], []).append(p[1:])
        new, changed = [], False
        for mode, name, sha in self.entries(tree):
            dec = name.decode("utf-8", "surrogateescape")
            if dec in here:
                changed = True
                continue
            if dec in below and mode == b"40000":
                sub = self.filter_tree(sha, tuple(below[dec]))
                changed |= sub != sha
                sha = sub
            new.append((mode, name, sha))
        res = tree
        if changed:
            res = self.write("tree", b"".join(m + b" " + nm + b"\0" + bytes.fromhex(s) for m, nm, s in new))
        self.trees[key] = res
        return res

    def commit_tree(self, sha):
        if sha not in self.tree_of:
            _, body = self.read(sha)
            self.tree_of[sha] = body[5:5 + self.hexlen].decode()
        return self.tree_of[sha]

    def project(self, tip):
        """The projection of TIP (a commit sha), computed for its whole history, oldest first."""
        code, o, e = run(["rev-list", "--topo-order", "--reverse", "--parents", tip], self.cwd)
        if code:
            raise RuntimeError(f"git rev-list: {e.strip()}")
        for line in o.decode().splitlines():
            sha, *parents = line.split()
            if sha in self.commits:
                continue
            _, body = self.read(sha)
            head, sep, msg = body.partition(b"\n\n")
            tree = head[5:5 + self.hexlen].decode()
            self.tree_of[sha] = tree
            new_tree = self.filter_tree(tree, tuple(self.private))
            new_parents = list(dict.fromkeys(self.commits[p] for p in parents))
            if new_tree == tree and new_parents == parents:
                self.commits[sha] = sha
                continue
            if new_parents and len(new_parents) == 1 and new_tree == self.commit_tree(new_parents[0]) and \
                    (len(parents) > 1 or tree != self.commit_tree(parents[0])):
                self.commits[sha] = new_parents[0]  # it changed only PRIVATE paths (or merged nothing public)
                continue
            lines, skip = [], False
            for ln in head.split(b"\n"):
                if ln.startswith(b" ") and skip:
                    continue  # the continuation of a dropped multi-line header
                skip = False
                if ln.startswith((b"gpgsig", b"gpgsig-sha256 ", b"mergetag ")):
                    skip = True
                    continue
                if ln.startswith(b"tree "):
                    lines.append(b"tree " + new_tree.encode())
                    lines += [b"parent " + p.encode() for p in new_parents]
                elif not ln.startswith(b"parent "):
                    lines.append(ln)
            self.commits[sha] = self.write("commit", b"\n".join(lines) + sep + msg)
            self.tree_of[self.commits[sha]] = new_tree
        return self.commits[tip]


def project(tip, cwd):
    """The projection of the commit TIP in the repository at CWD."""
    p = Projector(cwd)
    try:
        return p.project(tip)
    finally:
        p.close()


def is_ancestor(a, b, cwd):
    return run(["merge-base", "--is-ancestor", a, b], cwd)[0] == 0


def tree_files(rev, cwd):
    """The paths of REV's tree, or None on a git error."""
    code, o, _ = run(["ls-tree", "-r", "-z", "--name-only", rev], cwd)
    return [x for x in o.decode("utf-8", "replace").split("\0") if x] if code == 0 else None


def blobs(rev, paths, cwd):
    """{path: text} of the utf-8 files PATHS of REV's tree (binary and unreadable ones are left out)."""
    paths = [x for x in paths if "\n" not in x]
    code, o, _ = run(["cat-file", "--batch"], cwd, stdin="".join(f"{rev}:{x}\n" for x in paths).encode("utf-8"))
    res, pos = {}, 0
    for x in paths:
        end = o.find(b"\n", pos)
        if code or end < 0:
            break
        head = o[pos:end].split()
        pos = end + 1
        if len(head) == 3 and head[1] == b"blob":
            size = int(head[2])
            try:
                res[x] = o[pos:pos + size].decode("utf-8")
            except UnicodeDecodeError:
                pass
            pos += size + 1
    return res


def allowlist(proj, cwd):
    """{kind: lowercased values} of the projection's _tools/tests_allowlist.txt (leak scan exceptions)."""
    allow = {}
    for ln in blobs(proj, [ALLOWLIST_PATH], cwd).get(ALLOWLIST_PATH, "").splitlines():
        ln = ln.split("#", 1)[0].strip()
        if ln and len(ln.split(None, 1)) == 2:
            kind, value = ln.split(None, 1)
            allow.setdefault(kind, set()).add(value.strip().lower())
    return allow


def tree_refusals(proj, files, cwd):
    """Causes: an internal root (a `_root.md` saying `visibility: internal`) or a _private or _cache path in the tree."""
    import kbcommon
    res = []
    for x in files:
        if FORBIDDEN_RE.search(x):
            res.append(f"the projection's tree holds {x}, a path under _private or _cache")
    for x, text in sorted(blobs(proj, [f for f in files if f.rsplit("/", 1)[-1] == kbcommon.ROOT_FILE], cwd).items()):
        if kbcommon._meta(text).get("visibility") == "internal":
            res.append(f"the projection's tree holds the internal root {x.rsplit('/', 1)[0] or '.'} ({x} says visibility: internal)")
    return res


def leak_refusals(proj, tip, files, cwd):
    """Causes: a leak-scan hit in a file the projection changes against the public tip TIP (every file when None).
    Vendor exports and snapshots (`/artifacts/`, `/_snapshots/`) are scanned for secrets only, as the tracked-file scan does."""
    import kbcommon
    if tip is None:
        changed = files
    else:
        code, o, _ = run(["diff", "--name-only", "-z", "--diff-filter=ACMR", tip, proj], cwd)
        if code:
            return [f"git diff {tip[:12]} {proj[:12]} failed"]
        changed = [x for x in o.decode("utf-8", "replace").split("\0") if x]
    allow, res = allowlist(proj, cwd), []
    for x, text in sorted(blobs(proj, changed, cwd).items()):
        vendored = "/artifacts/" in x or f"/{kbcommon.SNAPSHOTS}/" in x
        hits = kbcommon.leak_hits(URL_RX.sub("", text), allow)
        hits += [h for h in kbcommon.leak_hits(text, allow) if h[0] == "secret" and h not in hits]
        kinds = sorted({k for k, _ in hits if k == "secret" or not vendored})
        if kinds:
            res.append(f"{x} has a leak-scan hit ({', '.join(kinds)})")
    return res


def ci_refusals(src, url, cwd, run_ci=None):
    """Causes: the integration CI verdict of the source commit SRC (remote url URL) is not ok. RUN_CI runs the CLIs."""
    import ql_deliver
    from ql_base import run_cmd
    verdict, detail, _ = ql_deliver.ci_pipeline(url, src, run_ci or CI_RUN or run_cmd)
    return [] if verdict == "ok" else [f"the CI verdict of the source commit {src[:12]} is {verdict}: {detail}"]


class BridgeError(Exception):
    """A bridge refusal: CODE is the exit code (1 refused, 2 bad arguments), the message says why."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def bridge_range(pub, branch, cwd):
    """(main sha, tip sha, [commit shas oldest first]) of the public home PUB's main and BRANCH, both fetched into
    refs/remotes/PUB/. The commits are main..BRANCH. Raises BridgeError: 2 when PUB is no remote or main or BRANCH
    is missing there, 1 when a commit touches a PRIVATE path. Nothing is pushed to PUB."""
    if not pub or out(["remote", "get-url", pub], cwd) is None:
        raise BridgeError(2, f"no public remote (git config {CONFIG_KEY} <remote>); the bridge reads the branch from it")
    if out(["check-ref-format", "--branch", branch], cwd) is None:
        raise BridgeError(2, f"{branch!r} is not a valid branch name")
    tips = []
    for b in ("main", branch):
        code, _, e = run(["fetch", "--quiet", pub, f"+refs/heads/{b}:refs/remotes/{pub}/{b}"], cwd)
        if code:
            raise BridgeError(2, f"git fetch {pub} {b} failed: {e.strip()[-300:]}")
        tips.append(out(["rev-parse", "--verify", "--quiet", f"refs/remotes/{pub}/{b}^{{commit}}"], cwd))
    main, tip = tips
    if not main or not tip:
        raise BridgeError(2, f"{pub} has no commit for main or {branch}")
    rng = f"{main}..{tip}"
    bad = private_commits(rng, cwd)
    if bad is None:
        raise BridgeError(2, f"git error reading {pub}/main..{pub}/{branch}")
    if bad:
        raise BridgeError(1, f"{pub}/{branch} touches {', '.join(PRIVATE)} in {', '.join(b[:9] for b in bad)}: "
                             "the query log's store stays on the integration remote; nothing was bridged")
    commits = (out(["rev-list", "--reverse", rng], cwd) or "").split()
    return main, tip, commits


def cmd_publish(a, cwd):
    remote = a.remote or publish_remote(cwd)
    if not remote:
        print(f"note: no public remote (git config {CONFIG_KEY} <remote>); nothing published")
        return 0
    source = a.source or f"{integration_remote(cwd)}/main"
    src_remote, _, src_branch = source.partition("/")
    if not src_branch or out(["remote", "get-url", src_remote], cwd) is None or out(["remote", "get-url", remote], cwd) is None:
        print(f"refused: no remote {remote!r}, or the source {source!r} is not REMOTE/BRANCH of a remote")
        return 2
    if remote == src_remote:
        print(f"refused: the public remote {remote!r} is the source's remote; publish goes from integration to public")
        return 2
    for r, b in ((src_remote, src_branch), (remote, a.branch)):
        code, _, e = run(["fetch", "--quiet", r, f"+refs/heads/{b}:refs/remotes/{r}/{b}"], cwd)
        if code and not (r == remote and "couldn't find remote ref" in e):
            print(f"refused: git fetch {r} {b} failed: {e.strip()[-300:]}")
            return 2
    src = out(["rev-parse", "--verify", "--quiet", f"refs/remotes/{source}^{{commit}}"], cwd)
    if not src:
        print(f"refused: {source} has no commit")
        return 2
    try:
        proj = project(src, cwd)
    except RuntimeError as exc:
        print(f"refused: {exc}")
        return 2
    left = private_commits(proj, cwd)
    if left is None or left:
        print(f"refused: the projection {proj[:12]} still touches {', '.join(PRIVATE)} in {left}")
        return 1
    tip = out(["rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{a.branch}^{{commit}}"], cwd)
    print(f"source: {source} {src[:12]}; projection: {proj[:12]}" + (" (the same commit)" if src == proj else ""))
    print(f"public: {remote}/{a.branch} " + (tip[:12] if tip else "(none)"))
    if tip == proj:
        print("publish: nothing to do (the public home has the projection)")
        run(["update-ref", PUBLISHED_REF, proj], cwd)
        return 0
    ff = tip is None or is_ancestor(tip, proj, cwd)
    if not ff and not a.rewrite:
        print(f"refused: {remote}/{a.branch} {tip[:12]} is not an ancestor of the projection: commits were pushed there "
              f"directly, or it holds a history from before the projection. Bring them to {source} first, or pass "
              f"--rewrite to replace it (force push with lease)")
        return 1
    files = tree_files(proj, cwd)
    if files is None:
        print(f"refused: git ls-tree {proj[:12]} failed")
        return 2
    causes = tree_refusals(proj, files, cwd) + leak_refusals(proj, tip, files, cwd)
    causes += ci_refusals(src, out(["remote", "get-url", src_remote], cwd), cwd, getattr(a, "ci_run", None))
    if causes:
        for c in causes:
            print(f"refused: {c}")
        print("nothing pushed" + (" (dry run)" if a.dry_run else ""))
        return 1
    n = out(["rev-list", "--count", proj if tip is None else f"{tip}..{proj}"], cwd)
    how = "fast-forward" if ff else "rewrite (force with lease)"
    if a.dry_run:
        print(f"dry run: would push {proj[:12]} to {remote}/{a.branch}: {how}, {n} commit(s)")
        return 0
    args = ["push", remote, f"{proj}:refs/heads/{a.branch}"]
    if not ff:
        args.insert(1, f"--force-with-lease=refs/heads/{a.branch}:{tip}")
    code, o, e = run(args, cwd, env={"KB_GATE_DONE": "1"})  # the source was gated on integration; the guard still runs
    if code:
        print(f"push failed: {(o.decode() + e).strip()[-600:]}")
        return 1
    run(["update-ref", PUBLISHED_REF, proj], cwd)
    run(["update-ref", f"refs/remotes/{remote}/{a.branch}", proj], cwd)
    print(f"published: {proj[:12]} to {remote}/{a.branch}: {how}, {n} commit(s)")
    return 0


def cmd_publish_hook(a, cwd):
    """The SessionStart form of publish: silent without a public remote or when there is nothing to publish, prints only
    the refusal and push-failure lines of a run, and returns 0 whatever happened (a hook never breaks a session start)."""
    import contextlib, io
    try:
        if not (a.remote or publish_remote(cwd)):
            return 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_publish(a, cwd)
        for line in buf.getvalue().splitlines():
            if line.startswith(("refused:", "push failed:")):
                print(f"kb publish {line}")
    except Exception as exc:  # noqa: BLE001 - the hook must exit 0 on every outcome
        print(f"kb publish hook: {type(exc).__name__}: {exc}"[:300])
    return 0


def cmd_check_public(a, cwd):
    rev = a.rev or "HEAD"
    bad = private_commits(rev, cwd)
    if bad is None:
        print(f"check-public: git error reading {rev}")
        return 2
    for sha in bad:
        print(f"private: {sha[:12]} touches {', '.join(PRIVATE)}")
    print(f"check-public: {'clean' if not bad else 'FAILED'} ({rev}; kept off the public home: {', '.join(PRIVATE)})")
    return 1 if bad else 0


def guard_push(remote, url, refs, cwd):
    """The pre-push guard: [(ref, reason)] of pushed refs (local ref, local sha) that would carry a PRIVATE path to a
    public remote. Deletes are skipped."""
    if not is_public(remote, cwd, url):
        return []
    res = []
    for ref, sha in refs:
        if ZERO_RE.match(sha):
            continue
        bad = private_commits(sha, cwd, limit=3)
        if bad is None or bad:
            res.append((ref, f"its history touches {', '.join(PRIVATE)}" + (f" ({', '.join(b[:9] for b in bad)})"
                                                                              if bad else " (git error)")))
    return res


if __name__ == "__main__":
    sys.exit("run it as: python3 _tools/kbgit.py publish | check-public")
