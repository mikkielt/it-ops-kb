"""The bugs a run filed and the gates it added are read at the integration main, not the runner worktree's HEAD: a
worker that files a bug or adds a gate and lands it through a code/<id> merge request leaves the item file on the
integration remote's main only, so `autopilot.bugs_filed` and `autopilot.gates_of_run` (and the `bugs` and `gates`
lines of `runner-status`) read the files at `autopilot.integration_tip`, the tip `landed_items` counts to. The tests
named run_report_reads_integration_tip are the bug's checks. Throwaway repositories with a local bare remote; no
network, no process but git and a fake claude."""
import json, subprocess
from pathlib import Path

import pytest

import autopilot, bl_base
from conftest import Repo, git_env
from test_autopilot import SP, T1, T2, T3, stream, world as _world_fixture

world = _world_fixture

BUGS = [f"BG-{c}{'b' * 7}" for c in "abcdefg"]  # bug items the run files, eight characters after the prefix
REL = bl_base.REL_DIR


class Lander:
    """A second clone of the world's origin that lands commits on its main the way a code/<id> merge request does: the
    runner worktree's branch never gets them."""

    def __init__(self, world):
        self.world = world
        path = world.tmp / f"lander{len(list(world.tmp.glob('lander*')))}"  # one clone for each lander
        self.repo = Repo(path, git_env())
        path.mkdir()
        subprocess.run(["git", "clone", "-q", str(world.tmp / "origin.git"), str(path)], env=git_env(), check=True,
                       capture_output=True)

    def land(self, files, msg="feat: land"):
        """FILES ({item id: object, or raw text}) written under the backlog directory, committed, pushed to main."""
        self.repo.git("pull", "-q", "--ff-only", "origin", "main")
        for iid, data in files.items():
            text = data if isinstance(data, str) else json.dumps(data, indent=2) + "\n"
            self.repo.write(f"{REL}/{iid}.json", text)
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "--allow-empty", "-m", msg)
        self.repo.git("push", "-q", "origin", "HEAD:main")

    def bug(self, iid):
        return {"id": iid, "kind": "bug", "title": "b " + iid, "status": "todo"}

    def read(self, iid):
        return json.loads((Path(self.repo.path) / REL / f"{iid}.json").read_text(encoding="utf-8"))

    def with_gates(self, iid, gates):
        """The item IID of the lander's tree, its gates replaced by GATES."""
        return {**self.read(iid), "gates": gates}


def gate(gid, answer=None):
    g = {"id": gid, "kind": "blocking" if answer is None else "provisional", "question": "q"}
    return g if answer is None else {**g, "answer": answer, "by": "agent"}


def started(world):
    """The world's run, ended, and its lander; the runner worktree stays at its start commit."""
    world.stream(stream())
    assert world.start() == 0
    return Lander(world), world.status()["start_ref"]


def report(world, start):
    wt = world.wt()
    bl = bl_base.Backlog(wt)
    tip = autopilot.integration_tip(wt)
    ids = set(bl.sprint_items(SP))
    return (autopilot.bugs_filed(wt, bl, start, tip), autopilot.gates_of_run(wt, bl, ids, start, tip),
            autopilot.bugs_filed(wt, bl, start, "HEAD"), autopilot.gates_of_run(wt, bl, ids, start, "HEAD"))


def test_run_report_reads_integration_tip_signature_takes_a_tip():
    import inspect
    for f in (autopilot.bugs_filed, autopilot.gates_of_run):
        assert inspect.signature(f).parameters["tip"].default == "HEAD"


