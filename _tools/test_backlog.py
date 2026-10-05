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
    assert "the sprint's start gate:" in out and "3 wait on the operator or a trigger" in out, out
    assert "approved, not started" not in out and "wait on backlog.py start" not in out, out
    # a change answer is no approval: still the operator's question (planted: an answer read as approval)
    edit(repo, sp, gates=[dict(g, answer="change: drop the bug", by="operator") if g["id"] == "start" else g
                          for g in item(repo, "Planned")["gates"]])
    code, out = b(repo, "horizon", "--sprint", sp)
    assert "the sprint's start gate:" in out and "approved, not started" not in out, out
    code, out = b(repo, "horizon", "--sprint", sp, "--hook")
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "3 wait on the operator" in ctx and "backlog.py start" not in ctx.split("Goals and")[0], ctx


def test_horizon_start_approved_waits_on_backlog_start_not_the_operator(repo):
    sp = planned_sprint(repo)
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "horizon", "--sprint", sp)
    assert code == 0, out
    assert f"approved, not started; run python3 _tools/backlog.py start {sp}" in out, out
    assert f"3 wait on backlog.py start {sp}; 0 wait on the operator or a trigger" in out, out
    assert "Approve this sprint" not in out, out
    code, out = b(repo, "horizon", "--sprint", sp, "--hook")
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "3 wait on backlog.py start" in ctx and "wait on the operator" not in ctx, ctx
    assert "approved, not started" in ctx and "Approve this sprint" not in ctx, ctx
    code, out = b(repo, "horizon", "--hook")  # no active sprint: the planned list names the approval
    assert "(approved, not started)" in json.loads(out)["systemMessage"], out
    # an item's own gate is still the operator's, inside an approved sprint
    bg = item(repo, "Planned bug")["id"]
    edit(repo, bg, gates=[{"id": "G1", "kind": "blocking", "question": "Fix or drop?", "recommendation": "fix"}])
    code, out = b(repo, "horizon", "--sprint", sp)
    assert "2 wait on backlog.py start" in out and "1 wait on the operator or a trigger" in out, out


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
            "2026-09-29T01:06:40.950000Z 01O+continued output\n"
            "2026-09-29T01:06:41.000000Z 01E ERROR: Job failed: exit code 1\n")


def test_gitlab_com_continuation_forms_give_one_failure_and_fingerprint():
    ts = "2026-09-29T01:06:40.889927Z"
    tid = "_tools/test_a.py::test_x"
    forms = {"first line": "01O ", "spaced continuation": "01O+ ", "real continuation": "01O+"}
    logs = [f"{ts} 00O start\n{ts} {m}FAILED {tid} - x\n" for m in forms.values()]
    assert [backlog.first_failure(x) for x in logs] == [tid] * 3
    assert len({backlog.failure_fingerprint("kb-tests-windows", backlog.first_failure(x)) for x in logs}) == 1
    # the error-line fallback reads the three forms alike
    errs = [f"{ts} {m}ERROR: Job failed: exit code 1\n" for m in ("01E ", "01E+ ", "01E+")]
    assert {backlog.first_failure(x) for x in errs} == {"ERROR: Job failed: exit code <n>"}
    assert len({backlog.failure_fingerprint("kb-tests", backlog.first_failure(x)) for x in errs}) == 1
    # a marker glued to text without a + is no marker: the id is not read from it
    assert backlog.first_failure(f"{ts} 01OFAILED {tid} - x\n") != tid
    # the fixture carries both continuation forms and still reads its failing id
    assert "01O+continued" in _gitlab_com_log(tid) and "01O+ continued" in _gitlab_com_log(tid)
    assert backlog.first_failure(_gitlab_com_log(tid)) == tid


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
