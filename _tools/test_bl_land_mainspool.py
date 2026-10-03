"""The warning `backlog.py land` gives for an item landed with no work rows also reads the spool of the git common dir's
main worktree (`python3 _tools/tests.py -k no_work_rows_reads_main_worktree_spool`).

A session started in the main checkout that orchestrates a linked clone writes the item's claim and done rows to the
main checkout's spool (`<main>/_cache/querylog/spool`), not the spool of the worktree `land` runs in, so a warning that
read only the latter fired for every landing. Each test builds a throwaway repository with a linked worktree (git
isolation: no inherited GIT_* location, committer set, nothing outside the temporary directory). Planted failures: no
row in either spool (the warning still fires), another item's row, a refused done, a main worktree with no spool
directory. The own spool is the test's own (`ql_capture.spool_dir` patched), never the clone's.
"""
import json
from pathlib import Path

import pytest

import backlog
import bl_land
import bl_testkit
import ql_capture
import ql_distill

bl_testkit.bind(backlog)

repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs
commit, sh = bl_testkit.commit, bl_testkit.sh

WARNING = "landed with no work rows"


@pytest.fixture
def linked(sprint, tmp_path_factory, monkeypatch):
    """(main checkout, linked worktree, item ids): the sprint's items committed in the main checkout and a linked
    worktree of it on its own branch. The own spool is an empty directory of the test, as distill leaves it."""
    main = sprint["repo"]
    commit(main, "plan")
    wt = tmp_path_factory.mktemp("linked") / "wt"
    sh(main, "git", "worktree", "add", "-q", "-b", "work/example", str(wt))
    own = tmp_path_factory.mktemp("own") / "spool"
    own.mkdir()
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: own)
    return {"main": main, "wt": wt, "own": own, "tk": sprint["tk"], "st": sprint["st"], "bg": sprint["bg"]}


def main_spool(main):
    return Path(main) / "_cache" / "querylog" / "spool"


def plant(spool, item_id, action="claim", n=1):
    spool.mkdir(parents=True, exist_ok=True)
    row = {"id": f"{n:08x}-1111-4111-8111-111111111111", "ts": "2026-10-01T10:00:00.000Z", "surface": "work", "v": 1,
           "session_id": "s1", "prompt_id": "p1", "item": item_id, "action": action}
    with open(spool / "tools-2026-10-01.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row) + "\n")


def snapshot(d):
    d = Path(d)
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()} if d.is_dir() else None


def landed(clone, iid, capsys):
    wrapped = bl_land.ops_land(lambda bl, a: 0)
    assert wrapped(backlog.Backlog(clone), type("A", (), {"id": iid})()) == 0
    return capsys.readouterr().out


def test_no_work_rows_reads_main_worktree_spool(linked, capsys):
    """A session in the main checkout wrote the item's rows there: landing from the linked worktree is quiet; the
    same landing with no row in either spool warns (planted failure)."""
    wt, main, tk = linked["wt"], linked["main"], linked["tk"]
    assert bl_land.ops_no_work_rows(wt, tk) is True and WARNING in landed(wt, tk, capsys)  # planted: nowhere
    plant(main_spool(main), tk)
    assert bl_land.ops_no_work_rows(wt, tk) is False
    assert WARNING not in landed(wt, tk, capsys)


@pytest.mark.parametrize("action", ql_capture.WORK_ACTIONS)
def test_no_work_rows_reads_main_worktree_spool_each_action(linked, action):
    plant(main_spool(linked["main"]), linked["tk"], action)
    assert bl_land.ops_no_work_rows(linked["wt"], linked["tk"]) is False


def test_no_work_rows_reads_main_worktree_spool_a_descendant_counts(linked):
    """The story's landing counts its task's rows in the main spool, as it does in the own one."""
    assert bl_land.ops_no_work_rows(linked["wt"], linked["st"]) is True
    plant(main_spool(linked["main"]), linked["tk"])
    assert bl_land.ops_no_work_rows(linked["wt"], linked["st"]) is False


def test_no_work_rows_reads_main_worktree_spool_other_rows_do_not_count(linked):
    """Planted failure: the main spool holds the bug's rows and a refused done of the task: the task still has none."""
    main = main_spool(linked["main"])
    plant(main, linked["bg"])
    plant(main, linked["tk"], "refused", 2)
    assert bl_land.ops_no_work_rows(linked["wt"], linked["tk"]) is True
    assert bl_land.ops_no_work_rows(linked["wt"], linked["bg"]) is False


def test_no_work_rows_reads_main_worktree_spool_none_there(linked):
    """The main worktree has no spool directory (no session ever wrote there): the own spool decides alone."""
    assert not (Path(linked["main"]) / "_cache").exists()
    assert bl_land.ops_no_work_rows(linked["wt"], linked["tk"]) is True
    plant(linked["own"], linked["tk"])
    assert bl_land.ops_no_work_rows(linked["wt"], linked["tk"]) is False


def test_no_work_rows_reads_main_worktree_spool_own_spool_missing(linked):
    """The linked worktree's own spool directory does not exist: the main spool's rows still count."""
    linked["own"].rmdir()
    plant(main_spool(linked["main"]), linked["tk"])
    assert bl_land.ops_no_work_rows(linked["wt"], linked["tk"]) is False
    assert bl_land.ops_no_work_rows(linked["wt"], linked["bg"]) is True


def test_no_work_rows_reads_main_worktree_spool_reads_only(linked):
    """A read only: the main worktree's files and the directories around them are byte for byte as they were."""
    main = main_spool(linked["main"])
    plant(main, linked["bg"])
    before, tree = snapshot(main), snapshot(Path(linked["main"]) / "_cache")
    assert bl_land.ops_no_work_rows(linked["wt"], linked["tk"]) is True
    assert snapshot(main) == before and snapshot(Path(linked["main"]) / "_cache") == tree


def test_no_work_rows_reads_main_worktree_spool_same_directory_read_once(linked, monkeypatch):
    """Landing in the main checkout itself: its spool is the own spool, read once, not twice."""
    main = main_spool(linked["main"])
    plant(main, linked["bg"])
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: main)
    reads = []
    real = ql_distill.spool_rows
    monkeypatch.setattr(ql_distill, "spool_rows", lambda p, *a, **k: reads.append(Path(p).name) or real(p, *a, **k))
    assert bl_land.ops_no_work_rows(linked["main"], linked["tk"]) is True
    assert reads == ["tools-2026-10-01.jsonl"], reads
    plant(main, linked["tk"], n=2)
    assert bl_land.ops_no_work_rows(linked["main"], linked["tk"]) is False


def test_no_work_rows_reads_main_worktree_spool_capture_off_says_nothing(linked, monkeypatch):
    """With capture off there is nothing to judge by: no warning, whatever the main spool holds."""
    plant(main_spool(linked["main"]), linked["bg"])
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: None)
    assert bl_land.ops_no_work_rows(linked["wt"], linked["tk"]) is False


def test_no_work_rows_reads_main_worktree_spool_not_a_repository(tmp_path):
    """Git cannot name a common dir: no main spool, no error."""
    assert bl_land.main_worktree_spool(tmp_path) is None
