"""backlog.py intake: the detector registry, fingerprints, dedup and the command (bl_intake.py).

Every test registers a planted detector in an emptied registry, so none depends on the detectors the kb ships. Planted
failures: a duplicate (a candidate whose fingerprint an open item already carries is skipped, a second --file files
nothing, a done or dropped item skips nothing), a `--status` that exits 1 while a detector reports the fingerprint and
0 once it stops (the passing one), a detector that raises and a candidate that cannot be filed (the others' findings
still print, exit 1), a malformed fingerprint (exit 2), and the same inputs giving the same lines in any registration
order.
"""
import json
import time
from pathlib import Path

import pytest

import backlog
import bl_intake
from bl_intake import Candidate
from conftest import Repo


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


# ------------------------------------------------------------------ the drift detector (intake_drift)
#
# Each scenario is a throwaway git repository whose commits carry dates the test sets, with `origin/main` pointing at
# its tip. Planted: a doing item with an old work commit (reported) beside one with a recent one, with only claim
# commits, and with none (all left out); a todo item whose check passes (reported) beside one whose check fails, one of
# two checks failing, and one whose touches did not change since its file (all left out, the last without running
# its checks); a check that exceeds the timeout (left out and counted); a check that runs the whole tests.py or
# stress_test.py (never run, counted); a check that sleeps past the total budget (cut, and the items after it not
# checked, counted).

T0 = 1767225600  # 2026-01-01T00:00:00Z
HOUR = 3600
PASS_CHECK = {"run": ["python3", "-c", "pass"]}
FAIL_CHECK = {"run": ["python3", "-c", "raise SystemExit(1)"]}
SLOW_CHECK = {"run": ["python3", "-c", "import time; time.sleep(60)"]}


