"""The settings a headless run reads cannot be changed from inside its worktree. Two layers, each with a planted failure:

  the file     autopilot.py runner start passes --settings a copy under _cache/autopilot/SP/, outside the runner's
               worktree, written at each start from the committed origin/main revision of .claude/settings.json (never the
               worktree's file): a `git checkout` of a path or of an old revision in the worktree, or a settings change
               committed in a worktree ahead of origin/main, changes the worktree's file and not the copy the run reads;
  the rules    .claude/settings.json allows `git checkout` only as a bare switch to work/ID or orch/SP, or -b of a work/ID,
               and denies a path after a branch and a start point after -b, for Bash and PowerShell. The permission
               matcher is the documented one: `*` matches any text including spaces, a trailing ` *` also matches the
               bare command, a deny beats an allow, and a command no allow rule matches is refused in a headless run.

Test names carry runner_settings_outside_worktree or runner_settings_from_origin_main."""
import json
import re
from pathlib import Path

import pytest

import autopilot
from conftest import Repo, git_env, text
from test_autopilot import SP, World, stream

SHELLS = ("Bash", "PowerShell")
OLD = '{"permissions": {"allow": ["Bash(*)"]}}\n'


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def settings_arg(argv):
    return Path(argv[argv.index("--settings") + 1])


def inside(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
    except ValueError:
        return False
    return True


def settings_problems(argv, root, worktree, sprint):
    """What is wrong with the --settings of ARGV: not outside WORKTREE, not under ROOT's _cache/autopilot/SPRINT/, or
    missing."""
    path = settings_arg(argv)
    out = []
    if inside(path, worktree):
        out.append("inside the worktree")
    if not inside(path, autopilot.cache_dir(root, sprint)):
        out.append("not under _cache/autopilot/SP")
    if not path.is_file():
        out.append("missing")
    return out


# ---------------------------------------------------------------- the file

def test_runner_settings_outside_worktree_path_is_under_the_cache_dir(tmp_path):
    p = autopilot.runner_settings_path(tmp_path, SP)
    assert inside(p, autopilot.cache_dir(tmp_path, SP)) and not inside(p, autopilot.worktree_path(tmp_path, SP))
    assert settings_arg(autopilot.claude_argv(autopilot.worktree_path(tmp_path, SP), SP, None, tmp_path)) == p


@pytest.mark.parametrize("landed", [None, 1, 4])
def test_runner_settings_outside_worktree_start_passes_the_copy(world, landed):
    """The --settings of a real start is outside the worktree, under the cache dir, and holds the settings content."""
    world.stream(stream())
    assert world.start(landed) == 0
    argv = world.seen()["argv"]
    assert settings_problems(argv, world.root, world.wt(), SP) == []
    assert settings_arg(argv).read_text(encoding="utf-8") == (world.wt() / ".claude" / "settings.json").read_text(encoding="utf-8")


def test_runner_settings_outside_worktree_a_planted_worktree_path_fails_the_check(world):
    """The old behaviour (the worktree's own file) is what the check refuses."""
    world.stream(stream())
    world.start()
    wt = world.wt()
    old = autopilot.claude_argv(wt, SP)
    old[old.index("--settings") + 1] = str(wt / ".claude" / "settings.json")
    assert "inside the worktree" in settings_problems(old, world.root, wt, SP)
    assert "not under _cache/autopilot/SP" in settings_problems(old, world.root, wt, SP)


def test_runner_settings_outside_worktree_a_checkout_in_the_worktree_leaves_the_copy(world, monkeypatch):
    """Plant a path checkout of an older revision in the worktree between two starts: the file the run reads at its start is
    the copy of the file the start saw, never the file the checkout wrote, and each start writes the copy afresh."""
    read = []
    real = autopilot.supervise

    def spy(argv, cwd, keep, stderr, deadline=None):
        read.append(settings_arg(argv).read_text(encoding="utf-8"))
        return real(argv, cwd, keep, stderr, deadline)

    monkeypatch.setattr(autopilot, "supervise", spy)
    world.stream(stream())
    assert world.start() == 0
    clone_text = (world.root / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert read == [clone_text]
    wt = Repo(world.wt(), git_env())
    wt.write(".claude/settings.json", OLD)  # a newer, wider file committed in the worktree ...
    wt.git("add", ".claude/settings.json")
    wt.git("commit", "-q", "-m", "wider")
    copy = autopilot.runner_settings_path(world.root, SP)
    assert copy.read_text(encoding="utf-8") == clone_text  # ... the copy is not the worktree's file
    wt.git("checkout", "HEAD~1", "--", ".claude/settings.json")  # what the run could do mid-run: restore an old revision
    assert wt.read(".claude/settings.json") == clone_text and copy.read_text(encoding="utf-8") == clone_text
    wt.write(".claude/settings.json", '{"x": 1}\n')  # any change of the worktree's file mid-run
    assert copy.read_text(encoding="utf-8") == clone_text
    wt.git("checkout", "HEAD", "--", ".claude/settings.json")  # the worktree is clean again, at the wider file
    assert world.start() == 0  # a second start refreshes the copy from origin/main, not from the wider file
    assert read == [clone_text, clone_text] and copy.read_text(encoding="utf-8") == clone_text


def test_runner_settings_outside_worktree_missing_source_stays_the_refusal(world, capsys, monkeypatch):
    world.repo.git("rm", "-q", ".claude/settings.json")
    world.commit("no settings")
    world.repo.git("push", "origin", "main")
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "start", SP]) == 2
    assert "settings.json" in capsys.readouterr().err
    assert not autopilot.runner_settings_path(world.root, SP).exists()


