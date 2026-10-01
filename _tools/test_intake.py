"""backlog.py intake: the detector registry, fingerprints, dedup and the command (bl_intake.py).

Every test registers a planted detector in an emptied registry, so none depends on the detectors the kb ships. Planted
failures: a duplicate (a candidate whose fingerprint an open item already carries is skipped, a second --file files
nothing, a done or dropped item skips nothing), a `--status` that exits 1 while a detector reports the fingerprint and
0 once it stops (the passing one), a detector that raises and a candidate that cannot be filed (the others' findings
still print, exit 1), a malformed fingerprint (exit 2), and the same inputs giving the same lines in any registration
order.
"""
import json
from pathlib import Path

import pytest

import backlog
import bl_intake
from bl_intake import Candidate


@pytest.fixture(autouse=True)
def empty_registry(monkeypatch):
    monkeypatch.setattr(bl_intake, "DETECTORS", {})


def bug(key="stale-doc:a", title="A doc names a gone file", severity="S3", **kw):
    return Candidate(kind="bug", title=title, goal="The doc names no gone file.", key=key, severity=severity, **kw)


def story(key="missing-test:b"):
    return Candidate(kind="story", title="Tool b has no test", goal="Tool b has a test.", key=key,
                     checks=[["python3", "-c", "pass"]])


def register(name, *candidates):
    bl_intake.detector(name)(lambda root, found=candidates: [Candidate(**vars(c)) for c in found])


def intake(root, capsys, *args):
    """(exit code, stdout lines, stderr) of `backlog.py --root ROOT intake ARGS`, run in this process."""
    capsys.readouterr()
    code = backlog.main(["--root", str(root), "intake", *args])
    out = capsys.readouterr()
    return code, out.out.splitlines(), out.err


def files(root):
    d = Path(root) / backlog.REL_DIR
    return sorted(d.glob("*.json")) if d.is_dir() else []


def load(root):
    return [json.loads(f.read_text(encoding="utf-8")) for f in files(root)]


def test_intake_core_fingerprint_is_twelve_hex_and_stable():
    a = bl_intake.fingerprint("det", "k")
    assert bl_intake.FP_RE.fullmatch(a)
    assert a == bl_intake.fingerprint("det", "k")
    assert len({a, bl_intake.fingerprint("det", "k2"), bl_intake.fingerprint("other", "k")}) == 3


def test_intake_core_prints_candidates_and_writes_nothing(tmp_path, capsys):
    register("docs", bug(), story())
    code, out, err = intake(tmp_path, capsys)
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    assert code == 0 and err == ""
    assert f"docs bug {fp} A doc names a gone file" in out
    assert "  goal: The doc names no gone file." in out
    assert "  repro: python3 _tools/backlog.py intake --status " + fp in out
    assert f"  links: fingerprint {fp}" in out
    assert any(ln.startswith("docs story ") for ln in out) and "  check: python3 -c pass" in out
    assert out[-1] == "intake: 2 candidate(s), 2 new, 0 skipped"
    assert files(tmp_path) == []


def test_intake_core_no_detector_reports_nothing(tmp_path, capsys):
    assert intake(tmp_path, capsys) == (0, ["intake: no candidates"], "")


def test_intake_core_same_inputs_same_lines_in_any_order(tmp_path, capsys, monkeypatch):
    register("beta", bug("k2"), bug("k1", title="Another"))
    register("alpha", story())
    first = intake(tmp_path, capsys)
    monkeypatch.setattr(bl_intake, "DETECTORS", {})
    register("alpha", story())
    register("beta", bug("k1", title="Another"), bug("k2"))
    assert intake(tmp_path, capsys) == first
    assert [ln.split()[0] for ln in first[1] if not ln.startswith(("  ", "intake:"))] == ["alpha", "beta", "beta"]


def test_intake_core_one_finding_reported_twice_is_one_candidate(tmp_path, capsys):
    register("docs", bug(), bug(title="Same finding, other words"))
    code, out, _ = intake(tmp_path, capsys)
    assert code == 0 and out[-1] == "intake: 1 candidate(s), 1 new, 0 skipped"


def test_intake_core_file_writes_draft_items_outside_any_sprint(tmp_path, capsys):
    register("docs", bug(links=["pipeline 7"]), story())
    code, out, _ = intake(tmp_path, capsys, "--file")
    assert code == 0 and out[-1] == "intake: 2 candidate(s), 2 new filed, 0 skipped"
    items = {it["kind"]: it for it in load(tmp_path)}
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    b = items["bug"]
    assert b["status"] == "draft" and "sprint" not in b and "parent" not in b
    assert b["links"] == [f"fingerprint {fp}", "pipeline 7"]
    assert b["severity"] == "S3" and b["repro"] == {"run": bl_intake.STATUS_REPRO + [fp]}
    assert items["story"]["status"] == "draft" and items["story"]["checks"] == [{"run": ["python3", "-c", "pass"]}]
    assert backlog.validate(backlog.Backlog(tmp_path)) == []  # canonical form, fields, a bug's repro: all valid


