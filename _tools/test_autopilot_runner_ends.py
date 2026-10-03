"""A sprint runner that is ended from outside (autopilot.py): SIGTERM and SIGHUP end the child's process tree and write a
status with the signal as its cause, `status` lists a `running` record no live runner holds as ended in error, and
`runner reset` frees a worktree a start refused as dirty or diverged. The tests named autopilot_runner_ends_cleanly are
the bug's checks. No real signal reaches another process: the runner's own signal is raised in the test's process, and a
planted child that outlives its tree ends by itself after a few seconds."""
import json, os, signal, sys, threading, time

import pytest

import autopilot, bl_base
from conftest import Repo, git_env
from test_autopilot import World, SP, T1, stream

posix_main_thread = pytest.mark.skipif(os.name != "posix" or threading.current_thread() is not threading.main_thread(),
                                       reason="the runner's signal handlers are POSIX and installed from the main thread")

KID = '''import os, subprocess, sys, time
life = os.environ["FAKE_LIFE"]
kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(" + life + ")"])
open(os.environ["FAKE_PIDS"], "w", encoding="utf-8").write(str(os.getpid()) + " " + str(kid.pid))
sys.stdout.write('{"type": "system", "subtype": "init"}\\n')
sys.stdout.flush()
time.sleep(float(life))
'''


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def alive_soon_gone(pid, wait=5.0):
    """Whether PID still runs after up to WAIT seconds (an orphan is reaped a moment after its group is killed)."""
    end = time.monotonic() + wait
    while time.monotonic() < end:
        if not bl_base.pid_alive(pid):
            return False
        time.sleep(0.05)
    return bl_base.pid_alive(pid)


class SignalsAtFirstLine:
    """The run's open stream file; the first line written to it raises SIG in this process, as a kill of the runner."""

    def __init__(self, f, sig):
        self.f, self.sig = f, sig

    def write(self, line):
        self.f.write(line)
        self.f.flush()
        signal.raise_signal(self.sig)

    def flush(self):
        self.f.flush()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.f.close()


def kill_the_runner(world, sig, life="60"):
    """Run the sprint against a child that starts a grandchild and then waits LIFE seconds; SIG reaches the runner at the
    child's first line. Returns (exit code, the child's and the grandchild's pids)."""
    script = world.tmp / "kid_claude.py"
    script.write_text(KID, encoding="utf-8", newline="\n")
    pids = world.tmp / "pids.txt"
    world.mp.setattr(autopilot, "CLAUDE", [sys.executable, str(script)])
    world.mp.setenv("FAKE_LIFE", life)
    world.mp.setenv("FAKE_PIDS", str(pids))
    real = autopilot.open_stream
    world.mp.setattr(autopilot, "open_stream", lambda d, stamp: (lambda n, f: (n, SignalsAtFirstLine(f, sig)))(*real(d, stamp)))
    t = time.monotonic()
    code = world.start()
    assert time.monotonic() - t < 30  # the child waits a minute: it was ended, not awaited
    child, grandchild = (int(x) for x in pids.read_text(encoding="utf-8").split())
    return code, child, grandchild


# ---------------------------------------------------------------- a signal ends the child's tree and writes the status

@posix_main_thread
@pytest.mark.parametrize("sig", [signal.SIGTERM, getattr(signal, "SIGHUP", signal.SIGTERM)])
def test_autopilot_runner_ends_cleanly_on_a_signal_with_the_tree_ended_and_a_status(world, sig):
    before = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
    code, child, grandchild = kill_the_runner(world, sig)
    st = world.status()
    assert code == 1 and st["cause"] == "error" and sig.name in st["detail"] and st["ended"]
    assert not alive_soon_gone(child) and not alive_soon_gone(grandchild)  # the process tree is gone, not just the child
    assert not bl_base.runner_record_path(os.getpid()).exists()  # the host slot is free again
    assert {s: signal.getsignal(s) for s in before} == before  # the handlers that were there are back
    assert world.streams()[0].read_text(encoding="utf-8").startswith('{"type": "system"')  # what arrived was kept


@posix_main_thread
def test_autopilot_runner_ends_cleanly_a_planted_tree_left_alive_fails_the_check(world, monkeypatch):
    """With end_tree reduced to killing the child alone, the grandchild is still there: the check above refuses that."""
    monkeypatch.setattr(autopilot, "end_tree", lambda proc: proc.kill())
    code, child, grandchild = kill_the_runner(world, signal.SIGTERM, life="4")
    assert world.status()["cause"] == "error" and code == 1
    assert bl_base.pid_alive(grandchild)  # it ends by itself after its few seconds


