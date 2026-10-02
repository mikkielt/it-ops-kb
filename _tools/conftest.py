"""Shared pytest setup for the kb tests. Run them with `python3 _tools/tests.py` (uv installs pytest and pytest-xdist
from pyproject.toml's dev group) or `uv run pytest`.

  Repo(path, env)       one throwaway directory: git(), run_git(), rev(), tool(), kbgit(), read(), write(), append()
  querylog_env(data)    the environment of a kb_hook.py or kb_ask.py run on this clone: its query log rows go under
                        `data`, never into the clone's own spool, in mode `local` (a config.json it writes unless one
                        is there; `mode=None` writes none), so a distill it starts never delivers to a real remote
  git_env(**extra)      the environment of a git scenario: no global or system git config, a fixed author, and none
                        of the variables that would leak the outer repository, a CI run or a verification date into it
  GIT_LOCATION          the git variables that name a repository (GIT_DIR, GIT_WORK_TREE, ...): removed from
                        os.environ at import, so a run a git hook starts never acts on the hook's repository
  copy_kb(dst, skip, copy)  a copy of the kb's working tree without .git, _cache, _private, __pycache__ (and `skip`):
                        hard links of a per-process template for the files in LINKED_DIRS, real copies of the rest (and
                        of the paths in `copy`); an autouse session fixture fails the run when a write went through a
                        link into the template
  kb_seed               (fixture) a bare repository of a kb copy, committed once per run and shared by the xdist
                        workers: the origin a git scenario clones
  requires_git          skip marker for a test that needs the git binary
  marker `git`          a scenario in throwaway git repositories (about 10 s each); `-m "not git"` leaves them out,
                        which is what KB_TESTS_FAST=1 (kbgit.py sync's gate) does
  marker `stress`       test_stress.py: stress_test.py runs it, tests.py leaves it out
  SOURCES_HEADER        the header line of _sources.csv
  P(rel)                a path relative to the public root as a path relative to the repository (kbcommon.repo_rel):
                        what a scenario passes to Repo.write/read or git for a ledger, article or retrieval data file
  D(rel)                P() of a retrieval data file (signals.csv, lookup_eval.csv, doc2query/expansions.csv, ...)
  Q(rel)                the qualified path of a public-root file (`public/<rel>`): what the read tools print
  SELF_REL              the kb's own docs directory relative to the repository (`_self`)
  timeout_s(seconds)    a subprocess timeout set on the project's Windows host, times KB_TEST_TIMEOUT_FACTOR (default
                        1, at least 1; kb-tests-windows sets 3): the limit follows a slower host
  run(*args), tracked(), text(rel), pinned(), authored(), allowlist(), hits(...), fmt(...), URL_RX, ALLOWLIST
                        what test_kb_cohesion.py, test_kb_lookup.py, test_kb_ids.py and test_kb_leaks.py share:
                        a tool run, the tracked files and their text, the pinned and authored subsets, the leak
                        scan's reviewed allowlist and its pattern search
"""
import csv, functools, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
os.environ.pop("KB_ROOTS", None)  # the suite tests this repository; test_kb_root.py sets it per call
# The variables that point git at one repository: `git rev-parse --local-env-vars` (what git itself unsets when it
# enters another repository) without its GIT_CONFIG* ones (CI passes safe.directory in GIT_CONFIG_COUNT), plus
# GIT_NAMESPACE. A git hook sets GIT_DIR (absolute in a worktree), and a run it starts inherits it: every git a test
# runs, whatever its cwd, would act on the real repository, and census.repo_dir's
# `fetch --force origin +refs/heads/*:refs/heads/*` would overwrite its branches and tags. So they go before any test.
GIT_LOCATION = ("GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_GRAFT_FILE", "GIT_SHALLOW_FILE",
                "GIT_REPLACE_REF_BASE", "GIT_NO_REPLACE_OBJECTS", "GIT_PREFIX", "GIT_NAMESPACE")
for _k in GIT_LOCATION:
    os.environ.pop(_k, None)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import kbcommon  # noqa: E402


def P(rel):
    return kbcommon.repo_rel(rel, kbcommon.PUBLIC)


def Q(rel):
    return kbcommon.qualify(kbcommon.public(), rel)


def D(rel):
    return P(kbcommon.data_rel(rel))


SELF_REL = kbcommon.repo_rel(kbcommon.SELF)

GIT = shutil.which("git")
requires_git = pytest.mark.skipif(not GIT, reason="git is not installed")
SOURCES_HEADER = "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
LEAKY = ("KB_VERIFIED", "KB_TESTS_FAST", "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", *GIT_LOCATION)


TIMEOUT_FACTOR_VAR = "KB_TEST_TIMEOUT_FACTOR"


