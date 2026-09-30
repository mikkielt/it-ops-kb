"""backlog.py in a throwaway git repository: items are created, validated, scheduled, finished and deleted.

Each refusal has a planted failure: a bug whose repro passes or fails for its own error (not found, a SyntaxError in
its own code, a usage error, no tests selected), a non-canonical file, a cycle, a blocking gate an
agent answers, a sprint started without the operator or with a work item without touches, a failing check, a commit outside `touches` (and the revert
that clears it), a review with an unconfirmed provisional answer, a malformed KB-Work trailer, a worked item of a
planned sprint, a KB-Work id whose item is unclaimed or not in a started sprint (work committed before its claim
commit included), and red pipelines that fail
the same way (one bug) or differently (a second), or the same way as a closed bug (a new one). The repository's
own backlog must pass `backlog.py check`.
"""
import argparse, json, os, re, shlex, shutil, subprocess, sys
from pathlib import Path

import pytest

import backlog
import kbgit
import ql_deliver

TOOLS = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(TOOLS, "backlog.py")
# Item checks and repros are Python commands, never test or true: those are Git Bash usr/bin tools, absent from a
# Windows PATH outside Git Bash, where the check would fail to start and the item could never be done.
IS_FILE = "import pathlib, sys; sys.exit(not pathlib.Path(sys.argv[1]).is_file())"
PASS = ["python3", "-c", "pass"]


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
    for f in (Path(root) / backlog.REL_DIR).glob("*.json"):
        it = json.loads(f.read_text(encoding="utf-8"))
        if it["title"] == title:
            return it
    raise AssertionError(title)


def edit(root, iid, **kw):
    f = Path(root) / backlog.REL_DIR / f"{iid}.json"
    it = json.loads(f.read_text(encoding="utf-8"))
    it.update(kw)
    f.write_text(backlog.canonical(it), encoding="utf-8", newline="\n")


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


def test_new_items_validate(sprint):
    code, out = b(sprint["repo"], "check")
    assert code == 0 and "errors=0" in out, out


def test_bug_repro_must_fail_now(repo):
    code, out = b(repo, "new", "bug", "--title", "Not a bug", "--severity", "S4", "--repro", argstr(PASS), "--goal", "x")
    assert code == 1 and "must fail" in out


def new_bug(repo, title, repro):
    return b(repo, "new", "bug", "--title", title, "--severity", "S4", "--repro", repro, "--goal", "x")


@pytest.fixture
def colour(monkeypatch):
    """Colour forced on, as in a Claude Code background session (FORCE_COLOR=3): Python 3.13+ then colours its
    tracebacks and 3.14 argparse its usage errors, so a repro's own error must be found whatever the host sets."""
    monkeypatch.setenv("FORCE_COLOR", "3")
    monkeypatch.setenv("PYTHON_COLORS", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)


def refused_own_error(repo, repro, cause):
    code, out = new_bug(repo, "Own error", repro)
    assert code == 1 and "fails for its own error, not the defect" in out and cause in out, out
    assert len(out) < 1500, out  # names the cause, does not dump the output
    assert not list((Path(repo) / backlog.REL_DIR).glob("*.json")), "a refused repro files nothing"


def test_repro_fails_for_its_own_error_command_not_found(repo, colour):
    refused_own_error(repo, "no-such-command-pl-lt-00123 --status", "cannot start")


def test_repro_fails_for_its_own_error_syntax_error(repo, colour):
    # a Windows path in a Python string (\x is a broken escape), and statements whose newlines --repro's split lost
    refused_own_error(repo, argstr(["python3", "-c", "import pathlib; pathlib.Path('kb\\public\\x.md')"]), "SyntaxError")
    refused_own_error(repo, argstr(["python3", "-c", "import sys sys.exit(1)"]), "SyntaxError")
    (repo / "broken.py").write_text("import sys\nif True\n    sys.exit(1)\n", encoding="utf-8")
    refused_own_error(repo, "python3 broken.py", "cannot compile the repro's own code")


def test_repro_fails_for_its_own_error_usage_error(repo, colour):
    refused_own_error(repo, argstr(["python3", TOOL, "list", "--no-such-flag"]), "rejects the repro's arguments")


def test_repro_fails_for_its_own_error_no_tests_selected(repo, colour):
    pytest.importorskip("pytest")
    (repo / "test_planted.py").write_text("def test_a():\n    assert False\n", encoding="utf-8")
    refused_own_error(repo, "python3 -m pytest -q -p no:cacheprovider test_planted.py -k no_such_test",
                      "selected no tests")


def test_repro_fails_for_its_own_error_genuine_failures_accepted(repo, colour):
    """A failure of the code under test is a reproduction: an exit 1, an assertion, a SyntaxError the tested code
    raises (not the repro's own), and a planted failing test that pytest selects."""
    (repo / "test_planted.py").write_text("def test_a():\n    assert False\n", encoding="utf-8")
    for title, repro in (
            ("Exit", argstr(["python3", "-c", "import sys; sys.exit(1)"])),
            ("Assert", argstr(["python3", "-c", "assert 1 == 2, 'PL-LT-00123 is missing'"])),
            ("Compiled", argstr(["python3", "-c", "compile('x = (', 'm.py', 'exec')"])),
            ("Pytest", "python3 -m pytest -q -p no:cacheprovider test_planted.py -k test_a")):
        code, out = new_bug(repo, title, repro)
        assert code == 0 and "own error" not in out, (title, out)
        assert item(repo, title)["repro"]["run"] == shlex.split(repro)


def test_repro_fails_for_its_own_error_runs_colour_off(repo, colour):
    """run_check, the runner of new's repro and done's checks, runs the command with colour off and matches its
    output with colour codes taken out: a check's match sees plain text even from a tool that colours anyway."""
    env = ("import os, sys; print(os.environ.get('NO_COLOR'), os.environ.get('FORCE_COLOR'), "
           "os.environ.get('PYTHON_COLORS'))")
    ok, code, out = backlog.run_check(repo, {"run": ["python3", "-c", env], "match": r"^1 None None$"})
    assert ok and code == 0, out
    ok, code, out = backlog.run_check(repo, {"run": ["python3", "-c", "print('\\x1b[1;31mred\\x1b[0m')"],
                                             "match": r"^red$"})
    assert ok and "\x1b" not in out, repr(out)


def test_repro_fails_for_its_own_error_classifier():
    """own_failure on outputs no host can produce here: a shell's exit 127, cmd's lone message, a pytest run whose
    selection was all deselected, and a tool's finding that mentions a missing command (accepted)."""
    f = backlog.own_failure
    assert "cannot start" in f(["bash", "-c", "x"], 127, "bash: line 1: x: command not found\n")
    assert "cannot start" in f(["cmd", "/c", "x"], 1, "'x' is not recognized as an internal or external command,\n"
                                                        "operable program or batch file.\n")
    assert "selected no tests" in f(["python3", "_tools/tests.py", "-k", "nope"], 5, "12 deselected in 0.40s\n")
    assert f(["python3", "t.py"], 1, "finding 1\nfinding 2\nfinding 3\nsetup.sh: x: command not found\n") is None
    assert f(["python3", "t.py"], 2, "usage: t.py [-h]\n") is None  # exit 2 without argparse's error line
    assert f(["python3", "t.py"], None, "Command 't.py' timed out after 1800 seconds") is None


def test_check_finds_planted_errors(sprint):
    repo = sprint["repo"]
    f = Path(repo) / backlog.REL_DIR / f"{sprint['tk']}.json"
    f.write_text(json.dumps(json.loads(f.read_text(encoding="utf-8"))) + "\n", encoding="utf-8")
    edit(repo, sprint["bg"], depends_on=[sprint["st"]])
    edit(repo, sprint["st"], depends_on=[sprint["bg"]])
    code, out = b(repo, "check")
    assert code == 1
    assert "canonical form" in out and "cycle" in out
    assert f"{sprint['tk']} “Task”" in out  # an id is never printed without its title


DOC_MAP = "doc,pattern\nkb/_self/tools.md,_tools/x.py\nkb/_self/plugin.md,.claude-plugin/**\n"


@pytest.fixture
def mapped(sprint):
    """The sprint with a kb/_self/map.csv: tools.md describes _tools/x.py, plugin.md all of .claude-plugin/."""
    repo = sprint["repo"]
    (repo / "kb" / "_self").mkdir(parents=True, exist_ok=True)
    (repo / "kb" / "_self" / "map.csv").write_text(DOC_MAP, encoding="utf-8", newline="\n")
    (repo / ".claude-plugin").mkdir()
    (repo / ".claude-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8", newline="\n")
    commit(repo, "map")
    return sprint


def test_check_warns_touches_miss_docs(mapped):
    """Planted: a task whose touches name mapped code (a literal path and a glob) and none of its docs; check warns,
    naming them, and exits 0. Its docs in the task's own touches clear the warning."""
    repo, tk = mapped["repo"], mapped["tk"]
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out
    edit(repo, tk, touches=["_tools/x.py", ".claude-plugin/*.json"])
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out and "warnings=1" in out, out
    assert (f"{tk} “Task”: touches code whose kb/_self/map.csv docs are in no item's touches: "
            f"kb/_self/plugin.md, kb/_self/tools.md") in out, out
    edit(repo, tk, touches=["_tools/x.py", ".claude-plugin/*.json", "kb/_self/tools.md", "kb/_self/plugin.md"])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out


def test_check_warns_docs_in_later_task(mapped):
    """Planted: the code's doc only in a task that depends on the code task (a later task); check warns, naming the
    doc and that task. The same doc in an item that does not depend on it is no warning."""
    repo, st, tk = mapped["repo"], mapped["st"], mapped["tk"]
    edit(repo, tk, touches=["_tools/x.py"])
    b(repo, "new", "task", "--title", "Docs", "--parent", st, "--goal", "docs", "--touch", "kb/_self/tools.md",
      "--depends", tk, "--check", argstr(PASS))
    docs = item(repo, "Docs")["id"]
    code, out = b(repo, "check")
    assert code == 0 and "warnings=1" in out, out
    assert (f"{tk} “Task”: the docs of its code are only in a later task's touches, {docs} “Docs” "
            f"(it depends on this one): kb/_self/tools.md") in out, out
    assert "in no item's touches" not in out, out
    edit(repo, docs, depends_on=[])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out


def test_task_needs_parent_and_touches(repo):
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    code, out = b(repo, "new", "task", "--title", "Orphan", "--goal", "g")
    assert "needs a parent" in out and "touches missing" in out


def test_only_operator_answers_blocking_gates_and_starts_sprints(repo):
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    assert b(repo, "start", sp)[0] == 1
    code, out = b(repo, "answer", sp, "start", "--answer", "approve", "--by", "agent")
    assert code == 1 and "only the operator" in out
    assert b(repo, "answer", sp, "start", "--provisional")[0] == 1