def test_runner_settings_outside_worktree_copy_is_written_whole(world):
    """The copy is the revision's bytes (a CRLF file stays as committed), no temporary file is left, and each call
    writes it afresh from the revision origin/main holds then."""
    wt, root = world.wt(), world.root
    world.repo.write(".claude/settings.json", '{"a": 1}\r\n')
    world.repo.git("config", "core.autocrlf", "false")
    world.commit("crlf")
    world.repo.git("push", "origin", "main")
    world.repo.git("worktree", "add", "-q", "-b", autopilot.branch_name(SP), str(wt), "origin/main")
    target = autopilot.copy_runner_settings(root, SP, wt)
    assert target == autopilot.runner_settings_path(root, SP) and target.read_bytes() == b'{"a": 1}\r\n'
    assert not list(target.parent.glob("*.tmp"))
    world.repo.write(".claude/settings.json", "{}\n")
    world.commit("plain")
    world.repo.git("push", "origin", "main")
    autopilot.copy_runner_settings(root, SP, wt)
    assert target.read_bytes() == b"{}\n"


# ---------------------------------------------------------------- the source is the committed origin/main

WIDE = "Bash(rm -rf *)"


def widened(rules):
    """RULES (a settings text) with one more allow entry, WIDE."""
    data = json.loads(rules)
    data.setdefault("permissions", {}).setdefault("allow", []).append(WIDE)
    return json.dumps(data, indent=2) + "\n"


def test_runner_settings_from_origin_main(world):
    """A commit in the worktree that widens an allow rule never reaches the copy: it holds the origin/main rules, the
    widened entry is absent, whether the commit is the worktree's only one ahead or one of several, and at every start."""
    world.stream(stream())
    assert world.start() == 0
    origin_text = world.repo.read(".claude/settings.json")
    wt = Repo(world.wt(), git_env())
    copy = autopilot.runner_settings_path(world.root, SP)
    for n in range(1, 4):  # one commit ahead, then more, each widening again
        wt.write(".claude/settings.json", widened(wt.read(".claude/settings.json")))
        wt.git("add", ".claude/settings.json")
        wt.git("commit", "-q", "-m", f"widen {n}")
        assert world.start() == 0  # the worktree is ahead of origin/main and is kept as it is
        assert wt.read(".claude/settings.json").count(WIDE) == n  # the worktree file does hold the wide rules ...
        assert copy.read_text(encoding="utf-8") == origin_text and WIDE not in copy.read_text(encoding="utf-8")  # ... the copy does not
        assert settings_arg(world.seen()["argv"]).read_text(encoding="utf-8") == origin_text


def test_runner_settings_from_origin_main_a_planted_worktree_source_fails_the_check(world):
    """The check of the first test refuses the old source: a copy written from the worktree's file holds the entry."""
    world.stream(stream())
    assert world.start() == 0
    wt = Repo(world.wt(), git_env())
    wt.write(".claude/settings.json", widened(wt.read(".claude/settings.json")))
    wt.git("add", ".claude/settings.json")
    wt.git("commit", "-q", "-m", "widen")
    copy = autopilot.runner_settings_path(world.root, SP)
    copy.write_bytes((world.wt() / ".claude" / "settings.json").read_bytes())  # the old source
    assert WIDE in copy.read_text(encoding="utf-8")
    autopilot.copy_runner_settings(world.root, SP, world.wt())  # the real one refreshes it
    assert WIDE not in copy.read_text(encoding="utf-8")


def test_runner_settings_from_origin_main_names_the_integration_remote(world):
    """The revision is read from the integration remote's main, whatever the remote is called."""
    world.stream(stream())
    assert world.start() == 0
    world.repo.git("remote", "rename", "origin", "integ")
    world.repo.git("config", "kb.integrationRemote", "integ")
    world.repo.write(".claude/settings.json", widened(world.repo.read(".claude/settings.json")))
    world.commit("landed")
    world.repo.git("push", "integ", "main")
    autopilot.copy_runner_settings(world.root, SP, world.wt())  # the worktree is behind integ/main: its file is not read
    assert WIDE in autopilot.runner_settings_path(world.root, SP).read_text(encoding="utf-8")


