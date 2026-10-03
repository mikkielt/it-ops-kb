"""The kb-sprint close step 5 (Clean up) also removes the closed sprint's runner leftovers, never with `--force`.

The skill is instructions a model follows, so the test reads its text. `cleanup_problems` returns what is wrong
with a text; the planted texts are strings here, never the skill, and the same helper refuses them.
"""
from pathlib import Path

import pytest

from conftest import KB

SKILL = Path(KB) / ".claude" / "skills" / "kb-sprint" / "SKILL.md"
NEEDS = (".claude/worktrees/runner-", "orch/", "_cache/autopilot/", "`agent-*`", "`worktree-agent-*`", "git branch -d")


def clean_up_section(text):
    """The text of step 5, from its `**Clean up**` mark to the next heading."""
    if "**Clean up**" not in text:
        return ""
    rest = text[text.index("**Clean up**"):]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def cleanup_problems(text):
    """What the Clean up step lacks of the runner leftovers, one line each."""
    sec = clean_up_section(text)
    if not sec:
        return ["no Clean up step"]
    out = [f"the Clean up step does not name {n}" for n in NEEDS if n not in sec]
    for ln in sec.splitlines():
        if "--force" in ln and "never" not in ln.lower():
            out.append(f"a line allows --force: {ln.strip()[:60]}")
    if "--force" not in sec:
        out.append("the Clean up step does not say never --force")
    return out


def test_kb_sprint_close_cleans_runner_worktree():
    assert cleanup_problems(SKILL.read_text(encoding="utf-8")) == []


GOOD = ("5. **Clean up** once pushed.\n"
        "   1. `git worktree remove .claude/worktrees/runner-<SP>` then `git branch -d orch/<SP>`, never with `--force`;\n"
        "   2. `rm -r _cache/autopilot/<SP>`;\n"
        "   3. a detached `agent-*` worktree and a `worktree-agent-*` branch with no commit: `git branch -d <branch>`.\n"
        "## Next\n")


@pytest.mark.parametrize("plant, want", [
    (GOOD, None),
    (GOOD.replace(".claude/worktrees/runner-<SP>", "the runner worktree"), "runner-"),
    (GOOD.replace("orch/<SP>", "the orch branch"), "orch/"),
    (GOOD.replace("_cache/autopilot/<SP>", "the state dir"), "_cache/autopilot/"),
    (GOOD.replace("`agent-*` worktree and a ", ""), "`agent-*`"),
    (GOOD.replace("`worktree-agent-*` branch", "branch"), "`worktree-agent-*`"),
    (GOOD.replace(", never with `--force`", ""), "never --force"),
    (GOOD.replace("`git worktree remove .claude", "`git worktree remove --force .claude")
        .replace(", never with `--force`", ""), "allows --force"),
    ("5. **Clean up** once pushed.\n## Next\n", "orch/"),
    ("no step", "no Clean up step"),
])
def test_kb_sprint_close_cleans_runner_worktree_planted_failures(plant, want):
    problems = cleanup_problems(plant)
    if want is None:
        assert problems == []
    else:
        assert any(want in p for p in problems), problems
