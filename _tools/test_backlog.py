"""backlog.py in a throwaway git repository: items are created, validated, scheduled, finished and deleted.

Each refusal has a planted failure: a bug whose repro passes or fails for its own error (not found, a SyntaxError in
its own code, a usage error, no tests selected), a repro that passes doing nothing in this clone (no public remote;
refused by done until a check runs tests or the operator accepts), a check that runs no code (warned of), a repro that
only matches text in a file with no stated reason (refused by new; warned of by check, a read of _tools/ source named), a non-canonical file, a cycle, a blocking gate an
agent answers, a sprint started without the operator or with a work item without touches, a failing check, a commit outside `touches` (and the revert
that clears it), a review with an unconfirmed provisional answer, a malformed KB-Work trailer, a worked item of a
planned sprint, a KB-Work id whose item is unclaimed or not in a started sprint (work committed before its claim
commit included), a --commit commit with KB-Work outside its trailer paragraph or a file the command did not write,
a KB-* or malformed --trailer, a landing whose step fails (land stops there, naming it), and red pipelines that fail
the same way (one bug) or differently (a second), red-pipeline over the job-state table (`-k job_state_table`), or the same way as a closed bug (a new one), a near-duplicate new
item (warned of) and a recurring P1 item a started sprint leaves out (warned of), and a malformed `recurs`. The repository's
own backlog must pass `backlog.py check`.
"""
import json, os, shlex, shutil, subprocess, sys
from pathlib import Path

import pytest

import backlog
import bl_check
import bl_land
import kbgit
import kg_hooks
import kg_trailers
import bl_testkit
from bl_testkit import argstr, b, commit, edit, is_file, item, item_json, land, PASS, sh, TEXT_REPRO, TOOL, TOOLS

bl_testkit.bind(backlog)
# the kit's fixtures, bound by name where this module's tests ask for them (an import would shadow the arguments)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


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


def test_repro_own_import_error():
    """ST-4mdnjuep planted: a -c string that imports a name its module never had (a missing module, a missing name
    in a from-import, a module's missing attribute) fails for its own error, and so does one importing a test module
    that needs pytest; the same errors raised inside the code under test are failures it accepts."""
    f = backlog.own_failure
    for code_ in ("import os; os.no_such_name_x", "from os import no_such_name_x", "import no_such_module_x"):
        p = subprocess.run([sys.executable, "-c", code_], capture_output=True, text=True)
        assert "cannot import" in (f(["python3", "-c", code_], p.returncode, p.stdout + p.stderr) or ""), code_
    tb = 'Traceback (most recent call last):\n  File "<string>", line 1, in <module>\n'
    pytest_tb = tb + '  File "/r/_tools/test_backlog.py", line 9, in <module>\n    import pytest\n'
    assert "needs pytest" in f(["python3", "-c", "import test_backlog"], 1,
                               pytest_tb + "ModuleNotFoundError: No module named 'pytest'\n")
    inner = tb + '  File "/r/_tools/bl_land.py", line 5, in own_failure\n    x.y\n'
    for err in ("AttributeError: module 'os' has no attribute 'y'", "ImportError: cannot import name 'z' from 'os'"):
        assert f(["python3", "-c", "import bl_land; bl_land.own_failure()"], 1, inner + err + "\n") is None, err
    assert f(["python3", "-c", "x = None; x.y"], 1, tb + "AttributeError: 'NoneType' object has no attribute 'y'\n") is None


def test_repro_fails_for_its_own_error_compound_shell():
    """BG-zvh7cvyo planted: a shell -c string that chains commands (&&, |) and misses a tool after its first word
    exits 127 for its own command, so both are refused as cannot start; a wrapper script (bash hook.sh) whose output
    names a tool inside it is still accepted, and so is a -c string that runs that script."""
    f = backlog.own_failure
    for argv, out in ((["sh", "-c", "cd /tmp && jq ."], "sh: line 1: jq: command not found\n"),
                      (["bash", "-c", "ls | jqx ."], "bash: line 1: jqx: command not found\n"),
                      (["sh", "-c", "FOO=1 true; jq ."], "sh: line 1: jq: command not found\n")):
        assert "cannot start" in (f(argv, 127, out) or ""), argv
    assert f(["bash", "hook.sh"], 127, "hook.sh: line 3: jq: command not found\n") is None
    assert f(["sh", "-c", "./hook.sh --x"], 127, "./hook.sh: line 3: jq: command not found\n") is None
    assert bl_land.own_words(["sh", "-c", "a && b || c; d | e"]) == {"a", "b", "c", "d", "e"}


def test_repro_fails_for_its_own_error_tool_and_wrapper(repo, colour):
    """BG-a3ubazze planted: a SyntaxError in a repository tool the repro runs (git tracks it: a 3.12-only construct
    on 3.11) is a genuine reproduction, filed; the same broken script untracked is the repro's own, also behind
    python's -u and -X options and a shell's -c; a wrapper's exit 127 naming a tool inside it is accepted, while one
    naming the command the repro launches is still its own."""
    broken = "import sys\nif True\n    sys.exit(1)\n"
    (repo / "tool.py").write_text(broken, encoding="utf-8")
    commit(repo, "a tool with a SyntaxError")
    (repo / "mine.py").write_text(broken, encoding="utf-8")
    refused_own_error(repo, "python3 -X dev mine.py", "cannot compile the repro's own code")
    code, out = new_bug(repo, "Tool", "python3 -u tool.py")
    assert code == 0 and "own error" not in out, out
    f = backlog.own_failure
    syntax = '  File "mine.py", line 2\n    if True\n           ^\nSyntaxError: expected \':\'\n'
    assert "cannot compile" in f(["sh", "-c", "python3 -u mine.py"], 1, syntax, repo)
    assert "cannot compile" in f(["python3", "-W", "ignore", "mine.py"], 1, syntax, repo)
    assert f(["python3", "-u", "tool.py"], 1, syntax.replace("mine.py", "tool.py"), repo) is None
    assert f(["bash", "hook.sh"], 127, "hook.sh: line 3: jq: command not found\n") is None
    assert f(["sh", "-c", "./hook.sh --x"], 127, "./hook.sh: line 3: jq: command not found\n") is None
    assert "cannot start" in f(["bash", "-c", "jq ."], 127, "bash: line 1: jq: command not found\n")
    assert "cannot start" in f(["bash", "hook.sh"], 127, "")


def test_new_warns_item_files_only_touches(sprint):
    """BG-2hxjopue planted: a bug whose touches are item files only can never pass done (it needs a KB-Work commit
    that changes another file): new warns and names the drop route, and so does check while it is open; touches that
    also name another file, or a story whose task does, give no warning."""
    repo, sp = sprint["repo"], sprint["sp"]
    code, out = b(repo, "new", "bug", "--title", "Fix an epic's text", "--sprint", sp, "--severity", "S4",
                  "--repro", argstr(is_file("src/z.txt")), "--goal", "z", "--touch", f"{backlog.REL_DIR}/EP-aaaaaaaa.json")
    assert code == 0 and "item files only" in out and "backlog.py drop ID --why" in out, out
    bg = item(repo, "Fix an epic's text")["id"]
    code, out = b(repo, "check")
    assert code == 0 and f"{bg} “Fix an epic's text”: its touches are item files only" in out, out
    edit(repo, bg, touches=[f"{backlog.REL_DIR}/**", "src/z.txt"])
    code, out = b(repo, "check")
    assert "item files only" not in out, out
    code, out = b(repo, "new", "bug", "--title", "Other", "--sprint", sp, "--severity", "S4",
                  "--repro", argstr(is_file("src/y.txt")), "--goal", "y", "--touch", "src/y.txt")
    assert code == 0 and "item files only" not in out, out
    assert backlog.item_files_only([f"{backlog.REL_DIR}/*.json"]) and not backlog.item_files_only([])
    assert not backlog.item_files_only([f"{backlog.REL_DIR}.md"])


