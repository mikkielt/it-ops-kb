#!/usr/bin/env python3
"""Run the kb's tests with pytest and pytest-xdist (pyproject.toml's dev group, installed by uv). Exit 0 when they pass
and the suite is within its ceiling.

  tests.py                         every test file in _tools/, in parallel; fails when the run breaks the ceiling
  tests.py -k NAME                 only tests whose name matches (pytest -k); other pytest arguments pass through
  tests.py PATH [PATH ...]         only those test files (and their `::` nodes)
  tests.py --changed [REV]         what a change from REV's merge base (default HEAD: the working tree) needs: nothing
                                   when only backlog items or the query log store changed, the suite without the git
                                   scenarios when only kb content changed, the whole suite for any other path
  tests.py --ceiling               collect the test ids without running them and compare ids and files with the ceiling
  tests.py --write-lint-baseline   record today's lint errors as known debt in _tools/lint_baseline.txt
  KB_TESTS_FAST=1 tests.py         leave out the git scenarios (-m "not git")

Before pytest, every run (a selection and a --changed run too, not --ceiling or --write-lint-baseline) compiles each
_tools/*.py in-process from its source text, writing no .pyc, and exits 1 naming each file and line whose compile warns
(compile_warnings), such as an invalid escape sequence: a SyntaxWarning, a DeprecationWarning before Python 3.12. A
cached .pyc does not warn and pytest only prints a warning, so a file no test imports would otherwise pass.

The ceiling (_tools/tests_ceiling.json: max_ids, max_files, max_seconds per sys.platform, decision) is the most the
suite may hold and the longest a full run may take. Every run checks the file count and that `decision` names an active
decision of kb/_self/_decisions.csv made by the operator whose text holds the file's own numbers (ceiling_token), so a
number changes only with the operator's recorded answer. A full run also fails when it ran more ids than max_ids or took
longer than max_seconds; --ceiling checks the ids without running. On a CI runner (GITLAB_CI or GITHUB_ACTIONS set)
KB_TEST_TIMEOUT_FACTOR (a number of at least 1) multiplies max_seconds, for a container slower than the host the
seconds were set on. A new test id needs room under max_ids, else it replaces one.

Each run appends one ops row `test.run` to the query log's spool (ql_capture.record, best effort: nothing is written
when capture is off, inside a test, or when the row breaks its closed shape, and a failure to write never changes the
exit code): mode, selected and total test files, workers, milliseconds, exit, passed, failed and skipped counts, the
slowest files, every file's time for a full run and the names of the test files with a failure. A run a backlog check
makes writes it to the spool of the query log directory KB_TEST_RUN_HOME names (bl_base.check_env: the clone's real
one), the one capture of that check outside its isolated home.

A full run and a --changed run take a host-wide lock first (host_lock): an O_EXCL file in KB_HOST_LOCK_DIR (default
/tmp, or the public directory on Windows) holding the pid, clone and start time. A second run prints who holds it and
waits; a holder whose pid no longer runs is cleared by one waiter (an atomic claim), an empty lock file only after
KB_HOST_LOCK_GRACE seconds (default 10). A -k run, a run of named files, a run inside a test and a one-worker run
(-n 1) take none. kg_lock.py's main lock uses the same helpers.

The default worker count is KB_TEST_WORKERS (a number) when set, else the CPUs divided among this run and the other
live tests.py runs (each holds a kb-tests-run.PID file beside the lock), at most DEFAULT_WORKER_CAP, at least 1; an
explicit -n in the arguments wins.

pytest is run as `uv run --frozen python -m pytest` (uv creates .venv from uv.lock on first use), or with this Python
when uv is missing but pytest and pytest-xdist are importable; otherwise exit 2 with how to install them. The tools
under test stay stdlib-only. Shared fixtures and helpers are in conftest.py.
"""
import contextlib, csv, datetime, json, os, pathlib, re, shutil, signal, subprocess, sys, tempfile, time, warnings
import xml.etree.ElementTree as ET

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
CEILING = os.path.join(TOOLS, "tests_ceiling.json")
DECISIONS = os.path.join(KB, "kb", "_self", "_decisions.csv")
NO_TESTS = ("kb/_self/backlog/", "kb/_querylog/")  # the gate's own checks cover them (backlog.py check, querylog.py check)
CONTENT = ("kb/", "AGENTS.md", "README.md", "CLAUDE.md")  # kb content: the git scenarios read none of it
FAST_M = "not git"


def pytest_cmd():
    """The command that runs pytest, or None."""
    if shutil.which("uv"):
        return ["uv", "run", "--quiet", "--frozen", "--project", KB, "python", "-m", "pytest"]
    try:
        import pytest, xdist  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "pytest"]


