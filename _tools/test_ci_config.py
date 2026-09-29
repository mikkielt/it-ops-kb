"""CI configuration tests: `python3 _tools/tests.py -k TestCiCodeBranch`.

  TestCiCodeBranch  .gitlab-ci.yml, read as text (no YAML library): the gate jobs kb-tests and kb-trailers have as
                    their first rule one on code/* branches (`$CI_COMMIT_BRANCH =~ /^code\\//`) that starts them without
                    a click and with `allow_failure: false`, so a failed gate fails a code/<id> branch pipeline and
                    auto-merge does not merge it; their later rules, and every other job, keep `allow_failure: true`
                    and never name code/*. Planted failures: the code rule moved after the catch-all rule, the code
                    rule with `allow_failure: true`, and a code rule on another job each make the check report.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CI = HERE.parent / ".gitlab-ci.yml"
GATE_JOBS = ("kb-tests", "kb-trailers")
CODE_IF = re.compile(r"\$CI_COMMIT_BRANCH =~ /\^code\\//")
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
    """What is wrong with the code/* rules of a .gitlab-ci.yml text; [] when nothing."""
    found = jobs(text)
    bad = []
    for job in GATE_JOBS:
        rules = found.get(job)
        if not rules:
            bad.append(f"{job}: no rules")
            continue
        first = rules[0]
        if not CODE_IF.search(first.get("if", "")):
            bad.append(f"{job}: the first rule is not the code/* branch rule")
        elif first.get("when") != "on_success" or first.get("allow_failure") != "false":
            bad.append(f"{job}: the code/* rule is not when: on_success with allow_failure: false")
        for r in rules[1:]:
            if CODE_IF.search(r.get("if", "")):
                bad.append(f"{job}: a second code/* rule")
            if r.get("allow_failure") != "true":
                bad.append(f"{job}: a rule after the code/* one without allow_failure: true")
    for job, rules in found.items():
        if job in GATE_JOBS:
            continue
        for r in rules:
            if CODE_IF.search(r.get("if", "")):
                bad.append(f"{job}: a code/* rule on a job that is not a gate job")
            if r.get("allow_failure") not in (None, "true"):
                bad.append(f"{job}: allow_failure is not true")
    return bad


class TestCiCodeBranch:
    def text(self):
        return CI.read_text(encoding="utf-8")

    def test_gate_jobs_block_on_code_branches(self):
        assert problems(self.text()) == []

    def test_parser_reads_every_job(self):
        found = jobs(self.text())
        for job in ("kb-tests", "kb-tests-floor", "kb-tests-windows", "tool-stress", "kb-trailers"):
            assert found.get(job), job

    def test_code_rule_after_catch_all_is_reported(self):
        text = self.text()
        code_rule = ("    - if: $CI_COMMIT_BRANCH =~ /^code\\//\n      when: on_success\n      allow_failure: false\n")
        assert code_rule in text
        catch_all = "    - when: on_success\n      allow_failure: true\n"
        planted = text.replace(code_rule + catch_all, catch_all + code_rule, 1)
        assert planted != text
        assert any("kb-tests: the first rule" in p for p in problems(planted))

    def test_code_rule_that_may_fail_is_reported(self):
        text = self.text()
        planted = text.replace("=~ /^code\\//\n      when: on_success\n      allow_failure: false",
                               "=~ /^code\\//\n      when: on_success\n      allow_failure: true")
        assert planted != text
        assert any("allow_failure: false" in p for p in problems(planted))

    def test_code_rule_on_another_job_is_reported(self):
        text = self.text()
        planted = text.replace("  rules:\n    - when: manual",
                               "  rules:\n    - if: $CI_COMMIT_BRANCH =~ /^code\\//\n      when: on_success\n"
                               "    - when: manual", 1)
        assert planted != text
        assert any("not a gate job" in p for p in problems(planted))