@posix_main_thread
def test_autopilot_runner_ends_cleanly_the_handlers_are_installed_ignore_a_second_signal_and_are_restored():
    before = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
    with autopilot.ends_on_signals():
        for sig in before:
            assert signal.getsignal(sig) not in (before[sig], signal.SIG_IGN)
        handler = signal.getsignal(signal.SIGTERM)
        with pytest.raises(autopilot.RunnerEnded) as e:
            handler(signal.SIGTERM, None)
        assert e.value.name == "SIGTERM"
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_IGN and signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
    assert {s: signal.getsignal(s) for s in before} == before


def test_autopilot_runner_ends_cleanly_outside_the_main_thread_installs_nothing_and_does_not_fail():
    out = {}

    def body():
        with autopilot.ends_on_signals():
            out["inside"] = True

    t = threading.Thread(target=body)
    t.start()
    t.join(10)
    assert out == {"inside": True}


# ---------------------------------------------------------------- status: a record nothing holds ended in error

def sealed(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "hostlocks"))
    (tmp_path / "hostlocks").mkdir()
    return tmp_path / "clone"


def plant_status(root, sprint, **kw):
    d = autopilot.cache_dir(root, sprint)
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(json.dumps({"sprint": sprint, **kw}), encoding="utf-8")


@pytest.mark.parametrize("pid", [999999, 1234567, 0, "x", None])
def test_autopilot_runner_ends_cleanly_status_shows_a_running_record_no_live_runner_holds_as_ended_error(tmp_path, monkeypatch, pid):
    root = sealed(tmp_path, monkeypatch)
    plant_status(root, "SP-aaaaaaaa", cause="running", pid=pid)
    assert autopilot.runner_lines(str(root), 9) == ["runners 1: SP-aaaaaaaa ended error"]


def test_autopilot_runner_ends_cleanly_status_keeps_a_live_runner_and_the_causes_of_ended_runs(tmp_path, monkeypatch):
    """The planted wrong version, which calls every `running` record dead, fails here: the live one stays alive."""
    root = sealed(tmp_path, monkeypatch)
    plant_status(root, "SP-aaaaaaaa", cause="running", pid=os.getpid())
    plant_status(root, "SP-bbbbbbbb", cause="blocked")
    plant_status(root, "SP-cccccccc", cause="running", pid=999999)
    bl_base.runner_record_path(os.getpid()).write_text(
        json.dumps({"pid": os.getpid(), "sprint": "SP-aaaaaaaa", "clone": str(root), "started": "2026-01-01T00:00:00Z"}), encoding="utf-8")
    (line,) = autopilot.runner_lines(str(root), 9)
    assert line == f"runners 3: SP-aaaaaaaa pid {os.getpid()} alive worktree clone, SP-cccccccc ended error, SP-bbbbbbbb ended blocked"


def test_autopilot_runner_ends_cleanly_the_stale_listing_reads_and_writes_nothing(tmp_path, monkeypatch):
    root = sealed(tmp_path, monkeypatch)
    plant_status(root, "SP-aaaaaaaa", cause="running", pid=999999)
    path = autopilot.cache_dir(root, "SP-aaaaaaaa") / "status.json"
    text = path.read_text(encoding="utf-8")
    autopilot.runner_lines(str(root), 9)
    assert path.read_text(encoding="utf-8") == text and json.loads(text)["cause"] == "running"


# ---------------------------------------------------------------- recovery from a refused start

def refused(world, capsys, monkeypatch):
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "start", SP]) == 2
    return capsys.readouterr().err


def make_dirty(world, n):
    for i in range(n):
        (world.wt() / f"stray{i}.txt").write_text(f"x{i}\n", encoding="utf-8")
    (world.wt() / "kb" / "_self" / "backlog" / f"{T1}.json").write_text("{}\n", encoding="utf-8")  # a tracked file, modified


def make_diverged(world):
    wt = Repo(world.wt(), git_env())
    wt.git("commit", "-q", "--allow-empty", "-m", "local only")
    world.repo.write("kb/y.md", "y\n")
    world.commit("remote")
    world.repo.git("push", "origin", "main")
    return wt.rev("HEAD")


