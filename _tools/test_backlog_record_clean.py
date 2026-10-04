"""`backlog.py answer --record` and `kbdecide.py digest --commit` leave a clean tree (`python3 _tools/tests.py -k
answer_record_leaves_a_clean_tree`): a session answers a gate, writes the digest and runs `kbgit.py sync --push`,
which refuses a dirty tree, so each step commits what it wrote.

  scenario (git)  a throwaway clone of a kb copy with its hooks installed: answer --record by the operator, then an
                  autopilot decision kept from before its retirement planted in the decision file, then digest
                  --commit, then `sync --dry-run --push`, the tree clean after each step and the planning commit named
                  with KB-Work and check-trailers satisfied; planted: the digest without --commit leaves the tracked
                  file modified and sync refuses it
"""
import json
import os

import pytest

from conftest import git_env, requires_git
from test_sync import clones

GATE = ("gate", "add")
GATE_ARGS = ("--kind", "blocking", "--id", "g9", "--question", "Which colour?", "--option", "a", "--option", "b",
             "--recommendation", "a", "--do", "a=true", "--do", "b=true")
DIGEST = "kb/_self/reports/decision-digest.md"


def an_item(clone):
    """The id of an item that is in no sprint: a gate on it is no sprint's start gate."""
    folder = clone.file("kb/_self/backlog")
    for name in sorted(os.listdir(folder)):
        if name.startswith("BG-") and name.endswith(".json"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                if "sprint" not in json.load(f):
                    return name[:-len(".json")]
    raise AssertionError("no item outside a sprint")


def clean(clone):
    return clone.git("status", "--porcelain").strip()


def backlog(clone, *args):
    p = clone.tool("backlog.py", *args)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


def plant_autopilot_decision(clone, iid):
    """An active, unratified autopilot decision on the item's gate g9, as the decision file keeps those made before the
    autopilot was retired: the operator records it with the autopilot as its maker, and it is committed."""
    p = clone.tool("kbdecide.py", "record", "--root", "_self", "--source", f"backlog item {iid} gate g9", "--context",
                   f"item:{iid}", "--gate", "g9", "--by", "operator", "--maker", "autopilot", "--review-by", "2999-01-01",
                   "--", "kept: a")
    assert p.returncode == 0, p.stdout + p.stderr
    clone.git("add", "-A")
    clone.git("commit", "-q", "-m", "chore(kb): an autopilot decision kept from before")
    assert clean(clone) == ""


@requires_git
@pytest.mark.git
def test_answer_record_leaves_a_clean_tree(tmp_path, kb_seed):
    env = git_env(KB_SYNC_NO_TESTS="1", KB_SYNC_PUSH_PAUSE_S="0")
    _, (a,), _ = clones(kb_seed, str(tmp_path), env, ("a",))
    iid = an_item(a)
    backlog(a, *GATE, iid, *GATE_ARGS)
    a.git("add", "-A")
    a.git("commit", "-q", "-m", f"chore(backlog): gate\n\nKB-Work: {iid}")
    assert clean(a) == ""
    tip = a.rev("HEAD")

    backlog(a, "answer", iid, "g9", "--answer", "a", "--by", "operator", "--record")
    assert clean(a) == "", clean(a)
    assert a.rev("HEAD") != tip
    item_commit, row_commit = a.rev("HEAD~1"), a.rev("HEAD")
    assert a.git("show", "--name-only", "--format=", item_commit).split() == [f"kb/_self/backlog/{iid}.json"]
    assert a.git("show", "--name-only", "--format=", row_commit).split() == ["kb/_self/_decisions.csv"]
    assert f"KB-Work: {iid}" in a.git("log", "-1", "--format=%B", item_commit).splitlines()
    assert "KB-Work" not in a.git("log", "-1", "--format=%B", row_commit)
    checked = a.kbgit("check-trailers", f"{tip}..HEAD")  # the item is not claimed: only a planning commit may name it
    assert checked.returncode == 0 and "bad=0" in checked.stdout, checked.stdout + checked.stderr

    plant_autopilot_decision(a, iid)
    assert a.kbgit("check-trailers", f"{tip}..HEAD").returncode == 0

    out = a.tool("kbdecide.py", "digest", "--commit")
    assert out.returncode == 0, out.stdout + out.stderr
    assert clean(a) == "", clean(a)
    assert a.git("show", "--name-only", "--format=", "HEAD").split() in ([DIGEST], [])  # unchanged: no commit at all
    again = a.rev("HEAD")
    assert a.tool("kbdecide.py", "digest", "--commit").returncode == 0 and a.rev("HEAD") == again  # converges

    dry = a.kbgit("sync", "--dry-run", "--push")
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert "uncommitted changes" not in dry.stdout + dry.stderr
    assert clean(a) == ""


@requires_git
@pytest.mark.git
def test_answer_record_leaves_a_clean_tree_planted_digest_without_commit_is_refused_by_sync(tmp_path, kb_seed):
    """Planted: the digest of an unratified autopilot decision written without --commit leaves the tracked file
    modified, and sync refuses the dirty tree: the failure the clean-tree test exists to catch."""
    env = git_env(KB_SYNC_NO_TESTS="1", KB_SYNC_PUSH_PAUSE_S="0")
    _, (a,), _ = clones(kb_seed, str(tmp_path), env, ("a",))
    iid = an_item(a)
    backlog(a, *GATE, iid, *GATE_ARGS)
    a.git("add", "-A")
    a.git("commit", "-q", "-m", f"chore(backlog): gate\n\nKB-Work: {iid}")
    plant_autopilot_decision(a, iid)
    assert a.tool("kbdecide.py", "digest").returncode == 0
    assert clean(a) == f"M {DIGEST}", clean(a)
    dry = a.kbgit("sync", "--dry-run", "--push")
    assert dry.returncode != 0 and "uncommitted changes" in dry.stdout + dry.stderr, dry.stdout + dry.stderr
