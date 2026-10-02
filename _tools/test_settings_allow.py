""".claude/settings.json allows the commands a headless sprint runner (autopilot.py runner start, /kb-sprint run
--headless) and its manager run, each shell rule as Bash and PowerShell, and nothing broader in the same families: no
git or glab rule beyond the listed subcommands, no whole-shell rule and no tool rule beyond the four the runner needs."""
import json
import re

import pytest

from conftest import text

RUNNER_COMMANDS = [
    "python3 _tools/kbgit.py *",
    "python3 _tools/selfdoc.py stale *",
    "python3 _tools/autopilot.py *",  # the manager's: runner start, runner-status
    *(f"git {c} *" for c in ("fetch", "status", "log", "show", "diff", "add", "commit", "rebase", "merge-base",
                             "checkout", "branch", "cherry", "worktree", "-C")),
    "glab mr view *",
    "glab mr merge *",
]
RUNNER_TOOLS = ["Agent", "Edit", "Write", "SendMessage"]
SHELLS = ("Bash", "PowerShell")


def allow_rules(settings_text):
    return json.loads(settings_text).get("permissions", {}).get("allow", [])


def runner_problems(allow):
    """What the allow list lacks of the runner's rules, or holds beyond them in the same families."""
    have = set(allow)
    out = [f"missing {s}({c})" for c in RUNNER_COMMANDS for s in SHELLS if f"{s}({c})" not in have]
    out += [f"missing {t}" for t in RUNNER_TOOLS if t not in have]
    listed = {f"{s}({c})" for c in RUNNER_COMMANDS for s in SHELLS}
    for rule in allow:
        m = re.fullmatch(r"(Bash|PowerShell)\((.*)\)", rule)
        if m and re.match(r"(git|glab)\b", m.group(2)) and rule not in listed:
            out.append(f"beyond the list: {rule}")
        elif rule in SHELLS or (m and m.group(2).strip() in ("*", "")):
            out.append(f"whole shell allowed: {rule}")
        elif not m and not rule.startswith("mcp__") and rule not in RUNNER_TOOLS:
            out.append(f"tool rule beyond the list: {rule}")
    return out


def test_settings_allow_headless_runner():
    assert runner_problems(allow_rules(text(".claude/settings.json"))) == []


@pytest.mark.parametrize("plant, want", [
    (lambda a: [r for r in a if r != "PowerShell(git rebase *)"], "missing PowerShell(git rebase *)"),
    (lambda a: [r for r in a if r != "SendMessage"], "missing SendMessage"),
    (lambda a: a + ["Bash(git push *)"], "beyond the list: Bash(git push *)"),
    (lambda a: a + ["Bash(*)"], "whole shell allowed: Bash(*)"),
    (lambda a: a + ["WebFetch"], "tool rule beyond the list: WebFetch"),
])
def test_settings_allow_headless_runner_refuses_a_planted_change(plant, want):
    assert want in runner_problems(plant(allow_rules(text(".claude/settings.json"))))
