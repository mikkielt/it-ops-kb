"""Shared pytest setup for the kb tests. Run them with `python3 _tools/tests.py` (uv installs pytest and pytest-xdist
from pyproject.toml's dev group) or `uv run pytest`.

  Repo(path, env)       one throwaway directory: git(), run_git(), rev(), tool(), kbgit(), read(), write(), append()
  querylog_env(data)    the environment of a kb_hook.py or kb_ask.py run on this clone: its query log rows go under
                        `data`, never into the clone's own spool
  git_env(**extra)      the environment of a git scenario: no global or system git config, a fixed author, and none
                        of the variables that would leak the outer repository, a CI run or a verification date into it
  copy_kb(dst, skip)    a copy of the kb's working tree without .git, _cache, _private, __pycache__ (and `skip`)
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
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
os.environ.pop("KB_ROOTS", None)  # the suite tests this repository; test_kb_root.py sets it per call
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
LEAKY = ("KB_VERIFIED", "KB_TESTS_FAST", "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")


def pytest_configure(config):
    config.addinivalue_line("markers", "git: a scenario in throwaway git repositories (left out by -m 'not git')")
    config.addinivalue_line("markers", "stress: the stress suite, test_stress.py (stress_test.py runs it; tests.py leaves it out)")


def querylog_env(data, home=KB, base=None):
    """The environment of a tool run whose query log rows must not reach the spool of the clone at `home`: capture
    writes as the plugin at `home` would, under `data` (querylog/spool/), while KB_INDEX keeps the pack index in
    `home`'s _cache, where it lives without the plugin variables."""
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
    return env


def copy_kb(dst, skip=()):
    shutil.copytree(KB, dst, ignore=shutil.ignore_patterns(".git", "_cache", "_private", "__pycache__", ".venv", ".pytest_cache",
                                                        ".ruff_cache", *skip))
    return dst


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
