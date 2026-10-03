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
