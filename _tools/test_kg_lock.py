"""The host's main lock (kg_lock; kb/_self/git.md, Two runners on one host): two holders never overlap (planted: workers
that skip it do), the waiter names the holder and its step, a dead holder's lock is cleared, a process the holder
starts takes no second lock, `land`'s fetch and rebase and `kbgit.py sync --push` hold it while `--dry-run` and a
sync without `--push` do not, and asking it while holding the host test lock is refused (LockOrderError). These guard
the live behaviour test_autopilot_two_runners.py held before the autopilot's retirement removed it (BG-m4pixy3p).
"""
import os, subprocess, sys, threading, time
from pathlib import Path

import pytest

import backlog, bl_land, bl_testkit, kg_lock, kg_sync
from bl_testkit import commit, sh

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

TOOLS = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def host_dir(tmp_path, monkeypatch):
    """One host per test: the locks are in a directory of the test's own."""
    d = tmp_path / "hostlocks"
    d.mkdir()
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(d))
    monkeypatch.setenv("KB_HOST_LOCK_POLL", "0.05")
    monkeypatch.delenv(kg_lock.HELD_ENV, raising=False)  # a run inside sync's gate inherits the holder's pid: not the test's business
    return d


HOLDER = """
import os, sys, time
sys.path.insert(0, {tools!r})
import kg_lock
os.environ.pop("PYTEST_CURRENT_TEST", None)
with kg_lock.main_lock({step!r}, "holder", poll=0.02):
    with open({ready!r} + ".tmp", "w") as f:  # its own pid: on Windows Popen.pid is the venv launcher's
        f.write(str(os.getpid()))
    os.replace({ready!r} + ".tmp", {ready!r})
    while not os.path.exists({release!r}):
        time.sleep(0.02)
"""

WORKER = """
import os, sys, time
sys.path.insert(0, {tools!r})
import kg_lock
def work():  # a file per worker: appends of several processes to one file lose lines on Windows
    with open({log!r} + "-" + str(os.getpid()), "a") as f:
        f.write(str(time.time_ns()) + " start " + str(os.getpid()) + "\\n")
        f.flush()
        time.sleep(0.25)
        f.write(str(time.time_ns()) + " end " + str(os.getpid()) + "\\n")
if {locked!r}:
    with kg_lock.main_lock("worker", "worker", poll=0.02):
        work()
else:
    work()
"""


def wait_for(path, seconds=15):
    end = time.time() + seconds
    while not os.path.exists(path):
        assert time.time() < end, f"{path} did not appear"
        time.sleep(0.02)


def env_for_child(host_dir):
    return {**os.environ, "KB_HOST_LOCK_DIR": str(host_dir), "KB_HOST_LOCK_POLL": "0.02"}


def overlapped(lines):
    """True when a `start` follows another worker's `start` before its `end`: two were inside at once."""
    inside = 0
    for ln in lines:
        inside += 1 if ln.startswith("start") else -1
        if inside > 1:
            return True
    return False


@pytest.mark.parametrize("n", [2, 3, 5])
def test_kg_lock_main_lock_keeps_holders_apart_and_planted_unlocked_overlap(host_dir, tmp_path, n):
    """n workers each hold the lock for a quarter of a second: with the lock their critical sections never overlap;
    planted, the same workers without it do."""
    for locked in (True, False):
        log = tmp_path / f"log-{locked}.txt"
        procs = [subprocess.Popen([sys.executable, "-c", WORKER.format(tools=str(TOOLS), log=str(log), locked=locked)],
                                  env=env_for_child(host_dir)) for _ in range(n)]
        assert [p.wait(60) for p in procs] == [0] * n
        stamped = [ln.split(" ", 1) for f in tmp_path.glob(f"{log.name}-*")
                   for ln in f.read_text(encoding="utf-8").splitlines()]
        lines = [ln for _, ln in sorted(stamped, key=lambda s: int(s[0]))]
        assert len(lines) == 2 * n
        assert overlapped(lines) is (not locked), lines
    assert not (host_dir / kg_lock.LOCK_NAME).exists()  # every holder released it


