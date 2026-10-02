"""Tests of `backlog.py bounds` and the rules it puts in front of `check`, `new` and `close` (bl_bounds.py): a running
sprint the autopilot started gains no item but an S1 bug, a finding becomes an item only with its evidence and no
near-duplicate, a sprint of findings has no retrospective, and the limits (findings per sprint, rework per item, draft
inflow against the done outflow, open drafts) and the manager's stop conditions hold over a range of counts, not one.
Real throwaway git repositories; the ops rows are planted as the rows the query log keeps, never a spool of the host.
"""
import argparse
import ast
import json
import re
from pathlib import Path

import pytest

import backlog
import bl_base
import bl_bounds
import bl_cli
import bl_testkit
from bl_testkit import TOOLS, argstr, b, commit, edit, is_file, item, item_json

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

SPRINT_ID = "SP-" + "a" * 8
DAY = "2026-10-01T10:00:00.000Z"


def autopilot_started(sprint_):
    """The fixture's running sprint, its start gate answered by the autopilot and its start committed: the baseline
    `check` and `new` compare a later joiner with."""
    repo_, sp = sprint_["repo"], sprint_["sp"]
    gates = item_json(repo_, sp)["gates"]
    for g in gates:
        if g["id"] == "start":
            g["by"] = "autopilot"
    edit(repo_, sp, gates=gates)
    commit(repo_, "start")
    return repo_, sp


def closed(n, landed, day=1):
    """One `sprint.close` row: sprint number n landed `landed` items."""
    return {"id": f"close-{n}-{day}", "ts": f"2026-09-{day:02d}T10:00:00.000Z", "surface": "ops", "v": 1,
            "event": "sprint.close", "sprint": "SP-" + "abcdefgh"[n % 8] * 8, "landed": landed, "dropped": 0, "bugs": 0,
            "confirmed": 0, "refused": 0, "ms": 1}


def plant_drafts(bl, n, origin=True, sprint_id=SPRINT_ID):
    """N draft stories in the backlog object (not on disk), each carrying an origin link when `origin`."""
    for k in range(n):
        iid = f"ST-{'abcdefgh'[k % 8]}{'abcdefgh'[(k // 8) % 8]}{'abcdefgh'[(k // 64) % 8]}aaaaa"
        bl.items[iid] = {"id": iid, "kind": "story", "title": f"Planted draft {k}", "status": "draft",
                         "links": ([f"origin retro {sprint_id}", "evidence commit abcdef1"] if origin else [])}


def finding(sprint_id, origin="retro", title="Process finding", goal="the finding is fixed", **kw):
    return argparse.Namespace(origin=origin, sprint=sprint_id, kind=kw.pop("kind", "story"), title=title, goal=goal,
                              severity=kw.pop("severity", None), repro=kw.pop("repro", None), check=None, touch=None,
                              evidence=kw.pop("evidence", []), **kw)


def head(repo_):
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def titles(repo_):
    return sorted(json.loads(f.read_text(encoding="utf-8"))["title"]
                  for f in (Path(repo_) / backlog.REL_DIR).glob("*.json"))


# ---------------------------------------------------------------- a running sprint gains no item but an S1 bug

@pytest.mark.parametrize("kind,severity,allowed", [("story", None, False), ("bug", "S4", False), ("bug", "S3", False),
                                                   ("bug", "S2", False), ("bug", "S1", True)])
def test_bounds_sprint_gains_only_s1_new_into_a_sprint_the_autopilot_started(sprint, kind, severity, allowed):
    repo_, sp = autopilot_started(sprint)
    argv = ["new", kind, "--title", "Late", "--sprint", sp, "--goal", "g", "--check", argstr(is_file("src/b.txt"))]
    if kind == "bug":
        argv += ["--severity", severity, "--repro", argstr(is_file("src/zzz.txt")), "--touch", "src/**"]
    code, out = b(repo_, *argv)
    if allowed:
        assert code == 0, out
        assert item(repo_, "Late")["sprint"] == sp
    else:
        assert code == 1 and "gains no item after its start" in out, out
        assert "Late" not in titles(repo_)


