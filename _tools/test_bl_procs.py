"""Tests of `backlog.py procs` (bl_procs.py): the inventory of the processes left in a clone's checkouts, its classes
(orphan, foreign), that nothing is ever signaled, and `land` naming the process that keeps it from removing a worker's
worktree. Real short-lived processes in a throwaway repository; a test skips
where the host cannot list working directories.
"""
import os
import re
import subprocess
import sys
import time

import pytest

import backlog  # first: it registers the other subcommands, and `procs` after them (bl_cli's registry keeps the order)
import bl_land
import bl_procs
from bl_testkit import TOOL
from conftest import git_env, timeout_s

SLEEP = "import time; time.sleep(120)"
# a process that starts a sleeper in a group of its own, prints its pid and exits: the sleeper's parent is gone
SPAWN = ("import subprocess, sys; p = subprocess.Popen([sys.executable, '-c', sys.argv[2]], cwd=sys.argv[1], "
         "start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); print(p.pid)")


def host_cannot():
    why = bl_procs.unsupported()
    if why is None and bl_procs.process_table() is None:
        why = "the process table could not be read"
    return why


needs_cwd = pytest.mark.skipif(host_cannot() is not None, reason=f"no process check on this host: {host_cannot()}")


def wait_for(cond, seconds=10.0):
    deadline = time.monotonic() + timeout_s(seconds)
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def alive(pid):
    return pid in (bl_procs.process_table() or {})


class Herd:
    """The processes a test starts; every one is ended when the test is over."""

    def __init__(self, base):
        self.base, self.children, self.pids = base, [], []

    def child(self, cwd, code=SLEEP):
        """A sleeper that is this process's child: its parent is alive."""
        p = subprocess.Popen([sys.executable, "-c", code], cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        self.children.append(p)
        self.pids.append(p.pid)
        assert wait_for(lambda: p.pid in (bl_procs.process_table() or {}))
        return p.pid

    def orphan(self, cwd, code=SLEEP):
        """A sleeper in a group of its own whose parent has exited: adopted by the system's reaper."""
        out = subprocess.run([sys.executable, "-c", SPAWN, str(cwd), code], capture_output=True, text=True, timeout=timeout_s(30))
        pid = int(out.stdout.split()[0])
        self.pids.append(pid)
        assert wait_for(lambda: pid in (tab := bl_procs.process_table() or {}) and bl_procs.orphaned(tab, pid)), "never orphaned"
        return pid

    def close(self):
        for pid in self.pids:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        for p in self.children:
            p.kill()
            p.wait()


@pytest.fixture
def herd(tmp_path):
    h = Herd(tmp_path)
    yield h
    h.close()


@pytest.fixture
def clone(tmp_path):
    """A throwaway git repository with a worktree directory under it: where the herd's processes run."""
    root = tmp_path / "clone"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, env=git_env())
    work = root / ".claude" / "worktrees" / "w1"
    work.mkdir(parents=True)
    return root.resolve(), work.resolve()


def kinds(root):
    procs, _, why = bl_procs.snapshot(str(root))
    assert procs is not None, why
    return {p["pid"]: p["kind"] for p in procs}



# ---------------------------------------------------------------- the inventory

@needs_cwd
def test_procs_inventory_orphans_classes_orphan_and_foreign(clone, herd, tmp_path):
    """A process whose parent is gone, in the main checkout or a worktree, is an orphan; one whose parent lives is
    foreign; one outside every checkout is not listed."""
    root, work = clone
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    foreign, foreign_wt = herd.child(root), herd.child(work)
    orphan, orphan_wt = herd.orphan(root), herd.orphan(work)
    outside = herd.child(elsewhere)
    got = kinds(root)
    assert got[orphan] == got[orphan_wt] == bl_procs.ORPHAN, got
    assert got[foreign] == got[foreign_wt] == bl_procs.FOREIGN, got
    assert outside not in got, "a process outside every checkout is not listed"


@needs_cwd
def test_procs_inventory_orphans_planted_blind_classifier_fails(clone, herd, monkeypatch):
    root, work = clone
    orphan = herd.orphan(work)
    assert kinds(root)[orphan] == bl_procs.ORPHAN
    monkeypatch.setattr(bl_procs, "orphaned", lambda tab, pid: False)  # planted: no parent is ever gone
    with pytest.raises(AssertionError):
        assert kinds(root)[orphan] == bl_procs.ORPHAN


