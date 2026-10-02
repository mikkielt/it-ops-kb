"""The kb-autopilot skill files findings through `backlog.py bounds file` and runs `bounds stop` before a refill.

The skill is instructions a model follows, so the test reads its text. The helper `bounds_problems` returns what is
wrong with a text; each planted text is a string here, never the skill, and the same helper refuses it.
"""
import re
from pathlib import Path

import pytest

from conftest import KB

SKILL = Path(KB) /".claude" / "skills" / "kb-autopilot" / "SKILL.md"
PLAIN_NEW = re.compile(r"backlog\.py new (bug|story)\b")
FILING_LINE = re.compile(r"review|retro|intake|refill", re.IGNORECASE)


def bounds_problems(text):
    """What a skill text lacks of the bounded filing and refill, one line each."""
    out = []
    for phrase in ("bounds file", "bounds stop", "bounds file --origin review", "bounds file --origin retro"):
        if phrase not in text:
            out.append(f"missing `{phrase}`")
    for n, line in enumerate(text.splitlines(), 1):
        if FILING_LINE.search(line) and PLAIN_NEW.search(line):
            out.append(f"line {n} files with the plain `backlog.py new` form")
    return out


def test_autopilot_tick_files_through_bounds():
    assert bounds_problems(SKILL.read_text(encoding="utf-8")) == []


GOOD = ("1. review: `backlog.py bounds file --origin review --kind bug`\n"
        "2. retro: `backlog.py bounds file --origin retro`\n5. refill: `backlog.py bounds stop --sprint SP`\n")


@pytest.mark.parametrize("plant, want", [
    (GOOD, None),
    (GOOD.replace("bounds stop", "status"), "missing `bounds stop`"),
    (GOOD.replace("--origin retro", "--origin review"), "missing `bounds file --origin retro`"),
    (GOOD + "a review gap: `python3 _tools/backlog.py new bug --title T`\n", "plain `backlog.py new`"),
    (GOOD + "each retro story: `python3 _tools/backlog.py new story --title T`\n", "plain `backlog.py new`"),
])
def test_autopilot_tick_files_through_bounds_planted_failures(plant, want):
    problems = bounds_problems(plant)
    if want is None:
        assert problems == []
    else:
        assert any(want in p for p in problems), problems