def test_repro_tool_exit_code_warning(sprint):
    """ST-f5v3i3yd planted (BG-ncpteupy's repro): a python -c proof that runs a tool with subprocess and reads only
    its stdout passes when the tool crashes printing nothing, so new warns; one that also reads returncode or passes
    check=True gives no warning."""
    repo, sp = sprint["repo"], sprint["sp"]
    blind = ["python3", "-c", "import subprocess,sys;o=subprocess.run([sys.executable,'_tools/t.py'],"
             "capture_output=True,text=True).stdout;sys.exit(1 if 'x' in o else 0)"]
    code, out = b(repo, "new", "story", "--title", "Blind", "--sprint", sp, "--goal", "g", "--touch", "src/a.txt",
                  "--check", argstr(blind))
    assert code == 0 and "never its exit code" in out, out
    seen = [blind[0], blind[1], blind[2].replace(".stdout;", ";r=subprocess.run([sys.executable,'_tools/t.py']).returncode;")]
    code, out = b(repo, "new", "story", "--title", "Seen", "--sprint", sp, "--goal", "g", "--touch", "src/b.txt",
                  "--check", argstr(seen))
    assert code == 0 and "never its exit code" not in out, out
    so = bl_check.stdout_only
    assert so(blind) and not so(seen) and not so(["python3", "-c", "subprocess.run(['t'],check=True).stdout"])
    assert not so(["python3", "_tools/tests.py", "-k", "x"]) and not so(["python3", "-c", "print(1)"])


def test_new_task_refuses_sprint(repo):
    """new task|subtask --sprint exits 2 naming the rule and writes nothing; a story may still name a sprint."""
    _, out = b(repo, "new", "sprint", "--title", "Sp")
    sp = item(repo, "Sp")["id"]
    _, out = b(repo, "new", "story", "--title", "St", "--goal", "g", "--sprint", sp)
    st = item(repo, "St")["id"]
    before = sorted((Path(repo) / backlog.REL_DIR).glob("*.json"))
    for kind, parent in (("task", st), ("subtask", st)):
        code, out = b(repo, "new", kind, "--title", "Child", "--parent", parent, "--sprint", sp)
        assert code == 2 and "only stories and bugs name a sprint" in out, out
    assert sorted((Path(repo) / backlog.REL_DIR).glob("*.json")) == before, "a refused new writes nothing"
    code, out = b(repo, "new", "task", "--title", "Child", "--parent", st)
    assert code == 0, out


def test_repro_needs_behaviour_or_reason_new_refuses_then_files(repo):
    """new refuses a text-only repro with no reason (exit 2, nothing written), files one with --repro-reason and
    keeps the reason; a repro that runs the behaviour needs none, and --repro-reason without a bug's repro is refused."""
    (repo / "tool.sh").write_text("echo refused >&2\n", encoding="utf-8")
    code, out = new_bug(repo, "Text only", argstr(["python3", "-c", TEXT_REPRO]))
    assert code == 2 and "only matches text in a file" in out and "--repro-reason" in out, out
    assert not list((Path(repo) / backlog.REL_DIR).glob("*.json")), "a refused repro files nothing"
    code, out = b(repo, "new", "bug", "--title", "Text only", "--severity", "S4", "--goal", "x",
                  "--repro", argstr(["python3", "-c", TEXT_REPRO]), "--repro-reason", "the defect is the doc's wording")
    assert code == 0, out
    assert item(repo, "Text only")["repro_reason"] == "the defect is the doc's wording"
    code, out = new_bug(repo, "Behaviour", argstr(is_file("src/c.txt")))
    assert code == 0 and "repro_reason" not in item(repo, "Behaviour"), out
    code, out = b(repo, "new", "story", "--title", "Story", "--goal", "g", "--check", argstr(is_file("src/a.txt")),
                  "--repro-reason", "why")
    assert code == 2 and "for a bug's --repro" in out, out
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out and "only matches text" not in out, out


def test_drop_chain_leaves_check_green(sprint):
    """Dropping a three-item chain, dependants first, leaves no dropped item depending on a dropped one: check
    stays at errors=0 (planted: the links stay and check reports a dependency on a dropped item)."""
    repo = sprint["repo"]
    ids = []
    for n in "abc":
        b(repo, "new", "bug", "--title", f"Chain {n}", "--sprint", sprint["sp"], "--severity", "S4", "--repro",
          argstr(is_file("src/y.txt")), "--goal", "y exists", "--touch", "src/**")
        ids.append(item(repo, f"Chain {n}")["id"])
    first, second, third = ids
    edit(repo, second, depends_on=[first])
    edit(repo, third, depends_on=[second, first])
    assert b(repo, "drop", first, "--why", "x")[0] == 1  # still a dependency of open items
    for iid in (third, second, first):
        code, out = b(repo, "drop", iid, "--why", "chain not needed")
        assert code == 0, out
    assert all(item_json(repo, i)["status"] == "dropped" for i in ids)
    assert not any(item_json(repo, i).get("depends_on") for i in ids)
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


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
    monkeypatch.setattr(kg_trailers, "blob", lambda rev, rel: "{}" if (rev, rel) in have else None)
    assert kg_trailers.work_ok("abc", ["TK-aaaaaaaa"])
    assert not kg_trailers.work_ok("abc", ["TK-bbbbbbbb"])  # no such item
    assert not kg_trailers.work_ok("abc", ["task 7"])  # not an id
    assert not kg_trailers.work_ok("abc", ["TK-aaaaaaaa", "TK-aaaaaaaa"])  # a second line


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
    """kg_trailers.work_state judges a KB-Work id by its item at the commit: claimed, in an active sprint."""
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
    state = lambda ids, paths=code: kg_trailers.work_state([ids], paths, load)  # noqa: E731
    assert state("TK-aaaaaaaa, BG-bbbbbbbb") == []  # claimed or done, in an active sprint (the task through its story)
    assert state("SP-aaaaaaaa, SP-bbbbbbbb, ST-cccccccc") == []  # the sprint and review items themselves
    assert ["not claimed" in x for x in state("TK-bbbbbbbb")] == [True]  # planted: unclaimed
    assert state("ST-bbbbbbbb") == ["ST-bbbbbbbb is not in a started sprint (SP-bbbbbbbb is planned)"]  # planted
    assert state("BG-aaaaaaaa") == ["BG-aaaaaaaa is not in a started sprint (no sprint)"]  # planted: no sprint
    assert state("TK-bbbbbbbb", ["kb/_self/backlog/TK-bbbbbbbb.json"]) == []  # a backlog-planning commit


def test_check_trailers_planning_commit_names_item():
    """A backlog-planning commit passes the started-sprint rules, but must change the file of every item its KB-Work
    names. Planted: a commit naming two items that changes one is refused for the other, whichever order they are named
    in; naming both with both files changed, or an id with no item file, leaves nothing to report here."""
    files = {"TK-aaaaaaaa": {"kind": "task", "status": "todo"}, "ST-aaaaaaaa": {"kind": "story", "status": "todo"}}
    load = lambda rel: json.dumps(files[Path(rel).stem]) if Path(rel).stem in files else None  # noqa: E731
    one = ["kb/_self/backlog/TK-aaaaaaaa.json"]
    both = one + ["kb/_self/backlog/ST-aaaaaaaa.json"]
    out = kg_trailers.work_state(["TK-aaaaaaaa, ST-aaaaaaaa"], one, load)
    assert len(out) == 1 and out[0].startswith("ST-aaaaaaaa:") and "backlog.py set" in out[0], out  # planted
    out = kg_trailers.work_state(["ST-aaaaaaaa, TK-aaaaaaaa"], one, load)
    assert len(out) == 1 and out[0].startswith("ST-aaaaaaaa:"), out  # planted: the order does not matter
    assert kg_trailers.work_state(["TK-aaaaaaaa, ST-aaaaaaaa"], both, load) == []
    assert kg_trailers.work_state(["TK-aaaaaaaa, TK-zzzzzzzz"], one, load) == []  # no item file: work_ok reports it


