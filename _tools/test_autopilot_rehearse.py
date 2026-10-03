"""The autopilot rehearsal (autopilot_rehearse.py; kb/_self/tools.md, The autopilot runner). The tests named
autopilot_rehearse_* are the item's checks:

- the whole rehearsal runs with the stubbed `claude` and ends `rehearse: ok (N steps)` with exit 0, each step on its line;
- a planted failure at each step (KB_REHEARSE_FAIL) ends the run with exit 1 and `FAILED at step <name>`, and the
  temporary directory is gone;
- a successful run leaves no process of its clone, no runner record and no worktree but the clone's own;
- a command or a runner that outlives the step bound fails the step and its process is ended;
- SIGINT and SIGTERM end the run with exit 1, its processes ended and its directory removed.

The rehearsal clones this repository's HEAD into a temporary directory with a bare repository for origin, so a test reads
the repository and writes nowhere else.
"""
import os, re, shutil, signal, subprocess, sys, time
from pathlib import Path

import pytest

import autopilot_rehearse as rh
from conftest import git_env, requires_git, timeout_s

TOOL = Path(rh.__file__).resolve()
posix = pytest.mark.skipif(os.name != "posix", reason="signals and `ps` as the rehearsal's tests use them are POSIX")
pytestmark = [requires_git, pytest.mark.git]


def rehearse(*args, **env):
    """The rehearsal as a command: (exit code, output lines, workdir named on the first line)."""
    p = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8",
                       env=git_env(**env), timeout=timeout_s(600))
    lines = p.stdout.splitlines()
    return p.returncode, lines, workdir(lines)


def workdir(lines):
    m = re.match(r"rehearse: workdir (.+)$", lines[0]) if lines else None
    return Path(m.group(1)) if m else None


def processes_of(path):
    """The command lines of the processes whose command names PATH (the stub, a runner, a command in the clone)."""
    out = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True, encoding="utf-8").stdout
    return [ln for ln in out.splitlines() if str(path) in ln]


@pytest.fixture(scope="module")
def whole_run():
    """One full rehearsal, shared by the tests that read its result."""
    return rehearse()


@pytest.fixture(scope="module")
def kept_run():
    """One full rehearsal that keeps its directory, for the test that looks for what it left; removed after it."""
    code, lines, wd = rehearse("--keep")
    yield code, lines, wd
    if wd:
        shutil.rmtree(wd, ignore_errors=True)


def test_autopilot_rehearse_runs_the_whole_tick_with_the_stub(whole_run):
    code, lines, wd = whole_run
    assert code == 0, "\n".join(lines)
    assert lines[-1] == f"rehearse: ok ({len(rh.STEPS)} steps)", lines[-1]
    steps = [re.match(r"rehearse: step ([a-z-]+): ", ln).group(1) for ln in lines[1:-1]]
    assert steps == list(rh.STEPS), steps  # one line for each step, in order
    detail = {ln.split(": ", 2)[1].split()[1]: ln.split(": ", 2)[2] for ln in lines[1:-1]}
    assert "runner ended sprint-done" in detail["runner"] and "both done" in detail["landed"]
    assert "stop no-ready" in detail["bounds-stop"] and "by autopilot" in detail["start-gate"]
    assert not [ln for ln in lines if "FAILED" in ln]
    assert wd is not None and not wd.exists()  # a run that ends well removes its directory


def test_autopilot_rehearse_starts_from_an_empty_backlog_whatever_the_repository_holds(kept_run):
    """the clone drops the real backlog first: only the rehearsal's own items are in it, so a claimed or stalled item
    of the repository (selfcheck's claim-no-commit) cannot fail the run"""
    code, lines, wd = kept_run
    assert code == 0 and wd is not None, "\n".join(lines)
    clone = wd / "clone"
    log = subprocess.run(["git", "log", "--format=%s"], cwd=clone, capture_output=True, text=True, env=git_env()).stdout
    assert "an empty backlog for the rehearsal" in log, log
    titles = [re.search(r'"title":\s*"([^"]*)"', p.read_text(encoding="utf-8")).group(1)
              for p in (clone / "kb" / "_self" / "backlog").glob("*.json")]
    assert titles and all("ehearsal" in t for t in titles), titles


def test_autopilot_rehearse_selfcheck_a_busy_host_alone_is_named_not_failed():
    import types
    busy = "selfcheck: 1 failed, 1 unknown of 6 checks\nFAIL host: load 23.4 over 1.5 per core of 14 -> retry-narrower\nUNKNOWN main: no row\n"
    step = lambda text, code: rh.Rehearsal.step_selfcheck(types.SimpleNamespace(backlog=lambda *a, **k: (code, text)))  # noqa: E731
    assert "only the host check failed" in step(busy, 1)
    assert step("selfcheck: 0 failed, 0 unknown of 6 checks\n", 0).startswith("selfcheck: 0 failed")
    for text in (busy.replace("FAIL host", "FAIL claims"), busy + "FAIL hooks: gone\n"):  # planted: any other failure fails the step
        with pytest.raises(rh.Failed):
            step(text, 1)