def test_bounds_sprint_gains_only_s1_a_task_and_an_operator_sprint_are_not_held(sprint):
    repo_, sp = sprint["repo"], sprint["sp"]
    code, out = b(repo_, "new", "bug", "--title", "Operator bug", "--sprint", sp, "--severity", "S3", "--repro",
                  argstr(is_file("src/zzz.txt")), "--goal", "g", "--touch", "src/**")
    assert code == 0, out  # a sprint the operator started: unchanged
    repo_, sp = autopilot_started(sprint)
    code, out = b(repo_, "new", "task", "--title", "More work", "--parent", sprint["st"], "--goal", "g", "--touch",
                  "src/**", "--check", argstr(is_file("src/b.txt")))
    assert code == 0, out  # a task is the breakdown of a story the sprint committed to


def test_bounds_sprint_gains_only_s1_check_reports_a_joiner_after_the_start(sprint):
    repo_, sp = autopilot_started(sprint)
    code, out = b(repo_, "check")
    assert code == 0 and "bounds" not in out, out  # what was there at the start is no late joiner
    assert b(repo_, "new", "story", "--title", "Loose", "--goal", "g", "--check", argstr(is_file("src/b.txt")),
             "--touch", "src/**")[0] == 0
    assert b(repo_, "new", "bug", "--title", "Loose S1", "--severity", "S1", "--repro", argstr(is_file("src/zzz.txt")),
             "--goal", "g", "--touch", "src/**")[0] == 0
    commit(repo_, "two items outside the sprint")
    loose, s1 = item(repo_, "Loose")["id"], item(repo_, "Loose S1")["id"]
    assert b(repo_, "check")[0] == 0
    edit(repo_, loose, sprint=sp, status="todo")  # joined by `set` or a hand edit, which `new` never sees
    edit(repo_, s1, sprint=sp, status="todo")
    code, out = b(repo_, "check")
    assert code == 1, out
    assert f"bounds: error: {loose}" in out and "after its start" in out and s1 not in out, out
    commit(repo_, "both joined")  # committed, the item is still later than the start
    code, out = b(repo_, "check")
    assert code == 1 and loose in out and s1 not in out, out


def test_bounds_sprint_gains_only_s1_close_refuses_while_check_would(sprint):
    repo_, sp = autopilot_started(sprint)
    assert b(repo_, "new", "story", "--title", "Loose", "--goal", "g", "--check", argstr(is_file("src/b.txt")),
             "--touch", "src/**")[0] == 0
    commit(repo_, "a story outside the sprint")
    edit(repo_, item(repo_, "Loose")["id"], sprint=sp, status="done")
    for i in (sprint["st"], sprint["tk"], sprint["bg"], sprint["rv"]):
        edit(repo_, i, status="done")
    code, out = b(repo_, "close", sp)
    assert code == 1 and "breaks the bounds" in out and "Loose" in out, out
    assert item_json(repo_, sp)  # nothing was deleted
    edit(repo_, item(repo_, "Loose")["id"], status="dropped")  # a dropped joiner gained nothing
    code, out = b(repo_, "close", sp, "--summary")
    assert code == 0, out


# ---------------------------------------------------------------- a finding needs a failure that happened, with evidence

def test_bounds_finding_needs_failure_and_evidence_none_is_kept_for_the_close_commit(sprint, capsys):
    repo_ = sprint["repo"]
    bl = bl_base.Backlog(repo_)
    before = titles(repo_)
    out = bl_bounds.file_finding(bl, finding(sprint["sp"], title="A feeling that retros are long"), rows=[])
    assert out == ("kept", None) and titles(repo_) == before
    assert "kept in the close commit body only" in capsys.readouterr().out


