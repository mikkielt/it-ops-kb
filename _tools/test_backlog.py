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
import json, os, re, shlex, shutil, subprocess, sys
from pathlib import Path

import pytest

import backlog
import kbgit
import kg_hooks
import kg_trailers
import ql_deliver
from test_ql_deliver import job_of, job_states, state_id  # the job-state table's rows
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


def test_backlog_similar_ranks_open_items_and_new_warns_of_a_near_duplicate(sprint):
    """A planted duplicate: similar ranks it first as near, new names it in a warning and still writes the item with
    exit 0; a unique title gets no warning, and a dropped item is no longer compared."""
    repo, ep = sprint["repo"], sprint["ep"]
    b(repo, "new", "story", "--title", "Rotate the BitLocker recovery keys after use", "--parent", ep,
      "--goal", "every used recovery key is rotated")
    dup = item(repo, "Rotate the BitLocker recovery keys after use")["id"]
    code, out = b(repo, "similar", "Rotate BitLocker recovery keys")
    assert code == 0, out
    first = out.splitlines()[0]
    assert dup in first and "near" in first and first.startswith("1.00"), out
    assert b(repo, "similar", "Rotate BitLocker recovery keys") == (code, out)  # deterministic
    code, out = b(repo, "new", "story", "--title", "Rotate used BitLocker recovery keys", "--parent", ep,
                  "--goal", "recovery keys rotated")
    assert code == 0, out
    assert f"warning: near-duplicate of open {dup} “Rotate the BitLocker recovery keys after use”" in out, out
    assert item(repo, "Rotate used BitLocker recovery keys")["status"] == "draft"
    code, out = b(repo, "new", "story", "--title", "Publish the sprint calendar", "--parent", ep,
                  "--goal", "calendar published")
    assert code == 0 and "warning" not in out, out
    edit(repo, dup, status="dropped", notes="planted")
    edit(repo, item(repo, "Rotate used BitLocker recovery keys")["id"], status="dropped", notes="planted")
    code, out = b(repo, "similar", "Rotate BitLocker recovery keys")
    assert code == 0 and dup not in out and "0 near-duplicate(s)" in out, out
    assert b(repo, "similar", "a the of")[0] == 1  # nothing to compare is refused, not an empty ranking


def test_backlog_similar_recurs_is_a_list_of_sprint_ids(sprint):
    """recurs is optional; check refuses a non-list, a non-sprint id and a repeated sprint, and fmt keeps it stable."""
    repo, st = sprint["repo"], sprint["st"]
    for bad, why in (("SP-aaaaaaaa", "recurs must be a list"), (["ST-aaaaaaaa"], "recurs must be a list"),
                     (["SP-aaaaaaaa", "SP-aaaaaaaa"], "recurs names a sprint twice")):
        edit(repo, st, recurs=bad)
        code, out = b(repo, "check")
        assert code == 1 and why in out, out
    edit(repo, st, recurs=["SP-aaaaaaaa", "SP-bbbbbbbb"])
    f = Path(repo) / backlog.REL_DIR / f"{st}.json"
    before = f.read_bytes()
    assert b(repo, "fmt")[1].strip() == "fmt: rewrote 0" and f.read_bytes() == before
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_next_orders_s1_bugs_first(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], severity="S1")
    code, out = b(repo, "next", "--all")
    assert code == 0
    assert out.splitlines()[0].startswith(sprint["bg"])
    assert sprint["st"] not in out  # a story with an open task is not ready itself
    assert sprint["rv"] not in out  # the review waits on every other item


NOOP_TOOL = """import pathlib, sys
if not pathlib.Path('remote.cfg').is_file():
    print('note: no public remote (git config kb.publishRemote <remote>); nothing published')
    sys.exit(0)
sys.exit('refused: the defect')
"""


def noop_bug(sprint):
    """BG-uqmjlqfl planted: a bug whose repro runs a tool that fails while the clone has its remote (the defect), then
    the remote goes and the repro passes doing nothing."""
    repo = sprint["repo"]
    (repo / "pub.py").write_text(NOOP_TOOL, encoding="utf-8", newline="\n")
    (repo / "remote.cfg").write_text("pub\n", encoding="utf-8")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")  # pytest's rewritten test_fix.py
    commit(repo, "tool")
    code, out = b(repo, "new", "bug", "--title", "Publish refuses", "--sprint", sprint["sp"], "--severity", "S2",
                  "--repro", "python3 pub.py", "--goal", "publish works", "--touch", "remote.cfg", "--touch", "test_fix.py")
    assert code == 0 and "no --check runs tests" in out, out
    bg = item(repo, "Publish refuses")["id"]
    commit(repo, "file bug")
    sh(repo, "git", "rm", "-q", "remote.cfg")
    commit(repo, "the remote goes", bg)
    return repo, bg


def test_done_flags_noop_check_refuses_a_repro_that_does_nothing_here(sprint):
    repo, bg = noop_bug(sprint)
    code, out = b(repo, "done", bg)
    assert code == 1 and "passed without doing its work" in out and "no public remote" in out, out
    assert "no check that runs tests" in out and item(repo, "Publish refuses")["status"] != "done"
    # the operator accepts the host-bound proof: done passes, still warning of it
    assert b(repo, "gate", "add", bg, "--id", backlog.HOST_BOUND_GATE, "--question", "Accept?", "--option", "accept",
             "--option", "add-test", "--recommendation", "add-test")[0] == 0
    assert b(repo, "answer", bg, backlog.HOST_BOUND_GATE, "--answer", "accept", "--by", "operator")[0] == 0
    commit(repo, "gate", bg)
    code, out = b(repo, "done", bg, "--dry-run")
    assert code == 0 and "warning:" in out and "would be done" in out, out


def test_done_flags_noop_check_passes_with_a_test_run(sprint):
    """A check that runs tests and did its work proves the fix beside the no-op repro; one whose tests were all
    skipped does not."""
    pytest.importorskip("pytest")
    repo, bg = noop_bug(sprint)
    run = "python3 -m pytest -q -p no:cacheprovider test_fix.py"
    edit(repo, bg, checks=[{"run": shlex.split(run)}])
    (repo / "test_fix.py").write_text("import pytest\n\n\ndef test_fix():\n    pytest.skip('planted')\n",
                                      encoding="utf-8")
    commit(repo, "a skipped test", bg)
    code, out = b(repo, "done", bg)
    assert code == 1 and "no check that runs tests" in out, out
    (repo / "test_fix.py").write_text("def test_fix():\n    assert True\n", encoding="utf-8")
    commit(repo, "the test runs", bg)
    code, out = b(repo, "done", bg)
    assert code == 0 and "warning:" in out and "no public remote" in out, out


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


