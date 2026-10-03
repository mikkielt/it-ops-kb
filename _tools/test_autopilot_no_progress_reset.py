"""`bounds reset-runs --sprint SP` clears the run history the no-progress stop reads (bl_base.runs_path), so a sprint
stopped for no progress is restarted once the cause is fixed. Planted runs in a throwaway repository, never a real
sprint's history."""
import pytest

import backlog
import bl_base
import bl_testkit
from bl_testkit import b

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    for var in ("KB_TESTS_FAST", "KB_TEST_WORKERS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "hostlocks"))


def plant(sprint, *runs):
    for landed, cause in runs:
        bl_base.append_run(sprint["repo"], sprint["sp"], cause, landed, "2026-01-01T00:00:00Z")


def stop(sprint):
    return b(sprint["repo"], "bounds", "stop", "--sprint", sprint["sp"], "--json")


def test_no_progress_reset_clears_the_stop(sprint):
    plant(sprint, (0, "compaction"), (0, "landed-limit"))
    code, out = stop(sprint)
    assert code == 1 and '"no-progress"' in out, out
    code, out = b(sprint["repo"], "bounds", "reset-runs", "--sprint", sprint["sp"])
    assert code == 0 and "cleared 2 run(s)" in out, out
    assert not bl_base.runs_path(sprint["repo"], sprint["sp"]).exists()
    code, out = stop(sprint)
    assert '"no-progress"' not in out, out
    plant(sprint, (0, "compaction"))  # a run after the reset starts a new count
    assert '"no-progress"' not in stop(sprint)[1]
    plant(sprint, (0, "compaction"))
    assert stop(sprint)[0] == 1


def test_no_progress_reset_clears_the_stop_is_idempotent_and_leaves_other_sprints(sprint):
    plant(sprint, (0, "error"), (0, "blocked"))
    other = bl_base.runs_path(sprint["repo"], "SP-other0000")
    other.parent.mkdir(parents=True)
    other.write_text("x\n", encoding="utf-8")
    assert "cleared 2 run(s)" in b(sprint["repo"], "bounds", "reset-runs", "--sprint", sprint["sp"])[1]
    code, out = b(sprint["repo"], "bounds", "reset-runs", "--sprint", sprint["sp"])
    assert code == 0 and "cleared 0 run(s)" in out, out
    assert other.exists()


def test_no_progress_reset_clears_the_stop_refuses_an_unknown_sprint_and_a_missing_one(sprint):
    code, out = b(sprint["repo"], "bounds", "reset-runs", "--sprint", "SP-nosuch00")
    assert code != 0, out
    assert not bl_base.runs_path(sprint["repo"], "SP-nosuch00").exists()
    code, out = b(sprint["repo"], "bounds", "reset-runs")
    assert code != 0, out
