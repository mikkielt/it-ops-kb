"""backlog.py cost --rework run in a linked clone also reads the spool of the main worktree
(`python3 _tools/tests.py -k cost_open_session_main_spool`): a session started in the main checkout that orchestrates
the clone writes its work rows to `<main>/_cache/querylog/spool`, so a read of the clone's spool alone gave a silent
zero. The clone's own spool is a throwaway directory the test points `ql_capture.spool_dir` at; the main spool is the
one the throwaway main checkout holds. Planted failure: the old behaviour (the clone's spool only) fails the check.
"""
import json
from pathlib import Path

import pytest

import backlog
import bl_cost
import bl_testkit
import ql_capture
from test_cost_open_session import MARK, OPUS, SID, plant

bl_testkit.bind(backlog)

repo, sprint, commit, sh = bl_testkit.repo, bl_testkit.sprint, bl_testkit.commit, bl_testkit.sh

SID2 = "cccccccc-0000-4000-8000-000000000002"


@pytest.fixture
def linked(sprint, tmp_path_factory, monkeypatch):
    """The sprint's repository is the main checkout; the report runs in a linked worktree of it, whose own spool
    is an empty directory of the test."""
    main = Path(sprint["repo"])
    commit(main, "plan")
    wt = tmp_path_factory.mktemp("linked") / "wt"
    sh(main, "git", "worktree", "add", "-q", "-b", "work/example", str(wt))
    own = tmp_path_factory.mktemp("own") / "spool"
    own.mkdir()
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: own)
    return {**sprint, "main": main, "wt": wt, "own": own, "mspool": main / "_cache" / "querylog" / "spool"}


def snapshot(d):
    d = Path(d)
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()} if d.is_dir() else None


def report(w, capsys):
    """The sprint's rework report, run in the clone, as JSON."""
    return json.loads(bl_testkit_cost(w, capsys, "--format", "json"))


def bl_testkit_cost(w, capsys, *extra):
    from test_bl_cost import cost_out
    return cost_out(w["wt"], capsys, w["sp"], "--rework", *extra)


def check_main_figures(w, capsys, sessions=1, prompts=3):
    o = report(w, capsys)["open_sessions"]
    assert (o["sessions"], o["missing"], o["prompts"]) == (sessions, 0, prompts), o
    assert MARK in bl_testkit_cost(w, capsys)


def test_cost_open_session_main_spool_rows_of_the_main_checkout_are_read(linked, capsys):
    plant(linked["mspool"], SID, linked["tk"])
    before = snapshot(linked["mspool"])
    check_main_figures(linked, capsys)
    assert report(linked, capsys)["open_sessions"]["rework_split"]["work"]["direct"][OPUS]["in"] == 6
    assert snapshot(linked["mspool"]) == before and not list(linked["own"].iterdir())  # nothing written to either


def test_cost_open_session_main_spool_two_sessions_in_two_spools_both_count(linked, capsys):
    plant(linked["mspool"], SID, linked["tk"])
    plant(linked["own"], SID2, linked["tk"])
    check_main_figures(linked, capsys, sessions=2, prompts=6)


def test_cost_open_session_main_spool_same_session_in_both_counts_once(linked, capsys):
    plant(linked["mspool"], SID, linked["tk"])
    plant(linked["own"], SID, linked["tk"])
    check_main_figures(linked, capsys)


def test_cost_open_session_main_spool_none_there_is_unchanged(linked, capsys):
    plant(linked["own"], SID, linked["tk"])
    assert not linked["mspool"].exists()
    check_main_figures(linked, capsys)
    out = bl_testkit_cost(linked, capsys)
    assert out.count(MARK) == 1


def test_cost_open_session_main_spool_nothing_anywhere_is_a_plain_zero(linked, capsys):
    assert "open session figures" not in bl_testkit_cost(linked, capsys)


def test_cost_open_session_main_spool_run_in_the_main_checkout_reads_it_once(linked, capsys, monkeypatch):
    """Own spool and main spool are the same directory (a run in the main checkout): the session counts once."""
    plant(linked["mspool"], SID, linked["tk"])
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: linked["mspool"])
    check_main_figures(linked, capsys)


def test_cost_open_session_main_spool_old_behaviour_fails_the_check(linked, capsys, monkeypatch):
    """Planted failure: the old code read the clone's spool only, so the main spool's session gave zero."""
    plant(linked["mspool"], SID, linked["tk"])
    monkeypatch.setattr(bl_cost.bl_base, "main_worktree_spool", lambda root: None)
    with pytest.raises(AssertionError):
        check_main_figures(linked, capsys)