def test_bounds_finding_needs_failure_and_evidence_a_ref_that_is_not_there_is_refused(sprint):
    repo_ = sprint["repo"]
    (repo_ / "_tools").mkdir()
    (repo_ / "_tools" / "test_real.py").write_text("def test_real_failure():\n    assert False\n", encoding="utf-8")
    commit(repo_, "a test")
    bl = bl_base.Backlog(repo_)
    before = titles(repo_)
    for ref in ("commit:" + "0" * 40, "commit:nothex", "test:test_nowhere", "test:test_real.py::test_nowhere",
                "test:other.py::test_real_failure", "ops:no-such-row"):
        with pytest.raises(bl_base.Refused, match="evidence is not there"):
            bl_bounds.file_finding(bl, finding(sprint["sp"], evidence=[ref]), rows=[{"id": "row-1"}])
    with pytest.raises(bl_base.Rejected, match="KIND:REF"):
        bl_bounds.file_finding(bl, finding(sprint["sp"], evidence=["a commit"]), rows=[])
    assert titles(repo_) == before


def test_bounds_finding_needs_failure_and_evidence_a_finding_with_each_kind_of_evidence_is_filed(sprint, capsys):
    repo_ = sprint["repo"]
    (repo_ / "_tools").mkdir()
    (repo_ / "_tools" / "test_real.py").write_text("def test_real_failure():\n    assert False\n", encoding="utf-8")
    commit(repo_, "a test")
    sha = head(repo_)
    for n, ev in enumerate((f"commit:{sha}", f"commit:{sha[:9]}", "test:test_real_failure",
                            "test:test_real.py::test_real_failure", "ops:row-1")):
        bl = bl_base.Backlog(repo_)
        outcome, iid = bl_bounds.file_finding(bl, finding(sprint["sp"], title=f"Unique zebra{n} xylophone{n}",
                                                         goal=f"quartz{n} fixed", evidence=[ev]), rows=[{"id": "row-1"}])
        assert outcome == "filed", ev
        it = item_json(repo_, iid)
        assert it["status"] == "draft" and "sprint" not in it  # the backlog, not the sprint
        assert f"origin retro {sprint['sp']}" in it["links"] and f"evidence {ev.replace(':', ' ', 1)}" in it["links"]
        assert bl_bounds.origin_of(it) == ("retro", sprint["sp"])
    assert "filed" in capsys.readouterr().out


def test_bounds_finding_needs_failure_and_evidence_a_near_duplicate_gets_it_in_its_notes(sprint, capsys):
    repo_ = sprint["repo"]
    commit(repo_, "plan")
    sha = head(repo_)
    bl = bl_base.Backlog(repo_)
    before = titles(repo_)
    outcome, dup = bl_bounds.file_finding(bl, finding(sprint["sp"], title="Story b exists", goal="b exists", evidence=[f"commit:{sha}"],
                                                      origin="review"), rows=[])
    assert outcome == "merged" and dup == sprint["st"]
    assert titles(repo_) == before  # no item was filed
    assert "Found again by the review of" in item_json(repo_, dup)["notes"] and sha in item_json(repo_, dup)["notes"]
    assert bl_bounds.origin_of(item_json(repo_, dup)) is None  # the duplicate is not a finding itself
    # the same words with no evidence are kept, not merged
    outcome, none = bl_bounds.file_finding(bl_base.Backlog(repo_), finding(sprint["sp"], title="Story b exists", goal="b exists"),
                                           rows=[])
    assert outcome == "kept" and none is None
    assert item_json(repo_, dup)["notes"].count("Found again") == 1
    assert "merged into the notes" in capsys.readouterr().out


def test_bounds_finding_needs_failure_and_evidence_a_bug_filed_is_a_draft_but_an_s1_joins_a_running_sprint(sprint):
    repo_, sp = autopilot_started(sprint)
    sha = head(repo_)
    kw = {"kind": "bug", "repro": argstr(is_file("src/zzz.txt")), "evidence": [f"commit:{sha}"], "origin": "review"}
    out, s3 = bl_bounds.file_finding(bl_base.Backlog(repo_), finding(sprint["sp"], title="Quartz tangerine wobble", goal="g1 fixed",
                                                                     severity="S3", **kw), rows=[])
    assert out == "filed" and "sprint" not in item_json(repo_, s3)
    out, s1 = bl_bounds.file_finding(bl_base.Backlog(repo_), finding(sp, title="Marmalade hexagon torque", goal="g2 fixed",
                                                                     severity="S1", **kw), rows=[])
    assert out == "filed" and item_json(repo_, s1)["sprint"] == sp  # the sprint's review files S1 into it
    assert bl_bounds.origin_of(item_json(repo_, s1)) == ("review", sp)


