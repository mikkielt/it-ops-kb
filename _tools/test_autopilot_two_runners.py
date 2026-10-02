"""Two sprint runners on one host (kb/_self/tools.md, The autopilot runner; kb/_self/git.md, Two runners on one host).
The tests named autopilot_two_runners_* are the item's checks, one group for each of its three behaviours:

- at most two runners live at once (autopilot.register_runner, over the records bl_base.live_runners reads): a third is
  refused naming the two, a record whose process is gone counts for nothing, a sprint a live runner holds is refused;
- `backlog.py start` refuses a sprint whose open items' touches overlap those a live runner of another sprint holds,
  naming the globs and the holder, and starts one that does not overlap or whose holder is gone;
- `land`'s fetch and rebase and `kbgit.py sync --push` hold the host's main lock (kg_lock), two holders never overlap,
  and the waiter names the holder.

Each has a planted failure: a third runner, an overlapping sprint, workers that skip the lock and so overlap.
"""
import json, os, subprocess, sys, threading, time
from pathlib import Path

import pytest

import autopilot, backlog, bl_base, bl_land, bl_testkit, kg_lock, kg_sync
from bl_testkit import argstr, b, commit, is_file, item, sh

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

TOOLS = Path(__file__).resolve().parent
OLD = "2020-01-01T00:00:00Z"


@pytest.fixture(autouse=True)
def host_dir(tmp_path, monkeypatch):
    """One host per test: the runners' records and the locks are in a directory of the test's own."""
    d = tmp_path / "hostlocks"
    d.mkdir()
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(d))
    monkeypatch.setenv("KB_HOST_LOCK_POLL", "0.05")
    monkeypatch.delenv(kg_lock.HELD_ENV, raising=False)  # a run inside sync's gate inherits the holder's pid: not the test's business
    return d


def record(host, pid, sprint_id, touches=(), started=OLD, clone="/clone/a"):
    (host / f"{bl_base.RUNNER_PREFIX}{pid}.json").write_text(json.dumps(
        {"pid": pid, "sprint": sprint_id, "clone": clone, "started": started, "touches": list(touches)}),
        encoding="utf-8")


def sp_id(n):
    return "SP-" + "abcdefgh"[n] * 8


# ---------------------------------------------------------------- behaviour 1: at most two runners