@pytest.mark.parametrize("n_bugs", range(0, 5))
@pytest.mark.parametrize("n_gates", range(0, 6))
def test_run_report_reads_integration_tip_finds_a_bug_and_gates_only_on_origin_main(world, n_bugs, n_gates):
    """(1) n bug files and n gates added only on origin's main: bugs_filed, gates_of_run and the status lines find them
    all, whatever the counts; the planted failure (5) is the HEAD-based reading, which finds none of them."""
    lander, start = started(world)
    tasks = [T1, T2, T3]
    per = {t: [] for t in tasks}
    for i in range(n_gates):
        per[tasks[i % 3]].append(gate(f"g{i}"))
    files = {BUGS[i]: lander.bug(BUGS[i]) for i in range(n_bugs)}
    files.update({t: lander.with_gates(t, per[t]) for t in tasks if per[t]})
    lander.land(files)
    bugs, gates, old_bugs, old_gates = report(world, start)
    assert bugs == sorted(BUGS[:n_bugs])
    assert gates == [f"{t}/{g['id']}=open" for t in sorted(tasks) for g in per[t]]
    assert old_bugs == [] and old_gates == []  # (5) the reading of the worktree's HEAD sees neither
    assert autopilot.bugs_filed(world.wt(), None, start) == []  # and so does the default tip
    text = autopilot.status_text(SP, world.root)
    assert f"bugs {n_bugs}" in text and f"gates {n_gates}" in text
    if n_bugs:
        assert f"bugs {n_bugs}: {BUGS[0]}" in text
    if n_gates:
        assert "/g0=open" in text


def test_run_report_reads_integration_tip_status_text_names_the_bug_and_the_gate(world):
    lander, start = started(world)
    lander.land({BUGS[0]: lander.bug(BUGS[0]), T3: lander.with_gates(T3, [gate("name", "recommend"), gate("ask")])})
    text = autopilot.status_text(SP, world.root)
    assert f"bugs 1: {BUGS[0]}" in text
    assert f"gates 2: {T3}/name=recommend, {T3}/ask=open" in text


@pytest.mark.parametrize("commits", range(0, 4))
def test_run_report_reads_integration_tip_a_blocked_run_finds_none(world, commits):
    """(2) nothing of the sprint on origin's main since the start (only unrelated commits there): no bug, no gate."""
    lander, start = started(world)
    for i in range(commits):
        lander.land({}, msg=f"docs: unrelated {i}")
    bugs, gates, old_bugs, old_gates = report(world, start)
    assert bugs == gates == old_bugs == old_gates == []
    text = autopilot.status_text(SP, world.root)
    assert "bugs 0" in text and "gates 0" in text and "bugs 0:" not in text and "gates 0:" not in text


@pytest.mark.parametrize("before", range(1, 4))
@pytest.mark.parametrize("after", range(0, 3))
def test_run_report_reads_integration_tip_leaves_out_bug_files_added_before_the_start(world, before, after):
    """(3) bug files on origin's main before the run's start ref are not the run's: only the `after` ones are listed."""
    pre = Lander(world)
    pre.land({BUGS[i]: pre.bug(BUGS[i]) for i in range(before)})
    lander, start = started(world)
    lander.land({BUGS[before + i]: lander.bug(BUGS[before + i]) for i in range(after)})
    bugs, _, _, _ = report(world, start)
    assert bugs == sorted(BUGS[before:before + after])


def test_run_report_reads_integration_tip_lists_bugs_only(world):
    """(4) a story, a task, an item of no kind and files that are no JSON object, added on main, are no bug; a bug
    named like a file that does not parse is skipped without a failure."""
    lander, start = started(world)
    lander.land({"ST-ffffffff": {"id": "ST-ffffffff", "kind": "story", "title": "s"},
                 "TK-gggggggg": {"id": "TK-gggggggg", "kind": "task", "title": "t"},
                 "TK-hhhhhhhh": {"id": "TK-hhhhhhhh", "title": "t"},
                 "BG-iiiiiiii": "{not json",
                 "BG-jjjjjjjj": "[1, 2]\n",
                 "BG-kkkkkkkk": "",
                 BUGS[0]: lander.bug(BUGS[0])})
    bugs, _, _, _ = report(world, start)
    assert bugs == [BUGS[0]]
    assert "bugs 1: " + BUGS[0] in autopilot.status_text(SP, world.root)


