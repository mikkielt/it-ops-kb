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

Each run appends one ops row `test.run` to the query log's spool (ql_capture.record, best effort: nothing is written
when capture is off, inside a test, or when the row breaks its closed shape, and a failure to write never changes the
exit code): mode, selected and total test files, workers, milliseconds, exit, passed, failed and skipped counts, the
slowest files, every file's time for a full run and the names of the test files with a failure.

Modules: test_kb_cohesion.py, test_kb_lookup.py, test_kb_ids.py, test_kb_leaks.py, test_merge.py, test_history.py, test_sync.py, test_census.py,
test_kb_mcp.py, test_research_merge.py, test_agent_bench.py, test_portability.py, test_redact.py, test_ql_capture.py,
test_ql_distill.py, test_ql_store.py, test_ql_learn.py, test_ql_deliver.py, test_ql_research.py, test_ql_report.py,
test_querylog_e2e.py, test_backlog.py, test_stress.py; shared fixtures and helpers in conftest.py, and the query log
tests' in ql_testkit.py.
pytest is run as `uv run --frozen python -m pytest` (uv creates .venv from uv.lock on first use), or with this Python
when uv is missing but pytest and pytest-xdist are importable; otherwise exit 2 with how to install them. The tools
under test stay stdlib-only.
"""
import os, re, shutil, subprocess, sys, tempfile, time
import xml.etree.ElementTree as ET

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


SLOW_FILES = 10  # the slowest files a test.run row names
TEST_FILE = re.compile(r"test_\w+|conftest")  # the module part of a junit classname: the test file's name


def junit_files(path):
    """{test file name: [ms, passed, failed, skipped]} read from a pytest junit xml (the time is the sum of its tests'
    times: the work it did, not the wall clock under xdist); {} when the file is missing or unreadable."""
    out = {}
    try:
        for case in ET.parse(path).getroot().iter("testcase"):
            parts = (case.get("classname") or "").split(".")
            name = next((p for p in parts if TEST_FILE.fullmatch(p)), None)
            if name is None:
                continue
            row = out.setdefault(name + ".py", [0.0, 0, 0, 0])
            row[0] += float(case.get("time") or 0)
            bad = case.find("failure") is not None or case.find("error") is not None
            skip = case.find("skipped") is not None
            row[2 if bad else 3 if skip else 1] += 1
    except (OSError, ET.ParseError, ValueError):
        return {}
    return {k: [int(round(v[0] * 1000))] + v[1:] for k, v in out.items()}


def run_fields(mode, entries, total, workers, full_files, ms):
    """The keys of the ops row `test.run` for the pytest runs in `entries` ({"exit", "files"} each, `files` from
    junit_files): counts and times only, and test file names that match the row's closed shape (ql_capture.ops_problems
    refuses the rest). `full_files`: the run covered every test file, so each file's time is kept."""
    import ql_capture
    files = {}
    for e in entries:
        for name, v in e["files"].items():
            cur = files.setdefault(name, [0, 0, 0, 0])
            for i, x in enumerate(v):
                cur[i] += x
    ok = {k: v for k, v in files.items() if ql_capture.OPS_TEST_FILE.fullmatch(k)}
    exits = [e["exit"] for e in entries]
    f = {"mode": mode, "ms": ms, "exit": next((c for c in exits if c), 0) if exits else 0,
         "selected": len(ok), "workers": workers,
         "passed": sum(v[1] for v in files.values()), "failed": sum(v[2] for v in files.values()),
         "skipped": sum(v[3] for v in files.values())}
    if total is not None:
        f["total"] = total
    by_time = sorted(ok.items(), key=lambda kv: (-kv[1][0], kv[0]))
    if by_time:
        f["slow"] = [{"file": k, "ms": v[0]} for k, v in by_time[:SLOW_FILES]]
    if full_files and ok:
        f["files"] = [{"file": k, "ms": ok[k][0]} for k in sorted(ok)][:ql_capture.OPS_LIST_MAX]
    failed = sorted(k for k, v in ok.items() if v[2])
    if failed:
        f["failed_files"] = failed[:ql_capture.OPS_LIST_MAX]
    return f


def inside_test():
    """True in a run started by a test (pytest sets PYTEST_CURRENT_TEST, which a scenario clone's subprocess inherits)."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def record_run(mode, entries, args, wall_ms):
    """Append the `test.run` row of one tests.py run; best effort: it returns None and raises nothing when ops capture is
    unavailable, when the run is inside a test (a scenario clone's run never writes into the real spool) or when the
    row breaks its shape."""
    try:
        if not entries or inside_test():
            return None
        import ql_capture
        workers = args[args.index("-n") + 1] if "-n" in args[:-1] else XDIST[1]
        workers = os.cpu_count() if workers == "auto" else int(workers)
        try:
            import testmap
            total = len(testmap.test_files())
        except Exception:  # noqa: BLE001 - a count the row can do without
            total = None
        full = mode == "full" and not any(a == "-k" or a.startswith("-k") for a in args)
        fields = run_fields(mode, entries, total, workers, full, wall_ms)
        return ql_capture.record("ops", event="test.run", **fields)
    except Exception:  # noqa: BLE001 - a run never fails for its log
        return None


def run_mode(env, fast):
    return "stress" if "KB_STRESS_SCALE" in (env or {}) else "fast" if fast else "full"


def run_pytest(args, env=None, dist="loadscope", report=None, mode=None):
    """Run pytest; the exit code. With `report` (a list) the run's result is appended to it for the caller to record
    once; without, the run records its own `test.run` row."""
    cmd = pytest_cmd()
    if cmd is None:
        print("pytest and pytest-xdist are needed: install uv (https://docs.astral.sh/uv/) and rerun, or "
              "`pip install pytest pytest-xdist`", file=sys.stderr)
        return 2
    xml, extra = None, []
    if not any(a.startswith("--junitxml") for a in args):
        fd, xml = tempfile.mkstemp(suffix=".xml", prefix="kb-tests-")
        os.close(fd)
        extra = [f"--junitxml={xml}"]
    start = time.monotonic()
    try:
        code = subprocess.run(cmd + XDIST + ["--dist", dist] + extra + args, cwd=KB,
                              env={**os.environ, **(env or {})}).returncode
        entry = {"exit": code, "ms": int((time.monotonic() - start) * 1000), "files": junit_files(xml) if xml else {}}
    finally:
        if xml:
            try:
                os.unlink(xml)
            except OSError:
                pass
    if report is not None:
        report.append(entry)
    else:
        record_run(mode or run_mode(env, os.environ.get("KB_TESTS_FAST") == "1"), [entry], args, entry["ms"])
    return code


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
    changed = "--changed" in args
    if changed:  # only the tests the change can break (testmap.py)
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
    code, report, start = 0, [], time.monotonic()
    for nodes, m in runs:
        got = run_pytest(([TOOLS] if nodes == EVERY else [target(n) for n in nodes])
                         + ([] if "-m" in args else ["-m", m]) + args, report=report)
        code = code or (0 if got == 5 and nodes != EVERY else got)  # 5: every selected test was deselected by -m
    for e in report:  # a deselected-to-nothing run is a pass here, and so is its row's exit
        if e["exit"] == 5 and runs[0][0] != EVERY:
            e["exit"] = 0
    record_run("changed" if changed else "fast" if fast else "full", report, args, int((time.monotonic() - start) * 1000))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
