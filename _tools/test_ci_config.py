"""CI configuration tests: `python3 _tools/tests.py -k TestCiAllManual`.

  TestCiAllManual  .gitlab-ci.yml, read as text (no YAML library): every job's every rule is `when: manual` with
                   `allow_failure: true`, so no push or merge request waits on a pipeline. Planted failures: a rule that
                   starts a job on its own, a rule that lets a manual job block the pipeline, and a job with no rule
                   each make the check report.
  TestCheckLanesCiJob  both forges' configs carry a `check-lanes` job that runs `kbgit.py check-lanes`, only by hand
                   (manual / workflow_dispatch), on the full history; the GitHub one has no secret and publishes
                   nothing. Planted: a config without the job, one that starts it on its own and one with a shallow
                   clone each fail the check.
  TestTimeoutFactor  kb-tests-windows sets KB_TEST_TIMEOUT_FACTOR (conftest.timeout_s scales the subprocess timeouts
                   that ran out in that job); planted: a factor below 1 or not a number is refused and stops the run.
"""
import os, re, subprocess, sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CI = HERE.parent / ".gitlab-ci.yml"
JOBS = ("kb-tests", "kb-tests-floor", "kb-tests-windows", "tool-stress", "kb-trailers", "check-lanes")
NOT_JOBS = {"workflow", "default", "variables", "cache", "stages", "include"}


def jobs(text):
    """{job name: [rule dicts]} of a .gitlab-ci.yml text: top-level keys other than the global ones, and under each
    the list items of its `rules:` with their scalar keys (if, when, allow_failure)."""
    out, name, in_rules, rule = {}, None, False, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z0-9_.-]+):", line)
        if top:
            name = top.group(1) if top.group(1) not in NOT_JOBS else None
            in_rules, rule = False, None
            if name:
                out[name] = []
            continue
        if name is None:
            continue
        if re.match(r"^  \S", line):
            in_rules = line.strip() == "rules:"
            continue
        if not in_rules:
            continue
        item = re.match(r"^    - (.*)$", line)
        if item:
            rule = {}
            out[name].append(rule)
            line = "      " + item.group(1)
        kv = re.match(r"^      ([a-z_]+):\s*(.*)$", line)
        if kv and rule is not None:
            rule[kv.group(1)] = kv.group(2).strip()
    return out


def problems(text):
    """What is wrong with the rules of a .gitlab-ci.yml text; [] when every job's every rule is manual and optional."""
    bad = []
    for job, rules in jobs(text).items():
        if not rules:
            bad.append(f"{job}: no rules")
        for r in rules:
            if r.get("when") != "manual":
                bad.append(f"{job}: a rule that is not when: manual")
            if r.get("allow_failure") != "true":
                bad.append(f"{job}: a rule without allow_failure: true")
    return bad


class TestCiAllManual:
    def text(self):
        return CI.read_text(encoding="utf-8")

    def test_every_job_is_manual_and_optional(self):
        assert problems(self.text()) == []

    def test_parser_reads_every_job(self):
        found = jobs(self.text())
        for job in JOBS:
            assert found.get(job), job

    def test_a_rule_that_starts_a_job_on_its_own_is_reported(self):
        text = self.text()
        planted = text.replace("    - when: manual\n      allow_failure: true", "    - when: on_success\n"
                               "      allow_failure: true", 1)
        assert planted != text
        assert any("not when: manual" in p for p in problems(planted))

    def test_a_manual_rule_that_may_block_the_pipeline_is_reported(self):
        text = self.text()
        planted = text.replace("      when: manual\n      allow_failure: true", "      when: manual\n"
                               "      allow_failure: false", 1)
        assert planted != text
        assert any("without allow_failure: true" in p for p in problems(planted))

    def test_a_job_with_no_rules_is_reported(self):
        planted = self.text() + "\nextra-job:\n  stage: test\n  script:\n    - true\n"
        assert any("extra-job: no rules" in p for p in problems(planted))


GH = HERE.parent / ".github" / "workflows" / "kb.yml"


def gitlab_lanes_problems(text):
    """What is wrong with the `check-lanes` job of a .gitlab-ci.yml text; [] when it is there, manual, optional, full."""
    rules = jobs(text).get("check-lanes")
    if rules is None:
        return ["check-lanes: no job"]
    bad = [f"check-lanes: {p.split(': ', 1)[1]}" for p in problems(text) if p.startswith("check-lanes:")]
    if job_variables(text, "check-lanes").get("GIT_DEPTH") != "0":
        bad.append("check-lanes: not the full history (GIT_DEPTH 0)")
    if not re.search(r"^\s+- python3 _tools/kbgit\.py check-lanes\b", text, re.M):
        bad.append("check-lanes: does not run kbgit.py check-lanes")
    return bad


def github_job(text, name):
    """The lines of a workflow job's block (from `  name:` to the next job or the end)."""
    m = re.search(rf"^  {re.escape(name)}:\n((?:(?:   .*)?\n)*)", text + "\n", re.M)
    return m.group(1).rstrip("\n") + "\n" if m else None