def test_start_refuses_work_items_without_touches(repo):
    """start names every story, task or bug (not the review) without a scope, changes nothing, and starts once each
    has one: touches of its own, or tasks that all have them. A dropped item is exempt."""
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    b(repo, "new", "story", "--title", "Split story", "--parent", ep, "--sprint", sp, "--goal", "g")
    st = item(repo, "Split story")["id"]
    b(repo, "new", "task", "--title", "Its task", "--parent", st, "--goal", "g", "--touch", "src/**")
    b(repo, "new", "story", "--title", "Bare story", "--parent", ep, "--sprint", sp, "--goal", "g")
    bare = item(repo, "Bare story")["id"]
    b(repo, "new", "bug", "--title", "Bare bug", "--sprint", sp, "--severity", "S3",
      "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists")
    bug = item(repo, "Bare bug")["id"]
    b(repo, "new", "bug", "--title", "Dropped bug", "--sprint", sp, "--severity", "S4",
      "--repro", argstr(is_file("src/d.txt")), "--goal", "d exists")
    edit(repo, item(repo, "Dropped bug")["id"], status="dropped", notes="not this sprint")
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    files = {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")}
    code, out = b(repo, "start", sp)
    assert code == 1, out
    assert f"{bare} “Bare story”" in out and f"{bug} “Bare bug”" in out, out
    assert "Split story" not in out and "Its task" not in out and "Dropped bug" not in out and "Review" not in out
    assert {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")} == files
    edit(repo, bare, touches=["src/b.txt"])
    edit(repo, bug, touches=["src/c.txt"])
    code, out = b(repo, "start", sp)
    assert code == 0, out
    assert item(repo, "S")["status"] == "active" and item(repo, "Bare bug")["status"] == "todo"


def test_next_orders_s1_bugs_first(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], severity="S1")
    code, out = b(repo, "next", "--all")
    assert code == 0
    assert out.splitlines()[0].startswith(sprint["bg"])
    assert sprint["st"] not in out  # a story with an open task is not ready itself
    assert sprint["rv"] not in out  # the review waits on every other item


def test_done_refuses_failing_check_and_scope_then_passes(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "x.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "start", tk)
    code, out = b(repo, "done", tk)
    assert code == 1 and "check(s) failed" in out
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "stray.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "write b", tk)
    code, out = b(repo, "done", tk)
    assert code == 1 and "stray.txt, outside touches" in out
    sh(repo, "git", "rm", "-q", "stray.txt")
    commit(repo, "revert stray", tk)
    code, out = b(repo, "done", tk)
    assert code == 0, out
    it = item(repo, "Task")
    assert it["status"] == "done" and it["evidence"]["commit"] and "claimed_by" not in it


def test_done_refuses_kb_work_outside_trailers(sprint):
    """A KB-Work line in a paragraph before Co-Authored-By is no trailer for git: done sees no commit and refuses."""
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"write b\n\nKB-Work: {tk}\n\nCo-Authored-By: A <a@example.com>")
    code, out = b(repo, "done", tk)
    assert code == 1 and "no commit on HEAD carries the trailer" in out
    (repo / "src" / "y.txt").write_text("y\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"more\n\nCo-Authored-By: A <a@example.com>\nKB-Work: {tk}")
    code, out = b(repo, "done", tk)
    assert code == 0, out


def story_with_touches(sprint):
    """The fixture's story given touches of its own, as a story whose tasks carry its work has."""
    repo, st = sprint["repo"], sprint["st"]
    edit(repo, st, touches=["src/**"])
    commit(repo, "story touches")
    return repo, st, sprint["tk"]


def finish_task(repo, tk):
    """The task claimed, worked and done under its own KB-Work id; the story's id is on none of these commits."""
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    commit(repo, "claim", tk)
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)
    code, out = b(repo, "done", tk)
    assert code == 0, out
    commit(repo, "task done", tk)


def test_done_counts_descendant_commits_story_closes(sprint):
    """A story with touches whose task's commits carried the work is done without a commit of its own."""
    repo, st, tk = story_with_touches(sprint)
    finish_task(repo, tk)
    code, out = b(repo, "done", st)
    assert code == 0, out
    assert item(repo, "Story")["status"] == "done"


def test_done_counts_descendant_commits_none_still_refused(sprint):
    """Planted: a story with touches and no commit under its id or its task's ids is still refused."""
    repo, st, tk = story_with_touches(sprint)
    edit(repo, tk, status="done")  # the task closed by hand, with no work commit anywhere
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "b, with no KB-Work trailer")
    code, out = b(repo, "done", st)
    assert code == 1 and "no commit on HEAD carries the trailer" in out, out


def test_done_counts_descendant_commits_outside_touches(sprint):
    """A task's commit outside the story's scope is still refused on the story."""
    repo, st, tk = story_with_touches(sprint)
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "stray.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "write b and stray", tk)
    edit(repo, tk, status="done")
    commit(repo, "task done", tk)
    code, out = b(repo, "done", st)
    assert code == 1 and "stray.txt, outside touches" in out, out


def test_check_interpreter_argv(monkeypatch, tmp_path):
    """run_check starts a python3 or python check with sys.executable (on Windows the venv launcher's base interpreter
    directory holds a python3.exe, so the PATH plant below cannot fail there); other commands are left as they are."""
    seen = []
    monkeypatch.setattr(backlog.subprocess, "run", lambda argv, **k: seen.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""))
    for cmd in ("python3", "python", "git"):
        assert backlog.run_check(tmp_path, {"run": [cmd, "x"]})[0]
    assert seen == [[sys.executable, "x"], [sys.executable, "x"], ["git", "x"]]


def test_check_interpreter_is_the_one_running_backlog(sprint, tmp_path):
    """A check naming python3 runs with backlog.py's own interpreter: a python3 on PATH that fails (the Windows Store
    alias exits 49) or none at all does not fail the item."""
    import shutil
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, checks=[{"run": ["python3", "-c", "import os, sys; sys.exit(0 if os.path.isfile('src/b.txt') else 1)"]}])
    commit(repo, "a python3 check")
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)
    bad = tmp_path / "bad-python"
    bad.mkdir()
    for name in ("python3", "python"):
        (bad / name).write_text("#!/bin/sh\nexit 49\n", encoding="utf-8", newline="\n")
        (bad / name).chmod(0o755)
    # Windows cannot start the planted scripts: there PATH holds git's directory and no Python at all
    path = os.path.dirname(shutil.which("git")) if os.name == "nt" else str(bad) + os.pathsep + os.environ["PATH"]
    env = {**os.environ, "PATH": path}
    run = lambda *a: subprocess.run([sys.executable, TOOL, "--root", str(repo), *a], cwd=repo, capture_output=True,  # noqa: E731
                                    text=True, encoding="utf-8", env=env)
    assert run("claim", tk, "--by", "agent-1").returncode == 0
    land(repo)
    p = run("done", tk)
    assert p.returncode == 0, p.stdout + p.stderr
    assert item(repo, "Task")["status"] == "done"


def test_done_refuses_uncommitted_changes_in_scope(sprint):
    repo = sprint["repo"]
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    code, out = b(repo, "done", sprint["tk"])
    assert code == 1 and "uncommitted" in out


def test_horizon_splits_reachable_from_gated(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], gates=[{"id": "G1", "kind": "blocking", "question": "Fix or drop?",
                                     "recommendation": "fix"}])
    code, out = b(repo, "horizon")
    assert code == 0
    assert "2 more reachable" in out and "2 wait on the operator" in out
    assert "Fix or drop?" in out and "critical path (2 steps" in out
    code, out = b(repo, "horizon", "--hook")
    hook = json.loads(out)
    assert "Fix or drop?" in hook["hookSpecificOutput"]["additionalContext"]


def planned_sprint(repo):
    """A planned sprint with a bug besides its review; its start gate is unanswered."""
    b(repo, "new", "sprint", "--title", "Planned", "--goal", "ship c")
    sp = item(repo, "Planned")["id"]
    b(repo, "new", "bug", "--title", "Planned bug", "--sprint", sp, "--severity", "S3",
      "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists")
    return sp


def test_horizon_start_unanswered_is_the_operators_question(repo):
    sp = planned_sprint(repo)
    code, out = b(repo, "horizon", "--sprint", sp)
    assert code == 0, out
    assert "the sprint's start gate:" in out and "2 wait on the operator or a trigger" in out, out
    assert "approved, not started" not in out and "wait on backlog.py start" not in out, out
    # a change answer is no approval: still the operator's question (planted: an answer read as approval)
    edit(repo, sp, gates=[dict(g, answer="change: drop the bug", by="operator") if g["id"] == "start" else g
                          for g in item(repo, "Planned")["gates"]])
    code, out = b(repo, "horizon", "--sprint", sp)
    assert "the sprint's start gate:" in out and "approved, not started" not in out, out
    code, out = b(repo, "horizon", "--sprint", sp, "--hook")
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "2 wait on the operator" in ctx and "backlog.py start" not in ctx.split("Goals and")[0], ctx


def test_horizon_start_approved_waits_on_backlog_start_not_the_operator(repo):
    sp = planned_sprint(repo)
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "horizon", "--sprint", sp)
    assert code == 0, out
    assert f"approved, not started; run python3 _tools/backlog.py start {sp}" in out, out
    assert f"2 wait on backlog.py start {sp}; 0 wait on the operator or a trigger" in out, out
    assert "Approve this sprint" not in out, out
    code, out = b(repo, "horizon", "--sprint", sp, "--hook")
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "2 wait on backlog.py start" in ctx and "wait on the operator" not in ctx, ctx
    assert "approved, not started" in ctx and "Approve this sprint" not in ctx, ctx
    code, out = b(repo, "horizon", "--hook")  # no active sprint: the planned list names the approval
    assert "(approved, not started)" in json.loads(out)["systemMessage"], out
    # an item's own gate is still the operator's, inside an approved sprint
    bg = item(repo, "Planned bug")["id"]
    edit(repo, bg, gates=[{"id": "G1", "kind": "blocking", "question": "Fix or drop?", "recommendation": "fix"}])
    code, out = b(repo, "horizon", "--sprint", sp)
    assert "1 wait on backlog.py start" in out and "1 wait on the operator or a trigger" in out, out


HOOK_LIMIT = 1000  # characters of the SessionStart hook's whole stdout, which every session in a clone reads


