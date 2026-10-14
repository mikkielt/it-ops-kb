"""The suite's ceiling (tests.py, _tools/tests_ceiling.json): the live file is accepted and holds the suite, and each
way to break it is refused."""
import json

import pytest

import tests

NUMBERS = {"max_ids": 3, "max_files": 2, "max_seconds": {"darwin": 5, "linux": 6, "win32": 7}}
HEADER = "id,text,by,by_ref,source,date,context,status,invalidated_reason,invalidated_date,supersedes,review_by,links\n"


def planted(tmp_path, by="operator", status="active", text=None, **numbers):
    """A ceiling file and a decisions ledger whose one decision D-planted is (text, by, status)."""
    c = {**NUMBERS, **numbers, "decision": "D-planted"}
    path, ledger = tmp_path / "ceiling.json", tmp_path / "_decisions.csv"
    path.write_text(json.dumps(c), encoding="utf-8")
    text = tests.ceiling_token({**NUMBERS, "decision": "D-planted"}) if text is None else text
    ledger.write_text(HEADER + f'D-planted,"{text}",{by},{by},a gate,2026-01-01,item:ST-aaaaaaaa,{status},,,,,\n',
                      encoding="utf-8")
    return str(path), str(ledger)


def test_live_ceiling_holds_the_suite_and_recorded_numbers_are_accepted_and_a_raised_number_or_a_decision_not_the_operators_is_refused(tmp_path):
    c = tests.read_ceiling()
    assert tests.ceiling_problems(c, files=len(tests.test_files())) == []
    assert tests.read_ceiling(*planted(tmp_path))["max_ids"] == 3
    for change in ({"max_ids": 4}, {"max_seconds": {"darwin": 50, "linux": 6, "win32": 7}}):  # a raised number
        with pytest.raises(tests.CeilingError, match="operator's recorded answer"):
            tests.read_ceiling(*planted(tmp_path, **change))
    for who in ({"by": "agent"}, {"status": "invalidated"}):  # a decision not the operator's or not active
        with pytest.raises(tests.CeilingError):
            tests.read_ceiling(*planted(tmp_path, **who))


def test_counts_over_the_ceiling_are_named_and_the_seconds_factor_applies_only_on_a_ci_runner_and_changed_paths_pick_the_scope():
    c = {**NUMBERS, "decision": "D-planted"}
    assert tests.ceiling_problems(c, files=2, ids=3, seconds=5.0, platform="darwin") == []
    over = tests.ceiling_problems(c, files=3, ids=4, seconds=5.5, platform="darwin")
    assert len(over) == 3 and "replaces one" in over[1]
    assert tests.seconds_factor({"KB_TEST_TIMEOUT_FACTOR": "3"}) == 1.0
    assert tests.seconds_factor({"GITLAB_CI": "true", "KB_TEST_TIMEOUT_FACTOR": "3"}) == 3.0
    assert tests.scope(["kb/_self/backlog/ST-aaaaaaaa.json", "kb/_querylog/ops/x.jsonl"]) == "none"
    assert tests.scope(["kb/public/auth/kerberos.md", "kb/_self/backlog/ST-aaaaaaaa.json"]) == "content"
    assert tests.scope(["kb/public/auth/kerberos.md", "_tools/check.py"]) == "all"
