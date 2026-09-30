#!/usr/bin/env python3
"""Run the kb's tests with pytest and pytest-xdist (pyproject.toml's dev group, installed by uv). Exit 0 when they pass.

  tests.py                         every test module in _tools/ but the stress suite, in parallel
  tests.py -k Leak                 only tests whose name matches (pytest -k); other pytest arguments pass through
  tests.py --changed [REV]         only the test files a change from REV's merge base (default HEAD: the working tree)
                                   can break, from testmap.py's map; none when no test can be affected
  tests.py --write-lint-baseline   record today's lint errors as known debt in _tools/lint_baseline.txt
  KB_TESTS_FAST=1 tests.py         leave out the git scenarios (-m "not git"): kbgit.py sync's gate
  stress_test.py                   the stress suite (test_stress.py)

Modules: test_kb_cohesion.py, test_kb_lookup.py, test_kb_ids.py, test_kb_leaks.py, test_merge.py, test_history.py, test_sync.py, test_census.py,
test_kb_mcp.py, test_research_merge.py, test_agent_bench.py, test_portability.py, test_redact.py, test_ql_capture.py,
test_ql_distill.py, test_ql_store.py, test_ql_learn.py, test_ql_deliver.py, test_ql_research.py, test_ql_report.py,
test_querylog_e2e.py, test_backlog.py, test_stress.py; shared fixtures and helpers in conftest.py, and the query log
tests' in ql_testkit.py.
pytest is run as `uv run --frozen python -m pytest` (uv creates .venv from uv.lock on first use), or with this Python
when uv is missing but pytest and pytest-xdist are importable; otherwise exit 2 with how to install them. The tools
under test stay stdlib-only.
"""
import os, shutil, subprocess, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
XDIST = ["-n", "auto"]  # dist loadscope: a class's scenario is built once, on one worker (stress_test.py: load)


def pytest_cmd():
    """The command that runs pytest, or None."""
    if shutil.which("uv"):
        return ["uv", "run", "--quiet", "--frozen", "--project", KB, "python", "-m", "pytest"]
    try:
        import pytest, xdist  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "pytest"]


def run_pytest(args, env=None, dist="loadscope"):
    cmd = pytest_cmd()
    if cmd is None:
        print("pytest and pytest-xdist are needed: install uv (https://docs.astral.sh/uv/) and rerun, or "
              "`pip install pytest pytest-xdist`", file=sys.stderr)
        return 2
    return subprocess.run(cmd + XDIST + ["--dist", dist] + args, cwd=KB, env={**os.environ, **(env or {})}).returncode


def write_lint_baseline():
    lint = os.path.join(KB, ".claude", "skills", "kb-verify", "lint.py")
    out = subprocess.run([sys.executable, lint], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
    errs = sorted({ln.strip() for ln in (out.stdout + out.stderr).splitlines() if ln.startswith("ERROR")})
    with open(os.path.join(TOOLS, "lint_baseline.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(e + "\n" for e in errs))
    print(f"wrote {len(errs)} known lint errors to _tools/lint_baseline.txt")
    return 0


def main(argv):
    if "--write-lint-baseline" in argv:
        return write_lint_baseline()
    args = list(argv)
    targets = [TOOLS]
    if "--changed" in args:  # only the tests the change can break (testmap.py)
        i = args.index("--changed")
        rev = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("-") else None
        del args[i:i + (2 if rev else 1)]
        import testmap
        sel, _ = testmap.select(testmap.changed(rev or "HEAD"))
        if sel == testmap.NONE:
            print(f"tests.py --changed {rev or 'HEAD'}: no test can be affected by the changed paths (testmap.py explain)")
            return 0
        if sel != testmap.ALL:
            targets = [os.path.join(KB, *n.split("::")[0].split("/")) + ("::" + n.split("::", 1)[1] if "::" in n else "") for n in sel]
            print(f"tests.py --changed {rev or 'HEAD'}: {len(sel)} of {len(testmap.test_files())} test files or classes")
    if "-m" not in args:
        args = ["-m", "not stress and not git" if os.environ.get("KB_TESTS_FAST") == "1" else "not stress"] + args
    code = run_pytest(targets + args)
    return 0 if code == 5 and targets != [TOOLS] else code  # 5: every selected test was deselected by -m


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