def test_bounds_finding_needs_failure_and_evidence_check_refuses_an_origin_with_no_evidence_or_a_bad_link(sprint):
    repo_ = sprint["repo"]
    st = sprint["st"]
    assert b(repo_, "check")[0] == 0
    edit(repo_, st, links=[f"origin retro {SPRINT_ID}"])
    code, out = b(repo_, "check")
    assert code == 1 and "names the failure's evidence" in out and st in out, out
    edit(repo_, st, links=[f"origin retro {SPRINT_ID}", "evidence commit abcdef1"])
    assert b(repo_, "check")[0] == 0
    for bad in ("origin retro", "origin everything " + SPRINT_ID, "evidence a hunch"):
        edit(repo_, st, links=[f"origin retro {SPRINT_ID}", "evidence commit abcdef1", bad])
        code, out = b(repo_, "check")
        assert code == 1 and "bounds: error" in out, (bad, out)


def test_bounds_finding_needs_failure_and_evidence_the_command_files_through_the_cli(sprint):
    repo_ = sprint["repo"]
    commit(repo_, "plan")
    code, out = b(repo_, "bounds", "file", "--origin", "retro", "--sprint", sprint["sp"], "--title", "Hunch",
                  "--goal", "g")
    assert code == 0 and "kept in the close commit body only" in out and "Hunch" not in titles(repo_), out
    code, out = b(repo_, "bounds", "file", "--origin", "retro", "--sprint", sprint["sp"], "--title", "Hunch",
                  "--goal", "g", "--evidence", "commit:" + "0" * 40)
    assert code == 1 and "evidence is not there" in out, out
    code, out = b(repo_, "bounds", "file", "--origin", "retro", "--sprint", sprint["sp"], "--title",
                  "Walrus kettle drum", "--goal", "quill is mended", "--evidence", f"commit:{head(repo_)}")
    assert code in (0, 1), out  # the host's own spool may hold a close row with no landed item
    if code == 0:
        assert "filed" in out and item(repo_, "Walrus kettle drum")["status"] == "draft"


# ---------------------------------------------------------------- a sprint of findings has no retrospective

def retro_sprint(sprint_, origins):
    """The fixture's story and bug given an origin each (None: none), everything done: the sprint ready to close."""
    repo_ = sprint_["repo"]
    for iid, origin in zip((sprint_["st"], sprint_["bg"]), origins):
        edit(repo_, iid, links=[f"origin {origin} {SPRINT_ID}", "evidence commit abcdef1"] if origin else [],
             status="done")
    for iid in (sprint_["tk"], sprint_["rv"]):
        edit(repo_, iid, status="done")
    return repo_


@pytest.mark.parametrize("origins,free", [(("review", "retro"), True), (("retro", "retro"), True),
                                          (("review", None), False), ((None, None), False),
                                          (("mid-sprint", "retro"), False), (("mid-sprint", "mid-sprint"), False)])
def test_bounds_retro_origin_has_no_retro_only_when_every_item_is_a_finding(sprint, origins, free):
    repo_ = retro_sprint(sprint, origins)
    assert bl_bounds.retro_free(bl_base.Backlog(repo_), sprint["sp"]) is free
    code, out = b(repo_, "close", sprint["sp"], "--summary")
    assert code == 0, out
    assert ("no retrospective" in out) is free, out
    assert out.startswith(f"delivered by {sprint['sp']}")  # the summary is the close commit's body, line for line


def test_bounds_retro_origin_has_no_retro_a_sprint_with_no_story_or_bug_is_not_free(sprint):
    repo_ = retro_sprint(sprint, ("review", "retro"))
    edit(repo_, sprint["st"], status="dropped")
    edit(repo_, sprint["bg"], status="dropped")  # dropped items are no work
    assert bl_bounds.retro_free(bl_base.Backlog(repo_), sprint["sp"]) is False


