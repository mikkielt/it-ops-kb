"""Shared pytest setup for the kb tests. Run them with `python3 _tools/tests.py` (uv installs pytest and pytest-xdist
from pyproject.toml's dev group).

  KB, TOOLS             the repository and its _tools directory
  tool(name, *args)     run _tools/NAME on this repository: (exit code, stdout + stderr)
  tracked(), text(rel)  the tracked files (git ls-files) and one file's text (None when it is not utf-8)
  git_env(**extra)      the environment of a git scenario: no global or system git config, a fixed author, and none
                        of the variables that would leak the outer repository, a CI run or a session into it
  Repo(path, env)       one throwaway directory: git(), run_git(), rev(), tool(), kbgit(), read(), write(), append()
  kb_seed               (fixture) a bare repository of this working tree's files (tracked and new, without the query
                        log store, _fetch_state.csv and the _snapshots directories), committed once per run and shared by the xdist workers
  scenario              (fixture) a Scenario: `origin`, a bare copy of the seed that only this test pushes to, and
                        `clone()`, a fresh clone of it as a Repo with the commit hooks installed
  marker `git`          a scenario in throwaway git repositories; `-m "not git"` leaves them out
"""
import functools, json, os, shutil, subprocess, sys, time
from pathlib import Path

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
os.environ.pop("KB_ROOTS", None)  # the suite tests this repository
# The variables that point git at one repository. A git hook sets GIT_DIR, and a run it starts inherits it: every git
# a test runs, whatever its cwd, would act on the real repository. So they go before any test.
GIT_LOCATION = ("GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_GRAFT_FILE", "GIT_SHALLOW_FILE",
                "GIT_REPLACE_REF_BASE", "GIT_NO_REPLACE_OBJECTS", "GIT_PREFIX", "GIT_NAMESPACE")
for _k in GIT_LOCATION:
    os.environ.pop(_k, None)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import kbpublic  # noqa: E402

# What a scenario must not inherit: a verification date, the gate's own switches, a CI run's range, the session a
# sync would compare commits with, the main lock a sync above the test run holds, and the publish hook's off switch.
LEAKY = ("KB_VERIFIED", "KB_TESTS_FAST", "KB_SYNC_NO_TESTS", "KB_GATE_DONE", "KB_SESSION", "KB_MAIN_LOCK_HELD",
         "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", "CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID",
         kbpublic.NO_HOOK_ENV, *GIT_LOCATION)
for _k in LEAKY:
    os.environ.pop(_k, None)
SEED_SKIP = ("kb/_querylog/", ".claude/worktrees/")  # the committed query log store is no part of a scenario's kb
SEED_SKIP_NAMES = ("_fetch_state.csv",)
SEED_SKIP_DIRS = ("_snapshots",)  # copies of sources no gate reads: half of the files a clone would check out

SLOW_FIRST = ("_e2e.py", "test_leaks.py", "test_live_kb.py")  # the scenarios and the scans of the whole tree
requires_git = pytest.mark.skipif(not shutil.which("git"), reason="git is not installed")


def pytest_configure(config):
    config.addinivalue_line("markers", "git: a scenario in throwaway git repositories (left out by -m 'not git')")


def pytest_collection_modifyitems(config, items):
    """The slow files first (SLOW_FIRST, file order within each group): tests.py hands whole files to the workers in
    this order (--no-loadscope-reorder), so each slow file starts on a worker of its own and the quick ones fill in
    behind, instead of two slow files sharing one worker."""
    items.sort(key=lambda it: 0 if any(s in it.nodeid.split("::")[0] for s in SLOW_FIRST) else 1)


