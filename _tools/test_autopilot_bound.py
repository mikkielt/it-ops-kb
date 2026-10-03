"""The bounds of a sprint runner's headless child (autopilot.py): the turn limit in its `claude` command, the wall-clock
deadline that ends a child that outlives it (and its process tree) with the cause `timeout`, and the age a run's report
shows, with `stalled` once a running run is past its deadline. The tests named autopilot_run_is_bounded are the bug's
checks. No real signal reaches another process: the fake child lives a few seconds at most by itself."""
import datetime, json, os, re, sys, threading, time
from pathlib import Path

import pytest

import autopilot, bl_base
from test_autopilot import World, SP, stream

SLEEPER = '''import os, signal, subprocess, sys, time
life = os.environ["FAKE_LIFE"]
if os.environ.get("FAKE_IGNORE_TERM"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(" + life + ")"])
open(os.environ["FAKE_PIDS"], "w", encoding="utf-8").write(str(os.getpid()) + " " + str(kid.pid))
sys.stdout.write('{"type": "system", "subtype": "init"}\\n')
sys.stdout.flush()
time.sleep(float(life))
'''
T0 = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in (autopilot.TURNS_ENV, autopilot.DEADLINE_ENV):
        monkeypatch.delenv(name, raising=False)
    return World(tmp_path, monkeypatch)


def stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def turn_limit(argv):
    """The number after --max-turns in ARGV; None when the flag is not there."""
    return int(argv[argv.index("--max-turns") + 1]) if "--max-turns" in argv else None


def alive_soon_gone(pid, wait=5.0):
    """Whether PID still runs after up to WAIT seconds (an orphan is reaped a moment after its group is killed)."""
    end = time.monotonic() + wait
    while time.monotonic() < end:
        if not bl_base.pid_alive(pid):
            return False
        time.sleep(0.05)
    return bl_base.pid_alive(pid)


def run_sleeper(world, life, deadline, ignore_term=False):
    """Run the sprint against a child that starts a grandchild and then sleeps LIFE seconds, with the deadline DEADLINE.
    Returns (exit code, seconds the run took, the child's and the grandchild's pids)."""
    script = world.tmp / "sleeper_claude.py"
    script.write_text(SLEEPER, encoding="utf-8", newline="\n")
    pids = world.tmp / "pids.txt"
    world.mp.setattr(autopilot, "CLAUDE", [sys.executable, str(script)])
    world.mp.setenv("FAKE_LIFE", str(life))
    world.mp.setenv("FAKE_PIDS", str(pids))
    world.mp.setenv(autopilot.DEADLINE_ENV, str(deadline))
    if ignore_term:
        world.mp.setenv("FAKE_IGNORE_TERM", "1")
    t = time.monotonic()
    code = world.start()
    took = time.monotonic() - t
    child, grandchild = (int(x) for x in pids.read_text(encoding="utf-8").split())
    return code, took, child, grandchild


# ---------------------------------------------------------------- the turn limit is in the child's command

def test_autopilot_run_is_bounded_by_a_turn_limit_in_the_claude_argv():
    argv = autopilot.claude_argv(Path("."), SP)
    assert turn_limit(argv) == autopilot.MAX_TURNS and autopilot.MAX_TURNS > 0
    assert argv.count("--max-turns") == 1


@pytest.mark.parametrize("value", ["1", "7", "500", "12345"])
def test_autopilot_run_is_bounded_the_turn_limit_follows_its_environment_override(monkeypatch, value):
    monkeypatch.setenv(autopilot.TURNS_ENV, value)
    assert turn_limit(autopilot.claude_argv(Path("."), SP, 3)) == int(value)


@pytest.mark.parametrize("value", ["0", "-3", "x", "", "1.5", "1e3", "nan"])
def test_autopilot_run_is_bounded_a_bad_turn_override_keeps_the_default(monkeypatch, value):
    monkeypatch.setenv(autopilot.TURNS_ENV, value)
    assert turn_limit(autopilot.claude_argv(Path("."), SP)) == autopilot.MAX_TURNS


@pytest.mark.parametrize("value", ["0", "-1", "abc", "nan", "inf", ""])
def test_autopilot_run_is_bounded_a_bad_deadline_override_keeps_the_default(monkeypatch, value):
    monkeypatch.setenv(autopilot.DEADLINE_ENV, value)
    assert autopilot.deadline_s() == autopilot.DEADLINE_S


@pytest.mark.parametrize("value", ["0.5", "1", "90", "21600"])
def test_autopilot_run_is_bounded_the_deadline_follows_its_environment_override(monkeypatch, value):
    monkeypatch.setenv(autopilot.DEADLINE_ENV, value)
    assert autopilot.deadline_s() == float(value)


