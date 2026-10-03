"""The bound of the wait for the host main lock (kg_lock.main_lock; kb/_self/git.md, Two runners on one host). The tests
named main_lock_wait_is_bounded are the item's check: a live holder (a real sleeping process) makes a waiter give up
with MainLockTimeout naming its pid, clone, step and age, `land` and `sync` stop with exit 1 and that message.
Planted failures: a live holder (refused), a dead holder (cleared, not counted), a free lock, a garbage bound.
"""
import argparse, contextlib, datetime, os, subprocess, sys, time
from pathlib import Path

import pytest

import backlog, bl_testkit, kg_lock, kg_sync

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs
from bl_testkit import commit, sh


@pytest.fixture(autouse=True)
def host_dir(tmp_path, monkeypatch):
    d = tmp_path / "hostlocks"
    d.mkdir()
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(d))
    monkeypatch.setenv("KB_HOST_LOCK_POLL", "0.05")
    for name in (kg_lock.HELD_ENV, kg_lock.MAX_WAIT_ENV, "KB_TESTS_FAST", "KB_TEST_WORKERS"):
        monkeypatch.delenv(name, raising=False)
    return d


def stamp(minutes_ago=0):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def plant(host, pid, clone="/clone/hung", step="backlog.py land: fetch and rebase", started=None):
    (host / kg_lock.LOCK_NAME).write_text(
        f"pid={pid}\nclone={clone}\nstarted={started or stamp()}\nstep={step}\n", encoding="utf-8")


@contextlib.contextmanager
def live_process():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        yield p
    finally:
        p.terminate()
        p.wait(timeout=10)


def dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_main_lock_wait_is_bounded_and_names_the_live_holder(host_dir, monkeypatch, capsys):
    monkeypatch.setenv(kg_lock.MAX_WAIT_ENV, "1")
    with live_process() as p:
        plant(host_dir, p.pid, started=stamp(31))
        t0 = time.time()
        with pytest.raises(kg_lock.MainLockTimeout) as e:
            with kg_lock.main_lock("kbgit.py sync --push", "kbgit.py", poll=0.05, clone="/clone/waiter"):
                pytest.fail("the lock was taken from a live holder")
        assert time.time() - t0 < 10
    msg = str(e.value)
    assert msg == (f"host main lock still held by pid {p.pid} (clone /clone/hung, step backlog.py land: fetch and "
                   "rebase, age 31 min) after 1 s: blocked")
    assert "waiting for the host main lock held by pid" in capsys.readouterr().out
    assert (host_dir / kg_lock.LOCK_NAME).exists()  # the live holder's file is left alone


def test_main_lock_wait_is_bounded_module_constant_is_the_default(monkeypatch):
    assert kg_lock.MAIN_LOCK_MAX_WAIT_S == 1800
    assert kg_lock.max_wait() == 1800
    monkeypatch.setenv(kg_lock.MAX_WAIT_ENV, "2.5")
    assert kg_lock.max_wait() == 2.5
    for bad in ("", "abc", "0", "-3", "nan", "inf"):
        monkeypatch.setenv(kg_lock.MAX_WAIT_ENV, bad)
        assert kg_lock.max_wait() == 1800, bad
    monkeypatch.delenv(kg_lock.MAX_WAIT_ENV)
    monkeypatch.setattr(kg_lock, "MAIN_LOCK_MAX_WAIT_S", 7)
    assert kg_lock.max_wait() == 7


def test_main_lock_wait_is_bounded_only_for_a_live_holder_a_stale_one_is_cleared(host_dir, monkeypatch, capsys):
    monkeypatch.setenv(kg_lock.MAX_WAIT_ENV, "0.1")
    plant(host_dir, dead_pid())
    with kg_lock.main_lock("s", "t", poll=0.05) as path:
        assert f"pid={os.getpid()}" in Path(path).read_text(encoding="utf-8")
    assert "clearing a stale host main lock" in capsys.readouterr().out
    assert not (host_dir / kg_lock.LOCK_NAME).exists()


def test_main_lock_wait_is_bounded_a_free_lock_is_taken_at_once(host_dir, monkeypatch):
    monkeypatch.setenv(kg_lock.MAX_WAIT_ENV, "0.1")
    t0 = time.time()
    with kg_lock.main_lock("s", "t", poll=5) as path:
        assert Path(path).exists()
    assert time.time() - t0 < 2 and not (host_dir / kg_lock.LOCK_NAME).exists()


def test_main_lock_wait_is_bounded_a_holder_that_releases_in_time_lets_the_waiter_in(host_dir, monkeypatch):
    monkeypatch.setenv(kg_lock.MAX_WAIT_ENV, "30")
    with live_process() as p:
        plant(host_dir, p.pid)
        import threading
        threading.Timer(0.3, lambda: (host_dir / kg_lock.LOCK_NAME).unlink()).start()
        with kg_lock.main_lock("s", "t", poll=0.05) as path:
            assert f"pid={os.getpid()}" in Path(path).read_text(encoding="utf-8")


def test_main_lock_wait_is_bounded_age_reads_the_started_stamp():
    assert kg_lock.holder_age(stamp(31)) == "31 min"
    assert kg_lock.holder_age(stamp(0)) == "<1 min"
    assert kg_lock.holder_age("?") == "?"


def blocked(pid=4242):
    return kg_lock.MainLockTimeout(f"host main lock still held by pid {pid} (clone /clone/hung, step s, age 31 min) "
                                   "after 1800 s: blocked")


def test_main_lock_wait_is_bounded_land_stops_with_exit_1_and_the_message(sprint, monkeypatch, capsys):
    r, tk = sprint["repo"], sprint["tk"]
    commit(r, "plan")
    sh(r, "git", "branch", f"work/{tk}")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    sh(r, "git", "remote", "add", "origin", str(r / "nowhere"))

    def refuse(*a, **k):
        raise blocked()

    monkeypatch.setattr(kg_lock, "guarded", refuse)
    assert backlog.main(["--root", str(r), "land", tk]) == 1
    out = capsys.readouterr()
    text = out.out + out.err
    assert "land stopped at step fetch and rebase: host main lock still held by pid 4242" in text
    assert "age 31 min) after 1800 s: blocked" in text


def test_main_lock_wait_is_bounded_sync_stops_with_exit_1_and_the_message(tmp_path, monkeypatch, capsys):
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
    monkeypatch.setattr(kg_sync, "KB", str(clone))
    host = kg_sync.Host(audit=None, message=None, hooks_ok=lambda p: True)
    called = []
    monkeypatch.setattr(kg_sync, "sync_rounds", lambda a, r, h: called.append(1) or 0)

    def refuse(*a, **k):
        raise blocked()

    monkeypatch.setattr(kg_lock, "guarded", refuse)
    a = argparse.Namespace(remote="origin", branch="main", push=True, dry_run=False, session="", rerun=None)
    assert kg_sync.cmd_sync(a, host) == 1
    assert called == []
    assert ("kbgit.py sync: host main lock still held by pid 4242 (clone /clone/hung, step s, age 31 min) after "
            "1800 s: blocked") in capsys.readouterr().out
