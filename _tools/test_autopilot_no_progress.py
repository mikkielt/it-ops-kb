"""A sprint whose last two runs landed nothing is not restarted: `bounds stop --runs-landed` names `no-progress`.

The tick supplies the landed count (and end cause) of each recorded run, oldest first; the skill states the rule, so
the test also reads its text. Planted runs, never a real sprint's history.
"""
import json
from pathlib import Path

import pytest

import backlog
import bl_base
import bl_bounds
import bl_testkit
from bl_testkit import b
from conftest import KB

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

SKILL = Path(KB) / ".claude" / "skills" / "kb-autopilot" / "SKILL.md"
RUNS = [
    ("0,0", True), ("0,1", False), ("1,0,0", True), ("0", False), ("", False), ("3", False), ("0,0,0", True),
    ("2,0,1", False), ("0,0,1", False), ("1,1", False), ("5,0,0,0,0", True), ("0,1,0", False),
]


def parsed(text):
    return bl_bounds.parse_runs(text) if text else []


@pytest.mark.parametrize("text, stops", RUNS)
def test_autopilot_no_progress_stops_restarts_over_planted_runs(sprint, text, stops):
    st = bl_bounds.stop_state(bl_base.Backlog(sprint["repo"]), sprint["sp"], rows=[], runs=parsed(text))
    assert ("no-progress" in st["causes"]) is stops, (text, st)
    assert st["stop"] is stops and st["cause"] == ("no-progress" if stops else None)


def test_autopilot_no_progress_stops_restarts_a_run_that_landed_something_resets_the_count(sprint):
    bl = bl_base.Backlog(sprint["repo"])
    for zeros in range(0, 7):
        runs = [(1, "landed-limit")] + [(0, "compaction")] * zeros
        st = bl_bounds.stop_state(bl, sprint["sp"], rows=[], runs=runs)
        assert st["stop"] == (zeros >= 2), zeros
        runs = [(0, "compaction")] * zeros + [(1, "landed-limit")]
        assert bl_bounds.stop_state(bl, sprint["sp"], rows=[], runs=runs)["stop"] is False, zeros


def test_autopilot_no_progress_stops_restarts_the_cli_exits_1_and_names_the_causes(sprint):
    repo_, sp = sprint["repo"], sprint["sp"]
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--runs-landed", "0:compaction,0:landed-limit")
    assert code == 1, out
    assert out.splitlines()[0] == ("bounds: stop no-progress: 2 consecutive runs landed nothing "
                                   "(causes: compaction, landed-limit)"), out
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--runs-landed", "1:compaction,0:landed-limit,0:landed-limit")
    assert code == 1 and out.splitlines()[0].endswith("(causes: landed-limit)"), out
    assert "2 consecutive runs" in out
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--runs-landed", "0:compaction,1:landed-limit")
    assert code == 0 and out.startswith("bounds: go: "), out
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--runs-landed", "0")
    assert code == 0, out  # fewer than two runs
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--runs-landed", "0,0", "--json")
    assert code == 1 and json.loads(out)["cause"] == "no-progress"
    assert b(repo_, "bounds", "stop", "--sprint", sp, "--runs-landed", "x,0")[0] == 2


def test_autopilot_no_progress_stops_restarts_it_is_listed_with_the_other_causes_in_order(sprint):
    st = bl_bounds.stop_state(bl_base.Backlog(sprint["repo"]), sprint["sp"], 1, 1, rows=[], runs=[(0, ""), (0, "")])
    assert st["causes"] == ["sprint-budget", "no-progress"]
    assert tuple(sorted(st["causes"], key=bl_bounds.STOPS.index)) == tuple(st["causes"])
    assert st["detail"]["no-progress"] == "2 consecutive runs landed nothing"


def skill_problems(text):
    low = text.lower()
    out = []
    if "no progress" not in low and "no-progress" not in low:
        out.append("the restart step does not name no progress")
    for phrase in ("--runs-landed", "bounds: stop no-progress", "PushNotification"):
        if phrase not in text:
            out.append(f"missing `{phrase}`")
    return out


def test_autopilot_no_progress_stops_restarts_the_skill_states_the_rule():
    assert skill_problems(SKILL.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("old, want", [
    ("no progress", "no progress"), ("--runs-landed", "--runs-landed"), ("PushNotification", "PushNotification"),
    ("bounds: stop no-progress", "bounds: stop no-progress"),
])
def test_autopilot_no_progress_stops_restarts_the_skill_check_refuses_a_text_without_the_rule(old, want):
    text = SKILL.read_text(encoding="utf-8").replace(old, "x")
    if old == "no progress":
        text = text.replace("no-progress", "x")
    assert any(want in p for p in skill_problems(text)), skill_problems(text)