def test_horizon_hook_prints_sprint_ids_and_titles_without_goals(sprint):
    repo = sprint["repo"]
    goals = {}
    for n in range(4):
        title = f"Long sprint {n}"
        goals[title] = f"Goal sentence {n}: " + "every part of this outcome is spelled out at length, " * 6
        b(repo, "new", "sprint", "--title", title, "--goal", goals[title])
        sp = item(repo, title)["id"]
        b(repo, "new", "bug", "--title", f"Bug {n}", "--sprint", sp, "--severity", "S3",
          "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**")
        assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
        code, out = b(repo, "start", sp)
        assert code == 0, out
    code, out = b(repo, "horizon", "--hook")
    assert code == 0, out
    hook = json.loads(out)
    context = hook["hookSpecificOutput"]["additionalContext"]
    for title, goal in goals.items():
        sp = item(repo, title)["id"]
        assert f"{sp} “{title}”" in context and f"{sp} “{title}”" in hook["systemMessage"], context
        assert goal[:20] not in out
    assert "ship b" not in out and sprint["sp"] in context
    assert len(out) < HOOK_LIMIT, len(out)
    code, out = b(repo, "horizon")  # without --hook: unchanged, goals and critical paths included
    assert code == 0 and all(f"goal {g}" in out for g in goals.values()) and "goal ship b" in out
    assert "critical path" in out


def test_horizon_hook_of_the_repository_backlog_stays_under_the_limit():
    code, out = b(os.path.dirname(TOOLS), "horizon", "--hook")
    assert code == 0, out
    assert len(out) < HOOK_LIMIT, (len(out), out)


def test_review_needs_confirmed_provisional_answers_and_close_deletes(sprint):
    repo, bg = sprint["repo"], sprint["bg"]
    edit(repo, bg, gates=[{"id": "G1", "kind": "provisional", "question": "Name c?", "recommendation": "c.txt"}])
    assert b(repo, "answer", bg, "G1", "--provisional")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{sprint['tk']}, {bg}")
    for iid in (sprint["tk"], sprint["st"], bg):
        code, out = b(repo, "done", iid)
        assert code == 0, out
    edit(repo, sprint["rv"], checks=[{"run": PASS}])
    commit(repo, "state")
    code, out = b(repo, "done", sprint["rv"])
    assert code == 1 and "provisional answer to confirm" in out
    assert b(repo, "answer", bg, "G1", "--confirm")[0] == 0
    assert b(repo, "done", sprint["rv"])[0] == 0
    assert b(repo, "done", sprint["ep"])[0] == 0
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert not list((Path(repo) / backlog.REL_DIR).glob("*.json"))


def test_close_summary_lists_every_item_with_its_evidence_commit(sprint):
    """close --summary prints, before the deletions, one line per item it deletes (the task, the review, a dropped
    subtask and the finished epic included) with the commit done recorded, and then closes as usual."""
    repo, tk, st, bg, rv, ep = (sprint[k] for k in ("repo", "tk", "st", "bg", "rv", "ep"))
    b(repo, "new", "subtask", "--title", "Sub", "--parent", tk, "--goal", "x", "--touch", "src/**",
      "--check", argstr(PASS))
    sb = item(repo, "Sub")["id"]
    assert b(repo, "drop", sb, "--why", "not needed")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{tk}, {bg}")
    work = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    for iid in (tk, st, bg):
        code, out = b(repo, "done", iid)
        assert code == 0, out
    edit(repo, rv, checks=[{"run": PASS}])
    commit(repo, "state")
    assert b(repo, "done", rv)[0] == 0
    assert b(repo, "done", ep)[0] == 0
    code, out = b(repo, "close", sprint["sp"], "--summary")
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == f"delivered by {sprint['sp']} “Sprint”:", out
    body = lines[1:lines.index("")]
    assert any(x.startswith(f"- {ep} “Epic” (epic): done at ") for x in body)  # the finished epic goes too
    assert f"  - {st} “Story” (story): done at {work[:10]}" in body
    assert f"    - {tk} “Task” (task): done at {work[:10]}" in body
    assert f"      - {sb} “Sub” (subtask): dropped, no evidence commit" in body
    assert f"- {bg} “Bug” (bug): done at {work[:10]}" in body
    assert any(x.startswith(f"- {rv} “Review sprint: Sprint” (story): done at ") for x in body)
    assert len(body) == 6, body  # one line per deleted item, no more
    assert body.index(f"  - {st} “Story” (story): done at {work[:10]}") < body.index(
        f"    - {tk} “Task” (task): done at {work[:10]}")  # a child under its parent
    assert out.index("delivered by") < out.index("deleted ")  # printed before anything goes
    assert not list((Path(repo) / backlog.REL_DIR).glob("*.json"))


def test_close_summary_refuses_open_items_and_deletes_nothing(sprint):
    code, out = b(sprint["repo"], "close", sprint["sp"], "--summary")
    assert code == 1 and "not finished" in out and "delivered by" not in out
    assert item(sprint["repo"], "Sprint")["id"] == sprint["sp"]


def test_close_refuses_open_items(sprint):
    code, out = b(sprint["repo"], "close", sprint["sp"])
    assert code == 1 and "not finished" in out


def test_close_drops_relates_to(sprint):
    """An open item outside the sprint relates to one close deletes: close drops the link, and check still passes."""
    repo = sprint["repo"]
    b(repo, "new", "bug", "--title", "Later", "--severity", "S4", "--repro", argstr(is_file("src/z.txt")),
      "--goal", "z exists")
    later = item(repo, "Later")["id"]
    edit(repo, later, relates_to=[sprint["bg"], sprint["ep"]])
    b(repo, "new", "bug", "--title", "Only", "--severity", "S4", "--repro", argstr(is_file("src/y.txt")),
      "--goal", "y exists")
    only = item(repo, "Only")["id"]
    edit(repo, only, relates_to=[sprint["tk"]])
    for iid in (sprint["st"], sprint["tk"], sprint["bg"], sprint["rv"]):
        edit(repo, iid, status="dropped")
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert item(repo, "Later")["relates_to"] == [sprint["ep"]]  # the epic stays open, so its link stays
    assert "relates_to" not in item(repo, "Only")
    assert later in out and only in out  # close names the items it edited
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_close_drops_depends_on(sprint):
    """An open item outside the sprint depends on a done one close deletes: the dependency is satisfied, so close
    drops it (and the key once empty), check still passes and horizon does not count the item as waiting."""
    repo = sprint["repo"]
    b(repo, "new", "bug", "--title", "Later", "--severity", "S4", "--repro", argstr(is_file("src/z.txt")),
      "--goal", "z exists")
    later = item(repo, "Later")["id"]
    b(repo, "new", "bug", "--title", "Other", "--severity", "S4", "--repro", argstr(is_file("src/y.txt")),
      "--goal", "y exists")
    other = item(repo, "Other")["id"]
    edit(repo, later, depends_on=[sprint["bg"]], relates_to=[sprint["tk"]])
    edit(repo, other, depends_on=[sprint["bg"], later])
    edit(repo, sprint["bg"], status="done")
    for iid in (sprint["st"], sprint["tk"], sprint["rv"]):
        edit(repo, iid, status="dropped")
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert "depends_on" not in item(repo, "Later") and "relates_to" not in item(repo, "Later")
    assert item(repo, "Other")["depends_on"] == [later]  # an open dependency stays
    assert out.count(f"from {later} ") == 1 and f"from {other} " in out  # one line per changed item
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out
    code, out = b(repo, "horizon")
    assert code == 0 and sprint["bg"] not in out, out


def test_goal_condition_names_checks_and_scope(sprint):
    code, out = b(sprint["repo"], "goal", sprint["tk"])
    assert f"`{argstr(is_file('src/b.txt'))}` exits 0" in out and "src/**" in out and f"backlog.py done {sprint['tk']}" in out


def test_glob_scope():
    assert backlog.in_scope("_tools/backlog.py", ["_tools/*.py"])
    assert not backlog.in_scope("_tools/sub/x.py", ["_tools/*.py"])
    assert backlog.in_scope("_tools/sub/x.py", ["_tools/**"])
    assert backlog.in_scope("kb/public/_coverage.csv", [])


def test_work_trailer(monkeypatch):
    have = {("abc", "kb/_self/backlog/TK-aaaaaaaa.json")}
    monkeypatch.setattr(kbgit, "blob", lambda rev, rel: "{}" if (rev, rel) in have else None)
    assert kbgit.work_ok("abc", ["TK-aaaaaaaa"])
    assert not kbgit.work_ok("abc", ["TK-bbbbbbbb"])  # no such item
    assert not kbgit.work_ok("abc", ["task 7"])  # not an id
    assert not kbgit.work_ok("abc", ["TK-aaaaaaaa", "TK-aaaaaaaa"])  # a second line


def test_started_sprint_check_refuses_worked_item_of_planned_sprint(repo):
    """A planned sprint's items stay draft until start: a task under its story is created draft, and check reports a
    todo, doing or done item of it (planted: the story set to todo)."""
    b(repo, "new", "sprint", "--title", "Planned", "--goal", "g")
    sp = item(repo, "Planned")["id"]
    b(repo, "new", "story", "--title", "S", "--sprint", sp, "--goal", "g", "--check", argstr(PASS))
    st = item(repo, "S")["id"]
    b(repo, "new", "task", "--title", "T", "--parent", st, "--goal", "g", "--touch", "src/**", "--check", argstr(PASS))
    assert item(repo, "T")["status"] == "draft"
    assert b(repo, "check")[0] == 0
    edit(repo, st, status="todo")
    code, out = b(repo, "check")
    assert code == 1 and f"{st} “S”: status todo while its sprint {sp} “Planned” is planned" in out, out
    assert "not in a started sprint" in out


