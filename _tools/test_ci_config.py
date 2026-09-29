"""CI configuration tests: `python3 _tools/tests.py -k TestCiAllManual`.

  TestCiAllManual  .gitlab-ci.yml, read as text (no YAML library): every job's every rule is `when: manual` with
                   `allow_failure: true`, so no push or merge request waits on a pipeline. Planted failures: a rule that
                   starts a job on its own, a rule that lets a manual job block the pipeline, and a job with no rule
                   each make the check report.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CI = HERE.parent / ".gitlab-ci.yml"
JOBS = ("kb-tests", "kb-tests-floor", "kb-tests-windows", "tool-stress", "kb-trailers")
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
