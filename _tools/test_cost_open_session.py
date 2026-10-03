"""backlog.py cost --rework while the session that ran the sprint is still open: the work sidecar holds only closed
sessions, so the figures come from the open session's spool (bl_cost.open_lines), marked as provisional; a session
that has no usage rows yet says so instead of printing zeros as if nothing happened; a closed session reads as before.

The spool is a throwaway directory the test points `ql_capture.spool_dir` at: no real query log is read or written.
The planted failure is the old behaviour (no open session read), which the same checks must reject.
"""
import json
import time
from pathlib import Path

import pytest

import backlog
import bl_cost
import bl_testkit
import kbusage
import ql_capture
from test_bl_cost import cost_out, cost_sidecar

bl_testkit.bind(backlog)

repo, sprint = bl_testkit.repo, bl_testkit.sprint

OPUS = "claude-opus-5-5"
SID = "cccccccc-0000-4000-8000-000000000001"
MARK = "open session figures (the session has not closed: provisional until it does)"


def counts(n):
    return {"requests": 1, "in": n, "cw": 10 * n, "cw1h": 0, "cr": 100 * n, "out": n}


def spool_rows(sid, item, usage=True):
    """p0 claims the item, p1 is plain work, p2 closes it with `done`; each prompt has a usage row when `usage`."""
    rows, n = [], 0
    for i, work in enumerate((("claim", item), (None, None), ("done", item))):
        kinds = [("prompt", {"prompt": "text"})]
        if work[0]:
            kinds.append(("work", {"action": work[0], "item": work[1]}))
        if usage:
            kinds.append(("usage", {"reader": kbusage.READER_VERSION,
                                    "usage": {"main": {OPUS: counts(i + 1)}, "start": 1000 + i}}))
        for surface, extra in kinds:
            n += 1
            ts = time.strftime("2026-10-03T09:00:%02d.000Z", time.gmtime(n))
            rows.append({"id": f"{sid[:23]}-{n:012x}", "ts": ts, "v": 1, "session_id": sid, "prompt_id": f"p{i}",
                         "surface": surface, **extra})
    return rows


def plant(spool, sid, item, usage=True, closed=False):
    spool.mkdir(parents=True, exist_ok=True)
    (spool / f"{sid}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in spool_rows(sid, item, usage)),
                                        encoding="utf-8", newline="\n")
    if closed:
        (spool / f"{sid}.end").touch()


@pytest.fixture
def spool(tmp_path, monkeypatch):
    d = tmp_path / "spool"
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: d)
    return d


def rework_json(w, capsys):
    return json.loads(cost_out(w["repo"], capsys, w["sp"], "--rework", "--format", "json"))


def check_open_figures(w, capsys):
    """The sprint's report holds the open session's three prompts, flagged, and the text says provisional."""
    rep = rework_json(w, capsys)
    o = rep["open_sessions"]
    assert (o["sessions"], o["missing"], o["prompts"]) == (1, 0, 3), o
    assert o["rework_split"]["work"]["prompts"] == 3 and o["rework_split"]["work"]["direct"][OPUS]["in"] == 1 + 2 + 3, o
    assert rep["prompts"] == 0  # the sidecar figures above are untouched: the open ones are an addition
    assert MARK in cost_out(w["repo"], capsys, w["sp"], "--rework")


def test_cost_open_session_figures_read_from_the_spool(sprint, spool, capsys):
    """An open session that claimed and closed a task has figures, not zeros, and no sidecar is written."""
    plant(spool, SID, sprint["tk"])
    check_open_figures(sprint, capsys)
    assert not list((Path(sprint["repo"]) / "kb" / "_querylog").rglob("*.jsonl"))  # read-only
    assert sorted(p.name for p in spool.iterdir()) == [f"{SID}.jsonl"]  # no marker, nothing moved
    task = json.loads(cost_out(sprint["repo"], capsys, sprint["tk"], "--rework", "--format", "json"))
    assert task["open_sessions"]["prompts"] == 3 and task["open_sessions"]["rework_split"]["items"] == []


def test_cost_open_session_figures_without_usage_say_the_wait(sprint, spool, capsys):
    """Work rows with no usage row yet: never a bare zero, the output says the session is open and nothing is read."""
    plant(spool, SID, sprint["tk"], usage=False)
    rep = rework_json(sprint, capsys)
    o = rep["open_sessions"]
    assert rep["prompts"] == 0 and (o["sessions"], o["missing"], o["prompts"]) == (1, 3, 0)
    out = cost_out(sprint["repo"], capsys, sprint["sp"], "--rework")
    assert MARK in out and "no figure yet" in out and "not that no work happened" in out


def test_cost_open_session_figures_no_work_is_a_plain_zero(sprint, spool, capsys):
    """No open session with work in the scope: no marker, so a zero means no work rows were read."""
    out = cost_out(sprint["repo"], capsys, sprint["sp"], "--rework")
    assert "open session figures" not in out and "0 prompt(s)" in out
    plant(spool, SID, "TK-zzzzzzzz")  # an item outside the sprint
    assert "open session figures" not in cost_out(sprint["repo"], capsys, sprint["sp"], "--rework")


def test_cost_open_session_figures_closed_session_reads_as_before(sprint, spool, capsys):
    """A closed session (its end marker) is the sidecar's, not read from the spool; the report is the sidecar's."""
    plant(spool, SID, sprint["tk"], closed=True)
    cost_sidecar(sprint["repo"], "20261002T100000Z-bbbbbbbb",
                 [{"item": sprint["tk"], "prompts": 2, "main": {OPUS: counts(5)}}])
    rep = rework_json(sprint, capsys)
    assert rep["open_sessions"]["sessions"] == 0 and rep["prompts"] == 2, rep
    assert "open session figures" not in cost_out(sprint["repo"], capsys, sprint["sp"], "--rework")
    assert rework_json(sprint, capsys)["direct"][OPUS]["in"] == 5


def test_cost_open_session_figures_old_behaviour_fails_the_check(sprint, spool, capsys, monkeypatch):
    """Planted failure: the old code read no open session and printed zero with nothing else; the check rejects it."""
    plant(spool, SID, sprint["tk"])
    monkeypatch.setattr(bl_cost, "open_lines", lambda root, rework=True: ([], []))
    with pytest.raises(AssertionError):
        check_open_figures(sprint, capsys)