def test_active_sprint_item_is_todo(sprint):
    """A bug filed into an active sprint is ready at once (todo); one filed into a planned sprint stays draft."""
    repo = sprint["repo"]
    b(repo, "new", "bug", "--title", "Found", "--sprint", sprint["sp"], "--severity", "S3",
      "--repro", argstr(is_file("src/d.txt")), "--goal", "d exists")
    assert item(repo, "Found")["status"] == "todo"
    b(repo, "new", "sprint", "--title", "Later", "--goal", "g")
    later = item(repo, "Later")["id"]
    b(repo, "new", "bug", "--title", "Queued", "--sprint", later, "--severity", "S3",
      "--repro", argstr(is_file("src/e.txt")), "--goal", "e exists")
    assert item(repo, "Queued")["status"] == "draft"
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_started_sprint_work_state():
    """kbgit.work_state judges a KB-Work id by its item at the commit: claimed, in an active sprint."""
    files = {
        "SP-aaaaaaaa": {"kind": "sprint", "status": "active"},
        "SP-bbbbbbbb": {"kind": "sprint", "status": "planned"},
        "ST-aaaaaaaa": {"kind": "story", "status": "doing", "sprint": "SP-aaaaaaaa"},
        "TK-aaaaaaaa": {"kind": "task", "status": "doing", "parent": "ST-aaaaaaaa"},
        "TK-bbbbbbbb": {"kind": "task", "status": "todo", "parent": "ST-aaaaaaaa"},
        "ST-bbbbbbbb": {"kind": "story", "status": "doing", "sprint": "SP-bbbbbbbb"},
        "BG-aaaaaaaa": {"kind": "bug", "status": "doing"},
        "BG-bbbbbbbb": {"kind": "bug", "status": "done", "sprint": "SP-aaaaaaaa"},
        "ST-cccccccc": {"kind": "story", "status": "todo", "sprint": "SP-aaaaaaaa", "review": True},
    }
    load = lambda rel: json.dumps(files[Path(rel).stem]) if Path(rel).stem in files else None  # noqa: E731
    code = ["src/a.txt", "kb/_self/backlog/TK-aaaaaaaa.json"]
    state = lambda ids, paths=code: kbgit.work_state([ids], paths, load)  # noqa: E731
    assert state("TK-aaaaaaaa, BG-bbbbbbbb") == []  # claimed or done, in an active sprint (the task through its story)
    assert state("SP-aaaaaaaa, SP-bbbbbbbb, ST-cccccccc") == []  # the sprint and review items themselves
    assert ["not claimed" in x for x in state("TK-bbbbbbbb")] == [True]  # planted: unclaimed
    assert state("ST-bbbbbbbb") == ["ST-bbbbbbbb is not in a started sprint (SP-bbbbbbbb is planned)"]  # planted
    assert state("BG-aaaaaaaa") == ["BG-aaaaaaaa is not in a started sprint (no sprint)"]  # planted: no sprint
    assert state("TK-bbbbbbbb, ST-bbbbbbbb", ["kb/_self/backlog/TK-bbbbbbbb.json"]) == []  # a backlog-planning commit