def test_bounds_retro_origin_has_no_retro_the_close_says_so_once_it_has_run(sprint):
    repo_ = retro_sprint(sprint, ("retro", "review"))
    code, out = b(repo_, "close", sprint["sp"])
    assert code == 0 and "no retrospective for" in out and "closed" in out, out


# ---------------------------------------------------------------- draft inflow stays within the done outflow

@pytest.mark.parametrize("out", range(0, 6))
def test_bounds_inflow_guard_trips_exactly_above_the_outflow(sprint, out):
    repo_ = sprint["repo"]
    commit(repo_, "plan")
    rows = [closed(1, out), {"id": "row-1"}]
    for n in range(0, 8):
        bl = bl_base.Backlog(repo_)
        plant_drafts(bl, n)  # findings of another sprint: only the inflow counts against the outflow here
        assert bool([t for t in bl_bounds.guard_trips(bl, rows) if "inflow" in t]) == (n > out), (out, n)
        filing = finding(sprint["sp"], title="Gecko lantern ribbon", goal="orchard mended", evidence=["ops:row-1"])
        if n + 1 > out:  # one more draft would be more inflow than the sprints before landed
            with pytest.raises(bl_base.Refused, match="inflow"):
                bl_bounds.file_finding(bl, filing, rows=rows)
        else:
            assert bl_bounds.file_finding(bl, filing, rows=rows)[0] == "filed"
            for f in sorted((Path(repo_) / backlog.REL_DIR).glob("*.json")):
                if "Gecko" in f.read_text(encoding="utf-8"):
                    f.unlink()


def test_bounds_inflow_guard_the_outflow_is_the_last_three_sprints_closed(sprint):
    rows = [closed(1, 40, day=1), closed(2, 1, day=2), closed(3, 1, day=3), closed(4, 2, day=4)]
    assert bl_bounds.outflow(rows) == (4, 3)  # the first sprint, the oldest, is out of the window
    assert bl_bounds.outflow([]) == (None, 0)
    assert bl_bounds.outflow([{"event": "done.refused", "item": "x"}]) == (None, 0)
    assert bl_bounds.outflow(rows + [dict(closed(4, 9, day=5))]) == (11, 3)  # a sprint's newest row replaces its older one
    bl = bl_base.Backlog(sprint["repo"])
    plant_drafts(bl, 4)
    assert bl_bounds.guard_trips(bl, rows) == []
    plant_drafts(bl, 5)
    assert any("inflow" in t for t in bl_bounds.guard_trips(bl, rows))


def test_bounds_inflow_guard_no_close_row_means_no_judgement_and_a_filing_is_not_refused_for_it(sprint):
    repo_ = sprint["repo"]
    commit(repo_, "plan")
    bl = bl_base.Backlog(repo_)
    plant_drafts(bl, 7)
    assert [t for t in bl_bounds.guard_trips(bl, []) if "inflow" in t] == []  # unknown outflow, not zero
    outcome, iid = bl_bounds.file_finding(bl, finding(sprint["sp"], title="Ocelot paprika drum", goal="saddle mended",
                                                      evidence=[f"commit:{head(repo_)}"]), rows=[])
    assert outcome == "filed"


@pytest.mark.parametrize("have", range(0, 8))
def test_bounds_inflow_guard_findings_per_sprint_are_capped(sprint, have):
    repo_ = sprint["repo"]
    commit(repo_, "plan")
    bl = bl_base.Backlog(repo_)
    plant_drafts(bl, have, sprint_id=sprint["sp"])
    kw = dict(title="Pelican quiver sonnet", goal="harbour mended", evidence=[f"commit:{head(repo_)}"])
    if have >= bl_bounds.FINDINGS_PER_SPRINT:
        with pytest.raises(bl_base.Refused, match="findings filed already"):
            bl_bounds.file_finding(bl, finding(sprint["sp"], **kw), rows=[])
    else:
        assert bl_bounds.file_finding(bl, finding(sprint["sp"], **kw), rows=[])[0] == "filed"
    errs, _ = bl_bounds.problems(bl)
    assert bool([e for e in errs if "findings were filed" in e]) == (have > bl_bounds.FINDINGS_PER_SPRINT)


