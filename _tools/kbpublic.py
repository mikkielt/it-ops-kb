#!/usr/bin/env python3
"""The public home (stdlib only): what never reaches it, which remote it is, and the history published there.

  kbgit.py publish [--remote R] [--source REMOTE/main] [--branch main] [--dry-run] [--rewrite]
  kbgit.py check-public [REV]
  kbgit.py bridge BRANCH [--push] [--dry-run] [--remote R]

The integration remote (git config kb.integrationRemote, default `origin`) holds everything; the public home (GitHub) holds the same history without the
PRIVATE paths: the query log's store `kb/_querylog/` and every `_logs.csv` (a root's observed signals, in any
directory) are kept on the integration remote only. Both hosts cannot carry
the same `main`, so the public home gets a projection of it:

  projection  every commit of the source is rewritten with the PRIVATE paths removed from its tree and its parents
              replaced by their projections; its author, committer, dates and message stay byte for byte (a
              signature goes, since it no longer matches). A commit whose tree carries no PRIVATE path and whose
              parents are unchanged is its own projection, so the history before the query log keeps its hashes (and
              the census tags stay valid). A commit that changed only PRIVATE paths becomes nothing: its projection is
              its parent's. The projection is a pure function of the source history, so every clone computes the same
              commits and each publish fast-forwards the last one. Each source commit's projection is cached in
              _cache/publish/ (projection_cache), so a publish projects only the commits it has not seen; objects are
              hashed here and written in one `git hash-object --stdin-paths` per kind.
  publish     fetches the source and the public home, projects the source, verifies the projection carries no
              PRIVATE path, checks its safety (below), and pushes it to the public home's BRANCH as a fast-forward. When the public home's branch
              is not an ancestor (a commit pushed there directly, or a history from before the projection) it refuses,
              exit 1, unless --rewrite, which pushes with --force-with-lease against the tip it fetched: the one-time
              move to the projection, or a decision to drop what was pushed there directly. `refs/kb/published` keeps
              the last projection. Without a public remote it prints a note and exits 0.
  safety      after the fast-forward check and before the push (a --dry-run runs them all and pushes nothing) every
              cause is reported, exit 1, in this order. The checks cover every commit to be pushed (tip..projection,
              the whole projected history when there is no tip), each by what it adds or changes against its first
              parent, so a later commit that deletes a path or a value does not hide it: a commit writes a path under
              a `_private` or `_cache` directory (any depth), or under a root whose `_root.md` says `visibility:
              internal` in any commit of the range, at the tip or in the projection (the projection's tree is checked
              too, for what the tip already holds); a file a commit writes has a leak-scan hit (kbcommon.leak_hits,
              allowing _tools/tests_allowlist.txt of the commit and of the projection, read as the tracked-file scan
              reads it: a vendor export, snapshot or pinned artifact for secrets only) that neither the parent's nor
              the tip's version of the file already holds and whose value no file of the tip holds (already public;
              the tip's values are scanned once per tip and cached in _cache/publish/, as digests); the integration
              CI verdict of the source commit (ql_deliver.ci_pipeline on the source remote's url) is not `ok`: red, pending,
              unverified, none, or skip when glab or gh cannot read it. Content is refused, never filtered.
              Each commit's leak verdict is cached in _cache/publish/ per public tip, projection allowlist and pinned artifacts, so a
              range is scanned once; `publish --hook` leaves a range with more than HOOK_BOUND uncached commits to a
              publish by hand (one line, exit 0, nothing checked or pushed).
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
import csv, hashlib, io, json, os, re, subprocess, sys, tempfile
from pathlib import Path

PRIVATE = ("kb/_querylog",)  # repository paths kept on the integration remote only (kb/_self/git.md, Public home)
PRIVATE_NAMES = ("_logs.csv",)  # file names kept there too, in any directory: a root's observed signals (content-rules.md, Logs)
PRIVATE_SPECS = (*PRIVATE, *(f":(glob)**/{n}" for n in PRIVATE_NAMES))  # `git log --` pathspecs of everything kept off
PRIVATE_LABEL = ", ".join((*PRIVATE, *(f"{n} (in any directory)" for n in PRIVATE_NAMES)))  # what a refusal names
CONFIG_KEY = "kb.publishRemote"
INTEGRATION_KEY = "kb.integrationRemote"
CLONE_REMOTE = "origin"  # what `git clone` names its source: the integration remote unless INTEGRATION_KEY says otherwise
PUBLISHED_REF = "refs/kb/published"
NO_HOOK_ENV = "KB_NO_PUBLISH_HOOK"  # a non-empty value: publish --hook does nothing (the unattended manager session exports it)
ZERO_RE = re.compile(r"^0+$")
FORBIDDEN_RE = re.compile(r"(^|/)(_private|_cache)(/|$)")
ALLOWLIST_PATH = "_tools/tests_allowlist.txt"
URL_RX = re.compile(r"(?:https?|ssh|git)://\S+|(?<![\w.%+-])git@[\w.-]+:[\w./~-]+|\bssh(?:\s+-\w+)*\s+git@[\w.-]+")
CACHE_DIR = ("_cache", "publish")  # the per-clone scan cache under the repository, never committed (its own .gitignore)
PROJECTION_FORM = 1  # the projection's form: a change to how commits are projected bumps it, so no older cache is read
HOOK_BOUND = 150  # uncached commits publish --hook checks at most; a longer range is left to a publish by hand (git.md)
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
    code, o, _ = run(["log", f"-{limit}", "--format=%H", rev, "--", *PRIVATE_SPECS], cwd)
    return o.decode().split() if code == 0 else None


class Projector:
    """Projects commits of the repository at CWD: projection(rev) is the commit of REV's history without PRIVATE."""

    def __init__(self, cwd):
        self.cwd = cwd
        self.hexlen = 64 if out(["rev-parse", "--show-object-format"], cwd) == "sha256" else 40
        self.cat = subprocess.Popen(["git", "cat-file", "--batch"], cwd=cwd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
        self.trees, self.commits, self.tree_of, self.pending = {}, {}, {}, {}
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
        """The sha of the object KIND with BODY, computed here; flush() writes it with the others."""
        algo = "sha256" if self.hexlen == 64 else "sha1"
        sha = hashlib.new(algo, f"{kind} {len(body)}\0".encode() + body).hexdigest()
        self.pending.setdefault(kind, {})[sha] = body
        return sha

    def flush(self):
        """Writes the pending objects, one `git hash-object -w --stdin-paths` per kind (trees before the commits that
        name them), and checks git computed the sha write() gave each."""
        with tempfile.TemporaryDirectory() as d:
            for kind in ("tree", "commit"):
                objs, paths = self.pending.pop(kind, {}), []
                for i, body in enumerate(objs.values()):
                    paths.append(Path(d, f"{kind}{i}"))
                    paths[-1].write_bytes(body)
                if not objs:
                    continue
                code, o, e = run(["hash-object", "-t", kind, "-w", "--no-filters", "--stdin-paths"], self.cwd,
                                 stdin="".join(f"{x}\n" for x in paths).encode("utf-8"))
                if code or o.decode().split() != list(objs):
                    raise RuntimeError(f"git hash-object: {e.strip() or 'a written object has another sha'}")

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
        """TREE without the PATHS (tuples of names) and without every file named in PRIVATE_NAMES, at any depth,
        written when it changed; the same sha when it did not. A directory that held nothing else goes too."""
        return self.filtered(tree, paths) or self.write("tree", b"")

    def filtered(self, tree, paths):
        """filter_tree's sha, or None when nothing is left of TREE."""
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
            if dec in here or (mode not in (b"40000", b"160000") and dec in PRIVATE_NAMES):
                changed = True
                continue
            if mode == b"40000":
                sub = self.filtered(sha, tuple(below.get(dec, ())))
                changed |= sub != sha
                if sub is None:
                    continue
                sha = sub
            new.append((mode, name, sha))
        res = tree
        if changed:
            res = self.write("tree", b"".join(m + b" " + nm + b"\0" + bytes.fromhex(s) for m, nm, s in new)) if new else None
        self.trees[key] = res
        return res

    def commit_tree(self, sha):
        if sha not in self.tree_of:
            _, body = self.read(sha)
            self.tree_of[sha] = body[5:5 + self.hexlen].decode()
        return self.tree_of[sha]

    def present(self, shas):
        """The SHAS that are commit objects of the repository (one `git cat-file --batch-check`)."""
        shas = list(shas)
        if not shas:
            return set()
        code, o, _ = run(["cat-file", "--batch-check"], self.cwd, stdin="".join(f"{x}\n" for x in shas).encode())
        rows = [ln.split() for ln in o.decode("utf-8", "replace").splitlines()] if code == 0 else []
        return {r[0] for r in rows if len(r) == 3 and r[1] == "commit"}

    def project(self, tip, cached=None):
        """The projection of TIP (a commit sha), computed for its whole history, oldest first. CACHED ({source sha:
        projected sha}, an earlier run's) gives the projection of each commit it names whose projected commit is still in
        the object store; the others are computed."""
        code, o, e = run(["rev-list", "--topo-order", "--reverse", "--parents", tip], self.cwd)
        if code:
            raise RuntimeError(f"git rev-list: {e.strip()}")
        rows = [line.split() for line in o.decode().splitlines()]
        cached = cached or {}
        known = self.present({cached[r[0]] for r in rows if cached.get(r[0], r[0]) != r[0]})
        for sha, *parents in rows:
            if sha in self.commits:
                continue
            got = cached.get(sha)
            self.commits[sha] = got if got is not None and (got == sha or got in known) else self.rewrite(sha, parents)
        self.flush()
        return self.commits[tip]

    def rewrite(self, sha, parents):
        """The projection of the commit SHA whose PARENTS are projected already."""
        _, body = self.read(sha)
        head, sep, msg = body.partition(b"\n\n")
        tree = head[5:5 + self.hexlen].decode()
        self.tree_of[sha] = tree
        new_tree = self.filter_tree(tree, tuple(self.private))
        new_parents = list(dict.fromkeys(self.commits[p] for p in parents))
        if new_tree == tree and new_parents == parents:
            return sha
        if new_parents and len(new_parents) == 1 and new_tree == self.commit_tree(new_parents[0]) and \
                (len(parents) > 1 or tree != self.commit_tree(parents[0])):
            return new_parents[0]  # it changed only PRIVATE paths (or merged nothing public)
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
        res = self.write("commit", b"\n".join(lines) + sep + msg)
        self.tree_of[res] = new_tree
        return res

def projection_cache(hexlen):
    """The name of the projection cache file: one per PRIVATE, PROJECTION_FORM and object format, so a change of what the
    projection removes or how never reads an older cache."""
    key = json.dumps([PROJECTION_FORM, list(PRIVATE), list(PRIVATE_NAMES), hexlen]).encode("utf-8")
    return f"projection-{hashlib.sha256(key).hexdigest()[:16]}.json"


def project(tip, cwd, sources=None):
    """The projection of the commit TIP in the repository at CWD. SOURCES, a dict, gets {projected sha: the oldest
    source commit projected to it}. The projection of each source commit is cached in CACHE_DIR ({source sha: projected
    sha}, projection_cache), so a later run projects only the commits not seen before; an entry whose projected commit
    is missing from the object store is computed again, and a missing or corrupt cache means the whole history."""
    p = Projector(cwd)
    name = projection_cache(p.hexlen)
    got, sha_rx = cache_load(cwd, name), re.compile(f"[0-9a-f]{{{p.hexlen}}}")
    cached = got if isinstance(got, dict) and all(isinstance(v, str) and sha_rx.fullmatch(k) and sha_rx.fullmatch(v)
                                                  for k, v in got.items()) else {}
    try:
        res = p.project(tip, cached)
    finally:
        p.close()
    if any(cached.get(s) != c for s, c in p.commits.items()):
        cache_save(cwd, name, {**cached, **p.commits}, "projection-")
    if sources is not None:
        for s, c in p.commits.items():
            sources.setdefault(c, s)
    return res

def is_ancestor(a, b, cwd):
    return run(["merge-base", "--is-ancestor", a, b], cwd)[0] == 0


def tree_files(rev, cwd):
    """The paths of REV's tree, or None on a git error."""
    code, o, _ = run(["ls-tree", "-r", "-z", "--name-only", rev], cwd)
    return [x for x in o.decode("utf-8", "replace").split("\0") if x] if code == 0 else None


def texts(specs, cwd, chunk=2000):
    """{spec: text} of the utf-8 blobs SPECS (object names: a sha or REV:PATH), read CHUNK at a time through one
    `git cat-file --batch` each; binary, missing and unreadable ones are left out."""
    specs = [x for x in dict.fromkeys(specs) if "\n" not in x]
    res = {}
    for i in range(0, len(specs), chunk):
        part = specs[i:i + chunk]
        code, o, _ = run(["cat-file", "--batch"], cwd, stdin="".join(f"{x}\n" for x in part).encode("utf-8"))
        pos = 0
        for x in part:
            end = o.find(b"\n", pos)
            if code or end < 0:
                break
            head = o[pos:end].split()
            pos = end + 1
            if len(head) == 3:
                size = int(head[2])
                if head[1] == b"blob":
                    try:
                        res[x] = o[pos:pos + size].decode("utf-8")
                    except UnicodeDecodeError:
                        pass
                pos += size + 1
    return res


def blobs(rev, paths, cwd):
    """{path: text} of the utf-8 files PATHS of REV's tree (binary and unreadable ones are left out)."""
    got = texts([f"{rev}:{x}" for x in paths], cwd)
    return {x: got[f"{rev}:{x}"] for x in paths if f"{rev}:{x}" in got}


def parse_allowlist(text):
    """{kind: lowercased values} of the text of a _tools/tests_allowlist.txt (leak scan exceptions)."""
    allow = {}
    for ln in text.splitlines():
        ln = ln.split("#", 1)[0].strip()
        if ln and len(ln.split(None, 1)) == 2:
            kind, value = ln.split(None, 1)
            allow.setdefault(kind, set()).add(value.strip().lower())
    return allow


def allowlist(proj, cwd):
    """{kind: lowercased values} of the projection's _tools/tests_allowlist.txt (leak scan exceptions)."""
    return parse_allowlist(blobs(proj, [ALLOWLIST_PATH], cwd).get(ALLOWLIST_PATH, ""))


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


def pinned_paths(proj, files, cwd):
    """{path} of the pinned artifacts the projection's roots list (each `_artifacts.csv` of FILES, PROJ's tree, names
    its paths relative to the root it sits in): the tracked-file scan reads them for secrets only."""
    import kbcommon
    res = set()
    for x, text in blobs(proj, [f for f in files if f.rsplit("/", 1)[-1] == kbcommon.ARTIFACTS], cwd).items():
        root = root_dir(x)
        for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff"), newline="")):
            if row.get("path"):
                res.add(f"{root}/{row['path']}" if root else row["path"])
    return res


def file_hits(path, text, allow, pinned=()):
    """[(kind, value)] of the leak scan of the file PATH with TEXT, as the tracked-file scan reads a file: urls are
    stripped except for secrets; vendor exports, snapshots (`/artifacts/`, `/_snapshots/`) and the pinned artifacts
    PINNED lists are scanned for secrets only; a GUID counts in every other text file."""
    import kbcommon
    vendored = "/artifacts/" in path or f"/{kbcommon.SNAPSHOTS}/" in path or path in pinned
    hits = kbcommon.leak_hits(URL_RX.sub("", text), allow)
    hits += [h for h in kbcommon.leak_hits(text, allow) if h[0] == "secret" and h not in hits]
    return [h for h in hits if h[0] == "secret" or not vendored]


def cache_load(cwd, name):
    """The JSON of the cache file NAME under CACHE_DIR, or None when it is missing or unreadable (then recomputed)."""
    try:
        return json.loads(Path(cwd, *CACHE_DIR, name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cache_save(cwd, name, data, prefix):
    """Writes DATA as the cache file NAME and removes the other files starting with PREFIX (an older tip's). The
    directory ignores itself (a `.gitignore` of `*`), so a clone without `_cache/` in its own ignores never commits it.
    A write that fails is left out: the cache only saves time."""
    d = Path(cwd, *CACHE_DIR)
    try:
        d.mkdir(parents=True, exist_ok=True)
        if not (d / ".gitignore").exists():
            (d / ".gitignore").write_text("*\n", encoding="utf-8", newline="\n")
        for old in d.glob(f"{prefix}*.json"):
            if old.name != name:
                old.unlink()
        tmp = d / f"{name}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(data), encoding="utf-8", newline="\n")
        tmp.replace(d / name)
    except OSError:
        pass


def hit_key(hit):
    """A digest of a leak-scan hit (kind, value): the cache keeps digests, never the values."""
    return hashlib.sha256("\0".join(hit).encode("utf-8")).hexdigest()


def public_values(tip, cwd):
    """{hit_key} of every leak-scan hit (file_hits without an allowlist) in any file of the public tip TIP's tree: the
    values the public home already holds, whichever file holds them. Scanned once per tip and cached in
    CACHE_DIR/public-<tip>.json; empty without a tip. Raises RuntimeError on a git error."""
    if not tip:
        return set()
    name = f"public-{tip}.json"
    got = cache_load(cwd, name)
    if isinstance(got, list) and all(isinstance(x, str) for x in got):
        return set(got)
    files = tree_files(tip, cwd)
    if files is None:
        raise RuntimeError(f"git ls-tree {tip[:12]} failed")
    res = {hit_key(h) for x, text in blobs(tip, files, cwd).items() for h in file_hits(x, text, {})}
    cache_save(cwd, name, sorted(res), "public-")
    return res


def history_changes(proj, tip, cwd):
    """[(commit sha, [(status, old blob, new blob, path)])] of the commits TIP..PROJ (all of PROJ's history when TIP is
    None), oldest first, from one `git log --raw` pass: a rename is a delete and an add, a merge is diffed against its
    first parent. Raises RuntimeError on a git error."""
    code, o, e = run(["log", "--topo-order", "--reverse", "--no-renames", "--raw", "-z", "--no-abbrev", "--root",
                      "--diff-merges=first-parent", "--format=%x01%H", proj if tip is None else f"{tip}..{proj}"], cwd)
    if code:
        raise RuntimeError(f"git log: {e.strip()}")
    res = []
    for chunk in o.split(b"\x01")[1:]:
        sha, _, rest = chunk.partition(b"\0")
        fields = rest.lstrip(b"\n").split(b"\0")
        changes = []
        for meta, path in zip(fields[0::2], fields[1::2]):
            _, _, old, new, status = meta.lstrip(b":").split()
            changes.append((status.decode()[:1], old.decode(), new.decode(), path.decode("utf-8", "replace")))
        res.append((sha.decode(), changes))
    return res


def root_dir(path):
    """The root directory of the `_root.md` at PATH ('' at the top)."""
    return path.rsplit("/", 1)[0] if "/" in path else ""


class LongRange(Exception):
    """The range holds more uncached commits than the bound history_refusals was given: N of them."""

    def __init__(self, n):
        super().__init__(n)
        self.n = n


def leak_verdicts(written, proj, tip, final, cwd, pinned=frozenset()):
    """{commit: [(path, kinds)]} of the leak check of WRITTEN [(commit, old blob, new blob, path)], the files the
    commits write: a hit in the lines a commit adds that the public tip holds in no file (public_values), and neither
    the parent's nor TIP's version of the file holds, allowing FINAL (PROJ's allowlist) and the commit's own, and reading PINNED (pinned_paths) for secrets only. A commit
    with no hit is left out."""
    # scan only the lines a commit adds (the new version's lines its parent's version lacks), a chunk of writes at a
    # time; the whole versions are read only for the files whose added lines hit
    public = public_values(tip, cwd)
    pairs, added = list(dict.fromkeys((old, new, x) for c, old, new, x in written)), {}
    for i in range(0, len(pairs), 500):
        part = pairs[i:i + 500]
        got = texts([s for old, new, x in part for s in (old, new) if not ZERO_RE.match(s)], cwd)
        for old, new, x in part:
            if new in got:
                seen = set(got.get(old, "").splitlines())
                text = "\n".join(ln for ln in got[new].splitlines() if ln not in seen)
                if any(hit_key(h) not in public for h in file_hits(x, text, {}, pinned)):
                    added[old, new, x] = text
    rows = [(c, old, new, x) for c, old, new, x in written if (old, new, x) in added]
    if not rows:
        return {}
    olds = texts([old for c, old, new, x in rows if not ZERO_RE.match(old)], cwd)
    at_tip = blobs(tip, [x for c, old, new, x in rows], cwd) if tip else {}
    commit_allow = texts([f"{c}:{ALLOWLIST_PATH}" for c, *_ in rows], cwd)
    res = {}
    for c, old, new, x in rows:
        known = set()
        for text in (olds.get(old), at_tip.get(x)):
            if text is not None:
                known |= set(file_hits(x, text, {}, pinned))
        allow = {k: set(vals) for k, vals in final.items()}
        for k, vals in parse_allowlist(commit_allow.get(f"{c}:{ALLOWLIST_PATH}", "")).items():
            allow.setdefault(k, set()).update(vals)
        kinds = sorted({k for k, val in file_hits(x, added[old, new, x], allow, pinned)
                        if (k, val) not in known and hit_key((k, val)) not in public})
        if kinds:
            res.setdefault(c, []).append((x, kinds))
    return res


def history_refusals(proj, tip, files, cwd, sources=None, bound=None):
    """(tree causes, leak causes, paths named) of the commits publish would push: TIP..PROJ, all of PROJ's history when
    TIP is None; FILES are the paths of PROJ's tree. A cause names the source commit (SOURCES: {projected sha: source
    sha}, from project()) and the projected one when they differ. Each commit is checked by what it adds or changes
    against its (first) parent, so a later commit that deletes a path or a value does not hide it:
      tree  a path under a `_private` or `_cache` directory, or a path under a root that is internal (its `_root.md`
            says `visibility: internal`) in any commit of the range, at TIP or at PROJ;
      leak  a leak-scan hit that neither the parent's version nor TIP's version of the file holds, and whose value no
            file of TIP holds (public_values: already public), allowing the _tools/tests_allowlist.txt of the commit
            and of PROJ.
    The leak verdict of each commit (its causes, often none) is cached per commit in
    CACHE_DIR/verdicts-<TIP>-<digest of PROJ's allowlist and pinned artifacts>.json, the inputs it depends on beside the commit's own, so a
    range already checked costs one `git log` the next time. With BOUND, raises LongRange before any scan when more
    than BOUND commits of the range have no cached verdict. Raises RuntimeError on a git error."""
    import kbcommon
    sources = sources or {}
    name = lambda c: sources.get(c, c)[:12] + (f" (projected {c[:12]})" if sources.get(c, c) != c else "")  # noqa: E731
    changes = history_changes(proj, tip, cwd)
    final = blobs(proj, [ALLOWLIST_PATH], cwd).get(ALLOWLIST_PATH, "")
    pinned = pinned_paths(proj, files, cwd)
    inputs = "\0".join([final, *sorted(pinned)])
    vname = f"verdicts-{tip or 'none'}-{hashlib.sha256(inputs.encode('utf-8')).hexdigest()[:16]}.json"
    got = cache_load(cwd, vname)
    verdicts = {c: v for c, v in (got.items() if isinstance(got, dict) else ())
                if isinstance(v, list) and all(isinstance(h, list) and len(h) == 2 for h in v)}
    todo = {c for c, _ in changes if c not in verdicts}
    if bound is not None and len(todo) > bound:
        raise LongRange(len(todo))
    written = [(c, old, new, x) for c, ch in changes for st, old, new, x in ch if st != "D"]
    is_root = lambda x: x.rsplit("/", 1)[-1] == kbcommon.ROOT_FILE  # noqa: E731
    roots = {}  # object name -> the _root.md paths it is (one blob can be several roots' file)
    for c, old, new, x in written:
        if is_root(x):
            roots.setdefault(new, set()).add(x)
    for rev, paths in ((tip, tree_files(tip, cwd) if tip else []), (proj, files)):
        for x in paths or []:
            if is_root(x):
                roots.setdefault(f"{rev}:{x}", set()).add(x)
    internal = sorted({root_dir(x) for spec, text in texts(list(roots), cwd).items()
                       if kbcommon._meta(text).get("visibility") == "internal" for x in roots[spec]})
    tree, named, under = [], set(), {}
    for c, old, new, x in written:
        if FORBIDDEN_RE.search(x):
            tree.append(f"commit {name(c)} holds {x}, a path under _private or _cache")
            named.add(x)
        for r in internal:
            if not r or x.startswith(r + "/"):
                under.setdefault((c, r), []).append(x)
                named.add(f"{r}/{kbcommon.ROOT_FILE}" if r else kbcommon.ROOT_FILE)
                break
    for (c, r), xs in under.items():
        tree.append(f"commit {name(c)} writes {len(xs)} path(s) under the internal root {r or '.'} "
                    f"({r + '/' if r else ''}{kbcommon.ROOT_FILE} says visibility: internal), e.g. {xs[0]}")
    if todo:
        found = leak_verdicts([w for w in written if w[0] in todo], proj, tip, parse_allowlist(final), cwd, pinned)
        verdicts.update({c: found.get(c, []) for c in todo})
        cache_save(cwd, vname, verdicts, "verdicts-")
    leak = [f"commit {name(c)}: {x} has a leak-scan hit ({', '.join(kinds)})" for c, _ in changes for x, kinds in verdicts[c]]
    return tree, leak, named


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
        raise BridgeError(1, f"{pub}/{branch} touches {PRIVATE_LABEL} in {', '.join(b[:9] for b in bad)}: "
                             "these stay on the integration remote; nothing was bridged")
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
    sources = {}
    try:
        proj = project(src, cwd, sources)
    except RuntimeError as exc:
        print(f"refused: {exc}")
        return 2
    left = private_commits(proj, cwd)
    if left is None or left:
        print(f"refused: the projection {proj[:12]} still touches {PRIVATE_LABEL} in {left}")
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
    try:
        tree, leak, named = history_refusals(proj, tip, files, cwd, sources, HOOK_BOUND if getattr(a, "hook", False) else None)
    except LongRange as exc:
        print(f"publish by hand: {exc.n} commits to check (python3 _tools/kbgit.py publish)")
        return 0
    except RuntimeError as exc:
        print(f"refused: {exc}")
        return 2
    causes = tree + tree_refusals(proj, [x for x in files if x not in named], cwd) + leak  # a path the tip holds already
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
    the refusal and push-failure lines of a run, and returns 0 whatever happened (a hook never breaks a session start).
    A range with more than HOOK_BOUND commits whose verdict is not cached is not checked or pushed: one line asks for a
    publish by hand, which has no bound and fills the cache."""
    import contextlib, io
    try:
        if os.environ.get(NO_HOOK_ENV) or not (a.remote or publish_remote(cwd)):
            return 0  # a session started with NO_HOOK_ENV never publishes from its hook
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_publish(a, cwd)
        for line in buf.getvalue().splitlines():
            if line.startswith(("refused:", "push failed:")):
                print(f"kb publish {line}")
            elif line.startswith("publish by hand:"):
                print(f"kb publish: {line}")
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
        print(f"private: {sha[:12]} touches {PRIVATE_LABEL}")
    print(f"check-public: {'clean' if not bad else 'FAILED'} ({rev}; kept off the public home: {PRIVATE_LABEL})")
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
            res.append((ref, f"its history touches {PRIVATE_LABEL}" + (f" ({', '.join(b[:9] for b in bad)})"
                                                                              if bad else " (git error)")))
    return res


if __name__ == "__main__":
    sys.exit("run it as: python3 _tools/kbgit.py publish | check-public")
