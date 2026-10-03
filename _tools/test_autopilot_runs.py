"""The runs history the runner keeps itself (`_cache/autopilot/SP/runs.jsonl`): `runner start` appends one line when a
run ends, whatever its cause, and `bounds stop` reads no-progress from that file, never from the manager's state.json.
The tests named runs_history_in_tool_code are the item's checks."""
import itertools
import json
import os

import pytest

import autopilot
import backlog
import bl_base
import bl_testkit
from bl_testkit import b
from test_autopilot import SP, T1, T2, World, done, stream

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.delenv("KB_HEADLESS_RUNNER", raising=False)
    return World(tmp_path, monkeypatch)


def lines(root, sp=SP):
    path = bl_base.runs_path(root, sp)
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def plant(root, sp, runs, raw=None):
    """Write the history file by hand: RUNS [(landed, cause)], then RAW text."""
    path = bl_base.runs_path(root, sp)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps({"sprint": sp, "cause": c, "landed": n, "time": "2026-10-01T10:00:00Z"}) + "\n"
                   for n, c in runs)
    path.write_text(text + (raw or ""), encoding="utf-8", newline="\n")


def stop(sp_, extra=()):
    return b(sp_["repo"], "bounds", "stop", "--sprint", sp_["sp"], *extra)


def test_runs_history_in_tool_code_the_file_name_is_the_tools(sprint):
    assert autopilot.RUNS_FILE == "runs.jsonl"
    assert bl_base.runs_path("/r", SP).as_posix() == f"/r/_cache/autopilot/{SP}/runs.jsonl"


@pytest.mark.parametrize("cause", ["landed-limit", "sprint-done", "blocked", "compaction"])
def test_runs_history_in_tool_code_runner_start_writes_one_line_at_the_end(world, cause):
    world.stream(stream(boundary=cause == "compaction", final=f"x\nsprint-runner: {cause}"))
    world.start()
    got = lines(world.root)
    assert len(got) == 1 and got[0]["sprint"] == SP and got[0]["cause"] == cause and got[0]["landed"] == 0
    assert got[0]["time"] == world.status()["ended"] and set(got[0]) == {"sprint", "cause", "landed", "time"}


def test_runs_history_in_tool_code_an_error_run_is_written_too(world, monkeypatch):
    monkeypatch.setattr(autopilot, "CLAUDE", [str(world.tmp / "no-such-claude")])
    assert world.start() == 1
    assert [x["cause"] for x in lines(world.root)] == ["error"]


def test_runs_history_in_tool_code_a_result_that_names_no_cause_is_an_error_line(world):
    world.stream(stream(final="nothing named"))
    world.start()
    assert [x["cause"] for x in lines(world.root)] == ["error"]


def test_runs_history_in_tool_code_the_landed_count_is_the_runs_own(world, monkeypatch):
    real = autopilot.supervise

    def commit_then_run(*a, **k):
        done(world, T1)
        done(world, T2)
        return real(*a, **k)

    monkeypatch.setattr(autopilot, "supervise", commit_then_run)
    world.stream(stream())
    world.start()
    assert lines(world.root)[0]["landed"] == 2
    monkeypatch.setattr(autopilot, "supervise", real)
    world.stream(stream())
    world.start()
    assert [x["landed"] for x in lines(world.root)] == [2, 0]  # the next run starts at the new tip: it landed nothing


def test_runs_history_in_tool_code_a_run_ended_by_a_signal_is_written(world, monkeypatch):
    def killed(*a, **k):
        raise autopilot.RunnerEnded("SIGTERM")

    monkeypatch.setattr(autopilot, "register_runner", killed)
    assert world.start() == 1
    got = lines(world.root)
    assert len(got) == 1 and got[0]["cause"] == "error" and got[0]["landed"] == 0


def test_runs_history_in_tool_code_a_signal_during_the_child_writes_once(world, monkeypatch):
    def killed(*a, **k):
        raise autopilot.RunnerEnded("SIGHUP")

    monkeypatch.setattr(autopilot, "supervise", killed)
    world.stream(stream())
    assert world.start() == 1
    assert [x["cause"] for x in lines(world.root)] == ["error"]


def test_runs_history_in_tool_code_a_refused_start_is_no_run(world, monkeypatch):
    monkeypatch.setattr(autopilot, "register_runner", lambda *a: (_ for _ in ()).throw(bl_base.Refused("full")))
    with pytest.raises(bl_base.Refused):
        world.start()
    assert lines(world.root) == []


def test_runs_history_in_tool_code_lines_are_appended_never_rewritten(world):
    seen = b""
    for n, cause in enumerate(["landed-limit", "blocked", "sprint-done"], 1):
        world.stream(stream(final=f"x\nsprint-runner: {cause}"))
        world.start()
        raw = bl_base.runs_path(world.root, SP).read_bytes()
        assert raw.startswith(seen) and raw.count(b"\n") == n and raw.endswith(b"\n")
        seen = raw


def test_runs_history_in_tool_code_a_line_is_one_write(tmp_path, monkeypatch):
    calls = []
    real = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: calls.append(data) or real(fd, data))
    bl_base.append_run(tmp_path, SP, "blocked", 3, "2026-10-01T10:00:00Z")
    bl_base.append_run(tmp_path, SP, "error", 0, "2026-10-01T11:00:00Z")
    assert len(calls) == 2 and all(c.endswith(b"\n") and c.count(b"\n") == 1 for c in calls)
    assert [x["landed"] for x in lines(tmp_path)] == [3, 0]