@pytest.mark.parametrize("have", (0, 59, 60, 61, 70))
def test_bounds_inflow_guard_open_drafts_are_capped(sprint, have):
    repo_ = sprint["repo"]
    commit(repo_, "plan")
    bl = bl_base.Backlog(repo_)
    plant_drafts(bl, have, origin=False)
    n = bl_bounds.open_drafts(bl)
    errs, warns = bl_bounds.problems(bl)
    assert bool(warns) == (n > bl_bounds.OPEN_DRAFTS_MAX)
    kw = dict(title="Lemur anvil carousel", goal="cellar mended", evidence=[f"commit:{head(repo_)}"])
    if n >= bl_bounds.OPEN_DRAFTS_MAX:
        with pytest.raises(bl_base.Refused, match="open drafts"):
            bl_bounds.file_finding(bl, finding(sprint["sp"], **kw), rows=[])
    else:
        assert bl_bounds.file_finding(bl, finding(sprint["sp"], **kw), rows=[])[0] == "filed"
    assert any("open drafts" in t for t in bl_bounds.guard_trips(bl, [])) == (n > bl_bounds.OPEN_DRAFTS_MAX)


def test_bounds_inflow_guard_check_reports_more_findings_than_the_cap_on_disk(sprint):
    repo_ = sprint["repo"]
    st = sprint["st"]
    for n in range(bl_bounds.FINDINGS_PER_SPRINT + 1):
        assert b(repo_, "new", "story", "--title", f"Finding {n}", "--goal", "g", "--check",
                 argstr(is_file("src/b.txt")))[0] == 0
        iid = item(repo_, f"Finding {n}")["id"]
        edit(repo_, iid, links=[f"origin retro {SPRINT_ID}", "evidence commit abcdef1"])
        code, out = b(repo_, "check")
        assert (code == 1) == (n + 1 > bl_bounds.FINDINGS_PER_SPRINT), (n, out)
    assert f"{SPRINT_ID}: 6 findings were filed" in out
    assert st


# ---------------------------------------------------------------- an item is refused or reopened at most three times

def rows_refused(iid, n):
    return [{"id": f"refused-{iid}-{k}", "ts": DAY, "surface": "ops", "v": 1, "event": "done.refused", "item": iid,
             "reasons": ["check-failed"], "ms": 5} for k in range(n)]


@pytest.mark.parametrize("n", range(0, 6))
def test_bounds_rework_cap_refused_dones_set_the_item_aside_at_the_cap(sprint, n):
    repo_, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    bl = bl_base.Backlog(repo_)
    rows = rows_refused(tk, n) + rows_refused(bg, 1) + rows_refused("TK-" + "z" * 8, 9)  # another item's rows count apart
    assert bl_bounds.refusals(rows, tk) == n and bl_bounds.refusals(rows, bg) == 1
    ready, aside = bl_bounds.ready_items(bl, sprint["sp"], rows)
    assert (tk in ready) == (n < bl_bounds.REWORK_CAP) and (tk in [a[0] for a in aside]) == (n >= bl_bounds.REWORK_CAP)
    assert bg in ready  # one refusal is under the cap
    assert bl_bounds.at_cap((n, 0)) == (n >= bl_bounds.REWORK_CAP)


@pytest.mark.parametrize("reopened", range(0, 5))
def test_bounds_rework_cap_reopens_are_counted_from_the_commits_that_took_the_item_back(sprint, reopened):
    repo_, tk = sprint["repo"], sprint["tk"]
    commit(repo_, "plan")
    assert bl_bounds.reopens(repo_, tk) == 0
    for n in range(reopened):
        edit(repo_, tk, status="done")
        commit(repo_, f"done {n}")
        edit(repo_, tk, status="todo")
        commit(repo_, f"reopen {n}")
    edit(repo_, tk, status="done")  # done, not reopened: the count does not move
    commit(repo_, "done again")
    assert bl_bounds.reopens(repo_, tk) == reopened
    edit(repo_, tk, status="todo")
    commit(repo_, "reopened")
    assert bl_bounds.reopens(repo_, tk) == reopened + 1


