"""A SIGTERM or SIGHUP that reaches `runner start` before its child runs (autopilot.py): the status is written, with
cause error and the signal's name, over the previous run's status.json. The tests named
autopilot_early_signal_writes_status are the bug's checks. RunnerEnded is raised by a planted function, no signal is
sent; the sprint id, the root and the host lock directory are temporary."""
import json

import pytest

import autopilot

SP = "SP-aaaaaaaa"


@pytest.fixture
def root(tmp_path, monkeypatch):
    for var in ("KB_TESTS_FAST", "KB_TEST_WORKERS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "locks"))
    r = tmp_path / "clone"
    r.mkdir()
    directory = autopilot.cache_dir(r, SP)
    directory.mkdir(parents=True)
    (directory / "status.json").write_text(json.dumps({"sprint": SP, "cause": "sprint-done", "detail": "older run",
                                                       "pid": 1}), encoding="utf-8")
    return r


def status_of(root):
    return json.loads((autopilot.cache_dir(root, SP) / "status.json").read_text(encoding="utf-8"))


def planted_end(name):
    def raiser(*args, **kwargs):
        raise autopilot.RunnerEnded(name)
    return raiser


def test_autopilot_early_signal_writes_status_in_register_runner(root, monkeypatch):
    monkeypatch.setattr(autopilot, "register_runner", planted_end("SIGTERM"))
    assert autopilot.runner_start(SP, root=root) == 1
    st = status_of(root)
    assert st["cause"] == "error" and "SIGTERM" in st["detail"]
    assert st["sprint"] == SP and st["ended"] and st["detail"] != "older run"


def test_autopilot_early_signal_writes_status_in_prepare_worktree(root, monkeypatch, tmp_path):
    monkeypatch.setattr(autopilot, "prepare_worktree", planted_end("SIGHUP"))
    assert autopilot.runner_start(SP, root=root) == 1
    st = status_of(root)
    assert st["cause"] == "error" and "SIGHUP" in st["detail"]
    assert st["pid"] != 1 and st["ended"]
    assert not list((tmp_path / "locks").glob("kb-runner.*.json"))  # the slot record is gone


def test_autopilot_early_signal_writes_status_when_no_status_existed(root, monkeypatch):
    (autopilot.cache_dir(root, SP) / "status.json").unlink()
    monkeypatch.setattr(autopilot, "register_runner", planted_end("SIGTERM"))
    assert autopilot.runner_start(SP, root=root) == 1
    assert status_of(root)["cause"] == "error"


def test_autopilot_early_signal_after_own_status_keeps_the_runs_status(root, monkeypatch, tmp_path):
    """A run that already kept its status ends it itself: the early writer does not run over it."""
    def run(sprint, landed, root_, record, kept=None):
        kept.append(True)
        raise autopilot.RunnerEnded("SIGTERM")
    monkeypatch.setattr(autopilot, "register_runner", lambda r, s: tmp_path / "record.json")
    monkeypatch.setattr(autopilot, "run_in_slot", run)
    autopilot.runner_start(SP, root=root)
    assert status_of(root)["detail"] == "older run"