def test_started_sprint_check_trailers_refuses_unclaimed_work(sprint, monkeypatch):
    """check-trailers (trailer_audit, which the pre-push hook and sync's gate run) refuses a commit not yet on
    origin/main whose KB-Work item is not claimed, and leaves one already on origin/main alone."""
    repo, tk = sprint["repo"], sprint["tk"]
    commit(repo, "plan")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    kbgit._WANT.clear()
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)  # planted: the task is todo, not claimed
    _, _, bad = kbgit.trailer_audit("HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad
    assert kbgit.trailer_audit("HEAD", quiet=True, work_state_on=False)[2] == []
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    assert kbgit.trailer_audit("HEAD", quiet=True)[2] == []  # history stays as it is
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    commit(repo, "claim", tk)  # a backlog-planning commit
    (repo / "src" / "b.txt").write_text("b2\n", encoding="utf-8")
    commit(repo, "write b again", tk)
    assert kbgit.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


def test_claim_committed_before_work(sprint, monkeypatch):
    """/kb-item commits the claimed item file on its own right after `claim`, before any work commit: check-trailers
    reads the item as each commit has it, so a work commit made while the claim is uncommitted is refused (planted:
    the claim commit left out) and the same work after a claim commit passes."""
    repo, tk = sprint["repo"], sprint["tk"]
    rel = f"{backlog.REL_DIR}/{tk}.json"
    commit(repo, "plan")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    kbgit._WANT.clear()

    def only(path, msg):
        sh(repo, "git", "add", "--", path)
        sh(repo, "git", "commit", "-qm", msg, "-m", f"KB-Work: {tk}")

    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    only("src/b.txt", "write b")  # planted: the claim is still uncommitted
    _, _, bad = kbgit.trailer_audit("origin/main..HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad

    sh(repo, "git", "reset", "-q", "origin/main")  # keeps the claim and the work in the working tree
    kbgit._WANT.clear()
    only(rel, "claim")  # the claim commit: a backlog-planning commit
    only("src/b.txt", "write b")
    assert kbgit.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


def test_repository_backlog_is_valid():
    code, out = b(os.path.dirname(TOOLS), "check")
    assert code == 0, out


# ---- host and user names: read from the environment, planted here as placeholders, never printed

PLANTED_HOST, PLANTED_USER = "PL-LT-00123", "jan.kowalski"
PLANTED_PIECES = ("pl-lt-00123", "pllt00123", "pllt00~", "jan.kowalski", "jankowalski", "jankow~", "kowalski")


@pytest.fixture
def planted_names(monkeypatch):
    """This host is PL-LT-00123 and its user jan.kowalski, in this process and in the backlog.py it starts."""
    for k in backlog.HOST_ENV + backlog.USER_ENV + backlog.PROFILE_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("COMPUTERNAME", PLANTED_HOST)
    monkeypatch.setenv("USERNAME", PLANTED_USER)
    monkeypatch.setattr(backlog.socket, "gethostname", lambda: PLANTED_HOST)


def no_planted_piece(out):
    low = out.lower()
    return not any(p in low for p in PLANTED_PIECES)


def test_item_holds_host_names_pieces_of_a_name():
    assert backlog.name_pieces(PLANTED_HOST) == {"pl-lt-00123", "pllt00123", "pllt00~"}  # pl, lt: too short; 00123: no letter
    assert backlog.name_pieces(PLANTED_USER) == {"jan.kowalski", "jankowalski", "jankow~", "kowalski"}
    assert backlog.name_pieces("JanKowalskiCorp") == {"jankowalskicorp", "jankow~", "kowalski"}  # CamelCase parts
    assert backlog.name_pieces("PL-SRV-0042") == {"pl-srv-0042", "plsrv0042", "plsrv0~"}
    assert backlog.name_pieces("XYZ-PC01") == {"xyz-pc01", "xyzpc01", "pc01"}  # 4 characters with a digit
    for generic in ("runner", "root", "user", "admin", "container", "localhost", "DESKTOP"):
        assert backlog.name_pieces(generic) == set(), generic
    # a GitLab runner's host name: only its token and the whole name are pieces, not project or concurrent
    assert backlog.name_pieces("runner-ab12cd34-project-42-concurrent-0") == {
        "runner-ab12cd34-project-42-concurrent-0", "runnerab12cd34project42concurrent0", "ab12cd34"}


def test_item_holds_host_names_read_from_the_environment(planted_names):
    pieces = backlog.host_user_pieces()
    assert set(pieces) == set(PLANTED_PIECES)
    assert pieces["kowalski"] == "user" and pieces["pllt00123"] == "host"
    assert backlog.host_user_pieces({"COMPUTERNAME": "runner", "USERNAME": "root"}) == {"pl-lt-00123": "host",
                                                                                        "pllt00123": "host", "pllt00~": "host"}


def test_item_holds_host_names_refused_without_the_piece(sprint, planted_names, capsys):
    repo = sprint["repo"]
    edit(repo, sprint["st"], goal="b exists on \\\\PL-LT-00123\\share")
    edit(repo, sprint["tk"], title="Task for Kowalski", gates=[{"id": "g", "kind": "blocking",
                                                                "question": "ask jan.kowalski first"}])
    assert backlog.main(["--root", str(repo), "check"]) == 1
    out = capsys.readouterr().out
    assert no_planted_piece(out), "a planted name was printed"
    # the id with its title withheld, which may hold the name too, and the field
    assert f"{sprint['st']} (title withheld" in out and "“Story”" not in out, out
    assert "field goal holds a piece of this host's computer name" in out
    assert f"{sprint['tk']} (title withheld" in out and "field title holds a piece of this host's user name" in out
    assert "field gates[0].question holds a piece of this host's user name" in out
    code, out = b(repo, "check")  # the command line, the push gate's form
    assert code == 1 and "errors=3" in out and no_planted_piece(out), "a planted name was printed"


def test_item_holds_host_names_clean_item_passes(sprint, planted_names, capsys):
    edit(sprint["repo"], sprint["st"], goal="b exists on \\\\PL-SRV-0042\\share for kowal")  # other names, a short one
    assert backlog.main(["--root", str(sprint["repo"]), "check"]) == 0, capsys.readouterr().out
    assert b(sprint["repo"], "check")[0] == 0


def test_item_holds_host_names_short_form(planted_names):
    """Windows' 8.3 form of a long profile name (a TEMP path's JANKOW~1 profile folder) is a piece too, and
    the profile folder's name counts as the user's."""
    assert "jankow~" in backlog.name_pieces("jan.kowalski") and "jankow~" in backlog.name_pieces("JanKowalskiCorp")
    assert not any("~" in p for p in backlog.name_pieces("kowal12"))  # 8 characters or fewer: never shortened
    pieces = backlog.host_user_pieces({"USERNAME": "x", "USERPROFILE": "C:/Users/<profile>/jan.kowalski"})
    assert "kowalski" in pieces and any(p in "c:/users/jankow~1/appdata/local/temp" for p in pieces)


def test_item_holds_host_names_never_printed_by_any_command(sprint, planted_names):
    """list, tree, show and claim print a named item's title and fields with the name withheld, not only check."""
    repo = sprint["repo"]
    edit(repo, sprint["tk"], title="Task for Kowalski on PL-LT-00123")
    for argv in (["list"], ["tree"], ["show", sprint["tk"]], ["claim", sprint["tk"], "--by", "w"]):
        code, out = b(repo, *argv)
        assert sprint["tk"] in out and no_planted_piece(out), (argv, out)


def test_name_check_exempts_project_path(sprint, planted_names, capsys):
    """A namespace equal to the user's name: the repository path (read from the remotes) is no hit, the name
    elsewhere still is."""
    repo = sprint["repo"]
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@gitlab.com:jan.kowalski/it-ops-kb.git"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "pub", "https://github.com/Jan.Kowalski/it-ops-kb"], check=True)
    assert backlog.project_paths(repo) == {"jan.kowalski/it-ops-kb", "jan.kowalski%2fit-ops-kb"}
    edit(repo, sprint["st"], goal="glab api projects/jan.kowalski%2Fit-ops-kb/runners, see Jan.Kowalski/it-ops-kb")
    assert backlog.main(["--root", str(repo), "check"]) == 0, capsys.readouterr().out
    edit(repo, sprint["st"], goal="projects/jan.kowalski%2Fit-ops-kb, ask jan.kowalski")
    assert backlog.main(["--root", str(repo), "check"]) == 1
    out = capsys.readouterr().out
    assert "field goal holds a piece of this host's user name" in out and no_planted_piece(out)


def test_item_holds_host_names_real_backlog_passes_on_this_host():
    """The names of the host running the tests, never spelled here: the real backlog holds no piece of them. (Not
    the planted ones: the backlog writes those placeholders on purpose.)"""
    assert backlog.items_holding_names(backlog.Backlog(os.path.dirname(TOOLS))) == {}
    code, out = b(os.path.dirname(TOOLS), "check")
    assert code == 0, out


# ---- knowledge: an item's asks and kb references, resolved against the kb of the clone

FACT = "Demo tools print their version. [DOC S100]"
ARTICLE = f"---\ntopic: demo/tool\nstatus: partial\n---\n\n# Demo tool\n\n## Facts\n- {FACT}\n"
CSV = "name,source,tag\nalpha,S100,DOC\n"


@pytest.fixture
def kb(repo):
    """The repository gets a public kb root: a source, a QK answer, an article with one fact and a data file; a
    story to carry `knowledge`."""
    root = repo / "kb" / "public"
    (root / "demo").mkdir(parents=True)
    (root / "_root.md").write_text("---\nroot: public\nid_prefix: S\nvisibility: public\n---\n\n# public\n",
                                   encoding="utf-8", newline="\n")
    (root / "_sources.csv").write_text("id,url\nS100,https://example.com/a\nS-abcdefgh,https://example.com/b\n",
                                       encoding="utf-8", newline="\n")
    (root / "_answers.md").write_text("# Answers\n\n## QK-demo-question. What does the demo print?\n- It prints. "
                                      "[DOC S100]\n", encoding="utf-8", newline="\n")
    (root / "demo" / "tool.md").write_text(ARTICLE, encoding="utf-8", newline="\n")
    (root / "demo" / "rows.csv").write_text(CSV, encoding="utf-8", newline="\n")
    b(repo, "new", "epic", "--title", "Carrier", "--goal", "carries knowledge")
    commit(repo, "kb")
    return repo, item(repo, "Carrier")["id"]


def key(text=FACT):
    import kbfacts
    return kbfacts.fact_key(text)


def test_knowledge_refs_of_every_kind_resolve(kb):
    repo, iid = kb
    refs = ["demo/tool", "public/demo/tool", "QK-demo-question", "public:QK-demo-question", "S100", "S-abcdefgh",
            f"public/demo/tool.md#{key()}", f"demo/tool.md#{key()}"]
    edit(repo, iid, knowledge={"ask": ["What does the demo print?"], "refs": refs})
    code, out = b(repo, "check")
    assert code == 0 and "errors=0 stale=0" in out, out


@pytest.mark.parametrize("ref, why", [
    ("demo/absent", "no such topic"),
    ("demo/tool.md", "no such topic"),  # a topic id has no extension
    ("public/_answers", "no such topic"),  # a ledger is no article
    ("QK-no-such-answer", "no such answer"),
    ("other:QK-demo-question", "no kb root"),
    ("S999", "no such source id"),
    ("S-zzzzzzzz", "no such source id"),
    ("public/demo/absent.md#" + "0" * 12, "no article or data file"),
    ("public/demo/tool.md#abc", "12 lowercase hex"),
    ("free text", "not a topic id"),
])
def test_knowledge_refs_missing_from_the_kb_are_refused(kb, ref, why):
    repo, iid = kb
    edit(repo, iid, knowledge={"refs": [ref]})
    code, out = b(repo, "check")
    assert code == 1 and why in out and f"{iid} “Carrier”: knowledge ref" in out, out


def test_knowledge_refs_fact_of_a_data_file_and_a_reworded_fact(kb):
    """A csv row's key resolves; the article's fact reworded (planted) is stale: printed, counted apart, exit 0."""
    repo, iid = kb
    csv_key = key("name=alpha; source=S100; tag=DOC")
    edit(repo, iid, knowledge={"refs": [f"public/demo/rows.csv#{csv_key}", f"public/demo/tool.md#{key()}"]})
    assert b(repo, "check")[0] == 0
    art = repo / "kb" / "public" / "demo" / "tool.md"
    art.write_text(ARTICLE.replace("print their version", "print their build"), encoding="utf-8", newline="\n")
    code, out = b(repo, "check")
    assert code == 0 and "errors=0 stale=1" in out, out
    assert f"{iid} “Carrier”: stale knowledge: fact {key()} is no longer in public/demo/tool.md" in out
    art.unlink()  # planted: the article removed is missing, not stale
    code, out = b(repo, "check")
    assert code == 1 and "no article or data file" in out, out


def test_knowledge_refs_shape_is_checked(kb):
    repo, iid = kb
    for bad in ("text", {"asks": []}, {"ask": "one question"}, {"ask": [""]}, {"refs": [1]}):
        edit(repo, iid, knowledge=bad)
        code, out = b(repo, "check")
        assert code == 1 and "knowledge" in out, (bad, out)
    edit(repo, iid, knowledge={"ask": ["What does the demo print?"], "refs": []})
    assert b(repo, "check")[0] == 0


def test_knowledge_refs_without_a_kb_are_refused(repo):
    b(repo, "new", "epic", "--title", "Carrier", "--goal", "g")
    edit(repo, item(repo, "Carrier")["id"], knowledge={"refs": ["S100"]})
    code, out = b(repo, "check")
    assert code == 1 and "no such source id" in out, out


# ---- knowledge state: show, next and horizon run the pack on each ask and ref of an item's `knowledge`

KS_TOOLS = ("backlog.py", "kbcommon.py", "kbfacts.py", "kbid.py", "ql_base.py", "aliases.csv")
KS_SOURCES = ("id,url,title,superseded_by,used_in\n"
              "S100,https://example.com/a,Zorbex agent guide,,demo/tool.md\n"
              "S101,https://example.com/b,Plimt gadget firmware notes,,demo/gadget.md\n")
KS_SUPERSEDED = KS_SOURCES.replace("Zorbex agent guide,,", "Zorbex agent guide,S101,")
KS_FACTS = ["The zorbex agent prints its build number at startup.", "The zorbex agent retries failed uploads three times."]
KS_GOOD = "How many times does the zorbex agent retry failed uploads?"
KS_CHECK = KS_GOOD[:-1] + " for Plimt?"  # `good`, with a `check:` line: the lead article never mentions Plimt
KS_WEAK = "Does the zorbex agent retry uploads with plimt firmware in quasar flash?"
KS_NONE = "How do I configure the wumpus frobnicator?"


def ks_article(topic, title, facts, source="S100"):
    return (f"---\ntopic: {topic}\nstatus: partial\n---\n\n# {title}\n\n## Facts\n"
            + "".join(f"- {f} [DOC {source}]\n" for f in facts))


def ks_fact(n):
    """The `<root>/<path>#<key>` ref of the n-th fact of the zorbex article."""
    return f"public/demo/tool.md#{key(KS_FACTS[n] + ' [DOC S100]')}"


def ks_states(out):
    """{text: state} of the `knowledge <state> ask|ref: <text>` lines of an output (a trailing `(why)` cut off)."""
    found = {}
    for ln in out.splitlines():
        m = re.match(r"\s*knowledge (\w+)\s+(?:ask|ref): (.*)$", ln)
        if m:
            found[re.sub(r" \([^()]*\)$", "", m.group(2))] = m.group(1)
    return found


class Ks:
    """A started sprint (the `sprint` fixture) with its own copy of the tools and a small kb of invented words, so the
    pack that show, next and horizon run answers from a corpus the test controls: two articles (zorbex, plimt) among
    twelve filler ones, one QK answer, two sources and an empty conflicts ledger."""

    def __init__(self, sprint):
        self.repo, self.tk, self.bg, self.sp = sprint["repo"], sprint["tk"], sprint["bg"], sprint["sp"]
        self.root = self.repo / "kb" / "public"
        (self.repo / "_tools").mkdir()
        for f in KS_TOOLS:
            shutil.copy(os.path.join(TOOLS, f), self.repo / "_tools" / f)
        (self.root / "demo").mkdir(parents=True)
        files = {
            "_root.md": "---\nroot: public\nid_prefix: S\nvisibility: public\n---\n\n# public\n",
            "_sources.csv": KS_SOURCES,
            "_answers.md": f"# Answers\n\n## QK-zorbex-retries. {KS_GOOD}\n- Three times. [DOC S100]\n",
            "_conflicts.md": "# Conflicts\n",
            "demo/tool.md": ks_article("demo/tool", "Zorbex sync agent", KS_FACTS),
            "demo/gadget.md": ks_article("demo/gadget", "Plimt gadget", [
                "The plimt gadget stores firmware in quasar flash.", "The plimt gadget resets after a wobble timeout."],
                                         "S101"),
            **{f"demo/filler{i}.md": ks_article(f"demo/filler{i}", f"Filler {i}", [
                f"Filler{i}a widget{i}b gizmo{i}c runs {i}d.", f"Sprocket{i}e flange{i}f."]) for i in range(12)},
        }
        for rel, text in files.items():
            self.write(rel, text)
        self.env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "CLAUDE_PLUGIN_DATA")} | {
            "KB_INDEX": "0"}

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8", newline="\n")

    def run(self, *a):
        """The copy of backlog.py in the repository, whose own kb is the one its pack reads."""
        p = subprocess.run([sys.executable, str(self.repo / "_tools" / "backlog.py"), *a], cwd=self.repo,
                           capture_output=True, text=True, encoding="utf-8", env=self.env)
        return p.returncode, p.stdout + p.stderr

    def know(self, asks=(), refs=(), item=None):
        edit(self.repo, item or self.tk, knowledge={"ask": list(asks), "refs": list(refs)})

    def show(self):
        code, out = self.run("show", self.tk)
        assert code == 0, out
        return out


@pytest.fixture
def ks(sprint):
    return Ks(sprint)


def test_knowledge_state_each_ask_has_one_of_five_states(ks):
    """A planted ask for each coverage: good, a good with a check line, weak and none."""
    ks.know(asks=[KS_GOOD, KS_CHECK, KS_WEAK, KS_NONE])
    out = ks.show()
    assert ks_states(out) == {KS_GOOD: "sufficient", KS_CHECK: "partial", KS_WEAK: "partial", KS_NONE: "unknown"}, out
    assert "check: line flags a possible false good" in out and "coverage weak" in out
    assert "the kb does not cover it" in out


def test_knowledge_state_refs_of_every_kind_are_sufficient_when_the_kb_covers_them(ks):
    refs = ["demo/tool", "public/demo/tool", "QK-zorbex-retries", "S100", ks_fact(1)]
    ks.know(refs=refs)
    out = ks.show()
    assert ks_states(out) == dict.fromkeys(refs, "sufficient"), out


