"""What `autopilot.py status` lists of the runs recorded under _cache/autopilot, and what `backlog.py close` leaves
there: only sprints that still have an item file, a failed run (`ended error`, `ended timeout`) before the others, each
group newest first, so a failed run is never hidden behind `+K more`; and the sprint's cache directory gone once it is
closed. The tests named autopilot_status_hides_no_failed_run are the bug's checks. No process starts: the records are
written by hand, and the host's runner records are a directory of the test's own."""
import json
from pathlib import Path

import pytest

import autopilot, backlog, bl_land, bl_testkit
from bl_testkit import b, sprint as _sprint_fixture, repo as _repo_fixture
from test_bl_land import finish

bl_testkit.bind(backlog)
repo, sprint = _repo_fixture, _sprint_fixture

SHOW = autopilot.SHOW


@pytest.fixture(autouse=True)
def no_live_runner(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path_factory.mktemp("hostlocks")))


def sid(n):
    """The sprint id of number N: eight characters of the id alphabet."""
    return "SP-" + "abcdefghijklmnopqrstuvwxyz"[n % 26] * 4 + "aaaa"


def stamp(n):
    return f"2026-03-{1 + n // 24:02d}T{n % 24:02d}:00:00Z"


def record(root, sprint_id, cause, n):
    d = Path(root) / "_cache" / "autopilot" / sprint_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(json.dumps({"sprint": sprint_id, "cause": cause, "ended": stamp(n)}),
                                   encoding="utf-8")


def item_file(root, sprint_id):
    d = Path(root) / backlog.REL_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sprint_id}.json").write_text(json.dumps({"id": sprint_id, "kind": "sprint"}), encoding="utf-8")


def listed(root, show=SHOW):
    """The sprint ids the runners line names, in order, and whether it ends in `+K more`."""
    (line,) = autopilot.runner_lines(str(root), show)
    body = line.split(": ", 1)[1] if line else ""
    return [x.split()[0] for x in body.split(", ")], "more" in body


def check_failed_first_newest_first(root, runs):
    """RUNS is [(sprint, cause, n)] of the records written; the listing leads with the failed ones, each group by n
    descending, and names a failed run whatever SHOW cuts."""
    names, _ = listed(root, 99)
    failed = [s for s, c, n in sorted(runs, key=lambda r: -r[2]) if c in autopilot.FAIL_CAUSES]
    rest = [s for s, c, n in sorted(runs, key=lambda r: -r[2]) if c not in autopilot.FAIL_CAUSES]
    assert names == failed + rest, f"{names} is not {failed + rest}"
    shown, _ = listed(root, SHOW)
    assert set(failed[:SHOW]) <= set(shown), f"a failed run is hidden: {shown} of {names}"


def test_autopilot_status_hides_no_failed_run_whatever_its_place_among_the_records(tmp_path):
    """Every count of records and every place of the one failed run among them, with and without item files."""
    for with_items in (True, False):
        for total in range(1, 9):
            for place in range(total):
                root = tmp_path / f"{with_items}-{total}-{place}"
                runs = [(sid(i), "error" if i == place else "sprint-done", i) for i in range(total)]
                for s, c, n in runs:
                    record(root, s, c, n)
                    if with_items:
                        item_file(root, s)
                check_failed_first_newest_first(root, runs)


def test_autopilot_status_hides_no_failed_run_timeout_and_killed_run_lead_too(tmp_path):
    """`ended timeout` and a `running` record no live runner holds (`ended error`) lead, newest first, over a later
    `sprint-done`, `blocked` and `landed-limit`."""
    runs = [(sid(0), "timeout", 0), (sid(1), "sprint-done", 5), (sid(2), "blocked", 6), (sid(3), "running", 3),
            (sid(4), "landed-limit", 7), (sid(5), "error", 1)]
    for s, c, n in runs:
        record(tmp_path, s, c, n)
        item_file(tmp_path, s)
    names, more = listed(tmp_path, 99)
    assert names == [sid(3), sid(5), sid(0), sid(4), sid(2), sid(1)], names
    (line,) = autopilot.runner_lines(str(tmp_path), 99)
    assert f"{sid(3)} ended error" in line and f"{sid(0)} ended timeout" in line and "running" not in line, line
    shown, more = listed(tmp_path, SHOW)
    assert shown == [sid(3), sid(5), sid(0)] and more