def test_kg_lock_main_lock_waiter_names_the_holder_and_its_step(host_dir, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    ready, release = tmp_path / "ready", tmp_path / "release"
    holder = subprocess.Popen([sys.executable, "-c", HOLDER.format(tools=str(TOOLS), step="sync --push",
                                                                   ready=str(ready), release=str(release))],
                              env=env_for_child(host_dir))
    try:
        wait_for(ready)
        threading.Timer(0.4, release.write_text, ["1"]).start()
        started = time.time()
        with kg_lock.main_lock("backlog.py land: fetch and rebase", "backlog.py", poll=0.02, clone="/clone/b"):
            waited = time.time() - started
            held = (host_dir / kg_lock.LOCK_NAME).read_text(encoding="utf-8")
        out = capsys.readouterr().out
        assert f"held by pid {ready.read_text(encoding='utf-8')}" in out and "sync --push" in out and "host main lock" in out, out
        assert waited >= 0.3 and f"pid={os.getpid()}" in held and "step=backlog.py land: fetch and rebase" in held
    finally:
        release.write_text("1", encoding="utf-8")
        holder.wait(30)
    assert not (host_dir / kg_lock.LOCK_NAME).exists()


def test_kg_lock_main_lock_clears_a_dead_holder_and_the_test_lock_is_another_file(host_dir, capsys):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (host_dir / kg_lock.LOCK_NAME).write_text(f"pid={dead.pid}\nclone=/c\nstarted=x\nstep=s\n", encoding="utf-8")
    (host_dir / "kb-tests.lock").write_text(f"pid={os.getppid()}\nclone=/c\nstarted=x\n", encoding="utf-8")
    with kg_lock.main_lock("s", "t", poll=0.02):  # a live holder of the test lock does not hold this one
        pass
    assert "clearing a stale host main lock" in capsys.readouterr().out
    assert (host_dir / "kb-tests.lock").exists()


def test_kg_lock_main_lock_a_process_the_holder_starts_takes_no_second_lock(host_dir):
    with kg_lock.main_lock("outer", "t", poll=0.02) as path:
        child = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {str(TOOLS)!r}); import kg_lock\n"
             "with kg_lock.main_lock('inner', 'child', poll=0.02): print('in')"],
            env=env_for_child(host_dir), capture_output=True, text=True, timeout=30)
        assert child.returncode == 0 and child.stdout.strip() == "in", child.stderr
        assert Path(path).exists()  # the child did not release the holder's lock
    assert not Path(path).exists()
    assert kg_lock.HELD_ENV not in os.environ


def test_kg_lock_land_fetch_and_rebase_hold_the_main_lock(sprint, host_dir, monkeypatch):
    """land's fetch runs while this process holds the lock file; a stop there releases it. Planted: guarded() that
    holds nothing leaves no lock file at the fetch."""
    repo, tk = sprint["repo"], sprint["tk"]
    commit(repo, "plan")
    sh(repo, "git", "branch", f"work/{tk}")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    seen = []

    def fetch(root, step, *args):
        text = (host_dir / kg_lock.LOCK_NAME).read_text(encoding="utf-8") if (host_dir / kg_lock.LOCK_NAME).exists() else ""
        seen.append(f"pid={os.getpid()}" in text)
        raise bl_land.land_stop(step, "planted stop")

    monkeypatch.setattr(bl_land, "land_git", fetch)
    sh(repo, "git", "remote", "add", "origin", str(repo / "nowhere"))
    assert backlog.main(["--root", str(repo), "land", tk]) == 1
    assert seen == [True] and not (host_dir / kg_lock.LOCK_NAME).exists()
    monkeypatch.setattr(kg_lock, "main_lock", lambda *a, **k: __import__("contextlib").nullcontext())
    seen.clear()
    assert backlog.main(["--root", str(repo), "land", tk]) == 1
    assert seen == [False]


def test_kg_lock_sync_push_holds_the_main_lock_and_a_dry_run_or_no_push_does_not(
        host_dir, tmp_path, monkeypatch):
    clone = tmp_path / "clone"
    clone.mkdir()
    sh(clone, "git", "init", "-q", "-b", "main")
    sh(clone, "git", "config", "user.email", "agent@example.com")
    sh(clone, "git", "config", "user.name", "agent")
    (clone / "f.txt").write_text("f\n", encoding="utf-8")
    sh(clone, "git", "add", "-A")
    sh(clone, "git", "commit", "-qm", "init")
    remote = tmp_path / "remote.git"
    sh(tmp_path, "git", "init", "-q", "--bare", str(remote))
    sh(clone, "git", "remote", "add", "origin", str(remote))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(kg_sync, "KB", str(clone))
    host = kg_sync.Host(audit=None, message=None, hooks_ok=lambda p: True)
    seen = []

    def rounds(a, r, h):
        lock = host_dir / kg_lock.LOCK_NAME
        seen.append(lock.exists() and f"pid={os.getpid()}" in lock.read_text(encoding="utf-8"))
        r["rerun"] = 0  # no report to print: the run reads as a re-run's
        return 0

    monkeypatch.setattr(kg_sync, "sync_rounds", rounds)
    import argparse

    def run(push, dry):
        a = argparse.Namespace(remote="origin", branch="main", push=push, dry_run=dry, session="", rerun=None)
        return kg_sync.cmd_sync(a, host)

    assert run(True, False) == 0 and seen == [True]
    assert not (host_dir / kg_lock.LOCK_NAME).exists()
    assert run(False, False) == 0 and run(True, True) == 0 and seen == [True, False, False]


def test_kg_lock_main_lock_asked_while_holding_the_test_lock_is_refused(host_dir):
    """Planted: the reverse order (test lock, then main lock) is refused, naming the rule, and takes no lock; the
    fixed order (main, then test) works."""
    import tests as tests_py
    with kg_lock.main_lock("first", "t", poll=0.02):
        with tests_py.host_lock("t", poll=0.02):
            pass
    assert not (host_dir / kg_lock.LOCK_NAME).exists() and not (host_dir / tests_py.HOST_LOCK_NAME).exists()
    with tests_py.host_lock("t", poll=0.02):
        with pytest.raises(kg_lock.LockOrderError, match="before the host test lock"):
            with kg_lock.main_lock("second", "t", poll=0.02):
                pass
        assert not (host_dir / kg_lock.LOCK_NAME).exists()
