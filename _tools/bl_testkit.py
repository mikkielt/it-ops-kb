"""Helpers the backlog's tests share: test_backlog.py and the test files split from it import them. A test helper, not
a module of backlog.py: its tests are those files'.

The tool and its Python checks: the paths (`TOOLS`, `TOOL`), checks that need no tool (`PASS`, `IS_FILE`, `is_file`,
`argstr`). A throwaway repository and what drives it: `sh` (a git command), `land` (origin's main fetched at HEAD), `b`
(a backlog.py run in the repository: exit code and output), `item`, `item_json` and `edit` (read and rewrite an item
file in its canonical form), `commit`, the fixtures `repo` (a repository with one commit) and `sprint` (an approved,
started sprint with a story, its task and a bug) and the autouse fixtures `no_git_location` and `gate_jobs`.

This module never imports `backlog` (a `bl_` module's layer rule): `item` and `edit` use the backlog's directory and its
canonical form through `bind(backlog)`, which each test file calls once after importing `backlog`.
"""
import os, shlex, subprocess, sys
import json
from pathlib import Path

import pytest

import ql_deliver

_BACKLOG = None


def bind(module):
    """Give the kit the `backlog` module the test file imported (`REL_DIR` and `canonical`)."""
    global _BACKLOG
    _BACKLOG = module


def _bl():
    assert _BACKLOG is not None, "bl_testkit.bind(backlog) was not called by the test file"
    return _BACKLOG


TOOLS = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(TOOLS, "backlog.py")
# Item checks and repros are Python commands, never test or true: those are Git Bash usr/bin tools, absent from a
# Windows PATH outside Git Bash, where the check would fail to start and the item could never be done.
IS_FILE = "import pathlib, sys; sys.exit(not pathlib.Path(sys.argv[1]).is_file())"
PASS = ["python3", "-c", "pass"]
# BG-qtphqxt2's repro planted: it read a script's text for the literal '>&2', which a fix met by writing '>& 2'.
TEXT_REPRO = "import sys; sys.exit(1 if '>&2' in open('tool.sh', encoding='utf-8').read() else 0)"
SOURCE_REPRO = ("import pathlib, re, sys; s = pathlib.Path('_tools/tool.py').read_text(encoding='utf-8'); "
                "sys.exit(0 if re.search(r'worktrees', s) else 1)")  # BG-rrht7uts's grep for 'worktrees'


def is_file(rel):
    """A check that exits 0 when the file exists: an argv for an item's JSON."""
    return ["python3", "-c", IS_FILE, rel]


def argstr(argv):
    """The same check as the one string --check and --repro take."""
    return shlex.join(argv)


def sh(root, *a):
    subprocess.run(list(a), cwd=root, check=True, capture_output=True)


def land(root):
    """Pretend the integration remote's main was fetched at HEAD: done's lane rule then sees every commit landed."""
    sh(root, "git", "update-ref", "refs/remotes/origin/main", "HEAD")


def b(root, *a):
    if a[:1] == ("done",):
        land(root)
    p = subprocess.run([sys.executable, TOOL, "--root", str(root), *a], cwd=root, capture_output=True, text=True,
                       encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def item(root, title):
    for f in (Path(root) / _bl().REL_DIR).glob("*.json"):
        it = json.loads(f.read_text(encoding="utf-8"))
        if it["title"] == title:
            return it
    raise AssertionError(title)


def item_json(root, iid):
    return json.loads((Path(root) / _bl().REL_DIR / f"{iid}.json").read_text(encoding="utf-8"))


def edit(root, iid, **kw):
    f = Path(root) / _bl().REL_DIR / f"{iid}.json"
    it = json.loads(f.read_text(encoding="utf-8"))
    it.update(kw)
    f.write_text(_bl().canonical(it), encoding="utf-8", newline="\n")


def commit(root, msg, work=None):
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-qm", msg, *(["-m", f"KB-Work: {work}"] if work else []))


@pytest.fixture(autouse=True)
def no_git_location(monkeypatch):
    """A pre-push hook in a worktree sets these; inherited, git init and commit would act on the real repository."""
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def gate_jobs(monkeypatch):
    """No job is a gate by default (every CI job is manual); these tests read pipelines with the two once-gate jobs
    named, and the default is proved in test_querylog.py's TestNoGateJobs."""
    monkeypatch.setattr(ql_deliver, "GATE_JOBS", ("kb-tests", "kb-trailers"))


@pytest.fixture
def repo(tmp_path):
    sh(tmp_path, "git", "init", "-q")
    sh(tmp_path, "git", "config", "user.email", "agent@example.com")
    sh(tmp_path, "git", "config", "user.name", "agent")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text("a\n", encoding="utf-8")
    commit(tmp_path, "init")
    return tmp_path


@pytest.fixture
def sprint(repo):
    """An approved, started sprint with a story, its task and a bug."""
    assert b(repo, "new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    ep = item(repo, "Epic")["id"]
    b(repo, "new", "sprint", "--title", "Sprint", "--goal", "ship b")
    sp = item(repo, "Sprint")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "b exists",
      "--check", argstr(is_file("src/b.txt")))
    st = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Task", "--parent", st, "--goal", "b written", "--touch", "src/**",
      "--check", argstr(is_file("src/b.txt")))
    b(repo, "new", "bug", "--title", "Bug", "--sprint", sp, "--severity", "S3", "--repro", argstr(is_file("src/c.txt")),
      "--goal", "c exists", "--touch", "src/**")
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0, out
    return {"repo": repo, "ep": ep, "sp": sp, "st": st, "tk": item(repo, "Task")["id"], "bg": item(repo, "Bug")["id"],
            "rv": item(repo, "Review sprint: Sprint")["id"]}