def test_run_report_reads_integration_tip_gates_added_since_the_start_or_still_open(world):
    """A gate that was answered before the start and is unchanged is not the run's; one open at the start is still
    open; a gate the run added is listed with its answer or open; an item the tip lacks has no gates."""
    pre = Lander(world)
    pre.land({T1: pre.with_gates(T1, [gate("old", "yes")]), T2: pre.with_gates(T2, [gate("open1")]),
              T3: pre.with_gates(T3, [gate("gone")])})
    lander, start = started(world)
    lander.land({T1: lander.with_gates(T1, [gate("old", "yes"), gate("new", "recommend")]),
                 T2: lander.with_gates(T2, [gate("open1"), gate("new2")])})
    subprocess.run(["git", "rm", "-q", f"{REL}/{T3}.json"], cwd=lander.repo.path, check=True, capture_output=True,
                   env=git_env())
    lander.repo.git("commit", "-q", "-m", "chore: drop")
    lander.repo.git("push", "-q", "origin", "HEAD:main")
    _, gates, _, _ = report(world, start)
    assert gates == [f"{T1}/new=recommend", f"{T2}/open1=open", f"{T2}/new2=open"]


def test_run_report_reads_integration_tip_gate_answered_on_main_is_no_longer_open(world):
    """A gate open at the start and answered on the integration main since is not listed: the tip's answer stands."""
    pre = Lander(world)
    pre.land({T1: pre.with_gates(T1, [gate("g")])})
    lander, start = started(world)
    lander.land({T1: lander.with_gates(T1, [gate("g", "go")])})
    assert report(world, start)[1] == []


def test_run_report_reads_integration_tip_fetches_once(world, monkeypatch):
    """(6) status_text fetches the integration remote once for all three sections."""
    lander, start = started(world)
    lander.land({BUGS[0]: lander.bug(BUGS[0])})
    fetches = []
    real = subprocess.run

    def spy(argv, *a, **kw):
        if argv[:2] == ["git", "fetch"]:
            fetches.append(argv)
        return real(argv, *a, **kw)

    monkeypatch.setattr(autopilot.subprocess, "run", spy)
    assert "bugs 1: " + BUGS[0] in autopilot.status_text(SP, world.root)
    assert len(fetches) == 1 and fetches[0][-2:] == ["origin", "main"]


def test_run_report_reads_integration_tip_uses_the_local_ref_when_the_fetch_fails(world, tmp_path):
    """No remote to fetch from but a local refs/remotes/origin/main that holds the files: the report finds them."""
    lander, start = started(world)
    lander.land({BUGS[0]: lander.bug(BUGS[0]), T3: lander.with_gates(T3, [gate("g")])})
    Repo(world.wt(), git_env()).git("fetch", "-q", "origin")
    (tmp_path / "origin.git").rename(tmp_path / "gone.git")
    text = autopilot.status_text(SP, world.root)
    assert f"bugs 1: {BUGS[0]}" in text and f"gates 1: {T3}/g=open" in text


def test_run_report_reads_integration_tip_never_raises_on_a_git_failure(tmp_path):
    """No repository, a start ref and a tip git does not know: the empty report, as before."""
    nowhere = tmp_path / "missing"
    assert autopilot.bugs_filed(nowhere, None, "0" * 40, "HEAD") == []
    assert autopilot.gates_of_run(nowhere, None, {T1}, "0" * 40, "HEAD") == []
    repo = Repo(tmp_path / "r", git_env())
    (tmp_path / "r").mkdir()
    repo.git("init", "-b", "main")
    repo.git("commit", "-q", "--allow-empty", "-m", "seed")
    assert autopilot.bugs_filed(repo.path, None, "0" * 40, "refs/remotes/origin/main") == []
    assert autopilot.bugs_filed(repo.path, None, "", "HEAD") == []
    assert autopilot.gates_of_run(repo.path, None, {T1}, "", "refs/remotes/origin/main") == []
