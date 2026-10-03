"""kb_hook.py's PreToolUse guard of a headless sprint run (KB_HEADLESS_RUNNER): an Edit or Write of the settings, the
hooks, the plugin, or of an item file's gate answer or by field is denied; every other call, and every call of the
operator-present session (no variable), passes. The hook runs as Claude Code runs it: a process reading the event."""
import json, os, subprocess, sys
from pathlib import Path

import pytest

from conftest import TOOLS
import backlog
import bl_testkit
from bl_testkit import b, edit, item, item_json

bl_testkit.bind(backlog)
repo = bl_testkit.repo  # the kit's throwaway git repository fixture, bound by name (an import would shadow the argument)

ITEM = {"id": "ST-aaaaaaaa", "kind": "story", "title": "t", "gates": [
    {"id": "g1", "kind": "blocking", "question": "q?", "options": ["a", "b"], "recommendation": "a"}]}


@pytest.fixture
def project(tmp_path):
    item = tmp_path / "kb" / "_self" / "backlog" / "ST-aaaaaaaa.json"
    item.parent.mkdir(parents=True)
    item.write_text(json.dumps(ITEM, indent=2) + "\n", encoding="utf-8")
    return tmp_path


def hook(project, tool, tool_input, headless=True):
    """The hook's answer (parsed) for one PreToolUse event, run as a process; None when it prints nothing."""
    env = {k: v for k, v in os.environ.items() if k != "KB_HEADLESS_RUNNER"}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    if headless:
        env["KB_HEADLESS_RUNNER"] = "1"
    ev = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    p = subprocess.run([sys.executable, str(Path(TOOLS, "kb_hook.py"))], input=json.dumps(ev), capture_output=True,
                       text=True, encoding="utf-8", env=env, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def denied(out):
    return bool(out) and out["hookSpecificOutput"].get("permissionDecision") == "deny"


def answered(answer="a", by="operator"):
    gates = [{**ITEM["gates"][0], "answer": answer, "by": by}]
    return json.dumps({**ITEM, "gates": gates}, indent=2) + "\n"


ITEM_PATH = "kb/_self/backlog/ST-aaaaaaaa.json"
GUARDED_CALLS = [
    ("Write", {"file_path": ".claude/settings.json", "content": "{}"}),
    ("Edit", {"file_path": ".claude/settings.local.json", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": ".claude/hooks/x.py", "content": ""}),
    ("Edit", {"file_path": ".claude-plugin/plugin.json", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": ITEM_PATH, "content": answered()}),
    ("Edit", {"file_path": ITEM_PATH, "old_string": '"recommendation": "a"',
              "new_string": '"recommendation": "a",\n      "answer": "a",\n      "by": "operator"'}),
    ("MultiEdit", {"file_path": ITEM_PATH, "edits": [{"old_string": "t", "new_string": "u"},
                                                     {"old_string": '"q?"', "new_string": '"q?", "by": "operator"'}]}),
    ("Write", {"file_path": ITEM_PATH, "content": "not json"}),
]


@pytest.mark.parametrize("tool, tool_input", GUARDED_CALLS, ids=[f"{t}-{i}" for i, (t, _) in enumerate(GUARDED_CALLS)])
def test_headless_pretooluse_guard_denies(project, tool, tool_input):
    out = hook(project, tool, tool_input)
    assert denied(out) and "headless run" in out["hookSpecificOutput"]["permissionDecisionReason"], out


@pytest.mark.parametrize("tool, tool_input", GUARDED_CALLS, ids=[f"{t}-{i}" for i, (t, _) in enumerate(GUARDED_CALLS)])
def test_headless_pretooluse_guard_operator_session_unaffected(project, tool, tool_input):
    assert hook(project, tool, tool_input, headless=False) is None  # the planted contrast: no variable, no guard


@pytest.mark.parametrize("tool, tool_input", [
    ("Write", {"file_path": "_tools/x.py", "content": "print(1)\n"}),
    ("Edit", {"file_path": ITEM_PATH, "old_string": '"title": "t"', "new_string": '"title": "u"'}),
    ("Write", {"file_path": ITEM_PATH, "content": json.dumps({**ITEM, "title": "u"})}),  # gates as they were
    ("Write", {"file_path": "kb/_self/backlog/ST-bbbbbbbb.json", "content": json.dumps({**ITEM, "id": "ST-bbbbbbbb"})}),
    ("Read", {"file_path": ".claude/settings.json"}),
])
def test_headless_pretooluse_guard_lets_other_calls_through(project, tool, tool_input):
    assert not denied(hook(project, tool, tool_input))


def test_headless_pretooluse_guard_is_registered_for_the_write_tools():
    pre = json.loads(Path(TOOLS).parent.joinpath(".claude", "settings.json").read_text("utf-8"))["hooks"]["PreToolUse"]
    groups = [g for g in pre if any("_tools/kb_hook.py" in h.get("command", "") for h in g.get("hooks", []))]
    matched = {t for g in groups for t in (g.get("matcher") or "").split("|")}
    assert {"Edit", "Write", "MultiEdit", "NotebookEdit"} <= matched, matched


# The review's gaps: a value-only edit of a gate, a path outside the project, the guard's own files.
@pytest.fixture
def guard(project, monkeypatch):
    """kb_hook.headless_guard run in process as a headless run of PROJECT; returns the guard's answer for one call."""
    for var in ("KB_TESTS_FAST", "KB_TEST_WORKERS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(project / "lock"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setenv("KB_HEADLESS_RUNNER", "1")
    monkeypatch.syspath_prepend(str(TOOLS))
    import kb_hook

    def run(tool, tool_input):
        return kb_hook.headless_guard({"tool_name": tool, "tool_input": tool_input})
    return run


def answered_item(project, by="agent"):
    (project / ITEM_PATH).write_text(answered(by=by), encoding="utf-8")


def test_headless_pretooluse_guard_review_value_only_edit_is_denied(project, guard):
    answered_item(project)
    out = guard("Edit", {"file_path": ITEM_PATH, "old_string": ': "agent"', "new_string": ': "operator"'})
    assert denied(out), out  # the planted failure: neither key is named in the edit, only a value changes
    out = guard("Edit", {"file_path": str(project / ITEM_PATH), "old_string": '"a"', "new_string": '"b"',
                         "replace_all": True})
    assert denied(out), out  # an answer changed through replace_all, by an absolute path


def test_headless_pretooluse_guard_review_multiedit_ending_in_a_changed_by_is_denied(project, guard):
    answered_item(project)
    out = guard("MultiEdit", {"file_path": ITEM_PATH, "edits": [
        {"old_string": '"agent"', "new_string": '"x"'}, {"old_string": '"x"', "new_string": '"agent"'}]})
    assert not denied(out), out  # ends where it began: gates unchanged
    out = guard("MultiEdit", {"file_path": ITEM_PATH, "edits": [
        {"old_string": '"agent"', "new_string": '"x"'}, {"old_string": '"x"', "new_string": '"operator"'}]})
    assert denied(out), out


def test_headless_pretooluse_guard_review_harmless_edit_of_another_field_passes(project, guard):
    answered_item(project)
    out = guard("Edit", {"file_path": ITEM_PATH, "old_string": '"title": "t"', "new_string": '"title": "u"'})
    assert not denied(out), out


@pytest.mark.parametrize("tool_input", [
    {"old_string": "no such text", "new_string": "x"},  # absent
    {"old_string": '"id"', "new_string": '"ident"'},  # ambiguous: the item and its gate both have an id
    {"old_string": "", "new_string": "x"},
])
def test_headless_pretooluse_guard_review_edit_that_cannot_apply_is_denied(project, guard, tool_input):
    answered_item(project)
    assert denied(guard("Edit", {"file_path": ITEM_PATH, **tool_input}))


def test_headless_pretooluse_guard_review_edit_of_a_missing_item_file_is_denied(guard):
    out = guard("Edit", {"file_path": "kb/_self/backlog/ST-cccccccc.json", "old_string": "a", "new_string": "b"})
    assert denied(out), out


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_headless_pretooluse_guard_review_path_outside_the_project_is_denied(project, guard, tool):
    away = project.parent / "outside-x"
    away.mkdir(exist_ok=True)
    (project / "link").symlink_to(away, target_is_directory=True)
    for path in ("/tmp/x", str(away / "x"), "../x", "kb/../../x", "link/x"):
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        tool_input = {key: path, "content": "x", "old_string": "a", "new_string": "b",
                      "edits": [{"old_string": "a", "new_string": "b"}], "new_source": "x"}
        assert denied(guard(tool, tool_input)), (tool, path)


@pytest.mark.parametrize("path", [
    "_tools/kb_hook.py", "_tools/kbpy", ".githooks/commit-msg", ".githooks/pre-push", "_tools/backlog.py",
    "_tools/kbgit.py", "_tools/kbpublic.py", "_tools/kg_x.py", ".gitlab-ci.yml", ".github/workflows/x.yml", "AGENTS.md",
    "_tools/bl_authority.py", "_tools/_TOOLS/../KB_HOOK.PY", ".claude/worktrees/w1/_tools/kb_hook.py",
])
def test_headless_pretooluse_guard_review_guard_files_are_denied(project, guard, path):
    for tool, tool_input in (("Write", {"file_path": path, "content": "x"}),
                             ("Edit", {"file_path": path, "old_string": "a", "new_string": "b"})):
        assert denied(guard(tool, tool_input)), (tool, path)


@pytest.mark.parametrize("path", ["kb/public/x.md", "_tools/kbusage.py", ".claude/worktrees/w1/kb/public/x.md", "_cache/x.json", "x.txt"])
def test_headless_pretooluse_guard_review_ordinary_project_files_are_allowed(project, guard, path):
    assert guard("Write", {"file_path": path, "content": "x"}) is None


def test_headless_pretooluse_guard_review_without_the_variable_nothing_is_answered(project, guard, monkeypatch):
    monkeypatch.delenv("KB_HEADLESS_RUNNER")
    answered_item(project)
    for path in ("/tmp/x", "_tools/kb_hook.py", ".githooks/commit-msg", ITEM_PATH):
        assert guard("Edit", {"file_path": path, "old_string": ': "agent"', "new_string": ': "operator"'}) is None


def test_headless_pretooluse_guard_review_a_guard_that_cannot_load_denies(project, guard, monkeypatch):
    monkeypatch.setitem(sys.modules, "bl_authority", None)  # import raises
    assert denied(guard("Write", {"file_path": "kb/public/x.md", "content": "x"}))


# The re-review's gaps: an item path in another case or under (nested) worktree prefixes, a duplicate gate id.
def start_gate(**kw):
    return {"id": "start", "kind": "blocking", "question": "q?", "options": ["approve", "reject"], **kw}


def item_with(gates):
    return json.dumps({**ITEM, "gates": gates}, indent=2) + "\n"


def test_headless_guard_case_dup_worktree_upper_case_item_path_value_only_change_is_denied(project, guard):
    answered_item(project)
    change = {"old_string": ': "agent"', "new_string": ': "operator"'}
    for path in ("kb/_self/BACKLOG/ST-aaaaaaaa.json", "KB/_SELF/backlog/ST-AAAAAAAA.JSON", "kb/_self/Backlog/x.json",
                 str(project / "kb" / "_self" / "BACKLOG" / "ST-aaaaaaaa.json")):
        assert denied(guard("Edit", {"file_path": path, **change})), path
    out = guard("Write", {"file_path": "kb/_self/BACKLOG/ST-aaaaaaaa.json", "content": answered(by="operator")})
    assert denied(out), out
    out = guard("Edit", {"file_path": "kb/_self/BACKLOG/ST-aaaaaaaa.json", "old_string": '"title": "t"',
                         "new_string": '"title": "u"'})
    assert not denied(out), out  # the same file, another field: allowed as in lower case


@pytest.mark.parametrize("path", [
    ".CLAUDE/Settings.JSON", ".claude/HOOKS/x.py", ".Claude-Plugin/plugin.json", "_TOOLS/KB_HOOK.py",
    ".claude/worktrees/a/.claude/worktrees/b/_tools/kb_hook.py", ".claude/worktrees/a/.claude/settings.json",
    ".claude/worktrees/a/.claude/worktrees/b/.claude/hooks/x.py",
])
def test_headless_guard_case_dup_worktree_settings_and_guard_paths_in_other_spellings_are_denied(project, guard, path):
    assert denied(guard("Write", {"file_path": path, "content": "x"})), path


def test_headless_guard_case_dup_worktree_nested_worktree_item_path_is_denied(project, guard):
    for prefix in (".claude/worktrees/a/", ".claude/worktrees/a/.claude/worktrees/b/",
                   ".claude/worktrees/a/.claude/worktrees/b/.claude/worktrees/c/", ".CLAUDE/Worktrees/a/"):
        path = prefix + "kb/_self/backlog/ST-aaaaaaaa.json"
        out = guard("Write", {"file_path": path, "content": answered(by="operator")})
        assert denied(out), path
        wt = project / prefix / "kb" / "_self" / "backlog"
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "ST-aaaaaaaa.json").write_text(answered(by="agent"), encoding="utf-8")
        out = guard("Edit", {"file_path": path, "old_string": ': "agent"', "new_string": ': "operator"'})
        assert denied(out), path  # a value-only change of the worktree's own copy


@pytest.mark.parametrize("path", [
    "./kb/_self/BACKLOG/ST-aaaaaaaa.json", "kb//_self///BACKLOG/ST-aaaaaaaa.json", "kb\\_self\\BACKLOG\\ST-aaaaaaaa.json",
    "kb/public/../_self/BACKLOG/ST-aaaaaaaa.json", ".claude/worktrees/a/./kb/_self/backlog//ST-aaaaaaaa.json",
    ".claude/worktrees/a/../b/kb/_self/backlog/ST-aaaaaaaa.json",
    ".\\.claude\\worktrees\\a\\kb\\_self\\backlog\\ST-aaaaaaaa.json",
])
def test_headless_guard_case_dup_worktree_dots_slashes_and_backslashes_in_a_path_are_tolerated(project, guard, path):
    assert denied(guard("Write", {"file_path": path, "content": answered(by="operator")})), path


def test_headless_guard_case_dup_worktree_duplicate_start_gate_is_denied_by_write_and_edit(project, guard):
    (project / ITEM_PATH).write_text(item_with([start_gate()]), encoding="utf-8")
    prepended = item_with([start_gate(answer="approve", by="operator"), start_gate()])
    out = guard("Write", {"file_path": ITEM_PATH, "content": prepended})
    assert denied(out) and "more than once" in json.dumps(out), out
    assert denied(guard("Write", {"file_path": ITEM_PATH, "content": item_with([start_gate(), start_gate()])}))
    assert denied(guard("Write", {"file_path": ITEM_PATH, "content": item_with([start_gate(), start_gate(id="g2"),
                                                                                start_gate()])}))
    assert not denied(guard("Write", {"file_path": ITEM_PATH, "content": item_with([start_gate(), start_gate(id="g2")])}))
    # an Edit whose result repeats the id, naming neither answer nor by
    extra = json.dumps(start_gate(), indent=2).replace("\n", "\n    ")
    out = guard("Edit", {"file_path": ITEM_PATH, "old_string": '"gates": [', "new_string": '"gates": [\n    ' + extra + ","})
    assert denied(out) and "more than once" in json.dumps(out), out
    out = guard("MultiEdit", {"file_path": ITEM_PATH, "edits": [
        {"old_string": '"title": "t"', "new_string": '"title": "u"'},
        {"old_string": '"gates": [', "new_string": '"gates": [\n    ' + extra + ","}]})
    assert denied(out), out
    out = guard("Edit", {"file_path": ITEM_PATH, "old_string": '"title": "t"', "new_string": '"title": "u"'})
    assert not denied(out), out  # a gate id used once: an unrelated edit stays allowed


def test_headless_guard_case_dup_worktree_an_existing_duplicate_is_not_waved_through_by_an_unrelated_edit(project, guard):
    (project / ITEM_PATH).write_text(item_with([start_gate(), start_gate()]), encoding="utf-8")
    out = guard("Edit", {"file_path": ITEM_PATH, "old_string": '"title": "t"', "new_string": '"title": "u"'})
    assert denied(out), out


def test_headless_guard_case_dup_worktree_ordinary_in_project_writes_are_allowed(project, guard):
    for path in ("kb/public/x.md", "_tools/kbusage.py", "kb/_self/BACKLOG-notes.md", ".claude/worktrees/a/.claude/worktrees/b/x.md",
                 "kb/_self/backlog/sub/x.txt", "KB/Public/X.md", "x\\y.txt"):
        assert guard("Write", {"file_path": path, "content": "x"}) is None, path


def test_headless_guard_case_dup_worktree_without_the_variable_nothing_is_answered(project, guard, monkeypatch):
    monkeypatch.delenv("KB_HEADLESS_RUNNER")
    for path in ("kb/_self/BACKLOG/ST-aaaaaaaa.json", ".claude/worktrees/a/.claude/worktrees/b/_tools/kb_hook.py"):
        assert guard("Write", {"file_path": path, "content": item_with([start_gate(), start_gate()])}) is None


def test_headless_guard_case_dup_worktree_check_refuses_an_item_with_a_duplicate_gate_id(repo):
    """The planted item: a prepended answered gate before the real unanswered one; check names the item and the id."""
    assert b(repo, "new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    ep = item(repo, "Epic")["id"]
    code, out = b(repo, "gate", "add", ep, "--kind", "blocking", "--question", "go?", "--option", "a", "--option", "b",
                  "--recommendation", "a")
    assert code == 0, out
    gate = item_json(repo, ep)["gates"][0]
    assert b(repo, "check")[0] == 0
    edit(repo, ep, gates=[{**gate, "answer": "a", "by": "operator"}, gate])
    code, out = b(repo, "check")
    assert code == 1 and ep in out and f"gate id {gate['id']!r} is repeated" in out, out
    edit(repo, ep, gates=[gate])
    assert b(repo, "check")[0] == 0


# The test runner's code: a headless run plants nothing tests.py would run (the bl_ modules, tests.py, conftest.py, a
# new test file). An existing _tools/test_*.py file stays editable, as before.
RUNNER_PATHS = ["_tools/bl_cost.py", "_tools/bl_authority.py", "_tools/bl_x.py", "_tools/tests.py", "_tools/conftest.py"]
# the path as written, with ./, with .. in it, with backslashes, in upper case
RUNNER_SPELLINGS = [lambda p: p, lambda p: "./" + p, lambda p: "_tools/../" + p, lambda p: p.replace("/", "\\"),
                    lambda p: p.upper()]


@pytest.fixture
def runner(project, monkeypatch):
    """The guard run in process as a headless run of PROJECT, which holds _tools/ with one existing test file."""
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(project / "lock"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setenv("KB_HEADLESS_RUNNER", "1")
    monkeypatch.syspath_prepend(str(TOOLS))
    (project / "_tools").mkdir()
    (project / "_tools" / "test_old.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    import kb_hook

    def run(tool, tool_input, headless=True):
        if not headless:
            monkeypatch.delenv("KB_HEADLESS_RUNNER")
        return kb_hook.headless_guard({"tool_name": tool, "tool_input": tool_input})
    return run


@pytest.mark.parametrize("path", RUNNER_PATHS)
@pytest.mark.parametrize("i", range(5))
@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_headless_guard_test_runner_code_is_denied_in_every_spelling(runner, tool, i, path):
    p = RUNNER_SPELLINGS[i](path)
    ti = {"file_path": p, "content": "x"} if tool == "Write" else {"file_path": p, "old_string": "a", "new_string": "b"} \
        if tool == "Edit" else {"file_path": p, "edits": [{"old_string": "a", "new_string": "b"}]}
    out = runner(tool, ti)
    assert denied(out), (p, out)
    assert path.split("/")[-1].lower() in out["hookSpecificOutput"]["permissionDecisionReason"].lower()
    assert runner(tool, ti, headless=False) is None  # the contrast: the operator-present session


@pytest.mark.parametrize("tool, ti", [
    ("Write", {"file_path": "_tools/test_new.py", "content": "import os\n"}),
    ("Edit", {"file_path": "_tools/test_new.py", "old_string": "", "new_string": "import os\n"}),
    ("Write", {"file_path": "./_tools/../_tools/TEST_new.py", "content": "x"}),
    ("Write", {"file_path": "_tools\\test_new.py", "content": "x"}),
])
def test_headless_guard_test_runner_new_test_file_is_denied(runner, tool, ti):
    out = runner(tool, ti)
    assert denied(out) and "new test file" in out["hookSpecificOutput"]["permissionDecisionReason"], out
    assert runner(tool, ti, headless=False) is None


@pytest.mark.parametrize("tool, ti", [
    ("Edit", {"file_path": "_tools/test_old.py", "old_string": "pass", "new_string": "assert 1"}),  # exists: allowed
    ("Write", {"file_path": "_tools/test_old.py", "content": "x"}),
    ("Write", {"file_path": "kb/test_x.py", "content": "x"}),  # not in _tools/
    ("Write", {"file_path": "_tools/helper_test.py", "content": "x"}),
    ("Write", {"file_path": "_tools/blame.py", "content": "x"}),  # no bl_ prefix
    ("Write", {"file_path": "docs/tests.py.md", "content": "x"}),
    ("Write", {"file_path": "docs/conftest.py", "content": "x"}),
    ("Write", {"file_path": "kb/public/bl_notes.md", "content": "x"}),
])
def test_headless_guard_test_runner_other_paths_are_not_over_matched(runner, tool, ti):
    assert not denied(runner(tool, ti))


@pytest.fixture
def clone(tmp_path):
    """(the runner's project, its clone): <clone>/.claude/worktrees/runner-SP-xxxxxxxx, a runner's worktree."""
    run = tmp_path / "clone-x" / ".claude" / "worktrees" / "runner-SP-xxxxxxxx"
    run.mkdir(parents=True)
    return run, run.parent.parent.parent


def worker_write(run, path):
    return hook(run, "Write", {"file_path": str(path), "content": "x"})


@pytest.mark.parametrize("rel", ["kb/_self/reports/t.md", "x.txt", "_tools/kbusage.py", ".claude/worktrees/n1/kb/public/x.md"])
def test_headless_guard_worker_worktree_sibling_agent_write_is_allowed(clone, rel):
    run, root = clone
    assert worker_write(run, root / ".claude" / "worktrees" / "agent-a1" / rel) is None


def test_headless_guard_worker_worktree_sibling_agent_write_in_other_case_is_allowed(clone):
    run, root = clone
    assert worker_write(run, root / ".claude" / "worktrees" / "Agent-A1" / "x.txt") is None


def test_headless_guard_worker_worktree_another_clone_is_denied(clone, tmp_path):
    run, root = clone
    other = tmp_path / "clone-y" / ".claude" / "worktrees" / "agent-a1"
    other.mkdir(parents=True)
    assert denied(worker_write(run, other / "x.txt"))
    assert denied(worker_write(run, tmp_path / "clone-y" / "x.txt"))
    assert denied(worker_write(run, root / "x.txt"))  # the clone root itself is not the project


@pytest.mark.parametrize("rel", ["../x.txt", "../../x.txt", "../../../../x.txt", "kb/../../x.txt", "../agent-a1/../../x.txt"])
def test_headless_guard_worker_worktree_dotdot_escape_is_denied(clone, rel):
    run, root = clone
    agent = root / ".claude" / "worktrees" / "agent-a1"
    agent.mkdir()
    assert denied(worker_write(run, str(agent) + "/" + rel)), rel


def test_headless_guard_worker_worktree_symlink_escape_is_denied(clone, tmp_path):
    run, root = clone
    away = tmp_path / "away"
    away.mkdir()
    agent = root / ".claude" / "worktrees" / "agent-a1"
    agent.mkdir()
    (agent / "link").symlink_to(away, target_is_directory=True)
    (root / ".claude" / "worktrees" / "agent-a2").symlink_to(away, target_is_directory=True)
    assert denied(worker_write(run, agent / "link" / "x.txt"))
    assert denied(worker_write(run, root / ".claude" / "worktrees" / "agent-a2" / "x.txt"))


@pytest.mark.parametrize("rel", [
    "_tools/kb_hook.py", ".claude/settings.json", ".claude/settings.local.json", ".claude/hooks/x.py", ".claude-plugin/plugin.json",
    "_tools/bl_land.py", "_tools/tests.py", "_tools/conftest.py", "_tools/test_new_thing.py", "AGENTS.md",
    "_TOOLS/KB_HOOK.PY", ".claude/worktrees/n1/_tools/kb_hook.py",
])
def test_headless_guard_worker_worktree_guard_files_inside_it_are_denied(clone, rel):
    run, root = clone
    assert denied(worker_write(run, root / ".claude" / "worktrees" / "agent-a1" / rel)), rel


def test_headless_guard_worker_worktree_item_gate_change_inside_it_is_denied(clone):
    run, root = clone
    path = root / ".claude" / "worktrees" / "agent-a1" / ITEM_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(ITEM, indent=2) + "\n", encoding="utf-8")
    assert denied(hook(run, "Write", {"file_path": str(path), "content": answered()}))
    assert hook(run, "Write", {"file_path": str(path), "content": json.dumps({**ITEM, "title": "u"})}) is None


@pytest.mark.parametrize("name", ["worker-a1", "runner-SP-yyyyyyyy", "agent", "agent-", "agents-a1", "xagent-a1", "a1"])
def test_headless_guard_worker_worktree_sibling_not_named_agent_is_denied(clone, name):
    run, root = clone
    assert denied(worker_write(run, root / ".claude" / "worktrees" / name / "x.txt")), name


def test_headless_guard_worker_worktree_deeper_or_elsewhere_agent_dir_is_denied(clone, tmp_path):
    run, root = clone
    assert denied(worker_write(run, root / ".claude" / "worktrees" / "n1" / "agent-a1" / "x.txt"))
    assert denied(worker_write(run, root / ".claude" / "agent-a1" / "x.txt"))
    assert denied(worker_write(run, root / "agent-a1" / "x.txt"))
    assert denied(worker_write(run, root / ".claude" / "worktrees" / "agent-a1"))  # the worktree itself, no file


def test_headless_guard_worker_worktree_plain_project_sibling_is_not_newly_allowed(tmp_path):
    proj = tmp_path / "clone-x" / ".claude" / "worktrees" / "w1"  # not runner-*
    proj.mkdir(parents=True)
    assert denied(worker_write(proj, proj.parent / "agent-a1" / "x.txt"))
    plain = tmp_path / "plain"
    plain.mkdir()
    assert denied(worker_write(plain, tmp_path / "agent-a1" / "x.txt"))
    assert denied(worker_write(plain, plain.parent / ".claude" / "worktrees" / "agent-a1" / "x.txt"))
    nodir = tmp_path / "clone-z" / "worktrees" / "runner-SP-xxxxxxxx"  # not under .claude/
    nodir.mkdir(parents=True)
    assert denied(worker_write(nodir, nodir.parent / "agent-a1" / "x.txt"))


def test_headless_guard_worker_worktree_without_the_variable_nothing_is_answered(clone):
    run, root = clone
    assert hook(run, "Write", {"file_path": str(root / "x.txt"), "content": "x"}, headless=False) is None