def timeout_factor(env=None):
    """KB_TEST_TIMEOUT_FACTOR (default 1): how many times slower than the project's Windows host the run's host is,
    for the subprocess timeouts set there. A number of at least 1, else ValueError: a smaller one would shorten them."""
    raw = (os.environ if env is None else env).get(TIMEOUT_FACTOR_VAR, "").strip() or "1"
    try:
        factor = float(raw)
    except ValueError:
        factor = None
    if factor is None or not factor >= 1 or factor == float("inf"):
        raise ValueError(f"{TIMEOUT_FACTOR_VAR}={raw!r}: need a number of at least 1")
    return factor


def timeout_s(seconds):
    """A test's subprocess timeout, set on the project's Windows host, times KB_TEST_TIMEOUT_FACTOR: kb-tests-windows
    (a Hyper-V container, about 3 times slower) sets it, so the limit follows the host instead of being raised for all."""
    return seconds * timeout_factor()


def pytest_configure(config):
    try:
        timeout_factor()
    except ValueError as e:
        raise pytest.UsageError(str(e)) from None
    config.addinivalue_line("markers", "git: a scenario in throwaway git repositories (left out by -m 'not git')")
    config.addinivalue_line("markers", "stress: the stress suite, test_stress.py (stress_test.py runs it; tests.py leaves it out)")


def querylog_env(data, home=KB, base=None, mode="local"):
    """The environment of a tool run whose query log rows must not reach the spool of the clone at `home`: capture
    writes as the plugin at `home` would, under `data` (querylog/spool/), while KB_INDEX keeps the pack index in
    `home`'s _cache, where it lives without the plugin variables.

    The plugin's config file (data/querylog/config.json) pins `mode` unless the test wrote one first: with none the
    mode is `auto`, whose distill delivers from a plugin host (ql_deliver.host_push), and on a host with the plugin
    installed it would clone the install source and push the test's entries. `mode=None` writes no file, for a test
    of the default itself that starts no distill; a test of delivery writes its own config and points the install
    source at a local bare repository."""
    if mode is not None:
        cfg = Path(data) / "querylog" / "config.json"
        if not cfg.exists():
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(json.dumps({"mode": mode}), encoding="utf-8", newline="\n")
    env = dict(os.environ if base is None else base)
    env.update(CLAUDE_PLUGIN_ROOT=str(home), CLAUDE_PLUGIN_DATA=str(data),
               KB_INDEX=env.get("KB_INDEX") or os.path.join(str(home), "_cache"))
    return env


def git_env(**extra):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    for k in LEAKY:
        env.pop(k, None)
    env.update(extra)
    # No automatic maintenance (gc --auto, maintenance run --auto) in a throwaway repository: appended after the
    # caller's GIT_CONFIG_COUNT entries (CI's safe.directory), never replacing them.
    try:
        n = max(int(env.get("GIT_CONFIG_COUNT") or 0), 0)
    except ValueError:
        n = 0
    for k, v in (("gc.auto", "0"), ("maintenance.auto", "false")):
        env[f"GIT_CONFIG_KEY_{n}"], env[f"GIT_CONFIG_VALUE_{n}"] = k, v
        n += 1
    env["GIT_CONFIG_COUNT"] = str(n)
    return env


# Directories whose files tests do not write through a kb copy: a copy links them. A test that writes into one passes
# `copy=` with the path (test_factdiff.py: its snapshots), else the end-of-run check fails.
LINKED_DIRS = ("_snapshots", "artifacts", "_census")


