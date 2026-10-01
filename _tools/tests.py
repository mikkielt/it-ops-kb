#!/usr/bin/env python3
"""Run the kb's tests with pytest and pytest-xdist (pyproject.toml's dev group, installed by uv). Exit 0 when they pass.

  tests.py                         every test module in _tools/ but the stress suite, in parallel
  tests.py -k Leak                 only tests whose name matches (pytest -k); other pytest arguments pass through
  tests.py --changed [REV]         only the test files a change from REV's merge base (default HEAD: the working tree)
                                   can break, from testmap.py's map; none when no test can be affected
  tests.py --write-lint-baseline   record today's lint errors as known debt in _tools/lint_baseline.txt
  KB_TESTS_FAST=1 tests.py         leave out the git scenarios (-m "not git"): kbgit.py sync's gate. With --changed it
                                   keeps them in the test files a code path selects (a changed path outside kb content
                                   and the backlog and query log store): one run of those with -m "not stress", one of
                                   the rest without the git scenarios; an `all` selection still leaves them out
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


FULL_M, FAST_M = "not stress", "not stress and not git"
EVERY = "all"  # every test module in _tools/ (testmap.ALL)


def is_code(path):
    """A changed path whose tests keep their git scenarios in a fast run: any path but kb content and the backlog and
    query log store (testmap's CONTENT and NO_TESTS)."""
    import testmap
    return not path.replace("\\", "/").startswith(testmap.CONTENT + testmap.NO_TESTS)


def plan(paths, fast):
    """The pytest runs for the changed paths: [(nodes, -m expression)], nodes a testmap node list or EVERY; [] when no
    test can be affected. A fast run (KB_TESTS_FAST=1, kbgit.py sync's gate) keeps the git scenarios of the test files
    a code path selects (is_code) and leaves them out of the rest, which only kb content selects, and of an `all`
    selection: the gate runs the slow tests of the code a push changes, not the whole slow suite."""
    import testmap
    sel, _ = testmap.select(paths)
    if sel == testmap.NONE:
        return []
    if sel == testmap.ALL or not fast:
        return [(EVERY if sel == testmap.ALL else sel, FAST_M if fast else FULL_M)]
    code, _ = testmap.select([p for p in paths if is_code(p)])
    if code in (testmap.NONE, testmap.ALL):
        return [(sel, FAST_M)]
    rest = [n for n in sel if n not in code and n.split("::")[0] not in code]
    return [(code, FULL_M)] + ([(rest, FAST_M)] if rest else [])


def target(node):
    """A testmap node (`_tools/test_x.py` or `_tools/test_x.py::Class`) as a pytest target under KB."""
    return os.path.join(KB, *node.split("::")[0].split("/")) + ("::" + node.split("::", 1)[1] if "::" in node else "")


def main(argv):
    if "--write-lint-baseline" in argv:
        return write_lint_baseline()
    args = list(argv)
    fast = os.environ.get("KB_TESTS_FAST") == "1"
    runs = [(EVERY, FAST_M if fast else FULL_M)]
    if "--changed" in args:  # only the tests the change can break (testmap.py)
        i = args.index("--changed")
        rev = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("-") else None
        del args[i:i + (2 if rev else 1)]
        import testmap
        runs = plan(testmap.changed(rev or "HEAD"), fast)
        if not runs:
            print(f"tests.py --changed {rev or 'HEAD'}: no test can be affected by the changed paths (testmap.py explain)")
            return 0
        if runs[0][0] != EVERY:
            n = sum(len(nodes) for nodes, _ in runs)
            slow = f", the git scenarios of {len(runs[0][0])} kept" if fast and runs[0][1] == FULL_M else ""
            print(f"tests.py --changed {rev or 'HEAD'}: {n} of {len(testmap.test_files())} test files or classes{slow}")
    code = 0
    for nodes, m in runs:
        got = run_pytest(([TOOLS] if nodes == EVERY else [target(n) for n in nodes])
                         + ([] if "-m" in args else ["-m", m]) + args)
        code = code or (0 if got == 5 and nodes != EVERY else got)  # 5: every selected test was deselected by -m
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