def test_intake_core_planted_duplicate_is_skipped(tmp_path, capsys):
    register("docs", bug())
    assert intake(tmp_path, capsys, "--file")[0] == 0
    (iid,) = [it["id"] for it in load(tmp_path)]
    code, out, _ = intake(tmp_path, capsys, "--file")
    assert code == 0 and len(files(tmp_path)) == 1
    assert out[0].endswith(f"(skipped: filed as {iid} “A doc names a gone file”)")
    assert out[-1] == "intake: 1 candidate(s), 0 new filed, 1 skipped"
    assert not any(ln.startswith("  filed") for ln in out)


def test_intake_core_duplicate_of_a_hand_filed_open_item_is_skipped(tmp_path, capsys):
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    it = {"id": "BG-aaaaaaaa", "kind": "bug", "title": "Filed by hand", "status": "todo", "priority": "P2", "rank": 0,
          "goal": "g", "severity": "S3", "repro": {"run": ["python3", "-c", "raise SystemExit(1)"]},
          "links": [f"fingerprint {fp}"]}
    backlog.Backlog(tmp_path).save(it)
    register("docs", bug())
    code, out, _ = intake(tmp_path, capsys, "--file")
    assert code == 0 and "(skipped: filed as BG-aaaaaaaa" in out[0] and len(files(tmp_path)) == 1


@pytest.mark.parametrize("status", ["done", "dropped"])
def test_intake_core_a_finished_item_skips_nothing(tmp_path, capsys, status):
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    it = {"id": "BG-aaaaaaaa", "kind": "bug", "title": "Old", "status": status, "priority": "P2", "rank": 0,
          "goal": "g", "severity": "S3", "repro": {"run": ["python3", "-c", "raise SystemExit(1)"]},
          "links": [f"fingerprint {fp}"]}
    backlog.Backlog(tmp_path).save(it)
    register("docs", bug())
    code, out, _ = intake(tmp_path, capsys, "--file")
    assert code == 0 and out[-1] == "intake: 1 candidate(s), 1 new filed, 0 skipped" and len(files(tmp_path)) == 2


def test_intake_core_status_exits_1_while_reported_and_0_once_not(tmp_path, capsys):
    register("docs", bug())
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    code, out, _ = intake(tmp_path, capsys, "--status", fp)
    assert code == 1 and out == [f"intake: {fp} is still reported by docs: A doc names a gone file"]
    assert intake(tmp_path, capsys, "--status", bl_intake.fingerprint("docs", "other"))[0] == 0
    bl_intake.DETECTORS.clear()  # the finding is fixed: no detector reports it
    code, out, _ = intake(tmp_path, capsys, "--status", fp)
    assert code == 0 and out == [f"intake: {fp} is no longer reported"]


def test_intake_core_status_is_the_repro_of_the_filed_bug(tmp_path, capsys):
    register("docs", bug())
    intake(tmp_path, capsys, "--file")
    (it,) = load(tmp_path)
    argv = it["repro"]["run"]
    assert argv[:2] == ["python3", "_tools/backlog.py"]
    assert intake(tmp_path, capsys, *argv[3:])[0] == 1  # fails while the detector reports it
    bl_intake.DETECTORS.clear()
    assert intake(tmp_path, capsys, *argv[3:])[0] == 0  # passes once it does not


def test_intake_core_status_ignores_dedup(tmp_path, capsys):
    register("docs", bug())
    intake(tmp_path, capsys, "--file")
    fp = bl_intake.fingerprint("docs", "stale-doc:a")
    assert intake(tmp_path, capsys, "--status", fp)[0] == 1  # an item carries it, the detector still reports it


@pytest.mark.parametrize("args", [["--status", "xyz"], ["--status", "ABCDEF012345"], ["--status", "0123456789ab", "--file"]])
def test_intake_core_a_bad_argument_exits_2(tmp_path, capsys, args):
    code, out, err = intake(tmp_path, capsys, *args)
    assert code == 2 and out == [] and err.startswith("intake:")


def test_intake_core_a_failing_detector_does_not_hide_the_others(tmp_path, capsys):
    def boom(root):
        raise RuntimeError("cannot read")
    bl_intake.DETECTORS["aaa-broken"] = boom
    register("docs", bug(), Candidate(kind="bug", title="No severity", goal="g", key="k", severity="S9"),
             Candidate(kind="story", title="No checks", goal="g", key="k2"))
    code, out, err = intake(tmp_path, capsys, "--file")
    assert code == 1 and out[-1] == "intake: 1 candidate(s), 1 new filed, 0 skipped"
    assert "aaa-broken: raised RuntimeError: cannot read" in err
    assert "docs: candidate 'No severity' refused: severity 'S9'" in err
    assert "docs: candidate 'No checks' refused: a story needs checks" in err
    assert len(files(tmp_path)) == 1


def test_intake_core_status_cannot_pass_while_a_detector_fails(tmp_path, capsys):
    def boom(root):
        raise RuntimeError("cannot read")
    bl_intake.DETECTORS["broken"] = boom
    code, out, _ = intake(tmp_path, capsys, "--status", "0123456789ab")
    assert code == 1 and out == ["intake: 0123456789ab is not reported, but a detector failed to run"]


def test_intake_core_multiline_text_prints_on_one_line(tmp_path, capsys):
    register("docs", bug(title="Two\nlines   here"))
    _, out, _ = intake(tmp_path, capsys)
    assert out[0].endswith(" Two lines here")