class KbTemplate:
    """One copy of a kb working tree, read once, that every kb copy of a run is built from: files in LINKED_DIRS are
    hard links of it (copied where the filesystem refuses a link), all others real copies, so a test may write any
    file outside LINKED_DIRS (or inside, when copy_to's `copy` names it). A write through a link would change the
    template and every later copy: `changed()` rereads the template against the digests taken while it was built."""

    def __init__(self, src, ignore, symlinks=False):
        self.base = tempfile.mkdtemp(prefix="kb-template-")
        self.root = os.path.join(self.base, "kb")
        self.digests = {}

        def read_once(s, d, *, follow_symlinks=True):
            with open(s, "rb") as f:
                data = f.read()
            with open(d, "wb") as f:
                f.write(data)
            shutil.copystat(s, d)
            self.digests[os.path.relpath(d, self.root)] = hashlib.sha256(data).hexdigest()
            return d

        shutil.copytree(src, self.root, ignore=ignore, symlinks=symlinks, copy_function=read_once)

    @staticmethod
    def linked(rel, copy=()):
        rel = rel.replace(os.sep, "/")
        return any(part in LINKED_DIRS for part in rel.split("/")[:-1]) and not any(
            rel == c.strip("/") or rel.startswith(c.strip("/") + "/") for c in copy)

    def copy_to(self, dst, skip=(), copy=()):
        """The template as a new tree at `dst` (which must not exist), without the names matching `skip` (glob
        patterns, as shutil.ignore_patterns); `copy`: path prefixes (relative, with /) that stay real copies."""
        drop = shutil.ignore_patterns(*skip) if skip else None

        def walk(s, d, rel):
            os.makedirs(d, exist_ok=bool(rel))
            with os.scandir(s) as it:
                entries = list(it)
            dropped = set(drop(s, [e.name for e in entries])) if drop else ()
            for e in entries:
                if e.name in dropped:
                    continue
                r, target = (rel + "/" + e.name) if rel else e.name, os.path.join(d, e.name)
                if e.is_symlink():
                    os.symlink(os.readlink(e.path), target)
                elif e.is_dir():
                    walk(e.path, target, r)
                elif self.linked(r, copy):
                    try:
                        os.link(e.path, target)
                    except OSError:  # another device, a filesystem without links, a link count limit
                        shutil.copy2(e.path, target)
                else:
                    shutil.copy2(e.path, target)

        walk(self.root, os.fspath(dst), "")
        return dst

    def changed(self):
        """Relative paths of the template's files that differ from what was read, went missing or appeared."""
        seen = {}
        for d, _, names in os.walk(self.root):
            for n in names:
                p = os.path.join(d, n)
                if not os.path.islink(p):
                    with open(p, "rb") as f:
                        seen[os.path.relpath(p, self.root)] = hashlib.sha256(f.read()).hexdigest()
        return sorted(k for k in seen.keys() | self.digests.keys() if seen.get(k) != self.digests.get(k))

    def remove(self):
        shutil.rmtree(self.base, ignore_errors=True)


TEMPLATES = {}  # per process, so per xdist worker: each builds its own, nothing is shared between workers


def kb_template(key, ignore, symlinks=False):
    if key not in TEMPLATES:
        TEMPLATES[key] = KbTemplate(KB, ignore, symlinks)
    return TEMPLATES[key]


@pytest.fixture(scope="session", autouse=True)
def kb_templates_untouched():
    """The end of a run (a worker's, under xdist): every template file is what it was when read, else an error."""
    yield
    templates, bad = list(TEMPLATES.values()), []
    TEMPLATES.clear()
    for t in templates:
        bad += t.changed()
        t.remove()
    if bad:
        pytest.fail(f"a test wrote through a hard link into the kb template: {bad[:10]} (a file a test writes belongs "
                    "outside conftest.LINKED_DIRS, or in copy_kb's `copy`)", pytrace=False)


