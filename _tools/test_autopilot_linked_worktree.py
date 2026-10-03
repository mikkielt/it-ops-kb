"""A manager clone that is a linked worktree of another checkout is refused (kb/_self/tools.md, The autopilot runner;
kb/_self/autopilot-test.md): `backlog.py selfcheck` fails its checkout check and `autopilot.py runner start` refuses,
both naming the other checkout and saying to use a standalone `git clone`. A standalone repository is not refused.
The tests named autopilot_refuses_linked_worktree* are the item's checks; the planted failure is the linked worktree.
"""
import pytest

import autopilot, bl_base, bl_selfcheck, bl_testkit
from bl_testkit import sh

bl_testkit.bind(__import__("backlog"))
repo, no_git_location = bl_testkit.repo, bl_testkit.no_git_location


@pytest.fixture(autouse=True)
def host_dir(tmp_path_factory, monkeypatch):
    for var in ("KB_TESTS_FAST", "KB_TEST_WORKERS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("KB_HEADLESS_RUNNER", raising=False)
    d = tmp_path_factory.mktemp("hostlocks")
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(d))
    return d


@pytest.fixture
def linked(repo, tmp_path_factory):
    wt = tmp_path_factory.mktemp("elsewhere") / "linked"
    sh(repo, "git", "worktree", "add", "-q", "-b", "side", str(wt))
    return wt


def test_autopilot_refuses_linked_worktree_selfcheck_names_the_other_checkout(repo, linked):
    r = bl_selfcheck.check_checkout(str(linked))
    assert r["state"] == "fail", r
    assert "linked worktree" in r["detail"] and str(repo.resolve()) in r["detail"], r
    assert "git clone" in r["remedy"], r


def test_autopilot_refuses_linked_worktree_runner_start_refuses(repo, linked):
    with pytest.raises(bl_base.Refused) as e:
        autopilot.runner_start("SP-aaaaaaaa", None, linked)
    msg = str(e.value)
    assert "linked worktree" in msg and str(repo.resolve()) in msg and "git clone" in msg, msg


def test_autopilot_refuses_linked_worktree_standalone_clone_is_not_refused(repo):
    assert bl_selfcheck.check_checkout(str(repo))["state"] == "ok"
    assert bl_selfcheck.linked_worktree_message(repo) is None
    sub = repo / "src"  # a subdirectory of a standalone clone: git prints a relative common dir there
    assert bl_selfcheck.linked_worktree_of(sub) is None


def test_autopilot_refuses_linked_worktree_relative_git_dirs_are_resolved(repo, linked):
    assert bl_selfcheck.linked_worktree_of(linked / "src") == repo.resolve()
