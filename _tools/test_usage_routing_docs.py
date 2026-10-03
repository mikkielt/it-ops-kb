"""The limits of the worker routing are stated where a reader looks (`python3 _tools/tests.py -k worker_routing_limits`).
  worker_routing_limits_documented  `kb/_self/usage.md` (How tokens are measured) and `.claude/agents/kb-worker.md`
                    state each case the path-based routing of `kbusage.work_item` leaves in `sub` without a warning (a
                    worktree outside .claude/worktrees, commands naming two items or none, a worker killed before its
                    first command), and the brief makes the worker's first command name its worktree path; a copy of
                    either text without one of them fails
"""
import re
from pathlib import Path

import pytest

from conftest import KB

USAGE = Path(KB) / "kb" / "_self" / "usage.md"
WORKER = Path(KB) / ".claude" / "agents" / "kb-worker.md"

# what each text must say, as phrases (case and runs of white space ignored)
USAGE_STATES = (
    "outside .claude/worktrees",
    "two different items",
    "killed before its first command",
    "stay in `sub`",
    "read zero for the item",
    "no warning",
    "first command name its worktree path",
)
WORKER_STATES = (
    "first one included",
    "outside .claude/worktrees",
    "two items' directories or none",
    "killed before its first command",
    "stay in `sub`",
    "read zero for the item",
    "without a warning",
    "worker_usage_routing_by_worktree_path",
)


def squash(text):
    return re.sub(r"\s+", " ", text).lower()


def unstated(text, phrases):
    """The phrases `text` does not contain."""
    text = squash(text)
    return [p for p in phrases if p.lower() not in text]


def test_worker_routing_limits_documented():
    usage, worker = USAGE.read_text(encoding="utf-8"), WORKER.read_text(encoding="utf-8")
    assert unstated(usage, USAGE_STATES) == [], "usage.md lacks a limit of the worker routing"
    assert unstated(worker, WORKER_STATES) == [], "kb-worker.md lacks a limit of the worker routing"


@pytest.mark.parametrize("name", ["usage", "worker"])
def test_worker_routing_limits_documented_planted_failure(name):
    """A copy of the text without one stated phrase fails: each phrase is checked, none is covered by another."""
    text, phrases = (USAGE, USAGE_STATES) if name == "usage" else (WORKER, WORKER_STATES)
    text = text.read_text(encoding="utf-8")
    for phrase in phrases:
        planted = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
        assert unstated(planted, phrases) == [phrase], phrase
