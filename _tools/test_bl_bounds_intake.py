"""Tests of the intake origin of `backlog.py bounds` (bl_bounds.py): `intake --file` files each detector candidate
through `file_finding`, so a draft carries its origin (`intake`) and its evidence (the detector fingerprint), a
near-duplicate of an open item is merged into that item's notes once, and the open-drafts cap refuses a further
finding with the cap message and exit 1. The detectors are planted as test_intake.py plants them (its helpers are
imported), the backlog is a throwaway directory.
"""
import json
import re

import pytest

import backlog
import bl_base
import bl_bounds
import bl_intake
from bl_intake import Candidate
from test_intake import files, intake, load, register

WORDS = ["amber", "basalt", "cobalt", "dune", "ember", "fjord", "garnet", "harbor", "indigo", "jasper"]


@pytest.fixture(autouse=True)
def empty_registry(monkeypatch):
    monkeypatch.setattr(bl_intake, "DETECTORS", {})


def finding(key, title, goal="The doc names no gone file.", kind="story"):
    return Candidate(kind=kind, title=title, goal=goal, key=key, checks=[["python3", "-c", "pass"]]) \
        if kind == "story" else Candidate(kind=kind, title=title, goal=goal, key=key, severity="S3")


def plant_drafts(root, n):
    """N unrelated open drafts in the backlog at `root`: each title is made of words no finding of these tests uses."""
    bl = bl_base.Backlog(root)
    for k in range(n):
        iid = f"ST-{'abcdefgh'[k % 8]}{'abcdefgh'[(k // 8) % 8]}{'abcdefgh'[(k // 64) % 8]}aaaaa"
        bl.save({"id": iid, "kind": "story", "title": f"Filler{k}x item{k}y", "status": "draft", "priority": "P2",
                 "rank": 0, "goal": f"Filler goal{k}z"})
    return bl_base.Backlog(root)


def drafts(root):
    return [it for it in load(root) if it["status"] == "draft"]


def test_bl_bounds_intake_files_through_bounds_origin_evidence_and_a_second_run_files_nothing(tmp_path, capsys):
    assert "intake" in bl_bounds.ORIGINS
    register("docs", finding("stale-doc:a", "Amber doc names a gone file"))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 0, err
    assert out[-1] == "intake: 1 candidate(s), 1 new filed, 0 skipped"
    assert any(ln.startswith("bounds: filed ") and ln.endswith(" from intake") for ln in out)
    (it,) = load(tmp_path)
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    assert it["status"] == "draft" and "sprint" not in it
    assert bl_bounds.origin_of(it) == ("intake", None)
    assert bl_bounds.evidence_of(it) == [("fingerprint", fp)]
    assert f"fingerprint {fp}" in it["links"] and it["links"][-1] == "detector docs"  # the links intake always wrote
    bl = bl_base.Backlog(tmp_path)
    assert bl_bounds.problems(bl) == ([], [])  # an intake origin has its evidence: `check` has no error for it
    assert bl_bounds.findings(bl, "SP-" + "a" * 8) == [] and bl_bounds.inflow(bl) == 0
    assert bl_bounds.guard_trips(bl, []) == []
    code, out, _ = intake(tmp_path, capsys, "--file")  # the same finding again
    assert code == 0 and len(files(tmp_path)) == 1 and "(skipped: filed as " in out[0]
    assert out[-1] == "intake: 1 candidate(s), 0 new filed, 1 skipped"


def test_bl_bounds_intake_files_through_bounds_a_near_duplicate_is_merged_once_not_filed(tmp_path, capsys):
    register("docs", finding("stale-doc:a", "Basalt harbor index drifts from its sources", goal="Index matches sources."))
    assert intake(tmp_path, capsys, "--file")[0] == 0
    (first,) = load(tmp_path)
    # another detector reports the same finding in the same words: a new fingerprint, no new item
    register("links", finding("dead-link:b", "Basalt harbor index drifts from its sources", goal="Index matches sources."))
    fp2 = bl_intake.fingerprint("links", "dead-link:b")
    for _ in range(3):  # a repeat run merges nothing more: the notes keep the finding once
        code, out, err = intake(tmp_path, capsys, "--file")
        assert code == 0, err
        assert len(files(tmp_path)) == 1
    (it,) = load(tmp_path)
    assert it["id"] == first["id"] and it["notes"].count("Found again by the intake") == 1
    assert f"fingerprint {fp2}" in it["notes"]
    assert any("a near-duplicate" in ln for ln in out)
    assert out[-1] == "intake: 2 candidate(s), 0 new filed, 2 skipped"


def test_bl_bounds_intake_files_through_bounds_one_detectors_alike_findings_are_each_filed(tmp_path, capsys):
    register("docs", finding("stale-doc:a", "Garnet harbor page names a gone file"),
             finding("stale-doc:b", "Garnet harbor page names a gone file"))  # two findings, one wording, one detector
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 0, err
    assert out[-1] == "intake: 2 candidate(s), 2 new filed, 0 skipped" and len(files(tmp_path)) == 2