def test_started_sprint_check_trailers_refuses_unclaimed_work(sprint, monkeypatch):
    """check-trailers (trailer_audit, which the pre-push hook and sync's gate run) refuses a commit not yet on
    origin/main whose KB-Work item is not claimed, and leaves one already on origin/main alone."""
    repo, tk = sprint["repo"], sprint["tk"]
    commit(repo, "plan")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    monkeypatch.setattr(kg_trailers, "KB", str(repo))
    kg_trailers._WANT.clear()
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)  # planted: the task is todo, not claimed
    _, _, bad = kg_trailers.trailer_audit("HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad
    assert kg_trailers.trailer_audit("HEAD", quiet=True, work_state_on=False)[2] == []
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    assert kg_trailers.trailer_audit("HEAD", quiet=True)[2] == []  # history stays as it is
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    commit(repo, "claim", tk)  # a backlog-planning commit
    (repo / "src" / "b.txt").write_text("b2\n", encoding="utf-8")
    commit(repo, "write b again", tk)
    assert kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


def test_check_trailers_flags_kb_work_outside_trailers(sprint, monkeypatch, capsys):
    """Planted: a work commit whose KB-Work line sits in a paragraph before Co-Authored-By, so git reads no KB-Work
    trailer: check-trailers refuses it, the commit-msg hook warns (and still lets the commit through), and the same
    commit already on origin/main is history, left alone. The trailer in the last paragraph passes."""
    repo, bg = sprint["repo"], sprint["bg"]
    commit(repo, "plan")
    assert b(repo, "claim", bg, "--by", "agent-1")[0] == 0
    commit(repo, "claim", bg)
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    monkeypatch.setattr(kg_trailers, "KB", str(repo))
    monkeypatch.setattr(kg_hooks, "KB", str(repo))
    kg_trailers._WANT.clear()
    stray = f"write c\n\nKB-Work: {bg}\n\nCo-Authored-By: A <a@example.com>\n"
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", stray)
    _, _, bad = kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)
    assert len(bad) == 1 and any("outside the trailer block" in ln for ln in bad[0][1]), bad
    assert kg_trailers.stray_work(stray)
    assert not kg_trailers.stray_work(f"write c\n\nCo-Authored-By: A <a@example.com>\nKB-Work: {bg}\n")
    assert not kg_trailers.stray_work("write c\n\nno work here\n")
    msg = repo / "MSG"
    msg.write_text(stray, encoding="utf-8")
    sh(repo, "git", "reset", "-q", "--soft", "HEAD^")
    kg_hooks.hook_commit_msg([str(msg)])
    assert "outside the trailer block" in capsys.readouterr().err
    sh(repo, "git", "commit", "-qm", stray)
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    kg_trailers._WANT.clear()
    assert kg_trailers.trailer_audit("HEAD", quiet=True)[2] == []  # history stays as it is
    (repo / "src" / "d.txt").write_text("d\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"write d\n\nCo-Authored-By: A <a@example.com>\nKB-Work: {bg}")
    assert kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


def test_claim_committed_before_work(sprint, monkeypatch):
    """/kb-item commits the claimed item file on its own right after `claim`, before any work commit: check-trailers
    reads the item as each commit has it, so a work commit made while the claim is uncommitted is refused (planted:
    the claim commit left out) and the same work after a claim commit passes."""
    repo, tk = sprint["repo"], sprint["tk"]
    rel = f"{backlog.REL_DIR}/{tk}.json"
    commit(repo, "plan")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    monkeypatch.setattr(kg_trailers, "KB", str(repo))
    kg_trailers._WANT.clear()

    def only(path, msg):
        sh(repo, "git", "add", "--", path)
        sh(repo, "git", "commit", "-qm", msg, "-m", f"KB-Work: {tk}")

    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    only("src/b.txt", "write b")  # planted: the claim is still uncommitted
    _, _, bad = kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad

    sh(repo, "git", "reset", "-q", "origin/main")  # keeps the claim and the work in the working tree
    kg_trailers._WANT.clear()
    only(rel, "claim")  # the claim commit: a backlog-planning commit
    only("src/b.txt", "write b")
    assert kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


@pytest.fixture
def research(repo, monkeypatch):
    """A planned sprint (start gate unanswered) with a research story (touches kb/public/**) and a code story
    (touches src/**), both draft, the plan committed and taken as origin/main; check-trailers reads this repository."""
    b(repo, "new", "sprint", "--title", "Planned", "--goal", "g")
    sp = item(repo, "Planned")["id"]
    b(repo, "new", "story", "--title", "Research", "--sprint", sp, "--goal", "r written",
      "--check", argstr(is_file("kb/public/r.md")), "--touch", "kb/public/**")
    b(repo, "new", "story", "--title", "Code", "--sprint", sp, "--goal", "c written",
      "--check", argstr(is_file("src/c.txt")), "--touch", "src/**")
    commit(repo, "plan")
    land(repo)
    monkeypatch.setattr(kbgit, "KB", str(repo))
    monkeypatch.setattr(kg_trailers, "KB", str(repo))
    kg_trailers._WANT.clear()
    return {"repo": repo, "sp": sp, "rs": item(repo, "Research")["id"], "cs": item(repo, "Code")["id"]}


def claim_committed(repo, iid):
    code, out = b(repo, "claim", iid, "--by", "agent-1")
    assert code == 0, out
    commit(repo, "claim", iid)  # a backlog-planning commit


def test_research_lands_before_sprint_start_touches_rule():
    """A research item's touches all lie inside a named kb root; planted: kb/_self/, tools, CI, a glob root, `..`."""
    assert backlog.research_touches(["kb/public/**", "kb/team-a/x/y.md"])
    for bad in ([], ["kb/_self/backlog.md"], ["kb/public/**", "_tools/x.py"], [".claude/**"], [".gitlab-ci.yml"],
                ["kb/*/x.md"], ["kb/public/../../_tools/x.py"], ["kb/public"], ["**"]):
        assert not backlog.research_touches(bad), bad


def test_research_lands_before_sprint_start_claim_commit_done(research):
    """A research item of a planned sprint is claimed from draft, its kb content commit passes check-trailers,
    check accepts it doing and done, and done proves it; the sprint stays planned."""
    repo, rs = research["repo"], research["rs"]
    claim_committed(repo, rs)
    assert item(repo, "Research")["status"] == "doing"
    code, out = b(repo, "check")
    assert code == 0, out
    (repo / "kb" / "public").mkdir(parents=True)
    (repo / "kb" / "public" / "r.md").write_text("r\n", encoding="utf-8")
    commit(repo, "write r", rs)
    kg_trailers._WANT.clear()
    assert kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)[2] == []
    code, out = b(repo, "done", rs)
    assert code == 0, out
    assert item(repo, "Research")["status"] == "done" and item(repo, "Planned")["status"] == "planned"
    code, out = b(repo, "check")
    assert code == 0, out


def test_research_lands_before_sprint_start_refuses_tools_commit(research):
    """Planted: the same research item's commit also changes _tools/: check-trailers refuses it, naming the path; a
    commit touching kb/_self/ is refused too."""
    repo, rs = research["repo"], research["rs"]
    claim_committed(repo, rs)
    (repo / "kb" / "public").mkdir(parents=True)
    (repo / "kb" / "public" / "r.md").write_text("r\n", encoding="utf-8")
    (repo / "_tools").mkdir()
    (repo / "_tools" / "x.py").write_text("x = 1\n", encoding="utf-8")
    commit(repo, "write r and a tool", rs)
    kg_trailers._WANT.clear()
    _, _, bad = kg_trailers.trailer_audit("HEAD^..HEAD", quiet=True)
    assert len(bad) == 1 and any("research item of a planned sprint" in ln and "_tools/x.py" in ln
                                 for ln in bad[0][1]), bad
    sh(repo, "git", "reset", "-q", "--hard", "HEAD^")
    (repo / "kb" / "_self").mkdir(parents=True, exist_ok=True)
    (repo / "kb" / "_self" / "doc.md").write_text("d\n", encoding="utf-8")
    commit(repo, "write a process doc", rs)
    kg_trailers._WANT.clear()
    _, _, bad = kg_trailers.trailer_audit("HEAD^..HEAD", quiet=True)
    assert len(bad) == 1 and any("kb/_self/doc.md" in ln for ln in bad[0][1]), bad


def test_research_lands_before_sprint_start_non_research_still_refused(research):
    """Planted: a code item of the same planned sprint: claim refuses it (draft), and check-trailers and check refuse
    it once its status is forced to doing; an unclaimed research item's commit is refused as not claimed."""
    repo, sp, rs, cs = research["repo"], research["sp"], research["rs"], research["cs"]
    code, out = b(repo, "claim", cs, "--by", "agent-1")
    assert code == 1 and "status draft" in out, out
    (repo / "kb" / "public").mkdir(parents=True)
    (repo / "kb" / "public" / "r.md").write_text("r\n", encoding="utf-8")
    commit(repo, "write r unclaimed", rs)
    kg_trailers._WANT.clear()
    _, _, bad = kg_trailers.trailer_audit("HEAD^..HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad
    edit(repo, cs, status="doing", claimed_by="agent-1")
    commit(repo, "force claim", cs)
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "write c", cs)
    kg_trailers._WANT.clear()
    _, _, bad = kg_trailers.trailer_audit("HEAD^..HEAD", quiet=True)
    assert len(bad) == 1 and any(f"not in a started sprint ({sp} is planned)" in ln for ln in bad[0][1]), bad
    code, out = b(repo, "check")
    assert code == 1 and f"{cs} “Code”: status doing while its sprint" in out, out