class World:
    """A throwaway repository with dated commits."""

    def __init__(self, path):
        self.root = Path(path)
        self.repo = Repo(path)
        self.repo.git("init", "-q", "-b", "main")

    def commit(self, hours, message, files=None, trailer=None):
        """Commit `files` ({path: text}) `hours` after T0 with the KB-Work `trailer` (an id), return its hash."""
        for rel, text in (files or {}).items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
        self.repo.git("add", "-A")
        body = message + (f"\n\nKB-Work: {trailer}" if trailer else "")
        when = f"{T0 + int(hours * HOUR)} +0000"
        self.repo.git("commit", "-q", "--allow-empty", "-m", body,
                      env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
        return self.repo.rev("HEAD")

    def item(self, hours, iid, status, **kw):
        """Write and commit an item file `hours` after T0 (its own commit, no KB-Work: a planning commit)."""
        it = {"id": iid, "kind": "task", "title": f"Item {iid}", "status": status, "priority": "P2", "rank": 0,
              "goal": "g", **kw}
        backlog.Backlog(self.root).save(it)
        return self.commit(hours, f"chore(backlog): file {iid}")

    def publish(self):
        """Point origin/main at the tip, as a fetch would."""
        self.repo.git("update-ref", "refs/remotes/origin/main", "HEAD")


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    w.commit(0, "init", {"src/a.txt": "a\n"})
    return w


def drift_candidates(world):
    bl_intake.detector("drift")(bl_intake.drift_detector)
    return bl_intake.collect(world.root)


def test_intake_drift_hours_is_a_day():
    assert bl_intake.DRIFT_HOURS == 24


def test_intake_drift_doing_item_with_an_old_work_commit_is_reported(world):
    world.item(1, "TK-aaaaaaaa", "doing", touches=["src/**"])
    work = world.commit(2, "feat: work", {"src/a.txt": "b\n"}, trailer="TK-aaaaaaaa")
    world.commit(60, "feat: other", {"src/z.txt": "z\n"})
    world.publish()
    d = bl_intake.scan_drift(world.root)
    assert d.stale == {"TK-aaaaaaaa": (work, 58)} and d.passing == {} and d.timed_out == []


def test_intake_drift_doing_item_with_a_recent_work_commit_is_not_reported(world):
    world.item(1, "TK-aaaaaaaa", "doing", touches=["src/**"])
    world.commit(40, "feat: work", {"src/a.txt": "b\n"}, trailer="TK-aaaaaaaa")
    world.commit(60, "feat: other", {"src/z.txt": "z\n"})
    world.publish()
    assert bl_intake.scan_drift(world.root).stale == {}


def test_intake_drift_the_limit_is_strictly_more_than_the_hours(world):
    world.item(1, "TK-aaaaaaaa", "doing", touches=["src/**"])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"}, trailer="TK-aaaaaaaa")
    world.commit(26, "feat: other", {"src/z.txt": "z\n"})
    world.publish()
    assert bl_intake.scan_drift(world.root).stale == {}  # exactly 24 h
    world.commit(26.01, "feat: later", {"src/y.txt": "y\n"})
    world.publish()
    assert list(bl_intake.scan_drift(world.root).stale) == ["TK-aaaaaaaa"]


def test_intake_drift_only_the_newest_work_commit_counts(world):
    world.item(1, "TK-aaaaaaaa", "doing", touches=["src/**"])
    world.commit(2, "feat: first", {"src/a.txt": "b\n"}, trailer="TK-aaaaaaaa")
    world.commit(50, "feat: second", {"src/a.txt": "c\n"}, trailer="TK-aaaaaaaa")
    world.commit(60, "feat: other", {"src/z.txt": "z\n"})
    world.publish()
    assert bl_intake.scan_drift(world.root).stale == {}


def test_intake_drift_a_claim_commit_is_no_work(world):
    world.item(1, "TK-aaaaaaaa", "doing", touches=["src/**"])
    claim = bl_intake.BACKLOG_DIR + "/TK-aaaaaaaa.json"
    text = (world.root / claim).read_text(encoding="utf-8")
    world.commit(2, "chore(backlog): claim", {claim: text.replace('"rank": 0', '"rank": 1')}, trailer="TK-aaaaaaaa")
    world.commit(60, "feat: other", {"src/z.txt": "z\n"})
    world.publish()
    assert bl_intake.scan_drift(world.root).stale == {}  # its only KB-Work commit changed an item file alone


def test_intake_drift_a_doing_item_without_a_work_commit_is_not_reported(world):
    world.item(1, "TK-aaaaaaaa", "doing", touches=["src/**"])
    world.commit(60, "feat: other", {"src/z.txt": "z\n"}, trailer="TK-bbbbbbbb")
    world.publish()
    assert bl_intake.scan_drift(world.root).stale == {}


def test_intake_drift_a_story_is_reported_for_the_work_of_its_task(world):
    world.item(1, "ST-aaaaaaaa", "doing", kind="story", checks=[PASS_CHECK])
    world.item(1.5, "TK-bbbbbbbb", "done", parent="ST-aaaaaaaa", touches=["src/**"])
    work = world.commit(2, "feat: work", {"src/a.txt": "b\n"}, trailer="TK-bbbbbbbb")
    world.commit(60, "feat: other", {"src/z.txt": "z\n"})
    world.publish()
    assert bl_intake.scan_drift(world.root).stale == {"ST-aaaaaaaa": (work, 58)}


def test_intake_drift_without_origin_main_no_doing_item_is_reported(world):
    world.item(1, "TK-aaaaaaaa", "doing", touches=["src/**"])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"}, trailer="TK-aaaaaaaa")
    world.commit(60, "feat: other", {"src/z.txt": "z\n"})
    assert bl_intake.scan_drift(world.root).stale == {}


def test_intake_drift_a_todo_item_whose_check_passes_is_reported(world):
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[PASS_CHECK, PASS_CHECK])
    world.item(1, "TK-bbbbbbbb", "draft", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    d = bl_intake.scan_drift(world.root)
    assert d.passing == {"TK-aaaaaaaa": 2, "TK-bbbbbbbb": 1} and d.timed_out == [] and d.ran == 2


def test_intake_drift_a_todo_item_whose_check_fails_is_not_reported(world):
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[FAIL_CHECK])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"], checks=[PASS_CHECK, FAIL_CHECK])
    world.item(1, "TK-cccccccc", "todo", touches=["src/**"],
               checks=[{"run": ["python3", "-c", "print('x')"], "match": "never printed"}])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    d = bl_intake.scan_drift(world.root)
    assert d.passing == {} and d.timed_out == [] and d.ran == 3


