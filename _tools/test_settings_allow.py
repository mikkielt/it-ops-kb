""".claude/settings.json allows the commands a headless sprint runner (autopilot.py runner start, /kb-sprint run
--headless) and its manager run, each shell rule as Bash and PowerShell, in the narrow forms the runner uses, and
nothing broader in the same families: no kbgit.py, git or glab rule beyond the list, no whole-shell rule and no tool
rule beyond the four the runner needs. It denies, for both shells, what a headless agent must never do without a
prompt: publish, push, delete a branch or a worktree, or throw away a file's changes."""
import json
import re

import pytest

from conftest import text

KBGIT_ALLOWED = ("sync", "check-trailers", "check-lanes", "lane", "fix --check", "fmt --check", "trailers", "log",
                 "blame", "asof", "check-public")  # never publish, bridge, install-hooks, tag-census, or a writing fix
RUNNER_COMMANDS = [
    *(f"python3 _tools/kbgit.py {c} *" for c in KBGIT_ALLOWED),
    "python3 _tools/selfdoc.py stale *",
    "python3 _tools/autopilot.py *",  # the manager's: runner start, runner-status
    "git fetch",
    "git fetch --quiet",
    "git fetch origin",
    *(f"git {c} *" for c in ("status", "log", "show", "diff", "add", "commit", "rebase", "merge-base", "cherry")),
    "git checkout -b *",
    "git checkout work/*",
    "git checkout orch/*",
    "git branch --list *",
    *(f"git worktree {c} *" for c in ("list", "add", "unlock")),
    "git -C * status *",
    "git -C * log *",
    "git -C * fetch",
    "git -C * fetch origin",
    "git -C * worktree add *",
    "glab mr view *",
    "glab mr merge *",
]
RUNNER_TOOLS = ["Agent", "Edit", "Write", "SendMessage"]
# The kb-autopilot tick's own: the decision digest and list (read forms only: digest without --out, which writes to
# any path), and the tools it notifies with. kbdecide.py's writing forms (record, ratify, revert, supersede,
# invalidate, ...) are never allowed.
TICK_COMMANDS = ["python3 _tools/kbdecide.py digest", "python3 _tools/kbdecide.py list *"]
TICK_TOOLS = ["PushNotification", "ToolSearch"]
DENIED_COMMANDS = ["python3 _tools/kbgit.py publish *", "git push *", "git -C * push *", "git branch -D *",
                   "git worktree remove *", "git checkout -- *"]
SHELLS = ("Bash", "PowerShell")


def permissions(settings_text):
    return json.loads(settings_text).get("permissions", {})


def runner_problems(perms):
    """What the permission lists lack of the runner's rules and denies, or allow beyond them in the same families."""
    allow, deny = perms.get("allow", []), set(perms.get("deny", []))
    have = set(allow)
    out = [f"missing {s}({c})" for c in RUNNER_COMMANDS for s in SHELLS if f"{s}({c})" not in have]
    out += [f"missing {t}" for t in RUNNER_TOOLS if t not in have]
    out += [f"not denied {s}({c})" for c in DENIED_COMMANDS for s in SHELLS if f"{s}({c})" not in deny]
    out += [f"missing {s}({c})" for c in TICK_COMMANDS for s in SHELLS if f"{s}({c})" not in have]
    out += [f"missing {t}" for t in TICK_TOOLS if t not in have]
    listed = {f"{s}({c})" for c in RUNNER_COMMANDS + TICK_COMMANDS for s in SHELLS}
    for rule in allow:
        m = re.fullmatch(r"(Bash|PowerShell)\((.*)\)", rule)
        if m and re.match(r"(git|glab)\b|python3 _tools/(kbgit|kbdecide)\.py\b", m.group(2)) and rule not in listed:
            out.append(f"beyond the list: {rule}")
        elif rule in SHELLS or (m and m.group(2).strip() in ("*", "")):
            out.append(f"whole shell allowed: {rule}")
        elif not m and not rule.startswith("mcp__") and rule not in RUNNER_TOOLS + TICK_TOOLS:
            out.append(f"tool rule beyond the list: {rule}")
    return out


def test_settings_allow_tick_commands():
    """The kb-autopilot tick runs kbdecide.py digest and list and calls PushNotification and ToolSearch: each is
    allowed, for both shells, and no wider kbdecide.py form is."""
    problems = runner_problems(permissions(text(".claude/settings.json")))
    assert problems == []


@pytest.mark.parametrize("plant, want", [
    (lambda a: [r for r in a if r != "PowerShell(python3 _tools/kbdecide.py digest)"],
     "missing PowerShell(python3 _tools/kbdecide.py digest)"),
    (lambda a: [r for r in a if r != "Bash(python3 _tools/kbdecide.py list *)"],
     "missing Bash(python3 _tools/kbdecide.py list *)"),
    (lambda a: [r for r in a if r != "PushNotification"], "missing PushNotification"),
    (lambda a: [r for r in a if r != "ToolSearch"], "missing ToolSearch"),
    *[(lambda a, c=c: a + [f"Bash(python3 _tools/kbdecide.py {c})"], f"beyond the list: Bash(python3 _tools/kbdecide.py {c})")
      for c in ("*", "digest *", "record *", "ratify *", "revert *", "supersede *", "invalidate *")],
])
def test_settings_allow_tick_commands_refuses_a_planted_change(plant, want):
    perms = permissions(text(".claude/settings.json"))
    assert want in runner_problems({**perms, "allow": plant(perms["allow"])})


def test_settings_allow_headless_runner():
    assert runner_problems(permissions(text(".claude/settings.json"))) == []


def _allow(f):
    return lambda p: {**p, "allow": f(p["allow"])}


@pytest.mark.parametrize("plant, want", [
    (_allow(lambda a: [r for r in a if r != "PowerShell(git rebase *)"]), "missing PowerShell(git rebase *)"),
    (_allow(lambda a: [r for r in a if r != "SendMessage"]), "missing SendMessage"),
    (_allow(lambda a: a + ["Bash(git push *)"]), "beyond the list: Bash(git push *)"),
    (_allow(lambda a: a + ["Bash(python3 _tools/kbgit.py *)"]), "beyond the list: Bash(python3 _tools/kbgit.py *)"),
    (_allow(lambda a: a + ["Bash(git -C *)"]), "beyond the list: Bash(git -C *)"),
    (_allow(lambda a: a + ["Bash(git worktree *)"]), "beyond the list: Bash(git worktree *)"),
    (_allow(lambda a: a + ["Bash(*)"]), "whole shell allowed: Bash(*)"),
    (_allow(lambda a: a + ["WebFetch"]), "tool rule beyond the list: WebFetch"),
    *[(lambda p, r=f"{s}({c})": {**p, "deny": [x for x in p["deny"] if x != r]}, f"not denied {s}({c})")
      for c in DENIED_COMMANDS for s in SHELLS],
])
def test_settings_allow_headless_runner_refuses_a_planted_change(plant, want):
    assert want in runner_problems(plant(permissions(text(".claude/settings.json"))))
