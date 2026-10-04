"""The kb-autopilot skill lets a tick be limited to named sprints with `--only`.

The skill is instructions a model follows, so the test reads its text. The helper `only_problems` returns what a
text lacks of the limited tick; each planted text is a string here, never the skill, and the same helper refuses it.
"""
import re
from pathlib import Path

import pytest

from conftest import KB

SKILL = Path(KB) / ".claude" / "skills" / "kb-autopilot" / "SKILL.md"
RULES = (
    ("--only SP[,SP]", "the argument-hint or the paragraph does not name `--only SP[,SP]`"),
    ("a started sprint outside the list is not given a runner", "step 5 does not refuse a runner to a started sprint outside the list"),
    ("plans, researches and starts no new sprint", "a limited tick may plan a new sprint"),
    ("the review, retrospective and close of step 3 run only for the named sprints", "review, retrospective and close are not limited"),
    ("the digest says the tick was limited", "the digest does not say the tick was limited"),
    ("that is not an active (started) sprint is named in the digest and ignored", "a named sprint that is not active is not reported and ignored"),
    ("without it the tick is as described below", "no `--only` does not mean the tick as today"),
    ("limited to SP", "step 9 does not record that the tick was limited"),
)


def only_problems(text):
    """What a skill text lacks of the limited tick, one line each."""
    out = []
    flat = re.sub(r"\s+", " ", text)
    if not re.search(r'^argument-hint: ".*--only SP\[,SP\]', text, re.MULTILINE):
        out.append("the frontmatter argument-hint lacks `--only SP[,SP]`")
    for phrase, why in RULES:
        if phrase not in flat:
            out.append(f"missing `{phrase}`: {why}")
    return out


def test_autopilot_tick_only_limits_runners_to_named_sprints():
    assert only_problems(SKILL.read_text(encoding="utf-8")) == []


GOOD = ('argument-hint: "[tick] [--only SP[,SP]]"\n'
        "`--only SP[,SP]` limits the tick; without it the tick is as described below. A named sprint that is not an "
        "active (started) sprint is named in the digest and ignored. A limited tick starts a runner only on a named "
        "sprint, a started sprint outside the list is not given a runner, and plans, researches and starts no new "
        "sprint; the review, retrospective and close of step 3 run only for the named sprints; the digest says the "
        "tick was limited (step 7); step 9 starts its first line with `limited to SP`.\n")


def test_autopilot_tick_only_good_text_passes():
    assert only_problems(GOOD) == []


@pytest.mark.parametrize("old, want", [
    ('argument-hint: "[tick] [--only SP[,SP]]"', "argument-hint"),
    ("a started sprint outside the list is not given a runner", "outside the list"),
    ("plans, researches and starts no new sprint", "no new sprint"),
    ("the review, retrospective and close of step 3 run only for the named sprints", "review, retrospective"),
    ("the digest says the tick was limited", "digest says"),
    ("that is not an active (started) sprint is named in the digest and ignored", "not active"),
    ("without it the tick is as described below", "as today"),
    ("limited to SP", "step 9"),
])
def test_autopilot_tick_only_planted_failures(old, want):
    assert old in GOOD
    plant = GOOD.replace(old, "x", 1)
    assert plant != GOOD
    problems = only_problems(plant)
    assert any(want in p for p in problems), problems