def test_knowledge_state_reworded_fact_is_stale_and_a_missing_ref_is_unknown(ks):
    """The fact reworded (planted) is stale; an article, answer or source the kb lacks is unknown, never stale."""
    ks.know(refs=[ks_fact(1), "demo/absent", "QK-no-answer", "S999"])
    assert ks_states(ks.show())[ks_fact(1)] == "sufficient"
    art = ks.root / "demo" / "tool.md"
    ks.write("demo/tool.md", art.read_text(encoding="utf-8").replace("three times", "five times"))
    out = ks.show()
    assert ks_states(out) == {ks_fact(1): "stale", "demo/absent": "unknown", "QK-no-answer": "unknown",
                              "S999": "unknown"}, out
    assert f"fact {ks_fact(1).rpartition('#')[2]} is no longer in public/demo/tool.md" in out


def test_knowledge_state_superseded_source_makes_refs_and_asks_stale(ks):
    """S100 superseded (planted): the source, a fact citing it and an ask whose pack cites it are stale; the source
    S101 that nothing supersedes is not."""
    ks.know(asks=[KS_GOOD], refs=["S100", "S101", ks_fact(0)])
    assert set(ks_states(ks.show()).values()) == {"sufficient"}
    ks.write("_sources.csv", KS_SUPERSEDED)
    out = ks.show()
    assert ks_states(out) == {KS_GOOD: "stale", "S100": "stale", "S101": "sufficient", ks_fact(0): "stale"}, out
    assert "source S100 is superseded by S101" in out


def test_knowledge_state_open_conflict_entry_makes_the_article_conflicting_until_settled(ks):
    """An open `_conflicts.md` entry naming demo/tool (planted): the topic, its fact, an ask its article answers and
    a source the entry names are conflicting, another article is not. A `Resolved` note closes the entry."""
    ks.know(asks=[KS_GOOD], refs=["demo/tool", ks_fact(0), "S100", "demo/gadget"])
    entry = "- The two pages disagree on the retry count (S100). (topic: demo/tool)\n"
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry)
    out = ks.show()
    assert ks_states(out) == {KS_GOOD: "conflicting", "demo/tool": "conflicting", ks_fact(0): "conflicting",
                              "S100": "conflicting", "demo/gadget": "sufficient"}, out
    assert "open entry at public/_conflicts.md:3" in out
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry + "  - Resolved 2026-09-29: the later page settles it.\n")
    assert set(ks_states(ks.show()).values()) == {"sufficient"}


def test_knowledge_state_reviewed_note_closes_only_when_not_a_source_disagreement(ks):
    """A `Reviewed <date>, not a source disagreement` note closes an entry like `Resolved`; a `Reviewed <date>, still
    open` note leaves it open (both planted)."""
    ks.know(refs=["demo/tool"])
    entry = "- The two pages disagree on the retry count (S100). (topic: demo/tool)\n"
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry + "  - Reviewed 2026-09-28, still open: not re-read.\n")
    assert ks_states(ks.show()) == {"demo/tool": "conflicting"}
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry
             + "  - Reviewed 2026-09-28, not a source disagreement: two quantities; closed.\n")
    assert ks_states(ks.show()) == {"demo/tool": "sufficient"}


def test_knowledge_state_stale_wins_over_conflicting_and_both_over_coverage(ks):
    ks.know(refs=["demo/tool", ks_fact(0)])
    ks.write("_conflicts.md", "# Conflicts\n\n- Disagreement. (topic: demo/tool)\n")
    assert set(ks_states(ks.show()).values()) == {"conflicting"}
    ks.write("_sources.csv", KS_SUPERSEDED)
    assert set(ks_states(ks.show()).values()) == {"stale"}


def test_knowledge_state_next_and_horizon_print_it_and_the_hook_runs_no_pack(ks, monkeypatch, capsys):
    ks.know(asks=[KS_GOOD, KS_NONE], refs=["demo/tool"])
    ks.know(asks=[KS_GOOD, KS_NONE], refs=["demo/tool"], item=ks.bg)  # whichever of the two is next
    want = {KS_GOOD: "sufficient", KS_NONE: "unknown", "demo/tool": "sufficient"}
    for cmd in (("next", "--sprint", ks.sp, "--all"), ("horizon", "--sprint", ks.sp)):
        code, out = ks.run(*cmd)
        assert code == 0 and ks_states(out) == want, (cmd, out)
    code, out = ks.run("horizon", "--sprint", ks.sp, "--hook")
    assert code == 0 and "knowledge" not in out, out
    # in this process with the pack counted: the hook asks it nothing, horizon asks it once per ask and ref
    calls = []

    def canned(self, question):
        calls.append(question)
        return {"verdict": "good", "sources": [], "paths": [], "unmatched": [], "spread": None}

    monkeypatch.setattr(backlog.KnowledgeState, "pack", canned)
    bl = backlog.Backlog(ks.repo)
    backlog.cmd_horizon(bl, argparse.Namespace(sprint=ks.sp, hook=True))
    assert calls == [] and "knowledge" not in capsys.readouterr().out
    backlog.cmd_horizon(bl, argparse.Namespace(sprint=ks.sp, hook=False))
    assert len(calls) == 3, calls
    assert "knowledge sufficient" in capsys.readouterr().out


def test_knowledge_state_is_reported_never_stored_and_never_changes_readiness(ks):
    ready = ks.run("next", "--sprint", ks.sp, "--all")[1]
    ks.know(asks=[KS_NONE], refs=["demo/absent"])  # every state a non-sufficient one: still nothing it waits on
    before = {p.name: p.read_bytes() for p in (ks.repo / backlog.REL_DIR).glob("*.json")}
    with_state = ks.run("next", "--sprint", ks.sp, "--all")[1]
    assert [ln for ln in with_state.splitlines() if not ln.strip().startswith("knowledge")] == ready.splitlines()
    assert ks_states(with_state) == {KS_NONE: "unknown", "demo/absent": "unknown"}
    assert ks.show().rstrip().endswith("ready")
    ks.run("horizon")
    assert {p.name: p.read_bytes() for p in (ks.repo / backlog.REL_DIR).glob("*.json")} == before


def test_knowledge_state_costs_nothing_for_items_without_knowledge(sprint):
    """No item carries knowledge: next and horizon never load the pack (kbfacts stays unimported)."""
    code = ("import sys; sys.path.insert(0, %r); import backlog\n"
            "for cmd in (['next', '--all'], ['horizon']):\n"
            "    backlog.main(['--root', %r] + cmd)\n"
            "print('LOADED' if 'kbfacts' in sys.modules else 'NOT LOADED')\n") % (TOOLS, str(sprint["repo"]))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0 and p.stdout.strip().endswith("NOT LOADED"), p.stdout + p.stderr


def test_knowledge_state_against_the_repositorys_own_kb(sprint):
    """The real pack of this clone (`--root` names only where the backlog is): an eval-set question it answers `good`
    with no check line, in an article with no open conflict entry, is sufficient; one about nothing the kb holds is
    unknown. The ledger entries are the kb's own state, so the question is picked, not named."""
    import rag

    class Clone:
        root, items = backlog.ROOT, {}

    state = backlog.KnowledgeState(Clone())
    good = next(c["question"] for _, c in rag.eval_cases() if c["expect_verdict"] == "good"
                and state.of_ask(c["question"])[0] == "sufficient")
    edit(sprint["repo"], sprint["tk"], knowledge={"ask": [good, KS_NONE]})
    code, out = b(sprint["repo"], "show", sprint["tk"])
    assert code == 0 and ks_states(out) == {good: "sufficient", KS_NONE: "unknown"}, out


def test_knowledge_state_judge_maps_every_verdict(monkeypatch):
    """The mapping alone, the pack canned: none -> unknown, weak -> partial, good -> sufficient, and a good with a
    check line (an unmatched name, or facts spread apart) -> partial."""
    class Empty:
        root, items = "/nonexistent", {}

    ks = backlog.KnowledgeState(Empty())
    base = {"sources": [], "paths": [], "unmatched": [], "spread": None}
    table = [({"verdict": "none"}, "unknown"), ({"verdict": "weak"}, "partial"), ({"verdict": "good"}, "sufficient"),
             ({"verdict": "good", "unmatched": ["plimt"]}, "partial"),
             ({"verdict": "good", "spread": (1, 4)}, "partial")]
    for res, state in table:
        monkeypatch.setattr(ks, "pack", lambda q, res=res: base | res)
        assert ks.of_ask("q")[0] == state, res
    assert {s for _, s in table} == set(backlog.STATES) - {"stale", "conflicting"}


# ---- red-pipeline: a planted red and a green pipeline on origin's main, glab and gh replaced (no network)

def forge(monkeypatch, repo, pipelines, jobs=(), signed_in=True, logs=None):
    """origin is a GitLab project; `glab` answers the given pipelines (newest first), their jobs (one list for every
    pipeline, or a dict pipeline id -> list) and job logs (`logs`: job id -> trace text). The lists and the dicts are
    read on every call: a test changes them in place."""
    sh(repo, "git", "remote", "add", "origin", "https://gitlab.example.com/team/kb.git")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    real = backlog.run

    def fake(argv, cwd=None):
        if argv[:2] == ["git", "fetch"]:
            return 0, "", ""
        if argv[0] in ("glab", "gh"):
            if argv[1] == "auth":
                return (0, "", "") if signed_in else (1, "", "not logged in")
            if argv[-1].endswith("/trace"):
                jid = int(argv[-1].split("/")[-2])
                return (0, logs[jid], "") if logs and jid in logs else (1, "", "404 Not Found")
            if "/jobs?" in argv[-1] and jobs is None:
                return 1, "", "500 Internal Server Error"
            if "/jobs?" in argv[-1] and isinstance(jobs, dict):
                return 0, json.dumps(jobs.get(int(argv[-1].split("/pipelines/")[1].split("/")[0]), [])), ""
            return 0, json.dumps(jobs if "/jobs?" in argv[-1] else pipelines), ""
        return real(argv, cwd=cwd)

    monkeypatch.setattr(backlog, "run", fake)
    monkeypatch.setattr(backlog, "run_check", lambda root, c: (False, 1, ""))  # the repro fails: main is red


def head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def bugs(repo):
    return [it for it in backlog.Backlog(repo).items.values() if it["kind"] == "bug"]


def red_pipeline(repo, *a):
    return backlog.main(["--root", str(repo), "red-pipeline", *a])


def test_red_pipeline_files_one_s2_bug_per_pipeline(repo, monkeypatch, capsys):
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 902, "sha": sha, "status": "running"},
                              {"id": 901, "sha": sha, "status": "failed", "web_url": "https://x/901"},
                              {"id": 900, "sha": sha, "status": "success"}],
          jobs=[{"name": "kb-tests-windows", "status": "failed"}])
    assert red_pipeline(repo) == 0
    (bug,) = bugs(repo)
    assert bug["severity"] == "S2" and bug["status"] == "draft" and "pipeline 901" in bug["title"]
    assert bug["repro"]["run"] == backlog.STATUS_REPRO + ["--job", "kb-tests-windows"]
    assert backlog.validate(backlog.Backlog(repo)) == []
    capsys.readouterr()
    assert red_pipeline(repo) == 0  # the same pipeline again: named by the bug, nothing filed
    assert "already filed" in capsys.readouterr().out
    assert len(bugs(repo)) == 1


