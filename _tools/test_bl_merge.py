"""`backlog.py merge ID` is the one way an agent merges a merge request: only the item's own code/ID, only on the
integration remote's GitLab project (no -R of another); .claude/settings.json allows no `glab mr merge`
(kb/_self/backlog.md)."""
import argparse

import pytest

import bl_base, bl_land


class FakeBacklog:
    def __init__(self, root, items):
        self.root, self.items = str(root), items


ITEMS = {"SP-aaaaaaaa": {"kind": "sprint"}, "ST-aaaaaaaa": {"kind": "story", "sprint": "SP-aaaaaaaa"},
         "TK-aaaaaaaa": {"kind": "task", "parent": "ST-aaaaaaaa"}, "BG-bbbbbbbb": {"kind": "bug", "sprint": "SP-bbbbbbbb"}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    calls = []

    def run(argv, cwd=None):
        calls.append(argv)
        if argv[:3] == ["git", "remote", "get-url"]:
            return 0, "git@gitlab.example.com:team/kb.git\n", ""
        return 0, "merged", ""
    monkeypatch.setattr(bl_land, "run", run)
    monkeypatch.setattr(bl_land, "say", lambda *a, **k: None)
    monkeypatch.setattr("kbpublic.integration_remote", lambda root: "origin")
    return FakeBacklog(tmp_path, dict(ITEMS)), calls


def merge(bl, iid):
    return bl_land.cmd_merge(bl, argparse.Namespace(id=iid))


def glab_calls(calls):
    return [c for c in calls if c[:1] == ["glab"]]


def test_merge_only_own_code_branch(world):
    bl, calls = world
    assert merge(bl, "TK-aaaaaaaa") == 0
    assert glab_calls(calls) == [["glab", "mr", "merge", "code/TK-aaaaaaaa", "--auto-merge=false", "--yes", "-R",
                                  "https://gitlab.example.com/team/kb"]]


def test_merge_only_own_code_branch_unknown_item_refused(world):
    bl, calls = world
    with pytest.raises(Exception):
        merge(bl, "TK-zzzzzzzz")
    assert not glab_calls(calls)


def test_merge_only_own_code_branch_no_gitlab_project_refused(world, monkeypatch, tmp_path):
    bl, calls = world
    monkeypatch.setattr(bl_land, "run", lambda argv, cwd=None: calls.append(argv) or (0, str(tmp_path) + "\n", ""))
    with pytest.raises(bl_base.Refused, match="names no GitLab project"):
        merge(bl, "TK-aaaaaaaa")  # a local remote: no forge, no -R to build
    assert not glab_calls(calls)


def test_merge_only_own_code_branch_takes_no_project_argument():
    p = argparse.ArgumentParser()
    bl_land.args_merge(p)
    with pytest.raises(SystemExit):
        p.parse_args(["TK-aaaaaaaa", "-R", "other/project"])