def github_lanes_problems(text):
    """What is wrong with the `check-lanes` job of a workflow text; [] when it is there, dispatch-only, full, secret-free."""
    block = github_job(text, "check-lanes")
    if block is None:
        return ["check-lanes: no job"]
    bad = []
    if "if: github.event_name == 'workflow_dispatch'" not in block:
        bad.append("check-lanes: not limited to workflow_dispatch")
    if "fetch-depth: 0" not in block:
        bad.append("check-lanes: not the full history (fetch-depth 0)")
    if "kbgit.py check-lanes" not in block:
        bad.append("check-lanes: does not run kbgit.py check-lanes")
    if "secrets." in block or "write" in block:
        bad.append("check-lanes: a secret or a write permission")
    return bad


class TestCheckLanesCiJob:
    def gl(self):
        return CI.read_text(encoding="utf-8")

    def gh(self):
        return GH.read_text(encoding="utf-8")

    def test_check_lanes_ci_job_gitlab(self):
        assert gitlab_lanes_problems(self.gl()) == []

    def test_check_lanes_ci_job_github(self):
        text = self.gh()
        assert github_lanes_problems(text) == []
        assert re.search(r"^  workflow_dispatch:", text, re.M)

    def test_check_lanes_ci_job_a_config_without_the_job_fails(self):
        """Planted: each forge's config with the job cut out reports it missing."""
        gl = self.gl()
        assert "check-lanes:" in gl
        assert gitlab_lanes_problems(gl.split("\ncheck-lanes:", 1)[0] + "\n") == ["check-lanes: no job"]
        gh = self.gh()
        assert github_lanes_problems(gh.replace("  check-lanes:\n", "  other-job:\n", 1)) == ["check-lanes: no job"]

    def test_check_lanes_ci_job_planted_starts_on_its_own_or_shallow(self):
        gl = self.gl()
        head, job = gl.split("\ncheck-lanes:", 1)
        planted = head + "\ncheck-lanes:" + job.replace("when: manual", "when: on_success", 1)
        assert any("not when: manual" in p for p in gitlab_lanes_problems(planted))
        planted = head + "\ncheck-lanes:" + job.replace('GIT_DEPTH: "0"', 'GIT_DEPTH: "5"', 1)
        assert any("full history" in p for p in gitlab_lanes_problems(planted))
        gh = self.gh()
        planted = gh.replace("if: github.event_name == 'workflow_dispatch'", "if: github.event_name == 'push'", 1)
        assert any("workflow_dispatch" in p for p in github_lanes_problems(planted))
        block = github_job(gh, "check-lanes")
        planted = gh.replace(block, block.replace("fetch-depth: 0", "fetch-depth: 1"), 1)
        assert any("full history" in p for p in github_lanes_problems(planted))
        planted = gh.replace(block, block + "          T: ${{ secrets.TOKEN }}\n", 1)
        assert any("secret" in p for p in github_lanes_problems(planted))


def job_variables(text, job):
    """{name: value} of a job's `variables:` block in a .gitlab-ci.yml text (scalar values, quotes removed)."""
    out, in_job, in_vars = {}, False, False
    for line in text.splitlines():
        if re.match(r"^[A-Za-z0-9_.-]+:", line):
            in_job, in_vars = line.startswith(job + ":"), False
            continue
        if not in_job or not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^  \S", line):
            in_vars = line.strip() == "variables:"
            continue
        kv = re.match(r"^    ([A-Z0-9_]+):\s*(.*)$", line)
        if in_vars and kv:
            out[kv.group(1)] = kv.group(2).strip().strip("\"'")
    return out


class TestTimeoutFactor:
    """KB_TEST_TIMEOUT_FACTOR scales the subprocess timeouts of the tests that ran out in kb-tests-windows
    (conftest.timeout_s); the Windows job sets it, and a value that would shorten a timeout stops the run."""

    def test_timeout_factor_the_windows_job_sets_it(self):
        from conftest import TIMEOUT_FACTOR_VAR, timeout_factor
        text = CI.read_text(encoding="utf-8")
        found = job_variables(text, "kb-tests-windows")
        assert timeout_factor({TIMEOUT_FACTOR_VAR: found.get(TIMEOUT_FACTOR_VAR, "")}) >= 3, found
        assert found.get("GIT_DEPTH") == "0", "the parser reads the job's variables"
        # the Linux jobs run at this host's speed and set none
        assert TIMEOUT_FACTOR_VAR not in job_variables(text, "kb-tests")

    def test_timeout_factor_scales_and_refuses_what_would_shorten(self, monkeypatch):
        from conftest import TIMEOUT_FACTOR_VAR, timeout_factor, timeout_s
        monkeypatch.delenv(TIMEOUT_FACTOR_VAR, raising=False)
        assert timeout_s(60) == 60
        monkeypatch.setenv(TIMEOUT_FACTOR_VAR, "2.5")
        assert timeout_s(60) == 150
        for bad in ("0.5", "0", "-3", "fast", "nan", "inf"):  # planted: each would shorten or break a timeout
            with pytest.raises(ValueError, match=TIMEOUT_FACTOR_VAR):
                timeout_factor({TIMEOUT_FACTOR_VAR: bad})

    def test_timeout_factor_a_bad_value_stops_the_run(self):
        """Planted: pytest started with a factor below 1 stops with the variable's message before any test runs."""
        env = {**os.environ, "KB_TEST_TIMEOUT_FACTOR": "0.1"}
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
                            str(HERE / "test_ci_config.py"), "-k", "test_parser_reads_every_job"],
                           capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(HERE.parent), timeout=120)
        assert p.returncode != 0 and "KB_TEST_TIMEOUT_FACTOR='0.1'" in p.stdout + p.stderr, p.stdout + p.stderr
