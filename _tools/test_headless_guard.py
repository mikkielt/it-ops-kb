"""kb_hook.py's PreToolUse guard of a headless sprint run (KB_HEADLESS_RUNNER): an Edit or Write of the settings, the
hooks, the plugin, or of an item file's gate answer or by field is denied; every other call, and every call of the
operator-present session (no variable), passes. The hook runs as Claude Code runs it: a process reading the event."""
import json, os, subprocess, sys
from pathlib import Path

import pytest

from conftest import TOOLS

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


@pytest.mark.parametrize("path", ["kb/public/x.md", "_tools/tests.py", "_tools/test_headless_guard.py",
                                  ".claude/worktrees/w1/kb/public/x.md", "_cache/x.json", "x.txt"])
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