def test_done_claim_commit_alone_is_not_the_work(sprint):
    """Planted: the claim commit carries KB-Work but changes only item files, and the work commit's KB-Work sits in a
    paragraph before Co-Authored-By: done does not count the claim commit as the work, so it refuses."""
    repo, bg = sprint["repo"], sprint["bg"]
    assert b(repo, "claim", bg, "--by", "agent-1")[0] == 0
    commit(repo, "claim", bg)
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"write c\n\nKB-Work: {bg}\n\nCo-Authored-By: A <a@example.com>")
    code, out = b(repo, "done", bg)
    assert code == 1 and "no commit on HEAD carries the trailer" in out, out
    (repo / "src" / "d.txt").write_text("d\n", encoding="utf-8")
    commit(repo, "write d", bg)
    code, out = b(repo, "done", bg)
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


def test_task_inherits_its_storys_undone_depends_on(sprint):
    """A story that depends on an undone item holds its tasks too, in waits, ready, next and horizon."""
    repo, st, tk, bg = sprint["repo"], sprint["st"], sprint["tk"], sprint["bg"]
    assert tk in backlog.ready(backlog.Backlog(repo))
    edit(repo, st, depends_on=[bg])
    bl = backlog.Backlog(repo)
    assert any(w.startswith(f"depends on {bl.label(bg)} (through {bl.label(st)})") for w in backlog.waits(bl, tk))
    assert tk not in backlog.ready(bl) and backlog.ready(bl) == [bg]
    code, out = b(repo, "next", "--all")
    assert code == 0 and tk not in out and bg in out, out
    reach, stuck, path, widths = backlog.horizon(bl, sprint["sp"])
    assert tk in reach and not stuck  # in-sprint: reachable, but after the bug on the critical path
    assert path == [bg, tk, st, sprint["rv"]] and widths == [1, 1, 1, 1]
    # a dependency outside the sprint holds the task as it holds the story
    b(repo, "new", "story", "--title", "Elsewhere", "--parent", sprint["ep"], "--goal", "x",
      "--check", argstr(is_file("src/x.txt")))
    edit(repo, st, depends_on=[item(repo, "Elsewhere")["id"]])
    reach, stuck, path, widths = backlog.horizon(backlog.Backlog(repo), sprint["sp"])
    assert tk not in reach and any(tk in ids for c, ids in stuck.items() if c.startswith("outside this sprint"))


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


def test_horizon_hook_stays_under_the_limit_with_many_sprints_and_a_long_gate(sprint):
    """Six active sprints with long titles and a gate question of 1500 characters: the lines are clipped and the last
    ones give way to a line naming how many were left out, so the hook stays valid JSON under the limit."""
    repo = sprint["repo"]
    ids = []
    for n in range(6):
        title = f"Sprint {n} whose title runs on" + " and on" * 12
        b(repo, "new", "sprint", "--title", title, "--goal", f"goal {n}")
        sp = item(repo, title)["id"]
        ids.append(sp)
        b(repo, "new", "bug", "--title", f"Bug {n}", "--sprint", sp, "--severity", "S3",
          "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**")
        assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
        assert b(repo, "start", sp)[0] == 0
    edit(repo, item(repo, "Bug 0")["id"], gates=[{"id": "G1", "kind": "blocking", "question": "Why? " * 300,
                                                  "recommendation": "fix"}])
    code, out = b(repo, "horizon", "--hook")
    assert code == 0, out
    assert len(out) < HOOK_LIMIT, (len(out), out)
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "Why? " * 30 not in out and "more line(s): python3 _tools/backlog.py horizon" in context, context
    assert context.startswith("sprint SP-") and any(sp in context for sp in ids + [sprint["sp"]]), context
    code, out = b(repo, "horizon")  # without --hook: every sprint and the whole question
    assert code == 0 and all(sp in out for sp in ids) and "Why? " * 300 in out.replace("\n", "")


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
    """close --summary prints one line per item close deletes (the task, the review, a dropped subtask and the
    finished epic included) with the commit done recorded, and nothing else."""
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
    body = lines[1:]
    assert any(x.startswith(f"- {ep} “Epic” (epic): done at ") for x in body)  # the finished epic goes too
    assert f"  - {st} “Story” (story): done at {work[:10]}" in body
    assert f"    - {tk} “Task” (task): done at {work[:10]}" in body
    assert f"      - {sb} “Sub” (subtask): dropped, no evidence commit" in body
    assert f"- {bg} “Bug” (bug): done at {work[:10]}" in body
    assert any(x.startswith(f"- {rv} “Review sprint: Sprint” (story): done at ") for x in body)
    assert len(body) == 6, body  # one line per deleted item, no more
    assert body.index(f"  - {st} “Story” (story): done at {work[:10]}") < body.index(
        f"    - {tk} “Task” (task): done at {work[:10]}")  # a child under its parent


def finish(sprint):
    """Every item of the sprint fixture done (the epic too), committed: close may delete them."""
    repo, tk, st, bg, rv, ep = (sprint[k] for k in ("repo", "tk", "st", "bg", "rv", "ep"))
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


def item_files(repo):
    return {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")}


def check_summary_changed_nothing(repo, before, out):
    """What close --summary must leave: every item file as it was, nothing named deleted or closed."""
    after = item_files(repo)
    assert after == before, f"close --summary changed {sorted(set(before) ^ set(after)) or 'an item file'}"
    assert "deleted " not in out and "closed " not in out, out


def test_backlog_close_summary_leaves_every_item_file_and_close_deletes(sprint):
    repo, sp = sprint["repo"], sprint["sp"]
    finish(sprint)
    before = item_files(repo)
    assert len(before) == 6
    code, out = b(repo, "close", sp, "--summary")
    assert code == 0 and out.startswith(f"delivered by {sp} “Sprint”:"), out
    check_summary_changed_nothing(repo, before, out)
    assert not subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True,
                              text=True).stdout  # nothing written, nothing deleted
    code, out = b(repo, "close", sp)  # plain close deletes them all
    assert code == 0 and "closed " in out, out
    assert item_files(repo) == {}


