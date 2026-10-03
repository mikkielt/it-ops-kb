"""The kb-autopilot tick's step 3 names the runner cause `timeout` and handles it like `error`.

The skill is instructions a model follows, so the test reads its text. The helper `timeout_problems` returns what is
wrong with a text; the planted texts are strings here, never the skill, and the same helper refuses them.
"""
from pathlib import Path

import pytest

from conftest import KB

SKILL = Path(KB) / ".claude" / "skills" / "kb-autopilot" / "SKILL.md"
CAUSES = ("sprint-done", "landed-limit", "compaction", "blocked", "error")


def cause_lines(text):
    """The bullet lines of step 3 that open with a runner cause, each cut before its first colon."""
    out = []
    for ln in text.splitlines():
        head = ln.split(":")[0]
        if ln.lstrip().startswith("- `") and any(f"`{c}`" in head for c in CAUSES + ("timeout",)):
            out.append(ln)
    return out


def timeout_problems(text):
    """What a skill text lacks of the `timeout` cause in step 3, one line each."""
    out = []
    lines = [ln for ln in cause_lines(text) if "`timeout`" in ln.split(":")[0]]
    if not lines:
        return ["no step 3 line lists the cause `timeout`"]
    line = lines[0]
    for need in ("`error`", "stderr", "second", "digest", "--max-turns"):
        if need not in line:
            out.append(f"the `timeout` line lacks {need}")
    return out


def test_autopilot_skill_names_timeout():
    text = SKILL.read_text(encoding="utf-8")
    assert timeout_problems(text) == []
    assert all(any(f"`{c}`" in ln.split(":")[0] for ln in cause_lines(text)) for c in CAUSES)


GOOD = ("   - `sprint-done`: review.\n"
        "   - `landed-limit`, `compaction`: work remains.\n"
        "   - `blocked`: a gate.\n"
        "   - `error`, `timeout` (a child that hits `--max-turns` ends as cause `error`): read the newest stderr; "
        "a second `error` or `timeout` in a row is not started again: name it in the digest.\n")


@pytest.mark.parametrize("plant, want", [
    (GOOD, None),
    (GOOD.replace("`error`, `timeout`", "`error`"), "no step 3 line lists the cause `timeout`"),
    (GOOD.replace("`--max-turns`", "the turn limit"), "lacks --max-turns"),
    (GOOD.replace("read the newest stderr; ", ""), "lacks stderr"),
    (GOOD.replace("a second ", "a "), "lacks second"),
    (GOOD.replace("name it in the digest", "say nothing"), "lacks digest"),
    (GOOD.replace("`error`", "`failure`"), "lacks `error`"),
])
def test_autopilot_skill_names_timeout_planted_failures(plant, want):
    problems = timeout_problems(plant)
    if want is None:
        assert problems == []
    else:
        assert any(want in p for p in problems), problems


def test_autopilot_skill_names_timeout_planted_skill_copy():
    """A copy of the skill text without the `timeout` mention fails the same helper."""
    text = SKILL.read_text(encoding="utf-8")
    stripped = text.replace("`error`, `timeout` (", "`error` (")
    assert stripped != text
    assert timeout_problems(stripped)
