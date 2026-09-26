"""Shared pytest setup for the kb tests. Run them with `python3 _tools/tests.py` (uv installs pytest and pytest-xdist
from pyproject.toml's dev group) or `uv run pytest`.

  Repo(path, env)       one throwaway directory: git(), run_git(), rev(), tool(), kbgit(), read(), write(), append()
  git_env(**extra)      the environment of a git scenario: no global or system git config, a fixed author, and none
                        of the variables that would leak the outer repository, a CI run or a verification date into it
  copy_kb(dst, skip)    a copy of the kb's working tree without .git, _cache, _private, __pycache__ (and `skip`)
  requires_git          skip marker for a test that needs the git binary
  marker `git`          a scenario in throwaway git repositories (about 10 s each); `-m "not git"` leaves them out,
                        which is what KB_TESTS_FAST=1 (kbgit.py sync's gate) does
  marker `stress`       test_stress.py: stress_test.py runs it, tests.py leaves it out
  SOURCES_HEADER        the header line of _sources.csv
"""
import os, shutil, subprocess, sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
os.environ.pop("KB_ROOT", None)  # the suite tests this repository; test_kb_root.py sets it per call
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

GIT = shutil.which("git")
requires_git = pytest.mark.skipif(not GIT, reason="git is not installed")
SOURCES_HEADER = "id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
LEAKY = ("KB_VERIFIED", "KB_TESTS_FAST", "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")


def pytest_configure(config):
    config.addinivalue_line("markers", "git: a scenario in throwaway git repositories (left out by -m 'not git')")
    config.addinivalue_line("markers", "stress: the stress suite, test_stress.py (stress_test.py runs it; tests.py leaves it out)")


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


class Repo:
    """One throwaway directory (a kb copy, a clone, a source repo) and the commands run in it."""

    def __init__(self, path, env=None):
        self.path, self.env = str(path), env if env is not None else git_env()

    def __repr__(self):
        return f"Repo({self.path!r})"

    def run_git(self, *args, env=None):
        return subprocess.run(["git", *args], cwd=self.path, env={**self.env, **(env or {})}, capture_output=True, text=True)

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
                              env={**self.env, **(env or {})}, capture_output=True, text=True, errors="replace")

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