def test_runs_history_in_tool_code_a_failed_write_never_changes_the_runs_exit(world, monkeypatch, capsys):
    monkeypatch.setattr(bl_base, "append_run", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    world.stream(stream())
    assert world.start() == 0
    assert "cannot record the run" in capsys.readouterr().err


# ---------------------------------------------------------------- bounds stop reads the file

CAUSES = ("landed-limit", "compaction", "error", "blocked", "sprint-done", "timeout")


@pytest.mark.parametrize("size", range(0, 6))
def test_runs_history_in_tool_code_bounds_stop_over_every_history_of_up_to_five_runs(sprint, size):
    sp_ = sprint["sp"]
    for landed in itertools.product((0, 1), repeat=size):
        causes = [CAUSES[(i * 5 + k) % len(CAUSES)] for i, k in enumerate(landed)]
        plant(sprint["repo"], sp_, list(zip(landed, causes)))
        code, out = stop(sprint)
        want = size >= 2 and landed[-1] == 0 and landed[-2] == 0
        assert (code == 1 and "no-progress" in out) is want, (landed, out)
        if want:
            assert out.splitlines()[0].startswith("bounds: stop no-progress: ")


@pytest.mark.parametrize("cause", ["error", "blocked", "timeout"])
def test_runs_history_in_tool_code_error_and_blocked_runs_count_as_no_progress(sprint, cause):
    plant(sprint["repo"], sprint["sp"], [(0, cause), (0, cause)])
    code, out = stop(sprint)
    assert code == 1 and out.splitlines()[0] == f"bounds: stop no-progress: 2 consecutive runs landed nothing (causes: {cause})"


@pytest.mark.parametrize("state", ["missing", "no-runs-field", "falsified", "corrupt"])
def test_runs_history_in_tool_code_a_state_json_that_drops_or_falsifies_runs_restarts_nothing(sprint, state):
    repo_, sp_ = sprint["repo"], sprint["sp"]
    plant(repo_, sp_, [(0, "blocked"), (0, "error")])
    path = repo_ / "_cache" / "autopilot" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"missing": None, "no-runs-field": '{"tick": 9, "actions": []}',
            "falsified": json.dumps({"tick": 9, "runs": {sp_: [{"started": "x", "cause": "landed-limit", "landed": 9}]}}),
            "corrupt": "{not json"}[state]
    if body is not None:
        path.write_text(body, encoding="utf-8")
    code, out = stop(sprint)
    assert code == 1 and out.splitlines()[0].startswith("bounds: stop no-progress: "), out


def test_runs_history_in_tool_code_a_run_that_landed_something_ends_the_streak(sprint):
    plant(sprint["repo"], sprint["sp"], [(0, "error"), (0, "blocked"), (2, "landed-limit"), (0, "blocked")])
    assert stop(sprint)[0] == 0


def test_runs_history_in_tool_code_no_file_and_an_empty_file_have_no_runs(sprint):
    assert stop(sprint)[0] == 0
    bl_base.runs_path(sprint["repo"], sprint["sp"]).parent.mkdir(parents=True, exist_ok=True)
    bl_base.runs_path(sprint["repo"], sprint["sp"]).write_text("", encoding="utf-8")
    assert stop(sprint)[0] == 0


@pytest.mark.parametrize("raw", ["not json\n", "[1, 2]\n", '{"sprint": "SP-aaaaaaaa"}\n', "\x00\x01\n", '{"landed": -1}\n'])
def test_runs_history_in_tool_code_a_non_empty_file_with_no_valid_line_is_no_progress(sprint, raw):
    plant(sprint["repo"], sprint["sp"], [], raw)
    code, out = stop(sprint)
    assert code == 1 and "(causes: unreadable)" in out.splitlines()[0], out


def test_runs_history_in_tool_code_a_malformed_line_among_good_ones_is_ignored(sprint):
    plant(sprint["repo"], sprint["sp"], [(1, "landed-limit")], 'garbage\n{"sprint": 1}\n')
    assert stop(sprint)[0] == 0
    plant(sprint["repo"], sprint["sp"], [(0, "blocked"), (0, "blocked")], 'garbage\n')
    assert stop(sprint)[0] == 1
    plant(sprint["repo"], sprint["sp"], [(0, "blocked")], 'garbage\n')
    assert stop(sprint)[0] == 0  # one real run and one torn line: not yet two runs of evidence


def test_runs_history_in_tool_code_an_unreadable_file_is_no_progress(sprint):
    p = bl_base.runs_path(sprint["repo"], sprint["sp"])
    p.mkdir(parents=True)  # a directory where the file belongs: reading it fails
    code, out = stop(sprint)
    assert code == 1 and "(causes: unreadable)" in out.splitlines()[0], out


def test_runs_history_in_tool_code_only_the_sprints_own_lines_count(sprint):
    repo_, sp_ = sprint["repo"], sprint["sp"]
    other = "SP-" + "z" * 8
    plant(repo_, sp_, [(1, "landed-limit")], json.dumps({"sprint": other, "cause": "error", "landed": 0, "time": "t"})  + "\n")
    with open(bl_base.runs_path(repo_, sp_), "a", encoding="utf-8") as f:
        f.write(json.dumps({"sprint": other, "cause": "error", "landed": 0, "time": "t"}) + "\n")
    assert stop(sprint)[0] == 0
    plant(repo_, other, [(0, "error"), (0, "error")])  # another sprint's own file is not this sprint's
    assert stop(sprint)[0] == 0


def test_runs_history_in_tool_code_the_flag_still_replaces_the_file(sprint):
    plant(sprint["repo"], sprint["sp"], [(0, "error"), (0, "error")])
    assert stop(sprint, ("--runs-landed", "1"))[0] == 0
