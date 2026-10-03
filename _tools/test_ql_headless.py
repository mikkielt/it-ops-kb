"""A headless runner (KB_HEADLESS_RUNNER, set by autopilot.py runner start) starts no distill: `querylog.py launch` and
ql_distill.launch, the SessionEnd and SessionStart launcher, do nothing and mark nothing there, so no process a runner
starts outlives its deadline or pushes outside the runner's land (kb/_self/querylog.md, Distill). Without the variable
the same event starts the distill, which a planted failure (the check removed) shows: the spy sees a spawn.

Every spawn is a spy: no test here starts a real distill."""
import datetime, io, json, os, subprocess, sys

import pytest

import kbpublic, ql_distill, querylog
from conftest import TOOLS, querylog_env

SID = "sess-headless-1"
VALUES = ["1", "yes"]  # any non-empty value counts: the runner sets "1"


def event(name):
    e = {"hook_event_name": name, "session_id": SID}
    if name == "SessionEnd":
        e["transcript_path"] = "transcript.jsonl"
    return e


def plant(data):
    """A closed session and a past day's tools file under data's spool: something a launch would distill."""
    sp = data / "querylog" / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / f"{SID}.jsonl").write_text("{}\n", encoding="utf-8", newline="\n")
    day = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).date().isoformat()
    (sp / f"tools-{day}.jsonl").write_text("{}\n", encoding="utf-8", newline="\n")
    return sp


@pytest.fixture
def spy(tmp_path, monkeypatch):
    """The plugin data under tmp_path with something ready to distill, and ql_distill.detach, the only place a launch
    starts a process, replaced by a recorder."""
    for k, v in querylog_env(tmp_path).items():
        if k.startswith("CLAUDE_PLUGIN_"):
            monkeypatch.setenv(k, v)
    monkeypatch.delenv(kbpublic.HEADLESS_ENV, raising=False)
    started = []
    monkeypatch.setattr(ql_distill, "detach", lambda argv, log: started.append(list(argv)) or 4242)
    return started, plant(tmp_path)


def launch_via_hook(ev):
    return ql_distill.launch(ev)


def launch_via_facade(ev, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(ev).encode("utf-8")), encoding="utf-8"))
    return querylog.main(["launch"])


def run(entry, ev, monkeypatch):
    return launch_via_hook(ev) if entry == "hook" else launch_via_facade(ev, monkeypatch)


def test_headless_env_is_the_runners_variable():
    assert ql_distill.HEADLESS_ENV == kbpublic.HEADLESS_ENV == "KB_HEADLESS_RUNNER"


@pytest.mark.parametrize("name", ["SessionEnd", "SessionStart"])
@pytest.mark.parametrize("entry", ["hook", "facade"])
@pytest.mark.parametrize("value", VALUES)
def test_launch_skipped_when_headless(spy, monkeypatch, entry, name, value):
    started, sp = spy
    monkeypatch.setenv(kbpublic.HEADLESS_ENV, value)
    before = sorted(p.name for p in sp.iterdir())
    run(entry, event(name), monkeypatch)
    assert started == []  # no process started
    assert sorted(p.name for p in sp.iterdir()) == before  # and the session not marked closed either
    assert not (sp.parent / ql_distill.LOG_NAME).exists()


@pytest.mark.parametrize("name", ["SessionEnd", "SessionStart"])
@pytest.mark.parametrize("entry", ["hook", "facade"])
@pytest.mark.parametrize("value", [None, ""])
def test_launch_skipped_when_headless_unset_or_empty_still_starts(spy, monkeypatch, entry, name, value):
    started, sp = spy  # the planted contrast: without the variable (or empty) the same event starts the distill
    if value is not None:
        monkeypatch.setenv(kbpublic.HEADLESS_ENV, value)
    run(entry, event(name), monkeypatch)
    assert len(started) == 1 and started[0][2:3] == ["distill"], started
    if name == "SessionEnd":
        assert "--session" in started[0] and (sp / f"{SID}.end").exists()


def test_launch_skipped_when_headless_as_the_hook_command_runs_it(tmp_path):
    """The hook is a process: with the variable set, `querylog.py launch` exits 0, prints nothing and leaves the
    spool as it was (no distill.log, no run file, no marker)."""
    sp = plant(tmp_path)
    before = sorted(p.name for p in sp.iterdir())
    env = querylog_env(tmp_path)
    env[kbpublic.HEADLESS_ENV] = "1"
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "querylog.py"), "launch"],
                       input=json.dumps(event("SessionEnd")).encode("utf-8"), capture_output=True, env=env, timeout=60)
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"")
    assert sorted(x.name for x in sp.iterdir()) == before
    assert not (tmp_path / "querylog" / ql_distill.LOG_NAME).exists()
    assert not (tmp_path / "querylog" / "store").exists()
