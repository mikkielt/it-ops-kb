"""The kb-sprint close step 5 (Clean up) names the closed sprint's worker leftovers that close removes, never with
`--force`, and none of the retired autopilot runner's (a runner-<SP> worktree, an orch/<SP> branch, _cache/autopilot).

The skill is instructions a model follows, so the test reads its text. `cleanup_problems` returns what is wrong
with a text; the planted texts are strings here, never the skill, and the same helper refuses them.
"""
from pathlib import Path

import pytest

from conftest import KB

SKILL = Path(KB) / ".claude" / "skills" / "kb-sprint" / "SKILL.md"
NEEDS = ("`agent-*`", "`worktree-agent-*`", "git branch -d")
RETIRED = ("runner-", "orch/", "_cache/autopilot", "runner's")  # the retired autopilot runner's leftovers


def clean_up_section(text):
    """The text of step 5, from its `**Clean up**` mark to the next heading."""
    if "**Clean up**" not in text:
        return ""
    rest = text[text.index("**Clean up**"):]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def cleanup_problems(text):
    """What is wrong with the Clean up step, one line each: a worker leftover it does not name, a retired runner
    leftover it still names, a line that allows --force."""
    sec = clean_up_section(text)
    if not sec:
        return ["no Clean up step"]
    out = [f"the Clean up step does not name {n}" for n in NEEDS if n not in sec]
    out += [f"the Clean up step names the retired {n}" for n in RETIRED if n in sec]
    for ln in sec.splitlines():
        if "--force" in ln and "never" not in ln.lower():
            out.append(f"a line allows --force: {ln.strip()[:60]}")
    if "--force" not in sec:
        out.append("the Clean up step does not say never --force")
    return out


def test_kb_sprint_close_cleans_worker_leftovers():
    assert cleanup_problems(SKILL.read_text(encoding="utf-8")) == []


GOOD = ("5. **Clean up** once pushed, never with `--force`.\n"
        "   1. a detached `agent-*` worktree and a `worktree-agent-*` branch with no commit: `git branch -d <branch>`.\n"
        "## Next\n")


@pytest.mark.parametrize("plant, want", [
    (GOOD, None),
    (GOOD.replace("`agent-*` worktree and a ", ""), "`agent-*`"),
    (GOOD.replace("`worktree-agent-*` branch", "branch"), "`worktree-agent-*`"),
    (GOOD.replace("`git branch -d <branch>`", "delete it"), "git branch -d"),
    (GOOD.replace(".\n   1.", "; `git worktree remove .claude/worktrees/runner-<SP>`.\n   1."), "retired runner-"),
    (GOOD.replace(".\n   1.", "; `git branch -d orch/<SP>`.\n   1."), "retired orch/"),
    (GOOD.replace(".\n   1.", "; `rm -r _cache/autopilot/<SP>`.\n   1."), "retired _cache/autopilot"),
    (GOOD.replace(", never with `--force`", ""), "never --force"),
    (GOOD.replace(", never with `--force`", "").replace("`git branch -d", "`git branch -D --force"), "allows --force"),
    ("no step", "no Clean up step"),
])
def test_kb_sprint_close_cleans_worker_leftovers_planted_failures(plant, want):
    problems = cleanup_problems(plant)
    if want is None:
        assert problems == []
    else:
        assert any(want in p for p in problems), problems
