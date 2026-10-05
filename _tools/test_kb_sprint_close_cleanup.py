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


# ---- backlog.py tidy (ST-3oaiwyfn): the clone's merged leftovers, listed and with --apply removed

def sh(cwd, *argv):
    import subprocess
    p = subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    return p.stdout


def tidy(clone, *args):
    import subprocess
    import sys
    p = subprocess.run([sys.executable, str(Path(KB) / "_tools" / "backlog.py"), "--root", str(clone), "tidy", *args],
                       cwd=clone, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


@pytest.fixture
def leftovers(tmp_path):
    """A clone with a bare origin: merged work/, worktree-agent-* and orch/ branches and a clean merged agent-a0
    worktree (tidy's); an unmerged work/ branch, a dirty agent-d1 worktree and a branch checked out in a worktree
    (kept)."""
    git = ("git", "-c", "user.name=t", "-c", "user.email=t@corp.example.com")
    origin, clone = tmp_path / "origin.git", tmp_path / "clone"
    sh(tmp_path, "git", "init", "-q", "--bare", "-b", "main", str(origin))
    sh(tmp_path, "git", "clone", "-q", str(origin), str(clone))
    (clone / "kb" / "_self" / "backlog").mkdir(parents=True)
    (clone / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
    sh(clone, *git, "checkout", "-q", "-b", "main")
    sh(clone, "git", "add", "-A")
    sh(clone, *git, "commit", "-qm", "base")
    sh(clone, "git", "push", "-q", "origin", "main")
    for b in ("work/TK-merged00", "worktree-agent-x1", "orch/SP-old00000"):
        sh(clone, "git", "branch", b)
    sh(clone, "git", "checkout", "-q", "-b", "work/TK-unmerged")
    (clone / "own.txt").write_text("own\n", encoding="utf-8")
    sh(clone, "git", "add", "own.txt")
    sh(clone, *git, "commit", "-qm", "own work")
    sh(clone, "git", "checkout", "-q", "main")
    wt = clone / ".claude" / "worktrees"
    sh(clone, "git", "worktree", "add", "-q", "--detach", str(wt / "agent-a0"), "main")
    sh(clone, "git", "worktree", "add", "-q", "--detach", str(wt / "agent-d1"), "main")
    (wt / "agent-d1" / "unsaved.txt").write_text("x\n", encoding="utf-8")
    sh(clone, "git", "worktree", "add", "-q", "-b", "work/TK-checked0", str(wt / "other-1"), "main")
    return clone


def branches(clone):
    return set(sh(clone, "git", "branch", "--format=%(refname:short)").split())


def test_tidy_removes_only_merged(leftovers):
    """Without --apply tidy lists and removes nothing; with it the merged branches and the clean merged agent worktree
    go, and the unmerged branch, the dirty worktree and the checked-out branch stay, each named with why."""
    clone, wt = leftovers, leftovers / ".claude" / "worktrees"
    before = branches(clone)
    code, out = tidy(clone)
    assert code == 0 and "would remove 4, kept 3" in out, out
    assert branches(clone) == before and (wt / "agent-a0").is_dir(), out
    code, out = tidy(clone, "--apply")
    assert code == 0 and "removed 4, kept 3" in out, out
    left = branches(clone)
    assert not {"work/TK-merged00", "worktree-agent-x1", "orch/SP-old00000"} & left, out
    assert {"work/TK-unmerged", "work/TK-checked0", "main"} <= left, out
    assert not (wt / "agent-a0").exists() and (wt / "agent-d1" / "unsaved.txt").is_file(), out
    assert "kept work/TK-unmerged: it has commits" in out and "kept work/TK-checked0: it is checked out" in out, out
    assert "agent-d1: it has uncommitted changes" in out, out
    assert "removed 0, kept 3" in tidy(clone, "--apply")[1]  # a second run finds nothing more
