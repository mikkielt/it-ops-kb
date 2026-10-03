"""A gate about the code that guards the autopilot (its runner, gate classes, bounds, self-check, edit guard, decision
record, lane routing, sync, the local settings) is of a class the autopilot may not answer as design, and so is a gate
whose question speaks of uploading, deploying, merge requests, GitLab, PATs, ssh, passphrases or bearer tokens: with
Edit, Write and glab mr merge allowed, an unattended sprint could otherwise approve and merge changes to its own guards
(kb/_self/backlog.md, Classes and the autopilot)."""
import pytest

import bl_authority as a

GUARD_PATHS = {
    "_tools/autopilot.py": "agents-rule", "_tools/bl_authority.py": "agents-rule", "_tools/bl_bounds.py": "agents-rule",
    "_tools/bl_selfcheck.py": "agents-rule", "_tools/kb_hook.py": "agents-rule", "_tools/kbdecide.py": "agents-rule",
    ".claude/settings.local.json": "agents-rule", "_tools/kblane.py": "push", "_tools/kg_sync.py": "push",
}
WORDINGS = {
    "Upload the commits to the git host?": "push", "Open a merge request to main?": "push", "Deploy this?": "push",
    "Sync to gitlab?": "push", "Use a PAT for the bot?": "secrets", "Change the ssh keys?": "secrets",
    "What passphrase do we use?": "secrets", "Send it with a bearer header?": "secrets",
}


def gate(question="Which layout?"):
    return {"id": "g", "question": question, "options": []}


@pytest.mark.parametrize("path, cls", GUARD_PATHS.items())
def test_gate_class_covers_the_guard_code(path, cls):
    assert a.derived_class({"touches": [path]}, gate()) == cls
    assert a.derived_class({"touches": ["_tools/"]}, gate()) in ("push", "agents-rule")  # a touch above them too


@pytest.mark.parametrize("question, cls", WORDINGS.items())
def test_gate_class_covers_the_guard_code_wordings(question, cls):
    assert a.derived_class({"touches": []}, gate(question)) == cls


@pytest.mark.parametrize("path", sorted(GUARD_PATHS))
def test_gate_class_covers_the_guard_code_planted_missing_path_fails(monkeypatch, path):
    """With the path taken out of PATHS the gate falls to design, which the autopilot may answer: the check above
    refuses that."""
    monkeypatch.setattr(a, "PATHS", {k: tuple(p for p in v if p != path and not (path.startswith(p) and p.endswith("_")))
                                     for k, v in a.PATHS.items()})
    assert a.derived_class({"touches": [path]}, gate()) == "design"


def test_gate_class_covers_the_guard_code_by_a_glob():
    """A glob over the bl_ modules names bl_authority.py, bl_bounds.py and bl_selfcheck.py: agents-rule, closed."""
    assert a.derived_class({"touches": ["_tools/bl_*.py"]}, gate()) == "agents-rule"
    assert a.derived_class({"touches": ["_tools/bl_plan*.py"]}, gate()) == "design"


def test_gate_class_covers_the_guard_code_ordinary_wordings_stay_design():
    for q in ("Which layout for the table?", "Patch the pattern parser?", "Keep the paths as they are?"):
        assert a.derived_class({"touches": ["kb/public/x.md"]}, gate(q)) == "design", q