def test_autopilot_run_is_bounded_the_child_the_runner_starts_gets_the_limit_and_the_status_keeps_both_bounds(world, monkeypatch):
    monkeypatch.setenv(autopilot.TURNS_ENV, "41")
    monkeypatch.setenv(autopilot.DEADLINE_ENV, "900")
    world.stream(stream())
    assert world.start() == 0
    assert turn_limit(world.seen()["argv"]) == 41
    st = world.status()
    assert st["max_turns"] == 41 and st["deadline_s"] == 900


def test_autopilot_run_is_bounded_a_planted_argv_without_the_limit_fails_the_check(world, monkeypatch):
    real = autopilot.claude_argv

    def without(*a, **k):
        argv = real(*a, **k)
        i = argv.index("--max-turns")
        return argv[:i] + argv[i + 2:]

    monkeypatch.setattr(autopilot, "claude_argv", without)
    world.stream(stream())
    world.start()
    assert turn_limit(world.seen()["argv"]) is None  # what the checks above refuse


# ---------------------------------------------------------------- the deadline ends a child that outlives it

@pytest.mark.parametrize("deadline, ignore_term", [(0.5, False), (1, False), (2, False), (1, True)])
def test_autopilot_run_is_bounded_the_deadline_ends_a_sleeping_child_and_its_tree_with_the_cause_timeout(
        world, monkeypatch, deadline, ignore_term):
    monkeypatch.setattr(autopilot, "GRACE_S", 0.3)  # a child that ignores SIGTERM is ended at its group after this
    code, took, child, grandchild = run_sleeper(world, 60, deadline, ignore_term)
    assert took < 30  # the child sleeps a minute: it was ended, not awaited
    st = world.status()
    assert code == 1 and st["cause"] == "timeout" and st["ended"] and st["exit_code"] != 0
    assert f"{deadline:g}s" in st["detail"] and st["deadline_s"] == deadline
    assert not alive_soon_gone(child) and not alive_soon_gone(grandchild)  # the process tree is gone, not just the child
    assert not bl_base.runner_record_path(os.getpid()).exists()  # the host slot is free again
    assert not [t for t in threading.enumerate() if isinstance(t, threading.Timer)]  # the deadline's timer is gone
    text = autopilot.status_text(SP, world.root)
    assert text.startswith(f"{SP} exit cause timeout") and ", ran " in text


def test_autopilot_run_is_bounded_a_run_within_its_deadline_is_not_ended_and_is_not_a_timeout(world):
    code, took, child, grandchild = run_sleeper(world, 2, 600)
    assert took >= 1.5  # it lived its life
    st = world.status()
    assert st["cause"] == "error" and "no result event" in st["detail"] and code == 1  # the child ended by itself
    assert not [t for t in threading.enumerate() if isinstance(t, threading.Timer)]  # nothing is left waiting 600 seconds


def test_autopilot_run_is_bounded_a_planted_end_that_leaves_the_tree_alive_fails_the_check(world, monkeypatch):
    """With end_tree reduced to killing the child alone, the grandchild holds the child's stdout open and the run waits
    for its few seconds instead of ending: the checks above (the run takes far less than the child's life) refuse that."""
    monkeypatch.setattr(autopilot, "end_tree", lambda proc: proc.kill())
    code, took, child, grandchild = run_sleeper(world, 5, 1)
    assert world.status()["cause"] == "timeout"
    assert took >= 4


def test_autopilot_run_is_bounded_a_timeout_after_a_compaction_is_not_recorded_over_it(world):
    """The child is ended at its first compact_boundary; a deadline that comes after does not rewrite that cause."""
    world.stream(stream(boundary=True), hang_after="compact_boundary")
    world.mp.setenv(autopilot.DEADLINE_ENV, "30")
    assert world.start() == 0
    assert world.status()["cause"] == "compaction"


# ---------------------------------------------------------------- the age line

@pytest.mark.parametrize("seconds", [0, 1, 59, 60, 61, 3599, 3600, 3661, 7499, 21600, 86399, 86400, 90000, 400000])
def test_autopilot_run_is_bounded_age_text_names_the_span(seconds):
    text = autopilot.age_text(seconds)
    if seconds < 60:
        assert text == f"{seconds}s"
    elif seconds < 3600:
        assert text == f"{seconds // 60}m"
    elif seconds < 86400:
        assert text == f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"
    else:
        assert text == f"{seconds // 86400}d{seconds % 86400 // 3600:02d}h"