class TestBacklogCommitFlag:
    """--commit on claim, done, new, start and close commits exactly the item files the command wrote (not what was
    staged or changed before it), with the fixed subject `chore(backlog): VERB ID "title"` and KB-Work in the last
    trailer paragraph beside the session's --trailer lines, and check-trailers passes on the commit. Planted: a
    commit with KB-Work before the trailer paragraph and one with a file outside the written set fail the same
    check; a KB-* --trailer, a malformed one and --trailer without --commit are refused before anything is written."""

    CO = "Co-Authored-By: A <a@example.com>"

    @staticmethod
    def out(repo, *a):
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                              check=True).stdout

    def assert_commit(self, repo, verb, iid, title, ids, paths, monkeypatch, rev="HEAD"):
        """The check each --commit commit passes: subject, trailer paragraph, changed paths, check-trailers."""
        subject = self.out(repo, "log", "-1", "--format=%s", rev).strip()
        assert subject == f'chore(backlog): {verb} {iid} "{title}"', subject
        work = self.out(repo, "log", "-1", "--format=%(trailers:key=KB-Work,valueonly)", rev).strip()
        assert work == ", ".join(ids), f"KB-Work trailer {work!r}"
        last = self.out(repo, "log", "-1", "--format=%B", rev).strip().split("\n\n")[-1].splitlines()
        assert last == [f"KB-Work: {', '.join(ids)}", self.CO], last
        changed = self.out(repo, "show", "--name-only", "--format=", rev).split()
        assert sorted(changed) == sorted(paths), changed
        monkeypatch.setattr(kbgit, "KB", str(repo))
        monkeypatch.setattr(kg_trailers, "KB", str(repo))
        kg_trailers._WANT.clear()
        assert kg_trailers.trailer_audit(rev, quiet=True)[2] == []

    @staticmethod
    def rel(*ids):
        return [f"{backlog.REL_DIR}/{i}.json" for i in ids]

    def test_backlog_commit_flag_claim_commits_only_its_item_file(self, sprint, monkeypatch):
        repo, tk = sprint["repo"], sprint["tk"]
        commit(repo, "plan")
        (repo / "src" / "staged.txt").write_text("s\n", encoding="utf-8")
        sh(repo, "git", "add", "src/staged.txt")  # staged before the command: stays staged, out of the commit
        (repo / "src" / "a.txt").write_text("changed\n", encoding="utf-8")  # an unstaged change stays too
        code, out = b(repo, "claim", tk, "--by", "agent-1", "--commit", "--trailer", self.CO)
        assert code == 0 and "committed " in out, out
        self.assert_commit(repo, "claim", tk, "Task", [tk], self.rel(tk), monkeypatch)
        assert self.out(repo, "diff", "--cached", "--name-only").split() == ["src/staged.txt"]
        assert self.out(repo, "diff", "--name-only").split() == ["src/a.txt"]

    def test_backlog_commit_flag_done_commits_the_evidence(self, sprint, monkeypatch):
        repo, tk = sprint["repo"], sprint["tk"]
        commit(repo, "plan")
        assert b(repo, "claim", tk, "--by", "agent-1", "--commit", "--trailer", self.CO)[0] == 0
        (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
        commit(repo, "write b", tk)
        work = self.out(repo, "rev-parse", "HEAD").strip()
        code, out = b(repo, "done", tk, "--commit", "--trailer", self.CO)
        assert code == 0 and "commit this with" not in out, out
        self.assert_commit(repo, "done", tk, "Task", [tk], self.rel(tk), monkeypatch)
        assert item(repo, "Task")["evidence"]["commit"] == work
        assert not self.out(repo, "status", "--porcelain")

    def test_backlog_commit_flag_new_files_the_item_and_a_sprint_its_review(self, sprint, monkeypatch):
        repo = sprint["repo"]
        commit(repo, "plan")
        code, out = b(repo, "new", "bug", "--title", "Bug two", "--sprint", sprint["sp"], "--severity", "S3",
                      "--repro", argstr(is_file("src/d.txt")), "--goal", "d exists", "--touch", "src/**",
                      "--commit", "--trailer", self.CO)
        assert code == 0, out
        bg = item(repo, "Bug two")["id"]
        self.assert_commit(repo, "file", bg, "Bug two", [bg], self.rel(bg), monkeypatch)
        code, out = b(repo, "new", "sprint", "--title", "Next", "--goal", "later", "--commit", "--trailer", self.CO)
        assert code == 0, out
        sp, rv = item(repo, "Next")["id"], item(repo, "Review sprint: Next")["id"]
        rs = item(repo, "Research sprint goal: Next")["id"]
        self.assert_commit(repo, "file", sp, "Next", [sp, rv, rs], self.rel(sp, rv, rs), monkeypatch)

    def test_backlog_commit_flag_start_commits_the_sprint_and_its_items(self, repo, monkeypatch):
        b(repo, "new", "sprint", "--title", "Sprint", "--goal", "ship b")
        sp = item(repo, "Sprint")["id"]
        b(repo, "new", "bug", "--title", "Bug", "--sprint", sp, "--severity", "S3", "--repro",
          argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**")
        bg, rv = item(repo, "Bug")["id"], item(repo, "Review sprint: Sprint")["id"]
        rs = item(repo, "Research sprint goal: Sprint")["id"]
        assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
        commit(repo, "plan")
        code, out = b(repo, "start", sp, "--commit", "--trailer", self.CO)
        assert code == 0, out
        self.assert_commit(repo, "start", sp, "Sprint", [sp], self.rel(bg, rv, rs, sp), monkeypatch)

    def test_backlog_commit_flag_close_commits_the_deletions_with_the_summary(self, sprint, monkeypatch):
        repo, tk, st, bg, rv, ep, sp, rs = (sprint[k] for k in ("repo", "tk", "st", "bg", "rv", "ep", "sp", "rs"))
        (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
        (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
        commit(repo, "b and c", f"{tk}, {bg}")
        for iid in (tk, st, bg):
            assert b(repo, "done", iid)[0] == 0
        edit(repo, rv, checks=[{"run": PASS}])
        commit(repo, "state")
        assert b(repo, "done", rv)[0] == 0
        assert b(repo, "done", ep)[0] == 0
        commit(repo, "done all")
        code, out = b(repo, "close", sp, "--commit", "--trailer", self.CO)
        assert code == 0, out
        self.assert_commit(repo, "close", sp, "Sprint", [sp], self.rel(ep, st, tk, bg, rv, rs, sp), monkeypatch)
        body = self.out(repo, "log", "-1", "--format=%b").split("\n\n")[0]
        assert body.startswith(f"delivered by {sp} “Sprint”:") and f"- {bg} “Bug” (bug): done at " in body, body

    def test_backlog_commit_flag_check_fails_on_planted_commits(self, sprint, monkeypatch):
        """The check above is not vacuous: KB-Work outside the last paragraph, or a file the command did not write,
        fails it."""
        repo, tk = sprint["repo"], sprint["tk"]
        commit(repo, "plan")
        assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
        sh(repo, "git", "add", "-A")
        subject = f'chore(backlog): claim {tk} "Task"'
        sh(repo, "git", "commit", "-qm", f"{subject}\n\nKB-Work: {tk}\n\n{self.CO}")  # planted: KB-Work in the body
        with pytest.raises(AssertionError, match="KB-Work trailer"):
            self.assert_commit(repo, "claim", tk, "Task", [tk], self.rel(tk), monkeypatch)
        edit(repo, tk, claimed_by="agent-2")
        (repo / "src" / "x.txt").write_text("x\n", encoding="utf-8")  # planted: a file outside the written set
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-qm", f"{subject}\n\nKB-Work: {tk}\n{self.CO}")
        with pytest.raises(AssertionError, match="src/x.txt"):
            self.assert_commit(repo, "claim", tk, "Task", [tk], self.rel(tk), monkeypatch)

    def test_backlog_commit_flag_refuses_bad_trailers_before_writing(self, sprint):
        repo, tk = sprint["repo"], sprint["tk"]
        commit(repo, "plan")
        head = self.out(repo, "rev-parse", "HEAD")
        for extra in (["--commit", "--trailer", f"KB-Work: {tk}"], ["--commit", "--trailer", "no colon"],
                      ["--commit", "--trailer", "A: b\nC: d"], ["--trailer", self.CO]):
            code, out = b(repo, "claim", tk, "--by", "agent-1", *extra)
            assert code == 1 and "--trailer" in out, (extra, out)
        assert item(repo, "Task")["status"] == "todo" and self.out(repo, "rev-parse", "HEAD") == head
        assert not self.out(repo, "status", "--porcelain")

    def test_backlog_commit_flag_nothing_written_commits_nothing(self, sprint):
        """A second claim by the same session rewrites the file unchanged: no empty commit."""
        repo, tk = sprint["repo"], sprint["tk"]
        commit(repo, "plan")
        assert b(repo, "claim", tk, "--by", "agent-1", "--commit")[0] == 0
        head = self.out(repo, "rev-parse", "HEAD")
        code, out = b(repo, "claim", tk, "--by", "agent-1", "--commit")
        assert code == 0 and "nothing committed" in out, out
        assert self.out(repo, "rev-parse", "HEAD") == head


# ------------------------------------------------------------------ set and gate add

def item_text(repo, iid):
    return (Path(repo) / backlog.REL_DIR / f"{iid}.json").read_text(encoding="utf-8")


def refused_unchanged(repo, iid, *args, rule):
    """The command exits 2 with the rule in its message and leaves the item file as it was."""
    before = item_text(repo, iid)
    code, out = b(repo, *args)
    assert code == 2 and rule in out, (code, out)
    assert item_text(repo, iid) == before


def test_backlog_set_changes_each_field_and_check_passes(sprint):
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    code, out = b(repo, "set", tk, "--notes", "why", "--link", "pipeline 1", "--touch", "src/a.txt", "--touch", "kb/x/**",
                  "--check", argstr(is_file("src/b.txt")), "--depends", bg, "--relates", sprint["st"], "--priority", "P1", "--rank", "3")
    assert code == 0 and "set " in out, out
    it = item_json(repo, tk)
    assert it["notes"] == "why" and it["links"] == ["pipeline 1"] and it["touches"] == ["src/a.txt", "kb/x/**"]
    assert it["checks"] == [{"run": is_file("src/b.txt")}] and it["depends_on"] == [bg] and it["relates_to"] == [sprint["st"]]
    assert it["priority"] == "P1" and it["rank"] == 3
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_backlog_set_moves_a_draft_story_to_another_sprint(repo):
    b(repo, "new", "sprint", "--title", "One", "--goal", "g")
    b(repo, "new", "sprint", "--title", "Two", "--goal", "g")
    one, two = item(repo, "One")["id"], item(repo, "Two")["id"]
    b(repo, "new", "story", "--title", "S", "--sprint", one, "--goal", "g", "--check", argstr(is_file("src/b.txt")))
    st = item(repo, "S")["id"]
    assert b(repo, "set", st, "--sprint", two)[0] == 0
    assert item_json(repo, st)["sprint"] == two
    assert b(repo, "set", st, "--clear", "sprint")[0] == 0
    assert "sprint" not in item_json(repo, st)
    assert b(repo, "check")[0] == 0


def test_backlog_set_second_run_changes_nothing(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    args = ("set", tk, "--notes", "why", "--link", "a", "--touch", "src/**", "--priority", "P3")
    assert b(repo, *args)[0] == 0
    after = item_text(repo, tk)
    code, out = b(repo, *args)
    assert code == 0 and "unchanged" in out and item_text(repo, tk) == after
    add = ("set", tk, "--add", "--link", "b", "--link", "a", "--notes", "more", "--touch", "kb/y/**")
    assert b(repo, *add)[0] == 0
    it = item_json(repo, tk)
    assert it["links"] == ["a", "b"] and it["notes"] == "why more" and it["touches"] == ["src/**", "kb/y/**"]
    after = item_text(repo, tk)
    code, out = b(repo, *add)
    assert code == 0 and "unchanged" in out and item_text(repo, tk) == after


def test_backlog_set_add_keeps_existing_checks(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "set", tk, "--add", "--check", argstr(PASS))[0] == 0
    assert item_json(repo, tk)["checks"] == [{"run": is_file("src/b.txt")}, {"run": PASS}]
    assert b(repo, "set", tk, "--check", argstr(PASS))[0] == 0  # without --add the list is replaced
    assert item_json(repo, tk)["checks"] == [{"run": PASS}]


@pytest.mark.parametrize("flag, value, rule", [
    ("--status", "done", "set refuses status"),
    ("--claimed-by", "me", "set refuses claimed_by"),
    ("--evidence", "x", "set refuses evidence"),
    ("--id", "TK-aaaaaaaa", "set refuses id"),
    ("--kind", "bug", "set refuses kind"),
    ("--parent", "ST-aaaaaaaa", "set refuses parent"),
    ("--title", "Other", "set refuses title"),
    ("--gates", "[]", "set refuses gates"),
])
def test_backlog_set_refuses_status_claim_evidence_and_identity(sprint, flag, value, rule):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], flag, value, rule=rule)


@pytest.mark.parametrize("field, rule", [
    ("status", "changes only through claim, release, start, close, drop and done"),
    ("claimed_by", "changes only through claim and release"),
    ("evidence", "is written only by done"),
    ("title", "identity"),
    ("goal", "is not a field set changes"),
    ("repro", "is not a field set changes"),
])
def test_backlog_set_clear_refuses_the_same_fields(sprint, field, rule):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], "--clear", field, rule=rule)


def test_backlog_set_refuses_nothing_to_change_and_a_value_with_its_clear(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    refused_unchanged(repo, tk, "set", tk, rule="nothing to change")
    refused_unchanged(repo, tk, "set", tk, "--notes", "x", "--clear", "notes", rule="given a value and --clear")


@pytest.mark.parametrize("args, rule", [
    (["--priority", "P9"], "priority must be one of"),
    (["--notes", " "], "notes empty or longer than TEXT_MAX"),
    (["--notes", "x" * 2001], "notes empty or longer than TEXT_MAX"),
    (["--link", ""], "links must be a list of texts"),
    (["--depends", "TK-zzzzzzzz"], "depends_on names TK-zzzzzzzz, which does not exist"),
    (["--relates", "TK-zzzzzzzz"], "relates_to names TK-zzzzzzzz, which does not exist"),
    (["--sprint", "SP-zzzzzzzz"], "only stories and bugs name a sprint"),
    (["--check", ""], "checks must be a list of"),
    (["--clear", "touches"], "touches missing"),
    (["--clear", "priority"], "priority must be one of"),
    (["--clear", "checks"], "checks missing"),
    (["--touch", "src/**", "--clear", "touches"], "given a value and --clear"),
])
def test_backlog_set_refuses_what_check_would_flag(sprint, args, rule):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], *args, rule=rule)


