"""The heavy suites run once, at the sprint's review story, not at every landing (bl_land.py, bl_base.py, backlog.py).

  land_runs_no_stress_before_sprint_end   a landing that changes `_tools/` runs the steps stale, rag.py eval, lint and
                                          sync, and no stress_test.py step, whatever the number of `_tools/` files it
                                          changes; `bl_land.LAND_HEAVY` names the lookup eval and the lint only.
                                          Planted: the old list, with the stress step first, makes the same landing log
                                          a stress_test.py step, and the checks below see it
  review_checks_run_stress_once           a review story made by `new sprint` has the checks backlog check, the full
                                          tests.py and stress_test.py, in that order, each exactly once, however many
                                          sprints are made; `bl_base.REVIEW_CHECKS` says the same. Planted: a list with
                                          the stress check twice or missing is counted wrong

The landing fixture is test_bl_land.py's (a throwaway clone with a bare remote and stub steps: its stress_test.py stub
logs its name, so a landing that ran it shows in the log).
"""
import pytest

import backlog
import bl_base
import bl_land
import bl_testkit
import test_bl_land
from bl_testkit import b, item

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

STRESS = "stress_test.py"
OLD_HEAVY = ((STRESS, ["_tools/stress_test.py"]), *bl_land.LAND_HEAVY)  # planted: the list before the three tiers


def heavy_names(heavy):
    return [step for step, _ in heavy]


def stress_steps(steps):
    return [s for s in steps if STRESS in s]


REVIEW_ORDER = [["python3", "_tools/backlog.py", "check"], ["python3", "_tools/tests.py"],
                ["python3", "_tools/stress_test.py"]]


def review_runs(checks):
    return [c["run"] for c in checks]


def review_checks_ok(checks):
    """Backlog check, then the full tests.py, then stress_test.py: each once, none else."""
    return review_runs(checks) == REVIEW_ORDER


class TestLandRunsNoStress:
    CO = test_bl_land.TestBacklogLand.CO
    out = staticmethod(test_bl_land.TestBacklogLand.out)
    landing = test_bl_land.TestBacklogLand.landing
    work = test_bl_land.TestBacklogLand.work
    land = test_bl_land.TestBacklogLand.land
    steps = staticmethod(test_bl_land.TestBacklogLand.steps)

    def test_land_runs_no_stress_before_sprint_end_list_names_eval_and_lint(self):
        assert heavy_names(bl_land.LAND_HEAVY) == ["rag.py eval", "lint"]
        assert not stress_steps(heavy_names(bl_land.LAND_HEAVY))
        assert stress_steps(heavy_names(OLD_HEAVY)) == [STRESS]  # planted: the old list is told apart

    @pytest.mark.parametrize("files", [["_tools/b.py"], ["_tools/b.py", "_tools/b2.py"],
                                       ["_tools/b.py", "_tools/b2.py", "_tools/b3.py", "_tools/b4.py"]])
    def test_land_runs_no_stress_before_sprint_end_for_a_tools_landing(self, landing, files):
        ld = landing
        repo, tk = ld["repo"], ld["tk"]
        bl_testkit.edit(repo, tk, touches=["src/**", "_tools/**"], checks=[{"run": bl_testkit.is_file("src/b.txt")}])
        for rel in [*files, "src/b.txt"]:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("b\n", encoding="utf-8")
        bl_testkit.commit(repo, "work", tk)
        code, out = self.land(ld)
        assert code == 0, out
        steps = self.steps(ld)
        assert steps == ["stale", "rag.py eval", "lint", "sync"], out
        assert not stress_steps(steps), out

    def test_land_runs_no_stress_before_sprint_end_planted_old_list_runs_it(self, landing, monkeypatch, capsys):
        """Planted: land with the old list, in this process, logs a stress_test.py step, which the test above refuses."""
        ld = landing
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        monkeypatch.setattr(bl_land, "LAND_HEAVY", OLD_HEAVY)
        code = backlog.main(["--root", str(ld["repo"]), "land", ld["tk"], "--trailer", self.CO])
        out = capsys.readouterr().out
        assert code == 0, out
        assert self.steps(ld) == ["stale", STRESS, "rag.py eval", "lint", "sync"], out
        assert stress_steps(self.steps(ld))

    def test_land_runs_no_stress_before_sprint_end_content_landing_has_no_heavy_step(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        code, out = self.land(ld)
        assert code == 0 and self.steps(ld) == ["sync"], out


class TestReviewChecksRunStressOnce:
    def made(self, repo, title):
        assert b(repo, "new", "sprint", "--title", title, "--goal", "ship")[0] == 0
        return item(repo, f"Review sprint: {title}")

    def test_review_checks_run_stress_once_base_constant(self):
        assert review_checks_ok(bl_base.REVIEW_CHECKS)
        assert review_runs(bl_base.REVIEW_CHECKS).count(["python3", "_tools/stress_test.py"]) == 1

    def test_review_checks_run_stress_once_in_each_new_sprints_review_story(self, repo):
        for n in range(3):  # each sprint's story carries each check once, whatever the number of sprints before it
            rv = self.made(repo, f"Sprint {n}")
            assert rv.get("review") is True
            assert review_checks_ok(rv["checks"]), rv["checks"]

    def test_review_checks_run_stress_once_planted_counts_are_told_apart(self):
        assert not review_checks_ok(bl_base.REVIEW_CHECKS[:2])  # stress missing
        assert not review_checks_ok([*bl_base.REVIEW_CHECKS, bl_base.REVIEW_CHECKS[2]])  # stress twice
        assert not review_checks_ok([bl_base.REVIEW_CHECKS[1], bl_base.REVIEW_CHECKS[0], bl_base.REVIEW_CHECKS[2]])
        assert not review_checks_ok([bl_base.REVIEW_CHECKS[0], bl_base.REVIEW_CHECKS[2], bl_base.REVIEW_CHECKS[1]])

    def test_review_checks_run_stress_once_an_existing_review_story_is_not_rewritten(self, repo):
        """A story already in the backlog keeps the checks it was written with: nothing rewrites it on a later `new`."""
        rv = self.made(repo, "Old")
        bl_testkit.edit(repo, rv["id"], checks=[{"run": ["python3", "_tools/backlog.py", "check"]}])
        self.made(repo, "Newer")
        old = item(repo, "Review sprint: Old")
        assert review_runs(old["checks"]) == [["python3", "_tools/backlog.py", "check"]]
