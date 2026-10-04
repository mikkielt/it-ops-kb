"""Tests of the filing of `backlog.py intake --file` (bl_intake.file_found, file_draft): each detector candidate no open
item's fingerprint covers is filed as a draft with its fingerprint and detector links, a near-duplicate of an open
item of another detector is merged into that item's notes once, and the open-drafts cap refuses a further candidate
with the cap message and exit 1. The detectors are planted as test_intake.py plants them (its helpers are imported),
the backlog is a throwaway directory.
"""
import json

import pytest

import backlog
import bl_base
import bl_intake
from bl_intake import Candidate
from test_intake import files, intake, load, register


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


def test_intake_filing_files_a_draft_with_its_links_and_a_second_run_files_nothing(tmp_path, capsys):
    register("docs", finding("stale-doc:a", "Amber doc names a gone file"))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 0, err
    assert out[-1] == "intake: 1 candidate(s), 1 new filed, 0 skipped"
    (it,) = load(tmp_path)
    assert f"intake: filed {it['id']} “Amber doc names a gone file”" in out
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    assert it["status"] == "draft" and "sprint" not in it
    assert f"fingerprint {fp}" in it["links"] and it["links"][-1] == "detector docs"  # the links intake always wrote
    assert bl_intake.detector_of(it) == "docs"
    assert backlog.validate(backlog.Backlog(tmp_path)) == []
    code, out, _ = intake(tmp_path, capsys, "--file")  # the same finding again
    assert code == 0 and len(files(tmp_path)) == 1 and "(skipped: filed as " in out[0]
    assert out[-1] == "intake: 1 candidate(s), 0 new filed, 1 skipped"


def test_intake_filing_a_near_duplicate_is_merged_once_not_filed(tmp_path, capsys):
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


def test_intake_filing_one_detectors_alike_findings_are_each_filed(tmp_path, capsys):
    register("docs", finding("stale-doc:a", "Garnet harbor page names a gone file"),
             finding("stale-doc:b", "Garnet harbor page names a gone file"))  # two findings, one wording, one detector
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 0, err
    assert out[-1] == "intake: 2 candidate(s), 2 new filed, 0 skipped" and len(files(tmp_path)) == 2


@pytest.mark.parametrize("have", [0, 1, 30, 58, 59])
def test_intake_filing_below_the_cap_a_finding_is_filed(tmp_path, capsys, have):
    plant_drafts(tmp_path, have)
    register("docs", finding("stale-doc:cap", "Cobalt dune gains a gap"))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 0, err
    assert len(drafts(tmp_path)) == have + 1


@pytest.mark.parametrize("have", [60, 61, 75])
def test_intake_filing_at_the_cap_a_finding_is_refused_with_the_cap_message(tmp_path, capsys, have):
    plant_drafts(tmp_path, have)
    register("docs", finding("stale-doc:one", "Cobalt dune gains a gap"),
             finding("stale-doc:two", "Ember fjord loses a test", goal="The test is back."))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 1
    assert f"intake: {have} open drafts (at most {bl_intake.OPEN_DRAFTS_MAX}): triage before filing" in err
    assert err.count("open drafts") == 1  # the cap holds for every later candidate: said once
    assert len(drafts(tmp_path)) == have  # nothing was filed
    assert out[-1] == "intake: 2 candidate(s), 0 new filed, 0 skipped, 2 refused"


def test_intake_filing_the_cap_planted_failure_a_higher_cap_files(tmp_path, capsys, monkeypatch):
    """The cap is the constant the filing reads: raised by one, the candidate at the old cap is filed."""
    plant_drafts(tmp_path, bl_intake.OPEN_DRAFTS_MAX)
    monkeypatch.setattr(bl_intake, "OPEN_DRAFTS_MAX", bl_intake.OPEN_DRAFTS_MAX + 1)
    register("docs", finding("stale-doc:cap", "Cobalt dune gains a gap"))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 0 and out[-1] == "intake: 1 candidate(s), 1 new filed, 0 skipped", err


def test_intake_filing_the_json_is_canonical(tmp_path, capsys):
    register("docs", finding("stale-doc:a", "Jasper indigo note", kind="bug"))
    assert intake(tmp_path, capsys, "--file")[0] == 0
    (f,) = files(tmp_path)
    assert json.loads(f.read_text(encoding="utf-8"))["repro"]["run"][-1] == bl_intake.fingerprint("docs", "stale-doc:a")
    assert backlog.validate(backlog.Backlog(tmp_path)) == []