def test_files():
    return sorted(f for f in os.listdir(TOOLS) if f.startswith("test_") and f.endswith(".py"))


# The compile check


def compile_warnings(tools=None):
    """`path:line: Category: message` for each warning (and SyntaxError) compiling each *.py of `tools` (default
    _tools/) from its source text gives, in file order; compile() writes no .pyc and a cached one is never read. The
    warnings are recorded, not raised: raised, a SyntaxWarning turns into a SyntaxError and loses its category."""
    base = pathlib.Path(tools or TOOLS)
    out = []
    for path in sorted(base.glob("*.py")):
        name = path.relative_to(base.parent).as_posix()
        try:
            src = path.read_bytes()
        except OSError as e:
            out.append(f"{name}: unreadable ({e.__class__.__name__})")
            continue
        with warnings.catch_warnings(record=True) as got:
            warnings.simplefilter("always")
            try:
                compile(src, str(path), "exec", dont_inherit=True)
            except SyntaxError as e:
                out.append(f"{name}:{e.lineno}: SyntaxError: {e.msg}")
        seen = []
        for w in got:
            line = f"{name}:{w.lineno}: {w.category.__name__}: {w.message}"
            if line not in seen:
                seen.append(line)
        out += seen
    return out


def compile_report(tools=None):
    """Print each compile warning of compile_warnings(); 1 when there is one, else 0."""
    bad = compile_warnings(tools)
    for b in bad:
        print(f"tests.py: compile warning: {b}", file=sys.stderr)
    if bad:
        print(f"tests.py: {len(bad)} compile warning(s) in _tools/, an error here: fix them (a raw string r\"...\" or "
              "a doubled backslash for an escape) before the tests run", file=sys.stderr)
    return 1 if bad else 0


# The ceiling


class CeilingError(Exception):
    """The ceiling file or its decision cannot be accepted."""


def ceiling_token(c):
    """The text an operator's decision holds for the ceiling's numbers: `tests-ceiling ids=N files=N seconds=p:N,...`."""
    secs = ",".join(f"{k}:{v}" for k, v in sorted(c["max_seconds"].items()))
    return f"tests-ceiling ids={c['max_ids']} files={c['max_files']} seconds={secs}"


def read_ceiling(path=None, decisions=None):
    """The ceiling {max_ids, max_files, max_seconds, decision} of `path`; CeilingError when the file is missing or
    malformed, or when no active decision of the operator in `decisions` with the id it names holds its numbers."""
    path, decisions = path or CEILING, decisions or DECISIONS
    try:
        with open(path, encoding="utf-8") as f:
            c = json.load(f)
        ok = (type(c["max_ids"]) is int and type(c["max_files"]) is int and isinstance(c["decision"], str)
              and isinstance(c["max_seconds"], dict) and c["max_seconds"]
              and all(type(v) is int for v in c["max_seconds"].values()))
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise CeilingError(f"{path}: unreadable ceiling ({e.__class__.__name__})") from None
    if not ok:
        raise CeilingError(f"{path}: max_ids, max_files (integers), max_seconds ({{platform: integer}}) and decision are needed")
    try:
        with open(decisions, encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("id") == c["decision"]]
    except OSError:
        rows = []
    token = ceiling_token(c)
    if not any(r.get("status") == "active" and r.get("by") == "operator" and token in (r.get("text") or "") for r in rows):
        raise CeilingError(f"{os.path.basename(path)}: no active decision {c['decision']} of the operator records "
                           f"`{token}`; the ceiling changes only with the operator's recorded answer "
                           "(backlog.py answer ID GATE --answer TEXT --by operator --record)")
    return c


def seconds_factor(env=None):
    """KB_TEST_TIMEOUT_FACTOR on a CI runner (a number of at least 1), else 1."""
    env = os.environ if env is None else env
    if not (env.get("GITLAB_CI") or env.get("GITHUB_ACTIONS")):
        return 1.0
    try:
        return max(float(env.get("KB_TEST_TIMEOUT_FACTOR") or 1), 1.0)
    except ValueError:
        return 1.0


def ceiling_problems(c, files=None, ids=None, seconds=None, platform=None, factor=1.0):
    """What breaks the ceiling `c`: one line for each of the given counts (None: not measured) that is over."""
    out = []
    if files is not None and files > c["max_files"]:
        out.append(f"{files} test files, the ceiling is {c['max_files']}")
    if ids is not None and ids > c["max_ids"]:
        out.append(f"{ids} test ids, the ceiling is {c['max_ids']}: a new test id replaces one")
    limit = c["max_seconds"].get(platform or sys.platform)
    if seconds is not None and limit is not None and seconds > limit * factor:
        out.append(f"the full run took {seconds:.0f} s, the ceiling is {limit * factor:.0f} s on {platform or sys.platform}")
    return out