def copy_kb(dst, skip=(), copy=()):
    patterns = shutil.ignore_patterns(".git", "_cache", "_private", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache")
    claude = os.path.normcase(os.path.join(KB, ".claude"))

    def ignore(d, names):  # and Claude Code's worktrees (sprint subagents): each is a whole second kb
        return set(patterns(d, names)) | ({"worktrees"} if os.path.normcase(d) == claude else set())

    return kb_template("kb", ignore).copy_to(dst, skip, copy)


ALLOWLIST = os.path.join(TOOLS, "tests_allowlist.txt")  # the reviewed exceptions of the leak scan


def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


@functools.lru_cache(maxsize=None)
def tracked():
    """Tracked files (git ls-files), or every file outside ignored dirs when git is unavailable (read once per run)."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=KB, capture_output=True, check=True).stdout
        return tuple(sorted(f for f in out.decode().split("\0") if f))
    except (OSError, subprocess.CalledProcessError):
        out = []
        for root, dirs, files in os.walk(KB):
            dirs[:] = [d for d in dirs if d not in {".git", "_cache", "_private", "__pycache__", ".venv", ".pytest_cache",
                                                    ".ruff_cache", ".uv-cache", "node_modules"}]  # never scan installed packages
            out += [os.path.relpath(os.path.join(root, f), KB) for f in files]
        return tuple(sorted(out))


@functools.lru_cache(maxsize=None)
def text(rel):
    try:
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def pinned():
    """Repository paths of every root's pinned artifacts."""
    out = set()
    for r in kbcommon.roots():
        with open(os.path.join(r.path, kbcommon.ARTIFACTS), encoding="utf-8-sig", newline="") as f:
            out |= {kbcommon.repo_rel(x["path"], r.path) for x in csv.DictReader(f)}
    return out


def internal_prefixes():
    """Repository path prefixes of the roots marked `visibility: internal`: they may hold real names and addresses."""
    return tuple(kbcommon.repo_rel(".", r.path) + "/" for r in kbcommon.roots() if r.visibility != "public")


@functools.lru_cache(maxsize=None)
def authored():
    """Tracked text files we wrote ourselves that the placeholders-only rule covers: not pinned artifacts, not vendor
    exports under */artifacts/ or snapshots of copy sources under */_snapshots/, not files of internal roots (secrets are
    checked everywhere: test_no_secrets)."""
    p, internal = pinned(), internal_prefixes()
    return tuple(f for f in tracked() if f not in p and "/artifacts/" not in f and f"/{kbcommon.SNAPSHOTS}/" not in f
                 and not f.startswith(internal) and text(f) is not None)


def allowlist():
    out = {}
    if os.path.exists(ALLOWLIST):
        with open(ALLOWLIST, encoding="utf-8") as f:
            lines = f.read().splitlines()
        for ln in lines:
            ln = ln.split("#", 1)[0].strip()
            if ln:
                kind, value = ln.split(None, 1)
                out.setdefault(kind, set()).add(value.strip().lower())
    return out


# urls, including git remotes: ssh:// and the scp-like `git@host:path` form, and `ssh [-opts] git@host` (a remote or an
# ssh login, not an e-mail address)
URL_RX = re.compile(r"(?:https?|ssh|git)://\S+|(?<![\w.%+-])git@[\w.-]+:[\w./~-]+|\bssh(?:\s+-\w+)*\s+git@[\w.-]+")


def hits(pattern, files, flags=0, strip_urls=False):
    rx = re.compile(pattern, flags)
    found = []
    for f in files:
        t = text(f)
        if t is None:
            continue
        for n, ln in enumerate(t.splitlines(), 1):
            src = URL_RX.sub("", ln) if strip_urls else ln
            for m in rx.finditer(src):
                found.append((f, n, m.group(0)))
    return found


def fmt(found, limit=20):
    return "\n".join(f"  {f}:{n}: {v}" for f, n, v in found[:limit]) + (f"\n  ... +{len(found) - limit}" if len(found) > limit else "")


@pytest.fixture(scope="session")
def kb_seed(tmp_path_factory):
    """(bare repository, its commit) of a kb copy without _fetch_state.csv and the committed query log store, committed
    once per run: the origin a git scenario clones. Under pytest-xdist the first worker that asks builds it in the
    run's shared temporary directory, and the others wait for it."""
    base = tmp_path_factory.getbasetemp()
    tmp = (base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base) / "kb-seed"
    done = tmp / "seed.json"
    try:
        tmp.mkdir()
    except FileExistsError:
        deadline = time.monotonic() + 900
        while not done.exists():
            assert time.monotonic() < deadline, f"no seed at {tmp}"
            time.sleep(0.1)
        got = json.loads(done.read_text(encoding="utf-8"))
        assert "error" not in got, got
        return Path(got["bare"]), got["base"]
    got = {"error": "not built"}
    try:
        repo = Repo(copy_kb(str(tmp / "seed"), skip=("_fetch_state.csv", "_querylog")))
        repo.git("init", "-q", "-b", "main")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "base")
        Repo(tmp).git("clone", "-q", "--bare", repo.path, str(tmp / "seed.git"))
        Repo(tmp / "seed.git").git("repack", "-a", "-d", "-q")  # one pack: a clone links two files, not every object
        got = {"bare": str(tmp / "seed.git"), "base": repo.rev("HEAD")}
    finally:
        part = done.with_suffix(".part")
        part.write_text(json.dumps(got), encoding="utf-8")
        os.replace(part, done)
    return Path(got["bare"]), got["base"]


class Repo:
    """One throwaway directory (a kb copy, a clone, a source repo) and the commands run in it."""

    def __init__(self, path, env=None):
        self.path, self.env = str(path), env if env is not None else git_env()

    def __repr__(self):
        return f"Repo({self.path!r})"

    def run_git(self, *args, env=None):
        return subprocess.run(["git", *args], cwd=self.path, env={**self.env, **(env or {})}, capture_output=True, text=True, encoding="utf-8")

    def git(self, *args, env=None):
        """git's stdout; AssertionError with its output when it fails."""
        p = self.run_git(*args, env=env)
        if p.returncode:
            raise AssertionError(f"git {' '.join(args)}: {p.stdout}{p.stderr}")
        return p.stdout

    def rev(self, r):
        return self.git("rev-parse", r).strip()

    def tool(self, name, *args, env=None):
        """Run this directory's own copy of _tools/NAME."""
        return subprocess.run([sys.executable, os.path.join(self.path, "_tools", name), *args], cwd=self.path,
                              env={**self.env, **(env or {})}, capture_output=True, text=True, encoding="utf-8", errors="replace")

    def kbgit(self, *args):
        return self.tool("kbgit.py", *args)

    def file(self, rel):
        return os.path.join(self.path, rel)

    def read(self, rel):
        with open(self.file(rel), encoding="utf-8", newline="") as f:
            return f.read()

    def write(self, rel, text, mode="w"):
        os.makedirs(os.path.dirname(self.file(rel)), exist_ok=True)
        with open(self.file(rel), mode, encoding="utf-8", newline="") as f:
            f.write(text)

    def append(self, rel, text):
        self.write(rel, text, "a")
