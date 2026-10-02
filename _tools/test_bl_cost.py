"""backlog.py cost: the work sidecars summed over an item and its descendants, the shared and session figures, the items
deleted at sprint close read from git history, the work and rework split, a sprint's research and overhead apart and
`cost --research` (bl_cost.py).

Each rule has a planted failure: a sum rule broken (models merged, cw folded into in, a shared line counted once per
item, a deleted item's line dropped), a history that resolves nothing or twice, a shallow clone, git missing or
failing, and a report whose order or shape changes. The patches name the module where the code looks the name up,
`bl_cost`.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

import backlog
import bl_cost
import bl_testkit
from bl_testkit import b, commit, edit, item, sh

bl_testkit.bind(backlog)

repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


@pytest.fixture
def planned(sprint):
    """The started sprint's story with its task, plus a second sprint still planned."""
    repo = sprint["repo"]
    assert b(repo, "new", "sprint", "--title", "Later", "--goal", "g")[0] == 0
    return {**sprint, "later": item(repo, "Later")["id"]}


# --- backlog.py cost: the work sidecars summed over an item and its descendants ---

OPUS, SONNET = "claude-opus-4-7", "claude-sonnet-4-6"
COST_RUN_A, COST_RUN_B = "20261001T100000Z-aaaaaaaa", "20261002T100000Z-bbbbbbbb"


def cc(requests, inp, cw, cr, out, cw1h=0):
    return {"requests": requests, "in": inp, "cw": cw, "cw1h": cw1h, "cr": cr, "out": out}


def cost_sidecar(repo, run, lines):
    d = Path(repo) / "kb" / "_querylog" / "work" / "2026-10"
    d.mkdir(parents=True, exist_ok=True)
    items = sum(1 for w in lines if "item" in w)
    head = {"run": run, "reader": 1, "counts": {"items": items, "shared": len(lines) - items, "missing": 0}}
    (d / f"{run}.jsonl").write_text("".join(json.dumps(o) + "\n" for o in [head, *lines]), encoding="utf-8",
                                    newline="\n")


@pytest.fixture
def costed(sprint):
    """The sprint fixture with two work sidecars: run A holds the task, its story, an unrelated bug, the sprint's own
    line and a shared line of the session; run B the task again and the story with only a routed subagent."""
    repo, st, tk, bg, sp = sprint["repo"], sprint["st"], sprint["tk"], sprint["bg"], sprint["sp"]
    cost_sidecar(repo, COST_RUN_A, [
        {"item": tk, "prompts": 2, "main": {OPUS: cc(3, 10, 5, 100, 7, cw1h=2), SONNET: cc(1, 1, 0, 2, 3)},
         "sub": {"general-purpose": {OPUS: cc(2, 20, 4, 50, 9)},
                 "Explore": {OPUS: cc(1, 5, 1, 10, 1), SONNET: cc(1, 1, 1, 1, 1)}}},
        {"item": st, "prompts": 1, "main": {OPUS: cc(1, 100, 10, 1000, 70)}},
        {"item": bg, "prompts": 1, "main": {OPUS: cc(9, 9, 9, 9, 9)}},
        {"item": sp, "prompts": 4, "main": {OPUS: cc(4, 40, 0, 400, 4)}},
        {"items": [tk], "prompts": 1, "main": {OPUS: cc(7, 7, 7, 7, 7)}},
    ])
    cost_sidecar(repo, COST_RUN_B, [
        {"item": tk, "prompts": 1, "main": {OPUS: cc(2, 3, 1, 4, 5)},
         "sub": {"general-purpose": {OPUS: cc(1, 1, 1, 1, 1)}}},
        {"item": st, "prompts": 0, "main": {}, "sub": {"Plan": {OPUS: cc(2, 2, 2, 2, 2)}}},
    ])
    return sprint


def check_cost_numbers(w):
    """Every rule of the sum, proved on the report of the story, of its task and of the sprint."""
    bl = backlog.Backlog(w["repo"])
    story, task, sprint_rep = (bl_cost.cost_report(bl, w[k]) for k in ("st", "tk", "sp"))
    # descendants sum: the story holds its own lines and its task's, not the shared line, the bug or the sprint's
    assert story["items"] == sorted([w["st"], w["tk"]]) and story["runs"] == 2 and story["prompts"] == 4
    assert task["items"] == [w["tk"]] and task["prompts"] == 3
    # per model, main (direct) apart from sub (attributed, summed over agent groups), cw a figure of its own
    assert story["direct"] == {OPUS: cc(6, 113, 16, 1104, 82, cw1h=2), SONNET: cc(1, 1, 0, 2, 3)}
    assert story["attributed"] == {OPUS: cc(6, 28, 8, 63, 13), SONNET: cc(1, 1, 1, 1, 1)}
    assert task["direct"] == {OPUS: cc(5, 13, 6, 104, 12, cw1h=2), SONNET: cc(1, 1, 0, 2, 3)}
    assert task["attributed"] == {OPUS: cc(4, 26, 6, 61, 11), SONNET: cc(1, 1, 1, 1, 1)}
    assert story["by_item"][w["tk"]]["direct"] == task["direct"] and story["by_item"][w["st"]]["prompts"] == 1
    # a sprint holds its own line and its items' (story, task, bug), still no shared line
    assert sprint_rep["direct"][OPUS] == cc(19, 162, 25, 1513, 95, cw1h=2) and sprint_rep["prompts"] == 9


def cost_out(repo, capsys, *a):
    assert backlog.main(["--root", str(repo), "cost", *a]) == 0
    return capsys.readouterr().out


def check_cost_cli(w, capsys):
    """Text rows print cw apart, --runs lists each run's line apart, --format json gives the numbers."""
    repo, st, tk = w["repo"], w["st"], w["tk"]
    out = cost_out(repo, capsys, st, "--runs")
    head = out.split("by item:")[0]
    direct = head.split("direct (main):")[1].split("attributed (sub):")[0]
    assert f"{OPUS}  requests 6  in 113  cr 1104  out 82 | cw 16" in direct, out
    assert f"{SONNET}  requests 1  in 1  cr 2  out 3 | cw 0" in direct and "all models  requests 7" in direct, out
    assert f"{OPUS}  requests 6  in 28  cr 63  out 13 | cw 8" in head.split("attributed (sub):")[1], out
    ran = [x.split()[0] for x in out.split("runs:")[1].splitlines() if x.startswith("  2026")]
    assert ran == [COST_RUN_A, COST_RUN_A, COST_RUN_B, COST_RUN_B], out
    one = json.loads(cost_out(repo, capsys, st, "--runs", "--format", "json"))
    assert [(x["run"], x["item"]) for x in one["run_lines"]] == [(COST_RUN_A, tk), (COST_RUN_A, st),
                                                                (COST_RUN_B, tk), (COST_RUN_B, st)]
    assert one["direct"][OPUS] == cc(6, 113, 16, 1104, 82, cw1h=2) and one["attributed"][SONNET] == cc(1, 1, 1, 1, 1)
    assert "run_lines" not in json.loads(cost_out(repo, capsys, st, "--format", "json"))


def test_backlog_cost_sums_descendants_per_model_main_sub_and_cw_apart(costed):
    check_cost_numbers(costed)


def test_backlog_cost_runs_and_json(costed, capsys):
    check_cost_cli(costed, capsys)


def planted_scope(bl, iid):
    return {iid}  # no descendants


def planted_models_merged(total, models):
    for c in models.values():
        t = total.setdefault(OPUS, dict.fromkeys(bl_cost.COST_KEYS, 0))
        for k in bl_cost.COST_KEYS:
            t[k] += c.get(k, 0)


def planted_cw_into_in(total, models):
    for m, c in models.items():
        t = total.setdefault(m, dict.fromkeys(bl_cost.COST_KEYS, 0))
        for k in bl_cost.COST_KEYS:
            t[k] += {"in": c["in"] + c["cw"], "cw": 0}.get(k, c[k])


@pytest.mark.parametrize("name,planted", [
    ("cost_scope", planted_scope),
    ("cost_add", planted_models_merged),
    ("cost_add", planted_cw_into_in),
    ("COST_GROUPS", (("direct", "sub", "direct (main)"), ("attributed", "main", "attributed (sub)"))),
], ids=["no descendants", "models merged", "cw folded into in", "main and sub swapped"])
def test_backlog_cost_planted_failure_of_each_sum_rule_is_caught(costed, monkeypatch, name, planted):
    monkeypatch.setattr(bl_cost, name, planted)
    with pytest.raises(AssertionError):
        check_cost_numbers(costed)


def test_backlog_cost_planted_failure_of_the_runs_listing_is_caught(costed, capsys, monkeypatch):
    """The lines of both runs given one run id: the check no longer sees the two attempts apart."""
    real = bl_cost.cost_lines

    def one_run(root, ids):
        lines, skipped = real(root, ids)
        return [{**x, "run": COST_RUN_A} for x in lines], skipped

    monkeypatch.setattr(bl_cost, "cost_lines", one_run)
    with pytest.raises(AssertionError):
        check_cost_cli(costed, capsys)


def test_backlog_cost_planted_failure_of_the_json_is_caught(costed, capsys, monkeypatch):
    """A json report whose attributed figures are empty differs from the numbers the check expects."""
    real = bl_cost.cost_report

    def no_sub(bl, iid):
        return {**real(bl, iid), "attributed": {}}

    monkeypatch.setattr(bl_cost, "cost_report", no_sub)
    with pytest.raises(AssertionError):
        check_cost_cli(costed, capsys)