def collect_ids():
    """How many test ids pytest collects in _tools/ (nothing runs), or None when the collection fails."""
    cmd = pytest_cmd()
    if cmd is None:
        return None
    p = subprocess.run(cmd + ["--collect-only", "-q", "-p", "no:cacheprovider", TOOLS], cwd=KB, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode not in (0, 5):
        return None
    return sum(1 for ln in p.stdout.splitlines() if "::" in ln and not ln.startswith(" "))


def ceiling_report(ids=None, seconds=None):
    """Print the ceiling's verdict for the measured counts; 0 when within it, 1 when over or the file is refused."""
    try:
        c = read_ceiling()
    except CeilingError as e:
        print(f"tests.py: ceiling refused: {e}", file=sys.stderr)
        return 1
    bad = ceiling_problems(c, files=len(test_files()), ids=ids, seconds=seconds, factor=seconds_factor())
    for b in bad:
        print(f"tests.py: over the ceiling: {b}", file=sys.stderr)
    if bad:
        print("tests.py: cut a test, or ask the operator for a recorded answer that raises _tools/tests_ceiling.json",
              file=sys.stderr)
    return 1 if bad else 0


# The test.run row

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


def run_fields(mode, entry, workers, full):
    """The keys of the ops row `test.run` for one pytest run (`entry`: {"exit", "ms", "files"}, `files` from
    junit_files): counts and times only, and test file names that match the row's closed shape. `full`: the run
    covered every test file, so each file's time is kept."""
    import ql_capture
    files = entry["files"]
    ok = {k: v for k, v in files.items() if ql_capture.OPS_TEST_FILE.fullmatch(k)}
    f = {"mode": mode, "ms": entry["ms"], "exit": entry["exit"], "selected": len(ok), "total": len(test_files()),
         "workers": workers, "passed": sum(v[1] for v in files.values()), "failed": sum(v[2] for v in files.values()),
         "skipped": sum(v[3] for v in files.values())}
    by_time = sorted(ok.items(), key=lambda kv: (-kv[1][0], kv[0]))
    if by_time:
        f["slow"] = [{"file": k, "ms": v[0]} for k, v in by_time[:SLOW_FILES]]
    if full and ok:
        f["files"] = [{"file": k, "ms": ok[k][0]} for k in sorted(ok)][:ql_capture.OPS_LIST_MAX]
    failed = sorted(k for k, v in ok.items() if v[2])
    if failed:
        f["failed_files"] = failed[:ql_capture.OPS_LIST_MAX]
    return f


def inside_test():
    """True in a run started by a test (pytest sets PYTEST_CURRENT_TEST, which a scenario clone's subprocess inherits)."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def record_run(mode, entry, args):
    """Append the `test.run` row of one tests.py run; best effort: it returns None and raises nothing when ops capture is
    unavailable, when the run is inside a test (a scenario clone's run never writes into the real spool) or when the
    row breaks its shape. A run a backlog check makes (bl_base.check_env) has KB_TEST_RUN_HOME, the clone's real query
    log directory: the row goes to that spool, not to the check's isolated home."""
    try:
        if inside_test():
            return None
        import ql_capture
        home = os.environ.get("KB_TEST_RUN_HOME")
        if home:
            ql_capture.spool_dir = lambda: pathlib.Path(home) / "spool"
        return ql_capture.record("ops", event="test.run", **run_fields(mode, entry, worker_count(args), mode == "full"))
    except Exception:  # noqa: BLE001 - a run never fails for its log
        return None


def run_pytest(args):
    """Run pytest with the default workers; {"exit", "ms", "files"} of the run, or None when pytest is missing."""
    cmd = pytest_cmd()
    if cmd is None:
        print("pytest and pytest-xdist are needed: install uv (https://docs.astral.sh/uv/) and rerun, or "
              "`pip install pytest pytest-xdist`", file=sys.stderr)
        return None
    fd, xml = tempfile.mkstemp(suffix=".xml", prefix="kb-tests-")
    os.close(fd)
    start = time.monotonic()
    try:
        code = subprocess.run(cmd + ["-n", str(worker_count(args)), "--dist", "loadscope", "--no-loadscope-reorder",
                                    f"--junitxml={xml}"] + args,
                              cwd=KB).returncode
        return {"exit": code, "ms": int((time.monotonic() - start) * 1000), "files": junit_files(xml)}
    finally:
        with contextlib.suppress(OSError):
            os.unlink(xml)


def write_lint_baseline():
    lint = os.path.join(KB, ".claude", "skills", "kb-verify", "lint.py")
    out = subprocess.run([sys.executable, lint], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
    errs = sorted({ln.strip() for ln in (out.stdout + out.stderr).splitlines() if ln.startswith("ERROR")})
    with open(os.path.join(TOOLS, "lint_baseline.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(e + "\n" for e in errs))
    print(f"wrote {len(errs)} known lint errors to _tools/lint_baseline.txt")
    return 0


# What a change needs


def changed(since):
    """Paths changed from the merge base of `since` and HEAD to the working tree, untracked files included."""
    def git(*args):
        p = subprocess.run(["git", *args], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode:
            raise SystemExit(f"tests.py: git {' '.join(args)} failed: {p.stderr.strip()}")
        return p.stdout
    base = git("merge-base", since, "HEAD").strip()
    names = git("diff", "--name-only", base).splitlines() + git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({n.strip().replace("\\", "/") for n in names if n.strip()})


def scope(paths):
    """What the changed `paths` need: `none` (only backlog items and the query log store, or nothing), `content` (only
    kb content beside those: the suite without the git scenarios) or `all` (any other path: the whole suite)."""
    rest = [p for p in paths if not p.startswith(NO_TESTS)]
    if not rest:
        return "none"
    return "content" if all(p.startswith(CONTENT) for p in rest) else "all"


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


DEFAULT_WORKER_CAP = 12  # the most workers a default run starts: a worker for each test file of a suite this small


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
    """The xdist workers a run with these pytest arguments uses: the last -n (`auto`: one per CPU), else
    default_workers()."""
    val = None
    for i, a in enumerate(args):
        if a == "-n" and i + 1 < len(args):
            val = args[i + 1]
        elif a.startswith("-n") and len(a) > 2:
            val = a[2:]
    if val is None:
        return default_workers(others)
    if val == "auto":
        return os.cpu_count() or 1
    try:
        return max(int(val), 1)
    except ValueError:
        return 1


VALUE_OPTIONS = {"-k", "-m", "-n", "-p", "-c", "-o", "--dist", "--maxfail", "--deselect", "--ignore", "--rootdir",
                 "--junitxml", "--durations", "--basetemp", "--tb", "-W"}  # pytest options whose next argument is their value


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


def keyword_run(args):
    """True when the arguments select tests by `-k` (`-k EXPR` or `-kEXPR`)."""
    return any(a == "-k" or (a.startswith("-k") and len(a) > 2) for a in args)


def run_scope(args, changed_run, fast):
    """The `mode` of a run's test.run row: `changed`, `files` (named files), `keyword` (a `-k` selection), `fast` or
    `full`; a run that selects tests is never `full`."""
    if changed_run:
        return "changed"
    if path_args(args):
        return "files"
    if keyword_run(args):
        return "keyword"
    return "fast" if fast else "full"


def wants_host_lock(args):
    """A run takes the host lock unless it is inside a test, selects with -k, names test files, only reads the ceiling
    or uses one worker."""
    return (not inside_test() and not keyword_run(args) and "--ceiling" not in args
            and ("--changed" in args or not path_args(args)) and worker_count(args) > 1)


def main(argv):
    with run_registered():
        if wants_host_lock(argv):
            with host_lock("tests.py"):
                return run_main(argv)
        return run_main(argv)


def run_main(argv):
    if "--write-lint-baseline" in argv:
        return write_lint_baseline()
    if "--ceiling" in argv:
        ids = collect_ids()
        if ids is None:
            print("tests.py --ceiling: pytest could not collect the tests", file=sys.stderr)
            return 2
        code = ceiling_report(ids=ids)
        if not code:
            print(f"tests.py --ceiling: {ids} test ids in {len(test_files())} files, within the ceiling")
        return code
    if compile_report():
        return 1
    args = list(argv)
    fast = os.environ.get("KB_TESTS_FAST") == "1"
    changed_run = "--changed" in args
    if changed_run:
        i = args.index("--changed")
        rev = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("-") else None
        del args[i:i + (2 if rev else 1)]
        need = scope(changed(rev or "HEAD"))
        if need == "none":
            print(f"tests.py --changed {rev or 'HEAD'}: no test can be affected by the changed paths")
            return 0
        fast = need == "content"
        print(f"tests.py --changed {rev or 'HEAD'}: " + ("kb content only, the suite without the git scenarios"
                                                          if fast else "the whole suite"))
    mode = run_scope(args, changed_run, fast)
    entry = run_pytest(([] if path_args(args) else [TOOLS]) + ([] if "-m" in args or not fast else ["-m", FAST_M]) + args)
    if entry is None:
        return 2
    record_run(mode, entry, args)
    whole = not path_args(args) and not keyword_run(args) and "-m" not in args
    ran = sum(v[1] + v[2] + v[3] for v in entry["files"].values())
    over = ceiling_report(ids=ran if whole and not fast else None,
                          seconds=entry["ms"] / 1000 if mode == "full" else None)
    return entry["exit"] or over


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
