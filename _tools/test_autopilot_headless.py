"""Inside a headless run (KB_HEADLESS_RUNNER) `autopilot.py runner start` and `runner reset` are refused, exit 2, with
no worktree, no status and no runner record written, so a runner never starts a nested runner whose claude child
would outlive its deadline; without the variable both work as before (kb/_self/tools.md, The autopilot runner)."""
import pytest

import autopilot, bl_base
from test_autopilot import World, SP, stream


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.delenv(autopilot.HEADLESS_ENV, raising=False)
    return World(tmp_path, monkeypatch)


@pytest.mark.parametrize("args", [["runner", "start", SP], ["runner", "start", SP, "--landed", "1"],
                                  ["runner", "reset", SP]])
def test_runner_refused_when_headless(world, monkeypatch, capsys, args):
    monkeypatch.setenv(autopilot.HEADLESS_ENV, "1")
    world.stream(stream())
    assert autopilot.main(args) == 2
    assert "only in the manager session" in capsys.readouterr().err
    assert not world.wt().exists() and not (autopilot.cache_dir(world.root, SP) / "status.json").exists()
    assert not bl_base.live_runners()


def test_runner_refused_when_headless_not_without_the_variable(world):
    """The planted contrast: the manager session's start runs the fake claude and keeps its status."""
    world.stream(stream())
    assert world.start() == 0
    assert world.wt().exists() and world.status()["cause"] == "landed-limit"


def test_runner_refused_when_headless_in_the_functions_too(world, monkeypatch):
    """runner_start and reset_worktree refuse themselves, so a caller that is not the command line is refused too."""
    monkeypatch.setenv(autopilot.HEADLESS_ENV, "1")
    with pytest.raises(bl_base.Refused, match="manager session"):
        world.start()
    with pytest.raises(bl_base.Refused, match="manager session"):
        autopilot.reset_worktree(world.root, SP)
    assert not world.wt().exists()


def test_runner_refused_when_headless_reads_only_still_work(world, monkeypatch, capsys):
    monkeypatch.setenv(autopilot.HEADLESS_ENV, "1")
    assert autopilot.main(["status", "--hook"]) == 0
    assert autopilot.main(["runner-status", SP]) in (0, 1)  # 1: no run recorded; never refused
    assert "only in the manager session" not in capsys.readouterr().err