def test_autopilot_status_hides_no_failed_run_of_a_closed_sprint(tmp_path):
    """A record whose sprint has no item file (the sprint was closed) is not listed, the failed one included; the
    other sprints of the root keep theirs."""
    record(tmp_path, sid(0), "error", 0)  # closed: no item file
    record(tmp_path, sid(1), "sprint-done", 1)
    record(tmp_path, sid(2), "timeout", 2)
    item_file(tmp_path, sid(1))
    item_file(tmp_path, sid(2))
    assert listed(tmp_path, 99)[0] == [sid(2), sid(1)]
    (Path(tmp_path) / backlog.REL_DIR / f"{sid(2)}.json").unlink()  # planted: the filter is by the item file
    assert listed(tmp_path, 99)[0] == [sid(1)]


def test_autopilot_status_hides_no_failed_run_in_a_bare_cache(tmp_path):
    """A root with no item files at all (a bare cache) lists every record, so nothing is hidden for want of a backlog."""
    for i, c in enumerate(("sprint-done", "sprint-done", "sprint-done", "error")):
        record(tmp_path, sid(i), c, i)
    names, more = listed(tmp_path, SHOW)
    assert names[0] == sid(3) and more, names


def test_autopilot_status_hides_no_failed_run_planted_wrong_orders_are_caught(tmp_path):
    """The order check is not vacuous: the listing by sprint id (the old order), or the oldest first, fails it."""
    runs = [(sid(0), "sprint-done", 0), (sid(1), "sprint-done", 1), (sid(2), "sprint-done", 2), (sid(3), "error", 3),
            (sid(4), "timeout", 4), (sid(5), "sprint-done", 5)]
    for s, c, n in runs:
        record(tmp_path, s, c, n)
    check_failed_first_newest_first(tmp_path, runs)
    old = autopilot.ended_runs

    def by_name(root, live):
        return [f"{s} ended {c}" for s, c, n in sorted(runs)]

    def oldest_first(root, live):
        return [f"{s} ended {c}" for s, c, n in sorted(runs, key=lambda r: (r[1] not in autopilot.FAIL_CAUSES, r[2]))]

    try:
        for planted in (by_name, oldest_first):
            autopilot.ended_runs = planted
            with pytest.raises(AssertionError):
                check_failed_first_newest_first(tmp_path, runs)
    finally:
        autopilot.ended_runs = old


def test_autopilot_status_hides_no_failed_run_close_prunes_the_sprints_cache(sprint):
    """`backlog.py close` removes _cache/autopilot/<sprint> of the sprint it closes and no other one."""
    repo_, sp = sprint["repo"], sprint["sp"]
    other = sid(7)
    finish(sprint)
    record(repo_, sp, "error", 1)
    (repo_ / "_cache" / "autopilot" / sp / "20260301T000000Z.jsonl").write_text("{}\n", encoding="utf-8")
    record(repo_, other, "sprint-done", 2)
    code, out = b(repo_, "close", sp, "--summary")
    assert code == 0 and (repo_ / "_cache" / "autopilot" / sp).is_dir(), "--summary prunes nothing"
    code, out = b(repo_, "close", sp)
    assert code == 0 and f"closed {sp}" in out, out
    assert not (repo_ / "_cache" / "autopilot" / sp).exists(), out
    assert (repo_ / "_cache" / "autopilot" / other / "status.json").is_file()


def test_autopilot_status_hides_no_failed_run_prune_removes_only_the_named_sprint(tmp_path):
    """The prune of a sprint id, planted: an id that is not a sprint's, a missing directory and a link are left alone."""
    record(tmp_path, sid(0), "error", 0)
    record(tmp_path, sid(1), "error", 1)
    bl_land.prune_runner_cache(tmp_path, sid(2))  # no directory: nothing happens
    bl_land.prune_runner_cache(tmp_path, "..")  # not an id
    assert (tmp_path / "_cache" / "autopilot" / sid(0)).is_dir() and (tmp_path / "_cache" / "autopilot").is_dir()
    bl_land.prune_runner_cache(tmp_path, sid(0))
    assert not (tmp_path / "_cache" / "autopilot" / sid(0)).exists()
    assert (tmp_path / "_cache" / "autopilot" / sid(1) / "status.json").is_file()