@pytest.mark.parametrize("have", [0, 1, 30, 58, 59])
def test_bl_bounds_intake_files_through_bounds_below_the_cap_a_finding_is_filed(tmp_path, capsys, have):
    plant_drafts(tmp_path, have)
    register("docs", finding("stale-doc:cap", "Cobalt dune gains a gap"))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 0, err
    assert len(drafts(tmp_path)) == have + 1


@pytest.mark.parametrize("have", [60, 61, 75])
def test_bl_bounds_intake_files_through_bounds_at_the_cap_a_finding_is_refused_with_the_cap_message(tmp_path, capsys,
                                                                                                    have):
    plant_drafts(tmp_path, have)
    register("docs", finding("stale-doc:one", "Cobalt dune gains a gap"),
             finding("stale-doc:two", "Ember fjord loses a test", goal="The test is back."))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 1
    assert f"bounds file: {have} open drafts (at most {bl_bounds.OPEN_DRAFTS_MAX}): triage before filing" in err
    assert err.count("open drafts") == 1  # the cap holds for every later candidate: said once
    assert len(drafts(tmp_path)) == have  # nothing was filed
    assert out[-1] == "intake: 2 candidate(s), 0 new filed, 0 skipped, 2 refused by the bounds"
    # the same exit code and message as `bounds file`
    sprint = bl_base.new_id("sprint")
    bl = bl_base.Backlog(tmp_path)
    bl.save({"id": sprint, "kind": "sprint", "title": "Sprint", "status": "planned", "rank": 0, "goal": "g"})
    with pytest.raises(bl_base.Refused, match=re.escape(f"{have} open drafts (at most 60)")):
        bl_bounds.file_finding(bl_base.Backlog(tmp_path), type("A", (), dict(
            origin="retro", sprint=sprint, kind="story", title="Garnet indigo twist", goal="Twist undone",
            severity=None, repro=None, check=None, touch=None, evidence=["ops:row-1"]))(), rows=[{"id": "row-1"}])


def test_bl_bounds_intake_files_through_bounds_an_intake_origin_is_not_retro_free_nor_counted_as_inflow():
    assert "intake" not in bl_bounds.RETRO_FREE_ORIGINS
    fp = "0123456789ab"
    it = {"id": "ST-aaaaaaaa", "kind": "story", "title": "t", "status": "draft", "links": [f"fingerprint {fp}"]}
    assert bl_bounds.origin_of(it) is None  # a bug red-pipeline files has a fingerprint and no detector: no origin
    it["links"].append("detector docs")
    assert bl_bounds.origin_of(it) == ("intake", None) and bl_bounds.evidence_of(it) == [("fingerprint", fp)]
    explicit = dict(it, links=it["links"] + ["origin retro SP-" + "a" * 8, "evidence commit abcdef1"])
    assert bl_bounds.origin_of(explicit) == ("retro", "SP-" + "a" * 8)  # an explicit origin link wins
    assert bl_bounds.evidence_of(explicit) == [("commit", "abcdef1")]


def test_bl_bounds_intake_files_through_bounds_the_origin_intake_is_for_intake_file_only(tmp_path, capsys):
    code, out, err = run(tmp_path, capsys, "bounds", "file", "--origin", "intake", "--title", "T", "--goal", "G",
                                "--evidence", "fingerprint:0123456789ab")
    assert code == 2 and "intake --file" in err
    sprint = bl_base.new_id("sprint")
    bl = bl_base.Backlog(tmp_path)
    bl.save({"id": sprint, "kind": "sprint", "title": "Sprint", "status": "planned", "rank": 0, "goal": "g"})
    code, out, err = run(tmp_path, capsys, "bounds", "file", "--origin", "retro", "--sprint", sprint, "--title", "T",
                                "--goal", "G", "--evidence", "fingerprint:0123456789ab")
    assert code == 2 and "intake finding only" in err
    assert not drafts(tmp_path)


def run(root, capsys, *args):
    """(exit code, stdout, stderr) of `backlog.py --root ROOT ARGS`, run in this process."""
    capsys.readouterr()
    code = backlog.main(["--root", str(root), *args])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_bl_bounds_intake_files_through_bounds_the_json_is_canonical(tmp_path, capsys):
    register("docs", finding("stale-doc:a", "Jasper indigo note", kind="bug"))
    assert intake(tmp_path, capsys, "--file")[0] == 0
    (f,) = files(tmp_path)
    assert json.loads(f.read_text(encoding="utf-8"))["repro"]["run"][-1] == bl_intake.fingerprint("docs", "stale-doc:a")
    assert backlog.validate(backlog.Backlog(tmp_path)) == []