def test_backlog_set_refuses_a_check_that_is_not_a_command_line(sprint):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], "--check", "python3 -c 'unclosed",
                      rule="not a command line")


def test_backlog_set_refuses_itself_and_a_dependency_cycle(sprint):
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    refused_unchanged(repo, tk, "set", tk, "--depends", tk, rule="names the item itself")
    assert b(repo, "set", bg, "--depends", tk)[0] == 0
    refused_unchanged(repo, tk, "set", tk, "--depends", bg, rule="cycle")


def test_backlog_set_refuses_a_missing_sprint_of_a_story_and_a_draft_item_in_an_active_sprint(sprint):
    repo, st = sprint["repo"], sprint["st"]
    refused_unchanged(repo, st, "set", st, "--sprint", "SP-zzzzzzzz", rule="sprint SP-zzzzzzzz does not exist")
    b(repo, "new", "story", "--title", "Loose", "--goal", "g", "--check", argstr(PASS))
    loose = item(repo, "Loose")["id"]
    refused_unchanged(repo, loose, "set", loose, "--sprint", sprint["sp"], rule="would never be ready")


def test_backlog_set_refuses_moving_the_review_story_out_of_its_sprint(sprint):
    repo, rv = sprint["repo"], sprint["rv"]
    b(repo, "new", "sprint", "--title", "Other", "--goal", "g")
    refused_unchanged(repo, rv, "set", rv, "--sprint", item(repo, "Other")["id"], rule="exactly one review story")