def test_runner_settings_from_origin_main_missing_ref_or_file_is_the_refusal(world):
    """No such file at origin/main, or no origin/main at all: bl_base.Refused naming the settings file, and no copy."""
    import bl_base
    wt = world.wt()
    world.repo.git("worktree", "add", "-q", "-b", autopilot.branch_name(SP), str(wt), "origin/main")
    target = autopilot.runner_settings_path(world.root, SP)
    world.repo.git("update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(bl_base.Refused, match="settings.json"):
        autopilot.copy_runner_settings(world.root, SP, wt)
    assert not target.exists() and not target.with_name(target.name + ".tmp").exists()


def test_runner_settings_from_origin_main_a_file_only_in_the_worktree_is_the_refusal(world, capsys, monkeypatch):
    """The worktree holds a settings file a commit ahead of origin/main added, origin/main has none: the start is refused
    (exit 2) and no copy is made."""
    world.repo.git("rm", "-q", ".claude/settings.json")
    world.commit("no settings")
    world.repo.git("push", "origin", "main")
    world.repo.git("worktree", "add", "-q", "-b", autopilot.branch_name(SP), str(world.wt()), "origin/main")
    wt = Repo(world.wt(), git_env())
    wt.write(".claude/settings.json", widened("{}\n"))
    wt.git("add", ".claude/settings.json")
    wt.git("commit", "-q", "-m", "settings only here")
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "start", SP]) == 2
    assert "origin/main:.claude/settings.json" in capsys.readouterr().err
    assert not autopilot.runner_settings_path(world.root, SP).exists()


# ---------------------------------------------------------------- the rules

def matches(rule, command):
    """Claude Code's Bash and PowerShell rule match: `*` is any text, a lone trailing ` *` also matches the bare command."""
    body = rule[rule.index("(") + 1:-1]
    pattern = ".*".join(re.escape(part) for part in body.split("*"))
    if body.endswith(" *") and body.count("*") == 1:
        pattern = re.escape(body[:-2]) + "(?: .*)?"
    return re.fullmatch(pattern, command, re.S) is not None


def verdict(perms, shell, command):
    """deny, allow, or ask (no rule: a headless run is refused) for COMMAND in SHELL."""
    for kind in ("deny", "allow"):
        if any(r.startswith(f"{shell}(") and matches(r, command) for r in perms.get(kind, [])):
            return kind
    return "ask"


ALLOWED = ["git checkout work/BG-abcdefg2", "git checkout orch/SP-abcdefg2", "git checkout -b work/BG-abcdefg2"]
DENIED = [
    "git checkout work/BG-abcdefg2 .claude/settings.json",  # a path after a branch
    "git checkout orch/SP-abcdefg2 _tools/autopilot.py",
    "git checkout work/BG-abcdefg2 -- .claude/settings.json",
    "git checkout work/BG-abcdefg2 -f",
    "git checkout -b work/BG-abcdefg2 HEAD~5",  # a start point, an old revision
    "git checkout -b work/BG-abcdefg2 origin/main",
    "git checkout -b work/BG-abcdefg2 -- .claude/settings.json",
    "git checkout -b orch/SP-abcdefg2 HEAD~5",
    "git checkout HEAD~5 -- .claude/settings.json",
    "git checkout -- .claude/settings.json",
]
NOT_ALLOWED = ["git checkout HEAD~5 .claude/settings.json", "git checkout main", "git checkout -b other",
               "git checkout -b orch/SP-abcdefg2", "git checkout -f work/BG-abcdefg2", "git checkout --detach"]


def perms():
    return json.loads(text(".claude/settings.json"))["permissions"]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("command", ALLOWED)
def test_runner_settings_outside_worktree_rules_allow_the_bare_switches(shell, command):
    assert verdict(perms(), shell, command) == "allow"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("command", DENIED)
def test_runner_settings_outside_worktree_rules_deny_a_path_and_a_start_point(shell, command):
    assert verdict(perms(), shell, command) == "deny"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("command", NOT_ALLOWED)
def test_runner_settings_outside_worktree_rules_refuse_every_other_checkout(shell, command):
    assert verdict(perms(), shell, command) == "ask"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("rule, command", [
    ("git checkout work/* *", "git checkout work/BG-abcdefg2 .claude/settings.json"),
    ("git checkout orch/* *", "git checkout orch/SP-abcdefg2 _tools/autopilot.py"),
    ("git checkout -b * *", "git checkout -b work/BG-abcdefg2 HEAD~5"),
])
def test_runner_settings_outside_worktree_rules_a_planted_missing_deny_allows_the_form(shell, rule, command):
    """Without its deny the form is allowed by the branch rule: what each deny closes."""
    p = perms()
    assert f"{shell}({rule})" in p["deny"]
    planted = {**p, "deny": [r for r in p["deny"] if r != f"{shell}({rule})"]}
    assert verdict(planted, shell, command) == "allow"


@pytest.mark.parametrize("shell", SHELLS)
def test_runner_settings_outside_worktree_rules_a_planted_wide_allow_is_not_the_list(shell):
    """The wide `-b *` allow the rules replaced is beyond the list test_settings_allow.py holds."""
    import test_settings_allow as lists
    p = perms()
    wide = {**p, "allow": p["allow"] + [f"{shell}(git checkout -b *)"]}
    assert f"beyond the list: {shell}(git checkout -b *)" in lists.runner_problems(wide)
    assert lists.runner_problems(p) == []