def test_backlog_close_summary_planted_failure_of_a_deleting_summary_is_caught(sprint):
    """The check is not vacuous: a summary run that deleted an item file (planted: one removed by hand after it), or
    printed the deletions, fails it."""
    repo, sp = sprint["repo"], sprint["sp"]
    finish(sprint)
    before = item_files(repo)
    code, out = b(repo, "close", sp, "--summary")
    (Path(repo) / backlog.REL_DIR / f"{sprint['tk']}.json").unlink()  # planted
    with pytest.raises(AssertionError, match=sprint["tk"]):
        check_summary_changed_nothing(repo, before, out)
    with pytest.raises(AssertionError):
        check_summary_changed_nothing(repo, item_files(repo), out + f"deleted {sprint['tk']}\n")  # planted


def test_backlog_close_summary_with_commit_is_refused_and_commits_nothing(sprint):
    repo, sp = sprint["repo"], sprint["sp"]
    finish(sprint)
    before = item_files(repo)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout
    code, out = b(repo, "close", sp, "--summary", "--commit")
    assert code == 1 and "only prints" in out, out
    check_summary_changed_nothing(repo, before, out)
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout == head


def holders(sprint):
    """The task claimed by agent-1 holding src/a.txt and docs/*.md, the bug by agent-2 holding src/**, a second task
    (todo, unclaimed) holding src/b/**; the story stays todo, so it holds nothing."""
    repo, tk, bg, st = sprint["repo"], sprint["tk"], sprint["bg"], sprint["st"]
    edit(repo, tk, touches=["src/a.txt", "docs/*.md"])
    b(repo, "new", "task", "--title", "Task two", "--parent", st, "--goal", "b/x written", "--touch", "src/b/**",
      "--check", argstr(is_file("src/b/x.txt")))
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    assert b(repo, "claim", bg, "--by", "agent-2")[0] == 0
    return item(repo, "Task two")["id"]


def check_held_overlaps(out, code, sprint):
    """What held --overlaps must say for task two: the bug's src/** meets its src/b/**, the task's paths do not."""
    assert code == 1, out
    assert out.splitlines() == [f"src/**  {sprint['bg']} “Bug”  by agent-2  {sprint['sp']} “Sprint”  meets src/b/**"], out


def test_backlog_held_paths_lists_each_claimed_glob_with_claimer_and_sprint(sprint):
    repo, tk, bg, sp = sprint["repo"], sprint["tk"], sprint["bg"], sprint["sp"]
    holders(sprint)
    code, out = b(repo, "held")
    assert code == 0, out
    assert out.splitlines() == [f"docs/*.md  {tk} “Task”  by agent-1  {sp} “Sprint”",
                                f"src/**  {bg} “Bug”  by agent-2  {sp} “Sprint”",
                                f"src/a.txt  {tk} “Task”  by agent-1  {sp} “Sprint”"], out


def test_backlog_held_paths_overlaps_names_the_claimed_items_an_item_would_meet(sprint):
    repo = sprint["repo"]
    tk2 = holders(sprint)
    code, out = b(repo, "held", "--overlaps", tk2)
    check_held_overlaps(out, code, sprint)
    code, out = b(repo, "held", "--overlaps", sprint["tk"])  # its own src/a.txt meets the bug's src/**
    assert code == 1 and out.startswith(f"src/**  {sprint['bg']} “Bug”") and "meets src/a.txt" in out, out
    edit(repo, tk2, touches=["kb/public/x/**"])
    code, out = b(repo, "held", "--overlaps", tk2)
    assert code == 0 and "no claimed item's touches overlap" in out, out
    assert b(repo, "held", "--overlaps", "TK-zzzzzzzz")[0] == 2


def test_backlog_held_paths_planted_failure_of_the_overlap_rule_is_caught(sprint, capsys, monkeypatch):
    """The check is not vacuous: an overlap rule that never finds one (planted) fails it."""
    tk2 = holders(sprint)
    monkeypatch.setattr(backlog, "touches_overlap", lambda a, b, files: False)  # planted
    code = backlog.main(["--root", str(sprint["repo"]), "held", "--overlaps", tk2])
    with pytest.raises(AssertionError):
        check_held_overlaps(capsys.readouterr().out, code, sprint)


def test_backlog_held_paths_overlap_rule():
    files = ["_tools/backlog.py", "_tools/kbgit.py"]
    assert backlog.touches_overlap("_tools/**", "_tools/x.py", [])  # a glob read as a path
    assert backlog.touches_overlap("_tools/*.py", "_tools/back*", files)  # a tracked file both match
    assert not backlog.touches_overlap("_tools/*.py", "_tools/zz*", files)
    assert not backlog.touches_overlap("kb/_self/a.md", "kb/_self/b.md", files)


def test_backlog_held_paths_ref_reads_the_claims_git_has(sprint):
    """--ref reads the item files as a ref has them: a claim pushed there shows though the files lost it."""
    repo, tk = sprint["repo"], sprint["tk"]
    holders(sprint)
    commit(repo, "claims")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    assert b(repo, "release", tk)[0] == 0
    assert f"{tk} “Task”" not in b(repo, "held")[1]
    code, out = b(repo, "held", "--ref", "origin/main")
    assert code == 0 and f"src/a.txt  {tk} “Task”  by agent-1" in out, out
    code, out = b(repo, "held", "--ref", "no/such/ref")
    assert code == 2 and "held --ref no/such/ref" in out, out


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
          jobs=[{"name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}])
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


# ---- red-pipeline over the job-state table (test_ql_deliver.py's rows: every status, started or not, each reason)

# allow_failure: a failed job leaves its pipeline's status success; created, pending and running are unfinished
PIPELINE_OF = {"failed": "success"}


def job_repro_rows():
    """`--status --job kb-tests` passes only when the newest pipeline in which kb-tests reached a verdict passed it:
    a canceled, manual or skipped job someone started is no verdict (BG-sim2fdaa), so the older red run decides."""
    return [pytest.param(st, id=state_id(st)) for st in job_states()]


@pytest.mark.parametrize("st", job_repro_rows())
def test_job_state_table_red_pipeline_job_repro(repo, monkeypatch, st):
    """Pipeline 81 holds kb-tests in the row's state, the older 80 a kb-tests whose script failed."""
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 81, "sha": sha, "status": PIPELINE_OF.get(st[0], st[0])},
                              {"id": 80, "sha": sha, "status": "success"}],
          jobs={81: [job_of(*st)], 80: [job_of("failed", True, "script_failure")]})
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == (0 if st[0] == "success" else 1)


