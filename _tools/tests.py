#!/usr/bin/env python3
"""Run the kb's tests with pytest and pytest-xdist (pyproject.toml's dev group, installed by uv). Exit 0 when they pass.

  tests.py                         every test module in _tools/ but the stress suite, in parallel
  tests.py -k Leak                 only tests whose name matches (pytest -k); other pytest arguments pass through
  tests.py PATH [PATH ...]         only those test files or directories (and their `::` nodes), not _tools/; -k and other pytest
                                   arguments pass through
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

A full run, a --changed run with more than one worker and stress_test.py take a host-wide lock first (host_lock): an
O_EXCL file in KB_HOST_LOCK_DIR (default /tmp, or the public directory on Windows) holding the pid, clone and start time.
A second run prints who holds it and waits; a holder whose pid no longer runs is cleared by one waiter (an atomic claim),
an empty lock file only after KB_HOST_LOCK_GRACE seconds (default 10). A -k run, a run inside a test,
a run that names only a few test files (at most NAMED_FILES_LOCK_FREE, 4; no --changed) and a one-worker run (-n 1)
take none; the run that names only a few test files records mode files and no file times, so mode full holds only
runs of the whole selection. A run that names more files (a shell glob of every test file) is a full run: it takes the
lock and records mode full with every file's time.

The default worker count is capped, not one per CPU: KB_TEST_WORKERS (a number) when set, else the CPUs divided among
this run and the other live tests.py runs (each run holds a kb-tests-run.PID file beside the lock while it runs; a dead
pid's is removed), at most DEFAULT_WORKER_CAP (8, the fastest of three timed counts on one 14-core host; a 4-core and an
8-core host are unmeasured), at least 1; an explicit -n in the arguments wins.

Modules: test_kb_cohesion.py, test_kb_lookup.py, test_kb_ids.py, test_kb_leaks.py, test_merge.py, test_history.py, test_sync.py, test_census.py,
test_kb_mcp.py, test_research_merge.py, test_agent_bench.py, test_portability.py, test_redact.py, test_ql_capture.py,
test_ql_distill.py, test_ql_store.py, test_ql_learn.py, test_ql_deliver.py, test_ql_research.py, test_ql_report.py,
test_querylog_e2e.py, test_backlog.py, test_stress.py; shared fixtures and helpers in conftest.py, and the query log
tests' in ql_testkit.py.
pytest is run as `uv run --frozen python -m pytest` (uv creates .venv from uv.lock on first use), or with this Python
when uv is missing but pytest and pytest-xdist are importable; otherwise exit 2 with how to install them. The tools
under test stay stdlib-only.
"""
import contextlib, datetime, os, re, shutil, signal, subprocess, sys, tempfile, time
import xml.etree.ElementTree as ET

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
XDIST = ["-n", "auto"]  # dist loadscope: a class's scenario is built once, on one worker (stress_test.py: load); run with
# --no-loadscope-reorder, conftest.pytest_collection_modifyitems orders the scopes: class-fixture scenarios first;
# "auto" here means default_workers(): the CPUs shared among the tests.py runs live on the host, KB_TEST_WORKERS overriding


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
        workers = worker_count(args)
        try:
            import testmap
            total = len(testmap.test_files())
        except Exception:  # noqa: BLE001 - a count the row can do without
            total = None
        full = mode == "full" and not any(a == "-k" or a.startswith("-k") for a in args) and not named_files_only(args)
        fields = run_fields(mode, entries, total, workers, full, wall_ms)
        return ql_capture.record("ops", event="test.run", **fields)
    except Exception:  # noqa: BLE001 - a run never fails for its log
        return None


def run_mode(env, fast):
    return "stress" if "KB_STRESS_SCALE" in (env or {}) else "fast" if fast else "full"