def tool(name, *args, env=None):
    p = subprocess.run([sys.executable, os.path.join(TOOLS, name), *args], cwd=KB, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, p.stdout + p.stderr


@functools.lru_cache(maxsize=None)
def tracked():
    """Tracked files (git ls-files), sorted: stage a new file before a run, or the scans pass it unchecked."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=KB, capture_output=True, check=True).stdout
    return tuple(sorted(f for f in out.decode("utf-8").split("\0") if f))


@functools.lru_cache(maxsize=None)
def text(rel):
    try:
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def git_env(**extra):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    for k in LEAKY:
        env.pop(k, None)
    env.update(extra)
    # No automatic maintenance in a throwaway repository, and long paths on Windows (a scenario's worktree under a
    # pytest temp directory passes 260 characters, and no host setting reaches past GIT_CONFIG_GLOBAL and NOSYSTEM;
    # other hosts ignore it): appended after the caller's GIT_CONFIG_COUNT entries (CI's safe.directory), never
    # replacing them.
    try:
        n = max(int(env.get("GIT_CONFIG_COUNT") or 0), 0)
    except ValueError:
        n = 0
    for k, v in (("gc.auto", "0"), ("maintenance.auto", "false"), ("core.longpaths", "true")):
        env[f"GIT_CONFIG_KEY_{n}"], env[f"GIT_CONFIG_VALUE_{n}"] = k, v
        n += 1
    env["GIT_CONFIG_COUNT"] = str(n)
    return env


class Repo:
    """One throwaway directory (a kb copy, a clone, a source repo) and the commands run in it."""

    def __init__(self, path, env=None):
        self.path, self.env = str(path), env if env is not None else git_env()

    def __repr__(self):
        return f"Repo({self.path!r})"

    def run_git(self, *args, env=None):
        return subprocess.run(["git", *args], cwd=self.path, env={**self.env, **(env or {})}, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

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
                              env={**self.env, **(env or {})}, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")

    def kbgit(self, *args, env=None):
        return self.tool("kbgit.py", *args, env=env)

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

    def commit(self, message, *paths):
        """Stage `paths` (everything when none) and commit; the new commit's hash."""
        self.git("add", *(paths or ("-A",)))
        self.git("commit", "-q", "-m", message)
        return self.rev("HEAD")


def seed_files():
    """This working tree's files a scenario's kb holds: tracked and new (not ignored), without SEED_SKIP."""
    out = subprocess.run(["git", "ls-files", "-z", "-c", "-o", "--exclude-standard"], cwd=KB, capture_output=True,
                         check=True).stdout.decode("utf-8")
    return sorted({f for f in out.split("\0") if f and not f.startswith(SEED_SKIP)
                   and f.rsplit("/", 1)[-1] not in SEED_SKIP_NAMES and not set(f.split("/")[:-1]) & set(SEED_SKIP_DIRS)
                   and os.path.isfile(os.path.join(KB, f))})


@pytest.fixture(scope="session")
def kb_seed(tmp_path_factory):
    """(bare repository, its commit) of this working tree's files (seed_files), committed once per run: the origin a
    git scenario copies. Nothing is written into the working tree: the commit is made with a git dir and an index of
    its own. Under pytest-xdist the first worker that asks builds it in the run's shared temporary
    directory, and the others wait for it."""
    base = tmp_path_factory.getbasetemp()
    tmp = (base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base) / "kb-seed"
    done = tmp / "seed.json"
    try:
        tmp.mkdir()
    except FileExistsError:
        deadline = time.monotonic() + 300
        while not done.exists():
            assert time.monotonic() < deadline, f"no seed at {tmp}"
            time.sleep(0.05)
        got = json.loads(done.read_text(encoding="utf-8"))
        assert "error" not in got, got
        return Path(got["bare"]), got["base"]
    got = {"error": "not built"}
    try:
        # committed straight from the working tree (GIT_WORK_TREE), with an index of its own: no copy of the files
        bare = tmp / "seed.git"
        Repo(tmp).git("init", "-q", "--bare", "-b", "main", str(bare))
        Repo(bare).git("config", "core.bare", "false")
        spec = tmp / "seed-paths"
        spec.write_bytes("\0".join(seed_files()).encode("utf-8"))
        tree = Repo(KB, git_env(GIT_DIR=str(bare), GIT_WORK_TREE=KB))
        tree.git("-c", "core.autocrlf=false", "add", "-f", f"--pathspec-from-file={spec}", "--pathspec-file-nul")
        tree.git("commit", "-q", "-m", "base")
        Repo(bare).git("config", "core.bare", "true")
        # one pack instead of a loose object per file: every scenario's two clones then link one file, not each object
        Repo(bare).git("repack", "-a", "-d", "-q", "--window=0", "--depth=0")
        got = {"bare": str(bare), "base": Repo(bare).rev("HEAD")}
    finally:
        part = done.with_suffix(".part")
        part.write_text(json.dumps(got), encoding="utf-8")
        os.replace(part, done)
    return Path(got["bare"]), got["base"]


class Scenario:
    """A test's own origin (a bare copy of the seed) and the clones made of it."""

    def __init__(self, tmp, seed, base):
        self.tmp, self.base, self.n = Path(tmp), base, 0
        self.origin = Repo(self.tmp / "origin.git")
        Repo(self.tmp).git("clone", "-q", "--bare", str(seed), self.origin.path)

    def bare(self, name):
        """Another bare copy of the origin (a public home, a second remote) as a Repo."""
        Repo(self.tmp).git("clone", "-q", "--bare", self.origin.path, str(self.tmp / name))
        return Repo(self.tmp / name)

    def clone(self, hooks=True, env=None):
        """A fresh clone of the origin on `main` as a Repo, with the commit hooks installed unless `hooks` is False."""
        self.n += 1
        repo = Repo(self.tmp / f"clone{self.n}", env)
        Repo(self.tmp).git("clone", "-q", self.origin.path, repo.path)
        repo.git("config", "core.autocrlf", "false")
        if hooks:
            p = repo.kbgit("install-hooks")
            assert p.returncode == 0, p.stdout + p.stderr
        return repo


@pytest.fixture
def scenario(tmp_path, kb_seed):
    return Scenario(tmp_path, *kb_seed)
