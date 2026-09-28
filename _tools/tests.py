#!/usr/bin/env python3
"""Run the kb's tests with pytest and pytest-xdist (pyproject.toml's dev group, installed by uv). Exit 0 when they pass.

  tests.py                         every test module in _tools/ but the stress suite, in parallel
  tests.py -k Leak                 only tests whose name matches (pytest -k); other pytest arguments pass through
  tests.py --write-lint-baseline   record today's lint errors as known debt in _tools/lint_baseline.txt
  KB_TESTS_FAST=1 tests.py         leave out the git scenarios (-m "not git"): kbgit.py sync's gate
  stress_test.py                   the stress suite (test_stress.py)

Modules: test_kb.py (cohesion, lookup, ids, leaks), test_merge.py, test_history.py, test_sync.py, test_census.py,
test_kb_mcp.py, test_research_merge.py, test_agent_bench.py, test_stress.py; shared fixtures and helpers in conftest.py.
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
    out = subprocess.run([sys.executable, lint], cwd=KB, capture_output=True, text=True, errors="replace")
    errs = sorted({ln.strip() for ln in (out.stdout + out.stderr).splitlines() if ln.startswith("ERROR")})
    with open(os.path.join(TOOLS, "lint_baseline.txt"), "w", encoding="utf-8") as f:
        f.write("".join(e + "\n" for e in errs))
    print(f"wrote {len(errs)} known lint errors to _tools/lint_baseline.txt")
    return 0


def main(argv):
    if "--write-lint-baseline" in argv:
        return write_lint_baseline()
    args = list(argv)
    if "-m" not in args:
        args = ["-m", "not stress and not git" if os.environ.get("KB_TESTS_FAST") == "1" else "not stress"] + args
    return run_pytest([TOOLS] + args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