@pytest.mark.parametrize("reason", ["ci_quota_exceeded", "runner_system_failure"])
def test_red_pipeline_files_a_red_status_whose_job_never_ran(repo, monkeypatch, reason):
    """BG-vsqfchgz: main's pipeline 85 failed by its status, its only failed job kb-tests failed without running; in
    the older 84 kb-tests passed. The bug is filed with plain `--status` as its repro (a `--job kb-tests` one would
    read 84 and pass), and that repro, run against the same forge, fails."""
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 85, "sha": sha, "status": "failed"}, {"id": 84, "sha": sha, "status": "success"}],
          jobs={85: [{"id": 41, "name": "kb-tests", "status": "failed", "failure_reason": reason}],
                84: [{"id": 40, "name": "kb-tests", "status": "success", "started_at": "2026-09-30T08:00:00Z"}]})
    monkeypatch.setattr(backlog, "run_check", lambda root, c: (
        lambda code: (code == 0, code, ""))(backlog.main(["--root", str(root), *c["run"][2:]])))
    assert red_pipeline(repo) == 0
    filed = [x for x in bugs(repo) if "pipeline 85" in x["title"]]
    assert filed and filed[0]["repro"]["run"] == backlog.STATUS_REPRO, filed
    assert red_pipeline(repo, "--status") == 1
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 0  # what a --job repro would have read


def test_red_pipeline_job_skips_a_canceled_run(repo, monkeypatch):
    """BG-sim2fdaa: someone starts kb-tests on main and cancels it; the newer pipeline holds no verdict on kb-tests,
    so a red-main bug's repro (`--status --job kb-tests`) still reads the older red run and fails."""
    sha = head(repo)
    pipelines = [{"id": 83, "sha": sha, "status": "canceled"}, {"id": 82, "sha": sha, "status": "success"}]
    jobs = {83: [{"id": 31, "name": "kb-tests", "status": "canceled", "started_at": "2026-09-30T09:00:00Z"}],
            82: [{"id": 30, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure",
                  "started_at": "2026-09-30T08:00:00Z"}]}
    forge(monkeypatch, repo, pipelines, jobs=jobs)
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1
    assert red_pipeline(repo, "--status") == 1  # without --job the canceled run hides nothing either
    jobs[83][0]["status"] = "manual"  # started, then left waiting: no verdict either
    pipelines[0]["status"] = "manual"
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1
    jobs[83][0]["status"] = "success"  # a run that passed is the verdict
    pipelines[0]["status"] = "success"
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 0


def file_rows():
    """A main pipeline that failed is red whatever its job did, so red-pipeline files a bug: its repro must fail now.
    A failed job that never ran is not named by `--job`, which would read an older pass (BG-vsqfchgz)."""
    return [pytest.param(st, id=state_id(st)) for st in job_states()]


@pytest.mark.parametrize("st", file_rows())
def test_job_state_table_red_pipeline_files_a_failed_main(repo, monkeypatch, st):
    """Pipeline 91 failed with kb-tests in the row's state; in the older 90 kb-tests passed. The bug's repro runs
    against the same forge (not canned), as red-pipeline's second read does."""
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 91, "sha": sha, "status": "failed"}, {"id": 90, "sha": sha, "status": "success"}],
          jobs={91: [job_of(*st)], 90: [job_of("success", True, None)]})
    monkeypatch.setattr(backlog, "run_check", lambda root, c: (
        lambda code: (code == 0, code, ""))(backlog.main(["--root", str(root), *c["run"][2:]])))
    assert red_pipeline(repo) == 0
    assert [x for x in bugs(repo) if "pipeline 91" in x["title"]], "nothing filed for a failed main"


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
        self.assert_commit(repo, "file", sp, "Next", [sp, rv], self.rel(sp, rv), monkeypatch)

    def test_backlog_commit_flag_start_commits_the_sprint_and_its_items(self, repo, monkeypatch):
        b(repo, "new", "sprint", "--title", "Sprint", "--goal", "ship b")
        sp = item(repo, "Sprint")["id"]
        b(repo, "new", "bug", "--title", "Bug", "--sprint", sp, "--severity", "S3", "--repro",
          argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**")
        bg, rv = item(repo, "Bug")["id"], item(repo, "Review sprint: Sprint")["id"]
        assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
        commit(repo, "plan")
        code, out = b(repo, "start", sp, "--commit", "--trailer", self.CO)
        assert code == 0, out
        self.assert_commit(repo, "start", sp, "Sprint", [sp], self.rel(bg, rv, sp), monkeypatch)

    def test_backlog_commit_flag_close_commits_the_deletions_with_the_summary(self, sprint, monkeypatch):
        repo, tk, st, bg, rv, ep, sp = (sprint[k] for k in ("repo", "tk", "st", "bg", "rv", "ep", "sp"))
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
        self.assert_commit(repo, "close", sp, "Sprint", [sp], self.rel(ep, st, tk, bg, rv, sp), monkeypatch)
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


STEP_STUB = """import os, sys
NAME = {name!r}
with open(os.environ["LAND_LOG"], "a", encoding="utf-8") as f:
    f.write(NAME + "\\n")
if os.environ.get("LAND_FAIL") == NAME:
    print(NAME + ": planted failure")
    sys.exit(1)
print(NAME + ": ok")
"""
# sync's stand-in: pushes by lane as kbgit.py sync --push does, the lane and the code/<id> branch from the real
# kg_lane.lane_plan (LAND_TOOLS: this _tools/ directory), the one helper sync and land name the branch with
SYNC_STUB = STEP_STUB.format(name="sync") + """import subprocess
def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout
git("fetch", "-q", "origin")
sys.path.insert(0, os.environ["LAND_TOOLS"])
import kg_lane
_, branch = kg_lane.lane_plan(os.getcwd(), "refs/remotes/origin/main", "HEAD")
git("push", "-q", "origin", "HEAD:refs/heads/" + (branch or "main"))
"""


def swaps_kbgit_kb(source):
    """Whether the source assigns kbgit.KB (the module global land once swapped around lane_plan)."""
    import ast
    for node in ast.walk(ast.parse(source)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AugAssign) else []
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Attribute) and sub.attr == "KB" and getattr(sub.value, "id", "") == "kbgit":
                    return True
    return False


def test_bl_split_land_does_not_swap_kb():
    """land names the branch through kg_lane.lane_plan(root, ...) and never sets kbgit.KB. Planted failure: the old swap."""
    assert not swaps_kbgit_kb(Path(backlog.__file__).read_text(encoding="utf-8"))
    assert swaps_kbgit_kb("kb, kbgit.KB = kbgit.KB, str(root)\n")
    assert swaps_kbgit_kb("kbgit.KB = kb\n")
    assert not swaps_kbgit_kb("x = kbgit.KB\n")