def test_autopilot_two_runners_a_third_is_refused_naming_the_two(host_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(bl_base, "pid_alive", lambda pid: pid in (4001, 4002, os.getpid()))
    record(host_dir, 4001, sp_id(0))
    record(host_dir, 4002, sp_id(1), clone="/clone/b")
    with pytest.raises(bl_base.Refused) as e:
        autopilot.runner_start(sp_id(2), None, tmp_path)  # refused before any git is asked
    msg = str(e.value)
    assert sp_id(0) in msg and sp_id(1) in msg and "4001" in msg and "4002" in msg and "/clone/b" in msg, msg
    assert not bl_base.runner_record_path(os.getpid()).exists()  # the refused start leaves no record
    assert {r["pid"] for r in bl_base.live_runners()} == {4001, 4002}


@pytest.mark.parametrize("others", range(0, 5))
def test_autopilot_two_runners_slot_goes_to_the_first_two_whatever_the_count(host_dir, monkeypatch, others):
    """The runner is let in exactly when fewer than two others live, whatever the number of others and their ages."""
    pids = [5000 + n for n in range(others)]
    monkeypatch.setattr(bl_base, "pid_alive", lambda pid: pid in pids or pid == os.getpid())
    for n, pid in enumerate(pids):
        record(host_dir, pid, sp_id(n))
    root = Path(host_dir)
    if others < bl_base.MAX_RUNNERS:
        path = autopilot.register_runner(root, "SP-zzzzzzzz")
        assert path.is_file() and json.loads(path.read_text(encoding="utf-8"))["sprint"] == "SP-zzzzzzzz"
    else:
        with pytest.raises(bl_base.Refused, match="already run"):
            autopilot.register_runner(root, "SP-zzzzzzzz")
        assert not bl_base.runner_record_path(os.getpid()).exists()


def test_autopilot_two_runners_a_runner_whose_process_is_gone_does_not_count(host_dir, monkeypatch):
    """Planted: two records, one of a dead process. A third is let in (and the dead record removed); with both alive
    it is refused, so the count reads the process and not the file."""
    monkeypatch.setattr(bl_base, "pid_alive", lambda pid: pid in (4001, os.getpid()))
    record(host_dir, 4001, sp_id(0))
    record(host_dir, 4002, sp_id(1))
    path = autopilot.register_runner(Path(host_dir), sp_id(2))
    assert path.is_file() and not (host_dir / f"{bl_base.RUNNER_PREFIX}4002.json").exists()
    path.unlink()
    monkeypatch.setattr(bl_base, "pid_alive", lambda pid: True)
    record(host_dir, 4002, sp_id(1))
    with pytest.raises(bl_base.Refused):
        autopilot.register_runner(Path(host_dir), sp_id(2))


def test_autopilot_two_runners_a_sprint_a_live_runner_holds_is_refused(host_dir, monkeypatch):
    monkeypatch.setattr(bl_base, "pid_alive", lambda pid: True)
    record(host_dir, 4001, sp_id(0))
    with pytest.raises(bl_base.Refused, match="already has a live runner"):
        autopilot.register_runner(Path(host_dir), sp_id(0))


# ---------------------------------------------------------------- behaviour 2: no overlapping sprints

def planned_sprint(repo, touch):
    """An approved sprint, not started, whose story's task carries the touches glob TOUCH."""
    b(repo, "new", "epic", "--title", "E2", "--goal", "g")
    ep = item(repo, "E2")["id"]
    b(repo, "new", "sprint", "--title", "S2", "--goal", "g")
    sp = item(repo, "S2")["id"]
    b(repo, "new", "story", "--title", "St2", "--parent", ep, "--sprint", sp, "--goal", "g")
    st = item(repo, "St2")["id"]
    b(repo, "new", "task", "--title", "Tk2", "--parent", st, "--goal", "g", "--touch", touch,
      "--check", argstr(is_file("src/a.txt")))
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    commit(repo, "plan")
    return sp


def test_autopilot_two_runners_start_refuses_overlapping_touches_naming_paths_and_holder(repo, host_dir):
    sp = planned_sprint(repo, "src/**")
    record(host_dir, os.getpid(), "SP-hhhhhhhh", touches=["src/a.txt", "docs/**"], clone="/clone/other")
    code, out = b(repo, "start", sp)
    assert code == 1, out
    assert "SP-hhhhhhhh" in out and "src/** meets src/a.txt" in out and "/clone/other" in out, out
    assert "docs/**" not in out and item(repo, "S2")["status"] == "planned"
    assert b(repo, "check")[0] in (0, 1)  # the refusal wrote nothing the check reads as a started sprint


@pytest.mark.parametrize("held", [["docs/**"], ["src2/x.md"], []])
def test_autopilot_two_runners_start_goes_on_when_nothing_overlaps(repo, host_dir, held):
    sp = planned_sprint(repo, "src/**")
    record(host_dir, os.getpid(), "SP-hhhhhhhh", touches=held)
    code, out = b(repo, "start", sp)
    assert code == 0, out
    assert item(repo, "S2")["status"] == "active"


def test_autopilot_two_runners_start_ignores_a_runner_that_is_gone_and_its_own_sprint(repo, host_dir):
    """Planted: the overlapping record belongs to a dead process (a pid no process has), then to the sprint itself."""
    sp = planned_sprint(repo, "src/**")
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    record(host_dir, dead.pid, "SP-hhhhhhhh", touches=["src/a.txt"])
    record(host_dir, os.getpid(), sp, touches=["src/a.txt"])
    code, out = b(repo, "start", sp)
    assert code == 0, out


# ---------------------------------------------------------------- behaviour 3: the main lock

HOLDER = """
import os, sys, time
sys.path.insert(0, {tools!r})
import kg_lock
os.environ.pop("PYTEST_CURRENT_TEST", None)
with kg_lock.main_lock({step!r}, "holder", poll=0.02):
    open({ready!r}, "w").write("1")
    while not os.path.exists({release!r}):
        time.sleep(0.02)
"""

WORKER = """
import os, sys, time
sys.path.insert(0, {tools!r})
import kg_lock
def work():
    with open({log!r}, "a") as f:
        f.write("start " + str(os.getpid()) + "\\n")
    time.sleep(0.25)
    with open({log!r}, "a") as f:
        f.write("end " + str(os.getpid()) + "\\n")
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
def test_autopilot_two_runners_main_lock_keeps_holders_apart_and_planted_unlocked_overlap(host_dir, tmp_path, n):
    """n workers each hold the lock for a quarter of a second: with the lock their critical sections never overlap;
    planted, the same workers without it do."""
    for locked in (True, False):
        log = tmp_path / f"log-{locked}.txt"
        procs = [subprocess.Popen([sys.executable, "-c", WORKER.format(tools=str(TOOLS), log=str(log), locked=locked)],
                                  env=env_for_child(host_dir)) for _ in range(n)]
        assert [p.wait(60) for p in procs] == [0] * n
        lines = log.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2 * n
        assert overlapped(lines) is (not locked), lines
    assert not (host_dir / kg_lock.LOCK_NAME).exists()  # every holder released it


def test_autopilot_two_runners_main_lock_waiter_names_the_holder_and_its_step(host_dir, tmp_path, capsys, monkeypatch):
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
        assert f"held by pid {holder.pid}" in out and "sync --push" in out and "host main lock" in out, out
        assert waited >= 0.3 and f"pid={os.getpid()}" in held and "step=backlog.py land: fetch and rebase" in held
    finally:
        release.write_text("1", encoding="utf-8")
        holder.wait(30)
    assert not (host_dir / kg_lock.LOCK_NAME).exists()


def test_autopilot_two_runners_main_lock_clears_a_dead_holder_and_the_test_lock_is_another_file(host_dir, capsys):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (host_dir / kg_lock.LOCK_NAME).write_text(f"pid={dead.pid}\nclone=/c\nstarted=x\nstep=s\n", encoding="utf-8")
    (host_dir / "kb-tests.lock").write_text(f"pid={os.getppid()}\nclone=/c\nstarted=x\n", encoding="utf-8")
    with kg_lock.main_lock("s", "t", poll=0.02):  # a live holder of the test lock does not hold this one
        pass
    assert "clearing a stale host main lock" in capsys.readouterr().out
    assert (host_dir / "kb-tests.lock").exists()


def test_autopilot_two_runners_main_lock_a_process_the_holder_starts_takes_no_second_lock(host_dir):
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


def test_autopilot_two_runners_land_fetch_and_rebase_hold_the_main_lock(sprint, host_dir, monkeypatch):
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


def test_autopilot_two_runners_sync_push_holds_the_main_lock_and_a_dry_run_or_no_push_does_not(
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


def test_autopilot_two_runners_main_lock_asked_while_holding_the_test_lock_is_refused(host_dir):
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