def test_autopilot_rehearse_leaves_no_orphan_and_no_worktree(kept_run):
    code, lines, wd = kept_run
    assert code == 0 and wd is not None and (wd / "clone").is_dir(), "\n".join(lines)  # kept by --keep
    trees = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=wd / "clone", capture_output=True, text=True,
                           encoding="utf-8", env=git_env()).stdout
    assert [ln for ln in trees.splitlines() if ln.startswith("worktree ")] == [f"worktree {(wd / 'clone').resolve()}"], trees
    assert not list((wd / "clone" / ".claude" / "worktrees").glob("runner-*"))
    assert not list((wd / "hostlocks").glob("*.json"))  # the runner's record is removed
    if os.name == "posix":
        assert processes_of(wd) == []  # no stub, runner or command of the clone is still running


@pytest.mark.parametrize("step", rh.STEPS)
def test_autopilot_rehearse_planted_failure_at_each_step(step):
    code, lines, wd = rehearse(**{rh.FAIL_ENV: step})
    assert code == 1, "\n".join(lines)
    assert lines[-1] == f"rehearse: FAILED at step {step}: planted failure", lines[-1]
    ran = [ln.split(": ")[1].split()[1].rstrip(":") for ln in lines if ln.startswith("rehearse: step ")]
    assert ran == list(rh.STEPS[:rh.STEPS.index(step)]), ran  # the steps before it ran, none after it
    assert not [ln for ln in lines if ln.startswith("rehearse: ok")]
    assert wd is not None and not wd.exists()  # the failed run removed its directory


# ---------------------------------------------------------------- the step bound

def fake_rehearsal(tmp_path, monkeypatch, script):
    """A Rehearsal over a directory whose clone holds a stand-in `_tools/autopilot.py` that runs SCRIPT."""
    monkeypatch.setenv(rh.TIMEOUT_ENV, "1")
    r = rh.Rehearsal()
    r.tmp = tmp_path
    r.env = git_env()
    r.sprint = "SP-aaaaaaaa"
    (tmp_path / "clone" / "_tools").mkdir(parents=True)
    (tmp_path / "clone" / "_tools" / "autopilot.py").write_text(script, encoding="utf-8", newline="\n")
    return r


def pid_gone(pid, wait=5.0):
    end = time.monotonic() + wait
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.05)
    return False


@posix
def test_autopilot_rehearse_a_hung_runner_fails_the_step_and_its_process_is_ended(tmp_path, monkeypatch):
    pidfile = tmp_path / "pid"
    script = f"import os, time\nopen({str(pidfile)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)\n"
    r = fake_rehearsal(tmp_path, monkeypatch, script)
    t = time.monotonic()
    with pytest.raises(rh.Failed, match="ran past the step bound of 1s"):
        r.step_runner()
    assert time.monotonic() - t < 30  # the bound ended it, the script's minute was not awaited
    assert pid_gone(int(pidfile.read_text(encoding="utf-8")))


@posix
def test_autopilot_rehearse_a_command_past_the_bound_fails_and_is_ended(tmp_path, monkeypatch):
    pidfile = tmp_path / "pid"
    r = fake_rehearsal(tmp_path, monkeypatch, "")
    code = f"import os, time; open({str(pidfile)!r}, 'w').write(str(os.getpid())); time.sleep(60)"
    with pytest.raises(rh.Failed, match="step bound"):
        r.run([sys.executable, "-c", code], cwd=tmp_path)
    assert pid_gone(int(pidfile.read_text(encoding="utf-8")))


@posix
def test_autopilot_rehearse_a_runner_that_fails_is_named_with_its_cause(tmp_path, monkeypatch):
    r = fake_rehearsal(tmp_path, monkeypatch, "import sys\nprint('boom')\nsys.exit(1)\n")
    with pytest.raises(rh.Failed, match="the runner exited 1 .*boom"):
        r.step_runner()


# ---------------------------------------------------------------- signals

@posix
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_autopilot_rehearse_a_signal_ends_the_run_and_removes_everything(sig):
    """The stub waits a minute; the signal arrives while the runner runs it. The run ends at once: exit 1, the step named
    with the signal, the stub, the runner and the directory gone."""
    p = subprocess.Popen([sys.executable, str(TOOL)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", env=git_env(**{rh.PAUSE_ENV: "60"}), start_new_session=True)
    lines, wd = [], None
    try:
        deadline = time.monotonic() + timeout_s(300)
        for ln in p.stdout:
            lines.append(ln.rstrip("\n"))
            if ln.startswith("rehearse: workdir"):
                wd = workdir(lines)
            if ln.startswith("rehearse: step start:"):
                break
            assert time.monotonic() < deadline, lines
        end = time.monotonic() + timeout_s(60)  # the runner starts and the stub begins its wait
        while time.monotonic() < end and not any("claude_stub" in x for x in processes_of(wd)):
            time.sleep(0.1)
        assert any("claude_stub" in x for x in processes_of(wd)), lines  # the stub is running when the signal comes
        os.kill(p.pid, sig)  # the rehearsal alone, not its group: it ends its own children
        rest = p.stdout.read().splitlines()
        p.wait(timeout=timeout_s(60))
    finally:
        if p.poll() is None:
            p.kill()
    lines += rest
    assert p.returncode == 1, "\n".join(lines)
    assert lines[-1] == f"rehearse: FAILED at step runner: interrupted by {sig.name}", lines[-1]
    assert wd is not None and not wd.exists()
    assert processes_of(wd) == []