class TestBacklogLand:
    """backlog.py land ID in a throwaway clone with a local bare remote; the heavy steps (stress_test.py, rag.py eval,
    the lint) and kbgit.py sync are stubs in the clone that log their names. A content item lands in one run; a code
    item's first run gates and opens code/<id> without moving main, and a re-run after the merge finishes it. Planted
    failures (a failing heavy step, a failing done check, a rebase conflict, a dirty tree) stop land at that step,
    named, with nothing after it run."""

    CO = "Co-Authored-By: A <a@example.com>"
    HEAVY = ["stress_test.py", "rag.py eval", "lint"]

    @staticmethod
    def out(cwd, *a):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              check=True).stdout

    @pytest.fixture
    def landing(self, sprint, monkeypatch):
        repo, tk = sprint["repo"], sprint["tk"]
        stubs = {"_tools/stress_test.py": STEP_STUB.format(name="stress_test.py"),
                 "_tools/rag.py": STEP_STUB.format(name="rag.py eval"),
                 ".claude/skills/kb-verify/lint.py": STEP_STUB.format(name="lint"), "_tools/kbgit.py": SYNC_STUB}
        for rel, text in stubs.items():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text, encoding="utf-8")
        commit(repo, "plan and step stubs")
        sh(repo, "git", "branch", "-M", "main")
        remote = repo.parent / f"{repo.name}-remote.git"
        sh(repo, "git", "init", "-q", "--bare", str(remote))
        sh(repo, "git", "remote", "add", "origin", str(remote))
        sh(repo, "git", "push", "-q", "origin", "main")
        log = repo.parent / f"{repo.name}-land.log"
        monkeypatch.setenv("LAND_LOG", str(log))
        monkeypatch.setenv("LAND_TOOLS", TOOLS)
        monkeypatch.delenv("LAND_FAIL", raising=False)
        sh(repo, "git", "checkout", "-q", "-b", f"work/{tk}")
        assert b(repo, "claim", tk, "--by", "worker", "--commit")[0] == 0
        return {"repo": repo, "tk": tk, "remote": remote, "log": log,
                "main": self.out(remote, "rev-parse", "main").strip()}

    def work(self, ld, files, check):
        repo, tk = ld["repo"], ld["tk"]
        edit(repo, tk, touches=["src/**", "kb/public/**", "_tools/b.py"], checks=[{"run": is_file(check)}])
        for rel in files:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("b\n", encoding="utf-8")
        commit(repo, "work", tk)

    @staticmethod
    def steps(ld):
        return ld["log"].read_text(encoding="utf-8").splitlines() if ld["log"].exists() else []

    def remote_item(self, ld, ref="main"):
        return json.loads(self.out(ld["remote"], "show", f"{ref}:{backlog.REL_DIR}/{ld['tk']}.json"))

    def land(self, ld):
        return b(ld["repo"], "land", ld["tk"], "--trailer", self.CO)

    def test_backlog_land_content_item_in_one_run(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "main")  # main moves on meanwhile: land rebases onto it
        (ld["repo"] / "kb" / "public").mkdir(parents=True, exist_ok=True)
        (ld["repo"] / "kb" / "public" / "y.md").write_text("y\n", encoding="utf-8")
        commit(ld["repo"], "other work")
        sh(ld["repo"], "git", "push", "-q", "origin", "main")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.steps(ld) == ["sync"], out  # no _tools/ change: no heavy step
        assert self.remote_item(ld)["status"] == "done"
        msg = self.out(ld["remote"], "log", "-1", "--format=%B", "main")
        assert msg.startswith(f"chore(backlog): done {ld['tk']}") and self.CO in msg, msg
        assert "kb/public/y.md" in self.out(ld["remote"], "ls-tree", "-r", "--name-only", "main")

    def test_backlog_land_code_item_waits_for_its_merge_request_then_finishes(self, landing):
        ld = landing
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        code, out = self.land(ld)
        assert code == 0 and f"code/{ld['tk']}" in out and "not done yet" in out, out
        assert self.steps(ld) == self.HEAVY + ["sync"], out
        assert self.out(ld["remote"], "rev-parse", "main").strip() == ld["main"]  # main did not move
        assert self.remote_item(ld, f"code/{ld['tk']}")["status"] == "doing"
        code, out = self.land(ld)  # before the merge: nothing re-run, nothing pushed
        assert code == 0 and "waits for its merge request" in out, out
        assert len(self.steps(ld)) == 4
        sh(ld["remote"], "git", "update-ref", "refs/heads/main", f"refs/heads/code/{ld['tk']}")  # the merge
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.steps(ld)[4:] == ["sync"], out  # the item file alone: the heavy steps ran once
        assert self.remote_item(ld)["status"] == "done"

    def test_backlog_land_stops_at_the_failing_step_and_names_it(self, landing, monkeypatch):
        ld = landing
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        monkeypatch.setenv("LAND_FAIL", "rag.py eval")  # planted
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step rag.py eval" in out and "planted failure" in out, out
        assert self.steps(ld) == self.HEAVY[:2], out  # neither the lint nor sync ran
        assert not self.out(ld["remote"], "branch", "--list", "code/*").strip()

    def test_backlog_land_stops_at_done(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/missing.md")  # planted: the item's check fails
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step done" in out, out
        assert self.steps(ld) == [] and self.out(ld["remote"], "rev-parse", "main").strip() == ld["main"]

    def test_backlog_land_stops_at_rebase_and_aborts_it(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "main")
        (ld["repo"] / "kb" / "public" / "x").mkdir(parents=True, exist_ok=True)
        (ld["repo"] / "kb" / "public" / "x" / "a.md").write_text("other\n", encoding="utf-8")  # planted conflict
        commit(ld["repo"], "conflicting work")
        sh(ld["repo"], "git", "push", "-q", "origin", "main")
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step rebase" in out, out
        assert self.steps(ld) == [] and not self.out(ld["repo"], "status", "--porcelain")
        assert not (ld["repo"] / ".git" / "rebase-merge").exists()

    def test_backlog_land_refuses_a_dirty_tree(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        (ld["repo"] / "src" / "a.txt").write_text("dirty\n", encoding="utf-8")  # planted
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step clean tree" in out, out
        assert self.steps(ld) == []

    # land returns the checkout to where it started: `git rebase UPSTREAM BRANCH` switches to BRANCH, and an
    # orchestrator's later claim --commit must not land on work/<id> and ride into its code/<id> merge request. The
    # names differ in their first 30 characters: pytest cuts tmp_path's name there, and the fixture's remote sits
    # beside it, so two tests on one worker would share it.
    def head_ref(self, ld):
        p = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=ld["repo"], capture_output=True, text=True,
                           encoding="utf-8")
        return p.stdout.strip() or None

    def orchestrate(self, ld, files, check):
        """The worker's commit on work/<id>, then the orchestrator's own branch checked out, as land finds it."""
        self.work(ld, files, check)
        sh(ld["repo"], "git", "checkout", "-q", "-b", "orch", "main")

    def test_content_lane_land_returns_to_start_branch(self, landing):
        ld = landing
        self.orchestrate(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out
        assert self.remote_item(ld)["status"] == "done"
        assert not self.out(ld["repo"], "status", "--porcelain")

    def test_code_lane_land_returns_to_start_branch(self, landing):
        ld = landing
        self.orchestrate(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        code, out = self.land(ld)
        assert code == 0 and "not done yet" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out
        code, out = self.land(ld)  # the re-run that waits for the merge request
        assert code == 0 and "waits for its merge request" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out

    def test_stopped_land_returns_to_start_branch(self, landing, monkeypatch):
        ld = landing
        self.orchestrate(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        monkeypatch.setenv("LAND_FAIL", "lint")  # planted: a stop after the rebase switched to work/<id>
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step lint" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out

    def test_conflicted_land_returns_to_start_branch(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "main")
        (ld["repo"] / "kb" / "public" / "x").mkdir(parents=True, exist_ok=True)
        (ld["repo"] / "kb" / "public" / "x" / "a.md").write_text("other\n", encoding="utf-8")  # planted conflict
        commit(ld["repo"], "conflicting work")
        sh(ld["repo"], "git", "push", "-q", "origin", "main")
        sh(ld["repo"], "git", "checkout", "-q", "-b", "orch")
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step rebase" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out

    def test_detached_land_returns_to_start_branch(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "--detach", "main")
        start = self.out(ld["repo"], "rev-parse", "HEAD").strip()
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.head_ref(ld) is None and self.out(ld["repo"], "rev-parse", "HEAD").strip() == start, out

    # land names the code/<id> branch it waits on with kg_lane.lane_plan, as sync names the branch it opens: a story's
    # range that begins with a content commit of another item (a bug filed with new --commit) is recognised on a
    # re-run before the merge. Planted: the bug's own code commit comes first, so sync opens code/<bug>, a branch
    # land's old naming (the item's own id) never looked for.
    def story_range(self, ld, bug_code):
        repo, tk = ld["repo"], ld["tk"]
        code, out = b(repo, "new", "bug", "--title", "Found", "--severity", "S3", "--repro",
                      argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**", "--commit")
        assert code == 0, out
        bug = item(repo, "Found")["id"]
        if bug_code:
            (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
            commit(repo, "fix the bug first", bug)
        (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
        commit(repo, "the story's work", tk)
        return bug

    def land_story_twice(self, ld, branch):
        land = ["land", self.story, "--branch", f"work/{ld['tk']}", "--trailer", self.CO]
        code, out = b(ld["repo"], *land)
        assert code == 0 and f"merge request of branch {branch}" in out and "not done yet" in out, out
        assert self.out(ld["remote"], "branch", "--list", branch).strip(), out
        code, out = b(ld["repo"], *land)  # before the merge: it finds the branch sync opened
        assert code == 0 and "waits for its merge request" in out and f"branch {branch} on origin" in out, out
        assert self.steps(ld) == ["sync"], out  # nothing pushed again

    def test_claim_first_land_names_sync_branch(self, landing, sprint):
        self.story = sprint["st"]
        self.story_range(landing, bug_code=False)
        self.land_story_twice(landing, f"code/{landing['tk']}")

    def test_bug_first_land_names_sync_branch(self, landing, sprint):
        self.story = sprint["st"]
        bug = self.story_range(landing, bug_code=True)
        self.land_story_twice(landing, f"code/{bug}")

    # a finished worker's worktree under .claude/worktrees/ that Claude Code left locked ("claude agent ...") and
    # clean is unlocked and removed by land's branch step; planted: one with uncommitted files, another lock reason,
    # or outside .claude/worktrees/ is refused, its lock and files kept
    AGENT_LOCK = "claude agent agent-a0 (pid 1 start Mon Jan  1 00:00:00 2026)"

    def worker_tree(self, ld, lock=AGENT_LOCK, where=None):
        """The landed branch checked out in a worker's worktree, locked with LOCK; the clone back on main."""
        repo, tk = ld["repo"], ld["tk"]
        self.work(ld, ["src/b.txt"], "src/b.txt")
        sh(repo, "git", "checkout", "-q", "main")
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "exclude").write_text(".claude/worktrees/\n", encoding="utf-8")
        path = where or repo / ".claude" / "worktrees" / "agent-a0"
        sh(repo, "git", "worktree", "add", "-q", str(path), f"work/{tk}")
        if lock is not None:
            sh(repo, "git", "worktree", "lock", "--reason", lock, str(path))
        return path

    def worktree_listed(self, ld, path):
        listed = self.out(ld["repo"], "worktree", "list", "--porcelain")
        return f"worktree {path.resolve()}" in listed or f"worktree {path}" in listed

    def test_clean_worker_worktree_unlocked_and_removed(self, landing):
        ld = landing
        path = self.worker_tree(ld)
        code, out = self.land(ld)
        assert code == 0 and "removed the finished worker's worktree" in out and "not done yet" in out, out
        assert not path.exists() and not self.worktree_listed(ld, path), out
        assert self.head_ref(ld) == "refs/heads/main", out

    def refused_kept(self, ld, path, why):
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step branch" in out and why in out, out
        assert path.exists() and self.worktree_listed(ld, path), out
        return out

    def test_dirty_worker_worktree_unlocked_never(self, landing):
        ld = landing
        path = self.worker_tree(ld)
        (path / "src" / "b.txt").write_text("unsaved\n", encoding="utf-8")  # planted: uncommitted work
        self.refused_kept(ld, path, "uncommitted changes")
        assert (path / "src" / "b.txt").read_text(encoding="utf-8") == "unsaved\n"
        assert "locked claude agent" in self.out(ld["repo"], "worktree", "list", "--porcelain")

    def test_other_lock_worker_worktree_unlocked_never(self, landing):
        ld = landing
        path = self.worker_tree(ld, lock="on a removable disk")  # planted: not Claude Code's lock
        self.refused_kept(ld, path, "locked (on a removable disk)")

    def test_unlocked_worker_worktree_unlocked_never(self, landing):
        ld = landing
        path = self.worker_tree(ld, lock=None)  # not locked: the orchestrator removes it, as before
        self.refused_kept(ld, path, "not locked")

    def test_outside_worker_worktree_unlocked_never(self, landing):
        ld = landing
        where = ld["repo"].parent / f"{ld['repo'].name}-wt"  # planted: not under .claude/worktrees/
        path = self.worker_tree(ld, where=where)
        self.refused_kept(ld, path, "not under .claude/worktrees/")

    # a worker that left a background command running in its worktree: land refuses to remove the worktree from
    # under it, naming the pid; planted: a process check blind to it removes the worktree, which the check catches.
    # The test names differ in their first 30 characters (pytest's tmp_path cut, beside which the remote sits).
    @staticmethod
    def sleeper(path):
        if backlog.live_processes(path)[0] is None:
            pytest.skip(f"no process check on this host: {backlog.live_processes(path)[1]}")
        return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], cwd=path)

    @staticmethod
    def check_refused_naming(code, out, pid):
        assert code == 1 and "land stopped at step branch" in out and f"pid {pid} (" in out, out
        assert "a process still runs there" in out, out

    def test_pid_named_land_refuses_live_worker_process(self, landing):
        ld = landing
        path = self.worker_tree(ld)
        child = self.sleeper(path)
        try:
            code, out = self.land(ld)
            self.check_refused_naming(code, out, child.pid)
            assert path.exists() and self.worktree_listed(ld, path), out
            assert "locked claude agent" in self.out(ld["repo"], "worktree", "list", "--porcelain")
        finally:
            child.kill()
            child.wait()
        code, out = self.land(ld)  # the process gone: the clean worktree is removed as before
        assert code == 0 and "removed the finished worker's worktree" in out, out

    def test_planted_blind_land_refuses_live_worker_process(self, landing, monkeypatch, capsys):
        ld = landing
        path = self.worker_tree(ld)
        child = self.sleeper(path)
        try:
            monkeypatch.setattr(backlog, "live_processes", lambda p: ([], None))  # planted: sees nothing
            other = backlog.checked_out_elsewhere(ld["repo"], f"work/{ld['tk']}")
            why = backlog.release_worker_worktree(ld["repo"], *other)
            with pytest.raises(AssertionError):
                self.check_refused_naming(1 if why else 0, f"land stopped at step branch: {why}", child.pid)
        finally:
            child.kill()
            child.wait()

    def test_unchecked_host_land_refuses_live_worker_process(self, landing, monkeypatch, capsys):
        """A host with no way to list processes does not refuse: land says it could not check and goes on."""
        ld = landing
        path = self.worker_tree(ld)
        monkeypatch.setattr(backlog, "live_processes", lambda p: (None, "no /proc and no lsof on this host"))
        other = backlog.checked_out_elsewhere(ld["repo"], f"work/{ld['tk']}")
        assert backlog.release_worker_worktree(ld["repo"], *other) is None
        out = capsys.readouterr().out
        assert "could not check" in out and "no lsof" in out and not path.exists(), out

    def test_backlog_land_refuses_kb_trailers(self, landing):
        code, out = b(landing["repo"], "land", landing["tk"], "--trailer", f"KB-Work: {landing['tk']}")
        assert code == 1 and "--trailer" in out, out

    # a re-run of land while the code/<id> request waits reads the request on GitLab: open, mergeable, auto-merge set
    # and a skipped pipeline is stuck (auto-merge never fires), and land names the command that merges it
    MR_SAMPLE = Path(TOOLS) / "fixtures" / "forge_mr" / "gitlab-merged-skipped-pipeline.json"
    FORGE_URL = "https://gitlab.corp.example.com/team/kb.git"
    MERGE_CMD = "glab mr merge 103 --auto-merge=false --yes -R https://gitlab.corp.example.com/team/kb"

    @classmethod
    def recorded_mr(cls):
        return json.loads(cls.MR_SAMPLE.read_text(encoding="utf-8"))["reply"]

    @classmethod
    def open_mr(cls, pipeline="skipped", **change):
        """The recorded request as it was while it waited: open and mergeable, its pipeline in state PIPELINE."""
        mr = cls.recorded_mr()
        mr.update(state="opened", detailed_merge_status="mergeable", merged_at=None, merged_by=None)
        mr["head_pipeline"]["status"] = pipeline
        mr.update(change)
        return mr

    def gitlab(self, monkeypatch, mr, signed_in=True, down=False):
        """origin (as land reads its url) is a GitLab project whose glab answers MR (None: no open request) for the
        list of open requests and the single request; DOWN: every glab api call fails as a network failure does."""
        calls, real = [], backlog.run

        def fake(argv, cwd=None):
            if argv[:3] == ["git", "remote", "get-url"]:
                return 0, self.FORGE_URL + "\n", ""
            if argv[0] != "glab":
                return real(argv, cwd=cwd)
            calls.append(argv)
            if argv[1] == "auth":
                return (0, "", "") if signed_in else (1, "", "not logged in")
            if down:
                return 127, "", "dial tcp: lookup gitlab.corp.example.com: no such host"
            if "/merge_requests?" in argv[-1]:
                return 0, json.dumps([{"iid": mr["iid"]}] if mr else []), ""
            if mr and argv[-1].endswith(f"/merge_requests/{mr['iid']}"):
                return 0, json.dumps(mr), ""
            return 1, "", "404 Not Found"

        monkeypatch.setattr(backlog, "run", fake)
        return calls

    def rerun(self, ld, capsys):
        """The code item's first land (it opens code/<id>), then the re-run in this process, where `run` is faked."""
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        code, out = self.land(ld)
        assert code == 0 and "not done yet" in out, out
        capsys.readouterr()
        code = backlog.main(["--root", str(ld["repo"]), "land", ld["tk"], "--trailer", self.CO])
        out = capsys.readouterr().out
        assert code == 0 and "waits for its merge request" in out, out
        assert len(self.steps(ld)) == 4, out  # nothing re-run, nothing pushed
        return out

    def test_land_stuck_auto_merge_is_reported(self, landing, monkeypatch, capsys):
        calls = self.gitlab(monkeypatch, self.open_mr())
        out = self.rerun(landing, capsys)
        assert "!103" in out and "pipeline was skipped" in out and self.MERGE_CMD in out, out
        listed = [c[-1] for c in calls if "/merge_requests?" in c[-1]]
        assert listed and "state=opened" in listed[0] and f"source_branch=code%2F{landing['tk']}" in listed[0]

    def test_land_stuck_auto_merge_not_reported_while_its_pipeline_runs(self, landing, monkeypatch, capsys):
        self.gitlab(monkeypatch, self.open_mr(pipeline="running"))
        out = self.rerun(landing, capsys)
        assert "glab mr merge" not in out, out

    @pytest.mark.parametrize("mr, forge", [
        ({"pipeline": "running"}, {}),
        ({"pipeline": "pending"}, {}),
        ({"detailed_merge_status": "conflict"}, {}),  # not mergeable
        ({"detailed_merge_status": "not_approved"}, {}),
        ({"merge_when_pipeline_succeeds": False}, {}),  # no auto-merge: nothing waits to fire
        ({"state": "closed"}, {}),
        ({"head_pipeline": None}, {}),
        (None, {}),  # no open request
        ({}, {"signed_in": False}),  # glab not signed in: nothing extra
        ({}, {"down": True}),  # a network failure: nothing extra
    ])
    def test_land_stuck_auto_merge_not_reported(self, tmp_path, monkeypatch, mr, forge):
        self.gitlab(monkeypatch, None if mr is None else self.open_mr(**mr), **forge)
        assert backlog.stuck_merge_request(tmp_path, "origin", "code/TK-aaaaaaaa") is None

    def test_land_stuck_auto_merge_reports_the_planted_stuck_request(self, tmp_path, monkeypatch):
        self.gitlab(monkeypatch, self.open_mr())
        note = backlog.stuck_merge_request(tmp_path, "origin", "code/TK-aaaaaaaa")
        assert note and self.MERGE_CMD in note and "/merge_requests/103" in note, note

    def test_land_stuck_auto_merge_reads_the_recorded_sample(self):
        mr = self.recorded_mr()  # merged by hand after its skipped pipeline left auto-merge waiting
        assert mr["merge_when_pipeline_succeeds"] is True and mr["head_pipeline"]["status"] == "skipped"
        assert not backlog.mr_stuck(mr)  # merged: nothing to report
        assert backlog.mr_stuck(self.open_mr())  # the same reply while it was open and mergeable
        legacy = self.open_mr()
        del legacy["detailed_merge_status"]  # a GitLab without the detailed field: merge_status decides
        assert backlog.mr_stuck(legacy)
        assert not backlog.mr_stuck(dict(legacy, merge_status="cannot_be_merged"))

    def test_land_stuck_auto_merge_skips_a_local_remote(self, landing, monkeypatch):
        """The landing fixture's origin is a bare repository on disk: no forge to ask, no glab call."""
        real, calls = backlog.run, []
        monkeypatch.setattr(backlog, "run", lambda argv, cwd=None: calls.append(argv) or real(argv, cwd=cwd))
        assert backlog.stuck_merge_request(landing["repo"], "origin", f"code/{landing['tk']}") is None
        assert [c[:3] for c in calls] == [["git", "remote", "get-url"]], calls


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
                  "--check", argstr(PASS), "--depends", bg, "--relates", sprint["st"], "--priority", "P1", "--rank", "3")
    assert code == 0 and "set " in out, out
    it = item_json(repo, tk)
    assert it["notes"] == "why" and it["links"] == ["pipeline 1"] and it["touches"] == ["src/a.txt", "kb/x/**"]
    assert it["checks"] == [{"run": PASS}] and it["depends_on"] == [bg] and it["relates_to"] == [sprint["st"]]
    assert it["priority"] == "P1" and it["rank"] == 3
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_backlog_set_moves_a_draft_story_to_another_sprint(repo):
    b(repo, "new", "sprint", "--title", "One", "--goal", "g")
    b(repo, "new", "sprint", "--title", "Two", "--goal", "g")
    one, two = item(repo, "One")["id"], item(repo, "Two")["id"]
    b(repo, "new", "story", "--title", "S", "--sprint", one, "--goal", "g", "--check", argstr(PASS))
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
                                              "options": ["left", "right"], "recommendation": "left"}]
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


def test_backlog_find_prints_open_matches_with_parent_chain_and_tree_open_hides_finished(sprint):
    """Planted: a done and a dropped item that match are not found and not in tree --open; a miss exits 1 with one
    line; words are case-insensitive and all must match."""
    repo, ep = sprint["repo"], sprint["ep"]
    story = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Rotate BitLocker keys", "--parent", story, "--goal", "keys rotated",
      "--touch", "src/**")
    live = item(repo, "Rotate BitLocker keys")["id"]
    b(repo, "new", "story", "--title", "Old BitLocker report", "--parent", ep, "--goal", "report")
    gone = item(repo, "Old BitLocker report")["id"]
    edit(repo, gone, status="dropped", notes="planted")
    code, out = b(repo, "find", "bitlocker", "ROTATED")
    assert code == 0, out
    lines = out.splitlines()
    assert live in lines[0] and gone not in out, out
    assert f"parent: {story} “Story”" in lines[1] and f"parent: {ep} “Epic”" in lines[2], out
    assert b(repo, "find", "bitlocker", "ROTATED") == (code, out)  # deterministic
    code, out = b(repo, "find", "bitlocker", "report")  # all words must match: only the dropped item has both
    assert code == 1 and len(out.splitlines()) == 1 and gone not in out, out
    assert b(repo, "find", "nonexistentword")[0] == 1
    assert b(repo, "find", " ")[0] == 1
    code, out = b(repo, "tree")
    assert gone in out
    code, out = b(repo, "tree", "--open")
    assert code == 0 and gone not in out and live in out, out


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
    assert b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")[0] == 0
    commit(repo, "the operator's answer")
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
    assert out.splitlines() == ["lib/mod.py  docs/n.md:1  1 line", "lib/mod.py  lib/user.py:1  2 lines",
                                "lib/mod.py  src/t.txt:1  1 line",
                                "helper_fn  docs/n.md:1  1 line", "helper_fn  lib/mod.py:1  1 line",
                                "helper_fn  lib/user.py:2  1 line",
                                "no_such_symbol  no tracked file names it"], out


def test_backlog_referrers_item_marks_the_files_outside_its_touches(sprint):
    repo = referrer_repo(sprint)
    code, out = b(repo, "referrers", "lib/mod.py", "--item", sprint["tk"])  # the task's touches are src/**
    assert code == 1, out
    assert "lib/mod.py  src/t.txt:1  1 line\n" in out + "\n" and "src/t.txt:1  1 line  outside" not in out, out
    assert "docs/n.md:1  1 line  outside touches" in out and "lib/user.py:1  2 lines  outside touches" in out, out
    edit(repo, sprint["tk"], touches=["src/**", "docs/n.md", "lib/user.py"])
    code, out = b(repo, "referrers", "lib/mod.py", "--item", sprint["tk"])
    assert code == 0 and "outside" not in out, out
    assert b(repo, "referrers", "x", "--item", "TK-zzzzzzzz")[0] == 2


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