@pytest.mark.parametrize("n", [0, 1, 7, 8, 9, 25])
def test_autopilot_runner_ends_cleanly_reset_frees_a_dirty_worktree_and_keeps_its_files_in_a_stash(world, capsys, monkeypatch, n):
    world.stream(stream())
    world.start()
    make_dirty(world, n)
    assert "uncommitted" in refused(world, capsys, monkeypatch)  # the failure the reset recovers from
    assert autopilot.main(["runner", "reset", SP]) == 0
    out = capsys.readouterr().out
    assert f"{n + 1} uncommitted files" in out and "stash" in out and "afresh" in out
    stash = world.repo.git("stash", "list")
    assert f"autopilot reset {SP}" in stash
    kept = world.repo.git("stash", "show", "--include-untracked", "--name-only", "stash@{0}").split()
    assert sorted(kept) == sorted([f"kb/_self/backlog/{T1}.json", *(f"stray{i}.txt" for i in range(n))])
    assert world.start() == 0 and world.start() == 0  # the refusal does not come back on the next starts


def test_autopilot_runner_ends_cleanly_reset_keeps_a_diverged_branch_and_the_next_start_is_afresh(world, capsys, monkeypatch):
    world.stream(stream())
    world.start()
    local = make_diverged(world)
    assert "by hand" in refused(world, capsys, monkeypatch)
    assert autopilot.main(["runner", "reset", SP]) == 0
    out = capsys.readouterr().out
    assert "diverged" in out and "stale/" + SP in out
    stale = [b.strip() for b in world.repo.git("branch", "--list", "stale/*").splitlines()]
    assert len(stale) == 1 and world.repo.rev(stale[0]) == local  # the local commit is on a branch, not lost
    assert not world.wt().exists()
    assert world.start() == 0
    assert Repo(world.wt(), git_env()).rev("HEAD") == world.origin_main() and world.status()["start_ref"] == world.origin_main()


def test_autopilot_runner_ends_cleanly_reset_of_a_dirty_and_diverged_worktree_keeps_both(world, capsys, monkeypatch):
    world.stream(stream())
    world.start()
    make_dirty(world, 2)
    local = make_diverged(world)
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "reset", SP]) == 0
    out = capsys.readouterr().out
    assert "uncommitted" in out and "stale/" in out
    assert world.repo.rev(world.repo.git("branch", "--list", "stale/*").strip()) == local
    assert "stray0.txt" in world.repo.git("stash", "show", "--include-untracked", "--name-only", "stash@{0}")
    assert world.start() == 0


def test_autopilot_runner_ends_cleanly_reset_leaves_a_clean_or_ahead_worktree_and_a_missing_one(world, capsys, monkeypatch):
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "reset", SP]) == 0 and "no runner worktree" in capsys.readouterr().out
    world.stream(stream())
    world.start()
    wt = Repo(world.wt(), git_env())
    wt.git("commit", "-q", "--allow-empty", "-m", "claim")  # ahead of origin/main: a start keeps it
    head = wt.rev("HEAD")
    assert autopilot.main(["runner", "reset", SP]) == 0 and "nothing to reset" in capsys.readouterr().out
    assert wt.rev("HEAD") == head and world.repo.git("stash", "list") == "" and world.repo.git("branch", "--list", "stale/*") == ""


def test_autopilot_runner_ends_cleanly_reset_is_refused_while_a_live_runner_holds_the_sprint(world, capsys, monkeypatch):
    world.stream(stream())
    world.start()
    make_dirty(world, 1)
    bl_base.runner_record_path(os.getpid()).write_text(
        json.dumps({"pid": os.getpid(), "sprint": SP, "clone": str(world.root), "started": "2026-01-01T00:00:00Z"}), encoding="utf-8")
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "reset", SP]) == 2
    assert "live runner" in capsys.readouterr().err
    assert (world.wt() / "stray0.txt").exists() and world.repo.git("stash", "list") == ""  # nothing was touched


@pytest.mark.parametrize("args", [["SP-short"], ["../x"], [""], []])
def test_autopilot_runner_ends_cleanly_reset_a_bad_argument_is_a_usage_error(args):
    with pytest.raises(SystemExit) as e:
        autopilot.main(["runner", "reset", *args])
    assert e.value.code == 2