def test_backlog_set_refuses_a_sprint_except_notes_and_links(sprint):
    repo, sp = sprint["repo"], sprint["sp"]
    refused_unchanged(repo, sp, "set", sp, "--priority", "P1", rule="a sprint takes notes and links only")
    assert b(repo, "set", sp, "--notes", "n", "--link", "l")[0] == 0


def test_backlog_set_refuses_checks_and_touches_of_a_done_item(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, status="done", evidence={"commit": "abc", "checks": []})
    refused_unchanged(repo, tk, "set", tk, "--check", argstr(PASS), rule="its evidence proves")
    refused_unchanged(repo, tk, "set", tk, "--clear", "touches", rule="its evidence proves")
    assert b(repo, "set", tk, "--notes", "after")[0] == 0


def test_backlog_set_refuses_a_name_of_this_host_in_notes(sprint, monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "ZyxwvuHost")
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], "--notes", "built on zyxwvuhost",
                      rule="holds a piece of this host's computer name")


def test_backlog_set_unknown_id_exits_2(sprint):
    code, out = b(sprint["repo"], "set", "TK-zzzzzzzz", "--notes", "x")
    assert code == 2 and "no item TK-zzzzzzzz" in out


def test_backlog_set_check_flags_malformed_links(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, links="pipeline 1")  # planted: a string, not a list
    code, out = b(repo, "check")
    assert code == 1 and "links must be a list of texts" in out, out


GATE = ("--question", "Which way?", "--option", "left", "--option", "right", "--recommendation", "left")


def test_backlog_set_gate_add_blocks_until_answered(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    code, out = b(repo, "gate", "add", tk, *GATE)
    assert code == 0 and "g1 (blocking) added" in out, out
    assert item_json(repo, tk)["gates"] == [{"id": "g1", "kind": "blocking", "question": "Which way?",
                                              "options": ["left", "right"], "recommendation": "left",
                                              "class": "design"}]
    assert b(repo, "check")[0] == 0
    assert "waits on" in b(repo, "show", tk)[1]
    assert b(repo, "answer", tk, "g1", "--answer", "left", "--by", "operator")[0] == 0
    assert b(repo, "gate", "add", tk, "--question", "Second?", "--option", "a", "--option", "b",
             "--recommendation", "b", "--kind", "provisional")[0] == 0
    assert [g["id"] for g in item_json(repo, tk)["gates"]] == ["g1", "g2"]
    assert b(repo, "answer", tk, "g2", "--provisional")[0] == 0


def test_backlog_set_gate_add_second_run_changes_nothing(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "gate", "add", tk, *GATE, "--id", "way")[0] == 0
    assert b(repo, "answer", tk, "way", "--answer", "right", "--by", "operator")[0] == 0
    after = item_text(repo, tk)
    for extra in ((), ("--id", "way")):  # an answered gate is not reopened or duplicated
        code, out = b(repo, "gate", "add", tk, *GATE, *extra)
        assert code == 0 and "unchanged" in out and item_text(repo, tk) == after, out


@pytest.mark.parametrize("args, rule", [
    (["--question", "Which way?", "--option", "up", "--option", "down", "--recommendation", "up"],
     "refuses a different gate with the question or id of gate way"),
    (["--question", "Other?", "--option", "left", "--option", "right", "--recommendation", "left", "--id", "way"],
     "refuses a different gate with the question or id of gate way"),
    (list(GATE) + ["--id", "other"], "refuses a different gate with the question or id of gate way"),
    (["--question", "Q?", "--option", "a", "--recommendation", "a"], "--option twice or more"),
    (["--question", "Q?", "--option", "a", "--option", "a", "--recommendation", "a"], "each different"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "c"], "must be one of the --option"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "a", "--id", "start"], "not 'start'"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "a", "--id", "Bad Id"],
     "lowercase letters, digits and hyphens"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "a", "--kind", "maybe"],
     "a gate needs id, kind"),
    (["--question", " ", "--option", "a", "--option", "b", "--recommendation", "a"], "a gate needs id, kind"),
])
def test_backlog_set_gate_add_refuses(sprint, args, rule):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "gate", "add", tk, *GATE, "--id", "way")[0] == 0
    refused_unchanged(repo, tk, "gate", "add", tk, *args, rule=rule)


@pytest.mark.parametrize("options", [
    ("fold into maintaining.md", "drop a row"),  # no measured size
    ("fold into maintaining.md: 3990 bytes", "drop a row"),  # one option without
])
def test_gate_size_cap_measured_refuses_an_option_without_a_size(sprint, options):
    repo, tk = sprint["repo"], sprint["tk"]
    args = ["--question", "How does AGENTS.md stay under its cap?", "--recommendation", options[0]]
    for o in options:
        args += ["--option", o]
    code, out = b(repo, "gate", "add", tk, *args)
    assert code == 2 and "each --option states the file's measured size" in out, out
    assert "gates" not in item_json(repo, tk)


