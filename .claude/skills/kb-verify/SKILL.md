---
name: kb-verify
description: Quality gate for it-ops-kb before a commit or merge request. Runs the repository checks, the stress tests and extra contract checks (coverage vs front matter, untagged facts, topic ids), and reports findings without changing anything.
disable-model-invocation: true
argument-hint: "[path prefixes to limit the contract checks, e.g. auth dsc/what-if]"
---

# Verify it-ops-kb

Report only: change no file, even to fix a finding.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Run
1. `python3 _tools/check.py`: sources, citations, artifacts, front matter, CSV shape.
2. `python3 _tools/fetch.py --offline`: pinned artifacts match their sha256.
3. `python3 _tools/stress_test.py`: tool robustness, about 10 s.
4. `python3 .claude/skills/kb-verify/lint.py $ARGUMENTS`: contract checks that `check.py` does not make:
   - ERROR: topic id vs path; header vs `_coverage.csv` (status, priority, source count); coverage lists a missing file; topic missing from `_coverage.csv` or the README table; missing section; tag without a source id; untagged Facts bullet.
   - WARN: no `#` title; a bullet mixing tag kinds; header sources never cited, or cited ids missing from the header.
5. `python3 _tools/tests.py`: what CI runs. Lint errors listed in `_tools/lint_baseline.txt` are known debt; only new ones fail.
6. If the working tree has changes (`git status --short`), run the lint on the changed topic paths too, and name them in the report.

## 2. Report
- One line per step: PASS/FAIL and the summary line.
- Findings grouped by file, errors first. Separate findings in files changed on this branch (`git diff --name-only main...HEAD` plus uncommitted) from the existing ones: the new ones block a merge; lint errors already in `_tools/lint_baseline.txt` are known debt.
- For each finding in a changed file, say what to change, but do not change it.
