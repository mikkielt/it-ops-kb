"""Tests of `backlog.py procs` (bl_procs.py): the inventory of the processes left in a clone's checkouts, its classes
(owned, owned orphan, orphan, foreign), the end of an owned orphan and of nothing else, and `land` naming the process
that keeps it from removing a worker's worktree. Real short-lived processes in a throwaway repository; a test skips
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
# the same with a child of its own: the leader prints its child's pid and sleeps
LEADER = ("import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
          "print(p.pid, flush=True); time.sleep(120)")


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


def started(pid):
    return bl_procs.process_table()[pid][1]


# ---------------------------------------------------------------- the inventory

@needs_cwd
def test_procs_inventory_orphans_classes_owned_orphan_and_foreign(clone, herd, tmp_path):
    root, work = clone
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    owned, foreign = herd.child(work), herd.child(root)
    owned_orphan, orphan = herd.orphan(work), herd.orphan(root)
    outside = herd.child(elsewhere)
    bl_procs.record(str(root), [owned, owned_orphan])
    got = kinds(root)
    assert got[owned] == bl_procs.OWNED and got[owned_orphan] == bl_procs.OWNED_ORPHAN, got
    assert got[orphan] == bl_procs.ORPHAN and got[foreign] == bl_procs.FOREIGN, got
    assert outside not in got, "a process outside every checkout is not listed"


@needs_cwd
def test_procs_inventory_orphans_planted_blind_classifier_fails(clone, herd, monkeypatch):
    root, work = clone
    owned_orphan = herd.orphan(work)
    bl_procs.record(str(root), [owned_orphan])
    assert kinds(root)[owned_orphan] == bl_procs.OWNED_ORPHAN
    monkeypatch.setattr(bl_procs, "load_records", lambda root: [])  # planted: nothing is recorded
    with pytest.raises(AssertionError):
        assert kinds(root)[owned_orphan] == bl_procs.OWNED_ORPHAN


@needs_cwd
def test_procs_inventory_orphans_a_reused_pid_is_not_owned(clone, herd):
    root, work = clone
    pid = herd.orphan(work)
    bl_procs.record(str(root), [pid])
    rows = bl_procs.load_records(str(root))
    assert [r["pid"] for r in rows] == [pid]
    for shift in (1, 60, 86400):  # a record of another process that had this pid: the start time differs
        bl_procs.save_records(str(root), [dict(rows[0], start=rows[0]["start"] - shift)])
        assert kinds(root)[pid] == bl_procs.ORPHAN, shift


@needs_cwd
def test_procs_inventory_orphans_prints_command_name_only(clone, herd, capsys):
    root, work = clone
    pid = herd.orphan(work, "import time; time.sleep(120)  # marker-argument-text")
    bl_procs.record(str(root), [pid])
    code = bl_procs.cmd_procs(backlog.Backlog(root), type("A", (), {"record": [], "end": False, "grace": None})())
    out = capsys.readouterr().out
    assert code == 0 and f"pid {pid} " in out and "owned orphan" in out, out
    assert "marker-argument-text" not in out and "time.sleep" not in out, "arguments are never read"
    assert str(root) not in out and str(work) not in out, "paths are the checkout's name and what is under it"
    assert "in clone/.claude/worktrees/w1" in out, out


def test_procs_inventory_orphans_record_refuses_a_dead_pid_and_this_process(tmp_path):
    tab = {os.getpid(): (100, 5, "python"), 100: (1, 4, "zsh"), 200: (1, 6, "sleep")}
    root = tmp_path / "r"
    root.mkdir()
    for pid, why in ((300, "no process runs"), (os.getpid(), "never recorded"), (100, "never recorded"), (1, "never recorded")):
        with pytest.raises(bl_procs.Refused, match=why):
            bl_procs.record(str(root), [pid], tab)
    assert bl_procs.record(str(root), [200], tab) == ["recorded pid 200 (sleep) as started by the autopilot"]
    assert [(r["pid"], r["start"], r["comm"]) for r in bl_procs.load_records(str(root))] == [(200, 6, "sleep")]
    # a record whose process is gone is dropped by the next one
    tab2 = {os.getpid(): (100, 5, "python"), 100: (1, 4, "zsh"), 201: (1, 7, "node")}
    bl_procs.record(str(root), [201], tab2)
    assert [r["pid"] for r in bl_procs.load_records(str(root))] == [201]


def test_procs_inventory_orphans_orphan_means_the_parent_is_gone():
    tab = {10: (1, 1, "a"), 11: (999, 1, "b"), 12: (10, 1, "c"), 13: (14, 1, "d"), 14: (1, 1, "systemd"), 15: (14, 1, "e")}
    assert bl_procs.orphaned(tab, 10) and bl_procs.orphaned(tab, 11) and not bl_procs.orphaned(tab, 12)
    assert bl_procs.orphaned(tab, 15), "a parent that only adopts orphans (systemd) is no parent"
    tab[14] = (1, 1, "bash")
    assert not bl_procs.orphaned(tab, 15)


def test_procs_inventory_orphans_a_host_that_cannot_list_says_so(clone, monkeypatch, capsys):
    root, _ = clone
    monkeypatch.setattr(bl_procs, "unsupported", lambda: "Windows does not expose a process's working directory")
    args = type("A", (), {"record": [], "end": False, "grace": None})
    assert bl_procs.cmd_procs(backlog.Backlog(root), args()) == 0
    out = capsys.readouterr().out
    assert "cannot list processes by working directory on this host (Windows" in out, out
    args.end = True  # an end that cannot check did not happen: exit 1, nothing signaled
    assert bl_procs.cmd_procs(backlog.Backlog(root), args()) == 1
    assert "cannot check this host" in capsys.readouterr().out


def test_procs_inventory_orphans_age_text():
    assert [bl_procs.age_text(s) for s in (-5, 0, 59, 60, 3599, 3600, 7500, 86400, 90000)] == [
        "0s", "0s", "59s", "1m", "59m", "1h00m", "2h05m", "1d00h", "1d01h"]


# ---------------------------------------------------------------- the end

def fake_snap(*tabs_and_rows):
    """A `snap` giving each call the next (table, records): the clone as the first look and as the one after the grace."""
    calls = iter(tabs_and_rows)

    def snap(root):
        tab, rows = next(calls)
        cwds = {pid: root for pid in tab}
        return bl_procs.classify(bl_procs.inventory(root, tab, cwds, bases=[root]), tab, rows), tab, None
    return snap


def row(pid, tab):
    return {"pid": pid, "start": tab[pid][1], "comm": tab[pid][2]}


def run_end(snap, grace=7):
    said, slept, ended = [], [], []
    result = bl_procs.end_owned_orphans("/clone", grace, say=said.append, sleep=slept.append, snap=snap, ender=ended.append)
    return result, said, slept, ended


def test_procs_ends_only_own_after_the_grace_and_takes_the_tree():
    tab = {500: (1, 50, "node"), 501: (500, 51, "sh"), 502: (501, 52, "sleep"), 600: (1, 60, "claude"), 700: (1, 70, "sleep")}
    rows = [row(500, tab)]
    result, said, slept, ended = run_end(fake_snap((tab, rows), (tab, rows)))
    assert result == (1, 0)
    assert slept == [7], "the grace is slept once, between the two looks"
    assert ended == [502, 501, 500], "the process tree under it first, deepest first, then the orphan"
    text = "\n".join(said)
    assert "left pid 600 (claude)" in text and "left pid 700 (sleep)" in text and "never signaled" in text
    assert all(p not in ended for p in (600, 700)), "an unrecorded orphan and a foreign process are never ended"


def test_procs_ends_only_own_leaves_one_whose_parent_returned_or_whose_pid_was_reused():
    tab = {500: (1, 50, "node"), 800: (1, 80, "node")}
    rows = [row(500, tab), row(800, tab)]
    later = {500: (1, 99, "other"), 800: (4, 80, "node"), 4: (1, 3, "autopilot")}  # 500 reused by another start; 800 has a parent
    result, said, _, ended = run_end(fake_snap((tab, rows), (later, rows)))
    assert ended == [] and result == (0, 0), said
    text = "\n".join(said)
    assert "gone pid 500" in text and "left pid 800 (node): no longer an owned orphan (owned)" in text


def test_procs_ends_only_own_never_this_process_or_one_above_it():
    me = os.getpid()
    tab = {me: (900, 5, "python"), 900: (901, 4, "zsh"), 901: (1, 3, "claude")}
    rows = [row(901, tab), row(900, tab)]
    result, said, _, ended = run_end(fake_snap((tab, rows), (tab, rows)))
    assert ended == [] and result == (0, 0), (ended, said)
    assert "this process or one above it" in "\n".join(said)


def test_procs_ends_only_own_planted_ender_that_ignores_ownership_ends_a_foreign_one():
    tab = {600: (1, 60, "claude"), 601: (10, 61, "sleep"), 10: (11, 9, "zsh"), 11: (1, 8, "init")}
    result, said, _, ended = run_end(fake_snap((tab, []), (tab, [])))
    assert ended == [] and "no owned orphan to end" in "\n".join(said)
    real = bl_procs.classify
    planted = lambda procs, tab, rows: [dict(p, kind=bl_procs.OWNED_ORPHAN) for p in real(procs, tab, rows)]  # noqa: E731
    try:
        bl_procs.classify = planted
        _, _, _, ended = run_end(fake_snap((tab, []), (tab, [])))
    finally:
        bl_procs.classify = real
    assert ended, "the planted classifier ends processes it does not own: the assertions above would fail"
    with pytest.raises(AssertionError):
        assert ended == []


def test_procs_ends_only_own_a_host_that_cannot_check_ends_nothing():
    def snap(root):
        return None, None, "no /proc, and no lsof and ps, on this host"
    result, said, slept, ended = run_end(snap)
    assert result is None and ended == [] and slept == [] and "cannot check this host" in said[0]


@needs_cwd
def test_procs_ends_only_own_real_processes(clone, herd):
    root, work = clone
    owned_orphan, owned, foreign, orphan = herd.orphan(work), herd.child(work), herd.child(root), herd.orphan(work)
    reused = herd.orphan(root)
    bl_procs.record(str(root), [owned_orphan, owned, reused])
    rows = bl_procs.load_records(str(root))
    bl_procs.save_records(str(root), [dict(r, start=r["start"] - 1000) if r["pid"] == reused else r for r in rows])
    said = []
    result = bl_procs.end_owned_orphans(str(root), 0.2, say=said.append)
    assert result == (1, 0), said
    assert not alive(owned_orphan), "the owned orphan is ended"
    assert all(alive(p) for p in (owned, foreign, orphan, reused)), said
    text = "\n".join(said)
    assert f"ended pid {owned_orphan} " in text, text
    for named in (orphan, reused, foreign):
        assert f"left pid {named} " in text, "an unrecorded orphan, a reused pid and a foreign process are named"
    assert f"pid {owned} " not in text, "an owned process whose parent lives is neither ended nor named"


@needs_cwd
def test_procs_ends_only_own_real_process_tree(clone, herd):
    root, work = clone
    leader = herd.orphan(work, LEADER)  # a group leader with a child of its own
    child = next(q for q, v in bl_procs.process_table().items() if v[0] == leader)
    herd.pids.append(child)
    bl_procs.record(str(root), [leader])
    assert bl_procs.end_owned_orphans(str(root), 0.2, say=lambda t: None) == (1, 0)
    assert not alive(leader) and not alive(child), "the process tree goes with the owned orphan"


@needs_cwd
def test_procs_ends_only_own_through_the_command(clone, herd):
    root, work = clone
    owned_orphan, foreign = herd.orphan(work), herd.orphan(work)

    def procs(*args):
        p = subprocess.run([sys.executable, str(TOOL), "--root", str(root), "procs", *args], capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout_s(60), cwd=str(root.parent))
        return p.returncode, p.stdout + p.stderr

    code, out = procs("--record", str(owned_orphan))
    assert code == 0 and f"recorded pid {owned_orphan} " in out, out
    code, out = procs()
    assert code == 0 and f"pid {owned_orphan} " in out and "owned orphan" in out and f"pid {foreign} " in out, out
    assert procs("--grace", "1")[0] == 2, "--grace goes with --end"
    code, out = procs("--end", "--grace", "0.2")
    assert code == 0 and f"ended pid {owned_orphan} " in out and f"left pid {foreign} " in out, out
    assert not alive(owned_orphan) and alive(foreign)
    assert procs("--record", str(owned_orphan))[0] == 1, "a pid that no longer runs is refused"


@pytest.mark.parametrize("blind", [False, True])
def test_procs_ends_only_own_runner_leaves_none_behind(tmp_path, monkeypatch, blind):
    """The runner's child leads a group of its own that `supervise` ends whole when it returns: a process the child
    started in the background does not outlive the run. Planted (`blind`): a supervise that ends no group leaves it."""
    import autopilot
    if bl_procs.process_table() is None:
        pytest.skip("no process table on this host")
    if blind:
        monkeypatch.setattr(autopilot, "end_tree", lambda proc: None)
    pidfile = tmp_path / "bg.pid"
    code = ("import subprocess, sys; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], "
            "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
            f"open({str(pidfile)!r}, 'w').write(str(p.pid))")
    with open(tmp_path / "s.jsonl", "w", encoding="utf-8") as stream, open(tmp_path / "e.txt", "w", encoding="utf-8") as err:
        run = autopilot.supervise([sys.executable, "-c", code], tmp_path, stream, err)
    assert run["exit_code"] == 0
    pid = int(pidfile.read_text(encoding="utf-8"))
    try:
        assert wait_for(lambda: not alive(pid), 2 if blind else 10) != blind, "a background process outlived the run" if not blind else "planted"
    finally:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


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