def xdist_args():
    """The default -n arguments: XDIST, with "auto" replaced by the capped default_workers()."""
    return ["-n", str(default_workers())] if XDIST[1] == "auto" else list(XDIST)


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
        code = subprocess.run(cmd + xdist_args() + ["--dist", dist] + (["--no-loadscope-reorder"] if dist == "loadscope" else []) + extra + args, cwd=KB,
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


HOST_LOCK_NAME = "kb-tests.lock"
HOST_LOCK_GRACE = 10.0  # seconds


def host_lock_dir():
    """Where the host lock lives: KB_HOST_LOCK_DIR, else a directory every user of the host can reach (not the per-user
    temp directory): /tmp, or the Public profile on Windows."""
    env = os.environ.get("KB_HOST_LOCK_DIR")
    if env:
        return env
    return os.environ.get("PUBLIC", r"C:\Users\Public") if os.name == "nt" else "/tmp"


def pid_alive(pid):
    """Whether process `pid` runs, asked of the OS without signalling it (ps, tasklist); True when it cannot be told."""
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=30).stdout
            return str(pid) in out.split()
        return subprocess.run(["ps", "-p", str(pid), "-o", "pid="], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


def parse_holder(text):
    """{pid, clone, started} of a lock file's text, or None when it does not hold a record (empty, torn, garbled)."""
    try:
        got = dict(ln.split("=", 1) for ln in text.splitlines() if "=" in ln)
        return {"pid": int(got["pid"]), "clone": got.get("clone", "?"), "started": got.get("started", "?")}
    except (ValueError, KeyError):
        return None


def read_lock(path):
    """The raw text of a lock file, or None when it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, ValueError):
        return None


def read_holder(path):
    """{pid, clone, started} of a lock file, or None when it is missing or unreadable."""
    text = read_lock(path)
    return None if text is None else parse_holder(text)


def lock_grace():
    """Seconds an empty or unreadable lock file is left alone, for its holder to write the record (KB_HOST_LOCK_GRACE)."""
    try:
        return float(os.environ.get("KB_HOST_LOCK_GRACE", HOST_LOCK_GRACE))
    except ValueError:
        return HOST_LOCK_GRACE


def clear_stale(path, judged):
    """Remove the lock file whose text the caller judged stale, only if it is still that text: claim it by renaming it to
    a name of this waiter (one waiter's rename succeeds, the others find no file), check that what was claimed is what
    was judged, then delete it. A lock another waiter wrote in between is put back (a link, which never replaces) and
    left alone. True when this waiter cleared it."""
    if read_lock(path) != judged:
        return False
    mine = f"{path}.clear.{os.getpid()}.{os.urandom(4).hex()}"
    try:
        os.replace(path, mine)
    except OSError:
        return False  # someone else took it
    took = read_lock(mine)
    if took != judged:
        with contextlib.suppress(OSError):
            os.link(mine, path)
    with contextlib.suppress(OSError):
        os.unlink(mine)
    return took == judged


@contextlib.contextmanager
def host_lock(label="tests.py", poll=None, on_stale=None):
    """Hold the host-wide test lock for the block: take it by exclusive create, print who holds it and wait while a live
    process does, clear a holder whose pid no longer runs (clear_stale: one waiter does, none removes a lock it did not
    judge), leave an empty or unreadable file alone for lock_grace() seconds, and release on exit, on an error and on
    SIGTERM. on_stale(label) is called after a lock is judged stale and before it is cleared (a test's hook)."""
    path = os.path.join(host_lock_dir(), HOST_LOCK_NAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    poll = poll if poll is not None else float(os.environ.get("KB_HOST_LOCK_POLL", "5"))
    me = (f"pid={os.getpid()}\nclone={KB}\n"
          f"started={datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
    told = None
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            text = read_lock(path)
            if text is None and not os.path.exists(path):  # released: look again
                continue
            holder = parse_holder(text or "")
            if holder is None:
                try:
                    young = time.time() - os.stat(path).st_mtime < lock_grace()
                except OSError:
                    continue
                if young:  # its holder has not written the record yet
                    time.sleep(poll)
                    continue
            if holder is None or not pid_alive(holder["pid"]):
                if on_stale:
                    on_stale(label)
                if clear_stale(path, text):
                    print(f"{label}: clearing a stale host test lock ({holder['pid'] if holder else 'unreadable'})",
                          flush=True)
                continue
            if holder != told:
                print(f"{label}: waiting for the host test lock held by pid {holder['pid']} "
                      f"(clone {holder['clone']}, started {holder['started']})", flush=True)
                told = holder
            time.sleep(poll)
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(me)
        break
    prev = None
    try:
        prev = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    except (ValueError, OSError):  # not the main thread
        pass
    try:
        yield path
    finally:
        if prev is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGTERM, prev)
        holder = read_holder(path)
        if holder and holder["pid"] == os.getpid():
            with contextlib.suppress(OSError):
                os.unlink(path)


RUN_PREFIX = "kb-tests-run."


def live_runs():
    """How many other tests.py runs are live on the host: the run files (RUN_PREFIX + pid, in the host lock's directory)
    whose pid still runs and is not this process's; a file of a pid that no longer runs is removed."""
    base, n = host_lock_dir(), 0
    try:
        names = os.listdir(base)
    except OSError:
        return 0
    for name in names:
        pid = name[len(RUN_PREFIX):]
        if not name.startswith(RUN_PREFIX) or not pid.isdigit() or int(pid) == os.getpid():
            continue
        if pid_alive(int(pid)):
            n += 1
        else:
            with contextlib.suppress(OSError):
                os.unlink(os.path.join(base, name))
    return n


@contextlib.contextmanager
def run_registered():
    """Count this run among the live ones (a RUN_PREFIX file named by its pid) for the block; not inside a test."""
    path = os.path.join(host_lock_dir(), RUN_PREFIX + str(os.getpid()))
    made = False
    if not inside_test():
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"clone={KB}\n")
            made = True
        except OSError:
            pass
    try:
        yield
    finally:
        if made:
            with contextlib.suppress(OSError):
                os.unlink(path)


# The most workers a default run starts. Full runs of this suite (5005 tests passed each) on one 14-core, 24 GB macOS
# host at load 3 to 7 took 770 s at -n 4, 681 s at -n 6 and 642 s at -n 8; no count above 8 was timed in that series,
# and no 4-core or 8-core host was measured, so 8 is the best count measured on that one host only. The one full run
# above 8 in the query log's spool (-n 14, 570 s, 4783 tests passed) was not part of the series and its load is unknown:
# it does not show that 14 is faster. A host with fewer CPUs still gets its share, cpus // (others + 1).
DEFAULT_WORKER_CAP = 8


def default_workers(others=None, cpus=None):
    """The workers a run uses when no -n is given: KB_TEST_WORKERS when it is a number (at least 1), else the CPUs
    divided among this run and the `others` live ones (live_runs() when None), at most DEFAULT_WORKER_CAP, never
    below 1."""
    try:
        return max(int(os.environ["KB_TEST_WORKERS"]), 1)
    except (KeyError, ValueError):
        pass
    cpus = cpus if cpus is not None else (os.cpu_count() or 1)
    return max(min(cpus // ((live_runs() if others is None else others) + 1), DEFAULT_WORKER_CAP), 1)


def worker_count(args, others=None):
    """The xdist workers a run with these pytest arguments uses (the last -n wins; the default is XDIST's, the capped
    default_workers() for "auto")."""
    val = None
    for i, a in enumerate(args):
        if a == "-n" and i + 1 < len(args):
            val = args[i + 1]
        elif a.startswith("-n") and len(a) > 2:
            val = a[2:]
    if val is None:
        val = XDIST[1]
        if val == "auto":
            return default_workers(others)
    if val == "auto":
        return os.cpu_count() or 1
    try:
        return max(int(val), 1)
    except ValueError:
        return 1


def wants_host_lock(args):
    """A run takes the host lock unless it is inside a test, selects with -k, names at most NAMED_FILES_LOCK_FREE test
    files and no directory (a cheap targeted run; a longer list or a named directory is a full-scope run and takes it;
    `--changed` never counts as one) or uses one worker."""
    return (not inside_test() and not any(a == "-k" or a.startswith("-k") for a in args) and not named_files_only(args)
            and worker_count(args) > 1)


VALUE_OPTIONS = {"-k", "-m", "-n", "-p", "-c", "-o", "--dist", "--maxfail", "--deselect", "--ignore", "--rootdir",
                 "--junitxml", "--durations", "--timeout", "--basetemp", "--tb", "-W", "--ignore-glob", "--confcutdir",
                 "--import-mode", "--log-level", "--log-format", "--log-file", "--log-cli-level", "--capture"}  # pytest options whose next argument is their value


def path_args(args):
    """The arguments that name a test file or directory (an existing path, with an optional `::node`), not the value of
    an option such as -k or -m; relative to the clone or to the working directory."""
    out = []
    for i, a in enumerate(args):
        if a.startswith("-") or (i and args[i - 1] in VALUE_OPTIONS):
            continue
        base = a.split("::")[0]
        if base and (os.path.exists(os.path.join(KB, base)) or os.path.exists(base)):
            out.append(a)
    return out


NAMED_FILES_LOCK_FREE = 4  # a handful of named files is cheap enough to skip the host lock; a shell glob of every test file is not


def named_files_only(args):
    """True when the arguments name at least one path, every one a file (optionally `::node`), at most
    NAMED_FILES_LOCK_FREE distinct files, and the run is not `--changed`: a cheap targeted run of a few files. A named
    directory, no path, or more files than that (a shell glob of the test files) is a full-scope run."""
    if "--changed" in args:
        return False
    paths = path_args(args)
    files = {a.split("::")[0] for a in paths}
    return (bool(paths) and len(files) <= NAMED_FILES_LOCK_FREE
            and all(os.path.isfile(os.path.join(KB, f)) or os.path.isfile(f) for f in files))


def main(argv):
    with run_registered():
        if wants_host_lock(argv):
            with host_lock("tests.py"):
                return run_main(argv)
        return run_main(argv)


def run_main(argv):
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
    named = not changed and bool(path_args(args))  # tests.py PATH: only the named files, not every test file beside them
    code, report, start = 0, [], time.monotonic()
    for nodes, m in runs:
        got = run_pytest(([] if named else [TOOLS] if nodes == EVERY else [target(n) for n in nodes])
                         + ([] if "-m" in args else ["-m", m]) + args, report=report)
        code = code or (0 if got == 5 and nodes != EVERY else got)  # 5: every selected test was deselected by -m
    for e in report:  # a deselected-to-nothing run is a pass here, and so is its row's exit
        if e["exit"] == 5 and runs[0][0] != EVERY:
            e["exit"] = 0
    mode = "changed" if changed else "files" if named_files_only(args) else "fast" if fast else "full"
    record_run(mode, report, args, int((time.monotonic() - start) * 1000))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