def test_bounds_rework_cap_refusals_and_reopens_add_up_and_the_cli_names_the_item_set_aside(sprint):
    repo_, tk = sprint["repo"], sprint["tk"]
    commit(repo_, "plan")
    for n in range(2):  # two reopens...
        edit(repo_, tk, status="done")
        commit(repo_, f"done {n}")
        edit(repo_, tk, status="todo")
        commit(repo_, f"reopen {n}")
    bl = bl_base.Backlog(repo_)
    assert not bl_bounds.at_cap(bl_bounds.rework(repo_, rows_refused(tk, 0), tk))
    assert bl_bounds.at_cap(bl_bounds.rework(repo_, rows_refused(tk, 1), tk))  # ...and one refusal reach the cap of three
    assert bl_bounds.rework(repo_, [], tk) == (0, 2)
    st = bl_bounds.stop_state(bl, sprint["sp"], rows=rows_refused(tk, 1))
    assert tk in [a[0] for a in st["aside"]] and tk not in st["ready"]
    assert sprint["bg"] in st["ready"] and st["stop"] is False


def test_bounds_rework_cap_no_refusal_row_is_zero_and_unreadable_rows_are_no_refusal(sprint, monkeypatch):
    assert bl_bounds.refusals([], sprint["tk"]) == 0 and bl_bounds.refusals(None, sprint["tk"]) == 0
    monkeypatch.setattr(bl_bounds, "ops_rows", lambda root: None)
    st = bl_bounds.stop_state(bl_base.Backlog(sprint["repo"]), sprint["sp"])
    assert sprint["tk"] in st["ready"]


# ---------------------------------------------------------------- the manager stops, and says which

def test_bounds_stops_on_budget_exactly_when_the_landed_count_reaches_it(sprint):
    bl = bl_base.Backlog(sprint["repo"])
    for budget in (1, 2, 3, 4, 6, 7):  # budgets that share a factor with the landed counts, or exceed them
        for landed in range(0, 10):
            st = bl_bounds.stop_state(bl, sprint["sp"], budget, landed, rows=[])
            assert st["stop"] == (landed >= budget), (budget, landed)
            assert (st["cause"] == "sprint-budget") == (landed >= budget)
        assert bl_bounds.stop_state(bl, sprint["sp"], None, budget, rows=[])["stop"] is False  # none given: no stop


def test_bounds_stops_on_budget_no_ready_item_and_the_inflow_guard_are_the_other_causes(sprint):
    repo_, sp = sprint["repo"], sprint["sp"]
    bl = bl_base.Backlog(repo_)
    assert bl_bounds.stop_state(bl, sp, rows=[])["cause"] is None
    edit(repo_, sprint["tk"], status="doing", claimed_by="worker")  # in flight: not ready
    edit(repo_, sprint["bg"], status="done")
    st = bl_bounds.stop_state(bl_base.Backlog(repo_), sp, rows=[])
    assert st["stop"] and st["cause"] == "no-ready" and st["ready"] == [], st
    assert "no item" in st["detail"]["no-ready"]
    edit(repo_, sprint["tk"], status="todo")
    bl = bl_base.Backlog(repo_)
    assert bl_bounds.stop_state(bl, sp, rows=[])["stop"] is False
    plant_drafts(bl, 3)
    st = bl_bounds.stop_state(bl, sp, rows=[closed(1, 1)])  # three drafts of findings, one item landed
    assert st["stop"] and st["cause"] == "inflow-guard" and "inflow 3" in st["detail"]["inflow-guard"], st
    st = bl_bounds.stop_state(bl, sp, 2, 2, rows=[closed(1, 1)])  # all three: reported in the order of STOPS
    assert st["causes"] == ["sprint-budget", "inflow-guard"] and st["cause"] == "sprint-budget"
    assert tuple(sorted(st["causes"], key=bl_bounds.STOPS.index)) == tuple(st["causes"])