def test_autopilot_run_is_bounded_age_text_never_runs_backwards_over_a_range_of_spans():
    last = -1
    for s in range(0, 300000, 37):
        m = re.fullmatch(r"(?:(\d+)d(\d\d)h|(\d+)h(\d\d)m|(\d+)m|(\d+)s)", autopilot.age_text(s))
        assert m, s
        d, dh, h, hm, mi, sec = m.groups()
        floor = (int(d) * 86400 + int(dh) * 3600 if d else int(h) * 3600 + int(hm) * 60 if h else
                 int(mi) * 60 if mi else int(sec))
        assert floor <= s and floor >= last  # the text names the span rounded down, and a longer span never reads shorter
        last = floor


@pytest.mark.parametrize("deadline", [1, 60, 3600, 21600])
@pytest.mark.parametrize("delta", [-61, -1, 0, 1, 61])
def test_autopilot_run_is_bounded_a_running_run_is_stalled_only_past_its_deadline(monkeypatch, deadline, delta):
    monkeypatch.setattr(autopilot, "now", lambda: T0)
    age = max(0, deadline + delta)
    st = {"cause": "running", "pid": 7, "started": stamp(T0 - datetime.timedelta(seconds=age)), "deadline_s": deadline}
    label = autopilot.age_label(st)
    assert label.startswith("age " + autopilot.age_text(age))
    assert label.endswith(" stalled") == (age > deadline)  # the planted wrong bound (>=, or none) fails here


def test_autopilot_run_is_bounded_an_ended_run_shows_how_long_it_ran_and_is_never_stalled(monkeypatch):
    monkeypatch.setattr(autopilot, "now", lambda: T0)
    for cause in ("timeout", "error", "compaction", "sprint-done"):
        st = {"cause": cause, "pid": 7, "deadline_s": 60, "started": stamp(T0 - datetime.timedelta(hours=9)),
              "ended": stamp(T0 - datetime.timedelta(hours=2, minutes=5))}
        assert autopilot.age_label(st) == "ran 6h55m"


@pytest.mark.parametrize("st", [None, [], {}, {"cause": "running"}, {"cause": "running", "started": "yesterday"},
                                {"cause": "error", "started": stamp(T0)}, {"cause": "error", "ended": stamp(T0)}])
def test_autopilot_run_is_bounded_a_status_with_no_readable_times_shows_no_age(monkeypatch, st):
    monkeypatch.setattr(autopilot, "now", lambda: T0)
    assert autopilot.age_label(st) == ""


def test_autopilot_run_is_bounded_the_age_of_another_runners_status_is_not_shown(monkeypatch):
    monkeypatch.setattr(autopilot, "now", lambda: T0)
    st = {"cause": "running", "pid": 7, "started": stamp(T0), "deadline_s": 60}
    assert autopilot.age_label(st, 7) == "age 0s" and autopilot.age_label(st, 8) == ""


def replant(world, **kw):
    """The run's status.json, rewritten as a run still running with the changes KW."""
    path = autopilot.cache_dir(world.root, SP) / "status.json"
    st = {**json.loads(path.read_text(encoding="utf-8")), "cause": "running", "ended": None, "pid": os.getpid(), **kw}
    path.write_text(json.dumps(st), encoding="utf-8")
    return st


@pytest.mark.parametrize("hours, deadline, stalled", [(7, 6 * 3600, True), (5, 6 * 3600, False), (1, 600, True), (0, 600, False)])
def test_autopilot_run_is_bounded_runner_status_and_status_show_the_age_and_mark_a_late_run_stalled(
        world, monkeypatch, hours, deadline, stalled):
    world.stream(stream())
    world.start()
    monkeypatch.setattr(autopilot, "now", lambda: T0)
    replant(world, started=stamp(T0 - datetime.timedelta(hours=hours, seconds=1)), deadline_s=deadline)
    text = autopilot.status_text(SP, world.root)
    age = autopilot.age_text(hours * 3600 + 1)
    assert "exit cause running" in text and f"age {age}" in text and len(text) < autopilot.STATUS_MAX
    assert (" stalled" in text) == stalled
    bl_base.runner_record_path(os.getpid()).write_text(
        json.dumps({"pid": os.getpid(), "sprint": SP, "clone": str(world.root), "started": stamp(T0)}), encoding="utf-8")
    (line,) = autopilot.runner_lines(str(world.root), 9)
    assert line == f"runners 1: {SP} pid {os.getpid()} alive worktree clone age {age}" + (" stalled" if stalled else "")