def test_gate_size_cap_measured_accepts_sizes_and_leaves_other_gates_alone(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    args = ["--question", "How does AGENTS.md stay under its cap?", "--option", "fold: 4001 bytes",
            "--option", "drop a row: 4,090 bytes", "--recommendation", "fold: 4001 bytes"]
    assert b(repo, "gate", "add", tk, *args)[0] == 0
    assert b(repo, "gate", "add", tk, "--question", "Name of the flag in AGENTS.md?", "--option", "a",
             "--option", "b", "--recommendation", "a")[0] == 0  # names the file, not a cap


def test_backlog_set_gate_add_refuses_a_done_item_and_an_unknown_one(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, status="done", evidence={"commit": "abc", "checks": []})
    refused_unchanged(repo, tk, "gate", "add", tk, *GATE, rule="it is done")
    code, out = b(repo, "gate", "add", "TK-zzzzzzzz", *GATE)
    assert code == 2 and "no item TK-zzzzzzzz" in out


ROOT_MD = "---\nroot: public\nid_prefix: S\nvisibility: public\ndescription: test root\n---\n"
SOURCES_HEADER = ("id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,"
                  "superseded_by\n")
DECIDE_TOOLS = ("kbdecide.py", "check.py", "kbcommon.py", "kbid.py", "kbfacts.py")


@pytest.fixture
def decide(sprint):
    """The started sprint's repository with a copy of the decision tools, a minimal public root and kb/_self's decision
    files, so `answer --record` writes into the copy and never into this repository."""
    repo = sprint["repo"]
    (repo / "_tools").mkdir()
    for name in DECIDE_TOOLS:
        shutil.copy(os.path.join(TOOLS, name), repo / "_tools" / name)
    pub = repo / "kb" / "public"
    pub.mkdir(parents=True)
    for rel, text in (("_root.md", ROOT_MD), ("_sources.csv", SOURCES_HEADER), ("_artifacts.csv", "path,source_id,sha256\n"),
                      ("_answers.md", "# Answers\n"), ("_gaps.md", "# Gaps\n"), ("_conflicts.md", "# Conflicts\n")):
        (pub / rel).write_text(text, encoding="utf-8", newline="\n")
    kb_self = repo / "kb" / "_self"
    kb_self.mkdir(exist_ok=True)
    (kb_self / "_decisions.csv").write_text(
        "id,text,by,by_ref,source,date,context,status,invalidated_reason,invalidated_date,supersedes,review_by,links\n",
        encoding="utf-8", newline="\n")
    (kb_self / "decision-makers.csv").write_text("id,role,name,source\noperator,operator,,the operator answers a gate\n",
                                                 encoding="utf-8", newline="\n")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8", newline="\n")
    edit(repo, sprint["bg"], gates=[{"id": "way", "kind": "blocking", "question": "Which way?",
                                      "options": ["left", "right"], "recommendation": "left"}])
    commit(repo, "decision tools")
    return sprint


def decisions(repo):
    import csv
    with open(Path(repo) / "kb" / "_self" / "_decisions.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def tool_run(repo, tool, *args):
    p = subprocess.run([sys.executable, str(Path(repo) / "_tools" / tool), *args], cwd=repo, capture_output=True,
                       text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def test_backlog_answer_record_writes_an_active_decision_of_the_item(decide):
    repo, bg = decide["repo"], decide["bg"]
    code, out = b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")
    assert code == 0, out
    assert item_json(repo, bg)["gates"][0]["answer"] == "left"
    (row,) = decisions(repo)
    assert (row["status"], row["text"], row["context"]) == ("active", "left", f"item:{bg}")
    assert (row["by"], row["by_ref"]) == ("operator", "operator")
    assert f"{bg} gate way" in row["source"]
    code, out = tool_run(repo, "kbdecide.py", "list", "--root", "_self", "--context", f"item:{bg}")
    assert code == 0 and row["id"] in out
    code, out = tool_run(repo, "check.py")
    assert code == 0, out


def test_backlog_answer_record_second_gate_same_text(decide):
    """Two gates of one item answered with the same text are two decisions, and the second answer is saved; the same
    gate answered alike again is still the same decision (refused)."""
    repo, bg = decide["repo"], decide["bg"]
    code, out = b(repo, "gate", "add", bg, "--question", "Which side?", "--option", "left", "--option", "right",
                  "--recommendation", "left", "--id", "side")
    assert code == 0, out
    commit(repo, "second gate")
    assert b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")[0] == 0
    code, out = b(repo, "answer", bg, "side", "--answer", "left", "--by", "operator", "--record")
    assert code == 0, out
    assert [g.get("answer") for g in item_json(repo, bg)["gates"]] == ["left", "left"]
    rows = decisions(repo)
    assert len(rows) == 2 and len({r["id"] for r in rows}) == 2, rows  # planted failure: one id means the gate is not in it
    assert [r["text"] for r in rows] == ["left", "left"] and {r["context"] for r in rows} == {f"item:{bg}"}
    assert [f"gate {g}" in r["source"] for g, r in zip(("way", "side"), rows)] == [True, True]
    code, out = tool_run(repo, "check.py")
    assert code == 0, out


def test_backlog_answer_record_without_record_writes_no_decision(decide):
    repo, bg = decide["repo"], decide["bg"]
    assert b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator")[0] == 0
    assert decisions(repo) == []


@pytest.mark.parametrize("args", [
    ("--provisional",),
    ("--confirm",),
    ("--answer", "left", "--by", "agent"),
    ("--answer", "left"),
    ("--by", "operator"),
])
def test_backlog_answer_record_refuses_what_is_not_the_operators_answer(decide, args):
    repo, bg = decide["repo"], decide["bg"]
    before = item_text(repo, bg)
    code, out = b(repo, "answer", bg, "way", *args, "--record")
    assert code == 2 and "--record" in out, out
    assert decisions(repo) == [] and item_text(repo, bg) == before


def test_backlog_answer_record_leaves_the_gate_open_when_kbdecide_refuses(decide):
    """A decision kbdecide refuses (here a maker the register lacks) leaves the gate unanswered and no row behind."""
    repo, bg = decide["repo"], decide["bg"]
    (Path(repo) / "kb" / "_self" / "decision-makers.csv").write_text("id,role,name,source\n", encoding="utf-8", newline="\n")
    before = item_text(repo, bg)
    code, out = b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")
    assert code == 1 and "no decision maker 'operator'" in out, out
    assert decisions(repo) == [] and item_text(repo, bg) == before


def test_backlog_answer_record_decision_stays_active_after_close_and_sweep(decide):
    repo, tk, st, bg, rv, ep, sp = (decide[k] for k in ("repo", "tk", "st", "bg", "rv", "ep", "sp"))
    assert b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")[0] == 0  # commits its own files
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{tk}, {bg}")
    for iid in (tk, st, bg):
        code, out = b(repo, "done", iid)
        assert code == 0, out
    edit(repo, rv, checks=[{"run": PASS}])
    commit(repo, "state")
    assert b(repo, "done", rv)[0] == 0
    assert b(repo, "done", ep)[0] == 0
    commit(repo, "done")
    code, out = b(repo, "close", sp)
    assert code == 0, out
    assert not (Path(repo) / backlog.REL_DIR / f"{bg}.json").exists()
    assert [r["status"] for r in decisions(repo)] == ["active"]
    code, out = tool_run(repo, "kbdecide.py", "sweep", "--root", "_self")
    assert code == 0, out
    assert [r["status"] for r in decisions(repo)] == ["active"]


# ------------------------------------------------------------------ move and reopen

@pytest.fixture
def planned(sprint):
    """The started sprint's story with its task, plus a second sprint still planned."""
    repo = sprint["repo"]
    assert b(repo, "new", "sprint", "--title", "Later", "--goal", "g")[0] == 0
    return {**sprint, "later": item(repo, "Later")["id"]}


def statuses(repo, *ids):
    return [item_json(repo, i)["status"] for i in ids]


def test_backlog_move_to_a_planned_sprint_writes_draft_and_the_tasks_follow(planned):
    repo, st, tk, later = planned["repo"], planned["st"], planned["tk"], planned["later"]
    assert statuses(repo, st, tk) == ["todo", "todo"]
    code, out = b(repo, "move", st, "--sprint", later)
    assert code == 0 and "status draft" in out and "1 task" in out, out
    assert item_json(repo, st)["sprint"] == later and statuses(repo, st, tk) == ["draft", "draft"]
    assert b(repo, "check")[0] == 0


def test_backlog_move_to_an_active_sprint_writes_todo_and_the_tasks_follow(planned):
    repo, st, tk, later, sp = planned["repo"], planned["st"], planned["tk"], planned["later"], planned["sp"]
    assert b(repo, "move", st, "--sprint", later)[0] == 0
    code, out = b(repo, "move", st, "--sprint", sp)
    assert code == 0 and "status todo" in out, out
    assert item_json(repo, st)["sprint"] == sp and statuses(repo, st, tk) == ["todo", "todo"]
    assert b(repo, "check")[0] == 0


def test_backlog_move_none_removes_the_sprint_and_writes_draft(planned):
    repo, st, tk = planned["repo"], planned["st"], planned["tk"]
    code, out = b(repo, "move", st, "--sprint", "none")
    assert code == 0, out
    assert "sprint" not in item_json(repo, st) and statuses(repo, st, tk) == ["draft", "draft"]
    assert b(repo, "check")[0] == 0


def test_backlog_move_second_run_changes_nothing(planned):
    repo, st, later = planned["repo"], planned["st"], planned["later"]
    for target in (later, "none"):
        assert b(repo, "move", st, "--sprint", target)[0] == 0
        files = {i: item_text(repo, i) for i in (st, planned["tk"])}
        code, out = b(repo, "move", st, "--sprint", target)
        assert code == 0 and "unchanged" in out, out
        assert {i: item_text(repo, i) for i in files} == files


def test_backlog_move_refuses_what_a_sprint_cannot_hold(planned):
    repo, st, tk, rv, sp, later = (planned[k] for k in ("repo", "st", "tk", "rv", "sp", "later"))
    refused_unchanged(repo, tk, "move", tk, "--sprint", later, rule="only a story or a bug names a sprint")
    refused_unchanged(repo, later, "move", later, "--sprint", sp, rule="only a story or a bug names a sprint")
    refused_unchanged(repo, rv, "move", rv, "--sprint", later, rule="exactly one review story")
    refused_unchanged(repo, st, "move", st, "--sprint", "SP-zzzzzzzz", rule="does not exist")
    refused_unchanged(repo, st, "move", st, "--sprint", planned["ep"], rule="is not a sprint")


def test_backlog_move_refuses_a_claimed_item_and_one_with_a_claimed_task(planned):
    repo, st, tk, later = planned["repo"], planned["st"], planned["tk"], planned["later"]
    assert b(repo, "claim", tk, "--by", "me")[0] == 0
    refused_unchanged(repo, st, "move", st, "--sprint", later, rule="is doing (claimed)")
    assert b(repo, "release", tk)[0] == 0
    edit(repo, st, status="doing", claimed_by="me")
    refused_unchanged(repo, st, "move", st, "--sprint", later, rule="is doing (claimed)")


def test_backlog_move_refuses_a_done_and_a_dropped_item(planned):
    repo, bg, later = planned["repo"], planned["bg"], planned["later"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []})
    refused_unchanged(repo, bg, "move", bg, "--sprint", later, rule="reopen it first")
    edit(repo, bg, status="dropped")
    refused_unchanged(repo, bg, "move", bg, "--sprint", later, rule="it is dropped")


def test_backlog_move_refuses_an_item_without_touches_into_an_active_sprint(planned):
    repo, sp = planned["repo"], planned["sp"]
    assert b(repo, "new", "story", "--title", "Bare", "--goal", "g", "--check", argstr(PASS))[0] == 0
    bare = item(repo, "Bare")["id"]
    refused_unchanged(repo, bare, "move", bare, "--sprint", sp, rule="has no touches")
    assert b(repo, "move", bare, "--sprint", planned["later"])[0] == 0  # a planned sprint takes it as a draft


def test_backlog_move_refuses_what_check_would_flag_and_writes_no_task(planned):
    repo, st, tk, later = planned["repo"], planned["st"], planned["tk"], planned["later"]
    assert b(repo, "new", "task", "--title", "Second", "--parent", st, "--goal", "g", "--touch", "src/**",
             "--check", argstr(PASS))[0] == 0
    second = item(repo, "Second")["id"]
    edit(repo, tk, status="done", evidence={"commit": "abc", "checks": []})  # planted: done cannot sit in a planned sprint
    before = item_text(repo, second)
    refused_unchanged(repo, st, "move", st, "--sprint", later, rule="while its sprint")
    assert item_text(repo, second) == before and statuses(repo, second) == ["todo"]


def test_backlog_move_requires_a_sprint_argument(planned):
    code, out = b(planned["repo"], "move", planned["st"])
    assert code == 2 and "--sprint" in out, out


def test_backlog_move_unknown_id_exits_2(planned):
    code, out = b(planned["repo"], "move", "ST-zzzzzzzz", "--sprint", "none")
    assert code == 2 and "no item" in out, out


def test_backlog_move_reopen_clears_evidence_and_claim_and_sets_todo(planned):
    repo, bg = planned["repo"], planned["bg"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []}, claimed_by="me")
    before = item_text(repo, bg)
    code, out = b(repo, "reopen", bg, "--why", "the fix regressed")
    assert code == 0 and "the fix regressed" in out, out
    it = item_json(repo, bg)
    assert it["status"] == "todo" and "evidence" not in it and "claimed_by" not in it
    assert "regressed" not in item_text(repo, bg) and item_text(repo, bg) != before
    assert b(repo, "check")[0] == 0


def test_backlog_move_reopen_in_a_planned_sprint_writes_draft(planned):
    repo, st, later = planned["repo"], planned["st"], planned["later"]
    assert b(repo, "move", st, "--sprint", later)[0] == 0
    edit(repo, st, status="done", evidence={"commit": "abc", "checks": []})
    assert b(repo, "reopen", st, "--why", "again")[0] == 0
    assert item_json(repo, st)["status"] == "draft"


def test_backlog_move_reopen_second_run_is_refused_and_changes_nothing(planned):
    repo, bg = planned["repo"], planned["bg"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []})
    assert b(repo, "reopen", bg, "--why", "x")[0] == 0
    refused_unchanged(repo, bg, "reopen", bg, "--why", "x", rule="reopen takes only a done item")


