---
name: kb-verify
description: Quality gate for it-ops-kb before a commit or a push. Runs the repository checks, the stress tests, the lookup eval, the doc2query stale check and extra contract checks (coverage vs front matter, untagged facts, topic ids), and reports findings without changing anything.
disable-model-invocation: true
argument-hint: "[path prefixes to limit the contract checks, e.g. auth dsc/what-if] [--base REV]"
---

# Verify it-ops-kb

Report only: change no file, even to fix a finding.

Read `MAINTAINING.md` first: the content rules, tools, git workflow and commit rules this skill relies on (`AGENTS.md` covers lookups only).

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Run
1. `python3 _tools/check.py`: sources, citations, artifacts, front matter, CSV shape.
   Also `python3 _tools/build_index.py --check`: the generated index files are up to date.
2. `python3 _tools/fetch.py --offline`: pinned artifacts match their sha256.
3. `python3 _tools/stress_test.py`: tool robustness, about 35 s.
4. `python3 .claude/skills/kb-verify/lint.py <path prefixes>` (the prefixes from the arguments; the base option is for step 6 only): contract checks that `check.py` does not make:
   - ERROR: topic id vs path; the topic's `_coverage.csv` or README row missing or stale (generated: the fix is `python3 _tools/build_index.py`); coverage lists a missing file (fix `files:`); missing section; tag without a source id; untagged Facts bullet.
   - WARN: no `#` title; a bullet mixing tag kinds; header sources never cited, or cited ids missing from the header.
5. `python3 _tools/tests.py`: what CI runs, about 20 s. Lint errors listed in `_tools/lint_baseline.txt` are known debt; only new ones fail. It also checks the `signals.csv` and `aliases.csv` tables (every signal names an existing topic, no duplicate keys), `expansions.csv`, the lookup eval, and both plugins (`claude plugin validate` when the CLI is installed).
   - `python3 _tools/rag.py eval`: the lookup eval set on its own; a failing question names the expected article and the verdict it got.
   - `python3 _tools/doc2query.py stale`: `stale=0`, else the listed expansion keys belong to reworded or removed facts (exit 1; `python3 _tools/doc2query.py prune` removes their rows).
   - `python3 _tools/rag.py audit --unlinked`: ledger entries with no topic link. Older ones are known debt (`work-left.md`); an entry this work added must end with `(topic: <domain>/<slug>)`.
6. Find the files this work changed, against the commit it started from, not against `main` (a branch made from another branch, or a `main` that moved on, would otherwise show other people's changes as yours):
   - base: the `--base REV` argument if given (the user knows the start, e.g. `--base chore/kb-tools-hardening`); else, when the branch tracks a different branch (`git rev-parse --abbrev-ref @{upstream}` is not `origin/<this branch>`), `git merge-base HEAD @{upstream}`; else `git merge-base HEAD origin/main`. Say which rule picked it; if none applies (no upstream, no `origin/main`), ask.
   - changed: `git diff --name-only <base>` (committed and uncommitted together), plus untracked files from `git status --short`.
   - Run the lint on the changed topic paths too, and name the base and the files in the report.

## 2. Report
- One line per step: PASS/FAIL and the summary line.
- Findings grouped by file, errors first. Separate findings in the files step 6 found changed since the base from the existing ones: the new ones block a push; lint errors already in `_tools/lint_baseline.txt` are known debt.
- For each finding in a changed file, say what to change, but do not change it.