@needs_cwd
def test_procs_inventory_orphans_prints_command_name_only(clone, herd, capsys):
    root, work = clone
    pid = herd.orphan(work, "import time; time.sleep(120)  # marker-argument-text")
    code = bl_procs.cmd_procs(backlog.Backlog(root), type("A", (), {})())
    out = capsys.readouterr().out
    assert code == 0 and f"pid {pid} " in out and " orphan " in out, out
    assert "marker-argument-text" not in out and "time.sleep" not in out, "arguments are never read"
    assert str(root) not in out and str(work) not in out, "paths are the checkout's name and what is under it"
    assert "in clone/.claude/worktrees/w1" in out, out


def test_procs_inventory_orphans_orphan_means_the_parent_is_gone():
    tab = {10: (1, 1, "a"), 11: (999, 1, "b"), 12: (10, 1, "c"), 13: (14, 1, "d"), 14: (1, 1, "systemd"), 15: (14, 1, "e")}
    assert bl_procs.orphaned(tab, 10) and bl_procs.orphaned(tab, 11) and not bl_procs.orphaned(tab, 12)
    assert bl_procs.orphaned(tab, 15), "a parent that only adopts orphans (systemd) is no parent"
    tab[14] = (1, 1, "bash")
    assert not bl_procs.orphaned(tab, 15)


def test_procs_inventory_orphans_a_host_that_cannot_list_says_so(clone, monkeypatch, capsys):
    root, _ = clone
    monkeypatch.setattr(bl_procs, "unsupported", lambda: "Windows does not expose a process's working directory")
    assert bl_procs.cmd_procs(backlog.Backlog(root), type("A", (), {})()) == 0
    out = capsys.readouterr().out
    assert "cannot list processes by working directory on this host (Windows" in out, out


def test_procs_inventory_orphans_age_text():
    assert [bl_procs.age_text(s) for s in (-5, 0, 59, 60, 3599, 3600, 7500, 86400, 90000)] == [
        "0s", "0s", "59s", "1m", "59m", "1h00m", "2h05m", "1d00h", "1d01h"]


@needs_cwd
def test_procs_names_orphans_never_signals_through_the_command(clone, herd):
    """BG-xwolxdi6: the command lists an orphan and a foreign process, takes no --record or --end (nothing recorded
    them since the autopilot was retired), and leaves both running."""
    root, work = clone
    orphan, foreign = herd.orphan(work), herd.child(root)

    def procs(*args):
        p = subprocess.run([sys.executable, str(TOOL), "--root", str(root), "procs", *args], capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout_s(60), cwd=str(root.parent))
        return p.returncode, p.stdout + p.stderr

    code, out = procs()
    assert code == 0 and f"pid {orphan} " in out and " orphan " in out and f"pid {foreign} " in out, out
    assert "nothing is signaled" in out, out
    for gone in (["--end"], ["--record", str(orphan)], ["--grace", "1"]):
        assert procs(*gone)[0] == 2, gone
    assert alive(orphan) and alive(foreign), "nothing is ever signaled"


# ---------------------------------------------------------------- land names the process it will not remove a worktree over

@needs_cwd
def test_land_names_pid_of_process_in_worktree(tmp_path, herd, monkeypatch):
    """`land` refuses to remove a finished worker's worktree while a process runs in it, and names each pid and command
    (`backlog.release_worker_worktree` is the refusal)."""
    repo = tmp_path / "repo"
    env = git_env()

    def git(*args, cwd=repo):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)

    repo.mkdir()
    git("init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-q", "-m", "one")
    path = repo / ".claude" / "worktrees" / "agent-x"
    git("worktree", "add", "-q", "-b", "work/TK-xxxxxxxx", str(path))
    lock = "claude agent agent-x (pid 1)"
    git("worktree", "lock", "--reason", lock, str(path))
    child = herd.child(path.resolve())
    other = bl_land.checked_out_elsewhere(repo, "work/TK-xxxxxxxx")
    assert other is not None and other[1] == lock
    why = bl_land.release_worker_worktree(repo, *other)
    assert why and re.search(rf"pid {child} \(\S+\)", why) and "a process still runs there" in why, why
    assert path.exists(), "the worktree stays while a process runs in it"
    # the same process, as `procs` lists it: a foreign one in the worker's worktree
    assert kinds(repo)[child] == bl_procs.FOREIGN
    # planted: a process check blind to it removes the worktree, and the assertions above catch it
    monkeypatch.setattr(bl_land, "live_processes", lambda p: ([], None))
    blind = bl_land.release_worker_worktree(repo, *other)
    with pytest.raises(AssertionError):
        assert blind and f"pid {child} (" in blind
    assert not path.exists()