def test_red_pipeline_gate_job_is_s1_and_joins_the_active_sprint(sprint, monkeypatch):
    repo = sprint["repo"]
    forge(monkeypatch, repo, [{"id": 77, "sha": head(repo), "status": "failed"}],
          jobs=[{"name": "kb-tests", "status": "failed"}])
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 77" in x["title"]]
    assert bug["severity"] == "S1" and bug["sprint"] == sprint["sp"] and bug["status"] == "todo"


GATE_PASSED = [{"id": 3, "name": "kb-trailers", "status": "success"}, {"id": 2, "name": "kb-tests", "status": "success"}]


def test_red_pipeline_green_files_nothing(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "success"},
                              {"id": 4, "sha": head(repo), "status": "failed"}], jobs=GATE_PASSED)
    assert red_pipeline(repo) == 0
    assert bugs(repo) == [] and "green" in capsys.readouterr().out
    assert red_pipeline(repo, "--status") == 0


def test_red_pipeline_unrun_gate_is_not_green(repo, monkeypatch, capsys):
    """The job list of a main pipeline whose status says success while no job ran (every job manual with
    allow_failure, the CI minutes quota spent): unverified, never green; each planted gate state keeps it so."""
    quota = {"status": "failed", "failure_reason": "ci_quota_exceeded", "allow_failure": True}
    pipelines = [{"id": 61, "sha": head(repo), "status": "success"}]
    jobs = [{"id": 15, "name": "kb-tests-windows", "status": "manual", "allow_failure": True},
            {"id": 14, "name": "kb-trailers", **quota}, {"id": 13, "name": "tool-stress", **quota},
            {"id": 12, "name": "kb-tests-floor", **quota}, {"id": 11, "name": "kb-tests", **quota}]
    forge(monkeypatch, repo, pipelines, jobs=jobs)
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 1
    out = capsys.readouterr().out
    assert "pipeline 61 of main is unverified" in out, out
    assert "kb-tests failed (ci_quota_exceeded), kb-trailers failed (ci_quota_exceeded)" in out, out
    assert "kb-tests-floor" not in out and "tool-stress" not in out and "kb-tests-windows" not in out, out
    assert red_pipeline(repo) == 0 and bugs(repo) == []  # unverified is not red: nothing filed
    assert "unverified" in capsys.readouterr().out
    # planted: every other way a gate job does not pass, on a pipeline whose status is no failure
    for status, gate, said in (
            ("manual", [{"name": "kb-tests", "status": "manual"}, {"name": "kb-trailers", "status": "manual"}],
             "kb-tests manual, kb-trailers manual"),
            ("success", [{"name": "kb-tests", "status": "skipped"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests skipped"),
            ("canceled", [{"name": "kb-tests", "status": "canceled"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests canceled"),
            ("success", [{"name": "kb-tests", "status": "success"}], "kb-trailers not in the pipeline"),
            ("success", [{"name": "kb-tests", "status": "running"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests running")):
        pipelines[0]["status"] = status
        jobs[:] = [{"id": i, **j} for i, j in enumerate(gate)]
        assert red_pipeline(repo, "--status") == 1, (status, gate)
        out = capsys.readouterr().out
        assert "is unverified" in out and said in out, out
    assert red_pipeline(repo) == 0 and bugs(repo) == []
    # the gate ran and passed: the other jobs, manual or never started, leave main green
    pipelines[0]["status"] = "success"
    jobs[:] = [{"id": 15, "name": "kb-tests-windows", "status": "manual"}, {"id": 13, "name": "tool-stress", **quota},
               {"id": 14, "name": "kb-trailers", "status": "success"}, {"id": 11, "name": "kb-tests", "status": "success"}]
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 0
    assert "pipeline 61 of main is green" in capsys.readouterr().out
    # planted: a job list glab cannot read is no proof either
    monkeypatch.undo()
    sh(repo, "git", "remote", "remove", "origin")
    forge(monkeypatch, repo, pipelines, jobs=None)
    assert red_pipeline(repo, "--status") == 1
    assert "the pipeline's jobs could not be read" in capsys.readouterr().out


def test_red_pipeline_failed_script_under_allow_failure_is_red(sprint, monkeypatch):
    """A job whose script ran and failed under allow_failure leaves the pipeline's status success: its job list makes
    it red, S1 when it is kb-tests, and the fingerprint names that job, not the one that never started."""
    repo = sprint["repo"]
    forge(monkeypatch, repo, [{"id": 62, "sha": head(repo), "status": "success"}],
          jobs=[{"id": 14, "name": "kb-trailers", "status": "success"},
                {"id": 12, "name": "kb-tests-floor", "status": "failed", "failure_reason": "ci_quota_exceeded"},
                {"id": 11, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure",
                 "allow_failure": True}],
          logs={11: "FAILED _tools/test_x.py::test_a - assert 1 == 2\n"})
    assert red_pipeline(repo, "--status") == 1
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 62" in x["title"]]
    assert bug["severity"] == "S1" and bug["title"].endswith(": kb-tests"), bug["title"]
    assert f"fingerprint {backlog.failure_fingerprint('kb-tests', '_tools/test_x.py::test_a')}" in bug["links"]


def test_red_pipeline_reads_a_pipeline_where_a_job_ran(sprint, monkeypatch, capsys):
    """Every job is manual, so most pipelines of main are ones nobody started. Planted: a red started pipeline, then
    newer ones where no job ran; the red one is read, its bug's repro names its failed job and fails until that job
    passes again, not when another job passes or a push starts nothing; a timed-out or stuck job is red too."""
    repo = sprint["repo"]
    monkeypatch.setattr(ql_deliver, "GATE_JOBS", ())  # the default: no job is a gate
    manual = [{"id": 30, "name": "kb-tests", "status": "manual"}, {"id": 31, "name": "kb-trailers", "status": "manual"},
              {"id": 32, "name": "kb-lint", "status": "failed", "failure_reason": "ci_quota_exceeded"}]
    pipelines = [{"id": 73, "sha": head(repo), "status": "manual"}, {"id": 72, "sha": head(repo), "status": "skipped"},
                 {"id": 71, "sha": head(repo), "status": "success"}]
    jobs = {73: manual, 72: [],
            71: [{"id": 11, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure",
                  "started_at": "2026-09-30T08:00:00Z"}, {"id": 12, "name": "kb-trailers", "status": "manual"}]}
    forge(monkeypatch, repo, pipelines, jobs=jobs, logs={11: "FAILED _tools/test_x.py::test_a - assert 1 == 2\n"})
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 1
    assert "pipeline 71 of main is red" in capsys.readouterr().out
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 71" in x["title"]]
    assert bug["severity"] == "S1" and bug["repro"]["run"] == backlog.STATUS_REPRO + ["--job", "kb-tests"], bug
    # a newer pipeline where only another job ran and passed: main reads green, the bug's job is still red
    pipelines.insert(0, {"id": 74, "sha": head(repo), "status": "manual"})
    jobs[74] = [{"id": 40, "name": "kb-trailers", "status": "success"}, {"id": 41, "name": "kb-tests", "status": "manual"}]
    assert red_pipeline(repo, "--status") == 0
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1
    assert "the newest kb-tests pipeline 71 of main is red" in capsys.readouterr().out
    # kb-tests runs again and passes: the bug's repro passes
    pipelines.insert(0, {"id": 75, "sha": head(repo), "status": "manual"})
    jobs[75] = [{"id": 50, "name": "kb-tests", "status": "success"}]
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 0
    # a job that ran past its timeout, or got stuck, is red
    for reason in ("job_execution_timeout", "stuck_or_timeout_failure"):
        pipelines.insert(0, {"id": 76, "sha": head(repo), "status": "success"})
        jobs[76] = [{"id": 60, "name": "kb-tests-windows", "status": "failed", "failure_reason": reason}]
        assert red_pipeline(repo, "--status") == 1, reason
        assert red_pipeline(repo, "--status", "--job", "kb-tests-windows") == 1, reason
        pipelines.pop(0)
    # no job ran in any pipeline: the newest finished one is read, and is green
    pipelines[:] = [{"id": 73, "sha": head(repo), "status": "manual"}, {"id": 72, "sha": head(repo), "status": "skipped"}]
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 0
    assert "no job ran in the last" in capsys.readouterr().out
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1  # the job never ran: not checked


def test_red_pipeline_status_is_the_repro_of_a_red_main(repo, monkeypatch):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}])
    assert red_pipeline(repo, "--status") == 1


def test_red_pipeline_automatic_revert_covers_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 8, "sha": auto, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert bugs(repo) == []


def test_red_pipeline_revert_of_another_commit_does_not_cover_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "a human commit")
    human = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 9, "sha": human, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert "pipeline 9" in bugs(repo)[0]["title"]


def test_red_pipeline_notes_when_not_signed_in(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}], signed_in=False)
    assert red_pipeline(repo) == 0
    assert "not signed in" in capsys.readouterr().out and bugs(repo) == []
    assert red_pipeline(repo, "--status") == 1


# ---- failure fingerprint: planted logs of red pipelines, the same failure twice and a different one

def test_fingerprint_names_the_first_failing_test_or_normalised_error_line():
    log = ("2026-09-01T10:00:00.1234567Z \x1b[31msection_start:1700000000:tests\x1b[0m\n"
           "_tools/test_a.py::test_one PASSED\n"
           "_tools/test_b.py::test_two FAILED\n"
           "FAILED _tools/test_c.py::test_three - assert 1 == 2\n")
    assert backlog.first_failure(log) == "_tools/test_b.py::test_two"
    a = backlog.first_failure("2026-09-01T10:00:00Z check: error in kb/x.md:12 (sha 0123abcd9)\nERROR: Job failed\n")
    b_ = backlog.first_failure("2026-09-02T11:30:01Z check: error in kb/x.md:57 (sha fedcba987)\nERROR: Job failed\n")
    assert a == b_ == "check: error in kb/x.md:<n> (sha <hex>)"
    assert backlog.first_failure("all good\n") == "" and backlog.first_failure(None) == ""
    fp = backlog.failure_fingerprint("kb-tests", a)
    assert len(fp) == 12 and int(fp, 16) >= 0
    assert fp == backlog.failure_fingerprint("kb-tests", b_)
    assert fp != backlog.failure_fingerprint("kb-tests-windows", a)  # another job
    assert fp != backlog.failure_fingerprint("kb-tests", "_tools/test_b.py::test_two")  # another failure


def _gitlab_com_log(failing):
    """A kb-tests-windows log as GitLab.com writes it: every line behind a timestamp and a stream marker."""
    return ("2026-09-29T01:06:30.100000Z 00O \x1b[0KRunning with gitlab-runner 18.4.0 (0123abcd)\n"
            "2026-09-29T01:06:31.200000Z 00O section_start:1759107991:step_script\r\x1b[0K\x1b[0K\x1b[36;1mExecuting\n"
            "2026-09-29T01:06:40.300000Z 01O _tools/test_a.py::test_ok PASSED\n"
            f"2026-09-29T01:06:40.889927Z 01O FAILED {failing} - AssertionError: 1 != 2\n"
            "2026-09-29T01:06:40.900000Z 01O+ continued output\n"
            "2026-09-29T01:06:41.000000Z 01E ERROR: Job failed: exit code 1\n")


def test_fingerprint_strips_gitlab_com_timestamp_and_stream_marker():
    ids = ["_tools/test_a.py::test_x", "_tools/test_b.py::test_y", "_tools/test_c.py::test_z"]
    assert [backlog.first_failure(_gitlab_com_log(t)) for t in ids] == ids
    fps = {backlog.failure_fingerprint("kb-tests-windows", backlog.first_failure(_gitlab_com_log(t))) for t in ids}
    assert len(fps) == 3  # three different failures, three fingerprints
    # the error-line fallback strips the prefix too: the same error at another time and stream gives one line
    a = backlog.first_failure("2026-09-29T01:06:41.000000Z 01E ERROR: Job failed: exit code 1\n")
    b_ = backlog.first_failure("2026-09-30T08:00:00.5Z 02O+ ERROR: Job failed: exit code 1\n")
    assert a == b_ == "ERROR: Job failed: exit code <n>"
    # a line without the prefix keeps a leading stream-like token
    assert backlog.first_failure("01E error: x\n") == "<n>E error: x"


# ---- recorded real GitLab.com job logs (_tools/fixtures/forge_logs/): the synthetic logs above are the author's
# guess at the format; these are what the forge sent, CRs, colour codes and section markers included

FORGE_LOGS = Path(TOOLS) / "fixtures" / "forge_logs"
REAL_WIN_FIRST = "_tools/test_kb_mcp.py::test_status_says_how_far_an_installed_plugin_is_behind_its_marketplace"
REAL_LINUX_FIRST = "_tools/test_kb_http.py::test_kb_http_roots_default_serves_public_only"


def real_forge_log(name):
    """(job, log) of a recorded real job log: its lines joined byte for byte as the forge sent them."""
    doc = json.loads((FORGE_LOGS / f"{name}.json").read_text(encoding="utf-8"))
    return doc["job"], "".join(doc["lines"])


def test_real_forge_log_first_failure_is_its_first_failing_test(monkeypatch):
    win_job, win = real_forge_log("gitlab-com-kb-tests-windows")
    lin_job, lin = real_forge_log("gitlab-com-kb-tests")
    assert (win_job, lin_job) == ("kb-tests-windows", "kb-tests")
    assert re.search(r"^\d{4}-\d\d-\d\dT[\d:.]+Z \d\d[OE] ", win, re.M) and "\r\n" in win and "\x1b[" in lin
    assert backlog.first_failure(win) == REAL_WIN_FIRST
    assert backlog.first_failure(lin) == REAL_LINUX_FIRST
    # two real failures under one job name give two fingerprints, not the one every real log gave (BG-jam2lysj)
    fps = {backlog.failure_fingerprint("kb-tests-windows", backlog.first_failure(x)) for x in (win, lin)}
    assert len(fps) == 2
    # planted: the parser without the GitLab.com timestamp and stream-marker rule reads no test id from either, only
    # an error line with the runner's timestamp in it
    monkeypatch.setattr(backlog, "LOG_PREFIX_RE", re.compile(r"^\s*(?:section_(?:start|end):\d+:\S+\s*)?"))
    for log, test_id in ((win, REAL_WIN_FIRST), (lin, REAL_LINUX_FIRST)):
        assert backlog.first_failure(log) != test_id and backlog.first_failure(log).startswith("<n>-<n>-<n>T")


def test_real_forge_log_red_pipeline_files_one_bug_per_real_failure(repo, monkeypatch):
    """red-pipeline end to end over the recorded logs: each real failure of kb-tests-windows files its own bug, whose
    fingerprint names the test that failed first."""
    sha = head(repo)
    _, win = real_forge_log("gitlab-com-kb-tests-windows")
    _, lin = real_forge_log("gitlab-com-kb-tests")
    pipelines = [{"id": 801, "sha": sha, "status": "failed"}]
    jobs = [{"id": 30, "name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}]
    logs = {30: win}
    forge(monkeypatch, repo, pipelines, jobs=jobs, logs=logs)
    assert red_pipeline(repo) == 0
    (first,) = bugs(repo)
    assert f"fingerprint {backlog.failure_fingerprint('kb-tests-windows', REAL_WIN_FIRST)}" in first["links"]
    pipelines[:] = [{"id": 802, "sha": sha, "status": "failed"}]
    logs[30] = lin
    assert red_pipeline(repo) == 0
    (second,) = [x for x in bugs(repo) if x["id"] != first["id"]]
    assert f"fingerprint {backlog.failure_fingerprint('kb-tests-windows', REAL_LINUX_FIRST)}" in second["links"]


def test_fingerprint_same_failure_one_bug_different_failure_a_second(repo, monkeypatch, capsys):
    sha = head(repo)
    pipelines = [{"id": 901, "sha": sha, "status": "failed"}]
    jobs = [{"id": 11, "name": "lint", "status": "failed"}, {"id": 10, "name": "check", "status": "failed"}]
    logs = {10: "2026-09-01T10:00:00Z FAILED _tools/test_x.py::test_a - assert 3 == 4\n", 11: "lint error\n"}
    forge(monkeypatch, repo, pipelines, jobs=jobs, logs=logs)
    assert red_pipeline(repo) == 0
    (first,) = bugs(repo)
    fp = backlog.failure_fingerprint("check", "_tools/test_x.py::test_a")  # the first failed job by name
    assert first["links"] == ["pipeline 901", f"fingerprint {fp}"]
    assert "_tools/test_x.py::test_a" in first["notes"]
    # a later pipeline failing the same way (other job ids, times and numbers): no second bug, its pipeline is added
    pipelines[:] = [{"id": 902, "sha": sha, "status": "failed"}]
    jobs[:] = [{"id": 20, "name": "check", "status": "failed"}]
    logs.clear()
    logs[20] = "2026-09-03T08:15:42Z FAILED _tools/test_x.py::test_a - assert 7 == 9\n"
    capsys.readouterr()
    assert red_pipeline(repo) == 0
    assert "fails the same way" in capsys.readouterr().out
    (same,) = bugs(repo)
    assert same["id"] == first["id"] and same["links"] == ["pipeline 901", f"fingerprint {fp}", "pipeline 902"]
    assert backlog.validate(backlog.Backlog(repo)) == []
    assert red_pipeline(repo) == 0 and len(bugs(repo)) == 1  # 902 again: named in the links, nothing filed
    # a different failure: a second bug with its own fingerprint
    pipelines[:] = [{"id": 903, "sha": sha, "status": "failed"}]
    logs[20] = "FAILED _tools/test_y.py::test_b - KeyError\n"
    assert red_pipeline(repo) == 0
    second = [x for x in bugs(repo) if x["id"] != first["id"]]
    assert len(second) == 1
    assert second[0]["links"] == ["pipeline 903", f"fingerprint {backlog.failure_fingerprint('check', '_tools/test_y.py::test_b')}"]


def test_fingerprint_of_a_closed_bug_files_a_new_one(repo, monkeypatch):
    sha = head(repo)
    pipelines = [{"id": 31, "sha": sha, "status": "failed"}]
    forge(monkeypatch, repo, pipelines, jobs=[{"id": 5, "name": "check", "status": "failed"}],
          logs={5: "Traceback (most recent call last):\n"})
    assert red_pipeline(repo) == 0
    (old,) = bugs(repo)
    edit(repo, old["id"], status="dropped")  # planted: only an open bug takes the pipeline
    pipelines[:] = [{"id": 32, "sha": sha, "status": "failed"}]
    assert red_pipeline(repo) == 0
    new = [x for x in bugs(repo) if x["id"] != old["id"]]
    assert len(new) == 1 and "pipeline 32" in new[0]["links"] and new[0]["links"][1] == old["links"][1]


class TestDoneLane:
    """done reads the integration main as last fetched: a code-lane KB-Work commit must be its ancestor."""

    def worked(self, sprint, path="src/b.txt"):
        repo, tk = sprint["repo"], sprint["tk"]
        assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
        commit(repo, "claim", tk)
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("b\n", encoding="utf-8")
        commit(repo, "write b", tk)
        return repo, tk

    def done(self, repo, tk):
        p = subprocess.run([sys.executable, TOOL, "--root", str(repo), "done", tk], cwd=repo, capture_output=True,
                           text=True, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    def test_unmerged_code_commit_is_refused_naming_the_branch(self, sprint):
        repo, tk = self.worked(sprint)
        sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD~1")  # planted: the code commit is not on main
        code, out = self.done(repo, tk)
        assert code == 1 and "not on origin/main" in out and f"code/{tk}" in out, out

    def test_missing_integration_ref_is_refused(self, sprint):
        repo, tk = self.worked(sprint)
        code, out = self.done(repo, tk)
        assert code == 1 and "not fetched" in out, out

    def test_merged_code_commit_passes(self, sprint):
        repo, tk = self.worked(sprint)
        land(repo)
        code, out = self.done(repo, tk)
        assert code == 0, out

    def test_done_counts_descendant_commits_unmerged_task_code(self, sprint):
        """A story whose task's code commit is not on main is refused, naming the task's code branch."""
        repo, st, tk = story_with_touches(sprint)
        finish_task(repo, tk)
        before = subprocess.run(["git", "log", "--format=%H", "--grep", "write b", "-1"], cwd=repo,
                                capture_output=True, text=True, encoding="utf-8").stdout.strip()
        sh(repo, "git", "update-ref", "refs/remotes/origin/main", f"{before}~1")  # planted: task code not on main
        code, out = self.done(repo, st)
        assert code == 1 and "not on origin/main" in out and f"code/{tk}" in out, out

    def test_content_item_needs_no_integration_main(self, sprint):
        repo, tk = self.worked(sprint, "kb/public/x/a.md")
        edit(repo, tk, checks=[{"run": is_file("kb/public/x/a.md")}], touches=["kb/public/**"])
        commit(repo, "widen", tk)
        code, out = self.done(repo, tk)
        assert code == 0, out