def test_backlog_cost_skips_a_sidecar_that_breaks_the_store_gates(costed):
    repo, tk = costed["repo"], costed["tk"]
    cost_sidecar(repo, "20261003T100000Z-cccccccc", [{"item": tk, "prompts": 1, "main": {OPUS: cc(99, 99, 99, 99, 99)},
                                                      "session": "s1"}])
    code, out = b(repo, "cost", tk)
    assert code == 0 and "skipped sidecars that break the store's gates: 20261003T100000Z-cccccccc" in out, out
    assert "requests 99" not in out and f"{OPUS}  requests 5  in 13  cr 104  out 12 | cw 6" in out, out


def test_backlog_cost_unknown_id_exits_2(costed):
    code, out = b(costed["repo"], "cost", "TK-zzzzzzzz")
    assert code == 2 and "no item TK-zzzzzzzz" in out, out


def test_backlog_cost_without_sidecars_prints_zeros_and_exits_0(sprint, capsys):
    repo, tk = sprint["repo"], sprint["tk"]
    code, out = b(repo, "cost", tk)
    assert code == 0 and "0 run(s)" in out, out
    assert out.count("all models  requests 0  in 0  cr 0  out 0 | cw 0") == 4, out  # direct, attributed, shared, total
    one = json.loads(cost_out(repo, capsys, tk, "--format", "json"))
    assert one["direct"] == {} and one["attributed"] == {} and one["runs"] == 0 and one["prompts"] == 0
    assert one["shared"] == {} and one["session_total"] == {} and one["shared_prompts"] == 0


# --- backlog.py cost --rework: the work before an item's first refused done apart from the rework after it ---

COST_RUN_C = "20261005T100000Z-eeeeeeee"


@pytest.fixture
def reworked(costed):
    """The costed sprint with a third sidecar: the task and the unrelated bug each have a `rework` block (a part of the
    line's own counts, from their first refused done), the story a line with none."""
    repo, st, tk, bg = costed["repo"], costed["st"], costed["tk"], costed["bg"]
    cost_sidecar(repo, COST_RUN_C, [
        {"item": tk, "prompts": 2, "main": {OPUS: cc(2, 10, 5, 100, 6)},
         "sub": {"Plan": {OPUS: cc(1, 2, 1, 3, 4)}},
         "rework": {"prompts": 1, "main": {OPUS: cc(1, 4, 2, 40, 2)}, "sub": {"Plan": {OPUS: cc(1, 2, 1, 3, 4)}}}},
        {"item": st, "prompts": 1, "main": {OPUS: cc(1, 1, 1, 1, 1)}},
        {"item": bg, "prompts": 2, "main": {OPUS: cc(2, 6, 0, 60, 6)},
         "rework": {"prompts": 1, "main": {OPUS: cc(1, 3, 0, 30, 3)}}},
    ])
    return costed


def rework_out(w, capsys, iid, *a):
    return json.loads(cost_out(w["repo"], capsys, iid, "--rework", "--format", "json", *a))


def check_rework_numbers(w, capsys):
    """The split of the task, of the story (a line of its own with no rework, and its task's) and of the sprint, as the
    sidecars hold them: rework is the blocks, work is the lines' counts less them, and the two add to the report's
    direct and attributed."""
    tk, st, sp, bg = w["tk"], w["st"], w["sp"], w["bg"]
    task = rework_out(w, capsys, tk)
    split = task["rework_split"]
    assert split["items"] == [tk] and split["rework"]["prompts"] == 1 and split["work"]["prompts"] == 4, split
    assert split["rework"]["direct"] == {OPUS: cc(1, 4, 2, 40, 2)}, split
    assert split["rework"]["attributed"] == {OPUS: cc(1, 2, 1, 3, 4)}, split
    assert split["work"]["direct"] == {OPUS: cc(6, 19, 9, 164, 16, cw1h=2), SONNET: cc(1, 1, 0, 2, 3)}, split
    assert split["work"]["attributed"] == {OPUS: cc(4, 26, 6, 61, 11), SONNET: cc(1, 1, 1, 1, 1)}, split
    assert (split["work"]["tokens"], split["rework"]["tokens"]) == (322, 58), split
    assert split["by_item"] == {tk: {"work": split["work"], "rework": split["rework"]}}, split
    # the report's own figures are the sum of the two, per model and count
    for key in ("direct", "attributed"):
        for m, c in task[key].items():
            both = {k: split["work"][key].get(m, {}).get(k, 0) + split["rework"][key].get(m, {}).get(k, 0) for k in c}
            assert both == c, (key, m)
    assert task["prompts"] == split["work"]["prompts"] + split["rework"]["prompts"] == 5
    story = rework_out(w, capsys, st)["rework_split"]  # its own line and its task's: the task's rework only
    assert story["items"] == [tk] and story["rework"] == split["rework"] and story["work"]["prompts"] == 4 + 2, story
    sprint = rework_out(w, capsys, sp)["rework_split"]  # the task's and the bug's
    assert sprint["items"] == sorted([tk, bg]) and sprint["rework"]["prompts"] == 2, sprint
    assert sprint["rework"]["direct"] == {OPUS: cc(2, 7, 2, 70, 5)}, sprint
    assert set(sprint["by_item"]) == {tk, bg} and sprint["by_item"][bg]["work"]["prompts"] == 2, sprint  # run A's 1, run C's 2, less 1


def test_backlog_work_rework_cost_prints_work_and_rework_for_an_item_a_story_and_a_sprint(reworked, capsys):
    check_rework_numbers(reworked, capsys)


def test_backlog_work_rework_cost_text(reworked, capsys):
    repo, tk, bg = reworked["repo"], reworked["tk"], reworked["bg"]
    view = backlog.Backlog(repo)
    out = cost_out(repo, capsys, tk, "--rework")
    block = out.split("work and rework (")[1]
    assert "1 item(s) with rework" in block.splitlines()[0], out
    assert "  work (4 prompt(s), 322 tokens):" in block and "  rework (1 prompt(s), 58 tokens):" in block, out
    assert f"{OPUS}  requests 1  in 4  cr 40  out 2 | cw 2" in block.split("rework (1 prompt(s)")[1], out
    assert (f"  {view.label(tk)}: work 4 prompt(s), 322 tokens; rework 1 prompt(s), 58 tokens") in out, out
    assert view.label(bg) not in out
    sprint = cost_out(repo, capsys, reworked["sp"], "--rework")
    assert view.label(tk) in sprint.split("work and rework (")[1] and view.label(bg) in sprint.split("work and rework (")[1]


def test_backlog_work_rework_an_item_with_no_rework_has_none(costed, capsys):
    """No sidecar line has a `rework` block: no item, the whole of the report as work, and the text says so."""
    tk = costed["tk"]
    split = rework_out(costed, capsys, tk)["rework_split"]
    assert split["items"] == [] and split["by_item"] == {} and split["rework"]["prompts"] == 0, split
    assert split["rework"]["direct"] == {} and split["rework"]["attributed"] == {}
    assert split["work"]["prompts"] == 3 and split["work"]["direct"][OPUS] == cc(5, 13, 6, 104, 12, cw1h=2), split
    assert "no item has rework" in cost_out(costed["repo"], capsys, tk, "--rework")
    assert rework_out(costed, capsys, costed["bg"])["rework_split"]["items"] == []