@pytest.mark.parametrize("status", ["draft", "todo", "doing", "dropped"])
def test_backlog_move_reopen_refuses_every_status_but_done(planned, status):
    repo, bg = planned["repo"], planned["bg"]
    edit(repo, bg, status=status, **({"claimed_by": "me"} if status == "doing" else {}))
    refused_unchanged(repo, bg, "reopen", bg, "--why", "x", rule=f"it is {status}")


def test_backlog_move_reopen_refuses_a_missing_or_blank_reason_and_a_sprint(planned):
    repo, bg, sp = planned["repo"], planned["bg"], planned["sp"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []})
    code, out = b(repo, "reopen", bg)
    assert code == 2 and "--why" in out, out
    refused_unchanged(repo, bg, "reopen", bg, "--why", "  ", rule="must not be empty")
    refused_unchanged(repo, sp, "reopen", sp, "--why", "x", rule="a sprint has no done status")
    code, out = b(repo, "reopen", "ST-zzzzzzzz", "--why", "x")
    assert code == 2 and "no item" in out, out


def referrer_repo(sprint):
    repo = Path(sprint["repo"])
    for rel, text in {"lib/mod.py": "def helper_fn():\n    pass\n", "lib/user.py": "import mod\nmod.helper_fn()\n",
                      "docs/n.md": "see lib/mod.py and `helper_fn`\nhelper_fn_other is another\n",
                      "src/t.txt": "lib/mod.py\n", "docs/none.md": "nothing\n"}.items():
        (repo / rel).parent.mkdir(exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    commit(repo, "files")
    return repo


def test_backlog_referrers_lists_each_file_that_names_a_moved_file_or_symbol(sprint):
    repo = referrer_repo(sprint)
    code, out = b(repo, "referrers", "lib/mod.py", "helper_fn", "no_such_symbol")
    assert code == 0, out
    assert out.splitlines() == ["lib/mod.py  docs/n.md:1  1 line", "lib/mod.py  lib/user.py:1  1 line",
                                "lib/mod.py  src/t.txt:1  1 line",
                                "helper_fn  docs/n.md:1  1 line", "helper_fn  lib/mod.py:1  1 line",
                                "helper_fn  lib/user.py:2  1 line",
                                "no_such_symbol  no tracked file names it"], out


def test_backlog_referrers_item_marks_the_files_outside_its_touches(sprint):
    repo = referrer_repo(sprint)
    code, out = b(repo, "referrers", "lib/mod.py", "--item", sprint["tk"])  # the task's touches are src/**
    assert code == 1, out
    assert "lib/mod.py  src/t.txt:1  1 line\n" in out + "\n" and "src/t.txt:1  1 line  outside" not in out, out
    assert "docs/n.md:1  1 line  outside touches" in out and "lib/user.py:1  1 line  outside touches" in out, out
    edit(repo, sprint["tk"], touches=["src/**", "docs/n.md", "lib/user.py"])
    code, out = b(repo, "referrers", "lib/mod.py", "--item", sprint["tk"])
    assert code == 0 and "outside" not in out, out
    assert b(repo, "referrers", "x", "--item", "TK-zzzzzzzz")[0] == 2


def test_backlog_referrers_ignores_item_files_and_matches_doc_names(sprint):
    """BG-ncpteupy planted: an item file naming the moved file and prose that only says the module's word are no
    referrers; an import line and <stem>.py are. A moved doc is found by its file name, word-bounded, too."""
    repo = referrer_repo(sprint)
    edit(repo, sprint["tk"], touches=["src/**", "lib/mod.py"], notes="the mod word, and mod.py")
    for rel, text in {"docs/word.md": "a mod of the game\n", "docs/script.md": "run mod.py now\n",
                      "lib/other.py": "from lib import mod\n", "docs/guide.md": "# guide\n",
                      "docs/cites.md": "see guide.md and not myguide.md\n"}.items():
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    commit(repo, "more files")
    code, out = b(repo, "referrers", "lib/mod.py", "docs/guide.md")
    assert code == 0, out
    assert backlog.REL_DIR not in out and "docs/word.md" not in out, out
    for want in ("lib/mod.py  docs/script.md:1  1 line", "lib/mod.py  lib/other.py:1  1 line",
                 "lib/mod.py  lib/user.py:1  1 line", "docs/guide.md  docs/cites.md:1  1 line"):
        assert want in out, (want, out)


def test_backlog_referrers_planted_failure_of_the_scope_rule_is_caught(sprint, capsys, monkeypatch):
    """A scope rule that holds every path (planted) hides the stray files, and the check sees it."""
    repo = referrer_repo(sprint)
    monkeypatch.setattr(backlog, "in_scope", lambda path, globs: True)  # planted
    code = backlog.main(["--root", str(repo), "referrers", "lib/mod.py", "--item", sprint["tk"]])
    out = capsys.readouterr().out
    assert code == 0 and "outside touches" not in out  # the stray files go unmarked: the test above would fail


def test_claim_accepts_own_claimed_dependency(sprint):
    """`claim --by X` accepts an item whose only undone dependency is doing and claimed by X, so a depends_on that
    orders two items sharing a file needs no hand edit; planted: another session's claim, an unclaimed dependency
    and a dependency of the same session that is not doing still refuse."""
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    edit(repo, tk, depends_on=[bg])
    code, out = b(repo, "claim", tk, "--by", "s1")
    assert code == 1 and "depends on" in out, out  # planted: bg is not claimed
    assert b(repo, "claim", bg, "--by", "s2")[0] == 0
    code, out = b(repo, "claim", tk, "--by", "s1")
    assert code == 1 and "depends on" in out, out  # planted: claimed by another session
    b(repo, "release", bg)
    assert b(repo, "claim", bg, "--by", "s1")[0] == 0
    code, out = b(repo, "claim", tk, "--by", "s1")
    assert code == 0, out
    assert backlog.Backlog(repo).items[tk]["claimed_by"] == "s1"
