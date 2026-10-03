"""land removes a finished worker's worktree that sits beside a headless runner's own (bl_land.release_worker_worktree).

A runner's worktree is `<clone root>/.claude/worktrees/runner-SP-*`; the Agent tool puts the worker's worktree beside it,
`<clone root>/.claude/worktrees/agent-*`, so the runner's toplevel alone never names the worker's directory. The clone
is the runner worktree's common checkout. Planted failures: a worker on another item's branch, one with uncommitted
changes, one under another clone, a lock that is not an agent's, a detached one not at the branch's tip: each is kept.
"""
import subprocess

import pytest

import bl_land

BRANCH = "work/ST-aaaaaaaa"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "hostlocks"))


def sh(cwd, *args):
    p = subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True, text=True)
    return p.stdout.strip()


def make_clone(parent):
    parent.mkdir(parents=True, exist_ok=True)
    sh(parent, "init", "-q", "-b", "main")
    sh(parent, "commit", "-q", "--allow-empty", "-m", "start")
    (parent / ".git" / "info").mkdir(exist_ok=True)
    (parent / ".git" / "info" / "exclude").write_text(".claude/worktrees/\n", encoding="utf-8")
    return parent


@pytest.fixture
def clone(tmp_path):
    return make_clone(tmp_path / "clone")


def runner_of(clone, name="runner-SP-xxxxxxxx"):
    path = clone / ".claude" / "worktrees" / name
    sh(clone, "worktree", "add", "-q", "-b", f"orch/{name}", str(path))
    return path


def worker_of(clone, name="agent-a1", branch=BRANCH, make_branch=True):
    path = clone / ".claude" / "worktrees" / name
    sh(clone, "worktree", "add", "-q", *(["-b", branch] if make_branch else []), str(path), *([] if make_branch else [branch]))
    return path


def listed(clone, path):
    return f"worktree {path.resolve()}" in sh(clone, "worktree", "list", "--porcelain")


def test_land_removes_sibling_worker_worktree_on_the_branch(clone, capsys):
    runner = runner_of(clone)
    worker = worker_of(clone)
    assert bl_land.release_worker_worktree(runner, worker, None, BRANCH) is None
    assert "land: removed the finished worker's worktree" in capsys.readouterr().out
    assert not worker.exists() and not listed(clone, worker)
    assert runner.exists()


def test_land_removes_sibling_worker_worktree_locked_by_an_agent(clone):
    runner = runner_of(clone)
    worker = worker_of(clone)
    sh(clone, "worktree", "lock", "--reason", "claude agent agent-a1 (pid 1)", str(worker))
    assert bl_land.release_worker_worktree(runner, worker, "claude agent agent-a1 (pid 1)", BRANCH) is None
    assert not worker.exists()


def test_land_removes_sibling_worker_worktree_detached_at_the_tip(clone):
    runner = runner_of(clone)
    worker = worker_of(clone)
    sh(worker, "checkout", "-q", "--detach")
    assert [p for p, _ in bl_land.detached_workers(runner, BRANCH)] == [worker.resolve()]  # the finder locates it
    assert bl_land.release_worker_worktree(runner, worker, None, BRANCH) is None
    assert not worker.exists() and not listed(clone, worker)


def test_land_removes_sibling_worker_worktree_keeps_one_detached_off_the_tip(clone):
    runner = runner_of(clone)
    worker = worker_of(clone)
    sh(worker, "commit", "-q", "--allow-empty", "-m", "more work")
    sh(worker, "checkout", "-q", "--detach")
    sh(clone, "branch", "-f", BRANCH, "main")  # planted: the branch moved away from the worker's commit
    assert bl_land.detached_workers(runner, BRANCH) == []
    why = bl_land.release_worker_worktree(runner, worker, None, BRANCH)
    assert why and f"not on {BRANCH}" in why and worker.exists() and listed(clone, worker)


def test_land_removes_sibling_worker_worktree_keeps_a_dirty_one(clone):
    runner = runner_of(clone)
    worker = worker_of(clone)
    (worker / "a.txt").write_text("unsaved\n", encoding="utf-8")  # planted: uncommitted work
    why = bl_land.release_worker_worktree(runner, worker, None, BRANCH)
    assert why and "uncommitted changes" in why and (worker / "a.txt").exists() and listed(clone, worker)


def test_land_removes_sibling_worker_worktree_keeps_another_items_branch(clone):
    runner = runner_of(clone)
    worker = worker_of(clone, branch="work/ST-bbbbbbbb")  # planted: another item's worker
    sh(clone, "branch", BRANCH)
    why = bl_land.release_worker_worktree(runner, worker, None, BRANCH)
    assert why and f"not on {BRANCH}" in why and worker.exists() and listed(clone, worker)


def test_land_removes_sibling_worker_worktree_keeps_another_clones_sibling(clone, tmp_path):
    runner = runner_of(clone)
    other = make_clone(tmp_path / "other-clone")  # planted: a worker under a different clone
    worker = worker_of(other)
    sh(clone, "branch", "-q", "-f", BRANCH, "main")
    why = bl_land.release_worker_worktree(runner, worker, None, BRANCH)
    assert why and "not under .claude/worktrees/" in why and worker.exists()


def test_land_removes_sibling_worker_worktree_keeps_a_locked_non_agent(clone):
    runner = runner_of(clone)
    worker = worker_of(clone)
    sh(clone, "worktree", "lock", "--reason", "on a removable disk", str(worker))  # planted: not an agent's lock
    why = bl_land.release_worker_worktree(runner, worker, "on a removable disk", BRANCH)
    assert why and "not by a Claude Code agent" in why and worker.exists() and listed(clone, worker)


def test_land_removes_sibling_worker_worktree_keeps_a_sibling_of_a_plain_linked_clone(clone):
    other = clone / ".claude" / "worktrees" / "linked-clone"  # planted: not a runner-*, so not the clone root's
    sh(clone, "worktree", "add", "-q", "-b", "linked", str(other))
    worker = worker_of(clone)
    why = bl_land.release_worker_worktree(other, worker, None, BRANCH)
    assert why and "not under .claude/worktrees/" in why and worker.exists() and listed(clone, worker)