def test_backlog_work_rework_without_the_flag_the_output_of_cost_is_unchanged(reworked, capsys):
    """`cost` of a store with rework blocks prints what it prints of the same store without them, text and json, with
    and without `--runs`; the key `rework_split` is only in a `--rework` report."""
    repo = reworked["repo"]
    ids = [reworked[k] for k in ("tk", "st", "sp")]
    runs = (("--runs",), ())
    before = {(i, a, f): cost_out(repo, capsys, i, *a, "--format", f) for i in ids for a in runs for f in ("text", "json")}
    side = Path(repo) / "kb" / "_querylog" / "work" / "2026-10" / f"{COST_RUN_C}.jsonl"
    rows = [json.loads(x) for x in side.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row.pop("rework", None)
    side.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    after = {(i, a, f): cost_out(repo, capsys, i, *a, "--format", f) for i in ids for a in runs for f in ("text", "json")}
    assert before == after
    assert all("rework" not in v for v in before.values())
    flagged = json.loads(cost_out(repo, capsys, ids[0], "--rework", "--format", "json"))
    assert "rework_split" in flagged and "rework_split" not in json.loads(before[(ids[0], (), "json")])


def test_backlog_work_rework_a_sidecar_with_a_block_above_its_line_is_skipped(reworked, capsys):
    repo, tk = reworked["repo"], reworked["tk"]
    side = Path(repo) / "kb" / "_querylog" / "work" / "2026-10" / f"{COST_RUN_C}.jsonl"
    text = side.read_text(encoding="utf-8").replace('"prompts": 1, "main": {"' + OPUS + '": {"requests": 1, "in": 4',
                                                    '"prompts": 9, "main": {"' + OPUS + '": {"requests": 1, "in": 4', 1)
    side.write_text(text, encoding="utf-8", newline="\n")
    code, out = b(repo, "cost", tk, "--rework")
    assert code == 0 and f"skipped sidecars that break the store's gates: {COST_RUN_C}" in out, out
    assert rework_out(reworked, capsys, tk)["rework_split"]["items"] == []


def test_backlog_work_rework_refuses_research_with_it(reworked):
    code, out = b(reworked["repo"], "cost", "--research", "--rework")
    assert code == 2 and "no ID, no --runs and no --rework" in out, out


def test_backlog_work_rework_planted_failure_of_the_subtraction_is_caught(reworked, capsys, monkeypatch):
    """With rework not taken out of the work, work counts what rework counts too."""
    monkeypatch.setattr(bl_cost, "cost_take", lambda total, models: None)
    with pytest.raises(AssertionError):
        check_rework_numbers(reworked, capsys)


def test_backlog_work_rework_planted_failure_of_a_dropped_block_is_caught(reworked, capsys, monkeypatch):
    real = bl_cost.cost_lines

    def no_blocks(root, ids, rework=False):
        lines, skipped = real(root, ids)
        return lines, skipped

    monkeypatch.setattr(bl_cost, "cost_lines", no_blocks)
    with pytest.raises(AssertionError):
        check_rework_numbers(reworked, capsys)


# --- backlog.py cost: items deleted at sprint close, read from their last version in git history ---

COST_RUN_D = "20261004T100000Z-dddddddd"
NO_HISTORY = "TK-aaaaaaaa"  # an id shaped like an item's, with no item file and no commit that ever held one


@pytest.fixture
def closed(costed):
    """The costed sprint, finished and closed in git: its story, task, bug, review and two more items are deleted (the
    epic stays), the sidecars stay. Task two has no work line of its own; its subtask has one (run D), so the subtask
    reaches the story only through a parent that is gone too."""
    w = costed
    repo, st = w["repo"], w["st"]
    assert b(repo, "new", "task", "--title", "Task two", "--parent", st, "--goal", "x", "--touch", "src/**")[0] == 0
    w["tk2"] = item(repo, "Task two")["id"]
    assert b(repo, "new", "subtask", "--title", "Subtask", "--parent", w["tk2"], "--goal", "x", "--touch", "src/**")[0] == 0
    w["sb"] = item(repo, "Subtask")["id"]
    cost_sidecar(repo, COST_RUN_D, [{"item": w["sb"], "prompts": 5, "main": {OPUS: cc(1, 1, 1, 1, 1)}}])
    for k in ("st", "tk", "bg", "rv", "tk2", "sb"):
        edit(repo, w[k], status="done")
    commit(repo, "the sprint, finished")
    code, out = b(repo, "close", w["sp"])
    assert code == 0, out
    commit(repo, "close the sprint")
    assert not [i for i in ("sp", "st", "tk", "bg", "tk2", "sb") if (Path(repo) / backlog.REL_DIR / f"{w[i]}.json").exists()]
    return w


def cost_run(repo, capsys, *a):
    """(exit code, stdout, stderr) of an in-process `cost`; a crash is a failed assertion, so a planted one is caught."""
    try:
        code = backlog.main(["--root", str(repo), "cost", *a])
    except Exception as e:  # noqa: BLE001 - any escape is the failure the check looks for
        raise AssertionError(f"cost crashed: {e!r}") from e
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def cost_json(repo, capsys, *a):
    code, out, err = cost_run(repo, capsys, *a, "--format", "json")
    assert code == 0, err
    return json.loads(out)


def check_closed_totals(w, capsys):
    """A closed sprint's total and an epic's total hold the lines of the items whose files are gone."""
    repo = w["repo"]
    sp = cost_json(repo, capsys, w["sp"])
    assert sp["items"] == sorted([w["sp"], w["st"], w["tk"], w["bg"], w["sb"]]) and sp["prompts"] == 14, sp["items"]
    assert sp["direct"][OPUS] == cc(20, 163, 26, 1514, 96, cw1h=2) and sp["restored"] == sp["items"]
    ep = cost_json(repo, capsys, w["ep"])
    assert ep["items"] == sorted([w["st"], w["tk"], w["sb"]]) and ep["prompts"] == 9, ep["items"]
    assert ep["direct"][OPUS] == cc(7, 114, 17, 1105, 83, cw1h=2) and ep["restored"] == ep["items"]
    # the text names the items it read from history, with their titles from the last version of their files
    code, out, _ = cost_run(repo, capsys, w["ep"])
    assert code == 0 and "from git history (item file deleted):" in out and "“Task”" in out and "“Subtask”" in out, out
    assert f"cost {w['sp']} “Sprint”:" in cost_run(repo, capsys, w["sp"])[1]


def test_backlog_cost_closed_sprint_and_epic_totals_include_deleted_items(closed, capsys):
    check_closed_totals(closed, capsys)


real_history_items = bl_cost.history_items


def planted_history_none(root, ids):
    return {}


def planted_history_without_parent(root, ids):
    return {i: {k: v for k, v in it.items() if k != "parent"} for i, it in real_history_items(root, ids).items()}


def planted_history_without_sprint(root, ids):
    return {i: {k: v for k, v in it.items() if k != "sprint"} for i, it in real_history_items(root, ids).items()}


@pytest.mark.parametrize("planted", [planted_history_none, planted_history_without_parent,
                                     planted_history_without_sprint],
                         ids=["no history", "no parent", "no sprint"])
def test_backlog_cost_closed_planted_failure_of_each_total_is_caught(closed, capsys, monkeypatch, planted):
    monkeypatch.setattr(bl_cost, "history_items", planted)
    with pytest.raises(AssertionError):
        check_closed_totals(closed, capsys)


def test_backlog_cost_closed_item_with_a_gone_parent_reaches_the_story(closed, capsys):
    """The subtask's parent (task two) has no line: it is found by asking history for the parent of a restored item."""
    one = cost_json(closed["repo"], capsys, closed["st"])
    assert closed["sb"] in one["items"] and closed["tk2"] not in one["items"] and one["unresolved"] == []


def check_closed_unresolved(w, capsys):
    """An id with a line and no history stays out of every sum and is named on stderr and in the json."""
    repo = w["repo"]
    cost_sidecar(repo, "20261005T100000Z-eeeeeeee", [{"item": NO_HISTORY, "prompts": 50, "main": {OPUS: cc(99, 99, 99, 99, 99)}}])
    code, out, err = cost_run(repo, capsys, w["ep"])
    assert code == 0 and NO_HISTORY in err and "no git history" in err and NO_HISTORY not in out, (out, err)
    assert "requests 99" not in out
    one = cost_json(repo, capsys, w["sp"])
    assert one["unresolved"] == [NO_HISTORY] and one["prompts"] == 14 and NO_HISTORY not in one["by_item"]


def test_backlog_cost_closed_id_with_no_history_stays_out_and_is_named(closed, capsys):
    check_closed_unresolved(closed, capsys)


def real_scope_wrapped(bl, iid):
    ids = {iid, *bl.descendants(iid)}
    if bl.items[iid].get("kind") == "sprint":
        ids |= set(bl.sprint_items(iid))
    return ids


def test_backlog_cost_closed_planted_failure_of_an_unresolved_id_counted_is_caught(closed, capsys, monkeypatch):
    monkeypatch.setattr(bl_cost, "cost_scope", lambda bl, iid: {*real_scope_wrapped(bl, iid), NO_HISTORY})
    with pytest.raises(AssertionError):
        check_closed_unresolved(closed, capsys)


def test_backlog_cost_closed_planted_failure_of_an_unresolved_id_unnamed_is_caught(closed, capsys, monkeypatch):
    real = bl_cost.cost_report
    monkeypatch.setattr(bl_cost, "cost_report", lambda bl, iid: {**real(bl, iid), "unresolved": []})
    with pytest.raises(AssertionError):
        check_closed_unresolved(closed, capsys)


def clone_shallow(w, tmp_path):
    """A depth-1 clone of the closed repository: its history holds one commit, none that deleted an item file."""
    dst = tmp_path / "shallow"
    sh(tmp_path, "git", "clone", "-q", "--depth", "1", Path(w["repo"]).as_uri(), str(dst))
    return dst


def check_closed_unreadable_history(w, capsys, repo):
    """The epic's file is there, its deleted items are not readable: zeros, the ids named, exit 0, no crash."""
    code, out, err = cost_run(repo, capsys, w["ep"])
    assert code == 0 and "0 run(s)" in out and "from git history" not in out, (out, err)
    for k in ("sp", "st", "tk", "bg", "sb"):
        assert w[k] in err, err
    assert cost_run(repo, capsys, w["sp"])[0] == 2  # the closed sprint itself has no file and no history


def test_backlog_cost_closed_shallow_clone_names_the_ids_and_does_not_crash(closed, capsys, tmp_path):
    check_closed_unreadable_history(closed, capsys, clone_shallow(closed, tmp_path))


def test_backlog_cost_closed_git_missing_names_the_ids_and_does_not_crash(closed, capsys, monkeypatch):
    real = subprocess.run

    def no_git(argv, *a, **kw):
        if argv[:1] == ["git"]:
            raise FileNotFoundError("git")
        return real(argv, *a, **kw)

    monkeypatch.setattr(bl_cost.subprocess, "run", no_git)
    check_closed_unreadable_history(closed, capsys, closed["repo"])


def test_backlog_cost_closed_git_failing_names_the_ids_and_does_not_crash(closed, capsys, monkeypatch):
    real = subprocess.run

    def failing(argv, *a, **kw):
        if argv[:1] == ["git"]:
            raise subprocess.TimeoutExpired(argv, 1)
        return real(argv, *a, **kw)

    monkeypatch.setattr(bl_cost.subprocess, "run", failing)
    check_closed_unreadable_history(closed, capsys, closed["repo"])


def test_backlog_cost_closed_planted_failure_of_a_crash_on_unreadable_history_is_caught(closed, capsys, tmp_path,
                                                                                      monkeypatch):
    def raises(root, ids):
        raise OSError("git")

    monkeypatch.setattr(bl_cost, "history_items", raises)
    with pytest.raises(AssertionError):
        check_closed_unreadable_history(closed, capsys, clone_shallow(closed, tmp_path))


def test_backlog_cost_closed_planted_failure_of_resolving_without_history_is_caught(closed, capsys, tmp_path,
                                                                                   monkeypatch):
    ep = closed["ep"]
    monkeypatch.setattr(bl_cost, "history_items", lambda root, ids: {i: {"kind": "task", "parent": ep} for i in ids})
    with pytest.raises(AssertionError):
        check_closed_unreadable_history(closed, capsys, clone_shallow(closed, tmp_path))


def asked_of_git(w, capsys, monkeypatch, *ids):
    """The ids `cost ID` asks git about, per call, with each call's argument list."""
    asked = []

    def spy(root, want):
        asked.append(sorted(want))
        return real_history_items(root, want)

    monkeypatch.setattr(bl_cost, "history_items", spy)
    for i in ids:
        cost_json(w["repo"], capsys, i)
    return asked


def check_closed_asked_once(w, capsys, monkeypatch):
    asked = asked_of_git(w, capsys, monkeypatch, w["st"])
    flat = [i for call in asked for i in call]
    assert len(flat) == len(set(flat)), asked  # one lookup per distinct id
    assert len(asked) == 2 and w["tk2"] in asked[1] and w["ep"] not in flat, asked  # an item with a file is never asked


def test_backlog_cost_closed_asks_git_once_per_id(closed, capsys, monkeypatch):
    check_closed_asked_once(closed, capsys, monkeypatch)


def test_backlog_cost_closed_planted_failure_of_a_second_lookup_is_caught(closed, capsys, monkeypatch):
    real = bl_cost.cost_view

    def twice(bl, ids):
        bl_cost.history_items(bl.root, [i for i in ids if i not in bl.items])
        return real(bl, ids)

    monkeypatch.setattr(bl_cost, "cost_view", twice)
    with pytest.raises(AssertionError):
        check_closed_asked_once(closed, capsys, monkeypatch)


def test_backlog_cost_closed_history_parse_takes_the_newest_deletion_and_skips_a_broken_one():
    text = "\n".join([
        "diff --git a/kb/_self/backlog/TK-aaaaaaab.json b/kb/_self/backlog/TK-aaaaaaab.json",
        "deleted file mode 100644", "--- a/kb/_self/backlog/TK-aaaaaaab.json", "+++ /dev/null", "@@ -1,3 +0,0 @@",
        '-{', '-  "id": "new"', '-}',
        "diff --git a/kb/_self/backlog/TK-aaaaaaab.json b/kb/_self/backlog/TK-aaaaaaab.json",
        "deleted file mode 100644", "@@ -1,3 +0,0 @@", '-{', '-  "id": "old"', '-}',
        "diff --git a/kb/_self/backlog/TK-aaaaaaac.json b/kb/_self/backlog/TK-aaaaaaac.json",
        "deleted file mode 100644", "@@ -1 +0,0 @@", "-not json", "\\ No newline at end of file",
    ])
    assert bl_cost.history_parse(text) == {"TK-aaaaaaab": {"id": "new"}}


def test_backlog_cost_closed_history_items_of_no_ids_runs_no_git(monkeypatch):
    monkeypatch.setattr(bl_cost.subprocess, "run", lambda *a, **kw: pytest.fail("git ran"))
    assert bl_cost.history_items(".", []) == {} and bl_cost.history_items(".", ["../x", "not an id"]) == {}


# --- backlog.py cost: shared (a session's prompts outside any window) and the session total ---

COST_RUN_E, COST_RUN_F = "20261005T100000Z-eeeeeeee", "20261005T110000Z-ffffffff"
KEYS6 = ("requests", "in", "cw", "cw1h", "cr", "out")


def plus(*maps):
    """{model: counts} summed by hand, without the code under test."""
    out = {}
    for m in maps:
        for model, c in m.items():
            t = out.setdefault(model, dict.fromkeys(KEYS6, 0))
            for k in KEYS6:
                t[k] += c.get(k, 0)
    return out


@pytest.fixture
def shared(sprint):
    """One session works the task, then the bug, with a prompt before the first window, one between the two and one
    after: the sidecar holds their counts on one shared line naming both items; a second session works the story and
    the task (a shared line naming both), a third only the bug. Three sessions in two runs, over the one epic and the
    one sprint of the fixture."""
    w = dict(sprint)
    st, tk, bg = w["st"], w["tk"], w["bg"]
    before, between, after = {OPUS: cc(1, 11, 2, 110, 5)}, {SONNET: cc(1, 13, 3, 130, 6)}, {OPUS: cc(1, 17, 5, 170, 8)}
    w["l1"] = {"items": sorted([tk, bg]), "prompts": 3, "main": plus(before, between, after),
               "sub": {"general-purpose": {OPUS: cc(2, 1, 1, 1, 1)}}}
    w["l2"] = {"items": sorted([st, tk]), "prompts": 2, "main": {OPUS: cc(2, 40, 0, 400, 20)}}
    w["l3"] = {"items": [bg], "prompts": 1, "main": {OPUS: cc(5, 50, 5, 500, 50)}}
    w["x_tk"] = {"item": tk, "prompts": 2, "main": {OPUS: cc(2, 20, 4, 200, 9)},
                 "sub": {"Explore": {OPUS: cc(1, 2, 1, 3, 4)}}}
    w["x_bg"] = {"item": bg, "prompts": 1, "main": {OPUS: cc(3, 30, 6, 300, 12)}}
    w["y_st"] = {"item": st, "prompts": 1, "main": {OPUS: cc(1, 100, 10, 1000, 70)}}
    w["y_tk"] = {"item": tk, "prompts": 1, "main": {OPUS: cc(1, 5, 0, 50, 2)}}
    w["z_bg"] = {"item": bg, "prompts": 1, "main": {OPUS: cc(1, 1, 1, 1, 1)}}
    cost_sidecar(w["repo"], COST_RUN_E, [w["x_tk"], w["x_bg"], w["l1"]])
    cost_sidecar(w["repo"], COST_RUN_F, [w["y_st"], w["y_tk"], w["z_bg"], w["l2"], w["l3"]])
    return w


def shared_expect(w, who):
    """The figures `cost` must give for the task, the bug, the story, the epic or the sprint, by hand from the lines."""
    def both(line):
        return plus(line["main"], *line.get("sub", {}).values())

    story = {"direct": plus(w["y_st"]["main"], w["x_tk"]["main"], w["y_tk"]["main"]),
             "attributed": plus(*w["x_tk"]["sub"].values()), "shared": plus(both(w["l1"]), both(w["l2"]))}
    one = {"tk": {"direct": plus(w["x_tk"]["main"], w["y_tk"]["main"]), "attributed": story["attributed"],
                  "shared": story["shared"]},
           "bg": {"direct": plus(w["x_bg"]["main"], w["z_bg"]["main"]), "attributed": {},
                  "shared": plus(both(w["l1"]), both(w["l3"]))},
           "st": story, "ep": story,  # the epic holds the story and the task, not the bug
           "sp": {"direct": plus(story["direct"], w["x_bg"]["main"], w["z_bg"]["main"]),
                  "attributed": story["attributed"], "shared": plus(both(w["l1"]), both(w["l2"]), both(w["l3"]))}}[who]
    return {**one, "total": plus(one["direct"], one["attributed"], one["shared"])}


def check_shared_totals(w, capsys):
    """Each figure, the session total as their sum, cw apart, and a shared line once for every rollup."""
    for who in ("tk", "bg", "st", "ep", "sp"):
        rep, e = cost_json(w["repo"], capsys, w[who]), shared_expect(w, who)
        assert rep["direct"] == e["direct"], who
        assert rep["attributed"] == e["attributed"], who
        assert rep["shared"] == e["shared"], who
        assert rep["session_total"] == e["total"], who
        # cw is its own figure: the total's cw is the sum of the three cw's, and no cw is in an `in`
        for k in ("cw", "in"):
            assert sum(c[k] for c in rep["session_total"].values()) == sum(
                c[k] for g in ("direct", "attributed", "shared") for c in rep[g].values()), (who, k)
    # hand-picked figures: the task's shared is its two sessions' prompts outside their windows
    tk = cost_json(w["repo"], capsys, w["tk"])
    assert tk["shared"][OPUS] == cc(1 + 1 + 2 + 2, 11 + 17 + 1 + 40, 2 + 5 + 1, 110 + 170 + 1 + 400, 5 + 8 + 1 + 20)
    assert tk["shared"][SONNET] == cc(1, 13, 3, 130, 6) and tk["shared_prompts"] == 5
    # a shared line naming two items of one rollup is counted once: the story and its task name the second session
    assert cost_json(w["repo"], capsys, w["ep"])["shared_prompts"] == 5
    assert cost_json(w["repo"], capsys, w["sp"])["shared_prompts"] == 6


def test_backlog_cost_shared_totals_per_item_and_rollup(shared, capsys):
    check_shared_totals(shared, capsys)


def test_backlog_cost_shared_text_prints_shared_and_the_session_total(shared, capsys):
    out = cost_out(shared["repo"], capsys, shared["tk"])
    e = shared_expect(shared, "tk")
    labels = [x for x in out.splitlines() if x.endswith(":") and not x.startswith(" ")]
    assert labels == ["direct (main):", "attributed (sub):", "shared (outside any window, 5 prompt(s)):",
                      "session total (direct + attributed + shared):"], out
    c = e["total"][OPUS]
    assert f"  {OPUS}  requests {c['requests']}  in {c['in']}  cr {c['cr']}  out {c['out']} | cw {c['cw']}\n" in (
        out.split("session total")[1]), out
    assert f"  {SONNET}  requests 1  in 13  cr 130  out 6 | cw 3\n" in out.split("shared (")[1].split("session total")[0]


def test_backlog_cost_shared_json_shape_and_runs(shared, capsys):
    w = shared
    rep = cost_json(w["repo"], capsys, w["sp"])
    assert sorted(rep) == ["attributed", "by_item", "direct", "id", "items", "overhead", "prompts", "research",
                           "restored", "runs", "session_total", "shared", "shared_prompts", "skipped",
                           "unresolved"], sorted(rep)  # a sprint's report also has research and overhead
    assert all(set(x) == {"prompts", "direct", "attributed"} for x in rep["by_item"].values())  # none holds shared
    runs = cost_json(w["repo"], capsys, w["sp"], "--runs")
    assert [(x["run"], x["items"], x["prompts"]) for x in runs["shared_lines"]] == [
        (COST_RUN_E, w["l1"]["items"], 3), (COST_RUN_F, w["l2"]["items"], 2), (COST_RUN_F, w["l3"]["items"], 1)]
    assert runs["shared_lines"][0]["shared"] == plus(w["l1"]["main"], *w["l1"]["sub"].values())
    assert all("item" not in x for x in runs["shared_lines"]) and all("items" not in x for x in runs["run_lines"])
    assert "shared_lines" not in rep
    out = cost_out(w["repo"], capsys, w["sp"], "--runs")
    assert out.index("shared lines") < out.index("runs:") and out.count(COST_RUN_F) >= 3, out


def test_backlog_cost_shared_line_of_no_item_in_scope_stays_out(shared, capsys):
    """The session that worked only the bug adds nothing to the task or to the story."""
    for who in ("tk", "st"):
        lines = cost_json(shared["repo"], capsys, shared[who], "--runs")["shared_lines"]
        assert [x["items"] for x in lines] == [shared["l1"]["items"], shared["l2"]["items"]], who


def test_backlog_cost_shared_without_a_shared_line_is_zero_and_total_is_direct_plus_attributed(sprint, capsys):
    w = sprint
    cost_sidecar(w["repo"], COST_RUN_E, [{"item": w["tk"], "prompts": 1, "main": {OPUS: cc(1, 2, 3, 4, 5)},
                                          "sub": {"Plan": {OPUS: cc(1, 1, 1, 1, 1)}}}])
    rep = cost_json(w["repo"], capsys, w["tk"])
    assert rep["shared"] == {} and rep["shared_prompts"] == 0
    assert rep["session_total"] == {OPUS: cc(2, 3, 4, 5, 6)}


@pytest.fixture
def closed_shared(sprint):
    """The sprint closed in git (story, task, bug and review deleted, the epic stays) with one session whose only
    record is its shared line naming the task: the task has no line of its own."""
    w = dict(sprint)
    w["l"] = {"items": [w["tk"]], "prompts": 2, "main": {OPUS: cc(2, 4, 6, 8, 10)}}
    cost_sidecar(w["repo"], COST_RUN_E, [w["l"]])
    for k in ("st", "tk", "bg", "rv"):
        edit(w["repo"], w[k], status="done")
    commit(w["repo"], "the sprint, finished")
    assert b(w["repo"], "close", w["sp"])[0] == 0
    commit(w["repo"], "close the sprint")
    return w


def test_backlog_cost_shared_of_an_item_deleted_at_sprint_close_reaches_the_epic(closed_shared, capsys):
    w = closed_shared
    ep = cost_json(w["repo"], capsys, w["ep"])
    assert ep["shared"] == w["l"]["main"] and ep["shared_prompts"] == 2 and ep["items"] == []
    assert ep["session_total"] == ep["shared"]


def planted_total_without_shared(real):
    def report(bl, iid):
        rep = real(bl, iid)
        rep["session_total"] = plus(rep["direct"], rep["attributed"])
        return rep
    return report


def planted_a_line_per_item(real):
    def lines(root, ids):
        out, skipped = real(root, ids)
        return [x for w in out for x in ([{**w, "items": [i]} for i in w["items"]] if "items" in w else [w])], skipped
    return lines


def planted_sessions_merged(real):
    """Every shared line given the items of all of them: a session counted for items it never worked."""
    def lines(root, ids):
        out, skipped = real(root, ids)
        every = sorted({i for w in out if "items" in w for i in w["items"]})
        return [{**w, "items": every} if "items" in w else w for w in out], skipped
    return lines


def planted_shared_without_sonnet(real):
    def lines(root, ids):
        out, skipped = real(root, ids)
        return [{**w, "shared": {m: c for m, c in w["shared"].items() if m != SONNET}} if "items" in w else w
                for w in out], skipped
    return lines


def planted_json_without_shared(real):
    def report(bl, iid):
        rep = real(bl, iid)
        rep["shared"] = {}
        return rep
    return report


@pytest.mark.parametrize("name,planted", [
    ("cost_report", planted_total_without_shared),
    ("cost_lines", planted_a_line_per_item),
    ("cost_lines", planted_sessions_merged),
    ("cost_lines", planted_shared_without_sonnet),
    ("cost_report", planted_json_without_shared),
], ids=["total without shared", "a shared line per item it names", "sessions' shared lines merged",
        "shared of one model left out", "shared left out"])
def test_backlog_cost_shared_planted_failure_of_each_rule_is_caught(shared, capsys, monkeypatch, name, planted):
    monkeypatch.setattr(bl_cost, name, planted(getattr(bl_cost, name)))
    with pytest.raises(AssertionError):
        check_shared_totals(shared, capsys)


def test_backlog_cost_shared_planted_failure_of_cw_folded_into_in_is_caught(shared, capsys, monkeypatch):
    monkeypatch.setattr(bl_cost, "cost_add", planted_cw_into_in)
    with pytest.raises(AssertionError):
        check_shared_totals(shared, capsys)


def test_backlog_cost_shared_planted_failure_of_a_shared_line_dropped_for_a_deleted_item_is_caught(closed_shared,
                                                                                                capsys, monkeypatch):
    """Only item lines name the ids asked of git history: the epic then misses the deleted task's shared line."""
    real = bl_cost.cost_view
    monkeypatch.setattr(bl_cost, "cost_view", lambda bl, ids: real(bl, {i for i in ids if i != closed_shared["tk"]}))
    with pytest.raises(AssertionError):
        test_backlog_cost_shared_of_an_item_deleted_at_sprint_close_reaches_the_epic(closed_shared, capsys)


# --- backlog.py cost SP: item work, research and system overhead printed apart ---

HAIKU = "claude-haiku-4-5"
OV_START, OV_CLOSE = "2026-09-01T09:00:00+00:00", "2026-09-05T09:00:00+00:00"
OV_BEFORE, OV_RES, OV_MORE = "20260901T085959Z-00000001", "20260901T090000Z-00000002", "20260902T100000Z-00000003"
OV_ON_CLOSE, OV_AFTER = "20260905T090000Z-00000004", "20260905T090001Z-00000005"


def overhead_sidecar(repo, run, lines):
    """A work sidecar in its month directory: item lines and overhead lines, the header counting each."""
    d = Path(repo) / "kb" / "_querylog" / "work" / f"{run[:4]}-{run[4:6]}"
    d.mkdir(parents=True, exist_ok=True)
    n = {k: sum(1 for w in lines if k in w) for k in ("item", "items", "overhead")}
    counts = {"items": n["item"], "shared": n["items"], "missing": 0}
    if n["overhead"]:
        counts["overhead"] = n["overhead"]
    head = {"run": run, "reader": 1, "counts": counts}
    (d / f"{run}.jsonl").write_text("".join(json.dumps(o) + "\n" for o in [head, *lines]), encoding="utf-8",
                                    newline="\n")


def commit_at(root, msg, when):
    """A commit whose author and committer time is `when`: the window rule reads the commit time."""
    sh(root, "git", "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
    subprocess.run(["git", "commit", "-qm", msg], cwd=root, check=True, capture_output=True, env=env)


def ov_line(kind, calls, models):
    return {"overhead": kind, "calls": calls, "main": models}


@pytest.fixture
def overheaded(costed):
    """The costed sprint, started in a commit of OV_START, with a research task (its line in the run of an overhead
    line) and overhead runs before the start, on it and after it."""
    w = costed
    repo = w["repo"]
    assert b(repo, "new", "task", "--title", "Research task", "--parent", w["st"], "--goal", "x",
             "--touch", "kb/public/**")[0] == 0
    w["rt"] = item(repo, "Research task")["id"]
    overhead_sidecar(repo, OV_BEFORE, [ov_line("distill", 1, {HAIKU: cc(1, 1000, 0, 1000, 1000)})])
    overhead_sidecar(repo, OV_RES, [
        {"item": w["rt"], "prompts": 2, "main": {OPUS: cc(2, 30, 3, 300, 20)},
         "sub": {"Explore": {OPUS: cc(1, 4, 1, 40, 2)}}},
        ov_line("distill", 2, {HAIKU: cc(2, 10, 4, 100, 5)})])
    overhead_sidecar(repo, OV_MORE, [ov_line("distill", 3, {HAIKU: cc(3, 30, 0, 300, 15)}),
                                     ov_line("eval", 1, {SONNET: cc(1, 5, 0, 50, 2)})])
    overhead_sidecar(repo, OV_ON_CLOSE, [ov_line("digest", 1, {HAIKU: cc(1, 7, 0, 70, 3)})])
    commit_at(repo, "start the sprint", OV_START)
    return w


@pytest.fixture
def overhead_closed(overheaded):
    """The same sprint finished and closed in a commit of OV_CLOSE, with one more overhead run a second later."""
    w = overheaded
    repo = w["repo"]
    for k in ("st", "tk", "bg", "rv", "rt"):
        edit(repo, w[k], status="done")
    commit_at(repo, "the sprint, finished", "2026-09-04T09:00:00+00:00")
    code, out = b(repo, "close", w["sp"])
    assert code == 0, out
    commit_at(repo, "close the sprint", OV_CLOSE)
    overhead_sidecar(repo, OV_AFTER, [ov_line("eval", 1, {SONNET: cc(99, 99, 0, 99, 99)})])
    return w


def check_overhead_work_and_research(rep, w):
    """Item work as the costed fixture sums it, the research task's lines apart from it."""
    assert rep["items"] == sorted([w["sp"], w["st"], w["tk"], w["bg"]]) and rep["prompts"] == 9, rep["items"]
    assert rep["direct"][OPUS] == cc(19, 162, 25, 1513, 95, cw1h=2)
    assert "research" in rep, sorted(rep)
    res = rep["research"]
    assert res["items"] == [w["rt"]] and res["prompts"] == 2 and w["rt"] not in rep["by_item"]
    assert res["direct"] == {OPUS: cc(2, 30, 3, 300, 20)} and res["attributed"] == {OPUS: cc(1, 4, 1, 40, 2)}
    assert res["total"] == {OPUS: cc(3, 34, 4, 340, 22)}


def check_overhead_totals(rep, closed):
    """The overhead lines of the runs in the window, a kind apart, and none outside it."""
    assert "overhead" in rep, sorted(rep)
    ov = rep["overhead"]
    assert ov["resolved"] is True and ov["reason"] is None and ov["start"] == "2026-09-01T09:00:00Z", ov
    assert ov["end"] == ("2026-09-05T09:00:00Z" if closed else None), ov
    assert ov["runs"] == 3 and ov["calls"] == 7, ov  # not the run before the start, nor the one after the close
    assert sorted(ov["kinds"]) == ["digest", "distill", "eval"], ov
    assert ov["kinds"]["distill"] == {"calls": 5, "main": {HAIKU: cc(5, 40, 4, 400, 20)}}, ov
    assert ov["kinds"]["eval"] == {"calls": 1, "main": {SONNET: cc(1, 5, 0, 50, 2)}}, ov
    assert ov["kinds"]["digest"] == {"calls": 1, "main": {HAIKU: cc(1, 7, 0, 70, 3)}}, ov
    assert ov["total"] == {HAIKU: cc(6, 47, 4, 470, 23), SONNET: cc(1, 5, 0, 50, 2)}, ov


def check_overhead_apart(rep):
    """No overhead count in any item figure, the sprint's included, and the session total stays the item work's."""
    for key in ("direct", "attributed", "shared", "session_total"):
        assert HAIKU not in rep[key] and SONNET not in rep["shared"], key
    for one in rep["by_item"].values():
        assert HAIKU not in one["direct"] and HAIKU not in one["attributed"]
    assert HAIKU not in rep["research"]["total"]
    for model in (OPUS, SONNET):
        for k in bl_cost.COST_KEYS:
            parts = (rep[g].get(model, {}).get(k, 0) for g in ("direct", "attributed", "shared"))
            assert rep["session_total"].get(model, {}).get(k, 0) == sum(parts), (model, k)
    assert rep["shared"] == {OPUS: cc(7, 7, 7, 7, 7)}  # the one shared line of the fixture, research not in it


def check_overhead_open(w, capsys):
    rep = cost_json(w["repo"], capsys, w["sp"])
    check_overhead_work_and_research(rep, w)
    check_overhead_totals(rep, closed=False)
    check_overhead_apart(rep)


def check_overhead_closed(w, capsys):
    rep = cost_json(w["repo"], capsys, w["sp"])
    check_overhead_work_and_research(rep, w)
    check_overhead_totals(rep, closed=True)
    check_overhead_apart(rep)


def test_backlog_cost_overhead_sprint_prints_item_work_research_and_overhead_apart(overheaded, capsys):
    check_overhead_open(overheaded, capsys)


def test_backlog_cost_overhead_closed_sprint_window_ends_at_its_close_commit(overhead_closed, capsys):
    check_overhead_closed(overhead_closed, capsys)


def check_overhead_text(w, capsys):
    """The text prints the three totals one after the other, the overhead naming its window."""
    code, out, _ = cost_run(w["repo"], capsys, w["sp"])
    assert code == 0, out
    assert "research (" in out and "system overhead (" in out, out
    work, rest = out.split("research (", 1)
    research, overhead = rest.split("system overhead (", 1)
    overhead = overhead.split("by item:")[0]
    assert "session total" in work and HAIKU not in work and "1 item(s), 2 prompt(s)" in research, out
    assert f"{OPUS}  requests 3  in 34  cr 340  out 22 | cw 4" in research and HAIKU not in research, out
    assert overhead.startswith("2026-09-01T09:00:00Z to now, 3 run(s), 7 call(s);"), out
    assert f"{HAIKU}  requests 6  in 47  cr 470  out 23 | cw 4" in overhead.split("all kinds:")[1], out
    assert "distill (5 call(s)):" in overhead and "eval (1 call(s)):" in overhead and OPUS not in overhead, out


def test_backlog_cost_overhead_text_prints_the_three_totals(overheaded, capsys):
    check_overhead_text(overheaded, capsys)


def check_overhead_other_ids(w, capsys):
    """An item, a story, a bug and an epic print as before: no research, no overhead, in the text or the json."""
    for k in ("tk", "st", "ep", "bg"):
        one = cost_json(w["repo"], capsys, w[k])
        assert "research" not in one and "overhead" not in one, (k, sorted(one))
        out = cost_run(w["repo"], capsys, w[k])[1]
        assert "overhead" not in out and "research (" not in out, out
    st = cost_json(w["repo"], capsys, w["st"])  # a story holds its research task's lines in its own totals, as before
    assert w["rt"] in st["items"] and st["direct"][OPUS]["requests"] == 6 + 2


def test_backlog_cost_overhead_only_a_sprint_prints_research_and_overhead(overheaded, capsys):
    check_overhead_other_ids(overheaded, capsys)


def check_overhead_runs_listing(w, capsys):
    """--runs lists every item line, the research task's too, and no overhead line."""
    one = cost_json(w["repo"], capsys, w["sp"], "--runs")
    assert [(x["run"], x["item"]) for x in one["run_lines"]] == [
        (OV_RES, w["rt"]), (COST_RUN_A, w["tk"]), (COST_RUN_A, w["st"]), (COST_RUN_A, w["bg"]), (COST_RUN_A, w["sp"]),
        (COST_RUN_B, w["tk"]), (COST_RUN_B, w["st"])]


def test_backlog_cost_overhead_runs_lists_every_item_line_and_no_overhead_line(overheaded, capsys):
    check_overhead_runs_listing(overheaded, capsys)


def check_overhead_shallow(repo, w, capsys):
    """A shallow clone cannot say when the sprint started: unresolved, said so, the item work still printed."""
    rep = cost_json(repo, capsys, w["sp"])
    ov = rep["overhead"]
    assert ov["resolved"] is False and "shallow" in ov["reason"] and "runs" not in ov and "total" not in ov, ov
    assert rep["direct"][OPUS] == cc(19, 162, 25, 1513, 95, cw1h=2)
    out = cost_run(repo, capsys, w["sp"])[1]
    assert "system overhead: unresolved (shallow clone" in out and HAIKU not in out, out


def test_backlog_cost_overhead_is_unresolved_in_a_shallow_clone(overheaded, capsys, tmp_path):
    check_overhead_shallow(clone_shallow(overheaded, tmp_path), overheaded, capsys)


def test_backlog_cost_overhead_is_unresolved_for_a_sprint_never_started_in_history(planned, capsys):
    ov = cost_json(planned["repo"], capsys, planned["later"])["overhead"]
    assert ov["resolved"] is False and "sets the sprint active" in ov["reason"], ov


def test_backlog_cost_overhead_git_missing_is_unresolved_not_a_crash(overheaded, capsys, monkeypatch):
    real = subprocess.run

    def no_git(argv, *a, **kw):
        if argv[:1] == ["git"]:
            raise FileNotFoundError("git")
        return real(argv, *a, **kw)

    monkeypatch.setattr(subprocess, "run", no_git)
    ov = cost_json(overheaded["repo"], capsys, overheaded["sp"])["overhead"]
    assert ov["resolved"] is False and "git" in ov["reason"], ov


def test_backlog_cost_overhead_a_sidecar_that_breaks_the_gates_is_left_out(overheaded, capsys):
    repo = overheaded["repo"]
    overhead_sidecar(repo, "20260903T100000Z-00000006", [ov_line("distill", 0, {HAIKU: cc(99, 99, 0, 99, 99)})])
    ov = cost_json(repo, capsys, overheaded["sp"])["overhead"]
    assert ov["runs"] == 3 and ov["calls"] == 7 and "99" not in json.dumps(ov["total"])


# a planted failure per rule: a check that does not fail when its rule is broken proves nothing
real_sprint_window = bl_cost.sprint_window
real_cost_report = bl_cost.cost_report


def planted_window(**shift):
    """The real window with its start or end moved: `start=0` the beginning of time, `end=None` open, `start=1`..."""
    def window(root, sid):
        start, end, reason = real_sprint_window(root, sid)
        if reason:
            return start, end, reason
        return shift.get("start", lambda t: t)(start), shift.get("end", lambda t: t)(end), reason
    return window


def planted_report(change):
    def report(bl, iid):
        rep = real_cost_report(bl, iid)
        change(rep)
        return rep
    return report


def add_overhead_to(key):
    def change(rep):
        if "overhead" in rep and rep["overhead"]["resolved"]:
            bl_cost.cost_add(rep[key], rep["overhead"]["total"])
    return change


def keep_research_in_work(rep):
    if "research" in rep:
        for key in ("direct", "attributed"):
            bl_cost.cost_add(rep[key], rep["research"][key])


def drop(key):
    return lambda rep: rep.pop(key, None)


@pytest.mark.parametrize("name,planted", [
    ("sprint_window", planted_window(start=lambda t: 0)),
    ("sprint_window", planted_window(start=lambda t: t + 1)),
    ("cost_report", planted_report(add_overhead_to("direct"))),
    ("cost_report", planted_report(add_overhead_to("session_total"))),
    ("cost_report", planted_report(keep_research_in_work)),
    ("cost_report", planted_report(drop("overhead"))),
    ("cost_report", planted_report(drop("research"))),
    ("cost_is_research", lambda view, iid: False),
    ("cost_is_research", lambda view, iid: True),
])
def test_backlog_cost_overhead_planted_failure_of_each_rule_is_caught(overheaded, capsys, monkeypatch, name, planted):
    monkeypatch.setattr(bl_cost, name, planted)
    with pytest.raises(AssertionError):
        check_overhead_open(overheaded, capsys)


@pytest.mark.parametrize("planted", [planted_window(end=lambda t: None), planted_window(end=lambda t: t - 1),
                                     planted_window(start=lambda t: 0)])
def test_backlog_cost_overhead_planted_failure_of_the_close_bound_is_caught(overhead_closed, capsys, monkeypatch, planted):
    monkeypatch.setattr(bl_cost, "sprint_window", planted)
    with pytest.raises(AssertionError):
        check_overhead_closed(overhead_closed, capsys)


def test_backlog_cost_overhead_planted_failure_of_a_guessed_window_in_a_shallow_clone_is_caught(
        overheaded, capsys, monkeypatch, tmp_path):
    clone = clone_shallow(overheaded, tmp_path)
    monkeypatch.setattr(bl_cost, "sprint_window", lambda root, sid: (0, None, None))
    with pytest.raises(AssertionError):
        check_overhead_shallow(clone, overheaded, capsys)


def test_backlog_cost_overhead_planted_failure_of_the_text_is_caught(overheaded, capsys, monkeypatch):
    monkeypatch.setattr(bl_cost, "cost_apart", lambda rep, view: [])
    with pytest.raises(AssertionError):
        check_overhead_text(overheaded, capsys)


@pytest.mark.parametrize("planted", [
    lambda rep, view: ["system overhead: x"],
    lambda rep, view: ["research (x"],
])
def test_backlog_cost_overhead_planted_failure_of_a_non_sprint_report_printing_them_is_caught(
        overheaded, capsys, monkeypatch, planted):
    monkeypatch.setattr(bl_cost, "cost_apart", planted)
    with pytest.raises(AssertionError):
        check_overhead_other_ids(overheaded, capsys)


def test_backlog_cost_overhead_planted_failure_of_the_runs_listing_is_caught(overheaded, capsys, monkeypatch):
    monkeypatch.setattr(bl_cost, "cost_report", planted_report(lambda rep: rep.update(run_lines=rep["run_lines"][1:])))
    with pytest.raises(AssertionError):
        check_overhead_runs_listing(overheaded, capsys)


# --- backlog.py cost --research: the research items' tokens against the gap findings their commits closed ---

GAP1, GAP2, GAP3, GAP4, GAP5, GAP6, EVAL1 = (f"F-{c * 12}" for c in "123456e")
RS_RUN = "20261001T120000Z-abcdef01"
RS_NOTE1 = f"Resolved 2026-10-02: a fact (see {GAP6})"


def gaps_file(repo, notes):
    """kb/public/_gaps.md with one entry per gap finding (the id on its bullet) and the dated notes `notes` maps to it."""
    lines = ["# Gaps", "", "## x-y", ""]
    for fid in (GAP1, GAP2, GAP3, GAP4, GAP5, GAP6):
        lines.append(f"- **question of {fid}** The kb was asked this (query log finding {fid}). (topic: x/y)")
        lines += [f"  - {n} (topic: x/y)" for n in notes.get(fid, [])]
    d = Path(repo) / "kb" / "public"
    d.mkdir(parents=True, exist_ok=True)
    (d / "_gaps.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def commit_with(repo, msg, trailer):
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", msg, "-m", trailer)


@pytest.fixture
def researched(costed):
    """The costed sprint with a findings store (six gap findings and one eval finding), a research task `tk` (research
    true, a link to a gap finding), the story `st` (a link to a gap finding and one to the eval finding, no research
    field), a second research task with no work line, the bug `bg` linking only the eval finding, and a ledger that
    commits close step by step: tk closes two gaps (a note's text names a third id), st only tries one, tk2 closes
    one with bg in one trailer, and a commit with no trailer closes another; the last commit, tk's, only edits a note."""
    w = costed
    repo, st, tk, bg = w["repo"], w["st"], w["tk"], w["bg"]
    assert b(repo, "new", "task", "--title", "Research task two", "--parent", st, "--goal", "x",
             "--touch", "kb/public/**")[0] == 0
    w["tk2"] = item(repo, "Research task two")["id"]
    d = Path(repo) / "kb" / "_querylog" / "findings" / "2026-10"
    d.mkdir(parents=True)
    recs = [{"id": g, "kind": "gap", "state": "open", "stage": "gap", "article": "x/y.md"}
            for g in (GAP1, GAP2, GAP3, GAP4, GAP5, GAP6)] + [{"id": EVAL1, "kind": "eval", "state": "open",
                                                                "stage": "miss"}]
    head = {"run": RS_RUN, "reader": 1, "counts": {"findings": len(recs), "open": len(recs), "fixed-since": 0}}
    (d / f"{RS_RUN}.jsonl").write_text("".join(json.dumps(o) + "\n" for o in [head, *recs]), encoding="utf-8",
                                       newline="\n")
    edit(repo, tk, research=True, links=[f"query log finding {GAP6}"])
    edit(repo, w["tk2"], research=True)
    edit(repo, st, links=[f"gap {GAP3}, see also {EVAL1}"])
    edit(repo, bg, links=[f"finding {EVAL1}"])
    notes = {}
    gaps_file(repo, notes)
    commit(repo, "ledger")
    notes.update({GAP1: [RS_NOTE1], GAP2: ["Resolved 2026-10-02: a fact"], GAP3: ["Tried 2026-10-02: nothing"]})
    gaps_file(repo, notes)
    commit(repo, "tk closes two", work=tk)
    notes[GAP3] = ["Tried 2026-10-02: nothing", "Tried 2026-10-03: nothing again"]
    gaps_file(repo, notes)
    commit(repo, "st only tries", work=st)
    notes[GAP4] = ["Resolved 2026-10-04: no trailer"]
    gaps_file(repo, notes)
    commit(repo, "nobody's trailer")
    notes[GAP5] = ["Superseded 2026-10-05: by a newer page"]
    gaps_file(repo, notes)
    commit_with(repo, "two items one close", f"KB-Work: {w['tk2']}, {bg}")
    notes[GAP1] = [f"Resolved 2026-10-03: the same entry, its note edited (see {GAP6})"]
    gaps_file(repo, notes)
    commit(repo, "tk edits a note", work=tk)
    return w


def research_json(repo, capsys):
    code = backlog.main(["--root", str(repo), "cost", "--research", "--format", "json"])
    out = capsys.readouterr()
    assert code == 0, out.err
    return json.loads(out.out)


def research_rows(w, capsys):
    return {r["id"]: r for r in research_json(w["repo"], capsys)["research_items"]}


def check_research_selection(w, capsys):
    """An item is listed by `research` true, by a link to a gap finding of the store, or both; a link to an eval
    finding, an item with neither, selects nothing."""
    rows = research_rows(w, capsys)
    assert sorted(rows) == sorted([w["st"], w["tk"], w["tk2"]]), sorted(rows)
    assert rows[w["tk"]]["selected_by"] == ["research", "links"]
    assert rows[w["st"]]["selected_by"] == ["links"] and rows[w["tk2"]]["selected_by"] == ["research"]


def check_research_tokens(w, capsys):
    """tokens = in + cw + cr + out of the item's own direct + attributed lines; requests and cw1h are no tokens."""
    rows = research_rows(w, capsys)
    tk = rows[w["tk"]]
    assert tk["direct_tokens"] == (10 + 5 + 100 + 7) + (1 + 0 + 2 + 3) + (3 + 1 + 4 + 5) == 141
    assert tk["attributed_tokens"] == (20 + 4 + 50 + 9) + (5 + 1 + 10 + 1) + (1 + 1 + 1 + 1) + (1 + 1 + 1 + 1) == 108
    assert tk["tokens"] == 249 and rows[w["st"]]["tokens"] == (100 + 10 + 1000 + 70) + (2 + 2 + 2 + 2) == 1188
    assert rows[w["tk2"]]["tokens"] == 0
    assert tk["runs"] == 2 and tk["prompts"] == 3  # no shared line of the session, no descendant


def check_research_closed_gaps(w, capsys):
    """A gap is closed by a commit with the item's KB-Work trailer whose version of the ledger settles its entry: a
    Resolved or Superseded note the parent's version lacks. Not a Tried note, not a note's text naming an id, not a
    note the parent already had, not a commit with no such trailer or another item's."""
    rows = research_rows(w, capsys)
    assert rows[w["tk"]]["closed_gaps"] == [GAP1, GAP2] and rows[w["tk"]]["gap_status"] == "closed"
    assert rows[w["st"]]["closed_gaps"] == [] and rows[w["st"]]["gap_status"] == "none"
    assert rows[w["tk2"]]["closed_gaps"] == [GAP5]  # a trailer naming two items counts for each of them


def check_research_per_gap(w, capsys):
    """Integer division by the count of closed gaps; none closed: no ratio (n/a); zero tokens over one gap: 0."""
    rows = research_rows(w, capsys)
    assert rows[w["tk"]]["tokens"] == 249 and rows[w["tk"]]["tokens_per_gap"] == 124  # 249 // 2, not 124.5 up
    assert rows[w["st"]]["tokens_per_gap"] is None
    assert rows[w["tk2"]]["tokens"] == 0 and rows[w["tk2"]]["tokens_per_gap"] == 0


def check_research_text(w, capsys):
    """Text rows by tokens descending then id, each with id and title only, the ratio or n/a."""
    assert backlog.main(["--root", str(w["repo"]), "cost", "--research"]) == 0
    out = capsys.readouterr().out
    rows = [x for x in out.splitlines() if x.startswith("  ")]
    assert [x.split()[0] for x in rows] == [w["st"], w["tk"], w["tk2"]], out
    assert rows[0].endswith("tokens per closed gap: n/a") and "no closed gap" in rows[0], rows[0]
    assert f"{GAP1}, {GAP2}" in rows[1] and rows[1].endswith("tokens per closed gap: 124") and "249 tokens" in rows[1]
    assert "Research task two" in rows[2] and rows[2].endswith("tokens per closed gap: 0"), rows[2]
    assert "closed gaps: resolved" in out and "in + cw + cr + out" in out, out


def check_research_json_shape(w, capsys):
    rep = research_json(w["repo"], capsys)
    assert sorted(rep) == ["git", "research_items", "skipped", "token_keys", "unresolved"], sorted(rep)
    assert rep["git"] == {"reason": None, "resolved": True} and rep["token_keys"] == ["in", "cw", "cr", "out"]
    assert [r["id"] for r in rep["research_items"]] == [w["st"], w["tk"], w["tk2"]]
    one = rep["research_items"][1]
    assert sorted(one) == ["attributed", "attributed_tokens", "closed_gaps", "direct", "direct_tokens", "gap_status",
                           "id", "prompts", "runs", "selected_by", "title", "tokens", "tokens_per_gap"], sorted(one)
    assert one["title"] == "Task" and one["direct"][OPUS]["in"] == 13 and "research" not in rep  # no sprint total key


def check_research_shallow(w, capsys, clone):
    """A shallow clone: the tokens print, the closed gaps are unresolved (no guess, no ratio), exit 0."""
    rep = research_json(clone, capsys)
    assert rep["git"]["resolved"] is False and "shallow" in rep["git"]["reason"], rep["git"]
    for r in rep["research_items"]:
        assert r["closed_gaps"] is None and r["tokens_per_gap"] is None and r["gap_status"] == "unresolved", r
    assert {r["id"]: r["tokens"] for r in rep["research_items"]}[w["tk"]] == 249
    assert backlog.main(["--root", str(clone), "cost", "--research"]) == 0
    out = capsys.readouterr().out
    assert "closed gaps: unresolved (shallow clone" in out and "tokens per closed gap: unresolved" in out, out
    assert "n/a" not in out


def test_backlog_cost_research_selects_by_a_gap_link_and_by_research_true(researched, capsys):
    check_research_selection(researched, capsys)


def test_backlog_cost_research_tokens_are_in_cw_cr_out_of_direct_and_attributed(researched, capsys):
    check_research_tokens(researched, capsys)


def test_backlog_cost_research_joins_closed_gaps_by_the_kb_work_trailer(researched, capsys):
    check_research_closed_gaps(researched, capsys)


def test_backlog_cost_research_tokens_per_closed_gap_is_integer_division_or_na(researched, capsys):
    check_research_per_gap(researched, capsys)


def test_backlog_cost_research_text_and_json_shape(researched, capsys):
    check_research_text(researched, capsys)
    check_research_json_shape(researched, capsys)


def test_backlog_cost_research_shallow_clone_says_unresolved(researched, capsys, tmp_path):
    check_research_shallow(researched, capsys, clone_shallow(researched, tmp_path))


def test_backlog_cost_research_git_missing_says_unresolved(researched, capsys, monkeypatch):
    real = subprocess.run

    def no_git(argv, *a, **kw):
        if argv[:1] == ["git"]:
            raise FileNotFoundError("git")
        return real(argv, *a, **kw)

    monkeypatch.setattr(bl_cost.subprocess, "run", no_git)
    rep = research_json(researched["repo"], capsys)
    assert rep["git"]["resolved"] is False and all(r["gap_status"] == "unresolved" for r in rep["research_items"])


def test_backlog_cost_research_asks_git_once_for_the_selected_items(researched, capsys, monkeypatch):
    calls = []
    real = bl_cost.closed_gaps_by_item
    monkeypatch.setattr(bl_cost, "closed_gaps_by_item", lambda root, wanted: calls.append(wanted) or real(root, wanted))
    research_json(researched["repo"], capsys)
    assert len(calls) == 1 and calls[0] == {researched["st"], researched["tk"], researched["tk2"]}


def test_backlog_cost_research_none_selected_prints_an_empty_list_and_asks_no_git(sprint, capsys, monkeypatch):
    monkeypatch.setattr(bl_cost, "closed_gaps_by_item", lambda root, wanted: pytest.fail("git asked"))
    rep = research_json(sprint["repo"], capsys)
    assert rep["research_items"] == [] and rep["git"]["resolved"] is True
    assert backlog.main(["--root", str(sprint["repo"]), "cost", "--research"]) == 0
    assert "0 item(s)" in capsys.readouterr().out


def test_backlog_cost_research_usage_errors_and_cost_id_unchanged(researched, capsys):
    repo, tk = researched["repo"], researched["tk"]
    for argv in (["cost"], ["cost", "--research", tk], ["cost", "--research", "--runs"]):
        assert backlog.main(["--root", str(repo), *argv]) == 2, argv
        capsys.readouterr()
    assert backlog.main(["--root", str(repo), "cost", tk]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"cost {tk} “Task”:") and "tokens per closed gap" not in out and "research" not in out
    one = json.loads(cost_out(repo, capsys, tk, "--format", "json"))
    assert "research_items" not in one and "git" not in one


def test_backlog_cost_research_gaps_settled_reads_the_bullet_not_its_notes():
    text = "\n".join(["## t", "", f"- **q** (query log finding {GAP1}). (topic: a/b)",
                      f"  - Resolved 2026-10-02: mentions {GAP2} (topic: a/b)", f"- **q2** {GAP3} wrapped",
                      f"  into a second line, {GAP4}", "  - Superseded 2026-10-02: by x", f"- **q3** {GAP5}",
                      "  - Tried 2026-10-02: no", f"- **q4** {GAP6}", "  - Partly resolved 2026-10-02: some"])
    assert bl_cost.gaps_settled(text) == {GAP1, GAP3, GAP4} and bl_cost.gaps_settled("") == set()


@pytest.mark.parametrize("check,name,planted", [
    (check_research_selection, "gap_links", lambda real: lambda it, kinds: []),
    (check_research_selection, "gap_links",
     lambda real: lambda it, kinds: real(it, {i: "gap" for i in (EVAL1, GAP3, GAP6)})),
    (check_research_tokens, "cost_tokens", lambda real: lambda models: real(models) + len(models)),
    (check_research_tokens, "cost_tokens",
     lambda real: lambda models: sum(c["requests"] for c in models.values()) + real(models)),
    (check_research_closed_gaps, "closed_gaps_by_item", lambda real: lambda root, wanted: ({i: set() for i in wanted}, None)),
    (check_research_closed_gaps, "gaps_settled", lambda real: lambda text: real(text) | set(bl_cost.GAP_ID_RE.findall(
        " ".join(x for x in text.split("\n") if x.startswith("  - Resolved"))))),
    (check_research_closed_gaps, "git_text",
     lambda real: lambda root, *a, **k: "" if a[:1] == ("ls-tree",) else real(root, *a, **k)),
    (check_research_per_gap, "cost_tokens", lambda real: lambda models: real(models) + (1 if models else 0)),
])
def test_backlog_cost_research_planted_failure_of_each_rule_is_caught(researched, capsys, monkeypatch, check, name,
                                                                      planted):
    monkeypatch.setattr(bl_cost, name, planted(getattr(bl_cost, name)))
    with pytest.raises(AssertionError):
        check(researched, capsys)


def planted_research_report(change):
    real = bl_cost.cost_research

    def report(bl):
        rep = real(bl)
        change(rep)
        return rep
    return report


@pytest.mark.parametrize("planted", [
    lambda rep: [r.__setitem__("tokens_per_gap", -(-r["tokens"] // len(r["closed_gaps"])))
                 for r in rep["items"] if r["closed_gaps"]],
    lambda rep: [r.__setitem__("tokens_per_gap", 0) for r in rep["items"] if r["tokens_per_gap"] is None],
])
def test_backlog_cost_research_planted_failure_of_a_rounded_or_zero_ratio_is_caught(researched, capsys, monkeypatch,
                                                                                    planted):
    monkeypatch.setattr(bl_cost, "cost_research", planted_research_report(planted))
    with pytest.raises(AssertionError):
        check_research_per_gap(researched, capsys)


def test_backlog_cost_research_planted_failure_of_a_guess_in_a_shallow_clone_is_caught(researched, capsys, tmp_path,
                                                                                       monkeypatch):
    clone = clone_shallow(researched, tmp_path)
    monkeypatch.setattr(bl_cost, "closed_gaps_by_item", lambda root, wanted: ({i: set() for i in wanted}, None))
    with pytest.raises(AssertionError):
        check_research_shallow(researched, capsys, clone)


@pytest.mark.parametrize("planted", [
    lambda rep: rep["items"].reverse(),
    lambda rep: rep["items"].sort(key=lambda r: r["tokens"]),
    lambda rep: [r.pop("title") for r in rep["items"]],
])
def test_backlog_cost_research_planted_failure_of_the_order_and_shape_is_caught(researched, capsys, monkeypatch, planted):
    monkeypatch.setattr(bl_cost, "cost_research", planted_research_report(planted))
    with pytest.raises(AssertionError):
        check_research_text(researched, capsys)
        check_research_json_shape(researched, capsys)
