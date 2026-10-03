"""backlog.py cost --rework for a session that was distilled after an idle close and then reopened: its earlier prompts
are in the work sidecar's figures (distill's `worked.json` lists them) and its rows are still in the spool, now with
new rows after the close, so it reads as open. The open session figures leave the listed prompts out, so no prompt is
counted in both the figures above and the open ones.

The spool is a throwaway directory the test points `ql_capture.spool_dir` at, with the ledger beside it as distill
keeps it. The planted failure is the old behaviour (the ledger not passed on), which the same check must reject.
"""
import json

import pytest

import backlog
import bl_testkit
import ql_capture
import ql_distill
from test_bl_cost import cost_out, cost_sidecar
from test_cost_open_session import OPUS, SID, counts, plant, rework_json

bl_testkit.bind(backlog)

repo, sprint = bl_testkit.repo, bl_testkit.sprint

PROMPTS = ("p0", "p1", "p2")  # the prompts test_cost_open_session.spool_rows plants, each with its own usage row


@pytest.fixture
def spool(tmp_path, monkeypatch):
    d = tmp_path / "spool"
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: d)
    return d


def ledger(spool, held, sid=SID):
    """Write distill's worked.json beside the spool: the prompts a sidecar already counted for the session."""
    (spool.parent / ql_distill.WORKED_NAME).write_text(json.dumps({sid: list(held)}), encoding="utf-8", newline="\n")


def check_not_twice(w, spool, capsys, held):
    """The open figures hold only the prompts the ledger does not list, once each, whatever `held` is."""
    ledger(spool, held)
    rest = [i for i, p in enumerate(PROMPTS) if p not in held]
    o = rework_json(w, capsys)["open_sessions"]
    assert (o["sessions"], o["missing"], o["prompts"]) == (1, 0, len(rest)), o
    got = o["rework_split"]["work"]["direct"].get(OPUS, {"in": 0})["in"]
    assert got == sum(i + 1 for i in rest), (held, o)


@pytest.mark.parametrize("n", range(len(PROMPTS) + 1))
def test_cost_open_session_reopened_counts_each_prompt_once(sprint, spool, capsys, n):
    """The first n prompts are in the sidecar (and the ledger), the session reopened: only the others are open."""
    plant(spool, SID, sprint["tk"])
    cost_sidecar(sprint["repo"], "20261002T100000Z-bbbbbbbb",
                 [{"item": sprint["tk"], "prompts": n, "main": {OPUS: counts(1)}}])
    check_not_twice(sprint, spool, capsys, PROMPTS[:n])
    assert rework_json(sprint, capsys)["prompts"] == n  # the sidecar figures above are the same


def test_cost_open_session_reopened_ledger_of_other_sessions_and_junk_change_nothing(sprint, spool, capsys):
    """A ledger naming another session, a damaged file or a non-list entry leaves the open figures whole."""
    plant(spool, SID, sprint["tk"])
    ledger(spool, PROMPTS, sid="-".join(("dddddddd", "0000", "4000", "8000", "000000000002")))
    assert rework_json(sprint, capsys)["open_sessions"]["prompts"] == 3
    (spool.parent / ql_distill.WORKED_NAME).write_text("{not json", encoding="utf-8")
    assert rework_json(sprint, capsys)["open_sessions"]["prompts"] == 3
    (spool.parent / ql_distill.WORKED_NAME).write_text(json.dumps({SID: "p0", "x": [1, None]}), encoding="utf-8")
    assert rework_json(sprint, capsys)["open_sessions"]["prompts"] == 3


def test_cost_open_session_reopened_the_marker_does_not_overstate(sprint, spool, capsys):
    """Every prompt in the ledger: the open figures hold none of them, and the text still says nothing was read."""
    plant(spool, SID, sprint["tk"])
    ledger(spool, PROMPTS)
    out = cost_out(sprint["repo"], capsys, sprint["sp"], "--rework")
    assert "0 prompt(s) read from their spool, not in the figures above" in out and "no figure yet" in out


def test_cost_open_session_reopened_old_behaviour_fails_the_check(sprint, spool, capsys, monkeypatch):
    """Planted failure: the old code gave plan_work no ledger, so a reopened session's sidecar prompts counted twice."""
    plant(spool, SID, sprint["tk"])
    real = ql_distill.plan_work
    monkeypatch.setattr(ql_distill, "plan_work", lambda sessions, worked, sprint_of=None: real(sessions, {}, sprint_of))
    with pytest.raises(AssertionError):
        check_not_twice(sprint, spool, capsys, PROMPTS[:2])