def test_bounds_stops_on_budget_the_cli_exits_1_and_the_first_line_names_the_cause(sprint):
    repo_, sp = sprint["repo"], sprint["sp"]
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--budget", "2", "--landed", "1")
    assert code == 0 and out.startswith("bounds: go: ") and "ready" in out, out
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--budget", "2", "--landed", "2")
    assert code == 1 and out.splitlines()[0].startswith("bounds: stop sprint-budget: 2 of 2 item(s) landed"), out
    for i in (sprint["st"], sprint["tk"], sprint["bg"]):
        edit(repo_, i, status="done")
    code, out = b(repo_, "bounds", "stop", "--sprint", sp)
    assert code == 1 and out.splitlines()[0].startswith("bounds: stop no-ready: "), out
    code, out = b(repo_, "bounds", "stop", "--sprint", sp, "--json")
    assert code == 1 and json.loads(out)["cause"] == "no-ready"
    assert b(repo_, "bounds", "stop")[0] == 2  # a sprint is required
    assert b(repo_, "bounds", "stop", "--sprint", sprint["st"])[0] == 2  # and it is a sprint


def test_bounds_stops_on_budget_report_lists_the_limits_and_what_is_over(sprint):
    repo_ = sprint["repo"]
    code, out = b(repo_, "bounds")
    assert code == 0 and "5 findings per sprint" in out and "60 open drafts" in out and "outflow" in out, out
    code, out = b(repo_, "bounds", "report", "--json")
    lim = json.loads(out)["limits"]
    assert lim == {"findings_per_sprint": 5, "rework_cap": 3, "outflow_sprints": 3, "open_drafts_max": 60}


# ---------------------------------------------------------------- how the module sits in the tools

def test_bounds_module_registers_itself_and_puts_its_rules_in_front_of_check_new_and_close():
    import bl_check
    import bl_land
    assert "bounds" in bl_cli.COMMANDS and list(bl_cli.COMMANDS)[-1] == "bounds"
    assert bl_cli.handler_of("check") is bl_bounds.cmd_check is bl_check.cmd_check
    assert bl_cli.handler_of("close") is bl_bounds.cmd_close is bl_land.cmd_close
    assert bl_cli.handler_of("new") is bl_bounds.cmd_new
    assert set(bl_bounds.ORIGINAL) == {"check", "new", "close"}
    before = dict(bl_bounds.ORIGINAL)
    bl_bounds.install()  # a second install wraps nothing again
    assert bl_bounds.ORIGINAL == before
    reg = {}
    bl_bounds.install(reg)  # a registry without the commands is left as it is
    assert reg == {}


def test_bounds_module_imports_only_the_base_and_the_cli_at_load_and_never_backlog():
    tree = ast.parse((Path(TOOLS) / "bl_bounds.py").read_text(encoding="utf-8"))
    top = {a.name.split(".")[0] for n in tree.body if isinstance(n, ast.Import) for a in n.names}
    top |= {n.module.split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom)}
    assert {m for m in top if m.startswith("bl_")} == {"bl_base", "bl_cli"}
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names) or
                   isinstance(n, ast.ImportFrom) and n.module == "backlog" for n in ast.walk(tree))


def test_bounds_docs_state_the_rules_the_module_enforces():
    text = (Path(TOOLS).parent / "kb" / "_self" / "backlog.md").read_text(encoding="utf-8")
    sec = text[text.index("## Bounds of the autopilot's work"):]
    sec = sec[:sec.index("\n## ", 5)] if "\n## " in sec[5:] else sec
    for word in ("FINDINGS_PER_SPRINT", "REWORK_CAP", "OUTFLOW_SPRINTS", "OPEN_DRAFTS_MAX", "bounds stop", "bounds file",
                 "sprint-budget", "inflow-guard", "no-ready", "origin", "evidence", "S1", "retrospective"):
        assert word in sec, word
    for name, value in (("FINDINGS_PER_SPRINT", 5), ("REWORK_CAP", 3), ("OUTFLOW_SPRINTS", 3), ("OPEN_DRAFTS_MAX", 60)):
        assert getattr(bl_bounds, name) == value
        assert re.search(rf"`{name}`[^\n]*\b{value}\b", sec), name
    tools = (Path(TOOLS).parent / "kb" / "_self" / "tools.md").read_text(encoding="utf-8")
    assert "backlog.py bounds" in tools and "bl_bounds.py" in tools