def test_intake_drift_a_check_over_the_timeout_is_not_reported_and_counted(world):
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[SLOW_CHECK])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"], checks=[PASS_CHECK, SLOW_CHECK])
    world.item(1, "TK-cccccccc", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    d = bl_intake.scan_drift(world.root, timeout=1)
    assert d.passing == {"TK-cccccccc": 1} and d.timed_out == ["TK-aaaaaaaa", "TK-bbbbbbbb"]


def test_intake_drift_checks_run_only_when_touches_changed_since_the_item_file(world):
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    world.item(3, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[PASS_CHECK])  # file newer than the change
    world.item(3, "TK-bbbbbbbb", "todo", touches=["docs/**"], checks=[PASS_CHECK])  # nothing under docs/
    d = bl_intake.scan_drift(world.root)
    assert d.passing == {} and d.ran == 0
    world.commit(4, "feat: more", {"src/b.txt": "b\n"})
    world.commit(5, "docs: more", {"docs/x.md": "x\n"})
    d = bl_intake.scan_drift(world.root)
    assert d.passing == {"TK-aaaaaaaa": 1, "TK-bbbbbbbb": 1} and d.ran == 2


def test_intake_drift_items_without_touches_checks_or_an_open_status_run_nothing(world):
    world.item(1, "TK-aaaaaaaa", "todo", checks=[PASS_CHECK])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"])
    world.item(1, "TK-cccccccc", "done", touches=["src/**"], checks=[PASS_CHECK])
    world.item(1, "TK-dddddddd", "dropped", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    d = bl_intake.scan_drift(world.root)
    assert d.passing == {} and d.ran == 0


def test_intake_drift_one_story_lists_the_items_and_its_fingerprint_is_the_sorted_ids(world):
    world.item(1, "TK-bbbbbbbb", "doing", touches=["src/**"])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"}, trailer="TK-bbbbbbbb")
    world.item(3, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(4, "feat: more", {"src/b.txt": "b\n"})
    world.commit(60, "feat: other", {"src/z.txt": "z\n"})
    world.publish()
    found, failures = drift_candidates(world)
    assert failures == [] and len(found) == 1
    (c,) = found
    assert c.kind == "story" and c.detector == "drift" and c.key == "TK-aaaaaaaa,TK-bbbbbbbb"
    assert c.fp == bl_intake.fingerprint("drift", "TK-aaaaaaaa,TK-bbbbbbbb")
    assert "TK-aaaaaaaa" in c.goal and "TK-bbbbbbbb" in c.goal and c.title.startswith("Drift: 2 ")
    assert "TK-bbbbbbbb: doing" in c.notes and "TK-aaaaaaaa: its 1 check(s) already pass" in c.notes
    assert c.checks == [bl_intake.STATUS_REPRO + [c.fp]]


def test_intake_drift_the_timeouts_are_counted_in_the_story(world, monkeypatch):
    monkeypatch.setattr(bl_intake, "CHECK_TIMEOUT_S", 1)
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[SLOW_CHECK])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    (c,), _ = drift_candidates(world)
    assert c.key == "TK-bbbbbbbb" and "1 item(s) had a check that exceeded 1 s" in c.notes


def test_intake_drift_a_timeout_alone_files_nothing(world, monkeypatch):
    monkeypatch.setattr(bl_intake, "CHECK_TIMEOUT_S", 1)
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[SLOW_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    assert drift_candidates(world) == ([], [])


def test_intake_drift_budget_is_well_under_a_minute_and_bounds_each_check():
    assert bl_intake.CHECK_TIMEOUT_S < bl_intake.DRIFT_BUDGET_S <= 30


@pytest.mark.parametrize("run, heavy", [
    (["python3", "_tools/tests.py"], True),
    (["python3", "_tools/tests.py", "-q"], True),
    (["python3", "_tools\\tests.py"], True),
    (["python3", "_tools/stress_test.py"], True),
    (["python3", "_tools/stress_test.py", "-k", "x"], True),
    (["python3", "_tools/tests.py", "-k", "intake_drift"], False),
    (["python3", "_tools/tests.py", "-kintake"], False),
    (["python3", "_tools/backlog.py", "check"], False),
    (["python3", "-c", "pass"], False),
])
def test_intake_drift_a_whole_suite_or_stress_check_is_heavy(run, heavy):
    assert bl_intake.heavy_check({"run": run}) is heavy


def test_intake_drift_a_heavy_check_never_runs_and_is_counted(world):
    marker = world.root / "ran.txt"
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"],
               checks=[{"run": ["python3", "-c", f"open({str(marker)!r}, 'w').close()"]},
                       {"run": ["python3", "_tools/tests.py"]}])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"], checks=[{"run": ["python3", "_tools/stress_test.py"]}])
    world.item(1, "TK-cccccccc", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    d = bl_intake.scan_drift(world.root)
    assert d.heavy == ["TK-aaaaaaaa", "TK-bbbbbbbb"] and d.passing == {"TK-cccccccc": 1} and d.ran == 1
    assert not marker.exists()  # no check of a heavy item ran, not even its light one


def test_intake_drift_a_check_sleeping_past_the_budget_stops_the_scan_and_the_rest_are_counted(world):
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[SLOW_CHECK])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.item(1, "TK-cccccccc", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    t = time.monotonic()
    d = bl_intake.scan_drift(world.root, timeout=30, budget=1)
    assert time.monotonic() - t < 20  # the budget, not the check's own timeout, cut the sleep
    assert d.timed_out == ["TK-aaaaaaaa"] and d.over_budget == ["TK-bbbbbbbb", "TK-cccccccc"]
    assert d.passing == {} and d.ran == 1


def test_intake_drift_finished_checks_report_the_same_set_on_every_run(world):
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"], checks=[FAIL_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    first, second = bl_intake.scan_drift(world.root), bl_intake.scan_drift(world.root)
    assert first == second and first.passing == {"TK-aaaaaaaa": 1} and first.over_budget == []


def test_intake_drift_skipped_items_are_counted_in_the_story(world, monkeypatch):
    monkeypatch.setattr(bl_intake, "DRIFT_BUDGET_S", 3)
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.item(1, "TK-bbbbbbbb", "todo", touches=["src/**"], checks=[{"run": ["python3", "_tools/tests.py"]}])
    world.item(1, "TK-cccccccc", "todo", touches=["src/**"], checks=[SLOW_CHECK])
    world.item(1, "TK-dddddddd", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    (c,), _ = drift_candidates(world)
    assert c.key == "TK-aaaaaaaa"
    assert "1 item(s) had a check that runs the whole test suite or the stress tests" in c.notes
    assert "1 item(s) had a check that exceeded" in c.notes
    assert "1 item(s) were not checked: the 3 s budget for checks was spent" in c.notes


def test_intake_drift_nothing_drifted_reports_no_candidate(world):
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[FAIL_CHECK])
    world.item(1, "TK-bbbbbbbb", "doing", touches=["src/**"])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    world.publish()
    assert drift_candidates(world) == ([], [])


def test_intake_drift_status_is_the_story_check_and_passes_once_the_item_is_done(world, capsys):
    world.item(1, "TK-aaaaaaaa", "todo", touches=["src/**"], checks=[PASS_CHECK])
    world.commit(2, "feat: work", {"src/a.txt": "b\n"})
    bl_intake.detector("drift")(bl_intake.drift_detector)
    code, out, _ = intake(world.root, capsys, "--file")
    assert code == 0 and out[-1] == "intake: 1 candidate(s), 1 new filed, 0 skipped"
    (story_item,) = [it for it in load(world.root) if it["kind"] == "story"]
    argv = story_item["checks"][0]["run"]
    assert intake(world.root, capsys, *argv[3:])[0] == 1  # still reported
    it = next(i for i in load(world.root) if i["id"] == "TK-aaaaaaaa")
    backlog.Backlog(world.root).save({**it, "status": "done"})
    world.commit(3, "chore(backlog): done")
    assert intake(world.root, capsys, *argv[3:])[0] == 0  # the item is done: no longer reported


# ------------------------------------------------------------------ the trailer detector (intake_trailers)
#
# Same throwaway repositories as the drift tests. Planted: a KB-Work line before a blank line and Co-Authored-By (git
# reads no trailer: reported) beside a correct trailer (not reported); a commit changing each of `_tools/`, `.claude/`,
# `.githooks/` and `.gitlab-ci.yml` without KB-Work (reported) beside one with a KB-Work trailer, one with a KB-Auto
# trailer and one changing only content (not reported); a commit older than the window (not reported).

CO = "Co-Authored-By: Claude <noreply@example.com>"
BAD_MSG = f"fix: work\n\nKB-Work: TK-aaaaaaaa\n\n{CO}"  # a blank line before Co-Authored-By: no trailer
GOOD_MSG = f"fix: work\n\nKB-Work: TK-aaaaaaaa\n{CO}"


def trailer_candidates(world):
    bl_intake.detector("trailers")(bl_intake.trailers_detector)
    return bl_intake.collect(world.root)


def test_intake_trailers_window_is_a_week():
    assert bl_intake.TRAILER_WINDOW_DAYS == 7


def test_intake_trailers_kb_work_before_a_blank_line_and_coauthored_by_is_reported(world):
    sha = world.commit(1, BAD_MSG, {"kb/x.md": "x\n"})
    world.publish()
    assert bl_intake.trailer_findings(world.root) == [(sha[:10], "stray")]


def test_intake_trailers_a_correct_trailer_is_not_reported(world):
    world.commit(1, GOOD_MSG, {"_tools/x.py": "x = 1\n"})
    world.publish()
    assert bl_intake.trailer_findings(world.root) == []


def test_intake_trailers_a_stray_line_beside_a_real_trailer_is_reported(world):
    sha = world.commit(1, f"fix: work\n\nKB-Work: TK-aaaaaaaa\n\nmore text\n\nKB-Work: TK-bbbbbbbb\n{CO}")
    world.publish()
    assert bl_intake.trailer_findings(world.root) == [(sha[:10], "stray")]


def test_intake_trailers_a_tools_commit_without_kb_work_is_reported(world):
    sha = world.commit(1, "fix: tool", {"_tools/x.py": "x = 1\n"})
    world.publish()
    assert bl_intake.trailer_findings(world.root) == [(sha[:10], "missing")]


@pytest.mark.parametrize("path", ["_tools/sub/x.py", ".claude/skills/x.md", ".githooks/pre-push", ".gitlab-ci.yml"])
def test_intake_trailers_each_code_path_needs_a_trailer(world, path):
    sha = world.commit(1, "fix: change", {path: "x\n"})
    world.publish()
    assert bl_intake.trailer_findings(world.root) == [(sha[:10], "missing")]


@pytest.mark.parametrize("path", ["kb/x.md", "src/a.txt", "_toolsx/a.py", "docs/_tools/a.py", ".gitlab-ci.yml.bak"])
def test_intake_trailers_other_paths_need_no_trailer(world, path):
    world.commit(1, "docs: change", {path: "x\n"})
    world.publish()
    assert bl_intake.trailer_findings(world.root) == []


def test_intake_trailers_a_kb_auto_commit_is_not_reported(world):
    world.commit(1, "chore: auto\n\nKB-Auto: eval", {"_tools/x.py": "x = 1\n"})
    world.publish()
    assert bl_intake.trailer_findings(world.root) == []


def test_intake_trailers_a_commit_with_one_trailer_among_many_files_is_not_reported(world):
    world.commit(1, GOOD_MSG, {"_tools/x.py": "x\n", ".githooks/h": "x\n", "kb/y.md": "y\n"})
    world.publish()
    assert bl_intake.trailer_findings(world.root) == []


def test_intake_trailers_the_window_is_measured_from_the_tip_of_main(world):
    old = world.commit(24, "fix: old", {"_tools/x.py": "1\n"})
    edge = world.commit(25, "fix: edge", {"_tools/x.py": "2\n"})
    world.commit(25 + 7 * 24, "fix: tip", {"src/a.txt": "t\n"})
    world.publish()
    found = bl_intake.trailer_findings(world.root)
    assert found == [(edge[:10], "missing")] and old[:10] not in dict(found)  # exactly 7 days older: in; older: out


def test_intake_trailers_a_commit_not_on_main_is_not_read(world):
    world.commit(1, "fix: ok", {"src/a.txt": "b\n"})
    world.publish()
    world.commit(2, "fix: local", {"_tools/x.py": "x\n"})
    assert bl_intake.trailer_findings(world.root) == []


def test_intake_trailers_without_origin_main_nothing_is_reported(world):
    world.commit(1, "fix: tool", {"_tools/x.py": "x\n"})
    assert bl_intake.trailer_findings(world.root) == []


def test_intake_trailers_one_bug_lists_the_commits_and_its_fingerprint_is_the_sorted_short_shas(world):
    a = world.commit(1, BAD_MSG, {"kb/x.md": "x\n"})
    b = world.commit(2, "fix: tool", {"_tools/x.py": "x\n"})
    world.commit(3, GOOD_MSG, {"_tools/y.py": "y\n"})
    world.publish()
    (c,), failures = trailer_candidates(world)
    assert failures == []
    key = ",".join(sorted([a[:10], b[:10]]))
    assert c.kind == "bug" and c.detector == "trailers" and c.key == key
    assert c.fp == bl_intake.fingerprint("trailers", key)
    assert a[:10] in c.notes and b[:10] in c.notes and "2 commit(s)" in c.title


def test_intake_trailers_the_fingerprint_is_stable_and_changes_with_the_set(world):
    world.commit(1, BAD_MSG, {"kb/x.md": "x\n"})
    world.publish()
    first = trailer_candidates(world)[0][0].fp
    assert trailer_candidates(world)[0][0].fp == first
    world.commit(2, "fix: tool", {"_tools/x.py": "x\n"})
    world.publish()
    assert trailer_candidates(world)[0][0].fp != first


def test_intake_trailers_clean_history_reports_no_candidate(world):
    world.commit(1, GOOD_MSG, {"_tools/x.py": "x\n"})
    world.commit(2, "docs: note", {"kb/x.md": "x\n"})
    world.publish()
    assert trailer_candidates(world) == ([], [])


def test_intake_trailers_status_is_the_bug_repro_and_passes_once_the_commit_leaves_the_window(world, capsys):
    world.commit(1, "fix: tool", {"_tools/x.py": "x\n"})
    world.publish()
    bl_intake.detector("trailers")(bl_intake.trailers_detector)
    code, out, _ = intake(world.root, capsys, "--file")
    assert code == 0 and out[-1] == "intake: 1 candidate(s), 1 new filed, 0 skipped"
    (bug_item,) = [it for it in load(world.root) if it["kind"] == "bug"]
    argv = bug_item["repro"]["run"]
    assert intake(world.root, capsys, *argv[3:])[0] == 1  # still reported
    world.commit(1 + 8 * 24, "docs: later", {"kb/x.md": "x\n"})
    world.publish()
    assert intake(world.root, capsys, *argv[3:])[0] == 0  # the commit is older than the window

